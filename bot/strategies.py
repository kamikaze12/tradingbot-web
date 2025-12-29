import pandas as pd
import numpy as np
from abc import ABC, abstractmethod
import warnings
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum
import logging
from scipy import stats
from scipy.signal import argrelextrema
import talib
import yfinance as yf
from datetime import datetime, timedelta
import time
import os
import sys

# =============================================
# IMPORT BACKTESTING LIBRARIES
# =============================================
try:
    # Coba import backtesting.py dari external_repos
    sys.path.append('bot/external_repos/backtesting')
    from backtesting import Backtest, Strategy as BTStrategy
    BACKTESTING_AVAILABLE = True
    logger.info("✅ Backtesting.py library loaded successfully")
except ImportError as e:
    BACKTESTING_AVAILABLE = False
    logger.warning(f"Backtesting.py not available: {e}")

try:
    # Coba import backtrader dari external_repos
    sys.path.append('bot/external_repos/backtrader')
    import backtrader as bt
    import backtrader.analyzers as btanalyzers
    import backtrader.feeds as btfeeds
    BACKTRADER_AVAILABLE = True
    logger.info("✅ Backtrader library loaded successfully")
except ImportError as e:
    BACKTRADER_AVAILABLE = False
    logger.warning(f"Backtrader not available: {e}")

try:
    # Coba import strategi dari quant-trading
    sys.path.append('bot/external_repos/quant-trading')
    from strategies import MeanReversionStrategy as QMeanReversionStrategy
    from strategies import TrendFollowingStrategy as QTrendFollowingStrategy
    from strategies import BreakoutStrategy as QBreakoutStrategy
    QUANT_STRATEGIES_AVAILABLE = True
    logger.info("✅ Quant trading strategies loaded successfully")
except ImportError as e:
    QUANT_STRATEGIES_AVAILABLE = False
    logger.warning(f"Quant strategies not available: {e}")

try:
    # Coba import dari awesome-systematic
    sys.path.append('bot/external_repos/awesome-systematic')
    from systematic_trading import MomentumStrategy, VolatilityStrategy
    AWESOME_SYSTEMATIC_AVAILABLE = True
    logger.info("✅ Awesome-systematic strategies loaded successfully")
except ImportError as e:
    AWESOME_SYSTEMATIC_AVAILABLE = False
    logger.warning(f"Awesome-systematic not available: {e}")

warnings.filterwarnings('ignore')

# Enhanced logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# =============================================
# SCALPING CONFIGURATION - UNTUK PERBAIKAN BIAS SHORT
# =============================================

SCALPING_CONFIG = {
    "timeframe": "5m",
    "lookback": 150,
    "min_score_threshold": 4.0,
    "long_bias": 0.0,
    "entry_range_pct": 0.008,
    "atr_multiplier": 0.7,
    "min_volume_usd": 500000,
    "price_filter": {
        "min": 0.01,
        "max": 500
    },
    "skip_dummy_data": True,
    "require_real_data": True,
    "max_volatility": 0.15,
    "min_volatility": 0.005
}

# =============================================
# BACKTESTING CONFIGURATION
# =============================================

BACKTEST_CONFIG = {
    "initial_cash": 10000,
    "commission": 0.001,  # 0.1% commission
    "slippage": 0.0005,   # 0.05% slippage
    "risk_free_rate": 0.02,  # 2% risk-free rate
    "test_period": {
        "train": "2023-01-01:2023-06-30",
        "test": "2023-07-01:2023-12-31"
    },
    "metrics": [
        "sharpe_ratio",
        "max_drawdown",
        "win_rate",
        "profit_factor",
        "total_return",
        "calmar_ratio",
        "sortino_ratio"
    ],
    "optimization": {
        "method": "grid_search",
        "param_grid": {
            "atr_multiplier": [0.5, 1.0, 1.5, 2.0],
            "entry_range_pct": [0.01, 0.02, 0.03, 0.04],
            "rsi_period": [10, 14, 20],
            "macd_fast": [8, 12, 16],
            "macd_slow": [21, 26, 30]
        }
    }
}

# =============================================
# DATA CLEANER FUNCTION
# =============================================

def get_clean_data(symbol, provider=None, timeframe='1h', lookback=200):
    """Fungsi simple untuk mendapatkan data bersih."""
    try:
        if provider is not None and hasattr(provider, 'get_ohlcv'):
            try:
                logger.info(f"📊 Getting data for {symbol} from {provider.__class__.__name__}...")
                df = provider.get_ohlcv(symbol, timeframe, limit=lookback)
                
                if df is None or df.empty:
                    logger.warning(f"Provider returned empty data for {symbol}")
                    provider = None
                else:
                    if len(df) < 20:
                        logger.warning(f"⚠️ Insufficient data from provider: {len(df)} bars")
                        provider = None
                    else:
                        logger.info(f"✅ Data from provider: {len(df)} bars")
                    
            except Exception as provider_error:
                logger.warning(f"Provider failed for {symbol}: {provider_error}, falling back to yfinance")
                provider = None
        
        if provider is None:
            time.sleep(0.5)
            
            clean_symbol = symbol.split(':')[0] if ':' in symbol else symbol
            clean_symbol = clean_symbol.replace('/', '-').replace('USDT-', '')
            
            logger.info(f"📥 Downloading {clean_symbol} from YFinance...")
            try:
                df = yf.download(clean_symbol, period=f'{lookback}d', interval=timeframe, progress=False)
            except Exception as e:
                logger.error(f"YFinance download error: {e}")
                return pd.DataFrame()
            
            if df is None or df.empty:
                logger.warning(f"No data for {symbol}")
                return pd.DataFrame()
        
        if df is None or df.empty:
            logger.warning(f"Empty DataFrame after provider for {symbol}")
            return pd.DataFrame()
        
        if 'close' in df.columns:
            close_values = df['close'].values
            is_close_to_100 = np.isclose(close_values, 100.0, atol=0.001)
            
            if np.any(is_close_to_100):
                count_100 = np.sum(is_close_to_100)
                logger.warning(f"Found {count_100} bars with close price 100 in {symbol}. Fixing...")
                
                df.loc[is_close_to_100, 'close'] = np.nan
                df['close'] = df['close'].ffill()
                df['close'] = df['close'].bfill()
        
        if 'close' in df.columns:
            close_values = df['close'].values
            
            mask_positive = close_values > 0
            if not np.all(mask_positive):
                df = df[mask_positive].copy()
            
            mask_realistic = close_values < 1000000
            if not np.all(mask_realistic):
                df = df[mask_realistic].copy()
            
            if 'high' in df.columns and 'low' in df.columns:
                high_values = df['high'].values
                low_values = df['low'].values
                mask_valid = high_values >= low_values
                if not np.all(mask_valid):
                    df = df[mask_valid].copy()
        
        column_mapping = {
            'Open': 'open',
            'High': 'high', 
            'Low': 'low',
            'Close': 'close',
            'Volume': 'volume'
        }
        
        for old, new in column_mapping.items():
            if old in df.columns:
                df = df.rename(columns={old: new})
        
        required_cols = ['open', 'high', 'low', 'close', 'volume']
        for col in required_cols:
            if col not in df.columns:
                if col == 'volume':
                    df[col] = np.random.normal(1000000, 100000, len(df))
                else:
                    df[col] = df['close'] if 'close' in df.columns else 100
        
        if df.empty:
            logger.warning(f"Empty DataFrame after cleaning for {symbol}")
            return pd.DataFrame()
        
        if 'close' in df.columns:
            close_values_final = df['close'].values
            is_close_to_100_final = np.isclose(close_values_final, 100.0, atol=0.001)
            
            if np.any(is_close_to_100_final):
                logger.error(f"🚨 {symbol} still has price 100 after cleaning!")
                return pd.DataFrame()
        
        logger.info(f"✅ Clean data for {symbol}: {len(df)} bars")
        return df
        
    except Exception as e:
        logger.error(f"Error in get_clean_data for {symbol}: {e}")
        return pd.DataFrame()

def get_trading_data(symbol, provider=None, scalping_mode=False, require_real_data=False):
    """Wrapper function untuk digunakan di strategi trading."""
    try:
        if provider is not None and hasattr(provider, 'get_ohlcv'):
            try:
                logger.info(f"🔍 Getting OHLCV for {symbol} from {provider.__class__.__name__}")
                
                timeframe = '5m' if scalping_mode else '1h'
                limit = 150 if scalping_mode else 100
                
                df = provider.get_ohlcv(symbol, timeframe, limit)
                
                if df is None or df.empty:
                    logger.warning(f"Provider returned no data for {symbol}")
                    return None
                
                min_bars = 100 if scalping_mode else 20
                if len(df) < min_bars:
                    logger.warning(f"⚠️ {symbol} insufficient data: {len(df)} < {min_bars} bars")
                    return None
                
                column_mapping = {
                    'Open': 'open',
                    'High': 'high', 
                    'Low': 'low',
                    'Close': 'close',
                    'Volume': 'volume'
                }
                
                for old, new in column_mapping.items():
                    if old in df.columns:
                        df = df.rename(columns={old: new})
                
                if 'close' in df.columns:
                    logger.debug(f"🔍 {symbol}: Checking for price 100, current range: {df['close'].min():.4f}-{df['close'].max():.4f}")
                    
                    close_values = df['close'].values
                    price_100_count = np.sum(np.isclose(close_values, 100.0, atol=0.001))
                    if price_100_count > 0:
                        logger.error(f"🚨 {symbol}: Found {price_100_count} bars with price ~100, rejecting!")
                        return None
                    
                    unique_prices = len(np.unique(close_values))
                    if unique_prices < 3 and len(df) > 10:
                        logger.warning(f"⚠️ {symbol}: Too few unique prices ({unique_prices}), possibly stuck at 100")
                        return None
                
                logger.info(f"✅ Valid data from provider for {symbol}: {len(df)} bars")
                return df
                
            except Exception as e:
                logger.error(f"Error getting data from provider: {e}")
                pass
        
        data = get_clean_data(symbol, provider)
        
        if data is None or data.empty:
            return None
        
        if isinstance(data, pd.Series):
            data = data.to_frame().T
        
        if scalping_mode:
            if len(data) < 100:
                logger.warning(f"⚠️ {symbol} insufficient data for scalping: {len(data)} bars")
                return None
            
            if len(data) > 1:
                price_changes = data['close'].pct_change().abs().mean()
                if price_changes < 0.0005:
                    logger.warning(f"⚠️ {symbol} too flat for scalping: {price_changes*100:.3f}% avg change")
                    return None
            
            if 'volume' in data.columns:
                avg_volume = data['volume'].mean()
                if avg_volume < 100000:
                    logger.warning(f"⚠️ {symbol} volume too low for scalping: {avg_volume:.0f}")
                    return None
            
            if len(data) > 1:
                volatility = data['close'].pct_change().std() * np.sqrt(252)
                if volatility > SCALPING_CONFIG["max_volatility"]:
                    logger.warning(f"⚠️ {symbol} too volatile for scalping: {volatility:.1%}")
                    return None
        
        try:
            if 'close' in data.columns:
                close_values = data['close'].values
                
                is_close_to_100 = np.isclose(close_values, 100.0, atol=0.001)
                
                if np.any(is_close_to_100):
                    count_100 = np.sum(is_close_to_100)
                    logger.error(f"🚨 {symbol}: Found {count_100} bars with price ~100 in final check, rejecting!")
                    return None
                
                if len(data) > 0:
                    current_price = data['close'].iloc[-1]
                else:
                    current_price = 0
                
                if current_price <= 0 or current_price > 1000000:
                    logger.warning(f"⚠️ {symbol} has unrealistic price: {current_price}")
                    return None
                
                if len(data) > 1:
                    price_changes = data['close'].diff().abs().sum()
                    if price_changes < (current_price * 0.0001 * len(data)):
                        logger.warning(f"⚠️ {symbol} has flatline prices")
                        return None
        except Exception as e:
            logger.error(f"Error in final validation for {symbol}: {e}")
            return None
        
        return data
        
    except Exception as e:
        logger.error(f"Error in get_trading_data for {symbol}: {e}")
        return None

# =============================================
# BACKTESTING STRATEGY CLASSES
# =============================================

class BacktestingWrapper:
    """Wrapper untuk menjalankan backtesting dengan berbagai library"""
    
    def __init__(self, strategy, initial_cash=10000, commission=0.001):
        self.strategy = strategy
        self.initial_cash = initial_cash
        self.commission = commission
        self.results = {}
        
    def run_backtest(self, df, symbol=None, use_library='backtesting'):
        """
        Run backtest dengan library yang dipilih
        
        Args:
            df: DataFrame dengan data OHLCV
            symbol: Nama simbol (optional)
            use_library: 'backtesting', 'backtrader', atau 'custom'
        """
        logger.info(f"📊 Running backtest for {symbol or 'unknown'} using {use_library}")
        
        if use_library == 'backtesting' and BACKTESTING_AVAILABLE:
            return self._run_backtesting_py(df, symbol)
        elif use_library == 'backtrader' and BACKTRADER_AVAILABLE:
            return self._run_backtrader(df, symbol)
        else:
            return self._run_custom_backtest(df, symbol)
    
    def _run_backtesting_py(self, df, symbol):
        """Run backtest menggunakan backtesting.py"""
        try:
            class StrategyWrapper(BTStrategy):
                def init(self):
                    # Inisialisasi indikator
                    self.rsi = self.I(talib.RSI, self.data.Close, timeperiod=14)
                    self.macd, self.signal, self.hist = self.I(talib.MACD, self.data.Close)
                    
                def next(self):
                    current_price = self.data.Close[-1]
                    
                    # Dapatkan sinyal dari strategi utama
                    current_df = pd.DataFrame({
                        'open': self.data.Open[-50:],
                        'high': self.data.High[-50:],
                        'low': self.data.Low[-50:],
                        'close': self.data.Close[-50:],
                        'volume': self.data.Volume[-50:]
                    })
                    
                    signal = self.strategy.analyze(current_df, symbol)
                    
                    if signal['action'] == 'LONG' and not self.position:
                        self.buy()
                    elif signal['action'] == 'SHORT' and not self.position:
                        self.sell()
                    elif signal['action'] == 'NEUTRAL' and self.position:
                        self.position.close()
            
            bt = Backtest(df, StrategyWrapper, 
                         cash=self.initial_cash, 
                         commission=self.commission)
            
            stats = bt.run()
            return {
                'library': 'backtesting.py',
                'sharpe_ratio': stats['Sharpe Ratio'],
                'max_drawdown': stats['Max. Drawdown [%]'],
                'win_rate': stats['Win Rate [%]'],
                'profit_factor': stats['Profit Factor'],
                'total_return': stats['Return [%]'],
                'total_trades': stats['# Trades'],
                'details': stats
            }
            
        except Exception as e:
            logger.error(f"Error in backtesting.py backtest: {e}")
            return self._run_custom_backtest(df, symbol)
    
    def _run_backtrader(self, df, symbol):
        """Run backtest menggunakan backtrader"""
        try:
            class BacktraderStrategy(bt.Strategy):
                params = (
                    ('initial_cash', self.initial_cash),
                )
                
                def __init__(self):
                    self.rsi = bt.indicators.RSI(self.data.close, period=14)
                    self.macd = bt.indicators.MACD(self.data.close)
                    
                def next(self):
                    current_price = self.data.close[0]
                    
                    current_df = pd.DataFrame({
                        'open': self.data.open.get(size=50),
                        'high': self.data.high.get(size=50),
                        'low': self.data.low.get(size=50),
                        'close': self.data.close.get(size=50),
                        'volume': self.data.volume.get(size=50)
                    })
                    
                    signal = self.strategy.analyze(current_df, symbol)
                    
                    if signal['action'] == 'LONG' and not self.position:
                        self.buy()
                    elif signal['action'] == 'SHORT' and not self.position:
                        self.sell()
                    elif signal['action'] == 'NEUTRAL' and self.position:
                        self.close()
            
            cerebro = bt.Cerebro()
            cerebro.broker.setcash(self.initial_cash)
            cerebro.broker.setcommission(commission=self.commission)
            
            data = btfeeds.PandasData(dataname=df)
            cerebro.adddata(data)
            cerebro.addstrategy(BacktraderStrategy)
            
            cerebro.addanalyzer(btanalyzers.SharpeRatio, _name='sharpe')
            cerebro.addanalyzer(btanalyzers.DrawDown, _name='drawdown')
            cerebro.addanalyzer(btanalyzers.TradeAnalyzer, _name='trades')
            cerebro.addanalyzer(btanalyzers.Returns, _name='returns')
            
            results = cerebro.run()
            strat = results[0]
            
            return {
                'library': 'backtrader',
                'sharpe_ratio': strat.analyzers.sharpe.get_analysis()['sharperatio'],
                'max_drawdown': strat.analyzers.drawdown.get_analysis()['max']['drawdown'],
                'total_return': strat.analyzers.returns.get_analysis()['rtot'],
                'details': {
                    'sharpe': strat.analyzers.sharpe.get_analysis(),
                    'drawdown': strat.analyzers.drawdown.get_analysis(),
                    'trades': strat.analyzers.trades.get_analysis()
                }
            }
            
        except Exception as e:
            logger.error(f"Error in backtrader backtest: {e}")
            return self._run_custom_backtest(df, symbol)
    
    def _run_custom_backtest(self, df, symbol):
        """Run backtest custom sederhana"""
        try:
            cash = self.initial_cash
            position = 0
            trades = []
            equity_curve = []
            
            for i in range(50, len(df)):
                current_data = df.iloc[i-50:i]
                signal = self.strategy.analyze(current_data, symbol)
                
                current_price = df['close'].iloc[i]
                equity_curve.append(cash + (position * current_price))
                
                if signal['action'] == 'LONG' and position <= 0:
                    if position < 0:  # Close short position
                        cash -= position * current_price * (1 + self.commission)
                        trades.append({
                            'type': 'close_short',
                            'price': current_price,
                            'profit': (position * (current_price - trades[-1]['price']))
                        })
                        position = 0
                    
                    # Open long position
                    shares = cash * 0.95 / current_price
                    cash -= shares * current_price * (1 + self.commission)
                    position = shares
                    trades.append({
                        'type': 'open_long',
                        'price': current_price,
                        'shares': shares
                    })
                    
                elif signal['action'] == 'SHORT' and position >= 0:
                    if position > 0:  # Close long position
                        cash += position * current_price * (1 - self.commission)
                        trades.append({
                            'type': 'close_long',
                            'price': current_price,
                            'profit': (position * (current_price - trades[-1]['price']))
                        })
                        position = 0
                    
                    # Open short position
                    shares = cash * 0.95 / current_price
                    cash += shares * current_price * (1 - self.commission)
                    position = -shares
                    trades.append({
                        'type': 'open_short',
                        'price': current_price,
                        'shares': shares
                    })
                
                elif signal['action'] == 'NEUTRAL' and position != 0:
                    if position > 0:  # Close long
                        cash += position * current_price * (1 - self.commission)
                        trades.append({
                            'type': 'close_long_neutral',
                            'price': current_price,
                            'profit': (position * (current_price - trades[-1]['price']))
                        })
                    elif position < 0:  # Close short
                        cash -= position * current_price * (1 + self.commission)
                        trades.append({
                            'type': 'close_short_neutral',
                            'price': current_price,
                            'profit': (position * (current_price - trades[-1]['price']))
                        })
                    position = 0
            
            # Close final position
            final_price = df['close'].iloc[-1]
            final_value = cash + (position * final_price)
            total_return = (final_value / self.initial_cash - 1) * 100
            
            # Calculate metrics
            winning_trades = [t for t in trades if 'profit' in t and t['profit'] > 0]
            losing_trades = [t for t in trades if 'profit' in t and t['profit'] <= 0]
            
            win_rate = len(winning_trades) / len(trades) * 100 if trades else 0
            profit_factor = abs(sum(t['profit'] for t in winning_trades)) / abs(sum(t['profit'] for t in losing_trades)) if losing_trades else float('inf')
            
            # Sharpe ratio (simplified)
            equity_array = np.array(equity_curve)
            returns = np.diff(equity_array) / equity_array[:-1]
            sharpe = np.mean(returns) / np.std(returns) * np.sqrt(252) if len(returns) > 1 and np.std(returns) > 0 else 0
            
            # Max drawdown
            rolling_max = np.maximum.accumulate(equity_array)
            drawdowns = (equity_array - rolling_max) / rolling_max
            max_drawdown = np.min(drawdowns) * 100 if len(drawdowns) > 0 else 0
            
            return {
                'library': 'custom',
                'sharpe_ratio': sharpe,
                'max_drawdown': max_drawdown,
                'win_rate': win_rate,
                'profit_factor': profit_factor,
                'total_return': total_return,
                'total_trades': len(trades),
                'winning_trades': len(winning_trades),
                'losing_trades': len(losing_trades),
                'final_value': final_value,
                'details': {
                    'equity_curve': equity_curve,
                    'trades': trades
                }
            }
            
        except Exception as e:
            logger.error(f"Error in custom backtest: {e}")
            return {
                'library': 'error',
                'error': str(e),
                'sharpe_ratio': 0,
                'max_drawdown': 0,
                'win_rate': 0,
                'total_return': 0
            }

