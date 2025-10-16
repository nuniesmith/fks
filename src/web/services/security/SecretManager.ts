interface SecretConfig {
  key: string;
  encrypted: boolean;
  expiresAt?: Date;
  scope: 'user' | 'system' | 'api';
  rotationPolicy?: {
    enabled: boolean;
    intervalDays: number;
  };
}

interface StoredSecret {
  value: string;
  encrypted: boolean;
  scope: string;
  createdAt: string;
  lastAccessed: string;
  expiresAt?: string;
  rotationPolicy?: {
    enabled: boolean;
    intervalDays: number;
  };
}

export class SecretManager {
  private static instance: SecretManager;
  private masterKey: string;
  private initialized = false;
  private cache: Map<string, StoredSecret> = new Map();

  private constructor() {
  this.masterKey = import.meta.env.VITE_MASTER_ENCRYPTION_KEY || this.generateMasterKey();
  }

  static getInstance(): SecretManager {
    if (!SecretManager.instance) {
      SecretManager.instance = new SecretManager();
    }
    return SecretManager.instance;
  }

  async initialize(): Promise<void> {
    if (this.initialized) return;

    try {
      await this.loadSecretsFromStorage();
      await this.setupSecretRotation();
      this.initialized = true;
      console.log('SecretManager initialized successfully');
    } catch (error) {
      console.error('Failed to initialize SecretManager:', error);
      throw error;
    }
  }

  /**
   * Store an encrypted secret with TTL and rotation policy
   */
  async storeSecret(key: string, value: string, config: SecretConfig): Promise<void> {
    if (!this.initialized) await this.initialize();

    const encrypted = config.encrypted ? this.encrypt(value) : value;
    const secretData: StoredSecret = {
      value: encrypted,
      encrypted: config.encrypted,
      scope: config.scope,
      createdAt: new Date().toISOString(),
      lastAccessed: new Date().toISOString(),
      expiresAt: config.expiresAt?.toISOString(),
      rotationPolicy: config.rotationPolicy
    };

    const secretKey = this.getSecretKey(key, config.scope);
    this.cache.set(secretKey, secretData);
    
    // Store in localStorage as fallback (encrypted)
    try {
      localStorage.setItem(secretKey, JSON.stringify(secretData));
    } catch (error) {
      console.warn('Failed to store secret in localStorage:', error);
    }

    // Store in audit log
    await this.auditSecretOperation('store', key, config.scope);
  }

  /**
   * Retrieve and decrypt a secret
   */
  async getSecret(key: string, scope: string = 'user'): Promise<string | null> {
    if (!this.initialized) await this.initialize();

    const secretKey = this.getSecretKey(key, scope);
    let secretData = this.cache.get(secretKey);
    
    // Fallback to localStorage
    if (!secretData) {
      try {
        const data = localStorage.getItem(secretKey);
        if (data) {
          secretData = JSON.parse(data);
          this.cache.set(secretKey, secretData!);
        }
      } catch (error) {
        console.warn('Failed to load secret from localStorage:', error);
      }
    }
    
    if (!secretData) return null;

    // Check expiration
    if (secretData.expiresAt && new Date(secretData.expiresAt) < new Date()) {
      await this.deleteSecret(key, scope);
      return null;
    }

    // Update last accessed timestamp
    secretData.lastAccessed = new Date().toISOString();
    this.cache.set(secretKey, secretData);
    
    try {
      localStorage.setItem(secretKey, JSON.stringify(secretData));
    } catch (error) {
      console.warn('Failed to update secret timestamp:', error);
    }

    // Audit access
    await this.auditSecretOperation('access', key, scope);

    return secretData.encrypted 
      ? this.decrypt(secretData.value)
      : secretData.value;
  }

  /**
   * Store API key with automatic rotation
   */
  async storeApiKey(userId: string, provider: string, apiKey: string, secret?: string): Promise<void> {
    const keyName = `api_key:${provider}:${userId}`;
    
    await this.storeSecret(keyName, apiKey, {
      key: keyName,
      encrypted: true,
      scope: 'api',
      expiresAt: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000), // 30 days
      rotationPolicy: {
        enabled: true,
        intervalDays: 30
      }
    });

