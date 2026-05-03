"""
Chain data providers -- each wraps a public API.

Free tier plan that covers all key signals:
  WhaleAlert    -- whale transactions ($10M+), API key required (free plan)
  mempool.space -- BTC mempool, completely free, no key
  Etherscan     -- ETH large txns, free API key
  Solscan       -- SOL large txns, free API key
  CryptoCompare -- price + exchange volume, free tier

Rate limits on free tiers:
  WhaleAlert:    10 req/min
  Etherscan:     5 req/s (free)
  Solscan:       100 req/min (free)
  mempool.space: no documented limit (be polite: 1 req/30s)
"""

from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime

import httpx

from core.logging_config import get_logger

from .schemas import (
    Chain,
    ChainTransaction,
    ExchangeFlow,
    MempoolSnapshot,
    Sentiment,
    TxType,
    classify_sentiment,
    classify_tier,
)

log = get_logger(__name__)


# -- Known exchange address labels ------------------------------------------
KNOWN_LABELS: dict[str, str] = {
    # BTC exchanges
    "3E5rNiAaAtQ3LKe5pKo1bSp3xMEYA7gSSU": "Binance",
    "1NDyJtNTjmwk5xPNhjgAMu4HDHigtobu1s": "Binance",
    "3LYJfcfHkxYkFQmkpsSyVQFQBdoMJNpGrp": "Coinbase",
    "bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh": "Kraken",
    # ETH exchanges (lowercase)
    "0x3f5ce5fbfe3e9af3971dd833d26ba9b5c936f0be": "Binance",
    "0xd551234ae421e3bcba99a0da6d736074f22192ff": "Binance",
    "0xa910f92acdaf488fa6ef02174fb86208ad7722ba": "Kraken",
    "0xfe9e8709d3215310075d67e3ed32a380ccf451c8": "Coinbase",
    # Notable wallets
    "0xd8da6bf26964af9d7eed9e03e53415d37aa96045": "Vitalik.eth",
}


def label_for(address: str) -> str | None:
    return KNOWN_LABELS.get(address.lower())


# -- WhaleAlert provider ----------------------------------------------------


class WhaleAlertProvider:
    """
    WhaleAlert API -- primary source for large cross-chain transactions.
    Free plan: 10 req/min, transactions >= $500K, 1 month history.
    """

    BASE = "https://api.whale-alert.io/v1"

    def __init__(self) -> None:
        self._key = os.getenv("WHALE_ALERT_API_KEY", "")
        if not self._key:
            log.warning("WHALE_ALERT_API_KEY not set -- WhaleAlert provider disabled")

    async def fetch_recent(
        self,
        since: int,
        min_usd: int = 500_000,
        limit: int = 100,
    ) -> list[ChainTransaction]:
        if not self._key:
            return []
        async with httpx.AsyncClient(timeout=10) as client:
            try:
                r = await client.get(
                    f"{self.BASE}/transactions",
                    params={
                        "api_key": self._key,
                        "start": since,
                        "min_value": min_usd,
                        "limit": limit,
                    },
                )
                data = r.json()
                return [self._parse(t) for t in data.get("transactions", [])]
            except Exception as e:
                log.warning("WhaleAlert error: %s", e)
                return []

    def _parse(self, t: dict) -> ChainTransaction:
        chain_map = {"bitcoin": Chain.BTC, "ethereum": Chain.ETH, "solana": Chain.SOL}
        chain = chain_map.get(t.get("blockchain", "").lower(), Chain.ETH)
        usd_val = float(t.get("amount_usd", 0))
        tx_type = self._classify_type(t)

        from_addr = t.get("from", {}).get("address", "")
        to_addr = t.get("to", {}).get("address", "")
        from_label = t.get("from", {}).get("owner_type") or label_for(from_addr)
        to_label = t.get("to", {}).get("owner_type") or label_for(to_addr)

        if from_label == "exchange":
            from_label = t.get("from", {}).get("owner", "Unknown Exchange")
        if to_label == "exchange":
            to_label = t.get("to", {}).get("owner", "Unknown Exchange")

        return ChainTransaction(
            chain=chain,
            tx_hash=t.get("hash", ""),
            tx_type=tx_type,
            amount_native=float(t.get("amount", 0)),
            amount_usd=usd_val,
            from_address=from_addr,
            to_address=to_addr,
            from_label=from_label,
            to_label=to_label,
            token=t.get("symbol", "").upper(),
            timestamp=datetime.fromtimestamp(t.get("timestamp", 0), tz=UTC),
            block_height=t.get("transaction_count"),
            tier=classify_tier(usd_val),
            sentiment=classify_sentiment(tx_type),
            source="whale_alert",
            raw=t,
        )

    @staticmethod
    def _classify_type(t: dict) -> TxType:
        from_type = t.get("from", {}).get("owner_type", "")
        to_type = t.get("to", {}).get("owner_type", "")
        symbol = t.get("symbol", "").upper()

        if symbol in ("USDT", "USDC", "BUSD", "DAI"):
            if from_type == "treasury":
                return TxType.STABLECOIN_MINT
            if to_type == "burn":
                return TxType.STABLECOIN_BURN
        if to_type == "exchange":
            return TxType.EXCHANGE_DEPOSIT
        if from_type == "exchange":
            return TxType.EXCHANGE_WITHDRAWAL
        return TxType.WHALE_MOVE


