"""
Lightweight Charts Bridge
===========================
Server-side chart HTML generation using TradingView Lightweight Charts v4
via CDN.  Returns self-contained HTML pages for iframe embedding or direct
serving.

Indicator set
-------------
Overlays (drawn on the price pane):
    ema_9, ema_20, ema_50        — Exponential Moving Average
    sma_20, sma_50, sma_200      — Simple Moving Average
    bb                           — Bollinger Bands (20, 2σ)
    vwap                         — VWAP with daily reset

Sub-panes (separate chart panel below price):
    rsi_14                       — RSI (14) with 70/50/30 levels
    macd                         — MACD (12/26/9) histogram + lines
    atr_14                       — ATR (14) absolute value
    cvd                          — Cumulative Volume Delta (per-bar, daily reset)

Architecture
------------
All indicator math is pure-Python (no pandas, no numpy) so the module is
fast to import and works in any context.  OHLCV data is fetched from Redis
(fast) then Postgres (slow fallback).

The generated HTML embeds all chart data as JSON globals and initialises
Lightweight Charts v4 from CDN.  Multiple panes are created as separate
chart instances whose time-scales are kept in sync.

Usage
-----
::

    from integrations.lightweight_charts_bridge import generate_chart_html

    # Single chart with EMA and RSI sub-pane
    html = await generate_chart_html("MES", "5m", indicators=["ema_20", "rsi_14"])

    # Full indicator set
    html = await generate_chart_html(
        "MNQ", "15m",
        indicators=["ema_9", "ema_20", "bb", "vwap", "rsi_14", "macd", "cvd"],
    )
"""

from __future__ import annotations

import asyncio
import json
import math
from typing import Any

import structlog

logger = structlog.get_logger("integrations.lightweight_charts_bridge")

# ---------------------------------------------------------------------------
# FKS design tokens
# ---------------------------------------------------------------------------

_THEME: dict[str, str] = {
    "bg": "#0a0a0f",
    "card": "#12121a",
    "border": "#1e1e2e",
    "text": "#e2e8f0",
    "dim": "#4b5563",
    "green": "#10b981",
    "red": "#ef4444",
    "amber": "#f59e0b",
    "cyan": "#00d4ff",
    "purple": "#a78bfa",
    "blue": "#3b82f6",
    "vol_up": "rgba(16,185,129,0.35)",
    "vol_dn": "rgba(239,68,68,0.35)",
}

# ---------------------------------------------------------------------------
# Indicator registry
# ---------------------------------------------------------------------------
# kind:
#   "overlay"  — line series drawn on the main price pane
#   "sub_pane" — separate chart rendered below the price pane

_INDICATOR_CONFIG: dict[str, dict[str, Any]] = {
    # ── Overlays ────────────────────────────────────────────────────────────
    "ema_9": {"label": "EMA 9", "kind": "overlay", "type": "ema", "period": 9, "color": _THEME["green"], "width": 1},
    "ema_20": {"label": "EMA 20", "kind": "overlay", "type": "ema", "period": 20, "color": _THEME["cyan"], "width": 1},
    "ema_50": {"label": "EMA 50", "kind": "overlay", "type": "ema", "period": 50, "color": _THEME["amber"], "width": 1},
    "sma_20": {"label": "SMA 20", "kind": "overlay", "type": "sma", "period": 20, "color": _THEME["amber"], "width": 1},
    "sma_50": {"label": "SMA 50", "kind": "overlay", "type": "sma", "period": 50, "color": _THEME["cyan"], "width": 1},
    "sma_200": {
        "label": "SMA 200",
        "kind": "overlay",
        "type": "sma",
        "period": 200,
        "color": _THEME["dim"],
        "width": 1,
    },
    "bb": {"label": "BB (20,2)", "kind": "overlay", "type": "bb", "period": 20, "std": 2.0, "color": _THEME["purple"]},
    "vwap": {"label": "VWAP", "kind": "overlay", "type": "vwap", "color": _THEME["amber"], "width": 1},
    # ── Sub-panes ───────────────────────────────────────────────────────────
    "rsi_14": {"label": "RSI (14)", "kind": "sub_pane", "type": "rsi", "period": 14, "height": 110},
    "macd": {"label": "MACD", "kind": "sub_pane", "type": "macd", "fast": 12, "slow": 26, "signal": 9, "height": 110},
    "atr_14": {"label": "ATR (14)", "kind": "sub_pane", "type": "atr", "period": 14, "height": 90},
    "cvd": {"label": "CVD", "kind": "sub_pane", "type": "cvd", "height": 90},
}

# ---------------------------------------------------------------------------
# Pure-Python indicator computations
# Each function accepts a list of bar dicts with keys:
#   time (int, unix seconds), open, high, low, close, volume
# and returns lightweight-charts-compatible data points.
# ---------------------------------------------------------------------------


