// Clean Gamification Context for Milestone System
import React, { createContext, useContext, useReducer } from 'react';

import { XP_VALUES } from '../types/gamification';

import type { UserProgress, ExperienceAction} from '../types/gamification';

interface GamificationContextType {
  userProgress: UserProgress;
  awardExperience: (action: ExperienceAction, customAmount?: number) => void;
  loading: boolean;
  error: string | null;
}

const GamificationContext = createContext<GamificationContextType | undefined>(undefined);

const initialUserProgress: UserProgress = {
  userId: 'user_1',
  totalXP: 0,
  currentTitle: 'Trading Newcomer',
  titleColor: '#6B7280',
  titleIcon: '🌱',
  milestones: [],
  achievements: [],
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

type GamificationAction = 
  | { type: 'AWARD_XP'; payload: { action: ExperienceAction; amount: number } }
  | { type: 'UPDATE_STATS'; payload: Partial<UserProgress['stats']> }
  | { type: 'COMPLETE_MILESTONE'; payload: string }
  | { type: 'SET_LOADING'; payload: boolean }
  | { type: 'SET_ERROR'; payload: string | null };

function gamificationReducer(state: UserProgress, action: GamificationAction): UserProgress {
  switch (action.type) {
    case 'AWARD_XP': {
      const newTotalXP = state.totalXP + action.payload.amount;
      return {
        ...state,
        totalXP: newTotalXP
      };
    }
    case 'UPDATE_STATS':
      return {
        ...state,
        stats: { ...state.stats, ...action.payload }
      };
    case 'COMPLETE_MILESTONE':
      return {
        ...state,
        milestones: [...state.milestones, action.payload]
      };
    default:
      return state;
  }
}

export const GamificationProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [userProgress, dispatch] = useReducer(gamificationReducer, initialUserProgress);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const awardExperience = (action: ExperienceAction, customAmount?: number) => {
    const amount = customAmount || XP_VALUES[action] || 0;
    dispatch({ type: 'AWARD_XP', payload: { action, amount } });
  };

  const value: GamificationContextType = {
    userProgress,
    awardExperience,
    loading,
    error
  };

  return (
    <GamificationContext.Provider value={value}>
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
