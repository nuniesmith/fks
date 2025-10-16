import React, { createContext, useContext, useReducer, useEffect } from 'react';

import { ENHANCED_ACHIEVEMENTS, checkAchievementProgress } from '../data/achievements';
import { useGamificationNotifications } from '../hooks/useGamificationNotifications';
import { XP_VALUES, USER_LEVELS } from '../types/gamification';

import type { UserProgress, Phase, Achievement, ExperienceAction} from '../types/gamification';

interface GamificationState {
  userProgress: UserProgress | null;
  isLoading: boolean;
  error: string | null;
}

interface GamificationContextType extends GamificationState {
  awardExperience: (action: ExperienceAction, metadata?: Record<string, any>) => void;
  unlockAchievement: (achievementId: string) => void;
  updatePhaseProgress: (phaseId: string, progress: Partial<Phase>) => void;
  addPropFirmAccount: (account: any) => void;
  updateFinancialTarget: (targetId: string, progress: number) => void;
  checkMilestones: () => void;
  getCurrentLevel: () => any;
  getProgressToNextLevel: () => { current: number; required: number; percentage: number };
  achievements: Achievement[];
}

type GamificationAction =
  | { type: 'SET_LOADING'; payload: boolean }
  | { type: 'SET_ERROR'; payload: string | null }
  | { type: 'SET_USER_PROGRESS'; payload: UserProgress }
  | { type: 'AWARD_EXPERIENCE'; payload: { action: ExperienceAction; points: number; metadata?: any } }
  | { type: 'UNLOCK_ACHIEVEMENT'; payload: string }
  | { type: 'UPDATE_PHASE'; payload: { phaseId: string; progress: Partial<Phase> } }
  | { type: 'ADD_PROP_FIRM_ACCOUNT'; payload: any }
  | { type: 'UPDATE_FINANCIAL_TARGET'; payload: { targetId: string; progress: number } };

const initialState: GamificationState = {
  userProgress: null,
  isLoading: true,
  error: null,
};

const GamificationContext = createContext<GamificationContextType | undefined>(undefined);

function gamificationReducer(state: GamificationState, action: GamificationAction): GamificationState {
  switch (action.type) {
    case 'SET_LOADING':
      return { ...state, isLoading: action.payload };
    
    case 'SET_ERROR':
      return { ...state, error: action.payload, isLoading: false };
    
    case 'SET_USER_PROGRESS':
      return { ...state, userProgress: action.payload, isLoading: false };
    
    case 'AWARD_EXPERIENCE': {
      if (!state.userProgress) return state;

      const newTotalXP = state.userProgress.totalXP + action.payload.points;
      const newLevel = USER_LEVELS.reduce((prev, current) =>
        newTotalXP >= current.requiredXP ? current : prev
      );

      return {
        ...state,
        userProgress: {
          ...state.userProgress,
          totalXP: newTotalXP,
          currentLevel: newLevel,
          xpToNextLevel: getXPToNextLevel(newTotalXP, newLevel.level),
          lastActivity: new Date(),
        }
      };
    }

    case 'UNLOCK_ACHIEVEMENT': {
      if (!state.userProgress) return state;

      const updatedAchievements = state.userProgress.achievements.map(achievement =>
        achievement.id === action.payload
          ? { ...achievement, unlocked: true, unlockedAt: new Date() }
          : achievement
      );

      return {
        ...state,
        userProgress: {
          ...state.userProgress,
          achievements: updatedAchievements,
        }
      };
    }

    case 'UPDATE_PHASE': {
      if (!state.userProgress) return state;

      const updatedPhases = state.userProgress.phases.map(phase =>
        phase.id === action.payload.phaseId
          ? { ...phase, ...action.payload.progress }
          : phase
      );

      return {
        ...state,
        userProgress: {
          ...state.userProgress,
          phases: updatedPhases,
        }
      };
    }

    case 'ADD_PROP_FIRM_ACCOUNT': {
      if (!state.userProgress) return state;

      return {
        ...state,
        userProgress: {
          ...state.userProgress,
          propFirmAccounts: [...state.userProgress.propFirmAccounts, action.payload],
          stats: {
            ...state.userProgress.stats,
            accountsManaged: state.userProgress.propFirmAccounts.length + 1,
          }
        }
      };
    }

    case 'UPDATE_FINANCIAL_TARGET': {
      if (!state.userProgress) return state;

      const updatedTargets = state.userProgress.financialTargets.map(target =>
        target.id === action.payload.targetId
          ? { ...target, currentAmount: action.payload.progress }
          : target
      );

      return {
        ...state,
        userProgress: {
          ...state.userProgress,
          financialTargets: updatedTargets,
        }
      };
    }
    
    default:
      return state;
  }
}

