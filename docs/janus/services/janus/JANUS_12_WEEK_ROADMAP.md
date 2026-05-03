# JANUS 12-Week Development Roadmap

## Executive Summary

This roadmap transforms JANUS from its current Phase 1 infrastructure state into a complete, Rust-only neuromorphic trading signal generation system. The plan focuses on:

1. **Data Infrastructure**: Built-in market data, news streams, and storage
2. **Data Quality**: Review, cleaning, validation, and staging pipelines
3. **ML Pipeline**: Full Burn-based machine learning infrastructure
4. **Signal Generation**: Complete forward/backward service implementation
5. **Observability**: Expanded CNS with comprehensive Prometheus metrics

**Key Principle**: JANUS generates trading signals only. Execution is handled by a separate, lightweight Rust service.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           JANUS Trading System                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │    Data      │  │   News       │  │   Storage    │  │   Quality    │   │
│  │  Ingestion   │──│   Streams    │──│    Layer     │──│   Pipeline   │   │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘   │
│         │                  │                  │                  │          │
│         └──────────────────┼──────────────────┼──────────────────┘          │
│                            │                  │                              │
│                   ┌────────▼──────────────────▼────────┐                    │
│                   │         Staging Layer              │                    │
│                   │    (Training Data Preparation)     │                    │
│                   └────────────────┬───────────────────┘                    │
│                                    │                                         │
│  ┌─────────────────────────────────┼─────────────────────────────────────┐  │
│  │                    Burn ML Pipeline                                    │  │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────────┐  │  │
│  │  │  Vision  │  │   LTN    │  │  Memory  │  │      Training        │  │  │
│  │  │ GAF/ViViT│  │ Symbolic │  │  Replay  │  │ Optimizers/Scheduler │  │  │
│  │  └────┬─────┘  └────┬─────┘  └────┬─────┘  └──────────┬───────────┘  │  │
│  └───────┼─────────────┼─────────────┼───────────────────┼──────────────┘  │
│          │             │             │                   │                  │
│  ┌───────▼─────────────▼─────────────▼───────────────────▼──────────────┐  │
│  │                   Neuromorphic Core                                   │  │
│  │  ┌─────────┐ ┌──────────┐ ┌──────────┐ ┌─────────┐ ┌─────────────┐  │  │
│  │  │ Cortex  │ │Hippocampus│ │  Basal   │ │Amygdala │ │ Cerebellum  │  │  │
│  │  │Strategic│ │ Episodic │ │ Ganglia  │ │  Risk   │ │   Motor     │  │  │
│  │  └────┬────┘ └────┬─────┘ └────┬─────┘ └────┬────┘ └──────┬──────┘  │  │
│  └───────┼───────────┼────────────┼────────────┼─────────────┼─────────┘  │
│          │           │            │            │             │             │
│          └───────────┴────────────┼────────────┴─────────────┘             │
│                                   │                                         │
│                          ┌────────▼────────┐                                │
│                          │ Signal Generator │                               │
│                          │   (Forward Svc)  │                               │
│                          └────────┬─────────┘                               │
│                                   │                                         │
│                          ┌────────▼────────┐                                │
│                          │  Trading Signal │ ──────────▶ [Execution Svc]   │
│                          │    (Output)     │              (External)        │
│                          └─────────────────┘                                │
│                                                                              │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                    CNS (Central Nervous System)                        │  │
│  │         Health • Metrics • Alerts • Circuit Breakers • Recovery        │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Phase 1: Data Foundation (Weeks 1-4)

### Week 1: Data Ingestion Enhancement

**Objective**: Extend the existing data service with comprehensive market data coverage.

#### Tasks

| Task | Description | Crate/Service | Priority |
|------|-------------|---------------|----------|
| 1.1 | Implement WebSocket reconnection with exponential backoff | `services/data` | P0 |
| 1.2 | Add Coinbase, Kraken, OKX exchange adapters | `services/data/actors` | P0 |
| 1.3 | Create unified `MarketDataEvent` enum for all exchanges | `lib/janus-core` | P0 |
| 1.4 | Implement order book depth snapshots (L2/L3) | `services/data` | P1 |
| 1.5 | Add liquidation data streams | `services/data` | P1 |
| 1.6 | Implement funding rate tracking | `services/data` | P1 |
| 1.7 | Add CNS probes for data ingestion health | `crates/cns` | P0 |

#### New Crate: `janus-exchanges`

```
crates/exchanges/
├── Cargo.toml
└── src/
    ├── lib.rs
    ├── adapters/
    │   ├── mod.rs
    │   ├── binance.rs      # Spot + Futures
    │   ├── bybit.rs        # Already exists, refactor
    │   ├── coinbase.rs     # New
    │   ├── kraken.rs       # New
    │   ├── okx.rs          # New
    │   └── kucoin.rs       # Exists in data service
    ├── types.rs            # Unified event types
    ├── normalizer.rs       # Price/volume normalization
    └── health.rs           # Connection health tracking
```

#### Key Data Structures

```rust
// lib/janus-core/src/market.rs

/// Unified market data event
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum MarketDataEvent {
    Trade(TradeEvent),
    OrderBook(OrderBookEvent),
    Ticker(TickerEvent),
    Liquidation(LiquidationEvent),
    FundingRate(FundingRateEvent),
    Kline(KlineEvent),
}

/// Normalized trade event
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TradeEvent {
    pub exchange: Exchange,
    pub symbol: Symbol,
    pub timestamp: i64,           // Unix micros
    pub price: Decimal,
    pub quantity: Decimal,
    pub side: Side,
    pub trade_id: String,
}

/// Order book snapshot/delta
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OrderBookEvent {
    pub exchange: Exchange,
    pub symbol: Symbol,
    pub timestamp: i64,
    pub sequence: u64,
    pub is_snapshot: bool,
    pub bids: Vec<PriceLevel>,
    pub asks: Vec<PriceLevel>,
}
```

#### CNS Metrics (New)

```rust
// crates/cns/src/metrics.rs - Data ingestion metrics

// Exchange connectivity
pub data_websocket_connections: IntGaugeVec,       // by exchange
pub data_websocket_reconnects: IntCounterVec,      // by exchange
pub data_websocket_latency_ms: HistogramVec,       // by exchange
pub data_messages_received: IntCounterVec,         // by exchange, type
pub data_messages_parsed_errors: IntCounterVec,    // by exchange

// Data quality
pub data_sequence_gaps: IntCounterVec,             // by exchange, symbol
pub data_stale_data_alerts: IntCounterVec,         // by exchange
pub data_duplicate_events: IntCounterVec,          // by exchange
```

#### Deliverables

- [ ] All 6 exchanges connected and streaming
- [ ] Unified event types in janus-core
- [ ] Health probes reporting to CNS
- [ ] Grafana dashboard for data ingestion
- [ ] 99.9% uptime target per exchange

---

### Week 2: News & Alternative Data Streams

**Objective**: Integrate news feeds and alternative data sources for sentiment analysis.

#### Tasks

| Task | Description | Crate/Service | Priority |
|------|-------------|---------------|----------|
| 2.1 | Create news aggregation service | `services/news` | P0 |
| 2.2 | Implement RSS/Atom feed parser | `crates/news-parser` | P0 |
| 2.3 | Add Twitter/X API integration | `services/news` | P1 |
| 2.4 | Implement news deduplication | `services/news` | P0 |
| 2.5 | Add sentiment scoring pipeline | `crates/sentiment` | P1 |
| 2.6 | Integrate Fear & Greed Index | `services/data` | P0 |
| 2.7 | Add on-chain metrics (Glassnode-style) | `crates/onchain` | P2 |

#### New Service: `services/news`

```
services/news/
├── Cargo.toml
└── src/
    ├── main.rs
    ├── lib.rs
    ├── sources/
    │   ├── mod.rs
    │   ├── rss.rs            # RSS/Atom feeds
    │   ├── twitter.rs        # Twitter API v2
    │   ├── reddit.rs         # Reddit API
    │   └── telegram.rs       # Telegram channels
    ├── dedup.rs              # MinHash deduplication
    ├── scoring.rs            # Relevance scoring
    └── storage.rs            # QuestDB persistence
```

#### New Crate: `janus-sentiment`

```
crates/sentiment/
├── Cargo.toml
└── src/
    ├── lib.rs
    ├── lexicon.rs            # Financial sentiment lexicon
    ├── vader.rs              # VADER sentiment (Rust port)
    ├── entity.rs             # Named entity recognition
    ├── aggregator.rs         # Multi-source aggregation
    └── timeseries.rs         # Sentiment time series
```

#### News Sources Configuration

```toml
# config/news.toml

[sources.rss]
feeds = [
    "https://cointelegraph.com/rss",
    "https://decrypt.co/feed",
    "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "https://bitcoinmagazine.com/feed",
    "https://cryptoslate.com/feed/",
]
poll_interval_secs = 60

[sources.twitter]
enabled = true
api_version = "v2"
tracked_accounts = ["@whale_alert", "@glassnode", "@santaborsu"]
keywords = ["$BTC", "$ETH", "bitcoin", "ethereum", "crypto"]
rate_limit_per_15min = 450

[sources.alternative]
fear_greed_interval_secs = 3600
etf_flows_interval_secs = 86400  # Daily
whale_alerts_enabled = true
```

#### Key Data Structures

```rust
// crates/sentiment/src/lib.rs

/// News article with metadata
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NewsArticle {
    pub id: Uuid,
    pub source: NewsSource,
    pub title: String,
    pub content: String,
    pub url: String,
    pub published_at: DateTime<Utc>,
    pub ingested_at: DateTime<Utc>,
    pub entities: Vec<Entity>,
    pub sentiment: Option<SentimentScore>,
    pub relevance: f32,
    pub fingerprint: u64,  // For deduplication
}

/// Sentiment analysis result
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SentimentScore {
    pub compound: f32,      // -1.0 to 1.0
    pub positive: f32,      // 0.0 to 1.0
    pub negative: f32,      // 0.0 to 1.0
    pub neutral: f32,       // 0.0 to 1.0
    pub confidence: f32,    // Model confidence
}

/// Named entity in news
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Entity {
    pub text: String,
    pub entity_type: EntityType,
    pub start: usize,
    pub end: usize,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum EntityType {
    Cryptocurrency,
    Exchange,
    Person,
    Organization,
    Amount,
    Date,
}
```

#### CNS Metrics (New)

```rust
// News service metrics
pub news_articles_ingested: IntCounterVec,         // by source
pub news_articles_deduplicated: IntCounter,
pub news_sentiment_scores: HistogramVec,           // by asset
pub news_processing_latency_ms: HistogramVec,      // by source
pub news_source_health: GaugeVec,                  // by source
pub news_api_rate_limit_remaining: IntGaugeVec,    // by source
```

#### Deliverables

- [ ] News service processing 5+ RSS feeds
- [ ] Twitter integration with rate limiting
- [ ] Sentiment scoring with VADER
- [ ] Deduplication with >95% accuracy
- [ ] News events published to SignalBus
- [ ] Grafana dashboard for news metrics

---

### Week 3: Storage Layer & Asset Configuration

**Objective**: Build robust storage for market data, news, and enable per-asset configuration.

#### Tasks

| Task | Description | Crate/Service | Priority |
|------|-------------|---------------|----------|
| 3.1 | Design asset configuration schema | `lib/janus-core` | P0 |
| 3.2 | Implement QuestDB schema migrations | `crates/questdb-writer` | P0 |
| 3.3 | Create TimescaleDB adapter (optional) | `crates/storage` | P2 |
| 3.4 | Build data retention policies | `services/data` | P1 |
| 3.5 | Implement hot/warm/cold storage tiers | `crates/storage` | P1 |
| 3.6 | Add Parquet export for training data | `crates/storage` | P0 |
| 3.7 | Create asset registry service | `services/registry` | P0 |

#### New Crate: `janus-storage`

```
crates/storage/
├── Cargo.toml
└── src/
    ├── lib.rs
    ├── backends/
    │   ├── mod.rs
    │   ├── questdb.rs        # Primary time-series
    │   ├── parquet.rs        # Training data export
    │   ├── qdrant.rs         # Vector storage (exists)
    │   └── redis.rs          # Hot cache
    ├── schema.rs             # Schema definitions
    ├── migration.rs          # Schema migrations
    ├── retention.rs          # Data lifecycle
    └── export.rs             # Batch export utilities
```

#### Asset Configuration

```rust
// lib/janus-core/src/asset.rs

/// Asset configuration for trading
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AssetConfig {
    pub symbol: Symbol,
    pub enabled: bool,
    pub exchanges: Vec<ExchangeConfig>,
    pub data_config: DataConfig,
    pub model_config: ModelConfig,
    pub risk_config: RiskConfig,
}

/// Per-asset data collection settings
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DataConfig {
    pub collect_trades: bool,
    pub collect_orderbook: bool,
    pub orderbook_depth: u8,              // L2 depth levels
    pub collect_funding: bool,
    pub collect_liquidations: bool,
    pub news_keywords: Vec<String>,
    pub retention_days: u32,
}

/// Per-asset model settings
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ModelConfig {
    pub vision_enabled: bool,
    pub ltn_enabled: bool,
    pub gaf_window_size: usize,
    pub gaf_num_frames: usize,
    pub custom_indicators: Vec<String>,
}

/// Per-asset risk parameters
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RiskConfig {
    pub max_position_size: Decimal,
    pub max_drawdown_pct: f32,
    pub volatility_lookback: u32,
    pub circuit_breaker_threshold: f32,
}
```

#### Asset Registry API

```rust
// services/registry/src/api.rs

/// Asset registry endpoints
pub fn router() -> Router {
    Router::new()
        .route("/assets", get(list_assets))
        .route("/assets/:symbol", get(get_asset))
        .route("/assets/:symbol", put(update_asset))
        .route("/assets/:symbol/enable", post(enable_asset))
        .route("/assets/:symbol/disable", post(disable_asset))
        .route("/assets/:symbol/status", get(asset_status))
}
```

#### QuestDB Schema

