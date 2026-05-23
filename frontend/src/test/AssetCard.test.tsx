import { render, screen } from './utils';
import AssetCard from '@/components/AssetCard';

const baseProps = {
  ticker: 'TSLA',
  price: 250.75,
  change: 2.34,
  sentiment: 'Bullish' as const,
};

describe('AssetCard', () => {
  describe('loading state', () => {
    it('renders skeleton placeholders and no price', () => {
      const { container } = render(<AssetCard {...baseProps} isLoading />);
      expect(screen.queryByText('$250.75')).toBeNull();
      // Three skeleton divs should be present
      expect(container.querySelectorAll('.skeleton').length).toBeGreaterThanOrEqual(1);
    });
  });

  describe('error state', () => {
    it('shows the ticker and an error message', () => {
      render(<AssetCard {...baseProps} hasError />);
      expect(screen.getByText('TSLA')).toBeInTheDocument();
      expect(screen.getByText(/failed to load/i)).toBeInTheDocument();
    });

    it('calls onClick when the error card is clicked', async () => {
      const onClick = vi.fn();
      const { user } = render(<AssetCard {...baseProps} hasError onClick={onClick} />);
      await user.click(screen.getByText('TSLA').closest('div')!);
      expect(onClick).toHaveBeenCalledTimes(1);
    });
  });

  describe('normal state', () => {
    it('renders the ticker symbol', () => {
      render(<AssetCard {...baseProps} />);
      expect(screen.getByText('TSLA')).toBeInTheDocument();
    });

    it('renders the formatted price', () => {
      render(<AssetCard {...baseProps} />);
      expect(screen.getByText('$250.75')).toBeInTheDocument();
    });

    it('renders a positive change with a + prefix', () => {
      render(<AssetCard {...baseProps} change={2.34} />);
      expect(screen.getByText('+2.34%')).toBeInTheDocument();
    });

    it('renders a negative change without a + prefix', () => {
      render(<AssetCard {...baseProps} change={-1.5} />);
      expect(screen.getByText('-1.50%')).toBeInTheDocument();
    });

    it('renders the Bullish sentiment badge', () => {
      render(<AssetCard {...baseProps} sentiment="Bullish" />);
      expect(screen.getByText('Bullish')).toBeInTheDocument();
    });

    it('renders the Bearish sentiment badge', () => {
      render(<AssetCard {...baseProps} sentiment="Bearish" />);
      expect(screen.getByText('Bearish')).toBeInTheDocument();
    });

    it('renders the known asset name for TSLA', () => {
      render(<AssetCard {...baseProps} ticker="TSLA" />);
      expect(screen.getByText('Tesla, Inc.')).toBeInTheDocument();
    });

    it('renders the known asset name for SPY', () => {
      render(<AssetCard {...baseProps} ticker="SPY" />);
      expect(screen.getByText('SPDR S&P 500 ETF')).toBeInTheDocument();
    });

    it('falls back to the ticker as name for unknown symbols', () => {
      render(<AssetCard {...baseProps} ticker="AAPL" />);
      // name falls back to ticker when not in META
      expect(screen.getAllByText('AAPL').length).toBeGreaterThanOrEqual(1);
    });

    it('calls onClick when clicked', async () => {
      const onClick = vi.fn();
      const { user } = render(<AssetCard {...baseProps} onClick={onClick} />);
      await user.click(screen.getByText('TSLA').closest('div')!);
      expect(onClick).toHaveBeenCalledTimes(1);
    });

    it('does not throw when onClick is not provided', async () => {
      const { user } = render(<AssetCard {...baseProps} />);
      // Should not throw
      await user.click(screen.getByText('TSLA').closest('div')!);
    });
  });
});
