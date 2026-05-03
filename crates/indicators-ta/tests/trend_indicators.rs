mod common;
use common::*;

use indicators::indicator::Indicator;
use indicators::momentum::williams_r::WilliamsR;
use indicators::trend::linear_regression::LinearRegression;
use indicators::trend::parabolic_sar::{ParabolicSar, PsarParams};
use indicators::volatility::choppiness_index::ChoppinessIndex;
use indicators::volatility::elder_ray_index::ElderRayIndex;

const EPS: f64 = 1e-7;

// ─────────────────────────────────────────────────────────────────────────────
// Choppiness Index
// ─────────────────────────────────────────────────────────────────────────────

#[test]
fn chop_14_first_valid() {
    // Python: chop.iloc[13] = 45.0101...
    let out = ChoppinessIndex::with_period(14).calculate(&ref_candles()).unwrap();
    let vals = out.get("CHOP_14").unwrap();
    assert_close(vals[13], 45.0101_4089_64, 1e-6, "CHOP(14)[13]");
}

#[test]
fn chop_14_last_value() {
    // Python: chop.iloc[29] = 50.3133...
    let out = ChoppinessIndex::with_period(14).calculate(&ref_candles()).unwrap();
    let vals = out.get("CHOP_14").unwrap();
    assert_close(vals[29], 50.3133_5013_22, 1e-6, "CHOP(14)[29]");
}

#[test]
fn chop_theoretical_bounds() {
    // CHOP has theoretical bounds (0, 100], though normal range is 0–100.
    let out = ChoppinessIndex::with_period(14).calculate(&ref_candles()).unwrap();
    assert_all_non_nan(out.get("CHOP_14").unwrap(), |v| v > 0.0 && v <= 100.0, "CHOP bounds");
}

#[test]
fn chop_constant_bars_equals_100() {
    // Equal-range bars every period: atr_sum = period*range, max_h-min_l = range
    // → log10(period) / log10(period) * 100 = 100.
    let bars: Vec<(f64, f64, f64, f64)> = vec![(11.0, 9.0, 10.0, 100.0); 20];
    let out = ChoppinessIndex::with_period(14).calculate(&make_candles(&bars)).unwrap();
    let vals = out.get("CHOP_14").unwrap();
    let last = vals.iter().rev().find(|v| !v.is_nan()).copied().unwrap();
    assert_close(last, 100.0, 1e-6, "CHOP constant = 100");
}

#[test]
fn chop_leading_nans() {
    let out = ChoppinessIndex::with_period(14).calculate(&ref_candles()).unwrap();
    assert_leading_nans(out.get("CHOP_14").unwrap(), 13, "CHOP(14)");
}

#[test]
fn chop_output_key_includes_period() {
    let out = ChoppinessIndex::with_period(14).calculate(&ref_candles()).unwrap();
    assert!(out.get("CHOP_14").is_some());
}

// ─────────────────────────────────────────────────────────────────────────────
// Williams %R
// ─────────────────────────────────────────────────────────────────────────────

#[test]
fn wr_14_first_valid() {
    // Python: wr.iloc[13] = -8.0
    let out = WilliamsR::with_period(14).calculate(&ref_candles()).unwrap();
    let vals = out.get("WR_14").unwrap();
    assert_close(vals[13], -8.0, EPS, "WR(14)[13]");
}

#[test]
fn wr_14_last_value() {
    // Python: wr.iloc[29] = -22.7272...
    let out = WilliamsR::with_period(14).calculate(&ref_candles()).unwrap();
    let vals = out.get("WR_14").unwrap();
    assert_close(vals[29], -22.7272_7272_73, 1e-7, "WR(14)[29]");
}

#[test]
fn wr_always_between_neg100_and_zero() {
    let out = WilliamsR::with_period(14).calculate(&ref_candles()).unwrap();
    assert_all_non_nan(
        out.get("WR_14").unwrap(),
        |v| (-100.0..=0.0).contains(&v),
        "WR range",
    );
}

#[test]
fn wr_close_at_highest_high_is_zero() {
    // close == high of window → WR = 0 (no bearish spread).
    let bars = vec![(12.0_f64, 8.0, 12.0, 100.0); 14];
    let out = WilliamsR::with_period(14).calculate(&make_candles(&bars)).unwrap();
    assert_close(out.get("WR_14").unwrap()[13], 0.0, EPS, "WR at high");
}

