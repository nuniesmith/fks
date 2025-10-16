import { Shield, User, Chrome, Key, AlertCircle, CheckCircle, Loader } from 'lucide-react';
import React, { useState } from 'react';

import { useSecurityContext } from '../../context/SecurityContext';

interface AuthenticationSelectorProps {
  onSignIn?: (user: any) => void;
  onError?: (error: string) => void;
  redirectUrl?: string;
  className?: string;
}

const AuthenticationSelector: React.FC<AuthenticationSelectorProps> = ({
  onSignIn,
  onError,
  redirectUrl = '/dashboard',
  className = ''
}) => {
  const { 
    authenticated, 
    user, 
    loading, 
    error,
    login,
    registerPasskey,
    vpnConnected,
    securityLevel
  } = useSecurityContext();

  // Provider 'authelia' was deprecated in favor of internal rust auth service; use 'rust' internally
  const [selectedProvider, setSelectedProvider] = useState<'rust' | 'google' | null>(null);
  const [showPasskeyOption, setShowPasskeyOption] = useState(true);
  const googleEnabled = (localStorage.getItem('security.googleOAuth') ?? (import.meta as any).env?.VITE_GOOGLE_OAUTH) === 'true';

  const handlePrimaryLogin = async (preferPasskey: boolean = true) => {
    try {
  setSelectedProvider('rust');
  const result = await login(preferPasskey, 'rust');
      
      if (typeof result === 'string') {
        // OAuth URL returned - redirect needed
        window.location.href = result;
      } else {
        // Authentication completed
        if (onSignIn && user) {
          onSignIn(user);
        }
      }
    } catch (err) {
  const errorMessage = err instanceof Error ? err.message : 'Primary authentication failed';
      if (onError) {
        onError(errorMessage);
      }
    } finally {
      setSelectedProvider(null);
    }
  };

  const handleGoogleLogin = async () => {
    try {
      setSelectedProvider('google');
      const result = await login(false, 'google'); // Don't prefer passkey for Google
      
      if (typeof result === 'string') {
        // OAuth URL returned - redirect needed
        window.location.href = result;
      } else {
        // Authentication completed
        if (onSignIn && user) {
          onSignIn(user);
        }
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Google authentication failed';
      if (onError) {
        onError(errorMessage);
      }
    } finally {
      setSelectedProvider(null);
    }
  };

  const handlePasskeyRegistration = async () => {
    try {
      await registerPasskey('Primary Device');
      setShowPasskeyOption(false);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Passkey registration failed';
      if (onError) {
        onError(errorMessage);
      }
    }
  };

  if (authenticated && user) {
    return (
      <div className={`bg-white dark:bg-gray-800 rounded-lg shadow-lg p-6 ${className}`}>
        <div className="text-center">
          <div className="flex items-center justify-center mb-4">
            <CheckCircle className="h-12 w-12 text-green-500" />
          </div>
          
          <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-2">
            Welcome back, {user.name}!
          </h3>
          
          <div className="flex items-center justify-center space-x-2 mb-4">
            {user.role === 'root' && <Shield className="h-5 w-5 text-red-500" />}
            {user.role === 'admin' && <Key className="h-5 w-5 text-blue-500" />}
            {user.role === 'user' && <User className="h-5 w-5 text-green-500" />}
            <span className="text-sm font-medium text-gray-600 dark:text-gray-400 capitalize">
              {user.role} User
            </span>
          </div>
          
          <div className="text-sm text-gray-500 dark:text-gray-400">
            Security Level: 
            <span className={`ml-1 font-medium ${
              securityLevel === 'secure' ? 'text-green-600' :
              securityLevel === 'warning' ? 'text-yellow-600' :
              'text-red-600'
            }`}>
              {securityLevel}
            </span>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={`bg-white dark:bg-gray-800 rounded-lg shadow-lg p-6 ${className}`}>
      <div className="text-center mb-6">
        <Shield className="h-12 w-12 text-blue-600 dark:text-blue-400 mx-auto mb-4" />
        <h3 className="text-xl font-semibold text-gray-900 dark:text-white mb-2">
          FKS Trading Platform
        </h3>
        <p className="text-gray-600 dark:text-gray-400">
          Secure authentication required
        </p>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-100 dark:bg-red-900/20 border border-red-300 dark:border-red-700 rounded-md">
          <div className="flex items-center">
            <AlertCircle className="h-5 w-5 text-red-500 dark:text-red-400 mr-2" />
            <span className="text-sm text-red-700 dark:text-red-300">{error}</span>
          </div>
        </div>
      )}

      {!vpnConnected && (
        <div className="mb-4 p-3 bg-yellow-100 dark:bg-yellow-900/20 border border-yellow-300 dark:border-yellow-700 rounded-md">
          <div className="flex items-center">
            <AlertCircle className="h-5 w-5 text-yellow-500 dark:text-yellow-400 mr-2" />
            <span className="text-sm text-yellow-700 dark:text-yellow-300">
              VPN connection recommended for enhanced security
            </span>
          </div>
        </div>
      )}

      <div className="space-y-4">
        {/* Primary Authentication - Authentik */}
        <div className="space-y-3">
          <h4 className="text-sm font-medium text-gray-900 dark:text-white flex items-center">
            <Shield className="h-4 w-4 mr-2 text-blue-600" />
            Primary Authentication
          </h4>
          
          <button
            onClick={() => handlePrimaryLogin(true)}
            disabled={loading}
            className="w-full flex items-center justify-center px-4 py-3 border border-transparent text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading && selectedProvider === 'rust' ? (
              <Loader className="animate-spin h-5 w-5 mr-2" />
            ) : (
              <Shield className="h-5 w-5 mr-2" />
            )}
            Sign in {showPasskeyOption && '(Passkey)'}
          </button>

          {showPasskeyOption && (
            <button
              onClick={() => handlePrimaryLogin(false)}
              disabled={loading}
              className="w-full flex items-center justify-center px-4 py-2 border border-gray-300 dark:border-gray-600 text-sm font-medium rounded-md text-gray-700 dark:text-gray-200 bg-white dark:bg-gray-700 hover:bg-gray-50 dark:hover:bg-gray-600 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50"
            >
              <Key className="h-4 w-4 mr-2" />
              Use Password Instead
            </button>
          )}
        </div>

        {/* Divider */}
        <div className="relative">
          <div className="absolute inset-0 flex items-center">
            <div className="w-full border-t border-gray-300 dark:border-gray-600" />
          </div>
          <div className="relative flex justify-center text-sm">
            <span className="px-2 bg-white dark:bg-gray-800 text-gray-500 dark:text-gray-400">
              or
            </span>
          </div>
        </div>

        {/* Alternative Authentication - Google OAuth (optional) */}
        {googleEnabled && (
          <div className="space-y-3">
            <h4 className="text-sm font-medium text-gray-900 dark:text-white flex items-center">
              <Chrome className="h-4 w-4 mr-2 text-gray-600" />
              Alternative Sign-in
            </h4>
            
            <button
              onClick={handleGoogleLogin}
              disabled={loading}
              className="w-full flex items-center justify-center px-4 py-3 border border-gray-300 dark:border-gray-600 text-sm font-medium rounded-md text-gray-700 dark:text-gray-200 bg-white dark:bg-gray-700 hover:bg-gray-50 dark:hover:bg-gray-600 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-gray-500 disabled:opacity-50"
            >
              {loading && selectedProvider === 'google' ? (
                <Loader className="animate-spin h-5 w-5 mr-2" />
              ) : (
                <Chrome className="h-5 w-5 mr-2" />
              )}
              Continue with Google
            </button>
          </div>
        )}

        {/* Passkey Registration */}
        {showPasskeyOption && (
          <>
            <div className="relative">
              <div className="absolute inset-0 flex items-center">
                <div className="w-full border-t border-gray-300 dark:border-gray-600" />
              </div>
              <div className="relative flex justify-center text-sm">
                <span className="px-2 bg-white dark:bg-gray-800 text-gray-500 dark:text-gray-400">
                  Enhanced Security
                </span>
              </div>
            </div>

            <button
              onClick={handlePasskeyRegistration}
              disabled={loading}
              className="w-full flex items-center justify-center px-4 py-2 border border-green-300 dark:border-green-600 text-sm font-medium rounded-md text-green-700 dark:text-green-200 bg-green-50 dark:bg-green-900/20 hover:bg-green-100 dark:hover:bg-green-900/30 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-green-500 disabled:opacity-50"
            >
              <Key className="h-4 w-4 mr-2" />
              Register Passkey (Recommended)
            </button>
          </>
        )}
      </div>

      <div className="mt-6 text-center">
        <p className="text-xs text-gray-500 dark:text-gray-400">
          Secure • Open Source • Privacy Focused
        </p>
      </div>
    </div>
  );
};

export default AuthenticationSelector;
