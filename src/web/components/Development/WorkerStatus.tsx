import { Zap, Activity, Clock } from 'lucide-react';
import React from 'react';

const WorkerStatus: React.FC = () => {
  return (
    <div className="space-y-6">
      <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
        <h1 className="text-3xl font-bold text-white mb-2 flex items-center">
          <Zap className="w-8 h-8 mr-3 text-yellow-400" />
          Worker Status
        </h1>
        <p className="text-gray-400">Background job monitoring and management</p>
      </div>
      
      <div className="bg-gray-800 rounded-lg p-8 border border-gray-700 text-center">
        <Activity className="w-16 h-16 text-yellow-400 mx-auto mb-4" />
        <h2 className="text-xl font-semibold text-white mb-2">Worker Monitoring Coming Soon</h2>
        <p className="text-gray-400 mb-6">
          Real-time monitoring of background workers, job queues, and processing status.
        </p>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="bg-gray-900/50 rounded-lg p-4">
            <Zap className="w-8 h-8 text-yellow-400 mx-auto mb-2" />
            <h3 className="text-white font-medium">Active Workers</h3>
            <p className="text-gray-400 text-sm">Real-time worker status</p>
          </div>
          <div className="bg-gray-900/50 rounded-lg p-4">
            <Clock className="w-8 h-8 text-blue-400 mx-auto mb-2" />
            <h3 className="text-white font-medium">Job Queue</h3>
            <p className="text-gray-400 text-sm">Pending and processing jobs</p>
          </div>
          <div className="bg-gray-900/50 rounded-lg p-4">
            <Activity className="w-8 h-8 text-green-400 mx-auto mb-2" />
            <h3 className="text-white font-medium">Performance</h3>
            <p className="text-gray-400 text-sm">Throughput and latency</p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default WorkerStatus;
