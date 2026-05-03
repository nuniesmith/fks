"""SIGNALS-B pre-filter verification tests.

Verifies that ExecutionGate.route_signal() correctly applies the focus-asset
filter (layer A) before any other checks:

  - Non-focus assets (e.g. "AAPL") are blocked immediately with BLOCK_FOCUS.
  - Focus futures (e.g. "MES") pass the focus filter and reach execution.
  - Focus crypto (e.g. "BTC") passes the focus filter.
  - The gate falls back to the hardcoded FOCUS_ASSETS constant when Redis
    is unavailable.
  - When Redis provides a ``config:enabled_assets`` payload, the gate uses
    that live set instead of the hardcoded defaults.

SIGNALS-B gate-level filtering confirmation
-------------------------------------------
The ``_handle_check_breakout_multi`` function in handlers_breakout.py
delegates to ``handle_breakout_multi()`` which routes every detected
breakout signal through ExecutionGate.route_signal().  Gate layer A
(focus filter) blocks all non-focus assets *before* any execution
logic runs — ensuring only the six configured micro-futures and approved
crypto symbols ever reach the order queue or the Rithmic manual-confirm
flow.  This test suite is the automated proof that the gate enforces
that contract.
"""

import json
import os

os.environ.setdefault("DISABLE_REDIS", "1")

from unittest.mock import patch

# ---------------------------------------------------------------------------
# Lazy imports — keep at module level for speed; all are pure Python / no I/O
# ---------------------------------------------------------------------------
from lib.services.engine.execution_gate import (
    FOCUS_ASSETS,
    FOCUS_CRYPTO,
    FOCUS_FUTURES,
    REDIS_ENABLED_ASSETS,
    ExecutionGate,
    GateConfig,
    GateVerdict,
)

# ---------------------------------------------------------------------------
# Minimal duck-typed signal factories
# ---------------------------------------------------------------------------


def _signal(symbol: str, direction: str = "LONG", confidence: float = 0.9, price: float = 100.0) -> dict:
    """Return a minimal dict-shaped signal accepted by route_signal()."""
    return {
        "symbol": symbol,
        "direction": direction,
        "confidence": confidence,
        "trigger_price": price,
        "size": 1,
    }


def _mes_signal(**kwargs) -> dict:
    return _signal("MES", price=5_000.0, **kwargs)


def _aapl_signal(**kwargs) -> dict:
    return _signal("AAPL", price=180.0, **kwargs)


def _btc_signal(**kwargs) -> dict:
    return _signal("BTC", price=70_000.0, **kwargs)


# ===========================================================================
# 1.  Focus-set constants
# ===========================================================================


class TestFocusConstants:
    """The module-level constants must satisfy basic invariants."""

    def test_focus_futures_contains_mes(self):
        assert "MES" in FOCUS_FUTURES, "MES must be in FOCUS_FUTURES"

    def test_focus_futures_contains_mgc(self):
        assert "MGC" in FOCUS_FUTURES

    def test_focus_futures_contains_mnq(self):
        assert "MNQ" in FOCUS_FUTURES

    def test_focus_crypto_contains_btc(self):
        assert "BTC" in FOCUS_CRYPTO

    def test_focus_assets_is_union(self):
        assert FOCUS_ASSETS == FOCUS_FUTURES | FOCUS_CRYPTO

    def test_aapl_not_in_focus_assets(self):
        assert "AAPL" not in FOCUS_ASSETS, "AAPL is an equity — must NOT appear in FOCUS_ASSETS"

    def test_spy_not_in_focus_assets(self):
        assert "SPY" not in FOCUS_ASSETS

    def test_focus_futures_and_crypto_disjoint(self):
        overlap = FOCUS_FUTURES & FOCUS_CRYPTO
        assert not overlap, f"FOCUS_FUTURES and FOCUS_CRYPTO should be disjoint; overlap: {overlap}"

    def test_focus_futures_non_empty(self):
        assert len(FOCUS_FUTURES) > 0

    def test_focus_crypto_non_empty(self):
        assert len(FOCUS_CRYPTO) > 0


