import os
import sys
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

# =============================================
# EMERGENCY IMPORT FIX - UNTUK STRUKTUR FOLDER BOT
# =============================================

# Tambahkan current directory ke sys.path untuk memastikan import bekerja
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

print(f"📁 Working directory: {current_dir}")
print(f"📦 Python path: {sys.path[:2]}")

# Suppress torch warnings
warnings.filterwarnings("ignore", message=".*torch.classes.*")
warnings.filterwarnings("ignore", category=UserWarning, module="torch")
warnings.filterwarnings("ignore", category=FutureWarning)

load_dotenv()

# Enhanced logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# =============================================
# IMPROVED IMPORT HANDLING - FIXED INDENTATION
# =============================================

# Import modul yang diperlukan dengan error handling yang lebih baik
print("\n" + "="*60)
print("DEBUG IMPORTS - PERBAIKAN INDEKSASI")
print("="*60)

# Initialize all imports to None
TechnicalAnalysisStrategy = None
UnifiedDataProvider = None
EnhancedYFinanceDataProvider = None
DataProviderMonitor = None
DynamicDataProvider = None
EnhancedCCXTDataProvider = None
EnhancedCCXTFuturesProvider = None
AlphaVantageProvider = None
DataProviderFactory = None
SoundNotifier = None
DatabaseHandler = None
SolanaPumpFunProvider = None
EnhancedDexScreenerProvider = None
get_trading_data = None
create_strategy_for_symbol = None
SmartChainDataProvider = None

try:
    print("✅ Mencoba import strategies...")
    from strategies import TechnicalAnalysisStrategy, get_trading_data, create_strategy_for_symbol
    print("  ✅ TechnicalAnalysisStrategy berhasil diimport")
    print("  ✅ get_trading_data dan create_strategy_for_symbol berhasil diimport")
except ImportError as e1:
    print(f"  ❌ Gagal import strategies: {e1}")
    # Buat dummy class dan fungsi
    class TechnicalAnalysisStrategy:
        def __init__(self, *args, **kwargs):
            logger.warning("TechnicalAnalysisStrategy dummy digunakan")
        def analyze(self, *args, **kwargs):
            return {'action': 'NEUTRAL', 'score': 0}
    
    def get_trading_data(symbol, provider=None):
        logger.warning("get_trading_data dummy digunakan")
        return None
    
    def create_strategy_for_symbol(symbol, **kwargs):
        logger.warning("create_strategy_for_symbol dummy digunakan")
        return TechnicalAnalysisStrategy()

try:
    print("✅ Mencoba import DatabaseHandler...")
    from database.db_handler import DatabaseHandler
    print("  ✅ DatabaseHandler berhasil diimport")
except ImportError as e2:
    print(f"  ❌ Gagal import DatabaseHandler: {e2}")
    # Buat dummy class
    class DatabaseHandler:
        def __init__(self):
            logger.warning("DatabaseHandler dummy digunakan")
        def get_active_positions(self, *args, **kwargs):
            return []
        def save_position(self, *args, **kwargs):
            return 1
        def update_position_current_price(self, *args, **kwargs):
            return True
        def close_position(self, *args, **kwargs):
            return True
        def get_trade_history(self, *args, **kwargs):
            return []

try:
    print("✅ Mencoba import SoundNotifier...")
    from notifier import SoundNotifier
    print("  ✅ SoundNotifier berhasil diimport")
except ImportError as e3:
    print(f"  ❌ Gagal import SoundNotifier: {e3}")
    class SoundNotifier:
        def __init__(self):
            logger.warning("SoundNotifier dummy digunakan")
        def notify(self, *args, **kwargs):
            pass

# PERBAIKAN UTAMA: Import data_provider dengan cara yang benar
print("\n🔧 Mengimport modul data_provider...")
try:
    # Import langsung karena satu folder
    import data_provider as data_provider_module
    print("✅ Modul data_provider berhasil diimport")
    
    # Assign setiap class secara individual
    if hasattr(data_provider_module, 'SmartChainDataProvider'):
        SmartChainDataProvider = data_provider_module.SmartChainDataProvider
        print("  ✅ SmartChainDataProvider ditemukan")
    
    if hasattr(data_provider_module, 'UnifiedDataProvider'):
        UnifiedDataProvider = data_provider_module.UnifiedDataProvider
        print("  ✅ UnifiedDataProvider ditemukan")
    
    if hasattr(data_provider_module, 'EnhancedYFinanceDataProvider'):
        EnhancedYFinanceDataProvider = data_provider_module.EnhancedYFinanceDataProvider
        print("  ✅ EnhancedYFinanceDataProvider ditemukan")
    
    if hasattr(data_provider_module, 'DataProviderMonitor'):
        DataProviderMonitor = data_provider_module.DataProviderMonitor
        print("  ✅ DataProviderMonitor ditemukan")
    
    if hasattr(data_provider_module, 'DynamicDataProvider'):
        DynamicDataProvider = data_provider_module.DynamicDataProvider
        print("  ✅ DynamicDataProvider ditemukan")
    
    if hasattr(data_provider_module, 'EnhancedCCXTDataProvider'):
        EnhancedCCXTDataProvider = data_provider_module.EnhancedCCXTDataProvider
        print("  ✅ EnhancedCCXTDataProvider ditemukan")
    
    if hasattr(data_provider_module, 'EnhancedCCXTFuturesProvider'):
        EnhancedCCXTFuturesProvider = data_provider_module.EnhancedCCXTFuturesProvider
        print("  ✅ EnhancedCCXTFuturesProvider ditemukan")
    
    if hasattr(data_provider_module, 'AlphaVantageProvider'):
        AlphaVantageProvider = data_provider_module.AlphaVantageProvider
        print("  ✅ AlphaVantageProvider ditemukan")
    
    if hasattr(data_provider_module, 'DataProviderFactory'):
        DataProviderFactory = data_provider_module.DataProviderFactory
        print("  ✅ DataProviderFactory ditemukan")
    
    if hasattr(data_provider_module, 'SolanaPumpFunProvider'):
        SolanaPumpFunProvider = data_provider_module.SolanaPumpFunProvider
        print("  ✅ SolanaPumpFunProvider ditemukan")
    
    if hasattr(data_provider_module, 'EnhancedDexScreenerProvider'):
        EnhancedDexScreenerProvider = data_provider_module.EnhancedDexScreenerProvider
        print("  ✅ EnhancedDexScreenerProvider ditemukan")
        
except Exception as e:
    print(f"❌ Error mengimport data_provider: {e}")
    print(f"   Traceback: {traceback.format_exc()}")
    
    # Buat dummy classes untuk semua provider
    print("🔄 Membuat dummy classes untuk data providers...")
    
    class UnifiedDataProvider:
        def __init__(self, *args, **kwargs):
            self.market_type = kwargs.get('market_type', 'crypto')
            self.trading_mode = kwargs.get('trading_mode', 'spot')
            self.active_exchange = 'yfinance_fallback'
            logger.warning("UnifiedDataProvider dummy digunakan")
        
        def get_popular_assets(self, limit=100, asset_type='spot'):
            return [{'symbol': 'BTC/USDT', 'name': 'Bitcoin'}]
        
        def get_ohlcv(self, symbol, timeframe, limit):
            dates = pd.date_range(end=datetime.now(), periods=limit, freq='1H')
            df = pd.DataFrame({
                'open': np.random.randn(limit) * 100 + 50000,
                'high': np.random.randn(limit) * 200 + 51000,
                'low': np.random.randn(limit) * 200 + 49000,
                'close': np.random.randn(limit) * 100 + 50000,
                'volume': np.random.rand(limit) * 1000
            }, index=dates)
            return df
        
        def get_ticker(self, symbol):
            return {'last': 50000, 'bid': 49900, 'ask': 50100}
        
        def search_assets(self, query, limit):
            return [{'symbol': 'BTC/USDT', 'name': 'Bitcoin'}]
    
    SmartChainDataProvider = None
    EnhancedYFinanceDataProvider = UnifiedDataProvider
    DataProviderMonitor = None
    DynamicDataProvider = UnifiedDataProvider
    EnhancedCCXTDataProvider = UnifiedDataProvider
    EnhancedCCXTFuturesProvider = UnifiedDataProvider
    AlphaVantageProvider = None
    DataProviderFactory = None
    SolanaPumpFunProvider = None
    EnhancedDexScreenerProvider = None

print("="*60)
print("IMPORT COMPLETED")
print("="*60 + "\n")

# =============================================
# HELPER FUNCTIONS - AUTO DETECTION & CONVERSION
# =============================================

def auto_detect_trading_type(symbol: str) -> Tuple[str, str]:
    """
    Auto-detect trading type (spot/futures) dari simbol.
    Returns: (trading_type, formatted_symbol)
    """
    symbol_upper = symbol.upper()
    
    # Deteksi futures dari format
    futures_markers = [':USDT', ':USDT:', 'PERP', 'FUTURES', 'FUTURE', ':PERP']
    
    for marker in futures_markers:
        if marker in symbol_upper:
            formatted = symbol_upper.replace('-', '/').replace('_', '/')
            return "futures", formatted
    
    # Default spot
    formatted = symbol_upper.replace('-', '/').replace('_', '/')
    return "spot", formatted

