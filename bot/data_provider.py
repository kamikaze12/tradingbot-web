import ccxt
import pandas as pd
import yfinance as yf
from abc import ABC, abstractmethod
import json
import os
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime, timedelta
import time
import logging
from typing import Dict, List, Optional, Tuple
import numpy as np
from dataclasses import dataclass
from functools import lru_cache
import hashlib

# Enhanced logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class DataQualityMetrics:
    """Data quality assessment metrics"""
    completeness: float
    freshness: float
    consistency: float
    validity: float
    overall_score: float

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
    
    def get_health_metrics(self) -> Dict:
        return {}

class CircuitBreaker:
    """Circuit breaker pattern for API rate limiting"""
    
    def __init__(self, failure_threshold=5, recovery_timeout=60):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
        
    def can_execute(self):
        if self.state == "OPEN":
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = "HALF_OPEN"
                return True
            return False
        return True
    
    def record_success(self):
        self.state = "CLOSED"
        self.failure_count = 0
        
    def record_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"
            logger.warning(f"Circuit breaker OPENED after {self.failure_count} failures")

class DataCache:
    """Enhanced caching with TTL and memory management"""
    
    def __init__(self, ttl_seconds=300, max_size=1000):
        self.ttl = ttl_seconds
        self.max_size = max_size
        self._cache = {}
        self._access_times = {}
        
    def _generate_key(self, symbol, timeframe, limit):
        """Generate unique cache key"""
        key_str = f"{symbol}_{timeframe}_{limit}"
        return hashlib.md5(key_str.encode()).hexdigest()
    
    def _clean_old_entries(self):
        """Remove expired entries"""
        current_time = time.time()
        expired_keys = [
            key for key, timestamp in self._access_times.items()
            if current_time - timestamp > self.ttl
        ]
        
        for key in expired_keys:
            self._cache.pop(key, None)
            self._access_times.pop(key, None)
            
        # If still over size limit, remove oldest
        if len(self._cache) > self.max_size:
            oldest_keys = sorted(self._access_times.items(), key=lambda x: x[1])[:100]
            for key, _ in oldest_keys:
                self._cache.pop(key, None)
                self._access_times.pop(key, None)
    
    def _is_valid_cached_data(self, data):
        """Validasi data cached"""
        if data is None:
            return False
        if isinstance(data, pd.DataFrame):
            if data.empty:
                return False
            if 'close' in data.columns and (data['close'] <= 0).all():
                return False
            if len(data) < 1:
                return False
        return True

    def get(self, symbol, timeframe, limit):
        """Get cached data"""
        self._clean_old_entries()
        key = self._generate_key(symbol, timeframe, limit)
        
        if key in self._cache:
            cached_data = self._cache[key]
            if self._is_valid_cached_data(cached_data):
                self._access_times[key] = time.time()
                logger.debug(f"Cache HIT for {symbol}")
                return cached_data
            else:
                logger.debug(f"Cache INVALID for {symbol}, removing")
                del self._cache[key]
                del self._access_times[key]
        return None
    
    def set(self, symbol, timeframe, limit, data):
        """Cache data"""
        self._clean_old_entries()
        
        if not self._is_valid_cached_data(data):
            logger.debug(f"Not caching invalid data for {symbol}")
            return
            
        key = self._generate_key(symbol, timeframe, limit)
        
        self._cache[key] = data
        self._access_times[key] = time.time()
        logger.debug(f"Data cached for {symbol}")

class RetryMechanism:
    """Enhanced retry mechanism with exponential backoff"""
    
    def __init__(self, max_retries=3, base_delay=1, max_delay=30):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        
    def execute_with_retry(self, func, *args, **kwargs):
        """Execute function with retry logic"""
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                result = func(*args, **kwargs)
                
                if self._validate_result(result):
                    return result
                else:
                    raise ValueError("Invalid data received")
                    
            except (requests.RequestException, ccxt.BaseError, ValueError, Exception) as e:
                last_exception = e
                logger.warning(f"Attempt {attempt + 1} failed: {str(e)}")
                
                if attempt < self.max_retries:
                    delay = min(self.base_delay * (2 ** attempt) + np.random.uniform(0, 1), self.max_delay)
                    logger.info(f"Retrying in {delay:.2f} seconds...")
                    time.sleep(delay)
                else:
                    logger.error(f"All {self.max_retries} attempts failed")
        
        raise last_exception or Exception("All retry attempts failed")
    
    def _validate_result(self, result):
        """Better validation of data result"""
        if result is None:
            return False
            
        if isinstance(result, pd.DataFrame):
            if result.empty:
                return False
            if 'close' in result.columns:
                valid_prices = result['close'].notna() & (result['close'] > 0)
                if valid_prices.sum() < 1:
                    return False
            return True
            
        elif isinstance(result, dict):
            if 'last' in result and result['last'] > 0:
                return True
            return False
            
        return True

class EnhancedDataProvider(DataProvider, ABC):
    """Enhanced base data provider with common improvements"""
    
    def __init__(self):
        super().__init__()
        self.circuit_breaker = CircuitBreaker()
        self.retry_mechanism = RetryMechanism()
        self.data_cache = DataCache(ttl_seconds=300)
        self.request_count = 0
        self.error_count = 0
        self.last_request_time = None
        
    def _safe_api_call(self, func, *args, **kwargs):
        """Execute API call with circuit breaker and retry logic"""
        if not self.circuit_breaker.can_execute():
            logger.warning("Circuit breaker is OPEN, blocking API call")
            return None
        
        try:
            self.request_count += 1
            self.last_request_time = time.time()
            
            result = self.retry_mechanism.execute_with_retry(func, *args, **kwargs)
            
            self.circuit_breaker.record_success()
            return result
            
        except Exception as e:
            self.error_count += 1
            self.circuit_breaker.record_failure()
            logger.error(f"API call failed after retries: {str(e)}")
            return None
    
    def _get_cached_data(self, symbol, timeframe, limit):
        """Get data from cache if available"""
        return self.data_cache.get(symbol, timeframe, limit)
    
    def _set_cached_data(self, symbol, timeframe, limit, data):
        """Store data in cache"""
        self.data_cache.set(symbol, timeframe, limit, data)
    
    def get_health_metrics(self) -> Dict:
        """Get provider health metrics"""
        return {
            'request_count': self.request_count,
            'error_count': self.error_count,
            'error_rate': self.error_count / max(1, self.request_count),
            'circuit_breaker_state': self.circuit_breaker.state,
            'cache_size': len(self.data_cache._cache)
        }
    
    def get_popular_assets(self, limit=100):
        """Default implementation"""
        logger.warning(f"get_popular_assets not properly implemented for {self.__class__.__name__}")
        
        fallback_assets = [
            'BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'XRP/USDT', 'ADA/USDT',
            'EUR/USD', 'USD/JPY', 'GBP/USD', 'AUD/USD', 'USD/CAD',
            'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA'
        ]
        return fallback_assets[:limit]

    def _estimate_realistic_price(self, symbol):
        """Estimate realistic price based on symbol"""
        price_estimates = {
            'BTC/USDT': 50000.0,
            'ETH/USDT': 3000.0,
            'BNB/USDT': 500.0,
            'XRP/USDT': 0.5,
            'ADA/USDT': 0.4,
            'EUR/USD': 1.08,
            'USD/JPY': 150.0,
            'GBP/USD': 1.26,
            'AAPL': 180.0,
            'MSFT': 400.0,
            'GOOGL': 150.0,
            'AMZN': 170.0,
            'TSLA': 200.0,
            'META': 500.0,
            'NVDA': 900.0,
            'BTC-USD': 50000.0,
            'ETH-USD': 3000.0,
            'EURUSD=X': 1.08,
            'USDJPY=X': 150.0,
        }
        
        for pattern, price in price_estimates.items():
            if pattern in symbol:
                return price
        
        if 'USDT' in symbol or '/USDT' in symbol:
            return 10.0
        elif 'USD' in symbol or '=X' in symbol:
            return 1.0
        else:
            return 100.0

