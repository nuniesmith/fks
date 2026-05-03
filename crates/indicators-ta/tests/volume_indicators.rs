mod common;
use common::*;

use indicators::indicator::Indicator;
use indicators::volume::vwap::Vwap;
use indicators::volume::adl::Adl;
use indicators::volume::chaikin_money_flow::ChaikinMoneyFlow;

const EPS: f64 = 1e-7;

// ─────────────────────────────────────────────────────────────────────────────
// VWAP — cumulative
// ─────────────────────────────────────────────────────────────────────────────

#[test]
fn vwap_cumulative_single_bar() {
    // tp = (101.5 + 99.0 + 100.0) / 3 = 100.1667; vwap = tp (only one bar)
    let out = Vwap::cumulative().calculate(&ref_candles()).unwrap();
    let vals = out.get("VWAP").unwrap();
    assert_close(vals[0], 100.1666_6666_667, EPS, "VWAP_cum[0]");
}

#[test]
fn vwap_cumulative_last_value() {
    // Python: (tp * vol).cumsum() / vol.cumsum() at bar 29 = 110.5357...
    let out = Vwap::cumulative().calculate(&ref_candles()).unwrap();
    let vals = out.get("VWAP").unwrap();
    assert_close(vals[29], 110.5357_5102_88, 1e-6, "VWAP_cum[29]");
}

#[test]
fn vwap_cumulative_is_non_decreasing_on_monotone_price() {
    // When all bars have the same typical price, VWAP must equal that price.
    let bars: Vec<(f64, f64, f64, f64)> = vec![(12.0, 8.0, 10.0, 100.0); 10];
    let out = Vwap::cumulative().calculate(&make_candles(&bars)).unwrap();
    let tp = (12.0 + 8.0 + 10.0) / 3.0;
    let vals = out.get("VWAP").unwrap();
    for (i, &v) in vals.iter().enumerate() {
        assert_close(v, tp, EPS, &format!("VWAP_cum const[{i}]"));
    }
}

#[test]
fn vwap_cumulative_no_leading_nans() {
    // Cumulative VWAP produces a value at every bar (no warm-up NaNs).
    let out = Vwap::cumulative().calculate(&ref_candles()).unwrap();
    let vals = out.get("VWAP").unwrap();
    assert_no_nans_from(vals, 0, "VWAP_cum");
}

#[test]
fn vwap_cumulative_output_key_is_vwap() {
    let out = Vwap::cumulative().calculate(&ref_candles()).unwrap();
    assert!(out.get("VWAP").is_some());
    assert!(out.get("VWAP_10").is_none());
}

// ─────────────────────────────────────────────────────────────────────────────
// VWAP — rolling
// ─────────────────────────────────────────────────────────────────────────────

#[test]
fn vwap_rolling10_first_valid() {
    // Python: rolling(10) sum at bar 9 = 103.7780...
    let out = Vwap::rolling(10).calculate(&ref_candles()).unwrap();
    let vals = out.get("VWAP_10").unwrap();
    assert_close(vals[9], 103.7780_3738_32, 1e-6, "VWAP_roll10[9]");
}

#[test]
fn vwap_rolling10_last_value() {
    // Python: iloc[29] = 117.0662...
    let out = Vwap::rolling(10).calculate(&ref_candles()).unwrap();
    let vals = out.get("VWAP_10").unwrap();
    assert_close(vals[29], 117.0662_1004_57, 1e-6, "VWAP_roll10[29]");
}

#[test]
fn vwap_rolling_leading_nans() {
    let out = Vwap::rolling(10).calculate(&ref_candles()).unwrap();
    let vals = out.get("VWAP_10").unwrap();
    assert_leading_nans(vals, 9, "VWAP_roll10");
    assert_no_nans_from(vals, 9, "VWAP_roll10");
}

#[test]
fn vwap_rolling_output_key_includes_period() {
    let out = Vwap::rolling(10).calculate(&ref_candles()).unwrap();
    assert!(out.get("VWAP_10").is_some());
    assert!(out.get("VWAP").is_none());
}

#[test]
fn vwap_rolling_equals_cumulative_on_one_bar() {
    // A rolling VWAP with period=1 must equal the bar's own typical price.
    let out = Vwap::rolling(1).calculate(&ref_candles()).unwrap();
    let vals = out.get("VWAP_1").unwrap();
    let tp0 = (BARS[0].0 + BARS[0].1 + BARS[0].2) / 3.0;
    assert_close(vals[0], tp0, EPS, "VWAP_roll1[0] vs tp");
}

// ─────────────────────────────────────────────────────────────────────────────
// ADL — Accumulation/Distribution Line
// ─────────────────────────────────────────────────────────────────────────────

#[test]
fn adl_first_bar_known_value() {
    // bar 0: high=101.5, low=99.0, close=100.0, vol=1000
    // range=2.5; mfm=((100-99)-(101.5-100))/2.5 = (1-1.5)/2.5 = -0.2
    // mfv = -0.2 * 1000 = -200; adl[0] = -200
    let out = Adl::new().calculate(&ref_candles()).unwrap();
    let vals = out.get("ADL").unwrap();
    assert_close(vals[0], -200.0, EPS, "ADL[0]");
}