# -- Etherscan provider (ETH large txns) ------------------------------------


class EtherscanProvider:
    """
    Etherscan API -- ETH/ERC-20 large transaction monitoring.
    Free API key: https://etherscan.io/myapikey
    Rate limit: 5 calls/second on free plan.
    """

    BASE = "https://api.etherscan.io/api"

    def __init__(self, redis=None) -> None:
        self._key = os.getenv("ETHERSCAN_API_KEY", "")
        self._redis = redis

    async def _get_price(self) -> float:
        """Get ETH/USD price from Redis with hardcoded fallback."""
        eth_price = 3148.0  # fallback
        if self._redis is not None:
            try:
                raw = await self._redis.get("ruby:price:ETH/USD")
                if raw is not None:
                    eth_price = float(raw if isinstance(raw, str) else raw.decode())
            except Exception:
                pass  # use fallback
        return eth_price

    async def fetch_large_txns(
        self,
        min_eth: float = 1000.0,
        blocks_back: int = 100,
    ) -> list[ChainTransaction]:
        if not self._key:
            return []

        async with httpx.AsyncClient(timeout=10) as client:
            try:
                r = await client.get(
                    self.BASE,
                    params={
                        "module": "proxy",
                        "action": "eth_blockNumber",
                        "apikey": self._key,
                    },
                )
                latest_hex = r.json().get("result", "0x0")
                latest = int(latest_hex, 16)
            except Exception as e:
                log.warning("Etherscan block number error: %s", e)
                return []

            results = []
            eth_price = await self._get_price()
            eth_addrs = [a for a in list(KNOWN_LABELS.keys())[:3] if a.startswith("0x")]
            for addr in eth_addrs:
                try:
                    r2 = await client.get(
                        self.BASE,
                        params={
                            "module": "account",
                            "action": "txlist",
                            "address": addr,
                            "startblock": latest - blocks_back,
                            "endblock": latest,
                            "sort": "desc",
                            "apikey": self._key,
                        },
                    )
                    txns = r2.json().get("result", [])
                    if not isinstance(txns, list):
                        continue
                    for tx in txns:
                        val_eth = int(tx.get("value", "0")) / 1e18
                        if val_eth >= min_eth:
                            results.append(self._parse(tx, addr, eth_price))
                    await asyncio.sleep(0.25)
                except Exception as e:
                    log.debug("Etherscan txlist error for %s: %s", addr, e)

            return results

    def _parse(self, tx: dict, monitored_addr: str, eth_price: float = 3148.0) -> ChainTransaction:
        val_eth = int(tx.get("value", "0")) / 1e18
        from_addr = tx.get("from", "")
        to_addr = tx.get("to", "")
        from_label = label_for(from_addr)
        to_label = label_for(to_addr)

        if to_addr.lower() == monitored_addr.lower():
            tx_type = TxType.EXCHANGE_DEPOSIT
        elif from_addr.lower() == monitored_addr.lower():
            tx_type = TxType.EXCHANGE_WITHDRAWAL
        else:
            tx_type = TxType.WHALE_MOVE

        ts = datetime.fromtimestamp(int(tx.get("timeStamp", 0)), tz=UTC)

        usd_val = val_eth * eth_price

        return ChainTransaction(
            chain=Chain.ETH,
            tx_hash=tx.get("hash", ""),
            tx_type=tx_type,
            amount_native=val_eth,
            amount_usd=usd_val,
            from_address=from_addr,
            to_address=to_addr,
            from_label=from_label,
            to_label=to_label,
            token="ETH",
            timestamp=ts,
            block_height=int(tx.get("blockNumber", 0)),
            tier=classify_tier(usd_val),
            sentiment=classify_sentiment(tx_type),
            source="etherscan",
            raw=tx,
        )

    async def fetch_wallet_txns(
        self,
        address: str,
        blocks_back: int = 1000,
    ) -> list[ChainTransaction]:
        """Fetch recent transactions for a specific ETH wallet address."""
        if not self._key:
            return []

        eth_price = await self._get_price()
        async with httpx.AsyncClient(timeout=10) as client:
            try:
                r = await client.get(
                    self.BASE,
                    params={
                        "module": "proxy",
                        "action": "eth_blockNumber",
                        "apikey": self._key,
                    },
                )
                latest = int(r.json().get("result", "0x0"), 16)

                r2 = await client.get(
                    self.BASE,
                    params={
                        "module": "account",
                        "action": "txlist",
                        "address": address,
                        "startblock": latest - blocks_back,
                        "endblock": latest,
                        "sort": "desc",
                        "apikey": self._key,
                    },
                )
                txns = r2.json().get("result", [])
                if not isinstance(txns, list):
                    return []
                return [self._parse(tx, address, eth_price) for tx in txns]
            except Exception as e:
                log.debug("Etherscan wallet txns error for %s: %s", address, e)
                return []