function getXPToNextLevel(currentXP: number, currentLevel: number): number {
  const nextLevel = USER_LEVELS.find(level => level.level === currentLevel + 1);
  return nextLevel ? nextLevel.requiredXP - currentXP : 0;
}

export const GamificationProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [state, dispatch] = useReducer(gamificationReducer, initialState);
  const { notifyAchievement, notifyLevelUp, notifyXP } = useGamificationNotifications();

  // Load user progress on mount
  useEffect(() => {
    loadUserProgress();
  }, []);

  const loadUserProgress = async () => {
    try {
      dispatch({ type: 'SET_LOADING', payload: true });
      
      // In a real app, this would be an API call
      // For now, we'll use localStorage or create initial data
      const savedProgress = localStorage.getItem('fks_user_progress');
      
      if (savedProgress) {
        const progress = JSON.parse(savedProgress);
        dispatch({ type: 'SET_USER_PROGRESS', payload: progress });
      } else {
        // Create initial user progress
        const initialProgress = createInitialUserProgress();
        dispatch({ type: 'SET_USER_PROGRESS', payload: initialProgress });
        localStorage.setItem('fks_user_progress', JSON.stringify(initialProgress));
      }
    } catch (error) {
      dispatch({ type: 'SET_ERROR', payload: 'Failed to load user progress' });
    }
  };

  const createInitialUserProgress = (): UserProgress => {
    const now = new Date();
    
    return {
      userId: 'user_1',
      currentLevel: USER_LEVELS[0],
      totalXP: 0,
      currentTitle: USER_LEVELS[0].title,
      titleColor: USER_LEVELS[0].titleColor,
      titleIcon: USER_LEVELS[0].titleIcon,
      milestones: [],
      xpToNextLevel: USER_LEVELS[1].requiredXP,
      currentPhase: 'phase_1',
      phases: [
        {
          id: 'phase_1',
          title: 'Foundation & Prop Firm Success',
          description: 'Build trading skills and scale to 30 prop firm accounts',
          objectives: [
            {
              id: 'prop_firms',
              title: 'Prop Firm Accounts',
              description: 'Pass and scale up to 30 prop firm accounts across 3 firms',
              category: 'prop_firm',
              target: 30,
              current: 0,
              unit: 'accounts',
              isCompleted: false,
              priority: 'high'
            },
            {
              id: 'crypto_setup',
              title: 'Crypto Investment Setup',
              description: 'Set up 1-2 crypto accounts for expense coverage',
              category: 'crypto',
              target: 2,
              current: 0,
              unit: 'accounts',
              isCompleted: false,
              priority: 'high'
            },
            {
              id: 'expense_coverage',
              title: 'Cover Personal Expenses',
              description: 'Generate enough income to cover all personal expenses',
              category: 'expenses',
              target: 100,
              current: 0,
              unit: 'percentage',
              isCompleted: false,
              priority: 'critical'
            }
          ],
          requirements: [
            { id: 'req_1', description: 'Complete trading education modules', isCompleted: false },
            { id: 'req_2', description: 'Pass first prop firm evaluation', isCompleted: false },
            { id: 'req_3', description: 'Establish consistent profitability', isCompleted: false }
          ],
          isActive: true,
          isCompleted: false,
          currentProgress: 0,
          totalProgress: 100
        },
        {
          id: 'phase_2',
          title: 'Wealth Building & Diversification',
          description: 'Long-term wealth building with diversified investment portfolio',
          objectives: [
            {
              id: 'investment_accounts',
              title: 'Investment Accounts',
              description: 'Set up various investment accounts (RRSP, TFSA, etc.)',
              category: 'accounts',
              target: 5,
              current: 0,
              unit: 'accounts',
              isCompleted: false,
              priority: 'medium'
            },
            {
              id: 'portfolio_growth',
              title: 'Portfolio Growth',
              description: 'Grow investment portfolio value',
              category: 'profit',
              target: 100000,
              current: 0,
              unit: 'CAD',
              isCompleted: false,
              priority: 'high'
            }
          ],
          requirements: [
            { id: 'req_p2_1', description: 'Complete Phase 1 successfully', isCompleted: false },
            { id: 'req_p2_2', description: 'Have stable monthly income from trading', isCompleted: false }
          ],
          isActive: false,
          isCompleted: false,
          currentProgress: 0,
          totalProgress: 100
        }
      ],
      achievements: createInitialAchievements(),
      propFirmAccounts: [],
      cryptoAccounts: [],
      financialTargets: [
        {
          id: 'monthly_expenses',
          category: 'monthly_expenses',
          description: 'Cover monthly living expenses',
          targetAmount: 4000,
          currentAmount: 0,
          isActive: true,
          priority: 'critical'
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
      lastActivity: now,
      joinedAt: now
    };
  };

  const createInitialAchievements = (): Achievement[] => {
    return ENHANCED_ACHIEVEMENTS;
  };

  const saveProgress = (progress: UserProgress) => {
    localStorage.setItem('fks_user_progress', JSON.stringify(progress));
  };

  const getUnlockedFeaturesForLevel = (level: number): string[] => {
    const features: string[] = [];
    if (level >= 2) features.push('Trading Mode Control', 'Financial Targets');
    if (level >= 3) features.push('Portfolio Manager', 'Prop Firm Manager', 'Strategy Library');
    if (level >= 4) features.push('Market Insights', 'Order Management', 'Signals Panel');
    if (level >= 5) features.push('FKS Data Service', 'Canadian Accounts', 'Strategy Development');
    if (level >= 6) features.push('FKS Intelligence', 'Worker Status', 'Services Monitor');
    if (level >= 7) features.push('FKS Transformer', 'API Testing', 'System Logs');
    if (level >= 8) features.push('Node Network', 'Git Status', 'Master Level Access');
    return features;
  };

  const awardExperience = (action: ExperienceAction, metadata?: Record<string, any>) => {
    const points = XP_VALUES[action];
    const oldLevel = state.userProgress?.currentLevel.level || 1;
    
    dispatch({ type: 'AWARD_EXPERIENCE', payload: { action, points, metadata } });
    
    // Show XP notification
    notifyXP(action.toLowerCase().replace(/_/g, ' '), points);
    
    // Check for level up
    if (state.userProgress) {
      const newTotalXP = state.userProgress.totalXP + points;
      const newLevel = USER_LEVELS.reduce((prev, current) => 
        newTotalXP >= current.requiredXP ? current : prev
      );
      
      if (newLevel.level > oldLevel) {
        const unlockedFeatures = getUnlockedFeaturesForLevel(newLevel.level);
        notifyLevelUp(newLevel.level, newLevel.title, unlockedFeatures);
      }
    }
    
    // Check for automatic achievement unlocks
    if (state.userProgress) {
      const newlyUnlocked = checkAchievementProgress(action, state.userProgress, state.userProgress.achievements);
      newlyUnlocked.forEach(achievementId => {
        unlockAchievement(achievementId);
      });
    }
    
    // Save to localStorage after state update
    if (state.userProgress) {
      const updatedProgress = {
        ...state.userProgress,
        totalXP: state.userProgress.totalXP + points
      };
      saveProgress(updatedProgress);
    }
  };

  const unlockAchievement = (achievementId: string) => {
    dispatch({ type: 'UNLOCK_ACHIEVEMENT', payload: achievementId });
    
    // Find the achievement and show notification
    if (state.userProgress) {
      const achievement = state.userProgress.achievements.find(a => a.id === achievementId);
      if (achievement) {
        notifyAchievement(achievement.title, achievement.description, achievement.points);
      }
      
      const updatedProgress = {
        ...state.userProgress,
        achievements: state.userProgress.achievements.map(achievement => 
          achievement.id === achievementId 
            ? { ...achievement, unlocked: true, unlockedAt: new Date() }
            : achievement
        )
      };
      saveProgress(updatedProgress);
    }
  };

  const updatePhaseProgress = (phaseId: string, progress: Partial<Phase>) => {
    dispatch({ type: 'UPDATE_PHASE', payload: { phaseId, progress } });
    
    if (state.userProgress) {
      const updatedProgress = {
        ...state.userProgress,
        phases: state.userProgress.phases.map(phase =>
          phase.id === phaseId ? { ...phase, ...progress } : phase
        )
      };
      saveProgress(updatedProgress);
    }
  };

  const addPropFirmAccount = (account: any) => {
    dispatch({ type: 'ADD_PROP_FIRM_ACCOUNT', payload: account });
    awardExperience('ACCOUNT_CREATED');
  };

  const updateFinancialTarget = (targetId: string, progress: number) => {
    dispatch({ type: 'UPDATE_FINANCIAL_TARGET', payload: { targetId, progress } });
  };

  const checkMilestones = () => {
    // Implementation for checking and unlocking milestones based on current progress
    if (!state.userProgress) return;

    // Check for automatic achievement unlocks
    const { stats, propFirmAccounts } = state.userProgress;
    
    // Example: Check if user should unlock "First Account" achievement
    if (propFirmAccounts.length >= 1) {
      const firstAccountAchievement = state.userProgress.achievements.find(a => a.id === 'first_account');
      if (firstAccountAchievement && !firstAccountAchievement.unlocked) {
        unlockAchievement('first_account');
      }
    }
  };

  const getCurrentLevel = () => {
    return state.userProgress?.currentLevel || USER_LEVELS[0];
  };

  const getProgressToNextLevel = () => {
    if (!state.userProgress) {
      return { current: 0, required: USER_LEVELS[1].requiredXP, percentage: 0 };
    }

    const { totalXP, currentLevel } = state.userProgress;
    const nextLevel = USER_LEVELS.find(level => level.level === currentLevel.level + 1);
    
    if (!nextLevel) {
      return { current: totalXP, required: totalXP, percentage: 100 };
    }

    const current = totalXP - currentLevel.requiredXP;
    const required = nextLevel.requiredXP - currentLevel.requiredXP;
    const percentage = Math.min((current / required) * 100, 100);

    return { current, required, percentage };
  };

  const contextValue: GamificationContextType = {
    ...state,
    awardExperience,
    unlockAchievement,
    updatePhaseProgress,
    addPropFirmAccount,
    updateFinancialTarget,
    checkMilestones,
    getCurrentLevel,
    getProgressToNextLevel,
    achievements: state.userProgress?.achievements || [],
  };

  return (
    <GamificationContext.Provider value={contextValue}>
      {children}
    </GamificationContext.Provider>
  );
};

export const useGamification = (): GamificationContextType => {
  const context = useContext(GamificationContext);
  if (!context) {
    throw new Error('useGamification must be used within a GamificationProvider');
  }
  return context;
};
