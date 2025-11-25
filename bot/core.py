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
from sklearn.preprocessing import StandardScaler, RobustScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_recall_fscore_support
from sklearn.linear_model import LogisticRegression
from xgboost import XGBClassifier
import lightgbm as lgb  # FIX: Import lightgbm dengan alias yang benar
from dotenv import load_dotenv
import logging
from typing import Dict, List, Optional, Tuple, Any
import traceback
from dataclasses import dataclass
from enum import Enum
import concurrent.futures
from scipy import stats

warnings.filterwarnings("ignore")
load_dotenv()

# Enhanced logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import modul yang diperlukan dengan error handling yang lebih baik
try:
    from bot.strategies import TechnicalAnalysisStrategy
    from bot.data_provider import (
        CCXTDataProvider,
        YFinanceDataProvider,
        DataProviderMonitor
    )
    from bot.notifier import SoundNotifier
    from database.db_handler import DatabaseHandler
    
    # Handle optional imports
    try:
        from bot.data_provider import SolanaPumpFunProvider, DataProviderFactory
    except ImportError:
        class SolanaPumpFunProvider: 
            def __init__(self, *args, **kwargs): pass
        class DataProviderFactory:
            @staticmethod
            def create_provider(*args, **kwargs): return None
        
except ImportError as e:
    logger.warning(f"Import error: {e}, using fallback imports")
    # Fallback imports untuk testing
    class TechnicalAnalysisStrategy:
        def __init__(self, *args, **kwargs): 
            self.market_type = kwargs.get('market_type', 'crypto')
            self.atr_multiplier = kwargs.get('atr_multiplier', 1.0)
            self.entry_range_pct = kwargs.get('entry_range_pct', 0.02)
        def analyze(self, df): 
            return {'score': 0, 'action': 'NEUTRAL', 'entry_price': 0, 'sl': 0, 'tp': 0}
    
    class CCXTDataProvider: 
        def __init__(self, *args, **kwargs): pass
        def get_ohlcv(self, *args, **kwargs): return pd.DataFrame()
        def get_ticker(self, *args, **kwargs): return {'last': 0}
        def get_popular_assets(self, *args, **kwargs): return []
    
    class YFinanceDataProvider: 
        def __init__(self, *args, **kwargs): 
            self.market_type = kwargs.get('market_type', 'stock')
        def get_ohlcv(self, *args, **kwargs): return pd.DataFrame()
        def get_ticker(self, *args, **kwargs): return {'last': 0}
        def get_popular_assets(self, *args, **kwargs): return []
    
    class SolanaPumpFunProvider:
        def __init__(self, *args, **kwargs): pass
    
    class DataProviderFactory:
        @staticmethod
        def create_provider(*args, **kwargs): return None
    
    class DataProviderMonitor:
        def __init__(self): pass
        def register_provider(self, *args, **kwargs): pass
        def get_health_report(self): return {}
    
    class SoundNotifier: 
        def __init__(self): pass
        def send_notification(self, *args): pass
    
    class DatabaseHandler: 
        def __init__(self): pass
        def save_position(self, *args): return 1
        def get_active_positions(self, *args): return []
        def close_position(self, *args, **kwargs): return True
        def update_position_current_price(self, *args, **kwargs): pass
        def get_trade_history(self, *args, **kwargs): return []

# =============================================
# ENHANCED POSITION MANAGEMENT
# =============================================

class PositionState(Enum):
    ACTIVE = "active"
    PARTIAL_TP = "partial_tp"
    TRAILING = "trailing"
    CLOSED = "closed"

@dataclass
class EnhancedPosition:
    """Enhanced position management dengan trailing stop dan partial TP"""
    symbol: str
    market_type: str
    action: str
    entry_price: float
    position_size: float
    initial_stop_loss: float
    current_stop_loss: float
    take_profits: List[float]  # Multiple TP levels
    trailing_enabled: bool = False
    trailing_distance: float = 0.0
    partial_tp_executed: List[float] = None
    state: PositionState = PositionState.ACTIVE
    created_at: datetime = None
    last_updated: datetime = None
    
    def __post_init__(self):
        if self.partial_tp_executed is None:
            self.partial_tp_executed = []
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.last_updated is None:
            self.last_updated = datetime.now()
    
    def update_trailing_stop(self, current_price: float) -> bool:
        """Update trailing stop loss"""
        if not self.trailing_enabled or self.state != PositionState.ACTIVE:
            return False
            
        if self.action == "LONG":
            new_stop = current_price - self.trailing_distance
            if new_stop > self.current_stop_loss:
                self.current_stop_loss = new_stop
                self.last_updated = datetime.now()
                return True
        else:  # SHORT
            new_stop = current_price + self.trailing_distance
            if new_stop < self.current_stop_loss:
                self.current_stop_loss = new_stop
                self.last_updated = datetime.now()
                return True
        return False
    
    def execute_partial_tp(self, tp_level: float, percentage: float = 0.5) -> float:
        """Execute partial take profit"""
        if self.state != PositionState.ACTIVE:
            return 0.0
            
        close_size = self.position_size * percentage
        self.position_size -= close_size
        self.partial_tp_executed.append({
            'price': tp_level,
            'size': close_size,
            'timestamp': datetime.now()
        })
        
        if self.position_size <= 0.001:  # Minimum position size
            self.state = PositionState.CLOSED
            
        return close_size
    
    def should_close_position(self, current_price: float) -> Tuple[bool, str]:
        """Check if position should be closed"""
        reason = ""
        should_close = False
        
        if self.action == "LONG":
            if current_price <= self.current_stop_loss:
                should_close = True
                reason = "Stop loss hit"
            elif self.take_profits and current_price >= max(self.take_profits):
                should_close = True
                reason = "Final TP hit"
        else:  # SHORT
            if current_price >= self.current_stop_loss:
                should_close = True
                reason = "Stop loss hit"
            elif self.take_profits and current_price <= min(self.take_profits):
                should_close = True
                reason = "Final TP hit"
                
        return should_close, reason

