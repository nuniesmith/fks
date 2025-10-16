import React from 'react';

interface SectionHeaderProps {
  icon?: React.ReactNode;
  title: string;
  className?: string;
  headingLevel?: 2 | 3 | 4 | 5 | 6; // semantic level for a11y
  trailing?: React.ReactNode;
  dense?: boolean; // reduces bottom margin
  titleClassName?: string; // override default title styling (for light surfaces)
}

/**
 * Consistent section header (icon + title) used across dashboard cards and pages.
 * Collapses duplicate flex & spacing markup and ensures visual rhythm consistency.
 */
const SectionHeader: React.FC<SectionHeaderProps> = ({ icon, title, className = '', headingLevel = 3, trailing, dense = false, titleClassName }) => {
  const base = <span className={titleClassName || 'text-xl font-semibold text-white leading-tight'}>{title}</span>;
  const semantic = (() => {
    switch (headingLevel) {
      case 2: return <h2 className="m-0 p-0">{base}</h2>;
      case 3: return <h3 className="m-0 p-0">{base}</h3>;
      case 4: return <h4 className="m-0 p-0">{base}</h4>;
      case 5: return <h5 className="m-0 p-0">{base}</h5>;
      case 6: return <h6 className="m-0 p-0">{base}</h6>;
      default: return <h3 className="m-0 p-0">{base}</h3>;
    }
  })();
  return (
    <div className={`flex items-center justify-between ${dense ? 'mb-3' : 'mb-4'} ${className}`}> 
      <div className="flex items-center gap-3">
        {icon && <span className="flex items-center justify-center">{icon}</span>}
        {semantic}
      </div>
      {trailing && <div className="flex items-center gap-2">{trailing}</div>}
    </div>
  );
};

export default SectionHeader;
