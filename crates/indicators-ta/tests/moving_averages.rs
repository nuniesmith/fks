mod common;
use common::*;

use indicators::indicator::{Indicator, PriceColumn};
use indicators::trend::sma::{Sma, SmaParams};
use indicators::trend::wma::Wma;

const EPS: f64 = 1e-7;

// ─────────────────────────────────────────────────────────────────────────────
// SMA
// ─────────────────────────────────────────────────────────────────────────────

#[test]
fn sma_5_first_valid_value() {
    // Python: close.rolling(5).mean().iloc[4] = 102.2
    let out = Sma::with_period(5).calculate(&ref_candles()).unwrap();
    let vals = out.get("SMA_5").unwrap();
    assert_close(vals[4], 102.2, EPS, "SMA(5)[4]");
}

#[test]
fn sma_5_last_value() {
    // Python: close.rolling(5).mean().iloc[29] = 118.8
    let out = Sma::with_period(5).calculate(&ref_candles()).unwrap();
    let vals = out.get("SMA_5").unwrap();
    assert_close(vals[29], 118.8, EPS, "SMA(5)[29]");
}

#[test]
fn sma_10_known_values() {
    // Python: iloc[9] = 103.75, iloc[29] = 117.05
    let out = Sma::with_period(10).calculate(&ref_candles()).unwrap();
    let vals = out.get("SMA_10").unwrap();
    assert_close(vals[9], 103.75, EPS, "SMA(10)[9]");
    assert_close(vals[29], 117.05, EPS, "SMA(10)[29]");
}

#[test]
fn sma_leading_nans_match_period_minus_one() {
    let out = Sma::with_period(10).calculate(&ref_candles()).unwrap();
    let vals = out.get("SMA_10").unwrap();
    // First 9 positions must be NaN (warm-up).
    assert_leading_nans(vals, 9, "SMA(10)");
    // Position 9 onward must be finite.
    assert_no_nans_from(vals, 9, "SMA(10)");
}

#[test]
fn sma_constant_series_equals_constant() {
    // SMA of a constant is that constant, at every valid position.
    let candles = close_candles(&[42.0_f64; 20]);
    let out = Sma::with_period(5).calculate(&candles).unwrap();
    let vals = out.get("SMA_5").unwrap();
    for (i, &v) in vals.iter().enumerate().take(20).skip(4) {
        assert_close(v, 42.0, EPS, &format!("SMA const[{i}]"));
    }
}

#[test]
fn sma_on_high_column() {
    // SMA can operate on the High price column.
    let params = SmaParams {
        period: 5,
        column: PriceColumn::High,
    };
    let out = Sma::new(params).calculate(&ref_candles()).unwrap();
    let vals = out.get("SMA_5").unwrap();
    // High[0..5] = [101.5, 103.0, 103.5, 104.5, 105.5] → mean = 103.6
    assert_close(vals[4], 103.6, EPS, "SMA(5, High)[4]");
}

#[test]
fn sma_insufficient_data_is_error() {
    use indicators::error::IndicatorError;
    let err = Sma::with_period(10)
        .calculate(&close_candles(&[1.0; 5]))
        .unwrap_err();
    assert!(matches!(err, IndicatorError::InsufficientData { .. }));
}

#[test]
fn sma_is_arithmetic_mean_of_window() {
    // Verify SMA exactly equals hand-computed window mean on known inputs.
    // close[0..5] = 100, 102, 101.5, 103, 104.5 → sum = 511.0 / 5 = 102.2
    let out = Sma::with_period(5).calculate(&ref_candles()).unwrap();
    let hand = [100.0, 102.0, 101.5, 103.0, 104.5].iter().sum::<f64>() / 5.0;
    assert_close(out.get("SMA_5").unwrap()[4], hand, EPS, "SMA manual");
}

// ─────────────────────────────────────────────────────────────────────────────
// WMA
// ─────────────────────────────────────────────────────────────────────────────

#[test]
fn wma_5_first_valid_value() {
    // Python: rolling(5).apply(weights=[1,2,3,4,5]).iloc[4] = 102.8667
    let out = Wma::with_period(5).calculate(&ref_candles()).unwrap();
    let vals = out.get("WMA_5").unwrap();
    assert_close(vals[4], 102.8666_6666_667, EPS, "WMA(5)[4]");
}

#[test]
fn wma_5_last_value() {
    // Python: iloc[29] = 119.1333...
    let out = Wma::with_period(5).calculate(&ref_candles()).unwrap();
    let vals = out.get("WMA_5").unwrap();
    assert_close(vals[29], 119.1333_3333_333, EPS, "WMA(5)[29]");
}

#[test]
fn wma_leading_nans_match_period_minus_one() {
    let out = Wma::with_period(5).calculate(&ref_candles()).unwrap();
    let vals = out.get("WMA_5").unwrap();
    assert_leading_nans(vals, 4, "WMA(5)");
    assert_no_nans_from(vals, 4, "WMA(5)");
}

#[test]
fn wma_greater_than_sma_on_uptrend() {
    // On a strictly rising series WMA weights recents more → WMA > SMA.
    let closes: Vec<f64> = (1..=20).map(|x| x as f64).collect();
    let candles = close_candles(&closes);
    let wma_out = Wma::with_period(5).calculate(&candles).unwrap();
    let sma_out = Sma::with_period(5).calculate(&candles).unwrap();
    let wma_vals = wma_out.get("WMA_5").unwrap();
    let sma_vals = sma_out.get("SMA_5").unwrap();
    for i in 4..20 {
        assert!(
            wma_vals[i] > sma_vals[i],
            "WMA[{i}]={} should exceed SMA[{i}]={} on uptrend",
            wma_vals[i],
            sma_vals[i]
        );
    }
}

#[test]
fn wma_constant_series_equals_constant() {
    let candles = close_candles(&[55.0_f64; 15]);
    let out = Wma::with_period(5).calculate(&candles).unwrap();
    let vals = out.get("WMA_5").unwrap();
    for (i, &v) in vals.iter().enumerate().take(15).skip(4) {
        assert_close(v, 55.0, EPS, &format!("WMA const[{i}]"));
    }
}

#[test]
fn wma_period3_hand_computed() {
    // weights [1,2,3], sum=6; prices [10, 20, 30]:
    // wma = (1*10 + 2*20 + 3*30) / 6 = (10+40+90)/6 = 140/6 = 23.333...
    let candles = close_candles(&[10.0, 20.0, 30.0]);
    let out = Wma::with_period(3).calculate(&candles).unwrap();
    assert_close(
        out.get("WMA_3").unwrap()[2],
        140.0 / 6.0,
        EPS,
        "WMA(3) hand",
    );
}

#[test]
fn wma_insufficient_data_is_error() {
    use indicators::error::IndicatorError;
    let err = Wma::with_period(10)
        .calculate(&close_candles(&[1.0; 3]))
        .unwrap_err();
    assert!(matches!(err, IndicatorError::InsufficientData { .. }));
}
