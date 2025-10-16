import {
  Plus,
  Settings,
  Globe,
  Twitter,
  MessageSquare,
  Brain,
  Wifi,
  WifiOff,
  ToggleLeft,
  ToggleRight,
  Trash2,
  Edit,
  ExternalLink,
  AlertCircle,
  CheckCircle,
  Clock,
  Shield,
  PiggyBank,
  TrendingUp,
  Building
} from 'lucide-react';
import React, { useState, useEffect } from 'react';

import { useTradingEnv } from '../../context/TradingEnvContext';
import { ACCOUNT_TYPES } from '../../types';

import type { AccountType} from '../../types';

interface TradingAccount {
  id: string;
  name: string;
  type: AccountType;
  broker: string;
  balance: number;
  equity: number;
  buyingPower: number;
  isEnabled: boolean;
  isConnected: boolean;
  lastUpdate: string;
  riskLevel: 'conservative' | 'moderate' | 'aggressive';
  maxDrawdown: number;
  maxPosition: number;
  contributionRoom?: number; // For registered accounts
  annualContributionLimit?: number; // For accounts with limits
}

interface ExternalInterface {
  id: string;
  name: string;
  type: 'social' | 'news' | 'ai' | 'data' | 'communication';
  isEnabled: boolean;
  isConnected: boolean;
  description: string;
  icon: React.ReactNode;
  configUrl?: string;
}

