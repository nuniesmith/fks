// components/TabButton.tsx - Accessible tab button
import React from 'react';

import type { LucideIcon } from 'lucide-react';

interface TabButtonProps {
  id: string;
  isActive: boolean;
  onClick: () => void;
  icon: LucideIcon;
  children: React.ReactNode;
  controls: string;
}

export const TabButton: React.FC<TabButtonProps> = ({
  id,
  isActive,
  onClick,
  icon: Icon,
  children,
  controls
}) => (
  <button
    id={id}
    role="tab"
    aria-selected={isActive}
    aria-controls={controls}
    tabIndex={isActive ? 0 : -1}
    onClick={onClick}
    className={`py-4 px-1 border-b-2 font-medium text-sm flex items-center focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 ${
      isActive
        ? 'border-blue-500 text-blue-600'
        : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
    }`}
  >
    <Icon className="w-4 h-4 mr-2" aria-hidden="true" />
    {children}
  </button>
);