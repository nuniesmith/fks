import { useContext } from 'react';
import { NotificationContext } from './notificationContext';
import type { NotificationContextType } from './notificationTypes';

export const useNotifications = () => {
  const ctx = useContext<NotificationContextType | undefined>(NotificationContext);
  if (!ctx) {
    throw new Error('useNotifications must be used within a NotificationProvider');
  }
  return ctx;
};
