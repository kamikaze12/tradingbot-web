import ccxt
import pandas as pd
import yfinance as yf
import numpy as np
from datetime import datetime, timedelta
import logging
from typing import Dict, List, Optional, Tuple, Any
import time

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# =============================================
# IMPORT SCRAPER MODULES (TRY-EXCEPT)
# =============================================

try:
    # Crypto scraper modules
    from bot.external_repos.Crypto_History_Scraper_BinanceApi.scraper import BinanceScraper
    BINANCE_SCRAPER_AVAILABLE = True
    logger.info("✅ BinanceScraper module imported successfully")
except ImportError as e:
    BINANCE_SCRAPER_AVAILABLE = False
    logger.warning(f"⚠️ BinanceScraper module not available: {e}")

try:
    # General crypto scraper
    from bot.external_repos.cryptocurrency_scraper.scraper import CryptoScraper
    CRYPTO_SCRAPER_AVAILABLE = True
    logger.info("✅ CryptoScraper module imported successfully")
except ImportError as e:
    CRYPTO_SCRAPER_AVAILABLE = False
    logger.warning(f"⚠️ CryptoScraper module not available: {e}")

try:
    # Indonesia stocks scraper
    from bot.external_repos.indonesia_stocks_scraper.scraper import IndonesiaStocksScraper
    ID_STOCKS_SCRAPER_AVAILABLE = True
    logger.info("✅ IndonesiaStocksScraper module imported successfully")
except ImportError as e:
    ID_STOCKS_SCRAPER_AVAILABLE = False
    logger.warning(f"⚠️ IndonesiaStocksScraper module not available: {e}")

try:
    # Forex scraper modules
    from bot.external_repos.ForexTrackerpro.tracker import ForexTracker
    FOREX_TRACKER_AVAILABLE = True
    logger.info("✅ ForexTracker module imported successfully")
except ImportError as e:
    FOREX_TRACKER_AVAILABLE = False
    logger.warning(f"⚠️ ForexTracker module not available: {e}")

try:
    from bot.external_repos.Forex_analyzer_X_scrapper.analyzer import ForexXScraper
    FOREX_X_SCRAPER_AVAILABLE = True
    logger.info("✅ ForexXScraper module imported successfully")
except ImportError as e:
    FOREX_X_SCRAPER_AVAILABLE = False
    logger.warning(f"⚠️ ForexXScraper module not available: {e}")

try:
    from bot.external_repos.ForexScraper.scraper import ForexGeneralScraper
    FOREX_GENERAL_AVAILABLE = True
    logger.info("✅ ForexGeneralScraper module imported successfully")
except ImportError as e:
    FOREX_GENERAL_AVAILABLE = False
    logger.warning(f"⚠️ ForexGeneralScraper module not available: {e}")

try:
    # Investing.com scraper
    from bot.external_repos.Investing_com_Scraper.scraper import InvestingScraper
    INVESTING_SCRAPER_AVAILABLE = True
    logger.info("✅ InvestingScraper module imported successfully")
except ImportError as e:
    INVESTING_SCRAPER_AVAILABLE = False
    logger.warning(f"⚠️ InvestingScraper module not available: {e}")

# =============================================
# BASE DATA PROVIDER
# =============================================

class EnhancedDataProvider:
    """Base class for enhanced data providers"""
    
    def __init__(self):
        self.api_calls = 0
        self.errors = 0
        self.last_success = None
        self.skip_errors = True  # Tambahkan flag untuk skip errors
        
    def _safe_api_call(self, func):
        """Safe wrapper for API calls"""
        try:
            self.api_calls += 1
            result = func()
            self.last_success = datetime.now()
            return result
        except Exception as e:
            self.errors += 1
            if self.skip_errors:
                logger.warning(f"API call failed, skipping: {e}")
                return None  # Return None untuk di-skip
            else:
                logger.error(f"API call failed: {e}")
                raise
    
    def validate_market_data(self, df: pd.DataFrame, symbol: str) -> Tuple[bool, str]:
        """Validate market data quality"""
        if df.empty:
            return False, "Empty DataFrame"
        
        # Check for NaN values
        if df.isnull().any().any():
            df = df.fillna(method='ffill').fillna(method='bfill')
            logger.warning(f"Fixed NaN values in {symbol}")
        
        # Check for zero volume
        if 'volume' in df.columns:
            zero_volume = (df['volume'] == 0).sum()
            if zero_volume > len(df) * 0.5:  # More than 50% zero volume
                return False, f"Too many zero volume bars: {zero_volume}/{len(df)}"
        
        # Check price validity
        required_cols = ['open', 'high', 'low', 'close']
        for col in required_cols:
            if col in df.columns:
                if (df[col] <= 0).any():
                    return False, f"Invalid {col} values (<=0)"
                
                # Check for unrealistic spikes (price change > 100% in one bar)
                if col == 'close' and len(df) > 1:
                    returns = df['close'].pct_change().abs()
                    if (returns > 5).any():  # >500% change
                        return False, "Unrealistic price spike detected"
        
        return True, "Data validated successfully"
    
    def validate_market_data_without_volume(self, df: pd.DataFrame, symbol: str) -> Tuple[bool, str]:
        """Validate market data TANPA cek volume (untuk YFinance)"""
        if df.empty:
            return False, "Empty DataFrame"
        
        # Check for NaN values
        if df.isnull().any().any():
            df = df.fillna(method='ffill').fillna(method='bfill')
            logger.warning(f"Fixed NaN values in {symbol}")
        
        # 🚨 SKIP VOLUME CHECK
        
        # Check price validity
        required_cols = ['open', 'high', 'low', 'close']
        for col in required_cols:
            if col in df.columns:
                if (df[col] <= 0).any():
                    return False, f"Invalid {col} values (<=0)"
                
                # Check for unrealistic spikes
                if col == 'close' and len(df) > 1:
                    returns = df['close'].pct_change().abs()
                    if (returns > 5).any():  # >500% change
                        return False, "Unrealistic price spike detected"
        
        return True, "Data validated successfully (volume check skipped)"
    
    def get_health_metrics(self) -> Dict:
        """Get provider health metrics"""
        return {
            'api_calls': self.api_calls,
            'errors': self.errors,
            'last_success': self.last_success,
            'uptime': (datetime.now() - self.last_success).total_seconds() if self.last_success else 0
        }

# =============================================
# SCRAPER DATA PROVIDERS
# =============================================

