"""
Unit tests for src/model_inference.py.

All external I/O (yfinance, keras model loading) is mocked so tests run
offline and without requiring trained model files on disk.
"""

import pytest
import numpy as np
import pandas as pd
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta


# ── helpers ───────────────────────────────────────────────────────────────────

def _fake_price_series(n=120, start_price=300.0):
    """Return a pd.Series of fake daily prices."""
    dates = pd.date_range(end=datetime.now(), periods=n, freq="B")
    prices = start_price + np.cumsum(np.random.normal(0, 5, n))
    return pd.Series(prices, index=dates, name="TSLA")


def _fake_price_df(ticker="TSLA", n=120):
    s = _fake_price_series(n)
    return pd.DataFrame({ticker: s})


# ── mock forecast (no model on disk) ─────────────────────────────────────────

class TestMockForecast:
    @patch("src.model_inference._model_exists", return_value=False)
    @patch("src.model_inference.fetch_data")
    def test_returns_30_points(self, mock_fetch, mock_exists):
        mock_fetch.return_value = _fake_price_df()
        from src.model_inference import get_forecast
        result = get_forecast("TSLA")
        assert result["ticker"] == "TSLA"
        assert len(result["forecast"]) == 30

    @patch("src.model_inference._model_exists", return_value=False)
    @patch("src.model_inference.fetch_data")
    def test_forecast_keys_present(self, mock_fetch, mock_exists):
        mock_fetch.return_value = _fake_price_df()
        from src.model_inference import get_forecast
        result = get_forecast("SPY")
        point = result["forecast"][0]
        assert "date" in point
        assert "predicted_price" in point
        assert "lower_bound" in point
        assert "upper_bound" in point

    @patch("src.model_inference._model_exists", return_value=False)
    @patch("src.model_inference.fetch_data")
    def test_lower_bound_lte_predicted_lte_upper(self, mock_fetch, mock_exists):
        mock_fetch.return_value = _fake_price_df()
        from src.model_inference import get_forecast
        result = get_forecast("BND")
        for point in result["forecast"]:
            assert point["lower_bound"] <= point["predicted_price"] <= point["upper_bound"]

    @patch("src.model_inference._model_exists", return_value=False)
    @patch("src.model_inference.fetch_data")
    def test_ticker_uppercased(self, mock_fetch, mock_exists):
        mock_fetch.return_value = _fake_price_df("TSLA")
        from src.model_inference import get_forecast
        result = get_forecast("tsla")
        assert result["ticker"] == "TSLA"

    @patch("src.model_inference._model_exists", return_value=False)
    @patch("src.model_inference.fetch_data")
    def test_fallback_when_fetch_fails(self, mock_fetch, mock_exists):
        """If fetch_data raises, mock forecast should still return 30 points."""
        mock_fetch.side_effect = Exception("network error")
        from src.model_inference import get_forecast
        result = get_forecast("TSLA")
        assert len(result["forecast"]) == 30


# ── LSTM forecast path (model exists) ────────────────────────────────────────

class TestLSTMForecast:
    @patch("src.model_inference._model_exists", return_value=True)
    @patch("src.model_inference.fetch_data")
    @patch("src.model_inference.joblib.load")
    @patch("src.model_inference.load_model")
    def test_lstm_path_returns_30_points(self, mock_load_model, mock_joblib, mock_fetch, mock_exists):
        # Set up fake scaler
        from sklearn.preprocessing import MinMaxScaler
        scaler = MinMaxScaler()
        prices = np.linspace(100, 400, 200).reshape(-1, 1).astype("float32")
        scaler.fit(prices)
        mock_joblib.return_value = scaler

        # Set up fake model that returns a constant scaled prediction
        fake_model = MagicMock()
        fake_model.predict.return_value = np.array([[0.5]])
        mock_load_model.return_value = fake_model

        mock_fetch.return_value = _fake_price_df(n=120)

        from src.model_inference import get_forecast
        result = get_forecast("TSLA")
        assert result["ticker"] == "TSLA"
        assert len(result["forecast"]) == 30

    @patch("src.model_inference._model_exists", return_value=True)
    @patch("src.model_inference.fetch_data")
    @patch("src.model_inference.joblib.load")
    @patch("src.model_inference.load_model")
    def test_lstm_falls_back_on_error(self, mock_load_model, mock_joblib, mock_fetch, mock_exists):
        """If LSTM inference raises, get_forecast should fall back to mock."""
        mock_load_model.side_effect = Exception("corrupt model file")
        mock_fetch.return_value = _fake_price_df(n=120)

        from src.model_inference import get_forecast
        result = get_forecast("TSLA")
        # Should still return 30 points via mock fallback
        assert len(result["forecast"]) == 30

