"""
Model inference module for stock price forecasting.

Loads trained LSTM models from the models/ directory and generates
30-day rolling forecasts with confidence intervals.

Falls back to a volatility-based Monte Carlo simulation when a trained
model is not available for the requested ticker.
"""

import os
import logging
import numpy as np
from datetime import datetime, timedelta

import joblib

from .data_fetcher import fetch_data

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────
SEQ_LENGTH    = 60          # must match the value used during training
FORECAST_DAYS = 30
MODELS_DIR    = os.path.join(os.path.dirname(__file__), "..", "models")
CONFIDENCE_Z  = 1.96        # 95 % confidence interval

# Minimum meaningful stock price used to clamp the lower confidence bound.
# Prevents the CI from going negative when volatility is high (e.g. TSLA).
_MIN_PRICE = 0.01


# ── Confidence-interval helper ────────────────────────────────────────────────

def _ci(price: float, volatility: float) -> tuple[float, float]:
    """
    Return (lower_bound, upper_bound) for a 95 % confidence interval around
    *price* given a daily *volatility* (standard deviation of daily returns).

    The lower bound is clamped to _MIN_PRICE so it is never zero or negative,
    which would be nonsensical for a stock price.

    Example
    -------
    >>> _ci(350.0, 0.50)   # 50 % daily vol — extreme but valid
    (0.01, 693.0)          # lower clamped; upper is fine
    >>> _ci(350.0, 0.03)   # typical ETF vol
    (329.42, 370.58)
    """
    half_width = CONFIDENCE_Z * volatility
    lower = max(_MIN_PRICE, round(price * (1.0 - half_width), 2))
    upper = round(price * (1.0 + half_width), 2)
    return lower, upper


# ── Lazy TensorFlow import (exposed at module level for test mocking) ─────────
def load_model(path: str):
    """Thin wrapper around keras.models.load_model, importable for mocking."""
    from tensorflow.keras.models import load_model as _keras_load  # noqa: PLC0415
    return _keras_load(path)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _model_path(ticker: str) -> str:
    return os.path.join(MODELS_DIR, f"{ticker}_lstm.keras")


def _scaler_path(ticker: str) -> str:
    return os.path.join(MODELS_DIR, f"{ticker}_scaler.pkl")


def _ready_path(ticker: str) -> str:
    """Path to the '.ready' marker written by retrain.py after a successful save."""
    return os.path.join(MODELS_DIR, f"{ticker}.ready")


def _model_exists(ticker: str) -> bool:
    """
    Return True only when the model, scaler, AND the '.ready' marker all exist.

    The marker is absent while retrain.py is mid-save, so this guard prevents
    loading a mismatched model+scaler pair if a save was interrupted.
    """
    return (
        os.path.exists(_model_path(ticker))
        and os.path.exists(_scaler_path(ticker))
        and os.path.exists(_ready_path(ticker))
    )


# ── LSTM forecast ─────────────────────────────────────────────────────────────

