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
            ticker = bot.data_provider.get_ticker(symbol)
            if ticker:
                # Cari key harga
                for key in ['last', 'close', 'current', 'price', 'markPrice']:
                    if key in ticker and ticker[key]:
                        return float(ticker[key])
        
        # Fallback: coba dari method lain
        if hasattr(bot, 'get_current_price'):
            return bot.get_current_price(symbol)
        
        return None
    except Exception as e:
        print(f"❌ Error getting real-time price for {symbol}: {e}")
        return None

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
# PERBAIKAN 2: Fungsi Open Position - ENHANCED
# ====================================
def open_position(symbol, action, entry_price=None, tp1=None, tp2=None, tp3=None, sl=None, 
                  position_size=100, risk_percent=1):
    """Open a new position dengan real-time price jika tidak ada entry_price"""
    try:
        bot = st.session_state.bot_instance
        
        # Jika entry_price tidak diberikan, ambil harga real-time
        if entry_price is None or entry_price <= 0:
            real_time_price = get_real_time_price(symbol, bot)
            if real_time_price and real_time_price > 0:
                entry_price = real_time_price
                print(f"✅ Using real-time price for {symbol}: ${entry_price}")
            else:
                # Ambil dari analysis data jika ada
                if symbol in st.session_state.selected_for_entry:
                    analysis = st.session_state.selected_for_entry[symbol]
                    entry_price = get_valid_price(analysis, symbol, bot)
        
        # Jika masih tidak valid, gunakan harga default
        if entry_price is None or entry_price <= 0:
            entry_price = 1.0
            print(f"⚠️ Using fallback price for {symbol}: ${entry_price}")
        
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
            'position_value': position_size * entry_price,
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

