// services/ApiService.ts
export interface ApiResponse<T = any> {
    success: boolean;
    data?: T;
    error?: string;
    stdout?: string;
    stderr?: string;
    size?: number;
}

export class ApiService {
    private baseUrl: string;
    private timeout: number;

    constructor(baseUrl: string, timeout: number = 30000) {
        this.baseUrl = baseUrl.replace(/\/+$/, ''); // Remove trailing slashes
        this.timeout = timeout;
    }

    private async makeRequest<T = any>(
        endpoint: string,
        options: RequestInit = {}
    ): Promise<ApiResponse<T>> {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), this.timeout);

        try {
            const response = await fetch(`${this.baseUrl}${endpoint}`, {
                ...options,
                signal: controller.signal,
                headers: {
                    'Content-Type': 'application/json',
                    ...options.headers,
                },
            });

            clearTimeout(timeoutId);

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const data = await response.json();
            return data;
        } catch (error) {
            clearTimeout(timeoutId);

            if (error instanceof Error) {
                if (error.name === 'AbortError') {
                    throw new Error('Request timeout');
                }
                throw error;
            }
            throw new Error('Unknown error occurred');
        }
    }

    async checkHealth(): Promise<boolean> {
        try {
            const response = await this.makeRequest('/api/health');
            return response.success === true;
        } catch {
            return false;
        }
    }

    async build(): Promise<ApiResponse> {
        return this.makeRequest('/api/build', {
            method: 'POST',
        });
    }

    async package(): Promise<ApiResponse> {
        return this.makeRequest('/api/package', {
            method: 'POST',
        });
    }

    async generateTemplate(type: string, fileName: string): Promise<ApiResponse> {
        return this.makeRequest('/api/template', {
            method: 'POST',
            body: JSON.stringify({ type, fileName }),
        });
    }

    async downloadFile(filename: string): Promise<Blob> {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), this.timeout);

        try {
            const response = await fetch(`${this.baseUrl}/api/download/${filename}`, {
                signal: controller.signal,
            });

            clearTimeout(timeoutId);

            if (!response.ok) {
                throw new Error(`Download failed: ${response.statusText}`);
            }

            return await response.blob();
        } catch (error) {
            clearTimeout(timeoutId);
            throw error;
        }
    }
}
