// hooks/useKeyboardNavigation.ts
import { useEffect } from 'react';

interface UseKeyboardNavigationProps {
  activeIndex: number;
  setActiveIndex: (index: number) => void;
  itemCount: number;
  containerId: string;
}

export const useKeyboardNavigation = ({
  activeIndex,
  setActiveIndex,
  itemCount,
  containerId
}: UseKeyboardNavigationProps) => {
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      const container = document.getElementById(containerId);
      if (!container || !container.contains(event.target as Node)) return;

      switch (event.key) {
        case 'ArrowLeft':
        case 'ArrowUp':
          event.preventDefault();
          setActiveIndex(activeIndex > 0 ? activeIndex - 1 : itemCount - 1);
          break;
        case 'ArrowRight':
        case 'ArrowDown':
          event.preventDefault();
          setActiveIndex(activeIndex < itemCount - 1 ? activeIndex + 1 : 0);
          break;
        case 'Home':
          event.preventDefault();
          setActiveIndex(0);
          break;
        case 'End':
          event.preventDefault();
          setActiveIndex(itemCount - 1);
          break;
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [activeIndex, setActiveIndex, itemCount, containerId]);
};