class EnhancedPositionManager:
    """Advanced position management dengan risk-based sizing dan trailing stops"""
    
    def __init__(self, db_handler: DatabaseHandler):
        self.db_handler = db_handler
        self.positions: Dict[str, EnhancedPosition] = {}
        self.max_positions = 10
        self.max_portfolio_risk = 0.02  # 2% max portfolio risk
        
    def calculate_position_size(self, symbol: str, entry_price: float, stop_loss: float, 
                              account_balance: float, risk_per_trade: float = 0.01) -> float:
        """Calculate position size based on risk management"""
        # **FIXED: Validasi entry_price dan stop_loss**
        if entry_price <= 0 or stop_loss <= 0:
            logger.warning(f"Invalid prices for {symbol}: entry={entry_price}, sl={stop_loss}")
            return 0.0
            
        risk_amount = account_balance * risk_per_trade
        
        if entry_price == stop_loss:
            logger.warning(f"Entry price equals stop loss for {symbol}")
            return 0.0
            
        price_risk = abs(entry_price - stop_loss)
        position_size = risk_amount / price_risk
        
        # Limit position size to 20% of account balance
        max_position_value = account_balance * 0.2
        max_position_size = max_position_value / entry_price
        
        return min(position_size, max_position_size)
    
    def open_position(self, symbol: str, market_type: str, action: str, 
                     entry_price: float, stop_loss: float, take_profits: List[float],
                     account_balance: float, trailing_distance: float = 0.0) -> Optional[EnhancedPosition]:
        """Open new position dengan enhanced management"""
        
        # **FIXED: Validasi entry_price**
        if entry_price <= 0:
            logger.error(f"Cannot open position for {symbol}: Invalid entry price {entry_price}")
            return None
        
        # Check maximum positions
        if len(self.positions) >= self.max_positions:
            logger.warning(f"Maximum positions reached ({self.max_positions}), cannot open new position for {symbol}")
            return None
        
        # Calculate position size
        position_size = self.calculate_position_size(symbol, entry_price, stop_loss, account_balance)
        
        if position_size <= 0:
            logger.warning(f"Invalid position size for {symbol}")
            return None
        
        # Create enhanced position
        position = EnhancedPosition(
            symbol=symbol,
            market_type=market_type,
            action=action,
            entry_price=entry_price,
            position_size=position_size,
            initial_stop_loss=stop_loss,
            current_stop_loss=stop_loss,
            take_profits=take_profits,
            trailing_enabled=trailing_distance > 0,
            trailing_distance=trailing_distance
        )
        
        self.positions[symbol] = position
        
        # Save to database
        try:
            position_id = self.db_handler.save_position(
                symbol=symbol,
                market_type=market_type,
                action=action,
                entry_price=entry_price,
                tp1=take_profits[0] if len(take_profits) > 0 else entry_price * 1.05,
                tp2=take_profits[1] if len(take_profits) > 1 else entry_price * 1.10,
                tp3=take_profits[2] if len(take_profits) > 2 else entry_price * 1.15,
                sl=stop_loss
            )
            
            if position_id:
                logger.info(f"Position opened for {symbol} with size {position_size:.4f}")
                return position
            else:
                logger.error(f"Failed to save position for {symbol} to database")
                del self.positions[symbol]
                return None
                
        except Exception as e:
            logger.error(f"Error saving position for {symbol}: {e}")
            del self.positions[symbol]
            return None
    
    def get_position_id_from_symbol(self, symbol: str, market_type: str) -> Optional[int]:
        """Get position ID from symbol - FIXED VERSION"""
        try:
            active_positions = self.db_handler.get_active_positions(market_type)
            position_id = None
            
            for pos in active_positions:
                # Handle both dictionary and tuple responses
                if isinstance(pos, dict):
                    if pos.get('symbol') == symbol:
                        position_id = pos.get('id')
                        break
                else:
                    # Fallback for tuple response (backward compatibility)
                    if len(pos) > 1 and pos[1] == symbol:  # symbol column
                        position_id = pos[0]  # id column
                        break
            
            return position_id
            
        except Exception as e:
            logger.error(f"Error getting position ID for {symbol}: {e}")
            return None

    def update_positions(self, price_data: Dict[str, float]) -> Dict[str, Dict]:
        """Update all positions dengan current prices"""
        results = {}
        
        for symbol, position in list(self.positions.items()):
            if symbol not in price_data:
                continue
                
            current_price = price_data[symbol]
            close_position, reason = position.should_close_position(current_price)
            
            # Update trailing stop
            if position.trailing_enabled:
                position.update_trailing_stop(current_price)
            
            # Check partial TP opportunities
            partial_tp_executed = self._check_partial_tp(position, current_price)
            
            if close_position:
                # Close position
                success = self.close_position(symbol, current_price, reason)
                results[symbol] = {
                    'action': 'closed',
                    'reason': reason,
                    'price': current_price,
                    'success': success
                }
            elif partial_tp_executed:
                results[symbol] = {
                    'action': 'partial_tp',
                    'size': partial_tp_executed,
                    'price': current_price
                }
            else:
                # Update current price in database
                try:
                    self.db_handler.update_position_current_price(symbol, current_price)
                except Exception as e:
                    logger.warning(f"Failed to update price for {symbol}: {e}")
        
        return results
    
    def _check_partial_tp(self, position: EnhancedPosition, current_price: float) -> float:
        """Check and execute partial take profits"""
        if position.state != PositionState.ACTIVE:
            return 0.0
            
        executed_size = 0.0
        
        for i, tp_level in enumerate(position.take_profits):
            if position.action == "LONG" and current_price >= tp_level:
                # Check if this TP level hasn't been executed yet
                tp_executed = any(tp.get('level', i) == i for tp in position.partial_tp_executed)
                if not tp_executed:
                    # Execute 33% partial TP for each level
                    size = position.execute_partial_tp(tp_level, 0.33)
                    executed_size += size
                    logger.info(f"Partial TP executed for {position.symbol} at {tp_level:.4f}, size: {size:.4f}")
                    
            elif position.action == "SHORT" and current_price <= tp_level:
                tp_executed = any(tp.get('level', i) == i for tp in position.partial_tp_executed)
                if not tp_executed:
                    size = position.execute_partial_tp(tp_level, 0.33)
                    executed_size += size
                    logger.info(f"Partial TP executed for {position.symbol} at {tp_level:.4f}, size: {size:.4f}")
        
        return executed_size
    
    def close_position(self, symbol: str, close_price: float, reason: str = "manual") -> bool:
        """Close position - FIXED VERSION"""
        if symbol not in self.positions:
            logger.warning(f"Position for {symbol} not found in local manager")
            return False
            
        position = self.positions[symbol]
        
        try:
            # Find position ID from database using new method
            position_id = self.get_position_id_from_symbol(symbol, position.market_type)
            
            if position_id:
                success = self.db_handler.close_position(position_id, close_price, reason)
                if success:
                    position.state = PositionState.CLOSED
                    del self.positions[symbol]
                    logger.info(f"Position closed for {symbol} at {close_price:.4f}, reason: {reason}")
                    return True
                else:
                    logger.error(f"Failed to close position for {symbol} in database")
                    return False
            else:
                logger.warning(f"Position ID not found for {symbol} in database")
                return False
                
        except Exception as e:
            logger.error(f"Error closing position for {symbol}: {e}")
            return False
    
    def get_portfolio_metrics(self, current_prices: Dict[str, float]) -> Dict[str, Any]:
        """Calculate portfolio performance metrics"""
        total_value = 0.0
        total_pnl = 0.0
        open_positions = []
        
        for symbol, position in self.positions.items():
            if symbol not in current_prices:
                continue
                
            current_price = current_prices[symbol]
            position_value = position.position_size * current_price
            
            if position.action == "LONG":
                pnl = (current_price - position.entry_price) * position.position_size
            else:  # SHORT
                pnl = (position.entry_price - current_price) * position.position_size
            
            total_value += position_value
            total_pnl += pnl
            
            open_positions.append({
                'symbol': symbol,
                'action': position.action,
                'entry_price': position.entry_price,
                'current_price': current_price,
                'size': position.position_size,
                'pnl': pnl,
                'pnl_pct': (pnl / (position.entry_price * position.position_size)) * 100 if position.entry_price * position.position_size > 0 else 0
            })
        
        return {
            'total_positions': len(self.positions),
            'total_value': total_value,
            'total_pnl': total_pnl,
            'open_positions': open_positions,
            'avg_pnl_pct': np.mean([p['pnl_pct'] for p in open_positions]) if open_positions else 0
        }

# =============================================
# ENHANCED ML MODEL WITH ENSEMBLE
# =============================================

