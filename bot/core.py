# core.py - PERBAIKAN UNTUK ANALISIS ENHANCED DAN FILTER SINYAL

import os
import sys
import time
import json
import warnings
import joblib
import random
from datetime import datetime, timedelta
import threading
import schedule
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler, RobustScaler
from sklearn.model_selection import train_test_split, TimeSeriesSplit
from sklearn.metrics import accuracy_score, precision_recall_fscore_support, classification_report
from sklearn.linear_model import LogisticRegression
from xgboost import XGBClassifier
import lightgbm as lgb
from dotenv import load_dotenv
import logging
from typing import Dict, List, Optional, Tuple, Any
import traceback
from dataclasses import dataclass
from enum import Enum
import concurrent.futures
from scipy import stats

# =============================================
# SCALPING CONFIGURATION - DITINGKATKAN
# =============================================
SCALPING_CONFIG = {
    "timeframe": "5m",           # 5 menit untuk scalping
    "lookback": 150,             # ~12.5 jam data
    "min_score": 4.0,            # Minimal score untuk eksekusi
    "max_signals": 10,           # Maksimal sinyal per scan
    "min_volume_usd": 500000,    # Minimal volume $500k
    "min_bars": 50,              # Minimal data bars untuk scalping (PERBAIKAN NON-CRYPTO)
    "yfinance_timeout": 30,      # Timeout khusus untuk YFinance
    "skip_weekends": True,       # Skip weekend data untuk stocks
    "price_filter": {
        "min": 0.01,             # Harga minimal $0.01
        "max": 1000              # Harga maksimal $1000
    },
    "provider_priority": ["binance", "kucoin", "yfinance"],  # Prioritize real data
    "skip_dummy_data": True,     # Skip aset dengan dummy data
    "analysis_coins_limit": 500  # PERBAIKAN: Naikkan limit analisis aset menjadi 500
}

# =============================================
# SCALPING STRATEGY
# =============================================
class ScalpingStrategy:
    """Scalping strategy untuk trading cepat dengan timeframe kecil"""
    
    def __init__(self, market_type='crypto', trading_type='spot', leverage=1):
        self.market_type = market_type
        self.trading_type = trading_type
        self.leverage = leverage
        self.timeframe = "5m"
        self.lookback = 150
        
    def analyze(self, df, symbol=None):
        """Analisis untuk scalping dengan timeframe 5m"""
        if df is None or df.empty or len(df) < 50:
            return None
            
        try:
            # Indicators khusus scalping
            close = df['close'].values
            high = df['high'].values
            low = df['low'].values
            
            # RSI cepat (7 period)
            rsi = self._calculate_rsi(close, 7)
            
            # EMA cepat (5, 10)
            ema_5 = self._calculate_ema(close, 5)
            ema_10 = self._calculate_ema(close, 10)
            
            # Volume spike detection
            volume_ratio = self._calculate_volume_ratio(df)
            
            # Price momentum (5 bar)
            momentum_5 = (close[-1] / close[-5] - 1) * 100 if len(close) >= 5 else 0
            
            # Volatilitas intraday
            volatility = self._calculate_volatility(df)
            
            # Support/Resistance detection
            support, resistance = self._find_support_resistance(df)
            
            # Score calculation - TANPA BIAS
            score = 0
            
            # Trend alignment (EMA 5 > EMA 10 = bullish)
            if ema_5 > ema_10:
                score += 1.5
            else:
                score -= 1.5
            
            # RSI conditions
            if rsi < 30:
                score += 1.0  # Oversold
            elif rsi > 70:
                score -= 1.0  # Overbought
            
            # Volume confirmation
            if volume_ratio > 1.5:
                score += 0.5
            
            # Momentum positive
            if momentum_5 > 0.5:
                score += 0.5
            elif momentum_5 < -0.5:
                score -= 0.5
            
            # Current price near support
            current_price = close[-1]
            if current_price <= support * 1.02:
                score += 1.0  # Near support, good for LONG
            
            # Current price near resistance
            if current_price >= resistance * 0.98:
                score -= 1.0  # Near resistance, good for SHORT
            
            # Volatility filter (skip too volatile)
            if volatility > 0.05:  # 5% volatility in 5m
                score *= 0.8  # Reduce score but don't eliminate
            
            # Determine action
            if score >= 2:
                action = "LONG"
            elif score <= -2:
                action = "SHORT"
            else:
                action = "NEUTRAL"
            
            # Calculate TP/SL levels
            atr = self._calculate_atr(df)
            
            if action == "LONG":
                sl = current_price - (atr * 1.5)
                tp1 = current_price + (atr * 1.0)
                tp2 = current_price + (atr * 2.0)
                tp3 = current_price + (atr * 3.0)
            elif action == "SHORT":
                sl = current_price + (atr * 1.5)
                tp1 = current_price - (atr * 1.0)
                tp2 = current_price - (atr * 2.0)
                tp3 = current_price - (atr * 3.0)
            else:
                sl = tp1 = tp2 = tp3 = current_price
            
            return {
                'action': action,
                'score': score,
                'entry_price': current_price,
                'sl': sl,
                'tp1': tp1,
                'tp2': tp2,
                'tp3': tp3,
                'rsi': rsi,
                'volume_ratio': volume_ratio,
                'momentum': momentum_5,
                'volatility': volatility,
                'support': support,
                'resistance': resistance,
                'strategy': 'scalping'
            }
            
        except Exception as e:
            logger.error(f"Error in scalping analysis: {e}")
            return None
    
    def _calculate_rsi(self, prices, period=14):
        """Calculate RSI"""
        if len(prices) < period + 1:
            return 50
        delta = np.diff(prices)
        gain = np.where(delta > 0, delta, 0)
        loss = np.where(delta < 0, -delta, 0)
        
        avg_gain = np.mean(gain[-period:])
        avg_loss = np.mean(loss[-period:])
        
        if avg_loss == 0:
            return 100
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))
    
    def _calculate_ema(self, prices, period):
        """Calculate EMA"""
        if len(prices) < period:
            return np.mean(prices)
        return pd.Series(prices).ewm(span=period).mean().iloc[-1]
    
    def _calculate_volume_ratio(self, df, period=20):
        """Calculate volume ratio"""
        if df is None or df.empty or len(df) < period:
            return 1
        current_volume = df['volume'].iloc[-1] if 'volume' in df.columns else 0
        avg_volume = df['volume'].rolling(period).mean().iloc[-1]
        return current_volume / avg_volume if avg_volume > 0 else 1
    
    def _calculate_volatility(self, df, period=20):
        """Calculate volatility"""
        if df is None or df.empty or len(df) < period:
            return 0.02
        returns = df['close'].pct_change().dropna()
        volatility = returns.rolling(period).std().iloc[-1]
        return volatility if not pd.isna(volatility) else 0.02
    
    def _find_support_resistance(self, df, lookback=50):
        """Find support and resistance levels"""
        if df is None or df.empty or len(df) < lookback:
            return df['low'].min(), df['high'].max()
        
        recent_lows = df['low'].iloc[-lookback:].nsmallest(3).values
        recent_highs = df['high'].iloc[-lookback:].nlargest(3).values
        
        support = np.mean(recent_lows) if len(recent_lows) > 0 else df['low'].min()
        resistance = np.mean(recent_highs) if len(recent_highs) > 0 else df['high'].max()
        
        return support, resistance
    
    def _calculate_atr(self, df, period=14):
        """Calculate ATR"""
        try:
            if df is None or df.empty or len(df) < period:
                return df['close'].iloc[-1] * 0.02
            
            high = df['high'].values
            low = df['low'].values
            close = df['close'].values
            
            tr = np.zeros(len(high))
            for i in range(1, len(high)):
                tr1 = high[i] - low[i]
                tr2 = abs(high[i] - close[i-1])
                tr3 = abs(low[i] - close[i-1])
                tr[i] = max(tr1, tr2, tr3)
            
            atr_value = np.mean(tr[-period:]) if len(tr) >= period else np.mean(tr)
            return max(atr_value, df['close'].iloc[-1] * 0.001)
        except:
            return df['close'].iloc[-1] * 0.02

    def analyze_enhanced(self, df, symbol=None):
        """Enhanced analysis untuk scalping dengan filter tambahan"""
        # Panggil analisis standar
        analysis = self.analyze(df, symbol)
        if not analysis:
            return None
        
        # Tambahkan filter tambahan untuk scalping
        current_price = df['close'].iloc[-1] if len(df) > 0 else 0
        
        # Filter volatilitas ekstrem untuk scalping
        if analysis.get('volatility', 0) > 0.1:  # 10% volatilitas dalam 5m terlalu tinggi
            analysis['action'] = 'NEUTRAL'
            analysis['notes'] = 'Volatilitas terlalu tinggi untuk scalping'
            analysis['score'] = 0
        
        # Filter spread (untuk scalping, spread harus kecil)
        if 'spread' in df.columns and len(df) > 0:
            spread = (df['high'].iloc[-1] - df['low'].iloc[-1]) / current_price
            if spread > 0.02:  # Spread 2% terlalu besar untuk scalping
                analysis['action'] = 'NEUTRAL'
                analysis['notes'] = 'Spread terlalu besar untuk scalping'
                analysis['score'] = 0
        
        # Tambahkan probabilitas untuk scalping
        score = analysis.get('score', 0)
        if score >= 4:
            analysis['confidence_level'] = 'HIGH'
            analysis['probabilities'] = {'LONG': 0.7, 'SHORT': 0.1, 'NEUTRAL': 0.2} if analysis['action'] == 'LONG' else {'LONG': 0.1, 'SHORT': 0.7, 'NEUTRAL': 0.2}
        elif score >= 2:
            analysis['confidence_level'] = 'MEDIUM'
            analysis['probabilities'] = {'LONG': 0.6, 'SHORT': 0.2, 'NEUTRAL': 0.2} if analysis['action'] == 'LONG' else {'LONG': 0.2, 'SHORT': 0.6, 'NEUTRAL': 0.2}
        else:
            analysis['confidence_level'] = 'LOW'
            analysis['probabilities'] = {'LONG': 0.4, 'SHORT': 0.4, 'NEUTRAL': 0.2}
        
        return analysis

# =============================================
# EMERGENCY IMPORT FIX - UNTUK STRUKTUR FOLDER BOT
# =============================================

# Tambahkan current directory ke sys.path untuk memastikan import bekerja
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

print(f"📁 Working directory: {current_dir}")
print(f"📦 Python path: {sys.path[:2]}")

# Suppress torch warnings
warnings.filterwarnings("ignore", message=".*torch.classes.*")
warnings.filterwarnings("ignore", category=UserWarning, module="torch")
warnings.filterwarnings("ignore", category=FutureWarning)

load_dotenv()

# Enhanced logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# =============================================
# IMPROVED IMPORT HANDLING - FIXED INDENTATION
# =============================================

# Import modul yang diperlukan dengan error handling yang lebih baik
print("\n" + "="*60)
print("DEBUG IMPORTS - PERBAIKAN INDEKSASI")
print("="*60)

# Initialize all imports to None
TechnicalAnalysisStrategy = None
SignalFilter = None
UnifiedDataProvider = None
EnhancedYFinanceDataProvider = None
DataProviderMonitor = None
DynamicDataProvider = None
EnhancedCCXTDataProvider = None
EnhancedCCXTFuturesProvider = None
AlphaVantageProvider = None
DataProviderFactory = None
SoundNotifier = None
DatabaseHandler = None
SolanaPumpFunProvider = None
EnhancedDexScreenerProvider = None
get_trading_data = None
create_strategy_for_symbol = None
SmartChainDataProvider = None
NonCryptoAssetsProvider = None  # New import

try:
    print("✅ Mencoba import strategies...")
    from strategies import TechnicalAnalysisStrategy, SignalFilter, get_trading_data, create_strategy_for_symbol
    print("  ✅ TechnicalAnalysisStrategy berhasil diimport")
    print("  ✅ SignalFilter berhasil diimport")
    print("  ✅ get_trading_data dan create_strategy_for_symbol berhasil diimport")
except ImportError as e1:
    print(f"  ❌ Gagal import strategies: {e1}")
    # Buat dummy class dan fungsi
    class TechnicalAnalysisStrategy:
        def __init__(self, *args, **kwargs):
            logger.warning("TechnicalAnalysisStrategy dummy digunakan")
        def analyze(self, *args, **kwargs):
            return {'action': 'NEUTRAL', 'score': 0}
        def analyze_enhanced(self, *args, **kwargs):
            return {'action': 'NEUTRAL', 'score': 0}
    
    class SignalFilter:
        @staticmethod
        def should_trade(signal):
            return True, "OK"
    
    def get_trading_data(symbol, provider=None):
        logger.warning("get_trading_data dummy digunakan")
        return None
    
    def create_strategy_for_symbol(symbol, **kwargs):
        logger.warning("create_strategy_for_symbol dummy digunakan")
        return TechnicalAnalysisStrategy()

try:
    print("✅ Mencoba import SoundNotifier...")
    from notifications.sound_notifier import SoundNotifier
    print("  ✅ SoundNotifier berhasil diimport")
except ImportError as e:
    print(f"  ❌ Gagal import SoundNotifier: {e}")
    # Buat dummy class
    class SoundNotifier:
        def __init__(self):
            pass
        def play_signal_sound(self, *args, **kwargs):
            logger.info("Sound notification (dummy)")

# PERBAIKAN: Import NonCryptoAssetsProvider setelah strategies
try:
    print("✅ Mencoba import NonCryptoAssetsProvider...")
    from non_crypto_assets_provider import NonCryptoAssetsProvider
    print("  ✅ NonCryptoAssetsProvider berhasil diimport")
except ImportError as e:
    print(f"  ❌ Gagal import NonCryptoAssetsProvider: {e}")
    # Buat dummy class sebagai fallback
    class NonCryptoAssetsProviderDummy:
        def __init__(self):
            self.cache = {}
            logger.warning("NonCryptoAssetsProvider dummy digunakan")
        
        def get_assets(self, category, limit=500, force_update=False):
            logger.warning(f"Dummy get_assets untuk {category}")
            if category == 'indonesia_stocks':
                return ['BBCA.JK', 'BBRI.JK', 'BMRI.JK', 'TLKM.JK', 'ASII.JK'][:limit]
            elif category == 'forex':
                return ['EURUSD=X', 'USDJPY=X', 'GBPUSD=X'][:limit]
            elif category == 'us_stocks':
                return ['AAPL', 'MSFT', 'GOOGL'][:limit]
            return []
        
        def get_active_assets(self, category, min_volume=1000000, min_volatility=0.025, limit=500):
            logger.warning(f"Dummy get_active_assets untuk {category}")
            return self.get_assets(category, limit)
    
    NonCryptoAssetsProvider = NonCryptoAssetsProviderDummy

try:
    print("✅ Mencoba import DatabaseHandler...")
    from database.db_handler import DatabaseHandler
    print("  ✅ DatabaseHandler berhasil diimport")
except ImportError as e2:
    print(f"  ❌ Gagal import DatabaseHandler: {e2}")
    # Buat dummy class
    class DatabaseHandler:
        def __init__(self):
            logger.warning("DatabaseHandler dummy digunakan")
        def get_active_positions(self, *args, **kwargs):
            return []
        def save_position(self, *args, **kwargs):
            return 1
        def update_position_current_price(self, *args, **kwargs):
            return True
        def close_position(self, *args, **kwargs):
            return True
        def get_trade_history(self, *args, **kwargs):
            return []

# PERBAIKAN UTAMA: Import data_provider dengan cara yang benar
print("\n🔧 Mengimport modul data_provider...")
try:
    # Import langsung karena satu folder
    import data_provider as data_provider_module
    print("✅ Modul data_provider berhasil diimport")
    
    # Assign setiap class secara individual
    if hasattr(data_provider_module, 'SmartChainDataProvider'):
        SmartChainDataProvider = data_provider_module.SmartChainDataProvider
        print("  ✅ SmartChainDataProvider ditemukan")
    
    if hasattr(data_provider_module, 'UnifiedDataProvider'):
        UnifiedDataProvider = data_provider_module.UnifiedDataProvider
        print("  ✅ UnifiedDataProvider ditemukan")
    
    if hasattr(data_provider_module, 'EnhancedYFinanceDataProvider'):
        EnhancedYFinanceDataProvider = data_provider_module.EnhancedYFinanceDataProvider
        print("  ✅ EnhancedYFinanceDataProvider ditemukan")
    
    if hasattr(data_provider_module, 'DataProviderMonitor'):
        DataProviderMonitor = data_provider_module.DataProviderMonitor
        print("  ✅ DataProviderMonitor ditemukan")
    
    if hasattr(data_provider_module, 'DynamicDataProvider'):
        DynamicDataProvider = data_provider_module.DynamicDataProvider
        print("  ✅ DynamicDataProvider ditemukan")
    
    if hasattr(data_provider_module, 'EnhancedCCXTDataProvider'):
        EnhancedCCXTDataProvider = data_provider_module.EnhancedCCXTDataProvider
        print("  ✅ EnhancedCCXTDataProvider ditemukan")
    
    if hasattr(data_provider_module, 'EnhancedCCXTFuturesProvider'):
        EnhancedCCXTFuturesProvider = data_provider_module.EnhancedCCXTFuturesProvider
        print("  ✅ EnhancedCCXTFuturesProvider ditemukan")
    
    if hasattr(data_provider_module, 'AlphaVantageProvider'):
        AlphaVantageProvider = data_provider_module.AlphaVantageProvider
        print("  ✅ AlphaVantageProvider ditemukan")
    
    if hasattr(data_provider_module, 'DataProviderFactory'):
        DataProviderFactory = data_provider_module.DataProviderFactory
        print("  ✅ DataProviderFactory ditemukan")
    
    if hasattr(data_provider_module, 'SolanaPumpFunProvider'):
        SolanaPumpFunProvider = data_provider_module.SolanaPumpFunProvider
        print("  ✅ SolanaPumpFunProvider ditemukan")
    
    if hasattr(data_provider_module, 'EnhancedDexScreenerProvider'):
        EnhancedDexScreenerProvider = data_provider_module.EnhancedDexScreenerProvider
        print("  ✅ EnhancedDexScreenerProvider ditemukan")
        
except Exception as e:
    print(f"❌ Error mengimport data_provider: {e}")
    print(f"   Traceback: {traceback.format_exc()}")
    
    # Buat dummy classes untuk semua provider
    print("🔄 Membuat dummy classes untuk data providers...")
    
    class UnifiedDataProvider:
        def __init__(self, *args, **kwargs):
            self.market_type = kwargs.get('market_type', 'crypto')
            self.trading_mode = kwargs.get('trading_mode', 'spot')
            self.active_exchange = 'yfinance_fallback'
            logger.warning("UnifiedDataProvider dummy digunakan")
        
        def get_popular_assets(self, limit=100, asset_type='spot'):
            return [{'symbol': 'BTC/USDT', 'name': 'Bitcoin'}]
        
        def get_ohlcv(self, symbol, timeframe, limit):
            dates = pd.date_range(end=datetime.now(), periods=limit, freq='1H')
            df = pd.DataFrame({
                'open': np.random.randn(limit) * 100 + 50000,
                'high': np.random.randn(limit) * 200 + 51000,
                'low': np.random.randn(limit) * 200 + 49000,
                'close': np.random.randn(limit) * 100 + 50000,
                'volume': np.random.rand(limit) * 1000
            }, index=dates)
            return df
        
        def get_ticker(self, symbol):
            return {'last': 50000, 'bid': 49900, 'ask': 50100}
        
        def search_assets(self, query, limit):
            return [{'symbol': 'BTC/USDT', 'name': 'Bitcoin'}]
    
    SmartChainDataProvider = None
    EnhancedYFinanceDataProvider = UnifiedDataProvider
    DataProviderMonitor = None
    DynamicDataProvider = UnifiedDataProvider
    EnhancedCCXTDataProvider = UnifiedDataProvider
    EnhancedCCXTFuturesProvider = UnifiedDataProvider
    AlphaVantageProvider = None
    DataProviderFactory = None
    SolanaPumpFunProvider = None
    EnhancedDexScreenerProvider = None

print("="*60)
print("IMPORT COMPLETED")
print("="*60 + "\n")

# =============================================
# HELPER FUNCTIONS - AUTO DETECTION & CONVERSION
# =============================================

def auto_detect_trading_type(symbol: str) -> Tuple[str, str]:
    """
    Auto-detect trading type (spot/futures) dari simbol.
    Returns: (trading_type, formatted_symbol)
    """
    symbol_upper = symbol.upper()
    
    # Deteksi futures dari format
    futures_markers = [':USDT', ':USDT:', 'PERP', 'FUTURES', 'FUTURE', ':PERP']
    
    for marker in futures_markers:
        if marker in symbol_upper:
            formatted = symbol_upper.replace('-', '/').replace('_', '/')
            return "futures", formatted
    
    # Default spot
    formatted = symbol_upper.replace('-', '/').replace('_', '/')
    return "spot", formatted

def convert_symbol_for_provider(symbol: str, provider_type: str) -> str:
    """
    Konversi simbol berdasarkan provider.
    
    Args:
        symbol: Simbol asli (BTC/USDT, BTC-USDT, BTC/USDT:USDT)
        provider_type: 'yfinance', 'ccxt', atau 'universal'
    
    Returns:
        Simbol yang diformat sesuai provider
    """
    if provider_type == 'yfinance':
        # Konversi untuk Yahoo Finance
        if '/USDT' in symbol:
            # Crypto: BTC/USDT -> BTC-USD
            return symbol.replace('/USDT', '-USD')
        elif ':USDT' in symbol:
            # Futures: BTC/USDT:USDT -> BTC-USD
            return symbol.replace(':USDT', '').replace('/', '-') + '-USD'
        elif '/' in symbol:
            # Pasangan lain: EUR/USD -> EURUSD=X
            base, quote = symbol.split('/')
            if quote in ['USD', 'EUR', 'GBP', 'JPY']:
                return f"{base}{quote}=X"
            else:
                return symbol.replace('/', '-')
        else:
            return symbol.replace('/', '-')
    
    elif provider_type == 'ccxt':
        # Untuk CCXT, format standar
        return symbol.replace('-', '/').replace('_', '/')
    
    else:  # universal
        # Format universal untuk kebanyakan provider
        return symbol.replace('-', '/').replace('_', '/')

# =============================================
# ENHANCED BACKTEST ENGINE
# =============================================

