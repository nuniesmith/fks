import { Bitcoin, Wallet, TrendingUp, TrendingDown, Plus, Edit3, Trash2, Eye, EyeOff, RefreshCw, AlertTriangle, Shield, PieChart } from 'lucide-react';
import React, { useState } from 'react';

import type { HardwareWallet, CryptoPortfolio } from '../../types';

interface CryptoTrackingProps {
  cryptoPortfolio: CryptoPortfolio;
  onUpdateCryptoPortfolio: (portfolio: CryptoPortfolio) => void;
}

const CryptoTracking: React.FC<CryptoTrackingProps> = ({ 
  cryptoPortfolio, 
  onUpdateCryptoPortfolio
}) => {
  const [activeTab, setActiveTab] = useState<'portfolio' | 'wallets' | 'allocation'>('portfolio');
  const [showWalletForm, setShowWalletForm] = useState(false);
  const [editingWallet, setEditingWallet] = useState<HardwareWallet | null>(null);
  const [showPrivateKeys, setShowPrivateKeys] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);

  const formatCurrency = (amount: number, currency: 'CAD' | 'USD' = 'CAD') => {
    return new Intl.NumberFormat(currency === 'CAD' ? 'en-CA' : 'en-US', {
      style: 'currency',
      currency: currency
    }).format(amount);
  };

  const formatCrypto = (amount: number, symbol: string) => {
    return `${amount.toFixed(8)} ${symbol.toUpperCase()}`;
  };

  // Mock crypto price fetching (replace with real API)
  const refreshPrices = async () => {
    setIsRefreshing(true);
    // Simulate API call
    await new Promise(resolve => setTimeout(resolve, 2000));
    
    // Mock updated holdings with new prices
    const updatedHoldings = cryptoPortfolio.holdings.map(holding => ({
      ...holding,
      priceCAD: holding.priceCAD * (0.95 + Math.random() * 0.1), // Random price movement
      priceUSD: holding.priceUSD * (0.95 + Math.random() * 0.1),
      change24h: -10 + Math.random() * 20, // -10% to +10%
      valueCAD: holding.balance * holding.priceCAD,
      valueUSD: holding.balance * holding.priceUSD,
      lastUpdated: new Date().toISOString()
    }));

    const updatedPortfolio = {
      ...cryptoPortfolio,
      holdings: updatedHoldings,
      totalValueCAD: updatedHoldings.reduce((sum, h) => sum + h.valueCAD, 0),
      totalValueUSD: updatedHoldings.reduce((sum, h) => sum + h.valueUSD, 0)
    };

    onUpdateCryptoPortfolio(updatedPortfolio);
    setIsRefreshing(false);
  };

  const WalletForm: React.FC<{
    wallet?: HardwareWallet;
    onSave: (wallet: Omit<HardwareWallet, 'id' | 'createdAt' | 'lastUpdated'>) => void;
    onCancel: () => void;
  }> = ({ wallet, onSave, onCancel }) => {
    const [formData, setFormData] = useState({
      name: wallet?.name || '',
      walletType: wallet?.walletType || 'ledger' as const,
      publicKey: wallet?.publicKey || '',
      description: wallet?.description || '',
      isActive: wallet?.isActive !== false
    });

    const handleSubmit = (e: React.FormEvent) => {
      e.preventDefault();
      onSave(formData);
    };

    return (
      <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
        <div className="bg-white rounded-lg max-w-2xl w-full">
          <div className="p-6 border-b">
            <h3 className="text-lg font-semibold flex items-center">
              <Shield className="mr-2 h-5 w-5" />
              {wallet ? 'Edit Hardware Wallet' : 'Add Hardware Wallet'}
            </h3>
            <p className="text-gray-600 text-sm mt-1">
              Track your Bitcoin and crypto holdings on hardware wallets
            </p>
          </div>

          <form onSubmit={handleSubmit} className="p-6 space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Wallet Name *
                </label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                  placeholder="e.g., Main Bitcoin Wallet"
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Wallet Type *
                </label>
                <select
                  value={formData.walletType}
                  onChange={(e) => setFormData({ ...formData, walletType: e.target.value as any })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                >
                  <option value="ledger">Ledger</option>
                  <option value="trezor">Trezor</option>
                  <option value="coldcard">Coldcard</option>
                  <option value="bitbox">BitBox</option>
                  <option value="other">Other</option>
                </select>
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Public Key / Address *
              </label>
              <textarea
                value={formData.publicKey}
                onChange={(e) => setFormData({ ...formData, publicKey: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                rows={3}
                placeholder="Enter public key or Bitcoin address (xpub, ypub, zpub, or standard address)"
                required
              />
              <p className="text-xs text-gray-500 mt-1">
                Only enter public keys or addresses. Never enter private keys or seed phrases.
              </p>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Description
              </label>
              <input
                type="text"
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                placeholder="Optional description"
              />
            </div>

            <div className="flex items-center space-x-3">
              <input
                type="checkbox"
                id="isActive"
                checked={formData.isActive}
                onChange={(e) => setFormData({ ...formData, isActive: e.target.checked })}
                className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
              />
              <label htmlFor="isActive" className="text-sm font-medium text-gray-700">
                Active Wallet (include in portfolio calculations)
              </label>
            </div>

            <div className="flex justify-end space-x-3 pt-4 border-t">
              <button
                type="button"
                onClick={onCancel}
                className="px-4 py-2 text-gray-600 bg-gray-100 rounded-lg hover:bg-gray-200 transition-colors"
              >
                Cancel
              </button>
              <button
                type="submit"
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors flex items-center space-x-2"
              >
                <Shield className="h-4 w-4" />
                <span>{wallet ? 'Update Wallet' : 'Add Wallet'}</span>
              </button>
            </div>
          </form>
        </div>
      </div>
    );
  };

  const renderPortfolioOverview = () => (
    <div className="space-y-6">
      {/* Portfolio Summary */}
      <div className="bg-gradient-to-r from-orange-500 to-yellow-500 rounded-lg p-6 text-white">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-lg font-semibold flex items-center">
              <Bitcoin className="mr-2 h-6 w-6" />
              Bitcoin & Crypto Portfolio
            </h3>
            <p className="text-orange-100 text-sm">Hardware wallet tracking for long-term investments</p>
          </div>
          <button
            onClick={refreshPrices}
            disabled={isRefreshing}
            className="p-2 bg-white/20 rounded-lg hover:bg-white/30 transition-colors disabled:opacity-50"
          >
            <RefreshCw className={`h-5 w-5 ${isRefreshing ? 'animate-spin' : ''}`} />
          </button>
        </div>
        
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mt-6">
          <div>
            <p className="text-orange-200 text-sm">Total Value (CAD)</p>
            <p className="text-2xl font-bold">{formatCurrency(cryptoPortfolio.totalValueCAD)}</p>
          </div>
          <div>
            <p className="text-orange-200 text-sm">Total Value (USD)</p>
            <p className="text-2xl font-bold">{formatCurrency(cryptoPortfolio.totalValueUSD, 'USD')}</p>
          </div>
          <div>
            <p className="text-orange-200 text-sm">Monthly Allocation</p>
            <p className="text-2xl font-bold">{formatCurrency(cryptoPortfolio.monthlyAllocation)}</p>
            <p className="text-orange-200 text-xs">
              {cryptoPortfolio.allocationTarget}% of income target
            </p>
          </div>
        </div>
      </div>

      {/* Holdings List */}
      <div className="bg-white rounded-lg border">
        <div className="p-4 border-b">
          <h4 className="font-semibold">Current Holdings</h4>
        </div>
        <div className="divide-y">
          {cryptoPortfolio.holdings.map(holding => (
            <div key={holding.id} className="p-4 flex items-center justify-between">
              <div className="flex items-center space-x-4">
                <div className="w-10 h-10 bg-orange-100 rounded-full flex items-center justify-center">
                  <Bitcoin className="h-6 w-6 text-orange-600" />
                </div>
                <div>
                  <h5 className="font-medium">{holding.name}</h5>
                  <p className="text-sm text-gray-600">
                    {formatCrypto(holding.balance, holding.symbol)}
                  </p>
                </div>
              </div>
              
              <div className="text-right">
                <p className="font-medium">{formatCurrency(holding.valueCAD)}</p>
                <p className="text-sm text-gray-600">{formatCurrency(holding.valueUSD, 'USD')}</p>
                <div className={`text-sm flex items-center ${
                  holding.change24h >= 0 ? 'text-green-600' : 'text-red-600'
                }`}>
                  {holding.change24h >= 0 ? <TrendingUp className="h-3 w-3 mr-1" /> : <TrendingDown className="h-3 w-3 mr-1" />}
                  {Math.abs(holding.change24h).toFixed(2)}%
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Allocation Strategy */}
      <div className="bg-white rounded-lg border p-6">
        <h4 className="font-semibold mb-4 flex items-center">
          <PieChart className="mr-2 h-5 w-5" />
          Long-term Allocation Strategy
        </h4>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <div className="space-y-4">
              <div className="flex justify-between items-center">
                <span className="text-gray-600">Target Allocation</span>
                <span className="font-medium">{cryptoPortfolio.allocationTarget}% of trading profits</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-gray-600">Monthly Target</span>
                <span className="font-medium">{formatCurrency(cryptoPortfolio.monthlyAllocation)}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-gray-600">Last Rebalanced</span>
                <span className="font-medium">
                  {new Date(cryptoPortfolio.lastRebalanced).toLocaleDateString()}
                </span>
              </div>
            </div>
          </div>
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
            <h5 className="font-medium text-blue-900 mb-2">Strategy Notes</h5>
            <ul className="text-sm text-blue-800 space-y-1">
              <li>• Bitcoin for long-term store of value</li>
              <li>• DCA strategy from trading profits</li>
              <li>• Hardware wallet cold storage</li>
              <li>• Rebalance monthly or on major moves</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );

  const renderWalletManagement = () => (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h3 className="text-lg font-semibold">Hardware Wallets</h3>
          <p className="text-gray-600">Manage your hardware wallet public keys for tracking</p>
        </div>
        <div className="flex space-x-2">
          <button
            onClick={() => setShowPrivateKeys(!showPrivateKeys)}
            className="px-3 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-colors flex items-center space-x-2"
          >
            {showPrivateKeys ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
            <span>{showPrivateKeys ? 'Hide' : 'Show'} Keys</span>
          </button>
          <button
            onClick={() => setShowWalletForm(true)}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors flex items-center space-x-2"
          >
            <Plus className="h-4 w-4" />
            <span>Add Wallet</span>
          </button>
        </div>
      </div>

      {/* Security Warning */}
      <div className="bg-amber-50 border border-amber-200 rounded-lg p-4">
        <div className="flex items-start space-x-3">
          <AlertTriangle className="h-5 w-5 text-amber-600 mt-0.5" />
          <div>
            <h4 className="font-medium text-amber-900">Security Notice</h4>
            <p className="text-sm text-amber-800 mt-1">
              Only store public keys or addresses here. Never enter private keys, seed phrases, or sensitive information.
              This tool is for monitoring balances only.
            </p>
          </div>
        </div>
      </div>

      {/* Wallets Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {cryptoPortfolio.wallets.map(wallet => (
          <div key={wallet.id} className="bg-white rounded-lg border p-6">
            <div className="flex justify-between items-start mb-4">
              <div className="flex items-center space-x-3">
                <div className="w-10 h-10 bg-gray-100 rounded-lg flex items-center justify-center">
                  <Wallet className="h-6 w-6 text-gray-600" />
                </div>
                <div>
                  <h4 className="font-medium">{wallet.name}</h4>
                  <p className="text-sm text-gray-600 capitalize">{wallet.walletType}</p>
                </div>
              </div>
              <div className="flex space-x-1">
                <button
                  onClick={() => {
                    setEditingWallet(wallet);
                    setShowWalletForm(true);
                  }}
                  className="p-1 text-gray-500 hover:text-blue-600 transition-colors"
                >
                  <Edit3 className="h-4 w-4" />
                </button>
                <button className="p-1 text-gray-500 hover:text-red-600 transition-colors">
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            </div>

            <div className="space-y-3">
              <div>
                <label className="text-xs text-gray-500">Public Key / Address</label>
                <p className="text-sm font-mono bg-gray-50 p-2 rounded border">
                  {showPrivateKeys 
                    ? wallet.publicKey
                    : `${wallet.publicKey.slice(0, 8)}...${wallet.publicKey.slice(-8)}`
                  }
                </p>
              </div>
              
              {wallet.description && (
                <div>
                  <label className="text-xs text-gray-500">Description</label>
                  <p className="text-sm text-gray-800">{wallet.description}</p>
                </div>
              )}

              <div className="flex items-center justify-between text-sm">
                <span className="text-gray-600">Status</span>
                <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                  wallet.isActive ? 'text-green-600 bg-green-100' : 'text-gray-600 bg-gray-100'
                }`}>
                  {wallet.isActive ? 'Active' : 'Inactive'}
                </span>
              </div>

              <div className="flex items-center justify-between text-sm">
                <span className="text-gray-600">Last Updated</span>
                <span className="font-medium">
                  {new Date(wallet.lastUpdated).toLocaleDateString()}
                </span>
              </div>
            </div>
          </div>
        ))}
      </div>

      {cryptoPortfolio.wallets.length === 0 && (
        <div className="text-center py-12 bg-white rounded-lg border">
          <Wallet className="h-12 w-12 text-gray-400 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-900 mb-2">No Hardware Wallets</h3>
          <p className="text-gray-600 mb-6">
            Add your hardware wallet public keys to track Bitcoin and crypto holdings
          </p>
          <button
            onClick={() => setShowWalletForm(true)}
            className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
          >
            Add First Wallet
          </button>
        </div>
      )}
    </div>
  );

  const handleSaveWallet = (walletData: Omit<HardwareWallet, 'id' | 'createdAt' | 'lastUpdated'>) => {
    const now = new Date().toISOString();
    
    if (editingWallet) {
      // Update existing wallet
      const updatedWallets = cryptoPortfolio.wallets.map(wallet => 
        wallet.id === editingWallet.id 
          ? { ...wallet, ...walletData, lastUpdated: now }
          : wallet
      );
      onUpdateCryptoPortfolio({
        ...cryptoPortfolio,
        wallets: updatedWallets
      });
    } else {
      // Create new wallet
      const newWallet: HardwareWallet = {
        ...walletData,
        id: Date.now().toString(),
        createdAt: now,
        lastUpdated: now
      };
      onUpdateCryptoPortfolio({
        ...cryptoPortfolio,
        wallets: [...cryptoPortfolio.wallets, newWallet]
      });
    }
    
    setShowWalletForm(false);
    setEditingWallet(null);
  };

  const tabConfig = [
    { id: 'portfolio', label: 'Portfolio', icon: Bitcoin },
    { id: 'wallets', label: 'Hardware Wallets', icon: Wallet },
    { id: 'allocation', label: 'Allocation Settings', icon: PieChart }
  ];

  return (
    <div className="space-y-6">
      {/* Tab Navigation */}
      <div className="border-b border-gray-200">
        <nav className="-mb-px flex space-x-8">
          {tabConfig.map((tab) => {
            const Icon = tab.icon;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as any)}
                className={`py-2 px-1 border-b-2 font-medium text-sm flex items-center ${
                  activeTab === tab.id
                    ? 'border-orange-500 text-orange-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                <Icon className="mr-2 h-4 w-4" />
                {tab.label}
              </button>
            );
          })}
        </nav>
      </div>

      {/* Tab Content */}
      {activeTab === 'portfolio' && renderPortfolioOverview()}
      {activeTab === 'wallets' && renderWalletManagement()}
      {activeTab === 'allocation' && (
        <div className="bg-white rounded-lg border p-6">
          <h3 className="text-lg font-semibold mb-4">Coming Soon: Allocation Settings</h3>
          <p className="text-gray-600">Configure automatic allocation rules and rebalancing strategies</p>
        </div>
      )}

      {/* Wallet Form Modal */}
      {showWalletForm && (
        <WalletForm
          wallet={editingWallet || undefined}
          onSave={handleSaveWallet}
          onCancel={() => {
            setShowWalletForm(false);
            setEditingWallet(null);
          }}
        />
      )}
    </div>
  );
};

export default CryptoTracking;
