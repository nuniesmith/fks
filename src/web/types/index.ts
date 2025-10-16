// types/index.ts - Centralized type definitions
export interface LogEntry {
  timestamp: string;
  message: string;
  type: 'info' | 'error' | 'success' | 'warning';
}

export interface SystemStatus {
  buildApi: boolean;
  dockerServices: boolean;
}

export type BuildStatus = 'idle' | 'building' | 'success' | 'error';
export type PackageStatus = 'idle' | 'building' | 'success' | 'error';

export interface FileItem {
  name: string;
  description: string;
  template: string;
}

export interface ProjectFiles {
  indicators: FileItem[];
  strategies: FileItem[];
  addons: FileItem[];
}

export interface ApiResponse {
  success: boolean;
  error?: string;
  stdout?: string;
  stderr?: string;
  size?: number;
}

// Canadian Investment Account Types
export type AccountType = 
  | 'prop-firm'           // Proprietary trading firms
  | 'personal-margin'     // Personal margin account
  | 'personal-cash'       // Personal cash account
  | 'tfsa'               // Tax-Free Savings Account
  | 'rrsp'               // Registered Retirement Savings Plan
  | 'spousal-rrsp'       // Spousal RRSP
  | 'lira'               // Locked-in Retirement Account
  | 'locked-in-rsp'      // Locked-In Retirement Savings Plan
  | 'rif'                // Retirement Income Fund
  | 'lif'                // Life Income Fund
  | 'fhsa'               // First Home Savings Account
  | 'resp'               // Registered Education Savings Plan
  | 'rdsp'               // Registered Disability Savings Plan
  | 'fx-cfd'             // Foreign Exchange & CFD
  | 'corporate-margin'   // Corporate margin account
  | 'corporate-cash'     // Corporate cash account
  | 'partnership'        // Partnership account
  | 'trust'              // Trust account
  | 'demo';              // Demo/paper trading

export interface CanadianAccountInfo {
  type: AccountType;
  displayName: string;
  description: string;
  taxAdvantaged: boolean;
  contributionLimits: boolean;
  withdrawalRestrictions: boolean;
  category: 'retirement' | 'tax-free' | 'taxable' | 'corporate' | 'specialized' | 'demo';
}

