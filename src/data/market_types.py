from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class MarketBar(BaseModel):
    ts: int = Field(ge=0)
    open: float
    high: float
    low: float
    close: float
    volume: float = Field(ge=0)
    provider: str | None = None

    @property
    def ohlc_tuple(self) -> tuple[float, float, float, float]:
        return (self.open, self.high, self.low, self.close)


__all__ = ["MarketBar"]
