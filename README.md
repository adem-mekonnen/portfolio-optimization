
# GMF Investments: Time Series Forecasting & Portfolio Optimization

**Author:** Adem M  
**Role:** Financial Analyst Intern  
**Date:** January 27, 2026  
**Project Status:** Completed (Tasks 1–5)

## 1. Project Overview
Guide Me in Finance (GMF) Investments specializes in data-driven portfolio management. This project integrates **Time Series Forecasting** with **Modern Portfolio Theory (MPT)** to predict market trends for Tesla (TSLA) and construct an optimized investment portfolio including the S&P 500 (SPY) and the Vanguard Total Bond Market ETF (BND).

### Business Objective
*   Forecast future prices of high-volatility assets (TSLA).
*   Optimize asset allocation to maximize risk-adjusted returns (Sharpe Ratio).
*   Validate strategies through rigorous backtesting against a passive 60/40 benchmark.

## 2. Installation & Setup
To run the analysis locally, ensure you have Python 3.9+ installed and follow these steps:

1. **Clone the repository:**
   ```bash
   git clone https://github.com/your-username/portfolio-optimization.git
   cd portfolio-optimization
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

## 3. Data Description
*   **Assets:** TSLA (High Growth), BND (Bonds/Stability), SPY (Market Index).
*   **Source:** YFinance API.
*   **Period:** January 1, 2015 – January 15, 2026.
*   **Target Column:** `Adj Close` (Adjusted for splits and dividends).

## 4. Implementation Details

### Task 1: Preprocessing & EDA
*   **Data Cleaning:** Handled MultiIndex headers and missing values.
*   **Stationarity:** Applied Augmented Dickey-Fuller (ADF) tests; confirmed raw prices are non-stationary while daily returns are stationary.
*   **Volatility:** Computed rolling statistics and outlier detection to identify periods of high market stress.

### Task 2: Time Series Forecasting
*   **SARIMA:** Statistical model optimized using `auto_arima`.
*   **LSTM:** Deep Learning model with a 60-day window to capture non-linear market regimes.
*   **Performance:** LSTM generally provided lower RMSE, adapting faster to Tesla's high volatility.

### Task 3: Future Trends (6-12 Months)
*   Generated a 12-month forecast into 2027.
*   **Insights:** Identified a [Bullish/Bearish] trend with widening confidence intervals, indicating increasing uncertainty over longer time horizons.

### Task 4: Portfolio Optimization
*   Utilized **PyPortfolioOpt** to calculate the **Efficient Frontier**.
*   **Result:** Recommended the **Maximum Sharpe Ratio Portfolio**, balancing the forecasted growth of TSLA with the stability of BND.

### Task 5: Backtesting
*   Simulated the optimized strategy using data from Jan 2025 – Jan 2026.
*   **Benchmark:** Compared against a static 60% SPY / 40% BND portfolio.
*   **Outcome:** Evaluated Total Return, Max Drawdown, and Sharpe Ratio to confirm strategy viability.

## 5. Project Structure
```text
portfolio-optimization/
├── .gitignore                # Prevents tracking of large data and venv files
├── README.md                 # Project summary and final report
├── requirements.txt          # List of Python dependencies
├── data/
│   └── processed/            # Cleaned CSV files
├── notebooks/
│   ├── 1_eda_preprocessing.ipynb
│   ├── 2_forecasting_models.ipynb
│   ├── 3_optimization_backtesting.ipynb
└── src/
    └── __init__.py           # Modularized scripts for reuse
```

## 6. Key Findings
*   **Forecasting:** While stock prices follow a "Random Walk" in the short term, LSTM models successfully captured the cyclical momentum of Tesla.
*   **Diversification:** Including BND significantly lowered the portfolio's Value at Risk (VaR), despite Tesla's aggressive price swings.
*   **Backtest:** The model-driven approach provided superior risk-adjusted returns during the 2025 market environment compared to a passive strategy.

## 7. Contact
**Adem M**  
Financial Analyst Intern | GMF Investments  


*Disclaimer: This project is for educational purposes and does not constitute professional financial advice.*