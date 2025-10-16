// Google Calendar API Configuration
export const GOOGLE_CALENDAR_CONFIG = {
  // Your Google Calendar API credentials will be set here
  CLIENT_ID: import.meta.env.VITE_GOOGLE_CLIENT_ID || '',
  // Never include client secrets in client-side code
  // CLIENT_SECRET must be handled server-side during OAuth token exchange
  REDIRECT_URI: import.meta.env.VITE_GOOGLE_REDIRECT_URI || 'http://localhost:3000/auth/google/callback',
  
  // OAuth 2.0 scopes for Google Calendar API
  SCOPES: [
    'https://www.googleapis.com/auth/calendar.readonly',
    'https://www.googleapis.com/auth/calendar.events',
    'https://www.googleapis.com/auth/calendar'
  ],

  // Default calendar settings
  DEFAULT_CALENDAR_ID: 'primary', // Use 'primary' for the main calendar
  TIME_ZONE: 'America/Toronto', // Based on your .env TZ setting
  
  // FKS Trading specific calendar settings
  FKS_CALENDAR_SETTINGS: {
    name: 'FKS Trading Development',
    description: 'Trading system development schedule and events',
    timeZone: 'America/Toronto',
    // Calendar color (optional)
    backgroundColor: '#1e3a8a', // Blue to match your theme
    foregroundColor: '#ffffff'
  }
};

// Event category mapping for Google Calendar
export const EVENT_CATEGORY_MAPPING = {
  foundation: {
    colorId: '1', // Lavender
    summary: '[Foundation]'
  },
  development: {
    colorId: '2', // Sage  
    summary: '[Development]'
  },
  testing: {
    colorId: '3', // Grape
    summary: '[Testing]'
  },
  integration: {
    colorId: '4', // Flamingo
    summary: '[Integration]'
  },
  polish: {
    colorId: '5', // Banana
    summary: '[Polish]'
  }
};

// Status to Google Calendar mapping
export const STATUS_MAPPING = {
  pending: 'tentative',
  'in-progress': 'confirmed',
  completed: 'confirmed',
  blocked: 'cancelled'
};
