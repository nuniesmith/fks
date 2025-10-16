import React from 'react';
import PageContainer from '@layout/PageContainer';

const Risk: React.FC = () => {
	return (
		<PageContainer className="space-y-6">
				<div>
					<h1 className="text-3xl font-bold text-white">Risk</h1>
					<p className="text-white/70">Risk assessment, VaR/ES, exposure breakdown, and alerts.</p>
				</div>
				<div className="glass-card p-6 text-white/70">Risk dashboards coming soon.</div>
		</PageContainer>
	);
};

export default Risk;
