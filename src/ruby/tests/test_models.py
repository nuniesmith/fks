"""
Tests for the model library: imports, instantiation, registry, factory, and metadata.

Covers all 11 registered model classes, the ModelRegistry, and the ModelFactory.
Optional dependencies (torch, xgboost, prophet, hmmlearn, arch, statsmodels, sklearn)
are handled gracefully via pytest.importorskip / pytest.skip so the suite runs
in any environment.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

import pytest

# ---------------------------------------------------------------------------
# 1. Import tests — verify each model class can be imported
# ---------------------------------------------------------------------------


class TestModelImports:
    """Verify that every model class is importable from its canonical path."""

    def test_import_base_model(self):
        from lib.model.base.model import BaseModel

        assert BaseModel is not None

    def test_import_estimator(self):
        from lib.model.base.estimator import Estimator

        assert Estimator is not None

    def test_import_classifier(self):
        from lib.model.base.classifier import Classifier

        assert Classifier is not None

    def test_import_regressor(self):
        from lib.model.base.regressor import Regressor

        assert Regressor is not None

    def test_import_xgboost_regressor(self):
        from lib.model.ml.xgboost import XGBoostRegressor

        assert XGBoostRegressor is not None

    def test_import_xgboost_classifier(self):
        from lib.model.ml.xgboost import XGBoostClassifier

        assert XGBoostClassifier is not None

    def test_import_logistic_regression_model(self):
        from lib.model.ml.logistic import LogisticRegressionModel

        assert LogisticRegressionModel is not None

    def test_import_arima_model(self):
        from lib.model.statistical.arima import ARIMAModel

        assert ARIMAModel is not None

    def test_import_garch(self):
        from lib.model.statistical.garch import GARCH

        assert GARCH is not None

    def test_import_hmm_model(self):
        from lib.model.statistical.hmm import HMMModel

        assert HMMModel is not None

    def test_import_prophet_model(self):
        from lib.model.statistical.prophet import ProphetModel

        assert ProphetModel is not None

    def test_import_simple_nn(self):
        from lib.model.deep.nn import SimpleNN

        assert SimpleNN is not None

    def test_import_lstm_model(self):
        from lib.model.deep.lstm import LSTMModel

        assert LSTMModel is not None

    def test_import_tft_model(self):
        from lib.model.deep.tft import TFTModel

        assert TFTModel is not None

    def test_import_ensemble_model(self):
        from lib.model.ensemble.ensemble import EnsembleModel

        assert EnsembleModel is not None

    def test_import_model_registry(self):
        from lib.model.registry import model_registry

        assert model_registry is not None

    def test_import_model_factory(self):
        from lib.model.factory import ModelFactory

        assert ModelFactory is not None

    def test_import_register_model_decorator(self):
        from lib.model.registry import register_model

        assert callable(register_model)

    def test_import_model_metadata(self):
        from lib.model.utils.metadata import ModelMetadata

        assert ModelMetadata is not None


# ---------------------------------------------------------------------------
# Helpers for safely instantiating models that have optional dependencies
# ---------------------------------------------------------------------------


def _skip_if_missing(module_name: str, reason: str | None = None):
    """Call pytest.importorskip for the given module."""
    pytest.importorskip(module_name, reason=reason or f"{module_name} not installed")


def _make_xgboost_regressor():
    _skip_if_missing("xgboost")
    from lib.model.ml.xgboost import XGBoostRegressor

    return XGBoostRegressor()


def _make_xgboost_classifier():
    _skip_if_missing("xgboost")
    from lib.model.ml.xgboost import XGBoostClassifier

    return XGBoostClassifier()


def _make_logistic_regression():
    _skip_if_missing("sklearn", reason="scikit-learn required for LogisticRegressionModel")
    from lib.model.ml.logistic import LogisticRegressionModel

    return LogisticRegressionModel()


def _make_arima():
    _skip_if_missing("statsmodels")
    from lib.model.statistical.arima import ARIMAModel

    return ARIMAModel()


def _make_garch():
    _skip_if_missing("arch")
    from lib.model.statistical.garch import GARCH

    return GARCH()


def _make_hmm():
    _skip_if_missing("hmmlearn")
    from lib.model.statistical.hmm import HMMModel

    return HMMModel()


def _make_prophet():
    _skip_if_missing("prophet")
    from lib.model.statistical.prophet import ProphetModel

    return ProphetModel()


def _make_simple_nn():
    from lib.model.deep.nn import SimpleNN

    return SimpleNN(input_size=10)


def _make_lstm():
    _skip_if_missing("torch")
    from lib.model.deep.lstm import LSTMModel

    return LSTMModel()


def _make_tft():
    _skip_if_missing("torch")
    from lib.model.deep.tft import TFTModel

    return TFTModel()


def _make_ensemble():
    from lib.model.ensemble.ensemble import EnsembleMethod, EnsembleModel

    # EnsembleModel requires a non-empty models list unless method is NONE
    return EnsembleModel(models=[], ensemble_method=EnsembleMethod.NONE)


# Mapping of human-readable model name → factory callable for parametrize
_MODEL_FACTORIES: list[tuple[str, Callable]] = [
    ("XGBoostRegressor", _make_xgboost_regressor),
    ("XGBoostClassifier", _make_xgboost_classifier),
    ("LogisticRegressionModel", _make_logistic_regression),
    ("ARIMAModel", _make_arima),
    ("GARCH", _make_garch),
    ("HMMModel", _make_hmm),
    ("ProphetModel", _make_prophet),
    ("SimpleNN", _make_simple_nn),
    ("LSTMModel", _make_lstm),
    ("TFTModel", _make_tft),
    ("EnsembleModel", _make_ensemble),
]


# ---------------------------------------------------------------------------
# 2. Instantiation tests — each model that extends BaseModel can be created
# ---------------------------------------------------------------------------


class TestModelInstantiation:
    """Verify that every concrete model class can be instantiated
    (i.e. super().__init__() chain works without error)."""

    @pytest.mark.parametrize(
        "model_name,factory_fn",
        _MODEL_FACTORIES,
        ids=[name for name, _ in _MODEL_FACTORIES],
    )
    def test_instantiation(self, model_name: str, factory_fn):
        """Instantiate *model_name* and verify it is a BaseModel."""
        from lib.model.base.model import BaseModel

        model = factory_fn()
        assert model is not None, f"{model_name} constructor returned None"
        assert isinstance(model, BaseModel), f"{model_name} is not an instance of BaseModel"

    def test_xgboost_regressor_is_regressor(self):
        """XGBoostRegressor should be a Regressor."""
        _skip_if_missing("xgboost")
        from lib.model.base.regressor import Regressor

        model = _make_xgboost_regressor()
        assert isinstance(model, Regressor)

    def test_xgboost_classifier_is_classifier(self):
        """XGBoostClassifier should be a Classifier."""
        _skip_if_missing("xgboost")
        from lib.model.base.classifier import Classifier

        model = _make_xgboost_classifier()
        assert isinstance(model, Classifier)

    def test_arima_is_estimator(self):
        """ARIMAModel should be an Estimator."""
        _skip_if_missing("statsmodels")
        from lib.model.base.estimator import Estimator

        model = _make_arima()
        assert isinstance(model, Estimator)

    def test_garch_is_estimator(self):
        """GARCH should be an Estimator."""
        _skip_if_missing("arch")
        from lib.model.base.estimator import Estimator

        model = _make_garch()
        assert isinstance(model, Estimator)


# ---------------------------------------------------------------------------
# 3. Registry tests — model_registry lists all expected models
# ---------------------------------------------------------------------------


# All 11 class names, lowercased (register_class uses cls.__name__.lower())
EXPECTED_REGISTERED_NAMES = {
    "xgboostregressor",
    "xgboostclassifier",
    "logisticregressionmodel",
    "arimamodel",
    "garch",
    "hmmmodel",
    "prophetmodel",
    "simplenn",
    "lstmmodel",
    "tftmodel",
    "ensemblemodel",
}


class TestModelRegistry:
    """Tests for the global model_registry singleton."""

    def test_registry_is_not_empty(self):
        """The registry should have at least the 11 known models."""
        from lib.model.registry import model_registry

        registered = model_registry.list()
        assert len(registered) >= len(EXPECTED_REGISTERED_NAMES), (
            f"Expected at least {len(EXPECTED_REGISTERED_NAMES)} registered models, "
            f"found {len(registered)}: {registered}"
        )

    @pytest.mark.parametrize("class_name", sorted(EXPECTED_REGISTERED_NAMES))
    def test_expected_model_in_registry(self, class_name: str):
        """Each expected model class should be present in the registry."""
        from lib.model.registry import model_registry

        registered = [n.lower() for n in model_registry.list()]
        assert class_name in registered, f"{class_name!r} not found in registry. Registered: {registered}"

    @pytest.mark.parametrize("class_name", sorted(EXPECTED_REGISTERED_NAMES))
    def test_registry_get_returns_class(self, class_name: str):
        """model_registry.get(name) should return a class, not None."""
        from lib.model.registry import model_registry

        cls = model_registry.get(class_name)
        assert cls is not None, f"model_registry.get({class_name!r}) returned None"
        assert isinstance(cls, type), f"model_registry.get({class_name!r}) returned {type(cls)}, expected a class"

    def test_registry_get_unknown_returns_none(self):
        """Looking up a non-existent model should return None (not raise)."""
        from lib.model.registry import model_registry

        result = model_registry.get("this_model_does_not_exist_xyz")
        assert result is None

    def test_list_returns_list_of_strings(self):
        """model_registry.list() should return a list of strings."""
        from lib.model.registry import model_registry

        result = model_registry.list()
        assert isinstance(result, list)
        for item in result:
            assert isinstance(item, str)


# ---------------------------------------------------------------------------
# 4. Factory tests — ModelFactory can create models by name
# ---------------------------------------------------------------------------


class TestModelFactory:
    """Tests for ModelFactory.create() and ModelFactory.list_available()."""

    def test_list_available_returns_strings(self):
        """ModelFactory.list_available() should return a list of name strings."""
        from lib.model.factory import ModelFactory

        available = ModelFactory.list_available()
        assert isinstance(available, list)
        assert len(available) > 0
        for name in available:
            assert isinstance(name, str)

    def test_list_available_contains_expected_models(self):
        """All 11 expected models should appear in ModelFactory.list_available()."""
        from lib.model.factory import ModelFactory

        available = [n.lower() for n in ModelFactory.list_available()]
        for expected in EXPECTED_REGISTERED_NAMES:
            assert expected in available, f"{expected!r} not in ModelFactory.list_available()"

    def test_factory_create_xgboost_regressor(self):
        """Factory can create XGBoostRegressor by name."""
        _skip_if_missing("xgboost")
        from lib.model.base.model import BaseModel
        from lib.model.factory import ModelFactory

        model = ModelFactory.create("xgboostregressor")
        assert isinstance(model, BaseModel)

    def test_factory_create_xgboost_classifier(self):
        """Factory can create XGBoostClassifier by name."""
        _skip_if_missing("xgboost")
        from lib.model.base.model import BaseModel
        from lib.model.factory import ModelFactory

        model = ModelFactory.create("xgboostclassifier")
        assert isinstance(model, BaseModel)

    def test_factory_create_logistic_regression(self):
        """Factory can create LogisticRegressionModel by name."""
        _skip_if_missing("sklearn")
        from lib.model.base.model import BaseModel
        from lib.model.factory import ModelFactory

        model = ModelFactory.create("logisticregressionmodel")
        assert isinstance(model, BaseModel)

    def test_factory_create_arima(self):
        """Factory can create ARIMAModel by name."""
        _skip_if_missing("statsmodels")
        from lib.model.base.model import BaseModel
        from lib.model.factory import ModelFactory

        model = ModelFactory.create("arimamodel")
        assert isinstance(model, BaseModel)

    def test_factory_create_garch(self):
        """Factory can create GARCH by name."""
        _skip_if_missing("arch")
        from lib.model.base.model import BaseModel
        from lib.model.factory import ModelFactory

        model = ModelFactory.create("garch")
        assert isinstance(model, BaseModel)

    def test_factory_create_hmm(self):
        """Factory can create HMMModel by name."""
        _skip_if_missing("hmmlearn")
        from lib.model.base.model import BaseModel
        from lib.model.factory import ModelFactory

        model = ModelFactory.create("hmmmodel")
        assert isinstance(model, BaseModel)

    def test_factory_create_prophet(self):
        """Factory can create ProphetModel by name."""
        _skip_if_missing("prophet")
        from lib.model.base.model import BaseModel
        from lib.model.factory import ModelFactory

        model = ModelFactory.create("prophetmodel")
        assert isinstance(model, BaseModel)

    def test_factory_create_simple_nn(self):
        """Factory can create SimpleNN by name (requires input_size)."""
        from lib.model.base.model import BaseModel
        from lib.model.factory import ModelFactory

        model = ModelFactory.create("simplenn", input_size=10)
        assert isinstance(model, BaseModel)

    def test_factory_create_lstm(self):
        """Factory can create LSTMModel by name."""
        _skip_if_missing("torch")
        from lib.model.base.model import BaseModel
        from lib.model.factory import ModelFactory

        model = ModelFactory.create("lstmmodel")
        assert isinstance(model, BaseModel)

    def test_factory_create_tft(self):
        """Factory can create TFTModel by name."""
        _skip_if_missing("torch")
        from lib.model.base.model import BaseModel
        from lib.model.factory import ModelFactory

        model = ModelFactory.create("tftmodel")
        assert isinstance(model, BaseModel)

    def test_factory_create_ensemble(self):
        """Factory can create EnsembleModel by name."""
        from lib.model.base.model import BaseModel
        from lib.model.ensemble.ensemble import EnsembleMethod
        from lib.model.factory import ModelFactory

        model = ModelFactory.create(
            "ensemblemodel",
            models=[],
            ensemble_method=EnsembleMethod.NONE,
        )
        assert isinstance(model, BaseModel)

    def test_factory_create_unknown_raises(self):
        """Creating an unknown model should raise ValueError."""
        from lib.model.factory import ModelFactory

        with pytest.raises(ValueError, match="not found"):
            ModelFactory.create("nonexistent_model_xyz")

    def test_factory_create_with_params(self):
        """Factory.create forwards **params to the model constructor."""
        _skip_if_missing("statsmodels")
        from lib.model.factory import ModelFactory

        custom_params = {"order": (2, 1, 1)}
        model = ModelFactory.create("arimamodel", params=custom_params)
        assert model is not None
        # The ARIMA model stores the order from params
        assert model.order == (2, 1, 1)


# ---------------------------------------------------------------------------
# 5. Metadata tests — instantiated models carry proper metadata
# ---------------------------------------------------------------------------


class TestModelMetadata:
    """Verify that instantiated models have correct metadata attributes."""

    @pytest.mark.parametrize(
        "model_name,factory_fn",
        _MODEL_FACTORIES,
        ids=[name for name, _ in _MODEL_FACTORIES],
    )
    def test_model_has_metadata(self, model_name: str, factory_fn):
        """Each model should have a _metadata attribute after construction."""
        model = factory_fn()
        assert hasattr(model, "_metadata"), f"{model_name} missing _metadata attribute"

    @pytest.mark.parametrize(
        "model_name,factory_fn",
        _MODEL_FACTORIES,
        ids=[name for name, _ in _MODEL_FACTORIES],
    )
    def test_metadata_property(self, model_name: str, factory_fn):
        """The .metadata property should return the ModelMetadata instance."""
        from lib.model.utils.metadata import ModelMetadata

        model = factory_fn()
        metadata = model.metadata
        assert isinstance(metadata, ModelMetadata), (
            f"{model_name}.metadata returned {type(metadata)}, expected ModelMetadata"
        )

    @pytest.mark.parametrize(
        "model_name,factory_fn",
        _MODEL_FACTORIES,
        ids=[name for name, _ in _MODEL_FACTORIES],
    )
    def test_metadata_has_model_type(self, model_name: str, factory_fn):
        """metadata.model_type should be set to the class name."""
        model = factory_fn()
        assert model.metadata.model_type, f"{model_name}.metadata.model_type is empty"
        # model_type is set to self.__class__.__name__ in BaseModel.__init__
        assert isinstance(model.metadata.model_type, str)

    @pytest.mark.parametrize(
        "model_name,factory_fn",
        _MODEL_FACTORIES,
        ids=[name for name, _ in _MODEL_FACTORIES],
    )
    def test_metadata_has_created_at(self, model_name: str, factory_fn):
        """metadata.created_at should be a non-empty ISO timestamp string."""
        model = factory_fn()
        created = model.metadata.created_at
        assert created is not None and len(created) > 0, f"{model_name}.metadata.created_at is missing"

    @pytest.mark.parametrize(
        "model_name,factory_fn",
        _MODEL_FACTORIES,
        ids=[name for name, _ in _MODEL_FACTORIES],
    )
    def test_metadata_has_version(self, model_name: str, factory_fn):
        """metadata.version should default to '1.0.0'."""
        model = factory_fn()
        assert model.metadata.version == "1.0.0", (
            f"{model_name}.metadata.version = {model.metadata.version!r}, expected '1.0.0'"
        )

    @pytest.mark.parametrize(
        "model_name,factory_fn",
        _MODEL_FACTORIES,
        ids=[name for name, _ in _MODEL_FACTORIES],
    )
    def test_get_params_returns_dict(self, model_name: str, factory_fn):
        """model.get_params() should return a dict."""
        model = factory_fn()
        params = model.get_params()
        assert isinstance(params, dict), f"{model_name}.get_params() returned {type(params)}, expected dict"

    @pytest.mark.parametrize(
        "model_name,factory_fn",
        _MODEL_FACTORIES,
        ids=[name for name, _ in _MODEL_FACTORIES],
    )
    def test_set_params_returns_self(self, model_name: str, factory_fn):
        """model.set_params() should return the model instance for chaining."""
        model = factory_fn()
        result = model.set_params(test_key="test_value")
        assert result is model, f"{model_name}.set_params() did not return self"

    @pytest.mark.parametrize(
        "model_name,factory_fn",
        _MODEL_FACTORIES,
        ids=[name for name, _ in _MODEL_FACTORIES],
    )
    def test_set_params_updates_params(self, model_name: str, factory_fn):
        """set_params() should make the new key visible via get_params()."""
        model = factory_fn()
        model.set_params(custom_param=42)
        params = model.get_params()
        assert "custom_param" in params, f"{model_name}: 'custom_param' not found after set_params()"
        assert params["custom_param"] == 42

    @pytest.mark.parametrize(
        "model_name,factory_fn",
        _MODEL_FACTORIES,
        ids=[name for name, _ in _MODEL_FACTORIES],
    )
    def test_summary_returns_string(self, model_name: str, factory_fn):
        """model.summary() should return a non-empty string."""
        model = factory_fn()
        summary = model.summary()
        assert isinstance(summary, str), f"{model_name}.summary() returned {type(summary)}, expected str"
        assert len(summary) > 0, f"{model_name}.summary() returned empty string"

    @pytest.mark.parametrize(
        "model_name,factory_fn",
        _MODEL_FACTORIES,
        ids=[name for name, _ in _MODEL_FACTORIES],
    )
    def test_summary_contains_class_name(self, model_name: str, factory_fn):
        """summary() output should mention the model's class name."""
        model = factory_fn()
        summary = model.summary()
        # The class name might differ from model_name for EnsembleModel etc.
        actual_class = model.__class__.__name__
        assert actual_class in summary, f"{model_name}.summary() does not contain class name {actual_class!r}"

    @pytest.mark.parametrize(
        "model_name,factory_fn",
        _MODEL_FACTORIES,
        ids=[name for name, _ in _MODEL_FACTORIES],
    )
    def test_metadata_to_dict(self, model_name: str, factory_fn):
        """metadata.to_dict() should return a serializable dict."""
        model = factory_fn()
        meta_dict = model.metadata.to_dict()
        assert isinstance(meta_dict, dict)
        assert "model_type" in meta_dict
        assert "created_at" in meta_dict
        assert "version" in meta_dict

    @pytest.mark.parametrize(
        "model_name,factory_fn",
        _MODEL_FACTORIES,
        ids=[name for name, _ in _MODEL_FACTORIES],
    )
    def test_str_repr(self, model_name: str, factory_fn):
        """__str__ and __repr__ should return non-empty strings without error."""
        model = factory_fn()
        s = str(model)
        r = repr(model)
        assert isinstance(s, str) and len(s) > 0
        assert isinstance(r, str) and len(r) > 0


