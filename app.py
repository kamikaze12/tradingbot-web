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

# ✅ FIX: Add the project root to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
# Tambahkan folder bot ke path Python
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "bot"))
# Try to import plotly
try:
    import plotly.graph_objects as go
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False

# ============================================
# ENHANCED BOT IMPORT - FIXED VERSION
# ============================================
def import_trading_bot():
    """Import TradingBot dari core.py - FIXED DATABASE CONNECTION"""
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
        
        # Last resort: buat dummy class dengan database connection
        print("⚠️ Creating TradingBot with database connection")
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
                
                print("⚠️ Using TradingBotWithDB - limited functionality")
            
            def set_mode(self, mode):
                self.mode = mode
                return True
            
            def get_popular_assets(self, limit=100):
                return []
            
            def scan_potential_assets(self, limit=25):
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
        
        print("✅ TradingBot initialization completed")
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

# ====================================
# SCALPING CONFIGURATION FOR APP - PERBAIKAN
# ====================================

SCALPING_CONFIG_APP = {
    "timeframe": "5m",            # 5 menit untuk scalping
    "lookback": 150,              # ~12.5 jam data
    "min_score": 2.5,             # 🔥 PERBAIKAN: Turun dari 3.0 ke 2.5
    "long_bias": 0.0,             # 🔥 PERBAIKAN: Ubah dari 0.3 ke 0.0 (no bias)
    "max_signals": 15,            # 🔥 PERBAIKAN: Tambah dari 10 ke 15
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
    users = {"muraga": "namikaze", "user2": "password2", "user3": "password3", "admin": "admin123"}
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
    
    with st.expander("ℹ️ Test Accounts"):
        st.write("""
        **Available test accounts:**
        - Username: `muraga` | Password: `namikaze`
        - Username: `user2` | Password: `password2` 
        - Username: `user3` | Password: `password3`
        - Username: `admin` | Password: `admin123`
        """)

def safe_get(data, key, default=0):
    """Safe dictionary access dengan fallback"""
    if isinstance(data, dict):
        return data.get(key, default)
    return default

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
                                print(f"✅ Real-time price for {symbol}: ${price}")
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
                            print(f"💰 Real-time price for {symbol}: ${price}")
                            return price
        
        # Fallback: coba dari method lain
        if hasattr(bot, 'get_current_price'):
            price = bot.get_current_price(symbol)
            if price and price > 0:
                print(f"✅ Got current price from bot method: ${price}")
                return price
        
        return None
    except Exception as e:
        print(f"❌ Error getting real-time price for {symbol}: {e}")
        return None

def get_realtime_price_with_fallback(symbol, bot):
    """Get real-time price with fallback to cached price"""
    try:
        # Try to get real-time price
        realtime_price = get_real_time_price(symbol, bot)
        
        if realtime_price is not None and realtime_price > 0:
            return realtime_price, "Live"
        
        # Fallback to database price
        positions = bot.get_active_positions()
        for pos in positions:
            if isinstance(pos, dict) and pos.get('symbol') == symbol and pos.get('current_price'):
                return pos.get('current_price'), "Database"
        
        return None, "None"
    except Exception as e:
        print(f"❌ Error in get_realtime_price_with_fallback: {e}")
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
    
    if tp1 <= 0 or tp1 == current_price:
        if action == "LONG":
            tp1 = current_price * 1.02
        elif action == "SHORT":
            tp1 = current_price * 0.98
    
    if tp2 <= 0 or tp2 == current_price:
        if action == "LONG":
            tp2 = current_price * 1.05
        elif action == "SHORT":
            tp2 = current_price * 0.95
    
    if tp3 <= 0 or tp3 == current_price:
        if action == "LONG":
            tp3 = current_price * 1.10
        elif action == "SHORT":
            tp3 = current_price * 0.90
    
    if sl <= 0 or sl == current_price:
        if action == "LONG":
            sl = current_price * 0.98
        elif action == "SHORT":
            sl = current_price * 1.02
    
    analysis['tp1'] = tp1
    analysis['tp2'] = tp2
    analysis['tp3'] = tp3
    analysis['sl'] = sl
    
    return analysis

def update_position_price_in_db(bot, position_id, current_price):
    """Update position current price in database with logging"""
    if hasattr(bot, 'update_position_current_price'):
        try:
            success = bot.update_position_current_price(position_id, current_price)
            if success:
                print(f"✅ Updated DB price for position {position_id}: ${current_price}")
                return True
            else:
                print(f"⚠️ DB update failed for {position_id}")
                return False
        except Exception as e:
            print(f"❌ DB update error: {e}")
            return False
    print("⚠️ No update method in bot")
    return False

def main_app():
    # Initialize bot jika belum
    if 'bot_instance' not in st.session_state:
        bot = init_bot()
        if bot is None:
            st.error("❌ Failed to initialize TradingBot. Please check console for errors.")
            st.stop()
        st.session_state.bot_instance = bot
    else:
        bot = st.session_state.bot_instance
    
    # Set default mode jika belum
    if bot.mode is None:
        bot.mode = "crypto"
    
    # Sidebar - Market Mode Selector
    with st.sidebar:
        st.title("⚙️ Settings")
        
        # Market Mode
        market_type = st.selectbox(
            "Market Type:",
            ["crypto", "us_stocks", "saham_id", "forex", "forex_gold", "scalping"],
            index=0,
            key="market_type_selector"
        )
        
        if market_type != st.session_state.get('current_market'):
            bot.set_mode(market_type)
            st.session_state.current_market = market_type
            st.session_state.market_set = True
            st.session_state.scalping_mode = (market_type == "scalping")
            st.rerun()
        
        # Trading Mode
        trading_mode = st.radio(
            "Trading Mode:",
            ["spot", "futures"],
            index=0 if bot.trading_mode == "spot" else 1,
            key="trading_mode_selector"
        )
        
        if trading_mode != st.session_state.get('current_trading_mode'):
            bot.set_trading_mode(trading_mode)
            st.session_state.current_trading_mode = trading_mode
            st.rerun()
        
        # Scalping Toggle - Independent
        scalping_toggle = st.checkbox("⚡ Enable Scalping Mode", value=st.session_state.scalping_mode)
        
        if scalping_toggle != st.session_state.scalping_mode:
            st.session_state.scalping_mode = scalping_toggle
            if scalping_toggle:
                bot.set_mode("scalping")
                st.session_state.current_market = "scalping"
            else:
                bot.set_mode("crypto")
                st.session_state.current_market = "crypto"
            st.rerun()
        
        # Scalping Config jika mode aktif
        if st.session_state.scalping_mode:
            with st.expander("⚡ Scalping Settings"):
                col_s1, col_s2 = st.columns(2)
                with col_s1:
                    st.session_state.scalping_config["min_score"] = st.slider(
                        "Min Score", 2.0, 6.0,
                        value=SCALPING_CONFIG_APP["min_score"],
                        step=0.5, key="scalping_min_score"
                    )
                with col_s2:
                    st.info("Long Bias: 0.0 (disabled)")
        
        st.markdown("---")
        st.caption(f"Logged in as: {st.session_state.username}")
        if st.button("Logout"):
            st.session_state.logged_in = False
            st.rerun()
    
    # Main Tabs
    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9, tab10 = st.tabs([
        "🏠 Dashboard",
        "🔍 Market Scanner",
        "📈 Asset Analysis",
        "🚀 Open Position",
        "⚖️ Risk Assessment",
        "📊 Active Positions",
        "📜 Trade History",
        "📡 Live Scanner",
        "🤖 ML Backtest",
        "⚖️ Portfolio Opt"
    ])
    
    # Tab 1: Dashboard
    with tab1:
        st.title("📊 TradingBot Pro Dashboard")
        
        # Mode info
        mode_info = []
        if hasattr(bot, 'trading_mode'):
            mode_display = "🔄 Spot" if bot.trading_mode == "spot" else "⚡ Futures"
            mode_info.append(f"**Trading Mode:** {mode_display}")
        
        if st.session_state.scalping_mode:
            mode_info.append("⚡ **SCALPING:** ON")
        
        if mode_info:
            st.info(" | ".join(mode_info))
        
        # Provider Health
        health = bot.get_provider_health()
        st.subheader("📡 System Status")
        col_h1, col_h2, col_h3 = st.columns(3)
        with col_h1:
            st.metric("Provider", health.get('provider_type', 'unknown').upper())
        with col_h2:
            status_color = "🟢" if health.get('status') == 'active' else "🟡"
            st.metric("Status", f"{status_color} {health.get('status', 'unknown')}")
        with col_h3:
            st.metric("Exchange", health.get('active_exchange', 'N/A'))
        
        # Quick Scan
        st.subheader("🔍 Quick Market Scan")
        if st.button("🚀 Run Quick Scan", key="quick_scan", type="primary"):
            with st.spinner("Scanning market..."):
                if st.session_state.scalping_mode:
                    signals = bot.scan_potential_assets(limit=SCALPING_CONFIG_APP["max_signals"])
                    st.session_state.scalping_results = signals
                else:
                    signals = bot.scan_potential_assets(limit=10)
                    st.session_state.scanned_results = signals
                
                st.session_state.latest_results = signals
                st.rerun()
        
        if st.session_state.latest_results:
            st.subheader("📈 Latest Signals")
            for signal in st.session_state.latest_results[:5]:
                try:
                    symbol = signal.get('symbol', 'Unknown')
                    action = signal.get('action', 'NEUTRAL')
                    score = signal.get('score', 0)
                    display_symbol = convert_symbol_for_display(symbol, bot.mode, bot.trading_mode)
                    scalping_indicator = "⚡ " if st.session_state.scalping_mode else ""
                    emoji = "📈" if action == "LONG" else "📉" if action == "SHORT" else "⚖️"
                    color = "green" if action == "LONG" else "red" if action == "SHORT" else "gray"
                    st.write(f"{emoji} **{scalping_indicator}{display_symbol}**: <span style='color:{color}'>{action}</span> (Score: {score:.1f})", unsafe_allow_html=True)
                except:
                    continue
        
        # Quick Stats
        st.subheader("📊 Quick Stats")
        col_q1, col_q2, col_q3 = st.columns(3)
        with col_q1:
            st.metric("Active Positions", len(bot.get_active_positions()))
        with col_q2:
            st.metric("Total Trades (History)", len(bot.get_trade_history()))
        with col_q3:
            st.metric("Win Rate", "N/A")  # Placeholder
        
        # Dashboard Notes
        st.info("""
        **Dashboard Features:**
        - Real-time market monitoring
        - Quick signal generation
        - System health checks
        - Performance metrics
        
        **Scalping Dashboard Rules:**
        1. Focus on high-liquidity assets
        2. Strict volatility filters
        3. Neutral bias (LONG/SHORT equal)
        4. Real data only
        """)

    # Tab 2: Market Scanner
    with tab2:
        st.subheader("🔍 Market Scanner")
        
        # Mode info
        mode_info = []
        if hasattr(bot, 'trading_mode'):
            mode_display = "🔄 Spot" if bot.trading_mode == "spot" else "⚡ Futures"
            mode_info.append(f"**Trading Mode:** {mode_display}")
        
        if st.session_state.scalping_mode:
            mode_info.append("⚡ **SCALPING:** ON")
        
        if mode_info:
            st.info(" | ".join(mode_info))
        
        col_scan1, col_scan2 = st.columns([2,1])
        with col_scan1:
            scan_limit = st.slider("Scan Limit:", 5, 50, 10, step=5, key="scan_limit")
        with col_scan2:
            if st.button("🚀 Start Scan", key="start_scan", type="primary"):
                st.session_state.last_scan_time = time.time()
                st.session_state.scan_attempts += 1
                
                with st.spinner("Scanning potential assets..."):
                    try:
                        if st.session_state.scalping_mode:
                            signals = bot.scan_potential_assets(limit=SCALPING_CONFIG_APP["max_signals"])
                            st.session_state.scalping_results = signals
                        else:
                            signals = bot.scan_potential_assets(limit=scan_limit)
                            st.session_state.scanned_results = signals
                        
                        if signals:
                            st.success(f"✅ Found {len(signals)} potential signals!")
                        else:
                            st.warning("⚠️ No signals found. Try adjusting parameters.")
                    except Exception as e:
                        st.error(f"❌ Scan error: {e}")
                        st.session_state.scan_attempts += 1  # Increment attempt on error
                
                st.rerun()
        
        # Display Scan Results
        if st.session_state.scalping_mode and st.session_state.scalping_results:
            results = st.session_state.scalping_results
            st.success("⚡ Scalping Scan Results")
        elif st.session_state.scanned_results:
            results = st.session_state.scanned_results
            st.success("📊 Standard Scan Results")
        else:
            results = []
        
        if results:
            for idx, signal in enumerate(results):
                try:
                    symbol = signal.get('symbol', 'Unknown')
                    action = signal.get('action', 'NEUTRAL')
                    score = signal.get('score', 0)
                    
                    # Format display
                    display_symbol = convert_symbol_for_display(
                        symbol,
                        bot.mode,
                        bot.trading_mode
                    )
                    
                    scalping_indicator = "⚡ " if st.session_state.scalping_mode else ""
                    
                    emoji = "📈" if action == "LONG" else "📉" if action == "SHORT" else "⚖️"
                    color = "green" if action == "LONG" else "red" if action == "SHORT" else "gray"
                    
                    col_s1, col_s2, col_s3 = st.columns([2,1,1])
                    with col_s1:
                        st.write(f"{emoji} **{scalping_indicator}{display_symbol}**")
                    with col_s2:
                        st.write(f"Action: <span style='color:{color}; font-weight:bold'>{action}</span>", unsafe_allow_html=True)
                    with col_s3:
                        if st.button("🔍 Analyze", key=f"analyze_{idx}"):
                            st.session_state.selected_for_entry = signal
                            st.session_state.selected_analysis = bot.analyze_asset(symbol)
                            st.rerun()
                    
                    st.markdown("---")
                except Exception as e:
                    st.error(f"❌ Signal error: {e}")
                    continue
        else:
            st.info("👉 Run a scan to see potential trading signals!")

    # Tab 3: Asset Analysis
    with tab3:
        st.subheader("📈 Asset Analysis")
        
        # Mode info
        mode_info = []
        if hasattr(bot, 'trading_mode'):
            mode_display = "🔄 Spot" if bot.trading_mode == "spot" else "⚡ Futures"
            mode_info.append(f"**Trading Mode:** {mode_display}")
        
        if st.session_state.scalping_mode:
            mode_info.append("⚡ **SCALPING:** ON")
        
        if mode_info:
            st.info(" | ".join(mode_info))
        
        with st.form("analyze_form"):
            symbol = st.text_input("Asset Symbol:", placeholder="e.g., BTC/USDT or AAPL")
            submit = st.form_submit_button("🔍 Analyze Asset", type="primary")
            
            if submit:
                if not symbol:  # Validasi input
                    st.error("⚠️ Masukkan simbol aset terlebih dahulu!")
                else:
                    formatted_symbol = format_symbol_for_mode(symbol.upper(), bot.mode, bot.trading_mode)
                    with st.spinner("Analyzing asset..."):
                        try:
                            analysis = bot.analyze_asset(formatted_symbol)
                            if analysis:
                                # Validasi dan fix price levels
                                analysis = validate_and_fix_price_levels(analysis, formatted_symbol, bot)
                                st.session_state.selected_analysis = analysis
                                st.session_state.selected_symbol_display = convert_symbol_for_display(
                                    formatted_symbol,
                                    bot.mode,
                                    bot.trading_mode
                                )
                                st.success("✅ Analysis complete!")
                            else:
                                st.warning("⚠️ No analysis data returned.")
                        except Exception as e:
                            st.error(f"❌ Analysis error: {e}")
                
                st.rerun()
        
        # Tambahkan button cek harga
        if st.button("💰 Cek Harga Real-Time"):
            if symbol:
                live_price = get_real_time_price(symbol.upper(), bot)
                if live_price:
                    st.success(f"💰 Harga real-time {symbol}: ${live_price:,.5f}")
                else:
                    st.warning(f"⚠️ Gagal ambil harga {symbol}. Coba cek koneksi atau provider.")
            else:
                st.error("⚠️ Masukkan simbol terlebih dahulu!")
        
        # Display Analysis Results
        if st.session_state.selected_analysis:
            analysis = st.session_state.selected_analysis
            display_symbol = st.session_state.selected_symbol_display or analysis.get('symbol', 'Unknown')
            
            scalping_indicator = "⚡ " if st.session_state.scalping_mode else ""
            
            st.subheader(f"📊 Analysis for {scalping_indicator}{display_symbol}")
            
            # Strategi Terdeteksi
            detected_strats = analysis.get('detected_strategies', [])
            if detected_strats:
                st.subheader("📊 Strategi Terdeteksi:")
                for strat in detected_strats:
                    st.write(f"- {strat}")
            else:
                st.info("ℹ️ Tidak ada strategi spesifik terdeteksi.")
            
            action = analysis.get('action', 'NEUTRAL')
            score = analysis.get('score', 0)
            current_price = analysis.get('current_price', 0)
            
            emoji = "📈" if action == "LONG" else "📉" if action == "SHORT" else "⚖️"
            color = "green" if action == "LONG" else "red" if action == "SHORT" else "gray"
            
            col_a1, col_a2 = st.columns(2)
            with col_a1:
                st.write(f"{emoji} **Action:** <span style='color:{color}; font-weight:bold'>{action}</span>", unsafe_allow_html=True)
                st.write(f"📊 **Score:** {score:.1f}")
                st.write(f"💰 **Current Price:** ${current_price:,.5f}")
            with col_a2:
                if st.button("🚀 Open Position", key="open_from_analysis"):
                    st.session_state.selected_for_entry = analysis
                    st.rerun()
            
            # Price Levels
            st.subheader("🎯 Price Levels")
            col_p1, col_p2 = st.columns(2)
            with col_p1:
                st.metric("Best Entry", f"${analysis.get('best_entry', 0):,.5f}")
                st.metric("Entry Range Low", f"${analysis.get('entry_range_low', 0):,.5f}")
                st.metric("Entry Range High", f"${analysis.get('entry_range_high', 0):,.5f}")
            with col_p2:
                st.metric("TP1", f"${analysis.get('tp1', 0):,.5f}")
                st.metric("TP2", f"${analysis.get('tp2', 0):,.5f}")
                st.metric("TP3", f"${analysis.get('tp3', 0):,.5f}")
                st.metric("SL", f"${analysis.get('sl', 0):,.5f}")
            
            # Additional Metrics
            with st.expander("📈 Additional Metrics"):
                col_m1, col_m2 = st.columns(2)
                with col_m1:
                    st.metric("ATR", f"${analysis.get('atr', 0):,.5f}")
                    st.metric("Volatility", f"{analysis.get('volatility', 0):.2%}")
                with col_m2:
                    st.metric("RSI", f"{analysis.get('rsi', 0):.1f}")
                    st.metric("Volume Ratio", f"{analysis.get('volume_ratio', 0):.2f}")
            
            # Chart jika plotly available
            if PLOTLY_AVAILABLE and 'ohlc_data' in analysis:
                fig = go.Figure(data=[go.Candlestick(
                    x=analysis['ohlc_data'].index,
                    open=analysis['ohlc_data']['open'],
                    high=analysis['ohlc_data']['high'],
                    low=analysis['ohlc_data']['low'],
                    close=analysis['ohlc_data']['close']
                )])
                st.plotly_chart(fig, use_container_width=True)

    # Tab 4: Open Position
    with tab4:
        st.subheader("🚀 Open New Position")
        
        # Mode info
        mode_info = []
        if hasattr(bot, 'trading_mode'):
            mode_display = "🔄 Spot" if bot.trading_mode == "spot" else "⚡ Futures"
            mode_info.append(f"**Trading Mode:** {mode_display}")
        
        if st.session_state.scalping_mode:
            mode_info.append("⚡ **SCALPING:** ON")
        
        if mode_info:
            st.info(" | ".join(mode_info))
        
        if st.session_state.selected_for_entry:
            entry_data = st.session_state.selected_for_entry
            symbol = entry_data.get('symbol', '')
            action = entry_data.get('action', 'LONG')
            entry_price = entry_data.get('best_entry', 0)
            tp1 = entry_data.get('tp1', 0)
            tp2 = entry_data.get('tp2', 0)
            tp3 = entry_data.get('tp3', 0)
            sl = entry_data.get('sl', 0)
        else:
            symbol = ""
            action = "LONG"
            entry_price = 0
            tp1 = tp2 = tp3 = sl = 0
        
        with st.form("open_position_form"):
            symbol_input = st.text_input("Symbol:", value=symbol)
            action_select = st.selectbox("Action:", ["LONG", "SHORT"], index=0 if action == "LONG" else 1)
            entry_price_input = st.number_input("Entry Price:", value=float(entry_price), step=0.01)
            tp1_input = st.number_input("TP1:", value=float(tp1), step=0.01)
            tp2_input = st.number_input("TP2:", value=float(tp2), step=0.01)
            tp3_input = st.number_input("TP3:", value=float(tp3), step=0.01)
            sl_input = st.number_input("SL:", value=float(sl), step=0.01)
            position_size = st.number_input("Position Size ($):", value=100.0, step=10.0)
            
            submit_open = st.form_submit_button("🚀 Open Position", type="primary")
            
            if submit_open:
                if symbol_input and entry_price_input > 0:
                    try:
                        position_id = bot.save_position_to_db(
                            symbol=symbol_input,
                            action=action_select,
                            entry_price=entry_price_input,
                            tp1=tp1_input,
                            tp2=tp2_input,
                            tp3=tp3_input,
                            sl=sl_input,
                            position_size=position_size
                        )
                        if position_id:
                            st.success(f"✅ Position opened! ID: {position_id}")
                            st.session_state.selected_for_entry = {}
                            st.rerun()
                        else:
                            st.error("❌ Failed to open position")
                    except Exception as e:
                        st.error(f"❌ Open position error: {e}")
                else:
                    st.error("⚠️ Please fill symbol and entry price")

    # Tab 5: Risk Assessment
    with tab5:
        st.subheader("⚖️ Risk Assessment")
        
        # Mode info
        mode_info = []
        if hasattr(bot, 'trading_mode'):
            mode_display = "🔄 Spot" if bot.trading_mode == "spot" else "⚡ Futures"
            mode_info.append(f"**Trading Mode:** {mode_display}")
        
        if st.session_state.scalping_mode:
            mode_info.append("⚡ **SCALPING:** ON")
        
        if mode_info:
            st.info(" | ".join(mode_info))
        
        if st.session_state.selected_analysis:
            analysis = st.session_state.selected_analysis
            symbol = analysis.get('symbol', 'Unknown')
            
            with st.spinner("Assessing risk..."):
                try:
                    risk = bot.assess_risk(analysis)
                    if risk:
                        st.session_state.open_position_risk = risk
                        st.success("✅ Risk assessment complete!")
                    else:
                        st.warning("⚠️ No risk data returned.")
                except Exception as e:
                    st.error(f"❌ Risk assessment error: {e}")
            
            if st.session_state.open_position_risk:
                risk = st.session_state.open_position_risk
                st.subheader(f"⚖️ Risk for {symbol}")
                
                col_r1, col_r2 = st.columns(2)
                with col_r1:
                    st.metric("Risk Level", risk.get('risk_level', 'Medium'))
                    st.metric("Max Loss %", f"{risk.get('max_loss_pct', 0):.2f}%")
                with col_r2:
                    st.metric("Reward/Risk", f"{risk.get('reward_risk_ratio', 0):.2f}")
                    st.metric("Win Probability", f"{risk.get('win_probability', 0):.1f}%")
                
                st.progress(risk.get('win_probability', 50) / 100)
                
                with st.expander("📋 Risk Details"):
                    st.write(risk.get('recommendation', 'No recommendation available.'))
        else:
            st.info("👉 Analyze an asset first to assess risk!")

    # Tab 6: Active Positions
    with tab6:
        st.subheader("📊 Active Positions")
        
        # Mode info
        mode_info = []
        if hasattr(bot, 'trading_mode'):
            mode_display = "🔄 Spot" if bot.trading_mode == "spot" else "⚡ Futures"
            mode_info.append(f"**Trading Mode:** {mode_display}")
        
        if st.session_state.scalping_mode:
            mode_info.append("⚡ **SCALPING:** ON")
        
        if mode_info:
            st.info(" | ".join(mode_info))
        
        if st.button("🔄 Refresh Positions", key="refresh_positions"):
            st.rerun()
        
        positions_data = bot.get_active_positions()
        
        if positions_data:
            for pos in positions_data:
                try:
                    if not isinstance(pos, dict):
                        continue
                    
                    symbol = pos.get('symbol', 'Unknown')
                    action = pos.get('action', 'Unknown')
                    entry_price = float(pos.get('entry_price', 0))
                    current_price = float(pos.get('current_price', entry_price))  # Fallback ke entry jika current 0
                    position_size = float(pos.get('position_size', 0))
                    tp1 = float(pos.get('tp1', 0))
                    tp2 = float(pos.get('tp2', 0))
                    tp3 = float(pos.get('tp3', 0))
                    sl = float(pos.get('sl', 0))
                    position_id = pos.get('id')
                    
                    # Fetch live price dan update ke database
                    live_price = get_real_time_price(symbol, bot)
                    price_source = "Live"
                    
                    if live_price is None or live_price <= 0:
                        live_price = entry_price  # Fallback ke entry jika live gagal
                        price_source = "Entry (Fallback)"
                        st.warning(f"⚠️ Gunakan harga entry untuk {symbol} karena live gagal.")
                    else:
                        # Update ke database
                        update_success = update_position_price_in_db(bot, position_id, live_price)
                        if update_success:
                            price_source = "Live + DB"
                        else:
                            price_source = "Live (DB update failed)"
                    
                    # Hitung P/L
                    if entry_price > 0 and live_price > 0:
                        if action == "LONG":
                            pl_pct = ((live_price - entry_price) / entry_price) * 100
                            pl_value = (live_price - entry_price) * (position_size / entry_price)
                        else:
                            pl_pct = ((entry_price - live_price) / entry_price) * 100
                            pl_value = (entry_price - live_price) * (position_size / entry_price)
                    else:
                        pl_pct = 0.0
                        pl_value = 0.0
                    
                    display_symbol = convert_symbol_for_display(symbol, bot.mode, bot.trading_mode)
                    scalping_indicator = "⚡ " if st.session_state.scalping_mode else ""
                    
                    col_p1, col_p2, col_p3 = st.columns(3)
                    with col_p1:
                        st.write(f"**{scalping_indicator}{display_symbol}** ({action})")
                        st.write(f"Entry: ${entry_price:,.5f}")
                        st.write(f"Current: ${live_price:,.5f} ({price_source})")
                    with col_p2:
                        st.write(f"TP1: ${tp1:,.5f}")
                        st.write(f"TP2: ${tp2:,.5f}")
                        st.write(f"TP3: ${tp3:,.5f}")
                        st.write(f"SL: ${sl:,.5f}")
                    with col_p3:
                        color = "green" if pl_pct >= 0 else "red"
                        emoji = "📈" if pl_pct >= 0 else "📉"
                        st.write(f"{emoji} P/L: <span style='color:{color}'>{pl_pct:+.2f}%</span>", unsafe_allow_html=True)
                        st.write(f"Value: <span style='color:{color}'>${pl_value:+,.2f}</span>", unsafe_allow_html=True)
                        if st.button("❌ Close", key=f"close_{position_id}"):
                            close_price = live_price or current_price
                            if bot.close_position(position_id, close_price):
                                st.success(f"✅ Position {display_symbol} closed!")
                                st.rerun()
                            else:
                                st.error("❌ Failed to close position")
                    
                    st.markdown("---")
                except Exception as e:
                    st.error(f"❌ Position error: {e}")
                    continue
        else:
            st.info("📭 No active positions")

    # Tab 7: Trade History
    with tab7:
        st.subheader("📜 Trade History")
        
        # Mode info
        mode_info = []
        if hasattr(bot, 'trading_mode'):
            mode_display = "🔄 Spot" if bot.trading_mode == "spot" else "⚡ Futures"
            mode_info.append(f"**Trading Mode:** {mode_display}")
        
        if st.session_state.scalping_mode:
            mode_info.append("⚡ **SCALPING:** ON")
        
        if mode_info:
            st.info(" | ".join(mode_info))
        
        history_data = bot.get_trade_history(limit=20)
        
        if history_data:
            for trade in history_data:
                try:
                    symbol = trade.get('symbol', 'Unknown')
                    action = trade.get('action', 'Unknown')
                    entry_price = float(trade.get('entry_price', 0))
                    exit_price = float(trade.get('exit_price', 0))
                    profit_loss = float(trade.get('profit_loss', 0))
                    
                    display_symbol = convert_symbol_for_display(symbol, bot.mode, bot.trading_mode)
                    scalping_indicator = "⚡ " if st.session_state.scalping_mode else ""
                    
                    emoji = "✅" if profit_loss >= 0 else "❌"
                    color = "green" if profit_loss >= 0 else "red"
                    
                    st.write(f"{emoji} **{scalping_indicator}{display_symbol}** - {action}")
                    st.write(f"Entry: `{entry_price:.5f}` | Exit: `{exit_price:.5f}`")
                    st.write(f"P/L: <span style='color:{color}'>{profit_loss:.5f}</span>", unsafe_allow_html=True)
                    st.markdown("---")
                except Exception as e:
                    st.error(f"History error: {e}")
        else:
            st.info("📭 No trade history available")

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
        col1, col2, col3, col4 = st.columns([1, 2, 1, 1])
        with col1:
            if st.button("🚀 Start Live Monitoring" if not st.session_state.live_monitoring else "⏹️ Stop Monitoring", 
                        key="toggle_live_tab8", type="primary"):
                st.session_state.live_monitoring = not st.session_state.live_monitoring
                st.rerun()
    
        with col2:
            auto_refresh_live = st.checkbox("🔄 Auto Refresh (10s)", value=True, key="auto_refresh_live_tab8")
        
        with col3:
            if st.button("🔄 Refresh Prices", key="refresh_prices_btn_tab8"):
                st.rerun()
        
        with col4:
            if st.button("📊 Show All", key="show_all_btn_tab8"):
                st.session_state.show_all_positions = not st.session_state.show_all_positions
                st.rerun()
        
        if st.session_state.live_monitoring:
            st.success("📡 LIVE MONITORING ACTIVE")
            
            # Selalu ambil dari database, hilangkan test_positions
            positions_data = bot.get_active_positions()
            
            if positions_data:
                st.subheader(f"📊 Monitoring {len(positions_data)} positions")
                
                for idx, pos in enumerate(positions_data):
                    try:
                        if not isinstance(pos, dict):
                            continue
                        
                        symbol = pos.get('symbol', 'Unknown')
                        action = pos.get('action', 'Unknown')
                        entry_price = float(pos.get('entry_price', 0))
                        current_price = float(pos.get('current_price', entry_price))  # Fallback ke entry jika current 0
                        position_size = float(pos.get('position_size', 0))
                        status = pos.get('status', 'open')
                        position_id = pos.get('id')
                        
                        # Fetch live price dan update ke database
                        live_price = get_real_time_price(symbol, bot)
                        price_source = "Live"
                        
                        if live_price is None or live_price <= 0:
                            live_price = entry_price  # Fallback ke entry jika live gagal
                            price_source = "Entry (Fallback)"
                            st.warning(f"⚠️ Gunakan harga entry untuk {symbol} karena live gagal.")
                        else:
                            # Update ke database
                            update_success = update_position_price_in_db(bot, position_id, live_price)
                            if update_success:
                                price_source = "Live + DB"
                            else:
                                price_source = "Live (DB update failed)"
                        
                        # Update P/L berdasarkan live_price
                        pl_pct = 0.0
                        pl_value = 0.0
                        
                        if entry_price > 0 and live_price > 0:
                            if action == "LONG":
                                pl_pct = ((live_price - entry_price) / entry_price) * 100
                                pl_value = (live_price - entry_price) * (position_size / entry_price) if entry_price > 0 else 0
                            else:
                                pl_pct = ((entry_price - live_price) / entry_price) * 100
                                pl_value = (entry_price - live_price) * (position_size / entry_price) if entry_price > 0 else 0
                        
                        display_symbol = convert_symbol_for_display(symbol, bot.mode, bot.trading_mode)
                        
                        # Display
                        col_l1, col_l2, col_l3, col_l4 = st.columns([2, 2, 2, 1])
                        
                        with col_l1:
                            status_emoji = "🟢" if status == 'open' else "🔴" if status == 'closed' else "⚪"
                            st.write(f"{status_emoji} **{display_symbol}**")
                            st.write(f"Action: `{action}` | Status: `{status}`")
                            if entry_price > 0:
                                st.write(f"🏁 Entry: `${entry_price:,.5f}`")
                            st.write(f"Size: `${position_size:,.2f}`")
                        
                        with col_l2:
                            price_color = "🟢" if "Live" in price_source else "🟡" if "Database" in price_source else "⚪"
                            st.write(f"{price_color} {price_source}: `${live_price:,.5f}`")
                            
                            if entry_price > 0:
                                if action == "LONG":
                                    change = ((live_price - entry_price) / entry_price) * 100
                                else:
                                    change = ((entry_price - live_price) / entry_price) * 100
                                change_emoji = "📈" if change >= 0 else "📉"
                                st.write(f"{change_emoji} Change: `{change:+.2f}%`")
                        
                        with col_l3:
                            color = "green" if pl_pct >= 0 else "red"
                            emoji = "📈" if pl_pct >= 0 else "📉"
                            st.write(f"{emoji} P/L: <span style='color:{color}; font-weight:bold'>{pl_pct:+.2f}%</span>", unsafe_allow_html=True)
                            st.write(f"💰 Value: <span style='color:{color}'>${pl_value:+,.2f}</span>", unsafe_allow_html=True)
                        
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

    # Tab 10: Portfolio Optimization
    with tab10:
        st.subheader("⚖️ Portfolio Optimization")
        
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
                        signals = st.session_state.scanned_results[:5]
                        position_size = 0.2  # 20% per position default
                    
                    total_signals = len(signals)
                    if total_signals > 0:
                        allocations = {
                            'signals': [
                                {
                                    'symbol': s['symbol'],
                                    'score': s.get('score', 1),
                                    'action': s.get('action', 'LONG'),
                                    'allocation_percent': position_size,
                                    'allocated_capital': portfolio_capital * position_size,
                                    'scalping': st.session_state.scalping_mode
                                }
                                for s in signals
                            ],
                            'total_allocated_percent': position_size * total_signals,
                            'total_allocated_capital': portfolio_capital * position_size * total_signals,
                            'remaining_capital': portfolio_capital * (1 - (position_size * total_signals)),
                            'scalping_mode': st.session_state.scalping_mode
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
            
            st.subheader("📋 Position Details")
            allocation_data = []
            for signal in allocations.get('signals', []):
                display_symbol = convert_symbol_for_display(
                    signal['symbol'],
                    bot.mode,
                    getattr(bot, 'trading_mode', 'spot')
                )
                
                scalping_indicator = "⚡ " if signal.get('scalping') else ""
                
                allocation_data.append({
                    'Symbol': f"{scalping_indicator}{display_symbol}",
                    'Action': signal['action'],
                    'Score': f"{signal['score']:+.1f}",
                    'Allocation %': f"{signal['allocation_percent']:.1%}",
                    'Capital': f"${signal['allocated_capital']:,.2f}"
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
        
        st.subheader("🔗 Portfolio Analysis")
        st.info("""
        **Portfolio Features:**
        - Risk-adjusted position sizing
        - Diversification scoring
        - Dynamic allocation optimization
        - Correlation analysis
        
        **Scalping Portfolio Rules:**
        1. Max 3-5 positions simultaneously
        2. 1-3% position size per trade
        3. Stop loss always set
        4. Take profit at TP1 (60% probability)
        5. Maximum 5 trades per day
        6. Equal opportunities for LONG/SHORT
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
        # JANGAN inisialisasi bot_instance di sini - biarkan di main_app()
        'positions_initialized': False,
        'refresh_counter': 0
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
