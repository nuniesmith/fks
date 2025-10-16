// Clean Gamification Types for Milestone-Based System

// Import milestone types
export * from './milestones';

// Unified Experience Action Types (combining both old and new systems)
export type ExperienceAction = 
  // Accounts
  | 'ACCOUNT_CREATED'
  | 'ACCOUNT_OPENED'
  | 'ACCOUNT_VERIFIED'
  | 'FIRST_DEPOSIT'
  | 'ACCOUNT_FUNDED'
  // Learning & Documentation
  | 'LESSON_COMPLETED'
  | 'DOCUMENTATION_READ'
  | 'SKILL_MASTERED'
  | 'CERTIFICATION_EARNED'
  // Trading Actions
  | 'FIRST_TRADE'
  | 'PROFITABLE_TRADE'
  | 'FIRST_PROFIT'
  | 'DAILY_PROFIT_TARGET'
  | 'WEEKLY_PROFIT_TARGET'
  | 'MONTHLY_PROFIT_TARGET'
  | 'MONTHLY_TARGET_HIT'
  // Strategy Development
  | 'STRATEGY_CREATED'
  | 'STRATEGY_BACKTESTED'
  | 'STRATEGY_DEPLOYED'
  | 'STRATEGY_VALIDATED'
  // Risk Management
  | 'STOP_LOSS_HONORED'
  | 'DRAWDOWN_MANAGED'
  | 'MAX_RISK_ADHERED'
  | 'RISK_RULES_SET'
  // Prop Firm Progress
  | 'PROP_FIRM_PASSED'
  // Financial Milestones
  | 'EXPENSES_COVERED'
  | 'EXPENSE_MILESTONE'
  | 'PROFIT_MILESTONE'
  // Tax Optimization
  | 'TAX_OPTIMIZATION'
  | 'TFSA_CONTRIBUTION'
  | 'RRSP_CONTRIBUTION'
  // Phase Progress
  | 'PHASE_1_MILESTONE'
  | 'PHASE_2_UNLOCKED'
  | 'MILESTONE_COMPLETED';

export const XP_VALUES: Record<ExperienceAction, number> = {
  // Accounts
  ACCOUNT_CREATED: 100,
  ACCOUNT_OPENED: 200,
  ACCOUNT_VERIFIED: 150,
  FIRST_DEPOSIT: 200,
  ACCOUNT_FUNDED: 250,
  // Learning & Documentation
  LESSON_COMPLETED: 50,
  DOCUMENTATION_READ: 25,
  SKILL_MASTERED: 500,
  CERTIFICATION_EARNED: 1000,
  // Trading Actions
  FIRST_TRADE: 200,
  PROFITABLE_TRADE: 100,
  FIRST_PROFIT: 300,
  DAILY_PROFIT_TARGET: 150,
  WEEKLY_PROFIT_TARGET: 400,
  MONTHLY_PROFIT_TARGET: 500,
  MONTHLY_TARGET_HIT: 500,
  // Strategy Development
  STRATEGY_CREATED: 300,
  STRATEGY_BACKTESTED: 200,
  STRATEGY_DEPLOYED: 400,
  STRATEGY_VALIDATED: 600,
  // Risk Management
  STOP_LOSS_HONORED: 50,
  DRAWDOWN_MANAGED: 100,
  MAX_RISK_ADHERED: 75,
  RISK_RULES_SET: 200,
  // Prop Firm Progress
  PROP_FIRM_PASSED: 1000,
  // Financial Milestones
  EXPENSES_COVERED: 750,
  EXPENSE_MILESTONE: 1000,
  PROFIT_MILESTONE: 800,
  // Tax Optimization
  TAX_OPTIMIZATION: 750,
  TFSA_CONTRIBUTION: 400,
  RRSP_CONTRIBUTION: 400,
  // Phase Progress
  PHASE_1_MILESTONE: 2000,
  PHASE_2_UNLOCKED: 3000,
  MILESTONE_COMPLETED: 1500
};

// Level system interface
export interface UserLevel {
  id: string;
  title: string;
  description: string;
  requiredXP: number;
  titleColor: string;
  titleIcon: string;
  rewards: LevelReward[];
  level: number;
}

export interface LevelReward {
  type: 'badge' | 'feature' | 'discount' | 'access';
  name: string;
  description: string;
  value?: any;
}

// User levels data export
export const USER_LEVELS: UserLevel[] = [
  {
    id: 'novice',
    title: 'Novice Trader',
    description: 'Starting your trading journey',
    requiredXP: 0,
    titleColor: '#6B7280',
    titleIcon: '🌱',
    rewards: [],
    level: 1
  },
  {
    id: 'apprentice',
    title: 'Apprentice',
    description: 'Learning the basics',
    requiredXP: 1000,
    titleColor: '#3B82F6',
    titleIcon: '📚',
    rewards: [],
    level: 2
  },
  {
    id: 'trader',
    title: 'Trader',
    description: 'Executing regular trades',
    requiredXP: 5000,
    titleColor: '#10B981',
    titleIcon: '📈',
    rewards: [],
    level: 3
  },
  {
    id: 'professional',
    title: 'Professional',
    description: 'Consistent profitable trading',
    requiredXP: 15000,
    titleColor: '#F59E0B',
    titleIcon: '💼',
    rewards: [],
    level: 4
  },
  {
    id: 'expert',
    title: 'Expert',
    description: 'Advanced trading strategies',
    requiredXP: 35000,
    titleColor: '#8B5CF6',
    titleIcon: '⭐',
    rewards: [],
    level: 5
  },
  {
    id: 'master',
    title: 'Master Trader',
    description: 'Elite trading performance',
    requiredXP: 75000,
    titleColor: '#EF4444',
    titleIcon: '👑',
    rewards: [],
    level: 6
  }
];

