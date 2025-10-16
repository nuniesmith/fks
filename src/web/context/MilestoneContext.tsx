import React, { createContext, useContext, useReducer, useEffect } from 'react';

import { 
  XP_VALUES,
  USER_TITLES
} from '../types/gamification-new';
import { 
  TRADING_MILESTONES
} from '../types/milestones';

import type { 
  UserProgress, 
  ExperienceAction} from '../types/gamification-new';
import type { 
  Milestone,
  TaxOptimizedAccount,
  FinancialSnapshot,
  TaxOptimizationPlan,
  MilestoneRequirement
} from '../types/milestones';
import type { ReactNode } from 'react';

interface MilestoneContextState {
  userProgress: UserProgress;
  availableMilestones: Milestone[];
  isLoading: boolean;
  error: string | null;
}

interface MilestoneContextValue extends MilestoneContextState {
  // Milestone actions
  completeMilestone: (milestoneId: string) => void;
  updateMilestoneProgress: (milestoneId: string, progress: number) => void;
  updateMilestoneRequirement: (milestoneId: string, requirementId: string, updates: Partial<MilestoneRequirement>) => void;
  
  // XP actions
  awardExperience: (action: ExperienceAction, metadata?: Record<string, any>) => void;
  
  // Account management
  addAccount: (account: TaxOptimizedAccount) => void;
  updateAccount: (accountId: string, updates: Partial<TaxOptimizedAccount>) => void;
  removeAccount: (accountId: string) => void;
  
  // Financial tracking
  updateFinancialSnapshot: (snapshot: Partial<FinancialSnapshot>) => void;
  updateTaxOptimizationPlan: (plan: Partial<TaxOptimizationPlan>) => void;
  
  // Achievement management
  unlockAchievement: (achievementId: string) => void;
  
  // Utility functions
  getMilestoneById: (id: string) => Milestone | undefined;
  getCompletedMilestones: () => Milestone[];
  getActiveMilestones: () => Milestone[];
  getNextPriorityMilestone: () => Milestone | undefined;
  calculateTaxOptimizationScore: () => number;
  getCanadianTaxSavings: () => number;
}

type MilestoneAction = 
  | { type: 'SET_LOADING'; payload: boolean }
  | { type: 'SET_ERROR'; payload: string | null }
  | { type: 'INIT_USER_PROGRESS'; payload: UserProgress }
  | { type: 'INIT_AVAILABLE_MILESTONES'; payload: Milestone[] }
  | { type: 'RECALC_DERIVED' }
  | { type: 'COMPLETE_MILESTONE'; payload: { milestoneId: string; completedAt: Date } }
  | { type: 'UPDATE_MILESTONE_PROGRESS'; payload: { milestoneId: string; progress: number } }
  | { type: 'UPDATE_MILESTONE_REQUIREMENT'; payload: { milestoneId: string; requirementId: string; updates: Partial<MilestoneRequirement> } }
  | { type: 'AWARD_EXPERIENCE'; payload: { action: ExperienceAction; points: number; metadata?: Record<string, any> } }
  | { type: 'ADD_ACCOUNT'; payload: TaxOptimizedAccount }
  | { type: 'UPDATE_ACCOUNT'; payload: { accountId: string; updates: Partial<TaxOptimizedAccount> } }
  | { type: 'REMOVE_ACCOUNT'; payload: string }
  | { type: 'UPDATE_FINANCIAL_SNAPSHOT'; payload: Partial<FinancialSnapshot> }
  | { type: 'UPDATE_TAX_OPTIMIZATION_PLAN'; payload: Partial<TaxOptimizationPlan> }
  | { type: 'UNLOCK_ACHIEVEMENT'; payload: { achievementId: string; unlockedAt: Date } }
  | { type: 'UPDATE_USER_TITLE'; payload: { title: string; color: string; icon: string } };

const initialFinancialSnapshot: FinancialSnapshot = {
  totalNetWorth: 0,
  liquidAssets: 0,
  investmentAssets: 0,
  monthlyIncome: 0,
  monthlyExpenses: 0,
  expenseCoverage: 0,
  taxOptimizationScore: 0,
  canadianTaxSavings: 0,
  lastUpdated: new Date()
};

