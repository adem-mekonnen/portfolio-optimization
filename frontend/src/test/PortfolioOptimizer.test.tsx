import { render, screen, waitFor } from './utils';
import axios from 'axios';
import MockAdapter from 'axios-mock-adapter';
import PortfolioOptimizer from '@/components/PortfolioOptimizer';
import type { OptimizeResult } from '@/hooks/usePortfolioStore';

const mock = new MockAdapter(axios);

// ── Fixtures ──────────────────────────────────────────────────────────────────

const TICKERS = ['TSLA', 'SPY', 'BND'];

const mockOptResult: OptimizeResult = {
  weights:         { TSLA: 0.054, SPY: 0.381, BND: 0.565 },
  expected_return: 0.18,
  volatility:      0.12,
  sharpe_ratio:    1.33,
  ef_points:       [
    { return: 0.08, volatility: 0.06 },
    { return: 0.12, volatility: 0.09 },
    { return: 0.18, volatility: 0.12 },
  ],
  mean_returns: { TSLA: 0.35, SPY: 0.14, BND: 0.03 },
  cov_matrix: {
    TSLA: { TSLA: 0.16, SPY: 0.04, BND: 0.001 },
    SPY:  { TSLA: 0.04, SPY: 0.04, BND: 0.001 },
    BND:  { TSLA: 0.001, SPY: 0.001, BND: 0.002 },
  },
};

// ── Setup / teardown ──────────────────────────────────────────────────────────

beforeEach(() => {
  localStorage.clear();
  mock.reset();
});

afterAll(() => mock.restore());

// ── Helper ────────────────────────────────────────────────────────────────────

function renderOptimizer(props: Partial<React.ComponentProps<typeof PortfolioOptimizer>> = {}) {
  return render(
    <PortfolioOptimizer initialTickers={TICKERS} {...props} />,
  );
}

// ── Tests ─────────────────────────────────────────────────────────────────────

