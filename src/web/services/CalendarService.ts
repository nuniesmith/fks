import type { CalendarEvent, MarketEvent, DevelopmentTask } from '../types/user';

export class CalendarService {
  private static instance: CalendarService;
  private marketEvents: MarketEvent[] = [];
  private developmentTasks: DevelopmentTask[] = [];
  private googleCalendarConnected = false;

  public static getInstance(): CalendarService {
    if (!CalendarService.instance) {
      CalendarService.instance = new CalendarService();
    }
    return CalendarService.instance;
  }

  // Mock market holidays and events for 2025
  private getMarketEvents(): MarketEvent[] {
    return [
      {
        id: 'new-years-2025',
        title: 'New Year\'s Day',
        description: 'Markets closed for New Year\'s Day',
        date: '2025-01-01',
        type: 'holiday',
        markets: ['NYSE', 'NASDAQ', 'TSX', 'FOREX'],
        impact: 'high',
        source: 'market_calendar'
      },
      {
        id: 'martin-luther-king-2025',
        title: 'Martin Luther King Jr. Day',
        description: 'US markets closed',
        date: '2025-01-20',
        type: 'holiday',
        markets: ['NYSE', 'NASDAQ'],
        impact: 'medium',
        source: 'market_calendar'
      },
      {
        id: 'family-day-ontario-2025',
        title: 'Family Day (Ontario)',
        description: 'TSX closed for Family Day',
        date: '2025-02-17',
        type: 'holiday',
        markets: ['TSX'],
        impact: 'medium',
        source: 'market_calendar'
      },
      {
        id: 'good-friday-2025',
        title: 'Good Friday',
        description: 'Most markets closed for Good Friday',
        date: '2025-04-18',
        type: 'holiday',
        markets: ['NYSE', 'NASDAQ', 'TSX', 'FOREX'],
        impact: 'high',
        source: 'market_calendar'
      },
      {
        id: 'independence-day-2025',
        title: 'Independence Day',
        description: 'US markets closed',
        date: '2025-07-04',
        type: 'holiday',
        markets: ['NYSE', 'NASDAQ'],
        impact: 'high',
        source: 'market_calendar'
      },
      {
        id: 'canada-day-2025',
        title: 'Canada Day',
        description: 'TSX closed for Canada Day',
        date: '2025-07-01',
        type: 'holiday',
        markets: ['TSX'],
        impact: 'high',
        source: 'market_calendar'
      },
      {
        id: 'thanksgiving-2025',
        title: 'Thanksgiving Day',
        description: 'US markets closed',
        date: '2025-11-27',
        type: 'holiday',
        markets: ['NYSE', 'NASDAQ'],
        impact: 'high',
        source: 'market_calendar'
      },
      {
        id: 'black-friday-2025',
        title: 'Day After Thanksgiving',
        description: 'US markets close early at 1:00 PM ET',
        date: '2025-11-28',
        type: 'early_close',
        markets: ['NYSE', 'NASDAQ'],
        impact: 'medium',
        source: 'market_calendar'
      },
      {
        id: 'christmas-eve-2025',
        title: 'Christmas Eve',
        description: 'US markets close early at 1:00 PM ET',
        date: '2025-12-24',
        type: 'early_close',
        markets: ['NYSE', 'NASDAQ'],
        impact: 'medium',
        source: 'market_calendar'
      },
      {
        id: 'christmas-2025',
        title: 'Christmas Day',
        description: 'All major markets closed',
        date: '2025-12-25',
        type: 'holiday',
        markets: ['NYSE', 'NASDAQ', 'TSX', 'FOREX'],
        impact: 'high',
        source: 'market_calendar'
      },
      // Economic releases
      {
        id: 'fomc-meeting-2025-08',
        title: 'FOMC Meeting',
        description: 'Federal Reserve interest rate decision',
        date: '2025-08-01',
        type: 'important_release',
        markets: ['FOREX', 'FUTURES'],
        impact: 'high',
        source: 'economic_calendar'
      },
      {
        id: 'nfp-2025-08',
        title: 'Non-Farm Payrolls',
        description: 'US employment data release',
        date: '2025-08-01',
        type: 'important_release',
        markets: ['FOREX', 'FUTURES'],
        impact: 'high',
        source: 'economic_calendar'
      },
      {
        id: 'cpi-2025-08',
        title: 'Consumer Price Index',
        description: 'US inflation data',
        date: '2025-08-13',
        type: 'important_release',
        markets: ['FOREX', 'FUTURES'],
        impact: 'high',
        source: 'economic_calendar'
      }
    ];
  }

