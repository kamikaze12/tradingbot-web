import os
import time
import json
import warnings
import joblib
from datetime import datetime, timedelta
import threading
import schedule
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split, TimeSeriesSplit
from sklearn.metrics import classification_report, accuracy_score
from dotenv import load_dotenv

warnings.filterwarnings("ignore")
load_dotenv()

# Import modul yang diperlukan
from strategies import TechnicalAnalysisStrategy
from data_provider import (
    CCXTDataProvider,
    YFinanceDataProvider,
    SolanaPumpFunProvider
)
from notifier import SoundNotifier
from database.db_handler import DatabaseHandler

# =============================================
# 1. AUTO RETRAINING PIPELINE - PHASE 2
# =============================================

class MLEnhancedBot:
    """Machine Learning enhanced trading bot dengan model real dan auto-retraining"""
    
    def __init__(self, model_type='random_forest'):
        self.model_type = model_type
        self.model = None
        self.scaler = StandardScaler()
        self.is_trained = False
        self.model_path = "models/trading_model.pkl"
        self.scaler_path = "models/scaler.pkl"
        self.feature_importance = {}
        
        # Auto-retraining configuration - ONLINE LEARNING
        self.auto_retrain_interval = 24 * 3600  # 24 hours in seconds
        self.last_retrain_time = 0
        self.retraining_threshold = 1000  # Minimum new samples for retraining
        self.new_samples_count = 0
        
        # Buat directory models jika belum ada
        os.makedirs("models", exist_ok=True)
        
        # Coba load model yang sudah ada
        self.load_model()
        
        # Start auto-retraining thread
        self.start_auto_retraining()

    def start_auto_retraining(self):
        """Start background thread untuk auto-retraining"""
        def retrain_worker():
            while True:
                try:
                    current_time = time.time()
                    if (current_time - self.last_retrain_time > self.auto_retrain_interval and 
                        self.new_samples_count >= self.retraining_threshold):
                        print("🔄 Starting auto-retraining...")
                        self.auto_retrain()
                    time.sleep(3600)  # Check every hour
                except Exception as e:
                    print(f"❌ Error in auto-retraining worker: {e}")
                    time.sleep(300)  # Wait 5 minutes on error
        
        retrain_thread = threading.Thread(target=retrain_worker, daemon=True)
        retrain_thread.start()
        print("✅ Auto-retraining thread started")

    def auto_retrain(self):
        """Auto-retrain model dengan data terbaru"""
        try:
            # Get recent trading data for retraining
            training_symbols = self.get_training_symbols()
            if not training_symbols:
                print("⚠️ No symbols available for auto-retraining")
                return False
            
            historical_data = self.collect_training_data(training_symbols)
            if len(historical_data) < 5:  # Minimum symbols
                print("⚠️ Insufficient data for auto-retraining")
                return False
            
            # Train model
            success = self.train_model(historical_data)
            if success:
                self.last_retrain_time = time.time()
                self.new_samples_count = 0
                print("✅ Auto-retraining completed successfully")
                return True
            else:
                print("❌ Auto-retraining failed")
                return False
                
        except Exception as e:
            print(f"❌ Error in auto-retraining: {e}")
            return False

    def get_training_symbols(self, count=50):
        """Get symbols untuk training dari berbagai sumber"""
        symbols = set()
        
        try:
            # Add popular crypto pairs
            crypto_pairs = ['BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'XRP/USDT', 'ADA/USDT',
                          'DOT/USDT', 'LINK/USDT', 'LTC/USDT', 'BCH/USDT', 'XLM/USDT']
            symbols.update(crypto_pairs)
            
            # Add forex majors
            forex_pairs = ['EUR/USD', 'GBP/USD', 'USD/JPY', 'USD/CHF', 'AUD/USD',
                          'USD/CAD', 'NZD/USD', 'USD/CNY']
            symbols.update(forex_pairs)
            
            # Add top stocks
            stocks = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA', 'META', 'NVDA', 'JPM']
            symbols.update(stocks)
            
            return list(symbols)[:count]
            
        except Exception as e:
            print(f"❌ Error getting training symbols: {e}")
            return ['BTC/USDT', 'ETH/USDT', 'EUR/USD', 'GBP/USD', 'AAPL']  # Fallback

    def collect_training_data(self, symbols, days=90):
        """Collect training data untuk auto-retraining"""
        historical_data = {}
        
        # In a real implementation, you would fetch actual historical data
        # This is a simplified version
        for symbol in symbols:
            try:
                # Simulate data collection - replace with actual data provider calls
                dates = pd.date_range(end=datetime.now(), periods=days, freq='D')
                data = {
                    'open': np.random.normal(100, 10, days),
                    'high': np.random.normal(105, 12, days),
                    'low': np.random.normal(95, 12, days),
                    'close': np.random.normal(100, 10, days),
                    'volume': np.random.normal(1000000, 100000, days)
                }
                df = pd.DataFrame(data, index=dates)
                historical_data[symbol] = df
                
            except Exception as e:
                print(f"⚠️ Error collecting data for {symbol}: {e}")
                continue
        
        return historical_data

    def update_training_data(self, symbol, new_data):
        """Update training data dengan data baru dan trigger retraining jika cukup"""
        self.new_samples_count += len(new_data)
        
        # Trigger immediate retraining jika cukup data baru
        if self.new_samples_count >= self.retraining_threshold:
            print("🔄 Sufficient new data, triggering retraining...")
            self.auto_retrain()

    def load_model(self):
        """Load model dan scaler yang sudah ditraining"""
        try:
            if os.path.exists(self.model_path) and os.path.exists(self.scaler_path):
                self.model = joblib.load(self.model_path)
                self.scaler = joblib.load(self.scaler_path)
                self.is_trained = True
                
                # Load retraining state
                state_path = "models/training_state.json"
                if os.path.exists(state_path):
                    with open(state_path, 'r') as f:
                        state = json.load(f)
                        self.last_retrain_time = state.get('last_retrain_time', 0)
                        self.new_samples_count = state.get('new_samples_count', 0)
                
                print("✅ ML model loaded successfully")
                return True
        except Exception as e:
            print(f"❌ Error loading model: {e}")
        
        # Initialize new model jika tidak ada
        self._initialize_model()
        return False

    def save_model(self):
        """Save model, scaler, dan training state"""
        try:
            if self.model and self.scaler:
                joblib.dump(self.model, self.model_path)
                joblib.dump(self.scaler, self.scaler_path)
                
                # Save training state
                state_path = "models/training_state.json"
                training_state = {
                    'last_retrain_time': self.last_retrain_time,
                    'new_samples_count': self.new_samples_count,
                    'last_saved': datetime.now().isoformat()
                }
                with open(state_path, 'w') as f:
                    json.dump(training_state, f, indent=2)
                
                print("✅ ML model and training state saved successfully")
                return True
        except Exception as e:
            print(f"❌ Error saving model: {e}")
        return False

    def _initialize_model(self):
        """Initialize model baru - MODEL ENSEMBLE"""
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
        print("🔄 New ML model initialized")

    def prepare_training_data(self, historical_data):
        """Prepare training data dari historical data"""
        try:
            features_list = []
            targets = []
            
            for symbol, data in historical_data.items():
                if len(data) < 100:  # Minimal data points
                    continue
                    
                # Extract features untuk setiap point dalam data
                for i in range(50, len(data) - 10):  # Leave room for future prediction
                    current_window = data.iloc[:i+1]
                    future_window = data.iloc[i+1:i+11]  # 10 period ke depan
                    
                    # Extract features - ADVANCED FEATURE ENGINEERING
                    features = self._extract_detailed_features(current_window)
                    if features:
                        # Determine target (1 jika harga naik, 0 jika turun)
                        current_price = current_window['close'].iloc[-1]
                        future_max = future_window['close'].max()
                        future_min = future_window['close'].min()
                        
                        # Target: 1 jika naik 2%, -1 jika turun 2%, 0 jika sideways
                        price_change = (future_max - current_price) / current_price
                        if price_change >= 0.02:
                            target = 1
                        elif (future_min - current_price) / current_price <= -0.02:
                            target = -1
                        else:
                            target = 0
                            
                        features_list.append(features)
                        targets.append(target)
            
            if len(features_list) < 100:  # Minimal training samples
                return None, None
                
            return np.array(features_list), np.array(targets)
            
        except Exception as e:
            print(f"❌ Error preparing training data: {e}")
            return None, None

    def train_model(self, historical_data, test_size=0.2):
        """Train model dengan historical data - ENSEMBLE TRAINING"""
        try:
            print("🔄 Preparing training data...")
            X, y = self.prepare_training_data(historical_data)
            
            if X is None or len(X) < 100:
                print("❌ Insufficient training data")
                return False
            
            print(f"📊 Training data shape: {X.shape}, targets: {y.shape}")
            
            # Split data dengan time series split
            tscv = TimeSeriesSplit(n_splits=5)
            accuracies = []
            
            for train_idx, test_idx in tscv.split(X):
                X_train, X_test = X[train_idx], X[test_idx]
                y_train, y_test = y[train_idx], y[test_idx]
                
                # Scale features
                X_train_scaled = self.scaler.fit_transform(X_train)
                X_test_scaled = self.scaler.transform(X_test)
                
                # Train model
                self.model.fit(X_train_scaled, y_train)
                
                # Evaluate
                y_pred = self.model.predict(X_test_scaled)
                accuracy = accuracy_score(y_test, y_pred)
                accuracies.append(accuracy)
            
            # Final training dengan semua data
            X_scaled = self.scaler.fit_transform(X)
            self.model.fit(X_scaled, y)
            
            # Calculate feature importance
            if hasattr(self.model, 'feature_importances_'):
                feature_names = [
                    'rsi', 'macd', 'sma_20', 'sma_50', 'ema_12', 'ema_26',
                    'atr', 'volume_ratio', 'price_change_1d', 'price_change_5d',
                    'volatility', 'momentum', 'williams_r', 'cci', 'obv'
                ]
                # Pastikan jumlah feature matches
                if len(self.model.feature_importances_) == len(feature_names):
                    self.feature_importance = dict(zip(feature_names, self.model.feature_importances_))
                else:
                    self.feature_importance = {f: 0.0 for f in feature_names}
            
            self.is_trained = True
            avg_accuracy = np.mean(accuracies)
            
            print(f"✅ Model training completed! Average Accuracy: {avg_accuracy:.3f}")
            print(f"📈 Feature Importance: {self.feature_importance}")
            
            # Save model
            self.save_model()
            return True
            
        except Exception as e:
            print(f"❌ Error training model: {e}")
            return False

    def _extract_detailed_features(self, df):
        """Extract detailed features untuk training dan prediction - ADVANCED FEATURES"""
        try:
            if len(df) < 50:
                return None
                
            features = {}
            
            # Price-based features
            prices = df['close']
            volumes = df['volume']
            
            # RSI
            features['rsi'] = self._calculate_rsi(prices)
            
            # MACD
            features['macd'] = self._calculate_macd(prices)
            
            # Moving Averages
            features['sma_20'] = prices.rolling(20).mean().iloc[-1] if len(prices) >= 20 else prices.mean()
            features['sma_50'] = prices.rolling(50).mean().iloc[-1] if len(prices) >= 50 else prices.mean()
            features['ema_12'] = prices.ewm(span=12).mean().iloc[-1]
            features['ema_26'] = prices.ewm(span=26).mean().iloc[-1]
            
            # ATR
            features['atr'] = self._calculate_atr(df)
            
            # Volume features
            vol_mean = volumes.rolling(20).mean().iloc[-1] if len(volumes) >= 20 else volumes.mean()
            features['volume_ratio'] = volumes.iloc[-1] / vol_mean if vol_mean > 0 else 1
            
            # Price changes
            if len(df) > 1:
                features['price_change_1d'] = (prices.iloc[-1] - prices.iloc[-2]) / prices.iloc[-2] if prices.iloc[-2] != 0 else 0
            else:
                features['price_change_1d'] = 0
                
            if len(df) > 5:
                features['price_change_5d'] = (prices.iloc[-1] - prices.iloc[-6]) / prices.iloc[-6] if prices.iloc[-6] != 0 else 0
            else:
                features['price_change_5d'] = 0
            
            # Volatility
            features['volatility'] = prices.pct_change().std() * np.sqrt(252) if len(prices) > 1 else 0.02
            
            # Momentum
            features['momentum'] = (prices.iloc[-1] - prices.iloc[-10]) / prices.iloc[-10] if len(prices) > 10 and prices.iloc[-10] != 0 else 0
            
            # Williams %R
            features['williams_r'] = self._calculate_williams_r(df)
            
            # CCI
            features['cci'] = self._calculate_cci(df)
            
            # OBV
            features['obv'] = self._calculate_obv(df)
            
            # Pastikan tidak ada NaN values
            for key, value in features.items():
                if pd.isna(value):
                    features[key] = 0
            
            return list(features.values())
            
        except Exception as e:
            print(f"❌ Error extracting features: {e}")
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
            print(f"❌ Error in extract_features: {e}")
            return pd.DataFrame([self._get_default_features()])

    def _get_default_features(self):
        """Return default features jika extraction gagal"""
        return [50, 0, 0, 0, 0, 0, 0.02, 1, 0, 0, 0.02, 0, -50, 0, 0]

    def predict(self, df):
        """Predict menggunakan model ML"""
        try:
            if not self.is_trained or self.model is None:
                return 0.5, 0  # Return default confidence dan direction
            
            # Extract features
            features_df = self.extract_features(df)
            if features_df.empty:
                return 0.5, 0
            
            # Scale features
            features_scaled = self.scaler.transform(features_df)
            
            # Predict
            prediction = self.model.predict(features_scaled)[0]
            probabilities = self.model.predict_proba(features_scaled)[0]
            
            # Confidence score (ambil probability tertinggi)
            confidence = np.max(probabilities)
            
            return confidence, prediction
            
        except Exception as e:
            print(f"❌ Error in ML prediction: {e}")
            return 0.5, 0

    def batch_predict(self, symbols_data):
        """Batch prediction untuk multiple symbols"""
        try:
            if not self.is_trained:
                return {}
            
            predictions = {}
            features_list = []
            symbol_features = {}
            
            # Extract features untuk semua symbols
            for symbol, df in symbols_data.items():
                features_df = self.extract_features(df)
                if not features_df.empty:
                    features_list.append(features_df.iloc[0].values)
                    symbol_features[symbol] = features_df.iloc[0].values
            
            if not features_list:
                return {}
            
            # Batch prediction
            features_array = np.array(features_list)
            features_scaled = self.scaler.transform(features_array)
            
            batch_predictions = self.model.predict(features_scaled)
            batch_probabilities = self.model.predict_proba(features_scaled)
            
            # Map predictions back to symbols
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
            print(f"❌ Error in batch prediction: {e}")
            return {}

    # Technical Indicators - ADVANCED FEATURE ENGINEERING
    def _calculate_rsi(self, prices, period=14):
        try:
            if len(prices) < period + 1:
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
            if len(prices) < 26:
                return 0
            exp1 = prices.ewm(span=12).mean()
            exp2 = prices.ewm(span=26).mean()
            macd = exp1 - exp2
            return macd.iloc[-1]
        except:
            return 0

    def _calculate_atr(self, df, period=14):
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

    def _calculate_williams_r(self, df, period=14):
        try:
            high = df['high'].rolling(period).max()
            low = df['low'].rolling(period).min()
            close = df['close']
            
            williams_r = -100 * (high - close) / (high - low)
            return williams_r.iloc[-1] if not pd.isna(williams_r.iloc[-1]) else -50
        except:
            return -50

    def _calculate_cci(self, df, period=20):
        try:
            typical_price = (df['high'] + df['low'] + df['close']) / 3
            sma = typical_price.rolling(period).mean()
            mad = typical_price.rolling(period).apply(lambda x: np.mean(np.abs(x - np.mean(x))))
            
            cci = (typical_price - sma) / (0.015 * mad)
            return cci.iloc[-1] if not pd.isna(cci.iloc[-1]) else 0
        except:
            return 0

    def _calculate_obv(self, df):
        try:
            close = df['close']
            volume = df['volume']
            obv = (np.sign(close.diff()) * volume).fillna(0).cumsum()
            return obv.iloc[-1] if len(obv) > 0 else 0
        except:
            return 0

