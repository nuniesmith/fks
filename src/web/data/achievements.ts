// Enhanced Achievement System with Better Progression and Rewards
import type { Achievement, ExperienceAction } from '../types/gamification';

export const ENHANCED_ACHIEVEMENTS: Achievement[] = [
  // 🌱 BEGINNER ACHIEVEMENTS (Common - Level 1-2)
  {
    id: 'first_steps',
    title: 'First Steps',
    description: 'Welcome to FKS Trading! Complete your profile setup.',
    category: 'learning',
    points: 100,
    icon: '👋',
    rarity: 'common',
    requirements: [
      { type: 'count', target: 1, metric: 'profile_completed' }
    ],
    unlocked: false,
    rewards: ['Welcome bonus: +100 XP', 'Unlock: Progress Dashboard']
  },
  {
    id: 'documentation_reader',
    title: 'Knowledge Seeker',
    description: 'Read 5 documentation pages to understand the platform.',
    category: 'learning',
    points: 150,
    icon: '📚',
    rarity: 'common',
    requirements: [
      { type: 'count', target: 5, metric: 'docs_read' }
    ],
    unlocked: false,
    progress: 0,
    maxProgress: 5,
    rewards: ['Unlock: Trading Philosophy section', 'Badge: Scholar']
  },
  {
    id: 'simulation_starter',
    title: 'Simulation Pioneer',
    description: 'Execute your first trade in simulation mode.',
    category: 'trading',
    points: 200,
    icon: '🎯',
    rarity: 'common',
    requirements: [
      { type: 'count', target: 1, metric: 'first_trade' }
    ],
    unlocked: false,
    rewards: ['Unlock: Live Charts', 'Strategy template access']
  },

  // 🔥 INTERMEDIATE ACHIEVEMENTS (Uncommon - Level 3-4)
  {
    id: 'profitable_week',
    title: 'Profitable Week',
    description: 'Achieve positive returns for 7 consecutive trading days.',
    category: 'trading',
    points: 500,
    icon: '📈',
    rarity: 'uncommon',
    requirements: [
      { type: 'streak', target: 7, metric: 'profitable_days', timeframe: 'weekly' }
    ],
    unlocked: false,
    progress: 0,
    maxProgress: 7,
    rewards: ['Unlock: Analytics Dashboard', 'Risk multiplier +0.1x', 'Badge: Consistent Trader']
  },
  {
    id: 'strategy_creator',
    title: 'Strategy Architect',
    description: 'Create and backtest your first custom trading strategy.',
    category: 'strategy_development',
    points: 750,
    icon: '🏗️',
    rarity: 'uncommon',
    requirements: [
      { type: 'count', target: 1, metric: 'strategy_created' }
    ],
    unlocked: false,
    rewards: ['Unlock: Strategy Library', 'Advanced backtesting tools', 'Strategy sharing permissions']
  },
  {
    id: 'risk_manager',
    title: 'Risk Guardian',
    description: 'Follow risk management rules for 30 consecutive trades.',
    category: 'risk_management',
    points: 600,
    icon: '🛡️',
    rarity: 'uncommon',
    requirements: [
      { type: 'streak', target: 30, metric: 'risk_rules_followed' }
    ],
    unlocked: false,
    progress: 0,
    maxProgress: 30,
    rewards: ['Unlock: Advanced Risk Tools', 'Max position size +20%', 'Badge: Disciplined Trader']
  },

  // ⭐ ADVANCED ACHIEVEMENTS (Rare - Level 5-6)
  {
    id: 'prop_firm_challenger',
    title: 'Prop Firm Challenger',
    description: 'Pass your first prop firm challenge evaluation.',
    category: 'account_growth',
    points: 1000,
    icon: '🏆',
    rarity: 'rare',
    requirements: [
      { type: 'count', target: 1, metric: 'prop_firm_passed' }
    ],
    unlocked: false,
    rewards: ['Unlock: Prop Firm Manager', 'Phase 1 progression boost', 'Elite trader badge']
  },
  {
    id: 'monthly_profit_target',
    title: 'Monthly Profit Master',
    description: 'Achieve monthly profit target 3 times in a row.',
    category: 'trading',
    points: 1200,
    icon: '💰',
    rarity: 'rare',
    requirements: [
      { type: 'streak', target: 3, metric: 'monthly_profit_target', timeframe: 'monthly' }
    ],
    unlocked: false,
    progress: 0,
    maxProgress: 3,
    rewards: ['Unlock: Financial Targets Manager', 'Profit sharing bonus +5%', 'Badge: Profit Master']
  },
  {
    id: 'ten_prop_firms',
    title: 'Multi-Account Trader',
    description: 'Successfully manage 10 prop firm accounts simultaneously.',
    category: 'account_growth',
    points: 1500,
    icon: '🏢',
    rarity: 'rare',
    requirements: [
      { type: 'count', target: 10, metric: 'active_prop_firms' }
    ],
    unlocked: false,
    progress: 0,
    maxProgress: 10,
    rewards: ['Unlock: Advanced Portfolio Tools', 'Account management automation', 'Badge: Multi-Account Master']
  },

  // 💎 EXPERT ACHIEVEMENTS (Epic - Level 7)
  {
    id: 'ai_strategist',
    title: 'AI-Powered Strategist',
    description: 'Deploy 5 AI-enhanced strategies with 80%+ win rate.',
    category: 'strategy_development',
    points: 2000,
    icon: '🤖',
    rarity: 'epic',
    requirements: [
      { type: 'count', target: 5, metric: 'ai_strategies_deployed' },
      { type: 'percentage', target: 80, metric: 'strategy_win_rate' }
    ],
    unlocked: false,
    progress: 0,
    maxProgress: 5,
    rewards: ['Unlock: FKS Intelligence', 'AI model training access', 'Badge: AI Pioneer']
  },
  {
    id: 'expense_coverage_master',
    title: 'Financial Freedom Seeker',
    description: 'Cover all personal expenses through trading income for 6 months.',
    category: 'milestones',
    points: 2500,
    icon: '🎯',
    rarity: 'epic',
    requirements: [
      { type: 'streak', target: 6, metric: 'expenses_covered', timeframe: 'monthly' }
    ],
    unlocked: false,
    progress: 0,
    maxProgress: 6,
    rewards: ['Unlock: Phase 2 Progression', 'Canadian Account Guide', 'Badge: Financially Independent']
  },
  {
    id: 'twenty_prop_firms',
    title: 'Prop Firm Empire',
    description: 'Scale to 20 profitable prop firm accounts.',
    category: 'account_growth',
    points: 3000,
    icon: '👑',
    rarity: 'epic',
    requirements: [
      { type: 'count', target: 20, metric: 'profitable_prop_firms' }
    ],
    unlocked: false,
    progress: 0,
    maxProgress: 20,
    rewards: ['Phase 1 near completion', 'Institutional trading access', 'Badge: Empire Builder']
  },

  // 🌟 LEGENDARY ACHIEVEMENTS (Legendary - Level 8)
  {
    id: 'thirty_prop_firms',
    title: 'Phase 1 Champion',
    description: 'Achieve the ultimate goal: 30 profitable prop firm accounts.',
    category: 'milestones',
    points: 5000,
    icon: '🏅',
    rarity: 'legendary',
    requirements: [
      { type: 'count', target: 30, metric: 'profitable_prop_firms' }
    ],
    unlocked: false,
    progress: 0,
    maxProgress: 30,
    rewards: ['Phase 1 COMPLETE!', 'Unlock: Full Phase 2 Access', 'Legend status', 'Mentor privileges']
  },
  {
    id: 'trading_legend',
    title: 'Trading Legend',
    description: 'Maintain 85%+ win rate across 1000+ trades.',
    category: 'trading',
    points: 7500,
    icon: '🌟',
    rarity: 'legendary',
    requirements: [
      { type: 'count', target: 1000, metric: 'total_trades' },
      { type: 'percentage', target: 85, metric: 'overall_win_rate' }
    ],
    unlocked: false,
    progress: 0,
    maxProgress: 1000,
    rewards: ['Hall of Fame entry', 'Platform naming rights', 'Lifetime elite status']
  },
  {
    id: 'financial_independence',
    title: 'Financial Independence Master',
    description: 'Build sustainable wealth through Phase 2 investment strategies.',
    category: 'milestones',
    points: 10000,
    icon: '💎',
    rarity: 'legendary',
    requirements: [
      { type: 'value', target: 1000000, metric: 'net_worth' }
    ],
    unlocked: false,
    rewards: ['Ultimate achievement unlocked', 'Wealth building mastery', 'Legacy trader status']
  }
];

