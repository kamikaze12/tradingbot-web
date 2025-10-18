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
import requests  # Untuk Alpha Vantage dan CoinGecko

# Extended mapping untuk crypto, forex, dan saham populer
COMMON_COIN_MAPPING = {
    # Crypto
    'BTC': {'ccxt': 'BTC/USDT', 'yf': 'BTC-USD', 'av': 'BTC', 'cg_id': 'bitcoin'},
    'ETH': {'ccxt': 'ETH/USDT', 'yf': 'ETH-USD', 'av': 'ETH', 'cg_id': 'ethereum'},
    'BNB': {'ccxt': 'BNB/USDT', 'yf': 'BNB-USD', 'av': 'BNB', 'cg_id': 'bnb'},
    'SOL': {'ccxt': 'SOL/USDT', 'yf': 'SOL-USD', 'av': 'SOL', 'cg_id': 'solana'},
    'ADA': {'ccxt': 'ADA/USDT', 'yf': 'ADA-USD', 'av': 'ADA', 'cg_id': 'cardano'},
    'XRP': {'ccxt': 'XRP/USDT', 'yf': 'XRP-USD', 'av': 'XRP', 'cg_id': 'xrp'},
    'DOT': {'ccxt': 'DOT/USDT', 'yf': 'DOT-USD', 'av': 'DOT', 'cg_id': 'polkadot'},
    'DOGE': {'ccxt': 'DOGE/USDT', 'yf': 'DOGE-USD', 'av': 'DOGE', 'cg_id': 'dogecoin'},
    'AVAX': {'ccxt': 'AVAX/USDT', 'yf': 'AVAX-USD', 'av': 'AVAX', 'cg_id': 'avalanche-2'},
    'MATIC': {'ccxt': 'MATIC/USDT', 'yf': 'MATIC-USD', 'av': 'MATIC', 'cg_id': 'polygon'},
    'LINK': {'ccxt': 'LINK/USDT', 'yf': 'LINK-USD', 'av': 'LINK', 'cg_id': 'chainlink'},
    'UNI': {'ccxt': 'UNI/USDT', 'yf': 'UNI-USD', 'av': 'UNI', 'cg_id': 'uniswap'},
    'LTC': {'ccxt': 'LTC/USDT', 'yf': 'LTC-USD', 'av': 'LTC', 'cg_id': 'litecoin'},

    # Forex
    'EURUSD': {'yf': 'EURUSD=X', 'av': 'EUR/USD'},
    'GBPUSD': {'yf': 'GBPUSD=X', 'av': 'GBP/USD'},
    'USDJPY': {'yf': 'USDJPY=X', 'av': 'USD/JPY'},
    'AUDUSD': {'yf': 'AUDUSD=X', 'av': 'AUD/USD'},
    'USDCAD': {'yf': 'USDCAD=X', 'av': 'USD/CAD'},
    'USDCHF': {'yf': 'USDCHF=X', 'av': 'USD/CHF'},
    'NZDUSD': {'yf': 'NZDUSD=X', 'av': 'NZD/USD'},
    'EURGBP': {'yf': 'EURGBP=X', 'av': 'EUR/GBP'},
    'EURJPY': {'yf': 'EURJPY=X', 'av': 'EUR/JPY'},
    'GBPJPY': {'yf': 'GBPJPY=X', 'av': 'GBP/JPY'},

    # Saham ID
    'BBCA': {'yf': 'BBCA.JK', 'av': 'BBCA.JK'},
    'TLKM': {'yf': 'TLKM.JK', 'av': 'TLKM.JK'},
    'ASII': {'yf': 'ASII.JK', 'av': 'ASII.JK'},
    'BMRI': {'yf': 'BMRI.JK', 'av': 'BMRI.JK'},
    'BBNI': {'yf': 'BBNI.JK', 'av': 'BBNI.JK'},
    'BBRI': {'yf': 'BBRI.JK', 'av': 'BBRI.JK'},
    'ANTM': {'yf': 'ANTM.JK', 'av': 'ANTM.JK'},
    'UNVR': {'yf': 'UNVR.JK', 'av': 'UNVR.JK'},
    'INDF': {'yf': 'INDF.JK', 'av': 'INDF.JK'},
    'GOTO': {'yf': 'GOTO.JK', 'av': 'GOTO.JK'},
}

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
        base = symbol.split('=')[0] if '=X' in symbol else symbol.split('.')[0] if '.JK' in symbol else symbol.split('/')[0] if '/' in symbol else symbol.upper()
        mapping = COMMON_COIN_MAPPING.get(base, {})
        if market_type == 'forex':
            return mapping.get('av', f"{base[:3]}/{base[3:]}")  # EURUSD → EUR/USD
        return mapping.get('av', symbol if '.JK' in symbol else base)

    def get_ohlcv(self, symbol, timeframe, limit=200):
        if not self.api_key:
            return None
        try:
            symbol_av = self._convert_symbol(symbol)
            if '/' in symbol_av:  # Forex
                function = "FX_DAILY"
            else:
                function = "DIGITAL_CURRENCY_DAILY" if 'crypto' in symbol_av.lower() else "TIME_SERIES_DAILY"
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
                return df.sort_index().tail(limit)
            else:
                print(f"Error in Alpha Vantage response: {data}")
                return None
        except Exception as e:
            print(f"Error getting OHLCV from Alpha Vantage for {symbol}: {e}")
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
            data = response.json()
            if "Realtime Currency Exchange Rate" in data:
                rate = data["Realtime Currency Exchange Rate"]
                return {'last': float(rate['5. Exchange Rate']), 'volume': 0}
            elif "Global Quote" in data:
                quote = data["Global Quote"]
                return {'last': float(quote['05. price']), 'volume': float(quote.get('06. volume', 0))}
            return None
        except Exception as e:
            print(f"Error getting ticker from Alpha Vantage for {symbol}: {e}")
            return None

    def get_popular_assets(self, limit=100):
        return [COMMON_COIN_MAPPING[k].get('ccxt') or COMMON_COIN_MAPPING[k].get('yf') or COMMON_COIN_MAPPING[k].get('av') for k in list(COMMON_COIN_MAPPING.keys())[:limit]]

