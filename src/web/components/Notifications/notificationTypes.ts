import React from 'react';

export interface Notification {
  id: string;
  type: 'achievement' | 'levelUp' | 'xp' | 'milestone' | 'warning' | 'success';
  title: string;
  message: string;
  icon?: React.ReactNode;
  duration?: number;
  action?: { label: string; onClick: () => void };
  timestamp: Date;
}

export interface NotificationContextType {
  notifications: Notification[];
  addNotification: (notification: Omit<Notification, 'id' | 'timestamp'>) => void;
  removeNotification: (id: string) => void;
  clearAll: () => void;
}
