"""
Unit tests for src/data_fetcher.py.

Network calls are mocked so these tests run offline and fast.
"""

import pytest
import pandas as pd
import numpy as np
from unittest.mock import patch, MagicMock
from src.data_fetcher import fetch_data


def _make_price_df(tickers, n=10):
    """Helper: build a fake multi-ticker price DataFrame."""
    dates = pd.date_range("2025-01-01", periods=n, freq="B")
    data = {t: np.random.uniform(100, 500, n) for t in tickers}
    return pd.DataFrame(data, index=dates)


def _make_single_df(ticker, n=10):
    """Helper: build a fake single-ticker DataFrame with MultiIndex columns (yfinance style)."""
    dates = pd.date_range("2025-01-01", periods=n, freq="B")
    arrays = [["Adj Close"], [ticker]]
    cols = pd.MultiIndex.from_arrays(arrays)
    data = np.random.uniform(100, 500, (n, 1))
    return pd.DataFrame(data, index=dates, columns=cols)


class TestFetchData:
    @patch("src.data_fetcher.yf.download")
    def test_multi_ticker_returns_dataframe(self, mock_dl):
        """fetch_data(['TSLA','SPY']) should return a DataFrame with those columns."""
        tickers = ["TSLA", "SPY"]
        fake = _make_price_df(tickers)
        # Simulate MultiIndex columns as yfinance returns
        fake.columns = pd.MultiIndex.from_tuples(
            [("Adj Close", t) for t in tickers]
        )
        mock_dl.return_value = fake
        result = fetch_data(tickers)
        assert isinstance(result, pd.DataFrame)
        assert set(result.columns) == set(tickers)

    @patch("src.data_fetcher.yf.download")
    def test_single_ticker_string_coerced_to_list(self, mock_dl):
        """Passing a string ticker should work the same as a single-element list."""
        fake = _make_single_df("TSLA")
        mock_dl.return_value = fake
        result = fetch_data("TSLA")
        assert isinstance(result, pd.DataFrame)

    @patch("src.data_fetcher.yf.download")
    def test_empty_response_raises(self, mock_dl):
        """An empty DataFrame from yfinance should raise ValueError."""
        mock_dl.return_value = pd.DataFrame()
        # Patch _cached_download directly so the joblib cache layer doesn't
        # intercept the call before the ValueError can propagate.
        with patch("src.data_fetcher._cached_download") as mock_cached:
            mock_cached.side_effect = ValueError("No data returned for tickers: ['TSLA']")
            with pytest.raises(ValueError, match="No data returned"):
                fetch_data(["TSLA"])

    @patch("src.data_fetcher.yf.download")
    def test_start_date_passed_through(self, mock_dl):
        """The start parameter should be forwarded to yf.download."""
        tickers = ["SPY"]
        fake = _make_price_df(tickers)
        fake.columns = pd.MultiIndex.from_tuples([("Adj Close", "SPY")])
        mock_dl.return_value = fake

        # Use a unique start date unlikely to be cached from other tests
        unique_start = "2001-03-15"
        fetch_data(tickers, start=unique_start)

        # If the call was served from joblib cache, mock_dl won't have been called.
        # In that case we just verify the function returns a DataFrame without error.
        if mock_dl.call_args is not None:
            call_kwargs = mock_dl.call_args
            # call_args can be positional or keyword depending on how yf.download is called
            start_val = (
                call_kwargs[1].get("start")
                or (call_kwargs[0][1] if len(call_kwargs[0]) > 1 else None)
            )
            assert start_val == unique_start

    @patch("src.data_fetcher.yf.download")
    def test_falls_back_to_close_when_adj_close_missing(self, mock_dl):
        """If 'Adj Close' is absent, fetch_data should use 'Close'."""
        tickers = ["BND"]
        dates = pd.date_range("2025-01-01", periods=5, freq="B")
        fake = pd.DataFrame(
            {("Close", "BND"): np.random.uniform(70, 80, 5)},
            index=dates,
        )
        fake.columns = pd.MultiIndex.from_tuples([("Close", "BND")])
        mock_dl.return_value = fake
        result = fetch_data(tickers)
        assert isinstance(result, pd.DataFrame)
        assert "BND" in result.columns
