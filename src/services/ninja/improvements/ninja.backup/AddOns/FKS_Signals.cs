// src/AddOns/FKS_Signals.cs - Unified Signal Generation and Coordination System
// Dependencies: FKS_Core.cs, FKS_Calculations.cs

#region Using declarations
using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading;
using NinjaTrader.NinjaScript;
#endregion

namespace NinjaTrader.NinjaScript.AddOns
{
    #region Signal Generation Engine (400 lines)

    /// <summary>
    /// Advanced signal generation with bulletproof filtering and setup detection
    /// Consolidates and enhances signal generation logic
    /// </summary>
    public static class FKS_SignalGenerator
    {
        #region Market Condition Detection

        /// <summary>
        /// Market condition classification for signal filtering
        /// </summary>
        public enum MarketCondition
        {
            Trending,
            Ranging,
            HighVolatility,
            LowVolatility,
            NewsEvent,
            Uncertain
        }

        /// <summary>
        /// Detect current market condition based on ADX and ATR
        /// </summary>
        public static MarketCondition DetectMarketCondition(NinjaScriptBase script, double adx, double currentATR, double avgATR)
        {
            try
            {
                // Calculate ATR volatility ratio
                double atrRatio = avgATR > 0 ? currentATR / avgATR : 1.0;

                // Determine market condition with enhanced logic
                if (atrRatio > 2.0) return MarketCondition.NewsEvent;
                if (atrRatio > 1.5) return MarketCondition.HighVolatility;
                if (atrRatio < 0.6) return MarketCondition.LowVolatility;
                if (adx > 30) return MarketCondition.Trending;
                if (adx < 18) return MarketCondition.Ranging;

                return MarketCondition.Uncertain;
            }
            catch
            {
                return MarketCondition.Uncertain;
            }
        }

        #endregion

        #region Enhanced Trading Setup Detection

        /// <summary>
        /// Comprehensive trading setup with enhanced validation
        /// </summary>
        public class TradingSetup
        {
            public string Name { get; set; }
            public SignalDirection Direction { get; set; }
            public double Confidence { get; set; }
            public double EntryPrice { get; set; }
            public double StopLoss { get; set; }
            public double Target1 { get; set; }
            public double Target2 { get; set; }
            public List<string> Reasons { get; set; } = new List<string>();
            public MarketCondition MarketCondition { get; set; }
            public bool IsValid { get; set; }
            public DateTime Timestamp { get; set; } = DateTime.Now;
            public double QualityScore { get; set; }
            public int ConfirmationCount { get; set; }

            // Enhanced properties
            public double RiskRewardRatio => Math.Abs(EntryPrice - StopLoss) > 0 ?
                Math.Abs(Target1 - EntryPrice) / Math.Abs(EntryPrice - StopLoss) : 0;
            public bool IsHighQuality => QualityScore > 0.75 && Confidence > 0.8;
            public bool IsLowRisk => RiskRewardRatio > 2.0 && Math.Abs(EntryPrice - StopLoss) / EntryPrice < 0.02;
            public TimeSpan Age => DateTime.Now - Timestamp;
            public bool IsStale => Age.TotalMinutes > 15;

            /// <summary>Calculate overall setup score</summary>
            public double GetOverallScore()
            {
                double baseScore = Confidence * 0.4;
                double qualityScore = QualityScore * 0.3;
                double rrScore = Math.Min(RiskRewardRatio / 3.0, 1.0) * 0.2;
                double confirmationScore = Math.Min(ConfirmationCount / 3.0, 1.0) * 0.1;

                return baseScore + qualityScore + rrScore + confirmationScore;
            }
        }

        /// <summary>
        /// Detect EMA9 + VWAP bullish breakout setup with enhanced validation
        /// </summary>
        public static TradingSetup DetectBullishBreakout(NinjaScriptBase script, double vwap, double ema9,
            double aoValue, double previousAO, double rsi, double volumeRatio, double currentPrice, double atr)
        {
            var setup = new TradingSetup
            {
                Name = "EMA9_VWAP_Bullish_Breakout",
                Direction = SignalDirection.Neutral,
                Timestamp = DateTime.Now,
                EntryPrice = currentPrice
            };

            try
            {
                // Enhanced validation criteria
                var validationResults = new Dictionary<string, bool>();

                // Core alignment check: Price > EMA9 > VWAP
                bool priceAlignment = currentPrice > ema9 && ema9 > vwap;
                validationResults["PriceAlignment"] = priceAlignment;
                if (!priceAlignment)
                {
                    setup.Reasons.Add("Price alignment failed: Price > EMA9 > VWAP required");
                    return setup;
                }

                // Strength of alignment (distance between levels)
                double emaVwapSpread = (ema9 - vwap) / atr;
                double priceEmaSpread = (currentPrice - ema9) / atr;
                bool strongAlignment = emaVwapSpread > 0.2 && priceEmaSpread > 0.1;
                validationResults["StrongAlignment"] = strongAlignment;

                // AO momentum check (enhanced)
                bool aoMomentum = aoValue > 0 || (script.CurrentBar > 1 && aoValue > previousAO);
                bool aoAcceleration = script.CurrentBar > 2 && aoValue > previousAO &&
                    previousAO > (aoValue - (aoValue - previousAO)); // Simple acceleration check
                validationResults["AOMomentum"] = aoMomentum;
                validationResults["AOAcceleration"] = aoAcceleration;

                // RSI filter - optimal range for breakouts
                bool rsiOptimal = rsi >= 45 && rsi <= 75;
                bool rsiNotOverbought = rsi < 80;
                validationResults["RSIOptimal"] = rsiOptimal;
                validationResults["RSINotOverbought"] = rsiNotOverbought;

                // Volume confirmation (enhanced)
                bool volumeConfirmation = volumeRatio >= 1.3;
                bool strongVolume = volumeRatio >= 2.0;
                validationResults["VolumeConfirmation"] = volumeConfirmation;
                validationResults["StrongVolume"] = strongVolume;

                // Time-based validation
                bool optimalTime = FKS_Utils.IsMarketHours(DateTime.Now) && !FKS_Utils.IsWeekend(DateTime.Now);
                var session = FKS_Utils.GetCurrentSession(DateTime.Now);
                bool activeSession = session == SessionType.NYOpen || session == SessionType.NYSession ||
                                   session == SessionType.LondonOpen || session == SessionType.LondonSession;
                validationResults["OptimalTime"] = optimalTime && activeSession;

                // Calculate confirmation count and quality score
                int confirmations = validationResults.Values.Count(v => v);
                setup.ConfirmationCount = confirmations;

                // Require minimum confirmations for validity
                if (confirmations < 4)
                {
                    setup.Reasons.Add($"Insufficient confirmations: {confirmations}/7 required minimum 4");
                    return setup;
                }

                // Calculate dynamic confidence based on confirmations
                double baseConfidence = (double)confirmations / validationResults.Count;
                double volumeBonus = strongVolume ? 0.1 : (volumeConfirmation ? 0.05 : 0);
                double alignmentBonus = strongAlignment ? 0.1 : 0.05;
                double momentumBonus = aoAcceleration ? 0.1 : (aoMomentum ? 0.05 : 0);

                setup.Confidence = Math.Min(0.95, baseConfidence + volumeBonus + alignmentBonus + momentumBonus);

                // Calculate quality score
                setup.QualityScore = CalculateSetupQuality(validationResults, volumeRatio, emaVwapSpread);

                // Calculate stop loss and targets
                double supportLevel = Math.Max(ema9, vwap) - (atr * 0.5);
                double riskAmount = currentPrice - supportLevel;

                setup.StopLoss = supportLevel;
                setup.Target1 = currentPrice + (riskAmount * 2.0); // 2:1 RR
                setup.Target2 = currentPrice + (riskAmount * 3.5); // 3.5:1 RR

                // Validate risk parameters
                double riskPercent = riskAmount / currentPrice;
                if (riskPercent > 0.025) // Max 2.5% risk
                {
                    setup.Reasons.Add($"Risk too high: {riskPercent:P2} > 2.5%");
                    return setup;
                }

                // Setup is valid - compile reasons
                setup.Direction = SignalDirection.Long;
                setup.IsValid = true;
                setup.MarketCondition = DetectMarketCondition(script, rsi > 50 ? 25 : 15, atr, atr); // Simplified

                // Add detailed reasons
                setup.Reasons.Add($"✓ Price alignment: {currentPrice:F2} > {ema9:F2} > {vwap:F2}");
                setup.Reasons.Add($"✓ AO momentum: {aoValue:F4} {(aoAcceleration ? "(accelerating)" : "")}");
                setup.Reasons.Add($"✓ RSI optimal: {rsi:F1} (45-75 range)");
                setup.Reasons.Add($"✓ Volume confirmation: {volumeRatio:F2}x {(strongVolume ? "(strong)" : "")}");
                setup.Reasons.Add($"✓ Risk/Reward: {setup.RiskRewardRatio:F1}:1");
                setup.Reasons.Add($"✓ Quality Score: {setup.QualityScore:F2}");

                if (activeSession)
                    setup.Reasons.Add($"✓ Active session: {session}");

                return setup;
            }
            catch (Exception ex)
            {
                setup.Reasons.Add($"Error: {ex.Message}");
                return setup;
            }
        }

