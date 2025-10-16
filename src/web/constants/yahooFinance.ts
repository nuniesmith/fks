// constants/yahooFinance.ts
// Hardcoded lists for Yahoo Finance Markets sections
// Source context: finance.yahoo.com/markets (structure captured from user-provided snapshot)

// Top-level Markets navigation sections as seen on Yahoo Finance
export type YahooMarketsSection =
  | 'overview'
  | 'world-indices'
  | 'futures'
  | 'bonds'
  | 'currencies'
  | 'options'
  | 'sectors'
  | 'stocks'
  | 'crypto'
  | 'private-companies'
  | 'etfs'
  | 'mutual-funds';

export const YAHOO_MARKETS_SECTIONS: YahooMarketsSection[] = [
  'overview',
  'world-indices',
  'futures',
  'bonds',
  'currencies',
  'options',
  'sectors',
  'stocks',
  'crypto',
  'private-companies',
  'etfs',
  'mutual-funds',
];

// Asset classes grouped from the Markets page
export type YahooAssetClass =
  | 'indices'
  | 'commodities'
  | 'currencies'
  | 'bonds'
  | 'sectors'
  | 'stocks'
  | 'crypto'
  | 'private-companies'
  | 'etfs'
  | 'mutual-funds'
  | 'futures'
  | 'options';

export interface AssetCategoryGroup<TName extends string = string> {
  key: TName;
  label: string;
  // Optional notes/context
  note?: string;
}

export interface YahooAssetClassDefinition {
  class: YahooAssetClass;
  label: string;
  categories: AssetCategoryGroup[];
}

// World Indices by region (categories only, not exhaustive symbols)
const INDICES_CATEGORIES: AssetCategoryGroup[] = [
  { key: 'americas', label: 'Americas' },
  { key: 'europe', label: 'Europe' },
  { key: 'asia', label: 'Asia' },
  { key: 'global', label: 'Global/World' },
];

// Commodities categories inferred from snapshot (energy, metals)
const COMMODITIES_CATEGORIES: AssetCategoryGroup[] = [
  { key: 'energy', label: 'Energy', note: 'Crude Oil, Brent, Natural Gas' },
  { key: 'metals', label: 'Metals', note: 'Gold, Silver, Copper' },
  // Additional groups exist on Yahoo (e.g., Agriculture, Softs), not shown in snapshot
];

// Currency categories
const CURRENCY_CATEGORIES: AssetCategoryGroup[] = [
  { key: 'majors', label: 'Major Pairs', note: 'EUR/USD, USD/JPY, GBP/USD, USD/CAD, USD/CHF, AUD/USD, NZD/USD' },
  { key: 'indices', label: 'Currency Indices', note: 'US Dollar Index, Euro Index, etc.' },
];

// Bonds categories
const BONDS_CATEGORIES: AssetCategoryGroup[] = [
  { key: 'us-treasuries', label: 'US Treasuries', note: '30Y, 10Y, 5Y, 2Y, 13W' },
  { key: 't-note-futures', label: 'T-Note Futures' },
];

// Sectors (GICS-like) as per snapshot
export type YahooSector =
  | 'technology'
  | 'financial-services'
  | 'consumer-cyclical'
  | 'communication-services'
  | 'industrials'
  | 'healthcare'
  | 'consumer-defensive'
  | 'energy'
  | 'basic-materials'
  | 'real-estate'
  | 'utilities';

export const YAHOO_SECTORS: { key: YahooSector; label: string }[] = [
  { key: 'technology', label: 'Technology' },
  { key: 'financial-services', label: 'Financial Services' },
  { key: 'consumer-cyclical', label: 'Consumer Cyclical' },
  { key: 'communication-services', label: 'Communication Services' },
  { key: 'industrials', label: 'Industrials' },
  { key: 'healthcare', label: 'Healthcare' },
  { key: 'consumer-defensive', label: 'Consumer Defensive' },
  { key: 'energy', label: 'Energy' },
  { key: 'basic-materials', label: 'Basic Materials' },
  { key: 'real-estate', label: 'Real Estate' },
  { key: 'utilities', label: 'Utilities' },
];

const SECTOR_CATEGORIES: AssetCategoryGroup[] = [
  { key: 'sectors-heatmap', label: 'Sectors Heatmap', note: 'Day return heatmap; market weights and YTD' },
  ...YAHOO_SECTORS.map((s) => ({ key: s.key, label: s.label })),
];

// Stocks list views/categories from snapshot
const STOCKS_CATEGORIES: AssetCategoryGroup[] = [
  { key: 'trending-now', label: 'Trending Now' },
  { key: 'most-active', label: 'Most Active' },
  { key: 'top-gainers', label: 'Top Gainers' },
  { key: 'top-losers', label: 'Top Losers' },
  { key: '52-week-gainers', label: '52 Week Gainers' },
  { key: '52-week-losers', label: '52 Week Losers' },
];

// Crypto list views/categories from snapshot
const CRYPTO_CATEGORIES: AssetCategoryGroup[] = [
  { key: 'all', label: 'All' },
  { key: 'most-active', label: 'Most Active' },
  { key: 'top-gainers', label: 'Top Gainers' },
  { key: 'top-losers', label: 'Top Losers' },
  { key: 'trending-now', label: 'Trending Now' },
];

// Private companies tables
const PRIVATE_COMPANY_CATEGORIES: AssetCategoryGroup[] = [
  { key: 'highest-valuation', label: 'Highest Valuation' },
  { key: '52-week-gainers', label: '52 Week Gainers' },
  { key: 'recently-funded', label: 'Recently Funded' },
  { key: 'most-funded', label: 'Most Funded' },
];

