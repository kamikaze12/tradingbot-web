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

# Define DataProvider abstract class FIRST
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
    
    # Optional: Add health metrics method
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
    
    def get(self, symbol, timeframe, limit):
        """Get cached data"""
        self._clean_old_entries()
        key = self._generate_key(symbol, timeframe, limit)
        
        if key in self._cache:
            self._access_times[key] = time.time()
            return self._cache[key]
        return None
    
    def set(self, symbol, timeframe, limit, data):
        """Cache data"""
        self._clean_old_entries()
        key = self._generate_key(symbol, timeframe, limit)
        
        self._cache[key] = data
        self._access_times[key] = time.time()

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
                
                # Validate result if possible
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
        """Basic validation of data result"""
        if result is None:
            return False
        if isinstance(result, pd.DataFrame) and result.empty:
            return False
        if isinstance(result, dict) and not result:
            return False
        return True

class DataValidator:
    """Comprehensive data validation"""
    
    @staticmethod
    def validate_ohlcv_data(df: pd.DataFrame) -> Tuple[bool, List[str]]:
        """Validate OHLCV data quality"""
        issues = []
        
        if df is None or df.empty:
            return False, ["Empty DataFrame"]
        
        # Check required columns
        required_columns = ['open', 'high', 'low', 'close']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            issues.append(f"Missing columns: {missing_columns}")
        
        # Check for NaN values
        nan_columns = df[required_columns].columns[df[required_columns].isna().any()].tolist()
        if nan_columns:
            issues.append(f"NaN values in: {nan_columns}")
        
        # Check for infinite values
        for col in required_columns:
            if col in df.columns:
                if np.any(np.isinf(df[col])):
                    issues.append(f"Infinite values in {col}")
        
        # Check data consistency (high >= low, high >= open, high >= close, etc.)
        if all(col in df.columns for col in ['high', 'low']):
            invalid_high_low = df[df['high'] < df['low']]
            if not invalid_high_low.empty:
                issues.append(f"{len(invalid_high_low)} rows with high < low")
        
        # Check volume (if available)
        if 'volume' in df.columns:
            negative_volume = df[df['volume'] < 0]
            if not negative_volume.empty:
                issues.append(f"{len(negative_volume)} rows with negative volume")
        
        # Check timestamp monotonicity
        if 'timestamp' in df.columns:
            if not df['timestamp'].is_monotonic_increasing:
                issues.append("Timestamps not monotonically increasing")
        
        return len(issues) == 0, issues
    
    @staticmethod
    def clean_ohlcv_data(df: pd.DataFrame) -> pd.DataFrame:
        """Clean and normalize OHLCV data"""
        if df is None or df.empty:
            return df
        
        df_clean = df.copy()
        
        # Ensure numeric types
        numeric_columns = ['open', 'high', 'low', 'close', 'volume']
        for col in numeric_columns:
            if col in df_clean.columns:
                df_clean[col] = pd.to_numeric(df_clean[col], errors='coerce')
        
        # Remove rows with NaN in critical columns
        critical_columns = ['open', 'high', 'low', 'close']
        df_clean = df_clean.dropna(subset=critical_columns)
        
        # Fix data consistency issues
        if all(col in df_clean.columns for col in ['high', 'low']):
            df_clean['high'] = np.maximum(df_clean['high'], df_clean[['open', 'close']].max(axis=1))
            df_clean['low'] = np.minimum(df_clean['low'], df_clean[['open', 'close']].min(axis=1))
        
        # Ensure volume is non-negative
        if 'volume' in df_clean.columns:
            df_clean['volume'] = df_clean['volume'].clip(lower=0)
        
        # Sort by timestamp if available
        if 'timestamp' in df_clean.columns:
            df_clean = df_clean.sort_values('timestamp').reset_index(drop=True)
        
        return df_clean
    
    @staticmethod
    def calculate_data_quality_metrics(df: pd.DataFrame) -> DataQualityMetrics:
        """Calculate comprehensive data quality metrics"""
        if df is None or df.empty:
            return DataQualityMetrics(0, 0, 0, 0, 0)
        
        required_columns = ['open', 'high', 'low', 'close']
        
        # Completeness: percentage of non-null values in required columns
        completeness = np.mean([df[col].notna().mean() for col in required_columns if col in df.columns])
        
        # Freshness: how recent is the data (if timestamp available)
        freshness = 1.0
        if 'timestamp' in df.columns and not df.empty:
            latest_ts = pd.to_datetime(df['timestamp'].max())
            age_hours = (pd.Timestamp.now() - latest_ts).total_seconds() / 3600
            freshness = max(0, 1 - (age_hours / 24))  # 24-hour freshness scale
        
        # Consistency: check for data anomalies
        consistency_checks = []
        if all(col in df.columns for col in ['high', 'low']):
            consistency_checks.append((df['high'] >= df['low']).mean())
        if all(col in df.columns for col in ['high', 'open', 'close']):
            consistency_checks.append((df['high'] >= df[['open', 'close']].max(axis=1)).mean())
        
        consistency = np.mean(consistency_checks) if consistency_checks else 1.0
        
        # Validity: check for reasonable price movements
        validity = 1.0
        if 'close' in df.columns and len(df) > 1:
            returns = df['close'].pct_change().dropna()
            extreme_moves = (returns.abs() > 0.5).mean()  # More than 50% moves
            validity = 1 - extreme_moves
        
        overall_score = np.mean([completeness, freshness, consistency, validity])
        
        return DataQualityMetrics(
            completeness=completeness,
            freshness=freshness,
            consistency=consistency,
            validity=validity,
            overall_score=overall_score
        )

