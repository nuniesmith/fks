import { Monitor, Palette, Settings, Zap, Code } from 'lucide-react';
import React from 'react';

import { useTheme } from './ThemeProvider';

interface ModernHeaderProps {
  title?: string;
  subtitle?: string;
}

export const ModernHeader: React.FC<ModernHeaderProps> = ({ 
  title = "🎯 FKS Trading Systems", 
  subtitle = "Advanced Trading Strategy Management Platform"
}) => {
  const { theme } = useTheme();

  return (
    <header className="glass-card p-8 mb-8 animated-card">
      <div className="flex flex-col lg:flex-row items-center justify-between gap-6">
        {/* Logo and Title */}
        <div className="text-center lg:text-left">
          <h1 className="text-4xl lg:text-5xl font-bold mb-3 flex items-center justify-center lg:justify-start gap-4 float-animation">
            <span className="text-6xl">🎯</span>
            <span className="gradient-text">{title}</span>
          </h1>
          <p className="text-lg text-white/80 mb-4">{subtitle}</p>
          
          {/* Stats Bar */}
          <div className="flex flex-wrap justify-center lg:justify-start gap-6 text-sm">
            <div className="flex items-center gap-2 status-bull">
              <Zap className="w-4 h-4" />
              <span>Active</span>
            </div>
            <div className="flex items-center gap-2 text-white/70">
              <Monitor className="w-4 h-4" />
              <span>Real-time Monitoring</span>
            </div>
            <div className="flex items-center gap-2 text-white/70">
              <Settings className="w-4 h-4" />
              <span>Advanced Controls</span>
            </div>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center gap-4">
          <a
            href="/vscode/"
            target="_blank"
            rel="noopener noreferrer"
            className="btn-icon group"
            title="Open VS Code IDE"
          >
            <Code className="w-5 h-5 group-hover:text-blue-400 transition-colors" />
          </a>
          
          <button className="btn-icon">
            <Palette className="w-5 h-5" />
          </button>
          
          <button className="btn-icon">
            <Settings className="w-5 h-5" />
          </button>
        </div>
      </div>
      
      {/* Search Bar */}
      <div className="mt-6 max-w-md mx-auto lg:mx-0">
        <input
          type="text"
          placeholder="Search features, logs, or commands..."
          className="input-glass"
        />
      </div>
    </header>
  );
};
