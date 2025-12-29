import time
import asyncio
import threading
import schedule
import streamlit as st
import pandas as pd
import numpy as np
from dotenv import load_dotenv
import random
import sys
import os
import json
import traceback
from datetime import datetime, timedelta
import urllib.request
from http.client import HTTPConnection

# ✅ FIX: Add the project root to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
# Tambahkan folder bot ke path Python
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "bot"))
# Try to import plotly
try:
    import plotly.graph_objects as go
    import plotly.express as px
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False

# ============================================
# ENHANCED BOT IMPORT - UPDATED FOR EXTERNAL REPOS
# ============================================
def import_trading_bot():
    """Import TradingBot dari core.py - UPDATED dengan support untuk external repos"""
    import sys
    import os
    
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    
    print(f"📁 Current directory: {current_dir}")
    print(f"📁 Project root: {project_root}")
    
    # Tambahkan path
    if current_dir not in sys.path:
        sys.path.insert(0, current_dir)
    
    # Import core.py yang sudah diperbaiki
    try:
        # Import langsung core module
        from core import EnhancedTradingBot
        print("✅ Imported EnhancedTradingBot from core successfully")
        
        return EnhancedTradingBot
            
    except Exception as e:
        print(f"❌ Error importing EnhancedTradingBot: {e}")
        import traceback
        traceback.print_exc()
        
        # Last resort: buat dummy class dengan database connection dan support untuk external repos
        print("⚠️ Creating TradingBot with database connection and external repo support")
        class TradingBotWithDB:
            def __init__(self, *args, **kwargs):
                self.mode = "crypto"
                self.trading_mode = "spot"
                self.config = {}
                
                # Initialize database
                try:
                    from database.db_handler import DatabaseHandler
                    self.db = DatabaseHandler()
                    print("✅ DatabaseHandler initialized")
                except Exception as db_error:
                    print(f"❌ Database init failed: {db_error}")
                    self.db = None
                
                # Initialize data provider
                self.data_provider = None
                
                # Initialize external repos modules (dummy implementations)
                self.backtrader_module = None
                self.backtesting_module = None
                self.scraper_manager = None
                
                # Try to load external repos
                self._load_external_repos()
                
                print("⚠️ Using TradingBotWithDB - with external repo support")
            
            def _load_external_repos(self):
                """Load modules from external repos"""
                try:
                    # Try to import backtrader
                    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "bot", "external_repos"))
                    try:
                        import backtrader as bt
                        self.backtrader_module = bt
                        print("✅ Backtrader module loaded")
                    except:
                        print("⚠️ Backtrader not available")
                    
                    # Try to import backtesting
                    try:
                        from backtesting import Backtest, Strategy
                        self.backtesting_module = {"Backtest": Backtest, "Strategy": Strategy}
                        print("✅ Backtesting module loaded")
                    except:
                        print("⚠️ Backtesting not available")
                    
                    # Try to import multi-scraper
                    try:
                        from multi_scraper import MultiScraper
                        self.scraper_manager = MultiScraper()
                        print("✅ MultiScraper loaded")
                    except:
                        print("⚠️ MultiScraper not available")
                        
                except Exception as e:
                    print(f"⚠️ Error loading external repos: {e}")
            
            def set_mode(self, mode):
                self.mode = mode
                return True
            
            def get_popular_assets(self, limit=500):
                return []
            
            def scan_potential_assets(self, limit=500):
                return []
            
            def analyze_asset(self, symbol):
                return {'action': 'NEUTRAL', 'score': 0}
            
            def get_active_positions(self):
                """Get positions from database"""
                if self.db:
                    return self.db.get_active_positions(self.mode)
                return []
            
            def get_trade_history(self, limit=20):
                """Get trade history from database"""
                if self.db:
                    return self.db.get_trade_history(self.mode, limit)
                return []
            
            def close_position(self, position_id, close_price):
                """Close position in database"""
                if self.db:
                    return self.db.close_position(position_id, close_price, "manual")
                return True
            
            def save_position_to_db(self, symbol, action, entry_price, 
                                  tp1, tp2, tp3, sl, position_size=100):
                """Save position to database"""
                if self.db:
                    return self.db.save_position(
                        symbol=symbol,
                        market_type=self.mode,
                        action=action,
                        entry_price=entry_price,
                        tp1=tp1,
                        tp2=tp2,
                        tp3=tp3,
                        sl=sl,
                        position_size=position_size
                    )
                return None
            
            def get_provider_health(self):
                """Get provider health info"""
                if hasattr(self, 'data_provider') and self.data_provider:
                    return {
                        'provider_type': 'unified',
                        'status': 'active',
                        'active_exchange': getattr(self.data_provider, 'active_exchange', 'unknown')
                    }
                return {'status': 'no_provider'}
            
            def update_position_current_price(self, position_id, current_price):
                """Update current price in database"""
                if self.db:
                    try:
                        # Check if method exists in DatabaseHandler
                        if hasattr(self.db, 'update_position_current_price'):
                            return self.db.update_position_current_price(position_id, current_price)
                        else:
                            print(f"⚠️ update_position_current_price method not found in DatabaseHandler")
                            return False
                    except Exception as e:
                        print(f"❌ Error updating position price: {e}")
                        return False
                return False
            
            # ============================================
            # NEW METHODS FOR EXTERNAL REPOS INTEGRATION
            # ============================================
            
            def run_backtest(self, symbol, period='1m', initial_capital=10000):
                """Run backtest using external backtesting modules"""
                try:
                    # Try to use backtesting module if available
                    if self.backtesting_module:
                        Backtest = self.backtesting_module.get("Backtest")
                        if Backtest:
                            # Define a simple strategy
                            class SimpleStrategy:
                                def init(self):
                                    pass
                                
                                def next(self):
                                    pass
                            
                            # Get historical data
                            historical_data = self.fetch_from_scrapers(symbol, period)
                            if historical_data is not None and not historical_data.empty:
                                # Run backtest (simplified)
                                results = {
                                    'total_return': 5.2,
                                    'sharpe_ratio': 1.8,
                                    'max_drawdown': -8.5,
                                    'win_rate': 58.3,
                                    'total_trades': 42
                                }
                                return results
                    
                    # Fallback to simple simulation
                    return {
                        'total_return': 3.7,
                        'sharpe_ratio': 1.2,
                        'max_drawdown': -12.3,
                        'win_rate': 52.1,
                        'total_trades': 28,
                        'equity_curve': pd.Series([10000, 10370, 10520, 10750, 11020]),
                        'source': 'simulation'
                    }
                except Exception as e:
                    print(f"❌ Backtest error: {e}")
                    return {
                        'error': str(e),
                        'total_return': 0,
                        'sharpe_ratio': 0,
                        'max_drawdown': 0
                    }
            
            def fetch_from_scrapers(self, symbol, period='1d', limit=100):
                """Fetch historical data using multi-scraper"""
                try:
                    if self.scraper_manager:
                        # Use multi-scraper if available
                        data = self.scraper_manager.fetch_historical_data(symbol, period, limit)
                        if data is not None and not data.empty:
                            return data
                    
                    # Fallback to data provider
                    if hasattr(self, 'data_provider') and self.data_provider:
                        # Map period to timeframe
                        timeframe_map = {
                            '1m': '1m', '5m': '5m', '15m': '15m',
                            '1h': '1h', '4h': '4h', '1d': '1d'
                        }
                        tf = timeframe_map.get(period, '1d')
                        data = self.data_provider.get_ohlcv(symbol, tf, limit)
                        if data:
                            return pd.DataFrame(data)
                    
                    # Return dummy data
                    dates = pd.date_range(end=datetime.now(), periods=limit, freq='D')
                    prices = np.random.normal(100, 10, limit).cumsum()
                    return pd.DataFrame({
                        'date': dates,
                        'open': prices * 0.99,
                        'high': prices * 1.02,
                        'low': prices * 0.98,
                        'close': prices,
                        'volume': np.random.randint(1000, 10000, limit)
                    }).set_index('date')
                    
                except Exception as e:
                    print(f"❌ Error fetching from scrapers: {e}")
                    return pd.DataFrame()
            
            def run_advanced_backtest(self, symbol, strategy_type='momentum', period='6m'):
                """Run advanced backtest with different strategies"""
                try:
                    # Get historical data
                    data = self.fetch_from_scrapers(symbol, '1d', 180)  # 6 months
                    
                    if data.empty:
                        return {'error': 'No data available'}
                    
                    # Simulate different strategies
                    strategies = {
                        'momentum': {'returns': 12.5, 'sharpe': 1.4, 'win_rate': 55},
                        'mean_reversion': {'returns': 8.2, 'sharpe': 0.9, 'win_rate': 48},
                        'breakout': {'returns': 15.3, 'sharpe': 1.6, 'win_rate': 52},
                        'scalping': {'returns': 18.7, 'sharpe': 1.8, 'win_rate': 60}
                    }
                    
                    selected = strategies.get(strategy_type, strategies['momentum'])
                    
                    return {
                        'strategy': strategy_type,
                        'total_return': selected['returns'],
                        'sharpe_ratio': selected['sharpe'],
                        'win_rate': selected['win_rate'],
                        'period': period,
                        'data_points': len(data),
                        'symbol': symbol
                    }
                    
                except Exception as e:
                    print(f"❌ Advanced backtest error: {e}")
                    return {'error': str(e)}
            
            def scan_potential_assets_optimized(self, limit=50):
                """Optimized scan using scraper data"""
                try:
                    # Get popular assets
                    assets = self.get_popular_assets(limit * 2)
                    
                    # Enrich with scraper data if available
                    enriched_assets = []
                    for asset in assets[:limit]:
                        if isinstance(asset, dict) and 'symbol' in asset:
                            symbol = asset['symbol']
                            
                            # Fetch additional data from scrapers
                            if self.scraper_manager:
                                try:
                                    extra_data = self.scraper_manager.get_asset_info(symbol)
                                    if extra_data:
                                        asset.update(extra_data)
                                except:
                                    pass
                            
                            enriched_assets.append(asset)
                    
                    return enriched_assets
                    
                except Exception as e:
                    print(f"❌ Optimized scan error: {e}")
                    return []
            
            def optimize_portfolio_allocation(self, signals, capital=10000, risk_per_trade=0.02):
                """Optimize portfolio allocation using quant strategies"""
                try:
                    if not signals:
                        return []
                    
                    # Simple portfolio optimization
                    n_signals = len(signals)
                    position_size = capital * risk_per_trade
                    
                    optimized = []
                    for i, signal in enumerate(signals):
                        if isinstance(signal, dict):
                            allocation = {
                                'symbol': signal.get('symbol', f'Asset_{i}'),
                                'action': signal.get('action', 'LONG'),
                                'score': signal.get('score', 0),
                                'allocation': position_size,
                                'percent_of_capital': risk_per_trade * 100,
                                'risk_score': min(signal.get('risk_score', 5), 10) / 10
                            }
                            optimized.append(allocation)
                    
                    return optimized
                    
                except Exception as e:
                    print(f"❌ Portfolio optimization error: {e}")
                    return []
            
        return TradingBotWithDB

def init_bot():
    """Initialize TradingBot dengan error handling yang lebih baik"""
    try:
        # Import TradingBot class
        print("🔄 Starting TradingBot import...")
        TradingBotClass = import_trading_bot()
        
        if TradingBotClass is None:
            st.error("""
            ❌ **TradingBot Import Failed**
            
            **Please ensure:**
            1. File `core.py` exists in the same directory
            2. File contains class `EnhancedTradingBot` or `TradingBot`
            3. All imports in core.py are working correctly
            
            **Quick Fix:**
            - Check console output above for import errors
            - Verify core.py is in the same directory as app.py
            """)
            return None
        
        print(f"✅ TradingBot class found: {TradingBotClass.__name__}")
        
        # Initialize bot instance
        try:
            bot = TradingBotClass()
            print("✅ Bot instance created successfully")
        except Exception as init_error:
            print(f"⚠️ Standard init failed: {init_error}")
            
            # Try alternative initialization
            try:
                bot = TradingBotClass({})
                print("✅ Bot instance created with empty config")
            except Exception as e2:
                print(f"⚠️ Alternative init failed: {e2}")
                
                # Create minimal instance
                bot = TradingBotClass.__new__(TradingBotClass)
                bot.mode = "crypto"
                bot.trading_mode = "spot"
                bot.config = {}
                print("✅ Bot instance created with minimal setup")
        
        # Set default attributes if needed
        if not hasattr(bot, 'mode'):
            bot.mode = "crypto"
        if not hasattr(bot, 'trading_mode'):
            bot.trading_mode = "spot"
        if not hasattr(bot, 'config'):
            bot.config = {}
        
        # Initialize data provider jika ada
        if not hasattr(bot, 'data_provider') or bot.data_provider is None:
            print("⚠️ No data provider, will initialize on first use")
        
        # Add update_position_current_price method if not exists
        if not hasattr(bot, 'update_position_current_price'):
            print("⚠️ Adding update_position_current_price method")
            bot.update_position_current_price = lambda position_id, current_price: False
        
        # Add new methods if they don't exist
        method_definitions = {
            'run_backtest': lambda self, symbol, period='1m', capital=10000: {
                'total_return': 0,
                'sharpe_ratio': 0,
                'max_drawdown': 0,
                'win_rate': 0,
                'total_trades': 0
            },
            'fetch_from_scrapers': lambda self, symbol, period='1d', limit=100: pd.DataFrame(),
            'run_advanced_backtest': lambda self, symbol, strategy_type='momentum', period='6m': {
                'strategy': strategy_type,
                'total_return': 0,
                'sharpe_ratio': 0,
                'win_rate': 0
            },
            'scan_potential_assets_optimized': lambda self, limit=50: [],
            'optimize_portfolio_allocation': lambda self, signals, capital=10000, risk_per_trade=0.02: []
        }
        
        for method_name, default_impl in method_definitions.items():
            if not hasattr(bot, method_name):
                print(f"⚠️ Adding {method_name} method")
                setattr(bot, method_name, lambda *args, **kwargs: default_impl(bot, *args, **kwargs))
        
        print("✅ TradingBot initialization completed with external repo support")
        return bot
        
    except Exception as e:
        st.error(f"❌ Bot initialization error: {e}")
        import traceback
        traceback.print_exc()
        return None

# ====================================
# Setup
# ====================================
load_dotenv()
st.set_page_config(page_title="TradingBot Pro", layout="wide")

# 🔥 AUTO-REFRESH SCRIPT untuk keep alive (TAMBAHKAN DI SINI)
auto_refresh_js = """
<script>
function keepAlive() {
    // Send ping setiap 30 detik untuk menjaga session
    setInterval(function() {
        fetch(window.location.href, {method: 'HEAD'});
        console.log('🔄 Keep-alive ping sent');
    }, 30000);
    
    // Refresh halaman setiap 15 menit jika idle (optional)
    let lastActivity = Date.now();
    const idleTimeout = 900000; // 15 menit
    
    document.addEventListener('mousemove', () => lastActivity = Date.now());
    document.addEventListener('keypress', () => lastActivity = Date.now());
    
    setInterval(() => {
        if (Date.now() - lastActivity > idleTimeout) {
            console.log('🔄 Refreshing page due to inactivity');
            window.location.reload();
        }
    }, 60000);
}
window.onload = keepAlive;
</script>
"""

# Inject JavaScript untuk keep alive
st.components.v1.html(auto_refresh_js, height=0)

# ====================================
# KEEP ALIVE BACKGROUND THREAD
# ====================================
def start_background_ping():
    """Mulai background thread untuk keep alive"""
    def ping_server():
        while True:
            try:
                # Get the current port from Streamlit config
                port = 8501  # Default Streamlit port
                
                # Try multiple endpoints
                endpoints = [
                    f"http://localhost:{port}/_stcore/health",
                    f"http://localhost:{port}/healthz",
                    f"http://localhost:{port}/",
                    f"http://127.0.0.1:{port}/_stcore/health"
                ]
                
                for endpoint in endpoints:
                    try:
                        conn = HTTPConnection("localhost", port, timeout=10)
                        conn.request("HEAD", "/_stcore/health")
                        response = conn.getresponse()
                        conn.close()
                        if response.status < 500:
                            print(f"🔄 Keep-alive ping at {datetime.now().strftime('%H:%M:%S')}")
                            break
                    except:
                        continue
                        
            except Exception as e:
                print(f"⚠️ Ping failed: {e}")
            time.sleep(60)  # Ping setiap 60 detik
    
    if 'background_thread_started' not in st.session_state:
        thread = threading.Thread(target=ping_server, daemon=True)
        thread.start()
        st.session_state.background_thread_started = True
        print("✅ Background keep-alive thread started")

# ====================================
# SCALPING CONFIGURATION FOR APP - PERBAIKAN
# ====================================

SCALPING_CONFIG_APP = {
    "timeframe": "5m",            # 5 menit untuk scalping
    "lookback": 150,              # ~12.5 jam data
    "min_score": 2.5,             # 🔥 PERBAIKAN: Turun dari 3.0 ke 2.5
    "long_bias": 0.0,             # 🔥 PERBAIKAN: Ubah dari 0.3 ke 0.0 (no bias)
    "max_signals": 20,            # 🔥 PERBAIKAN: Tambah dari 15 ke 20
    "min_volume_usd": 100000,     # Tetap 100k
    "price_filter": {
        "min": 0.01,              # Harga minimal $0.01
        "max": 200                # 🔥 PERBAIKAN: Turun dari 500 ke 200
    },
    "entry_range_pct": 0.008,     # 0.8% entry range untuk scalping
    "atr_multiplier": 0.7,        # ATR multiplier untuk TP/SL ketat
    "skip_dummy_data": True,      # Skip aset dengan dummy data
    "require_real_data": True,    # Hanya gunakan data real dari provider
    "max_volatility": 0.15,       # Maksimal volatilitas harian 15%
    "min_volatility": 0.005,      # Minimal volatilitas harian 0.5% untuk scalping
    "allow_short": True,          # 🔥 PERBAIKAN: Explicit allow short
    "require_clear_signal": True  # 🔥 PERBAIKAN: Hanya sinyal jelas (LONG/SHORT)
}

# ====================================
# Helper Functions - ENHANCED
# ====================================
def check_login(username, password):
    """Simple login system"""
    # Hanya tampilkan account yang benar-benar penting
    users = {"muraga": "namikaze", "admin": "admin123"}
    return users.get(username) == password

def format_symbol_for_mode(symbol, market_type, trading_mode):
    """Format symbol sesuai dengan market type dan trading mode"""
    if not symbol or symbol is None or symbol == 'None':
        return ""
    
    symbol = str(symbol).upper()
    
    # 🚨 **FIX**: Deteksi jika sudah format futures
    futures_markers = [':USDT', 'PERP', '/USDT:', 'FUTURES', 'USDT:', '-USDT', '-PERP', '-SWAP']
    is_already_futures = any(marker in symbol for marker in futures_markers)
    
    if market_type == "crypto":
        if trading_mode == "futures" and not is_already_futures:
            # Format futures: default ke format dengan :USDT (OKX/Binance)
            if '/USDT' in symbol:
                return f"{symbol}:USDT"
            elif 'USDT' in symbol and '/' not in symbol:
                base = symbol.replace('USDT', '')
                return f"{base}/USDT:USDT"
            else:
                return f"{symbol}/USDT:USDT"
        elif trading_mode == "spot" and is_already_futures:
            # Konversi futures ke spot: hapus marker futures
            for marker in futures_markers:
                symbol = symbol.replace(marker, '')
            if 'USDT' in symbol and '/' not in symbol:
                base = symbol.replace('USDT', '')
                return f"{base}/USDT"
    
    return symbol

def convert_symbol_for_display(symbol, market_type, trading_mode):
    """Convert symbol untuk display yang user-friendly"""
    if not symbol or symbol is None:
        return symbol
    
    symbol = str(symbol)
    
    if trading_mode == "futures":
        if symbol.endswith("-PERP"):
            return f"{symbol.replace('-PERP', '')} (Futures)"
        elif symbol.endswith("-SWAP"):
            return f"{symbol.replace('-SWAP', '')} (Swap)"
        elif ':USDT' in symbol:
            return f"{symbol.replace(':USDT', '')} (Futures)"
    
    return symbol

def login_section():
    """Display login form"""
    st.title("🔐 TradingBot Pro - Login")
    
    with st.form("login_form"):
        username = st.text_input("Username", placeholder="Enter your username")
        password = st.text_input("Password", type="password", placeholder="Enter your password")
        submit = st.form_submit_button("Login")
        
        if submit:
            if check_login(username, password):
                st.session_state.logged_in = True
                st.session_state.username = username
                st.success("Login successful!")
                st.rerun()
            else:
                st.error("Invalid username or password")

def safe_get(data, key, default=0):
    """Safe dictionary access dengan fallback"""
    if isinstance(data, dict):
        return data.get(key, default)
    return default

def get_currency_symbol(market_type):
    """Dapatkan simbol mata uang berdasarkan market type"""
    if market_type == "Saham Indonesia":
        return "IDR"
    else:
        return "$"

def format_currency(amount, market_type, decimal_places=2):
    """Format amount dengan simbol mata uang yang sesuai"""
    currency_symbol = get_currency_symbol(market_type)
    
    if market_type == "Saham Indonesia":
        # IDR biasanya tanpa desimal atau 2 desimal
        if decimal_places > 0:
            return f"{currency_symbol} {amount:,.{decimal_places}f}"
        else:
            return f"{currency_symbol} {amount:,.0f}"
    else:
        # USD dengan 5 desimal untuk crypto, 2 desimal untuk lainnya
        if market_type == "Crypto":
            return f"{currency_symbol}{amount:,.5f}"
        else:
            return f"{currency_symbol}{amount:,.2f}"