def convert_symbol_for_provider(symbol: str, provider_type: str) -> str:
    """
    Konversi simbol berdasarkan provider.
    
    Args:
        symbol: Simbol asli (BTC/USDT, BTC-USDT, BTC/USDT:USDT)
        provider_type: 'yfinance', 'ccxt', atau 'universal'
    
    Returns:
        Simbol yang diformat sesuai provider
    """
    if provider_type == 'yfinance':
        # Konversi untuk Yahoo Finance
        if '/USDT' in symbol:
            # Crypto: BTC/USDT -> BTC-USD
            return symbol.replace('/USDT', '-USD')
        elif ':USDT' in symbol:
            # Futures: BTC/USDT:USDT -> BTC-USD
            return symbol.replace(':USDT', '').replace('/', '-') + '-USD'
        elif '/' in symbol:
            # Pasangan lain: EUR/USD -> EURUSD=X
            base, quote = symbol.split('/')
            if quote in ['USD', 'EUR', 'GBP', 'JPY']:
                return f"{base}{quote}=X"
            else:
                return symbol.replace('/', '-')
        else:
            return symbol.replace('/', '-')
    
    elif provider_type == 'ccxt':
        # Untuk CCXT, format standar
        return symbol.replace('-', '/').replace('_', '/')
    
    else:  # universal
        # Format universal untuk kebanyakan provider
        return symbol.replace('-', '/').replace('_', '/')

