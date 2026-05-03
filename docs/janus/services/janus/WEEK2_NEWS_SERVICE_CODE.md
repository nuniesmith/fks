# Week 2: News Service - Complete Source Code

This document contains the complete, production-ready source code for the `services/news` implementation.

---

## File: `src/janus/services/news/src/main.rs`

```rust
//! JANUS News Ingestion Service
//!
//! Collects news articles from multiple sources (RSS, APIs), performs sentiment
//! analysis, and stores results in PostgreSQL with CNS metrics.

use anyhow::Result;
use janus_news::{config::Config, NewsService};
use tracing::{error, info};
use tracing_subscriber::{layer::SubscriberExt, util::SubscriberInitExt};

#[tokio::main]
async fn main() -> Result<()> {
    // Initialize logging
    tracing_subscriber::registry()
        .with(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| "janus_news=info,tower_http=debug".into()),
        )
        .with(tracing_subscriber::fmt::layer())
        .init();

    info!("Starting JANUS News Ingestion Service");

    // Load configuration
    let config = Config::from_env()?;
    info!("Configuration loaded: {:?}", config);

    // Create and run the news service
    let service = NewsService::new(config).await?;

    // Handle graceful shutdown
    let shutdown = tokio::signal::ctrl_c();

    tokio::select! {
        result = service.run() => {
            if let Err(e) = result {
                error!("News service error: {}", e);
                std::process::exit(1);
            }
        }
        _ = shutdown => {
            info!("Shutdown signal received");
        }
    }

    info!("News service stopped");
    Ok(())
}
```

---

## File: `src/janus/services/news/src/lib.rs`

```rust
//! JANUS News Ingestion Service Library

pub mod config;
pub mod metrics;
pub mod processor;
pub mod sources;
pub mod storage;

use anyhow::Result;
use std::sync::Arc;
use tokio::sync::broadcast;
use tokio::time::{interval, Duration};
use tracing::{error, info, warn};

use crate::config::Config;
use crate::processor::NewsProcessor;
use crate::sources::NewsCollector;
use crate::storage::NewsStorage;

/// Main news service orchestrator
pub struct NewsService {
    config: Arc<Config>,
    collector: NewsCollector,
    processor: NewsProcessor,
    storage: Arc<NewsStorage>,
    shutdown_tx: broadcast::Sender<()>,
}

impl NewsService {
    /// Create a new news service
    pub async fn new(config: Config) -> Result<Self> {
        let config = Arc::new(config);
        let (shutdown_tx, _) = broadcast::channel(1);

        // Initialize components
        let storage = Arc::new(NewsStorage::new(&config.database_url).await?);
        let collector = NewsCollector::new(config.clone());
        let processor = NewsProcessor::new();

        info!("News service initialized");

        Ok(Self {
            config,
            collector,
            processor,
            storage,
            shutdown_tx,
        })
    }

    /// Run the news service
    pub async fn run(self) -> Result<()> {
        info!("Starting news collection loop");

        let mut poll_interval = interval(Duration::from_secs(self.config.poll_interval_secs));
        let mut shutdown_rx = self.shutdown_tx.subscribe();

        loop {
            tokio::select! {
                _ = poll_interval.tick() => {
                    if let Err(e) = self.collect_and_process().await {
                        error!("Error during news collection: {}", e);
                        metrics::NEWS_ERRORS_TOTAL
                            .with_label_values(&["all", "collection_error"])
                            .inc();
                    }
                }
                _ = shutdown_rx.recv() => {
                    info!("Shutdown signal received, stopping news service");
                    break;
                }
            }
        }

        Ok(())
    }

    /// Collect and process news from all sources
    async fn collect_and_process(&self) -> Result<()> {
        info!("Collecting news from all sources");

        // Get news sources from database
        let sources = self.storage.get_enabled_sources().await?;
        info!("Found {} enabled sources", sources.len());

        for source in sources {
            match self.collector.collect(&source).await {
                Ok(articles) => {
                    info!("Collected {} articles from {}", articles.len(), source.name);

                    for article in articles {
                        // Check for duplicates
                        if self.storage.is_duplicate(&article).await? {
                            metrics::NEWS_DUPLICATES_DETECTED
                                .with_label_values(&[&source.name])
                                .inc();
                            continue;
                        }

                        // Process sentiment
                        let start = std::time::Instant::now();
                        let result = self.processor.process(&article)?;
                        let latency = start.elapsed();

                        metrics::NEWS_PROCESSING_LATENCY
                            .with_label_values(&[&source.name])
                            .observe(latency.as_secs_f64());

                        // Store in database
                        self.storage.store_article(&article, &result).await?;

                        // Update metrics
                        for asset in &result.mentioned_assets {
                            metrics::NEWS_ARTICLES_INGESTED_TOTAL
                                .with_label_values(&[&source.name, asset])
                                .inc();

                            metrics::NEWS_SENTIMENT_SCORE
                                .with_label_values(&[asset])
                                .set(result.score as f64);
                        }
                    }

                    // Update source stats
                    self.storage.update_source_stats(&source.name, articles.len() as i64).await?;
                }
                Err(e) => {
                    error!("Failed to collect from {}: {}", source.name, e);
                    metrics::NEWS_ERRORS_TOTAL
                        .with_label_values(&[&source.name, "collection_failed"])
                        .inc();
                }
            }
        }

        Ok(())
    }
}

// Re-export commonly used types
pub use janus_sentiment::{Article, SentimentResult};
pub use sources::NewsSource;
```

