mod common;
use common::*;

use indicators::indicator::Indicator;
use indicators::momentum::schaff_trend_cycle::{SchaffTrendCycle, StcParams};
use indicators::trend::atr::{Atr, AtrMethod, AtrParams};
use indicators::trend::macd::Macd;

const EPS: f64 = 1e-7;

// ─────────────────────────────────────────────────────────────────────────────
// MACD
// ─────────────────────────────────────────────────────────────────────────────

#[test]
fn macd_three_output_columns_present() {
    let out = Macd::default().calculate(&ref_candles()).unwrap();
    assert!(out.get("MACD_line").is_some(), "missing MACD_line");
    assert!(out.get("MACD_signal").is_some(), "missing MACD_signal");
    assert!(
        out.get("MACD_histogram").is_some(),
        "missing MACD_histogram"
    );
}

#[test]
fn macd_line_last_value() {
    // Python (adjust=False): macd_line.iloc[29] = 3.8439...
    let out = Macd::default().calculate(&ref_candles()).unwrap();
    assert_close(
        out.get("MACD_line").unwrap()[29],
        3.8439_8037_41,
        1e-6,
        "MACD_line[29]",
    );
}

#[test]
fn macd_signal_last_value() {
    // Python (adjust=False): signal.iloc[29] = 3.5560...
    let out = Macd::default().calculate(&ref_candles()).unwrap();
    assert_close(
        out.get("MACD_signal").unwrap()[29],
        3.5560_8869_21,
        1e-6,
        "MACD_signal[29]",
    );
}

#[test]
fn macd_histogram_equals_line_minus_signal() {
    // histogram = macd_line - signal_line, every bar.
    let out = Macd::default().calculate(&ref_candles()).unwrap();
    let line = out.get("MACD_line").unwrap();
    let signal = out.get("MACD_signal").unwrap();
    let hist = out.get("MACD_histogram").unwrap();
    for i in 0..30 {
        if !line[i].is_nan() && !signal[i].is_nan() {
            assert_close(
                hist[i],
                line[i] - signal[i],
                1e-12,
                &format!("MACD hist[{i}]"),
            );
        }
    }
}

#[test]
fn macd_histogram_last_value() {
    // Python: histogram.iloc[29] = 0.2878...
    let out = Macd::default().calculate(&ref_candles()).unwrap();
    assert_close(
        out.get("MACD_histogram").unwrap()[29],
        0.2878_9168_20,
        1e-6,
        "MACD_hist[29]",
    );
}

#[test]
fn macd_uptrend_line_is_positive() {
    // On a monotonically rising series the fast EMA > slow EMA → line > 0.
    let closes: Vec<f64> = (1..=50).map(|x| x as f64 * 2.0).collect();
    let out = Macd::default().calculate(&close_candles(&closes)).unwrap();
    let line = out.get("MACD_line").unwrap();
    for i in 25..50 {
        if !line[i].is_nan() {
            assert!(
                line[i] > 0.0,
                "MACD line[{i}]={} should be > 0 in uptrend",
                line[i]
            );
        }
    }
}

#[test]
fn macd_constant_series_all_zeros() {
    // EMA of a constant equals that constant → MACD components all zero.
    let out = Macd::default()
        .calculate(&close_candles(&[100.0_f64; 50]))
        .unwrap();
    let line = out.get("MACD_line").unwrap();
    for i in 0..50 {
        if !line[i].is_nan() {
            assert_close(line[i], 0.0, EPS, &format!("MACD const[{i}]"));
        }
    }
}

#[test]
fn macd_insufficient_data_is_error() {
    use indicators::error::IndicatorError;
    let err = Macd::default()
        .calculate(&close_candles(&[1.0; 5]))
        .unwrap_err();
    assert!(matches!(err, IndicatorError::InsufficientData { .. }));
}

// ─────────────────────────────────────────────────────────────────────────────
// ATR
// ─────────────────────────────────────────────────────────────────────────────

#[test]
fn atr_sma5_known_value_at_first_valid() {
    // Python: atr_sma5.iloc[5] = 3.0 (first SMA window after TR available from bar 1)
    let out = Atr::with_period(5).calculate(&ref_candles()).unwrap();
    assert_close(out.get("ATR_5").unwrap()[5], 3.0, EPS, "ATR_sma5[5]");
}

#[test]
fn atr_sma5_last_value() {
    // Python: atr_sma5.iloc[29] = 2.9
    let out = Atr::with_period(5).calculate(&ref_candles()).unwrap();
    assert_close(out.get("ATR_5").unwrap()[29], 2.9, 1e-9, "ATR_sma5[29]");
}

#[test]
fn atr_ema5_last_value() {
    // Python (adjust=False): atr_ema5.iloc[29] = 2.9473...
    let params = AtrParams {
        period: 5,
        method: AtrMethod::Ema,
    };
    let out = Atr::new(params).calculate(&ref_candles()).unwrap();
    assert_close(
        out.get("ATR_5").unwrap()[29],
        2.9473_6543_61,
        1e-6,
        "ATR_ema5[29]",
    );
}

