// Milestone-based Gamification System for Canadian Tax-Optimized Trading

export interface Milestone {
  id: string;
  title: string;
  description: string;
  category: MilestoneCategory;
  type: 'account' | 'financial' | 'tax' | 'investment' | 'strategy';
  target: number;
  current: number;
  unit: string;
  isCompleted: boolean;
  completedAt?: Date;
  priority: 'low' | 'medium' | 'high' | 'critical';
  canadianTaxBenefit?: string;
  nextSteps?: string[];
  relatedAccounts?: string[];
  estimatedTaxSavings?: number;
  xpReward: number;
  requirements: MilestoneRequirement[];
}

export type MilestoneCategory = 
  | 'prop_firm_scaling'      // Scale to multiple prop firm accounts
  | 'expense_coverage'       // Cover personal expenses through trading
  | 'tax_optimization'       // Canadian tax planning and optimization
  | 'long_term_wealth'       // RRSP, TFSA, RESP setup and management
  | 'account_diversification' // Multiple account types and brokers
  | 'strategy_development'   // Trading strategy creation and validation
  | 'profit_tracking'        // Comprehensive profit/loss tracking
  | 'business_setup';        // Business incorporation and structure

export interface MilestoneRequirement {
  id: string;
  description: string;
  type: 'count' | 'value' | 'percentage' | 'boolean';
  target: number | boolean;
  current: number | boolean;
  isCompleted: boolean;
  verificationMethod: 'automatic' | 'manual' | 'document_upload';
  evidence?: string[]; // optional references to documents or notes
  notes?: string;      // optional user-entered notes
}

export interface TaxOptimizedAccount {
  id: string;
  name: string;
  type: AccountType;
  broker: string;
  accountNumber: string;
  currency: 'CAD' | 'USD';
  taxCategory: CanadianTaxCategory;
  status: 'active' | 'inactive' | 'closed' | 'pending';
  openedAt: Date;
  closedAt?: Date;
  currentBalance: number;
  totalDeposits: number;
  totalWithdrawals: number;
  realizedProfits: number;
  unrealizedProfits: number;
  taxReporting: TaxReportingInfo;
  isActive: boolean;
  profitSharing?: PropFirmSplit;
  // Optional: strategies assigned to this account for execution/simulation
  assignedStrategies?: string[];
}

export type AccountType = 
  | 'prop_firm'              // Prop trading accounts
  | 'tfsa'                   // Tax-Free Savings Account
  | 'rrsp'                   // Registered Retirement Savings Plan
  | 'resp'                   // Registered Education Savings Plan
  | 'fhsa'                   // First Home Savings Account
  | 'margin'                 // Margin trading account
  | 'cash'                   // Cash trading account
  | 'business'               // Business trading account
  | 'crypto'                 // Cryptocurrency accounts
  | 'forex';                 // Foreign exchange accounts

export type CanadianTaxCategory = 
  | 'tax_free'               // TFSA, gains not taxable
  | 'tax_deferred'           // RRSP, deferred taxation
  | 'capital_gains'          // 50% of gains taxable
  | 'business_income'        // 100% taxable as business income
  | 'foreign_income'         // Foreign tax considerations
  | 'prop_firm_income';      // Prop firm profit sharing

export interface TaxReportingInfo {
  year: number;
  t4Reported: boolean;
  t5Reported: boolean;
  businessIncomeReported: boolean;
  foreignIncomeReported: boolean;
  capitalGainsReported: boolean;
  slips: TaxSlip[];
  estimatedTax: number;
  filedAt?: Date;
}

export interface TaxSlip {
  type: 'T4' | 'T5' | 'T3' | 'T1135' | 'Business';
  amount: number;
  source: string;
  reportingYear: number;
  issuedAt: Date;
}

export interface PropFirmSplit {
  firmPercentage: number;     // Usually 80%
  traderPercentage: number;   // Usually 20%
  monthlyTarget: number;
  currentMonthProfit: number;
  payout: 'monthly' | 'bi-weekly' | 'on-demand';
}

export interface FinancialSnapshot {
  totalNetWorth: number;
  liquidAssets: number;
  investmentAssets: number;
  monthlyIncome: number;
  monthlyExpenses: number;
  expenseCoverage: number;    // Percentage of expenses covered by trading
  taxOptimizationScore: number; // 0-100 score for tax efficiency
  canadianTaxSavings: number;  // Annual tax savings from optimization
  lastUpdated: Date;
}

export interface TaxOptimizationPlan {
  currentYear: number;
  tfsaContributionRoom: number;
  rrspContributionRoom: number;
  respContributionRoom: number;
  estimatedTaxSavings: number;
  recommendedActions: TaxAction[];
  nextReviewDate: Date;
}