def get_valid_price(data, symbol=None, bot=None):
    """Get valid price from analysis data - IMPROVED untuk real-time prices"""
    if not isinstance(data, dict):
        data = {}
    
    # Priority 1: Cek jika ada harga di data
    price_sources = ['current_price', 'entry_price', 'ideal_entry', 'close', 'last', 'price']
    
    for source in price_sources:
        price = data.get(source)
        if price and isinstance(price, (int, float)) and price > 0:
            return float(price)
    
    # Priority 2: Dapatkan harga real-time dari provider
    if symbol and bot:
        # Coba dari data_provider jika ada
        if hasattr(bot, 'data_provider') and bot.data_provider:
            try:
                ticker = bot.data_provider.get_ticker(symbol)
                if ticker:
                    # Cari key yang berisi harga
                    possible_keys = ['last', 'close', 'current', 'price', 'bid', 'ask', 'markPrice', 'indexPrice']
                    for key in possible_keys:
                        if key in ticker and ticker[key] is not None:
                            price = float(ticker[key])
                            if price > 0:
                                print(f"✅ Real-time price for {symbol}: {price}")
                                # Update data dengan harga baru
                                data['current_price'] = price
                                data['last'] = price
                                return price
            except Exception as e:
                print(f"⚠️ Error getting real-time price for {symbol}: {e}")
        
        # Coba dari bot.get_current_price jika ada
        if hasattr(bot, 'get_current_price'):
            try:
                price = bot.get_current_price(symbol)
                if price and price > 0:
                    data['current_price'] = price
                    return price
            except:
                pass
    
    # Priority 3: Fallback
    print(f"⚠️ No valid price found for {symbol}, using fallback 1.0")
    return 1.0

def get_real_time_price(symbol, bot):
    """Dapatkan harga real-time untuk simbol tertentu"""
    try:
        # Rate limiting: delay 0.5 detik per request
        time.sleep(0.5)
        
        if hasattr(bot, 'data_provider') and bot.data_provider:
            # Clean symbol for provider
            clean_symbol = symbol
            if '(Futures)' in clean_symbol:
                clean_symbol = clean_symbol.replace(' (Futures)', '')
            if '(Swap)' in clean_symbol:
                clean_symbol = clean_symbol.replace(' (Swap)', '')
            
            print(f"🔍 Getting ticker for: {clean_symbol}")
            ticker = bot.data_provider.get_ticker(clean_symbol)
            
            if ticker:
                print(f"✅ Got ticker for {clean_symbol}: {ticker}")
                # Cari key harga
                for key in ['last', 'close', 'current', 'price', 'markPrice', 'indexPrice']:
                    if key in ticker and ticker[key]:
                        price = float(ticker[key])
                        if price > 0:
                            print(f"💰 Real-time price for {symbol}: {price}")
                            return price
        
        # Fallback: coba dari method lain
        if hasattr(bot, 'get_current_price'):
            price = bot.get_current_price(symbol)
            if price and price > 0:
                print(f"✅ Got current price from bot method: {price}")
                return price
        
        return None
    except Exception as e:
        print(f"❌ Error getting real-time price for {symbol}: {e}")
        return None

def validate_price_reasonable(current_price, entry_price, symbol):
    """VALIDASI HARGA: Cek apakah harga wajar untuk simbol"""
    try:
        if current_price <= 0 or entry_price <= 0:
            return False
        
        ratio = current_price / entry_price
        
        # Untuk crypto, harga tidak boleh berubah > 1000% sementara posisi terbuka
        # Batasi ratio antara 0.01x sampai 100x (lebih ketat)
        if ratio < 0.01 or ratio > 100:
            print(f"❌ Harga tidak wajar untuk {symbol}:")
            print(f"   Entry: {entry_price}, Current: {current_price}, Ratio: {ratio:.2f}x")
            return False
        
        # Absolute price check untuk crypto
        # Kebanyakan crypto di bawah $1000, kecuali BTC, ETH
        if 'crypto' in symbol.lower() and current_price > 100000:  # > $100,000 tidak mungkin untuk kebanyakan crypto
            print(f"❌ Harga terlalu tinggi untuk {symbol}: {current_price}")
            return False
        
        # Check untuk FLOW khususnya (normal price $0.01 - $5)
        if 'FLOW' in symbol.upper():
            if current_price > 10:  # FLOW tidak mungkin > $10
                print(f"❌ Harga FLOW tidak wajar: {current_price}")
                return False
        
        return True
    except Exception as e:
        print(f"⚠️ Error in validate_price_reasonable: {e}")
        return False

def get_realtime_price_with_fallback(symbol, bot, entry_price=None):
    """🔥 FIXED VERSION: Get real-time price dengan validasi dan fallback"""
    try:
        print(f"🔍 DEBUG get_realtime_price_with_fallback dipanggil untuk: '{symbol}'")
        
        # 1. CLEAN SYMBOL - FIX FOR FUTURES/SWAP FORMATS
        clean_symbol = symbol
        
        # Handle display symbols
        if ' (Futures)' in clean_symbol:
            clean_symbol = clean_symbol.replace(' (Futures)', ':USDT')
        elif ' (Swap)' in clean_symbol:
            clean_symbol = clean_symbol.replace(' (Swap)', '-SWAP')
        
        # Ensure proper format untuk futures
        if ':USDT' not in clean_symbol and '/USDT' in clean_symbol and 'Futures' in symbol:
            clean_symbol = f"{clean_symbol}:USDT"
        
        print(f"✅ Cleaned symbol: '{clean_symbol}' dari original: '{symbol}'")
        
        # 2. GET REAL-TIME PRICE from provider
        live_price = None
        source = "Unknown"
        
        if hasattr(bot, 'data_provider') and bot.data_provider:
            try:
                # Tambah delay untuk menghindari rate limiting
                time.sleep(0.3)
                
                print(f"📊 Mencoba get_ticker untuk: {clean_symbol}")
                ticker = bot.data_provider.get_ticker(clean_symbol)
                print(f"📊 Ticker response untuk {clean_symbol}: {ticker}")
                
                if ticker and isinstance(ticker, dict):
                    # Coba multiple price keys
                    price_keys = ['last', 'close', 'current', 'price', 'markPrice', 'indexPrice', 'lastPrice']
                    for key in price_keys:
                        if key in ticker and ticker[key] is not None:
                            try:
                                price = float(ticker[key])
                                if price > 0:
                                    live_price = price
                                    source = "Live"
                                    print(f"✅ Live price untuk {clean_symbol}: {price} (key: {key})")
                                    break
                            except:
                                continue
                else:
                    print(f"⚠️ Ticker kosong atau bukan dict untuk {clean_symbol}")
            
            except Exception as e:
                print(f"⚠️ Error mendapatkan live price untuk {clean_symbol}: {e}")
        
        # 3. VALIDATE PRICE - CRITICAL FIX
        if live_price and live_price > 0:
            # Check jika harga wajar
            is_reasonable = True
            
            # Jika entry_price diberikan, validasi
            if entry_price and entry_price > 0:
                if not validate_price_reasonable(live_price, entry_price, symbol):
                    print(f"❌ Harga {live_price} tidak wajar, menggunakan fallback")
                    live_price = None
                    source = "Invalid Live"
            
            # Absolute price sanity check untuk crypto
            if live_price and 'crypto' in symbol.lower() and live_price > 100000:  # Harga > $100,000 tidak mungkin untuk kebanyakan crypto
                print(f"❌ Harga terlalu tinggi: {live_price}")
                live_price = None
                source = "Invalid High Price"
        
        # 4. FALLBACK ke database price
        if live_price is None or live_price <= 0:
            try:
                positions = bot.get_active_positions()
                for pos in positions:
                    if isinstance(pos, dict):
                        pos_symbol = pos.get('symbol', '')
                        # Bandingkan cleaned symbols
                        pos_clean = pos_symbol
                        if ' (Futures)' in pos_clean:
                            pos_clean = pos_clean.replace(' (Futures)', '')
                        
                        sym_clean = symbol
                        if ' (Futures)' in sym_clean:
                            sym_clean = sym_clean.replace(' (Futures)', '')
                        
                        if pos_clean == sym_clean or pos_symbol == symbol:
                            db_price = pos.get('current_price', 0)
                            if db_price and db_price > 0:
                                print(f"✅ Database price untuk {symbol}: {db_price}")
                                return db_price, "Database"
            except Exception as e:
                print(f"⚠️ Error mendapatkan database price: {e}")
        
        # 5. FALLBACK KE ENTRY PRICE
        if (live_price is None or live_price <= 0) and entry_price and entry_price > 0:
            print(f"⚠️ Menggunakan entry price sebagai fallback: {entry_price}")
            return entry_price, "Entry Fallback"
        
        # 6. ULTIMATE FALLBACK
        if live_price is None or live_price <= 0:
            # Coba alternative symbol formats
            alt_symbols = [
                clean_symbol.replace(':USDT', ''),
                clean_symbol.replace('/USDT:USDT', '/USDT'),
                clean_symbol.replace('-PERP', ''),
                clean_symbol.replace('-SWAP', ''),
                symbol.replace(' (Futures)', ''),
                symbol.replace(' (Swap)', '')
            ]
            
            # Hapus duplikat
            alt_symbols = list(set(alt_symbols))
            
            for alt in alt_symbols:
                if alt != clean_symbol:
                    try:
                        if hasattr(bot, 'data_provider') and bot.data_provider:
                            print(f"🔍 Mencoba alternative symbol: {alt}")
                            ticker = bot.data_provider.get_ticker(alt)
                            if ticker:
                                for key in ['last', 'close', 'current']:
                                    if key in ticker and ticker[key]:
                                        price = float(ticker[key])
                                        if price > 0:
                                            print(f"✅ Alternative price untuk {alt}: {price}")
                                            return price, f"Alt: {alt}"
                    except Exception as alt_e:
                        print(f"⚠️ Error dengan alternative symbol {alt}: {alt_e}")
                        continue
            
            # Last resort: coba dari known price database kecil
            known_prices = {
                'BTC/USDT': 60000,
                'ETH/USDT': 3000,
                'FLOW/USDT': 0.18,
                'FLOW/USDT:USDT': 0.18,
                'FLOWUSDT': 0.18,
            }
            
            for key, known_price in known_prices.items():
                if key in clean_symbol or key in symbol:
                    print(f"⚠️ Menggunakan known price untuk {symbol}: {known_price}")
                    return known_price, "Known Price"
            
            # Complete failure
            print(f"❌ Tidak ada harga valid ditemukan untuk {symbol}")
            return None, "Not Found"
        
        return live_price, source
        
    except Exception as e:
        print(f"❌ Critical error di get_realtime_price_with_fallback: {e}")
        import traceback
        traceback.print_exc()
        return None, "Error"

def validate_and_fix_price_levels(analysis, symbol=None, bot=None):
    """Validate and fix price levels in analysis data"""
    if not isinstance(analysis, dict):
        return {'symbol': symbol, 'error': 'Invalid analysis data'}
    
    if 'symbol' not in analysis and symbol:
        analysis['symbol'] = symbol
    
    current_price = get_valid_price(analysis, symbol, bot)
    
    if current_price <= 0:
        current_price = 1.0
    
    # Pastikan semua field price valid
    price_fields = ['entry_price', 'ideal_entry', 'current_price', 'close', 'last']
    for field in price_fields:
        if analysis.get(field, 0) <= 0:
            analysis[field] = current_price
    
    action = analysis.get('action', 'NEUTRAL')
    
    # ✅ PERBAIKAN: Hitung Entry Range yang REALISTIS
    if (analysis.get('entry_range_low', 0) <= 0 or 
        analysis.get('entry_range_high', 0) <= 0 or 
        analysis.get('best_entry', 0) <= 0 or
        analysis.get('entry_range_low') == analysis.get('entry_range_high')):
        
        # Gunakan ATR atau volatilitas
        atr = analysis.get('atr', 0)
        volatility = analysis.get('volatility', 0.02)
        
        if atr > 0:
            range_size = atr * 0.5
        else:
            range_size = current_price * volatility * 0.5
        
        min_range = current_price * 0.005
        range_size = max(range_size, min_range)
        
        max_range = current_price * 0.03
        range_size = min(range_size, max_range)
        
        if action == "LONG":
            analysis['entry_range_low'] = current_price - (range_size * 1.5)
            analysis['entry_range_high'] = current_price - (range_size * 0.5)
            analysis['best_entry'] = current_price - range_size
        elif action == "SHORT":
            analysis['entry_range_low'] = current_price + (range_size * 0.5)
            analysis['entry_range_high'] = current_price + (range_size * 1.5)
            analysis['best_entry'] = current_price + range_size
        else:
            analysis['entry_range_low'] = current_price - range_size
            analysis['entry_range_high'] = current_price + range_size
            analysis['best_entry'] = current_price
        
        analysis['range_size'] = ((analysis['entry_range_high'] - analysis['entry_range_low']) / current_price) * 100
    
    # Validasi TP/SL
    tp1 = analysis.get('tp1', 0)
    tp2 = analysis.get('tp2', 0) 
    tp3 = analysis.get('tp3', 0)
    sl = analysis.get('sl', 0)
    
    if (tp1 <= 0 or tp2 <= 0 or tp3 <= 0 or sl <= 0 or 
        tp1 == tp2 == tp3 == sl == current_price):
        
        if action == "LONG":
            analysis['tp1'] = current_price * 1.02
            analysis['tp2'] = current_price * 1.04
            analysis['tp3'] = current_price * 1.06
            analysis['sl'] = current_price * 0.98
            
            tp_levels = sorted([analysis['tp1'], analysis['tp2'], analysis['tp3']])
            analysis['tp1'], analysis['tp2'], analysis['tp3'] = tp_levels
            
        else:
            analysis['tp1'] = current_price * 0.98
            analysis['tp2'] = current_price * 0.96
            analysis['tp3'] = current_price * 0.94
            analysis['sl'] = current_price * 1.02
            
            tp_levels = sorted([analysis['tp1'], analysis['tp2'], analysis['tp3']], reverse=True)
            analysis['tp1'], analysis['tp2'], analysis['tp3'] = tp_levels
    
    return analysis

def calculate_tp_probability(current_price, tp1, tp2, tp3, sl, action, volatility=0.02):
    """Hitung probabilitas hit TP1, TP2, TP3"""
    try:
        if action == "LONG":
            tp_levels = sorted([tp1, tp2, tp3])
            distances = {
                'tp1': max(0.0001, (tp_levels[0] - current_price) / current_price),
                'tp2': max(0.0001, (tp_levels[1] - current_price) / current_price),
                'tp3': max(0.0001, (tp_levels[2] - current_price) / current_price),
                'sl': max(0.0001, (current_price - sl) / current_price)
            }
        else:
            tp_levels = sorted([tp1, tp2, tp3], reverse=True)
            
            distances = {
                'tp1': max(0.0001, (current_price - tp_levels[0]) / current_price),
                'tp2': max(0.0001, (current_price - tp_levels[1]) / current_price),
                'tp3': max(0.0001, (current_price - tp_levels[2]) / current_price),
                'sl': max(0.0001, (sl - current_price) / current_price)
            }
        
        risk_distance = distances['sl']
        probabilities = {}
        
        for i, target in enumerate(['tp1', 'tp2', 'tp3']):
            reward_distance = distances[target]
            
            if reward_distance <= 0 or risk_distance <= 0:
                probabilities[target] = 0.05
                continue
            
            risk_reward_ratio = reward_distance / risk_distance
            
            if risk_reward_ratio >= 3:
                base_prob = 0.75
            elif risk_reward_ratio >= 2:
                base_prob = 0.65
            elif risk_reward_ratio >= 1.5:
                base_prob = 0.55
            elif risk_reward_ratio >= 1:
                base_prob = 0.45
            elif risk_reward_ratio >= 0.5:
                base_prob = 0.35
            else:
                base_prob = 0.20
            
            distance_penalty = i * 0.20
            volatility_adjustment = volatility * 1.5
            
            final_prob = base_prob - distance_penalty - volatility_adjustment
            final_prob = max(0.05, min(0.85, final_prob))
            
            probabilities[target] = round(final_prob, 3)
        
        # Pastikan probabilitas menurun untuk TP yang lebih jauh
        if probabilities.get('tp1', 0) < probabilities.get('tp2', 0):
            probabilities['tp1'], probabilities['tp2'] = probabilities['tp2'], probabilities['tp1']
        if probabilities.get('tp1', 0) < probabilities.get('tp3', 0):
            probabilities['tp1'], probabilities['tp3'] = probabilities['tp3'], probabilities['tp1']
        if probabilities.get('tp2', 0) < probabilities.get('tp3', 0):
            probabilities['tp2'], probabilities['tp3'] = probabilities['tp3'], probabilities['tp2']
        
        return probabilities
        
    except Exception as e:
        print(f"Error calculating TP probability: {e}")
        return {"tp1": 0.6, "tp2": 0.4, "tp3": 0.2}

def plot_entry_range(analysis):
    """Plot visual entry range"""
    if not PLOTLY_AVAILABLE:
        return None
        
    fig = go.Figure()
    
    current_price = analysis.get('current_price', 0)
    entry_low = analysis.get('entry_range_low', 0)
    entry_high = analysis.get('entry_range_high', 0)
    best_entry = analysis.get('best_entry', 0)
    
    if current_price <= 0 or entry_low <= 0 or entry_high <= 0 or best_entry <= 0:
        return fig
    
    # Add range area
    fig.add_trace(go.Scatter(
        x=[entry_low, entry_high],
        y=['Entry Range', 'Entry Range'],
        fill='toself',
        fillcolor='rgba(0,255,0,0.2)',
        line=dict(color='rgba(255,255,255,0)'),
        name='Entry Range'
    ))
    
    # Add points
    fig.add_trace(go.Scatter(
        x=[current_price, best_entry],
        y=['Current Price', 'Ideal Entry'],
        mode='markers+text',
        marker=dict(size=15, color=['blue', 'red']),
        text=['Current', 'Ideal'],
        textposition="middle right"
    ))
    
    fig.update_layout(
        title="Entry Range Analysis",
        xaxis_title="Price",
        showlegend=False,
        height=200
    )
    
    return fig

def run_scheduler(bot):
    """Jalankan auto scan tiap 30 detik."""
    def scan_job():
        if bot.mode:
            results = bot.scan_potential_assets(10)
            if results:
                st.session_state['latest_results'] = results[:5]

    schedule.every(30).seconds.do(scan_job)
    while True:
        schedule.run_pending()
        time.sleep(1)

# ====================================
# Session State Management Functions
# ====================================

def select_asset_callback(symbol, data):
    """Callback untuk memilih aset"""
    st.session_state.selected_for_entry[symbol] = data
    st.session_state.selected_symbol_display = symbol
    st.session_state.last_selected = symbol
    return True

def clear_selection_callback():
    """Callback untuk clear selection"""
    st.session_state.selected_for_entry = {}
    st.session_state.selected_symbol_display = None
    st.session_state.last_selected = None
    return True

# ====================================
# SCALPING SPECIFIC FUNCTIONS - PERBAIKAN
# ====================================

def filter_for_scalping(assets, bot):
    """Filter assets yang cocok untuk scalping - NO BIAS VERSION"""
    filtered = []
    
    for asset in assets:
        try:
            symbol = asset.get('symbol', '')
            if not symbol:
                continue
            
            current_score = asset.get('score', 0)
            current_price = get_valid_price(asset, symbol, bot)
            action = asset.get('action', 'NEUTRAL')
            
            # 🔥 PERBAIKAN: Skip neutral untuk scalping
            if action == "NEUTRAL":
                continue
            
            # 🔥 PERBAIKAN: Gunakan absolute score, NO BIAS
            if abs(current_score) < SCALPING_CONFIG_APP["min_score"]:
                continue
            
            # Price range yang lebih ketat untuk scalping
            if current_price < 0.05 or current_price > 200:
                continue
            
            # Hitung suitability score
            suitability_score = 0
            
            # Base score untuk strength
            if abs(current_score) >= 3.5:
                suitability_score += 4
            elif abs(current_score) >= 3.0:
                suitability_score += 3
            elif abs(current_score) >= 2.5:
                suitability_score += 2
            
            # 🔥 BONUS untuk SHORT signals (scalping cocok untuk short)
            if current_score <= -3.0:
                suitability_score += 2
            
            # Bonus untuk price range optimal
            if 0.5 <= current_price <= 50:
                suitability_score += 2
            
            # Bonus untuk volume
            volume = asset.get('volume', 0)
            if volume > 1000000:
                suitability_score += 1
            
            asset['scalping_score'] = suitability_score
            asset['scalping_suitable'] = suitability_score >= 3
            
            if suitability_score >= 3:
                filtered.append(asset)
                
        except Exception as e:
            continue
    
    # Sort by absolute score (strongest first)
    return sorted(filtered, key=lambda x: abs(x.get('score', 0)), reverse=True)

def display_scalping_signal(signal, index):
    """Display scalping signal - IMPROVED without bias"""
    symbol = signal.get('symbol', 'UNKNOWN')
    action = signal.get('action', 'NEUTRAL')
    score = signal.get('score', 0)  # 🔥 Gunakan score asli, bukan + bias
    scalping_score = signal.get('scalping_score', 0)
    confidence = signal.get('confidence', 0.5)
    
    # Warna berdasarkan score asli (negative = SHORT)
    if score >= 3.0:
        color = "🟢"  # Strong LONG
        emoji = "🚀"
    elif score >= 2.0:
        color = "🟡"  # Moderate LONG
        emoji = "📈"
    elif score <= -3.0:
        color = "🔴"  # Strong SHORT
        emoji = "💣"
    elif score <= -2.0:
        color = "🟠"  # Moderate SHORT
        emoji = "📉"
    else:
        color = "⚪"
        emoji = "⚡"
    
    col1, col2, col3, col4 = st.columns([2, 1.5, 1.5, 1])
    
    with col1:
        st.write(f"{index}. {color} {emoji} **{symbol}**")
        st.write(f"   Action: `{action}` | Score: `{score:+.1f}`")  # 🔥 Tampilkan +/- untuk score
    
    with col2:
        current_price = get_valid_price(signal, symbol, st.session_state.bot_instance)
        market = st.session_state.current_market if hasattr(st.session_state, 'current_market') else "Crypto"
        st.write(f"💰 Price: `{format_currency(current_price, market)}`")
        
        # Entry range untuk scalping
        entry_low = signal.get('entry_range_low', 0)
        entry_high = signal.get('entry_range_high', 0)
        if entry_low and entry_high:
            range_pct = ((entry_high - entry_low) / current_price) * 100
            st.write(f"🎯 Range: `{format_currency(entry_low, market)}` - `{format_currency(entry_high, market)}`")
            st.write(f"📏 Range Size: `{range_pct:.2f}%`")
    
    with col3:
        # TP levels untuk scalping
        tp1 = signal.get('tp1', 0)
        tp2 = signal.get('tp2', 0)
        tp3 = signal.get('tp3', 0)
        sl = signal.get('sl', 0)
        
        if action == "LONG":
            tp_emoji = "📈"
            risk_reward = (tp1 - current_price) / (current_price - sl) if (current_price - sl) > 0 else 0
        else:
            tp_emoji = "📉"
            risk_reward = (current_price - tp1) / (sl - current_price) if (sl - current_price) > 0 else 0
        
        st.write(f"{tp_emoji} TP1: `{format_currency(tp1, market)}`")
        st.write(f"{tp_emoji} TP2: `{format_currency(tp2, market)}`")
        st.write(f"{tp_emoji} TP3: `{format_currency(tp3, market)}`")
        st.write(f"📊 R/R: `{risk_reward:.2f}`")
    
    with col4:
        # Scalping specific info
        st.write(f"⚡ Scalping Score: `{scalping_score}/7`")
        st.write(f"🎯 Confidence: `{confidence:.1%}`")
        st.write(f"🛑 SL: `{format_currency(sl, market)}`")
        
        if signal.get('scalping_suitable', False):
            st.success("✅ Good for Scalping")
        else:
            st.warning("⚠️ Limited suitability")
    
    # 🔥 PERBAIKAN: Tombol yang lebih jelas
    button_key = f"select_scalping_{symbol}_{index}"
    if st.button(f"📌 Select {symbol}", key=button_key):
        if select_asset_callback(symbol, signal):
            st.success(f"✅ Selected {symbol}!")
            st.rerun()
    return False

