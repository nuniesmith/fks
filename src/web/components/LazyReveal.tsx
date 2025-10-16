import React, { useEffect, useRef, useState } from 'react';

interface LazyRevealProps {
  children: React.ReactNode;
  rootMargin?: string;
  threshold?: number | number[];
  className?: string;
  placeholderHeight?: number; // reserve space to reduce layout shift
  skeleton?: React.ReactNode; // optional skeleton while waiting
  performanceLabel?: string; // add a performance mark when revealed
}

// Simple intersection-based reveal wrapper
const LazyReveal: React.FC<LazyRevealProps> = ({
  children,
  rootMargin = '120px',
  threshold = 0.1,
  className = '',
  placeholderHeight = 40,
  skeleton,
  performanceLabel
}) => {
  const ref = useRef<HTMLDivElement | null>(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (!ref.current || visible) return;
    const observer = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          setVisible(true);
          if (performanceLabel && performance?.mark) {
            try { performance.mark(`lazy-reveal:${performanceLabel}`); } catch {}
          }
          observer.disconnect();
        }
      });
    }, { root: null, rootMargin, threshold });
    observer.observe(ref.current);
    return () => observer.disconnect();
  }, [rootMargin, threshold, visible]);

  return (
    <div ref={ref} className={`lazy-reveal ${visible ? 'lazy-visible' : ''} ${className}`} style={{ minHeight: visible ? undefined : placeholderHeight }}>
      {visible ? children : (skeleton || null)}
    </div>
  );
};

export default LazyReveal;