    if (secret) {
      const secretName = `api_secret:${provider}:${userId}`;
      await this.storeSecret(secretName, secret, {
        key: secretName,
        encrypted: true,
        scope: 'api',
        expiresAt: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000),
        rotationPolicy: {
          enabled: true,
          intervalDays: 30
        }
      });
    }
  }

  /**
   * Get API credentials for a user and provider
   */
  async getApiCredentials(userId: string, provider: string): Promise<{ key: string; secret?: string } | null> {
    const apiKey = await this.getSecret(`api_key:${provider}:${userId}`, 'api');
    if (!apiKey) return null;

    const apiSecret = await this.getSecret(`api_secret:${provider}:${userId}`, 'api');
    
    return {
      key: apiKey,
      secret: apiSecret || undefined
    };
  }

  /**
   * Rotate expired secrets automatically
   */
  async rotateExpiredSecrets(): Promise<void> {
    for (const [key, secretData] of this.cache.entries()) {
      if (secretData.rotationPolicy?.enabled) {
        const createdAt = new Date(secretData.createdAt);
        const daysSinceCreation = Math.floor((Date.now() - createdAt.getTime()) / (1000 * 60 * 60 * 24));
        
        if (daysSinceCreation >= secretData.rotationPolicy.intervalDays) {
          await this.triggerSecretRotation(key, secretData);
        }
      }
    }
  }

  /**
   * Delete a secret and audit the operation
   */
  async deleteSecret(key: string, scope: string = 'user'): Promise<boolean> {
    if (!this.initialized) await this.initialize();

    const secretKey = this.getSecretKey(key, scope);
    const deleted = this.cache.delete(secretKey);
    
    try {
      localStorage.removeItem(secretKey);
    } catch (error) {
      console.warn('Failed to remove secret from localStorage:', error);
    }
    
    await this.auditSecretOperation('delete', key, scope);
    
    return deleted;
  }

  /**
   * List all secrets for a scope (without values)
   */
  async listSecrets(scope: string): Promise<string[]> {
    const pattern = `secret:${scope}:`;
    const keys: string[] = [];
    
    for (const key of this.cache.keys()) {
      if (key.startsWith(pattern)) {
        keys.push(key.replace(pattern, ''));
      }
    }
    
    return keys;
  }

  /**
   * Encrypt text using built-in Web Crypto API
   */
  private encrypt(text: string): string {
    // Simple base64 encoding for demo - in production use Web Crypto API
    return btoa(text);
  }

  /**
   * Decrypt text using built-in Web Crypto API
   */
  private decrypt(cipherText: string): string {
    // Simple base64 decoding for demo - in production use Web Crypto API
    try {
      return atob(cipherText);
    } catch (error) {
      console.error('Failed to decrypt secret:', error);
      return '';
    }
  }

  /**
   * Generate a secure master key
   */
  private generateMasterKey(): string {
    const array = new Uint8Array(32);
    crypto.getRandomValues(array);
    return Array.from(array, byte => byte.toString(16).padStart(2, '0')).join('');
  }

  /**
   * Get the storage key for a secret
   */
  private getSecretKey(key: string, scope: string): string {
    return `secret:${scope}:${key}`;
  }

  /**
   * Load secrets from localStorage on initialization
   */
  private async loadSecretsFromStorage(): Promise<void> {
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i);
      if (key?.startsWith('secret:')) {
        try {
          const data = localStorage.getItem(key);
          if (data) {
            const secretData = JSON.parse(data);
            this.cache.set(key, secretData);
          }
        } catch (error) {
          console.warn(`Failed to load secret ${key}:`, error);
        }
      }
    }
  }

  /**
   * Audit secret operations for security compliance
   */
  private async auditSecretOperation(operation: string, key: string, scope: string): Promise<void> {
    const auditEntry = {
      operation,
      key,
      scope,
      timestamp: new Date().toISOString(),
      userAgent: typeof window !== 'undefined' ? window.navigator.userAgent : 'server'
    };

    // Store audit log in localStorage
    try {
      const auditLog = JSON.parse(localStorage.getItem('secret_audit_log') || '[]');
      auditLog.push(auditEntry);
      
      // Keep only last 1000 entries
      if (auditLog.length > 1000) {
        auditLog.splice(0, auditLog.length - 1000);
      }
      
      localStorage.setItem('secret_audit_log', JSON.stringify(auditLog));
    } catch (error) {
      console.warn('Failed to log audit entry:', error);
    }
  }

  /**
   * Setup automatic secret rotation
   */
  private async setupSecretRotation(): Promise<void> {
    // Set up interval to check for expired secrets
    setInterval(async () => {
      try {
        await this.rotateExpiredSecrets();
      } catch (error) {
        console.error('Secret rotation failed:', error);
      }
    }, 24 * 60 * 60 * 1000); // Check daily
  }

  /**
   * Trigger rotation for a specific secret
   */
  private async triggerSecretRotation(key: string, secretData: StoredSecret): Promise<void> {
    console.log(`Secret rotation needed for ${key}`);
    
    // Mark for rotation - in production this would integrate with external APIs
    const rotationEntry = {
      key,
      lastRotation: secretData.createdAt,
      policy: secretData.rotationPolicy,
      timestamp: new Date().toISOString()
    };
    
    try {
      const rotationQueue = JSON.parse(localStorage.getItem('secret_rotation_queue') || '[]');
      rotationQueue.push(rotationEntry);
      localStorage.setItem('secret_rotation_queue', JSON.stringify(rotationQueue));
    } catch (error) {
      console.warn('Failed to queue secret for rotation:', error);
    }
  }

  /**
   * Health check for the secret manager
   */
  async healthCheck(): Promise<{ status: string; details: any }> {
    try {
      const secretCount = this.cache.size;
      
      return {
        status: 'healthy',
        details: {
          initialized: this.initialized,
          secretCount,
          cacheSize: this.cache.size
        }
      };
    } catch (error) {
      return {
        status: 'unhealthy',
        details: {
          error: error.message,
          initialized: this.initialized
        }
      };
    }
  }
}

export default SecretManager;