export const ACCOUNT_TYPES: Record<AccountType, CanadianAccountInfo> = {
  'prop-firm': {
    type: 'prop-firm',
    displayName: 'Proprietary Trading',
    description: 'Professional trading with firm capital',
    taxAdvantaged: false,
    contributionLimits: false,
    withdrawalRestrictions: true,
    category: 'specialized'
  },
  'personal-margin': {
    type: 'personal-margin',
    displayName: 'Personal Margin',
    description: 'Individual margin account for leveraged trading',
    taxAdvantaged: false,
    contributionLimits: false,
    withdrawalRestrictions: false,
    category: 'taxable'
  },
  'personal-cash': {
    type: 'personal-cash',
    displayName: 'Personal Cash',
    description: 'Individual cash account for investments',
    taxAdvantaged: false,
    contributionLimits: false,
    withdrawalRestrictions: false,
    category: 'taxable'
  },
  'tfsa': {
    type: 'tfsa',
    displayName: 'TFSA',
    description: 'Tax-Free Savings Account - tax-free growth and withdrawals',
    taxAdvantaged: true,
    contributionLimits: true,
    withdrawalRestrictions: false,
    category: 'tax-free'
  },
  'rrsp': {
    type: 'rrsp',
    displayName: 'RRSP',
    description: 'Registered Retirement Savings Plan - tax-deferred growth',
    taxAdvantaged: true,
    contributionLimits: true,
    withdrawalRestrictions: true,
    category: 'retirement'
  },
  'spousal-rrsp': {
    type: 'spousal-rrsp',
    displayName: 'Spousal RRSP',
    description: 'RRSP for income splitting in retirement',
    taxAdvantaged: true,
    contributionLimits: true,
    withdrawalRestrictions: true,
    category: 'retirement'
  },
  'lira': {
    type: 'lira',
    displayName: 'LIRA',
    description: 'Locked-in Retirement Account from pension transfers',
    taxAdvantaged: true,
    contributionLimits: false,
    withdrawalRestrictions: true,
    category: 'retirement'
  },
  'locked-in-rsp': {
    type: 'locked-in-rsp',
    displayName: 'Locked-in RSP',
    description: 'Locked-In Retirement Savings Plan',
    taxAdvantaged: true,
    contributionLimits: false,
    withdrawalRestrictions: true,
    category: 'retirement'
  },
  'rif': {
    type: 'rif',
    displayName: 'RIF',
    description: 'Retirement Income Fund for retirement withdrawals',
    taxAdvantaged: true,
    contributionLimits: false,
    withdrawalRestrictions: true,
    category: 'retirement'
  },
  'lif': {
    type: 'lif',
    displayName: 'LIF',
    description: 'Life Income Fund from locked-in accounts',
    taxAdvantaged: true,
    contributionLimits: false,
    withdrawalRestrictions: true,
    category: 'retirement'
  },
  'fhsa': {
    type: 'fhsa',
    displayName: 'FHSA',
    description: 'First Home Savings Account - tax-free for home purchases',
    taxAdvantaged: true,
    contributionLimits: true,
    withdrawalRestrictions: true,
    category: 'specialized'
  },
  'resp': {
    type: 'resp',
    displayName: 'RESP',
    description: 'Registered Education Savings Plan for children\'s education',
    taxAdvantaged: true,
    contributionLimits: true,
    withdrawalRestrictions: true,
    category: 'specialized'
  },
  'rdsp': {
    type: 'rdsp',
    displayName: 'RDSP',
    description: 'Registered Disability Savings Plan',
    taxAdvantaged: true,
    contributionLimits: true,
    withdrawalRestrictions: true,
    category: 'specialized'
  },
  'fx-cfd': {
    type: 'fx-cfd',
    displayName: 'FX & CFD',
    description: 'Foreign Exchange and Contract for Difference trading',
    taxAdvantaged: false,
    contributionLimits: false,
    withdrawalRestrictions: false,
    category: 'specialized'
  },
  'corporate-margin': {
    type: 'corporate-margin',
    displayName: 'Corporate Margin',
    description: 'Corporate margin account for business investments',
    taxAdvantaged: false,
    contributionLimits: false,
    withdrawalRestrictions: false,
    category: 'corporate'
  },
  'corporate-cash': {
    type: 'corporate-cash',
    displayName: 'Corporate Cash',
    description: 'Corporate cash account for business investments',
    taxAdvantaged: false,
    contributionLimits: false,
    withdrawalRestrictions: false,
    category: 'corporate'
  },
  'partnership': {
    type: 'partnership',
    displayName: 'Partnership',
    description: 'Partnership investment account',
    taxAdvantaged: false,
    contributionLimits: false,
    withdrawalRestrictions: false,
    category: 'corporate'
  },
  'trust': {
    type: 'trust',
    displayName: 'Trust Account',
    description: 'Formal or informal trust investment account',
    taxAdvantaged: false,
    contributionLimits: false,
    withdrawalRestrictions: false,
    category: 'corporate'
  },
  'demo': {
    type: 'demo',
    displayName: 'Demo Account',
    description: 'Paper trading and practice account',
    taxAdvantaged: false,
    contributionLimits: false,
    withdrawalRestrictions: false,
    category: 'demo'
  }
};

// Financial Target Management
export interface FinancialTarget {
  id: string;
  name: string;
  description: string;
  targetAmount: number;
  period: 'daily' | 'weekly' | 'monthly' | 'yearly';
  category: 'living-expenses' | 'trading-capital' | 'savings' | 'emergency-fund' | 'investment-goal' | 'custom' | 'trading-income' | 'expense-coverage';
  priority: 'critical' | 'high' | 'medium' | 'low';
  isActive: boolean;
  createdAt: string;
  lastModified: string;
}

export interface FinancialProgress {
  targetId: string;
  currentAmount: number;
  progressPercentage: number;
  remainingAmount: number;
  projectedCompletion: string | null;
  onTrack: boolean;
  lastUpdated: string;
}

// Individual expense item for expense management
export interface ExpenseItem {
  id: string;
  category: 'housing' | 'transportation' | 'food' | 'utilities' | 'healthcare' | 'personal' | 'debt' | 'savings' | 'other';
  name: string;
  amount: number;
  frequency: 'daily' | 'weekly' | 'monthly' | 'yearly';
  isEssential: boolean;
  notes?: string;
}

