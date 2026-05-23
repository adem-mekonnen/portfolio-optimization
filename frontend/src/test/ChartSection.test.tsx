import { render, screen } from './utils';
import ChartSection from '@/components/ChartSection';

const makeForecast = (n = 5) =>
  Array.from({ length: n }, (_, i) => ({
    date:            `2025-06-${String(i + 1).padStart(2, '0')}`,
    predicted_price: 300 + i * 2,
    lower_bound:     290 + i * 2,
    upper_bound:     310 + i * 2,
  }));

describe('ChartSection', () => {
  it('renders the ticker name in the header', () => {
    render(<ChartSection data={makeForecast()} selectedTicker="TSLA" />);
    expect(screen.getByText('TSLA')).toBeInTheDocument();
  });

  it('renders the "30-Day Forecast" label', () => {
    render(<ChartSection data={makeForecast()} selectedTicker="SPY" />);
    expect(screen.getByText('30-Day Forecast')).toBeInTheDocument();
  });

  it('renders the LSTM badge', () => {
    render(<ChartSection data={makeForecast()} />);
    expect(screen.getByText('LSTM')).toBeInTheDocument();
  });

  it('renders the Forecast legend item', () => {
    render(<ChartSection data={makeForecast()} />);
    expect(screen.getByText('Forecast')).toBeInTheDocument();
  });

  it('renders the confidence band legend item', () => {
    render(<ChartSection data={makeForecast()} />);
    expect(screen.getByText('95% Confidence Band')).toBeInTheDocument();
  });

  it('renders without crashing when data is empty', () => {
    render(<ChartSection data={[]} selectedTicker="BND" />);
    expect(screen.getByText('BND')).toBeInTheDocument();
  });

  it('defaults selectedTicker to TSLA when not provided', () => {
    render(<ChartSection data={makeForecast()} />);
    expect(screen.getByText('TSLA')).toBeInTheDocument();
  });
});
