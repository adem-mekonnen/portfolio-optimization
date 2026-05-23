"""
Out-of-sample LSTM model evaluation.

For each trained ticker model, this script:
  1. Downloads price data from TRAIN_END+1 day to today (the held-out period).
  2. Runs the LSTM autoregressively over that period, one step at a time,
     using only data available up to each prediction date (walk-forward).
  3. Computes MAE, RMSE, MAPE, and directional accuracy.
  4. Prints a per-ticker report and an overall summary table.
  5. Optionally saves per-ticker prediction CSVs to reports/.

Usage
-----
    python scripts/evaluate_models.py
    python scripts/evaluate_models.py --tickers TSLA SPY
    python scripts/evaluate_models.py --start 2025-01-01 --save-csv
    python scripts/evaluate_models.py --no-lstm   # mock/GBM baseline only

Walk-forward protocol
---------------------
At each step t we feed the model the SEQ_LENGTH prices ending at t-1 and
predict price at t.  This mirrors real-world usage: the model never sees
future data.  The window slides forward by one day at a time.
"""

import argparse
import os
import sys

import joblib
import numpy as np
import pandas as pd
import yfinance as yf

# ── Configuration ─────────────────────────────────────────────────────────────
DEFAULT_TICKERS = ["TSLA", "SPY", "BND"]
TRAIN_END       = "2024-12-31"          # last date used during training
SEQ_LENGTH      = 60                    # must match train_models.py
MODELS_DIR      = os.path.join(os.path.dirname(__file__), "..", "models")
REPORTS_DIR     = os.path.join(os.path.dirname(__file__), "..", "reports")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _model_path(ticker: str)  -> str:
    return os.path.join(MODELS_DIR, f"{ticker}_lstm.keras")

def _scaler_path(ticker: str) -> str:
    return os.path.join(MODELS_DIR, f"{ticker}_scaler.pkl")

def _ready_path(ticker: str)  -> str:
    return os.path.join(MODELS_DIR, f"{ticker}.ready")

def _model_ready(ticker: str) -> bool:
    return (
        os.path.exists(_model_path(ticker))
        and os.path.exists(_scaler_path(ticker))
        and os.path.exists(_ready_path(ticker))
    )


def _download_oos(ticker: str, start: str) -> pd.Series:
    """Download Adj Close prices from *start* to today."""
    raw = yf.download(ticker, start=start, auto_adjust=False, progress=False)
    if raw.empty:
        raise ValueError(f"No out-of-sample data for {ticker} from {start}.")
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.droplevel(1)
    col = "Adj Close" if "Adj Close" in raw.columns else "Close"
    return raw[col].dropna().astype("float32")


# ── Metrics ───────────────────────────────────────────────────────────────────

def _metrics(actual: np.ndarray, predicted: np.ndarray) -> dict:
    """
    Compute regression and directional accuracy metrics.

    Returns
    -------
    dict with keys: mae, rmse, mape, dir_acc
        mae      : Mean Absolute Error (price units)
        rmse     : Root Mean Squared Error (price units)
        mape     : Mean Absolute Percentage Error (%)
        dir_acc  : Directional accuracy — fraction of days where the model
                   correctly predicted the sign of the next-day price move (%)
    """
    errors   = actual - predicted
    mae      = float(np.mean(np.abs(errors)))
    rmse     = float(np.sqrt(np.mean(errors ** 2)))
    # Avoid division by zero for zero-priced assets
    mape     = float(np.mean(np.abs(errors / np.where(actual != 0, actual, 1e-8))) * 100)

    # Directional accuracy: did the model predict the correct direction?
    actual_dir    = np.sign(np.diff(actual))
    predicted_dir = np.sign(np.diff(predicted))
    dir_acc = float(np.mean(actual_dir == predicted_dir) * 100)

    return {"mae": mae, "rmse": rmse, "mape": mape, "dir_acc": dir_acc}


# ── Walk-forward evaluation ───────────────────────────────────────────────────