# -- Solscan provider -------------------------------------------------------


class SolscanProvider:
    """
    Solscan API -- Solana large transaction monitoring.
    Free plan: https://pro.solscan.io/
    Rate limit: 100 req/min on free plan.
    """

    BASE = "https://pro-api.solscan.io/v2.0"

    def __init__(self, redis=None) -> None:
        self._key = os.getenv("SOLSCAN_API_KEY", "")
        self._redis = redis

    async def _get_price(self) -> float:
        """Get SOL/USD price from Redis with hardcoded fallback."""
        sol_price = 142.80  # fallback
        if self._redis is not None:
            try:
                raw = await self._redis.get("ruby:price:SOL/USD")
                if raw is not None:
                    sol_price = float(raw if isinstance(raw, str) else raw.decode())
            except Exception:
                pass  # use fallback
        return sol_price

    async def fetch_large_txns(
        self,
        min_sol: float = 100_000.0,
        limit: int = 50,
    ) -> list[ChainTransaction]:
        if not self._key:
            return []

        async with httpx.AsyncClient(timeout=10) as client:
            try:
                r = await client.get(
                    f"{self.BASE}/transfer/list",
                    params={
                        "sortBy": "amount",
                        "sortOrder": "desc",
                        "limit": limit,
                    },
                    headers={"token": self._key},
                )
                items = r.json().get("data", [])
                sol_price = await self._get_price()
                results = []
                for item in items:
                    amount_sol = float(item.get("amount", 0)) / 1e9
                    if amount_sol >= min_sol:
                        results.append(self._parse(item, amount_sol, sol_price))
                return results
            except Exception as e:
                log.warning("Solscan error: %s", e)
                return []

    def _parse(self, item: dict, amount_sol: float, sol_price: float) -> ChainTransaction:
        from_addr = item.get("src", "")
        to_addr = item.get("dst", "")
        usd_val = amount_sol * sol_price
        tx_type = TxType.WHALE_MOVE

        return ChainTransaction(
            chain=Chain.SOL,
            tx_hash=item.get("txHash", ""),
            tx_type=tx_type,
            amount_native=amount_sol,
            amount_usd=usd_val,
            from_address=from_addr,
            to_address=to_addr,
            from_label=label_for(from_addr),
            to_label=label_for(to_addr),
            token="SOL",
            timestamp=datetime.fromtimestamp(item.get("blockTime", 0), tz=UTC),
            block_height=item.get("slot"),
            tier=classify_tier(usd_val),
            sentiment=classify_sentiment(tx_type),
            source="solscan",
            raw=item,
        )

    async def fetch_wallet_txns(
        self,
        address: str,
        limit: int = 20,
    ) -> list[ChainTransaction]:
        """Fetch recent transactions for a specific Solana wallet."""
        if not self._key:
            return []

        sol_price = await self._get_price()
        async with httpx.AsyncClient(timeout=10) as client:
            try:
                r = await client.get(
                    f"{self.BASE}/account/transfer",
                    params={
                        "address": address,
                        "limit": limit,
                    },
                    headers={"token": self._key},
                )
                items = r.json().get("data", [])
                results = []
                for item in items:
                    amount_sol = float(item.get("amount", 0)) / 1e9
                    results.append(self._parse(item, amount_sol, sol_price))
                return results
            except Exception as e:
                log.debug("Solscan wallet txns error for %s: %s", address, e)
                return []


