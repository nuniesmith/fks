import { Moon, Palette, Sun } from 'lucide-react';
import React from 'react';

import { useTheme } from './ThemeProvider';

export const ThemeToggle: React.FC = () => {
  const { theme, setTheme } = useTheme();

  const getIcon = () => {
    switch (theme) {
      case 'light':
        return <Sun className="w-5 h-5" />;
      case 'dark':
        return <Moon className="w-5 h-5" />;
      case 'trading':
      default:
        return <Palette className="w-5 h-5" />;
    }
  };

  const cycleTheme = () => {
    const themes = ['trading', 'light', 'dark'] as const;
    const currentIndex = themes.indexOf(theme);
    const nextIndex = (currentIndex + 1) % themes.length;
    setTheme(themes[nextIndex]);
  };

  return (
    <button
      onClick={cycleTheme}
      className="p-3 rounded-full bg-white/20 hover:bg-white/30 backdrop-blur-sm border border-white/30 transition-all duration-300 transform hover:scale-110 flex items-center gap-2"
      title={`Current theme: ${theme}. Click to switch.`}
    >
      {getIcon()}
      <span className="text-sm font-medium text-white/90 capitalize hidden sm:inline">
        {theme}
      </span>
    </button>
  );
};
