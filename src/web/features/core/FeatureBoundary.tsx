import React from 'react';
interface ErrorBoundaryProps { fallback?: React.ReactNode; children?: React.ReactNode }
class ErrorBoundary extends React.Component<ErrorBoundaryProps, { hasError: boolean; error?: any }> {
	constructor(props: ErrorBoundaryProps){ super(props); this.state={ hasError:false }; }
	static getDerivedStateFromError(error:any){ return { hasError:true, error }; }
	componentDidCatch(error:any, info:any){ if(import.meta?.env?.DEV) console.error('FeatureBoundary error', error, info); }
	render(){ if(this.state.hasError){ return this.props.fallback || (<div className="min-h-[200px] flex flex-col items-center justify-center text-center glass-card p-6"><h2 className="text-xl font-semibold text-red-400 mb-2">Something went wrong</h2><p className="text-white/70 text-sm mb-4">The feature failed to load. Try refreshing.</p><button onClick={()=>window.location.reload()} className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded">Refresh</button></div>); } return this.props.children as any; }
}
export const FeatureBoundary: React.FC<{ children: React.ReactNode; fallbackSpinner?: boolean }> = ({ children, fallbackSpinner }) => (<ErrorBoundary fallback={fallbackSpinner ? <div className="flex items-center justify-center min-h-[180px]"><div className="animate-spin rounded-full h-10 w-10 border-b-2 border-white/30 border-t-white" /></div>:undefined}><React.Suspense fallback={<div className="flex items-center justify-center min-h-[180px]"><div className="animate-spin rounded-full h-10 w-10 border-b-2 border-white/30 border-t-white" /></div>}>{children}</React.Suspense></ErrorBoundary>);
export const withFeatureBoundary = <P,>(Comp: React.ComponentType<P>) => (props: P) => (<FeatureBoundary><Comp {...props} /></FeatureBoundary>);
export default FeatureBoundary;
