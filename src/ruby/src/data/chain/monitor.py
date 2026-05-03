"""
ChainMonitor -- supervisord worker that runs all chain providers
on a schedule and feeds results to Postgres + Redis pub/sub.

Pub/sub channels written:
  ch:chain:whale          -> every whale tx above threshold
  ch:chain:whale:BTC      -> BTC-specific whale txns
  ch:chain:whale:ETH
  ch:chain:whale:SOL
  ch:chain:mempool        -> BTC mempool snapshots every 60s
  ch:chain:exchange_flow  -> hourly exchange flow summaries

Redis keys:
  chain:whale:recent              -> list (LPUSH, max 200 items)
  chain:mempool:latest            -> latest MempoolSnapshot JSON
  chain:flow:{chain}:{exchange}   -> ExchangeFlow JSON, TTL 4h
  chain:watchlist                 -> JSON list of WalletWatch

Postgres tables:
  chain_transactions    -> all whale moves, deduplicated by tx_hash
  chain_exchange_flows  -> hourly exchange flow snapshots
  chain_watchlist       -> user's watched wallets
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from typing import TYPE_CHECKING

from .correlator import ChainSignalCorrelator
from .providers import (
    CryptoCompareProvider,
    EtherscanProvider,
    MempoolSpaceProvider,
    SolscanProvider,
    WhaleAlertProvider,
)
from .schemas import Chain, ChainTransaction, Sentiment, WhaleTier

if TYPE_CHECKING:
    import redis.asyncio as aioredis
    from sqlalchemy.ext.asyncio import AsyncEngine

from core.logging_config import get_logger

log = get_logger(__name__)

# Thresholds (overridable via env or Redis)
DEFAULT_MIN_USD = float(os.getenv("CHAIN_MIN_USD", "1000000"))
WHALE_RECENT_MAX = 200
POLL_WHALE_SECS = int(os.getenv("CHAIN_POLL_WHALE", "30"))
POLL_MEMPOOL_SECS = int(os.getenv("CHAIN_POLL_MEMPOOL", "60"))
POLL_FLOW_SECS = int(os.getenv("CHAIN_POLL_FLOW", "3600"))


class ChainMonitor:
    def __init__(
        self,
        redis: aioredis.Redis,
        engine: AsyncEngine,
    ) -> None:
        self._r = redis
        self._engine = engine
        self._whale = WhaleAlertProvider()
        self._etherscan = EtherscanProvider(redis=redis)
        self._solscan = SolscanProvider(redis=redis)
        self._mempool = MempoolSpaceProvider()
        self._ccmp = CryptoCompareProvider()
        self._correlator = ChainSignalCorrelator(redis)
        self._seen_hashes: set[str] = set()

    async def run(self) -> None:
        """Long-running task -- call from coordinator."""
        log.info("ChainMonitor starting")
        await asyncio.gather(
            self._loop_whale(),
            self._loop_mempool(),
            self._loop_flows(),
            self._loop_watchlist(),
        )

    # -- Whale polling loop ----------------------------------------------------

    async def _loop_whale(self) -> None:
        while True:
            try:
                since = int(time.time()) - POLL_WHALE_SECS * 2
                txns = await self._whale.fetch_recent(since)
                eth_txns = await self._etherscan.fetch_large_txns()
                sol_txns = await self._solscan.fetch_large_txns()
                all_txns = txns + eth_txns + sol_txns

                for tx in all_txns:
                    if tx.tx_hash and tx.tx_hash in self._seen_hashes:
                        continue
                    if tx.amount_usd < DEFAULT_MIN_USD:
                        continue
                    await self._process_tx(tx)
                    if tx.tx_hash:
                        self._seen_hashes.add(tx.tx_hash)

                # Trim seen set to avoid unbounded growth
                if len(self._seen_hashes) > 10_000:
                    self._seen_hashes = set(list(self._seen_hashes)[-5_000:])

            except Exception:
                log.exception("ChainMonitor whale loop error")
            await asyncio.sleep(POLL_WHALE_SECS)

    async def _process_tx(self, tx: ChainTransaction) -> None:
        # Enrich with signal correlation
        tx = await self._correlator.enrich(tx)

        # Store in Postgres
        await self._store_tx(tx)

        # Push to Redis recent list
        payload = json.dumps(self._tx_to_dict(tx))
        pipe = self._r.pipeline()
        pipe.lpush("chain:whale:recent", payload)
        pipe.ltrim("chain:whale:recent", 0, WHALE_RECENT_MAX - 1)

        # Publish to pub/sub channels
        pipe.publish("ch:chain:whale", payload)
        pipe.publish(f"ch:chain:whale:{tx.chain.value}", payload)
        await pipe.execute()

        # Discord alert for high-tier moves
        if tx.tier in (WhaleTier.MEGA, WhaleTier.LARGE):
            await self._discord_alert(tx)

        log.info(
            "Whale tx: %s %s %.0f %s (%.0f USD) %s->%s [%s]",
            tx.tier.value.upper(),
            tx.chain.value,
            tx.amount_native,
            tx.token,
            tx.amount_usd,
            tx.from_label or tx.from_address[:8],
            tx.to_label or tx.to_address[:8],
            tx.sentiment.value,
        )

    # -- Mempool loop ----------------------------------------------------------

    async def _loop_mempool(self) -> None:
        while True:
            try:
                snap = await self._mempool.fetch_mempool()
                if snap:
                    payload = json.dumps(
                        {
                            "pending_txns": snap.pending_txns,
                            "size_mb": snap.size_mb,
                            "fee_next_block": snap.fee_next_block,
                            "fee_30min": snap.fee_30min,
                            "fee_1hour": snap.fee_1hour,
                            "fee_economy": snap.fee_economy,
                            "as_of": snap.as_of.isoformat() if snap.as_of else None,
                        }
                    )
                    await self._r.setex("chain:mempool:latest", 120, payload)
                    await self._r.publish("ch:chain:mempool", payload)

                    # Alert on congestion
                    if snap.fee_next_block > 100:
                        await self._r.publish(
                            "ch:chain:alert",
                            json.dumps(
                                {
                                    "type": "mempool_congestion",
                                    "fee": snap.fee_next_block,
                                    "msg": f"BTC mempool congested: {snap.fee_next_block:.0f} sat/vB",
                                }
                            ),
                        )
            except Exception:
                log.exception("ChainMonitor mempool loop error")
            await asyncio.sleep(POLL_MEMPOOL_SECS)

    # -- Exchange flow loop ----------------------------------------------------

    async def _loop_flows(self) -> None:
        await asyncio.sleep(60)  # let whale loop stabilise first
        while True:
            try:
                for chain in (Chain.BTC, Chain.ETH, Chain.SOL):
                    flows = await self._ccmp.fetch_exchange_flows(chain)
                    for flow in flows:
                        key = f"chain:flow:{chain.value}:{flow.exchange}"
                        payload = json.dumps(
                            {
                                "chain": chain.value,
                                "exchange": flow.exchange,
                                "inflow_native": flow.inflow_native,
                                "outflow_native": flow.outflow_native,
                                "inflow_usd": flow.inflow_usd,
                                "outflow_usd": flow.outflow_usd,
                                "net_native": flow.net_native,
                                "sentiment": flow.sentiment.value
                                if hasattr(flow.sentiment, "value")
                                else str(flow.sentiment),
                            }
                        )
                        await self._r.setex(key, 3600 * 4, payload)
                    await self._store_flows(chain, flows)
            except Exception:
                log.exception("ChainMonitor flow loop error")
            await asyncio.sleep(POLL_FLOW_SECS)

    # -- Watchlist polling -----------------------------------------------------

    async def _loop_watchlist(self) -> None:
        """Poll watched wallets for new transactions every 5 minutes."""
        while True:
            try:
                raw = await self._r.get("chain:watchlist")
                if not raw:
                    await asyncio.sleep(300)
                    continue

                watchlist = json.loads(raw)
                for wallet in watchlist:
                    if not wallet.get("enabled", True):
                        continue
                    await self._check_watched_wallet(wallet)
                    await asyncio.sleep(2)  # rate limit
            except Exception:
                log.exception("ChainMonitor watchlist loop error")
            await asyncio.sleep(300)

    async def _check_watched_wallet(self, wallet: dict) -> None:
        """Check a watched wallet for new activity."""
        addr = wallet["address"]
        chain = wallet.get("chain", "ETH")
        last_key = f"chain:watchlist:last_tx:{addr}"
        last_seen_raw = await self._r.get(last_key)
        last_seen_hash: str | None = None
        if last_seen_raw is not None:
            last_seen_hash = last_seen_raw.decode() if isinstance(last_seen_raw, bytes) else last_seen_raw

        # Query the appropriate provider for recent transactions
        txns: list[ChainTransaction] = []
        if chain == "ETH":
            txns = await self._etherscan.fetch_wallet_txns(addr)
        elif chain == "SOL":
            txns = await self._solscan.fetch_wallet_txns(addr)

        if not txns:
            return

        # Collect new transactions (those we haven't seen yet)
        new_txns: list[ChainTransaction] = []
        for tx in txns:
            if tx.tx_hash == last_seen_hash:
                break
            new_txns.append(tx)

        if not new_txns:
            return

        # Update last-seen transaction hash to the most recent one
        await self._r.set(last_key, new_txns[0].tx_hash)

        # Fire alerts for each new transaction
        for tx in new_txns:
            payload = json.dumps(
                {
                    "type": "watched_wallet",
                    "address": addr,
                    "chain": chain,
                    "tx_hash": tx.tx_hash,
                    "amount_native": tx.amount_native,
                    "amount_usd": tx.amount_usd,
                    "from": tx.from_address,
                    "to": tx.to_address,
                    "label": wallet.get("label", addr[:12]),
                }
            )
            await self._r.publish("ch:chain:wallet_alert", payload)
            await self._r.publish(f"ch:chain:whale:{chain}", payload)
            log.info(
                "Watched wallet activity: %s (%s) tx=%s $%.0f",
                wallet.get("label", addr[:12]),
                chain,
                tx.tx_hash[:16] if tx.tx_hash else "?",
                tx.amount_usd,
            )

    # -- Storage ---------------------------------------------------------------

    async def _store_tx(self, tx: ChainTransaction) -> None:
        from sqlalchemy import text

        async with self._engine.begin() as conn:
            await conn.execute(
                text("""
                INSERT INTO chain_transactions (
                    chain, tx_hash, tx_type, amount_native, amount_usd,
                    from_address, to_address, from_label, to_label,
                    token, tx_timestamp, block_height, tier, sentiment,
                    source, correlation_score, raw_json
                ) VALUES (
                    :chain, :tx_hash, :tx_type, :amount_native, :amount_usd,
                    :from_address, :to_address, :from_label, :to_label,
                    :token, :tx_timestamp, :block_height, :tier, :sentiment,
                    :source, :correlation_score, :raw_json
                )
                ON CONFLICT (tx_hash) DO NOTHING
            """),
                {
                    "chain": tx.chain.value,
                    "tx_hash": tx.tx_hash,
                    "tx_type": tx.tx_type.value,
                    "amount_native": tx.amount_native,
                    "amount_usd": tx.amount_usd,
                    "from_address": tx.from_address,
                    "to_address": tx.to_address,
                    "from_label": tx.from_label,
                    "to_label": tx.to_label,
                    "token": tx.token,
                    "tx_timestamp": tx.timestamp,
                    "block_height": tx.block_height,
                    "tier": tx.tier.value,
                    "sentiment": tx.sentiment.value,
                    "source": tx.source,
                    "correlation_score": tx.correlation_score,
                    "raw_json": json.dumps(tx.raw),
                },
            )

    async def _store_flows(self, chain: Chain, flows: list) -> None:
        from sqlalchemy import text

        async with self._engine.begin() as conn:
            for flow in flows:
                await conn.execute(
                    text("""
                    INSERT INTO chain_exchange_flows (
                        chain, exchange, inflow_native, outflow_native,
                        inflow_usd, outflow_usd, net_native, sentiment,
                        period_hours, as_of
                    ) VALUES (
                        :chain, :exchange, :inflow_native, :outflow_native,
                        :inflow_usd, :outflow_usd, :net_native, :sentiment,
                        :period_hours, NOW()
                    )
                """),
                    {
                        "chain": chain.value,
                        "exchange": flow.exchange,
                        "inflow_native": flow.inflow_native,
                        "outflow_native": flow.outflow_native,
                        "inflow_usd": flow.inflow_usd,
                        "outflow_usd": flow.outflow_usd,
                        "net_native": flow.net_native,
                        "sentiment": flow.sentiment.value if hasattr(flow.sentiment, "value") else str(flow.sentiment),
                        "period_hours": 24,
                    },
                )

    async def _discord_alert(self, tx: ChainTransaction) -> None:
        """Publish a Discord-bound alert for large whale moves."""
        emoji = "🟢" if tx.sentiment == Sentiment.BULLISH else "🔴" if tx.sentiment == Sentiment.BEARISH else "🟡"
        msg = (
            f"{emoji} **{tx.tier.value.upper()} WHALE** . {tx.chain.value}\n"
            f"**{tx.amount_native:,.0f} {tx.token}** (${tx.amount_usd / 1e6:.1f}M)\n"
            f"{tx.from_label or tx.from_address[:12]} -> {tx.to_label or tx.to_address[:12]}\n"
            f"Sentiment: **{tx.sentiment.value.upper()}** . {tx.tx_type.value.replace('_', ' ')}"
        )
        await self._r.publish(
            "ch:discord:chain",
            json.dumps(
                {
                    "channel": "chain-alerts" if tx.tier == WhaleTier.MEGA else "factory",
                    "message": msg,
                    "tx_hash": tx.tx_hash,
                }
            ),
        )

    @staticmethod
    def _tx_to_dict(tx: ChainTransaction) -> dict:
        return {
            "chain": tx.chain.value,
            "tx_hash": tx.tx_hash,
            "tx_type": tx.tx_type.value,
            "amount_native": tx.amount_native,
            "amount_usd": tx.amount_usd,
            "from_address": tx.from_address,
            "to_address": tx.to_address,
            "from_label": tx.from_label,
            "to_label": tx.to_label,
            "token": tx.token,
            "timestamp": tx.timestamp.isoformat(),
            "block_height": tx.block_height,
            "tier": tx.tier.value,
            "sentiment": tx.sentiment.value,
            "source": tx.source,
            "correlation_score": tx.correlation_score,
            "correlated_signals": tx.correlated_signals,
        }