export interface PersonalExpenses {
  housing: {
    rent: number;
    utilities: number;
    insurance: number;
    maintenance: number;
  };
  transportation: {
    carPayment: number;
    insurance: number;
    fuel: number;
    maintenance: number;
  };
  food: {
    groceries: number;
    diningOut: number;
  };
  utilities: {
    phone: number;
    internet: number;
    streaming: number;
  };
  healthcare: {
    insurance: number;
    medications: number;
    dental: number;
  };
  personal: {
    clothing: number;
    entertainment: number;
    hobbies: number;
    miscellaneous: number;
  };
  debt: {
    creditCards: number;
    loans: number;
    studentLoans: number;
  };
  savings: {
    emergency: number;
    retirement: number;
    investments: number;
  };
}

export interface TradingCapitalRequirement {
  minimumOperatingCapital: number;
  emergencyBuffer: number;
  scalingCapital: number;
  riskManagementBuffer: number;
}

export interface FinancialDashboard {
  totalMonthlyExpenses: number;
  projectedMonthlyIncome: number;
  surplusDeficit: number;
  expenseCoverage: number;
  totalCapitalRequired: number;
  activeTargetsCount: number;
  criticalTargetsCount: number;
  dailyTarget?: number;
  weeklyTarget?: number;
  monthlyTarget?: number;
  totalExpenses?: {
    daily: number;
    weekly: number;
    monthly: number;
    yearly: number;
  };
  tradingCapital?: TradingCapitalRequirement;
  currentProgress?: {
    daily: FinancialProgress;
    weekly: FinancialProgress;
    monthly: FinancialProgress;
  };
  projectedIncome?: {
    daily: number;
    weekly: number;
    monthly: number;
  };
  surplus?: {
    daily: number;
    weekly: number;
    monthly: number;
  };
}

export interface IncomeStream {
  id: string;
  name: string;
  source: 'trading' | 'employment' | 'business' | 'investment' | 'passive' | 'other';
  amount: number;
  frequency: 'daily' | 'weekly' | 'monthly' | 'yearly';
  reliability: 'guaranteed' | 'high' | 'medium' | 'low' | 'variable';
  isActive: boolean;
  accountType?: AccountType;
}

// Bitcoin and Crypto Tracking
export interface HardwareWallet {
  id: string;
  name: string;
  walletType: 'ledger' | 'trezor' | 'coldcard' | 'bitbox' | 'other';
  publicKey: string;
  description?: string;
  isActive: boolean;
  createdAt: string;
  lastUpdated: string;
}

export interface CryptoHolding {
  id: string;
  walletId: string;
  symbol: string;
  name: string;
  balance: number;
  valueCAD: number;
  valueUSD: number;
  lastUpdated: string;
  priceCAD: number;
  priceUSD: number;
  change24h: number;
}

export interface CryptoPortfolio {
  totalValue: number;
  totalValueCAD: number;
  totalValueUSD: number;
  holdings: CryptoHolding[];
  hardwareWallets: HardwareWallet[];
  wallets: HardwareWallet[];
  allocationStrategy: {
    monthlyDCAAmount: number;
    targetBitcoinPercentage: number;
    targetAltcoinPercentage: number;
    rebalanceFrequency: 'daily' | 'weekly' | 'monthly' | 'quarterly';
    profitAllocationPercentage: number;
  };
  allocationTarget: number; // Percentage of income to allocate
  monthlyAllocation: number; // CAD amount allocated monthly
  lastRebalanced: string;
  createdAt: string;
  lastUpdated: string;
}

// Futures Trading Accounts
export type FuturesFirm = 'take-profit-trader' | 'topstep' | 'apex' | 'interactive-brokers';

export interface FuturesAccount {
  id: string;
  firm: FuturesFirm;
  accountNumber: string;
  accountType: 'evaluation' | 'funded' | 'pro' | 'personal-futures' | 'portfolio-margin';
  capitalSize: number; // Account size in USD
  currentBalance: number;
  dailyProfit: number;
  weeklyProfit: number;
  monthlyProfit: number;
  maxDrawdown: number;
  currentDrawdown: number;
  profitTarget: number;
  isActive: boolean;
  status: 'active' | 'breached' | 'passed-evaluation' | 'withdrawn' | 'suspended' | 'good-standing';
  createdAt: string;
  lastTrade: string;
  // Interactive Brokers specific fields
  margin?: {
    initial: number;
    maintenance: number;
    available: number;
  };
  commissions?: {
    perContract: number;
    monthly: number;
  };
}

export interface FuturesScalingPlan {
  firm: FuturesFirm;
  maxAccounts: number;
  maxCapitalPerAccount: number;
  totalMaxCapital: number;
  currentAccounts: number;
  currentCapital: number;
  nextAccountThreshold: number; // Profit needed for next account
  scalingStrategy: 'conservative' | 'moderate' | 'aggressive';
  // Interactive Brokers specific
  portfolioMarginEligible?: boolean;
  minimumEquity?: number;
}

