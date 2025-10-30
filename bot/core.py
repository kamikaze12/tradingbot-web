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
            entry_range_pct=self.config.get("entry_range_pct", 0.015)
        )
        self.notifier = SoundNotifier()
        self.db = DatabaseHandler()

        # === State ===
        self.timeframe = self.config.get("timeframe", "4h")
        self.alert_active = False
        self.scanner_active = False
        
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
                "exchange_crypto": "bybit",  # Changed from binance to bybit
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
                exchange_id = self.config.get("exchange_crypto", "bybit")  # Default to bybit
                print(f"Initializing crypto provider with exchange: {exchange_id}")
                self.data_provider = CCXTDataProvider(exchange_id, "", "")
                self.pump_provider = DexScreenerProvider()
                print(f"✓ Crypto provider initialized with {getattr(self.data_provider, 'exchange_id', 'fallback')}")
            elif self.mode == "forex":
                self.data_provider = YFinanceDataProvider(market_type="forex")
                print("✓ Forex provider initialized")
            elif self.mode == "saham_id":
                self.data_provider = YFinanceDataProvider(market_type="saham_id")
                print("✓ Saham Indonesia provider initialized")
            else:
                raise ValueError(f"Unsupported mode: {mode}")
            
            print(f"✓ Mode set to: {self.mode.upper()}")
            return True
            
        except Exception as e:
            print(f"✗ Failed to set mode {mode}: {e}")
            return False

    def get_popular_assets(self, limit=None):
        """Get popular assets for the selected market with robust error handling"""
        if not self.data_provider:
            print("No data provider available")
            return self._get_fallback_assets(limit)

        limit = limit or self.config.get("analysis_coins_limit", 50)
        
        try:
            print(f"Getting popular assets for {self.mode}...")
            assets = self.data_provider.get_popular_assets(limit)
            
            # FIX: Comprehensive type checking and conversion
            if assets is None:
                print("Provider returned None, using fallback")
                return self._get_fallback_assets(limit)
                
            # Handle case where assets is an integer
            if isinstance(assets, int):
                print(f"Provider returned integer: {assets}, using fallback")
                return self._get_fallback_assets(limit)
                
            # Convert to list if it's not already
            if not isinstance(assets, list):
                print(f"Converting non-list to list: {type(assets)}")
                try:
                    # Handle pandas Series, tuples, etc.
                    if hasattr(assets, '__iter__') and not isinstance(assets, str):
                        assets = list(assets)
                    else:
                        print(f"Cannot convert {type(assets)} to list, using fallback")
                        return self._get_fallback_assets(limit)
                except Exception as e:
                    print(f"Failed to convert to list: {e}, using fallback")
                    return self._get_fallback_assets(limit)
            
            # Filter out any non-string items and ensure we have strings
            cleaned_assets = []
            for asset in assets:
                if asset is not None:
                    asset_str = str(asset).strip()
                    if asset_str:  # Only add non-empty strings
                        cleaned_assets.append(asset_str)
            
            print(f"Found {len(cleaned_assets)} assets after cleaning")
            
            if not cleaned_assets:
                print("No valid assets found, using fallback")
                return self._get_fallback_assets(limit)
                
            return cleaned_assets[:limit]
                
        except Exception as e:
            print(f"Error in get_popular_assets: {e}")
            return self._get_fallback_assets(limit)

    def _get_fallback_assets(self, limit):
        """Get fallback assets when primary source fails"""
        print(f"Using fallback assets for {self.mode}")
        
        if self.mode == "saham_id":
            fallback = [
                'BBCA.JK', 'TLKM.JK', 'ASII.JK', 'BMRI.JK', 'BBRI.JK',
                'BBNI.JK', 'UNVR.JK', 'INDF.JK', 'ICBP.JK', 'ADRO.JK'
            ]
        elif self.mode == "forex":
            fallback = [
                'EURUSD=X', 'GBPUSD=X', 'USDJPY=X', 'AUDUSD=X', 'USDCAD=X',
                'USDCHF=X', 'NZDUSD=X', 'EURGBP=X', 'EURJPY=X', 'GBPJPY=X'
            ]
        else:  # crypto
            fallback = [
                'BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'SOL/USDT', 'XRP/USDT',
                'ADA/USDT', 'AVAX/USDT', 'DOT/USDT', 'DOGE/USDT', 'MATIC/USDT'
            ]
        
        limit = limit or 10
        return fallback[:limit]

    def scan_potential_assets(self, limit=None):
        """Scan popular assets and return potential trading signals with robust error handling"""
        if not self.data_provider:
            print("No data provider available for scanning")
            return []

        print("Starting scan...")
        
        # Get assets with extra validation
        assets = self.get_popular_assets(limit)
        
        # FIX: Ensure assets is always a proper list
        if not isinstance(assets, list):
            print(f"CRITICAL: Assets is not a list! Type: {type(assets)}, Value: {assets}")
            assets = []
        
        if not assets:
            print("No assets to scan")
            return []
            
        print(f"Scanning {len(assets)} assets for {self.mode}")

        results = []
        max_signals = self.config.get("max_signals", 10)
        min_score = self.config.get("min_score", 2)
        
        for i, asset in enumerate(assets, 1):
            try:
                # Extra validation for each asset
                if asset is None:
                    continue
                    
                asset_str = str(asset).strip()
                if not asset_str:
                    continue
                    
                print(f"Analyzing {i}/{len(assets)}: {asset_str}")
                
                # Analyze asset
                analysis = self.analyze_asset(asset_str)
                
                # Validate analysis result
                if not analysis:
                    print(f"No analysis result for {asset_str}")
                    continue
                    
                if not isinstance(analysis, dict):
                    print(f"Analysis is not a dict for {asset_str}: {type(analysis)}")
                    continue
                    
                # Check if we have required fields
                required_fields = ['action', 'score']
                missing_fields = [field for field in required_fields if field not in analysis]
                if missing_fields:
                    print(f"Missing fields in analysis for {asset_str}: {missing_fields}")
                    continue
                
                # Check action and score
                if (analysis.get('action') in ['LONG', 'SHORT'] and 
                    abs(analysis.get('score', 0)) >= min_score):
                    
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
        print(f"Scan complete. Found {len(results)} signals.")
        return results[:max_signals]

    def _ensure_correct_tp_order(self, analysis):
        """Ensure TP levels are in correct order based on action"""
        try:
            if 'tp1' not in analysis or 'tp2' not in analysis or 'tp3' not in analysis:
                return
                
            tp1, tp2, tp3 = analysis['tp1'], analysis['tp2'], analysis['tp3']
            
            if analysis['action'] == 'LONG':
                # For LONG: TP1 < TP2 < TP3
                sorted_tps = sorted([tp1, tp2, tp3])
                analysis['tp1'], analysis['tp2'], analysis['tp3'] = sorted_tps
            else:  # SHORT
                # For SHORT: TP1 > TP2 > TP3
                sorted_tps = sorted([tp1, tp2, tp3], reverse=True)
                analysis['tp1'], analysis['tp2'], analysis['tp3'] = sorted_tps
        except Exception as e:
            print(f"Error ensuring TP order: {e}")

    def analyze_asset(self, symbol):
        """Analyze a specific asset and return signal with robust error handling"""
        if not self.data_provider or not symbol:
            return None
            
        try:
            print(f"Fetching OHLCV data for {symbol}")
            df = self.data_provider.get_ohlcv(
                symbol, self.timeframe, self.config.get("ohlcv_limit", 200)
            )
            
            # Validate DataFrame
            if df is None:
                print(f"No data returned for {symbol}")
                return None
                
            if not isinstance(df, pd.DataFrame):
                print(f"Data is not DataFrame for {symbol}: {type(df)}")
                return None
                
            if len(df) < 50:
                print(f"Insufficient data for {symbol}: {len(df)} rows")
                return None
                
            if df.empty:
                print(f"Empty DataFrame for {symbol}")
                return None
            
            print(f"Performing analysis for {symbol}")
            analysis = self.strategy.analyze(df)
            
            # Validate analysis result
            if analysis is None:
                print(f"No analysis returned for {symbol}")
                return None
                
            if not isinstance(analysis, dict):
                print(f"Analysis is not dict for {symbol}: {type(analysis)}")
                return None
                
            print(f"Analysis successful for {symbol}")
            return analysis
            
        except Exception as e:
            print(f"Error analyzing {symbol}: {e}")
            return None

    async def scan_pump_fun(self, limit=10):
        """Scan new tokens on Solana Pump Fun"""
        if not self.pump_provider:
            print("No Pump Fun provider available")
            return []
            
        try:
            print("Scanning Pump Fun tokens...")
            # Search for new tokens on Solana
            pairs = self.pump_provider.search_pairs("solana")
            
            if not pairs:
                print("No pairs found from Pump Fun")
                return []
                
            results = []
            for i, pair in enumerate(pairs[:limit]):
                try:
                    symbol = pair.get('baseToken', {}).get('symbol', 'Unknown')
                    token_address = pair.get('baseToken', {}).get('address', '')
                    
                    print(f"Processing token {i+1}/{min(len(pairs), limit)}: {symbol}")
                    
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
                        print(f"Added token: {symbol}")
                except Exception as e:
                    print(f"Error processing token: {e}")
                    continue
            
            print(f"Pump Fun scan complete. Found {len(results)} tokens.")
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
                # Use strategy's ATR calculation
                indicators = self.strategy.calculate_technical_indicators(df)
                atr = indicators['atr_14'].iloc[-1] if 'atr_14' in indicators else entry_price * 0.02
                
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

    def cleanup_old_data(self, days=7):
        """Clean up old data from database"""
        try:
            return self.db.cleanup_old_data(days)
        except Exception as e:
            print(f"Error cleaning up old data: {e}")
            return {'signals': 0, 'positions': 0, 'history': 0}