describe('PortfolioOptimizer', () => {

  // ── Initial render ──────────────────────────────────────────────────────────

  describe('initial render', () => {
    it('renders the component heading', () => {
      renderOptimizer();
      expect(screen.getByText('Portfolio Optimizer')).toBeInTheDocument();
    });

    it('renders a slider for each ticker', () => {
      renderOptimizer();
      const sliders = screen.getAllByRole('slider');
      expect(sliders).toHaveLength(TICKERS.length);
    });

    it('renders each ticker label', () => {
      renderOptimizer();
      TICKERS.forEach(t => expect(screen.getByText(t)).toBeInTheDocument());
    });

    it('renders the Run button', () => {
      renderOptimizer();
      expect(screen.getByRole('button', { name: /run optimization/i })).toBeInTheDocument();
    });

    it('renders the "Ready to optimize" empty state', () => {
      renderOptimizer();
      expect(screen.getByText('Ready to optimize')).toBeInTheDocument();
    });

    it('does not render the Reset button when no result exists', () => {
      renderOptimizer();
      expect(screen.queryByRole('button', { name: /reset/i })).toBeNull();
    });
  });

  // ── Weight sum indicator ────────────────────────────────────────────────────

  describe('weight sum indicator', () => {
    it('shows "100%" total when weights sum to 100', () => {
      renderOptimizer();
      // Default equal weights (33.33 each) round to 100
      expect(screen.getByText('100%')).toBeInTheDocument();
    });
  });

  // ── Transaction costs panel ─────────────────────────────────────────────────

  describe('transaction costs panel', () => {
    it('renders the Transaction Costs toggle button', () => {
      renderOptimizer();
      expect(screen.getByText('Transaction Costs')).toBeInTheDocument();
    });

    it('hides the cost sliders by default', () => {
      renderOptimizer();
      expect(screen.queryByText('Commission (bps/side)')).toBeNull();
    });

    it('reveals cost sliders when the toggle is clicked', async () => {
      const { user } = renderOptimizer();
      await user.click(screen.getByText('Transaction Costs'));
      expect(screen.getByText('Commission (bps/side)')).toBeInTheDocument();
      expect(screen.getByText('Slippage (bps/side)')).toBeInTheDocument();
    });

    it('shows all four rebalance frequency buttons when panel is open', async () => {
      const { user } = renderOptimizer();
      await user.click(screen.getByText('Transaction Costs'));
      ['Daily', 'Weekly', 'Monthly', 'Quarterly'].forEach(label => {
        expect(screen.getByRole('button', { name: label })).toBeInTheDocument();
      });
    });

    it('hides cost sliders again when toggle is clicked a second time', async () => {
      const { user } = renderOptimizer();
      await user.click(screen.getByText('Transaction Costs'));
      await user.click(screen.getByText('Transaction Costs'));
      expect(screen.queryByText('Commission (bps/side)')).toBeNull();
    });
  });

  // ── Run button states ───────────────────────────────────────────────────────

  describe('run button', () => {
    it('shows "Optimizing…" while the request is in flight', async () => {
      // Never resolves — keeps the component in loading state
      mock.onPost(/\/optimize/).reply(() => new Promise(() => {}));
      const { user } = renderOptimizer({ onBacktestData: vi.fn() });
      await user.click(screen.getByRole('button', { name: /run optimization/i }));
      expect(await screen.findByText('Optimizing…')).toBeInTheDocument();
    });

    it('is disabled while loading', async () => {
      mock.onPost(/\/optimize/).reply(() => new Promise(() => {}));
      const { user } = renderOptimizer({ onBacktestData: vi.fn() });
      await user.click(screen.getByRole('button', { name: /run optimization/i }));
      expect(screen.getByRole('button', { name: /optimizing/i })).toBeDisabled();
    });
  });

  // ── Error state ─────────────────────────────────────────────────────────────

  describe('error state', () => {
    it('displays the API error message when /optimize fails', async () => {
      mock.onPost(/\/optimize/).reply(400, { detail: 'Insufficient price history.' });
      const { user } = renderOptimizer({ onBacktestData: vi.fn() });
      await user.click(screen.getByRole('button', { name: /run optimization/i }));
      expect(await screen.findByText('Insufficient price history.')).toBeInTheDocument();
    });

    it('displays a network error message when the request fails entirely', async () => {
      mock.onPost(/\/optimize/).networkError();
      const { user } = renderOptimizer({ onBacktestData: vi.fn() });
      await user.click(screen.getByRole('button', { name: /run optimization/i }));
      // axios-mock-adapter surfaces network errors as "Network Error"
      expect(await screen.findByText('Network Error')).toBeInTheDocument();
    });

    it('clears the error when Run is clicked again', async () => {
      mock
        .onPost(/\/optimize/).replyOnce(400, { detail: 'First attempt failed.' })
        .onPost(/\/optimize/).reply(() => new Promise(() => {})); // second hangs

      const { user } = renderOptimizer({ onBacktestData: vi.fn() });

      // First click → error
      await user.click(screen.getByRole('button', { name: /run optimization/i }));
      expect(await screen.findByText('First attempt failed.')).toBeInTheDocument();

      // Second click → error clears, loading starts
      await user.click(screen.getByRole('button', { name: /run optimization/i }));
      await waitFor(() =>
        expect(screen.queryByText('First attempt failed.')).toBeNull(),
      );
    });
  });

  // ── Post-optimization result panels ────────────────────────────────────────

  describe('post-optimization results', () => {
    async function runOptimization(onBacktestData = vi.fn()) {
      mock.onPost(/\/optimize/).reply(200, mockOptResult);
      mock.onPost(/\/backtest/).reply(200, {
        data: [], gross_return: 12, total_return: 11,
        cost_drag: 1, total_costs_paid: 100,
        alpha: 2, beta: 0.9, max_drawdown: -5,
        rebalance_count: 12, avg_turnover: 4,
        benchmark_label: '60% SPY / 40% BND',
      });
      const utils = render(
        <PortfolioOptimizer initialTickers={TICKERS} onBacktestData={onBacktestData} />,
      );
      await utils.user.click(screen.getByRole('button', { name: /run optimization/i }));
      await waitFor(() => expect(screen.queryByText('Optimizing…')).toBeNull());
      return utils;
    }

    it('renders the Efficient Frontier section heading', async () => {
      await runOptimization();
      expect(screen.getByText('Efficient Frontier')).toBeInTheDocument();
    });

    it('renders the Comparison metrics table', async () => {
      await runOptimization();
      expect(screen.getByText('Comparison')).toBeInTheDocument();
      expect(screen.getByText('Your Mix')).toBeInTheDocument();
      expect(screen.getByText('AI Optimal')).toBeInTheDocument();
    });

    it('renders all three metric row labels', async () => {
      await runOptimization();
      expect(screen.getByText('Exp. Return')).toBeInTheDocument();
      expect(screen.getByText('Volatility')).toBeInTheDocument();
      expect(screen.getByText('Sharpe')).toBeInTheDocument();
    });

    it('renders the AI Optimal expected return value', async () => {
      await runOptimization();
      // 0.18 → 18.00%
      expect(screen.getByText('18.00%')).toBeInTheDocument();
    });

    it('renders the Recommended Weights section', async () => {
      await runOptimization();
      expect(screen.getByText('Recommended Weights')).toBeInTheDocument();
    });

    it('renders each ticker in the recommended weights panel', async () => {
      await runOptimization();
      // Each ticker appears at least twice (slider label + weights panel)
      TICKERS.forEach(t => {
        expect(screen.getAllByText(t).length).toBeGreaterThanOrEqual(1);
      });
    });

    it('renders the Reset button after a successful run', async () => {
      await runOptimization();
      expect(screen.getByRole('button', { name: /reset/i })).toBeInTheDocument();
    });

    it('calls onBacktestData with the backtest result', async () => {
      const onBacktestData = vi.fn();
      await runOptimization(onBacktestData);
      expect(onBacktestData).toHaveBeenCalledTimes(1);
      expect(onBacktestData).toHaveBeenCalledWith(
        expect.objectContaining({ total_return: 11 }),
      );
    });

    it('clears results and shows empty state after Reset is clicked', async () => {
      const { user } = await runOptimization();
      await user.click(screen.getByRole('button', { name: /reset/i }));
      expect(await screen.findByText('Ready to optimize')).toBeInTheDocument();
      expect(screen.queryByText('Efficient Frontier')).toBeNull();
    });
  });

  // ── Custom tickers ──────────────────────────────────────────────────────────

  describe('custom tickers', () => {
    it('renders sliders for a custom ticker list', () => {
      render(<PortfolioOptimizer initialTickers={['AAPL', 'MSFT']} />);
      expect(screen.getByText('AAPL')).toBeInTheDocument();
      expect(screen.getByText('MSFT')).toBeInTheDocument();
    });

    it('renders the correct number of sliders for a two-ticker portfolio', () => {
      render(<PortfolioOptimizer initialTickers={['AAPL', 'MSFT']} />);
      expect(screen.getAllByRole('slider')).toHaveLength(2);
    });
  });
});