        /// <summary>
        /// Detect EMA9 + VWAP bearish breakdown setup with enhanced validation
        /// </summary>
        public static TradingSetup DetectBearishBreakdown(NinjaScriptBase script, double vwap, double ema9,
            double aoValue, double previousAO, double rsi, double volumeRatio, double currentPrice, double atr)
        {
            var setup = new TradingSetup
            {
                Name = "EMA9_VWAP_Bearish_Breakdown",
                Direction = SignalDirection.Neutral,
                Timestamp = DateTime.Now,
                EntryPrice = currentPrice
            };

            try
            {
                var validationResults = new Dictionary<string, bool>();

                // Core alignment check: Price < EMA9 < VWAP
                bool priceAlignment = currentPrice < ema9 && ema9 < vwap;
                validationResults["PriceAlignment"] = priceAlignment;
                if (!priceAlignment)
                {
                    setup.Reasons.Add("Price alignment failed: Price < EMA9 < VWAP required");
                    return setup;
                }

                // Strength of alignment
                double vwapEmaSpread = (vwap - ema9) / atr;
                double emaLriceSpread = (ema9 - currentPrice) / atr;
                bool strongAlignment = vwapEmaSpread > 0.2 && emaLriceSpread > 0.1;
                validationResults["StrongAlignment"] = strongAlignment;

                // AO momentum check
                bool aoMomentum = aoValue < 0 || (script.CurrentBar > 1 && aoValue < previousAO);
                bool aoAcceleration = script.CurrentBar > 2 && aoValue < previousAO &&
                    previousAO < (aoValue - (aoValue - previousAO));
                validationResults["AOMomentum"] = aoMomentum;
                validationResults["AOAcceleration"] = aoAcceleration;

                // RSI filter for bearish setups
                bool rsiOptimal = rsi >= 25 && rsi <= 55;
                bool rsiNotOversold = rsi > 20;
                validationResults["RSIOptimal"] = rsiOptimal;
                validationResults["RSINotOversold"] = rsiNotOversold;

                // Volume confirmation
                bool volumeConfirmation = volumeRatio >= 1.3;
                bool strongVolume = volumeRatio >= 2.0;
                validationResults["VolumeConfirmation"] = volumeConfirmation;
                validationResults["StrongVolume"] = strongVolume;

                // Time validation
                bool optimalTime = FKS_Utils.IsMarketHours(DateTime.Now) && !FKS_Utils.IsWeekend(DateTime.Now);
                var session = FKS_Utils.GetCurrentSession(DateTime.Now);
                bool activeSession = session == SessionType.NYOpen || session == SessionType.NYSession ||
                                   session == SessionType.LondonOpen || session == SessionType.LondonSession;
                validationResults["OptimalTime"] = optimalTime && activeSession;

                int confirmations = validationResults.Values.Count(v => v);
                setup.ConfirmationCount = confirmations;

                if (confirmations < 4)
                {
                    setup.Reasons.Add($"Insufficient confirmations: {confirmations}/7 required minimum 4");
                    return setup;
                }

                // Calculate confidence and quality
                double baseConfidence = (double)confirmations / validationResults.Count;
                double volumeBonus = strongVolume ? 0.1 : (volumeConfirmation ? 0.05 : 0);
                double alignmentBonus = strongAlignment ? 0.1 : 0.05;
                double momentumBonus = aoAcceleration ? 0.1 : (aoMomentum ? 0.05 : 0);

                setup.Confidence = Math.Min(0.95, baseConfidence + volumeBonus + alignmentBonus + momentumBonus);
                setup.QualityScore = CalculateSetupQuality(validationResults, volumeRatio, vwapEmaSpread);

                // Calculate stop and targets
                double resistanceLevel = Math.Min(ema9, vwap) + (atr * 0.5);
                double riskAmount = resistanceLevel - currentPrice;

                setup.StopLoss = resistanceLevel;
                setup.Target1 = currentPrice - (riskAmount * 2.0);
                setup.Target2 = currentPrice - (riskAmount * 3.5);

                // Validate risk
                double riskPercent = riskAmount / currentPrice;
                if (riskPercent > 0.025)
                {
                    setup.Reasons.Add($"Risk too high: {riskPercent:P2} > 2.5%");
                    return setup;
                }

                // Setup is valid
                setup.Direction = SignalDirection.Short;
                setup.IsValid = true;
                setup.MarketCondition = DetectMarketCondition(script, rsi < 50 ? 25 : 15, atr, atr);

                // Add reasons
                setup.Reasons.Add($"✓ Price alignment: {currentPrice:F2} < {ema9:F2} < {vwap:F2}");
                setup.Reasons.Add($"✓ AO momentum: {aoValue:F4} {(aoAcceleration ? "(accelerating)" : "")}");
                setup.Reasons.Add($"✓ RSI optimal: {rsi:F1} (25-55 range)");
                setup.Reasons.Add($"✓ Volume confirmation: {volumeRatio:F2}x {(strongVolume ? "(strong)" : "")}");
                setup.Reasons.Add($"✓ Risk/Reward: {setup.RiskRewardRatio:F1}:1");
                setup.Reasons.Add($"✓ Quality Score: {setup.QualityScore:F2}");

                return setup;
            }
            catch (Exception ex)
            {
                setup.Reasons.Add($"Error: {ex.Message}");
                return setup;
            }
        }

        /// <summary>
        /// Detect VWAP rejection setup with enhanced logic
        /// </summary>
        public static TradingSetup DetectVWAPRejection(NinjaScriptBase script, double vwap, double ema9,
            double aoValue, double previousAO, double currentPrice, double previousPrice, double atr, bool testDirection)
        {
            var setup = new TradingSetup
            {
                Name = "VWAP_Rejection",
                Direction = SignalDirection.Neutral,
                Timestamp = DateTime.Now,
                EntryPrice = currentPrice
            };

            try
            {
                double vwapDistance = Math.Abs(currentPrice - vwap) / atr;

                // Must be close to VWAP for rejection setup
                if (vwapDistance > 0.75)
                {
                    setup.Reasons.Add($"Too far from VWAP: {vwapDistance:F2} ATR > 0.75 limit");
                    return setup;
                }

                var validationResults = new Dictionary<string, bool>();

                if (testDirection) // Test for bullish rejection (bounce from VWAP)
                {
                    // Price action: previous below VWAP, current above or touching
                    bool bounceCondition = previousPrice <= vwap && currentPrice >= vwap * 0.999;
                    validationResults["BounceCondition"] = bounceCondition;

                    // AO support
                    bool aoSupport = aoValue > 0 || aoValue > previousAO;
                    validationResults["AOSupport"] = aoSupport;

                    // EMA alignment support
                    bool emaSupport = ema9 >= vwap * 0.998; // EMA near or above VWAP
                    validationResults["EMASupport"] = emaSupport;

                    // Close to VWAP
                    bool closeToVwap = vwapDistance < 0.5;
                    validationResults["CloseToVWAP"] = closeToVwap;

                    int confirmations = validationResults.Values.Count(v => v);
                    if (confirmations >= 3)
                    {
                        setup.Direction = SignalDirection.Long;
                        setup.Confidence = 0.70 + (confirmations - 3) * 0.05;
                        setup.QualityScore = CalculateSetupQuality(validationResults, 1.0, vwapDistance);
                        setup.StopLoss = vwap - (atr * 1.2);
                        setup.Target1 = currentPrice + (atr * 1.5);
                        setup.Target2 = currentPrice + (atr * 2.5);
                        setup.IsValid = true;
                        setup.ConfirmationCount = confirmations;
                        setup.Reasons.Add("✓ VWAP bullish rejection/bounce");
                    }
                }
                else // Test for bearish rejection (rejection at VWAP)
                {
                    // Price action: previous above VWAP, current below or touching
                    bool rejectionCondition = previousPrice >= vwap && currentPrice <= vwap * 1.001;
                    validationResults["RejectionCondition"] = rejectionCondition;

                    // AO resistance
                    bool aoResistance = aoValue < 0 || aoValue < previousAO;
                    validationResults["AOResistance"] = aoResistance;

                    // EMA alignment resistance
                    bool emaResistance = ema9 <= vwap * 1.002; // EMA near or below VWAP
                    validationResults["EMAResistance"] = emaResistance;

                    // Close to VWAP
                    bool closeToVwap = vwapDistance < 0.5;
                    validationResults["CloseToVWAP"] = closeToVwap;

                    int confirmations = validationResults.Values.Count(v => v);
                    if (confirmations >= 3)
                    {
                        setup.Direction = SignalDirection.Short;
                        setup.Confidence = 0.70 + (confirmations - 3) * 0.05;
                        setup.QualityScore = CalculateSetupQuality(validationResults, 1.0, vwapDistance);
                        setup.StopLoss = vwap + (atr * 1.2);
                        setup.Target1 = currentPrice - (atr * 1.5);
                        setup.Target2 = currentPrice - (atr * 2.5);
                        setup.IsValid = true;
                        setup.ConfirmationCount = confirmations;
                        setup.Reasons.Add("✓ VWAP bearish rejection");
                    }
                }

                if (setup.IsValid)
                {
                    setup.Reasons.Add($"✓ VWAP distance: {vwapDistance:F2} ATR");
                    setup.Reasons.Add($"✓ Confirmations: {setup.ConfirmationCount}/4");
                }

                return setup;
            }
            catch (Exception ex)
            {
                setup.Reasons.Add($"Error: {ex.Message}");
                return setup;
            }
        }

        /// <summary>
        /// Calculate setup quality score based on validation results
        /// </summary>
        private static double CalculateSetupQuality(Dictionary<string, bool> validations, double volumeRatio, double spread)
        {
            double baseScore = (double)validations.Values.Count(v => v) / validations.Count;
            double volumeBonus = Math.Min((volumeRatio - 1.0) * 0.1, 0.2); // Max 20% bonus
            double spreadBonus = Math.Min(spread * 0.05, 0.1); // Max 10% bonus for good spread

            return Math.Min(0.95, baseScore + volumeBonus + spreadBonus);
        }

        #endregion

        #region AO Pattern Detection

