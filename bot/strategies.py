import pandas as pd
import numpy as np
from abc import ABC, abstractmethod
import warnings
warnings.filterwarnings('ignore')

try:
    import talib
    TALIB_AVAILABLE = True
except ImportError:
    TALIB_AVAILABLE = False
    print("Warning: TA-LIB not available, using simple calculations")

class TradingStrategy(ABC):
    @abstractmethod
    def analyze(self, df):
        pass

class TechnicalAnalysisStrategy(TradingStrategy):
    def __init__(self, atr_multiplier=1.0, entry_range_pct=0.02):
        self.atr_multiplier = atr_multiplier
        self.entry_range_pct = entry_range_pct
    
    def identify_hh_hl_lh_ll(self, df, lookback=20):
        """Identify Higher High, Higher Low, Lower High, Lower Low patterns"""
        highs = df['high'].tail(lookback)
        lows = df['low'].tail(lookback)
        
        # Initialize patterns
        hh = hl = lh = ll = False
        
        # Check for HH/HL (uptrend)
        if len(highs) >= 5:
            # Higher High: current high > previous high
            if highs.iloc[-1] > highs.iloc[-2] > highs.iloc[-3]:
                hh = True
            
            # Higher Low: current low > previous low
            if lows.iloc[-1] > lows.iloc[-2] > lows.iloc[-3]:
                hl = True
        
        # Check for LH/LL (downtrend)
        if len(highs) >= 5:
            # Lower High: current high < previous high
            if highs.iloc[-1] < highs.iloc[-2] < highs.iloc[-3]:
                lh = True
            
            # Lower Low: current low < previous low
            if lows.iloc[-1] < lows.iloc[-2] < lows.iloc[-3]:
                ll = True
                
        return hh, hl, lh, ll
    
    def analyze_ema_cross(self, df):
        """Analyze EMA 13 and EMA 21 crossover"""
        if len(df) < 22:  # Need enough data for EMA 21
            return "NEUTRAL", 0
            
        # Calculate EMAs
        ema_13 = talib.EMA(df['close'], timeperiod=13) if TALIB_AVAILABLE else df['close'].ewm(span=13).mean()
        ema_21 = talib.EMA(df['close'], timeperiod=21) if TALIB_AVAILABLE else df['close'].ewm(span=21).mean()
        
        # Check crossover
        ema_trend = "BULLISH" if ema_13.iloc[-1] > ema_21.iloc[-1] else "BEARISH"
        ema_score = 1 if ema_trend == "BULLISH" else -1
        
        return ema_trend, ema_score
    
    def calculate_atr(self, df):
        """Calculate ATR for the given dataframe"""
        if len(df) < 14:
            return 0.0
        if TALIB_AVAILABLE:
            atr = talib.ATR(df['high'], df['low'], df['close'], timeperiod=14)
            return atr.iloc[-1] if not np.isnan(atr.iloc[-1]) else 0.0
        else:
            # Fallback pandas calculation
            high_low = df['high'] - df['low']
            high_close = np.abs(df['high'] - df['close'].shift())
            low_close = np.abs(df['low'] - df['close'].shift())
            ranges = pd.concat([high_low, high_close, low_close], axis=1)
            true_range = np.max(ranges, axis=1)
            atr = true_range.rolling(14).sum() / 14
            return atr.iloc[-1] if not np.isnan(atr.iloc[-1]) else 0.0
    
    def detect_triangle_patterns(self, df, period=20):
        """Detect various triangle patterns"""
        patterns = {
            'symmetrical_triangle': False,
            'ascending_triangle': False,
            'descending_triangle': False,
            'broadening_ascending': False,
            'broadening_descending': False
        }
        
        if len(df) < period * 2:
            return patterns
            
        # Get recent highs and lows
        highs = df['high'].tail(period)
        lows = df['low'].tail(period)
        
        # Calculate trendlines for highs and lows
        high_slope = np.polyfit(range(len(highs)), highs, 1)[0]
        low_slope = np.polyfit(range(len(lows)), lows, 1)[0]
        
        # Symmetrical Triangle: converging trendlines with similar slopes
        if abs(high_slope) > 0 and abs(low_slope) > 0:
            if high_slope < 0 and low_slope > 0 and abs(high_slope/low_slope) < 1.5:
                patterns['symmetrical_triangle'] = True
        
        # Ascending Triangle: horizontal resistance, rising support
        high_std = np.std(highs)
        if high_std < np.std(highs) * 0.7 and low_slope > 0:
            patterns['ascending_triangle'] = True
        
        # Descending Triangle: horizontal support, falling resistance
        low_std = np.std(lows)
        if low_std < np.std(lows) * 0.7 and high_slope < 0:
            patterns['descending_triangle'] = True
            
        # Broadening patterns (expanding volatility)
        if high_slope > 0 and low_slope < 0:
            patterns['broadening_ascending'] = True
        elif high_slope < 0 and low_slope > 0:
            patterns['broadending_descending'] = True
            
        return patterns
    
    def detect_channel_wedge_patterns(self, df, period=20):
        """Detect channel and wedge patterns"""
        patterns = {
            'uptrend_channel': False,
            'downtrend_channel': False,
            'ranging_channel': False,
            'rising_wedge': False,
            'falling_wedge': False
        }
        
        if len(df) < period * 2:
            return patterns
            
        highs = df['high'].tail(period)
        lows = df['low'].tail(period)
        closes = df['close'].tail(period)
        
        # Calculate regression channels
        high_slope = np.polyfit(range(len(highs)), highs, 1)[0]
        low_slope = np.polyfit(range(len(lows)), lows, 1)[0]
        close_slope = np.polyfit(range(len(closes)), closes, 1)[0]
        
        # Uptrend Channel: both highs and lows trending up
        if high_slope > 0 and low_slope > 0 and close_slope > 0:
            patterns['uptrend_channel'] = True
            
        # Downtrend Channel: both highs and lows trending down
        if high_slope < 0 and low_slope < 0 and close_slope < 0:
            patterns['downtrend_channel'] = True
            
        # Ranging Channel: minimal slope with consistent range
        if abs(high_slope) < 0.001 and abs(low_slope) < 0.001:
            patterns['ranging_channel'] = True
            
        # Rising Wedge: highs rising faster than lows
        if high_slope > 0 and low_slope > 0 and high_slope > low_slope * 1.5:
            patterns['rising_wedge'] = True
            
        # Falling Wedge: lows falling faster than highs
        if high_slope < 0 and low_slope < 0 and abs(low_slope) > abs(high_slope) * 1.5:
            patterns['falling_wedge'] = True
            
        return patterns
    
    def detect_harmonic_patterns(self, df, period=50):
        """Simplified harmonic pattern detection"""
        patterns = {
            'gartley': False,
            'bat': False,
            'butterfly': False,
            'crab': False,
            'shark': False
        }
        
        if len(df) < period:
            return patterns
            
        # This is a simplified version - real harmonic pattern detection
        # requires complex Fibonacci retracement calculations
        closes = df['close'].tail(period)
        price_change = (closes.iloc[-1] - closes.iloc[0]) / closes.iloc[0]
        
        # Very basic pattern detection based on price movements
        # In a real implementation, this would use proper Fibonacci ratios
        if abs(price_change) < 0.05:  # Small price change
            patterns['gartley'] = True
        elif 0.05 <= abs(price_change) < 0.1:
            patterns['bat'] = True
        elif 0.1 <= abs(price_change) < 0.15:
            patterns['butterfly'] = True
        elif 0.15 <= abs(price_change) < 0.2:
            patterns['crab'] = True
        else:
            patterns['shark'] = True
            
        return patterns
    
    def analyze(self, df):
        """Main analysis method with enhanced pattern recognition"""
        if len(df) < 50:
            return None
        
        current_close = df['close'].iloc[-1]
        
        # Calculate RSI with fallback
        if TALIB_AVAILABLE:
            current_rsi = talib.RSI(df['close'], timeperiod=14).iloc[-1]
        else:
            # Simple RSI fallback
            price_diff = df['close'].diff()
            gain = price_diff.where(price_diff > 0, 0).rolling(14).mean()
            loss = -price_diff.where(price_diff < 0, 0).rolling(14).mean()
            rs = gain / loss
            current_rsi = 100 - (100 / (1 + rs)).iloc[-1] if not np.isnan(rs.iloc[-1]) and loss.iloc[-1] != 0 else 50
        
        # Get ATR
        atr = self.calculate_atr(df)
        
        # Pattern analysis
        hh, hl, lh, ll = self.identify_hh_hl_lh_ll(df)
        
        # EMA analysis
        ema_trend, ema_score = self.analyze_ema_cross(df)
        
        # Volume ratio
        vol_mean = df['volume'].rolling(20).mean().iloc[-1]
        volume_ratio = df['volume'].iloc[-1] / vol_mean if vol_mean > 0 else 1
        
        # Enhanced pattern detection
        triangle_patterns = self.detect_triangle_patterns(df)
        channel_wedge_patterns = self.detect_channel_wedge_patterns(df)
        harmonic_patterns = self.detect_harmonic_patterns(df)
        
        # Trend determination
        trend_score = 0
        if hh or hl:
            trend_score += 2  # Bullish pattern
        if lh or ll:
            trend_score -= 2  # Bearish pattern
        if ema_trend == "BULLISH":
            trend_score += ema_score
        else:
            trend_score += ema_score
        
        # Pattern-based scoring
        pattern_score = 0
        
        # Triangle patterns
        if triangle_patterns['ascending_triangle']:
            pattern_score += 3  # Bullish pattern
        if triangle_patterns['descending_triangle']:
            pattern_score -= 3  # Bearish pattern
        if triangle_patterns['symmetrical_triangle']:
            pattern_score += 1  # Neutral but often continuation
            
        # Channel patterns
        if channel_wedge_patterns['uptrend_channel']:
            pattern_score += 2
        if channel_wedge_patterns['downtrend_channel']:
            pattern_score -= 2
        if channel_wedge_patterns['falling_wedge']:
            pattern_score += 2  # Bullish reversal
        if channel_wedge_patterns['rising_wedge']:
            pattern_score -= 2  # Bearish reversal
            
        # Harmonic patterns (simplified scoring)
        for pattern, detected in harmonic_patterns.items():
            if detected:
                pattern_score += 1  # All harmonic patterns get a small boost
        
        # RSI score
        rsi_score = 0
        if 30 < current_rsi < 70:
            rsi_score = 1
        elif current_rsi < 30:
            rsi_score = 2  # Oversold - good for LONG
        elif current_rsi > 70:
            rsi_score = -2  # Overbought - good for SHORT
        
        # Volume score
        volume_score = 1 if volume_ratio > 1.2 else 0 if volume_ratio > 0.8 else -1
        
        # Total score with pattern enhancement
        score = trend_score + rsi_score + volume_score + pattern_score
        
        # Determine action
        action = "LONG" if score > 0 else "SHORT" if score < 0 else "NEUTRAL"
        
        # Calculate entry levels if action is LONG or SHORT
        if action in ["LONG", "SHORT"]:
            ideal_entry = current_close
            entry_low = ideal_entry * (1 - self.entry_range_pct)
            entry_high = ideal_entry * (1 + self.entry_range_pct)
            if action == "LONG":
                tp1 = ideal_entry + atr * self.atr_multiplier
                tp2 = ideal_entry + atr * self.atr_multiplier * 2
                tp3 = ideal_entry + atr * self.atr_multiplier * 3
                sl = ideal_entry - atr * self.atr_multiplier
            elif action == "SHORT":
                tp1 = ideal_entry - atr * self.atr_multiplier
                tp2 = ideal_entry - atr * self.atr_multiplier * 2
                tp3 = ideal_entry - atr * self.atr_multiplier * 3
                sl = ideal_entry + atr * self.atr_multiplier
        else:
            ideal_entry = entry_low = entry_high = tp1 = tp2 = tp3 = sl = None
        
        # Compile pattern information
        all_patterns = {**triangle_patterns, **channel_wedge_patterns, **harmonic_patterns}
        detected_patterns = [pattern for pattern, detected in all_patterns.items() if detected]
        
        # Result
        result = {
            'action': action,
            'ideal_entry': float(ideal_entry) if ideal_entry is not None else None,
            'entry_low': float(entry_low) if entry_low is not None else None,
            'entry_high': float(entry_high) if entry_high is not None else None,
            'tp1': float(tp1) if tp1 is not None else None,
            'tp2': float(tp2) if tp2 is not None else None,
            'tp3': float(tp3) if tp3 is not None else None,
            'sl': float(sl) if sl is not None else None,
            'current_price': float(current_close),
            'rsi': float(current_rsi),
            'trend': 'BULLISH' if trend_score > 0 else 'BEARISH' if trend_score < 0 else 'NEUTRAL',
            'volume_ratio': float(volume_ratio),
            'score': int(score),
            'atr': float(atr),
            'hh': hh,
            'hl': hl,
            'lh': lh,
            'll': ll,
            'ema_trend': ema_trend,
            'ema_score': ema_score,
            'pattern_score': pattern_score,
            'detected_patterns': detected_patterns,
            'pattern_details': all_patterns
        }
        
        return result