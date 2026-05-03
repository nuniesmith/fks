/// End-to-end tests for the full `compute_signal` pipeline.
///
/// Covers:
/// - Batch `SignalIndicator` API (columns, domain checks, required length)
/// - Per-bar `compute_signal` (warm-up gating, VWAP vote correctness)
/// - "any" mode fires at least one long signal on a sustained uptrend
/// - `SignalStreak` confirmation filter (required count, direction reset, zero handling)
mod common;

use indicators::{
    ConfluenceEngine, IndicatorConfig, Indicators, LiquidityProfile, MarketStructure,
    SignalIndicator, SignalStreak, compute_signal, indicator::Indicator, signal::cvd::CVDTracker,
    signal::vol_regime::VolatilityPercentile, types::Candle,
};

const EPS: f64 = 1e-9;

// ── Candle helpers ────────────────────────────────────────────────────────────

/// Generate `n` candles on a smooth uptrend starting at `base`.
/// Each bar: close rises by 0.5, body width 0.4, wick 0.3 each side.
fn rising_candles(n: usize, base: f64) -> Vec<Candle> {
    (0..n)
        .map(|i| {
            let c = base + i as f64 * 0.5;
            Candle {
                time: i as i64 * 60_000, // 1-minute bars, same UTC date
                open: c - 0.2,
                high: c + 0.3,
                low: c - 0.3,
                close: c,
                volume: 1_000.0 + (i % 10) as f64 * 50.0,
            }
        })
        .collect()
}

/// Generate `n` candles on a smooth downtrend starting at `base`.
fn falling_candles(n: usize, base: f64) -> Vec<Candle> {
    (0..n)
        .map(|i| {
            let c = base - i as f64 * 0.5;
            Candle {
                time: i as i64 * 60_000,
                open: c + 0.2,
                high: c + 0.3,
                low: c - 0.3,
                close: c,
                volume: 1_000.0 + (i % 10) as f64 * 50.0,
            }
        })
        .collect()
}

// ── Build default streaming sub-components ────────────────────────────────────

fn default_streaming() -> (
    Indicators,
    LiquidityProfile,
    ConfluenceEngine,
    MarketStructure,
    CVDTracker,
    VolatilityPercentile,
) {
    // Mirrors the construction inside SignalIndicator::calculate().
    (
        Indicators::new(IndicatorConfig::default()),
        LiquidityProfile::new(50, 20),
        ConfluenceEngine::new(8, 21, 50, 14, 14),
        MarketStructure::new(5, 0.5),
        CVDTracker::new(10, 20),
        VolatilityPercentile::new(100),
    )
}

// ── Column presence ───────────────────────────────────────────────────────────

#[test]
fn signal_indicator_emits_three_columns() {
    let candles = rising_candles(120, 100.0);
    let out = SignalIndicator::with_defaults()
        .calculate(&candles)
        .expect("calculate should succeed with 120 candles");

    assert!(out.get("signal").is_some(), "missing 'signal' column");
    assert!(
        out.get("signal_bull_score").is_some(),
        "missing 'signal_bull_score' column"
    );
    assert!(
        out.get("signal_bear_score").is_some(),
        "missing 'signal_bear_score' column"
    );
}

// ── Required length ───────────────────────────────────────────────────────────

#[test]
fn signal_indicator_required_len_is_100() {
    // training_period=100 dominates all other warm-up requirements.
    assert_eq!(SignalIndicator::with_defaults().required_len(), 100);
}

#[test]
fn signal_indicator_insufficient_data_returns_error() {
    // 50 bars is below the 100-bar training_period warm-up requirement.
    let candles = rising_candles(50, 100.0);
    let result = SignalIndicator::with_defaults().calculate(&candles);
    assert!(
        result.is_err(),
        "expected Err(InsufficientData) for {} candles < required_len",
        candles.len()
    );
}

// ── Value domain ──────────────────────────────────────────────────────────────