        /// <summary>
        /// Detect AO saucer patterns with enhanced validation
        /// </summary>
        public static TradingSetup DetectAOSaucer(NinjaScriptBase script, double[] aoHistory, double currentPrice,
            double ema9, double vwap, double atr)
        {
            var setup = new TradingSetup
            {
                Name = "AO_Saucer",
                Direction = SignalDirection.Neutral,
                Timestamp = DateTime.Now,
                EntryPrice = currentPrice
            };

            try
            {
                if (aoHistory == null || aoHistory.Length < 5)
                {
                    setup.Reasons.Add("Insufficient AO history for saucer detection");
                    return setup;
                }

                var validationResults = new Dictionary<string, bool>();

                // Check for bullish saucer: down, down, up pattern
                if (aoHistory.Length >= 3)
                {
                    bool isBullishSaucer = aoHistory[2] < aoHistory[1] &&  // First down
                                          aoHistory[1] < aoHistory[0] &&   // Second down  
                                          aoHistory[0] > aoHistory[1] &&   // Up from bottom
                                          aoHistory[0] < 0;                // Still below zero line
                    validationResults["BullishSaucerPattern"] = isBullishSaucer;

                    if (isBullishSaucer)
                    {
                        // Enhanced confirmation requirements
                        bool priceSupport = currentPrice > ema9 * 0.999;
                        bool vwapAlignment = currentPrice > vwap * 0.998;
                        bool strongTurning = aoHistory[0] > aoHistory[1] * 1.1; // 10% improvement
                        bool nearZero = Math.Abs(aoHistory[0]) < 0.0005; // Close to zero line

                        validationResults["PriceSupport"] = priceSupport;
                        validationResults["VWAPAlignment"] = vwapAlignment;
                        validationResults["StrongTurning"] = strongTurning;
                        validationResults["NearZeroLine"] = nearZero;

                        int confirmations = validationResults.Values.Count(v => v);
                        if (confirmations >= 3)
                        {
                            setup.Direction = SignalDirection.Long;
                            setup.Confidence = 0.75 + (confirmations - 3) * 0.05;
                            setup.QualityScore = CalculateSetupQuality(validationResults, 1.0, 0.5);
                            setup.StopLoss = currentPrice - (atr * 1.5);
                            setup.Target1 = currentPrice + (atr * 2.0);
                            setup.Target2 = currentPrice + (atr * 3.5);
                            setup.IsValid = true;
                            setup.ConfirmationCount = confirmations;

                            setup.Reasons.Add("✓ Bullish AO saucer pattern detected");
                            setup.Reasons.Add($"✓ AO sequence: {aoHistory[2]:F4} > {aoHistory[1]:F4} < {aoHistory[0]:F4}");
                            if (priceSupport && vwapAlignment) setup.Reasons.Add("✓ Price above EMA9 and VWAP");
                            if (strongTurning) setup.Reasons.Add("✓ Strong AO turning momentum");
                            if (nearZero) setup.Reasons.Add("✓ AO approaching zero line");
                        }
                    }
                }

                // Check for bearish saucer: up, up, down pattern  
                if (aoHistory.Length >= 3 && !setup.IsValid)
                {
                    bool isBearishSaucer = aoHistory[2] > aoHistory[1] &&  // First up
                                          aoHistory[1] > aoHistory[0] &&   // Second up
                                          aoHistory[0] < aoHistory[1] &&   // Down from top
                                          aoHistory[0] > 0;                // Still above zero line
                    validationResults["BearishSaucerPattern"] = isBearishSaucer;

                    if (isBearishSaucer)
                    {
                        bool priceResistance = currentPrice < ema9 * 1.001;
                        bool vwapAlignment = currentPrice < vwap * 1.002;
                        bool strongTurning = aoHistory[0] < aoHistory[1] * 0.9; // 10% deterioration
                        bool nearZero = Math.Abs(aoHistory[0]) < 0.0005;

                        validationResults["PriceResistance"] = priceResistance;
                        validationResults["VWAPAlignment"] = vwapAlignment;
                        validationResults["StrongTurning"] = strongTurning;
                        validationResults["NearZeroLine"] = nearZero;

                        int confirmations = validationResults.Values.Count(v => v);
                        if (confirmations >= 3)
                        {
                            setup.Direction = SignalDirection.Short;
                            setup.Confidence = 0.75 + (confirmations - 3) * 0.05;
                            setup.QualityScore = CalculateSetupQuality(validationResults, 1.0, 0.5);
                            setup.StopLoss = currentPrice + (atr * 1.5);
                            setup.Target1 = currentPrice - (atr * 2.0);
                            setup.Target2 = currentPrice - (atr * 3.5);
                            setup.IsValid = true;
                            setup.ConfirmationCount = confirmations;

                            setup.Reasons.Add("✓ Bearish AO saucer pattern detected");
                            setup.Reasons.Add($"✓ AO sequence: {aoHistory[2]:F4} < {aoHistory[1]:F4} > {aoHistory[0]:F4}");
                            if (priceResistance && vwapAlignment) setup.Reasons.Add("✓ Price below EMA9 and VWAP");
                            if (strongTurning) setup.Reasons.Add("✓ Strong AO turning momentum");
                            if (nearZero) setup.Reasons.Add("✓ AO approaching zero line");
                        }
                    }
                }

                if (!setup.IsValid)
                {
                    setup.Reasons.Add("No valid AO saucer pattern found or insufficient confirmations");
                }

                return setup;
            }
            catch (Exception ex)
            {
                setup.Reasons.Add($"Error: {ex.Message}");
                return setup;
            }
        }

        /// <summary>
        /// Detect AO zero line crosses with comprehensive validation
        /// </summary>
        public static TradingSetup DetectAOZeroCross(NinjaScriptBase script, double currentAO, double previousAO,
            double currentPrice, double ema9, double vwap, double atr)
        {
            var setup = new TradingSetup
            {
                Name = "AO_Zero_Cross",
                Direction = SignalDirection.Neutral,
                Timestamp = DateTime.Now,
                EntryPrice = currentPrice
            };

            try
            {
                var validationResults = new Dictionary<string, bool>();

                // Bullish zero line cross
                if (previousAO <= 0 && currentAO > 0)
                {
                    bool cleanCross = previousAO < -0.0001; // Ensure it was clearly negative
                    bool strongCross = currentAO > 0.0001; // Ensure it's clearly positive
                    bool priceConfirmation = currentPrice > ema9 && currentPrice > vwap;
                    bool momentumBuilding = Math.Abs(currentAO) > Math.Abs(previousAO);

                    validationResults["CleanCross"] = cleanCross;
                    validationResults["StrongCross"] = strongCross;
                    validationResults["PriceConfirmation"] = priceConfirmation;
                    validationResults["MomentumBuilding"] = momentumBuilding;

                    int confirmations = validationResults.Values.Count(v => v);
                    if (confirmations >= 3)
                    {
                        setup.Direction = SignalDirection.Long;
                        setup.Confidence = 0.80 + (confirmations - 3) * 0.05;
                        setup.QualityScore = CalculateSetupQuality(validationResults, 1.2, 0.3);
                        setup.StopLoss = Math.Min(ema9, vwap) - (atr * 1.0);
                        setup.Target1 = currentPrice + (atr * 2.0);
                        setup.Target2 = currentPrice + (atr * 3.0);
                        setup.IsValid = true;
                        setup.ConfirmationCount = confirmations;

                        setup.Reasons.Add("✓ Bullish AO zero line cross");
                        setup.Reasons.Add($"✓ AO: {previousAO:F4} → {currentAO:F4}");
                        if (priceConfirmation) setup.Reasons.Add("✓ Price above EMA9 and VWAP");
                        if (momentumBuilding) setup.Reasons.Add("✓ Momentum building");
                    }
                }
                // Bearish zero line cross
                else if (previousAO >= 0 && currentAO < 0)
                {
                    bool cleanCross = previousAO > 0.0001;
                    bool strongCross = currentAO < -0.0001;
                    bool priceConfirmation = currentPrice < ema9 && currentPrice < vwap;
                    bool momentumBuilding = Math.Abs(currentAO) > Math.Abs(previousAO);

                    validationResults["CleanCross"] = cleanCross;
                    validationResults["StrongCross"] = strongCross;
                    validationResults["PriceConfirmation"] = priceConfirmation;
                    validationResults["MomentumBuilding"] = momentumBuilding;

                    int confirmations = validationResults.Values.Count(v => v);
                    if (confirmations >= 3)
                    {
                        setup.Direction = SignalDirection.Short;
                        setup.Confidence = 0.80 + (confirmations - 3) * 0.05;
                        setup.QualityScore = CalculateSetupQuality(validationResults, 1.2, 0.3);
                        setup.StopLoss = Math.Max(ema9, vwap) + (atr * 1.0);
                        setup.Target1 = currentPrice - (atr * 2.0);
                        setup.Target2 = currentPrice - (atr * 3.0);
                        setup.IsValid = true;
                        setup.ConfirmationCount = confirmations;

                        setup.Reasons.Add("✓ Bearish AO zero line cross");
                        setup.Reasons.Add($"✓ AO: {previousAO:F4} → {currentAO:F4}");
                        if (priceConfirmation) setup.Reasons.Add("✓ Price below EMA9 and VWAP");
                        if (momentumBuilding) setup.Reasons.Add("✓ Momentum building");
                    }
                }
                else
                {
                    setup.Reasons.Add("No zero line cross detected");
                }

                if (!setup.IsValid && validationResults.Any())
                {
                    int confirmations = validationResults.Values.Count(v => v);
                    setup.Reasons.Add($"Insufficient confirmations for zero cross: {confirmations}/4 (need 3+)");
                }

                return setup;
            }
            catch (Exception ex)
            {
                setup.Reasons.Add($"Error: {ex.Message}");
                return setup;
            }
        }

        #endregion

        #region Utility Methods

        /// <summary>
        /// Calculate confidence based on multiple boolean conditions
        /// </summary>
        private static double CalculateConfidence(params bool[] conditions)
        {
            if (conditions == null || conditions.Length == 0) return 0.0;

            int trueCount = conditions.Count(c => c);
            double baseConfidence = (double)trueCount / conditions.Length;

            // Scale to more realistic range (0.6 - 0.9)
            return 0.6 + (baseConfidence * 0.3);
        }

        /// <summary>
        /// Check if current time is within active trading hours
        /// </summary>
        public static bool IsActiveTradingTime(DateTime currentTime)
        {
            if (FKS_Utils.IsWeekend(currentTime)) return false;

            var session = FKS_Utils.GetCurrentSession(currentTime);

            // Active sessions for signal generation
            return session == SessionType.LondonOpen ||
                   session == SessionType.LondonSession ||
                   session == SessionType.NYOpen ||
                   session == SessionType.NYSession;
        }

        /// <summary>
        /// Apply market condition filters to setup
        /// </summary>
        public static bool ApplyMarketFilters(TradingSetup setup, MarketCondition condition)
        {
            if (!setup.IsValid) return false;

            switch (condition)
            {
                case MarketCondition.Trending:
                    // In trending markets, allow slightly lower confidence but require good RR
                    return setup.Confidence >= 0.70 && setup.RiskRewardRatio >= 1.5;

                case MarketCondition.Ranging:
                    // In ranging markets, focus on reversal setups with higher confidence
                    return (setup.Name.Contains("Rejection") || setup.Name.Contains("Saucer")) &&
                           setup.Confidence >= 0.75;

                case MarketCondition.HighVolatility:
                    // In high volatility, require very high confidence and tight stops
                    return setup.Confidence >= 0.85 && setup.GetOverallScore() >= 0.80;

                case MarketCondition.LowVolatility:
                    // In low volatility, accept lower confidence but adjust targets
                    if (setup.Confidence >= 0.65)
                    {
                        // Reduce targets in low volatility
                        double currentRange = Math.Abs(setup.Target1 - setup.EntryPrice);
                        setup.Target1 = setup.EntryPrice + (setup.Direction == SignalDirection.Long ? 1 : -1) * (currentRange * 0.7);
                        setup.Target2 = setup.EntryPrice + (setup.Direction == SignalDirection.Long ? 1 : -1) * (currentRange * 1.2);
                        return true;
                    }
                    return false;

                case MarketCondition.NewsEvent:
                    // During news events, only take very high quality setups
                    return setup.Confidence >= 0.90 && setup.QualityScore >= 0.85;

                default:
                    return setup.Confidence >= 0.70 && setup.GetOverallScore() >= 0.65;
            }
        }

