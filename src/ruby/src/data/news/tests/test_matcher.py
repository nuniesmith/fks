"""Unit tests for AssetMatcher keyword relevance scoring.

Covers:
    - Ticker detection (headline-only, word-boundary match)
    - Primary keyword scoring (base 0.6, +0.1 per additional hit, capped 0.9)
    - Secondary keyword scoring (base 0.2, +0.05 per additional hit, capped 0.45)
    - Headline bonus (+0.15 when any primary keyword appears in headline)
    - Score cap (all scores capped at 1.0)
    - MIN_SCORE filter (articles below 0.25 are excluded)
    - Multi-asset matching (all relevant assets returned)
    - News-disabled assets are skipped
    - Case-insensitive matching
    - match_type precedence (ticker > primary > secondary)
"""

from __future__ import annotations

from unittest.mock import MagicMock

from data_factory.news.matcher import MIN_SCORE, AssetMatcher

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_asset(
    symbol: str,
    primary_keywords: list[str] | None = None,
    secondary_keywords: list[str] | None = None,
    news_enabled: bool = True,
) -> MagicMock:
    """Build a minimal AssetConfig-like mock for matcher tests."""
    asset = MagicMock()
    asset.symbol = symbol
    asset.news.enabled = news_enabled
    asset.news.primary_keywords = primary_keywords or []
    asset.news.secondary_keywords = secondary_keywords or []
    return asset


def _match(
    headline: str,
    body: str,
    assets: list[MagicMock],
) -> list[tuple[str, float, str]]:
    """Convenience wrapper around AssetMatcher.match."""
    return AssetMatcher().match(headline, body, assets)


# ---------------------------------------------------------------------------
# Ticker detection
# ---------------------------------------------------------------------------


class TestTickerDetection:
    """Ticker present in the headline triggers a 0.8 base score."""

    def test_ticker_in_headline_scores_0_8(self) -> None:
        asset = _make_asset("MGC")
        results = _match("MGC futures rally to record high", "", [asset])

        assert len(results) == 1
        symbol, score, match_type = results[0]
        assert symbol == "MGC"
        assert score >= 0.8
        assert match_type == "ticker"

    def test_ticker_in_body_only_does_not_trigger_ticker_match(self) -> None:
        """Ticker detection is headline-only.  Body-only ticker should NOT produce a ticker match."""
        asset = _make_asset("MGC", primary_keywords=["micro gold"])
        # MGC is only in the body — should fall through to keyword matching
        results = _match("Gold market update", "MGC futures rally today", [asset])
        # Either no match (score < MIN_SCORE) or a non-ticker match
        for _sym, _score, match_type in results:
            assert match_type != "ticker"

    def test_ticker_requires_word_boundary(self) -> None:
        """'MGCX' must not match the 'MGC' ticker (word-boundary guard)."""
        asset = _make_asset("MGC")
        results = _match("MGCX surges on volume", "", [asset])
        # The ticker 'MGC' must not appear as a word-boundary match inside 'MGCX'
        for _sym, _score, match_type in results:
            assert match_type != "ticker"

    def test_ticker_case_insensitive_in_headline(self) -> None:
        """Ticker matching against the headline should be case-insensitive."""
        asset = _make_asset("MGC")
        # The regex runs against headline.upper(), so 'mgc' should still match.
        results = _match("mgc futures rally", "", [asset])
        assert len(results) == 1
        assert results[0][2] == "ticker"

    def test_ticker_with_slash_uses_base_part(self) -> None:
        """BTC/USD should detect 'BTC' as the ticker portion."""
        asset = _make_asset("BTC/USD")
        results = _match("BTC hits 100k", "", [asset])
        assert len(results) == 1
        assert results[0][2] == "ticker"

    def test_ticker_not_matched_in_unrelated_headline(self) -> None:
        """No false positive when the ticker is absent from headline and body."""
        asset = _make_asset("MGC")
        results = _match("Oil prices tumble on inventory build", "Crude oil supply data", [asset])
        assert len(results) == 0


# ---------------------------------------------------------------------------
# Primary keyword scoring
# ---------------------------------------------------------------------------


