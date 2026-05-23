import { useMemo } from 'react';
import {
  ComposedChart, Area, Line,
  XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceDot,
} from 'recharts';

interface ForecastPoint {
  date: string;
  predicted_price: number;
  lower_bound: number;
  upper_bound: number;
}

interface Props {
  data: ForecastPoint[];
  selectedTicker?: string;
}

const fmtDate = (s: string) => {
  const d = new Date(s);
  return isNaN(d.getTime()) ? s : d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
};

const fmtUSD = (v: number) =>
  `$${v.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

const fmtAxis = (v: number) =>
  `$${v >= 1000 ? `${(v / 1000).toFixed(1)}k` : v.toFixed(0)}`;

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function Tooltip_({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  const pred  = payload.find((p: any) => p.dataKey === 'predicted_price');
  const upper = payload.find((p: any) => p.dataKey === 'upper_bound');
  const lower = payload.find((p: any) => p.dataKey === 'lower_bound');
  return (
    <div
      className="px-3 py-2.5 rounded-lg text-xs shadow-xl min-w-[150px]"
      style={{ background: 'var(--surface-1)', border: '1px solid var(--border-2)' }}
    >
      <p className="text-[var(--text-3)] mb-1.5 font-medium">{fmtDate(label)}</p>
      {pred && (
        <p className="text-white font-semibold">
          Forecast <span className="text-info font-mono ml-1">{fmtUSD(pred.value)}</span>
        </p>
      )}
      {upper && lower && (
        <p className="text-[var(--text-3)] mt-1">
          95% CI <span className="font-mono">{fmtUSD(lower.value)} – {fmtUSD(upper.value)}</span>
        </p>
      )}
    </div>
  );
}

export default function ChartSection({ data, selectedTicker = 'TSLA' }: Props) {
  const chartData = useMemo(() =>
    data.map(d => ({ ...d, band_width: d.upper_bound - d.lower_bound })),
  [data]);

  const yDomain = useMemo((): [number, number] | ['auto', 'auto'] => {
    if (!data.length) return ['auto', 'auto'];
    const vals = data.flatMap(d => [d.lower_bound, d.upper_bound, d.predicted_price]);
    const min = Math.min(...vals), max = Math.max(...vals);
    const pad = (max - min) * 0.1;
    return [Math.floor(min - pad), Math.ceil(max + pad)];
  }, [data]);

  // Last forecast point — shown as an inline annotation on the chart
  const lastPoint = data.length > 0 ? data[data.length - 1] : null;

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
          <div className="flex items-baseline gap-2">
            <span className="text-md font-semibold text-white">{selectedTicker}</span>
            <span className="text-sm text-[var(--text-3)]">30-Day Forecast</span>
          </div>
          <p className="text-xs text-[var(--text-3)] mt-0.5">
            LSTM autoregressive model · 95% confidence interval
          </p>
        </div>
        <span
          className="text-2xs font-semibold text-info px-2 py-1 rounded"
          style={{ background: 'rgba(59,130,246,0.1)', border: '1px solid rgba(59,130,246,0.2)' }}
        >
          LSTM
        </span>
      </div>

      {/* Chart */}
      <div className="px-3 pt-5 pb-3">
        <ResponsiveContainer width="100%" height={300}>
          <ComposedChart data={chartData} margin={{ top: 4, right: 12, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id="ci" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%"   stopColor="#3b82f6" stopOpacity={0.1} />
                <stop offset="100%" stopColor="#3b82f6" stopOpacity={0.01} />
              </linearGradient>
            </defs>

            <CartesianGrid
              strokeDasharray="2 6"
              stroke="rgba(255,255,255,0.04)"
              vertical={false}
            />
            <XAxis
              dataKey="date"
              stroke="transparent"
              tick={{ fill: '#475569', fontSize: 10 }}
              tickMargin={8}
              minTickGap={44}
              tickFormatter={fmtDate}
            />
            <YAxis
              domain={yDomain}
              stroke="transparent"
              tick={{ fill: '#475569', fontSize: 10, fontFamily: 'monospace' }}
              tickFormatter={fmtAxis}
              width={48}
            />
            <Tooltip content={<Tooltip_ />} />

            {/* CI band */}
            <Area type="monotone" dataKey="lower_bound" stroke="none" fill="none"
              stackId="ci" legendType="none" dot={false} activeDot={false} />
            <Area type="monotone" dataKey="band_width" stroke="none" fill="url(#ci)"
              stackId="ci" legendType="none" dot={false} activeDot={false} />

            {/* Forecast line */}
            <Line
              type="monotone"
              dataKey="predicted_price"
              stroke="#3b82f6"
              strokeWidth={1.75}
              dot={false}
              legendType="none"
              strokeLinecap="round"
              isAnimationActive
              animationDuration={1000}
              animationEasing="ease-out"
            />

            {/* Last-point annotation — shows final forecast price without hover */}
            {lastPoint && (
              <ReferenceDot
                x={lastPoint.date}
                y={lastPoint.predicted_price}
                r={3}
                fill="#3b82f6"
                stroke="#0b0f19"
                strokeWidth={2}
                label={{
                  value: fmtUSD(lastPoint.predicted_price),
                  position: 'right',
                  fill: '#3b82f6',
                  fontSize: 10,
                  fontFamily: '"JetBrains Mono", monospace',
                  fontWeight: 600,
                }}
              />
            )}
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      {/* Legend */}
      <div className="px-5 pb-4 flex items-center gap-4">
        <div className="flex items-center gap-1.5">
          <div className="w-4 h-px bg-info" />
          <span className="text-xs text-[var(--text-3)]">Forecast</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div
            className="w-3 h-2.5 rounded-sm"
            style={{ background: 'rgba(59,130,246,0.12)', border: '1px solid rgba(59,130,246,0.2)' }}
          />
          <span className="text-xs text-[var(--text-3)]">95% Confidence Band</span>
        </div>
      </div>
    </div>
  );
}
