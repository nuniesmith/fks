import { useEffect, useRef, useState } from 'react';

interface IndicatorState { left: boolean; right: boolean; }

interface Options { persistKey?: string; }

export function useHorizontalScrollIndicators<T extends HTMLElement>(opts: Options = {}) {
  const { persistKey = 'nav-scroll-x' } = opts;
  const containerRef = useRef<T | null>(null);
  const [indicators, setIndicators] = useState<IndicatorState>({ left: false, right: false });

  useEffect(() => {
    const el = containerRef.current; if (!el) return;
    // Restore scroll position
    const stored = sessionStorage.getItem(persistKey);
    if (stored) {
      const v = parseInt(stored, 10); if (!Number.isNaN(v)) el.scrollLeft = v;
    }
    const handleScroll = () => {
      const { scrollLeft, scrollWidth, clientWidth } = el;
      setIndicators({ left: scrollLeft > 4, right: scrollLeft + clientWidth < scrollWidth - 4 });
      sessionStorage.setItem(persistKey, String(scrollLeft));
    };
    handleScroll();
    el.addEventListener('scroll', handleScroll, { passive: true });
    window.addEventListener('resize', handleScroll);
    return () => { el.removeEventListener('scroll', handleScroll); window.removeEventListener('resize', handleScroll); };
  }, [persistKey]);

  return { containerRef, indicators } as const;
}