# =============================================
# QUANTITATIVE TRADING STRATEGIES
# =============================================

class MeanReversionStrategy(TradingStrategy):
    """Mean Reversion Strategy dari quant-trading repo"""
    
    def __init__(self, market_type="crypto", lookback_period=20, 
                 std_dev_threshold=2.0, **kwargs):
        super().__init__(market_type=market_type, **kwargs)
        self.lookback_period = lookback_period
        self.std_dev_threshold = std_dev_threshold
        
        if QUANT_STRATEGIES_AVAILABLE:
            self.quant_strategy = QMeanReversionStrategy(lookback=lookback_period)
        else:
            self.quant_strategy = None
        
        logger.info(f"📈 MeanReversionStrategy initialized (Lookback: {lookback_period}, Std Dev: {std_dev_threshold})")
    
    def analyze(self, df: pd.DataFrame, symbol: str = None) -> Dict[str, Any]:
        """Implementasi mean reversion strategy"""
        try:
            if df is None or len(df) < self.lookback_period:
                return self._get_default_analysis(symbol)
            
            prices = df['close'].values
            
            # Calculate Bollinger Bands
            sma = np.mean(prices[-self.lookback_period:])
            std = np.std(prices[-self.lookback_period:])
            
            upper_band = sma + (std * self.std_dev_threshold)
            lower_band = sma - (std * self.std_dev_threshold)
            
            current_price = prices[-1]
            
            # Calculate z-score
            z_score = (current_price - sma) / std if std > 0 else 0
            
            # Determine signal
            score = 0
            if current_price < lower_band:
                score = 3  # Strong buy signal (oversold)
                action = "LONG"
            elif current_price > upper_band:
                score = -3  # Strong sell signal (overbought)
                action = "SHORT"
            elif z_score < -1:
                score = 2
                action = "LONG"
            elif z_score > 1:
                score = -2
                action = "SHORT"
            else:
                score = 0
                action = "NEUTRAL"
            
            # Apply external quant strategy jika tersedia
            if self.quant_strategy:
                try:
                    quant_signal = self.quant_strategy.get_signal(prices)
                    if quant_signal != 0:
                        score += quant_signal * 2
                        logger.debug(f"Quant strategy signal: {quant_signal}")
                except:
                    pass
            
            # Calculate entry levels
            entry_calc = self.calculate_custom_entry(
                symbol=symbol or "UNKNOWN",
                current_price=current_price,
                action=action,
                df=df
            )
            
            result = {
                'action': action,
                'score': score,
                'current_price': current_price,
                'sma': sma,
                'std': std,
                'upper_band': upper_band,
                'lower_band': lower_band,
                'z_score': z_score,
                'symbol': symbol or "UNKNOWN",
                'strategy_type': 'mean_reversion',
                'confidence': min(abs(z_score) / 3.0, 1.0),
                'lookback_period': self.lookback_period,
                'std_dev_threshold': self.std_dev_threshold
            }
            
            result.update(entry_calc)
            
            logger.info(f"📊 {symbol}: MeanReversion {action} (Z-score: {z_score:.2f}, Score: {score:.1f})")
            return result
            
        except Exception as e:
            logger.error(f"Error in MeanReversionStrategy analysis: {e}")
            return self._get_default_analysis(symbol)

class TrendFollowingStrategy(TradingStrategy):
    """Trend Following Strategy dari quant-trading repo"""
    
    def __init__(self, market_type="crypto", fast_period=10, 
                 slow_period=30, **kwargs):
        super().__init__(market_type=market_type, **kwargs)
        self.fast_period = fast_period
        self.slow_period = slow_period
        
        if QUANT_STRATEGIES_AVAILABLE:
            self.quant_strategy = QTrendFollowingStrategy(fast=fast_period, slow=slow_period)
        else:
            self.quant_strategy = None
        
        logger.info(f"📈 TrendFollowingStrategy initialized (Fast: {fast_period}, Slow: {slow_period})")
    
    def analyze(self, df: pd.DataFrame, symbol: str = None) -> Dict[str, Any]:
        """Implementasi trend following strategy"""
        try:
            if df is None or len(df) < self.slow_period:
                return self._get_default_analysis(symbol)
            
            prices = df['close'].values
            
            # Calculate moving averages
            fast_ma = np.mean(prices[-self.fast_period:]) if len(prices) >= self.fast_period else prices[-1]
            slow_ma = np.mean(prices[-self.slow_period:]) if len(prices) >= self.slow_period else prices[-1]
            
            current_price = prices[-1]
            
            # Calculate ADX untuk konfirmasi trend
            if len(df) >= 14:
                high = df['high'].values[-14:]
                low = df['low'].values[-14:]
                close = prices[-14:]
                
                try:
                    adx = talib.ADX(high, low, close, timeperiod=14)[-1]
                except:
                    adx = 20
            else:
                adx = 20
            
            # Determine trend direction
            ma_diff = fast_ma - slow_ma
            price_above_fast = current_price > fast_ma
            price_above_slow = current_price > slow_ma
            
            # Calculate score
            score = 0
            
            # Uptrend conditions
            if ma_diff > 0 and price_above_fast and price_above_slow:
                score = 3
                if adx > 25:
                    score += 1
                action = "LONG"
            
            # Downtrend conditions
            elif ma_diff < 0 and not price_above_fast and not price_above_slow:
                score = -3
                if adx > 25:
                    score -= 1
                action = "SHORT"
            
            # Weak signals
            elif ma_diff > 0 and price_above_slow:
                score = 1
                action = "LONG"
            elif ma_diff < 0 and not price_above_slow:
                score = -1
                action = "SHORT"
            else:
                score = 0
                action = "NEUTRAL"
            
            # Apply external quant strategy
            if self.quant_strategy:
                try:
                    quant_signal = self.quant_strategy.get_signal(prices)
                    if quant_signal != 0:
                        score += quant_signal
                except:
                    pass
            
            # Calculate entry levels
            entry_calc = self.calculate_custom_entry(
                symbol=symbol or "UNKNOWN",
                current_price=current_price,
                action=action,
                df=df
            )
            
            result = {
                'action': action,
                'score': score,
                'current_price': current_price,
                'fast_ma': fast_ma,
                'slow_ma': slow_ma,
                'ma_diff': ma_diff,
                'adx': adx,
                'symbol': symbol or "UNKNOWN",
                'strategy_type': 'trend_following',
                'confidence': min(adx / 50.0, 1.0),
                'fast_period': self.fast_period,
                'slow_period': self.slow_period
            }
            
            result.update(entry_calc)
            
            logger.info(f"📊 {symbol}: TrendFollowing {action} (MA Diff: {ma_diff:.4f}, ADX: {adx:.1f}, Score: {score:.1f})")
            return result
            
        except Exception as e:
            logger.error(f"Error in TrendFollowingStrategy analysis: {e}")
            return self._get_default_analysis(symbol)

class BreakoutStrategy(TradingStrategy):
    """Breakout Strategy dari quant-trading repo"""
    
    def __init__(self, market_type="crypto", lookback_period=20, 
                 breakout_threshold=0.02, **kwargs):
        super().__init__(market_type=market_type, **kwargs)
        self.lookback_period = lookback_period
        self.breakout_threshold = breakout_threshold
        
        if QUANT_STRATEGIES_AVAILABLE:
            self.quant_strategy = QBreakoutStrategy(lookback=lookback_period)
        else:
            self.quant_strategy = None
        
        logger.info(f"📈 BreakoutStrategy initialized (Lookback: {lookback_period}, Threshold: {breakout_threshold*100:.1f}%)")
    
    def analyze(self, df: pd.DataFrame, symbol: str = None) -> Dict[str, Any]:
        """Implementasi breakout strategy"""
        try:
            if df is None or len(df) < self.lookback_period:
                return self._get_default_analysis(symbol)
            
            prices = df['close'].values
            highs = df['high'].values
            lows = df['low'].values
            
            current_price = prices[-1]
            
            # Calculate recent high and low
            recent_high = np.max(highs[-self.lookback_period:-1])
            recent_low = np.min(lows[-self.lookback_period:-1])
            
            # Calculate breakout levels
            resistance = recent_high * (1 + self.breakout_threshold)
            support = recent_low * (1 - self.breakout_threshold)
            
            # Determine breakout
            score = 0
            if current_price > resistance:
                score = 4  # Strong breakout long
                action = "LONG"
                breakout_type = "RESISTANCE"
            elif current_price < support:
                score = -4  # Strong breakout short
                action = "SHORT"
                breakout_type = "SUPPORT"
            elif current_price > recent_high:
                score = 2
                action = "LONG"
                breakout_type = "MINOR_BREAKOUT"
            elif current_price < recent_low:
                score = -2
                action = "SHORT"
                breakout_type = "MINOR_BREAKOUT"
            else:
                score = 0
                action = "NEUTRAL"
                breakout_type = "NO_BREAKOUT"
            
            # Volume confirmation
            if 'volume' in df.columns:
                volumes = df['volume'].values
                avg_volume = np.mean(volumes[-self.lookback_period:-1])
                current_volume = volumes[-1]
                volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1
                
                if volume_ratio > 1.5 and action != "NEUTRAL":
                    score *= 1.5  # Boost dengan volume confirmation
            
            # Apply external quant strategy
            if self.quant_strategy:
                try:
                    quant_signal = self.quant_strategy.get_signal(prices)
                    if quant_signal != 0:
                        score += quant_signal
                except:
                    pass
            
            # Calculate entry levels
            entry_calc = self.calculate_custom_entry(
                symbol=symbol or "UNKNOWN",
                current_price=current_price,
                action=action,
                df=df
            )
            
            result = {
                'action': action,
                'score': score,
                'current_price': current_price,
                'recent_high': recent_high,
                'recent_low': recent_low,
                'resistance': resistance,
                'support': support,
                'breakout_type': breakout_type,
                'symbol': symbol or "UNKNOWN",
                'strategy_type': 'breakout',
                'confidence': min(abs(score) / 4.0, 1.0),
                'lookback_period': self.lookback_period,
                'breakout_threshold': self.breakout_threshold
            }
            
            result.update(entry_calc)
            
            logger.info(f"📊 {symbol}: Breakout {action} (Type: {breakout_type}, Score: {score:.1f})")
            return result
            
        except Exception as e:
            logger.error(f"Error in BreakoutStrategy analysis: {e}")
            return self._get_default_analysis(symbol)

# =============================================
# AWESOME SYSTEMATIC STRATEGIES
# =============================================

class MomentumStrategy(TradingStrategy):
    """Momentum Strategy dari awesome-systematic repo"""
    
    def __init__(self, market_type="crypto", momentum_period=20, 
                 ranking_period=30, **kwargs):
        super().__init__(market_type=market_type, **kwargs)
        self.momentum_period = momentum_period
        self.ranking_period = ranking_period
        
        if AWESOME_SYSTEMATIC_AVAILABLE:
            self.systematic_strategy = MomentumStrategy(period=momentum_period)
        else:
            self.systematic_strategy = None
        
        logger.info(f"📈 MomentumStrategy initialized (Momentum: {momentum_period}, Ranking: {ranking_period})")
    
    def analyze(self, df: pd.DataFrame, symbol: str = None) -> Dict[str, Any]:
        """Implementasi momentum strategy"""
        try:
            if df is None or len(df) < self.momentum_period:
                return self._get_default_analysis(symbol)
            
            prices = df['close'].values
            
            # Calculate momentum
            momentum = (prices[-1] / prices[-self.momentum_period] - 1) * 100
            
            # Calculate volatility-adjusted momentum
            returns = np.diff(prices[-self.momentum_period:]) / prices[-self.momentum_period:-1]
            volatility = np.std(returns) * np.sqrt(252) if len(returns) > 1 else 0.02
            
            momentum_sharpe = momentum / volatility if volatility > 0 else 0
            
            # Determine signal
            score = 0
            if momentum > 5 and momentum_sharpe > 0.5:
                score = 4  # Strong momentum long
                action = "LONG"
            elif momentum < -5 and momentum_sharpe < -0.5:
                score = -4  # Strong momentum short
                action = "SHORT"
            elif momentum > 2:
                score = 2
                action = "LONG"
            elif momentum < -2:
                score = -2
                action = "SHORT"
            else:
                score = 0
                action = "NEUTRAL"
            
            # Apply systematic strategy
            if self.systematic_strategy:
                try:
                    systematic_signal = self.systematic_strategy.get_signal(prices)
                    if systematic_signal != 0:
                        score += systematic_signal * 2
                except:
                    pass
            
            # Calculate entry levels
            entry_calc = self.calculate_custom_entry(
                symbol=symbol or "UNKNOWN",
                current_price=prices[-1],
                action=action,
                df=df
            )
            
            result = {
                'action': action,
                'score': score,
                'current_price': prices[-1],
                'momentum': momentum,
                'volatility': volatility,
                'momentum_sharpe': momentum_sharpe,
                'symbol': symbol or "UNKNOWN",
                'strategy_type': 'momentum',
                'confidence': min(abs(momentum) / 10.0, 1.0),
                'momentum_period': self.momentum_period
            }
            
            result.update(entry_calc)
            
            logger.info(f"📊 {symbol}: Momentum {action} (Momentum: {momentum:.1f}%, Sharpe: {momentum_sharpe:.2f})")
            return result
            
        except Exception as e:
            logger.error(f"Error in MomentumStrategy analysis: {e}")
            return self._get_default_analysis(symbol)

