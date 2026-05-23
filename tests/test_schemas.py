"""
Unit tests for Pydantic schemas (src/schemas.py).
These tests are fast and require no network access.
"""

import pytest
from pydantic import ValidationError
from src.schemas import (
    ForecastItem,
    ForecastResponse,
    OptimizeRequest,
    OptimizeResponse,
    AssetInfoResponse,
    BacktestRequest,
    BacktestDataPoint,
    BacktestResponse,
)


# ── ForecastItem ──────────────────────────────────────────────────────────────

class TestForecastItem:
    def test_valid(self):
        item = ForecastItem(
            date="2026-05-01",
            predicted_price=350.0,
            lower_bound=330.0,
            upper_bound=370.0,
        )
        assert item.date == "2026-05-01"
        assert item.predicted_price == 350.0

    def test_missing_field_raises(self):
        with pytest.raises(ValidationError):
            ForecastItem(date="2026-05-01", predicted_price=350.0)  # missing bounds


# ── ForecastResponse ──────────────────────────────────────────────────────────

class TestForecastResponse:
    def test_valid(self):
        resp = ForecastResponse(
            ticker="TSLA",
            forecast=[
                ForecastItem(date="2026-05-01", predicted_price=350.0, lower_bound=330.0, upper_bound=370.0)
            ],
        )
        assert resp.ticker == "TSLA"
        assert len(resp.forecast) == 1

    def test_empty_forecast_list_is_valid(self):
        resp = ForecastResponse(ticker="SPY", forecast=[])
        assert resp.forecast == []


# ── OptimizeRequest ───────────────────────────────────────────────────────────

class TestOptimizeRequest:
    def test_valid(self):
        req = OptimizeRequest(tickers=["TSLA", "SPY"])
        assert "TSLA" in req.tickers

    def test_single_ticker_raises(self):
        """min_length=2 should reject a single-ticker list."""
        with pytest.raises(ValidationError):
            OptimizeRequest(tickers=["TSLA"])

    def test_empty_list_raises(self):
        with pytest.raises(ValidationError):
            OptimizeRequest(tickers=[])


# ── OptimizeResponse ──────────────────────────────────────────────────────────

class TestOptimizeResponse:
    def test_valid_with_ef_points(self):
        resp = OptimizeResponse(
            weights={"TSLA": 0.1, "SPY": 0.5, "BND": 0.4},
            expected_return=0.12,
            volatility=0.15,
            sharpe_ratio=0.8,
            ef_points=[{"return": 0.1, "volatility": 0.12}],
        )
        assert resp.sharpe_ratio == 0.8
        assert len(resp.ef_points) == 1

    def test_ef_points_defaults_to_empty(self):
        resp = OptimizeResponse(
            weights={"TSLA": 1.0},
            expected_return=0.1,
            volatility=0.2,
            sharpe_ratio=0.5,
        )
        assert resp.ef_points == []


# ── AssetInfoResponse ─────────────────────────────────────────────────────────

class TestAssetInfoResponse:
    def test_bullish(self):
        resp = AssetInfoResponse(ticker="TSLA", price=350.0, change_percent=2.5, sentiment="Bullish")
        assert resp.sentiment == "Bullish"

    def test_bearish(self):
        resp = AssetInfoResponse(ticker="BND", price=72.0, change_percent=-0.3, sentiment="Bearish")
        assert resp.sentiment == "Bearish"

    def test_missing_field_raises(self):
        with pytest.raises(ValidationError):
            AssetInfoResponse(ticker="TSLA", price=350.0)  # missing change_percent & sentiment


# ── BacktestRequest ───────────────────────────────────────────────────────────

class TestBacktestRequest:
    def test_valid_with_defaults(self):
        req = BacktestRequest(
            tickers=["TSLA", "SPY", "BND"],
            weights={"TSLA": 33.3, "SPY": 33.3, "BND": 33.4},
        )
        assert req.initial_investment == 10000.0

    def test_custom_investment(self):
        req = BacktestRequest(
            tickers=["SPY"],
            weights={"SPY": 100.0},
            initial_investment=50000.0,
        )
        assert req.initial_investment == 50000.0


# ── BacktestResponse ──────────────────────────────────────────────────────────

class TestBacktestResponse:
    def test_valid(self):
        resp = BacktestResponse(
            data=[BacktestDataPoint(date="2025-01-02", strategy=1.01, benchmark=1.005)],
            gross_return=16.0,
            total_return=15.5,
            cost_drag=0.5,
            total_costs_paid=50.0,
            alpha=1.2,
            beta=0.85,
            max_drawdown=-4.3,
            rebalance_count=12,
            avg_turnover=3.5,
        )
        assert resp.total_return == 15.5
        assert resp.gross_return == 16.0
        assert resp.cost_drag == 0.5
        assert resp.rebalance_count == 12
        assert len(resp.data) == 1
        assert resp.data[0].strategy == 1.01
