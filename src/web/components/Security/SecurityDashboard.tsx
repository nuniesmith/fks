import { Shield, Wifi, Lock, AlertTriangle, CheckCircle, XCircle, Activity } from 'lucide-react';
import React, { useState, useEffect } from 'react';

import { useSecurityContext } from '../../context/SecurityContext';

interface SecurityDashboardProps {
  showDetails?: boolean;
  className?: string;
}

const SecurityDashboard: React.FC<SecurityDashboardProps> = ({
  showDetails = false,
  className = ''
}) => {
  const {
    initialized,
    vpnConnected,
    authenticated,
    user,
    securityLevel,
    loading,
    error,
    getSecurityDashboard,
    validateSecurity,
    registerPasskey
  } = useSecurityContext();

  const [dashboardData, setDashboardData] = useState<any>(null);
  const [showPasskeyPrompt, setShowPasskeyPrompt] = useState(false);

  useEffect(() => {
    if (initialized) {
      try {
        const data = getSecurityDashboard();
        setDashboardData(data);
      } catch (error) {
        console.error('Failed to load security dashboard:', error);
      }
    }
  }, [initialized, getSecurityDashboard]);

  const getSecurityLevelColor = (level: string) => {
    switch (level) {
      case 'secure': return 'text-green-600 bg-green-50';
      case 'warning': return 'text-yellow-600 bg-yellow-50';
      case 'critical': return 'text-red-600 bg-red-50';
      default: return 'text-gray-600 bg-gray-50';
    }
  };

  const getSecurityIcon = (level: string) => {
    switch (level) {
      case 'secure': return CheckCircle;
      case 'warning': return AlertTriangle;
      case 'critical': return XCircle;
      default: return Shield;
    }
  };

  const handleRefreshSecurity = async () => {
    try {
      await validateSecurity();
      const data = getSecurityDashboard();
      setDashboardData(data);
    } catch (error) {
      console.error('Security refresh failed:', error);
    }
  };

  const handleRegisterPasskey = async () => {
    try {
      const deviceName = `${navigator.platform} - ${new Date().toLocaleDateString()}`;
      await registerPasskey(deviceName);
      setShowPasskeyPrompt(false);
      await handleRefreshSecurity();
    } catch (error) {
      console.error('Passkey registration failed:', error);
    }
  };

  if (!initialized) {
    return (
      <div className={`p-4 bg-gray-50 rounded-lg ${className}`}>
        <div className="flex items-center space-x-2">
          <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-600"></div>
          <span className="text-sm text-gray-600">Initializing security...</span>
        </div>
      </div>
    );
  }

  const SecurityIcon = getSecurityIcon(securityLevel);

  return (
    <div className={`bg-white rounded-lg shadow-sm border ${className}`}>
      {/* Header */}
      <div className="p-4 border-b">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className={`p-2 rounded-lg ${getSecurityLevelColor(securityLevel)}`}>
              <SecurityIcon className="h-5 w-5" />
            </div>
            <div>
              <h3 className="font-semibold text-gray-900">Security Status</h3>
              <p className="text-sm text-gray-500 capitalize">{securityLevel}</p>
            </div>
          </div>
          <button
            onClick={handleRefreshSecurity}
            disabled={loading}
            className="p-2 text-gray-400 hover:text-gray-600 transition-colors"
          >
            <Activity className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Status Indicators */}
      <div className="p-4 space-y-3">
        {/* VPN Status */}
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <Wifi className={`h-4 w-4 ${vpnConnected ? 'text-green-600' : 'text-red-600'}`} />
            <span className="text-sm font-medium">Tailscale VPN</span>
          </div>
          <span className={`text-xs px-2 py-1 rounded-full ${
            vpnConnected 
              ? 'text-green-700 bg-green-100' 
              : 'text-red-700 bg-red-100'
          }`}>
            {vpnConnected ? 'Connected' : 'Disconnected'}
          </span>
        </div>

        {/* Authentication Status */}
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <Lock className={`h-4 w-4 ${authenticated ? 'text-green-600' : 'text-red-600'}`} />
            <span className="text-sm font-medium">Authentication</span>
          </div>
          <span className={`text-xs px-2 py-1 rounded-full ${
            authenticated 
              ? 'text-green-700 bg-green-100' 
              : 'text-red-700 bg-red-100'
          }`}>
            {authenticated ? 'Authenticated' : 'Not Authenticated'}
          </span>
        </div>

        {/* User Info */}
        {authenticated && user && (
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <div className="h-4 w-4 rounded-full bg-blue-600 flex items-center justify-center">
                <span className="text-xs text-white font-medium">
                  {user.name?.charAt(0) || user.username?.charAt(0) || 'U'}
                </span>
              </div>
              <span className="text-sm font-medium">User</span>
            </div>
            <span className="text-xs text-gray-600">
              {user.name || user.username}
            </span>
          </div>
        )}
      </div>

      {/* Error Display */}
      {error && (
        <div className="p-4 border-t bg-red-50">
          <div className="flex items-center space-x-2">
            <AlertTriangle className="h-4 w-4 text-red-600" />
            <span className="text-sm text-red-700">{error}</span>
          </div>
        </div>
      )}

      {/* Passkey Prompt */}
      {authenticated && !showPasskeyPrompt && (
        <div className="p-4 border-t bg-blue-50">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <Shield className="h-4 w-4 text-blue-600" />
              <span className="text-sm text-blue-700">Enhance security with passkeys</span>
            </div>
            <button
              onClick={() => setShowPasskeyPrompt(true)}
              className="text-xs px-3 py-1 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors"
            >
              Set Up
            </button>
          </div>
        </div>
      )}

      {/* Passkey Registration */}
      {showPasskeyPrompt && (
        <div className="p-4 border-t bg-blue-50">
          <div className="space-y-3">
            <div className="flex items-center space-x-2">
              <Shield className="h-4 w-4 text-blue-600" />
              <span className="text-sm font-medium text-blue-700">Register Passkey</span>
            </div>
            <p className="text-xs text-blue-600">
              Passkeys provide passwordless authentication using your device's biometrics or security key.
            </p>
            <div className="flex space-x-2">
              <button
                onClick={handleRegisterPasskey}
                disabled={loading}
                className="text-xs px-3 py-1 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors disabled:opacity-50"
              >
                {loading ? 'Registering...' : 'Register Passkey'}
              </button>
              <button
                onClick={() => setShowPasskeyPrompt(false)}
                className="text-xs px-3 py-1 text-blue-600 border border-blue-600 rounded-md hover:bg-blue-50 transition-colors"
              >
                Skip
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Detailed Information */}
      {showDetails && dashboardData && (
        <div className="p-4 border-t bg-gray-50">
          <h4 className="text-sm font-medium text-gray-900 mb-3">Security Insights</h4>
          <div className="space-y-2">
            {dashboardData.insights?.map((insight: string, index: number) => (
              <div key={index} className="flex items-start space-x-2">
                <div className="h-1.5 w-1.5 rounded-full bg-gray-400 mt-2"></div>
                <span className="text-xs text-gray-600">{insight}</span>
              </div>
            ))}
            {(!dashboardData.insights || dashboardData.insights.length === 0) && (
              <span className="text-xs text-gray-500">No security issues detected</span>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default SecurityDashboard;
