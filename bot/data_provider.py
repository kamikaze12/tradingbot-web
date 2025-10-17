import ccxt
import pandas as pd
import yfinance as yf
import time

class DataProvider:
    def get_ohlcv(self, symbol, timeframe, limit):
        raise NotImplementedError("Must implement get_ohlcv() in subclass")

class AutoDataProvider(DataProvider):
    def __init__(self):
        self.available_providers = []
        self.active_provider = None
        self.init_providers()

    def init_providers(self):
        """Initialize providers and skip blocked ones"""
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
                    print(f"⚠️ {name.upper()} failed to initialize: {msg[:100]}")
                    continue

        # If both CCXT exchanges fail, use yfinance
        if not self.available_providers:
            print("⚠️ All CCXT exchanges failed, using YFINANCE fallback.")
            self.available_providers.append(("yfinance", None))

        # Choose first available
        self.active_provider = self.available_providers[0]
        print(f"✅ Active provider set to: {self.active_provider[0].upper()}")

    def get_ohlcv(self, symbol, timeframe='1h', limit=200):
        for name, provider in self.available_providers:
            try:
                if name == "yfinance":
                    yf_symbol = symbol.replace("/", "-").replace("USDT", "USD")
                    print(f"📈 Fetching from YFINANCE: {yf_symbol}")
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

                print(f"📈 Fetching from {name.upper()}: {symbol}")
                ohlcv = provider.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
                df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                return df

            except Exception as e:
                msg = str(e)
                print(f"❌ {name.upper()} error for {symbol}: {msg[:100]}...")
                if "451" in msg or "restricted location" in msg.lower():
                    print(f"⚠️ {name.upper()} blocked, switching provider...")
                    continue
                time.sleep(1)
                continue

        print(f"❌ All providers failed for {symbol}")
        return pd.DataFrame()

    def get_symbols(self):
        """Return up to 20 USDT pairs from first working provider"""
        symbols = []
        for name, provider in self.available_providers:
            if name == "yfinance":
                print("Using fallback symbol list for YFinance.")
                return [
                    "BTC/USDT", "ETH/USDT", "BNB/USDT", "SOL/USDT", "ADA/USDT",
                    "XRP/USDT", "DOT/USDT", "DOGE/USDT", "AVAX/USDT", "MATIC/USDT",
                    "LTC/USDT", "TRX/USDT", "LINK/USDT", "NEAR/USDT", "ATOM/USDT",
                    "ETC/USDT", "UNI/USDT", "XLM/USDT", "APT/USDT", "ICP/USDT"
                ]
            try:
                markets = provider.load_markets()
                for s in markets:
                    if s.endswith("/USDT"):
                        symbols.append(s)
                print(f"✅ {name.upper()} loaded {len(symbols)} symbols.")
                return symbols[:20]
            except Exception as e:
                print(f"⚠️ {name.upper()} failed to load symbols: {e}")
                continue
        return symbols[:20]