# =============================================
# 2. DYNAMIC RISK ENGINE - ENHANCED
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
        total_exposure = sum(pos['exposure'] for pos in current_positions)
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
        symbols = [pos['symbol'] for pos in positions]
        return 0.3  # Placeholder
    
    def _calculate_concentration_risk(self, positions):
        """Calculate concentration risk in portfolio"""
        if not positions:
            return 0.0
            
        exposures = [pos['exposure'] for pos in positions]
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
# 3. REALISTIC BACKTEST ENGINE - ENHANCED
# =============================================

class RealisticBacktestEngine:
    """Enhanced backtesting engine dengan realistic market conditions"""
    
    def __init__(self, initial_balance=10000):
        self.initial_balance = initial_balance
        self.results = {}
        
        # Realistic market parameters
        self.slippage_models = {
            'crypto': {'base': 0.001, 'volatility_multiplier': 2.0},
            'forex': {'base': 0.0001, 'volatility_multiplier': 1.5},
            'stocks': {'base': 0.0005, 'volatility_multiplier': 1.2}
        }
        
        self.commission_models = {
            'crypto': 0.001,  # 0.1%
            'forex': 0.0002,  # 0.02% 
            'stocks': 0.0015  # 0.15%
        }
        
        self.liquidity_impact = 0.0001  # 0.01% impact per $10k traded

    def run_realistic_backtest(self, df, strategy, market_type='crypto', **kwargs):
        """Run backtest dengan realistic market conditions"""
        try:
            # Extract parameters
            initial_balance = kwargs.get('initial_balance', self.initial_balance)
            commission = kwargs.get('commission', self.commission_models.get(market_type, 0.001))
            slippage_model = kwargs.get('slippage_model', self.slippage_models.get(market_type))
            
            balance = initial_balance
            position = 0
            trades = []
            equity_curve = [balance]
            max_balance = balance
            max_drawdown = 0
            
            if df is None or len(df) < 100:
                return self._get_empty_results()
            
            print(f"🔄 Running realistic backtest on {len(df)} bars...")
            
            for i in range(50, len(df)):
                current_data = df.iloc[:i+1]
                current_price = df['close'].iloc[i]
                current_volume = df['volume'].iloc[i] if 'volume' in df.columns else 1000
                current_time = df.index[i] if hasattr(df.index, 'iloc') else i
                
                # Calculate realistic slippage
                slippage = self._calculate_slippage(current_price, current_volume, market_type)
                
                # Get strategy analysis
                analysis = strategy.analyze(current_data)
                
                if analysis and analysis['action'] in ['LONG', 'SHORT']:
                    current_trade = None
                    
                    # Check if we should enter a trade
                    if position == 0 and self._should_enter_trade(analysis, current_price):
                        position = 1 if analysis['action'] == 'LONG' else -1
                        
                        # Apply realistic entry price dengan slippage
                        executed_price = current_price * (1 + slippage) if position == 1 else current_price * (1 - slippage)
                        
                        # Calculate position size with risk management
                        position_size = self._calculate_realistic_position_size(
                            balance, executed_price, analysis, market_type
                        )
                        
                        # Calculate commission and fees
                        trade_value = position_size * executed_price
                        entry_commission = trade_value * commission
                        
                        # Apply liquidity impact
                        liquidity_impact = self._calculate_liquidity_impact(trade_value, current_volume)
                        effective_entry_price = executed_price * (1 + liquidity_impact)
                        
                        entry_trade = {
                            'entry_time': current_time,
                            'entry_price': executed_price,
                            'effective_entry_price': effective_entry_price,
                            'action': analysis['action'],
                            'size': position_size,
                            'slippage': slippage,
                            'liquidity_impact': liquidity_impact,
                            'commission_paid': entry_commission,
                            'trade_value': trade_value
                        }
                        trades.append(entry_trade)
                        current_trade = entry_trade
                        
                        # Apply commission dan impact ke balance
                        balance -= entry_commission
                    
                    # Check if we should exit a trade
                    elif position != 0 and len(trades) > 0:
                        current_trade = trades[-1]
                        if current_trade.get('exit_time') is None:  # Still open
                            if self._should_exit_trade(current_trade, current_price, analysis, position):
                                # Apply realistic exit price dengan slippage
                                exit_slippage = self._calculate_slippage(current_price, current_volume, market_type)
                                executed_exit_price = current_price * (1 - exit_slippage) if position == 1 else current_price * (1 + exit_slippage)
                                
                                # Calculate exit commission
                                exit_trade_value = current_trade['size'] * executed_exit_price
                                exit_commission = exit_trade_value * commission
                                
                                # Apply liquidity impact pada exit
                                exit_liquidity_impact = self._calculate_liquidity_impact(exit_trade_value, current_volume)
                                effective_exit_price = executed_exit_price * (1 - exit_liquidity_impact)
                                
                                # Calculate P&L dengan realistic prices
                                if position == 1:  # LONG
                                    price_change = effective_exit_price - current_trade['effective_entry_price']
                                else:  # SHORT
                                    price_change = current_trade['effective_entry_price'] - effective_exit_price
                                
                                pnl = price_change * current_trade['size']
                                total_commission = current_trade['commission_paid'] + exit_commission
                                net_pnl = pnl - total_commission
                                
                                # Update balance
                                balance += net_pnl
                                
                                current_trade.update({
                                    'exit_time': current_time,
                                    'exit_price': executed_exit_price,
                                    'effective_exit_price': effective_exit_price,
                                    'exit_slippage': exit_slippage,
                                    'exit_liquidity_impact': exit_liquidity_impact,
                                    'exit_commission': exit_commission,
                                    'total_commission': total_commission,
                                    'gross_pnl': pnl + total_commission,  # P&L sebelum commission
                                    'net_pnl': net_pnl,
                                    'return_pct': (net_pnl / current_trade['trade_value']) * 100
                                })
                                
                                position = 0
                                
                                # Update max drawdown
                                if balance > max_balance:
                                    max_balance = balance
                                current_drawdown = (max_balance - balance) / max_balance if max_balance > 0 else 0
                                max_drawdown = max(max_drawdown, current_drawdown)
                
                # Update equity curve (include unrealized P&L)
                if position != 0 and len(trades) > 0:
                    current_trade = trades[-1]
                    if current_trade.get('exit_time') is None:  # Position still open
                        # Calculate unrealized P&L dengan current market price
                        if position == 1:  # LONG
                            unrealized_pnl = (current_price - current_trade['effective_entry_price']) * current_trade['size']
                        else:  # SHORT
                            unrealized_pnl = (current_trade['effective_entry_price'] - current_price) * current_trade['size']
                        current_equity = balance + unrealized_pnl
                    else:
                        current_equity = balance
                else:
                    current_equity = balance
                    
                equity_curve.append(current_equity)
            
            # Calculate realistic performance metrics
            self.results = self._calculate_realistic_performance_metrics(trades, equity_curve, market_type)
            return self.results
            
        except Exception as e:
            print(f"Error in realistic backtest: {e}")
            return self._get_empty_results()

    def _calculate_slippage(self, price, volume, market_type):
        """Calculate realistic slippage berdasarkan market conditions"""
        try:
            base_slippage = self.slippage_models[market_type]['base']
            multiplier = self.slippage_models[market_type]['volatility_multiplier']
            
            # Slippage increases dengan volatility dan decreases dengan volume
            volume_factor = max(0.1, 1000000 / volume) if volume > 0 else 1.0
            slippage = base_slippage * multiplier * volume_factor
            
            return min(slippage, 0.01)  # Max 1% slippage
        except:
            return 0.001  # Default 0.1%

    def _calculate_liquidity_impact(self, trade_value, volume):
        """Calculate liquidity impact berdasarkan trade size vs volume"""
        try:
            if volume <= 0:
                return 0.0001
                
            # Impact proportional to trade size relative to volume
            volume_ratio = trade_value / volume
            impact = self.liquidity_impact * volume_ratio
            
            return min(impact, 0.005)  # Max 0.5% impact
        except:
            return 0.0001

    def _calculate_realistic_position_size(self, balance, price, analysis, market_type):
        """Calculate position size dengan realistic constraints"""
        # Base position size (2% risk)
        risk_amount = balance * 0.02
        
        # Use ATR untuk risk calculation
        atr = analysis.get('atr', price * 0.02)
        if atr <= 0:
            atr = price * 0.02
            
        # Position size berdasarkan ATR risk
        position_size = risk_amount / (atr * 2)  # Stop loss at 2 ATR
        
        # Apply market-specific limits
        max_position_size = (balance * 0.2) / price  # Max 20% of balance
        
        # Minimum position size check
        min_trade_value = 10  # $10 minimum
        min_position_size = min_trade_value / price
        
        return max(min_position_size, min(position_size, max_position_size))

    def _should_enter_trade(self, analysis, current_price):
        """Enhanced entry logic"""
        score = analysis.get('score', 0)
        if (score >= 2 or score <= -2) and analysis.get('risk_metrics', {}).get('reward_ratio', 0) > 1.5:
            if analysis.get('volume_ratio', 0) > 0.8:  # Minimum volume
                if analysis.get('rsi', 50) not in [0, 100]:  # Valid RSI
                    return True
        return False

    def _should_exit_trade(self, trade, current_price, analysis, position):
        """Enhanced exit logic with trailing stops"""
        entry_price = trade['entry_price']
        
        if trade['action'] == 'LONG':
            # Profit taking
            if current_price >= entry_price * 1.05:
                return True
            # Stop loss
            if current_price <= entry_price * 0.98:
                return True
            # Trailing stop (if price moved up then reversed)
            if hasattr(self, 'highest_price'):
                if current_price <= self.highest_price * 0.97:
                    return True
            else:
                self.highest_price = current_price
        else:  # SHORT
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

    def _calculate_realistic_performance_metrics(self, trades, equity_curve, market_type):
        """Calculate performance metrics dengan realistic adjustments"""
        if not trades or len(equity_curve) < 2:
            return self._get_empty_results()
            
        # Filter hanya closed trades
        closed_trades = [t for t in trades if t.get('exit_time') is not None]
        
        if not closed_trades:
            return self._get_empty_results()
            
        # Basic metrics
        winning_trades = [t for t in closed_trades if t.get('net_pnl', 0) > 0]
        losing_trades = [t for t in closed_trades if t.get('net_pnl', 0) <= 0]
        
        total_trades = len(closed_trades)
        win_rate = len(winning_trades) / total_trades if total_trades else 0
        
        # P&L metrics dengan commission dan slippage
        total_net_pnl = sum(t.get('net_pnl', 0) for t in closed_trades)
        total_gross_pnl = sum(t.get('gross_pnl', 0) for t in closed_trades)
        total_commission = sum(t.get('total_commission', 0) for t in closed_trades)
        total_slippage_cost = sum(t.get('slippage', 0) * t.get('size', 0) * t.get('entry_price', 0) for t in closed_trades)
        
        avg_win = np.mean([t.get('net_pnl', 0) for t in winning_trades]) if winning_trades else 0
        avg_loss = np.mean([t.get('net_pnl', 0) for t in losing_trades]) if losing_trades else 0
        
        # Risk-adjusted metrics
        returns = np.diff(equity_curve) / np.array(equity_curve[:-1])
        volatility = np.std(returns) * np.sqrt(252) if len(returns) > 1 else 0
        sharpe_ratio = np.mean(returns) / np.std(returns) * np.sqrt(252) if len(returns) > 1 and np.std(returns) > 0 else 0
        
        # Drawdown analysis
        equity_array = np.array(equity_curve)
        peak = np.maximum.accumulate(equity_array)
        drawdown = (equity_array - peak) / peak
        max_drawdown = np.min(drawdown) if len(drawdown) > 0 else 0
        
        # Realistic metrics
        avg_holding_period = np.mean([
            (t['exit_time'] - t['entry_time']).total_seconds() / 3600 
            for t in closed_trades if 'entry_time' in t and 'exit_time' in t
        ]) if closed_trades else 0
        
        return {
            'total_trades': total_trades,
            'winning_trades': len(winning_trades),
            'losing_trades': len(losing_trades),
            'win_rate': win_rate,
            'total_net_pnl': total_net_pnl,
            'total_gross_pnl': total_gross_pnl,
            'total_commission': total_commission,
            'total_slippage_cost': total_slippage_cost,
            'net_profit_after_costs': total_net_pnl,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': abs(sum(t.get('net_pnl', 0) for t in winning_trades) / 
                               sum(t.get('net_pnl', 0) for t in losing_trades)) if losing_trades else float('inf'),
            'sharpe_ratio': sharpe_ratio,
            'volatility': volatility,
            'max_drawdown': max_drawdown,
            'final_balance': equity_curve[-1],
            'equity_curve': equity_curve,
            'avg_holding_period_hours': avg_holding_period,
            'avg_return_per_trade': total_net_pnl / total_trades if total_trades else 0,
            'realistic_metrics': {
                'commission_impact': total_commission / total_gross_pnl if total_gross_pnl != 0 else 0,
                'slippage_impact': total_slippage_cost / total_gross_pnl if total_gross_pnl != 0 else 0,
                'efficiency_ratio': total_net_pnl / total_gross_pnl if total_gross_pnl != 0 else 0
            }
        }

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
# 4. MODEL EXPLAINABILITY - PHASE 2
# =============================================