# ===========================================================================
# 2.  BLOCK_FOCUS for non-focus assets
# ===========================================================================


class TestNonFocusAssetsBlocked:
    """Non-focus assets must be blocked at gate layer A (BLOCK_FOCUS).

    These tests do not mock ``_check_risk`` because the focus filter fires
    before risk is ever evaluated — the gate must return BLOCK_FOCUS
    *immediately* without touching the risk manager or Redis queues.
    """

    def setup_method(self):
        self.gate = ExecutionGate()

    def test_aapl_blocked_with_high_confidence(self):
        """AAPL with conf=0.99 must be blocked — it is not a focus asset."""
        verdict = self.gate.route_signal(_aapl_signal(confidence=0.99))
        assert verdict == GateVerdict.BLOCK_FOCUS, f"Expected BLOCK_FOCUS for AAPL, got {verdict}"

    def test_tsla_blocked(self):
        verdict = self.gate.route_signal(_signal("TSLA", price=250.0))
        assert verdict == GateVerdict.BLOCK_FOCUS

    def test_nvda_blocked(self):
        verdict = self.gate.route_signal(_signal("NVDA", price=900.0))
        assert verdict == GateVerdict.BLOCK_FOCUS

    def test_spy_blocked(self):
        verdict = self.gate.route_signal(_signal("SPY", price=530.0))
        assert verdict == GateVerdict.BLOCK_FOCUS

    def test_qqq_blocked(self):
        verdict = self.gate.route_signal(_signal("QQQ", price=450.0))
        assert verdict == GateVerdict.BLOCK_FOCUS

    def test_empty_symbol_blocked(self):
        """An empty-string symbol must not match any focus asset."""
        verdict = self.gate.route_signal(_signal(""))
        assert verdict == GateVerdict.BLOCK_FOCUS

    def test_lowercase_non_focus_symbol_blocked(self):
        """The gate normalises symbols to uppercase; 'aapl' == 'AAPL' → blocked."""
        verdict = self.gate.route_signal(_signal("aapl", price=180.0))
        assert verdict == GateVerdict.BLOCK_FOCUS

    def test_partial_focus_name_blocked(self):
        """'ME' is not the same as 'MES' — must be blocked."""
        verdict = self.gate.route_signal(_signal("ME", price=100.0))
        assert verdict == GateVerdict.BLOCK_FOCUS

    def test_block_focus_returned_before_risk_check(self):
        """BLOCK_FOCUS is returned without ever calling _check_risk.

        This proves the focus filter is truly layer A — it short-circuits
        before any risk manager interaction.
        """
        with patch.object(self.gate, "_check_risk") as mock_risk:
            verdict = self.gate.route_signal(_aapl_signal())
        assert verdict == GateVerdict.BLOCK_FOCUS
        mock_risk.assert_not_called()


# ===========================================================================
# 3.  Focus assets pass layer A
# ===========================================================================


