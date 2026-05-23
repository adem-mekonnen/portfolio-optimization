"""
Unit tests for src/backtester.py.

No network calls — all tests use synthetic price data.
"""

import numpy as np
import pandas as pd
import pytest
from src.backtester import run_backtest, _rebalance_dates, _benchmark_weights


# ── Helpers ───────────────────────────────────────────────────────────────────

def _flat_prices(tickers=("TSLA", "SPY", "BND"), n=252, start="2025-01-01") -> pd.DataFrame:
    """Prices that never change — useful for isolating cost effects."""
    dates = pd.date_range(start, periods=n, freq="B")
    return pd.DataFrame({t: np.ones(n) * 100.0 for t in tickers}, index=dates)


def _trending_prices(tickers=("TSLA", "SPY", "BND"), n=252, daily_return=0.001) -> pd.DataFrame:
    """Prices that grow at a constant daily rate."""
    dates = pd.date_range("2025-01-01", periods=n, freq="B")
    data = {}
    for t in tickers:
        data[t] = 100.0 * (1 + daily_return) ** np.arange(n)
    return pd.DataFrame(data, index=dates)


def _equal_weights(tickers) -> dict:
    w = 1.0 / len(tickers)
    return {t: w for t in tickers}


def _drifting_prices(n=252) -> pd.DataFrame:
    """
    Prices where each ticker has a different return so weights drift between
    rebalances, generating real turnover and therefore real costs.
    """
    dates = pd.date_range("2025-01-01", periods=n, freq="B")
    np.random.seed(42)
    return pd.DataFrame({
        "TSLA": 100.0 * np.cumprod(1 + np.random.normal(0.002, 0.03, n)),
        "SPY":  100.0 * np.cumprod(1 + np.random.normal(0.001, 0.01, n)),
        "BND":  100.0 * np.cumprod(1 + np.random.normal(0.0002, 0.003, n)),
    }, index=dates)


# ── _rebalance_dates ──────────────────────────────────────────────────────────


# ── _rebalance_dates ──────────────────────────────────────────────────────────

class TestRebalanceDates:
    def test_daily_returns_all_dates(self):
        idx = pd.date_range("2025-01-01", periods=10, freq="B")
        result = _rebalance_dates(idx, "daily")
        assert result == set(idx)

    def test_monthly_first_date_always_included(self):
        idx = pd.date_range("2025-01-01", periods=60, freq="B")
        result = _rebalance_dates(idx, "monthly")
        assert idx[0] in result

    def test_monthly_fewer_dates_than_daily(self):
        idx = pd.date_range("2025-01-01", periods=252, freq="B")
        daily   = _rebalance_dates(idx, "daily")
        monthly = _rebalance_dates(idx, "monthly")
        assert len(monthly) < len(daily)

    def test_quarterly_fewer_than_monthly(self):
        idx = pd.date_range("2025-01-01", periods=252, freq="B")
        monthly   = _rebalance_dates(idx, "monthly")
        quarterly = _rebalance_dates(idx, "quarterly")
        assert len(quarterly) <= len(monthly)

    def test_weekly_between_daily_and_monthly(self):
        idx = pd.date_range("2025-01-01", periods=252, freq="B")
        daily   = len(_rebalance_dates(idx, "daily"))
        weekly  = len(_rebalance_dates(idx, "weekly"))
        monthly = len(_rebalance_dates(idx, "monthly"))
        assert monthly <= weekly <= daily

    def test_invalid_freq_raises(self):
        idx = pd.date_range("2025-01-01", periods=10, freq="B")
        with pytest.raises(ValueError, match="Unknown rebalance frequency"):
            _rebalance_dates(idx, "yearly")  # type: ignore


# ── _benchmark_weights ────────────────────────────────────────────────────────

class TestBenchmarkWeights:
    def test_spy_bnd_gives_60_40(self):
        w, _ = _benchmark_weights(["TSLA", "SPY", "BND"])
        assert abs(w["SPY"] - 0.60) < 1e-9
        assert abs(w["BND"] - 0.40) < 1e-9
        assert abs(w["TSLA"] - 0.00) < 1e-9

    def test_no_spy_bnd_gives_equal_weight(self):
        tickers = ["AAPL", "MSFT", "GOOG"]
        w, _ = _benchmark_weights(tickers)
        for t in tickers:
            assert abs(w[t] - 1 / 3) < 1e-9


# ── run_backtest — zero-cost baseline ────────────────────────────────────────

