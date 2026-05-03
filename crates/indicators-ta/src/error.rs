use std::error::Error;
use std::fmt;

// ── Error ────────────────────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub enum IndicatorError {
    InsufficientData {
        required: usize,
        available: usize,
    },
    InvalidParameter {
        name: String,
        value: f64,
    },
    /// Returned by the registry when `name` is not registered.
    /// Mirrors Python `IndicatorFactory`: `raise ValueError(f"Indicator not found: {name}")`.
    UnknownIndicator {
        name: String,
    },
    /// General construction-time validation failure (bad param combination, etc.).
    InvalidParam(String),
}

impl fmt::Display for IndicatorError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            IndicatorError::InsufficientData {
                required,
                available,
            } => write!(
                f,
                "Insufficient data: required {required} candles, but only {available} available"
            ),
            IndicatorError::InvalidParameter { name, value } => {
                write!(f, "Invalid parameter {name}: {value}")
            }
            IndicatorError::UnknownIndicator { name } => {
                write!(f, "Unknown indicator: '{name}'")
            }
            IndicatorError::InvalidParam(msg) => {
                write!(f, "Invalid parameter: {msg}")
            }
        }
    }
}

impl Error for IndicatorError {}
