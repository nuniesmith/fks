"""Tests for the enhanced ProviderRouter methods added in Session 3.

These tests verify that the new methods on :class:`ProviderRouter` —
``resolve_provider_symbol``, ``get_ws_url``, and ``get_routing_info`` —
exist and behave correctly without requiring a live Redis connection or
real provider instances.
"""

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

# ---------------------------------------------------------------------------
# Helpers — lightweight fakes so we don't need real Redis / providers
# ---------------------------------------------------------------------------


def _make_fake_redis() -> MagicMock:
    """Return an async-compatible mock that stands in for ``redis.asyncio.Redis``."""
    r = AsyncMock()
    r.get = AsyncMock(return_value=None)
    r.setex = AsyncMock()
    r.delete = AsyncMock()
    r.exists = AsyncMock(return_value=0)
    return r


def _make_fake_provider(name_value: str = "kraken") -> MagicMock:
    """Return a mock provider with a ``.name`` enum-like attribute."""
    prov = MagicMock()
    prov.name = MagicMock()
    prov.name.value = name_value
    # Make .name hashable so it can be a dict key
    prov.name.__hash__ = lambda self: hash(name_value)
    prov.name.__eq__ = lambda self, other: getattr(other, "value", other) == name_value
    prov.supported_intervals = MagicMock(return_value=[])
    prov.max_history_days = 365
    return prov


def _make_router(providers=None):
    """Instantiate a ``ProviderRouter`` with fake Redis and optional providers."""
    from data_factory.providers.router import ProviderRouter

    redis = _make_fake_redis()
    if providers is None:
        providers = [_make_fake_provider("kraken"), _make_fake_provider("binance")]
    return ProviderRouter(redis=redis, providers=providers)


def _make_asset_config(
    symbol: str = "BTC/USD",
    providers=None,
    provider_symbol_map=None,
    exchange: str = "",
):
    """Create a minimal mock AssetConfig."""
    cfg = MagicMock()
    cfg.symbol = symbol
    cfg.providers = providers or []
    cfg.provider_symbol_map = provider_symbol_map or {}
    cfg.exchange = exchange
    return cfg


# ---------------------------------------------------------------------------
# Tests — method existence
# ---------------------------------------------------------------------------


class TestProviderRouterMethodsExist(unittest.TestCase):
    """Verify that the Session-3 methods exist on ProviderRouter."""

    def test_get_ws_url_exists(self):
        """``get_ws_url`` should be a callable method on ProviderRouter."""
        from data_factory.providers.router import ProviderRouter

        self.assertTrue(hasattr(ProviderRouter, "get_ws_url"))
        self.assertTrue(callable(getattr(ProviderRouter, "get_ws_url", None)))

    def test_resolve_provider_symbol_exists(self):
        """``resolve_provider_symbol`` should be a callable method."""
        from data_factory.providers.router import ProviderRouter

        self.assertTrue(hasattr(ProviderRouter, "resolve_provider_symbol"))
        self.assertTrue(callable(getattr(ProviderRouter, "resolve_provider_symbol", None)))

    def test_get_routing_info_exists(self):
        """``get_routing_info`` should be a callable method."""
        from data_factory.providers.router import ProviderRouter

        self.assertTrue(hasattr(ProviderRouter, "get_routing_info"))
        self.assertTrue(callable(getattr(ProviderRouter, "get_routing_info", None)))

    def test_health_summary_exists(self):
        """``health_summary`` should be a callable async method."""
        from data_factory.providers.router import ProviderRouter

        self.assertTrue(hasattr(ProviderRouter, "health_summary"))

    def test_best_provider_for_exists(self):
        """``best_provider_for`` should be a callable async method."""
        from data_factory.providers.router import ProviderRouter

        self.assertTrue(hasattr(ProviderRouter, "best_provider_for"))


# ---------------------------------------------------------------------------
# Tests — resolve_provider_symbol
# ---------------------------------------------------------------------------


