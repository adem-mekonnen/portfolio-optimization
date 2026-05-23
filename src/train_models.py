"""
Train LSTM models for stock price forecasting and save them to the models/ directory.

Usage:
    python -m src.train_models

This script trains an LSTM model for each configured ticker using historical
Adjusted Close price data. The trained model (.keras) and its MinMaxScaler
(.pkl) are saved to the models/ directory so that model_inference.py can
load and use them for real predictions.

Save protocol
-------------
Files are written atomically using the same three-step protocol as retrain.py:
  1. Write model + scaler to a temp directory.
  2. Move both into models/ (replacing any stale files).
  3. Write the {ticker}.ready marker last.

model_inference._model_exists() requires all three files to be present before
it will use the LSTM path.  Writing the marker last ensures a partial save
(e.g. process killed mid-write) never leaves a mismatched model+scaler pair
visible to inference.
"""

import json
import os
import shutil
import tempfile
from datetime import datetime, timezone

import joblib
import numpy as np
import pandas as pd
import yfinance as yf
from sklearn.preprocessing import MinMaxScaler
from tensorflow.keras.layers import LSTM, Dense, Dropout, Input
from tensorflow.keras.models import Sequential

# ── Configuration ────────────────────────────────────────────────────────────
TICKERS        = ["TSLA", "SPY", "BND"]
TRAIN_START    = "2015-01-01"
TRAIN_END      = "2024-12-31"   # keep 2025-onwards as out-of-sample
SEQ_LENGTH     = 60             # look-back window (trading days)
EPOCHS         = 20
BATCH_SIZE     = 32
MODELS_DIR     = os.path.join(os.path.dirname(__file__), "..", "models")
META_FILE      = os.path.join(MODELS_DIR, "retrain_meta.json")


# ── Path helpers ──────────────────────────────────────────────────────────────

def _model_path(ticker: str) -> str:
    return os.path.join(MODELS_DIR, f"{ticker}_lstm.keras")

def _scaler_path(ticker: str) -> str:
    return os.path.join(MODELS_DIR, f"{ticker}_scaler.pkl")

def _ready_path(ticker: str) -> str:
    """
    Path to the '.ready' marker file.

    Written last, after both the model and scaler are in place.
    model_inference._model_exists() requires this file before trusting the pair.
    """
    return os.path.join(MODELS_DIR, f"{ticker}.ready")


# ── Meta helpers ──────────────────────────────────────────────────────────────

def _save_meta(ticker: str, trained_through: str) -> None:
    """
    Record the last date the model was trained through in retrain_meta.json.

    retrain.py reads this on its first run to decide whether to fine-tune or
    retrain from scratch.  Writing it here means the weekly scheduler will
    correctly fine-tune rather than doing a redundant full retrain.
    """
    os.makedirs(MODELS_DIR, exist_ok=True)
    meta: dict = {}
    try:
        with open(META_FILE, "r", encoding="utf-8") as f:
            meta = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    meta[ticker] = {
        "trained_through": trained_through,
        "retrained_at":    datetime.now(tz=timezone.utc).isoformat(),
    }
    # Atomic write — never leave a half-written JSON file
    tmp = META_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
    os.replace(tmp, META_FILE)


def create_sequences(data: np.ndarray, seq_length: int = SEQ_LENGTH):
    """
    Slide a window of `seq_length` over `data` to produce (X, y) pairs.

    Parameters
    ----------
    data       : 2-D array of shape (n_samples, 1), already scaled.
    seq_length : number of time steps in each input sequence.

    Returns
    -------
    X : shape (n_samples - seq_length, seq_length, 1)
    y : shape (n_samples - seq_length,)
    """
    X, y = [], []
    for i in range(seq_length, len(data)):
        X.append(data[i - seq_length:i, 0])
        y.append(data[i, 0])
    return np.array(X), np.array(y)


def build_lstm(seq_length: int = SEQ_LENGTH) -> Sequential:
    """Return a compiled LSTM model."""
    model = Sequential([
        Input(shape=(seq_length, 1)),
        LSTM(units=50, return_sequences=True),
        Dropout(0.2),
        LSTM(units=50, return_sequences=False),
        Dropout(0.2),
        Dense(units=25),
        Dense(units=1),
    ])
    model.compile(optimizer="adam", loss="mean_squared_error")
    return model


