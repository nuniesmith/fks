import React from 'react';
import clsx from 'clsx';

export interface StatTileProps {
  label: string;
  value: React.ReactNode;
  icon?: React.ReactNode;
  className?: string;
  onClick?: () => void;
}

export const StatTile: React.FC<StatTileProps> = ({ label, value, icon, className = '', onClick }) => {
  return (
    <div className={clsx('stat-tile', onClick && 'cursor-pointer hover:translate-y-[-2px] transition-transform', className)} onClick={onClick}>
      <p className="stat-label">{label}</p>
      <div className="flex items-end justify-between gap-2">
        <p className="stat-value">{value}</p>
        {icon && <span className="opacity-80 text-blue-400 h-5 w-5 md:h-6 md:w-6 flex items-center justify-center">{icon}</span>}
      </div>
    </div>
  );
};

export default StatTile;
