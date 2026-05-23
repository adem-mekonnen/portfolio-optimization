import { render, screen } from './utils';
import Sidebar, { BottomNav, type View } from '@/components/Sidebar';

const NAV_LABELS = ['Overview', 'Forecast', 'Portfolio', 'Backtest'];

// ── Sidebar (desktop) ─────────────────────────────────────────────────────────

describe('Sidebar', () => {
  const onNavigate = vi.fn();

  beforeEach(() => onNavigate.mockClear());

  // ── API status indicator ───────────────────────────────────────────────────
  // Labels were shortened in the redesign:
  //   checking     → "Connecting"
  //   connected    → "Connected"
  //   disconnected → "Disconnected"

  describe('status: checking', () => {
    it('shows "Connecting" label', () => {
      render(<Sidebar activeView="overview" onNavigate={onNavigate} apiStatus="checking" />);
      expect(screen.getByText('Connecting')).toBeInTheDocument();
    });

    it('does NOT render the ping animation span', () => {
      const { container } = render(
        <Sidebar activeView="overview" onNavigate={onNavigate} apiStatus="checking" />,
      );
      expect(container.querySelector('.animate-ping')).toBeNull();
    });
  });

  describe('status: connected', () => {
    it('shows "Connected" label', () => {
      render(<Sidebar activeView="overview" onNavigate={onNavigate} apiStatus="connected" />);
      expect(screen.getByText('Connected')).toBeInTheDocument();
    });

    it('renders the ping animation span', () => {
      const { container } = render(
        <Sidebar activeView="overview" onNavigate={onNavigate} apiStatus="connected" />,
      );
      expect(container.querySelector('.animate-ping')).toBeInTheDocument();
    });
  });

  describe('status: disconnected', () => {
    it('shows "Disconnected" label', () => {
      render(<Sidebar activeView="overview" onNavigate={onNavigate} apiStatus="disconnected" />);
      expect(screen.getByText('Disconnected')).toBeInTheDocument();
    });

    it('does NOT render the ping animation span', () => {
      const { container } = render(
        <Sidebar activeView="overview" onNavigate={onNavigate} apiStatus="disconnected" />,
      );
      expect(container.querySelector('.animate-ping')).toBeNull();
    });
  });

  // ── Navigation rendering ───────────────────────────────────────────────────

  describe('navigation items', () => {
    it('renders all four nav buttons', () => {
      render(<Sidebar activeView="overview" onNavigate={onNavigate} apiStatus="connected" />);
      NAV_LABELS.forEach((label) => {
        expect(screen.getByText(label)).toBeInTheDocument();
      });
    });

    it('renders exactly one nav-active-bar for the active item', () => {
      const { container } = render(
        <Sidebar activeView="forecast" onNavigate={onNavigate} apiStatus="connected" />,
      );
      // The redesigned active indicator uses the .nav-active-bar CSS class
      const bars = container.querySelectorAll('.nav-active-bar');
      expect(bars).toHaveLength(1);
    });
  });

  // ── Active state per view ──────────────────────────────────────────────────

  describe('active nav state', () => {
    const views: View[] = ['overview', 'forecast', 'portfolio', 'backtest'];

    views.forEach((view, idx) => {
      it(`applies active background style to "${NAV_LABELS[idx]}" when activeView="${view}"`, () => {
        render(<Sidebar activeView={view} onNavigate={onNavigate} apiStatus="connected" />);
        const activeButton = screen.getByText(NAV_LABELS[idx]).closest('button');
        // Active button gets #EFF6FF (Blue-50) inline background in light mode
        expect(activeButton).toHaveStyle({ background: 'rgb(239, 246, 255)' });
      });

      it(`does not apply active background to inactive items when activeView="${view}"`, () => {
        render(<Sidebar activeView={view} onNavigate={onNavigate} apiStatus="connected" />);
        NAV_LABELS.filter((_, i) => i !== idx).forEach((otherLabel) => {
          const btn = screen.getByText(otherLabel).closest('button');
          // Inactive buttons have no inline background style
          expect(btn).not.toHaveStyle({ background: 'rgba(56, 139, 253, 0.1)' });
        });
      });
    });
  });

  // ── Interaction ────────────────────────────────────────────────────────────

  describe('navigation interaction', () => {
    it('calls onNavigate with the correct view id when a nav button is clicked', async () => {
      const { user } = render(
        <Sidebar activeView="overview" onNavigate={onNavigate} apiStatus="connected" />,
      );
      await user.click(screen.getByText('Portfolio'));
      expect(onNavigate).toHaveBeenCalledWith('portfolio');
    });

    it('calls onNavigate once per click', async () => {
      const { user } = render(
        <Sidebar activeView="overview" onNavigate={onNavigate} apiStatus="connected" />,
      );
      await user.click(screen.getByText('Backtest'));
      expect(onNavigate).toHaveBeenCalledTimes(1);
    });
  });

  // ── Static content ─────────────────────────────────────────────────────────

  it('renders the GMF brand name', () => {
    render(<Sidebar activeView="overview" onNavigate={onNavigate} apiStatus="connected" />);
    expect(screen.getByText('GMF')).toBeInTheDocument();
  });

  it('renders the disclaimer text', () => {
    render(<Sidebar activeView="overview" onNavigate={onNavigate} apiStatus="connected" />);
    expect(screen.getByText(/educational use only/i)).toBeInTheDocument();
  });
});

// ── BottomNav (mobile) ────────────────────────────────────────────────────────

describe('BottomNav', () => {
  const onNavigate = vi.fn();

  beforeEach(() => onNavigate.mockClear());

  it('renders all four nav buttons', () => {
    render(<BottomNav activeView="overview" onNavigate={onNavigate} />);
    NAV_LABELS.forEach((label) => {
      expect(screen.getByText(label)).toBeInTheDocument();
    });
  });

  describe('active nav state', () => {
    const views: View[] = ['overview', 'forecast', 'portfolio', 'backtest'];

    views.forEach((view, idx) => {
      it(`sets aria-current="page" on "${NAV_LABELS[idx]}" when activeView="${view}"`, () => {
        render(<BottomNav activeView={view} onNavigate={onNavigate} />);
        const activeButton = screen.getByText(NAV_LABELS[idx]).closest('button');
        expect(activeButton).toHaveAttribute('aria-current', 'page');
      });

      it(`does not set aria-current on inactive items when activeView="${view}"`, () => {
        render(<BottomNav activeView={view} onNavigate={onNavigate} />);
        NAV_LABELS.filter((_, i) => i !== idx).forEach((otherLabel) => {
          const btn = screen.getByText(otherLabel).closest('button');
          expect(btn).not.toHaveAttribute('aria-current');
        });
      });
    });
  });

  describe('navigation interaction', () => {
    it('calls onNavigate with the correct view id when a button is clicked', async () => {
      const { user } = render(<BottomNav activeView="overview" onNavigate={onNavigate} />);
      await user.click(screen.getByText('Forecast'));
      expect(onNavigate).toHaveBeenCalledWith('forecast');
    });

    it('calls onNavigate once per click', async () => {
      const { user } = render(<BottomNav activeView="overview" onNavigate={onNavigate} />);
      await user.click(screen.getByText('Overview'));
      expect(onNavigate).toHaveBeenCalledTimes(1);
    });
  });

  it('has an accessible nav landmark label', () => {
    render(<BottomNav activeView="overview" onNavigate={onNavigate} />);
    expect(screen.getByRole('navigation', { name: /main navigation/i })).toBeInTheDocument();
  });
});
