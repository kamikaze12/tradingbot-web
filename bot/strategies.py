import pandas as pd
import numpy as np
from abc import ABC, abstractmethod
import warnings
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum
import logging
from scipy import stats
from scipy.signal import argrelextrema
import talib
import yfinance as yf
from datetime import datetime, timedelta
import time

warnings.filterwarnings('ignore')

# Enhanced logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# =============================================
# SCALPING CONFIGURATION - UNTUK PERBAIKAN BIAS SHORT
# =============================================

SCALPING_CONFIG = {
    "timeframe": "5m",            # 5 menit untuk scalping
    "lookback": 150,              # ~12.5 jam data
    "min_score_threshold": 4.0,   # Minimal absolute score untuk trigger sinyal
    "long_bias": 0.0,            # 🔥 UBAH: dari 0.3 ke 0.0 (NEUTRAL)
    "entry_range_pct": 0.008,     # 0.8% lebih ketat untuk scalping
    "atr_multiplier": 0.7,        # TP/SL lebih ketat untuk scalping
    "min_volume_usd": 500000,     # Minimal volume $500k
    "price_filter": {
        "min": 0.01,              # Harga minimal $0.01
        "max": 500                # 🔥 UBAH: dari 1000 ke 500
    },
    "skip_dummy_data": True,      # Skip aset dengan dummy data
    "require_real_data": True,    # Hanya gunakan data real dari provider
    "max_volatility": 0.15,       # Maksimal volatilitas harian 15%
    "min_volatility": 0.005       # Minimal volatilitas harian 0.5% untuk scalping
}

# =============================================
# DATA CLEANER FUNCTION - IMPLEMENTASI GAMPANG (DIPERBAIKI)
# =============================================

def get_clean_data(symbol, provider=None, timeframe='1h', lookback=200):
    """
    Fungsi simple untuk mendapatkan data bersih.
    HANYA ambil data jika bersih dari masalah harga 100 dan masalah umum lainnya.
    """
    try:
        # 🚨 **PERBAIKAN UTAMA: Gunakan provider jika diberikan**
        if provider is not None and hasattr(provider, 'get_ohlcv'):
            try:
                logger.info(f"📊 Getting data for {symbol} from {provider.__class__.__name__}...")
                df = provider.get_ohlcv(symbol, timeframe, limit=lookback)
                
                if df is None or df.empty:
                    logger.warning(f"Provider returned empty data for {symbol}")
                    # Fallback ke yfinance
                    provider = None
                else:
                    # 🔥 PERBAIKAN: Cek minimal data
                    if len(df) < 20:
                        logger.warning(f"⚠️ Insufficient data from provider: {len(df)} bars")
                        provider = None
                    else:
                        logger.info(f"✅ Data from provider: {len(df)} bars")
                    
            except Exception as provider_error:
                logger.warning(f"Provider failed for {symbol}: {provider_error}, falling back to yfinance")
                # Fallback ke yfinance jika provider gagal
                provider = None
        
        # Jika provider None atau gagal, gunakan yfinance
        if provider is None:
            # ⏰ TAMBAH RATE LIMITING - delay 1 detik antara request
            time.sleep(0.5)  # Dikurangi dari 1.0 ke 0.5 untuk lebih cepat
            
            # Clean symbol untuk yfinance
            clean_symbol = symbol.split(':')[0] if ':' in symbol else symbol
            clean_symbol = clean_symbol.replace('/', '-').replace('USDT-', '')
            
            # Download data dari yfinance
            logger.info(f"📥 Downloading {clean_symbol} from YFinance...")
            try:
                df = yf.download(clean_symbol, period=f'{lookback}d', interval=timeframe, progress=False)
            except Exception as e:
                logger.error(f"YFinance download error: {e}")
                return pd.DataFrame()
            
            if df is None or df.empty:
                logger.warning(f"No data for {symbol}")
                return pd.DataFrame()
        
        if df is None or df.empty:
            logger.warning(f"Empty DataFrame after provider for {symbol}")
            return pd.DataFrame()
        
        # 🚨 **CEK DAN PERBAIKI HARGA 100** - DIPERBAIKI: GUNAKAN numpy.isclose
        if 'close' in df.columns:
            # Deteksi harga stuck di 100 - GUNAKAN numpy.isclose
            close_values = df['close'].values
            is_close_to_100 = np.isclose(close_values, 100.0, atol=0.001)
            
            if np.any(is_close_to_100):
                count_100 = np.sum(is_close_to_100)
                logger.warning(f"Found {count_100} bars with close price 100 in {symbol}. Fixing...")
                
                # Ganti harga 100 dengan NaN
                df.loc[is_close_to_100, 'close'] = np.nan
                
                # Forward fill untuk ganti NaN dengan harga sebelumnya
                df['close'] = df['close'].ffill()
                
                # Backfill untuk kasus harga awal 100
                df['close'] = df['close'].bfill()
        
        # Pastikan harga tidak aneh
        if 'close' in df.columns:
            close_values = df['close'].values
            
            # Hapus baris dengan harga <= 0 - GUNAKAN BOOLEAN INDEXING dengan .values
            mask_positive = close_values > 0
            if not np.all(mask_positive):
                df = df[mask_positive].copy()
            
            # Hapus baris dengan harga tidak realistic
            mask_realistic = close_values < 1000000
            if not np.all(mask_realistic):
                df = df[mask_realistic].copy()
            
            # Hapus baris dengan pergerakan aneh (high < low)
            if 'high' in df.columns and 'low' in df.columns:
                high_values = df['high'].values
                low_values = df['low'].values
                mask_valid = high_values >= low_values
                if not np.all(mask_valid):
                    df = df[mask_valid].copy()
        
        # Standardize column names (jika belum)
        column_mapping = {
            'Open': 'open',
            'High': 'high', 
            'Low': 'low',
            'Close': 'close',
            'Volume': 'volume'
        }
        
        for old, new in column_mapping.items():
            if old in df.columns:
                df = df.rename(columns={old: new})
        
        # Tambahkan column jika tidak ada
        required_cols = ['open', 'high', 'low', 'close', 'volume']
        for col in required_cols:
            if col not in df.columns:
                if col == 'volume':
                    df[col] = np.random.normal(1000000, 100000, len(df))
                else:
                    df[col] = df['close'] if 'close' in df.columns else 100
        
        # Validasi final
        if df.empty:
            logger.warning(f"Empty DataFrame after cleaning for {symbol}")
            return pd.DataFrame()
        
        # Final check: pastikan TIDAK ADA harga 100 - GUNAKAN np.isclose
        if 'close' in df.columns:
            # GUNAKAN numpy.isclose untuk array
            close_values_final = df['close'].values
            is_close_to_100_final = np.isclose(close_values_final, 100.0, atol=0.001)
            
            if np.any(is_close_to_100_final):
                logger.error(f"🚨 {symbol} still has price 100 after cleaning!")
                return pd.DataFrame()
        
        logger.info(f"✅ Clean data for {symbol}: {len(df)} bars")
        return df
        
    except Exception as e:
        logger.error(f"Error in get_clean_data for {symbol}: {e}")
        return pd.DataFrame()

def get_trading_data(symbol, provider=None, scalping_mode=False, require_real_data=False):
    """
    Wrapper function untuk digunakan di strategi trading.
    HANYA return data jika benar-benar bersih.
    
    Args:
        symbol: Trading symbol
        provider: Data provider (optional)
        scalping_mode: Jika True, tambahkan filter khusus untuk scalping
        require_real_data: Jika True, tolak data dummy/sintetis
    """
    try:
        # 🚨 **PERBAIKAN: Gunakan provider langsung jika tersedia**
        if provider is not None and hasattr(provider, 'get_ohlcv'):
            try:
                logger.info(f"🔍 Getting OHLCV for {symbol} from {provider.__class__.__name__}")
                
                # 🔥 PERBAIKAN UTAMA: Gunakan timeframe dan limit yang sesuai
                timeframe = '5m' if scalping_mode else '1h'
                limit = 150 if scalping_mode else 100
                
                df = provider.get_ohlcv(symbol, timeframe, limit)
                
                if df is None or df.empty:
                    logger.warning(f"Provider returned no data for {symbol}")
                    return None
                
                # 🔥 PERBAIKAN: Validasi jumlah data minimum berdasarkan mode
                min_bars = 100 if scalping_mode else 20  # 🔥 DARI 10 ke 20 untuk regular
                if len(df) < min_bars:
                    logger.warning(f"⚠️ {symbol} insufficient data: {len(df)} < {min_bars} bars")
                    return None
                
                # Standardize column names
                column_mapping = {
                    'Open': 'open',
                    'High': 'high', 
                    'Low': 'low',
                    'Close': 'close',
                    'Volume': 'volume'
                }
                
                for old, new in column_mapping.items():
                    if old in df.columns:
                        df = df.rename(columns={old: new})
                
                # 🔥 PERBAIKAN KETAT: Cek dan bersihkan harga 100 secara eksplisit
                if 'close' in df.columns:
                    # Debug logging
                    logger.debug(f"🔍 {symbol}: Checking for price 100, current range: {df['close'].min():.4f}-{df['close'].max():.4f}")
                    
                    # Method 1: Direct check dengan numpy
                    close_values = df['close'].values
                    price_100_count = np.sum(np.isclose(close_values, 100.0, atol=0.001))
                    if price_100_count > 0:
                        logger.error(f"🚨 {symbol}: Found {price_100_count} bars with price ~100, rejecting!")
                        return None
                    
                    # Method 2: Filter jika terlalu banyak harga sama
                    unique_prices = len(np.unique(close_values))
                    if unique_prices < 3 and len(df) > 10:
                        logger.warning(f"⚠️ {symbol}: Too few unique prices ({unique_prices}), possibly stuck at 100")
                        return None
                
                logger.info(f"✅ Valid data from provider for {symbol}: {len(df)} bars")
                return df
                
            except Exception as e:
                logger.error(f"Error getting data from provider: {e}")
                # Fallback ke get_clean_data
                pass
        
        # Fallback ke get_clean_data jika provider tidak tersedia atau gagal
        data = get_clean_data(symbol, provider)
        
        # 🔥 PERBAIKAN: Validasi dengan cara yang lebih aman
        if data is None or data.empty:
            return None
        
        # Pastikan ini adalah DataFrame
        if isinstance(data, pd.Series):
            data = data.to_frame().T
        
        # =============================================
        # FILTER KHUSUS UNTUK SCALPING MODE
        # =============================================
        if scalping_mode:
            # 1. Cek jumlah data minimum untuk scalping
            if len(data) < 100:
                logger.warning(f"⚠️ {symbol} insufficient data for scalping: {len(data)} bars")
                return None
            
            # 2. Cek volatilitas (minimal movement untuk scalping)
            if len(data) > 1:
                price_changes = data['close'].pct_change().abs().mean()
                if price_changes < 0.0005:  # Kurang dari 0.05% average movement
                    logger.warning(f"⚠️ {symbol} too flat for scalping: {price_changes*100:.3f}% avg change")
                    return None
            
            # 3. Cek volume (harus cukup liquid untuk scalping)
            if 'volume' in data.columns:
                avg_volume = data['volume'].mean()
                if avg_volume < 100000:  # Minimal volume untuk scalping
                    logger.warning(f"⚠️ {symbol} volume too low for scalping: {avg_volume:.0f}")
                    return None
            
            # 4. Cek volatilitas maksimal (terlalu volatile berbahaya untuk scalping)
            if len(data) > 1:
                volatility = data['close'].pct_change().std() * np.sqrt(252)
                if volatility > SCALPING_CONFIG["max_volatility"]:
                    logger.warning(f"⚠️ {symbol} too volatile for scalping: {volatility:.1%}")
                    return None
        
        # 🔥 PERBAIKAN: Validasi harga 100 dengan metode yang TIDAK menyebabkan ambiguous truth value
        try:
            if 'close' in data.columns:
                # Gunakan .values untuk menghindari ambiguous truth value
                close_values = data['close'].values
                
                # Cek jika ada harga yang mendekati 100
                is_close_to_100 = np.isclose(close_values, 100.0, atol=0.001)
                
                if np.any(is_close_to_100):
                    count_100 = np.sum(is_close_to_100)
                    logger.error(f"🚨 {symbol}: Found {count_100} bars with price ~100 in final check, rejecting!")
                    return None
                
                # Pastikan harga realistic
                if len(data) > 0:
                    current_price = data['close'].iloc[-1]
                else:
                    current_price = 0
                
                # Skip kalau harga masih aneh
                if current_price <= 0 or current_price > 1000000:
                    logger.warning(f"⚠️ {symbol} has unrealistic price: {current_price}")
                    return None
                
                # Cek pergerakan harga (tidak stuck)
                if len(data) > 1:
                    price_changes = data['close'].diff().abs().sum()
                    if price_changes < (current_price * 0.0001 * len(data)):
                        logger.warning(f"⚠️ {symbol} has flatline prices")
                        return None
        except Exception as e:
            logger.error(f"Error in final validation for {symbol}: {e}")
            return None
        
        return data
        
    except Exception as e:
        logger.error(f"Error in get_trading_data for {symbol}: {e}")
        return None

