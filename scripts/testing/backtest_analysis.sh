#!/bin/bash
# Backtest Analysis Script
# Analyzes signal quality and simulated performance from paper trading data

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

PSQL() {
    docker exec fks_postgres psql -U fks_user -d fks -tAc "$1"
}

PSQL_TABLE() {
    docker exec fks_postgres psql -U fks_user -d fks -c "$1"
}

echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}           FKS PAPER TRADING BACKTEST ANALYSIS                ${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo ""

# Test duration
FIRST_SIGNAL=$(PSQL "SELECT MIN(created_at) FROM signals")
LAST_SIGNAL=$(PSQL "SELECT MAX(created_at) FROM signals")
TOTAL_SIGNALS=$(PSQL "SELECT COUNT(*) FROM signals")
DURATION_HOURS=$(PSQL "SELECT EXTRACT(EPOCH FROM (MAX(created_at) - MIN(created_at))) / 3600 FROM signals")

echo -e "${YELLOW}📊 TEST SUMMARY${NC}"
echo "───────────────────────────────────────────────────────────────"
echo "Test Start:     $FIRST_SIGNAL"
echo "Test End:       $LAST_SIGNAL"
printf "Duration:       %.1f hours\n" "$DURATION_HOURS"
echo "Total Signals:  $TOTAL_SIGNALS"
echo ""

# Signal distribution by asset
echo -e "${YELLOW}📈 SIGNAL DISTRIBUTION BY ASSET${NC}"
echo "───────────────────────────────────────────────────────────────"
PSQL_TABLE "
SELECT 
    symbol,
    COUNT(*) as total,
    SUM(CASE WHEN signal_type = 'Buy' THEN 1 ELSE 0 END) as buys,
    SUM(CASE WHEN signal_type = 'Sell' THEN 1 ELSE 0 END) as sells,
    SUM(CASE WHEN signal_type = 'Hold' THEN 1 ELSE 0 END) as holds,
    ROUND(AVG(confidence)::numeric, 3) as avg_conf,
    ROUND(AVG(strength)::numeric, 3) as avg_str
FROM signals
GROUP BY symbol
ORDER BY total DESC;
"

# Confidence distribution
echo -e "${YELLOW}📉 CONFIDENCE DISTRIBUTION${NC}"
echo "───────────────────────────────────────────────────────────────"
PSQL_TABLE "
SELECT 
    CASE 
        WHEN confidence >= 0.9 THEN '0.90-1.00 (Excellent)'
        WHEN confidence >= 0.8 THEN '0.80-0.89 (Strong)'
        WHEN confidence >= 0.7 THEN '0.70-0.79 (Good)'
        WHEN confidence >= 0.6 THEN '0.60-0.69 (Moderate)'
        WHEN confidence >= 0.5 THEN '0.50-0.59 (Weak)'
        ELSE '< 0.50 (Low)'
    END as confidence_range,
    COUNT(*) as count,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER(), 1) as pct
FROM signals
GROUP BY 1
ORDER BY MIN(confidence) DESC;
"

# High-confidence trading opportunities
echo -e "${YELLOW}💰 HIGH-CONFIDENCE OPPORTUNITIES (conf >= 0.8)${NC}"
echo "───────────────────────────────────────────────────────────────"
PSQL_TABLE "
SELECT 
    symbol,
    signal_type,
    COUNT(*) as count,
    ROUND(AVG(confidence)::numeric, 3) as avg_conf,
    ROUND(AVG(strength)::numeric, 3) as avg_str
FROM signals
WHERE confidence >= 0.8 AND signal_type != 'Hold'
GROUP BY symbol, signal_type
ORDER BY avg_conf DESC;
"

# Signal timing analysis (hourly distribution)
echo -e "${YELLOW}⏰ HOURLY SIGNAL DISTRIBUTION${NC}"
echo "───────────────────────────────────────────────────────────────"
PSQL_TABLE "
SELECT 
    EXTRACT(HOUR FROM timestamp)::int as hour,
    COUNT(*) as signals,
    ROUND(AVG(confidence)::numeric, 3) as avg_conf,
    REPEAT('█', (COUNT(*)::float / (SELECT MAX(c) FROM (SELECT COUNT(*) c FROM signals GROUP BY EXTRACT(HOUR FROM timestamp)) t) * 20)::int) as bar
FROM signals
GROUP BY 1
ORDER BY 1;
"

# Strategy performance simulation
echo -e "${YELLOW}💵 SIMULATED STRATEGY PERFORMANCE${NC}"
echo "───────────────────────────────────────────────────────────────"

# Simulate trading with different confidence thresholds
echo "Simulating trades with different confidence thresholds..."
echo ""

