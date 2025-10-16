import React, { createContext, useContext, useEffect, useState } from 'react';

type Theme = 'light' | 'dark' | 'trading';

interface ThemeContextType {
  theme: Theme;
  setTheme: (theme: Theme) => void;
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined);

export const useTheme = () => {
  const context = useContext(ThemeContext);
  if (context === undefined) {
    throw new Error('useTheme must be used within a ThemeProvider');
  }
  return context;
};

interface ThemeProviderProps {
  children: React.ReactNode;
}

export const ThemeProvider: React.FC<ThemeProviderProps> = ({ children }) => {
  const [theme, setTheme] = useState<Theme>(() => {
    try {
      const stored = localStorage.getItem('fks.ui.theme') as Theme | null
      if (stored) return stored
      // System preference: if prefers dark, start dark, else trading gradient
      if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) return 'dark'
      return 'trading'
    } catch { return 'trading' }
  });

  useEffect(() => {
    try { localStorage.setItem('fks.ui.theme', theme) } catch {}
    const root = document.documentElement;
    root.classList.remove('light', 'dark', 'trading');
    root.classList.add(theme);
    root.setAttribute('data-theme', theme);
  }, [theme]);

  return (
    <ThemeContext.Provider value={{ theme, setTheme }}>
      <div className={`theme-${theme} min-h-screen transition-colors duration-500 ease-in-out`}>
        {children}
      </div>
    </ThemeContext.Provider>
  );
};
