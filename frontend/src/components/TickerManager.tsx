import { useRef, useState } from 'react';
import { Plus, X } from 'lucide-react';
import { cn } from '@/lib/utils';

// ── Validation ────────────────────────────────────────────────────────────────
// Mirrors the backend regex in src/main.py:
//   ^[A-Z]{1,5}(\.[A-Z]{1,2})?$
// Covers US equities (TSLA), ETFs (SPY), and some international tickers (BRK.B).
const TICKER_RE = /^[A-Z]{1,5}(\.[A-Z]{1,2})?$/;

export const MIN_TICKERS = 2;   // optimizer requires at least 2
export const MAX_TICKERS = 5;   // COLORS palette has 5 entries

export function validateTicker(raw: string): { ok: true; ticker: string } | { ok: false; error: string } {
  const t = raw.trim().toUpperCase();
  if (!t) return { ok: false, error: 'Enter a ticker symbol.' };
  if (!TICKER_RE.test(t)) return { ok: false, error: `"${t}" is not a valid ticker format.` };
  return { ok: true, ticker: t };
}

// ── Component ─────────────────────────────────────────────────────────────────

interface Props {
  tickers:   string[];
  onChange:  (tickers: string[]) => void;
}

/**
 * Inline ticker chip manager.
 *
 * Renders the current tickers as removable chips followed by an add-input.
 * Validates format client-side (same regex as the backend) before adding.
 * Enforces MIN_TICKERS (2) and MAX_TICKERS (5) bounds.
 */
export default function TickerManager({ tickers, onChange }: Props) {
  const [inputVal, setInputVal] = useState('');
  const [error,    setError]    = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const add = () => {
    setError(null);
    const result = validateTicker(inputVal);
    if (!result.ok) { setError(result.error); return; }

    const { ticker } = result;
    if (tickers.includes(ticker)) {
      setError(`${ticker} is already in your list.`);
      return;
    }
    if (tickers.length >= MAX_TICKERS) {
      setError(`Maximum ${MAX_TICKERS} tickers allowed.`);
      return;
    }
    onChange([...tickers, ticker]);
    setInputVal('');
    inputRef.current?.focus();
  };

  const remove = (ticker: string) => {
    if (tickers.length <= MIN_TICKERS) return; // silently block — button is disabled
    setError(null);
    onChange(tickers.filter(t => t !== ticker));
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') { e.preventDefault(); add(); }
    // Backspace on empty input removes the last ticker (common UX pattern)
    if (e.key === 'Backspace' && inputVal === '' && tickers.length > MIN_TICKERS) {
      remove(tickers[tickers.length - 1]);
    }
  };

  const atMax = tickers.length >= MAX_TICKERS;

  return (
    <div>
      {/* Chip row + input */}
      <div
        className={cn(
          'flex flex-wrap items-center gap-1.5 px-3 py-2 rounded-lg',
          'transition-colors',
          error
            ? 'border border-loss/40'
            : 'border border-[var(--border)] focus-within:border-[var(--border-2)]',
        )}
        style={{ background: 'var(--surface-2)' }}
        // Clicking anywhere in the row focuses the input
        onClick={() => inputRef.current?.focus()}
      >
        {/* Ticker chips */}
        {tickers.map(t => (
          <span
            key={t}
            className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-semibold font-mono"
            style={{
              background: 'var(--surface-3)',
              border:     '1px solid var(--border-2)',
              color:      'var(--text-1)',
            }}
          >
            {t}
            <button
              type="button"
              onClick={e => { e.stopPropagation(); remove(t); }}
              disabled={tickers.length <= MIN_TICKERS}
              aria-label={`Remove ${t}`}
              className={cn(
                'rounded transition-colors',
                tickers.length <= MIN_TICKERS
                  ? 'opacity-25 cursor-not-allowed'
                  : 'text-[var(--text-3)] hover:text-loss focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-info/50',
              )}
            >
              <X size={10} />
            </button>
          </span>
        ))}

        {/* Add input — hidden when at max */}
        {!atMax && (
          <input
            ref={inputRef}
            type="text"
            value={inputVal}
            onChange={e => { setInputVal(e.target.value.toUpperCase()); setError(null); }}
            onKeyDown={handleKeyDown}
            placeholder="Add ticker…"
            maxLength={7}   // longest valid: BRK.B = 5 chars, with dot = 6
            aria-label="Add ticker symbol"
            aria-invalid={!!error}
            className={cn(
              'flex-1 min-w-[80px] bg-transparent text-xs font-mono text-white',
              'placeholder:text-[var(--text-3)] outline-none',
            )}
          />
        )}

        {/* Add button — only shown when input has content */}
        {!atMax && inputVal && (
          <button
            type="button"
            onClick={add}
            aria-label="Add ticker"
            className="shrink-0 text-[var(--text-3)] hover:text-info transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-info/50 rounded"
          >
            <Plus size={13} />
          </button>
        )}

        {/* Max reached label */}
        {atMax && (
          <span className="text-2xs text-[var(--text-3)] ml-1">
            Max {MAX_TICKERS} tickers
          </span>
        )}
      </div>

      {/* Inline error */}
      {error && (
        <p className="text-2xs text-loss mt-1.5 px-1" role="alert">
          {error}
        </p>
      )}

      {/* Helper text */}
      {!error && (
        <p className="text-2xs text-[var(--text-3)] mt-1.5 px-1">
          {tickers.length < MIN_TICKERS
            ? `Add at least ${MIN_TICKERS - tickers.length} more ticker${MIN_TICKERS - tickers.length !== 1 ? 's' : ''}.`
            : `${tickers.length}/${MAX_TICKERS} tickers · Press Enter or click + to add`}
        </p>
      )}
    </div>
  );
}
