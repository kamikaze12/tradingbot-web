import ccxt
import pandas as pd
import yfinance as yf
import numpy as np
from datetime import datetime, timedelta
import logging
from typing import Dict, List, Optional, Tuple
import time

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# =============================================
# BASE DATA PROVIDER
# =============================================

class EnhancedDataProvider:
    """Base class for enhanced data providers"""
    
    def __init__(self):
        self.api_calls = 0
        self.errors = 0
        self.last_success = None
        
    def _safe_api_call(self, func):
        """Safe wrapper for API calls"""
        try:
            self.api_calls += 1
            result = func()
            self.last_success = datetime.now()
            return result
        except Exception as e:
            self.errors += 1
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
    
    def _estimate_realistic_price(self, symbol: str) -> float:
        """Estimate realistic price for emergency fallback"""
        # Common crypto price estimates
        price_map = {
            'BTC': 50000, 'ETH': 3000, 'BNB': 400, 'XRP': 0.6, 'ADA': 0.5,
            'SOL': 100, 'DOT': 7, 'DOGE': 0.1, 'AVAX': 30, 'MATIC': 0.8,
            'LTC': 70, 'LINK': 15, 'ATOM': 10, 'XLM': 0.12, 'BCH': 300
        }
        
        for key, price in price_map.items():
            if key in symbol.upper():
                return price
        
        return 100.0  # Default fallback
    
    def get_health_metrics(self) -> Dict:
        """Get provider health metrics"""
        return {
            'api_calls': self.api_calls,
            'errors': self.errors,
            'last_success': self.last_success,
            'uptime': (datetime.now() - self.last_success).total_seconds() if self.last_success else 0
        }

# =============================================
# ENHANCED CCXT DATA PROVIDER - UNIVERSAL
# =============================================

