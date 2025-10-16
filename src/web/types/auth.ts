// OAuth and Authentication Types for Google and Authentik Integration

export interface OAuthProvider {
  id: string;
  name: string;
  type: 'google' | 'rust' | 'custom';
  enabled: boolean;
  configuration: OAuthConfiguration;
  status: 'connected' | 'disconnected' | 'error' | 'pending';
  lastConnected?: Date;
  tokenExpiry?: Date;
  scopes: string[];
}

export interface OAuthConfiguration {
  clientId: string;
  clientSecret?: string; // Never store in frontend
  redirectUri: string;
  authUrl: string;
  tokenUrl: string;
  userInfoUrl?: string;
  scopes: string[];
  additionalParams?: Record<string, string>;
}

export interface GoogleOAuthConfig extends OAuthConfiguration {
  // Google-specific configuration
  hostedDomain?: string; // For G Suite domains
  prompt?: 'none' | 'consent' | 'select_account';
  accessType: 'online' | 'offline';
  includeGrantedScopes: boolean;
}

export interface AuthentikOAuthConfig extends OAuthConfiguration {
  // Authentik-specific configuration
  serverUrl: string;
  applicationSlug: string;
  groupMappings?: GroupMapping[];
}

export interface GroupMapping {
  rustGroup?: string; // renamed from autheliaGroup
  applicationRole: string;
  permissions: string[];
}

export interface AuthenticationState {
  isAuthenticated: boolean;
  user?: AuthenticatedUser;
  providers: OAuthProvider[];
  currentProvider?: string;
  tokens: TokenSet;
  permissions: string[];
  roles: string[];
}

export interface AuthenticatedUser {
  id: string;
  email: string;
  name: string;
  picture?: string;
  provider: string;
  providerId: string;
  verified: boolean;
  createdAt: Date;
  lastLogin: Date;
  preferences: UserPreferences;
  canadianTaxInfo?: CanadianTaxInfo;
}

export interface UserPreferences {
  timezone: string;
  currency: 'CAD' | 'USD';
  language: 'en' | 'fr';
  theme: 'light' | 'dark' | 'auto';
  notifications: NotificationPreferences;
  trading: TradingPreferences;
}

export interface NotificationPreferences {
  email: boolean;
  push: boolean;
  milestoneAchievements: boolean;
  profitAlerts: boolean;
  riskWarnings: boolean;
  taxDeadlines: boolean;
  marketUpdates: boolean;
}

export interface TradingPreferences {
  defaultRiskPercentage: number;
  autoStopLoss: boolean;
  confirmTrades: boolean;
  showAdvancedTools: boolean;
  paperTradingMode: boolean;
}

export interface CanadianTaxInfo {
  sinNumber?: string; // Never store directly - encrypted
  province: CanadianProvince;
  taxFilingStatus: 'single' | 'married' | 'common_law';
  dependents: number;
  businessIncorporated: boolean;
  businessNumber?: string;
  preferredAccountant?: string;
}

export type CanadianProvince = 
  | 'AB' | 'BC' | 'MB' | 'NB' | 'NL' | 'NS' | 'NT' | 'NU' | 'ON' | 'PE' | 'QC' | 'SK' | 'YT';

export interface TokenSet {
  accessToken?: string;
  refreshToken?: string;
  idToken?: string;
  tokenType: string;
  expiresAt?: Date;
  scope?: string;
}

// Google Calendar Integration
export interface GoogleCalendarIntegration {
  enabled: boolean;
  calendarId?: string;
  syncTradingEvents: boolean;
  syncMilestones: boolean;
  syncTaxDeadlines: boolean;
  eventCategories: CalendarEventCategory[];
  lastSync?: Date;
  syncErrors: string[];
}

export interface CalendarEventCategory {
  id: string;
  name: string;
  color: string;
  enabled: boolean;
  eventTypes: string[];
}

export interface TradingCalendarEvent {
  id: string;
  title: string;
  description: string;
  startTime: Date;
  endTime: Date;
  category: string;
  type: 'trade' | 'milestone' | 'tax_deadline' | 'market_event' | 'custom';
  metadata: Record<string, any>;
  reminders: EventReminder[];
}

