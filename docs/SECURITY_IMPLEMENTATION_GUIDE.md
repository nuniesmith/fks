# FKS Security Implementation Guide

## Overview

This guide implements a comprehensive security framework for the FKS trading platform with **Tailscale-first security** as the top priority, integrated with Authentik for user management, passkey support, and encrypted secrets management.

## 🔐 Security Architecture

### 1. Tailscale VPN (Priority #1)
- **Enforced by default** - All traffic must go through Tailscale
- Zero-trust network architecture
- Automatic connection monitoring and reconnection
- Network policy enforcement through ACLs

### 2. Authentik SSO Integration
- OAuth 2.0 with PKCE for secure authentication
- **Passkey support by default** using WebAuthn
- User management and group-based authorization
- Session management with automatic token refresh

### 3. Encrypted Secrets Management
- **Moving away from localStorage** to encrypted Redis/PostgreSQL storage
- Automatic secret rotation policies
- Audit logging for all secret operations
- API key management with provider-specific handling

### 4. Performance Monitoring
- Security-aware performance tracking
- Real-time monitoring of VPN connections
- Component render performance with security validation
- Network request monitoring with Tailscale verification

## 🚀 Implementation Steps

### Phase 1: Core Security Services (Critical)

#### 1.1 Tailscale Integration
```bash
# Environment setup
export TAILSCALE_API_KEY="your_api_key"
export TAILSCALE_TAILNET="your_tailnet"
export REACT_APP_ENFORCE_VPN=true
```

#### 1.2 Authentik Configuration
```bash
# Docker Compose already includes Authentik
# Configure OAuth application in Authentik UI:
# - Client ID: fks-trading-platform
# - Redirect URI: https://your-app.ts.net/auth/callback
# - Enable passkey support in flow
```

#### 1.3 Secret Manager Setup
```typescript
import { SecretManager } from './services/security';

const secretManager = SecretManager.getInstance();
await secretManager.initialize();

// Store encrypted API keys
await secretManager.storeApiKey(userId, 'trading_provider', apiKey, apiSecret);
```

### Phase 2: React Integration

#### 2.1 Security Provider Setup
```tsx
import { SecurityProvider } from './contexts/SecurityContext';

function App() {
  return (
    <SecurityProvider enforceVPN={true} requirePasskeys={true}>
      <Router>
        <Routes>
          {/* Your app routes */}
        </Routes>
      </Router>
    </SecurityProvider>
  );
}
```

#### 2.2 Component Security Integration
```tsx
import { useSecurityContext } from './contexts/SecurityContext';

function TradingDashboard() {
  const { 
    authenticated, 
    vpnConnected, 
    securityLevel,
    validateSecurity 
  } = useSecurityContext();

  useEffect(() => {
    // Validate security before loading sensitive data
    validateSecurity();
  }, [validateSecurity]);

  if (!authenticated || !vpnConnected) {
    return <SecurityDashboard />;
  }

  return <YourTradingInterface />;
}
```

### Phase 3: Enhanced Security Features

#### 3.1 Passkey Registration
```tsx
import { useSecurityContext } from './contexts/SecurityContext';

function UserProfile() {
  const { registerPasskey } = useSecurityContext();

  const handlePasskeySetup = async () => {
    try {
      await registerPasskey('Desktop - Chrome');
      // Show success message
    } catch (error) {
      // Handle error
    }
  };

  return (
    <button onClick={handlePasskeySetup}>
      Set Up Passkey
    </button>
  );
}
```

#### 3.2 Performance Monitoring
```tsx
import { PerformanceMonitor } from './services/security';

function TradingChart() {
  const performanceMonitor = PerformanceMonitor.getInstance();

  const handleDataLoad = async () => {
    await performanceMonitor.measureAsyncOperation(
      'trading_data_load',
      () => fetchTradingData(),
      true // validateSecurity
    );
  };

  return performanceMonitor.measureComponentRender(
    'TradingChart',
    () => <ChartComponent />,
    { symbol: 'AAPL', timeframe: '1D' }
  );
}
```

## 🔧 Configuration

### Environment Variables (.env.local)
```bash
# Copy from .env.example and configure:
cp .env.example .env.local

# Required Variables:
TAILSCALE_API_KEY=your_tailscale_api_key
AUTHELIA_CLIENT_SECRET=your_authelia_secret
MASTER_ENCRYPTION_KEY=your_encryption_key
```

