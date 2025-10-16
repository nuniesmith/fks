import { Target, Trophy, Star, Zap, TrendingUp, Calendar, CheckCircle, Lock } from 'lucide-react';
import React, { useState } from 'react';

interface MilestoneSystemProps {
  userProgress?: any;
}

const MilestoneSystem: React.FC<MilestoneSystemProps> = ({ userProgress }) => {
  const [selectedCategory, setSelectedCategory] = useState('all');
  
  // Enhanced milestone data with more XP and achievement types
  const enhancedMilestones = [
    // Trading Milestones
    {
      id: 'first_prop_account',
      title: 'First Prop Account',
      description: 'Open your first proprietary trading account',
      category: 'trading',
      difficulty: 'beginner',
      xpReward: 500,
      current: 1,
      target: 1,
      unit: 'account',
      status: 'completed',
      canadianTaxBenefit: 'Professional trader tax deductions available',
      completedDate: '2024-12-15',
      badge: '🎯'
    },
    {
      id: 'profitable_month',
      title: 'Profitable Month',
      description: 'Achieve a profitable trading month',
      category: 'trading',
      difficulty: 'intermediate',
      xpReward: 1000,
      current: 2,
      target: 3,
      unit: 'months',
      status: 'in_progress',
      canadianTaxBenefit: 'Consistent income for tax planning',
      badge: '📈'
    },
    {
      id: 'risk_management_master',
      title: 'Risk Management Master',
      description: 'Maintain <2% risk per trade for 50 trades',
      category: 'trading',
      difficulty: 'advanced',
      xpReward: 2000,
      current: 32,
      target: 50,
      unit: 'trades',
      status: 'in_progress',
      canadianTaxBenefit: 'Lower volatility = better tax planning',
      badge: '🛡️'
    },
    
    // Tax Optimization Milestones
    {
      id: 'tfsa_maximizer',
      title: 'TFSA Maximizer',
      description: 'Maximize TFSA contributions for the year',
      category: 'tax',
      difficulty: 'intermediate',
      xpReward: 1500,
      current: 15000,
      target: 88000,
      unit: 'CAD',
      status: 'in_progress',
      canadianTaxBenefit: 'Tax-free growth on all gains',
      badge: '🇨🇦'
    },
    {
      id: 'tax_loss_harvesting',
      title: 'Tax Loss Harvesting Pro',
      description: 'Successfully harvest capital losses to offset gains',
      category: 'tax',
      difficulty: 'advanced',
      xpReward: 1200,
      current: 0,
      target: 5000,
      unit: 'CAD losses',
      status: 'locked',
      canadianTaxBenefit: 'Reduce taxable capital gains',
      badge: '🧮'
    },
    
    // Development & Organization Milestones
    {
      id: 'trading_journal_streak',
      title: 'Trading Journal Streak',
      description: 'Log trades for 30 consecutive days',
      category: 'organization',
      difficulty: 'intermediate',
      xpReward: 800,
      current: 18,
      target: 30,
      unit: 'days',
      status: 'in_progress',
      canadianTaxBenefit: 'Better record keeping for CRA',
      badge: '📔'
    },
    {
      id: 'calendar_integration',
      title: 'Calendar Integration Master',
      description: 'Set up automated trading calendar with Google Calendar',
      category: 'organization',
      difficulty: 'beginner',
      xpReward: 600,
      current: 0,
      target: 1,
      unit: 'setup',
      status: 'available',
      canadianTaxBenefit: 'Track business hours for tax purposes',
      badge: '📅'
    }
  ];

  const xpLevels = [
    { level: 1, name: 'Trading Novice', minXP: 0, maxXP: 999, icon: '🌱', color: 'text-green-400' },
    { level: 2, name: 'Tax-Smart Apprentice', minXP: 1000, maxXP: 2499, icon: '🇨🇦', color: 'text-blue-400' },
    { level: 3, name: 'Profit Strategist', minXP: 2500, maxXP: 4999, icon: '💡', color: 'text-purple-400' },
    { level: 4, name: 'Risk Master', minXP: 5000, maxXP: 9999, icon: '🛡️', color: 'text-orange-400' },
    { level: 5, name: 'Trading Elite', minXP: 10000, maxXP: 19999, icon: '👑', color: 'text-yellow-400' },
    { level: 6, name: 'Canadian Tax Ninja', minXP: 20000, maxXP: 99999, icon: '🥷', color: 'text-red-400' }
  ];

  const categories = [
    { id: 'all', name: 'All Milestones', icon: Target },
    { id: 'trading', name: 'Trading', icon: TrendingUp },
    { id: 'tax', name: 'Tax Optimization', icon: Trophy },
    { id: 'organization', name: 'Organization', icon: Calendar }
  ];

  const mockProgress = userProgress || { totalXP: 3200, completedMilestones: ['first_prop_account'] };
  
  const currentLevel = xpLevels.find(level => 
    mockProgress.totalXP >= level.minXP && mockProgress.totalXP <= level.maxXP
  ) || xpLevels[0];
  
  const nextLevel = xpLevels.find(level => level.level === currentLevel.level + 1);
  const xpProgress = nextLevel ? 
    ((mockProgress.totalXP - currentLevel.minXP) / (nextLevel.minXP - currentLevel.minXP)) * 100 : 100;

  const filteredMilestones = selectedCategory === 'all' ? 
    enhancedMilestones : 
    enhancedMilestones.filter(m => m.category === selectedCategory);

  const getDifficultyColor = (difficulty: string) => {
    switch (difficulty) {
      case 'beginner': return 'bg-green-500/20 text-green-300 border-green-500/50';
      case 'intermediate': return 'bg-yellow-500/20 text-yellow-300 border-yellow-500/50';
      case 'advanced': return 'bg-red-500/20 text-red-300 border-red-500/50';
      default: return 'bg-gray-500/20 text-gray-300 border-gray-500/50';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed': return <CheckCircle className="h-5 w-5 text-green-400" />;
      case 'in_progress': return <Zap className="h-5 w-5 text-blue-400" />;
      case 'available': return <Star className="h-5 w-5 text-yellow-400" />;
      case 'locked': return <Lock className="h-5 w-5 text-gray-400" />;
      default: return <Target className="h-5 w-5 text-white/50" />;
    }
  };

  return (
    <div className="min-h-screen p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header with XP Level */}
        <div className="mb-8">
          <div className="flex items-center justify-between mb-6">
            <div>
              <h1 className="text-4xl font-bold text-white mb-2">Milestone & XP System</h1>
              <p className="text-white/70">Track your progress and level up your trading game</p>
            </div>
          </div>
          
          {/* Current Level Display */}
          <div className="glass-card p-6">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <div className="text-6xl">{currentLevel.icon}</div>
                <div>
                  <h2 className={`text-2xl font-bold ${currentLevel.color}`}>{currentLevel.name}</h2>
                  <p className="text-white/70">Level {currentLevel.level}</p>
                  <p className="text-white font-semibold">{mockProgress.totalXP.toLocaleString()} XP</p>
                </div>
              </div>
              
              {nextLevel && (
                <div className="text-right">
                  <p className="text-white/70 text-sm">Next Level</p>
                  <p className="text-white font-semibold">{nextLevel.name}</p>
                  <p className="text-blue-400">{(nextLevel.minXP - mockProgress.totalXP).toLocaleString()} XP needed</p>
                  <div className="w-48 bg-white/20 rounded-full h-3 mt-2">
                    <div 
                      className="bg-blue-400 h-3 rounded-full transition-all duration-500"
                      style={{ width: `${xpProgress}%` }}
                    />
                  </div>
                  <p className="text-xs text-white/60 mt-1">{xpProgress.toFixed(1)}% to next level</p>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Category Filter */}
        <div className="mb-8">
          <div className="flex gap-2 overflow-x-auto">
            {categories.map((category) => (
              <button
                key={category.id}
                onClick={() => setSelectedCategory(category.id)}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-colors whitespace-nowrap ${
                  selectedCategory === category.id
                    ? 'bg-blue-500/30 text-blue-300 border border-blue-500/50'
                    : 'bg-white/10 text-white/70 border border-white/20 hover:bg-white/20'
                }`}
              >
                <category.icon className="h-4 w-4" />
                {category.name}
              </button>
            ))}
          </div>
        </div>

        {/* Milestones Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {filteredMilestones.map((milestone) => (
            <div 
              key={milestone.id} 
              className={`glass-card p-6 ${
                milestone.status === 'locked' ? 'opacity-60' : ''
              }`}
            >
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-center gap-3">
                  <span className="text-3xl">{milestone.badge}</span>
                  <div>
                    <h3 className="text-xl font-semibold text-white">{milestone.title}</h3>
                    <p className="text-white/70 text-sm">{milestone.description}</p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {getStatusIcon(milestone.status)}
                  <span className={`px-2 py-1 rounded text-xs font-medium border ${getDifficultyColor(milestone.difficulty)}`}>
                    {milestone.difficulty}
                  </span>
                </div>
              </div>

              {/* Progress Bar */}
              <div className="mb-4">
                <div className="flex justify-between items-center mb-2">
                  <span className="text-white/80 text-sm">
                    Progress: {milestone.current.toLocaleString()}/{milestone.target.toLocaleString()} {milestone.unit}
                  </span>
                  <span className="px-3 py-1 bg-purple-500/20 text-purple-300 rounded-full text-sm font-medium border border-purple-500/30">
                    +{milestone.xpReward} XP
                  </span>
                </div>
                <div className="bg-white/20 rounded-full h-2">
                  <div 
                    className={`h-2 rounded-full transition-all duration-500 ${
                      milestone.status === 'completed' ? 'bg-green-400' :
                      milestone.status === 'in_progress' ? 'bg-blue-400' :
                      milestone.status === 'available' ? 'bg-yellow-400' :
                      'bg-gray-400'
                    }`}
                    style={{ width: `${Math.min((milestone.current / milestone.target) * 100, 100)}%` }}
                  />
                </div>
              </div>

              {/* Canadian Tax Benefit */}
              {milestone.canadianTaxBenefit && (
                <div className="p-3 bg-green-500/20 rounded-lg border border-green-500/30">
                  <p className="text-green-300 text-sm">
                    <span className="font-medium">🇨🇦 Tax Benefit:</span> {milestone.canadianTaxBenefit}
                  </p>
                </div>
              )}

              {/* Completion Date */}
              {milestone.completedDate && (
                <div className="mt-3 text-center">
                  <p className="text-green-400 text-sm font-medium">
                    ✅ Completed on {new Date(milestone.completedDate).toLocaleDateString()}
                  </p>
                </div>
              )}
            </div>
          ))}
        </div>

        {/* XP Level Reference */}
        <div className="mt-12 glass-card p-6">
          <h3 className="text-xl font-semibold text-white mb-6">XP Level Reference</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {xpLevels.map((level) => (
              <div 
                key={level.level}
                className={`p-4 rounded-lg border transition-all ${
                  level.level === currentLevel.level 
                    ? 'bg-blue-500/20 border-blue-500/50' 
                    : 'bg-white/10 border-white/20'
                }`}
              >
                <div className="flex items-center gap-3">
                  <span className="text-2xl">{level.icon}</span>
                  <div>
                    <p className={`font-semibold ${level.color}`}>Level {level.level}</p>
                    <p className="text-white text-sm">{level.name}</p>
                    <p className="text-white/60 text-xs">
                      {level.minXP.toLocaleString()} - {level.maxXP.toLocaleString()} XP
                    </p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

export default MilestoneSystem;