class TestFocusAssetsPassFilter:
    """Focus futures and crypto must NOT get BLOCK_FOCUS.

    The tests isolate layer A by mocking ``_check_risk`` so that time-based
    session rules do not interfere with the focus-filter assertion.  The
    important invariant is: the gate never returns BLOCK_FOCUS for a symbol
    that belongs to the configured focus set.
    """

    def setup_method(self):
        self.gate = ExecutionGate()

    def _route_with_risk_mocked(self, signal: dict) -> GateVerdict:
        """Run route_signal with _check_risk forced to (True, '') to isolate focus layer."""
        with patch.object(self.gate, "_check_risk", return_value=(True, "")):
            return self.gate.route_signal(signal)

    # ── Futures ──────────────────────────────────────────────────────────────

    def test_mes_passes_focus_filter(self):
        """MES is in FOCUS_FUTURES — must not return BLOCK_FOCUS."""
        verdict = self._route_with_risk_mocked(_mes_signal())
        assert verdict != GateVerdict.BLOCK_FOCUS, f"MES must pass the focus filter; got {verdict}"

    def test_mes_routes_to_pass_queued(self):
        """MES with high confidence and mocked risk must reach PASS_QUEUED.

        This end-to-end assertion confirms that:
          - Layer A (focus)       → passes
          - Layer B (confidence)  → passes (conf=0.9 > threshold 0.65)
          - Layer C (circuit)     → passes (no Redis data → breaker CLOSED)
          - Layer D (idempotency) → passes (no Redis → not a duplicate)
          - Layer E (risk)        → passes (mocked)
          - _queue_pending        → logs warning (no Redis), returns normally
        The verdict must be PASS_QUEUED (futures path).
        """
        verdict = self._route_with_risk_mocked(_mes_signal())
        assert verdict == GateVerdict.PASS_QUEUED, f"Expected PASS_QUEUED for MES with mocked risk; got {verdict}"

    def test_mgc_passes_focus_filter(self):
        verdict = self._route_with_risk_mocked(_signal("MGC", price=2_500.0))
        assert verdict != GateVerdict.BLOCK_FOCUS

    def test_mnq_passes_focus_filter(self):
        verdict = self._route_with_risk_mocked(_signal("MNQ", price=20_000.0))
        assert verdict != GateVerdict.BLOCK_FOCUS

    def test_m2k_passes_focus_filter(self):
        verdict = self._route_with_risk_mocked(_signal("M2K", price=2_000.0))
        assert verdict != GateVerdict.BLOCK_FOCUS

    def test_mym_passes_focus_filter(self):
        verdict = self._route_with_risk_mocked(_signal("MYM", price=40_000.0))
        assert verdict != GateVerdict.BLOCK_FOCUS

    def test_sil_passes_focus_filter(self):
        verdict = self._route_with_risk_mocked(_signal("SIL", price=30.0))
        assert verdict != GateVerdict.BLOCK_FOCUS

    # ── Crypto ───────────────────────────────────────────────────────────────

    def test_btc_passes_focus_filter(self):
        """BTC is in FOCUS_CRYPTO — must not return BLOCK_FOCUS."""
        verdict = self._route_with_risk_mocked(_btc_signal())
        assert verdict != GateVerdict.BLOCK_FOCUS

    def test_eth_passes_focus_filter(self):
        verdict = self._route_with_risk_mocked(_signal("ETH", price=3_000.0))
        assert verdict != GateVerdict.BLOCK_FOCUS

    # ── Lowercase symbol normalisation ───────────────────────────────────────

    def test_lowercase_mes_passes_focus_filter(self):
        """The gate must normalise 'mes' → 'MES' before the focus check."""
        sig = _signal("mes", price=5_000.0)
        verdict = self._route_with_risk_mocked(sig)
        assert verdict != GateVerdict.BLOCK_FOCUS


# ===========================================================================
# 4.  Focus fallback to hardcoded FOCUS_ASSETS when Redis is unavailable
# ===========================================================================


class TestFocusFallbackToDefaults:
    """When Redis returns no enabled-assets data, the gate uses FOCUS_ASSETS.

    This is the SIGNALS-B verification that the fallback path is correct:
    even without a live Redis connection, the gate enforces the right
    focus list from module-level constants.
    """

    def setup_method(self):
        self.gate = ExecutionGate()

    def test_fallback_focus_futures_matches_constant(self):
        """_get_focus_assets() returns FOCUS_FUTURES when Redis has no data."""
        cfg = GateConfig()
        with patch("lib.core.cache.cache_get", return_value=None):
            fut, cry = self.gate._get_focus_assets(cfg)
        assert fut == FOCUS_FUTURES, f"Expected FOCUS_FUTURES as fallback; got {sorted(fut)}"

    def test_fallback_focus_crypto_matches_constant(self):
        cfg = GateConfig()
        with patch("lib.core.cache.cache_get", return_value=None):
            fut, cry = self.gate._get_focus_assets(cfg)
        assert cry == FOCUS_CRYPTO

    def test_mes_in_fallback_futures(self):
        cfg = GateConfig()
        with patch("lib.core.cache.cache_get", return_value=None):
            fut, _ = self.gate._get_focus_assets(cfg)
        assert "MES" in fut

    def test_aapl_not_in_fallback_futures(self):
        cfg = GateConfig()
        with patch("lib.core.cache.cache_get", return_value=None):
            fut, cry = self.gate._get_focus_assets(cfg)
        assert "AAPL" not in fut
        assert "AAPL" not in cry

    def test_redis_exception_falls_back_to_defaults(self):
        """Even if cache_get raises, _get_focus_assets must return the defaults."""
        cfg = GateConfig()
        with patch("lib.core.cache.cache_get", side_effect=RuntimeError("Redis down")):
            fut, cry = self.gate._get_focus_assets(cfg)
        assert "MES" in fut
        assert "BTC" in cry