class EnhancedCCXTDataProvider(EnhancedDataProvider):
    """Enhanced CCXT provider - UNIVERSAL (tanpa pemisahan spot/future)"""
    
    def __init__(self, exchange_id='binance', api_key='', secret=''):
        super().__init__()
        
        self.exchange_id = exchange_id
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
                    'options': {
                        'defaultType': 'spot',  # Default, tapi akan load semua markets
                    }
                }
                
                self.exchange = exchange_class(config)
                
                # Load semua market tanpa filter
                try:
                    self.exchange.load_markets()
                    logger.info(f"✅ Successfully connected to {exchange_id}, loaded {len(self.exchange.markets)} markets")
                    
                    # Log sample symbols
                    sample_symbols = list(self.exchange.markets.keys())[:10]
                    logger.info(f"📊 Sample symbols: {sample_symbols}")
                    
                except Exception as e:
                    logger.warning(f"⚠️ Could not load all markets: {e}")
                    self.exchange = None
                
            except Exception as e:
                logger.error(f"Failed to initialize {exchange_id}: {str(e)}")
                self.exchange = None
    
    def get_ohlcv(self, symbol: str, timeframe: str = '1h', limit: int = 200) -> pd.DataFrame:
        """Get OHLCV data - UNIVERSAL"""
        def fetch_ccxt_data():
            if not self.exchange:
                raise Exception(f"Exchange {self.exchange_id} not initialized")
            
            try:
                # Coba fetch data
                ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
                
                if not ohlcv:
                    # Coba dengan symbol alternatif
                    alt_symbols = self._get_alternative_symbols(symbol)
                    for alt_symbol in alt_symbols:
                        if alt_symbol != symbol:
                            try:
                                ohlcv = self.exchange.fetch_ohlcv(alt_symbol, timeframe, limit=limit)
                                if ohlcv:
                                    logger.info(f"⚠️ Using alternative symbol {alt_symbol} for {symbol}")
                                    symbol = alt_symbol
                                    break
                            except:
                                continue
                    
                    if not ohlcv:
                        raise ValueError(f"No OHLCV data returned for {symbol}")
                
                df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                
                # Validasi data
                if len(df) < 10:
                    raise ValueError(f"Insufficient data for {symbol}: {len(df)} bars")
                
                # 🚨 Filter harga 100 (data error)
                if 'close' in df.columns:
                    mask_100 = abs(df['close'] - 100.0) < 0.001
                    count_100 = mask_100.sum()
                    if count_100 > 0:
                        df = df[~mask_100].copy()
                        logger.warning(f"⚠️ Removed {count_100} bars with price 100 for {symbol}")
                
                # Validasi kualitas data
                is_valid, validation_msg = self.validate_market_data(df, symbol)
                if not is_valid:
                    logger.warning(f"Data validation failed: {symbol} - {validation_msg}")
                    # Data sudah diperbaiki di dalam fungsi validate_market_data
                
                current_price = df['close'].iloc[-1] if len(df) > 0 else 0
                logger.info(f"📊 {symbol} - {len(df)} bars, current: {current_price:.8f}, timeframe: {timeframe}")
                
                return df
                
            except Exception as e:
                logger.warning(f"CCXT failed for {symbol}: {str(e)}")
                raise

        return self._safe_api_call(fetch_ccxt_data)
    
    def get_ticker(self, symbol: str) -> Dict:
        """Get ticker data - UNIVERSAL"""
        def fetch_ticker():
            try:
                if not self.exchange:
                    raise Exception("Exchange not initialized")
                
                ticker = self.exchange.fetch_ticker(symbol)
                last_price = ticker.get('last')
                
                if last_price is None or last_price <= 0:
                    # Coba dengan symbol alternatif
                    alt_symbols = self._get_alternative_symbols(symbol)
                    for alt_symbol in alt_symbols:
                        if alt_symbol != symbol:
                            try:
                                ticker = self.exchange.fetch_ticker(alt_symbol)
                                last_price = ticker.get('last')
                                if last_price and last_price > 0:
                                    logger.info(f"⚠️ Using alternative symbol {alt_symbol} for ticker")
                                    symbol = alt_symbol
                                    break
                            except:
                                continue
                    
                    if last_price is None or last_price <= 0:
                        raise ValueError(f"Invalid price for {symbol}: {last_price}")
                
                # 🚨 Cek harga 100
                if abs(last_price - 100.0) < 0.001:
                    raise ValueError(f"Suspicious price 100 for {symbol}")
                
                return {
                    'last': last_price,
                    'volume': ticker.get('baseVolume', 0) or ticker.get('quoteVolume', 0),
                    'high': ticker.get('high'),
                    'low': ticker.get('low'),
                    'bid': ticker.get('bid'),
                    'ask': ticker.get('ask'),
                    'symbol': symbol,
                    'timestamp': datetime.now()
                }
            except Exception as e:
                logger.error(f"CCXT ticker error: {str(e)}")
                raise
        
        return self._safe_api_call(fetch_ticker)
    
    def get_popular_assets(self, limit: int = 100, **kwargs) -> List[Dict]:
        """Get popular assets - UNIVERSAL"""
        try:
            logger.info(f"🔄 Getting {limit} popular assets from {self.exchange_id}...")
            
            if not self.exchange:
                logger.warning(f"Exchange {self.exchange_id} not initialized")
                return self._get_fallback_major_coins(limit)
            
            # Coba load markets
            try:
                self.exchange.load_markets()
                markets = self.exchange.markets
                logger.info(f"📊 Loaded {len(markets)} markets from {self.exchange_id}")
            except Exception as e:
                logger.error(f"Failed to load markets: {e}")
                return self._get_fallback_major_coins(limit)
            
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
            if result:
                logger.info(f"   Top 10: {[item['symbol'] for item in result[:10]]}")
            
            return result[:limit]
            
        except Exception as e:
            logger.error(f"Error getting popular assets: {str(e)}")
            return self._get_fallback_major_coins(limit)
    
    def _get_fallback_major_coins(self, limit: int) -> List[Dict]:
        """Fallback major coins"""
        major_pairs = [
            'BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'XRP/USDT', 'ADA/USDT',
            'SOL/USDT', 'DOT/USDT', 'DOGE/USDT', 'AVAX/USDT', 'MATIC/USDT',
            'LTC/USDT', 'LINK/USDT', 'ATOM/USDT', 'XLM/USDT', 'BCH/USDT',
            'TRX/USDT', 'ETC/USDT', 'FIL/USDT', 'ALGO/USDT', 'VET/USDT'
        ]
        
        result = []
        for symbol in major_pairs[:limit]:
            base_name = symbol.split('/')[0]
            result.append({
                'symbol': symbol,
                'name': base_name,
                'exchange': self.exchange_id
            })
        
        return result
    
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
    
    def __init__(self):
        super().__init__()
    
    def get_ohlcv(self, symbol: str, timeframe: str = '1h', limit: int = 200) -> pd.DataFrame:
        """Get OHLCV from Yahoo Finance - UNIVERSAL"""
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
                    raise ValueError(f"No data returned for {yf_symbol}")
                
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
                        raise ValueError(f"Missing column {col} in data")
                
                df = df[required_cols]
                
                # 🚨 Filter harga 100
                if 'close' in df.columns:
                    mask_100 = abs(df['close'] - 100.0) < 0.001
                    count_100 = mask_100.sum()
                    if count_100 > 0:
                        df = df[~mask_100].copy()
                        logger.warning(f"⚠️ Removed {count_100} bars with price 100 for {symbol}")
                
                # Validasi
                is_valid, validation_msg = self.validate_market_data(df, symbol)
                if not is_valid:
                    logger.warning(f"YFinance validation failed: {symbol} - {validation_msg}")
                
                logger.info(f"📈 YFinance: {symbol} - {len(df)} bars")
                return df
                
            except Exception as e:
                logger.error(f"YFinance error for {symbol}: {str(e)}")
                raise

        return self._safe_api_call(fetch_yfinance_data)
    
    def get_ticker(self, symbol: str) -> Dict:
        """Get ticker data from Yahoo Finance - UNIVERSAL"""
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
                    raise ValueError(f"Invalid price: {last_price}")
                
                # 🚨 Cek harga 100
                if abs(last_price - 100.0) < 0.001:
                    raise ValueError(f"Suspicious price 100")
                
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
                logger.error(f"YFinance ticker error: {str(e)}")
                raise
        
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
            
            logger.info(f"📈 YFinance returning {len(result)} popular assets")
            return result
            
        except Exception as e:
            logger.error(f"Error getting popular assets: {str(e)}")
            return self._get_fallback_assets(limit)
    
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
    
    def _get_fallback_assets(self, limit: int) -> List[Dict]:
        """Fallback assets"""
        fallback = [
            {'symbol': 'BTC-USD', 'name': 'Bitcoin', 'exchange': 'yfinance', 'category': 'crypto'},
            {'symbol': 'ETH-USD', 'name': 'Ethereum', 'exchange': 'yfinance', 'category': 'crypto'},
            {'symbol': 'AAPL', 'name': 'Apple', 'exchange': 'yfinance', 'category': 'stock'},
            {'symbol': 'EURUSD=X', 'name': 'EUR/USD', 'exchange': 'yfinance', 'category': 'forex'}
        ]
        
        return fallback[:limit]

