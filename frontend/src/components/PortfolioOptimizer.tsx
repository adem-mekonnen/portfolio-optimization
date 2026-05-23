import { useCallback, useState } from 'react';
import axios from 'axios';
import {
  PieChart, Pie, Cell, ResponsiveContainer,
  ScatterChart, Scatter, XAxis, YAxis, CartesianGrid,
  Tooltip as RTooltip, ZAxis,
} from 'recharts';
import {
  ChevronDown, RotateCcw, Clock, Settings2,
  AlertTriangle, TrendingUp, TrendingDown, Minus,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import BASE_URL from '@/api';
import { usePortfolioStore } from '@/hooks/usePortfolioStore';

const COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#f43f5e', '#8b5cf6'];

const REBALANCE = [
  { value: 'daily',     label: 'Daily'     },
  { value: 'weekly',    label: 'Weekly'    },
  { value: 'monthly',   label: 'Monthly'   },
  { value: 'quarterly', label: 'Quarterly' },
] as const;
type Freq = typeof REBALANCE[number]['value'];

interface Props {
  initialTickers?: string[];
  onBacktestData?: (data: any) => void;
}

function timeAgo(iso: string) {
  const s = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 60)    return 'just now';
  if (s < 3600)  return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return new Date(iso).toLocaleDateString();
}

// ── Portfolio math ────────────────────────────────────────────────────────────
// Both functions implement standard Modern Portfolio Theory formulas.
// Weights are passed as fractions (0–1), not percentages.

/**
 * Weighted portfolio return:  w^T μ
 * where w = weight vector, μ = vector of annualised mean returns.
 */
function portfolioReturn(
  weights: Record<string, number>,   // fractions, sum ≈ 1
  meanReturns: Record<string, number>,
): number {
  return Object.keys(weights).reduce(
    (sum, t) => sum + (weights[t] ?? 0) * (meanReturns[t] ?? 0),
    0,
  );
}

/**
 * Portfolio volatility:  √(w^T Σ w)
 * where Σ = annualised covariance matrix.
 */
function portfolioVolatility(
  weights: Record<string, number>,   // fractions, sum ≈ 1
  covMatrix: Record<string, Record<string, number>>,
): number {
  const tickers = Object.keys(weights);
  let variance = 0;
  for (const i of tickers) {
    for (const j of tickers) {
      variance += (weights[i] ?? 0) * (weights[j] ?? 0) * (covMatrix[i]?.[j] ?? 0);
    }
  }
  return Math.sqrt(Math.max(0, variance)); // clamp to avoid √(−ε) from float rounding
}


function Panel({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <div
      className={cn('rounded-lg p-4', className)}
      style={{ background: 'var(--surface-2)', border: '1px solid var(--border)' }}
    >
      {children}
    </div>
  );
}

// ── Metric comparison row ─────────────────────────────────────────────────────
function MetricRow({ label, user, ai, higherIsBetter = true }: {
  label: string; user: string; ai: string; higherIsBetter?: boolean;
}) {
  const uv = parseFloat(user), av = parseFloat(ai);
  const better = higherIsBetter ? av > uv : av < uv;
  const Icon   = better ? TrendingUp : av === uv ? Minus : TrendingDown;
  return (
    <tr style={{ borderBottom: '1px solid var(--border)' }} className="last:border-0">
      <td className="py-2.5 text-sm text-[var(--text-2)]">{label}</td>
      <td className="py-2.5 text-sm text-[var(--text-2)] font-mono">{user}</td>
      <td className="py-2.5">
        <div className="flex items-center gap-1">
          <Icon size={12} className={better ? 'text-gain' : 'text-loss'} />
          <span className={cn('text-sm font-semibold font-mono', better ? 'text-gain' : 'text-white')}>
            {ai}
          </span>
        </div>
      </td>
    </tr>
  );
}