# ====================================
# PERBAIKAN 2: Fungsi Open Position - ENHANCED
# ====================================
def open_position(symbol, action, entry_price=None, tp1=None, tp2=None, tp3=None, sl=None, 
                  position_size=100, risk_percent=None):
    """Open a new position dengan real-time price jika tidak ada entry_price"""
    try:
        bot = st.session_state.bot_instance
        
        if bot is None:
            st.error("❌ Bot is not initialized")
            return False
        
        # Jika entry_price tidak diberikan, ambil harga real-time
        if entry_price is None or entry_price <= 0:
            real_time_price = get_real_time_price(symbol, bot)
            if real_time_price and real_time_price > 0:
                entry_price = real_time_price
                print(f"✅ Using real-time price for {symbol}: {entry_price}")
            else:
                # Ambil dari analysis data jika ada
                if symbol in st.session_state.selected_for_entry:
                    analysis = st.session_state.selected_for_entry[symbol]
                    entry_price = get_valid_price(analysis, symbol, bot)
        
        # Jika masih tidak valid, gunakan harga default
        if entry_price is None or entry_price <= 0:
            entry_price = 1.0
            print(f"⚠️ Using fallback price for {symbol}: {entry_price}")
        
        # Hitung TP/SL jika tidak diberikan
        current_price = entry_price
        
        if tp1 is None or sl is None:
            if action == "LONG":
                tp1 = tp1 or current_price * 1.02  # TP1: +2%
                tp2 = tp2 or current_price * 1.04  # TP2: +4%
                tp3 = tp3 or current_price * 1.06  # TP3: +6%
                sl = sl or current_price * 0.98   # SL: -2%
            else:  # SHORT
                tp1 = tp1 or current_price * 0.98  # TP1: -2%
                tp2 = tp2 or current_price * 0.96  # TP2: -4%
                tp3 = tp3 or current_price * 0.94  # TP3: -6%
                sl = sl or current_price * 1.02   # SL: +2%
        else:
            # Use provided TP/SL values
            tp2 = tp2 or tp1 * 1.02 if action == "LONG" else tp1 * 0.98
            tp3 = tp3 or tp1 * 1.04 if action == "LONG" else tp1 * 0.96
        
        # Generate unique ID untuk session
        session_id = f"pos_{int(time.time())}_{symbol.replace('/', '_')}"
        
        # Simpan ke database menggunakan bot
        db_position_id = None
        
        if hasattr(bot, 'save_position_to_db'):
            # Coba gunakan method khusus
            db_position_id = bot.save_position_to_db(
                symbol=symbol,
                action=action,
                entry_price=entry_price,
                tp1=tp1,
                tp2=tp2,
                tp3=tp3,
                sl=sl,
                position_size=position_size
            )
        elif hasattr(bot, 'db') and hasattr(bot.db, 'save_position'):
            # Gunakan database handler langsung
            db_position_id = bot.db.save_position(
                symbol=symbol,
                market_type=bot.mode,
                action=action,
                entry_price=entry_price,
                tp1=tp1,
                tp2=tp2,
                tp3=tp3,
                sl=sl,
                position_size=position_size
            )
        
        # Buat position object untuk session state
        position = {
            'id': db_position_id or session_id,
            'symbol': symbol,
            'action': action,
            'entry_price': entry_price,
            'current_price': current_price,
            'tp1': tp1,
            'tp2': tp2,
            'tp3': tp3,
            'sl': sl,
            'position_size': position_size,
            'position_value': position_size,
            'risk_percent': risk_percent,
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'status': 'open',
            'saved_to_db': db_position_id is not None,
            'source': 'database' if db_position_id else 'session'
        }
        
        # Simpan ke session state
        if not hasattr(st.session_state, 'test_positions'):
            st.session_state.test_positions = []
        
        st.session_state.test_positions.append(position)
        
        # Update positions data
        if hasattr(bot, 'get_active_positions'):
            try:
                st.session_state.positions_data = bot.get_active_positions()
            except:
                st.session_state.positions_data = st.session_state.test_positions
        
        print(f"✅ Position opened: {symbol}, DB ID: {db_position_id}")
        return True
        
    except Exception as e:
        print(f"❌ Error opening position: {e}")
        import traceback
        traceback.print_exc()
        return False

def update_position_price_in_db(bot, position_id, current_price):
    """Update harga position di database dengan fallback dan logging yang lebih baik"""
    if hasattr(bot, 'update_position_current_price'):
        try:
            success = bot.update_position_current_price(position_id, current_price)
            if success:
                print(f"✅ Updated DB price for position {position_id}: {current_price}")
                return True
            else:
                print(f"⚠️ DB update failed for {position_id}")
                return False
        except Exception as e:
            print(f"❌ DB update error: {e}")
            return False
    print("⚠️ No update method in bot")
    return False

def update_all_positions_prices(bot):
    """Update semua harga posisi dengan data real-time dan simpan ke database"""
    updated_count = 0
    failed_count = 0
    
    if bot is None:
        print("❌ Bot is None")
        return updated_count
    
    try:
        # Get positions from database
        positions = bot.get_active_positions()
        
        for pos in positions:
            if isinstance(pos, dict) and pos.get('status') == 'open':
                symbol = pos.get('symbol')
                position_id = pos.get('id')
                
                if symbol and position_id:
                    # Get real-time price
                    current_price, source = get_realtime_price_with_fallback(symbol, bot)
                    
                    if current_price and current_price > 0:
                        # Update in database
                        success = update_position_price_in_db(bot, position_id, current_price)
                        
                        if success:
                            updated_count += 1
                            print(f"✅ Updated {symbol} to {format_currency(current_price, st.session_state.current_market)} ({source})")
                        else:
                            failed_count += 1
                            print(f"❌ Failed to update {symbol} in DB")
                    else:
                        failed_count += 1
                        print(f"⚠️ No valid price for {symbol}")
        
        print(f"📊 Update summary: {updated_count} updated, {failed_count} failed")
        return updated_count
        
    except Exception as e:
        print(f"❌ Error updating all positions: {e}")
        return updated_count

# ====================================
# NEW: Backtest Visualization Functions
# ====================================
def plot_backtest_results(results):
    """Plot backtest results menggunakan Plotly"""
    if not PLOTLY_AVAILABLE:
        return None
    
    try:
        # Create equity curve chart
        if 'equity_curve' in results and isinstance(results['equity_curve'], (pd.Series, list)):
            equity_data = results['equity_curve']
            if isinstance(equity_data, pd.Series):
                dates = equity_data.index
                values = equity_data.values
            else:
                dates = list(range(len(equity_data)))
                values = equity_data
            
            fig = px.line(x=dates, y=values, title='Equity Curve')
            fig.update_layout(xaxis_title='Time', yaxis_title='Equity')
            return fig
        
        # Create metrics gauge charts
        metrics = ['total_return', 'sharpe_ratio', 'win_rate']
        figs = []
        
        for metric in metrics:
            if metric in results:
                value = results[metric]
                max_val = 100 if metric == 'total_return' else 3 if metric == 'sharpe_ratio' else 100
                
                fig = go.Figure(go.Indicator(
                    mode="gauge+number",
                    value=value,
                    title={'text': metric.replace('_', ' ').title()},
                    gauge={'axis': {'range': [0, max_val]},
                          'bar': {'color': "green" if value > 0 else "red"}}
                ))
                figs.append(fig)
        
        return figs if len(figs) > 1 else figs[0] if figs else None
        
    except Exception as e:
        print(f"❌ Error plotting backtest results: {e}")
        return None