#[test]
fn wr_close_at_lowest_low_is_neg100() {
    // close == low of window → WR = -100 (maximum bearish spread).
    let bars = vec![(12.0_f64, 8.0, 8.0, 100.0); 14];
    let out = WilliamsR::with_period(14).calculate(&make_candles(&bars)).unwrap();
    assert_close(out.get("WR_14").unwrap()[13], -100.0, EPS, "WR at low");
}

#[test]
fn wr_leading_nans() {
    let out = WilliamsR::with_period(14).calculate(&ref_candles()).unwrap();
    assert_leading_nans(out.get("WR_14").unwrap(), 13, "WR(14)");
}

#[test]
fn wr_midpoint_close_is_minus_50() {
    // close exactly halfway between highest high and lowest low → WR = -50.
    // Construct bars where hh=12, ll=8, close=10 for every bar in window.
    let bars = vec![(12.0_f64, 8.0, 10.0, 100.0); 14];
    let out = WilliamsR::with_period(14).calculate(&make_candles(&bars)).unwrap();
    assert_close(out.get("WR_14").unwrap()[13], -50.0, EPS, "WR midpoint");
}

// ─────────────────────────────────────────────────────────────────────────────
// Linear Regression slope
// ─────────────────────────────────────────────────────────────────────────────

#[test]
fn lr_slope_10_first_valid() {
    // Python: np.polyfit(arange(10), close[0:10], 1)[0] = 0.6878...
    let out = LinearRegression::with_period(10).calculate(&ref_candles()).unwrap();
    let vals = out.get("LR_slope_10").unwrap();
    assert_close(vals[9], 0.6878_7878_79, 1e-8, "LR(10)[9]");
}

#[test]
fn lr_slope_10_stable_on_uniform_trend() {
    // The slope does not change when the underlying trend is perfectly uniform.
    // Our reference data has a nearly uniform trend, so [9] ≈ [29].
    let out = LinearRegression::with_period(10).calculate(&ref_candles()).unwrap();
    let vals = out.get("LR_slope_10").unwrap();
    assert_close(vals[29], 0.6878_7878_79, 1e-8, "LR(10)[29]");
}

#[test]
fn lr_perfect_uptrend_slope_one() {
    // y = 0, 1, 2, ..., 13 → slope = 1.0 exactly.
    let closes: Vec<f64> = (0..14).map(|x| x as f64).collect();
    let out = LinearRegression::with_period(14)
        .calculate(&close_candles(&closes))
        .unwrap();
    assert_close(out.get("LR_slope_14").unwrap()[13], 1.0, EPS, "LR perfect slope");
}

#[test]
fn lr_constant_series_slope_zero() {
    let out = LinearRegression::with_period(14)
        .calculate(&close_candles(&[42.0_f64; 20]))
        .unwrap();
    assert_close(out.get("LR_slope_14").unwrap()[13], 0.0, EPS, "LR const slope");
}

#[test]
fn lr_downtrend_negative_slope() {
    // y = 20, 19, 18, ... → slope = -1.0.
    let closes: Vec<f64> = (0..20).map(|x| 20.0 - x as f64).collect();
    let out = LinearRegression::with_period(10)
        .calculate(&close_candles(&closes))
        .unwrap();
    let vals = out.get("LR_slope_10").unwrap();
    assert!(vals[9] < 0.0, "downtrend slope should be negative, got {}", vals[9]);
    assert_close(vals[9], -1.0, EPS, "LR downtrend");
}

#[test]
fn lr_leading_nans() {
    let out = LinearRegression::with_period(10).calculate(&ref_candles()).unwrap();
    assert_leading_nans(out.get("LR_slope_10").unwrap(), 9, "LR(10)");
}

// ─────────────────────────────────────────────────────────────────────────────
// Parabolic SAR
// ─────────────────────────────────────────────────────────────────────────────

#[test]
fn psar_bar0_is_zero_matching_python() {
    // Python: sar = np.zeros(n); sar[0] = 0.0 (intentional cold-start).
    let out = ParabolicSar::default().calculate(&ref_candles()).unwrap();
    assert_close(out.get("PSAR").unwrap()[0], 0.0, EPS, "PSAR[0]");
}

#[test]
fn psar_bar1_known_value() {
    // Python: sar[1] = 0 + 0.02 * (low[0] - 0) = 0.02 * 99.0 = 1.98
    let out = ParabolicSar::default().calculate(&ref_candles()).unwrap();
    assert_close(out.get("PSAR").unwrap()[1], 1.98, EPS, "PSAR[1]");
}