# =============================================
# ENHANCED BACKTEST ENGINE
# =============================================

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
            commission = kwargs.get('commission', 0.001)
            
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
                
                # Update equity curve
                if position != 0 and len(trades) > 0:
                    current_trade = trades[-1]
                    if current_trade.get('exit_time') is None:
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
                    optimized_params = self._optimize_parameters(train_data, strategy_class, **kwargs)
                    
                    strategy = strategy_class(**optimized_params)
                    period_result = self.run_backtest(test_data, strategy, **optimized_params)
                    
                    period_result['period'] = i + 1
                    period_result['train_size'] = len(train_data)
                    period_result['test_size'] = len(test_data)
                    results.append(period_result)
                    
                    logger.info(f"  Period {i+1}: {period_result.get('total_trades', 0)} trades, Win Rate: {period_result.get('win_rate', 0):.1%}")
            
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
            
            param_combinations = self._generate_parameter_combinations(param_grid)
            
            for i, params in enumerate(param_combinations):
                try:
                    strategy = strategy_class(**params)
                    result = self.run_backtest(df, strategy, **params)
                    
                    score = result.get('sharpe_ratio', 0)
                    
                    optimization_result = {
                        'params': params.copy(),
                        'score': score,
                        'total_trades': result.get('total_trades', 0),
                        'win_rate': result.get('win_rate', 0),
                        'total_pnl': result.get('total_pnl', 0)
                    }
                    results.append(optimization_result)
                    
                    if score > best_score and result.get('total_trades', 0) >= 5:
                        best_score = score
                        best_params = params.copy()
                    
                    if (i + 1) % 10 == 0:
                        logger.info(f"  Completed {i+1}/{len(param_combinations)} combinations...")
                        
                except Exception as e:
                    logger.warning(f"  Skipping combination {params}: {e}")
                    continue
            
            results.sort(key=lambda x: x['score'], reverse=True)
            
            return {
                'best_params': best_params,
                'best_score': best_score,
                'top_results': results[:10],
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
            
            pnl_values = [t.get('net_pnl', t.get('pnl', 0)) for t in trades if t.get('pnl') is not None]
            
            if len(pnl_values) < 10:
                return {"error": "Insufficient P&L data for simulation"}
            
            simulations = []
            num_trades = len(pnl_values)
            
            logger.info(f"🎲 Running Monte Carlo simulation ({num_simulations} iterations)...")
            
            for i in range(num_simulations):
                sampled_pnls = np.random.choice(pnl_values, size=num_trades, replace=True)
                sim_total = np.sum(sampled_pnls)
                sim_win_rate = np.sum(np.array(sampled_pnls) > 0) / num_trades
                
                simulations.append({
                    'total_pnl': sim_total,
                    'win_rate': sim_win_rate,
                    'avg_trade': np.mean(sampled_pnls)
                })
            
            total_pnls = [s['total_pnl'] for s in simulations]
            win_rates = [s['win_rate'] for s in simulations]
            
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
        score = analysis.get('score', 0)
        if (score >= 2 or score <= -2) and analysis.get('risk_metrics', {}).get('reward_ratio', 0) > 1.5:
            if analysis.get('volume_ratio', 0) > 0.8:
                if analysis.get('rsi', 50) not in [0, 100]:
                    return True
        return False
    
    def _should_exit_trade(self, trade, current_price, analysis, position):
        """Enhanced exit logic with trailing stops"""
        entry_price = trade['entry_price']
        
        if trade['action'] == 'LONG':
            if current_price >= entry_price * 1.05:
                return True
            if current_price <= entry_price * 0.98:
                return True
            if hasattr(self, 'highest_price'):
                if current_price <= self.highest_price * 0.97:
                    return True
            else:
                self.highest_price = current_price
        else:
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
        risk_per_trade = 0.02
        risk_amount = balance * risk_per_trade
        
        if atr > 0:
            position_size = risk_amount / (atr * 2)
        else:
            position_size = (balance * 0.1) / current_price
        
        return min(position_size, (balance * 0.2) / current_price)
    
    def _calculate_comprehensive_performance_metrics(self, trades, equity_curve):
        """Enhanced performance metrics"""
        if not trades or len(equity_curve) < 2:
            return self._get_empty_results()
            
        closed_trades = [t for t in trades if t.get('exit_time') is not None]
        winning_trades = [t for t in closed_trades if t.get('net_pnl', t.get('pnl', 0)) > 0]
        losing_trades = [t for t in closed_trades if t.get('net_pnl', t.get('pnl', 0)) <= 0]
        
        total_trades = len(closed_trades)
        win_rate = len(winning_trades) / total_trades if total_trades else 0
        
        total_pnl = sum(t.get('net_pnl', t.get('pnl', 0)) for t in closed_trades)
        avg_win = np.mean([t.get('net_pnl', t.get('pnl', 0)) for t in winning_trades]) if winning_trades else 0
        avg_loss = np.mean([t.get('net_pnl', t.get('pnl', 0)) for t in losing_trades]) if losing_trades else 0
        profit_factor = abs(sum(t.get('net_pnl', t.get('pnl', 0)) for t in winning_trades) / 
                           sum(t.get('net_pnl', t.get('pnl', 0)) for t in losing_trades)) if losing_trades else float('inf')
        
        returns = np.diff(equity_curve) / np.array(equity_curve[:-1])
        volatility = np.std(returns) * np.sqrt(252) if len(returns) > 1 else 0
        sharpe_ratio = np.mean(returns) / np.std(returns) * np.sqrt(252) if len(returns) > 1 and np.std(returns) > 0 else 0
        
        equity_array = np.array(equity_curve)
        peak = np.maximum.accumulate(equity_array)
        drawdown = (equity_array - peak) / peak
        max_drawdown = np.min(drawdown) if len(drawdown) > 0 else 0
        
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
            'net_pnl': total_pnl,
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
        default_params = {
            'atr_multiplier': 1.0,
            'entry_range_pct': 0.02,
            'market_type': kwargs.get('market_type', 'crypto')
        }
        
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
    take_profits: List[float]
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
        else:
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
        
        if self.position_size <= 0.001:
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
        else:
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
        self.max_portfolio_risk = 0.02
        
    def calculate_position_size(self, symbol: str, entry_price: float, stop_loss: float, 
                              account_balance: float, risk_per_trade: float = 0.01) -> float:
        """Calculate position size based on risk management"""
        if entry_price <= 0 or stop_loss <= 0:
            logger.warning(f"Invalid prices for {symbol}: entry={entry_price}, sl={stop_loss}")
            return 0.0
            
        risk_amount = account_balance * risk_per_trade
        
        if entry_price == stop_loss:
            logger.warning(f"Entry price equals stop loss for {symbol}")
            return 0.0
            
        price_risk = abs(entry_price - stop_loss)
        position_size = risk_amount / price_risk
        
        max_position_value = account_balance * 0.2
        max_position_size = max_position_value / entry_price
        
        return min(position_size, max_position_size)
    
    def open_position(self, symbol: str, market_type: str, action: str, 
                     entry_price: float, stop_loss: float, take_profits: List[float],
                     account_balance: float, trailing_distance: float = 0.0) -> Optional[EnhancedPosition]:
        """Open new position dengan enhanced management"""
        
        if entry_price <= 0:
            logger.error(f"Cannot open position for {symbol}: Invalid entry price {entry_price}")
            return None
        
        if len(self.positions) >= self.max_positions:
            logger.warning(f"Maximum positions reached ({self.max_positions}), cannot open new position for {symbol}")
            return None
        
        position_size = self.calculate_position_size(symbol, entry_price, stop_loss, account_balance)
        
        if position_size <= 0:
            logger.warning(f"Invalid position size for {symbol}")
            return None
        
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
        """Get position ID from symbol"""
        try:
            active_positions = self.db_handler.get_active_positions(market_type)
            position_id = None
            
            for pos in active_positions:
                if isinstance(pos, dict):
                    if pos.get('symbol') == symbol:
                        position_id = pos.get('id')
                        break
                else:
                    if len(pos) > 1 and pos[1] == symbol:
                        position_id = pos[0]
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
            
            if position.trailing_enabled:
                position.update_trailing_stop(current_price)
            
            partial_tp_executed = self._check_partial_tp(position, current_price)
            
            if close_position:
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
                tp_executed = any(tp.get('level', i) == i for tp in position.partial_tp_executed)
                if not tp_executed:
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
        """Close position"""
        if symbol not in self.positions:
            logger.warning(f"Position for {symbol} not found in local manager")
            return False
            
        position = self.positions[symbol]
        
        try:
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
            else:
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
        self.model_weights = {}
        
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
            
            self.scalers[model_type] = RobustScaler()
            self.model_weights[model_type] = 1.0
    
    def advanced_feature_engineering(self, df: pd.DataFrame) -> pd.DataFrame:
        """Advanced feature engineering dengan technical indicators"""
        if df is None or len(df) < 50:
            return pd.DataFrame()
        
        features = {}
        prices = df['close'].values
        volumes = df['volume'].values if 'volume' in df.columns else np.ones(len(df))
        
        if len(prices) == 0 or (prices <= 0).any():
            logger.warning("Invalid price data in feature engineering")
            return pd.DataFrame()
        
        if len(prices) >= 20:
            features['rsi'] = self._calculate_rsi(prices)
            features['macd'] = self._calculate_macd(prices)
            features['sma_20'] = np.mean(prices[-20:])
            features['sma_50'] = np.mean(prices[-min(50, len(prices)):])
            features['ema_12'] = self._calculate_ema(prices, 12)
            features['ema_26'] = self._calculate_ema(prices, 26)
            
            bb_upper, bb_lower, bb_middle = self._calculate_bollinger_bands(prices)
            features['bb_width'] = (bb_upper - bb_lower) / bb_middle if bb_middle > 0 else 0
            features['bb_position'] = (prices[-1] - bb_lower) / (bb_upper - bb_lower) if (bb_upper - bb_lower) > 0 else 0.5
        
        if len(volumes) >= 20:
            features['volume_ratio'] = volumes[-1] / np.mean(volumes[-20:]) if np.mean(volumes[-20:]) > 0 else 1
            features['volume_sma_ratio'] = volumes[-1] / np.mean(volumes) if np.mean(volumes) > 0 else 1
            features['obv'] = self._calculate_obv(prices, volumes)
        
        if len(prices) >= 20:
            features['atr'] = self._calculate_atr(df) if len(df) >= 14 else 0.02
            
            if features['atr'] <= 0:
                features['atr'] = prices[-1] * 0.001
                
            returns = np.diff(prices) / prices[:-1]
            features['volatility'] = np.std(returns) * np.sqrt(252) if len(returns) > 1 else 0.02
        
        if len(prices) >= 10:
            features['momentum_5'] = (prices[-1] / prices[-5] - 1) * 100 if prices[-5] > 0 else 0
            features['momentum_10'] = (prices[-1] / prices[-10] - 1) * 100 if prices[-10] > 0 else 0
            features['williams_r'] = self._calculate_williams_r(df)
            features['cci'] = self._calculate_cci(df)
        
        if len(prices) >= 20:
            features['skewness'] = stats.skew(prices[-20:])
            features['kurtosis'] = stats.kurtosis(prices[-20:])
            features['z_score'] = (prices[-1] - np.mean(prices[-20:])) / np.std(prices[-20:]) if np.std(prices[-20:]) > 0 else 0
        
        if len(prices) >= 10:
            features['trend_strength'] = self._calculate_trend_strength(prices)
            recent_trend = np.polyfit(range(5), prices[-5:], 1)[0]
            features['pattern_score'] = recent_trend * 100
        
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
        """Calculate ATR dengan fallback yang lebih baik"""
        try:
            if len(df) < period:
                return df['close'].iloc[-1] * 0.02 if len(df) > 0 else 0.02
                
            high = df['high'].values
            low = df['low'].values
            close = df['close'].values
            
            tr = np.zeros(len(high))
            for i in range(1, len(high)):
                tr1 = high[i] - low[i]
                tr2 = abs(high[i] - close[i-1])
                tr3 = abs(low[i] - close[i-1])
                tr[i] = max(tr1, tr2, tr3)
            
            atr_value = np.mean(tr[-period:]) if len(tr) >= period else np.mean(tr)
            
            if atr_value <= 0:
                atr_value = df['close'].iloc[-1] * 0.01
                
            return atr_value
        except:
            return df['close'].iloc[-1] * 0.02 if len(df) > 0 else 0.02
    
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
        return slope * r_value ** 2
    
    def train_ensemble(self, X: np.ndarray, y: np.ndarray, validation_size: float = 0.2):
        """Train ensemble of models dengan cross-validation"""
        if len(X) < 100:
            logger.warning("Insufficient data for training ensemble")
            return False
        
        X_train, X_val, y_train, y_val = train_test_split(
            X, y, test_size=validation_size, shuffle=False, random_state=42
        )
        
        model_scores = {}
        
        for model_name, model in self.models.items():
            try:
                X_train_scaled = self.scalers[model_name].fit_transform(X_train)
                X_val_scaled = self.scalers[model_name].transform(X_val)
                
                model.fit(X_train_scaled, y_train)
                
                y_pred = model.predict(X_val_scaled)
                accuracy = accuracy_score(y_val, y_pred)
                precision, recall, f1, _ = precision_recall_fscore_support(y_val, y_pred, average='weighted')
                
                model_scores[model_name] = {
                    'accuracy': accuracy,
                    'precision': precision,
                    'recall': recall,
                    'f1': f1
                }
                
                self.model_weights[model_name] = f1
                
                logger.info(f"Model {model_name} trained - Accuracy: {accuracy:.3f}, F1: {f1:.3f}")
                
            except Exception as e:
                logger.error(f"Error training {model_name}: {e}")
                model_scores[model_name] = {'accuracy': 0, 'f1': 0}
                self.model_weights[model_name] = 0.1
        
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
                if self.model_weights[model_name] > 0.01:
                    X_scaled = self.scalers[model_name].transform(X)
                    
                    if hasattr(model, 'predict_proba'):
                        proba = model.predict_proba(X_scaled)
                        confidence = np.max(proba)
                        prediction = np.argmax(proba)
                    else:
                        prediction = model.predict(X_scaled)[0]
                        confidence = 0.5
                    
                    predictions.append(prediction)
                    confidences.append(confidence)
                    weights.append(self.model_weights[model_name])
                    
            except Exception as e:
                logger.warning(f"Prediction failed for {model_name}: {e}")
                continue
        
        if not predictions:
            return 0.5, 0
        
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
        self.risk_free_rate = 0.02
        self.max_allocation_per_asset = 0.2
        self.min_allocation_per_asset = 0.05
    
    def mean_variance_optimization(self, expected_returns: List[float], 
                                 covariance_matrix: np.ndarray,
                                 target_return: float = None) -> Dict[str, Any]:
        """Mean-variance optimization (Markowitz)"""
        n_assets = len(expected_returns)
        
        if n_assets == 0:
            return {'weights': [], 'sharpe_ratio': 0, 'portfolio_return': 0, 'portfolio_risk': 0}
        
        try:
            equal_weights = np.ones(n_assets) / n_assets
            
            port_return = np.dot(equal_weights, expected_returns)
            port_risk = np.sqrt(np.dot(equal_weights.T, np.dot(covariance_matrix, equal_weights)))
            sharpe_ratio = (port_return - self.risk_free_rate) / port_risk if port_risk > 0 else 0
            
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
        
        inv_volatility = [1/v if v > 0 else 0 for v in volatility_estimates]
        total_inv_vol = sum(inv_volatility)
        
        if total_inv_vol == 0:
            return [1/len(volatility_estimates)] * len(volatility_estimates)
        
        weights = [inv_vol / total_inv_vol for inv_vol in inv_volatility]
        return self._apply_allocation_constraints(weights)
    
    def momentum_based_allocation(self, signals: List[Dict], total_capital: float) -> List[Dict]:
        """Momentum-based portfolio allocation"""
        if not signals:
            return []
        
        sorted_signals = sorted(signals, key=lambda x: abs(x.get('score', 0)), reverse=True)
        
        scores = [abs(s.get('score', 0)) for s in sorted_signals]
        volatilities = [s.get('volatility', 0.02) for s in sorted_signals]
        
        if sum(scores) == 0:
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
        
        weights = []
        for i, signal in enumerate(sorted_signals):
            score_weight = scores[i] / sum(scores)
            vol_weight = 1 / (volatilities[i] + 0.01)
            combined_weight = score_weight * vol_weight
            weights.append(combined_weight)
        
        total_weight = sum(weights)
        normalized_weights = [w / total_weight for w in weights]
        
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
        
        min_weight = self.min_allocation_per_asset
        constrained_weights[constrained_weights < min_weight] = 0
        
        max_weight = self.max_allocation_per_asset
        constrained_weights[constrained_weights > max_weight] = max_weight
        
        total_weight = np.sum(constrained_weights)
        if total_weight > 0:
            constrained_weights /= total_weight
        else:
            constrained_weights = np.ones(n_assets) / n_assets
        
        return constrained_weights.tolist()
    
    def _calculate_efficient_frontier(self, expected_returns: List[float], 
                                    covariance_matrix: np.ndarray, 
                                    points: int = 20) -> List[Dict]:
        """Calculate efficient frontier points"""
        frontiers = []
        
        for i in range(points):
            target_return = np.min(expected_returns) + (np.max(expected_returns) - np.min(expected_returns)) * i / points
            
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
# ENHANCED ML BOT
# =============================================

class MLEnhancedBot:
    """Machine Learning enhanced trading bot"""
    
    def __init__(self, model_type='random_forest'):
        self.model_type = model_type
        self.model = None
        self.scaler = StandardScaler()
        self.is_trained = False
        self.model_path = "models/trading_model.pkl"
        self.scaler_path = "models/scaler.pkl"
        self.feature_importance = {}
        
        os.makedirs("models", exist_ok=True)
        
        self.load_model()

    def load_model(self):
        """Load model dan scaler yang sudah ditraining"""
        try:
            if (os.path.exists(self.model_path) and 
                os.path.exists(self.scaler_path) and
                os.path.getsize(self.model_path) > 1000):
                
                self.model = None
                self.scaler = None
                
                self.model = joblib.load(self.model_path)
                self.scaler = joblib.load(self.scaler_path)
                
                if (hasattr(self.model, 'predict') and 
                    hasattr(self.scaler, 'transform')):
                    self.is_trained = True
                    logger.info("✅ ML model loaded successfully")
                    return True
                else:
                    logger.error("❌ Loaded model invalid")
                    self._initialize_model()
                    return False
            else:
                logger.warning("Model files not found or too small, initializing new model")
                self._initialize_model()
                return False
                
        except Exception as e:
            logger.error(f"❌ Error loading model: {e}")
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
                if len(data) < 100:
                    continue
                    
                for i in range(50, len(data) - 10):
                    current_window = data.iloc[:i+1]
                    future_window = data.iloc[i+1:i+11]
                    
                    features = self._extract_detailed_features(current_window)
                    if features:
                        current_price = current_window['close'].iloc[-1]
                        future_max = future_window['close'].max()
                        future_min = future_window['close'].min()
                        
                        price_change = (future_max - current_price) / current_price
                        if price_change >= 0.02:
                            target = 1
                        elif (future_min - current_price) / current_price <= -0.02:
                            target = -1
                        else:
                            target = 0
                            
                        features_list.append(features)
                        targets.append(target)
            
            if len(features_list) < 100:
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
            
            tscv = TimeSeriesSplit(n_splits=5)
            accuracies = []
            
            for train_idx, test_idx in tscv.split(X):
                X_train, X_test = X[train_idx], X[test_idx]
                y_train, y_test = y[train_idx], y[test_idx]
                
                X_train_scaled = self.scaler.fit_transform(X_train)
                X_test_scaled = self.scaler.transform(X_test)
                
                self.model.fit(X_train_scaled, y_train)
                
                y_pred = self.model.predict(X_test_scaled)
                accuracy = accuracy_score(y_test, y_pred)
                accuracies.append(accuracy)
            
            X_scaled = self.scaler.fit_transform(X)
            self.model.fit(X_scaled, y)
            
            if hasattr(self.model, 'feature_importances_'):
                feature_names = [
                    'rsi', 'macd', 'sma_20', 'sma_50', 'ema_12', 'ema_26',
                    'atr', 'volume_ratio', 'price_change_1d', 'price_change_5d',
                    'volatility', 'momentum', 'williams_r', 'cci', 'obv'
                ]
                if len(self.model.feature_importances_) == len(feature_names):
                    self.feature_importance = dict(zip(feature_names, self.model.feature_importances_))
                else:
                    self.feature_importance = {f: 0.0 for f in feature_names}
            
            self.is_trained = True
            avg_accuracy = np.mean(accuracies)
            
            logger.info(f"✅ Model training completed! Average Accuracy: {avg_accuracy:.3f}")
            logger.info(f"📈 Feature Importance: {self.feature_importance}")
            
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
            
            prices = df['close']
            volumes = df['volume']
            
            features['rsi'] = self._calculate_rsi(prices)
            features['macd'] = self._calculate_macd(prices)
            features['sma_20'] = prices.rolling(20).mean().iloc[-1] if len(prices) >= 20 else prices.mean()
            features['sma_50'] = prices.rolling(50).mean().iloc[-1] if len(prices) >= 50 else prices.mean()
            features['ema_12'] = prices.ewm(span=12).mean().iloc[-1]
            features['ema_26'] = prices.ewm(span=26).mean().iloc[-1]
            
            features['atr'] = self._calculate_atr(df)
            
            vol_mean = volumes.rolling(20).mean().iloc[-1] if len(volumes) >= 20 else volumes.mean()
            features['volume_ratio'] = volumes.iloc[-1] / vol_mean if vol_mean > 0 else 1
            
            if len(df) > 1:
                features['price_change_1d'] = (prices.iloc[-1] - prices.iloc[-2]) / prices.iloc[-2] if prices.iloc[-2] != 0 else 0
            else:
                features['price_change_1d'] = 0
                
            if len(df) > 5:
                features['price_change_5d'] = (prices.iloc[-1] - prices.iloc[-6]) / prices.iloc[-6] if prices.iloc[-6] != 0 else 0
            else:
                features['price_change_5d'] = 0
            
            features['volatility'] = prices.pct_change().std() * np.sqrt(252) if len(prices) > 1 else 0.02
            features['momentum'] = (prices.iloc[-1] - prices.iloc[-10]) / prices.iloc[-10] if len(prices) > 10 and prices.iloc[-10] != 0 else 0
            features['williams_r'] = self._calculate_williams_r(df)
            features['cci'] = self._calculate_cci(df)
            features['obv'] = self._calculate_obv(df)
            
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
                return 0.5, 0
            
            features_df = self.extract_features(df)
            if features_df.empty:
                return 0.5, 0
            
            features_scaled = self.scaler.transform(features_df)
            
            prediction = self.model.predict(features_scaled)[0]
            probabilities = self.model.predict_proba(features_scaled)[0]
            
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
            
            for symbol, df in symbols_data.items():
                features_df = self.extract_features(df)
                if not features_df.empty:
                    features_list.append(features_df.iloc[0].values)
                    symbol_features[symbol] = features_df.iloc[0].values
            
            if not features_list:
                return {}
            
            features_array = np.array(features_list)
            features_scaled = self.scaler.transform(features_array)
            
            batch_predictions = self.model.predict(features_scaled)
            batch_probabilities = self.model.predict_proba(features_array)
            
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
# ENHANCED TRADING BOT CORE - UNIVERSAL PROVIDER
# =============================================

class EnhancedTradingBot:
    """Enhanced trading bot dengan UNIVERSAL provider"""
    
    def __init__(self, config=None):
        if config is None:
            config_path = "config/config.json"
            self.config_path = config_path
            self.load_config()
        else:
            self.config = config
            self.config_path = "config/config.json"
        
        self.mode = None
        
        # **PERBAIKAN: Leverage default 1x**
        self.leverage = 1
        
        # **PERBAIKAN UTAMA: Setup provider universal**
        self.data_provider = None
        self._setup_universal_provider()
        
        # Initialize components
        self.strategy = None
        self.notifier = SoundNotifier()
        self.db = DatabaseHandler()
        
        # ENHANCED COMPONENTS
        self.position_manager = EnhancedPositionManager(self.db)
        self.ml_ensemble = EnsembleMLModel()
        self.ml_bot = MLEnhancedBot()
        self.portfolio_optimizer = PortfolioOptimizer()
        self.backtest_engine = BacktestEngine()
        
        # Configuration
        self.risk_per_trade = self.config.get("risk_per_trade", 0.01)
        self.max_drawdown_limit = self.config.get("max_drawdown_limit", 0.1)
        self.daily_loss_limit = self.config.get("daily_loss_limit", 0.05)
        
        # Trading mode
        self.trading_mode = self.config.get("trading_mode", "spot")
        
        # **PERBAIKAN: Hapus leverage dari config**
        if 'leverage' in self.config:
            self.config['leverage'] = 1
        
        # Monitoring
        self.daily_pnl = 0.0
        self.max_portfolio_value = 0.0
        self.current_drawdown = 0.0
        self.trading_enabled = True
        
        # Threading
        self.scheduler_thread = None
        self.stop_scheduler = False
        self.scanning_in_progress = False
        self.current_scan_task = None
        
        # ML enhancements
        self.ml_predictions_cache = {}
        self.last_ml_update = 0
        
        logger.info("✅ Enhanced TradingBot initialized dengan Universal Provider")

    def validate_market_data(self, df: pd.DataFrame, symbol: str, debug_mode: bool = False) -> Tuple[bool, str]:
        """Validasi data market dengan logging lebih detail"""
        checks = []
        messages = []
        
        # Check 1: DataFrame tidak kosong
        if df is None or len(df) == 0:
            return False, "Empty DataFrame"
        
        # Check 2: Column yang diperlukan ada
        required_columns = ['open', 'high', 'low', 'close']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            return False, f"Missing columns: {missing_columns}"
        
        # Check 3: Minimal data points
        min_data_points = 20
        if len(df) < min_data_points:
            return False, f"Insufficient data points: {len(df)} < {min_data_points}"
        
        # Check 4: Validasi harga positif
        price_columns = ['open', 'high', 'low', 'close']
        for col in price_columns:
            if (df[col] <= 0).any():
                checks.append(False)
                messages.append(f"❌ Non-positive values in {col}")
        
        # Check 5: Harga high >= low
        if (df['high'] < df['low']).any():
            checks.append(False)
            messages.append("❌ High < Low detected")
        
        # Check 6: Harga dalam range yang wajar
        if 'close' in df.columns and len(df) > 0:
            avg_price = df['close'].mean()
            min_price = df['close'].min()
            max_price = df['close'].max()
            
            if debug_mode:
                logger.debug(f"🔍 DEBUG {symbol}: Avg price = {avg_price:.8f}, Min = {min_price:.8f}, Max = {max_price:.8f}")
            
            # Deteksi dini harga ~100 (kemungkinan data sintetik)
            if abs(avg_price - 100.0) < 0.1:
                logger.error(f"🚨 CRITICAL: {symbol} has average price ~100 (likely synthetic/bad data)")
                checks.append(False)
                messages.append(f"❌ Average price is ~100 (invalid data)")
            
            # Check volume jika ada
            if 'volume' in df.columns:
                avg_volume = df['volume'].mean()
                if avg_volume <= 0:
                    checks.append(False)
                    messages.append(f"❌ Invalid volume: {avg_volume}")
        
        # Check 7: Tidak ada NaN values di kolom penting
        important_columns = ['open', 'high', 'low', 'close']
        for col in important_columns:
            if df[col].isna().any():
                checks.append(False)
                messages.append(f"❌ NaN values in {col}")
        
        # Hasil akhir
        all_checks_pass = all(checks) if checks else True
        
        if not all_checks_pass:
            error_msg = f"Data validation failed for {symbol}: " + "; ".join(messages)
            if debug_mode:
                logger.error(error_msg)
            return False, error_msg
        
        return True, "Data validation passed"

    def _setup_universal_provider(self):
        """Setup provider universal dengan SmartChain priority"""
        try:
            market_type = self.config.get("market_type", "crypto")
            
            logger.info(f"🔧 Setting up provider for {market_type} market...")
            
            # Priority order dari config
            provider_priority = self.config.get("provider_priority", "smart_chain")
            
            if provider_priority == "smart_chain" and SmartChainDataProvider is not None:
                # Coba SmartChainDataProvider terlebih dahulu
                try:
                    primary_mirror = self.config.get("primary_mirror", "binanceus")
                    self.data_provider = SmartChainDataProvider(
                        primary_mirror=primary_mirror,
                        market_type=market_type
                    )
                    logger.info(f"✅ Using SmartChainDataProvider with primary mirror: {primary_mirror}")
                    return True
                except Exception as e:
                    logger.warning(f"⚠️ SmartChainDataProvider failed: {e}")
            
            # Fallback ke UnifiedDataProvider
            if UnifiedDataProvider is not None:
                try:
                    exchange_id = self.config.get("exchange_crypto", "binance")
                    self.data_provider = UnifiedDataProvider(
                        exchange_id=exchange_id,
                        api_key='',
                        secret=''
                    )
                    logger.info(f"✅ Using UnifiedDataProvider with exchange: {exchange_id}")
                    return True
                except Exception as e:
                    logger.warning(f"⚠️ UnifiedDataProvider failed: {e}")
            
            # Fallback ke EnhancedCCXTDataProvider untuk crypto
            if market_type == 'crypto' and EnhancedCCXTDataProvider is not None:
                try:
                    exchange_id = self.config.get("exchange_crypto", "binance")
                    self.data_provider = EnhancedCCXTDataProvider(
                        exchange_id=exchange_id,
                        api_key='',
                        secret=''
                    )
                    logger.info(f"✅ Using EnhancedCCXTDataProvider: {exchange_id}")
                    return True
                except Exception as e:
                    logger.warning(f"⚠️ EnhancedCCXTDataProvider failed: {e}")
            
            # Ultimate fallback: YFinance
            if EnhancedYFinanceDataProvider is not None:
                self.data_provider = EnhancedYFinanceDataProvider()
                logger.info(f"✅ Using EnhancedYFinanceDataProvider for {market_type}")
                return True
            
            # Dummy fallback
            logger.error("❌ All providers failed, using dummy provider")
            class DummyDataProvider:
                def __init__(self, *args, **kwargs):
                    self.market_type = kwargs.get('market_type', 'crypto')
                    self.trading_mode = kwargs.get('trading_mode', 'spot')
                    self.active_exchange = 'dummy'
                
                def get_popular_assets(self, limit=100, asset_type='spot'):
                    return [{'symbol': 'BTC/USDT', 'name': 'Bitcoin'}]
                
                def get_ohlcv(self, symbol, timeframe, limit):
                    dates = pd.date_range(end=datetime.now(), periods=limit, freq='1H')
                    df = pd.DataFrame({
                        'open': np.random.randn(limit) * 100 + 50000,
                        'high': np.random.randn(limit) * 200 + 51000,
                        'low': np.random.randn(limit) * 200 + 49000,
                        'close': np.random.randn(limit) * 100 + 50000,
                        'volume': np.random.rand(limit) * 1000
                    }, index=dates)
                    return df
                
                def get_ticker(self, symbol):
                    return {'last': 50000, 'bid': 49900, 'ask': 50100}
                
                def search_assets(self, query, limit):
                    return [{'symbol': 'BTC/USDT', 'name': 'Bitcoin'}]
            
            self.data_provider = DummyDataProvider()
            logger.warning("⚠️ Using dummy data provider")
            return False
            
        except Exception as e:
            logger.error(f"❌ Failed to setup universal provider: {e}")
            return False

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
            "exchange_crypto": "binance",
            "analysis_coins_limit": 150,
            "ohlcv_limit": 200,
            "min_score": 2,
            "max_signals": 25,
            "update_interval": 30,
            "scan_delay": 0.3,
            "market_type": "crypto",
            "risk_per_trade": 0.01,
            "max_drawdown_limit": 0.1,
            "daily_loss_limit": 0.05,
            "enable_ml": True,
            "enable_trailing_stop": True,
            "partial_tp_enabled": True,
            "trading_mode": "spot",
            "default_exchange": "binance",
            "leverage": 1,
            # Tambahan untuk SmartChainDataProvider
            "provider_priority": "smart_chain",
            "primary_mirror": "binanceus"
        }
    
    def save_config(self):
        """Save configuration"""
        try:
            os.makedirs("config", exist_ok=True)
            with open(self.config_path, "w") as f:
                json.dump(self.config, f, indent=4)
        except Exception as e:
            logger.error(f"Error saving config: {e}")

    def _create_spot_strategy(self):
        """Create spot strategy"""
        return TechnicalAnalysisStrategy(
            market_type=self.mode,
            trading_type="spot",
            atr_multiplier=self.config.get("atr_multiplier", 1.0),
            entry_range_pct=self.config.get("entry_range_pct", 0.02),
        )
    
    def _create_futures_strategy(self):
        """Create futures strategy"""
        return TechnicalAnalysisStrategy(
            market_type=self.mode,
            trading_type="futures",
            atr_multiplier=self.config.get("atr_multiplier", 1.0),
            entry_range_pct=self.config.get("entry_range_pct", 0.02),
        )

    def get_popular_assets(self, limit=100):
        """Get all popular assets - biar strategi yang filter"""
        if not self.data_provider:
            return []
        
        try:
            assets = self.data_provider.get_popular_assets(limit)
            
            # Tambahkan auto-detected type
            for asset in assets:
                symbol = asset['symbol']
                trading_type, formatted_symbol = auto_detect_trading_type(symbol)
                asset['detected_type'] = trading_type
                asset['formatted_symbol'] = formatted_symbol
            
            return assets
        except Exception as e:
            logger.error(f"Error: {e}")
            return []

    def scan_potential_assets(self, limit=25, search_query: str = None):
        """Scan sederhana dengan provider universal - PERBAIKAN UTAMA"""
        if self.scanning_in_progress:
            logger.warning("Scan already in progress")
            return []
        
        self.scanning_in_progress = True
        self.current_scan_task = threading.current_thread().ident
        
        try:
            # Validasi provider
            if not self.data_provider:
                logger.error("❌ No data provider available. Run set_mode() first!")
                self.scanning_in_progress = False
                return []
            
            assets_limit = self.config.get("analysis_coins_limit", 150)
            
            logger.info(f"🔍 Scanning for {limit} signals...")
            logger.info(f"📊 Will analyze up to {assets_limit} assets")
            logger.info(f"🏢 Using provider: {self.data_provider.__class__.__name__}")
            
            # Get assets
            assets = self.get_popular_assets(assets_limit)
            
            if not assets:
                logger.warning("❌ No assets available for scanning")
                self.scanning_in_progress = False
                return []
            
            logger.info(f"📊 Scanning {len(assets)} assets...")
            
            signals = []
            scan_delay = self.config.get("scan_delay", 0.3)
            
            for i, asset in enumerate(assets[:50]):
                try:
                    symbol = asset.get('symbol')
                    asset_name = asset.get('name', symbol)
                    detected_type = asset.get('detected_type', 'spot')
                    formatted_symbol = asset.get('formatted_symbol', symbol)
                    
                    if not symbol:
                        continue
                    
                    logger.info(f"  [{i+1}/{len(assets[:50])}] Analyzing: {symbol} (Type: {detected_type})")
                    
                    # **PERBAIKAN UTAMA: Gunakan get_trading_data jika tersedia, kalau tidak gunakan provider langsung**
                    if get_trading_data is not None:
                        logger.info(f"    🔧 Menggunakan get_trading_data untuk membersihkan data {formatted_symbol}")
                        df = get_trading_data(formatted_symbol, self.data_provider)
                    else:
                        logger.info(f"    🔧 Menggunakan provider {self.data_provider.__class__.__name__} untuk data {formatted_symbol}")
                        df = self.data_provider.get_ohlcv(formatted_symbol, self.config.get("timeframe", "1h"), 100)
                    
                    if df is None or len(df) < 50:
                        logger.info(f"    ⚠️ Insufficient data for {symbol}: {len(df) if df else 0} bars")
                        continue
                    
                    # Validasi kualitas data
                    is_valid, validation_msg = self.validate_market_data(df, symbol, debug_mode=True)
                    if not is_valid:
                        logger.warning(f"    ⚠️ Data validation failed for {symbol}: {validation_msg}")
                        continue
                    
                    logger.info(f"    📊 OHLCV data: {len(df)} bars, price range: {df['close'].min():.2f}-{df['close'].max():.2f}")
                    
                    # Pilih strategi berdasarkan tipe
                    if detected_type == "futures":
                        strategy = self._create_futures_strategy()
                        leverage = 5  # Default untuk futures
                    else:
                        strategy = self._create_spot_strategy()
                        leverage = 1  # No leverage untuk spot
                    
                    # Analyze dengan strategy
                    analysis = strategy.analyze(df)
                    if not analysis:
                        logger.info(f"    ⚠️ No analysis for {symbol}")
                        continue
                    
                    # **PERBAIKAN UTAMA: Apply market constraints - untuk spot crypto hanya LONG**
                    analysis = self._apply_market_constraints(analysis, detected_type)
                    
                    score = analysis.get('score', 0)
                    action = analysis.get('action', 'NEUTRAL')
                    
                    min_score = self.config.get("min_score", 2.0)
                    
                    # Check jika signal valid
                    if abs(score) >= min_score and action != 'NEUTRAL':
                        signal_data = {
                            'symbol': formatted_symbol,
                            'name': asset_name,
                            'score': round(score, 2),
                            'action': action,
                            'entry_price': round(analysis.get('entry_price', df['close'].iloc[-1] if len(df) > 0 else 0), 4),
                            'sl': round(analysis.get('sl', df['close'].iloc[-1] * 0.97 if len(df) > 0 else 0), 4),
                            'tp1': round(analysis.get('tp1', df['close'].iloc[-1] * 1.03 if len(df) > 0 else 0), 4),
                            'tp2': round(analysis.get('tp2', df['close'].iloc[-1] * 1.06 if len(df) > 0 else 0), 4),
                            'tp3': round(analysis.get('tp3', df['close'].iloc[-1] * 1.09 if len(df) > 0 else 0), 4),
                            'current_price': round(df['close'].iloc[-1] if len(df) > 0 else 0, 4),
                            'ml_confidence': round(analysis.get('ml_confidence', 0), 2),
                            'rsi': round(analysis.get('rsi', 50), 2),
                            'volume_ratio': round(analysis.get('volume_ratio', 1), 2),
                            'market_type': self.mode,
                            'trading_mode': detected_type,
                            'provider': 'universal',
                            'asset_type': detected_type,
                            'leverage': leverage
                        }
                        
                        signals.append(signal_data)
                        logger.info(f"✅ Signal: {formatted_symbol} | {action} | Score: {score:.2f} | Type: {detected_type} | Leverage: {leverage}x")
                        
                        # Stop jika sudah cukup sinyal
                        if len(signals) >= limit:
                            break
                    
                    # Rate limiting
                    if scan_delay > 0:
                        time.sleep(scan_delay)
                
                except Exception as e:
                    logger.error(f"❌ Error analyzing {asset.get('symbol', 'unknown')}: {str(e)[:100]}")
                    continue
            
            logger.info(f"🎯 Scan completed: {len(signals)} signals found")
            
            # Sort signals by score absolute value
            if signals:
                signals.sort(key=lambda x: abs(x['score']), reverse=True)
                logger.info("🏆 Top signals:")
                for i, signal in enumerate(signals[:min(10, len(signals))]):
                    logger.info(f"  {i+1}. {signal['symbol']} | {signal['action']} | Score: {signal['score']} | Mode: {signal.get('trading_mode', 'N/A')}")
            else:
                logger.info("ℹ️ No signals found with current criteria")
            
            return signals[:limit]
            
        except Exception as e:
            logger.error(f"💥 Error during scanning: {e}")
            return []
        finally:
            self.scanning_in_progress = False
            self.current_scan_task = None

    def _apply_market_constraints(self, analysis: dict, detected_type: str = "spot") -> dict:
        """Apply market constraints berdasarkan detected type"""
        if not isinstance(analysis, dict):
            return analysis
            
        action = analysis.get('action', 'NEUTRAL')
        
        # **PERBAIKAN UTAMA: Untuk spot crypto, hanya LONG yang diperbolehkan**
        if action == 'SHORT' and self.mode == 'crypto' and detected_type == 'spot':
            logger.debug(f"🚫 SHORT blocked for {self.mode} (spot mode)")
            analysis['action'] = 'NEUTRAL'
            analysis['score'] = 0
        
        # Block SHORT untuk market lain
        elif action == 'SHORT' and self.mode in ['forex', 'saham_id', 'us_stocks']:
            logger.debug(f"🚫 SHORT blocked for {self.mode}")
            analysis['action'] = 'NEUTRAL'
            analysis['score'] = 0
        
        return analysis

    def analyze_with_enhanced_ml(self, symbol: str) -> dict:
        """Analyze asset dengan ML enhancement - MENGGUNAKAN get_trading_data"""
        try:
            if not self.data_provider:
                return {'error': 'No data provider available'}
            
            # Auto detect type
            detected_type, formatted_symbol = auto_detect_trading_type(symbol)
            
            # Get data menggunakan get_trading_data jika tersedia
            if get_trading_data is not None:
                logger.info(f"🔍 Menggunakan get_trading_data untuk membersihkan data {formatted_symbol}")
                df = get_trading_data(formatted_symbol, self.data_provider)
            else:
                logger.info(f"🔍 Menggunakan provider {self.data_provider.__class__.__name__} untuk data {formatted_symbol}")
                df = self.data_provider.get_ohlcv(formatted_symbol, self.config.get("timeframe", "1h"), 100)
            
            if df is None or len(df) < 50:
                return {'error': 'Insufficient data'}
            
            # Validasi data
            is_valid, validation_msg = self.validate_market_data(df, symbol, debug_mode=True)
            if not is_valid:
                return {'error': f'Data validation failed: {validation_msg}'}
            
            # Pilih strategi berdasarkan tipe
            if detected_type == "futures":
                strategy = self._create_futures_strategy()
            else:
                strategy = self._create_spot_strategy()
            
            # Technical analysis
            analysis = strategy.analyze(df)
            if not analysis:
                return {'error': 'Analysis failed'}
            
            # Apply market constraints
            analysis = self._apply_market_constraints(analysis, detected_type)
            
            return analysis
            
        except Exception as e:
            logger.error(f"Analysis error for {symbol}: {e}")
            return {'error': str(e)}

    # =============================================
    # BACKTEST METHODS
    # =============================================

    def run_advanced_backtest(self, symbol, timeframe=None, limit=500):
        """Run advanced backtest"""
        if not self.data_provider:
            return {"error": "No data provider available"}
            
        try:
            detected_type, formatted_symbol = auto_detect_trading_type(symbol)
            
            if timeframe is None:
                timeframe = self.config.get("timeframe", "1h")
                
            logger.info(f"🔧 Running advanced backtest for {formatted_symbol} ({detected_type})...")
            
            # Get data menggunakan get_trading_data jika tersedia
            if get_trading_data is not None:
                logger.info(f"  🔧 Menggunakan get_trading_data untuk data bersih")
                df = get_trading_data(formatted_symbol, self.data_provider)
            else:
                logger.info(f"  🔧 Menggunakan provider {self.data_provider.__class__.__name__}")
                df = self.data_provider.get_ohlcv(formatted_symbol, timeframe, limit)
            
            if df is None or len(df) < 100:
                return {"error": "Insufficient data for backtest"}
            
            # Validasi data
            is_valid, validation_msg = self.validate_market_data(df, symbol, debug_mode=True)
            if not is_valid:
                return {"error": f"Data validation failed: {validation_msg}"}
            
            # Pilih strategi
            if detected_type == "futures":
                strategy = self._create_futures_strategy()
            else:
                strategy = self._create_spot_strategy()
            
            # Run backtest
            basic_result = self.backtest_engine.run_backtest(df, strategy)
            
            return {
                'symbol': formatted_symbol,
                'detected_type': detected_type,
                'timeframe': timeframe,
                'basic_backtest': basic_result,
                'data_points': len(df)
            }
            
        except Exception as e:
            logger.error(f"Error in advanced backtest: {e}")
            return {"error": str(e)}

    # =============================================
    # PORTFOLIO OPTIMIZATION METHODS
    # =============================================

    def get_optimized_portfolio_allocation(self, signals: List[Dict], total_capital: float) -> List[Dict]:
        """Get optimized portfolio allocation"""
        try:
            return self.portfolio_optimizer.momentum_based_allocation(signals, total_capital)
        except Exception as e:
            logger.error(f"Portfolio optimization error: {e}")
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
                'action': s.get('action', 'NEUTRAL'),
                'asset_type': s.get('asset_type', 'spot')
            }
            for s in signals
        ]

    # =============================================
    # BACKGROUND TASKS
    # =============================================

    def start_background_tasks(self):
        """Start background tasks"""
        try:
            if self.scheduler_thread and self.scheduler_thread.is_alive():
                self.stop_background_tasks()
                
            self.stop_scheduler = False
            self.scheduler_thread = threading.Thread(target=self._run_scheduler, daemon=True)
            self.scheduler_thread.start()
            
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
        """Update all positions"""
        if not self.trading_enabled or not self.data_provider:
            return
        
        try:
            positions = self.position_manager.positions
            if not positions:
                return
            
            for symbol in list(positions.keys()):
                try:
                    ticker = self.data_provider.get_ticker(symbol)
                    if ticker and 'last' in ticker and ticker['last'] > 0:
                        # Update position dengan harga baru
                        pass
                except Exception as e:
                    logger.warning(f"Failed to get price for {symbol}: {e}")
                    
        except Exception as e:
            logger.error(f"Error updating positions: {e}")

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
        """Calculate custom entry dengan TP/SL"""
        try:
            detected_type, formatted_symbol = auto_detect_trading_type(symbol)
            
            # Get data menggunakan get_trading_data jika tersedia
            if get_trading_data is not None:
                df = get_trading_data(formatted_symbol, self.data_provider)
            else:
                df = self.data_provider.get_ohlcv(formatted_symbol, self.config.get("timeframe", "1h"), 50)
            
            if df is None or len(df) < 20:
                # Fallback calculation
                return {
                    'symbol': formatted_symbol,
                    'detected_type': detected_type,
                    'entry_price': entry_price,
                    'tp1': entry_price * 1.03,
                    'tp2': entry_price * 1.06,
                    'tp3': entry_price * 1.09,
                    'sl': entry_price * 0.97
                }
            
            # Pilih strategi
            if detected_type == "futures":
                strategy = self._create_futures_strategy()
            else:
                strategy = self._create_spot_strategy()
            
            # Calculate menggunakan strategy
            analysis = strategy.analyze(df)
            if analysis and 'tp1' in analysis and 'sl' in analysis:
                return {
                    'symbol': formatted_symbol,
                    'detected_type': detected_type,
                    'entry_price': entry_price,
                    'tp1': analysis['tp1'],
                    'tp2': analysis['tp2'],
                    'tp3': analysis['tp3'],
                    'sl': analysis['sl']
                }
            
            # Fallback
            return {
                'symbol': formatted_symbol,
                'detected_type': detected_type,
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
                'detected_type': 'spot',
                'entry_price': entry_price,
                'tp1': entry_price * 1.03,
                'tp2': entry_price * 1.06,
                'tp3': entry_price * 1.09,
                'sl': entry_price * 0.97
            }

    def get_provider_health(self):
        """Get provider health information"""
        if not hasattr(self, 'data_provider'):
            return {'status': 'no_provider', 'type': 'unknown'}
        
        try:
            # Untuk SmartChainDataProvider
            if hasattr(self.data_provider, 'get_health_status'):
                health = self.data_provider.get_health_status()
                health['provider_type'] = 'smart_chain'
                health['provider_class'] = self.data_provider.__class__.__name__
                return health
            
            # Untuk UnifiedDataProvider
            elif hasattr(self.data_provider, 'get_health_metrics'):
                health = self.data_provider.get_health_metrics()
                health['provider_type'] = 'unified'
                health['provider_class'] = self.data_provider.__class__.__name__
                return health
            
            # Untuk EnhancedCCXTDataProvider
            elif hasattr(self.data_provider, 'get_health_metrics'):
                health = self.data_provider.get_health_metrics()
                health['provider_type'] = 'ccxt'
                health['provider_class'] = self.data_provider.__class__.__name__
                return health
            
            # Untuk EnhancedYFinanceDataProvider
            elif hasattr(self.data_provider, 'get_health_metrics'):
                health = self.data_provider.get_health_metrics()
                health['provider_type'] = 'yfinance'
                health['provider_class'] = self.data_provider.__class__.__name__
                return health
            
            # Fallback
            else:
                return {
                    'provider_type': 'unknown',
                    'provider_class': self.data_provider.__class__.__name__,
                    'status': 'active' if self.data_provider else 'inactive'
                }
                
        except Exception as e:
            logger.error(f"Error getting provider health: {e}")
            return {'status': 'error', 'error': str(e)}

    # =============================================
    # SET MODE METHOD (SIMPLIFIED)
    # =============================================

    def set_mode(self, mode):
        """Set trading mode dengan universal provider"""
        try:
            self.mode = mode.lower()
            
            # Stop existing tasks
            self.stop_background_tasks()
            
            logger.info(f"🎯 Setting market mode to: {self.mode.upper()}")
            
            # Update provider dengan mode baru
            logger.info(f"🔄 Reconfiguring UniversalProvider for {self.mode}...")
            
            try:
                # Update config
                self.config["market_type"] = self.mode
                
                # Reinitialize provider
                self._setup_universal_provider()
                
                # Setup strategy
                if create_strategy_for_symbol is not None:
                    sample_symbol = "BTC/USDT" if self.mode == 'crypto' else "AAPL" if self.mode == 'us_stocks' else "BBCA.JK"
                    
                    try:
                        self.strategy = create_strategy_for_symbol(
                            sample_symbol,
                            market_type=self.mode
                        )
                        logger.info(f"✅ Created auto-detected strategy for {self.mode}")
                    except Exception as e:
                        logger.warning(f"⚠️ Auto strategy creation failed: {e}, falling back to TechnicalAnalysisStrategy")
                        self.strategy = TechnicalAnalysisStrategy(
                            market_type=self.mode,
                            trading_type="spot",
                            atr_multiplier=self.config.get("atr_multiplier", 1.0),
                            entry_range_pct=self.config.get("entry_range_pct", 0.02),
                        )
                else:
                    self.strategy = TechnicalAnalysisStrategy(
                        market_type=self.mode,
                        trading_type="spot",
                        atr_multiplier=self.config.get("atr_multiplier", 1.0),
                        entry_range_pct=self.config.get("entry_range_pct", 0.02),
                    )
                
                # Test provider connection
                test_assets = self._test_provider_connection()
                
                if test_assets:
                    logger.info(f"✅ Provider ready for {self.mode}")
                    logger.info(f"📋 Sample assets: {test_assets[:3]}")
                    
                    # Start background tasks
                    self.start_background_tasks()
                    return True
                else:
                    logger.warning(f"⚠️ Provider test returned no assets, but continuing...")
                    self.start_background_tasks()
                    return True
                    
            except Exception as e:
                logger.error(f"❌ Failed to configure provider: {e}")
                logger.error(traceback.format_exc())
                return False
                
        except Exception as e:
            logger.error(f"Error setting mode {mode}: {e}")
            return False

    def _test_provider_connection(self):
        """Test provider connection"""
        try:
            logger.info("🧪 Testing UniversalProvider connection...")
            logger.info(f"  Provider: {self.data_provider.__class__.__name__}")
            
            # Get popular assets
            assets = self.get_popular_assets(5)
            
            if not assets:
                logger.warning("⚠️ No assets returned from provider")
                return []
            
            # Format asset symbols
            asset_symbols = []
            for asset in assets[:5]:
                symbol = asset.get('symbol', 'Unknown')
                detected_type = asset.get('detected_type', 'spot')
                asset_symbols.append(f"{symbol} ({detected_type})")
            
            # Test OHLCV untuk asset pertama menggunakan get_trading_data
            if assets:
                test_symbol = assets[0].get('formatted_symbol', assets[0].get('symbol'))
                logger.info(f"  Testing OHLCV for: {test_symbol}")
                
                # Gunakan get_trading_data jika tersedia untuk membersihkan data
                if get_trading_data is not None:
                    logger.info(f"    🔧 Menggunakan get_trading_data")
                    df = get_trading_data(test_symbol, self.data_provider)
                else:
                    logger.info(f"    🔧 Menggunakan provider {self.data_provider.__class__.__name__}")
                    df = self.data_provider.get_ohlcv(test_symbol, '1h', 10)
                
                # Validasi data dengan debug mode
                if df is not None and len(df) > 0:
                    is_valid, msg = self.validate_market_data(df, test_symbol, debug_mode=True)
                    if is_valid:
                        logger.info(f"  ✅ OHLCV data: {len(df)} bars (valid)")
                    else:
                        logger.warning(f"  ⚠️ OHLCV data validation failed: {msg}")
                else:
                    logger.warning("  ⚠️ No OHLCV data, but continuing...")
            
            return asset_symbols
            
        except Exception as e:
            logger.warning(f"⚠️ Provider test had issues: {e}")
            return []

