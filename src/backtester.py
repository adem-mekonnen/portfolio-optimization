"""
Backtesting engine with transaction cost and slippage modelling.

Cost model
----------
Two friction sources are applied on every rebalance event:

1. **Commission** — a flat percentage of the *traded notional* on each leg.
   Typical retail broker: 0.05 % (5 bps).  Zero-commission brokers: 0 %.

2. **Slippage** — models the bid-ask spread and market-impact cost as a
   percentage of the *traded notional*.  Typical liquid ETF: 0.02–0.05 %.
   Illiquid single stocks: 0.10–0.25 %.

Both are applied symmetrically on buys and sells.

Rebalance schedule
------------------
The portfolio is rebalanced back to target weights on a fixed calendar
frequency.  Between rebalances the weights drift with market returns (buy-
and-hold).  Supported frequencies:

  - "daily"    — rebalance every trading day (maximum turnover / cost)
  - "weekly"   — rebalance every Monday (or first trading day of the week)
  - "monthly"  — rebalance on the first trading day of each calendar month
  - "quarterly"— rebalance on the first trading day of each quarter

Cost calculation per rebalance
-------------------------------
At each rebalance date we compute the *turnover* — the sum of absolute weight
changes across all assets — and apply:

    cost_per_rebalance = turnover * (commission_pct + slippage_pct)

This is deducted from the portfolio value before continuing the simulation.

Benchmark
---------
The benchmark is a static 60 % SPY / 40 % BND allocation (or equally-weighted
if SPY/BND are not in the ticker list) with NO transaction costs, representing
a passive buy-and-hold investor.
"""

from __future__ import annotations

import logging
from typing import Literal

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ── Types ─────────────────────────────────────────────────────────────────────

RebalanceFreq = Literal["daily", "weekly", "monthly", "quarterly"]

# ── Helpers ───────────────────────────────────────────────────────────────────

def _rebalance_dates(index: pd.DatetimeIndex, freq: RebalanceFreq) -> set:
    """
    Return the set of dates in *index* on which a rebalance should occur.
    The first date is always included (initial portfolio construction).
    """
    if freq == "daily":
        return set(index)

    dates = pd.Series(index, index=index)

    if freq == "weekly":
        # First trading day of each ISO week
        mask = dates.dt.isocalendar().week != dates.shift(1).dt.isocalendar().week
    elif freq == "monthly":
        mask = dates.dt.month != dates.shift(1).dt.month
    elif freq == "quarterly":
        mask = dates.dt.quarter != dates.shift(1).dt.quarter
    else:
        raise ValueError(f"Unknown rebalance frequency: {freq!r}")

    # Always include the very first date
    mask.iloc[0] = True
    return set(index[mask])


def _benchmark_weights(tickers: list[str]) -> tuple[dict[str, float], str]:
    """
    Return (weight_dict, human-readable label) for the benchmark.

    Priority:
      1. 60 % SPY / 40 % BND  — if both are in the ticker universe
      2. 100 % SPY             — if only SPY is present
      3. Equal-weight          — fallback when neither SPY nor BND is present
    """
    upper = [t.upper() for t in tickers]
    has_spy = "SPY" in upper
    has_bnd = "BND" in upper

    w: dict[str, float] = {t: 0.0 for t in tickers}

    if has_spy and has_bnd:
        w[tickers[upper.index("SPY")]] = 0.60
        w[tickers[upper.index("BND")]] = 0.40
        return w, "60% SPY / 40% BND"

    if has_spy:
        w[tickers[upper.index("SPY")]] = 1.0
        return w, "100% SPY"

    even = 1.0 / len(tickers)
    for t in tickers:
        w[t] = even
    label = " / ".join(f"{round(even * 100)}% {t}" for t in tickers)
    return w, f"Equal-weight ({label})"


# ── Core engine ───────────────────────────────────────────────────────────────