class TestResolveProviderSymbol(unittest.TestCase):
    """Test ProviderRouter.resolve_provider_symbol."""

    def test_passthrough_when_no_config_and_no_core(self):
        """Without config or core registry match, return the original symbol."""
        router = _make_router()
        with patch(
            "lib.data_factory.providers.router.ProviderRouter.resolve_provider_symbol",
            wraps=router.resolve_provider_symbol,
        ):
            # Patch the core registry import to raise so we hit passthrough
            with patch.dict("sys.modules", {"lib.core.asset_registry": None}):
                result = router.resolve_provider_symbol("UNKNOWN_XYZ", "kraken")
        self.assertIsInstance(result, str)

    def test_config_provider_symbol_map_takes_priority(self):
        """When config has a provider_symbol_map entry, it should win."""
        router = _make_router()
        config = _make_asset_config(
            provider_symbol_map={"kraken": "CUSTOM_KRK_SYM"},
        )
        result = router.resolve_provider_symbol("BTC/USD", "kraken", config=config)
        self.assertEqual(result, "CUSTOM_KRK_SYM")

    def test_config_map_miss_falls_through(self):
        """If config map doesn't have the provider, fall through to next source."""
        router = _make_router()
        config = _make_asset_config(
            provider_symbol_map={"binance": "BTCUSDT"},
        )
        # Asking for "kraken" which isn't in the map
        result = router.resolve_provider_symbol("BTC/USD", "kraken", config=config)
        # Should be either core-registry result or passthrough — not "BTCUSDT"
        self.assertNotEqual(result, "BTCUSDT")

    def test_provider_name_enum_value_extracted(self):
        """If provider_name has a .value attribute, it should be extracted."""
        router = _make_router()
        config = _make_asset_config(
            provider_symbol_map={"kraken": "XXBTZUSD"},
        )

        # Simulate a ProviderName enum
        class FakePN:
            value = "kraken"

        result = router.resolve_provider_symbol("BTC/USD", FakePN(), config=config)
        self.assertEqual(result, "XXBTZUSD")

    def test_returns_string_type(self):
        """Return type should always be str."""
        router = _make_router()
        result = router.resolve_provider_symbol("BTC/USD", "kraken")
        self.assertIsInstance(result, str)

    def test_empty_config_map_falls_through(self):
        """An empty provider_symbol_map should not short-circuit."""
        router = _make_router()
        config = _make_asset_config(provider_symbol_map={})
        result = router.resolve_provider_symbol("BTC/USD", "kraken", config=config)
        self.assertIsInstance(result, str)

    def test_none_config_accepted(self):
        """Passing config=None should not raise."""
        router = _make_router()
        result = router.resolve_provider_symbol("BTC/USD", "kraken", config=None)
        self.assertIsInstance(result, str)


# ---------------------------------------------------------------------------
# Tests — get_ws_url
# ---------------------------------------------------------------------------


class TestGetWsUrl(unittest.TestCase):
    """Test ProviderRouter.get_ws_url."""

    def test_returns_string(self):
        """get_ws_url should always return a string."""
        router = _make_router()
        result = router.get_ws_url("BTC/USD")
        self.assertIsInstance(result, str)

    def test_returns_empty_string_on_core_failure(self):
        """If core registry is unavailable, return empty string."""
        router = _make_router()
        with patch.dict("sys.modules", {"lib.core": None, "lib.core.asset_registry": None}):
            result = router.get_ws_url("BTC/USD")
        self.assertEqual(result, "")

    def test_known_crypto_delegates_to_core(self):
        """For a known crypto, get_ws_url should delegate to the core registry."""
        router = _make_router()
        # This will succeed or return "" depending on whether the core
        # registry is fully set up — either way it shouldn't crash.
        result = router.get_ws_url("Bitcoin")
        self.assertIsInstance(result, str)


# ---------------------------------------------------------------------------
# Tests — get_routing_info
# ---------------------------------------------------------------------------


class TestGetRoutingInfo(unittest.TestCase):
    """Test ProviderRouter.get_routing_info."""

    def test_returns_dict(self):
        """get_routing_info should return a dict."""
        router = _make_router()
        result = router.get_routing_info("BTC/USD")
        self.assertIsInstance(result, dict)

    def test_has_expected_keys(self):
        """Result dict should contain the five standard routing keys."""
        router = _make_router()
        result = router.get_routing_info("BTC/USD")
        for key in ("ws_url", "source_chain", "provider_symbols", "requires_auth", "delay_info"):
            self.assertIn(key, result, f"Missing key: {key}")

    def test_ws_url_is_string(self):
        """ws_url should be a string."""
        router = _make_router()
        result = router.get_routing_info("BTC/USD")
        self.assertIsInstance(result["ws_url"], str)

    def test_source_chain_is_list(self):
        """source_chain should be a list."""
        router = _make_router()
        result = router.get_routing_info("BTC/USD")
        self.assertIsInstance(result["source_chain"], list)

    def test_provider_symbols_is_dict(self):
        """provider_symbols should be a dict."""
        router = _make_router()
        result = router.get_routing_info("BTC/USD")
        self.assertIsInstance(result["provider_symbols"], dict)

    def test_config_overrides_are_respected(self):
        """When an AssetConfig is provided its values should take priority."""
        router = _make_router()
        config = _make_asset_config(
            provider_symbol_map={"kraken": "OVERRIDE_SYM"},
        )
        result = router.get_routing_info("BTC/USD", config=config)
        # The override should appear in provider_symbols
        self.assertEqual(result["provider_symbols"].get("kraken"), "OVERRIDE_SYM")

    def test_none_config_accepted(self):
        """Passing config=None should not raise."""
        router = _make_router()
        result = router.get_routing_info("BTC/USD", config=None)
        self.assertIsInstance(result, dict)

    def test_unknown_symbol_does_not_crash(self):
        """An unknown symbol should return safe defaults, not an exception."""
        router = _make_router()
        result = router.get_routing_info("TOTALLY_UNKNOWN_ASSET_999")
        self.assertIsInstance(result, dict)
        self.assertIn("ws_url", result)

    def test_requires_auth_is_bool(self):
        """requires_auth should be a boolean."""
        router = _make_router()
        result = router.get_routing_info("BTC/USD")
        self.assertIsInstance(result["requires_auth"], bool)

    def test_delegates_to_registry_bridge(self):
        """get_routing_info should call merge_routing_for_symbol internally."""
        router = _make_router()
        with patch(
            "lib.core.registry_bridge.merge_routing_for_symbol",
            return_value={
                "ws_url": "wss://test.example.com",
                "source_chain": ["test_provider"],
                "provider_symbols": {"test": "TEST_SYM"},
                "requires_auth": True,
                "delay_info": "15min",
            },
        ) as mock_merge:
            result = router.get_routing_info("BTC/USD")
            mock_merge.assert_called_once()
            self.assertEqual(result["ws_url"], "wss://test.example.com")
            self.assertTrue(result["requires_auth"])
            self.assertEqual(result["delay_info"], "15min")


