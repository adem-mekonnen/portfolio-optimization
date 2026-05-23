import { renderHook, act } from '@testing-library/react';
import { usePortfolioStore, type OptimizeResult, type BacktestResult } from '@/hooks/usePortfolioStore';

const TICKERS = ['TSLA', 'SPY', 'BND'];

beforeEach(() => localStorage.clear());

// ── Fixtures ──────────────────────────────────────────────────────────────────

const mockOptResult: OptimizeResult = {
  weights:         { TSLA: 0.5, SPY: 0.3, BND: 0.2 },
  expected_return: 0.18,
  volatility:      0.22,
  sharpe_ratio:    0.73,
  ef_points:       [{ return: 0.1, volatility: 0.15 }],
};

const mockBacktestResult: BacktestResult = {
  data:             [{ date: '2025-01-01', strategy: 1.0, benchmark: 1.0 }],
  gross_return:     12.5,
  total_return:     11.8,
  cost_drag:        0.7,
  total_costs_paid: 70,
  alpha:            2.1,
  beta:             0.95,
  max_drawdown:     -8.3,
  rebalance_count:  12,
  avg_turnover:     4.2,
  benchmark_label:  '60% SPY / 40% BND',
};

// ── Tests ─────────────────────────────────────────────────────────────────────

describe('usePortfolioStore', () => {
  it('initialises with equal weights across all tickers', () => {
    const { result } = renderHook(() => usePortfolioStore(TICKERS));
    const even = 100 / TICKERS.length;
    TICKERS.forEach(t => expect(result.current.weights[t]).toBeCloseTo(even));
  });

  it('initialises optResult and backtestResult as null', () => {
    const { result } = renderHook(() => usePortfolioStore(TICKERS));
    expect(result.current.optResult).toBeNull();
    expect(result.current.backtestResult).toBeNull();
    expect(result.current.savedAt).toBeNull();
  });

  it('setWeights updates weights and persists to localStorage', () => {
    const { result } = renderHook(() => usePortfolioStore(TICKERS));
    act(() => result.current.setWeights({ TSLA: 60, SPY: 30, BND: 10 }));
    expect(result.current.weights).toEqual({ TSLA: 60, SPY: 30, BND: 10 });
    const stored = JSON.parse(localStorage.getItem('gmf_portfolio_state')!);
    expect(stored.weights).toEqual({ TSLA: 60, SPY: 30, BND: 10 });
  });

  it('setWeights supports functional updater form', () => {
    const { result } = renderHook(() => usePortfolioStore(TICKERS));
    act(() => result.current.setWeights(prev => ({ ...prev, TSLA: 80 })));
    expect(result.current.weights.TSLA).toBe(80);
  });

  it('setOptResult stores the optimization result', () => {
    const { result } = renderHook(() => usePortfolioStore(TICKERS));
    act(() => result.current.setOptResult(mockOptResult));
    expect(result.current.optResult).toEqual(mockOptResult);
  });

  it('setBacktestResult stores the result and sets savedAt', () => {
    const before = Date.now();
    const { result } = renderHook(() => usePortfolioStore(TICKERS));
    act(() => result.current.setBacktestResult(mockBacktestResult));
    expect(result.current.backtestResult).toEqual(mockBacktestResult);
    expect(result.current.savedAt).not.toBeNull();
    expect(new Date(result.current.savedAt!).getTime()).toBeGreaterThanOrEqual(before);
  });

  it('setBacktestResult(null) does not overwrite savedAt', () => {
    const { result } = renderHook(() => usePortfolioStore(TICKERS));
    act(() => result.current.setBacktestResult(mockBacktestResult));
    const savedAt = result.current.savedAt;
    act(() => result.current.setBacktestResult(null));
    expect(result.current.backtestResult).toBeNull();
    expect(result.current.savedAt).toBe(savedAt);   // preserved
  });

  it('clearAll resets all state and removes the localStorage key', () => {
    const { result } = renderHook(() => usePortfolioStore(TICKERS));
    act(() => result.current.setOptResult(mockOptResult));
    act(() => result.current.setBacktestResult(mockBacktestResult));
    act(() => result.current.clearAll());
    expect(result.current.optResult).toBeNull();
    expect(result.current.backtestResult).toBeNull();
    // After clearAll the useEffect re-writes the reset state, so the key
    // exists again but holds the default (null results, equal weights).
    const stored = JSON.parse(localStorage.getItem('gmf_portfolio_state')!);
    expect(stored.optResult).toBeNull();
    expect(stored.backtestResult).toBeNull();
  });

  it('survives a page reload — restores state from localStorage', () => {
    // First render: set some state
    const { result: r1 } = renderHook(() => usePortfolioStore(TICKERS));
    act(() => r1.current.setOptResult(mockOptResult));
    act(() => r1.current.setWeights({ TSLA: 70, SPY: 20, BND: 10 }));

    // Second render (simulates reload): should read from localStorage
    const { result: r2 } = renderHook(() => usePortfolioStore(TICKERS));
    expect(r2.current.optResult).toEqual(mockOptResult);
    expect(r2.current.weights).toMatchObject({ TSLA: 70, SPY: 20, BND: 10 });
  });

  it('fills in missing ticker weights with equal share', () => {
    // Store state for 2 tickers, then render with 3
    localStorage.setItem(
      'gmf_portfolio_state',
      JSON.stringify({ weights: { TSLA: 50, SPY: 50 }, optResult: null, backtestResult: null, savedAt: null }),
    );
    const { result } = renderHook(() => usePortfolioStore(['TSLA', 'SPY', 'BND']));
    // BND was missing — should get the default equal share
    expect(result.current.weights.BND).toBeCloseTo(100 / 3);
  });
});
