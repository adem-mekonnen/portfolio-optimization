"""
Unit tests for src/portfolio_optimizer.py.

yfinance calls are mocked so tests run offline and fast.
"""

import pytest
import numpy as np
import pandas as pd
from unittest.mock import patch


def _fake_prices(tickers=("TSLA", "SPY", "BND"), n=500):
    """Return a realistic fake price DataFrame (trending up with noise)."""
    dates = pd.date_range("2020-01-01", periods=n, freq="B")
    np.random.seed(42)
    data = {}
    start_prices = {"TSLA": 200.0, "SPY": 350.0, "BND": 75.0}
    for t in tickers:
        start = start_prices.get(t, 100.0)
        returns = np.random.normal(0.0005, 0.02, n)
        prices = start * np.cumprod(1 + returns)
        data[t] = prices
    return pd.DataFrame(data, index=dates)


class TestOptimizePortfolio:
    @patch("src.portfolio_optimizer.fetch_data")
    def test_returns_expected_keys(self, mock_fetch):
        mock_fetch.return_value = _fake_prices()
        from src.portfolio_optimizer import optimize_portfolio
        result = optimize_portfolio(["TSLA", "SPY", "BND"])
        assert "weights" in result
        assert "expected_return" in result
        assert "volatility" in result
        assert "sharpe_ratio" in result
        assert "ef_points" in result

    @patch("src.portfolio_optimizer.fetch_data")
    def test_weights_sum_to_one(self, mock_fetch):
        mock_fetch.return_value = _fake_prices()
        from src.portfolio_optimizer import optimize_portfolio
        result = optimize_portfolio(["TSLA", "SPY", "BND"])
        total = sum(result["weights"].values())
        assert abs(total - 1.0) < 1e-4, f"Weights sum to {total}, expected ~1.0"

    @patch("src.portfolio_optimizer.fetch_data")
    def test_weights_are_non_negative(self, mock_fetch):
        mock_fetch.return_value = _fake_prices()
        from src.portfolio_optimizer import optimize_portfolio
        result = optimize_portfolio(["TSLA", "SPY", "BND"])
        for ticker, w in result["weights"].items():
            assert w >= -1e-6, f"Negative weight for {ticker}: {w}"

    @patch("src.portfolio_optimizer.fetch_data")
    def test_volatility_is_positive(self, mock_fetch):
        mock_fetch.return_value = _fake_prices()
        from src.portfolio_optimizer import optimize_portfolio
        result = optimize_portfolio(["TSLA", "SPY", "BND"])
        assert result["volatility"] > 0

    @patch("src.portfolio_optimizer.fetch_data")
    def test_ef_points_are_list(self, mock_fetch):
        mock_fetch.return_value = _fake_prices()
        from src.portfolio_optimizer import optimize_portfolio
        result = optimize_portfolio(["TSLA", "SPY", "BND"])
        assert isinstance(result["ef_points"], list)

    @patch("src.portfolio_optimizer.fetch_data")
    def test_two_ticker_portfolio(self, mock_fetch):
        """Should work with the minimum of 2 tickers."""
        mock_fetch.return_value = _fake_prices(tickers=("SPY", "BND"))
        from src.portfolio_optimizer import optimize_portfolio
        result = optimize_portfolio(["SPY", "BND"])
        assert set(result["weights"].keys()) == {"SPY", "BND"}

    @patch("src.portfolio_optimizer.fetch_data")
    def test_empty_data_raises(self, mock_fetch):
        mock_fetch.return_value = pd.DataFrame()
        from src.portfolio_optimizer import optimize_portfolio
        with pytest.raises(ValueError):
            optimize_portfolio(["TSLA", "SPY"])