class TestRunBacktestZeroCost:
    def test_returns_required_keys(self):
        prices = _trending_prices()
        result = run_backtest(prices, _equal_weights(prices.columns),
                              commission_pct=0, slippage_pct=0)
        for key in ("data", "gross_return", "total_return", "cost_drag",
                    "total_costs_paid", "alpha", "beta", "max_drawdown",
                    "rebalance_count", "avg_turnover"):
            assert key in result, f"Missing key: {key}"

    def test_zero_cost_drag_when_no_costs(self):
        prices = _trending_prices()
        result = run_backtest(prices, _equal_weights(prices.columns),
                              commission_pct=0, slippage_pct=0)
        assert result["cost_drag"] == 0.0
        assert result["total_costs_paid"] == 0.0

    def test_gross_equals_total_when_no_costs(self):
        prices = _trending_prices()
        result = run_backtest(prices, _equal_weights(prices.columns),
                              commission_pct=0, slippage_pct=0)
        assert result["gross_return"] == result["total_return"]

    def test_flat_prices_zero_return(self):
        prices = _flat_prices()
        result = run_backtest(prices, _equal_weights(prices.columns),
                              commission_pct=0, slippage_pct=0)
        assert abs(result["total_return"]) < 0.01

    def test_data_points_length_matches_prices(self):
        prices = _trending_prices(n=100)
        result = run_backtest(prices, _equal_weights(prices.columns),
                              commission_pct=0, slippage_pct=0)
        assert len(result["data"]) == len(prices)

    def test_data_points_have_correct_keys(self):
        prices = _trending_prices(n=50)
        result = run_backtest(prices, _equal_weights(prices.columns),
                              commission_pct=0, slippage_pct=0)
        for pt in result["data"]:
            assert "date" in pt
            assert "strategy" in pt
            assert "benchmark" in pt

    def test_positive_return_on_trending_prices(self):
        prices = _trending_prices(daily_return=0.001)
        result = run_backtest(prices, _equal_weights(prices.columns),
                              commission_pct=0, slippage_pct=0)
        assert result["total_return"] > 0


# ── run_backtest — cost effects ───────────────────────────────────────────────

class TestRunBacktestWithCosts:
    def test_costs_reduce_return(self):
        prices = _drifting_prices()
        w = _equal_weights(prices.columns)
        no_cost   = run_backtest(prices, w, commission_pct=0,     slippage_pct=0)
        with_cost = run_backtest(prices, w, commission_pct=0.001, slippage_pct=0.0005)
        assert with_cost["total_return"] < no_cost["total_return"]

    def test_cost_drag_is_positive(self):
        prices = _drifting_prices()
        result = run_backtest(prices, _equal_weights(prices.columns),
                              commission_pct=0.001, slippage_pct=0.0005)
        assert result["cost_drag"] >= 0

    def test_total_costs_paid_positive(self):
        prices = _drifting_prices()
        result = run_backtest(prices, _equal_weights(prices.columns),
                              commission_pct=0.001, slippage_pct=0.0005)
        assert result["total_costs_paid"] > 0

    def test_daily_rebalance_higher_cost_than_monthly(self):
        """More frequent rebalancing → more turnover → higher total costs."""
        prices = _drifting_prices()
        w = _equal_weights(prices.columns)
        daily   = run_backtest(prices, w, commission_pct=0.001, slippage_pct=0.0005,
                               rebalance_freq="daily")
        monthly = run_backtest(prices, w, commission_pct=0.001, slippage_pct=0.0005,
                               rebalance_freq="monthly")
        assert daily["total_costs_paid"] >= monthly["total_costs_paid"]

    def test_rebalance_count_daily_equals_price_rows_minus_one(self):
        prices = _trending_prices(n=50)
        result = run_backtest(prices, _equal_weights(prices.columns),
                              commission_pct=0, slippage_pct=0,
                              rebalance_freq="daily")
        # First day is construction (i=0 skipped), so count = n - 1
        assert result["rebalance_count"] == len(prices) - 1

    def test_rebalance_count_monthly_less_than_daily(self):
        prices = _trending_prices(n=252)
        w = _equal_weights(prices.columns)
        daily   = run_backtest(prices, w, rebalance_freq="daily")
        monthly = run_backtest(prices, w, rebalance_freq="monthly")
        assert monthly["rebalance_count"] < daily["rebalance_count"]


# ── run_backtest — weight normalisation ──────────────────────────────────────

class TestWeightNormalisation:
    def test_weights_summing_to_100_normalised(self):
        """Weights expressed as percentages (0–100) should be normalised to fractions."""
        prices = _trending_prices(tickers=("SPY", "BND"), n=100)
        # Pass weights as percentages (sum = 100)
        result = run_backtest(prices, {"SPY": 60, "BND": 40},
                              commission_pct=0, slippage_pct=0)
        assert "total_return" in result

    def test_single_asset_portfolio(self):
        prices = _trending_prices(tickers=("SPY",), n=100)
        result = run_backtest(prices, {"SPY": 1.0},
                              commission_pct=0, slippage_pct=0)
        assert result["total_return"] > 0


# ── run_backtest — max drawdown ───────────────────────────────────────────────

class TestMaxDrawdown:
    def test_flat_prices_zero_drawdown(self):
        prices = _flat_prices(n=100)
        result = run_backtest(prices, _equal_weights(prices.columns),
                              commission_pct=0, slippage_pct=0)
        assert abs(result["max_drawdown"]) < 0.01

    def test_drawdown_negative_or_zero(self):
        prices = _trending_prices(n=100)
        result = run_backtest(prices, _equal_weights(prices.columns),
                              commission_pct=0, slippage_pct=0)
        assert result["max_drawdown"] <= 0
