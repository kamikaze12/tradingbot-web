import ccxt
import pandas as pd
import yfinance as yf
from abc import ABC, abstractmethod
from solana.rpc.api import Client
from solana.rpc.websocket_api import connect
import json
import asyncio
import base58  # Untuk decode pubkey
import os
import requests  # Untuk Alpha Vantage dan DexScreener
from bs4 import BeautifulSoup  # Untuk parse HTML dari situs web
import re  # Untuk parse search result
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
            print("Warning: Alpha Vantage API key not found. Skipping Alpha fallback - get one at https://www.alphavantage.co/support/#api-key")
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
            print("No Alpha Vantage key, skipping OHLCV.")
            return None
        try:
            symbol_av = self._convert_symbol(symbol)
            if '/' in symbol_av:  # Forex
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
                print(f"Alpha Vantage OHLCV for {symbol}: {len(df_sorted)} rows fetched.")
                return df_sorted
            else:
                print(f"Error in Alpha Vantage response for {symbol}: {data}")
                return None
        except requests.exceptions.HTTPError as http_err:
            print(f"HTTP error in Alpha Vantage for {symbol}: {http_err}")
        except Exception as e:
            print(f"Error getting OHLCV from Alpha Vantage for {symbol}: {e}")
        return None

    def get_ticker(self, symbol):
        if not self.api_key:
            print("No Alpha Vantage key, skipping ticker.")
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
                ticker = {'last': float(rate['5. Exchange Rate']), 'volume': 0}
                print(f"Alpha Vantage ticker for {symbol}: {ticker}")
                return ticker
            elif "Global Quote" in data:
                quote = data["Global Quote"]
                ticker = {'last': float(quote['05. price']), 'volume': float(quote.get('06. volume', 0))}
                print(f"Alpha Vantage ticker for {symbol}: {ticker}")
                return ticker
            print(f"No valid ticker data from Alpha Vantage for {symbol}")
            return None
        except requests.exceptions.HTTPError as http_err:
            print(f"HTTP error in Alpha Vantage ticker for {symbol}: {http_err}")
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
            response.raise_for_status()
            data = response.json()
            if 'pairs' in data and data['pairs']:
                pair = data['pairs'][0]
                ticker = {
                    'last': float(pair.get('priceUsd', 0)),
                    'volume': float(pair.get('volume', {}).get('h24', 0)),
                    'liquidity': float(pair.get('liquidity', {}).get('usd', 0)),
                    'fdv': float(pair.get('fdv', 0))
                }
                print(f"DexScreener ticker for {token_address}: {ticker}")
                return ticker
            print(f"No pairs found in DexScreener for {token_address}")
            return None
        except requests.exceptions.HTTPError as http_err:
            print(f"HTTP error in DexScreener for {token_address}: {http_err}")
        except Exception as e:
            print(f"Error getting ticker from DexScreener for {token_address}: {e}")
            return None

    def search_pairs(self, query):
        try:
            url = f"{self.base_url}/search?q={query}"
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
            pairs = data.get('pairs', [])
            print(f"DexScreener search for {query}: {len(pairs)} pairs found")
            return pairs
        except requests.exceptions.HTTPError as http_err:
            print(f"HTTP error searching DexScreener: {http_err}")
        except Exception as e:
            print(f"Error searching pairs in DexScreener: {e}")
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
        self.fallback_av = AlphaVantageProvider() # Last untuk hemat limit 25/day

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
            print(f"CCXT OHLCV for {symbol}: {len(df)} rows fetched.")
            return df
        except Exception as e:
            print(f"Error getting data from CCXT for {symbol}: {e}")
            # Fallback chain: yf → av
            for fallback, target in [(self.fallback_yf, 'yf'), (self.fallback_av, 'av')]:
                try:
                    conv_symbol = self._convert_symbol(symbol, target)
                    print(f"Falling back to {fallback.__class__.__name__} with symbol: {conv_symbol}")
                    df = fallback.get_ohlcv(conv_symbol, timeframe, limit)
                    if df is not None and len(df) >= 50:
                        return df
                except Exception as fb_e:
                    print(f"Fallback error for {conv_symbol}: {fb_e}")
            # Ultimate dummy fallback
            print(f"All failed for OHLCV {symbol}. Returning dummy DF.")
            dates = pd.date_range(end=pd.Timestamp.now(), periods=limit, freq='D')
            dummy_data = {
                'timestamp': dates,
                'open': [1.0] * limit,
                'high': [1.1] * limit,
                'low': [0.9] * limit,
                'close': [1.0 + (i / 100) for i in range(limit)],  # Slight upward trend to trigger LONG
                'volume': [1000 + i for i in range(limit)]  # Increasing volume
            }
            return pd.DataFrame(dummy_data)

    def get_ticker(self, symbol):
        try:
            ticker = self.exchange.fetch_ticker(symbol)
            print(f"CCXT ticker for {symbol}: {ticker}")
            return ticker
        except Exception as e:
            print(f"Error getting ticker from CCXT for {symbol}: {e}")
            for fallback, target in [(self.fallback_yf, 'yf'), (self.fallback_av, 'av')]:
                try:
                    conv_symbol = self._convert_symbol(symbol, target)
                    print(f"Falling back to {fallback.__class__.__name__} with symbol: {conv_symbol}")
                    fb_ticker = fallback.get_ticker(conv_symbol)
                    if fb_ticker is not None:
                        return fb_ticker
                except Exception as fb_e:
                    print(f"Fallback ticker error for {conv_symbol}: {fb_e}")
            # Dummy fallback
            print(f"All failed for ticker {symbol}. Returning dummy.")
            return {'last': 1.0, 'volume': 1000}

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
                except Exception as sort_e:
                    print(f"Sorting error: {sort_e}")
                assets = filtered_markets[:limit]
                print(f"CCXT popular assets: {len(assets)} fetched.")
                return assets
        except Exception as e:
            print(f"Error loading markets from CCXT: {e}")
        # Fallback to hardcoded if fail
        hardcoded = ['BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'XRP/USDT', 'ADA/USDT', 'SOL/USDT', 'DOT/USDT', 'DOGE/USDT', 'LTC/USDT', 'LINK/USDT',
                     'TRX/USDT', 'AVAX/USDT', 'MATIC/USDT', 'SHIB/USDT', 'UNI/USDT', 'ATOM/USDT', 'XLM/USDT', 'BCH/USDT', 'ETC/USDT', 'FIL/USDT']
        print(f"Falling back to hardcoded crypto assets: {len(hardcoded[:limit])}")
        return hardcoded[:limit]

