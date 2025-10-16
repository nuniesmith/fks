import { TrendingUp, TrendingDown, Plus, Edit3, Trash2, BarChart3, DollarSign, Calendar, AlertCircle, Building, PieChart } from 'lucide-react';
import React, { useState } from 'react';

import type { StockPortfolio, StockHolding, AccountType } from '../../types';

interface StockPortfolioProps {
  stockPortfolios: StockPortfolio[];
  onUpdateStockPortfolios: (portfolios: StockPortfolio[]) => void;
}

export default function StockPortfolioTracking({ stockPortfolios, onUpdateStockPortfolios }: StockPortfolioProps) {
  const [activePortfolioTab, setActivePortfolioTab] = useState('overview');
  const [showNewPortfolioForm, setShowNewPortfolioForm] = useState(false);
  const [showNewHoldingForm, setShowNewHoldingForm] = useState(false);
  const [selectedPortfolioId, setSelectedPortfolioId] = useState<string>('');
  const [editingPortfolio, setEditingPortfolio] = useState<StockPortfolio | null>(null);
  const [editingHolding, setEditingHolding] = useState<StockHolding | null>(null);

  const [newPortfolio, setNewPortfolio] = useState<Partial<StockPortfolio>>({
    name: '',
    accountType: 'tfsa',
    broker: 'interactive-brokers',
    currency: 'CAD',
    rebalanceStrategy: {
      frequency: 'quarterly',
      threshold: 5,
      method: 'threshold'
    },
    allocationTargets: {
      'Technology': 30,
      'Healthcare': 20,
      'Financial': 15,
      'Consumer': 15,
      'Industrial': 10,
      'Energy': 5,
      'Utilities': 5
    }
  });

  const [newHolding, setNewHolding] = useState<Partial<StockHolding>>({
    symbol: '',
    name: '',
    shares: 0,
    averageCost: 0,
    currentPrice: 0,
    sector: 'Technology',
    purchaseDate: new Date().toISOString().split('T')[0]
  });

  const brokerOptions = [
    { value: 'interactive-brokers', label: 'Interactive Brokers' },
    { value: 'questrade', label: 'Questrade' },
    { value: 'td-direct', label: 'TD Direct Investing' },
    { value: 'rbc-direct', label: 'RBC Direct Investing' },
    { value: 'other', label: 'Other' }
  ];

  const accountTypeOptions: { value: AccountType; label: string }[] = [
    { value: 'tfsa', label: 'TFSA - Tax-Free Savings Account' },
    { value: 'rrsp', label: 'RRSP - Registered Retirement Savings Plan' },
    { value: 'personal-margin', label: 'Personal Margin Account' },
    { value: 'personal-cash', label: 'Personal Cash Account' },
    { value: 'corporate-margin', label: 'Corporate Margin Account' },
    { value: 'corporate-cash', label: 'Corporate Cash Account' }
  ];

  const sectorOptions = [
    'Technology', 'Healthcare', 'Financial', 'Consumer', 'Industrial', 
    'Energy', 'Utilities', 'Materials', 'Real Estate', 'Communication'
  ];

  const formatCurrency = (amount: number, currency: 'CAD' | 'USD' = 'CAD') => {
    return new Intl.NumberFormat(currency === 'CAD' ? 'en-CA' : 'en-US', {
      style: 'currency',
      currency: currency
    }).format(amount);
  };

  const formatPercent = (value: number) => {
    return `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`;
  };

  const addPortfolio = () => {
    if (newPortfolio.name && newPortfolio.accountType) {
      const portfolio: StockPortfolio = {
        id: Date.now().toString(),
        name: newPortfolio.name,
        totalValue: 0,
        totalCost: 0,
        unrealizedGainLoss: 0,
        unrealizedGainLossPercent: 0,
        annualDividends: 0,
        dividendYield: 0,
        holdings: [],
        accountType: newPortfolio.accountType,
        broker: newPortfolio.broker || 'interactive-brokers',
        currency: newPortfolio.currency || 'CAD',
        lastRebalanced: new Date().toISOString(),
        rebalanceStrategy: newPortfolio.rebalanceStrategy || {
          frequency: 'quarterly',
          threshold: 5,
          method: 'threshold'
        },
        allocationTargets: newPortfolio.allocationTargets || {}
      };

      onUpdateStockPortfolios([...stockPortfolios, portfolio]);
      setNewPortfolio({
        name: '',
        accountType: 'tfsa',
        broker: 'interactive-brokers',
        currency: 'CAD'
      });
      setShowNewPortfolioForm(false);
    }
  };

  const addHolding = () => {
    if (newHolding.symbol && newHolding.shares && newHolding.averageCost && selectedPortfolioId) {
      const portfolio = stockPortfolios.find(p => p.id === selectedPortfolioId);
      if (!portfolio) return;

      const holding: StockHolding = {
        id: Date.now().toString(),
        symbol: newHolding.symbol!.toUpperCase(),
        name: newHolding.name || newHolding.symbol!.toUpperCase(),
        shares: newHolding.shares!,
        averageCost: newHolding.averageCost!,
        currentPrice: newHolding.currentPrice || newHolding.averageCost!,
        marketValue: newHolding.shares! * (newHolding.currentPrice || newHolding.averageCost!),
        unrealizedGainLoss: (newHolding.shares! * (newHolding.currentPrice || newHolding.averageCost!)) - (newHolding.shares! * newHolding.averageCost!),
        unrealizedGainLossPercent: newHolding.currentPrice && newHolding.averageCost 
          ? ((newHolding.currentPrice - newHolding.averageCost!) / newHolding.averageCost!) * 100 
          : 0,
        dividendYield: 0,
        annualDividends: 0,
        sector: newHolding.sector || 'Technology',
        accountId: selectedPortfolioId,
        accountType: portfolio.accountType,
        purchaseDate: newHolding.purchaseDate || new Date().toISOString().split('T')[0],
        lastUpdated: new Date().toISOString()
      };

      const updatedPortfolio = {
        ...portfolio,
        holdings: [...portfolio.holdings, holding]
      };

      // Recalculate portfolio totals
      const totalValue = updatedPortfolio.holdings.reduce((sum, h) => sum + h.marketValue, 0);
      const totalCost = updatedPortfolio.holdings.reduce((sum, h) => sum + (h.shares * h.averageCost), 0);
      const totalDividends = updatedPortfolio.holdings.reduce((sum, h) => sum + h.annualDividends, 0);

      updatedPortfolio.totalValue = totalValue;
      updatedPortfolio.totalCost = totalCost;
      updatedPortfolio.unrealizedGainLoss = totalValue - totalCost;
      updatedPortfolio.unrealizedGainLossPercent = totalCost > 0 ? ((totalValue - totalCost) / totalCost) * 100 : 0;
      updatedPortfolio.annualDividends = totalDividends;
      updatedPortfolio.dividendYield = totalValue > 0 ? (totalDividends / totalValue) * 100 : 0;

      const updatedPortfolios = stockPortfolios.map(p => 
        p.id === selectedPortfolioId ? updatedPortfolio : p
      );

      onUpdateStockPortfolios(updatedPortfolios);
      setNewHolding({
        symbol: '',
        name: '',
        shares: 0,
        averageCost: 0,
        currentPrice: 0,
        sector: 'Technology',
        purchaseDate: new Date().toISOString().split('T')[0]
      });
      setShowNewHoldingForm(false);
    }
  };

  const deletePortfolio = (portfolioId: string) => {
    onUpdateStockPortfolios(stockPortfolios.filter(p => p.id !== portfolioId));
  };

  const deleteHolding = (portfolioId: string, holdingId: string) => {
    const updatedPortfolios = stockPortfolios.map(portfolio => {
      if (portfolio.id === portfolioId) {
        const updatedHoldings = portfolio.holdings.filter(h => h.id !== holdingId);
        const totalValue = updatedHoldings.reduce((sum, h) => sum + h.marketValue, 0);
        const totalCost = updatedHoldings.reduce((sum, h) => sum + (h.shares * h.averageCost), 0);
        
        return {
          ...portfolio,
          holdings: updatedHoldings,
          totalValue,
          totalCost,
          unrealizedGainLoss: totalValue - totalCost,
          unrealizedGainLossPercent: totalCost > 0 ? ((totalValue - totalCost) / totalCost) * 100 : 0
        };
      }
      return portfolio;
    });

    onUpdateStockPortfolios(updatedPortfolios);
  };

  const getSectorAllocation = (portfolio: StockPortfolio) => {
    const sectorValues: Record<string, number> = {};
    
    portfolio.holdings.forEach(holding => {
      if (!sectorValues[holding.sector]) {
        sectorValues[holding.sector] = 0;
      }
      sectorValues[holding.sector] += holding.marketValue;
    });

    return Object.entries(sectorValues).map(([sector, value]) => ({
      sector,
      value,
      percentage: portfolio.totalValue > 0 ? (value / portfolio.totalValue) * 100 : 0,
      target: portfolio.allocationTargets[sector] || 0
    }));
  };

  const getTotalPortfolioValue = () => {
    return stockPortfolios.reduce((sum, portfolio) => sum + portfolio.totalValue, 0);
  };

  const getTotalUnrealizedGains = () => {
    return stockPortfolios.reduce((sum, portfolio) => sum + portfolio.unrealizedGainLoss, 0);
  };

  const getTotalAnnualDividends = () => {
    return stockPortfolios.reduce((sum, portfolio) => sum + portfolio.annualDividends, 0);
  };

  return (
    <div className="space-y-6">
      {/* Header with Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-blue-600 text-sm font-medium">Total Portfolio Value</p>
              <p className="text-2xl font-bold text-blue-900">
                {formatCurrency(getTotalPortfolioValue())}
              </p>
            </div>
            <BarChart3 className="w-8 h-8 text-blue-600" />
          </div>
        </div>

        <div className={`border rounded-lg p-4 ${
          getTotalUnrealizedGains() >= 0 
            ? 'bg-green-50 border-green-200' 
            : 'bg-red-50 border-red-200'
        }`}>
          <div className="flex items-center justify-between">
            <div>
              <p className={`text-sm font-medium ${
                getTotalUnrealizedGains() >= 0 ? 'text-green-600' : 'text-red-600'
              }`}>
                Unrealized Gains/Loss
              </p>
              <p className={`text-2xl font-bold ${
                getTotalUnrealizedGains() >= 0 ? 'text-green-900' : 'text-red-900'
              }`}>
                {formatCurrency(getTotalUnrealizedGains())}
              </p>
            </div>
            {getTotalUnrealizedGains() >= 0 ? (
              <TrendingUp className="w-8 h-8 text-green-600" />
            ) : (
              <TrendingDown className="w-8 h-8 text-red-600" />
            )}
          </div>
        </div>

        <div className="bg-purple-50 border border-purple-200 rounded-lg p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-purple-600 text-sm font-medium">Annual Dividends</p>
              <p className="text-2xl font-bold text-purple-900">
                {formatCurrency(getTotalAnnualDividends())}
              </p>
            </div>
            <DollarSign className="w-8 h-8 text-purple-600" />
          </div>
        </div>

        <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-gray-600 text-sm font-medium">Portfolios</p>
              <p className="text-2xl font-bold text-gray-900">
                {stockPortfolios.length}
              </p>
            </div>
            <Building className="w-8 h-8 text-gray-600" />
          </div>
        </div>
      </div>

      {/* Portfolio Tabs */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200">
        <div className="border-b border-gray-200">
          <nav className="-mb-px flex space-x-8 px-6">
            {[
              { id: 'overview', name: 'Portfolio Overview', icon: BarChart3 },
              { id: 'holdings', name: 'Holdings Management', icon: Building },
              { id: 'allocation', name: 'Asset Allocation', icon: PieChart },
              { id: 'rebalancing', name: 'Rebalancing', icon: Calendar }
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActivePortfolioTab(tab.id)}
                className={`flex items-center space-x-2 py-4 px-1 border-b-2 font-medium text-sm ${
                  activePortfolioTab === tab.id
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

        <div className="p-6">
          {activePortfolioTab === 'overview' && (
            <div className="space-y-6">
              <div className="flex justify-between items-center">
                <h3 className="text-lg font-semibold text-gray-900">Stock Portfolios</h3>
                <button
                  onClick={() => setShowNewPortfolioForm(true)}
                  className="flex items-center space-x-2 bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors"
                >
                  <Plus className="w-4 h-4" />
                  <span>Add Portfolio</span>
                </button>
              </div>

              {/* New Portfolio Form */}
              {showNewPortfolioForm && (
                <div className="bg-gray-50 border border-gray-200 rounded-lg p-6">
                  <h4 className="text-lg font-medium text-gray-900 mb-4">Add New Stock Portfolio</h4>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Portfolio Name</label>
                      <input
                        type="text"
                        value={newPortfolio.name || ''}
                        onChange={(e) => setNewPortfolio({ ...newPortfolio, name: e.target.value })}
                        className="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                        placeholder="e.g., Long-term Growth Portfolio"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Account Type</label>
                      <select
                        value={newPortfolio.accountType || 'tfsa'}
                        onChange={(e) => setNewPortfolio({ ...newPortfolio, accountType: e.target.value as AccountType })}
                        className="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                      >
                        {accountTypeOptions.map(option => (
                          <option key={option.value} value={option.value}>{option.label}</option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Broker</label>
                      <select
                        value={newPortfolio.broker || 'interactive-brokers'}
                        onChange={(e) => setNewPortfolio({ ...newPortfolio, broker: e.target.value as any })}
                        className="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                      >
                        {brokerOptions.map(option => (
                          <option key={option.value} value={option.value}>{option.label}</option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Currency</label>
                      <select
                        value={newPortfolio.currency || 'CAD'}
                        onChange={(e) => setNewPortfolio({ ...newPortfolio, currency: e.target.value as 'CAD' | 'USD' })}
                        className="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                      >
                        <option value="CAD">CAD - Canadian Dollar</option>
                        <option value="USD">USD - US Dollar</option>
                      </select>
                    </div>
                  </div>
                  <div className="flex justify-end space-x-2 mt-4">
                    <button
                      onClick={() => setShowNewPortfolioForm(false)}
                      className="px-4 py-2 text-gray-600 border border-gray-300 rounded-md hover:bg-gray-50 transition-colors"
                    >
                      Cancel
                    </button>
                    <button
                      onClick={addPortfolio}
                      className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors"
                    >
                      Add Portfolio
                    </button>
                  </div>
                </div>
              )}

              {/* Portfolio List */}
              <div className="space-y-4">
                {stockPortfolios.map((portfolio) => (
                  <div key={portfolio.id} className="bg-white border border-gray-200 rounded-lg p-6">
                    <div className="flex items-center justify-between mb-4">
                      <div>
                        <h4 className="text-lg font-semibold text-gray-900">{portfolio.name}</h4>
                        <p className="text-sm text-gray-600">
                          {portfolio.broker} • {portfolio.accountType.toUpperCase()} • {portfolio.currency}
                        </p>
                      </div>
                      <div className="flex items-center space-x-2">
                        <button
                          onClick={() => setEditingPortfolio(portfolio)}
                          className="p-2 text-gray-400 hover:text-blue-600 transition-colors"
                        >
                          <Edit3 className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => deletePortfolio(portfolio.id)}
                          className="p-2 text-gray-400 hover:text-red-600 transition-colors"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                      <div>
                        <p className="text-sm text-gray-600">Total Value</p>
                        <p className="text-xl font-semibold text-gray-900">
                          {formatCurrency(portfolio.totalValue, portfolio.currency)}
                        </p>
                      </div>
                      <div>
                        <p className="text-sm text-gray-600">Unrealized P&L</p>
                        <p className={`text-xl font-semibold ${
                          portfolio.unrealizedGainLoss >= 0 ? 'text-green-600' : 'text-red-600'
                        }`}>
                          {formatCurrency(portfolio.unrealizedGainLoss, portfolio.currency)}
                          <span className="text-sm ml-1">
                            ({formatPercent(portfolio.unrealizedGainLossPercent)})
                          </span>
                        </p>
                      </div>
                      <div>
                        <p className="text-sm text-gray-600">Annual Dividends</p>
                        <p className="text-xl font-semibold text-purple-600">
                          {formatCurrency(portfolio.annualDividends, portfolio.currency)}
                        </p>
                      </div>
                      <div>
                        <p className="text-sm text-gray-600">Holdings</p>
                        <p className="text-xl font-semibold text-gray-900">
                          {portfolio.holdings.length}
                        </p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {activePortfolioTab === 'holdings' && (
            <div className="space-y-6">
              <div className="flex justify-between items-center">
                <h3 className="text-lg font-semibold text-gray-900">Holdings Management</h3>
                <div className="flex items-center space-x-2">
                  <select
                    value={selectedPortfolioId}
                    onChange={(e) => setSelectedPortfolioId(e.target.value)}
                    className="border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="">Select Portfolio</option>
                    {stockPortfolios.map(portfolio => (
                      <option key={portfolio.id} value={portfolio.id}>{portfolio.name}</option>
                    ))}
                  </select>
                  <button
                    onClick={() => setShowNewHoldingForm(true)}
                    disabled={!selectedPortfolioId}
                    className="flex items-center space-x-2 bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    <Plus className="w-4 h-4" />
                    <span>Add Holding</span>
                  </button>
                </div>
              </div>

              {/* New Holding Form */}
              {showNewHoldingForm && (
                <div className="bg-gray-50 border border-gray-200 rounded-lg p-6">
                  <h4 className="text-lg font-medium text-gray-900 mb-4">Add New Stock Holding</h4>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Stock Symbol</label>
                      <input
                        type="text"
                        value={newHolding.symbol || ''}
                        onChange={(e) => setNewHolding({ ...newHolding, symbol: e.target.value.toUpperCase() })}
                        className="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                        placeholder="e.g., AAPL, TSLA"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Company Name</label>
                      <input
                        type="text"
                        value={newHolding.name || ''}
                        onChange={(e) => setNewHolding({ ...newHolding, name: e.target.value })}
                        className="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                        placeholder="e.g., Apple Inc."
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Shares</label>
                      <input
                        type="number"
                        value={newHolding.shares || 0}
                        onChange={(e) => setNewHolding({ ...newHolding, shares: parseFloat(e.target.value) || 0 })}
                        className="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                        step="0.01"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Average Cost</label>
                      <input
                        type="number"
                        value={newHolding.averageCost || 0}
                        onChange={(e) => setNewHolding({ ...newHolding, averageCost: parseFloat(e.target.value) || 0 })}
                        className="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                        step="0.01"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Current Price</label>
                      <input
                        type="number"
                        value={newHolding.currentPrice || 0}
                        onChange={(e) => setNewHolding({ ...newHolding, currentPrice: parseFloat(e.target.value) || 0 })}
                        className="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                        step="0.01"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Sector</label>
                      <select
                        value={newHolding.sector || 'Technology'}
                        onChange={(e) => setNewHolding({ ...newHolding, sector: e.target.value })}
                        className="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                      >
                        {sectorOptions.map(sector => (
                          <option key={sector} value={sector}>{sector}</option>
                        ))}
                      </select>
                    </div>
                  </div>
                  <div className="flex justify-end space-x-2 mt-4">
                    <button
                      onClick={() => setShowNewHoldingForm(false)}
                      className="px-4 py-2 text-gray-600 border border-gray-300 rounded-md hover:bg-gray-50 transition-colors"
                    >
                      Cancel
                    </button>
                    <button
                      onClick={addHolding}
                      className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors"
                    >
                      Add Holding
                    </button>
                  </div>
                </div>
              )}

              {/* Holdings Display */}
              {selectedPortfolioId && (
                <div className="space-y-4">
                  {stockPortfolios
                    .find(p => p.id === selectedPortfolioId)
                    ?.holdings.map((holding) => (
                      <div key={holding.id} className="bg-white border border-gray-200 rounded-lg p-4">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center space-x-4">
                            <div>
                              <h4 className="font-semibold text-gray-900">{holding.symbol}</h4>
                              <p className="text-sm text-gray-600">{holding.name}</p>
                              <p className="text-xs text-gray-500">{holding.sector}</p>
                            </div>
                            <div className="text-right">
                              <p className="text-sm text-gray-600">Market Value</p>
                              <p className="font-semibold text-gray-900">
                                {formatCurrency(holding.marketValue)}
                              </p>
                            </div>
                            <div className="text-right">
                              <p className="text-sm text-gray-600">Unrealized P&L</p>
                              <p className={`font-semibold ${
                                holding.unrealizedGainLoss >= 0 ? 'text-green-600' : 'text-red-600'
                              }`}>
                                {formatCurrency(holding.unrealizedGainLoss)}
                                <span className="text-xs ml-1">
                                  ({formatPercent(holding.unrealizedGainLossPercent)})
                                </span>
                              </p>
                            </div>
                            <div className="text-right">
                              <p className="text-sm text-gray-600">Shares</p>
                              <p className="font-semibold text-gray-900">{holding.shares}</p>
                            </div>
                          </div>
                          <div className="flex items-center space-x-2">
                            <button
                              onClick={() => setEditingHolding(holding)}
                              className="p-2 text-gray-400 hover:text-blue-600 transition-colors"
                            >
                              <Edit3 className="w-4 h-4" />
                            </button>
                            <button
                              onClick={() => deleteHolding(selectedPortfolioId, holding.id)}
                              className="p-2 text-gray-400 hover:text-red-600 transition-colors"
                            >
                              <Trash2 className="w-4 h-4" />
                            </button>
                          </div>
                        </div>
                      </div>
                    ))}
                </div>
              )}
            </div>
          )}

          {activePortfolioTab === 'allocation' && (
            <div className="space-y-6">
              <h3 className="text-lg font-semibold text-gray-900">Asset Allocation Analysis</h3>
              
              {stockPortfolios.map((portfolio) => {
                const sectorAllocations = getSectorAllocation(portfolio);
                
                return (
                  <div key={portfolio.id} className="bg-white border border-gray-200 rounded-lg p-6">
                    <h4 className="text-lg font-semibold text-gray-900 mb-4">{portfolio.name}</h4>
                    
                    <div className="space-y-3">
                      {sectorAllocations.map((allocation) => (
                        <div key={allocation.sector} className="flex items-center justify-between">
                          <div className="flex-1">
                            <div className="flex items-center justify-between mb-1">
                              <span className="text-sm font-medium text-gray-700">{allocation.sector}</span>
                              <span className="text-sm text-gray-600">
                                {allocation.percentage.toFixed(1)}% / {allocation.target.toFixed(1)}% target
                              </span>
                            </div>
                            <div className="w-full bg-gray-200 rounded-full h-2">
                              <div
                                className={`h-2 rounded-full ${
                                  Math.abs(allocation.percentage - allocation.target) <= 2
                                    ? 'bg-green-500'
                                    : Math.abs(allocation.percentage - allocation.target) <= 5
                                    ? 'bg-yellow-500'
                                    : 'bg-red-500'
                                }`}
                                style={{ width: `${Math.min(allocation.percentage, 100)}%` }}
                              />
                            </div>
                          </div>
                          <div className="ml-4 text-right">
                            <p className="text-sm font-medium text-gray-900">
                              {formatCurrency(allocation.value, portfolio.currency)}
                            </p>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {activePortfolioTab === 'rebalancing' && (
            <div className="space-y-6">
              <h3 className="text-lg font-semibold text-gray-900">Portfolio Rebalancing</h3>
              
              {stockPortfolios.map((portfolio) => {
                const sectorAllocations = getSectorAllocation(portfolio);
                const needsRebalancing = sectorAllocations.some(
                  allocation => Math.abs(allocation.percentage - allocation.target) > portfolio.rebalanceStrategy.threshold
                );
                
                return (
                  <div key={portfolio.id} className="bg-white border border-gray-200 rounded-lg p-6">
                    <div className="flex items-center justify-between mb-4">
                      <div>
                        <h4 className="text-lg font-semibold text-gray-900">{portfolio.name}</h4>
                        <p className="text-sm text-gray-600">
                          Last rebalanced: {new Date(portfolio.lastRebalanced).toLocaleDateString()}
                        </p>
                      </div>
                      <div className="flex items-center space-x-2">
                        {needsRebalancing && (
                          <div className="flex items-center space-x-1 text-orange-600">
                            <AlertCircle className="w-4 h-4" />
                            <span className="text-sm font-medium">Rebalancing Needed</span>
                          </div>
                        )}
                      </div>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
                      <div>
                        <p className="text-sm text-gray-600">Rebalance Strategy</p>
                        <p className="font-medium text-gray-900 capitalize">
                          {portfolio.rebalanceStrategy.method} • {portfolio.rebalanceStrategy.frequency}
                        </p>
                      </div>
                      <div>
                        <p className="text-sm text-gray-600">Threshold</p>
                        <p className="font-medium text-gray-900">
                          {portfolio.rebalanceStrategy.threshold}%
                        </p>
                      </div>
                      <div>
                        <p className="text-sm text-gray-600">Status</p>
                        <p className={`font-medium ${
                          needsRebalancing ? 'text-orange-600' : 'text-green-600'
                        }`}>
                          {needsRebalancing ? 'Needs Rebalancing' : 'Balanced'}
                        </p>
                      </div>
                    </div>

                    {needsRebalancing && (
                      <div className="bg-orange-50 border border-orange-200 rounded-lg p-4">
                        <h5 className="font-medium text-orange-900 mb-2">Rebalancing Recommendations</h5>
                        <div className="space-y-2">
                          {sectorAllocations
                            .filter(allocation => Math.abs(allocation.percentage - allocation.target) > portfolio.rebalanceStrategy.threshold)
                            .map((allocation) => {
                              const deviation = allocation.percentage - allocation.target;
                              const action = deviation > 0 ? 'Reduce' : 'Increase';
                              const amount = Math.abs(deviation / 100 * portfolio.totalValue);
                              
                              return (
                                <div key={allocation.sector} className="flex items-center justify-between text-sm">
                                  <span className="text-orange-700">
                                    {action} {allocation.sector} by {Math.abs(deviation).toFixed(1)}%
                                  </span>
                                  <span className="font-medium text-orange-900">
                                    {formatCurrency(amount, portfolio.currency)}
                                  </span>
                                </div>
                              );
                            })}
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