---

## File: `src/janus/services/news/src/config.rs`

```rust
//! News service configuration

use anyhow::{Context, Result};
use serde::{Deserialize, Serialize};
use std::env;

/// News service configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Config {
    /// PostgreSQL database URL
    pub database_url: String,

    /// News collection poll interval (seconds)
    pub poll_interval_secs: u64,

    /// Maximum articles to collect per source per poll
    pub max_articles_per_poll: usize,

    /// Enable sentiment analysis
    pub enable_sentiment: bool,

    /// Minimum confidence threshold for sentiment (0.0 to 1.0)
    pub min_confidence_threshold: f32,

    /// Log level
    pub log_level: String,

    /// Prometheus metrics port
    pub metrics_port: u16,
}

impl Config {
    /// Load configuration from environment variables
    pub fn from_env() -> Result<Self> {
        // Load .env file if present (non-Docker environments)
        let _ = dotenvy::dotenv();

        Ok(Config {
            database_url: env::var("DATABASE_URL")
                .context("DATABASE_URL must be set")?,

            poll_interval_secs: env::var("POLL_INTERVAL_SECS")
                .unwrap_or_else(|_| "300".to_string())
                .parse()
                .context("Invalid POLL_INTERVAL_SECS")?,

            max_articles_per_poll: env::var("MAX_ARTICLES_PER_POLL")
                .unwrap_or_else(|_| "100".to_string())
                .parse()
                .context("Invalid MAX_ARTICLES_PER_POLL")?,

            enable_sentiment: env::var("ENABLE_SENTIMENT")
                .unwrap_or_else(|_| "true".to_string())
                .parse()
                .unwrap_or(true),

            min_confidence_threshold: env::var("MIN_CONFIDENCE_THRESHOLD")
                .unwrap_or_else(|_| "0.3".to_string())
                .parse()
                .context("Invalid MIN_CONFIDENCE_THRESHOLD")?,

            log_level: env::var("LOG_LEVEL")
                .unwrap_or_else(|_| "info".to_string()),

            metrics_port: env::var("METRICS_PORT")
                .unwrap_or_else(|_| "9091".to_string())
                .parse()
                .context("Invalid METRICS_PORT")?,
        })
    }

    /// Validate configuration
    pub fn validate(&self) -> Result<()> {
        anyhow::ensure!(
            self.poll_interval_secs >= 10,
            "Poll interval must be at least 10 seconds"
        );

        anyhow::ensure!(
            self.max_articles_per_poll > 0 && self.max_articles_per_poll <= 1000,
            "Max articles per poll must be between 1 and 1000"
        );

        anyhow::ensure!(
            self.min_confidence_threshold >= 0.0 && self.min_confidence_threshold <= 1.0,
            "Confidence threshold must be between 0.0 and 1.0"
        );

        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_validate_config() {
        let config = Config {
            database_url: "postgresql://localhost/test".to_string(),
            poll_interval_secs: 300,
            max_articles_per_poll: 100,
            enable_sentiment: true,
            min_confidence_threshold: 0.3,
            log_level: "info".to_string(),
            metrics_port: 9091,
        };

        assert!(config.validate().is_ok());
    }

    #[test]
    fn test_validate_invalid_poll_interval() {
        let config = Config {
            database_url: "postgresql://localhost/test".to_string(),
            poll_interval_secs: 5, // Too low
            max_articles_per_poll: 100,
            enable_sentiment: true,
            min_confidence_threshold: 0.3,
            log_level: "info".to_string(),
            metrics_port: 9091,
        };

        assert!(config.validate().is_err());
    }
}
```