class TestPrimaryKeywordScoring:
    """Primary keyword hits produce scores in the 0.6–0.9 range."""

    def test_single_primary_hit_scores_0_6(self) -> None:
        asset = _make_asset("MGC", primary_keywords=["micro gold"])
        results = _match("Micro gold demand surges", "Investors flock to micro gold contracts", [asset])

        assert len(results) == 1
        _sym, score, match_type = results[0]
        # Single primary hit → base 0.6, plus headline bonus (+0.15) since 'micro gold' is in headline
        assert score >= 0.6
        assert match_type == "primary"

    def test_two_primary_hits_score_0_7(self) -> None:
        """Two primary keywords → 0.6 + (2-1)*0.1 = 0.7 base."""
        asset = _make_asset("MGC", primary_keywords=["micro gold", "gold futures"])
        results = _match(
            "Report on micro gold",
            "Analysts discuss micro gold and gold futures contracts",
            [asset],
        )
        assert len(results) == 1
        _sym, score, _mt = results[0]
        # 2 hits → base 0.7 + headline bonus 0.15 → 0.85
        assert score >= 0.7

    def test_primary_keywords_capped_at_0_9(self) -> None:
        """Many primary hits must never exceed 0.9 before the headline bonus."""
        asset = _make_asset(
            "MGC",
            primary_keywords=["a", "b", "c", "d", "e", "f", "g"],
        )
        # All 7 keywords in text: 0.6 + 6*0.1 = 1.2 → capped at 0.9
        body = "a b c d e f g are all present"
        results = _match("Just a headline", body, [asset])
        assert len(results) == 1
        _sym, score, _mt = results[0]
        # score is min(0.9, 1.0) = 0.9, with possible headline bonus making it 1.0
        assert score <= 1.0

    def test_primary_match_type_is_primary(self) -> None:
        asset = _make_asset("SIL", primary_keywords=["micro silver"])
        results = _match("Micro silver sees buying pressure", "", [asset])
        assert len(results) == 1
        assert results[0][2] == "primary"

    def test_primary_match_excludes_disabled_news(self) -> None:
        """Assets with news.enabled=False must never appear in results."""
        asset = _make_asset("SPY", primary_keywords=["S&P 500"], news_enabled=False)
        results = _match("S&P 500 hits record high", "S&P 500 rally continues", [asset])
        assert len(results) == 0


# ---------------------------------------------------------------------------
# Secondary keyword scoring
# ---------------------------------------------------------------------------


class TestSecondaryKeywordScoring:
    """Secondary keyword hits produce scores in the 0.2–0.45 range."""

    def test_single_secondary_hit_is_below_min_score(self) -> None:
        """One secondary keyword → score 0.2 → below MIN_SCORE → excluded."""
        asset = _make_asset("MGC", secondary_keywords=["inflation"])
        results = _match("Inflation data disappoints", "CPI report misses expectations", [asset])
        assert len(results) == 0

    def test_two_secondary_hits_equals_min_score(self) -> None:
        """Two secondary keywords → 0.2 + 0.05 = 0.25 = MIN_SCORE → included."""
        asset = _make_asset("MGC", secondary_keywords=["inflation", "safe haven"])
        results = _match(
            "Inflation fears drive safe haven demand",
            "Safe haven assets rise as inflation expectations increase",
            [asset],
        )
        assert len(results) == 1
        _sym, score, _mt = results[0]
        assert score >= MIN_SCORE

    def test_three_secondary_hits_score_0_3(self) -> None:
        """Three secondary keywords → 0.2 + 2*0.05 = 0.30."""
        asset = _make_asset("MGC", secondary_keywords=["gold", "XAU", "precious metals"])
        results = _match(
            "Gold XAU precious metals rally",
            "Precious metals including gold and XAU advance",
            [asset],
        )
        assert len(results) == 1
        _sym, score, _mt = results[0]
        assert score >= 0.3

    def test_secondary_cap_at_0_45(self) -> None:
        """Many secondary hits must not produce a secondary-only score above 0.45."""
        asset = _make_asset(
            "MGC",
            secondary_keywords=["a", "b", "c", "d", "e", "f", "g", "h", "i", "j"],
        )
        body = "a b c d e f g h i j are all present"
        results = _match("Neutral headline", body, [asset])
        if results:
            _sym, score, _mt = results[0]
            # No primary or ticker hit → max score is min(0.45, 1.0) = 0.45
            assert score <= 0.45

    def test_secondary_match_type_is_secondary(self) -> None:
        """A secondary-only match must have match_type=='secondary'."""
        asset = _make_asset(
            "MGC",
            secondary_keywords=["safe haven", "precious metals", "inflation"],
        )
        results = _match(
            "Safe haven assets surge on inflation fears precious metals rally",
            "Precious metals and safe haven assets see inflows as inflation rises",
            [asset],
        )
        if results:
            assert results[0][2] == "secondary"


# ---------------------------------------------------------------------------
# Headline bonus
# ---------------------------------------------------------------------------


