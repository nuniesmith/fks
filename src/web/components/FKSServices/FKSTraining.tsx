import {
  Brain,
  Cpu,
  Zap,
  Play,
  Pause,
  Square,
  BarChart3,
  TrendingUp,
  AlertCircle,
  CheckCircle,
  Clock,
  Download,
  RefreshCw,
  Monitor,
  Thermometer,
  HardDrive,
  Activity
} from 'lucide-react';
import React, { useEffect, useMemo, useRef, useState } from 'react';

import {
  cancelTraining,
  downloadResults,
  getTrainingStatus,
  listModels,
  listTrainingJobs,
  startTraining,
  type JobsResponse,
  type ModelsResponse,
  type TrainRequest
} from '../../services/TrainingApi';
import { useNotifications } from '../Notifications';

interface TrainingJob {
  id: string;
  name: string;
  type: 'strategy_optimization' | 'sentiment_analysis' | 'price_prediction' | 'risk_assessment';
  status: 'running' | 'completed' | 'failed' | 'queued' | 'paused';
  progress: number;
  startTime: string;
  estimatedCompletion?: string;
  gpuUtilization: number;
  memoryUsage: number;
  currentEpoch?: number;
  totalEpochs?: number;
  bestScore?: number;
  hyperparameters: Record<string, any>;
}

interface ModelMetrics {
  accuracy: number;
  precision: number;
  recall: number;
  f1Score: number;
  loss: number;
  validationLoss: number;
  sharpeRatio?: number;
  maxDrawdown?: number;
  winRate?: number;
}

interface SystemResources {
  gpuUtilization: number;
  gpuMemory: number;
  gpuTemperature: number;
  cpuUsage: number;
  ramUsage: number;
  diskUsage: number;
  powerConsumption: number;
}

