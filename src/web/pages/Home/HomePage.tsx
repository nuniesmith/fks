import StatTile from '@stats/StatTile';
import { Target, TrendingUp, DollarSign, Shield, Settings, BarChart } from 'lucide-react';
import SectionHeader from '@layout/SectionHeader';
import LazyReveal from '../../components/LazyReveal';
import React from 'react';
import { useUISettings } from '../../context/UISettingsContext';
import { Link } from 'react-router-dom';

import { APP_SECTIONS } from '../../types/layout';
import { TRADING_MILESTONES } from '../../types/milestones';

interface TradingAccount { id: string; name: string; type: 'prop_firm' | 'tfsa' | 'rrsp' | 'personal' | string; currentBalance: number; status: 'active' | 'inactive' | string; }
interface FinancialSnapshot { totalNetWorth: number; monthlyIncome: number; monthlyExpenses: number; expenseCoverage: number; taxOptimizationScore: number; canadianTaxSavings: number; }
interface UserProgress {
	totalXP: number;
	currentTitle: string;
	titleColor: string;
	titleIcon: string;
	completedMilestones: string[];
	accounts: TradingAccount[];
	financialSnapshot: FinancialSnapshot;
}
interface HomePageProps { userProgress?: UserProgress; }

const HomePage: React.FC<HomePageProps> = ({ userProgress }) => {
	const mockProgress = {
		totalXP: 2500,
		currentTitle: 'Tax-Smart Apprentice',
		titleColor: 'blue',
		titleIcon: '🇨🇦',
		completedMilestones: ['first_prop_account'],
		accounts: [
			{ id: '1', name: 'FTMO Account 1', type: 'prop_firm', currentBalance: 12500, status: 'active' },
			{ id: '2', name: 'TFSA - Questrade', type: 'tfsa', currentBalance: 8900, status: 'active' }
		],
		financialSnapshot: {
			totalNetWorth: 45000,
			monthlyIncome: 3200,
			monthlyExpenses: 2800,
			expenseCoverage: 65,
			taxOptimizationScore: 78,
			canadianTaxSavings: 2400
		}
	};
	const progress: UserProgress = userProgress || mockProgress;
	const { density, toggleDensity } = useUISettings();
	const nextMilestone = TRADING_MILESTONES.find(m => !progress.completedMilestones.includes(m.id) && m.priority === 'high');
	const quickStats = [
		{ title: 'Total XP', value: progress.totalXP.toLocaleString(), icon: TrendingUp },
		{ title: 'Expense Coverage', value: `${progress.financialSnapshot.expenseCoverage}%`, icon: DollarSign },
		{ title: 'Tax Savings', value: `$${progress.financialSnapshot.canadianTaxSavings.toLocaleString()}`, icon: Shield },
		{ title: 'Active Accounts', value: progress.accounts.filter((a) => a.status === 'active').length, icon: BarChart }
	];
	const activeTradingSections = APP_SECTIONS.filter(section => ['trading', 'strategy', 'accounts'].includes(section.id));
	const longTermSections = [
		{ id: 'taxes', title: 'Tax Optimization', description: 'Maximize your Canadian tax benefits', icon: '🇨🇦' },
		{ id: 'portfolio', title: 'Long-term Portfolio', description: 'TFSA, RRSP & investment accounts', icon: '📈' },
		{ id: 'calendar', title: 'Dev Calendar', description: 'Schedule & track development work', icon: '📅' }
	];
	return (
			<div className="p-6">
				<div className="max-w-7xl mx-auto pb-10">
				<div className="mb-6 md:mb-8">
						<div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-6">
						<div>
							<h1 className="font-bold text-white mb-2 text-[clamp(1.9rem,3.5vw,2.5rem)] leading-tight">Welcome to FKS Trading Platform</h1>
							<div className="flex items-center gap-3">
								<span className="text-2xl">{progress.titleIcon}</span>
								<span className="text-xl font-semibold text-blue-400">{progress.currentTitle}</span>
								<span className="text-white/60">•</span>
								<span className="text-white/80">{progress.totalXP.toLocaleString()} XP</span>
							</div>
						</div>
						<div className="flex items-center gap-4">
							<div className="text-right text-white/70 hidden xs:block">
								<p className="text-lg font-mono">{new Date().toLocaleTimeString('en-CA',{hour:'2-digit',minute:'2-digit',timeZone:'America/Toronto'})} EST</p>
								<p className="text-sm">{new Date().toLocaleDateString('en-CA',{weekday:'short',month:'short',day:'numeric'})}</p>
							</div>
							<button title="Preferences" className="p-2 rounded-lg bg-white/10 hover:bg-white/20 transition-colors border border-white/20">
								<Settings className="h-5 w-5 text-white/80" />
							</button>
							<button onClick={toggleDensity} aria-label="Toggle density" title="Toggle density (Shift+D)" className="px-3 py-1 rounded-lg bg-white/10 hover:bg-white/20 text-xs border border-white/20 font-medium tracking-wide">
								{density === 'compact' ? 'Comfort' : 'Compact'}
							</button>
						</div>
					</div>
				</div>
				<div className="stats-grid mb-8">
					{quickStats.map((stat, i) => (
						<StatTile key={i} label={stat.title} value={stat.value} icon={<stat.icon className="h-5 w-5 md:h-6 md:w-6" />} className="min-h-[110px]" />
					))}
				</div>
				<div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
					<div className="glass-card p-6">
						<SectionHeader icon={<Target className="h-6 w-6 text-blue-400" />} title="Next Milestone" />
						{nextMilestone ? (
							<div>
								<h4 className="font-semibold text-white mb-2">{nextMilestone.title}</h4>
								<p className="text-white/80 mb-4">{nextMilestone.description}</p>
								<div className="flex items-center justify-between">
									<span className="text-sm text-white/70">Progress: {nextMilestone.current}/{nextMilestone.target} {nextMilestone.unit}</span>
									<span className="px-3 py-1 bg-blue-500/20 text-blue-300 rounded-full text-sm font-medium border border-blue-500/30">+{nextMilestone.xpReward} XP</span>
								</div>
								<div className="mt-3 bg-white/20 rounded-full h-2">
									<div className="bg-blue-400 h-2 rounded-full transition-all" style={{width:`${(nextMilestone.current/ nextMilestone.target)*100}%`}} />
								</div>
							</div>) : <p className="text-white/70">No active milestones.</p>}
					</div>
					<div className="glass-card p-6">
						<SectionHeader icon={<DollarSign className="h-6 w-6 text-green-400" />} title="Financial Overview" />
						<div className="space-y-4">
							<div className="flex justify-between"><span className="text-white/80">Monthly Income</span><span className="font-semibold text-green-400">${progress.financialSnapshot.monthlyIncome.toLocaleString()} CAD</span></div>
							<div className="flex justify-between"><span className="text-white/80">Monthly Expenses</span><span className="font-semibold text-red-400">${progress.financialSnapshot.monthlyExpenses.toLocaleString()} CAD</span></div>
							<div className="flex justify-between"><span className="text-white/80">Net Worth</span><span className="font-semibold text-blue-400">${progress.financialSnapshot.totalNetWorth.toLocaleString()} CAD</span></div>
							<div className="mt-4 p-3 bg-blue-500/20 rounded-lg border border-blue-500/30">
								<div className="flex justify-between items-center"><span className="text-blue-300 font-medium">Tax Optimization Score</span><span className="text-blue-200 font-bold">{progress.financialSnapshot.taxOptimizationScore}/100</span></div>
								<div className="mt-2 bg-blue-400/30 rounded-full h-2"><div className="bg-blue-400 h-2 rounded-full" style={{width:`${progress.financialSnapshot.taxOptimizationScore}%`}} /></div>
							</div>
						</div>
					</div>
				</div>
				<LazyReveal className="glass-card p-6 mb-6" placeholderHeight={220} skeleton={<div className="skeleton-pulse h-[220px]"></div>} performanceLabel="active-trading">
					<SectionHeader title="Active Trading" dense />
					<p className="text-white/60 text-sm mb-6">Real-time trading & money-making strategies</p>
					<div className="grid grid-cols-1 md:grid-cols-3 gap-4">
						{activeTradingSections.map(section => (
							<Link key={section.id} to={section.path} className="flex flex-col items-center p-4 rounded-lg border border-white/20 bg-white/10 hover:border-blue-400/50 hover:bg-blue-500/20 transition-all">
								<span className="text-3xl mb-2">{section.icon}</span>
								<span className="font-medium text-white text-center">{section.title}</span>
								<span className="text-sm text-white/60 text-center mt-1">{section.description}</span>
							</Link>
						))}
					</div>
				</LazyReveal>
				<LazyReveal className="glass-card p-6 mb-8" placeholderHeight={240} skeleton={<div className="skeleton-pulse h-[240px]"></div>} performanceLabel="long-term">
					<SectionHeader title="Long-term & Organization" dense />
					<p className="text-white/60 text-sm mb-6">Tax optimization, long-term investments & development planning</p>
					<div className="grid grid-cols-1 md:grid-cols-3 gap-4">
						{longTermSections.map(section => (
							<Link key={section.id} to={section.id === 'taxes' ? '/tax' : section.id === 'portfolio' ? '/portfolio' : '/calendar/dev'} className="flex flex-col items-center p-4 rounded-lg border border-white/20 bg-white/10 hover:border-green-400/50 hover:bg-green-500/20 transition-all">
								<span className="text-3xl mb-2">{section.icon}</span>
								<span className="font-medium text-white text-center">{section.title}</span>
								<span className="text-sm text-white/60 text-center mt-1">{section.description}</span>
							</Link>
						))}
					</div>
				</LazyReveal>
				<LazyReveal className="glass-card p-6" placeholderHeight={260} skeleton={<div className="skeleton-pulse h-[260px]"></div>} performanceLabel="active-accounts">
					<SectionHeader icon={<BarChart className="h-6 w-6 text-orange-400" />} title="Active Accounts" className="mb-6" />
					<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
						{progress.accounts.filter(a => a.status==='active').map((account) => (
							<div key={account.id} className="p-4 border border-white/20 bg-white/10 rounded-lg">
								<div className="flex items-center justify-between mb-2">
									<h4 className="font-medium text-white">{account.name}</h4>
									<span className={`px-2 py-1 rounded-full text-xs font-medium ${account.type==='prop_firm' ? 'bg-blue-500/30 text-blue-300 border border-blue-500/50' : account.type==='tfsa' ? 'bg-green-500/30 text-green-300 border border-green-500/50' : 'bg-gray-500/30 text-gray-300 border border-gray-500/50'}`}>{account.type.toUpperCase().replace('_',' ')}</span>
								</div>
								<p className="text-2xl font-bold text-white">${account.currentBalance.toLocaleString()} CAD</p>
								<p className="text-sm text-white/60 capitalize">Status: {account.status}</p>
							</div>
						))}
					</div>
				</LazyReveal>
			</div>
		</div>
	);
};

export default HomePage;