  // Auto-generate development tasks for the next month
  private generateDevelopmentTasks(): DevelopmentTask[] {
    const now = new Date();
    const nextMonth = new Date(now.getFullYear(), now.getMonth() + 1, 1);
    
    return [
      {
        id: 'dev-task-1',
        title: 'Enhanced User Authentication System',
        description: 'Implement proper JWT authentication and user role management',
        priority: 'high',
        estimatedHours: 16,
        category: 'feature',
        tags: ['authentication', 'security', 'backend'],
        status: 'planned',
        dueDate: new Date(nextMonth.getTime() + 7 * 24 * 60 * 60 * 1000).toISOString(), // 1 week
        createdAt: now.toISOString(),
        updatedAt: now.toISOString()
      },
      {
        id: 'dev-task-2',
        title: 'Real-time Market Data Integration',
        description: 'Connect to market data APIs for live price feeds',
        priority: 'high',
        estimatedHours: 24,
        category: 'feature',
        dependencies: ['dev-task-1'],
        tags: ['market-data', 'websockets', 'api'],
        status: 'planned',
        dueDate: new Date(nextMonth.getTime() + 14 * 24 * 60 * 60 * 1000).toISOString(), // 2 weeks
        createdAt: now.toISOString(),
        updatedAt: now.toISOString()
      },
      {
        id: 'dev-task-3',
        title: 'Google Calendar API Integration',
        description: 'Complete integration with Google Calendar for market events and development planning',
        priority: 'medium',
        estimatedHours: 12,
        category: 'feature',
        tags: ['google-calendar', 'api', 'automation'],
        status: 'in_progress',
        dueDate: new Date(nextMonth.getTime() + 10 * 24 * 60 * 60 * 1000).toISOString(),
        createdAt: now.toISOString(),
        updatedAt: now.toISOString()
      },
      {
        id: 'dev-task-4',
        title: 'Trading Journal Enhanced Features',
        description: 'Add trade tagging, performance analytics, and export functionality',
        priority: 'medium',
        estimatedHours: 20,
        category: 'feature',
        tags: ['trading-journal', 'analytics', 'export'],
        status: 'planned',
        dueDate: new Date(nextMonth.getTime() + 21 * 24 * 60 * 60 * 1000).toISOString(), // 3 weeks
        createdAt: now.toISOString(),
        updatedAt: now.toISOString()
      },
      {
        id: 'dev-task-5',
        title: 'Tax Optimization Calculator',
        description: 'Build advanced Canadian tax optimization calculator with scenarios',
        priority: 'medium',
        estimatedHours: 18,
        category: 'feature',
        tags: ['tax-optimization', 'calculator', 'canadian-tax'],
        status: 'planned',
        dueDate: new Date(nextMonth.getTime() + 28 * 24 * 60 * 60 * 1000).toISOString(), // 4 weeks
        createdAt: now.toISOString(),
        updatedAt: now.toISOString()
      },
      {
        id: 'dev-task-6',
        title: 'Performance Optimization',
        description: 'Optimize React components and reduce bundle size',
        priority: 'low',
        estimatedHours: 8,
        category: 'optimization',
        tags: ['performance', 'optimization', 'react'],
        status: 'planned',
        dueDate: new Date(nextMonth.getTime() + 35 * 24 * 60 * 60 * 1000).toISOString(),
        createdAt: now.toISOString(),
        updatedAt: now.toISOString()
      },
      {
        id: 'dev-task-7',
        title: 'Mobile Responsive Design',
        description: 'Ensure all components work well on mobile devices',
        priority: 'medium',
        estimatedHours: 14,
        category: 'feature',
        tags: ['mobile', 'responsive', 'ui'],
        status: 'planned',
        dueDate: new Date(nextMonth.getTime() + 42 * 24 * 60 * 60 * 1000).toISOString(),
        createdAt: now.toISOString(),
        updatedAt: now.toISOString()
      }
    ];
  }