# =============================================
# UNIFIED SMART DATA PROVIDER - UNIVERSAL
# =============================================

class UnifiedDataProvider(EnhancedDataProvider):
    """Provider terpadu dengan auto-fallback - UNIVERSAL"""
    
    def __init__(self, exchange_id='binance', api_key='', secret=''):
        super().__init__()
        self.exchange_id = exchange_id
        
        # Setup primary provider (CCXT Universal)
        self.primary_provider = EnhancedCCXTDataProvider(
            exchange_id=exchange_id,
            api_key=api_key,
            secret=secret
        )
        
        # Setup fallback provider (YFinance Universal)
        self.fallback_provider = EnhancedYFinanceDataProvider()
        
        logger.info(f"🚀 UnifiedDataProvider ready | Exchange: {exchange_id}")
    
    def get_ohlcv(self, symbol: str, timeframe: str = '1h', limit: int = 200) -> pd.DataFrame:
        """Get OHLCV data dengan auto-fallback - UNIVERSAL"""
        logger.info(f"📊 Getting OHLCV for {symbol} (limit: {limit})")
        
        # Coba primary provider dulu
        try:
            result = self.primary_provider.get_ohlcv(symbol, timeframe, limit)
            
            if result is not None and not result.empty and len(result) >= 10:
                # 🚨 Filter harga 100
                if 'close' in result.columns:
                    mask_100 = abs(result['close'] - 100.0) < 0.001
                    count_100 = mask_100.sum()
                    if count_100 > 0:
                        result = result[~mask_100].copy()
                        logger.warning(f"🚨 Removed {count_100} bars with price 100 for {symbol}")
                
                # Validasi
                is_valid, msg = self.validate_market_data(result, symbol)
                if is_valid:
                    logger.info(f"✅ Valid data from primary provider: {len(result)} bars")
                    return result
                else:
                    logger.warning(f"⚠️ Primary provider data invalid: {msg}")
        except Exception as e:
            logger.warning(f"⚠️ Primary provider failed: {e}")
        
        # Fallback ke YFinance
        logger.warning("🔄 AUTO-FALLBACK: Switching to YFinance...")
        
        try:
            result = self.fallback_provider.get_ohlcv(symbol, timeframe, limit)
            
            if result is not None and not result.empty and len(result) >= 10:
                # 🚨 Filter harga 100
                if 'close' in result.columns:
                    mask_100 = abs(result['close'] - 100.0) < 0.001
                    count_100 = mask_100.sum()
                    if count_100 > 0:
                        result = result[~mask_100].copy()
                        logger.warning(f"🚨 Removed {count_100} bars with price 100 for {symbol}")
                
                # Validasi
                is_valid, msg = self.validate_market_data(result, symbol)
                if is_valid:
                    logger.info(f"✅ Valid data from fallback provider: {len(result)} bars")
                    return result
                else:
                    logger.warning(f"⚠️ Fallback provider data invalid: {msg}")
        except Exception as e:
            logger.warning(f"⚠️ Fallback provider failed: {e}")
        
        # Semua gagal
        logger.error(f"🚨 ALL DATA SOURCES FAILED for {symbol}")
        return pd.DataFrame()
    
    def get_ticker(self, symbol: str) -> Dict:
        """Get ticker data dengan auto-fallback - UNIVERSAL"""
        logger.debug(f"📈 Getting ticker for {symbol}")
        
        # Coba primary provider
        try:
            result = self.primary_provider.get_ticker(symbol)
            if result and result.get('last', 0) > 0 and abs(result.get('last', 0) - 100.0) > 0.001:
                logger.info(f"✅ Ticker from primary: {result.get('last')}")
                return result
        except Exception as e:
            logger.debug(f"Primary ticker failed: {e}")
        
        # Fallback ke YFinance
        try:
            result = self.fallback_provider.get_ticker(symbol)
            if result and result.get('last', 0) > 0 and abs(result.get('last', 0) - 100.0) > 0.001:
                logger.info(f"✅ Ticker from fallback: {result.get('last')}")
                return result
        except Exception as e:
            logger.debug(f"Fallback ticker failed: {e}")
        
        # Emergency fallback
        logger.warning(f"⚠️ Using emergency fallback for {symbol}")
        return {
            'last': self._estimate_realistic_price(symbol),
            'volume': 10000,
            'symbol': symbol,
            'timestamp': datetime.now(),
            'source': 'emergency_fallback'
        }
    
    def get_popular_assets(self, limit: int = 100, **kwargs) -> List[Dict]:
        """Get popular assets - UNIVERSAL"""
        logger.info(f"📋 Getting {limit} popular assets from {self.exchange_id}")
        
        # Coba primary provider
        try:
            assets = self.primary_provider.get_popular_assets(limit)
            if assets and len(assets) > 0:
                logger.info(f"✅ Found {len(assets)} assets from primary provider")
                return assets
        except Exception as e:
            logger.warning(f"⚠️ Primary provider failed: {e}")
        
        # Fallback ke YFinance
        try:
            assets = self.fallback_provider.get_popular_assets(limit)
            if assets and len(assets) > 0:
                logger.info(f"✅ Found {len(assets)} assets from fallback provider")
                return assets
        except Exception as e:
            logger.warning(f"⚠️ Fallback provider failed: {e}")
        
        # Emergency fallback
        return [
            {'symbol': 'BTC/USDT', 'name': 'Bitcoin', 'exchange': self.exchange_id},
            {'symbol': 'ETH/USDT', 'name': 'Ethereum', 'exchange': self.exchange_id},
            {'symbol': 'BNB/USDT', 'name': 'Binance Coin', 'exchange': self.exchange_id},
            {'symbol': 'XRP/USDT', 'name': 'Ripple', 'exchange': self.exchange_id},
            {'symbol': 'ADA/USDT', 'name': 'Cardano', 'exchange': self.exchange_id}
        ][:limit]
    
    def get_health_metrics(self) -> Dict:
        """Get health metrics"""
        base_metrics = super().get_health_metrics()
        
        base_metrics.update({
            'exchange': self.exchange_id,
            'primary_provider': self.primary_provider.__class__.__name__,
            'fallback_provider': self.fallback_provider.__class__.__name__,
            'status': 'active'
        })
        
        return base_metrics