class BinanceHistoryScraperProvider(EnhancedDataProvider):
    """Binance History Scraper Provider"""
    
    def __init__(self, api_key=None, secret=None, skip_errors=True):
        super().__init__()
        self.skip_errors = skip_errors
        self.scraper = None
        
        if BINANCE_SCRAPER_AVAILABLE:
            try:
                self.scraper = BinanceScraper(api_key, secret)
                logger.info("✅ BinanceHistoryScraper initialized successfully")
            except Exception as e:
                logger.warning(f"⚠️ Failed to initialize BinanceScraper: {e}")
        else:
            logger.warning("⚠️ BinanceScraper module not available")
    
    def get_ohlcv(self, symbol: str, timeframe: str = '1h', limit: int = 200) -> Optional[pd.DataFrame]:
        """Get OHLCV data from Binance scraper"""
        if not self.scraper:
            return None
        
        def fetch_scraper_data():
            try:
                # Convert timeframe to scraper format
                timeframe_map = {
                    '1m': '1m', '5m': '5m', '15m': '15m', '30m': '30m',
                    '1h': '1h', '4h': '4h', '1d': '1d', '1w': '1w'
                }
                
                interval = timeframe_map.get(timeframe, '1h')
                
                # Fetch data from scraper
                # Assuming scraper has fetch_historical method
                data = self.scraper.fetch_historical(
                    symbol=symbol,
                    interval=interval,
                    limit=limit
                )
                
                if not data:
                    return None
                
                # Convert to DataFrame
                df = pd.DataFrame(data)
                
                # Standardize column names
                column_mapping = {
                    'time': 'timestamp',
                    'Time': 'timestamp',
                    'Open': 'open',
                    'High': 'high',
                    'Low': 'low',
                    'Close': 'close',
                    'Volume': 'volume'
                }
                
                df.rename(columns=column_mapping, inplace=True)
                
                # Ensure timestamp is datetime
                if 'timestamp' in df.columns:
                    if df['timestamp'].dtype != 'datetime64[ns]':
                        df['timestamp'] = pd.to_datetime(df['timestamp'])
                
                # Ensure required columns
                required_cols = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
                missing_cols = [col for col in required_cols if col not in df.columns]
                
                if missing_cols:
                    logger.warning(f"Missing columns in scraper data: {missing_cols}")
                    return None
                
                # Filter price 100
                if 'close' in df.columns:
                    mask_100 = abs(df['close'] - 100.0) < 0.001
                    count_100 = mask_100.sum()
                    if count_100 > 0:
                        df = df[~mask_100].copy()
                        logger.warning(f"⚠️ Removed {count_100} bars with price 100 for {symbol}")
                
                # Validate data
                is_valid, msg = self.validate_market_data(df, symbol)
                if not is_valid:
                    logger.warning(f"Scraper data invalid: {msg}")
                    return None
                
                logger.info(f"✅ BinanceScraper: {symbol} - {len(df)} bars")
                return df[required_cols]
                
            except Exception as e:
                logger.warning(f"❌ BinanceScraper error: {e}")
                return None
        
        return self._safe_api_call(fetch_scraper_data)
    
    def get_ticker(self, symbol: str) -> Optional[Dict]:
        """Get ticker from Binance scraper"""
        if not self.scraper:
            return None
        
        def fetch_ticker():
            try:
                # Assuming scraper has get_ticker method
                ticker_data = self.scraper.get_ticker(symbol)
                
                if not ticker_data:
                    return None
                
                return {
                    'last': ticker_data.get('last_price', ticker_data.get('close', 0)),
                    'volume': ticker_data.get('volume', 0),
                    'high': ticker_data.get('high', 0),
                    'low': ticker_data.get('low', 0),
                    'bid': ticker_data.get('bid', 0),
                    'ask': ticker_data.get('ask', 0),
                    'symbol': symbol,
                    'timestamp': datetime.now(),
                    'source': 'binance_scraper'
                }
            except Exception as e:
                logger.warning(f"BinanceScraper ticker error: {e}")
                return None
        
        return self._safe_api_call(fetch_ticker)

class CryptoScraperProvider(EnhancedDataProvider):
    """General Crypto Scraper Provider"""
    
    def __init__(self, skip_errors=True):
        super().__init__()
        self.skip_errors = skip_errors
        self.scraper = None
        
        if CRYPTO_SCRAPER_AVAILABLE:
            try:
                self.scraper = CryptoScraper()
                logger.info("✅ CryptoScraper initialized successfully")
            except Exception as e:
                logger.warning(f"⚠️ Failed to initialize CryptoScraper: {e}")
        else:
            logger.warning("⚠️ CryptoScraper module not available")
    
    def get_ohlcv(self, symbol: str, timeframe: str = '1h', limit: int = 200) -> Optional[pd.DataFrame]:
        """Get OHLCV data from Crypto scraper"""
        if not self.scraper:
            return None
        
        def fetch_scraper_data():
            try:
                # Fetch data from crypto scraper
                data = self.scraper.scrape_crypto_data(
                    symbol=symbol,
                    timeframe=timeframe,
                    limit=limit
                )
                
                if not data:
                    return None
                
                # Convert to DataFrame
                df = pd.DataFrame(data)
                
                # Standardize columns
                if 'Date' in df.columns:
                    df.rename(columns={'Date': 'timestamp'}, inplace=True)
                
                # Ensure timestamp
                if 'timestamp' in df.columns:
                    df['timestamp'] = pd.to_datetime(df['timestamp'])
                
                # Filter price 100
                if 'close' in df.columns:
                    mask_100 = abs(df['close'] - 100.0) < 0.001
                    count_100 = mask_100.sum()
                    if count_100 > 0:
                        df = df[~mask_100].copy()
                        logger.warning(f"⚠️ Removed {count_100} bars with price 100 for {symbol}")
                
                # Validate
                is_valid, msg = self.validate_market_data(df, symbol)
                if not is_valid:
                    return None
                
                logger.info(f"✅ CryptoScraper: {symbol} - {len(df)} bars")
                return df
                
            except Exception as e:
                logger.warning(f"CryptoScraper error: {e}")
                return None
        
        return self._safe_api_call(fetch_scraper_data)

class IndonesiaStocksScraperProvider(EnhancedDataProvider):
    """Indonesia Stocks Scraper Provider"""
    
    def __init__(self, skip_errors=True):
        super().__init__()
        self.skip_errors = skip_errors
        self.scraper = None
        
        if ID_STOCKS_SCRAPER_AVAILABLE:
            try:
                self.scraper = IndonesiaStocksScraper()
                logger.info("✅ IndonesiaStocksScraper initialized successfully")
            except Exception as e:
                logger.warning(f"⚠️ Failed to initialize IndonesiaStocksScraper: {e}")
        else:
            logger.warning("⚠️ IndonesiaStocksScraper module not available")
    
    def get_ohlcv(self, symbol: str, timeframe: str = '1d', limit: int = 100) -> Optional[pd.DataFrame]:
        """Get Indonesian stocks data"""
        if not self.scraper:
            return None
        
        def fetch_scraper_data():
            try:
                # Extract stock code (remove .JK suffix)
                stock_code = symbol.replace('.JK', '')
                
                # Fetch stock data
                data = self.scraper.get_stock_data(
                    stock_code=stock_code,
                    period='1y'  # Assuming 1 year data
                )
                
                if not data:
                    return None
                
                df = pd.DataFrame(data)
                
                # Standardize columns
                if 'Tanggal' in df.columns:
                    df.rename(columns={'Tanggal': 'timestamp'}, inplace=True)
                
                if 'timestamp' in df.columns:
                    df['timestamp'] = pd.to_datetime(df['timestamp'])
                
                # Rename Indonesian columns to English
                column_mapping = {
                    'Harga_Buka': 'open',
                    'Harga_Tertinggi': 'high',
                    'Harga_Terendah': 'low',
                    'Harga_Tutup': 'close',
                    'Volume': 'volume'
                }
                
                for id_col, en_col in column_mapping.items():
                    if id_col in df.columns and en_col not in df.columns:
                        df.rename(columns={id_col: en_col}, inplace=True)
                
                # Select only required columns
                required_cols = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
                available_cols = [col for col in required_cols if col in df.columns]
                
                if len(available_cols) < 4:  # At least need timestamp and OHLC
                    return None
                
                df = df[available_cols]
                
                # Limit rows
                if len(df) > limit:
                    df = df.tail(limit)
                
                logger.info(f"✅ IndonesiaStocksScraper: {symbol} - {len(df)} bars")
                return df
                
            except Exception as e:
                logger.warning(f"IndonesiaStocksScraper error: {e}")
                return None
        
        return self._safe_api_call(fetch_scraper_data)

