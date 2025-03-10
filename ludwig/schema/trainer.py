from abc import ABC
from typing import Optional, Union

from marshmallow_dataclass import dataclass

from ludwig.constants import COMBINED, DEFAULT_BATCH_SIZE, LOSS, MAX_POSSIBLE_BATCH_SIZE, MODEL_ECD, MODEL_GBM, TRAINING
from ludwig.schema import utils as schema_utils
from ludwig.schema.metadata.trainer_metadata import TRAINER_METADATA
from ludwig.schema.optimizers import (
    BaseOptimizerConfig,
    GradientClippingConfig,
    GradientClippingDataclassField,
    OptimizerDataclassField,
)
from ludwig.utils.registry import Registry

trainer_schema_registry = Registry()


def register_trainer_schema(model_type: str):
    def wrap(trainer_config: BaseTrainerConfig):
        trainer_schema_registry[model_type] = trainer_config
        return trainer_config

    return wrap


@dataclass(repr=False, order=True)
class BaseTrainerConfig(schema_utils.BaseMarshmallowConfig, ABC):
    """Common trainer parameter values."""

    pass


@register_trainer_schema("ecd_ray_legacy")
@register_trainer_schema(MODEL_ECD)
@dataclass(order=True)
class ECDTrainerConfig(BaseTrainerConfig):
    """Dataclass that configures most of the hyperparameters used for ECD model training."""

    learning_rate: Union[float, str] = schema_utils.OneOfOptionsField(
        default=0.001,
        allow_none=False,
        description=(
            "Controls how much to change the model in response to the estimated error each time the model weights are "
            "updated. If 'auto', the optimal learning rate is estimated by choosing the learning rate that produces "
            "the smallest non-diverging gradient update."
        ),
        parameter_metadata=TRAINER_METADATA["learning_rate"],
        field_options=[
            schema_utils.NonNegativeFloat(default=0.001, allow_none=False),
            schema_utils.StringOptions(options=["auto"], default="auto", allow_none=False),
        ],
    )

    epochs: int = schema_utils.PositiveInteger(
        default=100,
        description="Number of epochs the algorithm is intended to be run over.",
        parameter_metadata=TRAINER_METADATA["epochs"],
    )

    checkpoints_per_epoch: int = schema_utils.NonNegativeInteger(
        default=0,
        description=(
            "Number of checkpoints per epoch. For example, 2 -> checkpoints are written every half of an epoch. Note "
            "that it is invalid to specify both non-zero `steps_per_checkpoint` and non-zero `checkpoints_per_epoch`."
        ),
        parameter_metadata=TRAINER_METADATA["checkpoints_per_epoch"],
    )

    train_steps: int = schema_utils.PositiveInteger(
        default=None,
        description=(
            "Maximum number of training steps the algorithm is intended to be run over. "
            + "If unset, then `epochs` is used to determine training length."
        ),
        parameter_metadata=TRAINER_METADATA["train_steps"],
    )

    steps_per_checkpoint: int = schema_utils.NonNegativeInteger(
        default=0,
        description=(
            "How often the model is checkpointed. Also dictates maximum evaluation frequency. If 0 the model is "
            "checkpointed after every epoch."
        ),
        parameter_metadata=TRAINER_METADATA["steps_per_checkpoint"],
    )

    early_stop: int = schema_utils.IntegerRange(
        default=5,
        min=-1,
        description=(
            "Number of consecutive rounds of evaluation without any improvement on the `validation_metric` that "
            "triggers training to stop. Can be set to -1, which disables early stopping entirely."
        ),
        parameter_metadata=TRAINER_METADATA["early_stop"],
    )

    batch_size: Union[int, str] = schema_utils.OneOfOptionsField(
        default=DEFAULT_BATCH_SIZE,
        allow_none=False,
        description=(
            "The number of training examples utilized in one training step of the model. If ’auto’, the "
            "biggest batch size (power of 2) that can fit in memory will be used."
        ),
        parameter_metadata=TRAINER_METADATA["batch_size"],
        field_options=[
            schema_utils.PositiveInteger(default=DEFAULT_BATCH_SIZE, description="", allow_none=False),
            schema_utils.StringOptions(options=["auto"], default="auto", allow_none=False),
        ],
    )

    max_batch_size: int = schema_utils.PositiveInteger(
        default=MAX_POSSIBLE_BATCH_SIZE,
        allow_none=True,
        description=(
            "Auto batch size tuning and increasing batch size on plateau will be capped at this value. The default "
            "value is 2^40."
        ),
        parameter_metadata=TRAINER_METADATA["max_batch_size"],
    )

    eval_batch_size: Union[None, int, str] = schema_utils.OneOfOptionsField(
        default=None,
        description=(
            "Size of batch to pass to the model for evaluation. If it is `0` or `None`, the same value of `batch_size` "
            "is used. This is useful to speedup evaluation with a much bigger batch size than training, if enough "
            "memory is available. If ’auto’, the biggest batch size (power of 2) that can fit in memory will be used."
        ),
        parameter_metadata=TRAINER_METADATA["eval_batch_size"],
        field_options=[
            schema_utils.PositiveInteger(default=128, description="", allow_none=False),
            schema_utils.StringOptions(options=["auto"], default="auto", allow_none=False),
        ],
    )

    evaluate_training_set: bool = schema_utils.Boolean(
        default=True,
        description="Whether to include the entire training set during evaluation.",
        parameter_metadata=TRAINER_METADATA["evaluate_training_set"],
    )

    # TODO(#1673): Need some more logic here for validating against output features
    validation_field: str = schema_utils.String(
        default=COMBINED,
        description="First output feature, by default it is set as the same field of the first output feature.",
        parameter_metadata=TRAINER_METADATA["validation_field"],
    )

    validation_metric: str = schema_utils.String(
        default=LOSS,
        description=(
            "Metric used on `validation_field`, set by default to the "
            "output feature type's `default_validation_metric`."
        ),
        parameter_metadata=TRAINER_METADATA["validation_metric"],
    )

    optimizer: BaseOptimizerConfig = OptimizerDataclassField(
        default={"type": "adam"}, description="Parameter values for selected torch optimizer."
    )

    regularization_type: Optional[str] = schema_utils.RegularizerOptions(
        default="l2", description="Type of regularization."
    )

    regularization_lambda: float = schema_utils.FloatRange(
        default=0.0,
        min=0,
        description="Strength of the $L2$ regularization.",
        parameter_metadata=TRAINER_METADATA["regularization_lambda"],
    )

    should_shuffle: bool = schema_utils.Boolean(
        default=True,
        description="Whether to shuffle batches during training when true.",
        parameter_metadata=TRAINER_METADATA["should_shuffle"],
    )

    reduce_learning_rate_on_plateau: int = schema_utils.NonNegativeInteger(
        default=0,
        description=(
            "How many times to reduce the learning rate when the algorithm hits a plateau (i.e. the performance on the"
            "training set does not improve"
        ),
        parameter_metadata=TRAINER_METADATA["reduce_learning_rate_on_plateau"],
    )

    reduce_learning_rate_on_plateau_patience: int = schema_utils.NonNegativeInteger(
        default=5,
        description="How many epochs have to pass before the learning rate reduces.",
        parameter_metadata=TRAINER_METADATA["reduce_learning_rate_on_plateau_patience"],
    )

    reduce_learning_rate_on_plateau_rate: float = schema_utils.FloatRange(
        default=0.5,
        min=0,
        max=1,
        description="Rate at which we reduce the learning rate.",
        parameter_metadata=TRAINER_METADATA["reduce_learning_rate_on_plateau_rate"],
    )

    reduce_learning_rate_eval_metric: str = schema_utils.String(
        default=LOSS,
        description="Rate at which we reduce the learning rate.",
        parameter_metadata=TRAINER_METADATA["reduce_learning_rate_eval_metric"],
    )

    reduce_learning_rate_eval_split: str = schema_utils.String(
        default=TRAINING,
        description="Which dataset split to listen on for reducing the learning rate.",
        parameter_metadata=TRAINER_METADATA["reduce_learning_rate_eval_split"],
    )

    increase_batch_size_on_plateau: int = schema_utils.NonNegativeInteger(
        default=0,
        description="The number of times to increase the batch size on a plateau.",
        parameter_metadata=TRAINER_METADATA["increase_batch_size_on_plateau"],
    )

    increase_batch_size_on_plateau_patience: int = schema_utils.NonNegativeInteger(
        default=5,
        description="How many epochs to wait for before increasing the batch size.",
        parameter_metadata=TRAINER_METADATA["increase_batch_size_on_plateau_patience"],
    )

    increase_batch_size_on_plateau_rate: float = schema_utils.NonNegativeFloat(
        default=2.0,
        description="Rate at which the batch size increases.",
        parameter_metadata=TRAINER_METADATA["increase_batch_size_on_plateau_rate"],
    )

    increase_batch_size_eval_metric: str = schema_utils.String(
        default=LOSS,
        description="Which metric to listen on for increasing the batch size.",
        parameter_metadata=TRAINER_METADATA["increase_batch_size_eval_metric"],
    )

    increase_batch_size_eval_split: str = schema_utils.String(
        default=TRAINING,
        description="Which dataset split to listen on for increasing the batch size.",
        parameter_metadata=TRAINER_METADATA["increase_batch_size_eval_split"],
    )

    decay: bool = schema_utils.Boolean(
        default=False,
        description="Turn on exponential decay of the learning rate.",
        parameter_metadata=TRAINER_METADATA["decay"],
    )

    decay_steps: int = schema_utils.PositiveInteger(
        default=10000,
        description="The number of steps to take in the exponential learning rate decay.",
        parameter_metadata=TRAINER_METADATA["decay_steps"],
    )

    decay_rate: float = schema_utils.FloatRange(
        default=0.96,
        min=0,
        max=1,
        description="Decay per epoch (%): Factor to decrease the Learning rate.",
        parameter_metadata=TRAINER_METADATA["decay_steps"],
    )

    staircase: bool = schema_utils.Boolean(
        default=False,
        description="Decays the learning rate at discrete intervals.",
        parameter_metadata=TRAINER_METADATA["staircase"],
    )

    gradient_clipping: Optional[GradientClippingConfig] = GradientClippingDataclassField(
        description="Parameter values for gradient clipping.",
        default={},
    )

    learning_rate_warmup_epochs: float = schema_utils.NonNegativeFloat(
        default=1.0,
        description="Number of epochs to warmup the learning rate for.",
        parameter_metadata=TRAINER_METADATA["learning_rate_warmup_epochs"],
    )

    learning_rate_scaling: str = schema_utils.StringOptions(
        ["constant", "sqrt", "linear"],
        default="linear",
        description="Scale by which to increase the learning rate as the number of distributed workers increases. "
        "Traditionally the learning rate is scaled linearly with the number of workers to reflect the "
        "proportion by"
        " which the effective batch size is increased. For very large batch sizes, a softer square-root "
        "scale can "
        "sometimes lead to better model performance. If the learning rate is hand-tuned for a given "
        "number of "
        "workers, setting this value to constant can be used to disable scale-up.",
        parameter_metadata=TRAINER_METADATA["learning_rate_scaling"],
    )

    bucketing_field: str = schema_utils.String(
        default=None,
        description="When not null, when creating batches, instead of shuffling randomly, the length along the last "
        "dimension of the matrix of the specified input feature is used for bucketing examples and then "
        "randomly shuffled examples from the same bin are sampled. Padding is trimmed to the longest "
        "example in the batch. The specified feature should be either a sequence or text feature and the "
        "encoder encoding it has to be rnn. When used, bucketing improves speed of rnn encoding up to "
        "1.5x, depending on the length distribution of the inputs.",
        parameter_metadata=TRAINER_METADATA["bucketing_field"],
    )