```sql
-- Market data tables

CREATE TABLE IF NOT EXISTS trades (
    timestamp TIMESTAMP,
    exchange SYMBOL,
    symbol SYMBOL,
    price DOUBLE,
    quantity DOUBLE,
    side SYMBOL,
    trade_id STRING
) TIMESTAMP(timestamp) PARTITION BY DAY;

CREATE TABLE IF NOT EXISTS orderbook_snapshots (
    timestamp TIMESTAMP,
    exchange SYMBOL,
    symbol SYMBOL,
    sequence LONG,
    bid_prices DOUBLE[],
    bid_quantities DOUBLE[],
    ask_prices DOUBLE[],
    ask_quantities DOUBLE[]
) TIMESTAMP(timestamp) PARTITION BY HOUR;

CREATE TABLE IF NOT EXISTS funding_rates (
    timestamp TIMESTAMP,
    exchange SYMBOL,
    symbol SYMBOL,
    rate DOUBLE,
    next_funding_time TIMESTAMP
) TIMESTAMP(timestamp) PARTITION BY DAY;

CREATE TABLE IF NOT EXISTS news_articles (
    timestamp TIMESTAMP,
    source SYMBOL,
    title STRING,
    content STRING,
    url STRING,
    sentiment_compound DOUBLE,
    relevance DOUBLE,
    entities STRING
) TIMESTAMP(timestamp) PARTITION BY DAY;

CREATE TABLE IF NOT EXISTS sentiment_timeseries (
    timestamp TIMESTAMP,
    symbol SYMBOL,
    sentiment_1h DOUBLE,
    sentiment_4h DOUBLE,
    sentiment_24h DOUBLE,
    news_count_1h INT,
    news_count_24h INT
) TIMESTAMP(timestamp) PARTITION BY DAY;
```

#### Deliverables

- [ ] Asset registry with CRUD API
- [ ] QuestDB schema migrations
- [ ] Parquet export for training
- [ ] Data retention automation
- [ ] Hot/warm storage tiering
- [ ] Storage metrics in CNS

---

### Week 4: Data Quality Pipeline

**Objective**: Implement comprehensive data validation, cleaning, and anomaly detection.

#### Tasks

| Task | Description | Crate/Service | Priority |
|------|-------------|---------------|----------|
| 4.1 | Create data validation framework | `crates/data-quality` | P0 |
| 4.2 | Implement outlier detection | `crates/data-quality` | P0 |
| 4.3 | Build gap detection & backfill | `crates/gap-detection` | P0 |
| 4.4 | Add timestamp alignment | `crates/data-quality` | P1 |
| 4.5 | Implement data imputation | `crates/data-quality` | P1 |
| 4.6 | Create quality score metrics | `crates/data-quality` | P0 |
| 4.7 | Build data lineage tracking | `crates/data-quality` | P2 |

#### New Crate: `janus-data-quality`

```
crates/data-quality/
├── Cargo.toml
└── src/
    ├── lib.rs
    ├── validators/
    │   ├── mod.rs
    │   ├── schema.rs         # Schema validation
    │   ├── range.rs          # Value range checks
    │   ├── temporal.rs       # Timestamp validation
    │   └── cross_exchange.rs # Cross-exchange consistency
    ├── anomaly/
    │   ├── mod.rs
    │   ├── zscore.rs         # Z-score detection
    │   ├── iqr.rs            # IQR-based detection
    │   ├── mad.rs            # MAD-based detection
    │   └── isolation.rs      # Isolation forest (future)
    ├── cleaning/
    │   ├── mod.rs
    │   ├── outliers.rs       # Outlier handling
    │   ├── imputation.rs     # Missing value imputation
    │   ├── alignment.rs      # Time alignment
    │   └── dedup.rs          # Deduplication
    ├── scoring.rs            # Quality scoring
    └── lineage.rs            # Data lineage tracking
```

#### Data Quality Pipeline

```rust
// crates/data-quality/src/lib.rs

/// Data quality pipeline configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct QualityPipelineConfig {
    pub validators: Vec<ValidatorConfig>,
    pub anomaly_detectors: Vec<AnomalyDetectorConfig>,
    pub cleaners: Vec<CleanerConfig>,
    pub quality_threshold: f32,  // Minimum quality score
}

/// Quality assessment result
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct QualityReport {
    pub timestamp: DateTime<Utc>,
    pub symbol: Symbol,
    pub exchange: Exchange,
    pub total_records: u64,
    pub valid_records: u64,
    pub invalid_records: u64,
    pub anomalies_detected: u64,
    pub records_cleaned: u64,
    pub quality_score: f32,
    pub issues: Vec<QualityIssue>,
}

/// Individual quality issue
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct QualityIssue {
    pub issue_type: IssueType,
    pub severity: Severity,
    pub description: String,
    pub affected_records: u64,
    pub remediation: Option<Remediation>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum IssueType {
    MissingData,
    OutOfRange,
    Duplicate,
    SequenceGap,
    TimestampAnomaly,
    PriceSpike,
    VolumeAnomaly,
    CrossExchangeDeviation,
}

/// Data quality pipeline
pub struct QualityPipeline {
    config: QualityPipelineConfig,
    validators: Vec<Box<dyn Validator>>,
    detectors: Vec<Box<dyn AnomalyDetector>>,
    cleaners: Vec<Box<dyn Cleaner>>,
}

impl QualityPipeline {
    pub fn new(config: QualityPipelineConfig) -> Self { ... }
    
    /// Run full quality pipeline on a batch
    pub async fn process(&self, batch: DataBatch) -> Result<(DataBatch, QualityReport)> {
        // 1. Validate schema and constraints
        let validation_results = self.validate(&batch).await?;
        
        // 2. Detect anomalies
        let anomalies = self.detect_anomalies(&batch).await?;
        
        // 3. Clean data
        let cleaned = self.clean(&batch, &anomalies).await?;
        
        // 4. Generate quality report
        let report = self.generate_report(&batch, &cleaned, &validation_results, &anomalies);
        
        Ok((cleaned, report))
    }
}
```

#### Anomaly Detection

```rust
// crates/data-quality/src/anomaly/zscore.rs

/// Z-score based anomaly detector
pub struct ZScoreDetector {
    window_size: usize,
    threshold: f64,
    features: Vec<String>,
}

impl AnomalyDetector for ZScoreDetector {
    fn detect(&self, data: &DataBatch) -> Vec<AnomalyResult> {
        let mut anomalies = Vec::new();
        
        for feature in &self.features {
            let values = data.get_column(feature);
            let (mean, std) = rolling_stats(&values, self.window_size);
            
            for (i, value) in values.iter().enumerate() {
                let z_score = (value - mean[i]) / std[i];
                if z_score.abs() > self.threshold {
                    anomalies.push(AnomalyResult {
                        index: i,
                        feature: feature.clone(),
                        score: z_score.abs(),
                        anomaly_type: AnomalyType::ZScore,
                    });
                }
            }
        }
        
        anomalies
    }
}
```

#### CNS Metrics (New)

```rust
// Data quality metrics
pub quality_records_validated: IntCounterVec,      // by symbol
pub quality_records_invalid: IntCounterVec,        // by symbol, issue_type
pub quality_anomalies_detected: IntCounterVec,     // by symbol, detector
pub quality_records_cleaned: IntCounterVec,        // by symbol, cleaner
pub quality_score: GaugeVec,                       // by symbol, exchange
pub quality_pipeline_latency_ms: HistogramVec,     // by stage

// Gap detection metrics
pub gap_sequences_detected: IntCounterVec,         // by symbol, exchange
pub gap_backfill_requests: IntCounterVec,          // by symbol
pub gap_backfill_success: IntCounterVec,           // by symbol
pub gap_backfill_latency_ms: HistogramVec,         // by symbol
```

#### Deliverables

- [ ] Quality pipeline processing all data streams
- [ ] Anomaly detection with configurable thresholds
- [ ] Gap detection integrated with backfill
- [ ] Quality score per asset/exchange
- [ ] Quality alerts in CNS
- [ ] Grafana dashboard for data quality

---

## Phase 2: ML Pipeline with Burn (Weeks 5-8)

### Week 5: Burn Framework Migration - Core

**Objective**: Migrate from Candle to Burn for all ML operations.

#### Why Burn?

| Feature | Candle | Burn |
|---------|--------|------|
| Backend flexibility | CUDA only | CPU, CUDA, WGPU, Vulkan |
| Training support | Limited | Full, with autodiff |
| Custom ops | Hard | Easy with derive macros |
| Checkpointing | Manual | Built-in |
| Distributed | No | Planned |
| Ecosystem | HuggingFace focused | General purpose |

#### Tasks

| Task | Description | Crate/Service | Priority |
|------|-------------|---------------|----------|
| 5.1 | Add Burn dependencies to workspace | `Cargo.toml` | P0 |
| 5.2 | Create `janus-burn-core` foundation | `crates/burn-core` | P0 |
| 5.3 | Implement tensor utilities | `crates/burn-core` | P0 |
| 5.4 | Port training loop to Burn | `crates/training` | P0 |
| 5.5 | Implement checkpointing | `crates/training` | P1 |
| 5.6 | Add model serialization | `crates/burn-core` | P1 |
| 5.7 | Benchmark Burn vs Candle | `tests/benchmarks` | P2 |

#### Workspace Dependencies Update

```toml
# Cargo.toml - workspace dependencies

[workspace.dependencies]
# Burn ML Framework
burn = { version = "0.14", features = ["train", "autodiff", "metrics", "tui"] }
burn-core = "0.14"
burn-tensor = "0.14"
burn-autodiff = "0.14"
burn-train = "0.14"
burn-ndarray = "0.14"
burn-wgpu = { version = "0.14", optional = true }
burn-cuda = { version = "0.14", optional = true }
burn-candle = { version = "0.14", optional = true }  # Candle backend for compatibility

# Remove/deprecate Candle direct usage
# candle-core = "0.9.1"  # Deprecated - use burn-candle if needed
# candle-nn = "0.9.1"    # Deprecated
```

#### New Crate: `janus-burn-core`

```
crates/burn-core/
├── Cargo.toml
└── src/
    ├── lib.rs
    ├── backend.rs            # Backend selection/initialization
    ├── tensor.rs             # Tensor utilities
    ├── checkpoint.rs         # Model checkpointing
    ├── serialize.rs          # Model serialization
    ├── device.rs             # Device management
    └── metrics.rs            # Training metrics
```

#### Burn Backend Configuration

```rust
// crates/burn-core/src/backend.rs

use burn::backend::{Autodiff, NdArray, Wgpu};
use burn::tensor::backend::Backend;

/// Default backend for training (with autodiff)
#[cfg(feature = "wgpu")]
pub type TrainBackend = Autodiff<Wgpu>;

#[cfg(not(feature = "wgpu"))]
pub type TrainBackend = Autodiff<NdArray>;

/// Inference backend (no autodiff overhead)
#[cfg(feature = "wgpu")]
pub type InferBackend = Wgpu;

#[cfg(not(feature = "wgpu"))]
pub type InferBackend = NdArray;

/// Backend configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BackendConfig {
    pub device: DeviceConfig,
    pub precision: Precision,
    pub memory_config: MemoryConfig,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum Precision {
    F32,
    F16,
    BF16,
}

/// Initialize the default backend
pub fn init_backend(config: &BackendConfig) -> Result<()> {
    #[cfg(feature = "wgpu")]
    {
        // Initialize WGPU with configuration
        let device = match &config.device {
            DeviceConfig::Gpu(idx) => burn_wgpu::WgpuDevice::default(),
            DeviceConfig::Cpu => burn_wgpu::WgpuDevice::Cpu,
        };
        // Configure memory limits, etc.
    }
    Ok(())
}
```

#### Training Loop Migration

```rust
// crates/training/src/loop_burn.rs

use burn::train::{
    LearnerBuilder, TrainingInterrupter,
    metric::{LossMetric, CpuUse, CpuMemory},
};
use burn::optim::AdamWConfig;
use burn::lr_scheduler::CosineAnnealingLrScheduler;

/// Burn-based training loop for JANUS
pub struct BurnTrainingLoop<B: Backend> {
    config: TrainingConfig,
    learner: Option<Learner<B>>,
    interrupter: TrainingInterrupter,
}

impl<B: Backend> BurnTrainingLoop<B> {
    pub fn new(config: TrainingConfig) -> Self {
        Self {
            config,
            learner: None,
            interrupter: TrainingInterrupter::new(),
        }
    }
    
    /// Build and configure the learner
    pub fn build<M, O, S>(
        &mut self,
        model: M,
        optimizer_config: O,
        scheduler_config: S,
        train_dataloader: DataLoader,
        valid_dataloader: Option<DataLoader>,
        device: &B::Device,
    ) -> Result<()>
    where
        M: AutodiffModule<B>,
        O: OptimizerConfig,
        S: LrSchedulerConfig,
    {
        let mut builder = LearnerBuilder::new(&self.config.artifact_dir)
            .with_file_checkpointer(self.config.checkpoint_interval)
            .devices(vec![device.clone()])
            .num_epochs(self.config.num_epochs)
            .metric_train_numeric(LossMetric::new())
            .metric_valid_numeric(LossMetric::new())
            .metric_train_numeric(CpuUse::new())
            .metric_train_numeric(CpuMemory::new())
            .interrupter(self.interrupter.clone());
            
        if let Some(valid_loader) = valid_dataloader {
            builder = builder.with_validation(valid_loader);
        }
        
        self.learner = Some(builder.build(model, optimizer_config.init(), train_dataloader));
        Ok(())
    }
    
    /// Run training
    pub fn fit(&mut self) -> Result<TrainingResult> {
        let learner = self.learner.take()
            .ok_or_else(|| anyhow::anyhow!("Learner not built"))?;
            
        let trained_model = learner.fit();
        
        Ok(TrainingResult {
            final_model: trained_model,
            metrics: self.collect_metrics(),
        })
    }
    
    /// Interrupt training gracefully
    pub fn interrupt(&self) {
        self.interrupter.interrupt();
    }
}
```

#### CNS Metrics (New)

