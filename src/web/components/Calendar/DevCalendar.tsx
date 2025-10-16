import { Calendar, Clock, Plus, Settings, Users, FileText, AlertTriangle, TrendingUp, Zap } from 'lucide-react';
import PageContainer from '@layout/PageContainer';
import React, { useState, useEffect } from 'react';

import { useUser } from '../../context/UserContext';
import { CalendarService } from '../../services/CalendarService';

import type { CalendarEvent, DevelopmentTask, MarketEvent } from '../../types/user';

const DevCalendar: React.FC = () => {
  const { user, isDeveloper } = useUser();
  const [selectedDate, setSelectedDate] = useState(new Date());
  const [viewMode, setViewMode] = useState<'day' | 'week' | 'month'>('week');
  const [events, setEvents] = useState<CalendarEvent[]>([]);
  const [developmentTasks, setDevelopmentTasks] = useState<DevelopmentTask[]>([]);
  const [marketEvents, setMarketEvents] = useState<MarketEvent[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const calendarService = CalendarService.getInstance();

  useEffect(() => {
    loadCalendarData();
  }, [user]);

  const loadCalendarData = async () => {
    if (!user) return;
    
    setIsLoading(true);
    try {
      const startDate = new Date();
      startDate.setDate(startDate.getDate() - 7); // Load previous week
      const endDate = new Date();
      endDate.setDate(endDate.getDate() + 30); // Load next month

      const calendarEvents = await calendarService.getCalendarEvents(startDate, endDate, user.role);
      setEvents(calendarEvents);

      if (isDeveloper) {
        const devTasks = calendarService.getDevelopmentTasks();
        setDevelopmentTasks(devTasks);
      }

      const marketData = calendarService.getMarketEventsData();
      setMarketEvents(marketData);
    } catch (error) {
      console.error('Failed to load calendar data:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const getEventTypeColor = (type: string) => {
    switch (type) {
      case 'development': return 'bg-blue-500/20 text-blue-300 border-blue-500/50';
      case 'trading': return 'bg-green-500/20 text-green-300 border-green-500/50';
      case 'research': return 'bg-purple-500/20 text-purple-300 border-purple-500/50';
      case 'meeting': return 'bg-orange-500/20 text-orange-300 border-orange-500/50';
      default: return 'bg-gray-500/20 text-gray-300 border-gray-500/50';
    }
  };

  const getEventTypeIcon = (type: string) => {
    switch (type) {
      case 'development': return '💻';
      case 'trading': return '📈';
      case 'research': return '🔍';
      case 'meeting': return '👥';
      default: return '📅';
    }
  };

  const formatTime = (dateString: string) => {
    return new Date(dateString).toLocaleTimeString('en-CA', {
      hour: '2-digit',
      minute: '2-digit',
      hour12: false
    });
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-CA', {
      weekday: 'short',
      month: 'short',
      day: 'numeric'
    });
  };

  const getDaysInWeek = (date: Date) => {
    const week = [];
    const startOfWeek = new Date(date);
    const dayOfWeek = startOfWeek.getDay();
    startOfWeek.setDate(startOfWeek.getDate() - dayOfWeek);

    for (let i = 0; i < 7; i++) {
      const day = new Date(startOfWeek);
      day.setDate(startOfWeek.getDate() + i);
      week.push(day);
    }
    return week;
  };

  const getEventsForDate = (date: Date) => {
    const dateStr = date.toISOString().split('T')[0];
    return events.filter(event => 
      event.start.startsWith(dateStr)
    );
  };

  const connectGoogleCalendar = async () => {
    setIsLoading(true);
    try {
      const success = await calendarService.connectGoogleCalendar();
      if (success) {
        await loadCalendarData(); // Reload data after connection
        alert('Google Calendar connected successfully!');
      }
    } catch (error) {
      alert('Failed to connect Google Calendar');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <PageContainer>
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-4xl font-bold text-white mb-2">Development Calendar</h1>
              <p className="text-white/70">Organize your trading development and research work</p>
            </div>
            <div className="flex items-center gap-4">
              {!calendarService.isGoogleCalendarConnected() && (
                <button
                  onClick={connectGoogleCalendar}
                  className="px-4 py-2 bg-blue-500/20 hover:bg-blue-500/30 rounded-lg border border-blue-500/30 text-blue-300 font-medium transition-colors"
                >
                  Connect Google Calendar
                </button>
              )}
              <button className="p-2 bg-white/10 hover:bg-white/20 rounded-lg border border-white/20 transition-colors">
                <Settings className="h-5 w-5 text-white/80" />
              </button>
            </div>
          </div>
        </div>

        {/* Calendar Controls */}
        <div className="glass-card p-6 mb-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <h2 className="text-2xl font-bold text-white">
                {selectedDate.toLocaleDateString('en-CA', { 
                  month: 'long', 
                  year: 'numeric' 
                })}
              </h2>
              <div className="flex gap-2">
                {['day', 'week', 'month'].map((mode) => (
                  <button
                    key={mode}
                    onClick={() => setViewMode(mode as any)}
                    className={`px-3 py-1 rounded text-sm font-medium transition-colors ${
                      viewMode === mode
                        ? 'bg-blue-500/30 text-blue-300 border border-blue-500/50'
                        : 'bg-white/10 text-white/70 border border-white/20 hover:bg-white/20'
                    }`}
                  >
                    {mode.charAt(0).toUpperCase() + mode.slice(1)}
                  </button>
                ))}
              </div>
            </div>
            <button className="flex items-center gap-2 px-4 py-2 bg-green-500/20 hover:bg-green-500/30 rounded-lg border border-green-500/30 text-green-300 font-medium transition-colors">
              <Plus className="h-4 w-4" />
              New Event
            </button>
          </div>
        </div>

        {/* Calendar View */}
        {viewMode === 'week' && (
          <div className="glass-card p-6 mb-6">
            <div className="grid grid-cols-8 gap-4">
              {/* Time column */}
              <div className="col-span-1">
                <div className="h-12 mb-4"></div>
                {Array.from({ length: 12 }, (_, i) => (
                  <div key={i} className="h-16 flex items-center text-white/60 text-sm">
                    {String(8 + i).padStart(2, '0')}:00
                  </div>
                ))}
              </div>

              {/* Days */}
              {getDaysInWeek(selectedDate).map((day, dayIndex) => {
                const dayEvents = getEventsForDate(day);
                const isToday = day.toDateString() === new Date().toDateString();
                
                return (
                  <div key={dayIndex} className="col-span-1">
                    <div className={`h-12 mb-4 text-center p-2 rounded-lg ${
                      isToday ? 'bg-blue-500/20 border border-blue-500/50' : 'bg-white/10'
                    }`}>
                      <div className="text-white/70 text-xs">
                        {day.toLocaleDateString('en-CA', { weekday: 'short' })}
                      </div>
                      <div className={`font-bold ${isToday ? 'text-blue-300' : 'text-white'}`}>
                        {day.getDate()}
                      </div>
                    </div>
                    
                    <div className="space-y-2">
                      {dayEvents.map((event) => {
                        const startHour = new Date(event.start).getHours();
                        const duration = (new Date(event.end).getTime() - new Date(event.start).getTime()) / (1000 * 60 * 60);
                        const topOffset = (startHour - 8) * 64; // 64px per hour
                        const height = duration * 64;
                        
                        return (
                          <div
                            key={event.id}
                            className={`absolute w-full p-2 rounded border text-xs ${getEventTypeColor(event.type)}`}
                            style={{ 
                              top: `${topOffset}px`, 
                              height: `${Math.max(height, 32)}px`,
                              zIndex: 10
                            }}
                          >
                            <div className="flex items-center gap-1 mb-1">
                              <span className="text-xs">{getEventTypeIcon(event.type)}</span>
                              <span className="font-medium truncate">{event.title}</span>
                            </div>
                            <div className="text-xs opacity-75">
                              {formatTime(event.start)} - {formatTime(event.end)}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Today's Events */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
          <div className="glass-card p-6">
            <div className="flex items-center gap-3 mb-6">
              <Clock className="h-6 w-6 text-blue-400" />
              <h3 className="text-xl font-semibold text-white">Today's Schedule</h3>
            </div>
            
            <div className="space-y-4">
              {events
                .filter(event => event.start.startsWith(new Date().toISOString().split('T')[0]))
                .map((event) => (
                  <div key={event.id} className="p-4 bg-white/10 rounded-lg border border-white/20">
                    <div className="flex items-start justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <span className="text-lg">{getEventTypeIcon(event.type)}</span>
                        <h4 className="font-semibold text-white">{event.title}</h4>
                      </div>
                      <span className={`px-2 py-1 rounded text-xs font-medium border ${getEventTypeColor(event.type)}`}>
                        {event.type}
                      </span>
                    </div>
                    <p className="text-white/70 text-sm mb-2">{event.description}</p>
                    <div className="flex items-center gap-4 text-xs text-white/60">
                      <span>{formatTime(event.start)} - {formatTime(event.end)}</span>
                      {event.attendees && (
                        <span className="flex items-center gap-1">
                          <Users className="h-3 w-3" />
                          {event.attendees.length}
                        </span>
                      )}
                      <span className={`px-1 py-0.5 rounded text-xs ${
                        event.priority === 'high' ? 'bg-red-500/20 text-red-300' :
                        event.priority === 'medium' ? 'bg-yellow-500/20 text-yellow-300' :
                        'bg-green-500/20 text-green-300'
                      }`}>
                        {event.priority}
                      </span>
                    </div>
                  </div>
                ))}
              
              {events.filter(event => event.start.startsWith(new Date().toISOString().split('T')[0])).length === 0 && (
                <div className="text-center py-8">
                  <Calendar className="h-12 w-12 text-white/30 mx-auto mb-2" />
                  <p className="text-white/50">No events scheduled for today</p>
                </div>
              )}
            </div>
          </div>

          {/* Market Events & Development Tasks */}
          <div className="glass-card p-6">
            <div className="flex items-center gap-3 mb-6">
              <TrendingUp className="h-6 w-6 text-green-400" />
              <h3 className="text-xl font-semibold text-white">Market Events & News</h3>
            </div>
            
            <div className="space-y-4">
              {marketEvents.slice(0, 4).map((event) => (
                <div key={event.id} className="p-4 bg-white/10 rounded-lg border border-white/20">
                  <div className="flex items-start justify-between mb-2">
                    <h4 className="font-semibold text-white">{event.title}</h4>
                    <span className={`px-2 py-1 rounded text-xs font-medium ${
                      event.impact === 'high' ? 'bg-red-500/20 text-red-300 border border-red-500/50' :
                      event.impact === 'medium' ? 'bg-yellow-500/20 text-yellow-300 border border-yellow-500/50' :
                      'bg-green-500/20 text-green-300 border border-green-500/50'
                    }`}>
                      {event.impact} impact
                    </span>
                  </div>
                  <p className="text-white/70 text-sm mb-2">{event.description}</p>
                  <div className="flex items-center gap-4 text-xs text-white/60">
                    <span>{formatDate(event.date)}</span>
                    <span>{event.markets.join(', ')}</span>
                  </div>
                </div>
              ))}
              
              {isDeveloper && (
                <div className="mt-6">
                  <h4 className="text-white font-medium mb-3 flex items-center gap-2">
                    <Zap className="h-4 w-4 text-purple-400" />
                    Upcoming Development Tasks
                  </h4>
                  <div className="space-y-2">
                    {developmentTasks.slice(0, 3).map((task) => (
                      <div key={task.id} className="p-3 bg-purple-500/10 rounded-lg border border-purple-500/30">
                        <div className="flex items-center justify-between">
                          <span className="text-white text-sm font-medium">{task.title}</span>
                          <span className="text-purple-300 text-xs">{task.estimatedHours}h</span>
                        </div>
                        <p className="text-white/60 text-xs mt-1">{task.description.substring(0, 60)}...</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Enhanced Productivity & Auto-Planning */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Calendar Productivity Stats */}
          <div className="glass-card p-6">
            <div className="flex items-center gap-3 mb-6">
              <FileText className="h-6 w-6 text-green-400" />
              <h3 className="text-xl font-semibold text-white">Development Productivity</h3>
            </div>
            
            <div className="space-y-4">
              <div className="p-4 bg-white/10 rounded-lg border border-white/20">
                <div className="flex justify-between items-center mb-2">
                  <span className="text-white/70">This Week - Development</span>
                  <span className="text-white font-semibold">24 hours planned</span>
                </div>
                <div className="bg-white/20 rounded-full h-2">
                  <div className="bg-blue-400 h-2 rounded-full" style={{ width: '60%' }} />
                </div>
                <p className="text-xs text-white/60 mt-1">60% of planned development time</p>
              </div>
              
              <div className="p-4 bg-white/10 rounded-lg border border-white/20">
                <div className="flex justify-between items-center mb-2">
                  <span className="text-white/70">Market Analysis</span>
                  <span className="text-white font-semibold">8 hours</span>
                </div>
                <div className="bg-white/20 rounded-full h-2">
                  <div className="bg-green-400 h-2 rounded-full" style={{ width: '80%' }} />
                </div>
                <p className="text-xs text-white/60 mt-1">80% of research goals met</p>
              </div>
              
              <div className="p-4 bg-white/10 rounded-lg border border-white/20">
                <div className="flex justify-between items-center mb-2">
                  <span className="text-white/70">Auto-scheduled Tasks</span>
                  <span className="text-white font-semibold">{developmentTasks.length} tasks</span>
                </div>
                <div className="bg-white/20 rounded-full h-2">
                  <div className="bg-purple-400 h-2 rounded-full" style={{ width: '85%' }} />
                </div>
                <p className="text-xs text-white/60 mt-1">Next month auto-planned</p>
              </div>
            </div>

            {calendarService.isGoogleCalendarConnected() && (
              <div className="mt-6 p-4 bg-green-500/20 rounded-lg border border-green-500/30">
                <div className="flex items-center gap-2 mb-2">
                  <Calendar className="h-4 w-4 text-green-400" />
                  <span className="text-green-300 font-medium">Google Calendar Connected</span>
                </div>
                <p className="text-green-200 text-sm">
                  Syncing market events, holidays, and development tasks automatically
                </p>
              </div>
            )}
          </div>

          {/* Auto-Planning Features */}
          <div className="glass-card p-6">
            <div className="flex items-center gap-3 mb-6">
              <Zap className="h-6 w-6 text-purple-400" />
              <h3 className="text-xl font-semibold text-white">Smart Planning Features</h3>
            </div>
            
            <div className="space-y-4">
              <div className="p-4 bg-blue-500/10 rounded-lg border border-blue-500/30">
                <div className="flex items-center gap-2 mb-2">
                  <AlertTriangle className="h-4 w-4 text-blue-400" />
                  <span className="text-blue-300 font-medium">Market Event Alerts</span>
                </div>
                <p className="text-blue-200 text-sm">
                  Automatically blocks trading time during market holidays and major news events
                </p>
              </div>
              
              <div className="p-4 bg-green-500/10 rounded-lg border border-green-500/30">
                <div className="flex items-center gap-2 mb-2">
                  <TrendingUp className="h-4 w-4 text-green-400" />
                  <span className="text-green-300 font-medium">Development Scheduling</span>
                </div>
                <p className="text-green-200 text-sm">
                  Auto-schedules development tasks based on priority, dependencies, and available time
                </p>
              </div>
              
              <div className="p-4 bg-purple-500/10 rounded-lg border border-purple-500/30">
                <div className="flex items-center gap-2 mb-2">
                  <Calendar className="h-4 w-4 text-purple-400" />
                  <span className="text-purple-300 font-medium">Monthly Planning</span>
                </div>
                <p className="text-purple-200 text-sm">
                  Automatically plans development work 1 month ahead with realistic time estimates
                </p>
              </div>
              
              {isDeveloper && (
                <button 
                  onClick={() => {
                    const scheduledTasks = calendarService.autoScheduleDevelopmentTasks();
                    setDevelopmentTasks(scheduledTasks);
                    alert(`Auto-scheduled ${scheduledTasks.length} development tasks for the next month!`);
                  }}
                  className="w-full mt-4 p-3 bg-purple-500/20 hover:bg-purple-500/30 rounded-lg border border-purple-500/30 text-purple-300 font-medium transition-colors"
                >
                  Re-schedule Development Tasks
                </button>
              )}
            </div>
          </div>
    </div>
  </PageContainer>
  );
};

export default DevCalendar;