class CoinGeckoProvider(DataProvider):
    def __init__(self):
        self.base_url = "https://api.coingecko.com/api/v3"

    def _convert_symbol(self, symbol):
        base = symbol.split('/')[0] if '/' in symbol else symbol.upper()
        return COMMON_COIN_MAPPING.get(base, {}).get('cg_id', base.lower())

    def get_ohlcv(self, symbol, timeframe, limit=200):
        try:
            coin_id = self._convert_symbol(symbol)
            days = max(1, limit // (24 if timeframe == '1h' else 1))
            response = requests.get(f"{self.base_url}/coins/{coin_id}/ohlc?vs_currency=usd&days={days}")
            data = response.json()
            df = pd.DataFrame(data, columns=['timestamp', 'open', 'high', 'low', 'close'])
            df['volume'] = 0
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            return df.tail(limit)
        except Exception as e:
            print(f"Error getting OHLCV from CoinGecko for {symbol}: {e}")
            return None

    def get_ticker(self, symbol):
        try:
            coin_id = self._convert_symbol(symbol)
            response = requests.get(f"{self.base_url}/simple/price?ids={coin_id}&vs_currencies=usd&include_24hr_vol=true")
            data = response.json()
            if coin_id in data:
                return {'last': data[coin_id]['usd'], 'volume': data[coin_id].get('usd_24h_vol', 0)}
            return None
        except Exception as e:
            print(f"Error getting ticker from CoinGecko for {symbol}: {e}")
            return None

    def get_popular_assets(self, limit=100):
        try:
            response = requests.get(f"{self.base_url}/coins/markets?vs_currency=usd&order=market_cap_desc&per_page={limit}&page=1")
            data = response.json()
            return [f"{item['symbol'].upper()}/USDT" for item in data]
        except:
            return [COMMON_COIN_MAPPING[k]['ccxt'] for k in list(COMMON_COIN_MAPPING.keys()) if 'ccxt' in COMMON_COIN_MAPPING[k]][:limit]

class CCXTDataProvider(DataProvider):
    def __init__(self, exchange_id='bybit', api_key='', secret=''):
        exchange_class = getattr(ccxt, exchange_id)
        self.exchange = exchange_class({
            'apiKey': api_key,
            'secret': secret,
            'enableRateLimit': True,
        })
        self.fallback_yf = YFinanceDataProvider(market_type='crypto')
        self.fallback_cg = CoinGeckoProvider()
        self.fallback_av = AlphaVantageProvider()  # Last untuk hemat limit 25/day

    def _convert_symbol(self, symbol, target='yf'):
        base = symbol.split('/')[0] if '/' in symbol else symbol.upper()
        mapping = COMMON_COIN_MAPPING.get(base, {})
        if target == 'yf':
            return mapping.get('yf', f"{base}-USD")
        elif target == 'cg':
            return mapping.get('cg_id', base.lower())
        elif target == 'av':
            return mapping.get('av', base)
        return symbol

    def get_ohlcv(self, symbol, timeframe, limit=200):
        try:
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            return df
        except Exception as e:
            print(f"Error getting data from CCXT for {symbol}: {e}")
            # Fallback chain: yf → cg → av (hemat av)
            for fallback, target in [(self.fallback_yf, 'yf'), (self.fallback_cg, 'cg'), (self.fallback_av, 'av')]:
                try:
                    conv_symbol = self._convert_symbol(symbol, target)
                    print(f"Falling back to {fallback.__class__.__name__} with symbol: {conv_symbol}")
                    df = fallback.get_ohlcv(conv_symbol, timeframe, limit)
                    if df is not None:
                        return df
                except:
                    pass
            return None

    def get_ticker(self, symbol):
        try:
            return self.exchange.fetch_ticker(symbol)
        except Exception as e:
            print(f"Error getting ticker from CCXT for {symbol}: {e}")
            for fallback, target in [(self.fallback_yf, 'yf'), (self.fallback_cg, 'cg'), (self.fallback_av, 'av')]:
                try:
                    conv_symbol = self._convert_symbol(symbol, target)
                    print(f"Falling back to {fallback.__class__.__name__} with symbol: {conv_symbol}")
                    ticker = fallback.get_ticker(conv_symbol)
                    if ticker is not None:
                        return ticker
                except:
                    pass
            return None

    def get_popular_assets(self, limit=100):
        try:
            markets = self.exchange.load_markets()
            if self.exchange.id in ['binance', 'bybit']:
                usdt_markets = [symbol for symbol in markets if symbol.endswith('/USDT')]
                excluded_coins = ['BUSD', 'USDC', 'DAI', 'TUSD', 'USDP', 'UST']
                filtered_markets = [symbol for symbol in usdt_markets if not any(excluded in symbol for excluded in excluded_coins)]
                try:
                    tickers = self.exchange.fetch_tickers()
                    filtered_markets.sort(key=lambda x: tickers[x]['quoteVolume'] if x in tickers else 0, reverse=True)
                except:
                    pass
                return filtered_markets[:limit]
        except:
            print("Falling back to CoinGecko for popular assets")
            return self.fallback_cg.get_popular_assets(limit)

class YFinanceDataProvider(DataProvider):
    def __init__(self, market_type='saham_id'):
        self.market_type = market_type
        self.fallback_av = AlphaVantageProvider()  # Only fallback ke Alpha

    def _convert_symbol(self, symbol, target='av'):
        base = symbol.split('=')[0] if '=X' in symbol else symbol.split('.')[0] if '.JK' in symbol else symbol
        mapping = COMMON_COIN_MAPPING.get(base, {})
        if target == 'av':
            if self.market_type == 'forex':
                from_curr, to_curr = base[:3], base[3:]
                return f"{from_curr}/{to_curr}"
            return mapping.get('av', symbol)
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
            if 'datetime' in df.columns:
                df.rename(columns={'datetime': 'timestamp'}, inplace=True)
            df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
            return df
        except Exception as e:
            print(f"Error getting data from yfinance for {symbol}: {e}")
            try:
                conv_symbol = self._convert_symbol(symbol, 'av')
                print(f"Falling back to AlphaVantageProvider with symbol: {conv_symbol}")
                return self.fallback_av.get_ohlcv(conv_symbol, timeframe, limit)
            except:
                return None

    def get_ticker(self, symbol):
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            hist = ticker.history(period='1d', interval='1m')
            last_price = hist['Close'].iloc[-1] if not hist.empty else info.get('regularMarketPrice', 0)
            return {'last': last_price, 'volume': info.get('volume', 0)}
        except Exception as e:
            print(f"Error getting ticker from yfinance for {symbol}: {e}")
            try:
                conv_symbol = self._convert_symbol(symbol, 'av')
                print(f"Falling back to AlphaVantageProvider with symbol: {conv_symbol}")
                return self.fallback_av.get_ticker(conv_symbol)
            except:
                return None

    def get_popular_assets(self, limit=50):
        if self.market_type == 'saham_id':
            return [COMMON_COIN_MAPPING[k]['yf'] for k in ['BBCA', 'TLKM', 'ASII', 'BMRI', 'BBNI', 'BBRI', 'ANTM', 'UNVR', 'INDF', 'GOTO']][:limit]
        elif self.market_type == 'forex':
            return [COMMON_COIN_MAPPING[k]['yf'] for k in ['EURUSD', 'GBPUSD', 'USDJPY', 'AUDUSD', 'USDCAD', 'USDCHF', 'NZDUSD', 'EURGBP', 'EURJPY', 'GBPJPY']][:limit]
        elif self.market_type == 'crypto':
            return [COMMON_COIN_MAPPING[k]['yf'] for k in list(COMMON_COIN_MAPPING.keys()) if 'yf' in COMMON_COIN_MAPPING[k] and 'ccxt' in COMMON_COIN_MAPPING[k]][:limit]
        return []

class SolanaPumpFunProvider:
    # Sama seperti sebelumnya, tidak berubah
    def __init__(self, rpc_url):
        self.client = Client(rpc_url)
        self.program_id = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"
    
    async def monitor_new_tokens(self, limit=10):
        results = []
        try:
            async with connect(self.client._provider.endpoint_uri + "/") as websocket:
                await websocket.logs_subscribe(
                    {"mentions": [self.program_id]},
                    commitment="finalized"
                )
                async for msg in websocket:
                    if "create" in str(msg.result.value.logs):  # Simplified
                        token_mint = self.extract_token_mint(msg)
                        if token_mint:
                            ticker = await self.get_solana_ticker(token_mint)
                            results.append({'symbol': token_mint, 'ticker': ticker})
                            if len(results) >= limit:
                                break
        except Exception as e:
            print(f"Error monitoring Pump.fun: {e}")
        return results
    
    def extract_token_mint(self, msg):
        # Placeholder (real: parse logs)
        return "EXAMPLE_MINT_TOKEN"
    
    async def get_solana_ticker(self, mint):
        # Placeholder (real: Birdeye/Dexscreener API)
        return {'last': 0.001, 'volume': 10000}