# ---------------------------------------------------------------------------
# 6. Metadata edge cases
# ---------------------------------------------------------------------------


class TestModelMetadataEdgeCases:
    """Edge-case tests for metadata assignment and round-tripping."""

    def test_metadata_setter_accepts_dict(self):
        """Setting model.metadata to a dict should convert it to ModelMetadata."""
        from lib.model.utils.metadata import ModelMetadata

        model = _make_simple_nn()
        model.metadata = {"model_type": "custom", "version": "2.0.0"}
        assert isinstance(model.metadata, ModelMetadata)
        assert model.metadata.model_type == "custom"
        assert model.metadata.version == "2.0.0"

    def test_metadata_setter_accepts_metadata_object(self):
        """Setting model.metadata to a ModelMetadata should store it directly."""
        from lib.model.utils.metadata import ModelMetadata

        model = _make_simple_nn()
        new_meta = ModelMetadata(model_type="replaced", description="test")
        model.metadata = new_meta
        assert model.metadata is new_meta
        assert model.metadata.description == "test"

    def test_metadata_metrics_initially_empty(self):
        """A fresh model's metadata.metrics should be an empty dict."""
        model = _make_simple_nn()
        assert model.metadata.metrics == {}

    def test_metadata_params_initially_empty_or_dict(self):
        """A fresh model's metadata.params should be a dict."""
        model = _make_simple_nn()
        assert isinstance(model.metadata.params, dict)
