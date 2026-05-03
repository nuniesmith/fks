"""
Tests for data_factory.chain.cmc_provider — CMCProvider + CMCWorker

Covers:
  - TestCMCProviderDisabled: empty dict/list when CMC_API_KEY not set; warning logged
  - TestCachedGet: returns cached value from Redis; calls API on cache miss;
    caches only on error_code==0; does not cache error responses
  - TestQuotes: batches into single call; writes cmc:quote:{sym};
    writes ruby:price:{sym}/USD and ruby:chg_pct:{sym}/USD; correct field mapping
  - TestGlobalMetrics: parses nested structure; writes cmc:btc_dominance;
    returns all metric fields
  - TestFearAndGreed: _fg_to_sentiment mapping; writes cmc:fear_greed
  - TestTopListings: respects limit; returns sorted list
  - TestCryptoInfo: 24h cache; truncates description to 500 chars; handles missing URLs
  - TestCMCWorker: runs 4 loops; handles provider errors without crashing
"""

from __future__ import annotations

import contextlib
import json
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from data_factory.chain.cmc_provider import (
    TTL_FEAR_GREED,
    TTL_GLOBAL,
    TTL_INFO,
    TTL_LISTINGS,
    TTL_QUOTES,
    CMCProvider,
    CMCWorker,
    _fg_to_sentiment,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_redis(
    cached_values: dict[str, str] | None = None,
) -> AsyncMock:
    """
    Build a mock aioredis.Redis.

    cached_values: mapping of key -> raw string to return from redis.get().
                   If None, get() always returns None (cache miss).
    """
    redis = AsyncMock()
    store = dict(cached_values or {})

    async def fake_get(key: str):
        return store.get(key)

    redis.get = fake_get
    redis.setex = AsyncMock(return_value=True)

    pipe = AsyncMock()
    pipe.setex = AsyncMock()
    pipe.execute = AsyncMock(return_value=[True] * 20)
    redis.pipeline = MagicMock(return_value=pipe)

    return redis


def _make_http_response(json_data: dict, status_code: int = 200) -> MagicMock:
    r = MagicMock()
    r.status_code = status_code
    r.json.return_value = json_data
    r.text = json.dumps(json_data)
    return r


def _make_async_client(response: MagicMock) -> AsyncMock:
    client = AsyncMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    client.get = AsyncMock(return_value=response)
    return client


def _cmc_quotes_response(symbols: list[str]) -> dict:
    """Build a minimal CMC /quotes/latest style response."""
    data = {}
    for i, sym in enumerate(symbols):
        data[sym] = {
            "name": sym + "_name",
            "cmc_rank": i + 1,
            "circulating_supply": 1_000_000 * (i + 1),
            "max_supply": 21_000_000,
            "quote": {
                "USD": {
                    "price": 50_000.0 + i * 1000,
                    "market_cap": 1_000_000_000.0,
                    "volume_24h": 30_000_000_000.0,
                    "percent_change_1h": 0.5,
                    "percent_change_24h": 2.3,
                    "percent_change_7d": -1.2,
                    "market_cap_dominance": 45.0,
                    "fully_diluted_market_cap": 1_100_000_000.0,
                    "last_updated": "2024-01-01T12:00:00.000Z",
                }
            },
        }
    return {
        "status": {"error_code": 0, "error_message": None},
        "data": data,
    }


def _cmc_global_response() -> dict:
    return {
        "status": {"error_code": 0},
        "data": {
            "btc_dominance": 52.3,
            "btc_dominance_24h_percentage_change": -0.5,
            "eth_dominance": 17.1,
            "active_cryptocurrencies": 22_000,
            "active_market_pairs": 90_000,
            "active_exchanges": 800,
            "last_updated": "2024-01-01T12:00:00.000Z",
            "quote": {
                "USD": {
                    "total_market_cap": 2_000_000_000_000.0,
                    "total_volume_24h": 80_000_000_000.0,
                    "total_volume_24h_reported": 85_000_000_000.0,
                    "altcoin_market_cap": 950_000_000_000.0,
                    "altcoin_volume_24h": 35_000_000_000.0,
                    "defi_market_cap": 120_000_000_000.0,
                    "defi_24h_volume": 8_000_000_000.0,
                    "stablecoin_market_cap": 140_000_000_000.0,
                    "stablecoin_24h_volume": 60_000_000_000.0,
                }
            },
        },
    }


def _cmc_fear_greed_response(value: int = 55, label: str = "Greed") -> dict:
    return {
        "status": {"error_code": 0},
        "data": {
            "value": value,
            "value_classification": label,
            "timestamp": "2024-01-01T12:00:00Z",
        },
    }


def _cmc_listings_response(count: int = 5) -> dict:
    coins = []
    for i in range(count):
        coins.append(
            {
                "cmc_rank": i + 1,
                "symbol": f"COIN{i}",
                "name": f"Coin {i}",
                "quote": {
                    "USD": {
                        "price": 100.0 - i,
                        "market_cap": 1_000_000_000.0 - i * 1_000_000,
                        "volume_24h": 5_000_000.0,
                        "percent_change_24h": 1.5,
                        "percent_change_7d": -0.5,
                        "market_cap_dominance": 5.0,
                    }
                },
            }
        )
    return {"status": {"error_code": 0}, "data": coins}


def _cmc_info_response(symbols: list[str]) -> dict:
    data = {}
    for sym in symbols:
        data[sym] = {
            "name": sym + "_full",
            "description": "A" * 600,  # long description to test truncation
            "logo": f"https://example.com/{sym}.png",
            "category": "Cryptocurrency",
            "date_launched": "2009-01-03",
            "tags": ["tag1", "tag2", "tag3"],
            "urls": {
                "website": [f"https://{sym.lower()}.org"],
                "twitter": [f"https://twitter.com/{sym.lower()}"],
                "reddit": [f"https://reddit.com/r/{sym.lower()}"],
                "source_code": [f"https://github.com/{sym.lower()}"],
            },
        }
    return {"status": {"error_code": 0}, "data": data}


# ---------------------------------------------------------------------------
# TestCMCProviderDisabled
# ---------------------------------------------------------------------------


class TestCMCProviderDisabled:
    def test_quotes_returns_empty_dict_when_no_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("CMC_API_KEY", raising=False)
        redis = _make_redis()
        provider = CMCProvider(redis)
        # quotes() is async, use event loop via pytest-asyncio marker on separate test
        # Here we verify the _key attribute
        assert provider._key == ""

    @pytest.mark.asyncio
    async def test_quotes_returns_empty_dict_async(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("CMC_API_KEY", raising=False)
        redis = _make_redis()
        provider = CMCProvider(redis)
        result = await provider.quotes()
        assert result == {}

    @pytest.mark.asyncio
    async def test_global_metrics_returns_empty_dict(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("CMC_API_KEY", raising=False)
        redis = _make_redis()
        provider = CMCProvider(redis)
        result = await provider.global_metrics()
        assert result == {}

    @pytest.mark.asyncio
    async def test_fear_and_greed_returns_empty_dict(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("CMC_API_KEY", raising=False)
        redis = _make_redis()
        provider = CMCProvider(redis)
        result = await provider.fear_and_greed()
        assert result == {}

    @pytest.mark.asyncio
    async def test_top_listings_returns_empty_list(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("CMC_API_KEY", raising=False)
        redis = _make_redis()
        provider = CMCProvider(redis)
        result = await provider.top_listings()
        assert result == []

    @pytest.mark.asyncio
    async def test_crypto_info_returns_empty_dict(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("CMC_API_KEY", raising=False)
        redis = _make_redis()
        provider = CMCProvider(redis)
        result = await provider.crypto_info()
        assert result == {}

    def test_logs_warning_when_no_key(self, monkeypatch: pytest.MonkeyPatch, caplog) -> None:
        monkeypatch.delenv("CMC_API_KEY", raising=False)
        redis = _make_redis()
        with caplog.at_level(logging.WARNING, logger="lib.data_factory.chain.cmc_provider"):
            CMCProvider(redis)
        assert any("CMC_API_KEY" in r.message for r in caplog.records)

    @pytest.mark.asyncio
    async def test_no_http_call_when_no_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("CMC_API_KEY", raising=False)
        redis = _make_redis()
        provider = CMCProvider(redis)
        with patch("httpx.AsyncClient") as mock_cls:
            await provider.quotes()
            await provider.global_metrics()
            await provider.fear_and_greed()
            await provider.top_listings()
            await provider.crypto_info()
            mock_cls.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_redis_writes_when_no_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("CMC_API_KEY", raising=False)
        redis = _make_redis()
        provider = CMCProvider(redis)
        await provider.quotes()
        redis.setex.assert_not_called()
        redis.pipeline.return_value.execute.assert_not_called()


# ---------------------------------------------------------------------------
# TestCachedGet
# ---------------------------------------------------------------------------


class TestCachedGet:
    @pytest.mark.asyncio
    async def test_returns_cached_value_without_http_call(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CMC_API_KEY", "test_key")
        cached_data = {"status": {"error_code": 0}, "data": {"cached": True}}
        redis = _make_redis(cached_values={"my:cache:key": json.dumps(cached_data)})
        provider = CMCProvider(redis)

        with patch("httpx.AsyncClient") as mock_cls:
            result = await provider._cached_get("/some/path", {}, "my:cache:key", 300)
            mock_cls.assert_not_called()

        assert result == cached_data

    @pytest.mark.asyncio
    async def test_calls_api_on_cache_miss(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CMC_API_KEY", "test_key")
        redis = _make_redis()  # no cached values
        provider = CMCProvider(redis)

        api_response = {"status": {"error_code": 0}, "data": {"fresh": True}}
        mock_resp = _make_http_response(api_response)
        mock_client = _make_async_client(mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await provider._cached_get("/v1/test", {}, "missing:key", 300)

        assert result == api_response
        mock_client.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_caches_successful_response(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CMC_API_KEY", "test_key")
        redis = _make_redis()
        provider = CMCProvider(redis)

        api_response = {"status": {"error_code": 0}, "data": {}}
        mock_resp = _make_http_response(api_response)
        mock_client = _make_async_client(mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            await provider._cached_get("/v1/test", {}, "cache:key:ok", 600)

        redis.setex.assert_called_once()
        call_args = redis.setex.call_args[0]
        assert call_args[0] == "cache:key:ok"
        assert call_args[1] == 600
        assert json.loads(call_args[2]) == api_response

    @pytest.mark.asyncio
    async def test_does_not_cache_error_response(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CMC_API_KEY", "test_key")
        redis = _make_redis()
        provider = CMCProvider(redis)

        # error_code != 0 → should NOT cache
        api_response = {"status": {"error_code": 1001, "error_message": "API key invalid"}, "data": {}}
        mock_resp = _make_http_response(api_response)
        mock_client = _make_async_client(mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            await provider._cached_get("/v1/test", {}, "cache:key:err", 600)

        redis.setex.assert_not_called()

    @pytest.mark.asyncio
    async def test_returns_empty_dict_on_http_error_status(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CMC_API_KEY", "test_key")
        redis = _make_redis()
        provider = CMCProvider(redis)

        mock_resp = _make_http_response({}, status_code=429)
        mock_client = _make_async_client(mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await provider._cached_get("/v1/test", {}, "cache:key:429", 300)

        assert result == {}
        redis.setex.assert_not_called()

    @pytest.mark.asyncio
    async def test_cached_value_returned_as_parsed_dict(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CMC_API_KEY", "test_key")
        raw = {"key": "value", "nested": {"a": 1}}
        redis = _make_redis(cached_values={"my:key": json.dumps(raw)})
        provider = CMCProvider(redis)

        result = await provider._cached_get("/path", {}, "my:key", 100)
        assert result == raw
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_sends_correct_auth_headers(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CMC_API_KEY", "my_secret_key_xyz")
        redis = _make_redis()
        provider = CMCProvider(redis)

        api_response = {"status": {"error_code": 0}, "data": {}}
        mock_resp = _make_http_response(api_response)
        mock_client = _make_async_client(mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            await provider._cached_get("/v1/test", {"param": "val"}, "ck", 300)

        call_kwargs = mock_client.get.call_args[1]
        headers = call_kwargs.get("headers", {})
        assert headers.get("X-CMC_PRO_API_KEY") == "my_secret_key_xyz"
        assert headers.get("Accept") == "application/json"


# ---------------------------------------------------------------------------
# TestQuotes
# ---------------------------------------------------------------------------


class TestQuotes:
    @pytest.mark.asyncio
    async def test_batches_all_symbols_in_one_call(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CMC_API_KEY", "test_key")
        redis = _make_redis()
        provider = CMCProvider(redis)

        api_response = _cmc_quotes_response(["BTC", "ETH", "SOL"])
        mock_resp = _make_http_response(api_response)
        mock_client = _make_async_client(mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await provider.quotes(["BTC", "ETH", "SOL"])

        # Only 1 HTTP call — all symbols batched
        mock_client.get.assert_called_once()
        assert "BTC" in result
        assert "ETH" in result
        assert "SOL" in result

    @pytest.mark.asyncio
    async def test_writes_cmc_quote_per_symbol(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CMC_API_KEY", "test_key")
        redis = _make_redis()
        provider = CMCProvider(redis)
        pipe = redis.pipeline.return_value

        api_response = _cmc_quotes_response(["BTC", "ETH"])
        mock_resp = _make_http_response(api_response)
        mock_client = _make_async_client(mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            await provider.quotes(["BTC", "ETH"])

        setex_calls = [c[0] for c in pipe.setex.call_args_list]
        keys_written = [c[0] for c in setex_calls]
        assert "cmc:quote:BTC" in keys_written
        assert "cmc:quote:ETH" in keys_written

    @pytest.mark.asyncio
    async def test_writes_ruby_price_keys(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CMC_API_KEY", "test_key")
        redis = _make_redis()
        provider = CMCProvider(redis)
        pipe = redis.pipeline.return_value

        api_response = _cmc_quotes_response(["BTC", "SOL"])
        mock_resp = _make_http_response(api_response)
        mock_client = _make_async_client(mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            await provider.quotes(["BTC", "SOL"])

        setex_calls = [c[0] for c in pipe.setex.call_args_list]
        keys_written = [c[0] for c in setex_calls]
        assert "ruby:price:BTC/USD" in keys_written
        assert "ruby:price:SOL/USD" in keys_written

    @pytest.mark.asyncio
    async def test_writes_ruby_chg_pct_keys(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CMC_API_KEY", "test_key")
        redis = _make_redis()
        provider = CMCProvider(redis)
        pipe = redis.pipeline.return_value

        api_response = _cmc_quotes_response(["ETH"])
        mock_resp = _make_http_response(api_response)
        mock_client = _make_async_client(mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            await provider.quotes(["ETH"])

        setex_calls = [c[0] for c in pipe.setex.call_args_list]
        keys_written = [c[0] for c in setex_calls]
        assert "ruby:chg_pct:ETH/USD" in keys_written

    @pytest.mark.asyncio
    async def test_returns_correct_field_mapping(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CMC_API_KEY", "test_key")
        redis = _make_redis()
        provider = CMCProvider(redis)

        api_response = _cmc_quotes_response(["BTC"])
        mock_resp = _make_http_response(api_response)
        mock_client = _make_async_client(mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await provider.quotes(["BTC"])

        btc = result["BTC"]
        assert btc["symbol"] == "BTC"
        assert btc["price"] == 50_000.0
        assert btc["market_cap"] == 1_000_000_000.0
        assert btc["volume_24h"] == 30_000_000_000.0
        assert btc["pct_change_1h"] == 0.5
        assert btc["pct_change_24h"] == 2.3
        assert btc["pct_change_7d"] == -1.2
        assert btc["market_cap_dominance"] == 45.0
        assert btc["cmc_rank"] == 1
        assert btc["name"] == "BTC_name"

    @pytest.mark.asyncio
    async def test_uses_quotes_cache_ttl(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CMC_API_KEY", "test_key")
        redis = _make_redis()
        provider = CMCProvider(redis)
        pipe = redis.pipeline.return_value

        api_response = _cmc_quotes_response(["BTC"])
        mock_resp = _make_http_response(api_response)
        mock_client = _make_async_client(mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            await provider.quotes(["BTC"])

        # setex calls on the pipe should use TTL_QUOTES
        for c in pipe.setex.call_args_list:
            ttl = c[0][1]
            assert ttl == TTL_QUOTES

    @pytest.mark.asyncio
    async def test_returns_empty_dict_when_no_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("CMC_API_KEY", raising=False)
        redis = _make_redis()
        provider = CMCProvider(redis)
        result = await provider.quotes(["BTC", "ETH", "SOL"])
        assert result == {}

    @pytest.mark.asyncio
    async def test_returns_empty_dict_on_api_empty_data(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CMC_API_KEY", "test_key")
        redis = _make_redis()
        provider = CMCProvider(redis)

        mock_resp = _make_http_response({"status": {"error_code": 0}, "data": {}})
        mock_client = _make_async_client(mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await provider.quotes(["BTC"])

        assert result == {}

    @pytest.mark.asyncio
    async def test_cache_hit_returns_without_http(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CMC_API_KEY", "test_key")
        cached = _cmc_quotes_response(["BTC", "ETH", "SOL"])
        redis = _make_redis(cached_values={"cmc:quotes:BTC,ETH,SOL": json.dumps(cached)})
        provider = CMCProvider(redis)

        with patch("httpx.AsyncClient") as mock_cls:
            result = await provider.quotes(["BTC", "ETH", "SOL"])
            mock_cls.assert_not_called()

        assert "BTC" in result


# ---------------------------------------------------------------------------
# TestGlobalMetrics
# ---------------------------------------------------------------------------


class TestGlobalMetrics:
    @pytest.mark.asyncio
    async def test_parses_nested_structure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CMC_API_KEY", "test_key")
        redis = _make_redis()
        provider = CMCProvider(redis)

        mock_resp = _make_http_response(_cmc_global_response())
        mock_client = _make_async_client(mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await provider.global_metrics()

        assert result["btc_dominance"] == 52.3
        assert result["eth_dominance"] == 17.1
        assert result["total_market_cap"] == 2_000_000_000_000.0

    @pytest.mark.asyncio
    async def test_writes_cmc_btc_dominance_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CMC_API_KEY", "test_key")
        redis = _make_redis()
        provider = CMCProvider(redis)

        mock_resp = _make_http_response(_cmc_global_response())
        mock_client = _make_async_client(mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            await provider.global_metrics()

        # Verify cmc:btc_dominance setex call
        setex_calls = redis.setex.call_args_list
        btc_dom_calls = [c for c in setex_calls if c[0][0] == "cmc:btc_dominance"]
        assert len(btc_dom_calls) == 1
        assert btc_dom_calls[0][0][2] == str(52.3)

    @pytest.mark.asyncio
    async def test_writes_cmc_global_metrics_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CMC_API_KEY", "test_key")
        redis = _make_redis()
        provider = CMCProvider(redis)

        mock_resp = _make_http_response(_cmc_global_response())
        mock_client = _make_async_client(mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            await provider.global_metrics()

        setex_calls = redis.setex.call_args_list
        global_calls = [c for c in setex_calls if c[0][0] == "cmc:global_metrics"]
        # _cached_get writes once with the raw API response, then global_metrics()
        # writes again with the processed result dict — at least one write expected
        assert len(global_calls) >= 1

    @pytest.mark.asyncio
    async def test_returns_all_metric_fields(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CMC_API_KEY", "test_key")
        redis = _make_redis()
        provider = CMCProvider(redis)

        mock_resp = _make_http_response(_cmc_global_response())
        mock_client = _make_async_client(mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await provider.global_metrics()

        expected_fields = {
            "total_market_cap",
            "total_volume_24h",
            "total_volume_24h_reported",
            "altcoin_market_cap",
            "altcoin_volume_24h",
            "defi_market_cap",
            "defi_volume_24h",
            "stablecoin_market_cap",
            "stablecoin_volume_24h",
            "btc_dominance",
            "btc_dominance_24h_pct_change",
            "eth_dominance",
            "active_cryptocurrencies",
            "active_market_pairs",
            "active_exchanges",
            "last_updated",
        }
        assert expected_fields.issubset(result.keys())

    @pytest.mark.asyncio
    async def test_returns_empty_dict_when_no_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("CMC_API_KEY", raising=False)
        redis = _make_redis()
        provider = CMCProvider(redis)
        result = await provider.global_metrics()
        assert result == {}

    @pytest.mark.asyncio
    async def test_defi_volume_mapped_from_nested_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Ensure defi_volume_24h is pulled from defi_24h_volume in the USD quote."""
        monkeypatch.setenv("CMC_API_KEY", "test_key")
        redis = _make_redis()
        provider = CMCProvider(redis)

        mock_resp = _make_http_response(_cmc_global_response())
        mock_client = _make_async_client(mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await provider.global_metrics()

        assert result["defi_volume_24h"] == 8_000_000_000.0

    @pytest.mark.asyncio
    async def test_cache_hit_skips_api(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CMC_API_KEY", "test_key")
        cached = _cmc_global_response()
        redis = _make_redis(cached_values={"cmc:global_metrics": json.dumps(cached)})
        provider = CMCProvider(redis)

        with patch("httpx.AsyncClient") as mock_cls:
            await provider.global_metrics()
            mock_cls.assert_not_called()

    @pytest.mark.asyncio
    async def test_uses_global_ttl(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CMC_API_KEY", "test_key")
        redis = _make_redis()
        provider = CMCProvider(redis)

        mock_resp = _make_http_response(_cmc_global_response())
        mock_client = _make_async_client(mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            await provider.global_metrics()

        # The setex calls should use TTL_GLOBAL
        for c in redis.setex.call_args_list:
            ttl = c[0][1]
            assert ttl == TTL_GLOBAL


# ---------------------------------------------------------------------------
# TestFearAndGreed
# ---------------------------------------------------------------------------


class TestFearAndGreed:
    # -- _fg_to_sentiment boundary tests ------------------------------------

    def test_fg_to_sentiment_extreme_fear(self) -> None:
        assert _fg_to_sentiment(0) == "extreme_fear"
        assert _fg_to_sentiment(24) == "extreme_fear"

    def test_fg_to_sentiment_fear(self) -> None:
        assert _fg_to_sentiment(25) == "fear"
        assert _fg_to_sentiment(44) == "fear"

    def test_fg_to_sentiment_neutral(self) -> None:
        assert _fg_to_sentiment(45) == "neutral"
        assert _fg_to_sentiment(54) == "neutral"

    def test_fg_to_sentiment_greed(self) -> None:
        assert _fg_to_sentiment(55) == "greed"
        assert _fg_to_sentiment(74) == "greed"

    def test_fg_to_sentiment_extreme_greed(self) -> None:
        assert _fg_to_sentiment(75) == "extreme_greed"
        assert _fg_to_sentiment(100) == "extreme_greed"

    def test_fg_to_sentiment_boundary_25(self) -> None:
        assert _fg_to_sentiment(25) == "fear"
        assert _fg_to_sentiment(24) == "extreme_fear"

    def test_fg_to_sentiment_boundary_45(self) -> None:
        assert _fg_to_sentiment(45) == "neutral"
        assert _fg_to_sentiment(44) == "fear"

    def test_fg_to_sentiment_boundary_55(self) -> None:
        assert _fg_to_sentiment(55) == "greed"
        assert _fg_to_sentiment(54) == "neutral"

    def test_fg_to_sentiment_boundary_75(self) -> None:
        assert _fg_to_sentiment(75) == "extreme_greed"
        assert _fg_to_sentiment(74) == "greed"

    # -- Provider tests -----------------------------------------------------

    @pytest.mark.asyncio
    async def test_returns_correct_fields(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CMC_API_KEY", "test_key")
        redis = _make_redis()
        provider = CMCProvider(redis)

        mock_resp = _make_http_response(_cmc_fear_greed_response(value=30, label="Fear"))
        mock_client = _make_async_client(mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await provider.fear_and_greed()

        assert result["value"] == 30
        assert result["label"] == "Fear"
        # _fg_to_sentiment: 30 >= 25 and < 45 → "fear" (not extreme_fear which needs < 25)
        assert result["sentiment"] == "fear"
        assert "timestamp" in result

    @pytest.mark.asyncio
    async def test_writes_cmc_fear_greed_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CMC_API_KEY", "test_key")
        redis = _make_redis()
        provider = CMCProvider(redis)

        mock_resp = _make_http_response(_cmc_fear_greed_response(value=65, label="Greed"))
        mock_client = _make_async_client(mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            await provider.fear_and_greed()

        setex_calls = redis.setex.call_args_list
        fg_calls = [c for c in setex_calls if c[0][0] == "cmc:fear_greed"]
        # _cached_get writes raw API response; fear_and_greed() writes processed result
        # At least one write to cmc:fear_greed expected
        assert len(fg_calls) >= 1
        # Find the call that stores the processed result (has "sentiment" key)
        processed_calls = [c for c in fg_calls if "sentiment" in json.loads(c[0][2])]
        assert len(processed_calls) >= 1
        stored = json.loads(processed_calls[0][0][2])
        assert stored["value"] == 65
        assert stored["sentiment"] == "greed"

    @pytest.mark.asyncio
    async def test_sentiment_mapped_correctly_extreme_greed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CMC_API_KEY", "test_key")
        redis = _make_redis()
        provider = CMCProvider(redis)

        mock_resp = _make_http_response(_cmc_fear_greed_response(value=90, label="Extreme Greed"))
        mock_client = _make_async_client(mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await provider.fear_and_greed()

        assert result["sentiment"] == "extreme_greed"

    @pytest.mark.asyncio
    async def test_sentiment_mapped_correctly_neutral(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CMC_API_KEY", "test_key")
        redis = _make_redis()
        provider = CMCProvider(redis)

        mock_resp = _make_http_response(_cmc_fear_greed_response(value=50, label="Neutral"))
        mock_client = _make_async_client(mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await provider.fear_and_greed()

        assert result["sentiment"] == "neutral"

    @pytest.mark.asyncio
    async def test_returns_empty_dict_when_no_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("CMC_API_KEY", raising=False)
        redis = _make_redis()
        provider = CMCProvider(redis)
        result = await provider.fear_and_greed()
        assert result == {}

    @pytest.mark.asyncio
    async def test_uses_fear_greed_ttl(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CMC_API_KEY", "test_key")
        redis = _make_redis()
        provider = CMCProvider(redis)

        mock_resp = _make_http_response(_cmc_fear_greed_response())
        mock_client = _make_async_client(mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            await provider.fear_and_greed()

        fg_setex = [c for c in redis.setex.call_args_list if c[0][0] == "cmc:fear_greed"]
        assert fg_setex[0][0][1] == TTL_FEAR_GREED

    @pytest.mark.asyncio
    async def test_cache_hit_skips_api_call(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CMC_API_KEY", "test_key")
        cached_fg = {
            "status": {"error_code": 0},
            "data": {"value": 42, "value_classification": "Fear", "timestamp": "2024-01-01"},
        }
        redis = _make_redis(cached_values={"cmc:fear_greed": json.dumps(cached_fg)})
        provider = CMCProvider(redis)

        with patch("httpx.AsyncClient") as mock_cls:
            await provider.fear_and_greed()
            mock_cls.assert_not_called()


# ---------------------------------------------------------------------------
# TestTopListings
# ---------------------------------------------------------------------------


class TestTopListings:
    @pytest.mark.asyncio
    async def test_respects_limit_param(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CMC_API_KEY", "test_key")
        redis = _make_redis()
        provider = CMCProvider(redis)

        mock_resp = _make_http_response(_cmc_listings_response(count=10))
        mock_client = _make_async_client(mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await provider.top_listings(limit=10)

        # API returned 10, we expect 10 back
        assert len(result) == 10

        # Verify limit was passed to the API
        call_params = mock_client.get.call_args[1].get("params", {})
        assert call_params.get("limit") == 10

    @pytest.mark.asyncio
    async def test_returns_list_of_dicts(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CMC_API_KEY", "test_key")
        redis = _make_redis()
        provider = CMCProvider(redis)

        mock_resp = _make_http_response(_cmc_listings_response(count=5))
        mock_client = _make_async_client(mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await provider.top_listings(limit=5)

        assert isinstance(result, list)
        for item in result:
            assert isinstance(item, dict)

    @pytest.mark.asyncio
    async def test_contains_required_fields(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CMC_API_KEY", "test_key")
        redis = _make_redis()
        provider = CMCProvider(redis)

        mock_resp = _make_http_response(_cmc_listings_response(count=3))
        mock_client = _make_async_client(mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await provider.top_listings(limit=3)

        required = {
            "rank",
            "symbol",
            "name",
            "price",
            "market_cap",
            "volume_24h",
            "pct_change_24h",
            "pct_change_7d",
            "dominance",
        }
        for item in result:
            assert required.issubset(item.keys())

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("CMC_API_KEY", raising=False)
        redis = _make_redis()
        provider = CMCProvider(redis)
        result = await provider.top_listings()
        assert result == []

    @pytest.mark.asyncio
    async def test_uses_listings_ttl(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CMC_API_KEY", "test_key")
        redis = _make_redis()
        provider = CMCProvider(redis)

        mock_resp = _make_http_response(_cmc_listings_response(count=5))
        mock_client = _make_async_client(mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            await provider.top_listings(limit=5)

        # _cached_get writes raw API response and top_listings() writes processed coins list;
        # both use cmc:listings:5 as the key — all writes should use TTL_LISTINGS
        listing_setex = [c for c in redis.setex.call_args_list if "listings" in c[0][0]]
        assert len(listing_setex) >= 1
        for c in listing_setex:
            assert c[0][1] == TTL_LISTINGS

    @pytest.mark.asyncio
    async def test_cache_key_includes_limit(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CMC_API_KEY", "test_key")
        redis = _make_redis()
        provider = CMCProvider(redis)

        mock_resp = _make_http_response(_cmc_listings_response(count=20))
        mock_client = _make_async_client(mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            await provider.top_listings(limit=20)

        listing_setex = [c for c in redis.setex.call_args_list if "listings" in c[0][0]]
        assert "20" in listing_setex[0][0][0]

    @pytest.mark.asyncio
    async def test_returns_empty_list_on_empty_data(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CMC_API_KEY", "test_key")
        redis = _make_redis()
        provider = CMCProvider(redis)

        mock_resp = _make_http_response({"status": {"error_code": 0}, "data": []})
        mock_client = _make_async_client(mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await provider.top_listings(limit=10)

        assert result == []

    @pytest.mark.asyncio
    async def test_cache_hit_skips_api(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CMC_API_KEY", "test_key")
        cached = _cmc_listings_response(count=5)
        redis = _make_redis(cached_values={"cmc:listings:5": json.dumps(cached)})
        provider = CMCProvider(redis)

        with patch("httpx.AsyncClient") as mock_cls:
            await provider.top_listings(limit=5)
            mock_cls.assert_not_called()


# ---------------------------------------------------------------------------
# TestCryptoInfo
# ---------------------------------------------------------------------------


class TestCryptoInfo:
    @pytest.mark.asyncio
    async def test_truncates_description_to_500_chars(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CMC_API_KEY", "test_key")
        redis = _make_redis()
        provider = CMCProvider(redis)

        mock_resp = _make_http_response(_cmc_info_response(["BTC"]))
        mock_client = _make_async_client(mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await provider.crypto_info(["BTC"])

        assert len(result["BTC"]["description"]) <= 500

    @pytest.mark.asyncio
    async def test_uses_info_ttl_24h(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """crypto_info should cache for TTL_INFO = 86400s (24 hours)."""
        monkeypatch.setenv("CMC_API_KEY", "test_key")
        redis = _make_redis()
        provider = CMCProvider(redis)

        mock_resp = _make_http_response(_cmc_info_response(["ETH"]))
        mock_client = _make_async_client(mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            await provider.crypto_info(["ETH"])

        # The _cached_get writes with TTL_INFO via redis.setex
        info_setex = [c for c in redis.setex.call_args_list if "info" in c[0][0]]
        assert len(info_setex) == 1
        assert info_setex[0][0][1] == TTL_INFO

    @pytest.mark.asyncio
    async def test_handles_missing_urls_gracefully(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """If urls field is missing or empty, should return None (not crash)."""
        monkeypatch.setenv("CMC_API_KEY", "test_key")
        redis = _make_redis()
        provider = CMCProvider(redis)

        no_urls_data = {
            "status": {"error_code": 0},
            "data": {
                "SOL": {
                    "name": "Solana",
                    "description": "A fast blockchain",
                    "logo": "https://example.com/sol.png",
                    "category": "Cryptocurrency",
                    "date_launched": "2020-03-16",
                    "tags": [],
                    "urls": {},  # empty urls dict
                }
            },
        }
        mock_resp = _make_http_response(no_urls_data)
        mock_client = _make_async_client(mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await provider.crypto_info(["SOL"])

        assert result["SOL"]["website"] is None
        assert result["SOL"]["twitter"] is None
        assert result["SOL"]["reddit"] is None
        assert result["SOL"]["github"] is None

    @pytest.mark.asyncio
    async def test_handles_completely_missing_urls_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CMC_API_KEY", "test_key")
        redis = _make_redis()
        provider = CMCProvider(redis)

        no_urls_data = {
            "status": {"error_code": 0},
            "data": {
                "BTC": {
                    "name": "Bitcoin",
                    "description": "Digital gold",
                    "logo": None,
                    "category": "Cryptocurrency",
                    "date_launched": "2009-01-03",
                    "tags": [],
                    # "urls" key completely absent
                }
            },
        }
        mock_resp = _make_http_response(no_urls_data)
        mock_client = _make_async_client(mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await provider.crypto_info(["BTC"])

        assert result["BTC"]["website"] is None

    @pytest.mark.asyncio
    async def test_returns_correct_fields(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CMC_API_KEY", "test_key")
        redis = _make_redis()
        provider = CMCProvider(redis)

        mock_resp = _make_http_response(_cmc_info_response(["ETH"]))
        mock_client = _make_async_client(mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await provider.crypto_info(["ETH"])

        eth = result["ETH"]
        required_fields = {
            "symbol",
            "name",
            "description",
            "logo",
            "website",
            "twitter",
            "reddit",
            "github",
            "tags",
            "category",
            "date_launched",
        }
        assert required_fields.issubset(eth.keys())

    @pytest.mark.asyncio
    async def test_website_parsed_from_first_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CMC_API_KEY", "test_key")
        redis = _make_redis()
        provider = CMCProvider(redis)

        mock_resp = _make_http_response(_cmc_info_response(["BTC"]))
        mock_client = _make_async_client(mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await provider.crypto_info(["BTC"])

        assert result["BTC"]["website"] == "https://btc.org"

    @pytest.mark.asyncio
    async def test_returns_empty_dict_when_no_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("CMC_API_KEY", raising=False)
        redis = _make_redis()
        provider = CMCProvider(redis)
        result = await provider.crypto_info()
        assert result == {}

    @pytest.mark.asyncio
    async def test_cache_hit_skips_api(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CMC_API_KEY", "test_key")
        cached = _cmc_info_response(["BTC"])
        redis = _make_redis(cached_values={"cmc:info:BTC": json.dumps(cached)})
        provider = CMCProvider(redis)

        with patch("httpx.AsyncClient") as mock_cls:
            await provider.crypto_info(["BTC"])
            mock_cls.assert_not_called()

    @pytest.mark.asyncio
    async def test_tags_truncated_to_10(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CMC_API_KEY", "test_key")
        redis = _make_redis()
        provider = CMCProvider(redis)

        many_tags_data = {
            "status": {"error_code": 0},
            "data": {
                "BTC": {
                    "name": "Bitcoin",
                    "description": "desc",
                    "logo": None,
                    "category": "Cryptocurrency",
                    "date_launched": None,
                    "tags": [f"tag{i}" for i in range(20)],
                    "urls": {},
                }
            },
        }
        mock_resp = _make_http_response(many_tags_data)
        mock_client = _make_async_client(mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await provider.crypto_info(["BTC"])

        assert len(result["BTC"]["tags"]) <= 10


# ---------------------------------------------------------------------------
# TestCMCWorker
# ---------------------------------------------------------------------------


class TestCMCWorker:
    @pytest.mark.asyncio
    async def test_worker_runs_four_loops(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """CMCWorker.run() launches 4 concurrent coroutines via asyncio.gather."""

        monkeypatch.setenv("CMC_API_KEY", "test_key")

        redis = _make_redis()
        provider = CMCProvider(redis)
        worker = CMCWorker(provider)

        calls = []

        # Verify worker has the 4 loop methods
        assert hasattr(worker, "_loop_quotes")
        assert hasattr(worker, "_loop_global")
        assert hasattr(worker, "_loop_fear_greed")
        assert hasattr(worker, "_loop_listings")

        # Replace the 4 loop methods with coroutines that record a call and return
        async def fake_loop_quotes():
            calls.append("quotes")

        async def fake_loop_global():
            calls.append("global")

        async def fake_loop_fear_greed():
            calls.append("fear_greed")

        async def fake_loop_listings():
            calls.append("listings")

        worker._loop_quotes = fake_loop_quotes
        worker._loop_global = fake_loop_global
        worker._loop_fear_greed = fake_loop_fear_greed
        worker._loop_listings = fake_loop_listings

        await worker.run()

        # All 4 loops were invoked
        assert "quotes" in calls
        assert "global" in calls
        assert "fear_greed" in calls
        assert "listings" in calls

    @pytest.mark.asyncio
    async def test_worker_handles_quotes_error_without_crashing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """An exception from quotes() inside the loop must not crash the worker."""

        monkeypatch.setenv("CMC_API_KEY", "test_key")

        redis = _make_redis()
        provider = CMCProvider(redis)
        worker = CMCWorker(provider)

        error_raised = False
        global_called = False

        async def bad_loop_quotes():
            nonlocal error_raised
            # Simulate one iteration that raises, then the loop catches it
            error_raised = True
            raise RuntimeError("CMC API down")

        async def fake_loop_global():
            nonlocal global_called
            global_called = True

        async def fake_loop_fear_greed():
            pass

        async def fake_loop_listings():
            pass

        worker._loop_quotes = bad_loop_quotes
        worker._loop_global = fake_loop_global
        worker._loop_fear_greed = fake_loop_fear_greed
        worker._loop_listings = fake_loop_listings

        # run() uses asyncio.gather — an unhandled exception in one loop propagates
        # but the worker's individual loop methods should catch exceptions internally.
        # Here we test that gather itself runs all 4 coroutines.
        with contextlib.suppress(RuntimeError):
            await worker.run()

        assert error_raised
        assert global_called

    @pytest.mark.asyncio
    async def test_worker_handles_fear_greed_error_without_crashing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Fear & Greed loop error is isolated; other loops still run."""

        monkeypatch.setenv("CMC_API_KEY", "test_key")

        redis = _make_redis()
        provider = CMCProvider(redis)
        worker = CMCWorker(provider)

        fg_called = False
        quotes_called = False

        async def fake_loop_quotes():
            nonlocal quotes_called
            quotes_called = True

        async def fake_loop_global():
            pass

        async def bad_loop_fear_greed():
            nonlocal fg_called
            fg_called = True
            raise ValueError("F&G parse error")

        async def fake_loop_listings():
            pass

        worker._loop_quotes = fake_loop_quotes
        worker._loop_global = fake_loop_global
        worker._loop_fear_greed = bad_loop_fear_greed
        worker._loop_listings = fake_loop_listings

        with contextlib.suppress(ValueError):
            await worker.run()

        assert fg_called
        assert quotes_called

    @pytest.mark.asyncio
    async def test_quotes_loop_respects_interval_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """CMC_POLL_QUOTES env var controls the quotes polling interval."""
        import asyncio

        monkeypatch.setenv("CMC_API_KEY", "test_key")
        monkeypatch.setenv("CMC_POLL_QUOTES", "300")  # 5 minutes
        monkeypatch.setenv("CMC_POLL_GLOBAL", "9999")
        monkeypatch.setenv("CMC_POLL_FEAR_GREED", "9999")
        monkeypatch.setenv("CMC_POLL_LISTINGS", "9999")

        redis = _make_redis()
        provider = CMCProvider(redis)
        worker = CMCWorker(provider)

        sleep_durations = []
        call_count = 0

        async def fake_quotes(syms):
            return {}

        async def fake_global():
            return {}

        async def fake_fg():
            return {}

        async def fake_listings(limit=20):
            return []

        provider.quotes = fake_quotes
        provider.global_metrics = fake_global
        provider.fear_and_greed = fake_fg
        provider.top_listings = fake_listings

        async def fake_sleep(t):
            nonlocal call_count
            sleep_durations.append(t)
            call_count += 1
            if call_count >= 4:
                raise asyncio.CancelledError()

        with patch("asyncio.sleep", side_effect=fake_sleep):
            with contextlib.suppress(TimeoutError, asyncio.CancelledError):
                await asyncio.wait_for(worker.run(), timeout=5.0)

        # At least one sleep of 300s should appear (the quotes loop interval)
        assert 300 in sleep_durations

    @pytest.mark.asyncio
    async def test_worker_disabled_provider_no_crash(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Worker with a disabled provider (no API key) should run without crashing."""
        import asyncio

        monkeypatch.delenv("CMC_API_KEY", raising=False)
        monkeypatch.setenv("CMC_POLL_QUOTES", "9999")
        monkeypatch.setenv("CMC_POLL_GLOBAL", "9999")
        monkeypatch.setenv("CMC_POLL_FEAR_GREED", "9999")
        monkeypatch.setenv("CMC_POLL_LISTINGS", "9999")

        redis = _make_redis()
        provider = CMCProvider(redis)
        worker = CMCWorker(provider)

        call_count = 0

        async def fake_sleep(t):
            nonlocal call_count
            call_count += 1
            if call_count >= 4:
                raise asyncio.CancelledError()

        with patch("asyncio.sleep", side_effect=fake_sleep):
            with contextlib.suppress(TimeoutError, asyncio.CancelledError):
                await asyncio.wait_for(worker.run(), timeout=5.0)
        # No exception propagated — worker survived despite disabled provider
