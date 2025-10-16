import {
	TrendingUp,
	TrendingDown,
	DollarSign,
	Target,
	RefreshCw,
	Filter,
	BarChart3
} from 'lucide-react';
import React, { useState, useEffect } from 'react';

import type { AccountType} from '@/types';

import { useTradingEnv } from '@/context/TradingEnvContext';
import { ACCOUNT_TYPES } from '@/types';

interface PortfolioAsset { symbol: string; name: string; quantity: number; currentPrice: number; costBasis: number; marketValue: number; pnl: number; pnlPercentage: number; allocation: number; sector: string; }
interface PortfolioMetrics { totalValue: number; totalPnL: number; totalPnLPercentage: number; dayChange: number; dayChangePercentage: number; sharpeRatio: number; maxDrawdown: number; }
interface AccountSummary { id: string; name: string; type: AccountType; balance: number; equity: number; pnl: number; pnlPercentage: number; riskLevel: 'low' | 'medium' | 'high'; }

const PortfolioManager: React.FC = () => {
	const { environment, isLive } = useTradingEnv();
	const [selectedTimeframe, setSelectedTimeframe] = useState<'1D' | '1W' | '1M' | '3M' | '1Y'>('1D');
	const [selectedAccountType, setSelectedAccountType] = useState<'all' | 'prop-firm' | 'retirement' | 'tax-free' | 'taxable'>('all');
	const [assets, setAssets] = useState<PortfolioAsset[]>([]);
	const [metrics, setMetrics] = useState<PortfolioMetrics>({ totalValue: 0, totalPnL: 0, totalPnLPercentage: 0, dayChange: 0, dayChangePercentage: 0, sharpeRatio: 0, maxDrawdown: 0 });
	const [accounts, setAccounts] = useState<AccountSummary[]>([]);

	useEffect(() => {
		// Mock data (placeholder until integrated with backend)
		const mockAssets: PortfolioAsset[] = [
			{ symbol: 'BTC', name: 'Bitcoin', quantity: 0.75, currentPrice: 43620, costBasis: 41500, marketValue: 32715, pnl: 1590, pnlPercentage: 5.11, allocation: 45.2, sector: 'Cryptocurrency' },
			{ symbol: 'ETH', name: 'Ethereum', quantity: 12.5, currentPrice: 2655, costBasis: 2480, marketValue: 33187.5, pnl: 2187.5, pnlPercentage: 7.06, allocation: 32.8, sector: 'Cryptocurrency' },
			{ symbol: 'TSLA', name: 'Tesla Inc', quantity: 25, currentPrice: 248.50, costBasis: 235.00, marketValue: 6212.5, pnl: 337.5, pnlPercentage: 5.74, allocation: 15.3, sector: 'Technology' },
			{ symbol: 'AAPL', name: 'Apple Inc', quantity: 15, currentPrice: 192.35, costBasis: 185.20, marketValue: 2885.25, pnl: 107.25, pnlPercentage: 3.86, allocation: 6.7, sector: 'Technology' }
		];
		const mockMetrics: PortfolioMetrics = { totalValue: 75000, totalPnL: 4222.25, totalPnLPercentage: 5.96, dayChange: 892.50, dayChangePercentage: 1.20, sharpeRatio: 1.75, maxDrawdown: -8.5 };
		const mockAccounts: AccountSummary[] = [
			{ id: 'prop-001', name: 'Apex Prop Trading', type: 'prop-firm', balance: 50000, equity: 52500, pnl: 2500, pnlPercentage: 5.0, riskLevel: 'medium' },
			{ id: 'rrsp-001', name: 'Questrade RRSP', type: 'rrsp', balance: 75000, equity: 78420, pnl: 3420, pnlPercentage: 4.56, riskLevel: 'low' },
			{ id: 'tfsa-001', name: 'Questrade TFSA', type: 'tfsa', balance: 45000, equity: 47200, pnl: 2200, pnlPercentage: 4.89, riskLevel: 'low' },
			{ id: 'margin-001', name: 'Personal Margin Account', type: 'personal-margin', balance: 25000, equity: 26722.25, pnl: 1722.25, pnlPercentage: 6.89, riskLevel: 'medium' },
			{ id: 'fx-cfd-001', name: 'FX & CFD Trading', type: 'fx-cfd', balance: 15000, equity: 15750, pnl: 750, pnlPercentage: 5.0, riskLevel: 'high' }
		];
		setAssets(mockAssets); setMetrics(mockMetrics); setAccounts(mockAccounts);
	}, []);

	const filteredAccounts = selectedAccountType === 'all' ? accounts : accounts.filter(account => {
		if (selectedAccountType === 'prop-firm') return account.type === 'prop-firm';
		if (selectedAccountType === 'retirement') return ACCOUNT_TYPES[account.type].category === 'retirement';
		if (selectedAccountType === 'tax-free') return ACCOUNT_TYPES[account.type].category === 'tax-free';
		if (selectedAccountType === 'taxable') return ACCOUNT_TYPES[account.type].category === 'taxable';
		return false; });

	const getSectorAllocation = () => {
		const sectorMap = new Map<string, number>();
		assets.forEach(asset => { sectorMap.set(asset.sector, (sectorMap.get(asset.sector) || 0) + asset.allocation); });
		return Array.from(sectorMap.entries()).map(([sector, allocation]) => ({ sector, allocation: Number(allocation.toFixed(1)) }));
	};

	return (
		<div className="min-h-screen bg-gray-900 text-white p-6">
			<div className="flex justify-between items-center mb-8">
				<div>
					<h1 className="text-3xl font-bold text-white">Portfolio Manager</h1>
					<p className="text-gray-400 mt-2">Monitor and manage your trading portfolio across all accounts</p>
					<div className="flex items-center space-x-2 mt-3">
						<span className={`px-2 py-1 rounded text-sm font-medium ${ isLive ? 'bg-red-500/20 text-red-400' : 'bg-blue-500/20 text-blue-400' }`}>{environment} Mode</span>
					</div>
				</div>
				<div className="flex items-center space-x-3">
					<button className="flex items-center space-x-2 px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg transition-colors"><RefreshCw className="w-4 h-4" /><span>Refresh</span></button>
					<button className="flex items-center space-x-2 px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg transition-colors"><Filter className="w-4 h-4" /><span>Filter</span></button>
				</div>
			</div>

			<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
				<div className="bg-gray-800 rounded-lg p-6"><div className="flex items-center justify-between"><div><p className="text-sm text-gray-400">Total Value</p><p className="text-2xl font-bold text-white">${metrics.totalValue.toLocaleString()}</p></div><DollarSign className="w-8 h-8 text-green-400" /></div></div>
				<div className="bg-gray-800 rounded-lg p-6"><div className="flex items-center justify-between"><div><p className="text-sm text-gray-400">Total P&L</p><p className={`text-2xl font-bold ${ metrics.totalPnL >= 0 ? 'text-green-400' : 'text-red-400' }`}>{metrics.totalPnL >= 0 ? '+' : ''}${metrics.totalPnL.toFixed(2)}</p><p className={`text-sm ${ metrics.totalPnLPercentage >= 0 ? 'text-green-400' : 'text-red-400' }`}>{metrics.totalPnLPercentage >= 0 ? '+' : ''}{metrics.totalPnLPercentage.toFixed(2)}%</p></div>{metrics.totalPnL >= 0 ? <TrendingUp className="w-8 h-8 text-green-400" /> : <TrendingDown className="w-8 h-8 text-red-400" />}</div></div>
				<div className="bg-gray-800 rounded-lg p-6"><div className="flex items-center justify-between"><div><p className="text-sm text-gray-400">Day Change</p><p className={`text-2xl font-bold ${ metrics.dayChange >= 0 ? 'text-green-400' : 'text-red-400' }`}>{metrics.dayChange >= 0 ? '+' : ''}${metrics.dayChange.toFixed(2)}</p><p className={`text-sm ${ metrics.dayChangePercentage >= 0 ? 'text-green-400' : 'text-red-400' }`}>{metrics.dayChangePercentage >= 0 ? '+' : ''}{metrics.dayChangePercentage.toFixed(2)}%</p></div><BarChart3 className="w-8 h-8 text-blue-400" /></div></div>
				<div className="bg-gray-800 rounded-lg p-6"><div className="flex items-center justify-between"><div><p className="text-sm text-gray-400">Sharpe Ratio</p><p className="text-2xl font-bold text-white">{metrics.sharpeRatio.toFixed(2)}</p><p className="text-sm text-gray-400">Risk Adjusted</p></div><Target className="w-8 h-8 text-purple-400" /></div></div>
			</div>

			<div className="flex items-center space-x-6 mb-6">
				<div className="flex items-center space-x-2"><span className="text-sm text-gray-400">Timeframe:</span><div className="flex space-x-1">{['1D','1W','1M','3M','1Y'].map(period => (<button key={period} onClick={() => setSelectedTimeframe(period as any)} className={`px-3 py-1 rounded text-sm transition-colors ${ selectedTimeframe === period ? 'bg-blue-600 text-white' : 'bg-gray-700 text-gray-300 hover:bg-gray-600'}`}>{period}</button>))}</div></div>
				<div className="flex items-center space-x-2"><span className="text-sm text-gray-400">Account Type:</span><select value={selectedAccountType} onChange={(e) => setSelectedAccountType(e.target.value as any)} className="bg-gray-700 text-white px-3 py-1 rounded border border-gray-600 focus:border-blue-500 focus:outline-none"><option value="all">All Accounts</option><option value="prop-firm">Prop Trading</option><option value="retirement">Retirement (RRSP, LIRA, etc.)</option><option value="tax-free">Tax-Free (TFSA, FHSA)</option><option value="taxable">Taxable Accounts</option></select></div>
			</div>

			<div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
				<div className="lg:col-span-2 bg-gray-800 rounded-lg overflow-hidden">
					<div className="px-6 py-4 border-b border-gray-700"><h2 className="text-xl font-semibold text-white">Portfolio Holdings</h2></div>
					<div className="overflow-x-auto">
						<table className="w-full">
							<thead className="bg-gray-700"><tr><th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase">Asset</th><th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase">Quantity</th><th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase">Price</th><th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase">Market Value</th><th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase">P&L</th><th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase">Allocation</th></tr></thead>
							<tbody className="divide-y divide-gray-700">{assets.map((asset, index) => (<tr key={index} className="hover:bg-gray-700/50"><td className="px-6 py-4 whitespace-nowrap"><div><div className="text-sm font-medium text-white">{asset.symbol}</div><div className="text-sm text-gray-400">{asset.name}</div></div></td><td className="px-6 py-4 whitespace-nowrap text-sm text-white">{asset.quantity}</td><td className="px-6 py-4 whitespace-nowrap text-sm text-white">${asset.currentPrice.toLocaleString()}</td><td className="px-6 py-4 whitespace-nowrap text-sm text-white">${asset.marketValue.toLocaleString()}</td><td className="px-6 py-4 whitespace-nowrap text-sm"><div className={asset.pnl >= 0 ? 'text-green-400' : 'text-red-400'}>{asset.pnl >= 0 ? '+' : ''}${asset.pnl.toFixed(2)}</div><div className={`text-xs ${asset.pnlPercentage >= 0 ? 'text-green-400' : 'text-red-400'}`}>{asset.pnlPercentage >= 0 ? '+' : ''}{asset.pnlPercentage.toFixed(2)}%</div></td><td className="px-6 py-4 whitespace-nowrap text-sm text-white">{asset.allocation.toFixed(1)}%</td></tr>))}</tbody>
						</table>
					</div>
				</div>
				<div className="space-y-6">
					<div className="bg-gray-800 rounded-lg p-6"><h3 className="text-lg font-semibold text-white mb-4">Sector Allocation</h3><div className="space-y-3">{getSectorAllocation().map((item, index) => (<div key={index}><div className="flex justify-between items-center mb-1"><span className="text-sm text-gray-300">{item.sector}</span><span className="text-sm text-white">{item.allocation}%</span></div><div className="w-full bg-gray-700 rounded-full h-2"><div className="bg-blue-500 h-2 rounded-full transition-all duration-300" style={{ width: `${item.allocation}%` }}></div></div></div>))}</div></div>
					<div className="bg-gray-800 rounded-lg p-6"><h3 className="text-lg font-semibold text-white mb-4">Account Summary</h3><div className="space-y-4">{filteredAccounts.map(account => (<div key={account.id} className="border border-gray-700 rounded-lg p-4"><div className="flex justify-between items-start mb-2"><div><h4 className="text-sm font-medium text-white">{account.name}</h4><div className="flex items-center space-x-2"><span className="text-xs text-gray-400">{ACCOUNT_TYPES[account.type].displayName}</span>{ACCOUNT_TYPES[account.type].taxAdvantaged && (<span className="text-xs px-1 py-0.5 bg-green-500/20 text-green-400 rounded">Tax Advantaged</span>)}</div></div><div className={`px-2 py-1 rounded text-xs font-medium ${ account.riskLevel === 'low' ? 'bg-green-500/20 text-green-400' : account.riskLevel === 'medium' ? 'bg-yellow-500/20 text-yellow-400' : 'bg-red-500/20 text-red-400'}`}>{account.riskLevel} risk</div></div><div className="grid grid-cols-2 gap-2 text-sm"><div><span className="text-gray-400">Balance:</span><div className="text-white">${account.balance.toLocaleString()}</div></div><div><span className="text-gray-400">Equity:</span><div className="text-white">${account.equity.toLocaleString()}</div></div><div className="col-span-2"><span className="text-gray-400">P&L:</span><div className={account.pnl >= 0 ? 'text-green-400' : 'text-red-400'}>{account.pnl >= 0 ? '+' : ''}${account.pnl.toFixed(2)} ({account.pnlPercentage >= 0 ? '+' : ''}{account.pnlPercentage.toFixed(2)}%)</div></div></div></div>))}</div></div>
				</div>
			</div>
		</div>
	);
};

export default PortfolioManager;
