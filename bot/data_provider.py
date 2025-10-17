import ccxt
import pandas as pd
import yfinance as yf
import time

class DataProvider:
    def get_ohlcv(self, symbol, timeframe, limit):
        raise NotImplementedError("Must implement get_ohlcv() in subclass")

class AutoDataProvider(DataProvider):
    def __init__(self):
        self.providers = [
            ("binance", ccxt.binance({'enableRateLimit': True})),
            ("bybit", ccxt.bybit({'enableRateLimit': True})),
            ("yfinance", None)
        ]

    def get_ohlcv(self, symbol, timeframe='1h', limit=200):
        for name, provider in self.providers:
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

                # CCXT provider (Binance or Bybit)
                ohlcv = provider.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
                df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                return df

            except Exception as e:
                err = str(e)
                print(f"[{name.upper()}] Error fetching {symbol}: {err[:100]}...")
                if "451" in err or "restricted location" in err.lower():
                    print(f"⚠️ {name} blocked by region — switching provider...")
                    continue
                time.sleep(1)
                continue

        print(f"❌ All providers failed for {symbol}")
        return pd.DataFrame()

    def get_symbols(self):
        """Return up to 20 USDT pairs from Binance or fallback"""
        symbols = []
        for name, provider in self.providers:
            if name == "yfinance":
                # fallback list if all exchanges blocked
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
                print(f"[{name.upper()}] Loaded {len(symbols)} symbols")
                return symbols[:20]
            except Exception as e:
                print(f"[{name.upper()}] Failed to load symbols: {e}")
                continue
        return symbols[:20]