def run_backtest(
    prices: pd.DataFrame,
    target_weights: dict[str, float],
    *,
    initial_investment: float = 10_000.0,
    commission_pct: float = 0.001,   # 0.10 % per side
    slippage_pct: float = 0.0005,    # 0.05 % per side
    rebalance_freq: RebalanceFreq = "monthly",
) -> dict:
    """
    Simulate a rebalanced portfolio with transaction costs and slippage.

    Parameters
    ----------
    prices            : DataFrame of Adj Close prices, columns = tickers
    target_weights    : {ticker: weight} — must sum to ~1.0 (normalised internally)
    initial_investment: starting portfolio value in dollars
    commission_pct    : one-way commission as a fraction of traded notional
    slippage_pct      : one-way slippage as a fraction of traded notional
    rebalance_freq    : how often to rebalance back to target weights

    Returns
    -------
    dict with keys:
        data            : list of {date, strategy, benchmark} (cumulative multipliers)
        gross_return    : total return before costs (%)
        total_return    : total return after costs (%)
        cost_drag       : gross_return - total_return (pp)
        total_costs_paid: total dollar cost paid over the period
        alpha           : annualised alpha vs benchmark (%)
        beta            : beta vs benchmark
        max_drawdown    : maximum drawdown of the net strategy (%)
        rebalance_count : number of rebalance events
        avg_turnover    : average turnover per rebalance (fraction)
    """
    prices = prices.dropna()
    tickers = list(prices.columns)

    # ── Normalise target weights ──────────────────────────────────────────────
    total_w = sum(target_weights.get(t, 0.0) for t in tickers)
    if total_w <= 0:
        total_w = 1.0
    norm_w = {t: target_weights.get(t, 0.0) / total_w for t in tickers}

    # ── Identify rebalance dates ──────────────────────────────────────────────
    rebal_dates = _rebalance_dates(prices.index, rebalance_freq)

    # ── Simulation ────────────────────────────────────────────────────────────
    total_cost_per_side = commission_pct + slippage_pct  # applied to each side

    portfolio_value = initial_investment
    # Current holdings: {ticker: dollar_value}
    holdings: dict[str, float] = {t: portfolio_value * norm_w[t] for t in tickers}

    gross_portfolio_value = initial_investment  # tracks value WITHOUT costs
    gross_holdings: dict[str, float] = dict(holdings)

    strategy_curve: list[float] = []
    gross_curve: list[float]    = []
    total_costs_paid = 0.0
    rebalance_count  = 0
    turnovers: list[float] = []

    prev_prices = prices.iloc[0]

    for i, (date, row) in enumerate(prices.iterrows()):
        if i == 0:
            strategy_curve.append(1.0)
            gross_curve.append(1.0)
            continue

        # ── 1. Mark-to-market: update holdings with today's price change ──────
        for t in tickers:
            if prev_prices[t] > 0:
                price_ratio = row[t] / prev_prices[t]
                holdings[t]       *= price_ratio
                gross_holdings[t] *= price_ratio

        portfolio_value       = sum(holdings.values())
        gross_portfolio_value = sum(gross_holdings.values())

        # ── 2. Rebalance if scheduled ─────────────────────────────────────────
        if date in rebal_dates and i > 0:
            # Current weights after drift
            current_w = {t: holdings[t] / portfolio_value for t in tickers}

            # Turnover = sum of absolute weight changes / 2
            # (each dollar moved is a buy on one side and a sell on the other)
            turnover = sum(abs(norm_w[t] - current_w[t]) for t in tickers) / 2.0
            turnovers.append(turnover)

            # Cost = turnover * 2 sides * cost_per_side
            # (we pay commission+slippage on both the sell leg and the buy leg)
            cost_fraction = turnover * 2.0 * total_cost_per_side
            cost_dollars  = portfolio_value * cost_fraction
            total_costs_paid += cost_dollars

            # Deduct costs from net portfolio only
            portfolio_value -= cost_dollars
            # Rebalance holdings to target weights
            holdings = {t: portfolio_value * norm_w[t] for t in tickers}
            # Gross portfolio rebalances without cost deduction
            gross_holdings = {t: gross_portfolio_value * norm_w[t] for t in tickers}

            rebalance_count += 1

        strategy_curve.append(portfolio_value / initial_investment)
        gross_curve.append(gross_portfolio_value / initial_investment)
        prev_prices = row

    # ── Benchmark (no costs, static weights) ─────────────────────────────────
    bench_w, benchmark_label = _benchmark_weights(tickers)
    daily_returns = prices.pct_change().dropna()
    bench_returns = sum(
        daily_returns[t] * bench_w[t]
        for t in tickers
        if t in daily_returns.columns
    )
    bench_curve_series = (1 + bench_returns).cumprod()
    # Prepend 1.0 for the first day
    bench_curve = [1.0] + list(bench_curve_series.values)

    # Align lengths (strategy_curve includes day 0)
    min_len = min(len(strategy_curve), len(bench_curve))
    strategy_curve = strategy_curve[:min_len]
    bench_curve    = bench_curve[:min_len]
    date_index     = prices.index[:min_len]

    # ── Performance metrics ───────────────────────────────────────────────────
    strat_series = pd.Series(strategy_curve, index=date_index)
    bench_series = pd.Series(bench_curve,    index=date_index)
    gross_series = pd.Series(gross_curve[:min_len], index=date_index)

    gross_return = (gross_series.iloc[-1] - 1) * 100
    total_return = (strat_series.iloc[-1] - 1) * 100
    cost_drag    = round(gross_return - total_return, 4)

    # Daily returns for alpha/beta
    strat_daily = strat_series.pct_change().dropna()
    bench_daily = bench_series.pct_change().dropna()

    cov_matrix   = np.cov(strat_daily, bench_daily)
    beta         = float(cov_matrix[0, 1] / cov_matrix[1, 1]) if cov_matrix[1, 1] != 0 else 1.0
    alpha        = float((strat_daily.mean() - beta * bench_daily.mean()) * 252 * 100)

    roll_max     = strat_series.cummax()
    max_drawdown = float(((strat_series / roll_max) - 1.0).min() * 100)

    avg_turnover = float(np.mean(turnovers)) if turnovers else 0.0

    # ── Build data points ─────────────────────────────────────────────────────
    data_points = [
        {
            "date":      d.strftime("%Y-%m-%d"),
            "strategy":  round(float(sv), 4),
            "benchmark": round(float(bv), 4),
        }
        for d, sv, bv in zip(date_index, strategy_curve, bench_curve)
    ]

    return {
        "data":              data_points,
        "gross_return":      round(gross_return, 2),
        "total_return":      round(total_return, 2),
        "cost_drag":         round(cost_drag, 2),
        "total_costs_paid":  round(total_costs_paid, 2),
        "alpha":             round(alpha, 2),
        "beta":              round(beta, 2),
        "max_drawdown":      round(max_drawdown, 2),
        "rebalance_count":   rebalance_count,
        "avg_turnover":      round(avg_turnover * 100, 2),  # as percentage
        "benchmark_label":   benchmark_label,
    }
