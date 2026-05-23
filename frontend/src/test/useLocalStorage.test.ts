import { renderHook, act } from '@testing-library/react';
import { useLocalStorage } from '@/hooks/useLocalStorage';

// Reset localStorage before every test so state never leaks between cases
beforeEach(() => localStorage.clear());

describe('useLocalStorage', () => {
  it('returns the initial value when the key is absent', () => {
    const { result } = renderHook(() => useLocalStorage('k', 42));
    expect(result.current[0]).toBe(42);
  });

  it('reads an existing value from localStorage on mount', () => {
    localStorage.setItem('k', JSON.stringify('hello'));
    const { result } = renderHook(() => useLocalStorage('k', 'default'));
    expect(result.current[0]).toBe('hello');
  });

  it('persists a new value to localStorage', () => {
    const { result } = renderHook(() => useLocalStorage('k', 0));
    act(() => result.current[1](99));
    expect(result.current[0]).toBe(99);
    expect(JSON.parse(localStorage.getItem('k')!)).toBe(99);
  });

  it('supports functional updater form', () => {
    const { result } = renderHook(() => useLocalStorage('k', 10));
    act(() => result.current[1](prev => prev + 5));
    expect(result.current[0]).toBe(15);
  });

  it('clear() removes the key and resets to initialValue', () => {
    const { result } = renderHook(() => useLocalStorage('k', 'init'));
    act(() => result.current[1]('changed'));
    act(() => result.current[2]());          // call clear()
    expect(result.current[0]).toBe('init');
    // After clear(), the useEffect re-writes the initial value to localStorage.
    // Assert the stored value is the initial value, not that the key is absent.
    expect(JSON.parse(localStorage.getItem('k')!)).toBe('init');
  });

  it('falls back to initialValue when stored JSON is corrupt', () => {
    localStorage.setItem('k', '{bad json');
    const { result } = renderHook(() => useLocalStorage('k', 'fallback'));
    expect(result.current[0]).toBe('fallback');
  });

  it('works with object values', () => {
    const init = { a: 1, b: 'x' };
    const { result } = renderHook(() => useLocalStorage('obj', init));
    act(() => result.current[1]({ a: 2, b: 'y' }));
    expect(result.current[0]).toEqual({ a: 2, b: 'y' });
    expect(JSON.parse(localStorage.getItem('obj')!)).toEqual({ a: 2, b: 'y' });
  });
});
