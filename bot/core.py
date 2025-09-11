import os
import time
import json
import warnings
from datetime import datetime
import threading
import schedule

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


class TradingBot:
    def __init__(self, config_path="config/config.json"):
        # === Config & Setup ===
        self.config_path = config_path
        self.load_config()

        self.mode = None
        self.data_provider = None
        self.pump_provider = None

        # === Core Modules ===
        self.strategy = TechnicalAnalysisStrategy(
            atr_multiplier=self.config.get("atr_multiplier", 1.0),
            entry_range_pct=self.config.get("entry_range_pct", 0.02),
        )
        self.notifier = SoundNotifier()
        self.db = DatabaseHandler()

        # === State ===
        self.timeframe = self.config.get("timeframe", "1h")
        self.alert_active = False
        self.scanner_active = False
        self.entry_positions = {}
        self.position_ids = {}
        
        # === Background Tasks ===
        self.scheduler_thread = None
        self.stop_scheduler = False

    # =========================================================
    # Config Handling
    # =========================================================
    def load_config(self):
        """Load configuration from config.json"""
        try:
            os.makedirs("config", exist_ok=True)
            with open(self.config_path, "r") as f:
                self.config = json.load(f)
        except FileNotFoundError:
            self.config = {
                "timeframe": "1h",
                "atr_multiplier": 1.0,
                "entry_range_pct": 0.02,
                "exchange_crypto": "binance",
                "analysis_coins_limit": 50,
                "ohlcv_limit": 200,
                "min_score": 3,  # Reduced from 5 to 3 to get more signals
                "max_signals": 5,
                "update_interval": 30,  # Add update interval for background tasks
            }
            self.save_config()

    def save_config(self):
        """Save configuration to config.json"""
        os.makedirs("config", exist_ok=True)
        with open(self.config_path, "w") as f:
            json.dump(self.config, f, indent=4)

    # =========================================================
    # Mode / Provider
    # =========================================================
    def set_mode(self, mode):
        """Set market mode (crypto, forex, saham_id)"""
        self.mode = mode.lower()
        if self.mode == "crypto":
            self.data_provider = CCXTDataProvider(
                self.config.get("exchange_crypto", "binance"), "", ""
            )
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

        print(f"Mode set to: {self.mode.upper()} with data provider: {self.data_provider}")
        
        # Start background tasks when mode is set
        self.start_background_tasks()
        
        return True

    # =========================================================
    # Background Tasks
    # =========================================================
    def start_background_tasks(self):
        """Start background tasks for price updates and scanning"""
        if self.scheduler_thread and self.scheduler_thread.is_alive():
            self.stop_background_tasks()
            
        self.stop_scheduler = False
        self.scheduler_thread = threading.Thread(target=self._run_scheduler, daemon=True)
        self.scheduler_thread.start()
        print("Background tasks started")

    def stop_background_tasks(self):
        """Stop background tasks"""
        self.stop_scheduler = True
        if self.scheduler_thread:
            self.scheduler_thread.join(timeout=5)
        print("Background tasks stopped")

    def _run_scheduler(self):
        """Run scheduled tasks in background"""
        # Update prices every 30 seconds
        schedule.every(self.config.get("update_interval", 30)).seconds.do(self.update_all_prices)
        
        # Run scanner every 5 minutes
        schedule.every(5).minutes.do(self.scan_potential_assets)
        
        while not self.stop_scheduler:
            schedule.run_pending()
            time.sleep(1)

    def update_all_prices(self):
        """Update prices for all active positions"""
        if not self.data_provider:
            return
            
        try:
            active_positions = self.get_active_positions()
            for position in active_positions:
                symbol = position[1]  # symbol is at index 1
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

    # =========================================================
    # Asset Handling
    # =========================================================
    def get_popular_assets(self, limit=None):
        """Get list of popular assets for the selected market"""
        if not self.data_provider:
            print("No data provider available.")
            return []

        limit = limit or self.config.get("analysis_coins_limit", 50)
        try:
            assets = self.data_provider.get_popular_assets(limit)
            if not assets:
                print(f"No popular assets found for {self.mode}")
                # Return fallback assets based on mode
                if self.mode == "crypto":
                    assets = [
                        'BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'SOL/USDT', 'ADA/USDT',
                        'XRP/USDT', 'DOT/USDT', 'DOGE/USDT', 'AVAX/USDT', 'MATIC/USDT'
                    ][:limit]
                elif self.mode == "forex":
                    assets = [
                        'EURUSD=X', 'GBPUSD=X', 'USDJPY=X', 'AUDUSD=X', 'USDCAD=X'
                    ][:limit]
                elif self.mode == "saham_id":
                    assets = [
                        'BBCA.JK', 'TLKM.JK', 'ASII.JK', 'BMRI.JK', 'BBNI.JK'
                    ][:limit]
            return assets
        except Exception as e:
            print(f"Error fetching popular assets: {e}")
            return []

    def scan_potential_assets(self, limit=None):
        """Scan popular assets and return potential trading signals"""
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
                if df is None or len(df) < 50:  # Reduced from 100 to 50 to allow more assets
                    print(f"Insufficient data for {asset}")
                    continue

                analysis = self.strategy.analyze(df)
                if (
                    analysis
                    and analysis["action"] in ["LONG", "SHORT"]
                    and analysis["score"] >= self.config.get("min_score", 3)  # Reduced from 5 to 3
                ):
                    analysis["symbol"] = asset
                    analysis["market_type"] = self.mode
                    self.db.save_signal(analysis)
                    results.append(analysis)

                time.sleep(0.2)  # avoid rate limits
            except Exception as e:
                print(f"Error analyzing {asset}: {e}")
                continue

        results.sort(key=lambda x: x.get("score", 0), reverse=True)
        return results[: self.config.get("max_signals", 5)]

    def analyze_asset(self, symbol):
        """Analyze a specific asset and return signal"""
        if not self.data_provider:
            print("No data provider for analysis.")
            return None
        try:
            df = self.data_provider.get_ohlcv(
                symbol, self.timeframe, self.config.get("ohlcv_limit", 200)
            )
            if df is not None and len(df) >= 50:  # Reduced from 100 to 50
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

    async def scan_pump_fun(self):
        """Scan new tokens on Solana Pump Fun"""
        if not self.pump_provider:
            print("No Pump Fun provider available.")
            return []
        try:
            return await self.pump_provider.monitor_new_tokens(10)
        except Exception as e:
            print(f"Error scanning Pump Fun: {e}")
            return []

    def calculate_custom_entry(self, symbol, entry_price):
        """Calculate TP/SL for a custom entry price"""
        if not self.data_provider:
            print("No data provider for custom entry.")
            return None
        try:
            df = self.data_provider.get_ohlcv(
                symbol, self.timeframe, self.config.get("ohlcv_limit", 200)
            )
            if df is not None and len(df) >= 50:  # Reduced from 100 to 50
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

    # =========================================================
    # Database Helpers
    # =========================================================
    def get_active_positions(self):
        """Get active positions from database"""
        try:
            positions = self.db.get_active_positions(self.mode)
            # Update prices before returning
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
        """Get trade history from database"""
        try:
            return self.db.get_trade_history(self.mode, limit)
        except Exception as e:
            print(f"Error fetching trade history: {e}")
            return []

    def delete_signals_not_selected(self, selected_symbols):
        """Delete non-selected signals from signals table"""
        try:
            all_signals = self.db.get_all_signals(self.mode)
            for signal in all_signals:
                symbol = signal[1]  # column: symbol
                if symbol not in selected_symbols:
                    self.db.delete_signal_by_symbol(symbol, self.mode)
                    print(f"Deleted non-selected signal for {symbol}")
        except Exception as e:
            print(f"Error deleting non-selected signals: {e}")

    def close_position(self, position_id, exit_price, exit_type="manual"):
        """Close a position with the given exit price"""
        try:
            return self.db.close_position(position_id, exit_price, exit_type)
        except Exception as e:
            print(f"Error closing position: {e}")
            return False