```rust
// ML training metrics
pub ml_training_epoch: IntGaugeVec,                // by model
pub ml_training_step: IntGaugeVec,                 // by model
pub ml_training_loss: GaugeVec,                    // by model, loss_type
pub ml_validation_loss: GaugeVec,                  // by model, loss_type
pub ml_learning_rate: GaugeVec,                    // by model
pub ml_gradient_norm: GaugeVec,                    // by model
pub ml_batch_latency_ms: HistogramVec,             // by model
pub ml_gpu_memory_bytes: IntGaugeVec,              // by device
pub ml_gpu_utilization: GaugeVec,                  // by device
pub ml_checkpoint_saved: IntCounterVec,            // by model
```

#### Deliverables

- [ ] Burn dependencies in workspace
- [ ] janus-burn-core with backend selection
- [ ] Training loop migrated to Burn
- [ ] Checkpointing working
- [ ] Training metrics in CNS
- [ ] Benchmark comparison document

---

### Week 6: Vision Pipeline (GAF + ViViT) in Burn

**Objective**: Reimplement the vision pipeline (Gramian Angular Fields + Video Vision Transformer) using Burn.

#### Tasks

| Task | Description | Crate/Service | Priority |
|------|-------------|---------------|----------|
| 6.1 | Port GAF transformation to Burn | `crates/vision` | P0 |
| 6.2 | Implement DiffGAF (learnable normalization) | `crates/vision` | P0 |
| 6.3 | Port ViViT to Burn | `crates/vision` | P0 |
| 6.4 | Implement factorized attention | `crates/vision` | P1 |
| 6.5 | Add GAF video generation | `crates/vision` | P0 |
| 6.6 | Implement patch embedding | `crates/vision` | P1 |
| 6.7 | Benchmark vision pipeline | `tests/benchmarks` | P2 |

#### Vision Crate Refactor

```
crates/vision/
├── Cargo.toml
└── src/
    ├── lib.rs
    ├── gaf/
    │   ├── mod.rs
    │   ├── transform.rs      # GAF/GADF transformation
    │   ├── diff_gaf.rs       # Differentiable GAF with learnable params
    │   ├── normalization.rs  # Learnable normalization
    │   └── video.rs          # GAF video generation
    ├── vivit/
    │   ├── mod.rs
    │   ├── config.rs         # ViViT configuration
    │   ├── embedding.rs      # Patch embedding
    │   ├── attention.rs      # Factorized attention
    │   ├── encoder.rs        # ViViT encoder
    │   └── model.rs          # Full ViViT model
    ├── pipeline.rs           # Vision pipeline
    └── tests/
        └── integration.rs
```

#### GAF Implementation in Burn

```rust
// crates/vision/src/gaf/diff_gaf.rs

use burn::module::Module;
use burn::nn::{Linear, LinearConfig};
use burn::tensor::{backend::Backend, Tensor};

/// Differentiable Gramian Angular Field with learnable normalization
#[derive(Module, Debug)]
pub struct DiffGAF<B: Backend> {
    /// Learnable scale parameter (γ)
    gamma: Tensor<B, 1>,
    /// Learnable shift parameter (β)  
    beta: Tensor<B, 1>,
    /// Running mean for normalization
    running_mean: Tensor<B, 1>,
    /// Running std for normalization
    running_std: Tensor<B, 1>,
    /// Momentum for running stats
    momentum: f32,
    /// Field type (GASF or GADF)
    field_type: GafFieldType,
}

#[derive(Debug, Clone, Copy, PartialEq)]
pub enum GafFieldType {
    /// Gramian Angular Summation Field
    GASF,
    /// Gramian Angular Difference Field
    GADF,
}

impl<B: Backend> DiffGAF<B> {
    /// Create new DiffGAF module
    pub fn new(num_features: usize, field_type: GafFieldType, device: &B::Device) -> Self {
        Self {
            gamma: Tensor::ones([num_features], device),
            beta: Tensor::zeros([num_features], device),
            running_mean: Tensor::zeros([num_features], device),
            running_std: Tensor::ones([num_features], device),
            momentum: 0.1,
            field_type,
        }
    }
    
    /// Forward pass: time series → GAF image
    /// Input: [batch, seq_len, features]
    /// Output: [batch, features, seq_len, seq_len]
    pub fn forward(&self, x: Tensor<B, 3>, training: bool) -> Tensor<B, 4> {
        let [batch, seq_len, features] = x.dims();
        
        // Step 1: Learnable normalization
        let normalized = self.normalize(x, training);
        
        // Step 2: Tanh to ensure [-1, 1] range for arccos
        let bounded = normalized.tanh();
        
        // Step 3: Polar transformation
        let phi = bounded.acos(); // [batch, seq_len, features]
        
        // Step 4: Generate Gramian field
        let gaf = match self.field_type {
            GafFieldType::GASF => self.compute_gasf(phi, bounded),
            GafFieldType::GADF => self.compute_gadf(phi, bounded),
        };
        
        gaf
    }
    
    /// Compute GASF: G[i,j] = cos(φ_i + φ_j) = x̃_i * x̃_j - √(1-x̃_i²) * √(1-x̃_j²)
    fn compute_gasf(&self, phi: Tensor<B, 3>, x: Tensor<B, 3>) -> Tensor<B, 4> {
        let [batch, seq_len, features] = x.dims();
        
        // x̃_i * x̃_j term
        // Reshape for outer product: [batch, seq_len, 1, features] * [batch, 1, seq_len, features]
        let x_i = x.clone().reshape([batch, seq_len, 1, features]);
        let x_j = x.clone().reshape([batch, 1, seq_len, features]);
        let term1 = x_i.clone() * x_j.clone();
        
        // √(1-x̃_i²) * √(1-x̃_j²) term
        let sqrt_i = (1.0 - x_i.powf_scalar(2.0)).sqrt();
        let sqrt_j = (1.0 - x_j.powf_scalar(2.0)).sqrt();
        let term2 = sqrt_i * sqrt_j;
        
        // GASF = term1 - term2
        // Permute to [batch, features, seq_len, seq_len]
        (term1 - term2).swap_dims(1, 3)
    }
    
    /// Compute GADF: G[i,j] = sin(φ_i - φ_j) = √(1-x̃_i²) * x̃_j - x̃_i * √(1-x̃_j²)
    fn compute_gadf(&self, phi: Tensor<B, 3>, x: Tensor<B, 3>) -> Tensor<B, 4> {
        let [batch, seq_len, features] = x.dims();
        
        let x_i = x.clone().reshape([batch, seq_len, 1, features]);
        let x_j = x.clone().reshape([batch, 1, seq_len, features]);
        
        let sqrt_i = (1.0 - x_i.clone().powf_scalar(2.0)).sqrt();
        let sqrt_j = (1.0 - x_j.clone().powf_scalar(2.0)).sqrt();
        
        // GADF = √(1-x̃_i²) * x̃_j - x̃_i * √(1-x̃_j²)
        let gadf = sqrt_i * x_j - x_i * sqrt_j;
        
        gadf.swap_dims(1, 3)
    }
    
    /// Learnable normalization with running statistics
    fn normalize(&self, x: Tensor<B, 3>, training: bool) -> Tensor<B, 3> {
        if training {
            // Update running stats
            let mean = x.clone().mean_dim(1);
            let std = x.clone().var_dim(1).sqrt() + 1e-6;
            // Apply learnable affine transformation
            let gamma = self.gamma.clone().unsqueeze().unsqueeze();
            let beta = self.beta.clone().unsqueeze().unsqueeze();
            gamma * (x - mean) / std + beta
        } else {
            let mean = self.running_mean.clone().unsqueeze().unsqueeze();
            let std = self.running_std.clone().unsqueeze().unsqueeze();
            let gamma = self.gamma.clone().unsqueeze().unsqueeze();
            let beta = self.beta.clone().unsqueeze().unsqueeze();
            gamma * (x - mean) / std + beta
        }
    }
}
```

#### ViViT Implementation in Burn

```rust
// crates/vision/src/vivit/model.rs

use burn::module::Module;
use burn::nn::{
    Embedding, EmbeddingConfig,
    Linear, LinearConfig,
    LayerNorm, LayerNormConfig,
    Dropout, DropoutConfig,
};
use burn::tensor::{backend::Backend, Tensor};

/// Video Vision Transformer configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ViViTConfig {
    pub image_size: usize,
    pub patch_size: usize,
    pub num_frames: usize,
    pub num_channels: usize,
    pub embed_dim: usize,
    pub depth: usize,
    pub num_heads: usize,
    pub mlp_ratio: f32,
    pub dropout: f32,
    pub attention_dropout: f32,
    /// Factorization strategy
    pub factorization: ViViTFactorization,
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
pub enum ViViTFactorization {
    /// Space then time attention (more efficient)
    SpaceThenTime,
    /// Joint space-time attention (more accurate)
    JointSpaceTime,
}

impl Default for ViViTConfig {
    fn default() -> Self {
        Self {
            image_size: 32,
            patch_size: 4,
            num_frames: 8,
            num_channels: 1,
            embed_dim: 256,
            depth: 6,
            num_heads: 8,
            mlp_ratio: 4.0,
            dropout: 0.1,
            attention_dropout: 0.1,
            factorization: ViViTFactorization::SpaceThenTime,
        }
    }
}

/// Video Vision Transformer
#[derive(Module, Debug)]
pub struct ViViT<B: Backend> {
    /// Patch embedding projection
    patch_embed: Linear<B>,
    /// Spatial position embedding
    spatial_pos_embed: Tensor<B, 2>,
    /// Temporal position embedding
    temporal_pos_embed: Tensor<B, 2>,
    /// CLS token
    cls_token: Tensor<B, 2>,
    /// Spatial transformer blocks
    spatial_blocks: Vec<TransformerBlock<B>>,
    /// Temporal transformer blocks
    temporal_blocks: Vec<TransformerBlock<B>>,
    /// Output layer norm
    norm: LayerNorm<B>,
    /// Dropout
    dropout: Dropout,
    /// Configuration
    config: ViViTConfig,
}

impl<B: Backend> ViViT<B> {
    /// Create new ViViT model
    pub fn new(config: &ViViTConfig, device: &B::Device) -> Self {
        let num_patches = (config.image_size / config.patch_size).pow(2);
        let patch_dim = config.num_channels * config.patch_size * config.patch_size;
        
        // Patch embedding
        let patch_embed = LinearConfig::new(patch_dim, config.embed_dim)
            .init(device);
        
        // Position embeddings
        let spatial_pos_embed = Tensor::randn(
            [1, num_patches + 1, config.embed_dim],
            device,
        ) * 0.02;
        
        let temporal_pos_embed = Tensor::randn(
            [1, config.num_frames, config.embed_dim],
            device,
        ) * 0.02;
        
        // CLS token
        let cls_token = Tensor::randn([1, 1, config.embed_dim], device) * 0.02;
        
        // Transformer blocks
        let block_config = TransformerBlockConfig {
            embed_dim: config.embed_dim,
            num_heads: config.num_heads,
            mlp_ratio: config.mlp_ratio,
            dropout: config.dropout,
            attention_dropout: config.attention_dropout,
        };
        
        let spatial_blocks = (0..config.depth)
            .map(|_| TransformerBlock::new(&block_config, device))
            .collect();
            
        let temporal_blocks = (0..config.depth)
            .map(|_| TransformerBlock::new(&block_config, device))
            .collect();
        
        let norm = LayerNormConfig::new(config.embed_dim).init(device);
        let dropout = DropoutConfig::new(config.dropout).init();
        
        Self {
            patch_embed,
            spatial_pos_embed,
            temporal_pos_embed,
            cls_token,
            spatial_blocks,
            temporal_blocks,
            norm,
            dropout,
            config: config.clone(),
        }
    }
    
    /// Forward pass
    /// Input: [batch, num_frames, channels, height, width]
    /// Output: [batch, embed_dim]
    pub fn forward(&self, x: Tensor<B, 5>) -> Tensor<B, 2> {
        let [batch, num_frames, channels, height, width] = x.dims();
        let num_patches = (height / self.config.patch_size) * (width / self.config.patch_size);
        
        // Step 1: Patchify and embed
        // [batch, frames, channels, H, W] -> [batch * frames, num_patches, embed_dim]
        let patches = self.patchify(x);
        let embedded = self.patch_embed.forward(patches);
        
        // Step 2: Add spatial position embedding and CLS token
        let cls_tokens = self.cls_token
            .clone()
            .expand([batch * num_frames, 1, self.config.embed_dim]);
        let embedded = Tensor::cat(vec![cls_tokens, embedded], 1);
        let embedded = embedded + self.spatial_pos_embed.clone();
        let embedded = self.dropout.forward(embedded);
        
        // Step 3: Spatial attention (per frame)
        let mut spatial_out = embedded;
        for block in &self.spatial_blocks {
            spatial_out = block.forward(spatial_out);
        }
        
        // Step 4: Extract CLS tokens and reshape for temporal attention
        // [batch * frames, num_patches + 1, embed_dim] -> [batch, frames, embed_dim]
        let cls_tokens = spatial_out.slice([0..batch * num_frames, 0..1, 0..self.config.embed_dim]);
        let cls_tokens = cls_tokens.reshape([batch, num_frames, self.config.embed_dim]);
        
        // Step 5: Add temporal position embedding
        let temporal_in = cls_tokens + self.temporal_pos_embed.clone();
        
        // Step 6: Temporal attention
        let mut temporal_out = temporal_in;
        for block in &self.temporal_blocks {
            temporal_out = block.forward(temporal_out);
        }
        
        // Step 7: Final representation (mean over time or first token)
        let output = temporal_out.mean_dim(1);
        
        self.norm.forward(output)
    }
    
    /// Convert image to patches
    fn patchify(&self, x: Tensor<B, 5>) -> Tensor<B, 3> {
        let [batch, frames, channels, height, width] = x.dims();
        let p = self.config.patch_size;
        let h_patches = height / p;
        let w_patches = width / p;
        
        // Reshape to extract patches
        x.reshape([batch * frames, channels, h_patches, p, w_patches, p])
            .swap_dims(2, 3)
            .reshape([batch * frames, h_patches * w_patches, channels * p * p])
    }
}

/// Transformer block with self-attention and MLP
#[derive(Module, Debug)]
pub struct TransformerBlock<B: Backend> {
    attention: MultiHeadAttention<B>,
    mlp: MLP<B>,
    norm1: LayerNorm<B>,
    norm2: LayerNorm<B>,
    dropout: Dropout,
}

// ... (MultiHeadAttention and MLP implementations)
```

