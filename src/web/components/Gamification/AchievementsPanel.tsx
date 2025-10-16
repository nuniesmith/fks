import {
  Trophy,
  Star,
  Lock,
  CheckCircle,
  Target,
  TrendingUp,
  Brain,
  Users,
  DollarSign,
  Filter,
  Gift,
  Medal
} from 'lucide-react';
import React, { useState } from 'react';

import { useGamification } from '../../context/GamificationContext';

// Local shape (align with context data); broaden category/rarity with string fallback to avoid over-constraining.
interface Achievement {
  id: string;
  title: string;
  description: string;
  unlocked: boolean;
  category: 'trading' | 'learning' | 'progression' | 'milestones' | 'social' | 'financial' | string;
  rarity: 'common' | 'uncommon' | 'rare' | 'epic' | 'legendary' | string;
  points: number;
  progress?: number;
  maxProgress?: number;
  unlockedAt?: string | Date;
  rewards?: string[];
}

const AchievementsPanel: React.FC = () => {
  const { userProgress: _userProgress, achievements, getCurrentLevel } = useGamification();
  const [filter, setFilter] = useState<'all' | 'unlocked' | 'locked'>('all');
  const [category, setCategory] = useState<string>('all');
  // Retain level computation (unused currently) for potential future display without triggering lint.
  const _currentLevel = getCurrentLevel();
  const unlockedAchievements = achievements.filter(a => a.unlocked);
  const totalAchievements = achievements.length;

  // Group achievements by category
  const achievementCategories = [
    { id: 'all', label: 'All', icon: <Trophy className="w-4 h-4" /> },
    { id: 'trading', label: 'Trading', icon: <TrendingUp className="w-4 h-4" /> },
    { id: 'learning', label: 'Learning', icon: <Brain className="w-4 h-4" /> },
    { id: 'progression', label: 'Progression', icon: <Target className="w-4 h-4" /> },
    { id: 'milestones', label: 'Milestones', icon: <Medal className="w-4 h-4" /> },
    { id: 'social', label: 'Social', icon: <Users className="w-4 h-4" /> },
    { id: 'financial', label: 'Financial', icon: <DollarSign className="w-4 h-4" /> },
  ];

  const filteredAchievements = achievements.filter(achievement => {
    if (category !== 'all' && achievement.category !== category) return false;
    
    if (filter === 'unlocked') return achievement.unlocked;
    if (filter === 'locked') return !achievement.unlocked;
    
    return true;
  });

  const getAchievementIcon = (achievement: Achievement) => {
    switch (achievement.category) {
      case 'trading': return <TrendingUp className="w-8 h-8" />;
      case 'learning': return <Brain className="w-8 h-8" />;
      case 'progression': return <Target className="w-8 h-8" />;
      case 'milestones': return <Medal className="w-8 h-8" />;
      case 'social': return <Users className="w-8 h-8" />;
      case 'financial': return <DollarSign className="w-8 h-8" />;
      default: return <Trophy className="w-8 h-8" />;
    }
  };

  const getRarityColor = (rarity: string) => {
    switch (rarity) {
      case 'common': return 'text-gray-400 border-gray-400';
      case 'uncommon': return 'text-green-400 border-green-400';
      case 'rare': return 'text-blue-400 border-blue-400';
      case 'epic': return 'text-purple-400 border-purple-400';
      case 'legendary': return 'text-yellow-400 border-yellow-400';
      default: return 'text-gray-400 border-gray-400';
    }
  };

  const getRarityGlow = (rarity: string) => {
    switch (rarity) {
      case 'common': return 'shadow-lg';
      case 'uncommon': return 'shadow-lg shadow-green-500/20';
      case 'rare': return 'shadow-lg shadow-blue-500/20';
      case 'epic': return 'shadow-lg shadow-purple-500/20';
      case 'legendary': return 'shadow-lg shadow-yellow-500/30';
      default: return 'shadow-lg';
    }
  };

  const getCompletionRate = () => {
    return totalAchievements > 0 ? (unlockedAchievements.length / totalAchievements) * 100 : 0;
  };

  const getRecentAchievements = () => {
    return achievements
      .filter(a => a.unlocked && a.unlockedAt)
      .sort((a, b) => new Date(b.unlockedAt!).getTime() - new Date(a.unlockedAt!).getTime())
      .slice(0, 3);
  };

  const recentAchievements = getRecentAchievements();

  return (
    <div className="max-w-7xl mx-auto p-6 space-y-6">
      {/* Header */}
      <div className="bg-gradient-to-r from-purple-600 to-blue-600 rounded-2xl p-6 text-white">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold flex items-center space-x-3">
              <Trophy className="w-8 h-8 text-yellow-400" />
              <span>Achievements</span>
            </h1>
            <p className="text-purple-100 mt-2">
              Track your progress and unlock rewards on your trading journey
            </p>
          </div>
          <div className="text-right">
            <div className="text-4xl font-bold">{unlockedAchievements.length}</div>
            <div className="text-purple-200">of {totalAchievements} unlocked</div>
            <div className="text-sm text-purple-200 mt-1">
              {getCompletionRate().toFixed(1)}% complete
            </div>
          </div>
        </div>

        {/* Progress Bar */}
        <div className="mt-4">
          <div className="w-full bg-purple-800/30 rounded-full h-3">
            <div 
              className="bg-gradient-to-r from-yellow-400 to-orange-500 h-3 rounded-full transition-all duration-500"
              style={{ width: `${getCompletionRate()}%` }}
            ></div>
          </div>
        </div>
      </div>

      {/* Recent Achievements */}
      {recentAchievements.length > 0 && (
        <div className="bg-gray-800 rounded-xl p-6">
          <h2 className="text-xl font-bold text-white mb-4 flex items-center space-x-2">
            <Star className="w-6 h-6 text-yellow-400" />
            <span>Recently Unlocked</span>
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {recentAchievements.map((achievement) => (
              <div
                key={achievement.id}
                className={`bg-gray-700 rounded-lg p-4 border-2 ${getRarityColor(achievement.rarity)} ${getRarityGlow(achievement.rarity)}`}
              >
                <div className="flex items-center space-x-3">
                  <div className={`${getRarityColor(achievement.rarity)} flex-shrink-0`}>
                    {getAchievementIcon(achievement)}
                  </div>
                  <div className="flex-1 min-w-0">
                    <h3 className="font-bold text-white truncate">{achievement.title}</h3>
                    <p className="text-sm text-gray-400 line-clamp-2">{achievement.description}</p>
                    <div className="flex items-center space-x-2 mt-2">
                      <div className="text-xs bg-yellow-500/20 text-yellow-400 px-2 py-1 rounded">
                        +{achievement.points} XP
                      </div>
                      <div className="text-xs text-gray-500">
                        {achievement.unlockedAt && new Date(achievement.unlockedAt).toLocaleDateString()}
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="bg-gray-800 rounded-xl p-6">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between space-y-4 lg:space-y-0">
          {/* Category Filter */}
          <div className="flex flex-wrap gap-2">
            {achievementCategories.map((cat) => (
              <button
                key={cat.id}
                onClick={() => setCategory(cat.id)}
                className={`flex items-center space-x-2 px-4 py-2 rounded-lg transition-colors ${
                  category === cat.id
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                }`}
              >
                {cat.icon}
                <span>{cat.label}</span>
              </button>
            ))}
          </div>

          {/* Status Filter */}
          <div className="flex items-center space-x-2">
            <Filter className="w-5 h-5 text-gray-400" />
            <select
              value={filter}
              onChange={(e) => setFilter(e.target.value as 'all' | 'unlocked' | 'locked')}
              className="bg-gray-700 text-white rounded-lg px-3 py-2 border border-gray-600 focus:border-blue-500 focus:outline-none"
            >
              <option value="all">All Achievements</option>
              <option value="unlocked">Unlocked Only</option>
              <option value="locked">Locked Only</option>
            </select>
          </div>
        </div>
      </div>

      {/* Achievements Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {filteredAchievements.map((achievement) => (
          <div
            key={achievement.id}
            className={`bg-gray-800 rounded-xl p-6 border-2 transition-all duration-300 hover:scale-105 ${
              achievement.unlocked
                ? `${getRarityColor(achievement.rarity)} ${getRarityGlow(achievement.rarity)}`
                : 'border-gray-600 opacity-60'
            }`}
          >
            {/* Achievement Header */}
            <div className="flex items-start justify-between mb-4">
              <div className={`p-3 rounded-lg ${
                achievement.unlocked 
                  ? `${getRarityColor(achievement.rarity)} bg-current/10` 
                  : 'bg-gray-700 text-gray-500'
              }`}>
                {achievement.unlocked ? getAchievementIcon(achievement) : <Lock className="w-8 h-8" />}
              </div>
              
              <div className="text-right">
                {achievement.unlocked ? (
                  <CheckCircle className="w-6 h-6 text-green-400" />
                ) : (
                  <Lock className="w-6 h-6 text-gray-500" />
                )}
              </div>
            </div>

            {/* Achievement Info */}
            <div className="space-y-3">
              <div>
                <h3 className={`font-bold text-lg ${
                  achievement.unlocked ? 'text-white' : 'text-gray-400'
                }`}>
                  {achievement.title}
                </h3>
                <p className={`text-sm ${
                  achievement.unlocked ? 'text-gray-300' : 'text-gray-500'
                }`}>
                  {achievement.description}
                </p>
              </div>

              {/* Progress Bar (if applicable) */}
              {achievement.progress !== undefined && achievement.maxProgress && (
                <div className="space-y-2">
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-400">Progress</span>
                    <span className={achievement.unlocked ? 'text-green-400' : 'text-gray-400'}>
                      {achievement.progress}/{achievement.maxProgress}
                    </span>
                  </div>
                  <div className="w-full bg-gray-700 rounded-full h-2">
                    <div 
                      className={`h-2 rounded-full transition-all duration-500 ${
                        achievement.unlocked 
                          ? 'bg-gradient-to-r from-green-500 to-blue-500' 
                          : 'bg-gray-600'
                      }`}
                      style={{ 
                        width: `${Math.min((achievement.progress / achievement.maxProgress) * 100, 100)}%` 
                      }}
                    ></div>
                  </div>
                </div>
              )}

              {/* Rewards and Meta Info */}
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2">
                  <div className={`text-xs px-2 py-1 rounded ${
                    achievement.unlocked 
                      ? 'bg-yellow-500/20 text-yellow-400' 
                      : 'bg-gray-700 text-gray-500'
                  }`}>
                    +{achievement.points} XP
                  </div>
                  
                  <div className={`text-xs px-2 py-1 rounded border ${getRarityColor(achievement.rarity)}`}>
                    {achievement.rarity}
                  </div>
                </div>

                {achievement.unlocked && achievement.unlockedAt && (
                  <div className="text-xs text-gray-500">
                    {new Date(achievement.unlockedAt).toLocaleDateString()}
                  </div>
                )}
              </div>

              {/* Special Rewards */}
              {achievement.rewards && achievement.rewards.length > 0 && (
                <div className="mt-3 p-3 bg-gray-700/50 rounded-lg">
                  <div className="flex items-center space-x-2 mb-2">
                    <Gift className="w-4 h-4 text-purple-400" />
                    <span className="text-sm font-medium text-purple-400">Rewards</span>
                  </div>
                  <div className="space-y-1">
                    {achievement.rewards.map((reward, index) => (
                      <div key={index} className="text-xs text-gray-300">
                        • {reward}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Empty State */}
      {filteredAchievements.length === 0 && (
        <div className="text-center py-12">
          <Trophy className="w-16 h-16 text-gray-600 mx-auto mb-4" />
          <h3 className="text-xl font-bold text-gray-400 mb-2">No achievements found</h3>
          <p className="text-gray-500">
            {filter === 'unlocked' ? 'Start trading to unlock your first achievement!' : 
             filter === 'locked' ? 'All achievements unlocked! Great job!' :
             'Try adjusting your filters.'}
          </p>
        </div>
      )}
    </div>
  );
};

export default AchievementsPanel;
