import { google } from 'googleapis';

import { SecretManager } from './security';

interface GoogleUser {
  id: string;
  email: string;
  name: string;
  picture?: string;
  given_name?: string;
  family_name?: string;
  verified_email: boolean;
}

interface FKSUser {
  id: string;
  googleId: string;
  email: string;
  name: string;
  picture?: string;
  role: 'root' | 'admin' | 'user';
  permissions: string[];
  createdAt: string;
  lastLogin: string;
  isActive: boolean;
}

interface OAuthTokens {
  access_token: string;
  refresh_token?: string;
  scope: string;
  token_type: string;
  expires_in: number;
  expires_at: number;
}

export class GoogleOAuthService {
  private static instance: GoogleOAuthService;
  private oauth2Client: any;
  private tradingOAuth2Client: any;
  private calendarOAuth2Client: any;
  private secretManager: SecretManager;
  private isInitialized = false;

  // Define your admin email (you can add more later)
  private readonly ADMIN_EMAILS = [
    'nunie.smith01@gmail.com', // Your email as admin
    // Add more admin emails here as needed
  ];

  // Root user (backup access)
  private readonly ROOT_USER = {
    email: 'nunie.smith01@gmail.com',
    name: 'Root Administrator',
    role: 'root' as const
  };

  private constructor() {
    this.secretManager = SecretManager.getInstance();
    
    // Initialize OAuth clients for both projects
    // NOTE: Do not use CLIENT_SECRET in client-side code. In production, the
    // OAuth code exchange should occur on the backend. The client can still
    // create an OAuth2 client for auth URL generation using public CLIENT_ID.
    this.tradingOAuth2Client = new google.auth.OAuth2(
      import.meta.env.VITE_GOOGLE_TRADING_CLIENT_ID,
      undefined as any,
      import.meta.env.VITE_GOOGLE_TRADING_REDIRECT_URI || 'http://localhost:3001/auth/google/callback'
    );

    this.calendarOAuth2Client = new google.auth.OAuth2(
      import.meta.env.VITE_GOOGLE_CALENDAR_CLIENT_ID,
      undefined as any,
      import.meta.env.VITE_GOOGLE_CALENDAR_REDIRECT_URI || 'http://localhost:3001/auth/google/calendar/callback'
    );

    // Keep legacy oauth2Client for backward compatibility (defaults to trading)
    this.oauth2Client = this.tradingOAuth2Client;
  }

  static getInstance(): GoogleOAuthService {
    if (!GoogleOAuthService.instance) {
      GoogleOAuthService.instance = new GoogleOAuthService();
    }
    return GoogleOAuthService.instance;
  }

  async initialize(): Promise<void> {
    if (this.isInitialized) return;

    try {
      await this.secretManager.initialize();
      this.isInitialized = true;
      console.log('Google OAuth service initialized successfully');
    } catch (error) {
      console.error('Failed to initialize Google OAuth service:', error);
      throw error;
    }
  }

  /**
   * Get OAuth client for specific project
   */
  private getOAuthClient(project: 'trading' | 'calendar' = 'trading'): any {
    return project === 'calendar' ? this.calendarOAuth2Client : this.tradingOAuth2Client;
  }

  /**
   * Generate OAuth URL for specific project
   */
  getAuthUrl(project: 'trading' | 'calendar' = 'trading', state?: string): string {
    const client = this.getOAuthClient(project);
    
    let scopes: string[];
    if (project === 'calendar') {
      // Calendar-specific scopes
      scopes = [
        'https://www.googleapis.com/auth/userinfo.profile',
        'https://www.googleapis.com/auth/userinfo.email',
        'https://www.googleapis.com/auth/calendar.readonly',
        'https://www.googleapis.com/auth/calendar.events',
        'https://www.googleapis.com/auth/calendar'
      ];
    } else {
      // Trading platform scopes (minimal calendar access)
      scopes = [
        'https://www.googleapis.com/auth/userinfo.profile',
        'https://www.googleapis.com/auth/userinfo.email',
        'https://www.googleapis.com/auth/calendar.readonly'
      ];
    }

    return client.generateAuthUrl({
      access_type: 'offline',
      scope: scopes,
      state: state || `google_oauth_${project}_${Date.now()}`,
      prompt: 'consent'
    });
  }

