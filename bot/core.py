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
        features = {}
        
        # Price-based features
        features['price_change_1d'] = (df['close'].iloc[-1] - df['close'].iloc[-2]) / df['close'].iloc[-2]
        features['price_change_5d'] = (df['close'].iloc[-1] - df['close'].iloc[-6]) / df['close'].iloc[-6]
        features['volatility'] = df['close'].pct_change().std()
        
        # Volume features
        features['volume_ratio'] = df['volume'].iloc[-1] / df['volume'].rolling(20).mean().iloc[-1]
        
        # Technical indicators
        features['rsi'] = self._calculate_rsi(df['close'])
        features['macd'] = self._calculate_macd(df['close'])
        
        return pd.DataFrame([features])
    
    def _calculate_rsi(self, prices, period=14):
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs)).iloc[-1]
    
    def _calculate_macd(self, prices):
        exp1 = prices.ewm(span=12).mean()
        exp2 = prices.ewm(span=26).mean()
        return (exp1 - exp2).iloc[-1]

class BacktestEngine:
    """Advanced backtesting engine"""
    def __init__(self, initial_balance=10000):
        self.initial_balance = initial_balance
        self.results = {}
        
    def run_backtest(self, df, strategy, **kwargs):
        """Run comprehensive backtest"""
        balance = self.initial_balance
        position = 0
        trades = []
        equity_curve = []
        
        for i in range(50, len(df)):
            current_data = df.iloc[:i]
            analysis = strategy.analyze(current_data)
            
            if analysis and analysis['action'] in ['LONG', 'SHORT']:
                # Simulate trading logic
                entry_price = df['close'].iloc[i]
                
                if position == 0:  # No position, consider entry
                    if self._should_enter_trade(analysis, df['close'].iloc[i]):
                        position = 1 if analysis['action'] == 'LONG' else -1
                        entry_trade = {
                            'entry_time': df.index[i],
                            'entry_price': entry_price,
                            'action': analysis['action'],
                            'size': balance * 0.1 / entry_price  # 10% position
                        }
                        trades.append(entry_trade)
                
                elif position != 0:  # Have position, check exit
                    if self._should_exit_trade(entry_trade, df['close'].iloc[i], analysis):
                        exit_price = df['close'].iloc[i]
                        pnl = (exit_price - entry_trade['entry_price']) * entry_trade['size'] * position
                        balance += pnl
                        
                        entry_trade.update({
                            'exit_time': df.index[i],
                            'exit_price': exit_price,
                            'pnl': pnl
                        })
                        position = 0
            
            equity_curve.append(balance)
        
        self.results = self._calculate_performance_metrics(trades, equity_curve)
        return self.results
    
    def _should_enter_trade(self, analysis, current_price):
        """Enhanced entry logic"""
        if analysis['score'] >= 3 and analysis['risk_metrics']['reward_ratio'] > 1.5:
            return True
        return False
    
    def _should_exit_trade(self, trade, current_price, analysis):
        """Enhanced exit logic"""
        if trade['action'] == 'LONG':
            if current_price >= trade['entry_price'] * 1.05:  # 5% profit
                return True
            if current_price <= trade['entry_price'] * 0.98:  # 2% stop loss
                return True
        return False
    
    def _calculate_performance_metrics(self, trades, equity_curve):
        """Calculate comprehensive performance metrics"""
        if not trades:
            return {}
            
        winning_trades = [t for t in trades if t.get('pnl', 0) > 0]
        losing_trades = [t for t in trades if t.get('pnl', 0) <= 0]
        
        total_pnl = sum(t.get('pnl', 0) for t in trades)
        win_rate = len(winning_trades) / len(trades) if trades else 0
        
        # Sharpe Ratio (simplified)
        returns = np.diff(equity_curve) / equity_curve[:-1]
        sharpe_ratio = np.mean(returns) / np.std(returns) * np.sqrt(252) if len(returns) > 1 else 0
        
        # Max Drawdown
        peak = np.maximum.accumulate(equity_curve)
        drawdown = (equity_curve - peak) / peak
        max_drawdown = np.min(drawdown)
        
        return {
            'total_trades': len(trades),
            'winning_trades': len(winning_trades),
            'losing_trades': len(losing_trades),
            'win_rate': win_rate,
            'total_pnl': total_pnl,
            'sharpe_ratio': sharpe_ratio,
            'max_drawdown': max_drawdown,
            'final_balance': equity_curve[-1] if equity_curve else self.initial_balance
        }