        /// <summary>
        /// Enhanced signal quality assessment using the new FKS_SignalQuality framework
        /// </summary>
        public static FKS_SignalQuality AssessSignalQuality(TradingSetup setup, MarketCondition marketCondition,
            double volumeRatio, double atr, double riskRewardRatio)
        {
            var signalQuality = new FKS_SignalQuality();

            try
            {
                // Base Score (0-1): Core technical criteria
                double baseScore = 0.0;
                if (setup.Direction != SignalDirection.Neutral) baseScore += 0.3;
                if (setup.Confidence > 0.7) baseScore += 0.4;
                if (setup.ConfirmationCount >= 4) baseScore += 0.3;
                signalQuality.BaseScore = Math.Min(1.0, baseScore);

                // Confluence Score (0-1): Multiple indicator alignment
                double confluenceScore = 0.0;
                confluenceScore += Math.Min(setup.ConfirmationCount / 7.0, 1.0) * 0.6; // Confirmation ratio
                if (volumeRatio >= 1.5) confluenceScore += 0.2; // Volume confirmation
                if (riskRewardRatio >= 2.0) confluenceScore += 0.2; // Good RR
                signalQuality.ConfluenceScore = Math.Min(1.0, confluenceScore);

                // Timing Score (0-1): Market timing factors
                double timingScore = 0.0;
                var context = FKS_MarketContext.Instance;
                if (context.IsOptimalTradingTime) timingScore += 0.4;
                if (context.SessionPhase == "Active" || context.SessionPhase == "Open") timingScore += 0.3;
                if (!setup.IsStale) timingScore += 0.3; // Fresh signal
                signalQuality.TimingScore = Math.Min(1.0, timingScore);

                // Market Context Score (0-1): Current market conditions
                double marketContextScore = 0.0;
                switch (marketCondition)
                {
                    case MarketCondition.Trending:
                        marketContextScore = 0.9; // Best for directional trades
                        break;
                    case MarketCondition.Ranging:
                        marketContextScore = 0.6; // Moderate - depends on strategy
                        break;
                    case MarketCondition.LowVolatility:
                        marketContextScore = 0.7; // Good for breakouts
                        break;
                    case MarketCondition.HighVolatility:
                        marketContextScore = 0.4; // Risky
                        break;
                    case MarketCondition.NewsEvent:
                        marketContextScore = 0.2; // Very risky
                        break;
                    default:
                        marketContextScore = 0.5;
                        break;
                }

                // Adjust for market breadth if available
                if (context.MarketBreadth > 0.6) marketContextScore += 0.1;
                else if (context.MarketBreadth < 0.4) marketContextScore -= 0.1;

                signalQuality.MarketContextScore = Math.Max(0.0, Math.Min(1.0, marketContextScore));

                // Risk Reward Score (0-1): Risk management factors
                double riskRewardScore = 0.0;
                if (riskRewardRatio >= 3.0) riskRewardScore = 1.0;
                else if (riskRewardRatio >= 2.0) riskRewardScore = 0.8;
                else if (riskRewardRatio >= 1.5) riskRewardScore = 0.6;
                else if (riskRewardRatio >= 1.0) riskRewardScore = 0.4;
                else riskRewardScore = 0.2;

                // Adjust for position sizing risk
                double entryPrice = setup.EntryPrice;
                double stopLoss = setup.StopLoss;
                if (entryPrice > 0 && stopLoss > 0)
                {
                    double riskPercent = Math.Abs(entryPrice - stopLoss) / entryPrice;
                    if (riskPercent <= 0.01) riskRewardScore += 0.1; // Very tight stop
                    else if (riskPercent >= 0.03) riskRewardScore -= 0.2; // Wide stop penalty
                }

                signalQuality.RiskRewardScore = Math.Max(0.0, Math.Min(1.0, riskRewardScore));

                return signalQuality;
            }
            catch (Exception ex)
            {
                // Return default quality on error
                FKS_ErrorHandler.HandleError(ex, "AssessSignalQuality");
                return new FKS_SignalQuality
                {
                    BaseScore = 0.5,
                    ConfluenceScore = 0.5,
                    TimingScore = 0.5,
                    MarketContextScore = 0.5,
                    RiskRewardScore = 0.5
                };
            }
        }

        /// <summary>
        /// Enhanced setup creation with Signal Quality integration
        /// </summary>
        public static TradingSetup CreateEnhancedSetup(string name, SignalDirection direction,
            double entryPrice, double stopLoss, double target1, double confidence,
            MarketCondition marketCondition, Dictionary<string, bool> validations,
            double volumeRatio, double atr)
        {
            var setup = new TradingSetup
            {
                Name = name,
                Direction = direction,
                EntryPrice = entryPrice,
                StopLoss = stopLoss,
                Target1 = target1,
                Target2 = entryPrice + ((target1 - entryPrice) * 1.75), // Extended target
                Confidence = confidence,
                MarketCondition = marketCondition,
                IsValid = direction != SignalDirection.Neutral,
                Timestamp = DateTime.Now,
                ConfirmationCount = validations?.Values.Count(v => v) ?? 0
            };

            // Calculate quality score using new framework
            var signalQuality = AssessSignalQuality(setup, marketCondition, volumeRatio, atr, setup.RiskRewardRatio);
            setup.QualityScore = signalQuality.OverallScore;

            // Add quality assessment to reasons
            setup.Reasons.Add($"Quality Grade: {signalQuality.GetQualityGrade()} (Overall: {signalQuality.OverallScore:F2})");
            setup.Reasons.Add($"Bulletproof: {(signalQuality.IsBulletproof ? "YES" : "NO")}");


            if (validations != null)
            {
                foreach (var validation in validations.Where(v => v.Value))
                {
                    setup.Reasons.Add($"✓ {validation.Key}");
                }
            }

            return setup;
        }

        #endregion
    }

    #endregion

    #region Signal Coordination System (500 lines)

    /// <summary>
    /// Composite signal that combines multiple component signals with enhanced quality assessment
    /// </summary>
    public class CompositeSignal
    {
        public SignalDirection Direction { get; set; } = SignalDirection.Neutral;
        public double Confidence { get; set; }
        public double WeightedScore { get; set; }
        public double QualityScore { get; set; }
        public int ComponentCount { get; set; }
        public DateTime Timestamp { get; set; } = DateTime.Now;
        public List<string> Reasons { get; set; } = new List<string>();

        // Enhanced properties with Signal Quality Framework integration
        public FKS_SignalQuality SignalQuality { get; set; } = new FKS_SignalQuality();
        public List<ComponentSignal> ComponentSignals { get; set; } = new List<ComponentSignal>();
        public double RiskRewardEstimate { get; set; }
        public FKS_SignalGenerator.MarketCondition MarketCondition { get; set; }
        public string SetupName { get; set; }

        // Quality assessments
        public bool IsHighQuality => SignalQuality.OverallScore > 0.75 && Confidence > 0.8;
        public bool IsBulletproof => SignalQuality.IsBulletproof;
        public string QualityGrade => SignalQuality.GetQualityGrade();
        public bool IsStale => (DateTime.Now - Timestamp).TotalMinutes > 15;
        public bool IsActionable => IsHighQuality && !IsStale && ComponentCount >= 2;

        /// <summary>
        /// Calculate enhanced composite score incorporating all quality factors
        /// </summary>
        public double GetEnhancedScore()
        {
            double baseScore = WeightedScore * 0.4;
            double qualityScore = SignalQuality.OverallScore * 0.3;
            double confidenceScore = Confidence * 0.2;
            double componentScore = Math.Min(ComponentCount / 5.0, 1.0) * 0.1;

            return baseScore + qualityScore + confidenceScore + componentScore;
        }

        /// <summary>
        /// Get comprehensive signal assessment
        /// </summary>
        public string GetAssessment()
        {
            var assessment = new StringBuilder();
            assessment.AppendLine($"Signal Quality: {QualityGrade} ({SignalQuality.OverallScore:F2})");
            assessment.AppendLine($"Direction: {Direction} (Confidence: {Confidence:F2})");
            assessment.AppendLine($"Components: {ComponentCount} signals");
            assessment.AppendLine($"Enhanced Score: {GetEnhancedScore():F2}");

            if (IsBulletproof)
                assessment.AppendLine("⭐ BULLETPROOF SETUP ⭐");
            else if (IsHighQuality)
                assessment.AppendLine("✅ High Quality Signal");
            else if (IsActionable)
                assessment.AppendLine("⚡ Actionable Signal");

            if (!string.IsNullOrEmpty(SetupName))
                assessment.AppendLine($"Setup: {SetupName}");

            if (RiskRewardEstimate > 0)
                assessment.AppendLine($"R:R Estimate: {RiskRewardEstimate:F1}:1");

            return assessment.ToString();
        }
    }



    /// <summary>
    /// Advanced signal coordination with enhanced weighting and consensus algorithms
    /// Consolidates and enhances FKS_SignalCoordinator functionality
    /// </summary>
    public class FKS_SignalCoordinator : IDisposable
    {
        #region Private Fields
        private readonly object signalLock = new object();
        private readonly ConcurrentDictionary<string, ComponentSignal> componentSignals = new ConcurrentDictionary<string, ComponentSignal>();
        private readonly ConcurrentDictionary<string, DateTime> lastSignalTimes = new ConcurrentDictionary<string, DateTime>();
        private readonly ConcurrentDictionary<string, ComponentMetrics> componentMetrics = new ConcurrentDictionary<string, ComponentMetrics>();
        private readonly FKS_CircularBuffer<CompositeSignal> signalHistory = new FKS_CircularBuffer<CompositeSignal>(100);
        private readonly FKS_CircularBuffer<SignalLogEntry> eventLog = new FKS_CircularBuffer<SignalLogEntry>(500);

        private readonly FKS_Configuration config;
        private volatile bool disposed = false;

        // Enhanced weighting parameters
        private readonly Dictionary<string, double> baseWeights = new Dictionary<string, double>();
        private readonly Dictionary<string, double> performanceAdjustments = new Dictionary<string, double>();

        // Signal quality tracking
        private int totalSignalsGenerated = 0;
        private int qualitySignalsGenerated = 0;
        private int signalsEvaluated = 0;
        private int correctPredictions = 0;
        #endregion

        #region Constructor and Configuration

        public FKS_SignalCoordinator(FKS_Configuration configuration = null)
        {
            config = configuration ?? FKS_Configuration.CreateBalanced();
            InitializeDefaultWeights();
            LogEvent("Signal Coordinator initialized", FKSLogLevel.Information);
        }

