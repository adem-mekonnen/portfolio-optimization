# GMF Investments: Time Series Forecasting & Portfolio Optimization

**Author:** Adem M
**Role:** Financial Analyst Intern  
**Date:** January 26, 2026  
**Status:** Interim Submission (Task 1 & 2 In-Progress)

---

## 1. Executive Summary
This project aims to enhance GMF Investments' portfolio management strategies by integrating advanced time series forecasting. We are analyzing historical data for **Tesla (TSLA)**, **Vanguard Total Bond Market ETF (BND)**, and **S&P 500 ETF (SPY)** to forecast future market trends and optimize asset allocation using Modern Portfolio Theory (MPT).

This interim report documents the data preprocessing, exploratory analysis, and initial modeling phases.

## 2. Data Extraction & Cleaning
**Data Source:** YFinance API  
**Period:** Jan 1, 2015 – Jan 15, 2026

**Methodology:**
*   extracted daily historical data for TSLA, BND, and SPY.
*   **Handling Splits/Dividends:** Addressed changes in `yfinance` versioning by explicitly disabling auto-adjustment (`auto_adjust=False`) to ensure the retrieval of the 'Adj Close' column.
*   **Cleaning:** Checked for missing values (NaNs) and aligned dates across all assets.
*   **Feature Engineering:** Calculated Daily Returns (`pct_change`) to normalize data for volatility analysis.

## 3. Exploratory Data Analysis (EDA) & Risk Metrics

### Volatility Analysis
Visual inspection of Rolling Standard Deviation (30-day window) reveals distinct risk profiles:
*   **TSLA:** Exhibits high volatility with significant spikes during earnings reports and market stress events. It represents the high-risk/high-reward component.
*   **BND:** Shows extremely low volatility, confirming its role as a stabilizer in the portfolio.
*   **SPY:** Demonstrates moderate volatility, serving as the market benchmark.

### Risk Metrics
*   **Value at Risk (VaR):** TSLA has the deepest tail risk (highest VaR), indicating potential for significant short-term losses compared to the stable BND.
*   **Sharpe Ratio:** Historical analysis suggests TSLA provides high returns but at a "cost" of high variance, whereas BND offers lower but consistent risk-adjusted returns.

## 4. Stationarity Analysis
To prepare for ARIMA modeling, we performed the **Augmented Dickey-Fuller (ADF)** test:

*   **Raw Prices:** p-value > 0.05. The raw price series is **Non-Stationary**. It has a time-dependent structure (trend).
*   **Daily Returns:** p-value < 0.05. The returns series is **Stationary**.
*   **Implication:** We must use differencing (`d=1`) when building the ARIMA model to ensure statistical validity.

## 5. Forecasting Models (Initial Progress)
We have implemented the baseline **ARIMA (AutoRegressive Integrated Moving Average)** model for Tesla (TSLA).

*   **Train/Test Split:** 
    *   *Train:* 2015-01-01 to 2024-12-31
    *   *Test:* 2025-01-01 to 2026-01-15
*   **Model Selection:** Used `pmdarima.auto_arima` to minimize AIC.
*   **Current Results:** The model successfully generated a forecast for the test period.
*   **Error Analysis:** We addressed initial metric evaluation errors by strictly aligning the forecast index with the test data index, removing gaps (weekends/holidays) before calculating RMSE.

## 6. Next Steps
1.  **Deep Learning:** Complete the training and tuning of the Long Short-Term Memory (LSTM) model to capture non-linear patterns.
2.  **Comparison:** Select the best performing model (ARIMA vs. LSTM) based on RMSE/MAE.
3.  **Optimization:** Construct the Efficient Frontier using the forecasted returns and historical covariance.
4.  **Backtesting:** Simulate the strategy performance against a standard 60/40 benchmark.

### Part 2: Review of Your Folder Structure

**Verdict:** It is **90% Correct**, but there is one small adjustment needed for "Best Practices."

Currently, it looks like your `README.md` and `.gitignore` are **inside** the `notebooks` folder.

**The Fix:**
You should move `README.md`, `.gitignore`, and `requirements.txt` (if you have one) **UP** one level, to the main `portfolio-optimization` folder.

**Why?**
When someone opens your repository on GitHub, GitHub looks for the `README.md` in the **Root** (main) folder to display the front page. If it's hidden inside `notebooks/`, the main page will just show a list of folders, which looks less professional.

**Recommended Final Structure:**

```text
portfolio-optimization/       <-- ROOT FOLDER
├── .gitignore                <-- Move here
├── README.md                 <-- Move here (The file above)
├── requirements.txt          <-- Move here
├── data/                     <-- (Optional, but good practice if you have it)
│   ├── raw/
│   └── processed/
└── notebooks/                <-- Keep your code here
    ├── 1_data_extraction.ipynb
    ├── 1_eda_and_preprocessing.ipynb
    └── 2_forecasting.ipynb
```

**How to fix it in VS Code / File Explorer:**
Simply drag and drop the `README.md` and `.gitignore` files from the `notebooks` folder into the main `portfolio-optimization` folder. Then commit and push again!
