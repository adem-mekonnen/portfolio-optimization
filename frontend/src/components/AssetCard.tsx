import { ArrowUpRight, ArrowDownRight, AlertTriangle, RefreshCw } from 'lucide-react';
import { cn } from '@/lib/utils';

interface Props {
  ticker:    string;
  price:     number;
  change:    number;
  sentiment: 'Bullish' | 'Bearish';
  isActive?:  boolean;
  isLoading?: boolean;
  hasError?:  boolean;
  onClick?:   () => void;
}

const META: Record<string, { name: string; sector: string; color: string }> = {
  TSLA: { name: 'Tesla, Inc.',       sector: 'Cons. Disc.',   color: '#1D4ED8' },
  SPY:  { name: 'SPDR S&P 500 ETF',  sector: 'Broad Market', color: '#16A34A' },
  BND:  { name: 'Vanguard Bond ETF',  sector: 'Fixed Income', color: '#D97706' },
};

/* Deterministic sparkline — seeded from ticker, stable across renders */
function Sparkline({ ticker, up }: { ticker: string; up: boolean }) {
  const seed = ticker.split('').reduce((a, c) => a + c.charCodeAt(0), 0);
  const pts: number[] = [];
  let v = 50;
  for (let i = 0; i < 20; i++) {
    const r = ((seed * (i + 1) * 2654435761) >>> 0) % 100;
    v = Math.max(10, Math.min(90, v + (r % 14) - 7));
    pts.push(v);
  }
  if (up)  { pts[18] = Math.max(pts[17], pts[18]); pts[19] = Math.max(pts[18], pts[19]); }
  else     { pts[18] = Math.min(pts[17], pts[18]); pts[19] = Math.min(pts[18], pts[19]); }

  const w = 64, h = 28;
  const min = Math.min(...pts), max = Math.max(...pts);
  const range = max - min || 1;
  const toX = (i: number) => (i / (pts.length - 1)) * w;
  const toY = (v: number) => h - ((v - min) / range) * (h - 4) - 2;

  const d = pts.map((v, i) => `${i === 0 ? 'M' : 'L'}${toX(i).toFixed(1)},${toY(v).toFixed(1)}`).join(' ');
  const fillD = `${d} L${w},${h} L0,${h} Z`;
  const stroke = up ? '#16A34A' : '#DC2626';
  const fill   = up ? 'rgba(22,163,74,0.08)' : 'rgba(220,38,38,0.08)';

  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} className="sparkline" aria-hidden="true">
      <path d={fillD} fill={fill} />
      <path d={d} fill="none" stroke={stroke} strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export default function AssetCard({
  ticker, price, change, sentiment,
  isActive = false, isLoading = false, hasError = false, onClick,
}: Props) {
  const meta = META[ticker] ?? { name: ticker, sector: '', color: '#1D4ED8' };
  const up   = change >= 0;

  /* ── Loading skeleton ── */
  if (isLoading) {
    return (
      <div
        className="p-4 rounded-lg"
        style={{
          background: '#FFFFFF',
          border:     '1px solid #E2E8F0',
          boxShadow:  '0 1px 2px rgba(15,23,42,0.06)',
        }}
      >
        <div className="flex items-start justify-between mb-3">
          <div className="space-y-2">
            <div className="skeleton h-2.5 w-8 rounded" />
            <div className="skeleton h-2 w-20 rounded" />
          </div>
          <div className="skeleton h-4 w-12 rounded" />
        </div>
        <div className="skeleton h-5 w-24 rounded mb-2" />
        <div className="skeleton h-2.5 w-14 rounded" />
      </div>
    );
  }

  /* ── Error state ── */
  if (hasError) {
    return (
      <div
        onClick={onClick}
        role={onClick ? 'button' : undefined}
        tabIndex={onClick ? 0 : undefined}
        onKeyDown={onClick ? e => e.key === 'Enter' && onClick() : undefined}
        className="p-4 rounded-lg cursor-pointer group"
        style={{
          background: '#FFF5F5',
          border:     '1px solid #FECACA',
          boxShadow:  '0 1px 2px rgba(15,23,42,0.04)',
        }}
      >
        <div className="flex items-center justify-between mb-1">
          <div className="flex items-center gap-1.5">
            <AlertTriangle size={12} style={{ color: '#DC2626' }} className="shrink-0" />
            <span className="text-[13px] font-semibold" style={{ color: '#0F172A' }}>{ticker}</span>
          </div>
          <RefreshCw size={11} style={{ color: '#94A3B8' }} className="group-hover:text-[#475569] transition-colors" />
        </div>
        <p className="text-[11px]" style={{ color: '#94A3B8' }}>Failed to load · click to retry</p>
      </div>
    );
  }

  /* ── Normal state ── */
  return (
    <div
      onClick={onClick}
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : undefined}
      onKeyDown={onClick ? e => e.key === 'Enter' && onClick() : undefined}
      className={cn('p-4 rounded-lg card-hover', onClick ? 'cursor-pointer' : '')}
      style={{
        background: '#FFFFFF',
        border: isActive ? '1px solid #93C5FD' : '1px solid #E2E8F0',
        boxShadow: isActive
          ? '0 0 0 3px rgba(29,78,216,0.08), 0 1px 3px rgba(15,23,42,0.08)'
          : '0 1px 2px rgba(15,23,42,0.06)',
      }}
    >
      {/* Row 1 — ticker + sentiment */}
      <div className="flex items-start justify-between mb-3">
        <div>
          <div className="flex items-center gap-1.5 mb-0.5">
            <span className="w-2 h-2 rounded-full shrink-0" style={{ background: meta.color }} />
            <span className="text-[13px] font-bold tabular" style={{ color: '#0F172A' }}>
              {ticker}
            </span>
          </div>
          <p className="text-[11px] pl-3.5" style={{ color: '#94A3B8' }}>{meta.name}</p>
        </div>

        {/* Sentiment badge */}
        <span
          className="text-[10px] font-semibold px-2 py-0.5 rounded-full"
          style={
            sentiment === 'Bullish'
              ? { color: '#16A34A', background: '#F0FDF4', border: '1px solid #BBF7D0' }
              : { color: '#DC2626', background: '#FFF5F5', border: '1px solid #FECACA' }
          }
        >
          {sentiment}
        </span>
      </div>

      {/* Row 2 — price + sparkline */}
      <div className="flex items-end justify-between">
        <div>
          <p
            className="text-[20px] font-bold tabular leading-none mb-1"
            style={{ color: '#0F172A', fontFamily: '"JetBrains Mono", monospace' }}
          >
            ${price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </p>
          <div
            className="flex items-center gap-0.5 text-[11px] font-semibold"
            style={{ color: up ? '#16A34A' : '#DC2626' }}
          >
            {up ? <ArrowUpRight size={12} strokeWidth={2.5} /> : <ArrowDownRight size={12} strokeWidth={2.5} />}
            <span className="tabular">{up ? '+' : ''}{change.toFixed(2)}%</span>
            <span className="ml-1.5 font-normal" style={{ color: '#94A3B8' }}>{meta.sector}</span>
          </div>
        </div>
        <div className="shrink-0 mb-0.5">
          <Sparkline ticker={ticker} up={up} />
        </div>
      </div>
    </div>
  );
}
