"""
Incremental LSTM retraining module.

Strategy
--------
Rather than training from scratch every week (which takes ~10 min per ticker),
we use a two-phase approach:

1. **Data extension** — download all data from TRAIN_START up to today.
2. **Fine-tuning** — load the existing model and run a small number of
   additional epochs on the *new* data only (the rows added since the last
   training cut-off).  This is fast (~30 s per ticker on CPU) and prevents
   catastrophic forgetting of the original training.

If no existing model is found (first run), a full training pass is performed
instead (same as train_models.py).

Atomic saves
------------
Models are written to a temporary path first, then renamed into place so the
inference path never reads a partially-written file.

Usage
-----
    # Run manually:
    python -m src.retrain

    # Or call from the scheduler:
    from src.retrain import retrain_all
    retrain_all()
"""

import logging
import os
import shutil
import tempfile
from datetime import datetime, timezone

import joblib
import numpy as np
import pandas as pd
import yfinance as yf
from sklearn.preprocessing import MinMaxScaler

logger = logging.getLogger(__name__)

# ── Lazy TensorFlow import (exposed at module level for test mocking) ─────────
def load_model(path: str):
    """Thin wrapper around keras load_model, importable for mocking."""
    from tensorflow.keras.models import load_model as _keras_load  # noqa: PLC0415
    return _keras_load(path)

# ── Configuration ─────────────────────────────────────────────────────────────
TICKERS        = ["TSLA", "SPY", "BND"]
TRAIN_START    = "2015-01-01"
SEQ_LENGTH     = 60
FINETUNE_EPOCHS = 5    # epochs used when fine-tuning an existing model
FULL_EPOCHS     = 20   # epochs used when training from scratch
BATCH_SIZE      = 32

MODELS_DIR = os.path.join(os.path.dirname(__file__), "..", "models")
META_FILE  = os.path.join(MODELS_DIR, "retrain_meta.json")  # tracks last retrain time


# ── Helpers ───────────────────────────────────────────────────────────────────

def _model_path(ticker: str) -> str:
    return os.path.join(MODELS_DIR, f"{ticker}_lstm.keras")


def _scaler_path(ticker: str) -> str:
    return os.path.join(MODELS_DIR, f"{ticker}_scaler.pkl")


def _ready_path(ticker: str) -> str:
    """
    Path to the '.ready' marker file for *ticker*.

    This file is written **last**, after both the model and scaler have been
    successfully moved into place.  The inference path checks for its existence
    before loading the pair, so a partial save (model written, scaler failed)
    is never used.
    """
    return os.path.join(MODELS_DIR, f"{ticker}.ready")


def _model_exists(ticker: str) -> bool:
    """
    Return True only when the model, scaler, AND the '.ready' marker all exist.

    The marker is absent during a save-in-progress, so this guard prevents
    the inference path from loading a mismatched model+scaler pair.
    """
    return (
        os.path.exists(_model_path(ticker))
        and os.path.exists(_scaler_path(ticker))
        and os.path.exists(_ready_path(ticker))
    )


def _download_prices(ticker: str, start: str) -> pd.Series:
    """Download Adj Close prices for *ticker* from *start* to today."""
    today = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
    raw = yf.download(ticker, start=start, end=today, auto_adjust=False, progress=False)
    if raw.empty:
        raise ValueError(f"No data returned for {ticker}.")
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.droplevel(level=1)
    raw.columns = [str(c).strip() for c in raw.columns]
    col = "Adj Close" if "Adj Close" in raw.columns else "Close"
    return raw[col].dropna().astype("float32")


def _create_sequences(data: np.ndarray, seq_length: int = SEQ_LENGTH):
    X, y = [], []
    for i in range(seq_length, len(data)):
        X.append(data[i - seq_length:i, 0])
        y.append(data[i, 0])
    return np.array(X), np.array(y)


def _build_lstm(seq_length: int = SEQ_LENGTH):
    from tensorflow.keras.models import Sequential          # noqa: PLC0415
    from tensorflow.keras.layers import LSTM, Dense, Dropout, Input  # noqa: PLC0415
    model = Sequential([
        Input(shape=(seq_length, 1)),
        LSTM(50, return_sequences=True),
        Dropout(0.2),
        LSTM(50, return_sequences=False),
        Dropout(0.2),
        Dense(25),
        Dense(1),
    ])
    model.compile(optimizer="adam", loss="mean_squared_error")
    return model


def _save_meta(ticker: str, trained_through: str) -> None:
    """Record the date up to which a ticker's model has been trained."""
    import json
    os.makedirs(MODELS_DIR, exist_ok=True)
    meta: dict = {}
    try:
        with open(META_FILE, "r", encoding="utf-8") as f:
            meta = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    meta[ticker] = {
        "trained_through": trained_through,
        "retrained_at": datetime.now(tz=timezone.utc).isoformat(),
    }
    tmp = META_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
    os.replace(tmp, META_FILE)