def _compute_sma(bars: list[dict[str, Any]], period: int) -> list[dict[str, Any]]:
    """Simple moving average of close prices."""
    if len(bars) < period:
        return []
    closes = [b["close"] for b in bars]
    result: list[dict[str, Any]] = []
    window_sum = sum(closes[:period])
    result.append({"time": bars[period - 1]["time"], "value": round(window_sum / period, 6)})
    for i in range(period, len(bars)):
        window_sum += closes[i] - closes[i - period]
        result.append({"time": bars[i]["time"], "value": round(window_sum / period, 6)})
    return result


def _compute_ema(bars: list[dict[str, Any]], period: int) -> list[dict[str, Any]]:
    """Exponential moving average of close prices (seeded with SMA)."""
    if len(bars) < period:
        return []
    closes = [b["close"] for b in bars]
    k = 2.0 / (period + 1)
    ema = sum(closes[:period]) / period
    result: list[dict[str, Any]] = []
    result.append({"time": bars[period - 1]["time"], "value": round(ema, 6)})
    for i in range(period, len(bars)):
        ema = closes[i] * k + ema * (1.0 - k)
        result.append({"time": bars[i]["time"], "value": round(ema, 6)})
    return result


def _compute_rsi(bars: list[dict[str, Any]], period: int = 14) -> list[dict[str, Any]]:
    """RSI using Wilder's smoothing method.

    Returns one point per bar starting at index ``period``.
    """
    n = len(bars)
    if n < period + 1:
        return []
    closes = [b["close"] for b in bars]
    # Per-bar deltas (n-1 elements; index k = close[k+1] - close[k])
    gains = [max(closes[i + 1] - closes[i], 0.0) for i in range(n - 1)]
    losses = [max(closes[i] - closes[i + 1], 0.0) for i in range(n - 1)]

    # Seed with SMA of first `period` deltas
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    result: list[dict[str, Any]] = []
    for i in range(period, n):
        rsi = 100.0 - (100.0 / (1.0 + avg_gain / avg_loss)) if avg_loss > 1e-12 else 100.0
        result.append({"time": bars[i]["time"], "value": round(rsi, 2)})
        # Wilder's smoothing: update using the delta from bars[i] → bars[i+1]
        # gains[i] is valid for i < n-1
        if i < n - 1:
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    return result