def train_and_save_lstm(ticker: str) -> None:
    """
    Download historical data for *ticker*, train an LSTM, and persist both
    the model and its MinMaxScaler to disk.
    """
    print(f"\n{'='*60}")
    print(f"  Training LSTM for {ticker}")
    print(f"{'='*60}")

    # ── 1. Fetch data ─────────────────────────────────────────────────────
    print(f"  Downloading {ticker} data ({TRAIN_START} → {TRAIN_END}) …")
    raw = yf.download(ticker, start=TRAIN_START, end=TRAIN_END, auto_adjust=False, progress=False)

    if raw.empty:
        raise ValueError(f"No data returned for {ticker}.")

    # Flatten MultiIndex columns produced by yfinance
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.droplevel(level=1)
    raw.columns = [str(c).strip() for c in raw.columns]

    price_col = "Adj Close" if "Adj Close" in raw.columns else "Close"
    prices = raw[[price_col]].copy().astype("float32")
    prices = prices.dropna()
    print(f"  {len(prices)} trading days loaded.")

    # ── 2. Scale ──────────────────────────────────────────────────────────
    scaler = MinMaxScaler(feature_range=(0, 1))
    scaled = scaler.fit_transform(prices.values)

    # ── 3. Build sequences ────────────────────────────────────────────────
    X_train, y_train = create_sequences(scaled, SEQ_LENGTH)
    X_train = X_train.reshape(X_train.shape[0], X_train.shape[1], 1)
    print(f"  Training sequences: {X_train.shape[0]}")

    # ── 4. Train ──────────────────────────────────────────────────────────
    model = build_lstm(SEQ_LENGTH)
    print(f"  Fitting model (epochs={EPOCHS}, batch={BATCH_SIZE}) …")
    model.fit(
        X_train, y_train,
        epochs=EPOCHS,
        batch_size=BATCH_SIZE,
        verbose=1,
    )

    # ── 5. Atomic save ────────────────────────────────────────────────────
    #
    # Mirrors the protocol in retrain.py exactly:
    #
    #   Step A  Remove the .ready marker so inference stops trusting the
    #           current pair while we are replacing it.
    #   Step B  Write both files to an isolated temp directory inside
    #           models/ so a crash here never corrupts the live files.
    #   Step C  Move the model file into place.
    #   Step D  Move the scaler file into place.
    #   Step E  Write the .ready marker — only reached when C and D both
    #           succeeded.  Inference resumes trusting the new pair.
    #
    os.makedirs(MODELS_DIR, exist_ok=True)

    ready = _ready_path(ticker)

    # Step A — invalidate any existing pair before touching live files
    if os.path.exists(ready):
        os.remove(ready)

    try:
        # Step B — write to an isolated temp directory
        with tempfile.TemporaryDirectory(dir=MODELS_DIR) as tmp_dir:
            tmp_model  = os.path.join(tmp_dir, "model.keras")
            tmp_scaler = os.path.join(tmp_dir, "scaler.pkl")

            model.save(tmp_model)
            joblib.dump(scaler, tmp_scaler)

            # Steps C & D — promote both files atomically
            shutil.move(tmp_model,  _model_path(ticker))
            shutil.move(tmp_scaler, _scaler_path(ticker))

        # Step E — mark the pair as complete and trustworthy
        with open(ready, "w", encoding="utf-8") as f:
            f.write(datetime.now(tz=timezone.utc).isoformat())

        print(f"  ✓ Model  saved → {_model_path(ticker)}")
        print(f"  ✓ Scaler saved → {_scaler_path(ticker)}")
        print(f"  ✓ Ready marker → {ready}")

    except Exception as exc:
        # Leave the marker absent so inference falls back to the mock forecast.
        print(f"  ✗ Save failed for {ticker}: {exc}")
        print(f"    .ready marker NOT written — inference will use mock forecast.")
        raise

    # ── 6. Write retrain metadata ─────────────────────────────────────────
    # Record TRAIN_END as the training cut-off so retrain.py knows to
    # fine-tune from that date rather than doing a full retrain from scratch.
    trained_through = prices.index[-1].strftime("%Y-%m-%d")
    _save_meta(ticker, trained_through)
    print(f"  ✓ Meta   saved → trained_through={trained_through}")


if __name__ == "__main__":
    for ticker in TICKERS:
        try:
            train_and_save_lstm(ticker)
        except Exception as exc:
            print(f"  ✗ Error training {ticker}: {exc}")

    print("\nAll done.")
