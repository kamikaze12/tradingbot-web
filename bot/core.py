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
from sklearn.model_selection import train_test_split, TimeSeriesSplit
from sklearn.metrics import accuracy_score, precision_recall_fscore_support, classification_report
from sklearn.linear_model import LogisticRegression
from xgboost import XGBClassifier
import lightgbm as lgb
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
    from .strategies import TechnicalAnalysisStrategy
    from .data_provider import (
        CCXTDataProvider,
        YFinanceDataProvider,
        DataProviderMonitor,
        DynamicDataProvider
    )
    from .notifier import SoundNotifier
    from database.db_handler import DatabaseHandler
    
    # Handle optional imports
    try:
        from .data_provider import SolanaPumpFunProvider, DataProviderFactory
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
    
    class DynamicDataProvider:
        def __init__(self, *args, **kwargs): 
            self.market_type = kwargs.get('market_type', 'crypto')
        def get_ohlcv(self, *args, **kwargs): return pd.DataFrame()
        def get_ticker(self, *args, **kwargs): return {'last': 0}
        def get_popular_assets(self, *args, **kwargs): return []
        def search_assets(self, *args, **kwargs): return []
    
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
# ENHANCED BACKTEST ENGINE DARI CORE (1).PY
# =============================================

class BacktestEngine:
    """Enhanced backtesting engine dengan advanced features dari core (1).py"""
    
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
            
            logger.info(f"🔄 Running backtest on {len(df)} bars...")
            
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
            logger.error(f"Error in backtest: {e}")
            return self._get_empty_results()
    
    def run_walk_forward_analysis(self, df, strategy_class, periods=5, **kwargs):
        """Walk-forward analysis for strategy validation"""
        try:
            if len(df) < 200:
                return {"error": "Insufficient data for walk-forward analysis"}
            
            period_length = len(df) // periods
            results = []
            
            logger.info(f"🔍 Running walk-forward analysis with {periods} periods...")
            
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
                    
                    logger.info(f"  Period {i+1}: {period_result.get('total_trades', 0)} trades, Win Rate: {period_result.get('win_rate', 0):.1%}")
            
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
            logger.error(f"Error in walk-forward analysis: {e}")
            return {"error": str(e)}
    
    def run_parameter_optimization(self, df, strategy_class, param_grid, **kwargs):
        """Grid search for parameter optimization"""
        try:
            best_score = -float('inf')
            best_params = {}
            results = []
            
            logger.info("⚙️ Running parameter optimization...")
            
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
                        logger.info(f"  Completed {i+1}/{len(param_combinations)} combinations...")
                        
                except Exception as e:
                    logger.warning(f"  Skipping combination {params}: {e}")
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
            logger.error(f"Error in parameter optimization: {e}")
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
            
            logger.info(f"🎲 Running Monte Carlo simulation ({num_simulations} iterations)...")
            
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
            logger.error(f"Error in Monte Carlo simulation: {e}")
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
                self.models[model_type] = lgb.LGBMClassifier(
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
# ENHANCED ML BOT DARI CORE (1).PY
# =============================================

class MLEnhancedBot:
    """Machine Learning enhanced trading bot dengan model real dari core (1).py"""
    
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
                logger.info("✅ ML model loaded successfully")
                return True
        except Exception as e:
            logger.error(f"❌ Error loading model: {e}")
        
        # Initialize new model jika tidak ada
        self._initialize_model()
        return False

    def save_model(self):
        """Save model dan scaler"""
        try:
            if self.model and self.scaler:
                joblib.dump(self.model, self.model_path)
                joblib.dump(self.scaler, self.scaler_path)
                logger.info("✅ ML model saved successfully")
                return True
        except Exception as e:
            logger.error(f"❌ Error saving model: {e}")
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
        logger.info("🔄 New ML model initialized")

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
            logger.error(f"❌ Error preparing training data: {e}")
            return None, None

    def train_model(self, historical_data, test_size=0.2):
        """Train model dengan historical data"""
        try:
            logger.info("🔄 Preparing training data...")
            X, y = self.prepare_training_data(historical_data)
            
            if X is None or len(X) < 100:
                logger.error("❌ Insufficient training data")
                return False
            
            logger.info(f"📊 Training data shape: {X.shape}, targets: {y.shape}")
            
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
            
            logger.info(f"✅ Model training completed! Average Accuracy: {avg_accuracy:.3f}")
            logger.info(f"📈 Feature Importance: {self.feature_importance}")
            
            # Save model
            self.save_model()
            return True
            
        except Exception as e:
            logger.error(f"❌ Error training model: {e}")
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
            logger.error(f"❌ Error extracting features: {e}")
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
            logger.error(f"❌ Error in extract_features: {e}")
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
            logger.error(f"❌ Error in ML prediction: {e}")
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
            logger.error(f"❌ Error in batch prediction: {e}")
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

# =============================================
# ENHANCED TRADING BOT CORE - FINAL VERSION
# =============================================

class EnhancedTradingBot:
    """Enhanced trading bot dengan semua improvement dan fitur dari kedua versi"""
    
    def __init__(self, config_path="config/config.json"):
        self.config_path = config_path
        self.load_config()
        self.mode = None
        self.data_provider = None
        self.dynamic_provider = None
        self.pump_provider = None
        self.strategy = TechnicalAnalysisStrategy(
            market_type=self.config.get("market_type", "crypto"),
            atr_multiplier=self.config.get("atr_multiplier", 1.0),
            entry_range_pct=self.config.get("entry_range_pct", 0.02),
        )
        self.notifier = SoundNotifier()
        self.db = DatabaseHandler()
        
        # ENHANCED COMPONENTS DARI KEDUA VERSI
        self.position_manager = EnhancedPositionManager(self.db)
        self.ml_ensemble = EnsembleMLModel()
        self.ml_bot = MLEnhancedBot()  # Dari core (1).py
        self.portfolio_optimizer = PortfolioOptimizer()
        self.backtest_engine = BacktestEngine()  # Dari core (1).py
        self.data_provider_monitor = DataProviderMonitor()
        
        # Enhanced configuration
        self.risk_per_trade = self.config.get("risk_per_trade", 0.01)
        self.max_drawdown_limit = self.config.get("max_drawdown_limit", 0.1)
        self.daily_loss_limit = self.config.get("daily_loss_limit", 0.05)
        
        # Monitoring
        self.daily_pnl = 0.0
        self.max_portfolio_value = 0.0
        self.current_drawdown = 0.0
        self.trading_enabled = True
        
        # Threading
        self.scheduler_thread = None
        self.stop_scheduler = False
        self.scanning_in_progress = False
        
        # ML enhancements
        self.ml_predictions_cache = {}
        self.last_ml_update = 0
        
        logger.info("Enhanced TradingBot initialized successfully dengan semua fitur")

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

    def set_mode(self, mode):
        """Set trading mode dengan dynamic data provider"""
        try:
            self.mode = mode.lower()
            
            # GUNAKAN DYNAMIC DATA PROVIDER UNTUK SEMUA MARKET TYPE
            self.dynamic_provider = DynamicDataProvider(market_type=self.mode)
            self.data_provider = self.dynamic_provider  # Untuk kompatibilitas
            
            # Strategy tetap sama - akan auto-handle future/spot
            self.strategy = TechnicalAnalysisStrategy(
                market_type=self.mode,
                atr_multiplier=self.config.get("atr_multiplier", 1.0),
                entry_range_pct=self.config.get("entry_range_pct", 0.02),
            )
            
            # Untuk crypto, setup pump provider jika diperlukan
            if self.mode == "crypto":
                try:
                    self.pump_provider = SolanaPumpFunProvider(
                        os.getenv("SOLANA_RPC", "https://api.mainnet-beta.solana.com")
                    )
                except:
                    self.pump_provider = None
            
            # Register provider for monitoring
            if self.data_provider:
                self.data_provider_monitor.register_provider(self.mode, self.data_provider)
            
            logger.info(f"🎯 Mode set to: {self.mode.upper()} with DynamicDataProvider")
            self.start_background_tasks()
            return True
            
        except Exception as e:
            logger.error(f"Error setting mode {mode}: {e}")
            return False

    def search_assets(self, query: str, limit: int = 20) -> List[Dict]:
        """Search assets dynamically menggunakan dynamic provider"""
        if not self.dynamic_provider:
            logger.warning("Dynamic provider not initialized")
            return []
        
        try:
            logger.info(f"🔍 Searching assets for: '{query}' in {self.mode}")
            results = self.dynamic_provider.search_assets(query, limit)
            logger.info(f"✅ Found {len(results)} assets for query '{query}'")
            return results
        except Exception as e:
            logger.error(f"Error searching assets: {e}")
            return []

    def get_popular_assets(self, limit=None):
        """Get popular assets menggunakan dynamic provider - IMPROVED"""
        if not self.dynamic_provider:
            logger.warning("No dynamic provider configured")
            return self._get_fallback_assets(limit)
        
        try:
            if limit is None:
                limit = self.config.get("analysis_coins_limit", 100)
            
            logger.info(f"🔄 Fetching {limit} popular assets for {self.mode}...")
            
            assets = self.dynamic_provider.get_popular_assets(limit)
            
            if assets:
                logger.info(f"✅ Dynamic provider returned {len(assets)} assets for {self.mode}")
                
                # Log sample assets
                sample_count = min(5, len(assets))
                sample_symbols = [asset.get('symbol', 'N/A') for asset in assets[:sample_count]]
                logger.info(f"📋 Sample assets: {sample_symbols}")
                
                return assets
            else:
                logger.warning(f"❌ Dynamic provider returned no assets for {self.mode}")
                return self._get_fallback_assets(limit)
                
        except Exception as e:
            logger.error(f"❌ Error getting popular assets: {e}")
            return self._get_fallback_assets(limit)

    def _get_fallback_assets(self, limit):
        """Provide fallback assets ketika provider gagal"""
        fallback_assets = {
            "crypto": [
                {"symbol": "BTC/USDT", "name": "Bitcoin"},
                {"symbol": "ETH/USDT", "name": "Ethereum"}, 
                {"symbol": "BNB/USDT", "name": "Binance Coin"},
                {"symbol": "XRP/USDT", "name": "Ripple"},
                {"symbol": "ADA/USDT", "name": "Cardano"}
            ],
            "forex": [
                {"symbol": "EUR/USD", "name": "Euro US Dollar"},
                {"symbol": "USD/JPY", "name": "US Dollar Japanese Yen"},
                {"symbol": "GBP/USD", "name": "British Pound US Dollar"},
                {"symbol": "USD/CHF", "name": "US Dollar Swiss Franc"},
                {"symbol": "AUD/USD", "name": "Australian Dollar US Dollar"}
            ],
            "us_stocks": [
                {"symbol": "AAPL", "name": "Apple Inc"},
                {"symbol": "MSFT", "name": "Microsoft Corp"},
                {"symbol": "GOOGL", "name": "Alphabet Inc"},
                {"symbol": "AMZN", "name": "Amazon.com Inc"},
                {"symbol": "TSLA", "name": "Tesla Inc"}
            ],
            "saham_id": [
                {"symbol": "BBCA.JK", "name": "Bank Central Asia"},
                {"symbol": "BBRI.JK", "name": "Bank Rakyat Indonesia"},
                {"symbol": "BMRI.JK", "name": "Bank Mandiri"},
                {"symbol": "TLKM.JK", "name": "Telkom Indonesia"},
                {"symbol": "ASII.JK", "name": "Astra International"}
            ]
        }
        
        assets = fallback_assets.get(self.mode, [])
        limited_assets = assets[:limit] if limit else assets
        
        logger.info(f"🔄 Using {len(limited_assets)} fallback assets for {self.mode}")
        return [{"symbol": asset} for asset in limited_assets]

    def scan_potential_assets(self, limit=None, search_query: str = None):
        """Enhanced asset scanning dengan support untuk dynamic search"""
        if self.scanning_in_progress:
            logger.warning("Scan already in progress")
            return []
        
        self.scanning_in_progress = True
        
        try:
            if limit is None:
                limit = self.config.get("max_signals", 10)
            
            assets = []
            
            # JIKA ADA SEARCH QUERY, GUNAKAN DYNAMIC SEARCH
            if search_query:
                logger.info(f"🔍 Searching assets for: '{search_query}'")
                assets = self.search_assets(search_query, limit * 2)
            else:
                # GUNAKAN DYNAMIC PROVIDER UNTUK POPULAR ASSETS
                assets = self.dynamic_provider.get_popular_assets(limit * 2)
            
            logger.info(f"📊 Total assets to scan: {len(assets)}")
            
            if not assets:
                logger.warning("No assets available for scanning")
                return []
            
            signals = []
            scan_delay = self.config.get("scan_delay", 0.5)
            
            for i, asset in enumerate(assets):
                try:
                    symbol = asset.get('symbol') if isinstance(asset, dict) else str(asset)
                    asset_name = asset.get('name', symbol)
                    
                    if not symbol:
                        continue
                    
                    logger.info(f"🔎 Scanning {i+1}/{len(assets)}: {symbol} ({asset_name})")
                    
                    # Get current price menggunakan dynamic provider
                    try:
                        ticker = self.dynamic_provider.get_ticker(symbol)
                        if not ticker or ticker.get('last', 0) <= 0:
                            logger.warning(f"💰 Invalid price for {symbol}, skipping...")
                            continue
                        current_price = ticker['last']
                    except Exception as e:
                        logger.warning(f"💰 Failed to get price for {symbol}: {e}")
                        continue
                    
                    # Analyze asset - strategy akan auto-handle future/spot
                    analysis = self.analyze_with_enhanced_ml(symbol)
                    
                    # Apply market constraints
                    analysis = self._apply_market_constraints(analysis)
                    
                    # Validasi analysis
                    if (analysis and 'error' not in analysis and 
                        analysis.get('entry_price', 0) > 0 and 
                        analysis.get('current_price', 0) > 0):
                        
                        score = analysis.get('final_score', analysis.get('score', 0))
                        action = analysis.get('action', 'NEUTRAL')
                        
                        # Relaxed filter untuk lebih banyak signals
                        min_score = 1  # Reduced threshold
                        if abs(score) >= min_score and action != 'NEUTRAL':
                            
                            # Validasi dan adjust levels
                            entry_price = analysis.get('entry_price', current_price)
                            sl = analysis.get('sl', entry_price * 0.97)
                            tp1 = analysis.get('tp1', entry_price * 1.03)
                            tp2 = analysis.get('tp2', entry_price * 1.06) 
                            tp3 = analysis.get('tp3', entry_price * 1.09)
                            
                            # Ensure valid levels
                            if action == "LONG" and not (sl < entry_price < tp1 < tp2 < tp3):
                                logger.warning(f"🔄 Adjusting invalid LONG levels for {symbol}")
                                tp1, tp2, tp3 = sorted([tp1, tp2, tp3])
                                sl = min(sl, entry_price * 0.99)
                            elif action == "SHORT" and not (sl > entry_price > tp1 > tp2 > tp3):
                                logger.warning(f"🔄 Adjusting invalid SHORT levels for {symbol}")
                                tp1, tp2, tp3 = sorted([tp1, tp2, tp3], reverse=True)
                                sl = max(sl, entry_price * 1.01)
                            
                            signal_data = {
                                'symbol': symbol,
                                'name': asset_name,
                                'score': score,
                                'action': action,
                                'entry_price': entry_price,
                                'sl': sl,
                                'tp1': tp1,
                                'tp2': tp2,
                                'tp3': tp3,
                                'current_price': current_price,
                                'ml_confidence': analysis.get('ml_confidence', 0),
                                'rsi': analysis.get('rsi', 50),
                                'volume_ratio': analysis.get('volume_ratio', 1.0),
                                'market_regime': analysis.get('market_regime', 'unknown'),
                                'market_type': self.mode
                            }
                            
                            signals.append(signal_data)
                            logger.info(f"✅ Signal: {symbol} | {action} | Score: {score}")
                    
                    # Rate limiting
                    time.sleep(scan_delay)
                    
                except Exception as e:
                    logger.error(f"❌ Error analyzing {asset.get('symbol', 'unknown')}: {e}")
                    continue
            
            # Sort by absolute score dan limit results
            signals.sort(key=lambda x: abs(x['score']), reverse=True)
            final_signals = signals[:limit]
            
            logger.info(f"🎯 Scan completed: {len(final_signals)} signals found")
            
            if final_signals:
                logger.info("🏆 Top signals:")
                for i, signal in enumerate(final_signals[:5]):
                    logger.info(f"  {i+1}. {signal['symbol']} | {signal['action']} | Score: {signal['score']}")
            
            return final_signals
            
        except Exception as e:
            logger.error(f"💥 Error during asset scanning: {e}")
            return []
        finally:
            self.scanning_in_progress = False

    def analyze_with_enhanced_ml(self, symbol: str) -> Dict[str, Any]:
        """Enhanced analysis dengan ML ensemble"""
        try:
            # Extract symbol from dict if needed
            if isinstance(symbol, dict):
                symbol = symbol.get('symbol', '')
                if not symbol:
                    return {'error': 'Invalid symbol format'}
            
            # Validasi symbol yang sudah diperbaiki
            if not symbol or not isinstance(symbol, str) or symbol.strip() == "":
                return {'error': 'Invalid symbol'}
            
            # Get data menggunakan dynamic provider
            df = self.dynamic_provider.get_ohlcv(symbol, self.config.get("timeframe", "1h"), 100)
            if df is None or len(df) < 50:
                return {'error': 'Insufficient data'}
            
            # Validasi data harga
            current_price = df['close'].iloc[-1] if 'close' in df.columns and len(df) > 0 else 0
            if current_price <= 0:
                logger.warning(f"Invalid current price for {symbol}: {current_price}")
                return {'error': 'Invalid price data'}
            
            # Technical analysis
            technical_analysis = self.strategy.analyze(df, symbol)
            if not technical_analysis:
                return {'error': 'Technical analysis failed'}
            
            # CRITICAL FIX: Apply market constraints untuk mencegah SHORT di Forex, Saham Indonesia & US Stocks
            technical_analysis = self._apply_market_constraints(technical_analysis)
            
            # Validasi hasil technical analysis
            if technical_analysis.get('entry_price', 0) <= 0:
                logger.warning(f"Invalid entry price from technical analysis for {symbol}")
                # Fallback: gunakan current price
                technical_analysis['entry_price'] = current_price
                technical_analysis['current_price'] = current_price
            
            # ML analysis dengan kedua sistem ML
            ml_enhancements = {}
            
            # ML Ensemble (Enhanced)
            if self.ml_ensemble.is_trained:
                features_df = self.ml_ensemble.advanced_feature_engineering(df)
                if not features_df.empty:
                    ml_confidence, ml_direction = self.ml_ensemble.predict_ensemble(features_df.values)
                    
                    ml_enhancements.update({
                        'ml_ensemble_confidence': ml_confidence,
                        'ml_ensemble_direction': ml_direction,
                        'features_used': list(features_df.columns) if not features_df.empty else []
                    })
            
            # ML Bot (Traditional dari core (1).py)
            if self.ml_bot.is_trained:
                ml_confidence, ml_direction = self.ml_bot.predict(df)
                ml_enhancements.update({
                    'ml_bot_confidence': ml_confidence,
                    'ml_bot_direction': ml_direction
                })
            
            # Combine semua ML results
            if ml_enhancements:
                base_score = technical_analysis.get('score', 0)
                
                # Average confidence dari kedua sistem ML
                confidences = [v for k, v in ml_enhancements.items() if 'confidence' in k and v > 0]
                avg_ml_confidence = np.mean(confidences) if confidences else 0.5
                
                # Score boost berdasarkan ML confidence
                ml_score_boost = 0
                if avg_ml_confidence > 0.7:  # High confidence
                    ml_score_boost = 2.0
                elif avg_ml_confidence > 0.6:  # Medium confidence
                    ml_score_boost = 1.0
                
                final_score = base_score + ml_score_boost
                final_score = max(min(final_score, 10), -10)  # Clamp score
                
                technical_analysis.update(ml_enhancements)
                technical_analysis.update({
                    'final_score': final_score,
                    'ml_score_boost': ml_score_boost
                })
                
                # Update action berdasarkan final score
                if final_score >= 3:
                    technical_analysis['action'] = 'LONG'
                elif final_score <= -3:
                    technical_analysis['action'] = 'SHORT'
                else:
                    technical_analysis['action'] = 'NEUTRAL'
            
            return technical_analysis
            
        except Exception as e:
            logger.error(f"Enhanced ML analysis error for {symbol}: {e}")
            return {'error': str(e)}

    def _apply_market_constraints(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """CRITICAL FIX: Block short signals for markets that don't allow shorting"""
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

    # =============================================
    # ADVANCED BACKTEST METHODS DARI CORE (1).PY
    # =============================================

    def run_advanced_backtest(self, symbol, timeframe=None, limit=500):
        """Run advanced backtest dengan semua fitur baru"""
        if not self.dynamic_provider:
            return {"error": "No data provider available"}
            
        try:
            if timeframe is None:
                timeframe = self.config.get("timeframe", "1h")
                
            logger.info(f"🔧 Running advanced backtest for {symbol}...")
            df = self.dynamic_provider.get_ohlcv(symbol, timeframe, limit)
            
            if df is None or len(df) < 100:
                return {"error": "Insufficient data for backtest"}
            
            # Run basic backtest
            basic_result = self.backtest_engine.run_backtest(df, self.strategy)
            
            # Run Monte Carlo simulation if we have trades
            mc_result = {}
            if basic_result.get('total_trades', 0) > 10:
                # Get trades from basic backtest for Monte Carlo
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
            logger.error(f"Error in advanced backtest: {e}")
            return {"error": str(e)}

    def run_walk_forward_analysis(self, symbol, periods=5):
        """Run walk-forward analysis untuk validasi strategy"""
        if not self.dynamic_provider:
            return {"error": "No data provider available"}
            
        try:
            logger.info(f"📊 Running walk-forward analysis for {symbol}...")
            df = self.dynamic_provider.get_ohlcv(symbol, self.config.get("timeframe", "1h"), 1000)
            
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
            logger.error(f"Error in walk-forward analysis: {e}")
            return {"error": str(e)}

    def optimize_strategy_parameters(self, symbol, param_grid=None):
        """Optimize strategy parameters menggunakan grid search"""
        if not self.dynamic_provider:
            return {"error": "No data provider available"}
            
        try:
            if param_grid is None:
                param_grid = {
                    'atr_multiplier': [0.5, 1.0, 1.5, 2.0],
                    'entry_range_pct': [0.01, 0.02, 0.03, 0.05],
                    'market_type': [self.mode]
                }
                
            logger.info(f"⚙️ Optimizing parameters for {symbol}...")
            df = self.dynamic_provider.get_ohlcv(symbol, self.config.get("timeframe", "1h"), 500)
            
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
            logger.error(f"Error in parameter optimization: {e}")
            return {"error": str(e)}

    def run_comprehensive_backtest(self, symbol, days=180):
        """Run comprehensive backtest dengan multiple timeframes"""
        try:
            logger.info(f"📊 Running comprehensive backtest for {symbol} over {days} days...")
            
            # Get data for different timeframes
            timeframes = ['1h', '4h', '1d']
            results = {}
            
            for tf in timeframes:
                df = self.dynamic_provider.get_ohlcv(symbol, tf, days * 24)  # Estimate bars needed
                if df is None and len(df) > 100:
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
            logger.error(f"Error in comprehensive backtest: {e}")
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

    # =============================================
    # ML TRAINING METHODS DARI CORE (1).PY
    # =============================================

    def train_ml_model(self, training_symbols=None, days=365):
        """Train ML model dengan data historis - dari core (1).py"""
        try:
            if training_symbols is None:
                training_symbols = self.get_popular_assets(50)
            
            historical_data = {}
            
            logger.info(f"📊 Collecting historical data for {len(training_symbols)} symbols...")
            
            for symbol in training_symbols:
                try:
                    # Get data 1 tahun kebelakang
                    df = self.dynamic_provider.get_ohlcv(symbol, '1d', days)
                    if df is not None and len(df) > 100:
                        historical_data[symbol] = df
                        logger.info(f"  ✅ Collected data for {symbol}: {len(df)} bars")
                    else:
                        logger.info(f"  ⚠️ Insufficient data for {symbol}")
                except Exception as e:
                    logger.warning(f"  ❌ Error getting data for {symbol}: {e}")
            
            if len(historical_data) < 10:
                logger.error("❌ Not enough historical data for training")
                return False
            
            logger.info(f"🔄 Training ML model with {len(historical_data)} symbols...")
            success = self.ml_bot.train_model(historical_data)
            
            if success:
                logger.info("✅ ML model training completed successfully!")
            else:
                logger.error("❌ ML model training failed")
            
            return success
            
        except Exception as e:
            logger.error(f"❌ Error in ML model training: {e}")
            return False

    def update_ml_predictions(self, symbols_data):
        """Update ML predictions untuk multiple symbols sekaligus - dari core (1).py"""
        try:
            # Cache predictions untuk 5 menit
            current_time = time.time()
            if current_time - self.last_ml_update < 300:  # 5 menit
                return self.ml_predictions_cache
            
            logger.info("🔄 Updating ML predictions...")
            predictions = self.ml_bot.batch_predict(symbols_data)
            
            self.ml_predictions_cache = predictions
            self.last_ml_update = current_time
            
            logger.info(f"✅ ML predictions updated for {len(predictions)} symbols")
            return predictions
            
        except Exception as e:
            logger.error(f"❌ Error updating ML predictions: {e}")
            return {}

    # =============================================
    # PORTFOLIO OPTIMIZATION METHODS
    # =============================================

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

    # =============================================
    # BACKGROUND TASKS DAN UTILITY METHODS
    # =============================================

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
                time.sleep(5)

    def _update_positions(self):
        """Update all positions dengan current prices"""
        if not self.trading_enabled or not self.dynamic_provider:
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
                    ticker = self.dynamic_provider.get_ticker(symbol)
                    if ticker and 'last' in ticker and ticker['last'] > 0:
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

    # =============================================
    # BACKWARD COMPATIBILITY METHODS
    # =============================================

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

    def calculate_custom_entry(self, symbol, entry_price, action="LONG"):
        """Calculate custom entry dengan TP/SL - compatibility method"""
        try:
            # Implementation dari core (1).py dengan penyesuaian
            df = self.dynamic_provider.get_ohlcv(symbol, self.config.get("timeframe", "1h"), 50)
            
            if df is None or len(df) < 20:
                # Fallback calculation
                return {
                    'symbol': symbol,
                    'entry_price': entry_price,
                    'tp1': entry_price * 1.03,
                    'tp2': entry_price * 1.06,
                    'tp3': entry_price * 1.09,
                    'sl': entry_price * 0.97
                }
            
            # Calculate menggunakan strategy
            analysis = self.strategy.analyze(df)
            if analysis and 'tp1' in analysis and 'sl' in analysis:
                return {
                    'symbol': symbol,
                    'entry_price': entry_price,
                    'tp1': analysis['tp1'],
                    'tp2': analysis['tp2'],
                    'tp3': analysis['tp3'],
                    'sl': analysis['sl']
                }
            else:
                # Fallback
                return {
                    'symbol': symbol,
                    'entry_price': entry_price,
                    'tp1': entry_price * 1.03,
                    'tp2': entry_price * 1.06,
                    'tp3': entry_price * 1.09,
                    'sl': entry_price * 0.97
                }
                
        except Exception as e:
            logger.error(f"Error in custom entry calculation: {e}")
            return {
                'symbol': symbol,
                'entry_price': entry_price,
                'tp1': entry_price * 1.03,
                'tp2': entry_price * 1.06,
                'tp3': entry_price * 1.09,
                'sl': entry_price * 0.97
            }

    # Additional methods untuk Pump Fun
    async def scan_pump_fun(self):
        """Scan Pump Fun untuk token baru"""
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

    def delete_signal_by_symbol(self, symbol, market_type):
        """Delete signal by symbol"""
        try:
            # Method ini perlu diimplementasikan di DatabaseHandler
            return True
        except Exception as e:
            logger.error(f"Error deleting signal: {e}")
            return False

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
            logger.error(f"Error in risk assessment: {e}")
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

# =============================================
# BACKWARD COMPATIBILITY
# =============================================

# Untuk kompatibilitas dengan code yang lama
TradingBot = EnhancedTradingBot

# =============================================
# TESTING FUNCTIONALITY
# =============================================

def test_enhanced_functionality():
    """Test semua functionality enhanced core"""
    print("🧪 Testing Enhanced TradingBot dengan Semua Fitur...")
    
    bot = EnhancedTradingBot()
    
    # Test semua market type
    markets = ["crypto", "forex", "saham_id", "us_stocks"]
    
    for market in markets:
        print(f"\n{'='*50}")
        print(f"Testing {market.upper()} Market")
        print(f"{'='*50}")
        
        # Set mode
        success = bot.set_mode(market)
        if not success:
            print(f"❌ Failed to set mode {market}")
            continue
        
        # Test 1: Popular Assets
        print("1. Testing Popular Assets...")
        assets = bot.get_popular_assets(5)
        print(f"   ✅ {len(assets)} assets found")
        for asset in assets[:3]:
            print(f"      - {asset.get('symbol')}")
        
        # Test 2: Dynamic Search
        print("\n2. Testing Dynamic Search...")
        test_queries = {
            "crypto": "BTC",
            "forex": "EUR",
            "saham_id": "BBCA", 
            "us_stocks": "AAPL"
        }
        
        query = test_queries.get(market, "TEST")
        search_results = bot.search_assets(query, 3)
        print(f"   ✅ {len(search_results)} search results for '{query}'")
        
        # Test 3: Scanning
        print("\n3. Testing Scanning...")
        signals = bot.scan_potential_assets(limit=3)
        print(f"   ✅ {len(signals)} signals found")
        for signal in signals:
            print(f"      - {signal['symbol']} | {signal['action']} | Score: {signal['score']}")
        
        # Test 4: Backtesting
        print("\n4. Testing Backtesting...")
        if signals:
            symbol = signals[0]['symbol']
            backtest_result = bot.run_advanced_backtest(symbol, limit=100)
            if 'error' not in backtest_result:
                print(f"   ✅ Backtest completed for {symbol}")
            else:
                print(f"   ⚠️ Backtest failed: {backtest_result['error']}")
        
        # Test 5: ML Analysis
        print("\n5. Testing ML Analysis...")
        if assets:
            symbol = assets[0].get('symbol')
            ml_analysis = bot.analyze_with_enhanced_ml(symbol)
            if 'error' not in ml_analysis:
                print(f"   ✅ ML analysis completed for {symbol}")
                print(f"      Action: {ml_analysis.get('action')}, Score: {ml_analysis.get('final_score')}")
            else:
                print(f"   ⚠️ ML analysis failed: {ml_analysis['error']}")

def test_market_constraints():
    """Test semua perbaikan market constraints"""
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

# =============================================
# MAIN EXECUTION
# =============================================

if __name__ == "__main__":
    print("🚀 Testing Enhanced TradingBot dengan Semua Fitur...")
    
    # Test enhanced functionality
    test_enhanced_functionality()
    
    # Test market constraints
    test_market_constraints()
    
    print("✅ Enhanced Core Testing Completed dengan Semua 8 Menu!")
