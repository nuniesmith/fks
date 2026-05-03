#!/bin/bash
PSQL() {
  docker exec fks_postgres psql -U fks_user -d fks -tAc "$1"
}

echo "=== PAPER BACKTEST ==="
echo "Total Signals: $(PSQL "SELECT count(*) FROM signals")"
echo "High Conf (>0.9): $(PSQL "SELECT count(*) FROM signals WHERE confidence > 0.9")"

echo -e "\nHigh Opps (>0.8 Buy/Sell):"
PSQL "SELECT symbol, signal_type, round((avg(confidence))::numeric,2) as conf, count(*) as n FROM signals WHERE confidence > 0.8 AND signal_type != 'Hold' GROUP BY symbol, signal_type ORDER BY conf DESC LIMIT 10"

buys=$(PSQL "SELECT count(*) FROM signals WHERE confidence > 0.9 AND signal_type = 'Buy'")
sells=$(PSQL "SELECT count(*) FROM signals WHERE confidence > 0.9 AND signal_type = 'Sell'")
est_buy=$((buys * 5))  # 0.5% gain * \$10 size
est_sell=$((sells * -3))  # 0.3% loss
net=$((est_buy + est_sell))
echo -e "\nEst PnL: Buy +\$est_buy | Sell \$est_sell | **Net +\$net USD**"
