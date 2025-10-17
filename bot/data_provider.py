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
import requests  # Tambah untuk Alpha Vantage dan CoinGecko

# Mapping untuk top koin populer
COMMON_COIN_MAPPING = {
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
    # Tambah lebih jika perlu, seperti sebelumnya
    'LINK': {'ccxt': 'LINK/USDT', 'yf': 'LINK-USD', 'av': 'LINK', 'cg_id': 'chainlink'},
    'UNI': {'ccxt': 'UNI/USDT', 'yf': 'UNI-USD', 'av': 'UNI', 'cg_id': 'uniswap'},
    'LTC': {'ccxt': 'LTC/USDT', 'yf': 'LTC-USD', 'av': 'LTC', 'cg_id': 'litecoin'},
    # ... (extend dari list sebelumnya jika mau full 50)
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
            raise ValueError("Alpha Vantage API key required.")
        self.base_url = "https://www.alphavantage.co/query"

    def _convert_symbol(self, symbol):
        if '/' in symbol:
            base, _ = symbol.split('/')
            base = base.upper()
        else:
            base = symbol.upper()
        return COMMON_COIN_MAPPING.get(base, {}).get('av', base)

    def get_ohlcv(self, symbol, timeframe, limit=200):
        try:
            symbol_av = self._convert_symbol(symbol)
            function = "CRYPTO_INTRADAY" if timeframe in ['1m', '5m', '15m', '30m', '60m'] else "DIGITAL_CURRENCY_DAILY"
            params = {
                "function": function,
                "symbol": symbol_av,
                "market": "USD",
                "interval": timeframe if function == "CRYPTO_INTRADAY" else None,
                "apikey": self.api_key,
                "outputsize": "full" if limit > 100 else "compact"
            }
            response = requests.get(self.base_url, params=params)
            data = response.json()
            if "Time Series Crypto" in data:
                time_series_key = list(data.keys())[1]  # Dynamic key seperti 'Time Series Crypto (5min)'
                ohlcv_data = data[time_series_key]
                df = pd.DataFrame.from_dict(ohlcv_data, orient='index')
                df = df.astype(float)
                df['timestamp'] = pd.to_datetime(df.index)
                df = df[['timestamp', '1. open', '2. high', '3. low', '4. close', '5. volume']]
                df.columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
                return df.sort_index().tail(limit)
            else:
                print(f"Error in Alpha Vantage response: {data}")
                return None
        except Exception as e:
            print(f"Error getting OHLCV from Alpha Vantage for {symbol}: {e}")
            return None

    def get_ticker(self, symbol):
        try:
            symbol_av = self._convert_symbol(symbol)
            params = {
                "function": "CURRENCY_EXCHANGE_RATE",
                "from_currency": symbol_av,
                "to_currency": "USD",
                "apikey": self.api_key
            }
            response = requests.get(self.base_url, params=params)
            data = response.json()
            if "Realtime Currency Exchange Rate" in data:
                rate = data["Realtime Currency Exchange Rate"]
                return {'last': float(rate['5. Exchange Rate']), 'volume': 0}  # Volume not directly available
            return None
        except Exception as e:
            print(f"Error getting ticker from Alpha Vantage for {symbol}: {e}")
            return None

    def get_popular_assets(self, limit=100):
        # Fallback ke hardcoded karena Alpha Vantage no direct popular list
        return [COMMON_COIN_MAPPING[k]['ccxt'] for k in list(COMMON_COIN_MAPPING.keys())[:limit]]

class CoinGeckoProvider(DataProvider):
    def __init__(self):
        self.base_url = "https://api.coingecko.com/api/v3"

    def _convert_symbol(self, symbol):
        if '/' in symbol:
            base, _ = symbol.split('/')
            base = base.upper()
        else:
            base = symbol.upper()
        return COMMON_COIN_MAPPING.get(base, {}).get('cg_id', base.lower())

    def get_ohlcv(self, symbol, timeframe, limit=200):
        try:
            coin_id = self._convert_symbol(symbol)
            days = max(1, limit // (24 if timeframe == '1h' else 1))  # Approx days
            response = requests.get(f"{self.base_url}/coins/{coin_id}/ohlc?vs_currency=usd&days={days}")
            data = response.json()
            df = pd.DataFrame(data, columns=['timestamp', 'open', 'high', 'low', 'close'])
            df['volume'] = 0  # CoinGecko OHLC no volume
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
            return [f"{item['symbol'].upper()}/USDT" for item in data]  # Format ke CCXT style
        except:
            return [COMMON_COIN_MAPPING[k]['ccxt'] for k in list(COMMON_COIN_MAPPING.keys())[:limit]]

class CCXTDataProvider(DataProvider):
    def __init__(self, exchange_id='bybit', api_key='', secret=''):
        exchange_class = getattr(ccxt, exchange_id)
        self.exchange = exchange_class({
            'apiKey': api_key,
            'secret': secret,
            'enableRateLimit': True,
        })
        self.fallback_av = AlphaVantageProvider()  # Fallback primary ke Alpha
        self.fallback_cg = CoinGeckoProvider()
        self.fallback_yf = YFinanceDataProvider(market_type='crypto')

    def _convert_symbol(self, symbol, target='av'):
        if '/' in symbol:
            base, _ = symbol.split('/')
            base = base.upper()
        else:
            base = symbol.upper()
        if target == 'av':
            return COMMON_COIN_MAPPING.get(base, {}).get('av', base)
        elif target == 'cg':
            return COMMON_COIN_MAPPING.get(base, {}).get('cg_id', base.lower())
        elif target == 'yf':
            return COMMON_COIN_MAPPING.get(base, {}).get('yf', f"{base}-USD")
        return symbol

    def get_ohlcv(self, symbol, timeframe, limit=200):
        try:
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            return df
        except Exception as e:
            print(f"Error getting data from CCXT for {symbol}: {e}")
            # Fallback chain: Alpha -> CG -> YF
            for fallback in [self.fallback_av, self.fallback_cg, self.fallback_yf]:
                try:
                    conv_symbol = self._convert_symbol(symbol, 'av' if fallback == self.fallback_av else 'cg' if fallback == self.fallback_cg else 'yf')
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
            # Fallback chain sama
            for fallback in [self.fallback_av, self.fallback_cg, self.fallback_yf]:
                try:
                    conv_symbol = self._convert_symbol(symbol, 'av' if fallback == self.fallback_av else 'cg' if fallback == self.fallback_cg else 'yf')
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
            if self.exchange.id in ['binance', 'bybit']:  # Adjust per exchange
                usdt_markets = [symbol for symbol in markets if symbol.endswith('/USDT')]
                excluded_coins = ['BUSD', 'USDC', 'DAI', 'TUSD', 'USDP', 'UST']
                filtered_markets = [
                    symbol for symbol in usdt_markets 
                    if not any(excluded in symbol for excluded in excluded_coins)
                ]
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
    def __init__(self, market_type='saham_id'):  # 'saham_id' or 'forex' or 'crypto'
        self.market_type = market_type
        
    def get_ohlcv(self, symbol, timeframe='1h', limit=200):
        try:
            # Map timeframe yfinance: '1h', '2h', '1d', etc.
            interval_map = {'1h': '1h', '4h': '4h', '1d': '1d', '1w': '1wk'}
            interval = interval_map.get(timeframe, '1h')
            
            # Period: adjust berdasarkan interval dan limit
            if interval == '1h':
                period = '5d' if limit <= 120 else '2mo'  # Max 730h ~1mo, tapi extend
            elif interval == '1d':
                period = '1y'
            else:
                period = '1y'
            
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=period, interval=interval)
            if len(df) > limit:
                df = df.tail(limit)
            df.reset_index(inplace=True)
            df.columns = [col.lower() for col in df.columns]  # Normalize: 'datetime' -> 'timestamp'
            if 'datetime' in df.columns:
                df.rename(columns={'datetime': 'timestamp'}, inplace=True)
            df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
            return df
        except Exception as e:
            print(f"Error getting data for {symbol}: {e}")
            return None
            
    def get_ticker(self, symbol):
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            hist = ticker.history(period='1d', interval='1m')  # Latest price
            if not hist.empty:
                last_price = hist['Close'].iloc[-1]
            else:
                last_price = info.get('regularMarketPrice', 0)
            return {'last': last_price, 'volume': info.get('volume', 0)}
        except Exception as e:
            print(f"Error getting ticker for {symbol}: {e}")
            return None
            
    def get_popular_assets(self, limit=50):
        if self.market_type == 'saham_id':
            return ['BBCA.JK', 'TLKM.JK', 'ASII.JK', 'BMRI.JK', 'BBNI.JK', 'BBRI.JK', 'ANTM.JK', 'UNVR.JK', 'INDF.JK', 'GOTO.JK'][:limit]
        elif self.market_type == 'forex':
            return [
                'EURUSD=X', 'GBPUSD=X', 'USDJPY=X', 'AUDUSD=X', 'USDCAD=X', 
                'USDCHF=X', 'NZDUSD=X', 'EURGBP=X', 'EURJPY=X', 'GBPJPY=X'
            ][:limit]
        elif self.market_type == 'crypto':
            return [COMMON_COIN_MAPPING[k]['yf'] for k in list(COMMON_COIN_MAPPING.keys())[:limit]]

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
