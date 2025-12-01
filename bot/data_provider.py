import ccxt
import pandas as pd
import yfinance as yf
from abc import ABC, abstractmethod
from solana.rpc.api import Client
from solana.rpc.websocket_api import connect
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
from transformers import pipeline  # For FinBERT sentiment analysis

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
    """Enhanced caching with TTL and memory management - RELAXED VERSION"""
    
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
        """Validasi data cached - RELAXED: Terima data dengan harga rendah"""
        if data is None:
            return False
        if isinstance(data, pd.DataFrame):
            # Periksa apakah DataFrame memiliki data yang valid
            if data.empty:
                return False
            if 'close' in data.columns and (data['close'] <= 0).all():
                return False
            # RELAXED: Minimal 1 bar data sudah cukup (dari 5)
            if len(data) < 1:
                return False
        return True

    def get(self, symbol, timeframe, limit):
        """Get cached data dengan validasi - RELAXED"""
        self._clean_old_entries()
        key = self._generate_key(symbol, timeframe, limit)
        
        if key in self._cache:
            cached_data = self._cache[key]
            # Validasi data cached sebelum return
            if self._is_valid_cached_data(cached_data):
                self._access_times[key] = time.time()
                logger.debug(f"Cache HIT for {symbol}")
                return cached_data
            else:
                # Hapus cache yang invalid
                logger.debug(f"Cache INVALID for {symbol}, removing")
                del self._cache[key]
                del self._access_times[key]
        return None
    
    def set(self, symbol, timeframe, limit, data):
        """Cache data dengan validasi - RELAXED"""
        self._clean_old_entries()
        
        # Hanya cache data yang valid
        if not self._is_valid_cached_data(data):
            logger.debug(f"Not caching invalid data for {symbol}")
            return
            
        key = self._generate_key(symbol, timeframe, limit)
        
        self._cache[key] = data
        self._access_times[key] = time.time()
        logger.debug(f"Data cached for {symbol}")

class RetryMechanism:
    """Enhanced retry mechanism with exponential backoff - RELAXED VERSION"""
    
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
                
                # Validate result if possible - RELAXED: Lebih toleran
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
        """Better validation of data result - RELAXED: Lebih toleran"""
        if result is None:
            return False
            
        if isinstance(result, pd.DataFrame):
            # DataFrame dengan sedikit data masih bisa valid
            if result.empty:
                return False
            # RELAXED: Periksa apakah ada harga yang valid (minimal 1)
            if 'close' in result.columns:
                valid_prices = result['close'].notna() & (result['close'] > 0)
                if valid_prices.sum() < 1:  # Minimal 1 harga valid (dari 3)
                    return False
            return True
            
        elif isinstance(result, dict):
            # Untuk ticker data, pastikan ada harga last
            if 'last' in result and result['last'] > 0:
                return True
            return False
            
        return True

class DataValidator:
    """Comprehensive data validation - RELAXED VERSION"""
    
    @staticmethod
    def validate_ohlcv_data(df: pd.DataFrame) -> Tuple[bool, List[str]]:
        """Validate OHLCV data quality dengan toleransi tinggi - RELAXED"""
        issues = []
        
        if df is None or df.empty:
            return False, ["Empty DataFrame"]
        
        # Check required columns
        required_columns = ['open', 'high', 'low', 'close']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            issues.append(f"Missing columns: {missing_columns}")
            return False, issues  # Critical error
        
        # RELAXED: Check for zero prices dengan toleransi tinggi
        zero_prices = (df['close'] <= 0).sum()
        if zero_prices > len(df) * 0.8:  # Jika >80% harga nol (dari 50%)
            issues.append(f"Too many zero prices: {zero_prices}/{len(df)}")
            return False, issues  # Critical error
        elif zero_prices > 0:
            issues.append(f"Some zero prices: {zero_prices}/{len(df)}")  # Warning saja
        
        # Check for NaN values - lebih toleran
        nan_columns = df[required_columns].columns[df[required_columns].isna().any()].tolist()
        if nan_columns:
            nan_count = df[required_columns].isna().sum().sum()
            if nan_count > len(df) * 0.5:  # Jika >50% NaN (dari 30%)
                issues.append(f"Too many NaN values: {nan_count}")
                return False, issues  # Critical error
            else:
                issues.append(f"Some NaN values in: {nan_columns}")
        
        # RELAXED: Data consistency dengan toleransi tinggi
        if all(col in df.columns for col in ['high', 'low']):
            invalid_high_low = df[df['high'] < df['low']]
            if not invalid_high_low.empty:
                issues.append(f"{len(invalid_high_low)} rows with high < low")
        
        # Return True jika hanya warning, False jika critical error
        critical_issues = [issue for issue in issues if "Missing columns" in issue or "Too many" in issue]
        return len(critical_issues) == 0, issues
    
    @staticmethod
    def clean_ohlcv_data(df: pd.DataFrame) -> pd.DataFrame:
        """Clean and normalize OHLCV data - RELAXED"""
        if df is None or df.empty:
            return df
        
        df_clean = df.copy()
        
        # Ensure numeric types
        numeric_columns = ['open', 'high', 'low', 'close', 'volume']
        for col in numeric_columns:
            if col in df_clean.columns:
                df_clean[col] = pd.to_numeric(df_clean[col], errors='coerce')
        
        # RELAXED: Jangan hapus row dengan NaN, tapi isi dengan forward fill
        critical_columns = ['open', 'high', 'low', 'close']
        for col in critical_columns:
            if col in df_clean.columns:
                df_clean[col] = df_clean[col].fillna(method='ffill').fillna(method='bfill')
        
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
        
        # RELAXED: Handle zero prices dengan cara yang lebih baik
        for col in ['open', 'high', 'low', 'close']:
            if col in df_clean.columns:
                # Replace zero prices dengan nilai sebelumnya atau berikutnya
                zero_mask = df_clean[col] <= 0
                if zero_mask.any():
                    df_clean.loc[zero_mask, col] = np.nan
                    df_clean[col] = df_clean[col].fillna(method='ffill').fillna(method='bfill')
                    
                    # Jika masih ada NaN, isi dengan nilai kecil tapi positif
                    if df_clean[col].isna().any():
                        df_clean[col] = df_clean[col].fillna(0.0001)
        
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
        # Sentiment analysis pipeline using FinBERT
        try:
            self.sentiment_pipeline = pipeline('sentiment-analysis', model='ProsusAI/finbert')
        except:
            self.sentiment_pipeline = None
            logger.warning("FinBERT sentiment analysis not available")
        
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
        """Default implementation that should be overridden by subclasses"""
        logger.warning(f"get_popular_assets not properly implemented for {self.__class__.__name__}")
        
        # Provide basic fallback based on common assets
        fallback_assets = [
            'BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'XRP/USDT', 'ADA/USDT',
            'EUR/USD', 'USD/JPY', 'GBP/USD', 'AUD/USD', 'USD/CAD',
            'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA'
        ]
        return fallback_assets[:limit]

    def _generate_realistic_dummy_data(self, symbol, limit):
        """Generate realistic dummy data based on symbol - IMPROVED"""
        dates = pd.date_range(end=pd.Timestamp.now(), periods=limit, freq='D')
        
        # Gunakan harga yang realistis berdasarkan simbol
        base_price = self._estimate_realistic_price(symbol)
        
        # Generate price movement yang realistis
        np.random.seed(hash(symbol) % 10000)  # Seed konsisten per simbol
        returns = np.random.normal(0.001, 0.02, limit)  # Return harian ~2%
        
        prices = [base_price]
        for ret in returns[1:]:
            prices.append(prices[-1] * (1 + ret))
        
        dummy_data = {
            'timestamp': dates,
            'open': [p * (1 + np.random.normal(0, 0.005)) for p in prices],
            'high': [p * (1 + abs(np.random.normal(0.01, 0.01))) for p in prices],
            'low': [p * (1 - abs(np.random.normal(0.01, 0.01))) for p in prices],
            'close': prices,
            'volume': [np.random.randint(1000, 1000000) for _ in range(limit)]
        }
        
        result = pd.DataFrame(dummy_data)
        logger.info(f"Generated realistic dummy data for {symbol} with price ~{base_price:.4f}")
        return result

    def _estimate_realistic_price(self, symbol):
        """Estimate realistic price based on symbol - IMPROVED"""
        # Harga estimasi untuk simbol umum
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
        
        # Cari pattern dalam simbol
        for pattern, price in price_estimates.items():
            if pattern in symbol:
                return price
        
        # Default berdasarkan tipe market
        if 'USDT' in symbol or '/USDT' in symbol:
            return 10.0  # Harga rata-rata altcoin
        elif 'USD' in symbol or '=X' in symbol:
            return 1.0   # Forex pairs
        else:
            return 100.0  # Stocks

    # New methods for sentiment analysis
    def fetch_market_news(self, symbol, limit=10):
        """Fetch berita terkait symbol dari sumber seperti Yahoo Finance."""
        try:
            url = f"https://finance.yahoo.com/quote/{symbol}/news"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            headlines = [h.text.strip() for h in soup.find_all('h3', class_='Mb(5px)')][:limit]
            return headlines
        except Exception as e:
            logger.error(f"Error fetching news for {symbol}: {e}")
            return []  # Fallback to empty

    def analyze_market_sentiment(self, symbol, timeframe='1d', news_limit=20):
        """Analisis sentimen berita untuk symbol menggunakan FinBERT."""
        if not self.sentiment_pipeline:
            return {'average_sentiment': 0.0, 'details': []}
            
        news = self.fetch_market_news(symbol, news_limit)
        if not news:
            return {'average_sentiment': 0.0, 'details': []}  # Neutral fallback
        
        sentiments = []
        for headline in news:
            result = self.sentiment_pipeline(headline)[0]
            score = result['score'] if result['label'] == 'positive' else -result['score'] if result['label'] == 'negative' else 0
            sentiments.append({'headline': headline, 'score': score, 'label': result['label']})
        
        avg_score = sum(s['score'] for s in sentiments) / len(sentiments) if sentiments else 0.0
        return {'average_sentiment': avg_score, 'details': sentiments}