  /**
   * Handle OAuth callback and complete authentication
   */
  async handleOAuthCallback(code: string, state?: string, project: 'trading' | 'calendar' = 'trading'): Promise<FKSUser> {
    try {
      if (!this.isInitialized) await this.initialize();

      // Get the correct OAuth client for the project
      const client = this.getOAuthClient(project);

      // Exchange code for tokens
      const { tokens } = await client.getToken(code);
      client.setCredentials(tokens);

      // Get user information from Google
      const oauth2 = google.oauth2({ version: 'v2', auth: client });
      const userResponse = await oauth2.userinfo.get();
      const userData = userResponse.data;

      if (!userData.email || !userData.verified_email) {
        throw new Error('Google account email not verified');
      }

      const googleUser: GoogleUser = {
        id: userData.id!,
        email: userData.email,
        name: userData.name || 'Unknown User',
        picture: userData.picture,
        given_name: userData.given_name,
        family_name: userData.family_name,
        verified_email: userData.verified_email
      };

      // Create or update FKS user
      const fksUser = await this.createOrUpdateUser(googleUser);

      // Store tokens securely
      await this.storeUserTokens(fksUser.id, {
        access_token: tokens.access_token!,
        refresh_token: tokens.refresh_token,
        scope: tokens.scope!,
        token_type: tokens.token_type!,
        expires_in: tokens.expiry_date ? Math.floor((tokens.expiry_date - Date.now()) / 1000) : 3600,
        expires_at: tokens.expiry_date || Date.now() + 3600000
      });

      // Update last login
      fksUser.lastLogin = new Date().toISOString();
      await this.updateUser(fksUser);

      console.log(`User ${fksUser.email} authenticated as ${fksUser.role}`);
      return fksUser;

    } catch (error) {
      console.error('OAuth callback failed:', error);
      throw error;
    }
  }

  /**
   * Get current authenticated user from stored tokens
   */
  async getCurrentUser(): Promise<FKSUser | null> {
    try {
      const userId = localStorage.getItem('current_user_id');
      if (!userId) return null;

      const user = await this.getStoredUser(userId);
      if (!user) return null;

      // Verify tokens are still valid
      const tokens = await this.getUserTokens(userId);
      if (!tokens) return null;

      // Check if tokens need refresh
      if (tokens.expires_at < Date.now()) {
        const refreshed = await this.refreshUserTokens(userId);
        if (!refreshed) return null;
      }

      return user;

    } catch (error) {
      console.error('Failed to get current user:', error);
      return null;
    }
  }

  /**
   * Refresh user tokens
   */
  async refreshUserTokens(userId: string): Promise<boolean> {
    try {
      const tokens = await this.getUserTokens(userId);
      if (!tokens?.refresh_token) return false;

      this.oauth2Client.setCredentials({
        refresh_token: tokens.refresh_token
      });

      const { credentials } = await this.oauth2Client.refreshAccessToken();
      
      const newTokens: OAuthTokens = {
        access_token: credentials.access_token!,
        refresh_token: credentials.refresh_token || tokens.refresh_token,
        scope: credentials.scope || tokens.scope,
        token_type: credentials.token_type || tokens.token_type,
        expires_in: credentials.expiry_date ? Math.floor((credentials.expiry_date - Date.now()) / 1000) : 3600,
        expires_at: credentials.expiry_date || Date.now() + 3600000
      };

      await this.storeUserTokens(userId, newTokens);
      return true;

    } catch (error) {
      console.error('Failed to refresh tokens:', error);
      return false;
    }
  }

