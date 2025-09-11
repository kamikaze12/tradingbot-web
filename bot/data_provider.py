import ccxt
import pandas as pd
import yfinance as yf
from abc import ABC, abstractmethod
from solana.rpc.api import Client
from solana.rpc.websocket_api import connect
import json
import asyncio
import base58  # Untuk decode pubkey

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

class CCXTDataProvider(DataProvider):
    def __init__(self, exchange_id='binance', api_key='', secret=''):
        exchange_class = getattr(ccxt, exchange_id)
        self.exchange = exchange_class({
            'apiKey': api_key,
            'secret': secret,
            'enableRateLimit': True,
        })
        
    def get_ohlcv(self, symbol, timeframe, limit=200):
        try:
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            return df
        except Exception as e:
            print(f"Error getting data for {symbol}: {e}")
            return None
            
    def get_ticker(self, symbol):
        try:
            return self.exchange.fetch_ticker(symbol)
        except Exception as e:
            print(f"Error getting ticker for {symbol}: {e}")
            return None
            
    def get_popular_assets(self, limit=100):
        try:
            markets = self.exchange.load_markets()
            if self.exchange.id == 'binance':
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
            # Fallback untuk crypto
            return [
                'BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'SOL/USDT', 'ADA/USDT',
                'XRP/USDT', 'DOT/USDT', 'DOGE/USDT', 'AVAX/USDT', 'MATIC/USDT',
                # ... (sama seperti sebelumnya)
            ]

class YFinanceDataProvider(DataProvider):
    def __init__(self, market_type='saham_id'):  # 'saham_id' or 'forex'
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
                last_price = hist['close'].iloc[-1]
            else:
                last_price = info.get('regularMarketPrice', 0)
            return {'last': last_price, 'volume': info.get('volume', 0)}
        except Exception as e:
            print(f"Error getting ticker for {symbol}: {e}")
            return None
            
    def get_popular_assets(self, limit=50):
        if self.market_type == 'saham_id':
            # IDX stocks
            return ['BBCA.JK', 'TLKM.JK', 'ASII.JK', 'BMRI.JK', 'BBNI.JK', 'BBRI.JK', 'ANTM.JK', 'UNVR.JK', 'INDF.JK', 'GOTO.JK'][:limit]
        elif self.market_type == 'forex':
            # Popular forex pairs via Yahoo symbols
            return [
                'EURUSD=X', 'GBPUSD=X', 'USDJPY=X', 'AUDUSD=X', 'USDCAD=X', 
                'USDCHF=X', 'NZDUSD=X', 'EURGBP=X', 'EURJPY=X', 'GBPJPY=X',
                'AUDJPY=X', 'USDSGD=X', 'EURCAD=X', 'AUDCAD=X', 'NZDJPY=X'
            ][:limit]

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