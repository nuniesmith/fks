import { getData, postData } from './dataClient';

export interface BackendConfigSummary {
  system?: any;
  environment?: any;
  logging?: any;
  services?: string[];
}

export interface MergedConfigResponse {
  ok: boolean;
  config: BackendConfigSummary;
  overrides: Record<string,string>;
}

export async function fetchMergedConfig(): Promise<MergedConfigResponse> {
  const data = await getData<MergedConfigResponse>('/config');
  return data as any;
}

export async function updateRuntimeOverrides(kv: Record<string, any>): Promise<{ ok: boolean; updated: Record<string,string>; count: number }> {
  const data = await postData('/config/set', kv);
  return data as any;
}

export function guessSensitive(key: string): boolean {
  return /key|secret|token|password/i.test(key);
}