#[test]
fn adl_last_value() {
    // Python: adl.iloc[29] = -505.7142...
    let out = Adl::new().calculate(&ref_candles()).unwrap();
    let vals = out.get("ADL").unwrap();
    assert_close(vals[29], -505.7142_8571_43, 1e-6, "ADL[29]");
}

#[test]
fn adl_is_strictly_cumulative() {
    // adl[i] - adl[i-1] must equal mfv[i] for each bar.
    // We verify the cumulative property: two identical bars → adl[1] = 2*adl[0].
    let bars = vec![(10.0_f64, 8.0, 9.0, 100.0); 3];
    let out = Adl::new().calculate(&make_candles(&bars)).unwrap();
    let vals = out.get("ADL").unwrap();
    assert_close(vals[1], 2.0 * vals[0], EPS, "ADL cumulative");
    assert_close(vals[2], 3.0 * vals[0], EPS, "ADL cumulative x3");
}

#[test]
fn adl_full_positive_bar_mfm_one() {
    // close == high → mfm = 1.0 → mfv = volume
    let bars = vec![(10.0_f64, 8.0, 10.0, 500.0)];
    let out = Adl::new().calculate(&make_candles(&bars)).unwrap();
    assert_close(out.get("ADL").unwrap()[0], 500.0, EPS, "ADL full bull");
}

#[test]
fn adl_full_negative_bar_mfm_neg_one() {
    // close == low → mfm = -1.0 → mfv = -volume
    let bars = vec![(10.0_f64, 8.0, 8.0, 500.0)];
    let out = Adl::new().calculate(&make_candles(&bars)).unwrap();
    assert_close(out.get("ADL").unwrap()[0], -500.0, EPS, "ADL full bear");
}

#[test]
fn adl_zero_range_contributes_zero() {
    // high == low → mfm = 0 → adl unchanged
    let bars = vec![(5.0_f64, 5.0, 5.0, 1000.0), (10.0, 8.0, 10.0, 200.0)];
    let out = Adl::new().calculate(&make_candles(&bars)).unwrap();
    let vals = out.get("ADL").unwrap();
    assert_close(vals[0], 0.0, EPS, "ADL zero range");
    // Second bar: mfm=1, mfv=200 → adl = 200
    assert_close(vals[1], 200.0, EPS, "ADL after zero range");
}

#[test]
fn adl_no_leading_nans() {
    // ADL is purely cumulative — valid from bar 0.
    let out = Adl::new().calculate(&ref_candles()).unwrap();
    assert_no_nans_from(out.get("ADL").unwrap(), 0, "ADL");
}

// ─────────────────────────────────────────────────────────────────────────────
// CMF — Chaikin Money Flow
// ─────────────────────────────────────────────────────────────────────────────

#[test]
fn cmf_14_first_valid() {
    // Python: cmf.iloc[13] = 0.010866...
    let out = ChaikinMoneyFlow::with_period(14).calculate(&ref_candles()).unwrap();
    let vals = out.get("CMF_14").unwrap();
    assert_close(vals[13], 0.010_866_091_4, 1e-8, "CMF(14)[13]");
}

#[test]
fn cmf_14_last_value() {
    // Python: cmf.iloc[29] = -0.024262...
    let out = ChaikinMoneyFlow::with_period(14).calculate(&ref_candles()).unwrap();
    let vals = out.get("CMF_14").unwrap();
    assert_close(vals[29], -0.024_262_295_1, 1e-8, "CMF(14)[29]");
}

#[test]
fn cmf_always_in_neg1_to_pos1() {
    let out = ChaikinMoneyFlow::with_period(14).calculate(&ref_candles()).unwrap();
    assert_all_non_nan(out.get("CMF_14").unwrap(), |v| (-1.0..=1.0).contains(&v), "CMF range");
}

#[test]
fn cmf_leading_nans() {
    let out = ChaikinMoneyFlow::with_period(14).calculate(&ref_candles()).unwrap();
    assert_leading_nans(out.get("CMF_14").unwrap(), 13, "CMF(14)");
}

#[test]
fn cmf_all_up_bars_is_positive() {
    // close == high every bar → mfm = 1 for all bars → CMF = 1
    let bars: Vec<(f64, f64, f64, f64)> =
        (0..20).map(|i| (10.0 + i as f64, 8.0 + i as f64, 10.0 + i as f64, 100.0)).collect();
    let out = ChaikinMoneyFlow::with_period(5).calculate(&make_candles(&bars)).unwrap();
    assert_all_non_nan(out.get("CMF_5").unwrap(), |v| v > 0.0, "CMF all up");
}

#[test]
fn cmf_all_down_bars_is_negative() {
    // close == low every bar → mfm = -1 for all bars → CMF = -1
    let bars: Vec<(f64, f64, f64, f64)> =
        (0..20).map(|i| (10.0 + i as f64, 8.0 + i as f64, 8.0 + i as f64, 100.0)).collect();
    let out = ChaikinMoneyFlow::with_period(5).calculate(&make_candles(&bars)).unwrap();
    assert_all_non_nan(out.get("CMF_5").unwrap(), |v| v < 0.0, "CMF all down");
}

#[test]
fn cmf_output_key_includes_period() {
    let out = ChaikinMoneyFlow::with_period(20).calculate(&ref_candles()).unwrap();
    assert!(out.get("CMF_20").is_some());
}
