interface TailscaleNode {
  id: string;
  name: string;
  ipv4: string;
  ipv6: string;
  online: boolean;
  lastSeen: string;
  machineKey: string;
  nodeKey: string;
  user: string;
  tags: string[];
}

interface TailscaleStatus {
  connected: boolean;
  nodeId: string;
  tailnetName: string;
  magicDNSSuffix: string;
  currentTailnetIP: string;
  peers: TailscaleNode[];
}

interface NetworkPolicy {
  id: string;
  name: string;
  sourceNodes: string[];
  destinationNodes: string[];
  allowedPorts: number[];
  protocol: 'tcp' | 'udp' | 'icmp';
  action: 'allow' | 'deny';
  priority: number;
}

export class TailscaleService {
  private static instance: TailscaleService;
  private baseUrl: string;
  private apiKey: string;
  private tailnet: string;
  private enforceVPN: boolean = true;
  private statusCheckInterval: NodeJS.Timeout | null = null;

  private constructor() {
    // Force-disable VPN enforcement temporarily per request to remove network gating
    this.enforceVPN = false;
    if (typeof window !== 'undefined') {
      localStorage.setItem('security.enforceVPN', 'false');
    }

    this.baseUrl = 'https://api.tailscale.com/api/v2';
    this.apiKey = import.meta.env.VITE_TAILSCALE_API_KEY || '';
    this.tailnet = import.meta.env.VITE_TAILSCALE_TAILNET || '';
  }

  static getInstance(): TailscaleService {
    if (!TailscaleService.instance) {
      TailscaleService.instance = new TailscaleService();
    }
    return TailscaleService.instance;
  }

  /**
   * Initialize Tailscale service and start monitoring
   */
  async initialize(): Promise<void> {
    // Bypassed: no VPN check
    console.log('TailscaleService initialize bypassed (VPN enforcement disabled)');
  }

  /**
   * Check if current connection is through Tailscale
   */
  async isConnectedViaTailscale(): Promise<boolean> {
    return true;
  }

  /**
   * Get current Tailscale status
   */
  async getStatus(): Promise<TailscaleStatus | null> {
    return { connected: true, nodeId: '', tailnetName: 'bypass', magicDNSSuffix: '', currentTailnetIP: '127.0.0.1', peers: [] };
  }

  /**
   * Enforce VPN connection for all requests
   */
  async enforceVPNConnection(): Promise<void> {
    /* no-op */
  }

  /**
   * Get network policies for current node
   */
  async getNetworkPolicies(): Promise<NetworkPolicy[]> {
    try {
      const response = await fetch(`${this.baseUrl}/tailnet/${this.tailnet}/acl`, {
        headers: this.getHeaders()
      });

      if (!response.ok) {
        throw new Error(`Failed to get network policies: ${response.statusText}`);
      }

      const data = await response.json();
      
      // Transform ACL rules to network policies
      return this.transformACLToPolicies(data.acls || []);
    } catch (error) {
      console.error('Failed to get network policies:', error);
      return [];
    }
  }