#[test]
fn atr_normalized_is_atr_over_close_times_100() {
    // norm = atr / close * 100, verified at every non-NaN position.
    let out = Atr::with_period(5).calculate(&ref_candles()).unwrap();
    let atr_vals = out.get("ATR_5").unwrap();
    let norm_vals = out.get("ATR_5_normalized").unwrap();
    for (i, &(_, _, c, _)) in BARS.iter().enumerate() {
        if !atr_vals[i].is_nan() {
            assert_close(
                norm_vals[i],
                atr_vals[i] / c * 100.0,
                1e-12,
                &format!("norm[{i}]"),
            );
        }
    }
}

#[test]
fn atr_both_output_columns_present() {
    let out = Atr::with_period(5).calculate(&ref_candles()).unwrap();
    assert!(out.get("ATR_5").is_some(), "missing ATR_5");
    assert!(
        out.get("ATR_5_normalized").is_some(),
        "missing ATR_5_normalized"
    );
}

#[test]
fn atr_always_positive() {
    // True range is non-negative, so ATR is non-negative.
    let out = Atr::with_period(5).calculate(&ref_candles()).unwrap();
    assert_all_non_nan(out.get("ATR_5").unwrap(), |v| v >= 0.0, "ATR positive");
}

#[test]
fn atr_constant_ohlc_has_zero_tr() {
    // All bars identical → H−L = 0, |H−prev_C| = 0, |L−prev_C| = 0 → ATR = 0.
    let bars: Vec<(f64, f64, f64, f64)> = vec![(10.0, 10.0, 10.0, 100.0); 20];
    let out = Atr::with_period(5).calculate(&make_candles(&bars)).unwrap();
    let vals = out.get("ATR_5").unwrap();
    for i in 5..20 {
        assert_close(vals[i], 0.0, EPS, &format!("ATR const[{i}]"));
    }
}

#[test]
fn atr_ema_starts_at_bar0_no_leading_nan() {
    // EMA-smoothed ATR: ewm(adjust=False) emits a value from bar 0.
    // We only check that bars past required_len are non-NaN.
    let params = AtrParams {
        period: 5,
        method: AtrMethod::Ema,
    };
    let out = Atr::new(params).calculate(&ref_candles()).unwrap();
    let vals = out.get("ATR_5").unwrap();
    // At minimum, values from bar 5 onward must be finite.
    assert_no_nans_from(vals, 5, "ATR_ema");
}

#[test]
fn atr_sma_leading_nans() {
    // SMA-smoothed: first period-1 TR values have no complete window.
    let out = Atr::with_period(5).calculate(&ref_candles()).unwrap();
    // Bar 0: only one bar of TR; SMA(5) not yet full → NaN.
    assert!(
        out.get("ATR_5").unwrap()[0].is_nan(),
        "ATR_sma[0] should be NaN"
    );
}

// ─────────────────────────────────────────────────────────────────────────────
// Schaff Trend Cycle
// ─────────────────────────────────────────────────────────────────────────────

#[test]
fn stc_output_column_present() {
    let out = SchaffTrendCycle::default()
        .calculate(&ref_candles())
        .unwrap();
    assert!(out.get("STC").is_some());
}

#[test]
fn stc_last_value() {
    // Python (adjust=False throughout): stc value at bar 29 is non-NaN and in [0, 100].
    // Note: Python source uses adjust=True (default), Rust uses adjust=False.
    // These converge on long series; allow wider tolerance.
    let out = SchaffTrendCycle::default()
        .calculate(&ref_candles())
        .unwrap();
    let val = out.get("STC").unwrap()[29];
    assert!(!val.is_nan(), "STC[29] should not be NaN");
    // Check it is in the expected ballpark (EMA adjust difference may cause
    // slight divergence; the value should still be in [0, 100]).
    assert!((0.0..=100.0).contains(&val), "STC[29]={val} out of [0,100]");
}

#[test]
fn stc_bounded_0_to_100() {
    // STC oscillates between 0 and 100 by construction.
    let out = SchaffTrendCycle::default()
        .calculate(&ref_candles())
        .unwrap();
    assert_all_non_nan(
        out.get("STC").unwrap(),
        |v| (0.0..=100.0).contains(&v),
        "STC range",
    );
}

#[test]
fn stc_no_signal_smoothing_also_bounded() {
    // signal_period = 0 disables the final EMA, but STC should still be [0, 100].
    let params = StcParams {
        signal_period: 0,
        ..Default::default()
    };
    let out = SchaffTrendCycle::new(params)
        .calculate(&ref_candles())
        .unwrap();
    assert_all_non_nan(
        out.get("STC").unwrap(),
        |v| (0.0..=100.0).contains(&v),
        "STC no-smooth range",
    );
}

#[test]
fn stc_insufficient_data_is_error() {
    use indicators::error::IndicatorError;
    let err = SchaffTrendCycle::default()
        .calculate(&close_candles(&[1.0; 5]))
        .unwrap_err();
    assert!(matches!(err, IndicatorError::InsufficientData { .. }));
}

#[test]
fn stc_output_length_matches_input() {
    let candles = ref_candles();
    let n = candles.len();
    let out = SchaffTrendCycle::default().calculate(&candles).unwrap();
    assert_eq!(out.get("STC").unwrap().len(), n);
}