export interface EventReminder {
  method: 'email' | 'popup' | 'notification';
  minutes: number;
}

// OAuth Flow Types
export interface OAuthFlow {
  id: string;
  provider: string;
  state: string;
  codeVerifier?: string; // For PKCE
  redirectUri: string;
  scopes: string[];
  startedAt: Date;
  expiresAt: Date;
  metadata?: Record<string, any>;
}

export interface OAuthCallback {
  code?: string;
  state: string;
  error?: string;
  errorDescription?: string;
  errorUri?: string;
}

export interface OAuthTokenResponse {
  access_token: string;
  token_type: string;
  expires_in?: number;
  refresh_token?: string;
  scope?: string;
  id_token?: string;
}

// Authentication Actions
export type AuthAction = 
  | { type: 'INIT_AUTH'; payload: { providers: OAuthProvider[] } }
  | { type: 'LOGIN_START'; payload: { provider: string } }
  | { type: 'LOGIN_SUCCESS'; payload: { user: AuthenticatedUser; tokens: TokenSet } }
  | { type: 'LOGIN_ERROR'; payload: { error: string; provider: string } }
  | { type: 'LOGOUT' }
  | { type: 'REFRESH_TOKEN'; payload: { tokens: TokenSet } }
  | { type: 'UPDATE_PREFERENCES'; payload: { preferences: Partial<UserPreferences> } }
  | { type: 'CONNECT_PROVIDER'; payload: { provider: OAuthProvider } }
  | { type: 'DISCONNECT_PROVIDER'; payload: { providerId: string } };

// Google Calendar API Types
export interface GoogleCalendarAPI {
  listCalendars(): Promise<GoogleCalendar[]>;
  createEvent(calendarId: string, event: GoogleCalendarEvent): Promise<GoogleCalendarEvent>;
  updateEvent(calendarId: string, eventId: string, event: Partial<GoogleCalendarEvent>): Promise<GoogleCalendarEvent>;
  deleteEvent(calendarId: string, eventId: string): Promise<void>;
  listEvents(calendarId: string, timeMin?: Date, timeMax?: Date): Promise<GoogleCalendarEvent[]>;
}

export interface GoogleCalendar {
  id: string;
  summary: string;
  description?: string;
  primary?: boolean;
  accessRole: 'owner' | 'reader' | 'writer';
  colorId?: string;
  backgroundColor?: string;
  foregroundColor?: string;
}

export interface GoogleCalendarEvent {
  id?: string;
  summary: string;
  description?: string;
  start: {
    dateTime?: string;
    date?: string;
    timeZone?: string;
  };
  end: {
    dateTime?: string;
    date?: string;
    timeZone?: string;
  };
  recurrence?: string[];
  reminders?: {
    useDefault: boolean;
    overrides?: Array<{
      method: 'email' | 'popup';
      minutes: number;
    }>;
  };
  attendees?: Array<{
    email: string;
    displayName?: string;
    responseStatus?: 'needsAction' | 'declined' | 'tentative' | 'accepted';
  }>;
  colorId?: string;
  created?: string;
  updated?: string;
  status?: 'confirmed' | 'tentative' | 'cancelled';
}

// Security and Validation
export interface SecurityConfig {
  requireMFA: boolean;
  sessionTimeout: number; // minutes
  maxLoginAttempts: number;
  lockoutDuration: number; // minutes
  passwordPolicy: PasswordPolicy;
  allowedDomains?: string[];
  ipWhitelist?: string[];
}

export interface PasswordPolicy {
  minLength: number;
  requireUppercase: boolean;
  requireLowercase: boolean;
  requireNumbers: boolean;
  requireSpecialChars: boolean;
  preventReuse: number;
  expiryDays?: number;
}

export interface AuditLog {
  id: string;
  userId: string;
  action: string;
  resource: string;
  timestamp: Date;
  ipAddress: string;
  userAgent: string;
  success: boolean;
  details?: Record<string, any>;
}