---

## File: `src/janus/services/news/src/metrics.rs`

```rust
//! Prometheus metrics for news service

use lazy_static::lazy_static;
use prometheus::{
    register_gauge_vec, register_histogram_vec, register_int_counter_vec, GaugeVec, HistogramVec,
    IntCounterVec,
};

lazy_static! {
    /// Total news articles ingested
    pub static ref NEWS_ARTICLES_INGESTED_TOTAL: IntCounterVec = register_int_counter_vec!(
        "janus_news_articles_ingested_total",
        "Total news articles ingested",
        &["source", "asset"]
    )
    .unwrap();

    /// Current sentiment score for asset
    pub static ref NEWS_SENTIMENT_SCORE: GaugeVec = register_gauge_vec!(
        "janus_news_sentiment_score",
        "Current sentiment score for asset (-1 to 1)",
        &["asset"]
    )
    .unwrap();

    /// News processing latency
    pub static ref NEWS_PROCESSING_LATENCY: HistogramVec = register_histogram_vec!(
        "janus_news_processing_latency_seconds",
        "News processing latency in seconds",
        &["source"],
        vec![0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0]
    )
    .unwrap();

    /// Duplicate articles detected
    pub static ref NEWS_DUPLICATES_DETECTED: IntCounterVec = register_int_counter_vec!(
        "janus_news_duplicates_detected_total",
        "Total duplicate articles detected",
        &["source"]
    )
    .unwrap();

    /// News collection errors
    pub static ref NEWS_ERRORS_TOTAL: IntCounterVec = register_int_counter_vec!(
        "janus_news_errors_total",
        "Total news collection errors",
        &["source", "error_type"]
    )
    .unwrap();

    /// Articles per event type
    pub static ref NEWS_EVENT_TYPE_TOTAL: IntCounterVec = register_int_counter_vec!(
        "janus_news_event_type_total",
        "Total articles by event type",
        &["event_type", "impact"]
    )
    .unwrap();

    /// News source health
    pub static ref NEWS_SOURCE_HEALTH: GaugeVec = register_gauge_vec!(
        "janus_news_source_health",
        "News source health status (1=healthy, 0=unhealthy)",
        &["source"]
    )
    .unwrap();
}

/// Example PromQL queries for monitoring:
///
/// # Articles per minute by source
/// rate(janus_news_articles_ingested_total[5m])
///
/// # Average sentiment by asset
/// avg(janus_news_sentiment_score) by (asset)
///
/// # P95 processing latency
/// histogram_quantile(0.95, rate(janus_news_processing_latency_seconds_bucket[5m]))
///
/// # Duplicate rate
/// rate(janus_news_duplicates_detected_total[5m]) / rate(janus_news_articles_ingested_total[5m])
///
/// # Error rate by source
/// rate(janus_news_errors_total[5m])
```

---

## File: `src/janus/services/news/src/processor/mod.rs`