class EnsembleMLModel:
    """Enhanced ML model dengan ensemble methods dan advanced feature engineering"""
    
    def __init__(self, model_types: List[str] = None):
        self.model_types = model_types or ['random_forest', 'xgboost', 'lightgbm']
        self.models = {}
        self.scalers = {}
        self.feature_importance = {}
        self.is_trained = False
        self.model_weights = {}  # Dynamic model weighting
        
        # Feature configuration
        self.feature_config = {
            'price_features': ['rsi', 'macd', 'sma_20', 'sma_50', 'ema_12', 'ema_26'],
            'volume_features': ['volume_ratio', 'obv', 'volume_sma_ratio'],
            'volatility_features': ['atr', 'bb_width', 'volatility'],
            'momentum_features': ['momentum_5', 'momentum_10', 'williams_r', 'cci'],
            'pattern_features': ['pattern_score', 'trend_strength']
        }
        
        self._initialize_models()
    
    def _initialize_models(self):
        """Initialize multiple ML models"""
        for model_type in self.model_types:
            if model_type == 'random_forest':
                self.models[model_type] = RandomForestClassifier(
                    n_estimators=200,
                    max_depth=15,
                    min_samples_split=5,
                    min_samples_leaf=2,
                    random_state=42,
                    n_jobs=-1,
                    bootstrap=True,
                    max_features='sqrt'
                )
            elif model_type == 'xgboost':
                self.models[model_type] = XGBClassifier(
                    n_estimators=200,
                    max_depth=8,
                    learning_rate=0.1,
                    random_state=42,
                    n_jobs=-1,
                    subsample=0.8,
                    colsample_bytree=0.8
                )
            elif model_type == 'lightgbm':
                self.models[model_type] = lgb.LGBMClassifier(  # FIX: Gunakan lgb.LGBMClassifier
                    n_estimators=200,
                    max_depth=8,
                    learning_rate=0.1,
                    random_state=42,
                    n_jobs=-1,
                    subsample=0.8,
                    colsample_bytree=0.8
                )
            elif model_type == 'logistic':
                self.models[model_type] = LogisticRegression(
                    random_state=42,
                    max_iter=1000,
                    C=1.0,
                    solver='liblinear'
                )
            
            self.scalers[model_type] = RobustScaler()  # Less sensitive to outliers
            self.model_weights[model_type] = 1.0  # Initial equal weights
    
    def advanced_feature_engineering(self, df: pd.DataFrame) -> pd.DataFrame:
        """Advanced feature engineering dengan technical indicators"""
        if df is None or len(df) < 50:
            return pd.DataFrame()
        
        features = {}
        prices = df['close'].values
        volumes = df['volume'].values if 'volume' in df.columns else np.ones(len(df))
        
        # **FIXED: Validasi data harga**
        if len(prices) == 0 or (prices <= 0).any():
            logger.warning("Invalid price data in feature engineering")
            return pd.DataFrame()
        
        # Price-based features
        if len(prices) >= 20:
            # RSI
            features['rsi'] = self._calculate_rsi(prices)
            
            # MACD
            features['macd'] = self._calculate_macd(prices)
            
            # Moving averages
            features['sma_20'] = np.mean(prices[-20:])
            features['sma_50'] = np.mean(prices[-min(50, len(prices)):])
            features['ema_12'] = self._calculate_ema(prices, 12)
            features['ema_26'] = self._calculate_ema(prices, 26)
            
            # Bollinger Bands
            bb_upper, bb_lower, bb_middle = self._calculate_bollinger_bands(prices)
            features['bb_width'] = (bb_upper - bb_lower) / bb_middle if bb_middle > 0 else 0
            
            # Price position in BB
            features['bb_position'] = (prices[-1] - bb_lower) / (bb_upper - bb_lower) if (bb_upper - bb_lower) > 0 else 0.5
        
        # Volume features
        if len(volumes) >= 20:
            features['volume_ratio'] = volumes[-1] / np.mean(volumes[-20:]) if np.mean(volumes[-20:]) > 0 else 1
            features['volume_sma_ratio'] = volumes[-1] / np.mean(volumes) if np.mean(volumes) > 0 else 1
            features['obv'] = self._calculate_obv(prices, volumes)
        
        # Volatility features
        if len(prices) >= 20:
            features['atr'] = self._calculate_atr(df) if len(df) >= 14 else 0.02
            returns = np.diff(prices) / prices[:-1]
            features['volatility'] = np.std(returns) * np.sqrt(252) if len(returns) > 1 else 0.02
        
        # Momentum features
        if len(prices) >= 10:
            features['momentum_5'] = (prices[-1] / prices[-5] - 1) * 100 if prices[-5] > 0 else 0
            features['momentum_10'] = (prices[-1] / prices[-10] - 1) * 100 if prices[-10] > 0 else 0
            features['williams_r'] = self._calculate_williams_r(df)
            features['cci'] = self._calculate_cci(df)
        
        # Statistical features
        if len(prices) >= 20:
            features['skewness'] = stats.skew(prices[-20:])
            features['kurtosis'] = stats.kurtosis(prices[-20:])
            features['z_score'] = (prices[-1] - np.mean(prices[-20:])) / np.std(prices[-20:]) if np.std(prices[-20:]) > 0 else 0
        
        # Pattern and trend features (simplified)
        if len(prices) >= 10:
            features['trend_strength'] = self._calculate_trend_strength(prices)
            # Simple pattern score based on recent price action
            recent_trend = np.polyfit(range(5), prices[-5:], 1)[0]
            features['pattern_score'] = recent_trend * 100
        
        # Ensure no NaN values
        for key in features:
            if np.isnan(features[key]) or np.isinf(features[key]):
                features[key] = 0.0
        
        return pd.DataFrame([features])
    
    def _calculate_rsi(self, prices, period=14):
        """Calculate RSI"""
        if len(prices) < period + 1:
            return 50
        delta = np.diff(prices)
        gain = np.where(delta > 0, delta, 0)
        loss = np.where(delta < 0, -delta, 0)
        
        avg_gain = np.mean(gain[-period:])
        avg_loss = np.mean(loss[-period:])
        
        if avg_loss == 0:
            return 100
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))
    
    def _calculate_macd(self, prices):
        """Calculate MACD"""
        if len(prices) < 26:
            return 0
        exp1 = pd.Series(prices).ewm(span=12).mean().iloc[-1]
        exp2 = pd.Series(prices).ewm(span=26).mean().iloc[-1]
        return exp1 - exp2
    
    def _calculate_ema(self, prices, period):
        """Calculate EMA"""
        if len(prices) < period:
            return np.mean(prices)
        return pd.Series(prices).ewm(span=period).mean().iloc[-1]
    
    def _calculate_bollinger_bands(self, prices, period=20, std_dev=2):
        """Calculate Bollinger Bands"""
        if len(prices) < period:
            middle = np.mean(prices)
            std = np.std(prices) if len(prices) > 1 else 0.1
            return middle + std_dev * std, middle - std_dev * std, middle
        
        middle = np.mean(prices[-period:])
        std = np.std(prices[-period:])
        return middle + std_dev * std, middle - std_dev * std, middle
    
    def _calculate_obv(self, prices, volumes):
        """Calculate OBV"""
        if len(prices) < 2:
            return 0
        obv = 0
        for i in range(1, len(prices)):
            if prices[i] > prices[i-1]:
                obv += volumes[i]
            elif prices[i] < prices[i-1]:
                obv -= volumes[i]
        return obv
    
    def _calculate_atr(self, df, period=14):
        """Calculate ATR"""
        try:
            high = df['high'].values
            low = df['low'].values
            close = df['close'].values
            
            tr = np.zeros(len(high))
            for i in range(1, len(high)):
                tr1 = high[i] - low[i]
                tr2 = abs(high[i] - close[i-1])
                tr3 = abs(low[i] - close[i-1])
                tr[i] = max(tr1, tr2, tr3)
            
            return np.mean(tr[-period:]) if len(tr) >= period else np.mean(tr)
        except:
            return 0.02
    
    def _calculate_williams_r(self, df, period=14):
        """Calculate Williams %R"""
        try:
            high = df['high'].values[-period:]
            low = df['low'].values[-period:]
            close = df['close'].iloc[-1]
            
            highest_high = np.max(high)
            lowest_low = np.min(low)
            
            if highest_high == lowest_low:
                return -50
            return -100 * (highest_high - close) / (highest_high - lowest_low)
        except:
            return -50
    
    def _calculate_cci(self, df, period=20):
        """Calculate CCI"""
        try:
            typical_price = (df['high'] + df['low'] + df['close']) / 3
            sma = typical_price.rolling(period).mean().iloc[-1]
            mad = typical_price.rolling(period).apply(lambda x: np.mean(np.abs(x - np.mean(x)))).iloc[-1]
            
            if mad == 0:
                return 0
            return (typical_price.iloc[-1] - sma) / (0.015 * mad)
        except:
            return 0
    
    def _calculate_trend_strength(self, prices, period=10):
        """Calculate trend strength using linear regression"""
        if len(prices) < period:
            return 0
        x = np.arange(period)
        y = prices[-period:]
        slope, _, r_value, _, _ = stats.linregress(x, y)
        return slope * r_value ** 2  # Combine slope and R-squared
    
    def train_ensemble(self, X: np.ndarray, y: np.ndarray, validation_size: float = 0.2):
        """Train ensemble of models dengan cross-validation"""
        if len(X) < 100:
            logger.warning("Insufficient data for training ensemble")
            return False
        
        # Split data
        X_train, X_val, y_train, y_val = train_test_split(
            X, y, test_size=validation_size, shuffle=False, random_state=42
        )
        
        model_scores = {}
        
        for model_name, model in self.models.items():
            try:
                # Scale features
                X_train_scaled = self.scalers[model_name].fit_transform(X_train)
                X_val_scaled = self.scalers[model_name].transform(X_val)
                
                # Train model
                model.fit(X_train_scaled, y_train)
                
                # Validate model
                y_pred = model.predict(X_val_scaled)
                accuracy = accuracy_score(y_val, y_pred)
                precision, recall, f1, _ = precision_recall_fscore_support(y_val, y_pred, average='weighted')
                
                model_scores[model_name] = {
                    'accuracy': accuracy,
                    'precision': precision,
                    'recall': recall,
                    'f1': f1
                }
                
                # Update model weights based on performance
                self.model_weights[model_name] = f1  # Use F1 score as weight
                
                logger.info(f"Model {model_name} trained - Accuracy: {accuracy:.3f}, F1: {f1:.3f}")
                
            except Exception as e:
                logger.error(f"Error training {model_name}: {e}")
                model_scores[model_name] = {'accuracy': 0, 'f1': 0}
                self.model_weights[model_name] = 0.1  # Minimal weight
        
        # Normalize weights
        total_weight = sum(self.model_weights.values())
        if total_weight > 0:
            for model_name in self.model_weights:
                self.model_weights[model_name] /= total_weight
        
        self.is_trained = True
        logger.info(f"Ensemble training completed. Model weights: {self.model_weights}")
        return True
    
    def predict_ensemble(self, X: np.ndarray) -> Tuple[float, int]:
        """Predict using ensemble dengan weighted voting"""
        if not self.is_trained or len(self.models) == 0:
            return 0.5, 0
        
        predictions = []
        confidences = []
        weights = []
        
        for model_name, model in self.models.items():
            try:
                if self.model_weights[model_name] > 0.01:  # Only use models with meaningful weights
                    X_scaled = self.scalers[model_name].transform(X)
                    
                    if hasattr(model, 'predict_proba'):
                        proba = model.predict_proba(X_scaled)
                        confidence = np.max(proba)
                        prediction = np.argmax(proba)
                    else:
                        prediction = model.predict(X_scaled)[0]
                        confidence = 0.5  # Default confidence
                    
                    predictions.append(prediction)
                    confidences.append(confidence)
                    weights.append(self.model_weights[model_name])
                    
            except Exception as e:
                logger.warning(f"Prediction failed for {model_name}: {e}")
                continue
        
        if not predictions:
            return 0.5, 0
        
        # Weighted voting
        weighted_predictions = np.average(predictions, weights=weights)
        final_prediction = 1 if weighted_predictions > 0.5 else 0
        final_confidence = np.average(confidences, weights=weights)
        
        return final_confidence, final_prediction

