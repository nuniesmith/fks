"""
Async Redis store for the multi-asset futures trading bot.

Handles signal recording, PnL tracking, order history, worker heartbeats,
candle caching, and report storage.  Falls back to in-memory dicts when
Redis is unavailable so the bot can still run without a Redis instance.

Usage::

    from services.redis_store import RedisStore

    store = RedisStore(redis_url="redis://localhost:6379/0")
    await store.connect()
    await store.record_signal("BTCUSDT", {"side": "BUY", "price": 67000, ...})
    await store.close()
"""

from __future__ import annotations

import json
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from utils.logging_config import get_logger

try:
    import redis.asyncio as aioredis
except ImportError:  # pragma: no cover
    aioredis = None  # type: ignore[assignment]

logger = get_logger("redis_store")

# Eastern Time offset helpers (ET = UTC-5, EDT = UTC-4).
# We use ``ZoneInfo`` when available (3.9+), otherwise fall back to a fixed
# UTC-5 offset which is close enough for midnight-reset bucketing.
try:
    from zoneinfo import ZoneInfo

    _ET = ZoneInfo("America/New_York")
except ImportError:  # pragma: no cover
    _ET = timezone(timedelta(hours=-5))

_MAX_LIST_LEN = 1000
_HEARTBEAT_TTL = 120  # seconds


def _now_ts() -> float:
    """Current Unix timestamp."""
    return time.time()


def _today_et() -> str:
    """Return today's date string in ET, e.g. '2025-01-15'."""
    return datetime.now(tz=_ET).strftime("%Y-%m-%d")


def _midnight_et_ts() -> float:
    """Return Unix timestamp of midnight ET today."""
    now = datetime.now(tz=_ET)
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return midnight.timestamp()


def _days_ago_ts(days: int) -> float:
    """Return Unix timestamp for midnight ET *days* days ago."""
    now = datetime.now(tz=_ET)
    target = (now - timedelta(days=days)).replace(hour=0, minute=0, second=0, microsecond=0)
    return target.timestamp()


