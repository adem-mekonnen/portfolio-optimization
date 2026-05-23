import { useEffect, useRef, useState } from 'react';
import axios from 'axios';
import Sidebar, { BottomNav, type View } from './components/Sidebar';
import { useApiHealth } from '@/hooks/useApiHealth';
import { useToast } from '@/hooks/useToast';
import ToastContainer from './components/ToastContainer';
import TickerManager from './components/TickerManager';
import AssetCard from './components/AssetCard';
import ChartSection from './components/ChartSection';
import PortfolioOptimizer from './components/PortfolioOptimizer';
import BacktestingResult from './components/BacktestingResult';
import {
  Activity, AlertTriangle, RefreshCw, TrendingUp,
  ArrowRight, BarChart2, Briefcase, Plus,
} from 'lucide-react';
import BASE_URL from '@/api';
import { useLocalStorage } from '@/hooks/useLocalStorage';
import { usePortfolioStore } from '@/hooks/usePortfolioStore';
import { cn } from '@/lib/utils';

export interface AssetInfo {
  ticker:         string;
  price:          number;
  change_percent: number;
  sentiment:      'Bullish' | 'Bearish';
}

const DEFAULT_TICKERS = ['TSLA', 'SPY', 'BND'];

const PAGE_META: Record<View, { title: string; sub: string }> = {
  overview:  { title: 'Overview',          sub: 'Market snapshot & watchlist'         },
  forecast:  { title: 'Price Forecast',    sub: 'LSTM 30-day predictions'             },
  portfolio: { title: 'Portfolio',         sub: 'Optimizer & allocation'              },
  backtest:  { title: 'Backtest',          sub: 'Strategy simulation results'         },
};