#[test]
fn signal_column_values_are_valid() {
    let candles = rising_candles(150, 100.0);
    let out = SignalIndicator::with_defaults()
        .calculate(&candles)
        .unwrap();
    let signal = out.get("signal").unwrap();

    for (i, &v) in signal.iter().enumerate() {
        if !v.is_nan() {
            assert!(
                v == -1.0 || v == 0.0 || v == 1.0,
                "signal[{i}] = {v} — must be −1, 0, or +1"
            );
        }
    }
}

#[test]
fn bull_bear_scores_are_non_negative() {
    let candles = rising_candles(150, 100.0);
    let out = SignalIndicator::with_defaults()
        .calculate(&candles)
        .unwrap();

    for col in &["signal_bull_score", "signal_bear_score"] {
        for (i, &v) in out.get(col).unwrap().iter().enumerate() {
            if !v.is_nan() {
                assert!(
                    v >= 0.0,
                    "{col}[{i}] = {v} is negative — scores must be ≥ 0"
                );
            }
        }
    }
}

#[test]
fn output_length_matches_input_length() {
    let candles = rising_candles(150, 100.0);
    let n = candles.len();
    let out = SignalIndicator::with_defaults()
        .calculate(&candles)
        .unwrap();

    for col in &["signal", "signal_bull_score", "signal_bear_score"] {
        assert_eq!(
            out.get(col).unwrap().len(),
            n,
            "{col} length mismatch: expected {n}"
        );
    }
}

// ── Per-bar compute_signal ────────────────────────────────────────────────────

#[test]
fn compute_signal_returns_zero_before_engine_ready() {
    let (mut ind, mut liq, mut conf, mut ms, mut cvd, vol) = default_streaming();
    let cfg = IndicatorConfig::default();

    // Feed just one candle — engine has no SuperTrend yet.
    let c = Candle {
        time: 0,
        open: 100.0,
        high: 101.0,
        low: 99.0,
        close: 100.0,
        volume: 1_000.0,
    };
    ind.update(&c);
    liq.update(&c);
    conf.update(&c);
    ms.update(&c);
    cvd.update(&c);

    let (raw, _comps) = compute_signal(
        c.close,
        &ind,
        &liq,
        &conf,
        &ms,
        &cfg,
        Some(&cvd),
        Some(&vol),
    );
    assert_eq!(
        raw, 0,
        "compute_signal must return 0 before SuperTrend is available"
    );
}

#[test]
fn compute_signal_vwap_vote_is_bullish_on_rising_series() {
    let (mut ind, mut liq, mut conf, mut ms, mut cvd, mut vol) = default_streaming();
    let cfg = IndicatorConfig::default();

    // Feed enough bars so the engine has a SuperTrend (training_period = 100).
    let candles = rising_candles(105, 100.0);
    for c in &candles {
        ind.update(c);
        liq.update(c);
        conf.update(c);
        ms.update(c);
        cvd.update(c);
        vol.update(ind.atr);
    }

    let last = candles.last().unwrap();
    let (_raw, comps) = compute_signal(
        last.close,
        &ind,
        &liq,
        &conf,
        &ms,
        &cfg,
        Some(&cvd),
        Some(&vol),
    );

    // On a monotonically rising same-day series, close should be above VWAP.
    assert_eq!(
        comps.v_vwap, 1,
        "expected bullish VWAP vote (close > VWAP) on a 105-bar uptrend"
    );
}

#[test]
fn compute_signal_vwap_vote_is_bearish_on_falling_series() {
    let (mut ind, mut liq, mut conf, mut ms, mut cvd, mut vol) = default_streaming();
    let cfg = IndicatorConfig::default();

    // Start high so prices stay positive across a 105-bar fall.
    let candles = falling_candles(105, 200.0);
    for c in &candles {
        ind.update(c);
        liq.update(c);
        conf.update(c);
        ms.update(c);
        cvd.update(c);
        vol.update(ind.atr);
    }

    let last = candles.last().unwrap();
    let (_raw, comps) = compute_signal(
        last.close,
        &ind,
        &liq,
        &conf,
        &ms,
        &cfg,
        Some(&cvd),
        Some(&vol),
    );

    // On a monotonically falling same-day series, close should be below VWAP.
    assert_eq!(
        comps.v_vwap, -1,
        "expected bearish VWAP vote (close < VWAP) on a 105-bar downtrend"
    );
}