// Phase system types
export interface Phase {
  id: string;
  title: string;
  description: string;
  objectives: PhaseObjective[];
  requirements: PhaseRequirement[];
  isActive: boolean;
  isCompleted: boolean;
  currentProgress: number;
  totalProgress: number;
  startedAt?: Date;
}

export interface PhaseObjective {
  id: string;
  title: string;
  description: string;
  category: string;
  target: number;
  current: number;
  unit: string;
  isCompleted: boolean;
  priority: 'low' | 'medium' | 'high' | 'critical';
}

export interface PhaseRequirement {
  id: string;
  description: string;
  isCompleted: boolean;
}

// Enhanced PropFirmAccount interface
export interface PropFirmAccount {
  id: string;
  firmName: string;
  accountType: string;
  balance: number;
  status: 'active' | 'pending' | 'failed' | 'passed' | 'funded';
  createdAt: Date;
  // Additional properties needed by components
  accountSize: number;
  phase: string;
  netProfit: number;
  grossProfit: number;
  currentBalance: number;
  profitTarget: number;
  maxDrawdown: number;
  isEnabled: boolean;
  startDate: Date;
  dailyLossLimit: number;
  payouts: any[];
}

export interface FinancialTarget {
  id: string;
  category: string;
  description: string;
  targetAmount: number;
  currentAmount: number;
  isActive: boolean;
  priority: 'low' | 'medium' | 'high' | 'critical';
}

export interface UserStreaks {
  dailyLogin: number;
  profitableDays: number;
  riskManagement: number;
  milestoneCompletion: number;
}

export interface UserStats {
  totalTrades: number;
  winRate: number;
  totalProfit: number;
  monthlyIncome: number;
  expensesCovered: boolean;
  accountsManaged: number;
  strategiesValidated: number;
  taxSavingsRealized: number;
}

// Updated UserProgress interface with missing properties
export interface UserProgress {
  userId: string;
  totalXP: number;
  currentTitle: string;
  titleColor: string;
  titleIcon: string;
  milestones: string[]; // Milestone IDs
  achievements: Achievement[];
  streaks: UserStreaks;
  stats: UserStats;
  lastActivity: Date;
  joinedAt: Date;
  // Add missing properties from old system
  currentLevel?: any;
  currentPhase?: string;
  phases?: Phase[];
  propFirmAccounts?: PropFirmAccount[];
  cryptoAccounts?: any[];
  financialTargets?: FinancialTarget[];
  xpToNextLevel?: number;
}

export interface ExperiencePoint {
  id: string;
  userId: string;
  action: ExperienceAction;
  points: number;
  timestamp: Date;
  description: string;
  metadata?: Record<string, any>;
}

export interface Achievement {
  id: string;
  title: string;
  description: string;
  category: AchievementCategory;
  points: number;
  icon: string;
  rarity: 'common' | 'uncommon' | 'rare' | 'epic' | 'legendary';
  requirements: AchievementRequirement[];
  unlocked: boolean;
  unlockedAt?: Date;
  progress?: number;
  maxProgress?: number;
  rewards?: string[];
  canadianTaxBenefit?: string;
}

export type AchievementCategory = 
  | 'account_management'
  | 'profit_generation'
  | 'tax_optimization'
  | 'milestone_completion'
  | 'strategy_mastery'
  | 'canadian_investing'
  | 'learning'
  | 'trading'
  | 'risk_management'
  | 'account_growth'
  | 'strategy_development'
  | 'milestones';

export interface AchievementRequirement {
  type: 'count' | 'value' | 'percentage' | 'milestone' | 'streak';
  target: number;
  metric: string;
  timeframe?: 'daily' | 'weekly' | 'monthly' | 'yearly' | 'all_time';
}

// User Title System (replaces level system)
export const USER_TITLES = [
  { xpRequired: 0, title: 'Trading Newcomer', color: '#6B7280', icon: '🌱' },
  { xpRequired: 1000, title: 'Account Builder', color: '#3B82F6', icon: '🏗️' },
  { xpRequired: 3000, title: 'Profit Seeker', color: '#10B981', icon: '📈' },
  { xpRequired: 6000, title: 'Expense Crusher', color: '#8B5CF6', icon: '💪' },
  { xpRequired: 10000, title: 'Tax Optimizer', color: '#F59E0B', icon: '🧮' },
  { xpRequired: 15000, title: 'Wealth Builder', color: '#EF4444', icon: '🏆' },
  { xpRequired: 25000, title: 'Canadian Tax Master', color: '#DC2626', icon: '🍁' },
  { xpRequired: 40000, title: 'Financial Freedom', color: '#7C3AED', icon: '💎' }
];