// ETFs tables
const ETF_CATEGORIES: AssetCategoryGroup[] = [
  { key: 'most-active', label: 'Most Active' },
  { key: 'top-gainers', label: 'Top Gainers' },
  { key: 'top-losers', label: 'Top Losers' },
  { key: 'top-performing', label: 'Top Performing' },
  { key: 'best-historical-performance', label: 'Best Historical Performance' },
  { key: 'top-etfs', label: 'Top ETFs' },
];

// Mutual Funds tables
const MUTUAL_FUND_CATEGORIES: AssetCategoryGroup[] = [
  { key: 'top-gainers', label: 'Top Gainers' },
  { key: 'top-losers', label: 'Top Losers' },
  { key: 'top-performing', label: 'Top Performing' },
  { key: 'best-historical-performance', label: 'Best Historical Performance' },
  { key: 'top-mutual-funds', label: 'Top Mutual Funds' },
];

// Futures (present in nav, specific table categories not in snapshot)
const FUTURES_CATEGORIES: AssetCategoryGroup[] = [
  { key: 'equity-index', label: 'Equity Index' },
  { key: 'rates', label: 'Rates' },
  { key: 'energy', label: 'Energy' },
  { key: 'metals', label: 'Metals' },
  { key: 'agriculture', label: 'Agriculture' },
];

// Options (present in nav; category names are generalized)
const OPTIONS_CATEGORIES: AssetCategoryGroup[] = [
  { key: 'most-active', label: 'Most Active' },
  { key: 'highest-iv', label: 'Highest Implied Volatility' },
  { key: 'largest-open-interest', label: 'Largest Open Interest' },
  { key: 'unusual-volume', label: 'Unusual Volume' },
];

export const YAHOO_ASSET_CLASS_DEFINITIONS: YahooAssetClassDefinition[] = [
  { class: 'indices', label: 'World Indices', categories: INDICES_CATEGORIES },
  { class: 'commodities', label: 'Commodities', categories: COMMODITIES_CATEGORIES },
  { class: 'currencies', label: 'Currencies', categories: CURRENCY_CATEGORIES },
  { class: 'bonds', label: 'Bonds', categories: BONDS_CATEGORIES },
  { class: 'sectors', label: 'Sectors', categories: SECTOR_CATEGORIES },
  { class: 'stocks', label: 'Stocks', categories: STOCKS_CATEGORIES },
  { class: 'crypto', label: 'Cryptocurrencies', categories: CRYPTO_CATEGORIES },
  { class: 'private-companies', label: 'Private Companies', categories: PRIVATE_COMPANY_CATEGORIES },
  { class: 'etfs', label: 'ETFs', categories: ETF_CATEGORIES },
  { class: 'mutual-funds', label: 'Mutual Funds', categories: MUTUAL_FUND_CATEGORIES },
  { class: 'futures', label: 'Futures', categories: FUTURES_CATEGORIES },
  { class: 'options', label: 'Options', categories: OPTIONS_CATEGORIES },
];

// News categories from Yahoo Finance (snapshot)
export type YahooNewsCategory =
  | 'latest'
  | 'stock-market'
  | 'originals'
  | 'tariff-updates'
  | 'newsletters'
  | 'economies'
  | 'premium-news'
  | 'earnings'
  | 'tech'
  | 'housing'
  | 'crypto'
  | 'mergers-ipos'
  | 'electric-vehicles'
  | 'inflation';

export const YAHOO_NEWS_CATEGORIES: { key: YahooNewsCategory; label: string }[] = [
  { key: 'latest', label: 'Latest' },
  { key: 'stock-market', label: 'Stock Market' },
  { key: 'originals', label: 'Originals' },
  { key: 'tariff-updates', label: 'Tariff Updates' },
  { key: 'newsletters', label: 'Newsletters' },
  { key: 'economies', label: 'Economies' },
  { key: 'premium-news', label: 'Premium News' },
  { key: 'earnings', label: 'Earnings' },
  { key: 'tech', label: 'Tech' },
  { key: 'housing', label: 'Housing' },
  { key: 'crypto', label: 'Crypto' },
  { key: 'mergers-ipos', label: 'Mergers & IPOs' },
  { key: 'electric-vehicles', label: 'Electric Vehicles' },
  { key: 'inflation', label: 'Inflation' },
];

// Research and tools pages from Yahoo Finance
export type YahooResearchPage =
  | 'screeners'
  | 'earnings-calendar'
  | 'economic-calendar'
  | 'stock-comparison';

export const YAHOO_RESEARCH_PAGES: { key: YahooResearchPage; label: string }[] = [
  { key: 'screeners', label: 'Screeners' },
  { key: 'earnings-calendar', label: 'Earnings Calendar' },
  { key: 'economic-calendar', label: 'Economic Calendar' },
  { key: 'stock-comparison', label: 'Stock Comparison' },
];

// Convenience aggregate with lookups by class
export const YAHOO_ASSET_CLASSES: Record<YahooAssetClass, YahooAssetClassDefinition> =
  YAHOO_ASSET_CLASS_DEFINITIONS.reduce((acc, def) => {
    acc[def.class] = def;
    return acc;
  }, {} as Record<YahooAssetClass, YahooAssetClassDefinition>);

export default {
  sections: YAHOO_MARKETS_SECTIONS,
  assetClassDefinitions: YAHOO_ASSET_CLASS_DEFINITIONS,
  assetClasses: YAHOO_ASSET_CLASSES,
  sectors: YAHOO_SECTORS,
  newsCategories: YAHOO_NEWS_CATEGORIES,
  researchPages: YAHOO_RESEARCH_PAGES,
};