class BacktestEngine:
    """Enhanced backtesting engine dengan advanced features"""
    
    def __init__(self, initial_balance=10000):
        self.initial_balance = initial_balance
        self.results = {}
        self.parameter_results = []
        
    def run_backtest(self, df, strategy, **kwargs):
        """Run comprehensive backtest dengan multiple features"""
        try:
            # Extract parameters
            atr_multiplier = kwargs.get('atr_multiplier', 1.0)
            entry_range_pct = kwargs.get('entry_range_pct', 0.02)
            commission = kwargs.get('commission', 0.001)
            
            balance = self.initial_balance
            position = 0
            trades = []
            equity_curve = [balance]
            max_balance = balance
            max_drawdown = 0
            
            if df is None or df.empty or len(df) < 100:
                return self._get_empty_results()
            
            logger.info(f"🔄 Running backtest on {len(df)} bars...")
            
            for i in range(50, len(df)):
                current_data = df.iloc[:i+1]
                current_price = df['close'].iloc[i]
                current_time = df.index[i] if hasattr(df.index, 'iloc') else i
                
                # Get strategy analysis - GUNAKAN ANALISIS ENHANCED
                analysis = strategy.analyze_enhanced(current_data) if hasattr(strategy, 'analyze_enhanced') else strategy.analyze(current_data)
                
                if analysis and analysis['action'] in ['LONG', 'SHORT']:
                    current_trade = None
                    
                    # Check if we should enter a trade
                    if position == 0 and self._should_enter_trade(analysis, current_price):
                        position = 1 if analysis['action'] == 'LONG' else -1
                        
                        # Calculate position size with risk management
                        position_size = self._calculate_position_size(balance, current_price, analysis.get('atr', 0))
                        
                        entry_trade = {
                            'entry_time': current_time,
                            'entry_price': current_price,
                            'action': analysis['action'],
                            'size': position_size,
                            'commission_paid': position_size * current_price * commission
                        }
                        trades.append(entry_trade)
                        current_trade = entry_trade
                    
                    # Check if we should exit a trade
                    elif position != 0 and len(trades) > 0:
                        current_trade = trades[-1]
                        if current_trade.get('exit_time') is None:  # Still open
                            if self._should_exit_trade(current_trade, current_price, analysis, position):
                                # Calculate P&L
                                exit_price = current_price
                                price_change = exit_price - current_trade['entry_price']
                                pnl = price_change * current_trade['size'] * position
                                
                                # Apply commission on exit
                                exit_commission = current_trade['size'] * exit_price * commission
                                balance += pnl - exit_commission
                                
                                current_trade.update({
                                    'exit_time': current_time,
                                    'exit_price': exit_price,
                                    'pnl': pnl,
                                    'exit_commission': exit_commission,
                                    'total_commission': current_trade['commission_paid'] + exit_commission,
                                    'net_pnl': pnl - (current_trade['commission_paid'] + exit_commission)
                                })
                                position = 0
                                
                                # Update max drawdown
                                if balance > max_balance:
                                    max_balance = balance
                                current_drawdown = (max_balance - balance) / max_balance
                                max_drawdown = max(max_drawdown, current_drawdown)
                
                # Update equity curve
                if position != 0 and len(trades) > 0:
                    current_trade = trades[-1]
                    if current_trade.get('exit_time') is None:
                        unrealized_pnl = (current_price - current_trade['entry_price']) * current_trade['size'] * position
                        current_equity = balance + unrealized_pnl
                    else:
                        current_equity = balance
                    
                    equity_curve.append(current_equity)
                else:
                    equity_curve.append(balance)
            
            self.results = self._calculate_comprehensive_performance_metrics(trades, equity_curve)
            return self.results
            
        except Exception as e:
            logger.error(f"Error in backtest: {e}")
            return self._get_empty_results()
    
    def run_walk_forward_analysis(self, df, strategy_class, periods=5, **kwargs):
        """Walk-forward analysis for strategy validation"""
        try:
            if df is None or df.empty or len(df) < 200:
                return {"error": "Insufficient data for walk-forward analysis"}
            
            period_length = len(df) // periods
            results = []
            
            logger.info(f"🔍 Running walk-forward analysis with {periods} periods...")
            
            for i in range(periods):
                start_idx = i * period_length
                end_idx = start_idx + period_length if i < periods - 1 else len(df)
                
                train_data = df.iloc[:start_idx + period_length//2]
                test_data = df.iloc[start_idx + period_length//2:end_idx]
                
                if len(train_data) > 100 and len(test_data) > 50:
                    optimized_params = self._optimize_parameters(train_data, strategy_class, **kwargs)
                    
                    strategy = strategy_class(**optimized_params)
                    period_result = self.run_backtest(test_data, strategy, **optimized_params)
                    
                    period_result['period'] = i + 1
                    period_result['train_size'] = len(train_data)
                    period_result['test_size'] = len(test_data)
                    results.append(period_result)
                    
                    logger.info(f"  Period {i+1}: {period_result.get('total_trades', 0)} trades, Win Rate: {period_result.get('win_rate', 0):.1%}")
            
            if results:
                aggregate = self._aggregate_walk_forward_results(results)
                return {
                    'period_results': results,
                    'aggregate': aggregate,
                    'consistency_score': self._calculate_consistency_score(results)
                }
            else:
                return {"error": "No valid periods for analysis"}
                
        except Exception as e:
            logger.error(f"Error in walk-forward analysis: {e}")
            return {"error": str(e)}
    
    def run_parameter_optimization(self, df, strategy_class, param_grid, **kwargs):
        """Grid search for parameter optimization"""
        try:
            best_score = -float('inf')
            best_params = {}
            results = []
            
            logger.info("⚙️ Running parameter optimization...")
            
            param_combinations = self._generate_parameter_combinations(param_grid)
            
            for i, params in enumerate(param_combinations):
                try:
                    strategy = strategy_class(**params)
                    result = self.run_backtest(df, strategy, **params)
                    
                    score = result.get('sharpe_ratio', 0)
                    
                    optimization_result = {
                        'params': params.copy(),
                        'score': score,
                        'total_trades': result.get('total_trades', 0),
                        'win_rate': result.get('win_rate', 0),
                        'total_pnl': result.get('total_pnl', 0)
                    }
                    results.append(optimization_result)
                    
                    if score > best_score and result.get('total_trades', 0) >= 5:
                        best_score = score
                        best_params = params.copy()
                    
                    if (i + 1) % 10 == 0:
                        logger.info(f"  Completed {i+1}/{len(param_combinations)} combinations...")
                        
                except Exception as e:
                    logger.warning(f"  Skipping combination {params}: {e}")
                    continue
            
            results.sort(key=lambda x: x['score'], reverse=True)
            
            return {
                'best_params': best_params,
                'best_score': best_score,
                'top_results': results[:10],
                'all_results': results
            }
            
        except Exception as e:
            logger.error(f"Error in parameter optimization: {e}")
            return {"error": str(e)}
    
    def run_monte_carlo_simulation(self, trades, num_simulations=1000, confidence_level=0.95):
        """Monte Carlo simulation for strategy robustness"""
        try:
            if not trades or len(trades) < 10:
                return {"error": "Insufficient trades for Monte Carlo simulation"}
            
            pnl_values = [t.get('net_pnl', t.get('pnl', 0)) for t in trades if t.get('pnl') is not None]
            
            if len(pnl_values) < 10:
                return {"error": "Insufficient P&L data for simulation"}
            
            simulations = []
            num_trades = len(pnl_values)
            
            logger.info(f"🎲 Running Monte Carlo simulation ({num_simulations} iterations)...")
            
            for i in range(num_simulations):
                sampled_pnls = np.random.choice(pnl_values, size=num_trades, replace=True)
                sim_total = np.sum(sampled_pnls)
                sim_win_rate = np.sum(np.array(sampled_pnls) > 0) / num_trades
                
                simulations.append({
                    'total_pnl': sim_total,
                    'win_rate': sim_win_rate,
                    'avg_trade': np.mean(sampled_pnls)
                })
            
            total_pnls = [s['total_pnl'] for s in simulations]
            win_rates = [s['win_rate'] for s in simulations]
            
            pnl_sorted = sorted(total_pnls)
            win_rate_sorted = sorted(win_rates)
            
            lower_idx = int((1 - confidence_level) / 2 * num_simulations)
            upper_idx = int((1 - (1 - confidence_level) / 2) * num_simulations)
            
            return {
                'num_simulations': num_simulations,
                'original_pnl': sum(pnl_values),
                'original_win_rate': sum(1 for pnl in pnl_values if pnl > 0) / len(pnl_values),
                'monte_carlo_results': {
                    'pnl_mean': np.mean(total_pnls),
                    'pnl_std': np.std(total_pnls),
                    'pnl_confidence_interval': [pnl_sorted[lower_idx], pnl_sorted[upper_idx]],
                    'win_rate_mean': np.mean(win_rates),
                    'win_rate_confidence_interval': [win_rate_sorted[lower_idx], win_rate_sorted[upper_idx]],
                    'probability_profit': sum(1 for pnl in total_pnls if pnl > 0) / num_simulations,
                    'max_simulated_loss': min(total_pnls),
                    'best_simulated_profit': max(total_pnls)
                }
            }
            
        except Exception as e:
            logger.error(f"Error in Monte Carlo simulation: {e}")
            return {"error": str(e)}
    
    def _should_enter_trade(self, analysis, current_price):
        """Enhanced entry logic"""
        score = analysis.get('score', 0)
        if (score >= 2 or score <= -2) and analysis.get('risk_metrics', {}).get('reward_ratio', 0) > 1.5:
            if analysis.get('volume_ratio', 0) > 0.8:
                if analysis.get('rsi', 50) not in [0, 100]:
                    return True
        return False
    
    def _should_exit_trade(self, trade, current_price, analysis, position):
        """Enhanced exit logic with trailing stops"""
        entry_price = trade['entry_price']
        
        if trade['action'] == 'LONG':
            if current_price >= entry_price * 1.05:
                return True
            if current_price <= entry_price * 0.98:
                return True
            if hasattr(self, 'highest_price'):
                if current_price <= self.highest_price * 0.97:
                    return True
            else:
                self.highest_price = current_price
        else:
            if current_price <= entry_price * 0.95:
                return True
            if current_price >= entry_price * 1.02:
                return True
            if hasattr(self, 'lowest_price'):
                if current_price >= self.lowest_price * 1.03:
                    return True
            else:
                self.lowest_price = current_price
                
        return False
    
    def _calculate_position_size(self, balance, current_price, atr):
        """Position sizing with risk management"""
        risk_per_trade = 0.02
        risk_amount = balance * risk_per_trade
        
        if atr > 0:
            position_size = risk_amount / (atr * 2)
        else:
            position_size = (balance * 0.1) / current_price
        
        return min(position_size, (balance * 0.2) / current_price)
    
    def _calculate_comprehensive_performance_metrics(self, trades, equity_curve):
        """Enhanced performance metrics"""
        if not trades or len(equity_curve) < 2:
            return self._get_empty_results()
            
        closed_trades = [t for t in trades if t.get('exit_time') is not None]
        winning_trades = [t for t in closed_trades if t.get('net_pnl', t.get('pnl', 0)) > 0]
        losing_trades = [t for t in closed_trades if t.get('net_pnl', t.get('pnl', 0)) <= 0]
        
        total_trades = len(closed_trades)
        win_rate = len(winning_trades) / total_trades if total_trades else 0
        
        total_pnl = sum(t.get('net_pnl', t.get('pnl', 0)) for t in closed_trades)
        avg_win = np.mean([t.get('net_pnl', t.get('pnl', 0)) for t in winning_trades]) if winning_trades else 0
        avg_loss = np.mean([t.get('net_pnl', t.get('pnl', 0)) for t in losing_trades]) if losing_trades else 0
        profit_factor = abs(sum(t.get('net_pnl', t.get('pnl', 0)) for t in winning_trades) / 
                           sum(t.get('net_pnl', t.get('pnl', 0)) for t in losing_trades)) if losing_trades else float('inf')
        
        returns = np.diff(equity_curve) / np.array(equity_curve[:-1])
        volatility = np.std(returns) * np.sqrt(252) if len(returns) > 1 else 0
        sharpe_ratio = np.mean(returns) / np.std(returns) * np.sqrt(252) if len(returns) > 1 and np.std(returns) > 0 else 0
        
        equity_array = np.array(equity_curve)
        peak = np.maximum.accumulate(equity_array)
        drawdown = (equity_array - peak) / peak
        max_drawdown = np.min(drawdown) if len(drawdown) > 0 else 0
        
        trade_durations = []
        for trade in closed_trades:
            if 'entry_time' in trade and 'exit_time' in trade:
                if isinstance(trade['entry_time'], (int, float)) and isinstance(trade['exit_time'], (int, float)):
                    duration = trade['exit_time'] - trade['entry_time']
                    trade_durations.append(duration)
        
        avg_trade_duration = np.mean(trade_durations) if trade_durations else 0
        
        return {
            'total_trades': total_trades,
            'winning_trades': len(winning_trades),
            'losing_trades': len(losing_trades),
            'win_rate': win_rate,
            'total_pnl': total_pnl,
            'net_pnl': total_pnl,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': profit_factor,
            'sharpe_ratio': sharpe_ratio,
            'volatility': volatility,
            'max_drawdown': max_drawdown,
            'final_balance': equity_curve[-1],
            'equity_curve': equity_curve,
            'avg_trade_duration': avg_trade_duration,
            'total_commission': sum(t.get('total_commission', 0) for t in closed_trades),
            'risk_metrics': {
                'reward_ratio': abs(avg_win / avg_loss) if avg_loss != 0 else float('inf'),
                'expectancy': (win_rate * avg_win) + ((1 - win_rate) * avg_loss),
                'kelly_criterion': win_rate - (1 - win_rate) / (avg_win / abs(avg_loss)) if avg_loss != 0 else 0
            }
        }
    
    def _generate_parameter_combinations(self, param_grid):
        """Generate all parameter combinations for grid search"""
        from itertools import product
        
        keys = param_grid.keys()
        values = param_grid.values()
        combinations = [dict(zip(keys, v)) for v in product(*values)]
        return combinations
    
    def _optimize_parameters(self, df, strategy_class, **kwargs):
        """Simple parameter optimization for walk-forward"""
        default_params = {
            'atr_multiplier': 1.0,
            'entry_range_pct': 0.02,
            'market_type': kwargs.get('market_type', 'crypto')
        }
        
        best_score = -float('inf')
        best_params = default_params
        
        for atr_mult in [0.8, 1.0, 1.2, 1.5]:
            for entry_pct in [0.01, 0.02, 0.03]:
                params = default_params.copy()
                params['atr_multiplier'] = atr_mult
                params['entry_range_pct'] = entry_pct
                
                try:
                    strategy = strategy_class(**params)
                    result = self.run_backtest(df, strategy, **params)
                    score = result.get('sharpe_ratio', 0)
                    
                    if score > best_score and result.get('total_trades', 0) >= 3:
                        best_score = score
                        best_params = params
                except:
                    continue
        
        return best_params
    
    def _aggregate_walk_forward_results(self, results):
        """Aggregate results from walk-forward periods"""
        if not results:
            return {}
            
        aggregates = {
            'avg_win_rate': np.mean([r.get('win_rate', 0) for r in results]),
            'avg_sharpe': np.mean([r.get('sharpe_ratio', 0) for r in results]),
            'avg_trades': np.mean([r.get('total_trades', 0) for r in results]),
            'total_pnl': sum(r.get('total_pnl', 0) for r in results),
            'std_win_rate': np.std([r.get('win_rate', 0) for r in results]),
            'std_sharpe': np.std([r.get('sharpe_ratio', 0) for r in results]),
            'positive_periods': sum(1 for r in results if r.get('total_pnl', 0) > 0),
            'negative_periods': sum(1 for r in results if r.get('total_pnl', 0) <= 0)
        }
        
        return aggregates
    
    def _calculate_consistency_score(self, results):
        """Calculate strategy consistency score"""
        if not results:
            return 0
            
        win_rates = [r.get('win_rate', 0) for r in results]
        pnls = [r.get('total_pnl', 0) for r in results]
        
        win_rate_consistency = 1 - np.std(win_rates) / (np.mean(win_rates) + 1e-8)
        pnl_consistency = sum(1 for pnl in pnls if pnl > 0) / len(pnls)
        
        return (win_rate_consistency + pnl_consistency) / 2
    
    def _get_empty_results(self):
        return {
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'win_rate': 0,
            'total_pnl': 0,
            'net_pnl': 0,
            'sharpe_ratio': 0,
            'max_drawdown': 0,
            'final_balance': self.initial_balance,
            'equity_curve': [self.initial_balance],
            'risk_metrics': {
                'reward_ratio': 0,
                'expectancy': 0,
                'kelly_criterion': 0
            }
        }

# =============================================
# ENHANCED POSITION MANAGEMENT
# =============================================

class PositionState(Enum):
    ACTIVE = "active"
    PARTIAL_TP = "partial_tp"
    TRAILING = "trailing"
    CLOSED = "closed"

@dataclass
class EnhancedPosition:
    """Enhanced position management dengan trailing stop dan partial TP"""
    symbol: str
    market_type: str
    action: str
    entry_price: float
    position_size: float
    initial_stop_loss: float
    current_stop_loss: float
    take_profits: List[float]
    trailing_enabled: bool = False
    trailing_distance: float = 0.0
    partial_tp_executed: List[float] = None
    state: PositionState = PositionState.ACTIVE
    created_at: datetime = None
    last_updated: datetime = None
    
    def __post_init__(self):
        if self.partial_tp_executed is None:
            self.partial_tp_executed = []
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.last_updated is None:
            self.last_updated = datetime.now()
    
    def update_trailing_stop(self, current_price: float) -> bool:
        """Update trailing stop loss"""
        if not self.trailing_enabled or self.state != PositionState.ACTIVE:
            return False
            
        if self.action == "LONG":
            new_stop = current_price - self.trailing_distance
            if new_stop > self.current_stop_loss:
                self.current_stop_loss = new_stop
                self.last_updated = datetime.now()
                return True
        else:
            new_stop = current_price + self.trailing_distance
            if new_stop < self.current_stop_loss:
                self.current_stop_loss = new_stop
                self.last_updated = datetime.now()
                return True
        return False
    
    def execute_partial_tp(self, tp_level: float, percentage: float = 0.5) -> float:
        """Execute partial take profit"""
        if self.state != PositionState.ACTIVE:
            return 0.0
            
        close_size = self.position_size * percentage
        self.position_size -= close_size
        self.partial_tp_executed.append({
            'price': tp_level,
            'size': close_size,
            'timestamp': datetime.now()
        })
        
        if self.position_size <= 0.001:
            self.state = PositionState.CLOSED
            
        return close_size
    
    def should_close_position(self, current_price: float) -> Tuple[bool, str]:
        """Check if position should be closed"""
        reason = ""
        should_close = False
        
        if self.action == "LONG":
            if current_price <= self.current_stop_loss:
                should_close = True
                reason = "Stop loss hit"
            elif self.take_profits and current_price >= max(self.take_profits):
                should_close = True
                reason = "Final TP hit"
        else:
            if current_price >= self.current_stop_loss:
                should_close = True
                reason = "Stop loss hit"
            elif self.take_profits and current_price <= min(self.take_profits):
                should_close = True
                reason = "Final TP hit"
                
        return should_close, reason

class EnhancedPositionManager:
    """Advanced position management dengan risk-based sizing dan trailing stops"""
    
    def __init__(self, db_handler: DatabaseHandler):
        self.db_handler = db_handler
        self.positions: Dict[str, EnhancedPosition] = {}
        self.max_positions = 10
        self.max_portfolio_risk = 0.02
    
    def calculate_position_size(self, symbol: str, entry_price: float, stop_loss: float, 
                              account_balance: float, risk_per_trade: float = 0.01) -> float:
        """Calculate position size based on risk management"""
        if entry_price <= 0 or stop_loss <= 0:
            logger.warning(f"Invalid prices for {symbol}: entry={entry_price}, sl={stop_loss}")
            return 0.0
            
        risk_amount = account_balance * risk_per_trade
        
        if entry_price == stop_loss:
            logger.warning(f"Entry price equals stop loss for {symbol}")
            return 0.0
            
        price_risk = abs(entry_price - stop_loss)
        position_size = risk_amount / price_risk
        
        max_position_value = account_balance * 0.2
        max_position_size = max_position_value / entry_price
        
        return min(position_size, max_position_size)
    
    def open_position(self, symbol: str, market_type: str, action: str, 
                     entry_price: float, stop_loss: float, take_profits: List[float],
                     account_balance: float, trailing_distance: float = 0.0) -> Optional[EnhancedPosition]:
        """Open new position dengan enhanced management"""
        
        if entry_price <= 0:
            logger.error(f"Cannot open position for {symbol}: Invalid entry price {entry_price}")
            return None
        
        if len(self.positions) >= self.max_positions:
            logger.warning(f"Maximum positions reached ({self.max_positions}), cannot open new position for {symbol}")
            return None
        
        position_size = self.calculate_position_size(symbol, entry_price, stop_loss, account_balance)
        
        if position_size <= 0:
            logger.warning(f"Invalid position size for {symbol}")
            return None
        
        position = EnhancedPosition(
            symbol=symbol,
            market_type=market_type,
            action=action,
            entry_price=entry_price,
            position_size=position_size,
            initial_stop_loss=stop_loss,
            current_stop_loss=stop_loss,
            take_profits=take_profits,
            trailing_enabled=trailing_distance > 0,
            trailing_distance=trailing_distance
        )
        
        self.positions[symbol] = position
        
        try:
            position_id = self.db_handler.save_position(
                symbol=symbol,
                market_type=market_type,
                action=action,
                entry_price=entry_price,
                tp1=take_profits[0] if len(take_profits) > 0 else entry_price * 1.05,
                tp2=take_profits[1] if len(take_profits) > 1 else entry_price * 1.10,
                tp3=take_profits[2] if len(take_profits) > 2 else entry_price * 1.15,
                sl=stop_loss
            )
            
            if position_id:
                logger.info(f"Position opened for {symbol} with size {position_size:.4f}")
                return position
            else:
                logger.error(f"Failed to save position for {symbol} to database")
                del self.positions[symbol]
                return None
                
        except Exception as e:
            logger.error(f"Error saving position for {symbol}: {e}")
            del self.positions[symbol]
            return None
    
    def get_position_id_from_symbol(self, symbol: str, market_type: str) -> Optional[int]:
        """Get position ID from symbol"""
        try:
            active_positions = self.db_handler.get_active_positions(market_type)
            position_id = None
            
            for pos in active_positions:
                if isinstance(pos, dict):
                    if pos.get('symbol') == symbol:
                        position_id = pos.get('id')
                        break
                else:
                    if len(pos) > 1 and pos[1] == symbol:
                        position_id = pos[0]
                        break
            
            return position_id
            
        except Exception as e:
            logger.error(f"Error getting position ID for {symbol}: {e}")
            return None

    def update_positions(self, price_data: Dict[str, float]) -> Dict[str, Dict]:
        """Update all positions dengan current prices"""
        results = {}
        
        for symbol, position in list(self.positions.items()):
            if symbol not in price_data:
                continue
                
            current_price = price_data[symbol]
            close_position, reason = position.should_close_position(current_price)
            
            if position.trailing_enabled:
                position.update_trailing_stop(current_price)
            
            partial_tp_executed = self._check_partial_tp(position, current_price)
            
            if close_position:
                success = self.close_position(symbol, current_price, reason)
                results[symbol] = {
                    'action': 'closed',
                    'reason': reason,
                    'price': current_price,
                    'success': success
                }
            elif partial_tp_executed:
                results[symbol] = {
                    'action': 'partial_tp',
                    'size': partial_tp_executed,
                    'price': current_price
                }
            else:
                try:
                    self.db_handler.update_position_current_price(symbol, current_price)
                except Exception as e:
                    logger.warning(f"Failed to update price for {symbol}: {e}")
        
        return results
    
    def _check_partial_tp(self, position: EnhancedPosition, current_price: float) -> float:
        """Check and execute partial take profits"""
        if position.state != PositionState.ACTIVE:
            return 0.0
            
        executed_size = 0.0
        
        for i, tp_level in enumerate(position.take_profits):
            if position.action == "LONG" and current_price >= tp_level:
                tp_executed = any(tp.get('level', i) == i for tp in position.partial_tp_executed)
                if not tp_executed:
                    size = position.execute_partial_tp(tp_level, 0.33)
                    executed_size += size
                    logger.info(f"Partial TP executed for {position.symbol} at {tp_level:.4f}, size: {size:.4f}")
                    
            elif position.action == "SHORT" and current_price <= tp_level:
                tp_executed = any(tp.get('level', i) == i for tp in position.partial_tp_executed)
                if not tp_executed:
                    size = position.execute_partial_tp(tp_level, 0.33)
                    executed_size += size
                    logger.info(f"Partial TP executed for {position.symbol} at {tp_level:.4f}, size: {size:.4f}")
        
        return executed_size
    
    def close_position(self, symbol: str, close_price: float, reason: str = "manual") -> bool:
        """Close position"""
        if symbol not in self.positions:
            logger.warning(f"Position for {symbol} not found in local manager")
            return False
            
        position = self.positions[symbol]
        
        try:
            position_id = self.get_position_id_from_symbol(symbol, position.market_type)
            
            if position_id:
                success = self.db_handler.close_position(position_id, close_price, reason)
                if success:
                    position.state = PositionState.CLOSED
                    del self.positions[symbol]
                    logger.info(f"Position closed for {symbol} at {close_price:.4f}, reason: {reason}")
                    return True
                else:
                    logger.error(f"Failed to close position for {symbol} in database")
                    return False
            else:
                logger.warning(f"Position ID not found for {symbol} in database")
                return False
                
        except Exception as e:
            logger.error(f"Error closing position for {symbol}: {e}")
            return False
    
    def get_portfolio_metrics(self, current_prices: Dict[str, float]) -> Dict[str, Any]:
        """Calculate portfolio performance metrics"""
        total_value = 0.0
        total_pnl = 0.0
        open_positions = []
        
        for symbol, position in self.positions.items():
            if symbol not in current_prices:
                continue
                
            current_price = current_prices[symbol]
            position_value = position.position_size * current_price
            
            if position.action == "LONG":
                pnl = (current_price - position.entry_price) * position.position_size
            else:
                pnl = (position.entry_price - current_price) * position.position_size
            
            total_value += position_value
            total_pnl += pnl
            
            open_positions.append({
                'symbol': symbol,
                'action': position.action,
                'entry_price': position.entry_price,
                'current_price': current_price,
                'size': position.position_size,
                'pnl': pnl,
                'pnl_pct': (pnl / (position.entry_price * position.position_size)) * 100 if position.entry_price * position.position_size > 0 else 0
            })
        
        return {
            'total_positions': len(self.positions),
            'total_value': total_value,
            'total_pnl': total_pnl,
            'open_positions': open_positions,
            'avg_pnl_pct': np.mean([p['pnl_pct'] for p in open_positions]) if open_positions else 0
        }

# =============================================
# ENHANCED ML MODEL WITH ENSEMBLE
# =============================================

class EnsembleMLModel:
    """Enhanced ML model dengan ensemble methods dan advanced feature engineering"""
    
    def __init__(self, model_types: List[str] = None):
        self.model_types = model_types or ['random_forest', 'xgboost', 'lightgbm']
        self.models = {}
        self.scalers = {}
        self.feature_importance = {}
        self.is_trained = False
        self.model_weights = {}
        
        self.feature_config = {
            'price_features': ['rsi', 'macd', 'sma_20', 'sma_50', 'ema_12', 'ema_26'],
            'volume_features': ['volume_ratio', 'obv', 'volume_sma_ratio'],
            'volatility_features': ['atr', 'bb_width', 'volatility'],
            'momentum_features': ['momentum_5', 'momentum_10', 'williams_r', 'cci'],
            'pattern_features': ['pattern_score', 'trend_strength']
        }
        
        self._initialize_models()
    
    def _initialize_models(self):
        """Initialize multiple ML models"""
        for model_type in self.model_types:
            if model_type == 'random_forest':
                self.models[model_type] = RandomForestClassifier(
                    n_estimators=200,
                    max_depth=15,
                    min_samples_split=5,
                    min_samples_leaf=2,
                    random_state=42,
                    n_jobs=-1,
                    bootstrap=True,
                    max_features='sqrt'
                )
            elif model_type == 'xgboost':
                self.models[model_type] = XGBClassifier(
                    n_estimators=200,
                    max_depth=8,
                    learning_rate=0.1,
                    random_state=42,
                    n_jobs=-1,
                    subsample=0.8,
                    colsample_bytree=0.8
                )
            elif model_type == 'lightgbm':
                self.models[model_type] = lgb.LGBMClassifier(
                    n_estimators=200,
                    max_depth=8,
                    learning_rate=0.1,
                    random_state=42,
                    n_jobs=-1,
                    subsample=0.8,
                    colsample_bytree=0.8
                )
            elif model_type == 'logistic':
                self.models[model_type] = LogisticRegression(
                    random_state=42,
                    max_iter=1000,
                    C=1.0,
                    solver='liblinear'
                )
            
            self.scalers[model_type] = RobustScaler()
            self.model_weights[model_type] = 1.0
    
    def advanced_feature_engineering(self, df: pd.DataFrame) -> pd.DataFrame:
        """Advanced feature engineering dengan technical indicators"""
        if df is None or df.empty or len(df) < 50:
            return pd.DataFrame()
        
        features = {}
        prices = df['close'].values
        volumes = df['volume'].values if 'volume' in df.columns else np.ones(len(df))
        
        if len(prices) == 0 or (prices <= 0).any():
            logger.warning("Invalid price data in feature engineering")
            return pd.DataFrame()
        
        if len(prices) >= 20:
            features['rsi'] = self._calculate_rsi(prices)
            features['macd'] = self._calculate_macd(prices)
            features['sma_20'] = np.mean(prices[-20:])
            features['sma_50'] = np.mean(prices[-min(50, len(prices)):])
            features['ema_12'] = self._calculate_ema(prices, 12)
            features['ema_26'] = self._calculate_ema(prices, 26)
            
            bb_upper, bb_lower, bb_middle = self._calculate_bollinger_bands(prices)
            features['bb_width'] = (bb_upper - bb_lower) / bb_middle if bb_middle > 0 else 0
            features['bb_position'] = (prices[-1] - bb_lower) / (bb_upper - bb_lower) if (bb_upper - bb_lower) > 0 else 0.5
        
        if len(volumes) >= 20:
            features['volume_ratio'] = volumes[-1] / np.mean(volumes[-20:]) if np.mean(volumes[-20:]) > 0 else 1
            features['volume_sma_ratio'] = volumes[-1] / np.mean(volumes) if np.mean(volumes) > 0 else 1
            features['obv'] = self._calculate_obv(prices, volumes)
        
        if len(prices) >= 20:
            features['atr'] = self._calculate_atr(df) if len(df) >= 14 else 0.02
            
            if features['atr'] <= 0:
                features['atr'] = prices[-1] * 0.001
                
            returns = np.diff(prices) / prices[:-1]
            features['volatility'] = np.std(returns) * np.sqrt(252) if len(returns) > 1 else 0.02
        
        if len(prices) >= 10:
            features['momentum_5'] = (prices[-1] / prices[-5] - 1) * 100 if prices[-5] > 0 else 0
            features['momentum_10'] = (prices[-1] / prices[-10] - 1) * 100 if prices[-10] > 0 else 0
            features['williams_r'] = self._calculate_williams_r(df)
            features['cci'] = self._calculate_cci(df)
        
        if len(prices) >= 20:
            features['skewness'] = stats.skew(prices[-20:])
            features['kurtosis'] = stats.kurtosis(prices[-20:])
            features['z_score'] = (prices[-1] - np.mean(prices[-20:])) / np.std(prices[-20:]) if np.std(prices[-20:]) > 0 else 0
        
        if len(prices) >= 10:
            features['trend_strength'] = self._calculate_trend_strength(prices)
            recent_trend = np.polyfit(range(5), prices[-5:], 1)[0]
            features['pattern_score'] = recent_trend * 100
        
        for key in features:
            if np.isnan(features[key]) or np.isinf(features[key]):
                features[key] = 0.0
        
        return pd.DataFrame([features])
    
    def _calculate_rsi(self, prices, period=14):
        """Calculate RSI"""
        if len(prices) < period + 1:
            return 50
        delta = np.diff(prices)
        gain = np.where(delta > 0, delta, 0)
        loss = np.where(delta < 0, -delta, 0)
        
        avg_gain = np.mean(gain[-period:])
        avg_loss = np.mean(loss[-period:])
        
        if avg_loss == 0:
            return 100
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))
    
    def _calculate_macd(self, prices):
        """Calculate MACD"""
        if len(prices) < 26:
            return 0
        exp1 = pd.Series(prices).ewm(span=12).mean().iloc[-1]
        exp2 = pd.Series(prices).ewm(span=26).mean().iloc[-1]
        return exp1 - exp2
    
    def _calculate_ema(self, prices, period):
        """Calculate EMA"""
        if len(prices) < period:
            return np.mean(prices)
        return pd.Series(prices).ewm(span=period).mean().iloc[-1]
    
    def _calculate_bollinger_bands(self, prices, period=20, std_dev=2):
        """Calculate Bollinger Bands"""
        if len(prices) < period:
            middle = np.mean(prices)
            std = np.std(prices) if len(prices) > 1 else 0.1
            return middle + std_dev * std, middle - std_dev * std, middle
        
        middle = np.mean(prices[-period:])
        std = np.std(prices[-period:])
        return middle + std_dev * std, middle - std_dev * std, middle
    
    def _calculate_obv(self, prices, volumes):
        """Calculate OBV"""
        if len(prices) < 2:
            return 0
        obv = 0
        for i in range(1, len(prices)):
            if prices[i] > prices[i-1]:
                obv += volumes[i]
            elif prices[i] < prices[i-1]:
                obv -= volumes[i]
        return obv
    
    def _calculate_atr(self, df, period=14):
        """Calculate ATR dengan fallback yang lebih baik"""
        try:
            if df is None or df.empty or len(df) < period:
                return df['close'].iloc[-1] * 0.02 if len(df) > 0 else 0.02
                
            high = df['high'].values
            low = df['low'].values
            close = df['close'].values
            
            tr = np.zeros(len(high))
            for i in range(1, len(high)):
                tr1 = high[i] - low[i]
                tr2 = abs(high[i] - close[i-1])
                tr3 = abs(low[i] - close[i-1])
                tr[i] = max(tr1, tr2, tr3)
            
            atr_value = np.mean(tr[-period:]) if len(tr) >= period else np.mean(tr)
            
            if atr_value <= 0:
                atr_value = df['close'].iloc[-1] * 0.01
                
            return atr_value
        except:
            return df['close'].iloc[-1] * 0.02 if len(df) > 0 else 0.02
    
    def _calculate_williams_r(self, df, period=14):
        """Calculate Williams %R"""
        try:
            high = df['high'].values[-period:]
            low = df['low'].values[-period:]
            close = df['close'].iloc[-1]
            
            highest_high = np.max(high)
            lowest_low = np.min(low)
            
            if highest_high == lowest_low:
                return -50
            return -100 * (highest_high - close) / (highest_high - lowest_low)
        except:
            return -50
    
    def _calculate_cci(self, df, period=20):
        """Calculate CCI"""
        try:
            typical_price = (df['high'] + df['low'] + df['close']) / 3
            sma = typical_price.rolling(period).mean().iloc[-1]
            mad = typical_price.rolling(period).apply(lambda x: np.mean(np.abs(x - np.mean(x)))).iloc[-1]
            
            if mad == 0:
                return 0
            return (typical_price.iloc[-1] - sma) / (0.015 * mad)
        except:
            return 0
    
    def _calculate_trend_strength(self, prices, period=10):
        """Calculate trend strength using linear regression"""
        if len(prices) < period:
            return 0
        x = np.arange(period)
        y = prices[-period:]
        slope, _, r_value, _, _ = stats.linregress(x, y)
        return slope * r_value ** 2
    
    def train_ensemble(self, X: np.ndarray, y: np.ndarray, validation_size: float = 0.2):
        """Train ensemble of models dengan cross-validation"""
        if len(X) < 100:
            logger.warning("Insufficient data for training ensemble")
            return False
        
        X_train, X_val, y_train, y_val = train_test_split(
            X, y, test_size=validation_size, shuffle=False, random_state=42
        )
        
        model_scores = {}
        
        for model_name, model in self.models.items():
            try:
                X_train_scaled = self.scalers[model_name].fit_transform(X_train)
                X_val_scaled = self.scalers[model_name].transform(X_val)
                
                model.fit(X_train_scaled, y_train)
                
                y_pred = model.predict(X_val_scaled)
                accuracy = accuracy_score(y_val, y_pred)
                precision, recall, f1, _ = precision_recall_fscore_support(y_val, y_pred, average='weighted')
                
                model_scores[model_name] = {
                    'accuracy': accuracy,
                    'precision': precision,
                    'recall': recall,
                    'f1': f1
                }
                
                self.model_weights[model_name] = f1
                
                logger.info(f"Model {model_name} trained - Accuracy: {accuracy:.3f}, F1: {f1:.3f}")
                
            except Exception as e:
                logger.error(f"Error training {model_name}: {e}")
                model_scores[model_name] = {'accuracy': 0, 'f1': 0}
                self.model_weights[model_name] = 0.1
        
        total_weight = sum(self.model_weights.values())
        if total_weight > 0:
            for model_name in self.model_weights:
                self.model_weights[model_name] /= total_weight
        
        self.is_trained = True
        logger.info(f"Ensemble training completed. Model weights: {self.model_weights}")
        return True
    
    def predict_ensemble(self, X: np.ndarray) -> Tuple[float, int]:
        """Predict using ensemble dengan weighted voting"""
        if not self.is_trained or len(self.models) == 0:
            return 0.5, 0
        
        predictions = []
        confidences = []
        weights = []
        
        for model_name, model in self.models.items():
            try:
                if self.model_weights[model_name] > 0.01:
                    X_scaled = self.scalers[model_name].transform(X)
                    
                    if hasattr(model, 'predict_proba'):
                        proba = model.predict_proba(X_scaled)
                        confidence = np.max(proba)
                        prediction = np.argmax(proba)
                    else:
                        prediction = model.predict(X_scaled)[0]
                        confidence = 0.5
                    
                    predictions.append(prediction)
                    confidences.append(confidence)
                    weights.append(self.model_weights[model_name])
                    
            except Exception as e:
                logger.warning(f"Prediction failed for {model_name}: {e}")
                continue
        
        if not predictions:
            return 0.5, 0
        
        weighted_predictions = np.average(predictions, weights=weights)
        final_prediction = 1 if weighted_predictions > 0.5 else 0
        final_confidence = np.average(confidences, weights=weights)
        
        return final_confidence, final_prediction

