import os
import time
import json
import warnings
from datetime import datetime, timedelta
import threading
import schedule
import asyncio

from dotenv import load_dotenv
from strategies import TechnicalAnalysisStrategy
from data_provider import (
    CCXTDataProvider,
    YFinanceDataProvider,
    AlphaVantageProvider,
    DexScreenerProvider
)
from notifier import SoundNotifier
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
                "timeframe": "4h",
                "atr_multiplier": 1.5,
                "entry_range_pct": 0.015,
                "exchange_crypto": "binance",
                "analysis_coins_limit": 100,
                "ohlcv_limit": 200,
                "min_confidence": 0.6,
                "min_score": 2,
                "max_signals": 15,
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

    def update_config(self, new_config):
        """Update configuration dynamically"""
        self.config.update(new_config)
        self.save_config()
        
        # Update strategy parameters if changed
        if 'atr_multiplier' in new_config or 'entry_range_pct' in new_config:
            self.strategy.atr_multiplier = self.config.get("atr_multiplier", 1.5)
            self.strategy.entry_range_pct = self.config.get("entry_range_pct", 0.015)

    # =========================================================
    # Mode / Provider Management
    # =========================================================
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
            
            # Start background tasks
            self.start_background_tasks()
            return True
            
        except Exception as e:
            print(f"✗ Failed to set mode {mode}: {e}")
            self.data_provider = None
            self.backup_provider = None
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
            print(f"Using backup provider for {symbol}")
            return self.backup_provider
        
        return self.data_provider

    # =========================================================
    # Background Tasks & Scheduling
    # =========================================================
    def start_background_tasks(self):
        """Start background tasks for automated operations"""
        if self.scheduler_thread and self.scheduler_thread.is_alive():
            self.stop_background_tasks()
            
        self.stop_scheduler = False
        self.scheduler_thread = threading.Thread(target=self._run_scheduler, daemon=True)
        self.scheduler_thread.start()
        print("✓ Background tasks started")

    def stop_background_tasks(self):
        """Stop all background tasks"""
        self.stop_scheduler = True
        if self.scheduler_thread:
            self.scheduler_thread.join(timeout=5)
        print("✓ Background tasks stopped")

    def _run_scheduler(self):
        """Run scheduled tasks in background thread"""
        update_interval = self.config.get("update_interval", 60)
        scan_interval = self.config.get("scan_interval", 300)
        
        schedule.every(update_interval).seconds.do(self.update_all_prices)
        schedule.every(scan_interval).seconds.do(self.auto_scan_assets)
        schedule.every(1).hours.do(self.cleanup_old_signals)
        
        while not self.stop_scheduler:
            try:
                schedule.run_pending()
            except Exception as e:
                print(f"Scheduler error: {e}")
            time.sleep(1)

    def auto_scan_assets(self):
        """Automated asset scanning triggered by scheduler"""
        if not self.scanner_active:
            return
            
        print(f"\n🔄 Auto-scanning {self.mode} assets at {datetime.now().strftime('%H:%M:%S')}")
        signals = self.scan_potential_assets()
        
        if signals:
            print(f"🎯 Found {len(signals)} signals")
            # Optional: Send notifications for strong signals
            strong_signals = [s for s in signals if s.get('confidence', 0) > 0.8]
            for signal in strong_signals:
                self.notifier.alert_strong_signal(signal)

    # =========================================================
    # Asset Analysis & Scanning
    # =========================================================
    def get_popular_assets(self, limit=None):
        """Get popular assets with enhanced error handling"""
        if not self.data_provider:
            return []

        limit = limit or self.config.get("analysis_coins_limit", 100)
        
        try:
            assets = self.data_provider.get_popular_assets(limit)
            if not assets and self.backup_provider:
                assets = self.backup_provider.get_popular_assets(limit)
                
            return assets[:limit] if assets else []
            
        except Exception as e:
            print(f"Error fetching popular assets: {e}")
            return self._get_fallback_assets(limit)

    def _get_fallback_assets(self, limit):
        """Get fallback assets when primary source fails"""
        if self.mode == "saham_id":
            return ['BBCA.JK', 'TLKM.JK', 'ASII.JK', 'BMRI.JK', 'BBRI.JK', 
                   'UNVR.JK', 'INDF.JK', 'ICBP.JK', 'ADRO.JK', 'ANTM.JK'][:limit]
        elif self.mode == "forex":
            return ['EURUSD=X', 'GBPUSD=X', 'USDJPY=X', 'AUDUSD=X', 'USDCAD=X',
                   'USDCHF=X', 'NZDUSD=X', 'EURJPY=X', 'GBPJPY=X', 'AUDJPY=X'][:limit]
        else:  # crypto
            return ['BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'SOL/USDT', 'XRP/USDT',
                   'ADA/USDT', 'AVAX/USDT', 'DOT/USDT', 'DOGE/USDT', 'MATIC/USDT'][:limit]

    def scan_potential_assets(self, assets=None, limit=None):
        """Enhanced asset scanning with performance tracking"""
        if not self.data_provider:
            return []

        start_time = time.time()
        assets = assets or self.get_popular_assets(limit)
        max_signals = self.config.get("max_signals", 15)
        min_confidence = self.config.get("min_confidence", 0.6)
        min_score = self.config.get("min_score", 2)
        
        print(f"🔍 Scanning {len(assets)} {self.mode} assets...")
        
        results = []
        successful_scans = 0
        
        for i, asset in enumerate(assets, 1):
            try:
                analysis = self.analyze_asset(asset)
                if analysis and analysis.get('action') in ['LONG', 'SHORT']:
                    confidence = analysis.get('confidence', 0)
                    score = analysis.get('score', 0)
                    
                    if (confidence >= min_confidence and 
                        abs(score) >= min_score and
                        analysis.get('current_price', 0) > 0):
                        
                        analysis['symbol'] = asset
                        analysis['market_type'] = self.mode
                        analysis['scan_time'] = datetime.now().isoformat()
                        
                        self.db.save_signal(analysis)
                        results.append(analysis)
                        
                        print(f"✅ {i}/{len(assets)} {asset}: {analysis['action']} "
                              f"(Score: {score}, Conf: {confidence})")
                
                successful_scans += 1
                time.sleep(0.1)  # Rate limiting
                
            except Exception as e:
                print(f"❌ {i}/{len(assets)} {asset}: Error - {e}")
                continue

        # Sort by confidence and score
        results.sort(key=lambda x: (x.get('confidence', 0), abs(x.get('score', 0))), reverse=True)
        
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
        """Analyze single asset with fallback providers"""
        for provider in [self.data_provider, self.backup_provider]:
            if not provider:
                continue
                
            try:
                df = provider.get_ohlcv(symbol, self.timeframe, self.config.get("ohlcv_limit", 200))
                if df is not None and len(df) >= 50:
                    analysis = self.strategy.analyze(df)
                    if analysis:
                        return analysis
            except Exception as e:
                print(f"Analysis failed for {symbol} with {provider.__class__.__name__}: {e}")
                continue
                
        return None

    # =========================================================
    # Position & Portfolio Management
    # =========================================================
    def update_all_prices(self):
        """Update prices for all active positions"""
        if not self.data_provider:
            return
            
        try:
            active_positions = self.get_active_positions()
            updated_count = 0
            
            for position in active_positions:
                symbol = position[1]  # symbol column
                try:
                    provider = self.get_data_provider(symbol)
                    if provider:
                        ticker = provider.get_ticker(symbol)
                        if ticker and 'last' in ticker:
                            current_price = ticker['last']
                            self.db.update_position_current_price(symbol, current_price)
                            updated_count += 1
                except Exception as e:
                    print(f"Error updating price for {symbol}: {e}")
                    continue
            
            if updated_count > 0:
                print(f"✓ Updated prices for {updated_count} positions")
                
        except Exception as e:
            print(f"Error in update_all_prices: {e}")

    def get_active_positions(self):
        """Get active positions with current P&L"""
        try:
            positions = self.db.get_active_positions(self.mode)
            return positions
        except Exception as e:
            print(f"Error fetching active positions: {e}")
            return []

    def get_portfolio_summary(self):
        """Get portfolio summary with performance metrics"""
        try:
            positions = self.get_active_positions()
            total_investment = 0
            current_value = 0
            unrealized_pnl = 0
            
            for position in positions:
                entry_price = position[3]  # entry_price column
                current_price = position[7] or entry_price  # current_price column
                quantity = position[4]  # quantity column
                
                position_value = entry_price * quantity
                current_position_value = current_price * quantity
                
                total_investment += position_value
                current_value += current_position_value
                unrealized_pnl += (current_position_value - position_value)
            
            return {
                'total_positions': len(positions),
                'total_investment': round(total_investment, 2),
                'current_value': round(current_value, 2),
                'unrealized_pnl': round(unrealized_pnl, 2),
                'pnl_percentage': round((unrealized_pnl / total_investment * 100) if total_investment > 0 else 0, 2)
            }
        except Exception as e:
            print(f"Error calculating portfolio summary: {e}")
            return {}

    # =========================================================
    # Signal & Database Management
    # =========================================================
    def cleanup_old_signals(self, hours=24):
        """Clean up signals older than specified hours"""
        try:
            cutoff_time = datetime.now() - timedelta(hours=hours)
            self.db.cleanup_old_signals(cutoff_time)
            print(f"✓ Cleaned up signals older than {hours} hours")
        except Exception as e:
            print(f"Error cleaning up old signals: {e}")

    def get_recent_signals(self, hours=24, min_confidence=0.6):
        """Get recent signals within specified time window"""
        try:
            since_time = datetime.now() - timedelta(hours=hours)
            signals = self.db.get_signals_since(self.mode, since_time)
            
            # Filter by confidence
            filtered_signals = [
                signal for signal in signals 
                if signal[8] and float(signal[8]) >= min_confidence  # confidence column
            ]
            
            return filtered_signals
        except Exception as e:
            print(f"Error getting recent signals: {e}")
            return []

    def delete_weak_signals(self, min_confidence=0.5, min_score=1):
        """Delete signals below confidence and score thresholds"""
        try:
            all_signals = self.db.get_all_signals(self.mode)
            deleted_count = 0
            
            for signal in all_signals:
                confidence = signal[8] if signal[8] else 0  # confidence column
                score = signal[9] if signal[9] else 0  # score column
                
                if float(confidence) < min_confidence or abs(float(score)) < min_score:
                    self.db.delete_signal_by_id(signal[0])  # id column
                    deleted_count += 1
            
            print(f"✓ Deleted {deleted_count} weak signals")
            return deleted_count
        except Exception as e:
            print(f"Error deleting weak signals: {e}")
            return 0

    # =========================================================
    # Trading Operations
    # =========================================================
    def calculate_position_size(self, symbol, risk_per_trade=0.02, account_balance=1000):
        """Calculate position size based on risk management"""
        try:
            analysis = self.analyze_asset(symbol)
            if not analysis or not analysis.get('sl'):
                return None
            
            entry_price = analysis.get('current_price')
            stop_loss = analysis.get('sl')
            risk_per_share = abs(entry_price - stop_loss)
            
            if risk_per_share <= 0:
                return None
            
            risk_amount = account_balance * risk_per_trade
            position_size = risk_amount / risk_per_share
            
            return {
                'symbol': symbol,
                'entry_price': entry_price,
                'stop_loss': stop_loss,
                'position_size': int(position_size),
                'risk_per_share': risk_per_share,
                'risk_amount': risk_amount
            }
        except Exception as e:
            print(f"Error calculating position size for {symbol}: {e}")
            return None

    def close_position(self, position_id, exit_price=None, exit_type="manual"):
        """Close position with optional exit price"""
        try:
            if exit_price is None:
                # Get current price
                position = self.db.get_position_by_id(position_id)
                if position:
                    symbol = position[1]
                    provider = self.get_data_provider(symbol)
                    if provider:
                        ticker = provider.get_ticker(symbol)
                        exit_price = ticker['last'] if ticker else position[3]  # entry_price as fallback
            
            success = self.db.close_position(position_id, exit_price, exit_type)
            if success:
                print(f"✓ Position {position_id} closed at {exit_price}")
            return success
        except Exception as e:
            print(f"Error closing position {position_id}: {e}")
            return False

    # =========================================================
    # System Control
    # =========================================================
    def start_scanner(self):
        """Start automated scanner"""
        self.scanner_active = True
        print("✓ Scanner started")

    def stop_scanner(self):
        """Stop automated scanner"""
        self.scanner_active = False
        print("✓ Scanner stopped")

    def get_system_status(self):
        """Get comprehensive system status"""
        portfolio = self.get_portfolio_summary()
        
        return {
            'mode': self.mode,
            'scanner_active': self.scanner_active,
            'background_tasks_running': self.scheduler_thread and self.scheduler_thread.is_alive(),
            'data_provider': self.data_provider.__class__.__name__ if self.data_provider else 'None',
            'backup_provider': self.backup_provider.__class__.__name__ if self.backup_provider else 'None',
            'portfolio': portfolio,
            'scan_stats': self.scan_stats,
            'config': {
                'timeframe': self.timeframe,
                'min_confidence': self.config.get('min_confidence', 0.6),
                'min_score': self.config.get('min_score', 2),
                'update_interval': self.config.get('update_interval', 60)
            }
        }

# Utility function for quick testing
def test_market_modes():
    """Test function to verify all market modes work"""
    bot = TradingBot()
    
    test_modes = ['crypto', 'forex', 'saham_id']
    
    for mode in test_modes:
        print(f"\n{'='*50}")
        print(f"Testing {mode.upper()} mode")
        print(f"{'='*50}")
        
        if bot.set_mode(mode):
            # Test popular assets
            assets = bot.get_popular_assets(5)
            print(f"Popular assets: {assets}")
            
            # Test analysis
            if assets:
                test_asset = assets[0]
                print(f"Analyzing {test_asset}...")
                analysis = bot.analyze_asset(test_asset)
                if analysis:
                    print(f"Action: {analysis['action']}, Score: {analysis['score']}, Confidence: {analysis['confidence']}")
                else:
                    print("Analysis failed")
        
        time.sleep(2)  # Rate limiting between modes

if __name__ == "__main__":
    test_market_modes()
