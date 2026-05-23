"""
API route tests for src/main.py.

All external I/O (yfinance, model inference, portfolio optimizer, scheduler,
cache manager, retrain) is mocked so tests run offline and fast.

Coverage
--------
GET  /forecast/{ticker}       — happy path, invalid ticker, inference error
POST /optimize                — happy path, invalid ticker, single ticker
GET  /asset_info/{ticker}     — happy path, bullish/bearish, invalid ticker,
                                missing column, insufficient history
POST /backtest                — happy path, invalid ticker, invalid freq,
                                zero-cost baseline
GET  /data/status             — happy path
POST /data/refresh-cache      — queues background task
POST /data/retrain            — queues background task
"""

import numpy as np
import pandas as pd
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

# ── Helpers ───────────────────────────────────────────────────────────────────

def _price_df(tickers, n=60, start="2025-01-01"):
    """Return a fake price DataFrame with trending prices."""
    dates = pd.date_range(start, periods=n, freq="B")
    data  = {t: 100.0 + np.arange(n, dtype=float) for t in tickers}
    return pd.DataFrame(data, index=dates)


def _forecast_result(ticker="TSLA"):
    return {
        "ticker": ticker,
        "forecast": [
            {
                "date":            "2026-06-01",
                "predicted_price": 350.0,
                "lower_bound":     330.0,
                "upper_bound":     370.0,
            }
        ],
    }


def _optimize_result(tickers):
    weights = {t: round(1.0 / len(tickers), 4) for t in tickers}
    return {
        "weights":         weights,
        "expected_return": 0.12,
        "volatility":      0.15,
        "sharpe_ratio":    0.80,
        "ef_points":       [{"return": 0.10, "volatility": 0.12}],
    }


def _backtest_result():
    return {
        "data":              [{"date": "2025-01-02", "strategy": 1.01, "benchmark": 1.005}],
        "gross_return":      16.0,
        "total_return":      15.5,
        "cost_drag":         0.5,
        "total_costs_paid":  50.0,
        "alpha":             1.2,
        "beta":              0.85,
        "max_drawdown":      -4.3,
        "rebalance_count":   12,
        "avg_turnover":      3.5,
    }


# ── Fixture: TestClient with scheduler disabled ───────────────────────────────

@pytest.fixture(scope="module")
def client():
    """
    Create a TestClient with the scheduler patched out so no background
    threads are started during tests.
    """
    with patch("src.main.start_scheduler"), patch("src.main.stop_scheduler"):
        from src.main import app
        with TestClient(app, raise_server_exceptions=False) as c:
            yield c


# ══════════════════════════════════════════════════════════════════════════════
# GET /forecast/{ticker}
# ══════════════════════════════════════════════════════════════════════════════

class TestForecastEndpoint:

    @patch("src.main.get_forecast")
    def test_happy_path_returns_forecast(self, mock_fc, client):
        mock_fc.return_value = _forecast_result("TSLA")
        r = client.get("/forecast/TSLA")
        assert r.status_code == 200
        body = r.json()
        assert body["ticker"] == "TSLA"
        assert len(body["forecast"]) == 1
        pt = body["forecast"][0]
        assert "date" in pt
        assert "predicted_price" in pt
        assert "lower_bound" in pt
        assert "upper_bound" in pt

    @patch("src.main.get_forecast")
    def test_lowercase_ticker_normalised(self, mock_fc, client):
        mock_fc.return_value = _forecast_result("SPY")
        r = client.get("/forecast/spy")
        assert r.status_code == 200
        assert r.json()["ticker"] == "SPY"

    def test_invalid_ticker_returns_400(self, client):
        r = client.get("/forecast/TOOLONG123")
        assert r.status_code == 400
        assert "Invalid ticker" in r.json()["detail"]

    def test_numeric_ticker_returns_400(self, client):
        r = client.get("/forecast/123")
        assert r.status_code == 400

    def test_empty_ticker_returns_404_or_400(self, client):
        # FastAPI returns 404 for missing path param
        r = client.get("/forecast/")
        assert r.status_code in (404, 405)

    @patch("src.main.get_forecast", side_effect=RuntimeError("model corrupt"))
    def test_inference_error_returns_500(self, _mock, client):
        r = client.get("/forecast/TSLA")
        assert r.status_code == 500

    @patch("src.main.get_forecast", side_effect=ValueError("no data"))
    def test_value_error_returns_400(self, _mock, client):
        r = client.get("/forecast/TSLA")
        assert r.status_code == 400


# ══════════════════════════════════════════════════════════════════════════════
# POST /optimize
# ══════════════════════════════════════════════════════════════════════════════

