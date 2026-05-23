import { CheckCircle, XCircle, AlertTriangle, X } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { Toast, ToastVariant } from '@/hooks/useToast';

// ── Per-variant style config ──────────────────────────────────────────────────

const VARIANT_CONFIG: Record<ToastVariant, {
  icon:       React.ComponentType<{ size?: number; className?: string }>;
  iconClass:  string;
  bg:         string;
  border:     string;
}> = {
  success: {
    icon:      CheckCircle,
    iconClass: 'text-gain',
    bg:        'rgba(16,185,129,0.08)',
    border:    'rgba(16,185,129,0.25)',
  },
  error: {
    icon:      XCircle,
    iconClass: 'text-loss',
    bg:        'rgba(244,63,94,0.08)',
    border:    'rgba(244,63,94,0.25)',
  },
  warning: {
    icon:      AlertTriangle,
    iconClass: 'text-warn',
    bg:        'rgba(245,158,11,0.08)',
    border:    'rgba(245,158,11,0.25)',
  },
};

// ── Single toast item ─────────────────────────────────────────────────────────

function ToastItem({ toast, onDismiss }: {
  toast: Toast;
  onDismiss: (id: number) => void;
}) {
  const { icon: Icon, iconClass, bg, border } = VARIANT_CONFIG[toast.variant];

  return (
    <div
      role="status"
      aria-live="polite"
      className={cn(
        'flex items-center gap-3 px-4 py-3 rounded-lg shadow-xl',
        'animate-fade-up',
        // Pointer events so the close button is clickable
        'pointer-events-auto',
      )}
      style={{
        background:  bg,
        border:      `1px solid ${border}`,
        backdropFilter: 'blur(8px)',
        minWidth:    '240px',
        maxWidth:    '360px',
      }}
    >
      <Icon size={14} className={cn('shrink-0', iconClass)} aria-hidden="true" />

      <p className="flex-1 text-xs font-medium text-white leading-snug">
        {toast.message}
      </p>

      <button
        onClick={() => onDismiss(toast.id)}
        aria-label="Dismiss notification"
        className="shrink-0 text-[var(--text-3)] hover:text-[var(--text-2)] transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-info/50 rounded"
      >
        <X size={12} />
      </button>
    </div>
  );
}

// ── Container ─────────────────────────────────────────────────────────────────
//
// Fixed to the top-right corner, above everything (z-50).
// Pointer-events none on the container so clicks pass through the empty space;
// pointer-events auto is restored on each individual toast item.
// Bottom-right on mobile to avoid the topbar.

interface Props {
  toasts:    Toast[];
  onDismiss: (id: number) => void;
}

export default function ToastContainer({ toasts, onDismiss }: Props) {
  if (!toasts.length) return null;

  return (
    <div
      aria-label="Notifications"
      className={cn(
        'fixed z-50 flex flex-col gap-2',
        'pointer-events-none',
        // Desktop: top-right below the topbar (48px)
        'top-14 right-4',
        // Mobile: bottom above the bottom nav (56px nav + 8px gap)
        'md:top-14 md:bottom-auto md:right-4',
      )}
    >
      {toasts.map(t => (
        <ToastItem key={t.id} toast={t} onDismiss={onDismiss} />
      ))}
    </div>
  );
}