def _compute_macd(
    bars: list[dict[str, Any]],
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> dict[str, list[dict[str, Any]]]:
    """MACD (fast EMA − slow EMA), signal EMA, and histogram.

    Returns dict with keys ``macd``, ``signal``, ``hist``.
    Histogram bars carry a ``color`` field (green/red).
    """
    n = len(bars)
    if n < slow + signal:
        return {"macd": [], "signal": [], "hist": []}

    closes = [b["close"] for b in bars]
    times = [b["time"] for b in bars]

    k_f = 2.0 / (fast + 1)
    k_s = 2.0 / (slow + 1)
    k_g = 2.0 / (signal + 1)

    # Warm up fast and slow EMAs from bar 0
    ef = es = closes[0]
    macd_vals: list[float] = []
    for c in closes:
        ef = c * k_f + ef * (1.0 - k_f)
        es = c * k_s + es * (1.0 - k_s)
        macd_vals.append(ef - es)

    # Signal EMA of MACD line, seeded at index `slow`
    eg = macd_vals[slow]
    sig_vals: list[float | None] = [None] * slow + [eg]
    for i in range(slow + 1, n):
        eg = macd_vals[i] * k_g + eg * (1.0 - k_g)
        sig_vals.append(eg)

    # Emit points from index (slow + signal) where signal is warmed up
    emit_from = slow + signal
    macd_pts: list[dict[str, Any]] = []
    sig_pts: list[dict[str, Any]] = []
    hist_pts: list[dict[str, Any]] = []

    for i in range(emit_from, n):
        sv = sig_vals[i]
        if sv is None:
            continue
        m = macd_vals[i]
        h = m - sv
        macd_pts.append({"time": times[i], "value": round(m, 8)})
        sig_pts.append({"time": times[i], "value": round(sv, 8)})
        hist_pts.append(
            {
                "time": times[i],
                "value": round(h, 8),
                "color": _THEME["green"] if h >= 0 else _THEME["red"],
            }
        )

    return {"macd": macd_pts, "signal": sig_pts, "hist": hist_pts}


def _compute_atr(bars: list[dict[str, Any]], period: int = 14) -> list[dict[str, Any]]:
    """Wilder ATR (Average True Range).

    True range = max(H−L, |H−prevC|, |L−prevC|).
    Smoothed with Wilder's RMA (same as Wilder RSI smoothing).
    """
    if len(bars) < period + 1:
        return []

    trs: list[tuple[int, float]] = []  # (time, true_range)
    for i in range(1, len(bars)):
        b = bars[i]
        pc = bars[i - 1]["close"]
        tr = max(b["high"] - b["low"], abs(b["high"] - pc), abs(b["low"] - pc))
        trs.append((b["time"], tr))

    if len(trs) < period:
        return []

    # Seed with SMA of first `period` true ranges
    atr = sum(t for _, t in trs[:period]) / period
    result: list[dict[str, Any]] = [{"time": trs[period - 1][0], "value": round(atr, 6)}]

    for i in range(period, len(trs)):
        atr = (atr * (period - 1) + trs[i][1]) / period
        result.append({"time": trs[i][0], "value": round(atr, 6)})

    return result


def _compute_cvd(bars: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Per-bar Cumulative Volume Delta using the OHLCV heuristic.

    Formula (matches fks_charting chart.js calcCVD):
        delta = volume × ((close − low) / (high − low) − 0.5) × 2

    Values reset to 0 at the start of each calendar day (UTC).
    Each data point carries a ``color`` field (green / red).
    """
    result: list[dict[str, Any]] = []
    for b in bars:
        h = b["high"]
        lo = b["low"]
        c = b["close"]
        vol = b.get("volume") or 0.0
        rng = h - lo
        delta = vol * ((c - lo) / rng - 0.5) * 2.0 if rng > 1e-10 else 0.0
        color = _THEME["green"] if delta >= 0 else _THEME["red"]
        result.append({"time": b["time"], "value": round(delta, 4), "color": color})
    return result


def _compute_bb(
    bars: list[dict[str, Any]],
    period: int = 20,
    std_dev: float = 2.0,
) -> dict[str, list[dict[str, Any]]]:
    """Bollinger Bands (SMA ± std_dev × σ).

    Returns dict with keys ``upper``, ``mid``, ``lower``.
    """
    if len(bars) < period:
        return {"upper": [], "mid": [], "lower": []}

    closes = [b["close"] for b in bars]
    upper: list[dict[str, Any]] = []
    mid: list[dict[str, Any]] = []
    lower: list[dict[str, Any]] = []

    # Sliding window
    window_sum = sum(closes[:period])
    for i in range(period - 1, len(bars)):
        if i >= period:
            window_sum += closes[i] - closes[i - period]
        mean = window_sum / period
        variance = sum((closes[j] - mean) ** 2 for j in range(i - period + 1, i + 1)) / period
        sigma = math.sqrt(variance)
        t = bars[i]["time"]
        mid.append({"time": t, "value": round(mean, 6)})
        upper.append({"time": t, "value": round(mean + std_dev * sigma, 6)})
        lower.append({"time": t, "value": round(mean - std_dev * sigma, 6)})

    return {"upper": upper, "mid": mid, "lower": lower}


def _compute_vwap(bars: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Daily-reset VWAP (typical price × volume / cumulative volume).

    Resets at the start of each UTC calendar day (unix timestamp % 86400 == 0).
    """
    result: list[dict[str, Any]] = []
    cum_tpv = 0.0
    cum_vol = 0.0
    last_day: int | None = None

    for b in bars:
        day = b["time"] // 86400
        if day != last_day:
            cum_tpv = 0.0
            cum_vol = 0.0
            last_day = day
        vol = b.get("volume") or 0.0
        tp = (b["high"] + b["low"] + b["close"]) / 3.0
        cum_tpv += tp * vol
        cum_vol += vol
        if cum_vol > 1e-10:
            result.append({"time": b["time"], "value": round(cum_tpv / cum_vol, 6)})
    return result


# ---------------------------------------------------------------------------
# OHLCV data fetch helpers
# ---------------------------------------------------------------------------


def _fetch_ohlcv_redis(symbol: str, timeframe: str, limit: int) -> list[dict[str, Any]]:
    """Pull OHLCV bars from Redis sorted-set ``bars:{symbol}:{timeframe}``."""
    try:
        from core.cache import REDIS_AVAILABLE, _r  # type: ignore[import-unresolved]

        if not REDIS_AVAILABLE or _r is None:
            return []
        raw = _r.zrange(f"bars:{symbol}:{timeframe}", -limit, -1)
        bars: list[dict[str, Any]] = []
        for item in raw:
            try:
                bars.append(json.loads(item))
            except (json.JSONDecodeError, TypeError):
                continue
        return bars
    except Exception as exc:
        logger.debug("redis_ohlcv_miss", symbol=symbol, error=str(exc))
        return []


def _fetch_ohlcv_postgres(symbol: str, timeframe: str, limit: int) -> list[dict[str, Any]]:
    """Pull OHLCV bars from Postgres ``historical_bars`` table."""
    try:
        import psycopg2  # type: ignore[import-untyped]

        from core.db.postgres import get_connection_string  # type: ignore[import-unresolved]

        dsn = get_connection_string()
        conn = psycopg2.connect(dsn)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT timestamp, open, high, low, close, volume
                      FROM historical_bars
                     WHERE symbol = %s AND interval = %s
                     ORDER BY timestamp DESC
                     LIMIT %s
                    """,
                    (symbol, timeframe, limit),
                )
                rows = cur.fetchall()
        finally:
            conn.close()
        return [
            {
                "time": int(ts),
                "open": float(o),
                "high": float(h),
                "low": float(lo),
                "close": float(c),
                "volume": float(v) if v is not None else 0.0,
            }
            for ts, o, h, lo, c, v in reversed(rows)
        ]
    except Exception as exc:
        logger.debug("postgres_ohlcv_miss", symbol=symbol, error=str(exc))
        return []


def _get_ohlcv(symbol: str, timeframe: str, limit: int) -> list[dict[str, Any]]:
    bars = _fetch_ohlcv_redis(symbol, timeframe, limit)
    if bars:
        return bars
    return _fetch_ohlcv_postgres(symbol, timeframe, limit)


# ---------------------------------------------------------------------------
# Indicator computation pipeline
# ---------------------------------------------------------------------------


def _build_overlays(
    bars: list[dict[str, Any]],
    requested: list[str],
) -> list[dict[str, Any]]:
    """Compute all overlay indicators and return a list of line-series defs.

    Each entry:
        label    str  — legend text
        color    str  — CSS colour
        width    int  — line width in pixels
        dashed   bool — dashed line style
        data     list — [{time, value}, …]
    """
    overlays: list[dict[str, Any]] = []

    for key in requested:
        cfg = _INDICATOR_CONFIG.get(key)
        if not cfg or cfg["kind"] != "overlay":
            continue

        kind = cfg["type"]

        if kind in ("ema", "sma"):
            data = _compute_ema(bars, cfg["period"]) if kind == "ema" else _compute_sma(bars, cfg["period"])
            overlays.append(
                {
                    "label": cfg["label"],
                    "color": cfg["color"],
                    "width": cfg.get("width", 1),
                    "dashed": False,
                    "data": data,
                }
            )

        elif kind == "bb":
            bb = _compute_bb(bars, cfg["period"], cfg["std"])
            col = cfg["color"]
            for part, label, dashed in (
                ("upper", "BB Upper", True),
                ("mid", "BB Mid", False),
                ("lower", "BB Lower", True),
            ):
                overlays.append(
                    {
                        "label": label,
                        "color": col,
                        "width": 1,
                        "dashed": dashed,
                        "data": bb[part],
                    }
                )

        elif kind == "vwap":
            overlays.append(
                {
                    "label": cfg["label"],
                    "color": cfg["color"],
                    "width": cfg.get("width", 1),
                    "dashed": False,
                    "data": _compute_vwap(bars),
                }
            )

    return overlays


def _build_sub_panes(
    bars: list[dict[str, Any]],
    requested: list[str],
) -> list[dict[str, Any]]:
    """Compute all sub-pane indicators.

    Each entry:
        id      str  — unique pane identifier
        label   str  — pane header text
        height  int  — pane height in pixels
        type    str  — rsi | macd | atr | cvd
        series  list — list of series defs (type, data, color, …)
        levels  list — horizontal price lines [{value, color, label}, …]
    """
    sub_panes: list[dict[str, Any]] = []
    seen: set[str] = set()

    for key in requested:
        cfg = _INDICATOR_CONFIG.get(key)
        if not cfg or cfg["kind"] != "sub_pane":
            continue
        kind = cfg["type"]
        if kind in seen:
            continue
        seen.add(kind)

        if kind == "rsi":
            data = _compute_rsi(bars, cfg["period"])
            sub_panes.append(
                {
                    "id": "rsi",
                    "label": cfg["label"],
                    "height": cfg["height"],
                    "type": "rsi",
                    "series": [
                        {
                            "type": "line",
                            "label": "RSI",
                            "data": data,
                            "color": _THEME["purple"],
                            "width": 1,
                        }
                    ],
                    "levels": [
                        {"value": 70, "color": _THEME["red"], "label": "70"},
                        {"value": 50, "color": _THEME["dim"], "label": "50"},
                        {"value": 30, "color": _THEME["green"], "label": "30"},
                    ],
                    "scale": {"min": 0, "max": 100},
                }
            )

        elif kind == "macd":
            m = _compute_macd(bars, cfg["fast"], cfg["slow"], cfg["signal"])
            sub_panes.append(
                {
                    "id": "macd",
                    "label": cfg["label"],
                    "height": cfg["height"],
                    "type": "macd",
                    "series": [
                        {
                            "type": "histogram",
                            "label": "Hist",
                            "data": m["hist"],
                            "color": _THEME["blue"],  # per-bar color in data takes precedence
                        },
                        {
                            "type": "line",
                            "label": "MACD",
                            "data": m["macd"],
                            "color": _THEME["cyan"],
                            "width": 1,
                        },
                        {
                            "type": "line",
                            "label": "Signal",
                            "data": m["signal"],
                            "color": _THEME["amber"],
                            "width": 1,
                        },
                    ],
                    "levels": [
                        {"value": 0, "color": _THEME["dim"], "label": "0"},
                    ],
                }
            )

        elif kind == "atr":
            data = _compute_atr(bars, cfg["period"])
            sub_panes.append(
                {
                    "id": "atr",
                    "label": cfg["label"],
                    "height": cfg["height"],
                    "type": "atr",
                    "series": [
                        {
                            "type": "line",
                            "label": "ATR",
                            "data": data,
                            "color": _THEME["cyan"],
                            "width": 1,
                        }
                    ],
                    "levels": [],
                }
            )

        elif kind == "cvd":
            data = _compute_cvd(bars)
            sub_panes.append(
                {
                    "id": "cvd",
                    "label": cfg["label"],
                    "height": cfg["height"],
                    "type": "cvd",
                    "series": [
                        {
                            "type": "histogram",
                            "label": "CVD",
                            "data": data,
                            "color": _THEME["green"],  # per-bar color in data takes precedence
                        }
                    ],
                    "levels": [
                        {"value": 0, "color": _THEME["dim"], "label": "0"},
                    ],
                }
            )

    return sub_panes


# ---------------------------------------------------------------------------
# HTML template
# ---------------------------------------------------------------------------

_CDN_TEMPLATE = """\
<!doctype html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>{symbol} {timeframe} — FKS</title>
<script src="https://cdn.jsdelivr.net/npm/lightweight-charts@4.2.0/dist/lightweight-charts.standalone.production.js"></script>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
html,body{{height:100%;background:{bg};color:{text};font-family:'JetBrains Mono','Fira Code',ui-monospace,monospace;font-size:12px;overflow:hidden}}

/* ── Layout ── */
#root{{display:flex;flex-direction:column;height:100vh}}
#header{{height:36px;flex-shrink:0;display:flex;align-items:center;gap:10px;padding:0 12px;
         background:{card};border-bottom:1px solid {border}}}
