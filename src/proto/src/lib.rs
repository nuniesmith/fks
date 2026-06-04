//! # FKS Proto
//!
//! Centralized Protocol Buffer definitions for all FKS services.
//!
//! This crate provides a single source of truth for gRPC types across the FKS trading system,
//! ensuring consistency between services and eliminating type duplication.
//!
//! ## Available Modules
//!
//! - [`common`] - Shared types used across all services (TradingSignal, ExecutionResult, etc.)
//! - [`janus`] - JANUS orchestration service (Forward/Backward services)
//! - [`forward`] - Forward (Wake) real-time trading service
//! - [`execution`] - Order execution service
//! - [`data`] - Market data service
//! - [`cns`] - Central Nervous System monitoring service
//! - [`neuromorphic`] - Distributed training service
//! - [`paper_trading`] - Paper trading management service
//!
//! ## Usage
//!
//! ```rust,ignore
//! use fks_proto::common::{TradingSignal, SignalAction, ExecutionMode};
//! use fks_proto::execution::execution_service_client::ExecutionServiceClient;
//!
//! // Create a trading signal
//! let signal = TradingSignal {
//!     signal_id: "sig_123".to_string(),
//!     symbol: "BTCUSD".to_string(),
//!     action: SignalAction::Buy as i32,
//!     quantity: 0.1,
//!     confidence: 0.85,
//!     mode: ExecutionMode::Paper as i32,
//!     ..Default::default()
//! };
//!
//! // Connect to execution service
//! let mut client = ExecutionServiceClient::connect("http://localhost:50051").await?;
//! ```
//!
//! ## Feature Flags
//!
//! - `serde` - Enable serde serialization/deserialization for proto types

#![doc(html_root_url = "https://docs.rs/fks-proto/0.1.0")]
#![cfg_attr(docsrs, feature(doc_cfg))]
// Generated tonic/prost output transcribes the `.proto` doc comments verbatim;
// clippy's `doc_lazy_continuation` fires on their list continuations, which we
// don't author here. Allow it crate-wide so the generated modules below pass
// the `-D warnings` clippy gate.
#![allow(clippy::doc_lazy_continuation)]

// =============================================================================
// Generated Proto Modules
// =============================================================================

/// Common types shared across all FKS services
///
/// Contains core types like `TradingSignal`, `ExecutionResult`, `Position`,
/// and common enums used throughout the system.
pub mod common {
    tonic::include_proto!("fks.common.v1");
}

/// JANUS orchestration service
///
/// Provides high-level trading orchestration including Forward (Wake) and
/// Backward (Sleep) service definitions for the dual-pathway architecture.
pub mod janus {
    tonic::include_proto!("fks.janus.v1");

    /// Regime Bridge service for neuromorphic regime state distribution
    ///
    /// Provides the `RegimeBridgeService` gRPC definition along with all
    /// associated message types (`RegimeState`, `RegimeIndicators`, etc.)
    /// and enums (`HypothalamusRegime`, `AmygdalaRegime`) used to distribute
    /// regime updates from the JANUS forward service to neuromorphic consumers.
    pub mod regime_bridge {
        tonic::include_proto!("fks.janus.v1.bridge");
    }
}

/// Forward (Wake) trading service
///
/// Real-time trading engine that handles live market data processing,
/// signal generation, and trade execution.
pub mod forward {
    tonic::include_proto!("fks.forward.v1");
}

/// Order execution service
///
/// Handles order placement, position management, and trade execution
/// across multiple exchanges.
pub mod execution {
    tonic::include_proto!("fks.execution.v1");
}

/// Market data service
///
/// Provides historical and real-time market data, including OHLCV candles,
/// orderbook data, and market metrics.
pub mod data {
    tonic::include_proto!("fks.data.v1");
}