class EnhancedCCXTDataProvider(EnhancedDataProvider):
    """Enhanced CCXT provider dengan fallback support"""
    
    def __init__(self, exchange_id='binance', api_key='', secret='', market_type='spot'):
        super().__init__()
        
        self.exchange_id = exchange_id
        self.market_type = market_type
        exchange_class = getattr(ccxt, exchange_id, None)
        
        if exchange_class is None:
            logger.error(f"Exchange {exchange_id} not found in CCXT")
            self.exchange = None
        else:
            try:
                config = {
                    'apiKey': api_key,
                    'secret': secret,
                    'enableRateLimit': True,
                    'timeout': 30000,
                }
                
                if market_type == 'future':
                    config['options'] = {'defaultType': 'future'}
                
                self.exchange = exchange_class(config)
                self.exchange.load_markets()
                logger.info(f"Successfully connected to {exchange_id} ({market_type})")
                
            except Exception as e:
                logger.error(f"Failed to initialize {exchange_id}: {str(e)}")
                self.exchange = None

    def get_ohlcv(self, symbol, timeframe='1h', limit=200):
        """Get OHLCV data"""
        def fetch_ccxt_data():
            if not self.exchange:
                raise Exception("Exchange not initialized")
            
            try:
                ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
                if not ohlcv:
                    raise ValueError(f"No OHLCV data returned for {symbol}")
                
                df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                
                current_price = df['close'].iloc[-1] if len(df) > 0 else 0
                logger.info(f"📊 CCXT DATA: {symbol} - {len(df)} bars, current price: {current_price:.8f}")
                
                return df
                
            except Exception as e:
                logger.warning(f"CCXT failed for {symbol}: {str(e)}")
                raise

        return self._safe_api_call(fetch_ccxt_data)
        
    def get_ticker(self, symbol):
        """Get ticker data"""
        def fetch_ticker():
            try:
                if not self.exchange:
                    raise Exception("Exchange not initialized")
                    
                ticker = self.exchange.fetch_ticker(symbol)
                last_price = ticker.get('last')
                
                if last_price is None or last_price <= 0:
                    raise ValueError(f"Invalid price for {symbol}: {last_price}")
                
                return {
                    'last': last_price,
                    'volume': ticker.get('baseVolume', 0),
                    'high': ticker.get('high'),
                    'low': ticker.get('low'),
                    'bid': ticker.get('bid'),
                    'ask': ticker.get('ask'),
                    'symbol': symbol
                }
            except Exception as e:
                logger.error(f"CCXT ticker error: {str(e)}")
                raise
        
        return self._safe_api_call(fetch_ticker)

    def get_popular_assets(self, limit=100):
        """Get popular crypto assets dengan prioritas volume & trend"""
        try:
            logger.info(f"🔄 Getting {limit} popular assets from {self.exchange_id}...")
            
            if not self.exchange:
                logger.warning(f"Exchange {self.exchange_id} not initialized")
                return self._get_fallback_major_coins(limit)
            
            try:
                self.exchange.load_markets()
                markets = self.exchange.markets
                logger.info(f"📊 Loaded {len(markets)} markets from {self.exchange_id}")
            except Exception as e:
                logger.error(f"Failed to load markets: {e}")
                return self._get_fallback_major_coins(limit)
            
            if self.market_type == 'future':
                target_markets = [
                    symbol for symbol, market in markets.items()
                    if (market.get('future', False) or 
                        ':USDT' in symbol or 
                        'PERP' in symbol or
                        '/USDT:' in symbol)
                ]
            else:
                target_markets = [
                    symbol for symbol, market in markets.items()
                    if symbol.endswith('/USDT') and market.get('spot', True)
                ]
            
            logger.info(f"📊 Found {len(target_markets)} target markets for {self.market_type}")
            
            excluded_coins = ['BUSD', 'USDC', 'DAI', 'TUSD', 'USDP', 'UST', 'FDUSD']
            filtered_markets = [
                symbol for symbol in target_markets 
                if not any(excluded in symbol for excluded in excluded_coins)
            ]
            
            # **PERBAIKAN: Ambil data volume untuk sorting**
            assets_with_volume = []
            
            # Ambil sample dari filtered_markets untuk cek volume (max 50 untuk performance)
            sample_size = min(50, len(filtered_markets))
            markets_to_check = filtered_markets[:sample_size]
            
            for symbol in markets_to_check:
                try:
                    ticker = self.exchange.fetch_ticker(symbol)
                    volume = ticker.get('quoteVolume', 0) or ticker.get('baseVolume', 0)
                    assets_with_volume.append((symbol, volume))
                except:
                    assets_with_volume.append((symbol, 0))
                    continue
            
            # Sort berdasarkan volume (descending)
            assets_with_volume.sort(key=lambda x: x[1], reverse=True)
            
            # **PERBAIKAN: Prioritaskan coin utama (hardcoded)**
            major_coins = [
                'BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'XRP/USDT', 'ADA/USDT',
                'SOL/USDT', 'DOT/USDT', 'DOGE/USDT', 'AVAX/USDT', 'MATIC/USDT',
                'LTC/USDT', 'LINK/USDT', 'ATOM/USDT', 'XLM/USDT', 'BCH/USDT'
            ]
            
            # Gabungkan: major coins dulu, lalu berdasarkan volume
            result = []
            
            # Tambahkan major coins yang ada di market
            for coin in major_coins:
                if coin in filtered_markets and coin not in result:
                    result.append(coin)
            
            # Tambahkan sisanya berdasarkan volume
            for symbol, _ in assets_with_volume:
                if symbol not in result and len(result) < limit:
                    result.append(symbol)
            
            # Jika masih kurang, tambahkan dari filtered_markets
            if len(result) < limit:
                for symbol in filtered_markets:
                    if symbol not in result and len(result) < limit:
                        result.append(symbol)
            
            logger.info(f"✅ CCXT returning {len(result)} popular {self.market_type} assets (prioritized by volume)")
            logger.info(f"   Top 5: {result[:5]}")
            return result[:limit]
            
        except Exception as e:
            logger.error(f"Error getting popular assets from {self.exchange_id}: {str(e)}")
            return self._get_fallback_major_coins(limit)

    def _get_fallback_major_coins(self, limit):
        """Fallback major coins"""
        major_pairs = [
            'BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'XRP/USDT', 'ADA/USDT',
            'SOL/USDT', 'DOT/USDT', 'DOGE/USDT', 'AVAX/USDT', 'MATIC/USDT',
            'LTC/USDT', 'LINK/USDT', 'ATOM/USDT', 'XLM/USDT', 'BCH/USDT'
        ]
        return major_pairs[:limit]

class EnhancedCCXTFuturesProvider(EnhancedCCXTDataProvider):
    """Enhanced CCXT Futures provider"""
    
    def __init__(self, exchange_id='binance', api_key='', secret=''):
        super().__init__(exchange_id=exchange_id, api_key=api_key, secret=secret, market_type='future')
        
    def get_popular_assets(self, limit=100):
        """Get popular futures assets dengan prioritas major coins - ENHANCED"""
        try:
            logger.info(f"🔄 Getting {limit} popular futures from {self.exchange_id}...")
            
            if not self.exchange:
                logger.warning(f"Exchange {self.exchange_id} not initialized")
                return self._get_fallback_futures_coins(limit)
            
            try:
                self.exchange.load_markets()
                markets = self.exchange.markets
                logger.info(f"📊 Loaded {len(markets)} markets from {self.exchange_id}")
            except Exception as e:
                logger.error(f"Failed to load markets: {e}")
                return self._get_fallback_futures_coins(limit)
            
            # Cari futures contracts dengan berbagai format
            futures_markets = []
            for symbol, market in markets.items():
                # Check berbagai format futures
                if (market.get('future', False) or 
                    '/USDT:' in symbol or 
                    ':USDT' in symbol or
                    'PERP' in symbol or
                    '-USDT' in symbol or
                    '/USDT-PERP' in symbol or
                    '/USD:' in symbol or
                    'FUTURES' in symbol.upper()):
                    futures_markets.append(symbol)
            
            logger.info(f"📊 Found {len(futures_markets)} futures markets")
            
            # Filter stablecoins
            excluded_coins = ['BUSD', 'USDC', 'DAI', 'TUSD', 'USDP', 'UST', 'FDUSD']
            filtered_markets = [
                symbol for symbol in futures_markets 
                if not any(excluded in symbol.upper() for excluded in excluded_coins)
            ]
            
            # **PERBAIKAN: Prioritize major futures coins dengan berbagai format**
            major_futures_patterns = [
                'BTC/USDT', 'ETH/USDT', 'BNB/USDT', 
                'XRP/USDT', 'ADA/USDT', 'SOL/USDT',
                'DOT/USDT', 'DOGE/USDT', 'AVAX/USDT', 'MATIC/USDT',
                'LTC/USDT', 'LINK/USDT', 'ATOM/USDT', 'XLM/USDT',
                'BCH/USDT', 'ETC/USDT', 'FIL/USDT', 'THETA/USDT',
                'EOS/USDT', 'XTZ/USDT', 'ALGO/USDT', 'XMR/USDT',
                'ZEC/USDT', 'DASH/USDT', 'WAVES/USDT', 'COMP/USDT',
                'AAVE/USDT', 'SNX/USDT', 'UNI/USDT', 'CRV/USDT'
            ]
            
            # **PERBAIKAN: Gabungkan dengan logika yang lebih baik**
            result = []
            
            # 1. Tambahkan major futures yang tersedia (format apapun)
            for futures_coin in major_futures_patterns:
                # Cari semua format yang mungkin
                for symbol in filtered_markets:
                    base_coin = futures_coin.split('/')[0]
                    if base_coin in symbol and symbol not in result:
                        # Pastikan ini futures (ada tanda futures)
                        if any(marker in symbol for marker in [':', 'PERP', '-USDT', 'FUTURES']):
                            result.append(symbol)
                            break
            
            # 2. Jika masih kurang, tambahkan futures lain berdasarkan volume
            if len(result) < limit:
                remaining_markets = [s for s in filtered_markets if s not in result]
                
                # Coba ambil volume untuk sorting
                assets_with_volume = []
                sample_size = min(30, len(remaining_markets))
                
                for symbol in remaining_markets[:sample_size]:
                    try:
                        ticker = self.exchange.fetch_ticker(symbol)
                        volume = ticker.get('quoteVolume', 0) or ticker.get('baseVolume', 0)
                        assets_with_volume.append((symbol, volume))
                    except:
                        assets_with_volume.append((symbol, 0))
                        continue
                
                # Sort by volume
                assets_with_volume.sort(key=lambda x: x[1], reverse=True)
                
                for symbol, _ in assets_with_volume:
                    if symbol not in result and len(result) < limit:
                        result.append(symbol)
            
            # 3. Jika masih kurang, tambahkan secara acak
            if len(result) < limit:
                for symbol in filtered_markets:
                    if symbol not in result and len(result) < limit:
                        result.append(symbol)
            
            logger.info(f"✅ CCXT Futures returning {len(result)} popular FUTURES assets")
            logger.info(f"   Top 5: {result[:5]}")
            return result[:limit]
            
        except Exception as e:
            logger.error(f"Error getting popular futures from {self.exchange_id}: {str(e)}")
            return self._get_fallback_futures_coins(limit)

    def _get_fallback_futures_coins(self, limit):
        """Fallback futures coins - ENHANCED"""
        major_pairs = [
            'BTC/USDT:USDT', 'ETH/USDT:USDT', 'BNB/USDT:USDT',
            'XRP/USDT:USDT', 'ADA/USDT:USDT', 'SOL/USDT:USDT',
            'DOT/USDT:USDT', 'DOGE/USDT:USDT', 'AVAX/USDT:USDT', 'MATIC/USDT:USDT',
            'LTC/USDT:USDT', 'LINK/USDT:USDT', 'ATOM/USDT:USDT', 'XLM/USDT:USDT',
            'BCH/USDT:USDT', 'ETC/USDT:USDT', 'FIL/USDT:USDT', 'THETA/USDT:USDT',
            'EOS/USDT:USDT', 'XTZ/USDT:USDT', 'ALGO/USDT:USDT', 'XMR/USDT:USDT'
        ]
        return major_pairs[:limit]

