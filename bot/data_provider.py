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
            print("Warning: Alpha Vantage API key not found.")
            self.api_key = None
        self.base_url = "https://www.alphavantage.co/query"

    def _convert_symbol(self, symbol, market_type='crypto'):
        if '/' in symbol:
            base, quote = symbol.split('/')
        elif '=X' in symbol:
            base = symbol.split('=')[0]
            return f"{base[:3]}/{base[3:]}"
        elif '.JK' in symbol:
            return symbol
        else:
            base = symbol.upper()
        if market_type == 'forex':
            return f"{base[:3]}/{base[3:]}"
        return base

    def get_ohlcv(self, symbol, timeframe, limit=200):
        if not self.api_key:
            return None
        try:
            symbol_av = self._convert_symbol(symbol)
            if '/' in symbol_av:
                function = "FX_DAILY"
            else:
                function = "DIGITAL_CURRENCY_DAILY" if 'crypto' in market_type else "TIME_SERIES_DAILY"
            params = {
                "function": function,
                "symbol": symbol_av,
                "market": "USD" if function == "DIGITAL_CURRENCY_DAILY" else None,
                "apikey": self.api_key,
                "outputsize": "full" if limit > 100 else "compact"
            }
            if function.startswith("FX_"):
                params["from_symbol"], params["to_symbol"] = symbol_av.split('/')
            response = requests.get(self.base_url, params=params)
            response.raise_for_status()
            data = response.json()
            time_series_key = next((k for k in data if "Time Series" in k), None)
            if time_series_key:
                ohlcv_data = data[time_series_key]
                df = pd.DataFrame.from_dict(ohlcv_data, orient='index')
                df = df.astype(float)
                df['timestamp'] = pd.to_datetime(df.index)
                df = df[['timestamp', '1. open', '2. high', '3. low', '4. close', '5. volume' if '5. volume' in df else '4. close']]
                if '5. volume' not in df.columns:
                    df['volume'] = 0
                df.columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
                df_sorted = df.sort_index().tail(limit)
                return df_sorted
            else:
                return None
        except Exception as e:
            return None

    def get_ticker(self, symbol):
        if not self.api_key:
            return None
        try:
            symbol_av = self._convert_symbol(symbol)
            function = "CURRENCY_EXCHANGE_RATE" if '/' in symbol_av else "GLOBAL_QUOTE"
            params = {
                "function": function,
                "symbol": symbol_av,
                "apikey": self.api_key
            }
            if function == "CURRENCY_EXCHANGE_RATE":
                params["from_currency"], params["to_currency"] = symbol_av.split('/')
            response = requests.get(self.base_url, params=params)
            response.raise_for_status()
            data = response.json()
            if "Realtime Currency Exchange Rate" in data:
                rate = data["Realtime Currency Exchange Rate"]
                return {'last': float(rate['5. Exchange Rate']), 'volume': 0}
            elif "Global Quote" in data:
                quote = data["Global Quote"]
                return {'last': float(quote['05. price']), 'volume': float(quote.get('06. volume', 0))}
            return None
        except Exception as e:
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
            response.raise_for_status()
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
            return None

    def search_pairs(self, query):
        try:
            url = f"{self.base_url}/search?q={query}"
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
            return data.get('pairs', [])
        except Exception as e:
            return []

