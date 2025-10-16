import { PieChart, TrendingUp, Bell, Layers } from 'lucide-react';
import React, { useMemo } from 'react';

import { useMilestones } from '../../context/MilestoneContext';
import { usePortfolioStore } from '../../stores/portfolioStore';

import AllocationPie from './AllocationPie';


const PortfolioPage: React.FC = () => {
  const { userProgress, updateFinancialSnapshot, updateMilestoneProgress, completeMilestone } = useMilestones();
  const { allocations, setAllocation, phaseView, setPhaseView, rebalanceSuggestions, normalize, incomeAllocation, setIncomeAllocation, hardwarePubKey, setHardwarePubKey } = usePortfolioStore();

  const totals = useMemo(() => {
    const l = userProgress.financialSnapshot.liquidAssets;
    const i = userProgress.financialSnapshot.investmentAssets;
    const t = l + i;
    return { liquid: l, invest: i, total: t };
  }, [userProgress.financialSnapshot]);

  const activeVsLongTerm = useMemo(() => {
    const active = allocations['active_trading'] || 0;
    const longTerm = 100 - active;
    return { active, longTerm };
  }, [allocations]);

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      <div className="bg-gray-800 border border-gray-700 rounded-lg p-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <PieChart className="w-6 h-6 text-blue-400" />
            <div>
              <h1 className="text-2xl font-bold text-white">Portfolio</h1>
              <p className="text-gray-400 text-sm">Allocate across stocks/ETFs/crypto/futures. Phase 1 vs Phase 2 views.</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <select
              value={phaseView}
              onChange={(e) => setPhaseView(e.target.value as any)}
              className="px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white"
            >
              <option value="phase1">Phase 1: Money-making</option>
              <option value="phase2">Phase 2: Long-term</option>
            </select>
          </div>
        </div>

        <div className="mt-4 grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="bg-gray-700/30 rounded-lg p-4 border border-gray-600">
            <div className="text-gray-400 text-sm">Monthly Income</div>
            <input
              type="number"
              value={userProgress.financialSnapshot.monthlyIncome}
              onChange={(e)=> updateFinancialSnapshot({ monthlyIncome: Number(e.target.value) })}
              className="mt-1 w-full px-2 py-1 bg-gray-800 border border-gray-600 rounded text-white"
            />
          </div>
          <div className="bg-gray-700/30 rounded-lg p-4 border border-gray-600">
            <div className="text-gray-400 text-sm">Monthly Expenses</div>
            <input
              type="number"
              value={userProgress.financialSnapshot.monthlyExpenses}
              onChange={(e)=> updateFinancialSnapshot({ monthlyExpenses: Number(e.target.value) })}
              className="mt-1 w-full px-2 py-1 bg-gray-800 border border-gray-600 rounded text-white"
            />
          </div>
          <div className="bg-gray-700/30 rounded-lg p-4 border border-gray-600">
            <div className="text-gray-400 text-sm">Net Worth</div>
            <div className="text-2xl font-bold text-white">${userProgress.financialSnapshot.totalNetWorth.toFixed(0)}</div>
          </div>
          <div className="bg-gray-700/30 rounded-lg p-4 border border-gray-600">
            <div className="text-gray-400 text-sm">Liquid</div>
            <div className="text-2xl font-bold text-white">${totals.liquid.toFixed(0)}</div>
          </div>
          <div className="bg-gray-700/30 rounded-lg p-4 border border-gray-600">
            <div className="text-gray-400 text-sm">Investments</div>
            <div className="text-2xl font-bold text-white">${totals.invest.toFixed(0)}</div>
          </div>
          <div className="bg-gray-700/30 rounded-lg p-4 border border-gray-600">
            <div className="text-gray-400 text-sm">Expense Coverage</div>
            <div className="text-2xl font-bold text-white">{userProgress.financialSnapshot.expenseCoverage.toFixed(0)}%</div>
          </div>
        </div>
      </div>

      <div className="bg-gray-800 border border-gray-700 rounded-lg p-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Layers className="w-5 h-5 text-blue-400" />
            <h2 className="text-lg font-semibold text-white">Asset Allocation</h2>
          </div>
        </div>

  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="space-y-3">
            {Object.entries(allocations).map(([k, v]) => (
              <div key={k} className="bg-gray-700/30 rounded-lg p-4 border border-gray-600">
                <div className="flex items-center justify-between">
                  <div className="text-white font-medium">{k.split('_').join(' ').toUpperCase()}</div>
                  <div className="flex items-center gap-2">
                    <input
                      type="range"
                      min={0}
                      max={100}
                      value={Number(v as number)}
                      onChange={(e) => setAllocation(k as any, Number(e.target.value))}
                    />
                    <span className="text-white font-semibold w-12 text-right">{Number(v as number)}%</span>
                  </div>
                </div>
              </div>
            ))}
            <div className="flex justify-end">
              <button onClick={normalize} className="px-3 py-2 bg-gray-600 hover:bg-gray-700 rounded text-white text-sm">Normalize to 100%</button>
            </div>
          </div>

          <div className="space-y-4">
            <div className="bg-gray-700/30 rounded-lg p-4 border border-gray-600">
              <AllocationPie data={allocations as any} />
            </div>
            <div className="bg-gray-700/30 rounded-lg p-4 border border-gray-600">
              <div className="text-gray-400 text-sm">Phase View</div>
              <div className="text-xl font-semibold text-white">{phaseView === 'phase1' ? 'Focus: Cashflow' : 'Focus: Long-term Growth'}</div>
              <div className="mt-2 text-sm text-gray-300">Active Trading: {activeVsLongTerm.active}% • Long-term: {activeVsLongTerm.longTerm}%</div>
            </div>

            <div className="bg-gray-700/30 rounded-lg p-4 border border-gray-600">
              <div className="flex items-center gap-2 text-white font-semibold">
                <Bell className="w-4 h-4 text-yellow-300"/> Alerts & Suggestions
              </div>
              <ul className="mt-2 text-sm text-gray-300 list-disc pl-5 space-y-1">
                {rebalanceSuggestions().map((s, i) => (
                  <li key={i}>{s}</li>
                ))}
              </ul>
            </div>

            <div className="bg-gray-700/30 rounded-lg p-4 border border-gray-600">
              <div className="flex items-center gap-2 text-white font-semibold">
                <TrendingUp className="w-4 h-4 text-green-300"/> Phase Allocation Presets
              </div>
              <div className="mt-2 text-sm text-gray-300 space-x-2">
                <button onClick={() => setPhaseView('phase1')} className="px-3 py-1 bg-blue-600 hover:bg-blue-700 rounded">Phase 1</button>
                <button onClick={() => setPhaseView('phase2')} className="px-3 py-1 bg-purple-600 hover:bg-purple-700 rounded">Phase 2</button>
              </div>
            </div>

            <div className="bg-gray-700/30 rounded-lg p-4 border border-gray-600">
              <div className="text-white font-semibold mb-2">Income Allocation (Phase 2)</div>
              {Object.entries(incomeAllocation).map(([k, v]) => (
                <div key={k} className="flex items-center justify-between py-1 text-sm">
                  <span className="text-gray-300">{k.toUpperCase()}</span>
                  <div className="flex items-center gap-2">
                    <input type="range" min={0} max={100} value={Number(v as number)}
                      onChange={(e)=> setIncomeAllocation(k as any, Number(e.target.value))} />
                    <span className="text-white w-10 text-right">{Number(v as number)}%</span>
                  </div>
                </div>
              ))}
              <div className="text-xs text-gray-400 mt-2">Allocate a % of prop payouts to TFSA/RRSP/Crypto/Questrade.</div>
            </div>

            <div className="bg-gray-700/30 rounded-lg p-4 border border-gray-600">
              <div className="text-white font-semibold mb-2">Hardware Wallet Tracking</div>
              <input
                value={hardwarePubKey}
                onChange={(e)=> setHardwarePubKey(e.target.value)}
                placeholder="Enter public key / xpub"
                className="w-full px-3 py-2 bg-gray-800 border border-gray-600 rounded text-white"
              />
              <div className="text-xs text-gray-400 mt-2">We only store public keys and derive addresses read-only.</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default PortfolioPage;
