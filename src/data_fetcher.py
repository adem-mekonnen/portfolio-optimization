"""
Data fetcher with TTL-aware caching.

Prices are cached on disk via joblib so repeated calls within the same
process (or across restarts) don't hit yfinance unnecessarily.  A separate
manifest (managed by cache_manager) tracks *when* each entry was written so
we can expire stale data:

  - Short-range queries  (start within last 90 days) → 4-hour TTL
  - Long-range queries   (start older than 90 days)  → 24-hour TTL

When a cached result is stale the joblib entry is cleared for that call and
fresh data is downloaded from yfinance.
"""

import logging
import os

import pandas as pd
import yfinance as yf
from joblib import Memory

from .cache_manager import is_stale, record_fetch

logger = logging.getLogger(__name__)

CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", ".cache")
memory    = Memory(CACHE_DIR, verbose=0)


# ── Internal cached downloader ────────────────────────────────────────────────

@memory.cache
def _cached_download(tickers: list, start: str, end: str | None) -> pd.DataFrame:
    """
    Raw joblib-cached yfinance download.  Do not call directly — use
    fetch_data() which handles TTL expiry on top of this.
    """
    logger.info("Downloading %s from yfinance (start=%s, end=%s)", tickers, start, end)
    data = yf.download(tickers, start=start, end=end, auto_adjust=False, progress=False)

    if data.empty:
        raise ValueError(f"No data returned for tickers: {tickers}")

    # Normalise MultiIndex columns produced by yfinance for multi-ticker calls
    if isinstance(data.columns, pd.MultiIndex):
        if "Adj Close" in data.columns.levels[0]:
            return data["Adj Close"]
        return data["Close"]

    # Single-ticker case
    if "Adj Close" in data.columns:
        df = pd.DataFrame(data["Adj Close"])
        df.columns = tickers
        return df
    if "Close" in data.columns:
        df = pd.DataFrame(data["Close"])
        df.columns = tickers
        return df

    raise ValueError("Could not find valid price columns in downloaded data.")


def _bust_cache(tickers: list, start: str, end: str | None) -> None:
    """Remove the joblib cache entry for this exact call signature."""
    try:
        _cached_download.call_and_shelve(tickers, start, end).clear()
    except Exception:
        # Fallback: wipe the entire joblib store for this function
        try:
            _cached_download.clear()
        except Exception as exc:
            logger.warning("Could not clear joblib cache: %s", exc)


# ── Public API ────────────────────────────────────────────────────────────────

def fetch_data(
    tickers: list | str,
    start: str = "2015-01-01",
    end: str | None = None,
) -> pd.DataFrame:
    """
    Fetch Adjusted Close prices for *tickers* between *start* and *end*.

    Results are cached on disk.  If the cached entry is older than its TTL
    (4 h for recent data, 24 h for historical) the cache is busted and fresh
    data is downloaded from yfinance.

    Parameters
    ----------
    tickers : str or list of str
    start   : ISO date string, default "2015-01-01"
    end     : ISO date string or None (defaults to today)

    Returns
    -------
    pd.DataFrame  columns = tickers, index = DatetimeIndex
    """
    if not isinstance(tickers, list):
        tickers = [tickers]

    # Bust the joblib cache when the TTL has expired so the next call
    # re-downloads fresh data and records a new timestamp.
    if is_stale(tickers, start, end):
        logger.info("Cache stale for %s — busting and re-fetching.", tickers)
        _bust_cache(tickers, start, end)

    try:
        result = _cached_download(tickers, start, end)
        # Record the fetch timestamp so TTL tracking stays accurate
        record_fetch(tickers, start, end)
        return result
    except Exception as exc:
        raise ValueError(f"Error fetching data for {tickers}: {exc}") from exc
