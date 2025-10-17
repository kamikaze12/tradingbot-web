import ccxt
import yfinance as yf
import pandas as pd
import requests
import asyncio
import aiohttp
import time


# =========================================================
# === Base Class ==========================================
# =========================================================
class BaseDataProvider:
    def get_ohlcv(self, symbol, timeframe, limit):
        raise NotImplementedError

    def get_ticker(self, symbol):
        raise NotImplementedError

    def get_popular_assets(self, limit):
        raise NotImplementedError


# =========================================================
# === CCXT (Binance / Bybit) ==============================
# =========================================================
class CCXTDataProvider(BaseDataProvider):
    def __init__(self, exchange_name="binance", api_key="", api_secret=""):
        try:
            self.exchange = getattr(ccxt, exchange_name)({
                "enableRateLimit": True,
                "timeout": 30000,
            })
            self.exchange_name = exchange_name
            self.ok = True
            print(f"CCXTDataProvider initialized for {exchange_name}")
        except Exception as e:
            print(f"Failed to init CCXT for {exchange_name}: {e}")
            self.ok = False

    def get_ohlcv(self, symbol, timeframe="1h", limit=200):
        """Get OHLCV with fallback handling"""
        try:
            if not self.ok:
                raise Exception("Exchange not initialized")
            data = self.exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
            df = pd.DataFrame(
                data,
                columns=["timestamp", "open", "high", "low", "close", "volume"]
            )
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
            return df
        except Exception as e:
            print(f"[{self.exchange_name}] OHLCV error for {symbol}: {e}")
            return None

    def get_ticker(self, symbol):
        try:
            if not self.ok:
                raise Exception("Exchange not initialized")
            return self.exchange.fetch_ticker(symbol)
        except Exception as e:
            print(f"[{self.exchange_name}] Ticker error for {symbol}: {e}")
            return None

    def get_popular_assets(self, limit=20):
        """Top symbols by volume"""
        try:
            if not self.ok:
                raise Exception("Exchange not initialized")
            markets = self.exchange.load_markets()
            sorted_markets = sorted(
                markets.values(),
                key=lambda x: x.get("info", {}).get("quoteVolume", 0),
                reverse=True
            )
            symbols = [m["symbol"] for m in sorted_markets if "/USDT" in m["symbol"]][:limit]
            return symbols
        except Exception as e:
            print(f"[{self.exchange_name}] Error fetching assets: {e}")
            return []


# =========================================================
# === YFinance Provider ===================================
# =========================================================
class YFinanceDataProvider(BaseDataProvider):
    def __init__(self, market_type="crypto"):
        self.market_type = market_type
        print(f"YFinanceDataProvider initialized for {market_type}")

    def _convert_symbol(self, symbol):
        """Convert Binance-like symbol to Yahoo Finance format"""
        if self.market_type == "crypto":
            base = symbol.split("/")[0].replace("USDT", "USD")
            return f"{base}-USD"
        elif self.market_type == "forex":
            return symbol
        elif self.market_type == "saham_id":
            return symbol
        else:
            return symbol

    def get_ohlcv(self, symbol, timeframe="1h", limit=200):
        try:
            yf_symbol = self._convert_symbol(symbol)
            interval = "1h" if timeframe == "1h" else "1d"
            df = yf.download(yf_symbol, period="90d", interval=interval, progress=False)
            df = df.rename(columns=str.lower).reset_index()
            df = df.tail(limit)
            return df
        except Exception as e:
            print(f"[YFinance] Error getting OHLCV for {symbol}: {e}")
            return None

    def get_ticker(self, symbol):
        try:
            yf_symbol = self._convert_symbol(symbol)
            data = yf.Ticker(yf_symbol).history(period="1d")
            if not data.empty:
                return {"last": float(data["Close"].iloc[-1])}
            return None
        except Exception as e:
            print(f"[YFinance] Error fetching ticker for {symbol}: {e}")
            return None

    def get_popular_assets(self, limit=20):
        if self.market_type == "crypto":
            return [
                "BTC/USDT", "ETH/USDT", "BNB/USDT", "SOL/USDT", "ADA/USDT",
                "XRP/USDT", "DOGE/USDT", "AVAX/USDT", "DOT/USDT", "MATIC/USDT",
                "LTC/USDT", "LINK/USDT", "TRX/USDT", "UNI/USDT", "ATOM/USDT",
                "NEAR/USDT", "FIL/USDT", "ETC/USDT", "HBAR/USDT", "APT/USDT"
            ][:limit]
        elif self.market_type == "forex":
            return ['EURUSD=X', 'GBPUSD=X', 'USDJPY=X', 'AUDUSD=X', 'USDCAD=X'][:limit]
        elif self.market_type == "saham_id":
            return ['BBCA.JK', 'BMRI.JK', 'BBNI.JK', 'TLKM.JK', 'ASII.JK'][:limit]
        return []


# =========================================================
# === Solana PumpFun Provider =============================
# =========================================================
class SolanaPumpFunProvider:
    def __init__(self, rpc_url):
        self.rpc_url = rpc_url
        print(f"SolanaPumpFunProvider connected to {rpc_url}")

    async def monitor_new_tokens(self, limit=10):
        """Fetch new PumpFun tokens (mock for demo)"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("https://api.dexscreener.com/latest/dex/tokens") as resp:
                    data = await resp.json()
                    tokens = data.get("pairs", [])[:limit]
                    return [{
                        "name": t.get("baseToken", {}).get("name", ""),
                        "symbol": t.get("baseToken", {}).get("symbol", ""),
                        "priceUsd": t.get("priceUsd", 0),
                        "volume": t.get("volume", 0)
                    } for t in tokens]
        except Exception as e:
            print(f"[PumpFun] Error monitoring tokens: {e}")
            return []


# =========================================================
# === Auto Provider with Fallback =========================
# =========================================================
class AutoDataProvider(BaseDataProvider):
    """
    Combines Binance → Bybit → YFinance fallback logic.
    You can set this in your TradingBot by just replacing CCXTDataProvider with AutoDataProvider if needed.
    """
    def __init__(self):
        self.binance = CCXTDataProvider("binance")
        self.bybit = CCXTDataProvider("bybit")
        self.yf = YFinanceDataProvider("crypto")

    def get_ohlcv(self, symbol, timeframe="1h", limit=200):
        for provider in [self.binance, self.bybit, self.yf]:
            df = provider.get_ohlcv(symbol, timeframe, limit)
            if df is not None and len(df) > 0:
                return df
        return None

    def get_ticker(self, symbol):
        for provider in [self.binance, self.bybit, self.yf]:
            ticker = provider.get_ticker(symbol)
            if ticker and "last" in ticker:
                return ticker
        return None

    def get_popular_assets(self, limit=20):
        for provider in [self.binance, self.bybit, self.yf]:
            assets = provider.get_popular_assets(limit)
            if assets:
                return assets[:limit]
        return []


# =========================================================
# === Example Local Test ==================================
# =========================================================
if __name__ == "__main__":
    provider = AutoDataProvider()
    coins = provider.get_popular_assets()
    print("Popular assets:", coins)

    for sym in coins[:3]:
        df = provider.get_ohlcv(sym, "1h", 50)
        if df is not None:
            print(f"{sym} OHLCV rows: {len(df)}")
        ticker = provider.get_ticker(sym)
        print(f"{sym} price:", ticker)