class EnhancedYFinanceDataProvider(EnhancedDataProvider):
    """Enhanced Yahoo Finance provider"""
    
    def __init__(self, market_type='stock'):
        super().__init__()
        self.market_type = market_type

    def get_ohlcv(self, symbol, timeframe='1h', limit=200):
        """Get OHLCV from Yahoo Finance"""
        def fetch_yfinance_data():
            try:
                interval_map = {'1h': '1h', '4h': '4h', '1d': '1d', '1w': '1wk'}
                interval = interval_map.get(timeframe, '1d')
                
                if interval == '1h':
                    period = '2mo' if limit > 30 else '5d'
                elif interval == '1d':
                    period = '1y' if limit > 100 else '6mo'
                else:
                    period = '1y'
                
                ticker = yf.Ticker(symbol)
                df = ticker.history(period=period, interval=interval)
                
                if df.empty:
                    raise ValueError("No data returned from Yahoo Finance")
                
                if len(df) > limit:
                    df = df.tail(limit)
                
                df.reset_index(inplace=True)
                df.columns = [col.lower() for col in df.columns]
                if 'date' in df.columns:
                    df.rename(columns={'date': 'timestamp'}, inplace=True)
                elif 'datetime' in df.columns:
                    df.rename(columns={'datetime': 'timestamp'}, inplace=True)
                
                df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
                
                return df
                
            except Exception as e:
                logger.error(f"YFinance error for {symbol}: {str(e)}")
                raise

        return self._safe_api_call(fetch_yfinance_data)

    def get_ticker(self, symbol):
        """Get ticker data from Yahoo Finance"""
        def fetch_ticker():
            try:
                ticker = yf.Ticker(symbol)
                info = ticker.info
                history = ticker.history(period='1d')
                
                if not history.empty:
                    last_price = history['Close'].iloc[-1]
                    volume = history['Volume'].iloc[-1] if 'Volume' in history.columns else 0
                else:
                    last_price = info.get('currentPrice', info.get('regularMarketPrice', 0))
                    volume = info.get('volume', 0)
                
                if last_price <= 0:
                    raise ValueError(f"Invalid price from YFinance: {last_price}")
                
                return {
                    'last': last_price,
                    'volume': volume,
                    'high': info.get('dayHigh', 0),
                    'low': info.get('dayLow', 0),
                    'market_cap': info.get('marketCap', 0)
                }
            except Exception as e:
                logger.error(f"YFinance ticker error: {str(e)}")
                raise
        
        return self._safe_api_call(fetch_ticker)

    def get_popular_assets(self, limit=100):
        """Get popular assets berdasarkan market type - FIXED VERSION"""
        try:
            if self.market_type == "crypto":
                return self._get_popular_crypto(limit)
            elif self.market_type == "forex":
                return self._get_popular_forex(limit)
            elif self.market_type == "saham_id":
                return self._get_popular_indonesian_stocks(limit)
            elif self.market_type in ["us_stocks", "stocks"]:
                return self._get_popular_us_stocks(limit)
            else:
                logger.warning(f"Unknown market type: {self.market_type}")
                return []
                
        except Exception as e:
            logger.error(f"Error getting popular assets for {self.market_type}: {str(e)}")
            return self._get_fallback_assets(limit)

    def _get_popular_crypto(self, limit):
        """Get popular cryptocurrencies - ENHANCED"""
        crypto_pairs = [
            'BTC-USD', 'ETH-USD', 'BNB-USD', 'XRP-USD', 'ADA-USD',
            'SOL-USD', 'DOT-USD', 'DOGE-USD', 'AVAX-USD', 'MATIC-USD',
            'LTC-USD', 'LINK-USD', 'ATOM-USD', 'XLM-USD', 'BCH-USD',
            'ETC-USD', 'FIL-USD', 'THETA-USD', 'EOS-USD', 'XTZ-USD',
            'ALGO-USD', 'XMR-USD', 'ZEC-USD', 'DASH-USD', 'WAVES-USD',
            'COMP-USD', 'AAVE-USD', 'SNX-USD', 'UNI-USD', 'CRV-USD',
            'MKR-USD', 'SUSHI-USD', 'YFI-USD', 'RUNE-USD', 'NEAR-USD',
            'FTM-USD', 'ONE-USD', 'VET-USD', 'TRX-USD', 'SHIB-USD',
            'LEO-USD', 'CRO-USD', 'FTT-USD', 'HT-USD', 'KCS-USD',
            'BTT-USD', 'HNT-USD', 'GRT-USD', 'CHZ-USD', 'ENJ-USD',
            'BAT-USD', 'MANA-USD', 'SAND-USD', 'AXS-USD', 'GALA-USD'
        ]
        result = crypto_pairs[:limit]
        logger.info(f"📈 YFinance returning {len(result)} popular crypto assets")
        
        # Format sebagai list of dict untuk konsistensi
        formatted_result = []
        for symbol in result:
            formatted_result.append({
                'symbol': symbol,
                'name': symbol.replace('-USD', '')
            })
        
        return formatted_result

    def _get_popular_forex(self, limit):
        """Get popular forex pairs - ENHANCED"""
        forex_pairs = [
            'EURUSD=X', 'USDJPY=X', 'GBPUSD=X', 'AUDUSD=X', 'USDCAD=X',
            'USDCHF=X', 'NZDUSD=X', 'EURGBP=X', 'EURJPY=X', 'GBPJPY=X',
            'AUDJPY=X', 'EURCAD=X', 'EURCHF=X', 'EURAUD=X', 'GBPCHF=X',
            'AUDCAD=X', 'AUDNZD=X', 'NZDCAD=X', 'USDHKD=X', 'USDSGD=X',
            'USDINR=X', 'USDCNY=X', 'USDMXN=X', 'USDBRL=X', 'USDRUB=X'
        ]
        result = forex_pairs[:limit]
        logger.info(f"📈 YFinance returning {len(result)} popular forex pairs")
        
        formatted_result = []
        for symbol in result:
            pair = symbol.replace('=X', '')
            formatted_result.append({
                'symbol': symbol,
                'name': pair
            })
        
        return formatted_result

    def _get_popular_indonesian_stocks(self, limit):
        """Get popular Indonesian stocks - ENHANCED VERSION"""
        try:
            # Daftar lengkap saham bluechip dan liquid di IDX
            id_stocks = [
                'BBCA.JK', 'BBRI.JK', 'BMRI.JK', 'BBNI.JK', 'BNGA.JK',
                'TLKM.JK', 'ASII.JK', 'UNVR.JK', 'ICBP.JK', 'INDF.JK',
                'WIKA.JK', 'PGAS.JK', 'ANTM.JK', 'ADRO.JK', 'AKRA.JK',
                'ASSA.JK', 'AALI.JK', 'ADHI.JK', 'AMRT.JK', 'APLN.JK',
                'ARTO.JK', 'ASRI.JK', 'ASRM.JK', 'AUTO.JK', 'BAPA.JK',
                'BATA.JK', 'BEST.JK', 'BJBR.JK', 'BJTM.JK', 'BKSL.JK',
                'BTPN.JK', 'BYAN.JK', 'CPIN.JK', 'CTRA.JK', 'DMAS.JK',
                'ERAA.JK', 'EXCL.JK', 'GGRM.JK', 'HMSP.JK', 'INCO.JK',
                'INDY.JK', 'INKP.JK', 'ITMG.JK', 'JPFA.JK', 'JSMR.JK',
                'KAEF.JK', 'KLBF.JK', 'LPKR.JK', 'LPPF.JK', 'MAPI.JK',
                'MDKA.JK', 'MEDC.JK', 'MIKA.JK', 'MNCN.JK', 'MYOR.JK',
                'PGEO.JK', 'PTBA.JK', 'PTPP.JK', 'PWON.JK', 'SIDO.JK',
                'SMGR.JK', 'SRIL.JK', 'SSMS.JK', 'TINS.JK', 'TKIM.JK',
                'TLKM.JK', 'TOWR.JK', 'TPIA.JK', 'UNTR.JK', 'WEGE.JK',
                'WSKT.JK', 'WTON.JK', 'ACES.JK', 'ADMG.JK', 'AGRO.JK',
                'AKSI.JK', 'ALMI.JK', 'AMFG.JK', 'APIC.JK', 'ARNA.JK',
                'ASBI.JK', 'ASDM.JK', 'ASGR.JK', 'ASJT.JK', 'ASPI.JK',
                'ATIC.JK', 'AUTO.JK', 'BABP.JK', 'BACA.JK', 'BAJA.JK',
                'BALI.JK', 'BATA.JK', 'BAYU.JK', 'BCIC.JK', 'BCIP.JK',
                'BDMN.JK', 'BEEF.JK', 'BEKS.JK', 'BESS.JK', 'BINA.JK',
                'BIPI.JK', 'BISI.JK', 'BJBR.JK', 'BJTM.JK', 'BKDP.JK',
                'BKSL.JK', 'BLTA.JK', 'BLTZ.JK', 'BMAS.JK', 'BMRI.JK',
                'BMSR.JK', 'BMTR.JK', 'BNBA.JK', 'BNBR.JK', 'BNGA.JK',
                'BNII.JK', 'BNLI.JK', 'BOGA.JK', 'BOLT.JK', 'BOSS.JK',
                'BPFI.JK', 'BPII.JK', 'BPTR.JK', 'BRAM.JK', 'BRIS.JK',
                'BRMS.JK', 'BRPT.JK', 'BSDE.JK', 'BSIM.JK', 'BSSR.JK',
                'BSWD.JK', 'BTEL.JK', 'BTON.JK', 'BUDI.JK', 'BUKA.JK',
                'BUKK.JK', 'BUMI.JK', 'BUVA.JK', 'BVIC.JK', 'CAMP.JK',
                'CANI.JK', 'CARE.JK', 'CARS.JK', 'CASA.JK', 'CASH.JK',
                'CASS.JK', 'CBMF.JK', 'CCSI.JK', 'CEKA.JK', 'CENT.JK',
                'CFIN.JK', 'CINT.JK', 'CITA.JK', 'CITY.JK', 'CLAY.JK',
                'CLEO.JK', 'CLPI.JK', 'CMNP.JK', 'CMRY.JK', 'CMSN.JK',
                'CNKO.JK', 'CNTX.JK', 'COCO.JK', 'COWL.JK', 'CPRI.JK',
                'CSAP.JK', 'CSIS.JK', 'CSMI.JK', 'CSRA.JK', 'CTBN.JK',
                'CTTH.JK', 'DART.JK', 'DAYA.JK', 'DCII.JK', 'DEAL.JK',
                'DEFI.JK', 'DEWA.JK', 'DFAM.JK', 'DGIK.JK', 'DIGI.JK',
                'DILD.JK', 'DIVA.JK', 'DKFT.JK', 'DLTA.JK', 'DMND.JK',
                'DMMX.JK', 'DNET.JK', 'DOID.JK', 'DPUM.JK', 'DSFI.JK',
                'DSNG.JK', 'DSSA.JK', 'DUCK.JK', 'DUTI.JK', 'DVLA.JK',
                'DWGL.JK', 'EAST.JK', 'ECII.JK', 'EDGE.JK', 'EKAD.JK',
                'ELSA.JK', 'ELTY.JK', 'EMDE.JK', 'EMTK.JK', 'ENRG.JK',
                'ENVY.JK', 'EPAC.JK', 'EPMT.JK', 'ERAA.JK', 'ERTX.JK',
                'ESSA.JK', 'ESTA.JK', 'ESTI.JK', 'ETWA.JK', 'EXCL.JK',
                'FAST.JK', 'FASW.JK', 'FIRE.JK', 'FISH.JK', 'FITT.JK',
                'FMII.JK', 'FORU.JK', 'FORZ.JK', 'FPNI.JK', 'FREN.JK',
                'FUJI.JK', 'GAMA.JK', 'GDST.JK', 'GDYR.JK', 'GEMA.JK',
                'GEMS.JK', 'GGRM.JK', 'GJTL.JK', 'GLOB.JK', 'GMFI.JK',
                'GOLD.JK', 'GOLL.JK', 'GOOD.JK', 'GPRA.JK', 'GRHA.JK',
                'GSMF.JK', 'GTBO.JK', 'GTSI.JK', 'GWSA.JK', 'GZCO.JK',
                'HADE.JK', 'HDFA.JK', 'HDTX.JK', 'HEAL.JK', 'HELI.JK',
                'HERO.JK', 'HEXA.JK', 'HITS.JK', 'HKMU.JK', 'HMSP.JK',
                'HOKI.JK', 'HOME.JK', 'HOMI.JK', 'HOPE.JK', 'HOTL.JK',
                'HRME.JK', 'HRTA.JK', 'IATA.JK', 'IBFN.JK', 'IBST.JK',
                'ICBP.JK', 'ICON.JK', 'IDPR.JK', 'IFII.JK', 'IFSH.JK',
                'IGAR.JK', 'IIKP.JK', 'IKAI.JK', 'IKAN.JK', 'IKBI.JK',
                'IMAS.JK', 'IMJS.JK', 'INAF.JK', 'INAI.JK', 'INCF.JK',
                'INCI.JK', 'INCO.JK', 'INDF.JK', 'INDO.JK', 'INDR.JK',
                'INDS.JK', 'INDX.JK', 'INDY.JK', 'INKP.JK', 'INPC.JK',
                'INPP.JK', 'INPS.JK', 'INRU.JK', 'INTA.JK', 'INTD.JK',
                'INTP.JK', 'IPCC.JK', 'IPCM.JK', 'IPOL.JK', 'IPTV.JK',
                'IRRA.JK', 'ISAT.JK', 'ISSP.JK', 'ITIC.JK', 'ITMA.JK',
                'ITMG.JK', 'JAST.JK', 'JAWA.JK', 'JAYA.JK', 'JECC.JK',
                'JGLE.JK', 'JIHD.JK', 'JKSW.JK', 'JKTM.JK', 'JMAS.JK',
                'JPFA.JK', 'JRPT.JK', 'JSMR.JK', 'JSPT.JK', 'JTPE.JK',
                'KAEF.JK', 'KARW.JK', 'KAYU.JK', 'KBAG.JK', 'KBLI.JK',
                'KBLM.JK', 'KBLV.JK', 'KBRI.JK', 'KDSI.JK', 'KEEN.JK',
                'KEJU.JK', 'KICI.JK', 'KIAS.JK', 'KINO.JK', 'KIOS.JK',
                'KJEN.JK', 'KKGI.JK', 'KLBF.JK', 'KMDS.JK', 'KMTR.JK',
                'KOBX.JK', 'KOIN.JK', 'KONI.JK', 'KOTA.JK', 'KPAL.JK',
                'KPAS.JK', 'KPIG.JK', 'KRAH.JK', 'KRAS.JK', 'KREN.JK',
                'KUAS.JK', 'LABA.JK', 'LAND.JK', 'LAPD.JK', 'LCGP.JK',
                'LCKM.JK', 'LEAD.JK', 'LIFE.JK', 'LINK.JK', 'LION.JK',
                'LMAS.JK', 'LMPI.JK', 'LMSH.JK', 'LPCK.JK', 'LPGI.JK',
                'LPIN.JK', 'LPKR.JK', 'LPLI.JK', 'LPPF.JK', 'LPPS.JK',
                'LRNA.JK', 'LSIP.JK', 'LTLS.JK', 'LUCK.JK', 'LUCY.JK',
                'MABA.JK', 'MAGP.JK', 'MAIN.JK', 'MAMI.JK', 'MAPA.JK',
                'MAPB.JK', 'MAPI.JK', 'MASA.JK', 'MAYA.JK', 'MBAP.JK',
                'MBSS.JK', 'MBTO.JK', 'MCAS.JK', 'MCOL.JK', 'MCOR.JK',
                'MDIA.JK', 'MDKA.JK', 'MDKI.JK', 'MDLN.JK', 'MDRN.JK',
                'MEDC.JK', 'MEGA.JK', 'MERK.JK', 'META.JK', 'MFMI.JK',
                'MGNA.JK', 'MICE.JK', 'MIDI.JK', 'MIKA.JK', 'MINA.JK',
                'MIRA.JK', 'MITI.JK', 'MKNT.JK', 'MKPI.JK', 'MLBI.JK',
                'MLIA.JK', 'MLPL.JK', 'MLPT.JK', 'MMLP.JK', 'MNCN.JK',
                'MOLI.JK', 'MPMX.JK', 'MPOW.JK', 'MPPA.JK', 'MRAT.JK',
                'MREI.JK', 'MSIN.JK', 'MSKY.JK', 'MTDL.JK', 'MTFN.JK',
                'MTLA.JK', 'MTPS.JK', 'MTRA.JK', 'MTSM.JK', 'MTWI.JK',
                'MYOH.JK', 'MYOR.JK', 'MYRX.JK', 'MYTX.JK', 'NANO.JK',
                'NASA.JK', 'NATO.JK', 'NELY.JK', 'NFCX.JK', 'NICK.JK',
                'NICL.JK', 'NIKL.JK', 'NIPS.JK', 'NIRO.JK', 'NISP.JK',
                'NOBU.JK', 'NRCA.JK', 'NUSA.JK', 'NZIA.JK', 'OASA.JK',
                'OBMD.JK', 'OCAP.JK', 'OILS.JK', 'OKAS.JK', 'OMRE.JK',
                'OPMS.JK', 'PADI.JK', 'PALM.JK', 'PAMG.JK', 'PANI.JK',
                'PANR.JK', 'PANS.JK', 'PBID.JK', 'PBRX.JK', 'PBSA.JK',
                'PCAR.JK', 'PDES.JK', 'PEGE.JK', 'PEHA.JK', 'PGAS.JK',
                'PGEO.JK', 'PGLI.JK', 'PICO.JK', 'PJAA.JK', 'PKPK.JK',
                'PLAS.JK', 'PLIN.JK', 'PMJS.JK', 'PMMP.JK', 'PNBN.JK',
                'PNBS.JK', 'PNGO.JK', 'PNLF.JK', 'PNSE.JK', 'POLA.JK',
                'POLI.JK', 'POLL.JK', 'POLU.JK', 'POLY.JK', 'POWR.JK',
                'PPRE.JK', 'PPRO.JK', 'PRAS.JK', 'PRDA.JK', 'PRIM.JK',
                'PSAB.JK', 'PSDN.JK', 'PSGO.JK', 'PSKT.JK', 'PSSI.JK',
                'PTBA.JK', 'PTDU.JK', 'PTIS.JK', 'PTPP.JK', 'PTPW.JK',
                'PTRO.JK', 'PTSN.JK', 'PTSP.JK', 'PUDP.JK', 'PURA.JK',
                'PURE.JK', 'PURI.JK', 'PWON.JK', 'PYFA.JK', 'PZZA.JK',
                'RAJA.JK', 'RALS.JK', 'RANC.JK', 'RBMS.JK', 'RDTX.JK',
                'REAL.JK', 'RELI.JK', 'RICY.JK', 'RIGS.JK', 'RIMO.JK',
                'RISE.JK', 'RMBA.JK', 'ROCK.JK', 'RODA.JK', 'ROTI.JK',
                'RSGK.JK', 'RUIS.JK', 'RUNS.JK', 'SAFE.JK', 'SAME.JK',
                'SAMF.JK', 'SAPX.JK', 'SATU.JK', 'SBAT.JK', 'SCCO.JK',
                'SCMA.JK', 'SCNP.JK', 'SCPI.JK', 'SDMU.JK', 'SDPC.JK',
                'SDRA.JK', 'SEMA.JK', 'SFAN.JK', 'SGER.JK', 'SGRO.JK',
                'SHID.JK', 'SHIP.JK', 'SIDO.JK', 'SILO.JK', 'SIMA.JK',
                'SIMP.JK', 'SIPD.JK', 'SKBM.JK', 'SKLT.JK', 'SKRN.JK',
                'SKYB.JK', 'SLIS.JK', 'SMAR.JK', 'SMBR.JK', 'SMCB.JK',
                'SMDR.JK', 'SMGR.JK', 'SMKL.JK', 'SMMA.JK', 'SMMT.JK',
                'SMRA.JK', 'SMRU.JK', 'SMSM.JK', 'SNLK.JK', 'SOCI.JK',
                'SOFA.JK', 'SOHO.JK', 'SONA.JK', 'SOSS.JK', 'SOTS.JK',
                'SPMA.JK', 'SPOT.JK', 'SPTO.JK', 'SQMI.JK', 'SRAJ.JK',
                'SRIL.JK', 'SRSN.JK', 'SRTG.JK', 'SSIA.JK', 'SSMS.JK',
                'SSTM.JK', 'STAR.JK', 'STTP.JK', 'SUDI.JK', 'SUGI.JK',
                'SULI.JK', 'SUPR.JK', 'SURY.JK', 'SWAT.JK', 'TALF.JK',
                'TAMA.JK', 'TAMU.JK', 'TAPG.JK', 'TARA.JK', 'TAXI.JK',
                'TBIG.JK', 'TBLA.JK', 'TBMS.JK', 'TCID.JK', 'TCPI.JK',
                'TDPM.JK', 'TEBE.JK', 'TECH.JK', 'TELE.JK', 'TFAS.JK',
                'TFCO.JK', 'TINS.JK', 'TIRA.JK', 'TIRT.JK', 'TKIM.JK',
                'TLKM.JK', 'TMAS.JK', 'TMPO.JK', 'TMPP.JK', 'TNCA.JK',
                'TOBA.JK', 'TOPS.JK', 'TOTL.JK', 'TOWR.JK', 'TOYS.JK',
                'TPEN.JK', 'TPIA.JK', 'TPMA.JK', 'TRAM.JK', 'TRIL.JK',
                'TRIM.JK', 'TRIN.JK', 'TRIO.JK', 'TRIS.JK', 'TRST.JK',
                'TRUK.JK', 'TRUS.JK', 'TSPC.JK', 'TUGU.JK', 'TURI.JK',
                'UANG.JK', 'UCID.JK', 'UFOE.JK', 'ULTJ.JK', 'UNIC.JK',
                'UNIQ.JK', 'UNIT.JK', 'UNSP.JK', 'UNTR.JK', 'UNVR.JK',
                'URBN.JK', 'VICI.JK', 'VINS.JK', 'VIVA.JK', 'VOKS.JK',
                'VRNA.JK', 'WAPO.JK', 'WEGE.JK', 'WEHA.JK', 'WICO.JK',
                'WIFI.JK', 'WIIM.JK', 'WIKA.JK', 'WINS.JK', 'WMPP.JK',
                'WMUU.JK', 'WOOD.JK', 'WOWS.JK', 'WSBP.JK', 'WSKT.JK',
                'WSON.JK', 'WTON.JK', 'YELO.JK', 'YPAS.JK', 'YULE.JK',
                'ZBRA.JK', 'ZONE.JK', 'ZYRX.JK'
            ]
            
            # Ambil sesuai limit
            result = id_stocks[:limit]
            logger.info(f"📈 YFinance returning {len(result)} popular Indonesian stocks")
            
            # Format sebagai list of dict untuk konsistensi
            formatted_result = []
            for symbol in result:
                formatted_result.append({
                    'symbol': symbol,
                    'name': symbol.replace('.JK', '')
                })
            
            return formatted_result
        except Exception as e:
            logger.error(f"Error getting Indonesian stocks: {e}")
            # Fallback minimal
            fallback = [
                {'symbol': 'BBCA.JK', 'name': 'Bank BCA'},
                {'symbol': 'BBRI.JK', 'name': 'Bank BRI'},
                {'symbol': 'BMRI.JK', 'name': 'Bank Mandiri'},
                {'symbol': 'TLKM.JK', 'name': 'Telkom Indonesia'},
                {'symbol': 'ASII.JK', 'name': 'Astra International'}
            ]
            return fallback[:limit]

    def _get_popular_us_stocks(self, limit):
        """Get popular US stocks - ENHANCED"""
        us_stocks = [
            'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA', 'META', 'NVDA', 'NFLX',
            'BRK-B', 'JNJ', 'JPM', 'V', 'PG', 'UNH', 'HD', 'DIS', 'PYPL',
            'BAC', 'MA', 'ADBE', 'CMCSA', 'XOM', 'PFE', 'CSCO', 'PEP',
            'ABT', 'TMO', 'AVGO', 'COST', 'CVX', 'MRK', 'WMT', 'ABBV',
            'ACN', 'CRM', 'MCD', 'NKE', 'LIN', 'AMD', 'PM', 'TXN',
            'HON', 'INTC', 'IBM', 'GS', 'CAT', 'BA', 'MMM', 'GE',
            'F', 'GM', 'T', 'VZ', 'LMT', 'RTX', 'NOC', 'GD',
            'SPY', 'QQQ', 'DIA', 'IWM', 'VTI', 'VOO', 'IVV', 'GLD',
            'SLV', 'TLT', 'HYG', 'LQD', 'EMB', 'BND', 'AGG', 'TIP',
            'DBC', 'USO', 'UNG', 'GLDM', 'IAU', 'SIVR', 'PHYS', 'PSLV',
            'BITO', 'GBTC', 'ETHE', 'MSTR', 'COIN', 'RIOT', 'MARA', 'HUT',
            'CLSK', 'BTBT', 'BITF', 'ARBK', 'CIFR', 'SDIG', 'IREN', 'CIFR',
            'WULF', 'HIVE', 'HUT', 'RIOT', 'MARA', 'CLSK', 'BTBT', 'BITF'
        ]
        result = us_stocks[:limit]
        logger.info(f"📈 YFinance returning {len(result)} popular US stocks")
        
        formatted_result = []
        for symbol in result:
            formatted_result.append({
                'symbol': symbol,
                'name': symbol
            })
        
        return formatted_result

    def _get_fallback_assets(self, limit):
        """Fallback assets ketika primary method gagal"""
        fallback_assets = {
            "crypto": [
                {'symbol': 'BTC-USD', 'name': 'Bitcoin'},
                {'symbol': 'ETH-USD', 'name': 'Ethereum'},
                {'symbol': 'BNB-USD', 'name': 'Binance Coin'},
                {'symbol': 'XRP-USD', 'name': 'Ripple'},
                {'symbol': 'ADA-USD', 'name': 'Cardano'}
            ],
            "forex": [
                {'symbol': 'EURUSD=X', 'name': 'Euro/Dollar'},
                {'symbol': 'USDJPY=X', 'name': 'Dollar/Yen'},
                {'symbol': 'GBPUSD=X', 'name': 'Pound/Dollar'},
                {'symbol': 'AUDUSD=X', 'name': 'Aussie/Dollar'},
                {'symbol': 'USDCAD=X', 'name': 'Dollar/Canadian'}
            ],
            "saham_id": [
                {'symbol': 'BBCA.JK', 'name': 'Bank BCA'},
                {'symbol': 'BBRI.JK', 'name': 'Bank BRI'},
                {'symbol': 'BMRI.JK', 'name': 'Bank Mandiri'},
                {'symbol': 'TLKM.JK', 'name': 'Telkom Indonesia'},
                {'symbol': 'ASII.JK', 'name': 'Astra International'}
            ],
            "us_stocks": [
                {'symbol': 'AAPL', 'name': 'Apple Inc'},
                {'symbol': 'MSFT', 'name': 'Microsoft'},
                {'symbol': 'GOOGL', 'name': 'Google'},
                {'symbol': 'AMZN', 'name': 'Amazon'},
                {'symbol': 'TSLA', 'name': 'Tesla'}
            ]
        }
        
        assets = fallback_assets.get(self.market_type, [])
        logger.info(f"Using fallback assets for {self.market_type}: {len(assets[:limit])} assets")
        return assets[:limit]