#### Deliverables

- [ ] DiffGAF in Burn with learnable params
- [ ] GAF video generation
- [ ] ViViT with factorized attention
- [ ] Full vision pipeline
- [ ] Unit tests for all components
- [ ] Benchmark vs Candle implementation

---

### Week 7: Logic Tensor Networks (LTN) & Neuro-Symbolic Fusion

**Objective**: Enhance LTN implementation and integrate with Burn for end-to-end differentiable reasoning.

#### Tasks

| Task | Description | Crate/Service | Priority |
|------|-------------|---------------|----------|
| 7.1 | Port LTN to use Burn tensors | `crates/ltn` | P0 |
| 7.2 | Implement predicate neural networks | `crates/ltn` | P0 |
| 7.3 | Add trading-specific axioms | `crates/ltn` | P0 |
| 7.4 | Implement Gated Cross-Attention fusion | `crates/fusion` | P0 |
| 7.5 | Add compliance constraints | `crates/ltn` | P1 |
| 7.6 | Create LTN loss integration | `crates/training` | P0 |
| 7.7 | Add symbolic reasoning dashboard | `crates/cns` | P2 |

#### LTN Crate Refactor

```
crates/ltn/
├── Cargo.toml
└── src/
    ├── lib.rs
    ├── core/
    │   ├── mod.rs
    │   ├── grounding.rs      # Variable grounding
    │   ├── predicate.rs      # Predicate networks
    │   ├── function.rs       # Function symbols
    │   └── constant.rs       # Constants
    ├── logic/
    │   ├── mod.rs
    │   ├── connective.rs     # Logical connectives
    │   ├── quantifier.rs     # Quantifiers (ForAll, Exists)
    │   ├── tnorm.rs          # T-norm implementations
    │   └── aggregator.rs     # Aggregation functions
    ├── axioms/
    │   ├── mod.rs
    │   ├── trading.rs        # Trading axioms
    │   ├── risk.rs           # Risk constraints
    │   └── compliance.rs     # Regulatory compliance
    ├── loss.rs               # LTN loss functions
    └── fusion.rs             # Multimodal fusion
```

#### LTN with Burn

```rust
// crates/ltn/src/core/predicate.rs

use burn::module::Module;
use burn::nn::{Linear, LinearConfig, Relu};
use burn::tensor::{backend::Backend, Tensor};

/// Neural predicate network
/// Maps entity embeddings to truth values [0, 1]
#[derive(Module, Debug)]
pub struct Predicate<B: Backend> {
    name: String,
    arity: usize,
    layers: Vec<Linear<B>>,
    activation: Relu,
}

impl<B: Backend> Predicate<B> {
    /// Create a new predicate network
    pub fn new(
        name: &str,
        arity: usize,
        input_dim: usize,
        hidden_dims: &[usize],
        device: &B::Device,
    ) -> Self {
        let total_input = input_dim * arity;
        let mut layers = Vec::new();
        let mut in_dim = total_input;
        
        for &hidden_dim in hidden_dims {
            layers.push(LinearConfig::new(in_dim, hidden_dim).init(device));
            in_dim = hidden_dim;
        }
        
        // Final layer outputs single truth value
        layers.push(LinearConfig::new(in_dim, 1).init(device));
        
        Self {
            name: name.to_string(),
            arity,
            layers,
            activation: Relu::new(),
        }
    }
    
    /// Compute truth value for grounded entities
    /// Input: [batch, arity, embedding_dim]
    /// Output: [batch, 1] with values in [0, 1]
    pub fn forward(&self, entities: Tensor<B, 3>) -> Tensor<B, 2> {
        let [batch, arity, embed_dim] = entities.dims();
        assert_eq!(arity, self.arity, "Arity mismatch");
        
        // Flatten entities: [batch, arity * embed_dim]
        let mut x = entities.reshape([batch, arity * embed_dim]);
        
        // Forward through layers
        for (i, layer) in self.layers.iter().enumerate() {
            x = layer.forward(x);
            if i < self.layers.len() - 1 {
                x = self.activation.forward(x);
            }
        }
        
        // Sigmoid to get truth value in [0, 1]
        x.sigmoid()
    }
}

/// Grounding: maps symbols to tensor representations
pub struct Grounding<B: Backend> {
    variables: HashMap<String, Tensor<B, 2>>,
    constants: HashMap<String, Tensor<B, 1>>,
}

impl<B: Backend> Grounding<B> {
    /// Ground a variable with tensor values
    pub fn set_variable(&mut self, name: &str, value: Tensor<B, 2>) {
        self.variables.insert(name.to_string(), value);
    }
    
    /// Get grounded variable
    pub fn get(&self, name: &str) -> Option<&Tensor<B, 2>> {
        self.variables.get(name)
    }
}
```

#### Lukasiewicz T-Norm Operations

```rust
// crates/ltn/src/logic/tnorm.rs

use burn::tensor::{backend::Backend, Tensor};

/// T-norm implementations for fuzzy logic
pub trait TNorm<B: Backend> {
    /// Conjunction (AND)
    fn and(&self, a: Tensor<B, 2>, b: Tensor<B, 2>) -> Tensor<B, 2>;
    
    /// Disjunction (OR)
    fn or(&self, a: Tensor<B, 2>, b: Tensor<B, 2>) -> Tensor<B, 2>;
    
    /// Negation (NOT)
    fn not(&self, a: Tensor<B, 2>) -> Tensor<B, 2>;
    
    /// Implication (IF-THEN)
    fn implies(&self, a: Tensor<B, 2>, b: Tensor<B, 2>) -> Tensor<B, 2>;
}

/// Lukasiewicz t-norm (differentiable)
pub struct LukasiewiczTNorm;

impl<B: Backend> TNorm<B> for LukasiewiczTNorm {
    /// AND(a, b) = max(0, a + b - 1)
    fn and(&self, a: Tensor<B, 2>, b: Tensor<B, 2>) -> Tensor<B, 2> {
        (a + b - 1.0).clamp_min(0.0)
    }
    
    /// OR(a, b) = min(1, a + b)
    fn or(&self, a: Tensor<B, 2>, b: Tensor<B, 2>) -> Tensor<B, 2> {
        (a + b).clamp_max(1.0)
    }
    
    /// NOT(a) = 1 - a
    fn not(&self, a: Tensor<B, 2>) -> Tensor<B, 2> {
        1.0 - a
    }
    
    /// IMPLIES(a, b) = min(1, 1 - a + b)
    fn implies(&self, a: Tensor<B, 2>, b: Tensor<B, 2>) -> Tensor<B, 2> {
        (1.0 - a + b).clamp_max(1.0)
    }
}

/// Product t-norm (smooth gradients)
pub struct ProductTNorm;

impl<B: Backend> TNorm<B> for ProductTNorm {
    fn and(&self, a: Tensor<B, 2>, b: Tensor<B, 2>) -> Tensor<B, 2> {
        a * b
    }
    
    fn or(&self, a: Tensor<B, 2>, b: Tensor<B, 2>) -> Tensor<B, 2> {
        a.clone() + b.clone() - a * b
    }
    
    fn not(&self, a: Tensor<B, 2>) -> Tensor<B, 2> {
        1.0 - a
    }
    
    fn implies(&self, a: Tensor<B, 2>, b: Tensor<B, 2>) -> Tensor<B, 2> {
        // Reichenbach implication: 1 - a + a*b
        1.0 - a.clone() + a * b
    }
}
```

#### Trading Axioms

```rust
// crates/ltn/src/axioms/trading.rs

use crate::logic::{TNorm, Quantifier};
use crate::core::Predicate;

/// Trading-specific axioms for LTN
pub struct TradingAxioms<B: Backend> {
    /// Predicates
    pub is_bullish: Predicate<B>,
    pub is_bearish: Predicate<B>,
    pub high_volatility: Predicate<B>,
    pub sufficient_liquidity: Predicate<B>,
    pub within_risk_limits: Predicate<B>,
    pub wash_sale_compliant: Predicate<B>,
}

impl<B: Backend> TradingAxioms<B> {
    /// Create trading axioms
    pub fn new(embed_dim: usize, device: &B::Device) -> Self {
        Self {
            is_bullish: Predicate::new("is_bullish", 1, embed_dim, &[128, 64], device),
            is_bearish: Predicate::new("is_bearish", 1, embed_dim, &[128, 64], device),
            high_volatility: Predicate::new("high_volatility", 1, embed_dim, &[64], device),
            sufficient_liquidity: Predicate::new("sufficient_liquidity", 1, embed_dim, &[64], device),
            within_risk_limits: Predicate::new("within_risk_limits", 2, embed_dim, &[128, 64], device),
            wash_sale_compliant: Predicate::new("wash_sale_compliant", 2, embed_dim, &[64], device),
        }
    }
    
    /// Axiom: ∀x: IsBullish(x) ∧ SufficientLiquidity(x) → CanBuy(x)
    pub fn buy_axiom<T: TNorm<B>>(&self, tnorm: &T, market: Tensor<B, 2>) -> Tensor<B, 2> {
        let bullish = self.is_bullish.forward(market.clone().unsqueeze_dim(1));
        let liquid = self.sufficient_liquidity.forward(market.clone().unsqueeze_dim(1));
        tnorm.and(bullish, liquid)
    }
    
    /// Axiom: ∀x: IsBearish(x) ∧ HighVolatility(x) → ShouldReducePosition(x)
    pub fn risk_reduction_axiom<T: TNorm<B>>(&self, tnorm: &T, market: Tensor<B, 2>) -> Tensor<B, 2> {
        let bearish = self.is_bearish.forward(market.clone().unsqueeze_dim(1));
        let volatile = self.high_volatility.forward(market.clone().unsqueeze_dim(1));
        tnorm.and(bearish, volatile)
    }
    
    /// Compute satisfiability aggregation for all axioms
    pub fn compute_sat(&self, market: Tensor<B, 2>) -> Tensor<B, 1> {
        // Aggregate all axiom satisfactions
        let tnorm = LukasiewiczTNorm;
        let buy_sat = self.buy_axiom(&tnorm, market.clone());
        let risk_sat = self.risk_reduction_axiom(&tnorm, market);
        
        // Product aggregation
        (buy_sat * risk_sat).mean_dim(1)
    }
}
```

#### Gated Cross-Attention Fusion

```rust
// crates/fusion/src/cross_attention.rs

use burn::module::Module;
use burn::nn::{Linear, LinearConfig, LayerNorm, LayerNormConfig, Dropout, DropoutConfig};
use burn::tensor::{backend::Backend, Tensor};

/// Gated Cross-Attention for multimodal fusion
/// Fuses visual (GAF/ViViT), symbolic (LTN), and numerical features
#[derive(Module, Debug)]
pub struct GatedCrossAttention<B: Backend> {
    /// Query projection for primary modality
    query: Linear<B>,
    /// Key projection for secondary modality
    key: Linear<B>,
    /// Value projection for secondary modality
    value: Linear<B>,
    /// Output projection
    output: Linear<B>,
    /// Gating network
    gate: Linear<B>,
    /// Layer normalization
    norm: LayerNorm<B>,
    /// Dropout
    dropout: Dropout,
    /// Configuration
    num_heads: usize,
    head_dim: usize,
}

#[derive(Debug, Clone)]
pub struct GatedCrossAttentionConfig {
    pub embed_dim: usize,
    pub num_heads: usize,
    pub dropout: f32,
}

impl<B: Backend> GatedCrossAttention<B> {
    pub fn new(config: &GatedCrossAttentionConfig, device: &B::Device) -> Self {
        let head_dim = config.embed_dim / config.num_heads;
        
        Self {
            query: LinearConfig::new(config.embed_dim, config.embed_dim).init(device),
            key: LinearConfig::new(config.embed_dim, config.embed_dim).init(device),
            value: LinearConfig::new(config.embed_dim, config.embed_dim).init(device),
            output: LinearConfig::new(config.embed_dim, config.embed_dim).init(device),
            gate: LinearConfig::new(config.embed_dim * 2, config.embed_dim).init(device),
            norm: LayerNormConfig::new(config.embed_dim).init(device),
            dropout: DropoutConfig::new(config.dropout).init(),
            num_heads: config.num_heads,
            head_dim,
        }
    }
    
    /// Forward pass
    /// primary: [batch, seq_len_p, embed_dim] - main modality (e.g., visual)
    /// secondary: [batch, seq_len_s, embed_dim] - secondary modality (e.g., LTN)
    /// Output: [batch, seq_len_p, embed_dim] - fused representation
    pub fn forward(&self, primary: Tensor<B, 3>, secondary: Tensor<B, 3>) -> Tensor
<B, 3> {
        let [batch, seq_p, embed] = primary.dims();
        let [_, seq_s, _] = secondary.dims();
        
        // Project queries from primary, keys/values from secondary
        let q = self.query.forward(primary.clone())
            .reshape([batch, seq_p, self.num_heads, self.head_dim])
            .swap_dims(1, 2);
        let k = self.key.forward(secondary.clone())
            .reshape([batch, seq_s, self.num_heads, self.head_dim])
            .swap_dims(1, 2);
        let v = self.value.forward(secondary)
            .reshape([batch, seq_s, self.num_heads, self.head_dim])
            .swap_dims(1, 2);
        
        // Scaled dot-product attention
        let scale = (self.head_dim as f32).sqrt();
        let attn_weights = (q.matmul(k.swap_dims(2, 3)) / scale).softmax_dim(3);
        let attn_output = self.dropout.forward(attn_weights).matmul(v);
        
        // Reshape back
        let attn_output = attn_output
            .swap_dims(1, 2)
            .reshape([batch, seq_p, embed]);
        let attn_output = self.output.forward(attn_output);
        
        // Gating mechanism
        let concat = Tensor::cat(vec![primary.clone(), attn_output.clone()], 2);
        let gate = self.gate.forward(concat).sigmoid();
        
        // Gated fusion with residual
        let fused = gate.clone() * attn_output + (1.0 - gate) * primary;
        
        self.norm.forward(fused)
    }
}
```

