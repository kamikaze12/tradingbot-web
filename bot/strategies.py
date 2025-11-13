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
    from sklearn.preprocessing import StandardScaler
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False
    print("Warning: scikit-learn not available, skipping ML features. Install with pip install scikit-learn")

import yfinance as yf
from scipy.signal import argrelextrema
from scipy.stats import linregress

# =============================================
# DYNAMIC RISK ENGINE - PHASE 2 ENHANCED
# =============================================

class DynamicRiskEngine:
    """Enhanced dynamic risk management engine"""
    
    def __init__(self):
        self.risk_profiles = {
            'LOW': {'max_position_size': 0.1, 'max_drawdown': 0.02, 'volatility_threshold': 0.01},
            'MEDIUM': {'max_position_size': 0.07, 'max_drawdown': 0.035, 'volatility_threshold': 0.02},
            'HIGH': {'max_position_size': 0.04, 'max_drawdown': 0.05, 'volatility_threshold': 0.03},
            'VERY_HIGH': {'max_position_size': 0.02, 'max_drawdown': 0.08, 'volatility_threshold': 0.05}
        }
        
    def calculate_dynamic_position_size(self, balance, current_price, risk_score, volatility, correlation_penalty=0):
        """Calculate dynamic position size based on risk assessment"""
        # Determine risk profile based on score and volatility
        risk_profile = self._determine_risk_profile(risk_score, volatility)
        base_size = self.risk_profiles[risk_profile]['max_position_size']
        
        # Apply correlation penalty
        adjusted_size = base_size * (1 - correlation_penalty)
        
        # Calculate position size in units
        position_value = balance * adjusted_size
        position_size = position_value / current_price
        
        return {
            'position_size': position_size,
            'position_value': position_value,
            'risk_profile': risk_profile,
            'base_size_percent': base_size * 100,
            'adjusted_size_percent': adjusted_size * 100
        }
    
    def _determine_risk_profile(self, risk_score, volatility):
        """Determine risk profile based on score and volatility"""
        abs_score = abs(risk_score)
        
        if volatility > 0.04 or abs_score >= 8:
            return 'VERY_HIGH'
        elif volatility > 0.025 or abs_score >= 6:
            return 'HIGH'
        elif volatility > 0.015 or abs_score >= 4:
            return 'MEDIUM'
        else:
            return 'LOW'
    
    def calculate_stop_loss_level(self, entry_price, action, volatility, risk_profile):
        """Calculate dynamic stop loss level"""
        risk_params = self.risk_profiles[risk_profile]
        
        if action == "LONG":
            # Untuk LONG: SL di bawah entry
            sl_distance = entry_price * (volatility * 2 + risk_params['max_drawdown'])
            stop_loss = entry_price - sl_distance
        else:
            # Untuk SHORT: SL di atas entry
            sl_distance = entry_price * (volatility * 2 + risk_params['max_drawdown'])
            stop_loss = entry_price + sl_distance
            
        return max(stop_loss, 0.0001)  # Ensure positive price
    
    def calculate_take_profit_levels(self, entry_price, action, stop_loss, volatility):
        """Calculate dynamic take profit levels"""
        risk_reward_ratios = [1.5, 2.5, 4.0]  # RR ratios untuk TP1, TP2, TP3
        
        if action == "LONG":
            risk_amount = entry_price - stop_loss
            take_profits = [entry_price + (risk_amount * rr) for rr in risk_reward_ratios]
        else:
            risk_amount = stop_loss - entry_price
            take_profits = [entry_price - (risk_amount * rr) for rr in risk_reward_ratios]
            
        return take_profits
    
    def assess_portfolio_risk(self, current_positions, market_conditions):
        """Assess overall portfolio risk"""
        total_exposure = sum(pos.get('exposure', 0) for pos in current_positions)
        max_drawdown = max(pos.get('drawdown', 0) for pos in current_positions)
        avg_correlation = self._calculate_portfolio_correlation(current_positions)
        
        risk_metrics = {
            'total_exposure': total_exposure,
            'max_drawdown': max_drawdown,
            'avg_correlation': avg_correlation,
            'concentration_risk': self._calculate_concentration_risk(current_positions),
            'liquidity_risk': market_conditions.get('liquidity', 1.0)
        }
        
        # Calculate overall portfolio risk score
        risk_score = (
            risk_metrics['total_exposure'] * 0.3 +
            risk_metrics['max_drawdown'] * 0.25 +
            risk_metrics['avg_correlation'] * 0.2 +
            risk_metrics['concentration_risk'] * 0.15 +
            risk_metrics['liquidity_risk'] * 0.1
        )
        
        risk_metrics['overall_risk_score'] = risk_score
        risk_metrics['recommendation'] = self._generate_risk_recommendation(risk_score)
        
        return risk_metrics
    
    def _calculate_portfolio_correlation(self, positions):
        """Calculate average correlation between positions"""
        if len(positions) < 2:
            return 0.0
            
        # Simplified correlation calculation
        # In real implementation, use actual price correlations
        return 0.3  # Placeholder
    
    def _calculate_concentration_risk(self, positions):
        """Calculate concentration risk in portfolio"""
        if not positions:
            return 0.0
            
        exposures = [pos.get('exposure', 0) for pos in positions]
        total_exposure = sum(exposures)
        
        if total_exposure == 0:
            return 0.0
            
        # Calculate Herfindahl index for concentration
        herfindahl = sum((exp / total_exposure) ** 2 for exp in exposures)
        return herfindahl
    
    def _generate_risk_recommendation(self, risk_score):
        """Generate risk management recommendations"""
        if risk_score > 0.7:
            return "REDUCE_POSITIONS"
        elif risk_score > 0.5:
            return "HEDGE_POSITIONS"
        elif risk_score > 0.3:
            return "MONITOR_CLOSELY"
        else:
            return "NORMAL_OPERATIONS"

