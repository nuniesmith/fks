import React, { useCallback } from 'react';

import { usePersistentLogs } from '../../hooks/usePersistentLogs';
import { useServiceMonitoring } from '../../hooks/useServiceMonitoring';


import WebBuildControls from './WebBuildControls';

import { LogViewer, ArchitectureSummary } from './index';

import type { LogEntry } from '../../types/projectManager';

const FKSProjectManager: React.FC = () => {
	const { systemHealth, isLoading, refreshServices } = useServiceMonitoring();
	const { logs, add, append, clear } = usePersistentLogs();

	const pushLog = useCallback((message: string, type: LogEntry['type'] = 'info') => {
		add(message, type);
	}, [add]);

	const handleLogAppend = (entry: LogEntry) => append(entry);

	return (
		<div className="min-h-screen pt-4 pb-12">
			<div className="max-w-7xl mx-auto px-4 space-y-8">
				<header className="flex flex-col gap-2">
					<h1 className="text-3xl font-bold gradient-text">FKS Project Manager</h1>
					<p className="text-white/70 text-sm max-w-2xl">Unified management surface for builds, packaging, template scaffolding, and architecture health across the FKS platform.</p>
				</header>
				<div className="grid md:grid-cols-3 gap-6 items-start">
					<div className="md:col-span-2 space-y-6">
						<ArchitectureSummary systemHealth={systemHealth} isLoading={isLoading} onRefresh={refreshServices} />
						<WebBuildControls onLog={pushLog} />
						<div className="glass-card p-6">
							<h3 className="text-lg font-semibold mb-4">Notes</h3>
							<ul className="list-disc list-inside space-y-1 text-sm text-white/70">
								<li>Architecture snapshot mirrors live service health (polls every 30s).</li>
								<li>Web build action is a stub; integrate with CI or internal build pipeline endpoint.</li>
								<li>Future: code generation for new feature modules & auto-wiring based on detected gaps.</li>
							</ul>
						</div>
					</div>
					<div className="flex flex-col gap-6">
						<LogViewer logs={logs} onClear={clear} />
					</div>
				</div>
			</div>
		</div>
	);
};

export default FKSProjectManager;

