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
        
        # Auto-retraining configuration
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

    # ... (sisanya sama seperti sebelumnya, termasuk train_model, predict, dll.)
