// Central feature flags for conditional runtime functionality
// Controlled via Vite env vars (add to .env or .env.local)

export const features = {
  ninjaTrader: import.meta.env.VITE_ENABLE_NINJATRADER === 'true'
};

export type FeatureKey = keyof typeof features;
export const isFeatureEnabled = (key: FeatureKey) => !!features[key];