        private void InitializeDefaultWeights()
        {
            baseWeights["FKS_AI"] = config.AIComponentWeight;
            baseWeights["FKS_AO"] = config.AOComponentWeight;
            baseWeights["FKS_Dashboard"] = config.InfoComponentWeight;
            baseWeights["Default"] = 0.10;

            // Initialize performance adjustments to neutral
            foreach (var key in baseWeights.Keys)
            {
                performanceAdjustments[key] = 1.0;
            }
        }

        #endregion

        #region Component Registration and Management

        /// <summary>
        /// Register a component signal with enhanced validation
        /// </summary>
        public bool RegisterComponentSignal(string componentName, ComponentSignal signal)
        {
            if (disposed || string.IsNullOrEmpty(componentName) || signal == null || !signal.IsValid())
            {
                LogEvent($"Invalid signal registration attempt: {componentName}", FKSLogLevel.Warning);
                return false;
            }

            try
            {
                signal.Timestamp = DateTime.Now;

                // Store the signal
                componentSignals.AddOrUpdate(componentName, signal, (key, oldSignal) => signal);
                lastSignalTimes.AddOrUpdate(componentName, DateTime.Now, (key, oldTime) => DateTime.Now);

                // Update component metrics
                var metrics = componentMetrics.GetOrAdd(componentName, _ => new ComponentMetrics
                {
                    ComponentName = componentName,
                    FirstRegistration = DateTime.Now
                });

                metrics.TotalSignals++;
                metrics.LastSignalTime = DateTime.Now;

                // Quality assessment
                if (signal.Confidence >= config.BaseSignalThreshold)
                {
                    metrics.ValidSignals++;
                }

                if (signal.Confidence >= config.StrongSignalThreshold)
                {
                    metrics.StrongSignals++;
                }

                // Update recent performance tracking
                UpdateRecentPerformance(componentName, signal);

                LogEvent($"Signal registered: {componentName} -> {signal.Direction} ({signal.Confidence:F2})", FKSLogLevel.Debug);
                return true;
            }
            catch (Exception ex)
            {
                LogEvent($"Error registering signal from {componentName}: {ex.Message}", FKSLogLevel.Error);
                return false;
            }
        }

        /// <summary>
        /// Get latest signal from component
        /// </summary>
        public ComponentSignal GetComponentSignal(string componentName)
        {
            if (disposed || string.IsNullOrEmpty(componentName))
                return null;

            componentSignals.TryGetValue(componentName, out var signal);
            return signal?.IsValid() == true && !signal.IsStale ? signal : null;
        }

        /// <summary>
        /// Update component weight dynamically
        /// </summary>
        public void UpdateComponentWeight(string componentName, double weight)
        {
            if (string.IsNullOrEmpty(componentName)) return;

            weight = FKS_Utils.Clamp(weight, 0.05, 2.0);
            baseWeights[componentName] = weight;

            LogEvent($"Component weight updated: {componentName} = {weight:F2}", FKSLogLevel.Information);
        }

        /// <summary>
        /// Get effective weight for component (base weight * performance adjustment)
        /// </summary>
        public double GetEffectiveWeight(string componentName)
        {
            double baseWeight = baseWeights.TryGetValue(componentName, out var weight) ? weight : baseWeights["Default"];
            double performanceAdj = performanceAdjustments.TryGetValue(componentName, out var adj) ? adj : 1.0;

            return baseWeight * performanceAdj;
        }

        #endregion

        #region Signal Aggregation and Consensus

        /// <summary>
        /// Generate composite signal with enhanced consensus algorithm
        /// </summary>
        public CompositeSignal GenerateCompositeSignal()
        {
            if (disposed) return null;

            lock (signalLock)
            {
                try
                {
                    // Get valid, recent signals
                    var activeSignals = GetActiveSignals();

                    if (activeSignals.Count < config.MinComponentAgreement)
                    {
                        LogEvent($"Insufficient components for consensus: {activeSignals.Count}/{config.MinComponentAgreement}", FKSLogLevel.Debug);
                        return null;
                    }

                    var composite = new CompositeSignal
                    {
                        Timestamp = DateTime.Now,
                        Reasons = new List<string>()
                    };

                    // Enhanced consensus algorithm
                    var consensus = CalculateEnhancedConsensus(activeSignals);

                    if (consensus == null)
                    {
                        LogEvent("No consensus reached among components", FKSLogLevel.Debug);
                        return null;
                    }

                    // Apply consensus results to composite
                    composite.Direction = consensus.Direction;
                    composite.WeightedScore = consensus.WeightedScore;
                    composite.Confidence = consensus.Confidence;
                    composite.QualityScore = consensus.QualityScore;
                    composite.ComponentCount = activeSignals.Count;
                    composite.Reasons.AddRange(consensus.Reasons);

                    // Final validation
                    if (!ValidateCompositeSignal(composite))
                    {
                        LogEvent("Composite signal failed final validation", FKSLogLevel.Debug);
                        return null;
                    }

                    // Store in history and update statistics
                    signalHistory.Add(composite);
                    totalSignalsGenerated++;
                    if (composite.IsHighQuality) qualitySignalsGenerated++;

                    LogEvent($"Composite signal generated: {composite.Direction} (Conf: {composite.Confidence:F2}, Quality: {composite.QualityScore:F2}, Components: {composite.ComponentCount})", FKSLogLevel.Information);
                    return composite;
                }
                catch (Exception ex)
                {
                    LogEvent($"Error generating composite signal: {ex.Message}", FKSLogLevel.Error);
                    return null;
                }
            }
        }

        /// <summary>
        /// Get currently active (valid and recent) signals
        /// </summary>
        private Dictionary<string, ComponentSignal> GetActiveSignals()
        {
            var active = new Dictionary<string, ComponentSignal>();
            var cutoffTime = DateTime.Now.AddMinutes(-config.MaxSignalAgeMinutes);

            foreach (var kvp in componentSignals)
            {
                var signal = kvp.Value;
                if (signal?.IsValid() == true &&
                    signal.IsActive &&
                    signal.Timestamp > cutoffTime &&
                    signal.Confidence >= config.BaseSignalThreshold)
                {
                    active[kvp.Key] = signal;
                }
            }

            return active;
        }

        /// <summary>
        /// Enhanced consensus calculation with multiple factors
        /// </summary>
        private SignalConsensus CalculateEnhancedConsensus(Dictionary<string, NinjaTrader.NinjaScript.AddOns.ComponentSignal> signals)
        {
            var directionScores = new Dictionary<SignalDirection, double>();
            var directionCounts = new Dictionary<SignalDirection, int>();
            var directionConfidences = new Dictionary<SignalDirection, List<double>>();

            double totalWeight = 0;
            var reasons = new List<string>();

            // Analyze each signal
            foreach (var kvp in signals)
            {
                var componentName = kvp.Key;
                var signal = kvp.Value;

                if (signal.Direction == SignalDirection.Neutral) continue;

                // Calculate effective weight with multiple factors
                double effectiveWeight = CalculateEffectiveWeight(componentName, signal);
                totalWeight += effectiveWeight;

                // Accumulate by direction
                var dir = signal.Direction;
                var conf = signal.Confidence;
                if (!directionScores.ContainsKey(dir))
                {
                    directionScores[dir] = 0;
                    directionCounts[dir] = 0;
                    directionConfidences[dir] = new List<double>();
                }

                directionScores[dir] += effectiveWeight * conf;
                directionCounts[dir]++;
                directionConfidences[dir].Add(conf);

                reasons.Add($"{componentName}: {dir} (Conf: {conf:F2}, Weight: {effectiveWeight:F2})");
            }

            if (totalWeight == 0) return null;

            // Find dominant direction with quality checks
            var dominant = directionScores.OrderByDescending(kv => kv.Value).First();

            // Require minimum component agreement
            if (directionCounts[dominant.Key] < config.MinComponentAgreement)
            {
                return null;
            }

            // Calculate consensus metrics
            double weightedScore = dominant.Value / totalWeight;
            double avgConfidence = directionConfidences[dominant.Key].Average();
            double confidenceVariance = CalculateVariance(directionConfidences[dominant.Key]);
            double agreementRatio = (double)directionCounts[dominant.Key] / signals.Count;

            // Enhanced quality score calculation
            double qualityScore = CalculateConsensusQuality(
                avgConfidence,
                confidenceVariance,
                agreementRatio,
                directionCounts[dominant.Key],
                weightedScore
            );

            return new SignalConsensus
            {
                Direction = dominant.Key,
                WeightedScore = weightedScore,
                Confidence = avgConfidence,
                QualityScore = qualityScore,
                Reasons = reasons
            };
        }

        /// <summary>
        /// Calculate effective weight with multiple enhancement factors
        /// </summary>
        private double CalculateEffectiveWeight(string componentName, NinjaTrader.NinjaScript.AddOns.ComponentSignal signal)
        {
            double baseWeight = GetEffectiveWeight(componentName);

            // Get component metrics for additional factors
            if (!componentMetrics.TryGetValue(componentName, out var metrics))
                return baseWeight;

            // Recency factor (signals lose weight over time)
            double age = (DateTime.Now - signal.Timestamp).TotalMinutes;
            double recencyFactor = Math.Max(0.5, 1.0 - (age / (config.MaxSignalAgeMinutes * 2.0)));

            // Consistency factor (based on historical performance)
            double consistencyFactor = 1.0;
            if (metrics.TotalSignals > 10)
            {
                double validRatio = (double)metrics.ValidSignals / metrics.TotalSignals;
                consistencyFactor = 0.7 + (validRatio * 0.6); // Range 0.7 to 1.3
            }

            // Confidence strength factor
            double strengthFactor = 1.0 + ((signal.Confidence - config.BaseSignalThreshold) * 0.5);

            // Combine all factors
            return baseWeight * recencyFactor * consistencyFactor * strengthFactor;
        }

        /// <summary>
        /// Calculate consensus quality score
        /// </summary>
        private double CalculateConsensusQuality(double avgConfidence, double confidenceVariance,
            double agreementRatio, int componentCount, double weightedScore)
        {
            // Base quality from average confidence
            double baseQuality = avgConfidence * 0.4;

            // Bonus for high agreement ratio
            double agreementBonus = agreementRatio * 0.25;

            // Bonus for low variance (consistent signals)
            double consistencyBonus = Math.Max(0, (0.1 - confidenceVariance) * 2.5) * 0.15;

            // Bonus for strong weighted score
            double strengthBonus = Math.Min(weightedScore, 1.0) * 0.15;

            // Bonus for multiple components
            double componentBonus = Math.Min((componentCount - 1) * 0.05, 0.05);

            return Math.Min(0.98, baseQuality + agreementBonus + consistencyBonus + strengthBonus + componentBonus);
        }

