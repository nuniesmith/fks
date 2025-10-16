import { 
  useNotifications, 
  createAchievementNotification, 
  createLevelUpNotification, 
  createXPNotification,
  createMilestoneNotification 
} from '../components/Notifications';

// Safe hook that won't break if NotificationProvider isn't available
export const useSafeNotifications = () => {
  try {
    return useNotifications();
  } catch (error) {
    // Return mock functions if notifications aren't available
    return {
      notifications: [],
      addNotification: () => {},
      removeNotification: () => {},
      clearAll: () => {}
    };
  }
};

export const useGamificationNotifications = () => {
  const { addNotification } = useSafeNotifications();

  const notifyAchievement = (
    title: string,
    description: string,
    xpReward: number,
    onViewAchievements?: () => void
  ) => {
    addNotification(createAchievementNotification(title, description, xpReward, onViewAchievements));
  };

  const notifyLevelUp = (
    newLevel: number,
    levelTitle: string,
    unlockedFeatures: string[],
    onViewProgress?: () => void
  ) => {
    addNotification(createLevelUpNotification(newLevel, levelTitle, unlockedFeatures, onViewProgress));
  };

  const notifyXP = (action: string, xpGained: number) => {
    addNotification(createXPNotification(action, xpGained));
  };

  const notifyMilestone = (
    title: string,
    description: string,
    onViewPhases?: () => void
  ) => {
    addNotification(createMilestoneNotification(title, description, onViewPhases));
  };

  return {
    notifyAchievement,
    notifyLevelUp,
    notifyXP,
    notifyMilestone
  };
};

export default useGamificationNotifications;
