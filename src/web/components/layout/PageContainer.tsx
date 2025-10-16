import React from 'react';

interface PageContainerProps {
  children: React.ReactNode;
  className?: string;
  maxWidth?: '5xl' | '6xl' | '7xl' | 'full';
  noMinHeight?: boolean; // allow embedded usages
  padded?: boolean; // can disable default p-6
}

/**
 * Standard outer wrapper for top-level pages.
 * Consolidates repeated `min-h-screen p-6 max-w-* mx-auto` patterns.
 */
const PageContainer: React.FC<PageContainerProps> = ({
  children,
  className = '',
  maxWidth = '7xl',
  noMinHeight = false,
  padded = true,
}) => {
  const widthClass = maxWidth === 'full' ? '' : `max-w-${maxWidth}`;
  return (
    <div className={`${!noMinHeight ? 'min-h-screen' : ''} ${padded ? 'p-6' : ''} ${className}`.trim()}>
      <div className={`${widthClass} mx-auto`.trim()}>
        {children}
      </div>
    </div>
  );
};

export default PageContainer;
