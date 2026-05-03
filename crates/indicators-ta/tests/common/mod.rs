// Common test helpers shared across indicator integration tests.
// Not every file in the test suite uses every helper; suppress the noise.
#![allow(dead_code)]

// ── 30-bar reference dataset ──────────────────────────────────────────────────
//
// Deterministic OHLCV data whose indicator outputs were verified against the
// Python reference implementation.  See `scripts/compute_references.py`.
//
// Layout: (high, low, close, volume)
pub const BARS: [(f64, f64, f64, f64); 30] = [
    (101.5, 99.0, 100.0, 1000.0),
    (103.0, 100.5, 102.0, 1200.0),
    (103.5, 100.5, 101.5, 900.0),
    (104.5, 101.0, 103.0, 1100.0),
    (105.5, 103.0, 104.5, 1300.0),
    (105.0, 102.0, 103.0, 950.0),
    (106.5, 103.0, 105.0, 1050.0),
    (107.5, 105.0, 106.5, 1150.0),
    (107.0, 104.0, 105.0, 1250.0),
    (108.5, 105.0, 107.0, 800.0),
    (109.0, 106.5, 108.0, 900.0),
    (109.5, 106.5, 107.5, 1000.0),
    (110.5, 107.0, 109.0, 1100.0),
    (111.5, 109.0, 110.5, 1200.0),
    (111.0, 108.0, 109.0, 1300.0),
    (112.5, 109.0, 111.0, 950.0),
    (113.0, 110.5, 112.0, 1050.0),
    (113.5, 110.5, 111.5, 1150.0),
    (114.5, 111.0, 113.0, 1000.0),
    (115.5, 113.0, 114.5, 1100.0),
    (115.0, 112.0, 113.0, 1200.0),
    (116.5, 113.0, 115.0, 900.0),
    (117.5, 115.0, 116.5, 1100.0),
    (117.0, 114.0, 115.0, 1300.0),
    (118.5, 115.0, 117.0, 950.0),
    (119.0, 116.5, 118.0, 1050.0),
    (119.5, 116.5, 117.5, 1150.0),
    (120.5, 117.0, 119.0, 1000.0),
    (121.5, 119.0, 120.5, 1100.0),
    (121.0, 118.0, 119.0, 1200.0),
];

use indicators::types::Candle;

/// Build a `Vec<Candle>` from the shared reference dataset.
pub fn ref_candles() -> Vec<Candle> {
    make_candles(&BARS)
}

/// Build candles from an explicit slice of `(high, low, close, volume)` tuples.
pub fn make_candles(data: &[(f64, f64, f64, f64)]) -> Vec<Candle> {
    data.iter()
        .enumerate()
        .map(|(i, &(h, l, c, v))| Candle {
            time: i64::try_from(i).unwrap(),
            open: c,
            high: h,
            low: l,
            close: c,
            volume: v,
        })
        .collect()
}

/// Build candles from a flat close-price slice (h = l = c = close, volume = 1).
pub fn close_candles(closes: &[f64]) -> Vec<Candle> {
    closes
        .iter()
        .enumerate()
        .map(|(i, &c)| Candle {
            time: i64::try_from(i).unwrap(),
            open: c,
            high: c,
            low: c,
            close: c,
            volume: 1.0,
        })
        .collect()
}

/// Assert two f64 values are within `eps` of each other.
#[track_caller]
pub fn assert_close(actual: f64, expected: f64, eps: f64, label: &str) {
    assert!(
        (actual - expected).abs() < eps,
        "{label}: expected {expected:.10}, got {actual:.10} (diff={diff:.2e})",
        diff = (actual - expected).abs()
    );
}

/// Assert every value in a slice that is not NaN satisfies the predicate.
#[track_caller]
pub fn assert_all_non_nan<F: Fn(f64) -> bool>(values: &[f64], pred: F, label: &str) {
    for (i, &v) in values.iter().enumerate() {
        if !v.is_nan() {
            assert!(pred(v), "{label}[{i}] = {v} failed invariant");
        }
    }
}

/// Assert the first `n` values of a slice are NaN (warm-up period).
#[track_caller]
pub fn assert_leading_nans(values: &[f64], n: usize, label: &str) {
    for (i, &v) in values.iter().enumerate().take(n) {
        assert!(
            v.is_nan(),
            "{label}[{i}] should be NaN during warm-up, got {v}",
        );
    }
}

/// Assert none of the values at or after index `start` are NaN.
#[track_caller]
pub fn assert_no_nans_from(values: &[f64], start: usize, label: &str) {
    for (i, &v) in values.iter().enumerate().skip(start) {
        assert!(!v.is_nan(), "{label}[{i}] should not be NaN after warm-up");
    }
}
