# Data Providers in fks_data

The data service exposes pluggable providers and a few convenience endpoints.

Endpoints

- GET /providers — list providers, whether enabled, and masked keys
- GET /providers/keys — masked env keys to help configure
- GET /sources — alias for older UIs
- GET /validation/results — placeholder (returns ok: true)
- GET /daily — daily OHLCV with optional provider
- GET /crypto/binance/klines — free Binance Futures klines
- GET /providers/polygon/aggs — polygon aggregates (needs key)
- GET /providers/alpha/daily — Alpha Vantage daily adjusted (needs key)
- GET /providers/cmc/quotes — CoinMarketCap (needs key)
- GET /futures/rithmic/ohlcv — Rithmic demo (mock) OHLCV

Examples

- Free Binance futures:
  - /crypto/binance/klines?symbol=BTCUSDT&interval=1m&limit=100
- Daily via yfinance (default):
  - /daily?symbol=GC=F&period=6mo
- Daily via polygon:
  - /daily?symbol=AAPL&period=6mo&provider=polygon&apikey=YOUR_KEY
- Daily via alpha vantage:
  - /daily?symbol=AAPL&period=6mo&provider=alpha&apikey=YOUR_KEY
- Rithmic demo (mock):
  - export RITHMIC_MOCK=1
  - /daily?symbol=GC=F&period=6mo&provider=rithmic

Rithmic (real) next steps

- Wire R Protocol SDK via `infrastructure/external/exchanges/rithmic_adapter.py`.
- Read env: RITHMIC_USERNAME, RITHMIC_PASSWORD, RITHMIC_APPKEY, RITHMIC_SYSTEM.
- Map bars to the OHLCV shape used elsewhere.
