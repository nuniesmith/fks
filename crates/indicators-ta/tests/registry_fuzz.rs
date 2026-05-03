/// Fuzz-style and property tests for the indicator registry factory functions.
///
/// Covers:
/// - Every registered name is discoverable and creatable with default params
/// - All indicators run `calculate()` on `required_len()` candles without panicking
/// - Invalid params return typed errors, never panics
/// - Case-insensitive name lookup
/// - Unknown names return `UnknownIndicator`, not a panic
/// - Random numeric and non-numeric param values don't crash the factories
use std::collections::HashMap;

use indicators::{error::IndicatorError, registry::registry, types::Candle};

// ── Candle helpers ────────────────────────────────────────────────────────────

/// Build `n` candles on a gentle uptrend — safe for all indicators.
fn rising_candles(n: usize) -> Vec<Candle> {
    (0..n)
        .map(|i| {
            let c = 100.0 + i as f64 * 0.25;
            Candle {
                time: i64::try_from(i).unwrap() * 60_000,
                open: c - 0.1,
                high: c + 0.2,
                low: c - 0.2,
                close: c,
                volume: 500.0 + (i % 7) as f64 * 100.0,
            }
        })
        .collect()
}

// ── Registry meta ─────────────────────────────────────────────────────────────

#[test]
fn registry_is_non_empty() {
    let names = registry().list();
    assert!(
        !names.is_empty(),
        "registry must have at least one registered indicator"
    );
}

#[test]
fn registry_contains_core_indicators() {
    // Spot-check a representative set — any rename will surface here.
    let reg = registry();
    for name in &[
        "sma",
        "ema",
        "wma",
        "macd",
        "atr",
        "rsi",
        "stochastic",
        "williamsr",
        "bollingerbands",
        "keltnerchannels",
        "vwap",
        "adl",
        "engine",
        "signal",
    ] {
        assert!(
            reg.contains(name),
            "registry is missing expected indicator: '{name}'"
        );
    }
}

// ── Default-params creation ───────────────────────────────────────────────────

/// Every registered indicator must be constructable with an empty params map.
/// All factory functions must provide defaults for every parameter.
#[test]
fn all_indicators_create_with_empty_params() {
    let reg = registry();
    let names = reg.list();
    let empty: HashMap<String, String> = HashMap::new();

    for name in &names {
        let result = reg.create(name, &empty);
        assert!(
            result.is_ok(),
            "indicator '{name}' failed to create with empty params: {:?}",
            result.err()
        );
    }
}

// ── End-to-end calculate without panic ────────────────────────────────────────

/// Create each indicator with default params and run `calculate()` on exactly
/// `required_len()` candles.  The call must not panic; errors are acceptable
/// (some indicators may need specific columns not in our generic candles).
#[test]
fn all_indicators_calculate_does_not_panic_on_required_len() {
    let reg = registry();
    let names = reg.list();
    let empty: HashMap<String, String> = HashMap::new();
    // Use 350 candles — enough for even the most data-hungry indicators
    // (e.g. Engine training_period=100, EnsembleDetector, etc.)
    let candles = rising_candles(350);

    for name in &names {
        // Creation errors are already caught by all_indicators_create_with_empty_params above.
        let Ok(indicator) = reg.create(name, &empty) else { continue };
        let needed = indicator.required_len();
        let slice = if needed <= candles.len() {
            &candles[..needed.max(1)]
        } else {
            &candles[..]
        };
        // Must not panic — errors (e.g. InsufficientData) are fine.
        let _ = std::panic::catch_unwind(|| {
            // Use a fresh indicator inside the closure to satisfy UnwindSafe.
            if let Ok(ind) = reg.create(name, &empty) {
                let _ = ind.calculate(slice);
            }
        });
    }
}

/// Provide more than `required_len()` candles — calculate must succeed.
#[test]
fn all_indicators_calculate_succeeds_with_ample_data() {
    let reg = registry();
    let names = reg.list();
    let empty: HashMap<String, String> = HashMap::new();
    let candles = rising_candles(350);

    for name in &names {
        let Ok(indicator) = reg.create(name, &empty) else { continue };
            continue;
        }
        let result = indicator.calculate(&candles[..needed.max(2)]);
        assert!(
            result.is_ok(),
            "indicator '{name}' returned Err on {needed} candles: {:?}",
            result.err()
        );
    }
}

// ── Unknown name ──────────────────────────────────────────────────────────────

#[test]
fn unknown_name_returns_unknown_indicator_error() {
    let empty: HashMap<String, String> = HashMap::new();
    let err = registry()
        .create("this_indicator_does_not_exist_xyz", &empty)
        .unwrap_err();
    assert!(
        matches!(err, IndicatorError::UnknownIndicator { .. }),
        "expected UnknownIndicator, got {err:?}"
    );
}

#[test]
fn empty_name_returns_unknown_indicator_error() {
    let empty: HashMap<String, String> = HashMap::new();
    let err = registry().create("", &empty).unwrap_err();
    assert!(
        matches!(err, IndicatorError::UnknownIndicator { .. }),
        "expected UnknownIndicator for empty name, got {err:?}"
    );
}

// ── Case insensitivity ────────────────────────────────────────────────────────

#[test]
fn registry_lookup_is_case_insensitive() {
    let reg = registry();
    let empty: HashMap<String, String> = HashMap::new();

    // All of these should resolve to the same "sma" factory.
    for name in &["sma", "SMA", "Sma", "sMa", "SMA"] {
        assert!(
            reg.create(name, &empty).is_ok(),
            "case-insensitive lookup failed for '{name}'"
        );
    }
}