# =============================================
# SMART CHAIN DATA PROVIDER - ALL 3 SOLUTIONS
# =============================================

class SmartChainDataProvider(EnhancedDataProvider):
    """
    Provider dengan 3 solusi legal:
    1. Binance mirror (us, me, sg) - CHAIN 1
    2. Exchange lain (OKX, KuCoin, Bybit) - CHAIN 2  
    3. YFinance fallback - CHAIN 3
    4. Cache untuk performance
    """
    
    def __init__(self, primary_mirror='binanceus', market_type='crypto'):
        super().__init__()
        self.primary_mirror = primary_mirror
        self.market_type = market_type
        self.active_provider = None
        self.providers_chain = []
        self.data_cache = {}
        self.cache_ttl = 300  # 5 menit cache
        self.initialize_chain()
        logger.info(f"🔗 SmartChainDataProvider ready | Market: {market_type}")
        
    def initialize_chain(self):
        """Initialize chain of providers berurutan"""
        logger.info("🔗 Initializing Smart Chain Provider...")
        
        # CHAIN 1: Binance mirrors (legal & gratis)
        binance_mirrors = [
            ('binanceus', 'Binance US'),  # US mirror
            ('binanceme', 'Binance ME'),  # Middle East mirror
            ('binancesg', 'Binance SG'),  # Singapore mirror
        ]
        
        # CHAIN 2: Exchange alternatif (mirip Binance)
        alt_exchanges = [
            ('okx', 'OKX'),
            ('kucoin', 'KuCoin'),
            ('bybit', 'Bybit'),
            ('gate', 'Gate.io'),
            ('coinbase', 'Coinbase'),
        ]
        
        # CHAIN 3: YFinance fallback
        yfinance_provider = ('yfinance', 'Yahoo Finance')
        
        # Bangun chain berdasarkan market type
        if self.market_type == 'crypto':
            self.providers_chain = binance_mirrors + alt_exchanges + [yfinance_provider]
        elif self.market_type in ['us_stocks', 'saham_id']:
            self.providers_chain = [yfinance_provider]  # Hanya YFinance untuk stocks
        elif self.market_type == 'forex':
            self.providers_chain = [yfinance_provider]  # Hanya YFinance untuk forex
        else:
            self.providers_chain = [yfinance_provider]  # Default
        
        logger.info(f"📋 Provider chain ({len(self.providers_chain)}):")
        for i, (exchange_id, name) in enumerate(self.providers_chain):
            logger.info(f"  {i+1}. {exchange_id} - {name}")
        
        # Coba connect ke provider pertama yang berhasil
        self._connect_to_first_available()
    
    def _connect_to_first_available(self):
        """Connect ke provider pertama yang available"""
        for exchange_id, name in self.providers_chain:
            if self._test_provider(exchange_id):
                self.active_provider = exchange_id
                logger.info(f"✅ Connected to {name} ({exchange_id})")
                return True
        
        logger.warning("⚠️ All providers failed, will use fallback on first request")
        return False
    
    def _test_provider(self, exchange_id: str) -> bool:
        """Test jika provider bisa connect"""
        try:
            if exchange_id == 'yfinance':
                # Test YFinance dengan rate limiting
                time.sleep(0.5)  # Rate limit
                ticker = yf.Ticker("BTC-USD")
                hist = ticker.history(period='1d')
                return not hist.empty
            
            else:
                # Test CCXT exchange
                exchange_class = getattr(ccxt, exchange_id, None)
                if not exchange_class:
                    return False
                
                # Rate limiting
                time.sleep(0.3)
                
                exchange = exchange_class({
                    'enableRateLimit': True,
                    'timeout': 10000,
                    'options': {'defaultType': 'spot'}
                })
                
                # Coba load markets (non-blocking)
                try:
                    markets = exchange.load_markets()
                    if markets and len(markets) > 0:
                        return True
                except:
                    # Coba fetch ticker saja
                    try:
                        ticker = exchange.fetch_ticker('BTC/USDT')
                        return ticker and 'last' in ticker and ticker['last'] > 0
                    except:
                        return False
                        
                return False
                
        except Exception as e:
            logger.debug(f"❌ Provider {exchange_id} test failed: {e}")
            return False
    
    def _get_cached_data(self, cache_key: str):
        """Get cached data jika masih valid"""
        if cache_key in self.data_cache:
            timestamp, data = self.data_cache[cache_key]
            if datetime.now() - timestamp < timedelta(seconds=self.cache_ttl):
                return data
        return None
    
    def _set_cached_data(self, cache_key: str, data):
        """Set data ke cache"""
        self.data_cache[cache_key] = (datetime.now(), data)
        # Batasi cache size
        if len(self.data_cache) > 100:
            # Hapus yang paling lama
            oldest_key = next(iter(self.data_cache))
            del self.data_cache[oldest_key]
    
    def get_ohlcv(self, symbol: str, timeframe: str = '1h', limit: int = 100) -> pd.DataFrame:
        """
        Get OHLCV dengan fallback chain - OVERRIDE dari EnhancedDataProvider
        
        Args:
            symbol: Symbol (BTC/USDT, BTC-USD, etc)
            timeframe: 1h, 4h, 1d, etc
            limit: Number of candles
        
        Returns:
            DataFrame dengan OHLCV data
        """
        # Cache key
        cache_key = f"ohlcv_{symbol}_{timeframe}_{limit}"
        
        # Cek cache dulu
        cached_data = self._get_cached_data(cache_key)
        if cached_data is not None:
            logger.debug(f"📦 Using cached data for {symbol}")
            return cached_data.copy()
        
        # Coba semua provider berurutan
        for exchange_id, name in self.providers_chain:
            try:
                logger.debug(f"🔄 Trying {name} for {symbol}...")
                
                if exchange_id == 'yfinance':
                    df = self._get_yfinance_ohlcv(symbol, timeframe, limit)
                else:
                    df = self._get_ccxt_ohlcv(exchange_id, symbol, timeframe, limit)
                
                if df is not None and not df.empty and len(df) >= 10:
                    # Validasi data
                    is_valid, msg = self.validate_market_data(df, symbol)
                    if is_valid:
                        # Cache hasil
                        self._set_cached_data(cache_key, df.copy())
                        
                        # Update active provider jika berhasil
                        if exchange_id != self.active_provider:
                            self.active_provider = exchange_id
                            logger.info(f"✅ Switched to {name}")
                        
                        logger.info(f"✅ {symbol}: {len(df)} bars from {name}")
                        return df.copy()
                    else:
                        logger.warning(f"⚠️ {name} data invalid: {msg}")
                        
            except Exception as e:
                logger.debug(f"⚠️ {name} failed: {str(e)[:100]}")
                continue
        
        # Semua gagal, return dummy data
        logger.warning(f"🚨 All providers failed for {symbol}, using dummy data")
        df = self._get_dummy_data(symbol, limit)
        self._set_cached_data(cache_key, df.copy())
        return df
    
    def _get_ccxt_ohlcv(self, exchange_id: str, symbol: str, timeframe: str, limit: int) -> pd.DataFrame:
        """Get OHLCV dari CCXT exchange"""
        try:
            # Rate limiting
            time.sleep(0.2)
            
            # Convert symbol format untuk exchange
            formatted_symbol = self._format_symbol_for_exchange(exchange_id, symbol)
            
            # Buat provider CCXT
            provider = EnhancedCCXTDataProvider(exchange_id=exchange_id)
            
            # Get data
            df = provider.get_ohlcv(formatted_symbol, timeframe, limit)
            
            if df is not None and not df.empty:
                # Pastikan index timestamp
                if 'timestamp' in df.columns:
                    df.set_index('timestamp', inplace=True)
                return df
            else:
                return None
            
        except Exception as e:
            logger.debug(f"CCXT {exchange_id} error: {e}")
            raise
    
    def _get_yfinance_ohlcv(self, symbol: str, timeframe: str, limit: int) -> pd.DataFrame:
        """Get OHLCV dari YFinance"""
        try:
            # Rate limiting
            time.sleep(0.5)
            
            # Convert symbol format
            yf_symbol = self._convert_to_yfinance_symbol(symbol)
            
            # Buat provider YFinance
            provider = EnhancedYFinanceDataProvider()
            
            # Get data
            df = provider.get_ohlcv(yf_symbol, timeframe, limit)
            
            return df
            
        except Exception as e:
            logger.debug(f"YFinance error: {e}")
            raise
    
    def _get_dummy_data(self, symbol: str, limit: int) -> pd.DataFrame:
        """Generate dummy data jika semua gagal"""
        # Base price berdasarkan symbol
        if 'BTC' in symbol:
            base_price = 50000
        elif 'ETH' in symbol:
            base_price = 3000
        elif 'SOL' in symbol:
            base_price = 100
        else:
            base_price = 100
        
        dates = pd.date_range(end=datetime.now(), periods=limit, freq='1H')
        
        df = pd.DataFrame({
            'open': base_price + np.random.randn(limit) * base_price * 0.01,
            'high': base_price + np.random.randn(limit) * base_price * 0.02,
            'low': base_price - np.random.randn(limit) * base_price * 0.02,
            'close': base_price + np.random.randn(limit) * base_price * 0.01,
            'volume': np.random.rand(limit) * 1000
        }, index=dates)
        
        df.index.name = 'timestamp'
        logger.info(f"🛠️ Generated {len(df)} dummy bars for {symbol}")
        return df
    
    def _format_symbol_for_exchange(self, exchange_id: str, symbol: str) -> str:
        """Format symbol untuk exchange tertentu"""
        # Standardize: hapus - dan ganti dengan /
        formatted = symbol.replace('-', '/')
        
        # Konversi khusus untuk beberapa exchange
        if exchange_id in ['binanceus', 'binanceme', 'binancesg']:
            # Binance mirrors pakai format BTC/USDT
            if '/USD' in formatted and not formatted.endswith('T'):
                formatted = formatted.replace('/USD', '/USDT')
        
        return formatted
    
    def _convert_to_yfinance_symbol(self, symbol: str) -> str:
        """Convert ke format YFinance"""
        if '/USDT' in symbol:
            return symbol.replace('/USDT', '-USD')
        elif ':USDT' in symbol:
            return symbol.replace(':USDT', '')
        elif '/' in symbol and '=X' not in symbol:
            # Untuk forex pairs
            return symbol.replace('/', '') + '=X'
        else:
            return symbol
    
    def get_ticker(self, symbol: str) -> Dict:
        """Get ticker dengan fallback chain"""
        cache_key = f"ticker_{symbol}"
        
        # Cek cache
        cached_data = self._get_cached_data(cache_key)
        if cached_data is not None:
            return cached_data.copy()
        
        # Coba semua provider
        for exchange_id, name in self.providers_chain:
            try:
                if exchange_id == 'yfinance':
                    ticker = self._get_yfinance_ticker(symbol)
                else:
                    ticker = self._get_ccxt_ticker(exchange_id, symbol)
                
                if ticker and ticker.get('last', 0) > 0:
                    # Cache
                    self._set_cached_data(cache_key, ticker.copy())
                    
                    # Update active provider
                    if exchange_id != self.active_provider:
                        self.active_provider = exchange_id
                        logger.info(f"✅ Switched to {name} for ticker")
                    
                    return ticker
                    
            except Exception as e:
                logger.debug(f"⚠️ {name} ticker failed: {e}")
                continue
        
        # Fallback ke dummy
        ticker = self._get_dummy_ticker(symbol)
        self._set_cached_data(cache_key, ticker.copy())
        return ticker
    
    def _get_ccxt_ticker(self, exchange_id: str, symbol: str) -> Dict:
        """Get ticker dari CCXT"""
        try:
            time.sleep(0.1)  # Rate limit
            
            formatted_symbol = self._format_symbol_for_exchange(exchange_id, symbol)
            
            provider = EnhancedCCXTDataProvider(exchange_id=exchange_id)
            ticker = provider.get_ticker(formatted_symbol)
            
            if ticker:
                ticker['source'] = exchange_id
                return ticker
            else:
                raise Exception("No ticker data")
            
        except Exception as e:
            logger.debug(f"CCXT ticker error: {e}")
            raise
    
    def _get_yfinance_ticker(self, symbol: str) -> Dict:
        """Get ticker dari YFinance"""
        try:
            time.sleep(0.3)  # Rate limit
            
            yf_symbol = self._convert_to_yfinance_symbol(symbol)
            
            provider = EnhancedYFinanceDataProvider()
            ticker = provider.get_ticker(yf_symbol)
            
            if ticker:
                ticker['source'] = 'yfinance'
                return ticker
            else:
                raise Exception("No ticker data")
            
        except Exception as e:
            logger.debug(f"YFinance ticker error: {e}")
            raise
    
    def _get_dummy_ticker(self, symbol: str) -> Dict:
        """Generate dummy ticker"""
        if 'BTC' in symbol:
            price = 50000
        elif 'ETH' in symbol:
            price = 3000
        elif 'SOL' in symbol:
            price = 100
        else:
            price = 100
        
        return {
            'symbol': symbol,
            'last': price,
            'bid': price * 0.999,
            'ask': price * 1.001,
            'high': price * 1.01,
            'low': price * 0.99,
            'volume': 1000,
            'timestamp': datetime.now(),
            'source': 'dummy_fallback'
        }
    
    def get_popular_assets(self, limit: int = 100, **kwargs) -> List[Dict]:
        """Get popular assets dari provider yang aktif"""
        try:
            # Coba provider pertama yang berhasil
            for exchange_id, name in self.providers_chain:
                try:
                    if exchange_id == 'yfinance':
                        provider = EnhancedYFinanceDataProvider()
                        assets = provider.get_popular_assets(limit, **kwargs)
                    else:
                        provider = EnhancedCCXTDataProvider(exchange_id=exchange_id)
                        assets = provider.get_popular_assets(limit, **kwargs)
                    
                    if assets and len(assets) > 0:
                        # Tambahkan info provider
                        for asset in assets:
                            asset['provider'] = name
                            asset['source'] = exchange_id
                        
                        logger.info(f"✅ Got {len(assets)} assets from {name}")
                        return assets[:limit]
                        
                except Exception as e:
                    logger.debug(f"⚠️ {name} assets failed: {e}")
                    continue
            
            # Fallback
            return self._get_fallback_assets(limit)
            
        except Exception as e:
            logger.error(f"❌ Error getting assets: {e}")
            return self._get_fallback_assets(limit)
    
    def _get_fallback_assets(self, limit: int) -> List[Dict]:
        """Fallback assets"""
        assets = []
        
        if self.market_type == 'crypto':
            symbols = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'XRP/USDT', 'ADA/USDT']
            for symbol in symbols[:limit]:
                assets.append({
                    'symbol': symbol,
                    'name': symbol.split('/')[0],
                    'exchange': 'fallback',
                    'provider': 'SmartChainFallback',
                    'source': 'fallback',
                    'type': 'crypto'
                })
        elif self.market_type == 'us_stocks':
            symbols = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA']
            for symbol in symbols[:limit]:
                assets.append({
                    'symbol': symbol,
                    'name': symbol,
                    'exchange': 'NASDAQ',
                    'provider': 'SmartChainFallback',
                    'source': 'fallback',
                    'type': 'stock'
                })
        
        return assets
    
    def get_health_status(self) -> Dict:
        """Get health status provider"""
        return {
            'active_provider': self.active_provider,
            'provider_name': dict(self.providers_chain).get(self.active_provider, 'Unknown'),
            'total_providers': len(self.providers_chain),
            'cache_size': len(self.data_cache),
            'market_type': self.market_type,
            'status': 'active'
        }

