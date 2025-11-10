import os
import time
import json
import warnings
from datetime import datetime
import threading
import schedule
import pandas as pd
import numpy as np
from dotenv import load_dotenv
from .strategies import TechnicalAnalysisStrategy
from .data_provider import (
    CCXTDataProvider,
    YFinanceDataProvider,
    SolanaPumpFunProvider
)
from .notifier import SoundNotifier
from database.db_handler import DatabaseHandler

warnings.filterwarnings("ignore")
load_dotenv()

class MLEnhancedBot:
    """Machine Learning enhanced trading bot"""
    def __init__(self):
        self.model = None
        self.is_trained = False
        
    def extract_features(self, df):
        """Extract features for ML model"""
        try:
            features = {}
            
            if df is None or len(df) == 0:
                return pd.DataFrame([features])
                
            if len(df) > 1:
                features['price_change_1d'] = (df['close'].iloc[-1] - df['close'].iloc[-2]) / df['close'].iloc[-2] if df['close'].iloc[-2] != 0 else 0
            else:
                features['price_change_1d'] = 0
                
            if len(df) > 6:
                features['price_change_5d'] = (df['close'].iloc[-1] - df['close'].iloc[-6]) / df['close'].iloc[-6] if df['close'].iloc[-6] != 0 else 0
            else:
                features['price_change_5d'] = 0
                
            features['volatility'] = df['close'].pct_change().std() if len(df) > 1 else 0.02
            
            vol_mean = df['volume'].rolling(20).mean().iloc[-1] if len(df) >= 20 else df['volume'].mean()
            features['volume_ratio'] = df['volume'].iloc[-1] / vol_mean if vol_mean > 0 else 1
            
            features['rsi'] = self._calculate_rsi(df['close'])
            features['macd'] = self._calculate_macd(df['close'])
            
            return pd.DataFrame([features])
        except Exception as e:
            print(f"Error extracting features: {e}")
            return pd.DataFrame([{}])
    
    def _calculate_rsi(self, prices, period=14):
        try:
            if len(prices) < period + 1:
                return 50
            delta = prices.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            rs = gain / loss
            return 100 - (100 / (1 + rs)).iloc[-1] if not np.isnan(rs.iloc[-1]) and loss.iloc[-1] != 0 else 50
        except:
            return 50
    
    def _calculate_macd(self, prices):
        try:
            if len(prices) < 26:
                return 0
            exp1 = prices.ewm(span=12).mean()
            exp2 = prices.ewm(span=26).mean()
            return (exp1 - exp2).iloc[-1]
        except:
            return 0

class BacktestEngine:
    """Enhanced backtesting engine with advanced features"""
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
        if analysis.get('score', 0) >= 2 and analysis.get('risk_metrics', {}).get('reward_ratio', 0) > 1.5:
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

    def scan_potential_assets(self, limit=None):
        """Scan potential assets dengan error handling yang lebih baik"""
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
                    analysis = self.analyze_asset(asset)
                    
                    if analysis:
                        if analysis.get("action") in ["LONG", "SHORT"] and analysis.get("score", 0) >= self.config.get("min_score", 3):
                            results.append(analysis)
                            successful_analysis += 1
                            print(f"    ✅ Signal found: {analysis['action']} (Score: {analysis['score']})")
                        else:
                            print(f"    ⚠️ No trade signal (Action: {analysis.get('action')}, Score: {analysis.get('score')})")
                    else:
                        failed_analysis += 1
                        print(f"    ❌ Analysis failed for {asset}")
                        
                except Exception as e:
                    failed_analysis += 1
                    print(f"    ❌ Error analyzing {asset}: {str(e)}")
                
                # Delay untuk menghindari rate limit
                time.sleep(self.config.get("scan_delay", 0.5))
            
            # Urutkan berdasarkan score dan ambil yang terbaik
            results.sort(key=lambda x: x.get('score', 0), reverse=True)
            max_signals = self.config.get("max_signals", 10)
            final_results = results[:max_signals]
            
            print(f"📊 Scan complete: {successful_analysis} successful, {failed_analysis} failed, {len(final_results)} signals found")
            return final_results
            
        except Exception as e:
            print(f"❌ Error in scan_potential_assets: {e}")
            return []
        finally:
            self.scanning_in_progress = False

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

    def calculate_custom_entry(self, symbol, entry_price):
        """Calculate custom entry dengan TP/SL dan probabilitas"""
        if not self.data_provider:
            print("No data provider for custom entry.")
            return None
        try:
            df = self.data_provider.get_ohlcv(
                symbol, self.timeframe, self.config.get("ohlcv_limit", 200)
            )
            if df is not None and len(df) >= 20:
                atr = self.strategy.calculate_atr(df)
                
                # Calculate raw TP levels
                raw_tp1 = entry_price + atr * self.strategy.atr_multiplier
                raw_tp2 = entry_price + atr * self.strategy.atr_multiplier * 2
                raw_tp3 = entry_price + atr * self.strategy.atr_multiplier * 3
                sl = entry_price - atr * self.strategy.atr_multiplier
                
                # ✅ FIXED: Sort TP levels for LONG (ascending)
                tp1, tp2, tp3 = sorted([raw_tp1, raw_tp2, raw_tp3])
                
                # Calculate TP probabilities
                tp_probabilities = self.strategy.calculate_tp_probability(
                    entry_price, tp1, tp2, tp3, sl, "LONG"
                )
                
                return {
                    "symbol": symbol,
                    "entry_price": float(entry_price),
                    "tp1": float(tp1),
                    "tp2": float(tp2),
                    "tp3": float(tp3),
                    "sl": float(sl),
                    "tp_probabilities": tp_probabilities  # ✅ NEW: TP probabilities
                }
            print(f"Insufficient data for ATR calculation on {symbol}")
            return None
        except Exception as e:
            print(f"Error calculating custom entry for {symbol}: {e}")
            return None

    def get_active_positions(self):
        try:
            positions = self.db.get_active_positions(self.mode)
            for position in positions:
                symbol = position[1]
                try:
                    ticker = self.data_provider.get_ticker(symbol)
                    if ticker and 'last' in ticker:
                        self.db.update_position_current_price(symbol, ticker['last'])
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
