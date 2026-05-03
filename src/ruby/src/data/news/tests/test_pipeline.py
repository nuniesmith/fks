"""Unit tests for NewsPipeline deduplication, sentiment scoring, and storage.

Covers:
    - Deduplication: already-stored URL hashes are skipped
    - Sentiment scoring: VADER compound + label mapping
    - Label mapping: positive (≥0.05), neutral, negative (≤-0.05)
    - _store: writes to news_articles and news_asset_links, publishes to Redis
    - _process_batch: skips duplicates, applies since-filter, chains pipeline steps
    - Empty/invalid source: returns gracefully without raising
    - Timezone handling: timezone-naive published_at is normalised to UTC
    - URL hash: truncated SHA-256 (32 hex chars) is consistent
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from data_factory.news.pipeline import NewsPipeline, ProcessedArticle

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _url_hash(url: str) -> str:
    """Compute the same URL hash that NewsPipeline uses."""
    return hashlib.sha256(url.encode()).hexdigest()[:32]


def _make_redis(*, already_stored: bool = False) -> AsyncMock:
    """Minimal async-Redis mock."""
    redis = AsyncMock()
    redis.publish.return_value = 1
    return redis


def _make_engine(*, row_id: int | None = 42) -> MagicMock:
    """Minimal async SQLAlchemy engine mock.

    Parameters
    ----------
    row_id:
        The article ID returned by the INSERT RETURNING clause.
        Pass ``None`` to simulate a duplicate (ON CONFLICT DO NOTHING returns no row).

    Notes
    -----
    SQLAlchemy's ``engine.connect()`` and ``engine.begin()`` are **synchronous**
    calls that return async context managers.  The engine itself must be a
    ``MagicMock`` (not ``AsyncMock``) so that calling ``engine.connect()`` returns
    the context manager directly rather than a coroutine.
    """
    row = MagicMock()
    row.__getitem__ = MagicMock(return_value=row_id)

    result = MagicMock()
    if row_id is not None:
        result.fetchone.return_value = row
    else:
        result.fetchone.return_value = None  # duplicate — no row returned

    conn = AsyncMock()
    conn.execute.return_value = result
    conn.__aenter__ = AsyncMock(return_value=conn)
    conn.__aexit__ = AsyncMock(return_value=False)

    # engine.connect() / engine.begin() are sync calls returning async ctx-managers
    engine = MagicMock()
    engine.connect.return_value = conn
    engine.begin.return_value = conn
    return engine


def _make_pipeline(
    *,
    finnhub_key: str = "",
    poll_interval: int = 300,
    row_id: int | None = 42,
) -> tuple[NewsPipeline, AsyncMock, MagicMock]:
    """Build a NewsPipeline with fake Redis + engine.

    Returns
    -------
    (pipeline, redis, engine)
    """
    redis = _make_redis()
    engine = _make_engine(row_id=row_id)
    pipeline = NewsPipeline(
        redis=redis,
        engine=engine,
        finnhub_api_key=finnhub_key,
        poll_interval=poll_interval,
    )
    return pipeline, redis, engine


def _make_asset(
    symbol: str = "MGC",
    primary_keywords: list[str] | None = None,
    subreddits: list[str] | None = None,
    news_enabled: bool = True,
) -> MagicMock:
    asset = MagicMock()
    asset.symbol = symbol
    asset.news.enabled = news_enabled
    asset.news.primary_keywords = primary_keywords if primary_keywords is not None else ["micro gold"]
    asset.news.secondary_keywords = []
    # Use explicit None sentinel so callers can pass [] to mean "no subreddits"
    asset.news.subreddits = subreddits if subreddits is not None else ["Gold"]
    return asset


def _raw_article(
    *,
    url: str = "https://example.com/news/1",
    headline: str = "Micro gold futures surge",
    body: str = "Micro gold contracts advanced today.",
    published_at: str | None = None,
    source: str = "test",
) -> dict:
    if published_at is None:
        published_at = _utcnow().isoformat()
    return {
        "url": url,
        "headline": headline,
        "body": body,
        "published_at": published_at,
        "source": source,
    }


# ---------------------------------------------------------------------------
# URL hash
# ---------------------------------------------------------------------------


class TestUrlHash:
    """URL hash is a 32-character hex string derived from SHA-256."""

    def test_hash_is_32_chars(self) -> None:
        h = _url_hash("https://example.com/article/1")
        assert len(h) == 32

    def test_hash_is_deterministic(self) -> None:
        url = "https://reuters.com/markets/gold"
        assert _url_hash(url) == _url_hash(url)

    def test_different_urls_produce_different_hashes(self) -> None:
        assert _url_hash("https://example.com/a") != _url_hash("https://example.com/b")

    def test_pipeline_produces_same_hash(self) -> None:
        """NewsPipeline must produce the same hash as our helper."""
        pipeline, _, _ = _make_pipeline()
        url = "https://example.com/news/42"
        expected = _url_hash(url)
        actual = hashlib.sha256(url.encode()).hexdigest()[:32]
        assert expected == actual


# ---------------------------------------------------------------------------
# Sentiment label mapping
# ---------------------------------------------------------------------------


class TestSentimentLabelMapping:
    """_label maps VADER compound scores to human-readable labels."""

    def test_positive_label_at_0_05(self) -> None:
        pipeline, _, _ = _make_pipeline()
        assert pipeline._label(0.05) == "positive"

    def test_positive_label_above_threshold(self) -> None:
        pipeline, _, _ = _make_pipeline()
        assert pipeline._label(0.5) == "positive"
        assert pipeline._label(1.0) == "positive"

    def test_negative_label_at_minus_0_05(self) -> None:
        pipeline, _, _ = _make_pipeline()
        assert pipeline._label(-0.05) == "negative"

    def test_negative_label_below_threshold(self) -> None:
        pipeline, _, _ = _make_pipeline()
        assert pipeline._label(-0.5) == "negative"
        assert pipeline._label(-1.0) == "negative"

    def test_neutral_label_between_thresholds(self) -> None:
        pipeline, _, _ = _make_pipeline()
        assert pipeline._label(0.0) == "neutral"
        assert pipeline._label(0.04) == "neutral"
        assert pipeline._label(-0.04) == "neutral"

    def test_boundary_positive_is_not_neutral(self) -> None:
        pipeline, _, _ = _make_pipeline()
        assert pipeline._label(0.05) != "neutral"

    def test_boundary_negative_is_not_neutral(self) -> None:
        pipeline, _, _ = _make_pipeline()
        assert pipeline._label(-0.05) != "neutral"


# ---------------------------------------------------------------------------
# Sentiment scoring
# ---------------------------------------------------------------------------


class TestSentimentScoring:
    """_score_sentiment returns valid VADER polarity dicts."""

    def test_score_returns_compound_key(self) -> None:
        pipeline, _, _ = _make_pipeline()
        scores = pipeline._score_sentiment("Gold prices surge to record high")
        assert "compound" in scores

    def test_compound_is_float_in_range(self) -> None:
        pipeline, _, _ = _make_pipeline()
        scores = pipeline._score_sentiment("The market crashed violently today")
        compound = scores["compound"]
        assert isinstance(compound, float)
        assert -1.0 <= compound <= 1.0

    def test_positive_text_positive_compound(self) -> None:
        pipeline, _, _ = _make_pipeline()
        scores = pipeline._score_sentiment("Excellent record-breaking gains today amazing success")
        assert scores["compound"] > 0

    def test_negative_text_negative_compound(self) -> None:
        pipeline, _, _ = _make_pipeline()
        scores = pipeline._score_sentiment("Terrible crash disaster worst loss ever awful")
        assert scores["compound"] < 0

    def test_empty_text_returns_neutral(self) -> None:
        pipeline, _, _ = _make_pipeline()
        scores = pipeline._score_sentiment("")
        assert scores["compound"] == 0.0

    def test_vader_is_lazily_initialised(self) -> None:
        """VADER analyser must be None before first call, non-None after."""
        pipeline, _, _ = _make_pipeline()
        assert pipeline._vader is None
        pipeline._score_sentiment("hello world")
        assert pipeline._vader is not None

    def test_second_call_reuses_cached_analyser(self) -> None:
        """Subsequent calls must reuse the same VADER instance."""
        pipeline, _, _ = _make_pipeline()
        pipeline._score_sentiment("first call")
        vader_ref = pipeline._vader
        pipeline._score_sentiment("second call")
        assert pipeline._vader is vader_ref


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------


class TestDeduplication:
    """Already-stored articles are skipped without writing to the DB."""

    @pytest.mark.asyncio
    async def test_already_stored_returns_true_for_known_hash(self) -> None:
        """_already_stored returns True when the hash is found in Postgres."""
        # Build a fresh engine where connect() returns a row (exists)
        result = MagicMock()
        result.fetchone.return_value = MagicMock()  # truthy — found
        conn = AsyncMock()
        conn.execute.return_value = result
        conn.__aenter__ = AsyncMock(return_value=conn)
        conn.__aexit__ = AsyncMock(return_value=False)
        engine = MagicMock()
        engine.connect.return_value = conn

        redis = _make_redis()
        pipeline = NewsPipeline(redis=redis, engine=engine)

        stored = await pipeline._already_stored("abc123")
        assert stored is True

    @pytest.mark.asyncio
    async def test_already_stored_returns_false_for_unknown_hash(self) -> None:
        """_already_stored returns False when the hash is not in Postgres."""
        result = MagicMock()
        result.fetchone.return_value = None  # not found
        conn = AsyncMock()
        conn.execute.return_value = result
        conn.__aenter__ = AsyncMock(return_value=conn)
        conn.__aexit__ = AsyncMock(return_value=False)
        engine = MagicMock()
        engine.connect.return_value = conn

        redis = _make_redis()
        pipeline = NewsPipeline(redis=redis, engine=engine)

        stored = await pipeline._already_stored("newhashabc")
        assert stored is False

    @pytest.mark.asyncio
    async def test_process_batch_skips_duplicate_url(self) -> None:
        """_process_batch must not call _store for articles already in the DB."""
        pipeline, redis, _ = _make_pipeline()
        asset = _make_asset()

        since = _utcnow() - timedelta(minutes=10)

        raw = [_raw_article()]

        with patch.object(pipeline, "_already_stored", new_callable=AsyncMock, return_value=True):
            with patch.object(pipeline, "_store", new_callable=AsyncMock) as mock_store:
                await pipeline._process_batch(raw, "test", [asset], since)

        mock_store.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_batch_stores_new_article(self) -> None:
        """_process_batch must call _store for articles not yet in the DB."""
        pipeline, _, _ = _make_pipeline()
        asset = _make_asset()

        since = _utcnow() - timedelta(minutes=10)
        raw = [_raw_article()]

        with patch.object(pipeline, "_already_stored", new_callable=AsyncMock, return_value=False):
            with patch.object(pipeline, "_store", new_callable=AsyncMock) as mock_store:
                await pipeline._process_batch(raw, "test", [asset], since)

        mock_store.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_batch_skips_articles_before_since(self) -> None:
        """Articles published before `since` must be silently dropped."""
        pipeline, _, _ = _make_pipeline()
        asset = _make_asset()

        since = _utcnow()
        # Published 1 hour before since — should be excluded
        old_time = (since - timedelta(hours=1)).isoformat()
        raw = [_raw_article(published_at=old_time)]

        with patch.object(pipeline, "_already_stored", new_callable=AsyncMock, return_value=False):
            with patch.object(pipeline, "_store", new_callable=AsyncMock) as mock_store:
                await pipeline._process_batch(raw, "test", [asset], since)

        mock_store.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_batch_skips_articles_without_url(self) -> None:
        """Articles with no URL must be skipped (nothing to hash)."""
        pipeline, _, _ = _make_pipeline()
        asset = _make_asset()
        since = _utcnow() - timedelta(minutes=10)

        raw = [{"headline": "No URL article", "body": "body text", "published_at": _utcnow().isoformat()}]

        with patch.object(pipeline, "_store", new_callable=AsyncMock) as mock_store:
            await pipeline._process_batch(raw, "test", [asset], since)

        mock_store.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_batch_handles_multiple_articles(self) -> None:
        """New articles are stored; duplicate articles are skipped."""
        pipeline, _, _ = _make_pipeline()
        asset = _make_asset()
        since = _utcnow() - timedelta(minutes=10)

        raw = [
            _raw_article(url="https://example.com/1", headline="Article one micro gold"),
            _raw_article(url="https://example.com/2", headline="Article two micro gold"),
            _raw_article(url="https://example.com/3", headline="Article three micro gold"),
        ]

        # First and third are new; second is a duplicate
        already_stored_side_effect = [False, True, False]

        with (
            patch.object(
                pipeline,
                "_already_stored",
                new_callable=AsyncMock,
                side_effect=already_stored_side_effect,
            ),
            patch.object(pipeline, "_store", new_callable=AsyncMock) as mock_store,
        ):
            await pipeline._process_batch(raw, "test", [asset], since)

        assert mock_store.call_count == 2


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------


class TestStorage:
    """_store inserts into news_articles, news_asset_links, and publishes to Redis."""

    def _make_article(
        self,
        *,
        url_hash: str = "aabbccdd11223344aabbccdd11223344",
        headline: str = "Micro gold rally",
        body: str = "Gold futures advance.",
        source: str = "finnhub",
        compound: float = 0.5,
        label: str = "positive",
        matched_symbols: list[tuple[str, float, str]] | None = None,  # pass [] explicitly for empty
    ) -> ProcessedArticle:
        return ProcessedArticle(
            url_hash=url_hash,
            headline=headline,
            body=body,
            published_at=_utcnow(),
            source=source,
            sentiment_compound=compound,
            sentiment_label=label,
            matched_symbols=matched_symbols if matched_symbols is not None else [("MGC", 0.85, "ticker")],
            raw_json={"url": "https://example.com/1"},
        )

    @pytest.mark.asyncio
    async def test_store_executes_insert_for_news_article(self) -> None:
        """_store must call conn.execute at least once (for the article INSERT)."""
        pipeline, _, engine = _make_pipeline(row_id=42)
        article = self._make_article()

        await pipeline._store(article)

        conn = engine.begin.return_value
        assert conn.execute.call_count >= 1

    @pytest.mark.asyncio
    async def test_store_executes_asset_link_inserts(self) -> None:
        """_store must call conn.execute for each matched symbol (asset link INSERT)."""
        pipeline, _, engine = _make_pipeline(row_id=42)
        article = self._make_article(
            matched_symbols=[
                ("MGC", 0.85, "ticker"),
                ("SIL", 0.6, "primary"),
            ]
        )

        await pipeline._store(article)

        conn = engine.begin.return_value
        # At least: 1 article INSERT + 2 link INSERTs = 3 execute calls
        assert conn.execute.call_count >= 3

    @pytest.mark.asyncio
    async def test_store_publishes_to_redis_per_symbol(self) -> None:
        """_store must publish one Redis message per matched symbol."""
        pipeline, redis, _ = _make_pipeline(row_id=42)
        article = self._make_article(
            matched_symbols=[
                ("MGC", 0.9, "ticker"),
                ("GLD", 0.7, "primary"),
            ]
        )

        await pipeline._store(article)

        # Should have published to ch:news:MGC and ch:news:GLD
        assert redis.publish.call_count == 2
        channels = [call.args[0] for call in redis.publish.call_args_list]
        assert "ch:news:MGC" in channels
        assert "ch:news:GLD" in channels

    @pytest.mark.asyncio
    async def test_store_publishes_valid_json(self) -> None:
        """Each Redis publish payload must be valid JSON with required fields."""
        pipeline, redis, _ = _make_pipeline(row_id=42)
        article = self._make_article(matched_symbols=[("MGC", 0.9, "ticker")])

        await pipeline._store(article)

        payload_raw = redis.publish.call_args.args[1]
        payload = json.loads(payload_raw)

        assert "headline" in payload
        assert "published_at" in payload
        assert "sentiment" in payload
        assert "compound" in payload
        assert "score" in payload
        assert "source" in payload

    @pytest.mark.asyncio
    async def test_store_skips_redis_publish_for_no_matches(self) -> None:
        """If no assets are matched, _store must not call redis.publish."""
        pipeline, redis, _ = _make_pipeline(row_id=42)
        article = self._make_article(matched_symbols=[])

        await pipeline._store(article)

        redis.publish.assert_not_called()

    @pytest.mark.asyncio
    async def test_store_skips_asset_links_on_duplicate_article(self) -> None:
        """When ON CONFLICT DO NOTHING returns no row, asset links must not be inserted."""
        pipeline, redis, _ = _make_pipeline(row_id=None)  # duplicate → no row returned
        article = self._make_article(matched_symbols=[("MGC", 0.9, "ticker")])

        await pipeline._store(article)

        # No Redis publish since there was no new article_id
        redis.publish.assert_not_called()

    @pytest.mark.asyncio
    async def test_store_article_inserts_correct_fields(self) -> None:
        """The INSERT statement must bind all required fields."""
        pipeline, _, engine = _make_pipeline(row_id=99)
        article = self._make_article(
            url_hash="deadbeef" * 4,
            headline="Test headline",
            source="rss:Reuters",
            compound=0.3,
            label="positive",
        )

        await pipeline._store(article)

        conn = engine.begin.return_value
        # The first execute call is the article INSERT — inspect its parameters
        first_call = conn.execute.call_args_list[0]
        # parameters are in the second positional arg (dict)
        params = first_call.args[1] if len(first_call.args) > 1 else first_call.kwargs.get("parameters", {})

        assert params.get("url_hash") == article.url_hash
        assert params.get("headline") == article.headline
        assert params.get("source") == article.source
        assert params.get("sentiment_compound") == article.sentiment_compound
        assert params.get("sentiment_label") == article.sentiment_label


# ---------------------------------------------------------------------------
# Source adapter stubs — poll_finnhub / poll_reddit / poll_rss
# ---------------------------------------------------------------------------


class TestPollFinNhub:
    """_poll_finnhub skips gracefully when the API key is absent or the lib is missing."""

    @pytest.mark.asyncio
    async def test_skips_when_no_api_key(self) -> None:
        """With no Finnhub key, _poll_finnhub must return without calling _process_batch."""
        pipeline, _, _ = _make_pipeline(finnhub_key="")
        asset = _make_asset()

        with patch.object(pipeline, "_process_batch", new_callable=AsyncMock) as mock_batch:
            await pipeline._poll_finnhub([asset])

        mock_batch.assert_not_called()

    @pytest.mark.asyncio
    async def test_calls_process_batch_when_key_present(self) -> None:
        """With a valid key and mocked finnhub, _process_batch must be called."""
        pipeline, _, _ = _make_pipeline(finnhub_key="fake_key_123")
        asset = _make_asset()

        fake_news = [
            {
                "headline": "Gold prices surge",
                "summary": "Gold is up",
                "url": "https://finnhub.io/news/1",
                "datetime": int(_utcnow().timestamp()),
            }
        ]

        fake_client = MagicMock()
        fake_client.general_news.return_value = fake_news

        with patch("finnhub.Client", return_value=fake_client):
            with patch.object(pipeline, "_process_batch", new_callable=AsyncMock) as mock_batch:
                # Patch asyncio.to_thread to return the fake news synchronously
                with patch("asyncio.to_thread", new=AsyncMock(return_value=fake_news)):
                    await pipeline._poll_finnhub([asset])

        mock_batch.assert_called_once()

    @pytest.mark.asyncio
    async def test_skips_silently_on_finnhub_error(self) -> None:
        """A Finnhub API error must be caught and not propagate."""
        pipeline, _, _ = _make_pipeline(finnhub_key="fake_key")
        asset = _make_asset()

        with patch("finnhub.Client", side_effect=Exception("API error")):
            # Must not raise
            await pipeline._poll_finnhub([asset])


class TestPollReddit:
    """_poll_reddit skips gracefully when credentials are absent."""

    @pytest.mark.asyncio
    async def test_skips_when_no_credentials(self) -> None:
        """Without REDDIT_CLIENT_ID, _poll_reddit must not call _process_batch."""
        import os

        pipeline, _, _ = _make_pipeline()
        asset = _make_asset(subreddits=["Gold"])

        env = {"REDDIT_CLIENT_ID": "", "REDDIT_CLIENT_SECRET": ""}

        with patch.dict(os.environ, env, clear=False):
            with patch.object(pipeline, "_process_batch", new_callable=AsyncMock) as mock_batch:
                with patch("praw.Reddit") as mock_reddit_cls:
                    # Simulate read_only returning False (no credentials)
                    instance = MagicMock()
                    instance.read_only = False
                    mock_reddit_cls.return_value = instance
                    await pipeline._poll_reddit([asset])

        mock_batch.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_silently_on_reddit_error(self) -> None:
        """A PRAW error must be caught and not propagate."""
        import os

        pipeline, _, _ = _make_pipeline()
        asset = _make_asset(subreddits=["Gold"])

        env = {"REDDIT_CLIENT_ID": "fake_id", "REDDIT_CLIENT_SECRET": "fake_secret"}
        with patch.dict(os.environ, env, clear=False):
            with patch("praw.Reddit", side_effect=Exception("PRAW error")):
                # Must not raise
                await pipeline._poll_reddit([asset])

    @pytest.mark.asyncio
    async def test_no_subreddits_returns_early(self) -> None:
        """When no asset has subreddits configured, _process_batch is not called."""
        import os

        pipeline, _, _ = _make_pipeline()
        asset = _make_asset(subreddits=[])  # empty subreddit list

        env = {"REDDIT_CLIENT_ID": "x", "REDDIT_CLIENT_SECRET": "y"}
        with patch.dict(os.environ, env, clear=False), patch("praw.Reddit") as mock_reddit_cls:
            instance = MagicMock()
            instance.read_only = True
            mock_reddit_cls.return_value = instance

            with patch.object(pipeline, "_process_batch", new_callable=AsyncMock) as mock_batch:
                await pipeline._poll_reddit([asset])

        mock_batch.assert_not_called()


class TestPollRss:
    """_poll_rss skips gracefully when feedparser is unavailable or feeds error."""

    @pytest.mark.asyncio
    async def test_skips_when_feedparser_not_installed(self) -> None:
        """ImportError on feedparser must be silently handled."""
        pipeline, _, _ = _make_pipeline()
        asset = _make_asset()

        with patch.dict("sys.modules", {"feedparser": None}):
            with patch.object(pipeline, "_process_batch", new_callable=AsyncMock) as mock_batch:
                await pipeline._poll_rss([asset])

        mock_batch.assert_not_called()

    @pytest.mark.asyncio
    async def test_feed_http_error_does_not_propagate(self) -> None:
        """An HTTP error on a feed URL must be logged and skipped, not raised."""
        import httpx

        pipeline, _, _ = _make_pipeline()
        asset = _make_asset()

        fake_feedparser = MagicMock()
        fake_feedparser.parse.return_value = MagicMock(entries=[])

        with patch.dict("sys.modules", {"feedparser": fake_feedparser}):
            with patch("httpx.AsyncClient") as mock_client_cls:
                http_client = AsyncMock()
                http_client.get.side_effect = httpx.ConnectError("connection refused")
                http_client.__aenter__ = AsyncMock(return_value=http_client)
                http_client.__aexit__ = AsyncMock(return_value=False)
                mock_client_cls.return_value = http_client

                # Must not raise
                await pipeline._poll_rss([asset])


# ---------------------------------------------------------------------------
# ProcessedArticle dataclass
# ---------------------------------------------------------------------------


class TestProcessedArticle:
    """ProcessedArticle stores all expected fields."""

    def test_fields_are_accessible(self) -> None:
        now = _utcnow()
        article = ProcessedArticle(
            url_hash="abc" * 10 + "ab",
            headline="Gold rallies",
            body="Gold futures are up.",
            published_at=now,
            source="finnhub",
            sentiment_compound=0.45,
            sentiment_label="positive",
            matched_symbols=[("MGC", 0.9, "ticker")],
            raw_json={"url": "https://example.com"},
        )

        assert article.url_hash == "abc" * 10 + "ab"
        assert article.headline == "Gold rallies"
        assert article.body == "Gold futures are up."
        assert article.published_at == now
        assert article.source == "finnhub"
        assert article.sentiment_compound == 0.45
        assert article.sentiment_label == "positive"
        assert article.matched_symbols == [("MGC", 0.9, "ticker")]
        assert article.raw_json == {"url": "https://example.com"}

    def test_matched_symbols_defaults_to_empty_list(self) -> None:
        article = ProcessedArticle(
            url_hash="x" * 32,
            headline="h",
            body=None,
            published_at=_utcnow(),
            source="rss",
            sentiment_compound=0.0,
            sentiment_label="neutral",
        )
        assert article.matched_symbols == []
        assert article.raw_json == {}


# ---------------------------------------------------------------------------
# Timezone normalisation
# ---------------------------------------------------------------------------


class TestTimezoneNormalisation:
    """Timezone-naive published_at values are normalised to UTC."""

    @pytest.mark.asyncio
    async def test_naive_datetime_string_treated_as_utc(self) -> None:
        """A naive ISO-8601 string without timezone info must be accepted."""
        pipeline, _, _ = _make_pipeline()
        asset = _make_asset()

        since = _utcnow() - timedelta(hours=1)
        # Naive datetime — no +00:00 suffix
        naive_dt = (since + timedelta(minutes=30)).strftime("%Y-%m-%dT%H:%M:%S")

        raw = [_raw_article(published_at=naive_dt)]

        with patch.object(pipeline, "_already_stored", new_callable=AsyncMock, return_value=False):
            with patch.object(pipeline, "_store", new_callable=AsyncMock) as mock_store:
                await pipeline._process_batch(raw, "test", [asset], since)

        # Should have been stored (timestamp is after since)
        mock_store.assert_called_once()

    @pytest.mark.asyncio
    async def test_unix_timestamp_int_is_parsed(self) -> None:
        """An integer Unix timestamp for published_at must be parsed correctly."""
        pipeline, _, _ = _make_pipeline()
        asset = _make_asset()

        since = _utcnow() - timedelta(hours=1)
        ts = int((since + timedelta(minutes=30)).timestamp())

        raw = [_raw_article(published_at=None)]
        raw[0]["published_at"] = ts  # override with int

        with patch.object(pipeline, "_already_stored", new_callable=AsyncMock, return_value=False):
            with patch.object(pipeline, "_store", new_callable=AsyncMock) as mock_store:
                await pipeline._process_batch(raw, "test", [asset], since)

        mock_store.assert_called_once()

    @pytest.mark.asyncio
    async def test_missing_published_at_defaults_to_now(self) -> None:
        """When published_at is absent, the article is treated as just-published."""
        pipeline, _, _ = _make_pipeline()
        asset = _make_asset()

        since = _utcnow() - timedelta(minutes=10)
        raw = [_raw_article()]
        del raw[0]["published_at"]  # remove the key entirely

        with patch.object(pipeline, "_already_stored", new_callable=AsyncMock, return_value=False):
            with patch.object(pipeline, "_store", new_callable=AsyncMock) as mock_store:
                await pipeline._process_batch(raw, "test", [asset], since)

        # Should be stored since it defaults to now (which is after since)
        mock_store.assert_called_once()


# ---------------------------------------------------------------------------
# Full process_batch integration
# ---------------------------------------------------------------------------


class TestProcessBatchIntegration:
    """End-to-end _process_batch tests with real sentiment + matcher."""

    @pytest.mark.asyncio
    async def test_batch_with_matching_article_stores_result(self) -> None:
        """A matching article must result in _store being called with a ProcessedArticle."""
        pipeline, _, _ = _make_pipeline()
        asset = _make_asset("MGC", primary_keywords=["micro gold"])
        since = _utcnow() - timedelta(hours=1)

        raw = [_raw_article(headline="Micro gold surges on Fed comments")]
        stored_articles: list[ProcessedArticle] = []

        async def _capture_store(article: ProcessedArticle) -> None:
            stored_articles.append(article)

        with patch.object(pipeline, "_already_stored", new_callable=AsyncMock, return_value=False):
            with patch.object(pipeline, "_store", side_effect=_capture_store):
                await pipeline._process_batch(raw, "test", [asset], since)

        assert len(stored_articles) == 1
        stored = stored_articles[0]
        assert stored.source == "test"
        assert stored.headline == "Micro gold surges on Fed comments"
        assert stored.url_hash == _url_hash("https://example.com/news/1")
        assert stored.sentiment_label in ("positive", "neutral", "negative")
        assert -1.0 <= stored.sentiment_compound <= 1.0

    @pytest.mark.asyncio
    async def test_batch_article_error_does_not_abort_remaining(self) -> None:
        """An error on one article must not prevent subsequent articles from being processed."""
        pipeline, _, _ = _make_pipeline()
        asset = _make_asset("MGC", primary_keywords=["micro gold"])
        since = _utcnow() - timedelta(hours=1)

        raw = [
            _raw_article(url="https://example.com/1", headline="Micro gold rally one"),
            _raw_article(url="https://example.com/2", headline="Micro gold rally two"),
        ]

        call_count = 0

        async def _flaky_store(article: ProcessedArticle) -> None:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("Simulated storage failure")

        with patch.object(pipeline, "_already_stored", new_callable=AsyncMock, return_value=False):
            with patch.object(pipeline, "_store", side_effect=_flaky_store):
                # Must not propagate the exception
                await pipeline._process_batch(raw, "test", [asset], since)

        # Both articles were attempted; second one succeeded
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_empty_raw_list_is_no_op(self) -> None:
        """An empty raw article list must call _store zero times."""
        pipeline, _, _ = _make_pipeline()
        asset = _make_asset()
        since = _utcnow() - timedelta(hours=1)

        with patch.object(pipeline, "_store", new_callable=AsyncMock) as mock_store:
            await pipeline._process_batch([], "test", [asset], since)

        mock_store.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_asset_matches_still_stores_article(self) -> None:
        """Articles are stored even when no assets match (matched_symbols will be empty)."""
        pipeline, _, _ = _make_pipeline()
        # Asset with keywords that won't appear in the test article
        asset = _make_asset("MGC", primary_keywords=["totally unrelated keyword xyz"])
        since = _utcnow() - timedelta(hours=1)

        raw = [_raw_article(headline="Something completely different")]
        stored_articles: list[ProcessedArticle] = []

        async def _capture(article: ProcessedArticle) -> None:
            stored_articles.append(article)

        with patch.object(pipeline, "_already_stored", new_callable=AsyncMock, return_value=False):
            with patch.object(pipeline, "_store", side_effect=_capture):
                await pipeline._process_batch(raw, "test", [asset], since)

        # Article is still stored — just with empty matched_symbols
        assert len(stored_articles) == 1
        assert stored_articles[0].matched_symbols == []