class RedisStore:
    """Async Redis store for trading state.

    Falls back to in-memory dicts when Redis is unavailable.
    """

    # ------------------------------------------------------------------ #
    #  Init / connect / close
    # ------------------------------------------------------------------ #

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/0",
        password: str | None = None,
        prefix: str = "futures:",
    ) -> None:
        self._url = redis_url
        self._password = password
        self._prefix = prefix
        self._redis: Any | None = None
        self._connected = False

        # In-memory fallback stores
        self._mem_lists: dict[str, list[str]] = defaultdict(list)
        self._mem_zsets: dict[str, list[tuple[float, str]]] = defaultdict(list)
        self._mem_hashes: dict[str, dict[str, str]] = defaultdict(dict)
        self._mem_strings: dict[str, tuple[str, float | None]] = {}  # value, expire_ts

    def _key(self, *parts: str) -> str:
        """Build a Redis key with the configured prefix."""
        return self._prefix + ":".join(parts)

    # ── Connection ─────────────────────────────────────────────

    async def connect(self) -> None:
        """Connect to Redis.  Falls back to in-memory if unavailable."""
        if aioredis is None:
            logger.warning("redis.asyncio not installed — using in-memory fallback (no persistence)")
            self._connected = False
            return

        try:
            kwargs: dict[str, Any] = {"decode_responses": True}
            if self._password:
                kwargs["password"] = self._password
            self._redis = aioredis.from_url(self._url, **kwargs)
            await self._redis.ping()
            self._connected = True
            logger.info("Redis connected at %s", self._url)
        except Exception as exc:
            logger.warning(
                "Redis unavailable (%s) — using in-memory fallback (no persistence)",
                exc,
            )
            self._redis = None
            self._connected = False

    async def close(self) -> None:
        """Close the Redis connection."""
        if self._redis is not None:
            try:
                await self._redis.aclose()
            except Exception:
                pass
            self._redis = None
            self._connected = False
            logger.info("Redis connection closed")

    @property
    def connected(self) -> bool:
        """``True`` if Redis is connected (not in fallback mode)."""
        return self._connected

    # ================================================================== #
    #  Low-level helpers (Redis vs in-memory)
    # ================================================================== #

    async def _lpush_trim(self, key: str, value: str, maxlen: int = _MAX_LIST_LEN) -> None:
        if self._connected:
            pipe = self._redis.pipeline()
            pipe.lpush(key, value)
            pipe.ltrim(key, 0, maxlen - 1)
            await pipe.execute()
        else:
            lst = self._mem_lists[key]
            lst.insert(0, value)
            del lst[maxlen:]

    async def _lrange(self, key: str, start: int, stop: int) -> list[str]:
        if self._connected:
            return await self._redis.lrange(key, start, stop)
        return self._mem_lists.get(key, [])[start : stop + 1]

    async def _zadd(self, key: str, score: float, member: str) -> None:
        if self._connected:
            await self._redis.zadd(key, {member: score})
        else:
            self._mem_zsets[key].append((score, member))

    async def _zrangebyscore(self, key: str, min_score: float, max_score: float) -> list[str]:
        if self._connected:
            return await self._redis.zrangebyscore(key, min_score, max_score)
        entries = self._mem_zsets.get(key, [])
        return [m for s, m in entries if min_score <= s <= max_score]

    async def _zrange_all(self, key: str) -> list[str]:
        if self._connected:
            return await self._redis.zrange(key, 0, -1)
        entries = self._mem_zsets.get(key, [])
        return [m for _, m in sorted(entries, key=lambda x: x[0])]

    async def _hset(self, key: str, field: str, value: str) -> None:
        if self._connected:
            await self._redis.hset(key, field, value)
        else:
            self._mem_hashes[key][field] = value

    async def _hget(self, key: str, field: str) -> str | None:
        if self._connected:
            return await self._redis.hget(key, field)
        return self._mem_hashes.get(key, {}).get(field)

    async def _hgetall(self, key: str) -> dict[str, str]:
        if self._connected:
            return await self._redis.hgetall(key)
        return dict(self._mem_hashes.get(key, {}))

    async def _set(self, key: str, value: str, ex: int | None = None) -> None:
        if self._connected:
            await self._redis.set(key, value, ex=ex)
        else:
            expire_ts = (_now_ts() + ex) if ex else None
            self._mem_strings[key] = (value, expire_ts)

    async def _get(self, key: str) -> str | None:
        if self._connected:
            return await self._redis.get(key)
        item = self._mem_strings.get(key)
        if item is None:
            return None
        value, expire_ts = item
        if expire_ts is not None and _now_ts() > expire_ts:
            del self._mem_strings[key]
            return None
        return value

    async def increment_counter(self, key_suffix: str) -> int:
        """Increment a counter in Redis, creating it if needed.

        The key is auto-prefixed with the store prefix.
        Returns the new count.
        """
        full_key = self._key(key_suffix)
        if self._connected:
            return await self._redis.incr(full_key)
        else:
            val_str, _ = self._mem_strings.get(full_key, ("0", None))
            new_val = int(val_str) + 1
            self._mem_strings[full_key] = (str(new_val), None)
            return new_val

    async def get_counter(self, key_suffix: str) -> int:
        """Get current value of a counter."""
        val = await self._get(self._key(key_suffix))
        return int(val) if val else 0

    async def _keys(self, pattern: str) -> list[str]:
        if self._connected:
            return await self._redis.keys(pattern)
        # Simple glob-style match for in-memory keys (supports trailing *)
        prefix = pattern.rstrip("*")
        all_keys: set[str] = set()
        for store in (self._mem_lists, self._mem_zsets, self._mem_hashes):
            all_keys.update(store.keys())
        all_keys.update(self._mem_strings.keys())
        return [k for k in all_keys if k.startswith(prefix)]

    # ================================================================== #
    #  Signals / Sim Trades
    # ================================================================== #

    async def record_signal(self, asset: str, signal: dict) -> None:
        """Record a trading signal for an asset.

        Signal dict should include keys like ``side``, ``price``, ``size``,
        ``reason``, ``timestamp``, ``quality``, ``regime``, etc.

        Key: ``futures:signals:{asset}`` (list, LPUSH + LTRIM to 1000).
        """
        signal.setdefault("timestamp", _now_ts())
        signal.setdefault("asset", asset)
        key = self._key("signals", asset)
        await self._lpush_trim(key, json.dumps(signal, default=str))
        if "id" in signal:
            idx_key = f"futures:signal:idx:{signal['id']}"
            await self._redis.setex(idx_key, 86400, asset)

    async def get_signals(self, asset: str, limit: int = 50) -> list[dict]:
        """Return the last *limit* signals for *asset*."""
        key = self._key("signals", asset)
        raw = await self._lrange(key, 0, limit - 1)
        return [json.loads(r) for r in raw]

    # ================================================================== #
    #  PnL
    # ================================================================== #

    async def record_pnl(
        self,
        asset: str,
        pnl_usdt: float,
        pnl_pct: float,
        trade_info: dict | None = None,
    ) -> None:
        """Append a PnL entry to the sorted set for *asset*.

        Key: ``futures:pnl:{asset}`` (sorted set, score = timestamp).
        """
        ts = _now_ts()
        entry: dict[str, Any] = {
            "asset": asset,
            "pnl_usdt": pnl_usdt,
            "pnl_pct": pnl_pct,
            "timestamp": ts,
            "date": _today_et(),
        }
        if trade_info:
            entry["trade"] = trade_info
        key = self._key("pnl", asset)
        await self._zadd(key, ts, json.dumps(entry, default=str))

    async def get_daily_pnl(self, asset: str | None = None) -> float:
        """Sum of PnL for today (midnight ET reset).

        If *asset* is ``None``, sums across all assets.
        """
        since = _midnight_et_ts()
        now = _now_ts()
        total = 0.0

        if asset is not None:
            key = self._key("pnl", asset)
            entries = await self._zrangebyscore(key, since, now)
            for raw in entries:
                total += json.loads(raw).get("pnl_usdt", 0.0)
        else:
            keys = await self._keys(self._key("pnl", "*"))
            for k in keys:
                if self._connected:
                    entries = await self._redis.zrangebyscore(k, since, now)
                else:
                    entries = [m for s, m in self._mem_zsets.get(k, []) if since <= s <= now]
                for raw in entries:
                    total += json.loads(raw).get("pnl_usdt", 0.0)

        return round(total, 4)

    async def get_pnl_history(self, asset: str | None = None, days: int = 7) -> list[dict]:
        """Return PnL entries for the last *days* days."""
        since = _days_ago_ts(days)
        now = _now_ts()
        results: list[dict] = []

        if asset is not None:
            key = self._key("pnl", asset)
            entries = await self._zrangebyscore(key, since, now)
            for raw in entries:
                results.append(json.loads(raw))
        else:
            keys = await self._keys(self._key("pnl", "*"))
            for k in keys:
                if self._connected:
                    entries = await self._redis.zrangebyscore(k, since, now)
                else:
                    entries = [m for s, m in self._mem_zsets.get(k, []) if since <= s <= now]
                for raw in entries:
                    results.append(json.loads(raw))

        results.sort(key=lambda e: e.get("timestamp", 0))
        return results

    async def get_aggregate_stats(self, days: int = 30) -> dict:
        """Get aggregate stats across all assets for reporting.

        Returns::

            {
                "total_pnl": float,
                "total_trades": int,
                "win_rate": float,  # 0..1
                "best_asset": str | None,
                "worst_asset": str | None,
                "daily_breakdown": [
                    {"date": str, "pnl": float, "trades": int, "win_rate": float},
                    ...,
                ],
                "per_asset": {asset: {"pnl": float, "trades": int, "win_rate": float}},
            }
        """
        entries = await self.get_pnl_history(asset=None, days=days)

        total_pnl = 0.0
        total_trades = 0
        wins = 0
        per_asset: dict[str, dict[str, Any]] = defaultdict(lambda: {"pnl": 0.0, "trades": 0, "wins": 0})
        daily: dict[str, dict[str, Any]] = defaultdict(lambda: {"pnl": 0.0, "trades": 0, "wins": 0})

        for e in entries:
            pnl = e.get("pnl_usdt", 0.0)
            asset_name = e.get("asset", "unknown")
            date_str = e.get("date", "unknown")

            total_pnl += pnl
            total_trades += 1
            if pnl > 0:
                wins += 1

            pa = per_asset[asset_name]
            pa["pnl"] += pnl
            pa["trades"] += 1
            if pnl > 0:
                pa["wins"] += 1

            d = daily[date_str]
            d["pnl"] += pnl
            d["trades"] += 1
            if pnl > 0:
                d["wins"] += 1

        # Best / worst asset
        best_asset: str | None = None
        worst_asset: str | None = None
        if per_asset:
            best_asset = max(per_asset, key=lambda a: per_asset[a]["pnl"])
            worst_asset = min(per_asset, key=lambda a: per_asset[a]["pnl"])

        # Build per-asset output (compute win_rate, drop internal 'wins')
        per_asset_out: dict[str, dict[str, Any]] = {}
        for a, v in per_asset.items():
            per_asset_out[a] = {
                "pnl": round(v["pnl"], 4),
                "trades": v["trades"],
                "win_rate": round(v["wins"] / v["trades"], 4) if v["trades"] else 0.0,
            }

        # Daily breakdown sorted by date
        daily_breakdown = sorted(
            [
                {
                    "date": d,
                    "pnl": round(v["pnl"], 4),
                    "trades": v["trades"],
                    "win_rate": round(v["wins"] / v["trades"], 4) if v["trades"] else 0.0,
                }
                for d, v in daily.items()
            ],
            key=lambda x: x["date"],
        )

        return {
            "total_pnl": round(total_pnl, 4),
            "total_trades": total_trades,
            "win_rate": round(wins / total_trades, 4) if total_trades else 0.0,
            "best_asset": best_asset,
            "worst_asset": worst_asset,
            "daily_breakdown": daily_breakdown,
            "per_asset": per_asset_out,
        }

    # ================================================================== #
    #  Order History
    # ================================================================== #

    async def record_order(self, asset: str, order: dict) -> None:
        """Push an order to the list for *asset* (LPUSH + LTRIM to 1000)."""
        order.setdefault("timestamp", _now_ts())
        order.setdefault("asset", asset)
        key = self._key("orders", asset)
        await self._lpush_trim(key, json.dumps(order, default=str))

    async def get_orders(self, asset: str, limit: int = 50) -> list[dict]:
        """Return the last *limit* orders for *asset*."""
        key = self._key("orders", asset)
        raw = await self._lrange(key, 0, limit - 1)
        return [json.loads(r) for r in raw]

    async def get_all_orders(self, limit: int = 200) -> list[dict]:
        """Return recent orders across all assets, sorted by time descending."""
        keys = await self._keys(self._key("orders", "*"))
        all_orders: list[dict] = []
        for k in keys:
            if self._connected:
                raw = await self._redis.lrange(k, 0, limit - 1)
            else:
                raw = self._mem_lists.get(k, [])[:limit]
            for r in raw:
                all_orders.append(json.loads(r))

        all_orders.sort(key=lambda o: o.get("timestamp", 0), reverse=True)
        return all_orders[:limit]

    # ================================================================== #
    #  Worker State
    # ================================================================== #

    async def save_worker_state(self, asset: str, state: dict) -> None:
        """Persist worker state as JSON in a hash field."""
        key = self._key("worker_state")
        await self._hset(key, asset, json.dumps(state, default=str))

    async def load_worker_state(self, asset: str) -> dict | None:
        """Load persisted worker state for *asset*."""
        key = self._key("worker_state")
        raw = await self._hget(key, asset)
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            logger.warning("Corrupt worker state for %s — ignoring", asset)
            return None

    # ================================================================== #
    #  Heartbeat
    # ================================================================== #

    async def heartbeat(self, asset: str, status: dict | None = None) -> None:
        """Update worker heartbeat with optional status dict.  TTL = 120 s."""
        data: dict[str, Any] = {
            "last_seen": _now_ts(),
            "asset": asset,
        }
        if status:
            data["status"] = status
        key = self._key("heartbeat", asset)
        await self._set(key, json.dumps(data, default=str), ex=_HEARTBEAT_TTL)

    async def clear_heartbeat(self, asset: str) -> None:
        """Delete the heartbeat key for an asset (e.g. one that has been disabled)."""
        key = self._key("heartbeat", asset)
        if self._connected:
            await self._redis.delete(key)
        else:
            self._mem_strings.pop(key, None)

    async def get_heartbeats(self) -> dict[str, dict]:
        """Return ``{asset: {last_seen, status, ...}}`` for all workers."""
        keys = await self._keys(self._key("heartbeat", "*"))
        result: dict[str, dict] = {}
        for k in keys:
            # Extract asset name from key: futures:heartbeat:BTCUSDT -> BTCUSDT
            asset = k.split(":")[-1]
            if self._connected:
                raw = await self._redis.get(k)
            else:
                raw_item = self._mem_strings.get(k)
                if raw_item is None:
                    continue
                value, expire_ts = raw_item
                if expire_ts is not None and _now_ts() > expire_ts:
                    del self._mem_strings[k]
                    continue
                raw = value
            if raw:
                try:
                    result[asset] = json.loads(raw)
                except (json.JSONDecodeError, TypeError):
                    pass
        return result

    # ================================================================== #
    #  Report Data
    # ================================================================== #

    async def get_report_data(self, period: str = "day") -> dict:
        """Gather all data needed for Grok report generation.

        Parameters
        ----------
        period:
            ``'day'``, ``'week'``, or ``'month'``.

        Returns a comprehensive dict with PnL, trades, signals, and
        per-asset breakdown.
        """
        days_map = {"day": 1, "week": 7, "month": 30}
        days = days_map.get(period, 1)

        stats = await self.get_aggregate_stats(days=days)
        heartbeats = await self.get_heartbeats()

        # Gather recent signals per asset
        per_asset_signals: dict[str, list[dict]] = {}
        signal_keys = await self._keys(self._key("signals", "*"))
        for k in signal_keys:
            asset = k.split(":")[-1]
            per_asset_signals[asset] = await self.get_signals(asset, limit=20)

        # Gather recent orders per asset
        all_orders = await self.get_all_orders(limit=100)

        return {
            "period": period,
            "days": days,
            "generated_at": _now_ts(),
            "date": _today_et(),
            "stats": stats,
            "heartbeats": heartbeats,
            "signals_by_asset": per_asset_signals,
            "recent_orders": all_orders,
        }

    # ================================================================== #
    #  UI Asset Overrides (enable/disable via dashboard)
    # ================================================================== #

    async def get_ui_disabled_assets(self) -> set[str]:
        """Return the set of asset keys disabled via the web UI.

        Key: ``futures:ui:disabled_assets``  (Redis set of asset key strings).
        Everything is enabled by default; only explicitly disabled keys appear here.
        """
        key = self._key("ui", "disabled_assets")
        if self._connected:
            members = await self._redis.smembers(key)
            return set(members)
        # In-memory fallback: store as a list in _mem_lists, deduplicated
        return set(self._mem_lists.get(key, []))

    async def toggle_ui_asset(self, asset_key: str) -> bool:
        """Toggle the disabled state of *asset_key* in the UI override set.

        Returns ``True`` if the asset is now **enabled** (was removed from the
        disabled set), ``False`` if it is now **disabled** (was added to the set).
        """
        key = self._key("ui", "disabled_assets")
        if self._connected:
            # SISMEMBER → SREM (if present) or SADD (if absent)
            is_disabled = await self._redis.sismember(key, asset_key)
            if is_disabled:
                await self._redis.srem(key, asset_key)
                return True  # now enabled
            else:
                await self._redis.sadd(key, asset_key)
                return False  # now disabled
        else:
            members = set(self._mem_lists.get(key, []))
            if asset_key in members:
                members.discard(asset_key)
                self._mem_lists[key] = list(members)
                return True
            else:
                members.add(asset_key)
                self._mem_lists[key] = list(members)
                return False

    async def list_report_dates(self, report_type: str) -> list[str]:
        """Return all stored dates for *report_type*, newest first.

        Scans keys matching ``futures:reports:{type}:*`` and excludes the
        ``latest`` pseudo-date pointer, returning ISO date strings sorted
        descending so the caller can render a date picker.
        """
        pattern = self._key("reports", report_type, "*")
        keys = await self._keys(pattern)
        dates: list[str] = []
        for k in keys:
            # Key format: futures:reports:{type}:{date}
            date_part = k.rsplit(":", 1)[-1]
            if date_part != "latest":
                dates.append(date_part)
        dates.sort(reverse=True)
        return dates

    async def get_report_by_date(self, report_type: str, date: str) -> str | None:
        """Retrieve a stored report for a specific ISO date string."""
        key = self._key("reports", report_type, date)
        return await self._get(key)

    async def store_report(self, report_type: str, content: str) -> None:
        """Store a generated report.

        Key: ``futures:reports:{type}:{date}``.
        Also maintains a ``futures:reports:{type}:latest`` pointer.
        """
        date_str = _today_et()
        key = self._key("reports", report_type, date_str)
        latest_key = self._key("reports", report_type, "latest")
        await self._set(key, content)
        await self._set(latest_key, content)

    async def get_latest_report(self, report_type: str) -> str | None:
        """Get the most recent report of a given type."""
        key = self._key("reports", report_type, "latest")
        return await self._get(key)

    # ================================================================== #
    #  Candle Cache
    # ================================================================== #

    async def cache_candles(self, asset: str, timeframe: str, candles_json: str, ttl: int = 300) -> None:
        """Cache candle data for *asset* / *timeframe* with a TTL (default 5 min)."""
        key = self._key("candles", asset, timeframe)
        await self._set(key, candles_json, ex=ttl)

    async def get_cached_candles(self, asset: str, timeframe: str) -> str | None:
        """Return cached candle JSON or ``None`` if expired / missing."""
        key = self._key("candles", asset, timeframe)
        return await self._get(key)

    # ================================================================== #
    #  Bot Control (start / stop workers from UI)
    # ================================================================== #

    async def get_bot_status(self) -> dict:
        """Return overall bot status from supervisor heartbeat."""
        key = self._key("supervisor", "status")
        raw = await self._get(key)
        if raw:
            try:
                return json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                pass
        return {"running": False, "workers": 0, "mode": "unknown"}

    async def set_bot_status(self, status: dict) -> None:
        """Store supervisor status dict (called by main.py supervisor loop)."""
        key = self._key("supervisor", "status")
        await self._set(key, json.dumps(status, default=str))

    async def request_worker_action(self, asset: str, action: str) -> None:
        """Queue a control action for a specific worker.

        Actions: 'stop', 'start', 'restart'
        The supervisor loop polls this and acts accordingly.
        """
        key = self._key("control", asset)
        data = {"action": action, "requested_at": _now_ts()}
        await self._set(key, json.dumps(data), ex=300)  # expires in 5 min

    async def get_worker_action(self, asset: str) -> dict | None:
        """Check if there's a pending control action for a worker."""
        key = self._key("control", asset)
        raw = await self._get(key)
        if raw:
            try:
                data = json.loads(raw)
                # Clear after reading (consume the command)
                if self._connected:
                    await self._redis.delete(key)
                else:
                    self._mem_strings.pop(key, None)
                return data
            except (json.JSONDecodeError, TypeError):
                pass
        return None

    # ================================================================== #
    #  Trade Export (CSV-ready structured data with fees)
    # ================================================================== #

    async def get_trades_for_export(
        self,
        days: int = 30,
        asset: str | None = None,
    ) -> list[dict]:
        """Return trade records suitable for CSV export.

        Each record includes:
          - timestamp, date, asset, side, entry_price, exit_price
          - size_lots, contract_size, notional_usdt
          - pnl_usdt, pnl_pct
          - maker_fee, taker_fee, total_fees, net_pnl
          - regime, quality, duration_sec
        """
        entries = await self.get_pnl_history(asset=asset, days=days)
        trades: list[dict] = []

        for e in entries:
            trade_info = e.get("trade", {})
            pnl_usdt = e.get("pnl_usdt", 0.0)

            # Fee extraction — stored in trade_info by the bot
            maker_fee = trade_info.get("maker_fee", 0.0)
            taker_fee = trade_info.get("taker_fee", 0.0)
            total_fees = trade_info.get("total_fees", maker_fee + taker_fee)
            net_pnl = pnl_usdt  # pnl_usdt already includes fees if recorded properly

            row = {
                "timestamp": e.get("timestamp", 0),
                "date": e.get("date", ""),
                "asset": e.get("asset", "unknown"),
                "side": trade_info.get("side") or trade_info.get("direction", ""),
                "entry_price": trade_info.get("entry_price") or trade_info.get("avg_entry", 0.0),
                "exit_price": trade_info.get("exit_price", 0.0),
                "size_lots": trade_info.get("size_lots") or trade_info.get("size", 0),
                "contract_size": trade_info.get("contract_size", 0.0),
                "notional_usdt": trade_info.get("notional_usdt", 0.0),
                "pnl_usdt": pnl_usdt,
                "pnl_pct": e.get("pnl_pct", 0.0),
                "maker_fee": maker_fee,
                "taker_fee": taker_fee,
                "total_fees": total_fees,
                "net_pnl": net_pnl,
                "regime": trade_info.get("regime", ""),
                "quality": trade_info.get("quality", 0),
                "duration_sec": trade_info.get("duration_sec", 0),
                "entry_type": trade_info.get("entry_type", ""),
                "exit_type": trade_info.get("exit_type", ""),
            }
            trades.append(row)

        trades.sort(key=lambda t: t.get("timestamp", 0), reverse=True)
        return trades

    async def get_fee_summary(self, days: int = 30) -> dict:
        """Aggregate fee statistics across all trades.

        Returns:
            {
                "total_fees": float,
                "total_maker_fees": float,
                "total_taker_fees": float,
                "avg_fee_per_trade": float,
                "fee_pct_of_pnl": float,
                "total_trades": int,
                "total_gross_pnl": float,
                "total_net_pnl": float,
                "per_asset": {asset: {"fees": float, "trades": int}},
            }
        """
        trades = await self.get_trades_for_export(days=days)

        total_fees = 0.0
        total_maker = 0.0
        total_taker = 0.0
        total_gross = 0.0
        total_net = 0.0
        per_asset: dict[str, dict] = defaultdict(lambda: {"fees": 0.0, "trades": 0})

        for t in trades:
            f = t.get("total_fees", 0.0)
            total_fees += f
            total_maker += t.get("maker_fee", 0.0)
            total_taker += t.get("taker_fee", 0.0)
            total_gross += t.get("pnl_usdt", 0.0) + f  # gross = net + fees
            total_net += t.get("net_pnl", 0.0)

            asset_name = t.get("asset", "unknown")
            pa = per_asset[asset_name]
            pa["fees"] += f
            pa["trades"] += 1

        n = len(trades)
        return {
            "total_fees": round(total_fees, 6),
            "total_maker_fees": round(total_maker, 6),
            "total_taker_fees": round(total_taker, 6),
            "avg_fee_per_trade": round(total_fees / n, 6) if n else 0.0,
            "fee_pct_of_pnl": round(abs(total_fees / total_net) * 100, 2) if total_net else 0.0,
            "total_trades": n,
            "total_gross_pnl": round(total_gross, 6),
            "total_net_pnl": round(total_net, 6),
            "per_asset": dict(per_asset),
        }

    # ================================================================== #
    #  Gate Stats (for dashboard / Discord summary)
    # ================================================================== #

    async def get_gate_stats_all(self) -> dict[str, dict[str, int]]:
        """Get gate block statistics for all assets.

        Returns ``{asset_key: {reason: count, "total_evals": N}}``.
        """
        from services.execution_gate import GateVerdict

        # Discover assets that have gate evaluations
        eval_keys = await self._keys(self._key("gate_evals:*"))
        result: dict[str, dict[str, int]] = {}

        for eval_key in eval_keys:
            asset = eval_key.split(":")[-1]
            stats: dict[str, int] = {}

            # Total evaluations
            evals = await self.get_counter(f"gate_evals:{asset}")
            if evals > 0:
                stats["total_evals"] = evals

            # Per-reason block counts
            for verdict in GateVerdict:
                if verdict == GateVerdict.PASS:
                    continue
                count = await self.get_counter(f"gate_blocks:{asset}:{verdict.name.lower()}")
                if count > 0:
                    stats[verdict.name] = count

            if stats:
                result[asset] = stats

        return result

    # ================================================================== #
    #  Regime Distribution Tracking
    # ================================================================== #

    async def record_regime_tick(self, asset: str, regime: str) -> None:
        """Increment the regime counter for an asset.

        Called each heartbeat with the current regime. Uses daily-scoped
        Redis keys so distribution resets each day.

        Key: ``futures:regime_dist:{date}:{asset}:{regime}``
        """
        date = _today_et()
        await self.increment_counter(f"regime_dist:{date}:{asset}:{regime.lower()}")

    async def get_regime_distribution(
        self, asset: str | None = None, date: str | None = None
    ) -> dict[str, dict[str, int]]:
        """Get regime distribution for today (or a specific date).

        Returns ``{asset: {"trending_up": N, "volatile": M, ...}}``.
        If *asset* is given, returns only that asset's distribution.
        """
        if date is None:
            date = _today_et()

        pattern = self._key(f"regime_dist:{date}:*")
        keys = await self._keys(pattern)
        result: dict[str, dict[str, int]] = {}

        for key in keys:
            # Key format: futures:regime_dist:2026-04-01:btcusdt:trending_up
            parts = key.split(":")
            if len(parts) < 5:
                continue
            key_asset = parts[-2]
            key_regime = parts[-1]

            if asset and key_asset != asset:
                continue

            count = await self.get_counter(f"regime_dist:{date}:{key_asset}:{key_regime}")
            if count > 0:
                if key_asset not in result:
                    result[key_asset] = {}
                result[key_asset][key_regime] = count

        return result

    async def _get_signal_index_key(self, signal_id: str) -> str | None:
        """Look up which asset list contains a signal by ID.

        Signals are stored as JSON in per-asset lists:
            futures:signals:{asset}  → list of JSON dicts, each has an 'id' field

        We maintain a secondary index:
            futures:signal:idx:{signal_id}  → asset key  (TTL 24h)

        This gives us O(1) lookup instead of scanning all asset lists.
        """
        idx_key = f"futures:signal:idx:{signal_id}"
        asset = await self._redis.get(idx_key)
        if asset:
            return asset.decode() if isinstance(asset, bytes) else asset
        # Fallback: scan all asset signal lists (slow but safe)
        heartbeats = await self.get_heartbeats()
        for a in heartbeats:
            sigs = await self.get_signals(a, limit=500)
            for sig in sigs:
                if str(sig.get("id", "")) == signal_id:
                    # Backfill the index
                    await self._redis.setex(idx_key, 86400, a)
                    return a
        return None

    async def update_signal_status(self, signal_id: str, status: str) -> bool:
        """Update the status field of a signal in-place.

        Args:
            signal_id: The signal's UUID string.
            status:    New status — 'approved' | 'rejected' | 'staging'.

        Returns:
            True if the signal was found and updated, False otherwise.
        """
        asset = await self._get_signal_index_key(signal_id)
        if not asset:
            return False

        list_key = f"futures:signals:{asset}"
        raw_list = await self._redis.lrange(list_key, 0, -1)

        updated: list[bytes] = []
        found = False
        for item in raw_list:
            try:
                sig = json.loads(item)
                if str(sig.get("id", "")) == signal_id:
                    sig["status"] = status
                    sig["status_updated_at"] = time.time()
                    updated.append(json.dumps(sig).encode())
                    found = True
                else:
                    updated.append(item)
            except (json.JSONDecodeError, TypeError):
                updated.append(item)

        if found and updated:
            pipe = self._redis.pipeline()
            pipe.delete(list_key)
            for item in updated:
                pipe.rpush(list_key, item)
            await pipe.execute()

        return found

    _ALERTS_KEY = "futures:alerts"
    _ALERTS_MAX = 100  # keep last 100 alerts

    async def push_alert(
        self,
        title: str,
        message: str,
        severity: str = "warning",
        source: str = "",
    ) -> None:
        """Push a system alert into the alerts ring buffer.

        Call this from the supervisor on:
        - Circuit breaker trips
        - Risk threshold breaches
        - Worker crashes
        - ADL / liquidation warnings

        Args:
            title:    Short alert title shown in the UI header.
            message:  Full alert message.
            severity: 'error' | 'warning' | 'info'
            source:   Origin component (e.g. 'circuit_breaker', 'risk_engine')
        """
        alert = {
            "id": f"alert-{int(time.time() * 1000)}",
            "title": title,
            "message": message,
            "severity": severity,
            "source": source,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        pipe = self._redis.pipeline()
        pipe.rpush(self._ALERTS_KEY, json.dumps(alert))
        pipe.ltrim(self._ALERTS_KEY, -self._ALERTS_MAX, -1)
        pipe.expire(self._ALERTS_KEY, 86400 * 7)  # 7-day TTL
        await pipe.execute()

    async def get_alerts(self, limit: int = 20) -> list[dict]:
        """Return the most recent system alerts (newest first).

        Args:
            limit: Maximum number of alerts to return.

        Returns:
            List of alert dicts with keys: id, title, message, severity, timestamp.
        """
        raw = await self._redis.lrange(self._ALERTS_KEY, -limit, -1)
        alerts = []
        for item in reversed(raw):  # newest first
            try:
                alerts.append(json.loads(item))
            except (json.JSONDecodeError, TypeError):
                pass
        return alerts