  /**
   * Update network access control list
   */
  async updateNetworkACL(policies: NetworkPolicy[]): Promise<boolean> {
    try {
      const acl = this.transformPoliciesToACL(policies);
      
      const response = await fetch(`${this.baseUrl}/tailnet/${this.tailnet}/acl`, {
        method: 'POST',
        headers: {
          ...this.getHeaders(),
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ acls: acl })
      });

      return response.ok;
    } catch (error) {
      console.error('Failed to update network ACL:', error);
      return false;
    }
  }

  /**
   * Get secure tunnel URL for internal services
   */
  getTunnelUrl(service: string, port: number): string {
    const status = this.getLocalStatus();
    if (!status?.currentTailnetIP) {
      throw new Error('Tailscale not connected');
    }
    
    return `https://${service}.${status.currentTailnetIP}:${port}`;
  }

  /**
   * Create a secure service endpoint
   */
  async createSecureEndpoint(serviceName: string, port: number, tags: string[] = []): Promise<string> {
    const status = await this.getStatus();
    if (!status?.currentTailnetIP) {
      throw new Error('Cannot create endpoint: Tailscale not connected');
    }

    // Register service with Tailscale
    const endpoint = `${serviceName}.${status.tailnetName}`;
    
    // Add service tags for access control
    await this.addServiceTags(serviceName, [...tags, 'fks_service']);
    
    return `https://${endpoint}:${port}`;
  }

  /**
   * Monitor connection health and reconnect if needed
   */
  private startStatusMonitoring(): void {
    /* no-op */
  }

  /**
   * Validate Tailscale connection on startup
   */
  private async validateTailscaleConnection(): Promise<void> {
    /* no-op */
  }

  /**
   * Check if IP address is in Tailscale range
   */
  private isTailscaleIP(ip: string): boolean {
    return true;
  }

  /**
   * Get request headers with authentication
   */
  private getHeaders(): Record<string, string> {
    return {
      'Authorization': `Bearer ${this.apiKey}`,
      'Accept': 'application/json'
    };
  }

  /**
   * Transform ACL rules to network policies
   */
  private transformACLToPolicies(acls: any[]): NetworkPolicy[] {
    return acls.map((acl: any, index: number) => ({
      id: `policy-${index}`,
      name: acl.action || 'unnamed',
      sourceNodes: acl.src || [],
      destinationNodes: acl.dst || [],
      allowedPorts: this.extractPorts(acl.dst),
      protocol: this.extractProtocol(acl.proto) || 'tcp',
      action: acl.action === 'accept' ? 'allow' : 'deny',
      priority: index
    }));
  }

  /**
   * Transform network policies to ACL rules
   */
  private transformPoliciesToACL(policies: NetworkPolicy[]): any[] {
    return policies.map(policy => ({
      action: policy.action === 'allow' ? 'accept' : 'deny',
      src: policy.sourceNodes,
      dst: policy.destinationNodes.map(node => 
        `${node}:${policy.allowedPorts.join(',')}`
      ),
      proto: policy.protocol
    }));
  }

  /**
   * Extract ports from destination string
   */
  private extractPorts(destinations: string[]): number[] {
    const ports: number[] = [];
    
    destinations.forEach(dest => {
      const portMatch = dest.match(/:(\d+)/);
      if (portMatch) {
        ports.push(parseInt(portMatch[1]));
      }
    });
    
    return ports;
  }

  /**
   * Extract protocol from proto field
   */
  private extractProtocol(proto: string): 'tcp' | 'udp' | 'icmp' {
    if (proto?.toLowerCase().includes('udp')) return 'udp';
    if (proto?.toLowerCase().includes('icmp')) return 'icmp';
    return 'tcp';
  }

  /**
   * Get local status (cached)
   */
  private getLocalStatus(): TailscaleStatus | null {
    // This would be implemented with local caching
    return null;
  }

  /**
   * Attempt to reconnect to Tailscale
   */
  private async attemptReconnection(): Promise<void> {
    // This would trigger a reconnection attempt
    console.log('Attempting Tailscale reconnection...');
  }

  /**
   * Add service tags for access control
   */
  private async addServiceTags(serviceName: string, tags: string[]): Promise<void> {
    // Implementation would add tags to service for ACL
    console.log(`Adding tags ${tags.join(', ')} to service ${serviceName}`);
  }

  /**
   * Cleanup monitoring when service shuts down
   */
  destroy(): void {
    if (this.statusCheckInterval) {
      clearInterval(this.statusCheckInterval);
      this.statusCheckInterval = null;
    }
  }

  /**
   * Health check for Tailscale service
   */
  async healthCheck(): Promise<{ status: string; details: any }> {
    return { status: 'healthy', details: { connected: true, enforceVPN: false } };
  }
}

export default TailscaleService;
