import logging
import os
import re
from contextlib import asynccontextmanager
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .backtester import RebalanceFreq, run_backtest
from .cache_manager import get_status as cache_status, invalidate as invalidate_cache
from .data_fetcher import fetch_data
from .model_inference import get_forecast
from .portfolio_optimizer import optimize_portfolio
from .retrain import TICKERS as TRACKED_TICKERS, _load_meta as load_retrain_meta, retrain_all
from .scheduler import get_next_runs, start_scheduler, stop_scheduler
from .schemas import (
    AssetInfoResponse,
    BacktestRequest,
    BacktestResponse,
    DataStatusResponse,
    ForecastResponse,
    OptimizeRequest,
    OptimizeResponse,
)

logger = logging.getLogger(__name__)

# ── Ticker validation ─────────────────────────────────────────────────────────
# Allows 1–5 uppercase letters, optionally followed by a dot and 1–2 letters
# (covers US equities like TSLA, ETFs like SPY, and some international tickers
# like BRK.B).
_TICKER_RE = re.compile(r'^[A-Z]{1,5}(\.[A-Z]{1,2})?$')


def _validate_ticker(ticker: str) -> str:
    """
    Normalise and validate a ticker symbol.

    Returns the uppercased ticker if valid.
    Raises HTTPException(400) if the format is invalid.
    """
    t = ticker.strip().upper()
    if not _TICKER_RE.match(t):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid ticker format: {ticker!r}. "
                   "Expected 1–5 uppercase letters (e.g. TSLA, SPY, BRK.B).",
        )
    return t


# ── CORS ──────────────────────────────────────────────────────────────────────
# Allowed origins are read from the CORS_ORIGINS environment variable so the
# same image works in dev, staging, and production without a rebuild.
#
# Set CORS_ORIGINS as a comma-separated list, e.g.:
#   CORS_ORIGINS=http://localhost,http://localhost:5173,https://app.example.com
#
# If the variable is not set, the default covers local development only.
_raw_origins = os.getenv("CORS_ORIGINS", "*")
ALLOWED_ORIGINS: list[str] = (
    ["*"] if _raw_origins.strip() == "*"
    else [o.strip() for o in _raw_origins.split(",") if o.strip()]
)


# ── App lifespan (startup / shutdown) ─────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start the background scheduler on startup; stop it on shutdown."""
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(title="GMF Investments API", version="1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Accept"],
)


# ── Forecast ──────────────────────────────────────────────────────────────────

@app.get("/forecast/{ticker}", response_model=ForecastResponse)
async def forecast(ticker: str):
    """
    Generate a 30-day price forecast for *ticker*.

    Uses the trained LSTM model when available; falls back to a
    volatility-based simulation otherwise.

    Raises
    ------
    400  Invalid ticker format.
    500  Model inference failed unexpectedly.
    """
    ticker = _validate_ticker(ticker)
    try:
        return get_forecast(ticker)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Forecast error for %s: %s", ticker, e, exc_info=True)
        raise HTTPException(status_code=500, detail="Forecast generation failed.")


# ── Portfolio optimisation ────────────────────────────────────────────────────

@app.post("/optimize", response_model=OptimizeResponse)
async def optimize(request: OptimizeRequest):
    """
    Compute the Max Sharpe Ratio portfolio weights for the given tickers.

    Raises
    ------
    400  Invalid ticker format or insufficient data.
    500  Optimisation failed unexpectedly.
    """
    try:
        tickers = [_validate_ticker(t) for t in request.tickers]
        return optimize_portfolio(tickers)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Optimisation error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Portfolio optimisation failed.")


# ── Asset info ────────────────────────────────────────────────────────────────