# =============================================
# BASE STRATEGY CLASS
# =============================================

class TradingStrategy(ABC):
    @abstractmethod
    def analyze(self, df):
        pass

# =============================================
# ML STRATEGY ENHANCER - PHASE 2
# =============================================

class MLStrategyEnhancer:
    """Machine Learning enhancement for strategy validation"""
    def __init__(self):
        self.model = None
        self.scaler = StandardScaler()
        self.is_trained = False
        
    def prepare_features(self, df):
        """Prepare features for ML model - ADVANCED FEATURE ENGINEERING"""
        features = []
        
        # Price-based features
        if len(df) > 20:
            # RSI
            rsi = self._calculate_rsi(df['close'])
            features.append(rsi)
            
            # Moving averages
            sma_20 = df['close'].rolling(20).mean().iloc[-1]
            sma_50 = df['close'].rolling(50).mean().iloc[-1]
            features.extend([sma_20, sma_50, sma_20 - sma_50])
            
            # Volatility
            volatility = df['close'].pct_change().std() * np.sqrt(252)
            features.append(volatility)
            
            # Volume features
            volume_sma = df['volume'].rolling(20).mean().iloc[-1]
            volume_ratio = df['volume'].iloc[-1] / volume_sma if volume_sma > 0 else 1
            features.append(volume_ratio)
            
            # Price position in recent range
            high_20 = df['high'].rolling(20).max().iloc[-1]
            low_20 = df['low'].rolling(20).min().iloc[-1]
            price_position = (df['close'].iloc[-1] - low_20) / (high_20 - low_20) if (high_20 - low_20) > 0 else 0.5
            features.append(price_position)
            
            # Momentum features
            momentum_5 = (df['close'].iloc[-1] / df['close'].iloc[-5] - 1) * 100
            momentum_10 = (df['close'].iloc[-1] / df['close'].iloc[-10] - 1) * 100
            features.extend([momentum_5, momentum_10])
            
            # ATR
            atr = self._calculate_atr(df)
            features.append(atr)
            
            # MACD
            macd = self._calculate_macd(df['close'])
            features.append(macd)
        
        return np.array(features).reshape(1, -1) if features else None
    
    def predict_confidence(self, df):
        """Predict confidence score using ML"""
        if not ML_AVAILABLE or not self.is_trained:
            return 0.5  # Default medium confidence
            
        try:
            features = self.prepare_features(df)
            if features is not None:
                features_scaled = self.scaler.transform(features)
                confidence = self.model.predict_proba(features_scaled)[0][1]
                return float(confidence)
        except Exception as e:
            print(f"ML prediction error: {e}")
            
        return 0.5
    
    def _calculate_rsi(self, prices, period=14):
        """Calculate RSI"""
        if len(prices) < period + 1:
            return 50
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs)).iloc[-1] if not np.isnan(rs.iloc[-1]) and loss.iloc[-1] != 0 else 50

    def _calculate_atr(self, df, period=14):
        """Calculate ATR"""
        try:
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

    def _calculate_macd(self, prices):
        """Calculate MACD"""
        try:
            if len(prices) < 26:
                return 0
            exp1 = prices.ewm(span=12).mean()
            exp2 = prices.ewm(span=26).mean()
            macd = exp1 - exp2
            return macd.iloc[-1]
        except:
            return 0

# =============================================
# MAIN TECHNICAL ANALYSIS STRATEGY - PHASE 2 ENHANCED
# =============================================