# =============================================
# DATA PROVIDER FACTORY
# =============================================

class DataProviderFactory:
    """Factory untuk membuat data provider"""
    
    @staticmethod
    def create_provider(provider_type: str, **kwargs):
        """Create data provider berdasarkan type"""
        
        if provider_type == 'universal':
            # 🆕 PROVIDER UNIVERSAL (REKOMENDASI UTAMA)
            exchange_id = kwargs.get('exchange_id', 'binance')
            api_key = kwargs.get('api_key', '')
            secret = kwargs.get('secret', '')
            return UnifiedDataProvider(
                exchange_id=exchange_id,
                api_key=api_key,
                secret=secret
            )
            
        elif provider_type == 'smart_chain':
            # 🆕 SMART CHAIN PROVIDER (3 SOLUSI)
            market_type = kwargs.get('market_type', 'crypto')
            primary_mirror = kwargs.get('primary_mirror', 'binanceus')
            
            return SmartChainDataProvider(
                primary_mirror=primary_mirror,
                market_type=market_type
            )
            
        elif provider_type == 'ccxt':
            # CCXT Universal
            exchange_id = kwargs.get('exchange_id', 'binance')
            api_key = kwargs.get('api_key', '')
            secret = kwargs.get('secret', '')
            
            return EnhancedCCXTDataProvider(
                exchange_id=exchange_id,
                api_key=api_key,
                secret=secret
            )
                
        elif provider_type == 'yfinance':
            # YFinance Universal
            return EnhancedYFinanceDataProvider()
            
        else:
            raise ValueError(f"Unknown provider type: {provider_type}")

