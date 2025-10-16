import { google } from 'googleapis';

import { GOOGLE_CALENDAR_CONFIG, EVENT_CATEGORY_MAPPING, STATUS_MAPPING } from '../config/googleCalendar';

interface CalendarEvent {
  id: string;
  title: string;
  description: string;
  date: Date;
  startTime: string;
  endTime: string;
  category: 'foundation' | 'development' | 'testing' | 'integration' | 'polish';
  status: 'pending' | 'in-progress' | 'completed' | 'blocked';
  priority: 'low' | 'medium' | 'high';
  deliverables?: string[];
}

interface GoogleCalendarEvent {
  id?: string;
  summary: string;
  description?: string;
  start: {
    dateTime: string;
    timeZone: string;
  };
  end: {
    dateTime: string;
    timeZone: string;
  };
  status?: string;
  colorId?: string;
  transparency?: string;
  visibility?: string;
}

export class GoogleCalendarService {
  private calendar: any;
  private auth: any;
  private isInitialized = false;

  constructor() {
    // Initialize Google Auth
    // Do NOT use client secrets in browser code. Secrets must be handled server-side.
    // Pass undefined for clientSecret to preserve the redirectUri argument position.
    this.auth = new google.auth.OAuth2(
      GOOGLE_CALENDAR_CONFIG.CLIENT_ID,
      undefined,
      GOOGLE_CALENDAR_CONFIG.REDIRECT_URI
    );

    this.calendar = google.calendar({ version: 'v3', auth: this.auth });
  }

  /**
   * Initialize the Google Calendar service with user authentication
   */
  async initialize(): Promise<boolean> {
    try {
      // Check if we have stored credentials
      const storedCredentials = localStorage.getItem('google_calendar_credentials');
      
      if (storedCredentials) {
        const credentials = JSON.parse(storedCredentials);
        this.auth.setCredentials(credentials);
        
        // Verify credentials are still valid
        try {
          await this.calendar.calendars.get({ calendarId: 'primary' });
          this.isInitialized = true;
          return true;
        } catch (error) {
          // Credentials expired, need to re-authenticate
          localStorage.removeItem('google_calendar_credentials');
        }
      }

      return false;
    } catch (error) {
      console.error('Failed to initialize Google Calendar service:', error);
      return false;
    }
  }

  /**
   * Get the OAuth2 authorization URL for user consent
   */
  getAuthUrl(): string {
    return this.auth.generateAuthUrl({
      access_type: 'offline',
      scope: GOOGLE_CALENDAR_CONFIG.SCOPES,
      include_granted_scopes: true
    });
  }

  /**
   * Handle the OAuth2 callback and store credentials
   */
  async handleAuthCallback(code: string): Promise<boolean> {
    try {
      const { tokens } = await this.auth.getToken(code);
      this.auth.setCredentials(tokens);
      
      // Store credentials securely
      localStorage.setItem('google_calendar_credentials', JSON.stringify(tokens));
      
      this.isInitialized = true;
      return true;
    } catch (error) {
      console.error('Failed to handle auth callback:', error);
      return false;
    }
  }

  /**
   * Create a dedicated FKS Trading calendar
   */
  async createFKSCalendar(): Promise<string | null> {
    try {
      if (!this.isInitialized) {
        throw new Error('Google Calendar service not initialized');
      }

      const calendar = {
        summary: GOOGLE_CALENDAR_CONFIG.FKS_CALENDAR_SETTINGS.name,
        description: GOOGLE_CALENDAR_CONFIG.FKS_CALENDAR_SETTINGS.description,
        timeZone: GOOGLE_CALENDAR_CONFIG.FKS_CALENDAR_SETTINGS.timeZone
      };

      const response = await this.calendar.calendars.insert({
        resource: calendar
      });

      const calendarId = response.data.id;
      
      // Store the FKS calendar ID for future use
      localStorage.setItem('fks_calendar_id', calendarId);
      
      return calendarId;
    } catch (error) {
      console.error('Failed to create FKS calendar:', error);
      return null;
    }
  }

  /**
   * Convert FKS calendar event to Google Calendar event format
   */
  private convertToGoogleEvent(event: CalendarEvent): GoogleCalendarEvent {
    const startDateTime = new Date(event.date);
    const [startHour, startMinute] = event.startTime.split(':');
    startDateTime.setHours(parseInt(startHour), parseInt(startMinute), 0, 0);

    const endDateTime = new Date(event.date);
    const [endHour, endMinute] = event.endTime.split(':');
    endDateTime.setHours(parseInt(endHour), parseInt(endMinute), 0, 0);

    const categoryMapping = EVENT_CATEGORY_MAPPING[event.category];
    
    let description = event.description;
    if (event.deliverables && event.deliverables.length > 0) {
      description += '\n\nDeliverables:\n' + event.deliverables.map(d => `• ${d}`).join('\n');
    }
    description += `\n\nPriority: ${event.priority.toUpperCase()}`;
    description += `\n\nStatus: ${event.status.replace('-', ' ').toUpperCase()}`;

    return {
      summary: `${categoryMapping.summary} ${event.title}`,
      description,
      start: {
        dateTime: startDateTime.toISOString(),
        timeZone: GOOGLE_CALENDAR_CONFIG.TIME_ZONE
      },
      end: {
        dateTime: endDateTime.toISOString(),
        timeZone: GOOGLE_CALENDAR_CONFIG.TIME_ZONE
      },
      status: STATUS_MAPPING[event.status],
      colorId: categoryMapping.colorId,
      transparency: event.status === 'completed' ? 'transparent' : 'opaque'
    };
  }

