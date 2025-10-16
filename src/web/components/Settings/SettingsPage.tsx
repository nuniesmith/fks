import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';

const SettingsPage: React.FC = () => {
  const [apiUrl, setApiUrl] = useState<string>('');
  const [apiToken, setApiToken] = useState<string>('');
  const [mock, setMock] = useState<boolean>(true);

  useEffect(() => {
    const url = (import.meta as any).env?.VITE_API_BASE_URL as string | undefined;
    const lsUrl = typeof window !== 'undefined' ? localStorage.getItem('fks_api_base_url') : null;
    const token = typeof window !== 'undefined' ? localStorage.getItem('fks_api_token') : null;
    const mockEnv = (import.meta as any).env?.VITE_MOCK_SERVICES;
    setApiUrl(lsUrl || url || '/api');
    setApiToken(token || '');
    setMock((mockEnv === 'true') || localStorage.getItem('fks_mock_services') === 'true');
  }, []);

  const save = () => {
    if (typeof window !== 'undefined') {
      localStorage.setItem('fks_api_base_url', apiUrl);
      if (apiToken) localStorage.setItem('fks_api_token', apiToken); else localStorage.removeItem('fks_api_token');
      localStorage.setItem('fks_mock_services', mock ? 'true' : 'false');
    }
    alert('Settings saved. Reload the app to apply.');
  };

  return (
    <div className="max-w-3xl mx-auto">
      <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
        <h1 className="text-2xl font-bold text-white mb-4">Settings</h1>

        <div className="space-y-4">
          <div>
            <label className="block text-sm text-gray-300 mb-1">API Base URL</label>
            <input value={apiUrl} onChange={(e)=> setApiUrl(e.target.value)} className="w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded text-white" />
            <div className="text-xs text-gray-400 mt-1">Overrides VITE_API_BASE_URL. Example: http://localhost:8000/api</div>
          </div>

          <div>
            <label className="block text-sm text-gray-300 mb-1">API Token (Bearer / X-API-Key)</label>
            <input value={apiToken} onChange={(e)=> setApiToken(e.target.value)} className="w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded text-white" />
            <div className="text-xs text-gray-400 mt-1">Stored locally; used for Authorization and X-API-Key. Do not paste provider secrets here—use Providers.</div>
          </div>

          <label className="flex items-center gap-2 text-gray-300">
            <input type="checkbox" checked={mock} onChange={(e)=> setMock(e.target.checked)} />
            Use Mock Services
          </label>

          <button onClick={save} className="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded text-white">Save</button>
          <div className="mt-6 text-sm">
            <Link to="/settings/providers" className="text-blue-300 hover:text-blue-200 underline">Manage Market Data Providers →</Link>
          </div>
        </div>
      </div>
    </div>
  );
};

export default SettingsPage;