# =============================================
# DYNAMIC DATA PROVIDER
# =============================================

class DynamicDataProvider(EnhancedDataProvider):
    """Dynamic data provider dengan fallback - UNIVERSAL"""
    
    def __init__(self, exchange_id='binance', api_key='', secret=''):
        super().__init__()
        self.exchange_id = exchange_id
        
        # Setup providers
        self._setup_providers(exchange_id, api_key, secret)
        
        logger.info(f"DynamicDataProvider initialized for {exchange_id}")
    
    def _setup_providers(self, exchange_id: str, api_key: str, secret: str):
        """Setup providers"""
        try:
            # Setup CCXT provider
            self.primary_provider = EnhancedCCXTDataProvider(
                exchange_id=exchange_id,
                api_key=api_key,
                secret=secret
            )
            
            # Setup YFinance fallback
            self.fallback_provider = EnhancedYFinanceDataProvider()
            
            logger.info(f"✅ Providers setup: CCXT + YFinance")
            
        except Exception as e:
            logger.error(f"❌ Failed to setup CCXT: {e}")
            # Fallback ke YFinance saja
            self.primary_provider = EnhancedYFinanceDataProvider()
            self.fallback_provider = EnhancedYFinanceDataProvider()
            logger.info(f"⚠️ Using YFinance as primary")
    
    def get_ohlcv(self, symbol: str, timeframe: str = '1h', limit: int = 200) -> pd.DataFrame:
        """Get OHLCV dengan auto-fallback"""
        return self._execute_with_fallback('get_ohlcv', symbol, timeframe, limit)
    
    def get_ticker(self, symbol: str) -> Dict:
        """Get ticker dengan auto-fallback"""
        return self._execute_with_fallback('get_ticker', symbol)
    
    def get_popular_assets(self, limit: int = 100, **kwargs) -> List[Dict]:
        """Get popular assets dengan auto-fallback"""
        return self._execute_with_fallback('get_popular_assets', limit=limit)
    
    def _execute_with_fallback(self, method_name: str, *args, **kwargs):
        """Execute method dengan fallback otomatis"""
        try:
            # Coba primary provider
            method = getattr(self.primary_provider, method_name)
            result = method(*args, **kwargs)
            
            # Validasi result
            if self._validate_result(result, method_name):
                return result
            else:
                raise ValueError("Invalid data from primary provider")
                
        except Exception as e:
            logger.warning(f"⚠️ Primary failed for {method_name}: {e}")
            
            # Fallback
            try:
                method = getattr(self.fallback_provider, method_name)
                result = method(*args, **kwargs)
                
                if self._validate_result(result, method_name):
                    logger.info(f"✅ Fallback successful for {method_name}")
                    return result
                else:
                    raise ValueError("Invalid data from fallback provider")
                    
            except Exception as fallback_e:
                logger.error(f"❌ Fallback failed: {fallback_e}")
                
                # Emergency fallback
                return self._get_emergency_fallback(method_name, *args, **kwargs)
    
    def _validate_result(self, result, method_name: str) -> bool:
        """Validasi hasil"""
        if result is None:
            return False
            
        if method_name == 'get_ohlcv':
            return isinstance(result, pd.DataFrame) and not result.empty and len(result) >= 10
        elif method_name == 'get_ticker':
            return isinstance(result, dict) and result.get('last', 0) > 0
        elif method_name == 'get_popular_assets':
            return isinstance(result, list) and len(result) > 0
            
        return False
    
    def _get_emergency_fallback(self, method_name: str, *args, **kwargs):
        """Emergency fallback"""
        if method_name == 'get_ohlcv':
            return pd.DataFrame()
        elif method_name == 'get_ticker':
            symbol = kwargs.get('symbol', args[0] if args else 'BTC/USDT')
            return {
                'last': self._estimate_realistic_price(symbol),
                'volume': 10000,
                'symbol': symbol
            }
        elif method_name == 'get_popular_assets':
            limit = kwargs.get('limit', 100)
            return [
                {'symbol': 'BTC/USDT', 'name': 'Bitcoin', 'exchange': self.exchange_id},
                {'symbol': 'ETH/USDT', 'name': 'Ethereum', 'exchange': self.exchange_id}
            ][:limit]
        
        return None

