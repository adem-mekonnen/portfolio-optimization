"""
Performance report generator.

Runs the full pipeline end-to-end — portfolio optimisation, 1-year backtest,
and 30-day LSTM forecasts — then writes a self-contained Markdown report to
reports/performance_report_<date>.md.

Usage
-----
    python scripts/generate_report.py
    python scripts/generate_report.py --tickers TSLA SPY BND
    python scripts/generate_report.py --initial-investment 50000
    python scripts/generate_report.py --rebalance-freq weekly --output my_report.md
    python scripts/generate_report.py --no-forecast   # skip LSTM section

The script is intentionally self-contained: it imports directly from src/
rather than going through the HTTP API, so it works without a running server.
"""

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone

# ── Make sure src/ is importable when running from the repo root ──────────────
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from src.data_fetcher import fetch_data                          # noqa: E402
from src.portfolio_optimizer import optimize_portfolio           # noqa: E402
from src.backtester import run_backtest                          # noqa: E402
from src.model_inference import get_forecast                     # noqa: E402

# ── Defaults ──────────────────────────────────────────────────────────────────
DEFAULT_TICKERS     = ["TSLA", "SPY", "BND"]
DEFAULT_INVESTMENT  = 10_000.0
DEFAULT_FREQ        = "monthly"
DEFAULT_COMMISSION  = 0.001    # 0.10 %
DEFAULT_SLIPPAGE    = 0.0005   # 0.05 %
REPORTS_DIR         = os.path.join(_REPO_ROOT, "reports")
RISK_FREE_RATE      = 0.02     # 2 % annual, used for Sharpe display


# ── Formatting helpers ────────────────────────────────────────────────────────

def _pct(v: float, decimals: int = 2) -> str:
    return f"{v:.{decimals}f}%"

def _dollar(v: float) -> str:
    return f"${v:,.2f}"

def _sign(v: float) -> str:
    return f"+{v:.2f}%" if v >= 0 else f"{v:.2f}%"


# ── Section builders ──────────────────────────────────────────────────────────

def _section_header(title: str, level: int = 2) -> str:
    return f"\n{'#' * level} {title}\n"


def _build_overview(tickers: list[str], generated_at: str) -> str:
    lines = [
        _section_header("Overview"),
        f"| Field | Value |",
        f"|---|---|",
        f"| Generated | {generated_at} |",
        f"| Tickers | {', '.join(tickers)} |",
        f"| Risk-free rate | {_pct(RISK_FREE_RATE * 100)} |",
        "",
    ]
    return "\n".join(lines)


def _build_optimization(opt: dict, tickers: list[str]) -> str:
    lines = [
        _section_header("Portfolio Optimisation (Max Sharpe)"),
        "### Optimal Weights\n",
        "| Ticker | Weight |",
        "|---|---|",
    ]
    for t in tickers:
        w = opt["weights"].get(t, 0.0)
        lines.append(f"| {t} | {_pct(w * 100)} |")

    lines += [
        "",
        "### Expected Performance\n",
        "| Metric | Value |",
        "|---|---|",
        f"| Expected Annual Return | {_pct(opt['expected_return'] * 100)} |",
        f"| Annual Volatility      | {_pct(opt['volatility'] * 100)} |",
        f"| Sharpe Ratio           | {opt['sharpe_ratio']:.4f} |",
        "",
    ]
    return "\n".join(lines)


def _build_backtest(bt: dict, initial: float, freq: str) -> str:
    final_value = initial * (1 + bt["total_return"] / 100)
    lines = [
        _section_header("Backtest Results (1-Year)"),
        f"Rebalance frequency: **{freq}** · "
        f"Initial investment: **{_dollar(initial)}**\n",
        "### Returns\n",
        "| Metric | Value |",
        "|---|---|",
        f"| Gross Return (before costs) | {_sign(bt['gross_return'])} |",
        f"| Net Return  (after costs)   | {_sign(bt['total_return'])} |",
        f"| Cost Drag                   | -{_pct(bt['cost_drag'])} |",
        f"| Total Costs Paid            | {_dollar(bt['total_costs_paid'])} |",
        f"| Final Portfolio Value       | {_dollar(final_value)} |",
        "",
        "### Risk Metrics\n",
        "| Metric | Value |",
        "|---|---|",
        f"| Alpha (annualised) | {_sign(bt['alpha'])} |",
        f"| Beta               | {bt['beta']:.4f} |",
        f"| Max Drawdown       | {_pct(bt['max_drawdown'])} |",
        "",
        "### Execution\n",
        "| Metric | Value |",
        "|---|---|",
        f"| Rebalance Events | {bt['rebalance_count']} |",
        f"| Avg Turnover/Rebalance | {_pct(bt['avg_turnover'])} |",
        "",
        "> **Benchmark**: 60% SPY / 40% BND (buy-and-hold, no transaction costs).",
        "",
    ]
    return "\n".join(lines)


def _build_forecast(forecasts: dict[str, list]) -> str:
    lines = [_section_header("30-Day Price Forecasts (LSTM)")]
    for ticker, fc in forecasts.items():
        if not fc:
            lines.append(f"### {ticker}\n\n_No forecast available._\n")
            continue
        first = fc[0]
        last  = fc[-1]
        lines += [
            f"### {ticker}\n",
            f"| | Date | Price |",
            f"|---|---|---|",
            f"| Start | {first['date']} | {_dollar(first['predicted_price'])} |",
            f"| End   | {last['date']}  | {_dollar(last['predicted_price'])} |",
            f"| 30-day CI (last day) | — | "
            f"{_dollar(last['lower_bound'])} – {_dollar(last['upper_bound'])} |",
            "",
        ]
    return "\n".join(lines)


