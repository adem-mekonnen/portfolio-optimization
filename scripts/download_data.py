"""
Standalone data download utility.

Downloads historical Adjusted Close prices for the configured tickers and
saves them to data/raw/historical_data.csv and data/processed/cleaned_prices.csv
(with daily returns in data/processed/daily_returns.csv).

Usage
-----
    python scripts/download_data.py                        # default tickers & dates
    python scripts/download_data.py --tickers TSLA SPY BND AAPL
    python scripts/download_data.py --start 2018-01-01 --end 2024-12-31
    python scripts/download_data.py --tickers TSLA --start 2020-01-01 --no-save

Output files
------------
    data/raw/historical_data.csv        raw multi-ticker Adj Close prices
    data/processed/cleaned_prices.csv   prices after forward-fill + dropna
    data/processed/daily_returns.csv    percentage daily returns
"""

import argparse
import os
import sys

import pandas as pd
import yfinance as yf

# ── Defaults ──────────────────────────────────────────────────────────────────
DEFAULT_TICKERS    = ["TSLA", "SPY", "BND"]
DEFAULT_START      = "2015-01-01"
DEFAULT_END        = None          # None → today
RAW_DIR            = os.path.join(os.path.dirname(__file__), "..", "data", "raw")
PROCESSED_DIR      = os.path.join(os.path.dirname(__file__), "..", "data", "processed")


# ── Download ──────────────────────────────────────────────────────────────────

def download(
    tickers: list[str],
    start: str = DEFAULT_START,
    end: str | None = DEFAULT_END,
) -> pd.DataFrame:
    """
    Download Adjusted Close prices for *tickers* from yfinance.

    Returns a DataFrame with one column per ticker and a DatetimeIndex.
    Raises ValueError if yfinance returns no data.
    """
    print(f"  Downloading {tickers}  ({start} → {end or 'today'}) …")
    raw = yf.download(tickers, start=start, end=end, auto_adjust=False, progress=False)

    if raw.empty:
        raise ValueError(f"yfinance returned no data for {tickers}.")

    # Normalise MultiIndex produced for multi-ticker calls
    if isinstance(raw.columns, pd.MultiIndex):
        if "Adj Close" in raw.columns.levels[0]:
            prices = raw["Adj Close"]
        else:
            prices = raw["Close"]
    else:
        col = "Adj Close" if "Adj Close" in raw.columns else "Close"
        prices = raw[[col]].copy()
        prices.columns = tickers

    # Ensure column order matches the requested ticker list
    prices = prices[[t for t in tickers if t in prices.columns]]
    return prices


# ── Clean ─────────────────────────────────────────────────────────────────────

def clean(prices: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Forward-fill up to 5 consecutive missing values, then drop any remaining
    rows with NaN.

    Returns (cleaned_prices, daily_returns).
    """
    cleaned = prices.ffill(limit=5).dropna()
    returns = cleaned.pct_change().dropna()
    return cleaned, returns


# ── Save ──────────────────────────────────────────────────────────────────────

def save(
    raw_prices: pd.DataFrame,
    cleaned_prices: pd.DataFrame,
    daily_returns: pd.DataFrame,
) -> None:
    """Write all three DataFrames to CSV."""
    os.makedirs(RAW_DIR,       exist_ok=True)
    os.makedirs(PROCESSED_DIR, exist_ok=True)

    raw_path     = os.path.join(RAW_DIR,       "historical_data.csv")
    cleaned_path = os.path.join(PROCESSED_DIR, "cleaned_prices.csv")
    returns_path = os.path.join(PROCESSED_DIR, "daily_returns.csv")

    raw_prices.to_csv(raw_path)
    cleaned_prices.to_csv(cleaned_path)
    daily_returns.to_csv(returns_path)

    print(f"  ✓ Raw prices    → {raw_path}  ({len(raw_prices)} rows)")
    print(f"  ✓ Cleaned prices→ {cleaned_path}  ({len(cleaned_prices)} rows)")
    print(f"  ✓ Daily returns → {returns_path}  ({len(daily_returns)} rows)")


# ── Summary ───────────────────────────────────────────────────────────────────

def print_summary(prices: pd.DataFrame, returns: pd.DataFrame) -> None:
    """Print a quick data-quality summary to stdout."""
    print("\n  ── Data summary ──────────────────────────────────────────")
    print(f"  Date range : {prices.index[0].date()} → {prices.index[-1].date()}")
    print(f"  Trading days: {len(prices)}")
    print(f"  Tickers    : {list(prices.columns)}")
    print()
    print(f"  {'Ticker':<8}  {'Last price':>12}  {'Ann. return':>12}  {'Ann. vol':>10}  {'Missing':>8}")
    print(f"  {'-'*8}  {'-'*12}  {'-'*12}  {'-'*10}  {'-'*8}")
    ann_ret = returns.mean() * 252
    ann_vol = returns.std() * (252 ** 0.5)
    for t in prices.columns:
        last    = prices[t].iloc[-1]
        missing = prices[t].isna().sum()
        print(
            f"  {t:<8}  {last:>12.2f}  {ann_ret[t]:>11.1%}  {ann_vol[t]:>9.1%}  {missing:>8}"
        )
    print()


# ── CLI ───────────────────────────────────────────────────────────────────────

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Download and save historical price data.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument(
        "--tickers", nargs="+", default=DEFAULT_TICKERS,
        metavar="TICKER",
        help="Space-separated list of ticker symbols.",
    )
    p.add_argument(
        "--start", default=DEFAULT_START,
        help="Start date (YYYY-MM-DD).",
    )
    p.add_argument(
        "--end", default=DEFAULT_END,
        help="End date (YYYY-MM-DD). Defaults to today.",
    )
    p.add_argument(
        "--no-save", action="store_true",
        help="Print summary only; do not write CSV files.",
    )
    return p.parse_args()


def main() -> None:
    args = _parse_args()
    tickers = [t.upper() for t in args.tickers]

    print(f"\n{'='*60}")
    print(f"  GMF Investments — Data Downloader")
    print(f"{'='*60}")

    try:
        raw_prices = download(tickers, start=args.start, end=args.end)
    except ValueError as exc:
        print(f"\n  ✗ Download failed: {exc}", file=sys.stderr)
        sys.exit(1)

    cleaned_prices, daily_returns = clean(raw_prices)
    print_summary(cleaned_prices, daily_returns)

    if not args.no_save:
        save(raw_prices, cleaned_prices, daily_returns)
    else:
        print("  --no-save set: skipping file writes.\n")

    print("  Done.\n")


if __name__ == "__main__":
    main()