class EnhancedDataProvider(DataProvider, ABC):
    """Enhanced base data provider with common improvements"""
    
    def __init__(self):
        super().__init__()
        self.circuit_breaker = CircuitBreaker()
        self.retry_mechanism = RetryMechanism()
        self.data_cache = DataCache(ttl_seconds=300)  # 5 minutes cache
        self.validator = DataValidator()
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
        if data is not None and not (isinstance(data, pd.DataFrame) and data.empty):
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
        """Default implementation that should be overridden by subclasses"""
        logger.warning(f"get_popular_assets not properly implemented for {self.__class__.__name__}")
        
        # Provide basic fallback based on common assets
        fallback_assets = [
            'BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'XRP/USDT', 'ADA/USDT',
            'EUR/USD', 'USD/JPY', 'GBP/USD', 'AUD/USD', 'USD/CAD',
            'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA'
        ]
        return fallback_assets[:limit]

class AlphaVantageProvider(EnhancedDataProvider):
    def __init__(self, api_key=None):
        super().__init__()
        self.api_key = api_key or os.getenv('ALPHA_VANTAGE_KEY')
        if not self.api_key:
            logger.warning("Alpha Vantage API key not found.")
            self.api_key = None
        self.base_url = "https://www.alphavantage.co/query"

    def _convert_symbol(self, symbol, market_type='crypto'):
        if '/' in symbol:
            base, quote = symbol.split('/')
        elif '=X' in symbol:
            base = symbol.split('=')[0]
            return f"{base[:3]}/{base[3:]}"
        elif '.JK' in symbol:
            return symbol
        else:
            base = symbol.upper()
        if market_type == 'forex':
            return f"{base[:3]}/{base[3:]}"
        return base

    def get_ohlcv(self, symbol, timeframe='1d', limit=200):
        """Enhanced OHLCV with caching and validation"""
        # Check cache first
        cached_data = self._get_cached_data(symbol, timeframe, limit)
        if cached_data is not None:
            logger.info(f"Returning cached data for {symbol}")
            return cached_data

        if not self.api_key:
            return None
        
        def fetch_data():
            try:
                symbol_av = self._convert_symbol(symbol)
                market_type = 'crypto' if 'crypto' in symbol.lower() else 'forex'
                
                if '/' in symbol_av:
                    function = "FX_DAILY"
                else:
                    function = "DIGITAL_CURRENCY_DAILY" if market_type == 'crypto' else "TIME_SERIES_DAILY"
                
                params = {
                    "function": function,
                    "symbol": symbol_av,
                    "apikey": self.api_key,
                    "outputsize": "full" if limit > 100 else "compact"
                }
                
                if function == "FX_DAILY":
                    params["from_symbol"], params["to_symbol"] = symbol_av.split('/')
                elif function == "DIGITAL_CURRENCY_DAILY":
                    params["market"] = "USD"
                
                response = requests.get(self.base_url, params=params, timeout=10)
                response.raise_for_status()
                data = response.json()
                
                time_series_key = next((k for k in data.keys() if "Time Series" in k), None)
                if time_series_key:
                    ohlcv_data = data[time_series_key]
                    df = pd.DataFrame.from_dict(ohlcv_data, orient='index')
                    
                    # Convert string values to float
                    for col in df.columns:
                        df[col] = pd.to_numeric(df[col], errors='coerce')
                    
                    df['timestamp'] = pd.to_datetime(df.index)
                    
                    # Rename columns appropriately
                    column_mapping = {
                        '1. open': 'open',
                        '2. high': 'high', 
                        '3. low': 'low',
                        '4. close': 'close',
                        '5. volume': 'volume'
                    }
                    
                    # Find the actual column names in the dataframe
                    actual_columns = {}
                    for expected_col in column_mapping.keys():
                        for actual_col in df.columns:
                            if expected_col in actual_col:
                                actual_columns[expected_col] = actual_col
                                break
                    
                    # Create new dataframe with standardized column names
                    result_df = pd.DataFrame()
                    result_df['timestamp'] = df['timestamp']
                    
                    for expected_col, standardized_name in column_mapping.items():
                        if expected_col in actual_columns:
                            result_df[standardized_name] = df[actual_columns[expected_col]]
                    
                    # If volume column is missing, add it with zeros
                    if 'volume' not in result_df.columns:
                        result_df['volume'] = 0
                    
                    # Sort and limit
                    result_df = result_df.sort_values('timestamp').tail(limit)
                    
                    # Validate and clean data
                    is_valid, issues = self.validator.validate_ohlcv_data(result_df)
                    if not is_valid:
                        logger.warning(f"Data validation issues for {symbol}: {issues}")
                        result_df = self.validator.clean_ohlcv_data(result_df)
                    
                    return result_df
                return None
                
            except Exception as e:
                logger.error(f"AlphaVantage API error: {str(e)}")
                raise

        result = self._safe_api_call(fetch_data)
        
        # Cache the result
        self._set_cached_data(symbol, timeframe, limit, result)
        
        return result

    def get_ticker(self, symbol):
        """Enhanced ticker with error handling"""
        if not self.api_key:
            return None
        
        def fetch_ticker():
            try:
                symbol_av = self._convert_symbol(symbol)
                function = "CURRENCY_EXCHANGE_RATE" if '/' in symbol_av else "GLOBAL_QUOTE"
                params = {
                    "function": function,
                    "symbol": symbol_av,
                    "apikey": self.api_key
                }
                if function == "CURRENCY_EXCHANGE_RATE":
                    params["from_currency"], params["to_currency"] = symbol_av.split('/')
                
                response = requests.get(self.base_url, params=params, timeout=10)
                response.raise_for_status()
                data = response.json()
                
                if "Realtime Currency Exchange Rate" in data:
                    rate = data["Realtime Currency Exchange Rate"]
                    return {'last': float(rate['5. Exchange Rate']), 'volume': 0}
                elif "Global Quote" in data:
                    quote = data["Global Quote"]
                    return {'last': float(quote['05. price']), 'volume': float(quote.get('06. volume', 0))}
                return None
                
            except Exception as e:
                logger.error(f"AlphaVantage ticker error: {str(e)}")
                raise

        return self._safe_api_call(fetch_ticker)

    def get_popular_assets(self, limit=100):
        """Get popular assets from Alpha Vantage"""
        try:
            # Alpha Vantage doesn't have a direct popular assets endpoint
            # Return major forex pairs and stocks
            assets = []
            
            # Major forex pairs
            forex_pairs = ['EUR/USD', 'USD/JPY', 'GBP/USD', 'AUD/USD', 'USD/CAD']
            assets.extend(forex_pairs)
            
            # Major stocks
            stocks = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA', 'META', 'NVDA']
            assets.extend(stocks)
            
            # Major cryptocurrencies
            cryptos = ['BTC', 'ETH', 'BNB', 'XRP', 'ADA']
            assets.extend(cryptos)
            
            logger.info(f"AlphaVantage returning {len(assets[:limit])} popular assets")
            return assets[:limit]
            
        except Exception as e:
            logger.error(f"Error getting popular assets from Alpha Vantage: {str(e)}")
            # Fallback to basic assets
            fallback_assets = ['EUR/USD', 'USD/JPY', 'GBP/USD', 'AAPL', 'MSFT', 'BTC', 'ETH']
            return fallback_assets[:limit]