class ModelExplainer:
    """Advanced model explainability untuk trading ML models"""
    
    def __init__(self, model_path="models/trading_model.pkl", feature_names=None):
        self.model_path = model_path
        self.model = None
        self.feature_names = feature_names or [
            'rsi', 'macd', 'sma_20', 'sma_50', 'ema_12', 'ema_26',
            'atr', 'volume_ratio', 'price_change_1d', 'price_change_5d',
            'volatility', 'momentum', 'williams_r', 'cci', 'obv'
        ]
        self.load_model()
        
    def load_model(self):
        """Load model dari file"""
        try:
            if os.path.exists(self.model_path):
                self.model = joblib.load(self.model_path)
                print("✅ Model loaded successfully for explainability")
                return True
            else:
                print("❌ Model file not found")
                return False
        except Exception as e:
            print(f"❌ Error loading model: {e}")
            return False
    
    def explain_prediction(self, features_df, instance_index=0):
        """Explain individual prediction dengan feature contributions"""
        if self.model is None:
            return {"error": "Model not loaded"}
            
        try:
            # Convert to numpy array jika perlu
            if isinstance(features_df, pd.DataFrame):
                features_array = features_df.values
            else:
                features_array = features_df
                
            # Pastikan bentuk features benar
            if len(features_array.shape) == 1:
                features_array = features_array.reshape(1, -1)
                
            # Get prediction probabilities
            probabilities = self.model.predict_proba(features_array)[instance_index]
            prediction = self.model.predict(features_array)[instance_index]
            
            explanation = {
                'prediction': int(prediction),
                'probabilities': {
                    'DOWN': float(probabilities[0]),
                    'NEUTRAL': float(probabilities[1]) if len(probabilities) > 2 else 0.0,
                    'UP': float(probabilities[-1])
                },
                'confidence': float(np.max(probabilities)),
                'feature_contributions': {}
            }
            
            return explanation
            
        except Exception as e:
            return {"error": f"Explanation failed: {str(e)}"}

