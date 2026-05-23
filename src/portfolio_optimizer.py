import logging

import numpy as np
from joblib import Memory
from pypfopt import expected_returns, risk_models
from pypfopt.efficient_frontier import EfficientFrontier

from .data_fetcher import fetch_data

logger  = logging.getLogger(__name__)
memory  = Memory(".cache", verbose=0)

# ── Cache versioning ──────────────────────────────────────────────────────────
# joblib derives the cache key from the function's bytecode hash AND its
# arguments.  When the return shape changes (e.g. new fields added to the
# response dict) any on-disk entry from before the change will be returned
# as-is, missing the new fields and causing KeyErrors downstream.
#
# The _CACHE_VERSION sentinel is included as a default argument so that
# bumping it changes the effective cache key for every call without requiring
# any change at the call sites.  Increment this integer whenever the shape
# of the returned dict changes.
#
#   v1 → initial implementation (weights, expected_return, volatility,
#          sharpe_ratio, ef_points)
#   v2 → added mean_returns and cov_matrix fields
#
_CACHE_VERSION = 2


@memory.cache
def optimize_portfolio(tickers: list, _version: int = _CACHE_VERSION) -> dict:
    """
    Fetch historical prices and compute the Max Sharpe Ratio portfolio.

    Parameters
    ----------
    tickers  : list of str
        Ticker symbols.  Sorted internally so that
        ``optimize_portfolio(["SPY", "TSLA"])`` and
        ``optimize_portfolio(["TSLA", "SPY"])`` share the same cache entry.
    _version : int
        Cache-busting sentinel — do not pass explicitly.  Increment
        ``_CACHE_VERSION`` at module level whenever the shape of the returned
        dict changes so that stale on-disk entries are never served.

    Returns
    -------
    dict with keys: weights, expected_return, volatility, sharpe_ratio,
                    ef_points, mean_returns, cov_matrix
    """
    del _version  # used only as a cache-key discriminator; not needed at runtime
    # Normalise order so the joblib cache key is deterministic regardless of
    # the order the caller passes tickers in.
    tickers = sorted(tickers)

    # ── 1. Fetch prices ───────────────────────────────────────────────────────
    prices = fetch_data(tickers)

    if prices is None or prices.empty:
        raise ValueError("No price data retrieved for the provided tickers.")

    prices = prices.dropna()

    # ── 2. Expected returns & covariance ──────────────────────────────────────
    mean_hist_ret = expected_returns.mean_historical_return(prices)
    sample_cov    = risk_models.sample_cov(prices)

    # ── 3. Max Sharpe optimisation ────────────────────────────────────────────
    ef = EfficientFrontier(mean_hist_ret, sample_cov)
    ef.max_sharpe()
    cleaned_weights = ef.clean_weights()
    expected_return, volatility, sharpe_ratio = ef.portfolio_performance()

    weights_dict = {t: float(w) for t, w in cleaned_weights.items()}

    # ── 4. Efficient Frontier curve (20 points) ───────────────────────────────
    # Each point is computed by solving for the minimum-variance portfolio at a
    # target return level.  Some target returns may be infeasible (outside the
    # achievable range), so we catch only the specific exceptions PyPortfolioOpt
    # raises for infeasible problems — NOT bare except which would swallow
    # KeyboardInterrupt and SystemExit.
    ef_points: list[dict] = []
    ret_range = np.linspace(float(mean_hist_ret.min()), float(mean_hist_ret.max()), 20)

    for target_ret in ret_range:
        try:
            ef_curve = EfficientFrontier(mean_hist_ret, sample_cov)
            ef_curve.efficient_return(target_return=target_ret)
            t_ret, t_vol, _ = ef_curve.portfolio_performance()
            ef_points.append({
                "return":     round(float(t_ret), 4),
                "volatility": round(float(t_vol), 4),
            })
        except (ValueError, RuntimeError) as exc:
            # Target return is infeasible or solver failed — skip this point.
            logger.debug("EF point skipped (target_ret=%.4f): %s", target_ret, exc)

    return {
        "weights":         weights_dict,
        "expected_return": round(float(expected_return), 4),
        "volatility":      round(float(volatility), 4),
        "sharpe_ratio":    round(float(sharpe_ratio), 4),
        "ef_points":       ef_points,
        # Per-asset annualised mean returns (w^T μ gives the user portfolio return).
        "mean_returns":    {t: round(float(mean_hist_ret[t]), 6) for t in tickers},
        # Full annualised covariance matrix (w^T Σ w gives the user portfolio variance).
        "cov_matrix":      {
            t: {s: round(float(sample_cov.loc[t, s]), 8) for s in tickers}
            for t in tickers
        },
    }
