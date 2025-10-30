import ccxt
import pandas as pd
import yfinance as yf
from abc import ABC, abstractmethod
from solana.rpc.api import Client
from solana.rpc.websocket_api import connect
import json
import asyncio
import base58
import os
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime
import time

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
            print("Warning: Alpha Vantage API key not found. Skipping Alpha fallback")
            self.api_key = None
        self.base_url = "https://www.alphavantage.co/query"

    def _convert_symbol(self, symbol):
        """Convert symbol to Alpha Vantage format"""
        if '=X' in symbol:  # Forex format like EURUSD=X
            base = symbol.replace('=X', '')
            return f"{base[:3]}/{base[3:]}"
        elif '.JK' in symbol:  # Indonesian stock
            return symbol.replace('.JK', '.JK')
        elif '/' in symbol:  # Crypto format like BTC/USDT
            base, quote = symbol.split('/')
            return base
        else:
            return symbol

    def get_ohlcv(self, symbol, timeframe='1d', limit=200):
        # Skip Alpha Vantage for now as it's causing issues
        return None

    def get_ticker(self, symbol):
        # Skip Alpha Vantage for now
        return None

    def get_popular_assets(self, limit=100):
        return []

class DexScreenerProvider:
    def __init__(self):
        self.base_url = "https://api.dexscreener.com/latest/dex"
        
    def get_ticker(self, chain, token_address):
        try:
            url = f"{self.base_url}/tokens/{chain}/{token_address}"
            response = requests.get(url)
            data = response.json()
            if 'pairs' in data and data['pairs']:
                pair = data['pairs'][0]
                return {
                    'last': float(pair.get('priceUsd', 0)),
                    'volume': float(pair.get('volume', {}).get('h24', 0)),
                    'liquidity': float(pair.get('liquidity', {}).get('usd', 0)),
                    'fdv': float(pair.get('fdv', 0))
                }
            return None
        except Exception as e:
            print(f"Error getting ticker from DexScreener for {token_address}: {e}")
            return None
            
    def search_pairs(self, query):
        try:
            url = f"{self.base_url}/search?q={query}"
            response = requests.get(url)
            data = response.json()
            return data.get('pairs', [])
        except Exception as e:
            print(f"Error searching pairs in DexScreener: {e}")
            return []

class CCXTDataProvider(DataProvider):
    def __init__(self, exchange_id='binance', api_key='', secret=''):
        try:
            exchange_class = getattr(ccxt, exchange_id)
            self.exchange = exchange_class({
                'apiKey': api_key,
                'secret': secret,
                'enableRateLimit': True,
            })
            self.exchange.load_markets()
        except Exception as e:
            print(f"Error initializing {exchange_id}: {e}")
            self.exchange = None
            
        self.fallback_yf = YFinanceDataProvider()

    def get_ohlcv(self, symbol, timeframe, limit=200):
        # Try CCXT first
        if self.exchange:
            try:
                ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
                df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                return df
            except Exception as e:
                print(f"CCXT error for {symbol}: {e}")

        # Fallback to yfinance for forex and stocks
        if '=X' in symbol or '.JK' in symbol:
            return self.fallback_yf.get_ohlcv(symbol, timeframe, limit)
                
        return None

    def get_ticker(self, symbol):
        if self.exchange:
            try:
                return self.exchange.fetch_ticker(symbol)
            except Exception as e:
                print(f"CCXT ticker error for {symbol}: {e}")

        # Fallback to yfinance for non-crypto
        if '=X' in symbol or '.JK' in symbol:
            return self.fallback_yf.get_ticker(symbol)
                
        return None

    def get_popular_assets(self, limit=100):
        """Get popular crypto assets - NO FALLBACK to ensure crypto only"""
        try:
            if not self.exchange:
                return self._get_hardcoded_crypto_pairs(limit)
                
            markets = self.exchange.load_markets()
            usdt_markets = [symbol for symbol in markets if symbol.endswith('/USDT')]
            
            # Filter out stablecoins and low volume pairs
            excluded_coins = ['BUSD', 'USDC', 'DAI', 'TUSD', 'USDP', 'UST', 'FDUSD']
            filtered_markets = [
                symbol for symbol in usdt_markets 
                if not any(excluded in symbol for excluded in excluded_coins)
            ]
            
            # Get tickers for volume sorting
            try:
                # Limit to top 100 by default to avoid rate limits
                sample_markets = filtered_markets[:100]
                tickers = self.exchange.fetch_tickers(sample_markets)
                
                # Sort by volume
                filtered_markets.sort(
                    key=lambda x: tickers[x]['quoteVolume'] if x in tickers and tickers[x]['quoteVolume'] else 0, 
                    reverse=True
                )
            except Exception as e:
                print(f"Volume sorting failed, using default order: {e}")
                # Use hardcoded popular pairs if sorting fails
                return self._get_hardcoded_crypto_pairs(limit)
                
            return filtered_markets[:limit]
            
        except Exception as e:
            print(f"Error getting popular assets from CCXT: {e}")
            return self._get_hardcoded_crypto_pairs(limit)

    def _get_hardcoded_crypto_pairs(self, limit):
        """Fallback popular crypto pairs - EXTENDED LIST"""
        popular_pairs = [
            'BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'SOL/USDT', 'XRP/USDT',
            'ADA/USDT', 'AVAX/USDT', 'DOT/USDT', 'DOGE/USDT', 'MATIC/USDT',
            'LTC/USDT', 'LINK/USDT', 'ATOM/USDT', 'UNI/USDT', 'XLM/USDT',
            'ETC/USDT', 'XMR/USDT', 'EOS/USDT', 'AAVE/USDT', 'ALGO/USDT',
            'NEAR/USDT', 'FIL/USDT', 'SAND/USDT', 'AXS/USDT', 'THETA/USDT',
            'EGLD/USDT', 'FTM/USDT', 'XTZ/USDT', 'HBAR/USDT', 'MANA/USDT',
            'APE/USDT', 'GALA/USDT', 'CHZ/USDT', 'ENJ/USDT', 'FLOW/USDT',
            'ICP/USDT', 'VET/USDT', 'TRX/USDT', 'EOS/USDT', 'XEM/USDT'
        ]
        return popular_pairs[:limit]

