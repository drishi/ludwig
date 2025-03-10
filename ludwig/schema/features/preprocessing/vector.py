from marshmallow_dataclass import dataclass

from ludwig.constants import DROP_ROW, MISSING_VALUE_STRATEGY_OPTIONS, PREPROCESSING, VECTOR
from ludwig.schema import utils as schema_utils
from ludwig.schema.features.preprocessing.base import BasePreprocessingConfig
from ludwig.schema.features.preprocessing.utils import register_preprocessor
from ludwig.schema.metadata.feature_metadata import FEATURE_METADATA


@register_preprocessor(VECTOR)
@dataclass(repr=False)
class VectorPreprocessingConfig(BasePreprocessingConfig):

    vector_size: int = schema_utils.PositiveInteger(
        default=None,
        allow_none=True,
        description="The size of the vector. If None, the vector size will be inferred from the data.",
        parameter_metadata=FEATURE_METADATA[VECTOR][PREPROCESSING]["vector_size"],
    )

    missing_value_strategy: str = schema_utils.StringOptions(
        MISSING_VALUE_STRATEGY_OPTIONS,
        default="fill_with_const",
        allow_none=False,
        description="What strategy to follow when there's a missing value in a vector column",
        parameter_metadata=FEATURE_METADATA[VECTOR][PREPROCESSING]["missing_value_strategy"],
    )

    fill_value: str = schema_utils.String(
        default="",
        allow_none=False,
        pattern=r"^([0-9]+(\.[0-9]*)?\s*)*$",
        description="The value to replace missing values with in case the missing_value_strategy is fill_with_const",
        parameter_metadata=FEATURE_METADATA[VECTOR][PREPROCESSING]["fill_value"],
    )

    computed_fill_value: str = schema_utils.String(
        default="",
        allow_none=False,
        pattern=r"^([0-9]+(\.[0-9]*)?\s*)*$",
        description="The internally computed fill value to replace missing values with in case the "
        "missing_value_strategy is fill_with_mode or fill_with_mean",
        parameter_metadata=FEATURE_METADATA[VECTOR][PREPROCESSING]["computed_fill_value"],
    )


@register_preprocessor("vector_output")
@dataclass(repr=False)
class VectorOutputPreprocessingConfig(VectorPreprocessingConfig):

    missing_value_strategy: str = schema_utils.StringOptions(
        MISSING_VALUE_STRATEGY_OPTIONS,
        default=DROP_ROW,
        allow_none=False,
        description="What strategy to follow when there's a missing value in a vector output feature",
        parameter_metadata=FEATURE_METADATA[VECTOR][PREPROCESSING]["missing_value_strategy"],
    )
