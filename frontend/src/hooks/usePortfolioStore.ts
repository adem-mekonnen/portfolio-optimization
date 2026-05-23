import { useCallback } from 'react';
import { useLocalStorage } from './useLocalStorage';

// ── Types ─────────────────────────────────────────────────────────────────────

export interface OptimizeResult {
  weights: Record<string, number>;
  expected_return: number;
  volatility: number;
  sharpe_ratio: number;
  ef_points: { return: number; volatility: number }[];
  /** Annualised mean return per asset — used to compute user portfolio return (w^T μ) */
  mean_returns: Record<string, number>;
  /** Annualised covariance matrix — used to compute user portfolio volatility (√(w^T Σ w)) */
  cov_matrix: Record<string, Record<string, number>>;
}

export interface BacktestDataPoint {
  date: string;
  strategy: number;
  benchmark: number;
}

export interface BacktestResult {
  data: BacktestDataPoint[];
  gross_return: number;
  total_return: number;
  cost_drag: number;
  total_costs_paid: number;
  alpha: number;
  beta: number;
  max_drawdown: number;
  rebalance_count: number;
  avg_turnover: number;
  benchmark_label: string;
}

interface PortfolioState {
  /** User-adjusted weight sliders (values 0–100, sum ≈ 100) */
  weights: Record<string, number>;
  /** Last successful optimization response from /optimize */
  optResult: OptimizeResult | null;
  /** Last successful backtest response from /backtest */
  backtestResult: BacktestResult | null;
  /** ISO timestamp of the last time the user ran the optimizer */
  savedAt: string | null;
}

// ── Storage key ───────────────────────────────────────────────────────────────
const STORAGE_KEY = 'gmf_portfolio_state';

// ── Default weights (equal-weight across the 3 default tickers) ───────────────
function defaultWeights(tickers: string[]): Record<string, number> {
  const even = 100 / tickers.length;
  return Object.fromEntries(tickers.map(t => [t, even]));
}

// ── Hook ──────────────────────────────────────────────────────────────────────

/**
 * Centralised portfolio persistence hook.
 *
 * All state is stored in a single localStorage key (`gmf_portfolio_state`)
 * so it survives page refreshes.  The hook exposes granular setters so
 * components don't need to know about the storage shape.
 */
export function usePortfolioStore(tickers: string[]) {
  const initial: PortfolioState = {
    weights:        defaultWeights(tickers),
    optResult:      null,
    backtestResult: null,
    savedAt:        null,
  };

  const [state, setState, clearState] = useLocalStorage<PortfolioState>(
    STORAGE_KEY,
    initial,
  );

  // ── Ensure every ticker has a weight entry (handles new tickers added later)
  const weights = tickers.reduce<Record<string, number>>((acc, t) => {
    acc[t] = state.weights[t] ?? 100 / tickers.length;
    return acc;
  }, {});

  // ── Setters ───────────────────────────────────────────────────────────────

  const setWeights = useCallback(
    (updater: Record<string, number> | ((prev: Record<string, number>) => Record<string, number>)) => {
      setState(prev => ({
        ...prev,
        weights: typeof updater === 'function' ? updater(prev.weights) : updater,
      }));
    },
    [setState],
  );

  const setOptResult = useCallback(
    (result: OptimizeResult | null) => {
      setState(prev => ({ ...prev, optResult: result }));
    },
    [setState],
  );

  const setBacktestResult = useCallback(
    (result: BacktestResult | null) => {
      setState(prev => ({
        ...prev,
        backtestResult: result,
        savedAt: result ? new Date().toISOString() : prev.savedAt,
      }));
    },
    [setState],
  );

  /** Wipe all persisted state and reset to defaults. */
  const clearAll = useCallback(() => {
    clearState();
  }, [clearState]);

  return {
    weights,
    setWeights,
    optResult:      state.optResult,
    setOptResult,
    backtestResult: state.backtestResult,
    setBacktestResult,
    savedAt:        state.savedAt,
    clearAll,
  };
}
