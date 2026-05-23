from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

class ForecastItem(BaseModel):
    date: str
    predicted_price: float
    lower_bound: float
    upper_bound: float

class ForecastResponse(BaseModel):
    ticker: str
    forecast: List[ForecastItem]

class OptimizeRequest(BaseModel):
    tickers: List[str] = Field(..., min_length=2, description="List of at least two tickers to optimize")

class OptimizeResponse(BaseModel):
    weights: Dict[str, float]
    expected_return: float
    volatility: float
    sharpe_ratio: float
    ef_points: List[Dict[str, float]] = []
    # Per-asset annualised mean returns and the full covariance matrix.
    # Included so the frontend can compute accurate "Your Mix" metrics
    # (weighted return and portfolio volatility) for any user-defined weights
    # without needing an extra round-trip to the backend.
    mean_returns: Dict[str, float] = {}
    cov_matrix: Dict[str, Dict[str, float]] = {}

class AssetInfoResponse(BaseModel):
    ticker: str
    price: float
    change_percent: float
    sentiment: str

class BacktestRequest(BaseModel):
    tickers: List[str]
    weights: Dict[str, float]
    initial_investment: float = 10000.0
    commission_pct: float = Field(
        default=0.001,
        ge=0.0,
        le=0.05,
        description="One-way commission as a fraction of traded notional (e.g. 0.001 = 0.10%)",
    )
    slippage_pct: float = Field(
        default=0.0005,
        ge=0.0,
        le=0.05,
        description="One-way slippage as a fraction of traded notional (e.g. 0.0005 = 0.05%)",
    )
    rebalance_freq: str = Field(
        default="monthly",
        description="Rebalance frequency: daily | weekly | monthly | quarterly",
    )

class BacktestDataPoint(BaseModel):
    date: str
    strategy: float
    benchmark: float

class BacktestResponse(BaseModel):
    data: List[BacktestDataPoint]
    gross_return: float
    total_return: float
    cost_drag: float
    total_costs_paid: float
    alpha: float
    beta: float
    max_drawdown: float
    rebalance_count: int
    avg_turnover: float
    benchmark_label: str = "60% SPY / 40% BND"


# ── Data / scheduler status ───────────────────────────────────────────────────

class CacheEntry(BaseModel):
    tickers: str
    start: str
    fetched_at: str
    age_seconds: int
    stale: bool

class ScheduledJob(BaseModel):
    id: str
    name: str
    next_run: Optional[str]

class RetrainResult(BaseModel):
    ticker: str
    status: str

class DataStatusResponse(BaseModel):
    cache: List[CacheEntry]
    scheduled_jobs: List[ScheduledJob]
    retrain_meta: Dict[str, Any]