class ForexScraperProvider(EnhancedDataProvider):
    """Forex Scraper Provider (combines multiple forex scrapers)"""
    
    def __init__(self, skip_errors=True):
        super().__init__()
        self.skip_errors = skip_errors
        self.scrapers = {}
        
        # Initialize available forex scrapers
        if FOREX_TRACKER_AVAILABLE:
            try:
                self.scrapers['forex_tracker'] = ForexTracker()
                logger.info("✅ ForexTracker initialized")
            except Exception as e:
                logger.warning(f"ForexTracker init error: {e}")
        
        if FOREX_X_SCRAPER_AVAILABLE:
            try:
                self.scrapers['forex_x'] = ForexXScraper()
                logger.info("✅ ForexXScraper initialized")
            except Exception as e:
                logger.warning(f"ForexXScraper init error: {e}")
        
        if FOREX_GENERAL_AVAILABLE:
            try:
                self.scrapers['forex_general'] = ForexGeneralScraper()
                logger.info("✅ ForexGeneralScraper initialized")
            except Exception as e:
                logger.warning(f"ForexGeneralScraper init error: {e}")
    
    def get_ohlcv(self, symbol: str, timeframe: str = '1h', limit: int = 200) -> Optional[pd.DataFrame]:
        """Get Forex data from available scrapers"""
        if not self.scrapers:
            return None
        
        def fetch_forex_data():
            # Try each scraper until one works
            for scraper_name, scraper in self.scrapers.items():
                try:
                    # Convert symbol format (EUR/USD to EURUSD)
                    forex_symbol = symbol.replace('/', '')
                    
                    # Try to get data
                    if scraper_name == 'forex_tracker':
                        data = scraper.get_forex_data(forex_symbol, timeframe)
                    elif scraper_name == 'forex_x':
                        data = scraper.scrape_forex(forex_symbol, 'historical')
                    elif scraper_name == 'forex_general':
                        data = scraper.get_data(forex_symbol, timeframe)
                    else:
                        continue
                    
                    if not data:
                        continue
                    
                    df = pd.DataFrame(data)
                    
                    # Standardize columns
                    if 'timestamp' not in df.columns and 'date' in df.columns:
                        df.rename(columns={'date': 'timestamp'}, inplace=True)
                    
                    if 'timestamp' in df.columns:
                        df['timestamp'] = pd.to_datetime(df['timestamp'])
                    
                    # Limit rows
                    if len(df) > limit:
                        df = df.tail(limit)
                    
                    logger.info(f"✅ ForexScraper ({scraper_name}): {symbol} - {len(df)} bars")
                    return df
                    
                except Exception as e:
                    logger.debug(f"Forex scraper {scraper_name} failed: {e}")
                    continue
            
            return None
        
        return self._safe_api_call(fetch_forex_data)

class InvestingScraperProvider(EnhancedDataProvider):
    """Investing.com Scraper Provider"""
    
    def __init__(self, skip_errors=True):
        super().__init__()
        self.skip_errors = skip_errors
        self.scraper = None
        
        if INVESTING_SCRAPER_AVAILABLE:
            try:
                self.scraper = InvestingScraper()
                logger.info("✅ InvestingScraper initialized successfully")
            except Exception as e:
                logger.warning(f"⚠️ Failed to initialize InvestingScraper: {e}")
        else:
            logger.warning("⚠️ InvestingScraper module not available")
    
    def get_ohlcv(self, symbol: str, timeframe: str = '1d', limit: int = 100) -> Optional[pd.DataFrame]:
        """Get data from Investing.com scraper"""
        if not self.scraper:
            return None
        
        def fetch_investing_data():
            try:
                # Map timeframe
                period_map = {
                    '1d': 'daily',
                    '1w': 'weekly',
                    '1M': 'monthly'
                }
                
                period = period_map.get(timeframe, 'daily')
                
                # Fetch data
                data = self.scraper.scrape_investing(
                    symbol=symbol,
                    period=period,
                    limit=limit
                )
                
                if not data:
                    return None
                
                df = pd.DataFrame(data)
                
                # Standardize columns
                if 'Date' in df.columns:
                    df.rename(columns={'Date': 'timestamp'}, inplace=True)
                
                if 'timestamp' in df.columns:
                    df['timestamp'] = pd.to_datetime(df['timestamp'])
                
                # Rename columns
                column_mapping = {
                    'Open': 'open',
                    'High': 'high',
                    'Low': 'low',
                    'Close': 'close',
                    'Volume': 'volume',
                    'Price': 'close',
                    'Vol.': 'volume'
                }
                
                for old_col, new_col in column_mapping.items():
                    if old_col in df.columns and new_col not in df.columns:
                        df.rename(columns={old_col: new_col}, inplace=True)
                
                # Filter price 100
                if 'close' in df.columns:
                    mask_100 = abs(df['close'] - 100.0) < 0.001
                    count_100 = mask_100.sum()
                    if count_100 > 0:
                        df = df[~mask_100].copy()
                        logger.warning(f"⚠️ Removed {count_100} bars with price 100 for {symbol}")
                
                logger.info(f"✅ InvestingScraper: {symbol} - {len(df)} bars")
                return df
                
            except Exception as e:
                logger.warning(f"InvestingScraper error: {e}")
                return None
        
        return self._safe_api_call(fetch_investing_data)

# =============================================
# ENHANCED CCXT DATA PROVIDER - UNIVERSAL
# =============================================