# =============================================
# TRADING CORE - SIMPLIFIED VERSION
# =============================================

class TradingCore:
    """Main trading engine dengan universal provider"""
    
    def __init__(self, config=None):
        self.config = config or {}
        
        # Setup universal data provider
        self.data_provider = self._setup_data_provider()
        
        # Setup trading mode
        self.trading_type = self.config.get("trading_mode", "spot")
        
        # Setup strategy
        try:
            if create_strategy_for_symbol is not None:
                sample_symbol = "BTC/USDT" if self.config.get("market_type", "crypto") == "crypto" else "AAPL"
                
                self.strategy = create_strategy_for_symbol(
                    sample_symbol,
                    market_type=self.config.get("market_type", "crypto"),
                    trading_mode=self.trading_type
                )
                logger.info(f"✅ Created auto-detected strategy untuk {self.config.get('market_type', 'crypto')} ({self.trading_type})")
            else:
                from strategies import TechnicalAnalysisStrategy
                self.strategy = TechnicalAnalysisStrategy(
                    market_type=self.config.get("market_type", "crypto"),
                    trading_type=self.trading_type,
                    atr_multiplier=self.config.get("atr_multiplier", 1.0),
                    entry_range_pct=self.config.get("entry_range_pct", 0.02)
                )
                logger.info(f"✅ Menggunakan TechnicalAnalysisStrategy untuk {self.config.get('market_type', 'crypto')} ({self.trading_type})")
        except ImportError as e:
            print(f"❌ Gagal import strategies di TradingCore: {e}")
            class DummyStrategy:
                def analyze(self, *args, **kwargs):
                    return {'action': 'NEUTRAL', 'score': 0}
            self.strategy = DummyStrategy()
        
        logger.info(f"🚀 TradingCore initialized | Mode: {self.trading_type}")
    
    def _setup_data_provider(self):
        """Setup universal data provider"""
        try:
            # Gunakan provider berdasarkan market type
            market_type = self.config.get("market_type", "crypto")
            
            if market_type == 'crypto':
                # Coba CCXT terlebih dahulu
                if EnhancedCCXTDataProvider:
                    provider = EnhancedCCXTDataProvider(
                        exchange_id='binance',
                        api_key='',
                        secret=''
                    )
                    logger.info("✅ Using CCXT (Binance) for crypto data")
                    return provider
                else:
                    # Fallback ke YFinance
                    if EnhancedYFinanceDataProvider:
                        provider = EnhancedYFinanceDataProvider()
                        logger.info("✅ Using YFinance for crypto (fallback)")
                        return provider
            
            elif market_type in ['us_stocks', 'saham_id', 'forex']:
                # Untuk stocks/forex, gunakan YFinance
                if EnhancedYFinanceDataProvider:
                    provider = EnhancedYFinanceDataProvider()
                    logger.info(f"✅ Using YFinance for {market_type}")
                    return provider
            
            # Default ke UnifiedDataProvider jika ada
            if UnifiedDataProvider:
                provider = UnifiedDataProvider(
                    market_type=self.config.get("market_type", "crypto"),
                    trading_mode=self.config.get("trading_mode", "spot"),
                    default_exchange=self.config.get("default_exchange", "binance")
                )
                logger.info(f"✅ Using UnifiedDataProvider with {provider.active_exchange}")
                return provider
            
            raise Exception("No provider available")
            
        except Exception as e:
            logger.error(f"❌ Failed to setup universal provider: {e}")
            # Last resort: create simple provider
            class SimpleProvider:
                def __init__(self, *args, **kwargs):
                    pass
                def get_ohlcv(self, *args, **kwargs):
                    return pd.DataFrame()
                def get_ticker(self, *args, **kwargs):
                    return {'last': 0}
                def get_popular_assets(self, *args, **kwargs):
                    return []
            return SimpleProvider()
    
    def set_mode(self, market_type):
        """Set trading mode dengan update provider"""
        try:
            self.config["market_type"] = market_type
            
            # Update provider dengan mode baru
            self.data_provider.market_type = market_type
            self.data_provider.trading_mode = self.trading_type
            
            # Reinitialize jika perlu
            if hasattr(self.data_provider, '_initialize_providers_with_smart_fallback'):
                self.data_provider._initialize_providers_with_smart_fallback()
            
            logger.info(f"✅ Market mode set to: {market_type}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to set mode: {e}")
            return False
    
    def set_trading_mode(self, trading_mode):
        """Set spot/futures mode"""
        valid_modes = ['spot', 'future', 'futures']
        
        if trading_mode.lower() not in valid_modes:
            logger.error(f"Invalid trading mode: {trading_mode}")
            return False
        
        self.trading_type = trading_mode.lower()
        self.config["trading_mode"] = self.trading_type
        
        # Update provider
        if hasattr(self.data_provider, 'trading_mode'):
            self.data_provider.trading_mode = self.trading_type
            logger.info(f"✅ Trading mode updated in provider: {self.trading_type}")
        
        logger.info(f"✅ Trading mode set to: {self.trading_type}")
        return True
    
    def scan_market(self, scan_type="standard", limit=50):
        """Scan market dengan universal provider"""
        try:
            logger.info(f"🔍 Scanning {self.trading_type} market ({scan_type})...")
            
            # Get assets
            assets = self.data_provider.get_popular_assets(limit=limit)
            
            if not assets:
                logger.error("❌ No assets found for scanning")
                return []
            
            logger.info(f"📊 Found {len(assets)} assets for scanning")
            
            # Proses scanning...
            results = []
            for asset in assets[:20]:
                symbol = asset['symbol'] if isinstance(asset, dict) else asset
                
                try:
                    # Get data menggunakan get_trading_data jika tersedia
                    if get_trading_data is not None:
                        df = get_trading_data(symbol, self.data_provider)
                    else:
                        df = self.data_provider.get_ohlcv(
                            symbol=symbol,
                            timeframe=self.config.get("timeframe", "1h"),
                            limit=200
                        )
                    
                    if df is None or df.empty:
                        continue
                    
                    # Analisis dengan strategy
                    signal = self.strategy.analyze(df, symbol)
                    
                    if signal and signal.get('action') != 'hold':
                        results.append({
                            'symbol': symbol,
                            'signal': signal,
                            'price': df['close'].iloc[-1] if len(df) > 0 else 0,
                            'data_points': len(df)
                        })
                        
                except Exception as e:
                    logger.debug(f"❌ Failed to analyze {symbol}: {e}")
                    continue
            
            logger.info(f"✅ Scan complete: {len(results)} signals found")
            return results
            
        except Exception as e:
            logger.error(f"❌ Market scan failed: {e}")
            return []
    
    def get_health_status(self):
        """Get health status dari provider"""
        try:
            if hasattr(self.data_provider, 'get_health_metrics'):
                return self.data_provider.get_health_metrics()
            else:
                return {'status': 'unknown', 'provider': type(self.data_provider).__name__}
        except Exception as e:
            return {'status': 'error', 'error': str(e)}