const FKSTraining: React.FC = () => {
  const { addNotification } = useNotifications();
  const [trainingJobs, setTrainingJobs] = useState<TrainingJob[]>([]);
  const [selectedJob, setSelectedJob] = useState<string | null>(null);
  const [systemResources, setSystemResources] = useState<SystemResources | null>(null);
  const [isMonitoring, setIsMonitoring] = useState(true);
  const [showCreateJob, setShowCreateJob] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [models, setModels] = useState<string[]>([]);
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const notifiedStatusRef = useRef<Map<string, TrainingJob['status']>>(new Map());

  const [form, setForm] = useState<{
    data_file: string;
    timeframe: string;
    models: string[];
    forecast_horizon: number;
    hyperparameters: string;
  }>({ data_file: '', timeframe: '1m', models: ['LSTM'], forecast_horizon: 5, hyperparameters: '' });

  // Initial fetch of jobs and models
  useEffect(() => {
    let cancelled = false;
    async function boot() {
      setIsLoading(true);
      setError(null);
      try {
        const [jobs, mdl] = await Promise.allSettled([
          listTrainingJobs(),
          listModels(),
        ]);

        if (!cancelled) {
          if (jobs.status === 'fulfilled') {
            const mapped = mapJobsResponse(jobs.value);
            setTrainingJobs(mapped);
          }
          if (mdl.status === 'fulfilled') {
            const names = extractModelNames(mdl.value);
            setModels(names);
            if (names.length && form.models.length === 0) {
              setForm((f) => ({ ...f, models: [names[0]] }));
            }
          } else {
            // fallback defaults
            if (!models.length) setModels(['ARIMA', 'Prophet', 'LSTM']);
          }
          // initialize system widgets
          setSystemResources((prev) => prev ?? {
            gpuUtilization: 0,
            gpuMemory: 0,
            gpuTemperature: 55,
            cpuUsage: 10,
            ramUsage: 30,
            diskUsage: 35,
            powerConsumption: 120,
          });
        }
  } catch (e: any) {
        if (!cancelled) setError(e?.message || 'Failed to load training jobs');
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    }
    boot();
    return () => { cancelled = true; };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Poll jobs and update resource widgets
  useEffect(() => {
    if (!isMonitoring) {
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
        pollingRef.current = null;
      }
      return;
    }

    async function tick() {
      try {
        const jobsResp = await listTrainingJobs();
        const mapped = mapJobsResponse(jobsResp);
        setTrainingJobs((prev) => {
          // merge to preserve extra fields like name if present
          const byId = new Map(prev.map((j) => [j.id, j] as const));
          const merged = mapped.map((j) => ({ ...byId.get(j.id), ...j }));
          return merged;
        });
        // Emit notifications for status transitions to completed/failed
        mapped.forEach((j) => {
          const last = notifiedStatusRef.current.get(j.id);
          if ((j.status === 'completed' || j.status === 'failed') && last !== j.status) {
            notifiedStatusRef.current.set(j.id, j.status);
            addNotification({
              type: j.status === 'completed' ? 'success' : 'warning',
              title: `Training ${j.status}`,
              message: `${j.name} (${j.id})`,
              duration: 6000,
            } as any);
          }
        });

        // optionally query individual status for in-flight jobs to get progress
        const inflight = mapped.filter((j) => ['running', 'queued', 'paused'].includes(j.status));
        if (inflight.length) {
          const statuses = await Promise.allSettled(inflight.map((j) => getTrainingStatus(j.id)));
          setTrainingJobs((prev) => {
            const copy = [...prev];
            statuses.forEach((res, idx) => {
              if (res.status === 'fulfilled') {
                const s = res.value;
                const id = s.job_id || inflight[idx].id;
                const i = copy.findIndex((x) => x.id === id);
                if (i >= 0) {
                  copy[i] = {
                    ...copy[i],
                    status: mapStatus(s.status),
                    progress: s.progress ?? copy[i].progress ?? 0,
                    startTime: s.start_time ? new Date(s.start_time * 1000).toISOString() : copy[i].startTime,
                  };
                }
              }
            });
            return copy;
          });
        }

        // update simple resource widgets heuristically based on running jobs
        const running = mapped.some((j) => j.status === 'running');
        setSystemResources((prev) => {
          const base: SystemResources = prev ?? {
            gpuUtilization: 0, gpuMemory: 0, gpuTemperature: 55, cpuUsage: 10, ramUsage: 30, diskUsage: 35, powerConsumption: 120,
          };
          if (!running) return { ...base, gpuUtilization: 5, gpuMemory: Math.max(0, base.gpuMemory - 1), powerConsumption: 110 };
          return {
            ...base,
            gpuUtilization: Math.min(95, 60 + Math.random() * 30),
            gpuMemory: Math.min(95, 60 + Math.random() * 25),
            gpuTemperature: Math.min(85, 70 + Math.random() * 10),
            cpuUsage: Math.min(85, 35 + Math.random() * 30),
            ramUsage: Math.min(90, 50 + Math.random() * 30),
            powerConsumption: 250 + Math.floor(Math.random() * 120),
          };
        });
      } catch (e: any) {
        setError(e?.message || 'Failed to refresh jobs');
      }
    }

    // start immediately then poll every 5s
    tick();
    pollingRef.current = setInterval(tick, 5000);
    return () => { if (pollingRef.current) clearInterval(pollingRef.current); pollingRef.current = null; };
  }, [isMonitoring]);

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'running':
        return <Play className="w-4 h-4 text-green-400" />;
      case 'completed':
        return <CheckCircle className="w-4 h-4 text-blue-400" />;
      case 'failed':
        return <AlertCircle className="w-4 h-4 text-red-400" />;
      case 'queued':
        return <Clock className="w-4 h-4 text-yellow-400" />;
      case 'paused':
        return <Pause className="w-4 h-4 text-gray-400" />;
      default:
        return <Square className="w-4 h-4 text-gray-400" />;
    }
  };

  const getTypeIcon = (type: string) => {
    switch (type) {
      case 'strategy_optimization':
        return <TrendingUp className="w-4 h-4 text-green-400" />;
      case 'sentiment_analysis':
        return <Brain className="w-4 h-4 text-purple-400" />;
      case 'price_prediction':
        return <BarChart3 className="w-4 h-4 text-blue-400" />;
      case 'risk_assessment':
        return <AlertCircle className="w-4 h-4 text-orange-400" />;
      default:
        return <Cpu className="w-4 h-4 text-gray-400" />;
    }
  };

  const handleCancelJob = async (jobId: string) => {
    try {
  await cancelTraining(jobId);
      setTrainingJobs((prev) => prev.map((j) => (j.id === jobId ? { ...j, status: 'failed' } : j)));
  addNotification({ type: 'milestone', title: 'Cancellation requested', message: `Training job ${jobId}`, duration: 3000 } as any);
    } catch (e: any) {
      setError(e?.message || 'Failed to cancel job');
  addNotification({ type: 'warning', title: 'Cancel failed', message: e?.message || 'Could not cancel job', duration: 5000 } as any);
    }
  };

  const handleDownload = async (jobId: string) => {
  try {
      const blob = await downloadResults(jobId);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `training_results_${jobId}.zip`;
      a.click();
      URL.revokeObjectURL(url);
      addNotification({ type: 'success', title: 'Results downloaded', message: `Saved results for ${jobId}`, duration: 3000 } as any);
    } catch (e: any) {
      setError(e?.message || 'Failed to download results');
      addNotification({ type: 'warning', title: 'Download failed', message: e?.message || 'Failed to download', duration: 5000 } as any);
    }
  };

  const canDownload = useMemo(() => (status: TrainingJob['status']) => status === 'completed', []);

  function onFormChange<K extends keyof typeof form>(key: K, value: (typeof form)[K]) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  async function submitNewJob() {
    setIsLoading(true);
    setError(null);
    try {
      let hyper: Record<string, any> | null = null;
      if (form.hyperparameters.trim()) {
        try { hyper = JSON.parse(form.hyperparameters); }
        catch { throw new Error('Hyperparameters must be valid JSON'); }
      }
      const req: TrainRequest = {
        data_file: form.data_file,
        timeframe: form.timeframe,
        models: form.models.length ? form.models : undefined,
        forecast_horizon: form.forecast_horizon,
        hyperparameters: hyper,
      };
  const res = await startTraining(req);
      const jobId = (res as any).job_id || (res as any).id || 'unknown';
      const nowIso = new Date().toISOString();
      setTrainingJobs((prev) => ([
        {
          id: String(jobId),
          name: form.data_file.split('/').pop() || 'Training Job',
          type: 'strategy_optimization',
          status: 'queued',
          progress: 0,
          startTime: nowIso,
          gpuUtilization: 0,
          memoryUsage: 0,
          hyperparameters: req.hyperparameters || {},
        },
        ...prev,
      ]));
  addNotification({ type: 'success', title: 'Training job started', message: `Job ${jobId}`, duration: 4000 } as any);
      setShowCreateJob(false);
      setForm({ data_file: '', timeframe: '1m', models: models.slice(0, 1) || ['LSTM'], forecast_horizon: 5, hyperparameters: '' });
    } catch (e: any) {
      setError(e?.message || 'Failed to start training');
  addNotification({ type: 'warning', title: 'Failed to start training', message: e?.message || 'See logs for details', duration: 5000 } as any);
    } finally {
      setIsLoading(false);
    }
  }

  function extractModelNames(resp: ModelsResponse): string[] {
    // Accept models as list of strings or objects with name
    const list = resp?.models ?? [];
    return list.map((m: any) => (typeof m === 'string' ? m : m?.name || m?.id)).filter(Boolean);
  }

  function mapJobsResponse(resp: JobsResponse): TrainingJob[] {
    const jobs = resp?.jobs ?? [];
    const mapOne = (j: any): TrainingJob => {
      const id = String(j.job_id ?? j.id ?? j.uuid ?? Math.random().toString(36).slice(2));
      const status = mapStatus(j.status ?? j.state ?? 'queued');
      const progress = typeof j.progress === 'number' ? j.progress : 0;
      const startTs = j.start_time ?? j.started_at ?? j.created_at;
      const startTime = startTs ? new Date((typeof startTs === 'number' ? startTs * 1000 : Date.parse(startTs))).toISOString() : new Date().toISOString();
      return {
        id,
        name: j.name || j.title || `Job ${id}`,
        type: (j.type || 'strategy_optimization') as TrainingJob['type'],
        status,
        progress,
        startTime,
        gpuUtilization: j.gpu_utilization ?? 0,
        memoryUsage: j.memory_usage_gb ?? 0,
        currentEpoch: j.current_epoch,
        totalEpochs: j.total_epochs,
        bestScore: j.best_score,
        hyperparameters: j.hyperparameters || {},
      };
    };
    return jobs.map(mapOne);
  }

  function mapStatus(s: string): TrainingJob['status'] {
    const t = String(s || '').toLowerCase();
    if (t.includes('fail')) return 'failed';
    if (t.includes('complete') || t === 'done' || t === 'finished' || t === 'success') return 'completed';
    if (t.includes('pause')) return 'paused';
    if (t.includes('queue')) return 'queued';
    if (t.includes('cancel')) return 'failed';
    return 'running';
  }

  const formatTimeRemaining = (estimatedCompletion?: string) => {
    if (!estimatedCompletion) return 'Unknown';
    
    const now = new Date();
    const completion = new Date(estimatedCompletion);
    const diff = completion.getTime() - now.getTime();
    
    if (diff <= 0) return 'Completed';
    
    const hours = Math.floor(diff / (1000 * 60 * 60));
    const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
    
    return `${hours}h ${minutes}m`;
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white flex items-center space-x-3">
            <Brain className="w-8 h-8 text-purple-400" />
            <span>GPU Training</span>
          </h1>
          <p className="text-gray-400 mt-2">
            GPU-accelerated machine learning model training and backtesting for trading strategies
          </p>
        </div>
        <div className="flex items-center space-x-3">
          <button
            onClick={() => setIsMonitoring(!isMonitoring)}
            className={`px-4 py-2 rounded-lg transition-colors ${
              isMonitoring 
                ? 'bg-green-600 hover:bg-green-700 text-white' 
                : 'bg-gray-600 hover:bg-gray-700 text-white'
            }`}
          >
            {isMonitoring ? 'Monitoring ON' : 'Monitoring OFF'}
          </button>
          <button
            onClick={() => setShowCreateJob(true)}
            className="px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-lg transition-colors"
          >
            New Training Job
          </button>
        </div>
      </div>

      {error && (
        <div className="bg-red-900/40 text-red-200 border border-red-700 px-4 py-2 rounded">
          {error}
        </div>
      )}

      {/* System Resources */}
      {systemResources && (
        <div className="grid grid-cols-1 md:grid-cols-4 lg:grid-cols-7 gap-4">
          <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
            <div className="flex items-center justify-between mb-2">
              <span className="text-gray-400 text-sm">GPU Usage</span>
              <Cpu className="w-4 h-4 text-green-400" />
            </div>
            <div className="text-2xl font-bold text-white">{systemResources.gpuUtilization.toFixed(0)}%</div>
            <div className="w-full bg-gray-700 rounded-full h-2 mt-2">
              <div
                className="bg-green-400 h-2 rounded-full transition-all duration-500"
                style={{ width: `${systemResources.gpuUtilization}%` }}
              />
            </div>
          </div>
          
          <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
            <div className="flex items-center justify-between mb-2">
              <span className="text-gray-400 text-sm">GPU Memory</span>
              <HardDrive className="w-4 h-4 text-blue-400" />
            </div>
            <div className="text-2xl font-bold text-white">{systemResources.gpuMemory.toFixed(1)}%</div>
            <div className="w-full bg-gray-700 rounded-full h-2 mt-2">
              <div
                className="bg-blue-400 h-2 rounded-full transition-all duration-500"
                style={{ width: `${systemResources.gpuMemory}%` }}
              />
            </div>
          </div>
          
          <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
            <div className="flex items-center justify-between mb-2">
              <span className="text-gray-400 text-sm">GPU Temp</span>
              <Thermometer className="w-4 h-4 text-orange-400" />
            </div>
            <div className="text-2xl font-bold text-white">{systemResources.gpuTemperature}°C</div>
            <div className="w-full bg-gray-700 rounded-full h-2 mt-2">
              <div
                className={`h-2 rounded-full transition-all duration-500 ${
                  systemResources.gpuTemperature > 80 ? 'bg-red-400' :
                  systemResources.gpuTemperature > 70 ? 'bg-orange-400' : 'bg-green-400'
                }`}
                style={{ width: `${Math.min(systemResources.gpuTemperature, 100)}%` }}
              />
            </div>
          </div>
          
          <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
            <div className="flex items-center justify-between mb-2">
              <span className="text-gray-400 text-sm">CPU</span>
              <Monitor className="w-4 h-4 text-purple-400" />
            </div>
            <div className="text-2xl font-bold text-white">{systemResources.cpuUsage.toFixed(0)}%</div>
            <div className="w-full bg-gray-700 rounded-full h-2 mt-2">
              <div
                className="bg-purple-400 h-2 rounded-full transition-all duration-500"
                style={{ width: `${systemResources.cpuUsage}%` }}
              />
            </div>
          </div>
          
          <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
            <div className="flex items-center justify-between mb-2">
              <span className="text-gray-400 text-sm">RAM</span>
              <Activity className="w-4 h-4 text-yellow-400" />
            </div>
            <div className="text-2xl font-bold text-white">{systemResources.ramUsage.toFixed(0)}%</div>
            <div className="w-full bg-gray-700 rounded-full h-2 mt-2">
              <div
                className="bg-yellow-400 h-2 rounded-full transition-all duration-500"
                style={{ width: `${systemResources.ramUsage}%` }}
              />
            </div>
          </div>
          
          <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
            <div className="flex items-center justify-between mb-2">
              <span className="text-gray-400 text-sm">Disk</span>
              <HardDrive className="w-4 h-4 text-cyan-400" />
            </div>
            <div className="text-2xl font-bold text-white">{systemResources.diskUsage}%</div>
            <div className="w-full bg-gray-700 rounded-full h-2 mt-2">
              <div
                className="bg-cyan-400 h-2 rounded-full transition-all duration-500"
                style={{ width: `${systemResources.diskUsage}%` }}
              />
            </div>
          </div>
          
          <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
            <div className="flex items-center justify-between mb-2">
              <span className="text-gray-400 text-sm">Power</span>
              <Zap className="w-4 h-4 text-red-400" />
            </div>
            <div className="text-2xl font-bold text-white">{systemResources.powerConsumption}W</div>
            <div className="text-xs text-gray-400 mt-1">RTX 4090</div>
          </div>
        </div>
      )}

      {/* Training Jobs */}
      <div className="bg-gray-800 rounded-lg border border-gray-700">
        <div className="p-6 border-b border-gray-700">
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-semibold text-white">Active Training Jobs</h3>
            <button
              onClick={() => {
                setIsLoading(true);
                listTrainingJobs().then((r) => setTrainingJobs(mapJobsResponse(r))).catch((e) => setError(e?.message || 'Failed to refresh')).finally(() => setIsLoading(false));
              }}
              className="text-sm px-3 py-1 bg-gray-700 hover:bg-gray-600 text-white rounded flex items-center gap-1"
            >
              <RefreshCw className="w-4 h-4" /> Refresh
            </button>
          </div>
        </div>
        
        <div className="divide-y divide-gray-700">
          {isLoading && trainingJobs.length === 0 && (
            <div className="p-6 text-gray-400">Loading jobs…</div>
          )}
          {trainingJobs.map((job) => (
            <div key={job.id} className="p-6">
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-start space-x-3">
                  {getTypeIcon(job.type)}
                  <div>
                    <h4 className="font-medium text-white">{job.name}</h4>
                    <p className="text-sm text-gray-400 capitalize">{job.type.replace('_', ' ')}</p>
                  </div>
                </div>
                
                <div className="flex items-center space-x-2">
                  {getStatusIcon(job.status)}
                  <span className={`text-sm capitalize ${
                    job.status === 'running' ? 'text-green-400' :
                    job.status === 'completed' ? 'text-blue-400' :
                    job.status === 'failed' ? 'text-red-400' :
                    job.status === 'queued' ? 'text-yellow-400' :
                    'text-gray-400'
                  }`}>
                    {job.status}
                  </span>
                </div>
              </div>

              {/* Progress Bar */}
              <div className="mb-4">
                <div className="flex justify-between text-sm text-gray-400 mb-1">
                  <span>Progress</span>
                  <span>{job.progress.toFixed(1)}%</span>
                </div>
                <div className="w-full bg-gray-700 rounded-full h-2">
                  <div
                    className={`h-2 rounded-full transition-all duration-500 ${
                      job.status === 'running' ? 'bg-green-400' :
                      job.status === 'completed' ? 'bg-blue-400' :
                      job.status === 'failed' ? 'bg-red-400' :
                      'bg-gray-500'
                    }`}
                    style={{ width: `${job.progress}%` }}
                  />
                </div>
              </div>

              {/* Job Details */}
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 text-sm">
                <div>
                  <span className="text-gray-400">Started:</span>
                  <div className="text-white">{job.startTime}</div>
                </div>
                
                {job.estimatedCompletion && (
                  <div>
                    <span className="text-gray-400">Time Remaining:</span>
                    <div className="text-white">{formatTimeRemaining(job.estimatedCompletion)}</div>
                  </div>
                )}
                
                {job.currentEpoch && job.totalEpochs && (
                  <div>
                    <span className="text-gray-400">Epoch:</span>
                    <div className="text-white">{job.currentEpoch} / {job.totalEpochs}</div>
                  </div>
                )}
                
                {job.bestScore && (
                  <div>
                    <span className="text-gray-400">Best Score:</span>
                    <div className="text-white">{job.bestScore.toFixed(3)}</div>
                  </div>
                )}
              </div>

              {/* Resource Usage */}
              <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <span className="text-gray-400 text-sm">GPU Utilization:</span>
                  <div className="flex items-center space-x-2 mt-1">
                    <div className="w-full bg-gray-700 rounded-full h-1.5">
                      <div
                        className="bg-green-400 h-1.5 rounded-full transition-all duration-500"
                        style={{ width: `${job.gpuUtilization}%` }}
                      />
                    </div>
                    <span className="text-xs text-white">{job.gpuUtilization.toFixed(0)}%</span>
                  </div>
                </div>
                
                <div>
                  <span className="text-gray-400 text-sm">Memory Usage:</span>
                  <div className="flex items-center space-x-2 mt-1">
                    <div className="w-full bg-gray-700 rounded-full h-1.5">
                      <div
                        className="bg-blue-400 h-1.5 rounded-full transition-all duration-500"
                        style={{ width: `${Math.min(job.memoryUsage * 6.25, 100)}%` }}
                      />
                    </div>
                    <span className="text-xs text-white">{job.memoryUsage.toFixed(1)} GB</span>
                  </div>
                </div>
              </div>

              {/* Actions */}
              <div className="mt-4 flex items-center gap-2">
                {['running', 'queued', 'paused'].includes(job.status) && (
                  <button
                    onClick={() => handleCancelJob(job.id)}
                    className="px-3 py-1 bg-red-600 hover:bg-red-700 text-white rounded text-sm transition-colors"
                  >
                    Cancel
                  </button>
                )}
                {canDownload(job.status) && (
                  <button
                    onClick={() => handleDownload(job.id)}
                    className="px-3 py-1 bg-blue-600 hover:bg-blue-700 text-white rounded text-sm transition-colors flex items-center gap-1"
                  >
                    <Download className="w-4 h-4" /> Download Results
                  </button>
                )}
              </div>
            </div>
          ))}
          {(!isLoading && trainingJobs.length === 0) && (
            <div className="p-6 text-gray-400">No training jobs yet. Start one using the button above.</div>
          )}
        </div>
      </div>

      {/* Create Job Modal */}
      {showCreateJob && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
          <div className="bg-gray-900 border border-gray-700 rounded-lg p-6 w-full max-w-2xl">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-white font-semibold text-lg flex items-center gap-2">
                <Play className="w-5 h-5 text-purple-400" /> New Training Job
              </h3>
              <button className="text-gray-400 hover:text-gray-200" onClick={() => setShowCreateJob(false)}>×</button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="col-span-1 md:col-span-2">
                <label className="block text-sm text-gray-300 mb-1">Data file (path or dataset id)</label>
                <input
                  value={form.data_file}
                  onChange={(e) => onFormChange('data_file', e.target.value)}
                  placeholder="/data/training/bars_es.csv"
                  className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-white placeholder-gray-500"
                />
              </div>

              <div>
                <label className="block text-sm text-gray-300 mb-1">Timeframe</label>
                <input
                  value={form.timeframe}
                  onChange={(e) => onFormChange('timeframe', e.target.value)}
                  placeholder="1m"
                  className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-white placeholder-gray-500"
                />
              </div>

              <div>
                <label className="block text-sm text-gray-300 mb-1">Forecast horizon</label>
                <input
                  type="number"
                  value={form.forecast_horizon}
                  onChange={(e) => onFormChange('forecast_horizon', Number(e.target.value))}
                  className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-white"
                />
              </div>

              <div className="col-span-1 md:col-span-2">
                <label className="block text-sm text-gray-300 mb-1">Models</label>
                <div className="flex flex-wrap gap-2">
                  {(models.length ? models : ['ARIMA', 'Prophet', 'LSTM']).map((m) => {
                    const active = form.models.includes(m);
                    return (
                      <button
                        key={m}
                        type="button"
                        onClick={() => onFormChange('models', active ? form.models.filter((x) => x !== m) : [...form.models, m])}
                        className={`px-3 py-1 rounded border text-sm ${active ? 'bg-purple-600 border-purple-500 text-white' : 'bg-gray-800 border-gray-700 text-gray-300'}`}
                      >
                        {m}
                      </button>
                    );
                  })}
                </div>
              </div>

              <div className="col-span-1 md:col-span-2">
                <label className="block text-sm text-gray-300 mb-1">Hyperparameters (JSON)</label>
                <textarea
                  rows={5}
                  value={form.hyperparameters}
                  onChange={(e) => onFormChange('hyperparameters', e.target.value)}
                  placeholder='{"learning_rate": 0.0003, "batch_size": 64}'
                  className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-white placeholder-gray-500"
                />
              </div>
            </div>

            <div className="mt-6 flex items-center justify-end gap-2">
              <button className="px-4 py-2 rounded bg-gray-700 hover:bg-gray-600 text-white" onClick={() => setShowCreateJob(false)}>Cancel</button>
              <button
                className="px-4 py-2 rounded bg-purple-600 hover:bg-purple-700 text-white disabled:opacity-60"
                disabled={!form.data_file || isLoading}
                onClick={submitNewJob}
              >
                {isLoading ? 'Starting…' : 'Start Training'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default FKSTraining;
