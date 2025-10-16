import { Database, Search, Table } from 'lucide-react';
import React from 'react';

const DataViewer: React.FC = () => {
  return (
    <div className="space-y-6">
      <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
        <h1 className="text-3xl font-bold text-white mb-2 flex items-center">
          <Database className="w-8 h-8 mr-3 text-blue-400" />
          Data Viewer
        </h1>
        <p className="text-gray-400">Database inspection and query interface</p>
      </div>
      
      <div className="bg-gray-800 rounded-lg p-8 border border-gray-700 text-center">
        <Table className="w-16 h-16 text-blue-400 mx-auto mb-4" />
        <h2 className="text-xl font-semibold text-white mb-2">Data Viewer Coming Soon</h2>
        <p className="text-gray-400 mb-6">
          Database inspection tools and query interface for PostgreSQL and Redis data.
        </p>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="bg-gray-900/50 rounded-lg p-4">
            <Database className="w-8 h-8 text-blue-400 mx-auto mb-2" />
            <h3 className="text-white font-medium">PostgreSQL</h3>
            <p className="text-gray-400 text-sm">Trading data and logs</p>
          </div>
          <div className="bg-gray-900/50 rounded-lg p-4">
            <Search className="w-8 h-8 text-green-400 mx-auto mb-2" />
            <h3 className="text-white font-medium">Query Builder</h3>
            <p className="text-gray-400 text-sm">Visual query interface</p>
          </div>
          <div className="bg-gray-900/50 rounded-lg p-4">
            <Table className="w-8 h-8 text-purple-400 mx-auto mb-2" />
            <h3 className="text-white font-medium">Data Export</h3>
            <p className="text-gray-400 text-sm">CSV, JSON export options</p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default DataViewer;