# ── _ci (confidence interval helper) ─────────────────────────────────────────

class TestConfidenceInterval:
    """Tests for src.model_inference._ci — the shared CI clamping helper."""

    def test_normal_volatility_no_clamping(self):
        """Typical ETF volatility (~3 %) should not trigger clamping."""
        from src.model_inference import _ci, _MIN_PRICE
        lower, upper = _ci(350.0, 0.03)
        assert lower > _MIN_PRICE          # not clamped
        assert lower < 350.0
        assert upper > 350.0

    def test_lower_bound_never_negative(self):
        """Extreme volatility (50 %) must not produce a negative lower bound."""
        from src.model_inference import _ci, _MIN_PRICE
        lower, upper = _ci(350.0, 0.50)
        assert lower >= _MIN_PRICE
        assert lower >= 0.0

    def test_lower_bound_clamped_to_min_price(self):
        """When the raw lower bound would be negative, it is clamped to _MIN_PRICE."""
        from src.model_inference import _ci, _MIN_PRICE, CONFIDENCE_Z
        # Choose volatility so that price * (1 - Z * vol) < 0
        # e.g. price=100, vol=0.6 → 100 * (1 - 1.96*0.6) = 100 * (-0.176) = -17.6
        lower, upper = _ci(100.0, 0.60)
        assert lower == _MIN_PRICE

    def test_upper_bound_always_above_price(self):
        """Upper bound must always be greater than the predicted price."""
        from src.model_inference import _ci
        for vol in [0.01, 0.05, 0.20, 0.50]:
            _, upper = _ci(200.0, vol)
            assert upper > 200.0, f"upper bound below price at vol={vol}"

    def test_lower_lte_price_lte_upper(self):
        """lower ≤ price ≤ upper for a range of realistic prices and vols."""
        from src.model_inference import _ci
        for price in [10.0, 100.0, 500.0, 1000.0]:
            for vol in [0.01, 0.03, 0.10, 0.30]:
                lower, upper = _ci(price, vol)
                assert lower <= price <= upper, (
                    f"CI violated: lower={lower}, price={price}, upper={upper}, vol={vol}"
                )

    def test_zero_volatility_gives_tight_interval(self):
        """Zero volatility → lower == upper == price (no uncertainty)."""
        from src.model_inference import _ci
        lower, upper = _ci(250.0, 0.0)
        assert lower == upper == 250.0

    def test_very_small_price_clamped(self):
        """A penny stock with high vol should still have lower >= _MIN_PRICE."""
        from src.model_inference import _ci, _MIN_PRICE
        lower, _ = _ci(0.05, 0.80)
        assert lower >= _MIN_PRICE

    def test_mock_forecast_lower_bound_never_negative(self):
        """End-to-end: _mock_forecast must never produce a negative lower_bound."""
        from src.model_inference import _mock_forecast
        with patch("src.model_inference.fetch_data") as mock_fd:
            # Simulate a high-volatility ticker
            dates  = pd.date_range("2025-01-01", periods=180, freq="B")
            prices = pd.Series(
                100.0 * (1 + np.random.normal(0, 0.05, 180)).cumprod(),
                index=dates,
                name="TSLA",
            )
            mock_fd.return_value = pd.DataFrame({"TSLA": prices})
            result = _mock_forecast("TSLA", days=30)

        for pt in result:
            assert pt["lower_bound"] >= 0.0, (
                f"Negative lower_bound {pt['lower_bound']} on {pt['date']}"
            )
            assert pt["lower_bound"] <= pt["predicted_price"], (
                f"lower_bound {pt['lower_bound']} > predicted_price {pt['predicted_price']}"
            )
            assert pt["upper_bound"] >= pt["predicted_price"], (
                f"upper_bound {pt['upper_bound']} < predicted_price {pt['predicted_price']}"
            )