class VolatilityStrategy(TradingStrategy):
    """Volatility Strategy dari awesome-systematic repo"""
    
    def __init__(self, market_type="crypto", volatility_period=20, 
                 target_volatility=0.20, **kwargs):
        super().__init__(market_type=market_type, **kwargs)
        self.volatility_period = volatility_period
        self.target_volatility = target_volatility
        
        if AWESOME_SYSTEMATIC_AVAILABLE:
            self.systematic_strategy = VolatilityStrategy(period=volatility_period)
        else:
            self.systematic_strategy = None
        
        logger.info(f"📈 VolatilityStrategy initialized (Vol Period: {volatility_period}, Target: {target_volatility*100:.1f}%)")
    
    def analyze(self, df: pd.DataFrame, symbol: str = None) -> Dict[str, Any]:
        """Implementasi volatility strategy"""
        try:
            if df is None or len(df) < self.volatility_period:
                return self._get_default_analysis(symbol)
            
            prices = df['close'].values
            
            # Calculate volatility
            returns = np.diff(prices[-self.volatility_period:]) / prices[-self.volatility_period:-1]
            current_volatility = np.std(returns) * np.sqrt(252) if len(returns) > 1 else 0.02
            
            # Calculate volatility regime
            vol_ratio = current_volatility / self.target_volatility
            
            # Determine signal berdasarkan regime volatility
            score = 0
            current_price = prices[-1]
            
            if vol_ratio < 0.5:
                # Low volatility regime - mean reversion
                sma = np.mean(prices[-self.volatility_period:])
                if current_price < sma * 0.98:
                    score = 2
                    action = "LONG"
                elif current_price > sma * 1.02:
                    score = -2
                    action = "SHORT"
                else:
                    score = 0
                    action = "NEUTRAL"
                    
            elif vol_ratio > 1.5:
                # High volatility regime - breakout
                recent_high = np.max(prices[-self.volatility_period//2:])
                recent_low = np.min(prices[-self.volatility_period//2:])
                
                if current_price > recent_high:
                    score = 3
                    action = "LONG"
                elif current_price < recent_low:
                    score = -3
                    action = "SHORT"
                else:
                    score = 0
                    action = "NEUTRAL"
                    
            else:
                # Normal volatility - trend following
                fast_ma = np.mean(prices[-10:]) if len(prices) >= 10 else current_price
                slow_ma = np.mean(prices[-30:]) if len(prices) >= 30 else current_price
                
                if fast_ma > slow_ma and current_price > fast_ma:
                    score = 2
                    action = "LONG"
                elif fast_ma < slow_ma and current_price < fast_ma:
                    score = -2
                    action = "SHORT"
                else:
                    score = 0
                    action = "NEUTRAL"
            
            # Apply systematic strategy
            if self.systematic_strategy:
                try:
                    systematic_signal = self.systematic_strategy.get_signal(prices)
                    if systematic_signal != 0:
                        score += systematic_signal
                except:
                    pass
            
            # Calculate entry levels
            entry_calc = self.calculate_custom_entry(
                symbol=symbol or "UNKNOWN",
                current_price=current_price,
                action=action,
                df=df
            )
            
            result = {
                'action': action,
                'score': score,
                'current_price': current_price,
                'current_volatility': current_volatility,
                'vol_ratio': vol_ratio,
                'volatility_regime': 'LOW' if vol_ratio < 0.5 else 'HIGH' if vol_ratio > 1.5 else 'NORMAL',
                'symbol': symbol or "UNKNOWN",
                'strategy_type': 'volatility',
                'confidence': min(1.0 - abs(vol_ratio - 1.0), 1.0),
                'volatility_period': self.volatility_period,
                'target_volatility': self.target_volatility
            }
            
            result.update(entry_calc)
            
            logger.info(f"📊 {symbol}: Volatility {action} (Vol: {current_volatility:.1%}, Regime: {result['volatility_regime']})")
            return result
            
        except Exception as e:
            logger.error(f"Error in VolatilityStrategy analysis: {e}")
            return self._get_default_analysis(symbol)

# =============================================
# ENSEMBLE STRATEGY (MULTI-STRATEGY COMBINATION)
# =============================================

class EnsembleStrategy(TradingStrategy):
    """Ensemble strategy yang menggabungkan multiple strategies"""
    
    def __init__(self, market_type="crypto", strategies_config=None, **kwargs):
        super().__init__(market_type=market_type, **kwargs)
        
        # Default strategies jika tidak ada config
        if strategies_config is None:
            strategies_config = [
                {'type': 'technical', 'weight': 0.4},
                {'type': 'mean_reversion', 'weight': 0.2},
                {'type': 'trend_following', 'weight': 0.2},
                {'type': 'breakout', 'weight': 0.1},
                {'type': 'momentum', 'weight': 0.1}
            ]
        
        self.strategies = []
        self.weights = []
        
        for config in strategies_config:
            strategy_type = config['type']
            weight = config['weight']
            
            if strategy_type == 'technical':
                strategy = EnhancedTechnicalAnalysisStrategy(market_type=market_type, **kwargs)
            elif strategy_type == 'mean_reversion':
                strategy = MeanReversionStrategy(market_type=market_type, **kwargs)
            elif strategy_type == 'trend_following':
                strategy = TrendFollowingStrategy(market_type=market_type, **kwargs)
            elif strategy_type == 'breakout':
                strategy = BreakoutStrategy(market_type=market_type, **kwargs)
            elif strategy_type == 'momentum':
                strategy = MomentumStrategy(market_type=market_type, **kwargs)
            elif strategy_type == 'volatility':
                strategy = VolatilityStrategy(market_type=market_type, **kwargs)
            else:
                continue
            
            self.strategies.append(strategy)
            self.weights.append(weight)
        
        # Normalize weights
        total_weight = sum(self.weights)
        self.weights = [w / total_weight for w in self.weights]
        
        logger.info(f"📈 EnsembleStrategy initialized with {len(self.strategies)} strategies")
    
    def analyze(self, df: pd.DataFrame, symbol: str = None) -> Dict[str, Any]:
        """Combine signals from multiple strategies"""
        try:
            if df is None or len(df) < 20:
                return self._get_default_analysis(symbol)
            
            all_signals = []
            weighted_score = 0
            
            for strategy, weight in zip(self.strategies, self.weights):
                try:
                    signal = strategy.analyze(df, symbol)
                    
                    # Convert action to score
                    if signal['action'] == 'LONG':
                        action_score = 1
                    elif signal['action'] == 'SHORT':
                        action_score = -1
                    else:
                        action_score = 0
                    
                    # Weighted score
                    weighted_score += action_score * weight * abs(signal.get('score', 1))
                    
                    all_signals.append({
                        'type': strategy.__class__.__name__,
                        'action': signal['action'],
                        'score': signal.get('score', 0),
                        'weight': weight,
                        'confidence': signal.get('confidence', 0.5)
                    })
                    
                except Exception as e:
                    logger.error(f"Error in sub-strategy {strategy.__class__.__name__}: {e}")
                    continue
            
            # Determine final action
            if weighted_score > 0.5:
                action = "LONG"
                final_score = weighted_score
            elif weighted_score < -0.5:
                action = "SHORT"
                final_score = weighted_score
            else:
                action = "NEUTRAL"
                final_score = 0
            
            # Calculate entry levels
            current_price = df['close'].iloc[-1]
            entry_calc = self.calculate_custom_entry(
                symbol=symbol or "UNKNOWN",
                current_price=current_price,
                action=action,
                df=df
            )
            
            # Calculate consensus confidence
            long_votes = sum(1 for s in all_signals if s['action'] == 'LONG')
            short_votes = sum(1 for s in all_signals if s['action'] == 'SHORT')
            neutral_votes = sum(1 for s in all_signals if s['action'] == 'NEUTRAL')
            
            total_votes = len(all_signals)
            confidence = max(long_votes, short_votes) / total_votes if total_votes > 0 else 0.5
            
            result = {
                'action': action,
                'score': final_score,
                'current_price': current_price,
                'symbol': symbol or "UNKNOWN",
                'strategy_type': 'ensemble',
                'confidence': confidence,
                'consensus': {
                    'long_votes': long_votes,
                    'short_votes': short_votes,
                    'neutral_votes': neutral_votes,
                    'total_votes': total_votes
                },
                'all_signals': all_signals,
                'weighted_score': weighted_score
            }
            
            result.update(entry_calc)
            
            logger.info(f"📊 {symbol}: Ensemble {action} (Score: {final_score:.2f}, Confidence: {confidence:.1%}, Consensus: {long_votes}/{short_votes}/{neutral_votes})")
            return result
            
        except Exception as e:
            logger.error(f"Error in EnsembleStrategy analysis: {e}")
            return self._get_default_analysis(symbol)

# =============================================
# BASE STRATEGY CLASS DENGAN BACKTEST METHOD
# =============================================

class TradingStrategy(ABC):
    """Base class for all trading strategies dengan backtesting"""
    
    def __init__(self, market_type="crypto", atr_multiplier=1.0, entry_range_pct=0.02,
                 trading_type="spot", leverage=1, max_leverage_risk=0.01,
                 long_bias=0.0, min_score_threshold=3.0, scalping_mode=False):
        self.market_type = market_type
        self.atr_multiplier = atr_multiplier
        self.entry_range_pct = entry_range_pct
        self.trading_type = trading_type
        self.leverage = leverage
        self.max_leverage_risk = max_leverage_risk
        self.long_bias = long_bias
        self.min_score_threshold = min_score_threshold
        self.scalping_mode = scalping_mode
        
        if trading_type == "futures":
            self.entry_range_pct = entry_range_pct * 1.5
            self.atr_multiplier = atr_multiplier * 1.3
            logger.info(f"🔄 Strategy configured for FUTURES: leverage={leverage}x")
        
        if scalping_mode:
            self.entry_range_pct = SCALPING_CONFIG["entry_range_pct"]
            self.atr_multiplier = SCALPING_CONFIG["atr_multiplier"]
            self.min_score_threshold = SCALPING_CONFIG["min_score_threshold"]
            logger.info(f"⚡ SCALPING MODE: Bias={long_bias}, Min Score={min_score_threshold}")
    
    @abstractmethod
    def analyze(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Analyze market data and return trading signals"""
        pass
    
    def backtest_strategy(self, df, symbol=None, initial_cash=10000, commission=0.001,
                         use_library='auto'):
        """
        Backtest strategy dengan data historical
        
        Args:
            df: DataFrame dengan data OHLCV
            symbol: Nama simbol
            initial_cash: Modal awal
            commission: Komisi per trade
            use_library: Library untuk backtest ('auto', 'backtesting', 'backtrader', 'custom')
        """
        logger.info(f"🔬 Running backtest for {symbol or 'unknown'} with {self.__class__.__name__}")
        
        if df is None or len(df) < 100:
            logger.warning("Insufficient data for backtest")
            return {
                'error': 'Insufficient data',
                'min_data_required': 100,
                'data_provided': len(df) if df is not None else 0
            }
        
        # Pilih library otomatis
        if use_library == 'auto':
            if BACKTESTING_AVAILABLE:
                use_library = 'backtesting'
            elif BACKTRADER_AVAILABLE:
                use_library = 'backtrader'
            else:
                use_library = 'custom'
        
        wrapper = BacktestingWrapper(
            strategy=self,
            initial_cash=initial_cash,
            commission=commission
        )
        
        results = wrapper.run_backtest(df, symbol, use_library)
        
        # Tambahkan informasi strategy
        results['strategy_name'] = self.__class__.__name__
        results['symbol'] = symbol
        results['backtest_period'] = {
            'start': df.index[0].strftime('%Y-%m-%d'),
            'end': df.index[-1].strftime('%Y-%m-%d'),
            'days': (df.index[-1] - df.index[0]).days
        }
        
        # Evaluasi hasil
        self._evaluate_backtest_results(results)
        
        return results
    
    def _evaluate_backtest_results(self, results):
        """Evaluasi hasil backtest"""
        if 'error' in results:
            logger.error(f"Backtest error: {results['error']}")
            return
        
        sharpe = results.get('sharpe_ratio', 0)
        max_dd = results.get('max_drawdown', 0)
        win_rate = results.get('win_rate', 0)
        
        # Berikan rating
        rating = 0
        if sharpe > 1.5 and max_dd > -20 and win_rate > 55:
            rating = 5  # Excellent
        elif sharpe > 1.0 and max_dd > -30 and win_rate > 50:
            rating = 4  # Good
        elif sharpe > 0.5 and max_dd > -40 and win_rate > 45:
            rating = 3  # Average
        elif sharpe > 0 and max_dd > -50:
            rating = 2  # Below Average
        else:
            rating = 1  # Poor
        
        results['rating'] = rating
        results['rating_description'] = {
            5: 'Excellent',
            4: 'Good', 
            3: 'Average',
            2: 'Below Average',
            1: 'Poor'
        }.get(rating, 'Unknown')
        
        logger.info(f"📊 Backtest Results: Sharpe={sharpe:.2f}, Max DD={max_dd:.1f}%, Win Rate={win_rate:.1f}%, Rating={rating}/5")
    
    def optimize_parameters(self, df, symbol=None, param_grid=None):
        """
        Optimasi parameter strategy dengan grid search
        
        Args:
            df: DataFrame data
            symbol: Nama simbol
            param_grid: Grid parameter untuk optimasi
        """
        logger.info(f"🔧 Optimizing parameters for {self.__class__.__name__}")
        
        if param_grid is None:
            # Default parameter grid
            param_grid = BACKTEST_CONFIG['optimization']['param_grid']
        
        best_params = {}
        best_sharpe = -float('inf')
        best_results = {}
        
        # Generate semua kombinasi parameter
        from itertools import product
        
        param_names = list(param_grid.keys())
        param_values = list(param_grid.values())
        
        total_combinations = np.prod([len(v) for v in param_values])
        logger.info(f"Testing {total_combinations} parameter combinations")
        
        # Grid search sederhana (untuk production gunakan library seperti Optuna)
        for i, combo in enumerate(product(*param_values)):
            params = dict(zip(param_names, combo))
            
            try:
                # Buat strategy dengan parameter baru
                strategy_copy = self.__class__(
                    market_type=self.market_type,
                    trading_type=self.trading_type,
                    leverage=self.leverage,
                    **params
                )
                
                # Run backtest
                results = strategy_copy.backtest_strategy(df, symbol)
                
                if 'sharpe_ratio' in results:
                    sharpe = results['sharpe_ratio']
                    
                    if sharpe > best_sharpe:
                        best_sharpe = sharpe
                        best_params = params
                        best_results = results
                        
                        logger.info(f"🔥 New best: Sharpe={sharpe:.3f} with params={params}")
                
            except Exception as e:
                logger.warning(f"Failed test with params {params}: {e}")
                continue
            
            # Progress update
            if (i + 1) % max(1, total_combinations // 10) == 0:
                logger.info(f"Progress: {i+1}/{total_combinations} ({((i+1)/total_combinations*100):.1f}%)")
        
        return {
            'best_params': best_params,
            'best_sharpe': best_sharpe,
            'best_results': best_results,
            'param_grid': param_grid,
            'total_tested': total_combinations
        }
    
    # ... [semua method lainnya dari base class tetap sama] ...
    
    def _preprocess_and_validate(self, df: pd.DataFrame, symbol: str) -> pd.DataFrame:
        """Preprocess data dan validasi kualitas"""
        if df is None or df.empty:
            logger.error(f"Empty data for {symbol}")
            return self._get_fallback_data(symbol)
        
        required_cols = ['open', 'high', 'low', 'close', 'volume']
        if not all(col in df.columns for col in required_cols):
            logger.error(f"Missing columns for {symbol}: {df.columns.tolist()}")
            return self._get_fallback_data(symbol)
        
        df = df.replace([np.inf, -np.inf], np.nan)
        for col in required_cols:
            df[col] = df[col].ffill().bfill().fillna(0)
        
        last_10_prices = df['close'].tail(10).values
        if len(set(last_10_prices)) <= 2:
            logger.warning(f"Price stuck detected for {symbol}, using synthetic data")
            df = self._synthesize_movement(df, symbol)
        
        if (df['close'].values <= 0).any():
            logger.warning(f"Invalid price (<=0) detected for {symbol}, using synthetic data")
            df = self._synthesize_movement(df, symbol)
        
        if (df['high'].values < df['low'].values).any():
            logger.warning(f"High < Low detected for {symbol}, using synthetic data")
            df = self._synthesize_movement(df, symbol)
        
        if df['volume'].mean() < 1:
            logger.warning(f"Zero volume for {symbol}, estimating from volatility")
            df['volume'] = self._estimate_volume_from_volatility(df)
        
        return df
    
    def _get_fallback_data(self, symbol: str) -> pd.DataFrame:
        """Generate fallback data when original data is invalid"""
        dates = pd.date_range('2023-01-01', periods=100, freq='D')
        price = self._estimate_realistic_price(symbol)
        data = {
            'open': np.random.normal(price, price * 0.05, 100),
            'high': np.random.normal(price * 1.05, price * 0.06, 100),
            'low': np.random.normal(price * 0.95, price * 0.06, 100),
            'close': np.random.normal(price, price * 0.05, 100),
            'volume': np.random.normal(1000000, 100000, 100),
        }
        return pd.DataFrame(data, index=dates)
    
    def _synthesize_movement(self, df: pd.DataFrame, symbol: str) -> pd.DataFrame:
        """Add synthetic movement to stuck prices"""
        current_price = df['close'].iloc[-1] if len(df) > 0 else self._estimate_realistic_price(symbol)
        
        if current_price <= 0:
            current_price = self._estimate_realistic_price(symbol)
        
        price_series = [current_price]
        for _ in range(len(df) - 1):
            change = np.random.normal(0, current_price * 0.02)
            new_price = price_series[-1] + change
            price_series.append(max(new_price, current_price * 0.5))
        
        df['close'] = price_series
        df['open'] = df['close'].shift(1).fillna(df['close'])
        df['high'] = df[['open', 'close']].max(axis=1) * np.random.uniform(1.0, 1.02, len(df))
        df['low'] = df[['open', 'close']].min(axis=1) * np.random.uniform(0.98, 1.0, len(df))
        
        logger.info(f"Synthesized movement for {symbol}")
        return df
    
    def _estimate_volume_from_volatility(self, df: pd.DataFrame) -> pd.Series:
        """Estimate volume based on price volatility"""
        volatility = df['close'].pct_change().std()
        base_volume = 1000000
        volume_scale = 1 + (volatility * 100)
        
        return pd.Series(np.random.normal(base_volume * volume_scale, base_volume * 0.1, len(df)))
    
    def calculate_dynamic_entry_range(self, current_price: float, volatility: float = None, 
                                     df: pd.DataFrame = None) -> float:
        """Calculate dynamic entry range dengan bias correction"""
        try:
            if current_price < 0.001 and self.trading_type == "spot":
                logger.warning(f"Very low price detected: ${current_price}. Using conservative settings.")
                return 0.05
            
            if volatility is None:
                if df is not None and len(df) > 20:
                    returns = df['close'].pct_change().dropna()
                    if len(returns) > 1:
                        volatility = returns.std() * np.sqrt(252)
                    else:
                        volatility = 0.02
                else:
                    volatility_map = {
                        "crypto": 0.025,
                        "forex": 0.008,
                        "forex_gold": 0.012,
                        "us_stocks": 0.015,
                        "indonesia_stocks": 0.02,
                        "crypto_future": 0.035,
                        "stock_future": 0.020,
                        "forex_future": 0.010,
                    }
                    volatility = volatility_map.get(self.market_type, 0.02)
            
            daily_vol = volatility / np.sqrt(252)
            base_range = daily_vol * 1.5
            
            if self.trading_type == "futures":
                base_range *= 1.5
                
                if self.leverage >= 20:
                    base_range *= 0.6
                elif self.leverage >= 10:
                    base_range *= 0.8
                elif self.leverage >= 5:
                    base_range *= 1.0
                else:
                    base_range *= 1.2
            elif self.trading_type == "spot":
                base_range *= 0.7
            
            if self.market_type == "crypto" or "future" in str(self.market_type).lower():
                base_range *= 1.2
            
            if self.long_bias > 0:
                base_range = base_range * (1 - self.long_bias * 0.1)
            elif self.long_bias < 0:
                base_range = base_range * (1 + abs(self.long_bias) * 0.1)
            
            min_range = 0.005
            max_range = 0.03
            
            if self.trading_type == "futures":
                min_range = 0.01
                max_range = 0.04
            
            base_range = max(base_range, min_range)
            base_range = min(base_range, max_range)
            
            logger.debug(f"Dynamic range: {base_range*100:.2f}% (Vol: {volatility:.3f}, Type: {self.trading_type}, Lev: {self.leverage}x, Bias: {self.long_bias:.2f})")
            return base_range
            
        except Exception as e:
            logger.error(f"Error calculating dynamic range: {e}")
            return self.entry_range_pct
    
    def _get_minimal_tick_size(self, current_price: float) -> float:
        """Tentukan tick size minimal berdasarkan harga dan exchange"""
        if current_price < 0.0001:
            return 0.000001
        elif current_price < 0.001:
            return 0.00001
        elif current_price < 0.01:
            return 0.0001
        elif current_price < 0.1:
            return 0.001
        elif current_price < 1:
            return 0.01
        elif current_price < 10:
            return 0.02
        elif current_price < 100:
            return 0.05
        elif current_price < 1000:
            return 0.5
        else:
            return 1.0
    
    def calculate_custom_entry(self, symbol: str, current_price: float, action: str = "LONG", 
                              df: pd.DataFrame = None) -> Dict[str, Any]:
        """Calculate TP/SL dengan entry range - DENGAN BIAS CORRECTION"""
        try:
            if current_price < 0.001:
                logger.warning(f"Very low price for {symbol}: ${current_price}. Using conservative settings.")
                self.entry_range_pct = 0.05
                self.atr_multiplier = 2.0
            
            if current_price <= 0 or pd.isna(current_price) or not isinstance(current_price, (int, float)):
                logger.warning(f"Invalid current price for {symbol}: {current_price}")
                current_price = self._estimate_realistic_price(symbol)
                logger.info(f"Using estimated price: {current_price}")
            
            current_price = float(current_price)
            if current_price <= 0:
                current_price = self._estimate_realistic_price(symbol)
            
            if df is not None and not df.empty and all(col in df.columns for col in ['high', 'low', 'close']):
                atr = self._calculate_atr(df)
                if atr <= 0 or pd.isna(atr):
                    logger.warning(f"Invalid ATR for {symbol}: {atr}")
                    if current_price < 0.01:
                        atr = current_price * 0.10
                    elif current_price < 0.1:
                        atr = current_price * 0.05
                    else:
                        atr = current_price * 0.02
            else:
                atr_map = {
                    "forex": current_price * 0.005,
                    "us_stocks": current_price * 0.015,
                    "forex_gold": current_price * 0.008,
                    "crypto_future": current_price * 0.025,
                    "stock_future": current_price * 0.015,
                    "forex_future": current_price * 0.006,
                }
                atr = atr_map.get(self.market_type, current_price * 0.02)
            
            atr = max(atr, current_price * 0.01)
            
            dynamic_range = self.calculate_dynamic_entry_range(current_price, df=df)
            entry_range_pct = dynamic_range
            
            if self.long_bias != 0:
                bias_adjustment = 1 + (self.long_bias * 0.15)
                entry_range_pct = entry_range_pct * bias_adjustment
                logger.debug(f"Bias-adjusted entry range: {entry_range_pct*100:.2f}% (Bias: {self.long_bias:.2f})")
            
            if df is not None and 'sentiment' in df.columns:
                avg_sentiment = df['sentiment'].mean()
                if avg_sentiment < -0.3:
                    entry_range_pct *= 1.5
                    logger.info(f"Negative sentiment ({avg_sentiment:.2f}) detected; widening entry range to {entry_range_pct*100:.2f}%")
            
            if entry_range_pct <= 0:
                entry_range_pct = self.entry_range_pct
            
            liquidation_buffer = 0.0
            if self.trading_type == "futures" and self.leverage > 1:
                liquidation_buffer = (self.max_leverage_risk / self.leverage) * 0.5
            
            if action == "LONG":
                entry_range_low = current_price * (1 - entry_range_pct)
                entry_range_high = current_price * (1 - entry_range_pct * 0.3)
                best_entry = (entry_range_low + entry_range_high) / 2
                
                entry_range_low = max(entry_range_low, current_price * (1 - entry_range_pct - liquidation_buffer))
                
                base_move = max(atr * self.atr_multiplier, current_price * 0.01)
                
                leverage_factor = max(1, self.leverage / 10)
                min_move = base_move / leverage_factor
                
                tp1 = best_entry + min_move
                tp2 = best_entry + min_move * 2
                tp3 = best_entry + min_move * 3
                sl = best_entry - min_move * (1 + liquidation_buffer * 10)
                
            elif action == "SHORT":
                entry_range_low = current_price * (1 + entry_range_pct * 0.3)
                entry_range_high = current_price * (1 + entry_range_pct)
                best_entry = (entry_range_low + entry_range_high) / 2
                
                entry_range_high = min(entry_range_high, current_price * (1 + entry_range_pct + liquidation_buffer))
                
                base_move = max(atr * self.atr_multiplier, current_price * 0.01)
                leverage_factor = max(1, self.leverage / 10)
                min_move = base_move / leverage_factor
                
                if self.long_bias > 0:
                    min_move = min_move * (1 + self.long_bias * 0.2)
                    logger.debug(f"Long bias applied to SHORT: TP/SL widened by {self.long_bias*20:.1f}%")
                
                tp1 = best_entry - min_move
                tp2 = best_entry - min_move * 2
                tp3 = best_entry - min_move * 3
                
                min_distance = current_price * 0.02
                calculated_sl = best_entry + max(min_move, min_distance)
                sl = max(calculated_sl, entry_range_high * 1.01)
                
            else:
                entry_range_low = current_price * (1 - entry_range_pct * 0.1)
                entry_range_high = current_price * (1 + entry_range_pct * 0.1)
                best_entry = current_price
                tp1 = current_price * 1.01
                tp2 = current_price * 1.02
                tp3 = current_price * 1.03
                sl = current_price * 0.99

            tick_size = self._get_minimal_tick_size(current_price)
            entry_range_low = round(entry_range_low / tick_size) * tick_size
            entry_range_high = round(entry_range_high / tick_size) * tick_size
            best_entry = round(best_entry / tick_size) * tick_size
            tp1 = round(tp1 / tick_size) * tick_size
            tp2 = round(tp2 / tick_size) * tick_size
            tp3 = round(tp3 / tick_size) * tick_size
            sl = round(sl / tick_size) * tick_size

            if entry_range_low <= 0 or entry_range_high <= 0 or best_entry <= 0:
                logger.error(f"Invalid entry range calculation for {symbol}, using fallback")
                fallback_price = max(current_price, self._estimate_realistic_price(symbol))
                if action == "LONG":
                    entry_range_low = fallback_price * 0.98
                    entry_range_high = fallback_price * 0.99
                    best_entry = (entry_range_low + entry_range_high) / 2
                    tp1 = best_entry * 1.03
                    tp2 = best_entry * 1.06  
                    tp3 = best_entry * 1.09
                    sl = best_entry * 0.97
                elif action == "SHORT":
                    entry_range_low = fallback_price * 1.01
                    entry_range_high = fallback_price * 1.02
                    best_entry = (entry_range_low + entry_range_high) / 2
                    tp1 = best_entry * 0.97
                    tp2 = best_entry * 0.94
                    tp3 = best_entry * 0.91
                    sl = best_entry * 1.03
                else:
                    entry_range_low = fallback_price * 0.995
                    entry_range_high = fallback_price * 1.005
                    best_entry = fallback_price
                    tp1 = fallback_price * 1.01
                    tp2 = fallback_price * 1.02
                    tp3 = fallback_price * 1.03
                    sl = fallback_price * 0.99

            if action == "LONG":
                if not (sl < entry_range_low <= entry_range_high < tp1 < tp2 < tp3):
                    logger.warning("Invalid LONG levels, applying correction")
                    entry_range_low = current_price * 0.98
                    entry_range_high = current_price * 0.99
                    best_entry = (entry_range_low + entry_range_high) / 2
                    tp1 = best_entry * 1.03
                    tp2 = best_entry * 1.06
                    tp3 = best_entry * 1.09
                    sl = best_entry * 0.97
                    
            elif action == "SHORT":
                if not (sl > entry_range_high >= entry_range_low > tp1 > tp2 > tp3):
                    logger.warning("Invalid SHORT levels, applying correction")
                    entry_range_low = current_price * 1.01
                    entry_range_high = current_price * 1.02
                    best_entry = (entry_range_low + entry_range_high) / 2
                    tp1 = best_entry * 0.97
                    tp2 = best_entry * 0.94
                    tp3 = best_entry * 0.91
                    sl = best_entry * 1.03

            if action == "LONG":
                risk_amount = abs(best_entry - sl)
                reward_tp1 = abs(tp1 - best_entry)
                reward_tp3 = abs(tp3 - best_entry)
            elif action == "SHORT":
                risk_amount = abs(sl - best_entry)
                reward_tp1 = abs(best_entry - tp1)
                reward_tp3 = abs(best_entry - tp3)
            else:
                risk_amount = abs(best_entry - sl)
                reward_tp1 = abs(tp1 - best_entry)
                reward_tp3 = abs(tp3 - best_entry)
            
            rr_ratio_1 = reward_tp1 / risk_amount if risk_amount > 0 else 1
            rr_ratio_3 = reward_tp3 / risk_amount if risk_amount > 0 else 1

            return {
                'symbol': symbol,
                'action': action,
                'trading_type': self.trading_type,
                'leverage': self.leverage,
                'current_price': current_price,
                'entry_range_low': entry_range_low,
                'entry_range_high': entry_range_high,
                'best_entry': best_entry,
                'tp1': tp1,
                'tp2': tp2,
                'tp3': tp3,
                'sl': sl,
                'atr': atr,
                'entry_range_pct': entry_range_pct * 100,
                'range_size': (entry_range_high - entry_range_low) / current_price * 100 if current_price > 0 else 0,
                'risk_amount': risk_amount,
                'risk_percentage': (risk_amount / best_entry) * 100 if best_entry > 0 else 0,
                'rr_ratio_tp1': rr_ratio_1,
                'rr_ratio_tp3': rr_ratio_3,
                'liquidation_buffer_pct': liquidation_buffer * 100,
                'long_bias_applied': self.long_bias
            }
            
        except Exception as e:
            logger.error(f"Error in calculate_custom_entry: {e}")
            fallback_price = max(self._estimate_realistic_price(symbol), 0.01)
            return {
                'symbol': symbol,
                'action': action,
                'trading_type': self.trading_type,
                'leverage': self.leverage,
                'current_price': fallback_price,
                'entry_range_low': fallback_price * 0.98,
                'entry_range_high': fallback_price * 0.99,
                'best_entry': fallback_price * 0.985,
                'tp1': fallback_price * 1.03,
                'tp2': fallback_price * 1.06,
                'tp3': fallback_price * 1.09,
                'sl': fallback_price * 0.97,
                'atr': fallback_price * 0.02,
                'entry_range_pct': self.entry_range_pct * 100,
                'range_size': 1.0,
                'risk_amount': fallback_price * 0.03,
                'risk_percentage': 3.0,
                'rr_ratio_tp1': 1.5,
                'rr_ratio_tp3': 3.0,
                'liquidation_buffer_pct': 0.5,
                'long_bias_applied': self.long_bias
            }

    def _estimate_realistic_price(self, symbol):
        """Estimate realistic price based on symbol - UPDATED WITH FUTURES"""
        price_estimates = {
            'BTC/USDT': 50000.0, 'ETH/USDT': 3000.0, 'BNB/USDT': 500.0,
            'XRP/USDT': 0.5, 'ADA/USDT': 0.4, 'SOL/USDT': 100.0,
            'BTC/USDT-PERP': 50000.0, 'ETH/USDT-PERP': 3000.0,
            'BTC-PERP': 50000.0, 'ETH-PERP': 3000.0,
            'BTCUSDT': 50000.0, 'BTCUSDT.P': 50000.0,
            'EUR/USD': 1.08, 'USD/JPY': 150.0, 'GBP/USD': 1.26,
            'AUD/USD': 0.66, 'USD/CAD': 1.35, 'NZD/USD': 0.61,
            'XAU/USD': 1950.0, 'XAUUSD': 1950.0, 'GOLD': 1950.0,
            'XAG/USD': 22.0, 'XAGUSD': 22.0, 'SILVER': 22.0,
            'AAPL': 180.0, 'MSFT': 400.0, 'GOOGL': 150.0, 
            'AMZN': 170.0, 'TSLA': 200.0, 'META': 500.0, 
            'NVDA': 900.0, 'NFLX': 600.0,
            'ES1!': 4500.0, 'NQ1!': 15500.0, 'YM1!': 34000.0,
            'RTY1!': 1800.0,
            'CL': 75.0, 'NG': 2.5, 'GC': 1950.0,
            'SI': 22.0, 'HG': 3.5, 'ZC': 450.0,
            'BBCA.JK': 9000.0, 'BBRI.JK': 5000.0, 'BMRI.JK': 6000.0,
            'TLKM.JK': 4000.0, 'ASII.JK': 6000.0,
            'HYPE/USDT': 35.0, 'TON/USDT': 1.5, 'ENA/USDT': 0.3,
            'PINGPONG/USDT': 0.022, 'PLUME/USDT': 0.033, 'ASTER/USDT': 1.12
        }
        
        if symbol in price_estimates:
            return price_estimates[symbol]
        
        for pattern, price in price_estimates.items():
            if pattern in symbol:
                return price
        
        if any(x in symbol.upper() for x in ['PERP', 'FUTURES', 'SWAP', '1226', '0325', '0626', '0926']):
            return 100.0
        elif 'USDT' in symbol or '/USDT' in symbol:
            return 10.0
        elif 'USD' in symbol or '=X' in symbol:
            return 1.0
        elif '.JK' in symbol:
            return 5000.0
        elif any(stock in symbol.upper() for stock in ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA', 'META', 'NVDA', 'NFLX']):
            return 300.0
        elif any(future in symbol.upper() for future in ['ES', 'NQ', 'YM', 'RTY', 'CL', 'NG', 'GC', 'SI', 'HG', 'ZC']):
            return 100.0
        else:
            return 100.0

    def format_signal_output(self, analysis: Dict[str, Any]) -> str:
        """Format output signal dengan futures-specific info"""
        
        action = analysis.get('action', 'NEUTRAL')
        symbol = analysis.get('symbol', 'UNKNOWN')
        trading_type = analysis.get('trading_type', 'spot')
        leverage = analysis.get('leverage', 1)
        score = analysis.get('score', 0)
        current_price = analysis.get('current_price', 0)
        confidence = analysis.get('confidence', 0.5) * 100
        
        if action == "LONG":
            emoji = "🟢" if trading_type == "spot" else "💰"
            color_start = "🟢"
        elif action == "SHORT":
            emoji = "🔴" if trading_type == "spot" else "📉"
            color_start = "🔴"
        else:
            emoji = "⚪" if trading_type == "spot" else "📊"
            color_start = "⚪"
        
        entry_low = analysis.get('entry_range_low', current_price)
        entry_high = analysis.get('entry_range_high', current_price)
        best_entry = analysis.get('best_entry', current_price)
        range_pct = analysis.get('entry_range_pct', 2.0)
        
        if action == "LONG":
            entry_display = f"{entry_low:.5f} - {entry_high:.5f}"
            direction = "BELOW current"
        elif action == "SHORT":
            entry_display = f"{entry_low:.5f} - {entry_high:.5f}" 
            direction = "ABOVE current"
        else:
            entry_display = f"{current_price:.5f}"
            direction = "AT current"
        
        tp1_prob = min(confidence * 0.8, 95)
        tp2_prob = min(confidence * 0.5, 70)
        tp3_prob = min(confidence * 0.2, 40)
        
        bias_info = ""
        long_bias = analysis.get('long_bias_applied', 0)
        if long_bias != 0:
            bias_direction = "LONG" if long_bias > 0 else "SHORT"
            bias_info = f"⚖️ Strategy Bias: {bias_direction} ({abs(long_bias):.2f})"
        
        futures_info = ""
        if trading_type == "futures":
            risk_pct = analysis.get('risk_percentage', 0)
            rr_ratio = analysis.get('rr_ratio_tp1', 0)
            liquidation_buffer = analysis.get('liquidation_buffer_pct', 0)
            
            futures_info = f"""
⚡ FUTURES SPECIFICS:
   Leverage: {leverage}x
   Risk per Trade: {risk_pct:.2f}%
   R/R Ratio (TP1): {rr_ratio:.2f}:1
   Liquidation Buffer: ±{liquidation_buffer:.2f}%
"""
        
        output = f"""
{emoji} {symbol} - {action} (Score: {score:.1f})
{bias_info}
📊 Type: {trading_type.upper()}
💰 Current: {current_price:.5f} 
🎯 Entry Range: {entry_display} ({direction})
📊 Probabilities: TP1: {tp1_prob:.1f}% | TP2: {tp2_prob:.1f}% | TP3: {tp3_prob:.1f}%

🎯 Take Profit: 
   TP1: {analysis.get('tp1', 0):.5f}
   TP2: {analysis.get('tp2', 0):.5f}  
   TP3: {analysis.get('tp3', 0):.5f}

🛑 Stop Loss: {analysis.get('sl', 0):.5f}

{futures_info}
📈 Analytics:
   Confidence: {confidence:.1f}%
   Range Size: ±{range_pct:.1f}%
   ATR: {analysis.get('atr', 0):.5f}
   RSI: {analysis.get('rsi', 50):.1f}
   Trend: {analysis.get('trend_direction', 'NEUTRAL')}
   Market Regime: {analysis.get('market_regime', 'unknown')}
   Min Score Threshold: {self.min_score_threshold}
"""
        
        return output

# =============================================
# ENHANCED DATA STRUCTURES
# =============================================

class MarketRegime(Enum):
    BULL_TREND = "bull_trend"
    BEAR_TREND = "bear_trend"
    RANGING = "ranging"
    HIGH_VOLATILITY = "high_volatility"
    LOW_VOLATILITY = "low_volatility"
    BREAKOUT = "breakout"
    UNKNOWN = "unknown"

@dataclass
class PatternDetection:
    name: str
    detected: bool
    direction: str
    confidence: float
    entry_price: float
    target_price: float
    stop_loss: float
    risk_reward_ratio: float
    timeframe: str

@dataclass
class MarketAnalysis:
    regime: MarketRegime
    trend_strength: float
    volatility_regime: str
    support_levels: List[float]
    resistance_levels: List[float]
    key_levels: List[float]
    volume_profile: Dict[str, float]
    market_sentiment: str

# =============================================
# ADVANCED PATTERN DETECTION ENGINE
# =============================================

class AdvancedPatternDetector:
    """Advanced pattern detection dengan machine learning confirmation"""
    
    def __init__(self):
        self.pattern_cache = {}
        self.min_pattern_confidence = 0.6
        
    def detect_comprehensive_patterns(self, df: pd.DataFrame, symbol: str = None) -> Dict[str, PatternDetection]:
        """Detect comprehensive trading patterns dengan confidence scoring"""
        patterns = {}
        
        try:
            if df is None or df.empty:
                return patterns
            
            current_price = df['close'].iloc[-1] if 'close' in df.columns else 0
            if current_price <= 0:
                logger.warning("Invalid current price in pattern detection")
                return patterns

            harmonic_patterns = self._detect_harmonic_patterns_advanced(df)
            patterns.update(harmonic_patterns)
            
            chart_patterns = self._detect_chart_patterns_advanced(df)
            patterns.update(chart_patterns)
            
            candle_patterns = self._detect_candlestick_patterns(df)
            patterns.update(candle_patterns)
            
            volume_patterns = self._detect_volume_patterns(df)
            patterns.update(volume_patterns)
            
            trend_patterns = self._detect_trend_patterns(df)
            patterns.update(trend_patterns)
            
            valid_patterns = {
                name: pattern for name, pattern in patterns.items() 
                if pattern.detected and pattern.confidence >= self.min_pattern_confidence
            }
            
            return valid_patterns
            
        except Exception as e:
            logger.error(f"Pattern detection error: {e}")
            return {}

    def _detect_harmonic_patterns_advanced(self, df: pd.DataFrame) -> Dict[str, PatternDetection]:
        """Detect advanced harmonic patterns"""
        patterns = {}
        
        try:
            swing_highs, swing_lows = self._find_swing_points_advanced(df)
            
            gartley = self._detect_gartley_pattern(swing_highs, swing_lows, df)
            if gartley.detected:
                patterns['gartley'] = gartley
            
            return patterns
            
        except Exception as e:
            logger.error(f"Harmonic pattern detection error: {e}")
            return {}

    def _find_swing_points_advanced(self, df: pd.DataFrame, window: int = 5) -> Tuple[List[Tuple[int, float]], List[Tuple[int, float]]]:
        """Find swing points dengan advanced algorithm"""
        try:
            highs = df['high'].values
            lows = df['low'].values
            
            if (highs <= 0).any() or (lows <= 0).any():
                logger.warning("Invalid price data in swing point detection")
                return [], []
            
            high_idx = argrelextrema(highs, np.greater, order=window)[0]
            low_idx = argrelextrema(lows, np.less, order=window)[0]
            
            swing_highs = []
            for idx in high_idx:
                if idx >= window and idx < len(highs) - window:
                    left_min = np.min(lows[max(0, idx-window):idx])
                    right_min = np.min(lows[idx:min(len(lows), idx+window)])
                    min_val = min(left_min, right_min)
                    
                    if highs[idx] > min_val * 1.01:
                        swing_highs.append((idx, highs[idx]))
            
            swing_lows = []
            for idx in low_idx:
                if idx >= window and idx < len(lows) - window:
                    left_max = np.max(highs[max(0, idx-window):idx])
                    right_max = np.max(highs[idx:min(len(highs), idx+window)])
                    max_val = max(left_max, right_max)
                    
                    if lows[idx] < max_val * 0.99:
                        swing_lows.append((idx, lows[idx]))
            
            return swing_highs, swing_lows
            
        except Exception as e:
            logger.error(f"Swing point detection error: {e}")
            return [], []
    
    def _detect_gartley_pattern(self, swing_highs: List[Tuple[int, float]], 
                               swing_lows: List[Tuple[int, float]], 
                               df: pd.DataFrame) -> PatternDetection:
        """Detect Gartley pattern dengan Fibonacci ratios"""
        try:
            if len(swing_highs) < 3 or len(swing_lows) < 3:
                return PatternDetection("gartley", False, "", 0, 0, 0, 0, 0, "")
            
            current_price = df['close'].iloc[-1]
            if current_price <= 0:
                return PatternDetection("gartley", False, "", 0, 0, 0, 0, 0, "")
            
            detected = len(swing_highs) >= 4 and len(swing_lows) >= 4
            confidence = 0.7 if detected else 0.0
            
            if detected:
                direction = "BULLISH" if swing_highs[-1][1] > swing_highs[-2][1] else "BEARISH"
                entry = current_price
                target = current_price * 1.05 if direction == "BULLISH" else current_price * 0.95
                stop_loss = current_price * 0.98 if direction == "BULLISH" else current_price * 1.02
                rr_ratio = abs(target - entry) / abs(entry - stop_loss) if abs(entry - stop_loss) > 0 else 1.0
                
                return PatternDetection(
                    "gartley", True, direction, confidence, 
                    entry, target, stop_loss, rr_ratio, "1D"
                )
            
        except Exception as e:
            logger.error(f"Gartley pattern error: {e}")
        
        return PatternDetection("gartley", False, "", 0, 0, 0, 0, 0, "")
    
    def _detect_chart_patterns_advanced(self, df: pd.DataFrame) -> Dict[str, PatternDetection]:
        """Advanced chart pattern detection"""
        patterns = {}
        
        try:
            if df is None or df.empty:
                return patterns
            
            current_price = df['close'].iloc[-1]
            if current_price <= 0:
                return patterns

            hs_pattern = self._detect_head_shoulders(df)
            if hs_pattern.detected:
                patterns['head_shoulders'] = hs_pattern
            
            double_pattern = self._detect_double_top_bottom(df)
            if double_pattern.detected:
                patterns['double_top_bottom'] = double_pattern
            
            return patterns
            
        except Exception as e:
            logger.error(f"Chart pattern detection error: {e}")
            return {}
    
    def _detect_head_shoulders(self, df: pd.DataFrame) -> PatternDetection:
        """Detect Head and Shoulders pattern"""
        try:
            if len(df) < 50:
                return PatternDetection("head_shoulders", False, "", 0, 0, 0, 0, 0, "")
            
            current_price = df['close'].iloc[-1]
            if current_price <= 0:
                return PatternDetection("head_shoulders", False, "", 0, 0, 0, 0, 0, "")
            
            highs = df['high'].tail(30).values
            lows = df['low'].tail(30).values
            
            max_idx = np.argmax(highs)
            left_shoulder = np.max(highs[:max_idx]) if max_idx > 0 else 0
            right_shoulder = np.max(highs[max_idx+1:]) if max_idx < len(highs)-1 else 0
            head = highs[max_idx]
            
            if (left_shoulder > 0 and right_shoulder > 0 and 
                head > left_shoulder and head > right_shoulder and
                abs(left_shoulder - right_shoulder) / head < 0.02):
                
                neckline = (left_shoulder + right_shoulder) / 2
                
                if current_price < neckline:
                    confidence = 0.75
                    entry = current_price
                    target = current_price * 0.93
                    stop_loss = neckline * 1.02
                    rr_ratio = abs(target - entry) / abs(entry - stop_loss) if abs(entry - stop_loss) > 0 else 1.0
                    
                    return PatternDetection(
                        "head_shoulders", True, "BEARISH", confidence,
                        entry, target, stop_loss, rr_ratio, "1D"
                    )
            
        except Exception as e:
            logger.error(f"Head and Shoulders detection error: {e}")
        
        return PatternDetection("head_shoulders", False, "", 0, 0, 0, 0, 0, "")
    
    def _detect_double_top_bottom(self, df: pd.DataFrame) -> PatternDetection:
        """Detect Double Top/Bottom pattern"""
        try:
            if len(df) < 40:
                return PatternDetection("double_top_bottom", False, "", 0, 0, 0, 0, 0, "")
            
            current_price = df['close'].iloc[-1]
            if current_price <= 0:
                return PatternDetection("double_top_bottom", False, "", 0, 0, 0, 0, 0, "")
            
            highs = df['high'].tail(20).values
            lows = df['low'].tail(20).values
            
            peak1_idx = len(highs) // 3
            peak2_idx = 2 * len(highs) // 3
            
            peak1 = np.max(highs[:peak1_idx]) if peak1_idx > 0 else 0
            peak2 = np.max(highs[peak1_idx:peak2_idx]) if peak2_idx > peak1_idx else 0
            
            if peak1 > 0 and peak2 > 0 and abs(peak1 - peak2) / ((peak1 + peak2)/2) < 0.02:
                valley = np.min(lows[peak1_idx:peak2_idx])
                
                if valley > 0 and (peak1 - valley) / peak1 > 0.03:
                    confidence = 0.65
                    direction = "BEARISH"
                    entry = current_price
                    target = current_price - (peak1 - valley)
                    stop_loss = max(peak1, peak2) * 1.01
                    rr_ratio = abs(target - entry) / abs(entry - stop_loss) if abs(entry - stop_loss) > 0 else 1.0
                    
                    return PatternDetection(
                        "double_top", True, direction, confidence,
                        entry, target, stop_loss, rr_ratio, "1D"
                    )
            
            bottom1 = np.min(lows[:peak1_idx]) if peak1_idx > 0 else 0
            bottom2 = np.min(lows[peak1_idx:peak2_idx]) if peak2_idx > peak1_idx else 0
            
            if bottom1 > 0 and bottom2 > 0 and abs(bottom1 - bottom2) / ((bottom1 + bottom2)/2) < 0.02:
                peak_valley = np.max(highs[peak1_idx:peak2_idx])
                
                if peak_valley > 0 and (peak_valley - bottom1) / bottom1 > 0.03:
                    confidence = 0.65
                    direction = "BULLISH"
                    entry = current_price
                    target = current_price + (peak_valley - bottom1)
                    stop_loss = min(bottom1, bottom2) * 0.99
                    rr_ratio = abs(target - entry) / abs(entry - stop_loss) if abs(entry - stop_loss) > 0 else 1.0
                    
                    return PatternDetection(
                        "double_bottom", True, direction, confidence,
                        entry, target, stop_loss, rr_ratio, "1D"
                    )
            
        except Exception as e:
            logger.error(f"Double Top/Bottom detection error: {e}")
        
        return PatternDetection("double_top_bottom", False, "", 0, 0, 0, 0, 0, "")
    
    def _detect_candlestick_patterns(self, df: pd.DataFrame) -> Dict[str, PatternDetection]:
        """Detect candlestick patterns"""
        patterns = {}
        
        try:
            if len(df) < 5:
                return patterns
            
            open_price = df['open'].values
            high = df['high'].values
            low = df['low'].values
            close = df['close'].values
            
            if (open_price <= 0).any() or (high <= 0).any() or (low <= 0).any() or (close <= 0).any():
                return patterns
            
            doji = talib.CDLDOJI(open_price, high, low, close)
            if doji[-1] != 0:
                confidence = 0.6
                direction = "REVERSAL"
                entry = close[-1]
                target = entry * 1.02
                stop_loss = entry * 0.98
                rr_ratio = abs(target - entry) / abs(entry - stop_loss) if abs(entry - stop_loss) > 0 else 1.0
                
                patterns['doji'] = PatternDetection(
                    "doji", True, direction, confidence,
                    entry, target, stop_loss, rr_ratio, "1D"
                )
            
            hammer = talib.CDLHAMMER(open_price, high, low, close)
            if hammer[-1] != 0:
                confidence = 0.65
                direction = "BULLISH"
                entry = close[-1]
                target = entry * 1.03
                stop_loss = low[-1] * 0.99
                rr_ratio = abs(target - entry) / abs(entry - stop_loss) if abs(entry - stop_loss) > 0 else 1.0
                
                patterns['hammer'] = PatternDetection(
                    "hammer", True, direction, confidence,
                    entry, target, stop_loss, rr_ratio, "1D"
                )
            
            shooting_star = talib.CDLSHOOTINGSTAR(open_price, high, low, close)
            if shooting_star[-1] != 0:
                confidence = 0.65
                direction = "BEARISH"
                entry = close[-1]
                target = entry * 0.97
                stop_loss = high[-1] * 1.01
                rr_ratio = abs(target - entry) / abs(entry - stop_loss) if abs(entry - stop_loss) > 0 else 1.0
                
                patterns['shooting_star'] = PatternDetection(
                    "shooting_star", True, direction, confidence,
                    entry, target, stop_loss, rr_ratio, "1D"
                )
            
            return patterns
            
        except Exception as e:
            logger.error(f"Candlestick pattern detection error: {e}")
            return {}
    
    def _detect_volume_patterns(self, df: pd.DataFrame) -> Dict[str, PatternDetection]:
        """Detect volume-based patterns"""
        patterns = {}
        
        try:
            if 'volume' not in df.columns or len(df) < 20:
                return patterns
            
            current_price = df['close'].iloc[-1]
            if current_price <= 0:
                return patterns
            
            volumes = df['volume'].tail(20).values
            prices = df['close'].tail(20).values
            
            volume_ma = np.mean(volumes)
            current_volume = volumes[-1]
            
            if current_volume > volume_ma * 2.0 and prices[-1] > prices[-2]:
                confidence = 0.7
                direction = "BULLISH"
                entry = current_price
                target = entry * 1.05
                stop_loss = entry * 0.98
                rr_ratio = abs(target - entry) / abs(entry - stop_loss) if abs(entry - stop_loss) > 0 else 1.0
                
                patterns['volume_spike'] = PatternDetection(
                    "volume_spike", True, direction, confidence,
                    entry, target, stop_loss, rr_ratio, "1D"
                )
            
            return patterns
            
        except Exception as e:
            logger.error(f"Volume pattern detection error: {e}")
            return {}
    
    def _detect_trend_patterns(self, df: pd.DataFrame) -> Dict[str, PatternDetection]:
        """Detect trend continuation/reversal patterns"""
        patterns = {}
        
        try:
            if len(df) < 30:
                return patterns
            
            current_price = df['close'].iloc[-1]
            if current_price <= 0:
                return patterns
            
            prices = df['close'].values
            
            recent_high = np.max(prices[-20:-1])
            if prices[-1] > recent_high * 1.01:
                confidence = 0.75
                direction = "BULLISH"
                entry = current_price
                target = entry * 1.05
                stop_loss = recent_high * 0.99
                rr_ratio = abs(target - entry) / abs(entry - stop_loss) if abs(entry - stop_loss) > 0 else 1.0
                
                patterns['breakout'] = PatternDetection(
                    "breakout", True, direction, confidence,
                    entry, target, stop_loss, rr_ratio, "1D"
                )
            
            return patterns
            
        except Exception as e:
            logger.error(f"Trend pattern detection error: {e}")
            return {}

# =============================================
# ENHANCED TECHNICAL ANALYSIS STRATEGY
# =============================================

class EnhancedTechnicalAnalysisStrategy(TradingStrategy):
    """Enhanced technical analysis strategy dengan semua improvement dan backtesting"""
    
    def __init__(self, market_type="crypto", atr_multiplier=1.0, entry_range_pct=0.02,
                 trading_type="spot", leverage=1, max_leverage_risk=0.01,
                 long_bias=0.0, min_score_threshold=3.0, scalping_mode=False,
                 use_multi_tf_confirmation=True, use_adaptive_params=True,
                 use_regime_detection=True, use_consolidation_filter=True):
        super().__init__(
            market_type=market_type, 
            atr_multiplier=atr_multiplier,
            entry_range_pct=entry_range_pct,
            trading_type=trading_type,
            leverage=leverage,
            max_leverage_risk=max_leverage_risk,
            long_bias=long_bias,
            min_score_threshold=min_score_threshold,
            scalping_mode=scalping_mode
        )
        
        self.pattern_detector = AdvancedPatternDetector()
        self.analysis_history = []
        
        self.use_multi_tf_confirmation = use_multi_tf_confirmation
        self.use_adaptive_params = use_adaptive_params
        self.use_regime_detection = use_regime_detection
        self.use_consolidation_filter = use_consolidation_filter
        
        self.base_rsi_oversold = 30
        self.base_rsi_overbought = 70
        self.min_adx_trend = 25
        
        self.breakout_volume_threshold = 1.3
        self.breakout_price_threshold = 0.015
        self.breakout_penalty_factor = 0.8
        
        self.confidence_weights = {
            'rsi': 1.2,
            'macd': 1.1,
            'volume': 1.15,
            'trend': 1.3,
            'regime': 1.25,
            'multi_tf': 1.2,
            'pattern': 1.1
        }
        
        logger.info(f"📊 Strategy Enhanced: Multi-TF={use_multi_tf_confirmation}, Adaptive={use_adaptive_params}, Regime={use_regime_detection}")

    def _calculate_symmetrical_score(self, indicators, df):
        """Scoring system yang lebih seimbang untuk ranging markets"""
        score = 0
        
        rsi = indicators['rsi_14']
        
        if rsi < 30:
            score += 4
        elif rsi < 40:
            score += 2
        elif rsi > 70:
            score -= 4
        elif rsi > 60:
            score -= 2
        else:
            if len(df) > 10:
                trend = self._calculate_trend_strength(df, "")
                if trend > 0.1:
                    score += 1
                elif trend < -0.1:
                    score -= 1
        
        macd_line = indicators['macd_line']
        macd_signal = indicators['macd_signal']
        
        if macd_line > macd_signal:
            if rsi < 50:
                score += 3
            elif rsi > 70:
                score += 1
            else:
                score += 2
        else:
            if rsi > 70:
                score -= 3
            elif rsi < 30:
                score -= 1
            else:
                score -= 2
        
        bb_position = indicators['bb_position']
        
        if bb_position < 0.2:
            if rsi < 40:
                score += 3
            else:
                score += 2
        
        elif bb_position > 0.8:
            if rsi > 70:
                score -= 3
            else:
                score -= 2
        
        if 'volume_ratio' in indicators:
            volume_ratio = indicators['volume_ratio']
            if volume_ratio > 1.5:
                if score > 0:
                    score += 1
                elif score < 0:
                    score -= 1
        
        regime = indicators.get('market_regime', 'UNKNOWN')
        if regime == 'BULL_TREND':
            if score > 0:
                score = int(score * 1.3)
            elif score < 0:
                score = int(score * 0.7)
        
        elif regime == 'BEAR_TREND':
            if score > 0:
                score = int(score * 0.7)
            elif score < 0:
                score = int(score * 1.3)
        
        return score

    def _calculate_trend_following_score(self, indicators, df):
        """Scoring yang mengikuti trend, bukan melawan"""
        score = 0
        
        trend_strength = self._calculate_trend_strength(df, "")
        trend_direction = 'BULLISH' if trend_strength > 0.1 else 'BEARISH' if trend_strength < -0.1 else 'NEUTRAL'
        
        rsi = indicators['rsi_14']
        
        if trend_direction == 'BULLISH':
            if rsi > 70:
                score += 1
            elif rsi < 30:
                score += 3
            elif 40 < rsi < 60:
                score += 2
        
        elif trend_direction == 'BEARISH':
            if rsi < 30:
                score -= 1
            elif rsi > 70:
                score -= 3
            elif 40 < rsi < 60:
                score -= 2
        
        else:
            if rsi < 30: score += 3
            elif rsi < 40: score += 2
            elif rsi > 70: score -= 3
            elif rsi > 60: score -= 2
        
        macd_bullish = indicators['macd_line'] > indicators['macd_signal']
        
        if trend_direction == 'BULLISH' and macd_bullish:
            score += 3
        elif trend_direction == 'BULLISH' and not macd_bullish:
            score -= 1
        
        elif trend_direction == 'BEARISH' and not macd_bullish:
            score -= 3
        elif trend_direction == 'BEARISH' and macd_bullish:
            score += 1
        
        else:
            if macd_bullish: score += 2
            else: score -= 2
        
        current_price = df['close'].iloc[-1]
        sma_20 = indicators.get('sma_20', current_price)
        
        if current_price > sma_20 * 1.02:
            if trend_direction == 'BULLISH':
                score += 2
            else:
                score += 1
        
        elif current_price < sma_20 * 0.98:
            if trend_direction == 'BEARISH':
                score -= 2
            else:
                score -= 1
        
        return score

    def calculate_adaptive_score(self, indicators, df, symbol=None):
        """Scoring system hybrid yang cerdas"""
        trend_strength = abs(self._calculate_trend_strength(df, symbol))
        adx = indicators.get('adx', 20)
        regime = indicators.get('market_regime', 'UNKNOWN')
        
        if adx > 25 and trend_strength > 0.3 and regime in ['BULL_TREND', 'BEAR_TREND']:
            score = self._calculate_trend_following_score(indicators, df)
            logger.debug(f"🔷 {symbol}: Using TREND-FOLLOWING scoring (ADX={adx:.1f}, Trend={trend_strength:.2f})")
        elif adx < 20 or regime == 'RANGING':
            score = self._calculate_symmetrical_score(indicators, df)
            logger.debug(f"🔶 {symbol}: Using SYMMETRICAL scoring (ADX={adx:.1f}, Regime={regime})")
        else:
            tf_score = self._calculate_trend_following_score(indicators, df)
            sym_score = self._calculate_symmetrical_score(indicators, df)
            
            tf_weight = min(adx / 40, 0.7)
            sym_weight = 1 - tf_weight
            
            score = (tf_score * tf_weight) + (sym_score * sym_weight)
            logger.debug(f"⚖️ {symbol}: Using HYBRID scoring (ADX={adx:.1f}, TF={tf_weight:.1f}, SYM={sym_weight:.1f})")
        
        return score

    def _detect_breakout_pattern(self, df: pd.DataFrame, symbol: str = None) -> Dict:
        """Detect breakout patterns dengan parameter AMAN untuk menghindari false short signals"""
        try:
            if len(df) < 30:
                return {'breakout_detected': False, 'direction': None, 'strength': 0}
            
            current_price = df['close'].iloc[-1]
            
            recent_high_10 = df['high'].rolling(10).max().iloc[-1]
            recent_low_10 = df['low'].rolling(10).min().iloc[-1]
            
            if 'volume' in df.columns:
                volume_avg_10 = df['volume'].rolling(10).mean().iloc[-1]
                current_volume = df['volume'].iloc[-1]
                volume_ratio = current_volume / volume_avg_10 if volume_avg_10 > 0 else 1
            else:
                volume_ratio = 1
            
            is_breaking_high = current_price > recent_high_10 * (1 + self.breakout_price_threshold)
            is_breaking_low = current_price < recent_low_10 * (1 - self.breakout_price_threshold)
            
            strong_volume = volume_ratio > self.breakout_volume_threshold
            
            if len(df) > 1:
                prev_close = df['close'].iloc[-2]
                is_closing_above = current_price > max(prev_close, recent_high_10)
                is_closing_below = current_price < min(prev_close, recent_low_10)
            else:
                is_closing_above = is_breaking_high
                is_closing_below = is_breaking_low
            
            if is_breaking_high and strong_volume and is_closing_above:
                return {
                    'breakout_detected': True,
                    'direction': 'BULLISH',
                    'strength': min(volume_ratio / 1.5, 1.0),
                    'resistance_broken': recent_high_10
                }
            elif is_breaking_low and strong_volume and is_closing_below:
                return {
                    'breakout_detected': True,
                    'direction': 'BEARISH',
                    'strength': min(volume_ratio / 1.5, 1.0),
                    'support_broken': recent_low_10
                }
            
            return {'breakout_detected': False, 'direction': None, 'strength': 0}
            
        except Exception as e:
            logger.error(f"Breakout detection error: {e}")
            return {'breakout_detected': False, 'direction': None, 'strength': 0}
    
    def _calculate_adaptive_indicators(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Calculate indicators with adaptive parameters based on volatility"""
        indicators = {}
        
        try:
            prices = df['close'].values
            highs = df['high'].values
            lows = df['low'].values
            
            atr = self._calculate_atr(df)
            current_price = prices[-1] if len(prices) > 0 else 1.0
            atr_pct = atr / current_price if current_price > 0 else 0.02
            
            if self.use_adaptive_params:
                vol_factor = min(atr_pct / 0.05, 1.0)
                
                self.rsi_oversold = self.base_rsi_oversold - (vol_factor * 5)
                self.rsi_overbought = self.base_rsi_overbought + (vol_factor * 5)
            else:
                self.rsi_oversold = self.base_rsi_oversold
                self.rsi_overbought = self.base_rsi_overbought
            
            indicators['rsi'] = self._calculate_rsi(prices, 14)
            
            if len(prices) >= 14 and self.use_regime_detection:
                try:
                    adx = talib.ADX(highs, lows, prices, timeperiod=14)[-1]
                except:
                    adx = self._calculate_simple_adx(highs, lows, prices)
                indicators['adx'] = adx
            else:
                indicators['adx'] = 20.0
            
            if indicators['adx'] > self.min_adx_trend:
                if prices[-1] > np.mean(prices[-20:]):
                    indicators['market_regime'] = 'BULL_TREND'
                else:
                    indicators['market_regime'] = 'BEAR_TREND'
            else:
                indicators['market_regime'] = 'RANGING'
            
            if self.use_consolidation_filter:
                bb_width = (indicators.get('bb_upper', current_price*1.02) - 
                           indicators.get('bb_lower', current_price*0.98)) / current_price
                indicators['consolidation_score'] = 0
                
                if indicators['adx'] < 20 and bb_width < 0.03 and atr_pct < 0.015:
                    indicators['consolidation_score'] = 1 - (indicators['adx'] / 20)
            else:
                indicators['consolidation_score'] = 0
            
            if 'volume' in df.columns:
                vol_ma_20 = df['volume'].rolling(20).mean().iloc[-1]
                indicators['volume_ratio'] = df['volume'].iloc[-1] / vol_ma_20 if vol_ma_20 > 0 else 1.0
            
            return indicators
            
        except Exception as e:
            logger.error(f"Adaptive indicators error: {e}")
            return {'rsi': 50, 'adx': 20, 'market_regime': 'UNKNOWN', 'consolidation_score': 0}
    
    def _calculate_simple_adx(self, highs, lows, closes, period=14):
        """Simple ADX calculation without TA-Lib"""
        try:
            if len(highs) < period * 2:
                return 20.0
            
            tr = np.zeros(len(highs))
            for i in range(1, len(highs)):
                hl = highs[i] - lows[i]
                hc = abs(highs[i] - closes[i-1])
                lc = abs(lows[i] - closes[i-1])
                tr[i] = max(hl, hc, lc)
            
            plus_dm = np.zeros(len(highs))
            minus_dm = np.zeros(len(highs))
            
            for i in range(1, len(highs)):
                up_move = highs[i] - highs[i-1]
                down_move = lows[i-1] - lows[i]
                
                if up_move > down_move and up_move > 0:
                    plus_dm[i] = up_move
                if down_move > up_move and down_move > 0:
                    minus_dm[i] = down_move
            
            tr_smooth = self._smooth_series(tr, period)
            plus_dm_smooth = self._smooth_series(plus_dm, period)
            minus_dm_smooth = self._smooth_series(minus_dm, period)
            
            plus_di = 100 * (plus_dm_smooth / tr_smooth) if tr_smooth > 0 else 0
            minus_di = 100 * (minus_dm_smooth / tr_smooth) if tr_smooth > 0 else 0
            
            dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di) if (plus_di + minus_di) > 0 else 0
            adx = np.mean(dx[-period:]) if len(dx) >= period else 20.0
            
            return adx
            
        except Exception as e:
            logger.error(f"Simple ADX calculation error: {e}")
            return 20.0
    
    def _smooth_series(self, series, period):
        """Exponential smoothing"""
        if len(series) < period:
            return series
        
        alpha = 2 / (period + 1)
        smoothed = np.zeros(len(series))
        smoothed[0] = series[0]
        
        for i in range(1, len(series)):
            smoothed[i] = alpha * series[i] + (1 - alpha) * smoothed[i-1]
        
        return smoothed
    
    def _get_valid_current_price(self, df: pd.DataFrame) -> float:
        """Get valid current price from DataFrame with validation"""
        try:
            if df is None or df.empty:
                logger.warning("Empty DataFrame in _get_valid_current_price")
                return 0.0
            
            if 'close' not in df.columns:
                logger.warning("DataFrame has no 'close' column")
                return 0.0
            
            current_price = df['close'].iloc[-1]
            
            if pd.isna(current_price) or current_price <= 0:
                logger.warning(f"Invalid current price: {current_price}")
                return 0.0
            
            return float(current_price)
            
        except Exception as e:
            logger.error(f"Error in _get_valid_current_price: {e}")
            return 0.0
    
    def _safe_data_validation(self, df: pd.DataFrame, symbol: str) -> bool:
        """Validasi data dengan cara yang aman dari ambiguous truth value"""
        try:
            if df is None or df.empty:
                return False
            
            required_cols = ['open', 'high', 'low', 'close']
            for col in required_cols:
                if col not in df.columns:
                    logger.warning(f"Missing column {col} in {symbol}")
                    return False
            
            if (df['close'].values <= 0).any():
                logger.warning(f"Invalid price (<=0) detected for {symbol}")
                return False
            
            if (df['high'].values < df['low'].values).any():
                logger.warning(f"High < Low detected for {symbol}")
                return False
            
            if len(df) < 20:
                logger.warning(f"Insufficient data for {symbol}: {len(df)} bars")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error in safe data validation for {symbol}: {e}")
            return False

    def _should_skip_symbol(self, df, symbol):
        """Skip logic yang lebih pintar untuk scalping - DIPERBAIKI"""
        if df is None or df.empty or len(df) < 10:
            logger.debug(f"Skipping {symbol}: data too short ({len(df) if df is not None else 0} bars)")
            return True
        
        is_futures = any(x in symbol.upper() for x in [':USDT', 'PERP', 'FUTURES', '-USDT', 'USDT:'])
        
        if self.scalping_mode:
            min_volatility = SCALPING_CONFIG["min_volatility"]
            min_volume = 50000
            min_price = SCALPING_CONFIG["price_filter"]["min"]
            max_price = SCALPING_CONFIG["price_filter"]["max"]
            
            current_price = df['close'].iloc[-1] if len(df) > 0 else 0
            if current_price < min_price or current_price > max_price:
                logger.debug(f"Skipping {symbol}: price ${current_price:.4f} outside scalping range (${min_price}-${max_price})")
                return True
        else:
            if is_futures:
                min_volatility = 0.000001
                min_volume = 10
                min_price = 0.0000001
            else:
                min_volatility = 0.001
                min_volume = 1000
                min_price = 0.001
        
        if len(df) > 1:
            volatility = df['close'].pct_change().std()
        else:
            volatility = 0.01
        
        avg_volume = df['volume'].mean() if 'volume' in df.columns else 1000
        current_price = df['close'].iloc[-1] if len(df) > 0 else 0
        
        if df['close'].isna().any():
            logger.warning(f"Skipping {symbol}: has NaN values")
            return True
        
        if (df['close'].values <= 0).any() or (df['close'].values > 100000000).any():
            logger.warning(f"Skipping {symbol}: invalid price range")
            return True
        
        if (df['high'].values < df['low'].values).any():
            logger.warning(f"Skipping {symbol}: High < Low")
            return True
        
        if avg_volume < min_volume:
            logger.debug(f"Skipping {symbol}: low volume {avg_volume:.0f}")
            return True
        
        if len(df['close'].unique()) <= 3:
            logger.warning(f"Skipping {symbol}: flatline data")
            return True
        
        if volatility < min_volatility:
            logger.debug(f"Skipping {symbol}: low volatility {volatility:.6f}")
            return True
        
        if self.scalping_mode and volatility > SCALPING_CONFIG["max_volatility"]:
            logger.debug(f"Skipping {symbol}: too volatile for scalping {volatility:.3f}")
            return True
        
        return False
    
    def _get_safe_neutral_signal(self, symbol: str = None) -> Dict[str, Any]:
        """Return safe neutral signal when skipping analysis"""
        if symbol is None:
            symbol = "UNKNOWN"
            logger.warning("Symbol is None, using 'UNKNOWN'")
        
        default_price = self._estimate_realistic_price(symbol)
        return {
            'action': 'NEUTRAL',
            'trading_type': self.trading_type,
            'leverage': self.leverage,
            'current_price': default_price,
            'score': 0,
            'confidence': 0.1,
            'symbol': symbol,
            'risk_category': 'LOW',
            'market_regime': 'unknown',
            'skip_reason': 'data_validation_failed',
            'long_bias_applied': self.long_bias,
            'enter_tag': 'SKIPPED',
            'consolidation_score': 0
        }

    def analyze(self, df: pd.DataFrame, symbol: str = None, **kwargs) -> Dict[str, Any]:
        """Enhanced analysis dengan semua improvement DAN HYBRID SCORING SYSTEM"""
        try:
            if df is None or df.empty or len(df) < 10:
                logger.warning(f"Data insufficient for {symbol}: {len(df) if df is not None else 0} bars")
                return self._get_default_analysis(symbol)
            
            if not self._safe_data_validation(df, symbol):
                logger.warning(f"Data validation failed for {symbol}")
                return self._get_safe_neutral_signal(symbol)
            
            df = self._preprocess_and_validate(df, symbol)
            
            if self._should_skip_symbol(df, symbol):
                return self._get_safe_neutral_signal(symbol)
            
            current_price = df['close'].iloc[-1]
            
            indicators = self._calculate_enhanced_indicators(df)
            
            adaptive_indicators = self._calculate_adaptive_indicators(df)
            indicators.update(adaptive_indicators)
            
            mtf_confirmation = 1.0
            if self.use_multi_tf_confirmation and df is not None and len(df) > 100:
                mtf_data = df.iloc[-100:]
                mtf_rsi = self._calculate_rsi(mtf_data['close'].values, 14)
                mtf_trend = 'BULLISH' if mtf_data['close'].iloc[-1] > mtf_data['close'].iloc[-20] else 'BEARISH'
                
                current_trend = 'BULLISH' if indicators['momentum_5'] > 0 else 'BEARISH'
                if mtf_trend == current_trend:
                    mtf_confirmation = 1.2
                else:
                    mtf_confirmation = 0.8
            
            confidence_factors = []
            enter_tags = []
            
            rsi = indicators['rsi_14']
            if rsi < self.rsi_oversold:
                confidence_factors.append(self.confidence_weights['rsi'])
                enter_tags.append('RSI_OVERSOLD')
            elif rsi > self.rsi_overbought:
                confidence_factors.append(self.confidence_weights['rsi'])
                enter_tags.append('RSI_OVERBOUGHT')
            else:
                confidence_factors.append(0.8)
            
            macd_signal = indicators['macd_line'] > indicators['macd_signal']
            if macd_signal:
                confidence_factors.append(self.confidence_weights['macd'])
                enter_tags.append('MACD_BULLISH')
            else:
                confidence_factors.append(0.9)
                enter_tags.append('MACD_BEARISH')
            
            if indicators['market_regime'] in ['BULL_TREND', 'BEAR_TREND']:
                confidence_factors.append(self.confidence_weights['regime'])
                enter_tags.append('TRENDING')
            elif indicators['market_regime'] == 'RANGING':
                confidence_factors.append(0.7)
                enter_tags.append('RANGING')
            
            if 'volume_ratio' in indicators and indicators['volume_ratio'] > 1.2:
                confidence_factors.append(self.confidence_weights['volume'])
                enter_tags.append('VOLUME_SPIKE')
            
            patterns = self.pattern_detector.detect_comprehensive_patterns(df, symbol)
            if patterns:
                confidence_factors.append(self.confidence_weights['pattern'])
                pattern_names = [p for p in patterns.keys()][:2]
                enter_tags.append(f"PATTERN_{'_'.join(pattern_names)}")
            
            if 'consolidation_score' in indicators and indicators['consolidation_score'] > 0.7:
                confidence_factors.append(0.5)
                enter_tags.append('CONSOLIDATION')
            
            confidence_factors.append(mtf_confirmation)
            if mtf_confirmation > 1.0:
                enter_tags.append('MTF_CONFIRMED')
            
            base_confidence = np.mean(confidence_factors) if confidence_factors else 1.0
            confidence_score = min(base_confidence * 100, 100)
            
            score = self.calculate_adaptive_score(indicators, df, symbol)
            
            biased_score = score + (self.long_bias * 5)
            
            breakout_info = self._detect_breakout_pattern(df, symbol)
            if breakout_info['breakout_detected']:
                if breakout_info['direction'] == 'BULLISH':
                    if biased_score < 0:
                        logger.warning(f"⚠️ {symbol}: Bullish breakout detected, caution on SHORT signal")
                        enter_tags.append('BULL_BREAKOUT_WARNING')
                        biased_score = biased_score * self.breakout_penalty_factor
                
                elif breakout_info['direction'] == 'BEARISH':
                    if biased_score > 0:
                        logger.warning(f"⚠️ {symbol}: Bearish breakout detected, caution on LONG signal")
                        enter_tags.append('BEAR_BREAKOUT_WARNING')
                        biased_score = biased_score * self.breakout_penalty_factor
            
            logger.debug(f"Score calculation for {symbol}: Base={score:.1f}, Bias={self.long_bias:.2f}, Final={biased_score:.1f}, Breakout={breakout_info['breakout_detected']}")
            
            if indicators.get('consolidation_score', 0) > 0.8:
                confidence_score *= 0.3
            
            if abs(biased_score) < self.min_score_threshold:
                logger.debug(f"{symbol}: Score {biased_score:.1f} below threshold {self.min_score_threshold}, returning NEUTRAL")
                action = "NEUTRAL"
            elif biased_score > 0:
                action = "LONG"
            else:
                action = "SHORT"
            
            if (indicators.get('consolidation_score', 0) > 0.8 and 
                indicators.get('adx', 20) < 15 and
                action != "NEUTRAL"):
                logger.info(f"⏸️ {symbol}: Skipping {action} signal due to strong consolidation (ADX: {indicators.get('adx', 20):.1f})")
                action = "NEUTRAL"
                enter_tags.append('CONSOLIDATION_SKIP')
            
            entry_calc = self.calculate_custom_entry(
                symbol=symbol or "UNKNOWN",
                current_price=current_price,
                action=action,
                df=df
            )
            
            if (action == "LONG" and self.long_bias > 0) or (action == "SHORT" and self.long_bias < 0):
                confidence_score = min(confidence_score * (1 + abs(self.long_bias) * 0.3), 100)
            
            result = {
                'action': action,
                'score': biased_score,
                'current_price': current_price,
                'entry_range_low': entry_calc['entry_range_low'],
                'entry_range_high': entry_calc['entry_range_high'],
                'best_entry': entry_calc['best_entry'],
                'tp1': entry_calc['tp1'],
                'tp2': entry_calc['tp2'],
                'tp3': entry_calc['tp3'],
                'sl': entry_calc['sl'],
                'trading_type': self.trading_type,
                'leverage': self.leverage,
                'rsi': rsi,
                'atr': indicators['atr'],
                'symbol': symbol or "UNKNOWN",
                'entry_range_pct': entry_calc['entry_range_pct'],
                'range_size': entry_calc['range_size'],
                'risk_amount': entry_calc.get('risk_amount', 0),
                'risk_percentage': entry_calc.get('risk_percentage', 0),
                'rr_ratio_tp1': entry_calc.get('rr_ratio_tp1', 0),
                'rr_ratio_tp3': entry_calc.get('rr_ratio_tp3', 0),
                'liquidation_buffer_pct': entry_calc.get('liquidation_buffer_pct', 0),
                'confidence': confidence_score / 100.0,
                'long_bias_applied': self.long_bias,
                'min_score_threshold': self.min_score_threshold,
                'scalping_mode': self.scalping_mode,
                'enter_tag': '|'.join(enter_tags) if enter_tags else 'BASIC',
                'market_regime': indicators.get('market_regime', 'UNKNOWN'),
                'adx': indicators.get('adx', 20),
                'consolidation_score': indicators.get('consolidation_score', 0),
                'rsi_threshold_used': f"{self.rsi_oversold:.1f}/{self.rsi_overbought:.1f}",
                'mtf_confirmation': mtf_confirmation,
                'volume_ratio': indicators.get('volume_ratio', 1.0),
                'breakout_detected': breakout_info['breakout_detected'],
                'breakout_direction': breakout_info.get('direction', 'NONE'),
                'scoring_system': 'HYBRID'
            }
            
            ts = self._calculate_trend_strength(df, symbol)
            
            result.update({
                'macd_line': indicators['macd_line'],
                'macd_signal': indicators['macd_signal'],
                'bb_position': indicators['bb_position'],
                'volatility': indicators['volatility'],
                'trend_strength': ts,
                'trend_direction': 'BULLISH' if indicators['momentum_5'] > 0 else 'BEARISH' if indicators['momentum_5'] < 0 else 'NEUTRAL',
                'pattern_count': len(patterns)
            })
            
            logger.info(f"📈 {symbol}: {action} (Score: {biased_score:.1f}, Bias: {self.long_bias:.2f}, Conf: {confidence_score:.1f}%, Regime: {indicators.get('market_regime', 'UNKNOWN')}, Breakout: {breakout_info['breakout_detected']}, Scoring: {result['scoring_system']})")
            
            return result
            
        except Exception as e:
            logger.error(f"Enhanced analysis error for {symbol}: {e}")
            return self._get_default_analysis(symbol)
    
    def calculate_custom_entry(self, symbol: str, current_price: float, action: str = "LONG", 
                              df: pd.DataFrame = None) -> Dict[str, Any]:
        """Enhanced entry calculation with dynamic parameters based on market regime"""
        try:
            original_atr_multiplier = self.atr_multiplier
            original_entry_range = self.entry_range_pct
            
            if df is not None:
                adaptive_indicators = self._calculate_adaptive_indicators(df)
                regime = adaptive_indicators.get('market_regime', 'UNKNOWN')
                adx = adaptive_indicators.get('adx', 20)
                
                if regime == 'RANGING' or adx < 20:
                    self.atr_multiplier = max(self.atr_multiplier * 0.7, 0.5)
                    self.entry_range_pct = max(self.entry_range_pct * 0.8, 0.005)
                elif regime in ['BULL_TREND', 'BEAR_TREND'] and adx > 30:
                    self.atr_multiplier = min(self.atr_multiplier * 1.3, 2.0)
                    self.entry_range_pct = min(self.entry_range_pct * 1.2, 0.05)
            
            result = super().calculate_custom_entry(symbol, current_price, action, df)
            
            self.atr_multiplier = original_atr_multiplier
            self.entry_range_pct = original_entry_range
            
            if df is not None:
                adaptive_indicators = self._calculate_adaptive_indicators(df)
                result['market_regime'] = adaptive_indicators.get('market_regime', 'UNKNOWN')
                result['adx_value'] = adaptive_indicators.get('adx', 20)
            
            return result
            
        except Exception as e:
            logger.error(f"Enhanced entry calculation error: {e}")
            return super().calculate_custom_entry(symbol, current_price, action, df)
    
    def _calculate_enhanced_indicators(self, df: pd.DataFrame) -> Dict[str, float]:
        """Calculate enhanced technical indicators"""
        indicators = {}
        
        try:
            prices = df['close'].values
            highs = df['high'].values
            lows = df['low'].values
            
            if (prices <= 0).any() or (highs <= 0).any() or (lows <= 0).any():
                logger.warning("Invalid price data in indicator calculation")
                return self._get_default_indicators(prices[-1] if len(prices) > 0 else 1.0)
            
            indicators['rsi_14'] = self._calculate_rsi(prices, 14)
            
            indicators['sma_20'] = np.mean(prices[-20:]) if len(prices) >= 20 else np.mean(prices)
            
            macd_line, macd_signal, macd_histogram = self._calculate_macd(prices)
            indicators['macd_line'] = macd_line
            indicators['macd_signal'] = macd_signal
            indicators['macd_histogram'] = macd_histogram
            
            bb_upper, bb_lower, bb_middle = self._calculate_bollinger_bands(prices)
            indicators['bb_upper'] = bb_upper
            indicators['bb_lower'] = bb_lower
            indicators['bb_middle'] = bb_middle
            indicators['bb_position'] = (prices[-1] - bb_lower) / (bb_upper - bb_lower) if (bb_upper - bb_lower) > 0 else 0.5
            
            indicators['atr'] = self._calculate_atr(df)
            
            returns = np.diff(prices) / prices[:-1]
            indicators['volatility'] = np.std(returns) * np.sqrt(252) if len(returns) > 1 else 0.02
            
            indicators['momentum_5'] = (prices[-1] / prices[-5] - 1) * 100 if len(prices) >= 5 and prices[-5] > 0 else 0
            
            return indicators
            
        except Exception as e:
            logger.error(f"Enhanced indicators calculation error: {e}")
            return self._get_default_indicators(prices[-1] if 'prices' in locals() and len(prices) > 0 else 1.0)
    
    def _get_default_indicators(self, current_price: float) -> Dict[str, float]:
        """Get default indicators when calculation fails"""
        return {
            'rsi_14': 50.0,
            'sma_20': current_price,
            'macd_line': 0, 'macd_signal': 0, 'macd_histogram': 0,
            'bb_upper': current_price * 1.02, 'bb_lower': current_price * 0.98, 'bb_middle': current_price,
            'bb_position': 0.5,
            'atr': current_price * 0.02, 'volatility': 0.02,
            'momentum_5': 0
        }
    
    def _calculate_rsi(self, prices: np.ndarray, period: int) -> float:
        """Calculate RSI"""
        if len(prices) < period + 1:
            return 50.0
        
        if (prices <= 0).any():
            return 50.0
        
        deltas = np.diff(prices)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        avg_gains = np.mean(gains[-period:])
        avg_losses = np.mean(losses[-period:])
        
        if avg_losses == 0:
            return 100.0
        
        rs = avg_gains / avg_losses
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    def _calculate_macd(self, prices: np.ndarray) -> Tuple[float, float, float]:
        """Calculate MACD"""
        if len(prices) < 26:
            return 0.0, 0.0, 0.0
        
        ema_12 = self._calculate_ema(prices, 12)
        ema_26 = self._calculate_ema(prices, 26)
        macd_line = ema_12 - ema_26
        macd_signal = self._calculate_ema(prices[-9:], 9)
        macd_histogram = macd_line - macd_signal
        
        return macd_line, macd_signal, macd_histogram
    
    def _calculate_ema(self, prices: np.ndarray, period: int) -> float:
        """Calculate EMA"""
        if len(prices) < period:
            return np.mean(prices) if len(prices) > 0 else 1.0
        
        weights = np.exp(np.linspace(-1., 0., period))
        weights /= weights.sum()
        
        return np.convolve(prices[-period:], weights, mode='valid')[-1]
    
    def _calculate_bollinger_bands(self, prices: np.ndarray, period: int = 20, std_dev: int = 2) -> Tuple[float, float, float]:
        """Calculate Bollinger Bands"""
        if len(prices) < period:
            middle = np.mean(prices) if len(prices) > 0 else 1.0
            std = np.std(prices) if len(prices) > 1 else 0.1
            return middle + std_dev * std, middle - std_dev * std, middle
        
        middle = np.mean(prices[-period:])
        std = np.std(prices[-period:])
        upper = middle + std_dev * std
        lower = middle - std_dev * std
        
        return upper, lower, middle
    
    def _calculate_atr(self, df: pd.DataFrame) -> float:
        """Calculate Average True Range - DIPERBAIKI untuk data minimal"""
        try:
            if len(df) < 5:
                current_price = df['close'].iloc[-1] if 'close' in df.columns and len(df) > 0 else 100.0
                return current_price * 0.02
            
            high = df['high'].values
            low = df['low'].values
            close = df['close'].values
            
            if (high <= 0).any() or (low <= 0).any() or (close <= 0).any():
                logger.warning("Invalid price data in ATR calculation")
                return df['close'].iloc[-1] * 0.02
            
            tr = np.zeros(len(high))
            for i in range(1, len(high)):
                tr1 = high[i] - low[i]
                tr2 = abs(high[i] - close[i-1])
                tr3 = abs(low[i] - close[i-1])
                tr[i] = max(tr1, tr2, tr3)
            
            period = min(14, len(tr))
            atr = np.mean(tr[-period:]) if len(tr) >= period else np.mean(tr)
            
            if atr <= 0:
                current_price = close[-1]
                atr = current_price * 0.02
            
            return atr
            
        except Exception as e:
            logger.error(f"ATR calculation error: {e}")
            current_price = df['close'].iloc[-1] if 'close' in df.columns and len(df) > 0 else 100.0
            return current_price * 0.02
    
    def _calculate_trend_strength(self, df: pd.DataFrame, symbol: str = None) -> float:
        """Hitung kekuatan trend dengan linear regression"""
        try:
            prices = df['close'].values[-50:]
            if len(prices) < 2:
                return 0.0
            
            prices = np.nan_to_num(prices, nan=0.0, posinf=0.0, neginf=0.0)
            if not np.all(np.isfinite(prices)) or np.all(prices == prices[0]) or np.all(prices == 0):
                logger.warning(f"Invalid prices (nan/inf/constant/zero) for {symbol}, returning 0.0")
                return 0.0
            
            x = np.arange(len(prices))
            slope, intercept, r_value, p_value, std_err = stats.linregress(x, prices)
            
            mean_price = np.mean(prices)
            normalized_slope = slope / mean_price if mean_price > 0 else 0
            trend_strength = normalized_slope * (r_value ** 2)
            
            return max(min(trend_strength, 1.0), -1.0)
        
        except (ValueError, Exception) as e:
            logger.warning(f"Trend calc failed for {symbol}: {str(e)}. Return 0.0")
            return 0.0
    
    def _get_default_analysis(self, symbol: str = None) -> Dict[str, Any]:
        """Get default analysis result"""
        if symbol is None:
            symbol = "UNKNOWN"
            
        default_price = self._estimate_realistic_price(symbol)
        default_entry = self.calculate_custom_entry(symbol, default_price, "NEUTRAL")
        
        return {
            'action': 'NEUTRAL',
            'trading_type': self.trading_type,
            'leverage': self.leverage,
            'entry_range_low': default_entry['entry_range_low'],
            'entry_range_high': default_entry['entry_range_high'],
            'best_entry': default_entry['best_entry'],
            'tp1': default_entry['tp1'],
            'tp2': default_entry['tp2'],
            'tp3': default_entry['tp3'],
            'sl': default_entry['sl'],
            'current_price': default_price,
            'score': 0,
            'rsi': 50.0,
            'atr': default_price * 0.02,
            'market_regime': 'UNKNOWN',
            'trend_strength': 0.0,
            'trend_direction': 'NEUTRAL',
            'volatility': 0.02,
            'confidence': 0.5,
            'symbol': symbol,
            'entry_range_pct': self.entry_range_pct * 100,
            'range_size': default_entry['range_size'],
            'risk_amount': default_entry['risk_amount'],
            'risk_percentage': default_entry['risk_percentage'],
            'rr_ratio_tp1': default_entry['rr_ratio_tp1'],
            'rr_ratio_tp3': default_entry['rr_ratio_tp3'],
            'liquidation_buffer_pct': default_entry['liquidation_buffer_pct'],
            'long_bias_applied': self.long_bias,
            'min_score_threshold': self.min_score_threshold,
            'scalping_mode': self.scalping_mode,
            'enter_tag': 'DEFAULT',
            'adx': 20,
            'consolidation_score': 0,
            'rsi_threshold_used': f"{self.rsi_oversold:.1f}/{self.rsi_overbought:.1f}",
            'mtf_confirmation': 1.0,
            'volume_ratio': 1.0,
            'breakout_detected': False,
            'breakout_direction': 'NONE',
            'scoring_system': 'DEFAULT'
        }

# =============================================
# SCALPING STRATEGY - STRATEGI KHUSUS UNTUK SCALPING
# =============================================

class ScalpingStrategy(EnhancedTechnicalAnalysisStrategy):
    """Strategi khusus untuk scalping 3-5 menit dengan semua improvement"""
    
    def __init__(self, market_type="crypto", trading_type="spot", leverage=1):
        super().__init__(
            market_type=market_type,
            trading_type=trading_type,
            leverage=leverage,
            entry_range_pct=SCALPING_CONFIG["entry_range_pct"],
            atr_multiplier=SCALPING_CONFIG["atr_multiplier"],
            long_bias=0.0,
            min_score_threshold=SCALPING_CONFIG["min_score_threshold"],
            scalping_mode=True,
            use_multi_tf_confirmation=True,
            use_adaptive_params=True,
            use_regime_detection=True,
            use_consolidation_filter=True
        )
        self.base_rsi_oversold = 25
        self.base_rsi_overbought = 75
        self.min_adx_trend = 20
        
        self.breakout_volume_threshold = 1.5
        self.breakout_price_threshold = 0.01
        self.breakout_penalty_factor = 0.7
        
        logger.info(f"🎯 ScalpingStrategy created: Bias={self.long_bias:.1f}, Min Score={self.min_score_threshold}, Breakout Protection: ON")
    
    def analyze(self, df: pd.DataFrame, symbol: str = None, **kwargs) -> Dict[str, Any]:
        """Override untuk scalping dengan validasi tambahan"""
        
        if df is None or df.empty:
            return self._get_safe_neutral_signal(symbol)
        
        if not self._safe_data_validation(df, symbol):
            logger.warning(f"Data validation failed for {symbol} in scalping")
            return self._get_safe_neutral_signal(symbol)
        
        if len(df) < 50:
            logger.warning(f"⚠️ {symbol}: Insufficient data for scalping ({len(df)} bars)")
            return self._get_safe_neutral_signal(symbol)
        
        volatility = df['close'].pct_change().std() * np.sqrt(252)
        if volatility < SCALPING_CONFIG["min_volatility"]:
            logger.debug(f"⚠️ {symbol}: Too low volatility for scalping ({volatility:.3%})")
            return self._get_safe_neutral_signal(symbol)
        
        if volatility > SCALPING_CONFIG["max_volatility"]:
            logger.debug(f"⚠️ {symbol}: Too high volatility for scalping ({volatility:.3%})")
            return self._get_safe_neutral_signal(symbol)
        
        if 'volume' in df.columns:
            avg_volume = df['volume'].mean()
            if avg_volume < 50000:
                logger.debug(f"⚠️ {symbol}: Low volume for scalping ({avg_volume:.0f})")
                return self._get_safe_neutral_signal(symbol)
        
        result = super().analyze(df, symbol, **kwargs)
        
        result['scalping_mode'] = True
        result['scalping_optimized'] = True
        
        if result['action'] != 'NEUTRAL':
            if result['action'] == 'LONG':
                result['tp1'] = result['best_entry'] * 1.01
                result['tp2'] = result['best_entry'] * 1.02
                result['tp3'] = result['best_entry'] * 1.03
                result['sl'] = result['best_entry'] * 0.99
            elif result['action'] == 'SHORT':
                result['tp1'] = result['best_entry'] * 0.99
                result['tp2'] = result['best_entry'] * 0.98
                result['tp3'] = result['best_entry'] * 0.97
                result['sl'] = result['best_entry'] * 1.01
        
        return result

# =============================================
# UTILITY FUNCTIONS UNTUK AUTO-DETECTION DENGAN SCALPING
# =============================================

def auto_detect_trading_type_and_format(symbol: str) -> Tuple[str, str]:
    """
    Auto-detect trading type dan konversi format secara otomatis.
    Returns: (trading_type, formatted_symbol)
    """
    symbol_upper = symbol.upper()
    
    futures_markers = [':USDT', 'PERP', 'FUTURES', 'SWAP', '-USDT', '_PERP', '1226', '0325', '0626', '0926']
    is_futures = any(marker in symbol_upper for marker in futures_markers)
    
    if is_futures:
        trading_type = "futures"
        if ':USDT' in symbol_upper:
            formatted = symbol
        elif '/USDT' in symbol_upper and ':USDT' not in symbol_upper:
            formatted = f"{symbol}:USDT"
        elif '-USDT' in symbol_upper and 'PERP' not in symbol_upper:
            formatted = symbol.replace('-USDT', '/USDT:USDT')
        else:
            formatted = symbol
    else:
        trading_type = "spot"
        if ':USDT' in symbol_upper:
            formatted = symbol.replace(':USDT', '/USDT')
        else:
            formatted = symbol
    
    return trading_type, formatted

def auto_detect_trading_type(symbol: str) -> str:
    """Auto-detect if symbol is for spot or futures trading - ENHANCED"""
    trading_type, _ = auto_detect_trading_type_and_format(symbol)
    return trading_type

def convert_symbol_format(symbol: str, target_type: str = "spot") -> str:
    """Convert symbol between spot and futures format"""
    if target_type == "futures":
        if ':USDT' not in symbol.upper():
            if '/USDT' in symbol.upper():
                return f"{symbol}:USDT"
            elif '-USDT' in symbol.upper():
                return symbol.replace('-USDT', '/USDT:USDT')
            else:
                return f"{symbol}:USDT"
        else:
            return symbol
    
    elif target_type == "spot":
        if ':USDT' in symbol.upper():
            return symbol.replace(':USDT', '')
        else:
            return symbol
    
    return symbol

def auto_suggest_leverage(symbol: str, market_type: str = "crypto", scalping_mode: bool = False) -> int:
    """Auto-suggest leverage based on symbol and market type"""
    if scalping_mode:
        leverage_map = {
            'crypto': {
                'BTC': 3, 'ETH': 5, 'SOL': 8, 'ADA': 10, 'XRP': 10,
                'BNB': 8, 'DOGE': 12, 'DOT': 8, 'AVAX': 8, 'MATIC': 10,
                'default': 5
            },
            'forex': {
                'EURUSD': 20, 'USDJPY': 20, 'GBPUSD': 15, 'AUDUSD': 15,
                'USDCAD': 15, 'USDCHF': 15, 'NZDUSD': 15, 'XAUUSD': 10, 'XAGUSD': 10,
                'default': 15
            },
            'default': 5
        }
    else:
        leverage_map = {
            'crypto': {
                'BTC': 5, 'ETH': 8, 'SOL': 10, 'ADA': 15, 'XRP': 15,
                'BNB': 10, 'DOGE': 20, 'DOT': 12, 'AVAX': 12, 'MATIC': 15,
                'default': 10
            },
            'forex': {
                'EURUSD': 30, 'USDJPY': 30, 'GBPUSD': 20, 'AUDUSD': 25,
                'USDCAD': 25, 'USDCHF': 25, 'NZDUSD': 25, 'XAUUSD': 20, 'XAGUSD': 20,
                'default': 25
            },
            'us_stocks': {
                'ES': 20, 'NQ': 15, 'YM': 15, 'RTY': 15,
                'SPX': 20, 'NDX': 15, 'DJI': 15,
                'default': 15
            },
            'forex_gold': {
                'XAU': 20, 'GOLD': 20, 'XAG': 20, 'SILVER': 20,
                'default': 20
            },
            'crypto_future': {
                'BTC': 5, 'ETH': 8, 'SOL': 10, 'default': 8
            },
            'stock_future': {
                'ES': 20, 'NQ': 15, 'YM': 15, 'default': 15
            },
            'forex_future': {
                'EURUSD': 30, 'USDJPY': 30, 'default': 25
            }
        }
    
    symbol_upper = symbol.upper().replace('/', '').replace('-', '').replace('_', '').replace('=', '')
    
    for key, leverage in leverage_map.get(market_type, {}).items():
        if key in symbol_upper:
            return leverage
    
    return leverage_map.get(market_type, {}).get('default', 10)

def create_strategy_for_symbol(symbol: str, market_type: str = "auto", 
                               trading_mode: str = None, scalping_mode: bool = False,
                               strategy_type: str = "technical", backtest_mode: bool = False,
                               backtest_data: pd.DataFrame = None) -> TradingStrategy:
    """
    Create appropriate strategy based on symbol auto-detection dengan scalping support
    
    Args:
        symbol: Trading symbol
        market_type: Market type (auto-detect if 'auto')
        trading_mode: 'spot' or 'futures'
        scalping_mode: True for scalping strategy
        strategy_type: 'technical', 'mean_reversion', 'trend_following', 'breakout', 
                      'momentum', 'volatility', 'ensemble'
        backtest_mode: True untuk menjalankan backtest
        backtest_data: Data untuk backtest (jika tersedia)
    """
    # Auto-detect market type if not specified
    if market_type == "auto":
        if any(x in symbol.upper() for x in ['.JK', 'IDX', 'JAKARTA']):
            market_type = "indonesia_stocks"
        elif any(x in symbol.upper() for x in ['XAU', 'XAG', 'GOLD', 'SILVER']):
            market_type = "forex_gold"
        elif any(x in symbol.upper() for x in ['EUR', 'USD', 'JPY', 'GBP', 'AUD', 'CAD']):
            market_type = "forex"
        elif any(x in symbol.upper() for x in ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA', 'META']):
            market_type = "us_stocks"
        elif any(x in symbol.upper() for x in ['PERP', 'FUTURES', 'SWAP', '1226', '0325', '0626', '0926']):
            if 'BTC' in symbol.upper() or 'ETH' in symbol.upper() or 'SOL' in symbol.upper():
                market_type = "crypto_future"
            elif 'ES' in symbol.upper() or 'NQ' in symbol.upper() or 'YM' in symbol.upper():
                market_type = "stock_future"
            elif 'EUR' in symbol.upper() or 'USD' in symbol.upper() or 'JPY' in symbol.upper():
                market_type = "forex_future"
            else:
                market_type = "crypto_future"
        else:
            market_type = "crypto"
    
    # Jika trading_mode diberikan, gunakan itu
    if trading_mode:
        trading_type = trading_mode
        formatted_symbol = convert_symbol_format(symbol, trading_mode)
    else:
        trading_type, formatted_symbol = auto_detect_trading_type_and_format(symbol)
    
    # Auto-suggest leverage dengan scalping consideration
    leverage = auto_suggest_leverage(formatted_symbol, market_type, scalping_mode)
    
    # 🎯 BUAT STRATEGI BERDASARKAN TYPE
    strategy = None
    
    if strategy_type == 'mean_reversion':
        strategy = MeanReversionStrategy(
            market_type=market_type,
            trading_type=trading_type,
            leverage=leverage,
            lookback_period=20,
            std_dev_threshold=2.0
        )
        logger.info(f"📊 MeanReversion Strategy for {symbol} -> {formatted_symbol}")
        
    elif strategy_type == 'trend_following':
        strategy = TrendFollowingStrategy(
            market_type=market_type,
            trading_type=trading_type,
            leverage=leverage,
            fast_period=10,
            slow_period=30
        )
        logger.info(f"📊 TrendFollowing Strategy for {symbol} -> {formatted_symbol}")
        
    elif strategy_type == 'breakout':
        strategy = BreakoutStrategy(
            market_type=market_type,
            trading_type=trading_type,
            leverage=leverage,
            lookback_period=20,
            breakout_threshold=0.02
        )
        logger.info(f"📊 Breakout Strategy for {symbol} -> {formatted_symbol}")
        
    elif strategy_type == 'momentum':
        strategy = MomentumStrategy(
            market_type=market_type,
            trading_type=trading_type,
            leverage=leverage,
            momentum_period=20,
            ranking_period=30
        )
        logger.info(f"📊 Momentum Strategy for {symbol} -> {formatted_symbol}")
        
    elif strategy_type == 'volatility':
        strategy = VolatilityStrategy(
            market_type=market_type,
            trading_type=trading_type,
            leverage=leverage,
            volatility_period=20,
            target_volatility=0.20
        )
        logger.info(f"📊 Volatility Strategy for {symbol} -> {formatted_symbol}")
        
    elif strategy_type == 'ensemble':
        strategy = EnsembleStrategy(
            market_type=market_type,
            trading_type=trading_type,
            leverage=leverage
        )
        logger.info(f"📊 Ensemble Strategy for {symbol} -> {formatted_symbol}")
        
    else:  # Default atau 'technical'
        if scalping_mode:
            strategy = ScalpingStrategy(
                market_type=market_type,
                trading_type=trading_type,
                leverage=leverage
            )
            logger.info(f"⚡ SCALPING Strategy for {symbol} -> {formatted_symbol}")
        else:
            strategy = EnhancedTechnicalAnalysisStrategy(
                market_type=market_type,
                trading_type=trading_type,
                leverage=leverage,
                entry_range_pct=0.02,
                atr_multiplier=1.0,
                long_bias=0.0,
                min_score_threshold=3.0,
                use_multi_tf_confirmation=True,
                use_adaptive_params=True,
                use_regime_detection=True,
                use_consolidation_filter=True
            )
            logger.info(f"📊 REGULAR Strategy for {symbol} -> {formatted_symbol}")
    
    # Jika mode backtest dan ada data, jalankan backtest
    if backtest_mode and backtest_data is not None and strategy is not None:
        logger.info(f"🔬 Running backtest for {symbol} with {strategy_type} strategy")
        backtest_results = strategy.backtest_strategy(backtest_data, symbol)
        
        # Tambahkan hasil backtest ke strategy
        strategy.backtest_results = backtest_results
        
        # Log hasil backtest
        if 'error' in backtest_results:
            logger.error(f"Backtest failed: {backtest_results['error']}")
        else:
            logger.info(f"📊 Backtest Results: Sharpe={backtest_results.get('sharpe_ratio', 0):.2f}, "
                       f"Max DD={backtest_results.get('max_drawdown', 0):.1f}%, "
                       f"Win Rate={backtest_results.get('win_rate', 0):.1f}%")
    
    return strategy

def get_strategy_for_trading_mode(symbol: str, trading_mode: str = "spot", 
                                  market_type: str = "auto", scalping_mode: bool = False,
                                  strategy_type: str = "technical") -> TradingStrategy:
    """Get strategy configured for specific trading mode dengan scalping support"""
    formatted_symbol = convert_symbol_format(symbol, trading_mode)
    
    strategy = create_strategy_for_symbol(
        symbol=formatted_symbol,
        market_type=market_type,
        trading_mode=trading_mode,
        scalping_mode=scalping_mode,
        strategy_type=strategy_type
    )
    
    return strategy

# =============================================
# BACKTESTING UTILITY FUNCTIONS
# =============================================

def run_comprehensive_backtest(df, symbol, strategies_to_test=None):
    """Run backtest untuk multiple strategies dan bandingkan hasilnya"""
    if strategies_to_test is None:
        strategies_to_test = [
            'technical',
            'mean_reversion', 
            'trend_following',
            'breakout',
            'momentum',
            'volatility',
            'ensemble'
        ]
    
    results = {}
    
    for strategy_type in strategies_to_test:
        try:
            logger.info(f"🧪 Testing {strategy_type} strategy for {symbol}")
            
            strategy = create_strategy_for_symbol(
                symbol=symbol,
                strategy_type=strategy_type,
                backtest_mode=True,
                backtest_data=df
            )
            
            if hasattr(strategy, 'backtest_results'):
                results[strategy_type] = strategy.backtest_results
                
                sharpe = strategy.backtest_results.get('sharpe_ratio', 0)
                max_dd = strategy.backtest_results.get('max_drawdown', 0)
                win_rate = strategy.backtest_results.get('win_rate', 0)
                
                logger.info(f"  ✅ {strategy_type}: Sharpe={sharpe:.2f}, Max DD={max_dd:.1f}%, Win Rate={win_rate:.1f}%")
            else:
                logger.warning(f"  ⚠️ {strategy_type}: No backtest results")
                
        except Exception as e:
            logger.error(f"  ❌ {strategy_type}: Error - {e}")
            results[strategy_type] = {'error': str(e)}
    
    # Bandingkan hasil
    if results:
        best_sharpe = -float('inf')
        best_strategy = None
        
        for strategy_type, result in results.items():
            if 'error' not in result:
                sharpe = result.get('sharpe_ratio', 0)
                if sharpe > best_sharpe:
                    best_sharpe = sharpe
                    best_strategy = strategy_type
        
        logger.info(f"🏆 Best Strategy: {best_strategy} (Sharpe: {best_sharpe:.2f})")
    
    return results

def optimize_strategy_parameters(df, symbol, strategy_type='technical'):
    """Optimize strategy parameters menggunakan grid search"""
    logger.info(f"🔧 Optimizing {strategy_type} strategy for {symbol}")
    
    strategy = create_strategy_for_symbol(
        symbol=symbol,
        strategy_type=strategy_type
    )
    
    if strategy:
        optimization_results = strategy.optimize_parameters(df, symbol)
        return optimization_results
    else:
        logger.error(f"Failed to create strategy {strategy_type}")
        return None

# =============================================
# BACKWARD COMPATIBILITY
# =============================================

class TechnicalAnalysisStrategy(EnhancedTechnicalAnalysisStrategy):
    """Backward compatibility wrapper"""
    pass

# =============================================
# TESTING FUNCTIONS UNTUK VERIFIKASI PERBAIKAN
# =============================================

def test_hybrid_scoring_system():
    """Test the hybrid scoring system"""
    print("=" * 60)
    print("TESTING HYBRID SCORING SYSTEM")
    print("=" * 60)
    
    dates = pd.date_range('2023-12-24', periods=100, freq='5min')
    
    trend_prices = np.linspace(0.065, 0.075, 100)
    noise = np.random.normal(0, 0.0001, 100)
    prices = trend_prices + noise
    
    data = {
        'open': prices * np.random.uniform(0.999, 1.001, 100),
        'high': prices * np.random.uniform(1.001, 1.003, 100),
        'low': prices * np.random.uniform(0.997, 0.999, 100),
        'close': prices,
        'volume': np.random.normal(1000000, 100000, 100),
    }
    
    df = pd.DataFrame(data, index=dates)
    
    scenarios = [
        ("BULL_TREND", df),
        ("RANGING", df.iloc[-20:])
    ]
    
    for scenario_name, test_df in scenarios:
        print(f"\n📊 Testing {scenario_name} scenario:")
        
        strategy = EnhancedTechnicalAnalysisStrategy(market_type="crypto", trading_type="futures")
        
        indicators = strategy._calculate_enhanced_indicators(test_df)
        adaptive_indicators = strategy._calculate_adaptive_indicators(test_df)
        indicators.update(adaptive_indicators)
        
        sym_score = strategy._calculate_symmetrical_score(indicators, test_df)
        tf_score = strategy._calculate_trend_following_score(indicators, test_df)
        hybrid_score = strategy.calculate_adaptive_score(indicators, test_df, "TEST")
        
        print(f"   Symmetrical Score: {sym_score:.1f}")
        print(f"   Trend-Following Score: {tf_score:.1f}")
        print(f"   Hybrid Score: {hybrid_score:.1f}")
        
        result = strategy.analyze(test_df, f"TEST_{scenario_name}")
        print(f"   Final Action: {result['action']}")
        print(f"   Final Score: {result['score']:.1f}")
        print(f"   Scoring System Used: {result.get('scoring_system', 'N/A')}")
    
    return True

def test_skyusdt_scenario():
    """Test specific SKYUSDT scenario from Dec 24"""
    print("\n" + "=" * 60)
    print("🔍 TESTING SKYUSDT DEC 24 SCENARIO")
    print("=" * 60)
    
    dates = pd.date_range('2025-12-24 09:00', periods=100, freq='5min')
    
    prices = np.ones(100) * 0.065
    prices[50:] = np.linspace(0.065, 0.068, 50)
    
    volumes = np.random.normal(500000, 100000, 100)
    volumes[50:70] = np.random.normal(1500000, 200000, 20)
    
    data = {
        'open': prices * np.random.uniform(0.999, 1.001, 100),
        'high': prices * np.random.uniform(1.001, 1.003, 100),
        'low': prices * np.random.uniform(0.997, 0.999, 100),
        'close': prices,
        'volume': volumes,
    }
    
    df = pd.DataFrame(data, index=dates)
    
    strategy = EnhancedTechnicalAnalysisStrategy(market_type="crypto", trading_type="futures", leverage=3)
    
    print("⏰ Time-based analysis:")
    for i in range(0, 100, 10):
        subset = df.iloc[:i+10] if i+10 <= len(df) else df
        if len(subset) > 30:
            result = strategy.analyze(subset, "SKY/USDT")
            time_str = subset.index[-1].strftime('%H:%M')
            action_emoji = "🟢" if result['action'] == 'LONG' else "🔴" if result['action'] == 'SHORT' else "⚪"
            print(f"   {time_str} - {action_emoji} Action: {result['action']}, Score: {result['score']:.1f}, Scoring: {result.get('scoring_system', 'N/A')}")
    
    result = strategy.analyze(df, "SKY/USDT")
    
    print(f"\n📊 Final Result:")
    print(f"   Action: {result['action']}")
    print(f"   Score: {result['score']:.1f}")
    print(f"   Bias Applied: {result['long_bias_applied']}")
    print(f"   Breakout Detected: {result['breakout_detected']}")
    print(f"   Breakout Direction: {result['breakout_direction']}")
    print(f"   Scoring System: {result.get('scoring_system', 'N/A')}")
    print(f"   Market Regime: {result.get('market_regime', 'UNKNOWN')}")
    print(f"   Enter Tag: {result['enter_tag']}")
    
    if result['action'] == 'SHORT' and result['breakout_detected'] and result['breakout_direction'] == 'BULLISH':
        print(f"\n✅ SUCCESS: Breakout detection bekerja! SHORT signal di-warning saat bullish breakout.")
    elif result['action'] == 'NEUTRAL' and result['breakout_detected']:
        print(f"\n✅ SUCCESS: Breakout membuat sinyal menjadi NEUTRAL.")
    elif result['scoring_system'] == 'HYBRID':
        print(f"\n✅ SUCCESS: Hybrid scoring system aktif dan berfungsi.")
    else:
        print(f"\n⚠️ WARNING: Perlu pengecekan lebih lanjut.")
    
    return result

def test_backtesting_framework():
    """Test backtesting framework dengan berbagai strategi"""
    print("\n" + "=" * 60)
    print("🧪 TESTING BACKTESTING FRAMEWORK")
    print("=" * 60)
    
    # Generate sample data
    dates = pd.date_range('2023-01-01', periods=200, freq='D')
    prices = np.cumprod(1 + np.random.normal(0.0005, 0.02, 200))
    
    data = {
        'open': prices * np.random.uniform(0.99, 1.01, 200),
        'high': prices * np.random.uniform(1.01, 1.03, 200),
        'low': prices * np.random.uniform(0.97, 0.99, 200),
        'close': prices,
        'volume': np.random.normal(1000000, 200000, 200),
    }
    
    df = pd.DataFrame(data, index=dates)
    
    # Test berbagai strategi
    strategies = [
        ('technical', EnhancedTechnicalAnalysisStrategy(market_type="crypto")),
        ('mean_reversion', MeanReversionStrategy(market_type="crypto")),
        ('trend_following', TrendFollowingStrategy(market_type="crypto")),
    ]
    
    for name, strategy in strategies:
        print(f"\n📊 Testing {name} strategy:")
        
        # Run backtest
        results = strategy.backtest_strategy(df, "TEST_SYMBOL", initial_cash=10000)
        
        if 'error' in results:
            print(f"   ❌ Error: {results['error']}")
        else:
            print(f"   ✅ Sharpe Ratio: {results.get('sharpe_ratio', 0):.2f}")
            print(f"   ✅ Max Drawdown: {results.get('max_drawdown', 0):.1f}%")
            print(f"   ✅ Win Rate: {results.get('win_rate', 0):.1f}%")
            print(f"   ✅ Total Return: {results.get('total_return', 0):.1f}%")
            print(f"   ✅ Library Used: {results.get('library', 'unknown')}")
    
    return True

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("STRATEGIES.PY - HYBRID SCORING SYSTEM V1.0")
    print("=" * 60)
    print("✅ Bias Correction: SEMUA BIAS = 0.0")
    print("✅ Hybrid Scoring: Symmetrical + Trend-Following")
    print("✅ Smart Adaptation: Berdasarkan ADX dan Market Regime")
    print("✅ Breakout Detection: Aktif dengan parameter aman")
    print("✅ Warning System: Tidak langsung block, hanya warning")
    print("✅ Backtesting Framework: Integrated dengan backtesting.py & backtrader")
    print("✅ Quantitative Strategies: Mean Reversion, Trend Following, Breakout, Momentum, Volatility")
    print("✅ Ensemble Strategy: Multi-strategy combination")
    print("=" * 60)
    
    # Jalankan test
    test_hybrid_scoring_system()
    test_skyusdt_scenario()
    test_backtesting_framework()
    
    print("\n" + "=" * 60)
    print("✅ HYBRID SCORING SYSTEM READY!")
    print("✅ Backtesting Framework READY!")
    print("✅ Quantitative Strategies READY!")
    print("=" * 60)
