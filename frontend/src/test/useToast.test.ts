import { renderHook, act, waitFor } from '@testing-library/react';
import { useToast } from '@/hooks/useToast';

beforeEach(() => vi.useFakeTimers());
afterEach(() => vi.useRealTimers());

describe('useToast', () => {
  it('starts with no toasts', () => {
    const { result } = renderHook(() => useToast());
    expect(result.current.toasts).toHaveLength(0);
  });

  it('adds a toast when toast() is called', () => {
    const { result } = renderHook(() => useToast());
    act(() => result.current.toast('Hello', 'success'));
    expect(result.current.toasts).toHaveLength(1);
    expect(result.current.toasts[0]).toMatchObject({ message: 'Hello', variant: 'success' });
  });

  it('assigns unique ids to each toast', () => {
    const { result } = renderHook(() => useToast());
    act(() => {
      result.current.toast('A', 'success');
      result.current.toast('B', 'error');
    });
    const ids = result.current.toasts.map(t => t.id);
    expect(new Set(ids).size).toBe(2);
  });

  it('supports all three variants', () => {
    const { result } = renderHook(() => useToast());
    act(() => {
      result.current.toast('ok',   'success');
      result.current.toast('fail', 'error');
      result.current.toast('warn', 'warning');
    });
    const variants = result.current.toasts.map(t => t.variant);
    expect(variants).toEqual(['success', 'error', 'warning']);
  });

  it('auto-dismisses after the default 3 s', async () => {
    const { result } = renderHook(() => useToast());
    act(() => result.current.toast('bye', 'success'));
    expect(result.current.toasts).toHaveLength(1);

    await act(async () => { vi.advanceTimersByTime(3_000); });
    expect(result.current.toasts).toHaveLength(0);
  });

  it('auto-dismisses after a custom duration', async () => {
    const { result } = renderHook(() => useToast());
    act(() => result.current.toast('bye', 'error', 1_000));

    await act(async () => { vi.advanceTimersByTime(999); });
    expect(result.current.toasts).toHaveLength(1); // still visible

    await act(async () => { vi.advanceTimersByTime(1); });
    expect(result.current.toasts).toHaveLength(0);
  });

  it('dismiss() removes a specific toast immediately', () => {
    const { result } = renderHook(() => useToast());
    act(() => {
      result.current.toast('A', 'success');
      result.current.toast('B', 'error');
    });
    const idToRemove = result.current.toasts[0].id;
    act(() => result.current.dismiss(idToRemove));
    expect(result.current.toasts).toHaveLength(1);
    expect(result.current.toasts[0].message).toBe('B');
  });

  it('dismiss() is a no-op for an unknown id', () => {
    const { result } = renderHook(() => useToast());
    act(() => result.current.toast('A', 'success'));
    act(() => result.current.dismiss(9999));
    expect(result.current.toasts).toHaveLength(1);
  });

  it('multiple toasts stack and each auto-dismisses independently', async () => {
    const { result } = renderHook(() => useToast());
    act(() => {
      result.current.toast('short', 'success', 1_000);
      result.current.toast('long',  'warning', 5_000);
    });
    expect(result.current.toasts).toHaveLength(2);

    await act(async () => { vi.advanceTimersByTime(1_000); });
    expect(result.current.toasts).toHaveLength(1);
    expect(result.current.toasts[0].message).toBe('long');

    await act(async () => { vi.advanceTimersByTime(4_000); });
    expect(result.current.toasts).toHaveLength(0);
  });
});
