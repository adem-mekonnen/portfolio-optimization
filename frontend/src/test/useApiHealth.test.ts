import { renderHook, act, waitFor } from '@testing-library/react';
import axios from 'axios';
import MockAdapter from 'axios-mock-adapter';
import { useApiHealth } from '@/hooks/useApiHealth';

const mock = new MockAdapter(axios);

afterEach(() => {
  mock.reset();
  vi.useRealTimers();
});

describe('useApiHealth', () => {
  it('starts in "checking" state', () => {
    mock.onGet(/\/data\/status/).reply(() => new Promise(() => {})); // never resolves
    const { result } = renderHook(() => useApiHealth());
    expect(result.current).toBe('checking');
  });

  it('transitions to "connected" when the probe succeeds', async () => {
    mock.onGet(/\/data\/status/).reply(200, {});
    const { result } = renderHook(() => useApiHealth());
    await waitFor(() => expect(result.current).toBe('connected'));
  });

  it('transitions to "disconnected" on a network error', async () => {
    mock.onGet(/\/data\/status/).networkError();
    const { result } = renderHook(() => useApiHealth());
    await waitFor(() => expect(result.current).toBe('disconnected'));
  });

  it('transitions to "disconnected" on a non-2xx response', async () => {
    mock.onGet(/\/data\/status/).reply(503);
    const { result } = renderHook(() => useApiHealth());
    await waitFor(() => expect(result.current).toBe('disconnected'));
  });

  it('re-probes after the interval and updates status', async () => {
    // First probe fails, second succeeds.
    // Use a real short interval (no fake timers) to avoid axios/fake-timer conflicts.
    mock.onGet(/\/data\/status/).replyOnce(503).onGet(/\/data\/status/).reply(200, {});

    const { result } = renderHook(() => useApiHealth(100));

    // Wait for the first probe to settle as disconnected
    await waitFor(() => expect(result.current).toBe('disconnected'));

    // Wait for the interval to fire and the second probe to succeed
    await waitFor(() => expect(result.current).toBe('connected'), { timeout: 2_000 });
  }, 5_000);

  it('cleans up the interval on unmount', () => {
    vi.useFakeTimers();
    const clearSpy = vi.spyOn(globalThis, 'clearInterval');
    mock.onGet(/\/data\/status/).reply(200, {});

    const { unmount } = renderHook(() => useApiHealth(5_000));
    unmount();
    expect(clearSpy).toHaveBeenCalled();
  });
});
