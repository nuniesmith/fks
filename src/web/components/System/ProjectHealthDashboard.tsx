import { 
  AlertTriangle, 
  CheckCircle, 
  Clock, 
  Code, 
  FileText, 
  Package, 
  RefreshCw,
  Shield,
  Zap,
  Bug,
  TrendingUp,
  Server
} from 'lucide-react';
import React, { useState, useEffect } from 'react';

interface HealthCheck {
  id: string;
  name: string;
  category: 'code' | 'dependencies' | 'infrastructure' | 'security' | 'performance';
  status: 'healthy' | 'warning' | 'error' | 'unknown';
  message: string;
  details?: string[];
  lastChecked: Date;
  autoFix?: boolean;
  priority: 'low' | 'medium' | 'high' | 'critical';
}

interface ProjectTask {
  id: string;
  title: string;
  description: string;
  category: 'bug' | 'feature' | 'improvement' | 'security' | 'performance';
  priority: 'low' | 'medium' | 'high' | 'critical';
  status: 'todo' | 'in-progress' | 'review' | 'done';
  assignedTo?: string;
  dueDate?: Date;
  estimatedHours?: number;
  relatedHealthChecks?: string[];
}

const ProjectHealthDashboard: React.FC = () => {
  const [healthChecks, setHealthChecks] = useState<HealthCheck[]>([]);
  const [tasks, setTasks] = useState<ProjectTask[]>([]);
  const [loading, setLoading] = useState(false);
  const [lastUpdate, setLastUpdate] = useState<Date>(new Date());
  const [selectedCategory, setSelectedCategory] = useState<string>('all');

  // Initialize with sample health checks
  useEffect(() => {
    const initialHealthChecks: HealthCheck[] = [
      {
        id: 'ts-errors',
        name: 'TypeScript Compilation',
        category: 'code',
        status: 'healthy',
        message: 'All TypeScript files compile without errors',
        details: ['0 errors found', '2 warnings (non-blocking)', 'Last check: 2 minutes ago'],
        lastChecked: new Date(),
        priority: 'high'
      },
      {
        id: 'dependencies',
        name: 'Package Dependencies',
        category: 'dependencies',
        status: 'warning',
        message: '3 packages have security vulnerabilities',
        details: [
          'lodash@4.17.15 - Moderate severity',
          'axios@0.21.1 - High severity', 
          'dayjs@1.11.13 - Up to date'
        ],
        lastChecked: new Date(),
        autoFix: true,
        priority: 'high'
      },
      {
        id: 'docker-health',
        name: 'Docker Services',
        category: 'infrastructure',
        status: 'healthy',
        message: 'All containers running normally',
        details: [
          'react-app: Running (port 3000)',
          'api-service: Running (port 8000)', 
          'postgres: Running (port 5432)',
          'redis: Running (port 6379)'
        ],
        lastChecked: new Date(),
        priority: 'critical'
      },
      {
        id: 'api-endpoints',
        name: 'API Health Check',
        category: 'infrastructure',
        status: 'warning',
        message: '2 endpoints responding slowly',
        details: [
          '/api/trading/data - 850ms (target: <500ms)',
          '/api/market/live - 1.2s (target: <500ms)',
          'All other endpoints healthy'
        ],
        lastChecked: new Date(),
        priority: 'medium'
      },
      {
        id: 'security-scan',
        name: 'Security Vulnerabilities',
        category: 'security',
        status: 'error',
        message: 'High-severity vulnerability found',
        details: [
          'CVE-2021-44228 - Log4j vulnerability detected',
          'Recommendation: Update to latest version',
          'Risk: Remote code execution'
        ],
        lastChecked: new Date(),
        priority: 'critical'
      },
      {
        id: 'performance',
        name: 'Performance Metrics',
        category: 'performance',
        status: 'healthy',
        message: 'All metrics within acceptable ranges',
        details: [
          'Initial load time: 1.2s (target: <2s)',
          'Memory usage: 65% (target: <80%)',
          'CPU usage: 45% (target: <70%)'
        ],
        lastChecked: new Date(),
        priority: 'medium'
      }
    ];

    const initialTasks: ProjectTask[] = [
      {
        id: 'calendar-integration',
        title: 'Integrate Calendar Component',
        description: 'Add the calendar component to track development progress and milestone dates',
        category: 'feature',
        priority: 'high',
        status: 'in-progress',
        estimatedHours: 4,
        dueDate: new Date(2025, 6, 27)
      },
      {
        id: 'security-fix',
        title: 'Fix Log4j Vulnerability',
        description: 'Update dependencies to resolve CVE-2021-44228',
        category: 'security',
        priority: 'critical',
        status: 'todo',
        estimatedHours: 2,
        relatedHealthChecks: ['security-scan'],
        dueDate: new Date(2025, 6, 26)
      },
      {
        id: 'api-optimization',
        title: 'Optimize Slow API Endpoints',
        description: 'Improve response times for trading data and market live endpoints',
        category: 'performance',
        priority: 'medium',
        status: 'todo',
        estimatedHours: 8,
        relatedHealthChecks: ['api-endpoints']
      },
      {
        id: 'html-migration',
        title: 'Move HTML Files to React Directory',
        description: 'Reorganize project structure by moving HTML files under React directory',
        category: 'improvement',
        priority: 'medium',
        status: 'todo',
        estimatedHours: 3
      },
      {
        id: 'strategy-library',
        title: 'Implement Strategy Library',
        description: 'Create a library system for simple and complex trading strategies',
        category: 'feature',
        priority: 'high',
        status: 'todo',
        estimatedHours: 16,
        dueDate: new Date(2025, 7, 15)
      }
    ];

    setHealthChecks(initialHealthChecks);
    setTasks(initialTasks);
  }, []);

  const runHealthChecks = async () => {
    setLoading(true);
    
    // Simulate health check execution
    await new Promise(resolve => setTimeout(resolve, 2000));
    
    // Update timestamps and potentially status
    setHealthChecks(prev => 
      prev.map(check => ({
        ...check,
        lastChecked: new Date()
      }))
    );
    
    setLastUpdate(new Date());
    setLoading(false);
  };

  const getStatusIcon = (status: HealthCheck['status']) => {
    switch (status) {
      case 'healthy':
        return <CheckCircle className="w-5 h-5 text-green-400" />;
      case 'warning':
        return <AlertTriangle className="w-5 h-5 text-yellow-400" />;
      case 'error':
        return <AlertTriangle className="w-5 h-5 text-red-400" />;
      default:
        return <Clock className="w-5 h-5 text-gray-400" />;
    }
  };

  const getCategoryIcon = (category: HealthCheck['category']) => {
    switch (category) {
      case 'code':
        return <Code className="w-4 h-4" />;
      case 'dependencies':
        return <Package className="w-4 h-4" />;
      case 'infrastructure':
        return <Server className="w-4 h-4" />;
      case 'security':
        return <Shield className="w-4 h-4" />;
      case 'performance':
        return <TrendingUp className="w-4 h-4" />;
      default:
        return <FileText className="w-4 h-4" />;
    }
  };

  const getTaskIcon = (category: ProjectTask['category']) => {
    switch (category) {
      case 'bug':
        return <Bug className="w-4 h-4" />;
      case 'feature':
        return <Zap className="w-4 h-4" />;
      case 'security':
        return <Shield className="w-4 h-4" />;
      case 'performance':
        return <TrendingUp className="w-4 h-4" />;
      default:
        return <FileText className="w-4 h-4" />;
    }
  };

  const filteredHealthChecks = selectedCategory === 'all' 
    ? healthChecks 
    : healthChecks.filter(check => check.category === selectedCategory);

  const healthSummary = {
    healthy: healthChecks.filter(c => c.status === 'healthy').length,
    warning: healthChecks.filter(c => c.status === 'warning').length,
    error: healthChecks.filter(c => c.status === 'error').length,
    total: healthChecks.length
  };

  const taskSummary = {
    todo: tasks.filter(t => t.status === 'todo').length,
    inProgress: tasks.filter(t => t.status === 'in-progress').length,
    review: tasks.filter(t => t.status === 'review').length,
    done: tasks.filter(t => t.status === 'done').length,
    total: tasks.length
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white">Project Health Dashboard</h1>
          <p className="text-gray-400 mt-1">
            Monitor code quality, track issues, and manage development tasks
          </p>
        </div>
        
        <button
          onClick={runHealthChecks}
          disabled={loading}
          className="flex items-center space-x-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 rounded-lg text-white transition-colors"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          <span>{loading ? 'Checking...' : 'Run Health Checks'}</span>
        </button>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-gray-400 text-sm">System Health</p>
              <p className="text-2xl font-bold text-green-400">{healthSummary.healthy}/{healthSummary.total}</p>
            </div>
            <CheckCircle className="w-8 h-8 text-green-400" />
          </div>
        </div>

        <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-gray-400 text-sm">Warnings</p>
              <p className="text-2xl font-bold text-yellow-400">{healthSummary.warning}</p>
            </div>
            <AlertTriangle className="w-8 h-8 text-yellow-400" />
          </div>
        </div>

        <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-gray-400 text-sm">Critical Issues</p>
              <p className="text-2xl font-bold text-red-400">{healthSummary.error}</p>
            </div>
            <AlertTriangle className="w-8 h-8 text-red-400" />
          </div>
        </div>

        <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-gray-400 text-sm">Tasks Todo</p>
              <p className="text-2xl font-bold text-blue-400">{taskSummary.todo}</p>
            </div>
            <Clock className="w-8 h-8 text-blue-400" />
          </div>
        </div>
      </div>

      {/* Content Tabs */}
      <div className="bg-gray-800 rounded-lg border border-gray-700">
        <div className="flex border-b border-gray-700">
          <button
            onClick={() => setSelectedCategory('all')}
            className={`px-6 py-3 font-medium transition-colors ${
              selectedCategory === 'all'
                ? 'text-blue-400 border-b-2 border-blue-400 bg-gray-700/30'
                : 'text-gray-400 hover:text-white'
            }`}
          >
            All Health Checks
          </button>
          {['code', 'dependencies', 'infrastructure', 'security', 'performance'].map(category => (
            <button
              key={category}
              onClick={() => setSelectedCategory(category)}
              className={`px-6 py-3 font-medium transition-colors capitalize ${
                selectedCategory === category
                  ? 'text-blue-400 border-b-2 border-blue-400 bg-gray-700/30'
                  : 'text-gray-400 hover:text-white'
              }`}
            >
              {category}
            </button>
          ))}
        </div>

        <div className="p-6">
          <div className="space-y-4">
            {filteredHealthChecks.map(check => (
              <div key={check.id} className="bg-gray-700/30 rounded-lg p-4 border border-gray-600">
                <div className="flex items-start justify-between">
                  <div className="flex items-start space-x-3">
                    {getStatusIcon(check.status)}
                    <div className="flex-1">
                      <div className="flex items-center space-x-2">
                        {getCategoryIcon(check.category)}
                        <h3 className="font-semibold text-white">{check.name}</h3>
                        <span className={`text-xs px-2 py-1 rounded ${
                          check.priority === 'critical' ? 'bg-red-500/20 text-red-400' :
                          check.priority === 'high' ? 'bg-orange-500/20 text-orange-400' :
                          check.priority === 'medium' ? 'bg-yellow-500/20 text-yellow-400' :
                          'bg-gray-500/20 text-gray-400'
                        }`}>
                          {check.priority}
                        </span>
                      </div>
                      <p className="text-gray-300 mt-1">{check.message}</p>
                      {check.details && (
                        <ul className="text-sm text-gray-400 mt-2 space-y-1">
                          {check.details.map((detail, index) => (
                            <li key={index} className="flex items-start space-x-2">
                              <span className="text-gray-500">•</span>
                              <span>{detail}</span>
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                  </div>
                  
                  <div className="flex items-center space-x-2">
                    {check.autoFix && (
                      <button className="px-3 py-1 bg-blue-600 hover:bg-blue-700 rounded text-sm text-white transition-colors">
                        Auto Fix
                      </button>
                    )}
                    <span className="text-xs text-gray-500">
                      {check.lastChecked.toLocaleTimeString()}
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Tasks Section */}
      <div className="bg-gray-800 rounded-lg border border-gray-700">
        <div className="p-6 border-b border-gray-700">
          <h2 className="text-xl font-semibold text-white">Development Tasks</h2>
          <p className="text-gray-400 text-sm mt-1">
            Track and organize work items for the FKS project
          </p>
        </div>
        
        <div className="p-6">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {tasks.map(task => (
              <div key={task.id} className="bg-gray-700/30 rounded-lg p-4 border border-gray-600">
                <div className="flex items-start justify-between mb-2">
                  <div className="flex items-center space-x-2">
                    {getTaskIcon(task.category)}
                    <span className={`text-xs px-2 py-1 rounded capitalize ${
                      task.category === 'bug' ? 'bg-red-500/20 text-red-400' :
                      task.category === 'feature' ? 'bg-blue-500/20 text-blue-400' :
                      task.category === 'security' ? 'bg-orange-500/20 text-orange-400' :
                      task.category === 'performance' ? 'bg-green-500/20 text-green-400' :
                      'bg-gray-500/20 text-gray-400'
                    }`}>
                      {task.category}
                    </span>
                  </div>
                  <span className={`text-xs px-2 py-1 rounded ${
                    task.priority === 'critical' ? 'bg-red-500/20 text-red-400' :
                    task.priority === 'high' ? 'bg-orange-500/20 text-orange-400' :
                    task.priority === 'medium' ? 'bg-yellow-500/20 text-yellow-400' :
                    'bg-gray-500/20 text-gray-400'
                  }`}>
                    {task.priority}
                  </span>
                </div>
                
                <h3 className="font-semibold text-white mb-2">{task.title}</h3>
                <p className="text-sm text-gray-300 mb-3">{task.description}</p>
                
                <div className="flex items-center justify-between text-xs text-gray-400">
                  <span className={`px-2 py-1 rounded ${
                    task.status === 'done' ? 'bg-green-500/20 text-green-400' :
                    task.status === 'in-progress' ? 'bg-blue-500/20 text-blue-400' :
                    task.status === 'review' ? 'bg-purple-500/20 text-purple-400' :
                    'bg-gray-500/20 text-gray-400'
                  }`}>
                    {task.status.replace('-', ' ')}
                  </span>
                  {task.estimatedHours && (
                    <span>{task.estimatedHours}h</span>
                  )}
                </div>
                
                {task.dueDate && (
                  <div className="mt-2 text-xs text-gray-400">
                    Due: {task.dueDate.toLocaleDateString()}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Last update info */}
      <div className="text-center text-gray-500 text-sm">
        Last updated: {lastUpdate.toLocaleString()}
      </div>
    </div>
  );
};

export default ProjectHealthDashboard;
