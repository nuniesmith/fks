import React, { createContext, useContext, useState, useCallback, useEffect } from 'react';

export type Density = 'comfortable' | 'compact';
interface UISettingsState {
  density: Density;
  toggleDensity: () => void;
  setDensity: (d: Density) => void;
}

const UISettingsContext = createContext<UISettingsState | undefined>(undefined);

const LS_KEY = 'fks.ui.density';

export const UISettingsProvider: React.FC<React.PropsWithChildren> = ({ children }) => {
  const [density, setDensityState] = useState<Density>(() => {
    try { return (localStorage.getItem(LS_KEY) as Density) || 'comfortable'; } catch { return 'comfortable'; }
  });

  useEffect(() => { try { localStorage.setItem(LS_KEY, density); } catch {} }, [density]);

  const setDensity = useCallback((d: Density) => setDensityState(d), []);
  const toggleDensity = useCallback(() => setDensityState(d => d === 'compact' ? 'comfortable' : 'compact'), []);

  // Keyboard shortcut Shift + D to toggle density
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'D' && e.shiftKey) {
        e.preventDefault();
        toggleDensity();
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [toggleDensity]);

  return (
    <UISettingsContext.Provider value={{ density, toggleDensity, setDensity }}>
      <div data-density={density} className="density-animated">
        {children}
      </div>
    </UISettingsContext.Provider>
  );
};

export const useUISettings = () => {
  const ctx = useContext(UISettingsContext);
  if (!ctx) throw new Error('useUISettings must be used within UISettingsProvider');
  return ctx;
};

export default UISettingsProvider;