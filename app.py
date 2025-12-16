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

# Try to import plotly
try:
    import plotly.graph_objects as go
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False

# Import TradingBot dengan error handling yang lebih baik
def import_trading_bot():
    """Import TradingBot dari core.py - SIMPLIFIED VERSION"""
    import sys
    import os
    
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    
    print(f"📁 Current directory: {current_dir}")
    print(f"📁 Project root: {project_root}")
    
    # Tambahkan path
    if current_dir not in sys.path:
        sys.path.insert(0, current_dir)
    
    # 🔥 PERBAIKAN: Import langsung dari bot folder
    try:
        # Import core.py yang sudah diperbaiki
        import core as core_module
        print("✅ Imported core module successfully")
        
        # Cari class TradingBot atau EnhancedTradingBot
        if hasattr(core_module, 'EnhancedTradingBot'):
            print("✅ Found EnhancedTradingBot in core")
            return core_module.EnhancedTradingBot
        elif hasattr(core_module, 'TradingBot'):
            print("✅ Found TradingBot in core")
            return core_module.TradingBot
        else:
            print("❌ No TradingBot class found in core")
            return None
            
    except Exception as e:
        print(f"❌ Error importing core: {e}")
        
        # Fallback: coba import dari bot.core
        try:
            from bot.core import EnhancedTradingBot
            print("✅ Imported EnhancedTradingBot from bot.core")
            return EnhancedTradingBot
        except ImportError as e2:
            print(f"❌ Cannot import from bot.core: {e2}")
            
            # Last resort: buat dummy class
            print("⚠️ Creating dummy TradingBot class")
            class DummyTradingBot:
                def __init__(self, *args, **kwargs):
                    self.mode = "crypto"
                    self.trading_mode = "spot"
                    self.config = {}
                    self.db = None
                    self.data_provider = None
                    print("⚠️ Using dummy TradingBot - limited functionality")
                
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
                    return []
                
                def get_trade_history(self, limit=20):
                    return []
                
                def close_position(self, position_id, close_price):
                    return True
            
            return DummyTradingBot

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
    """Get valid price from analysis data"""
    if not isinstance(data, dict):
        return 1.0
    
    price_sources = ['current_price', 'entry_price', 'ideal_entry', 'close', 'last']
    
    for source in price_sources:
        price = data.get(source)
        if price and isinstance(price, (int, float)) and price > 0:
            return float(price)
    
    if symbol and bot and hasattr(bot, 'data_provider'):
        try:
            ticker = bot.data_provider.get_ticker(symbol)
            if ticker and 'last' in ticker and ticker['last'] > 0:
                return float(ticker['last'])
        except:
            pass
    
    return 1.0

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
    
    # 🔥 HAPUS: bias_applied = signal.get('long_bias_applied', 0)
    
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
        
        # 🔥 HAPUS bagian tampilkan bias info
    
    with col2:
        current_price = get_valid_price(signal, symbol, st.session_state.bot_instance)
        st.write(f"💰 Price: `{current_price:.5f}`")
        
        # Entry range untuk scalping
        entry_low = signal.get('entry_range_low', 0)
        entry_high = signal.get('entry_range_high', 0)
        if entry_low and entry_high:
            range_pct = ((entry_high - entry_low) / current_price) * 100
            st.write(f"🎯 Range: `{entry_low:.5f}` - `{entry_high:.5f}`")
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
        
        st.write(f"{tp_emoji} TP1: `{tp1:.5f}`")
        st.write(f"{tp_emoji} TP2: `{tp2:.5f}`")
        st.write(f"📊 R/R: `{risk_reward:.2f}`")
    
    with col4:
        # Scalping specific info
        st.write(f"⚡ Scalping Score: `{scalping_score}/7`")
        st.write(f"🎯 Confidence: `{confidence:.1%}`")
        st.write(f"🛡️ SL: `{sl:.5f}`")
        
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
# Main App - SIMPLIFIED VERSION
# ====================================
def main_app():
    st.title("🚀 TradingBot Pro - Enhanced Dashboard with Scalping Support")
    
    # User info and logout
    col1, col2 = st.columns([3, 1])
    with col1:
        st.write(f"Welcome, **{st.session_state.username}**! 👋")
    with col2:
        if st.button("🚪 Logout"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()

    # Initialize bot
    if 'bot_instance' not in st.session_state:
        with st.spinner("Initializing TradingBot..."):
            try:
                bot = init_bot()
                if bot:
                    st.session_state.bot_instance = bot
                    
                    # Set default mode jika belum
                    if not hasattr(bot, 'mode'):
                        bot.mode = "crypto"
                    if not hasattr(bot, 'trading_mode'):
                        bot.trading_mode = "spot"
                    
                    st.success("✅ TradingBot initialized successfully!")
                else:
                    st.error("Failed to initialize TradingBot")
                    st.stop()
            except Exception as e:
                st.error(f"Bot initialization error: {e}")
                st.stop()
    
    bot = st.session_state.bot_instance
    
    # Initialize session state
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
        st.session_state.saved_custom_entry = None  # 🔥 NEW: Untuk menyimpan entry dari tab 4
        st.session_state.open_position_result = None  # 🔥 NEW: Untuk menyimpan hasil kalkulasi TP/SL
        st.session_state.open_position_risk = None  # 🔥 NEW: Untuk menyimpan info risk
        
        # 🔥 PERBAIKAN: Tambahkan session state untuk debug
        st.session_state.last_scan_time = None
        st.session_state.scan_attempts = 0

    # Sidebar
    with st.sidebar:
        st.header("🎯 Trading Configuration")
        
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
                    # HAPUS slider untuk long_bias, tampilkan info
                    st.info("Bias: 0.0 (Neutral)")
                
                if st.button("Apply Settings", key="apply_scalping_settings"):
                    SCALPING_CONFIG_APP["min_score"] = min_score_sidebar
                    # HAPUS: SCALPING_CONFIG_APP["long_bias"] = long_bias_value
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
                st.write(f"Price: ${data.get('current_price', 0):.4f}")
            
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

        # Set Market Button
        if st.button("🎯 Set Market", key="set_market_btn", type="primary"):
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
        
        # Info tentang simbol berdasarkan mode
        if st.session_state.market_set:
            with st.expander("ℹ️ Symbol Format Info"):
                if hasattr(bot, 'trading_mode'):
                    if bot.trading_mode == "spot":
                        st.write("**Spot Trading Format:**")
                        st.write("- Crypto: BTC/USDT, ETH/USDT")
                        st.write("- Forex: EUR/USD, GBP/USD")
                        st.write("- Saham ID: BBCA.JK, TLKM.JK")
                        st.write("- US Stocks: AAPL, TSLA")
                    else:
                        st.write("**Futures Trading Format:**")
                        st.write("- Crypto: BTC/USDT:USDT, ETH/USDT:USDT")
                        st.write("- Crypto (alternative): BTCUSDT-PERP, ETHUSDT-PERP")

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

    # Check if market is set
    if not st.session_state.market_set:
        st.warning("⚠️ Please select a market first!")
        st.info("""
        **Instructions:**
        1. Select Market (Crypto/Forex/Saham Indonesia/US Stocks)  
        2. Select Trading Mode (Spot/Futures)
        3. Click **Set Market** button
        4. Start scanning assets
        
        **Note:** 
        - Futures trading only available for Crypto
        - Short trading only available for Crypto Futures
        """)
        return

    # Main Tabs - 🔥 UPDATED DENGAN TAB BARU (MENGHAPUS TAB 5)
    tab1, tab2, tab3, tab4, tab6, tab7, tab8, tab9, tab10 = st.tabs([
        "📊 Scan Assets", "⚡ Scalping Mode", "🔍 Analyze", "🎯 Custom Entry", 
        "💼 Positions", "📈 History", "📡 Live Scanner", 
        "🤖 ML Backtest", "⚖️ Portfolio"
    ])

    # Tab 1: Scan Assets (Regular) - PERBAIKAN
    with tab1:
        st.subheader("📊 Scan Potential Assets")
        
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
            """)
        
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
                    st.success(f"✅ **{display_symbol}** - {data.get('action', 'N/A')} (Score: {data.get('score', 0)})")
                    st.write(f"💰 Price: `{data.get('current_price', 0):.5f}` | Entry Range: `{data.get('entry_range_low', 0):.5f} - {data.get('entry_range_high', 0):.5f}`")
                with col_sel2:
                    if st.button(f"❌ Remove", key=f"remove_{symbol}"):
                        del st.session_state.selected_for_entry[symbol]
                        st.rerun()
            st.divider()
        
        # Scan button dengan opsi berbeda untuk scalping mode
        col_scan1, col_scan2 = st.columns([1, 3])
        with col_scan1:
            if st.session_state.scalping_mode:
                scan_button_label = "🚀 Start Scalping Scan"
                scan_type = "scalping"
            else:
                scan_button_label = "🚀 Start Regular Scan"
                scan_type = "regular"
        
        # Scan button
        if st.button(scan_button_label, key="start_scan", type="primary"):
            with st.spinner(f"Scanning assets ({scan_type})..."):
                try:
                    # 🔥 PERBAIKAN: Gunakan jumlah yang sesuai
                    if st.session_state.scalping_mode:
                        limit = 20  # Lebih banyak untuk scalping
                    else:
                        limit = 20
                    
                    # Gunakan scan_potential_assets_optimized jika tersedia
                    if hasattr(bot, 'scan_potential_assets_optimized'):
                        results = bot.scan_potential_assets_optimized(limit)
                    else:
                        results = bot.scan_potential_assets(limit)
                    
                    if results:
                        # Process results
                        formatted_results = []
                        scalping_results = []  # 🔥 NEW: Store scalping results separately
                        
                        for result in results:
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
                                        # 🔥 HAPUS baris ini: validated_result['long_bias_applied'] = SCALPING_CONFIG_APP["long_bias"]
                                        scalping_results.append(validated_result)
                                
                                formatted_results.append(validated_result)
                        
                        # 🔥 PERBAIKAN: Apply additional filtering for scalping
                        if st.session_state.scalping_mode and scalping_results:
                            scalping_results = filter_for_scalping(scalping_results, bot)
                        
                        st.session_state.scanned_results = formatted_results
                        st.session_state.scalping_results = scalping_results  # 🔥 NEW
                        
                        # 🔥 PERBAIKAN: Tampilkan informasi detail
                        col_info1, col_info2, col_info3 = st.columns(3)
                        with col_info1:
                            st.metric("Total Assets Scanned", len(results))
                        with col_info2:
                            st.metric("Valid Signals", len(formatted_results))
                        with col_info3:
                            if st.session_state.scalping_mode:
                                st.metric("Scalping Signals", len(scalping_results))
                        
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
                                4. Low volume or data quality
                                """)
                        else:
                            st.success(f"✅ Found {len(formatted_results)} potential assets")
                        
                    else:
                        st.warning("⚠️ No signals found")
                        
                except Exception as e:
                    st.error(f"Scan error: {str(e)[:200]}")
        
        # 🔥 PERBAIKAN: DEBUG INFO untuk scalping
        if st.session_state.scalping_mode:
            with st.expander("🔧 Debug Information"):
                st.write("**Current Scalping Configuration:**")
                st.json(SCALPING_CONFIG_APP)
                
                if st.session_state.scanned_results:
                    st.write(f"**Total Scanned Results:** {len(st.session_state.scanned_results)}")
                    st.write("**Top 10 Results (with scores):**")
                    debug_data = []
                    for i, res in enumerate(st.session_state.scanned_results[:10]):
                        symbol = res.get('symbol', 'N/A')
                        score = res.get('score', 0)
                        action = res.get('action', 'NEUTRAL')
                        price = get_valid_price(res, symbol, bot)
                        debug_data.append({
                            "Symbol": symbol,
                            "Score": f"{score:+.1f}",
                            "Action": action,
                            "Price": f"${price:.4f}",
                            "Scalping?": "✅" if res.get('scalping_suitable', False) else "❌"
                        })
                    
                    if debug_data:
                        df_debug = pd.DataFrame(debug_data)
                        st.dataframe(df_debug, use_container_width=True)
        
        # 🔥 NEW: Jika dalam scalping mode, tampilkan hasil khusus scalping
        if st.session_state.scalping_mode and st.session_state.scalping_results:
            st.subheader("⚡ Scalping Signals")
            
            for i, res in enumerate(st.session_state.scalping_results[:10], 1):
                if isinstance(res, dict) and 'symbol' in res:
                    selected = display_scalping_signal(res, i)
                    if selected:
                        st.rerun()
                    
                    st.divider()
        
        # Display regular scanned results jika tidak dalam scalping mode
        elif st.session_state.scanned_results and not st.session_state.scalping_mode:
            st.subheader("📊 Regular Signals")
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
                        
                        current_price = get_valid_price(res, symbol, bot)
                        st.write(f"💰 Current Price: `{current_price:.5f}`")
                        
                        # Tampilkan entry range
                        st.write(f"📊 **Entry Range:** `{res.get('entry_range_low', 0):.5f} - {res.get('entry_range_high', 0):.5f}`")
                        st.write(f"🎯 **Ideal Entry:** `{res.get('best_entry', 0):.5f}`")
                        if 'range_size' in res:
                            st.write(f"📏 **Range Size:** `{res.get('range_size', 0):.1f}%`")
                        
                        # TP/SL levels
                        tp1, tp2, tp3 = safe_get(res, 'tp1', 0), safe_get(res, 'tp2', 0), safe_get(res, 'tp3', 0)
                        sl = safe_get(res, 'sl', 0)
                        
                        st.write(f"🎯 **TP Levels:** `{tp1:.5f}` | `{tp2:.5f}` | `{tp3:.5f}`")
                        st.write(f"🛑 **Stop Loss:** `{sl:.5f}`")
                        
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
                    
                    st.divider()

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
                    # 🔥 HAPUS slider untuk long_bias, tampilkan info
                    st.info("Bias: 0.0 (Neutral)")
                    long_bias = 0.0  # Hardcode ke 0
                
                with col_sc3:
                    entry_range = st.slider("Entry Range %", 0.005, 0.02,
                                          value=SCALPING_CONFIG_APP["entry_range_pct"], step=0.001,
                                          key="tab2_entry_range")
                    st.caption(f"Current: {entry_range*100:.1f}%")
                
                if st.button("🔄 Update Scalping Config", key="update_scalping_config"):
                    SCALPING_CONFIG_APP["min_score"] = min_score
                    # HAPUS: SCALPING_CONFIG_APP["long_bias"] = long_bias
                    SCALPING_CONFIG_APP["entry_range_pct"] = entry_range
                    st.session_state.scalping_config = SCALPING_CONFIG_APP
                    st.success("✅ Scalping configuration updated!")
                    st.rerun()
            
            # 🔥 PERBAIKAN: Quick Actions dengan feedback yang lebih baik
            col_qs1, col_qs2, col_qs3 = st.columns(3)
            
            with col_qs1:
                if st.button("🎯 Quick Scan (Top 15)", key="quick_scalping_scan", type="primary"):
                    with st.spinner("Quick scanning for scalping..."):
                        try:
                            # Quick scan untuk scalping
                            results = bot.scan_potential_assets(15)
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
                st.subheader("⚡ Active Scalping Signals")
                
                # Sort by absolute score descending (strongest first)
                sorted_signals = sorted(st.session_state.scalping_results, 
                                      key=lambda x: abs(x.get('score', 0)), reverse=True)
                
                for i, signal in enumerate(sorted_signals[:8], 1):
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
                            entry_range_low = signal.get('entry_range_low', 0)
                            entry_range_high = signal.get('entry_range_high', 0)
                            
                            st.write(f"💰 Price: `{current_price:.5f}`")
                            st.write(f"🎯 Entry: `{entry_range_low:.5f}` - `{entry_range_high:.5f}`")
                        
                        with col_s3:
                            tp1 = signal.get('tp1', 0)
                            sl = signal.get('sl', 0)
                            
                            if action == "LONG":
                                rr_ratio = (tp1 - current_price) / (current_price - sl) if (current_price - sl) > 0 else 0
                            else:
                                rr_ratio = (current_price - tp1) / (sl - current_price) if (sl - current_price) > 0 else 0
                            
                            st.write(f"📊 R/R: `{rr_ratio:.2f}`")
                            st.write(f"🎯 TP1: `{tp1:.5f}`")
                            
                            button_key = f"select_scalping_signal_{i}_{symbol}"
                            if st.button(f"📌 Select", key=button_key):
                                if select_asset_callback(symbol, signal):
                                    st.success(f"✅ Selected {symbol} for scalping!")
                                    st.rerun()
                        
                        st.divider()
            
            # Scalping Tips
            with st.expander("💡 Scalping Tips"):
                st.write("""
                **Scalping Strategy (3-5 minutes):**
                1. **Entry Timing:** Wait for price to hit entry range
                2. **Position Size:** 2-5% of capital per trade
                3. **Take Profit:** TP1 is primary target (60-70% probability)
                4. **Stop Loss:** Always use stop loss
                5. **Max Trades:** 3-5 trades per day max
                
                **Risk Management:**
                - Max risk per trade: 1% of capital
                - Daily max loss: 3% of capital
                - Never revenge trade
                
                **SHORT Scalping Tips:**
                - Best during bearish trends or market corrections
                - Look for overbought RSI (>70) for short entries
                - Use tighter stops (1-2%) for shorts
                - Take profit quickly (1-2% moves)
                
                **Best Conditions for Scalping:**
                - High volume (> $1M daily)
                - Moderate volatility (2-8% daily)
                - Clear support/resistance levels
                """)

    # Tab 3: Analyze Asset
    with tab3:
        st.subheader("🔍 Analyze Specific Asset")
        
        # Info mode
        mode_status = []
        if hasattr(bot, 'trading_mode'):
            mode_display = "🔄 Spot" if bot.trading_mode == "spot" else "⚡ Futures"
            mode_status.append(f"Mode: {mode_display}")
        
        if st.session_state.scalping_mode:
            mode_status.append("⚡ Scalping: ON")
        
        if mode_status:
            st.caption(" | ".join(mode_status))
        
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
                    # HAPUS slider untuk bias, tampilkan info
                    st.info("Analysis Bias: 0.0 (disabled)")
                    analysis_config['long_bias'] = 0.0
                with col_sa2:
                    analysis_config['min_score'] = st.slider("Min Score", 2.0, 6.0,
                                                           value=SCALPING_CONFIG_APP["min_score"],
                                                           step=0.5, key="tab3_min_score")
        
        if st.button("Analyze", key="analyze_btn", type="primary"):
            if symbol_input:
                with st.spinner("Analyzing..."):
                    try:
                        symbol = symbol_input.upper()
                        
                        # Format simbol
                        formatted_symbol = format_symbol_for_mode(
                            symbol, 
                            bot.mode,
                            getattr(bot, 'trading_mode', 'spot')
                        )
                        
                        st.info(f"Analyzing: {formatted_symbol}")
                        
                        analysis = bot.analyze_asset(formatted_symbol)
                        if analysis:
                            # Apply scalping config jika ada
                            if analysis_config:
                                analysis['min_score_threshold'] = analysis_config.get('min_score', 2.5)
                                analysis['scalping_mode'] = True
                            
                            analysis = validate_and_fix_price_levels(analysis, formatted_symbol, bot)
                            
                            analysis['formatted_symbol'] = formatted_symbol
                            analysis['original_input'] = symbol
                            
                            # Hitung probabilitas TP
                            tp1, tp2, tp3 = safe_get(analysis, 'tp1', 0), safe_get(analysis, 'tp2', 0), safe_get(analysis, 'tp3', 0)
                            action = safe_get(analysis, 'action', 'LONG')
                            current_price = get_valid_price(analysis, formatted_symbol, bot)
                            
                            analysis['tp_probabilities'] = calculate_tp_probability(
                                current_price, tp1, tp2, tp3, safe_get(analysis, 'sl', 0), action
                            )
                            
                            st.session_state.selected_analysis = analysis
                            st.success("Analysis complete!")
                        else:
                            st.error("Analysis failed")
                    except Exception as e:
                        st.error(f"Analysis error: {e}")
        
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
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Action", safe_get(analysis, 'action', 'NEUTRAL'))
                st.metric("Score", safe_get(analysis, 'score', 0))
                st.metric("Current Price", f"{get_valid_price(analysis, safe_get(analysis, 'symbol'), bot):.5f}")
                st.metric("Trend", safe_get(analysis, 'trend', 'NEUTRAL'))
                
                # HAPUS: Bias info
            
            with col2:
                st.metric("RSI", f"{safe_get(analysis, 'rsi', 0):.1f}")
                st.metric("Volume Ratio", f"{safe_get(analysis, 'volume_ratio', 0):.2f}")
                st.metric("ATR", f"{safe_get(analysis, 'atr', 0):.5f}")
                
                if 'tp_probabilities' in analysis:
                    probs = analysis['tp_probabilities']
                    st.metric("TP1 Probability", f"{probs.get('tp1', 0)*100:.1f}%")
            
            # Entry Range Details
            st.subheader("🎯 Entry Range Details")
            col_range1, col_range2, col_range3 = st.columns(3)
            with col_range1:
                st.metric("Entry Range Low", f"{analysis.get('entry_range_low', 0):.5f}")
            with col_range2:
                st.metric("Entry Range High", f"{analysis.get('entry_range_high', 0):.5f}")
            with col_range3:
                st.metric("Ideal Entry", f"{analysis.get('best_entry', 0):.5f}")

    # Tab 4: Custom Entry Calculator (TANPA Open Position)
    with tab4:
        st.subheader("🎯 Custom Entry Calculator")
        
        # Mode info
        mode_info = []
        if hasattr(bot, 'trading_mode'):
            mode_display = "🔄 Spot" if bot.trading_mode == "spot" else "⚡ Futures"
            mode_info.append(f"**Trading Mode:** {mode_display}")
        
        if st.session_state.scalping_mode:
            mode_info.append("⚡ **SCALPING:** ON")
        
        if mode_info:
            st.info(" | ".join(mode_info))
        
        # ============================================
        # STEP 1: Pilih Aset dari Scan Results
        # ============================================
        st.subheader("📌 Step 1: Select Asset from Scan")
        
        # Tampilkan assets dari scan results
        if st.session_state.scanned_results or st.session_state.scalping_results:
            # Pilih results berdasarkan mode
            if st.session_state.scalping_mode and st.session_state.scalping_results:
                available_assets = st.session_state.scalping_results
            else:
                available_assets = st.session_state.scanned_results
            
            # Buat dropdown untuk memilih asset
            asset_options = {}
            for asset in available_assets[:20]:  # Limit 20 assets
                if isinstance(asset, dict) and 'symbol' in asset:
                    symbol = asset['symbol']
                    action = asset.get('action', 'NEUTRAL')
                    score = asset.get('score', 0)
                    price = get_valid_price(asset, symbol, bot)
                    
                    display_text = f"{symbol} - {action} (Score: {score:.1f}) - Price: ${price:.4f}"
                    asset_options[display_text] = asset
            
            if asset_options:
                selected_asset_display = st.selectbox(
                    "Choose an asset from scan results:",
                    options=list(asset_options.keys()),
                    key="select_asset_dropdown"
                )
                
                if selected_asset_display:
                    selected_asset = asset_options[selected_asset_display]
                    symbol_selected = selected_asset['symbol']
                    action_selected = selected_asset.get('action', 'LONG')
                    
                    # Tampilkan info asset yang dipilih
                    col_sel1, col_sel2 = st.columns([3, 1])
                    with col_sel1:
                        st.success(f"✅ Selected: **{symbol_selected}**")
                        st.write(f"Action: `{action_selected}` | Score: `{selected_asset.get('score', 0):.1f}`")
                        st.write(f"Current Price: `{get_valid_price(selected_asset, symbol_selected, bot):.5f}`")
                    
                    with col_sel2:
                        if st.button("📌 Use This Asset", key="use_selected_asset"):
                            st.session_state.selected_for_entry = {symbol_selected: selected_asset}
                            st.session_state.custom_symbol = symbol_selected
                            st.session_state.custom_action = action_selected
                            st.rerun()
        else:
            st.warning("No assets available from scan. Please scan assets first in Tab 1.")
        
        st.divider()
        
        # ============================================
        # STEP 2: Input Entry Price Manual (FIXED)
        # ============================================
        st.subheader("💰 Step 2: Enter Entry Details")
        
        col_symbol, col_action, col_entry = st.columns([2, 1, 2])
        
        with col_symbol:
            # Auto-fill symbol jika ada selected asset
            default_symbol = ""
            if st.session_state.selected_for_entry:
                first_symbol = list(st.session_state.selected_for_entry.keys())[0]
                default_symbol = first_symbol
            elif hasattr(st.session_state, 'custom_symbol'):
                default_symbol = st.session_state.custom_symbol
            
            symbol_custom = st.text_input("Symbol:", 
                                         value=default_symbol,
                                         key="custom_symbol_input", 
                                         placeholder="BTC/USDT or BTC/USDT:USDT")
        
        with col_action:
            # Auto-fill action jika ada selected asset
            default_action = "LONG"
            if st.session_state.selected_for_entry and default_symbol:
                data = st.session_state.selected_for_entry.get(default_symbol, {})
                default_action = data.get('action', 'LONG')
            elif hasattr(st.session_state, 'custom_action'):
                default_action = st.session_state.custom_action
            
            action_custom = st.selectbox("Action:", ["LONG", "SHORT"], 
                                        index=0 if default_action == "LONG" else 1,
                                        key="custom_action_select")
        
        with col_entry:
            # Input entry price manual - PERBAIKAN ERROR DI SINI
            default_price = 0.0
            if st.session_state.selected_for_entry and default_symbol:
                data = st.session_state.selected_for_entry.get(default_symbol, {})
                default_price = data.get('current_price', data.get('entry_price', 0))
            
            # FIX: Ensure default_price >= min_value
            safe_default_price = max(float(default_price), 0.00001) if default_price else 0.00001
            
            entry_price_custom = st.number_input(
                "Entry Price (Manual):", 
                value=safe_default_price,  # Gunakan nilai yang sudah aman
                min_value=0.00001,
                step=0.0001, 
                format="%.5f",
                key="custom_entry_price"
            )
            
            # Quick price buttons
            col_price1, col_price2, col_price3 = st.columns(3)
            with col_price1:
                if st.button("-1%", key="price_minus_1"):
                    if entry_price_custom > 0.00001:
                        st.session_state.custom_entry_price = max(entry_price_custom * 0.99, 0.00001)
                        st.rerun()
            with col_price2:
                if st.button("+1%", key="price_plus_1"):
                    if entry_price_custom > 0:
                        st.session_state.custom_entry_price = entry_price_custom * 1.01
                        st.rerun()
            with col_price3:
                if st.button("Reset", key="price_reset"):
                    st.session_state.custom_entry_price = safe_default_price
                    st.rerun()
        
        st.divider()
        
        # ============================================
        # STEP 3: Simpan ke Session State untuk Open Position
        # ============================================
        st.subheader("📝 Step 3: Save for Open Position")
        
        if st.button("💾 Save Entry Details", key="save_custom_entry", type="primary"):
            if symbol_custom and entry_price_custom > 0:
                # Simpan data ke session state
                st.session_state.saved_custom_entry = {
                    'symbol': symbol_custom,
                    'action': action_custom,
                    'entry_price': entry_price_custom,
                    'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                st.success("✅ Entry details saved!")
                st.info("Entry details have been saved. You can now analyze this asset in other tabs.")
            else:
                st.warning("⚠️ Please enter symbol and valid entry price")
        
        # Tampilkan saved entry jika ada
        saved_entry = st.session_state.get('saved_custom_entry')
        if saved_entry is not None and isinstance(saved_entry, dict):
            st.divider()
            st.subheader("💾 Saved Entry Details")
            col1, col2 = st.columns(2)
            with col1:
                st.write(f"**Symbol:** {safe_get(saved_entry, 'symbol', 'N/A')}")
                st.write(f"**Action:** {safe_get(saved_entry, 'action', 'N/A')}")
            with col2:
                st.write(f"**Entry Price:** {safe_get(saved_entry, 'entry_price', 0):.5f}")
                st.write(f"**Saved at:** {safe_get(saved_entry, 'timestamp', 'N/A')}")
            
            if st.button("🗑️ Clear Saved Entry", key="clear_saved_entry"):
                st.session_state.saved_custom_entry = None
                st.rerun()

    # Tab 6: Positions - PERBAIKAN dengan tambahan test positions (sebelumnya Tab 7, sekarang jadi Tab 6)
    with tab6:
        st.subheader("💼 Active Positions")
        
        # Mode info
        mode_info = []
        if hasattr(bot, 'trading_mode'):
            mode_display = "🔄 Spot" if bot.trading_mode == "spot" else "⚡ Futures"
            mode_info.append(f"**Trading Mode:** {mode_display}")
        
        if st.session_state.scalping_mode:
            mode_info.append("⚡ **SCALPING:** ON")
        
        if mode_info:
            st.info(" | ".join(mode_info))
        
        # Refresh positions
        if st.button("🔄 Refresh Positions", key="refresh_positions", type="primary"):
            try:
                st.session_state.positions_data = bot.get_active_positions()
                st.success("✅ Positions refreshed successfully!")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Refresh error: {e}")
        
        # Display regular positions
        if not st.session_state.positions_data:
            st.info("📭 No active positions")
        else:
            # Filter positions for scalping jika mode aktif
            positions_to_display = st.session_state.positions_data
            
            if st.session_state.scalping_mode:
                # Tambahkan info scalping untuk posisi yang sesuai
                for pos in positions_to_display:
                    if isinstance(pos, dict):
                        symbol = safe_get(pos, 'symbol')
                        if symbol:
                            # Cek apakah ini scalping position (based on entry range size)
                            entry_range_size = pos.get('range_size', 0)
                            if entry_range_size < 2.0:  # Entry range kecil = kemungkinan scalping
                                pos['scalping_position'] = True
                            else:
                                pos['scalping_position'] = False
            
            for pos in positions_to_display:
                try:
                    if isinstance(pos, tuple):
                        position_id = pos[0]
                        symbol = pos[1]
                        action = pos[3]
                        entry_price = float(pos[4])
                        current_price = float(pos[6]) if len(pos) > 6 and pos[6] else entry_price
                        tp1 = float(pos[7]) if len(pos) > 7 and pos[7] else 0
                        tp2 = float(pos[8]) if len(pos) > 8 and pos[8] else 0
                        tp3 = float(pos[9]) if len(pos) > 9 and pos[9] else 0
                        sl = float(pos[10]) if len(pos) > 10 and pos[10] else 0
                    else:
                        position_id = safe_get(pos, 'id')
                        symbol = safe_get(pos, 'symbol')
                        action = safe_get(pos, 'action')
                        entry_price = float(safe_get(pos, 'entry_price'))
                        current_price = float(safe_get(pos, 'current_price', entry_price))
                        tp1 = float(safe_get(pos, 'tp1', 0))
                        tp2 = float(safe_get(pos, 'tp2', 0))
                        tp3 = float(safe_get(pos, 'tp3', 0))
                        sl = float(safe_get(pos, 'sl', 0))
                    
                    # Format display
                    display_symbol = convert_symbol_for_display(
                        symbol,
                        bot.mode,
                        getattr(bot, 'trading_mode', 'spot')
                    )
                    
                    # Hitung P/L
                    if action == "LONG":
                        pl_pct = ((current_price - entry_price) / entry_price) * 100
                        pl_emoji = "📈" if pl_pct >= 0 else "📉"
                    else:
                        pl_pct = ((entry_price - current_price) / entry_price) * 100
                        pl_emoji = "📈" if pl_pct >= 0 else "📉"
                    
                    pl_color = "green" if pl_pct >= 0 else "red"
                    
                    # Tampilkan position card
                    with st.container():
                        col1, col2, col3 = st.columns([3, 2, 1])
                        
                        with col1:
                            # Scalping indicator jika ada
                            scalping_indicator = ""
                            if pos.get('scalping_position'):
                                scalping_indicator = "⚡ "
                            
                            st.write(f"**{scalping_indicator}{display_symbol}** - {action} {pl_emoji}")
                            st.write(f"🏁 Entry: `{entry_price:.5f}`")
                            st.write(f"📊 Current: `{current_price:.5f}`")
                            st.write(f"💰 P/L: <span style='color:{pl_color}; font-weight:bold'>{pl_pct:+.2f}%</span>", unsafe_allow_html=True)
                        
                        with col2:
                            st.write(f"🎯 **TP1:** `{tp1:.5f}`")
                            st.write(f"🎯 **TP2:** `{tp2:.5f}`")
                            st.write(f"🎯 **TP3:** `{tp3:.5f}`")
                            st.write(f"🛑 **SL:** `{sl:.5f}`")
                        
                        with col3:
                            close_key = f"close_{position_id}_{symbol}"
                            if st.button("❌ Close", key=close_key, type="secondary"):
                                try:
                                    success = bot.close_position(position_id, current_price)
                                    if success:
                                        st.success(f"✅ {display_symbol} position closed!")
                                        time.sleep(1)
                                        st.session_state.positions_data = bot.get_active_positions()
                                        st.rerun()
                                    else:
                                        st.error(f"❌ Failed to close {display_symbol}")
                                except Exception as close_error:
                                    st.error(f"❌ Close error: {close_error}")
                    
                    st.markdown("---")
                    
                except Exception as e:
                    st.error(f"❌ Position error: {e}")
        
        # 🔥 PERBAIKAN: Tampilkan test positions jika ada
        if hasattr(st.session_state, 'test_positions') and st.session_state.test_positions:
            st.subheader("🧪 Test Positions (Session Only)")
            
            for pos in st.session_state.test_positions:
                col1, col2, col3 = st.columns([3, 2, 1])
                
                with col1:
                    display_symbol = convert_symbol_for_display(
                        pos['symbol'],
                        bot.mode,
                        getattr(bot, 'trading_mode', 'spot')
                    )
                    
                    # Hitung P/L berdasarkan current price (gunakan entry sebagai current untuk testing)
                    current_price = pos['entry_price']  # Untuk testing, gunakan entry price sebagai current
                    
                    if pos['action'] == "LONG":
                        pl_pct = ((current_price - pos['entry_price']) / pos['entry_price']) * 100
                    else:
                        pl_pct = ((pos['entry_price'] - current_price) / pos['entry_price']) * 100
                    
                    pl_color = "green" if pl_pct >= 0 else "red"
                    pl_emoji = "📈" if pl_pct >= 0 else "📉"
                    
                    st.write(f"**{display_symbol}** - {pos['action']} {pl_emoji}")
                    st.write(f"🏁 Entry: `{pos['entry_price']:.5f}`")
                    st.write(f"📊 Current: `{current_price:.5f}`")
                    st.write(f"💰 P/L: <span style='color:{pl_color}; font-weight:bold'>{pl_pct:+.2f}%</span>", unsafe_allow_html=True)
                    st.write(f"📏 Size: `{pos['position_size']:.4f}` (${pos['position_value']:.2f})")
                
                with col2:
                    st.write(f"🎯 **TP1:** `{pos['tp1']:.5f}`")
                    st.write(f"🎯 **TP2:** `{pos['tp2']:.5f}`")
                    st.write(f"🎯 **TP3:** `{pos['tp3']:.5f}`")
                    st.write(f"🛑 **SL:** `{pos['sl']:.5f}`")
                
                with col3:
                    st.write(f"⏰ {pos['timestamp']}")
                    close_key = f"close_test_{pos['id']}"
                    if st.button("❌ Close", key=close_key, type="secondary"):
                        # Remove dari session state
                        st.session_state.test_positions = [p for p in st.session_state.test_positions if p['id'] != pos['id']]
                        st.success(f"Test position {display_symbol} closed!")
                        st.rerun()
                
                st.divider()

    # Tab 7: History (sebelumnya Tab 8, sekarang jadi Tab 7)
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
                    st.write(f"Entry: `{entry_price:.5f}` | Exit: `{exit_price:.5f}`")
                    st.write(f"P/L: <span style='color:{color}'>{profit_loss:.5f}</span>", unsafe_allow_html=True)
                    st.markdown("---")
                except Exception as e:
                    st.error(f"History error: {e}")

    # Tab 8: Live Scanner (sebelumnya Tab 9, sekarang jadi Tab 8)
    with tab8:
        st.subheader("📡 Live Scanner")
        
        # Mode info
        mode_info = []
        if hasattr(bot, 'trading_mode'):
            mode_display = "🔄 Spot" if bot.trading_mode == "spot" else "⚡ Futures"
            mode_info.append(f"**Trading Mode:** {mode_display}")
        
        if st.session_state.scalping_mode:
            mode_info.append("⚡ **SCALPING:** ON")
        
        if mode_info:
            st.info(" | ".join(mode_info))
        
        col1, col2 = st.columns([1, 3])
        with col1:
            if st.button("🚀 Mulai Live Monitoring" if not st.session_state.live_monitoring else "⏹️ Hentikan Live Monitoring", 
                        key="toggle_live", type="primary"):
                st.session_state.live_monitoring = not st.session_state.live_monitoring
                st.rerun()
        
        with col2:
            auto_refresh_live = st.checkbox("🔄 Auto Refresh setiap 10 detik", value=True, key="auto_refresh_live")
        
        if st.session_state.live_monitoring:
            st.info("📡 Live monitoring aktif. Harga real-time akan ditampilkan.")
            
            if st.button("🔄 Refresh Sekarang", key="manual_refresh_live"):
                st.rerun()
            
            if st.session_state.positions_data:
                st.subheader("📊 Posisi Aktif - Live Prices")
                
                for pos in st.session_state.positions_data:
                    try:
                        symbol = safe_get(pos, 'symbol')
                        if not symbol:
                            continue
                        
                        # Dapatkan harga real-time
                        try:
                            if hasattr(bot, 'data_provider') and bot.data_provider:
                                ticker = bot.data_provider.get_ticker(symbol)
                                if ticker and 'last' in ticker:
                                    latest_price = float(ticker['last'])
                                else:
                                    latest_price = safe_get(pos, 'current_price', safe_get(pos, 'entry_price'))
                            else:
                                latest_price = safe_get(pos, 'current_price', safe_get(pos, 'entry_price'))
                        except:
                            latest_price = safe_get(pos, 'current_price', safe_get(pos, 'entry_price'))
                        
                        entry_price = float(safe_get(pos, 'entry_price'))
                        action = safe_get(pos, 'action')
                        
                        # Format display
                        display_symbol = convert_symbol_for_display(
                            symbol,
                            bot.mode,
                            getattr(bot, 'trading_mode', 'spot')
                        )
                        
                        # Hitung perubahan
                        if action == "LONG":
                            change_pct = ((latest_price - entry_price) / entry_price) * 100
                        else:
                            change_pct = ((entry_price - latest_price) / entry_price) * 100
                        
                        color = "green" if change_pct >= 0 else "red"
                        emoji = "📈" if change_pct >= 0 else "📉"
                        
                        # Tampilkan data live
                        col_live1, col_live2, col_live3 = st.columns([2, 2, 1])
                        with col_live1:
                            st.write(f"**{display_symbol}** - {action}")
                            st.write(f"🏁 Entry: `{entry_price:.5f}`")
                        with col_live2:
                            st.write(f"{emoji} Live: `{latest_price:.5f}`")
                            st.write(f"💰 Change: <span style='color:{color}; font-weight:bold'>{change_pct:+.2f}%</span>", unsafe_allow_html=True)
                        
                        st.markdown("---")
                        
                    except Exception as e:
                        st.error(f"❌ Error updating {symbol}: {str(e)}")
                
                # Auto-refresh
                if auto_refresh_live:
                    time.sleep(10)
                    st.rerun()
                    
            else:
                st.info("📭 Tidak ada posisi aktif untuk di-monitor")
        else:
            st.info("👉 Klik 'Mulai Live Monitoring' untuk memantau harga real-time.")

    # Tab 9: ML Backtest (sebelumnya Tab 10, sekarang jadi Tab 9)
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
                    # HAPUS slider untuk long_bias, tampilkan info
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

    # Tab 10: Portfolio Optimization (sebelumnya Tab 11, sekarang jadi Tab 10)
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
                
                # Scalping indicator
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
    # Initialize session state
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
    if 'username' not in st.session_state:
        st.session_state.username = ""
    
    # Initialize scalping config
    if 'scalping_config' not in st.session_state:
        st.session_state.scalping_config = SCALPING_CONFIG_APP

    # Initialize selected_for_entry
    if 'selected_for_entry' not in st.session_state:
        st.session_state.selected_for_entry = {}
    
    # Initialize selected_symbol_display
    if 'selected_symbol_display' not in st.session_state:
        st.session_state.selected_symbol_display = None
    
    # Initialize last_selected
    if 'last_selected' not in st.session_state:
        st.session_state.last_selected = None
    
    # ✅ PERBAIKAN: Inisialisasi dengan None secara eksplisit
    if 'saved_custom_entry' not in st.session_state:
        st.session_state.saved_custom_entry = None
    
    # Initialize open_position_result
    if 'open_position_result' not in st.session_state:
        st.session_state.open_position_result = None
    
    # Initialize open_position_risk
    if 'open_position_risk' not in st.session_state:
        st.session_state.open_position_risk = None

    # Show login or main app
    if not st.session_state.logged_in:
        login_section()
    else:
        main_app()

if __name__ == "__main__":
    main()
