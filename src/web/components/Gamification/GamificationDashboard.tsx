import { Trophy, Star, Target, TrendingUp, Award, Calendar, DollarSign } from 'lucide-react';
import React from 'react';

import { useGamification } from '../../context/GamificationContext';

const GamificationDashboard: React.FC = () => {
  const { 
    userProgress, 
    getCurrentLevel, 
    getProgressToNextLevel,
    isLoading 
  } = useGamification();

  if (isLoading || !userProgress) {
    return (
      <div className="p-6 bg-gray-900 text-white">
        <div className="animate-pulse">
          <div className="h-8 bg-gray-700 rounded mb-4 w-1/3"></div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {[1, 2, 3].map(i => (
              <div key={i} className="h-32 bg-gray-700 rounded"></div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  const currentLevel = getCurrentLevel();
  const progressToNext = getProgressToNextLevel();
  const currentPhase = userProgress.phases.find(p => p.id === userProgress.currentPhase);

  return (
    <div className="p-6 bg-gray-900 text-white space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold">Progress Dashboard</h1>
        <div className="text-right">
          <div className="text-sm text-gray-400">Total Experience</div>
          <div className="text-2xl font-bold text-blue-400">{userProgress.totalXP.toLocaleString()} XP</div>
        </div>
      </div>

      {/* Level & Progress Section */}
      <div className="bg-gradient-to-r from-blue-900/50 to-purple-900/50 rounded-lg p-6 border border-blue-500/20">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center space-x-4">
            <div className="text-4xl">{currentLevel.icon}</div>
            <div>
              <h2 className="text-2xl font-bold">{currentLevel.title}</h2>
              <p className="text-gray-400">{currentLevel.description}</p>
            </div>
          </div>
          <div className="text-center">
            <div className="text-3xl font-bold text-blue-400">Level {currentLevel.level}</div>
            <div className="text-sm text-gray-400">
              {progressToNext.percentage < 100 ? 'Next level in' : 'Max level!'}
            </div>
          </div>
        </div>

        {/* Progress Bar */}
        {progressToNext.percentage < 100 && (
          <div className="space-y-2">
            <div className="flex justify-between text-sm">
              <span>{progressToNext.current.toLocaleString()} XP</span>
              <span>{progressToNext.required.toLocaleString()} XP</span>
            </div>
            <div className="w-full bg-gray-700 rounded-full h-3">
              <div 
                className="bg-gradient-to-r from-blue-500 to-purple-500 h-3 rounded-full transition-all duration-500"
                style={{ width: `${progressToNext.percentage}%` }}
              ></div>
            </div>
            <div className="text-center text-sm text-gray-400">
              {progressToNext.percentage.toFixed(1)}% to next level
            </div>
          </div>
        )}

        {/* Level Benefits */}
        <div className="mt-4">
          <h3 className="font-semibold mb-2">Current Benefits:</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            {currentLevel.benefits.map((benefit, index) => (
              <div key={index} className="flex items-center space-x-2 text-sm">
                <Star className="w-4 h-4 text-yellow-400" />
                <span>{benefit}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Phase Progress */}
      {currentPhase && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Current Phase */}
          <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
            <div className="flex items-center space-x-3 mb-4">
              <Target className="w-6 h-6 text-green-400" />
              <div>
                <h3 className="text-xl font-bold">{currentPhase.title}</h3>
                <p className="text-gray-400 text-sm">{currentPhase.description}</p>
              </div>
            </div>

            {/* Phase Objectives */}
            <div className="space-y-4">
              {currentPhase.objectives.map(objective => (
                <div key={objective.id} className="space-y-2">
                  <div className="flex justify-between items-center">
                    <span className="font-medium">{objective.title}</span>
                    <span className={`text-sm px-2 py-1 rounded ${
                      objective.priority === 'critical' ? 'bg-red-900 text-red-200' :
                      objective.priority === 'high' ? 'bg-orange-900 text-orange-200' :
                      objective.priority === 'medium' ? 'bg-yellow-900 text-yellow-200' :
                      'bg-gray-700 text-gray-300'
                    }`}>
                      {objective.priority}
                    </span>
                  </div>
                  <div className="text-sm text-gray-400">{objective.description}</div>
                  <div className="flex justify-between text-sm">
                    <span>{objective.current} / {objective.target} {objective.unit}</span>
                    <span>{((objective.current / objective.target) * 100).toFixed(1)}%</span>
                  </div>
                  <div className="w-full bg-gray-700 rounded-full h-2">
                    <div 
                      className={`h-2 rounded-full ${
                        objective.isCompleted ? 'bg-green-500' : 'bg-blue-500'
                      }`}
                      style={{ width: `${Math.min((objective.current / objective.target) * 100, 100)}%` }}
                    ></div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Stats Overview */}
          <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
            <h3 className="text-xl font-bold mb-4 flex items-center">
              <TrendingUp className="w-6 h-6 text-blue-400 mr-2" />
              Performance Stats
            </h3>
            
            <div className="grid grid-cols-2 gap-4">
              <div className="text-center p-3 bg-gray-700 rounded">
                <div className="text-2xl font-bold text-green-400">{userProgress.stats.totalTrades}</div>
                <div className="text-sm text-gray-400">Total Trades</div>
              </div>
              <div className="text-center p-3 bg-gray-700 rounded">
                <div className="text-2xl font-bold text-blue-400">{userProgress.stats.winRate.toFixed(1)}%</div>
                <div className="text-sm text-gray-400">Win Rate</div>
              </div>
              <div className="text-center p-3 bg-gray-700 rounded">
                <div className="text-2xl font-bold text-purple-400">${userProgress.stats.totalProfit.toLocaleString()}</div>
                <div className="text-sm text-gray-400">Total Profit</div>
              </div>
              <div className="text-center p-3 bg-gray-700 rounded">
                <div className="text-2xl font-bold text-yellow-400">{userProgress.stats.accountsManaged}</div>
                <div className="text-sm text-gray-400">Accounts</div>
              </div>
            </div>

            {/* Monthly Income Progress */}
            <div className="mt-4 p-3 bg-gray-700 rounded">
              <div className="flex justify-between items-center mb-2">
                <span className="font-medium">Monthly Income</span>
                <span className="text-green-400">${userProgress.stats.monthlyIncome.toLocaleString()}</span>
              </div>
              <div className="text-sm text-gray-400">
                {userProgress.stats.expensesCovered ? (
                  <span className="text-green-400">✓ Expenses covered!</span>
                ) : (
                  'Working towards expense coverage'
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Recent Achievements */}
      <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
        <h3 className="text-xl font-bold mb-4 flex items-center">
          <Award className="w-6 h-6 text-yellow-400 mr-2" />
          Recent Achievements
        </h3>
        
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {userProgress.achievements
            .filter(achievement => achievement.unlocked)
            .slice(0, 6)
            .map(achievement => (
              <div key={achievement.id} className="bg-gray-700 rounded-lg p-4 border border-gray-600">
                <div className="flex items-center space-x-3 mb-2">
                  <span className="text-2xl">{achievement.icon}</span>
                  <div>
                    <h4 className="font-bold">{achievement.title}</h4>
                    <div className={`text-xs px-2 py-1 rounded ${
                      achievement.rarity === 'legendary' ? 'bg-yellow-600 text-yellow-100' :
                      achievement.rarity === 'epic' ? 'bg-purple-600 text-purple-100' :
                      achievement.rarity === 'rare' ? 'bg-blue-600 text-blue-100' :
                      'bg-gray-600 text-gray-100'
                    }`}>
                      {achievement.rarity}
                    </div>
                  </div>
                </div>
                <p className="text-sm text-gray-400">{achievement.description}</p>
                <div className="mt-2 text-xs text-green-400">+{achievement.points} XP</div>
              </div>
            ))}
        </div>

        {userProgress.achievements.filter(a => a.unlocked).length === 0 && (
          <div className="text-center text-gray-400 py-8">
            <Trophy className="w-16 h-16 mx-auto mb-4 text-gray-600" />
            <p>Complete your first trading milestone to unlock achievements!</p>
          </div>
        )}
      </div>

      {/* Activity Streaks */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="bg-gray-800 rounded-lg p-4 text-center border border-gray-700">
          <Calendar className="w-8 h-8 text-blue-400 mx-auto mb-2" />
          <div className="text-2xl font-bold">{userProgress.streaks.dailyLogin}</div>
          <div className="text-sm text-gray-400">Day Login Streak</div>
        </div>
        <div className="bg-gray-800 rounded-lg p-4 text-center border border-gray-700">
          <TrendingUp className="w-8 h-8 text-green-400 mx-auto mb-2" />
          <div className="text-2xl font-bold">{userProgress.streaks.profitableDays}</div>
          <div className="text-sm text-gray-400">Profitable Days</div>
        </div>
        <div className="bg-gray-800 rounded-lg p-4 text-center border border-gray-700">
          <DollarSign className="w-8 h-8 text-purple-400 mx-auto mb-2" />
          <div className="text-2xl font-bold">{userProgress.streaks.riskManagement}</div>
          <div className="text-sm text-gray-400">Risk Management</div>
        </div>
      </div>
    </div>
  );
};

export default GamificationDashboard;
