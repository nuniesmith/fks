// Additional FKS Setups based on Top G Indicator and NSDT Pivot concepts
// These can be integrated into your main strategy

#region Additional Setup Methods

// SETUP 5: Pivot Zone Reversal (Based on NSDT Pivot Zones concept)
private bool CheckSetup5_PivotZoneReversal()
{
    // Calculate pivot-like levels using your existing support/resistance
    double pivotPoint = (High[1] + Low[1] + Close[1]) / 3;
    double r1 = (2 * pivotPoint) - Low[1];
    double s1 = (2 * pivotPoint) - High[1];
    
    bool atPivotSupport = Math.Abs(Close[0] - s1) <= atr[0] * 0.3;
    bool atPivotResistance = Math.Abs(Close[0] - r1) <= atr[0] * 0.3;
    
    // Long setup at pivot support
    if (atPivotSupport && Close[0] > Open[0] && aoValue > aoPrevValue &&
        volume[0] > volumeAvg[0] * VolumeThreshold)
    {
        currentSignal = "G";
        signalQuality = CalculateSignalQuality(true) * 0.92;
        activeSetup = 5;
        return true;
    }
    
    // Short setup at pivot resistance
    if (atPivotResistance && Close[0] < Open[0] && aoValue < aoPrevValue &&
        volume[0] > volumeAvg[0] * VolumeThreshold &&
        IsShortSafeToTrade())
    {
        currentSignal = "Top";
        signalQuality = CalculateSignalQuality(false) * 0.92;
        activeSetup = 5;
        return true;
    }
    
    return false;
}

// SETUP 6: Manipulation Candle Setup (Based on the Gold trading hack article)
private bool CheckSetup6_ManipulationCandle()
{
    if (CurrentBar < 3) return false;
    
    // Bullish Manipulation Candle
    // Price dips below previous low, then closes above previous high
    bool bullishMC = Low[0] < Low[1] && Close[0] > High[1] && Close[0] > Open[0];
    
    // Bearish Manipulation Candle  
    // Price spikes above previous high, then closes below previous low
    bool bearishMC = High[0] > High[1] && Close[0] < Low[1] && Close[0] < Open[0];
    
    // Additional confirmation requirements
    bool strongVolume = volume[0] > volumeAvg[0] * VolumeThreshold * 1.4;
    bool nearKeyLevel = Math.Abs(Close[0] - nearestSupport) <= atr[0] * 0.4 ||
                       Math.Abs(Close[0] - nearestResistance) <= atr[0] * 0.4;
    
    if (bullishMC && strongVolume && nearKeyLevel)
    {
        currentSignal = "G";
        signalQuality = CalculateSignalQuality(true) * 1.05; // Bonus for manipulation setup
        activeSetup = 6;
        return true;
    }
    
    if (bearishMC && strongVolume && nearKeyLevel && IsShortSafeToTrade())
    {
        currentSignal = "Top";
        signalQuality = CalculateSignalQuality(false) * 1.05;
        activeSetup = 6;
        return true;
    }
    
    return false;
}

// SETUP 7: Volume Price Analysis (VPA) Setup
private bool CheckSetup7_VPA()
{
    if (CurrentBar < 5) return false;
    
    // Calculate volume characteristics
    double avgVolume5 = (volume[0] + volume[1] + volume[2] + volume[3] + volume[4]) / 5;
    double currentVolumeRatio = volume[0] / avgVolume5;
    
    // High volume with narrow spread (accumulation/distribution)
    double spread = High[0] - Low[0];
    double avgSpread = (Math.Abs(High[0] - Low[0]) + Math.Abs(High[1] - Low[1]) + 
                      Math.Abs(High[2] - Low[2])) / 3;
    
    bool highVolumeNarrowSpread = currentVolumeRatio > 2.0 && spread < avgSpread * 0.7;
    bool closingStrong = Close[0] > (High[0] + Low[0]) / 2; // Close in upper half
    bool closingWeak = Close[0] < (High[0] + Low[0]) / 2;   // Close in lower half
    
    // Bullish VPA
    if (highVolumeNarrowSpread && closingStrong && Close[0] > ema9[0])
    {
        currentSignal = "G";
        signalQuality = CalculateSignalQuality(true) * 0.88;
        activeSetup = 7;
        return true;
    }
    
    // Bearish VPA
    if (highVolumeNarrowSpread && closingWeak && Close[0] < ema9[0] && IsShortSafeToTrade())
    {
        currentSignal = "Top";
        signalQuality = CalculateSignalQuality(false) * 0.88;
        activeSetup = 7;
        return true;
    }
    
    return false;
}