  // Convert tasks to calendar events
  private tasksToCalendarEvents(tasks: DevelopmentTask[]): CalendarEvent[] {
    return tasks.map(task => ({
      id: `cal-${task.id}`,
      title: `Dev: ${task.title}`,
      description: task.description,
      start: task.dueDate || new Date().toISOString(),
      end: task.dueDate || new Date().toISOString(),
      type: 'development' as const,
      priority: task.priority,
      source: 'auto_generated' as const,
      metadata: {
        developmentPhase: task.category,
        tradingImpact: 'none' as const
      }
    }));
  }

  // Convert market events to calendar events
  private marketEventsToCalendarEvents(events: MarketEvent[]): CalendarEvent[] {
    return events.map(event => ({
      id: `market-${event.id}`,
      title: event.title,
      description: event.description,
      start: `${event.date}T09:30:00-05:00`, // Market open time
      end: event.type === 'early_close' ? `${event.date}T13:00:00-05:00` : `${event.date}T16:00:00-05:00`,
      type: event.type === 'holiday' ? 'holiday' : 'market',
      priority: event.impact === 'high' ? 'high' : event.impact === 'medium' ? 'medium' : 'low',
      source: 'market_api' as const,
      metadata: {
        marketAffected: event.markets,
        tradingImpact: event.impact as any
      }
    }));
  }

  // Get all calendar events for a date range
  public async getCalendarEvents(startDate: Date, endDate: Date, userRole: string): Promise<CalendarEvent[]> {
    const marketEvents = this.getMarketEvents();
    const developmentTasks = this.generateDevelopmentTasks();

    const allEvents: CalendarEvent[] = [];

    // Add market events (visible to all users)
    const marketCalendarEvents = this.marketEventsToCalendarEvents(
      marketEvents.filter(event => {
        const eventDate = new Date(event.date);
        return eventDate >= startDate && eventDate <= endDate;
      })
    );
    allEvents.push(...marketCalendarEvents);

    // Add development events (only for developers/admins)
    if (userRole === 'developer' || userRole === 'admin') {
      const devCalendarEvents = this.tasksToCalendarEvents(
        developmentTasks.filter(task => {
          if (!task.dueDate) return false;
          const taskDate = new Date(task.dueDate);
          return taskDate >= startDate && taskDate <= endDate;
        })
      );
      allEvents.push(...devCalendarEvents);
    }

    return allEvents.sort((a, b) => new Date(a.start).getTime() - new Date(b.start).getTime());
  }

  // Simulate Google Calendar connection
  public async connectGoogleCalendar(): Promise<boolean> {
    // In a real implementation, this would use Google Calendar API
    return new Promise((resolve) => {
      setTimeout(() => {
        this.googleCalendarConnected = true;
        resolve(true);
      }, 1000);
    });
  }

  // Auto-schedule development tasks
  public autoScheduleDevelopmentTasks(): DevelopmentTask[] {
    const tasks = this.generateDevelopmentTasks();
    
    // Auto-schedule based on priority and dependencies
    const scheduledTasks = [...tasks];
    const workingHoursPerDay = 6; // 6 hours of development per day
    const startDate = new Date();
    startDate.setDate(startDate.getDate() + 1); // Start tomorrow

    scheduledTasks.forEach((task, index) => {
      const daysNeeded = Math.ceil(task.estimatedHours / workingHoursPerDay);
      const taskStartDate = new Date(startDate);
      taskStartDate.setDate(taskStartDate.getDate() + (index * 2)); // 2-day buffer between tasks
      
      const taskEndDate = new Date(taskStartDate);
      taskEndDate.setDate(taskEndDate.getDate() + daysNeeded);
      
      task.dueDate = taskEndDate.toISOString();
    });

    return scheduledTasks;
  }

  public isGoogleCalendarConnected(): boolean {
    return this.googleCalendarConnected;
  }

  public getDevelopmentTasks(): DevelopmentTask[] {
    return this.generateDevelopmentTasks();
  }

  public getMarketEventsData(): MarketEvent[] {
    return this.getMarketEvents();
  }
}