class AlphaVantageProvider(EnhancedDataProvider):
    """Alpha Vantage data provider"""
    
    def __init__(self, api_key='demo'):
        super().__init__()
        self.api_key = api_key
        self.base_url = 'https://www.alphavantage.co/query'
        
    def get_ohlcv(self, symbol, timeframe='1h', limit=200):
        """Get OHLCV data dari Alpha Vantage"""
        def fetch_av_data():
            try:
                # Mapping timeframe ke interval Alpha Vantage
                interval_map = {
                    '1m': '1min', '5m': '5min', '15m': '15min',
                    '30m': '30min', '1h': '60min', '1d': 'daily'
                }
                
                interval = interval_map.get(timeframe, '60min')
                
                # API call
                params = {
                    'function': 'TIME_SERIES_INTRADAY' if interval != 'daily' else 'TIME_SERIES_DAILY',
                    'symbol': symbol.replace('/', ''),
                    'interval': interval,
                    'apikey': self.api_key,
                    'outputsize': 'full' if limit > 100 else 'compact'
                }
                
                response = requests.get(self.base_url, params=params)
                data = response.json()
                
                # Parse response
                if 'Time Series' in data:
                    time_series = data[f'Time Series ({interval})'] if interval != 'daily' else data['Time Series (Daily)']
                    
                    records = []
                    for timestamp, values in list(time_series.items())[:limit]:
                        records.append({
                            'timestamp': pd.to_datetime(timestamp),
                            'open': float(values['1. open']),
                            'high': float(values['2. high']),
                            'low': float(values['3. low']),
                            'close': float(values['4. close']),
                            'volume': float(values['5. volume'])
                        })
                    
                    df = pd.DataFrame(records)
                    df.sort_values('timestamp', inplace=True)
                    
                    logger.info(f"📊 Alpha Vantage DATA: {symbol} - {len(df)} bars")
                    return df
                else:
                    raise ValueError(f"No data returned from Alpha Vantage: {data.get('Note', 'Unknown error')}")
                
            except Exception as e:
                logger.error(f"Alpha Vantage error for {symbol}: {str(e)}")
                raise
        
        return self._safe_api_call(fetch_av_data)
        
    def get_ticker(self, symbol):
        """Get ticker data dari Alpha Vantage"""
        def fetch_ticker():
            try:
                params = {
                    'function': 'GLOBAL_QUOTE',
                    'symbol': symbol.replace('/', ''),
                    'apikey': self.api_key
                }
                
                response = requests.get(self.base_url, params=params)
                data = response.json()
                
                if 'Global Quote' in data:
                    quote = data['Global Quote']
                    return {
                        'last': float(quote['05. price']),
                        'volume': float(quote['06. volume']),
                        'high': float(quote['03. high']),
                        'low': float(quote['04. low']),
                        'open': float(quote['02. open']),
                        'symbol': symbol
                    }
                else:
                    raise ValueError(f"No quote data from Alpha Vantage")
                
            except Exception as e:
                logger.error(f"Alpha Vantage ticker error: {str(e)}")
                raise
        
        return self._safe_api_call(fetch_ticker)

    def get_popular_assets(self, limit=100):
        """Get popular assets dari Alpha Vantage"""
        # Alpha Vantage tidak punya endpoint untuk popular assets
        # Gunakan hardcoded list
        popular_assets = [
            'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA', 'META', 'NVDA', 
            'JPM', 'V', 'JNJ', 'WMT', 'PG', 'MA', 'UNH', 'HD', 
            'BAC', 'DIS', 'CMCSA', 'NFLX', 'ADBE'
        ]
        return popular_assets[:limit]

