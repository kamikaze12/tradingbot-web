import ccxt
import pandas as pd
import yfinance as yf
import time
from abc import ABC, abstractmethod
from solana.rpc.api import Client
from solana.rpc.websocket_api import connect
import asyncio

# =========================
# Base DataProvider
# =========================
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

# =========================
# AutoDataProvider (CCXT + YFinance fallback)
# =========================
class AutoDataProvider(DataProvider):
    def __init__(self):
        self.available_providers = []
        self.active_provider = None
        self.init_providers()

    def init_providers(self):
        exchanges = [
            ("binance", lambda: ccxt.binance({'enableRateLimit': True})),
            ("bybit", lambda: ccxt.bybit({'enableRateLimit': True}))
        ]

        for name, init_fn in exchanges:
            try:
                ex = init_fn()
                ex.load_markets()
                print(f"✅ {name.upper()} connected successfully.")
                self.available_providers.append((name, ex))
            except Exception as e:
                msg = str(e)
                if "451" in msg or "restricted location" in msg.lower():
                    print(f"⚠️ {name.upper()} blocked by region — skipped.")
                    continue
                else:
                    print(f"⚠️ {name.upper()} failed: {msg[:100]}")
                    continue

        if not self.available_providers:
            print("⚠️ All CCXT exchanges failed, using YFinance fallback.")
            self.available_providers.append(("yfinance", None))

        self.active_provider = self.available_providers[0]
        print(f"✅ Active provider set to: {self.active_provider[0].upper()}")

    def get_ohlcv(self, symbol, timeframe='1h', limit=200):
        for name, provider in self.available_providers:
            try:
                if name == "yfinance":
                    yf_symbol = symbol.replace("/", "-").replace("USDT", "USD")
                    data = yf.download(yf_symbol, period="30d", interval="1h")
                    if data.empty:
                        raise Exception("YFinance returned empty data")
                    df = pd.DataFrame({
                        'timestamp': data.index,
                        'open': data['Open'].values,
                        'high': data['High'].values,
                        'low': data['Low'].values,
                        'close': data['Close'].values,
                        'volume': data['Volume'].values
                    })
                    return df.tail(limit)
                ohlcv = provider.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
                df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                return df
            except Exception as e:
                msg = str(e)
                print(f"❌ {name.upper()} error for {symbol}: {msg[:100]}...")
                time.sleep(1)
                continue
        return pd.DataFrame()

    def get_symbols(self):
        symbols = []
        for name, provider in self.available_providers:
            if name == "yfinance":
                return [
                    "BTC/USDT", "ETH/USDT", "BNB/USDT", "SOL/USDT", "ADA/USDT",
                    "XRP/USDT", "DOT/USDT", "DOGE/USDT", "AVAX/USDT", "MATIC/USDT"
                ]
            try:
                markets = provider.load_markets()
                for s in markets:
                    if s.endswith("/USDT"):
                        symbols.append(s)
                return symbols[:20]
            except:
                continue
        return symbols[:20]

    def get_ticker(self, symbol):
        for name, provider in self.available_providers:
            try:
                if name == "yfinance":
                    yf_symbol = symbol.replace("/", "-").replace("USDT", "USD")
                    data = yf.download(yf_symbol, period="1d", interval="1m")
                    if data.empty:
                        raise Exception("YFinance ticker empty")
                    last_price = data['Close'].iloc[-1]
                    high = data['High'].max()
                    low = data['Low'].min()
                    volume = data['Volume'].sum()
                    return {"last": float(last_price), "bid": float(last_price), "ask": float(last_price),
                            "high": float(high), "low": float(low), "volume": float(volume)}
                ticker = provider.fetch_ticker(symbol)
                return {"last": float(ticker['last']), "bid": float(ticker['bid']), "ask": float(ticker['ask']),
                        "high": float(ticker['high']), "low": float(ticker['low']), "volume": float(ticker['baseVolume'])}
            except:
                continue
        return None

# =========================
# Solana Pump Fun
# =========================
class SolanaPumpFunProvider:
    def __init__(self, rpc_url):
        self.client = Client(rpc_url)
        self.program_id = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"

    async def monitor_new_tokens(self, limit=10):
        results = []
        try:
            async with connect(self.client._provider.endpoint_uri + "/") as websocket:
                await websocket.logs_subscribe({"mentions": [self.program_id]}, commitment="finalized")
                async for msg in websocket:
                    if "create" in str(msg.result.value.logs):
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
        return "EXAMPLE_MINT_TOKEN"

    async def get_solana_ticker(self, mint):
        return {'last': 0.001, 'volume': 10000}