class TestOptimizeEndpoint:

    @patch("src.main.optimize_portfolio")
    def test_happy_path(self, mock_opt, client):
        mock_opt.return_value = _optimize_result(["TSLA", "SPY", "BND"])
        r = client.post("/optimize", json={"tickers": ["TSLA", "SPY", "BND"]})
        assert r.status_code == 200
        body = r.json()
        assert "weights" in body
        assert "expected_return" in body
        assert "volatility" in body
        assert "sharpe_ratio" in body
        assert "ef_points" in body

    @patch("src.main.optimize_portfolio")
    def test_weights_keys_match_tickers(self, mock_opt, client):
        tickers = ["TSLA", "SPY"]
        mock_opt.return_value = _optimize_result(tickers)
        r = client.post("/optimize", json={"tickers": tickers})
        assert r.status_code == 200
        assert set(r.json()["weights"].keys()) == set(tickers)

    def test_single_ticker_rejected_by_schema(self, client):
        # Pydantic min_length=2 on tickers list → 422 Unprocessable Entity
        r = client.post("/optimize", json={"tickers": ["TSLA"]})
        assert r.status_code == 422

    def test_empty_tickers_rejected(self, client):
        r = client.post("/optimize", json={"tickers": []})
        assert r.status_code == 422

    def test_invalid_ticker_format_returns_400(self, client):
        r = client.post("/optimize", json={"tickers": ["TSLA", "BAD!TICKER"]})
        assert r.status_code == 400

    @patch("src.main.optimize_portfolio", side_effect=ValueError("not enough data"))
    def test_value_error_returns_400(self, _mock, client):
        r = client.post("/optimize", json={"tickers": ["TSLA", "SPY"]})
        assert r.status_code == 400

    @patch("src.main.optimize_portfolio", side_effect=RuntimeError("solver failed"))
    def test_runtime_error_returns_500(self, _mock, client):
        r = client.post("/optimize", json={"tickers": ["TSLA", "SPY"]})
        assert r.status_code == 500

    def test_missing_body_returns_422(self, client):
        r = client.post("/optimize")
        assert r.status_code == 422


# ══════════════════════════════════════════════════════════════════════════════
# GET /asset_info/{ticker}
# ══════════════════════════════════════════════════════════════════════════════

class TestAssetInfoEndpoint:

    @patch("src.main.fetch_data")
    def test_bullish_sentiment(self, mock_fd, client):
        """Price above 20-day SMA → Bullish."""
        df = _price_df(["TSLA"], n=30)
        # Make last price clearly above SMA using .loc (pandas CoW-safe)
        df.loc[df.index[-1], "TSLA"] = 999.0
        mock_fd.return_value = df
        r = client.get("/asset_info/TSLA")
        assert r.status_code == 200
        body = r.json()
        assert body["ticker"] == "TSLA"
        assert body["sentiment"] == "Bullish"
        assert body["price"] == 999.0
        assert "change_percent" in body

    @patch("src.main.fetch_data")
    def test_bearish_sentiment(self, mock_fd, client):
        """Price below 20-day SMA → Bearish."""
        df = _price_df(["SPY"], n=30)
        # Make last price clearly below SMA using .loc (pandas CoW-safe)
        df.loc[df.index[-1], "SPY"] = 1.0
        mock_fd.return_value = df
        r = client.get("/asset_info/SPY")
        assert r.status_code == 200
        assert r.json()["sentiment"] == "Bearish"

    @patch("src.main.fetch_data")
    def test_response_schema_fields(self, mock_fd, client):
        mock_fd.return_value = _price_df(["BND"], n=30)
        r = client.get("/asset_info/BND")
        assert r.status_code == 200
        body = r.json()
        assert set(body.keys()) == {"ticker", "price", "change_percent", "sentiment"}

    def test_invalid_ticker_returns_400(self, client):
        r = client.get("/asset_info/WAYTOOLONG")
        assert r.status_code == 400

    @patch("src.main.fetch_data", return_value=pd.DataFrame())
    def test_empty_dataframe_returns_400(self, _mock, client):
        r = client.get("/asset_info/TSLA")
        assert r.status_code == 400

    @patch("src.main.fetch_data")
    def test_missing_ticker_column_returns_400(self, mock_fd, client):
        """DataFrame returned but doesn't contain the requested ticker column."""
        df = _price_df(["OTHER"], n=30)
        mock_fd.return_value = df
        r = client.get("/asset_info/TSLA")
        assert r.status_code == 400
        assert "not found" in r.json()["detail"]

    @patch("src.main.fetch_data")
    def test_insufficient_history_returns_400(self, mock_fd, client):
        """Only 1 row of data — need at least 2 to compute daily change."""
        df = _price_df(["TSLA"], n=1)
        mock_fd.return_value = df
        r = client.get("/asset_info/TSLA")
        assert r.status_code == 400

    @patch("src.main.fetch_data", side_effect=RuntimeError("network error"))
    def test_fetch_error_returns_500(self, _mock, client):
        r = client.get("/asset_info/TSLA")
        assert r.status_code == 500


