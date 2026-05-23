import { LayoutDashboard, TrendingUp, Briefcase, BarChart2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { type ApiStatus } from '@/hooks/useApiHealth';

export type View = 'overview' | 'forecast' | 'portfolio' | 'backtest';

const NAV = [
  { id: 'overview'  as View, icon: LayoutDashboard, label: 'Overview',   key: '1' },
  { id: 'forecast'  as View, icon: TrendingUp,      label: 'Forecast',   key: '2' },
  { id: 'portfolio' as View, icon: Briefcase,       label: 'Portfolio',  key: '3' },
  { id: 'backtest'  as View, icon: BarChart2,       label: 'Backtest',   key: '4' },
];

const STATUS: Record<ApiStatus, { dot: string; label: string; labelColor: string }> = {
  checking:     { dot: 'bg-[#94A3B8]', label: 'Connecting',   labelColor: '#94A3B8' },
  connected:    { dot: 'bg-[#16A34A]', label: 'Connected',    labelColor: '#16A34A' },
  disconnected: { dot: 'bg-[#DC2626]', label: 'Disconnected', labelColor: '#DC2626' },
};

interface Props {
  activeView: View;
  onNavigate: (v: View) => void;
  apiStatus:  ApiStatus;
}

export default function Sidebar({ activeView, onNavigate, apiStatus }: Props) {
  const st = STATUS[apiStatus];

  return (
    <aside
      className="hidden md:flex w-[200px] h-screen flex-col shrink-0 select-none"
      style={{
        background:  '#FFFFFF',
        borderRight: '1px solid #E2E8F0',
      }}
    >
      {/* ── Logo ── */}
      <div
        className="flex items-center gap-2 px-4 h-11 shrink-0"
        style={{ borderBottom: '1px solid #E2E8F0' }}
      >
        <div
          className="w-6 h-6 rounded-md flex items-center justify-center shrink-0"
          style={{ background: '#1D4ED8' }}
        >
          <TrendingUp size={12} color="#FFFFFF" strokeWidth={2.5} />
        </div>
        <span className="text-[14px] font-bold tracking-tight" style={{ color: '#0F172A' }}>
          GMF
        </span>
        <span className="text-[11px] font-medium" style={{ color: '#94A3B8' }}>
          Investments
        </span>
      </div>

      {/* ── Navigation ── */}
      <nav className="flex-1 px-2 pt-3 pb-2 overflow-y-auto">
        <p
          className="px-2 mb-1.5 text-[10px] font-semibold uppercase tracking-widest"
          style={{ color: '#94A3B8' }}
        >
          Workspace
        </p>

        {NAV.map(({ id, icon: Icon, label, key }) => {
          const active = activeView === id;
          return (
            <button
              key={id}
              onClick={() => onNavigate(id)}
              title={`${label}  [${key}]`}
              className={cn(
                'relative w-full flex items-center gap-2.5 px-2.5 py-2 rounded-md text-left mb-0.5',
                'transition-colors duration-100 group',
                'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#1D4ED8]/30',
              )}
              style={
                active
                  ? { background: '#EFF6FF', color: '#1D4ED8' }
                  : { background: 'transparent', color: '#475569' }
              }
              onMouseEnter={e => { if (!active) e.currentTarget.style.background = '#F8FAFC'; }}
              onMouseLeave={e => { if (!active) e.currentTarget.style.background = 'transparent'; }}
            >
              {active && <span className="nav-active-bar" />}

              <Icon
                size={14}
                strokeWidth={active ? 2.25 : 1.75}
                style={{ color: active ? '#1D4ED8' : '#94A3B8', flexShrink: 0 }}
              />

              <span
                className="text-[13px] font-medium flex-1"
                style={{ color: active ? '#1D4ED8' : '#475569' }}
              >
                {label}
              </span>

              {!active && (
                <kbd
                  className="opacity-0 group-hover:opacity-100 transition-opacity text-[10px] font-mono px-1.5 py-0.5 rounded"
                  style={{
                    color:      '#94A3B8',
                    background: '#F1F5F9',
                    border:     '1px solid #E2E8F0',
                  }}
                >
                  {key}
                </kbd>
              )}
            </button>
          );
        })}
      </nav>

      {/* ── Footer ── */}
      <div
        className="px-3 py-3 space-y-2"
        style={{ borderTop: '1px solid #E2E8F0' }}
      >
        <div className="flex items-center gap-2">
          <span className="relative flex shrink-0">
            {apiStatus === 'connected' && (
              <span
                className={cn('animate-ping absolute inline-flex h-full w-full rounded-full opacity-40', st.dot)}
              />
            )}
            <span className={cn('status-dot', st.dot)} />
          </span>
          <span className="text-[11px] font-medium" style={{ color: st.labelColor }}>
            {st.label}
          </span>
        </div>
        <p className="text-[10px] leading-relaxed" style={{ color: '#CBD5E1' }}>
          Educational use only. Not financial advice.
        </p>
      </div>
    </aside>
  );
}

/* ── Mobile bottom nav ── */
export function BottomNav({ activeView, onNavigate }: Omit<Props, 'apiStatus'>) {
  return (
    <nav
      className="md:hidden flex items-stretch shrink-0"
      style={{
        background:    '#FFFFFF',
        borderTop:     '1px solid #E2E8F0',
        paddingBottom: 'env(safe-area-inset-bottom)',
      }}
      aria-label="Main navigation"
    >
      {NAV.map(({ id, icon: Icon, label }) => {
        const active = activeView === id;
        return (
          <button
            key={id}
            onClick={() => onNavigate(id)}
            aria-current={active ? 'page' : undefined}
            className={cn(
              'flex-1 flex flex-col items-center justify-center gap-1 py-2.5 relative',
              'transition-colors duration-100',
              'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[#1D4ED8]/30',
            )}
            style={{ color: active ? '#1D4ED8' : '#94A3B8' }}
          >
            {active && (
              <span
                className="absolute top-0 left-1/2 -translate-x-1/2 w-8 h-[2px] rounded-b"
                style={{ background: '#1D4ED8' }}
              />
            )}
            <Icon size={18} aria-hidden="true" />
            <span className="text-[10px] font-medium leading-none">{label}</span>
          </button>
        );
      })}
    </nav>
  );
}