### Docker Compose Updates
The existing docker-compose.yml already includes Authentik services. Ensure these are running:
```bash
docker-compose up -d authelia-server authelia-worker
```

### Tailscale Setup
1. Install Tailscale on your development machine
2. Join your Tailnet
3. Configure ACLs for FKS services
4. Update environment variables

## 🛡️ Security Features

### 1. VPN Enforcement
- **Automatic connection validation** before any API calls
- Real-time monitoring with reconnection attempts
- User notifications for VPN disconnections
- Service-level VPN requirements

### 2. Passkey Authentication
- **WebAuthn implementation** with platform authenticators
- Biometric authentication (fingerprint, Face ID)
- Security key support (YubiKey, etc.)
- Fallback to OAuth for unsupported devices

### 3. Encrypted Secrets
- **AES encryption** for all stored secrets
- Automatic rotation policies
- Audit trail for all operations
- Secure API key management

### 4. Performance Security
- Security-aware performance monitoring
- VPN connection validation in metrics
- Component-level security tracking
- Network request security validation

## 📊 Security Dashboard

The SecurityDashboard component provides real-time security status:

```tsx
import SecurityDashboard from './components/Security/SecurityDashboard';

<SecurityDashboard 
  showDetails={true} 
  className="mb-4" 
/>
```

Features:
- VPN connection status
- Authentication state
- Security level indicator
- Passkey registration prompts
- Performance insights

## 🔍 Monitoring & Alerts

### Real-time Security Events
```typescript
const { onSecurityEvent } = useSecurityContext();

useEffect(() => {
  onSecurityEvent((event) => {
    if (event.severity === 'critical') {
      // Show alert, log to monitoring service
      console.error('CRITICAL SECURITY EVENT:', event);
    }
  });
}, [onSecurityEvent]);
```

### Performance Insights
```typescript
const performanceMonitor = PerformanceMonitor.getInstance();
const insights = performanceMonitor.getPerformanceInsights();
// Returns array of security and performance recommendations
```

## 🚨 Emergency Procedures

### Security Shutdown
```typescript
import { SecurityOrchestrator } from './services/security';

const securityOrchestrator = SecurityOrchestrator.getInstance();

// In case of security breach
securityOrchestrator.emergencyShutdown();
```

This will:
- Stop all monitoring
- Clear all stored tokens
- Disconnect VPN monitoring
- Log emergency event

## 📋 Migration Checklist

### From Current Setup
- [ ] Configure Tailscale API credentials
- [ ] Set up Authentik OAuth application
- [ ] Generate master encryption key
- [ ] Update environment variables
- [ ] Test VPN enforcement
- [ ] Register test passkeys
- [ ] Migrate existing secrets
- [ ] Update API calls to use SecretManager
- [ ] Add SecurityProvider to App
- [ ] Test complete authentication flow

### Verification Steps
- [ ] VPN disconnection triggers warnings
- [ ] Passkey authentication works
- [ ] Secrets are encrypted in storage
- [ ] Performance monitoring active
- [ ] Security dashboard shows accurate status
- [ ] Emergency shutdown functions

## 🔗 Integration Points

### With Existing Services
- **Trading API**: Secure credential storage
- **WebSocket**: VPN-verified connections
- **Database**: Encrypted sensitive data
- **File System**: Secure configuration management

### With External Services
- **Tailscale**: Network security layer
- **Authentik**: User authentication
- **Google Calendar**: Secure API key storage
- **Trading Providers**: Encrypted credentials

## 📚 API Reference

### SecurityOrchestrator
- `initialize()`: Initialize all security services
- `validateSecurityPosture()`: Check complete security status
- `enforceSecurityPolicies()`: Validate before operations
- `initiateAuthentication()`: Start auth flow
- `registerPasskey()`: Register new passkey

### SecretManager
- `storeSecret()`: Store encrypted secret
- `getSecret()`: Retrieve decrypted secret
- `storeApiKey()`: Store API credentials
- `getApiCredentials()`: Get API credentials

### TailscaleService
- `isConnectedViaTailscale()`: Check VPN status
- `enforceVPNConnection()`: Enforce VPN requirement
- `getStatus()`: Get Tailscale network status

### AuthentikService
- `initiateOAuthFlow()`: Start OAuth authentication
- `authenticateWithPasskey()`: Passkey authentication
- `registerPasskey()`: Register new passkey

This implementation provides a comprehensive, security-first approach that prioritizes Tailscale VPN, implements passkey authentication through Authentik, and ensures encrypted secrets management while maintaining high performance through continuous monitoring.
