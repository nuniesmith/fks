import { 
  Plus, 
  Building2, 
  TrendingUp, 
  DollarSign, 
  AlertCircle, 
  CheckCircle,
  Target
} from 'lucide-react';
import React, { useState } from 'react';

import { useGamification } from '../../context/GamificationContext';

import type { PropFirmAccount } from '../../types/gamification';

const PropFirmManager: React.FC = () => {
  const { userProgress, awardExperience, addPropFirmAccount } = useGamification();
  const [isAddingAccount, setIsAddingAccount] = useState(false);
  const [newAccount, setNewAccount] = useState({
    firmName: '',
    accountSize: 10000,
    profitTarget: 8,
    maxDrawdown: 5,
    dailyLossLimit: 3
  });

  const propFirms = [
    { name: 'FTMO', maxAccounts: 10, accountSizes: [10000, 25000, 50000, 100000, 200000] },
    { name: 'The5ers', maxAccounts: 10, accountSizes: [5000, 20000, 50000, 100000] },
    { name: 'MyForexFunds', maxAccounts: 10, accountSizes: [10000, 25000, 50000, 100000, 200000] }
  ];

  const handleAddAccount = () => {
    const account: PropFirmAccount = {
      id: `prop_${Date.now()}`,
      firmName: newAccount.firmName,
      accountType: 'evaluation',
      balance: newAccount.accountSize,
      accountSize: newAccount.accountSize,
      currentBalance: newAccount.accountSize,
      maxDrawdown: newAccount.maxDrawdown,
      profitTarget: newAccount.profitTarget,
      dailyLossLimit: newAccount.dailyLossLimit,
      status: 'pending',
      phase: 'evaluation',
      startDate: new Date(),
      createdAt: new Date(),
      grossProfit: 0,
      netProfit: 0,
      payouts: [],
      isEnabled: true
    };

    addPropFirmAccount(account);
    setIsAddingAccount(false);
    setNewAccount({
      firmName: '',
      accountSize: 10000,
      profitTarget: 8,
      maxDrawdown: 5,
      dailyLossLimit: 3
    });
  };

  const getStatusColor = (status: PropFirmAccount['status']) => {
    switch (status) {
      case 'active': return 'text-blue-400 bg-blue-900/20';
      case 'passed': return 'text-green-400 bg-green-900/20';
      case 'funded': return 'text-purple-400 bg-purple-900/20';
      case 'failed': return 'text-red-400 bg-red-900/20';
      default: return 'text-yellow-400 bg-yellow-900/20';
    }
  };

  const getPhaseColor = (phase: PropFirmAccount['phase']) => {
    switch (phase) {
      case 'evaluation': return 'text-orange-400';
      case 'verification': return 'text-blue-400';
      case 'funded': return 'text-green-400';
      default: return 'text-gray-400';
    }
  };

  if (!userProgress) {
    return <div className="p-6 text-white">Loading...</div>;
  }

  const { propFirmAccounts } = userProgress;
  const currentPhase = userProgress.phases.find(p => p.id === 'phase_1');
  const propFirmObjective = currentPhase?.objectives.find(obj => obj.category === 'prop_firm');

  return (
    <div className="p-6 bg-gray-900 text-white space-y-6">
      {/* Header with Phase Progress */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Prop Firm Management</h1>
          <p className="text-gray-400">Scale to 30 accounts across 3 firms</p>
        </div>
        <div className="text-right">
          <div className="text-sm text-gray-400">Phase 1 Progress</div>
          <div className="text-2xl font-bold text-blue-400">
            {propFirmObjective?.current || 0} / {propFirmObjective?.target || 30}
          </div>
        </div>
      </div>

      {/* Overview Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-2xl font-bold text-blue-400">{propFirmAccounts.length}</div>
              <div className="text-sm text-gray-400">Total Accounts</div>
            </div>
            <Building2 className="w-8 h-8 text-blue-400" />
          </div>
        </div>

        <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-2xl font-bold text-green-400">
                {propFirmAccounts.filter(acc => acc.status === 'funded').length}
              </div>
              <div className="text-sm text-gray-400">Funded Accounts</div>
            </div>
            <CheckCircle className="w-8 h-8 text-green-400" />
          </div>
        </div>

        <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-2xl font-bold text-purple-400">
                ${propFirmAccounts.reduce((sum, acc) => sum + acc.netProfit, 0).toLocaleString()}
              </div>
              <div className="text-sm text-gray-400">Net Profit (80%)</div>
            </div>
            <DollarSign className="w-8 h-8 text-purple-400" />
          </div>
        </div>

        <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-2xl font-bold text-yellow-400">
                {propFirmAccounts.filter(acc => acc.status === 'active').length}
              </div>
              <div className="text-sm text-gray-400">Active Trading</div>
            </div>
            <TrendingUp className="w-8 h-8 text-yellow-400" />
          </div>
        </div>
      </div>

      {/* Add Account Button */}
      <div className="flex justify-between items-center">
        <h2 className="text-xl font-bold">Your Prop Firm Accounts</h2>
        <button
          onClick={() => setIsAddingAccount(true)}
          className="bg-blue-600 hover:bg-blue-700 px-4 py-2 rounded-lg flex items-center space-x-2 transition-colors"
        >
          <Plus className="w-4 h-4" />
          <span>Add Account</span>
        </button>
      </div>

      {/* Add Account Modal */}
      {isAddingAccount && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-gray-800 rounded-lg p-6 w-full max-w-md border border-gray-700">
            <h3 className="text-xl font-bold mb-4">Add Prop Firm Account</h3>
            
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-2">Prop Firm</label>
                <select
                  value={newAccount.firmName}
                  onChange={(e) => setNewAccount({ ...newAccount, firmName: e.target.value })}
                  className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-white"
                >
                  <option value="">Select a firm</option>
                  {propFirms.map(firm => (
                    <option key={firm.name} value={firm.name}>{firm.name}</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium mb-2">Account Size</label>
                <select
                  value={newAccount.accountSize}
                  onChange={(e) => setNewAccount({ ...newAccount, accountSize: Number(e.target.value) })}
                  className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-white"
                >
                  {propFirms
                    .find(firm => firm.name === newAccount.firmName)?.accountSizes
                    .map(size => (
                      <option key={size} value={size}>${size.toLocaleString()}</option>
                    )) || (
                    <option value={10000}>$10,000</option>
                  )}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium mb-2">Profit Target (%)</label>
                <input
                  type="number"
                  value={newAccount.profitTarget}
                  onChange={(e) => setNewAccount({ ...newAccount, profitTarget: Number(e.target.value) })}
                  className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-white"
                  min="1"
                  max="20"
                />
              </div>

              <div>
                <label className="block text-sm font-medium mb-2">Max Drawdown (%)</label>
                <input
                  type="number"
                  value={newAccount.maxDrawdown}
                  onChange={(e) => setNewAccount({ ...newAccount, maxDrawdown: Number(e.target.value) })}
                  className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-white"
                  min="1"
                  max="10"
                />
              </div>

              <div>
                <label className="block text-sm font-medium mb-2">Daily Loss Limit (%)</label>
                <input
                  type="number"
                  value={newAccount.dailyLossLimit}
                  onChange={(e) => setNewAccount({ ...newAccount, dailyLossLimit: Number(e.target.value) })}
                  className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-white"
                  min="1"
                  max="5"
                />
              </div>
            </div>

            <div className="flex space-x-3 mt-6">
              <button
                onClick={handleAddAccount}
                disabled={!newAccount.firmName}
                className="flex-1 bg-green-600 hover:bg-green-700 disabled:bg-gray-600 px-4 py-2 rounded-lg transition-colors"
              >
                Add Account
              </button>
              <button
                onClick={() => setIsAddingAccount(false)}
                className="flex-1 bg-gray-600 hover:bg-gray-700 px-4 py-2 rounded-lg transition-colors"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Accounts List */}
      {propFirmAccounts.length > 0 ? (
        <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-4">
          {propFirmAccounts.map(account => (
            <div key={account.id} className="bg-gray-800 rounded-lg p-4 border border-gray-700">
              {/* Account Header */}
              <div className="flex items-center justify-between mb-3">
                <div>
                  <h3 className="font-bold">{account.firmName}</h3>
                  <p className="text-sm text-gray-400">${account.accountSize.toLocaleString()}</p>
                </div>
                <div className="text-right">
                  <div className={`text-xs px-2 py-1 rounded ${getStatusColor(account.status)}`}>
                    {account.status}
                  </div>
                  <div className={`text-xs mt-1 ${getPhaseColor(account.phase)}`}>
                    {account.phase}
                  </div>
                </div>
              </div>

              {/* Balance & Performance */}
              <div className="space-y-2 mb-3">
                <div className="flex justify-between">
                  <span className="text-sm text-gray-400">Current Balance:</span>
                  <span className="font-medium">${account.currentBalance.toLocaleString()}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-sm text-gray-400">Gross Profit:</span>
                  <span className="font-medium text-green-400">${account.grossProfit.toLocaleString()}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-sm text-gray-400">Net Profit (80%):</span>
                  <span className="font-medium text-purple-400">${account.netProfit.toLocaleString()}</span>
                </div>
              </div>

              {/* Progress Bars */}
              <div className="space-y-3">
                {/* Profit Target Progress */}
                <div>
                  <div className="flex justify-between text-xs mb-1">
                    <span>Profit Target</span>
                    <span>{((account.grossProfit / (account.accountSize * account.profitTarget / 100)) * 100).toFixed(1)}%</span>
                  </div>
                  <div className="w-full bg-gray-700 rounded-full h-2">
                    <div 
                      className="bg-green-500 h-2 rounded-full transition-all duration-300"
                      style={{ width: `${Math.min((account.grossProfit / (account.accountSize * account.profitTarget / 100)) * 100, 100)}%` }}
                    ></div>
                  </div>
                </div>

                {/* Drawdown Risk */}
                <div>
                  <div className="flex justify-between text-xs mb-1">
                    <span>Max Drawdown Risk</span>
                    <span>{account.maxDrawdown}%</span>
                  </div>
                  <div className="w-full bg-gray-700 rounded-full h-2">
                    <div 
                      className="bg-red-500 h-2 rounded-full transition-all duration-300"
                      style={{ width: `${(account.maxDrawdown / 10) * 100}%` }}
                    ></div>
                  </div>
                </div>
              </div>

              {/* Account Actions */}
              <div className="flex items-center justify-between mt-4 pt-3 border-t border-gray-700">
                <div className="flex items-center space-x-2">
                  {account.isEnabled ? (
                    <div className="flex items-center space-x-1 text-green-400">
                      <CheckCircle className="w-4 h-4" />
                      <span className="text-xs">Active</span>
                    </div>
                  ) : (
                    <div className="flex items-center space-x-1 text-gray-400">
                      <AlertCircle className="w-4 h-4" />
                      <span className="text-xs">Disabled</span>
                    </div>
                  )}
                </div>
                <div className="text-xs text-gray-400">
                  Started: {new Date(account.startDate).toLocaleDateString()}
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="bg-gray-800 rounded-lg p-8 text-center border border-gray-700">
          <Building2 className="w-16 h-16 text-gray-600 mx-auto mb-4" />
          <h3 className="text-xl font-bold mb-2">No Prop Firm Accounts Yet</h3>
          <p className="text-gray-400 mb-4">
            Start your journey by adding your first prop firm account. 
            This will help track your progress towards the Phase 1 goal of 30 accounts.
          </p>
          <button
            onClick={() => setIsAddingAccount(true)}
            className="bg-blue-600 hover:bg-blue-700 px-6 py-3 rounded-lg font-medium transition-colors"
          >
            Add Your First Account
          </button>
        </div>
      )}

      {/* Milestones */}
      <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
        <h3 className="text-xl font-bold mb-4 flex items-center">
          <Target className="w-6 h-6 text-blue-400 mr-2" />
          Phase 1 Milestones
        </h3>
        
        <div className="space-y-4">
          {[
            { count: 1, title: 'First Account', reward: '100 XP + Achievement' },
            { count: 5, title: 'Growing Portfolio', reward: '500 XP + New Features' },
            { count: 10, title: 'Serious Trader', reward: '1000 XP + Phase 1 Progress' },
            { count: 20, title: 'Professional Level', reward: '2000 XP + Advanced Tools' },
            { count: 30, title: 'Phase 1 Complete', reward: '5000 XP + Phase 2 Unlock' }
          ].map(milestone => {
            const isCompleted = propFirmAccounts.length >= milestone.count;
            const isNext = propFirmAccounts.length === milestone.count - 1;
            
            return (
              <div 
                key={milestone.count}
                className={`flex items-center justify-between p-4 rounded-lg border ${
                  isCompleted 
                    ? 'bg-green-900/20 border-green-500/30' 
                    : isNext 
                      ? 'bg-blue-900/20 border-blue-500/30' 
                      : 'bg-gray-700 border-gray-600'
                }`}
              >
                <div className="flex items-center space-x-3">
                  {isCompleted ? (
                    <CheckCircle className="w-6 h-6 text-green-400" />
                  ) : (
                    <div className={`w-6 h-6 rounded-full border-2 flex items-center justify-center text-xs ${
                      isNext ? 'border-blue-400 text-blue-400' : 'border-gray-500 text-gray-500'
                    }`}>
                      {milestone.count}
                    </div>
                  )}
                  <div>
                    <div className="font-medium">{milestone.count} Accounts - {milestone.title}</div>
                    <div className="text-sm text-gray-400">{milestone.reward}</div>
                  </div>
                </div>
                {isNext && (
                  <div className="text-sm text-blue-400 font-medium">Next!</div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};

export default PropFirmManager;