export default function App() {
  const [activeView,     setActiveView]     = useLocalStorage<View>('gmf_view', 'overview');
  const [selectedTicker, setSelectedTicker] = useLocalStorage<string>('gmf_ticker', 'TSLA');
  const [tickers,        setTickers]        = useLocalStorage<string[]>('gmf_tickers', DEFAULT_TICKERS);
  const { backtestResult, setBacktestResult } = usePortfolioStore(tickers);
  const apiStatus = useApiHealth();
  const { toasts, toast, dismiss } = useToast();

  const [forecastData,    setForecastData]    = useState([]);
  const [loadingForecast, setLoadingForecast] = useState(true);
  const [forecastError,   setForecastError]   = useState<string | null>(null);
  const [assetInfos,      setAssetInfos]      = useState<Record<string, AssetInfo>>({});
  const [assetErrors,     setAssetErrors]     = useState<Record<string, string>>({});
  const [refreshing,      setRefreshing]      = useState(false);
  const [now,             setNow]             = useState(new Date());
  const [showTickerMgr,   setShowTickerMgr]   = useState(false);
  const mainRef = useRef<HTMLDivElement>(null);

  /* Keyboard shortcuts 1–4 */
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;
      const map: Record<string, View> = { '1': 'overview', '2': 'forecast', '3': 'portfolio', '4': 'backtest' };
      if (map[e.key]) setActiveView(map[e.key]);
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [setActiveView]);

  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 60_000);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    mainRef.current?.scrollTo({ top: 0, behavior: 'instant' });
  }, [activeView]);

  const fetchPrices = async (showToast = true) => {
    setRefreshing(true);
    const results = await Promise.allSettled(
      tickers.map(t =>
        axios.get(`${BASE_URL}/asset_info/${t}`)
          .then(r => {
            setAssetInfos(p => ({ ...p, [t]: r.data }));
            setAssetErrors(p => { const n = { ...p }; delete n[t]; return n; });
            return t;
          })
          .catch(() => {
            setAssetErrors(p => ({ ...p, [t]: 'error' }));
            throw t;
          }),
      ),
    );
    setRefreshing(false);
    if (!showToast) return;
    const failed  = results.filter(r => r.status === 'rejected').length;
    const success = results.length - failed;
    if (failed === 0) {
      toast(`${success} ticker${success !== 1 ? 's' : ''} updated`, 'success');
    } else if (success === 0) {
      toast('Failed to load market data — check your connection', 'error', 5_000);
    } else {
      const failedTickers = results
        .filter((r): r is PromiseRejectedResult => r.status === 'rejected')
        .map(r => r.reason as string).join(', ');
      toast(`${success} updated · ${failedTickers} failed`, 'warning', 5_000);
    }
  };

  useEffect(() => { fetchPrices(false); }, []);

  useEffect(() => {
    setLoadingForecast(true);
    setForecastError(null);
    axios.get(`${BASE_URL}/forecast/${selectedTicker}`)
      .then(r => { setForecastData(r.data.forecast); setLoadingForecast(false); })
      .catch(e => {
        setForecastError(e?.response?.data?.detail ?? e.message ?? 'Unknown error');
        setLoadingForecast(false);
      });
  }, [selectedTicker]);

  const navigate = (v: View) => setActiveView(v);
  const meta = PAGE_META[activeView];

  return (
    <div className="flex w-full h-dvh overflow-hidden" style={{ background: 'var(--bg)' }}>
      <ToastContainer toasts={toasts} onDismiss={dismiss} />
      <Sidebar activeView={activeView} onNavigate={navigate} apiStatus={apiStatus} />

      <div className="flex-1 flex flex-col overflow-hidden min-w-0">

        {/* ── Topbar ── */}
        <header
          className="shrink-0 h-11 flex items-center justify-between px-4 md:px-5"
          style={{ borderBottom: '1px solid var(--border)', background: 'var(--surface-1)' }}
        >
          {/* Left — page title */}
          <div className="flex items-center gap-2.5 min-w-0">
            <div className="md:hidden w-5 h-5 rounded flex items-center justify-center shrink-0"
              style={{ background: 'var(--blue)' }}>
              <TrendingUp size={10} color="#fff" strokeWidth={2.5} />
            </div>
            <div className="min-w-0">
              <h1 className="text-[13px] font-semibold leading-none truncate" style={{ color: 'var(--text-1)' }}>
                {meta.title}
              </h1>
              <p className="text-[11px] leading-none mt-0.5 hidden sm:block" style={{ color: 'var(--text-3)' }}>
                {meta.sub}
              </p>
            </div>
          </div>

          {/* Right — controls */}
          <div className="flex items-center gap-2 shrink-0">
            {/* Date/time */}
            <span className="text-[11px] hidden md:block tabular" style={{ color: 'var(--text-3)' }}>
              {now.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' })}
              {' · '}
              {now.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })}
            </span>

            <div className="w-px h-3" style={{ background: 'var(--border-2)' }} />

            {/* Refresh */}
            <button
              onClick={() => fetchPrices(true)}
              disabled={refreshing}
              title={`Refresh · last at ${now.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })}`}
              className="flex items-center gap-1 text-[11px] transition-colors disabled:opacity-40 focus-visible:outline-none"
              style={{ color: 'var(--text-3)' }}
              onMouseEnter={e => (e.currentTarget.style.color = 'var(--text-2)')}
              onMouseLeave={e => (e.currentTarget.style.color = 'var(--text-3)')}
            >
              <RefreshCw size={11} className={cn(refreshing && 'animate-spin')} />
              <span className="hidden sm:inline">Refresh</span>
            </button>

            {/* Live indicator */}
            <div
              className="flex items-center gap-1.5 px-2 py-0.5 rounded text-[11px] font-medium"
              style={{
                color:      'var(--gain)',
                background: 'rgba(34,197,94,0.08)',
                border:     '1px solid rgba(34,197,94,0.18)',
              }}
            >
              <span className="relative flex h-1.5 w-1.5 shrink-0">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full opacity-50"
                  style={{ background: 'var(--gain)' }} />
                <span className="relative inline-flex rounded-full h-1.5 w-1.5"
                  style={{ background: 'var(--gain)' }} />
              </span>
              Live
            </div>
          </div>
        </header>

        {/* ── Content ── */}
        <main ref={mainRef} className="flex-1 overflow-y-auto">
          <div className="px-4 md:px-5 py-4 max-w-[1280px] mx-auto">

            {/* ══ OVERVIEW ══════════════════════════════════════════════ */}
            {activeView === 'overview' && (
              <div className="animate-fade-up space-y-4">

                {/* Loading bar — only while ALL are fetching */}
                {tickers.length > 0 && tickers.every(t => !assetInfos[t] && !assetErrors[t]) && (
                  <div className="flex items-center gap-2 text-[11px]" style={{ color: 'var(--text-3)' }}>
                    <span className="w-3 h-3 border border-current border-t-transparent rounded-full animate-spin shrink-0" />
                    Loading market data…
                  </div>
                )}

                {/* ── Watchlist header row ── */}
                <div className="flex items-center justify-between">
                  <div>
                    <h2 className="text-[13px] font-semibold" style={{ color: 'var(--text-1)' }}>
                      Watchlist
                    </h2>
                    <p className="text-[11px]" style={{ color: 'var(--text-3)' }}>
                      {tickers.length} asset{tickers.length !== 1 ? 's' : ''} tracked
                    </p>
                  </div>
                  <button
                    onClick={() => setShowTickerMgr(v => !v)}
                    className="flex items-center gap-1 text-[11px] font-medium px-2.5 py-1 rounded transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[var(--info)]/40"
                    style={{
                      color:      showTickerMgr ? 'var(--text-1)' : 'var(--text-2)',
                      background: showTickerMgr ? 'var(--surface-3)' : 'var(--surface-2)',
                      border:     '1px solid var(--border-2)',
                    }}
                  >
                    <Plus size={11} />
                    Manage
                  </button>
                </div>

                {/* Ticker manager — collapsible */}
                {showTickerMgr && (
                  <div
                    className="rounded-md p-3 animate-fade-up"
                    style={{ background: 'var(--surface-2)', border: '1px solid var(--border)' }}
                  >
                    <TickerManager
                      tickers={tickers}
                      onChange={next => {
                        setTickers(next);
                        if (!next.includes(selectedTicker) && next.length > 0) {
                          setSelectedTicker(next[0]);
                        }
                      }}
                    />
                  </div>
                )}

                {/* Asset cards — or empty state */}
                {tickers.length === 0 ? (
                  <EmptyState
                    icon={<Activity size={16} />}
                    title="No assets tracked"
                    desc="Click Manage to add tickers to your watchlist."
                    action={{ label: 'Add tickers', onClick: () => setShowTickerMgr(true) }}
                  />
                ) : (
                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2.5">
                    {tickers.map(t => (
                      <AssetCard
                        key={t}
                        ticker={t}
                        price={assetInfos[t]?.price ?? 0}
                        change={assetInfos[t]?.change_percent ?? 0}
                        sentiment={assetInfos[t]?.sentiment ?? 'Bullish'}
                        isActive={selectedTicker === t}
                        isLoading={!assetInfos[t] && !assetErrors[t]}
                        hasError={!!assetErrors[t]}
                        onClick={() => { setSelectedTicker(t); navigate('forecast'); }}
                      />
                    ))}
                  </div>
                )}

                {/* ── Quick actions ── */}
                <div>
                  <h2 className="text-[13px] font-semibold mb-2" style={{ color: 'var(--text-1)' }}>
                    Quick Actions
                  </h2>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                    <QuickAction
                      icon={<TrendingUp size={14} />}
                      title="Price Forecast"
                      desc="30-day LSTM predictions with 95% confidence intervals"
                      onClick={() => navigate('forecast')}
                    />
                    <QuickAction
                      icon={<Briefcase size={14} />}
                      title="Portfolio Optimizer"
                      desc="Max Sharpe allocation with transaction cost simulation"
                      onClick={() => navigate('portfolio')}
                    />
                    <QuickAction
                      icon={<BarChart2 size={14} />}
                      title="Strategy Backtest"
                      desc={backtestResult ? 'Results available — view performance analysis' : 'Run optimizer first to generate backtest data'}
                      onClick={() => navigate(backtestResult ? 'backtest' : 'portfolio')}
                      badge={backtestResult ? 'Ready' : undefined}
                    />
                  </div>
                </div>
              </div>
            )}

            {/* ══ FORECAST ══════════════════════════════════════════════ */}
            {activeView === 'forecast' && (
              <div className="space-y-3 animate-fade-up">

                {/* Ticker selector row */}
                <div className="flex items-center gap-1.5 flex-wrap">
                  {tickers.map(t => (
                    <button
                      key={t}
                      onClick={() => setSelectedTicker(t)}
                      className={cn(
                        'px-3 py-1 rounded text-[12px] font-medium transition-colors',
                        'focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[var(--info)]/40',
                        selectedTicker === t
                          ? 'text-[var(--info)]'
                          : 'text-[var(--text-3)] hover:text-[var(--text-2)]',
                      )}
                      style={selectedTicker === t
                        ? { background: 'rgba(59,130,246,0.1)', border: '1px solid rgba(59,130,246,0.25)' }
                        : { background: 'transparent', border: '1px solid transparent' }
                      }
                    >
                      {t}
                    </button>
                  ))}
                </div>

                {/* Selected asset summary — inline, not a full card */}
                {assetInfos[selectedTicker] && (
                  <div
                    className="flex items-center gap-4 px-3.5 py-2.5 rounded-md"
                    style={{ background: 'var(--surface-2)', border: '1px solid var(--border)' }}
                  >
                    <div>
                      <span className="text-[13px] font-semibold" style={{ color: 'var(--text-1)' }}>
                        {selectedTicker}
                      </span>
                      <span className="text-[11px] ml-2" style={{ color: 'var(--text-3)' }}>
                        {assetInfos[selectedTicker]?.sentiment}
                      </span>
                    </div>
                    <span
                      className="text-[16px] font-semibold tabular"
                      style={{ color: 'var(--text-1)', fontFamily: '"JetBrains Mono", monospace' }}
                    >
                      ${assetInfos[selectedTicker]?.price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                    </span>
                    <span
                      className="text-[12px] font-medium tabular"
                      style={{
                        color: (assetInfos[selectedTicker]?.change_percent ?? 0) >= 0
                          ? 'var(--gain)' : 'var(--loss)',
                      }}
                    >
                      {(assetInfos[selectedTicker]?.change_percent ?? 0) >= 0 ? '+' : ''}
                      {assetInfos[selectedTicker]?.change_percent.toFixed(2)}%
                    </span>
                  </div>
                )}

                {loadingForecast ? (
                  <Placeholder label={`Loading forecast for ${selectedTicker}…`} />
                ) : forecastError ? (
                  <ErrorPlaceholder message={forecastError} onRetry={() => setSelectedTicker(selectedTicker)} />
                ) : (
                  <ChartSection data={forecastData} selectedTicker={selectedTicker} />
                )}
              </div>
            )}

            {/* ══ PORTFOLIO ═════════════════════════════════════════════ */}
            {activeView === 'portfolio' && (
              <div className="animate-fade-up">
                <PortfolioOptimizer
                  initialTickers={tickers}
                  onBacktestData={d => { setBacktestResult(d); }}
                />
                {backtestResult && (
                  <div
                    className="mt-3 flex items-center justify-between px-3.5 py-2.5 rounded-md"
                    style={{
                      background: 'rgba(34,197,94,0.06)',
                      border:     '1px solid rgba(34,197,94,0.18)',
                    }}
                  >
                    <p className="text-[12px] font-medium" style={{ color: 'var(--gain)' }}>
                      Backtest complete — results ready
                    </p>
                    <button
                      onClick={() => navigate('backtest')}
                      className="flex items-center gap-1 text-[11px] font-semibold px-2.5 py-1 rounded transition-opacity hover:opacity-80"
                      style={{ background: 'var(--gain)', color: '#fff' }}
                    >
                      View Results
                      <ArrowRight size={11} />
                    </button>
                  </div>
                )}
              </div>
            )}

            {/* ══ BACKTEST ══════════════════════════════════════════════ */}
            {activeView === 'backtest' && (
              <div className="animate-fade-up">
                {backtestResult ? (
                  <BacktestingResult data={backtestResult} />
                ) : (
                  <EmptyState
                    icon={<BarChart2 size={16} />}
                    title="No backtest data"
                    desc="Run the Portfolio Optimizer to generate simulation results."
                    action={{ label: 'Go to Portfolio', onClick: () => navigate('portfolio') }}
                  />
                )}
              </div>
            )}

            <div className="h-6" />
          </div>
        </main>

        <BottomNav activeView={activeView} onNavigate={navigate} />
      </div>
    </div>
  );
}