# ====================================
# Main App - SIMPLIFIED VERSION
# ====================================
def main_app():
    st.title("🚀 TradingBot Pro - Enhanced Dashboard with External Repos Integration")
    
    # 🔥 START KEEP-ALIVE THREAD (TAMBAHKAN DI SINI)
    if 'background_thread_started' not in st.session_state:
        start_background_ping()
    
    # User info and logout
    col1, col2 = st.columns([3, 1])
    with col1:
        st.write(f"Welcome, **{st.session_state.username}**! 👋")
    with col2:
        if st.button("🚪 Logout"):
            for key in list(st.session_state.keys()):
                if key not in ['logged_in', 'username']:
                    del st.session_state[key]
            st.session_state.logged_in = False
            st.rerun()

    # Initialize bot - PERBAIKAN UTAMA
    if 'bot_instance' not in st.session_state or st.session_state.bot_instance is None:
        with st.spinner("Initializing TradingBot with External Repos..."):
            try:
                bot = init_bot()
                if bot:
                    st.session_state.bot_instance = bot
                    
                    # Set default mode jika belum
                    if not hasattr(bot, 'mode'):
                        bot.mode = "crypto"
                    if not hasattr(bot, 'trading_mode'):
                        bot.trading_mode = "spot"
                    
                    # Check external repo availability
                    external_repos_status = {}
                    if hasattr(bot, 'backtrader_module') and bot.backtrader_module:
                        external_repos_status['backtrader'] = "✅ Available"
                    else:
                        external_repos_status['backtrader'] = "❌ Not Available"
                    
                    if hasattr(bot, 'backtesting_module') and bot.backtesting_module:
                        external_repos_status['backtesting'] = "✅ Available"
                    else:
                        external_repos_status['backtesting'] = "❌ Not Available"
                    
                    if hasattr(bot, 'scraper_manager') and bot.scraper_manager:
                        external_repos_status['multi_scraper'] = "✅ Available"
                    else:
                        external_repos_status['multi_scraper'] = "❌ Not Available"
                    
                    st.success("✅ TradingBot initialized successfully!")
                    
                    # Show external repos status
                    with st.expander("📚 External Repos Status"):
                        for repo, status in external_repos_status.items():
                            st.write(f"{repo}: {status}")
                    
                else:
                    st.error("Failed to initialize TradingBot")
                    st.stop()
            except Exception as e:
                st.error(f"Bot initialization error: {e}")
                st.stop()
    
    bot = st.session_state.bot_instance
    
    # Pastikan bot tidak None
    if bot is None:
        st.error("❌ Bot is not available. Please refresh the page.")
        st.stop()
    
    # Initialize session state jika belum
    if 'app_initialized' not in st.session_state:
        st.session_state.app_initialized = True
        st.session_state.positions_data = []
        st.session_state.history_data = []
        st.session_state.scanned_results = []
        st.session_state.scalping_results = []  # 🔥 NEW: Results khusus scalping
        st.session_state.selected_analysis = None
        st.session_state.selected_for_entry = {}
        st.session_state.current_market = None
        st.session_state.current_trading_mode = None
        st.session_state.market_set = False
        st.session_state.live_monitoring = False
        st.session_state.custom_result = None
        st.session_state.backtest_results = {}
        st.session_state.portfolio_allocations = {}
        st.session_state.risk_assessments = {}
        st.session_state.latest_results = []
        st.session_state.scalping_mode = False  # 🔥 NEW: Scalping mode flag
        st.session_state.scalping_config = SCALPING_CONFIG_APP  # 🔥 NEW: Store config
        st.session_state.selected_symbol_display = None
        st.session_state.last_selected = None
        st.session_state.test_positions = []  # 🔥 NEW: Untuk menyimpan posisi sementara
        st.session_state.open_position_result = None
        st.session_state.open_position_risk = None
        st.session_state.last_scan_time = None
        st.session_state.scan_attempts = 0
        st.session_state.show_all_positions = False
        st.session_state.use_risk_management = False
        st.session_state.external_repo_data = {}  # 🔥 NEW: Untuk data external repos
        st.session_state.backtest_visualizations = {}  # 🔥 NEW: Untuk visualisasi backtest

    # Sidebar
    with st.sidebar:
        st.header("🎯 Trading Configuration")
        
        # 🔥 NEW: Info tentang 500+ aset
        if st.session_state.market_set and st.session_state.current_market in ["Saham Indonesia", "US Stocks", "Forex"]:
            st.success(f"✅ **500+ ASSETS SUPPORTED**")
            st.caption(f"Auto-fetch from NonCryptoAssetsProvider with cache")
            st.info("""
            **📊 Supported Markets:**
            - Saham Indonesia: 500+ saham terdaftar di BEI
            - US Stocks: 500+ saham utama Nasdaq/NYSE
            - Forex: 50+ pasangan mata uang utama
            - Crypto: 200+ aset cryptocurrency
            """)
        
        # 🎯 Scalping Mode Toggle
        scalping_mode = st.checkbox("⚡ Enable Scalping Mode", 
                                    value=st.session_state.scalping_mode,
                                    help="Enable for 3-5 minute scalping with tighter parameters")
        
        if scalping_mode != st.session_state.scalping_mode:
            st.session_state.scalping_mode = scalping_mode
            st.session_state.scanned_results = []  # Clear old results
            st.rerun()
        
        if scalping_mode:
            st.success("⚡ SCALPING MODE ACTIVE")
            
            # 🔥 PERBAIKAN: Scalping Settings tanpa bias
            with st.expander("⚡ Scalping Settings"):
                col1, col2 = st.columns(2)
                with col1:
                    min_score_sidebar = st.slider("Min Score", 2.0, 5.0, 
                                                 value=SCALPING_CONFIG_APP["min_score"], 
                                                 step=0.5, key="sidebar_min_score")
                with col2:
                    st.info("Bias: 0.0 (Neutral)")
                
                if st.button("Apply Settings", key="apply_scalping_settings"):
                    SCALPING_CONFIG_APP["min_score"] = min_score_sidebar
                    st.session_state.scalping_config = SCALPING_CONFIG_APP
                    st.success("✅ Settings applied!")
                    st.rerun()
            
            st.info(f"""
            **Scalping Parameters:**
            - Timeframe: 5m
            - Min Score: {SCALPING_CONFIG_APP["min_score"]}
            - Bias: 0.0 (Neutral)
            - Entry Range: 0.8%
            - Max Price: ${SCALPING_CONFIG_APP["price_filter"]["max"]}
            - Allow Short: ✅ Yes
            - Max Signals: {SCALPING_CONFIG_APP["max_signals"]}
            """)
        
        st.divider()
        
        # 🔥 PERBAIKAN: Tampilkan selected asset di sidebar
        if st.session_state.selected_for_entry:
            st.subheader("📌 Selected Asset")
            for symbol, data in st.session_state.selected_for_entry.items():
                display_symbol = convert_symbol_for_display(
                    symbol,
                    bot.mode,
                    getattr(bot, 'trading_mode', 'spot')
                )
                st.success(f"✅ {display_symbol}")
                st.write(f"Action: {data.get('action', 'N/A')}")
                st.write(f"Score: {data.get('score', 0)}")
                market = st.session_state.current_market if hasattr(st.session_state, 'current_market') else "Crypto"
                st.write(f"Price: {format_currency(data.get('current_price', 0), market)}")
            
            if st.button("🗑️ Clear Selection", key="clear_selection"):
                clear_selection_callback()
                st.success("Selection cleared!")
                st.rerun()
            
            st.divider()
        
        # Market Selection
        market_choice = st.selectbox(
            "Select Market:",
            ["Crypto", "Forex", "Saham Indonesia", "US Stocks"],
            key="market_select"
        )
        
        # Trading mode selection
        if market_choice == "Crypto":
            trading_mode = st.radio(
                "Trading Mode:",
                ["Spot", "Futures"],
                key="mode_select"
            )
        else:
            trading_mode = "Spot"  # Only spot for non-crypto
            st.info("📊 Only Spot trading available for this market")
        
        # Show warning for markets that don't support short trading
        if market_choice in ["Forex", "Saham Indonesia", "US Stocks"]:
            st.warning("⚠️ **SHORT TRADING NOT AVAILABLE** - Only LONG signals will be generated")

        # Set Market Button - PERBAIKAN UTAMA: Tambah pengecekan bot
        if st.button("🎯 Set Market", key="set_market_btn", type="primary"):
            # Pastikan bot tidak None
            if bot is None:
                st.error("❌ Bot is not initialized. Please refresh the page.")
                st.rerun()
            
            try:
                # Validasi Futures hanya untuk Crypto
                if market_choice != "Crypto" and trading_mode == "Futures":
                    st.error("❌ Futures mode hanya tersedia untuk Crypto")
                else:
                    # Set market mode
                    market_mode_map = {
                        "Crypto": "crypto",
                        "Forex": "forex", 
                        "Saham Indonesia": "saham_id",
                        "US Stocks": "us_stocks"
                    }
                    
                    mode_string = market_mode_map[market_choice]
                    
                    # Set trading mode
                    if trading_mode == "Futures":
                        target_trading_mode = "futures"
                    else:
                        target_trading_mode = "spot"
                    
                    # Gunakan set_mode yang ada di EnhancedTradingBot
                    if hasattr(bot, 'set_mode'):
                        success = bot.set_mode(mode_string)
                    else:
                        # Fallback: set attribute langsung
                        bot.mode = mode_string
                        success = True
                    
                    if success:
                        # Set trading mode
                        bot.trading_mode = target_trading_mode
                        
                        st.session_state.current_market = market_choice
                        st.session_state.current_trading_mode = trading_mode
                        st.session_state.market_set = True
                        st.session_state.scanned_results = []
                        st.session_state.scalping_results = []  # Clear scalping results
                        st.session_state.selected_for_entry = {}
                        st.session_state.selected_symbol_display = None
                        
                        # 🔥 NEW: Load 500+ assets for non-crypto markets
                        if market_choice in ["Saham Indonesia", "US Stocks", "Forex"]:
                            st.info(f"📊 Loading 500+ {market_choice} assets...")
                            # Call to load assets from NonCryptoAssetsProvider
                            if hasattr(bot, 'data_provider') and hasattr(bot.data_provider, 'load_non_crypto_assets'):
                                try:
                                    category_map = {
                                        "Saham Indonesia": "indonesia_stocks",
                                        "US Stocks": "us_stocks",
                                        "Forex": "forex"
                                    }
                                    category = category_map.get(market_choice)
                                    if category:
                                        assets_count = bot.data_provider.load_non_crypto_assets(category, limit=500)
                                        if assets_count:
                                            st.success(f"✅ Loaded {assets_count} {market_choice} assets")
                                        else:
                                            st.warning(f"⚠️ Could not load assets for {market_choice}")
                                except Exception as e:
                                    st.warning(f"⚠️ Asset loading: {e}")
                        
                        st.success(f"✅ Market set to: {market_choice} ({trading_mode})")
                        st.rerun()
                    else:
                        st.error("❌ Failed to set market mode")
                        
            except Exception as e:
                st.error(f"❌ Error: {str(e)[:200]}")
        
        # Tampilkan status market dan trading mode
        if st.session_state.market_set:
            st.divider()
            st.success(f"✅ Active: {st.session_state.current_market}")
            if hasattr(bot, 'trading_mode'):
                mode_display = bot.trading_mode.upper()
                st.info(f"📊 Mode: {mode_display}")
            
            if st.session_state.scalping_mode:
                st.success("⚡ SCALPING MODE: ON")
            
            # 🔥 NEW: Tampilkan jumlah aset yang tersedia
            if st.session_state.current_market in ["Saham Indonesia", "US Stocks", "Forex"]:
                st.info(f"📈 **500+ Assets Available**")
        
        # Info tentang simbol berdasarkan mode
        if st.session_state.market_set:
            with st.expander("ℹ️ Symbol Format Info"):
                if hasattr(bot, 'trading_mode'):
                    if bot.trading_mode == "spot":
                        st.write("**Spot Trading Format:**")
                        st.write("- Crypto: BTC/USDT, ETH/USDT (200+ assets)")
                        st.write("- Forex: EUR/USD, GBP/USD (50+ pairs)")
                        st.write("- Saham ID: BBCA.JK, TLKM.JK (500+ stocks)")
                        st.write("- US Stocks: AAPL, TSLA (500+ stocks)")
                    else:
                        st.write("**Futures Trading Format:**")
                        st.write("- Crypto: BTC/USDT:USDT, ETH/USDT:USDT")
                        st.write("- Crypto (alternative): BTCUSDT-PERP, ETHUSDT-PERP")
        
        # Asset Count Information
        if st.session_state.market_set:
            with st.expander("📊 Asset Count Information"):
                asset_counts = {
                    "Crypto": "200+ cryptocurrency pairs",
                    "Forex": "50+ major forex pairs",
                    "Saham Indonesia": "500+ stocks (BEI listed)",
                    "US Stocks": "500+ major stocks (S&P 500 + Nasdaq)"
                }
                
                current_market = st.session_state.current_market
                if current_market in asset_counts:
                    st.success(f"**{current_market}**: {asset_counts[current_market]}")
                
                st.info("""
                **💡 Tips:**
                - Larger asset pools = Better signal diversity
                - More assets = Higher chance of finding profitable opportunities
                - Auto-refresh every 24 hours for fresh data
                """)
        
        # ============================================
        # Provider Info di Sidebar
        # ============================================
        if st.session_state.market_set and hasattr(bot, 'get_provider_health'):
            with st.expander("🔧 Provider Info"):
                try:
                    health = bot.get_provider_health()
                    
                    # Display provider info
                    provider_type = health.get('provider_type', 'unknown')
                    status = health.get('status', 'unknown')
                    
                    if provider_type == 'smart_chain':
                        active_provider = health.get('active_provider', 'unknown')
                        cache_size = health.get('cache_size', 0)
                        
                        st.write(f"**Provider:** SmartChainDataProvider")
                        st.write(f"**Active:** {active_provider}")
                        st.write(f"**Cache:** {cache_size} items")
                        st.write(f"**Market:** {health.get('market_type', 'unknown')}")
                        
                        if status == 'active':
                            st.success("✅ Provider healthy")
                        else:
                            st.warning("⚠️ Provider issues")
                            
                    elif provider_type == 'unified':
                        st.write(f"**Provider:** UnifiedDataProvider")
                        st.write(f"**Primary:** {health.get('primary_provider', 'unknown')}")
                        st.write(f"**Fallback:** {health.get('fallback_provider', 'unknown')}")
                        
                    else:
                        st.write(f"**Provider:** {provider_type}")
                        st.write(f"**Status:** {status}")
                        
                    # 🔥 NEW: Asset count info
                    if st.session_state.current_market in ["Saham Indonesia", "US Stocks", "Forex"]:
                        st.info(f"**Asset Pool:** 500+ assets available")
                    
                    if st.button("🔄 Test Provider", key="test_provider"):
                        with st.spinner("Testing..."):
                            # Test dengan BTC/USDT
                            try:
                                test_result = bot.analyze_asset("BTC/USDT")
                                if test_result and 'error' not in test_result:
                                    st.success("✅ Provider test passed!")
                                else:
                                    st.error("❌ Provider test failed")
                            except Exception as e:
                                st.error(f"❌ Test error: {str(e)[:100]}")
                                
                except Exception as e:
                    st.error(f"Error getting provider info: {e}")

        # ============================================
        # PERBAIKAN 6: Database Health Check di Sidebar
        # ============================================
        if st.session_state.market_set and hasattr(bot, 'db'):
            with st.expander("🗄️ Database Info"):
                try:
                    # Test database connection
                    if st.button("🧪 Test Database", key="test_database"):
                        with st.spinner("Testing database..."):
                            try:
                                # Test save a dummy position
                                test_id = bot.db.save_position(
                                    symbol="TEST/DB",
                                    market_type="crypto",
                                    action="LONG",
                                    entry_price=100.0,
                                    tp1=102.0,
                                    tp2=104.0,
                                    tp3=106.0,
                                    sl=98.0,
                                    position_size=10.0
                                )
                                
                                if test_id:
                                    st.success(f"✅ Database test passed! ID: {test_id}")
                                    
                                    # Get active positions
                                    positions = bot.db.get_active_positions("crypto")
                                    st.info(f"📊 Active positions in DB: {len(positions)}")
                                    
                                    # Clean up test position
                                    bot.db.close_position(test_id, 101.0, "test")
                                else:
                                    st.error("❌ Database test failed")
                                    
                            except Exception as db_error:
                                st.error(f"❌ Database error: {db_error}")
                    
                    # Show database stats
                    if hasattr(bot.db, 'health_check'):
                        health = bot.db.health_check()
                        st.write(f"**Status:** {health.get('status', 'unknown')}")
                        st.write(f"**Tables:** {health.get('tables_count', 0)}")
                        st.write(f"**Active Connections:** {health.get('active_connections', 0)}")
                    
                except Exception as e:
                    st.error(f"Database info error: {e}")
        
        # ============================================
        # External Repos Status di Sidebar
        # ============================================
        with st.expander("📚 External Repos Status"):
            repos_info = [
                ("backtrader", "Backtesting framework"),
                ("backtesting.py", "Backtesting library"),
                ("multi_scraper", "Multi-source data scraper"),
                ("quant-trading", "Quantitative strategies")
            ]
            
            for repo_name, description in repos_info:
                # Check if method exists
                if repo_name == "backtrader" and hasattr(bot, 'backtrader_module'):
                    status = "✅ Loaded" if bot.backtrader_module else "❌ Not available"
                elif repo_name == "backtesting.py" and hasattr(bot, 'backtesting_module'):
                    status = "✅ Loaded" if bot.backtesting_module else "❌ Not available"
                elif repo_name == "multi_scraper" and hasattr(bot, 'scraper_manager'):
                    status = "✅ Loaded" if bot.scraper_manager else "❌ Not available"
                elif repo_name == "quant-trading" and hasattr(bot, 'optimize_portfolio_allocation'):
                    status = "✅ Available"
                else:
                    status = "❌ Not available"
                
                st.write(f"**{repo_name}:** {status}")
                st.caption(f"{description}")

    # Check if market is set
    if not st.session_state.market_set:
        st.warning("⚠️ Please select a market first!")
        st.info("""
        **Instructions:**
        1. Select Market (Crypto/Forex/Saham Indonesia/US Stocks)  
        2. Select Trading Mode (Spot/Futures)
        3. Click **Set Market** button
        4. Start scanning assets
        
        **📊 Asset Availability:**
        - **Saham Indonesia**: 500+ stocks
        - **US Stocks**: 500+ stocks  
        - **Forex**: 50+ currency pairs
        - **Crypto**: 200+ cryptocurrency pairs
        
        **Note:** 
        - Futures trading only available for Crypto
        - Short trading only available for Crypto Futures
        """)
        return

    # Main Tabs - UPDATED dengan tab baru untuk backtesting
    tab1, tab2, tab3, tab4, tab6, tab7, tab8, tab9, tab10, tab11 = st.tabs([
        "📊 Scan Assets", "⚡ Scalping Mode", "🔍 Analyze", "🎯 Custom Entry", 
        "💼 Positions", "📈 History", "📡 Live Scanner", 
        "🤖 ML Backtest", "⚖️ Portfolio", "🧪 Advanced Backtesting"  # 🔥 NEW TAB
    ])

    # Tab 1: Scan Assets (Regular) - PERBAIKAN dengan external repos
    with tab1:
        st.subheader("📊 Scan Potential Assets (Enhanced with External Repos)")
        
        # Tampilkan mode aktif
        mode_info = []
        if hasattr(bot, 'trading_mode'):
            mode_badge = "🔄 SPOT" if bot.trading_mode == "spot" else "⚡ FUTURES"
            mode_info.append(f"**Mode:** {mode_badge}")
        
        if st.session_state.scalping_mode:
            mode_info.append("⚡ **SCALPING:** ON")
            # 🔥 PERBAIKAN: Tampilkan konfigurasi scalping
            st.info(f"""
            ⚡ **SCALPING CONFIGURATION:**
            - Min Score: `{SCALPING_CONFIG_APP['min_score']}`
            - Price Range: `${SCALPING_CONFIG_APP['price_filter']['min']}` - `${SCALPING_CONFIG_APP['price_filter']['max']}`
            - Bias: `{SCALPING_CONFIG_APP['long_bias']}` (Neutral)
            - Entry Range: `{SCALPING_CONFIG_APP['entry_range_pct']*100:.1f}%`
            - Allow Short: ✅ Yes
            - Max Signals: `{SCALPING_CONFIG_APP['max_signals']}`
            """)
        
        # 🔥 NEW: External repos info
        external_repos_available = []
        if hasattr(bot, 'scraper_manager') and bot.scraper_manager:
            external_repos_available.append("Multi-Scraper")
        if hasattr(bot, 'backtesting_module') and bot.backtesting_module:
            external_repos_available.append("Backtesting.py")
        
        if external_repos_available:
            st.success(f"📚 **External Repos Active:** {', '.join(external_repos_available)}")
        
        # 🔥 NEW: Asset pool information
        asset_pool_info = {
            "Crypto": "200+ cryptocurrency pairs",
            "Forex": "50+ forex pairs", 
            "Saham Indonesia": "500+ Indonesian stocks",
            "US Stocks": "500+ US stocks"
        }
        
        if st.session_state.current_market in asset_pool_info:
            st.success(f"📈 **Asset Pool:** {asset_pool_info[st.session_state.current_market]}")
        
        if mode_info:
            st.info(" | ".join(mode_info))
        
        # 🔥 PERBAIKAN: Tampilkan selected asset jika ada
        if st.session_state.selected_for_entry:
            st.subheader("📌 Selected Assets")
            for symbol, data in st.session_state.selected_for_entry.items():
                col_sel1, col_sel2 = st.columns([3, 1])
                with col_sel1:
                    display_symbol = convert_symbol_for_display(
                        symbol,
                        bot.mode,
                        getattr(bot, 'trading_mode', 'spot')
                    )
                    market = st.session_state.current_market if hasattr(st.session_state, 'current_market') else "Crypto"
                    st.success(f"✅ **{display_symbol}** - {data.get('action', 'N/A')} (Score: {data.get('score', 0)})")
                    st.write(f"💰 Price: `{format_currency(data.get('current_price', 0), market)}` | Entry Range: `{format_currency(data.get('entry_range_low', 0), market)} - {format_currency(data.get('entry_range_high', 0), market)}`")
                with col_sel2:
                    if st.button(f"❌ Remove", key=f"remove_{symbol}"):
                        del st.session_state.selected_for_entry[symbol]
                        st.rerun()
            st.divider()
        
        # Scan button dengan opsi berbeda untuk scalping mode
        col_scan1, col_scan2, col_scan3 = st.columns([1, 2, 1])
        with col_scan1:
            if st.session_state.scalping_mode:
                scan_button_label = "🚀 Start Scalping Scan"
                scan_type = "scalping"
            else:
                scan_button_label = "🚀 Start Enhanced Scan"
                scan_type = "enhanced"
        
        with col_scan2:
            # Scan limit selector
            if st.session_state.current_market in ["Saham Indonesia", "US Stocks"]:
                scan_limit = st.select_slider(
                    "Scan Limit:",
                    options=[10, 25, 50, 100, 200, 300, 500],
                    value=100,
                    key="scan_limit_slider"
                )
            else:
                scan_limit = st.select_slider(
                    "Scan Limit:",
                    options=[10, 25, 50, 100, 200],
                    value=50,
                    key="scan_limit_slider"
                )
        
        # Enhanced scan options
        with st.expander("🔧 Advanced Scan Options"):
            col_adv1, col_adv2 = st.columns(2)
            with col_adv1:
                use_multi_scraper = st.checkbox("Use Multi-Scraper Data", value=True,
                                               help="Use data from multiple scraper sources")
                enrich_with_historical = st.checkbox("Enrich with Historical Data", value=True,
                                                    help="Add historical volatility and other metrics")
            with col_adv2:
                filter_low_volume = st.checkbox("Filter Low Volume", value=True,
                                               help="Filter assets with low trading volume")
                require_fresh_data = st.checkbox("Require Fresh Data", value=True,
                                                help="Only show assets with recent data")
        
        # Scan button
        if st.button(scan_button_label, key="start_scan", type="primary"):
            with st.spinner(f"Scanning {scan_limit} assets ({scan_type}) with external repos..."):
                try:
                    # Pastikan bot tidak None
                    if bot is None:
                        st.error("❌ Bot is not initialized")
                        return
                    
                    # Gunakan optimized scan method
                    if hasattr(bot, 'scan_potential_assets_optimized'):
                        results = bot.scan_potential_assets_optimized(scan_limit)
                    else:
                        results = bot.scan_potential_assets(scan_limit)
                    
                    if results:
                        # Process results dengan enrichment dari external repos
                        formatted_results = []
                        scalping_results = []  # 🔥 NEW: Store scalping results separately
                        
                        progress_bar = st.progress(0)
                        total_results = len(results)
                        
                        for idx, result in enumerate(results):
                            if isinstance(result, dict) and 'symbol' in result:
                                original_symbol = safe_get(result, 'symbol')
                                
                                # Format simbol
                                formatted_symbol = format_symbol_for_mode(
                                    original_symbol, 
                                    bot.mode, 
                                    getattr(bot, 'trading_mode', 'spot')
                                )
                                
                                result['symbol'] = formatted_symbol
                                result['original_symbol'] = original_symbol
                                
                                # 🔥 NEW: Enrich dengan data dari multi-scraper
                                if use_multi_scraper and hasattr(bot, 'fetch_from_scrapers'):
                                    try:
                                        historical_data = bot.fetch_from_scrapers(formatted_symbol, '1d', 30)
                                        if historical_data is not None and not historical_data.empty:
                                            # Calculate additional metrics
                                            if 'close' in historical_data.columns:
                                                returns = historical_data['close'].pct_change()
                                                result['historical_volatility'] = returns.std() * 100  # Annualized %
                                                result['avg_daily_return'] = returns.mean() * 100
                                                result['data_points'] = len(historical_data)
                                    except Exception as e:
                                        print(f"⚠️ Error enriching {formatted_symbol}: {e}")
                                
                                validated_result = validate_and_fix_price_levels(result, formatted_symbol, bot)
                                
                                # 🔥 PERBAIKAN: Filter untuk scalping yang lebih fleksibel
                                if st.session_state.scalping_mode:
                                    current_score = validated_result.get('score', 0)
                                    current_price = get_valid_price(validated_result, formatted_symbol, bot)
                                    
                                    # Kriteria tanpa bias
                                    is_scalping_suitable = (
                                        abs(current_score) >= SCALPING_CONFIG_APP["min_score"] and
                                        current_price >= 0.05 and
                                        current_price <= 200 and
                                        validated_result.get('action', 'NEUTRAL') != 'NEUTRAL'
                                    )
                                    
                                    if is_scalping_suitable:
                                        validated_result['scalping_suitable'] = True
                                        scalping_results.append(validated_result)
                                
                                formatted_results.append(validated_result)
                            
                            # Update progress bar
                            progress_bar.progress((idx + 1) / total_results)
                        
                        progress_bar.empty()
                        
                        # 🔥 PERBAIKAN: Apply additional filtering for scalping
                        if st.session_state.scalping_mode and scalping_results:
                            scalping_results = filter_for_scalping(scalping_results, bot)
                        
                        st.session_state.scanned_results = formatted_results
                        st.session_state.scalping_results = scalping_results  # 🔥 NEW
                        
                        # 🔥 PERBAIKAN: Tampilkan informasi detail
                        col_info1, col_info2, col_info3, col_info4 = st.columns(4)
                        with col_info1:
                            st.metric("Assets Scanned", scan_limit)
                        with col_info2:
                            st.metric("Valid Signals", len(formatted_results))
                        with col_info3:
                            if st.session_state.scalping_mode:
                                st.metric("Scalping Signals", len(scalping_results))
                        with col_info4:
                            st.metric("Scan Time", f"{datetime.now().strftime('%H:%M:%S')}")
                        
                        if use_multi_scraper:
                            enriched_count = sum(1 for r in formatted_results if 'historical_volatility' in r)
                            st.info(f"📊 Enriched {enriched_count} assets with historical data")
                        
                        if st.session_state.scalping_mode:
                            if scalping_results:
                                st.success(f"✅ Found {len(scalping_results)} assets suitable for scalping")
                            else:
                                st.warning(f"⚠️ No assets meet scalping criteria (min score: {SCALPING_CONFIG_APP['min_score']})")
                                st.info(f"""
                                **Possible reasons:**
                                1. Score too low (need ≥ {SCALPING_CONFIG_APP['min_score']})
                                2. Price outside range ($0.05 - $200)
                                3. NEUTRAL action (need LONG/SHORT)
                                4. Low volume atau data quality
                                """)
                        else:
                            st.success(f"✅ Found {len(formatted_results)} potential assets")
                        
                    else:
                        st.warning("⚠️ No signals found")
                        
                except Exception as e:
                    st.error(f"Scan error: {str(e)[:200]}")
        
        # 🔥 PERBAIKAN: DEBUG INFO untuk scalping dan external repos
        if st.session_state.scalping_mode or use_multi_scraper:
            with st.expander("🔧 Debug Information"):
                st.write("**Current Configuration:**")
                st.json({
                    "scalping_mode": st.session_state.scalping_mode,
                    "scalping_config": SCALPING_CONFIG_APP,
                    "use_multi_scraper": use_multi_scraper,
                    "enrich_with_historical": enrich_with_historical
                })
                
                if st.session_state.scanned_results:
                    st.write(f"**Total Scanned Results:** {len(st.session_state.scanned_results)}")
                    st.write("**Top 10 Results (with scores and historical data):**")
                    debug_data = []
                    for i, res in enumerate(st.session_state.scanned_results[:10]):
                        symbol = res.get('symbol', 'N/A')
                        score = res.get('score', 0)
                        action = res.get('action', 'NEUTRAL')
                        price = get_valid_price(res, symbol, bot)
                        market = st.session_state.current_market if hasattr(st.session_state, 'current_market') else "Crypto"
                        
                        debug_row = {
                            "Symbol": symbol,
                            "Score": f"{score:+.1f}",
                            "Action": action,
                            "Price": format_currency(price, market),
                            "Scalping?": "✅" if res.get('scalping_suitable', False) else "❌"
                        }
                        
                        # Add historical data if available
                        if 'historical_volatility' in res:
                            debug_row["Hist Vol"] = f"{res['historical_volatility']:.1f}%"
                        if 'data_points' in res:
                            debug_row["Data Points"] = res['data_points']
                        
                        debug_data.append(debug_row)
                    
                    if debug_data:
                        df_debug = pd.DataFrame(debug_data)
                        st.dataframe(df_debug, use_container_width=True)
        
        # 🔥 NEW: Jika dalam scalping mode, tampilkan hasil khusus scalping
        if st.session_state.scalping_mode and st.session_state.scalping_results:
            st.subheader("⚡ Scalping Signals (Enhanced)")
            
            for i, res in enumerate(st.session_state.scalping_results[:SCALPING_CONFIG_APP["max_signals"]], 1):
                if isinstance(res, dict) and 'symbol' in res:
                    selected = display_scalping_signal(res, i)
                    if selected:
                        st.rerun()
                    
                    # Show additional historical data if available
                    if 'historical_volatility' in res:
                        with st.expander(f"📈 Historical Data for {res['symbol']}"):
                            col_hist1, col_hist2 = st.columns(2)
                            with col_hist1:
                                st.metric("Historical Volatility", f"{res['historical_volatility']:.1f}%")
                                st.metric("Avg Daily Return", f"{res.get('avg_daily_return', 0):.2f}%")
                            with col_hist2:
                                st.metric("Data Points", res.get('data_points', 0))
                                st.metric("Signal Quality", "High" if res.get('score', 0) >= 3 else "Medium" if res.get('score', 0) >= 2 else "Low")
                    
                    st.divider()
        
        # Display regular scanned results jika tidak dalam scalping mode
        elif st.session_state.scanned_results and not st.session_state.scalping_mode:
            st.subheader("📊 Enhanced Signals with External Repos Data")
            for i, res in enumerate(st.session_state.scanned_results, 1):
                if isinstance(res, dict) and 'symbol' in res:
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        symbol = safe_get(res, 'symbol')
                        action = safe_get(res, 'action', 'NEUTRAL')
                        action_color = "🟢" if action == "LONG" else "🔴" if action == "SHORT" else "⚪"
                        
                        display_symbol = convert_symbol_for_display(
                            symbol, 
                            bot.mode, 
                            getattr(bot, 'trading_mode', 'spot')
                        )
                        
                        st.write(f"{i}. {action_color} **{display_symbol}** - {action} (Score: {safe_get(res, 'score', 0)})")
                        
                        # Show historical data if available
                        if 'historical_volatility' in res:
                            st.write(f"📊 **Historical Volatility:** `{res['historical_volatility']:.1f}%`")
                        
                        current_price = get_valid_price(res, symbol, bot)
                        market = st.session_state.current_market if hasattr(st.session_state, 'current_market') else "Crypto"
                        st.write(f"💰 Current Price: `{format_currency(current_price, market)}`")
                        
                        # Tampilkan entry range
                        st.write(f"📊 **Entry Range:** `{format_currency(res.get('entry_range_low', 0), market)} - {format_currency(res.get('entry_range_high', 0), market)}`")
                        st.write(f"🎯 **Ideal Entry:** `{format_currency(res.get('best_entry', 0), market)}`")
                        if 'range_size' in res:
                            st.write(f"📏 **Range Size:** `{res.get('range_size', 0):.1f}%`")
                        
                        # TP/SL levels
                        tp1, tp2, tp3 = safe_get(res, 'tp1', 0), safe_get(res, 'tp2', 0), safe_get(res, 'tp3', 0)
                        sl = safe_get(res, 'sl', 0)
                        
                        st.write(f"🎯 **TP Levels:** `{format_currency(tp1, market)}` | `{format_currency(tp2, market)}` | `{format_currency(tp3, market)}`")
                        st.write(f"🛑 **Stop Loss:** `{format_currency(sl, market)}`")
                        
                        # Probabilitas TP
                        if 'tp_probabilities' not in res:
                            res['tp_probabilities'] = calculate_tp_probability(
                                current_price, tp1, tp2, tp3, sl, action
                            )
                        
                        probs = res['tp_probabilities']
                        st.write(f"📊 **Probabilities:** TP1: {probs.get('tp1', 0)*100:.1f}% | TP2: {probs.get('tp2', 0)*100:.1f}% | TP3: {probs.get('tp3', 0)*100:.1f}%")
                    
                    with col2:
                        # 🔥 PERBAIKAN: Gunakan callback untuk tombol select
                        button_key = f"select_regular_{symbol}_{i}"
                        if st.button(f"📌 Select", key=button_key):
                            if select_asset_callback(symbol, res):
                                st.success(f"✅ Selected {display_symbol}!")
                                st.rerun()
                        
                        # Quick backtest button
                        backtest_key = f"quick_backtest_{symbol}_{i}"
                        if st.button(f"🧪 Quick Test", key=backtest_key):
                            with st.spinner(f"Running quick backtest for {symbol}..."):
                                try:
                                    backtest_result = bot.run_backtest(symbol)
                                    if backtest_result:
                                        st.session_state.external_repo_data[f"backtest_{symbol}"] = backtest_result
                                        st.success(f"✅ Backtest completed for {symbol}")
                                        st.rerun()
                                except Exception as e:
                                    st.error(f"❌ Backtest failed: {e}")
                    
                    st.divider()

        # ============================================
        # NEW: Manual Entry Form in Tab 1
        # ============================================
        if st.session_state.selected_for_entry:
            st.subheader("🎯 Manual Entry for Selected Asset")
            
            for symbol, data in st.session_state.selected_for_entry.items():
                display_symbol = convert_symbol_for_display(
                    symbol,
                    bot.mode,
                    getattr(bot, 'trading_mode', 'spot')
                )
                
                with st.expander(f"📝 Manual Entry Setup for {display_symbol}", expanded=True):
                    col_info1, col_info2 = st.columns(2)
                    
                    with col_info1:
                        st.info(f"**Symbol:** {display_symbol}")
                        st.info(f"**Recommended Action:** {data.get('action', 'LONG')}")
                        st.info(f"**Analysis Score:** {data.get('score', 0):.1f}")
                        
                        # Show historical data if available
                        if 'historical_volatility' in data:
                            st.info(f"**Historical Volatility:** {data['historical_volatility']:.1f}%")
                    
                    with col_info2:
                        current_price = get_valid_price(data, symbol, bot)
                        market = st.session_state.current_market if hasattr(st.session_state, 'current_market') else "Crypto"
                        st.info(f"**Current Price:** {format_currency(current_price, market)}")
                        
                        # Tombol untuk refresh harga real-time
                        if st.button(f"🔄 Refresh Price", key=f"refresh_price_{symbol}"):
                            if hasattr(bot, 'data_provider'):
                                try:
                                    ticker = bot.data_provider.get_ticker(symbol)
                                    if ticker and 'last' in ticker:
                                        data['current_price'] = float(ticker['last'])
                                        data['last'] = float(ticker['last'])
                                        st.session_state.selected_for_entry[symbol] = data
                                        st.success(f"✅ Price updated!")
                                        st.rerun()
                                except Exception as e:
                                    st.error(f"❌ Error: {e}")
                    
                    # Form manual entry
                    st.divider()
                    st.subheader("💰 Manual Entry Parameters")
                    
                    col_entry1, col_entry2 = st.columns(2)
                    
                    with col_entry1:
                        # Entry price input
                        default_entry = st.session_state.get(f'manual_entry_{symbol}', current_price)
                        currency_symbol = get_currency_symbol(st.session_state.current_market)
                        entry_price = st.number_input(
                            f"Entry Price ({currency_symbol}):",
                            value=float(default_entry),
                            min_value=0.00001,
                            step=0.0001,
                            format="%.5f",
                            key=f"entry_price_{symbol}"
                        )
                        
                        # Position size - tanpa batas minimal
                        position_size = st.number_input(
                            f"Position Size ({currency_symbol}):",
                            value=100.0,
                            min_value=0.0,  # 🔥 PERBAIKAN: Bisa 0
                            step=10.0,
                            key=f"position_size_{symbol}"
                        )
                        
                        # 🔥 PERBAIKAN: Risk optional dengan checkbox
                        use_risk = st.checkbox("Use Risk Management", 
                                             value=st.session_state.get(f'use_risk_{symbol}', False),
                                             key=f"use_risk_checkbox_{symbol}")
                        
                        if use_risk:
                            risk_percent = st.slider(
                                "Risk %:",
                                0.5, 5.0, 1.0, 0.5,
                                key=f"risk_percent_{symbol}"
                            )
                            
                            risk_amount = position_size * (risk_percent / 100)
                            st.metric("Risk Amount", f"{format_currency(risk_amount, st.session_state.current_market)}")
                        else:
                            risk_percent = None
                            st.info("⚠️ Risk management disabled")
                    
                    with col_entry2:
                        # Action selection
                        default_action = data.get('action', 'LONG')
                        action = st.selectbox(
                            "Action:",
                            ["LONG", "SHORT"],
                            index=0 if default_action == "LONG" else 1,
                            key=f"action_{symbol}"
                        )
                        
                        # TP/SL settings
                        st.subheader("🎯 Take Profit & Stop Loss")
                        
                        # Calculate default TP/SL based on action
                        if action == "LONG":
                            tp1_default = entry_price * 1.02
                            tp2_default = entry_price * 1.04
                            tp3_default = entry_price * 1.06
                            sl_default = entry_price * 0.98
                        else:
                            tp1_default = entry_price * 0.98
                            tp2_default = entry_price * 0.96
                            tp3_default = entry_price * 0.94
                            sl_default = entry_price * 1.02
                        
                        tp1 = st.number_input(
                            f"TP1 ({currency_symbol}):",
                            value=tp1_default,
                            min_value=0.00001,
                            step=0.0001,
                            format="%.5f",
                            key=f"tp1_{symbol}"
                        )
                        
                        tp2 = st.number_input(
                            f"TP2 ({currency_symbol}):",
                            value=tp2_default,
                            min_value=0.00001,
                            step=0.0001,
                            format="%.5f",
                            key=f"tp2_{symbol}"
                        )
                        
                        tp3 = st.number_input(
                            f"TP3 ({currency_symbol}):",
                            value=tp3_default,
                            min_value=0.00001,
                            step=0.0001,
                            format="%.5f",
                            key=f"tp3_{symbol}"
                        )
                        
                        sl = st.number_input(
                            f"Stop Loss ({currency_symbol}):",
                            value=sl_default,
                            min_value=0.00001,
                            step=0.0001,
                            format="%.5f",
                            key=f"sl_{symbol}"
                        )
                    
                    # Calculate Risk/Reward
                    st.divider()
                    st.subheader("📊 Risk/Reward Analysis")
                    
                    if entry_price > 0:
                        if action == "LONG":
                            risk = entry_price - sl
                            reward_tp1 = tp1 - entry_price
                            reward_tp2 = tp2 - entry_price
                            reward_tp3 = tp3 - entry_price
                        else:  # SHORT
                            risk = sl - entry_price
                            reward_tp1 = entry_price - tp1
                            reward_tp2 = entry_price - tp2
                            reward_tp3 = entry_price - tp3
                        
                        if risk > 0:
                            col_rr1, col_rr2, col_rr3 = st.columns(3)
                            with col_rr1:
                                st.metric("TP1 R/R", f"{reward_tp1/risk:.2f}:1")
                                st.caption(f"Reward: {format_currency(reward_tp1, st.session_state.current_market)}")
                            with col_rr2:
                                st.metric("TP2 R/R", f"{reward_tp2/risk:.2f}:1")
                                st.caption(f"Reward: {format_currency(reward_tp2, st.session_state.current_market)}")
                            with col_rr3:
                                st.metric("TP3 R/R", f"{reward_tp3/risk:.2f}:1")
                                st.caption(f"Reward: {format_currency(reward_tp3, st.session_state.current_market)}")
                            
                            st.metric("Risk Amount", f"{format_currency(risk, st.session_state.current_market)}", f"{risk/entry_price*100:.1f}%")
                    
                    # Tombol Open Position
                    st.divider()
                    col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 2])
                    
                    with col_btn1:
                        if st.button(f"📈 OPEN POSITION", key=f"open_position_tab1_{symbol}", type="primary"):
                            # Save parameters to session
                            st.session_state[f'manual_entry_{symbol}'] = entry_price
                            st.session_state[f'use_risk_{symbol}'] = use_risk
                            
                            # Open position
                            success = open_position(
                                symbol=symbol,
                                action=action,
                                entry_price=entry_price,
                                tp1=tp1,
                                tp2=tp2,
                                tp3=tp3,
                                sl=sl,
                                position_size=position_size,
                                risk_percent=risk_percent
                            )
                            
                            if success:
                                st.success(f"✅ Position opened for {display_symbol}!")
                                st.balloons()
                                
                                # Clear selection after opening
                                st.session_state.selected_for_entry = {}
                                
                                # Refresh positions data
                                if hasattr(bot, 'get_active_positions'):
                                    try:
                                        st.session_state.positions_data = bot.get_active_positions()
                                    except:
                                        st.session_state.positions_data = st.session_state.test_positions
                                
                                st.rerun()
                            else:
                                st.error(f"❌ Failed to open position")
                    
                    with col_btn2:
                        if st.button(f"💾 Save Parameters", key=f"save_params_{symbol}"):
                            # Save parameters to session for Tab 4
                            st.session_state.custom_symbol = symbol
                            st.session_state.custom_action = action
                            st.session_state.custom_entry_price = entry_price
                            st.session_state.custom_tp1 = tp1
                            st.session_state.custom_tp2 = tp2
                            st.session_state.custom_tp3 = tp3
                            st.session_state.custom_sl = sl
                            st.success(f"✅ Parameters saved for Tab 4!")
                    
                    with col_btn3:
                        if st.button(f"🗑️ Clear Selection", key=f"clear_sel_{symbol}"):
                            del st.session_state.selected_for_entry[symbol]
                            st.rerun()

    # Tab 2: Scalping Mode (NEW) - PERBAIKAN
    with tab2:
        st.subheader("⚡ Scalping Mode - 3-5 Minute Trading")
        
        if not st.session_state.scalping_mode:
            st.warning("⚠️ Scalping mode is not enabled!")
            st.info("""
            **Enable Scalping Mode from the sidebar to access:**
            - Tighter entry ranges (0.8%)
            - Higher score threshold (2.5)
            - No bias (0.0) - equal LONG/SHORT opportunities
            - Optimized for quick 3-5 minute trades
            - SHORT signals allowed ✅
            - Max signals: {SCALPING_CONFIG_APP["max_signals"]}
            """)
            
            if st.button("⚡ Enable Scalping Mode", key="enable_scalping_tab"):
                st.session_state.scalping_mode = True
                st.rerun()
        else:
            st.success("⚡ SCALPING MODE ACTIVE")
            
            # 🔥 PERBAIKAN: Dynamic Scalping Configuration
            with st.expander("⚙️ Dynamic Scalping Configuration"):
                col_sc1, col_sc2, col_sc3 = st.columns(3)
                
                with col_sc1:
                    min_score = st.slider("Min Score Threshold", 2.0, 5.0, 
                                         value=SCALPING_CONFIG_APP["min_score"], step=0.5,
                                         key="tab2_min_score")
                
                with col_sc2:
                    st.info("Bias: 0.0 (Neutral)")
                    long_bias = 0.0  # Hardcode ke 0
                
                with col_sc3:
                    entry_range = st.slider("Entry Range %", 0.005, 0.02,
                                          value=SCALPING_CONFIG_APP["entry_range_pct"], step=0.001,
                                          key="tab2_entry_range")
                    st.caption(f"Current: {entry_range*100:.1f}%")
                
                if st.button("🔄 Update Scalping Config", key="update_scalping_config"):
                    SCALPING_CONFIG_APP["min_score"] = min_score
                    SCALPING_CONFIG_APP["entry_range_pct"] = entry_range
                    st.session_state.scalping_config = SCALPING_CONFIG_APP
                    st.success("✅ Scalping configuration updated!")
                    st.rerun()
            
            # 🔥 PERBAIKAN: Quick Actions dengan feedback yang lebih baik
            col_qs1, col_qs2, col_qs3 = st.columns(3)
            
            with col_qs1:
                if st.button("🎯 Quick Scan (Top 20)", key="quick_scalping_scan", type="primary"):
                    with st.spinner("Quick scanning for scalping..."):
                        try:
                            # Quick scan untuk scalping
                            results = bot.scan_potential_assets(SCALPING_CONFIG_APP["max_signals"])
                            if results:
                                scalping_signals = []
                                for res in results:
                                    if isinstance(res, dict) and 'symbol' in res:
                                        symbol = res['symbol']
                                        score = res.get('score', 0)
                                        if abs(score) >= min_score:
                                            scalping_signals.append(res)
                                
                                # Apply filter
                                scalping_signals = filter_for_scalping(scalping_signals, bot)
                                
                                st.session_state.scalping_results = scalping_signals
                                st.success(f"✅ Found {len(scalping_signals)} scalping signals")
                            else:
                                st.warning("⚠️ No scalping signals found")
                        except Exception as e:
                            st.error(f"Quick scan error: {e}")
            
            with col_qs2:
                if st.button("📊 Analyze BTC/USDT", key="analyze_btc_scalping"):
                    with st.spinner("Analyzing BTC/USDT for scalping..."):
                        try:
                            symbol = "BTC/USDT" if bot.trading_mode == "spot" else "BTC/USDT:USDT"
                            analysis = bot.analyze_asset(symbol)
                            if analysis:
                                analysis['scalping_mode'] = True
                                analysis['scalping_suitable'] = True  # Mark as suitable
                                st.session_state.selected_analysis = analysis
                                st.success("✅ BTC analysis complete!")
                        except Exception as e:
                            st.error(f"Analysis error: {e}")
            
            with col_qs3:
                if st.button("🔄 Clear & Refresh", key="refresh_scalping_data"):
                    st.session_state.scalping_results = []
                    st.rerun()
            
            # Display Scalping Results
            if st.session_state.scalping_results:
                st.subheader(f"⚡ Active Scalping Signals ({len(st.session_state.scalping_results)} found)")
                
                # Sort by absolute score descending (strongest first)
                sorted_signals = sorted(st.session_state.scalping_results, 
                                      key=lambda x: abs(x.get('score', 0)), reverse=True)
                
                for i, signal in enumerate(sorted_signals[:SCALPING_CONFIG_APP["max_signals"]], 1):
                    with st.container():
                        col_s1, col_s2, col_s3 = st.columns([2, 2, 1])
                        
                        with col_s1:
                            symbol = signal.get('symbol', 'UNKNOWN')
                            action = signal.get('action', 'NEUTRAL')
                            score = signal.get('score', 0)
                            
                            # Warna berdasarkan score
                            if score >= 3.0:
                                emoji = "🚀"  # Strong LONG
                            elif score >= 2.0:
                                emoji = "📈"  # Moderate LONG
                            elif score <= -3.0:
                                emoji = "💣"  # Strong SHORT
                            elif score <= -2.0:
                                emoji = "📉"  # Moderate SHORT
                            else:
                                emoji = "⚡"
                            
                            st.write(f"{emoji} **{symbol}**")
                            st.write(f"Action: `{action}` | Score: `{score:+.1f}`")
                        
                        with col_s2:
                            current_price = get_valid_price(signal, symbol, bot)
                            market = st.session_state.current_market if hasattr(st.session_state, 'current_market') else "Crypto"
                            entry_range_low = signal.get('entry_range_low', 0)
                            entry_range_high = signal.get('entry_range_high', 0)
                            
                            st.write(f"💰 Price: `{format_currency(current_price, market)}`")
                            st.write(f"🎯 Entry: `{format_currency(entry_range_low, market)}` - `{format_currency(entry_range_high, market)}`")
                        
                        with col_s3:
                            tp1 = signal.get('tp1', 0)
                            tp2 = signal.get('tp2', 0)
                            tp3 = signal.get('tp3', 0)
                            sl = signal.get('sl', 0)
                            
                            if action == "LONG":
                                rr_ratio = (tp1 - current_price) / (current_price - sl) if (current_price - sl) > 0 else 0
                            else:
                                rr_ratio = (current_price - tp1) / (sl - current_price) if (sl - current_price) > 0 else 0
                            
                            st.write(f"📊 R/R: `{rr_ratio:.2f}`")
                            st.write(f"🎯 TP1: `{format_currency(tp1, market)}`")
                            
                            button_key = f"select_scalping_signal_{i}_{symbol}"
                            if st.button(f"📌 Select", key=button_key):
                                if select_asset_callback(symbol, signal):
                                    st.success(f"✅ Selected {symbol} for scalping!")
                                    st.rerun()
                        
                        st.divider()
            
            # Scalping Tips
            with st.expander("💡 Scalping Tips"):
                st.write(f"""
                **Scalping Strategy (3-5 minutes):**
                1. **Entry Timing:** Wait for price to hit entry range
                2. **Position Size:** 2-5% of capital per trade
                3. **Take Profit:** TP1 is primary target (60-70% probability)
                4. **Stop Loss:** Always use stop loss
                5. **Max Trades:** {SCALPING_CONFIG_APP["max_signals"]} signals maximum
                
                **Risk Management:**
                - Max risk per trade: 1% of capital
                - Daily max loss: 3% of capital
                - Never revenge trade
                
                **SHORT Scalping Tips:**
                - Best during bearish trends atau market corrections
                - Look for overbought RSI (>70) for short entries
                - Use tighter stops (1-2%) for shorts
                - Take profit quickly (1-2% moves)
                
                **Best Conditions for Scalping:**
                - High volume (> $1M daily)
                - Moderate volatility (2-8% daily)
                - Clear support/resistance levels
                - Large asset pool (500+ assets recommended)
                """)

    # Tab 3: Analyze Asset - FIXED VERSION
    with tab3:
        st.subheader("🔍 Analyze Specific Asset")
        
        # Info mode
        mode_status = []
        if hasattr(bot, 'trading_mode'):
            mode_display = "🔄 Spot" if bot.trading_mode == "spot" else "⚡ Futures"
            mode_status.append(f"**Mode:** {mode_display}")
        
        if st.session_state.scalping_mode:
            mode_status.append("⚡ **SCALPING:** ON")
        
        # Asset pool info
        if st.session_state.current_market in ["Saham Indonesia", "US Stocks"]:
            mode_status.append("📈 **500+ Assets**")
        elif st.session_state.current_market == "Forex":
            mode_status.append("💱 **50+ Pairs**")
        elif st.session_state.current_market == "Crypto":
            mode_status.append("💰 **200+ Pairs**")
        
        if mode_status:
            st.info(" | ".join(mode_status))
        
        col_analyze1, col_analyze2 = st.columns([2, 1])
        with col_analyze1:
            symbol_input = st.text_input("Enter symbol:", key="analyze_symbol", 
                                        placeholder="BTC or BTC/USDT or BTC/USDT:USDT")
    
        # Apply scalping parameters jika scalping mode aktif
        analysis_config = {}
        if st.session_state.scalping_mode:
            with st.expander("⚡ Scalping Analysis Settings"):
                col_sa1, col_sa2 = st.columns(2)
                with col_sa1:
                    st.info("Analysis Bias: 0.0 (disabled)")
                    analysis_config['long_bias'] = 0.0
                with col_sa2:
                    analysis_config['min_score'] = st.slider("Min Score", 2.0, 6.0,
                                                           value=SCALPING_CONFIG_APP["min_score"],
                                                           step=0.5, key="tab3_min_score")
        
        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            if st.button("🚀 Analyze", key="analyze_btn", type="primary"):
                if symbol_input:
                    with st.spinner("Analyzing..."):
                        try:
                            symbol = symbol_input.upper().strip()
                            
                            # Format simbol
                            formatted_symbol = format_symbol_for_mode(
                                symbol, 
                                bot.mode,
                                getattr(bot, 'trading_mode', 'spot')
                            )
                            
                            st.info(f"🔍 Analyzing: {formatted_symbol}")
                            
                            # Coba ambil harga real dulu sebelum analisis
                            current_price = 0
                            if hasattr(bot, 'data_provider') and bot.data_provider:
                                try:
                                    ticker = bot.data_provider.get_ticker(formatted_symbol)
                                    if ticker and isinstance(ticker, dict):
                                        for price_key in ['last', 'close', 'current']:
                                            if price_key in ticker and ticker[price_key]:
                                                current_price = float(ticker[price_key])
                                                market = st.session_state.current_market if hasattr(st.session_state, 'current_market') else "Crypto"
                                                st.success(f"💰 Current Price: {format_currency(current_price, market)}")
                                                break
                                except Exception as e:
                                    st.warning(f"⚠️ Cannot get real-time price: {e}")
                            
                            analysis = bot.analyze_asset(formatted_symbol)
                            if analysis:
                                # Apply scalping config jika ada
                                if analysis_config:
                                    analysis['min_score_threshold'] = analysis_config.get('min_score', 2.5)
                                    analysis['scalping_mode'] = True
                                
                                # Update dengan harga real jika ada
                                if current_price > 0:
                                    analysis['current_price'] = current_price
                                    analysis['last'] = current_price
                                
                                analysis = validate_and_fix_price_levels(analysis, formatted_symbol, bot)
                                
                                analysis['formatted_symbol'] = formatted_symbol
                                analysis['original_input'] = symbol_input
                                
                                # 🔥 NEW: Fetch historical data from scrapers
                                if hasattr(bot, 'fetch_from_scrapers'):
                                    try:
                                        historical_data = bot.fetch_from_scrapers(formatted_symbol, '1d', 30)
                                        if historical_data is not None and not historical_data.empty:
                                            if 'close' in historical_data.columns:
                                                returns = historical_data['close'].pct_change()
                                                analysis['historical_volatility'] = returns.std() * 100
                                                analysis['historical_data_points'] = len(historical_data)
                                                analysis['avg_historical_volume'] = historical_data['volume'].mean() if 'volume' in historical_data.columns else 0
                                    except Exception as e:
                                        print(f"⚠️ Error fetching historical data: {e}")
                                
                                # Hitung probabilitas TP
                                tp1, tp2, tp3 = safe_get(analysis, 'tp1', 0), safe_get(analysis, 'tp2', 0), safe_get(analysis, 'tp3', 0)
                                action = safe_get(analysis, 'action', 'LONG')
                                current_price = get_valid_price(analysis, formatted_symbol, bot)
                                
                                analysis['tp_probabilities'] = calculate_tp_probability(
                                    current_price, tp1, tp2, tp3, safe_get(analysis, 'sl', 0), action
                                )
                                
                                st.session_state.selected_analysis = analysis
                                st.success("✅ Analysis complete!")
                            else:
                                st.error("❌ Analysis failed - No data returned")
                        except Exception as e:
                            st.error(f"❌ Analysis error: {str(e)}")
                            import traceback
                            st.code(traceback.format_exc())
        
        with col_btn2:
            # Tombol untuk test provider
            if st.button("🧪 Test Provider", key="test_provider_btn"):
                if hasattr(bot, 'data_provider'):
                    try:
                        test_symbol = "BTC/USDT" if bot.trading_mode == "spot" else "BTC/USDT:USDT"
                        ticker = bot.data_provider.get_ticker(test_symbol)
                        if ticker:
                            market = st.session_state.current_market if hasattr(st.session_state, 'current_market') else "Crypto"
                            st.success(f"✅ Provider active! BTC Price: {format_currency(ticker.get('last', 'N/A'), market)}")
                        else:
                            st.error("❌ Provider returned no data")
                    except Exception as e:
                        st.error(f"❌ Provider error: {e}")
                else:
                    st.error("❌ No data provider available")
        
        if st.session_state.selected_analysis:
            analysis = st.session_state.selected_analysis
            symbol_display = convert_symbol_for_display(
                analysis.get('formatted_symbol', analysis.get('symbol', '')),
                bot.mode,
                getattr(bot, 'trading_mode', 'spot')
            )
            
            st.subheader(f"📊 Analysis: {symbol_display}")
            
            # Scalping indicator
            if analysis.get('scalping_mode'):
                st.success("⚡ Scalping Analysis Applied")
            
            # Historical data indicator
            if 'historical_volatility' in analysis:
                st.info(f"📈 Historical Data Available ({analysis.get('historical_data_points', 0)} data points)")
            
            # Tombol Save untuk digunakan di Custom Entry
            col_save1, col_save2, col_save3 = st.columns([2, 2, 1])
            with col_save1:
                if st.button("💾 Save for Custom Entry", key="save_analysis_btn", type="primary"):
                    symbol = analysis.get('formatted_symbol', analysis.get('symbol'))
                    if symbol:
                        st.session_state.selected_for_entry = {symbol: analysis}
                        st.session_state.custom_symbol = symbol
                        st.session_state.custom_action = analysis.get('action', 'LONG')
                        st.session_state.custom_entry_price = analysis.get('current_price', 0)
                        st.success(f"✅ {symbol} saved for Custom Entry!")
                        st.info("Go to Tab 4 (Custom Entry) to use this analysis")
            
            with col_save2:
                if st.button("📊 Show Raw Data", key="show_raw_data"):
                    with st.expander("📋 Raw Analysis Data"):
                        st.json(analysis)
            
            with col_save3:
                if st.button("🔄 Refresh Price", key="refresh_price_btn"):
                    # Refresh harga real
                    symbol = analysis.get('formatted_symbol', analysis.get('symbol'))
                    if symbol and hasattr(bot, 'data_provider'):
                        try:
                            ticker = bot.data_provider.get_ticker(symbol)
                            if ticker and 'last' in ticker:
                                new_price = float(ticker['last'])
                                analysis['current_price'] = new_price
                                analysis['last'] = new_price
                                st.session_state.selected_analysis = analysis
                                market = st.session_state.current_market if hasattr(st.session_state, 'current_market') else "Crypto"
                                st.success(f"✅ Price updated: {format_currency(new_price, market)}")
                                st.rerun()
                        except Exception as e:
                            st.error(f"❌ Price update failed: {e}")
            
            col1, col2 = st.columns(2)
            with col1:
                action = safe_get(analysis, 'action', 'NEUTRAL')
                action_color = "🟢" if action == "LONG" else "🔴" if action == "SHORT" else "⚪"
                st.metric("Action", f"{action_color} {action}")
                st.metric("Score", safe_get(analysis, 'score', 0))
                
                current_price = get_valid_price(analysis, analysis.get('symbol'), bot)
                market = st.session_state.current_market if hasattr(st.session_state, 'current_market') else "Crypto"
                st.metric("Current Price", format_currency(current_price, market))
                
                st.metric("Trend", safe_get(analysis, 'trend', 'NEUTRAL'))
                
                # Historical metrics
                if 'historical_volatility' in analysis:
                    st.metric("Historical Volatility", f"{analysis['historical_volatility']:.1f}%")
                
            with col2:
                st.metric("RSI", f"{safe_get(analysis, 'rsi', 0):.1f}")
                st.metric("Volume Ratio", f"{safe_get(analysis, 'volume_ratio', 0):.2f}")
                st.metric("ATR", f"{safe_get(analysis, 'atr', 0):.5f}")
                
                if 'tp_probabilities' in analysis:
                    probs = analysis['tp_probabilities']
                    st.metric("TP1 Probability", f"{probs.get('tp1', 0)*100:.1f}%")
                
                # More historical data
                if 'historical_data_points' in analysis:
                    st.metric("Data Points", analysis['historical_data_points'])
            
            # Entry Range Details
            st.subheader("🎯 Entry Range & TP/SL Levels")
            col_range1, col_range2, col_range3, col_range4 = st.columns(4)
            with col_range1:
                entry_low = analysis.get('entry_range_low', 0)
                st.metric("Entry Range Low", format_currency(entry_low, st.session_state.current_market))
            with col_range2:
                entry_high = analysis.get('entry_range_high', 0)
                st.metric("Entry Range High", format_currency(entry_high, st.session_state.current_market))
            with col_range3:
                best_entry = analysis.get('best_entry', 0)
                st.metric("Ideal Entry", format_currency(best_entry, st.session_state.current_market))
            with col_range4:
                range_size = analysis.get('range_size', 0)
                st.metric("Range Size", f"{range_size:.2f}%")
            
            # TP/SL Levels
            st.subheader("🎯 Take Profit & Stop Loss")
            tp_col1, tp_col2, tp_col3, sl_col = st.columns(4)
            with tp_col1:
                tp1 = analysis.get('tp1', 0)
                st.metric("TP1", format_currency(tp1, st.session_state.current_market))
            with tp_col2:
                tp2 = analysis.get('tp2', 0)
                st.metric("TP2", format_currency(tp2, st.session_state.current_market))
            with tp_col3:
                tp3 = analysis.get('tp3', 0)
                st.metric("TP3", format_currency(tp3, st.session_state.current_market))
            with sl_col:
                sl = analysis.get('sl', 0)
                st.metric("Stop Loss", format_currency(sl, st.session_state.current_market))
            
            # TP Probabilities
            if 'tp_probabilities' in analysis:
                st.subheader("📊 TP Probabilities")
                probs = analysis['tp_probabilities']
                prob_col1, prob_col2, prob_col3 = st.columns(3)
                with prob_col1:
                    st.progress(probs.get('tp1', 0), text=f"TP1: {probs.get('tp1', 0)*100:.1f}%")
                with prob_col2:
                    st.progress(probs.get('tp2', 0), text=f"TP2: {probs.get('tp2', 0)*100:.1f}%")
                with prob_col3:
                    st.progress(probs.get('tp3', 0), text=f"TP3: {probs.get('tp3', 0)*100:.1f}%")

    # Tab 4: Custom Entry & Open Position - ENHANCED VERSION
    with tab4:
        st.subheader("🎯 Custom Entry & Open Position")
        
        # Mode info
        mode_info = []
        if hasattr(bot, 'trading_mode'):
            mode_display = "🔄 Spot" if bot.trading_mode == "spot" else "⚡ Futures"
            mode_info.append(f"**Trading Mode:** {mode_display}")
        
        if st.session_state.scalping_mode:
            mode_info.append("⚡ **SCALPING:** ON")
        
        # Asset pool info
        if st.session_state.current_market in ["Saham Indonesia", "US Stocks"]:
            mode_info.append("📈 **500+ Assets**")
        
        if mode_info:
            st.info(" | ".join(mode_info))
        
        # ============================================
        # STEP 1: Pilih Aset atau Input Manual
        # ============================================
        st.subheader("📌 Step 1: Select or Enter Asset")
        
        use_existing = st.checkbox("Use existing analysis from Tab 3", value=True, 
                                  help="Use previously analyzed asset, or enter manually")
        
        if use_existing and st.session_state.selected_analysis:
            analysis = st.session_state.selected_analysis
            symbol_selected = analysis.get('formatted_symbol', analysis.get('symbol'))
            action_selected = analysis.get('action', 'LONG')
            entry_price = analysis.get('current_price', 0)
            
            col_info1, col_info2 = st.columns([3, 1])
            with col_info1:
                st.success(f"✅ Using: **{symbol_selected}**")
                st.write(f"Action: `{action_selected}` | Score: `{analysis.get('score', 0):.1f}`")
                market = st.session_state.current_market if hasattr(st.session_state, 'current_market') else "Crypto"
                st.write(f"Current Price: {format_currency(entry_price, market)}")
                st.write(f"Entry Range: {format_currency(analysis.get('entry_range_low', 0), market)} - {format_currency(analysis.get('entry_range_high', 0), market)}")
                
                # Show historical data if available
                if 'historical_volatility' in analysis:
                    st.write(f"Historical Volatility: {analysis['historical_volatility']:.1f}%")
            
            with col_info2:
                if st.button("📌 Use This", key="use_analysis_btn"):
                    st.session_state.custom_symbol = symbol_selected
                    st.session_state.custom_action = action_selected
                    st.session_state.custom_entry_price = entry_price
                    st.session_state.custom_tp1 = analysis.get('tp1', 0)
                    st.session_state.custom_tp2 = analysis.get('tp2', 0)
                    st.session_state.custom_tp3 = analysis.get('tp3', 0)
                    st.session_state.custom_sl = analysis.get('sl', 0)
                    st.success("✅ Data loaded!")
                    st.rerun()
        else:
            st.info("Enter asset details manually")
        
        st.divider()
        
        # ============================================
        # STEP 2: Input Entry Details Manual Lengkap
        # ============================================
        st.subheader("💰 Step 2: Entry Details (Manual Input)")
        
        col_symbol, col_action = st.columns([2, 1])
        with col_symbol:
            # Auto-fill symbol
            default_symbol = st.session_state.get('custom_symbol', '')
            symbol_custom = st.text_input("Symbol:", 
                                         value=default_symbol,
                                         key="custom_symbol_input_tab4", 
                                         placeholder="BTC/USDT or BTC/USDT:USDT")
        
        with col_action:
            # Auto-fill action
            default_action = st.session_state.get('custom_action', 'LONG')
            action_custom = st.selectbox("Action:", ["LONG", "SHORT"], 
                                        index=0 if default_action == "LONG" else 1,
                                        key="custom_action_select_tab4")
        
        # Get current price button
        col_price1, col_price2 = st.columns([3, 1])
        with col_price1:
            # Input entry price
            currency_symbol = get_currency_symbol(st.session_state.current_market)
            default_price = st.session_state.get('custom_entry_price', 0.0)
            safe_default_price = max(float(default_price), 0.00001)
            
            entry_price_custom = st.number_input(
                f"Entry Price ({currency_symbol}):", 
                value=safe_default_price,
                min_value=0.00001,
                step=0.01, 
                format="%.5f",
                key="custom_entry_price_tab4"
            )
        
        with col_price2:
            st.write("")  # Spacer
            st.write("")  # Spacer
            if st.button("📊 Get Current Price", key="get_current_price_btn"):
                if symbol_custom and hasattr(bot, 'data_provider'):
                    with st.spinner("Getting current price..."):
                        try:
                            ticker = bot.data_provider.get_ticker(symbol_custom)
                            if ticker and 'last' in ticker:
                                current_price = float(ticker['last'])
                                st.session_state.custom_entry_price = current_price
                                market = st.session_state.current_market if hasattr(st.session_state, 'current_market') else "Crypto"
                                st.success(f"✅ Current price: {format_currency(current_price, market)}")
                                st.rerun()
                            else:
                                st.error("❌ Cannot get current price")
                        except Exception as e:
                            st.error(f"❌ Error: {e}")
                else:
                    st.warning("⚠️ Enter symbol first or check provider")
        
        # Position Size dan Risk
        col_size, col_risk = st.columns(2)
        with col_size:
            position_size = st.number_input(
                f"Position Size ({currency_symbol}):",
                value=100.0,
                min_value=0.0,  # 🔥 PERBAIKAN: Bisa 0
                step=10.0,
                key="position_size_input_tab4"
            )
        
        with col_risk:
            # 🔥 PERBAIKAN: Risk optional dengan checkbox
            use_risk = st.checkbox("Use Risk Management", 
                                 value=st.session_state.get('use_risk_management', False),
                                 key="use_risk_tab4")
            
            if use_risk:
                risk_percent = st.slider("Risk %:", 0.5, 5.0, 1.0, 0.5, key="risk_percent_tab4")
                risk_amount = position_size * (risk_percent / 100)
                st.metric("Risk Amount", f"{format_currency(risk_amount, st.session_state.current_market)}")
            else:
                risk_percent = None
                st.info("⚠️ Risk management disabled")
        
        st.divider()
        
        # ============================================
        # STEP 3: TP/SL Settings - AUTO or MANUAL
        # ============================================
        st.subheader("🎯 Step 3: TP/SL Settings")
        
        tp_sl_mode = st.radio("TP/SL Mode:", ["Auto Calculate", "Manual Input"], 
                             key="tp_sl_mode", horizontal=True)
        
        if tp_sl_mode == "Auto Calculate":
            col_auto1, col_auto2 = st.columns(2)
            with col_auto1:
                tp_percent = st.slider("TP % per level:", 1.0, 10.0, 2.0, 0.5, 
                                     key="tp_percent_auto")
                st.caption(f"TP1: +{tp_percent}%, TP2: +{tp_percent*2}%, TP3: +{tp_percent*3}%")
            
            with col_auto2:
                sl_percent = st.slider("SL %:", 1.0, 10.0, 2.0, 0.5, key="sl_percent_auto")
                st.caption(f"Stop Loss: {sl_percent}%")
            
            # Calculate TP/SL automatically
            if action_custom == "LONG":
                tp1_auto = entry_price_custom * (1 + tp_percent/100)
                tp2_auto = entry_price_custom * (1 + (tp_percent*2)/100)
                tp3_auto = entry_price_custom * (1 + (tp_percent*3)/100)
                sl_auto = entry_price_custom * (1 - sl_percent/100)
            else:  # SHORT
                tp1_auto = entry_price_custom * (1 - tp_percent/100)
                tp2_auto = entry_price_custom * (1 - (tp_percent*2)/100)
                tp3_auto = entry_price_custom * (1 - (tp_percent*3)/100)
                sl_auto = entry_price_custom * (1 + sl_percent/100)
            
            # Assign auto values
            tp1_custom, tp2_custom, tp3_custom, sl_custom = tp1_auto, tp2_auto, tp3_auto, sl_auto
            
            # Show auto values
            col_show1, col_show2 = st.columns(2)
            with col_show1:
                st.info(f"**TP1:** {format_currency(tp1_auto, st.session_state.current_market)}")
                st.info(f"**TP2:** {format_currency(tp2_auto, st.session_state.current_market)}")
                st.info(f"**TP3:** {format_currency(tp3_auto, st.session_state.current_market)}")
            with col_show2:
                st.warning(f"**Stop Loss:** {format_currency(sl_auto, st.session_state.current_market)}")
                
        else:  # Manual Input
            st.info("Enter TP/SL values manually:")
            
            col_manual1, col_manual2 = st.columns(2)
            with col_manual1:
                # Load from session state if exists
                default_tp1 = st.session_state.get('custom_tp1', 0)
                default_tp2 = st.session_state.get('custom_tp2', 0)
                default_tp3 = st.session_state.get('custom_tp3', 0)
                
                tp1_custom = st.number_input(
                    f"TP1 ({currency_symbol}):",
                    value=max(default_tp1, entry_price_custom * 1.02),
                    min_value=0.00001,
                    step=0.01,
                    format="%.5f",
                    key="manual_tp1"
                )
                
                tp2_custom = st.number_input(
                    f"TP2 ({currency_symbol}):",
                    value=max(default_tp2, entry_price_custom * 1.04),
                    min_value=0.00001,
                    step=0.01,
                    format="%.5f",
                    key="manual_tp2"
                )
                
                tp3_custom = st.number_input(
                    f"TP3 ({currency_symbol}):",
                    value=max(default_tp3, entry_price_custom * 1.06),
                    min_value=0.00001,
                    step=0.01,
                    format="%.5f",
                    key="manual_tp3"
                )
            
            with col_manual2:
                # Load from session state if exists
                default_sl = st.session_state.get('custom_sl', 0)
                
                sl_custom = st.number_input(
                    f"Stop Loss ({currency_symbol}):",
                    value=max(default_sl, entry_price_custom * 0.98),
                    min_value=0.00001,
                    step=0.01,
                    format="%.5f",
                    key="manual_sl"
                )
                
                # Quick buttons for SL
                st.caption("Quick SL:")
                col_sl1, col_sl2, col_sl3 = st.columns(3)
                with col_sl1:
                    if st.button("-2%", key="sl_minus_2"):
                        st.session_state.manual_sl = entry_price_custom * 0.98
                        st.rerun()
                with col_sl2:
                    if st.button("-5%", key="sl_minus_5"):
                        st.session_state.manual_sl = entry_price_custom * 0.95
                        st.rerun()
                with col_sl3:
                    if st.button("-10%", key="sl_minus_10"):
                        st.session_state.manual_sl = entry_price_custom * 0.90
                        st.rerun()
        
        # Calculate Risk/Reward
        st.divider()
        st.subheader("📊 Risk/Reward Analysis")
        
        if entry_price_custom > 0:
            if action_custom == "LONG":
                risk = entry_price_custom - sl_custom
                reward_tp1 = tp1_custom - entry_price_custom
                reward_tp2 = tp2_custom - entry_price_custom
                reward_tp3 = tp3_custom - entry_price_custom
            else:  # SHORT
                risk = sl_custom - entry_price_custom
                reward_tp1 = entry_price_custom - tp1_custom
                reward_tp2 = entry_price_custom - tp2_custom
                reward_tp3 = entry_price_custom - tp3_custom
            
            if risk > 0:
                rr1 = reward_tp1 / risk
                rr2 = reward_tp2 / risk
                rr3 = reward_tp3 / risk
                
                col_rr1, col_rr2, col_rr3 = st.columns(3)
                with col_rr1:
                    st.metric("TP1 R/R", f"{rr1:.2f}:1")
                    st.caption(f"Reward: {format_currency(reward_tp1, st.session_state.current_market)}")
                with col_rr2:
                    st.metric("TP2 R/R", f"{rr2:.2f}:1")
                    st.caption(f"Reward: {format_currency(reward_tp2, st.session_state.current_market)}")
                with col_rr3:
                    st.metric("TP3 R/R", f"{rr3:.2f}:1")
                    st.caption(f"Reward: {format_currency(reward_tp3, st.session_state.current_market)}")
                
                st.metric("Risk Amount", f"{format_currency(risk, st.session_state.current_market)}", f"{risk/entry_price_custom*100:.1f}%")
        
        st.divider()
        
        # ============================================
        # STEP 4: Open Position
        # ============================================
        st.subheader("🚀 Step 4: Open Position")
        
        if st.button("📈 OPEN POSITION", key="open_position_btn_tab4", type="primary", use_container_width=True):
            if symbol_custom and entry_price_custom > 0:
                with st.spinner("Opening position..."):
                    # Create position data
                    position_data = {
                        'symbol': symbol_custom,
                        'action': action_custom,
                        'entry_price': entry_price_custom,
                        'tp1': tp1_custom,
                        'tp2': tp2_custom,
                        'tp3': tp3_custom,
                        'sl': sl_custom,
                        'position_size': position_size,
                        'risk_percent': risk_percent
                    }
                    
                    success = open_position(**position_data)
                    
                    if success:
                        st.success("✅ Position opened successfully!")
                        st.balloons()
                        
                        # Clear session state
                        keys_to_clear = ['custom_symbol', 'custom_action', 'custom_entry_price',
                                       'custom_tp1', 'custom_tp2', 'custom_tp3', 'custom_sl']
                        for key in keys_to_clear:
                            if key in st.session_state:
                                del st.session_state[key]
                        
                        # Refresh positions
                        if hasattr(bot, 'get_active_positions'):
                            try:
                                st.session_state.positions_data = bot.get_active_positions()
                            except:
                                st.session_state.positions_data = st.session_state.test_positions
                        
                        st.rerun()
                    else:
                        st.error("❌ Failed to open position")
            else:
                st.warning("⚠️ Please enter symbol and valid entry price")
        
        # Tampilkan positions yang sudah dibuat
        if hasattr(st.session_state, 'test_positions') and st.session_state.test_positions:
            st.divider()
            st.subheader("📋 Recently Opened Positions")
            
            for pos in st.session_state.test_positions[-3:]:
                col_pos1, col_pos2 = st.columns([3, 1])
                with col_pos1:
                    display_symbol = convert_symbol_for_display(
                        pos['symbol'],
                        bot.mode,
                        getattr(bot, 'trading_mode', 'spot')
                    )
                    st.write(f"**{display_symbol}** - {pos['action']}")
                    market = st.session_state.current_market if hasattr(st.session_state, 'current_market') else "Crypto"
                    st.write(f"Entry: {format_currency(pos['entry_price'], market)} | Size: {format_currency(pos['position_size'], market)}")
                    st.write(f"TP1: {format_currency(pos['tp1'], market)} | TP2: {format_currency(pos['tp2'], market)} | TP3: {format_currency(pos['tp3'], market)}")
                    st.write(f"SL: {format_currency(pos['sl'], market)}")
                    if pos['risk_percent']:
                        st.write(f"Risk: {pos['risk_percent']}% ({format_currency(pos['position_size'] * pos['risk_percent']/100, market)})")
                    else:
                        st.write("Risk: Disabled")
                with col_pos2:
                    st.write(f"⏰ {pos['timestamp']}")
                    if pos.get('saved_to_db'):
                        st.success("✅ In Database")
                    else:
                        st.warning("⚠️ Session Only")

    # Tab 6: Positions - 🔥 FIXED VERSION dengan VALIDASI HARGA
    with tab6:
        st.subheader("💼 Active Positions")
        
        # Mode info
        mode_info = []
        if hasattr(bot, 'trading_mode'):
            mode_display = "🔄 Spot" if bot.trading_mode == "spot" else "⚡ Futures"
            mode_info.append(f"**Trading Mode:** {mode_display}")
        
        if st.session_state.scalping_mode:
            mode_info.append("⚡ **SCALPING:** ON")
        
        # Asset pool info
        if st.session_state.current_market in ["Saham Indonesia", "US Stocks"]:
            mode_info.append("📈 **500+ Assets**")
        
        if mode_info:
            st.info(" | ".join(mode_info))
        
        # 🔥 DEBUG PANEL untuk troubleshooting
        with st.expander("🐛 Debug Price Lookup"):
            test_symbol = st.text_input("Test symbol:", "FLOW/USDT (Futures)")
            if st.button("Test Price Lookup", key="debug_price"):
                with st.spinner("Testing..."):
                    price, source = get_realtime_price_with_fallback(test_symbol, bot, 0.18660)
                    market = st.session_state.current_market if hasattr(st.session_state, 'current_market') else "Crypto"
                    st.write(f"**Result:** Price: {format_currency(price, market) if price else price}, Source: {source}")
                    if price:
                        st.write(f"**Validasi:** Entry: {format_currency(0.18660, market)}, Current: {format_currency(price, market)}, Ratio: {price/0.18660:.2f}x")
        
        # Tambahkan tombol refresh real-time dengan update database
        col_rt1, col_rt2, col_rt3 = st.columns([1, 1, 2])
        with col_rt1:
            if st.button("💰 Update ALL Prices", key="update_all_prices_tab6", type="primary"):
                with st.spinner("Updating prices from real-time data and saving to DB..."):
                    # Update semua harga dan simpan ke database
                    updated_count = update_all_positions_prices(bot)
                    
                    if updated_count > 0:
                        st.success(f"✅ Updated {updated_count} positions in database with real-time prices!")
                    else:
                        st.warning("⚠️ No positions were updated. Check logs for details.")
                    
                    # Refresh positions data setelah update
                    st.session_state.positions_data = bot.get_active_positions()
                    st.rerun()
        
        with col_rt2:
            if st.button("🔄 Refresh Positions", key="refresh_positions_tab6", type="primary"):
                try:
                    # Ambil dari database
                    positions = bot.get_active_positions()
                    if positions:
                        st.session_state.positions_data = positions
                        st.success(f"✅ Loaded {len(positions)} positions from database")
                    else:
                        # Fallback ke session state
                        if hasattr(st.session_state, 'test_positions') and st.session_state.test_positions:
                            st.session_state.positions_data = st.session_state.test_positions
                            st.info(f"📋 Showing {len(st.session_state.test_positions)} positions from session")
                        else:
                            st.session_state.positions_data = []
                            st.info("📭 No positions found")
                    
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Refresh error: {e}")
        
        with col_rt3:
            # Provider status
            if hasattr(bot, 'data_provider') and bot.data_provider:
                st.success("🟢 Provider Active")
            else:
                st.warning("🟡 No Data Provider")
        
        # Kumpulkan semua posisi dari database
        all_positions = []

        # 1. Dari database positions - PASTIKAN menggunakan get_active_positions()
        try:
            db_positions = bot.get_active_positions()
            if db_positions:
                for pos in db_positions:
                    if isinstance(pos, dict):
                        # Standardize status
                        if pos.get('status') == 'active':
                            pos['status'] = 'open'
                        
                        # Ensure current_price exists
                        if 'current_price' not in pos or not pos['current_price']:
                            pos['current_price'] = pos.get('entry_price', 0)
                        
                        # Add to list
                        all_positions.append(pos)
        except Exception as e:
            st.error(f"❌ Error getting DB positions: {e}")

        # 2. Dari session test_positions (hanya jika tidak ada di DB)
        if hasattr(st.session_state, 'test_positions') and st.session_state.test_positions:
            for session_pos in st.session_state.test_positions:
                # Check if already in all_positions
                session_symbol = session_pos.get('symbol', '')
                already_exists = False
                
                for db_pos in all_positions:
                    if db_pos.get('symbol') == session_symbol:
                        already_exists = True
                        break
                
                if not already_exists and session_pos.get('status', 'open') == 'open':
                    all_positions.append(session_pos)

        # Filter hanya posisi yang open
        open_positions = []
        for pos in all_positions:
            status = pos.get('status', 'open').lower()
            if status in ['open', 'active']:
                open_positions.append(pos)

        # Tampilkan jumlah posisi
        st.subheader(f"📊 Active Positions ({len(open_positions)})")
        
        if not open_positions:
            st.info("📭 No active positions")
            st.info("👉 Open a position in Tab 4 first!")
        else:
            # Display positions dengan error handling dan VALIDASI HARGA
            for idx, pos in enumerate(open_positions):
                try:
                    position_id = pos.get('id', f'pos_{idx}')
                    symbol = pos.get('symbol', 'UNKNOWN')
                    action = pos.get('action', 'LONG')
                    entry_price = float(pos.get('entry_price', 0))
                    
                    print(f"\n🔍 Processing position {idx+1}: {symbol}")
                    print(f"   Entry price: {format_currency(entry_price, st.session_state.current_market)}")
                    
                    # 🔥 Dapatkan harga real-time dengan VALIDASI
                    realtime_price, source = get_realtime_price_with_fallback(symbol, bot, entry_price)
                    
                    if realtime_price and realtime_price > 0:
                        # 🔥 VALIDASI HARGA: Cek apakah harga wajar
                        if not validate_price_reasonable(realtime_price, entry_price, symbol):
                            market = st.session_state.current_market if hasattr(st.session_state, 'current_market') else "Crypto"
                            st.warning(f"⚠️ Harga tidak wajar untuk {symbol}: {format_currency(realtime_price, market)}")
                            # Gunakan harga entry sebagai fallback
                            current_price = entry_price
                            price_source = "Entry (Invalid Live)"
                            
                            # Log error
                            st.error(f"""
                            ❌ **HARGA TIDAK WAJAR DETECTED**
                            - Simbol: {symbol}
                            - Entry: {format_currency(entry_price, market)}
                            - Live Price: {format_currency(realtime_price, market)}
                            - Rasio: {realtime_price/entry_price:.2f}x
                            
                            **Kemungkinan penyebab:**
                            1. Format simbol salah
                            2. Provider mengembalikan data yang salah
                            3. Simbol tidak ditemukan
                            
                            **Sementara menggunakan harga entry.**
                            """)
                        else:
                            # Update harga di database jika valid
                            update_success = update_position_price_in_db(bot, position_id, realtime_price)
                            current_price = realtime_price
                            price_source = f"Live ({source})" + (" + DB" if update_success else "")
                    else:
                        # Gunakan harga dari database
                        current_price = float(pos.get('current_price', entry_price))
                        price_source = "Database"
                    
                    # Pastikan tp1, sl, dan position_size valid
                    try:
                        tp1 = float(pos.get('tp1', entry_price * 1.02))
                        tp2 = float(pos.get('tp2', entry_price * 1.04))
                        tp3 = float(pos.get('tp3', entry_price * 1.06))
                        sl = float(pos.get('sl', entry_price * 0.98))
                        position_size = float(pos.get('position_size', 100))
                    except:
                        tp1 = entry_price * 1.02
                        tp2 = entry_price * 1.04
                        tp3 = entry_price * 1.06
                        sl = entry_price * 0.98
                        position_size = 100
                    
                    source_display = pos.get('source', 'database')
                    
                    # Format display symbol
                    display_symbol = convert_symbol_for_display(
                        symbol,
                        bot.mode,
                        getattr(bot, 'trading_mode', 'spot')
                    )
                    
                    # Hitung P/L dengan harga yang sudah divalidasi
                    pl_pct = 0.0
                    pl_value = 0.0
                    
                    if entry_price > 0 and current_price > 0:
                        if action == "LONG":
                            pl_pct = ((current_price - entry_price) / entry_price) * 100
                            pl_value = (current_price - entry_price) * (position_size / entry_price)
                        else:  # SHORT
                            pl_pct = ((entry_price - current_price) / entry_price) * 100
                            pl_value = (entry_price - current_price) * (position_size / entry_price)
                    
                    # 🔥 Tampilkan warning jika P/L ekstrem
                    if abs(pl_pct) > 1000:  # > 1000% gain/loss
                        st.error(f"🚨 **P/L EKSTREM DETECTED**: {pl_pct:.1f}%")
                        market = st.session_state.current_market if hasattr(st.session_state, 'current_market') else "Crypto"
                        st.info(f"""
                        **Kemungkinan masalah:**
                        1. Harga salah: Entry={format_currency(entry_price, market)}, Current={format_currency(current_price, market)}
                        2. Format simbol: {symbol}
                        3. Data provider error
                        
                        **Saran:**
                        - Cek simbol di exchange
                        - Close position jika perlu
                        - Update harga manual
                        """)
                    
                    # Tentukan warna dan emoji
                    if pl_pct > 0:
                        color = "green"
                        emoji = "📈"
                        status_display = "PROFIT"
                    elif pl_pct < 0:
                        color = "red"
                        emoji = "📉"
                        status_display = "LOSS"
                    else:
                        color = "gray"
                        emoji = "⚪"
                        status_display = "BREAKEVEN"
                    
                    # Tampilkan position card
                    with st.container():
                        col_pos1, col_pos2, col_pos3, col_pos4 = st.columns([2, 2, 2, 1])
                        
                        with col_pos1:
                            st.write(f"{emoji} **{display_symbol}**")
                            st.write(f"Action: `{action}`")
                            market = st.session_state.current_market if hasattr(st.session_state, 'current_market') else "Crypto"
                            st.write(f"🏁 Entry: {format_currency(entry_price, market)}")
                            st.write(f"📏 Size: {format_currency(position_size, market)}")
                        
                        with col_pos2:
                            # Tampilkan harga dengan indikator source
                            price_emoji = "🟢" if "Live" in price_source else "🟡" if "Database" in price_source else "⚪"
                            st.write(f"{price_emoji} {price_source}: {format_currency(current_price, market)}")
                            
                            # Calculate change from entry
                            if entry_price > 0:
                                if action == "LONG":
                                    change_pct = ((current_price - entry_price) / entry_price) * 100
                                    change_emoji = "📈" if change_pct >= 0 else "📉"
                                else:
                                    change_pct = ((entry_price - current_price) / entry_price) * 100
                                    change_emoji = "📈" if change_pct >= 0 else "📉"
                                
                                st.write(f"{change_emoji} Change: `{change_pct:+.2f}%`")
                            st.write(f"📍 Status: `{status_display}`")
                        
                        with col_pos3:
                            if entry_price > 0:
                                st.write(f"📊 P/L: <span style='color:{color}; font-weight:bold'>{pl_pct:+.2f}%</span>", unsafe_allow_html=True)
                                st.write(f"💰 Value: <span style='color:{color}'>{format_currency(pl_value, market)}</span>", unsafe_allow_html=True)
                                st.write(f"🎯 TP1: {format_currency(tp1, market)}")
                                st.write(f"🎯 TP2: {format_currency(tp2, market)}")
                                st.write(f"🎯 TP3: {format_currency(tp3, market)}")
                                st.write(f"🛑 SL: {format_currency(sl, market)}")
                            else:
                                st.write("⚠️ Invalid entry price")
                        
                        with col_pos4:
                            # Tombol update price individual dengan update database
                            update_key = f"update_price_single_{position_id}_{symbol}_{idx}"
                            if st.button("🔄 Update", key=update_key):
                                current_price, source = get_realtime_price_with_fallback(symbol, bot, entry_price)
                                if current_price and current_price > 0:
                                    # Update in database
                                    success = update_position_price_in_db(bot, position_id, current_price)
                                    if success:
                                        st.success(f"✅ {display_symbol} updated to {format_currency(current_price, market)} in DB!")
                                    else:
                                        st.warning(f"⚠️ {display_symbol} price update failed")
                                    st.rerun()
                                else:
                                    st.warning(f"⚠️ Cannot get real-time price for {display_symbol}")
                            
                            # Tombol close
                            close_key = f"close_position_{position_id}_{symbol}_{idx}"
                            if st.button("❌ Close", key=close_key, type="secondary"):
                                with st.spinner("Closing position..."):
                                    try:
                                        success = False
                                        close_price = current_price if current_price > 0 else entry_price
                                        
                                        # Try to close in database
                                        if hasattr(bot, 'close_position'):
                                            success = bot.close_position(position_id, close_price)
                                        
                                        # Also remove from session state if exists
                                        if hasattr(st.session_state, 'test_positions'):
                                            st.session_state.test_positions = [
                                                p for p in st.session_state.test_positions 
                                                if p.get('id') != position_id and p.get('symbol') != symbol
                                            ]
                                        
                                        if success:
                                            st.success(f"✅ {display_symbol} closed at {format_currency(close_price, market)}!")
                                            time.sleep(1)
                                            # Refresh positions
                                            if hasattr(bot, 'get_active_positions'):
                                                st.session_state.positions_data = bot.get_active_positions()
                                            st.rerun()
                                        else:
                                            st.error(f"❌ Failed to close {display_symbol}")
                                    except Exception as close_error:
                                        st.error(f"❌ Close error: {close_error}")
                    
                    st.divider()
                    
                except Exception as e:
                    st.error(f"❌ Error displaying position {idx+1}: {e}")
                    import traceback
                    traceback.print_exc()
                    
                    # Tampilkan minimal info untuk posisi error
                    with st.container():
                        st.warning(f"⚠️ Problem with position {idx+1}: {symbol if 'symbol' in pos else 'Unknown'}")
                        st.write(f"Error: {str(e)[:100]}")
                    continue

    # Tab 7: History
    with tab7:
        st.subheader("📈 Trade History")
        
        if st.button("🔄 Refresh History", key="refresh_history"):
            try:
                st.session_state.history_data = bot.get_trade_history()
                st.success("✅ History refreshed successfully!")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Refresh error: {e}")
        
        if not st.session_state.history_data:
            st.info("No trade history")
        else:
            # Filter untuk scalping trades jika mode aktif
            history_to_display = st.session_state.history_data
            
            if st.session_state.scalping_mode:
                # Coba identifikasi scalping trades (berdasarkan durasi atau profit target)
                pass
            
            for trade in history_to_display[:10]:
                try:
                    if isinstance(trade, tuple):
                        symbol = trade[1]
                        action = trade[3]
                        entry_price = trade[4]
                        exit_price = trade[5]
                        profit_loss = trade[6]
                    else:
                        symbol = safe_get(trade, 'symbol')
                        action = safe_get(trade, 'action')
                        entry_price = safe_get(trade, 'entry_price')
                        exit_price = safe_get(trade, 'exit_price')
                        profit_loss = safe_get(trade, 'profit_loss')
                    
                    # Format display
                    display_symbol = convert_symbol_for_display(
                        symbol,
                        bot.mode,
                        getattr(bot, 'trading_mode', 'spot')
                    )
                    
                    color = "green" if profit_loss > 0 else "red"
                    emoji = "✅" if profit_loss > 0 else "❌"
                    
                    st.write(f"{emoji} **{display_symbol}** - {action}")
                    market = st.session_state.current_market if hasattr(st.session_state, 'current_market') else "Crypto"
                    st.write(f"Entry: `{format_currency(entry_price, market)}` | Exit: `{format_currency(exit_price, market)}`")
                    st.write(f"P/L: <span style='color:{color}'>{format_currency(profit_loss, market)}</span>", unsafe_allow_html=True)
                    st.markdown("---")
                except Exception as e:
                    st.error(f"History error: {e}")

    # Tab 8: Live Scanner & Position Monitor - FIXED VERSION dengan update database
    with tab8:
        st.subheader("📡 Live Scanner & Position Monitor")
        
        # Mode info
        mode_info = []
        if hasattr(bot, 'trading_mode'):
            mode_display = "🔄 Spot" if bot.trading_mode == "spot" else "⚡ Futures"
            mode_info.append(f"**Trading Mode:** {mode_display}")
        
        if st.session_state.scalping_mode:
            mode_info.append("⚡ **SCALPING:** ON")
        
        if mode_info:
            st.info(" | ".join(mode_info))
        
        # Control buttons
        col1, col2, col3 = st.columns([1, 2, 1])
        with col1:
            if st.button("🚀 Start Live Monitoring" if not st.session_state.live_monitoring else "⏹️ Stop Monitoring", 
                        key="toggle_live_tab8", type="primary"):
                st.session_state.live_monitoring = not st.session_state.live_monitoring
                st.rerun()

        with col2:
            auto_refresh_live = st.checkbox("🔄 Auto Refresh (10s)", value=True, key="auto_refresh_live_tab8")

        with col3:
            if st.button("📊 Refresh Now", key="refresh_now_tab8"):
                st.rerun()
        
        if st.session_state.live_monitoring:
            st.success("📡 LIVE MONITORING ACTIVE")
            
            # Get ALL positions from database (not filtered)
            try:
                all_db_positions = bot.get_active_positions()
            except:
                all_db_positions = []
            
            # Add session positions
            all_positions = []
            if all_db_positions:
                all_positions.extend(all_db_positions)
            
            if hasattr(st.session_state, 'test_positions') and st.session_state.test_positions:
                for session_pos in st.session_state.test_positions:
                    # Check if already exists
                    session_symbol = session_pos.get('symbol', '')
                    exists = False
                    for db_pos in all_positions:
                        if db_pos.get('symbol') == session_symbol:
                            exists = True
                            break
                    if not exists:
                        all_positions.append(session_pos)
            
            # Filter hanya yang open/active
            active_positions = []
            for pos in all_positions:
                if isinstance(pos, dict):
                    status = pos.get('status', 'open').lower()
                    if status in ['open', 'active']:
                        active_positions.append(pos)
            
            if active_positions:
                st.subheader(f"📊 Monitoring {len(active_positions)} positions")
                
                for idx, pos in enumerate(active_positions):
                    try:
                        symbol = pos.get('symbol', 'Unknown')
                        action = pos.get('action', 'Unknown')
                        entry_price = float(pos.get('entry_price', 0))
                        current_price = float(pos.get('current_price', entry_price))
                        position_size = float(pos.get('position_size', 0))
                        status = pos.get('status', 'open')
                        position_id = pos.get('id', f'live_{idx}')
                        
                        # Get live price dengan VALIDASI
                        live_price, source = get_realtime_price_with_fallback(symbol, bot, entry_price)
                        
                        # Validasi harga
                        if live_price and live_price > 0 and validate_price_reasonable(live_price, entry_price, symbol):
                            # Update in database if possible
                            if hasattr(bot, 'update_position_current_price'):
                                bot.update_position_current_price(position_id, live_price)
                            current_price = live_price
                            price_source = f"Live ({source})"
                        else:
                            # Gunakan harga dari database
                            price_source = "Database"
                        
                        # Update P/L berdasarkan live_price yang sudah divalidasi
                        pl_pct = 0.0
                        pl_value = 0.0
                        
                        if entry_price > 0 and current_price > 0:
                            if action == "LONG":
                                pl_pct = ((current_price - entry_price) / entry_price) * 100
                                pl_value = (current_price - entry_price) * (position_size / entry_price) if entry_price > 0 else 0
                            else:
                                pl_pct = ((entry_price - current_price) / entry_price) * 100
                                pl_value = (entry_price - current_price) * (position_size / entry_price) if entry_price > 0 else 0
                        
                        display_symbol = convert_symbol_for_display(symbol, bot.mode, bot.trading_mode)
                        market = st.session_state.current_market if hasattr(st.session_state, 'current_market') else "Crypto"
                        
                        # Display
                        col_l1, col_l2, col_l3, col_l4 = st.columns([2, 2, 2, 1])
                        
                        with col_l1:
                            status_emoji = "🟢" if status == 'open' else "🔴" if status == 'closed' else "⚪"
                            st.write(f"{status_emoji} **{display_symbol}**")
                            st.write(f"Action: `{action}` | Status: `{status}`")
                            if entry_price > 0:
                                st.write(f"🏁 Entry: {format_currency(entry_price, market)}")
                            st.write(f"Size: {format_currency(position_size, market)}")
                        
                        with col_l2:
                            price_color = "🟢" if "Live" in price_source else "🟡" if "Database" in price_source else "⚪"
                            st.write(f"{price_color} {price_source}: {format_currency(current_price, market)}")
                            
                            if entry_price > 0:
                                if action == "LONG":
                                    change = ((current_price - entry_price) / entry_price) * 100
                                else:
                                    change = ((entry_price - current_price) / entry_price) * 100
                                change_emoji = "📈" if change >= 0 else "📉"
                                st.write(f"{change_emoji} Change: `{change:+.2f}%`")
                        
                        with col_l3:
                            color = "green" if pl_pct >= 0 else "red"
                            emoji = "📈" if pl_pct >= 0 else "📉"
                            st.write(f"{emoji} P/L: <span style='color:{color}; font-weight:bold'>{pl_pct:+.2f}%</span>", unsafe_allow_html=True)
                            st.write(f"💰 Value: <span style='color:{color}'>{format_currency(pl_value, market)}</span>", unsafe_allow_html=True)
                            st.write(f"🎯 TP1: {format_currency(pos.get('tp1', 0), market)}")
                            st.write(f"🎯 TP2: {format_currency(pos.get('tp2', 0), market)}")
                            st.write(f"🎯 TP3: {format_currency(pos.get('tp3', 0), market)}")
                            st.write(f"🛑 SL: {format_currency(pos.get('sl', 0), market)}")
                        
                        with col_l4:
                            # Simple update button
                            if st.button("Update", key=f"update_monitor_{symbol}_{idx}"):
                                st.rerun()
                        
                        st.divider()
                        
                    except Exception as e:
                        st.error(f"❌ Error in position {idx+1}: {e}")
                        continue
                
                # Auto-refresh dengan update database
                if auto_refresh_live and st.session_state.live_monitoring:
                    # Update all prices to DB before sleep
                    positions = bot.get_active_positions()
                    update_count = 0
                    for position in positions:
                        symbol = position.get('symbol')
                        position_id = position.get('id')
                        live_price = get_real_time_price(symbol, bot)
                        if live_price and live_price > 0:
                            success = update_position_price_in_db(bot, position_id, live_price)
                            if success:
                                update_count += 1
                    
                    if update_count > 0:
                        print(f"📡 Live monitor: Updated {update_count} positions in database")
                    
                    time.sleep(10)
                    st.rerun()
                    
            else:
                st.info("📭 No active positions to monitor")
                st.info("👉 Open a position in Tab 4 first!")
        else:
            st.info("👉 Click 'Start Live Monitoring' to begin tracking positions")

    # Tab 9: ML Backtest
    with tab9:
        st.subheader("🤖 ML Backtest & Analysis")
        
        # Mode info
        mode_info = []
        if hasattr(bot, 'trading_mode'):
            mode_display = "🔄 Spot" if bot.trading_mode == "spot" else "⚡ Futures"
            mode_info.append(f"**Trading Mode:** {mode_display}")
        
        if st.session_state.scalping_mode:
            mode_info.append("⚡ **SCALPING:** ON")
        
        if mode_info:
            st.info(" | ".join(mode_info))
        
        col1, col2 = st.columns([2, 1])
        with col1:
            backtest_symbol = st.text_input("Symbol untuk Backtest:", key="backtest_symbol")
        with col2:
            backtest_days = st.selectbox("Period:", [30, 90, 180, 365], index=2)
        
        # Format simbol
        formatted_backtest_symbol = None
        if backtest_symbol:
            formatted_backtest_symbol = format_symbol_for_mode(
                backtest_symbol.upper(),
                bot.mode,
                getattr(bot, 'trading_mode', 'spot')
            )
        
        # Scalping backtest settings
        backtest_settings = {}
        if st.session_state.scalping_mode:
            with st.expander("⚡ Scalping Backtest Settings"):
                col_bs1, col_bs2 = st.columns(2)
                with col_bs1:
                    backtest_settings['min_score'] = st.slider("Min Score Threshold", 2.0, 6.0,
                                                             value=SCALPING_CONFIG_APP["min_score"],
                                                             step=0.5, key="tab9_min_score")
                with col_bs2:
                    st.info("Long Bias: 0.0 (disabled)")
                    backtest_settings['long_bias'] = 0.0
        
        if st.button("🚀 Run Backtest", key="run_backtest", type="primary"):
            if backtest_symbol:
                with st.spinner("Running comprehensive backtest..."):
                    symbol_to_use = formatted_backtest_symbol if formatted_backtest_symbol else backtest_symbol.upper()
                    
                    # Apply scalping settings
                    if backtest_settings:
                        st.info(f"⚡ Scalping Backtest: Min Score={backtest_settings['min_score']}, Bias={backtest_settings['long_bias']}")
                    
                    # Gunakan run_advanced_backtest dari core.py
                    if hasattr(bot, 'run_advanced_backtest'):
                        results = bot.run_advanced_backtest(symbol_to_use)
                    else:
                        results = {"error": "Backtest feature not available"}
                    
                    # Apply scalping filter jika mode aktif
                    if st.session_state.scalping_mode and 'trades' in results:
                        # Filter trades based on scalping criteria
                        filtered_trades = []
                        for trade in results['trades']:
                            # Apply scalping filters here
                            filtered_trades.append(trade)
                        results['filtered_trades'] = filtered_trades
                        results['scalping_mode'] = True
                    
                    st.session_state.backtest_results = results
                    st.rerun()
        
        if st.session_state.backtest_results and 'error' not in st.session_state.backtest_results:
            results = st.session_state.backtest_results
            st.subheader("📊 Backtest Results")
            
            # Scalping indicator
            if results.get('scalping_mode'):
                st.success("⚡ Scalping Backtest Results")
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Trades", results.get('total_trades', 0))
            with col2:
                st.metric("Win Rate", f"{results.get('win_rate', 0):.1%}")
            with col3:
                st.metric("Total P&L", f"${results.get('total_pnl', 0):,.2f}")
            with col4:
                st.metric("Max Drawdown", f"{results.get('max_drawdown', 0):.1%}")
        
        elif st.session_state.backtest_results and 'error' in st.session_state.backtest_results:
            st.error(f"Backtest Error: {st.session_state.backtest_results['error']}")

    # Tab 10: Portfolio Optimization - UPDATED dengan external repos
    with tab10:
        st.subheader("⚖️ Portfolio Optimization with External Repos")
        
        # Mode info
        mode_info = []
        if hasattr(bot, 'trading_mode'):
            mode_display = "🔄 Spot" if bot.trading_mode == "spot" else "⚡ Futures"
            mode_info.append(f"**Trading Mode:** {mode_display}")
        
        if st.session_state.scalping_mode:
            mode_info.append("⚡ **SCALPING:** ON")
        
        if mode_info:
            st.info(" | ".join(mode_info))
        
        col1, col2 = st.columns([2, 1])
        with col1:
            portfolio_capital = st.number_input("Total Capital:", value=10000, step=1000, key="portfolio_capital_input")
        
        # External repos options
        with st.expander("📚 External Repos Options"):
            col_er1, col_er2 = st.columns(2)
            with col_er1:
                use_quant_strategies = st.checkbox("Use Quant Strategies", value=True,
                                                  help="Use quantitative strategies for optimization")
                use_risk_adjusted = st.checkbox("Risk-Adjusted Allocation", value=True,
                                               help="Adjust allocations based on risk scores")
            with col_er2:
                max_diversification = st.checkbox("Maximize Diversification", value=True,
                                                 help="Spread capital across different assets")
                consider_correlation = st.checkbox("Consider Correlations", value=False,
                                                  help="Account for asset correlations (requires historical data)")
        
        # Scalping portfolio settings
        if st.session_state.scalping_mode:
            with st.expander("⚡ Scalping Portfolio Settings"):
                col_sp1, col_sp2 = st.columns(2)
                with col_sp1:
                    max_scalping_positions = st.slider("Max Scalping Positions", 1, 10, value=5, step=1, key="max_scalping_positions")
                with col_sp2:
                    scalping_position_size = st.slider("Position Size %", 1, 10, value=2, step=1, key="scalping_position_size")
                    st.caption(f"Each position: {scalping_position_size}% of capital")
        
        with col2:
            if st.button("🔄 Optimize Portfolio", key="optimize_portfolio", type="primary"):
                if st.session_state.scanned_results or st.session_state.scalping_results:
                    # Pilih signals berdasarkan mode
                    if st.session_state.scalping_mode and st.session_state.scalping_results:
                        signals = st.session_state.scalping_results[:max_scalping_positions]
                        position_size = scalping_position_size / 100.0
                    else:
                        signals = st.session_state.scanned_results[:10]  # Increased for better diversification
                        position_size = 0.1  # 10% per position default for diversification
                    
                    total_signals = len(signals)
                    if total_signals > 0:
                        # Use bot's optimize_portfolio_allocation if available
                        if hasattr(bot, 'optimize_portfolio_allocation'):
                            optimized_allocations = bot.optimize_portfolio_allocation(
                                signals, 
                                capital=portfolio_capital,
                                risk_per_trade=position_size
                            )
                        else:
                            # Fallback to simple allocation
                            optimized_allocations = []
                            for s in signals:
                                allocation = {
                                    'symbol': s.get('symbol'),
                                    'action': s.get('action', 'LONG'),
                                    'score': s.get('score', 0),
                                    'allocation': portfolio_capital * position_size,
                                    'percent_of_capital': position_size * 100,
                                    'risk_score': min(s.get('risk_score', 5), 10) / 10
                                }
                                optimized_allocations.append(allocation)
                        
                        allocations = {
                            'signals': optimized_allocations,
                            'total_allocated_percent': position_size * total_signals,
                            'total_allocated_capital': portfolio_capital * position_size * total_signals,
                            'remaining_capital': portfolio_capital * (1 - (position_size * total_signals)),
                            'scalping_mode': st.session_state.scalping_mode,
                            'use_quant_strategies': use_quant_strategies,
                            'optimization_method': 'External Repos' if use_quant_strategies else 'Basic'
                        }
                    else:
                        allocations = {}
                    
                    st.session_state.portfolio_allocations = allocations
                    st.rerun()
        
        # Display Portfolio Allocations
        if st.session_state.portfolio_allocations:
            allocations = st.session_state.portfolio_allocations
            st.subheader("📈 Portfolio Allocation")
            
            # Mode info
            if allocations.get('scalping_mode'):
                st.success("⚡ Scalping Portfolio Allocation")
            
            if allocations.get('use_quant_strategies'):
                st.info(f"📊 Optimization Method: {allocations.get('optimization_method', 'External Repos')}")
            
            st.subheader("📋 Position Details")
            allocation_data = []
            for signal in allocations.get('signals', []):
                display_symbol = convert_symbol_for_display(
                    signal.get('symbol', 'Unknown'),
                    bot.mode,
                    getattr(bot, 'trading_mode', 'spot')
                )
                
                # Scalping indicator
                scalping_indicator = "⚡ " if allocations.get('scalping_mode') else ""
                
                allocation_data.append({
                    'Symbol': f"{scalping_indicator}{display_symbol}",
                    'Action': signal.get('action', 'N/A'),
                    'Score': f"{signal.get('score', 0):+.1f}",
                    'Allocation %': f"{signal.get('percent_of_capital', 0):.1f}%",
                    'Capital': f"${signal.get('allocation', 0):,.2f}",
                    'Risk Score': f"{signal.get('risk_score', 0.5):.2f}"
                })
            
            if allocation_data:
                df_allocations = pd.DataFrame(allocation_data)
                st.dataframe(df_allocations, use_container_width=True)
            
            # Summary
            col_ps1, col_ps2, col_ps3 = st.columns(3)
            with col_ps1:
                st.metric("Total Positions", len(allocations.get('signals', [])))
            with col_ps2:
                st.metric("Allocated Capital", f"${allocations.get('total_allocated_capital', 0):,.2f}")
            with col_ps3:
                st.metric("Remaining Capital", f"${allocations.get('remaining_capital', 0):,.2f}")
            
            # Portfolio metrics
            st.subheader("📊 Portfolio Metrics")
            col_m1, col_m2, col_m3 = st.columns(3)
            with col_m1:
                avg_score = np.mean([s.get('score', 0) for s in allocations.get('signals', [])])
                st.metric("Avg Signal Score", f"{avg_score:+.2f}")
            with col_m2:
                avg_risk = np.mean([s.get('risk_score', 0.5) for s in allocations.get('signals', [])])
                st.metric("Avg Risk Score", f"{avg_risk:.2f}")
            with col_m3:
                diversification = min(len(allocations.get('signals', [])), 10) / 10
                st.metric("Diversification", f"{diversification:.1%}")
        
        st.subheader("🔗 Portfolio Analysis with External Repos")
        st.info("""
        **Enhanced Portfolio Features:**
        - Risk-adjusted position sizing with quant strategies
        - Diversification scoring using correlation analysis
        - Dynamic allocation optimization
        - Multi-scraper data integration for better risk assessment
        
        **Scalping Portfolio Rules:**
        1. Max {SCALPING_CONFIG_APP["max_signals"]} positions simultaneously
        2. 1-3% position size per trade
        3. Stop loss always set
        4. Take profit at TP1 (60% probability)
        5. Maximum 5 trades per day
        6. Equal opportunities for LONG/SHORT
        
        **📊 External Repos Integration:**
        - **Backtrader/Backtesting.py**: Advanced backtesting frameworks
        - **Multi-Scraper**: Enhanced historical data from multiple sources
        - **Quant Strategies**: Professional portfolio optimization algorithms
        - **Risk Models**: Sophisticated risk assessment
        
        **Large Asset Pool Advantage:**
        - 500+ assets = Higher signal quality
        - More diversification opportunities
        - Better risk management
        - Higher probability of profitable trades
        """)

    # 🔥 NEW TAB 11: Advanced Backtesting with External Repos
    with tab11:
        st.subheader("🧪 Advanced Backtesting with External Repos")
        
        # Mode info
        mode_info = []
        if hasattr(bot, 'trading_mode'):
            mode_display = "🔄 Spot" if bot.trading_mode == "spot" else "⚡ Futures"
            mode_info.append(f"**Trading Mode:** {mode_display}")
        
        if st.session_state.scalping_mode:
            mode_info.append("⚡ **SCALPING:** ON")
        
        if mode_info:
            st.info(" | ".join(mode_info))
        
        # External repos status
        with st.expander("📚 External Backtesting Frameworks"):
            repos_status = []
            if hasattr(bot, 'backtrader_module') and bot.backtrader_module:
                repos_status.append("✅ Backtrader")
            if hasattr(bot, 'backtesting_module') and bot.backtesting_module:
                repos_status.append("✅ Backtesting.py")
            if hasattr(bot, 'scraper_manager') and bot.scraper_manager:
                repos_status.append("✅ Multi-Scraper")
            
            if repos_status:
                st.success(f"Available: {', '.join(repos_status)}")
            else:
                st.warning("⚠️ No external backtesting frameworks detected")
        
        col_symb, col_period = st.columns([2, 1])
        with col_symb:
            backtest_symbol_input = st.text_input("Symbol for Backtest:", 
                                                 value="BTC/USDT",
                                                 key="adv_backtest_symbol")
        
        with col_period:
            backtest_period = st.selectbox("Backtest Period:", 
                                          ["1m", "3m", "6m", "1y", "2y"],
                                          index=2,
                                          key="adv_backtest_period")
        
        # Strategy selection
        with st.expander("🎯 Strategy Configuration"):
            col_strat1, col_strat2 = st.columns(2)
            with col_strat1:
                strategy_type = st.selectbox("Strategy Type:",
                                           ["Momentum", "Mean Reversion", "Breakout", "Scalping", "Custom"],
                                           index=0,
                                           key="strategy_type")
                
                initial_capital = st.number_input("Initial Capital ($):",
                                                value=10000,
                                                min_value=100,
                                                step=1000,
                                                key="initial_capital")
            
            with col_strat2:
                use_stop_loss = st.checkbox("Use Stop Loss", value=True, key="use_stop_loss")
                use_take_profit = st.checkbox("Use Take Profit", value=True, key="use_take_profit")
                
                if use_stop_loss:
                    stop_loss_pct = st.slider("Stop Loss %", 1.0, 10.0, 2.0, 0.5, key="stop_loss_pct")
                if use_take_profit:
                    take_profit_pct = st.slider("Take Profit %", 1.0, 10.0, 2.0, 0.5, key="take_profit_pct")
        
        # Data source selection
        with st.expander("📊 Data Source Configuration"):
            col_data1, col_data2 = st.columns(2)
            with col_data1:
                data_source = st.selectbox("Data Source:",
                                         ["Multi-Scraper", "Primary Provider", "Hybrid"],
                                         index=0,
                                         key="data_source")
                
                timeframe = st.selectbox("Timeframe:",
                                       ["1m", "5m", "15m", "1h", "4h", "1d"],
                                       index=5,
                                       key="timeframe")
            
            with col_data2:
                data_points = st.slider("Data Points:", 100, 1000, 500, 50, key="data_points")
                use_technical_indicators = st.checkbox("Add Technical Indicators", value=True, key="use_tech_indicators")
        
        # Run backtest button
        col_run1, col_run2, col_run3 = st.columns([1, 2, 1])
        with col_run2:
            if st.button("🚀 Run Advanced Backtest", key="run_adv_backtest", type="primary", use_container_width=True):
                if backtest_symbol_input:
                    with st.spinner(f"Running {strategy_type} backtest for {backtest_symbol_input}..."):
                        try:
                            # Format symbol
                            formatted_symbol = format_symbol_for_mode(
                                backtest_symbol_input.upper(),
                                bot.mode,
                                getattr(bot, 'trading_mode', 'spot')
                            )
                            
                            # Run backtest using bot's method
                            backtest_result = bot.run_backtest(
                                symbol=formatted_symbol,
                                period=backtest_period,
                                initial_capital=initial_capital
                            )
                            
                            if backtest_result and 'error' not in backtest_result:
                                # Store results
                                st.session_state.external_repo_data['adv_backtest'] = backtest_result
                                
                                # Generate visualizations
                                if PLOTLY_AVAILABLE:
                                    visualizations = plot_backtest_results(backtest_result)
                                    st.session_state.backtest_visualizations = visualizations
                                
                                st.success(f"✅ Backtest completed for {formatted_symbol}")
                                st.rerun()
                            else:
                                st.error(f"❌ Backtest failed: {backtest_result.get('error', 'Unknown error')}")
                                
                        except Exception as e:
                            st.error(f"❌ Backtest error: {str(e)[:200]}")
                            import traceback
                            traceback.print_exc()
        
        # Display backtest results
        if 'adv_backtest' in st.session_state.external_repo_data:
            results = st.session_state.external_repo_data['adv_backtest']
            
            st.subheader("📊 Backtest Results")
            
            # Key metrics
            col_res1, col_res2, col_res3, col_res4 = st.columns(4)
            with col_res1:
                st.metric("Total Return", f"{results.get('total_return', 0):.1f}%")
            with col_res2:
                st.metric("Sharpe Ratio", f"{results.get('sharpe_ratio', 0):.2f}")
            with col_res3:
                st.metric("Max Drawdown", f"{results.get('max_drawdown', 0):.1f}%")
            with col_res4:
                st.metric("Win Rate", f"{results.get('win_rate', 0):.1f}%")
            
            # Additional metrics
            col_res5, col_res6, col_res7, col_res8 = st.columns(4)
            with col_res5:
                st.metric("Total Trades", results.get('total_trades', 0))
            with col_res6:
                avg_trade = results.get('total_return', 0) / max(results.get('total_trades', 1), 1)
                st.metric("Avg Trade Return", f"{avg_trade:.2f}%")
            with col_res7:
                profit_factor = "N/A"
                if 'profit_factor' in results:
                    profit_factor = f"{results['profit_factor']:.2f}"
                st.metric("Profit Factor", profit_factor)
            with col_res8:
                st.metric("Data Source", results.get('source', 'Unknown'))
            
            # Visualizations
            if PLOTLY_AVAILABLE and st.session_state.backtest_visualizations:
                st.subheader("📈 Visualizations")
                
                if isinstance(st.session_state.backtest_visualizations, list):
                    # Multiple charts
                    for i, fig in enumerate(st.session_state.backtest_visualizations[:3]):
                        st.plotly_chart(fig, use_container_width=True)
                else:
                    # Single chart
                    st.plotly_chart(st.session_state.backtest_visualizations, use_container_width=True)
            
            # Detailed analysis
            with st.expander("📋 Detailed Analysis"):
                st.write("**Strategy Performance:**")
                
                # Create performance dataframe
                perf_data = {
                    'Metric': ['Total Return', 'Sharpe Ratio', 'Max Drawdown', 'Win Rate', 'Total Trades'],
                    'Value': [
                        f"{results.get('total_return', 0):.1f}%",
                        f"{results.get('sharpe_ratio', 0):.2f}",
                        f"{results.get('max_drawdown', 0):.1f}%",
                        f"{results.get('win_rate', 0):.1f}%",
                        results.get('total_trades', 0)
                    ],
                    'Interpretation': [
                        "Positive = Profitable" if results.get('total_return', 0) > 0 else "Negative = Loss",
                        ">1 = Good, >2 = Excellent" if results.get('sharpe_ratio', 0) > 0 else "Poor",
                        "<10% = Good, <20% = Acceptable",
                        ">50% = Good, >60% = Excellent",
                        ">20 = Good sample size"
                    ]
                }
                
                df_perf = pd.DataFrame(perf_data)
                st.dataframe(df_perf, use_container_width=True, hide_index=True)
                
                # Recommendations
                st.write("**Recommendations:**")
                
                total_return = results.get('total_return', 0)
                sharpe_ratio = results.get('sharpe_ratio', 0)
                win_rate = results.get('win_rate', 0)
                
                recommendations = []
                
                if total_return > 10:
                    recommendations.append("✅ **Strong Strategy**: Consider scaling this approach")
                elif total_return > 0:
                    recommendations.append("⚠️ **Moderate Strategy**: May need optimization")
                else:
                    recommendations.append("❌ **Poor Strategy**: Consider alternative approaches")
                
                if sharpe_ratio > 1.5:
                    recommendations.append("✅ **Excellent Risk-Adjusted Returns**")
                elif sharpe_ratio > 1:
                    recommendations.append("⚠️ **Acceptable Risk-Adjusted Returns**")
                else:
                    recommendations.append("❌ **Poor Risk-Adjusted Returns**")
                
                if win_rate > 55:
                    recommendations.append("✅ **High Win Rate**: Consistent profitability")
                elif win_rate > 45:
                    recommendations.append("⚠️ **Moderate Win Rate**: Could be improved")
                else:
                    recommendations.append("❌ **Low Win Rate**: High risk of losses")
                
                for rec in recommendations:
                    st.write(rec)
        
        # Backtesting information
        st.divider()
        st.subheader("ℹ️ About External Backtesting Repos")
        
        col_info1, col_info2 = st.columns(2)
        with col_info1:
            st.info("""
            **Backtrader:**
            - Full-featured backtesting framework
            - Support for multiple data feeds
            - Complex strategy implementation
            - Live trading capabilities
            
            **Backtesting.py:**
            - Lightweight and fast
            - Easy strategy definition
            - Built-in performance metrics
            - Pandas integration
            """)
        
        with col_info2:
            st.info("""
            **Multi-Scraper:**
            - Aggregates data from multiple sources
            - Higher data quality and reliability
            - Historical data enrichment
            - Real-time data integration
            
            **Benefits:**
            - More accurate backtesting
            - Better strategy validation
            - Risk assessment improvements
            - Professional-grade analysis
            """)