        /// <summary>
        /// Validate composite signal meets quality thresholds
        /// </summary>
        private bool ValidateCompositeSignal(CompositeSignal signal)
        {
            // Must meet minimum confidence threshold
            if (signal.Confidence < config.BaseSignalThreshold)
                return false;

            // Must have minimum quality score
            if (signal.QualityScore < 0.5)
                return false;

            // Must have minimum component count
            if (signal.ComponentCount < config.MinComponentAgreement)
                return false;

            // Direction must not be neutral
            if (signal.Direction == SignalDirection.Neutral)
                return false;

            return true;
        }

        #endregion

        #region Performance Tracking and Learning

        /// <summary>
        /// Record signal performance for learning
        /// </summary>
        public void RecordSignalPerformance(CompositeSignal signal, SignalDirection actualDirection, double profitFactor)
        {
            if (disposed || signal == null) return;

            try
            {
                bool isCorrect = signal.Direction == actualDirection;
                signalsEvaluated++;
                if (isCorrect) correctPredictions++;

                // Update component performance adjustments for all active components
                // Since we don't store individual component signals in CompositeSignal,
                // we update all components that were active during signal generation
                var activeSignals = GetActiveSignals();
                foreach (var kvp in activeSignals)
                {
                    UpdateComponentPerformance(kvp.Key, isCorrect, profitFactor);
                }

                LogEvent($"Signal performance recorded: {signal.Direction} vs {actualDirection}, " +
                        $"Correct: {isCorrect}, PF: {profitFactor:F2}", FKSLogLevel.Information);
            }
            catch (Exception ex)
            {
                LogEvent($"Error recording signal performance: {ex.Message}", FKSLogLevel.Error);
            }
        }

        /// <summary>
        /// Update component performance adjustment
        /// </summary>
        private void UpdateComponentPerformance(string componentName, bool wasCorrect, double profitFactor)
        {
            if (!componentMetrics.TryGetValue(componentName, out var metrics))
                return;

            // Update metrics
            metrics.EvaluatedSignals++;
            if (wasCorrect)
            {
                metrics.CorrectPredictions++;
                metrics.TotalProfit += profitFactor;
            }

            // Calculate current accuracy
            double accuracy = (double)metrics.CorrectPredictions / metrics.EvaluatedSignals;

            // Adjust performance multiplier based on recent performance
            double currentAdjustment = performanceAdjustments.TryGetValue(componentName, out var adjustment) ? adjustment : 1.0;
            double targetAdjustment = accuracy > 0.6 ? 1.0 + ((accuracy - 0.6) * 0.5) : 0.7 + (accuracy * 0.5);

            // Smooth the adjustment change
            double newAdjustment = (currentAdjustment * 0.9) + (targetAdjustment * 0.1);
            newAdjustment = FKS_Utils.Clamp(newAdjustment, 0.5, 1.5);

            performanceAdjustments[componentName] = newAdjustment;

            LogEvent($"Performance adjustment for {componentName}: {currentAdjustment:F2} -> {newAdjustment:F2} " +
                    $"(Accuracy: {accuracy:P1})", FKSLogLevel.Debug);
        }

        /// <summary>
        /// Update recent performance tracking
        /// </summary>
        private void UpdateRecentPerformance(string componentName, ComponentSignal signal)
        {
            if (!componentMetrics.TryGetValue(componentName, out var metrics))
                return;

            // Update recent signal buffer
            if (metrics.RecentSignals == null)
                metrics.RecentSignals = new FKS_CircularBuffer<ComponentSignal>(20);

            metrics.RecentSignals.Add(signal);
        }

        #endregion

        #region Statistics and Reporting

        /// <summary>
        /// Get comprehensive signal coordinator statistics
        /// </summary>
        public SignalCoordinatorStatistics GetStatistics()
        {
            if (disposed) return new SignalCoordinatorStatistics();

            lock (signalLock)
            {
                var stats = new SignalCoordinatorStatistics
                {
                    TotalSignalsGenerated = totalSignalsGenerated,
                    QualitySignalsGenerated = qualitySignalsGenerated,
                    SignalsEvaluated = signalsEvaluated,
                    CorrectPredictions = correctPredictions,
                    RegisteredComponents = componentSignals.Count,
                    ActiveComponents = GetActiveSignals().Count,
                    ComponentMetrics = componentMetrics.Values.ToList(),
                    RecentSignals = signalHistory.GetLast(10),
                    ComponentWeights = baseWeights.ToDictionary(kv => kv.Key, kv => GetEffectiveWeight(kv.Key))
                };

                // Calculate derived statistics
                if (signalsEvaluated > 0)
                {
                    stats.OverallAccuracy = (double)correctPredictions / signalsEvaluated;
                }

                if (totalSignalsGenerated > 0)
                {
                    stats.QualityRatio = (double)qualitySignalsGenerated / totalSignalsGenerated;
                }

                return stats;
            }
        }

        /// <summary>
        /// Generate detailed diagnostic report
        /// </summary>
        public string GenerateDetailedReport()
        {
            var stats = GetStatistics();
            var sb = new StringBuilder();

            sb.AppendLine("=== FKS Signal Coordinator Report ===");
            sb.AppendLine($"Generated Signals: {stats.TotalSignalsGenerated} (Quality: {stats.QualitySignalsGenerated})");
            sb.AppendLine($"Evaluated Signals: {stats.SignalsEvaluated} (Accuracy: {stats.OverallAccuracy:P1})");
            sb.AppendLine($"Active Components: {stats.ActiveComponents}/{stats.RegisteredComponents}");
            sb.AppendLine();

            sb.AppendLine("Component Performance:");
            foreach (var metric in stats.ComponentMetrics.OrderByDescending(m => m.CurrentAccuracy))
            {
                double weight = stats.ComponentWeights.ContainsKey(metric.ComponentName)
                    ? stats.ComponentWeights[metric.ComponentName]
                    : 0.0;
                sb.AppendLine($"  {metric.ComponentName}: " +
                            $"Signals:{metric.TotalSignals} " +
                            $"Valid:{metric.ValidSignals} " +
                            $"Accuracy:{metric.CurrentAccuracy:P1} " +
                            $"Weight:{weight:F2}");
            }

            sb.AppendLine();
            sb.AppendLine("Recent Signals:");
            foreach (var signal in stats.RecentSignals.Take(5))
            {
                sb.AppendLine($"  {signal.Timestamp:HH:mm:ss} {signal.Direction} (Conf: {signal.Confidence:F2}, Quality: {signal.QualityScore:F2}, Components: {signal.ComponentCount})");
            }

            return sb.ToString();
        }

        #endregion

        #region Utility Methods

        /// <summary>
        /// Calculate variance of a list of values
        /// </summary>
        private double CalculateVariance(List<double> values)
        {
            if (values.Count < 2) return 0;

            double mean = values.Average();
            double sumSquaredDiffs = values.Sum(v => Math.Pow(v - mean, 2));
            return sumSquaredDiffs / values.Count;
        }

        /// <summary>
        /// Log events with timestamp
        /// </summary>
        private void LogEvent(string message, FKSLogLevel level)
        {
            if (disposed) return;

            var entry = new SignalLogEntry
            {
                Timestamp = DateTime.Now,
                Level = level,
                Message = message
            };

            eventLog.Add(entry);

            // Also log to debug output if enabled
            if (config.EnableDetailedLogging || level >= config.ConsoleLogLevel)
            {
                System.Diagnostics.Debug.WriteLine($"[FKS_SignalCoordinator] {level}: {message}");
            }
        }

        /// <summary>
        /// Get recent log entries
        /// </summary>
        public List<SignalLogEntry> GetRecentLogs(int count = 50, FKSLogLevel? minLevel = null)
        {
            var logs = eventLog.ToList();

            if (minLevel.HasValue)
            {
                logs = logs.Where(log => log.Level >= minLevel.Value).ToList();
            }

            return logs.OrderByDescending(log => log.Timestamp).Take(count).ToList();
        }

        #endregion

        #region Disposal

        public void Dispose()
        {
            if (!disposed)
            {
                disposed = true;

                LogEvent("Signal Coordinator disposing", FKSLogLevel.Information);

                componentSignals.Clear();
                lastSignalTimes.Clear();
                componentMetrics.Clear();
                signalHistory?.Dispose();
                eventLog?.Dispose();
            }
        }

        #endregion

        #region Supporting Classes

        /// <summary>
        /// Signal consensus calculation result
        /// </summary>
        private class SignalConsensus
        {
            public SignalDirection Direction { get; set; }
            public double WeightedScore { get; set; }
            public double Confidence { get; set; }
            public double QualityScore { get; set; }
            public List<string> Reasons { get; set; } = new List<string>();
        }

        /// <summary>
        /// Component performance metrics
        /// </summary>
        public class ComponentMetrics
        {
            public string ComponentName { get; set; }
            public DateTime FirstRegistration { get; set; }
            public DateTime LastSignalTime { get; set; }
            public int TotalSignals { get; set; }
            public int ValidSignals { get; set; }
            public int StrongSignals { get; set; }
            public int EvaluatedSignals { get; set; }
            public int CorrectPredictions { get; set; }
            public double TotalProfit { get; set; }
            public FKS_CircularBuffer<ComponentSignal> RecentSignals { get; set; }

            public double CurrentAccuracy => EvaluatedSignals > 0 ? (double)CorrectPredictions / EvaluatedSignals : 0;
            public double ValidSignalRatio => TotalSignals > 0 ? (double)ValidSignals / TotalSignals : 0;
            public TimeSpan TimeSinceLastSignal => DateTime.Now - LastSignalTime;
        }

        /// <summary>
        /// Signal coordinator statistics
        /// </summary>
        public class SignalCoordinatorStatistics
        {
            public int TotalSignalsGenerated { get; set; }
            public int QualitySignalsGenerated { get; set; }
            public int SignalsEvaluated { get; set; }
            public int CorrectPredictions { get; set; }
            public int RegisteredComponents { get; set; }
            public int ActiveComponents { get; set; }
            public double OverallAccuracy { get; set; }
            public double QualityRatio { get; set; }
            public List<ComponentMetrics> ComponentMetrics { get; set; } = new List<ComponentMetrics>();
            public List<CompositeSignal> RecentSignals { get; set; } = new List<CompositeSignal>();
            public Dictionary<string, double> ComponentWeights { get; set; } = new Dictionary<string, double>();
        }

