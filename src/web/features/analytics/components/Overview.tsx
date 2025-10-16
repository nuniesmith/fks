import React from 'react';
import PageContainer from '@layout/PageContainer';

const Overview: React.FC = () => {
	return (
		<PageContainer className="space-y-6">
				<div>
					<h1 className="text-3xl font-bold text-white">Analytics Overview</h1>
					<p className="text-white/70">High-level snapshot of performance, risk, and market context.</p>
				</div>

				<div className="grid grid-cols-1 md:grid-cols-3 gap-4">
					<div className="glass-card p-5">
						<div className="text-white/60 text-sm">YTD Return</div>
						<div className="text-green-300 text-2xl font-bold">+12.4%</div>
					</div>
					<div className="glass-card p-5">
						<div className="text-white/60 text-sm">Max Drawdown</div>
						<div className="text-red-300 text-2xl font-bold">-5.8%</div>
					</div>
					<div className="glass-card p-5">
						<div className="text-white/60 text-sm">Sharpe Ratio</div>
						<div className="text-yellow-300 text-2xl font-bold">1.62</div>
					</div>
				</div>
		</PageContainer>
	);
};

export default Overview;
