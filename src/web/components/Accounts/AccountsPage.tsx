import { Plus, ToggleLeft, ToggleRight, Wallet, LineChart, Trophy, Rocket } from 'lucide-react';
import React, { useMemo, useState } from 'react';

import { useMilestones } from '../../context/MilestoneContext';

import type { TaxOptimizedAccount, PropFirmSplit } from '../../types/milestones';

// Simple in-memory id
const uid = () => Math.random().toString(36).slice(2);

const DEFAULT_PROP_SPLIT: PropFirmSplit = {
  firmPercentage: 80,
  traderPercentage: 20,
  monthlyTarget: 1000,
  currentMonthProfit: 0,
  payout: 'monthly'
};

const AccountsPage: React.FC = () => {
  const { userProgress, addAccount, updateAccount, removeAccount, awardExperience, updateMilestoneProgress, completeMilestone } = useMilestones();
  const [filter, setFilter] = useState<'all' | 'prop_firm' | 'tfsa' | 'rrsp' | 'fhsa' | 'crypto' | 'margin' | 'cash' | 'business'>('all');
  const [strategyToAssign, setStrategyToAssign] = useState('');

  const accounts = userProgress.accounts;
  const filtered = useMemo(() => (filter === 'all' ? accounts : accounts.filter(a => a.type === filter)), [accounts, filter]);

  const propCount = accounts.filter(a => a.type === 'prop_firm' && a.status === 'active').length;

  const addPropAccount = () => {
    const n: TaxOptimizedAccount = {
      id: uid(),
      name: `Prop ${propCount + 1}`,
      type: 'prop_firm',
      broker: 'TopStep/Apex/TPT',
      accountNumber: 'P-' + Math.floor(Math.random() * 1e6).toString().padStart(6, '0'),
      currency: 'USD',
      taxCategory: 'prop_firm_income',
      status: 'active',
      openedAt: new Date(),
      currentBalance: 0,
      totalDeposits: 0,
      totalWithdrawals: 0,
      realizedProfits: 0,
      unrealizedProfits: 0,
      taxReporting: {
        year: new Date().getFullYear(),
        t4Reported: false,
        t5Reported: false,
        businessIncomeReported: false,
        foreignIncomeReported: false,
        capitalGainsReported: false,
        slips: [],
        estimatedTax: 0
      },
      isActive: true,
      profitSharing: { ...DEFAULT_PROP_SPLIT }
    };
    addAccount(n);
    // Update milestone progress toward 30 prop accounts
    const newCount = propCount + 1;
    updateMilestoneProgress('ten_prop_accounts', Math.min(10, newCount));
    updateMilestoneProgress('thirty_prop_accounts', Math.min(30, newCount));
    if (newCount === 1) { completeMilestone('first_prop_account'); awardExperience('MILESTONE_COMPLETED'); }
    if (newCount === 10) { completeMilestone('ten_prop_accounts'); awardExperience('MILESTONE_COMPLETED'); }
    if (newCount === 30) { completeMilestone('thirty_prop_accounts'); awardExperience('MILESTONE_COMPLETED'); }
  };

  const addCryptoAccount = () => {
    const n: TaxOptimizedAccount = {
      id: uid(),
      name: 'Crypto Wallet',
      type: 'crypto',
      broker: 'Binance/Coinbase',
      accountNumber: 'wallet',
      currency: 'USD',
      taxCategory: 'capital_gains',
      status: 'active',
      openedAt: new Date(),
      currentBalance: 0, totalDeposits: 0, totalWithdrawals: 0, realizedProfits: 0, unrealizedProfits: 0,
      taxReporting: { year: new Date().getFullYear(), t4Reported: false, t5Reported: false, businessIncomeReported: false, foreignIncomeReported: false, capitalGainsReported: true, slips: [], estimatedTax: 0 },
      isActive: true,
    };
    addAccount(n);
    awardExperience('ACCOUNT_OPENED', { type: 'crypto' });
  };

  const addQuestradeTFSA = () => {
    const n: TaxOptimizedAccount = {
      id: uid(),
      name: 'Questrade TFSA',
      type: 'tfsa',
      broker: 'Questrade',
      accountNumber: 'QT-' + Math.floor(Math.random() * 1e6).toString().padStart(6, '0'),
      currency: 'CAD',
      taxCategory: 'tax_free',
      status: 'active',
      openedAt: new Date(),
      currentBalance: 0, totalDeposits: 0, totalWithdrawals: 0, realizedProfits: 0, unrealizedProfits: 0,
      taxReporting: { year: new Date().getFullYear(), t4Reported: false, t5Reported: true, businessIncomeReported: false, foreignIncomeReported: false, capitalGainsReported: false, slips: [], estimatedTax: 0 },
      isActive: true,
    };
    addAccount(n);
    awardExperience('TFSA_CONTRIBUTION');
    completeMilestone('tfsa_setup');
  };

  const toggleActive = (id: string, isActive: boolean) => {
    updateAccount(id, { isActive, status: isActive ? 'active' : 'inactive' });
  };

  const updateSplit = (id: string, field: keyof PropFirmSplit, value: number | 'monthly' | 'bi-weekly' | 'on-demand') => {
    const acc = accounts.find(a => a.id === id);
    if (!acc) return;
    const ps = { ...(acc.profitSharing || DEFAULT_PROP_SPLIT), [field]: value } as PropFirmSplit;
    updateAccount(id, { profitSharing: ps });
  };

  const projectedTraderPayout = (a: TaxOptimizedAccount) => {
    const ps = a.profitSharing || DEFAULT_PROP_SPLIT;
    const gross = Math.max(0, ps.currentMonthProfit);
    // 80:20 net/gross note: some firms quote split on net after fees; we keep it simple here
    return (gross * ps.firmPercentage) / 100;
  };

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      <div className="bg-gray-800 border border-gray-700 rounded-lg p-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Wallet className="w-6 h-6 text-blue-400" />
            <div>
              <h1 className="text-2xl font-bold text-white">Accounts</h1>
              <p className="text-gray-400 text-sm">Manage futures, crypto, and Canadian tax-advantaged accounts</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <select
              value={filter}
              onChange={e => setFilter(e.target.value as any)}
              className="px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white"
            >
              <option value="all">All</option>
              <option value="prop_firm">Prop Firms</option>
              <option value="crypto">Crypto</option>
              <option value="tfsa">TFSA</option>
              <option value="rrsp">RRSP</option>
              <option value="fhsa">FHSA</option>
              <option value="margin">Margin</option>
              <option value="cash">Cash</option>
              <option value="business">Business</option>
            </select>
            <button onClick={addPropAccount} className="inline-flex items-center gap-2 px-4 py-2 bg-green-600 hover:bg-green-700 rounded-lg text-white">
              <Plus className="w-4 h-4" /> Add Prop Account
            </button>
            <button onClick={addCryptoAccount} className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg text-white">
              <Plus className="w-4 h-4" /> Add Crypto
            </button>
            <button onClick={addQuestradeTFSA} className="inline-flex items-center gap-2 px-4 py-2 bg-purple-600 hover:bg-purple-700 rounded-lg text-white">
              <Plus className="w-4 h-4" /> Add Questrade TFSA
            </button>
            {/* FHSA quick add mirrors TFSA properties but tagged 'fhsa' */}
            <button onClick={() => {
              const n: TaxOptimizedAccount = {
                id: uid(),
                name: 'Questrade FHSA',
                type: 'fhsa',
                broker: 'Questrade',
                accountNumber: 'FH-' + Math.floor(Math.random() * 1e6).toString().padStart(6, '0'),
                currency: 'CAD',
                taxCategory: 'tax_deferred',
                status: 'active',
                openedAt: new Date(),
                currentBalance: 0, totalDeposits: 0, totalWithdrawals: 0, realizedProfits: 0, unrealizedProfits: 0,
                taxReporting: { year: new Date().getFullYear(), t4Reported: false, t5Reported: false, businessIncomeReported: false, foreignIncomeReported: false, capitalGainsReported: false, slips: [], estimatedTax: 0 },
                isActive: true,
              };
              addAccount(n);
              awardExperience('ACCOUNT_OPENED', { type: 'fhsa' });
            }} className="inline-flex items-center gap-2 px-4 py-2 bg-pink-600 hover:bg-pink-700 rounded-lg text-white">
              <Plus className="w-4 h-4" /> Add Questrade FHSA
            </button>
          </div>
        </div>

        <div className="mt-4 grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="bg-gray-700/30 rounded-lg p-4 border border-gray-600">
            <div className="text-gray-400 text-sm">Active Prop Accounts</div>
            <div className="text-2xl font-bold text-white">{propCount}</div>
            <div className="text-xs text-gray-400">Goal: 30</div>
          </div>
          <div className="bg-gray-700/30 rounded-lg p-4 border border-gray-600">
            <div className="text-gray-400 text-sm">Milestone</div>
            <div className="text-2xl font-bold text-white flex items-center gap-2"><Trophy className="w-5 h-5 text-yellow-400"/>1 → 30</div>
            <div className="text-xs text-gray-400">Gamified scaling</div>
          </div>
          <div className="bg-gray-700/30 rounded-lg p-4 border border-gray-600">
            <div className="text-gray-400 text-sm">Projected Payouts</div>
            <div className="text-2xl font-bold text-green-400">
              ${filtered.filter(a=>a.type==='prop_firm').reduce((s,a)=>s+projectedTraderPayout(a),0).toFixed(0)}
            </div>
            <div className="text-xs text-gray-400">This month (80:20)</div>
          </div>
          <div className="bg-gray-700/30 rounded-lg p-4 border border-gray-600">
            <div className="text-gray-400 text-sm">EXP</div>
            <div className="text-2xl font-bold text-purple-400">{userProgress.totalXP}</div>
            <div className="text-xs text-gray-400">Rewards for scaling</div>
          </div>
        </div>
      </div>

      <div className="bg-gray-800 border border-gray-700 rounded-lg p-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <LineChart className="w-5 h-5 text-blue-400" />
            <h2 className="text-lg font-semibold text-white">Accounts ({filtered.length})</h2>
          </div>
          <div className="flex items-center gap-2">
            <input
              placeholder="Strategy ID/name"
              value={strategyToAssign}
              onChange={(e)=> setStrategyToAssign(e.target.value)}
              className="px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white"
            />
            <button
              onClick={() => {
                if (!strategyToAssign.trim()) return;
                filtered.forEach(a => {
                  const assigned = Array.from(new Set([...(a.assignedStrategies || []), strategyToAssign.trim()]));
                  updateAccount(a.id, { assignedStrategies: assigned });
                });
                awardExperience('STRATEGY_VALIDATED', { appliedTo: filtered.length });
              }}
              className="px-3 py-2 bg-indigo-600 hover:bg-indigo-700 rounded text-white"
            >Apply to Shown</button>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filtered.map(a => (
            <div key={a.id} className="bg-gray-700/30 rounded-lg p-4 border border-gray-600">
              <div className="flex items-center justify-between mb-2">
                <div>
                  <div className="text-white font-medium">{a.name}</div>
                  <div className="text-xs text-gray-400">{a.type.toUpperCase()} • {a.broker}</div>
                </div>
                <button
                  onClick={() => toggleActive(a.id, !a.isActive)}
                  className={`p-2 rounded ${a.isActive ? 'text-green-400' : 'text-gray-400 hover:text-white'}`}
                  title={a.isActive ? 'Active' : 'Inactive'}
                >
                  {a.isActive ? <ToggleRight className="w-5 h-5"/> : <ToggleLeft className="w-5 h-5"/>}
                </button>
              </div>

              {a.type === 'prop_firm' && (
                <div className="space-y-2 text-sm">
                  <div className="flex items-center justify-between">
                    <span className="text-gray-400">Split</span>
                    <span className="text-white">{a.profitSharing?.firmPercentage ?? 80}% / {a.profitSharing?.traderPercentage ?? 20}%</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-gray-400">Monthly Target</span>
                    <input
                      type="number"
                      className="w-28 px-2 py-1 bg-gray-800 border border-gray-600 rounded text-white"
                      value={a.profitSharing?.monthlyTarget ?? 1000}
                      onChange={e => updateSplit(a.id, 'monthlyTarget', Number(e.target.value))}
                    />
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-gray-400">Current Profit</span>
                    <input
                      type="number"
                      className="w-28 px-2 py-1 bg-gray-800 border border-gray-600 rounded text-white"
                      value={a.profitSharing?.currentMonthProfit ?? 0}
                      onChange={e => updateSplit(a.id, 'currentMonthProfit', Number(e.target.value))}
                    />
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-gray-400">Payout</span>
                    <select
                      className="w-32 px-2 py-1 bg-gray-800 border border-gray-600 rounded text-white"
                      value={a.profitSharing?.payout ?? 'monthly'}
                      onChange={e => updateSplit(a.id, 'payout', e.target.value as any)}
                    >
                      <option value="monthly">Monthly</option>
                      <option value="bi-weekly">Bi-weekly</option>
                      <option value="on-demand">On-demand</option>
                    </select>
                  </div>
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-gray-400">Projected Payout</span>
                    <span className="text-green-400 font-semibold">${projectedTraderPayout(a).toFixed(0)}</span>
                  </div>
                </div>
              )}

              <div className="mt-3 flex items-center justify-between text-xs text-gray-400">
                <button
                  className="text-red-300 hover:text-red-200"
                  onClick={() => removeAccount(a.id)}
                >
                  Remove
                </button>
                <button
                  className="text-purple-300 hover:text-purple-200 inline-flex items-center gap-1"
                  onClick={() => awardExperience('ACCOUNT_OPENED', { id: a.id })}
                >
                  <Rocket className="w-4 h-4"/> Award EXP
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default AccountsPage;
