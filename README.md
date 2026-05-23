# GMF Investments: Time Series Forecasting & Portfolio Optimization

**Author:** Adem M  
**Role:** Financial Analyst Intern  
**Date:** January 27, 2026  
**Project Status:** Completed

---

## 1. Project Overview
Guide Me in Finance (GMF) Investments specializes in data-driven portfolio management. This project integrates **Time Series Forecasting** with **Modern Portfolio Theory (MPT)** to predict market trends for Tesla (TSLA) and construct an optimized investment portfolio including the S&P 500 (SPY) and the Vanguard Total Bond Market ETF (BND).

---

## 2. Installation & Setup

### Option A — Docker (recommended, one command)
Requires [Docker Desktop](https://www.docker.com/products/docker-desktop/) (or Docker Engine + Compose plugin).

```bash
git clone https://github.com/your-username/portfolio-optimization.git
cd portfolio-optimization

# (Optional) copy and edit environment variables
cp .env.example .env

# Build images and start the full stack
docker compose up --build
```

| Service | URL |
|---|---|
| Frontend (React) | http://localhost |
| Backend API (FastAPI) | http://localhost:8000 |
| API docs (Swagger) | http://localhost:8000/docs |

To stop: `docker compose down`  
To stop and remove volumes: `docker compose down -v`

---

### Option B — Local development (manual)
1. **Clone the repository:**
   ```bash
   git clone https://github.com/your-username/portfolio-optimization.git
   ```
2. **Backend — install Python dependencies:**
   ```bash
   pip install -r backend_requirements.txt
   ```
3. **Train models** (first time only):
   ```bash
   python -m src.train_models
   ```
4. **Start the API:**
   ```bash
   uvicorn src.main:app --reload
   ```
5. **Frontend — install and start:**
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

---

## 3. Implementation Details

### Task 1 & 2: Data Preprocessing & Modeling
*   **Cleaning:** Handled MultiIndex headers from YFinance and cleaned missing values.
*   **Forecasting:** Developed and compared **SARIMA** and **LSTM** models. The LSTM model was selected for the final forecast due to its superior ability to capture non-linear volatility in Tesla's stock price.

### Task 3 & 4: Future Trends & Optimization
*   **Forecast:** Projected TSLA price 30 days into the future using the trained LSTM model (autoregressive rolling inference).
*   **Optimization:** Used **PyPortfolioOpt** to find the Maximum Sharpe Ratio portfolio.
*   **Optimal Weights (Max Sharpe):** BND **56.5%** · SPY **38.1%** · TSLA **5.4%**
*   **Recommendation:** A portfolio heavily weighted toward SPY (38.1%) and BND (56.5%) to hedge against TSLA's high idiosyncratic volatility, while retaining a small TSLA allocation (5.4%) for growth exposure.

### Task 5: Strategy Performance Analysis & Conclusion
**Performance Comparison (1-Year Out-of-Sample: 2025–2026):**  
The model-driven optimized portfolio achieved a total return of **+16.00%**, while the passive benchmark (60/40 SPY/BND) returned **+19.70%**. On a risk-adjusted basis, our strategy yielded a Sharpe Ratio of **1.42**, compared to the benchmark's **1.69**. This indicates that the forecasting-based approach was **less** efficient at generating returns per unit of risk over this specific one-year window — primarily because the conservative bond-heavy allocation (56.5% BND) dampened upside during a strong equity rally.

**Risk & Drawdown:**  
The strategy experienced a Maximum Drawdown of **-5.09%**. The high BND allocation successfully limited downside exposure, with the strategy showing a Beta of **0.86** relative to the benchmark — confirming lower market sensitivity. The Annualized Alpha was **-0.62%**, reflecting a slight underperformance versus the benchmark on a risk-adjusted basis.

**Strategy Limitations & Reality Check:**  
While the backtest results are statistically significant, the following limitations must be noted:
*   **Sample Length:** The one-year out-of-sample period (2025-2026) is relatively short and may not reflect performance during different interest rate cycles.
*   **Transaction Costs:** The default simulation uses 0.10% commission and 0.05% slippage per side, but these are configurable. Real-world costs vary by broker and asset liquidity and would reduce net alpha further.
*   **Model Risk:** Tesla is subject to high idiosyncratic risk (Elon Musk's public statements, regulatory changes). Time-series models cannot predict "Black Swan" events that deviate from historical patterns.

---

## 4. Project Structure
```text
portfolio-optimization/
├── .github/workflows/
│   └── unittests.yml          # CI: pytest on every push/PR
├── docker/
│   └── nginx.conf             # nginx config for the frontend container
├── frontend/                  # React + Vite + Tailwind SPA
│   ├── src/
│   │   ├── api.ts             # Centralised API base URL (reads VITE_API_URL)
│   │   ├── App.tsx
│   │   └── components/
├── models/                    # Trained LSTM models + scalers (gitignored)
│   ├── TSLA_lstm.keras
│   ├── TSLA_scaler.pkl
│   └── ...
├── src/                       # FastAPI backend
│   ├── main.py                # API routes
│   ├── model_inference.py     # LSTM inference + mock fallback
│   ├── portfolio_optimizer.py # PyPortfolioOpt (Max Sharpe)
│   ├── data_fetcher.py        # yfinance wrapper with joblib cache
│   ├── train_models.py        # LSTM training script
│   └── schemas.py             # Pydantic request/response models
├── tests/                     # pytest unit tests
├── .dockerignore
├── .env.example               # Environment variable template
├── backend_requirements.txt   # Slim production Python deps
├── docker-compose.yml         # One-command full-stack launcher
├── Dockerfile.backend         # Multi-stage Python/FastAPI image
├── Dockerfile.frontend        # Multi-stage Node → nginx image
└── requirements.txt           # Full dev deps (includes Jupyter)
```

---

## 5. Key Findings
*   **Diversification:** Integrating BND (Bonds) into the Tesla-heavy strategy successfully lowered the portfolio's overall Value at Risk (VaR) and limited maximum drawdown to **-5.09%**, compared to a higher drawdown in an equity-only allocation.
*   **Deep Learning vs Stats:** The LSTM model adapted more quickly to the "regime shifts" in Tesla's 2025 price action compared to the linear nature of SARIMA.
*   **Backtesting:** The optimized strategy returned **+16.00%** vs the passive 60/40 benchmark's **+19.70%** over the 2025–2026 out-of-sample window. The strategy underperformed on total return — the conservative BND-heavy allocation (56.5%) dampened upside during a strong equity rally — but delivered a lower Beta (**0.86**) and shallower drawdown, confirming the risk-reduction objective was met. On a risk-adjusted basis the strategy's Sharpe Ratio of **1.42** trailed the benchmark's **1.69**, reflecting the cost of defensiveness in a bull market.

Disclaimer: This project is for educational purposes and does not constitute professional financial advice.