// XP Action to Achievement mapping for automatic unlocking
export const XP_ACTION_ACHIEVEMENTS: Record<ExperienceAction, string[]> = {
  'ACCOUNT_CREATED': ['first_steps'],
  'ACCOUNT_OPENED': ['first_steps'],
  'ACCOUNT_VERIFIED': ['first_steps'],
  'FIRST_DEPOSIT': ['simulation_starter'],
  'ACCOUNT_FUNDED': ['prop_firm_challenger'],
  'LESSON_COMPLETED': ['documentation_reader'],
  'DOCUMENTATION_READ': ['documentation_reader'],
  'SKILL_MASTERED': ['ai_strategist'],
  'CERTIFICATION_EARNED': ['trading_legend'],
  'FIRST_TRADE': ['simulation_starter'],
  'PROFITABLE_TRADE': ['profitable_week'],
  'FIRST_PROFIT': ['profitable_week'],
  'DAILY_PROFIT_TARGET': ['profitable_week'],
  'WEEKLY_PROFIT_TARGET': ['profitable_week'],
  'MONTHLY_PROFIT_TARGET': ['monthly_profit_target'],
  'MONTHLY_TARGET_HIT': ['monthly_profit_target'],
  'STRATEGY_CREATED': ['strategy_creator'],
  'STRATEGY_BACKTESTED': ['strategy_creator'],
  'STRATEGY_DEPLOYED': ['ai_strategist'],
  'STRATEGY_VALIDATED': ['ai_strategist'],
  'STOP_LOSS_HONORED': ['risk_manager'],
  'DRAWDOWN_MANAGED': ['risk_manager'],
  'MAX_RISK_ADHERED': ['risk_manager'],
  'RISK_RULES_SET': ['risk_manager'],
  'PROP_FIRM_PASSED': ['prop_firm_challenger', 'ten_prop_firms', 'twenty_prop_firms', 'thirty_prop_firms'],
  'EXPENSES_COVERED': ['expense_coverage_master'],
  'EXPENSE_MILESTONE': ['expense_coverage_master'],
  'PROFIT_MILESTONE': ['monthly_profit_target'],
  'TAX_OPTIMIZATION': [],
  'TFSA_CONTRIBUTION': [],
  'RRSP_CONTRIBUTION': [],
  'PHASE_1_MILESTONE': ['thirty_prop_firms'],
  'PHASE_2_UNLOCKED': ['financial_independence'],
  'MILESTONE_COMPLETED': ['thirty_prop_firms']
};