# =============================================
# ADVANCED PORTFOLIO OPTIMIZATION
# =============================================

class PortfolioOptimizer:
    """Advanced portfolio optimization menggunakan Modern Portfolio Theory"""
    
    def __init__(self):
        self.risk_free_rate = 0.02
        self.max_allocation_per_asset = 0.2
        self.min_allocation_per_asset = 0.05
    
    def mean_variance_optimization(self, expected_returns: List[float], 
                                 covariance_matrix: np.ndarray,
                                 target_return: float = None) -> Dict[str, Any]:
        """Mean-variance optimization (Markowitz)"""
        n_assets = len(expected_returns)
        
        if n_assets == 0:
            return {'weights': [], 'sharpe_ratio': 0, 'portfolio_return': 0, 'portfolio_risk': 0}
        
        try:
            equal_weights = np.ones(n_assets) / n_assets
            
            port_return = np.dot(equal_weights, expected_returns)
            port_risk = np.sqrt(np.dot(equal_weights.T, np.dot(covariance_matrix, equal_weights)))
            sharpe_ratio = (port_return - self.risk_free_rate) / port_risk if port_risk > 0 else 0
            
            weights = self._apply_allocation_constraints(equal_weights)
            
            return {
                'weights': weights.tolist(),
                'sharpe_ratio': sharpe_ratio,
                'portfolio_return': port_return,
                'portfolio_risk': port_risk,
                'efficient_frontier': self._calculate_efficient_frontier(expected_returns, covariance_matrix)
            }
            
        except Exception as e:
            logger.error(f"Portfolio optimization error: {e}")
            weights = np.ones(n_assets) / n_assets
            return {
                'weights': weights.tolist(),
                'sharpe_ratio': 0,
                'portfolio_return': np.mean(expected_returns),
                'portfolio_risk': np.mean(np.diag(covariance_matrix)),
                'efficient_frontier': []
            }
    
    def risk_parity_allocation(self, volatility_estimates: List[float]) -> List[float]:
        """Risk parity allocation - equal risk contribution"""
        if not volatility_estimates or len(volatility_estimates) == 0:
            return []
        
        inv_volatility = [1/v if v > 0 else 0 for v in volatility_estimates]
        total_inv_vol = sum(inv_volatility)
        
        if total_inv_vol == 0:
            return [1/len(volatility_estimates)] * len(volatility_estimates)
        
        weights = [inv_vol / total_inv_vol for inv_vol in inv_volatility]
        return self._apply_allocation_constraints(weights)
    
    def momentum_based_allocation(self, signals: List[Dict], total_capital: float) -> List[Dict]:
        """Momentum-based portfolio allocation"""
        if not signals:
            return []
        
        sorted_signals = sorted(signals, key=lambda x: abs(x.get('score', 0)), reverse=True)
        
        scores = [abs(s.get('score', 0)) for s in sorted_signals]
        volatilities = [s.get('volatility', 0.02) for s in sorted_signals]
        
        if sum(scores) == 0:
            base_allocation = total_capital / len(signals)
            return [
                {
                    'symbol': s['symbol'],
                    'allocation_percent': 1/len(signals),
                    'allocated_capital': base_allocation,
                    'score': s.get('score', 0)
                }
                for s in sorted_signals
            ]
        
        weights = []
        for i, signal in enumerate(sorted_signals):
            score_weight = scores[i] / sum(scores)
            vol_weight = 1 / (volatilities[i] + 0.01)
            combined_weight = score_weight * vol_weight
            weights.append(combined_weight)
        
        total_weight = sum(weights)
        normalized_weights = [w / total_weight for w in weights]
        
        constrained_weights = self._apply_allocation_constraints(normalized_weights)
        
        allocations = []
        for i, signal in enumerate(sorted_signals):
            allocation_percent = constrained_weights[i] if i < len(constrained_weights) else 0
            allocated_capital = total_capital * allocation_percent
            
            allocations.append({
                'symbol': signal['symbol'],
                'allocation_percent': allocation_percent,
                'allocated_capital': allocated_capital,
                'score': signal.get('score', 0),
                'action': signal.get('action', 'NEUTRAL')
            })
        
        return allocations
    
    def _apply_allocation_constraints(self, weights: List[float]) -> List[float]:
        """Apply allocation constraints to weights"""
        if not weights:
            return []
        
        n_assets = len(weights)
        constrained_weights = np.array(weights, dtype=float)
        
        min_weight = self.min_allocation_per_asset
        constrained_weights[constrained_weights < min_weight] = 0
        
        max_weight = self.max_allocation_per_asset
        constrained_weights[constrained_weights > max_weight] = max_weight
        
        total_weight = np.sum(constrained_weights)
        if total_weight > 0:
            constrained_weights /= total_weight
        else:
            constrained_weights = np.ones(n_assets) / n_assets
        
        return constrained_weights.tolist()
    
    def _calculate_efficient_frontier(self, expected_returns: List[float], 
                                    covariance_matrix: np.ndarray, 
                                    points: int = 20) -> List[Dict]:
        """Calculate efficient frontier points"""
        frontiers = []
        
        for i in range(points):
            target_return = np.min(expected_returns) + (np.max(expected_returns) - np.min(expected_returns)) * i / points
            
            weights = np.ones(len(expected_returns)) / len(expected_returns)
            portfolio_return = np.dot(weights, expected_returns)
            portfolio_risk = np.sqrt(np.dot(weights.T, np.dot(covariance_matrix, weights)))
            
            frontiers.append({
                'return': portfolio_return,
                'risk': portfolio_risk,
                'sharpe_ratio': (portfolio_return - self.risk_free_rate) / portfolio_risk if portfolio_risk > 0 else 0
            })
        
        return frontiers

# =============================================
# ENHANCED ML BOT
# =============================================