# =============================================
# BACKWARD COMPATIBILITY
# =============================================

TradingBot = EnhancedTradingBot

# =============================================
# TESTING FUNCTIONALITY
# =============================================

def test_universal_provider():
    """Test bot dengan universal provider"""
    print("🧪 Testing TradingBot dengan UNIVERSAL PROVIDER...")
    print("="*60)
    
    bot = EnhancedTradingBot()
    
    # Test crypto market
    print("\n1. Testing CRYPTO market...")
    success = bot.set_mode("crypto")
    
    if success:
        print("✅ Crypto mode set successfully")
        
        # Test popular assets
        assets = bot.get_popular_assets(10)
        print(f"   Found {len(assets)} assets")
        for asset in assets[:5]:
            print(f"   - {asset['symbol']} ({asset.get('detected_type', 'N/A')})")
        
        # Test scanning
        print("\n2. Testing scanning...")
        signals = bot.scan_potential_assets(limit=10)
        print(f"   Found {len(signals)} signals")
        
        if signals:
            for i, signal in enumerate(signals[:10]):
                print(f"   {i+1}. {signal['symbol']}: {signal['action']} (Score: {signal['score']}, Type: {signal.get('trading_mode', 'N/A')}, Leverage: {signal.get('leverage', 1)}x)")
        else:
            print("   ℹ️ No signals found - this is normal with real data")
    
    # Test saham_id
    print("\n3. Testing SAHAM_ID market...")
    success = bot.set_mode("saham_id")
    
    if success:
        print("✅ Saham ID mode set successfully")
        
        # Test popular assets saham_id
        assets = bot.get_popular_assets(10)
        print(f"   Found {len(assets)} Indonesian stocks")
        for asset in assets[:5]:
            print(f"   - {asset['symbol']} ({asset.get('name', 'N/A')}) ({asset.get('detected_type', 'N/A')})")
        
        # Test scanning saham_id
        print("\n4. Testing scanning SAHAM_ID...")
        signals = bot.scan_potential_assets(limit=10)
        print(f"   Found {len(signals)} Indonesian stock signals")
        
        if signals:
            for i, signal in enumerate(signals[:10]):
                print(f"   {i+1}. {signal['symbol']}: {signal['action']} (Score: {signal['score']})")
        else:
            print("   ℹ️ No Indonesian stock signals found - this is normal with real data")
    
    print("\n" + "="*60)
    print("✅ Test completed - Bot menggunakan Universal Provider dengan auto-detection")
    print("   Auto-detect spot/futures dari simbol")
    print("   Leverage auto-detection (1x untuk spot, 5x untuk futures)")
    print("   Menggunakan get_trading_data untuk membersihkan data")

