"""
services/risk_engine.py
========================
Dynamic leverage and margin calculator.

Every trading loop tick, the AssetWorker calls ``compute_risk_profile()``
which combines five live risk signals into a single ``RiskProfile``.  The
profile is then used to:

  1. Set ``effective_leverage`` on the exchange (replaces the static
     ``asset.leverage`` config value for all sizing/order calls).
  2. Set ``effective_margin_pct`` in ``_calc_size()`` (replaces the static
     ``asset.margin_pct`` — shrinks the capital pool in bad conditions).

Risk signals (all normalised to a scalar in [0, 1]):
  ┌─────────────────────┬────────────────────────────────────────────┐
  │ Signal              │ Effect                                     │
  ├─────────────────────┼────────────────────────────────────────────┤
  │ vol_pct             │ ATR percentile — high vol → lower lev/marg │
  │ regime              │ Trending → full, Volatile → cut sharply    │
  │ quality             │ Low-quality setups → reduce exposure       │
  │ daily_drawdown_pct  │ Losing day → scale down progressively      │
  │ consecutive_losses  │ Loss streak → step-down per loss           │
  └─────────────────────┴────────────────────────────────────────────┘

Leverage and margin use independent scalar curves so you can tune them
separately (e.g. cut margin faster than leverage, or vice-versa).

Usage::

    engine = RiskEngine(config)

    profile = engine.compute_risk_profile(
        asset=asset_cfg,
        vol_pct=0.72,
        regime="VOLATILE",
        quality=48.0,
        daily_pnl_usdt=-35.0,
        balance_usdt=1000.0,
        consecutive_losses=2,
    )

    # In _calc_size():
    capital = balance_usdt * profile.effective_margin_pct

    # To set exchange leverage:
    if profile.effective_leverage != current_leverage:
        await _set_leverage(profile.effective_leverage, reason=profile.summary)
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from services.config_loader import AssetConfig, FuturesConfig
from utils.logging_config import get_logger

logger = get_logger("risk_engine")


# ═══════════════════════════════════════════════════════════════════════════
# Output dataclass
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class RiskProfile:
    """Result of a single ``compute_risk_profile()`` call."""

    # ── Primary outputs ──────────────────────────────────────────────
    effective_leverage: int
    effective_margin_pct: float

    # ── Composite scalars ────────────────────────────────────────────
    leverage_scalar: float   # product of all leverage sub-factors
    margin_scalar: float     # product of all margin sub-factors

    # ── Per-factor breakdown (for logging / heartbeat) ────────────────
    factors: dict = field(default_factory=dict)

    # ── One-line diagnostic ──────────────────────────────────────────
    summary: str = ""

    def __str__(self) -> str:
        return (
            f"lev={self.effective_leverage}x "
            f"(×{self.leverage_scalar:.2f}) "
            f"margin={self.effective_margin_pct:.1%} "
            f"(×{self.margin_scalar:.2f}) | {self.summary}"
        )


# ═══════════════════════════════════════════════════════════════════════════
# Internal helpers
# ═══════════════════════════════════════════════════════════════════════════


def _piecewise_linear(x: float, curve: list[tuple[float, float]]) -> float:
    """Interpolate *y* for *x* from a sorted list of (x, y) breakpoints.

    ``curve`` must be sorted ascending by the x-values.  Values outside
    the range are clamped to the first / last y value.
    """
    if not curve:
        return 1.0
    if x <= curve[0][0]:
        return curve[0][1]
    if x >= curve[-1][0]:
        return curve[-1][1]
    for i in range(len(curve) - 1):
        x0, y0 = curve[i]
        x1, y1 = curve[i + 1]
        if x0 <= x <= x1:
            t = (x - x0) / (x1 - x0)
            return y0 + t * (y1 - y0)
    return curve[-1][1]


def _step_lookup(n: int, mapping: dict[int, float], default: float = 1.0) -> float:
    """Return the scalar for *n* consecutive losses.

    Looks for the largest key ≤ n in *mapping*; falls back to *default*.
    """
    applicable = {k: v for k, v in mapping.items() if k <= n}
    if not applicable:
        return default
    return applicable[max(applicable)]


# ═══════════════════════════════════════════════════════════════════════════
# Default curves (all tunable via RiskEngineConfig in config_loader)
# ═══════════════════════════════════════════════════════════════════════════

# vol_pct → leverage scalar
_DEFAULT_VOL_LEV_CURVE: list[tuple[float, float]] = [
    (0.00, 1.15),   # very calm market → slight leverage boost
    (0.30, 1.00),   # normal vol range
    (0.55, 0.80),   # elevated volatility
    (0.75, 0.55),   # high volatility
    (0.90, 0.35),   # extreme volatility
    (1.00, 0.25),   # absolute spike
]

# vol_pct → margin scalar (cut margin faster than leverage in extreme vol)
_DEFAULT_VOL_MARGIN_CURVE: list[tuple[float, float]] = [
    (0.00, 1.10),
    (0.30, 1.00),
    (0.55, 0.85),
    (0.75, 0.65),
    (0.90, 0.45),
    (1.00, 0.30),
]

# quality score (0–100) → leverage scalar
_DEFAULT_QUAL_LEV_CURVE: list[tuple[float, float]] = [
    (0.0,  0.55),
    (40.0, 0.70),
    (60.0, 0.85),
    (80.0, 1.00),
    (100.0, 1.00),
]

# quality score → margin scalar
_DEFAULT_QUAL_MARGIN_CURVE: list[tuple[float, float]] = [
    (0.0,  0.60),
    (40.0, 0.75),
    (60.0, 0.90),
    (80.0, 1.00),
    (100.0, 1.00),
]

# daily drawdown as a fraction of balance (positive = loss) → margin scalar
_DEFAULT_DRAWDOWN_MARGIN_CURVE: list[tuple[float, float]] = [
    (0.000, 1.00),
    (0.005, 0.85),   # -0.5 % daily loss
    (0.010, 0.70),   # -1.0 %
    (0.015, 0.55),   # -1.5 %
    (0.025, 0.35),   # -2.5 %  (near max_asset_daily_loss_pct default)
    (0.040, 0.20),   # -4 %
]

# daily drawdown → leverage scalar (slightly less aggressive than margin)
_DEFAULT_DRAWDOWN_LEV_CURVE: list[tuple[float, float]] = [
    (0.000, 1.00),
    (0.005, 0.90),
    (0.010, 0.75),
    (0.015, 0.60),
    (0.025, 0.45),
    (0.040, 0.30),
]

# consecutive losses → scalar (same curve applied to both lev and margin)
_DEFAULT_CONSEC_LOSS_SCALARS: dict[int, float] = {
    0: 1.00,
    1: 0.90,
    2: 0.75,
    3: 0.60,
    4: 0.45,
}

# regime → leverage scalar
_DEFAULT_REGIME_LEV: dict[str, float] = {
    "trending_bull": 1.10,
    "trending_bear": 1.10,
    "trending":      1.10,
    "neutral":       1.00,
    "ranging":       0.80,
    "volatile":      0.55,
}

# regime → margin scalar
_DEFAULT_REGIME_MARGIN: dict[str, float] = {
    "trending_bull": 1.05,
    "trending_bear": 1.05,
    "trending":      1.05,
    "neutral":       1.00,
    "ranging":       0.85,
    "volatile":      0.65,
}


# ═══════════════════════════════════════════════════════════════════════════
# RiskEngine
# ═══════════════════════════════════════════════════════════════════════════


class RiskEngine:
    """Computes dynamic leverage and margin for each trading loop tick.

    All curves and limits are read from ``config.risk_engine`` if present,
    otherwise the module-level defaults above are used.  This means the
    engine works out-of-the-box without any YAML changes.

    Parameters
    ----------
    config : FuturesConfig
        The shared config singleton.
    """

    def __init__(self, config: FuturesConfig) -> None:
        self._config = config
        re_cfg = getattr(config, "risk_engine", None) or {}

        # ── Global limits ────────────────────────────────────────────
        # Absolute floor on the combined scalar (prevents going to 0)
        self._min_scalar: float = float(getattr(re_cfg, "min_scalar", None) or 0.20)
        # Whether to allow leverage > target when conditions are favourable
        self._allow_leverage_boost: bool = bool(
            getattr(re_cfg, "allow_leverage_boost", True)
        )
        # Global ceiling on the leverage scalar (1.0 = never exceed config target)
        self._max_lev_scalar: float = float(
            getattr(re_cfg, "max_leverage_scalar", 1.20)
        )
        self._global_min_leverage: int = int(
            getattr(re_cfg, "global_min_leverage", 2)
        )

        # ── Load curves (fall back to module defaults) ───────────────
        self._vol_lev_curve = self._load_curve(
            getattr(re_cfg, "vol_leverage_curve", None), _DEFAULT_VOL_LEV_CURVE
        )
        self._vol_margin_curve = self._load_curve(
            getattr(re_cfg, "vol_margin_curve", None), _DEFAULT_VOL_MARGIN_CURVE
        )
        self._qual_lev_curve = self._load_curve(
            getattr(re_cfg, "quality_leverage_curve", None), _DEFAULT_QUAL_LEV_CURVE
        )
        self._qual_margin_curve = self._load_curve(
            getattr(re_cfg, "quality_margin_curve", None), _DEFAULT_QUAL_MARGIN_CURVE
        )
        self._dd_lev_curve = self._load_curve(
            getattr(re_cfg, "drawdown_leverage_curve", None), _DEFAULT_DRAWDOWN_LEV_CURVE
        )
        self._dd_margin_curve = self._load_curve(
            getattr(re_cfg, "drawdown_margin_curve", None), _DEFAULT_DRAWDOWN_MARGIN_CURVE
        )
        raw_consec = getattr(re_cfg, "consec_loss_scalars", None)
        self._consec_scalars: dict[int, float] = (
            {int(k): float(v) for k, v in raw_consec.items()}
            if isinstance(raw_consec, dict)
            else _DEFAULT_CONSEC_LOSS_SCALARS
        )
        raw_regime_lev = getattr(re_cfg, "regime_leverage_multipliers", None)
        self._regime_lev: dict[str, float] = (
            {k.lower(): float(v) for k, v in raw_regime_lev.items()}
            if isinstance(raw_regime_lev, dict)
            else _DEFAULT_REGIME_LEV
        )
        raw_regime_margin = getattr(re_cfg, "regime_margin_multipliers", None)
        self._regime_margin: dict[str, float] = (
            {k.lower(): float(v) for k, v in raw_regime_margin.items()}
            if isinstance(raw_regime_margin, dict)
            else _DEFAULT_REGIME_MARGIN
        )

    # ── Helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _load_curve(
        raw: list | None,
        default: list[tuple[float, float]],
    ) -> list[tuple[float, float]]:
        """Parse [[x, y], ...] from config or return default."""
        if raw and isinstance(raw, list):
            try:
                return [(float(p[0]), float(p[1])) for p in raw]
            except (TypeError, IndexError, ValueError):
                pass
        return default

    def _regime_key(self, regime: str) -> str:
        """Normalise regime string to lowercase lookup key."""
        r = regime.lower().strip()
        # Map common variants
        if r.startswith("trend"):
            return "trending"
        if r in ("volatile", "high_vol", "highvol"):
            return "volatile"
        if r in ("ranging", "range", "sideways"):
            return "ranging"
        return "neutral"

    # ── Core computation ─────────────────────────────────────────────

    def compute_risk_profile(
        self,
        asset: AssetConfig,
        vol_pct: float,
        regime: str,
        quality: float,
        daily_pnl_usdt: float,
        balance_usdt: float,
        consecutive_losses: int,
    ) -> RiskProfile:
        """Compute the effective leverage and margin for this tick.

        All inputs are live values from the trading loop; none are cached
        here — the caller decides how often to call this.

        Parameters
        ----------
        asset : AssetConfig
            The per-asset config (target leverage, max leverage, margin_pct).
        vol_pct : float
            ATR percentile in [0, 1].  From ``compute_vol_pct()``.
        regime : str
            Current market regime string (e.g. "TRENDING_BULL", "VOLATILE").
        quality : float
            Signal quality score in [0, 100].  From ``compute_quality()``.
        daily_pnl_usdt : float
            Today's P&L in USDT (negative = loss).
        balance_usdt : float
            Current portfolio balance in USDT.
        consecutive_losses : int
            Current consecutive loss streak for this asset.

        Returns
        -------
        RiskProfile
            Contains ``effective_leverage`` and ``effective_margin_pct``
            ready to use in ``_calc_size()`` and ``_set_leverage()``.
        """
        rk = self._regime_key(regime)

        # ── 1. Volatility factors ─────────────────────────────────────
        vol_lev_f   = _piecewise_linear(vol_pct, self._vol_lev_curve)
        vol_marg_f  = _piecewise_linear(vol_pct, self._vol_margin_curve)

        # ── 2. Regime factors ─────────────────────────────────────────
        reg_lev_f   = self._regime_lev.get(rk, 1.0)
        reg_marg_f  = self._regime_margin.get(rk, 1.0)

        # ── 3. Quality factors ────────────────────────────────────────
        q_lev_f     = _piecewise_linear(quality, self._qual_lev_curve)
        q_marg_f    = _piecewise_linear(quality, self._qual_margin_curve)

        # ── 4. Daily drawdown factors ─────────────────────────────────
        # Convert negative PnL to a positive drawdown fraction
        if balance_usdt > 0 and daily_pnl_usdt < 0:
            dd_frac = abs(daily_pnl_usdt) / balance_usdt
        else:
            dd_frac = 0.0
        dd_lev_f    = _piecewise_linear(dd_frac, self._dd_lev_curve)
        dd_marg_f   = _piecewise_linear(dd_frac, self._dd_margin_curve)

        # ── 5. Consecutive loss factor ────────────────────────────────
        cl_f        = _step_lookup(consecutive_losses, self._consec_scalars, default=1.0)

        # ── Combine ───────────────────────────────────────────────────
        # Leverage scalar: product of all leverage-specific factors
        raw_lev_scalar = (
            vol_lev_f
            * reg_lev_f
            * q_lev_f
            * dd_lev_f
            * cl_f
        )
        # Margin scalar: product of all margin-specific factors
        raw_marg_scalar = (
            vol_marg_f
            * reg_marg_f
            * q_marg_f
            * dd_marg_f
            * cl_f
        )

        # Apply global floor
        lev_scalar  = max(raw_lev_scalar, self._min_scalar)
        marg_scalar = max(raw_marg_scalar, self._min_scalar)

        # Optionally cap leverage scalar at 1.0 (never exceed target)
        if not self._allow_leverage_boost:
            lev_scalar = min(lev_scalar, 1.0)
        else:
            lev_scalar = min(lev_scalar, self._max_lev_scalar)

        # ── Derive effective values ───────────────────────────────────
        raw_eff_lev = asset.leverage * lev_scalar
        effective_leverage = int(
            max(
                self._global_min_leverage,
                min(math.floor(raw_eff_lev), asset.max_leverage),
            )
        )
        effective_margin_pct = float(
            max(0.01, min(asset.margin_pct * marg_scalar, 1.0))
        )

        # ── Build breakdown for logging ───────────────────────────────
        factors = {
            "vol_pct":          round(vol_pct, 3),
            "vol_lev_f":        round(vol_lev_f, 3),
            "vol_marg_f":       round(vol_marg_f, 3),
            "regime":           rk,
            "reg_lev_f":        round(reg_lev_f, 3),
            "reg_marg_f":       round(reg_marg_f, 3),
            "quality":          round(quality, 1),
            "q_lev_f":          round(q_lev_f, 3),
            "q_marg_f":         round(q_marg_f, 3),
            "dd_frac":          round(dd_frac, 4),
            "dd_lev_f":         round(dd_lev_f, 3),
            "dd_marg_f":        round(dd_marg_f, 3),
            "consec_losses":    consecutive_losses,
            "cl_f":             round(cl_f, 3),
            "lev_scalar":       round(lev_scalar, 3),
            "marg_scalar":      round(marg_scalar, 3),
        }

        # ── Summary ───────────────────────────────────────────────────
        drivers: list[str] = []
        if vol_lev_f < 0.80:
            drivers.append(f"vol↑{vol_pct:.0%}")
        if reg_lev_f < 0.90:
            drivers.append(f"regime={rk}")
        if q_lev_f < 0.85:
            drivers.append(f"qual={quality:.0f}")
        if dd_lev_f < 0.90:
            drivers.append(f"dd={dd_frac:.1%}")
        if cl_f < 1.0:
            drivers.append(f"streak={consecutive_losses}")
        summary = "drivers=[" + ", ".join(drivers) + "]" if drivers else "all-clear"

        return RiskProfile(
            effective_leverage=effective_leverage,
            effective_margin_pct=effective_margin_pct,
            leverage_scalar=round(lev_scalar, 3),
            margin_scalar=round(marg_scalar, 3),
            factors=factors,
            summary=summary,
        )