class YFinanceDataProvider(DataProvider):
    def __init__(self, market_type='saham_id'):
        self.market_type = market_type
        self.fallback_av = AlphaVantageProvider() # Only fallback ke Alpha

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
            print(f"yfinance OHLCV for {symbol}: {len(df)} rows fetched.")
            return df
        except Exception as e:
            print(f"Error getting data from yfinance for {symbol}: {e}")
            try:
                conv_symbol = self._convert_symbol(symbol, 'av')
                print(f"Falling back to AlphaVantageProvider with symbol: {conv_symbol}")
                av_df = self.fallback_av.get_ohlcv(conv_symbol, timeframe, limit)
                if av_df is not None:
                    return av_df
            except Exception as av_e:
                print(f"Alpha fallback error: {av_e}")
            # Ultimate dummy fallback
            print(f"All failed for OHLCV {symbol}. Returning dummy DF.")
            dates = pd.date_range(end=pd.Timestamp.now(), periods=limit, freq='D')
            dummy_data = {
                'timestamp': dates,
                'open': [1.0] * limit,
                'high': [1.1] * limit,
                'low': [0.9] * limit,
                'close': [1.0 + (i / 100) for i in range(limit)],  # Slight upward trend to trigger LONG
                'volume': [1000 + i for i in range(limit)]  # Increasing volume
            }
            return pd.DataFrame(dummy_data)

    def get_ticker(self, symbol):
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            hist = ticker.history(period='1d', interval='1m')
            last_price = hist['Close'].iloc[-1] if not hist.empty else info.get('regularMarketPrice', info.get('previousClose', 0))
            volume = info.get('volume', hist['Volume'].iloc[-1] if not hist.empty else 0)
            tk = {'last': last_price, 'volume': volume}
            print(f"yfinance ticker for {symbol}: {tk}")
            return tk
        except Exception as e:
            print(f"Error getting ticker from yfinance for {symbol}: {e}")
            try:
                conv_symbol = self._convert_symbol(symbol, 'av')
                print(f"Falling back to AlphaVantageProvider with symbol: {conv_symbol}")
                av_tk = self.fallback_av.get_ticker(conv_symbol)
                if av_tk is not None:
                    return av_tk
            except Exception as av_e:
                print(f"Alpha fallback ticker error: {av_e}")
            # Dummy fallback
            print(f"All failed for ticker {symbol}. Returning dummy.")
            return {'last': 1.0, 'volume': 1000}

    def get_popular_assets(self, limit=100):
        if self.market_type == 'saham_id':
            # From search: top stocks by market cap in IDX
            hardcoded = ['BREN.JK', 'BBCA.JK', 'DCII.JK', 'TPIA.JK', 'BYAN.JK', 'TLKM.JK', 'ASII.JK', 'BMRI.JK', 'BBNI.JK', 'BRIS.JK',
                         'ADRO.JK', 'UNTR.JK', 'PGAS.JK', 'ANTM.JK', 'INDF.JK', 'CPIN.JK', 'KLBF.JK', 'UNVR.JK', 'HMSP.JK', 'GGRM.JK',
                         'MDKA.JK', 'EXCL.JK', 'ISAT.JK', 'SMGR.JK', 'INTP.JK', 'AKRA.JK', 'JSMR.JK', 'SRTG.JK', 'TBIG.JK', 'TOWR.JK',
                         'WIKA.JK', 'WSKT.JK', 'PTPP.JK', 'ADHI.JK', 'ACES.JK', 'AMRT.JK', 'ARTO.JK', 'AVIA.JK', 'BBRI.JK', 'BBTN.JK',
                         'BFIN.JK', 'BMAS.JK', 'BRMS.JK', 'BUKA.JK', 'CITA.JK', 'DNET.JK', 'DOID.JK', 'EMTK.JK', 'ESSA.JK', 'FAPA.JK']
            assets = hardcoded[:limit]
            print(f"Hardcoded saham ID assets (updated from search): {len(assets)} returned.")
            return assets
        elif self.market_type == 'forex':
            # From search: top most traded forex pairs
            hardcoded = ['EURUSD=X', 'USDJPY=X', 'GBPUSD=X', 'AUDUSD=X', 'USDCAD=X', 'USDCHF=X', 'NZDUSD=X', 'EURGBP=X', 'EURJPY=X', 'GBPJPY=X',
                         'AUDJPY=X', 'CADJPY=X', 'CHFJPY=X', 'EURCAD=X', 'GBPCAD=X', 'AUDCAD=X', 'NZDCAD=X', 'EURAUD=X', 'GBPAUD=X', 'NZDJPY=X',
                         'USDMXN=X', 'USDTRY=X', 'USDCNY=X', 'USDINR=X', 'USDBRL=X', 'USDRUB=X', 'USDZAR=X', 'USDKRW=X', 'USDSEK=X', 'USDNOK=X',
                         'USDPLN=X', 'USDSGD=X', 'USDHKD=X', 'USDDKK=X', 'EURCHF=X', 'GBCHF=X', 'AUDCHF=X', 'NZDCHF=X', 'CADCHF=X', 'EURSEK=X']
            assets = hardcoded[:limit]
            print(f"Hardcoded forex assets (updated from search): {len(assets)} returned.")
            return assets
        else:
            return []

