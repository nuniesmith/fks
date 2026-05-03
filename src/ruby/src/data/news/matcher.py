"""Keyword-based asset matcher for the news pipeline.

Scores how relevant a news article is to each enabled asset using a simple
two-tier keyword system:

* **Primary match** — exact ticker mention or ``primary_keywords`` hit →
  base score in the 0.7–1.0 range.
* **Secondary match** — ``secondary_keywords`` hit → base score in the
  0.3–0.6 range.

Multiple keyword hits compound additively, capped at 1.0.  Articles whose
best score falls below :data:`MIN_SCORE` are not linked to the asset at all.

The algorithm is intentionally simple (no embeddings, no LLM calls) so that
it can run synchronously at ingestion speed.  Qdrant-backed semantic matching
can be layered on top later for higher-precision retrieval.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..registry.schemas import AssetConfig

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MIN_SCORE: float = 0.25


# ---------------------------------------------------------------------------
# Matcher
# ---------------------------------------------------------------------------


class AssetMatcher:
    """Score news articles against the enabled asset catalog."""

    def match(
        self,
        headline: str,
        body: str,
        assets: list[AssetConfig],
    ) -> list[tuple[str, float, str]]:
        """Return ``(symbol, score, match_type)`` tuples for relevant assets.

        Parameters
        ----------
        headline:
            Article headline (plain text).
        body:
            Article body (plain text, may be empty).
        assets:
            Full list of :class:`AssetConfig` objects to test against.

        Returns
        -------
        list[tuple[str, float, str]]
            Each entry is ``(symbol, rounded_score, match_type)`` where
            *match_type* is one of ``"ticker"``, ``"primary"``, or
            ``"secondary"``.  Only assets with ``score >= MIN_SCORE`` are
            included.
        """
        text = f"{headline} {body}".lower()
        results: list[tuple[str, float, str]] = []

        for asset in assets:
            if not asset.news.enabled:
                continue

            score, match_type = self._score(text, headline, asset)

            if score >= MIN_SCORE:
                results.append((asset.symbol, round(score, 3), match_type))

        return results

    # ------------------------------------------------------------------
    # Internal scoring
    # ------------------------------------------------------------------

    def _score(
        self,
        text: str,
        headline: str,
        asset: AssetConfig,
    ) -> tuple[float, str]:
        """Compute a relevance score for *asset* against pre-lowered *text*.

        Returns ``(score, match_type)`` where *score* ∈ [0, 1].
        """
        score: float = 0.0
        match_type: str = "secondary"

        # -- Ticker detection (headline only, word-boundary match) ----------
        ticker = asset.symbol.split("/")[0].upper()
        pattern = r"\b" + re.escape(ticker) + r"\b"
        if re.search(pattern, headline.upper()):
            score += 0.8
            match_type = "ticker"

        # -- Primary keywords -----------------------------------------------
        primary_hits = sum(1 for kw in asset.news.primary_keywords if kw.lower() in text)
        if primary_hits > 0:
            score += min(0.6 + (primary_hits - 1) * 0.1, 0.9)
            if match_type != "ticker":
                match_type = "primary"

        # -- Secondary keywords ---------------------------------------------
        secondary_hits = sum(1 for kw in asset.news.secondary_keywords if kw.lower() in text)
        if secondary_hits > 0:
            score += min(0.2 + (secondary_hits - 1) * 0.05, 0.45)

        # -- Headline bonus -------------------------------------------------
        headline_lower = headline.lower()
        if any(kw.lower() in headline_lower for kw in asset.news.primary_keywords):
            score = min(score + 0.15, 1.0)

        return (min(score, 1.0), match_type)