export default function PortfolioOptimizer({ initialTickers = ['TSLA', 'SPY', 'BND'], onBacktestData }: Props) {
  const tickers = initialTickers;
  const { weights, setWeights, optResult, setOptResult, backtestResult, setBacktestResult, savedAt, clearAll } =
    usePortfolioStore(tickers);

  const [loading,  setLoading]  = useState(false);
  const [error,    setError]    = useState<string | null>(null);
  const [commBps,  setCommBps]  = useState(0.1);
  const [slipBps,  setSlipBps]  = useState(0.05);
  const [freq,     setFreq]     = useState<Freq>('monthly');
  const [showCost, setShowCost] = useState(false);

  // App.tsx reads backtestResult directly from usePortfolioStore,
  // so no restore callback needed here. Removing this prevents the
  // Portfolio page from accidentally triggering parent side-effects on mount.

  const handleWeight = useCallback((ticker: string, val: number) => {
    const v = Math.min(100, Math.max(0, val));
    setWeights(prev => {
      const rest = tickers.filter(t => t !== ticker);
      if (!rest.length) return { [ticker]: 100 };
      const step = (100 - v) / rest.length;
      const next = { ...prev, [ticker]: v };
      rest.forEach(t => { next[t] = step; });
      return next;
    });
  }, [tickers, setWeights]);

  const run = async () => {
    setLoading(true); setError(null);
    try {
      const opt = await axios.post(`${BASE_URL}/optimize`, { tickers });
      setOptResult(opt.data);
      if (onBacktestData) {
        const bt = await axios.post(`${BASE_URL}/backtest`, {
          tickers, weights,
          initial_investment: 10000,
          commission_pct: commBps / 10000,
          slippage_pct:   slipBps / 10000,
          rebalance_freq: freq,
        });
        setBacktestResult(bt.data);
        onBacktestData(bt.data);
      }
    } catch (e: any) {
      setError(e?.response?.data?.detail ?? e.message ?? 'Unknown error');
    } finally {
      setLoading(false);
    }
  };

  const reset = () => {
    clearAll(); setOptResult(null); setBacktestResult(null);
    if (onBacktestData) onBacktestData(null); setError(null);
  };

  const pieData    = tickers.map((t, i) => ({ name: t, value: weights[t], color: COLORS[i] }));
  const weightsSum = Math.round(tickers.reduce((s, t) => s + weights[t], 0));

  const userReturn = optResult
    ? portfolioReturn(
        Object.fromEntries(tickers.map(t => [t, (weights[t] ?? 0) / 100])),
        optResult.mean_returns,
      )
    : 0;
  const userVol = optResult
    ? portfolioVolatility(
        Object.fromEntries(tickers.map(t => [t, (weights[t] ?? 0) / 100])),
        optResult.cov_matrix,
      )
    : 0;
  const userSharpe = userVol > 0 ? (userReturn - 0.02) / userVol : 0;

  return (
    <div
      className="rounded-lg overflow-hidden"
      style={{ background: 'var(--surface-1)', border: '1px solid var(--border)' }}
    >
      {/* Header */}
      <div
        className="px-5 py-3.5 flex items-center justify-between"
        style={{ borderBottom: '1px solid var(--border)' }}
      >
        <div>
          <p className="text-md font-semibold text-white">Portfolio Optimizer</p>
          <p className="text-xs text-[var(--text-3)] mt-0.5">
            Max Sharpe Ratio · Efficient Frontier · Backtest
          </p>
        </div>
        <div className="flex items-center gap-2">
          {savedAt && (
            <span className="flex items-center gap-1 text-xs text-[var(--text-3)]">
              <Clock size={10} />
              {timeAgo(savedAt)}
            </span>
          )}
          {(optResult || savedAt) && (
            <button
              onClick={reset}
              className="flex items-center gap-1 text-xs text-[var(--text-3)] hover:text-loss transition-colors"
            >
              <RotateCcw size={11} />
              Reset
            </button>
          )}
        </div>
      </div>

      <div className="p-5">
        {/* Error */}
        {error && (
          <div
            className="flex items-center gap-2.5 text-sm text-loss rounded-lg px-4 py-3 mb-5"
            style={{ background: 'rgba(244,63,94,0.08)', border: '1px solid rgba(244,63,94,0.2)' }}
          >
            <AlertTriangle size={14} className="shrink-0" />
            {error}
          </div>
        )}

        <div className="grid grid-cols-1 xl:grid-cols-2 gap-5">

          {/* ── Left ──────────────────────────────────────────────────── */}
          <div className="space-y-4">

            {/* Weight sliders */}
            <Panel>
              <p className="text-xs font-medium text-[var(--text-3)] mb-4 uppercase tracking-wider">
                Allocation
              </p>
              <div className="space-y-4">
                {tickers.map((t, i) => (
                  <div key={t}>
                    <div className="flex items-center justify-between mb-1.5">
                      <div className="flex items-center gap-2">
                        <span className="w-2 h-2 rounded-full shrink-0" style={{ background: COLORS[i] }} />
                        <span className="text-sm font-medium text-white">{t}</span>
                      </div>
                      <span className="text-sm font-semibold font-mono text-info">
                        {Math.round(weights[t])}%
                      </span>
                    </div>
                    <input
                      type="range" min="0" max="100" value={weights[t]}
                      onChange={e => handleWeight(t, Number(e.target.value))}
                      style={{ '--range-pct': `${weights[t]}%` } as React.CSSProperties}
                    />
                  </div>
                ))}
              </div>

              {/* Sum */}
              <div
                className={cn(
                  'flex items-center justify-between text-xs px-3 py-2 rounded mt-4',
                  weightsSum === 100
                    ? 'text-gain'
                    : 'text-warn',
                )}
                style={{
                  background: weightsSum === 100 ? 'rgba(16,185,129,0.08)' : 'rgba(245,158,11,0.08)',
                  border: `1px solid ${weightsSum === 100 ? 'rgba(16,185,129,0.2)' : 'rgba(245,158,11,0.2)'}`,
                }}
              >
                <span>Total</span>
                <span className="font-mono font-semibold">{weightsSum}%</span>
              </div>
            </Panel>

            {/* Donut chart */}
            <Panel>
              <div className="relative h-44">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={pieData} dataKey="value" nameKey="name"
                      cx="50%" cy="50%" innerRadius={52} outerRadius={70} paddingAngle={2}
                    >
                      {pieData.map((e, i) => (
                        <Cell key={i} fill={e.color} />
                      ))}
                    </Pie>
                    <RTooltip
                      contentStyle={{
                        background: 'var(--surface-1)',
                        border: '1px solid var(--border-2)',
                        borderRadius: '8px',
                        fontSize: '12px',
                      }}
                      formatter={(v: any) => [`${Number(v).toFixed(1)}%`]}
                    />
                  </PieChart>
                </ResponsiveContainer>
                <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                  <div className="text-center">
                    <p className="text-xs font-medium text-white">Weights</p>
                  </div>
                </div>
              </div>
              {/* Legend */}
              <div className="flex flex-wrap gap-x-4 gap-y-1.5 mt-2">
                {tickers.map((t, i) => (
                  <div key={t} className="flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full" style={{ background: COLORS[i] }} />
                    <span className="text-xs text-[var(--text-3)]">{t} {Math.round(weights[t])}%</span>
                  </div>
                ))}
              </div>
            </Panel>

            {/* Transaction costs */}
            <div
              className="rounded-lg overflow-hidden"
              style={{ border: '1px solid var(--border)' }}
            >
              <button
                onClick={() => setShowCost(p => !p)}
                className="w-full flex items-center justify-between px-4 py-3 text-sm transition-colors hover:bg-white/[0.02]"
                style={{ background: 'var(--surface-2)' }}
              >
                <span className="flex items-center gap-2 text-[var(--text-2)] font-medium">
                  <Settings2 size={13} className="text-[var(--text-3)]" />
                  Transaction Costs
                </span>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-[var(--text-3)]">
                    {commBps}+{slipBps} bps · {freq}
                  </span>
                  <ChevronDown
                    size={13}
                    className={cn('text-[var(--text-3)] transition-transform', showCost && 'rotate-180')}
                  />
                </div>
              </button>

              {showCost && (
                <div
                  className="px-4 pb-4 pt-3 space-y-4"
                  style={{ borderTop: '1px solid var(--border)', background: 'var(--surface-2)' }}
                >
                  {[
                    { label: 'Commission (bps/side)', val: commBps, set: setCommBps, max: 50 },
                    { label: 'Slippage (bps/side)',   val: slipBps, set: setSlipBps, max: 50 },
                  ].map(({ label, val, set, max }) => (
                    <div key={label}>
                      <div className="flex justify-between text-xs text-[var(--text-3)] mb-1.5">
                        <span>{label}</span>
                        <span className="font-mono text-[var(--text-2)]">{val} bps</span>
                      </div>
                      <input type="range" min="0" max={max} step="1" value={val}
                        onChange={e => set(Number(e.target.value))}
                        style={{ '--range-pct': `${(val / max) * 100}%` } as React.CSSProperties}
                      />
                    </div>
                  ))}

                  <div>
                    <p className="text-xs text-[var(--text-3)] mb-2">Rebalance Frequency</p>
                    <div className="grid grid-cols-4 gap-1">
                      {REBALANCE.map(o => (
                        <button
                          key={o.value}
                          onClick={() => setFreq(o.value)}
                          className={cn(
                            'py-1.5 rounded text-xs font-medium transition-colors',
                            freq === o.value
                              ? 'bg-info/15 text-info'
                              : 'text-[var(--text-3)] hover:text-[var(--text-2)]',
                          )}
                          style={{
                            border: freq === o.value
                              ? '1px solid rgba(59,130,246,0.3)'
                              : '1px solid var(--border)',
                          }}
                        >
                          {o.label}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Run button */}
            <button
              onClick={run}
              disabled={loading}
              className="w-full py-2.5 rounded-lg text-sm font-semibold text-white transition-opacity disabled:opacity-50"
              style={{ background: 'var(--blue)' }}
            >
              {loading ? (
                <span className="flex items-center justify-center gap-2">
                  <span className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  Optimizing…
                </span>
              ) : (
                'Run Optimization & Backtest'
              )}
            </button>
          </div>

          {/* ── Right ─────────────────────────────────────────────────── */}
          <div className="space-y-4">
            {optResult ? (
              <>
                {/* Efficient Frontier */}
                <Panel>
                  <p className="text-xs font-medium text-[var(--text-3)] mb-3 uppercase tracking-wider">
                    Efficient Frontier
                  </p>
                  <div className="h-52">
                    <ResponsiveContainer width="100%" height="100%">
                      <ScatterChart margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
                        <CartesianGrid strokeDasharray="2 6" stroke="rgba(255,255,255,0.04)" />
                        <XAxis type="number" dataKey="volatility" name="Risk"
                          stroke="transparent"
                          tick={{ fill: '#475569', fontSize: 10 }}
                          tickFormatter={(v: number) => `${(v * 100).toFixed(1)}%`}
                          domain={['auto', 'auto']}
                        />
                        <YAxis type="number" dataKey="return" name="Return"
                          stroke="transparent"
                          tick={{ fill: '#475569', fontSize: 10 }}
                          tickFormatter={(v: number) => `${(v * 100).toFixed(1)}%`}
                          domain={['auto', 'auto']}
                          width={40}
                        />
                        <ZAxis range={[30, 30]} />
                        <RTooltip
                          cursor={{ strokeDasharray: '3 3' }}
                          contentStyle={{
                            background: 'var(--surface-1)',
                            border: '1px solid var(--border-2)',
                            borderRadius: '8px',
                            fontSize: '11px',
                          }}
                          formatter={(v: any, n: any) => [`${(Number(v) * 100).toFixed(2)}%`, n]}
                        />
                        <Scatter name="EF" data={optResult.ef_points} fill="#3b82f6" line shape="circle" />
                        <Scatter
                          name="Max Sharpe"
                          data={[{ volatility: optResult.volatility, return: optResult.expected_return }]}
                          fill="#10b981"
                          shape="star"
                        />
                      </ScatterChart>
                    </ResponsiveContainer>
                  </div>
                </Panel>

                {/* Metrics */}
                <Panel>
                  <div className="flex items-center justify-between mb-3">
                    <p className="text-xs font-medium text-[var(--text-3)] uppercase tracking-wider">
                      Comparison
                    </p>
                    <span className="text-2xs text-gain font-semibold">★ AI Optimal</span>
                  </div>
                  <table className="w-full">
                    <thead>
                      <tr style={{ borderBottom: '1px solid var(--border)' }}>
                        {['Metric', 'Your Mix', 'AI Optimal'].map(h => (
                          <th key={h} className="pb-2 text-left text-2xs uppercase tracking-wider text-[var(--text-3)] font-medium">
                            {h}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      <MetricRow
                        label="Exp. Return"
                        user={`${(userReturn * 100).toFixed(2)}%`}
                        ai={`${(optResult.expected_return * 100).toFixed(2)}%`}
                        higherIsBetter
                      />
                      <MetricRow
                        label="Volatility"
                        user={`${(userVol * 100).toFixed(2)}%`}
                        ai={`${(optResult.volatility * 100).toFixed(2)}%`}
                        higherIsBetter={false}
                      />
                      <MetricRow
                        label="Sharpe"
                        user={userSharpe.toFixed(2)}
                        ai={optResult.sharpe_ratio.toFixed(2)}
                        higherIsBetter
                      />
                    </tbody>
                  </table>
                </Panel>

                {/* AI weights */}
                <Panel>
                  <p className="text-xs font-medium text-[var(--text-3)] mb-3 uppercase tracking-wider">
                    Recommended Weights
                  </p>
                  <div className="space-y-3">
                    {tickers.map((t, i) => {
                      const w = (optResult.weights[t] ?? 0) * 100;
                      return (
                        <div key={t} className="flex items-center gap-3">
                          <span className="w-2 h-2 rounded-full shrink-0" style={{ background: COLORS[i] }} />
                          <span className="text-sm text-white w-10 shrink-0">{t}</span>
                          <div
                            className="flex-1 h-1.5 rounded-full overflow-hidden"
                            style={{ background: 'var(--surface-3)' }}
                          >
                            <div
                              className="h-full rounded-full transition-all duration-700"
                              style={{ width: `${w}%`, background: COLORS[i] }}
                            />
                          </div>
                          <span className="text-sm font-mono text-white w-12 text-right shrink-0">
                            {w.toFixed(1)}%
                          </span>
                        </div>
                      );
                    })}
                  </div>
                </Panel>
              </>
            ) : (
              <div
                className="flex flex-col items-center justify-center min-h-[380px] rounded-lg text-center"
                style={{ border: '1px dashed var(--border)' }}
              >
                <p className="text-sm font-medium text-white mb-1">Ready to optimize</p>
                <p className="text-xs text-[var(--text-3)] max-w-[220px] leading-relaxed">
                  Set your weights and click Run to compute the optimal portfolio.
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
