// =============================================================================
// config.rs — Rithmic connector configuration + the capability gate.
//
// All values are read from environment variables. Credentials (RITHMIC_USER /
// RITHMIC_PASSWORD) are injected by the spawner secret store at spawn time, the
// same way crypto bots receive their exchange keys (the 3-slot broker secret:
// user → api_key, password → api_secret, system → api_passphrase).
//
// The gate logic (`GateDecision`) is the heart of the "capability gate in
// action": the connector only ever touches Rithmic when it is BOTH enabled
// (RITHMIC_ENABLED=true) AND credentialed. Everything here is pure and unit-
// tested without a live connection.
// =============================================================================

use std::env;

/// Which Rithmic environment to target. Mirrors `rithmic_rs::RithmicEnv` but is
/// kept as our own type so the config surface does not leak the vendor crate
/// (and so the skeleton compiles without the `live-connect` feature).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default, serde::Serialize)]
#[serde(rename_all = "lowercase")]
pub enum RithmicEnvironment {
    /// Rithmic Paper Trading (demo/development). Safe default.
    #[default]
    Demo,
    /// Rithmic Test system (conformance / dev-kit login).
    Test,
    /// Rithmic 01 (production). Requires conformance sign-off. Read-only here.
    Live,
}

impl RithmicEnvironment {
    /// Parse from the `RITHMIC_ENV` string; unknown values fall back to `Demo`.
    pub fn parse(s: &str) -> Self {
        match s.trim().to_ascii_lowercase().as_str() {
            "test" => Self::Test,
            "live" | "production" | "prod" => Self::Live,
            _ => Self::Demo,
        }
    }

    /// The conventional Rithmic system_name default for this environment. Used
    /// only when `RITHMIC_SYSTEM_NAME` is not explicitly provided.
    pub fn default_system_name(self) -> &'static str {
        match self {
            Self::Demo => "Rithmic Paper Trading",
            Self::Test => "Rithmic Test",
            Self::Live => "Rithmic 01",
        }
    }
}

/// The outcome of evaluating whether the connector should touch Rithmic.
///
/// This is the capability gate. `Ready` is the ONLY variant that permits a
/// network connection; every other variant is a clean, logged no-op.
#[derive(Debug, Clone, PartialEq, Eq, serde::Serialize)]
#[serde(tag = "state", rename_all = "snake_case")]
pub enum GateDecision {
    /// `RITHMIC_ENABLED` is false (the default). Feature-flagged off.
    Disabled,
    /// Enabled, but one or more required credentials/URL are absent. We log the
    /// missing pieces and idle — no partial/ambiguous connection attempts.
    MissingCredentials {
        /// Names of the required-but-empty fields (never their values).
        missing: Vec<String>,
    },
    /// Enabled AND fully credentialed. The connector may open the read-only
    /// Ticker plant.
    Ready,
}

impl GateDecision {
    /// True only when the connector is cleared to open a Rithmic session.
    pub fn is_ready(&self) -> bool {
        matches!(self, GateDecision::Ready)
    }

    /// A short human-readable reason, for logs and the `/status` payload.
    pub fn reason(&self) -> String {
        match self {
            GateDecision::Disabled => {
                "RITHMIC_ENABLED is false — connector idle (no Rithmic session opened)".to_string()
            }
            GateDecision::MissingCredentials { missing } => format!(
                "RITHMIC_ENABLED is true but required config is absent: {} — connector idle",
                missing.join(", ")
            ),
            GateDecision::Ready => {
                "enabled + credentialed — cleared to open the read-only Ticker plant".to_string()
            }
        }
    }
}

/// Full connector configuration, parsed from the environment.
#[derive(Debug, Clone)]
pub struct RithmicConfig {
    /// Master runtime feature flag. Default: false. Nothing connects unless true.
    pub enabled: bool,

    /// Target Rithmic environment (demo/test/live).
    pub environment: RithmicEnvironment,

    /// Primary gateway WebSocket URL (`wss://…`). Handed out by Rithmic after
    /// onboarding; empty until then.
    pub gateway_url: String,

    /// Alternative/beta gateway URL used by the vendor crate's alternating
    /// reconnect strategy. Falls back to `gateway_url` when unset.
    pub gateway_alt_url: String,

    /// Rithmic `system_name` (e.g. "Rithmic Paper Trading"). Third secret slot.
    pub system_name: String,

    /// Login username (secret slot 1 / api_key). Injected by the spawner store.
    pub user: String,

    /// Login password (secret slot 2 / api_secret). Injected by the spawner store.
    pub password: String,

    /// Application name registered with Rithmic (required by R|Protocol login).
    pub app_name: String,

    /// Application version string (required by R|Protocol login).
    pub app_version: String,