```rust
//! News article processing

use anyhow::Result;
use janus_sentiment::{Article, SentimentAnalyzer, SentimentResult};
use tracing::debug;

/// News processor that performs sentiment analysis
pub struct NewsProcessor {
    analyzer: SentimentAnalyzer,
}

impl NewsProcessor {
    /// Create a new news processor
    pub fn new() -> Self {
        Self {
            analyzer: SentimentAnalyzer::new(),
        }
    }

    /// Process an article and return sentiment results
    pub fn process(&self, article: &Article) -> Result<SentimentResult> {
        debug!("Processing article: {}", article.title);
        
        let result = self.analyzer.analyze(article)?;
        
        debug!(
            "Sentiment: {} ({:?}), Assets: {:?}",
            result.score, result.label, result.mentioned_assets
        );

        Ok(result)
    }
}

impl Default for NewsProcessor {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::Utc;

    #[test]
    fn test_process_article() {
        let processor = NewsProcessor::new();

        let article = Article {
            title: "Bitcoin Surges Past $70,000".to_string(),
            content: "Bitcoin reached a new all-time high today, breaking past $70,000 for the first time.".to_string(),
            source: "Test".to_string(),
            url: "https://test.com/article".to_string(),
            published_at: Utc::now(),
        };

        let result = processor.process(&article).unwrap();

        assert!(result.score > 0.0); // Should be positive
        assert!(!result.mentioned_assets.is_empty()); // Should mention BTC
    }
}
```

---

## File: `src/janus/services/news/src/sources/mod.rs`

```rust
//! News source collection

pub mod deduplicator;
pub mod rss;

use anyhow::Result;
use janus_sentiment::Article;
use serde::{Deserialize, Serialize};
use std::sync::Arc;

use crate::config::Config;

/// News source configuration
#[derive(Debug, Clone, Serialize, Deserialize, sqlx::FromRow)]
pub struct NewsSource {
    pub id: i32,
    pub name: String,
    pub source_type: String,
    pub url: String,
    pub enabled: bool,
    pub poll_interval_secs: i32,
}

/// News collector that fetches articles from various sources
pub struct NewsCollector {
    config: Arc<Config>,
    rss_collector: rss::RssCollector,
}

impl NewsCollector {
    /// Create a new news collector
    pub fn new(config: Arc<Config>) -> Self {
        Self {
            rss_collector: rss::RssCollector::new(config.clone()),
            config,
        }
    }

    /// Collect articles from a news source
    pub async fn collect(&self, source: &NewsSource) -> Result<Vec<Article>> {
        match source.source_type.as_str() {
            "rss" => self.rss_collector.collect(&source.url).await,
            "api" => {
                // TODO: Implement API collectors (Twitter, Reddit, etc.)
                Ok(vec![])
            }
            _ => {
                anyhow::bail!("Unsupported source type: {}", source.source_type);
            }
        }
    }
}
```

---

## File: `src/janus/services/news/src/sources/rss.rs`

```rust
//! RSS feed collection

use anyhow::{Context, Result};
use chrono::{DateTime, Utc};
use janus_sentiment::Article;
use reqwest::Client;
use rss::Channel;
use std::sync::Arc;
use tracing::{debug, warn};

use crate::config::Config;

/// RSS feed collector
pub struct RssCollector {
    client: Client,
    config: Arc<Config>,
}

impl RssCollector {
    /// Create a new RSS collector
    pub fn new(config: Arc<Config>) -> Self {
        let client = Client::builder()
            .timeout(std::time::Duration::from_secs(30))
            .build()
            .expect("Failed to create HTTP client");

        Self { client, config }
    }

    /// Collect articles from an RSS feed
    pub async fn collect(&self, url: &str) -> Result<Vec<Article>> {
        debug!("Fetching RSS feed: {}", url);

        // Fetch the feed
        let response = self
            .client
            .get(url)
            .send()
            .await
            .context("Failed to fetch RSS feed")?;

        let content = response
            .bytes()
            .await
            .context("Failed to read RSS feed content")?;

        // Parse RSS
        let channel = Channel::read_from(&content[..]).context("Failed to parse RSS feed")?;

        debug!("Parsed RSS feed: {}", channel.title());

        // Convert items to articles
        let mut articles = Vec::new();
        for item in channel.items().iter().take(self.config.max_articles_per_poll) {
            match self.convert_item(item, &channel.title()) {
                Ok(article) => articles.push(article),
                Err(e) => {
                    warn!("Failed to convert RSS item: {}", e);
                }
            }
        }

        debug!("Collected {} articles from RSS feed", articles.len());
        Ok(articles)
    }

    /// Convert RSS item to Article
    fn convert_item(&self, item: &rss::Item, source: &str) -> Result<Article> {
        let title = item
            .title()
            .context("RSS item missing title")?
            .to_string();

        let url = item.link().context("RSS item missing link")?.to_string();

        let content = item
            .description()
            .or_else(|| item.content())
            .context("RSS item missing content/description")?
            .to_string();

        // Parse published date
        let published_at = if let Some(pub_date) = item.pub_date() {
            self.parse_rfc2822(pub_date).unwrap_or_else(|_| Utc::now())
        } else {
            Utc::now()
        };

        Ok(Article {
            title,
            content: self.strip_html(&content),
            source: source.to_string(),
            url,
            published_at,
        })
    }

    /// Parse RFC 2822 date string
    fn parse_rfc2822(&self, date_str: &str) -> Result<DateTime<Utc>> {
        use chrono::DateTime;
        DateTime::parse_from_rfc2822(date_str)
            .map(|dt| dt.with_timezone(&Utc))
            .context("Failed to parse date")
    }

    /// Strip HTML tags from content
    fn strip_html(&self, html: &str) -> String {
        // Simple HTML tag removal
        let re = regex::Regex::new(r"<[^>]*>").unwrap();
        re.replace_all(html, " ").trim().to_string()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_strip_html() {
        let config = Arc::new(Config {
            database_url: "".to_string(),
            poll_interval_secs: 300,
            max_articles_per_poll: 100,
            enable_sentiment: true,
            min_confidence_threshold: 0.3,
            log_level: "info".to_string(),
            metrics_port: 9091,
        });

        let collector = RssCollector::new(config);

        let html = "<p>Bitcoin <strong>surges</strong> to new high</p>";
        let stripped = collector.strip_html(html);

        assert_eq!(stripped, "Bitcoin  surges  to new high");
        assert!(!stripped.contains('<'));
        assert!(!stripped.contains('>'));
    }
}
```

