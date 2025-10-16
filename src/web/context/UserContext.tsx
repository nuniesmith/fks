import React, { createContext, useContext, useState, useEffect } from 'react';

import { useSecurityContext } from './SecurityContext';

import type { User, UserPermissions, UserPreferences } from '../types/user';


interface UserContextType {
  user: User | null;
  isAuthenticated: boolean;
  isAdmin: boolean;
  isDeveloper: boolean;
  login: (email: string, password: string) => Promise<boolean>;
  logout: () => void;
  updatePreferences: (preferences: Partial<UserPreferences>) => void;
  hasPermission: (permission: keyof UserPermissions) => boolean;
  canAccessFeature: (feature: string) => boolean;
}

const UserContext = createContext<UserContextType | undefined>(undefined);

export const useUser = () => {
  const context = useContext(UserContext);
  if (context === undefined) {
    throw new Error('useUser must be used within a UserProvider');
  }
  return context;
};

interface UserProviderProps {
  children: React.ReactNode;
}

export const UserProvider: React.FC<UserProviderProps> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const security = useSecurityContext();

  // Mock users for development
  const mockUsers: User[] = [
    {
      id: 'dev-1',
      email: 'nunie.smith01@gmail.com',
      name: 'Jordan (Developer)',
      role: 'developer',
      preferences: {
        timezone: 'America/Toronto',
        theme: 'dark',
        notifications: {
          email: true,
          push: true,
          tradingAlerts: true,
          marketNews: true,
          developmentUpdates: true
        },
        calendar: {
          showMarketEvents: true,
          showHolidays: true,
          showDevelopment: true,
          defaultView: 'week',
          workingHours: {
            start: '09:00',
            end: '17:00',
            timezone: 'America/Toronto'
          }
        },
        trading: {
          defaultRiskPercent: 1.5,
          preferredMarkets: ['FOREX', 'FUTURES'],
          alertThresholds: {
            dailyLoss: 500,
            weeklyLoss: 2000,
            monthlyLoss: 5000
          }
        }
      },
      createdAt: '2024-01-01T00:00:00Z',
      lastActive: new Date().toISOString(),
      status: 'active',
      permissions: {
        canAccessDevelopment: true,
        canManageUsers: true,
        canViewAnalytics: true,
        canModifySystem: true,
        canAccessMarketData: true,
        canManageCalendar: true,
        maxAccounts: 999,
        features: {
          tradingDashboard: true,
          taxOptimization: true,
          milestoneSystem: true,
          calendar: true,
          advancedAnalytics: true
        }
      }
    },
    {
      id: 'user-1',
      email: 'testuser@example.com',
      name: 'Test User',
      role: 'user',
      preferences: {
        timezone: 'America/Toronto',
        theme: 'dark',
        notifications: {
          email: true,
          push: false,
          tradingAlerts: true,
          marketNews: true,
          developmentUpdates: false
        },
        calendar: {
          showMarketEvents: true,
          showHolidays: true,
          showDevelopment: false,
          defaultView: 'week',
          workingHours: {
            start: '09:00',
            end: '17:00',
            timezone: 'America/Toronto'
          }
        },
        trading: {
          defaultRiskPercent: 2.0,
          preferredMarkets: ['FOREX'],
          alertThresholds: {
            dailyLoss: 200,
            weeklyLoss: 800,
            monthlyLoss: 2000
          }
        }
      },
      createdAt: '2024-06-01T00:00:00Z',
      lastActive: new Date().toISOString(),
      status: 'active',
      permissions: {
        canAccessDevelopment: false,
        canManageUsers: false,
        canViewAnalytics: false,
        canModifySystem: false,
        canAccessMarketData: true,
        canManageCalendar: false,
        maxAccounts: 5,
        features: {
          tradingDashboard: true,
          taxOptimization: true,
          milestoneSystem: true,
          calendar: true,
          advancedAnalytics: false
        }
      }
    }
  ];

  useEffect(() => {
    // If security context has an authenticated SSO user, map it
    const ssoUser = security?.user;
    if (security?.authenticated && ssoUser) {
      const groups: string[] = ssoUser.groups || [];
      const computedRole: User['role'] = (() => {
        const lower = groups.map((g: string) => g.toLowerCase());
        if (lower.some((g: string) => ['root', 'owner'].includes(g))) return 'admin';
        if (lower.some((g: string) => ['admin', 'developer', 'dev'].includes(g))) return 'developer';
        return 'user';
      })();

      const mapped: User = {
        id: ssoUser.id || ssoUser.pk?.toString?.() || ssoUser.sub || 'sso-user',
        email: ssoUser.email || ssoUser.username || 'unknown@local',
        name: ssoUser.name || ssoUser.username || 'User',
        role: computedRole,
        avatar: ssoUser.picture,
        preferences: (JSON.parse(localStorage.getItem('fks_user_prefs') || 'null') as User['preferences']) || mockUsers[1].preferences,
        createdAt: new Date().toISOString(),
        lastActive: new Date().toISOString(),
        status: 'active',
        permissions: computedRole === 'user' ? mockUsers[1].permissions : mockUsers[0].permissions
      };
      setUser(mapped);
      setIsAuthenticated(true);
      localStorage.setItem('fks_user', JSON.stringify(mapped));
      return;
    }

    // Otherwise fallback to stored user or dev mock (dev mode only)
    const storedUser = localStorage.getItem('fks_user');
    if (storedUser) {
      const userData = JSON.parse(storedUser);
      setUser(userData);
      setIsAuthenticated(true);
      return;
    }

    if (import.meta.env.DEV) {
      const devUser = mockUsers[0];
      setUser(devUser);
      setIsAuthenticated(true);
      localStorage.setItem('fks_user', JSON.stringify(devUser));
    } else {
      setUser(null);
      setIsAuthenticated(false);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [security?.authenticated, security?.user]);

  const login = async (identifier: string, password: string): Promise<boolean> => {
    const creds: Record<string, { password: string; email: string }> = {
      'jordan': { password: '567326', email: 'nunie.smith01@gmail.com' },
    }
    const key = identifier.toLowerCase()
    const record = creds[key]
    if (record && record.password === password) {
      const email = record.email.toLowerCase()
      const foundUser = mockUsers.find(u => u.email.toLowerCase() === email)
      if (!foundUser) return false
      const authd = { ...foundUser, lastActive: new Date().toISOString() }
      setUser(authd)
      setIsAuthenticated(true)
      localStorage.setItem('fks_user', JSON.stringify(authd))
      try { localStorage.setItem('auth_tokens', JSON.stringify({ access: 'local-demo-token', ts: Date.now() })) } catch {}
      return true
    }
    return false
  }

  const logout = () => {
    setUser(null);
    setIsAuthenticated(false);
    localStorage.removeItem('fks_user');
  try { localStorage.removeItem('auth_tokens'); } catch {}
  };

  const updatePreferences = (newPreferences: Partial<UserPreferences>) => {
    if (user) {
      const updatedUser = {
        ...user,
        preferences: { ...user.preferences, ...newPreferences }
      };
      setUser(updatedUser);
      localStorage.setItem('fks_user', JSON.stringify(updatedUser));
    }
  };

  const hasPermission = (permission: keyof UserPermissions): boolean => {
    if (!user) return false;
    const value = user.permissions[permission];
    return typeof value === 'boolean' ? value : false;
  };

  const canAccessFeature = (feature: string): boolean => {
    return user?.permissions.features[feature as keyof typeof user.permissions.features] || false;
  };

  const isAdmin = user?.role === 'admin';
  const isDeveloper = user?.role === 'developer' || user?.role === 'admin';

  return (
    <UserContext.Provider value={{
      user,
      isAuthenticated,
      isAdmin,
      isDeveloper,
      login,
      logout,
      updatePreferences,
      hasPermission,
      canAccessFeature
    }}>
      {children}
    </UserContext.Provider>
  );
};