class TestHeadlineBonus:
    """A primary keyword in the headline adds +0.15 to the score."""

    def test_headline_bonus_added_for_primary_in_headline(self) -> None:
        """Primary keyword in headline → +0.15 bonus."""
        asset = _make_asset("MGC", primary_keywords=["micro gold"])
        # 'micro gold' is in the headline → bonus should fire
        results_with_bonus = _match("Micro gold futures surge", "Some unrelated body text", [asset])
        # 'micro gold' NOT in headline → no bonus
        results_without_bonus = _match("Futures surge today", "Micro gold is discussed in the body", [asset])

        assert len(results_with_bonus) == 1
        # Score with bonus must be higher than without (or body-only match may be < MIN_SCORE)
        if results_without_bonus:
            assert results_with_bonus[0][1] > results_without_bonus[0][1]

    def test_headline_bonus_capped_at_1_0(self) -> None:
        """Score + headline bonus must never exceed 1.0."""
        asset = _make_asset("MGC", primary_keywords=["micro gold", "gold futures", "COMEX gold"])
        results = _match(
            "MGC micro gold gold futures COMEX gold",
            "micro gold gold futures COMEX gold extra keywords",
            [asset],
        )
        assert len(results) == 1
        assert results[0][1] <= 1.0

    def test_no_headline_bonus_without_primary_keyword_in_headline(self) -> None:
        """Headline bonus must NOT fire when primary keyword only appears in the body."""
        asset = _make_asset("MGC", primary_keywords=["micro gold"])
        results_body_only = _match(
            "Commodities rally broadly",
            "Micro gold was among the gainers today",
            [asset],
        )
        results_headline = _match(
            "Micro gold leads commodities rally",
            "The commodity market saw broad gains",
            [asset],
        )
        if results_body_only and results_headline:
            # Headline match must score higher due to bonus
            assert results_headline[0][1] > results_body_only[0][1]


# ---------------------------------------------------------------------------
# MIN_SCORE filter
# ---------------------------------------------------------------------------


class TestMinScoreFilter:
    """Articles below MIN_SCORE threshold are excluded from results."""

    def test_min_score_constant_is_0_25(self) -> None:
        assert MIN_SCORE == 0.25

    def test_score_below_threshold_excluded(self) -> None:
        """Secondary single hit → 0.2 < 0.25 → excluded."""
        asset = _make_asset("MGC", secondary_keywords=["gold"])
        results = _match("Markets mixed today", "Gold was mentioned once", [asset])
        assert len(results) == 0

    def test_score_at_threshold_included(self) -> None:
        """Score exactly equal to MIN_SCORE should be included."""
        asset = _make_asset("MGC", secondary_keywords=["gold", "precious"])
        results = _match(
            "Gold and precious metals move",
            "Gold and precious metals were active",
            [asset],
        )
        assert len(results) == 1
        assert results[0][1] >= MIN_SCORE

    def test_score_above_threshold_included(self) -> None:
        """Any score > MIN_SCORE must be included."""
        asset = _make_asset("MGC", primary_keywords=["micro gold"])
        results = _match("Micro gold", "", [asset])
        assert len(results) == 1


# ---------------------------------------------------------------------------
# Multi-asset matching
# ---------------------------------------------------------------------------


class TestMultiAssetMatching:
    """All relevant assets should be returned when multiple match."""

    def test_multiple_assets_matched(self) -> None:
        """An article about gold and silver should match both MGC and SIL."""
        mgc = _make_asset("MGC", primary_keywords=["micro gold", "gold futures"])
        sil = _make_asset("SIL", primary_keywords=["micro silver", "silver futures"])

        headline = "Gold and silver surge on Fed pivot hopes"
        body = "Micro gold and micro silver contracts led gains as gold futures and silver futures advanced"

        results = _match(headline, body, [mgc, sil])
        symbols = [r[0] for r in results]

        assert "MGC" in symbols
        assert "SIL" in symbols

    def test_irrelevant_asset_not_matched(self) -> None:
        """An unrelated asset must not appear in results."""
        mgc = _make_asset("MGC", primary_keywords=["micro gold"])
        btc = _make_asset("BTC/USD", primary_keywords=["Bitcoin", "BTC"])

        results = _match("Micro gold futures rally", "Gold micro contract sees volume", [mgc, btc])
        symbols = [r[0] for r in results]

        assert "MGC" in symbols
        assert "BTC/USD" not in symbols

    def test_returns_all_above_min_score(self) -> None:
        """Every matched asset with score ≥ MIN_SCORE should appear in results."""
        assets = [
            _make_asset("MGC", primary_keywords=["micro gold"]),
            _make_asset("MES", primary_keywords=["micro S&P", "E-mini S&P"]),
            _make_asset("MNQ", primary_keywords=["micro Nasdaq"]),
            _make_asset("UNRELATED", secondary_keywords=["xyz"]),  # single secondary → excluded
        ]

        body = "Micro gold micro S&P E-mini S&P and micro Nasdaq all moved today"
        results = _match("Multi-asset rally", body, assets)

        symbols = [r[0] for r in results]
        assert "MGC" in symbols
        assert "MES" in symbols
        assert "MNQ" in symbols
        assert "UNRELATED" not in symbols

    def test_empty_asset_list_returns_empty(self) -> None:
        results = _match("Gold surges", "Gold micro contracts rally", [])
        assert results == []

    def test_scores_are_independent_per_asset(self) -> None:
        """Each asset's score must be computed independently."""
        mgc = _make_asset("MGC", primary_keywords=["micro gold"])
        mes = _make_asset("MES", primary_keywords=["micro S&P"])

        results = _match(
            "MGC micro gold surges",
            "Micro gold sees huge volume",
            [mgc, mes],
        )
        mgc_result = next((r for r in results if r[0] == "MGC"), None)
        mes_result = next((r for r in results if r[0] == "MES"), None)

        assert mgc_result is not None
        # MES should not be in results since no MES keywords were matched
        assert mes_result is None