class YFinanceDataProvider(DataProvider):
    def __init__(self, market_type='auto'):
        self.market_type = market_type
        
    def _detect_symbol_type(self, symbol):
        """Auto-detect symbol type for proper handling"""
        if '=X' in symbol:
            return 'forex'
        elif '.JK' in symbol:
            return 'saham_id'
        elif '/' in symbol:
            return 'crypto'
        else:
            return 'stock'

    def get_ohlcv(self, symbol, timeframe='1d', limit=200):
        try:
            # Map timeframe to yfinance format
            interval_map = {
                '1m': '1m', '2m': '2m', '5m': '5m', '15m': '15m', '30m': '30m',
                '1h': '1h', '1d': '1d', '5d': '5d', '1wk': '1wk', '1mo': '1mo'
            }
            interval = interval_map.get(timeframe, '1d')
            
            # Determine period based on timeframe and limit
            if interval in ['1m', '2m', '5m', '15m', '30m']:
                period = '7d' if limit <= 1000 else '60d'
            elif interval == '1h':
                period = '60d'
            else:
                period = '1y' if limit <= 252 else '2y'

            ticker = yf.Ticker(symbol)
            df = ticker.history(period=period, interval=interval)
            
            if df.empty:
                print(f"No data returned from yfinance for {symbol}")
                return None
                
            # Reset index and rename columns
            df.reset_index(inplace=True)
            if 'Date' in df.columns:
                df.rename(columns={'Date': 'timestamp'}, inplace=True)
            elif 'Datetime' in df.columns:
                df.rename(columns={'Datetime': 'timestamp'}, inplace=True)
                
            # Ensure all required columns exist
            required_cols = ['open', 'high', 'low', 'close', 'volume']
            for col in required_cols:
                if col not in df.columns:
                    df[col] = 0
                    
            df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
            
            # Handle timezone-naive timestamps
            if hasattr(df['timestamp'].iloc[0], 'tz') and df['timestamp'].iloc[0].tz is not None:
                df['timestamp'] = df['timestamp'].dt.tz_localize(None)
                
            return df.tail(limit)
            
        except Exception as e:
            print(f"Error getting OHLCV from yfinance for {symbol}: {e}")
            return None

    def get_ticker(self, symbol):
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            
            # Try to get current price
            hist = ticker.history(period='1d', interval='1m')
            if not hist.empty:
                last_price = hist['Close'].iloc[-1]
                volume = hist['Volume'].iloc[-1] if 'Volume' in hist.columns else info.get('volume', 0)
            else:
                last_price = info.get('currentPrice', info.get('regularMarketPrice', 0))
                volume = info.get('volume', 0)
                
            return {
                'last': last_price,
                'volume': volume,
                'high': info.get('dayHigh', 0),
                'low': info.get('dayLow', 0)
            }
            
        except Exception as e:
            print(f"Error getting ticker from yfinance for {symbol}: {e}")
            return None

    def get_popular_assets(self, limit=50):
        symbol_type = self.market_type if self.market_type != 'auto' else 'stock'
        
        if symbol_type == 'saham_id':
            return self._get_indonesian_stocks(limit)
        elif symbol_type == 'forex':
            return self._get_forex_pairs(limit)
        else:
            return self._get_international_stocks(limit)

    def _get_indonesian_stocks(self, limit):
        """Get popular Indonesian stocks - EXTENDED LIST"""
        # Extended list of popular Indonesian stocks (LQ45 and more)
        popular_id_stocks = [
            'BBCA.JK', 'TLKM.JK', 'ASII.JK', 'BMRI.JK', 'BBNI.JK',
            'BBRI.JK', 'UNVR.JK', 'INDF.JK', 'ICBP.JK', 'ADRO.JK',
            'ANTM.JK', 'AKRA.JK', 'ASSA.JK', 'BUKA.JK', 'CPIN.JK',
            'EMTK.JK', 'ERAA.JK', 'EXCL.JK', 'GGRM.JK', 'HMSP.JK',
            'ICBP.JK', 'INCO.JK', 'INDF.JK', 'JPFA.JK', 'KLBF.JK',
            'MDKA.JK', 'MIKA.JK', 'MNCN.JK', 'PGAS.JK', 'PTBA.JK',
            'PTPP.JK', 'SMGR.JK', 'TBIG.JK', 'TINS.JK', 'TKIM.JK',
            'TLKM.JK', 'TOWR.JK', 'TPIA.JK', 'UNTR.JK', 'UNVR.JK',
            'WIKA.JK', 'WSKT.JK', 'WTON.JK', 'ACES.JK', 'ADMR.JK',
            'AMRT.JK', 'ARTO.JK', 'ASRI.JK', 'BACA.JK', 'BESS.JK',
            'BRIS.JK', 'BRMS.JK', 'BSDE.JK', 'BTPS.JK', 'CLEO.JK',
            'CMNP.JK', 'CPRO.JK', 'CTRA.JK', 'DMAS.JK', 'DNET.JK',
            'DOID.JK', 'ELSA.JK', 'ESSA.JK', 'ESTI.JK', 'EXCL.JK',
            'FIRE.JK', 'GJTL.JK', 'GOTO.JK', 'HRUM.JK', 'ICON.JK',
            'INCO.JK', 'INTP.JK', 'ITMG.JK', 'JPFA.JK', 'KAEF.JK',
            'KINO.JK', 'KLBF.JK', 'LINK.JK', 'LPPF.JK', 'MAPI.JK',
            'MDKA.JK', 'MEDC.JK', 'MIKA.JK', 'MLPT.JK', 'MNCN.JK',
            'MPMX.JK', 'MTEL.JK', 'MYOR.JK', 'PBSA.JK', 'PGAS.JK',
            'PTBA.JK', 'PTPP.JK', 'PWON.JK', 'SIDO.JK', 'SILO.JK',
            'SMGR.JK', 'SRIL.JK', 'SRTG.JK', 'TINS.JK', 'TKIM.JK',
            'TLKM.JK', 'TOWR.JK', 'TPIA.JK', 'UNTR.JK', 'UNVR.JK',
            'WIKA.JK', 'WSKT.JK', 'WTON.JK'
        ]
        return popular_id_stocks[:limit]

    def _get_forex_pairs(self, limit):
        """Get popular forex pairs - EXTENDED LIST"""
        # Extended list of popular forex pairs
        popular_forex = [
            'EURUSD=X', 'GBPUSD=X', 'USDJPY=X', 'USDCHF=X', 'AUDUSD=X',
            'USDCAD=X', 'NZDUSD=X', 'EURGBP=X', 'EURJPY=X', 'GBPJPY=X',
            'EURCHF=X', 'AUDJPY=X', 'CADJPY=X', 'CHFJPY=X', 'EURCAD=X',
            'EURAUD=X', 'GBPCHF=X', 'AUDCAD=X', 'AUDCHF=X', 'AUDNZD=X',
            'NZDJPY=X', 'GBPAUD=X', 'GBPCAD=X', 'EURSEK=X', 'EURNOK=X',
            'USDSEK=X', 'USDNOK=X', 'USDSGD=X', 'USDHKD=X', 'USDCNY=X',
            'USDMXN=X', 'USDZAR=X', 'USDTRY=X', 'USDINR=X', 'USDBRL=X',
            'USDRUB=X', 'USDKRW=X', 'USDTWD=X', 'USDTHB=X', 'USDPHP=X'
        ]
        return popular_forex[:limit]

    def _get_international_stocks(self, limit):
        """Get popular international stocks"""
        popular_stocks = [
            'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA', 
            'META', 'NVDA', 'JPM', 'JNJ', 'V',
            'PG', 'UNH', 'HD', 'DIS', 'PYPL',
            'NFLX', 'ADBE', 'CRM', 'INTC', 'CSCO',
            'PFE', 'WMT', 'VZ', 'KO', 'PEP',
            'T', 'ABT', 'TMO', 'COST', 'AVGO',
            'LLY', 'XOM', 'CVX', 'MRK', 'ABBV',
            'BAC', 'WFC', 'C', 'GS', 'MS',
            'SPY', 'QQQ', 'IWM', 'DIA', 'VIXY'
        ]
        return popular_stocks[:limit]

class SolanaPumpFunProvider:
    def __init__(self, rpc_url=None):
        self.rpc_url = rpc_url or "https://api.mainnet-beta.solana.com"
        self.client = Client(self.rpc_url)
        self.dex_provider = DexScreenerProvider()

    async def monitor_new_tokens(self, limit=10):
        """Monitor new tokens on Pump.fun"""
        print("Pump.fun monitoring requires WebSocket connection setup...")
        return []
