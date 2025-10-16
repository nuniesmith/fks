import React from 'react';
import PageContainer from '@layout/PageContainer';

const Performance: React.FC = () => {
	return (
		<PageContainer className="space-y-6">
				<div>
					<h1 className="text-3xl font-bold text-white">Performance</h1>
					<p className="text-white/70">Detailed performance metrics and time-series charts.</p>
				</div>
				<div className="glass-card p-6 text-white/70">Charts coming soon.</div>
		</PageContainer>
	);
};

export default Performance;