@register_trainer_schema(MODEL_GBM)
@dataclass(repr=False, order=True)
class GBMTrainerConfig(BaseTrainerConfig):
    """Dataclass that configures most of the hyperparameters used for GBM model training."""

    # NOTE: Overwritten here since GBM performs better with a different default learning rate.
    learning_rate: Union[float, str] = schema_utils.NonNegativeFloat(
        default=0.03,
        allow_none=False,
        description=(
            "Controls how much to change the model in response to the estimated error each time the model weights are "
            "updated."
        ),
        parameter_metadata=TRAINER_METADATA["learning_rate"],
    )

    early_stop: int = schema_utils.IntegerRange(
        default=5,
        min=-1,
        description=(
            "Number of consecutive rounds of evaluation without any improvement on the `validation_metric` that "
            "triggers training to stop. Can be set to -1, which disables early stopping entirely."
        ),
        parameter_metadata=TRAINER_METADATA["early_stop"],
    )

    # LightGBM Learning Control params
    max_depth: int = schema_utils.Integer(
        default=18,
        description="Maximum depth of a tree in the GBM trainer. A negative value means no limit.",
    )

    drop_rate: float = schema_utils.FloatRange(
        default=0.1,
        min=0,
        max=1,
        description="Dropout rate for the GBM trainer. Used only with boosting_type 'dart'.",
    )

    # NOTE: Overwritten here to provide a default value. In many places, we fall back to eval_batch_size if batch_size
    # is not specified. GBM does not have a value for batch_size, so we need to specify eval_batch_size here.
    eval_batch_size: Union[None, int, str] = schema_utils.PositiveInteger(
        default=1024,
        description="Size of batch to pass to the model for evaluation.",
        parameter_metadata=TRAINER_METADATA["eval_batch_size"],
    )

    evaluate_training_set: bool = schema_utils.Boolean(
        default=True,
        description="Whether to include the entire training set during evaluation.",
        parameter_metadata=TRAINER_METADATA["evaluate_training_set"],
    )

    # TODO(#1673): Need some more logic here for validating against output features
    validation_field: str = schema_utils.String(
        default=COMBINED,
        description="First output feature, by default it is set as the same field of the first output feature.",
        parameter_metadata=TRAINER_METADATA["validation_field"],
    )

    validation_metric: str = schema_utils.String(
        default=LOSS,
        description=(
            "Metric used on `validation_field`, set by default to the "
            "output feature type's `default_validation_metric`."
        ),
        parameter_metadata=TRAINER_METADATA["validation_metric"],
    )

    tree_learner: str = schema_utils.StringOptions(
        ["serial", "feature", "data", "voting"],
        default="serial",
        description="Type of tree learner to use with GBM trainer.",
    )

    # LightGBM core parameters (https://lightgbm.readthedocs.io/en/latest/Parameters.html)
    boosting_type: str = schema_utils.StringOptions(
        ["gbdt", "rf", "dart", "goss"],
        default="gbdt",
        description="Type of boosting algorithm to use with GBM trainer.",
    )

    boosting_rounds_per_checkpoint: int = schema_utils.PositiveInteger(
        default=50, description="Number of boosting rounds per checkpoint / evaluation round."
    )

    num_boost_round: int = schema_utils.PositiveInteger(
        default=1000, description="Number of boosting rounds to perform with GBM trainer."
    )

    num_leaves: int = schema_utils.PositiveInteger(
        default=82, description="Number of leaves to use in the tree with GBM trainer."
    )

    min_data_in_leaf: int = schema_utils.PositiveInteger(
        default=315, description="Minimum number of data points in a leaf with GBM trainer."
    )

    min_sum_hessian_in_leaf: float = schema_utils.NonNegativeFloat(
        default=1e-3, description="Minimum sum of hessians in a leaf with GBM trainer."
    )

    bagging_fraction: float = schema_utils.FloatRange(
        default=0.8, min=0, max=1, description="Fraction of data to use for bagging with GBM trainer."
    )

    pos_bagging_fraction: float = schema_utils.FloatRange(
        default=1.0, min=0, max=1, description="Fraction of positive data to use for bagging with GBM trainer."
    )

    neg_bagging_fraction: float = schema_utils.FloatRange(
        default=1.0, min=0, max=1, description="Fraction of negative data to use for bagging with GBM trainer."
    )

    bagging_freq: int = schema_utils.NonNegativeInteger(default=1, description="Frequency of bagging with GBM trainer.")

    bagging_seed: int = schema_utils.Integer(default=3, description="Random seed for bagging with GBM trainer.")

    feature_fraction: float = schema_utils.FloatRange(
        default=0.75, min=0, max=1, description="Fraction of features to use in the GBM trainer."
    )

    feature_fraction_bynode: float = schema_utils.FloatRange(
        default=1.0, min=0, max=1, description="Fraction of features to use for each tree node with GBM trainer."
    )

    feature_fraction_seed: int = schema_utils.Integer(
        default=2, description="Random seed for feature fraction with GBM trainer."
    )

    extra_trees: bool = schema_utils.Boolean(
        default=False, description="Whether to use extremely randomized trees in the GBM trainer."
    )

    extra_seed: int = schema_utils.Integer(
        default=6, description="Random seed for extremely randomized trees in the GBM trainer."
    )

    max_delta_step: float = schema_utils.FloatRange(
        default=0.0,
        min=0,
        max=1,
        description=(
            "Used to limit the max output of tree leaves in the GBM trainer. A negative value means no constraint."
        ),
    )

    lambda_l1: float = schema_utils.NonNegativeFloat(
        default=0.25, description="L1 regularization factor for the GBM trainer."
    )

    lambda_l2: float = schema_utils.NonNegativeFloat(
        default=0.2, description="L2 regularization factor for the GBM trainer."
    )

    linear_lambda: float = schema_utils.NonNegativeFloat(
        default=0.0, description="Linear tree regularization in the GBM trainer."
    )

    min_gain_to_split: float = schema_utils.NonNegativeFloat(
        default=0.03, description="Minimum gain to split a leaf in the GBM trainer."
    )

    max_drop: int = schema_utils.Integer(
        default=50,
        description=(
            "Maximum number of dropped trees during one boosting iteration. "
            "Used only with boosting_type 'dart'. A negative value means no limit."
        ),
    )

    skip_drop: float = schema_utils.FloatRange(
        default=0.5,
        min=0,
        max=1,
        description=(
            "Probability of skipping the dropout during one boosting iteration. Used only with boosting_type 'dart'."
        ),
    )

    xgboost_dart_mode: bool = schema_utils.Boolean(
        default=False,
        description="Whether to use xgboost dart mode in the GBM trainer. Used only with boosting_type 'dart'.",
    )

    uniform_drop: bool = schema_utils.Boolean(
        default=False,
        description="Whether to use uniform dropout in the GBM trainer. Used only with boosting_type 'dart'.",
    )

    drop_seed: int = schema_utils.Integer(
        default=4,
        description="Random seed to choose dropping models in the GBM trainer. Used only with boosting_type 'dart'.",
    )

    top_rate: float = schema_utils.FloatRange(
        default=0.2,
        min=0,
        max=1,
        description="The retain ratio of large gradient data in the GBM trainer. Used only with boosting_type 'goss'.",
    )

    other_rate: float = schema_utils.FloatRange(
        default=0.1,
        min=0,
        max=1,
        description="The retain ratio of small gradient data in the GBM trainer. Used only with boosting_type 'goss'.",
    )

    min_data_per_group: int = schema_utils.PositiveInteger(
        default=100,
        description="Minimum number of data points per categorical group for the GBM trainer.",
    )

    max_cat_threshold: int = schema_utils.PositiveInteger(
        default=32,
        description="Number of split points considered for categorical features for the GBM trainer.",
    )

    cat_l2: float = schema_utils.NonNegativeFloat(
        default=10.0, description="L2 regularization factor for categorical split in the GBM trainer."
    )

    cat_smooth: float = schema_utils.NonNegativeFloat(
        default=10.0, description="Smoothing factor for categorical split in the GBM trainer."
    )

    max_cat_to_onehot: int = schema_utils.PositiveInteger(
        default=4,
        description="Maximum categorical cardinality required before one-hot encoding in the GBM trainer.",
    )

    cegb_tradeoff: float = schema_utils.NonNegativeFloat(
        default=1.0,
        description="Cost-effective gradient boosting multiplier for all penalties in the GBM trainer.",
    )

    cegb_penalty_split: float = schema_utils.NonNegativeFloat(
        default=0.0,
        description="Cost-effective gradient boosting penalty for splitting a node in the GBM trainer.",
    )

    path_smooth: float = schema_utils.NonNegativeFloat(
        default=0.0,
        description="Smoothing factor applied to tree nodes in the GBM trainer.",
    )

    verbose: int = schema_utils.IntegerRange(default=-1, min=-1, max=2, description="Verbosity level for GBM trainer.")

    # LightGBM IO params
    max_bin: int = schema_utils.PositiveInteger(
        default=255, description="Maximum number of bins to use for discretizing features with GBM trainer."
    )


def get_model_type_jsonschema():
    return {
        "type": "string",
        "enum": [MODEL_ECD, MODEL_GBM, "ecd_ray_legacy"],
        "default": MODEL_ECD,
        "title": "model_type",
        "description": "Select the model type.",
    }


def get_trainer_jsonschema(model_type: str):
    trainer_cls = trainer_schema_registry[model_type]
    props = schema_utils.unload_jsonschema_from_marshmallow_class(trainer_cls)["properties"]

    return {
        "type": "object",
        "properties": props,
        "title": "trainer_options",
        "additionalProperties": False,
        "description": "Schema for trainer determined by Model Type",
    }
