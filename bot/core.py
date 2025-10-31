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
    
    def _calculate_rsi(self, prices, period=14):
        if len(prices) < period + 1:
            return 50
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs)).iloc[-1] if not np.isnan(rs.iloc[-1]) and loss.iloc[-1] != 0 else 50
    
    def _calculate_macd(self, prices):
        if len(prices) < 26:
            return 0
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
        equity_curve = [balance]
        
        if len(df) < 100:
            return self._get_empty_results()
        
        for i in range(50, len(df)):
            current_data = df.iloc[:i+1]
            analysis = strategy.analyze(current_data)
            
            if analysis and analysis['action'] in ['LONG', 'SHORT']:
                current_price = df['close'].iloc[i]
                
                if position == 0:
                    if self._should_enter_trade(analysis, current_price):
                        position = 1 if analysis['action'] == 'LONG' else -1
                        entry_trade = {
                            'entry_time': df.index[i] if hasattr(df.index, 'iloc') else i,
                            'entry_price': current_price,
                            'action': analysis['action'],
                            'size': balance * 0.1 / current_price
                        }
                        trades.append(entry_trade)
                
                elif position != 0:
                    current_trade = trades[-1]
                    if self._should_exit_trade(current_trade, current_price, analysis):
                        exit_price = current_price
                        pnl = (exit_price - current_trade['entry_price']) * current_trade['size'] * position
                        balance += pnl
                        
                        current_trade.update({
                            'exit_time': df.index[i] if hasattr(df.index, 'iloc') else i,
                            'exit_price': exit_price,
                            'pnl': pnl
                        })
                        position = 0
            
            equity_curve.append(balance)
        
        self.results = self._calculate_performance_metrics(trades, equity_curve)
        return self.results
    
    def _should_enter_trade(self, analysis, current_price):
        if analysis.get('score', 0) >= 3 and analysis.get('risk_metrics', {}).get('reward_ratio', 0) > 1.5:
            return True
        return False
    
    def _should_exit_trade(self, trade, current_price, analysis):
        if trade['action'] == 'LONG':
            if current_price >= trade['entry_price'] * 1.05:
                return True
            if current_price <= trade['entry_price'] * 0.98:
                return True
        else:
            if current_price <= trade['entry_price'] * 0.95:
                return True
            if current_price >= trade['entry_price'] * 1.02:
                return True
        return False
    
    def _calculate_performance_metrics(self, trades, equity_curve):
        if not trades:
            return self._get_empty_results()
            
        winning_trades = [t for t in trades if t.get('pnl', 0) > 0]
        losing_trades = [t for t in trades if t.get('pnl', 0) <= 0]
        
        total_pnl = sum(t.get('pnl', 0) for t in trades)
        win_rate = len(winning_trades) / len(trades) if trades else 0
        
        if len(equity_curve) > 1:
            returns = np.diff(equity_curve) / equity_curve[:-1]
            if len(returns) > 1 and np.std(returns) > 0:
                sharpe_ratio = np.mean(returns) / np.std(returns) * np.sqrt(252)
            else:
                sharpe_ratio = 0
        else:
            sharpe_ratio = 0
        
        if equity_curve:
            peak = np.maximum.accumulate(equity_curve)
            drawdown = (equity_curve - peak) / peak
            max_drawdown = np.min(drawdown) if len(drawdown) > 0 else 0
        else:
            max_drawdown = 0
        
        return {
            'total_trades': len(trades),
            'winning_trades': len(winning_trades),
            'losing_trades': len(losing_trades),
            'win_rate': win_rate,
            'total_pnl': total_pnl,
            'sharpe_ratio': sharpe_ratio,
            'max_drawdown': max_drawdown,
            'final_balance': equity_curve[-1] if equity_curve else self.initial_balance,
            'equity_curve': equity_curve
        }
    
    def _get_empty_results(self):
        return {
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'win_rate': 0,
            'total_pnl': 0,
            'sharpe_ratio': 0,
            'max_drawdown': 0,
            'final_balance': self.initial_balance,
            'equity_curve': [self.initial_balance]
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
                "analysis_coins_limit": 20,
                "ohlcv_limit": 200,
                "min_score": 3,
                "max_signals": 5,
                "update_interval": 30,
            }
            self.save_config()

    def save_config(self):
        os.makedirs("config", exist_ok=True)
        with open(self.config_path, "w") as f:
            json.dump(self.config, f, indent=4)

    def set_mode(self, mode):
        self.mode = mode.lower()
        if self.mode == "crypto":
            exchange_id = self.config.get("exchange_crypto", "kucoin")
            self.data_provider = CCXTDataProvider(exchange_id, "", "")
            self.pump_provider = SolanaPumpFunProvider(
                os.getenv("SOLANA_RPC", "https://api.mainnet-beta.solana.com")
            )
        elif self.mode == "forex":
            self.data_provider = YFinanceDataProvider(market_type="forex")
        elif self.mode == "saham_id":
            self.data_provider = YFinanceDataProvider(market_type="saham_id")
        else:
            self.data_provider = None
            self.pump_provider = None
            print(f"Invalid mode: {mode}")
            return False

        print(f"Mode set to: {self.mode.upper()} with data provider: {self.data_provider.__class__.__name__}")
        self.start_background_tasks()
        return True

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
        schedule.every(self.config.get("update_interval", 30)).seconds.do(self.update_all_prices)
        schedule.every(5).minutes.do(self.scan_potential_assets)
        
        while not self.stop_scheduler:
            schedule.run_pending()
            time.sleep(1)

    def update_all_prices(self):
        if not self.data_provider:
            return
            
        try:
            active_positions = self.get_active_positions()
            for position in active_positions:
                symbol = position[1]
                try:
                    ticker = self.data_provider.get_ticker(symbol)
                    if ticker and 'last' in ticker:
                        current_price = ticker['last']
                        self.db.update_position_current_price(symbol, current_price)
                        print(f"Updated price for {symbol}: {current_price}")
                except Exception as e:
                    print(f"Error updating price for {symbol}: {e}")
        except Exception as e:
            print(f"Error in update_all_prices: {e}")

    def get_popular_assets(self, limit=None):
        if not self.data_provider:
            print("No data provider available.")
            return []

        limit = limit or self.config.get("analysis_coins_limit", 20)
        try:
            assets = self.data_provider.get_popular_assets(limit)
            if not assets:
                print(f"No popular assets found for {self.mode}")
            return assets
        except Exception as e:
            print(f"Error fetching popular assets: {e}")
            return []

    def scan_potential_assets(self, limit=None):
        if not self.data_provider:
            print("No data provider for scanning.")
            return []

        results = []
        popular_assets = self.get_popular_assets(limit)
        print(f"Scanning {len(popular_assets)} assets for {self.mode}")

        for i, asset in enumerate(popular_assets, 1):
            print(f"Analyzing {i}/{len(popular_assets)}: {asset}")
            try:
                df = self.data_provider.get_ohlcv(
                    asset, self.timeframe, self.config.get("ohlcv_limit", 200)
                )
                if df is None or len(df) < 50:
                    print(f"Insufficient data for {asset}")
                    continue

                analysis = self.strategy.analyze(df)
                if (
                    analysis
                    and analysis["action"] in ["LONG", "SHORT"]
                    and analysis["score"] >= self.config.get("min_score", 3)
                ):
                    analysis["symbol"] = asset
                    analysis["market_type"] = self.mode
                    self.db.save_signal(analysis)
                    results.append(analysis)

                time.sleep(0.2)
            except Exception as e:
                print(f"Error analyzing {asset}: {e}")
                continue

        results.sort(key=lambda x: x.get("score", 0), reverse=True)
        return results[: self.config.get("max_signals", 5)]

    def analyze_asset(self, symbol):
        if not self.data_provider:
            print("No data provider for analysis.")
            return None
        try:
            df = self.data_provider.get_ohlcv(
                symbol, self.timeframe, self.config.get("ohlcv_limit", 200)
            )
            if df is not None and len(df) >= 50:
                analysis = self.strategy.analyze(df)
                if analysis:
                    analysis["symbol"] = symbol
                    analysis["market_type"] = self.mode
                    self.db.save_signal(analysis)
                    return analysis
            print(f"No valid analysis for {symbol}")
            return None
        except Exception as e:
            print(f"Error analyzing {symbol}: {e}")
            return None

    # PHASE 2 ENHANCEMENTS - ML AND ADVANCED FEATURES
    def analyze_with_ml(self, symbol):
        """Analyze asset with ML enhancement"""
        if not self.data_provider:
            return None
            
        try:
            df = self.data_provider.get_ohlcv(
                symbol, self.timeframe, self.config.get("ohlcv_limit", 200)
            )
            
            if df is not None and len(df) >= 50:
                traditional_analysis = self.strategy.analyze(df)
                
                if traditional_analysis:
                    ml_features = self.ml_bot.extract_features(df)
                    enhanced_analysis = self._combine_analyses(traditional_analysis, ml_features)
                    
                    portfolio_recommendation = self.portfolio_optimizer.optimize_position(
                        enhanced_analysis, self.get_active_positions()
                    )
                    
                    enhanced_analysis['portfolio_recommendation'] = portfolio_recommendation
                    enhanced_analysis['symbol'] = symbol
                    enhanced_analysis['market_type'] = self.mode
                    
                    self.db.save_signal(enhanced_analysis)
                    return enhanced_analysis
                
            return None
                
        except Exception as e:
            print(f"ML-enhanced analysis error for {symbol}: {e}")
            return None
    
    def _combine_analyses(self, traditional_analysis, ml_features):
        if not traditional_analysis:
            return None
            
        ml_confidence = self._calculate_ml_confidence(ml_features)
        traditional_analysis['ml_confidence'] = ml_confidence
        traditional_analysis['combined_score'] = traditional_analysis['final_score'] * ml_confidence
        
        return traditional_analysis
    
    def _calculate_ml_confidence(self, ml_features):
        if ml_features.empty:
            return 1.0
            
        volatility = ml_features['volatility'].iloc[0] if 'volatility' in ml_features.columns else 0.02
        volume_ratio = ml_features['volume_ratio'].iloc[0] if 'volume_ratio' in ml_features.columns else 1
        
        if 0.01 < volatility < 0.05 and volume_ratio > 1.2:
            return 1.2
        elif volatility > 0.1:
            return 0.8
        else:
            return 1.0
    
    def run_comprehensive_backtest(self, symbol, days=365):
        """Run comprehensive backtest for a symbol"""
        try:
            df = self._get_historical_data(symbol, days)
            
            if df is None or len(df) < 100:
                return {"error": "Insufficient historical data"}
            
            results = self.backtest_engine.run_backtest(df, self.strategy)
            
            results['symbol'] = symbol
            results['period_days'] = days
            results['test_date'] = datetime.now().isoformat()
            
            return results
            
        except Exception as e:
            print(f"Backtest error for {symbol}: {e}")
            return {"error": str(e)}
    
    def _get_historical_data(self, symbol, days):
        try:
            return self.data_provider.get_ohlcv(symbol, "1d", days)
        except Exception as e:
            print(f"Error getting historical data: {e}")
            return None
    
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
        if not self.data_provider:
            print("No data provider for custom entry.")
            return None
        try:
            df = self.data_provider.get_ohlcv(
                symbol, self.timeframe, self.config.get("ohlcv_limit", 200)
            )
            if df is not None and len(df) >= 50:
                atr = self.strategy.calculate_atr(df)
                return {
                    "symbol": symbol,
                    "entry_price": float(entry_price),
                    "tp1": float(entry_price + atr * self.strategy.atr_multiplier),
                    "tp2": float(entry_price + atr * self.strategy.atr_multiplier * 2),
                    "tp3": float(entry_price + atr * self.strategy.atr_multiplier * 3),
                    "sl": float(entry_price - atr * self.strategy.atr_multiplier),
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
                ticker = self.data_provider.get_ticker(symbol)
                if ticker and 'last' in ticker:
                    self.db.update_position_current_price(symbol, ticker['last'])
            return self.db.get_active_positions(self.mode)
        except Exception as e:
            print(f"Error fetching active positions: {e}")
            return []

    def get_trade_history(self, limit=10):
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
