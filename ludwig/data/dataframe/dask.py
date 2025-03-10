#! /usr/bin/env python
# Copyright (c) 2020 Uber Technologies, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ==============================================================================

import logging
import os
from typing import Dict

import dask
import dask.array as da
import dask.dataframe as dd
import pandas as pd
import ray
from dask.diagnostics import ProgressBar
from packaging import version
from pyarrow.fs import FSSpecHandler, PyFileSystem
from ray.data import read_parquet
from ray.data.extensions import TensorArray

from ludwig.data.dataframe.base import DataFrameEngine
from ludwig.globals import PREDICTIONS_SHAPES_FILE_NAME
from ludwig.utils.data_utils import get_pa_schema, load_json, save_json, split_by_slices
from ludwig.utils.dataframe_utils import flatten_df, set_index_name, unflatten_df
from ludwig.utils.fs_utils import get_fs_and_path

_ray200 = version.parse(ray.__version__) >= version.parse("2.0")

TMP_COLUMN = "__TMP_COLUMN__"


logger = logging.getLogger(__name__)


def set_scheduler(scheduler):
    dask.config.set(scheduler=scheduler)


def reset_index_across_all_partitions(df):
    """Compute a monotonically increasing index across all partitions.

    This differs from dd.reset_index, which computes an independent index for each partition.
    Source: https://stackoverflow.com/questions/61395351/how-to-reset-index-on-concatenated-dataframe-in-dask
    """
    # Create temporary column of ones
    df = df.assign(**{TMP_COLUMN: 1})

    # Set the index to the cumulative sum of TMP_COLUMN, which we know to be sorted; this improves efficiency.
    df = df.set_index(df[TMP_COLUMN].cumsum() - 1, sorted=True)

    # Drop temporary column and ensure the index is not named TMP_COLUMN
    df = df.drop(columns=TMP_COLUMN)
    df = df.map_partitions(lambda pd_df: set_index_name(pd_df, None))
    return df