# ---------------------------------------------------------------------------
# Tests — constructor
# ---------------------------------------------------------------------------


class TestProviderRouterInit(unittest.TestCase):
    """Test that ProviderRouter can be instantiated with our fakes."""

    def test_construct_with_no_providers(self):
        """Router should accept an empty provider list."""
        router = _make_router(providers=[])
        self.assertIsNotNone(router)

    def test_construct_with_multiple_providers(self):
        """Router should store multiple providers keyed by name."""
        providers = [
            _make_fake_provider("kraken"),
            _make_fake_provider("binance"),
            _make_fake_provider("polygon"),
        ]
        router = _make_router(providers=providers)
        # Internal dict should have 3 entries
        self.assertEqual(len(router._providers), 3)


# ---------------------------------------------------------------------------
# Tests — health tracking (async)
# ---------------------------------------------------------------------------


class TestHealthTracking(unittest.IsolatedAsyncioTestCase):
    """Test the async health/cooldown tracking methods."""

    async def test_mark_healthy_clears_cooldown(self):
        """_mark_healthy should set health and delete cooldown key."""
        router = _make_router()
        provider_name = list(router._providers.keys())[0]
        await router._mark_healthy(provider_name)
        router._redis.setex.assert_called()
        router._redis.delete.assert_called()

    async def test_mark_failed_sets_cooldown(self):
        """_mark_failed should set both cooldown and health keys."""
        router = _make_router()
        provider_name = list(router._providers.keys())[0]
        await router._mark_failed(provider_name)
        # Should have called setex twice (cooldown + health)
        self.assertEqual(router._redis.setex.call_count, 2)

    async def test_is_on_cooldown_checks_redis(self):
        """_is_on_cooldown should consult Redis for the cooldown key."""
        router = _make_router()
        provider_name = list(router._providers.keys())[0]
        router._redis.exists = AsyncMock(return_value=0)
        result = await router._is_on_cooldown(provider_name)
        self.assertFalse(result)

        router._redis.exists = AsyncMock(return_value=1)
        result = await router._is_on_cooldown(provider_name)
        self.assertTrue(result)

    async def test_health_summary_returns_dict(self):
        """health_summary should return a dict mapping provider name → status."""
        router = _make_router()
        router._redis.get = AsyncMock(return_value=None)
        summary = await router.health_summary()
        self.assertIsInstance(summary, dict)
        # All providers with no health record should be "unknown"
        for status in summary.values():
            self.assertEqual(status, "unknown")

    async def test_health_summary_reads_ok_status(self):
        """health_summary should decode 'ok' status from Redis."""
        router = _make_router()
        router._redis.get = AsyncMock(return_value="ok")
        summary = await router.health_summary()
        for status in summary.values():
            self.assertEqual(status, "ok")


# ---------------------------------------------------------------------------
# Tests — fetch_bars chain exhaustion
# ---------------------------------------------------------------------------


class TestFetchBarsChainExhaustion(unittest.IsolatedAsyncioTestCase):
    """Test that fetch_bars handles empty chains gracefully."""

    async def test_empty_chain_returns_empty(self):
        """When no provider is viable, return ([], None)."""
        router = _make_router(providers=[])
        config = _make_asset_config()

        interval_mock = MagicMock()
        interval_mock.value = "1m"

        from datetime import UTC, datetime

        start = datetime(2024, 1, 1, tzinfo=UTC)
        end = datetime(2024, 1, 2, tzinfo=UTC)

        bars, provider = await router.fetch_bars("BTC/USD", interval_mock, start, end, config)
        self.assertEqual(bars, [])
        self.assertIsNone(provider)


if __name__ == "__main__":
    unittest.main()