class EnhancedCCXTDataProvider(EnhancedDataProvider):
    """Enhanced CCXT provider with better error handling and fallbacks"""
    
    def __init__(self, exchange_id='kucoin', api_key='', secret=''):
        super().__init__()
        
        self.exchange_id = exchange_id
        exchange_class = getattr(ccxt, exchange_id, None)
        
        if exchange_class is None:
            logger.error(f"Exchange {exchange_id} not found in CCXT")
            self.exchange = None
        else:
            try:
                self.exchange = exchange_class({
                    'apiKey': api_key,
                    'secret': secret,
                    'enableRateLimit': True,
                    'timeout': 30000,
                })
                
                # Test connection
                self.exchange.load_markets()
                logger.info(f"Successfully connected to {exchange_id}")
                
            except Exception as e:
                logger.error(f"Failed to initialize {exchange_id}: {str(e)}")
                self.exchange = None
        
        self.fallback_yf = YFinanceDataProvider(market_type='crypto')
        self.fallback_av = AlphaVantageProvider()

    def _convert_symbol(self, symbol, target='yf'):
        """Convert symbol format for different providers"""
        if target == 'yf':
            if '/' in symbol:
                base, quote = symbol.split('/')
                return f"{base}-{quote}"
            return symbol
        elif target == 'av':
            if '/' in symbol:
                return symbol
            return symbol.replace('-', '/')
        return symbol

    def get_ohlcv(self, symbol, timeframe='1h', limit=200):
        """Enhanced OHLCV with multiple fallbacks and validation"""
        # Check cache first
        cached_data = self._get_cached_data(symbol, timeframe, limit)
        if cached_data is not None:
            return cached_data

        def fetch_ccxt_data():
            if not self.exchange:
                raise Exception("Exchange not initialized")
            
            try:
                ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
                df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                
                # Validate data
                is_valid, issues = self.validator.validate_ohlcv_data(df)
                if not is_valid:
                    logger.warning(f"CCXT data validation issues for {symbol}: {issues}")
                    df = self.validator.clean_ohlcv_data(df)
                
                return df
                
            except Exception as e:
                logger.warning(f"CCXT failed for {symbol}: {str(e)}")
                raise

        # Try CCXT first
        result = self._safe_api_call(fetch_ccxt_data)
        
        if result is not None and len(result) >= 50:
            self._set_cached_data(symbol, timeframe, limit, result)
            return result
        
        # Fallback to other providers
        fallback_providers = [
            (self.fallback_yf, 'yf'),
            (self.fallback_av, 'av')
        ]
        
        for fallback, target in fallback_providers:
            try:
                conv_symbol = self._convert_symbol(symbol, target)
                df = fallback.get_ohlcv(conv_symbol, timeframe, limit)
                
                if df is not None and len(df) >= 50:
                    logger.info(f"Using fallback {fallback.__class__.__name__} for {symbol}")
                    self._set_cached_data(symbol, timeframe, limit, df)
                    return df
                    
            except Exception as e:
                logger.warning(f"Fallback {fallback.__class__.__name__} failed: {str(e)}")
                continue
        
        # Ultimate fallback - generate dummy data
        logger.warning(f"All providers failed for {symbol}, generating dummy data")
        dates = pd.date_range(end=pd.Timestamp.now(), periods=limit, freq='D')
        dummy_data = {
            'timestamp': dates,
            'open': [1.0] * limit,
            'high': [1.1] * limit,
            'low': [0.9] * limit,
            'close': [1.0 + (i / 100) for i in range(limit)],
            'volume': [1000 + i for i in range(limit)]
        }
        result = pd.DataFrame(dummy_data)
        self._set_cached_data(symbol, timeframe, limit, result)
        return result

    def get_ticker(self, symbol):
        """Get ticker data with fallback"""
        if not self.exchange:
            # Try fallback providers
            for fallback in [self.fallback_yf, self.fallback_av]:
                try:
                    result = fallback.get_ticker(symbol)
                    if result:
                        return result
                except Exception as e:
                    logger.warning(f"Fallback ticker failed: {str(e)}")
                    continue
            return None
        
        def fetch_ticker():
            try:
                ticker = self.exchange.fetch_ticker(symbol)
                return {
                    'last': ticker.get('last'),
                    'volume': ticker.get('baseVolume', 0),
                    'high': ticker.get('high'),
                    'low': ticker.get('low'),
                    'bid': ticker.get('bid'),
                    'ask': ticker.get('ask')
                }
            except Exception as e:
                logger.error(f"CCXT ticker error: {str(e)}")
                raise
        
        return self._safe_api_call(fetch_ticker)

    def get_popular_assets(self, limit=100):
        """Get popular crypto assets from the exchange"""
        try:
            if not self.exchange:
                logger.warning(f"Exchange {self.exchange_id} not initialized, using fallback assets")
                return ['BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'XRP/USDT', 'ADA/USDT'][:limit]
            
            markets = self.exchange.load_markets()
            
            # Filter USDT pairs
            usdt_markets = [symbol for symbol in markets if symbol.endswith('/USDT')]
            
            # Exclude stablecoins and problematic pairs
            excluded_coins = ['BUSD', 'USDC', 'DAI', 'TUSD', 'USDP', 'UST', 'FDUSD']
            filtered_markets = [
                symbol for symbol in usdt_markets 
                if not any(excluded in symbol for excluded in excluded_coins)
            ]
            
            # Sort by volume if available
            try:
                tickers = self.exchange.fetch_tickers()
                filtered_markets.sort(
                    key=lambda x: tickers[x]['quoteVolume'] if x in tickers else 0, 
                    reverse=True
                )
                logger.info(f"Sorted {len(filtered_markets)} assets by volume")
            except Exception as e:
                logger.warning(f"Could not sort by volume: {str(e)}")
                # Fallback: use market cap ranking or alphabetical
                filtered_markets.sort()
            
            result = filtered_markets[:limit]
            logger.info(f"CCXT returning {len(result)} popular assets from {self.exchange_id}")
            return result
            
        except Exception as e:
            logger.error(f"Error getting popular assets from {self.exchange_id}: {str(e)}")
            # Fallback to major cryptocurrencies
            major_pairs = [
                'BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'XRP/USDT', 'ADA/USDT',
                'SOL/USDT', 'DOT/USDT', 'DOGE/USDT', 'AVAX/USDT', 'MATIC/USDT',
                'LTC/USDT', 'LINK/USDT', 'ATOM/USDT', 'XLM/USDT', 'BCH/USDT',
                'ETC/USDT', 'FIL/USDT', 'THETA/USDT', 'EOS/USDT', 'XTZ/USDT'
            ]
            return major_pairs[:limit]

class EnhancedYFinanceDataProvider(EnhancedDataProvider):
    """Enhanced Yahoo Finance provider with better error handling"""
    
    def __init__(self, market_type='stock'):
        super().__init__()
        self.market_type = market_type
        self.fallback_av = AlphaVantageProvider()

    def _convert_symbol(self, symbol, target='av'):
        """Convert symbol for different providers"""
        if target == 'av':
            if '-' in symbol:
                return symbol.replace('-', '/')
        return symbol

    def get_ohlcv(self, symbol, timeframe='1h', limit=200):
        """Enhanced Yahoo Finance with validation and fallbacks"""
        cached_data = self._get_cached_data(symbol, timeframe, limit)
        if cached_data is not None:
            return cached_data

        def fetch_yfinance_data():
            try:
                interval_map = {'1h': '1h', '4h': '4h', '1d': '1d', '1w': '1wk'}
                interval = interval_map.get(timeframe, '1d')
                
                # Determine period based on limit and interval
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
                
                # Validate data quality
                is_valid, issues = self.validator.validate_ohlcv_data(df)
                if not is_valid:
                    logger.warning(f"YFinance data validation issues for {symbol}: {issues}")
                    df = self.validator.clean_ohlcv_data(df)
                
                # Calculate quality metrics
                quality_metrics = self.validator.calculate_data_quality_metrics(df)
                if quality_metrics.overall_score < 0.7:
                    logger.warning(f"Low data quality for {symbol}: {quality_metrics}")
                
                return df
                
            except Exception as e:
                logger.error(f"YFinance error for {symbol}: {str(e)}")
                raise

        result = self._safe_api_call(fetch_yfinance_data)
        
        if result is not None:
            self._set_cached_data(symbol, timeframe, limit, result)
            return result
        
        # Fallback to Alpha Vantage
        try:
            conv_symbol = self._convert_symbol(symbol, 'av')
            av_df = self.fallback_av.get_ohlcv(conv_symbol, timeframe, limit)
            if av_df is not None:
                logger.info(f"Using AlphaVantage fallback for {symbol}")
                self._set_cached_data(symbol, timeframe, limit, av_df)
                return av_df
        except Exception as e:
            logger.warning(f"AlphaVantage fallback also failed: {str(e)}")
        
        # Generate dummy data as last resort
        logger.warning(f"All providers failed for {symbol}, generating dummy data")
        dates = pd.date_range(end=pd.Timestamp.now(), periods=limit, freq='D')
        dummy_data = {
            'timestamp': dates,
            'open': [1.0] * limit,
            'high': [1.1] * limit,
            'low': [0.9] * limit,
            'close': [1.0 + (i / 100) for i in range(limit)],
            'volume': [1000 + i for i in range(limit)]
        }
        result = pd.DataFrame(dummy_data)
        self._set_cached_data(symbol, timeframe, limit, result)
        return result

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
        
        result = self._safe_api_call(fetch_ticker)
        if result is None:
            # Try fallback
            try:
                return self.fallback_av.get_ticker(symbol)
            except Exception as e:
                logger.warning(f"AlphaVantage fallback also failed: {str(e)}")
        
        return result

    def get_popular_assets(self, limit=100):
        """Get popular assets based on market type"""
        try:
            if self.market_type == "crypto":
                return self._get_popular_crypto(limit)
            elif self.market_type == "forex":
                return self._get_popular_forex(limit)
            elif self.market_type == "saham_id":
                return self._get_popular_indonesian_stocks(limit)
            elif self.market_type == "stocks":
                return self._get_popular_international_stocks(limit)
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
            'ETC-USD', 'FIL-USD', 'THETA-USD', 'EOS-USD', 'XTZ-USD',
            'ALGO-USD', 'NEAR-USD', 'FTM-USD', 'SAND-USD', 'MANA-USD',
            'APE-USD', 'GALA-USD', 'ENJ-USD', 'CHZ-USD', 'BAT-USD'
        ]
        result = crypto_pairs[:limit]
        logger.info(f"YFinance returning {len(result)} popular crypto assets")
        return result

    def _get_popular_forex(self, limit):
        """Get popular forex pairs"""
        forex_pairs = [
            'EURUSD=X', 'USDJPY=X', 'GBPUSD=X', 'AUDUSD=X', 'USDCAD=X',
            'USDCHF=X', 'NZDUSD=X', 'EURGBP=X', 'EURJPY=X', 'GBPJPY=X',
            'AUDJPY=X', 'EURCAD=X', 'GBPCAD=X', 'AUDCAD=X', 'CADJPY=X',
            'CHFJPY=X', 'EURCHF=X', 'GBPCHF=X', 'AUDCHF=X', 'NZDJPY=X'
        ]
        result = forex_pairs[:limit]
        logger.info(f"YFinance returning {len(result)} popular forex pairs")
        return result

    def _get_popular_indonesian_stocks(self, limit):
        """Get popular Indonesian stocks"""
        id_stocks = [
            'BBCA.JK', 'BBRI.JK', 'BMRI.JK', 'BBNI.JK', 'BNGA.JK',
            'TLKM.JK', 'ASII.JK', 'UNVR.JK', 'ICBP.JK', 'INDF.JK',
            'ANTM.JK', 'ADRO.JK', 'PTBA.JK', 'ITMG.JK', 'MEDC.JK',
            'SMGR.JK', 'INTP.JK', 'TKIM.JK', 'KLBF.JK', 'GGRM.JK',
            'HMSP.JK', 'JPFA.JK', 'LSIP.JK', 'MYOR.JK', 'SCMA.JK',
            'SRIL.JK', 'TPIA.JK', 'UNTR.JK', 'WIKA.JK', 'WSKT.JK'
        ]
        result = id_stocks[:limit]
        logger.info(f"YFinance returning {len(result)} popular Indonesian stocks")
        return result

    def _get_popular_international_stocks(self, limit):
        """Get popular international stocks"""
        stocks = [
            'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA', 'META', 'NVDA', 
            'BRK-B', 'JNJ', 'JPM', 'V', 'PG', 'UNH', 'HD', 'DIS',
            'PYPL', 'NFLX', 'ADBE', 'CRM', 'CSCO', 'PEP', 'ABT', 
            'TMO', 'AVGO', 'COST', 'LLY', 'WMT', 'XOM', 'CVX', 'BAC'
        ]
        result = stocks[:limit]
        logger.info(f"YFinance returning {len(result)} popular international stocks")
        return result

    def _get_fallback_assets(self, limit):
        """Fallback assets when primary method fails"""
        fallback_assets = {
            "crypto": ['BTC-USD', 'ETH-USD', 'BNB-USD', 'XRP-USD', 'ADA-USD'],
            "forex": ['EURUSD=X', 'USDJPY=X', 'GBPUSD=X', 'AUDUSD=X', 'USDCAD=X'],
            "saham_id": ['BBCA.JK', 'BBRI.JK', 'BMRI.JK', 'TLKM.JK', 'ASII.JK'],
            "stocks": ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA']
        }
        
        assets = fallback_assets.get(self.market_type, [])
        logger.info(f"Using fallback assets for {self.market_type}: {len(assets[:limit])} assets")
        return assets[:limit]

