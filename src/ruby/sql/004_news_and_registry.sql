-- =============================================================================
-- 05_news_and_registry.sql — Asset registry & news ingestion tables
-- Adds the centralised asset registry, news article storage, and the
-- many-to-many link table that ties articles to assets.
-- Must run against ruby_db (the data/engine database).
--
-- Tables created:
--   asset_registry   — Canonical list of every tradeable asset
--   news_articles    — Ingested news / headlines with sentiment scores
--   news_asset_links — Many-to-many link between articles and assets
--
-- Views created:
--   news_with_assets — Convenience join of articles ↔ linked assets
-- =============================================================================

\set ruby_db `echo "${RUBY_DB:-ruby_db}"`
\set fks_user    `echo "${POSTGRES_USER:-fks_user}"`

\connect :ruby_db

-- ---------------------------------------------------------------------------
-- asset_registry
-- ---------------------------------------------------------------------------
-- Canonical, system-wide list of every asset the platform knows about.
-- `enabled` gates whether the asset is actively tracked / tradeable.
-- `config_json` holds per-asset overrides (lot size, tick value, etc.).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS asset_registry (
    symbol          TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    asset_class     TEXT NOT NULL,
    exchange        TEXT NOT NULL,
    enabled         BOOLEAN NOT NULL DEFAULT FALSE,
    config_json     JSONB NOT NULL DEFAULT '{}',
    disable_reason  TEXT,
    disabled_at     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Fast lookup of all currently-enabled assets
CREATE INDEX IF NOT EXISTS idx_asset_registry_enabled
    ON asset_registry (symbol)
    WHERE enabled = TRUE;

-- Filter / group by asset class (crypto, futures, equity, …)
CREATE INDEX IF NOT EXISTS idx_asset_registry_class
    ON asset_registry (asset_class);

-- ---------------------------------------------------------------------------
-- news_articles
-- ---------------------------------------------------------------------------
-- Stores ingested news articles and their pre-computed sentiment scores.
-- `url_hash` is a deterministic hash of the article URL used for dedup.
-- `sentiment_compound` / `sentiment_label` are filled by the NLP pipeline.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS news_articles (
    id                  BIGSERIAL PRIMARY KEY,
    url_hash            TEXT NOT NULL UNIQUE,
    headline            TEXT NOT NULL,
    body                TEXT,
    published_at        TIMESTAMPTZ NOT NULL,
    source              TEXT NOT NULL,
    sentiment_compound  REAL,
    sentiment_label     TEXT,
    raw_json            JSONB,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Full-text search across headline and body
CREATE INDEX IF NOT EXISTS idx_news_fts
    ON news_articles
    USING GIN (to_tsvector('english', coalesce(headline, '') || ' ' || coalesce(body, '')));

-- Time-ordered listing of articles
CREATE INDEX IF NOT EXISTS idx_news_published
    ON news_articles (published_at DESC);

-- Filter by news source
CREATE INDEX IF NOT EXISTS idx_news_source
    ON news_articles (source);

-- Filter / sort by sentiment score
CREATE INDEX IF NOT EXISTS idx_news_sentiment
    ON news_articles (sentiment_compound);

-- ---------------------------------------------------------------------------
-- news_asset_links
-- ---------------------------------------------------------------------------
-- Many-to-many link between news_articles and assets.
-- `relevance_score` (0.0–1.0) indicates how strongly the article relates to
-- the asset.  `match_type` records how the link was established (e.g.
-- 'ticker_mention', 'nlp_entity', 'manual').
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS news_asset_links (
    id               BIGSERIAL PRIMARY KEY,
    article_id       BIGINT NOT NULL REFERENCES news_articles (id) ON DELETE CASCADE,
    symbol           TEXT NOT NULL,
    relevance_score  REAL NOT NULL,
    match_type       TEXT NOT NULL,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (article_id, symbol)
);

-- Look up all articles for a given asset
CREATE INDEX IF NOT EXISTS idx_news_links_symbol
    ON news_asset_links (symbol);

-- Look up all assets for a given article
CREATE INDEX IF NOT EXISTS idx_news_links_article
    ON news_asset_links (article_id);

-- Filter links by relevance threshold
CREATE INDEX IF NOT EXISTS idx_news_links_score
    ON news_asset_links (relevance_score);

-- ---------------------------------------------------------------------------
-- news_with_assets  (convenience view)
-- ---------------------------------------------------------------------------
-- Flattened join of articles and their linked assets for easy querying.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW news_with_assets AS
SELECT
    a.id,
    a.headline,
    a.published_at,
    a.source,
    a.sentiment_compound,
    a.sentiment_label,
    l.symbol,
    l.relevance_score,
    l.match_type
FROM news_articles a
JOIN news_asset_links l ON l.article_id = a.id;