#### CNS Metrics (New)

```rust
// LTN and fusion metrics
pub ltn_axiom_satisfaction: GaugeVec,              // by axiom_name
pub ltn_predicate_confidence: GaugeVec,            // by predicate_name
pub ltn_logic_loss: Gauge,
pub fusion_gate_values: HistogramVec,              // by modality_pair
pub fusion_attention_entropy: Gauge,
```

#### Deliverables

- [ ] LTN ported to Burn tensors
- [ ] Trading axioms implemented
- [ ] Compliance constraints (wash sale, risk limits)
- [ ] Gated Cross-Attention fusion
- [ ] LTN loss integration in training
- [ ] Symbolic reasoning metrics in CNS

---

### Week 8: Training Pipeline & Experience Replay

**Objective**: Complete the training infrastructure with prioritized experience replay and memory consolidation.

#### Tasks

| Task | Description | Crate/Service | Priority |
|------|-------------|---------------|----------|
| 8.1 | Port experience replay to Burn | `crates/training` | P0 |
| 8.2 | Implement SWR (Sharp Wave Ripple) sampling | `crates/training` | P0 |
| 8.3 | Add importance sampling correction | `crates/training` | P1 |
| 8.4 | Implement schema consolidation | `crates/memory` | P0 |
| 8.5 | Add Qdrant vector storage integration | `crates/memory` | P0 |
| 8.6 | Create training data pipeline | `services/backward` | P0 |
| 8.7 | Implement model versioning | `crates/training` | P1 |

#### Prioritized Experience Replay

```rust
// crates/training/src/replay/per.rs

use burn::tensor::{backend::Backend, Tensor};
use std::collections::BinaryHeap;

/// Prioritized Experience Replay buffer with SWR sampling
pub struct PrioritizedReplayBuffer<B: Backend> {
    capacity: usize,
    experiences: Vec<Experience<B>>,
    priorities: Vec<f32>,
    sum_tree: SumTree,
    alpha: f32,  // Priority exponent
    beta: f32,   // Importance sampling exponent
    beta_increment: f32,
    min_priority: f32,
}

/// Single experience tuple
#[derive(Debug, Clone)]
pub struct Experience<B: Backend> {
    pub state: Tensor<B, 2>,
    pub action: Tensor<B, 1>,
    pub reward: f32,
    pub next_state: Tensor<B, 2>,
    pub done: bool,
    pub td_error: f32,
    pub timestamp: i64,
    pub metadata: ExperienceMetadata,
}

#[derive(Debug, Clone)]
pub struct ExperienceMetadata {
    pub symbol: String,
    pub regime: MarketRegime,
    pub volatility: f32,
    pub spread: f32,
}

impl<B: Backend> PrioritizedReplayBuffer<B> {
    pub fn new(capacity: usize, alpha: f32, beta_start: f32) -> Self {
        Self {
            capacity,
            experiences: Vec::with_capacity(capacity),
            priorities: Vec::with_capacity(capacity),
            sum_tree: SumTree::new(capacity),
            alpha,
            beta: beta_start,
            beta_increment: (1.0 - beta_start) / 100_000.0,
            min_priority: 1e-6,
        }
    }
    
    /// Add experience with priority
    pub fn push(&mut self, experience: Experience<B>, td_error: f32) {
        let priority = (td_error.abs() + self.min_priority).powf(self.alpha);
        
        if self.experiences.len() < self.capacity {
            self.experiences.push(experience);
            self.priorities.push(priority);
            self.sum_tree.update(self.experiences.len() - 1, priority);
        } else {
            // Replace lowest priority experience
            let idx = self.find_min_priority_idx();
            self.experiences[idx] = experience;
            self.priorities[idx] = priority;
            self.sum_tree.update(idx, priority);
        }
    }
    
    /// Sample batch with SWR-style prioritization
    pub fn sample_swr(&mut self, batch_size: usize) -> ReplayBatch<B> {
        let total = self.sum_tree.total();
        let segment = total / batch_size as f32;
        
        let mut indices = Vec::with_capacity(batch_size);
        let mut weights = Vec::with_capacity(batch_size);
        
        // SWR-style: prefer recent experiences with high TD error
        for i in 0..batch_size {
            let low = segment * i as f32;
            let high = segment * (i + 1) as f32;
            let value = rand::random::<f32>() * (high - low) + low;
            
            let idx = self.sum_tree.get(value);
            indices.push(idx);
            
            // Importance sampling weight
            let prob = self.priorities[idx] / total;
            let weight = (self.experiences.len() as f32 * prob).powf(-self.beta);
            weights.push(weight);
        }
        
        // Normalize weights
        let max_weight = weights.iter().cloned().fold(0.0f32, f32::max);
        let weights: Vec<f32> = weights.iter().map(|w| w / max_weight).collect();
        
        // Anneal beta
        self.beta = (self.beta + self.beta_increment).min(1.0);
        
        self.collect_batch(&indices, &weights)
    }
    
    /// Update priorities after training
    pub fn update_priorities(&mut self, indices: &[usize], td_errors: &[f32]) {
        for (&idx, &td_error) in indices.iter().zip(td_errors.iter()) {
            let priority = (td_error.abs() + self.min_priority).powf(self.alpha);
            self.priorities[idx] = priority;
            self.sum_tree.update(idx, priority);
        }
    }
    
    fn collect_batch(&self, indices: &[usize], weights: &[f32]) -> ReplayBatch<B> {
        // Collect tensors for batch
        // ... implementation
        todo!()
    }
    
    fn find_min_priority_idx(&self) -> usize {
        self.priorities
            .iter()
            .enumerate()
            .min_by(|a, b| a.1.partial_cmp(b.1).unwrap())
            .map(|(i, _)| i)
            .unwrap_or(0)
    }
}

/// Sum tree for efficient priority sampling
struct SumTree {
    capacity: usize,
    tree: Vec<f32>,
}

impl SumTree {
    fn new(capacity: usize) -> Self {
        let size = 2 * capacity - 1;
        Self {
            capacity,
            tree: vec![0.0; size],
        }
    }
    
    fn update(&mut self, idx: usize, priority: f32) {
        let tree_idx = idx + self.capacity - 1;
        let delta = priority - self.tree[tree_idx];
        self.tree[tree_idx] = priority;
        
        // Propagate up
        let mut parent = tree_idx;
        while parent > 0 {
            parent = (parent - 1) / 2;
            self.tree[parent] += delta;
        }
    }
    
    fn get(&self, value: f32) -> usize {
        let mut idx = 0;
        let mut value = value;
        
        while idx < self.capacity - 1 {
            let left = 2 * idx + 1;
            let right = left + 1;
            
            if value <= self.tree[left] {
                idx = left;
            } else {
                value -= self.tree[left];
                idx = right;
            }
        }
        
        idx - self.capacity + 1
    }
    
    fn total(&self) -> f32 {
        self.tree[0]
    }
}
```

#### Schema Consolidation with Qdrant

```rust
// crates/memory/src/consolidation.rs

use qdrant_client::client::QdrantClient;
use qdrant_client::qdrant::{
    PointStruct, SearchPoints, UpsertPointsBuilder,
    vectors_config::Config, VectorParams, Distance,
};
use burn::tensor::{backend::Backend, Tensor};

/// Schema consolidation engine
pub struct SchemaConsolidator<B: Backend> {
    client: QdrantClient,
    collection_name: String,
    embed_dim: usize,
    num_clusters: usize,
    _phantom: std::marker::PhantomData<B>,
}

/// Market regime schema
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MarketSchema {
    pub id: Uuid,
    pub regime: MarketRegime,
    pub centroid: Vec<f32>,
    pub member_count: u64,
    pub avg_return: f32,
    pub volatility: f32,
    pub created_at: DateTime<Utc>,
    pub updated_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq)]
pub enum MarketRegime {
    Trending,
    MeanReverting,
    HighVolatility,
    LowVolatility,
    Consolidation,
    Breakout,
}

impl<B: Backend> SchemaConsolidator<B> {
    pub async fn new(
        qdrant_url: &str,
        collection_name: &str,
        embed_dim: usize,
    ) -> Result<Self> {
        let client = QdrantClient::from_url(qdrant_url).build()?;
        
        // Ensure collection exists
        let collections = client.list_collections().await?;
        if !collections.collections.iter().any(|c| c.name == collection_name) {
            client.create_collection(&CreateCollectionBuilder::new(collection_name)
                .vectors_config(VectorParams {
                    size: embed_dim as u64,
                    distance: Distance::Cosine.into(),
                    ..Default::default()
                }))
                .await?;
        }
        
        Ok(Self {
            client,
            collection_name: collection_name.to_string(),
            embed_dim,
            num_clusters: 8,
            _phantom: std::marker::PhantomData,
        })
    }
    
    /// Consolidate experiences into schemas (nightly process)
    pub async fn consolidate(&self, experiences: &[Experience<B>]) -> Result<Vec<MarketSchema>> {
        // Step 1: Extract embeddings
        let embeddings: Vec<Vec<f32>> = experiences
            .iter()
            .map(|e| e.state.clone().into_data().value)
            .collect();
        
        // Step 2: K-means clustering
        let clusters = self.kmeans_cluster(&embeddings, self.num_clusters)?;
        
        // Step 3: Create/update schemas
        let mut schemas = Vec::new();
        for (cluster_id, members) in clusters.iter().enumerate() {
            if members.is_empty() {
                continue;
            }
            
            // Compute centroid
            let centroid = self.compute_centroid(&embeddings, members);
            
            // Compute statistics
            let returns: Vec<f32> = members.iter()
                .map(|&i| experiences[i].reward)
                .collect();
            let avg_return = returns.iter().sum::<f32>() / returns.len() as f32;
            let volatility = self.compute_volatility(&returns);
            
            // Classify regime
            let regime = self.classify_regime(avg_return, volatility);
            
            let schema = MarketSchema {
                id: Uuid::new_v4(),
                regime,
                centroid: centroid.clone(),
                member_count: members.len() as u64,
                avg_return,
                volatility,
                created_at: Utc::now(),
                updated_at: Utc::now(),
            };
            
            // Upsert to Qdrant
            self.upsert_schema(&schema).await?;
            schemas.push(schema);
        }
        
        Ok(schemas)
    }
    
    /// Find similar schemas for a state
    pub async fn find_similar(&self, state: &Tensor<B, 2>, top_k: usize) -> Result<Vec<MarketSchema>> {
        let vector: Vec<f32> = state.clone().into_data().value;
        
        let results = self.client
            .search_points(&SearchPoints {
                collection_name: self.collection_name.clone(),
                vector: vector,
                limit: top_k as u64,
                with_payload: Some(true.into()),
                ..Default::default()
            })
            .await?;
        
        results.result
            .into_iter()
            .map(|p| serde_json::from_value(p.payload.into()).map_err(Into::into))
            .collect()
    }
    
    async fn upsert_schema(&self, schema: &MarketSchema) -> Result<()> {
        let point = PointStruct {
            id: Some(schema.id.to_string().into()),
            vectors: Some(schema.centroid.clone().into()),
            payload: serde_json::to_value(schema)?.as_object().cloned().unwrap_or_default()
                .into_iter()
                .map(|(k, v)| (k, v.into()))
                .collect(),
        };
        
        self.client
            .upsert_points(UpsertPointsBuilder::new(&self.collection_name, vec![point]))
            .await?;
        
        Ok(())
    }
    
    fn kmeans_cluster(&self, embeddings: &[Vec<f32>], k: usize) -> Result<Vec<Vec<usize>>> {
        // Simple k-means implementation
        // ... implementation
        todo!()
    }
    
    fn compute_centroid(&self, embeddings: &[Vec<f32>], indices: &[usize]) -> Vec<f32> {
        let dim = embeddings[0].len();
        let mut centroid = vec![0.0; dim];
        
        for &idx in indices {
            for (i, &v) in embeddings[idx].iter().enumerate() {
                centroid[i] += v;
            }
        }
        
        let n = indices.len() as f32;
        centroid.iter_mut().for_each(|v| *v /= n);
        centroid
    }
    
    fn compute_volatility(&self, returns: &[f32]) -> f32 {
        let mean = returns.iter().sum::<f32>() / returns.len() as f32;
        let variance = returns.iter()
            .map(|r| (r - mean).powi(2))
            .sum::<f32>() / returns.len() as f32;
        variance.sqrt()
    }
    
    fn classify_regime(&self, avg_return: f32, volatility: f32) -> MarketRegime {
        if volatility > 0.03 {
            MarketRegime::HighVolatility
        } else if volatility < 0.01 {
            MarketRegime::LowVolatility
        } else if avg_return.abs() > 0.02 {
            MarketRegime::Trending
        } else {
            MarketRegime::MeanReverting
        }
    }
}
```

#### CNS Metrics (New)

```rust
// Memory and replay metrics
pub memory_replay_buffer_size: IntGauge,
pub memory_replay_samples_total: IntCounter,
pub memory_replay_priority_mean: Gauge,
pub memory_replay_beta: Gauge,
pub memory_schemas_total: IntGauge,
pub memory_schema_consolidations: IntCounter,
pub memory_qdrant_upserts: IntCounterVec,          // by collection
pub memory_qdrant_searches: IntCounterVec,         // by collection
pub memory_qdrant_latency_ms: HistogramVec,        // by operation
```

#### Deliverables

- [ ] PER with SWR sampling
- [ ] Importance sampling correction
- [ ] Schema consolidation working
- [ ] Qdrant integration tested
- [ ] Training data pipeline complete
- [ ] Model versioning system
- [ ] Memory metrics in CNS

---