#charts-wrap{{flex:1;display:flex;flex-direction:column;overflow:hidden;min-height:0}}
.pane-wrap{{flex-shrink:0;position:relative;border-top:1px solid {border}}}
.pane-wrap:first-child{{flex:1;min-height:0;border-top:none}}
.pane-label{{position:absolute;top:4px;left:8px;z-index:10;font-size:9px;font-weight:600;
             text-transform:uppercase;letter-spacing:.06em;color:{dim};pointer-events:none}}
.pane-div{{width:100%;height:100%}}
.price-wrap{{flex:1;min-height:0;position:relative}}
.price-div{{width:100%;height:100%}}

/* ── Header atoms ── */
.sym{{font-weight:700;font-size:13px;color:{text}}}
.tf{{font-size:10px;color:{dim};padding:2px 7px;border-radius:4px;background:rgba(255,255,255,0.05)}}
.last-price{{font-size:12px;font-weight:600;margin-left:auto}}
.up{{color:{green}}}.dn{{color:{red}}}

/* ── Legend ── */
#legend{{position:absolute;top:6px;right:8px;z-index:10;display:flex;flex-wrap:wrap;
         gap:6px;pointer-events:none;max-width:220px;justify-content:flex-end}}
.leg{{font-size:9px;padding:1px 6px;border-radius:3px;background:rgba(0,0,0,0.55);font-weight:600}}

