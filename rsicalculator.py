# Import required libraries

import requests                     # For making HTTP requests to APIs
import pandas as pd                 # For data manipulation and handling of CSVs
import numpy as np                  # For numerical operations
from datetime import datetime       # For timestamp creation
import time                         # For adding delays between API calls
import logging                      # For logging information and potential errors
from typing import List, Dict       # For type hints
import random                       # For generating random numbers
import string                       # For generating random strings

# This will configure logging and show timestamp, level, and message

logging.basicConfig(
    level=logging.INFO,                                     # Set a minimum logging level
    format='%(asctime)s - %(levelname)s - %(message)s'      # Define the log message format
)

class CryptoRSITracker:
    def __init__(self, symbol: str = 'BTC/USDT', period: int = 14, api_delay: int = 60):
        """
        Initialize the RSI trackerwith config parameters
        
        Args:
            symbol: Trading pair symbol (default: 'BTC/USDT')
            period: RSI period (default: 14)
            api_delay: Delay between API calls in seconds (default: 60)
        """
        self.symbol = symbol             # The trading pair that is being tracked
        self.period = period             # The period for RSI calculations
        self.api_delay = api_delay       # Time between API calls   
        self.prices: List[float] = []    # An empty list where historical prices are stored   
        self.csv_filename = f'{symbol.replace("/", "_")}_rsi_log.csv' # Create a filename for CSV and replacing / with _ symbol
        
        # Generate a random 32 character ID for API requests
        self.client_id = ''.join(random.choices(string.ascii_letters + string.digits, k=32))
        
        # Setup headers for API requests
        self.headers = {
            'User-Agent': f'crypto-rsi-tracker-{self.client_id}',       # Identify the script being used
            'Accept': 'application/json',                               # Request JSON
            'X-MBX-APIKEY': None                                        # Placeholder for API key
        }
        
        # Create CSV file if it doesn't exist
        try:
            pd.read_csv(self.csv_filename)                  # Trying to read existing file
        except FileNotFoundError:
            # Create new file with headers if it doesn't exist
            pd.DataFrame(columns=['timestamp', 'price', 'rsi']).to_csv(
                self.csv_filename, index=False
            )
            
    def fetch_price(self) -> float:                 
        """Fetch current price from Binance API"""
        try:
            symbol = self.symbol.replace('/', '').upper()       # Removes / and converts symbol to uppercase for API (BTC/USDT -> BTCUSDT)
            
            # First attempt: Binance.US API
            try:
                # Constructing Binance.US API URL
                url = f'https://api.binance.us/api/v3/ticker/price?symbol={symbol}'
                # Make GET request with headers and a 10 second timeout
                response = requests.get(url, headers=self.headers, timeout=10)
                # Check for HTTP errors
                response.raise_for_status()
                # Extract and return the price as float
                return float(response.json()['price'])
            except requests.exceptions.RequestException:
                # If Binance.US fails, try alternative API (CoinGecko)
                # Converting symbol to CoinGecko format (BTC/USDT -> bitcoin)
                coin_id = 'bitcoin' if 'BTC' in symbol else symbol.lower().split('usdt')[0]
                # Construct CoinGecko API URL
                url = f'https://api.coingecko.com/api/v3/simple/price?ids={coin_id}&vs_currencies=usd'
                # Make GET request
                response = requests.get(url, headers=self.headers, timeout=10)
                response.raise_for_status()
                # Extract and return price
                return float(response.json()[coin_id]['usd'])
                
        except requests.exceptions.RequestException as e:
            # Log and reraise network/API errors
            logging.error(f'Error fetching price: {str(e)}')
            raise
        except (KeyError, ValueError) as e:
            # Log and reraise data parsing errors
            logging.error(f'Error parsing API response: {str(e)}')
            raise
        except Exception as e:
            # Log and reraise any other errors
            logging.error(f'Unexpected error: {str(e)}')
            raise

    def calculate_rsi(self, prices: List[float]) -> float:
        # Check for enough data points
        if len(prices) < self.period + 1:
            return None
            
        # Calculate price changes between periods
        deltas = np.diff(prices)
        
        # Separate gains and losses (creating an array of positive and negative changes)
        gains = np.where(deltas > 0, deltas, 0) # If change is positive, keep it; else 0
        losses = np.where(deltas < 0, -deltas, 0) # If change is negative, make positive; else 0
        
        # Calculate average gains and losses over the period
        avg_gain = np.mean(gains[-self.period:])     # Average of latest period's gain
        avg_loss = np.mean(losses[-self.period:])    # Average of latest period's losses
        
        # Can't divide by 0
        if avg_loss == 0:
            return 100.0
            
        # Calculation of RSI 
        rs = avg_gain / avg_loss                #Relative strength
        rsi = 100 - (100 / (1 + rs))            # RSI formula
        
        return round(rsi, 2)                    #Return value rounded to two decimal places

    def log_data(self, timestamp: str, price: float, rsi: float) -> None:
        """Log data to CSV file"""
        try:
            # Create a single-row DataFrame with current data
            df = pd.DataFrame([[timestamp, price, rsi]], 
                            columns=['timestamp', 'price', 'rsi'])
            # Append to CSV without headers
            df.to_csv(self.csv_filename, mode='a', header=False, index=False)
            # Log into console
            logging.info(f'Logged data - Time: {timestamp}, Price: {price}, RSI: {rsi}')
        except Exception as e:
            # Log any errors experienced
            logging.error(f'Error logging data: {str(e)}')

    def run(self) -> None:
        # Log start of tracking
        """Main loop to fetch prices, calculate RSI, and log data"""
        logging.info(f'Starting RSI tracking for {self.symbol}')
        
        while True:
            try:
                # Fetch current price
                current_price = self.fetch_price()
                self.prices.append(current_price)
                
                # Calculate RSI if enough data points
                rsi = self.calculate_rsi(self.prices)
                
                # Get current timestamp
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                # Log data if RSI is available
                if rsi is not None:
                    self.log_data(timestamp, current_price, rsi)
                
                # Keep only the recent prices (2 * period length)
                if len(self.prices) > self.period * 2:
                    self.prices = self.prices[-(self.period * 2):]
                
                # Add jitter to API delay to prevent exact timing patterns (random delay variation)
                jitter = random.uniform(-2, 2)
                time.sleep(self.api_delay + jitter)
                
            except Exception as e:
                # Log any errors
                logging.error(f'Error in main loop: {str(e)}')
                # Exponential backoff on error (wait 5 minutes)
                time.sleep(min(self.api_delay * 2, 300))  
                
                #Script

if __name__ == '__main__':
    # Create and run tracker
    tracker = CryptoRSITracker(
        symbol='BTC/USDT',  # Trading pair
        period=14,          # RSI period
        api_delay=60        # Delay between API calls in seconds
    )
    tracker.run()