# ===========================================================================
# 5.  Focus uses the live Redis set when available
# ===========================================================================


class TestFocusFromRedis:
    """When Redis provides ``config:enabled_assets``, the gate uses that set.

    This verifies the priority: Redis live data > hardcoded defaults.
    """

    def setup_method(self):
        self.gate = ExecutionGate()

    def _make_enabled_assets_payload(self, futures: list[str], crypto: list[str] | None = None) -> bytes:
        """Build a ``config:enabled_assets`` JSON payload as Redis would return it."""
        items = [{"symbol": s, "asset_type": "futures", "enabled": True} for s in futures]
        items += [{"symbol": s, "asset_type": "crypto", "enabled": True} for s in (crypto or [])]
        return json.dumps(items).encode()

    def _mock_cache_get(self, enabled_payload: bytes):
        """Return a side_effect function that yields ``enabled_payload`` for the
        ``config:enabled_assets`` key and None for all others.
        """

        def _cache_get(key: str):
            if key == REDIS_ENABLED_ASSETS:
                return enabled_payload
            return None

        return _cache_get

    def test_redis_custom_futures_override_defaults(self):
        """When Redis returns ['TSLA'] as futures, the gate uses that (not FOCUS_FUTURES)."""
        payload = self._make_enabled_assets_payload(futures=["TSLA"])
        cfg = GateConfig()
        with patch("lib.core.cache.cache_get", side_effect=self._mock_cache_get(payload)):
            fut, _ = self.gate._get_focus_assets(cfg)
        assert "TSLA" in fut, "TSLA from Redis must be in focus futures"
        assert "MES" not in fut, "MES (hardcoded default) must NOT be in focus when Redis overrides"

    def test_redis_focus_blocks_mes_when_not_in_redis_set(self):
        """With a Redis-only ['TSLA'] futures set, 'MES' must get BLOCK_FOCUS."""
        payload = self._make_enabled_assets_payload(futures=["TSLA"])
        with (
            patch("lib.core.cache.cache_get", side_effect=self._mock_cache_get(payload)),
            patch.object(self.gate, "_check_risk", return_value=(True, "")),
        ):
            verdict = self.gate.route_signal(_mes_signal())
        assert verdict == GateVerdict.BLOCK_FOCUS, (
            f"MES must be BLOCK_FOCUS when not in Redis-provided focus set; got {verdict}"
        )

    def test_redis_focus_passes_custom_symbol(self):
        """With a Redis focus set that includes 'TSLA', TSLA must pass focus."""
        payload = self._make_enabled_assets_payload(futures=["TSLA"])
        with (
            patch("lib.core.cache.cache_get", side_effect=self._mock_cache_get(payload)),
            patch.object(self.gate, "_check_risk", return_value=(True, "")),
        ):
            verdict = self.gate.route_signal(_signal("TSLA", price=250.0))
        assert verdict != GateVerdict.BLOCK_FOCUS, f"TSLA in Redis focus set must pass focus filter; got {verdict}"

    def test_redis_crypto_included_in_focus(self):
        """Crypto symbols from Redis are included in the focus set."""
        payload = self._make_enabled_assets_payload(futures=["MES"], crypto=["DOGE"])
        cfg = GateConfig()
        with patch("lib.core.cache.cache_get", side_effect=self._mock_cache_get(payload)):
            _, cry = self.gate._get_focus_assets(cfg)
        assert "DOGE" in cry

    def test_disabled_symbol_excluded_from_focus(self):
        """A symbol with ``enabled=False`` in the Redis payload must NOT be in focus."""
        items = [
            {"symbol": "MES", "asset_type": "futures", "enabled": True},
            {"symbol": "AAPL", "asset_type": "futures", "enabled": False},
        ]
        payload = json.dumps(items).encode()
        cfg = GateConfig()
        with patch("lib.core.cache.cache_get", side_effect=self._mock_cache_get(payload)):
            fut, _ = self.gate._get_focus_assets(cfg)
        assert "MES" in fut
        assert "AAPL" not in fut, "AAPL with enabled=False must be excluded from focus"

    def test_dict_format_redis_payload(self):
        """The gate also accepts a dict-format Redis payload: {"futures": [...], "crypto": [...]}."""
        items = {"futures": ["MES", "MGC"], "crypto": ["BTC"]}
        payload = json.dumps(items).encode()
        cfg = GateConfig()
        with patch("lib.core.cache.cache_get", side_effect=self._mock_cache_get(payload)):
            fut, cry = self.gate._get_focus_assets(cfg)
        assert "MES" in fut
        assert "MGC" in fut
        assert "BTC" in cry