  /**
   * Create or update FKS user from Google user data
   */
  private async createOrUpdateUser(googleUser: GoogleUser): Promise<FKSUser> {
    const existingUser = await this.getUserByEmail(googleUser.email);
    
    if (existingUser) {
      // Update existing user
      existingUser.name = googleUser.name;
      existingUser.picture = googleUser.picture;
      existingUser.lastLogin = new Date().toISOString();
      return existingUser;
    }

    // Determine user role based on email
    const role = this.determineUserRole(googleUser.email);
    const permissions = this.getPermissionsForRole(role);

    const newUser: FKSUser = {
      id: `user_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      googleId: googleUser.id,
      email: googleUser.email,
      name: googleUser.name,
      picture: googleUser.picture,
      role,
      permissions,
      createdAt: new Date().toISOString(),
      lastLogin: new Date().toISOString(),
      isActive: true
    };

    await this.storeUser(newUser);
    return newUser;
  }

  /**
   * Determine user role based on email
   */
  private determineUserRole(email: string): 'root' | 'admin' | 'user' {
    if (email === this.ROOT_USER.email) {
      return 'root';
    }
    
    if (this.ADMIN_EMAILS.includes(email)) {
      return 'admin';
    }
    
    return 'user';
  }

  /**
   * Get permissions for a user role
   */
  private getPermissionsForRole(role: 'root' | 'admin' | 'user'): string[] {
    switch (role) {
      case 'root':
        return [
          'system:*',
          'user:*',
          'admin:*',
          'trading:*',
          'calendar:*',
          'security:*'
        ];
      
      case 'admin':
        return [
          'user:read',
          'user:create',
          'user:update',
          'admin:dashboard',
          'trading:*',
          'calendar:*',
          'security:read'
        ];
      
      case 'user':
        return [
          'trading:read',
          'trading:execute',
          'calendar:read',
          'calendar:write:own',
          'profile:update:own'
        ];
      
      default:
        return ['trading:read'];
    }
  }

  /**
   * Check if user has specific permission
   */
  hasPermission(user: FKSUser, permission: string): boolean {
    // Root has all permissions
    if (user.role === 'root') return true;
    
    // Check direct permission
    if (user.permissions.includes(permission)) return true;
    
    // Check wildcard permissions
    const permissionParts = permission.split(':');
    for (let i = permissionParts.length - 1; i >= 0; i--) {
      const wildcardPermission = permissionParts.slice(0, i + 1).join(':') + ':*';
      if (user.permissions.includes(wildcardPermission)) return true;
    }
    
    return false;
  }

  /**
   * Store user data securely
   */
  private async storeUser(user: FKSUser): Promise<void> {
    await this.secretManager.storeSecret(`user:${user.id}`, JSON.stringify(user), {
      key: `user:${user.id}`,
      encrypted: true,
      scope: 'system'
    });

    // Store email-to-id mapping for quick lookup
    await this.secretManager.storeSecret(`user_email:${user.email}`, user.id, {
      key: `user_email:${user.email}`,
      encrypted: false,
      scope: 'system'
    });
  }

  /**
   * Update user data
   */
  private async updateUser(user: FKSUser): Promise<void> {
    await this.storeUser(user);
  }

  /**
   * Get user by ID
   */
  private async getStoredUser(userId: string): Promise<FKSUser | null> {
    const userData = await this.secretManager.getSecret(`user:${userId}`, 'system');
    return userData ? JSON.parse(userData) : null;
  }

  /**
   * Get user by email
   */
  private async getUserByEmail(email: string): Promise<FKSUser | null> {
    const userId = await this.secretManager.getSecret(`user_email:${email}`, 'system');
    return userId ? await this.getStoredUser(userId) : null;
  }

  /**
   * Store OAuth tokens for user
   */
  private async storeUserTokens(userId: string, tokens: OAuthTokens): Promise<void> {
    await this.secretManager.storeSecret(`oauth_tokens:${userId}`, JSON.stringify(tokens), {
      key: `oauth_tokens:${userId}`,
      encrypted: true,
      scope: 'user',
      expiresAt: new Date(tokens.expires_at)
    });
  }

  /**
   * Get OAuth tokens for user
   */
  private async getUserTokens(userId: string): Promise<OAuthTokens | null> {
    const tokenData = await this.secretManager.getSecret(`oauth_tokens:${userId}`, 'user');
    return tokenData ? JSON.parse(tokenData) : null;
  }

  /**
   * Get valid OAuth client for user operations
   */
  async getAuthenticatedClient(userId: string): Promise<any> {
    const tokens = await this.getUserTokens(userId);
    if (!tokens) throw new Error('User not authenticated');

    // Check if tokens need refresh
    if (tokens.expires_at < Date.now()) {
      const refreshed = await this.refreshUserTokens(userId);
      if (!refreshed) throw new Error('Failed to refresh authentication');
    }

    const client = new google.auth.OAuth2(
      import.meta.env.VITE_GOOGLE_CLIENT_ID,
      undefined as any,
      import.meta.env.VITE_GOOGLE_REDIRECT_URI
    );

    const freshTokens = await this.getUserTokens(userId);
    client.setCredentials({
      access_token: freshTokens!.access_token,
      refresh_token: freshTokens!.refresh_token
    });

    return client;
  }

  /**
   * Sign out user and clean up
   */
  async signOut(userId?: string): Promise<void> {
    try {
      const currentUserId = userId || localStorage.getItem('current_user_id');
      if (!currentUserId) return;

      // Revoke tokens with Google
      const tokens = await this.getUserTokens(currentUserId);
      if (tokens?.access_token) {
        try {
          await this.oauth2Client.revokeCredentials();
        } catch (error) {
          console.warn('Failed to revoke Google tokens:', error);
        }
      }

      // Clear stored tokens
      await this.secretManager.deleteSecret(`oauth_tokens:${currentUserId}`, 'user');
      
      // Clear local session
      localStorage.removeItem('current_user_id');
      
      console.log('User signed out successfully');

    } catch (error) {
      console.error('Sign out failed:', error);
    }
  }

  /**
   * Get all users (admin only)
   */
  async getAllUsers(requestingUser: FKSUser): Promise<FKSUser[]> {
    if (!this.hasPermission(requestingUser, 'user:read')) {
      throw new Error('Insufficient permissions');
    }

    // This would need to be implemented with a proper user store
    // For now, return empty array
    return [];
  }

  /**
   * Update user role (root/admin only)
   */
  async updateUserRole(requestingUser: FKSUser, targetUserId: string, newRole: 'admin' | 'user'): Promise<boolean> {
    if (!this.hasPermission(requestingUser, 'user:update')) {
      throw new Error('Insufficient permissions');
    }

    const targetUser = await this.getStoredUser(targetUserId);
    if (!targetUser) {
      throw new Error('User not found');
    }

    // Prevent downgrading root user
    if (targetUser.role === 'root') {
      throw new Error('Cannot modify root user role');
    }

    targetUser.role = newRole;
    targetUser.permissions = this.getPermissionsForRole(newRole);
    
    await this.updateUser(targetUser);
    return true;
  }

  /**
   * Health check for Google OAuth service
   */
  async healthCheck(): Promise<{ status: string; details: any }> {
    try {
      const currentUser = await this.getCurrentUser();
      
      return {
        status: 'healthy',
        details: {
          initialized: this.isInitialized,
          authenticated: !!currentUser,
          userRole: currentUser?.role,
          clientConfigured: !!(import.meta.env.VITE_GOOGLE_CLIENT_ID)
        }
      };
    } catch (error) {
      return {
        status: 'unhealthy',
        details: {
          error: error.message,
          initialized: this.isInitialized
        }
      };
    }
  }
}

export default GoogleOAuthService;
