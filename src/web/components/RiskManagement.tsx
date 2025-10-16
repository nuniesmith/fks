import { Shield, AlertTriangle, Calculator, Target } from 'lucide-react';
import React from 'react';

const RiskManagement: React.FC = () => {
  const riskRules = [
    {
      rule: 'Maximum Capital Risk Per Trade',
      value: '1% of total account value',
      icon: <Shield className="w-5 h-5 text-red-400" />,
      description: 'Never risk more than 1% of total capital on any single trade'
    },
    {
      rule: 'Maximum Daily Drawdown',
      value: '3% of account value, stop trading upon reaching',
      icon: <AlertTriangle className="w-5 h-5 text-yellow-400" />,
      description: 'Protect against catastrophic daily losses'
    },
    {
      rule: 'Maximum Monthly Drawdown',
      value: '7% of account value, reduce position size by 50% at 5% drawdown',
      icon: <AlertTriangle className="w-5 h-5 text-orange-400" />,
      description: 'Scale down risk when monthly performance deteriorates'
    },
    {
      rule: 'Correlation Risk',
      value: 'Maximum 3 correlated positions open simultaneously',
      icon: <Target className="w-5 h-5 text-blue-400" />,
      description: 'Prevent overexposure to correlated market movements'
    },
    {
      rule: 'Risk-Reward Minimum',
      value: '1:1.5 for scalps, 1:2 for intraday, 1:3 for swing trades',
      icon: <Calculator className="w-5 h-5 text-green-400" />,
      description: 'Ensure favorable risk-to-reward ratios for all trades'
    }
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
        <h1 className="text-3xl font-bold text-white mb-2 flex items-center">
          <Shield className="w-8 h-8 mr-3 text-red-400" />
          Risk Management Master Rules
        </h1>
        <p className="text-gray-400">Fundamental risk controls that protect capital and ensure long-term survival</p>
      </div>

      {/* Risk Rules */}
      <div className="space-y-4">
        {riskRules.map((rule, index) => (
          <div key={index} className="bg-gray-800 rounded-lg p-6 border border-gray-700">
            <div className="flex items-start space-x-4">
              <div className="flex-shrink-0 mt-1">
                {rule.icon}
              </div>
              <div className="flex-1">
                <div className="flex items-start justify-between mb-2">
                  <h3 className="text-lg font-semibold text-white">{index + 1}. {rule.rule}</h3>
                </div>
                <div className="text-green-400 font-medium mb-2">{rule.value}</div>
                <p className="text-gray-400 text-sm">{rule.description}</p>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Position Sizing Formula */}
      <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
        <h2 className="text-xl font-semibold text-white mb-4 flex items-center">
          <Calculator className="w-6 h-6 mr-2 text-green-400" />
          Position Sizing Formula
        </h2>
        <div className="bg-gray-900/50 rounded-lg p-6">
          <div className="text-center">
            <div className="text-lg text-gray-300 mb-4">Position Size =</div>
            <div className="text-xl font-mono text-green-400 bg-gray-800 rounded-lg p-4 inline-block">
              (Account Size × Risk Percentage) ÷ (Entry Price - Stop Loss Price)
            </div>
          </div>
          <div className="mt-6 grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="text-center">
              <div className="text-sm text-gray-400 mb-1">Account Size</div>
              <div className="text-lg font-medium text-white">Total Capital</div>
            </div>
            <div className="text-center">
              <div className="text-sm text-gray-400 mb-1">Risk Percentage</div>
              <div className="text-lg font-medium text-white">1% (0.01)</div>
            </div>
            <div className="text-center">
              <div className="text-sm text-gray-400 mb-1">Risk per Share</div>
              <div className="text-lg font-medium text-white">Entry - Stop Loss</div>
            </div>
          </div>
        </div>
      </div>

      {/* Risk Monitoring */}
      <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
        <h2 className="text-xl font-semibold text-white mb-4">Real-Time Risk Monitoring</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="bg-gray-900/50 rounded-lg p-4 text-center">
            <div className="text-2xl font-bold text-green-400 mb-1">0.8%</div>
            <div className="text-sm text-gray-400">Current Daily Risk</div>
          </div>
          <div className="bg-gray-900/50 rounded-lg p-4 text-center">
            <div className="text-2xl font-bold text-blue-400 mb-1">2.1%</div>
            <div className="text-sm text-gray-400">Monthly Risk</div>
          </div>
          <div className="bg-gray-900/50 rounded-lg p-4 text-center">
            <div className="text-2xl font-bold text-purple-400 mb-1">2</div>
            <div className="text-sm text-gray-400">Open Positions</div>
          </div>
          <div className="bg-gray-900/50 rounded-lg p-4 text-center">
            <div className="text-2xl font-bold text-orange-400 mb-1">1:2.1</div>
            <div className="text-sm text-gray-400">Avg Risk:Reward</div>
          </div>
        </div>
      </div>

      {/* Emergency Protocols */}
      <div className="bg-gradient-to-r from-red-900/20 to-orange-900/20 rounded-lg p-6 border border-red-500/30">
        <h2 className="text-xl font-semibold text-white mb-4 flex items-center">
          <AlertTriangle className="w-6 h-6 mr-2 text-red-400" />
          Emergency Risk Protocols
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <h3 className="text-lg font-medium text-white mb-3">Daily Limit Breach</h3>
            <ul className="space-y-2 text-gray-300">
              <li className="flex items-start space-x-2">
                <span className="text-red-400 mt-1">•</span>
                <span>Immediately close all open positions</span>
              </li>
              <li className="flex items-start space-x-2">
                <span className="text-red-400 mt-1">•</span>
                <span>Cancel all pending orders</span>
              </li>
              <li className="flex items-start space-x-2">
                <span className="text-red-400 mt-1">•</span>
                <span>No new trades for remainder of day</span>
              </li>
            </ul>
          </div>
          <div>
            <h3 className="text-lg font-medium text-white mb-3">Monthly Limit Approach</h3>
            <ul className="space-y-2 text-gray-300">
              <li className="flex items-start space-x-2">
                <span className="text-orange-400 mt-1">•</span>
                <span>Reduce position sizes by 50%</span>
              </li>
              <li className="flex items-start space-x-2">
                <span className="text-orange-400 mt-1">•</span>
                <span>Increase minimum risk:reward to 1:3</span>
              </li>
              <li className="flex items-start space-x-2">
                <span className="text-orange-400 mt-1">•</span>
                <span>Review and analyze recent performance</span>
              </li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
};

export default RiskManagement;