class TechnicalAnalysisStrategy(TradingStrategy):
    def __init__(self, market_type="crypto", atr_multiplier=1.0, entry_range_pct=0.02):
        self.market_type = market_type
        self.atr_multiplier = atr_multiplier
        self.entry_range_pct = entry_range_pct
        self.ml_enhancer = MLStrategyEnhancer()
        self.risk_engine = DynamicRiskEngine()
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
            self.volatility_threshold = 0.02
        elif self.market_type == "forex":
            self.rsi_oversold = 30
            self.rsi_overbought = 70
            self.volume_threshold = 1.1
            self.adx_trend_threshold = 25
            self.pattern_weight = 1.0
            self.trend_weight = 1.0
            self.volatility_threshold = 0.005
        elif self.market_type == "saham_id":
            self.rsi_oversold = 35
            self.rsi_overbought = 65
            self.volume_threshold = 1.2
            self.adx_trend_threshold = 20
            self.pattern_weight = 1.5
            self.trend_weight = 1.5
            self.volatility_threshold = 0.01
        elif self.market_type == "stocks_international":
            self.rsi_oversold = 30
            self.rsi_overbought = 70
            self.volume_threshold = 1.2
            self.adx_trend_threshold = 22
            self.pattern_weight = 1.3
            self.trend_weight = 1.3
            self.volatility_threshold = 0.015
        else:  # default
            self.rsi_oversold = 30
            self.rsi_overbought = 70
            self.volume_threshold = 1.2
            self.adx_trend_threshold = 20
            self.pattern_weight = 1.0
            self.trend_weight = 1.0
            self.volatility_threshold = 0.01

    # =============================================
    # PHASE 2 ENHANCED METHODS
    # =============================================

    def analyze_with_risk(self, df, balance=10000, current_positions=None):
        """Enhanced analysis dengan risk management - PHASE 2"""
        if current_positions is None:
            current_positions = []
            
        # Get basic analysis
        analysis = self.analyze(df)
        if not analysis:
            return None
            
        # Add risk-adjusted position sizing
        symbol = analysis.get('symbol', 'Unknown')
        current_price = analysis.get('current_price', 0)
        score = analysis.get('score', 0)
        volatility = analysis.get('volatility', 0.02)
        
        # Calculate dynamic position size
        position_calc = self.risk_engine.calculate_dynamic_position_size(
            balance, current_price, score, volatility
        )
        
        # Calculate dynamic stop loss
        stop_loss = self.risk_engine.calculate_stop_loss_level(
            current_price, 
            analysis['action'], 
            volatility,
            position_calc['risk_profile']
        )
        
        # Calculate dynamic take profit levels
        take_profits = self.risk_engine.calculate_take_profit_levels(
            current_price,
            analysis['action'],
            stop_loss,
            volatility
        )
        
        # Update analysis dengan risk-adjusted levels
        analysis.update({
            'risk_adjusted_tp1': take_profits[0],
            'risk_adjusted_tp2': take_profits[1],
            'risk_adjusted_tp3': take_profits[2],
            'risk_adjusted_sl': stop_loss,
            'risk_metrics': position_calc,
            'recommended_position_size': position_calc['position_size'],
            'position_value_usd': position_calc['position_value'],
            'final_score': score  # Untuk backward compatibility
        })
        
        # Portfolio risk assessment
        if current_positions:
            portfolio_risk = self.risk_engine.assess_portfolio_risk(current_positions, {
                'liquidity': analysis.get('volume_ratio', 1.0),
                'volatility': volatility
            })
            analysis['portfolio_risk'] = portfolio_risk
        
        return analysis

    def calculate_tp_probability(self, current_price, tp1, tp2, tp3, sl, action, volatility=0.02):
        """Calculate probability of hitting TP1, TP2, TP3 - ENHANCED"""
        try:
            if action == "LONG":
                # Untuk LONG: TP di atas current price, SL di bawah
                distances = {
                    'tp1': (tp1 - current_price) / current_price,
                    'tp2': (tp2 - current_price) / current_price,
                    'tp3': (tp3 - current_price) / current_price,
                    'sl': (current_price - sl) / current_price
                }
            else:  # SHORT
                # Untuk SHORT: TP di bawah current price, SL di atas
                distances = {
                    'tp1': (current_price - tp1) / current_price,
                    'tp2': (current_price - tp2) / current_price,
                    'tp3': (current_price - tp3) / current_price,
                    'sl': (sl - current_price) / current_price
                }
            
            # Base probability berdasarkan distance
            probabilities = {}
            for target, distance in distances.items():
                if target.startswith('tp'):
                    # Semakin dekat TP, semakin tinggi probabilitas
                    if distance <= 0.01:  # Sangat dekat (<1%)
                        base_prob = 0.7
                    elif distance <= 0.03:  # Dekat (1-3%)
                        base_prob = 0.5
                    elif distance <= 0.05:  # Sedang (3-5%)
                        base_prob = 0.3
                    elif distance <= 0.08:  # Jauh (5-8%)
                        base_prob = 0.2
                    else:  # Sangat jauh (>8%)
                        base_prob = 0.1
                    
                    # Adjust berdasarkan volatilitas
                    volatility_adjustment = volatility * 5  # Normalize volatility
                    adjusted_prob = max(0.05, min(0.9, base_prob - volatility_adjustment))
                    
                    probabilities[target] = adjusted_prob
            
            # Pastikan TP1 > TP2 > TP3 untuk probabilitas
            if 'tp1' in probabilities and 'tp2' in probabilities and 'tp3' in probabilities:
                if action == "LONG":
                    probabilities['tp1'] = max(probabilities['tp1'], probabilities['tp2'], probabilities['tp3'])
                    probabilities['tp2'] = min(probabilities['tp1'], max(probabilities['tp2'], probabilities['tp3']))
                    probabilities['tp3'] = min(probabilities['tp1'], probabilities['tp2'], probabilities['tp3'])
                else:  # SHORT
                    probabilities['tp1'] = max(probabilities['tp1'], probabilities['tp2'], probabilities['tp3'])
                    probabilities['tp2'] = min(probabilities['tp1'], max(probabilities['tp2'], probabilities['tp3']))
                    probabilities['tp3'] = min(probabilities['tp1'], probabilities['tp2'], probabilities['tp3'])
            
            return probabilities
            
        except Exception as e:
            print(f"Error calculating TP probability: {e}")
            return {"tp1": 0.5, "tp2": 0.3, "tp3": 0.1}
    
    def _calculate_drawdown_risk(self, volatility, rsi, atr, price_position):
        """Calculate drawdown risk based on multiple factors"""
        risk_score = 0
        
        # Volatility component (40% weight)
        if volatility > 0.03:
            risk_score += 4
        elif volatility > 0.015:
            risk_score += 2
        elif volatility > 0.005:
            risk_score += 1
        
        # RSI component (30% weight) - extreme levels increase risk
        if rsi > 80 or rsi < 20:
            risk_score += 3
        elif rsi > 70 or rsi < 30:
            risk_score += 2
        elif 40 < rsi < 60:
            risk_score += 0  # Neutral zone - no additional risk
        else:
            risk_score += 1
        
        # ATR component (20% weight) - high ATR means larger potential drawdowns
        price = 1.0  # Normalized for calculation
        atr_ratio = atr / price
        if atr_ratio > 0.05:
            risk_score += 2
        elif atr_ratio > 0.02:
            risk_score += 1
        
        # Price position component (10% weight) - extreme highs increase risk
        if price_position > 0.8:  # Near recent highs
            risk_score += 1
        elif price_position < 0.2:  # Near recent lows
            risk_score += 1
        
        # Convert to risk level
        if risk_score >= 8:
            return "VERY HIGH"
        elif risk_score >= 6:
            return "HIGH"
        elif risk_score >= 4:
            return "MEDIUM"
        elif risk_score >= 2:
            return "LOW"
        else:
            return "VERY LOW"

    # =============================================
    # PATTERN DETECTION - PHASE 2 ENHANCED
    # =============================================

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
            ema_13_last = ema_13.iloc[-1] if not np.isnan(ema_13.iloc[-1]) else df['close'].iloc[-1]
            ema_21_last = ema_21.iloc[-1] if not np.isnan(ema_21.iloc[-1]) else df['close'].iloc[-1]
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
            last_atr = atr.iloc[-1] if not np.isnan(atr.iloc[-1]) else 0.0
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
        """Advanced market regime detection - ENHANCED"""
        if len(df) < 50:
            return "UNKNOWN", 0, 0
        
        try:
            # ADX for trend strength
            if TALIB_AVAILABLE:
                adx = talib.ADX(df['high'], df['low'], df['close'], timeperiod=14)
                current_adx = adx.iloc[-1] if not np.isnan(adx.iloc[-1]) else 0
            else:
                # Simple ADX calculation
                highs = df['high'].tail(14)
                lows = df['low'].tail(14)
                high_range = highs.max() - highs.min()
                low_range = lows.max() - lows.min()
                price_range = max(high_range, low_range)
                avg_price = df['close'].tail(14).mean()
                current_adx = (price_range / avg_price) * 100 if avg_price > 0 else 0
            
            # Volatility regime
            returns = df['close'].pct_change().dropna()
            volatility = returns.std() * np.sqrt(252)  # Annualized
            
            # Momentum regime
            momentum = (df['close'].iloc[-1] / df['close'].iloc[-20] - 1) if len(df) >= 20 else 0
            
            # Volume regime
            volume_trend = df['volume'].pct_change().mean() if len(df) > 1 else 0
            
            # Determine regime
            if current_adx > self.adx_trend_threshold and abs(momentum) > 0.05:
                regime = "TRENDING"
            elif volatility < self.volatility_threshold and abs(volume_trend) < 0.1:
                regime = "RANGING_LOW_VOL"
            elif volatility > self.volatility_threshold * 2:
                regime = "RANGING_HIGH_VOL"
            elif current_adx < 15 and abs(momentum) < 0.02:
                regime = "CONSOLIDATION"
            else:
                regime = "TRANSITION"
                
            return regime, current_adx, volatility
            
        except Exception as e:
            print(f"Market regime detection error: {e}")
            return "UNKNOWN", 0, 0
    
    def calculate_trend_strength(self, series):
        """Calculate trend strength dengan R-squared"""
        if len(series) < 5:
            return 0, 0
            
        x = np.arange(len(series))
        y = series.values
        
        # Linear regression
        try:
            coefficients = np.polyfit(x, y, 1)
            slope = coefficients[0]
            
            # Calculate R-squared
            y_pred = np.polyval(coefficients, x)
            ss_res = np.sum((y - y_pred) ** 2)
            ss_tot = np.sum((y - np.mean(y)) ** 2)
            r_squared = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0
            
            return slope, r_squared
        except:
            return 0, 0
    
    def find_swing_points(self, df, order=5):
        """Find swing highs and lows for harmonic patterns"""
        try:
            highs = df['high'].values
            lows = df['low'].values
            
            # Find local maxima and minima
            high_idx = argrelextrema(highs, np.greater, order=order)[0]
            low_idx = argrelextrema(lows, np.less, order=order)[0]
            
            # Get the points
            swing_highs = [(i, highs[i]) for i in high_idx]
            swing_lows = [(i, lows[i]) for i in low_idx]
            
            # Combine and sort by index
            swing_points = sorted(swing_highs + swing_lows, key=lambda x: x[0])
            
            return swing_points, swing_highs, swing_lows
            
        except Exception as e:
            print(f"Swing points error: {e}")
            return [], [], []
    
    def calculate_fibonacci_ratio(self, point1, point2):
        """Calculate Fibonacci ratios between two points"""
        price_diff = abs(point2 - point1)
        return {
            '0.236': point1 + 0.236 * price_diff if point2 > point1 else point1 - 0.236 * price_diff,
            '0.382': point1 + 0.382 * price_diff if point2 > point1 else point1 - 0.382 * price_diff,
            '0.500': point1 + 0.500 * price_diff if point2 > point1 else point1 - 0.500 * price_diff,
            '0.618': point1 + 0.618 * price_diff if point2 > point1 else point1 - 0.618 * price_diff,
            '0.786': point1 + 0.786 * price_diff if point2 > point1 else point1 - 0.786 * price_diff,
            '1.272': point1 + 1.272 * price_diff if point2 > point1 else point1 - 1.272 * price_diff,
            '1.618': point1 + 1.618 * price_diff if point2 > point1 else point1 - 1.618 * price_diff,
        }
    
    def detect_harmonic_patterns(self, df, lookback=100):
        """Real harmonic pattern detection dengan Fibonacci ratios - ENHANCED"""
        patterns = {
            'gartley': {'detected': False, 'direction': None, 'confidence': 0},
            'bat': {'detected': False, 'direction': None, 'confidence': 0},
            'butterfly': {'detected': False, 'direction': None, 'confidence': 0},
            'crab': {'detected': False, 'direction': None, 'confidence': 0},
            'shark': {'detected': False, 'direction': None, 'confidence': 0}
        }
        
        try:
            if len(df) < lookback:
                return patterns
            
            swing_points, swing_highs, swing_lows = self.find_swing_points(df.tail(lookback))
            
            if len(swing_points) < 5:
                return patterns
            
            # Get the last 5 significant swing points
            recent_points = swing_points[-5:]
            
            # Convert to price points only
            X, A, B, C, D = [point[1] for point in recent_points]
            
            # Calculate Fibonacci ratios for each leg
            # XA leg
            xa_ratios = self.calculate_fibonacci_ratio(X, A)
            
            # AB leg
            ab_retrace = abs(B - A) / abs(X - A) if X != A else 0
            
            # BC leg  
            bc_retrace = abs(C - B) / abs(A - B) if A != B else 0
            bc_extension = abs(C - B) / abs(X - A) if X != A else 0
            
            # CD leg
            cd_retrace = abs(D - C) / abs(B - C) if B != C else 0
            cd_extension = abs(D - C) / abs(X - A) if X != A else 0
            
            # Determine pattern direction
            direction = "BULLISH" if X < A else "BEARISH"
            
            # Gartley Pattern
            if (0.618 - 0.05 <= ab_retrace <= 0.618 + 0.05 and
                0.382 - 0.05 <= bc_retrace <= 0.382 + 0.05 and
                0.786 - 0.05 <= cd_retrace <= 0.786 + 0.05):
                patterns['gartley'] = {
                    'detected': True, 
                    'direction': direction,
                    'confidence': 0.8
                }
            
            # Bat Pattern
            if (0.382 - 0.05 <= ab_retrace <= 0.500 + 0.05 and
                0.382 - 0.05 <= bc_retrace <= 0.886 + 0.05 and
                1.618 - 0.1 <= cd_extension <= 2.618 + 0.1):
                patterns['bat'] = {
                    'detected': True,
                    'direction': direction, 
                    'confidence': 0.75
                }
            
            # Butterfly Pattern
            if (0.786 - 0.05 <= ab_retrace <= 0.786 + 0.05 and
                0.382 - 0.05 <= bc_retrace <= 0.886 + 0.05 and
                1.618 - 0.1 <= cd_extension <= 2.240 + 0.1):
                patterns['butterfly'] = {
                    'detected': True,
                    'direction': direction,
                    'confidence': 0.7
                }
            
            # Crab Pattern
            if (0.382 - 0.05 <= ab_retrace <= 0.618 + 0.05 and
                0.382 - 0.05 <= bc_retrace <= 0.886 + 0.05 and
                2.618 - 0.2 <= cd_extension <= 3.618 + 0.2):
                patterns['crab'] = {
                    'detected': True,
                    'direction': direction,
                    'confidence': 0.65
                }
            
            # Shark Pattern
            if (0.886 - 0.05 <= ab_retrace <= 1.130 + 0.05 and
                1.130 - 0.1 <= bc_extension <= 1.618 + 0.1):
                patterns['shark'] = {
                    'detected': True,
                    'direction': direction,
                    'confidence': 0.6
                }
                
        except Exception as e:
            print(f"Harmonic pattern detection error: {e}")
        
        return patterns
    
    def detect_triangle_patterns(self, df, period=20):
        """Enhanced triangle pattern detection dengan confidence"""
        patterns = {
            'symmetrical_triangle': {'detected': False, 'confidence': 0},
            'ascending_triangle': {'detected': False, 'confidence': 0},
            'descending_triangle': {'detected': False, 'confidence': 0},
            'broadening_ascending': {'detected': False, 'confidence': 0},
            'broadening_descending': {'detected': False, 'confidence': 0}
        }
        
        if len(df) < period * 2:
            return patterns
            
        try:
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
                    0.5 < slope_ratio < 2.0 and
                    base_confidence > 0.6):
                    patterns['symmetrical_triangle'] = {
                        'detected': True,
                        'confidence': base_confidence
                    }
            
            # Ascending Triangle: horizontal resistance, rising support
            high_std = np.std(highs)
            high_mean_std = np.std(highs) * 0.7
            if high_std < high_mean_std and low_slope > 0 and base_confidence > 0.5:
                patterns['ascending_triangle'] = {
                    'detected': True,
                    'confidence': base_confidence
                }
            
            # Descending Triangle: horizontal support, falling resistance
            low_std = np.std(lows)
            low_mean_std = np.std(lows) * 0.7
            if low_std < low_mean_std and high_slope < 0 and base_confidence > 0.5:
                patterns['descending_triangle'] = {
                    'detected': True,
                    'confidence': base_confidence
                }
                
            # Broadening patterns (expanding volatility)
            if high_slope > 0 and low_slope < 0 and base_confidence > 0.4:
                patterns['broadening_ascending'] = {
                    'detected': True,
                    'confidence': base_confidence
                }
            elif high_slope < 0 and low_slope > 0 and base_confidence > 0.4:
                patterns['broadening_descending'] = {
                    'detected': True,
                    'confidence': base_confidence
                }
                
        except Exception as e:
            print(f"Triangle pattern detection error: {e}")
            
        return patterns
    
    def detect_channel_wedge_patterns(self, df, period=20):
        """Enhanced channel and wedge pattern detection"""
        patterns = {
            'uptrend_channel': {'detected': False, 'confidence': 0},
            'downtrend_channel': {'detected': False, 'confidence': 0},
            'ranging_channel': {'detected': False, 'confidence': 0},
            'rising_wedge': {'detected': False, 'confidence': 0},
            'falling_wedge': {'detected': False, 'confidence': 0}
        }
        
        if len(df) < period * 2:
            return patterns
            
        try:
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
                patterns['uptrend_channel'] = {
                    'detected': True,
                    'confidence': base_confidence
                }
                
            # Downtrend Channel: both highs and lows trending down
            if (high_slope < 0 and low_slope < 0 and close_slope < 0 and 
                base_confidence > 0.6):
                patterns['downtrend_channel'] = {
                    'detected': True,
                    'confidence': base_confidence
                }
                
            # Ranging Channel: minimal slope with consistent range
            if (abs(high_slope) < 0.001 and abs(low_slope) < 0.001 and 
                base_confidence > 0.5):
                patterns['ranging_channel'] = {
                    'detected': True,
                    'confidence': base_confidence
                }
                
            # Rising Wedge: highs rising faster than lows
            if (high_slope > 0 and low_slope > 0 and 
                high_slope > low_slope * 1.5 and
                base_confidence > 0.5):
                patterns['rising_wedge'] = {
                    'detected': True,
                    'confidence': base_confidence
                }
                
            # Falling Wedge: lows falling faster than highs
            if (high_slope < 0 and low_slope < 0 and 
                abs(low_slope) > abs(high_slope) * 1.5 and
                base_confidence > 0.5):
                patterns['falling_wedge'] = {
                    'detected': True,
                    'confidence': base_confidence
                }
                
        except Exception as e:
            print(f"Channel/wedge pattern detection error: {e}")
            
        return patterns

    # =============================================
    # TECHNICAL INDICATORS - PHASE 2 ENHANCED
    # =============================================

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

    def calculate_momentum_score(self, df):
        """Calculate momentum-based score - ENHANCED"""
        if len(df) < 20:
            return 0
            
        try:
            # Price momentum
            price_change_5 = (df['close'].iloc[-1] / df['close'].iloc[-5] - 1) * 100
            price_change_10 = (df['close'].iloc[-1] / df['close'].iloc[-10] - 1) * 100
            price_change_20 = (df['close'].iloc[-1] / df['close'].iloc[-20] - 1) * 100
            
            # Volume momentum
            volume_change = (df['volume'].iloc[-1] / df['volume'].rolling(10).mean().iloc[-1] - 1) * 100
            
            momentum_score = 0
            
            # Positive momentum dengan confirmation
            if price_change_5 > 2 and price_change_10 > 5 and price_change_20 > 8:
                momentum_score += 3
            elif price_change_5 > 1 and price_change_10 > 2 and price_change_20 > 4:
                momentum_score += 2
            elif price_change_5 > 0.5 and price_change_10 > 1:
                momentum_score += 1
                
            # Negative momentum  
            if price_change_5 < -2 and price_change_10 < -5 and price_change_20 < -8:
                momentum_score -= 3
            elif price_change_5 < -1 and price_change_10 < -2 and price_change_20 < -4:
                momentum_score -= 2
            elif price_change_5 < -0.5 and price_change_10 < -1:
                momentum_score -= 1
                
            # Volume confirmation
            if momentum_score > 0 and volume_change > 20:
                momentum_score += 1
            elif momentum_score < 0 and volume_change > 20:
                momentum_score -= 1
                
            return momentum_score
            
        except Exception as e:
            print(f"Momentum calculation error: {e}")
            return 0

    # =============================================
    # MAIN ANALYSIS METHOD - PHASE 2 ENHANCED
    # =============================================

    def analyze(self, df):
        """Main analysis method dengan semua enhancements Phase 2"""
        if df is None or len(df) < 50:
            return None
        
        try:
            current_close = df['close'].iloc[-1]
            
            # Calculate RSI
            if TALIB_AVAILABLE:
                rsi_array = talib.RSI(df['close'], timeperiod=14)
                current_rsi = rsi_array.iloc[-1] if not np.isnan(rsi_array.iloc[-1]) else 50
            else:
                current_rsi = self._calculate_rsi(df['close'])
            
            atr = self.calculate_atr(df)
            
            # Basic technical analysis
            hh, hl, lh, ll = self.identify_hh_hl_lh_ll(df)
            ema_trend, ema_score = self.analyze_ema_cross(df)
            volume_score, volume_ratio = self.analyze_volume_profile(df)
            
            # Advanced analysis - PHASE 2 ENHANCEMENTS
            market_regime, adx_value, volatility = self.detect_market_regime(df)
            momentum_score = self.calculate_momentum_score(df)
            ml_confidence = self.ml_enhancer.predict_confidence(df)
            
            # Pattern detection dengan confidence - PHASE 2
            harmonic_patterns = self.detect_harmonic_patterns(df)
            triangle_patterns = self.detect_triangle_patterns(df)
            channel_wedge_patterns = self.detect_channel_wedge_patterns(df)
            
            # Calculate price position for drawdown risk
            high_20 = df['high'].rolling(20).max().iloc[-1]
            low_20 = df['low'].rolling(20).min().iloc[-1]
            price_position = (current_close - low_20) / (high_20 - low_20) if (high_20 - low_20) > 0 else 0.5
            
            # Calculate scores dengan market-specific weights
            trend_score = 0
            if hh or hl:
                trend_score += 2 * self.trend_weight
            if lh or ll:
                trend_score -= 2 * self.trend_weight
            
            if ema_trend == "BULLISH":
                trend_score += ema_score * self.trend_weight
            else:
                trend_score += ema_score * self.trend_weight
            
            # Enhanced pattern scoring with confidence - PHASE 2
            pattern_score = 0
            
            # Harmonic patterns
            for pattern_name, pattern_data in harmonic_patterns.items():
                if pattern_data['detected']:
                    direction_multiplier = 1 if pattern_data['direction'] == 'BULLISH' else -1
                    pattern_score += 2 * direction_multiplier * pattern_data['confidence'] * self.pattern_weight
            
            # Triangle patterns
            for pattern_name, pattern_data in triangle_patterns.items():
                if pattern_data['detected']:
                    if pattern_name == 'ascending_triangle':
                        pattern_score += 3 * pattern_data['confidence'] * self.pattern_weight
                    elif pattern_name == 'descending_triangle':
                        pattern_score -= 3 * pattern_data['confidence'] * self.pattern_weight
                    elif pattern_name == 'symmetrical_triangle':
                        pattern_score += 1 * pattern_data['confidence'] * self.pattern_weight
            
            # Channel and wedge patterns
            for pattern_name, pattern_data in channel_wedge_patterns.items():
                if pattern_data['detected']:
                    if pattern_name in ['uptrend_channel', 'falling_wedge']:
                        pattern_score += 2 * pattern_data['confidence'] * self.pattern_weight
                    elif pattern_name in ['downtrend_channel', 'rising_wedge']:
                        pattern_score -= 2 * pattern_data['confidence'] * self.pattern_weight
                    elif pattern_name == 'ranging_channel':
                        pattern_score += 1 * pattern_data['confidence'] * self.pattern_weight
            
            # Market-specific RSI scoring
            rsi_score = self.calculate_rsi_score(current_rsi)
            
            # Calculate final score dengan ML confidence - PHASE 2
            raw_score = trend_score + rsi_score + volume_score + pattern_score + momentum_score
            final_score = raw_score * ml_confidence  # Apply ML confidence
            
            # Adjust score based on market regime
            if market_regime == "TRENDING" and abs(final_score) > 2:
                final_score *= 1.2
            elif market_regime == "RANGING_LOW_VOL" and abs(final_score) > 3:
                final_score *= 0.7
            elif market_regime == "RANGING_HIGH_VOL":
                final_score *= 1.1
            elif market_regime == "CONSOLIDATION":
                final_score *= 0.8  # Reduce signals during consolidation
            
            # Round to integer
            final_score = int(round(final_score))
            
            # Determine action
            action_threshold = 2 if self.market_type == "crypto" else 1
            action = "LONG" if final_score >= action_threshold else "SHORT" if final_score <= -action_threshold else "NEUTRAL"
            
            # Calculate entry levels
            ideal_entry = current_close
            entry_low = ideal_entry * (1 - self.entry_range_pct)
            entry_high = ideal_entry * (1 + self.entry_range_pct)
            
            # Calculate raw TP levels
            if action == "LONG":
                raw_tp1 = ideal_entry + atr * self.atr_multiplier
                raw_tp2 = ideal_entry + atr * self.atr_multiplier * 2
                raw_tp3 = ideal_entry + atr * self.atr_multiplier * 3
                sl = ideal_entry - atr * self.atr_multiplier
            elif action == "SHORT":
                raw_tp1 = ideal_entry - atr * self.atr_multiplier
                raw_tp2 = ideal_entry - atr * self.atr_multiplier * 2
                raw_tp3 = ideal_entry - atr * self.atr_multiplier * 3
                sl = ideal_entry + atr * self.atr_multiplier
            else:  # NEUTRAL
                raw_tp1 = raw_tp2 = raw_tp3 = sl = ideal_entry
            
            # Apply TP ordering correction
            if action == "LONG":
                # Untuk LONG: TP1 < TP2 < TP3 (semua di atas current price)
                tp_levels = sorted([raw_tp1, raw_tp2, raw_tp3])
                tp1, tp2, tp3 = tp_levels
            elif action == "SHORT":
                # Untuk SHORT: TP1 > TP2 > TP3 (semua di bawah current price)
                tp_levels = sorted([raw_tp1, raw_tp2, raw_tp3], reverse=True)
                tp1, tp2, tp3 = tp_levels
            else:  # NEUTRAL
                tp1, tp2, tp3 = raw_tp1, raw_tp2, raw_tp3
            
            # Calculate TP probabilities - PHASE 2
            tp_probabilities = self.calculate_tp_probability(
                current_close, tp1, tp2, tp3, sl, action, volatility
            )
            
            # Prepare pattern details
            detected_patterns = []
            all_patterns = {}
            
            for pattern_dict in [harmonic_patterns, triangle_patterns, channel_wedge_patterns]:
                for pattern_name, pattern_data in pattern_dict.items():
                    if pattern_data.get('detected'):
                        detected_patterns.append(pattern_name)
                    all_patterns[pattern_name] = pattern_data
            
            # Calculate drawdown risk - PHASE 2
            drawdown_risk = self._calculate_drawdown_risk(volatility, current_rsi, atr, price_position)
            
            # Risk metrics dengan drawdown_risk - PHASE 2
            risk_metrics = {
                'reward_ratio': (tp1 - ideal_entry) / (ideal_entry - sl) if action == "LONG" else (ideal_entry - tp1) / (sl - ideal_entry),
                'risk_category': 'HIGH' if volatility > 0.03 else 'MEDIUM' if volatility > 0.01 else 'LOW',
                'optimal_position_size': 0.1 if volatility > 0.03 else 0.15 if volatility > 0.01 else 0.2,
                'drawdown_risk': drawdown_risk,
                'volatility_level': volatility
            }
            
            result = {
                'action': action,
                'ideal_entry': float(ideal_entry),
                'entry_low': float(entry_low),
                'entry_high': float(entry_high),
                'tp1': float(tp1),
                'tp2': float(tp2),
                'tp3': float(tp3),
                'sl': float(sl),
                'current_price': float(current_close),
                'rsi': float(current_rsi),
                'trend': 'BULLISH' if trend_score > 0 else 'BEARISH' if trend_score < 0 else 'NEUTRAL',
                'volume_ratio': float(volume_ratio),
                'score': final_score,
                'raw_score': int(raw_score),
                'final_score': final_score,  # Untuk compatibility
                'atr': float(atr),
                'hh': hh,
                'hl': hl,
                'lh': lh,
                'll': ll,
                'ema_trend': ema_trend,
                'ema_score': ema_score,
                'pattern_score': int(pattern_score),
                'momentum_score': momentum_score,
                'detected_patterns': detected_patterns,
                'pattern_details': all_patterns,
                'market_regime': market_regime,
                'adx_value': float(adx_value),
                'volatility': float(volatility),
                'market_type': self.market_type,
                'volume_score': volume_score,
                'rsi_score': rsi_score,
                'trend_score': int(trend_score),
                'ml_confidence': float(ml_confidence),
                'risk_metrics': risk_metrics,
                'tp_probabilities': tp_probabilities,  # PHASE 2
                'price_position': float(price_position)
            }
            
            return result
            
        except Exception as e:
            print(f"Error in strategy analysis: {e}")
            return None
    
    def _calculate_rsi(self, prices, period=14):
        """Calculate RSI manually"""
        if len(prices) < period + 1:
            return 50
            
        try:
            delta = prices.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            return rsi.iloc[-1] if not np.isnan(rsi.iloc[-1]) else 50
        except:
            return 50