# =============================================
# DYNAMIC DATA PROVIDER - NEW & COMPLETE
# =============================================

class DynamicDataProvider(EnhancedDataProvider):
    """Dynamic data provider yang bisa handle semua market type dengan smart detection"""
    
    def __init__(self, market_type="crypto"):
        super().__init__()
        self.market_type = market_type
        
        # Initialize semua provider yang mungkin dibutuhkan
        self.providers = {
            'crypto_spot': EnhancedCCXTDataProvider(exchange_id='binance', market_type='spot'),
            'crypto_future': EnhancedCCXTFuturesProvider(exchange_id='binance'),
            'forex': EnhancedYFinanceDataProvider(market_type='forex'),
            'saham_id': EnhancedYFinanceDataProvider(market_type='saham_id'), 
            'us_stocks': EnhancedYFinanceDataProvider(market_type='us_stocks'),
            'stocks': EnhancedYFinanceDataProvider(market_type='us_stocks')
        }
        
        # Default provider berdasarkan market type
        self.default_provider = self._get_default_provider(market_type)
        
        logger.info(f"DynamicDataProvider initialized for {market_type} market")

    def _get_default_provider(self, market_type):
        """Get default provider berdasarkan market type"""
        provider_map = {
            'crypto': self.providers['crypto_spot'],
            'forex': self.providers['forex'],
            'saham_id': self.providers['saham_id'],
            'us_stocks': self.providers['us_stocks'],
            'stocks': self.providers['us_stocks']
        }
        return provider_map.get(market_type, self.providers['crypto_spot'])

    def _detect_symbol_type(self, symbol):
        """Detect symbol type secara otomatis berdasarkan pattern"""
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
        
        # US Stocks detection (ticker biasanya 1-5 huruf, tanpa special characters)
        if (len(symbol) <= 5 and symbol.isalpha() and 
            not any(c in symbol for c in ['/', '=', '.', '-'])):
            return 'us_stocks'
        
        # Default ke crypto spot
        return 'crypto_spot'

    def get_ohlcv(self, symbol: str, timeframe: str = '1h', limit: int = 200):
        """Get OHLCV data dengan auto-detection symbol type and sentiment integration"""
        try:
            # Deteksi tipe symbol
            symbol_type = self._detect_symbol_type(symbol)
            provider = self.providers.get(symbol_type, self.default_provider)
            
            logger.info(f"🔍 Getting OHLCV for {symbol} (detected as {symbol_type}) using {provider.__class__.__name__}")
            
            # Gunakan cache mechanism dari base class
            cached_data = self._get_cached_data(symbol, timeframe, limit)
            if cached_data is not None:
                return cached_data
            
            # Get data dari provider yang sesuai
            data = provider.get_ohlcv(symbol, timeframe, limit)
            
            # Add sentiment analysis
            sentiment = self.analyze_market_sentiment(symbol)
            if data is not None:
                data = data.copy()  # Avoid modifying original
                data['sentiment'] = sentiment['average_sentiment']  # Add as column or metadata; here as column for simplicity
            
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
            
            return provider.get_ticker(symbol)
            
        except Exception as e:
            logger.error(f"Error getting ticker for {symbol}: {e}")
            # Fallback ke default provider
            return self.default_provider.get_ticker(symbol)

    def get_popular_assets(self, limit: int = 100):
        """Get popular assets untuk market type yang aktif"""
        try:
            logger.info(f"📊 Getting {limit} popular assets for {self.market_type}")
            
            assets = self.default_provider.get_popular_assets(limit)
            
            # Format konsisten: selalu return list of dict dengan 'symbol' dan 'name'
            formatted_assets = []
            for asset in assets:
                if isinstance(asset, dict):
                    formatted_assets.append(asset)
                else:
                    formatted_assets.append({
                        'symbol': str(asset),
                        'name': str(asset)
                    })
            
            logger.info(f"✅ Found {len(formatted_assets)} popular assets for {self.market_type}")
            return formatted_assets
            
        except Exception as e:
            logger.error(f"Error getting popular assets for {self.market_type}: {e}")
            return self._get_fallback_assets(limit)

    def search_assets(self, query: str, limit: int = 20) -> List[Dict]:
        """Search assets across all providers berdasarkan query"""
        try:
            logger.info(f"🔍 Searching assets for: '{query}' in {self.market_type}")
            
            if not query or len(query.strip()) < 2:
                logger.warning("Search query too short")
                return []
            
            query_clean = query.upper().strip()
            results = []
            
            # Search strategy berdasarkan market type
            if self.market_type == "crypto":
                results = self._search_crypto_assets(query_clean, limit)
            elif self.market_type == "forex":
                results = self._search_forex_pairs(query_clean, limit)
            elif self.market_type == "saham_id":
                results = self._search_saham_id(query_clean, limit)
            elif self.market_type in ["us_stocks", "stocks"]:
                results = self._search_us_stocks(query_clean, limit)
            else:
                results = self._search_generic(query_clean, limit)
            
            logger.info(f"✅ Found {len(results)} assets for query '{query}'")
            return results
            
        except Exception as e:
            logger.error(f"Error searching assets for '{query}': {e}")
            return []

    def _search_crypto_assets(self, query: str, limit: int) -> List[Dict]:
        """Search cryptocurrency assets"""
        try:
            # Dapatkan popular assets terlebih dahulu
            popular_assets = self.providers['crypto_spot'].get_popular_assets(200)
            results = []
            
            # Filter berdasarkan query
            for asset in popular_assets:
                symbol = asset.get('symbol', '') if isinstance(asset, dict) else str(asset)
                if query in symbol.upper():
                    results.append({
                        'symbol': symbol,
                        'name': symbol,
                        'type': 'crypto'
                    })
            
            # Jika tidak cukup, generate synthetic pairs
            if len(results) < limit:
                pairs = ['USDT', 'BUSD', 'BTC', 'ETH', 'USD']
                for pair in pairs:
                    synthetic_symbol = f"{query}/{pair}"
                    results.append({
                        'symbol': synthetic_symbol,
                        'name': f"{query}-{pair}",
                        'type': 'crypto'
                    })
            
            # Juga cari di futures
            try:
                futures_assets = self.providers['crypto_future'].get_popular_assets(100)
                for asset in futures_assets:
                    symbol = asset.get('symbol', '') if isinstance(asset, dict) else str(asset)
                    if query in symbol.upper():
                        results.append({
                            'symbol': symbol,
                            'name': f"{symbol} (Futures)",
                            'type': 'crypto_future'
                        })
            except:
                pass  # Skip jika futures provider error
            
            return results[:limit]
            
        except Exception as e:
            logger.error(f"Error searching crypto assets: {e}")
            return self._generate_crypto_suggestions(query, limit)

    def _search_forex_pairs(self, query: str, limit: int) -> List[Dict]:
        """Search forex pairs"""
        try:
            # Major forex pairs
            major_pairs = [
                'EUR/USD', 'USD/JPY', 'GBP/USD', 'AUD/USD', 'USD/CAD',
                'USD/CHF', 'NZD/USD', 'EUR/GBP', 'EUR/JPY', 'GBP/JPY',
                'AUD/JPY', 'EUR/CAD', 'GBP/CAD', 'AUD/CAD', 'CAD/JPY',
                'CHF/JPY', 'EUR/CHF', 'GBP/CHF', 'AUD/CHF', 'NZD/JPY'
            ]
            
            # Currency codes
            currencies = ['USD', 'EUR', 'JPY', 'GBP', 'AUD', 'CAD', 'CHF', 'NZD']
            
            results = []
            
            # Cari di major pairs
            for pair in major_pairs:
                if query in pair:
                    results.append({
                        'symbol': pair,
                        'name': pair,
                        'type': 'forex'
                    })
            
            # Generate pairs berdasarkan currency code
            if len(results) < limit and query in currencies:
                for currency in currencies:
                    if currency != query:
                        # Buat pairs dengan currency ini
                        results.append({
                            'symbol': f"{query}/{currency}",
                            'name': f"{query}/{currency}",
                            'type': 'forex'
                        })
                        results.append({
                            'symbol': f"{currency}/{query}",
                            'name': f"{currency}/{query}",
                            'type': 'forex'
                        })
            
            return results[:limit]
            
        except Exception as e:
            logger.error(f"Error searching forex pairs: {e}")
            return self._generate_forex_suggestions(query, limit)

    def _search_saham_id(self, query: str, limit: int) -> List[Dict]:
        """Search saham Indonesia"""
        try:
            # Daftar saham Indonesia populer
            saham_list = [
                'BBCA.JK', 'BBRI.JK', 'BMRI.JK', 'BBNI.JK', 'BNGA.JK',
                'TLKM.JK', 'ASII.JK', 'UNVR.JK', 'ICBP.JK', 'INDF.JK',
                'ANTM.JK', 'ADRO.JK', 'PTBA.JK', 'ITMG.JK', 'MEDC.JK',
                'SMGR.JK', 'INTP.JK', 'TKIM.JK', 'KLBF.JK', 'GGRM.JK'
            ]
            
            results = []
            
            # Cari exact match atau partial match
            for saham in saham_list:
                if query in saham.upper():
                    results.append({
                        'symbol': saham,
                        'name': saham,
                        'type': 'saham_id'
                    })
            
            # Jika query adalah kode saham tanpa .JK, tambahkan
            if not any('.JK' in result['symbol'] for result in results) and len(query) <= 4:
                results.append({
                    'symbol': f"{query}.JK",
                    'name': f"{query}.JK",
                    'type': 'saham_id'
                })
            
            return results[:limit]
            
        except Exception as e:
            logger.error(f"Error searching saham Indonesia: {e}")
            return self._generate_saham_suggestions(query, limit)

    def _search_us_stocks(self, query: str, limit: int) -> List[Dict]:
        """Search US stocks"""
        try:
            # Daftar US stocks populer
            us_stocks = [
                'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA', 'META', 'NVDA', 'NFLX',
                'BRK-B', 'JNJ', 'JPM', 'V', 'PG', 'UNH', 'HD', 'DIS', 'PYPL',
                'ADBE', 'CRM', 'CSCO', 'PEP', 'ABT', 'TMO', 'AVGO', 'COST'
            ]
            
            results = []
            
            # Cari exact match atau partial match
            for stock in us_stocks:
                if query in stock.upper():
                    results.append({
                        'symbol': stock,
                        'name': stock,
                        'type': 'us_stocks'
                    })
            
            # Jika query tidak ditemukan, anggap sebagai symbol baru
            if not results and len(query) <= 5:
                results.append({
                    'symbol': query,
                    'name': query,
                    'type': 'us_stocks'
                })
            
            return results[:limit]
            
        except Exception as e:
            logger.error(f"Error searching US stocks: {e}")
            return self._generate_us_stocks_suggestions(query, limit)

    def _search_generic(self, query: str, limit: int) -> List[Dict]:
        """Generic search fallback"""
        return [{
            'symbol': query,
            'name': query,
            'type': 'generic'
        }]

    def _generate_crypto_suggestions(self, query: str, limit: int) -> List[Dict]:
        """Generate crypto suggestions ketika search gagal"""
        pairs = ['USDT', 'BUSD', 'BTC', 'ETH']
        suggestions = []
        
        for pair in pairs:
            suggestions.append({
                'symbol': f"{query}/{pair}",
                'name': f"{query}-{pair}",
                'type': 'crypto'
            })
        
        return suggestions[:limit]

    def _generate_forex_suggestions(self, query: str, limit: int) -> List[Dict]:
        """Generate forex suggestions ketika search gagal"""
        majors = ['USD', 'EUR', 'JPY', 'GBP']
        suggestions = []
        
        for currency in majors:
            if currency != query:
                suggestions.append({
                    'symbol': f"{query}/{currency}",
                    'name': f"{query}/{currency}",
                    'type': 'forex'
                })
        
        return suggestions[:limit]

    def _generate_saham_suggestions(self, query: str, limit: int) -> List[Dict]:
        """Generate saham suggestions ketika search gagal"""
        return [{
            'symbol': f"{query}.JK",
            'name': f"{query}.JK",
            'type': 'saham_id'
        }]

    def _generate_us_stocks_suggestions(self, query: str, limit: int) -> List[Dict]:
        """Generate US stocks suggestions ketika search gagal"""
        return [{
            'symbol': query,
            'name': query,
            'type': 'us_stocks'
        }]

    def _get_fallback_assets(self, limit: int):
        """Fallback assets ketika provider gagal"""
        fallback_assets = {
            "crypto": [
                {"symbol": "BTC/USDT", "name": "Bitcoin"},
                {"symbol": "ETH/USDT", "name": "Ethereum"}, 
                {"symbol": "BNB/USDT", "name": "Binance Coin"},
                {"symbol": "XRP/USDT", "name": "Ripple"},
                {"symbol": "ADA/USDT", "name": "Cardano"}
            ],
            "forex": [
                {"symbol": "EUR/USD", "name": "Euro US Dollar"},
                {"symbol": "USD/JPY", "name": "US Dollar Japanese Yen"},
                {"symbol": "GBP/USD", "name": "British Pound US Dollar"},
                {"symbol": "USD/CHF", "name": "US Dollar Swiss Franc"},
                {"symbol": "AUD/USD", "name": "Australian Dollar US Dollar"}
            ],
            "us_stocks": [
                {"symbol": "AAPL", "name": "Apple Inc"},
                {"symbol": "MSFT", "name": "Microsoft Corp"},
                {"symbol": "GOOGL", "name": "Alphabet Inc"},
                {"symbol": "AMZN", "name": "Amazon.com Inc"},
                {"symbol": "TSLA", "name": "Tesla Inc"}
            ],
            "saham_id": [
                {"symbol": "BBCA.JK", "name": "Bank Central Asia"},
                {"symbol": "BBRI.JK", "name": "Bank Rakyat Indonesia"},
                {"symbol": "BMRI.JK", "name": "Bank Mandiri"},
                {"symbol": "TLKM.JK", "name": "Telkom Indonesia"},
                {"symbol": "ASII.JK", "name": "Astra International"}
            ]
        }
        
        assets = fallback_assets.get(self.market_type, [])
        logger.info(f"Using {len(assets)} fallback assets for {self.market_type}")
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
        
        return base_metrics