class MLEnhancedBot:
    """Machine Learning enhanced trading bot"""
    
    def __init__(self, model_type='random_forest'):
        self.model_type = model_type
        self.model = None
        self.scaler = StandardScaler()
        self.is_trained = False
        self.model_path = "models/trading_model.pkl"
        self.scaler_path = "models/scaler.pkl"
        self.feature_importance = {}
        
        os.makedirs("models", exist_ok=True)
        
        self.load_model()

    def load_model(self):
        """Load model dan scaler yang sudah ditraining"""
        try:
            if (os.path.exists(self.model_path) and 
                os.path.exists(self.scaler_path) and
                os.path.getsize(self.model_path) > 1000):
                
                self.model = None
                self.scaler = None
                
                self.model = joblib.load(self.model_path)
                self.scaler = joblib.load(self.scaler_path)
                
                if (hasattr(self.model, 'predict') and 
                    hasattr(self.scaler, 'transform')):
                    self.is_trained = True
                    logger.info("✅ ML model loaded successfully")
                    return True
                else:
                    logger.error("❌ Loaded model invalid")
                    self._initialize_model()
                    return False
            else:
                logger.warning("Model files not found or too small, initializing new model")
                self._initialize_model()
                return False
                
        except Exception as e:
            logger.error(f"❌ Error loading model: {e}")
            self._initialize_model()
            return False

    def save_model(self):
        """Save model dan scaler"""
        try:
            if self.model and self.scaler:
                joblib.dump(self.model, self.model_path)
                joblib.dump(self.scaler, self.scaler_path)
                logger.info("✅ ML model saved successfully")
                return True
        except Exception as e:
            logger.error(f"❌ Error saving model: {e}")
        return False

    def _initialize_model(self):
        """Initialize model baru"""
        if self.model_type == 'random_forest':
            self.model = RandomForestClassifier(
                n_estimators=100,
                max_depth=10,
                min_samples_split=5,
                min_samples_leaf=2,
                random_state=42,
                n_jobs=-1
            )
        elif self.model_type == 'gradient_boosting':
            self.model = GradientBoostingClassifier(
                n_estimators=100,
                max_depth=6,
                learning_rate=0.1,
                random_state=42
            )
        
        self.is_trained = False
        logger.info("🔄 New ML model initialized")

    def prepare_training_data(self, historical_data):
        """Prepare training data dari historical data"""
        try:
            features_list = []
            targets = []
            
            for symbol, data in historical_data.items():
                if data is None or data.empty or len(data) < 100:
                    continue
                    
                for i in range(50, len(data) - 10):
                    current_window = data.iloc[:i+1]
                    future_window = data.iloc[i+1:i+11]
                    
                    features = self._extract_detailed_features(current_window)
                    if features:
                        current_price = current_window['close'].iloc[-1]
                        future_max = future_window['close'].max()
                        future_min = future_window['close'].min()
                        
                        price_change = (future_max - current_price) / current_price
                        if price_change >= 0.02:
                            target = 1
                        elif (future_min - current_price) / current_price <= -0.02:
                            target = -1
                        else:
                            target = 0
                            
                        features_list.append(features)
                        targets.append(target)
            
            if len(features_list) < 100:
                return None, None
                
            return np.array(features_list), np.array(targets)
            
        except Exception as e:
            logger.error(f"❌ Error preparing training data: {e}")
            return None, None

    def train_model(self, historical_data, test_size=0.2):
        """Train model dengan historical data"""
        try:
            logger.info("🔄 Preparing training data...")
            X, y = self.prepare_training_data(historical_data)
            
            if X is None or len(X) < 100:
                logger.error("❌ Insufficient training data")
                return False
            
            logger.info(f"📊 Training data shape: {X.shape}, targets: {y.shape}")
            
            tscv = TimeSeriesSplit(n_splits=5)
            accuracies = []
            
            for train_idx, test_idx in tscv.split(X):
                X_train, X_test = X[train_idx], X[test_idx]
                y_train, y_test = y[train_idx], y[test_idx]
                
                X_train_scaled = self.scaler.fit_transform(X_train)
                X_test_scaled = self.scaler.transform(X_test)
                
                self.model.fit(X_train_scaled, y_train)
                
                y_pred = self.model.predict(X_test_scaled)
                accuracy = accuracy_score(y_test, y_pred)
                accuracies.append(accuracy)
            
            X_scaled = self.scaler.fit_transform(X)
            self.model.fit(X_scaled, y)
            
            if hasattr(self.model, 'feature_importances_'):
                feature_names = [
                    'rsi', 'macd', 'sma_20', 'sma_50', 'ema_12', 'ema_26',
                    'atr', 'volume_ratio', 'price_change_1d', 'price_change_5d',
                    'volatility', 'momentum', 'williams_r', 'cci', 'obv'
                ]
                if len(self.model.feature_importances_) == len(feature_names):
                    self.feature_importance = dict(zip(feature_names, self.model.feature_importances_))
                else:
                    self.feature_importance = {f: 0.0 for f in feature_names}
            
            self.is_trained = True
            avg_accuracy = np.mean(accuracies)
            
            logger.info(f"✅ Model training completed! Average Accuracy: {avg_accuracy:.3f}")
            logger.info(f"📈 Feature Importance: {self.feature_importance}")
            
            self.save_model()
            return True
            
        except Exception as e:
            logger.error(f"❌ Error training model: {e}")
            return False

    def _extract_detailed_features(self, df):
        """Extract detailed features untuk training dan prediction"""
        try:
            if df is None or df.empty or len(df) < 50:
                return None
                
            features = {}
            
            prices = df['close']
            volumes = df['volume']
            
            features['rsi'] = self._calculate_rsi(prices)
            features['macd'] = self._calculate_macd(prices)
            features['sma_20'] = prices.rolling(20).mean().iloc[-1] if len(prices) >= 20 else prices.mean()
            features['sma_50'] = prices.rolling(50).mean().iloc[-1] if len(prices) >= 50 else prices.mean()
            features['ema_12'] = prices.ewm(span=12).mean().iloc[-1]
            features['ema_26'] = prices.ewm(span=26).mean().iloc[-1]
            
            features['atr'] = self._calculate_atr(df)
            
            vol_mean = volumes.rolling(20).mean().iloc[-1] if len(volumes) >= 20 else volumes.mean()
            features['volume_ratio'] = volumes.iloc[-1] / vol_mean if vol_mean > 0 else 1
            
            if len(df) > 1:
                features['price_change_1d'] = (prices.iloc[-1] - prices.iloc[-2]) / prices.iloc[-2] if prices.iloc[-2] != 0 else 0
            else:
                features['price_change_1d'] = 0
                
            if len(df) > 5:
                features['price_change_5d'] = (prices.iloc[-1] - prices.iloc[-6]) / prices.iloc[-6] if prices.iloc[-6] != 0 else 0
            else:
                features['price_change_5d'] = 0
            
            features['volatility'] = prices.pct_change().std() * np.sqrt(252) if len(prices) > 1 else 0.02
            features['momentum'] = (prices.iloc[-1] - prices.iloc[-10]) / prices.iloc[-10] if len(prices) > 10 and prices.iloc[-10] != 0 else 0
            features['williams_r'] = self._calculate_williams_r(df)
            features['cci'] = self._calculate_cci(df)
            features['obv'] = self._calculate_obv(df)
            
            for key, value in features.items():
                if pd.isna(value):
                    features[key] = 0
            
            return list(features.values())
            
        except Exception as e:
            logger.error(f"❌ Error extracting features: {e}")
            return None

    def extract_features(self, df):
        """Extract features untuk prediction real-time"""
        try:
            features = self._extract_detailed_features(df)
            if features is None:
                return pd.DataFrame([self._get_default_features()])
            
            feature_names = [
                'rsi', 'macd', 'sma_20', 'sma_50', 'ema_12', 'ema_26',
                'atr', 'volume_ratio', 'price_change_1d', 'price_change_5d',
                'volatility', 'momentum', 'williams_r', 'cci', 'obv'
            ]
            
            return pd.DataFrame([features], columns=feature_names)
            
        except Exception as e:
            logger.error(f"❌ Error in extract_features: {e}")
            return pd.DataFrame([self._get_default_features()])

    def _get_default_features(self):
        """Return default features jika extraction gagal"""
        return [50, 0, 0, 0, 0, 0, 0.02, 1, 0, 0, 0.02, 0, -50, 0, 0]

    def predict(self, df):
        """Predict menggunakan model ML"""
        try:
            if not self.is_trained or self.model is None:
                return 0.5, 0
            
            features_df = self.extract_features(df)
            if features_df is None or features_df.empty:
                return 0.5, 0
            
            features_scaled = self.scaler.transform(features_df)
            
            prediction = self.model.predict(features_scaled)[0]
            probabilities = self.model.predict_proba(features_scaled)[0]
            
            confidence = np.max(probabilities)
            
            return confidence, prediction
            
        except Exception as e:
            logger.error(f"❌ Error in ML prediction: {e}")
            return 0.5, 0

    def batch_predict(self, symbols_data):
        """Batch prediction untuk multiple symbols"""
        try:
            if not self.is_trained:
                return {}
            
            predictions = {}
            features_list = []
            symbol_features = {}
            
            for symbol, df in symbols_data.items():
                features_df = self.extract_features(df)
                if features_df is not None and not features_df.empty:
                    features_list.append(features_df.iloc[0].values)
                    symbol_features[symbol] = features_df.iloc[0].values
            
            if not features_list:
                return {}
            
            features_array = np.array(features_list)
            features_scaled = self.scaler.transform(features_array)
            
            batch_predictions = self.model.predict(features_scaled)
            batch_probabilities = self.model.predict_proba(features_array)
            
            for i, (symbol, features) in enumerate(symbol_features.items()):
                if i < len(batch_predictions):
                    predictions[symbol] = {
                        'direction': batch_predictions[i],
                        'confidence': np.max(batch_probabilities[i]),
                        'probability_up': batch_probabilities[i][1] if len(batch_probabilities[i]) > 1 else 0.5,
                        'probability_down': batch_probabilities[i][-1] if len(batch_probabilities[i]) > 2 else 0.5
                    }
            
            return predictions
            
        except Exception as e:
            logger.error(f"❌ Error in batch prediction: {e}")
            return {}

    # Technical Indicators
    def _calculate_rsi(self, prices, period=14):
        try:
            if prices is None or prices.empty or len(prices) < period + 1:
                return 50
            delta = prices.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            return rsi.iloc[-1] if not pd.isna(rsi.iloc[-1]) else 50
        except:
            return 50

    def _calculate_macd(self, prices):
        try:
            if prices is None or prices.empty or len(prices) < 26:
                return 0
            exp1 = prices.ewm(span=12).mean()
            exp2 = prices.ewm(span=26).mean()
            macd = exp1 - exp2
            return macd.iloc[-1]
        except:
            return 0

    def _calculate_atr(self, df, period=14):
        try:
            if df is None or df.empty:
                return 0.02
                
            high = df['high']
            low = df['low']
            close = df['close']
            
            tr1 = high - low
            tr2 = abs(high - close.shift())
            tr3 = abs(low - close.shift())
            
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            atr = tr.rolling(period).mean()
            return atr.iloc[-1] if not pd.isna(atr.iloc[-1]) else 0.02
        except:
            return 0.02

    def _calculate_williams_r(self, df, period=14):
        try:
            if df is None or df.empty:
                return -50
                
            high = df['high'].rolling(period).max()
            low = df['low'].rolling(period).min()
            close = df['close']
            
            williams_r = -100 * (high - close) / (high - low)
            return williams_r.iloc[-1] if not pd.isna(williams_r.iloc[-1]) else -50
        except:
            return -50

    def _calculate_cci(self, df, period=20):
        try:
            if df is None or df.empty:
                return 0
                
            typical_price = (df['high'] + df['low'] + df['close']) / 3
            sma = typical_price.rolling(period).mean()
            mad = typical_price.rolling(period).apply(lambda x: np.mean(np.abs(x - np.mean(x))))
            
            cci = (typical_price - sma) / (0.015 * mad)
            return cci.iloc[-1] if not pd.isna(cci.iloc[-1]) else 0
        except:
            return 0

    def _calculate_obv(self, df):
        try:
            if df is None or df.empty:
                return 0
                
            close = df['close']
            volume = df['volume']
            obv = (np.sign(close.diff()) * volume).fillna(0).cumsum()
            return obv.iloc[-1] if len(obv) > 0 else 0
        except:
            return 0

# =============================================
# ENHANCED TRADING BOT CORE - UNIVERSAL PROVIDER
# =============================================