/* ── MACD legend in sub-pane ── */
.sub-legend{{position:absolute;top:4px;right:8px;z-index:10;display:flex;gap:6px;pointer-events:none}}
.sub-leg{{font-size:9px;padding:1px 5px;border-radius:3px;background:rgba(0,0,0,0.55)}}
</style>
</head>
<body>
<div id="root">

  <!-- ── Header ── -->
  <div id="header">
    <span class="sym">{symbol}</span>
    <span class="tf">{timeframe}</span>
    <span class="last-price" id="last-price">—</span>
  </div>

  <!-- ── Charts ── -->
  <div id="charts-wrap">

    <!-- Price pane (flex-1, fills remaining height) -->
    <div class="price-wrap" id="price-wrap" style="position:relative">
      <div class="price-div" id="chart-price"></div>
      <div id="legend"></div>
    </div>

    <!-- Sub-panes (injected by JS below) -->

  </div>

</div><!-- /#root -->

<script>
'use strict';
// ═══════════════════════════════════════════════════════════════════════════
// Data (injected by Python)
// ═══════════════════════════════════════════════════════════════════════════
const SYMBOL    = {symbol_json};
const TIMEFRAME = {timeframe_json};
const BARS      = {bars_json};
const OVERLAYS  = {overlays_json};
const SUB_PANES = {sub_panes_json};
const T         = {theme_json};

// ═══════════════════════════════════════════════════════════════════════════
// Helpers
// ═══════════════════════════════════════════════════════════════════════════
const LW = window.LightweightCharts;