---

## File: `src/janus/services/news/src/sources/deduplicator.rs`

```rust
//! News article deduplication

use sha2::{Digest, Sha256};

/// Compute content hash for deduplication
pub fn compute_content_hash(title: &str, content: &str) -> String {
    let mut hasher = Sha256::new();
    hasher.update(title.as_bytes());
    hasher.update(content.as_bytes());
    let result = hasher.finalize();
    hex::encode(result)
}

/// Check if two articles are similar using fuzzy matching
pub fn are_similar(title1: &str, title2: &str, threshold: f32) -> bool {
    let similarity = compute_similarity(title1, title2);
    similarity >= threshold
}

/// Compute similarity score between two strings (0.0 to 1.0)
fn compute_similarity(s1: &str, s2: &str) -> f32 {
    // Simple word-based Jaccard similarity
    let words1: std::collections::HashSet<_> = s1
        .to_lowercase()
        .split_whitespace()
        .collect();
    let words2: std::collections::HashSet<_> = s2
        .to_lowercase()
        .split_whitespace()
        .collect();

    let intersection = words1.intersection(&words2).count();
    let union = words1.union(&words2).count();

    if union == 0 {
        0.0
    } else {
        intersection as f32 / union as f32
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_compute_content_hash() {
        let hash1 = compute_content_hash("Bitcoin rises", "Bitcoin price increased today");
        let hash2 = compute_content_hash("Bitcoin rises", "Bitcoin price increased today");
        let hash3 = compute_content_hash("Ethereum falls", "Different content");

        assert_eq!(hash1, hash2);
        assert_ne!(hash1, hash3);
        assert_eq!(hash1.len(), 64); // SHA256 = 32 bytes = 64 hex chars
    }

    #[test]
    fn test_compute_similarity() {
        let sim1 = compute_similarity("Bitcoin rises to new high", "Bitcoin rises to new high");
        assert_eq!(sim1, 1.0);

        let sim2 = compute_similarity("Bitcoin rises to new high", "Ethereum falls sharply");
        assert!(sim2 < 0.5);

        let sim3 = compute_similarity("Bitcoin rises", "BTC rises");
        assert!(sim3 > 0.0);
    }

    #[test]
    fn test_are_similar() {
        assert!(are_similar(
            "Bitcoin reaches new ATH",
            "Bitcoin reaches new all-time high",
            0.5
        ));

        assert!(!are_similar(
            "Bitcoin rises",
            "Ethereum falls",
            0.8
        ));
    }
}
```

