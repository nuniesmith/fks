"""
ChainSignalCorrelator -- enriches whale transactions with context
from your active trading signals, CMC Fear & Greed, and BTC dominance.

Logic:
  - If a BEARISH whale tx (exchange deposit) happens when you have a LONG
    signal active on a correlated asset, that's a confluence warning
  - If a BULLISH whale tx (exchange withdrawal, stablecoin mint) aligns
    with a LONG signal, that's additional confluence
  - Score: -1.0 (counter-signal) to +1.0 (strong confluence)

CMC enrichment:
  - Fear & Greed < 45 + BULLISH whale = contrarian confluence (+0.25)
  - Fear & Greed >= 55 + BEARISH whale = distribution signal (-0.2)
  - BTC dominance < 44% + ETH BULLISH whale = alt season amplifier (+0.15)

Correlation written to Redis for the terminal to display:
  chain:correlation:latest  -> list of last 20 correlation events
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import redis.asyncio as aioredis

import contextlib

from core.logging_config import get_logger

from .schemas import Chain, ChainTransaction, Sentiment

log = get_logger(__name__)

# Which crypto assets correlate with CME futures
CHAIN_TO_FUTURES: dict[str, list[str]] = {
    "BTC": ["MGC", "MES", "MNQ"],  # BTC moves affect macro risk-on/off
    "ETH": ["MNQ", "MES"],  # ETH = risk-on tech proxy
    "SOL": ["MNQ"],  # SOL = high-risk growth proxy
}


class ChainSignalCorrelator:
    def __init__(self, redis: aioredis.Redis) -> None:
        self._r = redis

    async def enrich(self, tx: ChainTransaction) -> ChainTransaction:
        """
        Add correlation score and matched signal IDs to a whale tx.
        Reads active signals from Ruby's signal state in Redis,
        plus CMC Fear & Greed and BTC dominance for macro context.
        """
        try:
            # -- Signal correlation layer --
            related_assets = CHAIN_TO_FUTURES.get(tx.chain.value, [])
            if related_assets:
                signals = await self._get_active_signals(related_assets)
                for sig in signals:
                    sig_direction = sig.get("direction", "").upper()
                    tx_sentiment = tx.sentiment

                    if sig_direction == "LONG" and tx_sentiment == Sentiment.BULLISH:
                        tx.correlation_score += 0.4
                        tx.correlated_signals.append(f"LONG {sig['symbol']} + {tx_sentiment.value}")
                    elif sig_direction == "SHORT" and tx_sentiment == Sentiment.BEARISH:
                        tx.correlation_score += 0.4
                        tx.correlated_signals.append(f"SHORT {sig['symbol']} + {tx_sentiment.value}")
                    elif sig_direction == "LONG" and tx_sentiment == Sentiment.BEARISH:
                        tx.correlation_score -= 0.3
                        tx.correlated_signals.append(f"COUNTER: LONG {sig['symbol']} vs {tx_sentiment.value}")
                    elif sig_direction == "SHORT" and tx_sentiment == Sentiment.BULLISH:
                        tx.correlation_score -= 0.3
                        tx.correlated_signals.append(f"COUNTER: SHORT {sig['symbol']} vs {tx_sentiment.value}")

            # Amplify for mega whales
            if tx.amount_usd >= 100_000_000:
                tx.correlation_score *= 1.5

            # -- CMC macro context layer --
            await self._enrich_cmc(tx)

            # Clamp final score
            tx.correlation_score = max(-1.0, min(1.0, tx.correlation_score))

            # Publish correlation event if significant
            if abs(tx.correlation_score) > 0.3:
                await self._publish_correlation(tx)

        except Exception as e:
            log.debug("Correlator error: %s", e)

        return tx

    async def _enrich_cmc(self, tx: ChainTransaction) -> None:
        """Layer in CMC Fear & Greed and BTC dominance context."""
        try:
            fg_raw = await self._r.get("cmc:fear_greed")
            if fg_raw:
                fg = json.loads(fg_raw)
                fg_v = fg.get("value", 50)
                sent = fg.get("sentiment", "neutral")

                # Extreme fear + bullish whale = contrarian confluence
                if sent in ("fear", "extreme_fear") and tx.sentiment == Sentiment.BULLISH:
                    tx.correlation_score += 0.25
                    tx.correlated_signals.append(f"F&G={fg_v} (fear) + bullish whale = contrarian confluence")
                # Extreme greed + bearish whale = distribution warning
                elif sent in ("greed", "extreme_greed") and tx.sentiment == Sentiment.BEARISH:
                    tx.correlation_score -= 0.2
                    tx.correlated_signals.append(f"F&G={fg_v} (greed) + bearish whale = distribution signal")

            # BTC dominance layer for ETH whales
            if tx.chain == Chain.ETH:
                btc_dom_raw = await self._r.get("cmc:btc_dominance")
                if btc_dom_raw:
                    dom = float(btc_dom_raw)
                    if dom < 44.0 and tx.sentiment == Sentiment.BULLISH:
                        tx.correlation_score += 0.15
                        tx.correlated_signals.append(f"BTC dom={dom:.1f}% (low) = alt season amplifier")
        except Exception as e:
            log.debug("CMC correlation error: %s", e)

    async def _get_active_signals(self, symbols: list[str]) -> list[dict]:
        """Read Janus/Ruby active signals from Redis."""
        signals = []
        for sym in symbols:
            raw = await self._r.get(f"ruby:signals:active:{sym}")
            if raw:
                with contextlib.suppress(Exception):
                    signals.append(json.loads(raw))
        return signals

    async def _publish_correlation(self, tx: ChainTransaction) -> None:
        event = {
            "tx_hash": tx.tx_hash,
            "chain": tx.chain.value,
            "token": tx.token,
            "amount_usd": tx.amount_usd,
            "tier": tx.tier.value,
            "sentiment": tx.sentiment.value,
            "score": tx.correlation_score,
            "matched": tx.correlated_signals,
            "confluence": "bullish" if tx.correlation_score > 0 else "bearish",
            "timestamp": datetime.now(UTC).isoformat(),
        }
        payload = json.dumps(event)
        pipe = self._r.pipeline()
        pipe.lpush("chain:correlation:latest", payload)
        pipe.ltrim("chain:correlation:latest", 0, 19)
        pipe.publish("ch:chain:correlation", payload)
        await pipe.execute()
