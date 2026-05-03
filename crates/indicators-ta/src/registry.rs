//! Indicator registry — create indicators by name at runtime.
//!
//! Mirrors `indicators/registry.py` and `indicators/factory.py`:
//! - `IndicatorRegistry` ↔ `class IndicatorRegistry`
//! - `register!` macro ↔ `@register_indicator` decorator
//! - `IndicatorFactory::create(name, params)` ↔ `IndicatorFactory.create(name, **params)`
//!
//! # Usage
//!
//! ```rust,ignore
//! use crate::registry::REGISTRY;
//!
//! // list what's available
//! let names = REGISTRY.list();
//!
//! // create by name with typed params map
//! let params = [("period", "20")].into();
//! let indicator = REGISTRY.create("sma", params).unwrap();
//! let output = indicator.calculate(&candles).unwrap();
//! ```

use std::collections::HashMap;
use std::sync::{OnceLock, RwLock};

use crate::error::IndicatorError;
use crate::indicator::Indicator;

// ── Factory fn type ───────────────────────────────────────────────────────────

/// A function that constructs a `Box<dyn Indicator>` from a string param map.
///
/// Mirrors Python's `indicator_cls(name=name, params=params)` call in
/// `IndicatorRegistry.create()`.
pub type IndicatorFactory =
    fn(params: &HashMap<String, String>) -> Result<Box<dyn Indicator>, IndicatorError>;

// ── Registry ──────────────────────────────────────────────────────────────────

/// Runtime registry mapping indicator names to their factory functions.
///
/// Analogous to `IndicatorRegistry._indicators: dict[str, type[Indicator]]`
/// in Python.
pub struct IndicatorRegistry {
    entries: RwLock<HashMap<String, IndicatorFactory>>,
}

impl IndicatorRegistry {
    pub fn new_uninit() -> Self {
        // RwLock::new is not const-stable yet; we use OnceLock wrapping below.
        // This constructor is intentionally left as a marker — use `REGISTRY`.
        Self {
            entries: RwLock::new(HashMap::new()),
        }
    }

    /// Register an indicator factory under `name` (lowercased).
    ///
    /// Mirrors `IndicatorRegistry.register(indicator_cls)`.
    pub fn register(&self, name: &str, factory: IndicatorFactory) {
        let mut map = self.entries.write().expect("registry write lock poisoned");
        map.insert(name.to_ascii_lowercase(), factory);
    }

    /// List all registered indicator names.
    ///
    /// Mirrors `IndicatorRegistry.list() -> list[str]`.
    pub fn list(&self) -> Vec<String> {
        let map = self.entries.read().expect("registry read lock poisoned");
        map.keys().cloned().collect()
    }

    /// Look up a factory by name (case-insensitive).
    ///
    /// Mirrors `IndicatorRegistry.get(name)`.
    pub fn get(&self, name: &str) -> Option<IndicatorFactory> {
        let map = self.entries.read().expect("registry read lock poisoned");
        map.get(&name.to_ascii_lowercase()).copied()
    }

    /// Create an indicator instance by name.
    ///
    /// Mirrors `IndicatorRegistry.create(name, **params)` and
    /// `IndicatorFactory.create(name, **params)`.
    ///
    /// # Errors
    /// - `IndicatorError::UnknownIndicator` if `name` is not registered.
    /// - Propagates construction errors from the factory.
    pub fn create(
        &self,
        name: &str,
        params: &HashMap<String, String>,
    ) -> Result<Box<dyn Indicator>, IndicatorError> {
        let factory = self
            .get(name)
            .ok_or_else(|| IndicatorError::UnknownIndicator {
                name: name.to_string(),
            })?;
        factory(params)
    }

    /// Check whether an indicator name is registered.
    ///
    /// Mirrors `indicator_registry.get(name) is not None` in `IndicatorFactory.validate_config()`.
    pub fn contains(&self, name: &str) -> bool {
        self.get(name).is_some()
    }
}