// ── "any" mode fires on core-aligned uptrend ──────────────────────────────────

#[test]
fn any_mode_fires_at_least_one_long_signal_on_uptrend() {
    // "any" mode only requires the 4 core layers to agree; confirm_bars=1 removes
    // the streak filter so we can see any firing bar.
    let si = SignalIndicator {
        engine_cfg: IndicatorConfig {
            signal_mode: "any".into(),
            signal_confirm_bars: 1,
            ..IndicatorConfig::default()
        },
        conf_params: Default::default(),
        liq_params: Default::default(),
        struct_params: Default::default(),
        cvd_params: Default::default(),
        signal_confirm_bars: 1,
    };

    let candles = rising_candles(200, 50.0);
    let out = si.calculate(&candles).unwrap();
    let signal = out.get("signal").unwrap();

    let any_long = signal.iter().any(|&v| (v - 1.0).abs() < EPS);
    assert!(
        any_long,
        "expected ≥1 long signal (+1) on a 200-bar rising series in 'any' mode"
    );
}

#[test]
fn any_mode_fires_at_least_one_short_signal_on_downtrend() {
    let si = SignalIndicator {
        engine_cfg: IndicatorConfig {
            signal_mode: "any".into(),
            signal_confirm_bars: 1,
            ..IndicatorConfig::default()
        },
        conf_params: Default::default(),
        liq_params: Default::default(),
        struct_params: Default::default(),
        cvd_params: Default::default(),
        signal_confirm_bars: 1,
    };

    // Start high so prices stay positive.
    let candles = falling_candles(200, 500.0);
    let out = si.calculate(&candles).unwrap();
    let signal = out.get("signal").unwrap();

    let any_short = signal.iter().any(|&v| (v + 1.0).abs() < EPS);
    assert!(
        any_short,
        "expected ≥1 short signal (−1) on a 200-bar falling series in 'any' mode"
    );
}

// ── SignalStreak ───────────────────────────────────────────────────────────────

#[test]
fn signal_streak_does_not_fire_before_required_bars() {
    let mut streak = SignalStreak::new(3);
    assert!(!streak.update(1), "bar 1/3");
    assert!(!streak.update(1), "bar 2/3");
    assert!(streak.update(1), "bar 3/3 — should fire");
}

#[test]
fn signal_streak_continues_to_fire_after_reaching_required() {
    let mut streak = SignalStreak::new(2);
    assert!(!streak.update(1), "bar 1");
    assert!(streak.update(1), "bar 2 — fires");
    assert!(streak.update(1), "bar 3 — still fires");
    assert!(streak.update(1), "bar 4 — still fires");
}

#[test]
fn signal_streak_resets_on_direction_change() {
    let mut streak = SignalStreak::new(2);
    assert!(!streak.update(1), "1 bull");
    // Flip to bear — count resets.
    assert!(
        !streak.update(-1),
        "first bear after reset — should not fire"
    );
    assert!(streak.update(-1), "second consecutive bear — fires");
}

#[test]
fn signal_streak_zero_never_fires() {
    let mut streak = SignalStreak::new(1);
    assert!(!streak.update(0), "neutral bar");
    assert!(!streak.update(0), "still neutral");
    // Even after a run of zeros, a single non-zero should need required=1 bars.
    assert!(
        streak.update(1),
        "non-zero after zeros fires immediately (required=1)"
    );
}

#[test]
fn signal_streak_required_one_fires_immediately() {
    let mut streak = SignalStreak::new(1);
    assert!(streak.update(1), "required=1, first bull fires");
    assert!(streak.update(-1), "required=1, first bear after flip fires");
}

#[test]
fn signal_streak_reset_clears_state() {
    let mut streak = SignalStreak::new(2);
    assert!(!streak.update(1));
    assert!(streak.update(1)); // streak = 2, fires
    streak.reset();
    // After reset we need 2 more bars.
    assert!(!streak.update(1), "bar 1 after reset");
    assert!(streak.update(1), "bar 2 after reset — fires again");
}