function baseOpts(bg) {{
  return {{
    layout: {{
      background: {{ type: 'solid', color: bg || T.bg }},
      textColor:  T.text,
      fontFamily: "'JetBrains Mono','Fira Code',ui-monospace,monospace",
      fontSize:   10,
    }},
    grid: {{
      vertLines: {{ color: T.border }},
      horzLines: {{ color: T.border }},
    }},
    crosshair: {{ mode: LW.CrosshairMode.Normal }},
    rightPriceScale: {{ borderColor: T.border }},
    timeScale: {{
      borderColor:               T.border,
      timeVisible:               true,
      secondsVisible:            false,
      fixLeftEdge:               false,
      fixRightEdge:              false,
      lockVisibleTimeRangeOnResize: true,
    }},
    handleScroll:  {{ mouseWheel: true, pressedMouseMove: true }},
    handleScale:   {{ mouseWheel: true, pinch: true, axisPressedMouseMove: true }},
  }};
}}

// ═══════════════════════════════════════════════════════════════════════════
// Pane creation helpers
// ═══════════════════════════════════════════════════════════════════════════

function addPaneDiv(id, height, label) {{
  const wrap = document.createElement('div');
  wrap.className = 'pane-wrap';
  wrap.style.height = height + 'px';
  wrap.id = 'wrap-' + id;

  const lbl = document.createElement('div');
  lbl.className = 'pane-label';
  lbl.textContent = label;
  wrap.appendChild(lbl);

  const div = document.createElement('div');
  div.className = 'pane-div';
  div.id = 'chart-' + id;
  div.style.height = height + 'px';
  wrap.appendChild(div);

  document.getElementById('charts-wrap').appendChild(wrap);
  return div;
}}

function addSeries(chart, spec) {{
  const lineOpts = {{
    lineWidth:             spec.width || 1,
    color:                 spec.color,
    lineStyle:             spec.dashed ? LW.LineStyle.Dashed : LW.LineStyle.Solid,
    priceLineVisible:      false,
    lastValueVisible:      false,
    crosshairMarkerVisible:false,
  }};
  let series;
  if (spec.type === 'histogram') {{
    series = chart.addHistogramSeries({{
      color:             spec.color,
      priceLineVisible:  false,
      lastValueVisible:  false,
      priceScaleId:      spec.scaleId || 'right',
    }});
  }} else {{
    series = chart.addLineSeries(lineOpts);
  }}
  if (spec.data && spec.data.length) series.setData(spec.data);
  return series;
}}

function addLevels(series, levels) {{
  if (!levels || !series) return;
  levels.forEach(function(l) {{
    series.createPriceLine({{
      price:             l.value,
      color:             l.color,
      lineWidth:         1,
      lineStyle:         LW.LineStyle.Dashed,
      axisLabelVisible:  true,
      title:             l.label || '',
    }});
  }});
}}

// ═══════════════════════════════════════════════════════════════════════════
// Build the legend
// ═══════════════════════════════════════════════════════════════════════════
function buildLegend() {{
  const el = document.getElementById('legend');
  OVERLAYS.forEach(function(ov) {{
    const d = document.createElement('div');
    d.className = 'leg';
    d.style.color = ov.color;
    d.textContent = ov.label;
    el.appendChild(d);
  }});
}}

// ═══════════════════════════════════════════════════════════════════════════
// Time-scale synchronisation
// ═══════════════════════════════════════════════════════════════════════════
var _syncing = false;
var _allCharts = [];

function syncRange(sourceChart, range) {{
  if (_syncing || !range) return;
  _syncing = true;
  _allCharts.forEach(function(c) {{
    if (c !== sourceChart) {{
      try {{ c.timeScale().setVisibleLogicalRange(range); }} catch(e) {{}}
    }}
  }});
  _syncing = false;
}}

function syncCrosshair(sourceChart, param) {{
  if (!param.point || !param.time) return;
  var srcTs = sourceChart.timeScale();
  var x = srcTs.timeToCoordinate(param.time);
  if (x === null) return;
  _allCharts.forEach(function(c) {{
    if (c === sourceChart) return;
    try {{
      var ts = c.timeScale();
      var logical = ts.coordinateToLogical(x);
      if (logical !== null) {{
        // Move the crosshair to the same logical position
        // (setCrosshairPosition is available in LW Charts 4.x)
        var primarySeries = c.__primarySeries;
        if (!primarySeries) return;
        var coord = c.timeScale().logicalToCoordinate(logical);
        if (coord === null) return;
        var price = primarySeries.coordinateToPrice(param.point.y);
        if (price !== null) {{
          c.setCrosshairPosition(price, param.time, primarySeries);
        }}
      }}
    }} catch(e) {{}}
  }});
}}

function wireSync() {{
  _allCharts.forEach(function(c) {{
    c.timeScale().subscribeVisibleLogicalRangeChange(function(range) {{
      syncRange(c, range);
    }});
    c.subscribeCrosshairMove(function(param) {{
      syncCrosshair(c, param);
    }});
  }});
}}

