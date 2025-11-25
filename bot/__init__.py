"""
TradingBot Package
"""

from .core import TradingBot, EnhancedTradingBot
from .strategies import TechnicalAnalysisStrategy, EnhancedTechnicalAnalysisStrategy
from .data_provider import CCXTDataProvider, YFinanceDataProvider, DataProviderMonitor

__version__ = "1.0.0"
__author__ = "TradingBot Team"

__all__ = [
    'TradingBot',
    'EnhancedTradingBot', 
    'TechnicalAnalysisStrategy',
    'EnhancedTechnicalAnalysisStrategy',
    'CCXTDataProvider',
    'YFinanceDataProvider',
    'DataProviderMonitor'
]