## Phase 3: Signal Generation & Integration (Weeks 9-12)

### Week 9: Neuromorphic Core Integration

**Objective**: Wire up all neuromorphic brain regions into a coherent decision-making system.

#### Tasks

| Task | Description | Crate/Service | Priority |
|------|-------------|---------------|----------|
| 9.1 | Integrate Cortex with trained models | `neuromorphic/cortex` | P0 |
| 9.2 | Wire Hippocampus to schema storage | `neuromorphic/hippocampus` | P0 |
| 9.3 | Implement Basal Ganglia action selection | `neuromorphic/basal_ganglia` | P0 |
| 9.4 | Add Amygdala risk circuit breakers | `neuromorphic/amygdala` | P0 |
| 9.5 | Implement Cerebellum execution planning | `neuromorphic/cerebellum` | P1 |
| 9.6 | Create brain region communication bus | `neuromorphic/integration` | P0 |
| 9.7 | Add neuromorphic metrics | `crates/cns` | P1 |

#### Brain Integration Bus

```rust
// neuromorphic/integration/src/bus.rs

use tokio::sync::broadcast;
use std::sync::Arc;

/// Inter-region communication bus
pub struct BrainBus {
    /// Cortex → other regions: strategic signals
    cortex_tx: broadcast::Sender<CortexSignal>,
    /// Hippocampus → Cortex: memory retrieval
    hippocampus_tx: broadcast::Sender<HippocampusSignal>,
    /// Basal Ganglia → Cerebellum: action decisions
    basal_ganglia_tx: broadcast::Sender<BasalGangliaSignal>,
    /// Amygdala → all: risk alerts
    amygdala_tx: broadcast::Sender<AmygdalaSignal>,
    /// Cerebellum → output: execution plans
    cerebellum_tx: broadcast::Sender<CerebellumSignal>,
}

/// Strategic signal from Cortex
#[derive(Debug, Clone)]
pub struct CortexSignal {
    pub timestamp: i64,
    pub market_view: MarketView,
    pub confidence: f32,
    pub time_horizon: TimeHorizon,
}

/// Memory signal from Hippocampus
#[derive(Debug, Clone)]
pub struct HippocampusSignal {
    pub similar_episodes: Vec<EpisodeMatch>,
    pub regime_prediction: MarketRegime,
    pub pattern_confidence: f32,
}

/// Action signal from Basal Ganglia
#[derive(Debug, Clone)]
pub struct BasalGangliaSignal {
    pub action: TradingAction,
    pub go_pathway_strength: f32,
    pub nogo_pathway_strength: f32,
    pub selected: bool,
}

/// Risk signal from Amygdala
#[derive(Debug, Clone)]
pub struct AmygdalaSignal {
    pub threat_level: ThreatLevel,
    pub circuit_breaker_triggered: bool,
    pub risk_factors: Vec<RiskFactor>,
}

/// Execution plan from Cerebellum
#[derive(Debug, Clone)]
pub struct CerebellumSignal {
    pub execution_plan: ExecutionPlan,
    pub predicted_impact: f32,
    pub optimal_timing: i64,
}

impl BrainBus {
    pub fn new() -> Self {
        Self {
            cortex_tx: broadcast::channel(1000).0,
            hippocampus_tx: broadcast::channel(1000).0,
            basal_ganglia_tx: broadcast::channel(1000).0,
            amygdala_tx: broadcast::channel(100).0,  // Higher priority
            cerebellum_tx: broadcast::channel(1000).0,
        }
    }
    
    pub fn subscribe_cortex(&self) -> broadcast::Receiver<CortexSignal> {
        self.cortex_tx.subscribe()
    }
    
    pub fn subscribe_amygdala(&self) -> broadcast::Receiver<AmygdalaSignal> {
        self.amygdala_tx.subscribe()
    }
    
    // ... other subscription methods
}
```

#### Basal Ganglia Action Selection

```rust
// neuromorphic/basal_ganglia/src/action_selection.rs

use burn::module::Module;
use burn::nn::{Linear, LinearConfig};
use burn::tensor::{backend::Backend, Tensor};

/// Basal Ganglia dual-pathway action selection
#[derive(Module, Debug)]
pub struct BasalGanglia<B: Backend> {
    /// Direct pathway (Go signal)
    direct_pathway: DirectPathway<B>,
    /// Indirect pathway (No-Go signal)
    indirect_pathway: IndirectPathway<B>,
    /// Dopamine modulation
    dopamine_gate: Linear<B>,
    /// Action output
    action_head: Linear<B>,
}

#[derive(Module, Debug)]
struct DirectPathway<B: Backend> {
    striatum_d1: Linear<B>,  // D1 receptors (excitatory)
    gpi: Linear<B>,          // Globus Pallidus internal
    thalamus: Linear<B>,
}

#[derive(Module, Debug)]
struct IndirectPathway<B: Backend> {
    striatum_d2: Linear<B>,  // D2 receptors (inhibitory)
    gpe: Linear<B>,          // Globus Pallidus external
    stn: Linear<B>,          // Subthalamic Nucleus
    gpi: Linear<B>,
    thalamus: Linear<B>,
}

impl<B: Backend> BasalGanglia<B> {
    pub fn new(input_dim: usize, hidden_dim: usize, num_actions: usize, device: &B::Device) -> Self {
        Self {
            direct_pathway: DirectPathway {
                striatum_d1: LinearConfig::new(input_dim, hidden_dim).init(device),
                gpi: LinearConfig::new(hidden_dim, hidden_dim).init(device),
                thalamus: LinearConfig::new(hidden_dim, hidden_dim).init(device),
            },
            indirect_pathway: IndirectPathway {
                striatum_d2: LinearConfig::new(input_dim, hidden_dim).init(device),
                gpe: LinearConfig::new(hidden_dim, hidden_dim).init(device),
                stn: LinearConfig::new(hidden_dim, hidden_dim).init(device),
                gpi: LinearConfig::new(hidden_dim, hidden_dim).init(device),
                thalamus: LinearConfig::new(hidden_dim, hidden_dim).init(device),
            },
            dopamine_gate: LinearConfig::new(1, hidden_dim).init(device),
            action_head: LinearConfig::new(hidden_dim, num_actions).init(device),
        }
    }
    
    /// Select action using dual-pathway mechanism
    /// Input: state [batch, input_dim], reward_signal [batch, 1]
    /// Output: action probabilities [batch, num_actions], go/nogo strengths
    pub fn forward(&self, state: Tensor<B, 2>, reward_signal: Tensor<B, 2>) -> ActionOutput<B> {
        // Direct pathway (Go) - promotes action
        let d1_out = self.direct_pathway.striatum_d1.forward(state.clone()).relu();
        let gpi_inhibit_direct = self.direct_pathway.gpi.forward(d1_out.clone());
        let go_signal = self.direct_pathway.thalamus.forward(-gpi_inhibit_direct);
        
        // Indirect pathway (No-Go) - inhibits action
        let d2_out = self.indirect_pathway.striatum_d2.forward(state.clone()).relu();
        let gpe_out = self.indirect_pathway.gpe.forward(d2_out);
        let stn_out = self.indirect_pathway.stn.forward(-gpe_out).relu();
        let gpi_excite_indirect = self.indirect_pathway.gpi.forward(stn_out);
        let nogo_signal = self.indirect_pathway.thalamus.forward(-gpi_excite_indirect);
        
        // Dopamine modulation (reward prediction)
        let dopamine = self.dopamine_gate.forward(reward_signal).sigmoid();
        
        // Combined signal: Go - NoGo, modulated by dopamine
        let combined = (go_signal.clone() - nogo_signal.clone()) * dopamine;
        
        // Action probabilities
        let action_logits = self.action_head.forward(combined.relu());
        let action_probs = action_logits.softmax_dim(1);
        
        ActionOutput {
            action_probs,
            go_strength: go_signal.mean_dim(1),
            nogo_strength: nogo_signal.mean_dim(1),
        }
    }
}

#[derive(Debug)]
pub struct ActionOutput<B: Backend> {
    pub action_probs: Tensor<B, 2>,
    pub go_strength: Tensor<B, 1>,
    pub nogo_strength: Tensor<B, 1>,
}

/// Trading actions
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum TradingAction {
    Hold,
    BuySmall,
    BuyMedium,
    BuyLarge,
    SellSmall,
    SellMedium,
    SellLarge,
    ReducePosition,
    ClosePosition,
}
```

#### CNS Metrics (New)

```rust
// Neuromorphic metrics
pub neuro_cortex_confidence: GaugeVec,             // by symbol
pub neuro_hippocampus_pattern_matches: IntCounterVec, // by regime
pub neuro_basal_ganglia_go_strength: Gauge,
pub neuro_basal_ganglia_nogo_strength: Gauge,
pub neuro_basal_ganglia_actions: IntCounterVec,    // by action
pub neuro_amygdala_threat_level: GaugeVec,         // by symbol
pub neuro_amygdala_circuit_breaker_trips: IntCounterVec,
pub neuro_cerebellum_impact_prediction: Gauge,
pub neuro_brain_bus_messages: IntCounterVec,       // by region, direction
```

#### Deliverables

- [ ] All brain regions wired to BrainBus
- [ ] Basal Ganglia action selection tested
- [ ] Amygdala circuit breakers active
- [ ] Cerebellum execution planning
- [ ] Neuromorphic metrics in CNS
- [ ] Integration tests passing

---

### Week 10: Forward Service (Signal Generation)

**Objective**: Implement the complete forward service for real-time signal generation.

#### Tasks

| Task | Description | Crate/Service | Priority |
|------|-------------|---------------|----------|
| 10.1 | Implement market state processor | `services/forward` | P0 |
| 10.2 | Add real-time GAF generation | `services/forward` | P0 |
| 10.3 | Integrate ViViT inference | `services/forward` | P0 |
| 10.4 | Add LTN constraint checking | `services/forward` | P0 |
| 10.5 | Implement signal output format | `services/forward` | P0 |
| 10.6 | Add signal validation | `services/forward` | P1 |
| 10.7 | Performance optimization | `services/forward` | P1 |

#### Forward Service Architecture

```rust
// services/forward/src/lib.rs

use std::sync::Arc;
use tokio::sync::mpsc;
use burn::tensor::backend::Backend;

/// Forward service for real-time signal generation
pub struct ForwardService<B: Backend> {
    config: ForwardConfig,
    state: Arc<JanusState>,
    vision_pipeline: VisionPipeline<B>,
    ltn_engine: LTNEngine<B>,
    fusion: GatedCrossAttention<B>,
    basal_ganglia: BasalGanglia<B>,
    brain_bus: Arc<BrainBus>,
    signal_tx: mpsc::Sender<TradingSignal>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ForwardConfig {
    pub symbols: Vec<String>,
    pub gaf_window_size: usize,
    pub gaf_num_frames: usize,
    pub inference_interval_ms: u64,
    pub min_confidence: f32,
    pub enable_ltn_constraints: bool,
    pub max_batch_size: usize,
}

impl<B: Backend> ForwardService<B> {
    pub async fn new(
        config: ForwardConfig,
        state: Arc<JanusState>,
        device: &B::Device,
    ) -> Result<Self> {
        // Load trained models
        let vision_pipeline = VisionPipeline::load("models/vision", device)?;
        let ltn_engine = LTNEngine::load("models/ltn", device)?;
        let fusion = GatedCrossAttention::load("models/fusion", device)?;
        let basal_ganglia = BasalGanglia::load("models/basal_ganglia", device)?;
        
        let (signal_tx, _) = mpsc::channel(1000);
        
        Ok(Self {
            config,
            state,
            vision_pipeline,
            ltn_engine,
            fusion,
            basal_ganglia,
            brain_bus: Arc::new(BrainBus::new()),
            signal_tx,
        })
    }
    
    /// Main inference loop
    pub async fn run(&self) -> Result<()> {
        let mut market_rx = self.state.signal_bus().subscribe_market_data();
        
        loop {
            tokio::select! {
                Ok(market_data) = market_rx.recv() => {
                    if let Some(signal) = self.process_market_data(&market_data).await? {
                        self.emit_signal(signal).await?;
                    }
                }
                _ = self.state.shutdown_signal() => {
                    tracing::info!("Forward service shutting down");
                    break;
                }
            }
        }
        
        Ok(())
    }
    
    /// Process market data and generate signal
    async fn process_market_data(&self, data: &MarketDataBatch) -> Result<Option<TradingSignal>> {
        let start = std::time::Instant::now();
        
        // Step 1: Build time series window
        let window = self.build_window(data)?;
        
        // Step 2: Generate GAF video
        let gaf_video = self.vision_pipeline.forward_gaf(&window)?;
        
        // Step 3: ViViT feature extraction
        let visual_features = self.vision_pipeline.forward(&gaf_video)?;
        
        // Step 4: LTN constraint evaluation
        let ltn_features = self.ltn_engine.forward(&window)?;
        let constraint_sat = self.ltn_engine.check_constraints(&window)?;
        
        // Step 5: Multimodal fusion
        let fused = self.fusion.forward(visual_features, ltn_features)?;
        
        // Step 6: Action selection via Basal Ganglia
        let reward_pred = self.estimate_reward(&fused)?;
        let action_output = self.basal_ganglia.forward(fused, reward_pred)?;
        
        // Step 7: Apply LTN constraints
        let action = self.apply_constraints(action_output, constraint_sat)?;
        
        // Step 8: Build trading signal
        if action.confidence >= self.config.min_confidence && constraint_sat >= 0.8 {
            let signal = TradingSignal {
                id: Uuid::new_v4(),
                timestamp: Utc::now(),
                symbol: data.symbol.clone(),
                action: action.action,
                confidence: action.confidence,
                size_hint: action.size_hint,
                urgency: action.urgency,
                constraint_satisfaction: constraint_sat,
                metadata: SignalMetadata {
                    visual_confidence: action_output.go_strength.into_scalar(),
                    ltn_satisfaction: constraint_sat,
                    regime: self.detect_regime(&window)?,
                    volatility: self.current_volatility(&data.symbol),
                    processing_time_ms: start.elapsed().as_millis() as u64,
                },
            };
            
            self.record_metrics(&signal);
            return Ok(Some(signal));
        }
        
        Ok(None)
    }
    
    fn record_metrics(&self, signal: &TradingSignal) {
        CNS_METRICS.forward_signals_generated
            .with_label_values(&[&signal.symbol, &format!("{:?}", signal.action)])
            .inc();
        CNS_METRICS.forward_signal_confidence
            .with_label_values(&[&signal.symbol])
            .set(signal.confidence as f64);
        CNS_METRICS.forward_inference_latency_ms
            .observe(signal.metadata.processing_time_ms as f64);
    }
    
    async fn emit_signal(&self, signal: TradingSignal) -> Result<()> {
        // Publish to signal bus
        self.state.signal_bus().publish(Signal::Trading(signal.clone())).await?;
        
        // Record to experience buffer for backward service
        self.state.experience_buffer().push(signal.clone()).await?;
        
        Ok(())
    }
}
```

