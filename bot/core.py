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
        
        # === Performance Tracking ===
        self.scan_stats = {
            'total_assets': 0,
            'successful_scans': 0,
            'signals_found': 0,
            'last_scan_duration': 0
        }
        
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
                "min_confidence": 0.6,
                "min_score": 2,
                "max_signals": 10,
                "update_interval": 60,
                "scan_interval": 300,
                "use_ml": False,
                "enable_backup_provider": True
            }
            self.save_config()

    def save_config(self):
        """Save configuration to config.json"""
        os.makedirs("config", exist_ok=True)
        with open(self.config_path, "w") as f:
            json.dump(self.config, f, indent=4)

    def set_mode(self, mode):
        """Set market mode (crypto, forex, saham_id) with backup providers"""
        self.mode = mode.lower()
        
        try:
            if self.mode == "crypto":
                exchange_id = self.config.get("exchange_crypto", "binance")
                self.data_provider = CCXTDataProvider(exchange_id, "", "")
                if self.config.get("enable_backup_provider", True):
                    self.backup_provider = YFinanceDataProvider(market_type="crypto")
                    
            elif self.mode == "forex":
                self.data_provider = YFinanceDataProvider(market_type="forex")
                if self.config.get("enable_backup_provider", True):
                    self.backup_provider = AlphaVantageProvider()
                    
            elif self.mode == "saham_id":
                self.data_provider = YFinanceDataProvider(market_type="saham_id")
                if self.config.get("enable_backup_provider", True):
                    self.backup_provider = AlphaVantageProvider()
                    
            else:
                raise ValueError(f"Unsupported mode: {mode}")
            
            print(f"✓ Mode set to: {self.mode.upper()}")
            print(f"  Primary Provider: {self.data_provider.__class__.__name__}")
            if self.backup_provider:
                print(f"  Backup Provider: {self.backup_provider.__class__.__name__}")
            
            return True
            
        except Exception as e:
            print(f"✗ Failed to set mode {mode}: {e}")
            self.data_provider = None
            self.backup_provider = None
            return False

    def get_popular_assets(self, limit=None):
        """Get popular assets with enhanced error handling"""
        if not self.data_provider:
            print("❌ No data provider available")
            return []

        limit = limit or self.config.get("analysis_coins_limit", 50)
        
        try:
            print(f"🔍 Fetching popular assets for {self.mode}...")
            assets = self.data_provider.get_popular_assets(limit)
            
            # DEBUG: Print type and value for debugging
            print(f"DEBUG: get_popular_assets returned type: {type(assets)}, value: {assets}")
            
            # Handle different return types
            if assets is None:
                print("⚠️ get_popular_assets returned None, using fallback")
                assets = self._get_fallback_assets(limit)
            elif isinstance(assets, (int, float)):
                print(f"⚠️ get_popular_assets returned number: {assets}, using fallback")
                assets = self._get_fallback_assets(limit)
            elif isinstance(assets, str):
                print(f"⚠️ get_popular_assets returned string: {assets}, converting to list")
                assets = [assets]
            elif not isinstance(assets, (list, tuple)):
                print(f"⚠️ get_popular_assets returned unexpected type: {type(assets)}, using fallback")
                assets = self._get_fallback_assets(limit)
            elif len(assets) == 0:
                print("⚠️ get_popular_assets returned empty list, using fallback")
                assets = self._get_fallback_assets(limit)
                
            # Try backup provider if primary fails
            if (not assets or len(assets) == 0) and self.backup_provider:
                print("🔄 Trying backup provider...")
                try:
                    backup_assets = self.backup_provider.get_popular_assets(limit)
                    if backup_assets and len(backup_assets) > 0:
                        assets = backup_assets
                        print(f"✅ Backup provider returned {len(assets)} assets")
                except Exception as e:
                    print(f"❌ Backup provider failed: {e}")
            
            # Final fallback
            if not assets or len(assets) == 0:
                print("🔄 Using final fallback assets")
                assets = self._get_fallback_assets(limit)
            
            # Ensure we have a list and limit the results
            if isinstance(assets, (list, tuple)):
                assets = list(assets)[:limit]
            else:
                assets = [assets][:limit]
                
            print(f"✅ Final assets list: {len(assets)} items")
            return assets
            
        except Exception as e:
            print(f"❌ Error in get_popular_assets: {e}")
            return self._get_fallback_assets(limit)

    def _get_fallback_assets(self, limit):
        """Get fallback assets when primary source fails"""
        print(f"🔄 Using fallback assets for {self.mode}")
        
        if self.mode == "saham_id":
            fallback = ['BBCA.JK', 'TLKM.JK', 'ASII.JK', 'BMRI.JK', 'BBRI.JK', 
                       'UNVR.JK', 'INDF.JK', 'ICBP.JK', 'ADRO.JK', 'ANTM.JK']
        elif self.mode == "forex":
            fallback = ['EURUSD=X', 'GBPUSD=X', 'USDJPY=X', 'AUDUSD=X', 'USDCAD=X',
                       'USDCHF=X', 'NZDUSD=X', 'EURJPY=X', 'GBPJPY=X', 'AUDJPY=X']
        else:  # crypto
            fallback = ['BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'SOL/USDT', 'XRP/USDT',
                       'ADA/USDT', 'AVAX/USDT', 'DOT/USDT', 'DOGE/USDT', 'MATIC/USDT']
        
        return fallback[:limit]

    def scan_potential_assets(self, limit=None):
        """Enhanced asset scanning with proper error handling"""
        if not self.data_provider:
            print("❌ No data provider for scanning")
            return []

        start_time = time.time()
        
        # Get assets with extra validation
        assets = self.get_popular_assets(limit)
        
        # DOUBLE CHECK: Ensure assets is a list and has length
        if not isinstance(assets, list):
            print(f"❌ CRITICAL: assets is not a list, type: {type(assets)}, value: {assets}")
            assets = []
        
        if not assets:
            print("❌ No assets to scan")
            return []
            
        print(f"🔍 Starting scan of {len(assets)} {self.mode} assets...")
        
        max_signals = self.config.get("max_signals", 10)
        min_score = self.config.get("min_score", 2)
        
        results = []
        successful_scans = 0
        
        for i, asset in enumerate(assets, 1):
            try:
                # Extra validation for each asset
                if asset is None:
                    continue
                    
                asset_str = str(asset).strip()
                if not asset_str:
                    continue
                    
                print(f"Analyzing {i}/{len(assets)}: {asset_str}")
                
                analysis = self.analyze_asset(asset_str)
                
                if (analysis and 
                    analysis.get('action') in ['LONG', 'SHORT'] and 
                    abs(analysis.get('score', 0)) >= min_score):
                    
                    analysis['symbol'] = asset_str
                    analysis['market_type'] = self.mode
                    
                    # Ensure TP levels are in correct order
                    if analysis['action'] == 'LONG':
                        # For LONG: TP1 < TP2 < TP3
                        tp_levels = sorted([analysis['tp1'], analysis['tp2'], analysis['tp3']])
                        analysis['tp1'], analysis['tp2'], analysis['tp3'] = tp_levels
                    else:  # SHORT
                        # For SHORT: TP1 > TP2 > TP3  
                        tp_levels = sorted([analysis['tp1'], analysis['tp2'], analysis['tp3']], reverse=True)
                        analysis['tp1'], analysis['tp2'], analysis['tp3'] = tp_levels
                    
                    # Save to database
                    try:
                        self.db.save_signal(analysis)
                    except Exception as e:
                        print(f"⚠️ Failed to save signal to DB: {e}")
                    
                    results.append(analysis)
                    print(f"✅ Signal found: {asset_str} - {analysis['action']} (Score: {analysis['score']})")

                successful_scans += 1
                time.sleep(0.1)  # Rate limiting
                
            except Exception as e:
                print(f"❌ Error analyzing {asset}: {e}")
                continue

        # Sort by absolute score (highest first)
        results.sort(key=lambda x: abs(x.get('score', 0)), reverse=True)
        
        # Update scan statistics
        self.scan_stats.update({
            'total_assets': len(assets),
            'successful_scans': successful_scans,
            'signals_found': len(results),
            'last_scan_duration': time.time() - start_time,
            'last_scan_time': datetime.now()
        })
        
        print(f"📊 Scan complete: {successful_scans}/{len(assets)} successful, "
              f"{len(results)} signals found in {self.scan_stats['last_scan_duration']:.1f}s")
        
        return results[:max_signals]

    def analyze_asset(self, symbol):
        """Analyze single asset with fallback providers and proper error handling"""
        if not symbol:
            return None
            
        for provider in [self.data_provider, self.backup_provider]:
            if not provider:
                continue
                
            try:
                df = provider.get_ohlcv(symbol, self.timeframe, self.config.get("ohlcv_limit", 200))
                
                # Validate DataFrame
                if (df is not None and 
                    isinstance(df, pd.DataFrame) and 
                    len(df) >= 50 and
                    not df.empty and
                    'close' in df.columns):
                    
                    analysis = self.strategy.analyze(df)
                    if analysis and isinstance(analysis, dict):
                        return analysis
                        
            except Exception as e:
                print(f"Analysis failed for {symbol} with {provider.__class__.__name__}: {e}")
                continue
                
        return None

    def calculate_custom_entry(self, symbol, entry_price):
        """Calculate TP/SL for custom entry with correct TP order"""
        if not self.data_provider or not symbol:
            return None
            
        try:
            df = self.data_provider.get_ohlcv(symbol, self.timeframe, self.config.get("ohlcv_limit", 200))
            if df is not None and len(df) >= 50:
                atr = self.strategy.calculate_atr(df)
                
                # Calculate TP levels
                tp1 = entry_price + (atr * self.strategy.atr_multiplier)
                tp2 = entry_price + (atr * self.strategy.atr_multiplier * 2)
                tp3 = entry_price + (atr * self.strategy.atr_multiplier * 3)
                sl = entry_price - (atr * self.strategy.atr_multiplier)
                
                # Ensure correct TP order: TP1 < TP2 < TP3
                tp_levels = sorted([tp1, tp2, tp3])
                
                return {
                    "symbol": symbol,
                    "entry_price": float(entry_price),
                    "tp1": float(tp_levels[0]),  # Smallest
                    "tp2": float(tp_levels[1]),  # Middle  
                    "tp3": float(tp_levels[2]),  # Largest
                    "sl": float(sl),
                }
                
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
        """Close position with optional exit price"""
        try:
            if exit_price is None:
                # Get current price from position
                position = self.db.get_position_by_id(position_id)
                if position:
                    symbol = position[1]
                    provider = self.get_data_provider(symbol)
                    if provider:
                        ticker = provider.get_ticker(symbol)
                        exit_price = ticker['last'] if ticker else position[3]  # entry_price as fallback
            
            success = self.db.close_position(position_id, exit_price, exit_type)
            return success
        except Exception as e:
            print(f"Error closing position {position_id}: {e}")
            return False

    def get_data_provider(self, symbol):
        """Get appropriate data provider with fallback"""
        if self.data_provider:
            try:
                # Test primary provider
                test_data = self.data_provider.get_ohlcv(symbol, self.timeframe, 10)
                if test_data is not None and len(test_data) > 0:
                    return self.data_provider
            except:
                pass
        
        # Fallback to backup provider
        if self.backup_provider:
            return self.backup_provider
        
        return self.data_provider

    # Pump Fun integration placeholder
    async def scan_pump_fun(self):
        """Scan new tokens on Solana Pump Fun"""
        print("Pump.fun monitoring requires WebSocket connection setup...")
        return []