/// Central Nervous System (CNS) service
///
/// Provides health monitoring, metrics collection, and auto-recovery
/// capabilities for the trading system.
pub mod cns {
    tonic::include_proto!("fks.cns.v1");
}

/// Neuromorphic distributed training service
///
/// Provides gradient synchronization, parameter server, and distributed
/// training coordination primitives.
pub mod neuromorphic {
    /// Distributed training module
    pub mod distributed {
        tonic::include_proto!("fks.neuromorphic.distributed.v1");
    }
}

/// Paper trading management service
///
/// Provides session management, execution account configuration,
/// routing rules, and metrics for paper trading operations.
pub mod paper_trading {
    tonic::include_proto!("fks.paper_trading.v1");
}

/// Signals bus and inference service
///
/// Defines InferenceService (point-in-time ML inference) and SignalBusService
/// (publish/subscribe live signals), along with FeatureVector and TradingSignal
/// message types.
pub mod signals {
    tonic::include_proto!("fks.signals.v1");
}

/// Position feedback service
///
/// Provides the feedback loop from the execution layer (Python/Ruby) back to
/// Janus for real-time trade guidance and building execution memories.
pub mod feedback {
    tonic::include_proto!("fks.feedback.v1");
}

/// RustCode (RUSTCODE) service
///
/// Provides cross-service gRPC API for semantic search, chat completion,
/// and document ingestion used by Janus and other Rust services.
pub mod rc {
    tonic::include_proto!("fks.rustcode.v1");
}

// =============================================================================
// Inherent impls for janus::regime_bridge types
//
// These builder / convenience methods live here (in the crate that defines the
// types) rather than in the janus-forward crate.  Rust's orphan rule forbids
// inherent impls on types defined in another crate, so any crate that uses
// these types must go through extension traits or free functions for methods
// that depend on external types — but pure builder methods that only touch
// fields of `RegimeState` itself belong here.
// =============================================================================

impl janus::regime_bridge::RegimeState {
    /// Set the monotonic sequence number for this regime state.
    pub fn with_sequence(mut self, seq: u64) -> Self {
        self.sequence = seq;
        self
    }

    /// Mark this state as a transition from the given previous regimes.
    ///
    /// Sets `is_transition = true` and records the previous
    /// `HypothalamusRegime` and `AmygdalaRegime` values.
    pub fn with_transition(
        mut self,
        prev_hypo: janus::regime_bridge::HypothalamusRegime,
        prev_amyg: janus::regime_bridge::AmygdalaRegime,
    ) -> Self {
        self.is_transition = true;
        self.previous_hypothalamus_regime = prev_hypo.into();
        self.previous_amygdala_regime = prev_amyg.into();
        self
    }

    /// Override the timestamp field (Unix microseconds).
    pub fn with_timestamp_us(mut self, ts: i64) -> Self {
        self.timestamp_us = ts;
        self
    }
}

// =============================================================================
// Re-exports for Convenience
// =============================================================================

/// Common types re-exported for convenience
pub mod prelude {
    // Common types
    pub use crate::common::{
        Candle, Empty, ErrorResponse, ExecutionMode, ExecutionResult, ExecutionStatus,
        HealthCheckRequest, HealthCheckResponse, OrderType, PageRequest, PageResponse, Position,
        PositionSide, ServiceStatus, Severity, Side, SignalAction, TimeInForce, TimeRange,
        Timeframe, TradingSignal,
    };

    // Signals types
    pub use crate::signals::{
        FeatureVector, MarketRegime, SignalDirection, SignalQuality,
        TradingSignal as SignalsTradingSignal, inference_service_client::InferenceServiceClient,
        signal_bus_service_client::SignalBusServiceClient,
    };

    // Execution service client
    pub use crate::execution::execution_service_client::ExecutionServiceClient;
    pub use crate::execution::execution_service_server::{
        ExecutionService, ExecutionServiceServer,
    };

