"""Tests for RUSTCODE-CHAT-G intent detection."""

import asyncio

from lib.services.data.api.chat import _INTENT_PATTERNS, _detect_intents


class TestDetectIntents:
    def _run(self, coro):
        return asyncio.run(coro)

    def test_empty_message_no_intents(self):
        assert self._run(_detect_intents("")) == []

    def test_signal_intent_detected(self):
        assert "signals" in self._run(_detect_intents("show me the latest signals"))

    def test_positions_intent_detected(self):
        assert "positions" in self._run(_detect_intents("what are my open positions?"))

    def test_journal_intent_detected(self):
        assert "journal" in self._run(_detect_intents("how did my trades do this week"))

    def test_net_worth_intent_detected(self):
        assert "net_worth" in self._run(_detect_intents("what is my net worth today"))

    def test_market_context_intent_detected(self):
        assert "market_context" in self._run(_detect_intents("what is the market regime?"))

    def test_dom_intent_detected(self):
        assert "dom" in self._run(_detect_intents("show me the order book"))

    def test_multiple_intents(self):
        result = self._run(_detect_intents("show me signals and my positions"))
        assert "signals" in result
        assert "positions" in result

    def test_case_insensitive(self):
        assert "signals" in self._run(_detect_intents("SHOW ME SIGNALS"))

    def test_no_match_returns_empty(self):
        result = self._run(_detect_intents("hello how are you"))
        assert result == []

    def test_symbol_in_message(self):
        result = self._run(_detect_intents("show me MES signals"))
        assert "signals" in result

    def test_intent_patterns_not_empty(self):
        assert len(_INTENT_PATTERNS) > 0
        for intent, keywords in _INTENT_PATTERNS.items():
            assert len(keywords) > 0, f"Intent {intent} has no keywords"