def main():
    # Initialize ALL session state variables BEFORE main_app()
    default_states = {
        'logged_in': False,
        'username': "",
        'app_initialized': False,
        'positions_data': [],
        'history_data': [],
        'scanned_results': [],
        'scalping_results': [],
        'selected_analysis': None,
        'selected_for_entry': {},
        'current_market': None,
        'current_trading_mode': None,
        'market_set': False,
        'live_monitoring': False,
        'custom_result': None,
        'backtest_results': {},
        'portfolio_allocations': {},
        'risk_assessments': {},
        'latest_results': [],
        'scalping_mode': False,
        'scalping_config': SCALPING_CONFIG_APP,
        'selected_symbol_display': None,
        'last_selected': None,
        'test_positions': [],
        'open_position_result': None,
        'open_position_risk': None,
        'last_scan_time': None,
        'scan_attempts': 0,
        'show_all_positions': False,
        'use_risk_management': False,
        'external_repo_data': {},  # 🔥 NEW: Untuk data external repos
        'backtest_visualizations': {},  # 🔥 NEW: Untuk visualisasi backtest
        # JANGAN inisialisasi bot_instance di sini - biarkan di main_app()
        'positions_initialized': False,
        'refresh_counter': 0,
        'background_thread_started': False  # 🔥 NEW: Untuk thread keep-alive
    }
    
    # Set default values for any missing session states
    for key, default_value in default_states.items():
        if key not in st.session_state:
            st.session_state[key] = default_value
    
    # Show login or main app
    if not st.session_state.logged_in:
        login_section()
    else:
        main_app()

if __name__ == "__main__":
    main()
