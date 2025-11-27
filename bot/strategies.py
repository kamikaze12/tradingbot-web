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
from scipy.optimize import minimize
import talib
from sklearn.ensemble import IsolationForest
from sklearn.cluster import DBSCAN
import json
from datetime import datetime, timedelta

warnings.filterwarnings('ignore')

# Enhanced logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

try:
    import talib
    TALIB_AVAILABLE = True
except ImportError:
    TALIB_AVAILABLE = False
    logger.warning("TA-LIB not available, using simple calculations")

try:
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import accuracy_score
    from sklearn.preprocessing import StandardScaler
    from sklearn.decomposition import PCA
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False
    logger.warning("scikit-learn not available, skipping ML features")

import yfinance as yf

# =============================================
# BASE STRATEGY CLASS 
# =============================================

class TradingStrategy(ABC):
    """Base class for all trading strategies - ENHANCED WITH ENTRY RANGE"""
    
    def __init__(self, market_type="crypto", atr_multiplier=1.0, entry_range_pct=0.02):
        self.market_type = market_type
        self.atr_multiplier = atr_multiplier
        self.entry_range_pct = entry_range_pct
        
    @abstractmethod
    def analyze(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Analyze market data and return trading signals"""
        pass
    
    def calculate_custom_entry(self, symbol: str, current_price: float, action: str = "LONG") -> Dict[str, Any]:
        """Calculate TP/SL dengan entry range - FIXED VERSION"""
        try:
            # Validasi input yang lebih ketat
            if current_price <= 0 or pd.isna(current_price) or not isinstance(current_price, (int, float)):
                logger.warning(f"Invalid current price for {symbol}: {current_price}")
                current_price = self._estimate_realistic_price(symbol)
                logger.info(f"Using estimated price: {current_price}")
            
            # Pastikan current_price valid
            current_price = float(current_price)
            if current_price <= 0:
                current_price = self._estimate_realistic_price(symbol)
            
            # Calculate ATR based on market type - FIXED CALCULATION
            if self.market_type == "forex":
                atr = current_price * 0.005  # 0.5% untuk forex
            elif self.market_type == "us_stocks":
                atr = current_price * 0.015  # 1.5% untuk saham US
            elif self.market_type == "forex_gold":
                atr = current_price * 0.008  # 0.8% untuk gold
            else:
                atr = current_price * 0.02   # 2% untuk crypto
            
            atr = max(atr, current_price * 0.01)  # Minimum 1%
            
            # ✅ PERBAIKAN: Pastikan entry range selalu terhitung
            entry_range_pct = self.entry_range_pct
            if entry_range_pct <= 0:
                entry_range_pct = 0.02  # Default 2%
            
            # Tentukan entry range berdasarkan aksi
            if action == "LONG":
                # Untuk LONG: entry range di BAWAH current price
                entry_range_low = current_price * (1 - entry_range_pct)
                entry_range_high = current_price * (1 - entry_range_pct * 0.3)
                best_entry = (entry_range_low + entry_range_high) / 2
                
                # TP/SL untuk LONG
                min_move = max(atr * self.atr_multiplier, current_price * 0.01)
                tp1 = best_entry + min_move
                tp2 = best_entry + min_move * 2
                tp3 = best_entry + min_move * 3
                sl = best_entry - min_move
                
            elif action == "SHORT":
                # Untuk SHORT: entry range di ATAS current price  
                entry_range_low = current_price * (1 + entry_range_pct * 0.3)
                entry_range_high = current_price * (1 + entry_range_pct)
                best_entry = (entry_range_low + entry_range_high) / 2
                
                # TP/SL untuk SHORT
                min_move = max(atr * self.atr_multiplier, current_price * 0.01)
                tp1 = best_entry - min_move
                tp2 = best_entry - min_move * 2
                tp3 = best_entry - min_move * 3
                sl = best_entry + min_move
                
            else:  # NEUTRAL
                entry_range_low = current_price * (1 - entry_range_pct * 0.1)
                entry_range_high = current_price * (1 + entry_range_pct * 0.1)
                best_entry = current_price
                tp1 = current_price * 1.01
                tp2 = current_price * 1.02
                tp3 = current_price * 1.03
                sl = current_price * 0.99

            # ✅ VALIDASI FINAL: Pastikan tidak ada nilai 0
            if entry_range_low <= 0 or entry_range_high <= 0 or best_entry <= 0:
                logger.error(f"Invalid entry range calculation for {symbol}, using fallback")
                # Fallback calculation
                if action == "LONG":
                    entry_range_low = current_price * 0.98
                    entry_range_high = current_price * 0.99
                    best_entry = (entry_range_low + entry_range_high) / 2
                    tp1 = best_entry * 1.03
                    tp2 = best_entry * 1.06  
                    tp3 = best_entry * 1.09
                    sl = best_entry * 0.97
                elif action == "SHORT":
                    entry_range_low = current_price * 1.01
                    entry_range_high = current_price * 1.02
                    best_entry = (entry_range_low + entry_range_high) / 2
                    tp1 = best_entry * 0.97
                    tp2 = best_entry * 0.94
                    tp3 = best_entry * 0.91
                    sl = best_entry * 1.03
                else:
                    entry_range_low = current_price * 0.995
                    entry_range_high = current_price * 1.005
                    best_entry = current_price
                    tp1 = current_price * 1.01
                    tp2 = current_price * 1.02
                    tp3 = current_price * 1.03
                    sl = current_price * 0.99

            # Validasi final levels
            if action == "LONG":
                if not (sl < entry_range_low <= entry_range_high < tp1 < tp2 < tp3):
                    logger.warning("Invalid LONG levels in calculate_custom_entry, applying correction")
                    # Reset ke level yang valid
                    entry_range_low = current_price * 0.98
                    entry_range_high = current_price * 0.99
                    best_entry = (entry_range_low + entry_range_high) / 2
                    tp1 = best_entry * 1.03
                    tp2 = best_entry * 1.06
                    tp3 = best_entry * 1.09
                    sl = best_entry * 0.97
                    
            elif action == "SHORT":
                if not (sl > entry_range_high >= entry_range_low > tp1 > tp2 > tp3):
                    logger.warning("Invalid SHORT levels in calculate_custom_entry, applying correction")
                    # Reset ke level yang valid
                    entry_range_low = current_price * 1.01
                    entry_range_high = current_price * 1.02
                    best_entry = (entry_range_low + entry_range_high) / 2
                    tp1 = best_entry * 0.97
                    tp2 = best_entry * 0.94
                    tp3 = best_entry * 0.91
                    sl = best_entry * 1.03

            return {
                'symbol': symbol,
                'action': action,
                'current_price': current_price,
                'entry_range_low': entry_range_low,
                'entry_range_high': entry_range_high,
                'best_entry': best_entry,
                'tp1': tp1,
                'tp2': tp2,
                'tp3': tp3,
                'sl': sl,
                'atr': atr,
                'entry_range_pct': self.entry_range_pct * 100,
                'range_size': (entry_range_high - entry_range_low) / current_price * 100
            }
            
        except Exception as e:
            logger.error(f"Error in calculate_custom_entry: {e}")
            # Fallback calculation yang lebih robust
            fallback_price = max(self._estimate_realistic_price(symbol), 0.01)
            return {
                'symbol': symbol,
                'action': action,
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
                'range_size': 1.0
            }

    def _estimate_realistic_price(self, symbol):
        """Estimate realistic price based on symbol - ENHANCED"""
        # Harga estimasi untuk simbol umum
        price_estimates = {
            'BTC/USDT': 50000.0, 'ETH/USDT': 3000.0, 'BNB/USDT': 500.0,
            'XRP/USDT': 0.5, 'ADA/USDT': 0.4, 'SOL/USDT': 100.0,
            'EUR/USD': 1.08, 'USD/JPY': 150.0, 'GBP/USD': 1.26,
            'XAU/USD': 1950.0, 'XAUUSD': 1950.0, 'GOLD': 1950.0,
            'AAPL': 180.0, 'MSFT': 400.0, 'GOOGL': 150.0, 'AMZN': 170.0, 'TSLA': 200.0,
            'META': 500.0, 'NVDA': 900.0, 'NFLX': 600.0,
            'BTC-USD': 50000.0, 'ETH-USD': 3000.0,
            'EURUSD=X': 1.08, 'USDJPY=X': 150.0, 'XAUUSD=X': 1950.0,
            'BBCA.JK': 9000.0, 'BBRI.JK': 5000.0, 'BMRI.JK': 6000.0,
            'HYPE/USDT': 35.0, 'TON/USDT': 1.5, 'ENA/USDT': 0.3,
            'PINGPONG/USDT': 0.022, 'PLUME/USDT': 0.033, 'ASTER/USDT': 1.12
        }
        
        # Cari pattern dalam simbol
        for pattern, price in price_estimates.items():
            if pattern in symbol:
                return price
        
        # Default berdasarkan tipe market
        if 'USDT' in symbol or '/USDT' in symbol:
            return 10.0
        elif 'USD' in symbol or '=X' in symbol:
            return 1.0
        elif '.JK' in symbol:
            return 5000.0
        elif any(stock in symbol for stock in ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA', 'META', 'NVDA', 'NFLX']):
            return 300.0
        else:
            return 100.0

    def format_signal_output(self, analysis: Dict[str, Any]) -> str:
        """Format output signal dengan entry range yang jelas"""
        
        action = analysis.get('action', 'NEUTRAL')
        symbol = analysis.get('symbol', 'UNKNOWN')
        score = analysis.get('score', 0)
        current_price = analysis.get('current_price', 0)
        confidence = analysis.get('confidence', 0.5) * 100
        
        # Tentukan emoji dan warna berdasarkan aksi
        if action == "LONG":
            emoji = "🟢"
            color_start = "🟢"
        elif action == "SHORT":
            emoji = "🔴" 
            color_start = "🔴"
        else:
            emoji = "⚪"
            color_start = "⚪"
        
        # Format entry range
        entry_low = analysis.get('entry_range_low', current_price)
        entry_high = analysis.get('entry_range_high', current_price)
        best_entry = analysis.get('best_entry', current_price)
        range_pct = analysis.get('entry_range_pct', 2.0)
        
        # Untuk display, gunakan format yang lebih baik
        if action == "LONG":
            entry_display = f"{entry_low:.5f} - {entry_high:.5f}"
            direction = "BELOW current"
        elif action == "SHORT":
            entry_display = f"{entry_low:.5f} - {entry_high:.5f}" 
            direction = "ABOVE current"
        else:
            entry_display = f"{current_price:.5f}"
            direction = "AT current"
        
        # Probabilitas berdasarkan confidence score
        tp1_prob = min(confidence * 0.8, 95)
        tp2_prob = min(confidence * 0.5, 70)
        tp3_prob = min(confidence * 0.2, 40)
        
        output = f"""
{emoji} {symbol} - {action} (Score: {score})
💰 Current: {current_price:.5f} 
🎯 Entry Range: {entry_display} ({direction})
📊 Probabilitas: TP1: {tp1_prob:.1f}% | TP2: {tp2_prob:.1f}% | TP3: {tp3_prob:.1f}%

🎯 Take Profit: 
   TP1: {analysis.get('tp1', 0):.5f}
   TP2: {analysis.get('tp2', 0):.5f}  
   TP3: {analysis.get('tp3', 0):.5f}

🛑 Stop Loss: {analysis.get('sl', 0):.5f}

📈 Analytics:
   Confidence: {confidence:.1f}%
   Range Size: ±{range_pct:.1f}%
   ATR: {analysis.get('atr', 0):.5f}
   RSI: {analysis.get('rsi', 50):.1f}
   Trend: {analysis.get('trend_direction', 'NEUTRAL')}
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

class PatternConfidence(Enum):
    VERY_HIGH = 0.9
    HIGH = 0.7
    MEDIUM = 0.5
    LOW = 0.3
    VERY_LOW = 0.1

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

@dataclass
class RiskAdjustedSignal:
    symbol: str
    action: str
    entry_price: float
    stop_loss: float
    take_profits: List[float]
    position_size: float
    risk_reward_ratio: float
    confidence: float
    market_regime: str
    pattern_confirmations: List[str]
    risk_category: str
    expected_return: float
    max_drawdown: float

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
            if df is None or len(df) < 20:
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
            
            # Butterfly Pattern
            butterfly = self._detect_butterfly_pattern(swing_highs, swing_lows, df)
            if butterfly.detected:
                patterns['butterfly'] = butterfly
            
            # Bat Pattern
            bat = self._detect_bat_pattern(swing_highs, swing_lows, df)
            if bat.detected:
                patterns['bat'] = bat
            
            # Crab Pattern
            crab = self._detect_crab_pattern(swing_highs, swing_lows, df)
            if crab.detected:
                patterns['crab'] = crab
            
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
            
            # Filter significant swings (minimum 1% movement)
            swing_highs = []
            for idx in high_idx:
                if idx >= window and idx < len(highs) - window:
                    left_min = np.min(lows[max(0, idx-window):idx])
                    right_min = np.min(lows[idx:min(len(lows), idx+window)])
                    min_val = min(left_min, right_min)
                    
                    if highs[idx] > min_val * 1.01:  # At least 1% above surrounding lows
                        swing_highs.append((idx, highs[idx]))
            
            swing_lows = []
            for idx in low_idx:
                if idx >= window and idx < len(lows) - window:
                    left_max = np.max(highs[max(0, idx-window):idx])
                    right_max = np.max(highs[idx:min(len(highs), idx+window)])
                    max_val = max(left_max, right_max)
                    
                    if lows[idx] < max_val * 0.99:  # At least 1% below surrounding highs
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
            
            # Mock detection for demonstration
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
    
    def _detect_butterfly_pattern(self, swing_highs, swing_lows, df):
        """Detect Butterfly pattern"""
        return PatternDetection("butterfly", False, "", 0, 0, 0, 0, 0, "")
    
    def _detect_bat_pattern(self, swing_highs, swing_lows, df):
        """Detect Bat pattern"""
        return PatternDetection("bat", False, "", 0, 0, 0, 0, 0, "")
    
    def _detect_crab_pattern(self, swing_highs, swing_lows, df):
        """Detect Crab pattern"""
        return PatternDetection("crab", False, "", 0, 0, 0, 0, 0, "")
    
    def _detect_chart_patterns_advanced(self, df: pd.DataFrame) -> Dict[str, PatternDetection]:
        """Advanced chart pattern detection"""
        patterns = {}
        
        try:
            if df is None or len(df) < 20:
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
            
            # Triangle Patterns
            triangle_patterns = self._detect_triangle_patterns_advanced(df)
            patterns.update(triangle_patterns)
            
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
            
            # Find potential shoulders and head
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
            peak2 = np.max(highs[peak1_idx:]) if peak1_idx < len(highs) else 0
            
            trough1_idx = len(lows) // 3
            trough2_idx = 2 * len(lows) // 3
            trough1 = np.min(lows[:trough1_idx]) if trough1_idx > 0 else 0
            trough2 = np.min(lows[trough1_idx:]) if trough1_idx < len(lows) else 0
            
            # Double Top detection
            if (peak1 > 0 and peak2 > 0 and 
                abs(peak1 - peak2) / peak1 < 0.015 and
                current_price < (peak1 + peak2) / 2):
                
                confidence = 0.7
                entry = current_price
                target = current_price * 0.94
                stop_loss = max(peak1, peak2) * 1.01
                rr_ratio = abs(target - entry) / abs(entry - stop_loss) if abs(entry - stop_loss) > 0 else 1.0
                
                return PatternDetection(
                    "double_top", True, "BEARISH", confidence,
                    entry, target, stop_loss, rr_ratio, "1D"
                )
            
            # Double Bottom detection
            if (trough1 > 0 and trough2 > 0 and 
                abs(trough1 - trough2) / trough1 < 0.015 and
                current_price > (trough1 + trough2) / 2):
                
                confidence = 0.7
                entry = current_price
                target = current_price * 1.06
                stop_loss = min(trough1, trough2) * 0.99
                rr_ratio = abs(target - entry) / abs(entry - stop_loss) if abs(entry - stop_loss) > 0 else 1.0
                
                return PatternDetection(
                    "double_bottom", True, "BULLISH", confidence,
                    entry, target, stop_loss, rr_ratio, "1D"
                )
            
        except Exception as e:
            logger.error(f"Double Top/Bottom detection error: {e}")
        
        return PatternDetection("double_top_bottom", False, "", 0, 0, 0, 0, 0, "")
    
    def _detect_triangle_patterns_advanced(self, df: pd.DataFrame) -> Dict[str, PatternDetection]:
        """Advanced triangle pattern detection"""
        patterns = {}
        return patterns
    
    def _detect_candlestick_patterns(self, df: pd.DataFrame) -> Dict[str, PatternDetection]:
        """Detect Japanese candlestick patterns"""
        patterns = {}
        
        try:
            if not TALIB_AVAILABLE or len(df) < 10:
                return patterns
            
            current_price = df['close'].iloc[-1]
            if current_price <= 0:
                return patterns
            
            open_prices = df['open'].values
            high_prices = df['high'].values
            low_prices = df['low'].values
            close_prices = df['close'].values
            
            patterns_to_check = [
                ('CDLENGULFING', 'engulfing'),
                ('CDLHAMMER', 'hammer'),
                ('CDLSHOOTINGSTAR', 'shooting_star'),
                ('CDLDOJI', 'doji'),
                ('CDLMORNINGSTAR', 'morning_star'),
                ('CDLEVENINGSTAR', 'evening_star')
            ]
            
            for talib_pattern, pattern_name in patterns_to_check:
                try:
                    pattern_func = getattr(talib, talib_pattern)
                    result = pattern_func(open_prices, high_prices, low_prices, close_prices)
                    
                    if result[-1] != 0:
                        direction = "BULLISH" if result[-1] > 0 else "BEARISH"
                        
                        if direction == "BULLISH":
                            target = current_price * 1.03
                            stop_loss = current_price * 0.98
                        else:
                            target = current_price * 0.97
                            stop_loss = current_price * 1.02
                        
                        rr_ratio = abs(target - current_price) / abs(current_price - stop_loss) if abs(current_price - stop_loss) > 0 else 1.0
                        confidence = 0.6
                        
                        patterns[pattern_name] = PatternDetection(
                            pattern_name, True, direction, confidence,
                            current_price, target, stop_loss, rr_ratio, "1D"
                        )
                        
                except Exception as e:
                    logger.warning(f"Error detecting {pattern_name}: {e}")
                    continue
            
        except Exception as e:
            logger.error(f"Candlestick pattern detection error: {e}")
        
        return patterns
    
    def _detect_volume_patterns(self, df: pd.DataFrame) -> Dict[str, PatternDetection]:
        """Detect volume-based patterns"""
        patterns = {}
        
        try:
            if 'volume' not in df.columns:
                return patterns
            
            volumes = df['volume'].values
            prices = df['close'].values
            
            if len(volumes) < 20:
                return patterns
            
            current_price = prices[-1]
            if current_price <= 0:
                return patterns
            
            volume_ma = np.mean(volumes[-20:])
            current_volume = volumes[-1]
            
            if current_volume > volume_ma * 2:
                price_change = (prices[-1] - prices[-2]) / prices[-2] if prices[-2] > 0 else 0
                
                if abs(price_change) > 0.01:
                    direction = "BULLISH" if price_change > 0 else "BEARISH"
                    target = current_price * (1 + price_change * 2)
                    stop_loss = current_price * (1 - price_change)
                    rr_ratio = abs(target - current_price) / abs(current_price - stop_loss) if abs(current_price - stop_loss) > 0 else 1.0
                    
                    patterns['volume_spike'] = PatternDetection(
                        "volume_spike", True, direction, 0.65,
                        current_price, target, stop_loss, rr_ratio, "1D"
                    )
            
        except Exception as e:
            logger.error(f"Volume pattern detection error: {e}")
        
        return patterns
    
    def _detect_trend_patterns(self, df: pd.DataFrame) -> Dict[str, PatternDetection]:
        """Detect trend-based patterns"""
        patterns = {}
        return patterns

# =============================================
# ADVANCED MARKET REGIME DETECTION
# =============================================

class MarketRegimeDetector:
    """Advanced market regime detection"""
    
    def __init__(self):
        self.regime_history = []
        self.volatility_lookback = 20
        
    def analyze_market_regime(self, df: pd.DataFrame, symbol: str = None) -> MarketAnalysis:
        """Comprehensive market regime analysis"""
        try:
            if df is None or len(df) < 50:
                return self._get_default_analysis()
            
            current_price = df['close'].iloc[-1]
            if current_price <= 0:
                logger.warning("Invalid current price in regime analysis")
                return self._get_default_analysis()
            
            # Trend Analysis
            trend_strength, trend_direction = self._analyze_trend_strength(df)
            
            # Volatility Analysis
            volatility_regime = self._analyze_volatility_regime(df)
            
            # Support/Resistance Levels
            support_levels, resistance_levels = self._calculate_support_resistance(df)
            key_levels = self._identify_key_levels(df)
            
            # Volume Analysis
            volume_profile = self._analyze_volume_profile(df)
            
            # Market Sentiment
            market_sentiment = self._analyze_market_sentiment(df)
            
            # Determine overall regime
            regime = self._determine_overall_regime(
                trend_strength, trend_direction, volatility_regime, market_sentiment
            )
            
            analysis = MarketAnalysis(
                regime=regime,
                trend_strength=trend_strength,
                volatility_regime=volatility_regime,
                support_levels=support_levels,
                resistance_levels=resistance_levels,
                key_levels=key_levels,
                volume_profile=volume_profile,
                market_sentiment=market_sentiment
            )
            
            self.regime_history.append(analysis)
            if len(self.regime_history) > 100:
                self.regime_history.pop(0)
            
            return analysis
            
        except Exception as e:
            logger.error(f"Market regime analysis error: {e}")
            return self._get_default_analysis()
    
    def _analyze_trend_strength(self, df: pd.DataFrame) -> Tuple[float, str]:
        """Analyze trend strength and direction"""
        try:
            prices = df['close'].values
            
            if len(prices) < 20:
                return 0.0, "NEUTRAL"
            
            if (prices <= 0).any():
                return 0.0, "NEUTRAL"
            
            # ADX for trend strength
            if TALIB_AVAILABLE:
                adx = talib.ADX(df['high'], df['low'], df['close'], timeperiod=14)
                current_adx = adx.iloc[-1] if not pd.isna(adx.iloc[-1]) else 0
            else:
                current_adx = self._calculate_simple_adx(df)
            
            # Moving average alignment
            sma_20 = np.mean(prices[-20:])
            sma_50 = np.mean(prices[-min(50, len(prices)):])
            
            price_vs_sma20 = (prices[-1] - sma_20) / sma_20 if sma_20 > 0 else 0
            price_vs_sma50 = (prices[-1] - sma_50) / sma_50 if sma_50 > 0 else 0
            
            if price_vs_sma20 > 0.02 and price_vs_sma50 > 0.02:
                direction = "BULLISH"
            elif price_vs_sma20 < -0.02 and price_vs_sma50 < -0.02:
                direction = "BEARISH"
            else:
                direction = "NEUTRAL"
            
            trend_strength = min(current_adx / 50.0, 1.0)
            
            return trend_strength, direction
            
        except Exception as e:
            logger.error(f"Trend analysis error: {e}")
            return 0.0, "NEUTRAL"
    
    def _calculate_simple_adx(self, df: pd.DataFrame) -> float:
        """Calculate simplified ADX"""
        try:
            highs = df['high'].values
            lows = df['low'].values
            closes = df['close'].values
            
            if len(highs) < 14:
                return 0.0
            
            if (highs <= 0).any() or (lows <= 0).any() or (closes <= 0).any():
                return 0.0
            
            tr = np.zeros(len(highs))
            for i in range(1, len(highs)):
                tr1 = highs[i] - lows[i]
                tr2 = abs(highs[i] - closes[i-1])
                tr3 = abs(lows[i] - closes[i-1])
                tr[i] = max(tr1, tr2, tr3)
            
            plus_dm = np.zeros(len(highs))
            minus_dm = np.zeros(len(highs))
            
            for i in range(1, len(highs)):
                up_move = highs[i] - highs[i-1]
                down_move = lows[i-1] - lows[i]
                
                if up_move > down_move and up_move > 0:
                    plus_dm[i] = up_move
                if down_move > up_move and down_move > 0:
                    minus_dm[i] = down_move
            
            tr_smooth = np.mean(tr[-14:])
            plus_dm_smooth = np.mean(plus_dm[-14:])
            minus_dm_smooth = np.mean(minus_dm[-14:])
            
            if tr_smooth > 0:
                plus_di = 100 * plus_dm_smooth / tr_smooth
                minus_di = 100 * minus_dm_smooth / tr_smooth
                dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di) if (plus_di + minus_di) > 0 else 0
            else:
                dx = 0
            
            return dx
            
        except Exception as e:
            logger.error(f"Simple ADX calculation error: {e}")
            return 0.0
    
    def _analyze_volatility_regime(self, df: pd.DataFrame) -> str:
        """Analyze volatility regime"""
        try:
            prices = df['close'].values
            
            if len(prices) < 20:
                return "NORMAL"
            
            if (prices <= 0).any():
                return "NORMAL"
            
            returns = np.diff(prices) / prices[:-1]
            volatility = np.std(returns) * np.sqrt(252)
            
            if len(returns) > 50:
                historical_vol = np.std(returns[-50:]) * np.sqrt(252)
            else:
                historical_vol = volatility
            
            vol_ratio = volatility / historical_vol if historical_vol > 0 else 1.0
            
            if vol_ratio > 1.5:
                return "HIGH_VOLATILITY"
            elif vol_ratio < 0.7:
                return "LOW_VOLATILITY"
            else:
                return "NORMAL_VOLATILITY"
                
        except Exception as e:
            logger.error(f"Volatility analysis error: {e}")
            return "NORMAL_VOLATILITY"
    
    def _calculate_support_resistance(self, df: pd.DataFrame) -> Tuple[List[float], List[float]]:
        """Calculate support and resistance levels"""
        try:
            if len(df) < 20:
                return [], []
            
            current_price = df['close'].iloc[-1]
            if current_price <= 0:
                return [], []
            
            highs = df['high'].tail(50).values
            lows = df['low'].tail(50).values
            
            price_levels = np.concatenate([highs, lows])
            
            if len(price_levels) < 5:
                return [], []
            
            from sklearn.cluster import KMeans
            
            n_clusters = min(5, len(price_levels) // 5)
            if n_clusters < 2:
                return [], []
            
            kmeans = KMeans(n_clusters=n_clusters, random_state=42)
            clusters = kmeans.fit_predict(price_levels.reshape(-1, 1))
            
            levels = kmeans.cluster_centers_.flatten()
            
            support_levels = [level for level in levels if level < current_price]
            resistance_levels = [level for level in levels if level > current_price]
            
            support_levels = sorted(support_levels, reverse=True)[:3]
            resistance_levels = sorted(resistance_levels)[:3]
            
            return support_levels, resistance_levels
            
        except Exception as e:
            logger.error(f"Support/resistance calculation error: {e}")
            return [], []
    
    def _identify_key_levels(self, df: pd.DataFrame) -> List[float]:
        """Identify key psychological and technical levels"""
        try:
            current_price = df['close'].iloc[-1]
            if current_price <= 0:
                return []
            
            key_levels = []
            
            round_level = round(current_price / 10) * 10
            key_levels.append(round_level)
            
            recent_high = df['high'].tail(20).max()
            recent_low = df['low'].tail(20).min()
            key_levels.extend([recent_high, recent_low])
            
            if len(df) >= 50:
                ma_20 = df['close'].tail(20).mean()
                ma_50 = df['close'].tail(50).mean()
                key_levels.extend([ma_20, ma_50])
            
            return sorted(list(set(key_levels)))
            
        except Exception as e:
            logger.error(f"Key level identification error: {e}")
            return []
    
    def _analyze_volume_profile(self, df: pd.DataFrame) -> Dict[str, float]:
        """Analyze volume profile and anomalies"""
        try:
            if 'volume' not in df.columns:
                return {}
            
            volumes = df['volume'].values
            
            if len(volumes) < 20:
                return {}
            
            volume_profile = {
                'current_volume': volumes[-1],
                'volume_ma_20': np.mean(volumes[-20:]),
                'volume_ratio': volumes[-1] / np.mean(volumes[-20:]) if np.mean(volumes[-20:]) > 0 else 1.0,
                'volume_trend': self._calculate_volume_trend(volumes),
                'volume_volatility': np.std(volumes[-20:]) / np.mean(volumes[-20:]) if np.mean(volumes[-20:]) > 0 else 0.0
            }
            
            return volume_profile
            
        except Exception as e:
            logger.error(f"Volume profile analysis error: {e}")
            return {}
    
    def _calculate_volume_trend(self, volumes: np.ndarray) -> float:
        """Calculate volume trend strength"""
        if len(volumes) < 10:
            return 0.0
        
        x = np.arange(len(volumes))
        slope, _, r_value, _, _ = stats.linregress(x, volumes)
        
        normalized_slope = slope / np.mean(volumes) if np.mean(volumes) > 0 else 0
        trend_strength = normalized_slope * (r_value ** 2)
        
        return trend_strength
    
    def _analyze_market_sentiment(self, df: pd.DataFrame) -> str:
        """Analyze overall market sentiment"""
        try:
            prices = df['close'].values
            
            if len(prices) < 20:
                return "NEUTRAL"
            
            if (prices <= 0).any():
                return "NEUTRAL"
            
            rsi = self._calculate_rsi(prices, 14)
            price_position = (prices[-1] - np.min(prices[-20:])) / (np.max(prices[-20:]) - np.min(prices[-20:])) if (np.max(prices[-20:]) - np.min(prices[-20:])) > 0 else 0.5
            
            sentiment_score = 0
            
            if rsi > 70:
                sentiment_score -= 2
            elif rsi < 30:
                sentiment_score += 2
            elif rsi > 60:
                sentiment_score -= 1
            elif rsi < 40:
                sentiment_score += 1
            
            if price_position > 0.7:
                sentiment_score -= 1
            elif price_position < 0.3:
                sentiment_score += 1
            
            if sentiment_score >= 2:
                return "BULLISH"
            elif sentiment_score <= -2:
                return "BEARISH"
            else:
                return "NEUTRAL"
                
        except Exception as e:
            logger.error(f"Market sentiment analysis error: {e}")
            return "NEUTRAL"
    
    def _calculate_rsi(self, prices: np.ndarray, period: int = 14) -> float:
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
    
    def _determine_overall_regime(self, trend_strength: float, trend_direction: str, 
                                volatility_regime: str, market_sentiment: str) -> MarketRegime:
        """Determine overall market regime"""
        try:
            if trend_strength > 0.6:
                if trend_direction == "BULLISH":
                    return MarketRegime.BULL_TREND
                elif trend_direction == "BEARISH":
                    return MarketRegime.BEAR_TREND
            
            if volatility_regime == "HIGH_VOLATILITY":
                return MarketRegime.HIGH_VOLATILITY
            elif volatility_regime == "LOW_VOLATILITY":
                return MarketRegime.LOW_VOLATILITY
            
            return MarketRegime.RANGING
            
        except Exception as e:
            logger.error(f"Regime determination error: {e}")
            return MarketRegime.UNKNOWN
    
    def _get_default_analysis(self) -> MarketAnalysis:
        """Get default market analysis"""
        return MarketAnalysis(
            regime=MarketRegime.UNKNOWN,
            trend_strength=0.0,
            volatility_regime="NORMAL",
            support_levels=[],
            resistance_levels=[],
            key_levels=[],
            volume_profile={},
            market_sentiment="NEUTRAL"
        )

# =============================================
# ENHANCED TECHNICAL ANALYSIS STRATEGY - FIXED WITH ENTRY RANGE
# =============================================

class EnhancedTechnicalAnalysisStrategy(TradingStrategy):
    """Enhanced technical analysis strategy dengan ENTRY RANGE support"""
    
    def __init__(self, market_type="crypto", atr_multiplier=1.0, entry_range_pct=0.02):
        super().__init__(market_type, atr_multiplier, entry_range_pct)
        
        self.pattern_detector = AdvancedPatternDetector()
        self.regime_detector = MarketRegimeDetector()
        self.risk_engine = DynamicRiskEngine()
        
        self.set_market_parameters()
        self.analysis_history = []
        self.pattern_performance = {}
        
        logger.info(f"Enhanced Technical Analysis Strategy initialized for {market_type}")
    
    def set_market_parameters(self):
        """Set optimized parameters untuk different market types"""
        market_params = {
            "crypto": {
                'rsi_oversold': 25, 'rsi_overbought': 75, 'volume_threshold': 1.3,
                'adx_trend_threshold': 20, 'pattern_weight': 2.0, 'trend_weight': 2.0,
                'volatility_threshold': 0.02, 'atr_period': 14, 'risk_multiplier': 1.2
            },
            "forex": {
                'rsi_oversold': 30, 'rsi_overbought': 70, 'volume_threshold': 1.1,
                'adx_trend_threshold': 25, 'pattern_weight': 1.0, 'trend_weight': 1.0,
                'volatility_threshold': 0.005, 'atr_period': 20, 'risk_multiplier': 0.8
            },
            "us_stocks": {
                'rsi_oversold': 30, 'rsi_overbought': 70, 'volume_threshold': 1.2,
                'adx_trend_threshold': 22, 'pattern_weight': 1.3, 'trend_weight': 1.3,
                'volatility_threshold': 0.015, 'atr_period': 14, 'risk_multiplier': 1.0
            },
            "forex_gold": {
                'rsi_oversold': 25, 'rsi_overbought': 75, 'volume_threshold': 1.3,
                'adx_trend_threshold': 20, 'pattern_weight': 2.0, 'trend_weight': 2.0,
                'volatility_threshold': 0.008, 'atr_period': 14, 'risk_multiplier': 1.1
            }
        }
        
        params = market_params.get(self.market_type, market_params["crypto"])
        for key, value in params.items():
            setattr(self, key, value)

    def analyze(self, df: pd.DataFrame, symbol: str = None) -> Dict[str, Any]:
        """Enhanced analysis dengan entry range support"""
        
        if df is None or len(df) < 20:
            logger.error("Insufficient or None data for analysis")
            return self._get_default_analysis(symbol)
        
        try:
            required_columns = ['open', 'high', 'low', 'close']
            for col in required_columns:
                if col not in df.columns:
                    logger.error(f"Missing required column: {col}")
                    return self._get_default_analysis(symbol)
            
            current_price = self._get_valid_current_price(df)
            
            if current_price <= 0 or pd.isna(current_price):
                logger.error(f"All price data invalid, using estimated price")
                estimated_price = self._estimate_realistic_price(symbol or "UNKNOWN")
                return self._get_default_analysis_with_price(estimated_price, symbol)
            
            logger.info(f"Analysis starting with valid price: {current_price}")
            
            market_analysis = self.regime_detector.analyze_market_regime(df, symbol)
            patterns = self.pattern_detector.detect_comprehensive_patterns(df, symbol)
            technical_indicators = self._calculate_enhanced_indicators(df)
            volume_analysis = self._analyze_volume_advanced(df)
            trend_analysis = self._analyze_trend_advanced(df)
            
            combined_analysis = self._combine_analyses(
                market_analysis, patterns, technical_indicators, 
                volume_analysis, trend_analysis, current_price, symbol
            )
            
            risk_adjusted_signal = self._apply_risk_adjustment(combined_analysis, df, symbol)
            final_signal = self._final_validation(risk_adjusted_signal, symbol)
            
            self._store_analysis_history(final_signal)
            
            logger.info(f"Analysis completed - Entry Range: {final_signal['entry_range_low']:.5f}-{final_signal['entry_range_high']:.5f}")
            
            return final_signal
            
        except Exception as e:
            logger.error(f"Enhanced analysis error: {e}")
            return self._get_default_analysis(symbol)

    def _combine_analyses(self, market_analysis: MarketAnalysis, patterns: Dict[str, PatternDetection],
                         technical_indicators: Dict[str, float], volume_analysis: Dict[str, Any],
                         trend_analysis: Dict[str, Any], current_price: float, symbol: str = None) -> Dict[str, Any]:
        """Combine semua analyses dengan ENTRY RANGE support - FIXED BALANCE"""
        
        if current_price <= 0 or pd.isna(current_price):
            logger.error(f"Invalid current_price in combine_analyses: {current_price}")
            current_price = self._estimate_realistic_price(symbol or "UNKNOWN")
        
        # Base scores
        base_score = 0
        action = "NEUTRAL"
        
        # ✅ PERBAIKAN: Balance scoring antara LONG dan SHORT
        # Technical indicators contribution - MORE BALANCED
        rsi = technical_indicators.get('rsi_14', 50)
        
        # ✅ FIX: Berikan poin untuk kondisi oversold (LONG opportunity)
        if rsi < self.rsi_oversold:
            base_score += 3  # Increased from 2
        elif rsi > self.rsi_overbought:
            base_score -= 3  # Decreased from -3
        
        # Volume contribution - MORE BALANCED
        volume_score = volume_analysis.get('volume_score', 0)
        volume_ratio = volume_analysis.get('volume_ratio', 1.0)
        
        # ✅ FIX: Berikan poin positif untuk volume tinggi dengan trend bullish
        if volume_ratio > 1.5 and trend_analysis.get('trend_direction') == 'BULLISH':
            volume_score += 2
        elif volume_ratio > 1.2 and trend_analysis.get('trend_direction') == 'BULLISH':
            volume_score += 1
        elif volume_ratio > 1.5 and trend_analysis.get('trend_direction') == 'BEARISH':
            volume_score -= 2
        elif volume_ratio > 1.2 and trend_analysis.get('trend_direction') == 'BEARISH':
            volume_score -= 1
            
        base_score += volume_score
        
        # Trend contribution - MORE BALANCED
        trend_score = trend_analysis.get('trend_score', 0)
        trend_direction = trend_analysis.get('trend_direction', 'NEUTRAL')
        trend_strength = trend_analysis.get('trend_strength', 0.0)
        
        # ✅ FIX: Berikan poin yang seimbang untuk trend bullish dan bearish
        if trend_direction == 'BULLISH' and trend_strength > 0.6:
            trend_score += 3  # Increased from +2
        elif trend_direction == 'BULLISH':
            trend_score += 2
        elif trend_direction == 'BEARISH' and trend_strength > 0.6:
            trend_score -= 3  # Same as bearish
        elif trend_direction == 'BEARISH':
            trend_score -= 2
        
        base_score += trend_score
        
        # Pattern contribution - MORE BALANCED
        pattern_score = 0
        pattern_confirmations = []
        
        for pattern_name, pattern in patterns.items():
            if pattern.detected:
                if pattern.direction == "BULLISH":
                    pattern_score += pattern.confidence * 3  # Increased from 2
                    pattern_confirmations.append(f"{pattern_name}_BULLISH")
                elif pattern.direction == "BEARISH":
                    pattern_score -= pattern.confidence * 3  # Same as bearish
                    pattern_confirmations.append(f"{pattern_name}_BEARISH")
        
        base_score += pattern_score
        
        # Momentum indicators - MORE BALANCED
        momentum_5 = technical_indicators.get('momentum_5', 0)
        momentum_10 = technical_indicators.get('momentum_10', 0)
        
        # ✅ FIX: Berikan poin untuk momentum positif
        if momentum_5 > 2 and momentum_10 > 3:
            base_score += 2
        elif momentum_5 > 0 and momentum_10 > 0:
            base_score += 1
        elif momentum_5 < -2 and momentum_10 < -3:
            base_score -= 2
        elif momentum_5 < 0 and momentum_10 < 0:
            base_score -= 1
        
        # MACD - MORE BALANCED
        macd_line = technical_indicators.get('macd_line', 0)
        macd_signal = technical_indicators.get('macd_signal', 0)
        
        if macd_line > 0 and macd_signal > 0 and macd_line > macd_signal:
            base_score += 2
        elif macd_line < 0 and macd_signal < 0 and macd_line < macd_signal:
            base_score -= 2
        
        # Bollinger Bands position - MORE BALANCED
        bb_position = technical_indicators.get('bb_position', 0.5)
        if bb_position < 0.2:  # Near lower band - oversold
            base_score += 2
        elif bb_position > 0.8:  # Near upper band - overbought
            base_score -= 2
        elif bb_position < 0.3:  # Below middle - potential long
            base_score += 1
        elif bb_position > 0.7:  # Above middle - potential short
            base_score -= 1
        
        # ✅ FIX: Threshold yang lebih seimbang
        action_threshold = 3  # Increased from 2
        short_threshold = -3  # Increased from -1.5
        
        if base_score >= action_threshold:
            action = "LONG"
        elif base_score <= short_threshold:
            action = "SHORT"
        else:
            action = "NEUTRAL"
        
        # **ENTRY RANGE CALCULATION**
        atr = technical_indicators.get('atr', current_price * 0.02)
        if atr <= 0:
            atr = current_price * 0.02
        
        # Gunakan calculate_custom_entry untuk konsistensi
        entry_calculation = self.calculate_custom_entry(symbol or "UNKNOWN", current_price, action)
        
        # ✅ PERBAIKAN: Pastikan entry range tidak 0
        if (entry_calculation['entry_range_low'] <= 0 or 
            entry_calculation['entry_range_high'] <= 0 or 
            entry_calculation['best_entry'] <= 0):
            
            logger.warning(f"Invalid entry range for {symbol}, recalculating...")
            if action == "LONG":
                entry_calculation['entry_range_low'] = current_price * 0.98
                entry_calculation['entry_range_high'] = current_price * 0.99
                entry_calculation['best_entry'] = (entry_calculation['entry_range_low'] + entry_calculation['entry_range_high']) / 2
            elif action == "SHORT":
                entry_calculation['entry_range_low'] = current_price * 1.01
                entry_calculation['entry_range_high'] = current_price * 1.02
                entry_calculation['best_entry'] = (entry_calculation['entry_range_low'] + entry_calculation['entry_range_high']) / 2
            else:
                entry_calculation['entry_range_low'] = current_price * 0.995
                entry_calculation['entry_range_high'] = current_price * 1.005
                entry_calculation['best_entry'] = current_price
            
            entry_calculation['range_size'] = (entry_calculation['entry_range_high'] - entry_calculation['entry_range_low']) / current_price * 100
        
        return {
            'action': action,
            'entry_range_low': entry_calculation['entry_range_low'],
            'entry_range_high': entry_calculation['entry_range_high'],
            'best_entry': entry_calculation['best_entry'],
            'tp1': entry_calculation['tp1'],
            'tp2': entry_calculation['tp2'],
            'tp3': entry_calculation['tp3'],
            'sl': entry_calculation['sl'],
            'current_price': float(current_price),
            'score': int(base_score),
            'base_score': int(base_score),
            'rsi': float(rsi),
            'volume_ratio': volume_analysis.get('volume_ratio', 1.0),
            'atr': float(atr),
            'market_regime': market_analysis.regime.value,
            'trend_strength': trend_analysis.get('trend_strength', 0.0),
            'trend_direction': trend_analysis.get('trend_direction', 'NEUTRAL'),
            'pattern_confirmations': pattern_confirmations,
            'pattern_count': len(patterns),
            'support_levels': market_analysis.support_levels,
            'resistance_levels': market_analysis.resistance_levels,
            'volatility': technical_indicators.get('volatility', 0.02),
            'risk_category': self._determine_risk_category(technical_indicators.get('volatility', 0.02)),
            'confidence': min(abs(base_score) / 10.0, 1.0),
            'momentum_5': momentum_5,
            'momentum_10': momentum_10,
            'macd_line': macd_line,
            'macd_signal': macd_signal,
            'bb_position': bb_position,
            'symbol': symbol,
            'entry_range_pct': self.entry_range_pct * 100,
            'range_size': entry_calculation['range_size']
        }

    def _final_validation(self, analysis: Dict[str, Any], symbol: str = None) -> Dict[str, Any]:
        """Final validation dengan entry range support"""
        try:
            action = analysis.get('action', 'NEUTRAL')
            entry_low = analysis.get('entry_range_low', 0)
            entry_high = analysis.get('entry_range_high', 0)
            current_price = analysis.get('current_price', 0)
            
            # Validasi entry range
            if entry_low <= 0 or entry_high <= 0:
                logger.error(f"Invalid entry range: {entry_low}-{entry_high}")
                base_price = analysis.get('current_price', self._estimate_realistic_price(symbol or "UNKNOWN"))
                if base_price <= 0:
                    base_price = self._estimate_realistic_price(symbol or "UNKNOWN")
                
                if action == "LONG":
                    entry_low = base_price * 0.98
                    entry_high = base_price * 0.99
                elif action == "SHORT":
                    entry_low = base_price * 1.01
                    entry_high = base_price * 1.02
                else:
                    entry_low = base_price * 0.995
                    entry_high = base_price * 1.005
                
                analysis['entry_range_low'] = entry_low
                analysis['entry_range_high'] = entry_high
                analysis['best_entry'] = (entry_low + entry_high) / 2
                analysis['range_size'] = (entry_high - entry_low) / current_price * 100
            
            # Validasi konsistensi level dengan aksi
            if action == 'LONG':
                if not (analysis['sl'] < entry_low <= entry_high < analysis['tp1'] < analysis['tp2'] < analysis['tp3']):
                    logger.error("LONG levels invalid after final validation, forcing correction")
                    analysis['tp1'] = analysis['best_entry'] * 1.03
                    analysis['tp2'] = analysis['best_entry'] * 1.06
                    analysis['tp3'] = analysis['best_entry'] * 1.09
                    analysis['sl'] = analysis['best_entry'] * 0.97
                    
            elif action == 'SHORT':
                if not (analysis['sl'] > entry_high >= entry_low > analysis['tp1'] > analysis['tp2'] > analysis['tp3']):
                    logger.error("SHORT levels invalid after final validation, forcing correction")
                    analysis['tp1'] = analysis['best_entry'] * 0.97
                    analysis['tp2'] = analysis['best_entry'] * 0.94
                    analysis['tp3'] = analysis['best_entry'] * 0.91
                    analysis['sl'] = analysis['best_entry'] * 1.03
            
            return analysis
            
        except Exception as e:
            logger.error(f"Final validation error: {e}")
            return self._get_default_analysis(symbol)

    def _get_valid_current_price(self, df: pd.DataFrame) -> float:
        """Get valid current price dengan multiple fallback strategies"""
        try:
            current_close = df['close'].iloc[-1]
            if current_close > 0 and not pd.isna(current_close):
                return current_close
            
            valid_closes = df[df['close'] > 0]['close']
            if len(valid_closes) > 0:
                last_valid = valid_closes.iloc[-1]
                logger.warning(f"Using last valid close price: {last_valid}")
                return last_valid
            
            for price_type in ['open', 'high', 'low']:
                if price_type in df.columns:
                    price_val = df[price_type].iloc[-1]
                    if price_val > 0 and not pd.isna(price_val):
                        logger.warning(f"Using {price_type} price: {price_val}")
                        return price_val
            
            recent_prices = df['close'].tail(10)
            valid_recent = recent_prices[recent_prices > 0]
            if len(valid_recent) > 0:
                avg_price = valid_recent.mean()
                logger.warning(f"Using average of recent prices: {avg_price}")
                return avg_price
            
            min_price = 0.0001 if self.market_type == "crypto" else 0.01
            logger.warning(f"All prices invalid, using minimum: {min_price}")
            return min_price
            
        except Exception as e:
            logger.error(f"Error getting valid price: {e}")
            return self._estimate_realistic_price("UNKNOWN")

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
            indicators['rsi_21'] = self._calculate_rsi(prices, 21)
            
            # Moving Averages
            indicators['sma_20'] = np.mean(prices[-20:])
            indicators['sma_50'] = np.mean(prices[-min(50, len(prices)):])
            indicators['ema_12'] = self._calculate_ema(prices, 12)
            indicators['ema_26'] = self._calculate_ema(prices, 26)
            
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
            
            # Stochastic
            stoch_k, stoch_d = self._calculate_stochastic(highs, lows, prices)
            indicators['stoch_k'] = stoch_k
            indicators['stoch_d'] = stoch_d
            
            # ATR
            indicators['atr'] = self._calculate_atr(df)
            
            # Volatility
            returns = np.diff(prices) / prices[:-1]
            indicators['volatility'] = np.std(returns) * np.sqrt(252) if len(returns) > 1 else 0.02
            
            # Momentum
            indicators['momentum_5'] = (prices[-1] / prices[-5] - 1) * 100 if len(prices) >= 5 and prices[-5] > 0 else 0
            indicators['momentum_10'] = (prices[-1] / prices[-10] - 1) * 100 if len(prices) >= 10 and prices[-10] > 0 else 0
            
            return indicators
            
        except Exception as e:
            logger.error(f"Enhanced indicators calculation error: {e}")
            return self._get_default_indicators(prices[-1] if 'prices' in locals() and len(prices) > 0 else 1.0)
    
    def _get_default_indicators(self, current_price: float) -> Dict[str, float]:
        """Get default indicators when calculation fails"""
        return {
            'rsi_14': 50.0, 'rsi_21': 50.0,
            'sma_20': current_price, 'sma_50': current_price,
            'ema_12': current_price, 'ema_26': current_price,
            'macd_line': 0, 'macd_signal': 0, 'macd_histogram': 0,
            'bb_upper': current_price * 1.02, 'bb_lower': current_price * 0.98, 'bb_middle': current_price,
            'bb_position': 0.5, 'stoch_k': 50.0, 'stoch_d': 50.0,
            'atr': current_price * 0.02, 'volatility': 0.02,
            'momentum_5': 0, 'momentum_10': 0
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
    
    def _calculate_ema(self, prices: np.ndarray, period: int) -> float:
        """Calculate EMA"""
        if len(prices) < period:
            return np.mean(prices) if len(prices) > 0 else 1.0
        
        weights = np.exp(np.linspace(-1., 0., period))
        weights /= weights.sum()
        
        return np.convolve(prices[-period:], weights, mode='valid')[-1]
    
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
    
    def _calculate_stochastic(self, highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, 
                            k_period: int = 14, d_period: int = 3) -> Tuple[float, float]:
        """Calculate Stochastic Oscillator"""
        if len(highs) < k_period or len(lows) < k_period or len(closes) < k_period:
            return 50.0, 50.0
        
        highest_high = np.max(highs[-k_period:])
        lowest_low = np.min(lows[-k_period:])
        
        if highest_high == lowest_low:
            return 50.0, 50.0
        
        k = 100 * (closes[-1] - lowest_low) / (highest_high - lowest_low)
        d = np.mean(closes[-d_period:])
        
        return k, d
    
    def _calculate_atr(self, df: pd.DataFrame) -> float:
        """Calculate Average True Range"""
        try:
            high = df['high'].values
            low = df['low'].values
            close = df['close'].values
            
            if (high <= 0).any() or (low <= 0).any() or (close <= 0).any():
                return df['close'].iloc[-1] * 0.02
            
            tr = np.zeros(len(high))
            for i in range(1, len(high)):
                tr1 = high[i] - low[i]
                tr2 = abs(high[i] - close[i-1])
                tr3 = abs(low[i] - close[i-1])
                tr[i] = max(tr1, tr2, tr3)
            
            atr = np.mean(tr[-14:]) if len(tr) >= 14 else np.mean(tr)
            return atr if atr > 0 else df['close'].iloc[-1] * 0.02
            
        except Exception as e:
            logger.error(f"ATR calculation error: {e}")
            current_price = df['close'].iloc[-1] if 'close' in df.columns and len(df) > 0 else 1.0
            return current_price * 0.02
    
    def _analyze_volume_advanced(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Advanced volume analysis"""
        try:
            if 'volume' not in df.columns:
                return {'volume_ratio': 1.0, 'volume_trend': 0.0, 'volume_score': 0}
            
            volumes = df['volume'].values
            
            if len(volumes) < 20:
                return {'volume_ratio': 1.0, 'volume_trend': 0.0, 'volume_score': 0}
            
            volume_ma_20 = np.mean(volumes[-20:])
            volume_ratio = volumes[-1] / volume_ma_20 if volume_ma_20 > 0 else 1.0
            
            volume_trend = self._calculate_volume_trend(volumes)
            
            volume_score = 0
            if volume_ratio > 1.5:
                volume_score += 2
            elif volume_ratio > 1.2:
                volume_score += 1
            elif volume_ratio < 0.8:
                volume_score -= 1
            elif volume_ratio < 0.5:
                volume_score -= 2
            
            if volume_trend > 0.1:
                volume_score += 1
            elif volume_trend < -0.1:
                volume_score -= 1
            
            return {
                'volume_ratio': volume_ratio,
                'volume_trend': volume_trend,
                'volume_score': volume_score
            }
            
        except Exception as e:
            logger.error(f"Volume analysis error: {e}")
            return {'volume_ratio': 1.0, 'volume_trend': 0.0, 'volume_score': 0}
    
    def _analyze_trend_advanced(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Advanced trend analysis"""
        try:
            prices = df['close'].values
            
            if len(prices) < 20:
                return {'trend_strength': 0.0, 'trend_direction': 'NEUTRAL', 'trend_score': 0}
            
            if (prices <= 0).any():
                return {'trend_strength': 0.0, 'trend_direction': 'NEUTRAL', 'trend_score': 0}
            
            trend_short = self._calculate_trend_strength(prices[-10:])
            trend_medium = self._calculate_trend_strength(prices[-20:])
            trend_long = self._calculate_trend_strength(prices[-50:]) if len(prices) >= 50 else 0
            
            trend_strength = (trend_short * 0.4 + trend_medium * 0.4 + trend_long * 0.2)
            
            price_change_short = (prices[-1] - prices[-5]) / prices[-5] if prices[-5] > 0 else 0
            price_change_medium = (prices[-1] - prices[-10]) / prices[-10] if prices[-10] > 0 else 0
            
            if price_change_short > 0.02 and price_change_medium > 0.05:
                trend_direction = 'BULLISH'
            elif price_change_short < -0.02 and price_change_medium < -0.05:
                trend_direction = 'BEARISH'
            else:
                trend_direction = 'NEUTRAL'
            
            trend_score = 0
            if trend_strength > 0.6:
                if trend_direction == 'BULLISH':
                    trend_score += 3
                elif trend_direction == 'BEARISH':
                    trend_score -= 3
            elif trend_strength > 0.3:
                if trend_direction == 'BULLISH':
                    trend_score += 2
                elif trend_direction == 'BEARISH':
                    trend_score -= 2
            
            return {
                'trend_strength': trend_strength,
                'trend_direction': trend_direction,
                'trend_score': trend_score
            }
            
        except Exception as e:
            logger.error(f"Trend analysis error: {e}")
            return {'trend_strength': 0.0, 'trend_direction': 'NEUTRAL', 'trend_score': 0}
    
    def _calculate_trend_strength(self, prices: np.ndarray) -> float:
        """Calculate trend strength using linear regression"""
        if len(prices) < 5:
            return 0.0
        
        x = np.arange(len(prices))
        slope, _, r_value, _, _ = stats.linregress(x, prices)
        
        normalized_slope = abs(slope) / np.mean(prices) if np.mean(prices) > 0 else 0
        trend_strength = normalized_slope * (r_value ** 2)
        
        return min(trend_strength, 1.0)
    
    def _calculate_volume_trend(self, volumes: np.ndarray) -> float:
        """Calculate volume trend"""
        if len(volumes) < 10:
            return 0.0
        
        x = np.arange(len(volumes))
        slope, _, r_value, _, _ = stats.linregress(x, volumes)
        
        normalized_slope = slope / np.mean(volumes) if np.mean(volumes) > 0 else 0
        volume_trend = normalized_slope * (r_value ** 2)
        
        return volume_trend
    
    def _get_regime_multiplier(self, regime: MarketRegime) -> float:
        """Get score multiplier based on market regime"""
        multipliers = {
            MarketRegime.BULL_TREND: 1.3,
            MarketRegime.BEAR_TREND: 1.3,
            MarketRegime.RANGING: 0.7,
            MarketRegime.HIGH_VOLATILITY: 1.1,
            MarketRegime.LOW_VOLATILITY: 0.9,
            MarketRegime.BREAKOUT: 1.2,
            MarketRegime.UNKNOWN: 1.0
        }
        return multipliers.get(regime, 1.0)
    
    def _determine_risk_category(self, volatility: float) -> str:
        """Determine risk category based on volatility"""
        if volatility > 0.04:
            return "HIGH"
        elif volatility > 0.02:
            return "MEDIUM"
        else:
            return "LOW"
    
    def _apply_risk_adjustment(self, analysis: Dict[str, Any], df: pd.DataFrame, symbol: str = None) -> Dict[str, Any]:
        """Apply risk adjustment to analysis"""
        try:
            volatility = analysis.get('volatility', 0.02)
            score = analysis.get('score', 0)
            current_price = analysis.get('current_price', 0)
            
            if current_price <= 0:
                current_price = self._estimate_realistic_price(symbol or "UNKNOWN")
            
            risk_calc = self.risk_engine.calculate_dynamic_position_size(
                balance=10000,
                current_price=current_price,
                risk_score=score,
                volatility=volatility
            )
            
            analysis.update({
                'risk_metrics': risk_calc,
                'recommended_position_size': risk_calc.get('position_size', 0),
                'position_value_usd': risk_calc.get('position_value', 0),
                'risk_profile': risk_calc.get('risk_profile', 'MEDIUM')
            })
            
            return analysis
            
        except Exception as e:
            logger.error(f"Risk adjustment error: {e}")
            return analysis
    
    def _store_analysis_history(self, analysis: Dict[str, Any]):
        """Store analysis history untuk performance tracking"""
        try:
            self.analysis_history.append({
                'timestamp': datetime.now(),
                'symbol': analysis.get('symbol', 'Unknown'),
                'action': analysis.get('action', 'NEUTRAL'),
                'score': analysis.get('score', 0),
                'confidence': analysis.get('confidence', 0.5),
                'market_regime': analysis.get('market_regime', 'unknown')
            })
            
            if len(self.analysis_history) > 1000:
                self.analysis_history = self.analysis_history[-500:]
                
        except Exception as e:
            logger.error(f"Analysis history storage error: {e}")
    
    def _get_default_analysis(self, symbol: str = None) -> Dict[str, Any]:
        """Get default analysis result"""
        default_price = self._estimate_realistic_price(symbol or "UNKNOWN")
        default_entry = self.calculate_custom_entry(symbol or "UNKNOWN", default_price, "NEUTRAL")
        
        return {
            'action': 'NEUTRAL',
            'entry_range_low': default_entry['entry_range_low'],
            'entry_range_high': default_entry['entry_range_high'],
            'best_entry': default_entry['best_entry'],
            'tp1': default_entry['tp1'],
            'tp2': default_entry['tp2'],
            'tp3': default_entry['tp3'],
            'sl': default_entry['sl'],
            'current_price': default_price,
            'score': 0,
            'base_score': 0,
            'rsi': 50.0,
            'volume_ratio': 1.0,
            'atr': default_price * 0.02,
            'market_regime': 'unknown',
            'trend_strength': 0.0,
            'trend_direction': 'NEUTRAL',
            'pattern_confirmations': [],
            'pattern_count': 0,
            'support_levels': [],
            'resistance_levels': [],
            'volatility': 0.02,
            'risk_category': 'MEDIUM',
            'confidence': 0.5,
            'risk_metrics': {},
            'recommended_position_size': 0,
            'position_value_usd': 0,
            'risk_profile': 'MEDIUM',
            'symbol': symbol,
            'entry_range_pct': self.entry_range_pct * 100,
            'range_size': default_entry['range_size']
        }

    def _get_default_analysis_with_price(self, current_price: float, symbol: str = None) -> Dict[str, Any]:
        """Get default analysis dengan harga tertentu"""
        if current_price <= 0 or pd.isna(current_price):
            current_price = self._estimate_realistic_price(symbol or "UNKNOWN")
        
        default_entry = self.calculate_custom_entry(symbol or "UNKNOWN", current_price, "NEUTRAL")
        analysis = self._get_default_analysis(symbol)
        analysis.update({
            'entry_range_low': default_entry['entry_range_low'],
            'entry_range_high': default_entry['entry_range_high'],
            'best_entry': default_entry['best_entry'],
            'tp1': default_entry['tp1'],
            'tp2': default_entry['tp2'],
            'tp3': default_entry['tp3'],
            'sl': default_entry['sl'],
            'current_price': current_price,
            'range_size': default_entry['range_size']
        })
        return analysis

# =============================================
# DYNAMIC RISK ENGINE
# =============================================

class DynamicRiskEngine:
    """Dynamic risk management engine"""
    
    def __init__(self):
        self.risk_profiles = {
            'LOW': {'max_position_size': 0.1, 'max_drawdown': 0.02, 'volatility_threshold': 0.01},
            'MEDIUM': {'max_position_size': 0.07, 'max_drawdown': 0.035, 'volatility_threshold': 0.02},
            'HIGH': {'max_position_size': 0.04, 'max_drawdown': 0.05, 'volatility_threshold': 0.03},
            'VERY_HIGH': {'max_position_size': 0.02, 'max_drawdown': 0.08, 'volatility_threshold': 0.05}
        }
        
    def calculate_dynamic_position_size(self, balance, current_price, risk_score, volatility, correlation_penalty=0):
        """Calculate position size"""
        if current_price <= 0:
            current_price = 1.0
            
        risk_profile = 'MEDIUM'
        base_size = self.risk_profiles[risk_profile]['max_position_size']
        adjusted_size = base_size * (1 - correlation_penalty)
        position_value = balance * adjusted_size
        position_size = position_value / current_price if current_price > 0 else 0
        
        return {
            'position_size': position_size,
            'position_value': position_value,
            'risk_profile': risk_profile,
            'base_size_percent': base_size * 100,
            'adjusted_size_percent': adjusted_size * 100
        }

# =============================================
# BACKWARD COMPATIBILITY
# =============================================

class TechnicalAnalysisStrategy(EnhancedTechnicalAnalysisStrategy):
    """Backward compatibility wrapper"""
    pass

# =============================================
# TESTING FUNCTIONS
# =============================================

def test_strategy_with_entry_range():
    """Test the enhanced strategy with entry range"""
    strategy = EnhancedTechnicalAnalysisStrategy(market_type="crypto", entry_range_pct=0.03)
    
    # Create sample data
    dates = pd.date_range('2023-01-01', periods=100, freq='D')
    data = {
        'open': np.random.normal(100, 10, 100),
        'high': np.random.normal(105, 12, 100),
        'low': np.random.normal(95, 12, 100),
        'close': np.random.normal(100, 10, 100),
        'volume': np.random.normal(1000000, 100000, 100)
    }
    df = pd.DataFrame(data, index=dates)
    
    # Test analysis
    result = strategy.analyze(df, "BTC/USDT")
    print("Enhanced Analysis Result with Entry Range:")
    print(f"Action: {result['action']}")
    print(f"Current Price: {result['current_price']:.5f}")
    print(f"Entry Range: {result['entry_range_low']:.5f} - {result['entry_range_high']:.5f}")
    print(f"Best Entry: {result['best_entry']:.5f}")
    print(f"TP1: {result['tp1']:.5f}, TP2: {result['tp2']:.5f}, TP3: {result['tp3']:.5f}")
    print(f"SL: {result['sl']:.5f}")
    print(f"Score: {result['score']}")
    
    # Test format output
    formatted_output = strategy.format_signal_output(result)
    print("\nFormatted Output:")
    print(formatted_output)
    
    # Test custom entry calculation
    custom_entry = strategy.calculate_custom_entry("BTC/USDT", 100.0, "LONG")
    print(f"\nCustom Entry Calculation:")
    print(f"Entry Range: {custom_entry['entry_range_low']:.5f} - {custom_entry['entry_range_high']:.5f}")
    print(f"Range Size: {custom_entry['range_size']:.2f}%")
    
    return result

if __name__ == "__main__":
    # Run the test
    test_result = test_strategy_with_entry_range()
    
    print("\n✅ Enhanced Strategy with Entry Range Testing Completed!")
