import { TrendingUp, Target, DollarSign, AlertTriangle, Plus, Edit3, Trash2, BarChart3, Scale, Zap } from 'lucide-react';
import React, { useState } from 'react';

import type { FuturesAccount, FuturesScalingPlan } from '../../types';

interface FuturesScalingProps {
  futuresAccounts: FuturesAccount[];
  onUpdateFuturesAccounts: (accounts: FuturesAccount[]) => void;
}

const FuturesScaling: React.FC<FuturesScalingProps> = ({ futuresAccounts, onUpdateFuturesAccounts }) => {
  const [activeTab, setActiveTab] = useState<'overview' | 'accounts' | 'scaling' | 'performance'>('overview');
  const [showAccountForm, setShowAccountForm] = useState(false);
  const [editingAccount, setEditingAccount] = useState<FuturesAccount | null>(null);

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD'
    }).format(amount);
  };

  const getFirmLogo = (firm: string) => {
    const logos = {
      'take-profit-trader': '🎯',
      'topstep': '📈',
      'apex': '⚡',
      'interactive-brokers': '🏛️'
    };
    return logos[firm as keyof typeof logos] || '💼';
  };

  const getFirmColors = (firm: string) => {
    const colors = {
      'take-profit-trader': 'text-blue-600 bg-blue-100',
      'topstep': 'text-green-600 bg-green-100',
      'apex': 'text-purple-600 bg-purple-100',
      'interactive-brokers': 'text-indigo-600 bg-indigo-100'
    };
    return colors[firm as keyof typeof colors] || 'text-gray-600 bg-gray-100';
  };

  const getStatusColor = (status: string) => {
    const colors = {
      'active': 'text-green-600 bg-green-100',
      'breached': 'text-red-600 bg-red-100',
      'passed-evaluation': 'text-blue-600 bg-blue-100',
      'withdrawn': 'text-gray-600 bg-gray-100',
      'suspended': 'text-orange-600 bg-orange-100',
      'good-standing': 'text-emerald-600 bg-emerald-100'
    };
    return colors[status as keyof typeof colors] || 'text-gray-600 bg-gray-100';
  };

  // Default scaling plans
  const defaultScalingPlans: FuturesScalingPlan[] = [
    {
      firm: 'take-profit-trader',
      maxAccounts: 5,
      maxCapitalPerAccount: 150000,
      totalMaxCapital: 750000,
      currentAccounts: 1,
      currentCapital: 50000,
      nextAccountThreshold: 2500,
      scalingStrategy: 'moderate'
    },
    {
      firm: 'topstep',
      maxAccounts: 5,
      maxCapitalPerAccount: 150000,
      totalMaxCapital: 750000,
      currentAccounts: 1,
      currentCapital: 50000,
      nextAccountThreshold: 2500,
      scalingStrategy: 'moderate'
    },
    {
      firm: 'apex',
      maxAccounts: 20,
      maxCapitalPerAccount: 300000,
      totalMaxCapital: 6000000,
      currentAccounts: 1,
      currentCapital: 50000,
      nextAccountThreshold: 2500,
      scalingStrategy: 'aggressive'
    }
  ];

  // Initialize with default scaling plans if none exist
  const [scalingPlans, setScalingPlans] = useState<FuturesScalingPlan[]>([
    {
      firm: 'take-profit-trader',
      maxAccounts: 10,
      maxCapitalPerAccount: 150000,
      totalMaxCapital: 1500000,
      currentAccounts: 0,
      currentCapital: 0,
      nextAccountThreshold: 3000,
      scalingStrategy: 'moderate'
    },
    {
      firm: 'topstep',
      maxAccounts: 10,
      maxCapitalPerAccount: 150000,
      totalMaxCapital: 1500000,
      currentAccounts: 0,
      currentCapital: 0,
      nextAccountThreshold: 3000,
      scalingStrategy: 'moderate'
    },
    {
      firm: 'apex',
      maxAccounts: 20,
      maxCapitalPerAccount: 300000,
      totalMaxCapital: 6000000,
      currentAccounts: 0,
      currentCapital: 0,
      nextAccountThreshold: 5000,
      scalingStrategy: 'aggressive'
    },
    {
      firm: 'interactive-brokers',
      maxAccounts: 1,
      maxCapitalPerAccount: 1000000,
      totalMaxCapital: 1000000,
      currentAccounts: 0,
      currentCapital: 0,
      nextAccountThreshold: 10000,
      scalingStrategy: 'conservative'
    }
  ]);  const AccountForm: React.FC<{
    account?: FuturesAccount;
    onSave: (account: Omit<FuturesAccount, 'id' | 'createdAt' | 'lastTrade'>) => void;
    onCancel: () => void;
  }> = ({ account, onSave, onCancel }) => {
    const [formData, setFormData] = useState({
      firm: account?.firm || 'apex' as const,
      accountNumber: account?.accountNumber || '',
      accountType: account?.accountType || 'evaluation' as const,
      capitalSize: account?.capitalSize || 50000,
      currentBalance: account?.currentBalance || 50000,
      dailyProfit: account?.dailyProfit || 0,
      weeklyProfit: account?.weeklyProfit || 0,
      monthlyProfit: account?.monthlyProfit || 0,
      maxDrawdown: account?.maxDrawdown || 2500,
      currentDrawdown: account?.currentDrawdown || 0,
      profitTarget: account?.profitTarget || 3000,
      isActive: account?.isActive !== false,
      status: account?.status || 'active' as const
    });

    const handleSubmit = (e: React.FormEvent) => {
      e.preventDefault();
      onSave(formData);
    };

    return (
      <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
        <div className="bg-white rounded-lg max-w-4xl w-full max-h-[90vh] overflow-y-auto">
          <div className="p-6 border-b">
            <h3 className="text-lg font-semibold">
              {account ? 'Edit Futures Account' : 'Add Futures Account'}
            </h3>
            <p className="text-gray-600 text-sm mt-1">
              Track your prop firm evaluation and funded accounts
            </p>
          </div>

          <form onSubmit={handleSubmit} className="p-6 space-y-6">
            {/* Basic Info */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Prop Firm *
                </label>
                <select
                  value={formData.firm}
                  onChange={(e) => setFormData({ ...formData, firm: e.target.value as any })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                >
                  <option value="take-profit-trader">Take Profit Trader</option>
                  <option value="topstep">TopStep</option>
                  <option value="apex">Apex</option>
                  <option value="interactive-brokers">Interactive Brokers</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Account Number *
                </label>
                <input
                  type="text"
                  value={formData.accountNumber}
                  onChange={(e) => setFormData({ ...formData, accountNumber: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                  placeholder="e.g., APX-50001"
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Account Type *
                </label>
                <select
                  value={formData.accountType}
                  onChange={(e) => setFormData({ ...formData, accountType: e.target.value as any })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                >
                  <option value="evaluation">Evaluation</option>
                  <option value="funded">Funded</option>
                  <option value="pro">Pro</option>
                  <option value="personal-futures">Personal Futures</option>
                  <option value="portfolio-margin">Portfolio Margin</option>
                </select>
              </div>
            </div>

            {/* Capital & Balance */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Capital Size (USD) *
                </label>
                <input
                  type="number"
                  value={formData.capitalSize}
                  onChange={(e) => setFormData({ ...formData, capitalSize: parseFloat(e.target.value) || 0 })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Current Balance (USD) *
                </label>
                <input
                  type="number"
                  value={formData.currentBalance}
                  onChange={(e) => setFormData({ ...formData, currentBalance: parseFloat(e.target.value) || 0 })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                  required
                />
              </div>
            </div>

            {/* Performance Metrics */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Daily Profit (USD)
                </label>
                <input
                  type="number"
                  value={formData.dailyProfit}
                  onChange={(e) => setFormData({ ...formData, dailyProfit: parseFloat(e.target.value) || 0 })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Weekly Profit (USD)
                </label>
                <input
                  type="number"
                  value={formData.weeklyProfit}
                  onChange={(e) => setFormData({ ...formData, weeklyProfit: parseFloat(e.target.value) || 0 })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Monthly Profit (USD)
                </label>
                <input
                  type="number"
                  value={formData.monthlyProfit}
                  onChange={(e) => setFormData({ ...formData, monthlyProfit: parseFloat(e.target.value) || 0 })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </div>

            {/* Risk & Targets */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Max Drawdown (USD)
                </label>
                <input
                  type="number"
                  value={formData.maxDrawdown}
                  onChange={(e) => setFormData({ ...formData, maxDrawdown: parseFloat(e.target.value) || 0 })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Current Drawdown (USD)
                </label>
                <input
                  type="number"
                  value={formData.currentDrawdown}
                  onChange={(e) => setFormData({ ...formData, currentDrawdown: parseFloat(e.target.value) || 0 })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Profit Target (USD)
                </label>
                <input
                  type="number"
                  value={formData.profitTarget}
                  onChange={(e) => setFormData({ ...formData, profitTarget: parseFloat(e.target.value) || 0 })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </div>

            {/* Status */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Status
                </label>
                <select
                  value={formData.status}
                  onChange={(e) => setFormData({ ...formData, status: e.target.value as any })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                >
                  <option value="active">Active</option>
                  <option value="breached">Breached</option>
                  <option value="passed-evaluation">Passed Evaluation</option>
                  <option value="withdrawn">Withdrawn</option>
                  <option value="suspended">Suspended</option>
                </select>
              </div>

              <div className="flex items-center space-x-3 pt-8">
                <input
                  type="checkbox"
                  id="isActive"
                  checked={formData.isActive}
                  onChange={(e) => setFormData({ ...formData, isActive: e.target.checked })}
                  className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                />
                <label htmlFor="isActive" className="text-sm font-medium text-gray-700">
                  Active Account
                </label>
              </div>
            </div>

            {/* Action Buttons */}
            <div className="flex justify-end space-x-3 pt-6 border-t">
              <button
                type="button"
                onClick={onCancel}
                className="px-4 py-2 text-gray-600 bg-gray-100 rounded-lg hover:bg-gray-200 transition-colors"
              >
                Cancel
              </button>
              <button
                type="submit"
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
              >
                {account ? 'Update Account' : 'Add Account'}
              </button>
            </div>
          </form>
        </div>
      </div>
    );
  };

  const renderOverview = () => {
    const totalCapital = futuresAccounts.reduce((sum, acc) => sum + acc.capitalSize, 0);
    const totalProfit = futuresAccounts.reduce((sum, acc) => sum + acc.monthlyProfit, 0);
    const activeAccounts = futuresAccounts.filter(acc => acc.isActive).length;
    const maxPossibleCapital = scalingPlans.reduce((sum, plan) => sum + plan.totalMaxCapital, 0);

    return (
      <div className="space-y-6">
        {/* Key Metrics */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
          <div className="bg-gradient-to-r from-blue-500 to-blue-600 rounded-lg p-6 text-white">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-blue-100 text-sm">Active Accounts</p>
                <p className="text-2xl font-bold">{activeAccounts}</p>
                <p className="text-blue-200 text-xs">out of {futuresAccounts.length} total</p>
              </div>
              <Target className="h-8 w-8 text-blue-200" />
            </div>
          </div>

          <div className="bg-gradient-to-r from-green-500 to-green-600 rounded-lg p-6 text-white">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-green-100 text-sm">Current Capital</p>
                <p className="text-2xl font-bold">{formatCurrency(totalCapital)}</p>
                <p className="text-green-200 text-xs">across all accounts</p>
              </div>
              <DollarSign className="h-8 w-8 text-green-200" />
            </div>
          </div>

          <div className="bg-gradient-to-r from-purple-500 to-purple-600 rounded-lg p-6 text-white">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-purple-100 text-sm">Monthly Profit</p>
                <p className="text-2xl font-bold">{formatCurrency(totalProfit)}</p>
                <p className="text-purple-200 text-xs">combined P&L</p>
              </div>
              <TrendingUp className="h-8 w-8 text-purple-200" />
            </div>
          </div>

          <div className="bg-gradient-to-r from-orange-500 to-orange-600 rounded-lg p-6 text-white">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-orange-100 text-sm">Max Potential</p>
                <p className="text-2xl font-bold">{formatCurrency(maxPossibleCapital)}</p>
                <p className="text-orange-200 text-xs">full scaling plan</p>
              </div>
              <Scale className="h-8 w-8 text-orange-200" />
            </div>
          </div>
        </div>

        {/* Scaling Progress */}
        <div className="bg-white rounded-lg border p-6">
          <h3 className="text-lg font-semibold mb-4 flex items-center">
            <Scale className="mr-2 h-5 w-5" />
            Scaling Progress by Firm
          </h3>
          <div className="space-y-4">
            {scalingPlans.map(plan => {
              const firmAccounts = futuresAccounts.filter(acc => acc.firm === plan.firm);
              const currentCapital = firmAccounts.reduce((sum, acc) => sum + acc.capitalSize, 0);
              const progressPercentage = (plan.currentAccounts / plan.maxAccounts) * 100;
              const capitalPercentage = (currentCapital / plan.totalMaxCapital) * 100;

              return (
                <div key={plan.firm} className="border rounded-lg p-4">
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center space-x-3">
                      <span className="text-2xl">{getFirmLogo(plan.firm)}</span>
                      <div>
                        <h4 className="font-medium capitalize">{plan.firm.replace('-', ' ')}</h4>
                        <p className="text-sm text-gray-600">
                          {plan.currentAccounts}/{plan.maxAccounts} accounts • {formatCurrency(currentCapital)}/{formatCurrency(plan.totalMaxCapital)}
                        </p>
                      </div>
                    </div>
                    <span className={`px-3 py-1 rounded-full text-sm font-medium ${getFirmColors(plan.firm)}`}>
                      {plan.scalingStrategy}
                    </span>
                  </div>

                  <div className="space-y-2">
                    <div className="flex justify-between text-sm">
                      <span>Account Progress</span>
                      <span>{progressPercentage.toFixed(1)}%</span>
                    </div>
                    <div className="w-full bg-gray-200 rounded-full h-2">
                      <div 
                        className="bg-blue-600 h-2 rounded-full transition-all"
                        style={{ width: `${Math.min(100, progressPercentage)}%` }}
                      />
                    </div>

                    <div className="flex justify-between text-sm">
                      <span>Capital Progress</span>
                      <span>{capitalPercentage.toFixed(1)}%</span>
                    </div>
                    <div className="w-full bg-gray-200 rounded-full h-2">
                      <div 
                        className="bg-green-600 h-2 rounded-full transition-all"
                        style={{ width: `${Math.min(100, capitalPercentage)}%` }}
                      />
                    </div>
                  </div>

                  {plan.nextAccountThreshold > 0 && (
                    <div className="mt-3 p-3 bg-blue-50 border border-blue-200 rounded-lg">
                      <p className="text-sm text-blue-800">
                        <strong>Next Account:</strong> Need {formatCurrency(plan.nextAccountThreshold)} profit to qualify for next account
                      </p>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* Performance Summary */}
        <div className="bg-white rounded-lg border p-6">
          <h3 className="text-lg font-semibold mb-4 flex items-center">
            <BarChart3 className="mr-2 h-5 w-5" />
            Performance Summary
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <h4 className="font-medium mb-3">Best Performing Accounts</h4>
              <div className="space-y-2">
                {futuresAccounts
                  .sort((a, b) => b.monthlyProfit - a.monthlyProfit)
                  .slice(0, 3)
                  .map(account => (
                    <div key={account.id} className="flex items-center justify-between p-2 bg-gray-50 rounded">
                      <div className="flex items-center space-x-2">
                        <span>{getFirmLogo(account.firm)}</span>
                        <span className="text-sm font-medium">{account.accountNumber}</span>
                      </div>
                      <span className="text-sm font-bold text-green-600">
                        {formatCurrency(account.monthlyProfit)}
                      </span>
                    </div>
                  ))}
              </div>
            </div>

            <div>
              <h4 className="font-medium mb-3">Risk Overview</h4>
              <div className="space-y-2">
                <div className="flex justify-between text-sm">
                  <span>Total Max Drawdown</span>
                  <span className="font-medium">
                    {formatCurrency(futuresAccounts.reduce((sum, acc) => sum + acc.maxDrawdown, 0))}
                  </span>
                </div>
                <div className="flex justify-between text-sm">
                  <span>Current Drawdown</span>
                  <span className="font-medium text-red-600">
                    {formatCurrency(futuresAccounts.reduce((sum, acc) => sum + acc.currentDrawdown, 0))}
                  </span>
                </div>
                <div className="flex justify-between text-sm">
                  <span>Accounts at Risk</span>
                  <span className="font-medium">
                    {futuresAccounts.filter(acc => 
                      acc.currentDrawdown > acc.maxDrawdown * 0.8
                    ).length}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  };

  const renderAccounts = () => (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h3 className="text-lg font-semibold">Futures Accounts</h3>
          <p className="text-gray-600">Manage your prop firm evaluation and funded accounts</p>
        </div>
        <button
          onClick={() => setShowAccountForm(true)}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors flex items-center space-x-2"
        >
          <Plus className="h-4 w-4" />
          <span>Add Account</span>
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {futuresAccounts.map(account => (
          <div key={account.id} className="bg-white rounded-lg border p-6">
            <div className="flex justify-between items-start mb-4">
              <div className="flex items-center space-x-3">
                <span className="text-2xl">{getFirmLogo(account.firm)}</span>
                <div>
                  <h4 className="font-semibold">{account.accountNumber}</h4>
                  <p className="text-sm text-gray-600 capitalize">{account.firm.replace('-', ' ')}</p>
                </div>
              </div>
              <div className="flex items-center space-x-2">
                <span className={`px-2 py-1 rounded-full text-xs font-medium ${getStatusColor(account.status)}`}>
                  {account.status.replace('-', ' ')}
                </span>
                <div className="flex space-x-1">
                  <button
                    onClick={() => {
                      setEditingAccount(account);
                      setShowAccountForm(true);
                    }}
                    className="p-1 text-gray-500 hover:text-blue-600 transition-colors"
                  >
                    <Edit3 className="h-4 w-4" />
                  </button>
                  <button className="p-1 text-gray-500 hover:text-red-600 transition-colors">
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              </div>
            </div>

            <div className="space-y-3">
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <span className="text-gray-600">Capital Size</span>
                  <p className="font-medium">{formatCurrency(account.capitalSize)}</p>
                </div>
                <div>
                  <span className="text-gray-600">Current Balance</span>
                  <p className="font-medium">{formatCurrency(account.currentBalance)}</p>
                </div>
                <div>
                  <span className="text-gray-600">Monthly P&L</span>
                  <p className={`font-medium ${account.monthlyProfit >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                    {formatCurrency(account.monthlyProfit)}
                  </p>
                </div>
                <div>
                  <span className="text-gray-600">Drawdown</span>
                  <p className="font-medium text-red-600">
                    {formatCurrency(account.currentDrawdown)} / {formatCurrency(account.maxDrawdown)}
                  </p>
                </div>
              </div>

              {/* Progress to Profit Target */}
              <div>
                <div className="flex justify-between text-sm mb-1">
                  <span>Profit Target Progress</span>
                  <span>{((account.monthlyProfit / account.profitTarget) * 100).toFixed(1)}%</span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-2">
                  <div 
                    className="bg-green-600 h-2 rounded-full transition-all"
                    style={{ width: `${Math.min(100, (account.monthlyProfit / account.profitTarget) * 100)}%` }}
                  />
                </div>
              </div>

              {/* Drawdown Warning */}
              {account.currentDrawdown > account.maxDrawdown * 0.8 && (
                <div className="flex items-center space-x-2 p-2 bg-red-50 border border-red-200 rounded">
                  <AlertTriangle className="h-4 w-4 text-red-600" />
                  <span className="text-sm text-red-800">High drawdown risk</span>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      {futuresAccounts.length === 0 && (
        <div className="text-center py-12 bg-white rounded-lg border">
          <BarChart3 className="h-12 w-12 text-gray-400 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-900 mb-2">No Futures Accounts</h3>
          <p className="text-gray-600 mb-6">
            Add your prop firm accounts to start tracking performance and scaling progress
          </p>
          <button
            onClick={() => setShowAccountForm(true)}
            className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
          >
            Add First Account
          </button>
        </div>
      )}
    </div>
  );

  const handleSaveAccount = (accountData: Omit<FuturesAccount, 'id' | 'createdAt' | 'lastTrade'>) => {
    const now = new Date().toISOString();
    
    if (editingAccount) {
      // Update existing account
      const updatedAccounts = futuresAccounts.map(account => 
        account.id === editingAccount.id 
          ? { ...account, ...accountData, lastTrade: now }
          : account
      );
      onUpdateFuturesAccounts(updatedAccounts);
    } else {
      // Create new account
      const newAccount: FuturesAccount = {
        ...accountData,
        id: Date.now().toString(),
        createdAt: now,
        lastTrade: now
      };
      onUpdateFuturesAccounts([...futuresAccounts, newAccount]);
    }
    
    setShowAccountForm(false);
    setEditingAccount(null);
  };

  const tabConfig = [
    { id: 'overview', label: 'Overview', icon: TrendingUp },
    { id: 'accounts', label: 'Accounts', icon: BarChart3 },
    { id: 'scaling', label: 'Scaling Plans', icon: Scale },
    { id: 'performance', label: 'Performance', icon: Zap }
  ];

  return (
    <div className="space-y-6">
      {/* Tab Navigation */}
      <div className="border-b border-gray-200">
        <nav className="-mb-px flex space-x-8">
          {tabConfig.map((tab) => {
            const Icon = tab.icon;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as any)}
                className={`py-2 px-1 border-b-2 font-medium text-sm flex items-center ${
                  activeTab === tab.id
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                <Icon className="mr-2 h-4 w-4" />
                {tab.label}
              </button>
            );
          })}
        </nav>
      </div>

      {/* Tab Content */}
      {activeTab === 'overview' && renderOverview()}
      {activeTab === 'accounts' && renderAccounts()}
      {activeTab === 'scaling' && (
        <div className="bg-white rounded-lg border p-6">
          <h3 className="text-lg font-semibold mb-4">Coming Soon: Advanced Scaling Plans</h3>
          <p className="text-gray-600">Configure automatic scaling strategies and profit thresholds</p>
        </div>
      )}
      {activeTab === 'performance' && (
        <div className="bg-white rounded-lg border p-6">
          <h3 className="text-lg font-semibold mb-4">Coming Soon: Detailed Performance Analytics</h3>
          <p className="text-gray-600">Advanced performance metrics and historical analysis</p>
        </div>
      )}

      {/* Account Form Modal */}
      {showAccountForm && (
        <AccountForm
          account={editingAccount || undefined}
          onSave={handleSaveAccount}
          onCancel={() => {
            setShowAccountForm(false);
            setEditingAccount(null);
          }}
        />
      )}
    </div>
  );
};

export default FuturesScaling;
