import { useState, useMemo } from 'react';
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine,
} from 'recharts';
import {
  TrendingUp, TrendingDown, ShieldAlert, Activity,
  DollarSign, RefreshCw, BarChart2,
} from 'lucide-react';
import { cn } from '@/lib/utils';

interface BtPoint { date: string; strategy: number; benchmark: number; }

interface Props {
  data: {
    data: BtPoint[];
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
  } | null;
}

const INITIAL = 10_000;

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function ChartTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  const s    = payload.find((p: any) => p.dataKey === 'sv');
  const b    = payload.find((p: any) => p.dataKey === 'bv');
  const diff = s && b ? s.value - b.value : null;
  const fmt  = (v: number) =>
    `$${v.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  return (
    <div
      className="px-3 py-2.5 rounded-lg text-xs shadow-xl min-w-[170px]"
      style={{ background: 'var(--surface-1)', border: '1px solid var(--border-2)' }}
    >
      <p className="text-[var(--text-3)] mb-1.5 font-medium">{label}</p>
      {s && <p className="text-gain font-semibold">Strategy <span className="font-mono ml-1">{fmt(s.value)}</span></p>}
      {b && <p className="text-[var(--text-3)]">Benchmark <span className="font-mono ml-1">{fmt(b.value)}</span></p>}
      {diff !== null && (
        <p className={cn('mt-1.5 font-medium', diff >= 0 ? 'text-gain' : 'text-loss')}>
          {diff >= 0 ? '▲ +' : '▼ '}{fmt(diff)}
        </p>
      )}
    </div>
  );
}

interface StatProps {
  icon: React.ReactNode;
  label: string;
  value: string;
  sub?: string;
  tone?: 'gain' | 'loss' | 'neutral' | 'warn';
}

function Stat({ icon, label, value, sub, tone = 'neutral' }: StatProps) {
  const color = { gain: 'text-gain', loss: 'text-loss', neutral: 'text-white', warn: 'text-warn' }[tone];
  const bg    = {
    gain:    { background: 'rgba(16,185,129,0.06)',  border: '1px solid rgba(16,185,129,0.15)' },
    loss:    { background: 'rgba(244,63,94,0.06)',   border: '1px solid rgba(244,63,94,0.15)'  },
    neutral: { background: 'var(--surface-2)',       border: '1px solid var(--border)'         },
    warn:    { background: 'rgba(245,158,11,0.06)',  border: '1px solid rgba(245,158,11,0.15)' },
  }[tone];
  return (
    <div className="rounded-lg p-4 flex flex-col gap-2" style={bg}>
      <div className="flex items-center justify-between">
        <span className="text-2xs uppercase tracking-wider text-[var(--text-3)] font-medium">{label}</span>
        <span className={cn('opacity-50', color)}>{icon}</span>
      </div>
      <p className={cn('text-xl font-semibold font-mono', color)}>{value}</p>
      {sub && <p className="text-xs text-[var(--text-3)]">{sub}</p>}
    </div>
  );
}

export default function BacktestingResult({ data }: Props) {
  const [log, setLog] = useState(false);

  const chartData = useMemo(() => {
    if (!data?.data) return [];
    return data.data.map(d => ({ date: d.date, sv: d.strategy * INITIAL, bv: d.benchmark * INITIAL }));
  }, [data]);

  // Derive actual date range from the data series
  const dateRange = useMemo(() => {
    if (!data?.data?.length) return null;
    const fmt = (s: string) => {
      const d = new Date(s);
      return isNaN(d.getTime()) ? s : d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
    };
    return `${fmt(data.data[0].date)} – ${fmt(data.data[data.data.length - 1].date)}`;
  }, [data]);

  if (!data) return null;

  const hasCosts = data.cost_drag > 0;
  const pos      = data.total_return > 0;
  const alphaPos = data.alpha >= 0;

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
          <p className="text-md font-semibold text-white">Backtest Results</p>
          <p className="text-xs text-[var(--text-3)] mt-0.5">
            {dateRange ? `${dateRange}` : '1-year simulation'} · $10,000 initial investment · Benchmark: {data.benchmark_label}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {hasCosts && (
            <span
              className="text-2xs font-semibold text-warn px-2 py-1 rounded"
              style={{ background: 'rgba(245,158,11,0.1)', border: '1px solid rgba(245,158,11,0.2)' }}
            >
              Cost-adjusted
            </span>
          )}
          {/* Scale toggle */}
          <div
            className="flex items-center gap-2 px-3 py-1.5 rounded-md text-xs"
            style={{ background: 'var(--surface-2)', border: '1px solid var(--border)' }}
          >
            <span className={cn('font-medium', !log ? 'text-white' : 'text-[var(--text-3)]')}>Linear</span>
            <button
              onClick={() => setLog(v => !v)}
              className={cn(
                'relative w-8 h-4 rounded-full transition-colors',
                log ? 'bg-info' : 'bg-[var(--surface-3)]',
              )}
            >
              <span className={cn(
                'absolute top-0.5 w-3 h-3 rounded-full bg-white shadow transition-transform',
                log ? 'translate-x-4' : 'translate-x-0.5',
              )} />
            </button>
            <span className={cn('font-medium', log ? 'text-white' : 'text-[var(--text-3)]')}>Log</span>
          </div>
        </div>
      </div>

      <div className="p-5 space-y-5">

        {/* Cost notice */}
        {hasCosts && (
          <div
            className="flex flex-wrap items-center gap-2 px-4 py-2.5 rounded-lg text-xs"
            style={{ background: 'rgba(245,158,11,0.07)', border: '1px solid rgba(245,158,11,0.18)' }}
          >
            <DollarSign size={13} className="text-warn shrink-0" />
            <span className="text-warn font-medium">
              Costs reduced returns by <strong>{data.cost_drag.toFixed(2)} pp</strong>
              {' '}(${data.total_costs_paid.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })})
            </span>
            <span className="text-[var(--text-3)] ml-auto">
              {data.rebalance_count} rebalances · {data.avg_turnover.toFixed(1)}% avg turnover
            </span>
          </div>
        )}

        {/* Chart */}
        <div className="h-[320px]">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={chartData} margin={{ top: 4, right: 12, left: 4, bottom: 0 }}>
              <defs>
                <linearGradient id="gs" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%"   stopColor="#10b981" stopOpacity={0.25} />
                  <stop offset="100%" stopColor="#10b981" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="gb" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%"   stopColor="#475569" stopOpacity={0.15} />
                  <stop offset="100%" stopColor="#475569" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="2 6" stroke="rgba(255,255,255,0.04)" vertical={false} />
              <XAxis
                dataKey="date"
                stroke="transparent"
                tick={{ fill: '#475569', fontSize: 10 }}
                tickMargin={8}
                minTickGap={32}
              />
              <YAxis
                scale={log ? 'log' : 'linear'}
                domain={log ? ['dataMin', 'dataMax'] : ['auto', 'auto']}
                stroke="transparent"
                tick={{ fill: '#475569', fontSize: 10, fontFamily: 'monospace' }}
                tickFormatter={v => `$${Number(v).toLocaleString()}`}
                width={64}
              />
              <Tooltip content={<ChartTooltip />} />
              <ReferenceLine
                y={INITIAL}
                stroke="rgba(255,255,255,0.1)"
                strokeDasharray="4 4"
                label={{ value: '$10k', fill: '#475569', fontSize: 10, position: 'insideTopLeft' }}
              />
              <Area type="monotone" dataKey="bv" name="Benchmark"
                stroke="#475569" strokeWidth={1.5} fill="url(#gb)" fillOpacity={1} />
              <Area type="monotone" dataKey="sv" name="Strategy (net)"
                stroke="#10b981" strokeWidth={2} fill="url(#gs)" fillOpacity={1} />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        {/* Legend */}
        <div className="flex items-center gap-4 -mt-2">
          <div className="flex items-center gap-1.5">
            <div className="w-4 h-px bg-gain" />
            <span className="text-xs text-[var(--text-3)]">Strategy (net of costs)</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="w-4 h-px bg-[#475569]" />
            <span className="text-xs text-[var(--text-3)]">Benchmark: {data.benchmark_label}</span>
          </div>
        </div>

        {/* Scorecard */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <Stat
            icon={pos ? <TrendingUp size={16} /> : <TrendingDown size={16} />}
            label="Net Return"
            value={`${pos ? '+' : ''}${data.total_return.toFixed(2)}%`}
            sub={hasCosts ? `Gross ${data.gross_return > 0 ? '+' : ''}${data.gross_return.toFixed(2)}%` : undefined}
            tone={pos ? 'gain' : 'loss'}
          />
          <Stat
            icon={<Activity size={16} />}
            label="Ann. Alpha"
            value={`${alphaPos ? '+' : ''}${data.alpha.toFixed(2)}%`}
            sub={`vs ${data.benchmark_label}`}
            tone={alphaPos ? 'gain' : 'loss'}
          />
          <Stat
            icon={<BarChart2 size={16} />}
            label="Beta"
            value={data.beta.toFixed(2)}
            sub={`vs ${data.benchmark_label}`}
          />
          <Stat
            icon={<ShieldAlert size={16} />}
            label="Max Drawdown"
            value={`${data.max_drawdown.toFixed(2)}%`}
            tone="loss"
          />
        </div>

        {/* Cost detail */}
        {hasCosts && (
          <div className="grid grid-cols-3 gap-3">
            <Stat icon={<DollarSign size={14} />} label="Cost Drag"    value={`-${data.cost_drag.toFixed(2)} pp`} tone="warn" />
            <Stat icon={<RefreshCw size={14} />}  label="Rebalances"   value={String(data.rebalance_count)} />
            <Stat icon={<Activity size={14} />}   label="Avg Turnover" value={`${data.avg_turnover.toFixed(1)}%`} />
          </div>
        )}
      </div>
    </div>
  );
}