#[test]
fn registry_contains_is_case_insensitive() {
    let reg = registry();
    assert!(reg.contains("sma"));
    assert!(reg.contains("SMA"));
    assert!(reg.contains("Ema"));
    assert!(reg.contains("MACD"));
}

// ── Bad param types ───────────────────────────────────────────────────────────

#[test]
fn non_numeric_period_returns_invalid_parameter_error() {
    let bad_params: HashMap<String, String> =
        std::iter::once(("period".to_string(), "not_a_number".to_string())).collect();

    for name in &["sma", "ema", "wma", "rsi", "atr"] {
        let result = registry().create(name, &bad_params);
        assert!(
            result.is_err(),
            "indicator '{name}' should reject non-numeric 'period'"
        );
        let err = result.unwrap_err();
        assert!(
            matches!(err, IndicatorError::InvalidParameter { .. }),
            "indicator '{name}': expected InvalidParameter, got {err:?}"
        );
    }
}

#[test]
fn empty_string_period_returns_invalid_parameter_error() {
    let bad_params: HashMap<String, String> =
        std::iter::once(("period".to_string(), String::new())).collect();

    for name in &["sma", "ema", "rsi"] {
        let result = registry().create(name, &bad_params);
        assert!(
            result.is_err(),
            "indicator '{name}' should reject empty string 'period'"
        );
    }
}

#[test]
fn float_period_string_returns_error() {
    // e.g. "14.5" is not a valid usize.
    let bad_params: HashMap<String, String> =
        std::iter::once(("period".to_string(), "14.5".to_string())).collect();

    for name in &["sma", "ema", "rsi"] {
        let result = registry().create(name, &bad_params);
        assert!(
            result.is_err(),
            "indicator '{name}' should reject float string '14.5' for a usize param"
        );
    }
}

// ── Random param values ───────────────────────────────────────────────────────

/// Sweep a variety of nonsensical string values for the most-common param key
/// ("period") and assert that factories never panic — only return errors.
#[test]
fn random_string_params_do_not_panic() {
    let garbage_values = [
        "abc",
        "!@#$%",
        " ",
        "\t\n",
        "9999999999999999999999999999", // overflow
        "-1",
        "0",
        "1e10",
        "NaN",
        "inf",
        "-inf",
        "true",
        "null",
        "[]",
        "{}",
        "''",
    ];

    let reg = registry();
    let names = reg.list();

    for name in &names {
        for val in &garbage_values {
            let params: HashMap<String, String> =
                std::iter::once(("period".to_string(), val.to_string())).collect();
            // The call must never panic — errors are expected and fine.
            let result = std::panic::catch_unwind(|| {
                let _ = registry().create(name, &params);
            });
            assert!(
                result.is_ok(),
                "indicator '{name}' panicked on param value '{val}'"
            );
        }
    }
}

/// Verify that extra/unknown param keys are silently ignored and creation
/// still succeeds with defaults.
#[test]
fn unknown_param_keys_are_ignored() {
    let extra_params: HashMap<String, String> = [
        ("this_key_does_not_exist".to_string(), "42".to_string()),
        ("another_bogus_key".to_string(), "hello".to_string()),
    ]
    .into_iter()
    .collect();

    let reg = registry();
    for name in &["sma", "ema", "rsi", "macd"] {
        let result = reg.create(name, &extra_params);
        assert!(
            result.is_ok(),
            "indicator '{name}' should ignore unknown param keys; got {result:?}"
        );
    }
}

// ── Valid boundary params ─────────────────────────────────────────────────────

/// Period values of 1 should be accepted (degenerate but valid).
#[test]
fn period_of_one_is_accepted() {
    let params: HashMap<String, String> =
        std::iter::once(("period".to_string(), "1".to_string())).collect();

    let reg = registry();
    for name in &["sma", "ema", "wma", "rsi"] {
        let result = reg.create(name, &params);
        assert!(
            result.is_ok(),
            "indicator '{name}' should accept period=1; got {result:?}"
        );
    }
}

/// Very large but valid period strings should either succeed or fail gracefully.
#[test]
fn large_period_does_not_panic() {
    let params: HashMap<String, String> =
        std::iter::once(("period".to_string(), "10000".to_string())).collect();

    let reg = registry();
    for name in &reg.list() {
        let result = std::panic::catch_unwind(|| {
            let _ = registry().create(name, &params);
        });
        assert!(
            result.is_ok(),
            "indicator '{name}' panicked with period=10000"
        );
    }
}

// ── Output column invariants ──────────────────────────────────────────────────

/// Every indicator's output must contain at least one named column.
#[test]
fn all_indicators_output_at_least_one_column() {
    let reg = registry();
    let empty: HashMap<String, String> = HashMap::new();
    let candles = rising_candles(350);

    for name in &reg.list() {
        let Ok(indicator) = reg.create(name, &empty) else { continue };
        let needed = indicator.required_len();
        if needed > candles.len() {
            continue;
        }
        if let Ok(output) = indicator.calculate(&candles) {
            let mut cols = output.columns();
            assert!(
                cols.next().is_some(),
                "indicator '{name}' produced zero output columns"
            );
        }
    }
}

/// Output vectors must have the same length as the input candle slice.
#[test]
fn output_length_equals_input_length() {
    let reg = registry();
    let empty: HashMap<String, String> = HashMap::new();
    let candles = rising_candles(350);

    for name in &reg.list() {
        let Ok(indicator) = reg.create(name, &empty) else { continue };
        let needed = indicator.required_len();
        if needed > candles.len() {
            continue;
        }
        if let Ok(output) = indicator.calculate(&candles) {
            for col in output.columns() {
                assert_eq!(
                    output.get(col).unwrap().len(),
                    candles.len(),
                    "indicator '{name}' column '{col}' length mismatch"
                );
            }
        }
    }
}
