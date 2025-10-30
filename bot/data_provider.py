import ccxt
import pandas as pd
import yfinance as yf
from abc import ABC, abstractmethod
from solana.rpc.api import Client
from solana.rpc.websocket_api import connect
import json
import asyncio
import base58
import os
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime
import time

class DataProvider(ABC):
    @abstractmethod
    def get_ohlcv(self, symbol, timeframe, limit):
        pass
        
    @abstractmethod
    def get_ticker(self, symbol):
        pass
        
    @abstractmethod
    def get_popular_assets(self, limit):
        pass

class AlphaVantageProvider(DataProvider):
    def __init__(self, api_key=None):
        self.api_key = api_key or os.getenv('ALPHA_VANTAGE_KEY')
        if not self.api_key:
            print("Warning: Alpha Vantage API key not found. Skipping Alpha fallback")
            self.api_key = None
        self.base_url = "https://www.alphavantage.co/query"

    def _convert_symbol(self, symbol):
        """Convert symbol to Alpha Vantage format"""
        if '=X' in symbol:  # Forex format like EURUSD=X
            base = symbol.replace('=X', '')
            return f"{base[:3]}/{base[3:]}"
        elif '.JK' in symbol:  # Indonesian stock
            return symbol.replace('.JK', '.JK')
        elif '/' in symbol:  # Crypto format like BTC/USDT
            base, quote = symbol.split('/')
            return base
        else:
            return symbol

    def get_ohlcv(self, symbol, timeframe='1d', limit=200):
        if not self.api_key:
            return None
            
        try:
            symbol_av = self._convert_symbol(symbol)
            
            # Determine function based on symbol type
            if '=X' in symbol or ('/' in symbol and len(symbol.split('/')[0]) == 3 and len(symbol.split('/')[1]) == 3):
                # Forex
                function = "FX_DAILY"
                params = {
                    "function": function,
                    "from_symbol": symbol_av.split('/')[0],
                    "to_symbol": symbol_av.split('/')[1],
                    "apikey": self.api_key,
                    "outputsize": "full" if limit > 100 else "compact"
                }
            elif '.JK' in symbol:
                # Indonesian stock
                function = "TIME_SERIES_DAILY"
                params = {
                    "function": function,
                    "symbol": symbol_av,
                    "apikey": self.api_key,
                    "outputsize": "full" if limit > 100 else "compact"
                }
            else:
                # Crypto
                function = "DIGITAL_CURRENCY_DAILY"
                params = {
                    "function": function,
                    "symbol": symbol_av,
                    "market": "USD",
                    "apikey": self.api_key
                }

            response = requests.get(self.base_url, params=params)
            data = response.json()
            
            # Handle different response formats
            if "Time Series (Digital Currency Daily)" in data:
                ohlcv_data = data["Time Series (Digital Currency Daily)"]
            elif "Time Series (Daily)" in data:
                ohlcv_data = data["Time Series (Daily)"]
            elif "Time Series FX (Daily)" in data:
                ohlcv_data = data["Time Series FX (Daily)"]
            else:
                print(f"Unexpected Alpha Vantage response format: {list(data.keys())}")
                return None

            df = pd.DataFrame.from_dict(ohlcv_data, orient='index')
            df = df.astype(float)
            df['timestamp'] = pd.to_datetime(df.index)
            
            # Map columns based on data type
            if function == "DIGITAL_CURRENCY_DAILY":
                df = df[['timestamp', '1a. open (USD)', '2a. high (USD)', '3a. low (USD)', '4a. close (USD)', '5. volume']]
                df.columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
            elif function == "FX_DAILY":
                df = df[['timestamp', '1. open', '2. high', '3. low', '4. close']]
                df.columns = ['timestamp', 'open', 'high', 'low', 'close']
                df['volume'] = 0  # Forex doesn't have volume
            else:  # Stocks
                df = df[['timestamp', '1. open', '2. high', '3. low', '4. close', '5. volume']]
                df.columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume']

            return df.sort_values('timestamp').tail(limit)
            
        except Exception as e:
            print(f"Error getting OHLCV from Alpha Vantage for {symbol}: {e}")
            return None

    def get_ticker(self, symbol):
        if not self.api_key:
            return None
            
        try:
            symbol_av = self._convert_symbol(symbol)
            
            if '=X' in symbol or ('/' in symbol and len(symbol.split('/')[0]) == 3):
                # Forex
                function = "CURRENCY_EXCHANGE_RATE"
                from_curr = symbol_av.split('/')[0] if '/' in symbol_av else symbol_av[:3]
                to_curr = symbol_av.split('/')[1] if '/' in symbol_av else symbol_av[3:]
                params = {
                    "function": function,
                    "from_currency": from_curr,
                    "to_currency": to_curr,
                    "apikey": self.api_key
                }
            elif '.JK' in symbol:
                # Stock
                function = "GLOBAL_QUOTE"
                params = {
                    "function": function,
                    "symbol": symbol_av,
                    "apikey": self.api_key
                }
            else:
                # Crypto
                function = "CURRENCY_EXCHANGE_RATE"
                params = {
                    "function": function,
                    "from_currency": symbol_av,
                    "to_currency": "USD",
                    "apikey": self.api_key
                }

            response = requests.get(self.base_url, params=params)
            data = response.json()
            
            if "Realtime Currency Exchange Rate" in data:
                rate = data["Realtime Currency Exchange Rate"]
                return {
                    'last': float(rate['5. Exchange Rate']),
                    'volume': float(rate.get('6. Last Refreshed', 0))
                }
            elif "Global Quote" in data:
                quote = data["Global Quote"]
                return {
                    'last': float(quote['05. price']),
                    'volume': float(quote.get('06. volume', 0))
                }
            return None
            
        except Exception as e:
            print(f"Error getting ticker from Alpha Vantage for {symbol}: {e}")
            return None

    def get_popular_assets(self, limit=100):
        return []

