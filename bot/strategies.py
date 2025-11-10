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

try:
    from sklearn.svm import SVC
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import accuracy_score
    import optuna
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False
    print("Warning: scikit-learn or optuna not available, skipping ML features. Install with pip install scikit-learn optuna")

import yfinance as yf  # Untuk backtest data

class TradingStrategy(ABC):
    @abstractmethod
    def analyze(self, df):
        pass

class TechnicalAnalysisStrategy(TradingStrategy):
    def __init__(self, market_type="crypto", atr_multiplier=1.0, entry_range_pct=0.02):
        self.market_type = market_type
        self.atr_multiplier = atr_multiplier
        self.entry_range_pct = entry_range_pct
        self.set_market_parameters()
    
    def set_market_parameters(self):
        """Set market-specific parameters for better scoring"""
        if self.market_type == "crypto":
            self.rsi_oversold = 25
            self.rsi_overbought = 75
            self.volume_threshold = 1.3
            self.adx_trend_threshold = 20
            self.pattern_weight = 2.0
            self.trend_weight = 2.0
        elif self.market_type == "forex":
            self.rsi_oversold = 30
            self.rsi_overbought = 70
            self.volume_threshold = 1.1
            self.adx_trend_threshold = 25
            self.pattern_weight = 1.0
            self.trend_weight = 1.0
        elif self.market_type == "saham_id":
            self.rsi_oversold = 35
            self.rsi_overbought = 65
            self.volume_threshold = 1.2
            self.adx_trend_threshold = 20
            self.pattern_weight = 1.5
            self.trend_weight = 1.5
        else:  # stocks international
            self.rsi_oversold = 30
            self.rsi_overbought = 70
            self.volume_threshold = 1.2
            self.adx_trend_threshold = 22
            self.pattern_weight = 1.2
            self.trend_weight = 1.2
    
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
        if TALIB_AVAILABLE:
            ema_13 = talib.EMA(df['close'], timeperiod=13)
            ema_21 = talib.EMA(df['close'], timeperiod=21)
            ema_13_last = ema_13[-1]
            ema_21_last = ema_21[-1]
        else:
            ema_13 = df['close'].ewm(span=13).mean()
            ema_21 = df['close'].ewm(span=21).mean()
            ema_13_last = ema_13.iloc[-1]
            ema_21_last = ema_21.iloc[-1]
        
        # Check crossover
        ema_trend = "BULLISH" if ema_13_last > ema_21_last else "BEARISH"
        ema_score = 1 if ema_trend == "BULLISH" else -1
        
        return ema_trend, ema_score
    
    def calculate_atr(self, df):
        """Calculate ATR for the given dataframe"""
        if len(df) < 14:
            return 0.0
        if TALIB_AVAILABLE:
            atr = talib.ATR(df['high'], df['low'], df['close'], timeperiod=14)
            last_atr = atr[-1] if not np.isnan(atr[-1]) else 0.0
        else:
            # Fallback pandas calculation
            high_low = df['high'] - df['low']
            high_close = np.abs(df['high'] - df['close'].shift())
            low_close = np.abs(df['low'] - df['close'].shift())
            ranges = pd.concat([high_low, high_close, low_close], axis=1)
            true_range = np.max(ranges, axis=1)
            atr = true_range.rolling(14).sum() / 14
            last_atr = atr.iloc[-1] if not np.isnan(atr.iloc[-1]) else 0.0
        return last_atr
    
    def detect_market_regime(self, df):
        """Detect trending vs ranging market dengan ADX"""
        if len(df) < 20:
            return "UNKNOWN", 0
        
        try:
            if TALIB_AVAILABLE:
                adx = talib.ADX(df['high'], df['low'], df['close'], timeperiod=14)
                current_adx = adx[-1] if not np.isnan(adx[-1]) else 0
            else:
                # Simple trend strength calculation
                highs = df['high'].tail(14)
                lows = df['low'].tail(14)
                high_range = highs.max() - highs.min()
                low_range = lows.max() - lows.min()
                price_range = max(high_range, low_range)
                avg_price = df['close'].tail(14).mean()
                if avg_price > 0:
                    current_adx = (price_range / avg_price) * 100
                else:
                    current_adx = 0
            
            if current_adx > self.adx_trend_threshold:
                return "TRENDING", current_adx
            elif current_adx < 15:
                return "RANGING", current_adx
            else:
                return "MIXED", current_adx
                
        except Exception:
            return "UNKNOWN", 0
    
    def calculate_trend_strength(self, series):
        """Calculate trend strength dengan R-squared"""
        if len(series) < 5:
            return 0, 0
            
        x = np.arange(len(series))
        y = series.values
        
        # Linear regression
        coefficients = np.polyfit(x, y, 1)
        slope = coefficients[0]
        
        # Calculate R-squared
        y_pred = np.polyval(coefficients, x)
        ss_res = np.sum((y - y_pred) ** 2)
        ss_tot = np.sum((y - np.mean(y)) ** 2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0
        
        return slope, r_squared
    
    def detect_triangle_patterns(self, df, period=20):
        """Detect various triangle patterns dengan confidence"""
        patterns = {
            'symmetrical_triangle': False,
            'ascending_triangle': False,
            'descending_triangle': False,
            'broadening_ascending': False,
            'broadening_descending': False
        }
        
        confidence_scores = {}
        
        if len(df) < period * 2:
            return patterns, confidence_scores
            
        # Get recent highs and lows
        highs = df['high'].tail(period)
        lows = df['low'].tail(period)
        
        # Calculate trendlines dengan confidence
        high_slope, high_r2 = self.calculate_trend_strength(highs)
        low_slope, low_r2 = self.calculate_trend_strength(lows)
        
        # Overall pattern confidence
        base_confidence = (high_r2 + low_r2) / 2
        
        # Symmetrical Triangle: converging trendlines with similar slopes
        if abs(high_slope) > 0 and abs(low_slope) > 0:
            slope_ratio = abs(high_slope / low_slope) if low_slope != 0 else 0
            if (high_slope < 0 and low_slope > 0 and 
                0.5 < slope_ratio < 2.0 and  # More strict ratio
                base_confidence > 0.6):      # Minimum confidence
                patterns['symmetrical_triangle'] = True
                confidence_scores['symmetrical_triangle'] = base_confidence
        
        # Ascending Triangle: horizontal resistance, rising support
        high_std = np.std(highs)
        high_mean_std = np.std(highs) * 0.7  # Tighter threshold
        if high_std < high_mean_std and low_slope > 0 and base_confidence > 0.5:
            patterns['ascending_triangle'] = True
            confidence_scores['ascending_triangle'] = base_confidence
        
        # Descending Triangle: horizontal support, falling resistance
        low_std = np.std(lows)
        low_mean_std = np.std(lows) * 0.7  # Tighter threshold
        if low_std < low_mean_std and high_slope < 0 and base_confidence > 0.5:
            patterns['descending_triangle'] = True
            confidence_scores['descending_triangle'] = base_confidence
            
        # Broadening patterns (expanding volatility)
        if high_slope > 0 and low_slope < 0 and base_confidence > 0.4:
            patterns['broadening_ascending'] = True
            confidence_scores['broadening_ascending'] = base_confidence
        elif high_slope < 0 and low_slope > 0 and base_confidence > 0.4:
            patterns['broadening_descending'] = True
            confidence_scores['broadening_descending'] = base_confidence
            
        return patterns, confidence_scores
    
    def detect_channel_wedge_patterns(self, df, period=20):
        """Detect channel and wedge patterns dengan confidence"""
        patterns = {
            'uptrend_channel': False,
            'downtrend_channel': False,
            'ranging_channel': False,
            'rising_wedge': False,
            'falling_wedge': False
        }
        
        confidence_scores = {}
        
        if len(df) < period * 2:
            return patterns, confidence_scores
            
        highs = df['high'].tail(period)
        lows = df['low'].tail(period)
        closes = df['close'].tail(period)
        
        # Calculate regression channels dengan confidence
        high_slope, high_r2 = self.calculate_trend_strength(highs)
        low_slope, low_r2 = self.calculate_trend_strength(lows)
        close_slope, close_r2 = self.calculate_trend_strength(closes)
        
        base_confidence = (high_r2 + low_r2 + close_r2) / 3
        
        # Uptrend Channel: both highs and lows trending up
        if (high_slope > 0 and low_slope > 0 and close_slope > 0 and 
            base_confidence > 0.6):
            patterns['uptrend_channel'] = True
            confidence_scores['uptrend_channel'] = base_confidence
            
        # Downtrend Channel: both highs and lows trending down
        if (high_slope < 0 and low_slope < 0 and close_slope < 0 and 
            base_confidence > 0.6):
            patterns['downtrend_channel'] = True
            confidence_scores['downtrend_channel'] = base_confidence
            
        # Ranging Channel: minimal slope with consistent range
        if (abs(high_slope) < 0.001 and abs(low_slope) < 0.001 and 
            base_confidence > 0.5):
            patterns['ranging_channel'] = True
            confidence_scores['ranging_channel'] = base_confidence
            
        # Rising Wedge: highs rising faster than lows
        if (high_slope > 0 and low_slope > 0 and 
            high_slope > low_slope * 1.5 and  # More strict ratio
            base_confidence > 0.5):
            patterns['rising_wedge'] = True
            confidence_scores['rising_wedge'] = base_confidence
            
        # Falling Wedge: lows falling faster than highs
        if (high_slope < 0 and low_slope < 0 and 
            abs(low_slope) > abs(high_slope) * 1.5 and  # More strict ratio
            base_confidence > 0.5):
            patterns['falling_wedge'] = True
            confidence_scores['falling_wedge'] = base_confidence
            
        return patterns, confidence_scores
    
    def detect_harmonic_patterns(self, df, period=50):
        """Enhanced harmonic pattern detection"""
        patterns = {
            'gartley': False,
            'bat': False,
            'butterfly': False,
            'crab': False,
            'shark': False
        }
        
        confidence_scores = {}
        
        if len(df) < period:
            return patterns, confidence_scores
            
        try:
            # Look for swing points
            highs = df['high'].tail(period)
            lows = df['low'].tail(period)
            
            # Find local maxima and minima
            from scipy.signal import argrelextrema
            
            high_idx = argrelextrema(highs.values, np.greater, order=3)[0]
            low_idx = argrelextrema(lows.values, np.less, order=3)[0]
            
            if len(high_idx) >= 4 and len(low_idx) >= 4:
                # Get the last 4 significant points
                last_highs = highs.iloc[high_idx[-4:]]
                last_lows = lows.iloc[low_idx[-4:]]
                
                # Calculate Fibonacci ratios
                if len(last_highs) >= 2 and len(last_lows) >= 2:
                    # Simple pattern detection based on price relationships
                    price_range = (highs.max() - lows.min()) / lows.min()
                    
                    if price_range < 0.08:
                        patterns['gartley'] = True
                        confidence_scores['gartley'] = 0.6
                    elif 0.08 <= price_range < 0.13:
                        patterns['bat'] = True
                        confidence_scores['bat'] = 0.6
                    elif 0.13 <= price_range < 0.18:
                        patterns['butterfly'] = True
                        confidence_scores['butterfly'] = 0.6
                    elif 0.18 <= price_range < 0.23:
                        patterns['crab'] = True
                        confidence_scores['crab'] = 0.6
                    else:
                        patterns['shark'] = True
                        confidence_scores['shark'] = 0.5
                        
        except Exception:
            # Fallback to simple detection
            closes = df['close'].tail(period)
            price_change = (closes.iloc[-1] - closes.iloc[0]) / closes.iloc[0]
            
            if abs(price_change) < 0.08:
                patterns['gartley'] = True
                confidence_scores['gartley'] = 0.4
            elif 0.08 <= abs(price_change) < 0.13:
                patterns['bat'] = True
                confidence_scores['bat'] = 0.4
            elif 0.13 <= abs(price_change) < 0.18:
                patterns['butterfly'] = True
                confidence_scores['butterfly'] = 0.4
            elif 0.18 <= abs(price_change) < 0.23:
                patterns['crab'] = True
                confidence_scores['crab'] = 0.4
            else:
                patterns['shark'] = True
                confidence_scores['shark'] = 0.3
            
        return patterns, confidence_scores

    def analyze_volume_profile(self, df):
        """Enhanced volume analysis dengan market context"""
        vol_mean = df['volume'].rolling(20).mean().iloc[-1]
        volume_ratio = df['volume'].iloc[-1] / vol_mean if vol_mean > 0 else 1
        
        if self.market_type == "crypto":
            if volume_ratio > 1.5: 
                return 2, volume_ratio
            elif volume_ratio > 1.2: 
                return 1, volume_ratio
            else: 
                return -1, volume_ratio
        elif self.market_type == "saham_id":
            if volume_ratio > 1.3: 
                return 2, volume_ratio
            elif volume_ratio > 1.0: 
                return 1, volume_ratio
            else: 
                return 0, volume_ratio
        else:  # forex & stocks
            if volume_ratio > 1.1: 
                return 1, volume_ratio
            else: 
                return 0, volume_ratio

    def calculate_rsi_score(self, rsi_value):
        """Market-specific RSI scoring"""
        if self.market_type == "crypto":
            if rsi_value < self.rsi_oversold:
                return 2
            elif rsi_value > self.rsi_overbought:
                return -2
            elif 40 < rsi_value < 60:
                return 1
            else:
                return 0
        else:
            if rsi_value < self.rsi_oversold:
                return 2
            elif rsi_value > self.rsi_overbought:
                return -2
            elif 35 < rsi_value < 65:
                return 1
            else:
                return 0

    def analyze(self, df):
        if len(df) < 50:
            return None
        
        current_close = df['close'].iloc[-1]
        
        # Calculate RSI
        if TALIB_AVAILABLE:
            rsi_array = talib.RSI(df['close'], timeperiod=14)
            current_rsi = rsi_array[-1] if not np.isnan(rsi_array[-1]) else 50
        else:
            price_diff = df['close'].diff()
            gain = price_diff.where(price_diff > 0, 0).rolling(14).mean()
            loss = -price_diff.where(price_diff < 0, 0).rolling(14).mean()
            rs = gain / loss if loss.iloc[-1] != 0 else 1
            current_rsi = 100 - (100 / (1 + rs)).iloc[-1] if not np.isnan(rs.iloc[-1]) else 50
        
        atr = self.calculate_atr(df)
        
        hh, hl, lh, ll = self.identify_hh_hl_lh_ll(df)
        
        ema_trend, ema_score = self.analyze_ema_cross(df)
        
        # Enhanced volume analysis
        volume_score, volume_ratio = self.analyze_volume_profile(df)
        
        # Market regime detection
        market_regime, adx_value = self.detect_market_regime(df)
        
        # Enhanced pattern detection with confidence
        triangle_patterns, triangle_confidence = self.detect_triangle_patterns(df)
        channel_wedge_patterns, channel_confidence = self.detect_channel_wedge_patterns(df)
        harmonic_patterns, harmonic_confidence = self.detect_harmonic_patterns(df)
        
        # Calculate scores with market-specific weights
        trend_score = 0
        if hh or hl:
            trend_score += 2 * self.trend_weight
        if lh or ll:
            trend_score -= 2 * self.trend_weight
        
        if ema_trend == "BULLISH":
            trend_score += ema_score * self.trend_weight
        else:
            trend_score += ema_score * self.trend_weight
        
        # Enhanced pattern scoring with confidence
        pattern_score = 0
        
        # Triangle patterns
        if triangle_patterns['ascending_triangle']:
            confidence = triangle_confidence.get('ascending_triangle', 0.5)
            pattern_score += 3 * confidence * self.pattern_weight
            
        if triangle_patterns['descending_triangle']:
            confidence = triangle_confidence.get('descending_triangle', 0.5)
            pattern_score -= 3 * confidence * self.pattern_weight
            
        if triangle_patterns['symmetrical_triangle']:
            confidence = triangle_confidence.get('symmetrical_triangle', 0.5)
            pattern_score += 1 * confidence * self.pattern_weight
        
        # Channel and wedge patterns
        if channel_wedge_patterns['uptrend_channel']:
            confidence = channel_confidence.get('uptrend_channel', 0.5)
            pattern_score += 2 * confidence * self.pattern_weight
            
        if channel_wedge_patterns['downtrend_channel']:
            confidence = channel_confidence.get('downtrend_channel', 0.5)
            pattern_score -= 2 * confidence * self.pattern_weight
            
        if channel_wedge_patterns['falling_wedge']:
            confidence = channel_confidence.get('falling_wedge', 0.5)
            pattern_score += 2 * confidence * self.pattern_weight
            
        if channel_wedge_patterns['rising_wedge']:
            confidence = channel_confidence.get('rising_wedge', 0.5)
            pattern_score -= 2 * confidence * self.pattern_weight
            
        if channel_wedge_patterns['ranging_channel']:
            confidence = channel_confidence.get('ranging_channel', 0.5)
            pattern_score += 1 * confidence * self.pattern_weight
        
        # Harmonic patterns
        for pattern, detected in harmonic_patterns.items():
            if detected:
                confidence = harmonic_confidence.get(pattern, 0.3)
                pattern_score += 1 * confidence * self.pattern_weight
        
        # Market-specific RSI scoring
        rsi_score = self.calculate_rsi_score(current_rsi)
        
        # Calculate final score
        score = trend_score + rsi_score + volume_score + pattern_score
        
        # Adjust score based on market regime
        if market_regime == "TRENDING" and abs(score) > 2:
            score *= 1.2  # Boost score in trending markets
        elif market_regime == "RANGING" and abs(score) > 3:
            score *= 0.8  # Reduce score in ranging markets
        
        action = "LONG" if score > 0 else "SHORT" if score < 0 else "NEUTRAL"
        
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
        
        all_patterns = {**triangle_patterns, **channel_wedge_patterns, **harmonic_patterns}
        detected_patterns = [pattern for pattern, detected in all_patterns.items() if detected]
        
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
            'pattern_details': all_patterns,
            'market_regime': market_regime,
            'adx_value': float(adx_value),
            'market_type': self.market_type,
            'volume_score': volume_score,
            'rsi_score': rsi_score,
            'trend_score': trend_score
        }
        
        return result