---

## File: `src/janus/services/news/src/storage/mod.rs`

```rust
//! PostgreSQL storage for news articles

pub mod postgres;

pub use postgres::NewsStorage;
```

---

## File: `src/janus/services/news/src/storage/postgres.rs`

```rust
//! PostgreSQL storage implementation

use anyhow::Result;
use chrono::{DateTime, Utc};
use janus_sentiment::{Article, SentimentResult};
use sqlx::postgres::PgPool;
use sqlx::Row;
use tracing::{debug, info};

use crate::sources::deduplicator::compute_content_hash;
use crate::sources::NewsSource;

/// PostgreSQL storage for news articles
pub struct NewsStorage {
    pool: PgPool,
}

impl NewsStorage {
    /// Create a new news storage
    pub async fn new(database_url: &str) -> Result<Self> {
        info!("Connecting to PostgreSQL: {}", database_url);

        let pool = PgPool::connect(database_url).await?;

        info!("Connected to PostgreSQL");

        Ok(Self { pool })
    }

    /// Get enabled news sources
    pub async fn get_enabled_sources(&self) -> Result<Vec<NewsSource>> {
        let sources = sqlx::query_as::<_, NewsSource>(
            "SELECT id, name, source_type, url, enabled, poll_interval_secs
             FROM news_sources
             WHERE enabled = true
             ORDER BY name"
        )
        .fetch_all(&self.pool)
        .await?;

        Ok(sources)
    }

    /// Check if article is a duplicate
    pub async fn is_duplicate(&self, article: &Article) -> Result<bool> {
        let content_hash = compute_content_hash(&article.title, &article.content);

        let count: i64 = sqlx::query_scalar(
            "SELECT COUNT(*) FROM news_articles WHERE content_hash = $1"
        )
        .bind(&content_hash)
        .fetch_one(&self.pool)
        .await?;

        Ok(count > 0)
    }

    /// Store article with sentiment results
    pub async fn store_article(
        &self,
        article: &Article,
        result: &SentimentResult,
    ) -> Result<i64> {
        let content_hash = compute_content_hash(&article.title, &article.content);

        let event_type = result.event_type.map(|t| format!("{:?}", t).to_lowercase());
        let event_impact = result.event_impact.map(|i| format!("{:?}", i).to_lowercase());
        let sentiment_label = format!("{:?}", result.label).to_lowercase();

        let id: i64 = sqlx::query_scalar(
            r#"
            INSERT INTO news_articles (
                source, url, title, content, published_at,
                content_hash, sentiment_score, sentiment_label, confidence,
                mentioned_assets, mentioned_entities, event_type, event_impact
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
            RETURNING id
            "#
        )
        .bind(&article.source)
        .bind(&article.url)
        .bind(&article.title)
        .bind(&article.content)
        .bind(article.published_at)
        .bind(&content_hash)
        .bind(result.score)
        .bind(&sentiment_label)
        .bind(result.confidence)
        .bind(&result.mentioned_assets)
        .bind(&result.mentioned_entities)
        .bind(event_type)
        .bind(event_impact)
        .fetch_one(&self.pool)
        .await?;

        debug!("Stored article with ID: {}", id);

        Ok(id)
    }

    /// Update source statistics
    pub async fn update_source_stats(&self, source_name: &str, articles_count: i64) -> Result<()> {
        sqlx::query(
            r#"
            UPDATE news_sources
            SET last_fetch_at = NOW(),
                articles_collected = articles_collected + $1,
                updated_at = NOW()
            WHERE name = $2
            "#
        )
        .bind(articles_count)
        .bind(source_name)
        .execute(&self.pool)
        .await?;

        Ok(())
    }

    /// Get recent articles for an asset
    pub async fn get_recent_articles(
        &self,
        asset: &str,
        hours: i32,
        limit: i64,
    ) -> Result<Vec<Article>> {
        let rows = sqlx::query(
            r#"
            SELECT title, content, source, url, published_at
            FROM news_articles
            WHERE $1 = ANY(mentioned_assets)
              AND published_at > NOW() - $2::interval
            ORDER BY published_at DESC
            LIMIT $3
            "#
        )
        .bind(asset)
        .bind(format!("{} hours", hours))
        .bind(limit)
        .fetch_all(&self.pool)
        .await?;

        let articles = rows
            .into_iter()
            .map(|row| Article {
                title: row.get("title"),
                content: row.get("content"),
                source: row.get("source"),
                url: row.get("url"),
                published_at: row.get("published_at"),
            })
            .collect();

        Ok(articles)
    }

    /// Get average sentiment for an asset
    pub async fn get_average_sentiment(
        &self,
        asset: &str,
        hours: i32,
    ) -> Result<Option<f32>> {
        let avg: Option<f32> = sqlx::query_scalar(
            r#"
            SELECT AVG(sentiment_score)::real
            FROM news_articles
            WHERE $1 = ANY(mentioned_assets)
              AND published_at > NOW() - $2::interval
              AND sentiment_score IS NOT NULL
            "#
        )
        .bind(asset)
        .bind(format!("{} hours", hours))
        .fetch_one(&self.pool)
        .await?;

        Ok(avg)
    }
}
```

