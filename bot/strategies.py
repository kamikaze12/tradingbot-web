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
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import accuracy_score
    import optuna
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False
    print("Warning: scikit-learn or optuna not available, skipping ML features")

class TradingStrategy(ABC):
    @abstractmethod
    def analyze(self, df):
        pass

class TechnicalAnalysisStrategy(TradingStrategy):
    def __init__(self, atr_multiplier=1.5, entry_range_pct=0.015, use_ml=False):
        self.atr_multiplier = atr_multiplier
        self.entry_range_pct = entry_range_pct
        self.use_ml = use_ml and ML_AVAILABLE
        self.ml_model = None
        
    def calculate_technical_indicators(self, df):
        """Calculate comprehensive technical indicators"""
        indicators = {}
        
        # Price-based indicators
        close = df['close']
        high = df['high']
        low = df['low']
        volume = df['volume']
        
        # Trend indicators
        if TALIB_AVAILABLE:
            # Moving averages
            indicators['sma_20'] = talib.SMA(close, timeperiod=20)
            indicators['ema_12'] = talib.EMA(close, timeperiod=12)
            indicators['ema_26'] = talib.EMA(close, timeperiod=26)
            indicators['wma_14'] = talib.WMA(close, timeperiod=14)
            
            # MACD
            macd, macd_signal, macd_hist = talib.MACD(close)
            indicators['macd'] = macd
            indicators['macd_signal'] = macd_signal
            indicators['macd_hist'] = macd_hist
            
            # RSI
            indicators['rsi_14'] = talib.RSI(close, timeperiod=14)
            indicators['rsi_7'] = talib.RSI(close, timeperiod=7)
            
            # Stochastic
            slowk, slowd = talib.STOCH(high, low, close)
            indicators['stoch_k'] = slowk
            indicators['stoch_d'] = slowd
            
            # Bollinger Bands
            bb_upper, bb_middle, bb_lower = talib.BBANDS(close, timeperiod=20)
            indicators['bb_upper'] = bb_upper
            indicators['bb_middle'] = bb_middle
            indicators['bb_lower'] = bb_lower
            indicators['bb_position'] = (close - bb_lower) / (bb_upper - bb_lower)
            
            # ATR
            indicators['atr_14'] = talib.ATR(high, low, close, timeperiod=14)
            
            # ADX
            indicators['adx_14'] = talib.ADX(high, low, close, timeperiod=14)
            
            # OBV
            indicators['obv'] = talib.OBV(close, volume)
            
        else:
            # Fallback calculations
            indicators['sma_20'] = close.rolling(20).mean()
            indicators['ema_12'] = close.ewm(span=12).mean()
            indicators['ema_26'] = close.ewm(span=26).mean()
            indicators['wma_14'] = close.rolling(14).apply(
                lambda x: np.average(x, weights=np.arange(1, len(x)+1)), raw=False
            )
            
            # Simple MACD
            ema12 = close.ewm(span=12).mean()
            ema26 = close.ewm(span=26).mean()
            indicators['macd'] = ema12 - ema26
            indicators['macd_signal'] = indicators['macd'].ewm(span=9).mean()
            indicators['macd_hist'] = indicators['macd'] - indicators['macd_signal']
            
            # Simple RSI
            delta = close.diff()
            gain = delta.where(delta > 0, 0).rolling(14).mean()
            loss = (-delta).where(delta < 0, 0).rolling(14).mean()
            rs = gain / loss
            indicators['rsi_14'] = 100 - (100 / (1 + rs))
            
            # Simple ATR
            tr1 = high - low
            tr2 = abs(high - close.shift())
            tr3 = abs(low - close.shift())
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            indicators['atr_14'] = tr.rolling(14).mean()
        
        # Volume indicators
        indicators['volume_sma'] = volume.rolling(20).mean()
        indicators['volume_ratio'] = volume / indicators['volume_sma']
        
        # Price momentum
        indicators['price_change_1d'] = close.pct_change(1)
        indicators['price_change_5d'] = close.pct_change(5)
        indicators['price_change_20d'] = close.pct_change(20)
        
        # Volatility
        indicators['volatility_20d'] = close.pct_change().rolling(20).std()
        
        return indicators
    
    def detect_candlestick_patterns(self, df):
        """Detect Japanese candlestick patterns"""
        patterns = {}
        
        if TALIB_AVAILABLE and len(df) >= 5:
            open_price = df['open']
            high = df['high']
            low = df['low']
            close = df['close']
            
            # Bullish patterns
            patterns['hammer'] = talib.CDLHAMMER(open_price, high, low, close).iloc[-1]
            patterns['inverted_hammer'] = talib.CDLINVERTEDHAMMER(open_price, high, low, close).iloc[-1]
            patterns['bullish_engulfing'] = talib.CDLENGULFING(open_price, high, low, close).iloc[-1]
            patterns['morning_star'] = talib.CDLMORNINGSTAR(open_price, high, low, close).iloc[-1]
            patterns['piercing'] = talib.CDLPIERCING(open_price, high, low, close).iloc[-1]
            
            # Bearish patterns
            patterns['hanging_man'] = talib.CDLHANGINGMAN(open_price, high, low, close).iloc[-1]
            patterns['shooting_star'] = talib.CDLSHOOTINGSTAR(open_price, high, low, close).iloc[-1]
            patterns['bearish_engulfing'] = talib.CDLENGULFING(open_price, high, low, close).iloc[-1]
            patterns['evening_star'] = talib.CDLEVENINGSTAR(open_price, high, low, close).iloc[-1]
            patterns['dark_cloud_cover'] = talib.CDLDARKCLOUDCOVER(open_price, high, low, close).iloc[-1]
        
        return patterns
    
    def identify_support_resistance(self, df, window=20):
        """Identify support and resistance levels"""
        if len(df) < window * 2:
            return None, None
            
        highs = df['high'].tail(window * 2)
        lows = df['low'].tail(window * 2)
        
        # Find local maxima and minima
        resistance_levels = []
        support_levels = []
        
        for i in range(window, len(highs) - window):
            if highs.iloc[i] == highs.iloc[i-window:i+window].max():
                resistance_levels.append(highs.iloc[i])
            if lows.iloc[i] == lows.iloc[i-window:i+window].min():
                support_levels.append(lows.iloc[i])
        
        current_price = df['close'].iloc[-1]
        
        # Find nearest support and resistance
        nearest_resistance = min([r for r in resistance_levels if r > current_price], default=None)
        nearest_support = max([s for s in support_levels if s < current_price], default=None)
        
        return nearest_support, nearest_resistance
    
    def calculate_momentum_score(self, df, indicators):
        """Calculate momentum-based score"""
        score = 0
        
        # RSI scoring
        rsi_14 = indicators['rsi_14'].iloc[-1] if not pd.isna(indicators['rsi_14'].iloc[-1]) else 50
        if 30 < rsi_14 < 70:
            score += 1
        elif rsi_14 < 30:
            score += 2  # Oversold
        elif rsi_14 > 70:
            score -= 2  # Overbought
        
        # MACD scoring
        macd_hist = indicators['macd_hist'].iloc[-1] if not pd.isna(indicators['macd_hist'].iloc[-1]) else 0
        if macd_hist > 0:
            score += 2
        else:
            score -= 1
            
        # Price momentum
        price_change_5d = indicators['price_change_5d'].iloc[-1] if not pd.isna(indicators['price_change_5d'].iloc[-1]) else 0
        if price_change_5d > 0.02:  # +2%
            score += 2
        elif price_change_5d < -0.02:  # -2%
            score -= 2
            
        # Volume confirmation
        volume_ratio = indicators['volume_ratio'].iloc[-1] if not pd.isna(indicators['volume_ratio'].iloc[-1]) else 1
        if volume_ratio > 1.5:
            score += 2
        elif volume_ratio < 0.7:
            score -= 1
            
        return score
    
    def calculate_trend_score(self, df, indicators):
        """Calculate trend-based score"""
        score = 0
        
        # Moving average alignment
        if len(df) >= 26:
            ema_12 = indicators['ema_12'].iloc[-1]
            ema_26 = indicators['ema_26'].iloc[-1]
            sma_20 = indicators['sma_20'].iloc[-1]
            current_price = df['close'].iloc[-1]
            
            # Bullish: Price > EMA12 > EMA26 > SMA20
            if current_price > ema_12 > ema_26 > sma_20:
                score += 3
            # Bearish: Price < EMA12 < EMA26 < SMA20
            elif current_price < ema_12 < ema_26 < sma_20:
                score -= 3
            # Mixed but positive
            elif current_price > ema_12 and ema_12 > ema_26:
                score += 1
            # Mixed but negative
            elif current_price < ema_12 and ema_12 < ema_26:
                score -= 1
        
        # ADX for trend strength
        if 'adx_14' in indicators:
            adx = indicators['adx_14'].iloc[-1] if not pd.isna(indicators['adx_14'].iloc[-1]) else 0
            if adx > 25:  # Strong trend
                score += 2
        
        return score
    
    def calculate_pattern_score(self, df, indicators):
        """Calculate score based on chart patterns"""
        score = 0
        
        # Candlestick patterns
        candle_patterns = self.detect_candlestick_patterns(df)
        bullish_candle_count = sum(1 for pattern, value in candle_patterns.items() 
                                 if value > 0 and 'bullish' in pattern.lower())
        bearish_candle_count = sum(1 for pattern, value in candle_patterns.items() 
                                 if value > 0 and 'bearish' in pattern.lower())
        
        score += bullish_candle_count * 2
        score -= bearish_candle_count * 2
        
        # Support/Resistance analysis
        support, resistance = self.identify_support_resistance(df)
        current_price = df['close'].iloc[-1]
        
        if support and resistance:
            price_position = (current_price - support) / (resistance - support)
            # Near support - potential bounce
            if price_position < 0.3:
                score += 2
            # Near resistance - potential rejection
            elif price_position > 0.7:
                score -= 2
        
        # Bollinger Band position
        if 'bb_position' in indicators:
            bb_pos = indicators['bb_position'].iloc[-1] if not pd.isna(indicators['bb_position'].iloc[-1]) else 0.5
            if bb_pos < 0.2:  # Near lower band - oversold
                score += 2
            elif bb_pos > 0.8:  # Near upper band - overbought
                score -= 2
        
        return score
    
    def train_ml_model(self, X, y):
        """Train ML model for prediction"""
        if not self.use_ml:
            return None
            
        try:
            X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
            model = RandomForestClassifier(n_estimators=100, random_state=42)
            model.fit(X_train, y_train)
            
            # Evaluate model
            y_pred = model.predict(X_test)
            accuracy = accuracy_score(y_test, y_pred)
            print(f"ML Model trained with accuracy: {accuracy:.2f}")
            
            return model
        except Exception as e:
            print(f"ML training failed: {e}")
            return None
    
    def analyze(self, df):
        """Main analysis method with enhanced technical analysis"""
        if len(df) < 50:
            return None
        
        try:
            # Calculate technical indicators
            indicators = self.calculate_technical_indicators(df)
            
            # Get current values
            current_close = df['close'].iloc[-1]
            current_volume = df['volume'].iloc[-1]
            
            # Calculate scores from different aspects
            momentum_score = self.calculate_momentum_score(df, indicators)
            trend_score = self.calculate_trend_score(df, indicators)
            pattern_score = self.calculate_pattern_score(df, indicators)
            
            # Combined score with weights
            total_score = (
                momentum_score * 0.4 +
                trend_score * 0.4 +
                pattern_score * 0.2
            )
            
            # Determine action based on score
            if total_score >= 3:
                action = "LONG"
                confidence = min(total_score / 10.0, 1.0)
            elif total_score <= -3:
                action = "SHORT" 
                confidence = min(abs(total_score) / 10.0, 1.0)
            else:
                action = "NEUTRAL"
                confidence = 0.0
            
            # Calculate position sizing and levels
            atr = indicators['atr_14'].iloc[-1] if not pd.isna(indicators['atr_14'].iloc[-1]) else current_close * 0.02
            
            if action in ["LONG", "SHORT"]:
                if action == "LONG":
                    ideal_entry = current_close
                    sl = ideal_entry - (atr * self.atr_multiplier)
                    tp1 = ideal_entry + (atr * self.atr_multiplier)
                    tp2 = ideal_entry + (atr * self.atr_multiplier * 2)
                    tp3 = ideal_entry + (atr * self.atr_multiplier * 3)
                else:  # SHORT
                    ideal_entry = current_close
                    sl = ideal_entry + (atr * self.atr_multiplier)
                    tp1 = ideal_entry - (atr * self.atr_multiplier)
                    tp2 = ideal_entry - (atr * self.atr_multiplier * 2)
                    tp3 = ideal_entry - (atr * self.atr_multiplier * 3)
                
                entry_low = ideal_entry * (1 - self.entry_range_pct)
                entry_high = ideal_entry * (1 + self.entry_range_pct)
            else:
                ideal_entry = entry_low = entry_high = sl = tp1 = tp2 = tp3 = None
            
            # Support/Resistance levels
            support, resistance = self.identify_support_resistance(df)
            
            # Compile results
            result = {
                'action': action,
                'confidence': round(confidence, 2),
                'ideal_entry': float(ideal_entry) if ideal_entry else None,
                'entry_low': float(entry_low) if entry_low else None,
                'entry_high': float(entry_high) if entry_high else None,
                'tp1': float(tp1) if tp1 else None,
                'tp2': float(tp2) if tp2 else None,
                'tp3': float(tp3) if tp3 else None,
                'sl': float(sl) if sl else None,
                'current_price': float(current_close),
                'volume': float(current_volume),
                'rsi_14': float(indicators['rsi_14'].iloc[-1]) if not pd.isna(indicators['rsi_14'].iloc[-1]) else 50,
                'macd_hist': float(indicators['macd_hist'].iloc[-1]) if not pd.isna(indicators['macd_hist'].iloc[-1]) else 0,
                'atr': float(atr),
                'score': round(total_score, 2),
                'momentum_score': momentum_score,
                'trend_score': trend_score,
                'pattern_score': pattern_score,
                'support_level': float(support) if support else None,
                'resistance_level': float(resistance) if resistance else None,
                'volume_ratio': float(indicators['volume_ratio'].iloc[-1]) if not pd.isna(indicators['volume_ratio'].iloc[-1]) else 1,
            }
            
            return result
            
        except Exception as e:
            print(f"Error in technical analysis: {e}")
            return None
