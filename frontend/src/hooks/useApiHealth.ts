import { useEffect, useState } from 'react';
import axios from 'axios';
import BASE_URL from '@/api';

export type ApiStatus = 'checking' | 'connected' | 'disconnected';

/**
 * Polls GET /data/status every `intervalMs` milliseconds and returns the
 * current connectivity state.
 *
 * - 'checking'     — initial state before the first probe completes
 * - 'connected'    — last probe returned HTTP 2xx
 * - 'disconnected' — last probe failed (network error or non-2xx)
 */
export function useApiHealth(intervalMs = 30_000): ApiStatus {
  const [status, setStatus] = useState<ApiStatus>('checking');

  useEffect(() => {
    let cancelled = false;

    const probe = async () => {
      try {
        await axios.get(`${BASE_URL}/data/status`, { timeout: 5_000 });
        if (!cancelled) setStatus('connected');
      } catch {
        if (!cancelled) setStatus('disconnected');
      }
    };

    probe();
    const id = setInterval(probe, intervalMs);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [intervalMs]);

  return status;
}