def _build_disclaimer() -> str:
    return (
        "\n---\n"
        "_This report is generated automatically for educational purposes only. "
        "It does not constitute financial advice. Past performance is not indicative "
        "of future results._\n"
    )


# ── Main pipeline ─────────────────────────────────────────────────────────────

def generate_report(
    tickers: list[str],
    initial_investment: float = DEFAULT_INVESTMENT,
    rebalance_freq: str = DEFAULT_FREQ,
    commission_pct: float = DEFAULT_COMMISSION,
    slippage_pct: float = DEFAULT_SLIPPAGE,
    include_forecast: bool = True,
    output_path: str | None = None,
) -> str:
    """
    Run the full pipeline and return the Markdown report as a string.
    Optionally write it to *output_path*.
    """
    generated_at = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    tickers = [t.upper() for t in tickers]

    print(f"\n{'='*60}")
    print(f"  GMF Investments — Report Generator")
    print(f"  Tickers : {tickers}")
    print(f"  Generated: {generated_at}")
    print(f"{'='*60}\n")

    # ── 1. Optimise ───────────────────────────────────────────────────────
    print("  [1/3] Running portfolio optimisation …")
    try:
        opt = optimize_portfolio(tickers)
    except Exception as exc:
        print(f"  ✗ Optimisation failed: {exc}", file=sys.stderr)
        sys.exit(1)
    weight_summary = {t: f"{opt['weights'].get(t, 0) * 100:.1f}%" for t in tickers}
    print(f"       Max Sharpe weights: {weight_summary}")

    # ── 2. Backtest ───────────────────────────────────────────────────────
    print("  [2/3] Running 1-year backtest …")
    start_date = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
    try:
        prices = fetch_data(tickers, start=start_date)
        if prices is None or prices.empty:
            raise ValueError("No price data returned.")
        prices = prices.dropna()
        bt = run_backtest(
            prices             = prices,
            target_weights     = opt["weights"],
            initial_investment = initial_investment,
            commission_pct     = commission_pct,
            slippage_pct       = slippage_pct,
            rebalance_freq     = rebalance_freq,
        )
    except Exception as exc:
        print(f"  ✗ Backtest failed: {exc}", file=sys.stderr)
        sys.exit(1)
    print(f"       Net return: {_sign(bt['total_return'])}  |  Max DD: {_pct(bt['max_drawdown'])}")

    # ── 3. Forecasts ──────────────────────────────────────────────────────
    forecasts: dict[str, list] = {}
    if include_forecast:
        print("  [3/3] Generating 30-day LSTM forecasts …")
        for t in tickers:
            try:
                result = get_forecast(t)
                forecasts[t] = result["forecast"]
                last = result["forecast"][-1]
                print(f"       {t}: last predicted price {_dollar(last['predicted_price'])}")
            except Exception as exc:
                print(f"       ⚠  Forecast failed for {t}: {exc}", file=sys.stderr)
                forecasts[t] = []
    else:
        print("  [3/3] Skipping forecasts (--no-forecast).")

    # ── 4. Assemble Markdown ──────────────────────────────────────────────
    title = f"# GMF Investments — Performance Report\n"
    body  = "".join([
        title,
        _build_overview(tickers, generated_at),
        _build_optimization(opt, tickers),
        _build_backtest(bt, initial_investment, rebalance_freq),
        _build_forecast(forecasts) if include_forecast else "",
        _build_disclaimer(),
    ])

    # ── 5. Write to disk ──────────────────────────────────────────────────
    if output_path is None:
        date_str    = datetime.now().strftime("%Y%m%d")
        output_path = os.path.join(REPORTS_DIR, f"performance_report_{date_str}.md")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(body)

    print(f"\n  ✓ Report written → {output_path}\n")
    return body


# ── CLI ───────────────────────────────────────────────────────────────────────

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Generate a Markdown performance report.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument(
        "--tickers", nargs="+", default=DEFAULT_TICKERS,
        metavar="TICKER",
    )
    p.add_argument(
        "--initial-investment", type=float, default=DEFAULT_INVESTMENT,
        metavar="DOLLARS",
    )
    p.add_argument(
        "--rebalance-freq", default=DEFAULT_FREQ,
        choices=["daily", "weekly", "monthly", "quarterly"],
    )
    p.add_argument(
        "--commission-bps", type=float, default=DEFAULT_COMMISSION * 10_000,
        metavar="BPS",
        help="One-way commission in basis points (e.g. 10 = 0.10%%).",
    )
    p.add_argument(
        "--slippage-bps", type=float, default=DEFAULT_SLIPPAGE * 10_000,
        metavar="BPS",
        help="One-way slippage in basis points (e.g. 5 = 0.05%%).",
    )
    p.add_argument(
        "--no-forecast", action="store_true",
        help="Skip the LSTM forecast section.",
    )
    p.add_argument(
        "--output", default=None,
        metavar="PATH",
        help="Output file path. Defaults to reports/performance_report_<date>.md.",
    )
    return p.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    generate_report(
        tickers            = args.tickers,
        initial_investment = args.initial_investment,
        rebalance_freq     = args.rebalance_freq,
        commission_pct     = args.commission_bps / 10_000,
        slippage_pct       = args.slippage_bps  / 10_000,
        include_forecast   = not args.no_forecast,
        output_path        = args.output,
    )
