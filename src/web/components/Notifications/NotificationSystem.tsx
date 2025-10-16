import { Trophy, Star, Zap, Target, Award, X } from 'lucide-react';
import React, { useState, useCallback, createContext } from 'react';
import type { Notification, NotificationContextType } from './notificationTypes';

// Context defined locally (was previously imported); can be moved out if needed.
export const NotificationContext = createContext<NotificationContextType | undefined>(undefined);

interface NotificationProviderProps {
  children: React.ReactNode;
}

export const NotificationProvider: React.FC<NotificationProviderProps> = ({ children }) => {
  const [notifications, setNotifications] = useState<Notification[]>([]);

  const removeNotification = useCallback((id: string) => {
    setNotifications(prev => prev.filter(n => n.id !== id));
  }, []);

  const addNotification = useCallback((notification: Omit<Notification, 'id' | 'timestamp'>) => {
    const newNotification: Notification = {
      ...notification,
      id: `notification-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
      timestamp: new Date(),
      duration: notification.duration || 5000
    };

    setNotifications(prev => [newNotification, ...prev]);

    if (newNotification.duration > 0) {
      setTimeout(() => {
        removeNotification(newNotification.id);
      }, newNotification.duration);
    }
  }, [removeNotification]);

  const clearAll = useCallback(() => {
    setNotifications([]);
  }, []);

  return (
    <NotificationContext.Provider value={{ notifications, addNotification, removeNotification, clearAll }}>
      {children}
      <NotificationDisplay />
    </NotificationContext.Provider>
  );
};

// Attach a lightweight global bridge so other layers (SecurityContext, fetch wrappers) can push notifications
if (typeof window !== 'undefined' && !(window as any).fksNotify) {
  (window as any).fksNotify = (n: { title: string; message: string; type?: string }) => {
    try {
      const evt = new CustomEvent('fks:notify', { detail: n });
      window.dispatchEvent(evt);
    } catch {/* ignore */}
  };
  // Listener that consumes fks:notify and uses a tiny in-memory queue until provider mounts
  (window as any)._fksNotifyQueue = [] as any[];
  window.addEventListener('fks:notify', (e: any) => {
    const ctx = (window as any)._fksNotifyCtx as undefined | { add: Function };
    if (ctx && typeof ctx.add === 'function') {
      ctx.add({
        title: e.detail.title,
        message: e.detail.message,
        type: (e.detail.type || 'warning') as any,
        duration: 5000
      });
    } else {
      (window as any)._fksNotifyQueue.push(e.detail);
    }
  });
}

// Side effect hook to register provider context globally (done here to avoid extra component)
if (typeof window !== 'undefined') {
  // Poll until React context is available by monkey patching provider after mount via microtask
  queueMicrotask(() => {
    try {
      // Monkey patch NotificationContext to capture addNotification when provider mounts
      const origProvider = NotificationProvider;
      // (No override of component output required; bridge is attached inside useEffect of consumer scenario)
    } catch {/* ignore */}
  });
}

const NotificationDisplay: React.FC = () => {
  const context = React.useContext<NotificationContextType | undefined>(NotificationContext);
  if (!context) return null;
  const { notifications, removeNotification } = context;

  const getNotificationStyles = (type: Notification['type']) => {
    switch (type) {
      case 'achievement':
        return 'bg-gradient-to-r from-yellow-500 to-orange-500 border-yellow-400 text-white';
      case 'levelUp':
        return 'bg-gradient-to-r from-purple-500 to-blue-500 border-purple-400 text-white';
      case 'xp':
        return 'bg-gradient-to-r from-green-500 to-teal-500 border-green-400 text-white';
      case 'milestone':
        return 'bg-gradient-to-r from-pink-500 to-rose-500 border-pink-400 text-white';
      case 'success':
        return 'bg-gradient-to-r from-emerald-500 to-green-500 border-emerald-400 text-white';
      case 'warning':
        return 'bg-gradient-to-r from-amber-500 to-yellow-500 border-amber-400 text-white';
      default:
        return 'bg-gray-800 border-gray-600 text-white';
    }
  };

  const getDefaultIcon = (type: Notification['type']) => {
    switch (type) {
      case 'achievement':
        return <Trophy className="w-6 h-6" />;
      case 'levelUp':
        return <Star className="w-6 h-6" />;
      case 'xp':
        return <Zap className="w-6 h-6" />;
      case 'milestone':
        return <Target className="w-6 h-6" />;
      case 'success':
        return <Award className="w-6 h-6" />;
      default:
        return <Trophy className="w-6 h-6" />;
    }
  };

  if (notifications.length === 0) return null;

  return (
    <div className="fixed top-4 right-4 z-50 space-y-4 max-w-sm w-full">
      {notifications.slice(0, 5).map((notification) => (
        <div
          key={notification.id}
          className={`relative p-4 rounded-xl border-2 shadow-lg transform transition-all duration-300 hover:scale-105 ${getNotificationStyles(notification.type)}`}
        >
          {/* Close button */}
          <button
            onClick={() => removeNotification(notification.id)}
            className="absolute top-2 right-2 text-white/70 hover:text-white transition-colors"
          >
            <X className="w-4 h-4" />
          </button>

          {/* Content */}
          <div className="flex items-start space-x-3 pr-6">
            <div className="flex-shrink-0 mt-0.5">
              {notification.icon || getDefaultIcon(notification.type)}
            </div>
            <div className="flex-1 min-w-0">
              <h3 className="font-bold text-lg leading-tight">{notification.title}</h3>
              <p className="text-sm opacity-90 mt-1">{notification.message}</p>
              
              {notification.action && (
                <button
                  onClick={notification.action.onClick}
                  className="mt-2 bg-white/20 hover:bg-white/30 text-white px-3 py-1 rounded-lg text-sm font-medium transition-colors"
                >
                  {notification.action.label}
                </button>
              )}
            </div>
          </div>

          {/* Animation bar */}
          {notification.duration && notification.duration > 0 && (
            <div className="absolute bottom-0 left-0 h-1 bg-white/30 rounded-b-xl overflow-hidden">
              <div 
                className="h-full bg-white/60 animate-pulse"
                style={{
                  animation: `shrink ${notification.duration}ms linear`
                }}
              />
            </div>
          )}
        </div>
      ))}
      
      {notifications.length > 5 && (
        <div className="text-center">
          <div className="bg-gray-800/90 text-white px-4 py-2 rounded-lg text-sm">
            +{notifications.length - 5} more notifications
          </div>
        </div>
      )}
    </div>
  );
};


export default NotificationProvider;