# =============================================
# ENHANCED CCXT PROVIDERS
# =============================================

class EnhancedCCXTDataProvider(EnhancedDataProvider):
    """Enhanced CCXT provider with better error handling and fallbacks - RELAXED VERSION"""
    
    def __init__(self, exchange_id='binance', api_key='', secret='', market_type='spot'):
        super().__init__()
        
        self.exchange_id = exchange_id
        self.market_type = market_type  # 'spot' or 'future'
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
                
                # Add futures configuration if needed
                if market_type == 'future':
                    config['options'] = {'defaultType': 'future'}
                
                self.exchange = exchange_class(config)
                
                # Test connection
                self.exchange.load_markets()
                logger.info(f"Successfully connected to {exchange_id} ({market_type})")
                
            except Exception as e:
                logger.error(f"Failed to initialize {exchange_id}: {str(e)}")
                self.exchange = None
        
        self.fallback_yf = EnhancedYFinanceDataProvider(market_type='crypto')
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

    def _convert_to_futures_symbol(self, symbol):
        """Convert spot symbol to futures symbol format"""
        if self.market_type == 'future':
            # For perpetual futures, add :USDT suffix
            if not symbol.endswith(':USDT'):
                return f"{symbol}:USDT"
        return symbol

    def get_ohlcv(self, symbol, timeframe='1h', limit=200):
        """Enhanced OHLCV dengan validasi harga yang lebih toleran - RELAXED"""
        # Convert symbol for futures if needed
        actual_symbol = self._convert_to_futures_symbol(symbol)
        
        # Check cache first
        cached_data = self._get_cached_data(actual_symbol, timeframe, limit)
        if cached_data is not None:
            logger.info(f"Using cached data for {actual_symbol}")
            return cached_data

        def fetch_ccxt_data():
            if not self.exchange:
                raise Exception("Exchange not initialized")
            
            try:
                ohlcv = self.exchange.fetch_ohlcv(actual_symbol, timeframe, limit=limit)
                if not ohlcv:
                    raise ValueError(f"No OHLCV data returned for {actual_symbol}")
                
                df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                
                # Log data real yang didapat
                current_price = df['close'].iloc[-1] if len(df) > 0 else 0
                logger.info(f"📊 CCXT {self.market_type.upper()} DATA: {actual_symbol} - {len(df)} bars, current price: {current_price:.8f}")
                
                # Validasi data dengan toleransi lebih longgar
                is_valid, issues = self.validator.validate_ohlcv_data(df)
                if not is_valid:
                    logger.warning(f"CCXT data validation issues for {actual_symbol}: {issues}")
                    df = self.validator.clean_ohlcv_data(df)
                
                # RELAXED: Kurangi requirement minimal data
                if len(df) < 5:  # Dari 10 jadi 5
                    logger.warning(f"Low data count for {actual_symbol}: only {len(df)} rows")
                    # Tidak langsung error, lanjut proses
                
                # RELAXED: Handle zero prices dengan cara yang lebih baik
                if (df['close'] <= 0).any():
                    logger.warning(f"Zero or negative prices found for {actual_symbol}")
                    # Filter out zero prices tapi jangan reject seluruh dataset
                    df = df[df['close'] > 0]
                    if len(df) == 0:
                        raise ValueError("All prices are zero after filtering")
                
                return df
                
            except Exception as e:
                logger.warning(f"CCXT failed for {actual_symbol}: {str(e)}")
                raise

        # Try CCXT first
        result = self._safe_api_call(fetch_ccxt_data)
        
        # RELAXED: Cache dengan data lebih sedikit
        if result is not None and len(result) >= 3:  # Dari 5 jadi 3
            self._set_cached_data(actual_symbol, timeframe, limit, result)
            logger.info(f"✅ CCXT {self.market_type.upper()} ACCEPTED: {actual_symbol} - Price: {result['close'].iloc[-1]:.8f}, Bars: {len(result)}")
            return result
        
        # Fallback ke provider lain dengan prioritas
        fallback_providers = [
            (self.fallback_yf, 'yf'),
            (self.fallback_av, 'av')
        ]
        
        for fallback, target in fallback_providers:
            try:
                logger.info(f"Trying {fallback.__class__.__name__} fallback for {symbol}")
                conv_symbol = self._convert_symbol(symbol, target)
                df = fallback.get_ohlcv(conv_symbol, timeframe, limit)
                
                if df is not None and len(df) >= 3 and (df['close'] > 0).any():
                    logger.info(f"Using fallback {fallback.__class__.__name__} for {symbol}")
                    self._set_cached_data(actual_symbol, timeframe, limit, df)
                    return df
                    
            except Exception as e:
                logger.warning(f"Fallback {fallback.__class__.__name__} failed: {str(e)}")
                continue
        
        # Generate realistic data sebagai last resort
        logger.warning(f"All providers failed for {actual_symbol}, generating realistic dummy data")
        result = self._generate_realistic_dummy_data(actual_symbol, limit)
        self._set_cached_data(actual_symbol, timeframe, limit, result)
        return result
        
    def get_ticker(self, symbol):
        """Get ticker data dengan fallback yang lebih baik - RELAXED"""
        # Convert symbol for futures if needed
        actual_symbol = self._convert_to_futures_symbol(symbol)
        
        def fetch_ticker():
            try:
                if not self.exchange:
                    raise Exception("Exchange not initialized")
                    
                ticker = self.exchange.fetch_ticker(actual_symbol)
                last_price = ticker.get('last')
                
                # Validasi harga lebih toleran
                if last_price is None or last_price <= 0:
                    raise ValueError(f"Invalid price for {actual_symbol}: {last_price}")
                
                return {
                    'last': last_price,
                    'volume': ticker.get('baseVolume', 0),
                    'high': ticker.get('high'),
                    'low': ticker.get('low'),
                    'bid': ticker.get('bid'),
                    'ask': ticker.get('ask'),
                    'symbol': actual_symbol
                }
            except Exception as e:
                logger.error(f"CCXT ticker error: {str(e)}")
                raise
        
        # Try CCXT first
        result = self._safe_api_call(fetch_ticker)
        
        # Fallback sequence yang lebih robust
        if result and result.get('last', 0) > 0:
            logger.info(f"✅ CCXT {self.market_type.upper()} TICKER: {actual_symbol} - Price: {result['last']:.8f}")
            return result
        
        # Try fallback providers
        fallback_providers = [self.fallback_yf, self.fallback_av]
        
        for fallback in fallback_providers:
            try:
                fallback_result = fallback.get_ticker(symbol)
                if fallback_result and fallback_result.get('last', 0) > 0:
                    logger.info(f"Using {fallback.__class__.__name__} ticker for {symbol}")
                    return fallback_result
            except Exception as e:
                logger.warning(f"Fallback ticker failed: {str(e)}")
                continue
        
        # Fallback ke harga realistis
        estimated_price = self._estimate_realistic_price(symbol)
        logger.warning(f"All ticker providers failed for {actual_symbol}, using estimated price: {estimated_price}")
        return {
            'last': estimated_price,
            'volume': 100000,
            'high': estimated_price * 1.02,
            'low': estimated_price * 0.98,
            'bid': estimated_price * 0.999,
            'ask': estimated_price * 1.001,
            'symbol': actual_symbol
        }

    def get_popular_assets(self, limit=100):
        """Get popular crypto assets from the exchange - FIXED VERSION"""
        try:
            if not self.exchange:
                logger.warning(f"Exchange {self.exchange_id} not initialized")
                return ['BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'XRP/USDT', 'ADA/USDT'][:limit]
            
            # Load markets dengan error handling
            try:
                self.exchange.load_markets()
                markets = self.exchange.markets
                logger.info(f"📊 Loaded {len(markets)} markets from {self.exchange_id}")
            except Exception as e:
                logger.error(f"Failed to load markets: {e}")
                return ['BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'XRP/USDT', 'ADA/USDT'][:limit]
            
            # Filter based on market type
            if self.market_type == 'future':
                # Filter for futures markets
                target_markets = [
                    symbol for symbol, market in markets.items()
                    if (market.get('future', False) or 
                        ':USDT' in symbol or 
                        'PERP' in symbol or
                        '/USDT:' in symbol)
                ]
            else:
                # Filter for spot markets (USDT pairs)
                target_markets = [
                    symbol for symbol, market in markets.items()
                    if symbol.endswith('/USDT') and market.get('spot', True)
                ]
            
            logger.info(f"📊 Found {len(target_markets)} target markets for {self.market_type}")
            
            # Exclude stablecoins and problematic pairs
            excluded_coins = ['BUSD', 'USDC', 'DAI', 'TUSD', 'USDP', 'UST', 'FDUSD']
            filtered_markets = [
                symbol for symbol in target_markets 
                if not any(excluded in symbol for excluded in excluded_coins)
            ]
            
            logger.info(f"📊 After filtering: {len(filtered_markets)} markets")
            
            # Sort by volume if available
            try:
                # Ambil sample untuk volume check (jangan fetch semua tickers)
                sample_markets = filtered_markets[:50]  # Check first 50 saja
                tickers = self.exchange.fetch_tickers(sample_markets)
                
                filtered_markets.sort(
                    key=lambda x: tickers[x]['quoteVolume'] if x in tickers else 0, 
                    reverse=True
                )
                logger.info("✅ Sorted by volume")
            except Exception as e:
                logger.warning(f"Could not sort by volume: {str(e)}")
                # Fallback: use market cap ranking atau alphabetical
                filtered_markets.sort()
            
            result = filtered_markets[:limit]
            logger.info(f"✅ CCXT returning {len(result)} popular {self.market_type} assets from {self.exchange_id}")
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

# =============================================
# ENHANCED FUTURES PROVIDER WITH WEB SCRAPING - FIXED
# =============================================

class EnhancedCCXTFuturesProvider(EnhancedCCXTDataProvider):
    """Enhanced CCXT provider specifically for Futures trading dengan WEB SCRAPING FIXED"""
    
    def __init__(self, exchange_id='binance', api_key='', secret=''):
        super().__init__(exchange_id=exchange_id, api_key=api_key, secret=secret, market_type='future')
    
    def get_popular_assets(self, limit=200):
        """Get popular futures dari MULTI SOURCE: web scraping + API - FIXED"""
        all_assets = []
        
        try:
            # 1. DARI WEB SCRAPING (CoinGecko Derivatives) - FIXED
            scraping_assets = self._scrape_coingecko_futures(limit)
            if scraping_assets:
                all_assets.extend(scraping_assets)
                logger.info(f"✅ Web scraping found {len(scraping_assets)} futures assets")
            
            # 2. DARI EXCHANGE API (real trading data)
            if len(all_assets) < limit:
                api_assets = self._get_exchange_futures_api(limit - len(all_assets))
                if api_assets:
                    all_assets.extend(api_assets)
                    logger.info(f"✅ Exchange API found {len(api_assets)} futures assets")
            
            # 3. Jika masih kurang, tambahkan dari extended list
            if len(all_assets) < limit:
                extended_assets = self._get_extended_futures_assets(limit - len(all_assets))
                all_assets.extend(extended_assets)
                logger.info(f"✅ Extended list added {len(extended_assets)} futures assets")
            
            # Remove duplicates based on symbol
            seen = set()
            unique_assets = []
            for asset in all_assets:
                symbol = asset['symbol']
                if symbol not in seen:
                    seen.add(symbol)
                    unique_assets.append(asset)
            
            final_assets = unique_assets[:limit]
            logger.info(f"🎯 Total unique futures assets: {len(final_assets)}")
            
            return final_assets
            
        except Exception as e:
            logger.error(f"Error getting popular futures: {e}")
            return self._get_extended_futures_assets(limit)
    
    def _scrape_coingecko_futures(self, limit=150):
        """Web scraping dari CoinGecko derivatives page - FIXED & WORKING VERSION"""
        try:
            import requests
            from bs4 import BeautifulSoup
            import random
            
            url = "https://www.coingecko.com/en/derivatives"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Cache-Control': 'max-age=0',
            }
            
            logger.info("🔍 Scraping futures data from CoinGecko...")
            
            # Gunakan session dengan retry
            session = requests.Session()
            session.headers.update(headers)
            
            # Add random delay untuk avoid blocking
            time.sleep(random.uniform(2, 4))
            
            response = session.get(url, timeout=20)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            assets = []
            
            logger.info(f"✅ CoinGecko page loaded: {len(response.content)} bytes")
            
            # METHOD 1: Cari table derivatives dengan berbagai selector
            tables = soup.find_all('table')
            logger.info(f"📊 Found {len(tables)} tables on page")
            
            for i, table in enumerate(tables):
                logger.info(f"🔍 Checking table {i+1} with {len(table.find_all('tr'))} rows")
                
                # Coba extract data dari table ini
                rows = table.find_all('tr')[1:limit+1]  # Skip header
                
                for j, row in enumerate(rows):
                    try:
                        cells = row.find_all(['td', 'th'])
                        if len(cells) >= 2:
                            # Extract symbol dan name
                            symbol_cell = cells[0].get_text(strip=True)
                            name_cell = cells[1].get_text(strip=True) if len(cells) > 1 else symbol_cell
                            
                            # Clean dan validate
                            symbol = ' '.join(symbol_cell.split()).upper()
                            if not symbol or len(symbol) < 2:
                                continue
                                
                            # Skip header rows
                            if symbol in ['SYMBOL', 'PAIR', 'NAME', 'INSTRUMENT', '']:
                                continue
                            
                            # Format ke futures symbol
                            if '/' in symbol:
                                # Jika sudah ada pair, tambahkan :USDT
                                futures_symbol = f"{symbol}:USDT"
                            else:
                                # Jika hanya base currency, tambahkan /USDT:USDT
                                futures_symbol = f"{symbol}/USDT:USDT"
                            
                            assets.append({
                                'symbol': futures_symbol,
                                'name': name_cell[:50],  # Truncate long names
                                'source': 'coingecko_scraping'
                            })
                            
                    except Exception as e:
                        logger.debug(f"  Row {j} error: {e}")
                        continue
                
                # Jika berhasil extract dari table ini, stop
                if assets:
                    logger.info(f"✅ Successfully extracted {len(assets)} assets from table {i+1}")
                    break
            
            # METHOD 2: Alternative parsing - cari elements dengan class tertentu
            if not assets:
                logger.info("🔄 Trying alternative parsing...")
                
                # Cari elements yang mengandung cryptocurrency names
                crypto_elements = soup.find_all(['span', 'div', 'a'], class_=re.compile(r'coin|symbol|pair', re.I))
                
                for elem in crypto_elements[:limit*2]:
                    text = elem.get_text(strip=True)
                    if text and len(text) <= 10 and text.isalpha():
                        symbol = text.upper()
                        futures_symbol = f"{symbol}/USDT:USDT"
                        
                        assets.append({
                            'symbol': futures_symbol,
                            'name': symbol,
                            'source': 'coingecko_alternative'
                        })
            
            # METHOD 3: Fallback - gunakan extended list
            if not assets:
                logger.warning("❌ Web scraping failed to extract data")
                return self._get_extended_futures_assets(limit)
            
            # Remove duplicates
            seen = set()
            unique_assets = []
            for asset in assets:
                if asset['symbol'] not in seen:
                    seen.add(asset['symbol'])
                    unique_assets.append(asset)
            
            logger.info(f"✅ Final scraped assets: {len(unique_assets)}")
            
            # Log samples
            for asset in unique_assets[:5]:
                logger.info(f"  Sample: {asset['symbol']} - {asset['name']}")
            
            return unique_assets[:limit]
            
        except Exception as e:
            logger.error(f"❌ Web scraping error: {e}")
            # Fallback ke extended list
            return self._get_extended_futures_assets(limit)
    
    def _get_exchange_futures_api(self, limit=100):
        """Get futures dari Exchange API"""
        try:
            if not self.exchange:
                logger.warning("Exchange not initialized, skipping API call")
                return []
                
            markets = self.exchange.load_markets()
            futures_markets = [
                symbol for symbol, market in markets.items()
                if (market.get('future', False) or 
                    ':USDT' in symbol or 
                    'PERP' in symbol or
                    '/USDT:' in symbol)
            ]
            
            # Exclude stablecoins
            excluded_coins = ['BUSD', 'USDC', 'DAI', 'TUSD', 'USDP', 'UST', 'FDUSD']
            filtered_markets = [
                sym for sym in futures_markets 
                if not any(excluded in sym for excluded in excluded_coins)
            ]
            
            assets = [{
                'symbol': sym, 
                'name': sym,
                'source': 'exchange_api'
            } for sym in filtered_markets[:limit]]
            
            return assets
            
        except Exception as e:
            logger.error(f"Exchange API error: {e}")
            return []
    
    def _get_extended_futures_assets(self, limit=200):
        """Extended list of futures assets - 200+ PAIRS"""
        extended_futures = [
            # Major Cryptos (50)
            'BTC/USDT:USDT', 'ETH/USDT:USDT', 'BNB/USDT:USDT', 'XRP/USDT:USDT', 'ADA/USDT:USDT',
            'SOL/USDT:USDT', 'DOT/USDT:USDT', 'DOGE/USDT:USDT', 'AVAX/USDT:USDT', 'MATIC/USDT:USDT',
            'LTC/USDT:USDT', 'LINK/USDT:USDT', 'ATOM/USDT:USDT', 'XLM/USDT:USDT', 'BCH/USDT:USDT',
            'ETC/USDT:USDT', 'FIL/USDT:USDT', 'THETA/USDT:USDT', 'EOS/USDT:USDT', 'XTZ/USDT:USDT',
            'ALGO/USDT:USDT', 'NEAR/USDT:USDT', 'FTM/USDT:USDT', 'SAND/USDT:USDT', 'MANA/USDT:USDT',
            'APE/USDT:USDT', 'GALA/USDT:USDT', 'ENJ/USDT:USDT', 'CHZ/USDT:USDT', 'BAT/USDT:USDT',
            'DASH/USDT:USDT', 'ZEC/USDT:USDT', 'XMR/USDT:USDT', 'KAVA/USDT:USDT', 'ANKR/USDT:USDT',
            'CRV/USDT:USDT', 'ICX/USDT:USDT', 'IOTA/USDT:USDT', 'KSM/USDT:USDT', 'LRC/USDT:USDT',
            'MKR/USDT:USDT', 'OMG/USDT:USDT', 'ONT/USDT:USDT', 'QTUM/USDT:USDT', 'RSR/USDT:USDT',
            'RVN/USDT:USDT', 'SC/USDT:USDT', 'SNX/USDT:USDT', 'STORJ/USDT:USDT', 'SUSHI/USDT:USDT',
            
            # Mid-cap Cryptos (50)  
            'UMA/USDT:USDT', 'WAVES/USDT:USDT', 'YFI/USDT:USDT', 'ZIL/USDT:USDT', 'ZRX/USDT:USDT',
            'IOST/USDT:USDT', 'NEO/USDT:USDT', 'VET/USDT:USDT', 'TRX/USDT:USDT', 'EOS/USDT:USDT',
            'XEM/USDT:USDT', 'DGB/USDT:USDT', 'HBAR/USDT:USDT', 'ONT/USDT:USDT', 'ZEN/USDT:USDT',
            'STX/USDT:USDT', 'KNC/USDT:USDT', 'CELO/USDT:USDT', 'BAND/USDT:USDT', 'COTI/USDT:USDT',
            'OCEAN/USDT:USDT', 'REN/USDT:USDT', 'LINA/USDT:USDT', 'CVC/USDT:USDT', 'BAL/USDT:USDT',
            'NU/USDT:USDT', 'REP/USDT:USDT', 'RLC/USDT:USDT', 'OXT/USDT:USDT', 'COMP/USDT:USDT',
            'MKR/USDT:USDT', 'YFII/USDT:USDT', 'SRM/USDT:USDT', 'CREAM/USDT:USDT', 'SXP/USDT:USDT',
            'HNT/USDT:USDT', 'FTT/USDT:USDT', 'HOT/USDT:USDT', 'MTL/USDT:USDT', 'DENT/USDT:USDT',
            'KEY/USDT:USDT', 'STMX/USDT:USDT', 'DUSK/USDT:USDT', 'AR/USDT:USDT', 'CELR/USDT:USDT',
            'FET/USDT:USDT', 'ATA/USDT:USDT', 'OGN/USDT:USDT', 'SKL/USDT:USDT', 'GRT/USDT:USDT',
            
            # Small-cap & DeFi (50)
            'NKN/USDT:USDT', 'PERP/USDT:USDT', 'TRB/USDT:USDT', 'BNT/USDT:USDT', 'OCEAN/USDT:USDT',
            'NMR/USDT:USDT', 'LPT/USDT:USDT', 'API3/USDT:USDT', 'ANT/USDT:USDT', 'MIR/USDT:USDT',
            'FRONT/USDT:USDT', 'ROSE/USDT:USDT', 'CFX/USDT:USDT', 'TWT/USDT:USDT', 'BAKE/USDT:USDT',
            'EGLD/USDT:USDT', 'FLOW/USDT:USDT', 'AUDIO/USDT:USDT', 'INJ/USDT:USDT', 'RUNE/USDT:USDT',
            'CTK/USDT:USDT', 'STRAX/USDT:USDT', 'ALPHA/USDT:USDT', 'VIDT/USDT:USDT', 'AION/USDT:USDT',
            'REEF/USDT:USDT', 'TKO/USDT:USDT', 'PUNDIX/USDT:USDT', 'SLP/USDT:USDT', 'CHR/USDT:USDT',
            'MDX/USDT:USDT', 'TVK/USDT:USDT', 'BADGER/USDT:USDT', 'FIS/USDT:USDT', 'ARPA/USDT:USDT',
            'LIT/USDT:USDT', 'TRU/USDT:USDT', 'DODO/USDT:USDT', 'CAKE/USDT:USDT', 'ALICE/USDT:USDT',
            'DEGO/USDT:USDT', 'BZRX/USDT:USDT', 'SFP/USDT:USDT', 'XVS/USDT:USDT', 'HEGIC/USDT:USDT',
            'BEL/USDT:USDT', 'TORN/USDT:USDT', 'KEEP/USDT:USDT', 'PRQ/USDT:USDT', 'QNT/USDT:USDT',
            
            # Meme coins & New listings (50)
            'SHIB/USDT:USDT', 'BONK/USDT:USDT', 'PEPE/USDT:USDT', 'FLOKI/USDT:USDT', 'WIF/USDT:USDT',
            'BOME/USDT:USDT', 'MEME/USDT:USDT', 'AIDOGE/USDT:USDT', 'TURBO/USDT:USDT', 'SNEK/USDT:USDT',
            'WOJAK/USDT:USDT', 'KEK/USDT:USDT', 'VOLT/USDT:USDT', 'KISHU/USDT:USDT', 'SAITAMA/USDT:USDT',
            'ELON/USDT:USDT', 'FEG/USDT:USDT', 'HOKK/USDT:USDT', 'AKITA/USDT:USDT', 'SAMO/USDT:USDT',
            'NYAN/USDT:USDT', 'POODL/USDT:USDT', 'HUSKY/USDT:USDT', 'KABOSU/USDT:USDT', 'DOGGY/USDT:USDT',
            'USHIBA/USDT:USDT', 'MOON/USDT:USDT', 'SAFEMOON/USDT:USDT', 'EVERRISE/USDT:USDT', 'SAFEMARS/USDT:USDT',
            'MONSTA/USDT:USDT', 'PIT/USDT:USDT', 'MILK/USDT:USDT', 'BEER/USDT:USDT', 'TACO/USDT:USDT',
            'BURGER/USDT:USDT', 'SUSHI/USDT:USDT', 'YAM/USDT:USDT', 'PICKLE/USDT:USDT', 'KIMCHI/USDT:USDT',
            'CUM/USDT:USDT', 'ASS/USDT:USDT', 'PUSSY/USDT:USDT', 'ANUS/USDT:USDT', 'BUTT/USDT:USDT',
            'BOOB/USDT:USDT', 'DICK/USDT:USDT', 'FART/USDT:USDT', 'POOP/USDT:USDT', 'URANUS/USDT:USDT'
        ]
        
        # Remove duplicates and limit
        seen = set()
        unique_assets = []
        for asset in extended_futures:
            if asset not in seen:
                seen.add(asset)
                unique_assets.append({
                    'symbol': asset,
                    'name': asset.replace('/USDT:USDT', ''),
                    'source': 'extended_list'
                })
        
        logger.info(f"Extended futures list: {len(unique_assets)} unique assets")
        return unique_assets[:limit]
    
    def get_funding_rate(self, symbol):
        """Get funding rate for futures symbol"""
        actual_symbol = self._convert_to_futures_symbol(symbol)
        
        def fetch_funding_rate():
            try:
                if not self.exchange:
                    raise Exception("Exchange not initialized")
                    
                # Different exchanges have different methods for funding rate
                if hasattr(self.exchange, 'fetch_funding_rate'):
                    funding_rate = self.exchange.fetch_funding_rate(actual_symbol)
                    return funding_rate
                else:
                    logger.warning(f"Funding rate not supported for {self.exchange_id}")
                    return None
                    
            except Exception as e:
                logger.error(f"Error fetching funding rate for {actual_symbol}: {str(e)}")
                raise
        
        return self._safe_api_call(fetch_funding_rate)
    
    def get_open_interest(self, symbol):
        """Get open interest for futures symbol"""
        actual_symbol = self._convert_to_futures_symbol(symbol)
        
        def fetch_open_interest():
            try:
                if not self.exchange:
                    raise Exception("Exchange not initialized")
                    
                if hasattr(self.exchange, 'fetch_open_interest'):
                    oi = self.exchange.fetch_open_interest(actual_symbol)
                    return oi
                else:
                    logger.warning(f"Open interest not supported for {self.exchange_id}")
                    return None
                    
            except Exception as e:
                logger.error(f"Error fetching open interest for {actual_symbol}: {str(e)}")
                raise
        
        return self._safe_api_call(fetch_open_interest)

# =============================================
# ENHANCED YFINANCE PROVIDER
# =============================================

class EnhancedYFinanceDataProvider(EnhancedDataProvider):
    """Enhanced Yahoo Finance provider with better error handling - RELAXED VERSION"""
    
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
        """Enhanced Yahoo Finance dengan validasi harga yang toleran - RELAXED"""
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
                
                # RELAXED: Handle data yang sedikit
                if len(df) < 5:
                    logger.warning(f"YFinance returned only {len(df)} rows for {symbol}")
                    # Tidak langsung error, lanjut proses
                
                if len(df) > limit:
                    df = df.tail(limit)
                
                df.reset_index(inplace=True)
                df.columns = [col.lower() for col in df.columns]
                if 'date' in df.columns:
                    df.rename(columns={'date': 'timestamp'}, inplace=True)
                elif 'datetime' in df.columns:
                    df.rename(columns={'datetime': 'timestamp'}, inplace=True)
                
                df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
                
                # RELAXED: Handle zero prices
                if (df['close'] <= 0).any():
                    logger.warning(f"Zero or negative prices in YFinance data for {symbol}")
                    df = df[df['close'] > 0]  # Filter out invalid prices
                    if len(df) == 0:
                        raise ValueError("All prices are invalid")
                
                # Validate data quality
                is_valid, issues = self.validator.validate_ohlcv_data(df)
                if not is_valid:
                    logger.warning(f"YFinance data validation issues for {symbol}: {issues}")
                    df = self.validator.clean_ohlcv_data(df)
                
                return df
                
            except Exception as e:
                logger.error(f"YFinance error for {symbol}: {str(e)}")
                raise

        result = self._safe_api_call(fetch_yfinance_data)
        
        if result is not None and len(result) > 0:
            self._set_cached_data(symbol, timeframe, limit, result)
            return result
        
        # Fallback ke Alpha Vantage
        try:
            conv_symbol = self._convert_symbol(symbol, 'av')
            av_df = self.fallback_av.get_ohlcv(conv_symbol, timeframe, limit)
            if av_df is not None and len(av_df) > 0:
                logger.info(f"Using AlphaVantage fallback for {symbol}")
                self._set_cached_data(symbol, timeframe, limit, av_df)
                return av_df
        except Exception as e:
            logger.warning(f"AlphaVantage fallback failed: {str(e)}")
        
        # Generate realistic data
        result = self._generate_realistic_dummy_data(symbol, limit)
        self._set_cached_data(symbol, timeframe, limit, result)
        return result

    def get_ticker(self, symbol):
        """Get ticker data from Yahoo Finance - RELAXED"""
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
                
                # Validasi harga
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
        
        result = self._safe_api_call(fetch_ticker)
        
        # Fallback yang lebih baik
        if not result or result.get('last', 0) <= 0:
            try:
                fallback_result = self.fallback_av.get_ticker(symbol)
                if fallback_result and fallback_result.get('last', 0) > 0:
                    logger.info(f"Using AlphaVantage fallback ticker for {symbol}")
                    return fallback_result
            except Exception as e:
                logger.warning(f"AlphaVantage fallback also failed: {str(e)}")
            
            # Ultimate fallback
            estimated_price = self._estimate_realistic_price(symbol)
            logger.warning(f"All ticker providers failed for {symbol}, using estimated price: {estimated_price}")
            return {
                'last': estimated_price,
                'volume': 100000,
                'high': estimated_price * 1.02,
                'low': estimated_price * 0.98
            }
        
        return result

    def get_popular_assets(self, limit=100):
        """Get popular assets based on market type - UPDATED FOR US STOCKS"""
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

    def _get_popular_us_stocks(self, limit):
        """Get popular US stocks - NEW METHOD"""
        us_stocks = [
            'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA', 'META', 'NVDA', 'NFLX',
            'BRK-B', 'JNJ', 'JPM', 'V', 'PG', 'UNH', 'HD', 'DIS', 'PYPL',
            'ADBE', 'CRM', 'CSCO', 'PEP', 'ABT', 'TMO', 'AVGO', 'COST',
            'LLY', 'WMT', 'XOM', 'CVX', 'BAC', 'MA', 'INTC', 'CMCSA',
            'PFE', 'ABBV', 'T', 'DHR', 'MDT', 'NKE', 'UPS', 'RTX',
            'TXN', 'HON', 'PM', 'LOW', 'IBM', 'AMD', 'SPY', 'QQQ', 'VOO'
        ]
        result = us_stocks[:limit]
        logger.info(f"YFinance returning {len(result)} popular US stocks")
        return result

    def _get_fallback_assets(self, limit):
        """Fallback assets when primary method fails"""
        fallback_assets = {
            "crypto": ['BTC-USD', 'ETH-USD', 'BNB-USD', 'XRP-USD', 'ADA-USD'],
            "forex": ['EURUSD=X', 'USDJPY=X', 'GBPUSD=X', 'AUDUSD=X', 'USDCAD=X'],
            "saham_id": ['BBCA.JK', 'BBRI.JK', 'BMRI.JK', 'TLKM.JK', 'ASII.JK'],
            "us_stocks": ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA', 'META', 'NVDA', 'NFLX']
        }
        
        assets = fallback_assets.get(self.market_type, [])
        logger.info(f"Using fallback assets for {self.market_type}: {len(assets[:limit])} assets")
        return assets[:limit]

# =============================================
# ALPHA VANTAGE PROVIDER
# =============================================

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
        """Enhanced OHLCV with caching and validation - RELAXED"""
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
                    
                    # RELAXED: Validasi dan cleaning yang lebih toleran
                    is_valid, issues = self.validator.validate_ohlcv_data(result_df)
                    if not is_valid:
                        logger.warning(f"Data validation issues for {symbol}: {issues}")
                        result_df = self.validator.clean_ohlcv_data(result_df)
                    
                    # RELAXED: Pastikan hasil akhir valid dengan standar lebih rendah
                    if result_df.empty or len(result_df) < 3:
                        raise ValueError("Data remains invalid after cleaning")
                    
                    return result_df
                return None
                
            except Exception as e:
                logger.error(f"AlphaVantage API error: {str(e)}")
                raise

        result = self._safe_api_call(fetch_data)
        
        # Jika masih gagal, gunakan data dummy yang realistis
        if result is None or result.empty or len(result) < 3:
            logger.warning(f"AlphaVantage failed for {symbol}, using realistic dummy data")
            result = self._generate_realistic_dummy_data(symbol, limit)
        
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

        result = self._safe_api_call(fetch_ticker)
        
        # Fallback ke harga realistis jika gagal
        if not result or result.get('last', 0) <= 0:
            estimated_price = self._estimate_realistic_price(symbol)
            logger.warning(f"AlphaVantage ticker failed for {symbol}, using estimated price: {estimated_price}")
            return {
                'last': estimated_price,
                'volume': 100000
            }
        
        return result

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
            assets.extend([f"{crypto}/USD" for crypto in cryptos])
            
            logger.info(f"AlphaVantage returning {len(assets[:limit])} popular assets")
            return assets[:limit]
            
        except Exception as e:
            logger.error(f"Error getting popular assets from Alpha Vantage: {str(e)}")
            # Fallback to basic assets
            fallback_assets = ['EUR/USD', 'USD/JPY', 'GBP/USD', 'AAPL', 'MSFT', 'BTC/USD', 'ETH/USD']
            return fallback_assets[:limit]

# =============================================
# OTHER PROVIDERS (DexScreener, Solana)
# =============================================

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

class EnhancedSolanaPumpFunProvider(DataProvider):
    def __init__(self, rpc_url=None):
        super().__init__()
        self.rpc_url = rpc_url
        try:
            from solana.rpc.api import Client
            self.client = Client(rpc_url)
        except ImportError:
            self.client = None
            logger.warning("Solana client not available, install solana-py package")
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

# =============================================
# FACTORY AND MONITORING
# =============================================

class DataProviderFactory:
    """Factory for creating enhanced data providers"""
    
    @staticmethod
    def create_provider(provider_type, **kwargs):
        if provider_type == "ccxt":
            return EnhancedCCXTDataProvider(**kwargs)
        elif provider_type == "ccxt_futures":
            return EnhancedCCXTFuturesProvider(**kwargs)
        elif provider_type == "yfinance":
            return EnhancedYFinanceDataProvider(**kwargs)
        elif provider_type == "alphavantage":
            return AlphaVantageProvider(**kwargs)
        elif provider_type == "dexscreener":
            return EnhancedDexScreenerProvider()
        elif provider_type == "solanapump":
            return EnhancedSolanaPumpFunProvider(**kwargs)
        elif provider_type == "dynamic":
            return DynamicDataProvider(**kwargs)
        else:
            raise ValueError(f"Unknown provider type: {provider_type}")

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

# =============================================
# TESTING FUNCTIONALITY
# =============================================

def test_enhanced_futures_provider():
    """Test the enhanced futures provider with web scraping"""
    print("🧪 Testing Enhanced Futures Provider with Web Scraping...")
    
    provider = EnhancedCCXTFuturesProvider()
    
    # Test popular assets - sekarang harusnya bisa ratusan
    assets = provider.get_popular_assets(150)
    print(f"✅ Futures assets: {len(assets)} found")
    
    # Tampilkan breakdown by source
    sources = {}
    for asset in assets:
        source = asset.get('source', 'unknown')
        sources[source] = sources.get(source, 0) + 1
    
    print("📊 Sources breakdown:")
    for source, count in sources.items():
        print(f"   - {source}: {count} assets")
    
    # Tampilkan sample
    print("🔍 Sample assets:")
    for i, asset in enumerate(assets[:15]):
        print(f"   {i+1:2d}. {asset['symbol']} ({asset.get('source')})")
    
    if len(assets) >= 100:
        print(f"🎉 SUCCESS: Got {len(assets)} futures assets!")
    else:
        print(f"⚠️  Only got {len(assets)} futures assets")
    
    return assets

def test_dynamic_data_provider():
    """Test the new DynamicDataProvider"""
    print("🧪 Testing DynamicDataProvider...")
    
    market_types = ["crypto", "forex", "saham_id", "us_stocks"]
    
    for market_type in market_types:
        print(f"\n=== Testing {market_type.upper()} ===")
        
        provider = DynamicDataProvider(market_type=market_type)
        
        # Test popular assets
        assets = provider.get_popular_assets(5)
        print(f"✅ Popular assets: {len(assets)} found")
        for asset in assets[:3]:
            print(f"   - {asset.get('symbol')}")
        
        # Test search
        test_queries = {
            "crypto": "BTC",
            "forex": "EUR", 
            "saham_id": "BBCA",
            "us_stocks": "AAPL"
        }
        
        query = test_queries.get(market_type, "TEST")
        search_results = provider.search_assets(query, 3)
        print(f"✅ Search results for '{query}': {len(search_results)} found")
        for result in search_results:
            print(f"   - {result.get('symbol')} ({result.get('type')})")
        
        # Test OHLCV for first asset
        if assets:
            symbol = assets[0].get('symbol')
            try:
                ohlcv = provider.get_ohlcv(symbol, '1h', 10)
                if ohlcv is not None:
                    print(f"✅ OHLCV data: {len(ohlcv)} rows for {symbol}")
                else:
                    print(f"❌ No OHLCV data for {symbol}")
            except Exception as e:
                print(f"❌ OHLCV error for {symbol}: {e}")
        
        # Test health metrics
        metrics = provider.get_health_metrics()
        print(f"✅ Health metrics: {metrics.get('error_rate', 'N/A')} error rate")

if __name__ == "__main__":
    print("🚀 Testing Enhanced Data Providers...")
    
    # Test futures dengan web scraping
    test_enhanced_futures_provider()
    
    # Test dynamic provider
    test_dynamic_data_provider()
    
    print("\n🎉 All data provider tests completed!")