class DaskEngine(DataFrameEngine):
    def __init__(self, parallelism=None, persist=True, _use_ray=True, **kwargs):
        from ray.util.dask import ray_dask_get

        self._parallelism = parallelism
        self._persist = persist
        if _use_ray:
            set_scheduler(ray_dask_get)

    def set_parallelism(self, parallelism):
        self._parallelism = parallelism

    def df_like(self, df: dd.DataFrame, proc_cols: Dict[str, dd.Series]):
        """Outer joins the given DataFrame with the given processed columns.

        NOTE: If any of the processed columns have been repartitioned, the original index is replaced with a
        monotonically increasing index, which is used to define the new divisions and align the various partitions.
        """
        # Our goal is to preserve the index of the input dataframe but to drop
        # all its columns. Because to_frame() creates a column from the index,
        # we need to drop it immediately following creation.
        dataset = df.index.to_frame(name=TMP_COLUMN).drop(columns=TMP_COLUMN)

        repartitioned_cols = {}
        for k, v in proc_cols.items():
            if v.npartitions == dataset.npartitions:
                # Outer join cols with equal partitions
                v.divisions = dataset.divisions
                dataset[k] = v
            else:
                # If partitions have changed (e.g. due to conversion from Ray dataset), we handle separately
                repartitioned_cols[k] = v

        # Assumes that there is a globally unique index (see preprocessing.build_dataset)
        if repartitioned_cols:
            if not dataset.known_divisions:
                # Sometimes divisions are unknown despite having a usable index– set_index to know divisions
                dataset = dataset.assign(**{TMP_COLUMN: dataset.index})
                dataset = dataset.set_index(TMP_COLUMN, drop=True)
                dataset = dataset.map_partitions(lambda pd_df: set_index_name(pd_df, dataset.index.name))

            # Find the divisions of the column with the largest number of partitions
            proc_col_with_max_npartitions = max(repartitioned_cols.values(), key=lambda x: x.npartitions)
            new_divisions = proc_col_with_max_npartitions.divisions

            # Repartition all columns to have the same divisions
            dataset = dataset.repartition(new_divisions)
            repartitioned_cols = {k: v.repartition(new_divisions) for k, v in repartitioned_cols.items()}

            # Outer join the remaining columns
            for k, v in repartitioned_cols.items():
                dataset[k] = v

        return dataset

    def parallelize(self, data):
        if self.parallelism:
            return data.repartition(self.parallelism)
        return data

    def persist(self, data):
        # No graph optimizations to prevent dropping custom annotations
        # https://github.com/dask/dask/issues/7036
        return data.persist(optimize_graph=False) if self._persist else data

    def concat(self, dfs):
        return self.df_lib.multi.concat(dfs)

    def compute(self, data):
        return data.compute()

    def from_pandas(self, df):
        parallelism = self._parallelism or 1
        return dd.from_pandas(df, npartitions=parallelism)

    def map_objects(self, series, map_fn, meta=None):
        meta = meta if meta is not None else ("data", "object")
        return series.map(map_fn, meta=meta)

    def map_partitions(self, series, map_fn, meta=None):
        meta = meta if meta is not None else ("data", "object")
        return series.map_partitions(map_fn, meta=meta)

    def map_batches(self, series, map_fn):
        import ray.data

        ds = ray.data.from_dask(series)
        ds = ds.map_batches(map_fn, batch_format="pandas")
        return ds.to_dask()

    def apply_objects(self, df, apply_fn, meta=None):
        meta = meta if meta is not None else ("data", "object")
        return df.apply(apply_fn, axis=1, meta=meta)

    def reduce_objects(self, series, reduce_fn):
        return series.reduction(reduce_fn, aggregate=reduce_fn, meta=("data", "object")).compute()[0]

    def split(self, df, probabilities):
        # Split the DataFrame proprotionately along partitions. This is an inexact solution designed
        # to speed up the split process, as splitting within partitions would be significantly
        # more expensive.
        # TODO(travis): revisit in the future to make this more precise

        # First ensure that every split receives at least one partition.
        # If not, we need to increase the number of partitions to satisfy this constraint.
        min_prob = min(probabilities)
        min_partitions = int(1 / min_prob)
        if df.npartitions < min_partitions:
            df = df.repartition(min_partitions)

        n = df.npartitions
        slices = df.partitions
        return split_by_slices(slices, n, probabilities)

    def remove_empty_partitions(self, df):
        # Reference: https://stackoverflow.com/questions/47812785/remove-empty-partitions-in-dask
        ll = list(df.map_partitions(len).compute())
        if all([ll_i > 0 for ll_i in ll]):
            return df

        df_delayed = df.to_delayed()
        df_delayed_new = list()
        empty_partition = None
        for ix, n in enumerate(ll):
            if n == 0:
                empty_partition = df.get_partition(ix)
            else:
                df_delayed_new.append(df_delayed[ix])
        df = dd.from_delayed(df_delayed_new, meta=empty_partition)
        return df

    def to_parquet(self, df, path, index=False):
        schema = get_pa_schema(df)
        with ProgressBar():
            df.to_parquet(
                path,
                engine="pyarrow",
                write_index=index,
                schema=schema,
            )

    def write_predictions(self, df: dd.DataFrame, path: str):
        if not _ray200:
            # fallback to slow flatten_df
            df, column_shapes = flatten_df(df, self)
            self.to_parquet(df, path)
            save_json(os.path.join(os.path.dirname(path), PREDICTIONS_SHAPES_FILE_NAME), column_shapes)
            return

        ds = self.to_ray_dataset(df)

        def to_tensors(batch: pd.DataFrame) -> pd.DataFrame:
            data = {}
            for c in batch.columns:
                try:
                    data[c] = TensorArray(batch[c])
                except TypeError:
                    # Not a tensor, likely a string which pyarrow can handle natively
                    pass
            return pd.DataFrame(data)

        ds = ds.map_batches(to_tensors)

        fs, path = get_fs_and_path(path)
        ds.write_parquet(path, filesystem=PyFileSystem(FSSpecHandler(fs)))

    def read_predictions(self, path: str) -> dd.DataFrame:
        if not _ray200:
            # fallback to slow unflatten_df
            pred_df = dd.read_parquet(path)
            column_shapes = load_json(os.path.join(os.path.dirname(path), PREDICTIONS_SHAPES_FILE_NAME))
            return unflatten_df(pred_df, column_shapes, self)

        fs, path = get_fs_and_path(path)
        ds = read_parquet(path, filesystem=PyFileSystem(FSSpecHandler(fs)))
        return self.from_ray_dataset(ds)

    def to_ray_dataset(self, df):
        from ray.data import from_dask

        return from_dask(df)

    def from_ray_dataset(self, dataset) -> dd.DataFrame:
        return dataset.to_dask()

    def reset_index(self, df):
        return reset_index_across_all_partitions(df)

    @property
    def array_lib(self):
        return da

    @property
    def df_lib(self):
        return dd

    @property
    def parallelism(self):
        return self._parallelism

    @property
    def partitioned(self):
        return True
