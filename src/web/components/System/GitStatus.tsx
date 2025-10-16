import { GitBranch, Code, Clock } from 'lucide-react';
import React from 'react';

const GitStatus: React.FC = () => {
  return (
    <div className="space-y-6">
      <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
        <h1 className="text-3xl font-bold text-white mb-2 flex items-center">
          <GitBranch className="w-8 h-8 mr-3 text-purple-400" />
          Git Status
        </h1>
        <p className="text-gray-400">Repository information and deployment status</p>
      </div>
      
      <div className="bg-gray-800 rounded-lg p-8 border border-gray-700 text-center">
        <Code className="w-16 h-16 text-purple-400 mx-auto mb-4" />
        <h2 className="text-xl font-semibold text-white mb-2">Git Status Coming Soon</h2>
        <p className="text-gray-400 mb-6">
          Repository status, commit history, and deployment pipeline information.
        </p>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="bg-gray-900/50 rounded-lg p-4">
            <GitBranch className="w-8 h-8 text-purple-400 mx-auto mb-2" />
            <h3 className="text-white font-medium">Branch Status</h3>
            <p className="text-gray-400 text-sm">Current branch and commits</p>
          </div>
          <div className="bg-gray-900/50 rounded-lg p-4">
            <Clock className="w-8 h-8 text-blue-400 mx-auto mb-2" />
            <h3 className="text-white font-medium">Deploy History</h3>
            <p className="text-gray-400 text-sm">Recent deployments</p>
          </div>
          <div className="bg-gray-900/50 rounded-lg p-4">
            <Code className="w-8 h-8 text-green-400 mx-auto mb-2" />
            <h3 className="text-white font-medium">Code Changes</h3>
            <p className="text-gray-400 text-sm">Recent commits and PRs</p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default GitStatus;
