import { Settings, Sliders, Cog } from 'lucide-react';
import React from 'react';

const SettingsPanel: React.FC = () => {
  return (
    <div className="space-y-6">
      <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
        <h1 className="text-3xl font-bold text-white mb-2 flex items-center">
          <Settings className="w-8 h-8 mr-3 text-gray-400" />
          Settings
        </h1>
        <p className="text-gray-400">System configuration and preferences</p>
      </div>
      
      <div className="bg-gray-800 rounded-lg p-8 border border-gray-700 text-center">
        <Cog className="w-16 h-16 text-gray-400 mx-auto mb-4" />
        <h2 className="text-xl font-semibold text-white mb-2">Settings Panel Coming Soon</h2>
        <p className="text-gray-400 mb-6">
          Configuration management for system preferences, API settings, and user preferences.
        </p>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="bg-gray-900/50 rounded-lg p-4">
            <Settings className="w-8 h-8 text-gray-400 mx-auto mb-2" />
            <h3 className="text-white font-medium">System Config</h3>
            <p className="text-gray-400 text-sm">Global system settings</p>
          </div>
          <div className="bg-gray-900/50 rounded-lg p-4">
            <Sliders className="w-8 h-8 text-blue-400 mx-auto mb-2" />
            <h3 className="text-white font-medium">API Configuration</h3>
            <p className="text-gray-400 text-sm">Service endpoints and keys</p>
          </div>
          <div className="bg-gray-900/50 rounded-lg p-4">
            <Cog className="w-8 h-8 text-green-400 mx-auto mb-2" />
            <h3 className="text-white font-medium">User Preferences</h3>
            <p className="text-gray-400 text-sm">Personal customization</p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default SettingsPanel;