// ── Global singleton ──────────────────────────────────────────────────────────

/// Global indicator registry — the single source of truth for runtime creation.
///
/// Populate it once at startup via `REGISTRY.register(...)` or the `register_all!`
/// helper in each module's `mod.rs`.
///
/// Mirrors `indicator_registry = IndicatorRegistry()` in Python.
pub static REGISTRY: OnceLock<IndicatorRegistry> = OnceLock::new();

/// Get (or lazily init) the global registry.
pub fn registry() -> &'static IndicatorRegistry {
    REGISTRY.get_or_init(|| {
        let reg = IndicatorRegistry {
            entries: RwLock::new(HashMap::new()),
        };
        // Register all built-in indicators.
        crate::trend::register_all(&reg);
        crate::momentum::register_all(&reg);
        crate::volatility::register_all(&reg);
        crate::volume::register_all(&reg);
        crate::signal::register_all(&reg);
        crate::regime::register_all(&reg);
        reg
    })
}

// ── Param helpers ─────────────────────────────────────────────────────────────

/// Parse a `usize` from the params map with a default fallback.
///
/// Mirrors `self.params.get("period", 14)` in Python.
pub fn param_usize<S: ::std::hash::BuildHasher>(
    params: &HashMap<String, String, S>,
    key: &str,
    default: usize,
) -> Result<usize, IndicatorError> {
    match params.get(key) {
        None => Ok(default),
        Some(s) => s
            .parse::<usize>()
            .map_err(|_| IndicatorError::InvalidParameter {
                name: key.to_string(),
                value: s.parse::<f64>().unwrap_or(f64::NAN),
            }),
    }
}

/// Parse an `f64` from the params map with a default fallback.
pub fn param_f64<S: ::std::hash::BuildHasher>(
    params: &HashMap<String, String, S>,
    key: &str,
    default: f64,
) -> Result<f64, IndicatorError> {
    match params.get(key) {
        None => Ok(default),
        Some(s) => s
            .parse::<f64>()
            .map_err(|_| IndicatorError::InvalidParameter {
                name: key.to_string(),
                value: f64::NAN,
            }),
    }
}

/// Parse a `String` param with a default fallback.
pub fn param_str<'a, S: ::std::hash::BuildHasher>(
    params: &'a HashMap<String, String, S>,
    key: &str,
    default: &'a str,
) -> &'a str {
    params.get(key).map_or(default, String::as_str)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn dummy_factory(_p: &HashMap<String, String>) -> Result<Box<dyn Indicator>, IndicatorError> {
        // Stub: real indicators will provide a real factory.
        Err(IndicatorError::UnknownIndicator {
            name: "dummy".into(),
        })
    }

    #[test]
    fn registry_register_and_list() {
        let reg = IndicatorRegistry {
            entries: RwLock::new(HashMap::new()),
        };
        reg.register("sma", dummy_factory);
        reg.register("ema", dummy_factory);
        let mut names = reg.list();
        names.sort();
        assert_eq!(names, vec!["ema", "sma"]);
    }

    #[test]
    fn registry_unknown_returns_error() {
        let reg = IndicatorRegistry {
            entries: RwLock::new(HashMap::new()),
        };
        let err = reg
            .create("no_such_indicator", &HashMap::new())
            .unwrap_err();
        assert!(matches!(err, IndicatorError::UnknownIndicator { .. }));
    }

    #[test]
    fn param_usize_default() {
        let params = HashMap::new();
        assert_eq!(param_usize(&params, "period", 14).unwrap(), 14);
    }

    #[test]
    fn param_usize_override() {
        let params = [("period".to_string(), "20".to_string())].into();
        assert_eq!(param_usize(&params, "period", 14).unwrap(), 20);
    }

    #[test]
    fn param_usize_bad_value() {
        let params = [("period".to_string(), "abc".to_string())].into();
        assert!(param_usize(&params, "period", 14).is_err());
    }
}