const AccountsManager: React.FC = () => {
  const { environment, updateEnvironment, isLive, isSimulation } = useTradingEnv();
  const [accounts, setAccounts] = useState<TradingAccount[]>([]);
  const [interfaces, setInterfaces] = useState<ExternalInterface[]>([]);
  const [showAddAccount, setShowAddAccount] = useState(false);
  const [selectedTab, setSelectedTab] = useState<'accounts' | 'interfaces'>('accounts');

  useEffect(() => {
    // Mock trading accounts with Canadian account types
    const mockAccounts: TradingAccount[] = [
      {
        id: 'apex-001',
        name: 'Apex Trading - Main',
        type: 'prop-firm',
        broker: 'Apex Trader Funding',
        balance: 150000,
        equity: 152750,
        buyingPower: 600000,
        isEnabled: true,
        isConnected: true,
        lastUpdate: '2 minutes ago',
        riskLevel: 'moderate',
        maxDrawdown: 6000,
        maxPosition: 75000
      },
      {
        id: 'topstep-002',
        name: 'TopStep - Evaluation',
        type: 'prop-firm',
        broker: 'TopStep Trader',
        balance: 50000,
        equity: 51200,
        buyingPower: 200000,
        isEnabled: false,
        isConnected: true,
        lastUpdate: '5 minutes ago',
        riskLevel: 'conservative',
        maxDrawdown: 2000,
        maxPosition: 25000
      },
      {
        id: 'questrade-rrsp-001',
        name: 'Questrade RRSP - Long-term Growth',
        type: 'rrsp',
        broker: 'Questrade',
        balance: 75000,
        equity: 78420,
        buyingPower: 75000,
        isEnabled: true,
        isConnected: true,
        lastUpdate: '1 minute ago',
        riskLevel: 'conservative',
        maxDrawdown: 5000,
        maxPosition: 15000,
        contributionRoom: 25000,
        annualContributionLimit: 30780 // 2024 RRSP limit (18% of previous year income)
      },
      {
        id: 'questrade-tfsa-001',
        name: 'Questrade TFSA - Tax-Free Growth',
        type: 'tfsa',
        broker: 'Questrade',
        balance: 45000,
        equity: 47200,
        buyingPower: 45000,
        isEnabled: true,
        isConnected: true,
        lastUpdate: '3 minutes ago',
        riskLevel: 'moderate',
        maxDrawdown: 3000,
        maxPosition: 10000,
        contributionRoom: 43500,
        annualContributionLimit: 7000 // 2024 TFSA limit
      },
      {
        id: 'questrade-margin-001',
        name: 'Questrade Margin - Active Trading',
        type: 'personal-margin',
        broker: 'Questrade',
        balance: 25000,
        equity: 26800,
        buyingPower: 50000,
        isEnabled: true,
        isConnected: true,
        lastUpdate: '30 seconds ago',
        riskLevel: 'aggressive',
        maxDrawdown: 5000,
        maxPosition: 25000
      },
      {
        id: 'questrade-fx-001',
        name: 'Questrade FX & CFD',
        type: 'fx-cfd',
        broker: 'Questrade',
        balance: 15000,
        equity: 15750,
        buyingPower: 75000, // Higher leverage for FX
        isEnabled: false,
        isConnected: true,
        lastUpdate: '2 minutes ago',
        riskLevel: 'aggressive',
        maxDrawdown: 7500,
        maxPosition: 50000
      },
      {
        id: 'questrade-fhsa-001',
        name: 'Questrade FHSA - First Home',
        type: 'fhsa',
        broker: 'Questrade',
        balance: 12000,
        equity: 12450,
        buyingPower: 12000,
        isEnabled: true,
        isConnected: true,
        lastUpdate: '5 minutes ago',
        riskLevel: 'conservative',
        maxDrawdown: 1000,
        maxPosition: 5000,
        contributionRoom: 28000,
        annualContributionLimit: 8000 // 2024 FHSA limit
      }
    ];

    // Mock external interfaces
    const mockInterfaces: ExternalInterface[] = [
      {
        id: 'reddit-api',
        name: 'Reddit',
        type: 'social',
        isEnabled: true,
        isConnected: true,
        description: 'Market sentiment from trading communities',
        icon: <Globe className="w-5 h-5" />
      },
      {
        id: 'twitter-api',
        name: 'Twitter/X',
        type: 'social',
        isEnabled: true,
        isConnected: false,
        description: 'Real-time market news and sentiment',
        icon: <Twitter className="w-5 h-5" />
      },
      {
        id: 'discord-bot',
        name: 'Discord',
        type: 'communication',
        isEnabled: true,
        isConnected: true,
        description: 'Trading signals and notifications',
        icon: <MessageSquare className="w-5 h-5" />
      },
      {
        id: 'chatgpt-api',
        name: 'ChatGPT',
        type: 'ai',
        isEnabled: true,
        isConnected: true,
        description: 'AI market analysis and insights',
        icon: <Brain className="w-5 h-5" />
      },
      {
        id: 'ollama-local',
        name: 'Ollama (Local AI)',
        type: 'ai',
        isEnabled: false,
        isConnected: false,
        description: 'Local AI model for private analysis',
        icon: <Brain className="w-5 h-5" />
      }
    ];

    setAccounts(mockAccounts);
    setInterfaces(mockInterfaces);
  }, []);

  const toggleAccountEnabled = (accountId: string) => {
    setAccounts(prev => 
      prev.map(account => 
        account.id === accountId 
          ? { ...account, isEnabled: !account.isEnabled }
          : account
      )
    );

    // Update trading environment
    const updatedAccounts = accounts.map(account => 
      account.id === accountId 
        ? { ...account, isEnabled: !account.isEnabled }
        : account
    );
    
    const enabledAccountIds = updatedAccounts
      .filter(account => account.isEnabled)
      .map(account => account.id);
    
    // Note: In a real implementation, you would update the trading configuration
    // For now, we'll just log the enabled accounts
    console.log('Enabled accounts:', enabledAccountIds);
  };

  const toggleInterfaceEnabled = (interfaceId: string) => {
    setInterfaces(prev => 
      prev.map(iface => 
        iface.id === interfaceId 
          ? { ...iface, isEnabled: !iface.isEnabled }
          : iface
      )
    );
  };

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD'
    }).format(amount);
  };

  const getAccountTypeColor = (type: AccountType) => {
    const accountInfo = ACCOUNT_TYPES[type];
    switch (accountInfo.category) {
      case 'retirement': return 'bg-purple-500/20 text-purple-400 border-purple-500/30';
      case 'tax-free': return 'bg-green-500/20 text-green-400 border-green-500/30';
      case 'taxable': return 'bg-blue-500/20 text-blue-400 border-blue-500/30';
      case 'corporate': return 'bg-orange-500/20 text-orange-400 border-orange-500/30';
      case 'specialized': 
        if (type === 'prop-firm') return 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30';
        if (type === 'fx-cfd') return 'bg-red-500/20 text-red-400 border-red-500/30';
        return 'bg-indigo-500/20 text-indigo-400 border-indigo-500/30';
      case 'demo': return 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30';
      default: return 'bg-gray-500/20 text-gray-400 border-gray-500/30';
    }
  };

  const getAccountTypeIcon = (type: AccountType) => {
    const accountInfo = ACCOUNT_TYPES[type];
    switch (accountInfo.category) {
      case 'retirement': return <Shield className="w-4 h-4" />;
      case 'tax-free': return <PiggyBank className="w-4 h-4" />;
      case 'taxable': return <TrendingUp className="w-4 h-4" />;
      case 'corporate': return <Building className="w-4 h-4" />;
      case 'specialized':
        if (type === 'prop-firm') return <TrendingUp className="w-4 h-4" />;
        if (type === 'fx-cfd') return <Globe className="w-4 h-4" />;
        return <Settings className="w-4 h-4" />;
      case 'demo': return <Settings className="w-4 h-4" />;
      default: return <Settings className="w-4 h-4" />;
    }
  };

  const getRiskLevelColor = (level: string) => {
    switch (level) {
      case 'conservative': return 'text-green-400';
      case 'moderate': return 'text-yellow-400';
      case 'aggressive': return 'text-red-400';
      default: return 'text-gray-400';
    }
  };

  const getInterfaceTypeColor = (type: string) => {
    switch (type) {
      case 'social': return 'text-blue-400';
      case 'news': return 'text-green-400';
      case 'ai': return 'text-purple-400';
      case 'data': return 'text-orange-400';
      case 'communication': return 'text-indigo-400';
      default: return 'text-gray-400';
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-white mb-2">Accounts & Interfaces</h1>
            <p className="text-gray-400">Manage Canadian investment accounts and external integrations</p>
            <div className="mt-3 flex items-center space-x-4">
              <div className="flex items-center space-x-2 text-sm text-blue-400">
                <Shield className="w-4 h-4" />
                <span>Canadian Tax-Advantaged Accounts Available</span>
              </div>
              <div className="flex items-center space-x-2 text-sm text-green-400">
                <PiggyBank className="w-4 h-4" />
                <span>Questrade Integration Ready</span>
              </div>
            </div>
          </div>
          
          <div className="flex items-center space-x-4">
            <div className={`px-3 py-1 rounded-full text-sm font-medium border ${
              isLive 
                ? 'bg-red-500/20 text-red-400 border-red-500/30'
                : 'bg-green-500/20 text-green-400 border-green-500/30'
            }`}>
              {isLive ? '🔴 LIVE MODE' : '🟢 SIMULATION'}
            </div>
            
            <button
              onClick={() => setShowAddAccount(true)}
              className="flex items-center space-x-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg text-white transition-colors"
            >
              <Plus className="w-4 h-4" />
              <span>Add Account</span>
            </button>
          </div>
        </div>
        
        {/* Canadian Account Guide Banner */}
        <div className="mt-4 p-4 bg-gradient-to-r from-blue-600/20 to-green-600/20 border border-blue-500/30 rounded-lg">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <div className="w-8 h-8 bg-gradient-to-br from-red-500 to-white rounded-full flex items-center justify-center text-sm font-bold">
                🍁
              </div>
              <div>
                <h3 className="text-white font-medium">Canadian Investment Accounts</h3>
                <p className="text-gray-300 text-sm">Learn about TFSA, RRSP, FHSA, and other Canadian account types</p>
              </div>
            </div>
            <button
              onClick={() => window.location.hash = '#canadian-accounts'}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg text-white text-sm font-medium transition-colors"
            >
              View Guide
            </button>
          </div>
        </div>
      </div>

      {/* Tab Navigation */}
      <div className="bg-gray-800 rounded-lg border border-gray-700">
        <div className="flex border-b border-gray-700">
          <button
            onClick={() => setSelectedTab('accounts')}
            className={`flex-1 px-6 py-4 text-center font-medium transition-colors ${
              selectedTab === 'accounts'
                ? 'text-blue-400 border-b-2 border-blue-400 bg-gray-700/30'
                : 'text-gray-400 hover:text-white'
            }`}
          >
            Trading Accounts
          </button>
          <button
            onClick={() => setSelectedTab('interfaces')}
            className={`flex-1 px-6 py-4 text-center font-medium transition-colors ${
              selectedTab === 'interfaces'
                ? 'text-blue-400 border-b-2 border-blue-400 bg-gray-700/30'
                : 'text-gray-400 hover:text-white'
            }`}
          >
            External Interfaces
          </button>
        </div>

        <div className="p-6">
          {selectedTab === 'accounts' ? (
            /* Trading Accounts */
            <div className="space-y-4">
              {accounts.map((account) => (
                <div key={account.id} className="bg-gray-700/30 rounded-lg p-4 border border-gray-600">
                  <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center space-x-4">
                      <div className={`flex items-center space-x-2 px-3 py-1 rounded-full text-sm font-medium border ${getAccountTypeColor(account.type)}`}>
                        {getAccountTypeIcon(account.type)}
                        <span>{ACCOUNT_TYPES[account.type].displayName}</span>
                      </div>
                      
                      <div>
                        <h3 className="text-white font-semibold">{account.name}</h3>
                        <p className="text-gray-400 text-sm">{account.broker}</p>
                        <p className="text-gray-500 text-xs">{ACCOUNT_TYPES[account.type].description}</p>
                      </div>
                      
                      <div className="flex items-center space-x-2">
                        {ACCOUNT_TYPES[account.type].taxAdvantaged && (
                          <div className="flex items-center space-x-1 text-green-400">
                            <Shield className="w-4 h-4" />
                            <span className="text-xs">Tax Advantaged</span>
                          </div>
                        )}
                        
                        {account.isConnected ? (
                          <div className="flex items-center space-x-1 text-green-400">
                            <Wifi className="w-4 h-4" />
                            <span className="text-xs">Connected</span>
                          </div>
                        ) : (
                          <div className="flex items-center space-x-1 text-red-400">
                            <WifiOff className="w-4 h-4" />
                            <span className="text-xs">Disconnected</span>
                          </div>
                        )}
                        
                        <div className="flex items-center space-x-1 text-gray-400 text-xs">
                          <Clock className="w-3 h-3" />
                          <span>{account.lastUpdate}</span>
                        </div>
                      </div>
                    </div>
                    
                    <div className="flex items-center space-x-3">
                      <button
                        onClick={() => toggleAccountEnabled(account.id)}
                        className={`p-2 rounded-lg transition-colors ${
                          account.isEnabled 
                            ? 'text-green-400 hover:bg-green-500/20'
                            : 'text-gray-400 hover:bg-gray-600'
                        }`}
                        title={account.isEnabled ? 'Disable account' : 'Enable account'}
                      >
                        {account.isEnabled ? <ToggleRight className="w-6 h-6" /> : <ToggleLeft className="w-6 h-6" />}
                      </button>
                      
                      <button className="p-2 hover:bg-gray-600 rounded-lg text-gray-400 hover:text-white transition-colors">
                        <Edit className="w-4 h-4" />
                      </button>
                      
                      <button className="p-2 hover:bg-red-600 rounded-lg text-gray-400 hover:text-white transition-colors">
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                  
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                    <div>
                      <div className="text-gray-400">Balance</div>
                      <div className="text-white font-medium">{formatCurrency(account.balance)}</div>
                    </div>
                    <div>
                      <div className="text-gray-400">Equity</div>
                      <div className="text-white font-medium">{formatCurrency(account.equity)}</div>
                    </div>
                    <div>
                      <div className="text-gray-400">Buying Power</div>
                      <div className="text-white font-medium">{formatCurrency(account.buyingPower)}</div>
                    </div>
                    <div>
                      <div className="text-gray-400">Risk Level</div>
                      <div className={`font-medium ${getRiskLevelColor(account.riskLevel)}`}>
                        {account.riskLevel.charAt(0).toUpperCase() + account.riskLevel.slice(1)}
                      </div>
                    </div>
                  </div>
                  
                  {/* Canadian Account Specific Information */}
                  {(account.contributionRoom !== undefined || account.annualContributionLimit !== undefined) && (
                    <div className="mt-4 p-3 bg-gray-800/50 rounded-lg border border-gray-600">
                      <div className="text-sm text-gray-300 mb-2 font-medium">Canadian Tax Account Details</div>
                      <div className="grid grid-cols-2 gap-4 text-sm">
                        {account.contributionRoom !== undefined && (
                          <div>
                            <div className="text-gray-400">Contribution Room</div>
                            <div className="text-green-400 font-medium">{formatCurrency(account.contributionRoom)}</div>
                          </div>
                        )}
                        {account.annualContributionLimit !== undefined && (
                          <div>
                            <div className="text-gray-400">Annual Limit (2024)</div>
                            <div className="text-blue-400 font-medium">{formatCurrency(account.annualContributionLimit)}</div>
                          </div>
                        )}
                      </div>
                      {ACCOUNT_TYPES[account.type].withdrawalRestrictions && (
                        <div className="mt-2 text-xs text-yellow-400">
                          ⚠️ Withdrawal restrictions apply
                        </div>
                      )}
                    </div>
                  )}
                  
                  <div className="mt-4 flex items-center justify-between">
                    <div className="flex items-center space-x-4 text-sm">
                      <div className="text-gray-400">
                        Max Drawdown: <span className="text-red-400">{formatCurrency(account.maxDrawdown)}</span>
                      </div>
                      <div className="text-gray-400">
                        Max Position: <span className="text-blue-400">{formatCurrency(account.maxPosition)}</span>
                      </div>
                    </div>
                    
                    {account.isEnabled && isLive && (
                      <div className="flex items-center space-x-2 text-green-400 text-sm">
                        <CheckCircle className="w-4 h-4" />
                        <span>Active in Live Trading</span>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            /* External Interfaces */
            <div className="space-y-4">
              {interfaces.map((iface) => (
                <div key={iface.id} className="bg-gray-700/30 rounded-lg p-4 border border-gray-600">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-4">
                      <div className={`${getInterfaceTypeColor(iface.type)}`}>
                        {iface.icon}
                      </div>
                      
                      <div>
                        <h3 className="text-white font-semibold">{iface.name}</h3>
                        <p className="text-gray-400 text-sm">{iface.description}</p>
                      </div>
                      
                      <div className="flex items-center space-x-2">
                        {iface.isConnected ? (
                          <div className="flex items-center space-x-1 text-green-400">
                            <CheckCircle className="w-4 h-4" />
                            <span className="text-xs">Connected</span>
                          </div>
                        ) : (
                          <div className="flex items-center space-x-1 text-red-400">
                            <AlertCircle className="w-4 h-4" />
                            <span className="text-xs">Disconnected</span>
                          </div>
                        )}
                      </div>
                    </div>
                    
                    <div className="flex items-center space-x-3">
                      <button
                        onClick={() => toggleInterfaceEnabled(iface.id)}
                        className={`p-2 rounded-lg transition-colors ${
                          iface.isEnabled 
                            ? 'text-green-400 hover:bg-green-500/20'
                            : 'text-gray-400 hover:bg-gray-600'
                        }`}
                        title={iface.isEnabled ? 'Disable interface' : 'Enable interface'}
                      >
                        {iface.isEnabled ? <ToggleRight className="w-6 h-6" /> : <ToggleLeft className="w-6 h-6" />}
                      </button>
                      
                      <button className="p-2 hover:bg-gray-600 rounded-lg text-gray-400 hover:text-white transition-colors">
                        <Settings className="w-4 h-4" />
                      </button>
                      
                      {iface.configUrl && (
                        <button className="p-2 hover:bg-blue-600 rounded-lg text-gray-400 hover:text-white transition-colors">
                          <ExternalLink className="w-4 h-4" />
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Summary */}
      <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
        <h2 className="text-xl font-semibold text-white mb-4">Integration Summary</h2>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="text-center">
            <div className="text-2xl font-bold text-green-400">
              {accounts.filter(acc => acc.isEnabled).length}
            </div>
            <div className="text-gray-400 text-sm">Active Trading Accounts</div>
          </div>
          
          <div className="text-center">
            <div className="text-2xl font-bold text-purple-400">
              {accounts.filter(acc => acc.isEnabled && ACCOUNT_TYPES[acc.type].taxAdvantaged).length}
            </div>
            <div className="text-gray-400 text-sm">Tax-Advantaged Accounts</div>
          </div>
          
          <div className="text-center">
            <div className="text-2xl font-bold text-blue-400">
              {interfaces.filter(iface => iface.isEnabled && iface.isConnected).length}
            </div>
            <div className="text-gray-400 text-sm">Connected Interfaces</div>
          </div>
          
          <div className="text-center">
            <div className="text-2xl font-bold text-emerald-400">
              {formatCurrency(accounts.filter(acc => acc.isEnabled).reduce((sum, acc) => sum + acc.equity, 0))}
            </div>
            <div className="text-gray-400 text-sm">Total Active Equity</div>
          </div>
        </div>
        
        {/* Canadian Account Features */}
        <div className="mt-6 p-4 bg-gray-700/30 rounded-lg">
          <h3 className="text-lg font-medium text-white mb-3 flex items-center space-x-2">
            <span>🍁</span>
            <span>Canadian Account Benefits</span>
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 text-sm">
            <div className="flex items-center space-x-2">
              <Shield className="w-4 h-4 text-purple-400" />
              <span className="text-gray-300">RRSP: Tax-deferred growth</span>
            </div>
            <div className="flex items-center space-x-2">
              <PiggyBank className="w-4 h-4 text-green-400" />
              <span className="text-gray-300">TFSA: Tax-free growth & withdrawals</span>
            </div>
            <div className="flex items-center space-x-2">
              <Building className="w-4 h-4 text-indigo-400" />
              <span className="text-gray-300">FHSA: First home savings</span>
            </div>
            <div className="flex items-center space-x-2">
              <TrendingUp className="w-4 h-4 text-blue-400" />
              <span className="text-gray-300">Margin: Leveraged trading</span>
            </div>
            <div className="flex items-center space-x-2">
              <Globe className="w-4 h-4 text-red-400" />
              <span className="text-gray-300">FX & CFD: Currency trading</span>
            </div>
            <div className="flex items-center space-x-2">
              <Settings className="w-4 h-4 text-orange-400" />
              <span className="text-gray-300">Corporate accounts available</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default AccountsManager;
