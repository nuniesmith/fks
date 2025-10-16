import { 
  Shield, 
  PiggyBank, 
  TrendingUp, 
  Building, 
  Globe, 
  Settings,
  BookOpen,
  Filter,
  Search
} from 'lucide-react';
import React, { useState } from 'react';

import { ACCOUNT_TYPES } from '../../types';

import AccountTypeInfo from './AccountTypeInfo';

import type { AccountType } from '../../types';

const AccountGuide: React.FC = () => {
  const [selectedCategory, setSelectedCategory] = useState<'all' | 'retirement' | 'tax-free' | 'taxable' | 'corporate' | 'specialized' | 'demo'>('all');
  const [searchTerm, setSearchTerm] = useState('');

  const categories = [
    { key: 'all', label: 'All Accounts', icon: BookOpen },
    { key: 'retirement', label: 'Retirement', icon: Shield },
    { key: 'tax-free', label: 'Tax-Free', icon: PiggyBank },
    { key: 'taxable', label: 'Taxable', icon: TrendingUp },
    { key: 'corporate', label: 'Corporate', icon: Building },
    { key: 'specialized', label: 'Specialized', icon: Globe },
    { key: 'demo', label: 'Demo', icon: Settings }
  ];

  const filteredAccountTypes = Object.entries(ACCOUNT_TYPES)
    .filter(([type, info]) => {
      const matchesCategory = selectedCategory === 'all' || info.category === selectedCategory;
      const matchesSearch = searchTerm === '' || 
        info.displayName.toLowerCase().includes(searchTerm.toLowerCase()) ||
        info.description.toLowerCase().includes(searchTerm.toLowerCase()) ||
        type.toLowerCase().includes(searchTerm.toLowerCase());
      
      return matchesCategory && matchesSearch;
    });

  const getContributionLimits2024 = (type: AccountType) => {
    switch (type) {
      case 'tfsa': return '$7,000';
      case 'rrsp': return '18% of previous year income (max ~$30,780)';
      case 'fhsa': return '$8,000 (lifetime max $40,000)';
      case 'resp': return '$2,500 (to get max government grants)';
      default: return null;
    }
  };

  return (
    <div className="min-h-screen bg-gray-900 text-white p-6">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-white mb-2">Canadian Investment Account Guide</h1>
        <p className="text-gray-400 mb-4">
          Comprehensive guide to Canadian investment account types available through Questrade and other brokers
        </p>
        
        {/* Search and Filter */}
        <div className="flex flex-col sm:flex-row gap-4 mb-6">
          <div className="flex-1 relative">
            <Search className="w-4 h-4 absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" />
            <input
              type="text"
              placeholder="Search account types..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-10 pr-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:border-blue-500"
            />
          </div>
          
          <div className="flex items-center space-x-2">
            <Filter className="w-4 h-4 text-gray-400" />
            <select
              value={selectedCategory}
              onChange={(e) => setSelectedCategory(e.target.value as any)}
              className="px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white focus:outline-none focus:border-blue-500"
            >
              {categories.map(cat => (
                <option key={cat.key} value={cat.key}>{cat.label}</option>
              ))}
            </select>
          </div>
        </div>

        {/* Category Navigation */}
        <div className="flex flex-wrap gap-2">
          {categories.map(cat => {
            const Icon = cat.icon;
            return (
              <button
                key={cat.key}
                onClick={() => setSelectedCategory(cat.key as any)}
                className={`flex items-center space-x-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                  selectedCategory === cat.key
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-800 text-gray-300 hover:bg-gray-700'
                }`}
              >
                <Icon className="w-4 h-4" />
                <span>{cat.label}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* 2024 Key Information Banner */}
      <div className="bg-gradient-to-r from-blue-600/20 to-purple-600/20 border border-blue-500/30 rounded-lg p-4 mb-6">
        <h3 className="text-lg font-semibold text-blue-400 mb-2">2024 Contribution Limits & Updates</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
          <div>
            <div className="text-green-400 font-medium">TFSA: $7,000</div>
            <div className="text-gray-300">Annual contribution room</div>
          </div>
          <div>
            <div className="text-purple-400 font-medium">RRSP: 18% of income</div>
            <div className="text-gray-300">Max ~$30,780 (2024)</div>
          </div>
          <div>
            <div className="text-indigo-400 font-medium">FHSA: $8,000</div>
            <div className="text-gray-300">New in 2023, lifetime max $40,000</div>
          </div>
        </div>
      </div>

      {/* Account Types Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-6">
        {filteredAccountTypes.map(([type, info]) => {
          const contributionLimit = getContributionLimits2024(type as AccountType);
          
          return (
            <div key={type} className="bg-gray-800 rounded-lg p-6 border border-gray-700 hover:border-gray-600 transition-colors">
              <AccountTypeInfo type={type as AccountType} showDetails={true} className="mb-4" />
              
              {/* Additional Details */}
              <div className="space-y-3">
                {contributionLimit && (
                  <div className="bg-gray-700/50 rounded p-3">
                    <div className="text-sm text-gray-400 mb-1">2024 Contribution Limit</div>
                    <div className="text-green-400 font-medium">{contributionLimit}</div>
                  </div>
                )}
                
                {/* Questrade Specific Features */}
                <div className="text-xs text-gray-500">
                  <div className="font-medium text-gray-400 mb-1">Available at Questrade:</div>
                  {type === 'tfsa' && (
                    <ul className="list-disc list-inside space-y-1">
                      <li>No fees for ETF purchases</li>
                      <li>Wide selection of stocks, ETFs, options</li>
                      <li>Tax-free growth and withdrawals</li>
                    </ul>
                  )}
                  {type === 'rrsp' && (
                    <ul className="list-disc list-inside space-y-1">
                      <li>Tax deduction on contributions</li>
                      <li>Tax-deferred growth</li>
                      <li>Convert to RIF at retirement</li>
                    </ul>
                  )}
                  {type === 'personal-margin' && (
                    <ul className="list-disc list-inside space-y-1">
                      <li>Options trading available</li>
                      <li>Margin lending for leverage</li>
                      <li>Advanced order types</li>
                    </ul>
                  )}
                  {type === 'fx-cfd' && (
                    <ul className="list-disc list-inside space-y-1">
                      <li>Currency pairs trading</li>
                      <li>Contract for Difference</li>
                      <li>High leverage available</li>
                    </ul>
                  )}
                  {type === 'fhsa' && (
                    <ul className="list-disc list-inside space-y-1">
                      <li>Tax deduction + tax-free growth</li>
                      <li>For first-time home buyers</li>
                      <li>New account type (2023+)</li>
                    </ul>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Footer Information */}
      <div className="mt-12 bg-gray-800 rounded-lg p-6 border border-gray-700">
        <h3 className="text-lg font-semibold text-white mb-4">About Questrade & Canadian Brokers</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 text-sm text-gray-300">
          <div>
            <h4 className="font-medium text-blue-400 mb-2">Questrade Benefits</h4>
            <ul className="list-disc list-inside space-y-1">
              <li>No commission ETF purchases</li>
              <li>Low stock trading fees ($4.95-$9.95)</li>
              <li>Advanced trading platform</li>
              <li>Wide range of account types</li>
              <li>Options trading available</li>
              <li>FX and CFD trading</li>
            </ul>
          </div>
          <div>
            <h4 className="font-medium text-green-400 mb-2">Tax Optimization Strategy</h4>
            <ul className="list-disc list-inside space-y-1">
              <li>Max out TFSA first (tax-free growth)</li>
              <li>Use RRSP for tax deductions</li>
              <li>Consider FHSA for home purchases</li>
              <li>Taxable accounts for additional investing</li>
              <li>Corporate accounts for business</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
};

export default AccountGuide;