class DataProviderFactory:
    """Factory untuk membuat data provider"""
    
    @staticmethod
    def create_provider(provider_type, **kwargs):
        """Create data provider berdasarkan type"""
        if provider_type == 'ccxt':
            exchange_id = kwargs.get('exchange_id', 'binance')
            market_type = kwargs.get('market_type', 'spot')
            api_key = kwargs.get('api_key', '')
            secret = kwargs.get('secret', '')
            
            if market_type == 'future':
                return EnhancedCCXTFuturesProvider(
                    exchange_id=exchange_id,
                    api_key=api_key,
                    secret=secret
                )
            else:
                return EnhancedCCXTDataProvider(
                    exchange_id=exchange_id,
                    market_type=market_type,
                    api_key=api_key,
                    secret=secret
                )
                
        elif provider_type == 'yfinance':
            market_type = kwargs.get('market_type', 'stock')
            return EnhancedYFinanceDataProvider(market_type=market_type)
            
        elif provider_type == 'alphavantage':
            api_key = kwargs.get('api_key', 'demo')
            return AlphaVantageProvider(api_key=api_key)
            
        elif provider_type == 'dynamic':
            market_type = kwargs.get('market_type', 'crypto')
            return DynamicDataProvider(market_type=market_type)
            
        else:
            raise ValueError(f"Unknown provider type: {provider_type}")