class EnhancedTradingBot(TradingBot):
    """Enhanced TradingBot with ML and Backtesting"""
    
    def __init__(self, config_path="config/config.json"):
        super().__init__(config_path)
        
        # PHASE 2 Enhancements
        self.ml_bot = MLEnhancedBot()
        self.backtest_engine = BacktestEngine()
        self.portfolio_optimizer = PortfolioOptimizer()
        
    def analyze_with_ml(self, symbol):
        """Analyze asset with ML enhancement"""
        if not self.data_provider:
            return None
            
        try:
            df = self.data_provider.get_ohlcv(
                symbol, self.timeframe, self.config.get("ohlcv_limit", 200)
            )
            
            if df is not None and len(df) >= 50:
                # Traditional analysis
                traditional_analysis = self.strategy.analyze(df)
                
                # ML features
                ml_features = self.ml_bot.extract_features(df)
                
                # Combine analyses
                enhanced_analysis = self._combine_analyses(traditional_analysis, ml_features)
                
                # Portfolio optimization
                portfolio_recommendation = self.portfolio_optimizer.optimize_position(
                    enhanced_analysis, self.get_active_positions()
                )
                
                enhanced_analysis['portfolio_recommendation'] = portfolio_recommendation
                enhanced_analysis['symbol'] = symbol
                enhanced_analysis['market_type'] = self.mode
                
                self.db.save_signal(enhanced_analysis)
                return enhanced_analysis
                
        except Exception as e:
            print(f"ML-enhanced analysis error for {symbol}: {e}")
            return None
    
    def _combine_analyses(self, traditional_analysis, ml_features):
        """Combine traditional and ML analysis"""
        if not traditional_analysis:
            return None
            
        # Enhance confidence with ML
        ml_confidence = self._calculate_ml_confidence(ml_features)
        traditional_analysis['ml_confidence'] = ml_confidence
        traditional_analysis['combined_score'] = traditional_analysis['final_score'] * ml_confidence
        
        return traditional_analysis
    
    def _calculate_ml_confidence(self, ml_features):
        """Calculate ML-based confidence score"""
        # Simplified ML confidence calculation
        # In real implementation, this would use a trained model
        volatility = ml_features['volatility'].iloc[0] if 'volatility' in ml_features else 0.02
        volume_ratio = ml_features['volume_ratio'].iloc[0] if 'volume_ratio' in ml_features else 1
        
        # Higher confidence for moderate volatility and high volume
        if 0.01 < volatility < 0.05 and volume_ratio > 1.2:
            return 1.2  # Boost confidence
        elif volatility > 0.1:
            return 0.8  # Reduce confidence for high volatility
        else:
            return 1.0  # Neutral
    
    def run_comprehensive_backtest(self, symbol, days=365):
        """Run comprehensive backtest for a symbol"""
        try:
            # Get historical data
            df = self._get_historical_data(symbol, days)
            
            if df is None or len(df) < 100:
                return {"error": "Insufficient historical data"}
            
            # Run backtest
            results = self.backtest_engine.run_backtest(df, self.strategy)
            
            # Add symbol info
            results['symbol'] = symbol
            results['period_days'] = days
            results['test_date'] = datetime.now().isoformat()
            
            # Save backtest results
            self._save_backtest_results(results)
            
            return results
            
        except Exception as e:
            print(f"Backtest error for {symbol}: {e}")
            return {"error": str(e)}
    
    def _get_historical_data(self, symbol, days):
        """Get historical data for backtesting"""
        # This would need to be implemented based on your data provider
        # For now, return current OHLCV data as placeholder
        return self.data_provider.get_ohlcv(
            symbol, "1d", days
        )
    
    def _save_backtest_results(self, results):
        """Save backtest results to database"""
        # Implement database saving for backtest results
        pass
    
    def optimize_portfolio_allocation(self, signals, total_capital=10000):
        """Optimize portfolio allocation across multiple signals"""
        return self.portfolio_optimizer.optimize_allocations(signals, total_capital)
    
    def get_risk_assessment(self, symbol):
        """Get comprehensive risk assessment for a symbol"""
        analysis = self.analyze_asset(symbol)
        if analysis and 'risk_metrics' in analysis:
            return {
                'symbol': symbol,
                'risk_category': analysis['risk_metrics']['risk_category'],
                'optimal_position_size': analysis['risk_metrics']['optimal_position_size'],
                'reward_ratio': analysis['risk_metrics']['reward_ratio'],
                'volatility_level': analysis['market_regime']['volatility_level'],
                'recommendation': self._generate_risk_recommendation(analysis)
            }
        return None
    
    def _generate_risk_recommendation(self, analysis):
        """Generate risk-based trading recommendation"""
        risk_category = analysis['risk_metrics']['risk_category']
        score = analysis['final_score']
        
        if risk_category == 'HIGH' and score > 3:
            return "CAUTION: High risk but strong signal - consider smaller position"
        elif risk_category == 'LOW' and score > 2:
            return "GOOD: Low risk with positive signal"
        elif risk_category == 'MEDIUM' and score > 1:
            return "MODERATE: Medium risk with acceptable signal"
        else:
            return "AVOID: Risk-reward not favorable"