// Long-term Stock Investment Tracking
export interface StockHolding {
  id: string;
  symbol: string;
  name: string;
  shares: number;
  averageCost: number;
  currentPrice: number;
  marketValue: number;
  unrealizedGainLoss: number;
  unrealizedGainLossPercent: number;
  dividendYield: number;
  annualDividends: number;
  sector: string;
  accountId: string;
  accountType: AccountType;
  purchaseDate: string;
  lastUpdated: string;
}

export interface StockPortfolio {
  id: string;
  name: string;
  totalValue: number;
  totalCost: number;
  unrealizedGainLoss: number;
  unrealizedGainLossPercent: number;
  annualDividends: number;
  dividendYield: number;
  holdings: StockHolding[];
  accountType: AccountType;
  broker: 'interactive-brokers' | 'questrade' | 'td-direct' | 'rbc-direct' | 'other';
  currency: 'CAD' | 'USD';
  lastRebalanced: string;
  rebalanceStrategy: {
    frequency: 'monthly' | 'quarterly' | 'semi-annually' | 'annually' | 'never';
    threshold: number; // Percentage deviation trigger
    method: 'calendar' | 'threshold' | 'hybrid';
  };
  allocationTargets: {
    [sector: string]: number; // Target percentage per sector
  };
}

export interface TradingEcosystem {
  futuresAccounts: FuturesAccount[];
  scalingPlans: FuturesScalingPlan[];
  stockPortfolios: StockPortfolio[];
  cryptoPortfolio: CryptoPortfolio;
  totalTradingCapital: number;
  totalInvestmentValue: number;
  monthlyProfitTarget: number;
  personalExpensesCoverage: number; // Percentage from crypto
  longTermAllocation: number; // Percentage to Bitcoin/long-term
  stockAllocation: number; // Percentage to long-term stocks
  assetAllocation: {
    futures: number;
    stocks: number;
    crypto: number;
    cash: number;
  };
}

// Tax and Reporting
export interface TaxCategory {
  type: 'capital-gains' | 'business-income' | 'foreign-income' | 'crypto-gains' | 'futures-trading';
  description: string;
  rate: number; // Tax rate percentage
  accountTypes: AccountType[];
}

export interface TaxCalculation {
  totalIncome: number;
  capitalGains: number;
  businessIncome: number;
  foreignIncome: number;
  estimatedTax: number;
  taxEfficiency: number; // Percentage of income kept after tax
  recommendedAccountAllocation: Record<AccountType, number>;
}

export interface AlertConfig {
  id: string;
  type: 'target-achieved' | 'target-missed' | 'drawdown-warning' | 'profit-milestone' | 'crypto-allocation' | 'rebalance-needed' | 'stock-rebalance' | 'dividend-received';
  enabled: boolean;
  threshold: number;
  frequency: 'immediate' | 'daily' | 'weekly';
  channels: ('email' | 'sms' | 'push' | 'discord')[];
  message: string;
}

export interface TradingAlert {
  id: string;
  alertConfigId: string;
  triggered: boolean;
  triggeredAt: string;
  message: string;
  severity: 'info' | 'warning' | 'critical';
  acknowledged: boolean;
  data: Record<string, any>;
}

// API Integration Types
export interface APIConnection {
  id: string;
  name: string;
  type: 'futures-broker' | 'crypto-exchange' | 'blockchain' | 'tax-software' | 'bank' | 'stock-broker';
  provider: string; // e.g., 'topstep', 'binance', 'blockchain.info', 'turbotax', 'interactive-brokers'
  isConnected: boolean;
  lastSync: string;
  syncFrequency: 'real-time' | 'hourly' | 'daily';
  credentials: {
    apiKey?: string;
    secret?: string;
    passphrase?: string;
    sandbox?: boolean;
    username?: string; // For IB Gateway
    password?: string;
    clientId?: number; // For IB API
  };
  permissions: string[];
}

export interface IncomeTracking {
  source: APIConnection;
  income: number;
  date: string;
  type: 'trading-profit' | 'interest' | 'dividend' | 'crypto-gains' | 'futures-profit' | 'stock-gains' | 'options-profit';
  accountId: string;
  verified: boolean;
  taxCategory: TaxCategory['type'];
}