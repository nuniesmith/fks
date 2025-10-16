import { FileText, Search, Filter } from 'lucide-react';
import React from 'react';

const SystemLogs: React.FC = () => {
  return (
    <div className="space-y-6">
      <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
        <h1 className="text-3xl font-bold text-white mb-2 flex items-center">
          <FileText className="w-8 h-8 mr-3 text-orange-400" />
          System Logs
        </h1>
        <p className="text-gray-400">Real-time log viewer and analysis</p>
      </div>
      
      <div className="bg-gray-800 rounded-lg p-8 border border-gray-700 text-center">
        <FileText className="w-16 h-16 text-orange-400 mx-auto mb-4" />
        <h2 className="text-xl font-semibold text-white mb-2">System Logs Coming Soon</h2>
        <p className="text-gray-400 mb-6">
          Real-time log streaming, filtering, and analysis from all system components.
        </p>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="bg-gray-900/50 rounded-lg p-4">
            <FileText className="w-8 h-8 text-orange-400 mx-auto mb-2" />
            <h3 className="text-white font-medium">Live Streaming</h3>
            <p className="text-gray-400 text-sm">Real-time log updates</p>
          </div>
          <div className="bg-gray-900/50 rounded-lg p-4">
            <Filter className="w-8 h-8 text-blue-400 mx-auto mb-2" />
            <h3 className="text-white font-medium">Advanced Filtering</h3>
            <p className="text-gray-400 text-sm">Service, level, time filters</p>
          </div>
          <div className="bg-gray-900/50 rounded-lg p-4">
            <Search className="w-8 h-8 text-green-400 mx-auto mb-2" />
            <h3 className="text-white font-medium">Search & Analysis</h3>
            <p className="text-gray-400 text-sm">Pattern detection</p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default SystemLogs;