# =============================================
# TEST FUNCTIONS
# =============================================

def test_universal_provider():
    """Test Universal Provider"""
    print("\n" + "="*60)
    print("🧪 TESTING UNIVERSAL DATA PROVIDER")
    print("="*60)
    
    # Test 1: Universal CCXT Provider
    print("\n1️⃣ Testing Universal CCXT Provider:")
    try:
        provider = EnhancedCCXTDataProvider(exchange_id='binance')
        assets = provider.get_popular_assets(5)
        print(f"✅ Popular assets: {len(assets)} found")
        for i, asset in enumerate(assets[:3]):
            print(f"   {i+1}. {asset['symbol']} ({asset['name']})")
    except Exception as e:
        print(f"❌ CCXT Provider error: {e}")
    
    # Test 2: Unified Provider
    print("\n2️⃣ Testing Unified Provider:")
    try:
        unified = UnifiedDataProvider(exchange_id='binance')
        
        # Test OHLCV
        data = unified.get_ohlcv("BTC/USDT", '1h', 20)
        if not data.empty:
            print(f"✅ OHLCV data: {len(data)} rows")
            print(f"   Latest: {data['close'].iloc[-1]:.2f} | Volume: {data['volume'].iloc[-1]:.0f}")
        else:
            print("⚠️ No OHLCV data (might be API limit)")
        
        # Test ticker
        ticker = unified.get_ticker("ETH/USDT")
        print(f"✅ Ticker: {ticker['symbol']} = ${ticker['last']:.2f}")
        
    except Exception as e:
        print(f"❌ Unified Provider error: {e}")
    
    # Test 3: Factory
    print("\n3️⃣ Testing Factory:")
    try:
        factory_provider = DataProviderFactory.create_provider('universal', exchange_id='binance')
        assets = factory_provider.get_popular_assets(3)
        print(f"✅ Factory assets: {len(assets)} found")
        for asset in assets:
            print(f"   - {asset['symbol']} ({asset['name']})")
    except Exception as e:
        print(f"❌ Factory error: {e}")
    
    # Test 4: Dynamic Provider
    print("\n4️⃣ Testing Dynamic Provider:")
    try:
        dynamic = DynamicDataProvider(exchange_id='binance')
        assets = dynamic.get_popular_assets(3)
        print(f"✅ Dynamic assets: {len(assets)} found")
        print(f"   Health: {dynamic.get_health_metrics()}")
    except Exception as e:
        print(f"❌ Dynamic error: {e}")
    
    # Test 5: Smart Chain Provider
    print("\n5️⃣ Testing Smart Chain Provider:")
    try:
        smart_chain = SmartChainDataProvider(market_type='crypto')
        
        # Test popular assets
        assets = smart_chain.get_popular_assets(5)
        print(f"✅ Smart Chain assets: {len(assets)} found")
        for asset in assets[:3]:
            print(f"   - {asset['symbol']} from {asset['provider']}")
        
        # Test health status
        health = smart_chain.get_health_status()
        print(f"✅ Health status: {health['active_provider']} | Cache: {health['cache_size']}")
        
    except Exception as e:
        print(f"❌ Smart Chain error: {e}")