// ═══════════════════════════════════════════════════════════════════════════
// ResizeObserver — keep chart sized to its container
// ═══════════════════════════════════════════════════════════════════════════
function observeResize(el, chart) {{
  var ro = new ResizeObserver(function(entries) {{
    var entry = entries[0];
    if (!entry) return;
    var w = Math.floor(entry.contentRect.width);
    var h = Math.floor(entry.contentRect.height);
    if (w > 0 && h > 0) chart.resize(w, h);
  }});
  ro.observe(el);
}}

// ═══════════════════════════════════════════════════════════════════════════
// Boot
// ═══════════════════════════════════════════════════════════════════════════
(function boot() {{

  // ── Price pane ───────────────────────────────────────────────────────────
  var priceEl = document.getElementById('chart-price');
  var priceChart = LW.createChart(priceEl, Object.assign(baseOpts(T.bg), {{
    width:  priceEl.clientWidth  || 800,
    height: priceEl.clientHeight || 400,
  }}));

  var candleSeries = priceChart.addCandlestickSeries({{
    upColor:         T.green,
    downColor:       T.red,
    borderUpColor:   T.green,
    borderDownColor: T.red,
    wickUpColor:     T.green,
    wickDownColor:   T.red,
  }});
  if (BARS.length) candleSeries.setData(BARS);
  priceChart.__primarySeries = candleSeries;

  // Volume bars (overlay on price pane, 15% of scale)
  var volSeries = priceChart.addHistogramSeries({{
    color:            T.vol_up,
    priceFormat:      {{ type: 'volume' }},
    priceScaleId:     'vol',
    lastValueVisible: false,
    priceLineVisible: false,
  }});
  priceChart.priceScale('vol').applyOptions({{
    scaleMargins: {{ top: 0.85, bottom: 0.0 }},
  }});
  var volData = BARS.map(function(b) {{
    return {{
      time:  b.time,
      value: b.volume || 0,
      color: b.close >= b.open ? T.vol_up : T.vol_dn,
    }};
  }});
  volSeries.setData(volData);

  // Overlays
  OVERLAYS.forEach(function(ov) {{
    var s = priceChart.addLineSeries({{
      color:                  ov.color,
      lineWidth:              ov.width || 1,
      lineStyle:              ov.dashed ? LW.LineStyle.Dashed : LW.LineStyle.Solid,
      priceLineVisible:       false,
      lastValueVisible:       false,
      crosshairMarkerVisible: false,
    }});
    if (ov.data && ov.data.length) s.setData(ov.data);
  }});

  _allCharts.push(priceChart);
  observeResize(priceEl, priceChart);

  // ── Sub-panes ────────────────────────────────────────────────────────────
  SUB_PANES.forEach(function(pane) {{
    var paneEl = addPaneDiv(pane.id, pane.height, pane.label);

    var opts = Object.assign(baseOpts(T.card), {{
      width:           paneEl.clientWidth  || 800,
      height:          pane.height,
      leftPriceScale:  {{ visible: false }},
      rightPriceScale: {{ borderColor: T.border, scaleMargins: {{ top: 0.1, bottom: 0.1 }} }},
      timeScale:       Object.assign({{
        borderColor:  T.border,
        timeVisible:  false,
        visible:      false,
      }}),
    }});
    // hide the time scale on sub-panes (share with main)
    var subChart = LW.createChart(paneEl, opts);
    subChart.timeScale().applyOptions({{ visible: false }});

    var primarySeries = null;

    // RSI: fixed 0–100 scale
    if (pane.type === 'rsi' && pane.scale) {{
      subChart.priceScale('right').applyOptions({{
        autoScale:    false,
        minimum:      pane.scale.min,
        maximum:      pane.scale.max,
      }});
    }}

    // Add each series in this pane
    pane.series.forEach(function(spec, idx) {{
      var s = addSeries(subChart, spec);
      if (idx === 0) {{
        primarySeries = s;
        subChart.__primarySeries = s;
        // Attach price lines (levels) to the first series
        addLevels(s, pane.levels);
      }}
    }});

    // Build sub-legend for multi-series panes (MACD)
    if (pane.series.length > 1) {{
      var subLegend = document.createElement('div');
      subLegend.className = 'sub-legend';
      var wrapEl = document.getElementById('wrap-' + pane.id);
      if (wrapEl) {{
        pane.series.forEach(function(spec) {{
          if (spec.type === 'histogram') return;
          var el = document.createElement('div');
          el.className = 'sub-leg';
          el.style.color = spec.color;
          el.textContent = spec.label || '';
          subLegend.appendChild(el);
        }});
        wrapEl.appendChild(subLegend);
      }}
    }}

    _allCharts.push(subChart);
    observeResize(paneEl, subChart);
  }});

  // ── Sync ─────────────────────────────────────────────────────────────────
  wireSync();

  // Fit price pane content on load
  priceChart.timeScale().fitContent();

  // ── Last-price header ─────────────────────────────────────────────────────
  var lastBar = BARS.length ? BARS[BARS.length - 1] : null;
  if (lastBar) {{
    var disp = document.getElementById('last-price');
    var fmt  = lastBar.close >= lastBar.open ? 'up' : 'dn';
    disp.textContent = lastBar.close.toFixed(lastBar.close < 10 ? 4 : 2);
    disp.className   = 'last-price ' + fmt;
  }}

  priceChart.subscribeCrosshairMove(function(param) {{
    if (!param.seriesData || !param.seriesData.size) return;
    var bar = param.seriesData.get(candleSeries);
    if (!bar) return;
    var disp = document.getElementById('last-price');
    disp.textContent = bar.close.toFixed(bar.close < 10 ? 4 : 2);
    disp.className   = 'last-price ' + (bar.close >= bar.open ? 'up' : 'dn');
  }});

  // ── Build legend ──────────────────────────────────────────────────────────
  buildLegend();

}}());
</script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# HTML builder
# ---------------------------------------------------------------------------