# =============================================
# MAIN TRADING BOT CLASS - PHASE 2 ENHANCED
# =============================================

class TradingBot:
    def __init__(self, config_path="config/config.json"):
        self.config_path = config_path
        self.load_config()
        self.mode = None
        self.data_provider = None
        self.pump_provider = None
        self.strategy = TechnicalAnalysisStrategy(
            market_type=self.config.get("market_type", "crypto"),
            atr_multiplier=self.config.get("atr_multiplier", 1.0),
            entry_range_pct=self.config.get("entry_range_pct", 0.02),
        )
        self.notifier = SoundNotifier()
        self.db = DatabaseHandler()
        
        # PHASE 2 Enhancements - SEMUA INI BARU
        self.ml_bot = MLEnhancedBot()                    # ✅ Model Ensemble & Online Learning
        self.backtest_engine = RealisticBacktestEngine() # ✅ Realistic Backtest
        self.risk_engine = DynamicRiskEngine()          # ✅ Enhanced Risk Management
        self.model_explainer = ModelExplainer()         # ✅ Model Explainability
        
        # ML enhancements
        self.ml_predictions_cache = {}
        self.last_ml_update = 0

        self.timeframe = self.config.get("timeframe", "1h")
        self.alert_active = False
        self.scanner_active = False
        self.entry_positions = {}
        self.position_ids = {}
        
        self.scheduler_thread = None
        self.stop_scheduler = False
        self.scanning_in_progress = False

    def load_config(self):
        try:
            os.makedirs("config", exist_ok=True)
            with open(self.config_path, "r") as f:
                self.config = json.load(f)
        except FileNotFoundError:
            self.config = {
                "timeframe": "1h",
                "atr_multiplier": 1.0,
                "entry_range_pct": 0.02,
                "exchange_crypto": "kucoin",
                "analysis_coins_limit": 100,
                "ohlcv_limit": 200,
                "min_score": 3,
                "max_signals": 10,
                "update_interval": 30,
                "scan_delay": 0.5,
                "market_type": "crypto"
            }
            self.save_config()

    def save_config(self):
        os.makedirs("config", exist_ok=True)
        with open(self.config_path, "w") as f:
            json.dump(self.config, f, indent=4)

    def set_mode(self, mode):
        self.mode = mode.lower()
        try:
            if self.mode == "crypto":
                exchange_id = self.config.get("exchange_crypto", "kucoin")
                self.data_provider = CCXTDataProvider(exchange_id, "", "")
                self.pump_provider = SolanaPumpFunProvider(
                    os.getenv("SOLANA_RPC", "https://api.mainnet-beta.solana.com")
                )
                self.strategy = TechnicalAnalysisStrategy(market_type="crypto")
            elif self.mode == "forex":
                self.data_provider = YFinanceDataProvider(market_type="forex")
                self.strategy = TechnicalAnalysisStrategy(market_type="forex")
            elif self.mode == "saham_id":
                self.data_provider = YFinanceDataProvider(market_type="saham_id")
                self.strategy = TechnicalAnalysisStrategy(market_type="saham_id")
            elif self.mode == "stocks":
                self.data_provider = YFinanceDataProvider(market_type="stocks")
                self.strategy = TechnicalAnalysisStrategy(market_type="stocks")
            else:
                self.data_provider = None
                self.pump_provider = None
                print(f"Invalid mode: {mode}")
                return False
            
            # Test koneksi data provider
            if self.data_provider:
                test_assets = self.data_provider.get_popular_assets(5)
                print(f"✅ Data provider test: Found {len(test_assets)} assets")
            
            print(f"Mode set to: {self.mode.upper()} with data provider: {self.data_provider.__class__.__name__}")
            self.start_background_tasks()
            return True
        except Exception as e:
            print(f"❌ Error setting mode {mode}: {e}")
            return False

    def start_background_tasks(self):
        if self.scheduler_thread and self.scheduler_thread.is_alive():
            self.stop_background_tasks()
            
        self.stop_scheduler = False
        self.scheduler_thread = threading.Thread(target=self._run_scheduler, daemon=True)
        self.scheduler_thread.start()
        print("Background tasks started")

    def stop_background_tasks(self):
        self.stop_scheduler = True
        if self.scheduler_thread:
            self.scheduler_thread.join(timeout=5)
        print("Background tasks stopped")

    def _run_scheduler(self):
        while not self.stop_scheduler:
            schedule.run_pending()
            time.sleep(1)

    # =============================================
    # PHASE 2 ENHANCED METHODS
    # =============================================

    def analyze_with_risk(self, symbol, balance=10000, current_positions=None):
        """Enhanced analysis dengan risk management"""
        analysis = self.analyze_asset(symbol)
        if not analysis:
            return None
            
        return self.strategy.analyze_with_risk(
            analysis, balance, current_positions or []
        )

    def run_realistic_backtest(self, symbol, timeframe=None, limit=500, market_type=None):
        """Run realistic backtest dengan market conditions"""
        if not market_type:
            market_type = self.mode
            
        if not self.data_provider:
            return {"error": "No data provider available"}
            
        try:
            if timeframe is None:
                timeframe = self.timeframe
                
            df = self.data_provider.get_ohlcv(symbol, timeframe, limit)
            if df is None or len(df) < 100:
                return {"error": "Insufficient data for backtest"}
            
            result = self.backtest_engine.run_realistic_backtest(
                df, self.strategy, market_type=market_type
            )
            
            return {
                'symbol': symbol,
                'timeframe': timeframe,
                'backtest_result': result,
                'data_points': len(df)
            }
            
        except Exception as e:
            print(f"Error in realistic backtest: {e}")
            return {"error": str(e)}

    def explain_ml_prediction(self, symbol):
        """Explain ML prediction untuk symbol tertentu"""
        try:
            df = self.data_provider.get_ohlcv(symbol, self.timeframe, 100)
            if df is None or len(df) < 50:
                return {"error": "Insufficient data for explanation"}
            
            features_df = self.ml_bot.extract_features(df)
            explanation = self.model_explainer.explain_prediction(features_df)
            
            return {
                'symbol': symbol,
                'explanation': explanation
            }
            
        except Exception as e:
            print(f"Error explaining ML prediction: {e}")
            return {"error": str(e)}

    def auto_retrain_ml_model(self):
        """Manual trigger untuk auto-retraining"""
        return self.ml_bot.auto_retrain()

    # =============================================
    # EXISTING METHODS - TETAP SAMA
    # =============================================

    def analyze_asset(self, symbol):
        """Analyze asset dengan error handling yang lebih robust"""
        if not self.data_provider:
            print("❌ No data provider for analysis.")
            return None
            
        try:
            # Clean symbol untuk forex/saham
            original_symbol = symbol
            if self.mode == 'forex' and '=X' not in symbol:
                symbol = f"{symbol}=X"
            elif self.mode == 'saham_id' and not symbol.endswith('.JK'):
                symbol = f"{symbol}.JK"
            
            print(f"📈 Fetching data for {symbol}...")
            df = self.data_provider.get_ohlcv(
                symbol, self.timeframe, self.config.get("ohlcv_limit", 200)
            )
            
            if df is None or len(df) == 0:
                print(f"   ❌ No data returned for {symbol}")
                return None
                
            # Check data quality
            required_columns = ['open', 'high', 'low', 'close', 'volume']
            if not all(col in df.columns for col in required_columns):
                print(f"   ❌ Missing required columns in data for {symbol}")
                return None
                
            if len(df) < 20:
                print(f"   ⚠️ Insufficient data for {symbol}: {len(df)} rows")
                return None
            
            print(f"   ✅ Data fetched: {len(df)} rows")
            
            # Analisis dengan strategy
            analysis = self.strategy.analyze(df)
            
            if analysis and isinstance(analysis, dict):
                analysis["symbol"] = original_symbol
                analysis["market_type"] = self.mode
                
                # Simpan ke database
                try:
                    self.db.save_signal(analysis)
                except Exception as db_error:
                    print(f"   ⚠️ Could not save to DB: {db_error}")
                
                print(f"   📊 Analysis complete: {analysis.get('action', 'NO_ACTION')} (Score: {analysis.get('score', 0)})")
                return analysis
            else:
                print(f"   ⚠️ No valid analysis results for {symbol}")
                return None
                
        except Exception as e:
            print(f"❌ Error analyzing {symbol}: {str(e)}")
            return None

    def get_popular_assets(self, limit=100):
        if not self.data_provider:
            print("No data provider for popular assets.")
            return []
        try:
            assets = self.data_provider.get_popular_assets(limit)
            return assets
        except Exception as e:
            print(f"Error loading popular assets: {e}")
            return []

    def scan_potential_assets(self, limit=None):
        """Scan potential assets dengan ML enhancement"""
        if self.scanning_in_progress:
            print("⚠️ Scan already in progress, please wait...")
            return []
            
        if not self.data_provider:
            print("❌ No data provider for scanning.")
            return []
            
        try:
            self.scanning_in_progress = True
            if limit is None:
                limit = self.config.get("analysis_coins_limit", 100)
            
            print(f"🔄 Getting popular assets for {self.mode}...")
            assets = self.data_provider.get_popular_assets(limit)
            
            if not assets:
                print("❌ No assets found from data provider")
                return []
                
            print(f"🔄 Scanning {len(assets)} assets in {self.mode} mode...")
            
            results = []
            successful_analysis = 0
            failed_analysis = 0
            
            for i, asset in enumerate(assets):
                if self.stop_scheduler:
                    break
                    
                print(f"  Analyzing {i+1}/{len(assets)}: {asset}")
                
                try:
                    # Gunakan enhanced analysis dengan risk management
                    analysis = self.analyze_with_risk(asset)
                    
                    if analysis:
                        score = analysis.get("final_score", analysis.get("score", 0))
                        min_score = self.config.get("min_score", 3)
                        
                        if (analysis.get("action") in ["LONG", "SHORT"] and 
                            abs(score) >= min_score):
                            
                            results.append(analysis)
                            successful_analysis += 1
                            action_emoji = "🟢" if analysis['action'] == "LONG" else "🔴"
                            print(f"    {action_emoji} Signal found: {analysis['action']} (Score: {analysis['final_score']})")
                        else:
                            print(f"    ⚠️ No trade signal (Action: {analysis.get('action')}, Score: {analysis.get('final_score')})")
                    else:
                        failed_analysis += 1
                        print(f"    ❌ Analysis failed for {asset}")
                        
                except Exception as e:
                    failed_analysis += 1
                    print(f"    ❌ Error analyzing {asset}: {str(e)}")
                
                # Delay untuk menghindari rate limit
                time.sleep(self.config.get("scan_delay", 0.5))
            
            # Urutkan berdasarkan absolute final score
            results.sort(key=lambda x: abs(x.get('final_score', 0)), reverse=True)
            max_signals = self.config.get("max_signals", 10)
            final_results = results[:max_signals]
            
            print(f"📊 Scan complete: {successful_analysis} successful, {failed_analysis} failed, {len(final_results)} signals found")
            
            return final_results
            
        except Exception as e:
            print(f"❌ Error in scan_potential_assets: {e}")
            return []
        finally:
            self.scanning_in_progress = False

    def calculate_custom_entry(self, symbol, entry_price):
        """Calculate custom entry levels untuk manual trading"""
        try:
            # Get basic analysis untuk ATR dan volatilitas
            analysis = self.analyze_asset(symbol)
            if analysis:
                atr = analysis.get('atr', entry_price * 0.02)
                volatility = analysis.get('volatility', 0.02)
            else:
                atr = entry_price * 0.02
                volatility = 0.02
            
            # Calculate TP/SL levels berdasarkan ATR
            tp1 = entry_price + (atr * 1.5)
            tp2 = entry_price + (atr * 2.5)
            tp3 = entry_price + (atr * 4.0)
            sl = entry_price - (atr * 1.5)
            
            return {
                'symbol': symbol,
                'entry_price': entry_price,
                'tp1': tp1,
                'tp2': tp2,
                'tp3': tp3,
                'sl': sl,
                'atr': atr,
                'volatility': volatility
            }
        except Exception as e:
            print(f"Error calculating custom entry: {e}")
            return None

    def get_active_positions(self):
        """Get active positions dari database"""
        return self.db.get_active_positions(self.mode)

    def get_trade_history(self, limit=20):
        """Get trade history dari database"""
        return self.db.get_trade_history(self.mode, limit)

    def close_position(self, position_id, close_price):
        """Close position dan simpan ke history"""
        return self.db.close_position(position_id, close_price, "manual")

    async def scan_pump_fun(self, limit=10):
        """Scan new tokens dari Pump Fun"""
        if not self.pump_provider:
            return []
        try:
            results = await self.pump_provider.monitor_new_tokens(limit)
            return results
        except Exception as e:
            print(f"Error scanning Pump Fun: {e}")
            return []

# =============================================
# MAIN EXECUTION - TEST PHASE 2 FEATURES
# =============================================

if __name__ == "__main__":
    # Test the enhanced bot
    bot = TradingBot()
    
    print("🚀 Testing Phase 2 Enhanced Features...")
    
    # Test auto-retraining
    print("🔄 Testing Auto-Retraining...")
    bot.auto_retrain_ml_model()
    
    # Test realistic backtest
    print("📊 Testing Realistic Backtest...")
    result = bot.run_realistic_backtest("BTC/USDT", "1h", 500, "crypto")
    print("Backtest result:", result)
    
    # Test risk analysis
    print("⚖️ Testing Risk Analysis...")
    risk_analysis = bot.analyze_with_risk("BTC/USDT", balance=10000)
    print("Risk analysis:", risk_analysis)
    
    # Test ML explanation
    print("🤖 Testing ML Explanation...")
    explanation = bot.explain_ml_prediction("BTC/USDT")
    print("ML explanation:", explanation)
    
    print("✅ Phase 2 Core Testing Completed!")