    // Forward service client
    pub use crate::forward::forward_service_client::ForwardServiceClient;
    pub use crate::forward::forward_service_server::{ForwardService, ForwardServiceServer};

    // Data service client
    pub use crate::data::data_service_client::DataServiceClient;
    pub use crate::data::data_service_server::{DataService, DataServiceServer};

    // CNS service client
    pub use crate::cns::cns_service_client::CnsServiceClient;
    pub use crate::cns::cns_service_server::{CnsService, CnsServiceServer};

    // Paper trading service
    pub use crate::paper_trading::{
        AccountType, ExchangeName, ExecutionAccount, ExecutionPolicy, PaperTradingSession,
        SessionConfig, SessionState,
        paper_trading_service_client::PaperTradingServiceClient,
        paper_trading_service_server::{PaperTradingService, PaperTradingServiceServer},
    };

    // Feedback service
    pub use crate::feedback::{
        GuidanceAction, OutcomeResult, PositionFeedback, PositionState, TradeGuidance,
        TradeOutcome,
        position_feedback_service_client::PositionFeedbackServiceClient,
        position_feedback_service_server::{
            PositionFeedbackService, PositionFeedbackServiceServer,
        },
    };

    // RUSTCODE service
    pub use crate::rc::{
        ChatMessage, ChatRequest, ChatResponse, IngestRequest, IngestResponse, RaHealthRequest,
        RaHealthResponse, SearchResult, SemanticSearchRequest, SemanticSearchResponse,
        ra_service_client::RaServiceClient,
        ra_service_server::{RaService, RaServiceServer},
    };
}

// =============================================================================
// Type Conversions & Utilities
// =============================================================================

impl common::TradingSignal {
    /// Create a new buy signal
    pub fn buy(symbol: impl Into<String>, quantity: f64) -> Self {
        Self {
            signal_id: uuid_v4(),
            symbol: symbol.into(),
            action: common::SignalAction::Buy as i32,
            quantity,
            timestamp: current_timestamp_ms(),
            ..Default::default()
        }
    }

    /// Create a new sell signal
    pub fn sell(symbol: impl Into<String>, quantity: f64) -> Self {
        Self {
            signal_id: uuid_v4(),
            symbol: symbol.into(),
            action: common::SignalAction::Sell as i32,
            quantity,
            timestamp: current_timestamp_ms(),
            ..Default::default()
        }
    }

    /// Create a close position signal
    pub fn close(symbol: impl Into<String>) -> Self {
        Self {
            signal_id: uuid_v4(),
            symbol: symbol.into(),
            action: common::SignalAction::Close as i32,
            timestamp: current_timestamp_ms(),
            ..Default::default()
        }
    }

    /// Set the execution mode
    pub fn with_mode(mut self, mode: common::ExecutionMode) -> Self {
        self.mode = mode as i32;
        self
    }

    /// Set the confidence score
    pub fn with_confidence(mut self, confidence: f64) -> Self {
        self.confidence = confidence;
        self
    }

    /// Set the strategy ID
    pub fn with_strategy(mut self, strategy_id: impl Into<String>) -> Self {
        self.strategy_id = strategy_id.into();
        self
    }

    /// Set stop loss price
    pub fn with_stop_loss(mut self, stop_loss: f64) -> Self {
        self.stop_loss = stop_loss;
        self
    }

    /// Set take profit price
    pub fn with_take_profit(mut self, take_profit: f64) -> Self {
        self.take_profit = take_profit;
        self
    }

    /// Check if this is a buy signal
    pub fn is_buy(&self) -> bool {
        self.action == common::SignalAction::Buy as i32
    }

    /// Check if this is a sell signal
    pub fn is_sell(&self) -> bool {
        self.action == common::SignalAction::Sell as i32
    }

    /// Check if this is a close signal
    pub fn is_close(&self) -> bool {
        matches!(
            self.action,
            x if x == common::SignalAction::Close as i32
                || x == common::SignalAction::CloseLong as i32
                || x == common::SignalAction::CloseShort as i32
        )
    }
}