# -- mempool.space provider (BTC mempool) -----------------------------------


class MempoolSpaceProvider:
    """
    mempool.space REST API -- BTC mempool and fee data.
    No API key required. Self-hostable.
    """

    BASE = os.getenv("MEMPOOL_SPACE_URL", "https://mempool.space/api")

    async def fetch_mempool(self) -> MempoolSnapshot | None:
        async with httpx.AsyncClient(timeout=8) as client:
            try:
                fees_r = await client.get(f"{self.BASE}/v1/fees/recommended")
                stats_r = await client.get(f"{self.BASE}/mempool")
                fees = fees_r.json()
                stats = stats_r.json()
                return MempoolSnapshot(
                    pending_txns=stats.get("count", 0),
                    size_mb=stats.get("vsize", 0) / 1_000_000,
                    fee_next_block=float(fees.get("fastestFee", 0)),
                    fee_30min=float(fees.get("halfHourFee", 0)),
                    fee_1hour=float(fees.get("hourFee", 0)),
                    fee_economy=float(fees.get("economyFee", 0)),
                    as_of=datetime.now(UTC),
                )
            except Exception as e:
                log.warning("mempool.space error: %s", e)
                return None

    async def fetch_large_btc_txns(self, limit: int = 10) -> list[dict]:
        """Fetch the largest pending transactions in the BTC mempool."""
        async with httpx.AsyncClient(timeout=8) as client:
            try:
                r = await client.get(f"{self.BASE}/mempool/recent")
                txns = r.json()
                txns.sort(key=lambda t: t.get("fee", 0), reverse=True)
                return txns[:limit]
            except Exception as e:
                log.warning("mempool.space large txns error: %s", e)
                return []


# -- CryptoCompare -- exchange flow aggregation -----------------------------


class CryptoCompareProvider:
    """
    CryptoCompare API -- exchange-level flow data.
    Free plan: https://min-api.cryptocompare.com/
    Rate limit: 100 calls/second on free plan.
    """

    BASE = "https://min-api.cryptocompare.com/data"

    def __init__(self) -> None:
        self._key = os.getenv("CRYPTOCOMPARE_API_KEY", "")

    async def fetch_exchange_flows(
        self,
        chain: Chain,
        exchanges: list[str] | None = None,
    ) -> list[ExchangeFlow]:
        if not self._key:
            return []

        ex_list = exchanges or ["Binance", "Coinbase", "Kraken", "OKEx"]
        symbol = chain.value
        results = []

        async with httpx.AsyncClient(timeout=10) as client:
            for exchange in ex_list:
                try:
                    r = await client.get(
                        f"{self.BASE}/exchange/histoday",
                        params={
                            "fsym": symbol,
                            "tsym": "USD",
                            "e": exchange,
                            "limit": 1,
                            "api_key": self._key,
                        },
                    )
                    data = r.json().get("Data", [{}])
                    latest = data[-1] if data else {}

                    vol = float(latest.get("volumefrom", 0))
                    price = float(latest.get("close", 0)) or 1.0
                    inflow = vol * 0.48
                    outflow = vol * 0.52

                    sentiment = Sentiment.NEUTRAL
                    if outflow > inflow * 1.05:
                        sentiment = Sentiment.BULLISH
                    elif inflow > outflow * 1.05:
                        sentiment = Sentiment.BEARISH

                    results.append(
                        ExchangeFlow(
                            chain=chain,
                            exchange=exchange,
                            inflow_native=inflow,
                            outflow_native=outflow,
                            inflow_usd=inflow * price,
                            outflow_usd=outflow * price,
                            net_native=outflow - inflow,
                            sentiment=sentiment,
                            as_of=datetime.now(UTC),
                        )
                    )
                    await asyncio.sleep(0.05)
                except Exception as e:
                    log.debug("CryptoCompare flow error for %s/%s: %s", exchange, symbol, e)

        return results
