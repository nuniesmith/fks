// Add these methods to your FKSStrategyAIO class

private void GenerateSignal()
{
    currentSignal = "";
    signalQuality = 0;
    
    // Heiken Ashi specific handling
    if (BarsPeriod.BarsPeriodType == BarsPeriodType.HeikenAshi)
    {
        GenerateHeikenAshiSignal();
    }
    else
    {
        GenerateStandardSignal();
    }
}

private void GenerateHeikenAshiSignal()
{
    // For Heiken Ashi, we need to be more selective due to smoothing
    // Increase quality requirements and look for stronger patterns
    
    // Calculate HA pattern strength
    double haBodySize = Math.Abs(Close[0] - Open[0]);
    double haUpperWick = High[0] - Math.Max(Close[0], Open[0]);
    double haLowerWick = Math.Min(Close[0], Open[0]) - Low[0];
    
    // Strong bullish HA candle: no upper wick, large body
    bool strongBullishHA = Close[0] > Open[0] && 
                          haUpperWick < haBodySize * 0.1 && 
                          haBodySize > atr[0] * 0.5;
    
    // Strong bearish HA candle: no lower wick, large body
    bool strongBearishHA = Close[0] < Open[0] && 
                          haLowerWick < haBodySize * 0.1 && 
                          haBodySize > atr[0] * 0.5;
    
    // SETUP 1: EMA9 + VWAP Bullish Breakout (HA Enhanced)
    if (Close[0] > ema9[0] && ema9[0] > sma20[0] && strongBullishHA &&
        Low[0] <= nearestSupport * 1.001 && Close[0] > nearestSupport && 
        volume[0] > volumeAvg[0] * VolumeThreshold * VolumeMultiplier * 1.2) // Higher volume requirement
    {
        currentSignal = "G";
        signalQuality = CalculateSignalQuality(true) * SignalQualityMultiplier * 1.1; // Boost for strong HA
        activeSetup = 1;
    }
    // SETUP 2: EMA9 + VWAP Bearish Breakdown (HA Enhanced)
    else if (Close[0] < ema9[0] && ema9[0] < sma20[0] && strongBearishHA &&
             High[0] >= nearestResistance * 0.999 && Close[0] < nearestResistance && 
             volume[0] > volumeAvg[0] * VolumeThreshold * VolumeMultiplier * 1.2)
    {
        currentSignal = "Top";
        signalQuality = CalculateSignalQuality(false) * SignalQualityMultiplier * 1.1;
        activeSetup = 2;
    }
    // SETUP 3: VWAP Rejection with HA Confirmation
    else if (Math.Abs(Low[0] - sma20[0]) <= atr[0] * 0.5 && strongBullishHA && 
             Close[0] > sma20[0])
    {
        // Check for HA trend change (previous candles were bearish)
        bool trendChange = CurrentBar > 2 && Close[1] < Open[1] && Close[2] < Open[2];
        if (trendChange)
        {
            currentSignal = "G";
            signalQuality = CalculateSignalQuality(true) * SignalQualityMultiplier;
            activeSetup = 3;
        }
    }
    else if (Math.Abs(High[0] - sma20[0]) <= atr[0] * 0.5 && strongBearishHA && 
             Close[0] < sma20[0])
    {
        // Check for HA trend change (previous candles were bullish)
        bool trendChange = CurrentBar > 2 && Close[1] > Open[1] && Close[2] > Open[2];
        if (trendChange)
        {
            currentSignal = "Top";
            signalQuality = CalculateSignalQuality(false) * SignalQualityMultiplier;
            activeSetup = 3;
        }
    }
    // SETUP 4: S/R + AO with HA Pattern Recognition
    else if (Low[0] <= nearestSupport * 1.002 && strongBullishHA &&
             aoValue > 0.001 && aoPrevValue <= 0)
    {
        // Look for HA doji patterns at support (indecision before reversal)
        bool haDojiPattern = CurrentBar > 0 && 
                           Math.Abs(Close[1] - Open[1]) < atr[0] * 0.1;
        
        currentSignal = "G";
        signalQuality = CalculateSignalQuality(true) * SignalQualityMultiplier * 
                       (haDojiPattern ? 1.15 : 0.9);
        activeSetup = 4;
    }
    else if (High[0] >= nearestResistance * 0.998 && strongBearishHA &&
             aoValue < -0.001 && aoPrevValue >= 0)
    {
        // Look for HA doji patterns at resistance
        bool haDojiPattern = CurrentBar > 0 && 
                           Math.Abs(Close[1] - Open[1]) < atr[0] * 0.1;
        
        currentSignal = "Top";
        signalQuality = CalculateSignalQuality(false) * SignalQualityMultiplier * 
                       (haDojiPattern ? 1.15 : 0.9);
        activeSetup = 4;
    }
    
    // For Heiken Ashi, reduce quality of minor signals
    if (currentSignal == "")
    {
        if (Low[0] > nearestSupport && Low[0] < nearestSupport * 1.02 && strongBullishHA)
        {
            currentSignal = "^";
            signalQuality = CalculateSignalQuality(true) * 0.6 * SignalQualityMultiplier; // Lower quality
            activeSetup = 0;
        }
        else if (High[0] < nearestResistance && High[0] > nearestResistance * 0.98 && strongBearishHA)
        {
            currentSignal = "v";
            signalQuality = CalculateSignalQuality(false) * 0.6 * SignalQualityMultiplier; // Lower quality
            activeSetup = 0;
        }
    }
}

// Enhanced exit management for Heiken Ashi
private void ManageHeikenAshiLongPosition()
{
    // Heiken Ashi exit signals are more reliable when multiple candles confirm
    int bearishCount = 0;
    for (int i = 0; i < Math.Min(3, CurrentBar); i++)
    {
        if (Close[i] < Open[i]) bearishCount++;
    }
    
    // Exit on strong bearish HA pattern
    if (bearishCount >= 2 && Close[0] < Open[0] && 
        Math.Abs(Close[0] - Open[0]) > atr[0] * 0.5)
    {
        ExitLong("HA Bearish Pattern");
        return;
    }
    
    // Standard management continues...
    ManageStandardLongPosition();
}

private void ManageHeikenAshiShortPosition()
{
    // Count bullish candles
    int bullishCount = 0;
    for (int i = 0; i < Math.Min(3, CurrentBar); i++)
    {
        if (Close[i] > Open[i]) bullishCount++;
    }
    
    // Exit on strong bullish HA pattern
    if (bullishCount >= 2 && Close[0] > Open[0] && 
        Math.Abs(Close[0] - Open[0]) > atr[0] * 0.5)
    {
        ExitShort("HA Bullish Pattern");
        return;
    }
    
    // Standard management continues...
    ManageStandardShortPosition();
}