# Update the existing classes to use enhanced versions
class CCXTDataProvider(EnhancedCCXTDataProvider):
    """Backward compatibility wrapper"""
    pass

class YFinanceDataProvider(EnhancedYFinanceDataProvider):
    """Backward compatibility wrapper"""
    pass

# Enhanced DexScreenerProvider
class EnhancedDexScreenerProvider(DataProvider):
    """Enhanced DexScreener with error handling"""
    
    def __init__(self):
        super().__init__()
        self.base_url = "https://api.dexscreener.com/latest/dex"
        self.circuit_breaker = CircuitBreaker()
        self.retry_mechanism = RetryMechanism(max_retries=2)

    def get_ticker(self, chain, token_address):
        def fetch_ticker():
            try:
                url = f"{self.base_url}/tokens/{chain}/{token_address}"
                response = requests.get(url, timeout=10)
                response.raise_for_status()
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
                logger.error(f"DexScreener error: {str(e)}")
                raise

        return self.retry_mechanism.execute_with_retry(fetch_ticker)

    def get_ohlcv(self, symbol, timeframe, limit):
        """DexScreener doesn't provide OHLCV directly, return None"""
        logger.warning("DexScreener does not support OHLCV data")
        return None

    def get_popular_assets(self, limit):
        """Get popular assets from DexScreener"""
        def fetch_popular():
            try:
                url = f"{self.base_url}/search?q=top"
                response = requests.get(url, timeout=10)
                response.raise_for_status()
                data = response.json()
                
                if 'pairs' in data:
                    return data['pairs'][:limit]
                return []
            except Exception as e:
                logger.error(f"DexScreener popular assets error: {str(e)}")
                raise
        
        return self.retry_mechanism.execute_with_retry(fetch_popular)

