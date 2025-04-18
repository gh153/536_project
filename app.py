from flask import Flask, render_template, request, redirect, url_for
import requests
import sqlite3
import datetime
import numpy as np
import pandas as pd
import cvxopt as opt
from cvxopt import solvers
import yfinance as yf

app = Flask(__name__)

assets = pd.read_csv('data/SP500Data.csv', index_col=0)
missing_fractions = assets.isnull().mean().sort_values(ascending=False)
drop_list = sorted(list(missing_fractions[missing_fractions > 0.3].index))
assets.drop(labels=drop_list, axis=1, inplace=True)
assets = assets.ffill()
assets.rename(index=lambda x: pd.to_datetime(x), inplace=True)

# Database connection helper
def get_db_connection():
    conn = sqlite3.connect('stocks.db')
    conn.row_factory = sqlite3.Row
    return conn

# Function to get the latest balance from the database
def get_latest_balance():
    conn = get_db_connection()
    balance = conn.execute('SELECT balance FROM balance ORDER BY date DESC LIMIT 1').fetchone()
    conn.close()
    return balance

# Function to set or update the balance in the database
def set_balance(new_balance):
    conn = get_db_connection()
    current_date = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    conn.execute('INSERT INTO balance (date, balance) VALUES (?, ?)', (current_date, new_balance))
    conn.commit()
    conn.close()

# Initialize the database if it's the first time
def initialize_balance():
    conn = get_db_connection()
    balance = conn.execute('SELECT COUNT(*) FROM balance').fetchone()[0]
    if balance == 0:
        set_balance(100000)
    conn.close()

@app.route('/')
def index():
    # Initialize the database on first launch
    initialize_balance()

    # Get the latest balance from the database
    balance = get_latest_balance()

    if not balance:
        set_balance(100000)
        balance = get_latest_balance()

    # Render the index page with the balance and available columns
    columns = assets.columns.tolist()
    default_columns = ['GOOGL', 'FB', 'GS', 'MS', 'GE', 'MSFT']
    
    # On page load, do not calculate allocation; we only show the form
    return render_template('index.html', balance=balance['balance'], columns=columns, default_columns=default_columns, alloc=None)

@app.route('/rebalance', methods=['POST'])
def portfolio_selection():
    # Retrieve the form data
    risk_tolerance = float(request.form['risk_tolerance']) # Normalize risk tolerance between 0 and 1
    selected_columns = request.form.getlist('selected_columns')

    # Call get_asset_allocation to get the allocation
    Alloc, _ = get_asset_allocation(risk_tolerance, selected_columns)

    # Convert the allocation to a dictionary for easy display in HTML
    alloc_dict = Alloc.to_dict().get(0, {})  # Convert DataFrame column to dictionary
    for stock in alloc_dict.keys():
        alloc_dict[stock] = np.round(alloc_dict[stock] * 100, 1)

    # Pass the allocation data to the template
    return render_template('index.html', alloc=alloc_dict, balance=get_latest_balance()['balance'], columns=assets.columns.tolist(), default_columns=['GOOGL', 'FB', 'GS', 'MS', 'GE', 'MSFT'])

def get_asset_allocation(riskTolerance, stock_ticker):
    assets = pd.read_csv('data/SP500Data.csv', index_col=0)
    missing_fractions = assets.isnull().mean().sort_values(ascending=False)
    drop_list = sorted(list(missing_fractions[missing_fractions > 0.3].index))
    assets.drop(labels=drop_list, axis=1, inplace=True)
    # Fill the missing values with the last value available in the dataset.
    assets=assets.ffill()
    dates = (assets.index.to_series()).apply(lambda x: pd.to_datetime(x))
    assets.rename(index=lambda x: pd.to_datetime(x), inplace=True)

    assets_selected = assets.loc[:, stock_ticker]
    return_vec = np.array(assets_selected.pct_change().dropna(axis=0)).T
    n = len(return_vec)
    mus = 1 - riskTolerance

    # Convert to cvxopt matrices
    S = opt.matrix(np.cov(return_vec))
    pbar = opt.matrix(np.mean(return_vec, axis=1))

    # Create constraint matrices
    G = -opt.matrix(np.eye(n))  # negative n x n identity matrix
    h = opt.matrix(0.0, (n, 1))
    A = opt.matrix(1.0, (1, n))
    b = opt.matrix(1.0)

    # Calculate efficient frontier weights using quadratic programming
    portfolios = solvers.qp(mus * S, -pbar, G, h, A, b)
    w = portfolios['x'].T
    Alloc = pd.DataFrame(
        data=np.array(portfolios['x']),
        index=assets_selected.columns
    )

    # Calculate efficient frontier weights using quadratic programming
    returns_final = (np.array(assets_selected) * np.array(w))
    returns_sum = np.sum(returns_final, axis=1)
    returns_sum_pd = pd.DataFrame(returns_sum, index=assets.index)
    returns_sum_pd = returns_sum_pd - returns_sum_pd.iloc[0, :] + 100
    return Alloc, returns_sum_pd

def get_latest_close_price(stock_symbol):
    stock = yf.Ticker(stock_symbol)

    # Get the historical market data (default: last 5 days)
    historical_data = stock.history(period='1d')  # '1d' fetches the latest day's data
    print(historical_data)
    return float(historical_data['Close'])
    """
    except requests.exceptions.RequestException as e:
        print("Error fetching data:", e)
        return None
    """

