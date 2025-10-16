import { Target, TrendingUp, DollarSign, Shield, Settings, BarChart } from 'lucide-react';
import { ThemeToggle } from '../ThemeToggle';
import { EnvironmentBadge } from '../EnvironmentBadge';
import { DensityToggle } from '../DensityToggle';
import React from 'react';
import { Link } from 'react-router-dom';

import { APP_SECTIONS } from '../../types/layout';
import { TRADING_MILESTONES } from '../../types/milestones';

interface HomePageProps {
  userProgress?: any; // We'll type this properly later
}

const HomePage: React.FC<HomePageProps> = ({ userProgress }) => {
  // Mock data for demonstration
  const mockProgress = {
    totalXP: 2500,
    currentTitle: 'Tax-Smart Apprentice',
    titleColor: 'blue',
    titleIcon: '🇨🇦',
    completedMilestones: ['first_prop_account'],
    accounts: [
      { id: '1', name: 'FTMO Account 1', type: 'prop_firm', currentBalance: 12500, status: 'active' },
      { id: '2', name: 'TFSA - Questrade', type: 'tfsa', currentBalance: 8900, status: 'active' }
    ],
    financialSnapshot: {
      totalNetWorth: 45000,
      monthlyIncome: 3200,
      monthlyExpenses: 2800,
      expenseCoverage: 65,
      taxOptimizationScore: 78,
      canadianTaxSavings: 2400
    }
  };

  const progress = userProgress || mockProgress;

  // Get next milestone
  const nextMilestone = TRADING_MILESTONES.find(m => 
    !progress.completedMilestones.includes(m.id) && m.priority === 'high'
  );

  // Quick stats
  const quickStats = [
    {
      title: 'Total XP',
      value: progress.totalXP.toLocaleString(),
      icon: TrendingUp,
  color: 'text-blue-400'
    },
    {
      title: 'Expense Coverage',
      value: `${progress.financialSnapshot.expenseCoverage}%`,
      icon: DollarSign,
  color: 'text-green-400'
    },
    {
      title: 'Tax Savings',
      value: `$${progress.financialSnapshot.canadianTaxSavings.toLocaleString()}`,
      icon: Shield,
  color: 'text-purple-400'
    },
    {
      title: 'Active Accounts',
      value: progress.accounts.filter((a: any) => a.status === 'active').length,
      icon: BarChart,
  color: 'text-orange-400'
    }
  ];

  // Get main sections for quick access - organized into two main categories
  const activeTradingSections = APP_SECTIONS.filter(section => 
    ['trading', 'strategy', 'accounts'].includes(section.id)
  );
  
  const longTermSections = [
    {
      id: 'taxes',
      title: 'Tax Optimization',
      description: 'Maximize your Canadian tax benefits',
      icon: '🇨🇦',
      category: 'long-term'
    },
    {
      id: 'portfolio',
      title: 'Long-term Portfolio',
      description: 'TFSA, RRSP & investment accounts',
      icon: '📈',
      category: 'long-term'
    },
    {
      id: 'calendar',
      title: 'Dev Calendar',
      description: 'Schedule & track development work',
      icon: '📅',
      category: 'organization'
    }
  ];

  return (
    <div className="min-h-screen p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-4xl font-bold text-white mb-2">
                Welcome to FKS Trading Platform
              </h1>
              <div className="flex items-center gap-3">
                <span className="text-2xl">{progress.titleIcon}</span>
                <span className={`text-xl font-semibold text-blue-400`}>
                  {progress.currentTitle}
                </span>
                <span className="text-white/60">•</span>
                <span className="text-white/80">{progress.totalXP.toLocaleString()} XP</span>
              </div>
            </div>
            <div className="flex items-center gap-4">
              <div className="text-right text-white/70">
                <p className="text-lg font-mono">
                  {new Date().toLocaleTimeString('en-CA', { 
                    hour: '2-digit', 
                    minute: '2-digit',
                    timeZone: 'America/Toronto'
                  })} EST
                </p>
                <p className="text-sm">
                  {new Date().toLocaleDateString('en-CA', { 
                    weekday: 'short', 
                    month: 'short', 
                    day: 'numeric' 
                  })}
                </p>
              </div>
              <button className="p-2 rounded-lg bg-white/10 hover:bg-white/20 transition-colors border border-white/20">
                <Settings className="h-5 w-5 text-white/80" />
              </button>
              <ThemeToggle />
              <DensityToggle />
              <EnvironmentBadge />
            </div>
          </div>
        </div>

        {/* Quick Stats */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
          {quickStats.map((stat, index) => (
            <div
              key={index}
              className="glass-card p-6 group transition-transform duration-300 hover:scale-[1.02] focus-within:scale-[1.02] outline-none"
              tabIndex={0}
            >
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-white/70 tracking-wide">{stat.title}</p>
                  <p className="mt-1 text-2xl font-bold text-white drop-shadow-sm">{stat.value}</p>
                </div>
                <div className={`p-2 rounded-xl bg-white/10 border border-white/10 shadow-inner group-hover:bg-white/15 group-focus-visible:bg-white/15 transition-colors ${stat.color}`}>
                  <stat.icon className={`h-6 w-6 ${stat.color}`} />
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Current Focus & Next Milestone */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
          {/* Next Milestone */}
          <div className="glass-card p-6">
            <div className="flex items-center gap-3 mb-4">
              <Target className="h-6 w-6 text-blue-400" />
              <h3 className="text-xl font-semibold text-white">Next Milestone</h3>
            </div>
            {nextMilestone ? (
              <div>
                <h4 className="font-semibold text-white mb-2">{nextMilestone.title}</h4>
                <p className="text-white/80 mb-4">{nextMilestone.description}</p>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-white/70">
                    Progress: {nextMilestone.current}/{nextMilestone.target} {nextMilestone.unit}
                  </span>
                  <span className="px-3 py-1 bg-blue-500/20 text-blue-300 rounded-full text-sm font-medium border border-blue-500/30">
                    +{nextMilestone.xpReward} XP
                  </span>
                </div>
                <div className="mt-3 bg-white/20 rounded-full h-2">
                  <div 
                    className="bg-blue-400 h-2 rounded-full transition-all duration-300"
                    style={{ width: `${(nextMilestone.current / nextMilestone.target) * 100}%` }}
                  />
                </div>
                {nextMilestone.canadianTaxBenefit && (
                  <div className="mt-3 p-3 bg-green-500/20 rounded-lg border border-green-500/30">
                    <p className="text-sm text-green-300">
                      <span className="font-medium">🇨🇦 Tax Benefit:</span> {nextMilestone.canadianTaxBenefit}
                    </p>
                  </div>
                )}
              </div>
            ) : (
              <p className="text-white/70">No active milestones. Great job!</p>
            )}
          </div>

          {/* Financial Overview */}
          <div className="glass-card p-6">
            <div className="flex items-center gap-3 mb-4">
              <DollarSign className="h-6 w-6 text-green-400" />
              <h3 className="text-xl font-semibold text-white">Financial Overview</h3>
            </div>
            <div className="space-y-4">
              <div className="flex justify-between items-center">
                <span className="text-white/80">Monthly Income</span>
                <span className="font-semibold text-green-400">
                  ${progress.financialSnapshot.monthlyIncome.toLocaleString()} CAD
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-white/80">Monthly Expenses</span>
                <span className="font-semibold text-red-400">
                  ${progress.financialSnapshot.monthlyExpenses.toLocaleString()} CAD
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-white/80">Net Worth</span>
                <span className="font-semibold text-blue-400">
                  ${progress.financialSnapshot.totalNetWorth.toLocaleString()} CAD
                </span>
              </div>
              <div className="mt-4 p-3 bg-blue-500/20 rounded-lg border border-blue-500/30">
                <div className="flex justify-between items-center">
                  <span className="text-blue-300 font-medium">Tax Optimization Score</span>
                  <span className="text-blue-200 font-bold">
                    {progress.financialSnapshot.taxOptimizationScore}/100
                  </span>
                </div>
                <div className="mt-2 bg-blue-400/30 rounded-full h-2">
                  <div 
                    className="bg-blue-400 h-2 rounded-full transition-all duration-300"
                    style={{ width: `${progress.financialSnapshot.taxOptimizationScore}%` }}
                  />
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Quick Access - Active Trading */}
        <div className="glass-card p-6 mb-6">
          <h3 className="text-xl font-semibold text-white mb-2">Active Trading</h3>
          <p className="text-white/60 text-sm mb-6">Real-time trading & money-making strategies</p>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {activeTradingSections.map((section) => (
              <Link
                key={section.id}
                to={section.path}
                className="flex flex-col items-center p-4 rounded-lg border border-white/20 bg-white/10 hover:border-blue-400/50 hover:bg-blue-500/20 transition-all duration-200 group"
              >
                <span className="text-3xl mb-2">{section.icon}</span>
                <span className="font-medium text-white group-hover:text-blue-300 text-center">
                  {section.title}
                </span>
                <span className="text-sm text-white/60 text-center mt-1">
                  {section.description}
                </span>
              </Link>
            ))}
          </div>
        </div>

        {/* Quick Access - Long-term & Organization */}
        <div className="glass-card p-6 mb-8">
          <h3 className="text-xl font-semibold text-white mb-2">Long-term & Organization</h3>
          <p className="text-white/60 text-sm mb-6">Tax optimization, long-term investments & development planning</p>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {longTermSections.map((section) => (
              <Link
                key={section.id}
                to={section.id === 'taxes' ? '/taxes' : section.id === 'portfolio' ? '/portfolio' : '/calendar'}
                className="flex flex-col items-center p-4 rounded-lg border border-white/20 bg-white/10 hover:border-green-400/50 hover:bg-green-500/20 transition-all duration-200 group"
              >
                <span className="text-3xl mb-2">{section.icon}</span>
                <span className="font-medium text-white group-hover:text-green-300 text-center">
                  {section.title}
                </span>
                <span className="text-sm text-white/60 text-center mt-1">
                  {section.description}
                </span>
              </Link>
            ))}
          </div>
        </div>

        {/* Active Accounts Summary */}
        <div className="glass-card p-6">
          <div className="flex items-center gap-3 mb-6">
            <BarChart className="h-6 w-6 text-orange-400" />
            <h3 className="text-xl font-semibold text-white">Active Accounts</h3>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {progress.accounts.filter((account: any) => account.status === 'active').map((account: any) => (
              <div key={account.id} className="p-4 border border-white/20 bg-white/10 rounded-lg">
                <div className="flex items-center justify-between mb-2">
                  <h4 className="font-medium text-white">{account.name}</h4>
                  <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                    account.type === 'prop_firm' ? 'bg-blue-500/30 text-blue-300 border border-blue-500/50' :
                    account.type === 'tfsa' ? 'bg-green-500/30 text-green-300 border border-green-500/50' :
                    'bg-gray-500/30 text-gray-300 border border-gray-500/50'
                  }`}>
                    {account.type.toUpperCase().replace('_', ' ')}
                  </span>
                </div>
                <p className="text-2xl font-bold text-white">
                  ${account.currentBalance.toLocaleString()} CAD
                </p>
                <p className="text-sm text-white/60 capitalize">
                  Status: {account.status}
                </p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

export default HomePage;