for THRESHOLD in 0.5 0.6 0.7 0.8 0.9; do
    SIGNALS=$(PSQL "SELECT COUNT(*) FROM signals WHERE confidence >= $THRESHOLD AND signal_type != 'Hold'")
    BUYS=$(PSQL "SELECT COUNT(*) FROM signals WHERE confidence >= $THRESHOLD AND signal_type = 'Buy'")
    SELLS=$(PSQL "SELECT COUNT(*) FROM signals WHERE confidence >= $THRESHOLD AND signal_type = 'Sell'")
    AVG_CONF=$(PSQL "SELECT COALESCE(ROUND(AVG(confidence)::numeric, 3), 0) FROM signals WHERE confidence >= $THRESHOLD AND signal_type != 'Hold'")
    
    # Simple PnL estimation:
    # Assume 0.5% avg win for high-conf trades, 0.3% avg loss for low-conf
    # Win rate roughly correlates with confidence (75% at 0.9, 55% at 0.5)
    if [ "$THRESHOLD" = "0.9" ]; then WIN_RATE=75; AVG_WIN=0.8; AVG_LOSS=0.3; fi
    if [ "$THRESHOLD" = "0.8" ]; then WIN_RATE=70; AVG_WIN=0.6; AVG_LOSS=0.3; fi
    if [ "$THRESHOLD" = "0.7" ]; then WIN_RATE=65; AVG_WIN=0.5; AVG_LOSS=0.3; fi
    if [ "$THRESHOLD" = "0.6" ]; then WIN_RATE=60; AVG_WIN=0.4; AVG_LOSS=0.4; fi
    if [ "$THRESHOLD" = "0.5" ]; then WIN_RATE=55; AVG_WIN=0.3; AVG_LOSS=0.5; fi
    
    # Simplified expected value calculation
    WINS=$((SIGNALS * WIN_RATE / 100))
    LOSSES=$((SIGNALS - WINS))
    # Assume $1000 position size
    POSITION_SIZE=1000
    GROSS_WINS=$(echo "$WINS * $POSITION_SIZE * $AVG_WIN / 100" | bc 2>/dev/null || echo "0")
    GROSS_LOSSES=$(echo "$LOSSES * $POSITION_SIZE * $AVG_LOSS / 100" | bc 2>/dev/null || echo "0")
    NET_PNL=$(echo "$GROSS_WINS - $GROSS_LOSSES" | bc 2>/dev/null || echo "0")
    
    printf "Confidence >= %.1f: %4d signals | Buy: %4d | Sell: %4d | Est Win Rate: %d%% | Est PnL: \$%.0f\n" \
        "$THRESHOLD" "$SIGNALS" "$BUYS" "$SELLS" "$WIN_RATE" "$NET_PNL"
done

echo ""

# Best performing symbol analysis
echo -e "${YELLOW}🏆 SYMBOL PERFORMANCE RANKING${NC}"
echo "───────────────────────────────────────────────────────────────"
PSQL_TABLE "
WITH symbol_stats AS (
    SELECT 
        symbol,
        COUNT(*) as total_signals,
        SUM(CASE WHEN confidence >= 0.8 THEN 1 ELSE 0 END) as high_conf_signals,
        ROUND(AVG(confidence)::numeric, 3) as avg_confidence,
        ROUND(AVG(strength)::numeric, 3) as avg_strength,
        ROUND(STDDEV(confidence)::numeric, 4) as conf_stddev
    FROM signals
    WHERE signal_type != 'Hold'
    GROUP BY symbol
)
SELECT 
    symbol,
    total_signals,
    high_conf_signals,
    avg_confidence,
    avg_strength,
    conf_stddev,
    ROUND((avg_confidence * 100 - conf_stddev * 100)::numeric, 1) as quality_score
FROM symbol_stats
ORDER BY quality_score DESC;
"

# Recent trend analysis (last hour)
echo -e "${YELLOW}📊 RECENT TREND (Last Hour)${NC}"
echo "───────────────────────────────────────────────────────────────"
PSQL_TABLE "
SELECT 
    symbol,
    signal_type,
    COUNT(*) as count,
    ROUND(AVG(confidence)::numeric, 3) as avg_conf
FROM signals
WHERE created_at > NOW() - INTERVAL '1 hour'
  AND signal_type != 'Hold'
GROUP BY symbol, signal_type
ORDER BY symbol, signal_type;
"

# Trading recommendations
echo -e "${YELLOW}💡 TRADING RECOMMENDATIONS${NC}"
echo "───────────────────────────────────────────────────────────────"

HIGH_CONF=$(PSQL "SELECT COUNT(*) FROM signals WHERE confidence >= 0.8 AND signal_type != 'Hold'")
TOTAL_ACTIONABLE=$(PSQL "SELECT COUNT(*) FROM signals WHERE signal_type != 'Hold'")
HIGH_CONF_PCT=$(echo "scale=1; $HIGH_CONF * 100 / $TOTAL_ACTIONABLE" | bc)

echo "Based on the analysis:"
echo ""
if (( $(echo "$HIGH_CONF_PCT > 15" | bc -l) )); then
    echo -e "${GREEN}✓ Good signal quality - $HIGH_CONF_PCT% of signals are high-confidence (>=0.8)${NC}"
else
    echo -e "${YELLOW}⚠ Signal quality needs tuning - only $HIGH_CONF_PCT% high-confidence signals${NC}"
fi

# Check signal balance
BUY_COUNT=$(PSQL "SELECT COUNT(*) FROM signals WHERE signal_type = 'Buy'")
SELL_COUNT=$(PSQL "SELECT COUNT(*) FROM signals WHERE signal_type = 'Sell'")
BALANCE_RATIO=$(echo "scale=2; $BUY_COUNT / ($SELL_COUNT + 1)" | bc)

if (( $(echo "$BALANCE_RATIO > 0.8 && $BALANCE_RATIO < 1.2" | bc -l) )); then
    echo -e "${GREEN}✓ Good buy/sell balance - ratio: $BALANCE_RATIO${NC}"
elif (( $(echo "$BALANCE_RATIO > 1.2" | bc -l) )); then
    echo -e "${YELLOW}⚠ Buy-heavy signal distribution - ratio: $BALANCE_RATIO (consider shorting opportunities)${NC}"
else
    echo -e "${YELLOW}⚠ Sell-heavy signal distribution - ratio: $BALANCE_RATIO (bullish sentiment low)${NC}"
fi

echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}Backtest analysis complete!${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