@app.get("/asset_info/{ticker}", response_model=AssetInfoResponse)
async def asset_info(ticker: str):
    """
    Return the latest price, daily change, and sentiment signal for *ticker*.

    Sentiment is determined by comparing the current price to the 20-day SMA:
    price > SMA-20 → Bullish, otherwise → Bearish.

    Raises
    ------
    400  Invalid ticker format or insufficient price history.
    500  Data fetch failed unexpectedly.
    """
    ticker = _validate_ticker(ticker)
    try:
        start_date = (datetime.now() - timedelta(days=60)).strftime("%Y-%m-%d")
        df = fetch_data(ticker, start=start_date)

        if df is None or df.empty:
            raise ValueError(f"No price data available for {ticker}.")

        if ticker not in df.columns:
            raise ValueError(
                f"Ticker {ticker!r} not found in the returned data. "
                "The symbol may be delisted or unsupported."
            )

        prices = df[ticker].dropna()
        if len(prices) < 2:
            raise ValueError(
                f"Not enough price history for {ticker} "
                f"(got {len(prices)} rows, need at least 2)."
            )

        current_price = float(prices.iloc[-1])
        prev_price    = float(prices.iloc[-2])
        change_pct    = ((current_price - prev_price) / prev_price) * 100
        sma_20        = float(prices.tail(20).mean())
        sentiment     = "Bullish" if current_price > sma_20 else "Bearish"

        return {
            "ticker":         ticker,
            "price":          round(current_price, 2),
            "change_percent": round(change_pct, 2),
            "sentiment":      sentiment,
        }
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Asset info error for %s: %s", ticker, e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch asset data.")


# ── Backtest ──────────────────────────────────────────────────────────────────

_VALID_FREQS = {"daily", "weekly", "monthly", "quarterly"}


@app.post("/backtest", response_model=BacktestResponse)
async def backtest(request: BacktestRequest):
    """
    Run a 1-year historical backtest with configurable transaction costs.

    Cost parameters
    ---------------
    commission_pct  : one-way commission as a fraction of traded notional
                      (default 0.001 = 0.10 %).
    slippage_pct    : one-way slippage as a fraction of traded notional
                      (default 0.0005 = 0.05 %).
    rebalance_freq  : daily | weekly | monthly | quarterly  (default monthly).

    The response includes both gross_return (before costs) and total_return
    (after costs) so the cost_drag is transparent.

    Raises
    ------
    400  Invalid ticker, invalid rebalance frequency, or insufficient data.
    500  Backtest computation failed unexpectedly.
    """
    try:
        tickers = [_validate_ticker(t) for t in request.tickers]

        freq = request.rebalance_freq.lower()
        if freq not in _VALID_FREQS:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid rebalance_freq {freq!r}. "
                       f"Must be one of: {sorted(_VALID_FREQS)}.",
            )

        start_date = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
        df = fetch_data(tickers, start=start_date)

        if df is None or df.empty:
            raise ValueError("No price data available for the given tickers.")

        df = df.dropna()
        if isinstance(df, pd.Series):
            df = pd.DataFrame({tickers[0]: df})

        result = run_backtest(
            prices             = df,
            target_weights     = dict(request.weights),
            initial_investment = request.initial_investment,
            commission_pct     = request.commission_pct,
            slippage_pct       = request.slippage_pct,
            rebalance_freq     = freq,  # type: ignore[arg-type]
        )
        return result

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Backtest error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Backtest computation failed.")


# ── Data / scheduler status ───────────────────────────────────────────────────

@app.get("/data/status", response_model=DataStatusResponse)
async def data_status():
    """
    Return the current state of the price cache and the background scheduler.

    Useful for monitoring dashboards and the frontend "Models Active" badge.
    """
    try:
        cs   = cache_status()
        jobs = get_next_runs()
        meta = load_retrain_meta()
        return {
            "cache":          cs["entries"],
            "scheduled_jobs": jobs,
            "retrain_meta":   meta,
        }
    except Exception as e:
        logger.error("Status error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve status.")


# ── Manual trigger endpoints ──────────────────────────────────────────────────

@app.post("/data/refresh-cache")
async def refresh_cache(background_tasks: BackgroundTasks):
    """
    Manually invalidate the price cache for all tracked tickers.

    The next API call for each ticker will re-fetch fresh data from yfinance.
    Runs in the background so the response is immediate.
    """
    background_tasks.add_task(invalidate_cache, tickers=TRACKED_TICKERS)
    return {"message": f"Cache invalidation queued for {TRACKED_TICKERS}."}


@app.post("/data/retrain")
async def trigger_retrain(background_tasks: BackgroundTasks):
    """
    Manually trigger an incremental LSTM model retrain for all tracked tickers.

    Runs in the background — check /data/status for completion.
    This can take several minutes on CPU.
    """
    background_tasks.add_task(retrain_all)
    return {"message": f"Retrain queued for {TRACKED_TICKERS}. Check /data/status for progress."}