impl common::HealthCheckResponse {
    /// Create a healthy response
    pub fn healthy(version: impl Into<String>) -> Self {
        Self {
            healthy: true,
            status: "healthy".to_string(),
            version: version.into(),
            timestamp: current_timestamp_ms(),
            ..Default::default()
        }
    }

    /// Create an unhealthy response
    pub fn unhealthy(message: impl Into<String>) -> Self {
        Self {
            healthy: false,
            status: message.into(),
            timestamp: current_timestamp_ms(),
            ..Default::default()
        }
    }
}

impl common::ErrorResponse {
    /// Create a new error response
    pub fn new(code: impl Into<String>, message: impl Into<String>) -> Self {
        Self {
            code: code.into(),
            message: message.into(),
            timestamp: current_timestamp_ms(),
            ..Default::default()
        }
    }

    /// Add a detail to the error
    pub fn with_detail(mut self, key: impl Into<String>, value: impl Into<String>) -> Self {
        self.details.insert(key.into(), value.into());
        self
    }

    /// Set the request ID
    pub fn with_request_id(mut self, request_id: impl Into<String>) -> Self {
        self.request_id = request_id.into();
        self
    }
}

// =============================================================================
// Helper Functions
// =============================================================================

/// Generate a UUID v4 string
fn uuid_v4() -> String {
    // Simple UUID generation without external dependency
    // In production, you'd want to use the uuid crate
    use std::time::{SystemTime, UNIX_EPOCH};
    let now = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap()
        .as_nanos();
    format!("{:032x}", now)
}

/// Get current timestamp in milliseconds
fn current_timestamp_ms() -> i64 {
    use std::time::{SystemTime, UNIX_EPOCH};
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap()
        .as_millis() as i64
}

// =============================================================================
// Tests
// =============================================================================

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_trading_signal_buy() {
        let signal = common::TradingSignal::buy("BTCUSD", 0.1)
            .with_confidence(0.85)
            .with_strategy("momentum_v1")
            .with_mode(common::ExecutionMode::Paper);

        assert!(signal.is_buy());
        assert!(!signal.is_sell());
        assert_eq!(signal.symbol, "BTCUSD");
        assert_eq!(signal.quantity, 0.1);
        assert_eq!(signal.confidence, 0.85);
        assert_eq!(signal.strategy_id, "momentum_v1");
        assert_eq!(signal.mode, common::ExecutionMode::Paper as i32);
    }

    #[test]
    fn test_trading_signal_sell() {
        let signal = common::TradingSignal::sell("ETHUSDT", 1.0);

        assert!(signal.is_sell());
        assert!(!signal.is_buy());
    }

    #[test]
    fn test_trading_signal_close() {
        let signal = common::TradingSignal::close("BTCUSD");

        assert!(signal.is_close());
        assert!(!signal.is_buy());
        assert!(!signal.is_sell());
    }

    #[test]
    fn test_health_check_healthy() {
        let response = common::HealthCheckResponse::healthy("1.0.0");

        assert!(response.healthy);
        assert_eq!(response.status, "healthy");
        assert_eq!(response.version, "1.0.0");
    }

    #[test]
    fn test_health_check_unhealthy() {
        let response = common::HealthCheckResponse::unhealthy("Database connection failed");

        assert!(!response.healthy);
        assert_eq!(response.status, "Database connection failed");
    }

    #[test]
    fn test_error_response() {
        let error = common::ErrorResponse::new("ERR_001", "Something went wrong")
            .with_detail("field", "username")
            .with_request_id("req_123");

        assert_eq!(error.code, "ERR_001");
        assert_eq!(error.message, "Something went wrong");
        assert_eq!(error.details.get("field"), Some(&"username".to_string()));
        assert_eq!(error.request_id, "req_123");
    }
}