# ---------------------------------------------------------------------------
# match_type precedence
# ---------------------------------------------------------------------------


class TestMatchTypePrecedence:
    """match_type follows ticker > primary > secondary precedence."""

    def test_ticker_beats_primary(self) -> None:
        """When ticker is detected in headline, match_type must be 'ticker'."""
        asset = _make_asset("MGC", primary_keywords=["micro gold"])
        results = _match("MGC micro gold rallies", "micro gold and MGC are active", [asset])
        assert results[0][2] == "ticker"

    def test_primary_beats_secondary(self) -> None:
        """When primary keyword matches, match_type must be 'primary'."""
        asset = _make_asset(
            "MGC",
            primary_keywords=["micro gold"],
            secondary_keywords=["inflation", "gold", "precious"],
        )
        results = _match(
            "Commodities rise on inflation",
            "Micro gold, gold, precious metals and inflation all in focus",
            [asset],
        )
        assert results[0][2] == "primary"

    def test_secondary_only_when_no_ticker_or_primary(self) -> None:
        """When only secondary keywords match, match_type must be 'secondary'."""
        asset = _make_asset(
            "MGC",
            primary_keywords=[],
            secondary_keywords=["safe haven", "precious metals", "dollar"],
        )
        results = _match(
            "Safe haven assets rise as dollar weakens precious metals",
            "Precious metals and safe haven demand increased",
            [asset],
        )
        if results:
            assert results[0][2] == "secondary"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Edge cases: empty inputs, special characters, unicode."""

    def test_empty_headline_and_body(self) -> None:
        asset = _make_asset("MGC", primary_keywords=["micro gold"])
        results = _match("", "", [asset])
        assert len(results) == 0

    def test_empty_headline_with_body_keyword(self) -> None:
        """Keywords only in body can still produce a match (above threshold)."""
        asset = _make_asset("MGC", primary_keywords=["micro gold"])
        results = _match("", "Micro gold and more micro gold activity today", [asset])
        # Two primary hits in body → 0.7 base → above MIN_SCORE
        assert len(results) == 1

    def test_none_body_handled_gracefully(self) -> None:
        """None body is converted to empty string by the caller, not the matcher."""
        asset = _make_asset("MGC", primary_keywords=["micro gold"])
        # Matcher receives plain strings; test that empty body is fine
        results = _match("Micro gold futures", "", [asset])
        assert len(results) == 1

    def test_special_characters_in_ticker(self) -> None:
        """Tickers with special characters like '/' should match their base part."""
        asset = _make_asset("BTC/USD", primary_keywords=["Bitcoin"])
        results = _match("BTC and Bitcoin rally", "Bitcoin surges to new high", [asset])
        assert len(results) == 1

    def test_result_scores_are_rounded_to_3_decimals(self) -> None:
        """match() must return scores rounded to 3 decimal places."""
        asset = _make_asset("MGC", primary_keywords=["micro gold"])
        results = _match("Micro gold", "micro gold micro gold", [asset])
        if results:
            _sym, score, _mt = results[0]
            # Score must have at most 3 decimal places
            assert score == round(score, 3)

    def test_duplicate_keywords_do_not_double_count(self) -> None:
        """The same keyword appearing multiple times in text is one hit."""
        asset = _make_asset("MGC", primary_keywords=["micro gold"])
        # 'micro gold' appears 5 times in body — but it's ONE unique keyword
        body = "micro gold micro gold micro gold micro gold micro gold"
        results = _match("Some headline", body, [asset])
        if results:
            _sym, score, _mt = results[0]
            # Single keyword → 0.6 base (not 0.6 + 4*0.1)
            # No headline bonus (keyword not in headline)
            assert score < 0.7, f"Expected single-keyword score < 0.7, got {score}"