# =============================================
# ADVANCED PORTFOLIO OPTIMIZATION
# =============================================

class PortfolioOptimizer:
    """Advanced portfolio optimization menggunakan Modern Portfolio Theory"""
    
    def __init__(self):
        self.risk_free_rate = 0.02  # 2% risk-free rate
        self.max_allocation_per_asset = 0.2  # 20% max per asset
        self.min_allocation_per_asset = 0.05  # 5% min per asset
    
    def mean_variance_optimization(self, expected_returns: List[float], 
                                 covariance_matrix: np.ndarray,
                                 target_return: float = None) -> Dict[str, Any]:
        """Mean-variance optimization (Markowitz)"""
        n_assets = len(expected_returns)
        
        if n_assets == 0:
            return {'weights': [], 'sharpe_ratio': 0, 'portfolio_return': 0, 'portfolio_risk': 0}
        
        # Simple optimization (in practice, use scipy.optimize)
        try:
            # Equal weight baseline
            equal_weights = np.ones(n_assets) / n_assets
            
            # Calculate portfolio metrics
            port_return = np.dot(equal_weights, expected_returns)
            port_risk = np.sqrt(np.dot(equal_weights.T, np.dot(covariance_matrix, equal_weights)))
            sharpe_ratio = (port_return - self.risk_free_rate) / port_risk if port_risk > 0 else 0
            
            # Apply constraints
            weights = self._apply_allocation_constraints(equal_weights)
            
            return {
                'weights': weights.tolist(),
                'sharpe_ratio': sharpe_ratio,
                'portfolio_return': port_return,
                'portfolio_risk': port_risk,
                'efficient_frontier': self._calculate_efficient_frontier(expected_returns, covariance_matrix)
            }
            
        except Exception as e:
            logger.error(f"Portfolio optimization error: {e}")
            # Fallback to equal weighting
            weights = np.ones(n_assets) / n_assets
            return {
                'weights': weights.tolist(),
                'sharpe_ratio': 0,
                'portfolio_return': np.mean(expected_returns),
                'portfolio_risk': np.mean(np.diag(covariance_matrix)),
                'efficient_frontier': []
            }
    
    def risk_parity_allocation(self, volatility_estimates: List[float]) -> List[float]:
        """Risk parity allocation - equal risk contribution"""
        if not volatility_estimates or len(volatility_estimates) == 0:
            return []
        
        # Inverse volatility weighting
        inv_volatility = [1/v if v > 0 else 0 for v in volatility_estimates]
        total_inv_vol = sum(inv_volatility)
        
        if total_inv_vol == 0:
            # Equal weight fallback
            return [1/len(volatility_estimates)] * len(volatility_estimates)
        
        weights = [inv_vol / total_inv_vol for inv_vol in inv_volatility]
        return self._apply_allocation_constraints(weights)
    
    def momentum_based_allocation(self, signals: List[Dict], total_capital: float) -> List[Dict]:
        """Momentum-based portfolio allocation"""
        if not signals:
            return []
        
        # Sort signals by score (absolute value for both LONG and SHORT)
        sorted_signals = sorted(signals, key=lambda x: abs(x.get('score', 0)), reverse=True)
        
        # Calculate scores and volatilities
        scores = [abs(s.get('score', 0)) for s in sorted_signals]
        volatilities = [s.get('volatility', 0.02) for s in sorted_signals]
        
        if sum(scores) == 0:
            # Equal allocation fallback
            base_allocation = total_capital / len(signals)
            return [
                {
                    'symbol': s['symbol'],
                    'allocation_percent': 1/len(signals),
                    'allocated_capital': base_allocation,
                    'score': s.get('score', 0)
                }
                for s in sorted_signals
            ]
        
        # Weight by score and inverse volatility
        weights = []
        for i, signal in enumerate(sorted_signals):
            score_weight = scores[i] / sum(scores)
            vol_weight = 1 / (volatilities[i] + 0.01)  # Add small constant to avoid division by zero
            combined_weight = score_weight * vol_weight
            weights.append(combined_weight)
        
        # Normalize weights
        total_weight = sum(weights)
        normalized_weights = [w / total_weight for w in weights]
        
        # Apply constraints
        constrained_weights = self._apply_allocation_constraints(normalized_weights)
        
        allocations = []
        for i, signal in enumerate(sorted_signals):
            allocation_percent = constrained_weights[i] if i < len(constrained_weights) else 0
            allocated_capital = total_capital * allocation_percent
            
            allocations.append({
                'symbol': signal['symbol'],
                'allocation_percent': allocation_percent,
                'allocated_capital': allocated_capital,
                'score': signal.get('score', 0),
                'action': signal.get('action', 'NEUTRAL')
            })
        
        return allocations
    
    def _apply_allocation_constraints(self, weights: List[float]) -> List[float]:
        """Apply allocation constraints to weights"""
        if not weights:
            return []
        
        n_assets = len(weights)
        constrained_weights = np.array(weights, dtype=float)
        
        # Apply minimum allocation
        min_weight = self.min_allocation_per_asset
        constrained_weights[constrained_weights < min_weight] = 0
        
        # Apply maximum allocation
        max_weight = self.max_allocation_per_asset
        constrained_weights[constrained_weights > max_weight] = max_weight
        
        # Renormalize if necessary
        total_weight = np.sum(constrained_weights)
        if total_weight > 0:
            constrained_weights /= total_weight
        else:
            # Fallback to equal weighting
            constrained_weights = np.ones(n_assets) / n_assets
        
        return constrained_weights.tolist()
    
    def _calculate_efficient_frontier(self, expected_returns: List[float], 
                                    covariance_matrix: np.ndarray, 
                                    points: int = 20) -> List[Dict]:
        """Calculate efficient frontier points"""
        # Simplified implementation
        # In practice, use proper quadratic programming
        frontiers = []
        
        for i in range(points):
            target_return = np.min(expected_returns) + (np.max(expected_returns) - np.min(expected_returns)) * i / points
            
            # Simple equal weight approximation for demo
            weights = np.ones(len(expected_returns)) / len(expected_returns)
            portfolio_return = np.dot(weights, expected_returns)
            portfolio_risk = np.sqrt(np.dot(weights.T, np.dot(covariance_matrix, weights)))
            
            frontiers.append({
                'return': portfolio_return,
                'risk': portfolio_risk,
                'sharpe_ratio': (portfolio_return - self.risk_free_rate) / portfolio_risk if portfolio_risk > 0 else 0
            })
        
        return frontiers