  /**
   * Sync FKS events to Google Calendar
   */
  async syncEventsToGoogle(events: CalendarEvent[]): Promise<boolean> {
    try {
      if (!this.isInitialized) {
        throw new Error('Google Calendar service not initialized');
      }

      // Get or create FKS calendar
      let calendarId = localStorage.getItem('fks_calendar_id');
      if (!calendarId) {
        calendarId = await this.createFKSCalendar();
        if (!calendarId) {
          throw new Error('Failed to create FKS calendar');
        }
      }

      // Clear existing FKS events (optional - you might want to update instead)
      await this.clearFKSEvents(calendarId);

      // Add all FKS events
      for (const event of events) {
        const googleEvent = this.convertToGoogleEvent(event);
        
        await this.calendar.events.insert({
          calendarId: calendarId,
          resource: googleEvent
        });
      }

      console.log(`Successfully synced ${events.length} events to Google Calendar`);
      return true;
    } catch (error) {
      console.error('Failed to sync events to Google Calendar:', error);
      return false;
    }
  }

  /**
   * Get events from Google Calendar
   */
  async getEventsFromGoogle(timeMin?: Date, timeMax?: Date): Promise<CalendarEvent[]> {
    try {
      if (!this.isInitialized) {
        throw new Error('Google Calendar service not initialized');
      }

      const calendarId = localStorage.getItem('fks_calendar_id') || 'primary';
      
      const response = await this.calendar.events.list({
        calendarId: calendarId,
        timeMin: timeMin?.toISOString() || new Date().toISOString(),
        timeMax: timeMax?.toISOString(),
        maxResults: 100,
        singleEvents: true,
        orderBy: 'startTime'
      });

      const events = response.data.items || [];
      
      // Convert Google Calendar events back to FKS format
      return events.map(this.convertFromGoogleEvent).filter(Boolean);
    } catch (error) {
      console.error('Failed to get events from Google Calendar:', error);
      return [];
    }
  }

  /**
   * Convert Google Calendar event to FKS event format
   */
  private convertFromGoogleEvent(googleEvent: any): CalendarEvent | null {
    try {
      if (!googleEvent.start?.dateTime || !googleEvent.end?.dateTime) {
        return null;
      }

      const startDate = new Date(googleEvent.start.dateTime);
      const endDate = new Date(googleEvent.end.dateTime);
      
      // Extract category from summary
      const summaryMatch = googleEvent.summary?.match(/^\[(\w+)\]/);
      const category = summaryMatch ? summaryMatch[1].toLowerCase() : 'development';
      
      // Extract title (remove category prefix)
      const title = googleEvent.summary?.replace(/^\[\w+\]\s*/, '') || 'Untitled Event';
      
      // Parse description for deliverables and other details
      const description = googleEvent.description || '';
      const deliverables = this.extractDeliverables(description);
      const priority = this.extractPriority(description);
      const status = this.extractStatus(description);

      return {
        id: googleEvent.id || Math.random().toString(36).substr(2, 9),
        title,
        description: description.split('\n\nDeliverables:')[0], // Remove deliverables from main description
        date: startDate,
        startTime: startDate.toTimeString().substr(0, 5),
        endTime: endDate.toTimeString().substr(0, 5),
        category: category as any,
        status: status as any,
        priority: priority as any,
        deliverables
      };
    } catch (error) {
      console.error('Failed to convert Google event:', error);
      return null;
    }
  }

  private extractDeliverables(description: string): string[] {
    const deliverablesMatch = description.match(/Deliverables:\n((?:• .+\n?)+)/);
    if (deliverablesMatch) {
      return deliverablesMatch[1]
        .split('\n')
        .map(line => line.replace('• ', '').trim())
        .filter(Boolean);
    }
    return [];
  }

  private extractPriority(description: string): 'low' | 'medium' | 'high' {
    const priorityMatch = description.match(/Priority: (\w+)/i);
    if (priorityMatch) {
      const priority = priorityMatch[1].toLowerCase();
      if (['low', 'medium', 'high'].includes(priority)) {
        return priority as any;
      }
    }
    return 'medium';
  }

  private extractStatus(description: string): 'pending' | 'in-progress' | 'completed' | 'blocked' {
    const statusMatch = description.match(/Status: (.+)/i);
    if (statusMatch) {
      const status = statusMatch[1].toLowerCase().replace(' ', '-');
      if (['pending', 'in-progress', 'completed', 'blocked'].includes(status)) {
        return status as any;
      }
    }
    return 'pending';
  }

  /**
   * Clear all FKS events from Google Calendar
   */
  private async clearFKSEvents(calendarId: string): Promise<void> {
    try {
      const response = await this.calendar.events.list({
        calendarId: calendarId,
        maxResults: 1000
      });

      const events = response.data.items || [];
      
      // Delete events that have FKS category markers
      for (const event of events) {
        if (event.summary?.match(/^\[\w+\]/)) {
          await this.calendar.events.delete({
            calendarId: calendarId,
            eventId: event.id
          });
        }
      }
    } catch (error) {
      console.error('Failed to clear FKS events:', error);
    }
  }

  /**
   * Sign out and clear stored credentials
   */
  signOut(): void {
    localStorage.removeItem('google_calendar_credentials');
    localStorage.removeItem('fks_calendar_id');
    this.isInitialized = false;
  }

  /**
   * Check if the service is authenticated and ready
   */
  isAuthenticated(): boolean {
    return this.isInitialized;
  }
}

export default GoogleCalendarService;