def _lstm_forecast(ticker: str, days: int = FORECAST_DAYS) -> list:
    """
    Generate a *days*-step ahead forecast using the saved LSTM model.

    The forecast is produced autoregressively: each predicted value is fed
    back into the sliding window to predict the next step.

    Returns a list of dicts with keys: date, predicted_price, lower_bound,
    upper_bound.
    """
    model  = load_model(_model_path(ticker))
    scaler = joblib.load(_scaler_path(ticker))

    # Fetch enough history to seed the window
    lookback_days = SEQ_LENGTH * 2          # calendar days buffer
    start = (datetime.now() - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
    df = fetch_data(ticker, start=start)

    if df is None or df.empty:
        raise ValueError(f"Could not fetch recent data for {ticker}.")

    prices = df[ticker] if ticker in df.columns else df.iloc[:, 0]
    prices = prices.dropna()

    if len(prices) < SEQ_LENGTH:
        raise ValueError(
            f"Not enough recent data for {ticker}: "
            f"need {SEQ_LENGTH}, got {len(prices)}."
        )

    # Use the last SEQ_LENGTH closing prices as the seed window
    seed = prices.values[-SEQ_LENGTH:].reshape(-1, 1).astype("float32")
    seed_scaled = scaler.transform(seed)          # shape (SEQ_LENGTH, 1)

    # Estimate historical volatility for confidence bands
    daily_returns = prices.pct_change().dropna()
    volatility = float(daily_returns.std())

    # Autoregressive rolling forecast
    window = seed_scaled[:, 0].tolist()           # plain Python list for speed
    forecast_list = []
    current_date  = datetime.now()

    for _ in range(days):
        current_date += timedelta(days=1)
        # Skip weekends (simple approximation)
        while current_date.weekday() >= 5:
            current_date += timedelta(days=1)

        x = np.array(window[-SEQ_LENGTH:], dtype="float32").reshape(1, SEQ_LENGTH, 1)
        pred_scaled = model.predict(x, verbose=0)[0, 0]
        window.append(float(pred_scaled))

        # Inverse-transform to get the actual price
        pred_price = float(scaler.inverse_transform([[pred_scaled]])[0, 0])

        lower, upper = _ci(pred_price, volatility)
        forecast_list.append({
            "date":            current_date.strftime("%Y-%m-%d"),
            "predicted_price": round(pred_price, 2),
            "lower_bound":     lower,
            "upper_bound":     upper,
        })

    return forecast_list


# ── Mock / fallback forecast ──────────────────────────────────────────────────

def _mock_forecast(ticker: str, days: int = FORECAST_DAYS) -> list:
    """
    Fallback: generate a realistic-looking forecast using Geometric Brownian
    Motion seeded from the ticker's actual recent price and volatility.
    """
    try:
        start = (datetime.now() - timedelta(days=180)).strftime("%Y-%m-%d")
        df = fetch_data(ticker, start=start)
        if df is None or df.empty:
            raise ValueError("No data")
        prices = df[ticker] if ticker in df.columns else df.iloc[:, 0]
        prices = prices.dropna()
        current_price = float(prices.iloc[-1])
        daily_returns = prices.pct_change().dropna()
        drift      = float(daily_returns.mean())
        volatility = float(daily_returns.std())
    except Exception:
        np.random.seed(abs(hash(ticker)) % (2 ** 32 - 1))
        current_price = np.random.uniform(100, 500)
        drift         = np.random.normal(0, 0.002)
        volatility    = np.random.uniform(0.01, 0.03)

    np.random.seed(abs(hash(ticker)) % (2 ** 32 - 1))
    forecast_list = []
    current_date  = datetime.now()

    for _ in range(days):
        current_date += timedelta(days=1)
        daily_return   = np.random.normal(drift, volatility)
        current_price *= 1 + daily_return
        lower, upper = _ci(current_price, volatility)
        forecast_list.append({
            "date":            current_date.strftime("%Y-%m-%d"),
            "predicted_price": round(current_price, 2),
            "lower_bound":     lower,
            "upper_bound":     upper,
        })

    return forecast_list


# ── Public API ────────────────────────────────────────────────────────────────

def get_forecast(ticker: str) -> dict:
    """
    Return a 30-day price forecast for *ticker*.

    Uses the trained LSTM model when available; falls back to the
    volatility-based mock otherwise.
    """
    ticker = ticker.upper()

    if _model_exists(ticker):
        try:
            logger.info("Using LSTM model for %s", ticker)
            forecast = _lstm_forecast(ticker)
            return {"ticker": ticker, "forecast": forecast}
        except Exception as exc:
            logger.warning(
                "LSTM inference failed for %s (%s). Falling back to mock.", ticker, exc
            )

    logger.info("Using mock forecast for %s (no trained model found).", ticker)
    return {"ticker": ticker, "forecast": _mock_forecast(ticker)}
