import { DollarSign, Target, TrendingUp, Plus, Edit3, Trash2, Calculator, PiggyBank, Shield, AlertTriangle, Bitcoin, BarChart3, Link, Building2 } from 'lucide-react';
import React, { useState } from 'react';


import CryptoTracking from './FinancialTargets/CryptoTracking';
import FuturesScaling from './FinancialTargets/FuturesScaling';
import IntegrationAndAlerts from './FinancialTargets/IntegrationAndAlerts';
import StockPortfolioTracking from './FinancialTargets/StockPortfolio';

import type { 
  FinancialTarget, 
  PersonalExpenses, 
  TradingCapitalRequirement, 
  FinancialDashboard, 
  CryptoPortfolio,
  FuturesAccount,
  StockPortfolio,
  APIConnection,
  AlertConfig
} from '../types';

export default function FinancialTargetsManager() {
  const [activeTab, setActiveTab] = useState('targets');
  const [targets, setTargets] = useState<FinancialTarget[]>([
    {
      id: '1',
      name: 'Daily Trading Profit',
      description: 'Daily profit target from futures trading',
      targetAmount: 500,
      period: 'daily',
      category: 'trading-income',
      priority: 'high',
      isActive: true,
      createdAt: new Date().toISOString(),
      lastModified: new Date().toISOString()
    },
    {
      id: '2',
      name: 'Weekly Expenses Coverage',
      description: 'Weekly income to cover all personal expenses',
      targetAmount: 2500,
      period: 'weekly',
      category: 'expense-coverage',
      priority: 'critical',
      isActive: true,
      createdAt: new Date().toISOString(),
      lastModified: new Date().toISOString()
    },
    {
      id: '3',
      name: 'Monthly Savings Goal',
      description: 'Monthly savings for TFSA and RRSP',
      targetAmount: 2000,
      period: 'monthly',
      category: 'savings',
      priority: 'high',
      isActive: true,
      createdAt: new Date().toISOString(),
      lastModified: new Date().toISOString()
    },
    {
      id: '4',
      name: 'Long-term Bitcoin Allocation',
      description: 'Monthly allocation to Bitcoin for long-term wealth building',
      targetAmount: 1500,
      period: 'monthly',
      category: 'investment-goal',
      priority: 'high',
      isActive: true,
      createdAt: new Date().toISOString(),
      lastModified: new Date().toISOString()
    }
  ]);

  const [personalExpenses, setPersonalExpenses] = useState<PersonalExpenses>({
    housing: {
      rent: 1800,
      utilities: 200,
      insurance: 150,
      maintenance: 100
    },
    transportation: {
      carPayment: 400,
      insurance: 120,
      fuel: 200,
      maintenance: 100
    },
    food: {
      groceries: 400,
      diningOut: 200
    },
    utilities: {
      phone: 80,
      internet: 70,
      streaming: 50
    },
    healthcare: {
      insurance: 200,
      medications: 50,
      dental: 100
    },
    personal: {
      clothing: 100,
      entertainment: 150,
      hobbies: 100,
      miscellaneous: 200
    },
    debt: {
      creditCards: 0,
      loans: 0,
      studentLoans: 0
    },
    savings: {
      emergency: 300,
      retirement: 500,
      investments: 200
    }
  });

  const [capitalRequirements, setCapitalRequirements] = useState<TradingCapitalRequirement>({
    minimumOperatingCapital: 25000,
    emergencyBuffer: 10000,
    scalingCapital: 50000,
    riskManagementBuffer: 15000
  });

  const [cryptoPortfolio, setCryptoPortfolio] = useState<CryptoPortfolio>({
    totalValue: 0,
    totalValueCAD: 0,
    totalValueUSD: 0,
    holdings: [],
    hardwareWallets: [],
    wallets: [],
    allocationStrategy: {
      monthlyDCAAmount: 1500,
      targetBitcoinPercentage: 70,
      targetAltcoinPercentage: 30,
      rebalanceFrequency: 'monthly',
      profitAllocationPercentage: 20
    },
    allocationTarget: 20,
    monthlyAllocation: 1500,
    lastRebalanced: new Date().toISOString(),
    createdAt: new Date().toISOString(),
    lastUpdated: new Date().toISOString()
  });

  const [futuresAccounts, setFuturesAccounts] = useState<FuturesAccount[]>([]);
  
  const [stockPortfolios, setStockPortfolios] = useState<StockPortfolio[]>([]);

  const [apiConnections, setApiConnections] = useState<APIConnection[]>([]);

  const [alertConfigs, setAlertConfigs] = useState<AlertConfig[]>([]);

  const [showNewTargetForm, setShowNewTargetForm] = useState(false);
  const [editingTarget, setEditingTarget] = useState<FinancialTarget | null>(null);

  const [newTarget, setNewTarget] = useState<Partial<FinancialTarget>>({
    name: '',
    description: '',
    targetAmount: 0,
    period: 'daily',
    category: 'trading-income',
    priority: 'medium',
    isActive: true
  });

  // Calculate total monthly expenses
  const calculateTotalMonthlyExpenses = (): number => {
    const housing = Object.values(personalExpenses.housing).reduce((sum, val) => sum + val, 0);
    const transportation = Object.values(personalExpenses.transportation).reduce((sum, val) => sum + val, 0);
    const food = Object.values(personalExpenses.food).reduce((sum, val) => sum + val, 0);
    const utilities = Object.values(personalExpenses.utilities).reduce((sum, val) => sum + val, 0);
    const healthcare = Object.values(personalExpenses.healthcare).reduce((sum, val) => sum + val, 0);
    const personal = Object.values(personalExpenses.personal).reduce((sum, val) => sum + val, 0);
    const debt = Object.values(personalExpenses.debt).reduce((sum, val) => sum + val, 0);
    const savings = Object.values(personalExpenses.savings).reduce((sum, val) => sum + val, 0);
    
    return housing + transportation + food + utilities + healthcare + personal + debt + savings;
  };

  // Calculate dashboard metrics
  const getDashboardMetrics = (): FinancialDashboard => {
    const totalMonthlyExpenses = calculateTotalMonthlyExpenses();
    const dailyTargets = targets.filter(t => t.period === 'daily' && t.isActive);
    const weeklyTargets = targets.filter(t => t.period === 'weekly' && t.isActive);
    const monthlyTargets = targets.filter(t => t.period === 'monthly' && t.isActive);

    const totalDailyTarget = dailyTargets.reduce((sum, target) => sum + target.targetAmount, 0);
    const totalWeeklyTarget = weeklyTargets.reduce((sum, target) => sum + target.targetAmount, 0);
    const totalMonthlyTarget = monthlyTargets.reduce((sum, target) => sum + target.targetAmount, 0);

    const projectedMonthlyIncome = (totalDailyTarget * 22) + (totalWeeklyTarget * 4.33) + totalMonthlyTarget;
    const surplusDeficit = projectedMonthlyIncome - totalMonthlyExpenses;

    return {
      totalMonthlyExpenses,
      projectedMonthlyIncome,
      surplusDeficit,
      expenseCoverage: totalMonthlyExpenses > 0 ? (projectedMonthlyIncome / totalMonthlyExpenses) * 100 : 0,
      totalCapitalRequired: Object.values(capitalRequirements).reduce((sum, val) => sum + val, 0),
      activeTargetsCount: targets.filter(t => t.isActive).length,
      criticalTargetsCount: targets.filter(t => t.priority === 'critical' && t.isActive).length
    };
  };

  const addTarget = () => {
    if (newTarget.name && newTarget.targetAmount) {
      const target: FinancialTarget = {
        id: Date.now().toString(),
        name: newTarget.name,
        description: newTarget.description || '',
        targetAmount: newTarget.targetAmount,
        period: newTarget.period || 'daily',
        category: newTarget.category || 'trading-income',
        priority: newTarget.priority || 'medium',
        isActive: true,
        createdAt: new Date().toISOString(),
        lastModified: new Date().toISOString()
      };

      setTargets([...targets, target]);
      setNewTarget({
        name: '',
        description: '',
        targetAmount: 0,
        period: 'daily',
        category: 'trading-income',
        priority: 'medium',
        isActive: true
      });
      setShowNewTargetForm(false);
    }
  };

  const updateTarget = (updatedTarget: FinancialTarget) => {
    setTargets(targets.map(target => 
      target.id === updatedTarget.id 
        ? { ...updatedTarget, lastModified: new Date().toISOString() }
        : target
    ));
    setEditingTarget(null);
  };

  const deleteTarget = (id: string) => {
    setTargets(targets.filter(target => target.id !== id));
  };

  const toggleTargetActive = (id: string) => {
    setTargets(targets.map(target => 
      target.id === id 
        ? { ...target, isActive: !target.isActive, lastModified: new Date().toISOString() }
        : target
    ));
  };

  const dashboard = getDashboardMetrics();

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-CA', {
      style: 'currency',
      currency: 'CAD'
    }).format(amount);
  };

  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case 'critical': return 'text-red-600 bg-red-50';
      case 'high': return 'text-orange-600 bg-orange-50';
      case 'medium': return 'text-yellow-600 bg-yellow-50';
      case 'low': return 'text-green-600 bg-green-50';
      default: return 'text-gray-600 bg-gray-50';
    }
  };

  const getCategoryIcon = (category: string) => {
    switch (category) {
      case 'trading-income': return <TrendingUp className="w-4 h-4" />;
      case 'expense-coverage': return <Shield className="w-4 h-4" />;
      case 'savings': return <PiggyBank className="w-4 h-4" />;
      case 'investment-goal': return <Target className="w-4 h-4" />;
      default: return <DollarSign className="w-4 h-4" />;
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Financial Trading Ecosystem</h1>
            <p className="text-gray-600 mt-1">
              Comprehensive financial management for trading operations, crypto investments, stock portfolios, and income targets
            </p>
          </div>
          <div className="flex items-center space-x-2">
            <Calculator className="w-6 h-6 text-blue-600" />
            <span className="text-sm font-medium text-gray-600">
              {dashboard.activeTargetsCount} Active Targets
            </span>
          </div>
        </div>
      </div>

      {/* Navigation Tabs */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200">
        <div className="border-b border-gray-200">
          <nav className="-mb-px flex space-x-8 px-6">
            {[
              { id: 'targets', name: 'Financial Targets', icon: Target },
              { id: 'crypto', name: 'Crypto & Bitcoin', icon: Bitcoin },
              { id: 'futures', name: 'Futures Scaling', icon: BarChart3 },
              { id: 'stocks', name: 'Stock Portfolios', icon: Building2 },
              { id: 'integration', name: 'API & Alerts', icon: Link }
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center space-x-2 py-4 px-1 border-b-2 font-medium text-sm ${
                  activeTab === tab.id
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                <tab.icon className="w-4 h-4" />
                <span>{tab.name}</span>
              </button>
            ))}
          </nav>
        </div>

        {/* Tab Content */}
        <div className="p-6">
          {activeTab === 'targets' && (
            <div className="space-y-6">
              {/* Dashboard Cards */}
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-blue-600 text-sm font-medium">Monthly Income Target</p>
                      <p className="text-2xl font-bold text-blue-900">
                        {formatCurrency(dashboard.projectedMonthlyIncome)}
                      </p>
                    </div>
                    <TrendingUp className="w-8 h-8 text-blue-600" />
                  </div>
                </div>

                <div className="bg-green-50 border border-green-200 rounded-lg p-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-green-600 text-sm font-medium">Monthly Expenses</p>
                      <p className="text-2xl font-bold text-green-900">
                        {formatCurrency(dashboard.totalMonthlyExpenses)}
                      </p>
                    </div>
                    <Calculator className="w-8 h-8 text-green-600" />
                  </div>
                </div>

                <div className={`border rounded-lg p-4 ${
                  dashboard.surplusDeficit >= 0 
                    ? 'bg-emerald-50 border-emerald-200' 
                    : 'bg-red-50 border-red-200'
                }`}>
                  <div className="flex items-center justify-between">
                    <div>
                      <p className={`text-sm font-medium ${
                        dashboard.surplusDeficit >= 0 ? 'text-emerald-600' : 'text-red-600'
                      }`}>
                        Monthly Surplus/Deficit
                      </p>
                      <p className={`text-2xl font-bold ${
                        dashboard.surplusDeficit >= 0 ? 'text-emerald-900' : 'text-red-900'
                      }`}>
                        {formatCurrency(dashboard.surplusDeficit)}
                      </p>
                    </div>
                    {dashboard.surplusDeficit >= 0 ? (
                      <PiggyBank className="w-8 h-8 text-emerald-600" />
                    ) : (
                      <AlertTriangle className="w-8 h-8 text-red-600" />
                    )}
                  </div>
                </div>

                <div className="bg-purple-50 border border-purple-200 rounded-lg p-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-purple-600 text-sm font-medium">Expense Coverage</p>
                      <p className="text-2xl font-bold text-purple-900">
                        {dashboard.expenseCoverage.toFixed(1)}%
                      </p>
                    </div>
                    <Shield className="w-8 h-8 text-purple-600" />
                  </div>
                </div>
              </div>

              {/* Add New Target Button */}
              <div className="flex justify-between items-center">
                <h2 className="text-xl font-semibold text-gray-900">Financial Targets</h2>
                <button
                  onClick={() => setShowNewTargetForm(true)}
                  className="flex items-center space-x-2 bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors"
                >
                  <Plus className="w-4 h-4" />
                  <span>Add Target</span>
                </button>
              </div>

              {/* New Target Form */}
              {showNewTargetForm && (
                <div className="bg-gray-50 border border-gray-200 rounded-lg p-6">
                  <h3 className="text-lg font-medium text-gray-900 mb-4">Add New Financial Target</h3>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Target Name</label>
                      <input
                        type="text"
                        value={newTarget.name || ''}
                        onChange={(e) => setNewTarget({ ...newTarget, name: e.target.value })}
                        className="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                        placeholder="e.g., Daily Trading Profit"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Target Amount (CAD)</label>
                      <input
                        type="number"
                        value={newTarget.targetAmount || 0}
                        onChange={(e) => setNewTarget({ ...newTarget, targetAmount: parseFloat(e.target.value) || 0 })}
                        className="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                        placeholder="500"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Period</label>
                      <select
                        value={newTarget.period || 'daily'}
                        onChange={(e) => setNewTarget({ ...newTarget, period: e.target.value as any })}
                        className="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                      >
                        <option value="daily">Daily</option>
                        <option value="weekly">Weekly</option>
                        <option value="monthly">Monthly</option>
                        <option value="yearly">Yearly</option>
                      </select>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Category</label>
                      <select
                        value={newTarget.category || 'trading-income'}
                        onChange={(e) => setNewTarget({ ...newTarget, category: e.target.value as any })}
                        className="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                      >
                        <option value="trading-income">Trading Income</option>
                        <option value="expense-coverage">Expense Coverage</option>
                        <option value="savings">Savings</option>
                        <option value="investment-goal">Investment Goal</option>
                      </select>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Priority</label>
                      <select
                        value={newTarget.priority || 'medium'}
                        onChange={(e) => setNewTarget({ ...newTarget, priority: e.target.value as any })}
                        className="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                      >
                        <option value="critical">Critical</option>
                        <option value="high">High</option>
                        <option value="medium">Medium</option>
                        <option value="low">Low</option>
                      </select>
                    </div>
                    <div className="md:col-span-2">
                      <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
                      <textarea
                        value={newTarget.description || ''}
                        onChange={(e) => setNewTarget({ ...newTarget, description: e.target.value })}
                        className="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                        rows={2}
                        placeholder="Brief description of this financial target"
                      />
                    </div>
                  </div>
                  <div className="flex justify-end space-x-2 mt-4">
                    <button
                      onClick={() => setShowNewTargetForm(false)}
                      className="px-4 py-2 text-gray-600 border border-gray-300 rounded-md hover:bg-gray-50 transition-colors"
                    >
                      Cancel
                    </button>
                    <button
                      onClick={addTarget}
                      className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors"
                    >
                      Add Target
                    </button>
                  </div>
                </div>
              )}

              {/* Targets List */}
              <div className="space-y-4">
                {targets.map((target) => (
                  <div key={target.id} className="bg-white border border-gray-200 rounded-lg p-4">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-3">
                        {getCategoryIcon(target.category)}
                        <div>
                          <h3 className="font-medium text-gray-900">{target.name}</h3>
                          <p className="text-sm text-gray-600">{target.description}</p>
                        </div>
                      </div>
                      <div className="flex items-center space-x-4">
                        <span className={`px-2 py-1 rounded-full text-xs font-medium ${getPriorityColor(target.priority)}`}>
                          {target.priority}
                        </span>
                        <div className="text-right">
                          <p className="text-lg font-semibold text-gray-900">
                            {formatCurrency(target.targetAmount)}
                          </p>
                          <p className="text-sm text-gray-600 capitalize">
                            per {target.period}
                          </p>
                        </div>
                        <div className="flex items-center space-x-2">
                          <button
                            onClick={() => toggleTargetActive(target.id)}
                            className={`px-3 py-1 rounded-md text-xs font-medium transition-colors ${
                              target.isActive
                                ? 'bg-green-100 text-green-800 hover:bg-green-200'
                                : 'bg-gray-100 text-gray-800 hover:bg-gray-200'
                            }`}
                          >
                            {target.isActive ? 'Active' : 'Inactive'}
                          </button>
                          <button
                            onClick={() => setEditingTarget(target)}
                            className="p-1 text-gray-400 hover:text-blue-600 transition-colors"
                          >
                            <Edit3 className="w-4 h-4" />
                          </button>
                          <button
                            onClick={() => deleteTarget(target.id)}
                            className="p-1 text-gray-400 hover:text-red-600 transition-colors"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {activeTab === 'crypto' && (
            <CryptoTracking
              cryptoPortfolio={cryptoPortfolio}
              onUpdateCryptoPortfolio={setCryptoPortfolio}
            />
          )}

          {activeTab === 'futures' && (
            <FuturesScaling
              futuresAccounts={futuresAccounts}
              onUpdateFuturesAccounts={setFuturesAccounts}
            />
          )}

          {activeTab === 'stocks' && (
            <StockPortfolioTracking
              stockPortfolios={stockPortfolios}
              onUpdateStockPortfolios={setStockPortfolios}
            />
          )}

          {activeTab === 'integration' && (
            <IntegrationAndAlerts
              apiConnections={apiConnections}
              alertConfigs={alertConfigs}
              onUpdateApiConnections={setApiConnections}
              onUpdateAlertConfigs={setAlertConfigs}
            />
          )}
        </div>
      </div>
    </div>
  );
}
