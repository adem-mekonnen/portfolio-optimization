import { useState, useEffect, useCallback } from 'react';

/**
 * A typed localStorage hook that mirrors React's useState API.
 *
 * - Reads the initial value from localStorage on mount (falls back to
 *   `initialValue` if the key is absent or the stored JSON is corrupt).
 * - Writes to localStorage on every state change.
 * - Exposes a `clear` helper that removes the key and resets to `initialValue`.
 *
 * @param key          localStorage key
 * @param initialValue value used when nothing is stored yet
 */
export function useLocalStorage<T>(
  key: string,
  initialValue: T,
): [T, (value: T | ((prev: T) => T)) => void, () => void] {
  // Lazy initialiser — only runs once on mount
  const [storedValue, setStoredValue] = useState<T>(() => {
    try {
      const item = window.localStorage.getItem(key);
      return item !== null ? (JSON.parse(item) as T) : initialValue;
    } catch {
      return initialValue;
    }
  });

  // Keep localStorage in sync whenever the value changes
  useEffect(() => {
    try {
      window.localStorage.setItem(key, JSON.stringify(storedValue));
    } catch {
      // Quota exceeded or private-browsing restriction — fail silently
    }
  }, [key, storedValue]);

  const clear = useCallback(() => {
    try {
      window.localStorage.removeItem(key);
    } catch {
      // ignore
    }
    setStoredValue(initialValue);
  }, [key, initialValue]);

  return [storedValue, setStoredValue, clear];
}