#### Trading Signal Output Format

```rust
// lib/janus-core/src/signal.rs

/// Trading signal output
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TradingSignal {
    /// Unique signal ID
    pub id: Uuid,
    /// Signal generation timestamp
    pub timestamp: DateTime<Utc>,
    /// Trading symbol
    pub symbol: String,
    /// Recommended action
    pub action: SignalAction,
    /// Confidence score [0, 1]
    pub confidence: f32,
    /// Suggested position size (percentage of portfolio)
    pub size_hint: f32,
    /// Urgency level
    pub urgency: Urgency,
    /// LTN constraint satisfaction score
    pub constraint_satisfaction: f32,
    /// Additional metadata
    pub metadata: SignalMetadata,
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq)]
pub enum SignalAction {
    /// No action recommended
    Hold,
    /// Open/increase long position
    Buy { strength: f32 },
    /// Open/increase short position
    Sell { strength: f32 },
    /// Reduce current position
    ReducePosition { target_pct: f32 },
    /// Close all positions
    CloseAll,
    /// Hedge current exposure
    Hedge { ratio: f32 },
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
pub enum Urgency {
    /// Can wait for better entry
    Low,
    /// Execute within reasonable time
    Normal,
    /// Execute soon
    High,
    /// Execute immediately
    Critical,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SignalMetadata {
    pub visual_confidence: f32,
    pub ltn_satisfaction: f32,
    pub regime: MarketRegime,
    pub volatility: f32,
    pub processing_time_ms: u64,
    pub model_version: String,
}
```

#### CNS Metrics (New)

```rust
// Forward service metrics
pub forward_signals_generated: IntCounterVec,      // by symbol, action
pub forward_signal_confidence: GaugeVec,           // by symbol
pub forward_constraint_satisfaction: GaugeVec,     // by symbol
pub forward_inference_latency_ms: Histogram,
pub forward_gaf_generation_ms: Histogram,
pub forward_vivit_inference_ms: Histogram,
pub forward_ltn_evaluation_ms: Histogram,
pub forward_fusion_ms: Histogram,
pub forward_batch_size: Histogram,
pub forward_active_symbols: IntGauge,
```

#### Deliverables

- [ ] Complete forward service implementation
- [ ] Real-time GAF generation
- [ ] ViViT inference < 10ms p99
- [ ] LTN constraint checking
- [ ] Signal output to execution service
- [ ] Forward metrics in CNS
- [ ] Performance benchmarks

---

### Week 11: Backward Service & CNS Expansion

**Objective**: Complete the backward service for memory consolidation and expand CNS with comprehensive metrics.

#### Tasks

| Task | Description | Crate/Service | Priority |
|------|-------------|---------------|----------|
| 11.1 | Implement nightly consolidation job | `services/backward` | P0 |
| 11.2 | Add model retraining pipeline | `services/backward` | P0 |
| 11.3 | Implement UMAP visualization | `services/backward` | P2 |
| 11.4 | Expand CNS with all new metrics | `crates/cns` | P0 |
| 11.5 | Create Grafana dashboards | `config/grafana` | P0 |
| 11.6 | Add alerting rules | `config/prometheus` | P1 |
| 11.7 | Implement log aggregation | `crates/cns` | P2 |

#### Backward Service

```rust
// services/backward/src/lib.rs

use apalis::prelude::*;
use tokio_cron_scheduler::{Job, JobScheduler};

/// Backward service for offline processing
pub struct BackwardService<B: Backend> {
    config: BackwardConfig,
    state: Arc<JanusState>,
    replay_buffer: PrioritizedReplayBuffer<B>,
    consolidator: SchemaConsolidator<B>,
    trainer: BurnTrainingLoop<B>,
    scheduler: JobScheduler,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BackwardConfig {
    pub consolidation_cron: String,  // e.g., "0 0 4 * * *" (4 AM daily)
    pub retraining_cron: String,     // e.g., "0 0 2 * * 0" (2 AM Sunday)
    pub min_experiences_for_training: usize,
    pub batch_size: usize,
    pub num_epochs: usize,
}

impl<B: Backend> BackwardService<B> {
    pub async fn new(
        config: BackwardConfig,
        state: Arc<JanusState>,
        device: &B::Device,
    ) -> Result<Self> {
        let replay_buffer = PrioritizedReplayBuffer::new(100_000, 0.6, 0.4);
        let consolidator = SchemaConsolidator::new(
            &state.config().qdrant_url,
            "market_schemas",
            256,
        ).await?;
        let trainer = BurnTrainingLoop::new(TrainingConfig::default());
        let scheduler = JobScheduler::new().await?;
        
        Ok(Self {
            config,
            state,
            replay_buffer,
            consolidator,
            trainer,
            scheduler,
        })
    }
    
    /// Start the backward service
    pub async fn run(&self) -> Result<()> {
        // Schedule consolidation job
        let consolidation_job = Job::new_async(
            &self.config.consolidation_cron,
            |_, _| Box::pin(async move {
                self.run_consolidation().await
            }),
        )?;
        self.scheduler.add(consolidation_job).await?;
        
        // Schedule retraining job
        let retraining_job = Job::new_async(
            &self.config.retraining_cron,
            |_, _| Box::pin(async move {
                self.run_retraining().await
            }),
        )?;
        self.scheduler.add(retraining_job).await?;
        
        // Start scheduler
        self.scheduler.start().await?;
        
        // Listen for new experiences
        let mut exp_rx = self.state.signal_bus().subscribe_experiences();
        
        loop {
            tokio::select! {
                Ok(experience) = exp_rx.recv() => {
                    self.replay_buffer.push(experience, 1.0);
                }
                _ = self.state.shutdown_signal() => {
                    tracing::info!("Backward service shutting down");
                    break;
                }
            }
        }
        
        Ok(())
    }
    
    /// Nightly consolidation: experiences → schemas
    async fn run_consolidation(&self) -> Result<()> {
        tracing::info!("Starting nightly consolidation");
        let start = std::time::Instant::now();
        
        // Get all experiences from buffer
        let experiences = self.replay_buffer.get_all();
        
        if experiences.len() < 100 {
            tracing::warn!("Insufficient experiences for consolidation");
            return Ok(());
        }
        
        // Consolidate into schemas
        let schemas = self.consolidator.consolidate(&experiences).await?;
        
        // Record metrics
        CNS_METRICS.backward_consolidations.inc();
        CNS_METRICS.backward_schemas_created.add(schemas.len() as u64);
        CNS_METRICS.backward_consolidation_latency_ms.observe(start.elapsed().as_millis() as f64);
        
        tracing::info!("Consolidation complete: {} schemas created", schemas.len());
        Ok(())
    }
    
    /// Weekly retraining
    async fn run_retraining(&self) -> Result<()> {
        tracing::info!("Starting model retraining");
        let start = std::time::Instant::now();
        
        if self.replay_buffer.len() < self.config.min_experiences_for_training {
            tracing::warn!("Insufficient experiences for retraining");
            return Ok(());
        }
        
        // Sample training data
        let train_data = self.prepare_training_data().await?;
        
        // Run training
        let result = self.trainer.fit(train_data).await?;
        
        // Save new model version
        let version = self.save_model(&result.final_model).await?;
        
        // Record metrics
        CNS_METRICS.backward_training_runs.inc();
        CNS_METRICS.backward_training_loss.set(result.final_loss as f64);
        CNS_METRICS.backward_training_latency_ms.observe(start.elapsed().as_millis() as f64);
        
        tracing::info!("Retraining complete: version {}, loss {:.4}", version, result.final_loss);
        Ok(())
    }
}
```

#### Expanded CNS Metrics Registry

```rust
// crates/cns/src/metrics.rs - Complete metrics registry

/// All JANUS CNS metrics organized by subsystem
pub struct MetricsRegistry {
    pub registry: Registry,
    
    // ===== SYSTEM METRICS =====
    pub system_health_score: Gauge,
    pub system_status: IntGauge,
    pub system_uptime_seconds: IntGauge,
    pub system_version: IntGaugeVec,
    
    // ===== DATA INGESTION =====
    pub data_websocket_connections: IntGaugeVec,
    pub data_websocket_reconnects: IntCounterVec,
    pub data_websocket_latency_ms: HistogramVec,
    pub data_messages_received: IntCounterVec,
    pub data_messages_parsed_errors: IntCounterVec,
    pub data_sequence_gaps: IntCounterVec,
    pub data_stale_data_alerts: IntCounterVec,
    pub data_duplicate_events: IntCounterVec,
    pub data_bytes_received: IntCounterVec,
    
    // ===== NEWS & SENTIMENT =====
    pub news_articles_ingested: IntCounterVec,
    pub news_articles_deduplicated: IntCounter,
    pub news_sentiment_scores: HistogramVec,
    pub news_processing_latency_ms: HistogramVec,
    pub news_source_health: GaugeVec,
    pub news_api_rate_limit_remaining: IntGaugeVec,
    
    // ===== STORAGE =====
    pub storage_records_written: IntCounterVec,
    pub storage_write_latency_ms: HistogramVec,
    pub storage_query_latency_ms: HistogramVec,
    pub storage_disk_usage_bytes: IntGaugeVec,
    pub storage_retention_deletes: IntCounterVec,
    
    // ===== DATA QUALITY =====
    pub quality_records_validated: IntCounterVec,
    pub quality_records_invalid: IntCounterVec,
    pub quality_anomalies_detected: IntCounterVec,
    pub quality_records_cleaned: IntCounterVec,
    pub quality_score: GaugeVec,
    pub quality_pipeline_latency_ms: HistogramVec,
    pub quality_gap_sequences_detected: IntCounterVec,
    pub quality_backfill_requests: IntCounterVec,
    
    // ===== ML TRAINING =====
    pub ml_training_epoch: IntGaugeVec,
    pub ml_training_step: IntGaugeVec,
    pub ml_training_loss: GaugeVec,
    pub ml_validation_loss: GaugeVec,
    pub ml_learning_rate: GaugeVec,
    pub ml_gradient_norm: GaugeVec,
    pub ml_batch_latency_ms: HistogramVec,
    pub ml_gpu_memory_bytes: IntGaugeVec,
    pub ml_gpu_utilization: GaugeVec,
    pub ml_checkpoint_saved: IntCounterVec,
    
    // ===== VISION PIPELINE =====
    pub vision_gaf_generations: IntCounterVec,
    pub vision_gaf_latency_ms: Histogram,
    pub vision_vivit_inferences: IntCounterVec,
    pub vision_vivit_latency_ms: Histogram,
    pub vision_pipeline_errors: IntCounterVec,
    
    // ===== LTN & SYMBOLIC =====
    pub ltn_axiom_satisfaction: GaugeVec,
    pub ltn_predicate_confidence: GaugeVec,
    pub ltn_logic_loss: Gauge,
    pub ltn_constraint_violations: IntCounterVec,
    pub fusion_gate_values: HistogramVec,
    
    // ===== MEMORY & REPLAY =====
    pub memory_replay_buffer_size: IntGauge,
    pub memory_replay_samples_total: IntCounter,
    pub memory_replay_priority_mean: Gauge,
    pub memory_schemas_total: IntGauge,
    pub memory_schema_consolidations: IntCounter,
    pub memory_qdrant_upserts: IntCounterVec,
    pub memory_qdrant_searches: IntCounterVec,
    pub memory_qdrant_latency_ms: HistogramVec,
    
    // ===== NEUROMORPHIC =====
    pub neuro_cortex_confidence: GaugeVec,
    pub neuro_hippocampus_pattern_matches: IntCounterVec,
    pub neuro_basal_ganglia_go_strength: Gauge,
    pub neuro_basal_ganglia_nogo_strength: Gauge,
    pub neuro_basal_ganglia_actions: IntCounterVec,
    pub neuro_amygdala_threat_level: GaugeVec,
    pub neuro_amygdala_circuit_breaker_trips: IntCounterVec,
    pub neuro_cerebellum_impact_prediction: Gauge,
    
    // ===== FORWARD SERVICE =====
    pub forward_signals_generated: IntCounterVec,
    pub forward_signal_confidence: GaugeVec,
    pub forward_constraint_satisfaction: GaugeVec,
    pub forward_inference_latency_ms: Histogram,
    pub forward_batch_size: Histogram,
    pub forward_active_symbols: IntGauge,
    pub forward_model_version: IntGaugeVec,
    
    // ===== BACKWARD SERVICE =====
    pub backward_consolidations: IntCounter,
    pub backward_schemas_created: IntCounter,
    pub backward_training_runs: IntCounter,
    pub backward_training_loss: Gauge,
    pub backward_consolidation_latency_ms: Histogram,
    pub backward_training_latency_ms: Histogram,
    pub backward_experience_buffer_size: IntGauge,
    
    // ===== DEPENDENCIES =====
    pub redis_connections_active: IntGauge,
    pub redis_commands_total: IntCounterVec,
    pub redis_command_duration: HistogramVec,
    pub qdrant_vectors_stored: IntGauge,
    pub qdrant_search_requests: IntCounter,
    pub qdrant_search_duration: Histogram,
    pub questdb_writes_total: IntCounterVec,
    pub questdb_write_duration: HistogramVec,
    
    // ===== CIRCUIT BREAKERS =====
    pub circuit_breaker_state: IntGaugeVec,
    pub circuit_breaker_trips: IntCounterVec,
    pub circuit_breaker_recovery_time_ms: HistogramVec,
    
    // ===== RESOURCES =====
    pub memory_usage_bytes: IntGauge,
    pub cpu_usage_percent: Gauge,
    pub active_tasks: IntGauge,
    pub thread_pool_active: IntGauge,
    pub thread_pool_queued: IntGauge,
}
```