class EnhancedTradingBot:
    """Enhanced trading bot dengan UNIVERSAL provider"""
    
    def __init__(self, config=None):
        # PERBAIKAN: Inisialisasi semua atribut di awal
        self.mode = None
        self.scanning_in_progress = False
        self.current_scan_task = None
        self.leverage = 1
        self.scheduler_thread = None
        self.stop_scheduler = False
        
        if config is None:
            config_path = "config/config.json"
            self.config_path = config_path
            self.load_config()
        else:
            self.config = config
            self.config_path = "config/config.json"
        
        # **PERBAIKAN UTAMA: Setup provider universal**
        self.data_provider = None
        self._setup_universal_provider()
        
        # **TAMBAHAN: Setup NonCryptoAssetsProvider**
        self.non_crypto_provider = None
        self._setup_non_crypto_provider()
        
        # Initialize components
        self.strategy = None
        self.notifier = SoundNotifier()
        self.db = DatabaseHandler()
        
        # ENHANCED COMPONENTS
        self.position_manager = EnhancedPositionManager(self.db)
        self.ml_ensemble = EnsembleMLModel()
        self.ml_bot = MLEnhancedBot()
        self.portfolio_optimizer = PortfolioOptimizer()
        self.backtest_engine = BacktestEngine()
        
        # Scalping configuration
        self.scalping_mode = False
        self.scalping_config = SCALPING_CONFIG.copy()
        
        # Configuration
        self.risk_per_trade = self.config.get("risk_per_trade", 0.01)
        self.max_drawdown_limit = self.config.get("max_drawdown_limit", 0.1)
        self.daily_loss_limit = self.config.get("daily_loss_limit", 0.05)
        
        # Trading mode
        self.trading_mode = self.config.get("trading_mode", "spot")
        
        # **PERBAIKAN: Hapus leverage dari config**
        if 'leverage' in self.config:
            self.config['leverage'] = 1
        
        # Monitoring
        self.daily_pnl = 0.0
        self.max_portfolio_value = 0.0
        self.current_drawdown = 0.0
        self.trading_enabled = True
        
        # ML enhancements
        self.ml_predictions_cache = {}
        self.last_ml_update = 0
        
        logger.info("✅ Enhanced TradingBot initialized dengan Universal Provider")

    # =============================================
    # HELPER METHODS FOR MINIMUM BARS BY MARKET TYPE
    # =============================================
    
    def _get_min_bars(self):
        """Get minimum bars required based on market type"""
        if self.mode in ['saham_id', 'forex', 'us_stocks']:
            return 30  # Untuk non-crypto, minimal 30 bar
        elif self.scalping_mode:
            return 50  # Scalping tetap 50 bar
        else:
            return 50  # Crypto default 50 bar

    def _get_min_bars_backtest(self):
        """Get minimum bars for backtest based on market type"""
        if self.mode in ['saham_id', 'forex', 'us_stocks']:
            return 40  # Untuk backtest non-crypto, minimal 40 bar
        else:
            return 100  # Crypto default 100 bar

    def _get_min_data_points_validation(self):
        """Get minimum data points for validation based on market type"""
        if self.mode in ['saham_id', 'forex', 'us_stocks']:
            return 10  # Untuk validasi non-crypto, minimal 10 bar
        else:
            return 20  # Crypto default 20 bar

    # =============================================
    # HELPER METHODS FOR MARKET CONSTRAINTS (SHORT FILTER)
    # =============================================
    
    def _is_short_allowed(self, market_type: str, symbol: str = None) -> bool:
        """
        Check apakah short selling diizinkan untuk market type tertentu.
        Rules:
        - Crypto: SHORT diizinkan untuk spot & futures (semua pair)
        - Saham Indonesia (IDX): SHORT TIDAK diizinkan (hanya long)
        - Forex: SHORT diizinkan untuk semua pair
        - US Stocks: SHORT diizinkan (tapi dengan regulasi tertentu)
        - Futures: SHORT diizinkan
        """
        if market_type == 'crypto':
            # Crypto: semua SHORT diizinkan
            return True
        elif market_type == 'saham_id':
            # Saham Indonesia: TIDAK boleh short (IDX tidak mengizinkan short selling reguler)
            return False
        elif market_type == 'forex':
            # Forex: SHORT diizinkan (trading pasangan mata uang)
            return True
        elif market_type == 'us_stocks':
            # US Stocks: SHORT diizinkan dengan regulasi tertentu
            return True
        else:
            # Default: tidak diizinkan
            return False
    
    def _get_market_min_score(self, market_type: str, action: str = "LONG") -> float:
        """
        Get minimum score yang berbeda berdasarkan market type dan action.
        Untuk non-crypto yang tidak mengizinkan SHORT, gunakan threshold yang lebih tinggi.
        """
        base_min_score = self.config.get("min_score", 2.0)
        
        if market_type == 'saham_id' and action == "SHORT":
            # Saham Indonesia: sangat tinggi untuk SHORT karena tidak diizinkan
            return 999.0  # Effectifely mencegah SHORT
        elif market_type == 'saham_id' and action == "LONG":
            # Saham Indonesia: sedikit lebih tinggi untuk LONG
            return max(base_min_score, 3.0)
        elif self.scalping_mode:
            return self.scalping_config.get("min_score", 4.0)
        else:
            return base_min_score

    # =============================================
    # PERBAIKAN UTAMA: POSITION MANAGEMENT METHODS
    # =============================================

    def get_active_positions(self, market_type=None):
        """Get positions from database with consistent format"""
        try:
            if hasattr(self, 'db') and self.db:
                # Get positions from database
                positions = self.db.get_active_positions(market_type or self.mode)
                
                # Format positions to be consistent with app expectations
                formatted_positions = []
                for pos in positions:
                    if isinstance(pos, dict):
                        # Standardize status
                        status = pos.get('status', '')
                        if status == 'active':
                            pos['status'] = 'open'
                        
                        # Ensure all required fields exist
                        required_fields = ['id', 'symbol', 'action', 'entry_price', 'current_price', 
                                         'tp1', 'tp2', 'tp3', 'sl', 'position_size']
                        
                        for field in required_fields:
                            if field not in pos:
                                # Set defaults
                                if field == 'id':
                                    pos[field] = f"db_{pos.get('id', int(time.time()))}"
                                elif field == 'current_price':
                                    pos[field] = pos.get('entry_price', 0)
                                elif field in ['tp1', 'tp2', 'tp3', 'sl']:
                                    # Calculate based on action
                                    entry = pos.get('entry_price', 0)
                                    action = pos.get('action', 'LONG')
                                    if action == 'LONG':
                                        pos['tp1'] = entry * 1.02
                                        pos['tp2'] = entry * 1.04
                                        pos['tp3'] = entry * 1.06
                                        pos['sl'] = entry * 0.98
                                    else:
                                        pos['tp1'] = entry * 0.98
                                        pos['tp2'] = entry * 0.96
                                        pos['tp3'] = entry * 0.94
                                        pos['sl'] = entry * 1.02
                                elif field == 'position_size':
                                    pos[field] = pos.get('position_size', 100)
                        
                        # Add source field
                        pos['source'] = 'database'
                        
                        formatted_positions.append(pos)
                
                return formatted_positions
            else:
                logger.warning("⚠️ No database connection in bot")
                return []
        except Exception as e:
            logger.error(f"❌ Error getting positions: {e}")
            return []

    def update_position_current_price(self, position_id, current_price):
        """Update position current price in database"""
        try:
            if hasattr(self, 'db') and self.db:
                # Check if method exists in database handler
                if hasattr(self.db, 'update_position_current_price'):
                    return self.db.update_position_current_price(position_id, current_price)
                elif hasattr(self.db, 'update_position'):
                    # Alternative method name
                    return self.db.update_position(position_id, {'current_price': current_price})
                else:
                    logger.warning(f"⚠️ No update method found in DatabaseHandler")
                    return False
            return False
        except Exception as e:
            logger.error(f"❌ Error updating position price: {e}")
            return False

    def close_position(self, position_id, close_price=None, close_reason="manual"):
        """Close position in database"""
        try:
            if hasattr(self, 'db') and self.db:
                if close_price is None:
                    # Get current price
                    positions = self.get_active_positions()
                    for pos in positions:
                        if str(pos.get('id')) == str(position_id):
                            close_price = pos.get('current_price', pos.get('entry_price', 0))
                            break
                
                return self.db.close_position(position_id, close_price, close_reason)
            return False
        except Exception as e:
            logger.error(f"❌ Error closing position: {e}")
            return False

    def validate_market_data(self, df: pd.DataFrame, symbol: str, debug_mode: bool = False) -> Tuple[bool, str]:
        """Validasi data market dengan logging lebih detail - PERBAIKAN UTAMA"""
        try:
            # PERBAIKAN: Ganti 'not df' menjadi 'df is None', dan gunakan df.empty hanya jika df bukan None
            if df is None or df.empty:
                return False, "Empty DataFrame"

            # Check 2: Column yang diperlukan ada
            required_columns = ['open', 'high', 'low', 'close']
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                return False, f"Missing columns: {missing_columns}"
            
            # Check 3: Minimal data points
            min_data_points = self._get_min_data_points_validation()
            if len(df) < min_data_points:
                return False, f"Insufficient data points: {len(df)} < {min_data_points}"
            
            # Check 4: Validasi harga positif
            price_columns = ['open', 'high', 'low', 'close']
            for col in price_columns:
                if (df[col] <= 0).any():
                    return False, f"Non-positive values in {col}"
            
            # Check 5: Harga high >= low
            if (df['high'] < df['low']).any():
                return False, "Invalid high/low values"
            
            # Check 6: Validasi data numerik
            for col in required_columns:
                if not pd.api.types.is_numeric_dtype(df[col]):
                    return False, f"Non-numeric values in {col}"
            
            # Check 7: Tidak ada NaN values di kolom penting
            for col in required_columns:
                if df[col].isna().any():
                    return False, f"NaN values in {col}"
            
            # Check 8: Harga dalam range yang wajar
            if 'close' in df.columns and len(df) > 0:
                avg_price = df['close'].mean()
                min_price = df['close'].min()
                max_price = df['close'].max()
                
                if debug_mode:
                    logger.debug(f"🔍 DEBUG {symbol}: Avg price = {avg_price:.8f}, Min = {min_price:.8f}, Max = {max_price:.8f}")
                
                # Deteksi dini harga ~100 (kemungkinan data sintetik)
                if np.any(np.isclose(df['close'].values, 100.0, atol=0.001)):
                    logger.error(f"🚨 CRITICAL: {symbol} has average price ~100 (likely synthetic/bad data)")
                    return False, f"Average price is ~100 (invalid data)"
            
            return True, "Data validation passed"
        
        except Exception as e:
            return False, f"Validation error: {str(e)}"

    def _setup_universal_provider(self):
        """Setup provider universal dengan SmartChain priority"""
        try:
            market_type = self.config.get("market_type", "crypto")
            
            logger.info(f"🔧 Setting up provider for {market_type} market...")
            
            # Priority order dari config
            provider_priority = self.config.get("provider_priority", "smart_chain")
            
            if provider_priority == "smart_chain" and SmartChainDataProvider is not None:
                # Coba SmartChainDataProvider terlebih dahulu
                try:
                    primary_mirror = self.config.get("primary_mirror", "binanceus")
                    self.data_provider = SmartChainDataProvider(
                        primary_mirror=primary_mirror,
                        market_type=market_type
                    )
                    logger.info(f"✅ Using SmartChainDataProvider with primary mirror: {primary_mirror}")
                    return True
                except Exception as e:
                    logger.warning(f"⚠️ SmartChainDataProvider failed: {e}")
            
            # Fallback ke UnifiedDataProvider
            if UnifiedDataProvider is not None:
                try:
                    exchange_id = self.config.get("exchange_crypto", "binance")
                    self.data_provider = UnifiedDataProvider(
                        exchange_id=exchange_id,
                        api_key='',
                        secret=''
                    )
                    logger.info(f"✅ Using UnifiedDataProvider with exchange: {exchange_id}")
                    return True
                except Exception as e:
                    logger.warning(f"⚠️ UnifiedDataProvider failed: {e}")
            
            # Fallback ke EnhancedCCXTDataProvider untuk crypto
            if market_type == 'crypto' and EnhancedCCXTDataProvider is not None:
                try:
                    exchange_id = self.config.get("exchange_crypto", "binance")
                    self.data_provider = EnhancedCCXTDataProvider(
                        exchange_id=exchange_id,
                        api_key='',
                        secret=''
                    )
                    logger.info(f"✅ Using EnhancedCCXTDataProvider: {exchange_id}")
                    return True
                except Exception as e:
                    logger.warning(f"⚠️ EnhancedCCXTDataProvider failed: {e}")
            
            # Ultimate fallback: YFinance
            if EnhancedYFinanceDataProvider is not None:
                self.data_provider = EnhancedYFinanceDataProvider()
                logger.info(f"✅ Using EnhancedYFinanceDataProvider for {market_type}")
                return True
            
            # Dummy fallback
            logger.error("❌ All providers failed, using dummy provider")
            class DummyDataProvider:
                def __init__(self, *args, **kwargs):
                    self.market_type = kwargs.get('market_type', 'crypto')
                    self.trading_mode = kwargs.get('trading_mode', 'spot')
                    self.active_exchange = 'dummy'
                
                def get_popular_assets(self, limit=100, asset_type='spot'):
                    return [{'symbol': 'BTC/USDT', 'name': 'Bitcoin'}]
                
                def get_ohlcv(self, symbol, timeframe, limit):
                    dates = pd.date_range(end=datetime.now(), periods=limit, freq='1H')
                    df = pd.DataFrame({
                        'open': np.random.randn(limit) * 100 + 50000,
                        'high': np.random.randn(limit) * 200 + 51000,
                        'low': np.random.randn(limit) * 200 + 49000,
                        'close': np.random.randn(limit) * 100 + 50000,
                        'volume': np.random.rand(limit) * 1000
                    }, index=dates)
                    return df
                
                def get_ticker(self, symbol):
                    return {'last': 50000, 'bid': 49900, 'ask': 50100}
                
                def search_assets(self, query, limit):
                    return [{'symbol': 'BTC/USDT', 'name': 'Bitcoin'}]
            
            self.data_provider = DummyDataProvider()
            logger.warning("⚠️ Using dummy data provider")
            return False
            
        except Exception as e:
            logger.error(f"❌ Failed to setup universal provider: {e}")
            return False

    def _setup_non_crypto_provider(self):
        """Setup NonCryptoAssetsProvider untuk aset non-crypto"""
        try:
            if NonCryptoAssetsProvider is not None:
                self.non_crypto_provider = NonCryptoAssetsProvider()
                logger.info("✅ NonCryptoAssetsProvider initialized")
                return True
            else:
                logger.warning("⚠️ NonCryptoAssetsProvider not available")
                self.non_crypto_provider = None
                return False
        except Exception as e:
            logger.error(f"❌ Failed to setup NonCryptoAssetsProvider: {e}")
            self.non_crypto_provider = None
            return False

    def load_config(self):
        """Load configuration dengan error handling"""
        try:
            os.makedirs("config", exist_ok=True)
            if os.path.exists(self.config_path):
                with open(self.config_path, "r") as f:
                    self.config = json.load(f)
            else:
                self.config = self._get_default_config()
                self.save_config()
                
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            self.config = self._get_default_config()
    
    def _get_default_config(self):
        """Get default configuration - DITINGKATKAN UNTUK 500+ ASET"""
        return {
            "timeframe": "1h",
            "atr_multiplier": 1.0,
            "entry_range_pct": 0.02,
            "exchange_crypto": "binance",
            "analysis_coins_limit": 500,  # PERBAIKAN: Naikkan dari 300 ke 500
            "ohlcv_limit": 200,
            "min_score": 2,
            "max_signals": 25,
            "update_interval": 30,
            "scan_delay": 0.1,
            "market_type": "crypto",
            "risk_per_trade": 0.01,
            "max_drawdown_limit": 0.1,
            "daily_loss_limit": 0.05,
            "enable_ml": True,
            "enable_trailing_stop": True,
            "partial_tp_enabled": True,
            "trading_mode": "spot",
            "default_exchange": "binance",
            "leverage": 1,
            # Tambahan untuk SmartChainDataProvider
            "provider_priority": "smart_chain",
            "primary_mirror": "binanceus"
        }
    
    def save_config(self):
        """Save configuration"""
        try:
            os.makedirs("config", exist_ok=True)
            with open(self.config_path, "w") as f:
                json.dump(self.config, f, indent=4)
        except Exception as e:
            logger.error(f"Error saving config: {e}")

    def _create_spot_strategy(self):
        """Create spot strategy"""
        return TechnicalAnalysisStrategy(
            market_type=self.mode,
            trading_type="spot",
            atr_multiplier=self.config.get("atr_multiplier", 1.0),
            entry_range_pct=self.config.get("entry_range_pct", 0.02),
        )
    
    def _create_futures_strategy(self):
        """Create futures strategy"""
        return TechnicalAnalysisStrategy(
            market_type=self.mode,
            trading_type="futures",
            atr_multiplier=self.config.get("atr_multiplier", 1.0),
            entry_range_pct=self.config.get("entry_range_pct", 0.02),
        )
    
    def _create_scalping_strategy(self):
        """Create scalping strategy"""
        return ScalpingStrategy(
            market_type=self.mode,
            trading_type="spot",
            leverage=1
        )

    def get_popular_assets(self, limit=500):
        """Get popular assets berdasarkan market mode - DITINGKATKAN UNTUK 500+ ASET"""
        if not self.data_provider:
            logger.warning("No data provider, returning empty list")
            return []
        
        try:
            logger.info(f"🔄 Getting {limit} popular assets for {self.mode} market...")
            
            # **PERBAIKAN: Gunakan NonCryptoAssetsProvider untuk non-crypto markets**
            if self.mode in ['saham_id', 'forex', 'us_stocks'] and self.non_crypto_provider:
                return self._get_non_crypto_assets_from_provider(limit)
            
            # Get assets dari provider untuk crypto
            assets = []
            if hasattr(self.data_provider, 'get_popular_assets'):
                assets = self.data_provider.get_popular_assets(limit=limit * 2)  # Get more untuk difilter
            else:
                logger.warning("Provider tidak memiliki get_popular_assets method")
                return []
            
            if not assets:
                return []
            
            # Filter dan proses berdasarkan mode
            processed_assets = []
            
            for asset in assets:
                try:
                    # Handle format asset
                    if isinstance(asset, dict):
                        symbol = asset.get('symbol', '')
                        name = asset.get('name', symbol)
                    else:
                        symbol = str(asset)
                        name = symbol
                    
                    if not symbol:
                        continue
                    
                    # Auto-detect trading type
                    trading_type, formatted_symbol = auto_detect_trading_type(symbol)
                    
                    # Filter berdasarkan market mode
                    if self.mode == "crypto":
                        # Crypto: hanya terima USDT pairs dan futures
                        if any(x in symbol.upper() for x in ['/USDT', ':USDT', 'USDT']):
                            processed_assets.append({
                                'symbol': symbol,
                                'name': name,
                                'detected_type': trading_type,
                                'formatted_symbol': formatted_symbol
                            })
                    
                    elif self.mode == "forex":
                        # Forex: hanya currency pairs
                        forex_markers = ['/USD', '/EUR', '/JPY', '/GBP', '/CHF', '/CAD', '/AUD', '/NZD']
                        if any(x in symbol.upper() for x in forex_markers):
                            processed_assets.append({
                                'symbol': symbol,
                                'name': name,
                                'detected_type': "spot",
                                'formatted_symbol': formatted_symbol
                            })
                    
                    elif self.mode == "saham_id":
                        # Saham Indonesia: harus ada .JK
                        if '.JK' in symbol.upper():
                            processed_assets.append({
                                'symbol': symbol,
                                'name': name,
                                'detected_type': "spot",
                                'formatted_symbol': formatted_symbol
                            })
                    
                    elif self.mode == "us_stocks":
                        # US Stocks: biasanya ticker singkat tanpa /
                        if '/' not in symbol and ':' not in symbol:
                            processed_assets.append({
                                'symbol': symbol,
                                'name': name,
                                'detected_type': "spot",
                                'formatted_symbol': formatted_symbol
                            })
                    
                    else:
                        # Untuk mode lain, terima semua
                        processed_assets.append({
                            'symbol': symbol,
                            'name': name,
                            'detected_type': trading_type,
                            'formatted_symbol': formatted_symbol
                        })
                    
                except Exception as e:
                    logger.debug(f"Skipping asset {asset}: {e}")
                    continue
            
            # Acak urutan aset untuk menghindari bias
            random.shuffle(processed_assets)
            
            # Limit hasil
            result = processed_assets[:limit]
            logger.info(f"✅ Found {len(result)} assets for {self.mode} market")
            return result
            
        except Exception as e:
            logger.error(f"Error getting popular assets: {e}")
            return []
    
    def _get_non_crypto_assets_from_provider(self, limit=500):
        """Get non-crypto assets dari NonCryptoAssetsProvider - OPTIMIZED UNTUK SAHAM"""
        try:
            if not self.non_crypto_provider:
                logger.warning("⚠️ NonCryptoAssetsProvider not available")
                return self._get_non_crypto_assets_fallback()
            
            category_map = {
                'saham_id': 'indonesia_stocks',
                'forex': 'forex', 
                'us_stocks': 'us_stocks'
            }
            
            category = category_map.get(self.mode)
            if not category:
                logger.error(f"Invalid mode for NonCryptoAssetsProvider: {self.mode}")
                return self._get_non_crypto_assets_fallback()
            
            # **PERBAIKAN KHUSUS UNTUK SAHAM INDONESIA: SCAN SEMUA!**
            if self.mode == 'saham_id':
                logger.info("📊 MODE SAHAM INDONESIA: Menggunakan FULL LIST (semua saham)")
                
                # **STRATEGI SMART:** 
                # 1. Ambil dari provider jika ada method get_all_assets
                # 2. Jika tidak, gunakan fallback lengkap
                # 3. Untuk saham, TIDAK PERLU filter min_volume/min_volatility
                
                if hasattr(self.non_crypto_provider, 'get_all_assets'):
                    symbols = self.non_crypto_provider.get_all_assets(category=category)
                    logger.info(f"✅ Menggunakan get_all_assets() untuk {self.mode} - {len(symbols)} saham")
                else:
                    # Untuk saham Indonesia, skip volume filter, ambil semua
                    symbols = self.non_crypto_provider.get_assets(
                        category=category, 
                        limit=1000,  # Request besar untuk cover semua
                        force_update=True
                    )
                    logger.info(f"📊 Menggunakan get_assets() untuk {self.mode} - {len(symbols)} saham")
                
                # Jika masih sedikit, gunakan fallback lengkap
                if not symbols or len(symbols) < 50:
                    logger.info(f"⚠️ Provider hanya memberikan {len(symbols)} saham, menggunakan fallback lengkap")
                    fallback_assets = self._get_non_crypto_assets_fallback()
                    return fallback_assets  # Return semua dari fallback
                
            else:
                # Untuk forex & US stocks, gunakan strategi normal dengan filter
                requested_limit = min(600, limit * 2)
                min_volume = 1_000_000  
                min_volatility = 0.025
                
                if hasattr(self.non_crypto_provider, 'get_active_assets'):
                    symbols = self.non_crypto_provider.get_active_assets(
                        category=category,
                        min_volume=min_volume,
                        min_volatility=min_volatility,
                        limit=requested_limit
                    )
                    logger.info(f"📊 Menggunakan get_active_assets() untuk {self.mode} - {len(symbols)} aset aktif")
                else:
                    symbols = self.non_crypto_provider.get_assets(
                        category=category, 
                        limit=requested_limit, 
                        force_update=True
                    )
                    logger.warning(f"⚠️ Menggunakan get_assets() (fallback) untuk {self.mode}")
            
            logger.info(f"📊 Provider returned {len(symbols)} symbols for {self.mode}")
            
            # Format hasil
            processed_assets = []
            
            for symbol in symbols:
                detected_type = "spot"
                
                if self.mode == 'saham_id':
                    if not symbol.endswith('.JK'):
                        formatted_symbol = f"{symbol}.JK"
                    else:
                        formatted_symbol = symbol
                        
                    # Ambil nama saham dari yfinance atau gunakan symbol
                    try:
                        import yfinance as yf
                        ticker = yf.Ticker(formatted_symbol)
                        info = ticker.info
                        if 'shortName' in info:
                            name = info['shortName']
                        elif 'longName' in info:
                            name = info['longName']
                        else:
                            name = symbol.replace('.JK', '')
                    except:
                        name = symbol.replace('.JK', '')
                        
                elif self.mode == 'forex':
                    if '=X' not in symbol:
                        formatted_symbol = f"{symbol}=X"
                    else:
                        formatted_symbol = symbol
                    name = symbol.replace('=X', '')
                    
                elif self.mode == 'us_stocks':
                    formatted_symbol = symbol.split('.')[0] if '.' in symbol else symbol
                    
                    try:
                        import yfinance as yf
                        ticker = yf.Ticker(formatted_symbol)
                        info = ticker.info
                        if 'shortName' in info:
                            name = info['shortName']
                        elif 'longName' in info:
                            name = info['longName']
                        else:
                            name = symbol
                    except:
                        name = symbol
                else:
                    formatted_symbol = symbol
                    name = symbol
                
                processed_assets.append({
                    'symbol': symbol,
                    'name': name,
                    'detected_type': detected_type,
                    'formatted_symbol': formatted_symbol,
                    'source': 'non_crypto_provider'
                })
            
            logger.info(f"✅ Processed {len(processed_assets)} assets from NonCryptoAssetsProvider")
            return processed_assets[:2000]  # Return banyak untuk scanning lengkap
            
        except Exception as e:
            logger.error(f"Error getting non-crypto assets: {e}")
            return self._get_non_crypto_assets_fallback()
    
    def _get_non_crypto_assets_fallback(self):
        """Fallback method untuk mendapatkan non-crypto assets jika provider gagal"""
        logger.info(f"🔄 Using fallback method for {self.mode} assets")
        
        fallback_assets = []
        
        if self.mode == 'saham_id':
            # Saham Indonesia fallback - LIST LENGKAP TANPA LIMIT (DIPERBARUI)
            fallback_symbols = [
                'AADI.JK', 'ACES.JK', 'ADMR.JK', 'ADRO.JK', 'AKRA.JK', 'AMMN.JK', 'ANTM.JK', 'ASII.JK', 
                'AVIA.JK', 'BBCA.JK', 'BBNI.JK', 'BBRI.JK', 'BMRI.JK', 'BRMS.JK', 'BRPT.JK', 'BUKA.JK', 
                'BUMI.JK', 'BYAN.JK', 'CPIN.JK', 'CTRA.JK', 'DSSA.JK', 'EMTK.JK', 'ESSA.JK', 'EXCL.JK', 
                'GOTO.JK', 'HEAL.JK', 'ICBP.JK', 'INCO.JK', 'INDF.JK', 'INKP.JK', 'INTP.JK', 'ITMG.JK', 
                'JPFA.JK', 'JSMR.JK', 'KLBF.JK', 'MAPA.JK', 'MDKA.JK', 'MEDC.JK', 'MTEL.JK', 'NCKL.JK', 
                'PGAS.JK', 'PTBA.JK', 'PGEO.JK', 'SCMA.JK', 'SIDO.JK', 'SMGR.JK', 'SRTG.JK', 'TBIG.JK', 
                'TINS.JK', 'TLKM.JK', 'TOWR.JK', 'TPIA.JK', 'UNTR.JK', 'UNVR.JK',
                
                # Tambahan dari IDX80 dan top performers 2025-2026
                'AGII.JK', 'AGRO.JK', 'AKSI.JK', 'ALTO.JK', 'AMRT.JK', 'APLN.JK', 'ARTO.JK', 'ASRI.JK', 
                'ASSA.JK', 'BACA.JK', 'BALI.JK', 'BANK.JK', 'BBHI.JK', 'BBKP.JK', 'BBTN.JK', 'BCAP.JK', 
                'BFIN.JK', 'BINA.JK', 'BJBR.JK', 'BJTM.JK', 'BKSW.JK', 'BMAS.JK', 'BNGA.JK', 'BNII.JK', 
                'BRIS.JK', 'BSDE.JK', 'BSSR.JK', 'BTPS.JK', 'BVIC.JK', 'CASA.JK', 'CMNP.JK', 'CMRY.JK', 
                'CSAP.JK', 'CSMI.JK', 'DMAS.JK', 'DMND.JK', 'DOID.JK', 'DSNG.JK', 'DUTI.JK', 'ELSA.JK', 
                'ENRG.JK', 'FAST.JK', 'FREN.JK', 'GEMS.JK', 'GIAA.JK', 'GOOD.JK', 'HEXA.JK', 'HOKI.JK', 
                'HRTA.JK', 'HRUM.JK', 'IBFN.JK', 'IFSH.JK', 'IMAS.JK', 'IMJS.JK', 'IMPC.JK', 'INAF.JK',
                'INAI.JK', 'INCF.JK', 'INDO.JK', 'INDR.JK', 'INDX.JK', 'INDY.JK', 'INPC.JK', 'INPP.JK', 
                'INPS.JK', 'INRU.JK', 'IPCC.JK', 'IPCM.JK', 'IPOL.JK', 'ISAT.JK', 'ISSP.JK', 'ITIC.JK', 
                'JARR.JK', 'JAST.JK', 'JECC.JK', 'JIHD.JK', 'JKSW.JK', 'JMAS.JK', 'JRPT.JK', 'KAEF.JK', 
                'KARW.JK', 'KBAG.JK', 'KBLI.JK', 'KBLM.JK', 'KBLV.JK', 'KDSI.JK', 'KEEN.JK', 'KIAS.JK', 
                'KIJA.JK', 'KKES.JK', 'KMDS.JK', 'KMTR.JK', 'KOBX.JK', 'KOPI.JK', 'KPAS.JK', 'KPPI.JK', 
                'KRAS.JK', 'KREN.JK', 'LAND.JK', 'LAPD.JK', 'LCKM.JK', 'LEAD.JK', 'LIFE.JK', 'LINK.JK', 
                'LION.JK', 'LMAX.JK', 'LMSH.JK', 'LPGI.JK', 'LPIN.JK', 'LPLI.JK', 'LPPF.JK', 'LPPS.JK', 
                'LRNA.JK', 'LTLS.JK', 'LUCK.JK', 'MAIN.JK', 'MAMI.JK', 'MAPB.JK', 'MAPI.JK', 'MARI.JK', 
                'MARK.JK', 'MASA.JK', 'MAYA.JK', 'MBSS.JK', 'MBTO.JK', 'MCAS.JK', 'MCOR.JK', 'MDIA.JK', 
                'MDLN.JK', 'MDRN.JK', 'MEGA.JK', 'META.JK', 'MGNA.JK', 'MGRO.JK', 'MICE.JK', 'MIKA.JK', 
                'MINA.JK', 'MITI.JK', 'MKPI.JK', 'MKTR.JK', 'MLBI.JK', 'MLIA.JK', 'MLPL.JK', 'MLPT.JK', 
                'MLTX.JK', 'MNCN.JK', 'MPMX.JK', 'MPPA.JK', 'MRAT.JK', 'MSIN.JK', 'MSKY.JK', 'MTDL.JK', 
                'MTFN.JK', 'MTLA.JK', 'MTMH.JK', 'MTPS.JK', 'MTSM.JK', 'MTWI.JK', 'MYOH.JK', 'MYOR.JK', 
                'MYTX.JK', 'NASA.JK', 'NATO.JK', 'NETV.JK', 'NFCX.JK', 'NIKL.JK', 'NRCA.JK', 'NSSS.JK', 
                'NTBK.JK', 'NUSA.JK', 'NZIA.JK', 'OBMD.JK', 'OILS.JK', 'OKAS.JK', 'OMRE.JK', 'OPMS.JK', 
                'PACK.JK', 'PADI.JK', 'PALM.JK', 'PAMG.JK', 'PANI.JK', 'PBID.JK', 'PBSA.JK', 'PCAR.JK', 
                'PDAI.JK', 'PDES.JK', 'PEGE.JK', 'PEHA.JK', 'PGUN.JK', 'PICO.JK', 'PKPK.JK', 'PLAS.JK', 
                'PLIN.JK', 'PMJS.JK', 'PMMP.JK', 'PNLF.JK', 'POLA.JK', 'POLI.JK', 'POLU.JK', 'POOL.JK', 
                'PORT.JK', 'POWR.JK', 'PPGL.JK', 'PPRE.JK', 'PRDA.JK', 'PRIM.JK', 'PSAB.JK', 'PSDN.JK', 
                'PSGO.JK', 'PSKT.JK', 'PTDU.JK', 'PTIS.JK', 'PTRO.JK', 'PTSN.JK', 'PUDP.JK', 'PWON.JK', 
                'PYFA.JK', 'PZZA.JK', 'RAJA.JK', 'RALS.JK', 'RANC.JK', 'RBMS.JK', 'RDTX.JK', 'REAL.JK', 
                'RELI.JK', 'RICY.JK', 'RIGS.JK', 'RISE.JK', 'RMKE.JK', 'RMKO.JK', 'ROCK.JK', 'RODA.JK', 
                'ROTI.JK', 'RUIS.JK', 'SAFE.JK', 'SAGE.JK', 'SAMA.JK', 'SAMF.JK', 'SAPX.JK', 'SATU.JK', 
                'SBAT.JK', 'SBMA.JK', 'SBSN.JK', 'SCBD.JK', 'SCMA.JK', 'SCNP.JK', 'SCPI.JK', 'SDMU.JK', 
                'SDPC.JK', 'SDRA.JK', 'SFAN.JK', 'SGER.JK', 'SGRO.JK', 'SHID.JK', 'SHIP.JK', 'SICO.JK', 
                'SILO.JK', 'SINI.JK', 'SIPD.JK', 'SKBM.JK', 'SKLT.JK', 'SKRN.JK', 'SLIS.JK', 'SMAR.JK', 
                'SMBR.JK', 'SMDR.JK', 'SMGA.JK', 'SMKL.JK', 'SMKM.JK', 'SMMA.JK', 'SMMT.JK', 'SMRU.JK', 
                'SMSM.JK', 'SNLK.JK', 'SOCI.JK', 'SOFA.JK', 'SOHO.JK', 'SONA.JK', 'SOSS.JK', 'SOTS.JK', 
                'SPMA.JK', 'SPTO.JK', 'SQMI.JK', 'SRAJ.JK', 'SRSN.JK', 'STAA.JK', 'STAR.JK', 'STRK.JK', 
                'STTP.JK', 'SUGI.JK', 'SULI.JK', 'SUPR.JK', 'SURE.JK', 'SWAT.JK', 'TALF.JK', 'TAMU.JK', 
                'TARA.JK', 'TAXI.JK', 'TBMS.JK', 'TCID.JK', 'TCPI.JK', 'TDPM.JK', 'TECH.JK', 'TEBE.JK', 
                'TELE.JK', 'TFAS.JK', 'TFCO.JK', 'TGKA.JK', 'TIFA.JK', 'TIRT.JK', 'TJWI.JK', 'TKIM.JK', 
                'TMAS.JK', 'TMPO.JK', 'TNCA.JK', 'TOPS.JK', 'TOTL.JK', 'TPMA.JK', 'TRGU.JK', 'TRIM.JK', 
                'TRIN.JK', 'TRIS.JK', 'TRJA.JK', 'TRST.JK', 'TRUE.JK', 'TRUK.JK', 'TRUS.JK', 'TUGU.JK', 
                'UANG.JK', 'UCID.JK', 'UFOE.JK', 'UNIC.JK', 'UNIQ.JK', 'UNSP.JK', 'UVCR.JK', 'VAST.JK', 
                'VICI.JK', 'VICO.JK', 'VINS.JK', 'VIVA.JK', 'VKTR.JK', 'VOKS.JK', 'VTNY.JK', 'WAPO.JK', 
                'WEGE.JK', 'WEHA.JK', 'WGSH.JK', 'WINE.JK', 'WINS.JK', 'WMPP.JK', 'WMUU.JK', 'WOMF.JK', 
                'WOOD.JK', 'WOWS.JK', 'YELO.JK', 'YPAS.JK', 'ZATA.JK', 'ZONE.JK', 'ZBRA.JK', 'ZYRX.JK'
            ]
            
            # Exclude delisted/suspended
            delisted_suspended = [
                'ALMI.JK', 'ARMY.JK', 'ARTI.JK', 'BEBS.JK', 'BIKA.JK', 'CNTX.JK', 'ENVY.JK', 'FKON.JK', 
                'HDTX.JK', 'HITS.JK', 'KPAL.JK', 'MAGP.JK', 'RSGK.JK', 'SKYB.JK', 'SRIL.JK', 'TGRA.JK', 
                'WICO.JK', 'CHEK.JK', 'PMUI.JK', 'COIN.JK', 'CDIA.JK', 'NIPS.JK', 'PRAS.JK', 'POSA.JK',
                'WIKA.JK', 'WSKT.JK', 'INAF.JK'
            ]
            fallback_symbols = [s for s in fallback_symbols if s not in delisted_suspended]
            
        elif self.mode == 'forex':
            # Forex fallback - LIST LENGKAP TANPA LIMIT
            fallback_symbols = [
                'EURUSD=X', 'USDJPY=X', 'GBPUSD=X', 'AUDUSD=X', 'USDCAD=X',
                'USDCHF=X', 'NZDUSD=X', 'EURGBP=X', 'EURJPY=X', 'GBPJPY=X',
                'AUDJPY=X', 'EURCHF=X', 'GBPCHF=X', 'AUDNZD=X', 'NZDJPY=X',
                'USDSGD=X', 'USDHKD=X', 'USDCNY=X', 'USDKRW=X', 'USDMYR=X',
                'EURUSD', 'USDJPY', 'GBPUSD', 'AUDUSD', 'USDCAD',
                'USDCHF', 'NZDUSD', 'EURGBP', 'EURJPY', 'GBPJPY',
                'AUDJPY', 'EURCHF', 'GBPCHF', 'AUDNZD', 'NZDJPY',
                'USDSGD', 'USDHKD', 'USDCNY', 'USDKRW', 'USDMYR',
                'EURCAD', 'EURAUD', 'EURCHF', 'EURNZD', 'GBPAUD',
                'GBPCAD', 'GBPCHF', 'GBPNZD', 'AUDCAD', 'AUDCHF',
                'AUDNZD', 'CADCHF', 'CADJPY', 'CHFJPY', 'NZDCHF',
                'NZDCAD', 'NZDJPY', 'SGDJPY', 'HKDJPY', 'CNYJPY',
                'EURSEK', 'EURNOK', 'EURDKK', 'EURPLN', 'EURHUF',
                'EURCZK', 'EURRON', 'EURTRY', 'USDRUB', 'USDINR',
                'USDBRL', 'USDMXN', 'USDZAR', 'USDTWD', 'USDTHB',
                'USDPHP', 'USDIDR', 'USDVND', 'USDBDT', 'USDPKR'
            ]
            
        elif self.mode == 'us_stocks':
            # US Stocks fallback - LIST LENGKAP TANPA LIMIT
            fallback_symbols = [
                'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'TSLA', 'NVDA',
                'BRK-B', 'JPM', 'V', 'JNJ', 'WMT', 'PG', 'MA', 'UNH',
                'HD', 'BAC', 'DIS', 'ADBE', 'NFLX', 'CMCSA', 'PEP',
                'CSCO', 'INTC', 'T', 'PFE', 'XOM', 'CVX', 'ABT', 'KO',
                'AVGO', 'MRK', 'PEP', 'COST', 'ABBV', 'TMO', 'DHR',
                'MCD', 'NKE', 'ACN', 'ADP', 'BMY', 'LLY', 'LIN', 'UPS',
                'RTX', 'UNP', 'PM', 'TXN', 'SCHW', 'CVS', 'LOW', 'DE',
                'CAT', 'MDT', 'AMGN', 'GILD', 'CI', 'BKNG', 'PLD',
                'SPGI', 'AXP', 'INTU', 'ISRG', 'SBUX', 'GS', 'BLK',
                'MMM', 'BA', 'MO', 'IBM', 'GE', 'F', 'GM', 'AMD',
                'QCOM', 'TXN', 'ADI', 'MU', 'INTC', 'AMAT', 'LRCX',
                'KLAC', 'NXPI', 'SWKS', 'QRVO', 'MRVL', 'ANET', 'CDNS',
                'SNPS', 'ADSK', 'TTWO', 'EA', 'ATVI', 'TTD', 'ROKU',
                'SPOT', 'PYPL', 'SQ', 'SHOP', 'MELI', 'SE', 'NET',
                'CRWD', 'ZS', 'OKTA', 'PANW', 'FTNT', 'CYBR', 'PLTR',
                'SNOW', 'DDOG', 'MDB', 'TWLO', 'TEAM', 'ZS', 'ESTC',
                'AI', 'PATH', 'ASAN', 'SMAR', 'BILL', 'COUP', 'DOCU',
                'ZM', 'FSLY', 'PINS', 'SNAP', 'TWTR', 'FB', 'UBER',
                'LYFT', 'DASH', 'ABNB', 'EXPE', 'BKNG', 'TRIP', 'RCL',
                'NCLH', 'CCL', 'MAR', 'HLT', 'HYATT', 'AAL', 'DAL',
                'UAL', 'LUV', 'ALK', 'JBLU', 'SAVE', 'FDX', 'UPS',
                'EXPD', 'CHRW', 'JBHT', 'LSTR', 'ODFL', 'XPO', 'YRCW',
                'ZTO', 'JD', 'BABA', 'PDD', 'TCEHY', 'BIDU', 'NTES',
                'BILI', 'IQ', 'TME', 'YY', 'DOYU', 'HUYA', 'WB', 'MOMO',
                'ADP', 'ADSK', 'AEP', 'AIG', 'ALL', 'AMAT', 'AMD', 'AMGN',
                'AMT', 'ANET', 'ANTM', 'APA', 'APD', 'APH', 'ATVI', 'AVB',
                'AVGO', 'AVY', 'AXP', 'AZO', 'BA', 'BAC', 'BAX', 'BBY',
                'BDX', 'BEN', 'BIIB', 'BK', 'BKNG', 'BLK', 'BLL', 'BMY',
                'BR', 'BRK-B', 'BSX', 'BWA', 'BXP', 'C', 'CAG', 'CAH',
                'CAT', 'CB', 'CBOE', 'CBRE', 'CCI', 'CCL', 'CDNS', 'CDW',
                'CE', 'CERN', 'CF', 'CFG', 'CHD', 'CHRW', 'CHTR', 'CI',
                'CINF', 'CL', 'CLX', 'CMA', 'CMCSA', 'CME', 'CMG', 'CMI',
                'CMS', 'CNC', 'CNP', 'COF', 'COG', 'COO', 'COP', 'COST',
                'CPB', 'CPRT', 'CRM', 'CSCO', 'CSX', 'CTAS', 'CTSH', 'CTVA',
                'CTXS', 'CVS', 'CVX', 'D', 'DAL', 'DD', 'DE', 'DFS', 'DG',
                'DGX', 'DHI', 'DHR', 'DIS', 'DISCA', 'DISCK', 'DISH', 'DLR',
                'DLTR', 'DOV', 'DOW', 'DRE', 'DRI', 'DTE', 'DUK', 'DVA',
                'DVN', 'DXC', 'DXCM', 'EA', 'EBAY', 'ECL', 'ED', 'EFX',
                'EIX', 'EL', 'EMN', 'EMR', 'EOG', 'EQIX', 'EQR', 'ES',
                'ESS', 'ETN', 'ETR', 'EVRG', 'EW', 'EXC', 'EXPD', 'EXPE',
                'EXR', 'F', 'FANG', 'FAST', 'FB', 'FBHS', 'FCX', 'FDX',
                'FE', 'FFIV', 'FIS', 'FISV', 'FITB', 'FLT', 'FMC', 'FOX',
                'FOXA', 'FRC', 'FRT', 'FTI', 'FTNT', 'FTV', 'GD', 'GE',
                'GILD', 'GIS', 'GL', 'GLW', 'GM', 'GOOG', 'GOOGL', 'GPC',
                'GPN', 'GPS', 'GRMN', 'GS', 'GWW', 'HAL', 'HAS', 'HBAN',
                'HBI', 'HCA', 'HD', 'HES', 'HIG', 'HLT', 'HOLX', 'HON',
                'HPE', 'HPQ', 'HRB', 'HRL', 'HSIC', 'HST', 'HSY', 'HUM',
                'HWM', 'IBM', 'ICE', 'IDXX', 'IEX', 'IFF', 'ILMN', 'INCY',
                'INFO', 'INTC', 'INTU', 'IP', 'IPG', 'IQV', 'IR', 'IRM',
                'ISRG', 'IT', 'ITW', 'IVZ', 'J', 'JBHT', 'JCI', 'JKHY',
                'JNJ', 'JNPR', 'JPM', 'K', 'KEY', 'KEYS', 'KHC', 'KIM',
                'KLAC', 'KMB', 'KMI', 'KMX', 'KO', 'KR', 'KSS', 'KSU',
                'L', 'LDOS', 'LEG', 'LEN', 'LH', 'LHX', 'LIN', 'LKQ',
                'LLY', 'LMT', 'LNC', 'LNT', 'LOW', 'LRCX', 'LUV', 'LVS',
                'LW', 'LYB', 'LYV', 'MA', 'MAA', 'MAR', 'MAS', 'MCD',
                'MCHP', 'MCK', 'MCO', 'MDLZ', 'MDT', 'MET', 'MGM', 'MHK',
                'MKC', 'MKTX', 'MLM', 'MMC', 'MMM', 'MNST', 'MO', 'MOS',
                'MPC', 'MPWR', 'MRK', 'MRO', 'MS', 'MSCI', 'MSFT', 'MSI',
                'MTB', 'MTD', 'MU', 'MXIM', 'NCLH', 'NDAQ', 'NEE', 'NEM',
                'NFLX', 'NI', 'NKE', 'NLOK', 'NLSN', 'NOC', 'NOV', 'NOW',
                'NRG', 'NSC', 'NTAP', 'NTRS', 'NUE', 'NVDA', 'NVR', 'NWL',
                'NWS', 'NWSA', 'O', 'ODFL', 'OKE', 'OMC', 'ORCL', 'ORLY',
                'OTIS', 'OXY', 'PAYC', 'PAYX', 'PBCT', 'PCAR', 'PEAK',
                'PEG', 'PEP', 'PFE', 'PFG', 'PG', 'PGR', 'PH', 'PHM',
                'PKG', 'PKI', 'PLD', 'PM', 'PNC', 'PNR', 'PNW', 'PPG',
                'PPL', 'PRU', 'PSA', 'PSX', 'PTC', 'PVH', 'PWR', 'PXD',
                'PYPL', 'QCOM', 'QRVO', 'RCL', 'RE', 'REG', 'REGN', 'RF',
                'RHI', 'RJF', 'RL', 'RMD', 'ROK', 'ROL', 'ROP', 'ROST',
                'RSG', 'RTX', 'SBAC', 'SBUX', 'SCHW', 'SEE', 'SHW', 'SIVB',
                'SJM', 'SLB', 'SLG', 'SNA', 'SNPS', 'SO', 'SPG', 'SPGI',
                'SRE', 'STE', 'STT', 'STX', 'STZ', 'SWK', 'SWKS', 'SYF',
                'SYK', 'SYY', 'T', 'TAP', 'TDG', 'TDY', 'TEL', 'TER',
                'TFC', 'TFX', 'TGT', 'TIF', 'TJX', 'TMO', 'TMUS', 'TPR',
                'TRIP', 'TROW', 'TRV', 'TSCO', 'TSLA', 'TSN', 'TT', 'TTWO',
                'TWTR', 'TXN', 'TXT', 'TYL', 'UA', 'UAA', 'UAL', 'UDR',
                'UHS', 'ULTA', 'UNH', 'UNP', 'UPS', 'URI', 'USB', 'V',
                'VFC', 'VIAC', 'VLO', 'VMC', 'VNO', 'VRSK', 'VRSN', 'VRTX',
                'VTR', 'VZ', 'WAB', 'WAT', 'WBA', 'WDC', 'WEC', 'WELL',
                'WFC', 'WHR', 'WLTW', 'WM', 'WMB', 'WMT', 'WRB', 'WRK',
                'WST', 'WU', 'WY', 'WYNN', 'XEL', 'XLNX', 'XOM', 'XRAY',
                'XYL', 'YUM', 'ZBH', 'ZBRA', 'ZION', 'ZTS'
            ]
        else:
            return []
        
        for symbol in fallback_symbols:
            fallback_assets.append({
                'symbol': symbol,
                'name': symbol,
                'detected_type': 'spot',
                'formatted_symbol': symbol,
                'source': 'fallback'
            })
        
        return fallback_assets  # TIDAK ADA LIMIT DI SINI JUGA

    def scan_potential_assets(self, limit=25, search_query: str = None):
        """Scan sederhana dengan provider universal - OPTIMIZED UNTUK SAHAM"""
        if self.scanning_in_progress:
            logger.warning("Scan already in progress")
            return []
        
        self.scanning_in_progress = True
        self.current_scan_task = threading.current_thread().ident
        
        try:
            # Validasi provider
            if not self.data_provider:
                logger.error("❌ No data provider available. Run set_mode() first!")
                self.scanning_in_progress = False
                return []
            
            # **STRATEGI BERBEDA UNTUK SAHAM vs CRYPTO**
            if self.mode == 'saham_id':
                # UNTUK SAHAM: ANALISIS SEMUA SAHAM (FULL COVERAGE)
                assets_limit = 1000  # Sangat besar untuk cover semua saham
                max_workers = 20     # Lebih banyak thread untuk handle volume besar
                scan_timeout = 45    # Timeout lebih lama untuk saham
                logger.info("🎯 MODE SAHAM INDONESIA: SCANNING SEMUA SAHAM (FULL COVERAGE)")
            else:
                # Untuk crypto/forex/stocks lain: strategi normal
                assets_limit = self.config.get("analysis_coins_limit", 500)
                max_workers = 10
                scan_timeout = 30
            
            logger.info(f"🔍 Scanning for {limit} signals (analyzing up to {assets_limit} assets)...")
            
            # Get assets menggunakan metode yang sudah diperbaiki
            assets = self.get_popular_assets(assets_limit)
            
            if not assets:
                logger.warning("❌ No assets available for scanning")
                self.scanning_in_progress = False
                return []
            
            logger.info(f"📊 Scanning {len(assets)} assets...")
            
            signals = []
            
            # **PERBAIKAN: Batasi jumlah assets jika terlalu banyak untuk testing**
            # Dalam production, bisa scan semua, tapi untuk testing kita batasi
            if len(assets) > 200 and self.mode == 'saham_id':
                logger.info(f"⚠️ Terlalu banyak assets ({len(assets)}), menggunakan 200 saham teratas untuk demo")
                assets_to_process = assets[:200]
            else:
                assets_to_process = assets
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                # Submit semua tasks
                future_to_asset = {
                    executor.submit(self._analyze_single_asset_enhanced, asset, i, len(assets_to_process)): asset 
                    for i, asset in enumerate(assets_to_process)
                }
                
                # Kumpulkan hasil
                for future in concurrent.futures.as_completed(future_to_asset):
                    asset = future_to_asset[future]
                    try:
                        signal_data = future.result(timeout=scan_timeout)
                        if signal_data:
                            signals.append(signal_data)
                            
                            # Untuk saham, kumpulkan lebih banyak sinyal
                            max_signals = 50 if self.mode == 'saham_id' else self.scalping_config.get("max_signals", 10) if self.scalping_mode else limit
                            if len(signals) >= max_signals:
                                logger.info(f"✅ Sudah mencapai {max_signals} sinyal, menghentikan scan...")
                                break
                                
                    except Exception as e:
                        logger.error(f"❌ Error processing asset {asset.get('symbol', 'unknown')}: {e}")
                        continue
            
            logger.info(f"🎯 Scan completed: {len(signals)} signals found")
            
            # Sort signals by score absolute value
            if signals:
                signals.sort(key=lambda x: abs(x['score']), reverse=True)
                
                # **UNTUK SAHAM: Tampilkan lebih banyak hasil**
                top_n = 20 if self.mode == 'saham_id' else 10
                logger.info(f"🏆 Top {top_n} signals:")
                
                for i, signal in enumerate(signals[:top_n]):
                    # Tandai sinyal SHORT dengan warna berbeda (hanya untuk info)
                    short_marker = "🚫" if signal['action'] == 'SHORT' and self.mode == 'saham_id' else ""
                    logger.info(f"  {i+1}. {signal['symbol']} | {signal['action']} {short_marker} | Score: {signal['score']} | Confidence: {signal.get('confidence_level', 'LOW')}")
            else:
                logger.info("ℹ️ No signals found with current criteria")
            
            return signals[:limit]
            
        except Exception as e:
            logger.error(f"💥 Error during scanning: {e}")
            logger.error(traceback.format_exc())
            return []
        finally:
            self.scanning_in_progress = False
            self.current_scan_task = None

    def _analyze_single_asset_enhanced(self, asset, index, total):
        """Helper method untuk menganalisis single asset dengan analisis enhanced (untuk threading)"""
        try:
            symbol = asset.get('symbol')
            asset_name = asset.get('name', symbol)
            detected_type = asset.get('detected_type', 'spot')
            formatted_symbol = asset.get('formatted_symbol', symbol)
            
            logger.info(f"  [{index+1}/{total}] Analyzing: {symbol} (Type: {detected_type})")
            
            # **SCALPING MODE FILTERS**
            if self.scalping_mode:
                # Gunakan parameter dari scalping config
                timeframe = self.scalping_config.get("timeframe", "5m")
                limit = self.scalping_config.get("lookback", 150)
                
                logger.info(f"    ⚡ Scalping mode: {timeframe} timeframe, {limit} bars")
                df = self.data_provider.get_ohlcv(formatted_symbol, timeframe, limit)
                
                # PERBAIKAN: Gunakan kondisi yang aman untuk semua DataFrame
                # Gunakan minimum bars yang sesuai dengan market type
                min_bars = self._get_min_bars()
                if df is None or df.empty or len(df) < min_bars:
                    logger.info(f"    ⚠️ Insufficient data for {symbol}: {len(df) if df is not None and not df.empty else 0} bars (minimum {min_bars} required)")
                    return None
                
                # Filter harga untuk scalping
                current_price = df['close'].iloc[-1]
                price_filter = self.scalping_config["price_filter"]
                if current_price < price_filter["min"] or current_price > price_filter["max"]:
                    logger.info(f"    ⚠️ Price filter failed for {symbol}: {current_price}")
                    return None
                
                # Filter volume untuk scalping
                if 'volume' in df.columns and 'close' in df.columns:
                    lookback = min(20, len(df))
                    volume_usd = (df['volume'].iloc[-lookback:] * df['close'].iloc[-lookback:]).mean()
                    if volume_usd < self.scalping_config["min_volume_usd"]:
                        logger.info(f"    ⚠️ Volume filter failed for {symbol}: {volume_usd}")
                        return None
                
                # Skip dummy data untuk scalping
                if self.scalping_config.get("skip_dummy_data", True):
                    if df['close'].std() < 0.001:
                        logger.info(f"    ⚠️ Dummy data filter failed for {symbol}")
                        return None
            else:
                # **NORMAL MODE**
                # **PERBAIKAN: Gunakan timeframe='1d' untuk saham_id**
                timeframe = '1d' if self.mode == 'saham_id' else self.config.get("timeframe", "1h")
                lookback = 90 if self.mode == 'saham_id' else 200
                
                if get_trading_data is not None:
                    logger.info(f"    🔧 Menggunakan get_trading_data untuk membersihkan data {formatted_symbol}")
                    df = get_trading_data(formatted_symbol, self.data_provider)
                else:
                    logger.info(f"    🔧 Menggunakan provider {self.data_provider.__class__.__name__} untuk data {formatted_symbol}")
                    df = self.data_provider.get_ohlcv(formatted_symbol, timeframe, lookback)
            
            # PERBAIKAN: Gunakan kondisi yang aman untuk semua DataFrame
            # Gunakan minimum bars yang sesuai dengan market type
            min_bars = self._get_min_bars()
            if df is None or df.empty or len(df) < min_bars:
                logger.info(f"    ⚠️ Insufficient data for {symbol}: {len(df) if df is not None and not df.empty else 0} bars (minimum {min_bars} required)")
                return None
            
            # Validasi kualitas data
            is_valid, validation_msg = self.validate_market_data(df, symbol, debug_mode=True)
            if not is_valid:
                logger.warning(f"    ⚠️ Data validation failed for {symbol}: {validation_msg}")
                return None
            
            logger.info(f"    📊 OHLCV data: {len(df)} bars, price range: {df['close'].min():.2f}-{df['close'].max():.2f}")
            
            # Pilih strategi berdasarkan mode
            if self.scalping_mode:
                strategy = self._create_scalping_strategy()
                leverage = 1  # No leverage untuk scalping spot
                detected_type = "spot"  # Scalping hanya untuk spot
            elif detected_type == "futures":
                strategy = self._create_futures_strategy()
                leverage = 5  # Default untuk futures
            else:
                strategy = self._create_spot_strategy()
                leverage = 1  # No leverage untuk spot
            
            # Analyze dengan strategy ENHANCED - GUNAKAN ANALISIS ENHANCED
            if hasattr(strategy, 'analyze_enhanced'):
                logger.info(f"    🔍 Menggunakan analyze_enhanced untuk {symbol}")
                analysis = strategy.analyze_enhanced(df, symbol)
            else:
                logger.info(f"    ⚠️ analyze_enhanced tidak tersedia, menggunakan analyze biasa")
                analysis = strategy.analyze(df, symbol)
            
            if not analysis:
                logger.info(f"    ⚠️ No analysis for {symbol}")
                return None
            
            # **PERBAIKAN PENTING: Filter SHORT untuk market yang tidak mengizinkan**
            if analysis['action'] == "SHORT" and not self._is_short_allowed(self.mode, symbol):
                logger.info(f"    ⛔ SHORT tidak diizinkan untuk {self.mode}, mengubah menjadi NEUTRAL")
                analysis['action'] = 'NEUTRAL'
                analysis['score'] = 0
            
            score = analysis.get('score', 0)
            action = analysis.get('action', 'NEUTRAL')
            
            # Gunakan min_score yang berbeda berdasarkan market type dan action
            min_score = self._get_market_min_score(self.mode, action)
            
            # **PERBAIKAN: Terapkan filter sinyal tambahan menggunakan SignalFilter**
            if action != 'NEUTRAL' and abs(score) >= min_score:
                # Buat sinyal sementara untuk filtering
                temp_signal = {
                    'symbol': formatted_symbol,
                    'action': action,
                    'score': score,
                    'probabilities': analysis.get('probabilities', {'LONG': 0.4, 'SHORT': 0.4, 'NEUTRAL': 0.2}),
                    'confidence_level': analysis.get('confidence_level', 'LOW'),
                    'rsi': analysis.get('rsi', 50),
                    'volume_ratio': analysis.get('volume_ratio', 1),
                    'volatility': analysis.get('volatility', 0.02)
                }
                
                # Terapkan filter sinyal
                should_trade, reason = SignalFilter.should_trade(temp_signal)
                
                if not should_trade:
                    logger.info(f"    ⛔ Signal filter rejected {symbol}: {reason}")
                    return None
            
            # Check jika signal valid setelah filter
            if abs(score) >= min_score and action != 'NEUTRAL':
                signal_data = {
                    'symbol': formatted_symbol,
                    'name': asset_name,
                    'score': round(score, 2),
                    'action': action,
                    'entry_price': round(analysis.get('entry_price', df['close'].iloc[-1] if len(df) > 0 else 0), 4),
                    'sl': round(analysis.get('sl', df['close'].iloc[-1] * 0.97 if len(df) > 0 else 0), 4),
                    'tp1': round(analysis.get('tp1', df['close'].iloc[-1] * 1.03 if len(df) > 0 else 0), 4),
                    'tp2': round(analysis.get('tp2', df['close'].iloc[-1] * 1.06 if len(df) > 0 else 0), 4),
                    'tp3': round(analysis.get('tp3', df['close'].iloc[-1] * 1.09 if len(df) > 0 else 0), 4),
                    'current_price': round(df['close'].iloc[-1] if len(df) > 0 else 0, 4),
                    'ml_confidence': round(analysis.get('ml_confidence', 0), 2),
                    'rsi': round(analysis.get('rsi', 50), 2),
                    'volume_ratio': round(analysis.get('volume_ratio', 1), 2),
                    'market_type': self.mode,
                    'trading_mode': detected_type,
                    'provider': 'universal',
                    'asset_type': detected_type,
                    'leverage': leverage,
                    'strategy': 'scalping' if self.scalping_mode else 'standard',
                    'short_allowed': self._is_short_allowed(self.mode, symbol),
                    # Tambahan untuk enhanced analysis
                    'probabilities': analysis.get('probabilities', {'LONG': 0.4, 'SHORT': 0.4, 'NEUTRAL': 0.2}),
                    'confidence_level': analysis.get('confidence_level', 'LOW'),
                    'filter_reason': analysis.get('notes', '')
                }
                
                logger.info(f"✅ Signal: {formatted_symbol} | {action} | Score: {score:.2f} | Type: {detected_type} | Strategy: {'SCALPING' if self.scalping_mode else 'STANDARD'} | Short Allowed: {self._is_short_allowed(self.mode, symbol)} | Confidence: {signal_data['confidence_level']}")
                return signal_data
            else:
                return None
            
        except Exception as e:
            logger.error(f"❌ Error analyzing {asset.get('symbol', 'unknown')}: {str(e)[:100]}")
            return None

    def _analyze_single_asset(self, asset, index, total):
        """Backward compatibility - gunakan enhanced version"""
        return self._analyze_single_asset_enhanced(asset, index, total)

    def _apply_market_constraints(self, analysis: dict, detected_type: str = "spot") -> dict:
        """Apply market constraints berdasarkan detected type - DIPERBAIKI UNTUK NON-CRYPTO"""
        if not isinstance(analysis, dict):
            return analysis
            
        action = analysis.get('action', 'NEUTRAL')
        
        # **PERUBAHAN: Filter SHORT untuk market yang tidak mengizinkan**
        if action == "SHORT" and not self._is_short_allowed(self.mode):
            logger.info(f"🔒 Market constraint: SHORT tidak diizinkan untuk {self.mode}")
            analysis['action'] = 'NEUTRAL'
            analysis['score'] = 0
        
        return analysis

    def analyze_with_enhanced_ml(self, symbol: str) -> dict:
        """Analyze asset dengan ML enhancement - MENGGUNAKAN get_trading_data"""
        try:
            if not self.data_provider:
                return {'error': 'No data provider available'}
            
            # Auto detect type
            detected_type, formatted_symbol = auto_detect_trading_type(symbol)
            
            # **PERBAIKAN: Gunakan timeframe='1d' untuk saham_id**
            timeframe = '1d' if self.mode == 'saham_id' else self.config.get("timeframe", "1h")
            lookback = 90 if self.mode == 'saham_id' else 200
            
            # Get data menggunakan get_trading_data jika tersedia
            if get_trading_data is not None:
                logger.info(f"🔍 Menggunakan get_trading_data untuk membersihkan data {formatted_symbol}")
                df = get_trading_data(formatted_symbol, self.data_provider)
            else:
                logger.info(f"🔍 Menggunakan provider {self.data_provider.__class__.__name__} untuk data {formatted_symbol}")
                df = self.data_provider.get_ohlcv(formatted_symbol, timeframe, lookback)
            
            # PERBAIKAN: Gunakan kondisi yang aman untuk semua DataFrame
            # Gunakan minimum bars yang sesuai dengan market type
            min_bars = self._get_min_bars()
            if df is None or df.empty or len(df) < min_bars:
                return {'error': f'Insufficient data: {len(df) if df is not None else 0} bars (minimum {min_bars} required)'}
            
            # Validasi data
            is_valid, validation_msg = self.validate_market_data(df, symbol, debug_mode=True)
            if not is_valid:
                return {'error': f'Data validation failed: {validation_msg}'}
            
            # Pilih strategi berdasarkan tipe
            if detected_type == "futures":
                strategy = self._create_futures_strategy()
            else:
                strategy = self._create_spot_strategy()
            
            # Technical analysis ENHANCED
            if hasattr(strategy, 'analyze_enhanced'):
                analysis = strategy.analyze_enhanced(df)
            else:
                analysis = strategy.analyze(df)
                
            if not analysis:
                return {'error': 'Analysis failed'}
            
            # Apply market constraints (dengan filter SHORT untuk non-crypto)
            analysis = self._apply_market_constraints(analysis, detected_type)
            
            return analysis
            
        except Exception as e:
            logger.error(f"Analysis error for {symbol}: {e}")
            return {'error': str(e)}

    # =============================================
    # BACKTEST METHODS
    # =============================================

    def run_advanced_backtest(self, symbol, timeframe=None, limit=500):
        """Run advanced backtest"""
        if not self.data_provider:
            return {"error": "No data provider available"}
            
        try:
            detected_type, formatted_symbol = auto_detect_trading_type(symbol)
            
            if timeframe is None:
                timeframe = '1d' if self.mode == 'saham_id' else self.config.get("timeframe", "1h")
                limit = 90 if self.mode == 'saham_id' else limit
                
            logger.info(f"🔧 Running advanced backtest for {formatted_symbol} ({detected_type})...")
            
            # Get data menggunakan get_trading_data jika tersedia
            if get_trading_data is not None:
                logger.info(f"  🔧 Menggunakan get_trading_data untuk data bersih")
                df = get_trading_data(formatted_symbol, self.data_provider)
            else:
                logger.info(f"  🔧 Menggunakan provider {self.data_provider.__class__.__name__}")
                df = self.data_provider.get_ohlcv(formatted_symbol, timeframe, limit)
            
            # PERBAIKAN: Gunakan kondisi yang aman untuk semua DataFrame
            # Gunakan minimum bars yang sesuai dengan market type
            min_bars_backtest = self._get_min_bars_backtest()
            if df is None or df.empty or len(df) < min_bars_backtest:
                return {"error": f"Insufficient data for backtest: {len(df) if df is not None else 0} bars (minimum {min_bars_backtest} required)"}
            
            # Validasi data
            is_valid, validation_msg = self.validate_market_data(df, symbol, debug_mode=True)
            if not is_valid:
                return {"error": f"Data validation failed: {validation_msg}"}
            
            # Pilih strategi
            if detected_type == "futures":
                strategy = self._create_futures_strategy()
            else:
                strategy = self._create_spot_strategy()
            
            # Run backtest
            basic_result = self.backtest_engine.run_backtest(df, strategy)
            
            return {
                'symbol': formatted_symbol,
                'detected_type': detected_type,
                'timeframe': timeframe,
                'basic_backtest': basic_result,
                'data_points': len(df)
            }
            
        except Exception as e:
            logger.error(f"Error in advanced backtest: {e}")
            return {"error": str(e)}

    # =============================================
    # PORTFOLIO OPTIMIZATION METHODS
    # =============================================

    def get_optimized_portfolio_allocation(self, signals: List[Dict], total_capital: float) -> List[Dict]:
        """Get optimized portfolio allocation"""
        try:
            return self.portfolio_optimizer.momentum_based_allocation(signals, total_capital)
        except Exception as e:
            logger.error(f"Portfolio optimization error: {e}")
            return self._simple_allocation_fallback(signals, total_capital)
    
    def _simple_allocation_fallback(self, signals: List[Dict], total_capital: float) -> List[Dict]:
        """Simple allocation fallback"""
        if not signals:
            return []
        
        n_signals = len(signals)
        base_allocation = total_capital / n_signals
        
        return [
            {
                'symbol': s['symbol'],
                'allocation_percent': 1/n_signals,
                'allocated_capital': base_allocation,
                'score': s.get('score', 0),
                'action': s.get('action', 'NEUTRAL'),
                'asset_type': s.get('asset_type', 'spot')
            }
            for s in signals
        ]

    # =============================================
    # BACKGROUND TASKS - PERBAIKAN UTAMA
    # =============================================

    def start_background_tasks(self):
        """Start background tasks"""
        try:
            # PERBAIKAN: Cek jika scheduler_thread ada dan masih hidup
            if self.scheduler_thread is not None and hasattr(self.scheduler_thread, 'is_alive'):
                if self.scheduler_thread.is_alive():
                    logger.info("Background tasks already running")
                    return
            
            self.stop_scheduler = False
            self.scheduler_thread = threading.Thread(target=self._run_scheduler, daemon=True)
            self.scheduler_thread.start()
            
            logger.info("✅ Background tasks started successfully")
            
        except Exception as e:
            logger.error(f"❌ Error starting background tasks: {e}")

    def stop_background_tasks(self):
        """Stop background tasks"""
        try:
            self.stop_scheduler = True
            
            # PERBAIKAN: Cek jika scheduler_thread ada
            if self.scheduler_thread is not None:
                if hasattr(self.scheduler_thread, 'is_alive') and self.scheduler_thread.is_alive():
                    self.scheduler_thread.join(timeout=5)
                self.scheduler_thread = None
            
            schedule.clear()
            logger.info("✅ Background tasks stopped")
        except Exception as e:
            logger.error(f"❌ Error stopping background tasks: {e}")

    def _run_scheduler(self):
        """Run scheduler loop"""
        while not self.stop_scheduler:
            try:
                schedule.run_pending()
                time.sleep(1)
            except Exception as e:
                logger.error(f"Scheduler error: {e}")
                time.sleep(5)

    def _update_positions(self):
        """Update all positions"""
        if not self.trading_enabled or not self.data_provider:
            return
        
        try:
            positions = self.position_manager.positions
            if not positions:
                return
            
            for symbol in list(positions.keys()):
                try:
                    ticker = self.data_provider.get_ticker(symbol)
                    if ticker and 'last' in ticker and ticker['last'] > 0:
                        # Update position dengan harga baru
                        pass
                except Exception as e:
                    logger.warning(f"Failed to get price for {symbol}: {e}")
                    
        except Exception as e:
            logger.error(f"Error updating positions: {e}")

    # =============================================
    # BACKWARD COMPATIBILITY METHODS
    # =============================================

    def analyze_asset(self, symbol):
        """Backward compatibility method - TANPA BIAS"""
        return self.analyze_with_enhanced_ml(symbol)
    
    def get_trade_history(self, limit=20):
        """Get trade history"""
        return self.db.get_trade_history(self.mode, limit)

    def calculate_custom_entry(self, symbol, entry_price, action="LONG"):
        """Calculate custom entry dengan TP/SL - DIPERBAIKI"""
        try:
            detected_type, formatted_symbol = auto_detect_trading_type(symbol)
            
            # **PERBAIKAN: Gunakan timeframe='1d' untuk saham_id**
            timeframe = '1d' if self.mode == 'saham_id' else self.config.get("timeframe", "1h")
            lookback = 90 if self.mode == 'saham_id' else 50
            
            # Get data menggunakan get_trading_data jika tersedia
            if get_trading_data is not None:
                logger.info(f"🔍 Menggunakan get_trading_data untuk {formatted_symbol}")
                df = get_trading_data(formatted_symbol, self.data_provider)
            else:
                logger.info(f"🔍 Menggunakan provider {self.data_provider.__class__.__name__} untuk {formatted_symbol}")
                df = self.data_provider.get_ohlcv(formatted_symbol, timeframe, lookback)
            
            # PERBAIKAN: Gunakan kondisi yang aman untuk semua DataFrame
            if df is None or df.empty or len(df) < 20:
                # Fallback calculation dengan ATR default
                atr_value = entry_price * 0.02  # 2% ATR default
                
                if action == "LONG":
                    tp1 = entry_price + (atr_value * 1.0)
                    tp2 = entry_price + (atr_value * 2.0)
                    tp3 = entry_price + (atr_value * 3.0)
                    sl = entry_price - (atr_value * 1.5)
                else:  # SHORT
                    tp1 = entry_price - (atr_value * 1.0)
                    tp2 = entry_price - (atr_value * 2.0)
                    tp3 = entry_price - (atr_value * 3.0)
                    sl = entry_price + (atr_value * 1.5)
                
                return {
                    'symbol': formatted_symbol,
                    'detected_type': detected_type,
                    'entry_price': entry_price,
                    'tp1': tp1,
                    'tp2': tp2,
                    'tp3': tp3,
                    'sl': sl,
                    'method': 'fallback_calculation'
                }
            
            # Pilih strategi berdasarkan tipe
            if detected_type == "futures":
                strategy = self._create_futures_strategy()
            else:
                strategy = self._create_spot_strategy()
            
            # Calculate menggunakan strategy ENHANCED
            if hasattr(strategy, 'analyze_enhanced'):
                analysis = strategy.analyze_enhanced(df)
            else:
                analysis = strategy.analyze(df)
            
            if analysis and 'tp1' in analysis and 'sl' in analysis:
                # Dapatkan current_price dari data terbaru
                current_price = df['close'].iloc[-1]
                
                if current_price > 0:
                    # Hitung rasio untuk menyesuaikan TP/SL dengan entry_price yang diberikan
                    price_ratio = entry_price / current_price
                    
                    # Sesuaikan TP/SL berdasarkan rasio
                    tp1 = analysis['tp1'] * price_ratio
                    tp2 = analysis['tp2'] * price_ratio
                    tp3 = analysis['tp3'] * price_ratio
                    sl = analysis['sl'] * price_ratio
                    
                    # Untuk SHORT, pastikan TP lebih rendah dari entry dan SL lebih tinggi
                    if action == "SHORT":
                        if tp1 > entry_price:
                            tp1 = entry_price * 0.97
                        if tp2 > entry_price:
                            tp2 = entry_price * 0.94
                        if tp3 > entry_price:
                            tp3 = entry_price * 0.91
                        if sl < entry_price:
                            sl = entry_price * 1.03
                else:
                    # Fallback jika current_price tidak valid
                    atr_value = entry_price * 0.02
                    if action == "LONG":
                        tp1 = entry_price * 1.03
                        tp2 = entry_price * 1.06
                        tp3 = entry_price * 1.09
                        sl = entry_price * 0.97
                    else:
                        tp1 = entry_price * 0.97
                        tp2 = entry_price * 0.94
                        tp3 = entry_price * 0.91
                        sl = entry_price * 1.03
                
                return {
                    'symbol': formatted_symbol,
                    'detected_type': detected_type,
                    'entry_price': entry_price,
                    'tp1': tp1,
                    'tp2': tp2,
                    'tp3': tp3,
                    'sl': sl,
                    'method': 'strategy_adjusted',
                    'current_price_in_data': current_price if current_price > 0 else 0
                }
            
            # Fallback jika analisis gagal
            atr_value = entry_price * 0.02
            
            if action == "LONG":
                tp1 = entry_price * 1.03
                tp2 = entry_price * 1.06
                tp3 = entry_price * 1.09
                sl = entry_price * 0.97
            else:
                tp1 = entry_price * 0.97
                tp2 = entry_price * 0.94
                tp3 = entry_price * 0.91
                sl = entry_price * 1.03
            
            return {
                'symbol': formatted_symbol,
                'detected_type': detected_type,
                'entry_price': entry_price,
                'tp1': tp1,
                'tp2': tp2,
                'tp3': tp3,
                'sl': sl,
                'method': 'fallback_percentage'
            }
                
        except Exception as e:
            logger.error(f"Error in custom entry calculation for {symbol}: {e}")
            
            # Ultimate fallback
            if action == "LONG":
                tp1 = entry_price * 1.03
                tp2 = entry_price * 1.06
                tp3 = entry_price * 1.09
                sl = entry_price * 0.97
            else:
                tp1 = entry_price * 0.97
                tp2 = entry_price * 0.94
                tp3 = entry_price * 0.91
                sl = entry_price * 1.03
            
            return {
                'symbol': symbol,
                'detected_type': 'spot',
                'entry_price': entry_price,
                'tp1': tp1,
                'tp2': tp2,
                'tp3': tp3,
                'sl': sl,
                'method': 'error_fallback'
            }
    
    def get_provider_health(self):
        """Get provider health information"""
        if not hasattr(self, 'data_provider'):
            return {'status': 'no_provider', 'type': 'unknown'}
        
        try:
            # Untuk SmartChainDataProvider
            if hasattr(self.data_provider, 'get_health_status'):
                health = self.data_provider.get_health_status()
                health['provider_type'] = 'smart_chain'
                health['provider_class'] = self.data_provider.__class__.__name__
                return health
            
            # Untuk UnifiedDataProvider
            elif hasattr(self.data_provider, 'get_health_metrics'):
                health = self.data_provider.get_health_metrics()
                health['provider_type'] = 'unified'
                health['provider_class'] = self.data_provider.__class__.__name__
                return health
            
            # Untuk EnhancedCCXTDataProvider
            elif hasattr(self.data_provider, 'get_health_metrics'):
                health = self.data_provider.get_health_metrics()
                health['provider_type'] = 'ccxt'
                health['provider_class'] = self.data_provider.__class__.__name__
                return health
            
            # Untuk EnhancedYFinanceDataProvider
            elif hasattr(self.data_provider, 'get_health_metrics'):
                health = self.data_provider.get_health_metrics()
                health['provider_type'] = 'yfinance'
                health['provider_class'] = self.data_provider.__class__.__name__
                return health
            
            # Fallback
            else:
                return {
                    'provider_type': 'unknown',
                    'provider_class': self.data_provider.__class__.__name__,
                    'status': 'active' if self.data_provider else 'inactive'
                }
                
        except Exception as e:
            logger.error(f"Error getting provider health: {e}")
            return {'status': 'error', 'error': str(e)}

    # =============================================
    # SET MODE METHOD (SIMPLIFIED)
    # =============================================

    def set_mode(self, mode):
        """Set trading mode dengan universal provider"""
        try:
            # Check jika mode scalping
            if mode == "scalping":
                self.scalping_mode = True
                mode = "crypto"  # Scalping hanya untuk crypto
                logger.info(f"🎯 Setting market mode to: SCALPING (crypto spot)")
            else:
                self.scalping_mode = False
                self.mode = mode.lower()
                logger.info(f"🎯 Setting market mode to: {self.mode.upper()}")
            
            # Stop existing tasks
            self.stop_background_tasks()
            
            # Update config
            self.config["market_type"] = self.mode
            
            # Reinitialize provider
            logger.info(f"🔄 Reconfiguring UniversalProvider for {self.mode}...")
            self._setup_universal_provider()
            
            # Setup strategy
            if create_strategy_for_symbol is not None:
                sample_symbol = "BTC/USDT" if self.mode == 'crypto' else "AAPL" if self.mode == 'us_stocks' else "BBCA.JK"
                
                try:
                    self.strategy = create_strategy_for_symbol(
                        sample_symbol,
                        market_type=self.mode
                    )
                    logger.info(f"✅ Created auto-detected strategy for {self.mode}")
                except Exception as e:
                    logger.warning(f"⚠️ Auto strategy creation failed: {e}, falling back to TechnicalAnalysisStrategy")
                    self.strategy = TechnicalAnalysisStrategy(
                        market_type=self.mode,
                        trading_type="spot",
                        atr_multiplier=self.config.get("atr_multiplier", 1.0),
                        entry_range_pct=self.config.get("entry_range_pct", 0.02),
                    )
            else:
                self.strategy = TechnicalAnalysisStrategy(
                    market_type=self.mode,
                    trading_type="spot",
                    atr_multiplier=self.config.get("atr_multiplier", 1.0),
                    entry_range_pct=self.config.get("entry_range_pct", 0.02),
                )
            
            # Test provider connection
            test_assets = self._test_provider_connection()
            
            if test_assets:
                logger.info(f"✅ Provider ready for {self.mode}")
                logger.info(f"📋 Sample assets: {test_assets[:3]}")
                
                # Start background tasks
                self.start_background_tasks()
                return True
            else:
                logger.warning(f"⚠️ Provider test returned no assets, but continuing...")
                self.start_background_tasks()
                return True
                
        except Exception as e:
            logger.error(f"❌ Failed to configure provider: {e}")
            logger.error(traceback.format_exc())
            return False

    def _test_provider_connection(self):
        """Test provider connection - PERBAIKAN UTAMA"""
        try:
            logger.info("🧪 Testing UniversalProvider connection...")
            logger.info(f"  Provider: {self.data_provider.__class__.__name__}")
            
            # **PERBAIKAN: Handle non-crypto provider test**
            if self.mode in ['saham_id', 'forex', 'us_stocks']:
                logger.info(f"  Mode {self.mode} menggunakan NonCryptoAssetsProvider")
                
                # Test NonCryptoAssetsProvider
                if self.non_crypto_provider:
                    # **PERBAIKAN: Gunakan get_active_assets() untuk saham_id**
                    if self.mode == 'saham_id' and hasattr(self.non_crypto_provider, 'get_active_assets'):
                        assets = self.non_crypto_provider.get_active_assets(
                            category='indonesia_stocks',
                            min_volume=1000000,
                            min_volatility=0.025,
                            limit=25
                        )
                    else:
                        assets = self.get_popular_assets(5)
                        
                    if assets:
                        asset_symbols = [f"{a['symbol']} ({a['name']})" for a in assets[:5]]
                        logger.info(f"  ✅ NonCryptoAssetsProvider test passed")
                        return asset_symbols
                    else:
                        logger.warning("  ⚠️ NonCryptoAssetsProvider returned no assets")
                        return []
                else:
                    logger.warning("  ⚠️ NonCryptoAssetsProvider not available")
                    return []
            
            # Test get popular assets untuk crypto
            assets = self.get_popular_assets(5)
            
            if not assets:
                logger.warning("⚠️ No assets returned from provider")
                return []
            
            # Format asset symbols untuk display
            asset_symbols = []
            for asset in assets[:5]:
                symbol = asset.get('symbol', 'Unknown')
                name = asset.get('name', 'N/A')
                detected_type = asset.get('detected_type', 'spot')
                asset_symbols.append(f"{symbol} ({name}) [{detected_type}]")
            
            # Test OHLCV untuk asset pertama
            if assets:
                test_asset = assets[0]
                test_symbol = test_asset.get('formatted_symbol', test_asset.get('symbol'))
                logger.info(f"  Testing OHLCV for: {test_symbol}")
                
                # **PERBAIKAN: Gunakan timeframe='1d' untuk saham_id**
                timeframe = '1d' if self.mode == 'saham_id' else '1h'
                lookback = 90 if self.mode == 'saham_id' else 10
                
                # Gunakan get_trading_data jika tersedia
                if get_trading_data is not None:
                    df = get_trading_data(test_symbol, self.data_provider)
                else:
                    df = self.data_provider.get_ohlcv(test_symbol, timeframe, lookback)
                
                # Validasi data
                if df is not None and not df.empty:
                    is_valid, msg = self.validate_market_data(df, test_symbol, debug_mode=True)
                    if is_valid:
                        logger.info(f"  ✅ OHLCV data: {len(df)} bars (valid)")
                        logger.info(f"  📊 Price range: ${df['close'].min():.2f} - ${df['close'].max():.2f}")
                    else:
                        logger.warning(f"  ⚠️ OHLCV data validation failed: {msg}")
                else:
                    logger.warning("  ⚠️ No OHLCV data, but continuing...")
            
            return asset_symbols
            
        except Exception as e:
            logger.warning(f"⚠️ Provider test had issues: {e}")
            return []

