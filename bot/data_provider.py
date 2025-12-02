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
        """Get popular futures assets dengan prioritas major coins"""
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
            
            # Cari futures contracts
            futures_markets = [
                symbol for symbol, market in markets.items()
                if (market.get('future', False) or 
                    '/USDT:' in symbol or 
                    ':USDT' in symbol or
                    'PERP' in symbol)
            ]
            
            logger.info(f"📊 Found {len(futures_markets)} futures markets")
            
            # Filter stablecoins
            excluded_coins = ['BUSD', 'USDC', 'DAI', 'TUSD', 'USDP', 'UST', 'FDUSD']
            filtered_markets = [
                symbol for symbol in futures_markets 
                if not any(excluded in symbol for excluded in excluded_coins)
            ]
            
            # **PERBAIKAN: Prioritize major futures coins**
            major_futures = [
                'BTC/USDT:USDT', 'ETH/USDT:USDT', 'BNB/USDT:USDT', 
                'XRP/USDT:USDT', 'ADA/USDT:USDT', 'SOL/USDT:USDT',
                'DOT/USDT:USDT', 'DOGE/USDT:USDT', 'AVAX/USDT:USDT', 'MATIC/USDT:USDT',
                'LTC/USDT:USDT', 'LINK/USDT:USDT', 'ATOM/USDT:USDT', 'XLM/USDT:USDT'
            ]
            
            # **PERBAIKAN: Gabungkan dengan logika yang lebih baik**
            result = []
            
            # 1. Tambahkan major futures yang tersedia
            for futures_coin in major_futures:
                # Cari format yang tepat di filtered_markets
                for symbol in filtered_markets:
                    if futures_coin in symbol and symbol not in result:
                        result.append(symbol)
                        break
            
            # 2. Tambahkan futures lain (yang belum ada di result)
            for symbol in filtered_markets:
                if symbol not in result and len(result) < limit:
                    result.append(symbol)
            
            # 3. Jika masih kurang, tambahkan format alternatif
            if len(result) < limit:
                # Coba cari dengan pattern yang lebih umum
                for symbol in filtered_markets:
                    if any(coin.split('/')[0] in symbol for coin in major_futures):
                        if symbol not in result and len(result) < limit:
                            result.append(symbol)
            
            logger.info(f"✅ CCXT Futures returning {len(result)} popular FUTURES assets")
            logger.info(f"   Top 5: {result[:5]}")
            return result[:limit]
            
        except Exception as e:
            logger.error(f"Error getting popular futures from {self.exchange_id}: {str(e)}")
            return self._get_fallback_futures_coins(limit)

    def _get_fallback_futures_coins(self, limit):
        """Fallback futures coins"""
        major_pairs = [
            'BTC/USDT:USDT', 'ETH/USDT:USDT', 'BNB/USDT:USDT',
            'XRP/USDT:USDT', 'ADA/USDT:USDT', 'SOL/USDT:USDT',
            'DOT/USDT:USDT', 'DOGE/USDT:USDT', 'AVAX/USDT:USDT', 'MATIC/USDT:USDT'
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
        """Get popular assets berdasarkan market type"""
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
        """Get popular cryptocurrencies"""
        crypto_pairs = [
            'BTC-USD', 'ETH-USD', 'BNB-USD', 'XRP-USD', 'ADA-USD',
            'SOL-USD', 'DOT-USD', 'DOGE-USD', 'AVAX-USD', 'MATIC-USD',
            'LTC-USD', 'LINK-USD', 'ATOM-USD', 'XLM-USD', 'BCH-USD',
            'ETC-USD', 'FIL-USD', 'THETA-USD', 'EOS-USD', 'XTZ-USD'
        ]
        result = crypto_pairs[:limit]
        logger.info(f"YFinance returning {len(result)} popular crypto assets")
        return result

    def _get_popular_forex(self, limit):
        """Get popular forex pairs"""
        forex_pairs = [
            'EURUSD=X', 'USDJPY=X', 'GBPUSD=X', 'AUDUSD=X', 'USDCAD=X',
            'USDCHF=X', 'NZDUSD=X', 'EURGBP=X', 'EURJPY=X', 'GBPJPY=X'
        ]
        result = forex_pairs[:limit]
        logger.info(f"YFinance returning {len(result)} popular forex pairs")
        return result

    def _get_popular_indonesian_stocks(self, limit):
        """Get popular Indonesian stocks"""
        id_stocks = [
            'BBCA.JK', 'BBRI.JK', 'BMRI.JK', 'BBNI.JK', 'BNGA.JK',
            'TLKM.JK', 'ASII.JK', 'UNVR.JK', 'ICBP.JK', 'INDF.JK'
        ]
        result = id_stocks[:limit]
        logger.info(f"YFinance returning {len(result)} popular Indonesian stocks")
        return result

    def _get_popular_us_stocks(self, limit):
        """Get popular US stocks"""
        us_stocks = [
            'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA', 'META', 'NVDA', 'NFLX',
            'BRK-B', 'JNJ', 'JPM', 'V', 'PG', 'UNH', 'HD', 'DIS', 'PYPL'
        ]
        result = us_stocks[:limit]
        logger.info(f"YFinance returning {len(result)} popular US stocks")
        return result

    def _get_fallback_assets(self, limit):
        """Fallback assets ketika primary method gagal"""
        fallback_assets = {
            "crypto": ['BTC-USD', 'ETH-USD', 'BNB-USD', 'XRP-USD', 'ADA-USD'],
            "forex": ['EURUSD=X', 'USDJPY=X', 'GBPUSD=X', 'AUDUSD=X', 'USDCAD=X'],
            "saham_id": ['BBCA.JK', 'BBRI.JK', 'BMRI.JK', 'TLKM.JK', 'ASII.JK'],
            "us_stocks": ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA']
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
    """Dynamic data provider dengan fallback yang benar"""
    
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
        """Setup providers dengan sistem fallback yang benar"""
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
                                'stocks': EnhancedYFinanceDataProvider(market_type='us_stocks')
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
                'stocks': EnhancedYFinanceDataProvider(market_type='us_stocks')
            }
        
        self.default_provider = self._get_default_provider(self.market_type)
        logger.info(f"🎯 Using {successful_exchange} as data source")
        
        # Log provider status
        for provider_name, provider in self.providers.items():
            logger.info(f"   {provider_name}: {provider.__class__.__name__}")

    def _get_default_provider(self, market_type):
        """Get default provider berdasarkan market type"""
        provider_map = {
            'crypto': self.providers.get('crypto_spot', None),
            'forex': self.providers.get('forex', None),
            'saham_id': self.providers.get('saham_id', None),
            'us_stocks': self.providers.get('us_stocks', None),
            'stocks': self.providers.get('stocks', None)
        }
        
        default = provider_map.get(market_type)
        if default is None:
            # Fallback ke YFinance jika provider tidak ditemukan
            default = EnhancedYFinanceDataProvider(market_type=market_type)
            
        return default

    def _detect_symbol_type(self, symbol):
        """Detect symbol type secara otomatis"""
        if not symbol:
            return 'unknown'
            
        symbol_upper = symbol.upper()
        
        # Crypto detection
        if ('/USDT' in symbol_upper or '/BUSD' in symbol_upper or 
            '/BTC' in symbol_upper or '/ETH' in symbol_upper):
            if ':USDT' in symbol_upper or 'PERP' in symbol_upper or 'FUTURES' in symbol_upper:
                return 'crypto_future'
            else:
                return 'crypto_spot'
        
        # Forex detection
        if ('/USD' in symbol_upper or '/EUR' in symbol_upper or '/JPY' in symbol_upper or
            '=X' in symbol_upper or 'FOREX' in symbol_upper):
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
        """Get OHLCV data dengan auto-detection symbol type"""
        try:
            # Deteksi tipe symbol
            symbol_type = self._detect_symbol_type(symbol)
            provider = self.providers.get(symbol_type, self.default_provider)
            
            logger.info(f"🔍 Getting OHLCV for {symbol} (detected as {symbol_type}) using {provider.__class__.__name__}")
            
            # Gunakan cache mechanism
            cached_data = self._get_cached_data(symbol, timeframe, limit)
            if cached_data is not None:
                return cached_data
            
            # **FIXED: Jika provider adalah CCXT dan exchange None, langsung fallback ke YFinance**
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
        """Get ticker data dengan auto-detection symbol type"""
        try:
            # Deteksi tipe symbol
            symbol_type = self._detect_symbol_type(symbol)
            provider = self.providers.get(symbol_type, self.default_provider)
            
            logger.info(f"🔍 Getting ticker for {symbol} (detected as {symbol_type}) using {provider.__class__.__name__}")
            
            # **FIXED: Jika provider adalah CCXT dan exchange None, langsung fallback ke YFinance**
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

    def get_popular_assets(self, limit: int = 100, asset_type: str = None):
        """Get popular assets dengan opsi pilih spot/future"""
        try:
            # Jika ada parameter asset_type, gunakan provider yang sesuai
            if asset_type:
                if asset_type.lower() in ['futures', 'future'] and 'crypto_future' in self.providers:
                    provider = self.providers['crypto_future']
                    logger.info(f"📊 Getting {limit} {asset_type} assets from {provider.__class__.__name__}")
                elif asset_type.lower() in ['spot', 'spots'] and 'crypto_spot' in self.providers:
                    provider = self.providers['crypto_spot']
                    logger.info(f"📊 Getting {limit} {asset_type} assets from {provider.__class__.__name__}")
                else:
                    provider = self.default_provider
                    logger.info(f"📊 Getting {limit} assets from default provider ({provider.__class__.__name__})")
            else:
                # Default: gunakan berdasarkan market_type
                provider = self.default_provider
                logger.info(f"📊 Getting {limit} {self.market_type} assets from default provider")
            
            # Get assets dari provider yang sesuai
            assets = provider.get_popular_assets(limit)
            
            # Filter berdasarkan asset_type jika diperlukan (untuk safety)
            if asset_type and asset_type.lower() in ['futures', 'future']:
                # Pastikan yang diambil benar futures
                filtered_assets = []
                for asset in assets:
                    if any(marker in asset for marker in [':USDT', 'PERP', '/USDT:', 'FUTURES']):
                        filtered_assets.append(asset)
                assets = filtered_assets[:limit] if filtered_assets else assets[:limit]
            elif asset_type and asset_type.lower() in ['spot', 'spots']:
                # Pastikan yang diambil benar spot
                filtered_assets = []
                for asset in assets:
                    if not any(marker in asset for marker in [':USDT', 'PERP', '/USDT:', 'FUTURES']):
                        filtered_assets.append(asset)
                assets = filtered_assets[:limit] if filtered_assets else assets[:limit]
            
            logger.info(f"✅ Found {len(assets)} {asset_type or self.market_type} assets")
            if assets:
                logger.info(f"   Sample: {assets[:3]}")
            return assets[:limit]
            
        except Exception as e:
            logger.error(f"Error getting popular assets: {e}")
            # Fallback ke emergency assets
            return self._get_fallback_assets(limit)

    def _get_fallback_assets(self, limit: int):
        """Emergency fallback assets"""
        logger.warning("🔄 Using emergency fallback assets")
        
        emergency_assets = {
            "crypto": [
                {"symbol": "BTC/USDT", "name": "Bitcoin"},
                {"symbol": "ETH/USDT", "name": "Ethereum"},
                {"symbol": "BNB/USDT", "name": "Binance Coin"},
                {"symbol": "XRP/USDT", "name": "Ripple"},
                {"symbol": "ADA/USDT", "name": "Cardano"}
            ],
            "forex": [
                {"symbol": "EUR/USD", "name": "Euro/Dollar"},
                {"symbol": "USD/JPY", "name": "Dollar/Yen"},
                {"symbol": "GBP/USD", "name": "Pound/Dollar"},
                {"symbol": "USD/CHF", "name": "Dollar/Franc"},
                {"symbol": "AUD/USD", "name": "Aussie/Dollar"}
            ],
            "us_stocks": [
                {"symbol": "AAPL", "name": "Apple Inc"},
                {"symbol": "MSFT", "name": "Microsoft"},
                {"symbol": "GOOGL", "name": "Google"},
                {"symbol": "AMZN", "name": "Amazon"},
                {"symbol": "TSLA", "name": "Tesla"}
            ],
            "saham_id": [
                {"symbol": "BBCA.JK", "name": "Bank BCA"},
                {"symbol": "BBRI.JK", "name": "Bank BRI"},
                {"symbol": "BMRI.JK", "name": "Bank Mandiri"},
                {"symbol": "TLKM.JK", "name": "Telkom Indonesia"},
                {"symbol": "ASII.JK", "name": "Astra International"}
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
    
    # Test untuk crypto
    provider = DynamicDataProvider(market_type="crypto")
    
    # Test popular assets SPOT
    print("\n📊 Testing SPOT assets:")
    spot_assets = provider.get_popular_assets(10, asset_type='spot')
    print(f"✅ Popular SPOT assets: {len(spot_assets)} found")
    for asset in spot_assets[:5]:
        print(f"   - {asset}")
    
    # Test popular assets FUTURES
    print("\n📊 Testing FUTURES assets:")
    futures_assets = provider.get_popular_assets(10, asset_type='futures')
    print(f"✅ Popular FUTURES assets: {len(futures_assets)} found")
    for asset in futures_assets[:5]:
        print(f"   - {asset}")
    
    # Test OHLCV untuk BTC
    try:
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
        ticker = provider.get_ticker("BTC/USDT")
        if ticker:
            print(f"✅ Ticker data: {ticker['last']} for BTC/USDT")
        else:
            print("❌ No ticker data for BTC/USDT")
    except Exception as e:
        print(f"❌ Ticker error: {e}")
    
    # Test health metrics
    metrics = provider.get_health_metrics()
    print(f"✅ Health metrics available")
    print(f"   Error rate: {metrics.get('error_rate', 'N/A')}")
    print(f"   Default provider: {metrics.get('default_provider', 'N/A')}")

if __name__ == "__main__":
    test_dynamic_provider()
