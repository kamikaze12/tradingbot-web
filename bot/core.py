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
from .strategies import TechnicalAnalysisStrategy
from .data_provider import (
    CCXTDataProvider,
    YFinanceDataProvider,
    SolanaPumpFunProvider
)
from .notifier import SoundNotifier
from database.db_handler import DatabaseHandler

class MLEnhancedBot:
    """Machine Learning enhanced trading bot dengan model real"""
    
    def __init__(self, model_type='random_forest'):
        self.model_type = model_type
        self.model = None
        self.scaler = StandardScaler()
        self.is_trained = False
        self.model_path = "models/trading_model.pkl"
        self.scaler_path = "models/scaler.pkl"
        self.feature_importance = {}
        
        # Buat directory models jika belum ada
        os.makedirs("models", exist_ok=True)
        
        # Coba load model yang sudah ada
        self.load_model()

    def load_model(self):
        """Load model dan scaler yang sudah ditraining"""
        try:
            if os.path.exists(self.model_path) and os.path.exists(self.scaler_path):
                self.model = joblib.load(self.model_path)
                self.scaler = joblib.load(self.scaler_path)
                self.is_trained = True
                print("✅ ML model loaded successfully")
                return True
        except Exception as e:
            print(f"❌ Error loading model: {e}")
        
        # Initialize new model jika tidak ada
        self._initialize_model()
        return False

    def save_model(self):
        """Save model dan scaler"""
        try:
            if self.model and self.scaler:
                joblib.dump(self.model, self.model_path)
                joblib.dump(self.scaler, self.scaler_path)
                print("✅ ML model saved successfully")
                return True
        except Exception as e:
            print(f"❌ Error saving model: {e}")
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
                    
                    # Extract features
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
        """Train model dengan historical data"""
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
        """Extract detailed features untuk training dan prediction"""
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

    # Technical Indicators
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
            commission = kwargs.get('commission', 0.001)  # 0.1% commission
            
            balance = self.initial_balance
            position = 0
            trades = []
            equity_curve = [balance]
            max_balance = balance
            max_drawdown = 0
            
            if df is None or len(df) < 100:
                return self._get_empty_results()
            
            print(f"🔄 Running backtest on {len(df)} bars...")
            
            for i in range(50, len(df)):
                current_data = df.iloc[:i+1]
                current_price = df['close'].iloc[i]
                current_time = df.index[i] if hasattr(df.index, 'iloc') else i
                
                # Get strategy analysis
                analysis = strategy.analyze(current_data)
                
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
                        
                        # Apply commission
                        balance -= entry_trade['commission_paid']
                    
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
                
                # Update equity curve (include unrealized P&L)
                if position != 0 and len(trades) > 0:
                    current_trade = trades[-1]
                    if current_trade.get('exit_time') is None:  # Position still open
                        unrealized_pnl = (current_price - current_trade['entry_price']) * current_trade['size'] * position
                        current_equity = balance + unrealized_pnl
                    else:
                        current_equity = balance
                else:
                    current_equity = balance
                    
                equity_curve.append(current_equity)
            
            self.results = self._calculate_comprehensive_performance_metrics(trades, equity_curve)
            return self.results
            
        except Exception as e:
            print(f"Error in backtest: {e}")
            return self._get_empty_results()
    
    def run_walk_forward_analysis(self, df, strategy_class, periods=5, **kwargs):
        """Walk-forward analysis for strategy validation"""
        try:
            if len(df) < 200:
                return {"error": "Insufficient data for walk-forward analysis"}
            
            period_length = len(df) // periods
            results = []
            
            print(f"🔍 Running walk-forward analysis with {periods} periods...")
            
            for i in range(periods):
                start_idx = i * period_length
                end_idx = start_idx + period_length if i < periods - 1 else len(df)
                
                train_data = df.iloc[:start_idx + period_length//2]
                test_data = df.iloc[start_idx + period_length//2:end_idx]
                
                if len(train_data) > 100 and len(test_data) > 50:
                    # Optimize parameters on training data
                    optimized_params = self._optimize_parameters(train_data, strategy_class, **kwargs)
                    
                    # Test on out-of-sample data
                    strategy = strategy_class(**optimized_params)
                    period_result = self.run_backtest(test_data, strategy, **optimized_params)
                    
                    period_result['period'] = i + 1
                    period_result['train_size'] = len(train_data)
                    period_result['test_size'] = len(test_data)
                    results.append(period_result)
                    
                    print(f"  Period {i+1}: {period_result.get('total_trades', 0)} trades, Win Rate: {period_result.get('win_rate', 0):.1%}")
            
            # Aggregate results
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
            print(f"Error in walk-forward analysis: {e}")
            return {"error": str(e)}
    
    def run_parameter_optimization(self, df, strategy_class, param_grid, **kwargs):
        """Grid search for parameter optimization"""
        try:
            best_score = -float('inf')
            best_params = {}
            results = []
            
            print("⚙️ Running parameter optimization...")
            
            # Generate parameter combinations
            param_combinations = self._generate_parameter_combinations(param_grid)
            
            for i, params in enumerate(param_combinations):
                try:
                    strategy = strategy_class(**params)
                    result = self.run_backtest(df, strategy, **params)
                    
                    # Use Sharpe ratio as optimization score
                    score = result.get('sharpe_ratio', 0)
                    
                    optimization_result = {
                        'params': params.copy(),
                        'score': score,
                        'total_trades': result.get('total_trades', 0),
                        'win_rate': result.get('win_rate', 0),
                        'total_pnl': result.get('total_pnl', 0)
                    }
                    results.append(optimization_result)
                    
                    if score > best_score and result.get('total_trades', 0) >= 5:  # Minimum trades requirement
                        best_score = score
                        best_params = params.copy()
                    
                    if (i + 1) % 10 == 0:
                        print(f"  Completed {i+1}/{len(param_combinations)} combinations...")
                        
                except Exception as e:
                    print(f"  Skipping combination {params}: {e}")
                    continue
            
            # Sort results by score
            results.sort(key=lambda x: x['score'], reverse=True)
            
            return {
                'best_params': best_params,
                'best_score': best_score,
                'top_results': results[:10],  # Top 10 results
                'all_results': results
            }
            
        except Exception as e:
            print(f"Error in parameter optimization: {e}")
            return {"error": str(e)}
    
    def run_monte_carlo_simulation(self, trades, num_simulations=1000, confidence_level=0.95):
        """Monte Carlo simulation for strategy robustness"""
        try:
            if not trades or len(trades) < 10:
                return {"error": "Insufficient trades for Monte Carlo simulation"}
            
            # Extract P&L values from trades
            pnl_values = [t.get('net_pnl', t.get('pnl', 0)) for t in trades if t.get('pnl') is not None]
            
            if len(pnl_values) < 10:
                return {"error": "Insufficient P&L data for simulation"}
            
            simulations = []
            num_trades = len(pnl_values)
            
            print(f"🎲 Running Monte Carlo simulation ({num_simulations} iterations)...")
            
            for i in range(num_simulations):
                # Random sampling with replacement
                sampled_pnls = np.random.choice(pnl_values, size=num_trades, replace=True)
                sim_total = np.sum(sampled_pnls)
                sim_win_rate = np.sum(np.array(sampled_pnls) > 0) / num_trades
                
                simulations.append({
                    'total_pnl': sim_total,
                    'win_rate': sim_win_rate,
                    'avg_trade': np.mean(sampled_pnls)
                })
            
            # Calculate statistics
            total_pnls = [s['total_pnl'] for s in simulations]
            win_rates = [s['win_rate'] for s in simulations]
            
            # Confidence intervals
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
            print(f"Error in Monte Carlo simulation: {e}")
            return {"error": str(e)}
    
    def _should_enter_trade(self, analysis, current_price):
        """Enhanced entry logic"""
        # ✅ PERBAIKAN: Terima sinyal SHORT dengan skor negatif kuat
        score = analysis.get('score', 0)
        if (score >= 2 or score <= -2) and analysis.get('risk_metrics', {}).get('reward_ratio', 0) > 1.5:
            # Additional filters
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
    
    def _calculate_position_size(self, balance, current_price, atr):
        """Position sizing with risk management"""
        risk_per_trade = 0.02  # 2% risk per trade
        risk_amount = balance * risk_per_trade
        
        if atr > 0:
            # Use ATR for position sizing
            position_size = risk_amount / (atr * 2)  # Stop loss at 2 ATR
        else:
            # Fallback to percentage-based sizing
            position_size = (balance * 0.1) / current_price  # 10% of balance
        
        return min(position_size, (balance * 0.2) / current_price)  # Max 20% per trade
    
    def _calculate_comprehensive_performance_metrics(self, trades, equity_curve):
        """Enhanced performance metrics"""
        if not trades or len(equity_curve) < 2:
            return self._get_empty_results()
            
        # Basic metrics
        closed_trades = [t for t in trades if t.get('exit_time') is not None]
        winning_trades = [t for t in closed_trades if t.get('net_pnl', t.get('pnl', 0)) > 0]
        losing_trades = [t for t in closed_trades if t.get('net_pnl', t.get('pnl', 0)) <= 0]
        
        total_trades = len(closed_trades)
        win_rate = len(winning_trades) / total_trades if total_trades else 0
        
        # P&L metrics
        total_pnl = sum(t.get('net_pnl', t.get('pnl', 0)) for t in closed_trades)
        avg_win = np.mean([t.get('net_pnl', t.get('pnl', 0)) for t in winning_trades]) if winning_trades else 0
        avg_loss = np.mean([t.get('net_pnl', t.get('pnl', 0)) for t in losing_trades]) if losing_trades else 0
        profit_factor = abs(sum(t.get('net_pnl', t.get('pnl', 0)) for t in winning_trades) / 
                           sum(t.get('net_pnl', t.get('pnl', 0)) for t in losing_trades)) if losing_trades else float('inf')
        
        # Risk metrics
        returns = np.diff(equity_curve) / np.array(equity_curve[:-1])
        volatility = np.std(returns) * np.sqrt(252) if len(returns) > 1 else 0
        sharpe_ratio = np.mean(returns) / np.std(returns) * np.sqrt(252) if len(returns) > 1 and np.std(returns) > 0 else 0
        
        # Drawdown analysis
        equity_array = np.array(equity_curve)
        peak = np.maximum.accumulate(equity_array)
        drawdown = (equity_array - peak) / peak
        max_drawdown = np.min(drawdown) if len(drawdown) > 0 else 0
        
        # Trade statistics
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
            'net_pnl': total_pnl,  # Including commissions
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
        # This is a simplified version - in practice you might want more sophisticated optimization
        default_params = {
            'atr_multiplier': 1.0,
            'entry_range_pct': 0.02,
            'market_type': kwargs.get('market_type', 'crypto')
        }
        
        # Test a few parameter combinations
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
        
        # Consistency based on win rate stability and P&L consistency
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

class PortfolioOptimizer:
    """Portfolio optimization engine"""
    
    def __init__(self):
        self.correlation_matrix = {}
    
    def optimize_position(self, analysis, existing_positions):
        """Optimize position size based on portfolio context"""
        if not analysis:
            return {}
            
        base_size = analysis.get('risk_metrics', {}).get('optimal_position_size', 0.1)
        correlation_penalty = self._calculate_correlation_penalty(analysis.get('symbol', ''), existing_positions)
        adjusted_size = base_size * (1 - correlation_penalty)
        
        return {
            'base_position_size': base_size,
            'adjusted_position_size': adjusted_size,
            'correlation_penalty': correlation_penalty,
            'recommended_size': min(adjusted_size, 0.15)
        }
    
    def _calculate_correlation_penalty(self, symbol, existing_positions):
        if not existing_positions:
            return 0
        num_positions = len(existing_positions)
        return min(0.3, num_positions * 0.05)
    
    def optimize_allocations(self, signals, total_capital):
        """Optimize capital allocation across multiple signals"""
        if not signals:
            return {}
            
        scored_signals = []
        for signal in signals:
            if not isinstance(signal, dict):
                continue
                
            score = signal.get('final_score', signal.get('score', 0))
            risk_metrics = signal.get('risk_metrics', {})
            risk_category = risk_metrics.get('risk_category', 'MEDIUM')
            base_allocation = risk_metrics.get('optimal_position_size', 0.05)
            
            risk_multiplier = 1.0 if risk_category == 'LOW' else 0.7 if risk_category == 'MEDIUM' else 0.4
            score_multiplier = 1.0 + (score - 1) * 0.1
            
            final_allocation = base_allocation * risk_multiplier * score_multiplier
            scored_signals.append({
                'symbol': signal.get('symbol', 'Unknown'),
                'score': score,
                'risk_category': risk_category,
                'allocation_percent': final_allocation,
                'allocated_capital': total_capital * final_allocation
            })
        
        if not scored_signals:
            return {}
        
        total_allocated = sum(s['allocation_percent'] for s in scored_signals)
        if total_allocated > 1.0:
            for signal in scored_signals:
                signal['allocation_percent'] /= total_allocated
                signal['allocated_capital'] = total_capital * signal['allocation_percent']
        
        return {
            'signals': scored_signals,
            'total_allocated_percent': sum(s['allocation_percent'] for s in scored_signals),
            'total_allocated_capital': sum(s['allocated_capital'] for s in scored_signals),
            'remaining_capital': total_capital * (1 - sum(s['allocation_percent'] for s in scored_signals))
        }

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
        # PHASE 2 Enhancements
        self.ml_bot = MLEnhancedBot()
        self.backtest_engine = BacktestEngine()
        self.portfolio_optimizer = PortfolioOptimizer()
        self.timeframe = self.config.get("timeframe", "1h")
        self.alert_active = False
        self.scanner_active = False
        self.entry_positions = {}
        self.position_ids = {}
        
        self.scheduler_thread = None
        self.stop_scheduler = False
        self.scanning_in_progress = False
        
        # ML enhancements
        self.ml_predictions_cache = {}
        self.last_ml_update = 0

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

    def update_ml_predictions(self, symbols_data):
        """Update ML predictions untuk multiple symbols sekaligus"""
        try:
            # Cache predictions untuk 5 menit
            current_time = time.time()
            if current_time - self.last_ml_update < 300:  # 5 menit
                return self.ml_predictions_cache
            
            print("🔄 Updating ML predictions...")
            predictions = self.ml_bot.batch_predict(symbols_data)
            
            self.ml_predictions_cache = predictions
            self.last_ml_update = current_time
            
            print(f"✅ ML predictions updated for {len(predictions)} symbols")
            return predictions
            
        except Exception as e:
            print(f"❌ Error updating ML predictions: {e}")
            return {}

    def analyze_with_ml(self, symbol):
        """Enhanced analysis dengan ML real"""
        try:
            # Dapatkan analisis dasar terlebih dahulu
            base_analysis = self.analyze_asset(symbol)
            if not base_analysis:
                return None
            
            # Get data untuk ML
            df = self.data_provider.get_ohlcv(symbol, self.timeframe, 100)
            if df is None or len(df) < 50:
                return base_analysis
            
            # Dapatkan ML prediction
            ml_confidence, ml_direction = self.ml_bot.predict(df)
            
            # Enhanced scoring dengan ML
            ml_score_boost = 0
            
            if ml_confidence > 0.7:  # High confidence
                if ml_direction == 1:  # Bullish prediction
                    ml_score_boost = 2.0
                elif ml_direction == -1:  # Bearish prediction
                    ml_score_boost = -2.0
            
            elif ml_confidence > 0.6:  # Medium confidence
                if ml_direction == 1:
                    ml_score_boost = 1.0
                elif ml_direction == -1:
                    ml_score_boost = -1.0
            
            # Update analysis dengan ML enhancements
            base_score = base_analysis.get('score', 0)
            final_score = base_score + ml_score_boost
            
            # Jangan biarkan score terlalu ekstrim
            final_score = max(min(final_score, 10), -10)
            
            base_analysis['ml_confidence'] = ml_confidence
            base_analysis['ml_direction'] = ml_direction
            base_analysis['ml_score_boost'] = ml_score_boost
            base_analysis['final_score'] = final_score
            
            # Update action berdasarkan final score
            if final_score >= 3:
                base_analysis['action'] = 'LONG'
            elif final_score <= -3:
                base_analysis['action'] = 'SHORT'
            else:
                base_analysis['action'] = 'NEUTRAL'
            
            base_analysis['ml_features'] = {
                'model_used': self.ml_bot.model_type,
                'feature_importance': self.ml_bot.feature_importance,
                'is_trained': self.ml_bot.is_trained
            }
            
            return base_analysis
            
        except Exception as e:
            print(f"❌ Error in ML analysis: {e}")
            return self.analyze_asset(symbol)  # Fallback ke analisis biasa

    def train_ml_model(self, training_symbols=None, days=365):
        """Train ML model dengan data historis"""
        try:
            if training_symbols is None:
                training_symbols = self.get_popular_assets(50)  # Gunakan 50 aset populer
            
            historical_data = {}
            
            print(f"📊 Collecting historical data for {len(training_symbols)} symbols...")
            
            for symbol in training_symbols:
                try:
                    # Get data 1 tahun kebelakang
                    df = self.data_provider.get_ohlcv(symbol, '1d', days)
                    if df is not None and len(df) > 100:
                        historical_data[symbol] = df
                        print(f"  ✅ Collected data for {symbol}: {len(df)} bars")
                    else:
                        print(f"  ⚠️ Insufficient data for {symbol}")
                except Exception as e:
                    print(f"  ❌ Error getting data for {symbol}: {e}")
            
            if len(historical_data) < 10:
                print("❌ Not enough historical data for training")
                return False
            
            print(f"🔄 Training ML model with {len(historical_data)} symbols...")
            success = self.ml_bot.train_model(historical_data)
            
            if success:
                print("✅ ML model training completed successfully!")
            else:
                print("❌ ML model training failed")
            
            return success
            
        except Exception as e:
            print(f"❌ Error in ML model training: {e}")
            return False

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
            
            # Prepare data untuk batch ML prediction
            symbols_data = {}
            for asset in assets:
                try:
                    df = self.data_provider.get_ohlcv(asset, self.timeframe, 100)
                    if df is not None and len(df) > 50:
                        symbols_data[asset] = df
                except:
                    continue
            
            # Dapatkan batch ML predictions
            ml_predictions = self.update_ml_predictions(symbols_data)
            
            results = []
            successful_analysis = 0
            failed_analysis = 0
            
            for i, asset in enumerate(assets):
                if self.stop_scheduler:
                    break
                    
                print(f"  Analyzing {i+1}/{len(assets)}: {asset}")
                
                try:
                    # Gunakan ML-enhanced analysis
                    analysis = self.analyze_with_ml(asset)
                    
                    if analysis:
                        score = analysis.get("final_score", analysis.get("score", 0))
                        min_score = self.config.get("min_score", 3)
                        
                        if (analysis.get("action") in ["LONG", "SHORT"] and 
                            abs(score) >= min_score):
                            
                            # Tambahkan ML info ke analysis
                            if asset in ml_predictions:
                                ml_info = ml_predictions[asset]
                                analysis['ml_prediction'] = ml_info
                            
                            results.append(analysis)
                            successful_analysis += 1
                            action_emoji = "🟢" if analysis['action'] == "LONG" else "🔴"
                            ml_indicator = " 🤖" if analysis.get('ml_confidence', 0) > 0.6 else ""
                            print(f"    {action_emoji} Signal found: {analysis['action']} (Score: {analysis['final_score']}){ml_indicator}")
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
            
            ml_enhanced_count = sum(1 for r in final_results if r.get('ml_confidence', 0) > 0.6)
            print(f"📊 Scan complete: {successful_analysis} successful, {failed_analysis} failed, {len(final_results)} signals found ({ml_enhanced_count} ML-enhanced)")
            
            return final_results
            
        except Exception as e:
            print(f"❌ Error in scan_potential_assets: {e}")
            return []
        finally:
            self.scanning_in_progress = False

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
                
                # ✅ PERBAIKAN KRITIS: Pastikan TP/SL tidak sama dengan current_price
                current_price = df['close'].iloc[-1] if len(df) > 0 else 0
                
                # Jika TP/SL sama dengan current_price, gunakan custom calculation
                if (analysis.get('tp1', 0) == analysis.get('tp2', 0) == 
                    analysis.get('tp3', 0) == analysis.get('sl', 0) == current_price):
                    print(f"   ⚠️ TP/SL sama dengan current price, menggunakan custom calculation...")
                    custom_result = self.calculate_custom_entry(original_symbol, current_price, analysis.get('action', 'LONG'))
                    if custom_result:
                        analysis.update(custom_result)
                
                # ✅ VALIDASI: Pastikan TP levels urutannya benar
                if analysis.get('action') == 'LONG':
                    tp1, tp2, tp3 = sorted([analysis.get('tp1', 0), analysis.get('tp2', 0), analysis.get('tp3', 0)])
                    analysis['tp1'] = tp1
                    analysis['tp2'] = tp2
                    analysis['tp3'] = tp3
                elif analysis.get('action') == 'SHORT':
                    tp1, tp2, tp3 = sorted([analysis.get('tp1', 0), analysis.get('tp2', 0), analysis.get('tp3', 0)], reverse=True)
                    analysis['tp1'] = tp1
                    analysis['tp2'] = tp2
                    analysis['tp3'] = tp3
                
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

    def search_assets(self, query, limit=100):
        """Search assets berdasarkan query untuk web interface"""
        if not self.data_provider:
            return []
        
        try:
            if hasattr(self.data_provider, 'search_assets'):
                return self.data_provider.search_assets(query, limit)
            else:
                all_assets = self.data_provider.get_popular_assets(limit=100)
                query_clean = query.upper().strip()
                
                if self.mode == 'forex':
                    results = [asset for asset in all_assets if query_clean in asset.replace('=X', '')]
                elif self.mode == 'saham_id':
                    results = [asset for asset in all_assets if query_clean in asset.replace('.JK', '')]
                else:
                    results = [asset for asset in all_assets if query_clean in asset]
                
                return results[:limit]
                
        except Exception as e:
            print(f"Error searching assets: {e}")
            return []

    def scan_selected_assets(self, symbols):
        """Scan specific symbols dengan error handling"""
        if not self.data_provider:
            return []
        
        results = []
        for symbol in symbols:
            try:
                analysis = self.analyze_asset(symbol)
                if analysis and analysis.get("action") in ["LONG", "SHORT"]:
                    results.append(analysis)
            except Exception as e:
                print(f"Error scanning {symbol}: {e}")
                continue
        
        return results

    async def scan_pump_fun(self):
        if not self.pump_provider:
            print("No Pump Fun provider available.")
            return []
        try:
            return await self.pump_provider.monitor_new_tokens(10)
        except Exception as e:
            print(f"Error scanning Pump Fun: {e}")
            return []

    def calculate_custom_entry(self, symbol, entry_price, action="LONG"):
        """Calculate custom entry dengan TP/SL dan probabilitas - DIPERBAIKI"""
        if not self.data_provider:
            print("No data provider for custom entry.")
            return self.calculate_fallback_entry(symbol, entry_price, action)
        
        try:
            df = self.data_provider.get_ohlcv(
                symbol, self.timeframe, self.config.get("ohlcv_limit", 200)
            )
            
            # ✅ PERBAIKAN: Jika tidak ada data, langsung gunakan fallback
            if df is None or len(df) < 20:
                print(f"Insufficient data for {symbol}, using fallback")
                return self.calculate_fallback_entry(symbol, entry_price, action)
            
            atr = self.strategy.calculate_atr(df)
            
            # ✅ PERBAIKAN: Validasi ATR lebih ketat
            if (atr is None or atr <= 0 or atr < entry_price * 0.0001 or 
                atr > entry_price * 0.5):  # ATR tidak boleh lebih dari 50% dari harga
                print(f"ATR invalid ({atr}) for {symbol}, using percentage-based calculation")
                return self.calculate_fallback_entry(symbol, entry_price, action)
            
            # Calculate TP/SL levels dengan ATR
            atr_multiplier = self.strategy.atr_multiplier
            
            if action == "LONG":
                tp1 = entry_price + (atr * atr_multiplier * 1)
                tp2 = entry_price + (atr * atr_multiplier * 2)
                tp3 = entry_price + (atr * atr_multiplier * 3)
                sl = entry_price - (atr * atr_multiplier * 1)
            else:  # SHORT
                tp1 = entry_price - (atr * atr_multiplier * 1)
                tp2 = entry_price - (atr * atr_multiplier * 2)
                tp3 = entry_price - (atr * atr_multiplier * 3)
                sl = entry_price + (atr * atr_multiplier * 1)
            
            # ✅ PERBAIKAN: Pastikan TP/SL berbeda dari entry price
            # Jika masih sama, gunakan fallback
            if (abs(tp1 - entry_price) < entry_price * 0.001 or 
                abs(tp2 - entry_price) < entry_price * 0.001 or
                abs(tp3 - entry_price) < entry_price * 0.001 or
                abs(sl - entry_price) < entry_price * 0.001):
                print(f"TP/SL too close to entry price, using fallback")
                return self.calculate_fallback_entry(symbol, entry_price, action)
            
            # ✅ FIXED: Urutkan TP levels
            if action == "LONG":
                tp1, tp2, tp3 = sorted([tp1, tp2, tp3])
            else:
                tp1, tp2, tp3 = sorted([tp1, tp2, tp3], reverse=True)
            
            # Calculate TP probabilities
            tp_probabilities = self.strategy.calculate_tp_probability(
                entry_price, tp1, tp2, tp3, sl, action
            )
            
            return {
                "symbol": symbol,
                "entry_price": float(entry_price),
                "tp1": float(tp1),
                "tp2": float(tp2),
                "tp3": float(tp3),
                "sl": float(sl),
                "action": action,
                "tp_probabilities": tp_probabilities,
                "atr_used": True
            }
            
        except Exception as e:
            print(f"Error calculating custom entry for {symbol}: {e}")
            return self.calculate_fallback_entry(symbol, entry_price, action)

    def calculate_fallback_entry(self, symbol, entry_price, action="LONG"):
        """Fallback calculation ketika data historis tidak cukup"""
        try:
            # ✅ PERBAIKAN: Gunakan persentase yang lebih reasonable
            if action == "LONG":
                tp1 = entry_price * 1.02  # +2%
                tp2 = entry_price * 1.05  # +5%
                tp3 = entry_price * 1.08  # +8%
                sl = entry_price * 0.97   # -3%
            else:  # SHORT
                tp1 = entry_price * 0.98  # -2%
                tp2 = entry_price * 0.95  # -5%
                tp3 = entry_price * 0.92  # -8%
                sl = entry_price * 1.03   # +3%
            
            # ✅ PERBAIKAN: Pastikan urutan TP levels benar
            if action == "LONG":
                tp1, tp2, tp3 = sorted([tp1, tp2, tp3])
            else:
                tp1, tp2, tp3 = sorted([tp1, tp2, tp3], reverse=True)
            
            # Calculate TP probabilities untuk fallback
            tp_probabilities = self.calculate_tp_probability_fallback(
                entry_price, tp1, tp2, tp3, sl, action
            )
            
            return {
                "symbol": symbol,
                "entry_price": float(entry_price),
                "tp1": float(tp1),
                "tp2": float(tp2),
                "tp3": float(tp3),
                "sl": float(sl),
                "action": action,
                "tp_probabilities": tp_probabilities,
                "fallback_used": True
            }
        except Exception as e:
            print(f"Error in fallback calculation: {e}")
            # Ultimate fallback
            return {
                "symbol": symbol,
                "entry_price": float(entry_price),
                "tp1": float(entry_price * 1.03),
                "tp2": float(entry_price * 1.06),
                "tp3": float(entry_price * 1.09),
                "sl": float(entry_price * 0.95),
                "action": action,
                "tp_probabilities": {"tp1": 0.4, "tp2": 0.25, "tp3": 0.15},
                "fallback_used": True
            }

    def calculate_tp_probability_fallback(self, current_price, tp1, tp2, tp3, sl, action, volatility=0.02):
        """Fallback TP probability calculation"""
        try:
            if action == "LONG":
                distances = {
                    'tp1': (tp1 - current_price) / current_price,
                    'tp2': (tp2 - current_price) / current_price,
                    'tp3': (tp3 - current_price) / current_price,
                    'sl': (current_price - sl) / current_price
                }
            else:  # SHORT
                distances = {
                    'tp1': (current_price - tp1) / current_price,
                    'tp2': (current_price - tp2) / current_price,
                    'tp3': (current_price - tp3) / current_price,
                    'sl': (sl - current_price) / current_price
                }
            
            probabilities = {}
            for target, distance in distances.items():
                if target.startswith('tp'):
                    if distance <= 0.02:  # 2%
                        base_prob = 0.6
                    elif distance <= 0.05:  # 5%
                        base_prob = 0.4
                    elif distance <= 0.08:  # 8%
                        base_prob = 0.25
                    else:  # >8%
                        base_prob = 0.15
                    
                    volatility_adjustment = volatility * 10
                    adjusted_prob = max(0.1, min(0.8, base_prob - volatility_adjustment))
                    probabilities[target] = adjusted_prob
            
            # Ensure probabilities make sense
            if 'tp1' in probabilities and 'tp2' in probabilities and 'tp3' in probabilities:
                if action == "LONG":
                    probabilities['tp1'] = max(probabilities['tp1'], probabilities['tp2'], probabilities['tp3'])
                    probabilities['tp2'] = min(probabilities['tp1'], max(probabilities['tp2'], probabilities['tp3']))
                    probabilities['tp3'] = min(probabilities['tp1'], probabilities['tp2'], probabilities['tp3'])
                else:
                    probabilities['tp1'] = max(probabilities['tp1'], probabilities['tp2'], probabilities['tp3'])
                    probabilities['tp2'] = min(probabilities['tp1'], max(probabilities['tp2'], probabilities['tp3']))
                    probabilities['tp3'] = min(probabilities['tp1'], probabilities['tp2'], probabilities['tp3'])
            
            return probabilities
            
        except Exception as e:
            print(f"Error in fallback TP probability: {e}")
            return {"tp1": 0.4, "tp2": 0.25, "tp3": 0.15}

    def get_active_positions(self):
        try:
            positions = self.db.get_active_positions(self.mode)
            for position in positions:
                symbol = position[1]
                try:
                    # Update current price
                    ticker = self.data_provider.get_ticker(symbol)
                    if ticker and 'last' in ticker:
                        current_price = ticker['last']
                        self.db.update_position_current_price(symbol, current_price)
                        
                        # ✅ PERBAIKAN: Jika TP/SL sama, perbaiki data di database
                        entry_price = position[4]
                        tp1 = position[7] if len(position) > 7 else 0
                        
                        if abs(tp1 - entry_price) < entry_price * 0.001:  # Jika TP1 sama dengan entry
                            print(f"⚠️ Fixing invalid TP/SL for {symbol}")
                            # Recalculate TP/SL
                            new_calculation = self.calculate_custom_entry(symbol, entry_price, position[3])
                            if new_calculation:
                                self.db.update_position_levels(
                                    symbol, 
                                    new_calculation['tp1'], 
                                    new_calculation['tp2'], 
                                    new_calculation['tp3'], 
                                    new_calculation['sl']
                                )
                except Exception as e:
                    print(f"Error updating price for {symbol}: {e}")
            return self.db.get_active_positions(self.mode)
        except Exception as e:
            print(f"Error fetching active positions: {e}")
            return []

    def get_trade_history(self, limit=100):
        try:
            return self.db.get_trade_history(self.mode, limit)
        except Exception as e:
            print(f"Error fetching trade history: {e}")
            return []

    def delete_signals_not_selected(self, selected_symbols):
        try:
            all_signals = self.db.get_all_signals(self.mode)
            for signal in all_signals:
                symbol = signal[1]
                if symbol not in selected_symbols:
                    self.db.delete_signal_by_symbol(symbol, self.mode)
                    print(f"Deleted non-selected signal for {symbol}")
        except Exception as e:
            print(f"Error deleting non-selected signals: {e}")

    def close_position(self, position_id, exit_price, exit_type="manual"):
        try:
            return self.db.close_position(position_id, exit_price, exit_type)
        except Exception as e:
            print(f"Error closing position: {e}")
            return False

    # Enhanced Backtest Methods
    def run_advanced_backtest(self, symbol, timeframe=None, limit=500):
        """Run advanced backtest dengan semua fitur baru"""
        if not self.data_provider:
            return {"error": "No data provider available"}
            
        try:
            if timeframe is None:
                timeframe = self.timeframe
                
            print(f"🔧 Running advanced backtest for {symbol}...")
            df = self.data_provider.get_ohlcv(symbol, timeframe, limit)
            
            if df is None or len(df) < 100:
                return {"error": "Insufficient data for backtest"}
            
            # Run basic backtest
            basic_result = self.backtest_engine.run_backtest(df, self.strategy)
            
            # Run Monte Carlo simulation if we have trades
            mc_result = {}
            if basic_result.get('total_trades', 0) > 10:
                # Get trades from basic backtest for Monte Carlo
                # Note: In a real implementation, you'd need to store the trades
                mc_result = self.backtest_engine.run_monte_carlo_simulation(
                    trades=[],  # You'd pass actual trades here
                    num_simulations=1000
                )
            
            return {
                'symbol': symbol,
                'timeframe': timeframe,
                'basic_backtest': basic_result,
                'monte_carlo': mc_result,
                'data_points': len(df)
            }
            
        except Exception as e:
            print(f"Error in advanced backtest: {e}")
            return {"error": str(e)}

    def run_walk_forward_analysis(self, symbol, periods=5):
        """Run walk-forward analysis untuk validasi strategy"""
        if not self.data_provider:
            return {"error": "No data provider available"}
            
        try:
            print(f"📊 Running walk-forward analysis for {symbol}...")
            df = self.data_provider.get_ohlcv(symbol, self.timeframe, 1000)  # Get more data
            
            if df is None or len(df) < 200:
                return {"error": "Insufficient data for walk-forward analysis"}
            
            result = self.backtest_engine.run_walk_forward_analysis(
                df, TechnicalAnalysisStrategy, periods=periods,
                market_type=self.mode
            )
            
            return {
                'symbol': symbol,
                'walk_forward_result': result
            }
            
        except Exception as e:
            print(f"Error in walk-forward analysis: {e}")
            return {"error": str(e)}

    def optimize_strategy_parameters(self, symbol, param_grid=None):
        """Optimize strategy parameters menggunakan grid search"""
        if not self.data_provider:
            return {"error": "No data provider available"}
            
        try:
            if param_grid is None:
                param_grid = {
                    'atr_multiplier': [0.5, 1.0, 1.5, 2.0],
                    'entry_range_pct': [0.01, 0.02, 0.03, 0.05],
                    'market_type': [self.mode]
                }
                
            print(f"⚙️ Optimizing parameters for {symbol}...")
            df = self.data_provider.get_ohlcv(symbol, self.timeframe, 500)
            
            if df is None or len(df) < 100:
                return {"error": "Insufficient data for parameter optimization"}
            
            result = self.backtest_engine.run_parameter_optimization(
                df, TechnicalAnalysisStrategy, param_grid
            )
            
            return {
                'symbol': symbol,
                'optimization_result': result
            }
            
        except Exception as e:
            print(f"Error in parameter optimization: {e}")
            return {"error": str(e)}

    def calculate_tp_probability(self, current_price, tp1, tp2, tp3, sl, action, volatility=0.02):
        """Calculate TP probabilities - wrapper untuk strategy method"""
        return self.strategy.calculate_tp_probability(
            current_price, tp1, tp2, tp3, sl, action, volatility
        )

    def optimize_portfolio_allocation(self, signals, total_capital):
        """Optimize portfolio allocation across signals"""
        return self.portfolio_optimizer.optimize_allocations(signals, total_capital)

    def get_risk_assessment(self, symbol):
        """Get comprehensive risk assessment untuk symbol"""
        try:
            analysis = self.analyze_asset(symbol)
            if analysis:
                return {
                    'symbol': symbol,
                    'risk_category': analysis.get('risk_metrics', {}).get('risk_category', 'MEDIUM'),
                    'volatility_level': analysis.get('volatility', 0.02),
                    'optimal_position_size': analysis.get('risk_metrics', {}).get('optimal_position_size', 0.1),
                    'reward_ratio': analysis.get('risk_metrics', {}).get('reward_ratio', 2.0),
                    'recommendation': self._generate_risk_recommendation(analysis)
                }
            return None
        except Exception as e:
            print(f"Error in risk assessment: {e}")
            return None

    def _generate_risk_recommendation(self, analysis):
        """Generate risk recommendation berdasarkan analysis"""
        risk_category = analysis.get('risk_metrics', {}).get('risk_category', 'MEDIUM')
        volatility = analysis.get('volatility', 0.02)
        
        if risk_category == 'HIGH' or volatility > 0.03:
            return "Consider smaller position size and tighter stop loss"
        elif risk_category == 'MEDIUM':
            return "Standard position sizing appropriate"
        else:
            return "Can consider larger position size with standard risk management"

    # New method untuk comprehensive backtest
    def run_comprehensive_backtest(self, symbol, days=180):
        """Run comprehensive backtest dengan multiple timeframes"""
        try:
            print(f"📊 Running comprehensive backtest for {symbol} over {days} days...")
            
            # Get data for different timeframes
            timeframes = ['1h', '4h', '1d']
            results = {}
            
            for tf in timeframes:
                df = self.data_provider.get_ohlcv(symbol, tf, days * 24)  # Estimate bars needed
                if df is not None and len(df) > 100:
                    result = self.backtest_engine.run_backtest(df, self.strategy)
                    results[tf] = result
                else:
                    results[tf] = {"error": f"Insufficient data for {tf} timeframe"}
            
            return {
                'symbol': symbol,
                'timeframe_results': results,
                'overall_score': self._calculate_overall_backtest_score(results)
            }
            
        except Exception as e:
            print(f"Error in comprehensive backtest: {e}")
            return {"error": str(e)}

    def _calculate_overall_backtest_score(self, results):
        """Calculate overall score from multiple timeframe results"""
        try:
            scores = []
            for tf, result in results.items():
                if 'error' not in result:
                    # Combine multiple metrics for score
                    win_rate = result.get('win_rate', 0)
                    sharpe = max(result.get('sharpe_ratio', 0), 0)
                    profit_factor = min(result.get('profit_factor', 1), 10)
                    
                    timeframe_score = (win_rate * 0.4 + sharpe * 0.3 + profit_factor * 0.1)
                    scores.append(timeframe_score)
            
            return np.mean(scores) if scores else 0
        except:
            return 0