#### Prometheus Alerting Rules

```yaml
# config/prometheus/alerts.yml

groups:
  - name: janus_critical
    rules:
      - alert: SystemHealthCritical
        expr: janus_cns_system_health_score < 0.5
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "JANUS system health critical"
          description: "System health score is {{ $value }}"
          
      - alert: CircuitBreakerTripped
        expr: increase(janus_cns_circuit_breaker_trips[5m]) > 0
        labels:
          severity: warning
        annotations:
          summary: "Circuit breaker tripped"
          description: "Circuit breaker {{ $labels.component }} tripped"
          
      - alert: DataIngestionDown
        expr: janus_data_websocket_connections == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "No data connections"
          description: "All WebSocket connections are down"
          
      - alert: HighInferenceLatency
        expr: histogram_quantile(0.99, janus_forward_inference_latency_ms_bucket) > 50
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High inference latency"
          description: "p99 inference latency is {{ $value }}ms"
          
      - alert: LowConstraintSatisfaction
        expr: janus_forward_constraint_satisfaction < 0.7
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Low LTN constraint satisfaction"
          description: "Constraint satisfaction for {{ $labels.symbol }} is {{ $value }}"
          
      - alert: DataQualityDegraded
        expr: janus_quality_score < 0.8
        for: 15m
        labels:
          severity: warning
        annotations:
          summary: "Data quality degraded"
          description: "Quality score for {{ $labels.symbol }} is {{ $value }}"

  - name: janus_performance
    rules:
      - alert: HighMemoryUsage
        expr: janus_cns_memory_usage_bytes / 1e9 > 4
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "High memory usage"
          description: "Memory usage is {{ $value | humanize1024 }}B"
          
      - alert: GPUMemoryExhaustion
        expr: janus_ml_gpu_memory_bytes / janus_ml_gpu_memory_total_bytes > 0.95
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "GPU memory nearly exhausted"
          description: "GPU memory usage at {{ $value | humanizePercentage }}"
```

#### Deliverables

- [ ] Backward service with scheduled jobs
- [ ] Nightly consolidation working
- [ ] Weekly retraining pipeline
- [ ] All CNS metrics implemented
- [ ] Grafana dashboards (5+ dashboards)
- [ ] Alerting rules configured
- [ ] Log aggregation setup

---

### Week 12: Integration Testing & Documentation

**Objective**: Complete integration testing, performance validation, and documentation.

#### Tasks

| Task | Description | Priority |
|------|-------------|----------|
| 12.1 | End-to-end integration tests | P0 |
| 12.2 | Performance benchmarking | P0 |
| 12.3 | Load testing | P1 |
| 12.4 | Security audit | P1 |
| 12.5 | API documentation | P0 |
| 12.6 | Operator runbook | P1 |
| 12.7 | Deployment guide | P0 |

#### Integration Test Suite

```rust
// tests/integration/mod.rs

mod data_pipeline;
mod ml_pipeline;
mod signal_generation;
mod e2e;

/// Full end-to-end test
#[tokio::test]
async fn test_full_pipeline() {
    // Setup
    let test_env = TestEnvironment::new().await;
    
    // 1. Start data ingestion with mock exchange
    test_env.start_mock_exchange("BTCUSD").await;
    test_env.wait_for_data(100).await;
    
    // 2. Verify data quality
    let quality = test_env.get_quality_score("BTCUSD").await;
    assert!(quality > 0.9, "Data quality too low: {}", quality);
    
    // 3. Run forward inference
    let signals = test_env.generate_signals(10).await;
    assert!(!signals.is_empty(), "No signals generated");
    
    // 4. Verify signal format
    for signal in &signals {
        assert!(signal.confidence >= 0.0 && signal.confidence <= 1.0);
        assert!(signal.constraint_satisfaction >= 0.0);
        assert!(!signal.symbol.is_empty());
    }
    
    // 5. Check CNS metrics
    let health = test_env.get_system_health().await;
    assert!(health.score > 0.8, "System health too low: {}", health.score);
    
    // Cleanup
    test_env.shutdown().await;
}

/// Test data pipeline
#[tokio::test]
async fn test_data_pipeline() {
    let env = TestEnvironment::new().await;
    
    // Ingest mock data
    env.ingest_mock_data(1000).await;
    
    // Verify storage
    let count = env.query_storage_count("trades").await;
    assert_eq!(count, 1000);
    
    // Verify quality pipeline
    let report = env.run_quality_pipeline().await;
    assert!(report.quality_score > 0.95);
    
    env.shutdown().await;
}

/// Test ML pipeline
#[tokio::test]
async fn test_ml_pipeline() {
    let env = TestEnvironment::new().await;
    
    // Load test data
    let data = env.load_test_dataset("btc_2024").await;
    
    // Run vision pipeline
    let features = env.run_vision_pipeline(&data).await;
    assert_eq!(features.dims()[0], data.len());
    
    // Run LTN evaluation
    let satisfaction = env.run_ltn_evaluation(&features).await;
    assert!(satisfaction > 0.0);
    
    env.shutdown().await;
}
```

#### Performance Benchmarks

```rust
// benches/inference.rs

use criterion::{black_box, criterion_group, criterion_main, Criterion, BenchmarkId};

fn benchmark_gaf_generation(c: &mut Criterion) {
    let pipeline = setup_vision_pipeline();
    let data = generate_test_data(1000);
    
    let mut group = c.benchmark_group("GAF Generation");
    
    for window_size in [32, 64, 128] {
        group.bench_with_input(
            BenchmarkId::from_parameter(window_size),
            &window_size,
            |b, &size| {
                b.iter(|| {
                    pipeline.generate_gaf(black_box(&data[..size]))
                });
            },
        );
    }
    
    group.finish();
}

fn benchmark_vivit_inference(c: &mut Criterion) {
    let model = load_vivit_model();
    let gaf_video = generate_test_gaf_video(8, 32, 32);
    
    c.bench_function("ViViT Inference", |b| {
        b.iter(|| {
            model.forward(black_box(&gaf_video))
        });
    });
}

fn benchmark_full_inference(c: &mut Criterion) {
    let forward_service = setup_forward_service();
    let market_data = generate_market_data_batch(100);
    
    c.bench_function("Full Inference Pipeline", |b| {
        b.iter(|| {
            forward_service.process_batch(black_box(&market_data))
        });
    });
}

criterion_group!(
    benches,
    benchmark_gaf_generation,
    benchmark_vivit_inference,
    benchmark_full_inference
);
criterion_main!(benches);
```

#### Performance Targets

| Metric | Target | Acceptable |
|--------|--------|------------|
| GAF Generation (32x32) | < 1ms | < 5ms |
| ViViT Inference | < 5ms | < 10ms |
| Full Pipeline p50 | < 8ms | < 15ms |
| Full Pipeline p99 | < 15ms | < 30ms |
| Throughput | > 1000 signals/sec | > 500 signals/sec |
| Memory (idle) | < 500MB | < 1GB |
| Memory (active) | < 2GB | < 4GB |

#### Documentation Structure

```
docs/
├── architecture/
│   ├── SYSTEM_OVERVIEW.md
│   ├── DATA_FLOW.md
│   ├── ML_PIPELINE.md
│   ├── NEUROMORPHIC.md
│   └── CNS_MONITORING.md
├── api/
│   ├── REST_API.md
│   ├── GRPC_API.md
│   ├── SIGNAL_FORMAT.md
│   └── METRICS_REFERENCE.md
├── operations/
│   ├── DEPLOYMENT_GUIDE.md
│   ├── RUNBOOK.md
│   ├── TROUBLESHOOTING.md
│   └── DISASTER_RECOVERY.md
├── development/
│   ├── CONTRIBUTING.md
│   ├── CODE_STYLE.md
│   ├── TESTING_GUIDE.md
│   └── BURN_MIGRATION.md
└── whitepaper/
    └── janus.tex (existing)
```

#### Deliverables

- [ ] Integration test suite (>80% coverage)
- [ ] Performance benchmarks passing targets
- [ ] Load test with 10x expected traffic
- [ ] Security audit complete
- [ ] API documentation (OpenAPI spec)
- [ ] Operator runbook
- [ ] Deployment guide
- [ ] All tests passing in CI

---

## Summary

### Deliverable Timeline

| Week | Phase | Key Deliverables |
|------|-------|------------------|
| 1 | Data Foundation | 6 exchanges connected, unified events, health probes |
| 2 | Data Foundation | News service, sentiment scoring, deduplication |
| 3 | Data Foundation | Asset registry, storage layer, Parquet export |
| 4 | Data Foundation | Quality pipeline, anomaly detection, gap filling |
| 5 | ML Pipeline | Burn migration, training loop, checkpointing |
| 6 | ML Pipeline | DiffGAF in Burn, ViViT implementation |
| 7 | ML Pipeline | LTN with Burn, trading axioms, Gated Cross-Attention |
| 8 | ML Pipeline | PER with SWR, schema consolidation, Qdrant |
| 9 | Signal Generation | Brain integration bus, Basal Ganglia, Amygdala |
| 10 | Signal Generation | Forward service, signal output, real-time inference |
| 11 | Signal Generation | Backward service, CNS expansion, Grafana dashboards |
| 12 | Finalization | Integration tests, benchmarks, documentation |

### New Crates Created

1. `janus-exchanges` - Unified exchange adapters
2. `janus-sentiment` - News and sentiment analysis
3. `janus-storage` - Storage abstraction layer
4. `janus-data-quality` - Data validation and cleaning
5. `janus-burn-core` - Burn ML framework foundation
6. `janus-fusion` - Multimodal fusion (Gated Cross-Attention)

### New Services Created

1. `services/news` - News aggregation and processing
2. `services/registry` - Asset configuration registry

### CNS Metrics Summary

| Category | Metrics Count |
|----------|---------------|
| System | 4 |
| Data Ingestion | 9 |
| News & Sentiment | 6 |
| Storage | 5 |
| Data Quality | 8 |
| ML Training | 10 |
| Vision Pipeline | 5 |
| LTN & Symbolic | 5 |
| Memory & Replay | 9 |
| Neuromorphic | 9 |
| Forward Service | 7 |
| Backward Service | 7 |
| Dependencies | 9 |
| Circuit Breakers | 3 |
| Resources | 5 |
| **Total** | **101** |

### Architecture Principles

1. **Signal Generation Only**: JANUS generates signals; execution is external
2. **Rust-Only**: All components in Rust with Burn for ML
3. **Neuromorphic Design**: Brain-inspired modular architecture
4. **Neuro-Symbolic**: Neural + LTN constraint satisfaction
5. **Observable**: Comprehensive CNS metrics and alerting
6. **Modular**: Each component independently deployable

### Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Burn framework immaturity | Fallback to ONNX Runtime for inference |
| Data quality issues | Multi-layer validation, anomaly detection |
| Inference latency | Batch processing, model optimization |
| Memory pressure | Tiered storage, buffer limits |
| Exchange API changes | Adapter pattern, quick hotfix capability |

### Success Criteria

- [ ] All 6 exchanges streaming data reliably
- [ ] Data quality score > 95% across all assets
- [ ] Inference latency p99 < 30ms
- [ ] Signal confidence correlation with returns > 0.3
- [ ] LTN constraint satisfaction > 90%
- [ ] System health score > 0.9 during market hours
- [ ] Zero critical alerts during normal operation
- [ ] Documentation coverage > 90%

---

## Appendix A: Dependency Versions

```toml
# Workspace Cargo.toml additions

[workspace.dependencies]
# Burn ML Framework
burn = { version = "0.14", features = ["train", "autodiff", "metrics", "tui"] }
burn-core = "0.14"
burn-tensor = "0.14"
burn-autodiff = "0.14"
burn-train = "0.14"
burn-ndarray = "0.14"
burn-wgpu = { version = "0.14", optional = true }

# Data Quality
approx = "0.5"
statrs = "0.17"

# News & Sentiment
feed-rs = "2.0"
ego-tree = "0.6"

# Additional utilities
dashmap = "6.0"
moka = { version = "0.12", features = ["future"] }
```

---

## Appendix B: Grafana Dashboard JSON

See `config/grafana/dashboards/` for pre-built dashboards:

1. `janus-overview.json` - System health overview
2. `janus-data.json` - Data ingestion metrics
3. `janus-ml.json` - ML training and inference
4. `janus-signals.json` - Signal generation metrics
5. `janus-neuromorphic.json` - Brain region activity

---

## Appendix C: Environment Variables

```bash
# Core
JANUS_ENVIRONMENT=production
JANUS_HTTP_PORT=8080
JANUS_GRPC_PORT=50051
JANUS_METRICS_PORT=9090

# Modules
JANUS_ENABLE_FORWARD=true
JANUS_ENABLE_BACKWARD=true
JANUS_ENABLE_CNS=true
JANUS_ENABLE_DATA=true
JANUS_ENABLE_NEWS=true

# Storage
REDIS_URL=redis://localhost:6379/0
QUESTDB_HOST=localhost:9009
QDRANT_URL=http://localhost:6333

# ML
JANUS_MODEL_PATH=/models
JANUS_BURN_BACKEND=wgpu
JANUS_DEVICE=gpu:0

# Data
JANUS_EXCHANGES=binance,bybit,coinbase,kraken,okx,kucoin
JANUS_SYMBOLS=BTCUSD,ETHUSDT,SOLUSDT

# Logging
RUST_LOG=info,janus=debug
```

---

**Document Version**: 1.0.0  
**Last Updated**: 2025  
**Status**: Draft - Ready for Review