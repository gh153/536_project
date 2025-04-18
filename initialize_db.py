import sqlite3
import datetime

# Function to create the balance table if it doesn't exist
def initialize_balance_db():
    conn = sqlite3.connect('stocks.db')
    c = conn.cursor()

    # Create balance table if it doesn't exist
    c.execute('''
        CREATE TABLE IF NOT EXISTS balance (
            date TEXT NOT NULL,
            balance REAL NOT NULL
        )
    ''')

    # Check if the balance table is empty (first run)
    c.execute('SELECT COUNT(*) FROM balance')
    if c.fetchone()[0] == 0:
        # Insert initial balance of 100000
        initial_balance = 100000
        current_date = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        c.execute('INSERT INTO balance (date, balance) VALUES (?, ?)', (current_date, initial_balance))
        print(f"Initial balance of {initial_balance} inserted with date {current_date}.")
    else:
        print("Balance table already initialized.")

    # Commit the transaction and close the connection
    conn.commit()
    conn.close()

# Initialize the transaction table if it doesn't exist
def initialize_transaction_table():
    """ Create the stock table to track stock purchases """
    conn = sqlite3.connect('stocks.db')
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS stocks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stock_symbol TEXT NOT NULL,
            share_num INTEGER NOT NULL,
            amount_spent REAL NOT NULL,
            date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


if __name__ == '__main__':
    initialize_balance_db()
    initialize_transaction_table()