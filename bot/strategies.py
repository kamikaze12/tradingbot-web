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

    # =========================================================
    # PHASE 2 ENHANCEMENTS - ADVANCED CANDLESTICK PATTERNS
    # =========================================================
    def detect_candlestick_patterns(self, df, period=10):
        """Detect advanced candlestick patterns"""
        patterns = {
            'doji': False, 'hammer': False, 'shooting_star': False,
            'bullish_engulfing': False, 'bearish_engulfing': False,
            'morning_star': False, 'evening_star': False,
            'three_white_soldiers': False, 'three_black_crows': False,
            'bullish_harami': False, 'bearish_harami': False
        }
        
        if len(df) < period:
            return patterns
        
        # Get recent candlesticks
        for i in range(1, min(5, len(df)-1)):
            open_prev, high_prev, low_prev, close_prev = df[['open','high','low','close']].iloc[-i-1]
            open_curr, high_curr, low_curr, close_curr = df[['open','high','low','close']].iloc[-i]
            
            # Calculate candle properties
            body_curr = abs(close_curr - open_curr)
            range_curr = high_curr - low_curr
            body_prev = abs(close_prev - open_prev)
            
            # Doji Pattern - very small body
            if range_curr > 0 and body_curr/range_curr < 0.1:
                patterns['doji'] = True
                
            # Hammer Pattern - small body at top with long lower wick
            lower_wick = min(open_curr, close_curr) - low_curr
            upper_wick = high_curr - max(open_curr, close_curr)
            if (body_curr > 0 and 
                lower_wick > 2 * body_curr and 
                upper_wick < 0.3 * body_curr and
                close_curr > open_curr):  # Bullish hammer
                patterns['hammer'] = True
                
            # Shooting Star - small body at bottom with long upper wick
            if (body_curr > 0 and 
                upper_wick > 2 * body_curr and 
                lower_wick < 0.3 * body_curr and
                close_curr < open_curr):  # Bearish shooting star
                patterns['shooting_star'] = True
                
            # Bullish Engulfing
            if (close_prev < open_prev and close_curr > open_curr and
                open_curr < close_prev and close_curr > open_prev):
                patterns['bullish_engulfing'] = True
                
            # Bearish Engulfing
            if (close_prev > open_prev and close_curr < open_curr and
                open_curr > close_prev and close_curr < open_prev):
                patterns['bearish_engulfing'] = True
                
            # Bullish Harami
            if (close_prev < open_prev and close_curr > open_curr and
                open_curr > close_prev and close_curr < open_prev):
                patterns['bullish_harami'] = True
                
            # Bearish Harami
            if (close_prev > open_prev and close_curr < open_curr and
                open_curr < close_prev and close_curr > open_prev):
                patterns['bearish_harami'] = True
                
            # Three White Soldiers (need 3 consecutive bullish candles)
            if i <= len(df) - 3:
                opens = df['open'].iloc[-i-2:-i+1].values
                closes = df['close'].iloc[-i-2:-i+1].values
                if all(closes > opens) and all(closes[1:] > closes[:-1]):
                    patterns['three_white_soldiers'] = True
                    
            # Three Black Crows (need 3 consecutive bearish candles)
            if i <= len(df) - 3:
                opens = df['open'].iloc[-i-2:-i+1].values
                closes = df['close'].iloc[-i-2:-i+1].values
                if all(closes < opens) and all(closes[1:] < closes[:-1]):
                    patterns['three_black_crows'] = True
                    
        return patterns

    # =========================================================
    # PHASE 2 ENHANCEMENTS - ADVANCED MOMENTUM INDICATORS
    # =========================================================
    def calculate_momentum_indicators(self, df):
        """Calculate advanced momentum indicators"""
        indicators = {
            'macd_signal': 0, 'stochastic_signal': 0, 'momentum_score': 0,
            'williams_r': 0, 'cci': 0, 'roc': 0, 'momentum_quality': 'NEUTRAL'
        }
        
        if len(df) < 26:
            return indicators
            
        try:
            # MACD Calculation
            ema_12 = df['close'].ewm(span=12).mean()
            ema_26 = df['close'].ewm(span=26).mean()
            macd = ema_12 - ema_26
            signal = macd.ewm(span=9).mean()
            histogram = macd - signal
            
            # MACD Signal
            if macd.iloc[-1] > signal.iloc[-1] and histogram.iloc[-1] > 0:
                indicators['macd_signal'] += 3
            elif macd.iloc[-1] < signal.iloc[-1] and histogram.iloc[-1] < 0:
                indicators['macd_signal'] -= 3
            
            # Stochastic Oscillator (simplified)
            high_14 = df['high'].rolling(14).max()
            low_14 = df['low'].rolling(14).min()
            k = 100 * ((df['close'] - low_14) / (high_14 - low_14))
            d = k.rolling(3).mean()
            if k.iloc[-1] > 80:
                indicators['stochastic_signal'] -= 2
            elif k.iloc[-1] < 20:
                indicators['stochastic_signal'] += 2
            
            # Williams %R
            indicators['williams_r'] = -100 * ((high_14.iloc[-1] - df['close'].iloc[-1]) / (high_14.iloc[-1] - low_14.iloc[-1]))
            
            # CCI (Commodity Channel Index)
            typical_price = (df['high'] + df['low'] + df['close']) / 3
            sma_tp = typical_price.rolling(20).mean()
            mad = typical_price.rolling(20).apply(lambda x: np.abs(x - x.mean()).mean())
            indicators['cci'] = (typical_price - sma_tp) / (0.015 * mad)
            
            # ROC (Rate of Change)
            indicators['roc'] = (df['close'].iloc[-1] - df['close'].shift(12).iloc[-1]) / df['close'].shift(12).iloc[-1] * 100
            
            # Momentum Score Aggregation
            indicators['momentum_score'] = indicators['macd_signal'] + indicators['stochastic_signal']
            if indicators['cci'].iloc[-1] > 100:
                indicators['momentum_score'] += 1
            elif indicators['cci'].iloc[-1] < -100:
                indicators['momentum_score'] -= 1
                
            if indicators['roc'] > 0:
                indicators['momentum_score'] += 1
            else:
                indicators['momentum_score'] -= 1
                
            # Momentum Quality
            if abs(indicators['momentum_score']) > 4:
                indicators['momentum_quality'] = 'STRONG'
            elif abs(indicators['momentum_score']) > 2:
                indicators['momentum_quality'] = 'MODERATE'
            
        except Exception as e:
            print(f"Error in momentum indicators: {e}")
            
        return indicators

    def detect_market_regime(self, df, period=20):
        """Detect market regime: trending, ranging, volatile"""
        regime = {
            'market_phase': 'ACCUMULATION',
            'volatility_level': 'NORMAL',
            'regime_score': 0
        }
        
        if len(df) < period * 2:
            return regime
            
        # Volatility calculation
        returns = df['close'].pct_change()
        volatility = returns.tail(period).std() * np.sqrt(252)  # Annualized
        
        if volatility > 0.5:
            regime['volatility_level'] = 'HIGH'
            regime['regime_score'] -= 2
        elif volatility < 0.2:
            regime['volatility_level'] = 'LOW'
            regime['regime_score'] += 1
        else:
            regime['volatility_level'] = 'NORMAL'
        
        # ADX for trend strength (simplified without TA-LIB)
        plus_di = 100 * (df['high'].diff().clip(lower=0) / df['close'].rolling(period).std())
        minus_di = 100 * (df['low'].diff().clip(upper=0).abs() / df['close'].rolling(period).std())
        adx = ((plus_di - minus_di).abs() / (plus_di + minus_di).abs()).rolling(period).mean() * 100
        
        if adx.iloc[-1] > 25:
            regime['market_phase'] = 'TRENDING'
            regime['regime_score'] += 2 if df['close'].iloc[-1] > df['close'].rolling(period).mean().iloc[-1] else -2
        else:
            regime['market_phase'] = 'RANGING'
            regime['regime_score'] += 1
        
        return regime

    # =========================================================
    # PHASE 2 ENHANCEMENTS - RISK METRICS
    # =========================================================
    def calculate_risk_metrics(self, df, analysis_result):
        """Calculate enhanced risk metrics"""
        risk = {
            'reward_ratio': 0,
            'optimal_position_size': 0.1,
            'volatility_adjustment': 0,
            'drawdown_risk': 'LOW',
            'risk_category': 'LOW',
            'position_score': analysis_result.get('score', 0),
            'risk_adjusted_score': 0
        }
        
        if len(df) < 50:
            return risk
            
        try:
            # Reward Ratio with safety check
            entry = analysis_result.get('ideal_entry', 0)
            tp1 = analysis_result.get('tp1', 0)
            sl = analysis_result.get('sl', 0)
            if entry == 0 or sl == entry:
                risk['reward_ratio'] = 0
            else:
                risk['reward_ratio'] = abs((tp1 - entry) / (entry - sl))
            
            # Optimal Position Size based on ATR
            atr = analysis_result.get('atr', 0.01)
            current_price = analysis_result.get('current_price', entry)  # Use entry as fallback
            if current_price > 0 and atr > 0:
                risk['optimal_position_size'] = min(0.02 / (atr / current_price), 0.2)  # 2% risk max, cap at 20%
            else:
                risk['optimal_position_size'] = 0.1  # Default
            
            # Volatility Adjustment
            volatility = (df['high'] - df['low']) / df['close']
            volatility_ratio = volatility.tail(20).mean()
            if volatility_ratio > 0.05:
                risk['volatility_adjustment'] -= 2
                risk['drawdown_risk'] = 'HIGH'
                risk['risk_category'] = 'HIGH'
            elif volatility_ratio > 0.03:
                risk['volatility_adjustment'] -= 1
                risk['drawdown_risk'] = 'MEDIUM'
                risk['risk_category'] = 'MEDIUM'
            else:
                risk['volatility_adjustment'] += 1
                risk['drawdown_risk'] = 'LOW'
                risk['risk_category'] = 'LOW'
                
            # Recent Drawdown Analysis
            rolling_max = df['close'].rolling(20).max()
            current_drawdown = (df['close'] - rolling_max) / rolling_max
            max_drawdown = current_drawdown.min()
            
            if max_drawdown < -0.15:  # 15% drawdown
                risk['volatility_adjustment'] -= 1
                
            # Combine with original score
            original_score = analysis_result.get('score', 0)
            risk['risk_adjusted_score'] = (
                original_score + 
                risk['position_score'] + 
                risk['volatility_adjustment']
            )
            
        except Exception as e:
            print(f"Error calculating risk metrics: {e}")
            
        return risk

    # =========================================================
    # PHASE 2 ENHANCEMENTS - SUPPORT/RESISTANCE DETECTION
    # =========================================================
    def detect_support_resistance(self, df, window=20):
        """Detect key support and resistance levels"""
        levels = {
            'support_levels': [],
            'resistance_levels': [],
            'strong_support': None,
            'strong_resistance': None,
            'breakout_level': None,
            'consolidation_zone': False
        }
        
        if len(df) < window * 2:
            return levels
            
        try:
            # Find local minima and maxima
            highs = df['high'].tail(window * 3)
            lows = df['low'].tail(window * 3)
            
            # Simple pivot point detection
            for i in range(window, len(highs) - window):
                if highs.iloc[i] == highs.iloc[i-window:i+window].max():
                    levels['resistance_levels'].append(highs.iloc[i])
                if lows.iloc[i] == lows.iloc[i-window:i+window].min():
                    levels['support_levels'].append(lows.iloc[i])
                    
            # Remove duplicates and sort
            levels['support_levels'] = sorted(list(set(levels['support_levels'])))
            levels['resistance_levels'] = sorted(list(set(levels['resistance_levels'])))
            
            # Find strong levels (clustered)
            if levels['support_levels']:
                levels['strong_support'] = levels['support_levels'][0]  # Nearest support
            if levels['resistance_levels']:
                levels['strong_resistance'] = levels['resistance_levels'][-1]  # Nearest resistance
                
            # Check for consolidation
            price_range = df['high'].tail(window).max() - df['low'].tail(window).min()
            avg_range = (df['high'] - df['low']).tail(window).mean()
            
            if price_range < 2 * avg_range:  # Tight range indicates consolidation
                levels['consolidation_zone'] = True
                levels['breakout_level'] = levels['strong_resistance'] if levels['strong_resistance'] else None
                
        except Exception as e:
            print(f"Error detecting support/resistance: {e}")
            
        return levels

    def analyze(self, df):
        """Main analysis method with enhanced pattern recognition"""
        if len(df) < 50:
            return None
        
        current_close = df['close'].iloc[-1]
        
        # Calculate RSI with fallback
        if TALIB_AVAILABLE:
            rsi_array = talib.RSI(df['close'], timeperiod=14)
            current_rsi = rsi_array[-1]
        else:
            # Simple RSI fallback
            price_diff = df['close'].diff()
            gain = price_diff.where(price_diff > 0, 0).rolling(14).mean()
            loss = -price_diff.where(price_diff < 0, 0).rolling(14).mean()
            rs = gain / loss if loss.iloc[-1] != 0 else 1
            current_rsi = 100 - (100 / (1 + rs)).iloc[-1] if not np.isnan(rs.iloc[-1]) else 50
        
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
        
        # PHASE 2 ENHANCEMENTS - NEW INDICATORS
        candlestick_patterns = self.detect_candlestick_patterns(df)
        momentum_indicators = self.calculate_momentum_indicators(df)
        market_regime = self.detect_market_regime(df)
        support_resistance = self.detect_support_resistance(df)
        
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
                
        # PHASE 2 ENHANCEMENTS - CANDLESTICK PATTERN SCORING
        candlestick_score = 0
        bullish_candles = ['hammer', 'bullish_engulfing', 'morning_star', 'three_white_soldiers', 'bullish_harami']
        bearish_candles = ['shooting_star', 'bearish_engulfing', 'evening_star', 'three_black_crows', 'bearish_harami']
        
        for pattern in bullish_candles:
            if candlestick_patterns.get(pattern, False):
                candlestick_score += 2
                
        for pattern in bearish_candles:
            if candlestick_patterns.get(pattern, False):
                candlestick_score -= 2
        
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
        
        # PHASE 2 ENHANCEMENTS - COMBINED SCORING
        # Base score from original strategy
        base_score = trend_score + rsi_score + volume_score + pattern_score
        
        # Enhanced scoring with new indicators
        momentum_score = momentum_indicators['momentum_score']
        regime_score = market_regime['regime_score']
        candlestick_adjustment = candlestick_score
        
        # Total enhanced score
        enhanced_score = base_score + momentum_score + regime_score + candlestick_adjustment
        
        # Determine action based on enhanced score
        action = "LONG" if enhanced_score > 0 else "SHORT" if enhanced_score < 0 else "NEUTRAL"
        
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
        
        # PHASE 2 ENHANCEMENTS - RISK METRICS CALCULATION
        # Prepare initial result for risk calculation (FIX: Tambahkan current_price)
        initial_result = {
            'action': action,
            'ideal_entry': ideal_entry,
            'tp1': tp1,
            'sl': sl,
            'score': enhanced_score,
            'atr': atr,
            'current_price': float(current_close)  # FIX: Tambahkan ini untuk hindari KeyError
        }
        
        risk_metrics = self.calculate_risk_metrics(df, initial_result)
        
        # Final risk-adjusted score
        final_score = risk_metrics['risk_adjusted_score']
        
        # Update action if risk adjustment changes direction
        if final_score > 0 and enhanced_score <= 0:
            action = "LONG"
        elif final_score < 0 and enhanced_score >= 0:
            action = "SHORT"
        elif final_score == 0:
            action = "NEUTRAL"
        
        # Compile pattern information
        all_patterns = {**triangle_patterns, **channel_wedge_patterns, **harmonic_patterns, **candlestick_patterns}
        detected_patterns = [pattern for pattern, detected in all_patterns.items() if detected]
        
        # Result (Tambahkan .item() untuk handle np scalar/array size 1)
        def to_python_scalar(val):
            if isinstance(val, np.ndarray) and val.size == 1:
                return val.item()
            return val
        
        result = {
            'action': action,
            'ideal_entry': to_python_scalar(float(ideal_entry)) if ideal_entry is not None else None,
            'entry_low': to_python_scalar(float(entry_low)) if entry_low is not None else None,
            'entry_high': to_python_scalar(float(entry_high)) if entry_high is not None else None,
            'tp1': to_python_scalar(float(tp1)) if tp1 is not None else None,
            'tp2': to_python_scalar(float(tp2)) if tp2 is not None else None,
            'tp3': to_python_scalar(float(tp3)) if tp3 is not None else None,
            'sl': to_python_scalar(float(sl)) if sl is not None else None,
            'current_price': to_python_scalar(float(current_close)),
            'rsi': to_python_scalar(float(current_rsi)),
            'trend': 'BULLISH' if trend_score > 0 else 'BEARISH' if trend_score < 0 else 'NEUTRAL',
            'volume_ratio': to_python_scalar(float(volume_ratio)),
            'score': int(to_python_scalar(final_score)),  # Use risk-adjusted final score
            'atr': to_python_scalar(float(atr)),
            'hh': hh,
            'hl': hl,
            'lh': lh,
            'll': ll,
            'ema_trend': ema_trend,
            'ema_score': ema_score,
            'pattern_score': pattern_score,
            'detected_patterns': detected_patterns,
            'pattern_details': all_patterns,
            
            # PHASE 2 ENHANCEMENTS - NEW FIELDS
            'candlestick_patterns': candlestick_patterns,
            'momentum_indicators': momentum_indicators,
            'market_regime': market_regime,
            'support_resistance': support_resistance,
            'risk_metrics': risk_metrics,
            'base_score': int(to_python_scalar(base_score)),
            'enhanced_score': int(to_python_scalar(enhanced_score)),
            'final_score': int(to_python_scalar(final_score)),
            'momentum_quality': momentum_indicators.get('momentum_quality', 'NEUTRAL'),
            'risk_category': risk_metrics.get('risk_category', 'LOW'),
            'optimal_position_size': risk_metrics.get('optimal_position_size', 0.1),
            'reward_ratio': risk_metrics.get('reward_ratio', 0),
            'market_phase': market_regime.get('market_phase', 'ACCUMULATION')
        }
        
        return result
