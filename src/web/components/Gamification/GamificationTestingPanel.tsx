import {
  Play,
  Trophy,
  Target,
  Star,
  Zap,
  CheckCircle,
  RefreshCw,
  Activity,
  Award,
  Settings,
  Users,
  TrendingUp
} from 'lucide-react';
import React, { useState } from 'react';

import { useGamification } from '../../context/GamificationContext';

const GamificationTestingPanel: React.FC = () => {
  const {
    userProgress,
    awardExperience,
    unlockAchievement,
    updatePhaseProgress,
    addPropFirmAccount,
    updateFinancialTarget,
    getCurrentLevel,
    getProgressToNextLevel,
    achievements
  } = useGamification();

  const [selectedXPAction, setSelectedXPAction] = useState<string>('LESSON_COMPLETED');
  const [testResults, setTestResults] = useState<string[]>([]);

  const currentLevel = getCurrentLevel();
  const progressToNext = getProgressToNextLevel();

  const xpActions = [
    'LESSON_COMPLETED',
    'FIRST_TRADE',
    'PROFITABLE_TRADE',
    'STRATEGY_CREATED',
    'STRATEGY_BACKTESTED',
    'STRATEGY_DEPLOYED',
    'DAILY_PROFIT_TARGET',
    'WEEKLY_PROFIT_TARGET',
    'MONTHLY_PROFIT_TARGET',
    'RISK_RULES_SET',
    'STOP_LOSS_HONORED',
    'DRAWDOWN_MANAGED',
    'MAX_RISK_ADHERED',
    'PHASE_1_MILESTONE',
    'PHASE_2_UNLOCKED',
    'PROP_FIRM_PASSED',
    'EXPENSES_COVERED',
    'ACCOUNT_CREATED',
    'ACCOUNT_VERIFIED',
    'FIRST_DEPOSIT',
    'ACCOUNT_FUNDED'
  ];

  const testScenarios = [
    {
      name: 'Award XP Test',
      action: () => {
        try {
          awardExperience(selectedXPAction as any);
          addTestResult(`✅ Successfully awarded XP for ${selectedXPAction}`);
        } catch (error) {
          addTestResult(`❌ Error awarding XP: ${error}`);
        }
      }
    },
    {
      name: 'Add Prop Firm Account',
      action: () => {
        try {
          const newAccount = {
            id: `test-${Date.now()}`,
            name: `Test Prop Firm ${Date.now()}`,
            challenge: 'Phase 1',
            balance: 10000,
            target: 800,
            status: 'active',
            createdAt: new Date()
          };
          addPropFirmAccount(newAccount);
          addTestResult(`✅ Added prop firm account: ${newAccount.name}`);
        } catch (error) {
          addTestResult(`❌ Error adding prop firm account: ${error}`);
        }
      }
    },
    {
      name: 'Update Phase Progress',
      action: () => {
        try {
          updatePhaseProgress('phase-1', {
            objectives: [
              { 
                id: 'prop-firms', 
                title: 'Scale to 30 Prop Firm Accounts', 
                description: 'Test objective update',
                category: 'prop_firm',
                target: 30,
                current: 15,
                unit: 'accounts',
                isCompleted: false,
                priority: 'critical'
              }
            ]
          });
          addTestResult(`✅ Updated Phase 1 progress`);
        } catch (error) {
          addTestResult(`❌ Error updating phase progress: ${error}`);
        }
      }
    },
    {
      name: 'Update Financial Target',
      action: () => {
        try {
          updateFinancialTarget('monthly-income', 2500);
          addTestResult(`✅ Updated financial target to $2,500`);
        } catch (error) {
          addTestResult(`❌ Error updating financial target: ${error}`);
        }
      }
    },
    {
      name: 'Unlock Achievement',
      action: () => {
        try {
          const testAchievement = achievements.find(a => !a.unlocked);
          if (testAchievement) {
            unlockAchievement(testAchievement.id);
            addTestResult(`✅ Unlocked achievement: ${testAchievement.title}`);
          } else {
            addTestResult(`ℹ️ All achievements already unlocked`);
          }
        } catch (error) {
          addTestResult(`❌ Error unlocking achievement: ${error}`);
        }
      }
    },
    {
      name: 'Rapid Level Up Test',
      action: () => {
        try {
          // Award enough XP to level up
          for (let i = 0; i < 10; i++) {
            awardExperience('PHASE_1_MILESTONE');
          }
          addTestResult(`✅ Rapid XP test completed - awarded 10x milestone XP`);
        } catch (error) {
          addTestResult(`❌ Error in rapid level up test: ${error}`);
        }
      }
    }
  ];

  const addTestResult = (result: string) => {
    setTestResults(prev => [result, ...prev].slice(0, 10));
  };

  const clearResults = () => {
    setTestResults([]);
  };

  const getStatsDisplay = () => {
    if (!userProgress) return null;

    return {
      totalXP: userProgress.totalXP,
      currentLevel: currentLevel?.level || 1,
      levelTitle: currentLevel?.title || 'Novice',
      unlockedAchievements: achievements.filter(a => a.unlocked).length,
      totalAchievements: achievements.length,
      propFirmAccounts: userProgress.propFirmAccounts?.length || 0,
      winRate: userProgress.stats?.winRate || 0,
      totalTrades: userProgress.stats?.totalTrades || 0,
      totalProfit: userProgress.stats?.totalProfit || 0
    };
  };

  const stats = getStatsDisplay();

  return (
    <div className="max-w-7xl mx-auto p-6 space-y-6">
      {/* Header */}
      <div className="bg-gradient-to-r from-green-600 to-blue-600 rounded-2xl p-6 text-white">
        <h1 className="text-3xl font-bold flex items-center space-x-3">
          <Settings className="w-8 h-8" />
          <span>Gamification Testing Panel</span>
        </h1>
        <p className="text-green-100 mt-2">
          Test and validate the complete gamification system functionality
        </p>
      </div>

      {/* Current Stats Overview */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-gray-800 rounded-xl p-4">
          <div className="flex items-center space-x-3">
            <Trophy className="w-8 h-8 text-yellow-400" />
            <div>
              <div className="text-2xl font-bold text-white">{stats?.totalXP.toLocaleString() || '0'}</div>
              <div className="text-sm text-gray-400">Total XP</div>
            </div>
          </div>
        </div>

        <div className="bg-gray-800 rounded-xl p-4">
          <div className="flex items-center space-x-3">
            <Star className="w-8 h-8 text-purple-400" />
            <div>
              <div className="text-2xl font-bold text-white">{stats?.currentLevel || 1}</div>
              <div className="text-sm text-gray-400">Level ({stats?.levelTitle || 'Novice'})</div>
            </div>
          </div>
        </div>

        <div className="bg-gray-800 rounded-xl p-4">
          <div className="flex items-center space-x-3">
            <Award className="w-8 h-8 text-blue-400" />
            <div>
              <div className="text-2xl font-bold text-white">
                {stats?.unlockedAchievements || 0}/{stats?.totalAchievements || 0}
              </div>
              <div className="text-sm text-gray-400">Achievements</div>
            </div>
          </div>
        </div>

        <div className="bg-gray-800 rounded-xl p-4">
          <div className="flex items-center space-x-3">
            <Target className="w-8 h-8 text-green-400" />
            <div>
              <div className="text-2xl font-bold text-white">{stats?.propFirmAccounts || 0}/30</div>
              <div className="text-sm text-gray-400">Prop Firms</div>
            </div>
          </div>
        </div>
      </div>

      {/* Level Progress */}
      {progressToNext && (
        <div className="bg-gray-800 rounded-xl p-6">
          <h2 className="text-xl font-bold text-white mb-4 flex items-center space-x-2">
            <TrendingUp className="w-6 h-6 text-blue-400" />
            <span>Level Progress</span>
          </h2>
          <div className="space-y-3">
            <div className="flex justify-between text-sm">
              <span className="text-gray-400">Progress to Level {(stats?.currentLevel || 1) + 1}</span>
              <span className="text-white">{progressToNext.percentage.toFixed(1)}%</span>
            </div>
            <div className="w-full bg-gray-700 rounded-full h-4">
              <div 
                className="bg-gradient-to-r from-blue-500 to-purple-500 h-4 rounded-full transition-all duration-500 flex items-center justify-center"
                style={{ width: `${progressToNext.percentage}%` }}
              >
                {progressToNext.percentage > 20 && (
                  <span className="text-xs text-white font-medium">
                    {progressToNext.current.toLocaleString()} / {progressToNext.required.toLocaleString()} XP
                  </span>
                )}
              </div>
            </div>
            {progressToNext.percentage <= 20 && (
              <div className="text-xs text-gray-500 text-center">
                {progressToNext.current.toLocaleString()} / {progressToNext.required.toLocaleString()} XP
              </div>
            )}
          </div>
        </div>
      )}

      {/* Testing Controls */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* XP Testing */}
        <div className="bg-gray-800 rounded-xl p-6">
          <h2 className="text-xl font-bold text-white mb-4 flex items-center space-x-2">
            <Zap className="w-6 h-6 text-yellow-400" />
            <span>XP Testing</span>
          </h2>
          
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                Select XP Action
              </label>
              <select
                value={selectedXPAction}
                onChange={(e) => setSelectedXPAction(e.target.value)}
                className="w-full bg-gray-700 text-white rounded-lg px-3 py-2 border border-gray-600 focus:border-blue-500 focus:outline-none"
              >
                {xpActions.map(action => (
                  <option key={action} value={action}>
                    {action.replace(/_/g, ' ').toLowerCase()}
                  </option>
                ))}
              </select>
            </div>
            
            <button
              onClick={() => testScenarios[0].action()}
              className="w-full bg-yellow-600 hover:bg-yellow-700 text-white px-4 py-2 rounded-lg transition-colors flex items-center justify-center space-x-2"
            >
              <Play className="w-4 h-4" />
              <span>Award XP</span>
            </button>
          </div>
        </div>

        {/* Scenario Testing */}
        <div className="bg-gray-800 rounded-xl p-6">
          <h2 className="text-xl font-bold text-white mb-4 flex items-center space-x-2">
            <Activity className="w-6 h-6 text-green-400" />
            <span>Scenario Testing</span>
          </h2>
          
          <div className="grid grid-cols-1 gap-2">
            {testScenarios.slice(1).map((scenario, index) => (
              <button
                key={index}
                onClick={scenario.action}
                className="bg-gray-700 hover:bg-gray-600 text-white px-4 py-2 rounded-lg transition-colors text-sm flex items-center space-x-2"
              >
                <Play className="w-3 h-3" />
                <span>{scenario.name}</span>
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Test Results */}
      <div className="bg-gray-800 rounded-xl p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-bold text-white flex items-center space-x-2">
            <CheckCircle className="w-6 h-6 text-green-400" />
            <span>Test Results</span>
          </h2>
          <button
            onClick={clearResults}
            className="bg-gray-700 hover:bg-gray-600 text-white px-3 py-1 rounded-lg transition-colors text-sm flex items-center space-x-1"
          >
            <RefreshCw className="w-3 h-3" />
            <span>Clear</span>
          </button>
        </div>
        
        <div className="space-y-2 max-h-64 overflow-y-auto">
          {testResults.length === 0 ? (
            <div className="text-gray-500 text-center py-4">
              No test results yet. Run some tests to see results here.
            </div>
          ) : (
            testResults.map((result, index) => (
              <div
                key={index}
                className={`p-3 rounded-lg text-sm ${
                  result.startsWith('✅') ? 'bg-green-900/20 text-green-400 border border-green-700' :
                  result.startsWith('❌') ? 'bg-red-900/20 text-red-400 border border-red-700' :
                  result.startsWith('ℹ️') ? 'bg-blue-900/20 text-blue-400 border border-blue-700' :
                  'bg-gray-700 text-gray-300'
                }`}
              >
                {result}
              </div>
            ))
          )}
        </div>
      </div>

      {/* Debug Information */}
      <div className="bg-gray-800 rounded-xl p-6">
        <h2 className="text-xl font-bold text-white mb-4 flex items-center space-x-2">
          <Users className="w-6 h-6 text-purple-400" />
          <span>Debug Information</span>
        </h2>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
          <div>
            <h3 className="font-medium text-white mb-2">User Progress</h3>
            <pre className="bg-gray-900 p-3 rounded text-gray-300 overflow-x-auto">
              {JSON.stringify(userProgress, null, 2)}
            </pre>
          </div>
          
          <div>
            <h3 className="font-medium text-white mb-2">Current Level</h3>
            <pre className="bg-gray-900 p-3 rounded text-gray-300 overflow-x-auto">
              {JSON.stringify(currentLevel, null, 2)}
            </pre>
          </div>
        </div>
      </div>
    </div>
  );
};

export default GamificationTestingPanel;