class DynamicDataProvider(EnhancedDataProvider):
    """Dynamic data provider dengan fallback yang benar - FIXED VERSION"""
    
    def __init__(self, market_type="crypto"):
        super().__init__()
        self.market_type = market_type
        
        # List exchange untuk dicoba secara berurutan
        self.exchange_list = ['binance', 'kucoin', 'bybit', 'okx']
        self.current_exchange_idx = 0
        
        # Initialize semua provider yang mungkin dibutuhkan
        self.providers = {}
        
        # Coba setup CCXT provider dengan fallback yang benar
        self._setup_providers_with_fallback()
        
        logger.info(f"DynamicDataProvider initialized for {market_type} market")

    def _setup_providers_with_fallback(self):
        """Setup providers dengan sistem fallback yang benar - FIXED"""
        
        # **PERBAIKAN: Tentukan provider berdasarkan market_type**
        if self.market_type in ['crypto', 'crypto_spot', 'crypto_future']:
            successful_exchange = None
            
            # Coba satu per satu exchange
            for exchange_id in self.exchange_list:
                try:
                    logger.info(f"🔄 Trying to connect to {exchange_id}...")
                    
                    # Coba spot dengan timeout pendek
                    spot_provider = EnhancedCCXTDataProvider(exchange_id=exchange_id, market_type='spot')
                    
                    # **FIXED: Test koneksi yang sebenarnya, bukan hanya get_popular_assets**
                    # Coba load markets untuk test koneksi
                    if spot_provider.exchange is not None:
                        try:
                            # Test dengan fetch ticker untuk BTC/USDT (timeout 5 detik)
                            test_ticker = spot_provider.get_ticker("BTC/USDT")
                            if test_ticker and test_ticker.get('last', 0) > 0:
                                successful_exchange = exchange_id
                                logger.info(f"✅ Successfully connected to {exchange_id}")
                                
                                # Setup providers dengan exchange yang berhasil
                                self.providers = {
                                    'crypto_spot': spot_provider,
                                    'crypto_future': EnhancedCCXTFuturesProvider(exchange_id=exchange_id),
                                    'forex': EnhancedYFinanceDataProvider(market_type='forex'),
                                    'saham_id': EnhancedYFinanceDataProvider(market_type='saham_id'), 
                                    'us_stocks': EnhancedYFinanceDataProvider(market_type='us_stocks'),
                                    'stocks': EnhancedYFinanceDataProvider(market_type='us_stocks'),
                                    'crypto': spot_provider  # default untuk crypto
                                }
                                break
                            else:
                                logger.warning(f"❌ {exchange_id} test failed: Invalid ticker data")
                        except Exception as test_e:
                            logger.warning(f"❌ {exchange_id} test failed: {test_e}")
                    else:
                        logger.warning(f"❌ {exchange_id} exchange not initialized")
                        
                except Exception as e:
                    logger.warning(f"❌ Failed to initialize {exchange_id}: {e}")
                    continue
            
            # **FIXED: Jika semua exchange gagal, langsung gunakan YFinance**
            if not successful_exchange:
                logger.warning("⚠️ All exchanges failed, using YFinance as fallback...")
                successful_exchange = "yfinance"
                
                # Setup semua provider dengan YFinance
                self.providers = {
                    'crypto_spot': EnhancedYFinanceDataProvider(market_type='crypto'),
                    'crypto_future': EnhancedYFinanceDataProvider(market_type='crypto'),
                    'forex': EnhancedYFinanceDataProvider(market_type='forex'),
                    'saham_id': EnhancedYFinanceDataProvider(market_type='saham_id'), 
                    'us_stocks': EnhancedYFinanceDataProvider(market_type='us_stocks'),
                    'stocks': EnhancedYFinanceDataProvider(market_type='us_stocks'),
                    'crypto': EnhancedYFinanceDataProvider(market_type='crypto')
                }
        else:
            # **PERBAIKAN: Untuk market_type non-crypto, langsung gunakan YFinance**
            logger.info(f"📊 Non-crypto market type detected: {self.market_type}, using YFinance")
            successful_exchange = "yfinance"
            
            # Setup semua provider dengan YFinance
            self.providers = {
                'crypto_spot': EnhancedYFinanceDataProvider(market_type='crypto'),
                'crypto_future': EnhancedYFinanceDataProvider(market_type='crypto'),
                'forex': EnhancedYFinanceDataProvider(market_type='forex'),
                'saham_id': EnhancedYFinanceDataProvider(market_type='saham_id'), 
                'us_stocks': EnhancedYFinanceDataProvider(market_type='us_stocks'),
                'stocks': EnhancedYFinanceDataProvider(market_type='us_stocks'),
                'crypto': EnhancedYFinanceDataProvider(market_type='crypto')
            }
        
        # Set default provider
        self.default_provider = self._get_default_provider(self.market_type)
        logger.info(f"🎯 Using {successful_exchange} as data source for {self.market_type}")
        
        # Log provider status
        for provider_name, provider in self.providers.items():
            logger.info(f"   {provider_name}: {provider.__class__.__name__}")

    def _get_default_provider(self, market_type):
        """Get default provider berdasarkan market type - FIXED"""
        provider_map = {
            'crypto': self.providers.get('crypto', None),
            'crypto_spot': self.providers.get('crypto_spot', None),
            'crypto_future': self.providers.get('crypto_future', None),
            'forex': self.providers.get('forex', None),
            'saham_id': self.providers.get('saham_id', None),
            'us_stocks': self.providers.get('us_stocks', None),
            'stocks': self.providers.get('stocks', None)
        }
        
        default = provider_map.get(market_type)
        if default is None:
            # Fallback ke YFinance jika provider tidak ditemukan
            logger.warning(f"⚠️ Provider not found for {market_type}, falling back to YFinance")
            default = EnhancedYFinanceDataProvider(market_type=market_type)
            
        return default

    def _detect_symbol_type(self, symbol):
        """Detect symbol type secara otomatis"""
        if not symbol:
            return 'unknown'
            
        symbol_upper = symbol.upper()
        
        # Crypto detection
        if ('/USDT' in symbol_upper or '/BUSD' in symbol_upper or 
            '/BTC' in symbol_upper or '/ETH' in symbol_upper or
            '/USD' in symbol_upper and '=X' not in symbol_upper):
            if ':USDT' in symbol_upper or 'PERP' in symbol_upper or 'FUTURES' in symbol_upper:
                return 'crypto_future'
            else:
                return 'crypto_spot'
        
        # Forex detection
        if ('=X' in symbol_upper or 'FOREX' in symbol_upper or
            ('/' in symbol_upper and 'USD' in symbol_upper and len(symbol_upper) <= 7)):
            return 'forex'
        
        # Saham Indonesia detection
        if '.JK' in symbol_upper:
            return 'saham_id'
        
        # US Stocks detection
        if (len(symbol) <= 5 and symbol.isalpha() and 
            not any(c in symbol for c in ['/', '=', '.', '-'])):
            return 'us_stocks'
        
        # Default ke crypto spot
        return 'crypto_spot'

    def get_ohlcv(self, symbol: str, timeframe: str = '1h', limit: int = 200):
        """Get OHLCV data dengan auto-detection symbol type - FIXED"""
        try:
            # Deteksi tipe symbol
            symbol_type = self._detect_symbol_type(symbol)
            provider = self.providers.get(symbol_type, self.default_provider)
            
            logger.info(f"🔍 Getting OHLCV for {symbol} (detected as {symbol_type}) using {provider.__class__.__name__}")
            
            # Gunakan cache mechanism
            cached_data = self._get_cached_data(symbol, timeframe, limit)
            if cached_data is not None:
                return cached_data
            
            # **PERBAIKAN: Jika provider adalah CCXT dan exchange None, langsung fallback ke YFinance**
            if (isinstance(provider, (EnhancedCCXTDataProvider, EnhancedCCXTFuturesProvider)) 
                and hasattr(provider, 'exchange') 
                and provider.exchange is None):
                
                logger.warning(f"⚠️ {provider.__class__.__name__} exchange is None, falling back to YFinance")
                # Cari YFinance provider yang sesuai
                if symbol_type == 'crypto_spot' or symbol_type == 'crypto_future':
                    fallback_provider = self.providers.get('crypto_spot', self.default_provider)
                    if isinstance(fallback_provider, EnhancedYFinanceDataProvider):
                        provider = fallback_provider
                        logger.info(f"   Using YFinance for {symbol}")
            
            # Get data dari provider yang sesuai
            data = provider.get_ohlcv(symbol, timeframe, limit)
            
            # Cache hasil yang valid
            if data is not None and len(data) > 0:
                self._set_cached_data(symbol, timeframe, limit, data)
            
            return data
            
        except Exception as e:
            logger.error(f"Error getting OHLCV for {symbol}: {e}")
            # Fallback ke default provider
            return self.default_provider.get_ohlcv(symbol, timeframe, limit)

    def get_ticker(self, symbol: str):
        """Get ticker data dengan auto-detection symbol type - FIXED"""
        try:
            # Deteksi tipe symbol
            symbol_type = self._detect_symbol_type(symbol)
            provider = self.providers.get(symbol_type, self.default_provider)
            
            logger.info(f"🔍 Getting ticker for {symbol} (detected as {symbol_type}) using {provider.__class__.__name__}")
            
            # **PERBAIKAN: Jika provider adalah CCXT dan exchange None, langsung fallback ke YFinance**
            if (isinstance(provider, (EnhancedCCXTDataProvider, EnhancedCCXTFuturesProvider)) 
                and hasattr(provider, 'exchange') 
                and provider.exchange is None):
                
                logger.warning(f"⚠️ {provider.__class__.__name__} exchange is None, falling back to YFinance")
                # Cari YFinance provider yang sesuai
                if symbol_type == 'crypto_spot' or symbol_type == 'crypto_future':
                    fallback_provider = self.providers.get('crypto_spot', self.default_provider)
                    if isinstance(fallback_provider, EnhancedYFinanceDataProvider):
                        provider = fallback_provider
                        logger.info(f"   Using YFinance for {symbol}")
            
            return provider.get_ticker(symbol)
            
        except Exception as e:
            logger.error(f"Error getting ticker for {symbol}: {e}")
            # Fallback ke default provider
            return self.default_provider.get_ticker(symbol)

    def get_popular_assets(self, limit: int = 100, asset_type: str = None) -> List:
        """Get popular assets dengan opsi pilih spot/futures - FIXED VERSION"""
        try:
            # **PERBAIKAN: Jika market_type bukan crypto, langsung gunakan provider yang sesuai**
            if self.market_type not in ['crypto', 'crypto_spot', 'crypto_future']:
                logger.info(f"📊 Getting {limit} {self.market_type} assets from YFinance")
                provider = self.providers.get(self.market_type, self.default_provider)
                assets = provider.get_popular_assets(limit)
                
                # Format hasil
                if assets and isinstance(assets[0], str):
                    formatted_assets = []
                    for symbol in assets:
                        formatted_assets.append({
                            'symbol': symbol,
                            'name': symbol
                        })
                    return formatted_assets[:limit]
                else:
                    return assets[:limit]
            
            # **PERBAIKAN: Gunakan provider berdasarkan asset_type yang diminta**
            provider_key = None
            
            if asset_type:
                asset_type_lower = asset_type.lower()
                if asset_type_lower in ['futures', 'future']:
                    provider_key = 'crypto_future'
                elif asset_type_lower in ['spot', 'spots']:
                    provider_key = 'crypto_spot'
            
            # Jika tidak ada asset_type, gunakan berdasarkan market_type
            if not provider_key:
                if self.market_type == 'crypto_future':
                    provider_key = 'crypto_future'
                else:
                    provider_key = 'crypto_spot'  # default untuk crypto
            
            # Dapatkan provider
            provider = self.providers.get(provider_key, self.default_provider)
            
            logger.info(f"📊 Getting {limit} {asset_type or provider_key} assets from {provider.__class__.__name__}")
            
            # Get assets dari provider
            assets = provider.get_popular_assets(limit)
            
            if not assets:
                logger.warning(f"⚠️ No assets returned from {provider.__class__.__name__}")
                return self._get_fallback_assets(limit)
            
            # **PERBAIKAN: Filter assets berdasarkan type yang diminta**
            filtered_assets = []
            
            if asset_type and asset_type.lower() in ['futures', 'future']:
                # Hanya ambil futures symbols
                for asset in assets:
                    if isinstance(asset, str):
                        if any(marker in asset for marker in [':USDT', 'PERP', '/USDT:', 'FUTURES', 'USDT:', '-USDT']):
                            filtered_assets.append(asset)
                    elif isinstance(asset, dict):
                        symbol = asset.get('symbol', '')
                        if any(marker in symbol for marker in [':USDT', 'PERP', '/USDT:', 'FUTURES', 'USDT:', '-USDT']):
                            filtered_assets.append(asset)
            elif asset_type and asset_type.lower() in ['spot', 'spots']:
                # Hanya ambil spot symbols
                for asset in assets:
                    if isinstance(asset, str):
                        if not any(marker in asset for marker in [':USDT', 'PERP', '/USDT:', 'FUTURES', 'USDT:', '-USDT']):
                            filtered_assets.append(asset)
                    elif isinstance(asset, dict):
                        symbol = asset.get('symbol', '')
                        if not any(marker in symbol for marker in [':USDT', 'PERP', '/USDT:', 'FUTURES', 'USDT:', '-USDT']):
                            filtered_assets.append(asset)
            else:
                filtered_assets = assets
            
            # Jika setelah filtering kosong, return aslinya
            if not filtered_assets:
                filtered_assets = assets
            
            # Format hasil untuk konsistensi
            formatted_result = []
            for asset in filtered_assets:
                if isinstance(asset, dict):
                    formatted_result.append(asset)
                else:
                    formatted_result.append({
                        'symbol': asset,
                        'name': asset
                    })
            
            logger.info(f"✅ Found {len(formatted_result)} {asset_type or provider_key} assets")
            if formatted_result:
                sample_size = min(5, len(formatted_result))
                sample = [item['symbol'] for item in formatted_result[:sample_size]]
                logger.info(f"   Sample: {sample}")
            
            return formatted_result[:limit]
            
        except Exception as e:
            logger.error(f"❌ Error getting popular assets: {e}")
            # Fallback ke emergency assets
            return self._get_fallback_assets(limit)

    def _get_fallback_assets(self, limit: int):
        """Emergency fallback assets - ENHANCED"""
        logger.warning("🔄 Using emergency fallback assets")
        
        emergency_assets = {
            "crypto": [
                {"symbol": "BTC/USDT", "name": "Bitcoin"},
                {"symbol": "ETH/USDT", "name": "Ethereum"},
                {"symbol": "BNB/USDT", "name": "Binance Coin"},
                {"symbol": "XRP/USDT", "name": "Ripple"},
                {"symbol": "ADA/USDT", "name": "Cardano"},
                {"symbol": "SOL/USDT", "name": "Solana"},
                {"symbol": "DOT/USDT", "name": "Polkadot"},
                {"symbol": "DOGE/USDT", "name": "Dogecoin"},
                {"symbol": "AVAX/USDT", "name": "Avalanche"},
                {"symbol": "MATIC/USDT", "name": "Polygon"}
            ],
            "crypto_spot": [
                {"symbol": "BTC/USDT", "name": "Bitcoin"},
                {"symbol": "ETH/USDT", "name": "Ethereum"},
                {"symbol": "BNB/USDT", "name": "Binance Coin"},
                {"symbol": "XRP/USDT", "name": "Ripple"},
                {"symbol": "ADA/USDT", "name": "Cardano"},
                {"symbol": "SOL/USDT", "name": "Solana"},
                {"symbol": "DOT/USDT", "name": "Polkadot"},
                {"symbol": "DOGE/USDT", "name": "Dogecoin"},
                {"symbol": "AVAX/USDT", "name": "Avalanche"},
                {"symbol": "MATIC/USDT", "name": "Polygon"}
            ],
            "crypto_future": [
                {"symbol": "BTC/USDT:USDT", "name": "Bitcoin Futures"},
                {"symbol": "ETH/USDT:USDT", "name": "Ethereum Futures"},
                {"symbol": "BNB/USDT:USDT", "name": "Binance Coin Futures"},
                {"symbol": "XRP/USDT:USDT", "name": "Ripple Futures"},
                {"symbol": "ADA/USDT:USDT", "name": "Cardano Futures"},
                {"symbol": "SOL/USDT:USDT", "name": "Solana Futures"},
                {"symbol": "DOT/USDT:USDT", "name": "Polkadot Futures"},
                {"symbol": "DOGE/USDT:USDT", "name": "Dogecoin Futures"},
                {"symbol": "AVAX/USDT:USDT", "name": "Avalanche Futures"},
                {"symbol": "MATIC/USDT:USDT", "name": "Polygon Futures"}
            ],
            "forex": [
                {"symbol": "EUR/USD", "name": "Euro/Dollar"},
                {"symbol": "USD/JPY", "name": "Dollar/Yen"},
                {"symbol": "GBP/USD", "name": "Pound/Dollar"},
                {"symbol": "USD/CHF", "name": "Dollar/Franc"},
                {"symbol": "AUD/USD", "name": "Aussie/Dollar"},
                {"symbol": "USD/CAD", "name": "Dollar/Canadian"},
                {"symbol": "NZD/USD", "name": "Kiwi/Dollar"},
                {"symbol": "EUR/GBP", "name": "Euro/Pound"},
                {"symbol": "EUR/JPY", "name": "Euro/Yen"},
                {"symbol": "GBP/JPY", "name": "Pound/Yen"}
            ],
            "us_stocks": [
                {"symbol": "AAPL", "name": "Apple Inc"},
                {"symbol": "MSFT", "name": "Microsoft"},
                {"symbol": "GOOGL", "name": "Google"},
                {"symbol": "AMZN", "name": "Amazon"},
                {"symbol": "TSLA", "name": "Tesla"},
                {"symbol": "META", "name": "Meta Platforms"},
                {"symbol": "NVDA", "name": "NVIDIA"},
                {"symbol": "NFLX", "name": "Netflix"},
                {"symbol": "JPM", "name": "JPMorgan Chase"},
                {"symbol": "V", "name": "Visa"}
            ],
            "stocks": [
                {"symbol": "AAPL", "name": "Apple Inc"},
                {"symbol": "MSFT", "name": "Microsoft"},
                {"symbol": "GOOGL", "name": "Google"},
                {"symbol": "AMZN", "name": "Amazon"},
                {"symbol": "TSLA", "name": "Tesla"},
                {"symbol": "META", "name": "Meta Platforms"},
                {"symbol": "NVDA", "name": "NVIDIA"},
                {"symbol": "NFLX", "name": "Netflix"},
                {"symbol": "JPM", "name": "JPMorgan Chase"},
                {"symbol": "V", "name": "Visa"}
            ],
            "saham_id": [
                {"symbol": "BBCA.JK", "name": "Bank BCA"},
                {"symbol": "BBRI.JK", "name": "Bank BRI"},
                {"symbol": "BMRI.JK", "name": "Bank Mandiri"},
                {"symbol": "TLKM.JK", "name": "Telkom Indonesia"},
                {"symbol": "ASII.JK", "name": "Astra International"},
                {"symbol": "UNVR.JK", "name": "Unilever Indonesia"},
                {"symbol": "ICBP.JK", "name": "Indofood CBP"},
                {"symbol": "INDF.JK", "name": "Indofood"},
                {"symbol": "WIKA.JK", "name": "Wijaya Karya"},
                {"symbol": "PGAS.JK", "name": "Perusahaan Gas Negara"}
            ]
        }
        
        assets = emergency_assets.get(self.market_type, [])
        return assets[:limit]

    def get_health_metrics(self) -> Dict:
        """Get comprehensive health metrics untuk semua providers"""
        base_metrics = super().get_health_metrics()
        
        provider_metrics = {}
        for provider_name, provider in self.providers.items():
            try:
                provider_metrics[provider_name] = provider.get_health_metrics()
            except:
                provider_metrics[provider_name] = {'error': 'Unable to get metrics'}
        
        base_metrics['providers'] = provider_metrics
        base_metrics['market_type'] = self.market_type
        base_metrics['default_provider'] = self.default_provider.__class__.__name__
        
        # Tambah info apakah menggunakan CCXT atau YFinance
        using_ccxt = False
        for provider in self.providers.values():
            if isinstance(provider, (EnhancedCCXTDataProvider, EnhancedCCXTFuturesProvider)):
                if hasattr(provider, 'exchange') and provider.exchange is not None:
                    using_ccxt = True
                    break
        
        base_metrics['using_ccxt'] = using_ccxt
        base_metrics['using_yfinance'] = not using_ccxt
        
        return base_metrics

