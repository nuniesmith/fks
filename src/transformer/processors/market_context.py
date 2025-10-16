from typing import Dict, List

import pandas as pd


class MarketContextEnhancer:
    def __init__(self, config: dict):
        self.config = config
        self.context_window = config.get("context_window", 20)

    async def enhance_data(self, market_data: pd.DataFrame):
        """Enhance market data with contextual features"""
        enhanced = market_data.copy()

        # Add market regime
        enhanced["market_regime"] = await self._detect_market_regime(market_data)

        # Add volatility regime
        enhanced["volatility_regime"] = await self._detect_volatility_regime(
            market_data
        )

        # Add correlation features
        enhanced = await self._add_correlation_features(enhanced)

        # Add microstructure features
        enhanced = await self._add_microstructure_features(enhanced)

        return enhanced

    async def _detect_market_regime(self, data: pd.DataFrame):
        """Detect current market regime"""
        # Calculate rolling statistics
        returns = data["close"].pct_change()

        # Bull/Bear detection
        sma_20 = data["close"].rolling(20).mean()
        sma_50 = data["close"].rolling(50).mean()

        regime = pd.Series(index=data.index, dtype="object")
        regime[sma_20 > sma_50] = "bull"
        regime[sma_20 <= sma_50] = "bear"

        # Trending vs ranging
        atr = await self._calculate_atr(data)
        trend_strength = abs(returns.rolling(20).mean()) / atr

        regime[trend_strength < 0.5] = regime + "_ranging"
        regime[trend_strength >= 0.5] = regime + "_trending"

        return regime