# Enhanced Solana provider
class EnhancedSolanaPumpFunProvider(DataProvider):
    def __init__(self, rpc_url):
        super().__init__()
        self.client = Client(rpc_url)
        self.program_id = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"
        self.dex_provider = EnhancedDexScreenerProvider()
        self.retry_mechanism = RetryMechanism()
  
    async def monitor_new_tokens(self, limit=10):
        def fetch_tokens():
            # Implementation with retry logic
            pass
            
        return await self.retry_mechanism.execute_with_retry(fetch_tokens)

    def get_ohlcv(self, symbol, timeframe, limit):
        """Solana PumpFun doesn't provide OHLCV directly"""
        logger.warning("Solana PumpFun does not support OHLCV data")
        return None

    def get_ticker(self, symbol):
        """Get ticker data for Solana token"""
        # This would need actual implementation for Solana tokens
        return None

    def get_popular_assets(self, limit):
        """Get popular Solana tokens"""
        # This would need actual implementation
        return []

# Factory for creating data providers
class DataProviderFactory:
    """Factory for creating enhanced data providers"""
    
    @staticmethod
    def create_provider(provider_type, **kwargs):
        if provider_type == "ccxt":
            return EnhancedCCXTDataProvider(**kwargs)
        elif provider_type == "yfinance":
            return EnhancedYFinanceDataProvider(**kwargs)
        elif provider_type == "alphavantage":
            return AlphaVantageProvider(**kwargs)
        elif provider_type == "dexscreener":
            return EnhancedDexScreenerProvider()
        elif provider_type == "solanapump":
            return EnhancedSolanaPumpFunProvider(**kwargs)
        else:
            raise ValueError(f"Unknown provider type: {provider_type}")

# Health monitoring for all providers
class DataProviderMonitor:
    """Monitor health of all data providers"""
    
    def __init__(self):
        self.providers = {}
        
    def register_provider(self, name, provider):
        self.providers[name] = provider
        
    def get_health_report(self):
        report = {}
        for name, provider in self.providers.items():
            try:
                report[name] = provider.get_health_metrics()
            except Exception as e:
                report[name] = {'error': str(e)}
        return report
    
    def get_overall_health_score(self):
        report = self.get_health_report()
        scores = []
        
        for metrics in report.values():
            if 'error_rate' in metrics:
                scores.append(1 - metrics['error_rate'])
            elif 'error' in metrics:
                scores.append(0)
        
        return np.mean(scores) if scores else 1.0