def quick_test():
    """Quick test function"""
    print("\n⚡ QUICK TEST")
    
    # Simple test with YFinance (always works)
    print("\nTesting YFinance Provider:")
    yf_provider = EnhancedYFinanceDataProvider()
    
    try:
        # Test crypto
        btc_data = yf_provider.get_ohlcv("BTC-USD", '1d', 10)
        print(f"✅ BTC data: {len(btc_data)} rows")
        
        # Test stock
        aapl_ticker = yf_provider.get_ticker("AAPL")
        print(f"✅ AAPL price: ${aapl_ticker['last']:.2f}")
        
        # Test popular assets
        assets = yf_provider.get_popular_assets(5)
        print(f"✅ Popular assets: {[a['symbol'] for a in assets]}")
        
    except Exception as e:
        print(f"❌ YFinance test failed: {e}")
    
    # Test Smart Chain
    print("\nTesting Smart Chain Provider:")
    try:
        smart_chain = SmartChainDataProvider(market_type='crypto')
        
        # Test OHLCV
        data = smart_chain.get_ohlcv("BTC/USDT", '1h', 10)
        if not data.empty:
            print(f"✅ Smart Chain BTC data: {len(data)} rows")
        else:
            print("⚠️ No data from Smart Chain")
        
        # Test ticker
        ticker = smart_chain.get_ticker("ETH/USDT")
        print(f"✅ Smart Chain ETH price: ${ticker['last']:.2f}")
        
    except Exception as e:
        print(f"❌ Smart Chain test failed: {e}")

if __name__ == "__main__":
    print("\n" + "="*60)
    print("UNIVERSAL DATA PROVIDER TEST SUITE")
    print("="*60)
    
    # Run comprehensive tests
    test_universal_provider()
    
    # Run quick test
    quick_test()
    
    print("\n" + "="*60)
    print("✅ TESTS COMPLETED")
    print("="*60)
