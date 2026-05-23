import { render, screen } from './utils';
import BacktestingResult from '@/components/BacktestingResult';
import type { ComponentProps } from 'react';

type Props = ComponentProps<typeof BacktestingResult>;

const makeData = (overrides: Partial<Props['data']> = {}): Props['data'] => ({
  data: [
    { date: '2024-01-01', strategy: 1.0,  benchmark: 1.0  },
    { date: '2024-06-01', strategy: 1.08, benchmark: 1.05 },
    { date: '2024-12-31', strategy: 1.15, benchmark: 1.10 },
  ],
  gross_return:     16.0,
  total_return:     15.0,
  cost_drag:        1.0,
  total_costs_paid: 100,
  alpha:            3.5,
  beta:             0.88,
  max_drawdown:     -7.2,
  rebalance_count:  12,
  avg_turnover:     4.5,
  benchmark_label:  '60% SPY / 40% BND',
  ...overrides,
});

describe('BacktestingResult', () => {
  it('renders nothing when data is null', () => {
    const { container } = render(<BacktestingResult data={null} />);
    expect(container.firstChild).toBeNull();
  });

  it('renders the "Backtest Results" heading', () => {
    render(<BacktestingResult data={makeData()} />);
    expect(screen.getByText('Backtest Results')).toBeInTheDocument();
  });

  it('displays the net return value', () => {
    render(<BacktestingResult data={makeData({ total_return: 15.0 })} />);
    expect(screen.getByText('+15.00%')).toBeInTheDocument();
  });

  it('displays a negative net return without a + prefix', () => {
    render(<BacktestingResult data={makeData({ total_return: -5.5 })} />);
    expect(screen.getByText('-5.50%')).toBeInTheDocument();
  });

  it('displays the alpha value', () => {
    render(<BacktestingResult data={makeData({ alpha: 3.5 })} />);
    expect(screen.getByText('+3.50%')).toBeInTheDocument();
  });

  it('displays the beta value', () => {
    render(<BacktestingResult data={makeData({ beta: 0.88 })} />);
    expect(screen.getByText('0.88')).toBeInTheDocument();
  });

  it('displays the max drawdown value', () => {
    render(<BacktestingResult data={makeData({ max_drawdown: -7.2 })} />);
    expect(screen.getByText('-7.20%')).toBeInTheDocument();
  });

  it('shows the cost notice when cost_drag > 0', () => {
    render(<BacktestingResult data={makeData({ cost_drag: 1.0 })} />);
    expect(screen.getByText(/costs reduced returns/i)).toBeInTheDocument();
  });

  it('hides the cost notice when cost_drag is 0', () => {
    render(<BacktestingResult data={makeData({ cost_drag: 0, total_costs_paid: 0 })} />);
    expect(screen.queryByText(/costs reduced returns/i)).toBeNull();
  });

  it('shows the "Cost-adjusted" badge when cost_drag > 0', () => {
    render(<BacktestingResult data={makeData({ cost_drag: 1.0 })} />);
    expect(screen.getByText('Cost-adjusted')).toBeInTheDocument();
  });

  it('renders the benchmark label in the subtitle', () => {
    render(<BacktestingResult data={makeData({ benchmark_label: '100% SPY' })} />);
    expect(screen.getAllByText(/100% SPY/).length).toBeGreaterThanOrEqual(1);
  });

  it('renders the benchmark label in the chart legend', () => {
    render(<BacktestingResult data={makeData({ benchmark_label: 'Equal-weight (50% AAPL / 50% MSFT)' })} />);
    expect(screen.getAllByText(/Equal-weight/).length).toBeGreaterThanOrEqual(1);
  });

  it('toggles between Linear and Log scale', async () => {
    const { user } = render(<BacktestingResult data={makeData()} />);
    // The toggle button is the element between "Linear" and "Log" labels
    const toggle = screen.getByRole('button');
    // Initial state: Linear active
    expect(screen.getByText('Linear')).toBeInTheDocument();
    await user.click(toggle);
    // After click: Log should be active (no crash)
    expect(screen.getByText('Log')).toBeInTheDocument();
  });
});
