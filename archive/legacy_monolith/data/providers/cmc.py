"""CoinMarketCap provider extraction module."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Dict


def cmc_quotes(
    requester: Callable[[str, dict[str, Any], dict[str, str]], dict[str, Any]],
    symbol: str,
) -> dict[str, Any]:
    url = "https://pro-api.coinmarketcap.com/v2/fkscurrency/quotes/latest"
    params = {"symbol": symbol}
    headers: dict[str, str] = {}
    data = requester(url, params, headers)
    return {"raw": data}