def test_data_cleaner_integration():
    """Test integrasi data cleaner di core.py"""
    print("\n" + "="*60)
    print("TESTING DATA CLEANER INTEGRATION")
    print("="*60)
    
    bot = EnhancedTradingBot()
    
    # Test symbols yang bermasalah
    test_symbols = ["BONK/USDT:USDT", "CATI/USDT:USDT", "100MAD/USDT", "BTC/USDT", "ETH/USDT"]
    
    for symbol in test_symbols:
        print(f"\n🔍 Testing {symbol} dengan get_trading_data")
        
        if get_trading_data is not None:
            data = get_trading_data(symbol, bot.data_provider)
            if data is not None and not data.empty:
                print(f"   ✅ Clean data: {len(data)} bars")
                if 'close' in data.columns:
                    current_price = data['close'].iloc[-1]
                    print(f"   📊 Current price: ${current_price:.6f}")
                    
                    # Cek apakah ada harga 100
                    if (abs(data['close'] - 100.0) < 0.001).any():
                        print(f"   ⚠️ WARNING: Still has price 100!")
                    else:
                        print(f"   👍 No price 100 detected")
            else:
                print(f"   ❌ get_trading_data returned None atau empty")
        else:
            print(f"   ℹ️ get_trading_data not available")
    
    # Test scan dengan symbols bermasalah
    print("\n🧪 Testing scanning dengan symbols bermasalah...")
    
    bot.set_mode("crypto")
    
    # Test beberapa simbol
    test_assets = [
        {'symbol': 'BONK/USDT:USDT', 'name': 'Bonk'},
        {'symbol': 'CATI/USDT:USDT', 'name': 'Cati'},
        {'symbol': 'BTC/USDT', 'name': 'Bitcoin'},
        {'symbol': 'ETH/USDT', 'name': 'Ethereum'},
    ]
    
    for asset in test_assets:
        print(f"\n🔍 Processing {asset['symbol']}")
        
        # Auto-detect type
        detected_type, formatted_symbol = auto_detect_trading_type(asset['symbol'])
        print(f"   Detected type: {detected_type}")
        
        if get_trading_data is not None:
            data = get_trading_data(formatted_symbol, bot.data_provider)
            if data is None or data.empty:
                print(f"   ❌ Data tidak valid, akan di-skip")
            else:
                print(f"   ✅ Data valid: {len(data)} bars")
                print(f"   📊 Price range: ${data['close'].min():.6f} - ${data['close'].max():.6f}")
                
                # Validasi data
                is_valid, msg = bot.validate_market_data(data, asset['symbol'], debug_mode=True)
                if is_valid:
                    print(f"   👍 Data validation passed")
                else:
                    print(f"   ⚠️ Data validation failed: {msg}")

if __name__ == "__main__":
    test_universal_provider()
    test_data_cleaner_integration()
    
    print("\n" + "="*60)
    print("🎯 CORE.PY READY WITH UNIVERSAL PROVIDER")
    print("🎯 Menggunakan get_trading_data untuk membersihkan data")
    print("🎯 Auto-detect spot/futures dari simbol")
    print("🎯 Leverage auto-detection (1x spot, 5x futures)")
    print("🎯 Provider universal (CCXT untuk crypto, YFinance untuk stocks/forex)")
    print("🎯 SmartChainDataProvider sebagai prioritas utama")
    print("="*60)