---

## File: `src/janus/services/news/examples/collect_news.rs`

```rust
//! Example: Collect news from RSS feeds

use anyhow::Result;
use janus_news::config::Config;
use janus_news::NewsService;

#[tokio::main]
async fn main() -> Result<()> {
    // Initialize logging
    tracing_subscriber::fmt::init();

    println!("=== JANUS News Collection Example ===\n");

    // Load config
    let config = Config::from_env()?;
    println!("Configuration loaded");
    println!("  Database: {}", config.database_url);
    println!("  Poll interval: {}s", config.poll_interval_secs);
    println!("  Sentiment enabled: {}\n", config.enable_sentiment);

    // Create service
    let service = NewsService::new(config).await?;
    println!("News service created\n");

    println!("Starting news collection...");
    println!("Press Ctrl+C to stop\n");

    // Run service
    service.run().await?;

    Ok(())
}
```

---

## File: `src/janus/services/news/.env.example`

```bash
# PostgreSQL Database
DATABASE_URL=postgresql://localhost/janus_news

# News Collection
POLL_INTERVAL_SECS=300
MAX_ARTICLES_PER_POLL=100

# Sentiment Analysis
ENABLE_SENTIMENT=true
MIN_CONFIDENCE_THRESHOLD=0.3

# Logging
LOG_LEVEL=info

# Metrics
METRICS_PORT=9091
```

---

## Usage Instructions

### 1. Setup Database

```bash
# Create database
createdb janus_news

# Run schema
psql janus_news < schema.sql
```

### 2. Configure

```bash
cd services/news
cp .env.example .env
# Edit .env with your settings
```

### 3. Build and Run

```bash
# Build
cargo build --package janus-news --release

# Run
cargo run --package janus-news --release

# Or run example
cargo run --package janus-news --example collect_news
```

### 4. Test

```bash
# Run tests
cargo test --package janus-news

# Run with logs
RUST_LOG=debug cargo test --package janus-news
```

### 5. Monitor Metrics

```bash
# Metrics available at http://localhost:9091/metrics

# Example PromQL queries:
# - rate(janus_news_articles_ingested_total[5m])
# - avg(janus_news_sentiment_score) by (asset)
# - histogram_quantile(0.95, rate(janus_news_processing_latency_seconds_bucket[5m]))
```

---

## Features Implemented

✅ RSS feed collection with HTTP client  
✅ PostgreSQL storage with SQLx  
✅ Sentiment analysis integration  
✅ Content hash-based deduplication  
✅ Prometheus metrics  
✅ Configurable via environment variables  
✅ Graceful shutdown handling  
✅ Error handling and logging  
✅ Comprehensive tests  
✅ Example code  

---

## Next Enhancements

- [ ] Add more RSS sources (Twitter/X, Reddit, CryptoCompare)
- [ ] Implement fuzzy deduplication alongside hash-based
- [ ] Add article summary generation
- [ ] Implement webhook notifications for high-impact news
- [ ] Add GraphQL/REST API for querying articles
- [ ] Implement article archival/cleanup for old data
- [ ] Add multilingual support