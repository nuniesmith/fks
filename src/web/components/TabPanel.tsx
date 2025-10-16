// components/TabPanel.tsx - Accessible tab panel
import React from 'react';

interface TabPanelProps {
  children: React.ReactNode;
  isActive: boolean;
  id: string;
  ariaLabelledBy: string;
}

export const TabPanel: React.FC<TabPanelProps> = ({
  children,
  isActive,
  id,
  ariaLabelledBy
}) => (
  <div
    id={id}
    role="tabpanel"
    aria-labelledby={ariaLabelledBy}
    hidden={!isActive}
    tabIndex={0}
    className="focus:outline-none"
  >
    {isActive && children}
  </div>
);