class DexScreenerProvider:
    def __init__(self):
        self.base_url = "https://api.dexscreener.com/latest/dex"
        
    def get_ticker(self, chain, token_address):
        try:
            url = f"{self.base_url}/tokens/{chain}/{token_address}"
            response = requests.get(url)
            data = response.json()
            if 'pairs' in data and data['pairs']:
                pair = data['pairs'][0]
                return {
                    'last': float(pair.get('priceUsd', 0)),
                    'volume': float(pair.get('volume', {}).get('h24', 0)),
                    'liquidity': float(pair.get('liquidity', {}).get('usd', 0)),
                    'fdv': float(pair.get('fdv', 0))
                }
            return None
        except Exception as e:
            print(f"Error getting ticker from DexScreener for {token_address}: {e}")
            return None
            
    def search_pairs(self, query):
        try:
            url = f"{self.base_url}/search?q={query}"
            response = requests.get(url)
            data = response.json()
            return data.get('pairs', [])
        except Exception as e:
            print(f"Error searching pairs in DexScreener: {e}")
            return []

class CCXTDataProvider(DataProvider):
    def __init__(self, exchange_id='binance', api_key='', secret=''):
        try:
            exchange_class = getattr(ccxt, exchange_id)
            self.exchange = exchange_class({
                'apiKey': api_key,
                'secret': secret,
                'enableRateLimit': True,
            })
            self.exchange.load_markets()
        except Exception as e:
            print(f"Error initializing {exchange_id}: {e}")
            self.exchange = None
            
        self.fallback_yf = YFinanceDataProvider()
        self.fallback_av = AlphaVantageProvider()

    def _convert_symbol_for_fallback(self, symbol, target_provider):
        """Convert symbol format for different fallback providers"""
        if target_provider == 'yfinance':
            if '/' in symbol:  # Crypto pair like BTC/USDT
                base, quote = symbol.split('/')
                if quote == 'USDT':
                    return f"{base}-USD"
                return f"{base}-{quote}"
            return symbol
        elif target_provider == 'alphavantage':
            return symbol.replace('/', '')
        return symbol

    def get_ohlcv(self, symbol, timeframe, limit=200):
        # Try CCXT first
        if self.exchange:
            try:
                ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
                df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                return df
            except Exception as e:
                print(f"CCXT error for {symbol}: {e}")

        # Fallback to yfinance for forex and stocks
        if '=X' in symbol or '.JK' in symbol:
            return self.fallback_yf.get_ohlcv(symbol, timeframe, limit)
        
        # Fallback chain for crypto
        fallback_providers = [
            (self.fallback_yf, 'yfinance'),
            (self.fallback_av, 'alphavantage')
        ]
        
        for provider, provider_type in fallback_providers:
            try:
                conv_symbol = self._convert_symbol_for_fallback(symbol, provider_type)
                print(f"Trying {provider.__class__.__name__} with symbol: {conv_symbol}")
                df = provider.get_ohlcv(conv_symbol, timeframe, limit)
                if df is not None and not df.empty:
                    return df
            except Exception as e:
                print(f"Fallback {provider_type} failed: {e}")
                continue
                
        return None

    def get_ticker(self, symbol):
        if self.exchange:
            try:
                return self.exchange.fetch_ticker(symbol)
            except Exception as e:
                print(f"CCXT ticker error for {symbol}: {e}")

        # Fallback logic similar to OHLCV
        if '=X' in symbol or '.JK' in symbol:
            return self.fallback_yf.get_ticker(symbol)
            
        fallback_providers = [
            (self.fallback_yf, 'yfinance'),
            (self.fallback_av, 'alphavantage')
        ]
        
        for provider, provider_type in fallback_providers:
            try:
                conv_symbol = self._convert_symbol_for_fallback(symbol, provider_type)
                ticker = provider.get_ticker(conv_symbol)
                if ticker is not None:
                    return ticker
            except Exception as e:
                print(f"Fallback ticker {provider_type} failed: {e}")
                continue
                
        return None

    def get_popular_assets(self, limit=100):
        try:
            if not self.exchange:
                return self._get_hardcoded_crypto_pairs(limit)
                
            markets = self.exchange.load_markets()
            usdt_markets = [symbol for symbol in markets if symbol.endswith('/USDT')]
            
            # Filter out stablecoins
            excluded_coins = ['BUSD', 'USDC', 'DAI', 'TUSD', 'USDP', 'UST']
            filtered_markets = [
                symbol for symbol in usdt_markets 
                if not any(excluded in symbol for excluded in excluded_coins)
            ]
            
            # Sort by volume if available
            try:
                tickers = self.exchange.fetch_tickers(filtered_markets[:50])  # Limit to avoid rate limits
                filtered_markets.sort(key=lambda x: tickers[x]['quoteVolume'] if x in tickers else 0, reverse=True)
            except:
                # If volume sorting fails, use hardcoded popular pairs
                pass
                
            return filtered_markets[:limit]
            
        except Exception as e:
            print(f"Error getting popular assets from CCXT: {e}")
            return self._get_hardcoded_crypto_pairs(limit)

    def _get_hardcoded_crypto_pairs(self, limit):
        """Fallback popular crypto pairs"""
        popular_pairs = [
            'BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'SOL/USDT', 'XRP/USDT',
            'ADA/USDT', 'AVAX/USDT', 'DOT/USDT', 'DOGE/USDT', 'MATIC/USDT',
            'LTC/USDT', 'LINK/USDT', 'ATOM/USDT', 'UNI/USDT', 'XLM/USDT'
        ]
        return popular_pairs[:limit]

