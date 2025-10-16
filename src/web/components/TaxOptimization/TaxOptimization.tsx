import { TrendingUp, Shield, DollarSign, Calendar, CheckCircle, AlertCircle } from 'lucide-react';
import SectionHeader from '@layout/SectionHeader';
import PageContainer from '@layout/PageContainer';
import React, { useState } from 'react';

interface TaxOptimizationProps {
  userFinancialData?: any;
}

const TaxOptimization: React.FC<TaxOptimizationProps> = ({ userFinancialData }) => {
  const [selectedTaxYear, setSelectedTaxYear] = useState(2024);
  
  // Mock Canadian tax optimization data
  const mockTaxData = {
    currentYear: 2024,
    taxOptimizationScore: 78,
    estimatedSavings: 4200,
    accounts: {
      tfsa: {
        contribution: 15000,
        limit: 88000,
        remaining: 73000,
        growth: 2400
      },
      rrsp: {
        contribution: 8500,
        limit: 31560,
        remaining: 23060,
        taxSavings: 2550
      },
      nonRegistered: {
        tradingGains: 12500,
        capitalGains: 8200,
        taxableIncome: 6100
      }
    },
    optimizationActions: [
      {
        id: 1,
        title: 'Maximize TFSA Contributions',
        description: 'You have $73,000 in unused TFSA room. Consider transferring gains here.',
        priority: 'high',
        potentialSavings: 1200,
        status: 'pending'
      },
      {
        id: 2,
        title: 'Harvest Capital Losses',
        description: 'Realize $3,400 in capital losses to offset trading gains.',
        priority: 'medium',
        potentialSavings: 850,
        status: 'pending'
      },
      {
        id: 3,
        title: 'RRSP Top-up Before Deadline',
        description: 'Add $5,000 to RRSP for additional tax deduction.',
        priority: 'high',
        potentialSavings: 1500,
        status: 'completed'
      }
    ],
    quarterlyReports: [
      { quarter: 'Q1 2024', tradingIncome: 8500, taxOwing: 2125, optimized: true },
      { quarter: 'Q2 2024', tradingIncome: 12200, taxOwing: 2440, optimized: true },
      { quarter: 'Q3 2024', tradingIncome: 15800, taxOwing: 2844, optimized: false },
      { quarter: 'Q4 2024', tradingIncome: 0, taxOwing: 0, optimized: false }
    ]
  };

  const taxYears = [2022, 2023, 2024, 2025];

  return (
    <PageContainer>
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-4xl font-bold text-white mb-2">Taxes</h1>
              <p className="text-white/70">Maximize your tax efficiency and savings 🇨🇦</p>
            </div>
            <div className="flex items-center gap-4">
              <select 
                value={selectedTaxYear}
                onChange={(e) => setSelectedTaxYear(Number(e.target.value))}
                className="bg-white/10 border border-white/20 rounded-lg px-4 py-2 text-white"
              >
                {taxYears.map(year => (
                  <option key={year} value={year} className="bg-gray-800">{year}</option>
                ))}
              </select>
            </div>
          </div>
        </div>

        {/* Tax Optimization Score */}
        <div className="glass-card p-6 mb-8">
          <div className="flex items-center justify-between mb-4">
            <div>
              <SectionHeader title="Tax Optimization Score" headingLevel={3} dense />
              <p className="text-white/70 -mt-1">Based on your current tax strategy</p>
            </div>
            <div className="text-center">
              <div className="relative w-24 h-24">
                <svg className="w-24 h-24 transform -rotate-90">
                  <circle
                    cx="48"
                    cy="48"
                    r="40"
                    stroke="rgba(255,255,255,0.2)"
                    strokeWidth="8"
                    fill="none"
                  />
                  <circle
                    cx="48"
                    cy="48"
                    r="40"
                    stroke="#60a5fa"
                    strokeWidth="8"
                    fill="none"
                    strokeDasharray={`${2 * Math.PI * 40}`}
                    strokeDashoffset={`${2 * Math.PI * 40 * (1 - mockTaxData.taxOptimizationScore / 100)}`}
                    className="transition-all duration-500"
                  />
                </svg>
                <div className="absolute inset-0 flex items-center justify-center">
                  <span className="text-2xl font-bold text-white">{mockTaxData.taxOptimizationScore}</span>
                </div>
              </div>
              <p className="text-blue-300 font-medium mt-2">Estimated Savings</p>
              <p className="text-white font-bold">${mockTaxData.estimatedSavings.toLocaleString()}</p>
            </div>
          </div>
        </div>

        {/* Account Overview */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
          {/* TFSA */}
          <div className="glass-card p-6">
            <SectionHeader icon={<Shield className="h-6 w-6 text-green-400" />} title="TFSA" />
            <div className="space-y-3">
              <div className="flex justify-between">
                <span className="text-white/70">Contributed</span>
                <span className="text-white font-semibold">${mockTaxData.accounts.tfsa.contribution.toLocaleString()}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-white/70">Room Remaining</span>
                <span className="text-green-400 font-semibold">${mockTaxData.accounts.tfsa.remaining.toLocaleString()}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-white/70">Tax-Free Growth</span>
                <span className="text-green-400 font-semibold">+${mockTaxData.accounts.tfsa.growth.toLocaleString()}</span>
              </div>
              <div className="mt-4 bg-green-400/20 rounded-full h-2">
                <div 
                  className="bg-green-400 h-2 rounded-full"
                  style={{ width: `${(mockTaxData.accounts.tfsa.contribution / mockTaxData.accounts.tfsa.limit) * 100}%` }}
                />
              </div>
              <p className="text-xs text-white/60">
                {((mockTaxData.accounts.tfsa.contribution / mockTaxData.accounts.tfsa.limit) * 100).toFixed(1)}% of limit used
              </p>
            </div>
          </div>

          {/* RRSP */}
          <div className="glass-card p-6">
            <SectionHeader icon={<TrendingUp className="h-6 w-6 text-blue-400" />} title="RRSP" />
            <div className="space-y-3">
              <div className="flex justify-between">
                <span className="text-white/70">Contributed</span>
                <span className="text-white font-semibold">${mockTaxData.accounts.rrsp.contribution.toLocaleString()}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-white/70">Room Remaining</span>
                <span className="text-blue-400 font-semibold">${mockTaxData.accounts.rrsp.remaining.toLocaleString()}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-white/70">Tax Savings</span>
                <span className="text-blue-400 font-semibold">${mockTaxData.accounts.rrsp.taxSavings.toLocaleString()}</span>
              </div>
              <div className="mt-4 bg-blue-400/20 rounded-full h-2">
                <div 
                  className="bg-blue-400 h-2 rounded-full"
                  style={{ width: `${(mockTaxData.accounts.rrsp.contribution / mockTaxData.accounts.rrsp.limit) * 100}%` }}
                />
              </div>
              <p className="text-xs text-white/60">
                {((mockTaxData.accounts.rrsp.contribution / mockTaxData.accounts.rrsp.limit) * 100).toFixed(1)}% of limit used
              </p>
            </div>
          </div>

          {/* Non-Registered */}
          <div className="glass-card p-6">
            <SectionHeader icon={<DollarSign className="h-6 w-6 text-purple-400" />} title="Non-Registered" />
            <div className="space-y-3">
              <div className="flex justify-between">
                <span className="text-white/70">Trading Gains</span>
                <span className="text-white font-semibold">${mockTaxData.accounts.nonRegistered.tradingGains.toLocaleString()}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-white/70">Capital Gains</span>
                <span className="text-white font-semibold">${mockTaxData.accounts.nonRegistered.capitalGains.toLocaleString()}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-white/70">Taxable Income</span>
                <span className="text-red-400 font-semibold">${mockTaxData.accounts.nonRegistered.taxableIncome.toLocaleString()}</span>
              </div>
              <div className="mt-4 p-3 bg-red-500/20 rounded-lg border border-red-500/30">
                <p className="text-red-300 text-sm">
                  Estimated tax: ${(mockTaxData.accounts.nonRegistered.taxableIncome * 0.25).toLocaleString()}
                </p>
              </div>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
          {/* Optimization Actions */}
          <div className="glass-card p-6">
            <SectionHeader title="Optimization Actions" />
            <div className="space-y-4">
              {mockTaxData.optimizationActions.map((action) => (
                <div key={action.id} className="p-4 bg-white/10 rounded-lg border border-white/20">
                  <div className="flex items-start justify-between mb-2">
                    <div className="flex items-center gap-2">
                      {action.status === 'completed' ? 
                        <CheckCircle className="h-5 w-5 text-green-400" /> :
                        <AlertCircle className={`h-5 w-5 ${action.priority === 'high' ? 'text-red-400' : 'text-yellow-400'}`} />
                      }
                      <h4 className="font-semibold text-white">{action.title}</h4>
                    </div>
                    <span className={`px-2 py-1 rounded text-xs font-medium ${
                      action.priority === 'high' ? 'bg-red-500/20 text-red-300 border border-red-500/50' :
                      'bg-yellow-500/20 text-yellow-300 border border-yellow-500/50'
                    }`}>
                      {action.priority}
                    </span>
                  </div>
                  <p className="text-white/70 text-sm mb-3">{action.description}</p>
                  <div className="flex items-center justify-between">
                    <span className="text-green-400 font-medium">
                      Potential Savings: ${action.potentialSavings}
                    </span>
                    <span className={`px-2 py-1 rounded text-xs ${
                      action.status === 'completed' ? 'bg-green-500/20 text-green-300' :
                      'bg-blue-500/20 text-blue-300'
                    }`}>
                      {action.status}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Quarterly Reports */}
          <div className="glass-card p-6">
            <SectionHeader title="Quarterly Tax Reports" />
            <div className="space-y-4">
              {mockTaxData.quarterlyReports.map((report, index) => (
                <div key={index} className="p-4 bg-white/10 rounded-lg border border-white/20">
                  <div className="flex items-center justify-between mb-2">
                    <h4 className="font-semibold text-white">{report.quarter}</h4>
                    <span className={`px-2 py-1 rounded text-xs ${
                      report.optimized ? 'bg-green-500/20 text-green-300' : 'bg-gray-500/20 text-gray-300'
                    }`}>
                      {report.optimized ? 'Optimized' : 'Pending'}
                    </span>
                  </div>
                  <div className="grid grid-cols-2 gap-4 text-sm">
                    <div>
                      <span className="text-white/70">Trading Income</span>
                      <p className="text-white font-semibold">${report.tradingIncome.toLocaleString()}</p>
                    </div>
                    <div>
                      <span className="text-white/70">Tax Owing</span>
                      <p className="text-white font-semibold">${report.taxOwing.toLocaleString()}</p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
            
            <button className="w-full mt-4 p-3 bg-blue-500/20 hover:bg-blue-500/30 rounded-lg border border-blue-500/30 text-blue-300 font-medium transition-colors">
              Generate Tax Report
            </button>
          </div>
        </div>

        {/* Tax Calendar */}
  <div className="glass-card p-6">
          <SectionHeader icon={<Calendar className="h-6 w-6 text-orange-400" />} title="Important Tax Dates" />
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="p-4 bg-white/10 rounded-lg border border-white/20 text-center">
              <p className="text-white/70 text-sm">RRSP Deadline</p>
              <p className="text-white font-bold">March 1, 2025</p>
              <p className="text-red-400 text-xs mt-1">45 days left</p>
            </div>
            <div className="p-4 bg-white/10 rounded-lg border border-white/20 text-center">
              <p className="text-white/70 text-sm">Tax Filing</p>
              <p className="text-white font-bold">April 30, 2025</p>
              <p className="text-yellow-400 text-xs mt-1">104 days left</p>
            </div>
            <div className="p-4 bg-white/10 rounded-lg border border-white/20 text-center">
              <p className="text-white/70 text-sm">Q1 Installment</p>
              <p className="text-white font-bold">March 15, 2025</p>
              <p className="text-orange-400 text-xs mt-1">59 days left</p>
            </div>
            <div className="p-4 bg-white/10 rounded-lg border border-white/20 text-center">
              <p className="text-white/70 text-sm">TFSA New Room</p>
              <p className="text-white font-bold">January 1, 2025</p>
              <p className="text-green-400 text-xs mt-1">Available now</p>
            </div>
          </div>
    </div>
  </PageContainer>
  );
};

export default TaxOptimization;