# =============================================
# TRADING CORE - SIMPLIFIED VERSION
# =============================================

class TradingCore:
    """Main trading engine dengan universal provider"""
    
    def __init__(self, config=None):
        self.config = config or {}
        
        # Setup universal data provider
        self.data_provider = self._setup_data_provider()
        
        # Setup trading mode
        self.trading_type = self.config.get("trading_mode", "spot")
        
        # Setup strategy
        try:
            if create_strategy_for_symbol is not None:
                sample_symbol = "BTC/USDT" if self.config.get("market_type", "crypto") == "crypto" else "AAPL"
                
                self.strategy = create_strategy_for_symbol(
                    sample_symbol,
                    market_type=self.config.get("market_type", "crypto"),
                    trading_mode=self.trading_type
                )
                logger.info(f"✅ Created auto-detected strategy untuk {self.config.get('market_type', 'crypto')} ({self.trading_type})")
            else:
                from strategies import TechnicalAnalysisStrategy
                self.strategy = TechnicalAnalysisStrategy(
                    market_type=self.config.get("market_type", "crypto"),
                    trading_type=self.trading_type,
                    atr_multiplier=self.config.get("atr_multiplier", 1.0),
                    entry_range_pct=self.config.get("entry_range_pct", 0.02)
                )
                logger.info(f"✅ Menggunakan TechnicalAnalysisStrategy untuk {self.config.get('market_type', 'crypto')} ({self.trading_type})")
        except ImportError as e:
            print(f"❌ Gagal import strategies di TradingCore: {e}")
            class DummyStrategy:
                def analyze(self, *args, **kwargs):
                    return {'action': 'NEUTRAL', 'score': 0}
                def analyze_enhanced(self, *args, **kwargs):
                    return {'action': 'NEUTRAL', 'score': 0}
            self.strategy = DummyStrategy()
        
        logger.info(f"🚀 TradingCore initialized | Mode: {self.trading_type}")
    
    def _setup_data_provider(self):
        """Setup universal data provider"""
        try:
            # Gunakan provider berdasarkan market type
            market_type = self.config.get("market_type", "crypto")
            
            if market_type == 'crypto':
                # Coba CCXT terlebih dahulu
                if EnhancedCCXTDataProvider:
                    provider = EnhancedCCXTDataProvider(
                        exchange_id='binance',
                        api_key='',
                        secret=''
                    )
                    logger.info("✅ Using CCXT (Binance) for crypto data")
                    return provider
                else:
                    # Fallback ke YFinance
                    if EnhancedYFinanceDataProvider:
                        provider = EnhancedYFinanceDataProvider()
                        logger.info("✅ Using YFinance for crypto (fallback)")
                        return provider
            
            elif market_type in ['us_stocks', 'saham_id', 'forex']:
                # Untuk stocks/forex, gunakan YFinance
                if EnhancedYFinanceDataProvider:
                    provider = EnhancedYFinanceDataProvider()
                    logger.info(f"✅ Using YFinance for {market_type}")
                    return provider
            
            # Default ke UnifiedDataProvider jika ada
            if UnifiedDataProvider:
                provider = UnifiedDataProvider(
                    market_type=self.config.get("market_type", "crypto"),
                    trading_mode=self.config.get("trading_mode", "spot"),
                    default_exchange=self.config.get("default_exchange", "binance")
                )
                logger.info(f"✅ Using UnifiedDataProvider with {provider.active_exchange}")
                return provider
            
            raise Exception("No provider available")
            
        except Exception as e:
            logger.error(f"❌ Failed to setup universal provider: {e}")
            # Last resort: create simple provider
            class SimpleProvider:
                def __init__(self, *args, **kwargs):
                    pass
                def get_ohlcv(self, *args, **kwargs):
                    return pd.DataFrame()
                def get_ticker(self, *args, **kwargs):
                    return {'last': 0}
                def get_popular_assets(self, *args, **kwargs):
                    return []
            return SimpleProvider()
    
    def set_mode(self, market_type):
        """Set trading mode dengan update provider"""
        try:
            self.config["market_type"] = market_type
            
            # Update provider dengan mode baru
            self.data_provider.market_type = market_type
            self.data_provider.trading_mode = self.trading_type
            
            # Reinitialize jika perlu
            if hasattr(self.data_provider, '_initialize_providers_with_smart_fallback'):
                self.data_provider._initialize_providers_with_smart_fallback()
            
            logger.info(f"✅ Market mode set to: {market_type}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to set mode: {e}")
            return False
    
    def set_trading_mode(self, trading_mode):
        """Set spot/futures mode"""
        valid_modes = ['spot', 'future', 'futures']
        
        if trading_mode.lower() not in valid_modes:
            logger.error(f"Invalid trading mode: {trading_mode}")
            return False
        
        self.trading_type = trading_mode.lower()
        self.config["trading_mode"] = self.trading_type
        
        # Update provider
        if hasattr(self.data_provider, 'trading_mode'):
            self.data_provider.trading_mode = self.trading_type
            logger.info(f"✅ Trading mode updated in provider: {self.trading_type}")
        
        logger.info(f"✅ Trading mode set to: {self.trading_type}")
        return True
    
    def scan_market(self, scan_type="standard", limit=50):
        """Scan market dengan universal provider"""
        try:
            market_type = self.config.get("market_type", "crypto")
            timeframe = '1d' if market_type == 'saham_id' else '1h'  # PERBAIKAN: '1d' untuk saham_id
            lookback = 90 if market_type == 'saham_id' else 200     # 90 hari untuk saham
            
            logger.info(f"🔍 Scanning {self.trading_type} market ({scan_type}) | Timeframe: {timeframe} | Lookback: {lookback}")
            
            # PERBAIKAN: Gunakan active assets dari provider untuk saham_id dengan multi-threading
            if market_type == 'saham_id':
                # **PERBAIKAN: Gunakan get_active_assets() untuk efisiensi**
                if hasattr(self, 'non_crypto_provider') and hasattr(self.non_crypto_provider, 'get_active_assets'):
                    symbols = self.non_crypto_provider.get_active_assets(
                        category='indonesia_stocks',
                        min_volume=1000000,
                        min_volatility=0.025,
                        limit=25  # **PERBAIKAN: Scan 25 saham cepat**
                    )
                    assets = [{'symbol': s} for s in symbols]
                else:
                    assets = self.data_provider.get_popular_assets(limit=25)
            else:
                assets = self.data_provider.get_popular_assets(limit=limit)
            
            if not assets:
                logger.error("❌ No assets found for scanning")
                return []
            
            logger.info(f"📊 Found {len(assets)} assets for scanning")
            
            # **PERBAIKAN: Multi-threading untuk scan cepat**
            results = []
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                future_to_asset = {}
                for asset in assets[:25]:  # **PERBAIKAN: Maksimal 25 assets untuk scanning cepat**
                    symbol = asset['symbol'] if isinstance(asset, dict) else asset
                    future_to_asset[executor.submit(self._analyze_symbol_enhanced, symbol, timeframe, lookback, market_type)] = symbol
                
                for future in concurrent.futures.as_completed(future_to_asset):
                    symbol = future_to_asset[future]
                    try:
                        signal = future.result(timeout=30)
                        if signal and signal.get('action') != 'NEUTRAL':
                            # **PERBAIKAN: Block SHORT untuk saham_id**
                            if market_type == 'saham_id' and signal['action'] == 'SHORT':
                                signal['action'] = 'NEUTRAL'
                                signal['notes'] = "SHORT diblokir untuk saham Indonesia (regulasi IDX)"
                            
                            if signal['action'] != 'NEUTRAL':
                                results.append(signal)
                    except Exception as e:
                        logger.debug(f"❌ Failed to analyze {symbol}: {e}")
            
            logger.info(f"✅ Scan complete: {len(results)} signals found")
            return results
            
        except Exception as e:
            logger.error(f"❌ Market scan failed: {e}")
            return []
    
    def _analyze_symbol_enhanced(self, symbol, timeframe, lookback, market_type):
        """Helper untuk analisis per symbol dengan enhanced analysis"""
        try:
            time.sleep(1)  # Delay untuk rate limit
            
            # Get data menggunakan get_trading_data jika tersedia
            if get_trading_data is not None:
                df = get_trading_data(symbol, self.data_provider)
            else:
                df = self.data_provider.get_ohlcv(symbol, timeframe, lookback)
            
            if df is None or df.empty or len(df) < 40:
                return None
            
            # Buat strategy berdasarkan market type
            if market_type == 'saham_id':
                # **PERBAIKAN: Gunakan spot strategy untuk saham_id (no leverage)**
                strategy = TechnicalAnalysisStrategy(
                    market_type=market_type,
                    trading_type="spot",
                    atr_multiplier=1.0,
                    entry_range_pct=0.02
                )
            else:
                # Untuk crypto, auto-detect type
                detected_type, _ = auto_detect_trading_type(symbol)
                if detected_type == "futures":
                    strategy = TechnicalAnalysisStrategy(
                        market_type=market_type,
                        trading_type="futures",
                        atr_multiplier=1.0,
                        entry_range_pct=0.02
                    )
                else:
                    strategy = TechnicalAnalysisStrategy(
                        market_type=market_type,
                        trading_type="spot",
                        atr_multiplier=1.0,
                        entry_range_pct=0.02
                    )
            
            # Gunakan analisis enhanced jika tersedia
            if hasattr(strategy, 'analyze_enhanced'):
                signal = strategy.analyze_enhanced(df, symbol)
            else:
                signal = strategy.analyze(df, symbol)
            
            # Terapkan filter sinyal tambahan
            if signal and signal.get('action') != 'NEUTRAL':
                temp_signal = {
                    'symbol': symbol,
                    'action': signal['action'],
                    'score': signal.get('score', 0),
                    'probabilities': signal.get('probabilities', {'LONG': 0.4, 'SHORT': 0.4, 'NEUTRAL': 0.2}),
                    'confidence_level': signal.get('confidence_level', 'LOW'),
                    'rsi': signal.get('rsi', 50),
                    'volume_ratio': signal.get('volume_ratio', 1),
                    'volatility': signal.get('volatility', 0.02)
                }
                
                should_trade, reason = SignalFilter.should_trade(temp_signal)
                if not should_trade:
                    signal['action'] = 'NEUTRAL'
                    signal['notes'] = reason
            
            return {
                'symbol': symbol,
                'action': signal.get('action', 'NEUTRAL'),
                'score': signal.get('score', 0),
                'price': df['close'].iloc[-1] if len(df) > 0 else 0,
                'data_points': len(df),
                'probabilities': signal.get('probabilities', {}),
                'confidence_level': signal.get('confidence_level', 'LOW')
            }
            
        except Exception as e:
            logger.debug(f"❌ Failed to analyze {symbol}: {e}")
            return None
    
    def _analyze_symbol(self, symbol, timeframe, lookback, market_type):
        """Backward compatibility"""
        return self._analyze_symbol_enhanced(symbol, timeframe, lookback, market_type)
    
    def get_health_status(self):
        """Get health status dari provider"""
        try:
            if hasattr(self.data_provider, 'get_health_metrics'):
                return self.data_provider.get_health_metrics()
            else:
                return {'status': 'unknown', 'provider': type(self.data_provider).__name__}
        except Exception as e:
            return {'status': 'error', 'error': str(e)}