class PortfolioOptimizer:
    """Portfolio optimization engine"""
    
    def __init__(self):
        self.correlation_matrix = {}
    
    def optimize_position(self, analysis, existing_positions):
        """Optimize position size based on portfolio context"""
        if not analysis:
            return {}
            
        base_size = analysis['risk_metrics']['optimal_position_size']
        
        # Adjust based on correlation with existing positions
        correlation_penalty = self._calculate_correlation_penalty(analysis['symbol'], existing_positions)
        adjusted_size = base_size * (1 - correlation_penalty)
        
        return {
            'base_position_size': base_size,
            'adjusted_position_size': adjusted_size,
            'correlation_penalty': correlation_penalty,
            'recommended_size': min(adjusted_size, 0.15)  # Cap at 15%
        }
    
    def _calculate_correlation_penalty(self, symbol, existing_positions):
        """Calculate position size penalty based on correlation"""
        if not existing_positions:
            return 0
            
        # Simplified correlation logic
        # In real implementation, calculate actual correlation
        num_positions = len(existing_positions)
        return min(0.3, num_positions * 0.05)  # 5% penalty per existing position
    
    def optimize_allocations(self, signals, total_capital):
        """Optimize capital allocation across multiple signals"""
        if not signals:
            return {}
            
        # Calculate scores and risk metrics
        scored_signals = []
        for signal in signals:
            score = signal.get('final_score', 0)
            risk_category = signal['risk_metrics']['risk_category']
            base_allocation = signal['risk_metrics']['optimal_position_size']
            
            # Adjust allocation based on risk and score
            risk_multiplier = 1.0 if risk_category == 'LOW' else 0.7 if risk_category == 'MEDIUM' else 0.4
            score_multiplier = 1.0 + (score - 1) * 0.1  # 10% boost per score point above 1
            
            final_allocation = base_allocation * risk_multiplier * score_multiplier
            scored_signals.append({
                'symbol': signal['symbol'],
                'score': score,
                'risk_category': risk_category,
                'allocation_percent': final_allocation,
                'allocated_capital': total_capital * final_allocation
            })
        
        # Normalize allocations to not exceed 100%
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

# Replace the original TradingBot with enhanced version
TradingBot = EnhancedTradingBot