class EnhancedCCXTDataProvider(EnhancedDataProvider):
    """Enhanced CCXT provider - UNIVERSAL (tanpa pemisahan spot/future)"""
    
    def __init__(self, exchange_id='binance', api_key='', secret='', skip_errors=True, use_binance_scraper=False):
        super().__init__()
        self.skip_errors = skip_errors
        self.exchange_id = exchange_id
        self.use_binance_scraper = use_binance_scraper
        
        # Initialize scraper if requested
        if use_binance_scraper and BINANCE_SCRAPER_AVAILABLE:
            try:
                self.binance_scraper = BinanceScraper(api_key, secret)
                logger.info("✅ BinanceScraper initialized for CCXT provider")
            except Exception as e:
                logger.warning(f"⚠️ Failed to initialize BinanceScraper: {e}")
                self.binance_scraper = None
        else:
            self.binance_scraper = None
        
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
                    'timeout': 10000,
                    'options': {
                        'defaultType': 'spot',
                    }
                }
                
                self.exchange = exchange_class(config)
                
                # Load semua market tanpa filter
                try:
                    self.exchange.load_markets()
                    logger.info(f"✅ Successfully connected to {exchange_id}, loaded {len(self.exchange.markets)} markets")
                    
                except Exception as e:
                    logger.warning(f"⚠️ Could not load all markets: {e}")
                    self.exchange = None
                
            except Exception as e:
                logger.error(f"Failed to initialize {exchange_id}: {str(e)}")
                self.exchange = None
    
    def get_ohlcv(self, symbol: str, timeframe: str = '1h', limit: int = 200) -> Optional[pd.DataFrame]:
        """Get OHLCV data - UNIVERSAL, return None jika error"""
        
        # Try Binance scraper first if enabled
        if self.use_binance_scraper and self.binance_scraper:
            try:
                scraper_result = self._get_ohlcv_from_scraper(symbol, timeframe, limit)
                if scraper_result is not None:
                    return scraper_result
            except Exception as e:
                logger.debug(f"Binance scraper failed, falling back to CCXT: {e}")
        
        # Fall back to CCXT
        def fetch_ccxt_data():
            if not self.exchange:
                raise Exception(f"Exchange {self.exchange_id} not initialized")
            
            try:
                current_symbol = symbol
                # Coba fetch data
                ohlcv = self.exchange.fetch_ohlcv(current_symbol, timeframe, limit=limit)
                
                if not ohlcv:
                    # Coba dengan symbol alternatif
                    alt_symbols = self._get_alternative_symbols(current_symbol)
                    for alt_symbol in alt_symbols:
                        if alt_symbol != current_symbol:
                            try:
                                ohlcv = self.exchange.fetch_ohlcv(alt_symbol, timeframe, limit=limit)
                                if ohlcv:
                                    logger.info(f"⚠️ Using alternative symbol {alt_symbol} for {current_symbol}")
                                    current_symbol = alt_symbol
                                    break
                            except:
                                continue
                    
                    if not ohlcv:
                        logger.warning(f"❌ No data for {symbol}")
                        return None
                
                df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                
                # Validasi jumlah data minimum
                if len(df) < 10:
                    logger.warning(f"❌ Insufficient data for {symbol}: {len(df)} bars")
                    return None
                
                # 🚨 Filter harga 100 (data error)
                if 'close' in df.columns:
                    mask_100 = abs(df['close'] - 100.0) < 0.001
                    count_100 = mask_100.sum()
                    if count_100 > 0:
                        df = df[~mask_100].copy()
                        logger.warning(f"⚠️ Removed {count_100} bars with price 100 for {current_symbol}")
                
                # Validasi kualitas data
                is_valid, validation_msg = self.validate_market_data(df, current_symbol)
                if not is_valid:
                    logger.warning(f"❌ Data validation failed: {current_symbol} - {validation_msg}")
                    return None
                
                current_price = df['close'].iloc[-1] if len(df) > 0 else 0
                logger.info(f"✅ {current_symbol} - {len(df)} bars, current: {current_price:.8f}, timeframe: {timeframe}")
                
                return df
                
            except Exception as e:
                logger.warning(f"❌ CCXT failed for {symbol}: {str(e)}")
                return None

        return self._safe_api_call(fetch_ccxt_data)
    
    def _get_ohlcv_from_scraper(self, symbol: str, timeframe: str, limit: int) -> Optional[pd.DataFrame]:
        """Get OHLCV data from Binance scraper"""
        if not self.binance_scraper:
            return None
        
        try:
            # Map timeframe
            timeframe_map = {
                '1m': '1m', '5m': '5m', '15m': '15m', '30m': '30m',
                '1h': '1h', '4h': '4h', '1d': '1d', '1w': '1w'
            }
            
            interval = timeframe_map.get(timeframe, '1h')
            
            # Fetch from scraper
            data = self.binance_scraper.fetch_historical(
                symbol=symbol,
                interval=interval,
                limit=limit
            )
            
            if not data:
                return None
            
            # Convert to DataFrame
            df = pd.DataFrame(data)
            
            # Standardize columns
            if 'timestamp' not in df.columns and 'time' in df.columns:
                df.rename(columns={'time': 'timestamp'}, inplace=True)
            
            if 'timestamp' in df.columns:
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            
            # Ensure required columns
            required_cols = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
            for col in required_cols:
                if col not in df.columns:
                    # Try to find alternative column names
                    alt_names = {
                        'open': ['Open'],
                        'high': ['High'],
                        'low': ['Low'],
                        'close': ['Close', 'Last'],
                        'volume': ['Volume', 'vol']
                    }
                    
                    if col in alt_names:
                        for alt_name in alt_names[col]:
                            if alt_name in df.columns:
                                df.rename(columns={alt_name: col}, inplace=True)
                                break
            
            # Check if we have enough columns
            missing_cols = [col for col in required_cols if col not in df.columns]
            if missing_cols:
                logger.warning(f"Scraper missing columns: {missing_cols}")
                return None
            
            df = df[required_cols]
            
            # Filter price 100
            if 'close' in df.columns:
                mask_100 = abs(df['close'] - 100.0) < 0.001
                count_100 = mask_100.sum()
                if count_100 > 0:
                    df = df[~mask_100].copy()
                    logger.warning(f"⚠️ Removed {count_100} bars with price 100 from scraper for {symbol}")
            
            # Validate
            is_valid, msg = self.validate_market_data(df, symbol)
            if not is_valid:
                logger.warning(f"Scraper data invalid: {msg}")
                return None
            
            logger.info(f"✅ BinanceScraper (via CCXT): {symbol} - {len(df)} bars")
            return df
            
        except Exception as e:
            logger.warning(f"Binance scraper error: {e}")
            return None
    
    def get_ticker(self, symbol: str) -> Optional[Dict]:
        """Get ticker data - UNIVERSAL, return None jika error"""
        def fetch_ticker():
            try:
                if not self.exchange:
                    raise Exception("Exchange not initialized")
                
                current_symbol = symbol
                ticker = self.exchange.fetch_ticker(current_symbol)
                last_price = ticker.get('last')
                
                if last_price is None or last_price <= 0:
                    # Coba dengan symbol alternatif
                    alt_symbols = self._get_alternative_symbols(current_symbol)
                    for alt_symbol in alt_symbols:
                        if alt_symbol != current_symbol:
                            try:
                                ticker = self.exchange.fetch_ticker(alt_symbol)
                                last_price = ticker.get('last')
                                if last_price and last_price > 0:
                                    logger.info(f"⚠️ Using alternative symbol {alt_symbol} for ticker")
                                    current_symbol = alt_symbol
                                    break
                            except:
                                continue
                    
                    if last_price is None or last_price <= 0:
                        logger.warning(f"❌ Invalid price for {current_symbol}: {last_price}")
                        return None
                
                # 🚨 Cek harga 100
                if abs(last_price - 100.0) < 0.001:
                    logger.warning(f"❌ Suspicious price 100 for {current_symbol}")
                    return None
                
                return {
                    'last': last_price,
                    'volume': ticker.get('baseVolume', 0) or ticker.get('quoteVolume', 0),
                    'high': ticker.get('high'),
                    'low': ticker.get('low'),
                    'bid': ticker.get('bid'),
                    'ask': ticker.get('ask'),
                    'symbol': current_symbol,
                    'timestamp': datetime.now()
                }
            except Exception as e:
                logger.warning(f"❌ CCXT ticker error for {symbol}: {str(e)}")
                return None
        
        return self._safe_api_call(fetch_ticker)
    
    def get_popular_assets(self, limit: int = 100, **kwargs) -> List[Dict]:
        """Get popular assets - UNIVERSAL"""
        try:
            logger.info(f"🔄 Getting {limit} popular assets from {self.exchange_id}...")
            
            if not self.exchange:
                logger.warning(f"Exchange {self.exchange_id} not initialized")
                return []
            
            # Coba load markets
            try:
                self.exchange.load_markets()
                markets = self.exchange.markets
                logger.info(f"📊 Loaded {len(markets)} markets from {self.exchange_id}")
            except Exception as e:
                logger.error(f"Failed to load markets: {e}")
                return []
            
            # Filter untuk USDT pairs (semua jenis: spot, futures, dll)
            usdt_markets = []
            for symbol, market in markets.items():
                # Prioritaskan USDT pairs
                if any(sep in symbol for sep in ['/USDT', ':USDT', '-USDT', 'USDT']):
                    usdt_markets.append(symbol)
            
            logger.info(f"📊 Found {len(usdt_markets)} USDT markets")
            
            # Filter stablecoins yang tidak populer untuk trading
            excluded_coins = ['BUSD', 'USDC', 'DAI', 'TUSD', 'USDP', 'UST', 'FDUSD', 'PAX']
            filtered_markets = [
                symbol for symbol in usdt_markets 
                if not any(excluded in symbol for excluded in excluded_coins)
            ]
            
            # Prioritaskan major coins dulu
            major_coins = [
                'BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'XRP/USDT', 'ADA/USDT',
                'SOL/USDT', 'DOT/USDT', 'DOGE/USDT', 'AVAX/USDT', 'MATIC/USDT',
                'LTC/USDT', 'LINK/USDT', 'ATOM/USDT', 'XLM/USDT', 'BCH/USDT',
                'TRX/USDT', 'ETC/USDT', 'FIL/USDT', 'ALGO/USDT', 'VET/USDT'
            ]
            
            # Tambahkan major coins
            result_symbols = []
            for coin in major_coins:
                # Cari semua variasi dari coin
                coin_variations = [
                    coin,
                    coin.replace('/USDT', ':USDT'),
                    coin.replace('/USDT', '-USDT'),
                    f"{coin.split('/')[0]}/USDT:USDT",
                    f"{coin.split('/')[0]}-USDT"
                ]
                
                for variation in coin_variations:
                    if variation in filtered_markets and variation not in result_symbols:
                        result_symbols.append(variation)
                        break
            
            # Tambahkan yang lain sampai mencapai limit
            for symbol in filtered_markets:
                if symbol not in result_symbols and len(result_symbols) < limit:
                    result_symbols.append(symbol)
            
            # Format hasil
            result = []
            for symbol in result_symbols:
                base_name = symbol.split('/')[0] if '/' in symbol else symbol.split(':')[0].split('-')[0]
                result.append({
                    'symbol': symbol,
                    'name': base_name,
                    'exchange': self.exchange_id
                })
            
            logger.info(f"✅ Returning {len(result)} popular assets from {self.exchange_id}")
            return result[:limit]
            
        except Exception as e:
            logger.error(f"Error getting popular assets: {str(e)}")
            return []
    
    def _get_alternative_symbols(self, symbol: str) -> List[str]:
        """Get alternative symbol formats"""
        alt_symbols = [symbol]
        
        # Format asli
        if symbol:
            alt_symbols.append(symbol)
        
        # Konversi separators
        if ':USDT' in symbol:
            alt_symbols.append(symbol.replace(':USDT', '/USDT'))
            alt_symbols.append(symbol.replace(':USDT', '-USDT'))
        elif '/USDT' in symbol:
            alt_symbols.append(symbol.replace('/USDT', ':USDT'))
            alt_symbols.append(symbol.replace('/USDT', '-USDT'))
        elif '-USDT' in symbol:
            alt_symbols.append(symbol.replace('-USDT', '/USDT'))
            alt_symbols.append(symbol.replace('-USDT', ':USDT'))
        
        # Hapus duplikat
        return list(dict.fromkeys(alt_symbols))