class YFinanceDataProvider(DataProvider):
    def __init__(self, market_type='auto'):
        self.market_type = market_type
        
    def _detect_symbol_type(self, symbol):
        """Auto-detect symbol type for proper handling"""
        if '=X' in symbol:
            return 'forex'
        elif '.JK' in symbol:
            return 'saham_id'
        elif '/' in symbol:
            return 'crypto'
        else:
            return 'stock'

    def get_ohlcv(self, symbol, timeframe='1d', limit=200):
        try:
            # Map timeframe to yfinance format
            interval_map = {
                '1m': '1m', '2m': '2m', '5m': '5m', '15m': '15m', '30m': '30m',
                '1h': '1h', '1d': '1d', '5d': '5d', '1wk': '1wk', '1mo': '1mo'
            }
            interval = interval_map.get(timeframe, '1d')
            
            # Determine period based on timeframe and limit
            if interval in ['1m', '2m', '5m', '15m', '30m']:
                period = '7d' if limit <= 1000 else '60d'
            elif interval == '1h':
                period = '60d'
            else:
                period = '1y' if limit <= 252 else '2y'

            ticker = yf.Ticker(symbol)
            df = ticker.history(period=period, interval=interval)
            
            if df.empty:
                print(f"No data returned from yfinance for {symbol}")
                return None
                
            # Reset index and rename columns
            df.reset_index(inplace=True)
            if 'Date' in df.columns:
                df.rename(columns={'Date': 'timestamp'}, inplace=True)
            elif 'Datetime' in df.columns:
                df.rename(columns={'Datetime': 'timestamp'}, inplace=True)
                
            # Ensure all required columns exist
            required_cols = ['open', 'high', 'low', 'close', 'volume']
            for col in required_cols:
                if col not in df.columns:
                    df[col] = 0
                    
            df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
            
            # Handle timezone-naive timestamps
            if hasattr(df['timestamp'].iloc[0], 'tz') and df['timestamp'].iloc[0].tz is not None:
                df['timestamp'] = df['timestamp'].dt.tz_localize(None)
                
            return df.tail(limit)
            
        except Exception as e:
            print(f"Error getting OHLCV from yfinance for {symbol}: {e}")
            return None

    def get_ticker(self, symbol):
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            
            # Try to get current price
            hist = ticker.history(period='1d', interval='1m')
            if not hist.empty:
                last_price = hist['Close'].iloc[-1]
                volume = hist['Volume'].iloc[-1] if 'Volume' in hist.columns else info.get('volume', 0)
            else:
                last_price = info.get('currentPrice', info.get('regularMarketPrice', 0))
                volume = info.get('volume', 0)
                
            return {
                'last': last_price,
                'volume': volume,
                'high': info.get('dayHigh', 0),
                'low': info.get('dayLow', 0)
            }
            
        except Exception as e:
            print(f"Error getting ticker from yfinance for {symbol}: {e}")
            return None

    def get_popular_assets(self, limit=50):
        symbol_type = self._detect_symbol_type(self.market_type) if self.market_type != 'auto' else 'stock'
        
        if symbol_type == 'saham_id':
            return self._get_indonesian_stocks(limit)
        elif symbol_type == 'forex':
            return self._get_forex_pairs(limit)
        else:
            return self._get_international_stocks(limit)

    def _get_indonesian_stocks(self, limit):
        """Get popular Indonesian stocks"""
        try:
            # Try to fetch from investing.com
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            url = "https://www.investing.com/indices/idx-composite-components"
            response = requests.get(url, headers=headers, timeout=10)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            tickers = []
            table = soup.find('table', {'class': 'genTbl openTbl'})
            if table:
                rows = table.find_all('tr')[1:]  # Skip header
                for row in rows:
                    cells = row.find_all('td')
                    if len(cells) > 1:
                        ticker = cells[1].text.strip()
                        if ticker and len(ticker) <= 4:
                            tickers.append(f"{ticker}.JK")
                            
            if tickers:
                return tickers[:limit]
                
        except Exception as e:
            print(f"Error fetching Indonesian stocks: {e}")

        # Fallback to popular LQ45 stocks
        lq45_stocks = [
            'BBCA.JK', 'TLKM.JK', 'ASII.JK', 'BMRI.JK', 'BBNI.JK',
            'BBRI.JK', 'UNVR.JK', 'INDF.JK', 'ICBP.JK', 'ADRO.JK',
            'ANTM.JK', 'AKRA.JK', 'ASSA.JK', 'BUKA.JK', 'CPIN.JK',
            'EMTK.JK', 'ERAA.JK', 'EXCL.JK', 'GGRM.JK', 'HMSP.JK',
            'ICBP.JK', 'INCO.JK', 'INDF.JK', 'JPFA.JK', 'KLBF.JK',
            'MDKA.JK', 'MIKA.JK', 'MNCN.JK', 'PGAS.JK', 'PTBA.JK',
            'PTPP.JK', 'SMGR.JK', 'TBIG.JK', 'TINS.JK', 'TKIM.JK',
            'TLKM.JK', 'TOWR.JK', 'TPIA.JK', 'UNTR.JK', 'UNVR.JK',
            'WIKA.JK', 'WSKT.JK', 'WTON.JK'
        ]
        return lq45_stocks[:limit]

    def _get_forex_pairs(self, limit):
        """Get popular forex pairs"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            url = "https://www.investing.com/currencies/"
            response = requests.get(url, headers=headers, timeout=10)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            pairs = []
            # Look for major currency pairs
            major_pairs_section = soup.find('div', {'class': 'major-currency-pairs'})
            if major_pairs_section:
                links = major_pairs_section.find_all('a', {'class': 'js-quote-ticker-link'})
                for link in links:
                    pair_text = link.text.strip().replace('/', '')
                    if len(pair_text) == 6:  # Standard forex pair like EURUSD
                        pairs.append(f"{pair_text}=X")
            
            if pairs:
                return pairs[:limit]
                
        except Exception as e:
            print(f"Error fetching forex pairs: {e}")

        # Fallback major forex pairs
        major_forex = [
            'EURUSD=X', 'GBPUSD=X', 'USDJPY=X', 'USDCHF=X', 'AUDUSD=X',
            'USDCAD=X', 'NZDUSD=X', 'EURGBP=X', 'EURJPY=X', 'GBPJPY=X',
            'EURCHF=X', 'AUDJPY=X', 'CADJPY=X', 'CHFJPY=X', 'EURCAD=X',
            'EURAUD=X', 'GBPCHF=X', 'AUDCAD=X', 'AUDCHF=X', 'AUDNZD=X'
        ]
        return major_forex[:limit]

    def _get_international_stocks(self, limit):
        """Get popular international stocks"""
        popular_stocks = [
            'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA', 
            'META', 'NVDA', 'JPM', 'JNJ', 'V',
            'PG', 'UNH', 'HD', 'DIS', 'PYPL',
            'NFLX', 'ADBE', 'CRM', 'INTC', 'CSCO'
        ]
        return popular_stocks[:limit]

class SolanaPumpFunProvider:
    def __init__(self, rpc_url=None):
        self.rpc_url = rpc_url or "https://api.mainnet-beta.solana.com"
        self.client = Client(self.rpc_url)
        self.dex_provider = DexScreenerProvider()

    async def monitor_new_tokens(self, limit=10):
        """Monitor new tokens on Pump.fun"""
        print("Pump.fun monitoring requires WebSocket connection setup...")
        return []

# Example usage and testing
def test_providers():
    """Test function to verify all providers work correctly"""
    
    print("Testing Data Providers...")
    
    # Initialize providers
    yf_provider = YFinanceDataProvider()
    ccxt_provider = CCXTDataProvider('binance')
    av_provider = AlphaVantageProvider()
    
    # Test symbols for different markets
    test_symbols = {
        'forex': 'EURUSD=X',
        'saham_id': 'BBCA.JK', 
        'crypto': 'BTC/USDT',
        'international': 'AAPL'
    }
    
    for market_type, symbol in test_symbols.items():
        print(f"\n=== Testing {market_type.upper()} : {symbol} ===")
        
        # Test yfinance
        print(f"YFinance OHLCV for {symbol}:")
        yf_data = yf_provider.get_ohlcv(symbol, '1d', 5)
        if yf_data is not None and not yf_data.empty:
            print(f"✓ Success: {len(yf_data)} rows")
            print(yf_data[['timestamp', 'close']].tail())
        else:
            print("✗ Failed")
            
        # Test ticker
        print(f"YFinance Ticker for {symbol}:")
        yf_ticker = yf_provider.get_ticker(symbol)
        if yf_ticker:
            print(f"✓ Success: {yf_ticker}")
        else:
            print("✗ Failed")
    
    # Test popular assets
    print("\n=== Testing Popular Assets ===")
    
    # Indonesian stocks
    id_stocks = yf_provider._get_indonesian_stocks(10)
    print(f"Indonesian Stocks: {id_stocks}")
    
    # Forex pairs  
    forex_pairs = yf_provider._get_forex_pairs(10)
    print(f"Forex Pairs: {forex_pairs}")
    
    # Crypto pairs
    crypto_pairs = ccxt_provider.get_popular_assets(10)
    print(f"Crypto Pairs: {crypto_pairs}")

if __name__ == "__main__":
    test_providers()