// Achievement unlocking logic
export const checkAchievementProgress = (
  action: ExperienceAction,
  userProgress: any,
  currentAchievements: Achievement[]
): string[] => {
  const potentialAchievements = XP_ACTION_ACHIEVEMENTS[action] || [];
  const newlyUnlocked: string[] = [];

  potentialAchievements.forEach(achievementId => {
    const achievement = currentAchievements.find(a => a.id === achievementId);
    if (!achievement || achievement.unlocked) return;

    // Check if requirements are met based on user progress
    const requirementsMet = achievement.requirements.every(req => {
      switch (req.type) {
        case 'count':
          return userProgress[req.metric] >= req.target;
        case 'streak':
          return userProgress[`${req.metric}_streak`] >= req.target;
        case 'percentage':
          return userProgress[req.metric] >= req.target;
        case 'value':
          return userProgress[req.metric] >= req.target;
        default:
          return false;
      }
    });

    if (requirementsMet) {
      newlyUnlocked.push(achievementId);
    }
  });

  return newlyUnlocked;
};

// Clean Achievements for Milestone-Based System
// (Removed duplicate re-import of types to avoid TS duplicate identifier errors)

export const ACHIEVEMENTS: Achievement[] = [
  {
    id: 'first_account',
    title: 'Account Pioneer',
    description: 'Open your first trading account',
    category: 'account_management',
    points: 200,
    icon: '🏦',
    rarity: 'common',
    requirements: [
      { type: 'count', target: 1, metric: 'accounts_opened' }
    ],
    unlocked: false,
    canadianTaxBenefit: 'Capital gains eligibility begins'
  },
  {
    id: 'first_profit',
    title: 'Profit Maker',
    description: 'Generate your first profitable trade',
    category: 'profit_generation',
    points: 300,
    icon: '💰',
    rarity: 'common',
    requirements: [
      { type: 'value', target: 1, metric: 'profitable_trades' }
    ],
    unlocked: false,
    canadianTaxBenefit: 'Begin capital gains tracking'
  },
  {
    id: 'tax_tfsa_setup',
    title: 'TFSA Master',
    description: 'Set up Tax-Free Savings Account optimization',
    category: 'tax_optimization',
    points: 750,
    icon: '🇨🇦',
    rarity: 'uncommon',
    requirements: [
      { type: 'count', target: 1, metric: 'tfsa_accounts_setup' }
    ],
    unlocked: false,
    canadianTaxBenefit: 'Tax-free growth on investments'
  },
  {
    id: 'expense_coverage',
    title: 'Expense Crusher',
    description: 'Cover monthly expenses with trading profits',
    category: 'milestone_completion',
    points: 1000,
    icon: '🎯',
    rarity: 'rare',
    requirements: [
      { type: 'milestone', target: 1, metric: 'monthly_expenses_covered' }
    ],
    unlocked: false,
    canadianTaxBenefit: 'Reduced taxable employment income dependency'
  },
  {
    id: 'rrsp_optimizer',
    title: 'RRSP Strategist',
    description: 'Optimize RRSP contributions for tax savings',
    category: 'tax_optimization',
    points: 750,
    icon: '📊',
    rarity: 'uncommon',
    requirements: [
      { type: 'count', target: 1, metric: 'rrsp_optimization_setup' }
    ],
    unlocked: false,
    canadianTaxBenefit: 'Tax deduction on contributions'
  },
  {
    id: 'business_incorporation',
    title: 'Business Builder',
    description: 'Set up business structure for trading',
    category: 'canadian_investing',
    points: 1500,
    icon: '🏢',
    rarity: 'epic',
    requirements: [
      { type: 'milestone', target: 1, metric: 'business_incorporated' }
    ],
    unlocked: false,
    canadianTaxBenefit: 'Small business tax rate eligibility'
  }
];

// Simplified XP mapping for milestone system
export const ACHIEVEMENT_XP_MAPPING: Record<string, ExperienceAction[]> = {
  'first_account': ['ACCOUNT_OPENED'],
  'first_profit': ['FIRST_PROFIT'],
  'tax_tfsa_setup': ['TFSA_CONTRIBUTION'],
  'expense_coverage': ['EXPENSE_MILESTONE'],
  'rrsp_optimizer': ['RRSP_CONTRIBUTION'],
  'business_incorporation': ['TAX_OPTIMIZATION']
};

// Achievement progress calculation
export function calculateAchievementProgress(
  achievement: Achievement,
  userStats: Record<string, number>
): number {
  const requirement = achievement.requirements[0];
  const current = userStats[requirement.metric] || 0;
  return Math.min(current / requirement.target, 1) * 100;
}
