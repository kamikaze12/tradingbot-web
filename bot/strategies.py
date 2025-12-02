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
    
    def calculate_custom_entry(self, symbol: str, current_price: float, action: str = "LONG", df: pd.DataFrame = None) -> Dict[str, Any]:
        """Calculate TP/SL dengan entry range - FIXED VERSION with dynamic ATR and sentiment modifier"""
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
            
            # Calculate dynamic ATR from real data if DF provided, else fallback
            if df is not None and not df.empty and all(col in df.columns for col in ['high', 'low', 'close']):
                atr = self._calculate_atr(df)
            else:
                if self.market_type == "forex":
                    atr = current_price * 0.005  # 0.5% untuk forex
                elif self.market_type == "us_stocks":
                    atr = current_price * 0.015  # 1.5% untuk saham US
                elif self.market_type == "forex_gold":
                    atr = current_price * 0.008  # 0.8% untuk gold
                else:
                    atr = current_price * 0.02   # 2% untuk crypto
            
            atr = max(atr, current_price * 0.01)  # Minimum 1%
            
            # Sentiment modifier: Widen range if sentiment < -0.3
            entry_range_pct = self.entry_range_pct
            if df is not None and 'sentiment' in df.columns:
                avg_sentiment = df['sentiment'].mean()
                if avg_sentiment < -0.3:
                    entry_range_pct *= 1.5  # Widen by 50% for caution
                    logger.info(f"Negative sentiment ({avg_sentiment:.2f}) detected; widening entry range to {entry_range_pct*100:.2f}%")
            
            # ✅ PERBAIKAN: Pastikan entry range selalu terhitung
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
                'entry_range_pct': entry_range_pct * 100,
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
            peak2 = np.max(highs[peak1_idx:peak2_idx]) if peak2_idx > peak1_idx else 0
            
            if peak1 > 0 and peak2 > 0 and abs(peak1 - peak2) / ((peak1 + peak2)/2) < 0.02:  # Peaks within 2%
                valley = np.min(lows[peak1_idx:peak2_idx])
                
                if valley > 0 and (peak1 - valley) / peak1 > 0.03:  # At least 3% drop
                
                    detected = True
                    confidence = 0.65
                    direction = "BEARISH"  # Double Top
                    entry = current_price
                    target = current_price - (peak1 - valley)
                    stop_loss = max(peak1, peak2) * 1.01
                    rr_ratio = abs(target - entry) / abs(entry - stop_loss) if abs(entry - stop_loss) > 0 else 1.0
                    
                    return PatternDetection(
                        "double_top", True, direction, confidence,
                        entry, target, stop_loss, rr_ratio, "1D"
                    )
            
            # Similar logic for Double Bottom (inverted)
            bottom1 = np.min(lows[:peak1_idx]) if peak1_idx > 0 else 0
            bottom2 = np.min(lows[peak1_idx:peak2_idx]) if peak2_idx > peak1_idx else 0
            
            if bottom1 > 0 and bottom2 > 0 and abs(bottom1 - bottom2) / ((bottom1 + bottom2)/2) < 0.02:
                peak_valley = np.max(highs[peak1_idx:peak2_idx])
                
                if peak_valley > 0 and (peak_valley - bottom1) / bottom1 > 0.03:
                    
                    detected = True
                    confidence = 0.65
                    direction = "BULLISH"  # Double Bottom
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
    
    def _detect_triangle_patterns_advanced(self, df: pd.DataFrame) -> Dict[str, PatternDetection]:
        """Detect triangle patterns: Ascending, Descending, Symmetrical"""
        patterns = {}
        
        try:
            if len(df) < 50:
                return patterns
            
            current_price = df['close'].iloc[-1]
            if current_price <= 0:
                return patterns
            
            highs = df['high'].tail(50).values
            lows = df['low'].tail(50).values
            
            # Calculate trendlines
            upper_trendline = self._calculate_trendline(highs, 'upper')
            lower_trendline = self._calculate_trendline(lows, 'lower')
            
            # Check for convergence
            upper_slope = upper_trendline['slope']
            lower_slope = lower_trendline['slope']
            
            if abs(upper_slope) < 0.001 and abs(lower_slope) < 0.001:  # Both flat
                return patterns  # Not a triangle
            
            # Symmetrical Triangle: Upper down, lower up
            if upper_slope < 0 and lower_slope > 0:
                confidence = 0.7
                direction = "BULLISH" if current_price > (upper_trendline['intercept'] + lower_trendline['intercept']) / 2 else "BEARISH"
                entry = current_price
                target = current_price * 1.05 if direction == "BULLISH" else current_price * 0.95
                stop_loss = current_price * 0.98 if direction == "BULLISH" else current_price * 1.02
                rr_ratio = abs(target - entry) / abs(entry - stop_loss) if abs(entry - stop_loss) > 0 else 1.0
                
                patterns['symmetrical_triangle'] = PatternDetection(
                    "symmetrical_triangle", True, direction, confidence,
                    entry, target, stop_loss, rr_ratio, "1D"
                )
            
            # Ascending Triangle: Upper flat, lower up
            if abs(upper_slope) < 0.001 and lower_slope > 0:
                confidence = 0.75
                direction = "BULLISH"
                entry = current_price
                target = current_price * 1.05
                stop_loss = current_price * 0.98
                rr_ratio = abs(target - entry) / abs(entry - stop_loss) if abs(entry - stop_loss) > 0 else 1.0
                
                patterns['ascending_triangle'] = PatternDetection(
                    "ascending_triangle", True, direction, confidence,
                    entry, target, stop_loss, rr_ratio, "1D"
                )
            
            # Descending Triangle: Upper down, lower flat
            if upper_slope < 0 and abs(lower_slope) < 0.001:
                confidence = 0.75
                direction = "BEARISH"
                entry = current_price
                target = current_price * 0.95
                stop_loss = current_price * 1.02
                rr_ratio = abs(target - entry) / abs(entry - stop_loss) if abs(entry - stop_loss) > 0 else 1.0
                
                patterns['descending_triangle'] = PatternDetection(
                    "descending_triangle", True, direction, confidence,
                    entry, target, stop_loss, rr_ratio, "1D"
                )
            
            return patterns
            
        except Exception as e:
            logger.error(f"Triangle pattern detection error: {e}")
            return {}
    
    def _calculate_trendline(self, prices: np.ndarray, direction: str = 'upper') -> Dict[str, float]:
        """Calculate trendline slope and intercept"""
        try:
            if len(prices) < 5:
                return {'slope': 0, 'intercept': 0}
            
            x = np.arange(len(prices))
            slope, intercept, r_value, _, _ = stats.linregress(x, prices)
            
            return {'slope': slope, 'intercept': intercept, 'r_squared': r_value**2}
            
        except Exception as e:
            logger.error(f"Trendline calculation error: {e}")
            return {'slope': 0, 'intercept': 0}
    
    def _detect_candlestick_patterns(self, df: pd.DataFrame) -> Dict[str, PatternDetection]:
        """Detect candlestick patterns"""
        patterns = {}
        
        try:
            if not TALIB_AVAILABLE:
                return patterns
            
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
                target = entry * 1.02  # Neutral reversal
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
            
            # Engulfing
            engulfing = talib.CDLENGULFING(open_price, high, low, close)
            if engulfing[-1] != 0:
                confidence = 0.7
                direction = "BULLISH" if engulfing[-1] > 0 else "BEARISH"
                entry = close[-1]
                target = entry * 1.03 if direction == "BULLISH" else entry * 0.97
                stop_loss = low[-1] * 0.99 if direction == "BULLISH" else high[-1] * 1.01
                rr_ratio = abs(target - entry) / abs(entry - stop_loss) if abs(entry - stop_loss) > 0 else 1.0
                
                patterns['engulfing'] = PatternDetection(
                    "engulfing", True, direction, confidence,
                    entry, target, stop_loss, rr_ratio, "1D"
                )
            
            # Add more candlestick patterns as needed
            
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
            
            # Volume Divergence
            price_trend = prices[-1] - prices[0]
            volume_trend = volumes[-1] - volumes[0]
            
            if price_trend > 0 and volume_trend < 0:
                confidence = 0.6
                direction = "BEARISH"  # Bullish divergence
                entry = current_price
                target = entry * 0.95
                stop_loss = entry * 1.02
                rr_ratio = abs(target - entry) / abs(entry - stop_loss) if abs(entry - stop_loss) > 0 else 1.0
                
                patterns['volume_divergence'] = PatternDetection(
                    "volume_divergence", True, direction, confidence,
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
            
            # Channel Pattern
            upper_trend = self._calculate_trendline(df['high'].values, 'upper')
            lower_trend = self._calculate_trendline(df['low'].values, 'lower')
            
            if abs(upper_trend['slope'] - lower_trend['slope']) < 0.001 and abs(upper_trend['slope']) > 0.001:
                confidence = 0.7
                direction = "BULLISH" if upper_trend['slope'] > 0 else "BEARISH"
                entry = current_price
                target = entry * 1.05 if direction == "BULLISH" else entry * 0.95
                stop_loss = entry * 0.98 if direction == "BULLISH" else entry * 1.02
                rr_ratio = abs(target - entry) / abs(entry - stop_loss) if abs(entry - stop_loss) > 0 else 1.0
                
                patterns['trend_channel'] = PatternDetection(
                    "trend_channel", True, direction, confidence,
                    entry, target, stop_loss, rr_ratio, "1D"
                )
            
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
# ENHANCED TECHNICAL ANALYSIS STRATEGY
# =============================================

class EnhancedTechnicalAnalysisStrategy(TradingStrategy):
    """Enhanced technical analysis strategy dengan multi-timeframe dan pattern detection"""
    
    def __init__(self, market_type="crypto", atr_multiplier=1.0, entry_range_pct=0.02):
        super().__init__(market_type, atr_multiplier, entry_range_pct)
        self.pattern_detector = AdvancedPatternDetector()
        self.risk_engine = DynamicRiskEngine()
        self.analysis_history = []
        self.min_pattern_confidence = 0.6
    
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

    def analyze(self, df: pd.DataFrame, symbol: str = None) -> Dict[str, Any]:
        """Analyze market data with enhanced features and entry range"""
        try:
            if df is None or df.empty:
                logger.warning("Empty DataFrame in analyze")
                return self._get_default_analysis(symbol)
            
            # Get valid current price
            current_price = self._get_valid_current_price(df)
            if current_price <= 0:
                logger.warning("Invalid current price in analyze")
                return self._get_default_analysis(symbol)
            
            # Calculate enhanced indicators
            indicators = self._calculate_enhanced_indicators(df)
            
            # Analyze volume
            volume_analysis = self._analyze_volume_advanced(df)
            
            # Analyze trend
            trend_analysis = self._analyze_trend_advanced(df)
            
            # Detect patterns
            patterns = self.pattern_detector.detect_comprehensive_patterns(df, symbol)
            pattern_count = len(patterns)
            pattern_confirmations = list(patterns.keys())
            pattern_score = sum(p.confidence for p in patterns.values()) / max(1, pattern_count) * 3
            
            # Calculate base score
            base_score = self._calculate_base_score(indicators, volume_analysis, trend_analysis, pattern_score)
            
            # Get market regime
            market_regime = self._analyze_market_regime(df, base_score, indicators['volatility'], trend_analysis['trend_strength'])
            regime_multiplier = self._get_regime_multiplier(market_regime)
            
            # Apply regime adjustment
            adjusted_score = base_score * regime_multiplier
            
            # Determine action
            action = "LONG" if adjusted_score > 5 else "SHORT" if adjusted_score < -5 else "NEUTRAL"
            
            # Calculate custom entry with DF for dynamic ATR and sentiment
            entry_calculation = self.calculate_custom_entry(symbol, current_price, action, df)
            
            # Final analysis dict
            analysis = {
                'action': action,
                'entry_range_low': entry_calculation['entry_range_low'],
                'entry_range_high': entry_calculation['entry_range_high'],
                'best_entry': entry_calculation['best_entry'],
                'tp1': entry_calculation['tp1'],
                'tp2': entry_calculation['tp2'],
                'tp3': entry_calculation['tp3'],
                'sl': entry_calculation['sl'],
                'current_price': current_price,
                'score': adjusted_score,
                'base_score': base_score,
                'rsi': indicators['rsi_14'],
                'volume_ratio': volume_analysis['volume_ratio'],
                'atr': indicators['atr'],
                'market_regime': market_regime.value,
                'trend_strength': trend_analysis['trend_strength'],
                'trend_direction': trend_analysis['trend_direction'],
                'pattern_confirmations': pattern_confirmations,
                'pattern_count': pattern_count,
                'support_levels': self._find_support_resistance(df)['support'],
                'resistance_levels': self._find_support_resistance(df)['resistance'],
                'volatility': indicators['volatility'],
                'risk_category': self._determine_risk_category(indicators['volatility']),
                'confidence': min(abs(adjusted_score) / 10.0, 1.0),
                'momentum_5': indicators['momentum_5'],
                'momentum_10': indicators['momentum_10'],
                'macd_line': indicators['macd_line'],
                'macd_signal': indicators['macd_signal'],
                'bb_position': indicators['bb_position'],
                'symbol': symbol,
                'entry_range_pct': entry_calculation['entry_range_pct'],
                'range_size': entry_calculation['range_size']
            }
            
            # Final validation
            analysis = self._final_validation(analysis, symbol)
            
            # Apply risk adjustment
            analysis = self._apply_risk_adjustment(analysis, df, symbol)
            
            # Store history
            self._store_analysis_history(analysis)
            
            return analysis
            
        except Exception as e:
            logger.error(f"Analysis error: {e}")
            return self._get_default_analysis_with_price(current_price, symbol)

    def _calculate_base_score(self, indicators: Dict[str, float], 
                             volume: Dict[str, Any], 
                             trend: Dict[str, Any], 
                             pattern_score: float) -> float:
        """Calculate base score from indicators"""
        score = 0
        
        # RSI Score (30% weight)
        rsi = indicators['rsi_14']
        if rsi < 30:
            score += 3
        elif rsi < 40:
            score += 2
        elif rsi > 70:
            score -= 3
        elif rsi > 60:
            score -= 2
        
        # MACD Score (25% weight)
        if indicators['macd_line'] > indicators['macd_signal'] and indicators['macd_histogram'] > 0:
            score += 2.5
        elif indicators['macd_line'] < indicators['macd_signal'] and indicators['macd_histogram'] < 0:
            score -= 2.5
        
        # Bollinger Bands Score (20% weight)
        bb_pos = indicators['bb_position']
        if bb_pos < 0.2:
            score += 2
        elif bb_pos > 0.8:
            score -= 2
        
        # Volume Score (15% weight)
        score += volume['volume_score'] * 1.5
        
        # Trend Score (10% weight)
        score += trend['trend_score']
        
        # Pattern Score
        score += pattern_score
        
        return score

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

    def _find_support_resistance(self, df: pd.DataFrame, window: int = 5) -> Dict[str, List[float]]:
        """Find support and resistance levels"""
        try:
            highs = df['high'].values
            lows = df['low'].values
            
            if len(highs) < window * 2 or len(lows) < window * 2:
                return {'support': [], 'resistance': []}
            
            resistance = highs[argrelextrema(highs, np.greater, order=window)[0]].tolist()
            support = lows[argrelextrema(lows, np.less, order=window)[0]].tolist()
            
            # Filter duplicates and sort
            resistance = sorted(list(set(resistance)))[-3:]  # Top 3 recent
            support = sorted(list(set(support)))[-3:]
            
            return {'support': support, 'resistance': resistance}
            
        except Exception as e:
            logger.error(f"Support/resistance calculation error: {e}")
            return {'support': [], 'resistance': []}

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

    def _final_validation(self, analysis: Dict[str, Any], symbol: str = None) -> Dict[str, Any]:
        """Final validation and cleanup of analysis data"""
        try:
            # Ensure all numeric values are valid
            for key in ['current_price', 'entry_range_low', 'entry_range_high', 
                       'best_entry', 'tp1', 'tp2', 'tp3', 'sl', 'atr', 'score']:
                if key in analysis:
                    if pd.isna(analysis[key]) or not isinstance(analysis[key], (int, float)):
                        analysis[key] = 0.0
                    analysis[key] = float(analysis[key])
            
            # Ensure action is valid
            if analysis['action'] not in ['LONG', 'SHORT', 'NEUTRAL']:
                analysis['action'] = 'NEUTRAL'
            
            return analysis
            
        except Exception as e:
            logger.error(f"Final validation error: {e}")
            return self._get_default_analysis(symbol)

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
        'volume': np.random.normal(1000000, 100000, 100),
        'sentiment': np.random.uniform(-1, 1, 100)  # Sample sentiment data
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
    custom_entry = strategy.calculate_custom_entry("BTC/USDT", 100.0, "LONG", df)
    print(f"\nCustom Entry Calculation:")
    print(f"Entry Range: {custom_entry['entry_range_low']:.5f} - {custom_entry['entry_range_high']:.5f}")
    print(f"Range Size: {custom_entry['range_size']:.2f}%")
    
    return result

if __name__ == "__main__":
    # Run the test
    test_result = test_strategy_with_entry_range()
    
    print("\n✅ Enhanced Strategy with Entry Range Testing Completed!")