        /// <summary>
        /// Signal log entry
        /// </summary>
        public class SignalLogEntry
        {
            public DateTime Timestamp { get; set; }
            public FKSLogLevel Level { get; set; }
            public string Message { get; set; }
        }

        #endregion
    }

    #endregion

    #region Component Management System (300 lines)

    /// <summary>
    /// Unified component management system for all FKS components
    /// Handles registration, health monitoring, and lifecycle management
    /// </summary>
    public sealed class FKS_ComponentManager : IDisposable
    {
        #region Singleton Pattern
        private static volatile FKS_ComponentManager instance;
        private static readonly object instanceLock = new object();

        public static FKS_ComponentManager Instance
        {
            get
            {
                if (instance == null)
                {
                    lock (instanceLock)
                    {
                        if (instance == null)
                            instance = new FKS_ComponentManager();
                    }
                }
                return instance;
            }
        }

        private FKS_ComponentManager()
        {
            InitializeHealthMonitoring();
        }
        #endregion

        #region Private Fields
        private readonly ConcurrentDictionary<string, ComponentInfo> components = new ConcurrentDictionary<string, ComponentInfo>();
        private readonly ConcurrentDictionary<string, ComponentHealthReport> healthReports = new ConcurrentDictionary<string, ComponentHealthReport>();
        private Timer healthCheckTimer;
        private readonly FKS_CircularBuffer<string> systemEvents = new FKS_CircularBuffer<string>(200);
        private volatile bool disposed = false;
        private DateTime startTime = DateTime.Now;
        #endregion

        #region Component Registration

        /// <summary>
        /// Register a component with the manager
        /// </summary>
        public bool RegisterComponent(string name, IFKSComponent component, double weight = 1.0)
        {
            if (disposed || string.IsNullOrEmpty(name) || component == null)
                return false;

            try
            {
                var info = new ComponentInfo
                {
                    Name = name,
                    Component = component,
                    Weight = FKS_Utils.Clamp(weight, 0.1, 2.0),
                    RegistrationTime = DateTime.Now,
                    Status = ComponentStatus.Initializing
                };

                bool added = components.TryAdd(name, info);
                if (added)
                {
                    // Initialize health report
                    healthReports.TryAdd(name, new ComponentHealthReport
                    {
                        ComponentName = name,
                        Status = ComponentStatus.Initializing,
                        LastUpdate = DateTime.Now
                    });

                    LogSystemEvent($"Component registered: {name} (Weight: {weight:F2})");

                    // Try to initialize the component
                    try
                    {
                        component.Initialize();
                        info.Status = ComponentStatus.Healthy;
                        UpdateHealthReport(name, ComponentStatus.Healthy, "Component initialized successfully");
                    }
                    catch (Exception ex)
                    {
                        info.Status = ComponentStatus.Failed;
                        UpdateHealthReport(name, ComponentStatus.Failed, $"Initialization failed: {ex.Message}");
                        LogSystemEvent($"Component initialization failed: {name} - {ex.Message}");
                    }
                }

                return added;
            }
            catch (Exception ex)
            {
                LogSystemEvent($"Error registering component {name}: {ex.Message}");
                return false;
            }
        }

        /// <summary>
        /// Unregister a component
        /// </summary>
        public bool UnregisterComponent(string name)
        {
            if (disposed || string.IsNullOrEmpty(name))
                return false;

            try
            {
                if (components.TryRemove(name, out var info))
                {
                    // Cleanup the component
                    try
                    {
                        info.Component?.Cleanup();
                    }
                    catch (Exception ex)
                    {
                        LogSystemEvent($"Error during component cleanup {name}: {ex.Message}");
                    }

                    healthReports.TryRemove(name, out _);
                    LogSystemEvent($"Component unregistered: {name}");
                    return true;
                }

                return false;
            }
            catch (Exception ex)
            {
                LogSystemEvent($"Error unregistering component {name}: {ex.Message}");
                return false;
            }
        }

        /// <summary>
        /// Get component by name
        /// </summary>
        public T GetComponent<T>(string name) where T : class, IFKSComponent
        {
            if (disposed || string.IsNullOrEmpty(name))
                return null;

            if (components.TryGetValue(name, out var info))
            {
                return info.Component as T;
            }

            return null;
        }

        /// <summary>
        /// Check if component is registered and healthy
        /// </summary>
        public bool IsComponentHealthy(string name)
        {
            if (disposed || string.IsNullOrEmpty(name))
                return false;

            if (components.TryGetValue(name, out var info))
            {
                return info.Status == ComponentStatus.Healthy;
            }

            return false;
        }

        #endregion

        #region Health Monitoring

        /// <summary>
        /// Initialize health monitoring system
        /// </summary>
        private void InitializeHealthMonitoring()
        {
            // Health check every 30 seconds
            healthCheckTimer = new Timer(PerformHealthCheck, null, TimeSpan.FromSeconds(30), TimeSpan.FromSeconds(30));
        }

        /// <summary>
        /// Perform health check on all components
        /// </summary>
        private void PerformHealthCheck(object state)
        {
            if (disposed) return;

            var now = DateTime.Now;
            var issues = new List<string>();

            foreach (var kvp in components)
            {
                var name = kvp.Key;
                var info = kvp.Value;

                try
                {
                    // Check component responsiveness
                    var previousStatus = info.Status;
                    var currentStatus = CheckComponentHealth(info);

                    if (currentStatus != previousStatus)
                    {
                        info.Status = currentStatus;
                        UpdateHealthReport(name, currentStatus, $"Status changed from {previousStatus} to {currentStatus}");
                        LogSystemEvent($"Component {name} status changed: {previousStatus} -> {currentStatus}");
                    }

                    // Attempt restart if failed
                    if (currentStatus == ComponentStatus.Failed &&
                        now - info.LastRestartAttempt > TimeSpan.FromMinutes(5))
                    {
                        AttemptComponentRestart(info);
                    }

                    // Track issues
                    if (currentStatus != ComponentStatus.Healthy)
                    {
                        issues.Add($"{name}: {currentStatus}");
                    }
                }
                catch (Exception ex)
                {
                    LogSystemEvent($"Error during health check for {name}: {ex.Message}");
                    UpdateHealthReport(name, ComponentStatus.Error, $"Health check error: {ex.Message}");
                }
            }

            // Log overall system health
            if (issues.Any())
            {
                LogSystemEvent($"System health issues: {string.Join(", ", issues)}");
            }
        }

        /// <summary>
        /// Check individual component health
        /// </summary>
        private ComponentStatus CheckComponentHealth(ComponentInfo info)
        {
            try
            {
                // Check if component is responsive by calling Update
                info.Component.Update();

                // Check last signal time if applicable
                var signal = info.Component.GetSignal();
                if (signal != null)
                {
                    info.LastSignalTime = DateTime.Now;
                    info.SignalCount++;
                }

                // Component is healthy if no exception and recent activity
                var timeSinceLastSignal = DateTime.Now - info.LastSignalTime;
                if (timeSinceLastSignal > TimeSpan.FromMinutes(15))
                {
                    return ComponentStatus.Warning; // No recent signals
                }

                return ComponentStatus.Healthy;
            }
            catch
            {
                info.ErrorCount++;
                return info.ErrorCount > 3 ? ComponentStatus.Failed : ComponentStatus.Warning;
            }
        }

        /// <summary>
        /// Attempt to restart a failed component
        /// </summary>
        private void AttemptComponentRestart(ComponentInfo info)
        {
            try
            {
                info.LastRestartAttempt = DateTime.Now;
                info.Component.Initialize();
                info.Status = ComponentStatus.Healthy;
                info.ErrorCount = 0;

                UpdateHealthReport(info.Name, ComponentStatus.Healthy, "Component restarted successfully");
                LogSystemEvent($"Successfully restarted component: {info.Name}");
            }
            catch (Exception ex)
            {
                info.Status = ComponentStatus.Failed;
                UpdateHealthReport(info.Name, ComponentStatus.Failed, $"Restart failed: {ex.Message}");
                LogSystemEvent($"Failed to restart component {info.Name}: {ex.Message}");
            }
        }

        /// <summary>
        /// Update health report for component
        /// </summary>
        private void UpdateHealthReport(string name, ComponentStatus status, string message)
        {
            var report = healthReports.GetOrAdd(name, _ => new ComponentHealthReport { ComponentName = name });

            report.Status = status;
            report.LastUpdate = DateTime.Now;
            report.StatusMessage = message;

            if (status == ComponentStatus.Failed || status == ComponentStatus.Error)
            {
                report.ErrorCount++;
            }

            // Calculate uptime
            if (components.TryGetValue(name, out var info))
            {
                report.Uptime = DateTime.Now - info.RegistrationTime;
            }
        }

        /// <summary>
        /// Get system health summary
        /// </summary>
        public SystemHealthSummary GetSystemHealth()
        {
            if (disposed) return new SystemHealthSummary();

            var totalComponents = components.Count;
            var healthyComponents = components.Values.Count(c => c.Status == ComponentStatus.Healthy);
            var warningComponents = components.Values.Count(c => c.Status == ComponentStatus.Warning);
            var failedComponents = components.Values.Count(c => c.Status == ComponentStatus.Failed);

            return new SystemHealthSummary
            {
                TotalComponents = totalComponents,
                HealthyComponents = healthyComponents,
                WarningComponents = warningComponents,
                FailedComponents = failedComponents,
                OverallHealthPercentage = totalComponents > 0 ? (double)healthyComponents / totalComponents * 100 : 100,
                SystemUptime = DateTime.Now - startTime,
                ComponentReports = healthReports.Values.ToList(),
                RecentEvents = systemEvents.GetLast(20)
            };
        }

        #endregion

        #region Utility Methods

        /// <summary>
        /// Log system events
        /// </summary>
        private void LogSystemEvent(string message)
        {
            var eventMessage = $"[{DateTime.Now:HH:mm:ss}] {message}";
            systemEvents.Add(eventMessage);
            System.Diagnostics.Debug.WriteLine($"[FKS_ComponentManager] {message}");
        }

        /// <summary>
        /// Get all registered component names
        /// </summary>
        public List<string> GetComponentNames()
        {
            return disposed ? new List<string>() : components.Keys.ToList();
        }

        /// <summary>
        /// Get component count by status
        /// </summary>
        public int GetComponentCountByStatus(ComponentStatus status)
        {
            return disposed ? 0 : components.Values.Count(c => c.Status == status);
        }

        #endregion

        #region Disposal