/* ── Shared micro-components ─────────────────────────────────────────────── */

function QuickAction({
  icon, title, desc, onClick, badge,
}: {
  icon: React.ReactNode;
  title: string;
  desc: string;
  onClick: () => void;
  badge?: string;
}) {
  return (
    <button
      onClick={onClick}
      className="text-left p-3 rounded-md card-hover group focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[var(--info)]/40"
      style={{ background: 'var(--surface-1)', border: '1px solid var(--border)' }}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-start gap-2.5 min-w-0">
          <span className="mt-0.5 shrink-0" style={{ color: 'var(--text-3)' }}>{icon}</span>
          <div className="min-w-0">
            <div className="flex items-center gap-2 mb-0.5">
              <p className="text-[13px] font-semibold" style={{ color: 'var(--text-1)' }}>{title}</p>
              {badge && (
                <span
                  className="text-[10px] font-semibold px-1.5 py-0.5 rounded"
                  style={{
                    color:      'var(--gain)',
                    background: 'rgba(34,197,94,0.1)',
                    border:     '1px solid rgba(34,197,94,0.2)',
                  }}
                >
                  {badge}
                </span>
              )}
            </div>
            <p className="text-[11px] leading-relaxed" style={{ color: 'var(--text-3)' }}>{desc}</p>
          </div>
        </div>
        <ArrowRight
          size={13}
          className="shrink-0 mt-0.5 transition-transform group-hover:translate-x-0.5"
          style={{ color: 'var(--text-3)' }}
        />
      </div>
    </button>
  );
}