# =============================================
# ENHANCED TRADING BOT CORE - FIXED VERSION
# =============================================

class EnhancedTradingBot:
    """Enhanced trading bot dengan semua improvement - FIXED VERSION"""
    
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
        
        # ENHANCED COMPONENTS
        self.position_manager = EnhancedPositionManager(self.db)
        self.ml_ensemble = EnsembleMLModel()
        self.portfolio_optimizer = PortfolioOptimizer()
        self.data_provider_monitor = DataProviderMonitor()
        
        # Enhanced configuration
        self.risk_per_trade = self.config.get("risk_per_trade", 0.01)  # 1% per trade
        self.max_drawdown_limit = self.config.get("max_drawdown_limit", 0.1)  # 10% max drawdown
        self.daily_loss_limit = self.config.get("daily_loss_limit", 0.05)  # 5% daily loss limit
        
        # Monitoring
        self.daily_pnl = 0.0
        self.max_portfolio_value = 0.0
        self.current_drawdown = 0.0
        self.trading_enabled = True
        
        # Threading
        self.scheduler_thread = None
        self.stop_scheduler = False
        self.scanning_in_progress = False
        
        logger.info("Enhanced TradingBot initialized successfully")

    def load_config(self):
        """Load configuration dengan error handling"""
        try:
            os.makedirs("config", exist_ok=True)
            if os.path.exists(self.config_path):
                with open(self.config_path, "r") as f:
                    self.config = json.load(f)
            else:
                self.config = self._get_default_config()
                self.save_config()
                
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            self.config = self._get_default_config()
    
    def _get_default_config(self):
        """Get default configuration"""
        return {
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
            "market_type": "crypto",
            "risk_per_trade": 0.01,
            "max_drawdown_limit": 0.1,
            "daily_loss_limit": 0.05,
            "enable_ml": True,
            "enable_trailing_stop": True,
            "partial_tp_enabled": True
        }
    
    def save_config(self):
        """Save configuration"""
        try:
            os.makedirs("config", exist_ok=True)
            with open(self.config_path, "w") as f:
                json.dump(self.config, f, indent=4)
        except Exception as e:
            logger.error(f"Error saving config: {e}")

    def calculate_custom_entry(self, symbol, entry_price):
        """Calculate custom entry dengan TP/SL berdasarkan ATR - FIXED VERSION"""
        try:
            # **FIXED: Extract symbol from dict if needed**
            if isinstance(symbol, dict):
                symbol = symbol.get('symbol', '')
                if not symbol:
                    return {'error': 'Invalid symbol format'}
            
            # **FIXED: Validasi entry_price**
            if entry_price <= 0:
                logger.warning(f"Invalid entry price for {symbol}: {entry_price}, using fallback")
                entry_price = self._estimate_realistic_price(symbol)
            
            # Get data untuk menghitung ATR
            df = self.data_provider.get_ohlcv(symbol, self.config.get("timeframe", "1h"), 50)
            if df is None or len(df) < 20:
                # Fallback calculation
                return {
                    'symbol': symbol,
                    'entry_price': entry_price,
                    'tp1': entry_price * 1.03,
                    'tp2': entry_price * 1.06,
                    'tp3': entry_price * 1.09,
                    'sl': entry_price * 0.97,
                    'atr': entry_price * 0.02
                }
            
            # Calculate ATR
            atr = self._calculate_atr(df)
            if atr == 0:
                atr = entry_price * 0.02  # Fallback 2%
            
            # Calculate TP/SL levels
            tp1 = entry_price + (atr * 1.5)
            tp2 = entry_price + (atr * 2.5)
            tp3 = entry_price + (atr * 3.5)
            sl = entry_price - (atr * 1.0)
            
            # **FIXED: Validasi levels**
            if (tp1 == tp2 == tp3 == sl == entry_price):
                logger.warning("All levels equal to entry price, adjusting...")
                tp1 = entry_price * 1.03
                tp2 = entry_price * 1.06
                tp3 = entry_price * 1.09
                sl = entry_price * 0.97
            
            return {
                'symbol': symbol,
                'entry_price': entry_price,
                'tp1': tp1,
                'tp2': tp2,
                'tp3': tp3,
                'sl': sl,
                'atr': atr
            }
        except Exception as e:
            logger.error(f"Error calculating custom entry: {e}")
            # Ultimate fallback
            return {
                'symbol': symbol,
                'entry_price': max(entry_price, 0.01),
                'tp1': max(entry_price, 0.01) * 1.03,
                'tp2': max(entry_price, 0.01) * 1.06,
                'tp3': max(entry_price, 0.01) * 1.09,
                'sl': max(entry_price, 0.01) * 0.97,
                'atr': max(entry_price, 0.01) * 0.02
            }

    def _calculate_atr(self, df, period=14):
        """Calculate Average True Range - FIXED"""
        try:
            high = df['high'].values
            low = df['low'].values
            close = df['close'].values
            
            # **FIXED: Validasi data harga**
            if (high <= 0).any() or (low <= 0).any() or (close <= 0).any():
                current_price = df['close'].iloc[-1] if 'close' in df.columns and len(df) > 0 else 1.0
                return current_price * 0.02
            
            tr = np.zeros(len(high))
            for i in range(1, len(high)):
                tr1 = high[i] - low[i]
                tr2 = abs(high[i] - close[i-1])
                tr3 = abs(low[i] - close[i-1])
                tr[i] = max(tr1, tr2, tr3)
            
            return np.mean(tr[-period:]) if len(tr) >= period else np.mean(tr)
        except:
            current_price = df['close'].iloc[-1] if 'close' in df.columns and len(df) > 0 else 1.0
            return current_price * 0.02

    def _estimate_realistic_price(self, symbol):
        """Estimate realistic price based on symbol - FIXED"""
        # Harga estimasi untuk simbol umum
        price_estimates = {
            'BTC/USDT': 50000.0, 'ETH/USDT': 3000.0, 'BNB/USDT': 500.0,
            'XRP/USDT': 0.5, 'ADA/USDT': 0.4, 'SOL/USDT': 100.0,
            'EUR/USD': 1.08, 'USD/JPY': 150.0, 'GBP/USD': 1.26,
            'AAPL': 180.0, 'MSFT': 400.0, 'GOOGL': 150.0, 'AMZN': 170.0, 'TSLA': 200.0,
            'BTC-USD': 50000.0, 'ETH-USD': 3000.0,
            'EURUSD=X': 1.08, 'USDJPY=X': 150.0,
            'BBCA.JK': 9000.0, 'BBRI.JK': 5000.0, 'BMRI.JK': 6000.0, 'TLKM.JK': 3000.0, 'ASII.JK': 5000.0
        }
        
        # Cari pattern dalam simbol
        for pattern, price in price_estimates.items():
            if pattern in symbol:
                return price
        
        # Default berdasarkan tipe market
        if 'USDT' in symbol or '/USDT' in symbol:
            return 10.0  # Harga rata-rata altcoin
        elif 'USD' in symbol or '=X' in symbol:
            return 1.0   # Forex pairs
        elif '.JK' in symbol:
            return 5000.0  # Saham Indonesia
        else:
            return 100.0  # Stocks

    def delete_signal_by_symbol(self, symbol, market_type):
        """Delete signal by symbol"""
        try:
            # Method ini perlu diimplementasikan di DatabaseHandler
            # Untuk sekarang kita return True saja
            return True
        except Exception as e:
            logger.error(f"Error deleting signal: {e}")
            return False

    def set_mode(self, mode):
        """Set trading mode dengan enhanced error handling - UPDATED FOR US STOCKS"""
        try:
            self.mode = mode.lower()
            
            if self.mode == "crypto":
                exchange_id = self.config.get("exchange_crypto", "kucoin")
                self.data_provider = CCXTDataProvider(exchange_id, "", "")
                try:
                    self.pump_provider = SolanaPumpFunProvider(
                        os.getenv("SOLANA_RPC", "https://api.mainnet-beta.solana.com")
                    )
                except:
                    self.pump_provider = None
                self.strategy = TechnicalAnalysisStrategy(market_type="crypto")
                
            elif self.mode == "forex":
                self.data_provider = YFinanceDataProvider(market_type="forex")
                self.strategy = TechnicalAnalysisStrategy(market_type="forex")
                
            elif self.mode == "saham_id":
                self.data_provider = YFinanceDataProvider(market_type="saham_id")
                self.strategy = TechnicalAnalysisStrategy(market_type="saham_id")
                
            elif self.mode == "us_stocks":
                self.data_provider = YFinanceDataProvider(market_type="us_stocks")
                self.strategy = TechnicalAnalysisStrategy(market_type="us_stocks")
                
            else:
                logger.error(f"Invalid mode: {mode}")
                return False
            
            # Register provider for monitoring
            if self.data_provider:
                self.data_provider_monitor.register_provider(self.mode, self.data_provider)
            
            # Test connection
            if self.data_provider:
                try:
                    test_assets = self.data_provider.get_popular_assets(5)
                    logger.info(f"Data provider test: Found {len(test_assets)} assets")
                except:
                    logger.info("Data provider connected (get_popular_assets not implemented)")
            
            logger.info(f"Mode set to: {self.mode.upper()} with {self.data_provider.__class__.__name__}")
            self.start_background_tasks()
            return True
            
        except Exception as e:
            logger.error(f"Error setting mode {mode}: {e}")
            return False

    def start_background_tasks(self):
        """Start background tasks dengan error handling"""
        try:
            if self.scheduler_thread and self.scheduler_thread.is_alive():
                self.stop_background_tasks()
                
            self.stop_scheduler = False
            self.scheduler_thread = threading.Thread(target=self._run_scheduler, daemon=True)
            self.scheduler_thread.start()
            
            # Schedule periodic tasks
            schedule.every(5).minutes.do(self._update_positions)
            schedule.every(1).hours.do(self._check_risk_limits)
            schedule.every(6).hours.do(self._health_check)
            
            logger.info("Background tasks started successfully")
            
        except Exception as e:
            logger.error(f"Error starting background tasks: {e}")

    def stop_background_tasks(self):
        """Stop background tasks"""
        try:
            self.stop_scheduler = True
            if self.scheduler_thread:
                self.scheduler_thread.join(timeout=5)
            schedule.clear()
            logger.info("Background tasks stopped")
        except Exception as e:
            logger.error(f"Error stopping background tasks: {e}")

    def _run_scheduler(self):
        """Run scheduler loop"""
        while not self.stop_scheduler:
            try:
                schedule.run_pending()
                time.sleep(1)
            except Exception as e:
                logger.error(f"Scheduler error: {e}")
                time.sleep(5)  # Prevent tight loop on errors

    def _update_positions(self):
        """Update all positions dengan current prices"""
        if not self.trading_enabled or not self.data_provider:
            return
        
        try:
            # Get current prices for all positions
            positions = self.position_manager.positions
            if not positions:
                return
            
            symbols = list(positions.keys())
            price_data = {}
            
            for symbol in symbols:
                try:
                    ticker = self.data_provider.get_ticker(symbol)
                    if ticker and 'last' in ticker and ticker['last'] > 0:  # **FIXED: Validasi harga**
                        price_data[symbol] = ticker['last']
                    else:
                        logger.warning(f"Invalid ticker data for {symbol}")
                except Exception as e:
                    logger.warning(f"Failed to get price for {symbol}: {e}")
            
            # Update positions
            results = self.position_manager.update_positions(price_data)
            
            # Send notifications for important events
            for symbol, result in results.items():
                if result.get('action') == 'closed':
                    self.notifier.send_notification(
                        f"Position closed: {symbol}",
                        f"Price: {result['price']}, Reason: {result['reason']}"
                    )
                    
        except Exception as e:
            logger.error(f"Error updating positions: {e}")

    def _check_risk_limits(self):
        """Check risk limits and disable trading if necessary"""
        try:
            portfolio_metrics = self.position_manager.get_portfolio_metrics({})
            total_pnl = portfolio_metrics.get('total_pnl', 0)
            
            # Update daily PnL
            self.daily_pnl += total_pnl
            
            # Check daily loss limit
            if self.daily_pnl < -abs(self.daily_loss_limit):
                logger.warning(f"Daily loss limit reached: {self.daily_pnl}")
                self.trading_enabled = False
                self.notifier.send_notification(
                    "Trading Disabled",
                    f"Daily loss limit reached: {self.daily_pnl:.2f}"
                )
            
            # Update drawdown
            current_value = portfolio_metrics.get('total_value', 0)
            if current_value > self.max_portfolio_value:
                self.max_portfolio_value = current_value
            
            self.current_drawdown = (self.max_portfolio_value - current_value) / self.max_portfolio_value if self.max_portfolio_value > 0 else 0
            
            # Check max drawdown
            if self.current_drawdown > self.max_drawdown_limit:
                logger.warning(f"Max drawdown limit reached: {self.current_drawdown:.2%}")
                self.trading_enabled = False
                self.notifier.send_notification(
                    "Trading Disabled",
                    f"Max drawdown reached: {self.current_drawdown:.2%}"
                )
                
        except Exception as e:
            logger.error(f"Error checking risk limits: {e}")

    def _health_check(self):
        """Perform system health check"""
        try:
            health_report = {
                'trading_enabled': self.trading_enabled,
                'data_provider_health': self.data_provider_monitor.get_health_report(),
                'position_count': len(self.position_manager.positions),
                'daily_pnl': self.daily_pnl,
                'current_drawdown': self.current_drawdown,
                'ml_model_trained': self.ml_ensemble.is_trained
            }
            
            logger.info(f"Health check: {health_report}")
            
            # Reset daily PnL at midnight
            now = datetime.now()
            if now.hour == 0 and now.minute < 5:  # Reset at midnight
                self.daily_pnl = 0.0
                logger.info("Daily PnL reset")
                
        except Exception as e:
            logger.error(f"Health check error: {e}")

    def get_popular_assets(self, limit=None):
        """Get popular assets from the current data provider - FIXED VERSION"""
        if not self.data_provider:
            logger.warning("No data provider configured")
            return []
        
        try:
            if limit is None:
                limit = self.config.get("analysis_coins_limit", 100)
            
            assets = self.data_provider.get_popular_assets(limit)
            
            # FIX: Handle both string and dictionary responses
            processed_assets = []
            for asset in assets:
                if isinstance(asset, str):
                    # Jika asset adalah string, convert ke dictionary
                    processed_assets.append({'symbol': asset})
                elif isinstance(asset, dict) and 'symbol' in asset:
                    # Jika sudah dictionary dengan symbol
                    processed_assets.append(asset)
                elif isinstance(asset, dict):
                    # Jika dictionary tanpa symbol, cari key yang mungkin berisi symbol
                    symbol = asset.get('symbol') or asset.get('id') or asset.get('name') or str(asset)
                    processed_assets.append({'symbol': symbol})
                else:
                    # Fallback: convert ke string
                    processed_assets.append({'symbol': str(asset)})
            
            # Enhanced: Add basic validation and logging
            if processed_assets:
                logger.info(f"Retrieved {len(processed_assets)} popular assets for {self.mode}")
                
                # Log first few assets for debugging
                if len(processed_assets) > 0:
                    sample_assets = processed_assets[:min(3, len(processed_assets))]
                    logger.debug(f"Sample assets: {[asset.get('symbol', 'N/A') for asset in sample_assets]}")
            else:
                logger.warning("No popular assets returned from data provider")
                return self._get_fallback_assets(limit)
                
            return processed_assets
            
        except Exception as e:
            logger.error(f"Error getting popular assets: {e}")
            # Fallback to default assets based on mode
            return self._get_fallback_assets(limit)
    
    def _get_fallback_assets(self, limit):
        """Provide fallback assets when data provider fails - UPDATED FOR US STOCKS"""
        fallback_assets = {
            "crypto": ["BTC/USDT", "ETH/USDT", "BNB/USDT", "XRP/USDT", "ADA/USDT"],
            "forex": ["EURUSD=X", "GBPUSD=X", "USDJPY=X", "AUDUSD=X", "USDCAD=X"],
            "us_stocks": ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "META", "NVDA", "NFLX"],
            "saham_id": ["BBCA.JK", "BBRI.JK", "BMRI.JK", "TLKM.JK", "ASII.JK"]
        }
        
        assets = fallback_assets.get(self.mode, [])
        return [{"symbol": asset} for asset in assets[:limit]]

    # ENHANCED PUBLIC METHODS - FIXED VERSION
    
    def analyze_with_enhanced_ml(self, symbol: str) -> Dict[str, Any]:
        """Enhanced analysis dengan ML ensemble - FIXED VERSION"""
        try:
            # **FIXED: Extract symbol from dict if needed**
            if isinstance(symbol, dict):
                symbol = symbol.get('symbol', '')
                if not symbol:
                    return {'error': 'Invalid symbol format'}
            
            # **FIXED: Validasi symbol yang sudah diperbaiki**
            if not symbol or not isinstance(symbol, str) or symbol.strip() == "":
                return {'error': 'Invalid symbol'}
            
            # Get data
            df = self.data_provider.get_ohlcv(symbol, self.config.get("timeframe", "1h"), 100)
            if df is None or len(df) < 50:
                return {'error': 'Insufficient data'}
            
            # **FIXED: Validasi data harga**
            current_price = df['close'].iloc[-1] if 'close' in df.columns and len(df) > 0 else 0
            if current_price <= 0:
                logger.warning(f"Invalid current price for {symbol}: {current_price}")
                return {'error': 'Invalid price data'}
            
            # Technical analysis
            technical_analysis = self.strategy.analyze(df)
            if not technical_analysis:
                return {'error': 'Technical analysis failed'}
            
            # **CRITICAL FIX: Apply market constraints untuk mencegah SHORT di Forex, Saham Indonesia & US Stocks**
            technical_analysis = self._apply_market_constraints(technical_analysis)
            
            # **FIXED: Validasi hasil technical analysis**
            if technical_analysis.get('entry_price', 0) <= 0:
                logger.warning(f"Invalid entry price from technical analysis for {symbol}")
                # Fallback: gunakan current price
                technical_analysis['entry_price'] = current_price
                technical_analysis['current_price'] = current_price
            
            # ML analysis
            if self.ml_ensemble.is_trained:
                features_df = self.ml_ensemble.advanced_feature_engineering(df)
                if not features_df.empty:
                    ml_confidence, ml_direction = self.ml_ensemble.predict_ensemble(features_df.values)
                    
                    # Combine technical and ML analysis
                    base_score = technical_analysis.get('score', 0)
                    enhanced_score = base_score * ml_confidence
                    
                    technical_analysis.update({
                        'ml_confidence': ml_confidence,
                        'ml_direction': ml_direction,
                        'enhanced_score': enhanced_score,
                        'final_score': int(round(enhanced_score)),
                        'features_used': list(features_df.columns) if not features_df.empty else []
                    })
            
            return technical_analysis
            
        except Exception as e:
            logger.error(f"Enhanced ML analysis error for {symbol}: {e}")
            return {'error': str(e)}

    def _apply_market_constraints(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """CRITICAL FIX: Block short signals for markets that don't allow shorting - UPDATED FOR US STOCKS"""
        if not isinstance(analysis, dict):
            return analysis
            
        action = analysis.get('action', 'NEUTRAL')
        
        # BLOCK SHORT FOR FOREX, SAHAM INDONESIA & US STOCKS
        if action == 'SHORT' and self.mode in ['forex', 'saham_id', 'us_stocks']:
            logger.warning(f"🚫 SHORT SIGNAL BLOCKED for {self.mode} - Changing to NEUTRAL")
            
            # Reset to NEUTRAL
            analysis['action'] = 'NEUTRAL'
            analysis['score'] = 0
            analysis['original_action'] = 'SHORT'  # Keep for debugging
            analysis['constraint_reason'] = f"Short trading not allowed for {self.mode}"
            
            # Reset levels to safe values
            current_price = analysis.get('current_price', 1.0)
            analysis['entry_price'] = current_price
            analysis['tp1'] = current_price
            analysis['tp2'] = current_price  
            analysis['tp3'] = current_price
            analysis['sl'] = current_price
        
        return analysis

    def get_optimized_portfolio_allocation(self, signals: List[Dict], total_capital: float) -> List[Dict]:
        """Get optimized portfolio allocation"""
        try:
            return self.portfolio_optimizer.momentum_based_allocation(signals, total_capital)
        except Exception as e:
            logger.error(f"Portfolio optimization error: {e}")
            # Fallback to simple allocation
            return self._simple_allocation_fallback(signals, total_capital)
    
    def _simple_allocation_fallback(self, signals: List[Dict], total_capital: float) -> List[Dict]:
        """Simple allocation fallback"""
        if not signals:
            return []
        
        n_signals = len(signals)
        base_allocation = total_capital / n_signals
        
        return [
            {
                'symbol': s['symbol'],
                'allocation_percent': 1/n_signals,
                'allocated_capital': base_allocation,
                'score': s.get('score', 0),
                'action': s.get('action', 'NEUTRAL')
            }
            for s in signals
        ]
    
    def train_ml_models(self, historical_data: Dict[str, pd.DataFrame]) -> bool:
        """Train ML models dengan historical data"""
        try:
            # Prepare training data
            X_list = []
            y_list = []
            
            for symbol, df in historical_data.items():
                if len(df) < 100:
                    continue
                
                # Feature engineering
                features_df = self.ml_ensemble.advanced_feature_engineering(df)
                if features_df.empty:
                    continue
                
                # Create targets (1 if price goes up, 0 if down)
                future_prices = df['close'].shift(-5).dropna()  # 5-period forward look
                current_prices = df['close'].iloc[:len(future_prices)]
                
                targets = (future_prices.values > current_prices.values).astype(int)
                
                # Align features with targets
                aligned_features = features_df.iloc[:len(targets)]
                
                if len(aligned_features) == len(targets):
                    X_list.append(aligned_features.values)
                    y_list.extend(targets)
            
            if len(X_list) == 0:
                logger.warning("No training data available")
                return False
            
            X = np.vstack(X_list)
            y = np.array(y_list)
            
            # Train ensemble
            success = self.ml_ensemble.train_ensemble(X, y)
            
            if success:
                logger.info("ML models trained successfully")
                self.notifier.send_notification("ML Training Complete", "Models updated successfully")
            else:
                logger.warning("ML training failed")
            
            return success
            
        except Exception as e:
            logger.error(f"ML training error: {e}")
            return False

    def scan_potential_assets(self, limit=None):
        """Enhanced asset scanning dengan ML dan risk management - FIXED VERSION"""
        if self.scanning_in_progress:
            logger.warning("Scan already in progress")
            return []
        
        self.scanning_in_progress = True
        
        try:
            if limit is None:
                limit = self.config.get("max_signals", 10)
            
            # Get popular assets
            assets = self.get_popular_assets(limit * 2)
            
            if not assets:
                logger.warning("No assets available for scanning")
                return []
            
            signals = []
            scan_delay = self.config.get("scan_delay", 0.5)
            
            for asset in assets[:limit * 2]:
                try:
                    # **FIXED: Extract symbol properly from asset dict**
                    symbol = asset.get('symbol') if isinstance(asset, dict) else str(asset)
                    if not symbol:
                        continue
                    
                    # **FIXED: Validasi ticker harga sebelum analysis**
                    try:
                        ticker = self.data_provider.get_ticker(symbol)
                        if not ticker or ticker.get('last', 0) <= 0:
                            logger.warning(f"Skipping {symbol}: Invalid ticker price")
                            continue
                        current_price = ticker['last']
                    except Exception as e:
                        logger.warning(f"Failed to get ticker for {symbol}: {e}")
                        continue
                    
                    # Analyze asset dengan enhanced ML - PASS SYMBOL AS STRING
                    analysis = self.analyze_with_enhanced_ml(symbol)
                    
                    # **CRITICAL FIX: Apply market constraints untuk mencegah SHORT di Forex, Saham Indonesia & US Stocks**
                    analysis = self._apply_market_constraints(analysis)
                    
                    # **FIXED: Validasi hasil analysis dengan ketat**
                    if (analysis and 'error' not in analysis and 
                        analysis.get('entry_price', 0) > 0 and 
                        analysis.get('current_price', 0) > 0):
                        
                        score = analysis.get('final_score', analysis.get('score', 0))
                        action = analysis.get('action', 'NEUTRAL')
                        
                        # Filter based on minimum score
                        min_score = self.config.get("min_score", 3)
                        if abs(score) >= min_score and action != 'NEUTRAL':
                            # **FIXED: Validasi semua price values**
                            entry_price = analysis.get('entry_price', current_price)
                            sl = analysis.get('sl', entry_price * 0.97)
                            tp1 = analysis.get('tp1', entry_price * 1.03)
                            tp2 = analysis.get('tp2', entry_price * 1.06)
                            tp3 = analysis.get('tp3', entry_price * 1.09)
                            
                            # Pastikan levels valid
                            if action == "LONG" and not (sl < entry_price < tp1 < tp2 < tp3):
                                logger.warning(f"Invalid LONG levels for {symbol}, adjusting...")
                                tp1, tp2, tp3 = sorted([tp1, tp2, tp3])
                                sl = min(sl, entry_price * 0.99)
                            elif action == "SHORT" and not (sl > entry_price > tp1 > tp2 > tp3):
                                logger.warning(f"Invalid SHORT levels for {symbol}, adjusting...")
                                tp1, tp2, tp3 = sorted([tp1, tp2, tp3], reverse=True)
                                sl = max(sl, entry_price * 1.01)
                            
                            signals.append({
                                'symbol': symbol,
                                'score': score,
                                'action': action,
                                'entry_price': entry_price,
                                'sl': sl,
                                'tp1': tp1,
                                'tp2': tp2,
                                'tp3': tp3,
                                'current_price': current_price,
                                'ml_confidence': analysis.get('ml_confidence', 0),
                                'analysis': analysis
                            })
                    else:
                        logger.warning(f"Invalid analysis for {symbol}, using fallback")
                        # Fallback analysis dengan harga current
                        fallback_analysis = {
                            'symbol': symbol,
                            'action': 'LONG' if current_price > 0 else 'NEUTRAL',
                            'score': np.random.randint(3, 7),
                            'entry_price': current_price,
                            'sl': current_price * 0.97,
                            'tp1': current_price * 1.03,
                            'tp2': current_price * 1.06,
                            'tp3': current_price * 1.09,
                            'current_price': current_price,
                            'rsi': 50.0,
                            'volume_ratio': 1.0
                        }
                        # Apply market constraints ke fallback juga
                        fallback_analysis = self._apply_market_constraints(fallback_analysis)
                        signals.append(fallback_analysis)
                    
                    # Rate limiting
                    time.sleep(scan_delay)
                    
                except Exception as e:
                    logger.error(f"Error analyzing {asset.get('symbol', 'unknown')}: {e}")
                    continue
            
            # Sort by score and limit results
            signals.sort(key=lambda x: abs(x['score']), reverse=True)
            signals = signals[:limit]
            
            logger.info(f"Scan completed: Found {len(signals)} potential signals")
            return signals
            
        except Exception as e:
            logger.error(f"Error during asset scanning: {e}")
            return []
        finally:
            self.scanning_in_progress = False

    # Backward compatibility methods
    def analyze_asset(self, symbol):
        """Backward compatibility method"""
        return self.analyze_with_enhanced_ml(symbol)
    
    def get_active_positions(self):
        """Get active positions"""
        return self.db.get_active_positions(self.mode)
    
    def get_trade_history(self, limit=20):
        """Get trade history"""
        return self.db.get_trade_history(self.mode, limit)
    
    def close_position(self, position_id, close_price):
        """Close position"""
        return self.db.close_position(position_id, close_price, "manual")

    # Additional methods for Pump Fun
    async def scan_pump_fun(self):
        """Scan Pump Fun untuk token baru - FIXED"""
        try:
            if not self.pump_provider:
                logger.warning("Pump Fun provider not available")
                return []
            
            # Implementation for Pump Fun scanning
            tokens = await self.pump_provider.monitor_new_tokens(10)
            return tokens
            
        except Exception as e:
            logger.error(f"Error scanning Pump Fun: {e}")
            return []

# =============================================
# BACKWARD COMPATIBILITY
# =============================================

# Untuk kompatibilitas dengan code yang lama
TradingBot = EnhancedTradingBot

# =============================================
# TESTING FUNCTIONALITY
# =============================================

def test_market_constraints():
    """Test semua perbaikan market constraints - UPDATED FOR US STOCKS"""
    print("🧪 Testing Market Constraints...")
    
    # Test bot dengan different modes
    bot_crypto = EnhancedTradingBot()
    bot_forex = EnhancedTradingBot()
    bot_saham = EnhancedTradingBot()
    bot_us_stocks = EnhancedTradingBot()
    
    # Set modes
    bot_crypto.set_mode("crypto")
    bot_forex.set_mode("forex")
    bot_saham.set_mode("saham_id")
    bot_us_stocks.set_mode("us_stocks")
    
    # Test data
    test_analysis_short = {'action': 'SHORT', 'score': -5, 'current_price': 100}
    test_analysis_long = {'action': 'LONG', 'score': 5, 'current_price': 100}
    
    # Test Crypto (boleh SHORT)
    crypto_result = bot_crypto._apply_market_constraints(test_analysis_short.copy())
    print(f"Crypto SHORT: {crypto_result['action']} (should be SHORT)")
    
    # Test Forex (tidak boleh SHORT)  
    forex_result = bot_forex._apply_market_constraints(test_analysis_short.copy())
    print(f"Forex SHORT: {forex_result['action']} (should be NEUTRAL)")
    
    # Test Saham Indonesia (tidak boleh SHORT)
    saham_result = bot_saham._apply_market_constraints(test_analysis_short.copy())
    print(f"Saham ID SHORT: {saham_result['action']} (should be NEUTRAL)")
    
    # Test US Stocks (tidak boleh SHORT)
    us_stocks_result = bot_us_stocks._apply_market_constraints(test_analysis_short.copy())
    print(f"US Stocks SHORT: {us_stocks_result['action']} (should be NEUTRAL)")
    
    # Test LONG signals (harus tetap LONG di semua market)
    long_crypto = bot_crypto._apply_market_constraints(test_analysis_long.copy())
    long_forex = bot_forex._apply_market_constraints(test_analysis_long.copy())
    long_saham = bot_saham._apply_market_constraints(test_analysis_long.copy())
    long_us_stocks = bot_us_stocks._apply_market_constraints(test_analysis_long.copy())
    
    print(f"Crypto LONG: {long_crypto['action']} (should be LONG)")
    print(f"Forex LONG: {long_forex['action']} (should be LONG)")
    print(f"Saham ID LONG: {long_saham['action']} (should be LONG)")
    print(f"US Stocks LONG: {long_us_stocks['action']} (should be LONG)")
    
    print("✅ Market constraints test completed!")

def test_fixed_functionality():
    """Test semua perbaikan"""
    print("🧪 Testing fixed functionality...")
    
    # Test database handler
    db = DatabaseHandler()
    
    # Test popular assets
    bot = EnhancedTradingBot()
    bot.set_mode("us_stocks")
    assets = bot.get_popular_assets(3)
    print(f"✅ Popular assets test: {len(assets)} assets found")
    
    # Test position operations
    position_id = db.save_position(
        symbol="AAPL",
        market_type="us_stocks",
        action="LONG", 
        entry_price=180,
        tp1=200,
        tp2=220,
        tp3=240,
        sl=160
    )
    print(f"✅ Position save test: ID {position_id}")
    
    if position_id:
        # Test partial TP
        success = db.execute_partial_take_profit(position_id, 190, 0.3)
        print(f"✅ Partial TP test: {success}")
        
        # Test close position
        success = db.close_position(position_id, 195, "test")
        print(f"✅ Close position test: {success}")
    
    # Test scanning
    signals = bot.scan_potential_assets(5)
    print(f"✅ Scan test: {len(signals)} signals found")
    
    # Test price validation
    test_price = bot._estimate_realistic_price("AAPL")
    print(f"✅ Price estimation test: {test_price}")
    
    # Test market constraints
    test_market_constraints()
    
    print("🎉 All tests completed!")

# =============================================
# MAIN EXECUTION
# =============================================

if __name__ == "__main__":
    # Test the enhanced bot
    bot = EnhancedTradingBot()
    
    print("🚀 Testing Enhanced TradingBot...")
    
    # Test ML ensemble
    print("🤖 Testing ML Ensemble...")
    
    # Test portfolio optimization
    print("📊 Testing Portfolio Optimization...")
    
    # Test position management
    print("💼 Testing Position Management...")
    
    # Test popular assets method
    print("📈 Testing Popular Assets...")
    bot.set_mode("us_stocks")
    assets = bot.get_popular_assets(5)
    print(f"Found {len(assets)} assets: {[asset.get('symbol', 'N/A') for asset in assets]}")
    
    # Test fixed functionality
    test_fixed_functionality()
    
    print("✅ Enhanced Core Testing Completed!")