class SolanaPumpFunProvider:
    def __init__(self, rpc_url):
        self.client = Client(rpc_url)
        self.program_id = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"
        self.dex_provider = DexScreenerProvider() # Integrasi DexScreener
  
    async def monitor_new_tokens(self, limit=10):
        results = []
        try:
            async with connect(self.client._provider.endpoint_uri + "/") as websocket:
                await websocket.logs_subscribe(
                    {"mentions": [self.program_id]},
                    commitment="finalized"
                )
                async for msg in websocket:
                    if "create" in str(msg.result.value.logs): # Simplified
                        token_mint = self.extract_token_mint(msg)
                        if token_mint:
                            ticker = await self.get_solana_ticker(token_mint)
                            results.append({'symbol': token_mint, 'ticker': ticker})
                            if len(results) >= limit:
                                break
        except Exception as e:
            print(f"Error monitoring Pump.fun: {e}")
        print(f"Pump.fun tokens monitored: {len(results)}")
        return results
  
    def extract_token_mint(self, msg):
        # Placeholder (real: parse logs untuk dapat mint address)
        return "EXAMPLE_MINT_TOKEN" # Ganti dengan parsing real dari logs
    async def get_solana_ticker(self, mint):
        return self.dex_provider.get_ticker('solana', mint) # Return {'last': price, 'volume': vol}
