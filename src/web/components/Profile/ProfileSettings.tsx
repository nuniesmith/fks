import {
  User,
  Settings,
  Shield,
  Brain,
  Save,
  AlertTriangle,
  Eye,
  EyeOff
} from 'lucide-react';
import React, { useState } from 'react';


interface RiskProfile {
  maxDrawdown: number;
  maxPositionSize: number;
  riskPerTrade: number;
  stopLossPercentage: number;
  takeProfitRatio: number;
}

interface TradingPreferences {
  tradingStyle: 'scalping' | 'day-trading' | 'swing' | 'position';
  preferredTimeframes: string[];
  preferredMarkets: string[];
  autoTradingEnabled: boolean;
  notificationsEnabled: boolean;
  maxConcurrentTrades: number;
}

interface Strategy {
  id: string;
  name: string;
  description: string;
  isActive: boolean;
  winRate: number;
  avgReturn: number;
}

const ProfileSettings: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'profile' | 'strategies' | 'risk' | 'preferences'>('profile');
  
  // Profile data
  const [profile, setProfile] = useState({
    name: 'Jordan Smith',
    email: 'nunie.smith01@gmail.com',
    timezone: 'America/New_York',
    joinDate: '2024-01-15',
    totalTrades: 1247,
    totalPnL: 45780.50,
    winRate: 68.5
  });

  // Risk management settings
  const [riskProfile, setRiskProfile] = useState<RiskProfile>({
    maxDrawdown: 5000,
    maxPositionSize: 50000,
    riskPerTrade: 1.5,
    stopLossPercentage: 2.0,
    takeProfitRatio: 2.5
  });

  // Trading preferences
  const [preferences, setPreferences] = useState<TradingPreferences>({
    tradingStyle: 'day-trading',
    preferredTimeframes: ['5m', '15m', '1h'],
    preferredMarkets: ['ES', 'NQ', 'YM'],
    autoTradingEnabled: true,
    notificationsEnabled: true,
    maxConcurrentTrades: 3
  });

  // Strategies
  const [strategies, setStrategies] = useState<Strategy[]>([
    {
      id: 'momentum-scalp',
      name: 'Momentum Scalping',
      description: 'Quick scalps on momentum moves',
      isActive: true,
      winRate: 72.5,
      avgReturn: 1.8
    },
    {
      id: 'mean-reversion',
      name: 'Mean Reversion',
      description: 'Counter-trend trades at key levels',
      isActive: true,
      winRate: 65.2,
      avgReturn: 2.4
    },
    {
      id: 'breakout',
      name: 'Breakout Strategy',
      description: 'Trade breakouts from consolidation',
      isActive: false,
      winRate: 58.7,
      avgReturn: 3.1
    }
  ]);

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD'
    }).format(amount);
  };

  const handleSaveProfile = () => {
    // Save profile logic
    console.log('Saving profile...', profile);
  };

  const handleSaveRisk = () => {
    // Save risk settings logic
    console.log('Saving risk profile...', riskProfile);
  };

  const handleSavePreferences = () => {
    // Save preferences logic
    console.log('Saving preferences...', preferences);
  };

  const toggleStrategy = (strategyId: string) => {
    setStrategies(prev => 
      prev.map(strategy => 
        strategy.id === strategyId 
          ? { ...strategy, isActive: !strategy.isActive }
          : strategy
      )
    );
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-4">
            <div className="w-16 h-16 bg-gradient-to-br from-blue-500 to-purple-600 rounded-full flex items-center justify-center">
              <User className="w-8 h-8 text-white" />
            </div>
            <div>
              <h1 className="text-3xl font-bold text-white">{profile.name}</h1>
              <p className="text-gray-400">Trading Profile & Preferences</p>
            </div>
          </div>
          
          <div className="flex items-center space-x-4">
            <div className="text-right">
              <div className="text-sm text-gray-400">Total P&L</div>
              <div className="text-xl font-bold text-green-400">
                {formatCurrency(profile.totalPnL)}
              </div>
            </div>
            <div className="text-right">
              <div className="text-sm text-gray-400">Win Rate</div>
              <div className="text-xl font-bold text-blue-400">
                {profile.winRate.toFixed(1)}%
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Tab Navigation */}
      <div className="bg-gray-800 rounded-lg border border-gray-700">
        <div className="flex border-b border-gray-700">
          {[
            { id: 'profile', label: 'Profile', icon: User },
            { id: 'strategies', label: 'Strategies', icon: Brain },
            { id: 'risk', label: 'Risk Management', icon: Shield },
            { id: 'preferences', label: 'Preferences', icon: Settings }
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as any)}
              className={`flex-1 flex items-center justify-center space-x-2 px-6 py-4 font-medium transition-colors ${
                activeTab === tab.id
                  ? 'text-blue-400 border-b-2 border-blue-400 bg-gray-700/30'
                  : 'text-gray-400 hover:text-white'
              }`}
            >
              <tab.icon className="w-4 h-4" />
              <span>{tab.label}</span>
            </button>
          ))}
        </div>

        <div className="p-6">
          {activeTab === 'profile' && (
            <div className="space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                  <label className="block text-sm font-medium text-gray-400 mb-2">
                    Full Name
                  </label>
                  <input
                    type="text"
                    value={profile.name}
                    onChange={(e) => setProfile({ ...profile, name: e.target.value })}
                    className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white focus:outline-none focus:border-blue-500"
                  />
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-gray-400 mb-2">
                    Email
                  </label>
                  <input
                    type="email"
                    value={profile.email}
                    onChange={(e) => setProfile({ ...profile, email: e.target.value })}
                    className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white focus:outline-none focus:border-blue-500"
                  />
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-gray-400 mb-2">
                    Timezone
                  </label>
                  <select
                    value={profile.timezone}
                    onChange={(e) => setProfile({ ...profile, timezone: e.target.value })}
                    className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white focus:outline-none focus:border-blue-500"
                  >
                    <option value="America/New_York">Eastern Time</option>
                    <option value="America/Chicago">Central Time</option>
                    <option value="America/Denver">Mountain Time</option>
                    <option value="America/Los_Angeles">Pacific Time</option>
                    <option value="Europe/London">London Time</option>
                  </select>
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-gray-400 mb-2">
                    Member Since
                  </label>
                  <input
                    type="text"
                    value={new Date(profile.joinDate).toLocaleDateString()}
                    disabled
                    className="w-full px-3 py-2 bg-gray-600 border border-gray-600 rounded-lg text-gray-400"
                  />
                </div>
              </div>
              
              <div className="flex justify-end">
                <button
                  onClick={handleSaveProfile}
                  className="flex items-center space-x-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg text-white transition-colors"
                >
                  <Save className="w-4 h-4" />
                  <span>Save Profile</span>
                </button>
              </div>
            </div>
          )}

          {activeTab === 'strategies' && (
            <div className="space-y-4">
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-xl font-semibold text-white">Trading Strategies</h2>
                <button className="flex items-center space-x-2 px-4 py-2 bg-green-600 hover:bg-green-700 rounded-lg text-white transition-colors">
                  <Brain className="w-4 h-4" />
                  <span>Create Strategy</span>
                </button>
              </div>
              
              {strategies.map((strategy) => (
                <div key={strategy.id} className="bg-gray-700/30 rounded-lg p-4 border border-gray-600">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-4">
                      <button
                        onClick={() => toggleStrategy(strategy.id)}
                        className={`p-2 rounded-lg transition-colors ${
                          strategy.isActive 
                            ? 'text-green-400 hover:bg-green-500/20'
                            : 'text-gray-400 hover:bg-gray-600'
                        }`}
                      >
                        {strategy.isActive ? <Eye className="w-5 h-5" /> : <EyeOff className="w-5 h-5" />}
                      </button>
                      
                      <div>
                        <h3 className="text-white font-semibold">{strategy.name}</h3>
                        <p className="text-gray-400 text-sm">{strategy.description}</p>
                      </div>
                    </div>
                    
                    <div className="flex items-center space-x-6">
                      <div className="text-center">
                        <div className="text-green-400 font-semibold">{strategy.winRate.toFixed(1)}%</div>
                        <div className="text-gray-400 text-xs">Win Rate</div>
                      </div>
                      <div className="text-center">
                        <div className="text-blue-400 font-semibold">{strategy.avgReturn.toFixed(1)}%</div>
                        <div className="text-gray-400 text-xs">Avg Return</div>
                      </div>
                      <button className="p-2 hover:bg-gray-600 rounded-lg text-gray-400 hover:text-white transition-colors">
                        <Settings className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}

          {activeTab === 'risk' && (
            <div className="space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                  <label className="block text-sm font-medium text-gray-400 mb-2">
                    Max Drawdown ($)
                  </label>
                  <input
                    type="number"
                    value={riskProfile.maxDrawdown}
                    onChange={(e) => setRiskProfile({ ...riskProfile, maxDrawdown: Number(e.target.value) })}
                    className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white focus:outline-none focus:border-blue-500"
                  />
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-gray-400 mb-2">
                    Max Position Size ($)
                  </label>
                  <input
                    type="number"
                    value={riskProfile.maxPositionSize}
                    onChange={(e) => setRiskProfile({ ...riskProfile, maxPositionSize: Number(e.target.value) })}
                    className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white focus:outline-none focus:border-blue-500"
                  />
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-gray-400 mb-2">
                    Risk Per Trade (%)
                  </label>
                  <input
                    type="number"
                    step="0.1"
                    value={riskProfile.riskPerTrade}
                    onChange={(e) => setRiskProfile({ ...riskProfile, riskPerTrade: Number(e.target.value) })}
                    className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white focus:outline-none focus:border-blue-500"
                  />
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-gray-400 mb-2">
                    Stop Loss (%)
                  </label>
                  <input
                    type="number"
                    step="0.1"
                    value={riskProfile.stopLossPercentage}
                    onChange={(e) => setRiskProfile({ ...riskProfile, stopLossPercentage: Number(e.target.value) })}
                    className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white focus:outline-none focus:border-blue-500"
                  />
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-gray-400 mb-2">
                    Take Profit Ratio
                  </label>
                  <input
                    type="number"
                    step="0.1"
                    value={riskProfile.takeProfitRatio}
                    onChange={(e) => setRiskProfile({ ...riskProfile, takeProfitRatio: Number(e.target.value) })}
                    className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white focus:outline-none focus:border-blue-500"
                  />
                </div>
              </div>
              
              <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-lg p-4">
                <div className="flex items-start space-x-3">
                  <AlertTriangle className="w-5 h-5 text-yellow-400 mt-0.5" />
                  <div>
                    <h3 className="text-yellow-400 font-semibold">Risk Management</h3>
                    <p className="text-yellow-300 text-sm">
                      These settings will be enforced across all trading strategies and accounts. 
                      Changes will affect all future trades.
                    </p>
                  </div>
                </div>
              </div>
              
              <div className="flex justify-end">
                <button
                  onClick={handleSaveRisk}
                  className="flex items-center space-x-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg text-white transition-colors"
                >
                  <Save className="w-4 h-4" />
                  <span>Save Risk Settings</span>
                </button>
              </div>
            </div>
          )}

          {activeTab === 'preferences' && (
            <div className="space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                  <label className="block text-sm font-medium text-gray-400 mb-2">
                    Trading Style
                  </label>
                  <select
                    value={preferences.tradingStyle}
                    onChange={(e) => setPreferences({ ...preferences, tradingStyle: e.target.value as any })}
                    className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white focus:outline-none focus:border-blue-500"
                  >
                    <option value="scalping">Scalping</option>
                    <option value="day-trading">Day Trading</option>
                    <option value="swing">Swing Trading</option>
                    <option value="position">Position Trading</option>
                  </select>
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-gray-400 mb-2">
                    Max Concurrent Trades
                  </label>
                  <input
                    type="number"
                    value={preferences.maxConcurrentTrades}
                    onChange={(e) => setPreferences({ ...preferences, maxConcurrentTrades: Number(e.target.value) })}
                    className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white focus:outline-none focus:border-blue-500"
                  />
                </div>
              </div>
              
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="text-white font-medium">Auto Trading</h3>
                    <p className="text-gray-400 text-sm">Allow automated strategy execution</p>
                  </div>
                  <button
                    onClick={() => setPreferences({ ...preferences, autoTradingEnabled: !preferences.autoTradingEnabled })}
                    className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                      preferences.autoTradingEnabled ? 'bg-blue-600' : 'bg-gray-600'
                    }`}
                  >
                    <span
                      className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                        preferences.autoTradingEnabled ? 'translate-x-6' : 'translate-x-1'
                      }`}
                    />
                  </button>
                </div>
                
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="text-white font-medium">Notifications</h3>
                    <p className="text-gray-400 text-sm">Receive trade alerts and updates</p>
                  </div>
                  <button
                    onClick={() => setPreferences({ ...preferences, notificationsEnabled: !preferences.notificationsEnabled })}
                    className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                      preferences.notificationsEnabled ? 'bg-blue-600' : 'bg-gray-600'
                    }`}
                  >
                    <span
                      className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                        preferences.notificationsEnabled ? 'translate-x-6' : 'translate-x-1'
                      }`}
                    />
                  </button>
                </div>
              </div>
              
              <div className="flex justify-end">
                <button
                  onClick={handleSavePreferences}
                  className="flex items-center space-x-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg text-white transition-colors"
                >
                  <Save className="w-4 h-4" />
                  <span>Save Preferences</span>
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default ProfileSettings;
