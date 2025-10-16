// hooks/useApiCall.ts
import { useState } from 'react';

interface ApiCallState<T = any> {
  data: T | null;
  loading: boolean;
  error: string | null;
}

interface UseApiCallReturn<T> extends ApiCallState<T> {
  execute: (apiCall: () => Promise<T>) => Promise<void>;
  reset: () => void;
}

export const useApiCall = <T = any>(): UseApiCallReturn<T> => {
  const [state, setState] = useState<ApiCallState<T>>({
    data: null,
    loading: false,
    error: null
  });

  const execute = async (apiCall: () => Promise<T>) => {
    setState(prev => ({ ...prev, loading: true, error: null }));
    
    try {
      const result = await apiCall();
      setState({ data: result, loading: false, error: null });
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'An unknown error occurred';
      setState({ data: null, loading: false, error: errorMessage });
      throw error; // Re-throw for component-specific handling
    }
  };

  const reset = () => {
    setState({ data: null, loading: false, error: null });
  };

  return { ...state, execute, reset };
};