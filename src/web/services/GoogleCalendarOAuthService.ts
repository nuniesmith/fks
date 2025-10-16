import { google } from 'googleapis';

import SecretManager from './security/SecretManager';

export class GoogleCalendarOAuthService {
  private static instance: GoogleCalendarOAuthService;
  private secretManager: SecretManager;

  private constructor() {
    this.secretManager = SecretManager.getInstance();
  }

  static getInstance(): GoogleCalendarOAuthService {
    if (!GoogleCalendarOAuthService.instance) {
      GoogleCalendarOAuthService.instance = new GoogleCalendarOAuthService();
    }
    return GoogleCalendarOAuthService.instance;
  }

  /**
   * Get Calendar API client using user's OAuth tokens
   */
  private async getCalendarClient(userId: string): Promise<any> {
    // Get OAuth tokens from SecretManager (stored by GoogleOAuthService)
    const tokensJson = await this.secretManager.getSecret(`oauth_tokens:${userId}`, 'user');
    if (!tokensJson) {
      throw new Error('No Google OAuth tokens found for user');
    }

    let tokens;
    try {
      tokens = JSON.parse(tokensJson);
    } catch (error) {
      throw new Error('Invalid OAuth tokens format');
    }

    const oauth2Client = new google.auth.OAuth2(
      import.meta.env.VITE_GOOGLE_CALENDAR_CLIENT_ID,
      undefined as any,
      import.meta.env.VITE_GOOGLE_CALENDAR_REDIRECT_URI
    );

    // Set the credentials from stored tokens
    oauth2Client.setCredentials({
      access_token: tokens.access_token,
      refresh_token: tokens.refresh_token,
      expiry_date: tokens.expires_at
    });

    return google.calendar({ version: 'v3', auth: oauth2Client });
  }

  /**
   * List user's calendars
   */
  async listCalendars(userId: string): Promise<any[]> {
    try {
      const calendar = await this.getCalendarClient(userId);
      const response = await calendar.calendarList.list();
      return response.data.items || [];
    } catch (error) {
      console.error('Failed to list calendars:', error);
      throw new Error('Failed to fetch calendars');
    }
  }

  /**
   * Get events from user's primary calendar
   */
  async getEvents(userId: string, options: {
    calendarId?: string;
    timeMin?: string;
    timeMax?: string;
    maxResults?: number;
  } = {}): Promise<any[]> {
    try {
      const calendar = await this.getCalendarClient(userId);
      const response = await calendar.events.list({
        calendarId: options.calendarId || 'primary',
        timeMin: options.timeMin || new Date().toISOString(),
        timeMax: options.timeMax,
        maxResults: options.maxResults || 50,
        singleEvents: true,
        orderBy: 'startTime'
      });
      
      return response.data.items || [];
    } catch (error) {
      console.error('Failed to get events:', error);
      throw new Error('Failed to fetch calendar events');
    }
  }

  /**
   * Create a new calendar event
   */
  async createEvent(userId: string, eventData: {
    summary: string;
    description?: string;
    start: {
      dateTime: string;
      timeZone?: string;
    };
    end: {
      dateTime: string;
      timeZone?: string;
    };
    location?: string;
    attendees?: Array<{ email: string }>;
    calendarId?: string;
  }): Promise<any> {
    try {
      const calendar = await this.getCalendarClient(userId);
      const response = await calendar.events.insert({
        calendarId: eventData.calendarId || 'primary',
        requestBody: {
          summary: eventData.summary,
          description: eventData.description,
          start: eventData.start,
          end: eventData.end,
          location: eventData.location,
          attendees: eventData.attendees
        }
      });
      
      return response.data;
    } catch (error) {
      console.error('Failed to create event:', error);
      throw new Error('Failed to create calendar event');
    }
  }

  /**
   * Update an existing calendar event
   */
  async updateEvent(userId: string, eventId: string, eventData: any, calendarId: string = 'primary'): Promise<any> {
    try {
      const calendar = await this.getCalendarClient(userId);
      const response = await calendar.events.update({
        calendarId,
        eventId,
        requestBody: eventData
      });
      
      return response.data;
    } catch (error) {
      console.error('Failed to update event:', error);
      throw new Error('Failed to update calendar event');
    }
  }

  /**
   * Delete a calendar event
   */
  async deleteEvent(userId: string, eventId: string, calendarId: string = 'primary'): Promise<void> {
    try {
      const calendar = await this.getCalendarClient(userId);
      await calendar.events.delete({
        calendarId,
        eventId
      });
    } catch (error) {
      console.error('Failed to delete event:', error);
      throw new Error('Failed to delete calendar event');
    }
  }

  /**
   * Get trading calendar events (specific to FKS trading schedule)
   */
  async getTradingCalendarEvents(userId: string, options: {
    startDate?: Date;
    endDate?: Date;
  } = {}): Promise<any[]> {
    const startDate = options.startDate || new Date();
    const endDate = options.endDate || new Date(Date.now() + 30 * 24 * 60 * 60 * 1000); // 30 days

    const events = await this.getEvents(userId, {
      timeMin: startDate.toISOString(),
      timeMax: endDate.toISOString(),
      maxResults: 100
    });

    // Filter for trading-related events
    return events.filter(event => 
      event.summary?.toLowerCase().includes('trading') ||
      event.summary?.toLowerCase().includes('market') ||
      event.summary?.toLowerCase().includes('fks') ||
      event.description?.toLowerCase().includes('trading')
    );
  }

  /**
   * Create trading session event
   */
  async createTradingSession(userId: string, sessionData: {
    strategy: string;
    startTime: Date;
    endTime: Date;
    notes?: string;
    symbols?: string[];
  }): Promise<any> {
    const eventData = {
      summary: `Trading Session - ${sessionData.strategy}`,
      description: [
        `Strategy: ${sessionData.strategy}`,
        sessionData.symbols ? `Symbols: ${sessionData.symbols.join(', ')}` : '',
        sessionData.notes ? `Notes: ${sessionData.notes}` : '',
        'Created by FKS Trading System'
      ].filter(Boolean).join('\n'),
      start: {
        dateTime: sessionData.startTime.toISOString(),
        timeZone: 'America/Toronto'
      },
      end: {
        dateTime: sessionData.endTime.toISOString(),
        timeZone: 'America/Toronto'
      },
      location: 'FKS Trading Platform'
    };

    return this.createEvent(userId, eventData);
  }

  /**
   * Health check for calendar service
   */
  async healthCheck(userId: string): Promise<{ status: string; details: any }> {
    try {
      const calendar = await this.getCalendarClient(userId);
      
      // Test by getting calendar list
      const response = await calendar.calendarList.list({ maxResults: 1 });
      
      return {
        status: 'healthy',
        details: {
          connected: true,
          calendarsFound: response.data.items?.length || 0
        }
      };
    } catch (error) {
      return {
        status: 'unhealthy',
        details: {
          error: error.message,
          connected: false
        }
      };
    }
  }
}

export default GoogleCalendarOAuthService;
