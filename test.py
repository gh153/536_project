import yfinance as yf

if __name__ == "__main__":

    # Define the stock ticker symbol
    ticker_symbol = 'GOOGL'  # Example: Apple Inc.

    # Fetch the stock data using yfinance
    stock = yf.Ticker(ticker_symbol)

    # Get the historical market data (default: last 5 days)
    historical_data = stock.history(period='1d')  # '1d' fetches the latest day's data
    print(historical_data)
    print(historical_data.columns)
    
    # Extract the latest close price
    latest_close_price = historical_data['Close'].iloc[0]
    print(float(latest_close_price))
    print(f"The latest close price of {ticker_symbol} is: {latest_close_price}")