# =============================================
# STRATEGY TESTING - PHASE 2
# =============================================

if __name__ == "__main__":
    # Test the enhanced strategy
    strategy = TechnicalAnalysisStrategy(market_type="crypto")
    
    # Create sample data for testing
    dates = pd.date_range('2023-01-01', periods=100, freq='D')
    data = {
        'open': np.random.normal(100, 10, 100),
        'high': np.random.normal(105, 12, 100),
        'low': np.random.normal(95, 12, 100),
        'close': np.random.normal(100, 10, 100),
        'volume': np.random.normal(1000000, 100000, 100)
    }
    df = pd.DataFrame(data, index=dates)
    
    # Test basic analysis
    result = strategy.analyze(df)
    print("Phase 2 Enhanced Analysis Result:")
    print(f"Action: {result['action']}")
    print(f"Final Score: {result['final_score']}")
    print(f"Market Regime: {result['market_regime']}")
    print(f"ML Confidence: {result['ml_confidence']:.2f}")
    print(f"TP Probabilities: {result['tp_probabilities']}")
    print(f"Detected Patterns: {result['detected_patterns']}")
    
    # Test risk analysis
    risk_result = strategy.analyze_with_risk(df, balance=10000)
    print("\nPhase 2 Risk Analysis Result:")
    print(f"Recommended Position Size: {risk_result['recommended_position_size']:.4f}")
    print(f"Risk Profile: {risk_result['risk_metrics']['risk_profile']}")
    print(f"Drawdown Risk: {risk_result['risk_metrics']['drawdown_risk']}")