# ===========================================================================
# 6.  Config override via GateConfig fields
# ===========================================================================


class TestGateConfigFocusOverrides:
    """GateConfig.focus_futures_override / focus_crypto_override take priority
    over Redis when non-empty.
    """

    def setup_method(self):
        self.gate = ExecutionGate()

    def test_futures_override_used_when_set(self):
        cfg = GateConfig(focus_futures_override=["MES", "CUSTOM1"])
        fut, _ = self.gate._get_focus_assets(cfg)
        assert "MES" in fut
        assert "CUSTOM1" in fut

    def test_futures_override_excludes_unset_symbols(self):
        cfg = GateConfig(focus_futures_override=["CUSTOM1"])
        fut, _ = self.gate._get_focus_assets(cfg)
        assert "MGC" not in fut, "MGC must not appear when override list omits it"

    def test_crypto_override_used_when_set(self):
        cfg = GateConfig(focus_crypto_override=["DOGE", "SOL"])
        _, cry = self.gate._get_focus_assets(cfg)
        assert "DOGE" in cry
        assert "SOL" in cry

    def test_override_takes_priority_over_redis(self):
        """GateConfig override wins even if Redis has a different enabled-assets list."""
        cfg = GateConfig(focus_futures_override=["OVERRIDE_SYMBOL"])
        redis_payload = json.dumps([{"symbol": "MES", "asset_type": "futures", "enabled": True}]).encode()
        with patch("lib.core.cache.cache_get", return_value=redis_payload):
            fut, _ = self.gate._get_focus_assets(cfg)
        assert "OVERRIDE_SYMBOL" in fut
        assert "MES" not in fut, "Redis data must not override GateConfig.focus_futures_override"


# ===========================================================================
# 7.  Disabled gate passes all signals
# ===========================================================================


class TestGateDisabled:
    """When GateConfig.disabled=True the gate short-circuits to PASS_AUTO."""

    def setup_method(self):
        self.gate = ExecutionGate()

    def test_disabled_gate_passes_non_focus_asset(self):
        """Even AAPL gets PASS_AUTO when the gate is disabled entirely."""
        cfg = GateConfig(disabled=True)
        with patch.object(self.gate, "_cfg", return_value=cfg):
            verdict = self.gate.route_signal(_aapl_signal())
        assert verdict == GateVerdict.PASS_AUTO, f"Disabled gate must return PASS_AUTO for any asset; got {verdict}"

    def test_disabled_gate_passes_mes(self):
        cfg = GateConfig(disabled=True)
        with patch.object(self.gate, "_cfg", return_value=cfg):
            verdict = self.gate.route_signal(_mes_signal())
        assert verdict == GateVerdict.PASS_AUTO
