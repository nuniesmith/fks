import { describe, it, expect } from 'vitest';
import { renderHook } from '@testing-library/react';
import { useHorizontalScrollIndicators } from '../useHorizontalScrollIndicators';

describe('useHorizontalScrollIndicators', () => {
  it('initializes without crashing', () => {
    const { result } = renderHook(() => useHorizontalScrollIndicators<HTMLDivElement>());
    expect(result.current.indicators).toEqual({ left: false, right: false });
  });
});
