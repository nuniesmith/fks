// Gamification Types for FKS Trading Platform - Milestone-Based System

// Import milestone types
import type { 
  TaxOptimizedAccount, 
  FinancialSnapshot, 
  TaxOptimizationPlan, 
  PhaseType, 
  Phase 
} from './milestones';

export interface ExperiencePoint {
  id: string;
  userId: string;
  action: ExperienceAction;
  points: number;
  timestamp: Date;
  description: string;
  metadata?: Record<string, any>;
}

// Simplified XP actions focused on milestones
export type ExperienceAction = 
  // Accounts
  | 'ACCOUNT_OPENED'
  | 'FIRST_PROFIT'
  | 'MONTHLY_TARGET_HIT'
  | 'EXPENSE_MILESTONE'
  | 'TAX_OPTIMIZATION'
  | 'TFSA_CONTRIBUTION'
  | 'RRSP_CONTRIBUTION'
  | 'STRATEGY_VALIDATED'
  | 'PROFIT_MILESTONE'
  | 'MILESTONE_COMPLETED';

export const XP_VALUES: Record<ExperienceAction, number> = {
  ACCOUNT_OPENED: 200,
  FIRST_PROFIT: 300,
  MONTHLY_TARGET_HIT: 500,
  EXPENSE_MILESTONE: 1000,
  TAX_OPTIMIZATION: 750,
  TFSA_CONTRIBUTION: 400,
  RRSP_CONTRIBUTION: 400,
  STRATEGY_VALIDATED: 600,
  PROFIT_MILESTONE: 800,
  MILESTONE_COMPLETED: 1500
};

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
  | 'canadian_investing';

export interface AchievementRequirement {
  type: 'count' | 'value' | 'percentage' | 'milestone';
  target: number;
  metric: string;
  timeframe?: 'daily' | 'weekly' | 'monthly' | 'yearly' | 'all_time';
}

// Simplified user progress without level locks
export interface UserProgress {
  userId: string;
  totalXP: number;
  currentTitle: string;
  titleColor: string;
  titleIcon: string;
  completedMilestones: string[]; // Milestone IDs
  achievements: Achievement[];
  accounts: TaxOptimizedAccount[];
  financialSnapshot: FinancialSnapshot;
  taxOptimizationPlan: TaxOptimizationPlan;
  currentPhase: PhaseType;
  phases: Phase[];
  streaks: UserStreaks;
  stats: UserStats;
  lastActivity: Date;
  joinedAt: Date;
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

// User titles based on XP and achievements rather than levels
export interface UserTitle {
  id: string;
  title: string;
  description: string;
  color: string;
  icon: string;
  requiredXP: number;
  requiredMilestones?: string[];
  benefits: string[];
}

export const USER_TITLES: UserTitle[] = [
  { 
    id: 'newcomer', 
    title: 'Trading Newcomer', 
    description: 'Starting your Canadian trading journey', 
    requiredXP: 0, 
    color: 'gray', 
    icon: '🌱', 
    benefits: ['Access to milestone tracking', 'Basic Canadian tax guides'] 
  },
  { 
    id: 'apprentice', 
    title: 'Tax-Smart Apprentice', 
    description: 'Learning tax-optimized trading', 
    requiredXP: 1000, 
    color: 'blue', 
    icon: '🇨🇦', 
    benefits: ['TFSA/RRSP guidance', 'Expense tracking tools'] 
  },
  { 
    id: 'prop_trader', 
    title: 'Prop Firm Trader', 
    description: 'Active in prop firm accounts', 
    requiredXP: 2500, 
    color: 'green', 
    icon: '📈', 
    benefits: ['Advanced account management', 'Profit optimization tools'],
    requiredMilestones: ['first_prop_account']
  },
  { 
    id: 'expense_covered', 
    title: 'Expense Master', 
    description: 'Covering personal expenses through trading', 
    requiredXP: 5000, 
    color: 'purple', 
    icon: '💰', 
    benefits: ['Business incorporation guidance', 'Advanced tax strategies'],
    requiredMilestones: ['partial_expense_coverage']
  },
  { 
    id: 'tax_optimizer', 
    title: 'Tax Optimization Expert', 
    description: 'Maximizing Canadian tax benefits', 
    requiredXP: 7500, 
    color: 'orange', 
    icon: '🏛️', 
    benefits: ['Professional tax guidance', 'Business structure optimization'],
    requiredMilestones: ['tfsa_setup', 'rrsp_setup']
  },
  { 
    id: 'wealth_builder', 
    title: 'Wealth Builder', 
    description: 'Building long-term Canadian wealth', 
    requiredXP: 12000, 
    color: 'red', 
    icon: '🏗️', 
    benefits: ['Investment portfolio guidance', 'Estate planning resources'],
    requiredMilestones: ['full_expense_coverage', 'first_long_term_investment']
  },
  { 
    id: 'financial_freedom', 
    title: 'Financial Freedom Achiever', 
    description: 'Achieved true financial independence', 
    requiredXP: 25000, 
    color: 'gold', 
    icon: '🗽', 
    benefits: ['All features unlocked', 'Mentorship opportunities'],
    requiredMilestones: ['thirty_prop_accounts', 'diversified_portfolio', 'first_100k_profit']
  }
];