def calculate_shares_to_buy(stock_symbol, amount_to_spend):
    # Get the latest price for the stock (assumed to be in the assets DataFrame)
    latest_price = get_latest_close_price(stock_symbol)
    num_shares = amount_to_spend // latest_price  # Integer division to get the number of shares
    return int(num_shares)

@app.route('/buy_stock', methods=['POST'])
def buy_stock():
    stock_symbol = request.form['stock_symbol']
    amount_to_spend = float(request.form['amount_to_spend'])

    # Get the latest balance
    balance = get_latest_balance()

    # Check if the user has enough balance
    if balance['balance'] < amount_to_spend:
        error_message = "Insufficient balance"
        return render_template('index.html', alloc = None, balance=balance['balance'], error=error_message, columns=assets.columns.tolist(), default_columns=['GOOGL', 'FB', 'GS', 'MS', 'GE', 'MSFT'])

    # Calculate how many shares the user can buy
    num_shares = calculate_shares_to_buy(stock_symbol, amount_to_spend)

    if num_shares == 0:
        error_message = "Insufficient balance to buy any shares of this stock"
        return render_template('index.html', alloc = None, balance=balance['balance'], error=error_message, columns=assets.columns.tolist(), default_columns=['GOOGL', 'FB', 'GS', 'MS', 'GE', 'MSFT'])

    # Update balance: Deduct the amount spent on the stock
    latest_price = get_latest_close_price(stock_symbol)
    new_balance = balance['balance'] - (num_shares * latest_price)  # Last price for the stock
    set_balance(new_balance)

    # Record the transaction in the database
    conn = get_db_connection()
    current_date = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    conn.execute('''
    INSERT INTO stocks (stock_symbol, share_num, amount_spent, date)
    VALUES (?, ?, ?, ?)
    ''', (stock_symbol, num_shares, num_shares * latest_price, current_date))
    conn.commit()
    conn.close()

    # Redirect back to the index page with updated balance and transaction message
    success_message = f"Successfully bought {num_shares} shares of {stock_symbol} for ${amount_to_spend:.2f}"
    return render_template('index.html', alloc = None, balance=new_balance, success_message=success_message, columns=assets.columns.tolist(), default_columns=['GOOGL', 'FB', 'GS', 'MS', 'GE', 'MSFT'])

@app.route('/check_stocks', methods=['GET'])
def check_all_stocks():
    # Query to sum the shares of each stock symbol in the transaction table
    conn = get_db_connection()
    stock_data = conn.execute('''
        SELECT stock_symbol, SUM(share_num) AS total_shares
        FROM stocks
        GROUP BY stock_symbol
        HAVING total_shares > 0
        ORDER BY stock_symbol
    ''').fetchall()
    conn.close()

    # If no stocks are found, set an error message
    if not stock_data:
        error_message = "No stocks found in your portfolio."
        return render_template('index.html', alloc=None, balance=get_latest_balance()['balance'], error=error_message, columns=assets.columns.tolist(), default_columns=['GOOGL', 'FB', 'GS', 'MS', 'GE', 'MSFT'])

    # Pass the stock data to the template if stocks are found
    return render_template('index.html', alloc=None, balance=get_latest_balance()['balance'], stock_data=stock_data, columns=assets.columns.tolist(), default_columns=['GOOGL', 'FB', 'GS', 'MS', 'GE', 'MSFT'])

@app.route('/sell_stock', methods=['POST'])
def sell_stock():
    stock_symbol = request.form['stock_symbol']
    share_amount = int(request.form['share_amount'])

    # Get the latest balance
    balance = get_latest_balance()

    # Query the current amount of shares the user has for the specified stock
    conn = get_db_connection()
    stock_data = conn.execute('''
        SELECT SUM(share_num) AS total_shares
        FROM stocks
        WHERE stock_symbol = ?
        GROUP BY stock_symbol
    ''', (stock_symbol,)).fetchone()
    conn.close()

    # If no records are found for the stock or the user has insufficient shares
    if stock_data is None or stock_data['total_shares'] < share_amount:
        error_message = "You do not have enough shares to sell."
        return render_template('index.html', alloc=None, balance=balance['balance'], error=error_message, columns=assets.columns.tolist(), default_columns=['GOOGL', 'FB', 'GS', 'MS', 'GE', 'MSFT'])

    # Proceed with the sale: Deduct the balance for the shares being sold
    latest_price = float(get_latest_close_price(stock_symbol))
    new_balance = balance['balance'] + (share_amount * latest_price)  # Add the proceeds from the sale

    # Update balance in the database
    set_balance(new_balance)

    # Record the transaction in the database with negative share amount
    conn = get_db_connection()
    current_date = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    conn.execute('''
    INSERT INTO stocks (stock_symbol, share_num, amount_spent, date)
    VALUES (?, ?, ?, ?)
    ''', (stock_symbol, -share_amount, -share_amount * latest_price, current_date))
    conn.commit()
    conn.close()

    # Redirect back to the index page with updated balance and transaction message
    success_message = f"Successfully sold {share_amount} shares of {stock_symbol} for ${share_amount * latest_price:.2f}"
    return render_template('index.html', alloc=None, balance=new_balance, success_message=success_message, columns=assets.columns.tolist(), default_columns=['GOOGL', 'FB', 'GS', 'MS', 'GE', 'MSFT'])
if __name__ == '__main__':
    app.run(debug=True)