# =============================================
# ENHANCED YFINANCE DATA PROVIDER - UNIVERSAL
# =============================================

class EnhancedYFinanceDataProvider(EnhancedDataProvider):
    """Enhanced Yahoo Finance provider - UNIVERSAL"""
    
    def __init__(self, skip_errors=True):
        super().__init__()
        self.skip_errors = skip_errors
    
    def get_ohlcv(self, symbol: str, timeframe: str = '1h', limit: int = 200) -> Optional[pd.DataFrame]:
        """Get OHLCV from Yahoo Finance - UNIVERSAL, return None jika error"""
        def fetch_yfinance_data():
            try:
                # Convert symbol ke format YFinance
                yf_symbol = self._convert_to_yfinance_symbol(symbol)
                
                # Map timeframe
                interval_map = {
                    '1m': '1m', '5m': '5m', '15m': '15m',
                    '1h': '1h', '4h': '1h',  # YFinance doesn't have 4h
                    '1d': '1d', '1w': '1wk', '1M': '1mo'
                }
                
                interval = interval_map.get(timeframe, '1d')
                
                # Tentukan period berdasarkan interval
                if interval in ['1m', '5m', '15m', '1h']:
                    period = '60d' if limit > 100 else '7d'
                elif interval == '1d':
                    period = '1y' if limit > 200 else '6mo'
                else:
                    period = '1y'
                
                ticker = yf.Ticker(yf_symbol)
                df = ticker.history(period=period, interval=interval)
                
                if df.empty:
                    logger.warning(f"❌ No data returned for {yf_symbol}")
                    return None
                
                if len(df) > limit:
                    df = df.tail(limit)
                
                df.reset_index(inplace=True)
                df.columns = [col.lower() for col in df.columns]
                
                # Standardize column names
                if 'date' in df.columns:
                    df.rename(columns={'date': 'timestamp'}, inplace=True)
                elif 'datetime' in df.columns:
                    df.rename(columns={'datetime': 'timestamp'}, inplace=True)
                
                # Ensure we have required columns
                required_cols = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
                for col in required_cols:
                    if col not in df.columns:
                        logger.warning(f"❌ Missing column {col} in data for {symbol}")
                        return None
                
                df = df[required_cols]
                
                # 🚨 Filter harga 100
                if 'close' in df.columns:
                    mask_100 = abs(df['close'] - 100.0) < 0.001
                    count_100 = mask_100.sum()
                    if count_100 > 0:
                        df = df[~mask_100].copy()
                        logger.warning(f"⚠️ Removed {count_100} bars with price 100 for {symbol}")
                
                # 🚨 DISABLE VOLUME VALIDATION UNTUK YFINANCE
                # Validasi TANPA cek volume (karena YFinance sering volume=0 untuk crypto)
                is_valid, validation_msg = self.validate_market_data_without_volume(df, symbol)
                if not is_valid:
                    logger.warning(f"❌ YFinance validation failed: {symbol} - {validation_msg}")
                    return None
                
                logger.info(f"✅ YFinance: {symbol} - {len(df)} bars")
                return df
                
            except Exception as e:
                logger.warning(f"❌ YFinance error for {symbol}: {str(e)}")
                return None

        return self._safe_api_call(fetch_yfinance_data)
    
    def get_ticker(self, symbol: str) -> Optional[Dict]:
        """Get ticker data from Yahoo Finance - UNIVERSAL, return None jika error"""
        def fetch_ticker():
            try:
                # Convert symbol
                yf_symbol = self._convert_to_yfinance_symbol(symbol)
                
                ticker = yf.Ticker(yf_symbol)
                info = ticker.info
                history = ticker.history(period='1d')
                
                if not history.empty:
                    last_price = history['Close'].iloc[-1]
                    volume = history['Volume'].iloc[-1] if 'Volume' in history.columns else 0
                    high = history['High'].iloc[-1] if 'High' in history.columns else last_price
                    low = history['Low'].iloc[-1] if 'Low' in history.columns else last_price
                else:
                    last_price = info.get('currentPrice', info.get('regularMarketPrice', 0))
                    volume = info.get('volume', 0)
                    high = info.get('dayHigh', last_price)
                    low = info.get('dayLow', last_price)
                
                if last_price <= 0:
                    logger.warning(f"❌ Invalid price for {symbol}: {last_price}")
                    return None
                
                # 🚨 Cek harga 100
                if abs(last_price - 100.0) < 0.001:
                    logger.warning(f"❌ Suspicious price 100 for {symbol}")
                    return None
                
                return {
                    'last': last_price,
                    'volume': volume,
                    'high': high,
                    'low': low,
                    'bid': info.get('bid', last_price * 0.999),
                    'ask': info.get('ask', last_price * 1.001),
                    'market_cap': info.get('marketCap', 0),
                    'symbol': symbol,
                    'timestamp': datetime.now()
                }
            except Exception as e:
                logger.warning(f"❌ YFinance ticker error for {symbol}: {str(e)}")
                return None
        
        return self._safe_api_call(fetch_ticker)
    
    def get_popular_assets(self, limit: int = 100, **kwargs) -> List[Dict]:
        """Get popular assets - UNIVERSAL"""
        try:
            # Gabungkan semua jenis aset
            all_assets = []
            
            # Crypto (prioritas)
            crypto_assets = self._get_crypto_assets(limit // 2)
            all_assets.extend(crypto_assets)
            
            # US Stocks
            stock_assets = self._get_us_stock_assets(limit // 4)
            all_assets.extend(stock_assets)
            
            # Forex
            forex_assets = self._get_forex_assets(limit // 4)
            all_assets.extend(forex_assets)
            
            # Indonesian Stocks
            id_stock_assets = self._get_id_stock_assets(limit // 4)
            all_assets.extend(id_stock_assets)
            
            # Potong sesuai limit
            result = all_assets[:limit]
            
            logger.info(f"✅ YFinance returning {len(result)} popular assets")
            return result
            
        except Exception as e:
            logger.error(f"❌ Error getting popular assets: {str(e)}")
            return []
    
    def _convert_to_yfinance_symbol(self, symbol: str) -> str:
        """Convert symbol ke format YFinance"""
        if '/USDT' in symbol:
            return symbol.replace('/USDT', '-USD')
        elif ':USDT' in symbol:
            return symbol.replace(':USDT', '-USD')
        elif '/USD' in symbol and '=X' not in symbol:
            return symbol.replace('/USD', '-USD')
        elif '/' in symbol:
            # Untuk pairs seperti EUR/USD
            return symbol.replace('/', '') + '=X'
        else:
            return symbol
    
    def _get_crypto_assets(self, limit: int) -> List[Dict]:
        """Get crypto assets"""
        crypto_pairs = [
            'BTC-USD', 'ETH-USD', 'BNB-USD', 'XRP-USD', 'ADA-USD',
            'SOL-USD', 'DOT-USD', 'DOGE-USD', 'AVAX-USD', 'MATIC-USD',
            'LTC-USD', 'LINK-USD', 'ATOM-USD', 'XLM-USD', 'BCH-USD',
            'TRX-USD', 'ETC-USD', 'FIL-USD', 'ALGO-USD', 'VET-USD'
        ]
        
        result = []
        for symbol in crypto_pairs[:limit]:
            result.append({
                'symbol': symbol,
                'name': symbol.replace('-USD', ''),
                'exchange': 'yfinance',
                'category': 'crypto'
            })
        
        return result
    
    def _get_forex_assets(self, limit: int) -> List[Dict]:
        """Get forex assets"""
        forex_pairs = [
            'EURUSD=X', 'USDJPY=X', 'GBPUSD=X', 'AUDUSD=X', 'USDCAD=X',
            'USDCHF=X', 'NZDUSD=X', 'EURGBP=X', 'EURJPY=X', 'GBPJPY=X'
        ]
        
        result = []
        for symbol in forex_pairs[:limit]:
            pair = symbol.replace('=X', '')
            result.append({
                'symbol': symbol,
                'name': pair,
                'exchange': 'yfinance',
                'category': 'forex'
            })
        
        return result
    
    def _get_us_stock_assets(self, limit: int) -> List[Dict]:
        """Get US stock assets"""
        us_stocks = [
            'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA', 'META', 'NVDA', 'NFLX',
            'JPM', 'V', 'JNJ', 'WMT', 'PG', 'MA', 'UNH', 'HD', 'DIS', 'BAC'
        ]
        
        result = []
        for symbol in us_stocks[:limit]:
            result.append({
                'symbol': symbol,
                'name': symbol,
                'exchange': 'yfinance',
                'category': 'stock'
            })
        
        return result
    
    def _get_id_stock_assets(self, limit: int) -> List[Dict]:
        """Get Indonesian stock assets"""
        id_stocks = [
            'BBCA.JK', 'BBRI.JK', 'BMRI.JK', 'BBNI.JK', 'BNGA.JK',
            'TLKM.JK', 'ASII.JK', 'UNVR.JK', 'ICBP.JK', 'INDF.JK'
        ]
        
        result = []
        for symbol in id_stocks[:limit]:
            result.append({
                'symbol': symbol,
                'name': symbol.replace('.JK', ''),
                'exchange': 'yfinance',
                'category': 'stock'
            })
        
        return result

# =============================================
# SCRAPER UNIFIED PROVIDER
# =============================================

class ScraperUnifiedProvider(EnhancedDataProvider):
    """Unified provider that uses all available scrapers"""
    
    def __init__(self, skip_errors=True):
        super().__init__()
        self.skip_errors = skip_errors
        
        # Initialize all available scrapers
        self.scrapers = []
        
        # Crypto scrapers
        if BINANCE_SCRAPER_AVAILABLE:
            try:
                self.scrapers.append(BinanceHistoryScraperProvider(skip_errors=skip_errors))
                logger.info("✅ Added BinanceHistoryScraperProvider")
            except Exception as e:
                logger.warning(f"Failed to add BinanceHistoryScraperProvider: {e}")
        
        if CRYPTO_SCRAPER_AVAILABLE:
            try:
                self.scrapers.append(CryptoScraperProvider(skip_errors=skip_errors))
                logger.info("✅ Added CryptoScraperProvider")
            except Exception as e:
                logger.warning(f"Failed to add CryptoScraperProvider: {e}")
        
        # Indonesia stocks scraper
        if ID_STOCKS_SCRAPER_AVAILABLE:
            try:
                self.scrapers.append(IndonesiaStocksScraperProvider(skip_errors=skip_errors))
                logger.info("✅ Added IndonesiaStocksScraperProvider")
            except Exception as e:
                logger.warning(f"Failed to add IndonesiaStocksScraperProvider: {e}")
        
        # Forex scrapers
        if FOREX_TRACKER_AVAILABLE or FOREX_X_SCRAPER_AVAILABLE or FOREX_GENERAL_AVAILABLE:
            try:
                self.scrapers.append(ForexScraperProvider(skip_errors=skip_errors))
                logger.info("✅ Added ForexScraperProvider")
            except Exception as e:
                logger.warning(f"Failed to add ForexScraperProvider: {e}")
        
        # Investing.com scraper
        if INVESTING_SCRAPER_AVAILABLE:
            try:
                self.scrapers.append(InvestingScraperProvider(skip_errors=skip_errors))
                logger.info("✅ Added InvestingScraperProvider")
            except Exception as e:
                logger.warning(f"Failed to add InvestingScraperProvider: {e}")
        
        logger.info(f"✅ ScraperUnifiedProvider initialized with {len(self.scrapers)} scrapers")
    
    def get_ohlcv(self, symbol: str, timeframe: str = '1h', limit: int = 200) -> Optional[pd.DataFrame]:
        """Try all scrapers sequentially"""
        if not self.scrapers:
            logger.warning("No scrapers available")
            return None
        
        for scraper in self.scrapers:
            try:
                data = scraper.get_ohlcv(symbol, timeframe, limit)
                if data is not None and not data.empty and len(data) >= 10:
                    logger.info(f"✅ ScraperUnified: Got data from {scraper.__class__.__name__}")
                    return data
            except Exception as e:
                logger.debug(f"Scraper {scraper.__class__.__name__} failed: {e}")
                continue
        
        logger.warning(f"❌ All scrapers failed for {symbol}")
        return None
    
    def get_ticker(self, symbol: str) -> Optional[Dict]:
        """Get ticker from any scraper"""
        for scraper in self.scrapers:
            try:
                ticker = scraper.get_ticker(symbol)
                if ticker:
                    return ticker
            except Exception as e:
                logger.debug(f"Scraper ticker failed: {e}")
                continue
        
        return None

# =============================================
# SUPER UNIFIED DATA PROVIDER - WITH ALL SOURCES
# =============================================

class SuperUnifiedDataProvider(EnhancedDataProvider):
    """Super provider with CCXT, YFinance, and all scrapers"""
    
    def __init__(self, exchange_id='binance', api_key='', secret='', skip_errors=True):
        super().__init__()
        self.skip_errors = skip_errors
        self.exchange_id = exchange_id
        
        # Setup all providers in priority order
        self.providers = []
        
        # 1. Primary: CCXT with scraper fallback
        try:
            self.providers.append(EnhancedCCXTDataProvider(
                exchange_id=exchange_id,
                api_key=api_key,
                secret=secret,
                skip_errors=skip_errors,
                use_binance_scraper=True
            ))
            logger.info("✅ Added EnhancedCCXTDataProvider (with scraper)")
        except Exception as e:
            logger.warning(f"Failed to add CCXT provider: {e}")
        
        # 2. Secondary: YFinance
        try:
            self.providers.append(EnhancedYFinanceDataProvider(skip_errors=skip_errors))
            logger.info("✅ Added EnhancedYFinanceDataProvider")
        except Exception as e:
            logger.warning(f"Failed to add YFinance provider: {e}")
        
        # 3. Tertiary: Scraper unified
        try:
            self.providers.append(ScraperUnifiedProvider(skip_errors=skip_errors))
            logger.info("✅ Added ScraperUnifiedProvider")
        except Exception as e:
            logger.warning(f"Failed to add ScraperUnifiedProvider: {e}")
        
        logger.info(f"🚀 SuperUnifiedDataProvider ready with {len(self.providers)} providers")
    
    def get_ohlcv(self, symbol: str, timeframe: str = '1h', limit: int = 200) -> Optional[pd.DataFrame]:
        """Try all providers sequentially"""
        for i, provider in enumerate(self.providers):
            try:
                logger.debug(f"Trying provider {i+1}/{len(self.providers)}: {provider.__class__.__name__}")
                data = provider.get_ohlcv(symbol, timeframe, limit)
                
                if data is not None and not data.empty and len(data) >= 10:
                    # Filter price 100
                    if 'close' in data.columns:
                        mask_100 = abs(data['close'] - 100.0) < 0.001
                        count_100 = mask_100.sum()
                        if count_100 > 0:
                            data = data[~mask_100].copy()
                            logger.warning(f"🚨 Removed {count_100} bars with price 100 for {symbol}")
                    
                    # Validate
                    is_valid, msg = self.validate_market_data(data, symbol)
                    if is_valid:
                        logger.info(f"✅ SuperUnified: Got data from {provider.__class__.__name__} ({len(data)} bars)")
                        return data
                    else:
                        logger.warning(f"Provider {i+1} data invalid: {msg}")
                
            except Exception as e:
                logger.debug(f"Provider {i+1} failed: {e}")
                continue
        
        logger.warning(f"❌ ALL PROVIDERS FAILED for {symbol}")
        return None
    
    def get_ticker(self, symbol: str) -> Optional[Dict]:
        """Get ticker from any provider"""
        for provider in self.providers:
            try:
                ticker = provider.get_ticker(symbol)
                if ticker and ticker.get('last', 0) > 0:
                    return ticker
            except Exception as e:
                logger.debug(f"Provider ticker failed: {e}")
                continue
        
        return None
    
    def get_popular_assets(self, limit: int = 100, **kwargs) -> List[Dict]:
        """Get popular assets from all providers"""
        all_assets = []
        
        for provider in self.providers:
            try:
                assets = provider.get_popular_assets(limit, **kwargs)
                if assets:
                    # Add provider info
                    for asset in assets:
                        asset['provider'] = provider.__class__.__name__
                    all_assets.extend(assets)
                    
                    # Stop if we have enough
                    if len(all_assets) >= limit:
                        break
            except Exception as e:
                logger.debug(f"Provider assets failed: {e}")
                continue
        
        # Remove duplicates (by symbol)
        seen_symbols = set()
        unique_assets = []
        
        for asset in all_assets:
            if asset['symbol'] not in seen_symbols:
                seen_symbols.add(asset['symbol'])
                unique_assets.append(asset)
        
        return unique_assets[:limit]

# =============================================
# DATA PROVIDER FACTORY (UPDATED)
# =============================================

class DataProviderFactory:
    """Factory untuk membuat data provider"""
    
    @staticmethod
    def create_provider(provider_type: str, **kwargs):
        """Create data provider berdasarkan type"""
        
        if provider_type == 'super_unified':
            # 🆕 SUPER UNIFIED (REKOMENDASI UTAMA)
            exchange_id = kwargs.get('exchange_id', 'binance')
            api_key = kwargs.get('api_key', '')
            secret = kwargs.get('secret', '')
            skip_errors = kwargs.get('skip_errors', True)
            return SuperUnifiedDataProvider(
                exchange_id=exchange_id,
                api_key=api_key,
                secret=secret,
                skip_errors=skip_errors
            )
            
        elif provider_type == 'universal':
            # Universal (existing)
            exchange_id = kwargs.get('exchange_id', 'binance')
            api_key = kwargs.get('api_key', '')
            secret = kwargs.get('secret', '')
            skip_errors = kwargs.get('skip_errors', True)
            return UnifiedDataProvider(
                exchange_id=exchange_id,
                api_key=api_key,
                secret=secret,
                skip_errors=skip_errors
            )
            
        elif provider_type == 'smart_chain':
            # SMART CHAIN PROVIDER (NO DUMMY DATA)
            market_type = kwargs.get('market_type', 'crypto')
            primary_mirror = kwargs.get('primary_mirror', 'binanceus')
            skip_errors = kwargs.get('skip_errors', True)
            
            return SmartChainDataProvider(
                primary_mirror=primary_mirror,
                market_type=market_type,
                skip_errors=skip_errors
            )
            
        elif provider_type == 'ccxt':
            # CCXT Universal
            exchange_id = kwargs.get('exchange_id', 'binance')
            api_key = kwargs.get('api_key', '')
            secret = kwargs.get('secret', '')
            skip_errors = kwargs.get('skip_errors', True)
            use_scraper = kwargs.get('use_binance_scraper', False)
            
            return EnhancedCCXTDataProvider(
                exchange_id=exchange_id,
                api_key=api_key,
                secret=secret,
                skip_errors=skip_errors,
                use_binance_scraper=use_scraper
            )
                
        elif provider_type == 'yfinance':
            # YFinance Universal
            skip_errors = kwargs.get('skip_errors', True)
            return EnhancedYFinanceDataProvider(skip_errors=skip_errors)
            
        elif provider_type == 'scraper_unified':
            # 🆕 Scraper Unified Provider
            skip_errors = kwargs.get('skip_errors', True)
            return ScraperUnifiedProvider(skip_errors=skip_errors)
            
        elif provider_type == 'binance_scraper':
            # 🆕 Binance Scraper only
            api_key = kwargs.get('api_key', '')
            secret = kwargs.get('secret', '')
            skip_errors = kwargs.get('skip_errors', True)
            return BinanceHistoryScraperProvider(
                api_key=api_key,
                secret=secret,
                skip_errors=skip_errors
            )
            
        elif provider_type == 'forex_scraper':
            # 🆕 Forex Scraper only
            skip_errors = kwargs.get('skip_errors', True)
            return ForexScraperProvider(skip_errors=skip_errors)
            
        elif provider_type == 'investing_scraper':
            # 🆕 Investing.com Scraper only
            skip_errors = kwargs.get('skip_errors', True)
            return InvestingScraperProvider(skip_errors=skip_errors)
            
        elif provider_type == 'id_stocks_scraper':
            # 🆕 Indonesia Stocks Scraper only
            skip_errors = kwargs.get('skip_errors', True)
            return IndonesiaStocksScraperProvider(skip_errors=skip_errors)
            
        else:
            raise ValueError(f"Unknown provider type: {provider_type}")

# =============================================
# BATCH DATA FETCHER - ENHANCED WITH SCRAPERS
# =============================================

class BatchDataFetcher:
    """Batch fetcher untuk multiple koin dengan skip error"""
    
    def __init__(self, provider=None, provider_type='super_unified', **kwargs):
        if provider:
            self.provider = provider
        else:
            self.provider = DataProviderFactory.create_provider(provider_type, **kwargs)
        
        # Initialize scraper fallback
        self.scraper_fallback = None
        if provider_type != 'scraper_unified' and provider_type != 'super_unified':
            try:
                self.scraper_fallback = ScraperUnifiedProvider(skip_errors=True)
            except Exception as e:
                logger.warning(f"Could not initialize scraper fallback: {e}")
        
        logger.info(f"BatchDataFetcher initialized with {provider_type}")
    
    def fetch_multiple_ohlcv(self, symbols: List[str], timeframe: str = '1h', 
                           limit: int = 100, min_bars: int = 10, 
                           use_scraper_fallback: bool = True) -> Dict[str, pd.DataFrame]:
        """
        Fetch OHLCV data untuk multiple symbols, skip yang error
        
        Returns:
            Dict dengan symbol sebagai key dan DataFrame sebagai value
        """
        results = {}
        
        for symbol in symbols:
            try:
                logger.info(f"🔄 Fetching {symbol}...")
                data = self.provider.get_ohlcv(symbol, timeframe, limit)
                
                # Try scraper fallback if enabled and main provider failed
                if (data is None or data.empty or len(data) < min_bars) and use_scraper_fallback and self.scraper_fallback:
                    logger.info(f"🔄 Trying scraper fallback for {symbol}...")
                    data = self.scraper_fallback.get_ohlcv(symbol, timeframe, limit)
                
                if data is not None and not data.empty and len(data) >= min_bars:
                    results[symbol] = data
                    logger.info(f"✅ {symbol}: {len(data)} bars")
                else:
                    logger.warning(f"❌ Skipping {symbol}: insufficient data")
                    
            except Exception as e:
                logger.warning(f"❌ Skipping {symbol}: {e}")
                continue
        
        logger.info(f"✅ Batch fetch complete: {len(results)}/{len(symbols)} symbols successful")
        return results
    
    def fetch_multiple_tickers(self, symbols: List[str], use_scraper_fallback: bool = True) -> Dict[str, Dict]:
        """
        Fetch ticker data untuk multiple symbols, skip yang error
        """
        results = {}
        
        for symbol in symbols:
            try:
                ticker = self.provider.get_ticker(symbol)
                
                # Try scraper fallback
                if (not ticker or ticker.get('last', 0) <= 0) and use_scraper_fallback and self.scraper_fallback:
                    ticker = self.scraper_fallback.get_ticker(symbol)
                
                if ticker and ticker.get('last', 0) > 0:
                    results[symbol] = ticker
                    logger.info(f"✅ {symbol}: ${ticker['last']:.2f}")
                else:
                    logger.warning(f"❌ Skipping {symbol}: invalid ticker")
                    
            except Exception as e:
                logger.warning(f"❌ Skipping {symbol}: {e}")
                continue
        
        logger.info(f"✅ Batch ticker fetch complete: {len(results)}/{len(symbols)} symbols successful")
        return results

# =============================================
# TEST FUNCTIONS - UPDATED WITH SCRAPERS
# =============================================

def test_scraper_providers():
    """Test scraper providers"""
    print("\n" + "="*60)
    print("🧪 TESTING SCRAPER DATA PROVIDERS")
    print("="*60)
    
    # Test scraper availability
    print(f"\n📊 Scraper Availability:")
    print(f"  Binance Scraper: {'✅' if BINANCE_SCRAPER_AVAILABLE else '❌'}")
    print(f"  Crypto Scraper: {'✅' if CRYPTO_SCRAPER_AVAILABLE else '❌'}")
    print(f"  Indonesia Stocks Scraper: {'✅' if ID_STOCKS_SCRAPER_AVAILABLE else '❌'}")
    print(f"  Forex Tracker: {'✅' if FOREX_TRACKER_AVAILABLE else '❌'}")
    print(f"  Forex X Scraper: {'✅' if FOREX_X_SCRAPER_AVAILABLE else '❌'}")
    print(f"  Forex General: {'✅' if FOREX_GENERAL_AVAILABLE else '❌'}")
    print(f"  Investing Scraper: {'✅' if INVESTING_SCRAPER_AVAILABLE else '❌'}")
    
    # Test Scraper Unified Provider
    print("\n1️⃣ Testing ScraperUnifiedProvider:")
    try:
        scraper_provider = ScraperUnifiedProvider(skip_errors=True)
        
        # Test different asset types
        test_symbols = [
            ('BTC/USDT', 'crypto'),
            ('BBCA.JK', 'indonesia_stock'),
            ('EUR/USD', 'forex'),
            ('AAPL', 'us_stock')
        ]
        
        for symbol, asset_type in test_symbols:
            data = scraper_provider.get_ohlcv(symbol, '1d', 10)
            if data is not None:
                print(f"✅ {asset_type} ({symbol}): {len(data)} bars")
            else:
                print(f"⚠️ {asset_type} ({symbol}): No data from scrapers")
        
    except Exception as e:
        print(f"❌ ScraperUnifiedProvider error: {e}")
    
    # Test Super Unified Provider
    print("\n2️⃣ Testing SuperUnifiedDataProvider:")
    try:
        super_provider = SuperUnifiedDataProvider(exchange_id='binance', skip_errors=True)
        
        # Test OHLCV
        data = super_provider.get_ohlcv("BTC/USDT", '1h', 20)
        if data is not None:
            print(f"✅ SuperUnified BTC: {len(data)} bars")
            if len(data) > 0:
                print(f"   Latest: {data['close'].iloc[-1]:.2f}")
        else:
            print("⚠️ No BTC data from SuperUnified")
        
        # Test popular assets
        assets = super_provider.get_popular_assets(5)
        if assets:
            print(f"✅ SuperUnified assets: {len(assets)} found")
            for asset in assets[:3]:
                print(f"   - {asset['symbol']} via {asset.get('provider', 'unknown')}")
        
    except Exception as e:
        print(f"❌ SuperUnifiedProvider error: {e}")
    
    # Test Batch Fetcher with scraper fallback
    print("\n3️⃣ Testing BatchDataFetcher with scraper fallback:")
    try:
        batch_fetcher = BatchDataFetcher(provider_type='ccxt')
        
        symbols = ["BTC/USDT", "ETH/USDT", "INVALID/SYMBOL", "BBCA.JK", "EUR/USD"]
        results = batch_fetcher.fetch_multiple_ohlcv(
            symbols, '1d', 10, 
            use_scraper_fallback=True
        )
        
        print(f"✅ Batch fetch with scraper fallback: {len(results)}/{len(symbols)} successful")
        for symbol, data in results.items():
            print(f"   - {symbol}: {len(data)} bars")
        
    except Exception as e:
        print(f"❌ Batch fetcher error: {e}")

def test_all_providers():
    """Test semua provider types"""
    print("\n" + "="*60)
    print("🧪 TESTING ALL PROVIDER TYPES")
    print("="*60)
    
    provider_types = [
        'super_unified',
        'universal',
        'smart_chain',
        'ccxt',
        'yfinance',
        'scraper_unified'
    ]
    
    for provider_type in provider_types:
        print(f"\n🔧 Testing {provider_type} provider:")
        try:
            provider = DataProviderFactory.create_provider(provider_type, skip_errors=True)
            
            # Test basic functionality
            data = provider.get_ohlcv("BTC/USDT", '1h', 10)
            if data is not None and not data.empty:
                print(f"✅ {provider_type}: {len(data)} bars for BTC/USDT")
            else:
                print(f"⚠️ {provider_type}: No BTC data")
                
        except Exception as e:
            print(f"❌ {provider_type} error: {e}")

if __name__ == "__main__":
    print("\n" + "="*60)
    print("ENHANCED DATA PROVIDER TEST SUITE (WITH SCRAPERS)")
    print("="*60)
    
    # Run scraper tests
    test_scraper_providers()
    
    # Run all provider tests
    test_all_providers()
    
    print("\n" + "="*60)
    print("✅ TESTS COMPLETED - SCRAPERS INTEGRATED")
    print("="*60)