def _build_cdn_chart(
    symbol: str,
    timeframe: str,
    bars: list[dict[str, Any]],
    indicators: list[str],
) -> str:
    """Render the multi-pane CDN chart HTML."""
    overlays = _build_overlays(bars, indicators)
    sub_panes = _build_sub_panes(bars, indicators)

    return _CDN_TEMPLATE.format(
        symbol=symbol,
        timeframe=timeframe,
        symbol_json=json.dumps(symbol),
        timeframe_json=json.dumps(timeframe),
        bars_json=json.dumps(bars),
        overlays_json=json.dumps(overlays),
        sub_panes_json=json.dumps(sub_panes),
        theme_json=json.dumps(_THEME),
        **_THEME,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def generate_chart_html(
    symbol: str,
    timeframe: str = "5m",
    indicators: list[str] | None = None,
    df: Any | None = None,
    limit: int = 500,
) -> str:
    """Generate a self-contained multi-pane chart HTML page.

    Parameters
    ----------
    symbol:
        Instrument symbol, e.g. ``"MES"``, ``"BTCUSD"``.
    timeframe:
        Timeframe string matching stored bar keys, e.g. ``"5m"``, ``"1h"``.
    indicators:
        Indicator keys from ``_INDICATOR_CONFIG``.  Unknown keys are silently
        ignored.  Example::

            ["ema_9", "ema_20", "bb", "vwap", "rsi_14", "macd", "cvd"]

    df:
        Optional ``pandas.DataFrame`` with columns ``time, open, high, low,
        close, volume``.  When supplied, skips the Redis/Postgres lookup.
    limit:
        Maximum bars to fetch / display (default 500).

    Returns
    -------
    str
        Complete ``<!doctype html>`` document.
    """
    if indicators is None:
        indicators = []

    # Resolve OHLCV data
    if df is not None:
        try:
            bars: list[dict[str, Any]] = df[["time", "open", "high", "low", "close", "volume"]].to_dict("records")
            bars = [{k: (int(v) if k == "time" else float(v)) for k, v in b.items()} for b in bars]
        except Exception as exc:
            logger.warning("dataframe_conversion_failed", error=str(exc))
            bars = await asyncio.to_thread(_get_ohlcv, symbol, timeframe, limit)
    else:
        bars = await asyncio.to_thread(_get_ohlcv, symbol, timeframe, limit)

    # Filter to known indicator keys
    valid = [k for k in indicators if k in _INDICATOR_CONFIG]
    unknown = [k for k in indicators if k not in _INDICATOR_CONFIG]
    if unknown:
        logger.warning("unknown_indicators_ignored", keys=unknown)

    html = _build_cdn_chart(symbol, timeframe, bars, valid)

    logger.info(
        "chart_generated",
        symbol=symbol,
        timeframe=timeframe,
        bars=len(bars),
        indicators=valid,
    )
    return html


async def get_ohlcv_json(
    symbol: str,
    timeframe: str = "5m",
    limit: int = 500,
) -> dict[str, Any]:
    """Return OHLCV bars as a JSON-serialisable dict.

    Used by ``GET /api/tv/chart/{symbol}/data`` for client-side rendering.
    """
    bars = await asyncio.to_thread(_get_ohlcv, symbol, timeframe, limit)
    return {"symbol": symbol, "timeframe": timeframe, "bars": bars, "count": len(bars)}


# Expose the full indicator registry so tv_charts.py can read valid keys
VALID_INDICATOR_KEYS: frozenset[str] = frozenset(_INDICATOR_CONFIG)


__all__ = [
    "generate_chart_html",
    "get_ohlcv_json",
    "VALID_INDICATOR_KEYS",
    # Computation functions — exported for testing / external use
    "_compute_sma",
    "_compute_ema",
    "_compute_rsi",
    "_compute_macd",
    "_compute_atr",
    "_compute_cvd",
    "_compute_bb",
    "_compute_vwap",
]