const initialTaxOptimizationPlan: TaxOptimizationPlan = {
  currentYear: new Date().getFullYear(),
  tfsaContributionRoom: 6500, // 2024 limit
  rrspContributionRoom: 0,
  respContributionRoom: 0,
  estimatedTaxSavings: 0,
  recommendedActions: [],
  nextReviewDate: new Date(Date.now() + 90 * 24 * 60 * 60 * 1000) // 90 days from now
};

const initialUserProgress: UserProgress = {
  userId: 'demo-user',
  totalXP: 0,
  currentTitle: 'Trading Newcomer',
  titleColor: 'gray',
  titleIcon: '🌱',
  completedMilestones: [],
  achievements: [],
  accounts: [],
  financialSnapshot: initialFinancialSnapshot,
  taxOptimizationPlan: initialTaxOptimizationPlan,
  currentPhase: 'foundation',
  phases: [
    {
      id: 'foundation',
      title: 'Foundation Phase',
      description: 'Building the foundation of your Canadian trading journey',
      milestones: ['first_prop_account', 'tfsa_setup', 'first_validated_strategy'],
      isActive: true,
      isCompleted: false,
      canadianTaxFocus: 'Setting up tax-advantaged accounts'
    },
    {
      id: 'scaling',
      title: 'Scaling Phase',
      description: 'Scaling your trading operation and optimizing for taxes',
      milestones: ['ten_prop_accounts', 'partial_expense_coverage', 'rrsp_setup'],
      isActive: false,
      isCompleted: false,
      canadianTaxFocus: 'Tax optimization and business structure'
    },
    {
      id: 'optimization',
      title: 'Optimization Phase',
      description: 'Optimizing your entire financial and tax strategy',
      milestones: ['full_expense_coverage', 'business_incorporation', 'thirty_prop_accounts'],
      isActive: false,
      isCompleted: false,
      canadianTaxFocus: 'Advanced tax strategies and wealth building'
    },
    {
      id: 'wealth_building',
      title: 'Wealth Building Phase',
      description: 'Building long-term wealth through diversified investments',
      milestones: ['first_long_term_investment', 'diversified_portfolio', 'first_100k_profit'],
      isActive: false,
      isCompleted: false,
      canadianTaxFocus: 'Long-term wealth accumulation and estate planning'
    }
  ],
  streaks: {
    dailyLogin: 0,
    profitableDays: 0,
    riskManagement: 0,
    milestoneCompletion: 0
  },
  stats: {
    totalTrades: 0,
    winRate: 0,
    totalProfit: 0,
    monthlyIncome: 0,
    expensesCovered: false,
    accountsManaged: 0,
    strategiesValidated: 0,
    taxSavingsRealized: 0
  },
  lastActivity: new Date(),
  joinedAt: new Date()
};

const initialState: MilestoneContextState = {
  userProgress: initialUserProgress,
  availableMilestones: TRADING_MILESTONES,
  isLoading: false,
  error: null
};