export interface TaxAction {
  id: string;
  title: string;
  description: string;
  category: 'contribution' | 'withdrawal' | 'rebalancing' | 'incorporation';
  priority: 'low' | 'medium' | 'high' | 'urgent';
  deadline?: Date;
  estimatedSavings: number;
  completed: boolean;
}

export type PhaseType = 'foundation' | 'scaling' | 'optimization' | 'wealth_building';

export interface Phase {
  id: PhaseType;
  title: string;
  description: string;
  milestones: string[]; // References to milestone IDs
  isActive: boolean;
  isCompleted: boolean;
  startedAt?: Date;
  completedAt?: Date;
  canadianTaxFocus: string;
}

// Comprehensive milestones for Canadian tax-optimized trading
export const TRADING_MILESTONES: Milestone[] = [
  // Prop Firm Scaling Milestones
  {
    id: 'first_prop_account',
    title: 'First Prop Firm Account',
    description: 'Successfully open and fund your first prop firm account',
    category: 'prop_firm_scaling',
    type: 'account',
    target: 1,
    current: 0,
    unit: 'accounts',
    isCompleted: false,
    priority: 'high',
    xpReward: 500,
    requirements: [
      {
        id: 'account_opened',
        description: 'Prop firm account opened',
        type: 'boolean',
        target: true,
        current: false,
        isCompleted: false,
        verificationMethod: 'manual'
      }
    ]
  },
  {
    id: 'ten_prop_accounts',
    title: '10 Prop Firm Accounts',
    description: 'Scale to 10 active prop firm accounts',
    category: 'prop_firm_scaling',
    type: 'account',
    target: 10,
    current: 0,
    unit: 'accounts',
    isCompleted: false,
    priority: 'high',
    xpReward: 2000,
    requirements: [
      {
        id: 'ten_accounts_active',
        description: '10 prop firm accounts active',
        type: 'count',
        target: 10,
        current: 0,
        isCompleted: false,
        verificationMethod: 'automatic'
      }
    ]
  },
  {
    id: 'thirty_prop_accounts',
    title: '30 Prop Firm Accounts',
    description: 'Reach the target of 30 prop firm accounts',
    category: 'prop_firm_scaling',
    type: 'account',
    target: 30,
    current: 0,
    unit: 'accounts',
    isCompleted: false,
    priority: 'critical',
    xpReward: 5000,
    requirements: [
      {
        id: 'thirty_accounts_active',
        description: '30 prop firm accounts active',
        type: 'count',
        target: 30,
        current: 0,
        isCompleted: false,
        verificationMethod: 'automatic'
      }
    ]
  },

  // Expense Coverage Milestones
  {
    id: 'partial_expense_coverage',
    title: '25% Expense Coverage',
    description: 'Cover 25% of monthly personal expenses through trading profits',
    category: 'expense_coverage',
    type: 'financial',
    target: 25,
    current: 0,
    unit: 'percentage',
    isCompleted: false,
    priority: 'high',
    xpReward: 1000,
    requirements: [
      {
        id: 'monthly_coverage_25',
        description: '25% of monthly expenses covered for 3 consecutive months',
        type: 'percentage',
        target: 25,
        current: 0,
        isCompleted: false,
        verificationMethod: 'automatic'
      }
    ]
  },
  {
    id: 'full_expense_coverage',
    title: '100% Expense Coverage',
    description: 'Fully cover all monthly personal expenses through trading profits',
    category: 'expense_coverage',
    type: 'financial',
    target: 100,
    current: 0,
    unit: 'percentage',
    isCompleted: false,
    priority: 'critical',
    canadianTaxBenefit: 'Convert to business income for tax optimization',
    xpReward: 3000,
    requirements: [
      {
        id: 'monthly_coverage_100',
        description: '100% of monthly expenses covered for 6 consecutive months',
        type: 'percentage',
        target: 100,
        current: 0,
        isCompleted: false,
        verificationMethod: 'automatic'
      }
    ]
  },

  // Tax Optimization Milestones
  {
    id: 'tfsa_setup',
    title: 'TFSA Account Setup',
    description: 'Open and optimize Tax-Free Savings Account for Canadian tax benefits',
    category: 'tax_optimization',
    type: 'tax',
    target: 1,
    current: 0,
    unit: 'accounts',
    isCompleted: false,
    priority: 'high',
    canadianTaxBenefit: 'Tax-free growth on investments',
    estimatedTaxSavings: 2000,
    xpReward: 750,
    requirements: [
      {
        id: 'tfsa_opened',
        description: 'TFSA account opened',
        type: 'boolean',
        target: true,
        current: false,
        isCompleted: false,
        verificationMethod: 'document_upload'
      }
    ]
  },
  {
    id: 'rrsp_setup',
    title: 'RRSP Account Setup',
    description: 'Open and optimize Registered Retirement Savings Plan',
    category: 'tax_optimization',
    type: 'tax',
    target: 1,
    current: 0,
    unit: 'accounts',
    isCompleted: false,
    priority: 'high',
    canadianTaxBenefit: 'Tax deduction and deferred growth',
    estimatedTaxSavings: 3000,
    xpReward: 750,
    requirements: [
      {
        id: 'rrsp_opened',
        description: 'RRSP account opened',
        type: 'boolean',
        target: true,
        current: false,
        isCompleted: false,
        verificationMethod: 'document_upload'
      }
    ]
  },
  {
    id: 'business_incorporation',
    title: 'Business Incorporation',
    description: 'Incorporate trading business for tax optimization',
    category: 'business_setup',
    type: 'tax',
    target: 1,
    current: 0,
    unit: 'business',
    isCompleted: false,
    priority: 'medium',
    canadianTaxBenefit: 'Small business tax rate (11.5% vs 26.67%)',
    estimatedTaxSavings: 8000,
    xpReward: 2000,
    requirements: [
      {
        id: 'business_registered',
        description: 'Business incorporated with CRA',
        type: 'boolean',
        target: true,
        current: false,
        isCompleted: false,
        verificationMethod: 'document_upload'
      }
    ]
  },

  // Long-term Wealth Building
  {
    id: 'first_long_term_investment',
    title: 'First Long-term Investment',
    description: 'Set up first long-term investment account separate from trading',
    category: 'long_term_wealth',
    type: 'investment',
    target: 1,
    current: 0,
    unit: 'accounts',
    isCompleted: false,
    priority: 'medium',
    xpReward: 1000,
    requirements: [
      {
        id: 'investment_account_opened',
        description: 'Long-term investment account opened',
        type: 'boolean',
        target: true,
        current: false,
        isCompleted: false,
        verificationMethod: 'manual'
      }
    ]
  },
  {
    id: 'diversified_portfolio',
    title: 'Diversified Investment Portfolio',
    description: 'Build diversified portfolio across multiple asset classes',
    category: 'long_term_wealth',
    type: 'investment',
    target: 5,
    current: 0,
    unit: 'asset_classes',
    isCompleted: false,
    priority: 'medium',
    xpReward: 1500,
    requirements: [
      {
        id: 'asset_diversification',
        description: 'Investment across 5 different asset classes',
        type: 'count',
        target: 5,
        current: 0,
        isCompleted: false,
        verificationMethod: 'automatic'
      }
    ]
  },

  // Strategy Development
  {
    id: 'first_validated_strategy',
    title: 'First Validated Strategy',
    description: 'Develop and validate your first profitable trading strategy',
    category: 'strategy_development',
    type: 'strategy',
    target: 1,
    current: 0,
    unit: 'strategies',
    isCompleted: false,
    priority: 'high',
    xpReward: 1200,
    requirements: [
      {
        id: 'strategy_backtested',
        description: 'Strategy backtested with positive results',
        type: 'boolean',
        target: true,
        current: false,
        isCompleted: false,
        verificationMethod: 'automatic'
      }
    ]
  },

  // Profit Tracking & Milestones
  {
    id: 'first_10k_profit',
    title: 'First $10,000 Profit',
    description: 'Achieve $10,000 in cumulative trading profits',
    category: 'profit_tracking',
    type: 'financial',
    target: 10000,
    current: 0,
    unit: 'CAD',
    isCompleted: false,
    priority: 'high',
    xpReward: 2000,
    requirements: [
      {
        id: 'cumulative_profit_10k',
        description: 'Cumulative trading profit of $10,000 CAD',
        type: 'value',
        target: 10000,
        current: 0,
        isCompleted: false,
        verificationMethod: 'automatic'
      }
    ]
  },
  {
    id: 'first_100k_profit',
    title: 'First $100,000 Profit',
    description: 'Achieve $100,000 in cumulative trading profits',
    category: 'profit_tracking',
    type: 'financial',
    target: 100000,
    current: 0,
    unit: 'CAD',
    isCompleted: false,
    priority: 'critical',
    xpReward: 5000,
    requirements: [
      {
        id: 'cumulative_profit_100k',
        description: 'Cumulative trading profit of $100,000 CAD',
        type: 'value',
        target: 100000,
        current: 0,
        isCompleted: false,
        verificationMethod: 'automatic'
      }
    ]
  }
];