        public void Dispose()
        {
            if (!disposed)
            {
                disposed = true;

                healthCheckTimer?.Dispose();

                // Cleanup all components
                foreach (var info in components.Values)
                {
                    try
                    {
                        info.Component?.Cleanup();
                    }
                    catch (Exception ex)
                    {
                        LogSystemEvent($"Error during disposal cleanup: {ex.Message}");
                    }
                }

                components.Clear();
                healthReports.Clear();
                systemEvents?.Dispose();
            }
        }

        #endregion

        #region Supporting Classes

        /// <summary>
        /// Internal component information
        /// </summary>
        private class ComponentInfo
        {
            public string Name { get; set; }
            public IFKSComponent Component { get; set; }
            public double Weight { get; set; }
            public DateTime RegistrationTime { get; set; }
            public DateTime LastSignalTime { get; set; }
            public DateTime LastRestartAttempt { get; set; }
            public ComponentStatus Status { get; set; }
            public int SignalCount { get; set; }
            public int ErrorCount { get; set; }
        }

        /// <summary>
        /// System health summary
        /// </summary>
        public class SystemHealthSummary
        {
            public int TotalComponents { get; set; }
            public int HealthyComponents { get; set; }
            public int WarningComponents { get; set; }
            public int FailedComponents { get; set; }
            public double OverallHealthPercentage { get; set; }
            public TimeSpan SystemUptime { get; set; }
            public List<ComponentHealthReport> ComponentReports { get; set; } = new List<ComponentHealthReport>();
            public List<string> RecentEvents { get; set; } = new List<string>();

            public bool IsSystemHealthy => OverallHealthPercentage >= 80;
            public string HealthStatus => OverallHealthPercentage >= 90 ? "Excellent" :
                                        OverallHealthPercentage >= 80 ? "Good" :
                                        OverallHealthPercentage >= 60 ? "Fair" : "Poor";
        }

        #endregion
    }

    #endregion

    #region Master Plan Phase 1.3 - Unified Signal Structure

    /// <summary>
    /// Unified signal structure as specified in Master Plan Phase 1.3
    /// Standardized signal format for all FKS components
    /// </summary>
    public class UnifiedSignal
    {
        public SignalType Type { get; set; } // G, Top, ^, v
        public double Quality { get; set; } // 0-1
        public double WaveRatio { get; set; }
        public bool AOConfirmation { get; set; }
        public int SetupNumber { get; set; } // 1-4
        public int RecommendedContracts { get; set; }
        
        // Additional properties for enhanced functionality
        public DateTime Timestamp { get; set; } = DateTime.Now;
        public double Confidence { get; set; }
        public string Source { get; set; }
        public double Price { get; set; }
        public List<string> Reasons { get; set; } = new List<string>();
        public MarketRegime MarketRegime { get; set; }
        public SessionType Session { get; set; }
        
        // Calculated properties
        public bool IsHighQuality => Quality >= 0.8 && Confidence >= 0.7;
        public bool IsValidSignal => Quality >= 0.5 && !IsStale;
        public bool IsStale => (DateTime.Now - Timestamp).TotalMinutes > 10;
        public bool IsActionable => IsValidSignal && RecommendedContracts > 0;
        
        /// <summary>
        /// Get signal summary for logging
        /// </summary>
        public string GetSummary()
        {
            return $"{Type} | Setup:{SetupNumber} | Quality:{Quality:F2} | " +
                   $"Contracts:{RecommendedContracts} | AO:{(AOConfirmation ? "YES" : "NO")}";
        }
        
        /// <summary>
        /// Validate signal integrity
        /// </summary>
        public bool Validate()
        {
            return Quality >= 0 && Quality <= 1 &&
                   WaveRatio >= 0 &&
                   SetupNumber >= 1 && SetupNumber <= 4 &&
                   RecommendedContracts >= 0 &&
                   !string.IsNullOrEmpty(Source);
        }
    }

    /// <summary>
    /// Signal types as specified in master plan
    /// </summary>
    public enum SignalType
    {
        G,      // Green light signal
        Top,    // Top signal
        Up,     // ^ signal (up arrow)
        Down    // v signal (down arrow)
    }

    /// <summary>
    /// Signal factory for creating standardized unified signals
    /// </summary>
    public static class UnifiedSignalFactory
    {
        /// <summary>
        /// Create unified signal from AI component
        /// </summary>
        public static UnifiedSignal CreateFromAI(SignalType type, double quality, double waveRatio, 
            string source, double price, List<string> reasons = null)
        {
            return new UnifiedSignal
            {
                Type = type,
                Quality = quality,
                WaveRatio = waveRatio,
                Source = source,
                Price = price,
                Confidence = quality * 0.9, // AI confidence slightly lower than quality
                Reasons = reasons ?? new List<string>(),
                Timestamp = DateTime.Now
            };
        }

        /// <summary>
        /// Create unified signal from AO component
        /// </summary>
        public static UnifiedSignal CreateFromAO(SignalType type, double quality, bool confirmation,
            string source, double price, List<string> reasons = null)
        {
            return new UnifiedSignal
            {
                Type = type,
                Quality = quality,
                AOConfirmation = confirmation,
                Source = source,
                Price = price,
                Confidence = confirmation ? quality : quality * 0.8,
                Reasons = reasons ?? new List<string>(),
                Timestamp = DateTime.Now
            };
        }

        /// <summary>
        /// Create unified signal from setup detection
        /// </summary>
        public static UnifiedSignal CreateFromSetup(int setupNumber, SignalType type, double quality,
            double waveRatio, bool aoConfirmation, int recommendedContracts, string source, double price,
            List<string> reasons = null)
        {
            return new UnifiedSignal
            {
                Type = type,
                Quality = quality,
                WaveRatio = waveRatio,
                AOConfirmation = aoConfirmation,
                SetupNumber = setupNumber,
                RecommendedContracts = recommendedContracts,
                Source = source,
                Price = price,
                Confidence = CalculateConfidence(quality, waveRatio, aoConfirmation),
                Reasons = reasons ?? new List<string>(),
                Timestamp = DateTime.Now
            };
        }

        /// <summary>
        /// Calculate confidence based on signal components
        /// </summary>
        private static double CalculateConfidence(double quality, double waveRatio, bool aoConfirmation)
        {
            double confidence = quality * 0.6; // Base confidence from quality
            
            // Add wave ratio contribution
            if (waveRatio >= 1.5)
                confidence += 0.15;
            else if (waveRatio >= 1.0)
                confidence += 0.10;
            
            // Add AO confirmation contribution
            if (aoConfirmation)
                confidence += 0.20;
            
            return Math.Min(1.0, confidence);
        }

        /// <summary>
        /// Merge multiple signals into composite signal
        /// </summary>
        public static UnifiedSignal MergeSignals(List<UnifiedSignal> signals)
        {
            if (signals == null || signals.Count == 0)
                return null;

            if (signals.Count == 1)
                return signals[0];

            // Find dominant signal type
            var typeGroups = signals.GroupBy(s => s.Type);
            var dominantType = typeGroups.OrderByDescending(g => g.Count()).First().Key;

            // Calculate weighted averages
            double totalWeight = signals.Sum(s => s.Confidence);
            double avgQuality = signals.Sum(s => s.Quality * s.Confidence) / totalWeight;
            double avgWaveRatio = signals.Where(s => s.WaveRatio > 0).Sum(s => s.WaveRatio * s.Confidence) / 
                                  signals.Where(s => s.WaveRatio > 0).Sum(s => s.Confidence);
            
            // Check AO confirmation
            bool aoConfirmation = signals.Any(s => s.AOConfirmation);
            
            // Find best setup number
            int setupNumber = signals.Where(s => s.SetupNumber > 0).DefaultIfEmpty().Max(s => s?.SetupNumber ?? 0);
            
            // Calculate recommended contracts
            int recommendedContracts = (int)Math.Round(signals.Average(s => s.RecommendedContracts));

            // Merge reasons
            var allReasons = signals.SelectMany(s => s.Reasons).Distinct().ToList();

            return new UnifiedSignal
            {
                Type = dominantType,
                Quality = avgQuality,
                WaveRatio = avgWaveRatio,
                AOConfirmation = aoConfirmation,
                SetupNumber = setupNumber,
                RecommendedContracts = recommendedContracts,
                Source = "MERGED",
                Price = signals.First().Price,
                Confidence = avgQuality,
                Reasons = allReasons,
                Timestamp = DateTime.Now
            };
        }
    }

    /// <summary>
    /// Signal quality analyzer for unified signals
    /// </summary>
    public static class SignalQualityAnalyzer
    {
        /// <summary>
        /// Analyze signal quality with comprehensive scoring
        /// </summary>
        public static double AnalyzeSignalQuality(UnifiedSignal signal, MarketStateResult marketState)
        {
            if (signal == null || marketState == null)
                return 0;

            double score = 0;

            // Base quality contribution (40%)
            score += signal.Quality * 0.4;

            // Wave ratio contribution (20%)
            if (signal.WaveRatio >= 2.0)
                score += 0.2;
            else if (signal.WaveRatio >= 1.5)
                score += 0.15;
            else if (signal.WaveRatio >= 1.0)
                score += 0.10;

            // AO confirmation contribution (15%)
            if (signal.AOConfirmation)
                score += 0.15;

            // Market condition contribution (15%)
            if (marketState.IsHighQuality)
                score += 0.15;
            else if (marketState.IsTradeableCondition)
                score += 0.10;

            // Time-based contribution (10%)
            if (marketState.IsOptimalTime)
                score += 0.10;
            else if (marketState.Session == SessionType.NYSession || marketState.Session == SessionType.LondonSession)
                score += 0.05;

            return Math.Min(1.0, score);
        }

        /// <summary>
        /// Get signal grade based on quality
        /// </summary>
        public static string GetSignalGrade(double quality)
        {
            if (quality >= 0.9) return "A+";
            if (quality >= 0.85) return "A";
            if (quality >= 0.80) return "B+";
            if (quality >= 0.75) return "B";
            if (quality >= 0.70) return "C+";
            if (quality >= 0.65) return "C";
            if (quality >= 0.60) return "D";
            return "F";
        }

        /// <summary>
        /// Check if signal meets quality threshold for given market
        /// </summary>
        public static bool MeetsQualityThreshold(UnifiedSignal signal, string symbol)
        {
            if (signal == null || string.IsNullOrEmpty(symbol))
                return false;

            var marketConfig = MarketConfigurations.GetConfig(symbol);
            double threshold = marketConfig.GetAdjustedSignalThreshold();

            return signal.Quality >= threshold && signal.Validate();
        }
    }

    #endregion
}