function EmptyState({
  icon, title, desc, action,
}: {
  icon: React.ReactNode;
  title: string;
  desc: string;
  action?: { label: string; onClick: () => void };
}) {
  return (
    <div
      className="flex flex-col items-center justify-center min-h-[200px] rounded-md gap-2 text-center py-10"
      style={{ border: '1px dashed var(--border)' }}
    >
      <span style={{ color: 'var(--text-3)' }}>{icon}</span>
      <p className="text-[13px] font-medium" style={{ color: 'var(--text-2)' }}>{title}</p>
      <p className="text-[11px] max-w-[240px] leading-relaxed" style={{ color: 'var(--text-3)' }}>{desc}</p>
      {action && (
        <button
          onClick={action.onClick}
          className="mt-1 text-[11px] font-medium transition-colors focus-visible:outline-none"
          style={{ color: 'var(--info)' }}
          onMouseEnter={e => (e.currentTarget.style.textDecoration = 'underline')}
          onMouseLeave={e => (e.currentTarget.style.textDecoration = 'none')}
        >
          {action.label} →
        </button>
      )}
    </div>
  );
}

function Placeholder({ label, action }: {
  label: string;
  action?: { label: string; onClick: () => void };
}) {
  return (
    <div
      className="flex flex-col items-center justify-center min-h-[280px] rounded-md gap-2 text-center"
      style={{ border: '1px dashed var(--border)' }}
    >
      <Activity size={15} style={{ color: 'var(--text-3)' }} />
      <p className="text-[12px] max-w-xs" style={{ color: 'var(--text-3)' }}>{label}</p>
      {action && (
        <button
          onClick={action.onClick}
          className="text-[11px] mt-1 focus-visible:outline-none"
          style={{ color: 'var(--info)' }}
        >
          {action.label}
        </button>
      )}
    </div>
  );
}

function ErrorPlaceholder({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div
      className="flex flex-col items-center justify-center min-h-[280px] rounded-md gap-2 text-center"
      style={{
        border:     '1px dashed rgba(248,81,73,0.25)',
        background: 'rgba(248,81,73,0.03)',
      }}
    >
      <AlertTriangle size={15} style={{ color: 'var(--loss)' }} />
      <p className="text-[12px] max-w-sm leading-relaxed" style={{ color: 'rgba(248,81,73,0.8)' }}>
        {message}
      </p>
      <button
        onClick={onRetry}
        className="text-[11px] mt-1 underline focus-visible:outline-none"
        style={{ color: 'var(--text-3)' }}
      >
        Try again
      </button>
    </div>
  );
}
