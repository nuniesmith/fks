// Minimal interface and mock used in unit tests; can be swapped with full implementation when needed.
export interface AuthTokens { access_token: string; refresh_token?: string }

class AuthentikServiceMock {
  static instance: AuthentikServiceMock | null = null;
  static getInstance(): AuthentikServiceMock {
    if (!this.instance) this.instance = new AuthentikServiceMock();
    return this.instance;
  }
  async refreshToken(refresh: string): Promise<AuthTokens> {
    return { access_token: `${refresh}-refreshed`, refresh_token: refresh };
  }
}

export default AuthentikServiceMock;
