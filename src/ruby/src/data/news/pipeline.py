"""Multi-source news ingestion pipeline.

Ingests news from all enabled sources, deduplicates articles by URL hash,
runs NLP sentiment scoring (VADER), matches articles to tracked assets, and
stores results linked to assets in Postgres.  Scored articles are also
published to Redis pub/sub so that downstream consumers (engine, dashboards)
receive updates in near-real-time.

Sources
-------
* **Finnhub** — general market news via the Finnhub REST API.
* **Reddit** — new posts from asset-specific subreddits via PRAW.
* **RSS** — curated list of financial news feeds (Reuters, MarketWatch, etc.).

Processing
----------
Each article is:

1. Deduplicated by a truncated SHA-256 hash of its canonical URL.
2. Scored with VADER (compound + label).
3. Matched to tracked assets using :class:`.matcher.AssetMatcher`.
4. Stored in Postgres (``news_articles`` table) with asset links written to
   ``news_asset_links``.
5. Published to Redis pub/sub on ``ch:news:<symbol>`` channels.

Tables
------
* ``news_articles`` — one row per unique article (keyed on ``url_hash``).
* ``news_asset_links`` — many-to-many join between articles and assets.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from core.logging_config import get_logger

if TYPE_CHECKING:
    import redis.asyncio as aioredis
    from sqlalchemy.ext.asyncio import AsyncEngine

    from ..registry.asset_registry import AssetRegistry
    from ..registry.schemas import AssetConfig

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

NEWS_CHANNEL_PREFIX: str = "ch:news"
"""Redis pub/sub channel prefix for real-time news events."""

NEWS_POLL_INTERVAL: int = 300
"""Default polling interval in seconds (5 minutes)."""


# ---------------------------------------------------------------------------
# ProcessedArticle
# ---------------------------------------------------------------------------


@dataclass
class ProcessedArticle:
    """A fully processed news article ready for storage."""

    url_hash: str
    headline: str
    body: str | None
    published_at: datetime
    source: str
    sentiment_compound: float
    sentiment_label: str
    matched_symbols: list[tuple[str, float, str]] = field(default_factory=list)
    raw_json: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# NewsPipeline
# ---------------------------------------------------------------------------


class NewsPipeline:
    """Polls multiple news sources, deduplicates, scores, and stores articles.

    Parameters
    ----------
    redis:
        An async Redis client (``redis.asyncio.Redis`` or compatible).
    engine:
        An async SQLAlchemy engine pointing at the Postgres database.
    finnhub_api_key:
        Optional Finnhub API key.  When empty the Finnhub source is skipped.
    poll_interval:
        Seconds between polling cycles (default :data:`NEWS_POLL_INTERVAL`).
    """

    def __init__(
        self,
        redis: aioredis.Redis,  # type: ignore[name-defined]
        engine: AsyncEngine,
        finnhub_api_key: str = "",
        poll_interval: int = NEWS_POLL_INTERVAL,
    ) -> None:
        self._redis = redis
        self._engine = engine
        self._finnhub_key = finnhub_api_key
        self._poll_interval = poll_interval
        self._vader: Any = None  # lazy-initialised SentimentIntensityAnalyzer

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    async def run(self, registry: AssetRegistry) -> None:
        """Run the news pipeline indefinitely.

        Parameters
        ----------
        registry:
            The :class:`AssetRegistry` used to look up enabled assets and
            their per-asset news configuration.
        """
        log.info("news_pipeline.starting", poll_interval=self._poll_interval)
        await asyncio.sleep(30)  # let other services stabilise

        while True:
            try:
                enabled = await registry.enabled_assets()
                assets = [a for a in enabled if a.news.enabled]

                if not assets:
                    log.debug("news_pipeline.no_news_assets")
                else:
                    results = await asyncio.gather(
                        self._poll_finnhub(assets),
                        self._poll_reddit(assets),
                        self._poll_rss(assets),
                        return_exceptions=True,
                    )
                    for idx, result in enumerate(results):
                        if isinstance(result, Exception):
                            source_name = ("finnhub", "reddit", "rss")[idx]
                            log.warning(
                                "news_pipeline.source_error",
                                source=source_name,
                                error=str(result),
                            )
            except Exception:
                log.exception("news_pipeline.cycle_error")

            await asyncio.sleep(self._poll_interval)

    # ------------------------------------------------------------------
    # Source fetchers
    # ------------------------------------------------------------------

    async def _poll_finnhub(self, assets: list[AssetConfig]) -> None:
        """Fetch general news from the Finnhub REST API."""
        if not self._finnhub_key:
            return

        try:
            import finnhub  # type: ignore[import-untyped]
        except ImportError:
            log.debug("news_pipeline.finnhub_not_installed")
            return

        try:
            client = finnhub.Client(api_key=self._finnhub_key)
            since = datetime.now(UTC) - timedelta(seconds=self._poll_interval * 2)

            raw: list[dict[str, Any]] = await asyncio.to_thread(client.general_news, "general", min_id=0)

            log.debug("news_pipeline.finnhub_fetched", count=len(raw))
            await self._process_batch(raw, "finnhub", assets, since)
        except Exception:
            log.warning("news_pipeline.finnhub_error", exc_info=True)

    async def _poll_reddit(self, assets: list[AssetConfig]) -> None:
        """Fetch new posts from asset-specific subreddits via PRAW."""
        try:
            import praw  # type: ignore[import-untyped]
        except ImportError:
            log.debug("news_pipeline.praw_not_installed")
            return

        try:
            client_id = os.environ.get("REDDIT_CLIENT_ID", "")
            client_secret = os.environ.get("REDDIT_CLIENT_SECRET", "")

            reddit = praw.Reddit(
                client_id=client_id,
                client_secret=client_secret,
                user_agent="FKS-DataFactory/1.0",
            )

            if not reddit.read_only:
                log.debug("news_pipeline.reddit_no_readonly")
                return

            # Collect unique subreddits across all assets
            subreddits: set[str] = set()
            for asset in assets:
                for sub in asset.news.subreddits:
                    subreddits.add(sub)

            if not subreddits:
                return

            multi = "+".join(sorted(subreddits))
            since = datetime.now(UTC) - timedelta(seconds=self._poll_interval * 2)

            posts = await asyncio.to_thread(lambda: list(reddit.subreddit(multi).new(limit=50)))

            raw: list[dict[str, Any]] = []
            for post in posts:
                published_at = datetime.fromtimestamp(post.created_utc, tz=UTC)
                if published_at < since:
                    continue
                raw.append(
                    {
                        "headline": post.title,
                        "body": (post.selftext or "")[:2000],
                        "url": f"https://reddit.com{post.permalink}",
                        "published_at": published_at.isoformat(),
                        "source": "reddit",
                        "subreddit": str(post.subreddit),
                        "score": post.score,
                        "upvote_ratio": post.upvote_ratio,
                    }
                )

            log.debug("news_pipeline.reddit_fetched", count=len(raw))
            await self._process_batch(raw, "reddit", assets, since)
        except Exception:
            log.warning("news_pipeline.reddit_error", exc_info=True)

    async def _poll_rss(self, assets: list[AssetConfig]) -> None:
        """Fetch articles from curated financial RSS feeds."""
        try:
            import feedparser  # type: ignore[import-untyped]
        except ImportError:
            log.debug("news_pipeline.feedparser_not_installed")
            return

        import httpx

        RSS_FEEDS: list[tuple[str, str]] = [
            ("Reuters Markets", "https://www.reutersagency.com/feed/?taxonomy=best-sectors&post_type=best"),
            ("MarketWatch", "https://feeds.marketwatch.com/marketwatch/topstories/"),
            ("Investing.com", "https://www.investing.com/rss/news.rss"),
            ("FX Street", "https://www.fxstreet.com/rss"),
            ("CME Group News", "https://www.cmegroup.com/rss/news.xml"),
            ("CoinDesk", "https://www.coindesk.com/arc/outboundfeeds/rss/"),
        ]

        since = datetime.now(UTC) - timedelta(seconds=self._poll_interval * 2)

        async with httpx.AsyncClient(timeout=15) as http:
            for feed_name, feed_url in RSS_FEEDS:
                try:
                    resp = await http.get(feed_url)
                    resp.raise_for_status()

                    parsed = await asyncio.to_thread(feedparser.parse, resp.text)
                    entries = parsed.entries[:30]

                    raw: list[dict[str, Any]] = []
                    for entry in entries:
                        raw.append(
                            {
                                "headline": getattr(entry, "title", ""),
                                "body": getattr(entry, "summary", ""),
                                "url": getattr(entry, "link", ""),
                                "published_at": getattr(entry, "published", ""),
                                "source": f"rss:{feed_name}",
                            }
                        )

                    log.debug(
                        "news_pipeline.rss_fetched",
                        feed=feed_name,
                        count=len(raw),
                    )
                    await self._process_batch(raw, f"rss:{feed_name}", assets, since)
                except Exception:
                    log.debug(
                        "news_pipeline.rss_feed_error",
                        feed=feed_name,
                        exc_info=True,
                    )

    # ------------------------------------------------------------------
    # Processing
    # ------------------------------------------------------------------

    async def _process_batch(
        self,
        raw_articles: list[dict[str, Any]],
        source: str,
        assets: list[AssetConfig],
        since: datetime,
    ) -> None:
        """Deduplicate, score, match, and store a batch of raw articles."""
        from .matcher import AssetMatcher

        matcher = AssetMatcher()

        for raw in raw_articles:
            try:
                url = raw.get("url") or raw.get("link") or ""
                if not url:
                    continue

                url_hash = hashlib.sha256(url.encode()).hexdigest()[:32]

                if await self._already_stored(url_hash):
                    continue

                headline = raw.get("headline") or raw.get("title") or ""
                body = raw.get("body") or raw.get("summary") or raw.get("text")

                # -- Parse published_at ------------------------------------
                published_raw = raw.get("published_at") or raw.get("published") or ""
                published_at: datetime
                if isinstance(published_raw, datetime):
                    published_at = published_raw
                elif isinstance(published_raw, (int, float)):
                    published_at = datetime.fromtimestamp(published_raw, tz=UTC)
                elif isinstance(published_raw, str) and published_raw:
                    try:
                        cleaned = published_raw.replace("Z", "+00:00")
                        published_at = datetime.fromisoformat(cleaned)
                    except (ValueError, TypeError):
                        published_at = datetime.now(UTC)
                else:
                    published_at = datetime.now(UTC)

                # Ensure timezone-aware (UTC)
                if published_at.tzinfo is None:
                    published_at = published_at.replace(tzinfo=UTC)

                if published_at < since:
                    continue

                # -- Sentiment ---------------------------------------------
                sentiment = self._score_sentiment(f"{headline} {body or ''}")
                compound: float = sentiment.get("compound", 0.0)
                label = self._label(compound)

                # -- Asset matching ----------------------------------------
                matched = matcher.match(headline, body or "", assets)

                article = ProcessedArticle(
                    url_hash=url_hash,
                    headline=headline,
                    body=body,
                    published_at=published_at,
                    source=source,
                    sentiment_compound=compound,
                    sentiment_label=label,
                    matched_symbols=matched,
                    raw_json=raw,
                )

                await self._store(article)
            except Exception:
                log.debug(
                    "news_pipeline.article_error",
                    source=source,
                    exc_info=True,
                )

    # ------------------------------------------------------------------
    # Sentiment
    # ------------------------------------------------------------------

    def _score_sentiment(self, text: str) -> dict[str, float]:
        """Return VADER polarity scores for *text* (lazy-loads the analyser)."""
        if self._vader is None:
            from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer  # type: ignore[import-untyped]

            self._vader = SentimentIntensityAnalyzer()
        return self._vader.polarity_scores(text)

    @staticmethod
    def _label(compound: float) -> str:
        """Map a VADER compound score to a human-readable label."""
        if compound >= 0.05:
            return "positive"
        if compound <= -0.05:
            return "negative"
        return "neutral"

    # ------------------------------------------------------------------
    # Storage helpers
    # ------------------------------------------------------------------

    async def _already_stored(self, url_hash: str) -> bool:
        """Return ``True`` if an article with *url_hash* exists in Postgres."""
        from sqlalchemy import text

        async with self._engine.connect() as conn:
            row = await conn.execute(
                text("SELECT 1 FROM news_articles WHERE url_hash = :h LIMIT 1"),
                {"h": url_hash},
            )
            return row.fetchone() is not None

    async def _store(self, article: ProcessedArticle) -> None:
        """Persist a :class:`ProcessedArticle` and publish to Redis pub/sub."""
        from sqlalchemy import text

        async with self._engine.begin() as conn:
            result = await conn.execute(
                text(
                    """
                    INSERT INTO news_articles
                        (url_hash, headline, body, published_at, source,
                         sentiment_compound, sentiment_label, raw_json)
                    VALUES
                        (:url_hash, :headline, :body, :published_at, :source,
                         :sentiment_compound, :sentiment_label, :raw_json)
                    ON CONFLICT (url_hash) DO NOTHING
                    RETURNING id
                    """
                ),
                {
                    "url_hash": article.url_hash,
                    "headline": article.headline,
                    "body": article.body,
                    "published_at": article.published_at,
                    "source": article.source,
                    "sentiment_compound": article.sentiment_compound,
                    "sentiment_label": article.sentiment_label,
                    "raw_json": json.dumps(article.raw_json),
                },
            )

            row = result.fetchone()
            if row is None:
                # Duplicate — already inserted by a concurrent worker
                return

            article_id = row[0]

            # -- Asset links -----------------------------------------------
            for symbol, score, match_type in article.matched_symbols:
                await conn.execute(
                    text(
                        """
                        INSERT INTO news_asset_links
                            (article_id, symbol, relevance_score, match_type)
                        VALUES
                            (:article_id, :symbol, :relevance_score, :match_type)
                        ON CONFLICT DO NOTHING
                        """
                    ),
                    {
                        "article_id": article_id,
                        "symbol": symbol,
                        "relevance_score": score,
                        "match_type": match_type,
                    },
                )

        # -- Redis pub/sub -------------------------------------------------
        for symbol, score, _match_type in article.matched_symbols:
            channel = f"{NEWS_CHANNEL_PREFIX}:{symbol}"
            payload = json.dumps(
                {
                    "id": article_id,
                    "headline": article.headline,
                    "published_at": article.published_at.isoformat(),
                    "sentiment": article.sentiment_label,
                    "compound": article.sentiment_compound,
                    "score": score,
                    "source": article.source,
                }
            )
            try:
                await self._redis.publish(channel, payload)
            except Exception:
                log.debug(
                    "news_pipeline.publish_error",
                    channel=channel,
                    exc_info=True,
                )

        log.debug(
            "news_pipeline.stored",
            url_hash=article.url_hash,
            source=article.source,
            matched=len(article.matched_symbols),
        )