def update_all_positions_prices(bot):
    """Update semua harga posisi dengan data real-time"""
    updated_positions = []
    
    # Update positions dari database
    if hasattr(bot, 'get_active_positions'):
        try:
            positions = bot.get_active_positions()
            for pos in positions:
                if isinstance(pos, dict) and pos.get('status') == 'open':
                    symbol = pos.get('symbol')
                    if symbol:
                        new_price = get_valid_price({}, symbol, bot)
                        if new_price > 0:
                            pos['current_price'] = new_price
                            updated_positions.append(pos)
        except Exception as e:
            print(f"⚠️ Error updating database positions: {e}")
    
    # Update positions dari session state
    if hasattr(st.session_state, 'test_positions'):
        for pos in st.session_state.test_positions:
            if pos.get('status') == 'open':
                symbol = pos.get('symbol')
                if symbol:
                    new_price = get_valid_price({}, symbol, bot)
                    if new_price > 0:
                        pos['current_price'] = new_price
                        updated_positions.append(pos)
    
    return updated_positions

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
                if key not in ['logged_in', 'username']:
                    del st.session_state[key]
            st.session_state.logged_in = False
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
        st.session_state.show_all_positions = False  # ✅ PERBAIKAN: Initialize here

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
                    
                    with col_info2:
                        current_price = get_valid_price(data, symbol, bot)
                        st.info(f"**Current Price:** ${current_price:,.5f}")
                        
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
                        entry_price = st.number_input(
                            "Entry Price ($):",
                            value=float(default_entry),
                            min_value=0.00001,
                            step=0.0001,
                            format="%.5f",
                            key=f"entry_price_{symbol}"
                        )
                        
                        # Position size
                        position_size = st.number_input(
                            "Position Size ($):",
                            value=100.0,
                            min_value=10.0,
                            step=10.0,
                            key=f"position_size_{symbol}"
                        )
                        
                        # Risk percentage
                        risk_percent = st.slider(
                            "Risk %:",
                            0.5, 5.0, 1.0, 0.5,
                            key=f"risk_percent_{symbol}"
                        )
                        
                        risk_amount = position_size * (risk_percent / 100)
                        st.metric("Risk Amount", f"${risk_amount:,.2f}")
                    
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
                            "TP1 ($):",
                            value=tp1_default,
                            min_value=0.00001,
                            step=0.0001,
                            format="%.5f",
                            key=f"tp1_{symbol}"
                        )
                        
                        tp2 = st.number_input(
                            "TP2 ($):",
                            value=tp2_default,
                            min_value=0.00001,
                            step=0.0001,
                            format="%.5f",
                            key=f"tp2_{symbol}"
                        )
                        
                        tp3 = st.number_input(
                            "TP3 ($):",
                            value=tp3_default,
                            min_value=0.00001,
                            step=0.0001,
                            format="%.5f",
                            key=f"tp3_{symbol}"
                        )
                        
                        sl = st.number_input(
                            "Stop Loss ($):",
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
                                st.caption(f"Reward: ${reward_tp1:,.2f}")
                            with col_rr2:
                                st.metric("TP2 R/R", f"{reward_tp2/risk:.2f}:1")
                                st.caption(f"Reward: ${reward_tp2:,.2f}")
                            with col_rr3:
                                st.metric("TP3 R/R", f"{reward_tp3/risk:.2f}:1")
                                st.caption(f"Reward: ${reward_tp3:,.2f}")
                            
                            st.metric("Risk Amount", f"${risk:,.2f}", f"{risk/entry_price*100:.1f}%")
                    
                    # Tombol Open Position
                    st.divider()
                    col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 2])
                    
                    with col_btn1:
                        if st.button(f"📈 OPEN POSITION", key=f"open_position_tab1_{symbol}", type="primary"):
                            # Save parameters to session
                            st.session_state[f'manual_entry_{symbol}'] = entry_price
                            
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
                                                st.success(f"💰 Current Price: ${current_price:,.2f}")
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
                            st.success(f"✅ Provider active! BTC Price: ${ticker.get('last', 'N/A')}")
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
                                st.success(f"✅ Price updated: ${new_price:,.2f}")
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
                st.metric("Current Price", f"${current_price:,.5f}")
                
                st.metric("Trend", safe_get(analysis, 'trend', 'NEUTRAL'))
                
            with col2:
                st.metric("RSI", f"{safe_get(analysis, 'rsi', 0):.1f}")
                st.metric("Volume Ratio", f"{safe_get(analysis, 'volume_ratio', 0):.2f}")
                st.metric("ATR", f"{safe_get(analysis, 'atr', 0):.5f}")
                
                if 'tp_probabilities' in analysis:
                    probs = analysis['tp_probabilities']
                    st.metric("TP1 Probability", f"{probs.get('tp1', 0)*100:.1f}%")
            
            # Entry Range Details
            st.subheader("🎯 Entry Range & TP/SL Levels")
            col_range1, col_range2, col_range3, col_range4 = st.columns(4)
            with col_range1:
                entry_low = analysis.get('entry_range_low', 0)
                st.metric("Entry Range Low", f"${entry_low:,.5f}")
            with col_range2:
                entry_high = analysis.get('entry_range_high', 0)
                st.metric("Entry Range High", f"${entry_high:,.5f}")
            with col_range3:
                best_entry = analysis.get('best_entry', 0)
                st.metric("Ideal Entry", f"${best_entry:,.5f}")
            with col_range4:
                range_size = analysis.get('range_size', 0)
                st.metric("Range Size", f"{range_size:.2f}%")
            
            # TP/SL Levels
            st.subheader("🎯 Take Profit & Stop Loss")
            tp_col1, tp_col2, tp_col3, sl_col = st.columns(4)
            with tp_col1:
                tp1 = analysis.get('tp1', 0)
                st.metric("TP1", f"${tp1:,.5f}")
            with tp_col2:
                tp2 = analysis.get('tp2', 0)
                st.metric("TP2", f"${tp2:,.5f}")
            with tp_col3:
                tp3 = analysis.get('tp3', 0)
                st.metric("TP3", f"${tp3:,.5f}")
            with sl_col:
                sl = analysis.get('sl', 0)
                st.metric("Stop Loss", f"${sl:,.5f}")
            
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
                st.write(f"Current Price: `${entry_price:,.5f}`")
                st.write(f"Entry Range: `${analysis.get('entry_range_low', 0):,.5f}` - `${analysis.get('entry_range_high', 0):,.5f}`")
            
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
            default_price = st.session_state.get('custom_entry_price', 0.0)
            safe_default_price = max(float(default_price), 0.00001)
            
            entry_price_custom = st.number_input(
                "Entry Price ($):", 
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
                                st.success(f"✅ Current price: ${current_price:,.5f}")
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
                "Position Size ($):",
                value=100.0,
                min_value=10.0,
                step=10.0,
                key="position_size_input_tab4"
            )
        
        with col_risk:
            risk_percent = st.slider("Risk %:", 0.5, 5.0, 1.0, 0.5, key="risk_percent_tab4")
            risk_amount = position_size * (risk_percent / 100)
            st.metric("Risk Amount", f"${risk_amount:,.2f}")
        
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
                st.info(f"**TP1:** `${tp1_auto:,.5f}`")
                st.info(f"**TP2:** `${tp2_auto:,.5f}`")
                st.info(f"**TP3:** `${tp3_auto:,.5f}`")
            with col_show2:
                st.warning(f"**Stop Loss:** `${sl_auto:,.5f}`")
                
        else:  # Manual Input
            st.info("Enter TP/SL values manually:")
            
            col_manual1, col_manual2 = st.columns(2)
            with col_manual1:
                # Load from session state if exists
                default_tp1 = st.session_state.get('custom_tp1', 0)
                default_tp2 = st.session_state.get('custom_tp2', 0)
                default_tp3 = st.session_state.get('custom_tp3', 0)
                
                tp1_custom = st.number_input(
                    "TP1 ($):",
                    value=max(default_tp1, entry_price_custom * 1.02),
                    min_value=0.00001,
                    step=0.01,
                    format="%.5f",
                    key="manual_tp1"
                )
                
                tp2_custom = st.number_input(
                    "TP2 ($):",
                    value=max(default_tp2, entry_price_custom * 1.04),
                    min_value=0.00001,
                    step=0.01,
                    format="%.5f",
                    key="manual_tp2"
                )
                
                tp3_custom = st.number_input(
                    "TP3 ($):",
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
                    "Stop Loss ($):",
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
                    st.caption(f"Reward: ${reward_tp1:,.2f}")
                with col_rr2:
                    st.metric("TP2 R/R", f"{rr2:.2f}:1")
                    st.caption(f"Reward: ${reward_tp2:,.2f}")
                with col_rr3:
                    st.metric("TP3 R/R", f"{rr3:.2f}:1")
                    st.caption(f"Reward: ${reward_tp3:,.2f}")
                
                st.metric("Risk Amount", f"${risk:,.2f}", f"{risk/entry_price_custom*100:.1f}%")
        
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
                    st.write(f"Entry: `${pos['entry_price']:,.5f}` | Size: `${pos['position_size']:,.2f}`")
                    st.write(f"TP1: `${pos['tp1']:,.5f}` | SL: `${pos['sl']:,.5f}`")
                    st.write(f"Risk: {pos['risk_percent']}% (${pos['position_size'] * pos['risk_percent']/100:,.2f})")
                with col_pos2:
                    st.write(f"⏰ {pos['timestamp']}")
                    if pos.get('saved_to_db'):
                        st.success("✅ In Database")
                    else:
                        st.warning("⚠️ Session Only")

    # Tab 6: Positions - ENHANCED WITH DATABASE (PERBAIKAN 4)
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
        
        # Tambahkan tombol refresh real-time
        col_rt1, col_rt2 = st.columns([1, 3])
        with col_rt1:
            if st.button("💰 Update ALL Prices", key="update_all_prices_tab6", type="primary"):
                with st.spinner("Updating prices from real-time data..."):
                    # Update prices for all positions
                    updated_count = 0
                    
                    # Update session positions
                    if hasattr(st.session_state, 'test_positions'):
                        for pos in st.session_state.test_positions:
                            if pos.get('status') == 'open':
                                symbol = pos['symbol']
                                new_price = get_valid_price({}, symbol, bot)
                                if new_price > 0:
                                    pos['current_price'] = new_price
                                    updated_count += 1
                    
                    # Update database positions (jika ada)
                    if hasattr(bot, 'get_active_positions'):
                        try:
                            db_positions = bot.get_active_positions()
                            # Update setiap position dengan harga real-time
                            for pos in db_positions:
                                if isinstance(pos, dict) and pos.get('status') == 'open':
                                    symbol = pos.get('symbol')
                                    if symbol:
                                        new_price = get_valid_price({}, symbol, bot)
                                        if new_price > 0:
                                            pos['current_price'] = new_price
                        except:
                            pass
                    
                    st.success(f"✅ Updated {updated_count} positions!")
                    st.rerun()
        
        # Refresh positions button
        col_refresh1, col_refresh2 = st.columns([1, 3])
        with col_refresh1:
            if st.button("🔄 Refresh Positions", key="refresh_positions_tab6", type="primary"):
                try:
                    # Coba ambil dari database
                    if hasattr(bot, 'get_active_positions'):
                        db_positions = bot.get_active_positions()
                        if db_positions:
                            st.session_state.positions_data = db_positions
                            st.success(f"✅ Loaded {len(db_positions)} positions from database")
                        else:
                            # Fallback ke session state
                            if hasattr(st.session_state, 'test_positions'):
                                st.session_state.positions_data = st.session_state.test_positions
                                st.info(f"📋 Showing {len(st.session_state.test_positions)} positions from session")
                            else:
                                st.session_state.positions_data = []
                    else:
                        st.error("❌ Bot doesn't have get_active_positions method")
                    
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Refresh error: {e}")
        
        # Tampilkan positions
        positions_to_display = []
        
        # Prioritize database positions
        if st.session_state.positions_data:
            positions_to_display = st.session_state.positions_data
        
        # Add session positions jika tidak ada di database
        if hasattr(st.session_state, 'test_positions') and st.session_state.test_positions:
            session_positions = st.session_state.test_positions
            # Filter out positions that might already be in database
            db_symbols = [p.get('symbol') for p in positions_to_display if isinstance(p, dict)]
            for pos in session_positions:
                if pos.get('symbol') not in db_symbols:
                    positions_to_display.append(pos)
        
        if not positions_to_display:
            st.info("📭 No active positions")
            st.info("👉 Open a position in Tab 4 first!")
        else:
            # Display positions
            for pos in positions_to_display:
                try:
                    # Extract position data
                    if isinstance(pos, dict):
                        position_id = pos.get('id', '')
                        symbol = pos.get('symbol', '')
                        action = pos.get('action', 'LONG')
                        entry_price = float(pos.get('entry_price', 0))
                        current_price = float(pos.get('current_price', entry_price))
                        tp1 = float(pos.get('tp1', 0))
                        tp2 = float(pos.get('tp2', 0))
                        tp3 = float(pos.get('tp3', 0))
                        sl = float(pos.get('sl', 0))
                        position_size = float(pos.get('position_size', 100))
                        source = pos.get('source', 'unknown')
                    else:
                        # Handle tuple format (legacy)
                        continue
                    
                    if not symbol:
                        continue
                    
                    # Format display
                    display_symbol = convert_symbol_for_display(
                        symbol,
                        bot.mode,
                        getattr(bot, 'trading_mode', 'spot')
                    )
                    
                    # Hitung P/L
                    if action == "LONG":
                        pl_pct = ((current_price - entry_price) / entry_price) * 100
                        pl_value = (current_price - entry_price) * position_size
                    else:
                        pl_pct = ((entry_price - current_price) / entry_price) * 100
                        pl_value = (entry_price - current_price) * position_size
                    
                    # Tentukan warna dan emoji
                    if pl_pct > 0:
                        color = "green"
                        emoji = "📈"
                        status = "PROFIT"
                    elif pl_pct < 0:
                        color = "red"
                        emoji = "📉"
                        status = "LOSS"
                    else:
                        color = "gray"
                        emoji = "⚪"
                        status = "BREAKEVEN"
                    
                    # Tampilkan position card
                    with st.container():
                        col_pos1, col_pos2, col_pos3, col_pos4 = st.columns([2, 2, 2, 1])
                        
                        with col_pos1:
                            st.write(f"{emoji} **{display_symbol}**")
                            st.write(f"Action: `{action}`")
                            st.write(f"Entry: `{entry_price:.5f}`")
                            st.write(f"Size: `{position_size:.2f}`")
                        
                        with col_pos2:
                            st.write(f"💰 Current: `{current_price:.5f}`")
                            st.write(f"📍 Status: `{status}`")
                            st.write(f"Source: `{source if source else 'Database'}`")
                        
                        with col_pos3:
                            st.write(f"📊 P/L: <span style='color:{color}; font-weight:bold'>{pl_pct:+.2f}%</span>", unsafe_allow_html=True)
                            st.write(f"💰 Value: <span style='color:{color}'>${pl_value:+.2f}</span>", unsafe_allow_html=True)
                            st.write(f"🎯 TP1: `{tp1:.5f}`")
                            st.write(f"🛑 SL: `{sl:.5f}`")
                        
                        with col_pos4:
                            # Tombol update price individual
                            update_key = f"update_price_single_{position_id}_{symbol}"
                            if st.button("🔄 Update", key=update_key):
                                new_price = get_valid_price({}, symbol, bot)
                                if new_price > 0:
                                    # Update in session state
                                    if hasattr(st.session_state, 'test_positions'):
                                        for i, p in enumerate(st.session_state.test_positions):
                                            if p.get('id') == position_id:
                                                st.session_state.test_positions[i]['current_price'] = new_price
                                                st.success(f"✅ {display_symbol} updated to ${new_price:,.5f}")
                                                st.rerun()
                            
                            # Tombol close
                            close_key = f"close_position_{position_id}_{symbol}"
                            if st.button("❌ Close", key=close_key, type="secondary"):
                                with st.spinner("Closing position..."):
                                    try:
                                        success = False
                                        close_price = current_price
                                        
                                        # Try to close in database
                                        if hasattr(bot, 'close_position'):
                                            success = bot.close_position(position_id, close_price)
                                        
                                        # Also remove from session state if exists
                                        if hasattr(st.session_state, 'test_positions'):
                                            st.session_state.test_positions = [
                                                p for p in st.session_state.test_positions 
                                                if p.get('id') != position_id
                                            ]
                                        
                                        if success:
                                            st.success(f"✅ {display_symbol} closed!")
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
                    st.error(f"❌ Error displaying position: {e}")
                    continue

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

    # Tab 8: Live Scanner & Position Monitor - FIXED WITH REAL PRICES
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
        
        # Enhanced auto-refresh dengan real-time prices
        if st.session_state.live_monitoring:
            # Tampilkan real-time price update section
            st.subheader("💰 Real-time Price Updates")
            
            col_refresh_all, col_interval = st.columns([1, 2])
            with col_refresh_all:
                if st.button("🔄 Refresh ALL Prices Now", key="refresh_all_prices_now", type="primary"):
                    with st.spinner("Refreshing all prices..."):
                        if hasattr(st.session_state, 'test_positions'):
                            updated_count = 0
                            for pos in st.session_state.test_positions:
                                if pos['status'] == 'open':
                                    symbol = pos['symbol']
                                    # Dapatkan harga real-time
                                    current_price = get_valid_price({}, symbol, bot)
                                    if current_price > 0 and current_price != pos['current_price']:
                                        pos['current_price'] = current_price
                                        updated_count += 1
                            
                            st.success(f"✅ Updated {updated_count} positions with real-time prices!")
                            st.rerun()
            
            with col_interval:
                refresh_interval = st.slider("Auto-refresh interval (seconds):", 5, 60, 10, 5,
                                            key="refresh_interval_tab8")
        
        # Status monitoring
        col1, col2, col3, col4 = st.columns([1, 2, 1, 1])
        with col1:
            if st.button("🚀 Start Live Monitoring" if not st.session_state.live_monitoring else "⏹️ Stop Monitoring", 
                        key="toggle_live_tab8", type="primary"):
                st.session_state.live_monitoring = not st.session_state.live_monitoring
                st.rerun()
    
        with col2:
            auto_refresh_live = st.checkbox("🔄 Auto Refresh (10s)", value=True, key="auto_refresh_live_tab8")
        
        with col3:
            if st.button("🔄 Refresh Prices", key="refresh_prices_btn"):
                # Refresh semua harga posisi
                if hasattr(st.session_state, 'test_positions') and st.session_state.test_positions:
                    for pos in st.session_state.test_positions:
                        if pos['status'] == 'open' and hasattr(bot, 'data_provider'):
                            try:
                                ticker = bot.data_provider.get_ticker(pos['symbol'])
                                if ticker and 'last' in ticker:
                                    pos['current_price'] = float(ticker['last'])
                            except:
                                pass
                    st.success("✅ Prices refreshed!")
                    st.rerun()
        
        with col4:
            # ✅ PERBAIKAN: Gunakan key yang unik untuk tombol ini
            if st.button("📊 Show All", key="show_all_btn_tab8"):
                # Toggle untuk menunjukkan semua posisi
                st.session_state.show_all_positions = not st.session_state.show_all_positions
                st.rerun()
        
        if st.session_state.live_monitoring:
            st.success("📡 LIVE MONITORING ACTIVE")
            
            # Get positions
            positions_data = []
            
            # Prioritize database positions
            if hasattr(bot, 'get_active_positions'):
                try:
                    positions_data = bot.get_active_positions()
                except:
                    pass
            
            # Add session positions
            if hasattr(st.session_state, 'test_positions'):
                session_positions = st.session_state.test_positions
                # Filter hanya yang open jika tidak show all
                if not st.session_state.show_all_positions:
                    session_positions = [p for p in session_positions if p.get('status') == 'open']
                
                db_symbols = [p.get('symbol') for p in positions_data if isinstance(p, dict)]
                for pos in session_positions:
                    if pos.get('symbol') not in db_symbols:
                        positions_data.append(pos)
            
            if positions_data:
                st.subheader(f"📊 Active Positions ({len(positions_data)})")
                
                for pos in positions_data:
                    try:
                        # Extract position data
                        if isinstance(pos, dict):
                            symbol = pos.get('symbol', '')
                            action = pos.get('action', 'LONG')
                            entry_price = float(pos.get('entry_price', 0))
                            current_price = float(pos.get('current_price', entry_price))
                            position_id = pos.get('id', '')
                            position_size = float(pos.get('position_size', 100))
                            status = pos.get('status', 'open')
                        else:
                            continue
                        
                        if not symbol:
                            continue
                        
                        # Skip closed positions unless show_all
                        if status != 'open' and not st.session_state.show_all_positions:
                            continue
                        
                        # Get real-time price from provider
                        live_price = current_price
                        price_source = "Cached"
                        
                        if hasattr(bot, 'data_provider') and bot.data_provider:
                            try:
                                ticker = bot.data_provider.get_ticker(symbol)
                                if ticker and isinstance(ticker, dict) and 'last' in ticker:
                                    live_price = float(ticker['last'])
                                    price_source = "Live"
                                    # Update cache
                                    pos['current_price'] = live_price
                                else:
                                    # Simulate small change for demo
                                    import random
                                    price_change = random.uniform(-0.005, 0.005)
                                    live_price = current_price * (1 + price_change)
                                    price_source = "Simulated"
                            except Exception as e:
                                # Fallback to simulation
                                import random
                                price_change = random.uniform(-0.005, 0.005)
                                live_price = current_price * (1 + price_change)
                                price_source = "Simulated"
                        
                        # Format display
                        display_symbol = convert_symbol_for_display(
                            symbol,
                            bot.mode,
                            getattr(bot, 'trading_mode', 'spot')
                        )
                        
                        # Hitung P/L dengan live price
                        if action == "LONG":
                            pl_pct = ((live_price - entry_price) / entry_price) * 100
                            pl_value = (live_price - entry_price) * position_size
                        else:
                            pl_pct = ((entry_price - live_price) / entry_price) * 100
                            pl_value = (entry_price - live_price) * position_size
                        
                        # Tampilkan live data
                        with st.container():
                            col_live1, col_live2, col_live3, col_live4 = st.columns([2, 2, 2, 1])
                            
                            with col_live1:
                                status_emoji = "🟢" if status == 'open' else "🔴" if status == 'closed' else "⚪"
                                st.write(f"{status_emoji} **{display_symbol}**")
                                st.write(f"Action: `{action}` | Status: `{status}`")
                                st.write(f"🏁 Entry: `${entry_price:,.5f}`")
                                st.write(f"Size: `${position_size:,.2f}`")
                            
                            with col_live2:
                                price_color = "🟢" if live_price > current_price else "🔴" if live_price < current_price else "⚪"
                                st.write(f"{price_color} {price_source} Price: `${live_price:,.5f}`")
                                if price_source != "Live":
                                    change_pct = ((live_price - current_price) / current_price) * 100
                                    st.write(f"📊 Change: `{change_pct:+.2f}%`")
                            
                            with col_live3:
                                color = "green" if pl_pct >= 0 else "red"
                                emoji = "📈" if pl_pct >= 0 else "📉"
                                st.write(f"{emoji} P/L: <span style='color:{color}; font-weight:bold'>{pl_pct:+.2f}%</span>", unsafe_allow_html=True)
                                st.write(f"💰 Value: <span style='color:{color}'>${pl_value:+,.2f}</span>", unsafe_allow_html=True)
                            
                            with col_live4:
                                # Update current price in position
                                update_key = f"update_price_{position_id}"
                                if st.button("🔄 Update", key=update_key):
                                    # Update in session state
                                    if hasattr(st.session_state, 'test_positions'):
                                        for i, p in enumerate(st.session_state.test_positions):
                                            if p.get('id') == position_id:
                                                st.session_state.test_positions[i]['current_price'] = live_price
                                                st.success(f"✅ {display_symbol} updated to ${live_price:,.5f}")
                                                st.rerun()
                    
                        st.divider()
                        
                    except Exception as e:
                        st.error(f"❌ Error updating {symbol}: {e}")
                        continue
                
                # Summary
                total_positions = len([p for p in positions_data if isinstance(p, dict) and p.get('status') == 'open'])
                if total_positions > 0:
                    st.info(f"📊 **Monitoring {total_positions} open positions**")
            
            else:
                st.info("📭 No active positions to monitor")
                st.info("👉 Open a position in Tab 4 first!")
            
            # Auto-refresh dengan cara yang lebih aman
            if auto_refresh_live and st.session_state.live_monitoring:
                # Gunakan st.experimental_rerun dengan delay
                time.sleep(10)
                st.rerun()
        else:
            st.info("👉 Click 'Start Live Monitoring' to begin tracking positions")

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
        'bot_instance': None,
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
