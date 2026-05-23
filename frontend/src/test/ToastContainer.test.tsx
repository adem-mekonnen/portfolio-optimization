import { render, screen } from './utils';
import ToastContainer from '@/components/ToastContainer';
import type { Toast } from '@/hooks/useToast';

const makeToast = (overrides: Partial<Toast> = {}): Toast => ({
  id:      1,
  message: 'Test message',
  variant: 'success',
  ...overrides,
});

describe('ToastContainer', () => {
  it('renders nothing when toasts array is empty', () => {
    const { container } = render(<ToastContainer toasts={[]} onDismiss={() => {}} />);
    expect(container.firstChild).toBeNull();
  });

  it('renders a success toast with the correct message', () => {
    render(<ToastContainer toasts={[makeToast({ message: 'Prices updated' })]} onDismiss={() => {}} />);
    expect(screen.getByText('Prices updated')).toBeInTheDocument();
  });

  it('renders an error toast', () => {
    render(<ToastContainer toasts={[makeToast({ variant: 'error', message: 'Failed' })]} onDismiss={() => {}} />);
    expect(screen.getByText('Failed')).toBeInTheDocument();
  });

  it('renders a warning toast', () => {
    render(<ToastContainer toasts={[makeToast({ variant: 'warning', message: 'Partial failure' })]} onDismiss={() => {}} />);
    expect(screen.getByText('Partial failure')).toBeInTheDocument();
  });

  it('renders multiple toasts', () => {
    const toasts: Toast[] = [
      { id: 1, message: 'First',  variant: 'success' },
      { id: 2, message: 'Second', variant: 'error'   },
    ];
    render(<ToastContainer toasts={toasts} onDismiss={() => {}} />);
    expect(screen.getByText('First')).toBeInTheDocument();
    expect(screen.getByText('Second')).toBeInTheDocument();
  });

  it('calls onDismiss with the correct id when close button is clicked', async () => {
    const onDismiss = vi.fn();
    const { user } = render(
      <ToastContainer toasts={[makeToast({ id: 42 })]} onDismiss={onDismiss} />,
    );
    await user.click(screen.getByRole('button', { name: /dismiss/i }));
    expect(onDismiss).toHaveBeenCalledWith(42);
  });

  it('has accessible role="status" on each toast', () => {
    render(<ToastContainer toasts={[makeToast()]} onDismiss={() => {}} />);
    expect(screen.getByRole('status')).toBeInTheDocument();
  });

  it('has an accessible label on the notifications container', () => {
    render(<ToastContainer toasts={[makeToast()]} onDismiss={() => {}} />);
    expect(screen.getByLabelText('Notifications')).toBeInTheDocument();
  });
});