# =============================================
# BACKWARD COMPATIBILITY
# =============================================

TradingBot = EnhancedTradingBot

# =============================================
# TESTING FUNCTIONALITY - DIPERBAIKI
# =============================================

def test_universal_provider():
    """Test bot dengan universal provider"""
    print("🧪 Testing TradingBot dengan UNIVERSAL PROVIDER...")
    print("="*60)
    
    bot = EnhancedTradingBot()
    
    # Test crypto market
    print("\n1. Testing CRYPTO market...")
    success = bot.set_mode("crypto")
    
    if success:
        print("✅ Crypto mode set successfully")
        
        # Test popular assets
        assets = bot.get_popular_assets(10)
        print(f"   Found {len(assets)} assets")
        for asset in assets[:5]:
            print(f"   - {asset['symbol']} ({asset.get('detected_type', 'N/A')})")
        
        # Test scanning
        print("\n2. Testing scanning...")
        signals = bot.scan_potential_assets(limit=10)
        print(f"   Found {len(signals)} signals")
        
        if signals:
            for i, signal in enumerate(signals[:10]):
                print(f"   {i+1}. {signal['symbol']}: {signal['action']} (Score: {signal['score']}, Type: {signal.get('trading_mode', 'N/A')}, Leverage: {signal.get('leverage', 1)}x, Confidence: {signal.get('confidence_level', 'LOW')})")
        else:
            print("   ℹ️ No signals found - this is normal with real data")
    
    # Test saham_id dengan 500 aset
    print("\n3. Testing SAHAM_ID market dengan 500+ aset...")
    success = bot.set_mode("saham_id")
    
    if success:
        print("✅ Saham ID mode set successfully")
        
        # Test popular assets saham_id
        assets = bot.get_popular_assets(15)
        print(f"   Found {len(assets)} Indonesian stocks")
        for i, asset in enumerate(assets[:15]):
            print(f"   {i+1}. {asset['symbol']} ({asset.get('name', 'N/A')}) (Source: {asset.get('source', 'N/A')})")
        
        # Test scanning saham_id
        print("\n4. Testing scanning SAHAM_ID...")
        signals = bot.scan_potential_assets(limit=10)
        print(f"   Found {len(signals)} Indonesian stock signals")
        
        if signals:
            for i, signal in enumerate(signals[:10]):
                print(f"   {i+1}. {signal['symbol']}: {signal['action']} (Score: {signal['score']}, Confidence: {signal.get('confidence_level', 'LOW')})")
                # Pastikan tidak ada sinyal SHORT untuk saham Indonesia
                if signal['action'] == 'SHORT':
                    print(f"     ⚠️ ERROR: SHORT signal found for Indonesian stock!")
        else:
            print("   ℹ️ No Indonesian stock signals found - this is normal with real data")
    
    # Test scalping mode
    print("\n5. Testing SCALPING mode...")
    success = bot.set_mode("scalping")
    
    if success:
        print("✅ Scalping mode set successfully")
        
        # Test scanning scalping
        print("\n6. Testing SCALPING scanning...")
        signals = bot.scan_potential_assets(limit=5)
        print(f"   Found {len(signals)} scalping signals")
        
        if signals:
            for i, signal in enumerate(signals[:5]):
                print(f"   {i+1}. {signal['symbol']}: {signal['action']} (Score: {signal['score']}, Strategy: {signal.get('strategy', 'N/A')}, Confidence: {signal.get('confidence_level', 'LOW')})")
        else:
            print("   ℹ️ No scalping signals found - this is normal with strict filters")
    
    print("\n" + "="*60)
    print("✅ Test completed - Bot menggunakan Universal Provider dengan enhanced analysis")
    print("   Auto-detect spot/futures dari simbol")
    print("   Leverage auto-detection (1x spot, 5x futures)")
    print("   Menggunakan get_trading_data untuk membersihkan data")
    print("   TANPA BIAS untuk semua sinyal")
    print("   SHORT diizinkan untuk crypto (spot & futures)")
    print("   SHORT TIDAK diizinkan untuk Saham Indonesia (sesuai regulasi IDX)")
    print("   SCALPING mode dengan filter ketat dan timeframe 5m")
    print("   SUPPORT 500+ ASSETS untuk non-crypto markets")
    print("   ✅ ENHANCED ANALYSIS: Menggunakan analyze_enhanced untuk analisis lebih baik")
    print("   ✅ SIGNAL FILTER: Terapkan filter sinyal tambahan")
    print("   ✅ CONFIDENCE LEVEL: HIGH/MEDIUM/LOW berdasarkan score")
    print("   ✅ PROBABILITIES: Probabilitas LONG/SHORT/NEUTRAL")
    print("   ✅ PERBAIKAN: Menggunakan get_active_assets() untuk efisiensi scanning")
    print("   ✅ PERBAIKAN: Timeframe='1d' untuk saham_id")
    print("   ✅ PERBAIKAN: Multi-threading untuk scan 25 saham cepat")
    print("   ✅ PERBAIKAN: SHORT diblokir untuk saham_id")