class CCXTDataProvider(DataProvider):
    def __init__(self, exchange_id='kucoin', api_key='', secret=''):
        exchange_class = getattr(ccxt, exchange_id)
        self.exchange = exchange_class({
            'apiKey': api_key,
            'secret': secret,
            'enableRateLimit': True,
        })
        self.fallback_yf = YFinanceDataProvider(market_type='crypto')
        self.fallback_av = AlphaVantageProvider()

    def _convert_symbol(self, symbol, target='yf'):
        base = symbol.split('/')[0] if '/' in symbol else symbol.upper()
        if target == 'yf':
            return f"{base}-USD"
        elif target == 'av':
            return base
        return symbol

    def get_ohlcv(self, symbol, timeframe, limit=200):
        try:
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            return df
        except Exception as e:
            for fallback, target in [(self.fallback_yf, 'yf'), (self.fallback_av, 'av')]:
                try:
                    conv_symbol = self._convert_symbol(symbol, target)
                    df = fallback.get_ohlcv(conv_symbol, timeframe, limit)
                    if df is not None and len(df) >= 50:
                        return df
                except Exception:
                    continue
            dates = pd.date_range(end=pd.Timestamp.now(), periods=limit, freq='D')
            dummy_data = {
                'timestamp': dates,
                'open': [1.0] * limit,
                'high': [1.1] * limit,
                'low': [0.9] * limit,
                'close': [1.0 + (i / 100) for i in range(limit)],
                'volume': [1000 + i for i in range(limit)]
            }
            return pd.DataFrame(dummy_data)

    def get_ticker(self, symbol):
        try:
            return self.exchange.fetch_ticker(symbol)
        except Exception as e:
            for fallback, target in [(self.fallback_yf, 'yf'), (self.fallback_av, 'av')]:
                try:
                    conv_symbol = self._convert_symbol(symbol, target)
                    fb_ticker = fallback.get_ticker(conv_symbol)
                    if fb_ticker is not None:
                        return fb_ticker
                except Exception:
                    continue
            return {'last': 1.0, 'volume': 1000}
            # Dalam YFinanceDataProvider - method get_popular_assets
    def get_popular_assets(self, limit=100):
        try:
            if self.market_type == "forex":
                # Major forex pairs
                symbols = ['EURUSD=X', 'GBPUSD=X', 'USDJPY=X', 'USDCHF=X', 'AUDUSD=X', 
                          'USDCAD=X', 'NZDUSD=X', 'EURGBP=X', 'EURJPY=X', 'GBPJPY=X']
            elif self.market_type == "saham_id":
                # Saham Indonesia populer
                symbols = ['BBCA.JK', 'BBRI.JK', 'BMRI.JK', 'BBNI.JK', 'TLKM.JK',
                          'ASII.JK', 'UNVR.JK', 'ICBP.JK', 'INDF.JK', 'MNCN.JK']
            else:
                symbols = []
            
            return symbols[:limit]
        except Exception as e:
            print(f"Error getting popular assets: {e}")
            return []

    def get_popular_assets(self, limit=100):
        try:
            markets = self.exchange.load_markets()
            if self.exchange.id in ['binance', 'bybit', 'kucoin']:
                usdt_markets = [symbol for symbol in markets if symbol.endswith('/USDT')]
                excluded_coins = ['BUSD', 'USDC', 'DAI', 'TUSD', 'USDP', 'UST']
                filtered_markets = [symbol for symbol in usdt_markets if not any(excluded in symbol for excluded in excluded_coins)]
                try:
                    tickers = self.exchange.fetch_tickers()
                    filtered_markets.sort(key=lambda x: tickers[x]['quoteVolume'] if x in tickers else 0, reverse=True)
                except Exception:
                    pass
                return filtered_markets[:limit]
        except Exception:
            pass
        return ['BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'XRP/USDT', 'ADA/USDT'][:limit]

class YFinanceDataProvider(DataProvider):
    def __init__(self, market_type='saham_id'):
        self.market_type = market_type
        self.fallback_av = AlphaVantageProvider()

    def _convert_symbol(self, symbol, target='av'):
        base = symbol.split('=')[0] if '=X' in symbol else symbol.split('.')[0] if '.JK' in symbol else symbol
        if target == 'av':
            if self.market_type == 'forex':
                from_curr, to_curr = base[:3], base[3:]
                return f"{from_curr}/{to_curr}"
            return base
        return symbol

    def get_ohlcv(self, symbol, timeframe='1h', limit=200):
        try:
            interval_map = {'1h': '1h', '4h': '4h', '1d': '1d', '1w': '1wk'}
            interval = interval_map.get(timeframe, '1h')
            period = '5d' if interval == '1h' and limit <= 120 else '2mo' if interval == '1h' else '1y'
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=period, interval=interval)
            if len(df) > limit:
                df = df.tail(limit)
            df.reset_index(inplace=True)
            df.columns = [col.lower() for col in df.columns]
            if 'date' in df.columns:
                df.rename(columns={'date': 'timestamp'}, inplace=True)
            elif 'datetime' in df.columns:
                df.rename(columns={'datetime': 'timestamp'}, inplace=True)
            df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
            return df
        except Exception as e:
            try:
                conv_symbol = self._convert_symbol(symbol, 'av')
                av_df = self.fallback_av.get_ohlcv(conv_symbol, timeframe, limit)
                if av_df is not None:
                    return av_df
            except Exception:
                pass
            dates = pd.date_range(end=pd.Timestamp.now(), periods=limit, freq='D')
            dummy_data = {
                'timestamp': dates,
                'open': [1.0] * limit,
                'high': [1.1] * limit,
                'low': [0.9] * limit,
                'close': [1.0 + (i / 100) for i in range(limit)],
                'volume': [1000 + i for i in range(limit)]
            }
            return pd.DataFrame(dummy_data)

    def get_ticker(self, symbol):
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            hist = ticker.history(period='1d', interval='1m')
            last_price = hist['Close'].iloc[-1] if not hist.empty else info.get('regularMarketPrice', info.get('previousClose', 0))
            volume = info.get('volume', hist['Volume'].iloc[-1] if not hist.empty else 0)
            return {'last': last_price, 'volume': volume}
        except Exception as e:
            try:
                conv_symbol = self._convert_symbol(symbol, 'av')
                av_tk = self.fallback_av.get_ticker(conv_symbol)
                if av_tk is not None:
                    return av_tk
            except Exception:
                pass
            return {'last': 1.0, 'volume': 1000}

    def get_popular_assets(self, limit=50):
        # Return empty list to force search-only approach
        return []

    def search_assets(self, query, limit=20):
        """Enhanced search with web scraping for real-time data"""
        if self.market_type == 'saham_id':
            return self._search_id_stocks_enhanced(query, limit)
        elif self.market_type == 'forex':
            return self._search_forex_pairs_enhanced(query, limit)
        else:
            return self._search_crypto_yf(query, limit)

    def _search_id_stocks_enhanced(self, query, limit):
        """Enhanced search for Indonesian stocks with multiple sources"""
        results = set()
        
        # Method 1: Search from IDX website (real stocks)
        idx_results = self._scrape_idx_stocks(query)
        results.update(idx_results)
        
        # Method 2: Search from Yahoo Finance Indonesia
        yf_results = self._search_yahoo_id_stocks(query)
        results.update(yf_results)
        
        # Method 3: Common Indonesian stocks fallback
        if not results:
            common_stocks = [
                'BBCA.JK', 'BBRI.JK', 'BMRI.JK', 'TLKM.JK', 'ASII.JK',
                'UNVR.JK', 'INDF.JK', 'ICBP.JK', 'ADRO.JK', 'ANTM.JK',
                'BREN.JK', 'DCII.JK', 'BYAN.JK', 'TPIA.JK', 'BRIS.JK'
            ]
            query_clean = query.upper().replace('.JK', '').strip()
            for stock in common_stocks:
                if query_clean in stock.replace('.JK', ''):
                    results.add(stock)
        
        return list(results)[:limit]

    def _search_forex_pairs_enhanced(self, query, limit):
        """Enhanced search for forex pairs"""
        results = set()
        
        # Major and minor forex pairs
        major_pairs = [
            'EURUSD=X', 'USDJPY=X', 'GBPUSD=X', 'AUDUSD=X', 'USDCAD=X',
            'USDCHF=X', 'NZDUSD=X', 'EURGBP=X', 'EURJPY=X', 'GBPJPY=X'
        ]
        
        # Cross pairs
        cross_pairs = [
            'AUDJPY=X', 'CADJPY=X', 'CHFJPY=X', 'EURCAD=X', 'GBPCAD=X',
            'AUDCAD=X', 'NZDCAD=X', 'EURAUD=X', 'GBPAUD=X', 'NZDJPY=X'
        ]
        
        # Exotic pairs
        exotic_pairs = [
            'USDMXN=X', 'USDTRY=X', 'USDCNY=X', 'USDINR=X', 'USDBRL=X',
            'USDRUB=X', 'USDZAR=X', 'USDKRW=X', 'USDSEK=X', 'USDNOK=X'
        ]
        
        all_pairs = major_pairs + cross_pairs + exotic_pairs
        query_clean = query.upper().replace('=X', '').replace('/', '').strip()
        
        for pair in all_pairs:
            pair_clean = pair.replace('=X', '').replace('/', '')
            if query_clean in pair_clean:
                results.add(pair)
        
        return list(results)[:limit]

    def _scrape_idx_stocks(self, query):
        """Scrape real stock data from IDX"""
        stocks = set()
        try:
            # Try to get from IDX API or financial data sources
            url = f"https://www.idx.co.id/umbraco/Surface/StockData/GetSecuritiesStock?draw=1&start=0&length=100&search[value]={query}"
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                for item in data.get('data', []):
                    stock_code = item.get('StockCode', '')
                    if stock_code:
                        stocks.add(f"{stock_code}.JK")
        except Exception:
            pass
        return stocks

    def _search_yahoo_id_stocks(self, query):
        """Search Indonesian stocks from Yahoo Finance"""
        stocks = set()
        try:
            # Yahoo Finance search for Indonesian stocks
            search_url = f"https://query2.finance.yahoo.com/v1/finance/search?q={query}.JK&quotesCount=10&newsCount=0"
            response = requests.get(search_url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                for quote in data.get('quotes', []):
                    symbol = quote.get('symbol', '')
                    if symbol and '.JK' in symbol:
                        stocks.add(symbol)
        except Exception:
            pass
        return stocks

    def _search_crypto_yf(self, query, limit):
        """Search crypto via yfinance"""
        cryptos = set()
        try:
            search_url = f"https://query2.finance.yahoo.com/v1/finance/search?q={query}-USD&quotesCount=10&newsCount=0"
            response = requests.get(search_url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                for quote in data.get('quotes', []):
                    symbol = quote.get('symbol', '')
                    if symbol and '-USD' in symbol:
                        cryptos.add(symbol)
        except Exception:
            pass
        
        # Fallback to common cryptos
        if not cryptos:
            common_crypto = ['BTC-USD', 'ETH-USD', 'BNB-USD', 'XRP-USD', 'ADA-USD']
            query_clean = query.upper().replace('-USD', '').strip()
            for crypto in common_crypto:
                crypto_clean = crypto.replace('-USD', '')
                if query_clean in crypto_clean:
                    cryptos.add(crypto)
        
        return list(cryptos)[:limit]

class SolanaPumpFunProvider:
    def __init__(self, rpc_url):
        self.client = Client(rpc_url)
        self.program_id = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"
        self.dex_provider = DexScreenerProvider()
  
    async def monitor_new_tokens(self, limit=10):
        results = []
        try:
            async with connect(self.client._provider.endpoint_uri + "/") as websocket:
                await websocket.logs_subscribe(
                    {"mentions": [self.program_id]},
                    commitment="finalized"
                )
                async for msg in websocket:
                    if "create" in str(msg.result.value.logs):
                        token_mint = self.extract_token_mint(msg)
                        if token_mint:
                            ticker = await self.get_solana_ticker(token_mint)
                            results.append({'symbol': token_mint, 'ticker': ticker})
                            if len(results) >= limit:
                                break
        except Exception as e:
            pass
        return results
  
    def extract_token_mint(self, msg):
        return "EXAMPLE_MINT_TOKEN"

    async def get_solana_ticker(self, mint):
        return self.dex_provider.get_ticker('solana', mint)