# ══════════════════════════════════════════════════════════════════════════════
# POST /backtest
# ══════════════════════════════════════════════════════════════════════════════

class TestBacktestEndpoint:

    _VALID_BODY = {
        "tickers": ["TSLA", "SPY", "BND"],
        "weights": {"TSLA": 0.1, "SPY": 0.5, "BND": 0.4},
    }

    @patch("src.main.fetch_data")
    @patch("src.main.run_backtest")
    def test_happy_path(self, mock_bt, mock_fd, client):
        mock_fd.return_value = _price_df(["TSLA", "SPY", "BND"], n=252)
        mock_bt.return_value = _backtest_result()
        r = client.post("/backtest", json=self._VALID_BODY)
        assert r.status_code == 200
        body = r.json()
        for key in ("data", "gross_return", "total_return", "cost_drag",
                    "total_costs_paid", "alpha", "beta", "max_drawdown",
                    "rebalance_count", "avg_turnover"):
            assert key in body, f"Missing key: {key}"

    @patch("src.main.fetch_data")
    @patch("src.main.run_backtest")
    def test_default_cost_params_used(self, mock_bt, mock_fd, client):
        """Verify run_backtest is called with the default commission/slippage."""
        mock_fd.return_value = _price_df(["TSLA", "SPY"], n=252)
        mock_bt.return_value = _backtest_result()
        client.post("/backtest", json={
            "tickers": ["TSLA", "SPY"],
            "weights": {"TSLA": 0.5, "SPY": 0.5},
        })
        _, kwargs = mock_bt.call_args
        assert kwargs["commission_pct"] == pytest.approx(0.001)
        assert kwargs["slippage_pct"]   == pytest.approx(0.0005)
        assert kwargs["rebalance_freq"] == "monthly"

    @patch("src.main.fetch_data")
    @patch("src.main.run_backtest")
    def test_custom_cost_params_forwarded(self, mock_bt, mock_fd, client):
        mock_fd.return_value = _price_df(["TSLA", "SPY"], n=252)
        mock_bt.return_value = _backtest_result()
        client.post("/backtest", json={
            "tickers":        ["TSLA", "SPY"],
            "weights":        {"TSLA": 0.5, "SPY": 0.5},
            "commission_pct": 0.002,
            "slippage_pct":   0.001,
            "rebalance_freq": "weekly",
        })
        _, kwargs = mock_bt.call_args
        assert kwargs["commission_pct"] == pytest.approx(0.002)
        assert kwargs["slippage_pct"]   == pytest.approx(0.001)
        assert kwargs["rebalance_freq"] == "weekly"

    def test_invalid_ticker_returns_400(self, client):
        r = client.post("/backtest", json={
            "tickers": ["TSLA", "BAD TICKER"],
            "weights": {"TSLA": 0.5, "BAD TICKER": 0.5},
        })
        assert r.status_code == 400

    def test_invalid_rebalance_freq_returns_400(self, client):
        r = client.post("/backtest", json={
            "tickers":        ["TSLA", "SPY"],
            "weights":        {"TSLA": 0.5, "SPY": 0.5},
            "rebalance_freq": "annually",
        })
        assert r.status_code == 400
        assert "rebalance_freq" in r.json()["detail"]

    @patch("src.main.fetch_data", return_value=pd.DataFrame())
    def test_empty_data_returns_400(self, _mock, client):
        r = client.post("/backtest", json=self._VALID_BODY)
        assert r.status_code == 400

    @patch("src.main.fetch_data")
    @patch("src.main.run_backtest", side_effect=RuntimeError("numerical error"))
    def test_runtime_error_returns_500(self, _mock_bt, mock_fd, client):
        mock_fd.return_value = _price_df(["TSLA", "SPY", "BND"], n=252)
        r = client.post("/backtest", json=self._VALID_BODY)
        assert r.status_code == 500

    def test_commission_above_max_rejected(self, client):
        """commission_pct > 0.05 violates Pydantic le=0.05 constraint."""
        r = client.post("/backtest", json={
            "tickers":        ["TSLA", "SPY"],
            "weights":        {"TSLA": 0.5, "SPY": 0.5},
            "commission_pct": 0.99,
        })
        assert r.status_code == 422

    def test_missing_body_returns_422(self, client):
        r = client.post("/backtest")
        assert r.status_code == 422