def test_non_crypto_assets_500():
    """Test khusus untuk 500+ aset non-crypto"""
    print("\n" + "="*60)
    print("TESTING 500+ NON-CRYPTO ASSETS")
    print("="*60)
    
    bot = EnhancedTradingBot()
    
    # Test Saham Indonesia
    print("\n1. Testing SAHAM_ID dengan 500+ aset...")
    success = bot.set_mode("saham_id")
    
    if success:
        print("✅ Saham ID mode set successfully")
        
        # Test popular assets dengan limit 500
        assets = bot.get_popular_assets(500)
        print(f"   Found {len(assets)} Indonesian stocks")
        
        # Hitung sumber aset
        sources = {}
        for asset in assets:
            source = asset.get('source', 'unknown')
            sources[source] = sources.get(source, 0) + 1
        
        print(f"   Sources: {sources}")
        
        # Tampilkan 20 aset pertama
        print("\n   Top 20 assets:")
        for i, asset in enumerate(assets[:20]):
            print(f"   {i+1:3d}. {asset['symbol']} - {asset['name']} (Source: {asset.get('source', 'N/A')})")
    
    # Test US Stocks
    print("\n2. Testing US_STOCKS dengan 500+ aset...")
    success = bot.set_mode("us_stocks")
    
    if success:
        print("✅ US Stocks mode set successfully")
        
        # Test popular assets dengan limit 500
        assets = bot.get_popular_assets(500)
        print(f"   Found {len(assets)} US stocks")
        
        # Hitung sumber aset
        sources = {}
        for asset in assets:
            source = asset.get('source', 'unknown')
            sources[source] = sources.get(source, 0) + 1
        
        print(f"   Sources: {sources}")
        
        # Tampilkan 20 aset pertama
        print("\n   Top 20 assets:")
        for i, asset in enumerate(assets[:20]):
            print(f"   {i+1:3d}. {asset['symbol']} - {asset['name']} (Source: {asset.get('source', 'N/A')})")
    
    # Test Forex
    print("\n3. Testing FOREX dengan 500+ aset...")
    success = bot.set_mode("forex")
    
    if success:
        print("✅ Forex mode set successfully")
        
        # Test popular assets dengan limit 500
        assets = bot.get_popular_assets(500)
        print(f"   Found {len(assets)} forex pairs")
        
        # Hitung sumber aset
        sources = {}
        for asset in assets:
            source = asset.get('source', 'unknown')
            sources[source] = sources.get(source, 0) + 1
        
        print(f"   Sources: {sources}")
        
        # Tampilkan 20 aset pertama
        print("\n   Top 20 assets:")
        for i, asset in enumerate(assets[:20]):
            print(f"   {i+1:3d}. {asset['symbol']} - {asset['name']} (Source: {asset.get('source', 'N/A')})")
    
    print("\n" + "="*60)
    print("✅ 500+ assets test completed")
    print("   NonCryptoAssetsProvider terintegrasi dengan baik")
    print("   Cache 3 hari untuk mengurangi API calls")
    print("   Fallback ke list statis jika provider gagal")
    print("   Multi-threading untuk scanning cepat")
    print("   ✅ ENHANCED ANALYSIS: Menggunakan analyze_enhanced")
    print("   ✅ SIGNAL FILTER: Filter sinyal lebih realistis")
    print("   ✅ PERBAIKAN: Menggunakan get_active_assets() untuk efisiensi scanning")
    print("   ✅ PERBAIKAN: Timeframe='1d' untuk saham_id")
    print("   ✅ PERBAIKAN: Multi-threading untuk scan 25 saham cepat")
    print("   ✅ PERBAIKAN: SHORT diblokir untuk saham_id")

if __name__ == "__main__":
    test_universal_provider()
    test_non_crypto_assets_500()
    
    print("\n" + "="*60)
    print("🎯 CORE.PY READY WITH UNIVERSAL PROVIDER")
    print("🎯 Menggunakan get_trading_data untuk membersihkan data")
    print("🎯 Auto-detect spot/futures dari simbol")
    print("🎯 Leverage auto-detection (1x spot, 5x futures)")
    print("🎯 Provider universal (CCXT untuk crypto, YFinance untuk stocks/forex)")
    print("🎯 SmartChainDataProvider sebagai prioritas utama")
    print("🎯 NON-CRYPTO ASSETS PROVIDER terintegrasi untuk:")
    print("   - Saham Indonesia (.JK) - 500+ aset")
    print("   - US Stocks - 500+ aset") 
    print("   - Forex pairs - 500+ aset")
    print("🎯 Menggunakan cache 3 hari untuk mengurangi API calls")
    print("🎯 Fallback ke list statis jika fetch gagal")
    print("🎯 Filter aset berdasarkan market mode (crypto, saham_id, forex, us_stocks)")
    print("🎯 TANPA BIAS - Semua sinyal (LONG/SHORT) diterima berdasarkan analisis murni")
    print("🎯 SHORT DIIZINKAN untuk crypto (spot & futures) - TANPA DIBLOKIR")
    print("🎯 SHORT TIDAK DIIZINKAN untuk Saham Indonesia (sesuai regulasi IDX)")
    print("🎯 SCALPING MODE dengan konfigurasi khusus:")
    print("   - Timeframe 5m untuk trading cepat")
    print("   - Filter harga ($0.01 - $1000)")
    print("   - Minimal volume $500k")
    print("   - Skip dummy data")
    print("   - Minimal score 4.0")
    print("🎯 PERBAIKAN: Semua kondisi 'if df' diperbaiki dengan 'df is None or df.empty'")
    print("🎯 FIXED: Error 'ambiguous truth value' untuk mode non-crypto (saham_id, forex, us_stocks)")
    print("🎯 PERBAIKAN BARU: Minimum bars berbeda berdasarkan market type:")
    print("   - Saham ID/Forex/US Stocks: 30 bars untuk scanning")
    print("   - Crypto: 50 bars untuk scanning")
    print("   - Scalping: 50 bars (tetap)")
    print("   - Backtest non-crypto: 40 bars")
    print("   - Backtest crypto: 100 bars")
    print("   - Validasi non-crypto: 10 bars")
    print("   - Validasi crypto: 20 bars")
    print("🎯 ENHANCEMENT: Multi-threading untuk scanning 500+ aset")
    print("   - Max workers: 10 thread paralel")
    print("   - Timeout: 30 detik per aset")
    print("   - Processing: 500 aset per scanning cycle")
    print("🎯 PERBAIKAN UTAMA: Menggunakan get_active_assets() untuk efisiensi scanning")
    print("   - Hanya analisa aset aktif dengan volume > 1 juta")
    print("   - Minimal volatilitas 2.5% untuk filter aset liquid")
    print("   - Fallback ke get_assets() jika method tidak tersedia")
    print("🎯 PERBAIKAN BARU: Timeframe='1d' untuk saham_id")
    print("   - Data harian untuk analisis fundamental")
    print("   - Lookback 90 hari (3 bulan) untuk saham")
    print("🎯 PERBAIKAN BARU: Multi-threading untuk scan 25 saham cepat")
    print("   - 5 workers untuk analisis paralel")
    print("   - Timeout 30 detik per saham")
    print("   - Focus pada 25 saham likuid teratas")
    print("🎯 PERBAIKAN BARU: SHORT diblokir untuk saham_id")
    print("   - Sesuai regulasi IDX (tidak mengizinkan short selling)")
    print("   - Semua sinyal SHORT diubah menjadi NEUTRAL")
    print("   - Pesan jelas bahwa SHORT tidak diizinkan")
    print("🎯 **ENHANCED ANALYSIS DAN SIGNAL FILTER**")
    print("   - Menggunakan analyze_enhanced untuk analisis lebih baik")
    print("   - SignalFilter untuk filter sinyal realistis")
    print("   - Confidence level: HIGH/MEDIUM/LOW")
    print("   - Probabilities untuk LONG/SHORT/NEUTRAL")
    print("   - Backward compatibility dengan method lama")
    print("="*60)