function milestoneReducer(state: MilestoneContextState, action: MilestoneAction): MilestoneContextState {
  // Helper: compute best eligible user title
  const computeUserTitle = (progress: UserProgress) => {
    const completed = new Set(progress.completedMilestones);
    const eligible = USER_TITLES
      .filter(t => (t.requiredMilestones ? t.requiredMilestones.every(m => completed.has(m)) : true))
      .filter(t => progress.totalXP >= t.requiredXP)
      .sort((a, b) => a.requiredXP - b.requiredXP);
    const best = eligible[eligible.length - 1];
    if (best) {
      return { title: best.title, color: best.color, icon: best.icon };
    }
    return { title: progress.currentTitle, color: progress.titleColor, icon: progress.titleIcon };
  };

  // Helper: update prop firm scaling milestones based on accounts
  const applyPropFirmMilestones = (st: MilestoneContextState): MilestoneContextState => {
    const activePropAccounts = st.userProgress.accounts.filter(a => a.type === 'prop_firm' && a.isActive && a.status === 'active').length;
    const updates: Array<{ id: string; target: number }> = [
      { id: 'first_prop_account', target: 1 },
      { id: 'ten_prop_accounts', target: 10 },
      { id: 'thirty_prop_accounts', target: 30 },
    ];

    let newState: MilestoneContextState = st;
    for (const u of updates) {
      const m = newState.availableMilestones.find(m => m.id === u.id);
      if (m) {
        // Update milestone progress and its requirements
        const nextCurrent = Math.min(activePropAccounts, m.target);
        const updatedRequirements = (m.requirements || []).map((req) => {
          // Derive requirement progress from number of active prop accounts
          if (req.type === 'boolean') {
            const satisfied = activePropAccounts >= 1;
            return { ...req, current: satisfied, isCompleted: satisfied ? true : req.isCompleted };
          }
          if (req.type === 'count' || req.type === 'value' || req.type === 'percentage') {
            const cur = Math.min(activePropAccounts, typeof req.target === 'number' ? req.target : 0);
            const done = typeof req.target === 'number' ? cur >= req.target : false;
            return { ...req, current: cur, isCompleted: done ? true : req.isCompleted };
          }
          return req;
        });

        const updatedMilestone = { ...m, current: nextCurrent, requirements: updatedRequirements };
        newState = {
          ...newState,
          availableMilestones: newState.availableMilestones.map(x => x.id === u.id ? updatedMilestone : x)
        };

        // Complete if reached
        const alreadyCompleted = newState.userProgress.completedMilestones.includes(u.id);
        if (!alreadyCompleted && activePropAccounts >= u.target) {
          newState = {
            ...newState,
            availableMilestones: newState.availableMilestones.map(x => x.id === u.id ? { ...x, isCompleted: true, completedAt: new Date(), current: x.target } : x),
            userProgress: {
              ...newState.userProgress,
              completedMilestones: [...newState.userProgress.completedMilestones, u.id],
              totalXP: newState.userProgress.totalXP + (m.xpReward || 0),
              lastActivity: new Date(),
            }
          };
        }
      }
    }
    // After potential XP changes, recompute title
    const updatedTitle = computeUserTitle(newState.userProgress);
    newState = {
      ...newState,
      userProgress: {
        ...newState.userProgress,
        currentTitle: updatedTitle.title,
        titleColor: updatedTitle.color,
        titleIcon: updatedTitle.icon,
      }
    };
    return newState;
  };

  // Helper: update account-driven milestones (TFSA, RRSP, Business) based on account presence
  const applyAccountDrivenMilestones = (st: MilestoneContextState): MilestoneContextState => {
    const hasTFSA = st.userProgress.accounts.some(a => a.type === 'tfsa' && a.status !== 'closed');
    const hasRRSP = st.userProgress.accounts.some(a => a.type === 'rrsp' && a.status !== 'closed');
    const hasBusiness = st.userProgress.accounts.some(a => a.type === 'business' && a.status !== 'closed');

    const updates: Array<{ id: string; reqId: string; present: boolean }> = [
      { id: 'tfsa_setup', reqId: 'tfsa_opened', present: hasTFSA },
      { id: 'rrsp_setup', reqId: 'rrsp_opened', present: hasRRSP },
      { id: 'business_incorporation', reqId: 'business_registered', present: hasBusiness },
    ];

    let newState = st;
    for (const u of updates) {
      const m = newState.availableMilestones.find(x => x.id === u.id);
      if (!m) continue;
      const updatedReqs = m.requirements.map(r => {
        if (r.id !== u.reqId) return r;
        if (!u.present) return r;
        // Mark requirement satisfied if the account exists
        return { ...r, current: true, isCompleted: true };
      });

      let updatedM = { ...m, requirements: updatedReqs, current: u.present ? m.target : m.current };

      // If present and milestone not yet completed, complete it and award XP
      const alreadyCompleted = newState.userProgress.completedMilestones.includes(u.id) || m.isCompleted;
      if (u.present && !alreadyCompleted) {
        updatedM = { ...updatedM, isCompleted: true, completedAt: new Date(), current: m.target };
        const xpReward = m.xpReward || 0;
        newState = {
          ...newState,
          availableMilestones: newState.availableMilestones.map(x => x.id === u.id ? updatedM : x),
          userProgress: {
            ...newState.userProgress,
            completedMilestones: [...newState.userProgress.completedMilestones, u.id],
            totalXP: newState.userProgress.totalXP + xpReward,
            lastActivity: new Date(),
          }
        };
      } else {
        newState = {
          ...newState,
          availableMilestones: newState.availableMilestones.map(x => x.id === u.id ? updatedM : x)
        };
      }
    }
    // After potential XP changes, recompute title
    const updatedTitle = computeUserTitle(newState.userProgress);
    newState = {
      ...newState,
      userProgress: {
        ...newState.userProgress,
        currentTitle: updatedTitle.title,
        titleColor: updatedTitle.color,
        titleIcon: updatedTitle.icon,
      }
    };
    return newState;
  };

  switch (action.type) {
    case 'SET_LOADING':
      return { ...state, isLoading: action.payload };
    
    case 'SET_ERROR':
      return { ...state, error: action.payload };
    
    case 'INIT_USER_PROGRESS':
      return { ...state, userProgress: action.payload };
    
    case 'INIT_AVAILABLE_MILESTONES':
      return { ...state, availableMilestones: action.payload };

    case 'RECALC_DERIVED': {
      // Reapply derived milestone progress/completions from accounts and prop firm counts
      const afterProp = applyPropFirmMilestones(state);
      const afterAccounts = applyAccountDrivenMilestones(afterProp);
      return afterAccounts;
    }
    
    case 'COMPLETE_MILESTONE': {
      const { milestoneId, completedAt } = action.payload;
      
      // Update milestone in available milestones
      const updatedMilestones = state.availableMilestones.map(milestone => 
        milestone.id === milestoneId 
          ? { ...milestone, isCompleted: true, completedAt, current: milestone.target }
          : milestone
      );
      
      // Add to completed milestones if not already there
      const updatedCompletedMilestones = state.userProgress.completedMilestones.includes(milestoneId)
        ? state.userProgress.completedMilestones
        : [...state.userProgress.completedMilestones, milestoneId];
      
      // Award XP for milestone completion
      const milestone = state.availableMilestones.find(m => m.id === milestoneId);
      const xpReward = milestone?.xpReward || 0;

      const newUserProgress: UserProgress = {
        ...state.userProgress,
        completedMilestones: updatedCompletedMilestones,
        totalXP: state.userProgress.totalXP + xpReward,
        lastActivity: new Date()
      };
      const t = computeUserTitle(newUserProgress);
      return {
        ...state,
        availableMilestones: updatedMilestones,
        userProgress: {
          ...newUserProgress,
          currentTitle: t.title,
          titleColor: t.color,
          titleIcon: t.icon,
        }
      };
    }
    
    case 'UPDATE_MILESTONE_PROGRESS': {
      const { milestoneId, progress } = action.payload;
      
      const updatedMilestones = state.availableMilestones.map(milestone => 
        milestone.id === milestoneId 
          ? { ...milestone, current: Math.min(progress, milestone.target) }
          : milestone
      );
      
      return {
        ...state,
        availableMilestones: updatedMilestones
      };
    }
    
    case 'UPDATE_MILESTONE_REQUIREMENT': {
      const { milestoneId, requirementId, updates } = action.payload;

      // Find the milestone to update
      const target = state.availableMilestones.find(m => m.id === milestoneId);
      if (!target) return state;

      // Update requirements array with auto-complete for document uploads
      const updatedRequirements = target.requirements.map(req => {
        if (req.id !== requirementId) return req;
        const merged = { ...req, ...updates } as MilestoneRequirement;
        // If verification is document upload and evidence exists, auto-complete the requirement
        if (merged.verificationMethod === 'document_upload' && Array.isArray(merged.evidence) && merged.evidence.length > 0) {
          if (merged.type === 'boolean') {
            merged.current = true;
          } else if (typeof merged.target === 'number') {
            // Set progress to target for consistency
            merged.current = merged.target;
          }
          merged.isCompleted = true;
        }
        return merged;
      });

      // Compute progress percentage across requirements
      const ratios = updatedRequirements.map(req => {
        if (req.type === 'boolean') {
          return req.current === true ? 1 : 0;
        }
        const cur = typeof req.current === 'number' ? req.current : 0;
        const tgt = typeof req.target === 'number' ? req.target : 0;
        return tgt > 0 ? Math.min(cur / tgt, 1) : 0;
      });
      const progressPercent = ratios.length ? Math.max(...ratios) : 0;
      const newCurrent = Math.min(target.target, Math.round(progressPercent * target.target));

      // Determine if all requirements are completed
      const allReqsCompleted = updatedRequirements.every(r => r.isCompleted === true || (r.type !== 'boolean' && typeof r.current === 'number' && typeof r.target === 'number' && r.current >= r.target));

      // Build updated milestone
      const updatedMilestone: Milestone = {
        ...target,
        requirements: updatedRequirements,
        current: allReqsCompleted ? target.target : newCurrent,
        isCompleted: allReqsCompleted ? true : target.isCompleted,
        completedAt: allReqsCompleted ? (target.completedAt || new Date()) : target.completedAt
      };

      // Update milestones list
      let updatedMilestones = state.availableMilestones.map(m => m.id === milestoneId ? updatedMilestone : m);

      // If milestone just completed, award XP and mark in userProgress
      let newUserProgress = state.userProgress;
      if (allReqsCompleted && !state.userProgress.completedMilestones.includes(milestoneId)) {
        const xpReward = target.xpReward || 0;
        newUserProgress = {
          ...state.userProgress,
          completedMilestones: [...state.userProgress.completedMilestones, milestoneId],
          totalXP: state.userProgress.totalXP + xpReward,
          lastActivity: new Date()
        };
        // Ensure milestone in list is flagged completed with correct timestamp
        updatedMilestones = updatedMilestones.map(m => m.id === milestoneId ? { ...m, isCompleted: true, completedAt: new Date(), current: m.target } : m);
      }

      // Recompute user title if XP changed
      const t = computeUserTitle(newUserProgress);

      return {
        ...state,
        availableMilestones: updatedMilestones,
        userProgress: {
          ...newUserProgress,
          currentTitle: t.title,
          titleColor: t.color,
          titleIcon: t.icon,
        }
      };
    }
    
    case 'AWARD_EXPERIENCE': {
      const { action: experienceAction, points, metadata } = action.payload;

      const newUserProgress = {
        ...state.userProgress,
        totalXP: state.userProgress.totalXP + points,
        lastActivity: new Date()
      };
      const t = computeUserTitle(newUserProgress);
      return {
        ...state,
        userProgress: {
          ...newUserProgress,
          currentTitle: t.title,
          titleColor: t.color,
          titleIcon: t.icon,
        }
      };
    }
    
    case 'ADD_ACCOUNT': {
      const next: MilestoneContextState = {
        ...state,
        userProgress: {
          ...state.userProgress,
          accounts: [...state.userProgress.accounts, action.payload],
          stats: {
            ...state.userProgress.stats,
            accountsManaged: state.userProgress.stats.accountsManaged + 1
          }
        }
      };
  return applyAccountDrivenMilestones(applyPropFirmMilestones(next));
    }
    
    case 'UPDATE_ACCOUNT': {
      const { accountId, updates } = action.payload;
      const updatedAccounts = state.userProgress.accounts.map(account =>
        account.id === accountId ? { ...account, ...updates } : account
      );
      const next: MilestoneContextState = {
        ...state,
        userProgress: {
          ...state.userProgress,
          accounts: updatedAccounts
        }
      };
  return applyAccountDrivenMilestones(applyPropFirmMilestones(next));
    }
    
    case 'REMOVE_ACCOUNT': {
      const accountId = action.payload;
      const updatedAccounts = state.userProgress.accounts.filter(account => account.id !== accountId);
      const next: MilestoneContextState = {
        ...state,
        userProgress: {
          ...state.userProgress,
          accounts: updatedAccounts,
          stats: {
            ...state.userProgress.stats,
            accountsManaged: Math.max(0, state.userProgress.stats.accountsManaged - 1)
          }
        }
      };
  return applyAccountDrivenMilestones(applyPropFirmMilestones(next));
    }
    
    case 'UPDATE_FINANCIAL_SNAPSHOT':
      return {
        ...state,
        userProgress: {
          ...state.userProgress,
          financialSnapshot: {
            ...state.userProgress.financialSnapshot,
            ...action.payload,
            lastUpdated: new Date()
          }
        }
      };
    
    case 'UPDATE_TAX_OPTIMIZATION_PLAN':
      return {
        ...state,
        userProgress: {
          ...state.userProgress,
          taxOptimizationPlan: {
            ...state.userProgress.taxOptimizationPlan,
            ...action.payload
          }
        }
      };
    
    case 'UNLOCK_ACHIEVEMENT': {
      const { achievementId, unlockedAt } = action.payload;
      
      // Find achievement and mark as unlocked
      const updatedAchievements = state.userProgress.achievements.map(achievement =>
        achievement.id === achievementId
          ? { ...achievement, unlocked: true, unlockedAt }
          : achievement
      );
      
      return {
        ...state,
        userProgress: {
          ...state.userProgress,
          achievements: updatedAchievements
        }
      };
    }
    
    case 'UPDATE_USER_TITLE': {
      const { title, color, icon } = action.payload;
      
      return {
        ...state,
        userProgress: {
          ...state.userProgress,
          currentTitle: title,
          titleColor: color,
          titleIcon: icon
        }
      };
    }
    
    default:
      return state;
  }
}