    /// The single instrument this foundation subscribes to (e.g. "MES").
    pub instrument: String,

    /// The exchange the instrument trades on (e.g. "CME").
    pub exchange: String,

    /// Host for the /health + /status server.
    pub health_host: String,

    /// Port for the /health + /status server (FKS bot contract: :9091).
    pub health_port: u16,
}

impl RithmicConfig {
    /// Parse configuration from the process environment.
    pub fn from_env() -> Self {
        Self::from_getter(|k| env::var(k).ok())
    }

    /// Parse configuration from an arbitrary getter. This is the deterministic
    /// core used by tests — no process-global env mutation required.
    pub fn from_getter(get: impl Fn(&str) -> Option<String>) -> Self {
        let get_or = |k: &str, default: &str| {
            get(k)
                .filter(|v| !v.trim().is_empty())
                .unwrap_or_else(|| default.to_string())
        };

        let enabled = parse_bool(get("RITHMIC_ENABLED").as_deref(), false);
        let environment = RithmicEnvironment::parse(&get_or("RITHMIC_ENV", "demo"));

        let gateway_url = get_or("RITHMIC_GATEWAY_URL", "");
        // Alt URL defaults to the primary so a single-URL config still works.
        let gateway_alt_url = get("RITHMIC_GATEWAY_ALT_URL")
            .filter(|v| !v.trim().is_empty())
            .unwrap_or_else(|| gateway_url.clone());

        let system_name = get_or("RITHMIC_SYSTEM_NAME", environment.default_system_name());

        Self {
            enabled,
            environment,
            gateway_url,
            gateway_alt_url,
            system_name,
            user: get_or("RITHMIC_USER", ""),
            password: get_or("RITHMIC_PASSWORD", ""),
            app_name: get_or("RITHMIC_APP_NAME", "fks-rithmic-connector"),
            app_version: get_or("RITHMIC_APP_VERSION", env!("CARGO_PKG_VERSION")),
            instrument: get_or("RITHMIC_INSTRUMENT", "MES"),
            exchange: get_or("RITHMIC_EXCHANGE", "CME"),
            health_host: get_or("RITHMIC_HEALTH_HOST", "0.0.0.0"),
            health_port: get_or("RITHMIC_HEALTH_PORT", "9091")
                .parse()
                .unwrap_or(9091),
        }
    }

    /// Evaluate the capability gate. See [`GateDecision`].
    pub fn gate(&self) -> GateDecision {
        if !self.enabled {
            return GateDecision::Disabled;
        }

        // Enabled — every field required to *authenticate* must be present.
        // We check the URL and credentials; app_name/version/system_name always
        // have defaults so are never "missing".
        let mut missing = Vec::new();
        if self.gateway_url.trim().is_empty() {
            missing.push("RITHMIC_GATEWAY_URL".to_string());
        }
        if self.user.trim().is_empty() {
            missing.push("RITHMIC_USER".to_string());
        }
        if self.password.trim().is_empty() {
            missing.push("RITHMIC_PASSWORD".to_string());
        }

        if missing.is_empty() {
            GateDecision::Ready
        } else {
            GateDecision::MissingCredentials { missing }
        }
    }
}

