import { 
  DollarSign, 
  Target, 
  Plus, 
  TrendingUp,
  Home,
  Car,
  ShoppingCart,
  Utensils,
  Zap,
  Phone,
  Heart,
  GraduationCap,
  Edit,
  Trash2,
  CheckCircle
} from 'lucide-react';
import React, { useState } from 'react';

import { useGamification } from '../../context/GamificationContext';

import type { FinancialTarget } from '../../types/gamification';

const FinancialTargetsManager: React.FC = () => {
  const { userProgress, updateFinancialTarget: _updateFinancialTarget, awardExperience } = useGamification();
  const [isAddingTarget, setIsAddingTarget] = useState(false);
  const [newTarget, setNewTarget] = useState({
    category: 'monthly_expenses' as FinancialTarget['category'],
    description: '',
    targetAmount: 0,
    priority: 'medium' as FinancialTarget['priority']
  });

  const expenseCategories = [
    { id: 'housing', icon: Home, label: 'Housing', color: 'blue', typical: 1500 },
    { id: 'transportation', icon: Car, label: 'Transportation', color: 'green', typical: 400 },
    { id: 'groceries', icon: ShoppingCart, label: 'Groceries', color: 'purple', typical: 600 },
    { id: 'dining', icon: Utensils, label: 'Dining Out', color: 'orange', typical: 300 },
    { id: 'utilities', icon: Zap, label: 'Utilities', color: 'yellow', typical: 200 },
    { id: 'phone', icon: Phone, label: 'Phone/Internet', color: 'cyan', typical: 150 },
    { id: 'healthcare', icon: Heart, label: 'Healthcare', color: 'red', typical: 300 },
    { id: 'education', icon: GraduationCap, label: 'Education', color: 'indigo', typical: 200 },
  ];

  const handleAddTarget = () => {
    const target: FinancialTarget = {
      id: `target_${Date.now()}`,
      category: newTarget.category,
      description: newTarget.description,
      targetAmount: newTarget.targetAmount,
      currentAmount: 0,
      isActive: true,
      priority: newTarget.priority
    };

    // In a real app, this would make an API call
    // For now, we'll just award experience
    awardExperience('STRATEGY_CREATED'); // Temporary XP award

  setIsAddingTarget(false);
  setNewTarget({
      category: 'monthly_expenses',
      description: '',
      targetAmount: 0,
      priority: 'medium'
    });
  };

  const calculateTotalMonthlyExpenses = () => {
    return userProgress?.financialTargets
      .filter(target => target.category === 'monthly_expenses' && target.isActive)
      .reduce((sum, target) => sum + target.targetAmount, 0) || 0;
  };

  const calculateCurrentIncome = () => {
    return userProgress?.stats.monthlyIncome || 0;
  };

  const getCoveragePercentage = () => {
    const totalExpenses = calculateTotalMonthlyExpenses();
    const currentIncome = calculateCurrentIncome();
    return totalExpenses > 0 ? (currentIncome / totalExpenses) * 100 : 0;
  };

  const getPriorityColor = (priority: FinancialTarget['priority']) => {
    switch (priority) {
      case 'critical': return 'text-red-400 bg-red-900/20 border-red-500';
      case 'high': return 'text-orange-400 bg-orange-900/20 border-orange-500';
      case 'medium': return 'text-yellow-400 bg-yellow-900/20 border-yellow-500';
      case 'low': return 'text-gray-400 bg-gray-900/20 border-gray-500';
      default: return 'text-gray-400 bg-gray-900/20 border-gray-500';
    }
  };

  if (!userProgress) {
    return <div className="p-6 text-white">Loading...</div>;
  }

  const { financialTargets } = userProgress;
  const totalExpenses = calculateTotalMonthlyExpenses();
  const currentIncome = calculateCurrentIncome();
  const coveragePercentage = getCoveragePercentage();
  const isExpensesCovered = coveragePercentage >= 100;

  return (
    <div className="p-6 bg-gray-900 text-white space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Financial Targets</h1>
          <p className="text-gray-400">Track your path to financial independence</p>
        </div>
        <div className="text-right">
          <div className="text-sm text-gray-400">Expense Coverage</div>
          <div className={`text-2xl font-bold ${isExpensesCovered ? 'text-green-400' : 'text-orange-400'}`}>
            {coveragePercentage.toFixed(1)}%
          </div>
        </div>
      </div>

      {/* Overview Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-2xl font-bold text-blue-400">${totalExpenses.toLocaleString()}</div>
              <div className="text-sm text-gray-400">Monthly Expenses</div>
            </div>
            <Target className="w-8 h-8 text-blue-400" />
          </div>
        </div>

        <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-2xl font-bold text-green-400">${currentIncome.toLocaleString()}</div>
              <div className="text-sm text-gray-400">Monthly Income</div>
            </div>
            <TrendingUp className="w-8 h-8 text-green-400" />
          </div>
        </div>

        <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
          <div className="flex items-center justify-between">
            <div>
              <div className={`text-2xl font-bold ${currentIncome - totalExpenses >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                ${(currentIncome - totalExpenses).toLocaleString()}
              </div>
              <div className="text-sm text-gray-400">Monthly Surplus</div>
            </div>
            <DollarSign className={`w-8 h-8 ${currentIncome - totalExpenses >= 0 ? 'text-green-400' : 'text-red-400'}`} />
          </div>
        </div>

        <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-2xl font-bold text-purple-400">
                {financialTargets.filter(t => t.isActive).length}
              </div>
              <div className="text-sm text-gray-400">Active Targets</div>
            </div>
            <Target className="w-8 h-8 text-purple-400" />
          </div>
        </div>
      </div>

      {/* Progress Overview */}
      <div className="bg-gradient-to-r from-blue-900/50 to-purple-900/50 rounded-lg p-6 border border-blue-500/20">
        <h2 className="text-xl font-bold mb-4">Phase 1 Progress: Expense Coverage</h2>
        
        <div className="space-y-4">
          <div className="flex justify-between items-center">
            <span className="font-medium">Total Coverage Progress</span>
            <span className={`font-bold ${isExpensesCovered ? 'text-green-400' : 'text-orange-400'}`}>
              {coveragePercentage.toFixed(1)}%
            </span>
          </div>
          
          <div className="w-full bg-gray-700 rounded-full h-4">
            <div 
              className={`h-4 rounded-full transition-all duration-500 ${
                isExpensesCovered 
                  ? 'bg-gradient-to-r from-green-500 to-emerald-500' 
                  : 'bg-gradient-to-r from-blue-500 to-purple-500'
              }`}
              style={{ width: `${Math.min(coveragePercentage, 100)}%` }}
            ></div>
          </div>

          {isExpensesCovered ? (
            <div className="flex items-center space-x-2 text-green-400">
              <CheckCircle className="w-5 h-5" />
              <span className="font-medium">Congratulations! Your expenses are fully covered!</span>
            </div>
          ) : (
            <div className="text-gray-400">
              You need ${(totalExpenses - currentIncome).toLocaleString()} more monthly income to cover all expenses.
            </div>
          )}
        </div>
      </div>

      {/* Quick Expense Setup */}
      <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
        <h3 className="text-xl font-bold mb-4">Quick Expense Setup</h3>
        <p className="text-gray-400 mb-4">Set up your typical monthly expenses to track your progress</p>
        
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {expenseCategories.map(category => {
            const IconComponent = category.icon;
            const existingTarget = financialTargets.find(
              t => t.description.toLowerCase().includes(category.label.toLowerCase())
            );
            
            return (
              <button
                key={category.id}
                onClick={() => {
                  if (!existingTarget) {
                    setNewTarget({
                      category: 'monthly_expenses',
                      description: category.label,
                      targetAmount: category.typical,
                      priority: 'medium'
                    });
                    setIsAddingTarget(true);
                  }
                }}
                className={`p-3 rounded-lg border transition-colors ${
                  existingTarget 
                    ? 'bg-green-900/20 border-green-500/30 text-green-400'
                    : 'bg-gray-700 border-gray-600 hover:bg-gray-600 text-gray-300'
                }`}
                disabled={!!existingTarget}
              >
                <IconComponent className="w-6 h-6 mx-auto mb-2" />
                <div className="text-sm font-medium">{category.label}</div>
                <div className="text-xs text-gray-400">${category.typical}</div>
                {existingTarget && (
                  <div className="text-xs text-green-400 mt-1">✓ Added</div>
                )}
              </button>
            );
          })}
        </div>
      </div>

      {/* Add Target Button */}
      <div className="flex justify-between items-center">
        <h2 className="text-xl font-bold">Your Financial Targets</h2>
        <button
          onClick={() => setIsAddingTarget(true)}
          className="bg-blue-600 hover:bg-blue-700 px-4 py-2 rounded-lg flex items-center space-x-2 transition-colors"
        >
          <Plus className="w-4 h-4" />
          <span>Add Custom Target</span>
        </button>
      </div>

      {/* Add/Edit Target Modal */}
      {isAddingTarget && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-gray-800 rounded-lg p-6 w-full max-w-md border border-gray-700">
            <h3 className="text-xl font-bold mb-4">Add Financial Target</h3>
            
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-2">Category</label>
                <select
                  value={newTarget.category}
                  onChange={(e) => setNewTarget({ ...newTarget, category: e.target.value as FinancialTarget['category'] })}
                  className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-white"
                >
                  <option value="monthly_expenses">Monthly Expenses</option>
                  <option value="yearly_expenses">Yearly Expenses</option>
                  <option value="investment_goal">Investment Goal</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium mb-2">Description</label>
                <input
                  type="text"
                  value={newTarget.description}
                  onChange={(e) => setNewTarget({ ...newTarget, description: e.target.value })}
                  placeholder="e.g., Housing, Car payment, Emergency fund"
                  className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-white"
                />
              </div>

              <div>
                <label className="block text-sm font-medium mb-2">Target Amount</label>
                <input
                  type="number"
                  value={newTarget.targetAmount}
                  onChange={(e) => setNewTarget({ ...newTarget, targetAmount: Number(e.target.value) })}
                  placeholder="0"
                  className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-white"
                  min="0"
                />
              </div>

              <div>
                <label className="block text-sm font-medium mb-2">Priority</label>
                <select
                  value={newTarget.priority}
                  onChange={(e) => setNewTarget({ ...newTarget, priority: e.target.value as FinancialTarget['priority'] })}
                  className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-white"
                >
                  <option value="critical">Critical</option>
                  <option value="high">High</option>
                  <option value="medium">Medium</option>
                  <option value="low">Low</option>
                </select>
              </div>
            </div>

            <div className="flex space-x-3 mt-6">
              <button
                onClick={handleAddTarget}
                disabled={!newTarget.description || newTarget.targetAmount <= 0}
                className="flex-1 bg-green-600 hover:bg-green-700 disabled:bg-gray-600 px-4 py-2 rounded-lg transition-colors"
              >
                Add Target
              </button>
              <button
                onClick={() => setIsAddingTarget(false)}
                className="flex-1 bg-gray-600 hover:bg-gray-700 px-4 py-2 rounded-lg transition-colors"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Targets List */}
      {financialTargets.length > 0 ? (
        <div className="space-y-4">
          {financialTargets
            .filter(target => target.isActive)
            .sort((a, b) => {
              const priorityOrder = { critical: 0, high: 1, medium: 2, low: 3 };
              return priorityOrder[a.priority] - priorityOrder[b.priority];
            })
            .map(target => {
              const progressPercentage = target.targetAmount > 0 
                ? (target.currentAmount / target.targetAmount) * 100 
                : 0;
              
              return (
                <div key={target.id} className="bg-gray-800 rounded-lg p-4 border border-gray-700">
                  <div className="flex items-center justify-between mb-3">
                    <div>
                      <h3 className="font-bold">{target.description}</h3>
                      <p className="text-sm text-gray-400 capitalize">
                        {target.category.replace('_', ' ')}
                      </p>
                    </div>
                    <div className="flex items-center space-x-2">
                      <div className={`text-xs px-2 py-1 rounded border ${getPriorityColor(target.priority)}`}>
                        {target.priority}
                      </div>
                      <button className="p-1 hover:bg-gray-700 rounded">
                        <Edit className="w-4 h-4 text-gray-400" />
                      </button>
                      <button className="p-1 hover:bg-gray-700 rounded">
                        <Trash2 className="w-4 h-4 text-red-400" />
                      </button>
                    </div>
                  </div>

                  <div className="space-y-2">
                    <div className="flex justify-between text-sm">
                      <span>Progress: ${target.currentAmount.toLocaleString()}</span>
                      <span>Target: ${target.targetAmount.toLocaleString()}</span>
                    </div>
                    <div className="w-full bg-gray-700 rounded-full h-2">
                      <div 
                        className={`h-2 rounded-full transition-all duration-300 ${
                          progressPercentage >= 100 ? 'bg-green-500' : 'bg-blue-500'
                        }`}
                        style={{ width: `${Math.min(progressPercentage, 100)}%` }}
                      ></div>
                    </div>
                    <div className="text-xs text-gray-400 text-center">
                      {progressPercentage.toFixed(1)}% complete
                    </div>
                  </div>
                </div>
              );
            })}
        </div>
      ) : (
        <div className="bg-gray-800 rounded-lg p-8 text-center border border-gray-700">
          <Target className="w-16 h-16 text-gray-600 mx-auto mb-4" />
          <h3 className="text-xl font-bold mb-2">No Financial Targets Set</h3>
          <p className="text-gray-400 mb-4">
            Start by setting up your monthly expenses to track your progress towards financial independence.
          </p>
          <button
            onClick={() => setIsAddingTarget(true)}
            className="bg-blue-600 hover:bg-blue-700 px-6 py-3 rounded-lg font-medium transition-colors"
          >
            Set Your First Target
          </button>
        </div>
      )}
    </div>
  );
};

export default FinancialTargetsManager;
