import React from 'react';
import { Wand2, X } from 'lucide-react';
import { optimizeStrategy } from '@/services/strategyOptimization';

interface Props { open: boolean; onClose: () => void; code: string; language: 'python' | 'javascript' | 'pinescript'; parameters: Record<string, unknown>; onOptimized: (p: Record<string, unknown>) => void; }

const StrategyOptimizationModal: React.FC<Props> = ({ open, onClose, code, language, parameters, onOptimized }) => {
  const [loading, setLoading] = React.useState(false);
  const [result, setResult] = React.useState<Record<string, unknown> | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  if (!open) return null;
  const run = async () => { setLoading(true); setError(null); try { const r = await optimizeStrategy({ code, language, parameters }); setResult(r.parameters); } catch (e: any) { setError(e?.message || 'Optimization failed'); } finally { setLoading(false); } };
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm" data-testid="optimization-modal">
      <div className="bg-gray-800 rounded-xl p-6 max-w-2xl w-full mx-4">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2 text-white font-semibold"><Wand2 className="w-5 h-5 text-purple-400"/> Parameter Optimization</div>
          <button onClick={onClose} className="text-gray-400 hover:text-white" data-testid="close-opt"><X className="w-5 h-5"/></button>
        </div>
        <div className="space-y-3 text-sm">
          <div className="text-gray-300">Find better parameters automatically (mock).</div>
          <button disabled={loading} onClick={run} className="px-4 py-2 bg-purple-600 hover:bg-purple-700 rounded text-white disabled:bg-gray-600" data-testid="run-opt">{loading ? 'Optimizing…' : 'Run Optimization'}</button>
          {error && <div className="p-2 rounded bg-red-500/20 border border-red-500/40 text-red-300">{error}</div>}
          {result && (
            <div className="bg-gray-900 rounded-lg p-3">
              <div className="text-gray-400 mb-2">Suggested Parameters</div>
              <pre className="text-xs text-gray-200 overflow-x-auto" data-testid="opt-result">{JSON.stringify(result, null, 2)}</pre>
              <button onClick={() => { onOptimized(result); onClose(); }} className="mt-3 px-3 py-2 bg-green-600 hover:bg-green-700 rounded text-white">Apply</button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
export default StrategyOptimizationModal;
