import React from 'react';

const CryptoGuidelines = () => (
  <div>
    <h1>Crypto Exchange Module</h1>
    <h2>Market Characteristics</h2>
    <ul>
      <li><strong>Trading Hours</strong>: 24/7 market, optimal windows 8:00-11:00 UTC and 20:00-23:00 UTC</li>
      <li><strong>Volatility Patterns</strong>: Higher during US market open/close, news events, and weekends</li>
      <li><strong>Market Inefficiencies</strong>:
        <ul>
          <li>Exchange funding rate arbitrage</li>
          <li>Futures basis trading</li>
          <li>Altcoin market cycles (BTC dominance shifts)</li>
        </ul>
      </li>
    </ul>
    <h2>Operational Guidelines</h2>
    <ul>
      <li><strong>Exchanges</strong>: Binance, Kraken, Coinbase Pro (primary); FTX, Bybit (secondary)</li>
      <li><strong>Custody Protocol</strong>:
        <ul>
          <li>Maximum 20% of total crypto holdings on any exchange</li>
          <li>Hardware wallet storage for long-term positions</li>
          <li>2FA on all exchange accounts</li>
        </ul>
      </li>
    </ul>
    <h2>Position Parameters</h2>
    <ul>
      <li><strong>Position Sizing</strong>: 0.5-1% risk per trade</li>
      <li><strong>Leverage Limits</strong>:
        <ul>
          <li>BTC/ETH: Maximum 5x leverage</li>
          <li>Top 10 altcoins: Maximum 3x leverage</li>
          <li>Small caps: No leverage (spot only)</li>
        </ul>
      </li>
      <li><strong>Stop Loss Placement</strong>:
        <ul>
          <li>BTC/ETH: 5-7% from entry (adjusted for volatility)</li>
          <li>Altcoins: 10-15% from entry (adjusted for volatility)</li>
        </ul>
      </li>
    </ul>
  </div>
);

export default CryptoGuidelines;

