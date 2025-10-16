// Central constants (stub) used by analytics components. Expand with real domain data as needed.

export const YAHOO_ASSET_CLASS_DEFINITIONS = [
  {
    class: 'equities',
    label: 'Equities',
    categories: [
      { key: 'most_active', label: 'Most Active' },
      { key: 'gainers', label: 'Top Gainers' },
      { key: 'losers', label: 'Top Losers' },
      { key: 'trending', label: 'Trending Tickers' }
    ]
  },
  {
    class: 'etfs',
    label: 'ETFs',
    categories: [
      { key: 'top_etfs', label: 'Top ETFs' },
      { key: 'etf_trending', label: 'Trending ETFs' }
    ]
  },
  {
    class: 'crypto',
    label: 'Crypto',
    categories: [
      { key: 'crypto_top', label: 'Top Crypto' },
      { key: 'crypto_trending', label: 'Trending Crypto' }
    ]
  }
];

export const YAHOO_NEWS_CATEGORIES = [
  { key: 'general', label: 'General Market' },
  { key: 'earnings', label: 'Earnings' },
  { key: 'crypto', label: 'Crypto' },
  { key: 'analysis', label: 'Analysis' },
];

export const YAHOO_RESEARCH_PAGES = [
  { key: 'calendar', label: 'Economic Calendar' },
  { key: 'screener', label: 'Stock Screener' },
  { key: 'options', label: 'Options Chains' },
  { key: 'futures', label: 'Futures Overview' },
];