def _load_meta() -> dict:
    import json
    try:
        with open(META_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


# ── Core retraining logic ─────────────────────────────────────────────────────

def retrain_ticker(ticker: str) -> None:
    """
    Retrain (or fine-tune) the LSTM model for *ticker*.

    - If no model exists → full training pass (FULL_EPOCHS).
    - If a model exists  → fine-tune on new data only (FINETUNE_EPOCHS).
    """
    ticker = ticker.upper()
    logger.info("=== Retraining %s ===", ticker)

    # ── 1. Download all data up to today ─────────────────────────────────
    prices = _download_prices(ticker, TRAIN_START)
    logger.info("%s: %d trading days loaded (up to %s).", ticker, len(prices), prices.index[-1].date())

    # ── 2. Fit / update scaler ────────────────────────────────────────────
    # Always refit the scaler on the full dataset so it covers the new price range.
    scaler = MinMaxScaler(feature_range=(0, 1))
    scaled = scaler.fit_transform(prices.values.reshape(-1, 1))

    # ── 3. Decide: fine-tune or full train ────────────────────────────────
    if _model_exists(ticker):
        meta = _load_meta()
        ticker_meta = meta.get(ticker, {})
        last_trained_through = ticker_meta.get("trained_through")

        if last_trained_through:
            # Only train on rows after the last training cut-off
            cutoff = pd.Timestamp(last_trained_through)
            new_prices = prices[prices.index > cutoff]
            if len(new_prices) < SEQ_LENGTH + 1:
                logger.info("%s: fewer than %d new rows since last retrain — skipping.", ticker, SEQ_LENGTH + 1)
                return
            # We need SEQ_LENGTH rows of context before the new data
            context_start = prices.index.get_loc(new_prices.index[0]) - SEQ_LENGTH
            context_start = max(context_start, 0)
            finetune_prices = prices.iloc[context_start:]
            finetune_scaled = scaler.transform(finetune_prices.values.reshape(-1, 1))
            X, y = _create_sequences(finetune_scaled, SEQ_LENGTH)
        else:
            # Model exists but no meta — retrain on full dataset
            X, y = _create_sequences(scaled, SEQ_LENGTH)

        X = X.reshape(X.shape[0], X.shape[1], 1)
        logger.info("%s: fine-tuning on %d sequences (%d epochs).", ticker, len(X), FINETUNE_EPOCHS)

        model = load_model(_model_path(ticker))
        model.fit(X, y, epochs=FINETUNE_EPOCHS, batch_size=BATCH_SIZE, verbose=0)
        epochs_used = FINETUNE_EPOCHS

    else:
        # No existing model — full training pass
        X, y = _create_sequences(scaled, SEQ_LENGTH)
        X = X.reshape(X.shape[0], X.shape[1], 1)
        logger.info("%s: full training on %d sequences (%d epochs).", ticker, len(X), FULL_EPOCHS)

        model = _build_lstm(SEQ_LENGTH)
        model.fit(X, y, epochs=FULL_EPOCHS, batch_size=BATCH_SIZE, verbose=0)
        epochs_used = FULL_EPOCHS

    # ── 4. Atomic save ────────────────────────────────────────────────────
    #
    # Safety protocol — prevents a mismatched model+scaler pair from ever
    # being visible to the inference path:
    #
    #   Step A  Remove the .ready marker so inference stops trusting the
    #           current pair while we are replacing it.
    #   Step B  Write both new files to a temp directory (isolated from the
    #           live models/ directory so a crash here leaves the old pair
    #           intact).
    #   Step C  Move the model file into place.
    #   Step D  Move the scaler file into place.
    #   Step E  Write the .ready marker — only reached if C and D both
    #           succeeded.  Inference resumes trusting the new pair.
    #
    # If the process crashes between C and D, the old scaler is still in
    # place (overwritten by D only if D succeeds), so the pair is still
    # consistent.  If it crashes between D and E, the marker is absent and
    # inference falls back to the mock forecast until the next retrain run
    # completes successfully.
    #
    os.makedirs(MODELS_DIR, exist_ok=True)

    ready = _ready_path(ticker)

    # Step A — invalidate the current pair before touching any live file
    if os.path.exists(ready):
        os.remove(ready)
        logger.debug("%s: .ready marker removed — save in progress.", ticker)

    try:
        # Step B — write to an isolated temp directory
        with tempfile.TemporaryDirectory(dir=MODELS_DIR) as tmp_dir:
            tmp_model  = os.path.join(tmp_dir, "model.keras")
            tmp_scaler = os.path.join(tmp_dir, "scaler.pkl")

            model.save(tmp_model)
            joblib.dump(scaler, tmp_scaler)

            # Steps C & D — promote both files
            shutil.move(tmp_model,  _model_path(ticker))
            shutil.move(tmp_scaler, _scaler_path(ticker))

        # Step E — mark the pair as complete and trustworthy
        with open(ready, "w", encoding="utf-8") as f:
            f.write(datetime.now(tz=timezone.utc).isoformat())

        logger.debug("%s: .ready marker written — save complete.", ticker)

    except Exception:
        # Leave the marker absent so inference falls back to mock forecast.
        logger.error(
            "%s: save failed — .ready marker NOT written. "
            "Inference will use mock forecast until next successful retrain.",
            ticker,
        )
        raise

    trained_through = prices.index[-1].strftime("%Y-%m-%d")
    _save_meta(ticker, trained_through)

    logger.info(
        "%s: saved (epochs=%d, trained_through=%s).",
        ticker, epochs_used, trained_through,
    )


def retrain_all(tickers: list[str] | None = None) -> dict:
    """
    Retrain models for all (or specified) tickers.

    Returns a summary dict: {ticker: "ok" | "skipped" | "error: <msg>"}.
    """
    targets = [t.upper() for t in (tickers or TICKERS)]
    results: dict[str, str] = {}

    for ticker in targets:
        try:
            retrain_ticker(ticker)
            results[ticker] = "ok"
        except Exception as exc:
            logger.error("Retrain failed for %s: %s", ticker, exc, exc_info=True)
            results[ticker] = f"error: {exc}"

    logger.info("Retrain complete: %s", results)
    return results


# ── CLI entry point ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    retrain_all()
