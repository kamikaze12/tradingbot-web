# data_provider.py
import ccxt
import yfinance as yf
import pandas as pd
import time
import random
from abc import ABC, abstractmethod

class DataProvider(ABC):
    @abstractmethod
    def get_ohlcv(self, symbol, timeframe='1h', limit=200):
        pass

class BybitProvider(DataProvider):
    def __init__(self):
        self.exchange = ccxt.bybit({'enableRateLimit': True})

    def get_ohlcv(self, symbol, timeframe='1h', limit=200):
        try:
            data = self.exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
            df = pd.DataFrame(data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            return df
        except Exception as e:
            print(f"Bybit error for {symbol}: {e}")
            return None

class BinanceUSProvider(DataProvider):
    def __init__(self):
        self.exchange = ccxt.binanceus({'enableRateLimit': True})

    def get_ohlcv(self, symbol, timeframe='1h', limit=200):
        try:
            data = self.exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
            df = pd.DataFrame(data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            return df
        except Exception as e:
            print(f"BinanceUS error for {symbol}: {e}")
            return None

class YahooFinanceProvider(DataProvider):
    def get_ohlcv(self, symbol, timeframe='1h', limit=200):
        try:
            # Ganti simbol agar cocok untuk YFinance (contoh BTC/USDT -> BTC-USD)
            yf_symbol = symbol.replace("/", "-").replace("USDT", "USD")
            df = yf.download(yf_symbol, period='60d', interval='1h')
            if df.empty:
                return None
            df = df.reset_index().rename(columns={
                'Datetime': 'timestamp',
                'Open': 'open',
                'High': 'high',
                'Low': 'low',
                'Close': 'close',
                'Volume': 'volume'
            })
            return df.tail(limit)
        except Exception as e:
            print(f"YFinance error for {symbol}: {e}")
            return None


class AutoDataProvider:
    """
    Provider otomatis: coba Bybit dulu, lalu BinanceUS, terakhir YFinance.
    """
    def __init__(self):
        self.providers = [
            BybitProvider(),
            BinanceUSProvider(),
            YahooFinanceProvider()
        ]

    def get_ohlcv(self, symbol, timeframe='1h', limit=200):
        for provider in self.providers:
            df = provider.get_ohlcv(symbol, timeframe, limit)
            if df is not None and not df.empty:
                print(f"✅ Data OK from {provider.__class__.__name__} for {symbol}")
                return df
        print(f"⚠️ All providers failed for {symbol}")
        return None


def get_top_symbols(limit=20):
    """Ambil daftar coin utama (USDT pair)."""
    coins = [
        'BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'SOL/USDT', 'ADA/USDT',
        'XRP/USDT', 'DOT/USDT', 'DOGE/USDT', 'AVAX/USDT', 'MATIC/USDT',
        'LTC/USDT', 'TRX/USDT', 'LINK/USDT', 'ATOM/USDT', 'UNI/USDT',
        'ETC/USDT', 'XLM/USDT', 'FIL/USDT', 'NEAR/USDT', 'APT/USDT'
    ]
    return coins[:limit]


if __name__ == "__main__":
    provider = AutoDataProvider()
    symbols = get_top_symbols(limit=20)

    for i, symbol in enumerate(symbols, 1):
        print(f"\nAnalyzing {i}/{len(symbols)}: {symbol}")
        df = provider.get_ohlcv(symbol)
        if df is not None and not df.empty:
            print(df.tail(3))
        else:
            print(f"❌ No data available for {symbol}")
        time.sleep(random.uniform(1.5, 2.5))