#[test]
fn psar_last_value() {
    // Python: sar[29] = 117.9342...
    let out = ParabolicSar::default().calculate(&ref_candles()).unwrap();
    assert_close(out.get("PSAR").unwrap()[29], 117.9342_0267_38, 1e-6, "PSAR[29]");
}

#[test]
fn psar_all_finite() {
    let out = ParabolicSar::default().calculate(&ref_candles()).unwrap();
    let vals = out.get("PSAR").unwrap();
    for (i, &v) in vals.iter().enumerate() {
        assert!(v.is_finite(), "PSAR[{i}] = {v} is not finite");
    }
}

#[test]
fn psar_correct_length() {
    let out = ParabolicSar::default().calculate(&ref_candles()).unwrap();
    assert_eq!(out.get("PSAR").unwrap().len(), 30);
}

#[test]
fn psar_af_bounded_by_max_step() {
    // Custom tight bounds: step=0.05, max_step=0.1.
    let params = PsarParams { step: 0.05, max_step: 0.1 };
    let out = ParabolicSar::new(params).calculate(&ref_candles()).unwrap();
    let vals = out.get("PSAR").unwrap();
    // Values must stay finite (AF bounded → SAR stays near price).
    for (i, &v) in vals.iter().enumerate() {
        assert!(v.is_finite(), "PSAR bounded[{i}] = {v}");
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// Elder Ray Index
// ─────────────────────────────────────────────────────────────────────────────

#[test]
fn elder_ray_two_output_columns() {
    let out = ElderRayIndex::with_period(14).calculate(&ref_candles()).unwrap();
    assert!(out.get("ElderRay_bull").is_some(), "missing bull");
    assert!(out.get("ElderRay_bear").is_some(), "missing bear");
}

#[test]
fn elder_ray_bull_last_value() {
    // Python (adjust=False): bull[29] = high[29] - ema14[29] = 5.1694...
    let out = ElderRayIndex::with_period(14).calculate(&ref_candles()).unwrap();
    let bull = out.get("ElderRay_bull").unwrap();
    assert_close(bull[29], 5.1694_5936_27, 1e-4, "Elder bull[29]");
}

#[test]
fn elder_ray_bear_last_value() {
    // Python (adjust=False): bear[29] = low[29] - ema14[29] = 2.1694...
    let out = ElderRayIndex::with_period(14).calculate(&ref_candles()).unwrap();
    let bear = out.get("ElderRay_bear").unwrap();
    assert_close(bear[29], 2.1694_5936_27, 1e-4, "Elder bear[29]");
}

#[test]
fn elder_ray_bull_always_geq_bear() {
    // bull = High - EMA; bear = Low - EMA; since High >= Low, bull >= bear always.
    let out = ElderRayIndex::with_period(14).calculate(&ref_candles()).unwrap();
    let bull = out.get("ElderRay_bull").unwrap();
    let bear = out.get("ElderRay_bear").unwrap();
    for i in 0..30 {
        if !bull[i].is_nan() && !bear[i].is_nan() {
            assert!(
                bull[i] >= bear[i] - 1e-12,
                "bull[{i}]={} < bear[{i}]={}",
                bull[i], bear[i]
            );
        }
    }
}

#[test]
fn elder_ray_bull_minus_bear_equals_high_minus_low() {
    // bull - bear = (High - EMA) - (Low - EMA) = High - Low, always.
    let out = ElderRayIndex::with_period(14).calculate(&ref_candles()).unwrap();
    let bull = out.get("ElderRay_bull").unwrap();
    let bear = out.get("ElderRay_bear").unwrap();
    for (i, &(h, l, _, _)) in BARS.iter().enumerate() {
        if !bull[i].is_nan() {
            assert_close(bull[i] - bear[i], h - l, EPS, &format!("H-L[{i}]"));
        }
    }
}

#[test]
fn elder_ray_uptrending_market_bull_positive() {
    // In a strongly trending up market the EMA lags, so bull power > 0.
    let closes: Vec<f64> = (0..30).map(|x| 100.0 + x as f64 * 2.0).collect();
    let bars: Vec<(f64, f64, f64, f64)> =
        closes.iter().map(|&c| (c + 1.0, c - 1.0, c, 1000.0)).collect();
    let out = ElderRayIndex::with_period(5).calculate(&make_candles(&bars)).unwrap();
    let bull = out.get("ElderRay_bull").unwrap();
    // Last several bars should have positive bull power.
    for i in 20..30 {
        if !bull[i].is_nan() {
            assert!(bull[i] > 0.0, "bull[{i}]={} should be > 0 in uptrend", bull[i]);
        }
    }
}
