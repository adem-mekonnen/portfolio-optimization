import { useCallback, useRef, useState } from 'react';

// ── Types ─────────────────────────────────────────────────────────────────────

export type ToastVariant = 'success' | 'error' | 'warning';

export interface Toast {
  id: number;
  message: string;
  variant: ToastVariant;
}

// ── Hook ──────────────────────────────────────────────────────────────────────

/**
 * Lightweight toast manager.
 *
 * Usage:
 *   const { toasts, toast, dismiss } = useToast();
 *   toast('Prices updated', 'success');          // auto-dismisses after 3 s
 *   toast('TSLA failed to load', 'error', 5000); // custom duration
 *   toast('2 of 3 tickers updated', 'warning');
 *
 * Each toast auto-dismisses after `duration` ms (default 3000).
 * Calling dismiss(id) removes it immediately (e.g. on close button click).
 */
export function useToast() {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const nextId = useRef(0);

  const dismiss = useCallback((id: number) => {
    setToasts(prev => prev.filter(t => t.id !== id));
  }, []);

  const toast = useCallback(
    (message: string, variant: ToastVariant = 'success', duration = 3_000) => {
      const id = nextId.current++;
      // Cap visible toasts at 3 — oldest is dropped when the queue is full
      setToasts(prev => {
        const next = [...prev, { id, message, variant }];
        return next.length > 3 ? next.slice(next.length - 3) : next;
      });
      setTimeout(() => dismiss(id), duration);
    },
    [dismiss],
  );

  return { toasts, toast, dismiss };
}
