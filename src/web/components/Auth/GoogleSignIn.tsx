import { Shield, User, Users, Crown, Chrome, AlertCircle, CheckCircle, Loader } from 'lucide-react';
import React, { useState, useEffect } from 'react';

import { useSecurityContext } from '../../context/SecurityContext';

interface GoogleSignInProps {
  onSignIn?: (user: any) => void;
  onError?: (error: string) => void;
  redirectUrl?: string;
  className?: string;
}

const GoogleSignIn: React.FC<GoogleSignInProps> = ({
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
    completeLogin, 
    logout,
    vpnConnected,
    securityLevel
  } = useSecurityContext();

  const [isSigningIn, setIsSigningIn] = useState(false);
  const [showUserInfo, setShowUserInfo] = useState(false);
  const googleEnabled = (localStorage.getItem('security.googleOAuth') ?? (import.meta as any).env?.VITE_GOOGLE_OAUTH) === 'true';

  // Handle OAuth callback if we're on the callback URL
  useEffect(() => {
    const urlParams = new URLSearchParams(window.location.search);
    const code = urlParams.get('code');
    const state = urlParams.get('state');
    const error = urlParams.get('error');

    if (error) {
      console.error('OAuth error:', error);
      onError?.(`Authentication failed: ${error}`);
      return;
    }

    if (code && state) {
      handleOAuthCallback(code, state);
    }
  }, []);

  const handleOAuthCallback = async (code: string, state: string) => {
    try {
      setIsSigningIn(true);
      const user = await completeLogin(code, state);
      
      onSignIn?.(user);
      
      // Redirect to desired page
      if (redirectUrl && window.location.pathname.includes('/auth/')) {
        window.location.href = redirectUrl;
      }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Authentication failed';
      onError?.(errorMessage);
    } finally {
      setIsSigningIn(false);
    }
  };

  const handleSignIn = async () => {
    try {
      if (!googleEnabled) {
        throw new Error('Google sign-in is disabled in this environment');
      }
      setIsSigningIn(true);
      const authUrl = await login(false, 'google'); // Explicitly use Google OAuth
      
      if (typeof authUrl === 'string') {
        // Redirect to Google OAuth
        window.location.href = authUrl;
      }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Sign-in failed';
      onError?.(errorMessage);
      setIsSigningIn(false);
    }
  };

  const handleSignOut = async () => {
    try {
      await logout();
      setShowUserInfo(false);
    } catch (error) {
      console.error('Sign out failed:', error);
    }
  };

  const getRoleIcon = (role: string) => {
    switch (role) {
      case 'root': return Crown;
      case 'admin': return Shield;
      case 'user': return User;
      default: return Users;
    }
  };

  const getRoleColor = (role: string) => {
    switch (role) {
      case 'root': return 'text-purple-600 bg-purple-50 border-purple-200';
      case 'admin': return 'text-blue-600 bg-blue-50 border-blue-200';
      case 'user': return 'text-green-600 bg-green-50 border-green-200';
      default: return 'text-gray-600 bg-gray-50 border-gray-200';
    }
  };

  const getSecurityStatusColor = (level: string) => {
    switch (level) {
      case 'secure': return 'text-green-600';
      case 'warning': return 'text-yellow-600';
      case 'critical': return 'text-red-600';
      default: return 'text-gray-600';
    }
  };

  // Show loading state during sign in
  if (isSigningIn || loading) {
    return (
      <div className={`flex items-center justify-center p-8 ${className}`}>
        <div className="text-center">
          <Loader className="h-8 w-8 animate-spin text-blue-600 mx-auto mb-4" />
          <p className="text-gray-600">
            {isSigningIn ? 'Signing you in...' : 'Loading...'}
          </p>
        </div>
      </div>
    );
  }

  // Show user info if authenticated
  if (authenticated && user) {
    const RoleIcon = getRoleIcon(user.role);
    
    return (
      <div className={`bg-white rounded-lg shadow-sm border ${className}`}>
        <div className="p-4">
          <div className="flex items-start justify-between">
            <div className="flex items-center space-x-3">
              {user.picture ? (
                <img 
                  src={user.picture} 
                  alt={user.name} 
                  className="h-10 w-10 rounded-full"
                />
              ) : (
                <div className="h-10 w-10 rounded-full bg-blue-100 flex items-center justify-center">
                  <User className="h-5 w-5 text-blue-600" />
                </div>
              )}
              
              <div>
                <div className="flex items-center space-x-2">
                  <h3 className="font-semibold text-gray-900">{user.name}</h3>
                  <div className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium border ${getRoleColor(user.role)}`}>
                    <RoleIcon className="h-3 w-3 mr-1" />
                    {user.role.toUpperCase()}
                  </div>
                </div>
                <p className="text-sm text-gray-500">{user.email}</p>
                
                {/* Security Status */}
                <div className="flex items-center mt-1 space-x-4">
                  <div className="flex items-center space-x-1">
                    {vpnConnected ? (
                      <CheckCircle className="h-3 w-3 text-green-600" />
                    ) : (
                      <AlertCircle className="h-3 w-3 text-red-600" />
                    )}
                    <span className="text-xs text-gray-500">
                      VPN: {vpnConnected ? 'Connected' : 'Disconnected'}
                    </span>
                  </div>
                  <div className="flex items-center space-x-1">
                    <Shield className={`h-3 w-3 ${getSecurityStatusColor(securityLevel)}`} />
                    <span className="text-xs text-gray-500 capitalize">
                      Security: {securityLevel}
                    </span>
                  </div>
                </div>
              </div>
            </div>

            <div className="flex items-center space-x-2">
              <button
                onClick={() => setShowUserInfo(!showUserInfo)}
                className="p-1 text-gray-400 hover:text-gray-600 transition-colors"
              >
                <User className="h-4 w-4" />
              </button>
              <button
                onClick={handleSignOut}
                className="text-sm px-3 py-1 text-red-600 border border-red-600 rounded-md hover:bg-red-50 transition-colors"
              >
                Sign Out
              </button>
            </div>
          </div>

          {/* Extended User Info */}
          {showUserInfo && (
            <div className="mt-4 pt-4 border-t border-gray-100">
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <label className="font-medium text-gray-700">User ID:</label>
                  <p className="text-gray-600 font-mono text-xs">{user.id}</p>
                </div>
                <div>
                  <label className="font-medium text-gray-700">Last Login:</label>
                  <p className="text-gray-600">{new Date(user.lastLogin).toLocaleString()}</p>
                </div>
                <div>
                  <label className="font-medium text-gray-700">Created:</label>
                  <p className="text-gray-600">{new Date(user.createdAt).toLocaleDateString()}</p>
                </div>
                <div>
                  <label className="font-medium text-gray-700">Status:</label>
                  <p className={`${user.isActive ? 'text-green-600' : 'text-red-600'}`}>
                    {user.isActive ? 'Active' : 'Inactive'}
                  </p>
                </div>
              </div>
              
              {/* Permissions */}
              {user.permissions && user.permissions.length > 0 && (
                <div className="mt-3">
                  <label className="font-medium text-gray-700">Permissions:</label>
                  <div className="mt-1 flex flex-wrap gap-1">
                    {user.permissions.slice(0, 6).map((permission: string, index: number) => (
                      <span
                        key={index}
                        className="text-xs px-2 py-1 bg-gray-100 text-gray-600 rounded-md font-mono"
                      >
                        {permission}
                      </span>
                    ))}
                    {user.permissions.length > 6 && (
                      <span className="text-xs px-2 py-1 bg-gray-100 text-gray-600 rounded-md">
                        +{user.permissions.length - 6} more
                      </span>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    );
  }

  // Show sign-in interface
  return (
    <div className={`bg-white rounded-lg shadow-sm border ${className}`}>
      <div className="p-6">
        <div className="text-center">
          <div className="mx-auto h-12 w-12 bg-blue-100 rounded-full flex items-center justify-center">
            <Chrome className="h-6 w-6 text-blue-600" />
          </div>
          
          <h2 className="mt-4 text-lg font-semibold text-gray-900">
            Sign in to FKS Trading
          </h2>
          <p className="mt-2 text-sm text-gray-600">
            Access your secure trading platform with Google
          </p>

          {!googleEnabled && (
            <div className="mt-4 p-3 bg-amber-50 border border-amber-200 rounded-md text-left">
              <div className="flex items-start space-x-2">
                <AlertCircle className="h-4 w-4 text-amber-600 mt-0.5" />
                <div>
                  <p className="text-sm text-amber-800 font-medium">Google sign-in is disabled</p>
                  <p className="text-xs text-amber-700 mt-1">Enable by setting localStorage security.googleOAuth = 'true' and ensure a backend proxy handles Google API calls.</p>
                </div>
              </div>
            </div>
          )}

          {/* Security Status Warning */}
          {!vpnConnected && (
            <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-md">
              <div className="flex items-center space-x-2">
                <AlertCircle className="h-4 w-4 text-red-600" />
                <span className="text-sm text-red-700">
                  VPN connection required for secure access
                </span>
              </div>
            </div>
          )}

          {error && (
            <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-md">
              <div className="flex items-center space-x-2">
                <AlertCircle className="h-4 w-4 text-red-600" />
                <span className="text-sm text-red-700">{error}</span>
              </div>
            </div>
          )}

          <button
            onClick={handleSignIn}
            disabled={isSigningIn || !vpnConnected || !googleEnabled}
            className={`mt-6 w-full flex items-center justify-center px-4 py-2 border rounded-md text-sm font-medium transition-colors ${
              (!vpnConnected || !googleEnabled)
                ? 'border-gray-300 text-gray-400 bg-gray-50 cursor-not-allowed'
                : 'border-blue-600 text-blue-600 hover:bg-blue-50 focus:outline-none focus:ring-2 focus:ring-blue-500'
            }`}
          >
            <Chrome className="h-4 w-4 mr-2" />
            {isSigningIn ? 'Signing in...' : 'Sign in with Google'}
          </button>

          <div className="mt-4 text-xs text-gray-500">
            <p>
              By signing in, you agree to our terms of service and privacy policy.
              <br />
              Only authorized users can access this platform.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default GoogleSignIn;