def evaluate_lstm(ticker: str, oos_prices: pd.Series) -> tuple[dict, pd.DataFrame]:
    """
    Walk-forward evaluation of the LSTM model for *ticker*.

    At each step t (starting at index SEQ_LENGTH) we:
      - Feed prices[t-SEQ_LENGTH : t] into the model
      - Predict prices[t]
      - Compare to the actual prices[t]

    Returns (metrics_dict, predictions_df).
    """
    from tensorflow.keras.models import load_model  # lazy import

    model  = load_model(_model_path(ticker))
    scaler = joblib.load(_scaler_path(ticker))

    values = oos_prices.values.reshape(-1, 1)
    scaled = scaler.transform(values)

    actuals    = []
    preds      = []
    pred_dates = []

    for i in range(SEQ_LENGTH, len(scaled)):
        window = scaled[i - SEQ_LENGTH:i].reshape(1, SEQ_LENGTH, 1)
        pred_scaled = model.predict(window, verbose=0)[0, 0]
        pred_price  = float(scaler.inverse_transform([[pred_scaled]])[0, 0])

        actuals.append(float(values[i, 0]))
        preds.append(pred_price)
        pred_dates.append(oos_prices.index[i])

    actuals = np.array(actuals)
    preds   = np.array(preds)

    df = pd.DataFrame({
        "date":      pred_dates,
        "actual":    actuals,
        "predicted": preds,
        "error":     actuals - preds,
        "abs_error": np.abs(actuals - preds),
    })

    return _metrics(actuals, preds), df


def evaluate_mock(ticker: str, oos_prices: pd.Series) -> tuple[dict, pd.DataFrame]:
    """
    Baseline: naive persistence model (predict today's price = yesterday's price).
    This is the simplest possible benchmark — the LSTM should beat it.
    """
    values = oos_prices.values
    actuals = values[1:]
    preds   = values[:-1]          # yesterday's price as today's prediction
    dates   = oos_prices.index[1:]

    df = pd.DataFrame({
        "date":      dates,
        "actual":    actuals,
        "predicted": preds,
        "error":     actuals - preds,
        "abs_error": np.abs(actuals - preds),
    })

    return _metrics(actuals, preds), df


# ── Report ────────────────────────────────────────────────────────────────────

def _print_ticker_report(
    ticker: str,
    lstm_m: dict | None,
    mock_m: dict,
    oos_len: int,
    oos_start: str,
) -> None:
    print(f"\n  ── {ticker} ──────────────────────────────────────────────")
    print(f"  Out-of-sample period : {oos_start} → today  ({oos_len} trading days)")
    print()
    header = f"  {'Metric':<20}  {'LSTM':>10}  {'Naive baseline':>14}  {'LSTM better?':>12}"
    print(header)
    print(f"  {'-'*20}  {'-'*10}  {'-'*14}  {'-'*12}")

    metrics_cfg = [
        ("MAE  (price)",  "mae",     False),   # lower is better
        ("RMSE (price)",  "rmse",    False),
        ("MAPE (%)",      "mape",    False),
        ("Dir. Acc. (%)", "dir_acc", True),    # higher is better
    ]

    for label, key, higher_better in metrics_cfg:
        lstm_val = lstm_m[key] if lstm_m else float("nan")
        mock_val = mock_m[key]

        if lstm_m is None:
            better = "N/A (no model)"
        elif higher_better:
            better = "✓" if lstm_val > mock_val else "✗"
        else:
            better = "✓" if lstm_val < mock_val else "✗"

        lstm_str = f"{lstm_val:.4f}" if lstm_m else "  N/A"
        print(f"  {label:<20}  {lstm_str:>10}  {mock_val:>14.4f}  {better:>12}")


