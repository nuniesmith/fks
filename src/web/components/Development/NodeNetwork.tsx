import { Network, Globe, Wifi } from 'lucide-react';
import React from 'react';

const NodeNetwork: React.FC = () => {
  return (
    <div className="space-y-6">
      <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
        <h1 className="text-3xl font-bold text-white mb-2 flex items-center">
          <Network className="w-8 h-8 mr-3 text-cyan-400" />
          Node Network
          <span className="ml-3 px-2 py-1 bg-blue-500/20 text-blue-400 text-xs rounded border border-blue-500/30">
            Beta
          </span>
        </h1>
        <p className="text-gray-400">Distributed nodes status and connectivity</p>
      </div>
      
      <div className="bg-gray-800 rounded-lg p-8 border border-gray-700 text-center">
        <Globe className="w-16 h-16 text-cyan-400 mx-auto mb-4" />
        <h2 className="text-xl font-semibold text-white mb-2">Node Network Coming Soon</h2>
        <p className="text-gray-400 mb-6">
          Distributed system monitoring for multi-node deployments and edge computing.
        </p>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="bg-gray-900/50 rounded-lg p-4">
            <Network className="w-8 h-8 text-cyan-400 mx-auto mb-2" />
            <h3 className="text-white font-medium">Node Discovery</h3>
            <p className="text-gray-400 text-sm">Automatic node detection</p>
          </div>
          <div className="bg-gray-900/50 rounded-lg p-4">
            <Wifi className="w-8 h-8 text-green-400 mx-auto mb-2" />
            <h3 className="text-white font-medium">Health Monitoring</h3>
            <p className="text-gray-400 text-sm">Real-time node status</p>
          </div>
          <div className="bg-gray-900/50 rounded-lg p-4">
            <Globe className="w-8 h-8 text-blue-400 mx-auto mb-2" />
            <h3 className="text-white font-medium">Load Balancing</h3>
            <p className="text-gray-400 text-sm">Traffic distribution</p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default NodeNetwork;
