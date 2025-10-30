import os
import time
import json
import warnings
from datetime import datetime, timedelta
import threading
import schedule
import asyncio
import pandas as pd
import numpy as np

from dotenv import load_dotenv

# Import relative untuk package bot
from .strategies import TechnicalAnalysisStrategy
from .data_provider import (
    CCXTDataProvider,
    YFinanceDataProvider,
    AlphaVantageProvider,
    DexScreenerProvider
)
from .notifier import SoundNotifier
from database.db_handler import DatabaseHandler

warnings.filterwarnings("ignore")
load_dotenv()

class TradingBot:
    def __init__(self, config_path="config/config.json"):
        # === Config & Setup ===
        self.config_path = config_path
        self.load_config()

        self.mode = None
        self.data_provider = None
        self.backup_provider = None
        self.pump_provider = None

        # === Core Modules ===
        self.strategy = TechnicalAnalysisStrategy(
            atr_multiplier=self.config.get("atr_multiplier", 1.5),
            entry_range_pct=self.config.get("entry_range_pct", 0.015),
            use_ml=self.config.get("use_ml", False)
        )
        self.notifier = SoundNotifier()
        self.db = DatabaseHandler()

        # === State ===
        self.timeframe = self.config.get("timeframe", "4h")
        self.alert_active = False
        self.scanner_active = False
        self.entry_positions = {}
        self.position_ids = {}
        self.last_scan_time = None
        
        # === Background Tasks ===
        self.scheduler_thread = None
        self.stop_scheduler = False

    def load_config(self):
        """Load configuration from config.json"""
        try:
            os.makedirs("config", exist_ok=True)
            with open(self.config_path, "r") as f:
                self.config = json.load(f)
        except FileNotFoundError:
            self.config = {
                "timeframe": "4h",
                "atr_multiplier": 1.5,
                "entry_range_pct": 0.015,
                "exchange_crypto": "binance",
                "analysis_coins_limit": 50,
                "ohlcv_limit": 200,
                "min_score": 2,
                "max_signals": 10,
                "update_interval": 60,
            }
            self.save_config()

    def save_config(self):
        """Save configuration to config.json"""
        os.makedirs("config", exist_ok=True)
        with open(self.config_path, "w") as f:
            json.dump(self.config, f, indent=4)

    def set_mode(self, mode):
        """Set market mode (crypto, forex, saham_id)"""
        self.mode = mode.lower()
        
        try:
            if self.mode == "crypto":
                exchange_id = self.config.get("exchange_crypto", "binance")
                self.data_provider = CCXTDataProvider(exchange_id, "", "")
                self.pump_provider = DexScreenerProvider()
            elif self.mode == "forex":
                self.data_provider = YFinanceDataProvider(market_type="forex")
            elif self.mode == "saham_id":
                self.data_provider = YFinanceDataProvider(market_type="saham_id")
            else:
                raise ValueError(f"Unsupported mode: {mode}")
            
            print(f"Mode set to: {self.mode.upper()}")
            return True
            
        except Exception as e:
            print(f"Failed to set mode {mode}: {e}")
            return False

    def get_popular_assets(self, limit=None):
        """Get popular assets for the selected market"""
        if not self.data_provider:
            return []

        limit = limit or self.config.get("analysis_coins_limit", 50)
        
        try:
            assets = self.data_provider.get_popular_assets(limit)
            
            # Ensure we return a list
            if assets is None:
                return self._get_fallback_assets(limit)
            elif isinstance(assets, (list, tuple)):
                return list(assets)[:limit]
            else:
                # If it's a single item, convert to list
                return [assets][:limit]
                
        except Exception as e:
            print(f"Error fetching popular assets: {e}")
            return self._get_fallback_assets(limit)

    def _get_fallback_assets(self, limit):
        """Get fallback assets when primary source fails"""
        if self.mode == "saham_id":
            return ['BBCA.JK', 'TLKM.JK', 'ASII.JK', 'BMRI.JK', 'BBRI.JK'][:limit]
        elif self.mode == "forex":
            return ['EURUSD=X', 'GBPUSD=X', 'USDJPY=X', 'AUDUSD=X', 'USDCAD=X'][:limit]
        else:  # crypto
            return ['BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'SOL/USDT', 'XRP/USDT'][:limit]

    def scan_potential_assets(self, limit=None):
        """Scan popular assets and return potential trading signals"""
        if not self.data_provider:
            return []

        # Get assets
        assets = self.get_popular_assets(limit)
        
        # Ensure assets is a list
        if not isinstance(assets, list):
            assets = []
        
        if not assets:
            return []
            
        print(f"Scanning {len(assets)} assets for {self.mode}")

        results = []
        max_signals = self.config.get("max_signals", 10)
        min_score = self.config.get("min_score", 2)
        
        for i, asset in enumerate(assets, 1):
            try:
                asset_str = str(asset)
                print(f"Analyzing {i}/{len(assets)}: {asset_str}")
                
                # Analyze asset
                analysis = self.analyze_asset(asset_str)
                
                # Check if analysis is valid and meets minimum score
                if (analysis and 
                    analysis.get('action') in ['LONG', 'SHORT'] and 
                    abs(analysis.get('score', 0)) >= min_score):
                    
                    # Add symbol to analysis
                    analysis['symbol'] = asset_str
                    analysis['market_type'] = self.mode
                    
                    # Ensure TP levels are in correct order
                    self._ensure_correct_tp_order(analysis)
                    
                    # Save to database
                    try:
                        self.db.save_signal(analysis)
                    except Exception as e:
                        print(f"Failed to save signal: {e}")
                    
                    results.append(analysis)
                    print(f"Signal found: {asset_str} - {analysis['action']} (Score: {analysis['score']})")

                time.sleep(0.1)  # Rate limiting
                
            except Exception as e:
                print(f"Error analyzing {asset}: {e}")
                continue

        # Sort by absolute score (highest first)
        results.sort(key=lambda x: abs(x.get('score', 0)), reverse=True)
        return results[:max_signals]

    def _ensure_correct_tp_order(self, analysis):
        """Ensure TP levels are in correct order based on action"""
        try:
            if analysis['action'] == 'LONG':
                # For LONG: TP1 < TP2 < TP3
                tp1, tp2, tp3 = analysis['tp1'], analysis['tp2'], analysis['tp3']
                sorted_tps = sorted([tp1, tp2, tp3])
                analysis['tp1'], analysis['tp2'], analysis['tp3'] = sorted_tps
            else:  # SHORT
                # For SHORT: TP1 > TP2 > TP3
                tp1, tp2, tp3 = analysis['tp1'], analysis['tp2'], analysis['tp3']
                sorted_tps = sorted([tp1, tp2, tp3], reverse=True)
                analysis['tp1'], analysis['tp2'], analysis['tp3'] = sorted_tps
        except Exception as e:
            print(f"Error ensuring TP order: {e}")

    def analyze_asset(self, symbol):
        """Analyze a specific asset and return signal"""
        if not self.data_provider:
            return None
            
        try:
            df = self.data_provider.get_ohlcv(
                symbol, self.timeframe, self.config.get("ohlcv_limit", 200)
            )
            
            # Validate DataFrame
            if (df is None or 
                not isinstance(df, pd.DataFrame) or 
                len(df) < 50 or 
                df.empty):
                return None
            
            # Perform analysis
            analysis = self.strategy.analyze(df)
            
            # Validate analysis result
            if (not analysis or 
                not isinstance(analysis, dict) or
                'action' not in analysis or
                'score' not in analysis):
                return None
                
            return analysis
            
        except Exception as e:
            print(f"Error analyzing {symbol}: {e}")
            return None

    async def scan_pump_fun(self, limit=10):
        """Scan new tokens on Solana Pump Fun"""
        if not self.pump_provider:
            return []
            
        try:
            # Search for new tokens on Solana
            pairs = self.pump_provider.search_pairs("solana")
            
            results = []
            for pair in pairs[:limit]:
                try:
                    symbol = pair.get('baseToken', {}).get('symbol', 'Unknown')
                    token_address = pair.get('baseToken', {}).get('address', '')
                    
                    # Get token info
                    ticker_info = self.pump_provider.get_ticker('solana', token_address)
                    
                    if ticker_info:
                        result = {
                            'symbol': symbol,
                            'address': token_address,
                            'ticker': ticker_info,
                            'price_usd': ticker_info.get('last', 0),
                            'volume_24h': ticker_info.get('volume', 0),
                            'liquidity': ticker_info.get('liquidity', 0),
                            'pair_url': pair.get('url', '')
                        }
                        results.append(result)
                except Exception as e:
                    print(f"Error processing token: {e}")
                    continue
            
            return results
        except Exception as e:
            print(f"Error scanning Pump Fun: {e}")
            return []

    def calculate_custom_entry(self, symbol, entry_price):
        """Calculate TP/SL for a custom entry price"""
        if not self.data_provider:
            return None
            
        try:
            df = self.data_provider.get_ohlcv(
                symbol, self.timeframe, self.config.get("ohlcv_limit", 200)
            )
            
            if df is not None and len(df) >= 50:
                atr = self.strategy.calculate_atr(df)
                
                # Calculate TP levels
                tp1 = entry_price + (atr * self.strategy.atr_multiplier)
                tp2 = entry_price + (atr * self.strategy.atr_multiplier * 2)
                tp3 = entry_price + (atr * self.strategy.atr_multiplier * 3)
                sl = entry_price - (atr * self.strategy.atr_multiplier)
                
                # Ensure correct TP order
                tp_levels = sorted([tp1, tp2, tp3])
                
                return {
                    "symbol": symbol,
                    "entry_price": float(entry_price),
                    "tp1": float(tp_levels[0]),
                    "tp2": float(tp_levels[1]),
                    "tp3": float(tp_levels[2]),
                    "sl": float(sl),
                }
                
            return None
        except Exception as e:
            print(f"Error calculating custom entry for {symbol}: {e}")
            return None

    def get_active_positions(self):
        """Get active positions from database"""
        try:
            positions = self.db.get_active_positions(self.mode)
            return positions if positions else []
        except Exception as e:
            print(f"Error fetching active positions: {e}")
            return []

    def get_trade_history(self, limit=10):
        """Get trade history from database"""
        try:
            history = self.db.get_trade_history(self.mode, limit)
            return history if history else []
        except Exception as e:
            print(f"Error fetching trade history: {e}")
            return []

    def close_position(self, position_id, exit_price=None, exit_type="manual"):
        """Close a position with the given exit price"""
        try:
            return self.db.close_position(position_id, exit_price, exit_type)
        except Exception as e:
            print(f"Error closing position: {e}")
            return False
