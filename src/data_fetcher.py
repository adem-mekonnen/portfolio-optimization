import yfinance as yf
import pandas as pd
import os

def fetch_data(tickers, start, end):
    # Use auto_adjust=True to automatically handle dividends and splits.
    # This renames the adjusted price column to simply 'Close'.
    data = yf.download(tickers, start=start, end=end, auto_adjust=True)
    
    # If the download is successful, 'Close' now contains the Adjusted Close prices.
    if 'Close' in data.columns:
        return data['Close']
    else:
        # Fallback in case auto_adjust is ignored by the API
        return data['Adj Close']

if __name__ == "__main__":
    # Create data directory if it doesn't exist
    if not os.path.exists('data'):
        os.makedirs('data')

    tickers = ['TSLA', 'BND', 'SPY']
    print(f"Downloading data for {tickers}...")
    
    try:
        df = fetch_data(tickers, '2015-01-01', '2026-01-15')
        
        if df.empty:
            print("No data downloaded. Check your internet connection or ticker symbols.")
        else:
            df.to_csv('data/tsla_bnd_spy_raw.csv')
            print("Successfully saved data to data/tsla_bnd_spy_raw.csv")
            print(df.head()) # Verify the data
            
    except Exception as e:
        print(f"An error occurred: {e}")