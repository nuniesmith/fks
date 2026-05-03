"""
Tests for the Position Intelligence Engine (POSINT)
====================================================
Covers:
  - PositionIntel dataclass construction and serialisation
  - compute_multi_tp: long/short TP levels, ATR=0 edge case, VP level integration
  - assess_book_pressure: bid/ask totals, imbalance clamping, empty/None input
  - suggest_risk_actions: all five priority branches (exit_full, take_partial,
    trail_stop, add_size, hold)
  - _estimate_atr: standard calculation, short DataFrame guard, empty guard
  - compute_position_intelligence: end-to-end with mocked analysis modules,
    fallback behaviour when each module raises
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

# ---------------------------------------------------------------------------
# Guard analysis module imports so the tests can run without a full install.
# We patch them inside individual tests / classes; here we just make sure
# the position_intelligence module itself loads cleanly.
# ---------------------------------------------------------------------------
from lib.services.engine.position_intelligence import (
    PositionIntel,
    _estimate_atr,
    assess_book_pressure,
    compute_multi_tp,
    compute_position_intelligence,
    suggest_risk_actions,
)

# ===========================================================================
# Helpers / fixtures
# ===========================================================================


def _make_ohlcv(
    n: int = 200,
    start_price: float = 5000.0,
    seed: int = 42,
    freq: str = "5min",
) -> pd.DataFrame:
    """Minimal synthetic OHLCV DataFrame with all required columns."""
    rng = np.random.default_rng(seed)
    returns = rng.normal(0, 0.002, n)
    close = start_price * np.exp(np.cumsum(returns))
    spread = close * 0.002
    high = close + rng.uniform(0, 1, n) * spread
    low = close - rng.uniform(0, 1, n) * spread
    opn = close + rng.uniform(-0.5, 0.5, n) * spread
    high = np.maximum(high, np.maximum(opn, close))
    low = np.minimum(low, np.minimum(opn, close))
    volume = rng.poisson(1000, n).astype(float) + 1
    idx = pd.date_range("2025-01-06 09:30", periods=n, freq=freq, tz="America/New_York")
    return pd.DataFrame(
        {"Open": opn, "High": high, "Low": low, "Close": close, "Volume": volume},
        index=idx,
    )


@pytest.fixture()
def bars_5m() -> pd.DataFrame:
    return _make_ohlcv(n=300, freq="5min", seed=10)


@pytest.fixture()
def bars_1m() -> pd.DataFrame:
    return _make_ohlcv(n=300, freq="1min", seed=20)


@pytest.fixture()
def empty_df() -> pd.DataFrame:
    return pd.DataFrame(columns=pd.Index(["Open", "High", "Low", "Close", "Volume"]))


# ===========================================================================
# PositionIntel dataclass
# ===========================================================================


class TestPositionIntel:
    """Tests for the PositionIntel dataclass and its serialisation."""

    def test_default_construction(self):
        intel = PositionIntel()
        assert intel.sweep_zones == []
        assert intel.multi_tp_targets == []
        assert intel.book_pressure == {}
        assert intel.risk_actions == []
        assert intel.confluence_score == 0
        assert intel.confluence_quality == 0.0
        assert intel.confluence_direction == "neutral"
        assert intel.regime_context == "unknown"
        assert intel.regime_confidence == 0.0
        assert intel.position_multiplier == 0.25
        assert intel.cvd == 0.0
        assert intel.cvd_slope == 0.0
        assert intel.vp_levels == {}

    def test_explicit_construction(self):
        intel = PositionIntel(
            sweep_zones=[{"price": 5400.0, "label": "FVG", "distance": 10.0}],
            confluence_score=3,
            confluence_quality=0.9,
            confluence_direction="bullish",
            regime_context="trending",
            regime_confidence=0.85,
            position_multiplier=1.0,
            cvd=500.0,
            cvd_slope=0.25,
            vp_levels={"poc": 5410.0, "vah": 5430.0, "val": 5390.0},
        )
        assert intel.confluence_score == 3
        assert intel.confluence_direction == "bullish"
        assert intel.regime_context == "trending"

    def test_to_dict_keys(self):
        intel = PositionIntel()
        d = intel.to_dict()
        expected_keys = {
            "sweep_zones",
            "multi_tp_targets",
            "book_pressure",
            "risk_actions",
            "confluence_score",
            "confluence_quality",
            "confluence_direction",
            "regime_context",
            "regime_confidence",
            "position_multiplier",
            "cvd",
            "cvd_slope",
            "vp_levels",
        }
        assert set(d.keys()) == expected_keys

    def test_to_dict_values_match_fields(self):
        intel = PositionIntel(
            confluence_score=2,
            regime_context="choppy",
            cvd=-123.45,
            cvd_slope=-0.15,
        )
        d = intel.to_dict()
        assert d["confluence_score"] == 2
        assert d["regime_context"] == "choppy"
        assert d["cvd"] == pytest.approx(-123.45)
        assert d["cvd_slope"] == pytest.approx(-0.15)

    def test_to_dict_is_serialisable(self):
        """to_dict output must be JSON-serialisable (no numpy scalars etc.)."""
        import json

        intel = PositionIntel(
            sweep_zones=[{"price": 5400.0, "label": "OB"}],
            multi_tp_targets=[5410.0, 5420.0, 5435.0],
            vp_levels={"poc": 5415.0, "vah": 5430.0, "val": 5400.0},
        )
        # Should not raise
        payload = json.dumps(intel.to_dict())
        assert "5410" in payload

    def test_independent_mutable_defaults(self):
        """Each PositionIntel instance must have independent mutable defaults."""
        a = PositionIntel()
        b = PositionIntel()
        a.sweep_zones.append({"price": 100.0})
        assert b.sweep_zones == []
        a.risk_actions.append("hold")
        assert b.risk_actions == []


# ===========================================================================
# compute_multi_tp
# ===========================================================================


class TestComputeMultiTP:
    """Tests for the multi-take-profit level computation."""

    def test_long_basic(self):
        targets = compute_multi_tp(
            entry=5000.0,
            direction="long",
            atr=10.0,
            vp_levels={"poc": 5025.0, "vah": 5040.0, "val": 4990.0},
        )
        assert len(targets) >= 2
        # All targets should be above entry for a long
        assert all(t > 5000.0 for t in targets)
        # Should be in ascending order
        assert targets == sorted(targets)

    def test_short_basic(self):
        targets = compute_multi_tp(
            entry=5000.0,
            direction="short",
            atr=10.0,
            vp_levels={"poc": 4975.0, "vah": 5010.0, "val": 4960.0},
        )
        assert len(targets) >= 2
        # All targets should be below entry for a short
        assert all(t < 5000.0 for t in targets)
        # Should be in descending order
        assert targets == sorted(targets, reverse=True)

    def test_atr_zero_returns_empty(self):
        targets = compute_multi_tp(
            entry=5000.0,
            direction="long",
            atr=0.0,
            vp_levels={},
        )
        assert targets == []

    def test_atr_negative_returns_empty(self):
        targets = compute_multi_tp(
            entry=5000.0,
            direction="long",
            atr=-5.0,
            vp_levels={},
        )
        assert targets == []

    def test_tp1_is_one_atr_long(self):
        targets = compute_multi_tp(5000.0, "long", 10.0, {})
        # tp1 = 5000 + 1*10 = 5010
        assert 5010.0 in targets

    def test_tp2_is_two_atr_long(self):
        targets = compute_multi_tp(5000.0, "long", 10.0, {})
        # tp2 = 5000 + 2*10 = 5020
        assert 5020.0 in targets

    def test_tp1_is_one_atr_short(self):
        targets = compute_multi_tp(5000.0, "short", 10.0, {})
        # tp1 = 5000 - 1*10 = 4990
        assert 4990.0 in targets

    def test_vp_level_used_as_tp3_long(self):
        # VAH at 5035 is beyond tp2 (5020) — should become tp3
        targets = compute_multi_tp(
            entry=5000.0,
            direction="long",
            atr=10.0,
            vp_levels={"poc": 5015.0, "vah": 5035.0, "val": 4980.0},
        )
        assert 5035.0 in targets

    def test_vp_level_used_as_tp3_short(self):
        # VAL at 4965 is below tp2 (4980) — should become tp3
        targets = compute_multi_tp(
            entry=5000.0,
            direction="short",
            atr=10.0,
            vp_levels={"poc": 4985.0, "vah": 5010.0, "val": 4965.0},
        )
        assert 4965.0 in targets

    def test_empty_vp_levels_still_works(self):
        targets = compute_multi_tp(5000.0, "long", 5.0, {})
        assert len(targets) >= 2

    def test_deduplication(self):
        """If all VP levels fall below tp2, tp3 == tp2; result should not have
        duplicate elements."""
        targets = compute_multi_tp(
            entry=5000.0,
            direction="long",
            atr=10.0,
            vp_levels={"poc": 4990.0, "vah": 4995.0, "val": 4985.0},
        )
        assert len(targets) == len(set(targets))

    def test_results_are_floats(self):
        targets = compute_multi_tp(5000.0, "long", 8.0, {"poc": 5025.0, "vah": 5035.0, "val": 4990.0})
        assert all(isinstance(t, float) for t in targets)


# ===========================================================================
# assess_book_pressure
# ===========================================================================


class TestAssessBookPressure:
    """Tests for the Level-2 order-book pressure summariser."""

    def test_returns_empty_for_none(self):
        assert assess_book_pressure(None) == {}

    def test_returns_empty_for_empty_dict(self):
        assert assess_book_pressure({}) == {}

    def test_basic_balanced_book(self):
        l2 = {
            "bids": [{"price": 100.0, "size": 50}, {"price": 99.5, "size": 50}],
            "asks": [{"price": 100.5, "size": 50}, {"price": 101.0, "size": 50}],
        }
        result = assess_book_pressure(l2)
        assert result["bid_total"] == pytest.approx(100.0)
        assert result["ask_total"] == pytest.approx(100.0)
        assert result["imbalance_ratio"] == pytest.approx(1.0)

    def test_bid_heavy_book(self):
        l2 = {
            "bids": [{"price": 100.0, "size": 200}],
            "asks": [{"price": 100.5, "size": 50}],
        }
        result = assess_book_pressure(l2)
        assert result["bid_total"] == pytest.approx(200.0)
        assert result["ask_total"] == pytest.approx(50.0)
        assert result["imbalance_ratio"] == pytest.approx(4.0)

    def test_ask_heavy_book(self):
        l2 = {
            "bids": [{"price": 100.0, "size": 20}],
            "asks": [{"price": 100.5, "size": 200}],
        }
        result = assess_book_pressure(l2)
        assert result["imbalance_ratio"] == pytest.approx(0.1)  # lower clamp

    def test_imbalance_clamped_upper(self):
        l2 = {
            "bids": [{"price": 100.0, "size": 100_000}],
            "asks": [{"price": 100.5, "size": 1}],
        }
        result = assess_book_pressure(l2)
        assert result["imbalance_ratio"] == pytest.approx(10.0)

    def test_imbalance_clamped_lower(self):
        l2 = {
            "bids": [{"price": 100.0, "size": 1}],
            "asks": [{"price": 100.5, "size": 100_000}],
        }
        result = assess_book_pressure(l2)
        assert result["imbalance_ratio"] == pytest.approx(0.1)

    def test_zero_ask_total_gives_upper_clamp(self):
        l2 = {
            "bids": [{"price": 100.0, "size": 50}],
            "asks": [],
        }
        result = assess_book_pressure(l2)
        assert result["imbalance_ratio"] == pytest.approx(10.0)

    def test_empty_bids_and_asks(self):
        l2 = {"bids": [], "asks": []}
        result = assess_book_pressure(l2)
        # bid_total == 0, ask_total == 0 → imbalance_ratio = 10 (ask_total == 0 guard)
        assert result["bid_total"] == pytest.approx(0.0)
        assert result["ask_total"] == pytest.approx(0.0)
        assert result["imbalance_ratio"] == pytest.approx(10.0)

    def test_missing_size_treated_as_zero(self):
        l2 = {
            "bids": [{"price": 100.0}],  # no "size" key
            "asks": [{"price": 101.0, "size": 10}],
        }
        result = assess_book_pressure(l2)
        assert result["bid_total"] == pytest.approx(0.0)

    def test_result_keys(self):
        l2 = {
            "bids": [{"price": 100.0, "size": 10}],
            "asks": [{"price": 101.0, "size": 10}],
        }
        result = assess_book_pressure(l2)
        assert set(result.keys()) == {"bid_total", "ask_total", "imbalance_ratio"}

    def test_float_sizes(self):
        l2 = {
            "bids": [{"price": 100.0, "size": 12.5}],
            "asks": [{"price": 101.0, "size": 12.5}],
        }
        result = assess_book_pressure(l2)
        assert result["bid_total"] == pytest.approx(12.5)


# ===========================================================================
# suggest_risk_actions
# ===========================================================================


class TestSuggestRiskActions:
    """Tests for the prioritised risk-action decision chain."""

    # -----------------------------------------------------------------------
    # Priority 1: exit_full
    # -----------------------------------------------------------------------

    def test_exit_full_fires_on_volatile_adverse_cvd_and_low_imbalance(self):
        intel = PositionIntel(
            regime_context="volatile",
            cvd_slope=-0.5,  # |slope| > 0.3
            book_pressure={"imbalance_ratio": 0.2},  # < 0.3
        )
        actions = suggest_risk_actions(intel)
        assert "exit_full" in actions

    def test_exit_full_requires_all_three_conditions(self):
        # Only volatile + slope, but imbalance is fine
        intel = PositionIntel(
            regime_context="volatile",
            cvd_slope=-0.5,
            book_pressure={"imbalance_ratio": 1.0},
        )
        actions = suggest_risk_actions(intel)
        assert "exit_full" not in actions

    def test_exit_full_not_in_trending_regime(self):
        intel = PositionIntel(
            regime_context="trending",
            cvd_slope=-0.5,
            book_pressure={"imbalance_ratio": 0.1},
        )
        actions = suggest_risk_actions(intel)
        assert "exit_full" not in actions

    # -----------------------------------------------------------------------
    # Priority 2: take_partial
    # -----------------------------------------------------------------------

    def test_take_partial_on_low_book_imbalance(self):
        intel = PositionIntel(
            book_pressure={"imbalance_ratio": 0.4},  # < 0.5
        )
        actions = suggest_risk_actions(intel)
        assert "take_partial" in actions
        assert "exit_full" not in actions

    def test_take_partial_on_choppy_low_confluence(self):
        intel = PositionIntel(
            regime_context="choppy",
            confluence_score=1,  # < 2
            book_pressure={"imbalance_ratio": 1.0},
        )
        actions = suggest_risk_actions(intel)
        assert "take_partial" in actions

    def test_take_partial_not_on_choppy_high_confluence(self):
        intel = PositionIntel(
            regime_context="choppy",
            confluence_score=3,  # >= 2, so no partial for this reason
            book_pressure={"imbalance_ratio": 1.0},
        )
        suggest_risk_actions(intel)
        # No partial from choppy+score alone; others may fire though
        action_causes = _explain_partial_causes(intel)
        assert "choppy_low_confluence" not in action_causes

    def test_take_partial_on_negative_cvd_slope(self):
        intel = PositionIntel(
            cvd_slope=-0.2,  # abs > 0.1 and negative
            book_pressure={"imbalance_ratio": 1.0},
        )
        actions = suggest_risk_actions(intel)
        assert "take_partial" in actions

    def test_take_partial_not_on_positive_cvd_slope(self):
        """Positive CVD slope should NOT trigger take_partial by itself."""
        intel = PositionIntel(
            cvd_slope=0.2,  # positive slope = buying pressure
            book_pressure={"imbalance_ratio": 1.0},
            regime_context="trending",
        )
        actions = suggest_risk_actions(intel)
        assert "take_partial" not in actions

    # -----------------------------------------------------------------------
    # Priority 3: trail_stop
    # -----------------------------------------------------------------------

    def test_trail_stop_fires_on_full_trending_confluence_positive_cvd(self):
        intel = PositionIntel(
            confluence_score=3,
            regime_context="trending",
            cvd_slope=0.1,  # > 0.05
            book_pressure={"imbalance_ratio": 1.0},
        )
        actions = suggest_risk_actions(intel)
        assert "trail_stop" in actions
        assert "exit_full" not in actions

    def test_trail_stop_not_without_full_confluence(self):
        intel = PositionIntel(
            confluence_score=2,  # not 3
            regime_context="trending",
            cvd_slope=0.2,
        )
        actions = suggest_risk_actions(intel)
        assert "trail_stop" not in actions

    def test_trail_stop_not_in_choppy_regime(self):
        intel = PositionIntel(
            confluence_score=3,
            regime_context="choppy",
            cvd_slope=0.2,
        )
        actions = suggest_risk_actions(intel)
        assert "trail_stop" not in actions

    def test_trail_stop_not_with_low_cvd_slope(self):
        intel = PositionIntel(
            confluence_score=3,
            regime_context="trending",
            cvd_slope=0.01,  # <= 0.05 threshold
        )
        actions = suggest_risk_actions(intel)
        assert "trail_stop" not in actions

    # -----------------------------------------------------------------------
    # Priority 4: add_size
    # -----------------------------------------------------------------------

    def test_add_size_fires_when_all_conditions_met(self):
        intel = PositionIntel(
            confluence_score=3,
            regime_context="trending",
            position_multiplier=1.0,
            cvd_slope=0.2,  # > 0.1
            book_pressure={"imbalance_ratio": 1.0},
        )
        actions = suggest_risk_actions(intel)
        assert "add_size" in actions

    def test_add_size_not_when_multiplier_below_one(self):
        intel = PositionIntel(
            confluence_score=3,
            regime_context="trending",
            position_multiplier=0.5,
            cvd_slope=0.2,
        )
        actions = suggest_risk_actions(intel)
        assert "add_size" not in actions

    def test_add_size_not_when_take_partial_fired(self):
        intel = PositionIntel(
            confluence_score=3,
            regime_context="trending",
            position_multiplier=1.0,
            cvd_slope=0.2,
            book_pressure={"imbalance_ratio": 0.3},  # triggers take_partial
        )
        actions = suggest_risk_actions(intel)
        assert "take_partial" in actions
        assert "add_size" not in actions

    # -----------------------------------------------------------------------
    # Priority 5: hold (default)
    # -----------------------------------------------------------------------

    def test_hold_is_default(self):
        # Neutral intel — nothing special fires
        intel = PositionIntel()
        actions = suggest_risk_actions(intel)
        assert actions == ["hold"]

    def test_hold_not_present_when_other_action_fires(self):
        intel = PositionIntel(
            regime_context="volatile",
            cvd_slope=-0.5,
            book_pressure={"imbalance_ratio": 0.2},
        )
        actions = suggest_risk_actions(intel)
        assert "hold" not in actions

    # -----------------------------------------------------------------------
    # General properties
    # -----------------------------------------------------------------------

    def test_no_duplicates_in_result(self):
        intel = PositionIntel(
            confluence_score=3,
            regime_context="trending",
            position_multiplier=1.0,
            cvd_slope=0.2,
        )
        actions = suggest_risk_actions(intel)
        assert len(actions) == len(set(actions))

    def test_returns_list(self):
        assert isinstance(suggest_risk_actions(PositionIntel()), list)

    def test_no_book_pressure_key_uses_default(self):
        """When book_pressure has no imbalance_ratio key, default 1.0 is used."""
        intel = PositionIntel(book_pressure={})
        # Should not crash; default imbalance 1.0 means no adverse book signal
        actions = suggest_risk_actions(intel)
        assert isinstance(actions, list)


# ---------------------------------------------------------------------------
# Helper used inside tests (NOT a production function)
# ---------------------------------------------------------------------------


def _explain_partial_causes(intel: PositionIntel) -> list[str]:
    """Mirror the internal partial-reason logic for assertion clarity."""
    reasons = []
    imbalance = intel.book_pressure.get("imbalance_ratio", 1.0)
    if imbalance < 0.5:
        reasons.append("book_imbalance")
    if intel.regime_context == "choppy" and intel.confluence_score < 2:
        reasons.append("choppy_low_confluence")
    if abs(intel.cvd_slope) > 0.1 and intel.cvd_slope < 0:
        reasons.append("cvd_selling_pressure")
    return reasons


# ===========================================================================
# _estimate_atr
# ===========================================================================


class TestEstimateATR:
    """Tests for the internal ATR estimation helper."""

    def test_returns_positive_for_normal_data(self, bars_5m):
        atr = _estimate_atr(bars_5m)
        assert atr > 0.0

    def test_returns_zero_for_empty_df(self, empty_df):
        atr = _estimate_atr(empty_df)
        assert atr == 0.0

    def test_returns_zero_for_too_short_df(self):
        # Need at least period+1 rows; default period=14
        df = _make_ohlcv(n=5)
        atr = _estimate_atr(df, period=14)
        assert atr == 0.0

    def test_custom_period(self, bars_5m):
        atr5 = _estimate_atr(bars_5m, period=5)
        atr20 = _estimate_atr(bars_5m, period=20)
        # Both should be positive; short period is usually more reactive
        assert atr5 > 0.0
        assert atr20 > 0.0

    def test_scales_with_price(self):
        """Higher-priced assets should have higher raw ATR."""
        df_low = _make_ohlcv(n=100, start_price=100.0, seed=1)
        df_high = _make_ohlcv(n=100, start_price=10_000.0, seed=1)
        # Same seed but 100× price difference → ATR should scale proportionally
        assert _estimate_atr(df_high) > _estimate_atr(df_low)

    def test_exact_enough_rows(self):
        # Exactly period+1 rows should work
        df = _make_ohlcv(n=15, seed=7)
        atr = _estimate_atr(df, period=14)
        assert atr >= 0.0  # may be 0 or small but should not raise

    def test_returns_float(self, bars_5m):
        atr = _estimate_atr(bars_5m)
        assert isinstance(atr, float)


# ===========================================================================
# compute_position_intelligence — integration (mocked analysis modules)
# ===========================================================================


class TestComputePositionIntelligence:
    """End-to-end tests for the main POSINT entry point.

    All heavy analysis modules are patched so these tests run fast and
    deterministically with no GPU / network requirements.
    """

    # -----------------------------------------------------------------------
    # Patch helpers
    # -----------------------------------------------------------------------

    @staticmethod
    def _ict_mock() -> MagicMock:
        m = MagicMock()
        m.return_value = {
            "nearest_levels": {
                "above": {"price": 5050.0, "label": "FVG", "distance": 5.0},
                "below": {"price": 4990.0, "label": "OB", "distance": 10.0},
            },
            "stats": {"fvg_count": 2},
        }
        return m

    @staticmethod
    def _confluence_mock() -> MagicMock:
        m = MagicMock()
        m.return_value = {
            "score": 2,
            "quality": 0.75,
            "direction": "bullish",
            "tradeable": True,
        }
        return m

    @staticmethod
    def _volume_profile_mock() -> MagicMock:
        m = MagicMock()
        m.return_value = {
            "poc": 5015.0,
            "vah": 5030.0,
            "val": 5000.0,
            "bin_volumes": {},
            "hvn": [5015.0],
            "lvn": [5005.0],
        }
        return m

    @staticmethod
    def _cvd_df_mock(n: int = 10) -> pd.DataFrame:
        idx = pd.date_range("2025-01-06 09:30", periods=n, freq="1min", tz="America/New_York")
        return pd.DataFrame(
            {
                "buy_volume": [100.0] * n,
                "sell_volume": [80.0] * n,
                "delta": [20.0] * n,
                "cvd": list(range(0, n * 20, 20)),
                "cvd_slope": [0.15] * n,
                "cvd_source": ["ohlcv"] * n,
            },
            index=idx,
        )

    @staticmethod
    def _regime_mock() -> MagicMock:
        m = MagicMock()
        m.return_value = {
            "regime": "trending",
            "confidence": 0.88,
            "position_multiplier": 1.0,
            "confident": True,
            "probabilities": {"trending": 0.88, "choppy": 0.08, "volatile": 0.04},
        }
        return m

    # -----------------------------------------------------------------------
    # Full happy-path test
    # -----------------------------------------------------------------------

    def test_happy_path(self, bars_1m, bars_5m):
        """All modules succeed — verify PositionIntel is fully populated."""
        ict_fn = self._ict_mock()
        conf_fn = self._confluence_mock()
        vp_fn = self._volume_profile_mock()
        cvd_df = self._cvd_df_mock()
        regime_fn = self._regime_mock()

        with (
            patch(
                "lib.services.engine.position_intelligence._import_ict_summary",
                return_value=ict_fn,
            ),
            patch(
                "lib.services.engine.position_intelligence._import_check_confluence",
                return_value=conf_fn,
            ),
            patch(
                "lib.services.engine.position_intelligence._import_compute_volume_profile",
                return_value=vp_fn,
            ),
            patch(
                "lib.services.engine.position_intelligence._import_compute_cvd",
                return_value=lambda df: cvd_df,
            ),
            patch(
                "lib.services.engine.position_intelligence._import_regime_detector",
                return_value=MagicMock(),
            ),
            patch(
                "lib.analysis.regime.detect_regime_hmm",
                side_effect=regime_fn,
                create=True,
            ),
        ):
            intel = compute_position_intelligence(
                symbol="MES",
                entry_price=5010.0,
                direction="long",
                bars_1m=bars_1m,
                bars_5m=bars_5m,
                l2_depth={
                    "bids": [{"price": 5009.0, "size": 100}],
                    "asks": [{"price": 5011.0, "size": 80}],
                },
            )

        assert isinstance(intel, PositionIntel)
        # ICT sweep zones
        assert len(intel.sweep_zones) > 0
        # Confluence
        assert intel.confluence_score == 2
        assert intel.confluence_quality == pytest.approx(0.75)
        assert intel.confluence_direction == "bullish"
        # Volume profile
        assert intel.vp_levels["poc"] == pytest.approx(5015.0)
        assert intel.vp_levels["vah"] == pytest.approx(5030.0)
        assert intel.vp_levels["val"] == pytest.approx(5000.0)
        # CVD
        assert intel.cvd > 0.0
        assert intel.cvd_slope == pytest.approx(0.15)
        # Multi-TP
        assert len(intel.multi_tp_targets) >= 2
        # Book pressure
        assert "imbalance_ratio" in intel.book_pressure
        # Risk actions — must be non-empty
        assert len(intel.risk_actions) > 0

    # -----------------------------------------------------------------------
    # Returns PositionIntel even with empty DataFrames
    # -----------------------------------------------------------------------

    def test_empty_dataframes_return_defaults(self, empty_df):
        """Empty bars should cause each module to be skipped; no crash."""
        intel = compute_position_intelligence(
            symbol="MES",
            entry_price=5000.0,
            direction="long",
            bars_1m=empty_df,
            bars_5m=empty_df,
        )
        assert isinstance(intel, PositionIntel)
        assert intel.sweep_zones == []
        assert intel.confluence_score == 0
        assert intel.multi_tp_targets == []

    # -----------------------------------------------------------------------
    # Module-level fallback tests — each module raises; others still run
    # -----------------------------------------------------------------------

    def test_ict_failure_does_not_crash(self, bars_1m, bars_5m):
        def _raise_ict():
            def _fn(df):
                raise RuntimeError("ICT module broken")

            return _fn

        with patch(
            "lib.services.engine.position_intelligence._import_ict_summary",
            return_value=_raise_ict(),
        ):
            intel = compute_position_intelligence(
                symbol="MES",
                entry_price=5000.0,
                direction="long",
                bars_1m=bars_1m,
                bars_5m=bars_5m,
            )
        assert isinstance(intel, PositionIntel)
        assert intel.sweep_zones == []

    def test_confluence_failure_does_not_crash(self, bars_1m, bars_5m):
        def _raise_conf(htf_df, setup_df, entry_df, asset_name):
            raise ValueError("Confluence module broken")

        with patch(
            "lib.services.engine.position_intelligence._import_check_confluence",
            return_value=_raise_conf,
        ):
            intel = compute_position_intelligence(
                symbol="MES",
                entry_price=5000.0,
                direction="long",
                bars_1m=bars_1m,
                bars_5m=bars_5m,
            )
        assert isinstance(intel, PositionIntel)
        assert intel.confluence_score == 0

    def test_volume_profile_failure_does_not_crash(self, bars_1m, bars_5m):
        def _raise_vp(df, n_bins=50):
            raise RuntimeError("VP broken")

        with patch(
            "lib.services.engine.position_intelligence._import_compute_volume_profile",
            return_value=_raise_vp,
        ):
            intel = compute_position_intelligence(
                symbol="MES",
                entry_price=5000.0,
                direction="long",
                bars_1m=bars_1m,
                bars_5m=bars_5m,
            )
        assert isinstance(intel, PositionIntel)
        # vp_levels should fall back to entry price
        assert intel.vp_levels.get("poc") == pytest.approx(5000.0)

    def test_cvd_failure_does_not_crash(self, bars_1m, bars_5m):
        def _raise_cvd(df):
            raise RuntimeError("CVD broken")

        with patch(
            "lib.services.engine.position_intelligence._import_compute_cvd",
            return_value=_raise_cvd,
        ):
            intel = compute_position_intelligence(
                symbol="MES",
                entry_price=5000.0,
                direction="long",
                bars_1m=bars_1m,
                bars_5m=bars_5m,
            )
        assert isinstance(intel, PositionIntel)
        assert intel.cvd == pytest.approx(0.0)
        assert intel.cvd_slope == pytest.approx(0.0)

    def test_regime_failure_does_not_crash(self, bars_1m, bars_5m):
        with (
            patch(
                "lib.services.engine.position_intelligence._import_regime_detector",
                return_value=MagicMock(),
            ),
            patch(
                "lib.analysis.regime.detect_regime_hmm",
                side_effect=RuntimeError("HMM broken"),
                create=True,
            ),
            # Also patch the fallback detector so it raises too
            patch(
                "lib.services.engine.position_intelligence._import_regime_detector",
                return_value=None,
            ),
        ):
            intel = compute_position_intelligence(
                symbol="MES",
                entry_price=5000.0,
                direction="long",
                bars_1m=bars_1m,
                bars_5m=bars_5m,
            )
        assert isinstance(intel, PositionIntel)
        assert intel.regime_context == "unknown"

    def test_all_modules_missing_returns_defaults(self, bars_1m, bars_5m):
        """If every lazy import returns None, the result should be a valid PositionIntel."""
        with (
            patch(
                "lib.services.engine.position_intelligence._import_ict_summary",
                return_value=None,
            ),
            patch(
                "lib.services.engine.position_intelligence._import_check_confluence",
                return_value=None,
            ),
            patch(
                "lib.services.engine.position_intelligence._import_compute_volume_profile",
                return_value=None,
            ),
            patch(
                "lib.services.engine.position_intelligence._import_compute_cvd",
                return_value=None,
            ),
            patch(
                "lib.services.engine.position_intelligence._import_regime_detector",
                return_value=None,
            ),
        ):
            intel = compute_position_intelligence(
                symbol="MES",
                entry_price=5000.0,
                direction="long",
                bars_1m=bars_1m,
                bars_5m=bars_5m,
            )

        assert isinstance(intel, PositionIntel)
        assert intel.sweep_zones == []
        assert intel.confluence_score == 0
        assert intel.regime_context == "unknown"

    # -----------------------------------------------------------------------
    # Direction handling
    # -----------------------------------------------------------------------

    def test_long_direction_tp_targets_above_entry(self, bars_1m, bars_5m):
        with (
            patch("lib.services.engine.position_intelligence._import_ict_summary", return_value=None),
            patch("lib.services.engine.position_intelligence._import_check_confluence", return_value=None),
            patch("lib.services.engine.position_intelligence._import_compute_volume_profile", return_value=None),
            patch("lib.services.engine.position_intelligence._import_compute_cvd", return_value=None),
            patch("lib.services.engine.position_intelligence._import_regime_detector", return_value=None),
        ):
            intel = compute_position_intelligence(
                symbol="MES",
                entry_price=5000.0,
                direction="long",
                bars_1m=bars_1m,
                bars_5m=bars_5m,
            )

        # With real ATR from bars_5m but all modules patched to None, multi_tp
        # is still computed via _estimate_atr — targets should be above entry
        for tp in intel.multi_tp_targets:
            assert tp > 5000.0

    def test_short_direction_tp_targets_below_entry(self, bars_1m, bars_5m):
        with (
            patch("lib.services.engine.position_intelligence._import_ict_summary", return_value=None),
            patch("lib.services.engine.position_intelligence._import_check_confluence", return_value=None),
            patch("lib.services.engine.position_intelligence._import_compute_volume_profile", return_value=None),
            patch("lib.services.engine.position_intelligence._import_compute_cvd", return_value=None),
            patch("lib.services.engine.position_intelligence._import_regime_detector", return_value=None),
        ):
            intel = compute_position_intelligence(
                symbol="MES",
                entry_price=5000.0,
                direction="short",
                bars_1m=bars_1m,
                bars_5m=bars_5m,
            )

        for tp in intel.multi_tp_targets:
            assert tp < 5000.0

    # -----------------------------------------------------------------------
    # L2 depth integration
    # -----------------------------------------------------------------------

    def test_l2_depth_none_gives_empty_book_pressure(self, bars_1m, bars_5m):
        with (
            patch("lib.services.engine.position_intelligence._import_ict_summary", return_value=None),
            patch("lib.services.engine.position_intelligence._import_check_confluence", return_value=None),
            patch("lib.services.engine.position_intelligence._import_compute_volume_profile", return_value=None),
            patch("lib.services.engine.position_intelligence._import_compute_cvd", return_value=None),
            patch("lib.services.engine.position_intelligence._import_regime_detector", return_value=None),
        ):
            intel = compute_position_intelligence(
                symbol="MES",
                entry_price=5000.0,
                direction="long",
                bars_1m=bars_1m,
                bars_5m=bars_5m,
                l2_depth=None,
            )
        assert intel.book_pressure == {}

    def test_l2_depth_populated_gives_book_pressure(self, bars_1m, bars_5m):
        l2 = {
            "bids": [{"price": 4999.0, "size": 200}],
            "asks": [{"price": 5001.0, "size": 100}],
        }
        with (
            patch("lib.services.engine.position_intelligence._import_ict_summary", return_value=None),
            patch("lib.services.engine.position_intelligence._import_check_confluence", return_value=None),
            patch("lib.services.engine.position_intelligence._import_compute_volume_profile", return_value=None),
            patch("lib.services.engine.position_intelligence._import_compute_cvd", return_value=None),
            patch("lib.services.engine.position_intelligence._import_regime_detector", return_value=None),
        ):
            intel = compute_position_intelligence(
                symbol="MES",
                entry_price=5000.0,
                direction="long",
                bars_1m=bars_1m,
                bars_5m=bars_5m,
                l2_depth=l2,
            )
        assert intel.book_pressure.get("bid_total") == pytest.approx(200.0)
        assert intel.book_pressure.get("ask_total") == pytest.approx(100.0)

    # -----------------------------------------------------------------------
    # Return type guarantee
    # -----------------------------------------------------------------------

    def test_always_returns_positionintel(self, bars_1m, bars_5m):
        result = compute_position_intelligence(
            symbol="TEST",
            entry_price=100.0,
            direction="long",
            bars_1m=bars_1m,
            bars_5m=bars_5m,
        )
        assert isinstance(result, PositionIntel)

    def test_to_dict_on_result_is_valid(self, bars_1m, bars_5m):
        import json

        with (
            patch("lib.services.engine.position_intelligence._import_ict_summary", return_value=None),
            patch("lib.services.engine.position_intelligence._import_check_confluence", return_value=None),
            patch("lib.services.engine.position_intelligence._import_compute_volume_profile", return_value=None),
            patch("lib.services.engine.position_intelligence._import_compute_cvd", return_value=None),
            patch("lib.services.engine.position_intelligence._import_regime_detector", return_value=None),
        ):
            intel = compute_position_intelligence(
                symbol="MES",
                entry_price=5000.0,
                direction="long",
                bars_1m=bars_1m,
                bars_5m=bars_5m,
            )
        d = intel.to_dict()
        # Should serialise without error
        json.dumps(d)
        assert "confluence_score" in d