def _print_summary_table(results: list[dict]) -> None:
    print(f"\n{'='*60}")
    print("  Summary")
    print(f"{'='*60}")
    print(f"  {'Ticker':<8}  {'MAE':>8}  {'RMSE':>8}  {'MAPE%':>8}  {'DirAcc%':>8}  {'vs Naive':>10}")
    print(f"  {'-'*8}  {'-'*8}  {'-'*8}  {'-'*8}  {'-'*8}  {'-'*10}")
    for r in results:
        if r["lstm"] is None:
            print(f"  {r['ticker']:<8}  {'N/A':>8}  {'N/A':>8}  {'N/A':>8}  {'N/A':>8}  {'no model':>10}")
        else:
            m = r["lstm"]
            beats = r["lstm"]["mape"] < r["mock"]["mape"]
            print(
                f"  {r['ticker']:<8}  {m['mae']:>8.4f}  {m['rmse']:>8.4f}"
                f"  {m['mape']:>7.2f}%  {m['dir_acc']:>7.1f}%  {'✓ better' if beats else '✗ worse':>10}"
            )
    print()


# ── CLI ───────────────────────────────────────────────────────────────────────

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Out-of-sample LSTM model evaluation.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument(
        "--tickers", nargs="+", default=DEFAULT_TICKERS,
        metavar="TICKER",
        help="Tickers to evaluate.",
    )
    p.add_argument(
        "--start", default=None,
        help=(
            "Start of the out-of-sample window (YYYY-MM-DD). "
            f"Defaults to the day after TRAIN_END ({TRAIN_END})."
        ),
    )
    p.add_argument(
        "--no-lstm", action="store_true",
        help="Skip LSTM evaluation; show naive baseline only.",
    )
    p.add_argument(
        "--save-csv", action="store_true",
        help="Save per-ticker prediction DataFrames to reports/.",
    )
    return p.parse_args()


def main() -> None:
    args    = _parse_args()
    tickers = [t.upper() for t in args.tickers]
    oos_start = args.start or (
        pd.Timestamp(TRAIN_END) + pd.offsets.BDay(1)
    ).strftime("%Y-%m-%d")

    print(f"\n{'='*60}")
    print(f"  GMF Investments — Model Evaluator")
    print(f"  Out-of-sample start: {oos_start}")
    print(f"{'='*60}")

    all_results = []

    for ticker in tickers:
        print(f"\n  Processing {ticker} …")

        # ── Download OOS data ─────────────────────────────────────────────
        try:
            oos_prices = _download_oos(ticker, oos_start)
        except ValueError as exc:
            print(f"  ✗ {exc}", file=sys.stderr)
            all_results.append({"ticker": ticker, "lstm": None, "mock": {}})
            continue

        if len(oos_prices) <= SEQ_LENGTH:
            print(
                f"  ✗ Only {len(oos_prices)} OOS rows for {ticker} "
                f"(need > {SEQ_LENGTH}). Skipping.",
                file=sys.stderr,
            )
            all_results.append({"ticker": ticker, "lstm": None, "mock": {}})
            continue

        # ── Naive baseline ────────────────────────────────────────────────
        mock_metrics, mock_df = evaluate_mock(ticker, oos_prices)

        # ── LSTM evaluation ───────────────────────────────────────────────
        lstm_metrics = None
        lstm_df      = None

        if not args.no_lstm:
            if not _model_ready(ticker):
                print(f"  ⚠  No trained model found for {ticker} — skipping LSTM eval.")
            else:
                try:
                    lstm_metrics, lstm_df = evaluate_lstm(ticker, oos_prices)
                except Exception as exc:
                    print(f"  ✗ LSTM evaluation failed for {ticker}: {exc}", file=sys.stderr)

        _print_ticker_report(ticker, lstm_metrics, mock_metrics, len(oos_prices), oos_start)

        # ── Save CSVs ─────────────────────────────────────────────────────
        if args.save_csv:
            os.makedirs(REPORTS_DIR, exist_ok=True)
            if lstm_df is not None:
                path = os.path.join(REPORTS_DIR, f"{ticker}_lstm_predictions.csv")
                lstm_df.to_csv(path, index=False)
                print(f"  ✓ Saved LSTM predictions → {path}")
            mock_path = os.path.join(REPORTS_DIR, f"{ticker}_naive_predictions.csv")
            mock_df.to_csv(mock_path, index=False)
            print(f"  ✓ Saved naive predictions → {mock_path}")

        all_results.append({"ticker": ticker, "lstm": lstm_metrics, "mock": mock_metrics})

    _print_summary_table(all_results)


if __name__ == "__main__":
    main()