// SETUP 8: Multi-Timeframe Momentum Alignment
private bool CheckSetup8_MomentumAlignment()
{
    if (BarsArray[1].Count < 3) return false;
    
    // Check momentum alignment across timeframes
    bool primaryBullish = Close[0] > ema9[0] && aoValue > 0;
    bool primaryBearish = Close[0] < ema9[0] && aoValue < 0;
    
    bool higherTFBullish = Closes[1][0] > ema9_HT[0] && aoValue_HT > 0;
    bool higherTFBearish = Closes[1][0] < ema9_HT[0] && aoValue_HT < 0;
    
    // Look for momentum acceleration
    bool momentumAccelerating = false;
    if (primaryBullish && higherTFBullish)
    {
        momentumAccelerating = aoValue > aoPrevValue && aoValue_HT > aoPrevValue_HT;
    }
    else if (primaryBearish && higherTFBearish)
    {
        momentumAccelerating = aoValue < aoPrevValue && aoValue_HT < aoPrevValue_HT;
    }
    
    // Strong volume confirmation
    bool volumeExpansion = volume[0] > volumeAvg[0] * VolumeThreshold * 1.5;
    
    if (primaryBullish && higherTFBullish && momentumAccelerating && volumeExpansion)
    {
        currentSignal = "G";
        signalQuality = CalculateSignalQuality(true) * 1.08; // High quality setup
        activeSetup = 8;
        return true;
    }
    
    if (primaryBearish && higherTFBearish && momentumAccelerating && volumeExpansion && IsShortSafeToTrade())
    {
        currentSignal = "Top";
        signalQuality = CalculateSignalQuality(false) * 1.08;
        activeSetup = 8;
        return true;
    }
    
    return false;
}

// SETUP 9: Gap Fill Strategy (for futures that gap)
private bool CheckSetup9_GapFill()
{
    if (CurrentBar < 2) return false;
    
    // Detect gap (difference between previous close and current open)
    double gapSize = Math.Abs(Open[0] - Close[1]);
    double minGapSize = atr[0] * 0.5; // Minimum gap size to consider
    
    if (gapSize < minGapSize) return false;
    
    bool isGapUp = Open[0] > Close[1] + minGapSize;
    bool isGapDown = Open[0] < Close[1] - minGapSize;
    
    // Look for gap fill opportunity
    bool gapFillLong = isGapDown && Close[0] > Open[0] && 
                      Close[0] > (Open[0] + Close[1]) / 2; // Moving toward gap fill
    
    bool gapFillShort = isGapUp && Close[0] < Open[0] && 
                       Close[0] < (Open[0] + Close[1]) / 2; // Moving toward gap fill
    
    if (gapFillLong && volume[0] > volumeAvg[0] * VolumeThreshold)
    {
        currentSignal = "G";
        signalQuality = CalculateSignalQuality(true) * 0.85; // Lower quality as it's mean reversion
        activeSetup = 9;
        return true;
    }
    
    if (gapFillShort && volume[0] > volumeAvg[0] * VolumeThreshold && IsShortSafeToTrade())
    {
        currentSignal = "Top";
        signalQuality = CalculateSignalQuality(false) * 0.85;
        activeSetup = 9;
        return true;
    }
    
    return false;
}

// SETUP 10: Breakout Retest Setup
private bool CheckSetup10_BreakoutRetest()
{
    if (CurrentBar < 20) return false;
    
    // Look for recent breakout in the last 10 bars
    bool recentBreakoutUp = false;
    bool recentBreakoutDown = false;
    double breakoutLevel = 0;
    
    for (int i = 1; i <= 10; i++)
    {
        if (Close[i] > nearestResistance && Close[i-1] <= nearestResistance)
        {
            recentBreakoutUp = true;
            breakoutLevel = nearestResistance;
            break;
        }
        if (Close[i] < nearestSupport && Close[i-1] >= nearestSupport)
        {
            recentBreakoutDown = true;
            breakoutLevel = nearestSupport;
            break;
        }
    }
    
    // Now look for retest of breakout level
    if (recentBreakoutUp && Math.Abs(Close[0] - breakoutLevel) <= atr[0] * 0.4 &&
        Close[0] > breakoutLevel && Close[0] > Open[0])
    {
        currentSignal = "G";
        signalQuality = CalculateSignalQuality(true) * 0.90;
        activeSetup = 10;
        return true;
    }
    
    if (recentBreakoutDown && Math.Abs(Close[0] - breakoutLevel) <= atr[0] * 0.4 &&
        Close[0] < breakoutLevel && Close[0] < Open[0] && IsShortSafeToTrade())
    {
        currentSignal = "Top";
        signalQuality = CalculateSignalQuality(false) * 0.90;
        activeSetup = 10;
        return true;
    }
    
    return false;
}

// Enhanced GenerateSignal method to include all setups
private void GenerateEnhancedSignalWithAllSetups()
{
    currentSignal = "";
    signalQuality = 0;
    activeSetup = 0;
    
    // Check higher timeframe confirmation first
    if (UseHigherTimeframeConfirmation && BarsArray[1].Count > 0)
    {
        higherTimeframeConfirmed = CheckHigherTimeframeConfirmation();
        if (!higherTimeframeConfirmed) return;
    }
    else
    {
        higherTimeframeConfirmed = true;
    }
    
    // Check all setups in priority order (highest quality first)
    if (CheckSetup8_MomentumAlignment()) return;      // Highest quality
    if (CheckSetup6_ManipulationCandle()) return;     // High quality
    if (CheckSetup1_EMAVWAPBreakout()) return;        // Your original setups
    if (CheckSetup2_EMAVWAPBreakdown()) return;
    if (CheckSetup5_PivotZoneReversal()) return;
    if (CheckSetup3_VWAPRejection()) return;
    if (CheckSetup4_SupportResistanceAO()) return;
    if (CheckSetup10_BreakoutRetest()) return;
    if (CheckSetup7_VPA()) return;
    if (CheckSetup9_GapFill()) return;               // Lowest priority
}

#endregion

// Add this to your main strategy's CheckForSignals method:
// Replace GenerateSignal() with GenerateEnhancedSignalWithAllSetups()
