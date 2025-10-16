import { Calendar, Clock, Plus, TrendingUp, AlertCircle } from 'lucide-react';
import React, { useState, useEffect } from 'react';

import { useSecurityContext } from '../../context/SecurityContext';
// Lazy-load calendar service to avoid pulling `googleapis` (Node-only) into the browser bundle

interface CalendarEvent {
  id: string;
  summary: string;
  start: {
    dateTime?: string;
    date?: string;
  };
  end: {
    dateTime?: string;
    date?: string;
  };
  description?: string;
  location?: string;
}

const TradingCalendar: React.FC = () => {
  const { user, authenticated } = useSecurityContext();
  const [events, setEvents] = useState<CalendarEvent[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Service is loaded on demand to keep initial bundle light and avoid shim errors
  const [calendarService, setCalendarService] = useState<any | null>(null);

  useEffect(() => {
    if (!authenticated || !user) return;
    // Load the service dynamically when first needed
  (async () => {
      if (!calendarService) {
        try {
      const mod = await import('../../services/GoogleCalendarOAuthService');
      const svc = (mod.default as any).getInstance();
          setCalendarService(svc);
          await loadTradingEvents(svc);
        } catch (err) {
          setError(err instanceof Error ? err.message : 'Failed to initialize calendar service');
        }
      } else {
        await loadTradingEvents(calendarService);
      }
    })();
  }, [authenticated, user]);

  const loadTradingEvents = async (svc?: any) => {
    if (!user?.id) return;

    setLoading(true);
    setError(null);

    try {
      const service = svc || calendarService;
      if (!service) throw new Error('Calendar service not initialized');
      const tradingEvents = await service.getTradingCalendarEvents(user.id, {
        startDate: new Date(),
        endDate: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000) // Next 7 days
      });

      setEvents(tradingEvents);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load calendar events');
    } finally {
      setLoading(false);
    }
  };

  const createTradingSession = async () => {
    if (!user?.id) return;

    try {
      setLoading(true);
      
      const sessionData = {
        strategy: 'Day Trading',
        startTime: new Date(Date.now() + 60 * 60 * 1000), // 1 hour from now
        endTime: new Date(Date.now() + 4 * 60 * 60 * 1000), // 4 hours from now
        notes: 'Focus on SPY and QQQ movements',
        symbols: ['SPY', 'QQQ', 'AAPL']
      };

      if (!calendarService) {
        const mod = await import('../../services/GoogleCalendarOAuthService');
        const svc = (mod.default as any).getInstance();
        setCalendarService(svc);
        await svc.createTradingSession(user.id, sessionData);
        await loadTradingEvents(svc);
      } else {
        await calendarService.createTradingSession(user.id, sessionData);
        await loadTradingEvents(calendarService); // Refresh events
      }
      
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create trading session');
    } finally {
      setLoading(false);
    }
  };

  const formatEventTime = (event: CalendarEvent) => {
    const startTime = event.start.dateTime || event.start.date;
    const endTime = event.end.dateTime || event.end.date;
    
    if (!startTime) return 'No time specified';
    
    const start = new Date(startTime);
    const end = new Date(endTime || startTime);
    
    if (event.start.date) {
      // All-day event
      return 'All day';
    }
    
    return `${start.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} - ${end.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`;
  };

  const formatEventDate = (event: CalendarEvent) => {
    const startTime = event.start.dateTime || event.start.date;
    if (!startTime) return '';
    
    const date = new Date(startTime);
    return date.toLocaleDateString([], { 
      weekday: 'short', 
      month: 'short', 
      day: 'numeric' 
    });
  };

  if (!authenticated) {
    return (
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-lg p-6">
        <div className="text-center">
          <Calendar className="h-12 w-12 text-gray-400 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-2">
            Trading Calendar
          </h3>
          <p className="text-gray-500 dark:text-gray-400">
            Please sign in to view your trading calendar
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow-lg p-6">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center">
          <Calendar className="h-6 w-6 text-blue-600 dark:text-blue-400 mr-2" />
          <h3 className="text-lg font-medium text-gray-900 dark:text-white">
            Trading Calendar
          </h3>
        </div>
        
        <div className="flex space-x-2">
          <button
            onClick={loadTradingEvents}
            disabled={loading}
            className="inline-flex items-center px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md text-sm font-medium text-gray-700 dark:text-gray-200 bg-white dark:bg-gray-700 hover:bg-gray-50 dark:hover:bg-gray-600 disabled:opacity-50"
          >
            <Clock className="h-4 w-4 mr-1" />
            Refresh
          </button>
          
          <button
            onClick={createTradingSession}
            disabled={loading}
            className="inline-flex items-center px-3 py-2 border border-transparent rounded-md text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-50"
          >
            <Plus className="h-4 w-4 mr-1" />
            New Session
          </button>
        </div>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-100 dark:bg-red-900/20 border border-red-300 dark:border-red-700 rounded-md">
          <div className="flex items-center">
            <AlertCircle className="h-5 w-5 text-red-500 dark:text-red-400 mr-2" />
            <span className="text-sm text-red-700 dark:text-red-300">{error}</span>
          </div>
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center py-8">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
          <span className="ml-2 text-gray-600 dark:text-gray-400">Loading events...</span>
        </div>
      ) : events.length === 0 ? (
        <div className="text-center py-8">
          <TrendingUp className="h-12 w-12 text-gray-400 mx-auto mb-4" />
          <h4 className="text-lg font-medium text-gray-900 dark:text-white mb-2">
            No trading events found
          </h4>
          <p className="text-gray-500 dark:text-gray-400 mb-4">
            Create your first trading session to get started
          </p>
          <button
            onClick={createTradingSession}
            className="inline-flex items-center px-4 py-2 border border-transparent rounded-md text-sm font-medium text-white bg-blue-600 hover:bg-blue-700"
          >
            <Plus className="h-4 w-4 mr-1" />
            Create Trading Session
          </button>
        </div>
      ) : (
        <div className="space-y-3">
          {events.map((event) => (
            <div
              key={event.id}
              className="border border-gray-200 dark:border-gray-700 rounded-lg p-4 hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors"
            >
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <h4 className="text-sm font-medium text-gray-900 dark:text-white mb-1">
                    {event.summary}
                  </h4>
                  
                  <div className="flex items-center text-xs text-gray-500 dark:text-gray-400 mb-2">
                    <Calendar className="h-3 w-3 mr-1" />
                    <span>{formatEventDate(event)}</span>
                    <Clock className="h-3 w-3 ml-3 mr-1" />
                    <span>{formatEventTime(event)}</span>
                  </div>
                  
                  {event.description && (
                    <p className="text-xs text-gray-600 dark:text-gray-300 line-clamp-2">
                      {event.description}
                    </p>
                  )}
                  
                  {event.location && (
                    <p className="text-xs text-blue-600 dark:text-blue-400 mt-1">
                      📍 {event.location}
                    </p>
                  )}
                </div>
                
                <div className="flex items-center">
                  <TrendingUp className="h-4 w-4 text-green-500" />
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default TradingCalendar;
