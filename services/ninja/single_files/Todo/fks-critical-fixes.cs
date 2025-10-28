// CRITICAL FIX 1: Update ManagePosition to handle Heiken Ashi
private void ManagePosition()
{
    if (BarsPeriod.BarsPeriodType == BarsPeriodType.HeikenAshi)
    {
        if (Position.MarketPosition == MarketPosition.Long)
            ManageHeikenAshiLongPosition();
        else if (Position.MarketPosition == MarketPosition.Short)
            ManageHeikenAshiShortPosition();
    }
    else
    {
        if (Position.MarketPosition == MarketPosition.Long)
            ManageStandardLongPosition();
        else if (Position.MarketPosition == MarketPosition.Short)
            ManageStandardShortPosition();
    }
}

// CRITICAL FIX 2: Fix duplicate signal generation in GenerateStandardSignal()
// Remove the duplicate "v" signal at the end of the method (lines ~430)

// CRITICAL FIX 3: Add market-specific position sizing
private int CalculatePositionSize()
{
    int contracts = BaseContracts;
    
    // Get the base contract calculation (existing code)
    // ... your existing tier calculations ...
    
    // NEW: Market-specific adjustments
    string instrument = Instrument.MasterInstrument.Name;
    
    switch (instrument)
    {
        case "GC": // Gold - stable, can use full size
            // No adjustment needed
            break;
            
        case "NQ": // Nasdaq - volatile, reduce size
            contracts = Math.Max(1, (contracts * 3) / 4);
            break;
            
        case "CL": // Crude Oil - very volatile
            contracts = Math.Max(1, contracts / 2);
            // Extra reduction for inventory days (Wednesday 10:30 AM)
            if (Time[0].DayOfWeek == DayOfWeek.Wednesday && 
                Time[0].Hour == 10 && Time[0].Minute >= 20 && Time[0].Minute <= 40)
            {
                contracts = 1; // Minimum size around EIA
            }
            break;
            
        case "BTC": // Bitcoin - extreme volatility
            contracts = Math.Max(1, contracts / 2);
            // Reduce further on weekends
            if (Time[0].DayOfWeek == DayOfWeek.Saturday || 
                Time[0].DayOfWeek == DayOfWeek.Sunday)
            {
                contracts = 1;
            }
            break;
            
        case "ES": // S&P 500 - moderate volatility
            // No adjustment needed
            break;
    }
    
    // Continue with existing adjustments...
    // (consecutive losses, soft limits, etc.)
    
    return Math.Min(contracts, MaxContracts);
}

// CRITICAL FIX 4: Improve time-based exit for overnight positions
protected override void OnBarUpdate()
{
    if (CurrentBar < BarsRequiredToTrade) return;
    
    // NEW: Force close positions outside trading hours
    if (Position.MarketPosition != MarketPosition.Flat)
    {
        int currentHour = Time[0].Hour;
        bool outsideTradingHours = currentHour < StartHour || currentHour >= EndHour;
        
        if (outsideTradingHours && !DisableTimeFilter)
        {
            if (Position.MarketPosition == MarketPosition.Long)
            {
                ExitLong("Outside Hours Exit");
                if (ShowDebugInfo)
                    Print($"Exiting LONG - Outside trading hours ({currentHour}:00)");
            }
            else if (Position.MarketPosition == MarketPosition.Short)
            {
                ExitShort("Outside Hours Exit");
                if (ShowDebugInfo)
                    Print($"Exiting SHORT - Outside trading hours ({currentHour}:00)");
            }
            return;
        }
    }
    
    // Continue with existing OnBarUpdate logic...
}

// CRITICAL FIX 5: Add session-based volatility adjustment
private double GetSessionVolatilityMultiplier()
{
    int hour = Time[0].Hour;
    string instrument = Instrument.MasterInstrument.Name;
    
    // London Open (3-5 AM EST) - Highest volatility for forex/commodities
    if (hour >= 3 && hour < 5)
    {
        if (instrument == "GC" || instrument == "CL")
            return 1.3; // Higher volatility expected
        return 1.1;
    }
    // London/NY Overlap (8-10 AM EST) - High volatility for all
    else if (hour >= 8 && hour < 10)
    {
        return 1.2;
    }
    // US Lunch (12-14 PM EST) - Lower volatility
    else if (hour >= 12 && hour < 14)
    {
        return 0.7;
    }
    // Normal hours
    else
    {
        return 1.0;
    }
}

// CRITICAL FIX 6: Better signal quality calculation for HA
private double CalculateSignalQuality(bool isBullish)
{
    double quality = 0.4; // Base quality
    
    // For Heiken Ashi, add pattern recognition bonus
    if (BarsPeriod.BarsPeriodType == BarsPeriodType.HeikenAshi)
    {
        // Check for consecutive same-color candles (trend strength)
        int sameColorCount = 0;
        for (int i = 0; i < Math.Min(5, CurrentBar); i++)
        {
            if ((isBullish && Close[i] > Open[i]) || 
                (!isBullish && Close[i] < Open[i]))
                sameColorCount++;
            else
                break;
        }
        
        // Bonus for trend consistency
        quality += (sameColorCount * 0.05); // Up to 0.25 bonus
    }
    
    // Continue with your existing quality calculation...
    // (trend alignment, AO momentum, volume, etc.)
    
    return Math.Min(1.0, quality);
}