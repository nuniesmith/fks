import { Trophy, Star, Zap, Target } from 'lucide-react';
import type { Notification } from './notificationTypes';

export const createAchievementNotification = (
  title: string,
  description: string,
  xpReward: number,
  onViewAchievements?: () => void
): Omit<Notification, 'id' | 'timestamp'> => ({
  type: 'achievement',
  title: `🏆 Achievement Unlocked!`,
  message: `${title}: ${description} (+${xpReward} XP)`,
  icon: <Trophy className="w-6 h-6 text-yellow-400" />,
  duration: 8000,
  action: onViewAchievements ? { label: 'View Achievements', onClick: onViewAchievements } : undefined
});

export const createLevelUpNotification = (
  newLevel: number,
  levelTitle: string,
  unlockedFeatures: string[],
  onViewProgress?: () => void
): Omit<Notification, 'id' | 'timestamp'> => ({
  type: 'levelUp',
  title: `🌟 Level Up! Level ${newLevel}`,
  message: `You are now ${levelTitle}! ${unlockedFeatures.length > 0 ? `Unlocked: ${unlockedFeatures.join(', ')}` : ''}`,
  icon: <Star className="w-6 h-6 text-purple-400" />,
  duration: 10000,
  action: onViewProgress ? { label: 'View Progress', onClick: onViewProgress } : undefined
});

export const createXPNotification = (
  action: string,
  xpGained: number
): Omit<Notification, 'id' | 'timestamp'> => ({
  type: 'xp',
  title: `+${xpGained} XP Earned!`,
  message: `Great job on: ${action}`,
  icon: <Zap className="w-6 h-6 text-green-400" />,
  duration: 3000
});

export const createMilestoneNotification = (
  title: string,
  description: string,
  onViewPhases?: () => void
): Omit<Notification, 'id' | 'timestamp'> => ({
  type: 'milestone',
  title: `🎯 Milestone Reached!`,
  message: `${title}: ${description}`,
  icon: <Target className="w-6 h-6 text-pink-400" />,
  duration: 8000,
  action: onViewPhases ? { label: 'View Phases', onClick: onViewPhases } : undefined
});

export const notificationAnimations = `
@keyframes shrink { from { width: 100%; } to { width: 0%; } }
@keyframes slideInRight { from { transform: translateX(100%); opacity: 0; } to { transform: translateX(0); opacity: 1; } }
@keyframes slideOutRight { from { transform: translateX(0); opacity: 1; } to { transform: translateX(100%); opacity: 0; } }
.notification-enter { animation: slideInRight 0.3s ease-out; }
.notification-exit { animation: slideOutRight 0.3s ease-in; }
`;