# ══════════════════════════════════════════════════════════════════════════════
# GET /data/status
# ══════════════════════════════════════════════════════════════════════════════

class TestDataStatusEndpoint:

    @patch("src.main.cache_status")
    @patch("src.main.get_next_runs")
    @patch("src.main.load_retrain_meta")
    def test_happy_path(self, mock_meta, mock_jobs, mock_cs, client):
        mock_cs.return_value   = {"entries": [], "total": 0}
        mock_jobs.return_value = [
            {"id": "cache_refresh", "name": "Daily cache refresh", "next_run": "2026-06-01T23:05:00+00:00"},
        ]
        mock_meta.return_value = {"TSLA": {"trained_through": "2024-12-31"}}

        r = client.get("/data/status")
        assert r.status_code == 200
        body = r.json()
        assert "cache" in body
        assert "scheduled_jobs" in body
        assert "retrain_meta" in body

    @patch("src.main.cache_status")
    @patch("src.main.get_next_runs")
    @patch("src.main.load_retrain_meta")
    def test_cache_entries_is_list(self, mock_meta, mock_jobs, mock_cs, client):
        mock_cs.return_value   = {"entries": [], "total": 0}
        mock_jobs.return_value = []
        mock_meta.return_value = {}
        r = client.get("/data/status")
        assert isinstance(r.json()["cache"], list)
        assert isinstance(r.json()["scheduled_jobs"], list)

    @patch("src.main.cache_status", side_effect=RuntimeError("disk error"))
    def test_error_returns_500(self, _mock, client):
        r = client.get("/data/status")
        assert r.status_code == 500


# ══════════════════════════════════════════════════════════════════════════════
# POST /data/refresh-cache
# ══════════════════════════════════════════════════════════════════════════════

class TestRefreshCacheEndpoint:

    def test_returns_200_with_message(self, client):
        r = client.post("/data/refresh-cache")
        assert r.status_code == 200
        body = r.json()
        assert "message" in body
        assert "Cache invalidation queued" in body["message"]

    def test_response_mentions_tracked_tickers(self, client):
        r = client.post("/data/refresh-cache")
        msg = r.json()["message"]
        # At least one of the tracked tickers should appear in the message
        assert any(t in msg for t in ["TSLA", "SPY", "BND"])


# ══════════════════════════════════════════════════════════════════════════════
# POST /data/retrain
# ══════════════════════════════════════════════════════════════════════════════

class TestRetrainEndpoint:

    def test_returns_200_with_message(self, client):
        r = client.post("/data/retrain")
        assert r.status_code == 200
        body = r.json()
        assert "message" in body
        assert "Retrain queued" in body["message"]

    def test_response_mentions_status_endpoint(self, client):
        msg = r = client.post("/data/retrain").json()["message"]
        assert "/data/status" in msg


# ══════════════════════════════════════════════════════════════════════════════
# Ticker validation (shared across endpoints)
# ══════════════════════════════════════════════════════════════════════════════

class TestTickerValidation:
    """
    Verify the _validate_ticker guard rejects bad input across all
    ticker-accepting endpoints.
    """

    INVALID_TICKERS = [
        "TOOLONG",        # > 5 chars
        "123",            # digits only
        "TS LA",          # space
        "TS@LA",          # special char
        "",               # empty (caught by path routing)
        "tsla!",          # lowercase + special
    ]

    @pytest.mark.parametrize("bad", INVALID_TICKERS)
    def test_forecast_rejects_bad_ticker(self, bad, client):
        if bad == "":
            return  # empty path → 404, not 400
        r = client.get(f"/forecast/{bad}")
        assert r.status_code == 400, f"Expected 400 for ticker {bad!r}, got {r.status_code}"

    @pytest.mark.parametrize("bad", INVALID_TICKERS)
    def test_asset_info_rejects_bad_ticker(self, bad, client):
        if bad == "":
            return
        r = client.get(f"/asset_info/{bad}")
        assert r.status_code == 400, f"Expected 400 for ticker {bad!r}, got {r.status_code}"

    VALID_TICKERS = ["TSLA", "SPY", "BND", "AAPL", "MSFT"]

    @patch("src.main.get_forecast")
    @pytest.mark.parametrize("good", VALID_TICKERS)
    def test_forecast_accepts_valid_ticker(self, mock_fc, good, client):
        mock_fc.return_value = _forecast_result(good)
        r = client.get(f"/forecast/{good}")
        assert r.status_code == 200
