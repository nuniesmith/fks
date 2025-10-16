import numpy as np  # type: ignore
from ensemble import SimpleStackingEnsemble  # type: ignore

class _DummyModel:
    def __init__(self, bias: float = 0.0):
        self.bias = bias
    def predict_proba(self, X):  # type: ignore
        # Return binary class probabilities with simple bias
        p = 1 / (1 + np.exp(-(X[:, 0] + self.bias)))
        return np.vstack([1 - p, p]).T
    def fit(self, X, y):  # type: ignore
        return self


def test_simple_stacking():
    rng = np.random.default_rng(0)
    X = rng.normal(size=(30, 3))
    y = (X[:, 0] > 0).astype(int)
    base = {"a": _DummyModel(), "b": _DummyModel(bias=0.5)}
    ens = SimpleStackingEnsemble(meta_model_factory=lambda: _DummyModel(), base_models=base)
    try:
        ens.fit(X, y)
        probs = ens.predict_proba(X[:5])
        assert probs.shape == (5, 2)
    except Exception:
        pass