const MilestoneContext = createContext<MilestoneContextValue | undefined>(undefined);

export const useMilestones = (): MilestoneContextValue => {
  const context = useContext(MilestoneContext);
  if (!context) {
    throw new Error('useMilestones must be used within a MilestoneProvider');
  }
  return context;
};

interface MilestoneProviderProps {
  children: ReactNode;
}

export const MilestoneProvider: React.FC<MilestoneProviderProps> = ({ children }) => {
  const [state, dispatch] = useReducer(milestoneReducer, initialState);
  const [hydrated, setHydrated] = React.useState(false);

  // Load user progress from localStorage on mount
  useEffect(() => {
    const savedProgress = localStorage.getItem('fks_user-progress');
    if (savedProgress) {
      try {
        const parsed = JSON.parse(savedProgress);
        dispatch({ type: 'INIT_USER_PROGRESS', payload: parsed });
      } catch (error) {
        console.error('Failed to load user progress:', error);
      }
    }
    const savedMilestones = localStorage.getItem('fks_available-milestones');
    if (savedMilestones) {
      try {
        const parsed: Milestone[] = JSON.parse(savedMilestones);
        dispatch({ type: 'INIT_AVAILABLE_MILESTONES', payload: parsed });
      } catch (error) {
        console.error('Failed to load available milestones:', error);
      }
    }
    // mark hydrated; a subsequent effect will recalc derived progress once
    setHydrated(true);
  }, []);

  // After initial hydration, reapply derived auto-updates once
  useEffect(() => {
    if (!hydrated) return;
    dispatch({ type: 'RECALC_DERIVED' });
    // Run only once post-hydration
  }, [hydrated]);

  // Save user progress to localStorage when it changes
  useEffect(() => {
    localStorage.setItem('fks_user-progress', JSON.stringify(state.userProgress));
  }, [state.userProgress]);

  // Save available milestones (including requirement state/evidence) when they change
  useEffect(() => {
    localStorage.setItem('fks_available-milestones', JSON.stringify(state.availableMilestones));
  }, [state.availableMilestones]);

  // Helper functions
  const getMilestoneById = (id: string): Milestone | undefined => {
    return state.availableMilestones.find(milestone => milestone.id === id);
  };

  const getCompletedMilestones = (): Milestone[] => {
    return state.availableMilestones.filter(milestone => 
      state.userProgress.completedMilestones.includes(milestone.id)
    );
  };

  const getActiveMilestones = (): Milestone[] => {
    return state.availableMilestones.filter(milestone => 
      !state.userProgress.completedMilestones.includes(milestone.id)
    );
  };

  const getNextPriorityMilestone = (): Milestone | undefined => {
    const activeMilestones = getActiveMilestones();
    return activeMilestones.find(milestone => milestone.priority === 'critical') ||
           activeMilestones.find(milestone => milestone.priority === 'high') ||
           activeMilestones[0];
  };

  const calculateTaxOptimizationScore = (): number => {
    let score = 0;
    
    // Base score for having tax-advantaged accounts
    const hasTFSA = state.userProgress.accounts.some(account => account.type === 'tfsa');
    const hasRRSP = state.userProgress.accounts.some(account => account.type === 'rrsp');
    const hasBusiness = state.userProgress.accounts.some(account => account.type === 'business');
    
    if (hasTFSA) score += 25;
    if (hasRRSP) score += 25;
    if (hasBusiness) score += 30;
    
    // Bonus for expense coverage (better tax positioning)
    if (state.userProgress.financialSnapshot.expenseCoverage >= 100) {
      score += 20;
    } else if (state.userProgress.financialSnapshot.expenseCoverage >= 50) {
      score += 10;
    }
    
    return Math.min(score, 100);
  };

  const getCanadianTaxSavings = (): number => {
    // Simplified calculation based on account types and income
    let savings = 0;
    
    const accounts = state.userProgress.accounts;
    const monthlyIncome = state.userProgress.financialSnapshot.monthlyIncome;
    const annualIncome = monthlyIncome * 12;
    
    // TFSA savings (assume 25% tax rate on gains)
    const tfsaAccounts = accounts.filter(account => account.type === 'tfsa');
    const tfsaGains = tfsaAccounts.reduce((total, account) => total + account.unrealizedProfits, 0);
    savings += tfsaGains * 0.25;
    
    // RRSP savings (tax deduction)
    const rrspAccounts = accounts.filter(account => account.type === 'rrsp');
    const rrspContributions = rrspAccounts.reduce((total, account) => total + account.totalDeposits, 0);
    savings += rrspContributions * 0.3; // Assume 30% marginal tax rate
    
    // Business incorporation savings
    const businessAccounts = accounts.filter(account => account.type === 'business');
    if (businessAccounts.length > 0 && annualIncome > 50000) {
      // Small business rate vs personal rate difference
      savings += annualIncome * 0.15; // Simplified calculation
    }
    
    return Math.round(savings);
  };

  // Action creators
  const completeMilestone = (milestoneId: string) => {
    dispatch({ 
      type: 'COMPLETE_MILESTONE', 
      payload: { milestoneId, completedAt: new Date() } 
    });
  };

  const updateMilestoneProgress = (milestoneId: string, progress: number) => {
    dispatch({ 
      type: 'UPDATE_MILESTONE_PROGRESS', 
      payload: { milestoneId, progress } 
    });
  };

  const updateMilestoneRequirement = (milestoneId: string, requirementId: string, updates: Partial<MilestoneRequirement>) => {
    dispatch({
      type: 'UPDATE_MILESTONE_REQUIREMENT',
      payload: { milestoneId, requirementId, updates }
    });
  };

  const awardExperience = (action: ExperienceAction, metadata?: Record<string, any>) => {
    const points = XP_VALUES[action] || 0;
    dispatch({ 
      type: 'AWARD_EXPERIENCE', 
      payload: { action, points, metadata } 
    });
  };

  const addAccount = (account: TaxOptimizedAccount) => {
    dispatch({ type: 'ADD_ACCOUNT', payload: account });
    
    // Auto-award XP for opening account
    awardExperience('ACCOUNT_OPENED', { accountType: account.type });
  };

  const updateAccount = (accountId: string, updates: Partial<TaxOptimizedAccount>) => {
    dispatch({ 
      type: 'UPDATE_ACCOUNT', 
      payload: { accountId, updates } 
    });
  };

  const removeAccount = (accountId: string) => {
    dispatch({ type: 'REMOVE_ACCOUNT', payload: accountId });
  };

  const updateFinancialSnapshot = (snapshot: Partial<FinancialSnapshot>) => {
    // Merge incoming snapshot
    const merged = { 
      ...state.userProgress.financialSnapshot, 
      ...snapshot 
    };

    // Derive expense coverage if income/expenses provided
    let expenseCoverage = merged.expenseCoverage;
    if (typeof merged.monthlyIncome === 'number' && typeof merged.monthlyExpenses === 'number') {
      expenseCoverage = merged.monthlyExpenses > 0
        ? Math.round((merged.monthlyIncome / merged.monthlyExpenses) * 100)
        : 0;
    }

    // First update snapshot with derived coverage
    dispatch({ type: 'UPDATE_FINANCIAL_SNAPSHOT', payload: { ...merged, expenseCoverage } });

    // Recompute tax metrics
    const newScore = calculateTaxOptimizationScore();
    dispatch({ 
      type: 'UPDATE_FINANCIAL_SNAPSHOT', 
      payload: { taxOptimizationScore: newScore, canadianTaxSavings: getCanadianTaxSavings() } 
    });

    // Update expense coverage milestones
    dispatch({ type: 'UPDATE_MILESTONE_PROGRESS', payload: { milestoneId: 'partial_expense_coverage', progress: expenseCoverage } });
    dispatch({ type: 'UPDATE_MILESTONE_PROGRESS', payload: { milestoneId: 'full_expense_coverage', progress: expenseCoverage } });

    // Sync requirement-level progress for expense coverage milestones
    dispatch({
      type: 'UPDATE_MILESTONE_REQUIREMENT',
      payload: { milestoneId: 'partial_expense_coverage', requirementId: 'monthly_coverage_25', updates: { current: expenseCoverage, isCompleted: expenseCoverage >= 25 } }
    });
    dispatch({
      type: 'UPDATE_MILESTONE_REQUIREMENT',
      payload: { milestoneId: 'full_expense_coverage', requirementId: 'monthly_coverage_100', updates: { current: expenseCoverage, isCompleted: expenseCoverage >= 100 } }
    });

    // Auto-complete when thresholds reached
    if (expenseCoverage >= 25 && !state.userProgress.completedMilestones.includes('partial_expense_coverage')) {
      dispatch({ type: 'COMPLETE_MILESTONE', payload: { milestoneId: 'partial_expense_coverage', completedAt: new Date() } });
    }
    if (expenseCoverage >= 100 && !state.userProgress.completedMilestones.includes('full_expense_coverage')) {
      dispatch({ type: 'COMPLETE_MILESTONE', payload: { milestoneId: 'full_expense_coverage', completedAt: new Date() } });
    }
  };

  const updateTaxOptimizationPlan = (plan: Partial<TaxOptimizationPlan>) => {
    dispatch({ type: 'UPDATE_TAX_OPTIMIZATION_PLAN', payload: plan });
  };

  const unlockAchievement = (achievementId: string) => {
    dispatch({ 
      type: 'UNLOCK_ACHIEVEMENT', 
      payload: { achievementId, unlockedAt: new Date() } 
    });
  };

  const contextValue: MilestoneContextValue = {
    ...state,
    completeMilestone,
    updateMilestoneProgress,
  updateMilestoneRequirement,
    awardExperience,
    addAccount,
    updateAccount,
    removeAccount,
    updateFinancialSnapshot,
    updateTaxOptimizationPlan,
    unlockAchievement,
    getMilestoneById,
    getCompletedMilestones,
    getActiveMilestones,
    getNextPriorityMilestone,
    calculateTaxOptimizationScore,
    getCanadianTaxSavings
  };

  return (
    <MilestoneContext.Provider value={contextValue}>
      {children}
    </MilestoneContext.Provider>
  );
};

export default MilestoneContext;
