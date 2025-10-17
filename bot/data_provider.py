import ccxt
import pandas as pd
import yfinance as yf
from abc import ABC, abstractmethod
import random
import datetime

# ====================================================
# 🔹 Base Class
# ====================================================
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


# ====================================================
# 🔹 CCXT Provider (Generic)
# ====================================================
class CCXTDataProvider(DataProvider):
    def __init__(self, exchange_id='binance'):
        exchange_class = getattr(ccxt, exchange_id)
        self.exchange = exchange_class({'enableRateLimit': True})
        self.id = exchange_id

    def get_ohlcv(self, symbol, timeframe='1h', limit=200):
        try:
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            return df
        except Exception as e:
            print(f"[{self.id}] ❌ {symbol} failed: {e}")
            return None

    def get_ticker(self, symbol):
        try:
            return self.exchange.fetch_ticker(symbol)
        except Exception as e:
            print(f"[{self.id}] ❌ Ticker failed: {e}")
            return None

    def get_popular_assets(self, limit=20):
        try:
            markets = self.exchange.load_markets()
            usdt_pairs = [s for s in markets if s.endswith('/USDT')]
            excluded = ['BUSD', 'USDC', 'DAI', 'TUSD', 'USDP', 'UST']
            filtered = [s for s in usdt_pairs if not any(x in s for x in excluded)]
            tickers = self.exchange.fetch_tickers()
            filtered.sort(
                key=lambda s: tickers[s]['quoteVolume'] if s in tickers and 'quoteVolume' in tickers[s] else 0,
                reverse=True
            )
            return filtered[:limit]
        except Exception as e:
            print(f"[{self.id}] ⚠️ Error loading markets: {e}")
            return []


# ====================================================
# 🔹 Yahoo Finance Provider
# ====================================================
class YFinanceDataProvider(DataProvider):
    def get_ohlcv(self, symbol, timeframe='1h', limit=200):
        try:
            yf_symbol = self._to_yfinance_symbol(symbol)
            interval_map = {'1h': '1h', '4h': '4h', '1d': '1d'}
            interval = interval_map.get(timeframe, '1h')
            period = '7d' if interval == '1h' else '1y'

            ticker = yf.Ticker(yf_symbol)
            df = ticker.history(period=period, interval=interval)
            if len(df) > limit:
                df = df.tail(limit)
            df.reset_index(inplace=True)
            df.columns = [c.lower() for c in df.columns]
            if 'datetime' in df.columns:
                df.rename(columns={'datetime': 'timestamp'}, inplace=True)
            df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
            return df
        except Exception as e:
            print(f"[YF] ❌ {symbol}: {e}")
            return None

    def get_ticker(self, symbol):
        try:
            yf_symbol = self._to_yfinance_symbol(symbol)
            ticker = yf.Ticker(yf_symbol)
            hist = ticker.history(period='1d', interval='1m')
            last_price = hist['close'].iloc[-1] if not hist.empty else None
            return {'last': last_price}
        except Exception as e:
            print(f"[YF] ❌ Ticker {symbol}: {e}")
            return None

    def get_popular_assets(self, limit=20):
        base = ['BTC-USD', 'ETH-USD', 'BNB-USD', 'SOL-USD', 'XRP-USD', 'ADA-USD', 'DOGE-USD', 'DOT-USD',
                'AVAX-USD', 'MATIC-USD', 'LINK-USD', 'LTC-USD', 'TRX-USD', 'NEAR-USD', 'ATOM-USD',
                'OP-USD', 'APT-USD', 'ARB-USD', 'FIL-USD', 'ICP-USD']
        return base[:limit]

    def _to_yfinance_symbol(self, symbol):
        """Convert CCXT-style symbol (e.g., BTC/USDT) to Yahoo style (BTC-USD)."""
        if '/' in symbol:
            base, quote = symbol.split('/')
            if quote == 'USDT':
                quote = 'USD'
            return f"{base}-{quote}"
        return symbol


# ====================================================
# 🔹 Dummy Provider (optional last fallback)
# ====================================================
class DummyDataProvider(DataProvider):
    def get_ohlcv(self, symbol, timeframe='1h', limit=200):
        print(f"[DUMMY] ⚠️ Generating random data for {symbol}")
        now = datetime.datetime.utcnow()
        timestamps = [now - datetime.timedelta(hours=i) for i in range(limit)][::-1]
        return pd.DataFrame({
            'timestamp': timestamps,
            'open': [random.uniform(10, 100) for _ in range(limit)],
            'high': [random.uniform(100, 200) for _ in range(limit)],
            'low': [random.uniform(5, 90) for _ in range(limit)],
            'close': [random.uniform(10, 120) for _ in range(limit)],
            'volume': [random.uniform(1000, 5000) for _ in range(limit)]
        })

    def get_ticker(self, symbol):
        return {'last': random.uniform(10, 100), 'volume': random.uniform(1000, 50000)}

    def get_popular_assets(self, limit=20):
        return [f"DUMMY{i}" for i in range(limit)]


# ====================================================
# 🔹 Auto Switch Provider (Core)
# ====================================================
class AutoDataProvider:
    def __init__(self):
        self.providers = [
            CCXTDataProvider('binance'),
            CCXTDataProvider('binanceus'),
            CCXTDataProvider('bybit'),
            YFinanceDataProvider(),
            DummyDataProvider()
        ]

    def _convert_symbol_for_provider(self, symbol, provider):
        """Convert symbol depending on provider."""
        if isinstance(provider, YFinanceDataProvider):
            return symbol.replace('/', '-').replace('USDT', 'USD')
        else:
            return symbol.replace('-', '/').replace('USD', 'USDT')

    def get_ohlcv(self, symbol, timeframe='1h', limit=200):
        for provider in self.providers:
            adapted_symbol = self._convert_symbol_for_provider(symbol, provider)
            df = provider.get_ohlcv(adapted_symbol, timeframe, limit)
            if df is not None and not df.empty:
                print(f"✅ Using {provider.__class__.__name__} ({getattr(provider, 'id', 'YF')}) for {symbol}")
                return df
        print("❌ All providers failed")
        return pd.DataFrame()

    def get_ticker(self, symbol):
        for provider in self.providers:
            adapted_symbol = self._convert_symbol_for_provider(symbol, provider)
            data = provider.get_ticker(adapted_symbol)
            if data and data.get('last') is not None:
                print(f"✅ Using {provider.__class__.__name__} ({getattr(provider, 'id', 'YF')}) for ticker {symbol}")
                return data
        return {'last': None}

    def get_popular_assets(self, limit=20):
        for provider in self.providers:
            try:
                assets = provider.get_popular_assets(limit)
                if assets:
                    print(f"✅ Using {provider.__class__.__name__} ({getattr(provider, 'id', 'YF')}) for list")
                    return assets
            except Exception as e:
                print(f"⚠️ Error fetching from {provider.__class__.__name__}: {e}")
        return []


# ====================================================
# 🔹 Test / Demo
# ====================================================
if __name__ == "__main__":
    provider = AutoDataProvider()
    print("\n=== 🔹 POPULAR COINS ===")
    coins = provider.get_popular_assets(20)
    print(coins)

    symbol = coins[0]
    print(f"\n=== 🔹 OHLCV for {symbol} ===")
    df = provider.get_ohlcv(symbol, '1h', 10)
    print(df.tail())

    print(f"\n=== 🔹 TICKER for {symbol} ===")
    print(provider.get_ticker(symbol))
