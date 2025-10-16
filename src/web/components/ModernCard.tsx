import React from 'react';

import type { LucideIcon } from 'lucide-react';

interface ModernCardProps {
  title: string;
  subtitle?: string;
  icon?: LucideIcon;
  children: React.ReactNode;
  className?: string;
  variant?: 'default' | 'success' | 'warning' | 'danger' | 'info';
  gradient?: boolean;
  hoverable?: boolean;
  loading?: boolean;
}

export const ModernCard: React.FC<ModernCardProps> = ({
  title,
  subtitle,
  icon: Icon,
  children,
  className = '',
  variant = 'default',
  gradient = false,
  hoverable = true,
  loading = false
}) => {
  const getVariantClasses = () => {
    switch (variant) {
      case 'success':
        return 'border-l-4 border-l-green-400 bg-gradient-to-r from-green-500/20 to-green-600/10';
      case 'warning':
        return 'border-l-4 border-l-yellow-400 bg-gradient-to-r from-yellow-500/20 to-yellow-600/10';
      case 'danger':
        return 'border-l-4 border-l-red-400 bg-gradient-to-r from-red-500/20 to-red-600/10';
      case 'info':
        return 'border-l-4 border-l-blue-400 bg-gradient-to-r from-blue-500/20 to-blue-600/10';
      default:
        return '';
    }
  };

  const cardClasses = `
    glass-card p-6 transition-all duration-300 relative
    ${hoverable ? 'hover:shadow-glass-hover hover:-translate-y-1 cursor-pointer' : ''}
    ${gradient ? 'bg-gradient-to-br from-gray-800/50 to-gray-900/50' : ''}
    ${getVariantClasses()}
    ${className}
  `;

  return (
    <div className={cardClasses}>
      {loading && (
        <div className="absolute inset-0 bg-gray-900/60 backdrop-blur-sm rounded-glass flex items-center justify-center z-10">
          <div className="spinner border-white/50 border-t-white"></div>
        </div>
      )}
      
      {/* Header */}
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-3">
          {Icon && (
            <div className="p-2 rounded-lg bg-gradient-primary shadow-lg">
              <Icon className="w-5 h-5 text-white" />
            </div>
          )}
          <div>
            <h3 className="text-lg font-semibold text-white drop-shadow-sm">{title}</h3>
            {subtitle && (
              <p className="text-sm text-gray-300 mt-1">{subtitle}</p>
            )}
          </div>
        </div>
      </div>
      
      {/* Content */}
      <div className="text-gray-100">
        {children}
      </div>
    </div>
  );
};

interface StatsCardProps {
  title: string;
  value: string | number;
  change?: {
    value: number;
    type: 'increase' | 'decrease';
    timeframe?: string;
  };
  icon?: LucideIcon;
  color?: 'blue' | 'green' | 'red' | 'yellow' | 'purple';
}

export const StatsCard: React.FC<StatsCardProps> = ({
  title,
  value,
  change,
  icon: Icon,
  color = 'blue'
}) => {
  const getColorClasses = () => {
    switch (color) {
      case 'green':
        return 'from-green-500/30 to-green-600/20 border-green-400/40';
      case 'red':
        return 'from-red-500/30 to-red-600/20 border-red-400/40';
      case 'yellow':
        return 'from-yellow-500/30 to-yellow-600/20 border-yellow-400/40';
      case 'purple':
        return 'from-purple-500/30 to-purple-600/20 border-purple-400/40';
      default:
        return 'from-blue-500/30 to-blue-600/20 border-blue-400/40';
    }
  };

  return (
    <div className={`glass-card p-6 bg-gradient-to-br ${getColorClasses()} border-2 hover:shadow-glass-hover hover:-translate-y-1 transition-all duration-300`}>
      <div className="flex items-center justify-between">
        <div>
          <p className="text-gray-200 text-sm font-medium uppercase tracking-wide">{title}</p>
          <p className="text-3xl font-bold text-white mt-2 drop-shadow-sm">{value}</p>
          
          {change && (
            <div className={`flex items-center gap-1 mt-3 text-sm font-semibold ${
              change.type === 'increase' ? 'text-green-300' : 'text-red-300'
            }`}>
              <span className="text-lg">{change.type === 'increase' ? '↗' : '↘'}</span>
              <span>{Math.abs(change.value)}%</span>
              {change.timeframe && (
                <span className="text-gray-400 font-normal">vs {change.timeframe}</span>
              )}
            </div>
          )}
        </div>
        
        {Icon && (
          <div className="p-4 rounded-xl bg-white/15 backdrop-blur-sm shadow-lg">
            <Icon className="w-7 h-7 text-white drop-shadow-sm" />
          </div>
        )}
      </div>
    </div>
  );
};

interface ActionCardProps {
  title: string;
  description: string;
  action: string;
  onClick: () => void;
  icon?: LucideIcon;
  variant?: 'primary' | 'secondary' | 'success' | 'danger';
  disabled?: boolean;
  loading?: boolean;
}

export const ActionCard: React.FC<ActionCardProps> = ({
  title,
  description,
  action,
  onClick,
  icon: Icon,
  variant = 'primary',
  disabled = false,
  loading = false
}) => {
  const getButtonClasses = () => {
    switch (variant) {
      case 'secondary':
        return 'btn-secondary';
      case 'success':
        return 'btn-success';
      case 'danger':
        return 'btn-danger';
      default:
        return 'btn-primary';
    }
  };

  return (
    <div className="glass-card p-6 hover:shadow-glass-hover hover:-translate-y-1 transition-all duration-300 border border-gray-600/40">
      <div className="flex items-start gap-4">
        {Icon && (
          <div className="p-3 rounded-xl bg-gradient-primary flex-shrink-0 mt-1 shadow-lg">
            <Icon className="w-6 h-6 text-white" />
          </div>
        )}
        
        <div className="flex-grow">
          <h3 className="text-lg font-semibold text-white mb-2 drop-shadow-sm">{title}</h3>
          <p className="text-gray-200 mb-4 leading-relaxed">{description}</p>
          
          <button
            onClick={onClick}
            disabled={disabled || loading}
            className={`${getButtonClasses()} ${disabled ? 'opacity-50 cursor-not-allowed' : ''}`}
          >
            {loading ? (
              <div className="flex items-center gap-2">
                <div className="spinner w-4 h-4 border-white/50 border-t-white"></div>
                <span>Loading...</span>
              </div>
            ) : (
              action
            )}
          </button>
        </div>
      </div>
    </div>
  );
};