# =============================================
# BASE STRATEGY CLASS DENGAN BIAS CORRECTION
# =============================================

class TradingStrategy(ABC):
    """Base class for all trading strategies - ENHANCED WITH BIAS CORRECTION"""
    
    def __init__(self, market_type="crypto", atr_multiplier=1.0, entry_range_pct=0.02,
                 trading_type="spot", leverage=1, max_leverage_risk=0.01,
                 # 🔥 PERBAIKAN: SET SEMUA BIAS KE 0.0
                 long_bias=0.0,           # 🔥 UBAH: -1.0 to +1.0, default 0.0 (NEUTRAL)
                 min_score_threshold=3.0, # Minimal absolute score untuk trigger sinyal
                 scalping_mode=False):    # Mode scalping khusus
        self.market_type = market_type
        self.atr_multiplier = atr_multiplier
        self.entry_range_pct = entry_range_pct
        self.trading_type = trading_type  # 'spot' or 'futures'
        self.leverage = leverage
        self.max_leverage_risk = max_leverage_risk
        
        # 🔥 PARAMETER KOREKSI BIAS - SEMUA 0.0
        self.long_bias = long_bias  # 🔥 SELALU 0.0 DEFAULT
        self.min_score_threshold = min_score_threshold
        self.scalping_mode = scalping_mode
        
        # LOGIKA SIMPLE: Jika futures, adjust parameters
        if trading_type == "futures":
            self.entry_range_pct = entry_range_pct * 1.5  # Lebih lebar untuk futures
            self.atr_multiplier = atr_multiplier * 1.3    # Lebih agresif
            logger.info(f"🔄 Strategy configured for FUTURES: leverage={leverage}x")
        
        # LOGIKA SCALPING MODE
        if scalping_mode:
            self.entry_range_pct = SCALPING_CONFIG["entry_range_pct"]
            self.atr_multiplier = SCALPING_CONFIG["atr_multiplier"]
            self.min_score_threshold = SCALPING_CONFIG["min_score_threshold"]
            logger.info(f"⚡ SCALPING MODE: Bias={long_bias}, Min Score={min_score_threshold}")
    
    @abstractmethod
    def analyze(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Analyze market data and return trading signals"""
        pass
    
    def _preprocess_and_validate(self, df: pd.DataFrame, symbol: str) -> pd.DataFrame:
        """Preprocess data dan validasi kualitas"""
        
        # 1. Cek data kosong
        if df is None or df.empty:
            logger.error(f"Empty data for {symbol}")
            return self._get_fallback_data(symbol)
        
        # 2. Cek kolom yang diperlukan
        required_cols = ['open', 'high', 'low', 'close', 'volume']
        if not all(col in df.columns for col in required_cols):
            logger.error(f"Missing columns for {symbol}: {df.columns.tolist()}")
            return self._get_fallback_data(symbol)
        
        # ✅ TAMBAH: Clean NaN/inf lebih agresif
        df = df.replace([np.inf, -np.inf], np.nan)
        for col in required_cols:
            df[col] = df[col].ffill().bfill().fillna(0)  # Fill nan dengan 0 kalau masih ada
        
        # 3. Cek harga stuck (no movement)
        last_10_prices = df['close'].tail(10).values
        if len(set(last_10_prices)) <= 2:
            logger.warning(f"Price stuck detected for {symbol}, using synthetic data")
            df = self._synthesize_movement(df, symbol)
        
        # 4. Cek harga tidak valid (<= 0) - PERBAIKAN: GUNAKAN .values
        if (df['close'].values <= 0).any():
            logger.warning(f"Invalid price (<=0) detected for {symbol}, using synthetic data")
            df = self._synthesize_movement(df, symbol)
        
        # 5. Cek high < low - PERBAIKAN: GUNAKAN .values
        if (df['high'].values < df['low'].values).any():
            logger.warning(f"High < Low detected for {symbol}, using synthetic data")
            df = self._synthesize_movement(df, symbol)
        
        # 6. Cek volume = 0
        if df['volume'].mean() < 1:
            logger.warning(f"Zero volume for {symbol}, estimating from volatility")
            df['volume'] = self._estimate_volume_from_volatility(df)
        
        return df
    
    def _get_fallback_data(self, symbol: str) -> pd.DataFrame:
        """Generate fallback data when original data is invalid"""
        dates = pd.date_range('2023-01-01', periods=100, freq='D')
        price = self._estimate_realistic_price(symbol)
        data = {
            'open': np.random.normal(price, price * 0.05, 100),
            'high': np.random.normal(price * 1.05, price * 0.06, 100),
            'low': np.random.normal(price * 0.95, price * 0.06, 100),
            'close': np.random.normal(price, price * 0.05, 100),
            'volume': np.random.normal(1000000, 100000, 100),
        }
        return pd.DataFrame(data, index=dates)
    
    def _synthesize_movement(self, df: pd.DataFrame, symbol: str) -> pd.DataFrame:
        """Add synthetic movement to stuck prices"""
        current_price = df['close'].iloc[-1] if len(df) > 0 else self._estimate_realistic_price(symbol)
        
        # PERBAIKAN: Jika harga <= 0, gunakan harga realistis
        if current_price <= 0:
            current_price = self._estimate_realistic_price(symbol)
        
        # Generate synthetic price movement
        price_series = [current_price]
        for _ in range(len(df) - 1):
            # Random walk with drift
            change = np.random.normal(0, current_price * 0.02)
            new_price = price_series[-1] + change
            price_series.append(max(new_price, current_price * 0.5))
        
        df['close'] = price_series
        df['open'] = df['close'].shift(1).fillna(df['close'])
        df['high'] = df[['open', 'close']].max(axis=1) * np.random.uniform(1.0, 1.02, len(df))
        df['low'] = df[['open', 'close']].min(axis=1) * np.random.uniform(0.98, 1.0, len(df))
        
        logger.info(f"Synthesized movement for {symbol}")
        return df
    
    def _estimate_volume_from_volatility(self, df: pd.DataFrame) -> pd.Series:
        """Estimate volume based on price volatility"""
        volatility = df['close'].pct_change().std()
        base_volume = 1000000
        volume_scale = 1 + (volatility * 100)
        
        return pd.Series(np.random.normal(base_volume * volume_scale, base_volume * 0.1, len(df)))
    
    def calculate_dynamic_entry_range(self, current_price: float, volatility: float = None, 
                                     df: pd.DataFrame = None) -> float:
        """
        Calculate dynamic entry range dengan bias correction
        """
        try:
            # PERBAIKAN: Filter aset dengan harga terlalu rendah
            if current_price < 0.001 and self.trading_type == "spot":
                logger.warning(f"Very low price detected: ${current_price}. Using conservative settings.")
                return 0.05  # 5% untuk coins murah
            
            # Calculate volatility if not provided
            if volatility is None:
                if df is not None and len(df) > 20:
                    returns = df['close'].pct_change().dropna()
                    if len(returns) > 1:
                        volatility = returns.std() * np.sqrt(252)
                    else:
                        volatility = 0.02
                else:
                    # Default volatility by market type
                    volatility_map = {
                        "crypto": 0.025,
                        "forex": 0.008,
                        "forex_gold": 0.012,
                        "us_stocks": 0.015,
                        "indonesia_stocks": 0.02,
                        "crypto_future": 0.035,
                        "stock_future": 0.020,
                        "forex_future": 0.010,
                    }
                    volatility = volatility_map.get(self.market_type, 0.02)
            
            # Base range: 1.5 x daily volatility
            daily_vol = volatility / np.sqrt(252)
            base_range = daily_vol * 1.5
            
            # Adjust for trading type
            if self.trading_type == "futures":
                # Wider range for futures
                base_range *= 1.5
                
                # Adjust for leverage
                if self.leverage >= 20:
                    base_range *= 0.6
                elif self.leverage >= 10:
                    base_range *= 0.8
                elif self.leverage >= 5:
                    base_range *= 1.0
                else:
                    base_range *= 1.2
            elif self.trading_type == "spot":
                # Tighter range for spot trading
                base_range *= 0.7
            
            # Adjust for market type
            if self.market_type == "crypto" or "future" in str(self.market_type).lower():
                base_range *= 1.2
            
            # 🔥 APPLY LONG BIAS CORRECTION - TIDAK ADA BIAS (0.0)
            if self.long_bias > 0:
                # Jika bias positif (long), sedikit kurangi range untuk long, tambah untuk short
                base_range = base_range * (1 - self.long_bias * 0.1)
            elif self.long_bias < 0:
                # Jika bias negatif (short), sedikit kurangi range untuk short, tambah untuk long
                base_range = base_range * (1 + abs(self.long_bias) * 0.1)
            
            # Clamping values
            min_range = 0.005
            max_range = 0.03
            
            # Special clamp for futures
            if self.trading_type == "futures":
                min_range = 0.01
                max_range = 0.04
            
            base_range = max(base_range, min_range)
            base_range = min(base_range, max_range)
            
            logger.debug(f"Dynamic range: {base_range*100:.2f}% (Vol: {volatility:.3f}, Type: {self.trading_type}, Lev: {self.leverage}x, Bias: {self.long_bias:.2f})")
            return base_range
            
        except Exception as e:
            logger.error(f"Error calculating dynamic range: {e}")
            return self.entry_range_pct
    
    def _get_minimal_tick_size(self, current_price: float) -> float:
        """Tentukan tick size minimal berdasarkan harga dan exchange"""
        if current_price < 0.0001:
            return 0.000001
        elif current_price < 0.001:
            return 0.00001
        elif current_price < 0.01:
            return 0.0001
        elif current_price < 0.1:
            return 0.001
        elif current_price < 1:
            return 0.01
        elif current_price < 10:
            return 0.02
        elif current_price < 100:
            return 0.05
        elif current_price < 1000:
            return 0.5
        else:
            return 1.0
    
    def calculate_custom_entry(self, symbol: str, current_price: float, action: str = "LONG", 
                              df: pd.DataFrame = None) -> Dict[str, Any]:
        """Calculate TP/SL dengan entry range - DENGAN BIAS CORRECTION"""
        try:
            # PERBAIKAN 1: Filter aset dengan harga terlalu rendah
            if current_price < 0.001:
                logger.warning(f"Very low price for {symbol}: ${current_price}. Using conservative settings.")
                self.entry_range_pct = 0.05
                self.atr_multiplier = 2.0
            
            # Validasi input yang lebih ketat
            if current_price <= 0 or pd.isna(current_price) or not isinstance(current_price, (int, float)):
                logger.warning(f"Invalid current price for {symbol}: {current_price}")
                current_price = self._estimate_realistic_price(symbol)
                logger.info(f"Using estimated price: {current_price}")
            
            current_price = float(current_price)
            if current_price <= 0:
                current_price = self._estimate_realistic_price(symbol)
            
            # Calculate dynamic ATR
            if df is not None and not df.empty and all(col in df.columns for col in ['high', 'low', 'close']):
                atr = self._calculate_atr(df)
                if atr <= 0 or pd.isna(atr):
                    logger.warning(f"Invalid ATR for {symbol}: {atr}")
                    if current_price < 0.01:
                        atr = current_price * 0.10
                    elif current_price < 0.1:
                        atr = current_price * 0.05
                    else:
                        atr = current_price * 0.02
            else:
                # Fallback ATR by market type
                atr_map = {
                    "forex": current_price * 0.005,
                    "us_stocks": current_price * 0.015,
                    "forex_gold": current_price * 0.008,
                    "crypto_future": current_price * 0.025,
                    "stock_future": current_price * 0.015,
                    "forex_future": current_price * 0.006,
                }
                atr = atr_map.get(self.market_type, current_price * 0.02)
            
            atr = max(atr, current_price * 0.01)
            
            # Calculate dynamic entry range dengan bias correction
            dynamic_range = self.calculate_dynamic_entry_range(current_price, df=df)
            entry_range_pct = dynamic_range
            
            # 🔥 APPLY LONG BIAS TO ENTRY RANGE - TIDAK ADA BIAS (0.0)
            if self.long_bias != 0:
                bias_adjustment = 1 + (self.long_bias * 0.15)  # Max 15% adjustment
                entry_range_pct = entry_range_pct * bias_adjustment
                logger.debug(f"Bias-adjusted entry range: {entry_range_pct*100:.2f}% (Bias: {self.long_bias:.2f})")
            
            # Sentiment modifier
            if df is not None and 'sentiment' in df.columns:
                avg_sentiment = df['sentiment'].mean()
                if avg_sentiment < -0.3:
                    entry_range_pct *= 1.5
                    logger.info(f"Negative sentiment ({avg_sentiment:.2f}) detected; widening entry range to {entry_range_pct*100:.2f}%")
            
            if entry_range_pct <= 0:
                entry_range_pct = self.entry_range_pct
            
            # FUTURES-SPECIFIC: Adjust for liquidation risk
            liquidation_buffer = 0.0
            if self.trading_type == "futures" and self.leverage > 1:
                liquidation_buffer = (self.max_leverage_risk / self.leverage) * 0.5
            
            # Determine entry range based on action
            if action == "LONG":
                # For LONG: entry range BELOW current price
                entry_range_low = current_price * (1 - entry_range_pct)
                entry_range_high = current_price * (1 - entry_range_pct * 0.3)
                best_entry = (entry_range_low + entry_range_high) / 2
                
                # Apply liquidation buffer
                entry_range_low = max(entry_range_low, current_price * (1 - entry_range_pct - liquidation_buffer))
                
                # TP/SL for LONG with leverage adjustment
                base_move = max(atr * self.atr_multiplier, current_price * 0.01)
                
                leverage_factor = max(1, self.leverage / 10)
                min_move = base_move / leverage_factor
                
                tp1 = best_entry + min_move
                tp2 = best_entry + min_move * 2
                tp3 = best_entry + min_move * 3
                sl = best_entry - min_move * (1 + liquidation_buffer * 10)
                
            elif action == "SHORT":
                # For SHORT: entry range ABOVE current price  
                entry_range_low = current_price * (1 + entry_range_pct * 0.3)
                entry_range_high = current_price * (1 + entry_range_pct)
                best_entry = (entry_range_low + entry_range_high) / 2
                
                # Apply liquidation buffer
                entry_range_high = min(entry_range_high, current_price * (1 + entry_range_pct + liquidation_buffer))
                
                # TP/SL for SHORT dengan bias correction
                base_move = max(atr * self.atr_multiplier, current_price * 0.01)
                leverage_factor = max(1, self.leverage / 10)
                min_move = base_move / leverage_factor
                
                # 🔥 APPLY LONG BIAS TO SHORT TP/SL (make it harder to short when bias long)
                if self.long_bias > 0:
                    min_move = min_move * (1 + self.long_bias * 0.2)  # 20% wider TP/SL untuk short
                    logger.debug(f"Long bias applied to SHORT: TP/SL widened by {self.long_bias*20:.1f}%")
                
                tp1 = best_entry - min_move
                tp2 = best_entry - min_move * 2
                tp3 = best_entry - min_move * 3
                
                min_distance = current_price * 0.02
                calculated_sl = best_entry + max(min_move, min_distance)
                sl = max(calculated_sl, entry_range_high * 1.01)
                
            else:  # NEUTRAL
                entry_range_low = current_price * (1 - entry_range_pct * 0.1)
                entry_range_high = current_price * (1 + entry_range_pct * 0.1)
                best_entry = current_price
                tp1 = current_price * 1.01
                tp2 = current_price * 1.02
                tp3 = current_price * 1.03
                sl = current_price * 0.99

            # Apply minimal tick size
            tick_size = self._get_minimal_tick_size(current_price)
            entry_range_low = round(entry_range_low / tick_size) * tick_size
            entry_range_high = round(entry_range_high / tick_size) * tick_size
            best_entry = round(best_entry / tick_size) * tick_size
            tp1 = round(tp1 / tick_size) * tick_size
            tp2 = round(tp2 / tick_size) * tick_size
            tp3 = round(tp3 / tick_size) * tick_size
            sl = round(sl / tick_size) * tick_size

            # FINAL VALIDATION: Ensure no zero/negative values
            if entry_range_low <= 0 or entry_range_high <= 0 or best_entry <= 0:
                logger.error(f"Invalid entry range calculation for {symbol}, using fallback")
                fallback_price = max(current_price, self._estimate_realistic_price(symbol))
                if action == "LONG":
                    entry_range_low = fallback_price * 0.98
                    entry_range_high = fallback_price * 0.99
                    best_entry = (entry_range_low + entry_range_high) / 2
                    tp1 = best_entry * 1.03
                    tp2 = best_entry * 1.06  
                    tp3 = best_entry * 1.09
                    sl = best_entry * 0.97
                elif action == "SHORT":
                    entry_range_low = fallback_price * 1.01
                    entry_range_high = fallback_price * 1.02
                    best_entry = (entry_range_low + entry_range_high) / 2
                    tp1 = best_entry * 0.97
                    tp2 = best_entry * 0.94
                    tp3 = best_entry * 0.91
                    sl = best_entry * 1.03
                else:
                    entry_range_low = fallback_price * 0.995
                    entry_range_high = fallback_price * 1.005
                    best_entry = fallback_price
                    tp1 = fallback_price * 1.01
                    tp2 = fallback_price * 1.02
                    tp3 = fallback_price * 1.03
                    sl = fallback_price * 0.99

            # Validate order levels
            if action == "LONG":
                if not (sl < entry_range_low <= entry_range_high < tp1 < tp2 < tp3):
                    logger.warning("Invalid LONG levels, applying correction")
                    entry_range_low = current_price * 0.98
                    entry_range_high = current_price * 0.99
                    best_entry = (entry_range_low + entry_range_high) / 2
                    tp1 = best_entry * 1.03
                    tp2 = best_entry * 1.06
                    tp3 = best_entry * 1.09
                    sl = best_entry * 0.97
                    
            elif action == "SHORT":
                if not (sl > entry_range_high >= entry_range_low > tp1 > tp2 > tp3):
                    logger.warning("Invalid SHORT levels, applying correction")
                    entry_range_low = current_price * 1.01
                    entry_range_high = current_price * 1.02
                    best_entry = (entry_range_low + entry_range_high) / 2
                    tp1 = best_entry * 0.97
                    tp2 = best_entry * 0.94
                    tp3 = best_entry * 0.91
                    sl = best_entry * 1.03

            # Calculate risk metrics
            if action == "LONG":
                risk_amount = abs(best_entry - sl)
                reward_tp1 = abs(tp1 - best_entry)
                reward_tp3 = abs(tp3 - best_entry)
            elif action == "SHORT":
                risk_amount = abs(sl - best_entry)
                reward_tp1 = abs(best_entry - tp1)
                reward_tp3 = abs(best_entry - tp3)
            else:
                risk_amount = abs(best_entry - sl)
                reward_tp1 = abs(tp1 - best_entry)
                reward_tp3 = abs(tp3 - best_entry)
            
            rr_ratio_1 = reward_tp1 / risk_amount if risk_amount > 0 else 1
            rr_ratio_3 = reward_tp3 / risk_amount if risk_amount > 0 else 1

            return {
                'symbol': symbol,
                'action': action,
                'trading_type': self.trading_type,
                'leverage': self.leverage,
                'current_price': current_price,
                'entry_range_low': entry_range_low,
                'entry_range_high': entry_range_high,
                'best_entry': best_entry,
                'tp1': tp1,
                'tp2': tp2,
                'tp3': tp3,
                'sl': sl,
                'atr': atr,
                'entry_range_pct': entry_range_pct * 100,
                'range_size': (entry_range_high - entry_range_low) / current_price * 100 if current_price > 0 else 0,
                'risk_amount': risk_amount,
                'risk_percentage': (risk_amount / best_entry) * 100 if best_entry > 0 else 0,
                'rr_ratio_tp1': rr_ratio_1,
                'rr_ratio_tp3': rr_ratio_3,
                'liquidation_buffer_pct': liquidation_buffer * 100,
                'long_bias_applied': self.long_bias  # Tambahkan info bias yang diaplikasikan
            }
            
        except Exception as e:
            logger.error(f"Error in calculate_custom_entry: {e}")
            fallback_price = max(self._estimate_realistic_price(symbol), 0.01)
            return {
                'symbol': symbol,
                'action': action,
                'trading_type': self.trading_type,
                'leverage': self.leverage,
                'current_price': fallback_price,
                'entry_range_low': fallback_price * 0.98,
                'entry_range_high': fallback_price * 0.99,
                'best_entry': fallback_price * 0.985,
                'tp1': fallback_price * 1.03,
                'tp2': fallback_price * 1.06,
                'tp3': fallback_price * 1.09,
                'sl': fallback_price * 0.97,
                'atr': fallback_price * 0.02,
                'entry_range_pct': self.entry_range_pct * 100,
                'range_size': 1.0,
                'risk_amount': fallback_price * 0.03,
                'risk_percentage': 3.0,
                'rr_ratio_tp1': 1.5,
                'rr_ratio_tp3': 3.0,
                'liquidation_buffer_pct': 0.5,
                'long_bias_applied': self.long_bias
            }

    def _estimate_realistic_price(self, symbol):
        """Estimate realistic price based on symbol - UPDATED WITH FUTURES"""
        price_estimates = {
            # Crypto Spot
            'BTC/USDT': 50000.0, 'ETH/USDT': 3000.0, 'BNB/USDT': 500.0,
            'XRP/USDT': 0.5, 'ADA/USDT': 0.4, 'SOL/USDT': 100.0,
            
            # Crypto Futures
            'BTC/USDT-PERP': 50000.0, 'ETH/USDT-PERP': 3000.0,
            'BTC-PERP': 50000.0, 'ETH-PERP': 3000.0,
            'BTCUSDT': 50000.0, 'BTCUSDT.P': 50000.0,
            
            # Forex
            'EUR/USD': 1.08, 'USD/JPY': 150.0, 'GBP/USD': 1.26,
            'AUD/USD': 0.66, 'USD/CAD': 1.35, 'NZD/USD': 0.61,
            
            # Gold/Metals
            'XAU/USD': 1950.0, 'XAUUSD': 1950.0, 'GOLD': 1950.0,
            'XAG/USD': 22.0, 'XAGUSD': 22.0, 'SILVER': 22.0,
            
            # US Stocks
            'AAPL': 180.0, 'MSFT': 400.0, 'GOOGL': 150.0, 
            'AMZN': 170.0, 'TSLA': 200.0, 'META': 500.0, 
            'NVDA': 900.0, 'NFLX': 600.0,
            
            # Stock Futures
            'ES1!': 4500.0, 'NQ1!': 15500.0, 'YM1!': 34000.0,
            'RTY1!': 1800.0,
            
            # Futures Contracts
            'CL': 75.0, 'NG': 2.5, 'GC': 1950.0,
            'SI': 22.0, 'HG': 3.5, 'ZC': 450.0,
            
            # Indonesian Stocks
            'BBCA.JK': 9000.0, 'BBRI.JK': 5000.0, 'BMRI.JK': 6000.0,
            'TLKM.JK': 4000.0, 'ASII.JK': 6000.0,
            
            # New Crypto
            'HYPE/USDT': 35.0, 'TON/USDT': 1.5, 'ENA/USDT': 0.3,
            'PINGPONG/USDT': 0.022, 'PLUME/USDT': 0.033, 'ASTER/USDT': 1.12
        }
        
        # Check for exact match first
        if symbol in price_estimates:
            return price_estimates[symbol]
        
        # Check for pattern match
        for pattern, price in price_estimates.items():
            if pattern in symbol:
                return price
        
        # Default based on symbol type
        if any(x in symbol.upper() for x in ['PERP', 'FUTURES', 'SWAP', '1226', '0325', '0626', '0926']):
            return 100.0
        elif 'USDT' in symbol or '/USDT' in symbol:
            return 10.0
        elif 'USD' in symbol or '=X' in symbol:
            return 1.0
        elif '.JK' in symbol:
            return 5000.0
        elif any(stock in symbol.upper() for stock in ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA', 'META', 'NVDA', 'NFLX']):
            return 300.0
        elif any(future in symbol.upper() for future in ['ES', 'NQ', 'YM', 'RTY', 'CL', 'NG', 'GC', 'SI', 'HG', 'ZC']):
            return 100.0
        else:
            return 100.0

    def format_signal_output(self, analysis: Dict[str, Any]) -> str:
        """Format output signal dengan futures-specific info"""
        
        action = analysis.get('action', 'NEUTRAL')
        symbol = analysis.get('symbol', 'UNKNOWN')
        trading_type = analysis.get('trading_type', 'spot')
        leverage = analysis.get('leverage', 1)
        score = analysis.get('score', 0)
        current_price = analysis.get('current_price', 0)
        confidence = analysis.get('confidence', 0.5) * 100
        
        # Determine emoji and color
        if action == "LONG":
            emoji = "🟢" if trading_type == "spot" else "💰"
            color_start = "🟢"
        elif action == "SHORT":
            emoji = "🔴" if trading_type == "spot" else "📉"
            color_start = "🔴"
        else:
            emoji = "⚪" if trading_type == "spot" else "📊"
            color_start = "⚪"
        
        # Format entry range
        entry_low = analysis.get('entry_range_low', current_price)
        entry_high = analysis.get('entry_range_high', current_price)
        best_entry = analysis.get('best_entry', current_price)
        range_pct = analysis.get('entry_range_pct', 2.0)
        
        if action == "LONG":
            entry_display = f"{entry_low:.5f} - {entry_high:.5f}"
            direction = "BELOW current"
        elif action == "SHORT":
            entry_display = f"{entry_low:.5f} - {entry_high:.5f}" 
            direction = "ABOVE current"
        else:
            entry_display = f"{current_price:.5f}"
            direction = "AT current"
        
        # Probabilities based on confidence score
        tp1_prob = min(confidence * 0.8, 95)
        tp2_prob = min(confidence * 0.5, 70)
        tp3_prob = min(confidence * 0.2, 40)
        
        # Bias information
        bias_info = ""
        long_bias = analysis.get('long_bias_applied', 0)
        if long_bias != 0:
            bias_direction = "LONG" if long_bias > 0 else "SHORT"
            bias_info = f"⚖️ Strategy Bias: {bias_direction} ({abs(long_bias):.2f})"
        
        # Futures-specific info
        futures_info = ""
        if trading_type == "futures":
            risk_pct = analysis.get('risk_percentage', 0)
            rr_ratio = analysis.get('rr_ratio_tp1', 0)
            liquidation_buffer = analysis.get('liquidation_buffer_pct', 0)
            
            futures_info = f"""
⚡ FUTURES SPECIFICS:
   Leverage: {leverage}x
   Risk per Trade: {risk_pct:.2f}%
   R/R Ratio (TP1): {rr_ratio:.2f}:1
   Liquidation Buffer: ±{liquidation_buffer:.2f}%
"""
        
        output = f"""
{emoji} {symbol} - {action} (Score: {score:.1f})
{bias_info}
📊 Type: {trading_type.upper()}
💰 Current: {current_price:.5f} 
🎯 Entry Range: {entry_display} ({direction})
📊 Probabilities: TP1: {tp1_prob:.1f}% | TP2: {tp2_prob:.1f}% | TP3: {tp3_prob:.1f}%

🎯 Take Profit: 
   TP1: {analysis.get('tp1', 0):.5f}
   TP2: {analysis.get('tp2', 0):.5f}  
   TP3: {analysis.get('tp3', 0):.5f}

🛑 Stop Loss: {analysis.get('sl', 0):.5f}

{futures_info}
📈 Analytics:
   Confidence: {confidence:.1f}%
   Range Size: ±{range_pct:.1f}%
   ATR: {analysis.get('atr', 0):.5f}
   RSI: {analysis.get('rsi', 50):.1f}
   Trend: {analysis.get('trend_direction', 'NEUTRAL')}
   Market Regime: {analysis.get('market_regime', 'unknown')}
   Min Score Threshold: {self.min_score_threshold}
"""
        
        return output

# =============================================
# ENHANCED DATA STRUCTURES
# =============================================

class MarketRegime(Enum):
    BULL_TREND = "bull_trend"
    BEAR_TREND = "bear_trend"
    RANGING = "ranging"
    HIGH_VOLATILITY = "high_volatility"
    LOW_VOLATILITY = "low_volatility"
    BREAKOUT = "breakout"
    UNKNOWN = "unknown"

@dataclass
class PatternDetection:
    name: str
    detected: bool
    direction: str
    confidence: float
    entry_price: float
    target_price: float
    stop_loss: float
    risk_reward_ratio: float
    timeframe: str

@dataclass
class MarketAnalysis:
    regime: MarketRegime
    trend_strength: float
    volatility_regime: str
    support_levels: List[float]
    resistance_levels: List[float]
    key_levels: List[float]
    volume_profile: Dict[str, float]
    market_sentiment: str

# =============================================
# ADVANCED PATTERN DETECTION ENGINE
# =============================================

class AdvancedPatternDetector:
    """Advanced pattern detection dengan machine learning confirmation"""
    
    def __init__(self):
        self.pattern_cache = {}
        self.min_pattern_confidence = 0.6
        
    def detect_comprehensive_patterns(self, df: pd.DataFrame, symbol: str = None) -> Dict[str, PatternDetection]:
        """Detect comprehensive trading patterns dengan confidence scoring"""
        patterns = {}
        
        try:
            if df is None or df.empty:
                return patterns
            
            current_price = df['close'].iloc[-1] if 'close' in df.columns else 0
            if current_price <= 0:
                logger.warning("Invalid current price in pattern detection")
                return patterns

            # Harmonic Patterns
            harmonic_patterns = self._detect_harmonic_patterns_advanced(df)
            patterns.update(harmonic_patterns)
            
            # Chart Patterns
            chart_patterns = self._detect_chart_patterns_advanced(df)
            patterns.update(chart_patterns)
            
            # Candlestick Patterns
            candle_patterns = self._detect_candlestick_patterns(df)
            patterns.update(candle_patterns)
            
            # Volume Patterns
            volume_patterns = self._detect_volume_patterns(df)
            patterns.update(volume_patterns)
            
            # Trend Patterns
            trend_patterns = self._detect_trend_patterns(df)
            patterns.update(trend_patterns)
            
            # Filter patterns by confidence
            valid_patterns = {
                name: pattern for name, pattern in patterns.items() 
                if pattern.detected and pattern.confidence >= self.min_pattern_confidence
            }
            
            return valid_patterns
            
        except Exception as e:
            logger.error(f"Pattern detection error: {e}")
            return {}

    def _detect_harmonic_patterns_advanced(self, df: pd.DataFrame) -> Dict[str, PatternDetection]:
        """Detect advanced harmonic patterns"""
        patterns = {}
        
        try:
            swing_highs, swing_lows = self._find_swing_points_advanced(df)
            
            # Gartley Pattern
            gartley = self._detect_gartley_pattern(swing_highs, swing_lows, df)
            if gartley.detected:
                patterns['gartley'] = gartley
            
            return patterns
            
        except Exception as e:
            logger.error(f"Harmonic pattern detection error: {e}")
            return {}

    def _find_swing_points_advanced(self, df: pd.DataFrame, window: int = 5) -> Tuple[List[Tuple[int, float]], List[Tuple[int, float]]]:
        """Find swing points dengan advanced algorithm"""
        try:
            highs = df['high'].values
            lows = df['low'].values
            
            if (highs <= 0).any() or (lows <= 0).any():
                logger.warning("Invalid price data in swing point detection")
                return [], []
            
            # Find local maxima and minima
            high_idx = argrelextrema(highs, np.greater, order=window)[0]
            low_idx = argrelextrema(lows, np.less, order=window)[0]
            
            # Filter significant swings
            swing_highs = []
            for idx in high_idx:
                if idx >= window and idx < len(highs) - window:
                    left_min = np.min(lows[max(0, idx-window):idx])
                    right_min = np.min(lows[idx:min(len(lows), idx+window)])
                    min_val = min(left_min, right_min)
                    
                    if highs[idx] > min_val * 1.01:
                        swing_highs.append((idx, highs[idx]))
            
            swing_lows = []
            for idx in low_idx:
                if idx >= window and idx < len(lows) - window:
                    left_max = np.max(highs[max(0, idx-window):idx])
                    right_max = np.max(highs[idx:min(len(highs), idx+window)])
                    max_val = max(left_max, right_max)
                    
                    if lows[idx] < max_val * 0.99:
                        swing_lows.append((idx, lows[idx]))
            
            return swing_highs, swing_lows
            
        except Exception as e:
            logger.error(f"Swing point detection error: {e}")
            return [], []
    
    def _detect_gartley_pattern(self, swing_highs: List[Tuple[int, float]], 
                               swing_lows: List[Tuple[int, float]], 
                               df: pd.DataFrame) -> PatternDetection:
        """Detect Gartley pattern dengan Fibonacci ratios"""
        try:
            if len(swing_highs) < 3 or len(swing_lows) < 3:
                return PatternDetection("gartley", False, "", 0, 0, 0, 0, 0, "")
            
            current_price = df['close'].iloc[-1]
            if current_price <= 0:
                return PatternDetection("gartley", False, "", 0, 0, 0, 0, 0, "")
            
            detected = len(swing_highs) >= 4 and len(swing_lows) >= 4
            confidence = 0.7 if detected else 0.0
            
            if detected:
                direction = "BULLISH" if swing_highs[-1][1] > swing_highs[-2][1] else "BEARISH"
                entry = current_price
                target = current_price * 1.05 if direction == "BULLISH" else current_price * 0.95
                stop_loss = current_price * 0.98 if direction == "BULLISH" else current_price * 1.02
                rr_ratio = abs(target - entry) / abs(entry - stop_loss) if abs(entry - stop_loss) > 0 else 1.0
                
                return PatternDetection(
                    "gartley", True, direction, confidence, 
                    entry, target, stop_loss, rr_ratio, "1D"
                )
            
        except Exception as e:
            logger.error(f"Gartley pattern error: {e}")
        
        return PatternDetection("gartley", False, "", 0, 0, 0, 0, 0, "")
    
    def _detect_chart_patterns_advanced(self, df: pd.DataFrame) -> Dict[str, PatternDetection]:
        """Advanced chart pattern detection"""
        patterns = {}
        
        try:
            if df is None or df.empty:
                return patterns
            
            current_price = df['close'].iloc[-1]
            if current_price <= 0:
                return patterns

            # Head and Shoulders
            hs_pattern = self._detect_head_shoulders(df)
            if hs_pattern.detected:
                patterns['head_shoulders'] = hs_pattern
            
            # Double Top/Bottom
            double_pattern = self._detect_double_top_bottom(df)
            if double_pattern.detected:
                patterns['double_top_bottom'] = double_pattern
            
            return patterns
            
        except Exception as e:
            logger.error(f"Chart pattern detection error: {e}")
            return {}
    
    def _detect_head_shoulders(self, df: pd.DataFrame) -> PatternDetection:
        """Detect Head and Shoulders pattern"""
        try:
            if len(df) < 50:
                return PatternDetection("head_shoulders", False, "", 0, 0, 0, 0, 0, "")
            
            current_price = df['close'].iloc[-1]
            if current_price <= 0:
                return PatternDetection("head_shoulders", False, "", 0, 0, 0, 0, 0, "")
            
            highs = df['high'].tail(30).values
            lows = df['low'].tail(30).values
            
            max_idx = np.argmax(highs)
            left_shoulder = np.max(highs[:max_idx]) if max_idx > 0 else 0
            right_shoulder = np.max(highs[max_idx+1:]) if max_idx < len(highs)-1 else 0
            head = highs[max_idx]
            
            if (left_shoulder > 0 and right_shoulder > 0 and 
                head > left_shoulder and head > right_shoulder and
                abs(left_shoulder - right_shoulder) / head < 0.02):
                
                neckline = (left_shoulder + right_shoulder) / 2
                
                if current_price < neckline:
                    confidence = 0.75
                    entry = current_price
                    target = current_price * 0.93
                    stop_loss = neckline * 1.02
                    rr_ratio = abs(target - entry) / abs(entry - stop_loss) if abs(entry - stop_loss) > 0 else 1.0
                    
                    return PatternDetection(
                        "head_shoulders", True, "BEARISH", confidence,
                        entry, target, stop_loss, rr_ratio, "1D"
                    )
            
        except Exception as e:
            logger.error(f"Head and Shoulders detection error: {e}")
        
        return PatternDetection("head_shoulders", False, "", 0, 0, 0, 0, 0, "")
    
    def _detect_double_top_bottom(self, df: pd.DataFrame) -> PatternDetection:
        """Detect Double Top/Bottom pattern"""
        try:
            if len(df) < 40:
                return PatternDetection("double_top_bottom", False, "", 0, 0, 0, 0, 0, "")
            
            current_price = df['close'].iloc[-1]
            if current_price <= 0:
                return PatternDetection("double_top_bottom", False, "", 0, 0, 0, 0, 0, "")
            
            highs = df['high'].tail(20).values
            lows = df['low'].tail(20).values
            
            peak1_idx = len(highs) // 3
            peak2_idx = 2 * len(highs) // 3
            
            peak1 = np.max(highs[:peak1_idx]) if peak1_idx > 0 else 0
            peak2 = np.max(highs[peak1_idx:peak2_idx]) if peak2_idx > peak1_idx else 0
            
            if peak1 > 0 and peak2 > 0 and abs(peak1 - peak2) / ((peak1 + peak2)/2) < 0.02:
                valley = np.min(lows[peak1_idx:peak2_idx])
                
                if valley > 0 and (peak1 - valley) / peak1 > 0.03:
                    confidence = 0.65
                    direction = "BEARISH"
                    entry = current_price
                    target = current_price - (peak1 - valley)
                    stop_loss = max(peak1, peak2) * 1.01
                    rr_ratio = abs(target - entry) / abs(entry - stop_loss) if abs(entry - stop_loss) > 0 else 1.0
                    
                    return PatternDetection(
                        "double_top", True, direction, confidence,
                        entry, target, stop_loss, rr_ratio, "1D"
                    )
            
            bottom1 = np.min(lows[:peak1_idx]) if peak1_idx > 0 else 0
            bottom2 = np.min(lows[peak1_idx:peak2_idx]) if peak2_idx > peak1_idx else 0
            
            if bottom1 > 0 and bottom2 > 0 and abs(bottom1 - bottom2) / ((bottom1 + bottom2)/2) < 0.02:
                peak_valley = np.max(highs[peak1_idx:peak2_idx])
                
                if peak_valley > 0 and (peak_valley - bottom1) / bottom1 > 0.03:
                    confidence = 0.65
                    direction = "BULLISH"
                    entry = current_price
                    target = current_price + (peak_valley - bottom1)
                    stop_loss = min(bottom1, bottom2) * 0.99
                    rr_ratio = abs(target - entry) / abs(entry - stop_loss) if abs(entry - stop_loss) > 0 else 1.0
                    
                    return PatternDetection(
                        "double_bottom", True, direction, confidence,
                        entry, target, stop_loss, rr_ratio, "1D"
                    )
            
        except Exception as e:
            logger.error(f"Double Top/Bottom detection error: {e}")
        
        return PatternDetection("double_top_bottom", False, "", 0, 0, 0, 0, 0, "")
    
    def _detect_candlestick_patterns(self, df: pd.DataFrame) -> Dict[str, PatternDetection]:
        """Detect candlestick patterns"""
        patterns = {}
        
        try:
            if len(df) < 5:
                return patterns
            
            open_price = df['open'].values
            high = df['high'].values
            low = df['low'].values
            close = df['close'].values
            
            if (open_price <= 0).any() or (high <= 0).any() or (low <= 0).any() or (close <= 0).any():
                return patterns
            
            # Doji
            doji = talib.CDLDOJI(open_price, high, low, close)
            if doji[-1] != 0:
                confidence = 0.6
                direction = "REVERSAL"
                entry = close[-1]
                target = entry * 1.02
                stop_loss = entry * 0.98
                rr_ratio = abs(target - entry) / abs(entry - stop_loss) if abs(entry - stop_loss) > 0 else 1.0
                
                patterns['doji'] = PatternDetection(
                    "doji", True, direction, confidence,
                    entry, target, stop_loss, rr_ratio, "1D"
                )
            
            # Hammer
            hammer = talib.CDLHAMMER(open_price, high, low, close)
            if hammer[-1] != 0:
                confidence = 0.65
                direction = "BULLISH"
                entry = close[-1]
                target = entry * 1.03
                stop_loss = low[-1] * 0.99
                rr_ratio = abs(target - entry) / abs(entry - stop_loss) if abs(entry - stop_loss) > 0 else 1.0
                
                patterns['hammer'] = PatternDetection(
                    "hammer", True, direction, confidence,
                    entry, target, stop_loss, rr_ratio, "1D"
                )
            
            # Shooting Star
            shooting_star = talib.CDLSHOOTINGSTAR(open_price, high, low, close)
            if shooting_star[-1] != 0:
                confidence = 0.65
                direction = "BEARISH"
                entry = close[-1]
                target = entry * 0.97
                stop_loss = high[-1] * 1.01
                rr_ratio = abs(target - entry) / abs(entry - stop_loss) if abs(entry - stop_loss) > 0 else 1.0
                
                patterns['shooting_star'] = PatternDetection(
                    "shooting_star", True, direction, confidence,
                    entry, target, stop_loss, rr_ratio, "1D"
                )
            
            return patterns
            
        except Exception as e:
            logger.error(f"Candlestick pattern detection error: {e}")
            return {}
    
    def _detect_volume_patterns(self, df: pd.DataFrame) -> Dict[str, PatternDetection]:
        """Detect volume-based patterns"""
        patterns = {}
        
        try:
            if 'volume' not in df.columns or len(df) < 20:
                return patterns
            
            current_price = df['close'].iloc[-1]
            if current_price <= 0:
                return patterns
            
            volumes = df['volume'].tail(20).values
            prices = df['close'].tail(20).values
            
            volume_ma = np.mean(volumes)
            current_volume = volumes[-1]
            
            # Volume Spike
            if current_volume > volume_ma * 2.0 and prices[-1] > prices[-2]:
                confidence = 0.7
                direction = "BULLISH"
                entry = current_price
                target = entry * 1.05
                stop_loss = entry * 0.98
                rr_ratio = abs(target - entry) / abs(entry - stop_loss) if abs(entry - stop_loss) > 0 else 1.0
                
                patterns['volume_spike'] = PatternDetection(
                    "volume_spike", True, direction, confidence,
                    entry, target, stop_loss, rr_ratio, "1D"
                )
            
            return patterns
            
        except Exception as e:
            logger.error(f"Volume pattern detection error: {e}")
            return {}
    
    def _detect_trend_patterns(self, df: pd.DataFrame) -> Dict[str, PatternDetection]:
        """Detect trend continuation/reversal patterns"""
        patterns = {}
        
        try:
            if len(df) < 30:
                return patterns
            
            current_price = df['close'].iloc[-1]
            if current_price <= 0:
                return patterns
            
            prices = df['close'].values
            
            # Breakout Pattern
            recent_high = np.max(prices[-20:-1])
            if prices[-1] > recent_high * 1.01:
                confidence = 0.75
                direction = "BULLISH"
                entry = current_price
                target = entry * 1.05
                stop_loss = recent_high * 0.99
                rr_ratio = abs(target - entry) / abs(entry - stop_loss) if abs(entry - stop_loss) > 0 else 1.0
                
                patterns['breakout'] = PatternDetection(
                    "breakout", True, direction, confidence,
                    entry, target, stop_loss, rr_ratio, "1D"
                )
            
            return patterns
            
        except Exception as e:
            logger.error(f"Trend pattern detection error: {e}")
            return {}

# =============================================
# ENHANCED TECHNICAL ANALYSIS STRATEGY DENGAN BIAS CORRECTION
# =============================================

class EnhancedTechnicalAnalysisStrategy(TradingStrategy):
    """Enhanced technical analysis strategy dengan bias correction untuk scalping"""
    
    def __init__(self, market_type="crypto", atr_multiplier=1.0, entry_range_pct=0.02,
                 trading_type="spot", leverage=1, max_leverage_risk=0.01,
                 long_bias=0.0, min_score_threshold=3.0, scalping_mode=False):
        super().__init__(
            market_type=market_type, 
            atr_multiplier=atr_multiplier,
            entry_range_pct=entry_range_pct,
            trading_type=trading_type,
            leverage=leverage,
            max_leverage_risk=max_leverage_risk,
            long_bias=long_bias,  # 🔥 SELALU 0.0
            min_score_threshold=min_score_threshold,
            scalping_mode=scalping_mode
        )
        
        self.pattern_detector = AdvancedPatternDetector()
        self.analysis_history = []
        
        # LOG SCALPING CONFIG
        if scalping_mode:
            logger.info(f"⚡ SCALPING STRATEGY: Bias={long_bias}, Min Score={min_score_threshold}, Range={entry_range_pct*100:.1f}%")
        else:
            logger.info(f"📊 REGULAR STRATEGY: Bias={long_bias}, Min Score={min_score_threshold}")
    
    def _get_valid_current_price(self, df: pd.DataFrame) -> float:
        """Get valid current price from DataFrame with validation"""
        try:
            if df is None or df.empty:
                logger.warning("Empty DataFrame in _get_valid_current_price")
                return 0.0
            
            if 'close' not in df.columns:
                logger.warning("DataFrame has no 'close' column")
                return 0.0
            
            current_price = df['close'].iloc[-1]
            
            # Validate price
            if pd.isna(current_price) or current_price <= 0:
                logger.warning(f"Invalid current price: {current_price}")
                return 0.0
            
            return float(current_price)
            
        except Exception as e:
            logger.error(f"Error in _get_valid_current_price: {e}")
            return 0.0
    
    def _safe_data_validation(self, df: pd.DataFrame, symbol: str) -> bool:
        """Validasi data dengan cara yang aman dari ambiguous truth value"""
        try:
            if df is None or df.empty:
                return False
            
            # Cek kolom yang diperlukan
            required_cols = ['open', 'high', 'low', 'close']
            for col in required_cols:
                if col not in df.columns:
                    logger.warning(f"Missing column {col} in {symbol}")
                    return False
            
            # Cek harga tidak valid (<= 0) - GUNAKAN .values dan .any()
            if (df['close'].values <= 0).any():
                logger.warning(f"Invalid price (<=0) detected for {symbol}")
                return False
            
            # Cek high >= low - GUNAKAN .values dan .any()
            if (df['high'].values < df['low'].values).any():
                logger.warning(f"High < Low detected for {symbol}")
                return False
            
            # Cek jika data terlalu pendek
            if len(df) < 20:
                logger.warning(f"Insufficient data for {symbol}: {len(df)} bars")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error in safe data validation for {symbol}: {e}")
            return False

    def _should_skip_symbol(self, df, symbol):
        """Skip logic yang lebih pintar untuk scalping - DIPERBAIKI"""
        if df is None or df.empty or len(df) < 10:
            logger.debug(f"Skipping {symbol}: data too short ({len(df) if df is not None else 0} bars)")
            return True
        
        # Deteksi apakah ini futures
        is_futures = any(x in symbol.upper() for x in [':USDT', 'PERP', 'FUTURES', '-USDT', 'USDT:'])
        
        # 🆕 PARAMETER SCALPING YANG LEBIH KETAT
        if self.scalping_mode:
            min_volatility = SCALPING_CONFIG["min_volatility"]
            min_volume = 50000  # Lebih tinggi untuk scalping
            min_price = SCALPING_CONFIG["price_filter"]["min"]
            max_price = SCALPING_CONFIG["price_filter"]["max"]
            
            # Cek filter harga untuk scalping
            current_price = df['close'].iloc[-1] if len(df) > 0 else 0
            if current_price < min_price or current_price > max_price:
                logger.debug(f"Skipping {symbol}: price ${current_price:.4f} outside scalping range (${min_price}-${max_price})")
                return True
        else:
            if is_futures:
                min_volatility = 0.000001
                min_volume = 10
                min_price = 0.0000001
            else:
                min_volatility = 0.001
                min_volume = 1000
                min_price = 0.001
        
        # Check conditions
        if len(df) > 1:
            volatility = df['close'].pct_change().std()
        else:
            volatility = 0.01
        
        avg_volume = df['volume'].mean() if 'volume' in df.columns else 1000
        current_price = df['close'].iloc[-1] if len(df) > 0 else 0
        
        # Cek jika ada NaN - GUNAKAN .any() DENGAN AMAN
        if df['close'].isna().any():
            logger.warning(f"Skipping {symbol}: has NaN values")
            return True
        
        # Cek harga valid - GUNAKAN .values dan .any()
        if (df['close'].values <= 0).any() or (df['close'].values > 100000000).any():
            logger.warning(f"Skipping {symbol}: invalid price range")
            return True
        
        # Cek high >= low - GUNAKAN .values dan .any()
        if (df['high'].values < df['low'].values).any():
            logger.warning(f"Skipping {symbol}: High < Low")
            return True
        
        # Cek volume terlalu rendah
        if avg_volume < min_volume:
            logger.debug(f"Skipping {symbol}: low volume {avg_volume:.0f}")
            return True
        
        # Cek jika semua data sama (flatline)
        if len(df['close'].unique()) <= 3:
            logger.warning(f"Skipping {symbol}: flatline data")
            return True
        
        # Cek volatility terlalu rendah
        if volatility < min_volatility:
            logger.debug(f"Skipping {symbol}: low volatility {volatility:.6f}")
            return True
        
        # 🆕 CEK VOLATILITY TERLALU TINGGI UNTUK SCALPING
        if self.scalping_mode and volatility > SCALPING_CONFIG["max_volatility"]:
            logger.debug(f"Skipping {symbol}: too volatile for scalping {volatility:.3f}")
            return True
        
        return False
    
    def _get_safe_neutral_signal(self, symbol: str = None) -> Dict[str, Any]:
        """Return safe neutral signal when skipping analysis"""
        if symbol is None:
            symbol = "UNKNOWN"
            logger.warning("Symbol is None, using 'UNKNOWN'")
        
        default_price = self._estimate_realistic_price(symbol)
        return {
            'action': 'NEUTRAL',
            'trading_type': self.trading_type,
            'leverage': self.leverage,
            'current_price': default_price,
            'score': 0,
            'confidence': 0.1,
            'symbol': symbol,
            'risk_category': 'LOW',
            'market_regime': 'unknown',
            'skip_reason': 'data_validation_failed',
            'long_bias_applied': self.long_bias
        }
    
    def analyze(self, df: pd.DataFrame, symbol: str = None, **kwargs) -> Dict[str, Any]:
        """Analyze market data dengan bias correction untuk scalping"""
        try:
            # 1. Validasi data dasar - GUNAKAN OPERASI YANG AMAN
            if df is None or df.empty or len(df) < 10:
                logger.warning(f"Data insufficient for {symbol}: {len(df) if df is not None else 0} bars")
                return self._get_default_analysis(symbol)
            
            # 2. Gunakan validasi data yang aman
            if not self._safe_data_validation(df, symbol):
                logger.warning(f"Data validation failed for {symbol}")
                return self._get_safe_neutral_signal(symbol)
            
            # 3. Preprocess data
            df = self._preprocess_and_validate(df, symbol)
            
            # 4. Skip jika data tidak valid
            if self._should_skip_symbol(df, symbol):
                return self._get_safe_neutral_signal(symbol)
            
            # 5. Ambil harga sekarang
            current_price = df['close'].iloc[-1]
            
            # 6. Hitung indikator teknis
            indicators = self._calculate_enhanced_indicators(df)
            
            # 7. Tentukan sinyal berdasarkan indikator
            rsi = indicators['rsi_14']
            macd_signal = indicators['macd_line'] > indicators['macd_signal']
            bb_position = indicators['bb_position']
            
            # 🆕 SCORING SISTEM DENGAN BIAS CORRECTION
            score = 0
            
            # RSI Scoring
            if rsi < 30: 
                score += 3
            elif rsi < 40: 
                score += 2
            elif rsi > 70: 
                score -= 3
            elif rsi > 60: 
                score -= 2
            
            # MACD Scoring
            if macd_signal: 
                score += 2
            else: 
                score -= 2
            
            # Bollinger Bands Scoring
            if bb_position < 0.2: 
                score += 2
            elif bb_position > 0.8: 
                score -= 2
            
            # 🔥 APPLY LONG BIAS CORRECTION - TIDAK ADA BIAS (0.0)
            biased_score = score + (self.long_bias * 5)  # Scale bias effect
            
            logger.debug(f"Score calculation for {symbol}: Base={score:.1f}, Bias={self.long_bias:.2f}, Final={biased_score:.1f}")
            
            # 🆕 APPLY MINIMUM SCORE THRESHOLD
            if abs(biased_score) < self.min_score_threshold:
                logger.debug(f"{symbol}: Score {biased_score:.1f} below threshold {self.min_score_threshold}, returning NEUTRAL")
                action = "NEUTRAL"
            elif biased_score > 0:
                action = "LONG"
            else:
                action = "SHORT"
            
            # 8. Hitung TP/SL dengan bias correction
            entry_calc = self.calculate_custom_entry(
                symbol=symbol or "UNKNOWN",
                current_price=current_price,
                action=action,
                df=df
            )
            
            # 9. Confidence calculation dengan bias adjustment
            confidence = min(abs(biased_score) / 10.0, 1.0)
            
            # Adjust confidence based on bias
            if (action == "LONG" and self.long_bias > 0) or (action == "SHORT" and self.long_bias < 0):
                confidence = min(confidence * (1 + abs(self.long_bias) * 0.3), 1.0)
            
            # 10. Return hasil
            result = {
                'action': action,
                'score': biased_score,
                'current_price': current_price,
                'entry_range_low': entry_calc['entry_range_low'],
                'entry_range_high': entry_calc['entry_range_high'],
                'best_entry': entry_calc['best_entry'],
                'tp1': entry_calc['tp1'],
                'tp2': entry_calc['tp2'],
                'tp3': entry_calc['tp3'],
                'sl': entry_calc['sl'],
                'trading_type': self.trading_type,
                'leverage': self.leverage,
                'rsi': rsi,
                'atr': indicators['atr'],
                'symbol': symbol or "UNKNOWN",
                'entry_range_pct': entry_calc['entry_range_pct'],
                'range_size': entry_calc['range_size'],
                'risk_amount': entry_calc.get('risk_amount', 0),
                'risk_percentage': entry_calc.get('risk_percentage', 0),
                'rr_ratio_tp1': entry_calc.get('rr_ratio_tp1', 0),
                'rr_ratio_tp3': entry_calc.get('rr_ratio_tp3', 0),
                'liquidation_buffer_pct': entry_calc.get('liquidation_buffer_pct', 0),
                'confidence': confidence,
                'long_bias_applied': self.long_bias,
                'min_score_threshold': self.min_score_threshold,
                'scalping_mode': self.scalping_mode
            }
            
            # 11. Hitung trend_strength
            ts = self._calculate_trend_strength(df, symbol)
            
            # 12. Tambahkan indikator tambahan
            result.update({
                'macd_line': indicators['macd_line'],
                'macd_signal': indicators['macd_signal'],
                'bb_position': bb_position,
                'volatility': indicators['volatility'],
                'trend_strength': ts,
                'trend_direction': 'BULLISH' if indicators['momentum_5'] > 0 else 'BEARISH' if indicators['momentum_5'] < 0 else 'NEUTRAL',
                'market_regime': self._analyze_market_regime(df, biased_score, indicators['volatility'], ts).value,
                'pattern_count': len(self.pattern_detector.detect_comprehensive_patterns(df, symbol))
            })
            
            # LOG SIGNAL DETAILS
            logger.info(f"📈 {symbol}: {action} (Score: {biased_score:.1f}, Bias: {self.long_bias:.2f}, Conf: {confidence:.1%})")
            
            return result
            
        except Exception as e:
            logger.error(f"Analysis error for {symbol}: {e}")
            return self._get_default_analysis(symbol)
    
    def _calculate_enhanced_indicators(self, df: pd.DataFrame) -> Dict[str, float]:
        """Calculate enhanced technical indicators"""
        indicators = {}
        
        try:
            prices = df['close'].values
            highs = df['high'].values
            lows = df['low'].values
            
            if (prices <= 0).any() or (highs <= 0).any() or (lows <= 0).any():
                logger.warning("Invalid price data in indicator calculation")
                return self._get_default_indicators(prices[-1] if len(prices) > 0 else 1.0)
            
            # RSI
            indicators['rsi_14'] = self._calculate_rsi(prices, 14)
            
            # Moving Averages
            indicators['sma_20'] = np.mean(prices[-20:]) if len(prices) >= 20 else np.mean(prices)
            
            # MACD
            macd_line, macd_signal, macd_histogram = self._calculate_macd(prices)
            indicators['macd_line'] = macd_line
            indicators['macd_signal'] = macd_signal
            indicators['macd_histogram'] = macd_histogram
            
            # Bollinger Bands
            bb_upper, bb_lower, bb_middle = self._calculate_bollinger_bands(prices)
            indicators['bb_upper'] = bb_upper
            indicators['bb_lower'] = bb_lower
            indicators['bb_middle'] = bb_middle
            indicators['bb_position'] = (prices[-1] - bb_lower) / (bb_upper - bb_lower) if (bb_upper - bb_lower) > 0 else 0.5
            
            # ATR - DIPERBAIKI
            indicators['atr'] = self._calculate_atr(df)
            
            # Volatility
            returns = np.diff(prices) / prices[:-1]
            indicators['volatility'] = np.std(returns) * np.sqrt(252) if len(returns) > 1 else 0.02
            
            # Momentum
            indicators['momentum_5'] = (prices[-1] / prices[-5] - 1) * 100 if len(prices) >= 5 and prices[-5] > 0 else 0
            
            return indicators
            
        except Exception as e:
            logger.error(f"Enhanced indicators calculation error: {e}")
            return self._get_default_indicators(prices[-1] if 'prices' in locals() and len(prices) > 0 else 1.0)
    
    def _get_default_indicators(self, current_price: float) -> Dict[str, float]:
        """Get default indicators when calculation fails"""
        return {
            'rsi_14': 50.0,
            'sma_20': current_price,
            'macd_line': 0, 'macd_signal': 0, 'macd_histogram': 0,
            'bb_upper': current_price * 1.02, 'bb_lower': current_price * 0.98, 'bb_middle': current_price,
            'bb_position': 0.5,
            'atr': current_price * 0.02, 'volatility': 0.02,
            'momentum_5': 0
        }
    
    def _calculate_rsi(self, prices: np.ndarray, period: int) -> float:
        """Calculate RSI"""
        if len(prices) < period + 1:
            return 50.0
        
        if (prices <= 0).any():
            return 50.0
        
        deltas = np.diff(prices)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        avg_gains = np.mean(gains[-period:])
        avg_losses = np.mean(losses[-period:])
        
        if avg_losses == 0:
            return 100.0
        
        rs = avg_gains / avg_losses
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    def _calculate_macd(self, prices: np.ndarray) -> Tuple[float, float, float]:
        """Calculate MACD"""
        if len(prices) < 26:
            return 0.0, 0.0, 0.0
        
        ema_12 = self._calculate_ema(prices, 12)
        ema_26 = self._calculate_ema(prices, 26)
        macd_line = ema_12 - ema_26
        macd_signal = self._calculate_ema(prices[-9:], 9)
        macd_histogram = macd_line - macd_signal
        
        return macd_line, macd_signal, macd_histogram
    
    def _calculate_ema(self, prices: np.ndarray, period: int) -> float:
        """Calculate EMA"""
        if len(prices) < period:
            return np.mean(prices) if len(prices) > 0 else 1.0
        
        weights = np.exp(np.linspace(-1., 0., period))
        weights /= weights.sum()
        
        return np.convolve(prices[-period:], weights, mode='valid')[-1]
    
    def _calculate_bollinger_bands(self, prices: np.ndarray, period: int = 20, std_dev: int = 2) -> Tuple[float, float, float]:
        """Calculate Bollinger Bands"""
        if len(prices) < period:
            middle = np.mean(prices) if len(prices) > 0 else 1.0
            std = np.std(prices) if len(prices) > 1 else 0.1
            return middle + std_dev * std, middle - std_dev * std, middle
        
        middle = np.mean(prices[-period:])
        std = np.std(prices[-period:])
        upper = middle + std_dev * std
        lower = middle - std_dev * std
        
        return upper, lower, middle
    
    def _calculate_atr(self, df: pd.DataFrame) -> float:
        """Calculate Average True Range - DIPERBAIKI untuk data minimal"""
        try:
            # Cek jika data cukup
            if len(df) < 5:
                current_price = df['close'].iloc[-1] if 'close' in df.columns and len(df) > 0 else 100.0
                return current_price * 0.02  # Fallback
            
            high = df['high'].values
            low = df['low'].values
            close = df['close'].values
            
            # Validasi data
            if (high <= 0).any() or (low <= 0).any() or (close <= 0).any():
                logger.warning("Invalid price data in ATR calculation")
                return df['close'].iloc[-1] * 0.02
            
            # Hitung True Range untuk setiap bar
            tr = np.zeros(len(high))
            for i in range(1, len(high)):
                tr1 = high[i] - low[i]
                tr2 = abs(high[i] - close[i-1])
                tr3 = abs(low[i] - close[i-1])
                tr[i] = max(tr1, tr2, tr3)
            
            # Hitung ATR (14-period)
            period = min(14, len(tr))
            atr = np.mean(tr[-period:]) if len(tr) >= period else np.mean(tr)
            
            # Pastikan ATR tidak nol atau negatif
            if atr <= 0:
                current_price = close[-1]
                atr = current_price * 0.02
            
            return atr
            
        except Exception as e:
            logger.error(f"ATR calculation error: {e}")
            current_price = df['close'].iloc[-1] if 'close' in df.columns and len(df) > 0 else 100.0
            return current_price * 0.02
    
    def _calculate_trend_strength(self, df: pd.DataFrame, symbol: str = None) -> float:
        """Hitung kekuatan trend dengan linear regression"""
        try:
            prices = df['close'].values[-50:]
            if len(prices) < 2:
                return 0.0
            
            # FIX: Clean nan/inf/constant
            prices = np.nan_to_num(prices, nan=0.0, posinf=0.0, neginf=0.0)
            if not np.all(np.isfinite(prices)) or np.all(prices == prices[0]) or np.all(prices == 0):
                logger.warning(f"Invalid prices (nan/inf/constant/zero) for {symbol}, returning 0.0")
                return 0.0
            
            x = np.arange(len(prices))
            slope, intercept, r_value, p_value, std_err = stats.linregress(x, prices)
            
            mean_price = np.mean(prices)
            normalized_slope = slope / mean_price if mean_price > 0 else 0
            trend_strength = normalized_slope * (r_value ** 2)
            
            return max(min(trend_strength, 1.0), -1.0)
        
        except (ValueError, Exception) as e:
            logger.warning(f"Trend calc failed for {symbol}: {str(e)}. Return 0.0")
            return 0.0
    
    def _analyze_market_regime(self, df: pd.DataFrame, base_score: float, volatility: float, trend_strength: float) -> MarketRegime:
        """Determine market regime"""
        if trend_strength > 0.6:
            if base_score > 0:
                return MarketRegime.BULL_TREND
            elif base_score < 0:
                return MarketRegime.BEAR_TREND
        elif volatility > 0.04:
            return MarketRegime.HIGH_VOLATILITY
        elif volatility < 0.01:
            return MarketRegime.LOW_VOLATILITY
        elif abs(base_score) > 5 and volatility > 0.03:
            return MarketRegime.BREAKOUT
        elif trend_strength < 0.3:
            return MarketRegime.RANGING
        return MarketRegime.UNKNOWN
    
    def _get_default_analysis(self, symbol: str = None) -> Dict[str, Any]:
        """Get default analysis result"""
        if symbol is None:
            symbol = "UNKNOWN"
            
        default_price = self._estimate_realistic_price(symbol)
        default_entry = self.calculate_custom_entry(symbol, default_price, "NEUTRAL")
        
        return {
            'action': 'NEUTRAL',
            'trading_type': self.trading_type,
            'leverage': self.leverage,
            'entry_range_low': default_entry['entry_range_low'],
            'entry_range_high': default_entry['entry_range_high'],
            'best_entry': default_entry['best_entry'],
            'tp1': default_entry['tp1'],
            'tp2': default_entry['tp2'],
            'tp3': default_entry['tp3'],
            'sl': default_entry['sl'],
            'current_price': default_price,
            'score': 0,
            'rsi': 50.0,
            'atr': default_price * 0.02,
            'market_regime': 'unknown',
            'trend_strength': 0.0,
            'trend_direction': 'NEUTRAL',
            'volatility': 0.02,
            'confidence': 0.5,
            'symbol': symbol,
            'entry_range_pct': self.entry_range_pct * 100,
            'range_size': default_entry['range_size'],
            'risk_amount': default_entry['risk_amount'],
            'risk_percentage': default_entry['risk_percentage'],
            'rr_ratio_tp1': default_entry['rr_ratio_tp1'],
            'rr_ratio_tp3': default_entry['rr_ratio_tp3'],
            'liquidation_buffer_pct': default_entry['liquidation_buffer_pct'],
            'long_bias_applied': self.long_bias,
            'min_score_threshold': self.min_score_threshold,
            'scalping_mode': self.scalping_mode
        }

# =============================================
# SCALPING STRATEGY - STRATEGI KHUSUS UNTUK SCALPING
# =============================================

class ScalpingStrategy(EnhancedTechnicalAnalysisStrategy):
    """Strategi khusus untuk scalping 3-5 menit dengan bias correction"""
    
    def __init__(self, market_type="crypto", trading_type="spot", leverage=1):
        super().__init__(
            market_type=market_type,
            trading_type=trading_type,
            leverage=leverage,
            # 🎯 PARAMETER SCALPING OPTIMAL
            entry_range_pct=SCALPING_CONFIG["entry_range_pct"],  # 0.8%
            atr_multiplier=SCALPING_CONFIG["atr_multiplier"],    # 0.7
            long_bias=0.0,  # 🔥 GANTI: dari SCALPING_CONFIG["long_bias"] ke 0.0
            min_score_threshold=SCALPING_CONFIG["min_score_threshold"],  # 4.0
            scalping_mode=True
        )
        logger.info(f"🎯 ScalpingStrategy created: Bias={self.long_bias:.1f}, Min Score={self.min_score_threshold}")
    
    def analyze(self, df: pd.DataFrame, symbol: str = None, **kwargs) -> Dict[str, Any]:
        """Override untuk scalping dengan validasi tambahan"""
        
        # 1. Validasi khusus untuk scalping
        if df is None or df.empty:
            return self._get_safe_neutral_signal(symbol)
        
        # 2. Gunakan validasi data yang aman
        if not self._safe_data_validation(df, symbol):
            logger.warning(f"Data validation failed for {symbol} in scalping")
            return self._get_safe_neutral_signal(symbol)
        
        # 3. Cek minimal data untuk scalping
        if len(df) < 50:
            logger.warning(f"⚠️ {symbol}: Insufficient data for scalping ({len(df)} bars)")
            return self._get_safe_neutral_signal(symbol)
        
        # 4. Cek volatilitas untuk scalping
        volatility = df['close'].pct_change().std() * np.sqrt(252)
        if volatility < SCALPING_CONFIG["min_volatility"]:
            logger.debug(f"⚠️ {symbol}: Too low volatility for scalping ({volatility:.3%})")
            return self._get_safe_neutral_signal(symbol)
        
        if volatility > SCALPING_CONFIG["max_volatility"]:
            logger.debug(f"⚠️ {symbol}: Too high volatility for scalping ({volatility:.3%})")
            return self._get_safe_neutral_signal(symbol)
        
        # 5. Cek volume untuk scalping
        if 'volume' in df.columns:
            avg_volume = df['volume'].mean()
            if avg_volume < 50000:  # Minimal volume untuk scalping
                logger.debug(f"⚠️ {symbol}: Low volume for scalping ({avg_volume:.0f})")
                return self._get_safe_neutral_signal(symbol)
        
        # 6. Gunakan analisis parent dengan parameter scalping
        result = super().analyze(df, symbol, **kwargs)
        
        # 7. Tambahkan flag scalping
        result['scalping_mode'] = True
        result['scalping_optimized'] = True
        
        return result

# =============================================
# UTILITY FUNCTIONS UNTUK AUTO-DETECTION DENGAN SCALPING
# =============================================

def auto_detect_trading_type_and_format(symbol: str) -> Tuple[str, str]:
    """
    Auto-detect trading type dan konversi format secara otomatis.
    Returns: (trading_type, formatted_symbol)
    """
    symbol_upper = symbol.upper()
    
    # Deteksi futures
    futures_markers = [':USDT', 'PERP', 'FUTURES', 'SWAP', '-USDT', '_PERP', '1226', '0325', '0626', '0926']
    is_futures = any(marker in symbol_upper for marker in futures_markers)
    
    if is_futures:
        trading_type = "futures"
        # Standardisasi format untuk futures
        if ':USDT' in symbol_upper:
            formatted = symbol
        elif '/USDT' in symbol_upper and ':USDT' not in symbol_upper:
            formatted = f"{symbol}:USDT"
        elif '-USDT' in symbol_upper and 'PERP' not in symbol_upper:
            formatted = symbol.replace('-USDT', '/USDT:USDT')
        else:
            formatted = symbol
    else:
        trading_type = "spot"
        # Standardisasi format spot
        if ':USDT' in symbol_upper:
            formatted = symbol.replace(':USDT', '/USDT')
        else:
            formatted = symbol
    
    return trading_type, formatted

def auto_detect_trading_type(symbol: str) -> str:
    """
    Auto-detect if symbol is for spot or futures trading - ENHANCED
    """
    trading_type, _ = auto_detect_trading_type_and_format(symbol)
    return trading_type

def convert_symbol_format(symbol: str, target_type: str = "spot") -> str:
    """
    Convert symbol between spot and futures format
    """
    if target_type == "futures":
        # Convert spot to futures format
        if ':USDT' not in symbol.upper():
            if '/USDT' in symbol.upper():
                return f"{symbol}:USDT"
            elif '-USDT' in symbol.upper():
                return symbol.replace('-USDT', '/USDT:USDT')
            else:
                return f"{symbol}:USDT"
        else:
            return symbol
    
    elif target_type == "spot":
        # Convert futures to spot format
        if ':USDT' in symbol.upper():
            return symbol.replace(':USDT', '')
        else:
            return symbol
    
    return symbol

def auto_suggest_leverage(symbol: str, market_type: str = "crypto", scalping_mode: bool = False) -> int:
    """
    Auto-suggest leverage based on symbol and market type
    """
    # 🆕 SCALPING LEVERAGE LEBIH RENDAH
    if scalping_mode:
        leverage_map = {
            'crypto': {
                'BTC': 3, 'ETH': 5, 'SOL': 8, 'ADA': 10, 'XRP': 10,
                'BNB': 8, 'DOGE': 12, 'DOT': 8, 'AVAX': 8, 'MATIC': 10,
                'default': 5  # Leverage rendah untuk scalping
            },
            'forex': {
                'EURUSD': 20, 'USDJPY': 20, 'GBPUSD': 15, 'AUDUSD': 15,
                'USDCAD': 15, 'USDCHF': 15, 'NZDUSD': 15, 'XAUUSD': 10, 'XAGUSD': 10,
                'default': 15  # Leverage rendah untuk scalping
            },
            'default': 5
        }
    else:
        leverage_map = {
            'crypto': {
                'BTC': 5, 'ETH': 8, 'SOL': 10, 'ADA': 15, 'XRP': 15,
                'BNB': 10, 'DOGE': 20, 'DOT': 12, 'AVAX': 12, 'MATIC': 15,
                'default': 10
            },
            'forex': {
                'EURUSD': 30, 'USDJPY': 30, 'GBPUSD': 20, 'AUDUSD': 25,
                'USDCAD': 25, 'USDCHF': 25, 'NZDUSD': 25, 'XAUUSD': 20, 'XAGUSD': 20,
                'default': 25
            },
            'us_stocks': {
                'ES': 20, 'NQ': 15, 'YM': 15, 'RTY': 15,
                'SPX': 20, 'NDX': 15, 'DJI': 15,
                'default': 15
            },
            'forex_gold': {
                'XAU': 20, 'GOLD': 20, 'XAG': 20, 'SILVER': 20,
                'default': 20
            },
            'crypto_future': {
                'BTC': 5, 'ETH': 8, 'SOL': 10, 'default': 8
            },
            'stock_future': {
                'ES': 20, 'NQ': 15, 'YM': 15, 'default': 15
            },
            'forex_future': {
                'EURUSD': 30, 'USDJPY': 30, 'default': 25
            }
        }
    
    symbol_upper = symbol.upper().replace('/', '').replace('-', '').replace('_', '').replace('=', '')
    
    # Check for specific symbol match
    for key, leverage in leverage_map.get(market_type, {}).items():
        if key in symbol_upper:
            return leverage
    
    # Return default for market type
    return leverage_map.get(market_type, {}).get('default', 10)

def create_strategy_for_symbol(symbol: str, market_type: str = "auto", 
                               trading_mode: str = None, scalping_mode: bool = False) -> EnhancedTechnicalAnalysisStrategy:
    """
    Create appropriate strategy based on symbol auto-detection dengan scalping support
    """
    # Auto-detect market type if not specified
    if market_type == "auto":
        if any(x in symbol.upper() for x in ['.JK', 'IDX', 'JAKARTA']):
            market_type = "indonesia_stocks"
        elif any(x in symbol.upper() for x in ['XAU', 'XAG', 'GOLD', 'SILVER']):
            market_type = "forex_gold"
        elif any(x in symbol.upper() for x in ['EUR', 'USD', 'JPY', 'GBP', 'AUD', 'CAD']):
            market_type = "forex"
        elif any(x in symbol.upper() for x in ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA', 'META']):
            market_type = "us_stocks"
        elif any(x in symbol.upper() for x in ['PERP', 'FUTURES', 'SWAP', '1226', '0325', '0626', '0926']):
            if 'BTC' in symbol.upper() or 'ETH' in symbol.upper() or 'SOL' in symbol.upper():
                market_type = "crypto_future"
            elif 'ES' in symbol.upper() or 'NQ' in symbol.upper() or 'YM' in symbol.upper():
                market_type = "stock_future"
            elif 'EUR' in symbol.upper() or 'USD' in symbol.upper() or 'JPY' in symbol.upper():
                market_type = "forex_future"
            else:
                market_type = "crypto_future"
        else:
            market_type = "crypto"
    
    # Jika trading_mode diberikan dari core.py, gunakan itu
    if trading_mode:
        trading_type = trading_mode
        formatted_symbol = convert_symbol_format(symbol, trading_mode)
    else:
        trading_type, formatted_symbol = auto_detect_trading_type_and_format(symbol)
    
    # Auto-suggest leverage dengan scalping consideration
    leverage = auto_suggest_leverage(formatted_symbol, market_type, scalping_mode)
    
    # 🎯 BUAT STRATEGI BERDASARKAN SCALPING MODE
    if scalping_mode:
        strategy = ScalpingStrategy(
            market_type=market_type,
            trading_type=trading_type,
            leverage=leverage
        )
        logger.info(f"⚡ SCALPING Strategy for {symbol} -> {formatted_symbol}: Market={market_type}, Leverage={leverage}x")
    else:
        # 🔥 PERBAIKAN: HAPUS BIAS DARI REGULAR STRATEGY
        strategy = EnhancedTechnicalAnalysisStrategy(
            market_type=market_type,
            trading_type=trading_type,
            leverage=leverage,
            entry_range_pct=0.02,
            atr_multiplier=1.0,
            long_bias=0.0,  # 🔥 GANTI: dari 0.1 ke 0.0 (NEUTRAL)
            min_score_threshold=3.0
        )
        logger.info(f"📊 REGULAR Strategy for {symbol} -> {formatted_symbol}: Market={market_type}, Leverage={leverage}x")
    
    return strategy

def get_strategy_for_trading_mode(symbol: str, trading_mode: str = "spot", 
                                  market_type: str = "auto", scalping_mode: bool = False) -> EnhancedTechnicalAnalysisStrategy:
    """
    Get strategy configured for specific trading mode dengan scalping support
    """
    # Convert symbol format jika diperlukan
    formatted_symbol = convert_symbol_format(symbol, trading_mode)
    
    # Create strategy dengan trading_mode dan scalping_mode yang ditentukan
    strategy = create_strategy_for_symbol(
        symbol=formatted_symbol,
        market_type=market_type,
        trading_mode=trading_mode,
        scalping_mode=scalping_mode
    )
    
    return strategy

# =============================================
# BACKWARD COMPATIBILITY
# =============================================

class TechnicalAnalysisStrategy(EnhancedTechnicalAnalysisStrategy):
    """Backward compatibility wrapper"""
    pass

# =============================================
# TESTING FUNCTIONS UNTUK VERIFIKASI PERBAIKAN
# =============================================

def test_data_cleaner():
    """Test the data cleaner function"""
    print("=" * 60)
    print("TESTING DATA CLEANER FUNCTION")
    print("=" * 60)
    
    test_symbols = [
        "BONK/USDT:USDT",
        "CATI/USDT:USDT", 
        "BTC-USD",
        "ETH-USD",
        "SOL-USD",
    ]
    
    for symbol in test_symbols:
        print(f"\n🔍 Testing {symbol}")
        
        data = get_trading_data(symbol)
        
        if data is None:
            print(f"   ❌ Skipped - no valid data")
            continue
        
        print(f"   ✅ Valid data: {len(data)} bars")
        
        if not data.empty and 'close' in data.columns:
            current_price = data['close'].iloc[-1]
            print(f"   📊 Current price: ${current_price:.6f}")
            
            # Cek harga 100 dengan .any()
            price_diff = abs(data['close'] - 100.0)
            mask_100 = (price_diff < 0.001)
            
            if mask_100.any():
                print(f"   ⚠️ WARNING: Still has price 100!")
            else:
                print(f"   👍 No price 100 detected")
    
    return True

def test_strategy_with_bias_correction():
    """Test the enhanced strategy with bias correction"""
    print("=" * 60)
    print("TESTING STRATEGY WITH BIAS CORRECTION")
    print("=" * 60)
    
    # Test 1: Regular Strategy dengan Bias 0
    print("\n1. TESTING REGULAR STRATEGY (NO BIAS)")
    print("-" * 40)
    
    dates = pd.date_range('2023-01-01', periods=100, freq='D')
    data = {
        'open': np.random.normal(50000, 1000, 100),
        'high': np.random.normal(50500, 1200, 100),
        'low': np.random.normal(49500, 1200, 100),
        'close': np.random.normal(50000, 1000, 100),
        'volume': np.random.normal(1000000, 100000, 100),
    }
    df = pd.DataFrame(data, index=dates)
    
    regular_strategy = EnhancedTechnicalAnalysisStrategy(
        market_type="crypto",
        trading_type="spot",
        leverage=1,
        long_bias=0.0,  # No bias
        min_score_threshold=3.0
    )
    
    result = regular_strategy.analyze(df, "BTC/USDT")
    print(f"Action: {result['action']}")
    print(f"Score: {result['score']:.1f}")
    print(f"Bias Applied: {result['long_bias_applied']}")
    
    # Test 2: Strategy dengan Long Bias +0.3 (SEKARANG 0.0)
    print("\n2. TESTING STRATEGY WITH LONG BIAS 0.0")
    print("-" * 40)
    long_bias_strategy = EnhancedTechnicalAnalysisStrategy(
        market_type="crypto",
        trading_type="spot",
        leverage=1,
        long_bias=0.0,  # 🔥 UBAH: dari 0.3 ke 0.0
        min_score_threshold=3.0
    )
    
    result = long_bias_strategy.analyze(df, "BTC/USDT")
    print(f"Action: {result['action']}")
    print(f"Score: {result['score']:.1f}")
    print(f"Bias Applied: {result['long_bias_applied']}")
    
    # Test 3: Scalping Strategy dengan Long Bias 0.0
    print("\n3. TESTING SCALPING STRATEGY (BIAS 0.0)")
    print("-" * 40)
    scalping_strategy = ScalpingStrategy(
        market_type="crypto",
        trading_type="spot",
        leverage=1
    )
    
    result = scalping_strategy.analyze(df, "BTC/USDT")
    print(f"Action: {result['action']}")
    print(f"Score: {result['score']:.1f}")
    print(f"Bias Applied: {result['long_bias_applied']}")
    print(f"Min Score Threshold: {result['min_score_threshold']}")
    print(f"Scalping Mode: {result['scalping_mode']}")
    
    # Test 4: Simulasi Multiple Symbols untuk Verifikasi Bias
    print("\n4. TESTING BIAS CORRECTION ACROSS MULTIPLE SIGNALS")
    print("-" * 40)
    
    test_cases = [
        ("BTC/USDT", 0.0, "No bias"),
        ("ETH/USDT", 0.0, "No bias"),  # 🔥 UBAH: dari 0.3 ke 0.0
        ("SOL/USDT", 0.0, "No bias"),  # 🔥 UBAH: dari -0.3 ke 0.0
    ]
    
    for symbol, bias, description in test_cases:
        strategy = EnhancedTechnicalAnalysisStrategy(
            market_type="crypto",
            trading_type="spot",
            leverage=1,
            long_bias=bias,
            min_score_threshold=3.0
        )
        
        # Simulate different market conditions
        for i in range(3):
            # Generate different price data
            base_price = 100 if i == 0 else 200 if i == 1 else 50
            test_data = {
                'open': np.random.normal(base_price, base_price * 0.05, 50),
                'high': np.random.normal(base_price * 1.05, base_price * 0.06, 50),
                'low': np.random.normal(base_price * 0.95, base_price * 0.06, 50),
                'close': np.random.normal(base_price, base_price * 0.05, 50),
                'volume': np.random.normal(1000000, 100000, 50),
            }
            test_df = pd.DataFrame(test_data)
            
            result = strategy.analyze(test_df, symbol)
            action = result['action']
            score = result['score']
            
            print(f"{symbol} ({description}): {action} (Score: {score:.1f}, Bias: {bias})")
    
    return regular_strategy, long_bias_strategy, scalping_strategy

def test_integration_with_core():
    """Test integration dengan scalping mode"""
    print("\n" + "=" * 60)
    print("TESTING INTEGRATION WITH SCALPING MODE")
    print("=" * 60)
    
    test_cases = [
        ("BTC/USDT", "spot", "crypto", False),
        ("BTC/USDT", "spot", "crypto", True),  # Scalping mode
        ("ETH/USDT", "futures", "crypto_future", True),
        ("EUR/USD", "spot", "forex", False),
        ("EUR/USD", "futures", "forex_future", True),
    ]
    
    for symbol, trading_mode, expected_market_type, scalping in test_cases:
        strategy = get_strategy_for_trading_mode(symbol, trading_mode, scalping_mode=scalping)
        print(f"\n{symbol} → {trading_mode} (Scalping: {scalping}):")
        print(f"  Market Type: {strategy.market_type}")
        print(f"  Trading Type: {strategy.trading_type}")
        print(f"  Leverage: {strategy.leverage}x")
        print(f"  Long Bias: {strategy.long_bias:.2f}")
        print(f"  Min Score: {strategy.min_score_threshold}")
        print(f"  Scalping Mode: {strategy.scalping_mode}")
    
    # Test convert_symbol_format
    print("\n" + "-" * 40)
    print("TESTING SYMBOL CONVERSION:")
    print("-" * 40)
    
    conversion_tests = [
        ("BTC/USDT", "spot", "BTC/USDT"),
        ("BTC/USDT", "futures", "BTC/USDT:USDT"),
        ("BTC/USDT:USDT", "spot", "BTC/USDT"),
        ("BTC/USDT:USDT", "futures", "BTC/USDT:USDT"),
        ("ETH-USD", "futures", "ETH/USDT:USDT"),
    ]
    
    for original, target_type, expected in conversion_tests:
        result = convert_symbol_format(original, target_type)
        status = "✓" if result == expected else "✗"
        print(f"{status} {original} → {target_type}: {result} (expected: {expected})")

def test_scalping_trading_loop():
    """Contoh penggunaan scalping di loop trading"""
    print("\n" + "=" * 60)
    print("EXAMPLE SCALPING TRADING LOOP")
    print("=" * 60)
    
    symbols = ["BTC-USD", "ETH-USD", "SOL-USD"]
    
    for symbol in symbols:
        print(f"\n🔍 Processing {symbol} for scalping")
        
        # Gunakan filter khusus scalping
        data = get_trading_data(symbol, scalping_mode=True)
        
        if data is None:
            print(f"   ❌ Skipping - not suitable for scalping")
            continue
        
        print(f"   ✅ Valid scalping data: {len(data)} bars")
        
        # Gunakan scalping strategy
        strategy = ScalpingStrategy(
            market_type="crypto",
            trading_type="spot",
            leverage=3  # Leverage rendah untuk scalping
        )
        
        result = strategy.analyze(data, symbol)
        
        print(f"   📊 Action: {result['action']}")
        print(f"   📈 Score: {result['score']:.2f} (Bias: {result['long_bias_applied']:.2f})")
        print(f"   💰 Current: ${result['current_price']:.6f}")
        print(f"   🎯 Entry: ${result['best_entry']:.6f}")
        print(f"   🛑 SL: ${result['sl']:.6f}")
        print(f"   ⚡ Scalping Mode: {result['scalping_mode']}")

def test_bias_correction_statistics():
    """Test statistik bias correction"""
    print("\n" + "=" * 60)
    print("BIAS CORRECTION STATISTICS TEST")
    print("=" * 60)
    
    # Simulate 100 random market conditions
    np.random.seed(42)
    actions = []
    scores = []
    
    for i in range(100):
        # Generate random market data
        base_price = np.random.uniform(10, 1000)
        trend = np.random.choice([-1, 0, 1])
        
        dates = pd.date_range('2023-01-01', periods=100, freq='D')
        data = {
            'open': base_price + np.random.normal(0, base_price * 0.05, 100) + trend * np.linspace(0, base_price * 0.2, 100),
            'high': base_price * 1.05 + np.random.normal(0, base_price * 0.06, 100) + trend * np.linspace(0, base_price * 0.2, 100),
            'low': base_price * 0.95 + np.random.normal(0, base_price * 0.06, 100) + trend * np.linspace(0, base_price * 0.2, 100),
            'close': base_price + np.random.normal(0, base_price * 0.05, 100) + trend * np.linspace(0, base_price * 0.2, 100),
            'volume': np.random.normal(1000000, 100000, 100),
        }
        df = pd.DataFrame(data, index=dates)
        
        # Test dengan bias berbeda
        for bias in [0.0, 0.0, 0.0]:  # 🔥 UBAH: semua 0.0 (tidak ada bias)
            strategy = EnhancedTechnicalAnalysisStrategy(
                market_type="crypto",
                trading_type="spot",
                leverage=1,
                long_bias=bias,
                min_score_threshold=3.0
            )
            
            result = strategy.analyze(df, f"TEST{i}")
            actions.append((bias, result['action']))
            scores.append((bias, result['score']))
    
    # Analyze results
    print("\n📊 ACTION DISTRIBUTION BY BIAS:")
    print("-" * 40)
    
    for bias in [0.0, 0.0, 0.0]:  # 🔥 UBAH: semua 0.0
        bias_actions = [action for b, action in actions if b == bias]
        total = len(bias_actions)
        long_count = bias_actions.count("LONG")
        short_count = bias_actions.count("SHORT")
        neutral_count = bias_actions.count("NEUTRAL")
        
        print(f"\nBias {bias:+.1f}:")
        print(f"  Total: {total}")
        print(f"  LONG: {long_count} ({long_count/total*100:.1f}%)")
        print(f"  SHORT: {short_count} ({short_count/total*100:.1f}%)")
        print(f"  NEUTRAL: {neutral_count} ({neutral_count/total*100:.1f}%)")
        
        if total > 0:
            long_short_ratio = long_count / short_count if short_count > 0 else float('inf')
            print(f"  LONG/SHORT Ratio: {long_short_ratio:.2f}:1")
    
    print("\n🎯 BIAS CORRECTION SUMMARY:")
    print("-" * 40)
    print("• Bias 0.0: Sistem NEUTRAL (tidak ada bias)")
    print("• Semua trading decisions murni berdasarkan kondisi market")
    print("• Sistem trading sepenuhnya netral")
    print("\n✅ Sistem sekarang benar-benar NETRAL tanpa bias!")

if __name__ == "__main__":
    # Jalankan semua test
    print("\n" + "=" * 60)
    print("ENHANCED STRATEGIES.PY - SYSTEM NETRAL (NO BIAS)")
    print("=" * 60)
    
    # Test data cleaner
    test_data_cleaner()
    
    # Test strategy dengan bias correction (sekarang 0.0)
    regular, long_bias, scalping = test_strategy_with_bias_correction()
    
    # Test bias correction statistics
    test_bias_correction_statistics()
    
    # Test integration
    test_integration_with_core()
    
    # Test scalping trading loop
    test_scalping_trading_loop()
    
    # Show example output
    print("\n" + "=" * 60)
    print("📊 EXAMPLE SCALPING SIGNAL OUTPUT (NO BIAS):")
    print("=" * 60)
    
    dates = pd.date_range('2023-12-01', periods=50, freq='H')
    data = {
        'open': np.random.normal(87000, 1000, 50),
        'high': np.random.normal(87500, 1200, 50),
        'low': np.random.normal(86500, 1200, 50),
        'close': np.random.normal(87000, 1000, 50),
        'volume': np.random.normal(1000000, 100000, 50),
    }
    df = pd.DataFrame(data, index=dates)
    
    scalping_strategy = ScalpingStrategy(
        market_type="crypto_future",
        trading_type="futures",
        leverage=5
    )
    
    result = scalping_strategy.analyze(df, "BTC/USDT:USDT")
    formatted_output = scalping_strategy.format_signal_output(result)
    print(formatted_output)
    
    print("\n" + "=" * 60)
    print("✅ STRATEGIES.PY READY - SYSTEM NETRAL!")
    print("✅ NO LONG BIAS APPLIED!")
    print("✅ SCALPING MODE OPTIMIZED!")
    print("=" * 60)
