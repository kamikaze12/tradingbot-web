import requests
import time
from abc import ABC, abstractmethod


# =======================
# Abstract Base Class
# =======================
class DataProvider(ABC):
    @abstractmethod
    def get_price(self, symbol: str):
        pass


# =======================
# Binance Provider
# =======================
class BinanceDataProvider(DataProvider):
    def __init__(self):
        self.base_url = "https://api.binance.com/api/v3"

    def get_price(self, symbol: str):
        try:
            url = f"{self.base_url}/ticker/price?symbol={symbol}"
            resp = requests.get(url, timeout=10)
            if resp.status_code == 451:
                raise Exception("Binance restricted location (451).")
            resp.raise_for_status()
            data = resp.json()
            return float(data["price"])
        except Exception as e:
            print(f"Binance error for {symbol}: {e}")
            raise


# =======================
# Bybit Provider
# =======================
class BybitDataProvider(DataProvider):
    def __init__(self):
        self.base_url = "https://api.bybit.com/v5/market"

    def get_price(self, symbol: str):
        try:
            # Bybit pakai format misalnya "BTCUSDT"
            url = f"{self.base_url}/tickers?category=spot&symbol={symbol}"
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            if "result" in data and "list" in data["result"] and len(data["result"]["list"]) > 0:
                return float(data["result"]["list"][0]["lastPrice"])
            else:
                raise Exception(f"No data for {symbol} from Bybit")
        except Exception as e:
            print(f"Bybit error for {symbol}: {e}")
            raise


# =======================
# OKX Provider
# =======================
class OKXDataProvider(DataProvider):
    def __init__(self):
        self.base_url = "https://www.okx.com/api/v5/market"

    def get_price(self, symbol: str):
        try:
            # OKX pakai format "BTC-USDT"
            if "USDT" in symbol:
                okx_symbol = symbol.replace("USDT", "-USDT")
            else:
                okx_symbol = symbol

            url = f"{self.base_url}/ticker?instId={okx_symbol}"
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            if "data" in data and len(data["data"]) > 0:
                return float(data["data"][0]["last"])
            else:
                raise Exception(f"No data for {symbol} from OKX")
        except Exception as e:
            print(f"OKX error for {symbol}: {e}")
            raise


# =======================
# CoinGecko Provider
# =======================
class CoinGeckoDataProvider(DataProvider):
    def __init__(self):
        self.base_url = "https://api.coingecko.com/api/v3"

        # Mapping supaya BTC/USDT → bitcoin
        self.symbol_map = {
            "BTCUSDT": "bitcoin",
            "ETHUSDT": "ethereum",
            "BNBUSDT": "binancecoin",
            "SOLUSDT": "solana",
            "ADAUSDT": "cardano",
            "XRPUSDT": "ripple",
            "DOTUSDT": "polkadot",
            "DOGEUSDT": "dogecoin",
            "AVAXUSDT": "avalanche-2",
            "MATICUSDT": "polygon"
        }

    def get_price(self, symbol: str):
        try:
            coin_id = self.symbol_map.get(symbol)
            if not coin_id:
                raise Exception(f"Symbol {symbol} not mapped for CoinGecko")
            url = f"{self.base_url}/simple/price?ids={coin_id}&vs_currencies=usdt"
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            return float(data[coin_id]["usdt"])
        except Exception as e:
            print(f"CoinGecko error for {symbol}: {e}")
            raise


# =======================
# Fallback Provider
# =======================
class FallbackDataProvider(DataProvider):
    def __init__(self):
        self.providers = [
            BinanceDataProvider(),
            BybitDataProvider(),
            OKXDataProvider(),
            CoinGeckoDataProvider()
        ]

    def get_price(self, symbol: str):
        last_error = None
        for provider in self.providers:
            try:
                return provider.get_price(symbol)
            except Exception as e:
                last_error = e
                continue
        raise Exception(f"All providers failed for {symbol}. Last error: {last_error}")


# =======================
# Example usage
# =======================
if __name__ == "__main__":
    provider = FallbackDataProvider()
    symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT"]
    for s in symbols:
        try:
            price = provider.get_price(s)
            print(f"{s}: {price}")
        except Exception as e:
            print(f"Failed to get {s}: {e}")
        time.sleep(1)  # delay biar nggak kebanned rate limit
