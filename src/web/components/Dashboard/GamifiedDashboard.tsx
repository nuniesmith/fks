import { 
  Trophy, 
  Target, 
  Building2,
  DollarSign,
  Activity,
  Award,
  CheckCircle,
  AlertTriangle
} from 'lucide-react';
import React from 'react';

import { useGamification } from '../../context/GamificationContext';
import { useTradingEnv } from '../../context/TradingEnvContext';
import Dashboard from './Dashboard';

const GamifiedDashboardOverlay: React.FC = () => {
  const { userProgress, getCurrentLevel, getProgressToNextLevel } = useGamification();
  const { environment, isSimulation } = useTradingEnv();

  if (!userProgress) {
    return <Dashboard />;
  }

  const currentLevel = getCurrentLevel();
  const progressToNext = getProgressToNextLevel();
  const currentPhase = userProgress.phases.find(p => p.id === userProgress.currentPhase);
  const propFirmObjective = currentPhase?.objectives.find(obj => obj.category === 'prop_firm');
  const expenseObjective = currentPhase?.objectives.find(obj => obj.category === 'expenses');

  return (
    <div className="space-y-6">
      {/* Gamification Header */}
      <div className="bg-gradient-to-r from-purple-900/50 to-blue-900/50 rounded-lg p-6 border border-purple-500/20">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-4">
            <div className="text-4xl">{currentLevel.icon}</div>
            <div>
              <h2 className="text-2xl font-bold text-white">{currentLevel.title}</h2>
              <p className="text-gray-400">{currentLevel.description}</p>
              <div className="mt-2 flex items-center space-x-4">
                <div className="flex items-center space-x-2">
                  <Trophy className="w-4 h-4 text-yellow-400" />
                  <span className="text-sm text-yellow-400">{userProgress.totalXP.toLocaleString()} XP</span>
                </div>
                <div className="flex items-center space-x-2">
                  <Target className="w-4 h-4 text-blue-400" />
                  <span className="text-sm text-blue-400">Level {currentLevel.level}</span>
                </div>
              </div>
            </div>
          </div>
          
          <div className="text-right">
            <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
              <div className="text-sm text-gray-400 mb-1">Progress to Next Level</div>
              <div className="w-32 bg-gray-700 rounded-full h-2 mb-2">
                <div 
                  className="bg-gradient-to-r from-blue-500 to-purple-500 h-2 rounded-full transition-all duration-500"
                  style={{ width: `${progressToNext.percentage}%` }}
                ></div>
              </div>
              <div className="text-xs text-gray-400">
                {progressToNext.current.toLocaleString()} / {progressToNext.required.toLocaleString()} XP
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Phase Progress Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Phase 1 Progress */}
        <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-bold text-white flex items-center">
              <Building2 className="w-5 h-5 text-blue-400 mr-2" />
              Phase 1: Prop Firms
            </h3>
            <div className={`text-xs px-2 py-1 rounded ${
              currentPhase?.isActive ? 'bg-blue-500/20 text-blue-400' : 'bg-gray-600 text-gray-400'
            }`}>
              {currentPhase?.isActive ? 'ACTIVE' : 'LOCKED'}
            </div>
          </div>
          
          {propFirmObjective && (
            <div className="space-y-2">
              <div className="flex justify-between text-sm">
                <span>Prop Firm Accounts</span>
                <span>{propFirmObjective.current} / {propFirmObjective.target}</span>
              </div>
              <div className="w-full bg-gray-700 rounded-full h-2">
                <div 
                  className="bg-blue-500 h-2 rounded-full transition-all duration-300"
                  style={{ width: `${Math.min((propFirmObjective.current / propFirmObjective.target) * 100, 100)}%` }}
                ></div>
              </div>
              <div className="text-xs text-gray-400">
                {((propFirmObjective.current / propFirmObjective.target) * 100).toFixed(1)}% complete
              </div>
            </div>
          )}
        </div>

        {/* Expense Coverage */}
        <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-bold text-white flex items-center">
              <DollarSign className="w-5 h-5 text-green-400 mr-2" />
              Expense Coverage
            </h3>
            <div className={`text-xs px-2 py-1 rounded ${
              userProgress.stats.expensesCovered ? 'bg-green-500/20 text-green-400' : 'bg-orange-500/20 text-orange-400'
            }`}>
              {userProgress.stats.expensesCovered ? 'COVERED' : 'IN PROGRESS'}
            </div>
          </div>
          
          <div className="space-y-2">
            <div className="flex justify-between text-sm">
              <span>Monthly Income</span>
              <span>${userProgress.stats.monthlyIncome.toLocaleString()}</span>
            </div>
            <div className="w-full bg-gray-700 rounded-full h-2">
              <div className={`h-2 rounded-full transition-all duration-300 ${
                userProgress.stats.expensesCovered ? 'bg-green-500' : 'bg-orange-500'
              }`} style={{ width: '75%' }}></div>
            </div>
            <div className="text-xs text-gray-400">
              {userProgress.stats.expensesCovered ? 'Expenses fully covered!' : 'Building towards full coverage'}
            </div>
          </div>
        </div>

        {/* Recent Achievement */}
        <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-bold text-white flex items-center">
              <Award className="w-5 h-5 text-yellow-400 mr-2" />
              Latest Achievement
            </h3>
          </div>
          
          {(() => {
            const latestAchievement = userProgress.achievements
              .filter(a => a.unlocked && a.unlockedAt)
              .sort((a, b) => new Date(b.unlockedAt!).getTime() - new Date(a.unlockedAt!).getTime())[0];
            
            if (latestAchievement) {
              return (
                <div className="space-y-2">
                  <div className="flex items-center space-x-2">
                    <span className="text-xl">{latestAchievement.icon}</span>
                    <div>
                      <div className="font-medium text-white">{latestAchievement.title}</div>
                      <div className="text-xs text-gray-400">{latestAchievement.description}</div>
                    </div>
                  </div>
                  <div className="text-xs text-green-400">+{latestAchievement.points} XP</div>
                </div>
              );
            } else {
              return (
                <div className="text-center text-gray-400 py-4">
                  <Trophy className="w-8 h-8 mx-auto mb-2 text-gray-600" />
                  <div className="text-sm">No achievements yet</div>
                  <div className="text-xs">Complete your first milestone!</div>
                </div>
              );
            }
          })()}
        </div>
      </div>

      {/* Quick Stats Row */}
      <div className="grid grid-cols-2 md:grid-cols-6 gap-4">
        <div className="bg-gray-800 rounded-lg p-3 text-center border border-gray-700">
          <div className="text-lg font-bold text-blue-400">{userProgress.streaks.dailyLogin}</div>
          <div className="text-xs text-gray-400">Login Streak</div>
        </div>
        <div className="bg-gray-800 rounded-lg p-3 text-center border border-gray-700">
          <div className="text-lg font-bold text-green-400">{userProgress.stats.totalTrades}</div>
          <div className="text-xs text-gray-400">Total Trades</div>
        </div>
        <div className="bg-gray-800 rounded-lg p-3 text-center border border-gray-700">
          <div className="text-lg font-bold text-purple-400">{userProgress.stats.winRate.toFixed(1)}%</div>
          <div className="text-xs text-gray-400">Win Rate</div>
        </div>
        <div className="bg-gray-800 rounded-lg p-3 text-center border border-gray-700">
          <div className="text-lg font-bold text-yellow-400">{userProgress.propFirmAccounts.length}</div>
          <div className="text-xs text-gray-400">Prop Accounts</div>
        </div>
        <div className="bg-gray-800 rounded-lg p-3 text-center border border-gray-700">
          <div className="text-lg font-bold text-orange-400">{userProgress.achievements.filter(a => a.unlocked).length}</div>
          <div className="text-xs text-gray-400">Achievements</div>
        </div>
        <div className="bg-gray-800 rounded-lg p-3 text-center border border-gray-700">
          <div className="text-lg font-bold text-red-400">${userProgress.stats.totalProfit.toLocaleString()}</div>
          <div className="text-xs text-gray-400">Total Profit</div>
        </div>
      </div>

      {/* Environment Status with Gamification */}
      <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-bold text-white flex items-center">
            <Activity className="w-5 h-5 text-blue-400 mr-2" />
            Trading Environment Status
          </h3>
          <div className="flex items-center space-x-2">
            <div className={`px-3 py-1 rounded-lg text-xs ${
              isSimulation 
                ? 'bg-blue-500/20 text-blue-400 border border-blue-500/30' 
                : 'bg-red-500/20 text-red-400 border border-red-500/30'
            }`}>
              {environment}
            </div>
            {isSimulation && (
              <div className="flex items-center space-x-1 text-green-400">
                <CheckCircle className="w-4 h-4" />
                <span className="text-xs">Safe Practice Mode</span>
              </div>
            )}
            {!isSimulation && (
              <div className="flex items-center space-x-1 text-red-400">
                <AlertTriangle className="w-4 h-4" />
                <span className="text-xs">Live Money at Risk</span>
              </div>
            )}
          </div>
        </div>
        
        <div className="text-sm text-gray-400">
          {isSimulation ? (
            "You're in simulation mode - perfect for testing strategies and earning XP safely!"
          ) : (
            "Live trading mode active - strategies are executing with real money."
          )}
        </div>
      </div>

      {/* Next Milestones */}
      <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
        <h3 className="text-lg font-bold text-white mb-4 flex items-center">
          <Target className="w-5 h-5 text-blue-400 mr-2" />
          Next Milestones
        </h3>
        
        <div className="space-y-3">
          {[
            {
              title: 'First Prop Firm Account',
              description: 'Pass your first prop firm evaluation',
              progress: userProgress.propFirmAccounts.length > 0 ? 100 : 0,
              reward: '500 XP + Achievement',
              completed: userProgress.propFirmAccounts.length > 0
            },
            {
              title: '5 Profitable Days',
              description: 'Maintain profitability for 5 consecutive days',
              progress: (userProgress.streaks.profitableDays / 5) * 100,
              reward: '300 XP + Risk Master Badge',
              completed: userProgress.streaks.profitableDays >= 5
            },
            {
              title: 'Phase 1 Complete',
              description: 'Reach 30 prop firm accounts and cover expenses',
              progress: propFirmObjective ? (propFirmObjective.current / propFirmObjective.target) * 100 : 0,
              reward: '2000 XP + Phase 2 Unlock',
              completed: currentPhase?.isCompleted || false
            }
          ].map((milestone, index) => (
            <div key={index} className={`p-3 rounded-lg border ${
              milestone.completed 
                ? 'bg-green-900/20 border-green-500/30' 
                : 'bg-gray-700 border-gray-600'
            }`}>
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center space-x-2">
                  {milestone.completed ? (
                    <CheckCircle className="w-5 h-5 text-green-400" />
                  ) : (
                    <Target className="w-5 h-5 text-blue-400" />
                  )}
                  <div>
                    <div className="font-medium text-white">{milestone.title}</div>
                    <div className="text-sm text-gray-400">{milestone.description}</div>
                  </div>
                </div>
                <div className="text-xs text-yellow-400">{milestone.reward}</div>
              </div>
              
              {!milestone.completed && (
                <div className="space-y-1">
                  <div className="w-full bg-gray-600 rounded-full h-2">
                    <div 
                      className="bg-blue-500 h-2 rounded-full transition-all duration-300"
                      style={{ width: `${Math.min(milestone.progress, 100)}%` }}
                    ></div>
                  </div>
                  <div className="text-xs text-gray-400">{milestone.progress.toFixed(1)}% complete</div>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Original Dashboard Content */}
      <Dashboard />
    </div>
  );
};

export default GamifiedDashboardOverlay;
