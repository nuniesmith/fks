// components/ErrorBoundary.tsx
import { AlertCircle } from 'lucide-react';
import React from 'react';

interface ErrorBoundaryState {
  hasError: boolean;
  error?: Error;
}

export class ErrorBoundary extends React.Component<
  React.PropsWithChildren<unknown>,
  ErrorBoundaryState
> {
  constructor(props: React.PropsWithChildren<unknown>) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error('Error caught by boundary:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen bg-gray-50 flex items-center justify-center">
          <div className="bg-white p-6 rounded-lg shadow-sm border border-red-200 max-w-md">
            <div className="flex items-center mb-4">
              <AlertCircle className="w-6 h-6 text-red-500 mr-2" />
              <h2 className="text-lg font-semibold text-red-800">Something went wrong</h2>
            </div>
            <p className="text-red-600 mb-4">
              The application encountered an unexpected error. Please refresh the page to try again.
            </p>
            <button
              onClick={() => window.location.reload()}
              className="w-full bg-red-500 text-white py-2 px-4 rounded hover:bg-red-600"
            >
              Refresh Page
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

// Enhanced API service with better error handling
class ApiService {
  private baseUrl: string;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl;
  }

  private async handleResponse<T>(response: Response): Promise<T> {
    if (!response.ok) {
      const errorData = await response.text().catch(() => 'Network error');
      throw new Error(`API Error (${response.status}): ${errorData}`);
    }
    
    const contentType = response.headers.get('content-type');
    if (contentType?.includes('application/json')) {
      return response.json();
    }
    
    return response.text() as T;
  }

  async build(): Promise<any> {
    const response = await fetch(`${this.baseUrl}/api/build`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      signal: AbortSignal.timeout(300000) // 5 minute timeout
    });
    
    return this.handleResponse(response);
  }

  async package(): Promise<any> {
    const response = await fetch(`${this.baseUrl}/api/package`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      signal: AbortSignal.timeout(60000) // 1 minute timeout
    });
    
    return this.handleResponse(response);
  }

  async generateTemplate(type: string, fileName: string): Promise<any> {
    const response = await fetch(`${this.baseUrl}/api/template`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ type, fileName }),
      signal: AbortSignal.timeout(30000) // 30 second timeout
    });
    
    return this.handleResponse(response);
  }

  async downloadAddon(): Promise<Blob> {
    const response = await fetch(`${this.baseUrl}/api/download/fks_addon.zip`, {
      signal: AbortSignal.timeout(60000) // 1 minute timeout
    });
    
    if (!response.ok) {
      throw new Error(`Download failed: ${response.statusText}`);
    }
    
    return response.blob();
  }

  async checkHealth(): Promise<boolean> {
    try {
      const response = await fetch(`${this.baseUrl}/api/health`, {
        signal: AbortSignal.timeout(5000) // 5 second timeout
      });
      return response.ok;
    } catch {
      return false;
    }
  }
}

export { ApiService };