# =============================================
# DATA PROVIDER MONITOR
# =============================================

class DataProviderMonitor:
    """Monitor kesehatan data providers"""
    
    def __init__(self):
        self.providers = {}
        self.health_history = {}
        
    def register_provider(self, name: str, provider):
        """Register provider untuk monitoring"""
        self.providers[name] = provider
        self.health_history[name] = []
        logger.info(f"Registered provider: {name}")
        
    def get_health_report(self):
        """Get health report untuk semua providers"""
        report = {
            'total_providers': len(self.providers),
            'providers': {}
        }
        
        for name, provider in self.providers.items():
            try:
                # Coba ambil metrics jika tersedia
                if hasattr(provider, 'get_health_metrics'):
                    metrics = provider.get_health_metrics()
                else:
                    metrics = {'status': 'unknown'}
                
                report['providers'][name] = {
                    'status': 'active',
                    **metrics
                }
            except Exception as e:
                report['providers'][name] = {
                    'status': 'error',
                    'error': str(e)
                }
        
        return report

# Test function
def test_dynamic_provider():
    """Test DynamicDataProvider dengan fallback system"""
    print("🧪 Testing DynamicDataProvider...")
    
    # Test untuk crypto spot
    print("\n1. Testing CRYPTO SPOT:")
    provider = DynamicDataProvider(market_type="crypto")
    
    spot_assets = provider.get_popular_assets(10, asset_type='spot')
    print(f"✅ Popular SPOT assets: {len(spot_assets)} found")
    for i, asset in enumerate(spot_assets[:5]):
        if isinstance(asset, dict):
            print(f"   {i+1}. {asset['symbol']} ({asset.get('name', 'N/A')})")
        else:
            print(f"   {i+1}. {asset}")
    
    # Test untuk crypto futures
    print("\n2. Testing CRYPTO FUTURES:")
    futures_assets = provider.get_popular_assets(10, asset_type='futures')
    print(f"✅ Popular FUTURES assets: {len(futures_assets)} found")
    for i, asset in enumerate(futures_assets[:5]):
        if isinstance(asset, dict):
            print(f"   {i+1}. {asset['symbol']} ({asset.get('name', 'N/A')})")
        else:
            print(f"   {i+1}. {asset}")
    
    # Test untuk saham_id
    print("\n3. Testing SAHAM_ID:")
    provider_saham = DynamicDataProvider(market_type="saham_id")
    
    saham_assets = provider_saham.get_popular_assets(10)
    print(f"✅ Popular SAHAM_ID assets: {len(saham_assets)} found")
    for i, asset in enumerate(saham_assets[:5]):
        if isinstance(asset, dict):
            print(f"   {i+1}. {asset['symbol']} ({asset.get('name', 'N/A')})")
        else:
            print(f"   {i+1}. {asset}")
    
    # Test OHLCV untuk BTC
    try:
        print("\n4. Testing OHLCV for BTC/USDT:")
        ohlcv = provider.get_ohlcv("BTC/USDT", '1h', 10)
        if ohlcv is not None:
            print(f"✅ OHLCV data: {len(ohlcv)} rows for BTC/USDT")
            print(f"   Latest price: {ohlcv['close'].iloc[-1] if len(ohlcv) > 0 else 'N/A'}")
        else:
            print("❌ No OHLCV data for BTC/USDT")
    except Exception as e:
        print(f"❌ OHLCV error: {e}")
    
    # Test ticker
    try:
        print("\n5. Testing TICKER for BTC/USDT:")
        ticker = provider.get_ticker("BTC/USDT")
        if ticker:
            print(f"✅ Ticker data: {ticker['last']} for BTC/USDT")
        else:
            print("❌ No ticker data for BTC/USDT")
    except Exception as e:
        print(f"❌ Ticker error: {e}")
    
    # Test health metrics
    print("\n6. Testing HEALTH METRICS:")
    metrics = provider.get_health_metrics()
    print(f"✅ Health metrics available")
    print(f"   Error rate: {metrics.get('error_rate', 'N/A')}")
    print(f"   Default provider: {metrics.get('default_provider', 'N/A')}")
    print(f"   Market type: {metrics.get('market_type', 'N/A')}")
    print(f"   Using CCXT: {metrics.get('using_ccxt', 'N/A')}")
    print(f"   Using YFinance: {metrics.get('using_yfinance', 'N/A')}")

if __name__ == "__main__":
    test_dynamic_provider()