/// Parse a boolean env var leniently: true/1/yes/on (case-insensitive) → true.
fn parse_bool(v: Option<&str>, default: bool) -> bool {
    match v {
        Some(s) => matches!(
            s.trim().to_ascii_lowercase().as_str(),
            "1" | "true" | "yes" | "on"
        ),
        None => default,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::HashMap;

    /// Build a getter closure over a fixed map — deterministic, no env mutation.
    fn getter(pairs: &[(&str, &str)]) -> impl Fn(&str) -> Option<String> {
        let map: HashMap<String, String> = pairs
            .iter()
            .map(|(k, v)| (k.to_string(), v.to_string()))
            .collect();
        move |k: &str| map.get(k).cloned()
    }

    #[test]
    fn defaults_are_safe_when_env_empty() {
        let cfg = RithmicConfig::from_getter(getter(&[]));
        assert!(!cfg.enabled, "RITHMIC_ENABLED must default to false");
        assert_eq!(cfg.environment, RithmicEnvironment::Demo);
        assert_eq!(cfg.instrument, "MES");
        assert_eq!(cfg.exchange, "CME");
        assert_eq!(cfg.health_port, 9091);
        assert_eq!(cfg.system_name, "Rithmic Paper Trading");
    }

    #[test]
    fn parses_all_fields() {
        let cfg = RithmicConfig::from_getter(getter(&[
            ("RITHMIC_ENABLED", "true"),
            ("RITHMIC_ENV", "test"),
            ("RITHMIC_GATEWAY_URL", "wss://rituz00100.rithmic.com:443"),
            ("RITHMIC_SYSTEM_NAME", "Rithmic Test"),
            ("RITHMIC_USER", "devuser"),
            ("RITHMIC_PASSWORD", "devpass"),
            ("RITHMIC_INSTRUMENT", "ES"),
            ("RITHMIC_EXCHANGE", "CME"),
            ("RITHMIC_HEALTH_PORT", "9099"),
        ]));
        assert!(cfg.enabled);
        assert_eq!(cfg.environment, RithmicEnvironment::Test);
        assert_eq!(cfg.gateway_url, "wss://rituz00100.rithmic.com:443");
        assert_eq!(cfg.system_name, "Rithmic Test");
        assert_eq!(cfg.instrument, "ES");
        assert_eq!(cfg.health_port, 9099);
        // Alt URL falls back to the primary when unset.
        assert_eq!(cfg.gateway_alt_url, cfg.gateway_url);
    }

    #[test]
    fn env_default_system_name_used_when_absent() {
        let cfg = RithmicConfig::from_getter(getter(&[("RITHMIC_ENV", "live")]));
        assert_eq!(cfg.environment, RithmicEnvironment::Live);
        assert_eq!(cfg.system_name, "Rithmic 01");
    }

    #[test]
    fn bool_parsing_is_lenient() {
        for truthy in ["1", "true", "TRUE", "yes", "On"] {
            let cfg = RithmicConfig::from_getter(getter(&[("RITHMIC_ENABLED", truthy)]));
            assert!(cfg.enabled, "{truthy} should be truthy");
        }
        for falsy in ["0", "false", "no", "", "garbage"] {
            let cfg = RithmicConfig::from_getter(getter(&[("RITHMIC_ENABLED", falsy)]));
            assert!(!cfg.enabled, "{falsy:?} should be falsy");
        }
    }

    // ─── the gate contract ────────────────────────────────────────────────

    #[test]
    fn gate_disabled_by_default() {
        let cfg = RithmicConfig::from_getter(getter(&[]));
        assert_eq!(cfg.gate(), GateDecision::Disabled);
        assert!(!cfg.gate().is_ready());
    }

    #[test]
    fn gate_disabled_even_with_full_creds() {
        // The disabled flag dominates: creds present but flag off ⇒ no-op.
        let cfg = RithmicConfig::from_getter(getter(&[
            ("RITHMIC_GATEWAY_URL", "wss://gw.example:443"),
            ("RITHMIC_USER", "u"),
            ("RITHMIC_PASSWORD", "p"),
        ]));
        assert_eq!(cfg.gate(), GateDecision::Disabled);
    }

    #[test]
    fn gate_missing_credentials_lists_absent_fields() {
        let cfg = RithmicConfig::from_getter(getter(&[("RITHMIC_ENABLED", "true")]));
        match cfg.gate() {
            GateDecision::MissingCredentials { missing } => {
                assert!(missing.contains(&"RITHMIC_GATEWAY_URL".to_string()));
                assert!(missing.contains(&"RITHMIC_USER".to_string()));
                assert!(missing.contains(&"RITHMIC_PASSWORD".to_string()));
            }
            other => panic!("expected MissingCredentials, got {other:?}"),
        }
        assert!(!cfg.gate().is_ready());
    }

    #[test]
    fn gate_missing_only_password() {
        let cfg = RithmicConfig::from_getter(getter(&[
            ("RITHMIC_ENABLED", "true"),
            ("RITHMIC_GATEWAY_URL", "wss://gw.example:443"),
            ("RITHMIC_USER", "u"),
        ]));
        assert_eq!(
            cfg.gate(),
            GateDecision::MissingCredentials {
                missing: vec!["RITHMIC_PASSWORD".to_string()]
            }
        );
    }

    #[test]
    fn gate_ready_when_enabled_and_credentialed() {
        let cfg = RithmicConfig::from_getter(getter(&[
            ("RITHMIC_ENABLED", "true"),
            ("RITHMIC_GATEWAY_URL", "wss://gw.example:443"),
            ("RITHMIC_USER", "u"),
            ("RITHMIC_PASSWORD", "p"),
        ]));
        assert_eq!(cfg.gate(), GateDecision::Ready);
        assert!(cfg.gate().is_ready());
    }

    #[test]
    fn gate_treats_whitespace_creds_as_missing() {
        let cfg = RithmicConfig::from_getter(getter(&[
            ("RITHMIC_ENABLED", "true"),
            ("RITHMIC_GATEWAY_URL", "wss://gw.example:443"),
            ("RITHMIC_USER", "   "),
            ("RITHMIC_PASSWORD", "p"),
        ]));
        // Whitespace-only user is blanked by from_getter's empty filter, so the
        // gate must report it missing rather than attempting a bad login.
        assert!(!cfg.gate().is_ready());
    }
}
