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

# ============================================
# 🔥 PERBAIKAN 1: PATH IMPORTS YANG BENAR
# ============================================
current_dir = os.path.dirname(os.path.abspath(__file__))

# Tambahkan semua path yang diperlukan
paths_to_add = [
    current_dir,                          # Root folder
    os.path.join(current_dir, "bot"),     # Folder bot
    os.path.join(current_dir, "database"), # Folder database
    os.path.join(current_dir, "bot", "strategies"),  # Folder strategies
    os.path.join(current_dir, "bot", "notifications"), # Folder notifications
]

for path in paths_to_add:
    if os.path.exists(path) and path not in sys.path:
        sys.path.insert(0, path)

print("📁 PATH SETUP:")
print(f"Current dir: {current_dir}")
print(f"Python path: {sys.path[:5]}")

# Try to import plotly
try:
    import plotly.graph_objects as go
    import plotly.express as px
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False
    print("⚠️ Plotly tidak tersedia, beberapa grafik tidak akan ditampilkan")
    # Buat dummy go object
    class DummyGo:
        def Figure(self): return None
        def Scatter(self, **kwargs): return None
    go = DummyGo()

# ============================================
# 🔥 PERBAIKAN 2: FUNGSI IMPORT TRADING BOT - DIPERBAIKI
# ============================================
def import_trading_bot():
    """Import TradingBot dari core.py di folder bot"""
    print("🔄 Mencoba import dari bot/core.py...")
    
    try:
        # Coba import EnhancedTradingBot dari core.py di folder bot
        from bot.core import EnhancedTradingBot
        print("✅ EnhancedTradingBot berhasil diimport dari bot.core")
        return EnhancedTradingBot
    except ImportError as e1:
        print(f"❌ Import dari bot.core gagal: {e1}")
        
        try:
            # Coba import dari core langsung
            from core import EnhancedTradingBot
            print("✅ EnhancedTradingBot berhasil diimport dari core")
            return EnhancedTradingBot
        except ImportError as e2:
            print(f"❌ Import dari core gagal: {e2}")
        
        # Buat minimal bot sebagai fallback
        print("⚠️ Membuat MinimalTradingBot sebagai fallback")
        class MinimalTradingBot:
            def __init__(self, config=None):
                self.mode = "crypto"
                self.trading_mode = "spot"
                self.config = config or {}
                self.data_provider = None
                self.db = None
                print("⚠️ MinimalTradingBot digunakan - fungsi terbatas")
            
            def set_mode(self, mode):
                self.mode = mode
                return True
            
            def scan_potential_assets(self, limit=25):
                """Scan assets - dummy implementation"""
                print(f"⚠️ Dummy scan dengan limit {limit}")
                return []
            
            def analyze_asset(self, symbol):
                """Analyze asset - dummy implementation"""
                print(f"⚠️ Dummy analyze untuk {symbol}")
                return {'action': 'NEUTRAL', 'score': 0, 'symbol': symbol}
            
            def get_active_positions(self):
                """Get active positions - dummy implementation"""
                print("⚠️ Dummy get_active_positions")
                return []
            
            def get_trade_history(self, limit=20):
                """Get trade history - dummy implementation"""
                print(f"⚠️ Dummy get_trade_history dengan limit {limit}")
                return []
            
            def get_current_price(self, symbol):
                """Get current price - dummy implementation"""
                print(f"⚠️ Dummy get_current_price untuk {symbol}")
                return 100.0
            
            def get_provider_health(self):
                """Get provider health - dummy implementation"""
                return {'status': 'dummy', 'provider_type': 'minimal'}
        
        return MinimalTradingBot

# ============================================
# 🔥 PERBAIKAN 3: FUNGSI INIT BOT - DIPERBAIKI
# ============================================
def init_bot():
    """Initialize TradingBot dengan error handling"""
    try:
        print("🔄 Inisialisasi TradingBot...")
        
        # Import TradingBot class
        TradingBotClass = import_trading_bot()
        
        if TradingBotClass is None:
            st.error("❌ TradingBot Import Gagal")
            return None
        
        print(f"✅ TradingBot class ditemukan: {TradingBotClass.__name__}")
        
        # Coba inisialisasi
        try:
            bot = TradingBotClass()
        except Exception as e:
            print(f"⚠️ Init gagal, coba dengan config kosong: {e}")
            bot = TradingBotClass({})
        
        # Pastikan atribut penting ada
        if not hasattr(bot, 'mode'):
            bot.mode = "crypto"
        if not hasattr(bot, 'trading_mode'):
            bot.trading_mode = "spot"
        if not hasattr(bot, 'config'):
            bot.config = {}
        
        # Tambahkan method update_position_current_price jika tidak ada
        if not hasattr(bot, 'update_position_current_price'):
            bot.update_position_current_price = lambda position_id, current_price: False
        
        print("✅ TradingBot initialization completed")
        return bot
        
    except Exception as e:
        st.error(f"❌ Error inisialisasi bot: {str(e)[:100]}")
        traceback.print_exc()
        return None

# ====================================
# Setup
# ====================================
load_dotenv()
st.set_page_config(page_title="TradingBot Pro", layout="wide")

# 🔥 AUTO-REFRESH SCRIPT untuk keep alive
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
                port = 8501  # Default Streamlit port
                
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
# SCALPING CONFIGURATION FOR APP - DIPERTAHANKAN
# ====================================

SCALPING_CONFIG_APP = {
    "timeframe": "5m",
    "lookback": 150,
    "min_score": 2.5,
    "long_bias": 0.0,
    "max_signals": 20,
    "min_volume_usd": 100000,
    "price_filter": {
        "min": 0.01,
        "max": 200
    },
    "entry_range_pct": 0.008,
    "atr_multiplier": 0.7,
    "skip_dummy_data": True,
    "require_real_data": True,
    "max_volatility": 0.15,
    "min_volatility": 0.005,
    "allow_short": True,
    "require_clear_signal": True
}

# Regular configuration (non-scalping)
REGULAR_CONFIG_APP = {
    "timeframe": "15m",
    "lookback": 100,
    "min_score": 2.0,
    "long_bias": 0.0,
    "max_signals": 15,
    "min_volume_usd": 50000,
    "price_filter": {
        "min": 0.001,
        "max": 500
    },
    "entry_range_pct": 0.02,
    "atr_multiplier": 1.0,
    "skip_dummy_data": True,
    "require_real_data": True,
    "max_volatility": 0.20,
    "min_volatility": 0.01,
    "allow_short": True,
    "require_clear_signal": True
}

# ====================================
# Helper Functions - DISEDERHANAKAN
# ====================================
def check_login(username, password):
    """Simple login system"""
    users = {"muraga": "namikaze", "admin": "admin123"}
    return users.get(username) == password

def format_symbol_for_mode(symbol, market_type, trading_mode):
    """Format symbol sesuai dengan market type dan trading mode"""
    if not symbol or symbol is None or symbol == 'None':
        return ""
    
    symbol = str(symbol).upper()
    
    futures_markers = [':USDT', 'PERP', '/USDT:', 'FUTURES', 'USDT:', '-USDT', '-PERP', '-SWAP']
    is_already_futures = any(marker in symbol for marker in futures_markers)
    
    if market_type == "crypto":
        if trading_mode == "futures" and not is_already_futures:
            if '/USDT' in symbol:
                return f"{symbol}:USDT"
            elif 'USDT' in symbol and '/' not in symbol:
                base = symbol.replace('USDT', '')
                return f"{base}/USDT:USDT"
            else:
                return f"{symbol}/USDT:USDT"
        elif trading_mode == "spot" and is_already_futures:
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
        if decimal_places > 0:
            return f"{currency_symbol} {amount:,.{decimal_places}f}"
        else:
            return f"{currency_symbol} {amount:,.0f}"
    else:
        if market_type == "Crypto":
            return f"{currency_symbol}{amount:,.8f}"
        else:
            return f"{currency_symbol}{amount:,.2f}"

def get_valid_price(data, symbol=None, bot=None):
    """Get valid price from analysis data - simplified"""
    if not isinstance(data, dict):
        data = {}
    
    price_sources = ['current_price', 'entry_price', 'ideal_entry', 'close', 'last', 'price']
    
    for source in price_sources:
        price = data.get(source)
        if price and isinstance(price, (int, float)) and price > 0:
            return float(price)
    
    return 1.0

def get_real_time_price(symbol, bot):
    """Dapatkan harga real-time untuk simbol tertentu"""
    try:
        time.sleep(0.3)
        
        if hasattr(bot, 'data_provider') and bot.data_provider:
            clean_symbol = symbol
            if '(Futures)' in clean_symbol:
                clean_symbol = clean_symbol.replace(' (Futures)', '')
            if '(Swap)' in clean_symbol:
                clean_symbol = clean_symbol.replace(' (Swap)', '')
            
            ticker = bot.data_provider.get_ticker(clean_symbol)
            
            if ticker:
                for key in ['last', 'close', 'current', 'price', 'markPrice', 'indexPrice']:
                    if key in ticker and ticker[key]:
                        price = float(ticker[key])
                        if price > 0:
                            return price
    except Exception as e:
        print(f"❌ Error getting real-time price: {e}")
    
    return None

def validate_price_reasonable(current_price, entry_price, symbol):
    """VALIDASI HARGA sederhana"""
    try:
        if current_price <= 0 or entry_price <= 0:
            return False
        
        ratio = current_price / entry_price
        
        if ratio < 0.01 or ratio > 100:
            return False
        
        if 'crypto' in symbol.lower() and current_price > 100000:
            return False
        
        return True
    except:
        return False

# 🔥 PERBAIKAN 4: FUNGSI GET REALTIME PRICE - DISEDERHANAKAN
def get_realtime_price_with_fallback(symbol, bot, entry_price=None):
    """🔥 SIMPLIFIED: Get real-time price dengan fallback"""
    try:
        # Clean symbol
        clean_symbol = symbol.replace(' (Futures)', '').replace(' (Swap)', '')
        
        # Priority 1: Coba dari provider
        if hasattr(bot, 'data_provider') and bot.data_provider:
            try:
                ticker = bot.data_provider.get_ticker(clean_symbol)
                if ticker and isinstance(ticker, dict):
                    for key in ['last', 'close', 'current', 'price']:
                        if key in ticker and ticker[key]:
                            price = float(ticker[key])
                            if price > 0 and validate_price_reasonable(price, entry_price if entry_price else price, symbol):
                                return price, "Live"
            except Exception as e:
                print(f"⚠️ Error get live price: {e}")
        
        # Priority 2: Gunakan entry price
        if entry_price and entry_price > 0:
            return entry_price, "Entry"
        
        # Priority 3: Default
        return 1.0, "Default"
        
    except Exception as e:
        print(f"❌ Error in get_realtime_price_with_fallback: {e}")
        return 1.0, "Error"

def validate_and_fix_price_levels(analysis, symbol=None, bot=None, is_scalping=False):
    """Validate and fix price levels in analysis data"""
    if not isinstance(analysis, dict):
        return {'symbol': symbol, 'error': 'Invalid analysis data'}
    
    if 'symbol' not in analysis and symbol:
        analysis['symbol'] = symbol
    
    current_price = get_valid_price(analysis, symbol, bot)
    
    if current_price <= 0:
        current_price = 1.0
    
    price_fields = ['entry_price', 'ideal_entry', 'current_price', 'close', 'last']
    for field in price_fields:
        if analysis.get(field, 0) <= 0:
            analysis[field] = current_price
    
    action = analysis.get('action', 'NEUTRAL')
    
    config = SCALPING_CONFIG_APP if is_scalping else REGULAR_CONFIG_APP
    
    if (analysis.get('entry_range_low', 0) <= 0 or 
        analysis.get('entry_range_high', 0) <= 0 or 
        analysis.get('best_entry', 0) <= 0 or
        analysis.get('entry_range_low') == analysis.get('entry_range_high')):
        
        atr = analysis.get('atr', 0)
        volatility = analysis.get('volatility', 0.02)
        
        if atr > 0:
            range_size = atr * config["atr_multiplier"]
        else:
            range_size = current_price * volatility * 0.5
        
        min_range = current_price * (config["entry_range_pct"] * 0.5)
        range_size = max(range_size, min_range)
        
        max_range = current_price * (config["entry_range_pct"] * 2)
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
    
    tp1 = analysis.get('tp1', 0)
    tp2 = analysis.get('tp2', 0) 
    tp3 = analysis.get('tp3', 0)
    sl = analysis.get('sl', 0)
    
    if (tp1 <= 0 or tp2 <= 0 or tp3 <= 0 or sl <= 0 or 
        tp1 == tp2 == tp3 == sl == current_price):
        
        if action == "LONG":
            analysis['tp1'] = round(current_price * 1.02, 8)
            analysis['tp2'] = round(current_price * 1.04, 8)
            analysis['tp3'] = round(current_price * 1.06, 8)
            analysis['sl'] = round(current_price * 0.98, 8)
        else:
            analysis['tp1'] = round(current_price * 0.98, 8)
            analysis['tp2'] = round(current_price * 0.96, 8)
            analysis['tp3'] = round(current_price * 0.94, 8)
            analysis['sl'] = round(current_price * 1.02, 8)
    
    action = analysis.get('action', 'NEUTRAL')
    if action in ["LONG", "SHORT"]:
        tp1 = analysis.get('tp1', 0)
        tp2 = analysis.get('tp2', 0)
        tp3 = analysis.get('tp3', 0)
        
        if action == "LONG":
            tp_levels = sorted([tp1, tp2, tp3])
            min_diff = max(current_price * 0.001, 0.000001)
            for i in range(1, 3):
                if tp_levels[i] - tp_levels[i-1] < min_diff:
                    tp_levels[i] = tp_levels[i-1] + min_diff
            analysis['tp1'], analysis['tp2'], analysis['tp3'] = tp_levels
        else:
            tp_levels = sorted([tp1, tp2, tp3], reverse=True)
            min_diff = max(current_price * 0.001, 0.000001)
            for i in range(1, 3):
                if tp_levels[i-1] - tp_levels[i] < min_diff:
                    tp_levels[i] = tp_levels[i-1] - min_diff
            analysis['tp1'], analysis['tp2'], analysis['tp3'] = tp_levels
    
    return analysis

def calculate_tp_probability(current_price, tp1, tp2, tp3, sl, action, volatility=0.02):
    """Hitung probabilitas hit TP - simplified"""
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
    
    fig.add_trace(go.Scatter(
        x=[entry_low, entry_high],
        y=['Entry Range', 'Entry Range'],
        fill='toself',
        fillcolor='rgba(0,255,0,0.2)',
        line=dict(color='rgba(255,255,255,0)'),
        name='Entry Range'
    ))
    
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
# SCALPING SPECIFIC FUNCTIONS
# ====================================

def filter_for_scalping(assets, bot):
    """Filter assets yang cocok untuk scalping"""
    filtered = []
    
    for asset in assets:
        try:
            symbol = asset.get('symbol', '')
            if not symbol:
                continue
            
            current_score = asset.get('score', 0)
            current_price = get_valid_price(asset, symbol, bot)
            action = asset.get('action', 'NEUTRAL')
            
            if action == "NEUTRAL":
                continue
            
            if abs(current_score) < SCALPING_CONFIG_APP["min_score"]:
                continue
            
            if current_price < 0.05 or current_price > 200:
                continue
            
            suitability_score = 0
            
            if abs(current_score) >= 3.5:
                suitability_score += 4
            elif abs(current_score) >= 3.0:
                suitability_score += 3
            elif abs(current_score) >= 2.5:
                suitability_score += 2
            
            if current_score <= -3.0:
                suitability_score += 2
            
            if 0.5 <= current_price <= 50:
                suitability_score += 2
            
            volume = asset.get('volume', 0)
            if volume > 1000000:
                suitability_score += 1
            
            asset['scalping_score'] = suitability_score
            asset['scalping_suitable'] = suitability_score >= 3
            
            if suitability_score >= 3:
                filtered.append(asset)
                
        except Exception as e:
            continue
    
    return sorted(filtered, key=lambda x: abs(x.get('score', 0)), reverse=True)

def display_scalping_signal(signal, index):
    """Display scalping signal"""
    symbol = signal.get('symbol', 'UNKNOWN')
    action = signal.get('action', 'NEUTRAL')
    score = signal.get('score', 0)
    scalping_score = signal.get('scalping_score', 0)
    
    if score >= 3.0:
        color = "🟢"
        emoji = "🚀"
    elif score >= 2.0:
        color = "🟡"
        emoji = "📈"
    elif score <= -3.0:
        color = "🔴"
        emoji = "💣"
    elif score <= -2.0:
        color = "🟠"
        emoji = "📉"
    else:
        color = "⚪"
        emoji = "⚡"
    
    col1, col2, col3, col4 = st.columns([2, 1.5, 1.5, 1])
    
    with col1:
        st.write(f"{index}. {color} {emoji} **{symbol}**")
        st.write(f"   Action: `{action}` | Score: `{score:+.1f}`")
    
    with col2:
        current_price = get_valid_price(signal, symbol, st.session_state.bot_instance)
        market = st.session_state.current_market if hasattr(st.session_state, 'current_market') else "Crypto"
        st.write(f"💰 Price: `{format_currency(current_price, market)}`")
        
        entry_low = signal.get('entry_range_low', 0)
        entry_high = signal.get('entry_range_high', 0)
        if entry_low and entry_high:
            range_pct = ((entry_high - entry_low) / current_price) * 100
            st.write(f"🎯 Range: `{format_currency(entry_low, market)}` - `{format_currency(entry_high, market)}`")
            st.write(f"📏 Range Size: `{range_pct:.2f}%`")
    
    with col3:
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
        st.write(f"⚡ Scalping Score: `{scalping_score}/7`")
        st.write(f"🛑 SL: `{format_currency(sl, market)}`")
        
        if signal.get('scalping_suitable', False):
            st.success("✅ Good for Scalping")
        else:
            st.warning("⚠️ Limited suitability")
    
    button_key = f"select_scalping_{symbol}_{index}"
    if st.button(f"📌 Select {symbol}", key=button_key):
        if select_asset_callback(symbol, signal):
            st.success(f"✅ Selected {symbol}!")
            st.rerun()
    return False

# ====================================
# FUNGSI Open Position
# ====================================
def open_position(symbol, action, entry_price=None, tp1=None, tp2=None, tp3=None, sl=None, 
                  position_size=100, risk_percent=None):
    """Open a new position"""
    try:
        bot = st.session_state.bot_instance
        
        if bot is None:
            st.error("❌ Bot is not initialized")
            return False
        
        if entry_price is None or entry_price <= 0:
            real_time_price = get_real_time_price(symbol, bot)
            if real_time_price and real_time_price > 0:
                entry_price = real_time_price
            else:
                if symbol in st.session_state.selected_for_entry:
                    analysis = st.session_state.selected_for_entry[symbol]
                    entry_price = get_valid_price(analysis, symbol, bot)
        
        if entry_price is None or entry_price <= 0:
            entry_price = 1.0
        
        current_price = entry_price
        
        if tp1 is None or sl is None:
            if action == "LONG":
                tp1 = tp1 or round(current_price * 1.02, 8)
                tp2 = tp2 or round(current_price * 1.04, 8)
                tp3 = tp3 or round(current_price * 1.06, 8)
                sl = sl or round(current_price * 0.98, 8)
            else:
                tp1 = tp1 or round(current_price * 0.98, 8)
                tp2 = tp2 or round(current_price * 0.96, 8)
                tp3 = tp3 or round(current_price * 0.94, 8)
                sl = sl or round(current_price * 1.02, 8)
        else:
            tp2 = tp2 or round(tp1 * 1.02, 8) if action == "LONG" else round(tp1 * 0.98, 8)
            tp3 = tp3 or round(tp1 * 1.04, 8) if action == "LONG" else round(tp1 * 0.96, 8)
        
        session_id = f"pos_{int(time.time())}_{symbol.replace('/', '_')}"
        
        db_position_id = None
        
        if hasattr(bot, 'save_position_to_db'):
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
        
        if not hasattr(st.session_state, 'test_positions'):
            st.session_state.test_positions = []
        
        st.session_state.test_positions.append(position)
        
        if hasattr(bot, 'get_active_positions'):
            try:
                st.session_state.positions_data = bot.get_active_positions()
            except:
                st.session_state.positions_data = st.session_state.test_positions
        
        print(f"✅ Position opened: {symbol}, DB ID: {db_position_id}")
        return True
        
    except Exception as e:
        print(f"❌ Error opening position: {e}")
        traceback.print_exc()
        return False

def update_position_price_in_db(bot, position_id, current_price):
    """Update harga position di database"""
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

# 🔥 PERBAIKAN 5: FUNGSI UPDATE ALL POSITIONS - DISEDERHANAKAN
def update_all_positions_prices(bot):
    """🔥 SIMPLIFIED: Update semua harga posisi"""
    updated_count = 0
    
    try:
        # Get positions
        positions = bot.get_active_positions()
        
        for pos in positions:
            if isinstance(pos, dict) and pos.get('status') in ['open', 'active']:
                symbol = pos.get('symbol')
                position_id = pos.get('id')
                
                if symbol and position_id:
                    # Get price
                    current_price, source = get_realtime_price_with_fallback(symbol, bot)
                    
                    if current_price and current_price > 0:
                        # Simple update
                        if hasattr(bot, 'update_position_current_price'):
                            bot.update_position_current_price(position_id, current_price)
                            updated_count += 1
        
        return updated_count
        
    except Exception as e:
        print(f"❌ Error updating prices: {e}")
        return 0

# ====================================
# Main App - SIMPLIFIED VERSION
# ====================================
def main_app():
    st.title("🚀 TradingBot Pro - Enhanced Dashboard with Scalping Support")
    
    # 🔥 START KEEP-ALIVE THREAD
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

    # Initialize bot
    if 'bot_instance' not in st.session_state or st.session_state.bot_instance is None:
        with st.spinner("Initializing TradingBot..."):
            try:
                bot = init_bot()
                if bot:
                    st.session_state.bot_instance = bot
                    
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
    
    if bot is None:
        st.error("❌ Bot is not available. Please refresh the page.")
        st.stop()
    
    # Initialize session state
    default_states = {
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
        'regular_config': REGULAR_CONFIG_APP,
        'selected_symbol_display': None,
        'last_selected': None,
        'test_positions': [],
        'open_position_result': None,
        'open_position_risk': None,
        'last_scan_time': None,
        'scan_attempts': 0,
        'show_all_positions': False,
        'use_risk_management': False,
        'current_config': REGULAR_CONFIG_APP,
        'positions_initialized': False,
        'refresh_counter': 0
    }
    
    for key, default_value in default_states.items():
        if key not in st.session_state:
            st.session_state[key] = default_value

    # Update current config berdasarkan mode
    if st.session_state.scalping_mode:
        st.session_state.current_config = SCALPING_CONFIG_APP
    else:
        st.session_state.current_config = REGULAR_CONFIG_APP

    # Sidebar
    with st.sidebar:
        st.header("🎯 Trading Configuration")
        
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
        
        # Scalping Mode Toggle
        scalping_mode = st.checkbox("⚡ Enable Scalping Mode", 
                                    value=st.session_state.scalping_mode,
                                    help="Enable for 3-5 minute scalping with tighter parameters")
        
        if scalping_mode != st.session_state.scalping_mode:
            st.session_state.scalping_mode = scalping_mode
            st.session_state.scanned_results = []
            st.session_state.scalping_results = []
            if scalping_mode:
                st.session_state.current_config = SCALPING_CONFIG_APP
            else:
                st.session_state.current_config = REGULAR_CONFIG_APP
            st.rerun()
        
        if scalping_mode:
            st.success("⚡ SCALPING MODE ACTIVE")
            
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
                    st.session_state.current_config = SCALPING_CONFIG_APP
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
        else:
            st.info(f"""
            **Regular Parameters:**
            - Timeframe: 15m
            - Min Score: {REGULAR_CONFIG_APP["min_score"]}
            - Bias: 0.0 (Neutral)
            - Entry Range: 2.0%
            - Max Price: ${REGULAR_CONFIG_APP["price_filter"]["max"]}
            - Allow Short: ✅ Yes
            - Max Signals: {REGULAR_CONFIG_APP["max_signals"]}
            """)
        
        st.divider()
        
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
            trading_mode = "Spot"
            st.info("📊 Only Spot trading available for this market")
        
        if market_choice in ["Forex", "Saham Indonesia", "US Stocks"]:
            st.warning("⚠️ **SHORT TRADING NOT AVAILABLE** - Only LONG signals will be generated")

        # Set Market Button
        if st.button("🎯 Set Market", key="set_market_btn", type="primary"):
            if bot is None:
                st.error("❌ Bot is not initialized. Please refresh the page.")
                st.rerun()
            
            try:
                if market_choice != "Crypto" and trading_mode == "Futures":
                    st.error("❌ Futures mode hanya tersedia untuk Crypto")
                else:
                    market_mode_map = {
                        "Crypto": "crypto",
                        "Forex": "forex", 
                        "Saham Indonesia": "saham_id",
                        "US Stocks": "us_stocks"
                    }
                    
                    mode_string = market_mode_map[market_choice]
                    
                    if trading_mode == "Futures":
                        target_trading_mode = "futures"
                    else:
                        target_trading_mode = "spot"
                    
                    if hasattr(bot, 'set_mode'):
                        success = bot.set_mode(mode_string)
                    else:
                        bot.mode = mode_string
                        success = True
                    
                    if success:
                        bot.trading_mode = target_trading_mode
                        
                        st.session_state.current_market = market_choice
                        st.session_state.current_trading_mode = trading_mode
                        st.session_state.market_set = True
                        st.session_state.scanned_results = []
                        st.session_state.scalping_results = []
                        st.session_state.selected_for_entry = {}
                        st.session_state.selected_symbol_display = None
                        
                        if market_choice in ["Saham Indonesia", "US Stocks", "Forex"]:
                            st.info(f"📊 Loading 500+ {market_choice} assets...")
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
                                except Exception as e:
                                    st.warning(f"⚠️ Asset loading: {e}")
                        
                        st.success(f"✅ Market set to: {market_choice} ({trading_mode})")
                        st.rerun()
                    else:
                        st.error("❌ Failed to set market mode")
                        
            except Exception as e:
                st.error(f"❌ Error: {str(e)[:200]}")
        
        # Tampilkan status market
        if st.session_state.market_set:
            st.divider()
            st.success(f"✅ Active: {st.session_state.current_market}")
            if hasattr(bot, 'trading_mode'):
                mode_display = bot.trading_mode.upper()
                st.info(f"📊 Mode: {mode_display}")
            
            if st.session_state.scalping_mode:
                st.success("⚡ SCALPING MODE: ON")
            else:
                st.info("📊 REGULAR MODE: ON")
            
            if st.session_state.current_market in ["Saham Indonesia", "US Stocks", "Forex"]:
                st.info(f"📈 **500+ Assets Available**")
        
        # Info tentang simbol
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

    # Check if market is set
    if not st.session_state.market_set:
        st.warning("⚠️ Please select a market first!")
        st.info("""
        **Instructions:**
        1. Select Market (Crypto/Forex/Saham Indonesia/US Stocks)  
        2. Select Trading Mode (Spot/Futures)
        3. Click **Set Market** button
        4. Start scanning assets
        """)
        return

    # Main Tabs - Hanya tampilkan tab utama untuk kesederhanaan
    tab1, tab2, tab3, tab4, tab6, tab8 = st.tabs([
        "📊 Scan Assets", "⚡ Scalping Mode", "🔍 Analyze", "🎯 Custom Entry", 
        "💼 Positions", "📡 Live Scanner"
    ])

    # Tab 1: Scan Assets
    with tab1:
        st.subheader("📊 Scan Potential Assets")
        
        mode_info = []
        if hasattr(bot, 'trading_mode'):
            mode_badge = "🔄 SPOT" if bot.trading_mode == "spot" else "⚡ FUTURES"
            mode_info.append(f"**Mode:** {mode_badge}")
        
        if st.session_state.scalping_mode:
            mode_info.append("⚡ **SCALPING:** ON")
            config = st.session_state.current_config
            st.info(f"""
            ⚡ **SCALPING CONFIGURATION:**
            - Min Score: `{config['min_score']}`
            - Price Range: `${config['price_filter']['min']}` - `${config['price_filter']['max']}`
            - Bias: `{config['long_bias']}` (Neutral)
            - Entry Range: `{config['entry_range_pct']*100:.1f}%`
            - Allow Short: ✅ Yes
            - Max Signals: `{config['max_signals']}`
            """)
        else:
            mode_info.append("📊 **REGULAR:** ON")
            config = st.session_state.current_config
            st.info(f"""
            📊 **REGULAR CONFIGURATION:**
            - Min Score: `{config['min_score']}`
            - Price Range: `${config['price_filter']['min']}` - `${config['price_filter']['max']}`
            - Bias: `{config['long_bias']}` (Neutral)
            - Entry Range: `{config['entry_range_pct']*100:.1f}%`
            - Allow Short: ✅ Yes
            - Max Signals: `{config['max_signals']}`
            """)
        
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
                    st.write(f"💰 Price: `{format_currency(data.get('current_price', 0), market)}`")
                with col_sel2:
                    if st.button(f"❌ Remove", key=f"remove_{symbol}"):
                        del st.session_state.selected_for_entry[symbol]
                        st.rerun()
            st.divider()
        
        # Scan button
        col_scan1, col_scan2 = st.columns([1, 2])
        with col_scan1:
            if st.session_state.scalping_mode:
                scan_button_label = "🚀 Start Scalping Scan"
                scan_type = "scalping"
            else:
                scan_button_label = "🚀 Start Regular Scan"
                scan_type = "regular"
        
        with col_scan2:
            if st.session_state.current_market in ["Saham Indonesia", "US Stocks"]:
                scan_limit = st.select_slider(
                    "Scan Limit:",
                    options=[10, 25, 50, 100, 200],
                    value=50,
                    key="scan_limit_slider"
                )
            else:
                scan_limit = st.select_slider(
                    "Scan Limit:",
                    options=[10, 25, 50, 100],
                    value=25,
                    key="scan_limit_slider"
                )
        
        if st.button(scan_button_label, key="start_scan", type="primary"):
            with st.spinner(f"Scanning {scan_limit} assets ({scan_type})..."):
                try:
                    if bot is None:
                        st.error("❌ Bot is not initialized")
                        return
                    
                    results = bot.scan_potential_assets(scan_limit)
                    
                    if results:
                        formatted_results = []
                        scalping_results = []
                        
                        for result in results:
                            if isinstance(result, dict) and 'symbol' in result:
                                original_symbol = safe_get(result, 'symbol')
                                
                                formatted_symbol = format_symbol_for_mode(
                                    original_symbol, 
                                    bot.mode, 
                                    getattr(bot, 'trading_mode', 'spot')
                                )
                                
                                result['symbol'] = formatted_symbol
                                result['original_symbol'] = original_symbol
                                
                                validated_result = validate_and_fix_price_levels(
                                    result, formatted_symbol, bot, st.session_state.scalping_mode
                                )
                                
                                if st.session_state.scalping_mode:
                                    current_score = validated_result.get('score', 0)
                                    current_price = get_valid_price(validated_result, formatted_symbol, bot)
                                    action = validated_result.get('action', 'NEUTRAL')
                                    
                                    is_scalping_suitable = (
                                        abs(current_score) >= SCALPING_CONFIG_APP["min_score"] and
                                        current_price >= SCALPING_CONFIG_APP["price_filter"]["min"] and
                                        current_price <= SCALPING_CONFIG_APP["price_filter"]["max"] and
                                        action != 'NEUTRAL'
                                    )
                                    
                                    if is_scalping_suitable:
                                        validated_result['scalping_suitable'] = True
                                        scalping_results.append(validated_result)
                                
                                formatted_results.append(validated_result)
                        
                        if st.session_state.scalping_mode and scalping_results:
                            scalping_results = filter_for_scalping(scalping_results, bot)
                        
                        st.session_state.scanned_results = formatted_results
                        st.session_state.scalping_results = scalping_results
                        
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
                        
                        if st.session_state.scalping_mode:
                            if scalping_results:
                                st.success(f"✅ Found {len(scalping_results)} assets suitable for scalping")
                            else:
                                st.warning(f"⚠️ No assets meet scalping criteria")
                        else:
                            st.success(f"✅ Found {len(formatted_results)} potential assets")
                        
                    else:
                        st.warning("⚠️ No signals found")
                        
                except Exception as e:
                    st.error(f"Scan error: {str(e)[:200]}")
        
        if st.session_state.scalping_mode and st.session_state.scalping_results:
            st.subheader("⚡ Scalping Signals")
            
            for i, res in enumerate(st.session_state.scalping_results[:SCALPING_CONFIG_APP["max_signals"]], 1):
                if isinstance(res, dict) and 'symbol' in res:
                    selected = display_scalping_signal(res, i)
                    if selected:
                        st.rerun()
                    
                    st.divider()
        
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
                        market = st.session_state.current_market if hasattr(st.session_state, 'current_market') else "Crypto"
                        st.write(f"💰 Current Price: `{format_currency(current_price, market)}`")
                        
                        st.write(f"📊 **Entry Range:** `{format_currency(res.get('entry_range_low', 0), market)} - {format_currency(res.get('entry_range_high', 0), market)}`")
                        st.write(f"🎯 **Ideal Entry:** `{format_currency(res.get('best_entry', 0), market)}`")
                        if 'range_size' in res:
                            st.write(f"📏 **Range Size:** `{res.get('range_size', 0):.1f}%`")
                        
                        tp1, tp2, tp3 = safe_get(res, 'tp1', 0), safe_get(res, 'tp2', 0), safe_get(res, 'tp3', 0)
                        sl = safe_get(res, 'sl', 0)
                        
                        st.write(f"🎯 **TP Levels:** `{format_currency(tp1, market)}` | `{format_currency(tp2, market)}` | `{format_currency(tp3, market)}`")
                        st.write(f"🛑 **Stop Loss:** `{format_currency(sl, market)}`")
                        
                        if 'tp_probabilities' not in res:
                            res['tp_probabilities'] = calculate_tp_probability(
                                current_price, tp1, tp2, tp3, sl, action
                            )
                        
                        probs = res['tp_probabilities']
                        st.write(f"📊 **Probabilities:** TP1: {probs.get('tp1', 0)*100:.1f}% | TP2: {probs.get('tp2', 0)*100:.1f}% | TP3: {probs.get('tp3', 0)*100:.1f}%")
                    
                    with col2:
                        button_key = f"select_regular_{symbol}_{i}"
                        if st.button(f"📌 Select", key=button_key):
                            if select_asset_callback(symbol, res):
                                st.success(f"✅ Selected {display_symbol}!")
                                st.rerun()
                    
                    st.divider()

    # Tab 2: Scalping Mode
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
                st.session_state.current_config = SCALPING_CONFIG_APP
                st.rerun()
        else:
            st.success("⚡ SCALPING MODE ACTIVE")
            
            with st.expander("⚙️ Dynamic Scalping Configuration"):
                col_sc1, col_sc2 = st.columns(2)
                
                with col_sc1:
                    min_score = st.slider("Min Score Threshold", 2.0, 5.0, 
                                         value=SCALPING_CONFIG_APP["min_score"], step=0.5,
                                         key="tab2_min_score")
                
                with col_sc2:
                    st.info("Bias: 0.0 (Neutral)")
                    entry_range = st.slider("Entry Range %", 0.005, 0.02,
                                          value=SCALPING_CONFIG_APP["entry_range_pct"], step=0.001,
                                          key="tab2_entry_range")
                    st.caption(f"Current: {entry_range*100:.1f}%")
                
                if st.button("🔄 Update Scalping Config", key="update_scalping_config"):
                    SCALPING_CONFIG_APP["min_score"] = min_score
                    SCALPING_CONFIG_APP["entry_range_pct"] = entry_range
                    st.session_state.scalping_config = SCALPING_CONFIG_APP
                    st.session_state.current_config = SCALPING_CONFIG_APP
                    st.success("✅ Scalping configuration updated!")
                    st.rerun()
            
            col_qs1, col_qs2 = st.columns(2)
            
            with col_qs1:
                if st.button("🎯 Quick Scan (Top 20)", key="quick_scalping_scan", type="primary"):
                    with st.spinner("Quick scanning for scalping..."):
                        try:
                            results = bot.scan_potential_assets(SCALPING_CONFIG_APP["max_signals"])
                            if results:
                                scalping_signals = []
                                for res in results:
                                    if isinstance(res, dict) and 'symbol' in res:
                                        symbol = res['symbol']
                                        score = res.get('score', 0)
                                        if abs(score) >= min_score:
                                            scalping_signals.append(res)
                                
                                scalping_signals = filter_for_scalping(scalping_signals, bot)
                                st.session_state.scalping_results = scalping_signals
                                st.success(f"✅ Found {len(scalping_signals)} scalping signals")
                            else:
                                st.warning("⚠️ No scalping signals found")
                        except Exception as e:
                            st.error(f"Quick scan error: {e}")
            
            with col_qs2:
                if st.button("🔄 Clear & Refresh", key="refresh_scalping_data"):
                    st.session_state.scalping_results = []
                    st.rerun()
            
            # Display Scalping Results
            if st.session_state.scalping_results:
                st.subheader(f"⚡ Active Scalping Signals ({len(st.session_state.scalping_results)} found)")
                
                sorted_signals = sorted(st.session_state.scalping_results, 
                                      key=lambda x: abs(x.get('score', 0)), reverse=True)
                
                for i, signal in enumerate(sorted_signals[:SCALPING_CONFIG_APP["max_signals"]], 1):
                    with st.container():
                        col_s1, col_s2, col_s3 = st.columns([2, 2, 1])
                        
                        with col_s1:
                            symbol = signal.get('symbol', 'UNKNOWN')
                            action = signal.get('action', 'NEUTRAL')
                            score = signal.get('score', 0)
                            
                            if score >= 3.0:
                                emoji = "🚀"
                            elif score >= 2.0:
                                emoji = "📈"
                            elif score <= -3.0:
                                emoji = "💣"
                            elif score <= -2.0:
                                emoji = "📉"
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

    # Tab 3: Analyze Asset
    with tab3:
        st.subheader("🔍 Analyze Specific Asset")
        
        mode_status = []
        if hasattr(bot, 'trading_mode'):
            mode_display = "🔄 Spot" if bot.trading_mode == "spot" else "⚡ Futures"
            mode_status.append(f"**Mode:** {mode_display}")
        
        if st.session_state.scalping_mode:
            mode_status.append("⚡ **SCALPING:** ON")
        else:
            mode_status.append("📊 **REGULAR:** ON")
        
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
    
        analysis_config = {}
        if st.session_state.scalping_mode:
            with st.expander("⚡ Scalping Analysis Settings"):
                st.info("Analysis Bias: 0.0 (disabled)")
                analysis_config['long_bias'] = 0.0
        
        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            if st.button("🚀 Analyze", key="analyze_btn", type="primary"):
                if symbol_input:
                    with st.spinner("Analyzing..."):
                        try:
                            symbol = symbol_input.upper().strip()
                            
                            formatted_symbol = format_symbol_for_mode(
                                symbol, 
                                bot.mode,
                                getattr(bot, 'trading_mode', 'spot')
                            )
                            
                            st.info(f"🔍 Analyzing: {formatted_symbol}")
                            
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
                                if analysis_config:
                                    analysis['scalping_mode'] = True
                                
                                if current_price > 0:
                                    analysis['current_price'] = current_price
                                    analysis['last'] = current_price
                                
                                analysis = validate_and_fix_price_levels(
                                    analysis, formatted_symbol, bot, st.session_state.scalping_mode
                                )
                                
                                analysis['formatted_symbol'] = formatted_symbol
                                analysis['original_input'] = symbol_input
                                
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
        
        with col_btn2:
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
            
            if analysis.get('scalping_mode'):
                st.success("⚡ Scalping Analysis Applied")
            
            col_save1, col_save2 = st.columns([2, 1])
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
                if st.button("🔄 Refresh Price", key="refresh_price_btn"):
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
                
            with col2:
                st.metric("RSI", f"{safe_get(analysis, 'rsi', 0):.1f}")
                st.metric("ATR", f"{safe_get(analysis, 'atr', 0):.8f}")
                
                if 'tp_probabilities' in analysis:
                    probs = analysis['tp_probabilities']
                    st.metric("TP1 Probability", f"{probs.get('tp1', 0)*100:.1f}%")
            
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

    # Tab 4: Custom Entry & Open Position
    with tab4:
        st.subheader("🎯 Custom Entry & Open Position")
        
        mode_info = []
        if hasattr(bot, 'trading_mode'):
            mode_display = "🔄 Spot" if bot.trading_mode == "spot" else "⚡ Futures"
            mode_info.append(f"**Trading Mode:** {mode_display}")
        
        if st.session_state.scalping_mode:
            mode_info.append("⚡ **SCALPING:** ON")
        else:
            mode_info.append("📊 **REGULAR:** ON")
        
        if mode_info:
            st.info(" | ".join(mode_info))
        
        st.subheader("📌 Step 1: Select or Enter Asset")
        
        use_existing = st.checkbox("Use existing analysis from Tab 3", value=True)
        
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
        
        st.subheader("💰 Step 2: Entry Details (Manual Input)")
        
        col_symbol, col_action = st.columns([2, 1])
        with col_symbol:
            default_symbol = st.session_state.get('custom_symbol', '')
            symbol_custom = st.text_input("Symbol:", 
                                         value=default_symbol,
                                         key="custom_symbol_input_tab4", 
                                         placeholder="BTC/USDT or BTC/USDT:USDT")
        
        with col_action:
            default_action = st.session_state.get('custom_action', 'LONG')
            action_custom = st.selectbox("Action:", ["LONG", "SHORT"], 
                                        index=0 if default_action == "LONG" else 1,
                                        key="custom_action_select_tab4")
        
        col_price1, col_price2 = st.columns([3, 1])
        with col_price1:
            currency_symbol = get_currency_symbol(st.session_state.current_market)
            default_price = st.session_state.get('custom_entry_price', 0.0)
            safe_default_price = max(float(default_price), 0.00001)
            
            entry_price_custom = st.number_input(
                f"Entry Price ({currency_symbol}):", 
                value=safe_default_price,
                min_value=0.00001,
                step=0.01, 
                format="%.8f",
                key="custom_entry_price_tab4"
            )
        
        with col_price2:
            st.write("")  
            st.write("")  
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
        
        col_size, col_risk = st.columns(2)
        with col_size:
            position_size = st.number_input(
                f"Position Size ({currency_symbol}):",
                value=100.0,
                min_value=0.0,
                step=10.0,
                key="position_size_input_tab4"
            )
        
        with col_risk:
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
            
            if action_custom == "LONG":
                tp1_auto = round(entry_price_custom * (1 + tp_percent/100), 8)
                tp2_auto = round(entry_price_custom * (1 + (tp_percent*2)/100), 8)
                tp3_auto = round(entry_price_custom * (1 + (tp_percent*3)/100), 8)
                sl_auto = round(entry_price_custom * (1 - sl_percent/100), 8)
            else:
                tp1_auto = round(entry_price_custom * (1 - tp_percent/100), 8)
                tp2_auto = round(entry_price_custom * (1 - (tp_percent*2)/100), 8)
                tp3_auto = round(entry_price_custom * (1 - (tp_percent*3)/100), 8)
                sl_auto = round(entry_price_custom * (1 + sl_percent/100), 8)
            
            tp1_custom, tp2_custom, tp3_custom, sl_custom = tp1_auto, tp2_auto, tp3_auto, sl_auto
            
            col_show1, col_show2 = st.columns(2)
            with col_show1:
                st.info(f"**TP1:** {format_currency(tp1_auto, st.session_state.current_market)}")
                st.info(f"**TP2:** {format_currency(tp2_auto, st.session_state.current_market)}")
                st.info(f"**TP3:** {format_currency(tp3_auto, st.session_state.current_market)}")
            with col_show2:
                st.warning(f"**Stop Loss:** {format_currency(sl_auto, st.session_state.current_market)}")
                
        else:
            st.info("Enter TP/SL values manually:")
            
            col_manual1, col_manual2 = st.columns(2)
            with col_manual1:
                default_tp1 = st.session_state.get('custom_tp1', 0)
                default_tp2 = st.session_state.get('custom_tp2', 0)
                default_tp3 = st.session_state.get('custom_tp3', 0)
                
                tp1_custom = st.number_input(
                    f"TP1 ({currency_symbol}):",
                    value=max(default_tp1, entry_price_custom * 1.02),
                    min_value=0.00001,
                    step=0.01,
                    format="%.8f",
                    key="manual_tp1"
                )
                
                tp2_custom = st.number_input(
                    f"TP2 ({currency_symbol}):",
                    value=max(default_tp2, entry_price_custom * 1.04),
                    min_value=0.00001,
                    step=0.01,
                    format="%.8f",
                    key="manual_tp2"
                )
                
                tp3_custom = st.number_input(
                    f"TP3 ({currency_symbol}):",
                    value=max(default_tp3, entry_price_custom * 1.06),
                    min_value=0.00001,
                    step=0.01,
                    format="%.8f",
                    key="manual_tp3"
                )
            
            with col_manual2:
                default_sl = st.session_state.get('custom_sl', 0)
                
                sl_custom = st.number_input(
                    f"Stop Loss ({currency_symbol}):",
                    value=max(default_sl, entry_price_custom * 0.98),
                    min_value=0.00001,
                    step=0.01,
                    format="%.8f",
                    key="manual_sl"
                )
        
        st.divider()
        st.subheader("📊 Risk/Reward Analysis")
        
        if entry_price_custom > 0:
            if action_custom == "LONG":
                risk = entry_price_custom - sl_custom
                reward_tp1 = tp1_custom - entry_price_custom
                reward_tp2 = tp2_custom - entry_price_custom
                reward_tp3 = tp3_custom - entry_price_custom
            else:
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
        
        st.subheader("🚀 Step 4: Open Position")
        
        if st.button("📈 OPEN POSITION", key="open_position_btn_tab4", type="primary", use_container_width=True):
            if symbol_custom and entry_price_custom > 0:
                with st.spinner("Opening position..."):
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
                        
                        keys_to_clear = ['custom_symbol', 'custom_action', 'custom_entry_price',
                                       'custom_tp1', 'custom_tp2', 'custom_tp3', 'custom_sl']
                        for key in keys_to_clear:
                            if key in st.session_state:
                                del st.session_state[key]
                        
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

    # Tab 6: Positions
    with tab6:
        st.subheader("💼 Active Positions")
        
        mode_info = []
        if hasattr(bot, 'trading_mode'):
            mode_display = "🔄 Spot" if bot.trading_mode == "spot" else "⚡ Futures"
            mode_info.append(f"**Trading Mode:** {mode_display}")
        
        if st.session_state.scalping_mode:
            mode_info.append("⚡ **SCALPING:** ON")
        else:
            mode_info.append("📊 **REGULAR:** ON")
        
        if mode_info:
            st.info(" | ".join(mode_info))
        
        col_rt1, col_rt2 = st.columns([1, 1])
        with col_rt1:
            if st.button("💰 Update ALL Prices", key="update_all_prices_tab6", type="primary"):
                with st.spinner("Updating prices from real-time data..."):
                    updated_count = update_all_positions_prices(bot)
                    
                    if updated_count > 0:
                        st.success(f"✅ Updated {updated_count} positions with real-time prices!")
                    else:
                        st.warning("⚠️ No positions were updated.")
                    
                    st.session_state.positions_data = bot.get_active_positions()
                    st.rerun()
        
        with col_rt2:
            if st.button("🔄 Refresh Positions", key="refresh_positions_tab6", type="primary"):
                try:
                    positions = bot.get_active_positions()
                    if positions:
                        st.session_state.positions_data = positions
                        st.success(f"✅ Loaded {len(positions)} positions")
                    else:
                        if hasattr(st.session_state, 'test_positions') and st.session_state.test_positions:
                            st.session_state.positions_data = st.session_state.test_positions
                            st.info(f"📋 Showing {len(st.session_state.test_positions)} positions from session")
                        else:
                            st.session_state.positions_data = []
                            st.info("📭 No positions found")
                    
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Refresh error: {e}")
        
        # Get all positions
        all_positions = []

        try:
            db_positions = bot.get_active_positions()
            if db_positions:
                for pos in db_positions:
                    if isinstance(pos, dict):
                        if pos.get('status') == 'active':
                            pos['status'] = 'open'
                        
                        if 'current_price' not in pos or not pos['current_price']:
                            pos['current_price'] = pos.get('entry_price', 0)
                        
                        all_positions.append(pos)
        except Exception as e:
            st.error(f"❌ Error getting DB positions: {e}")

        if hasattr(st.session_state, 'test_positions') and st.session_state.test_positions:
            for session_pos in st.session_state.test_positions:
                session_symbol = session_pos.get('symbol', '')
                already_exists = False
                
                for db_pos in all_positions:
                    if db_pos.get('symbol') == session_symbol:
                        already_exists = True
                        break
                
                if not already_exists and session_pos.get('status', 'open') == 'open':
                    all_positions.append(session_pos)

        open_positions = []
        for pos in all_positions:
            status = pos.get('status', 'open').lower()
            if status in ['open', 'active']:
                open_positions.append(pos)

        st.subheader(f"📊 Active Positions ({len(open_positions)})")
        
        if not open_positions:
            st.info("📭 No active positions")
            st.info("👉 Open a position in Tab 4 first!")
        else:
            for idx, pos in enumerate(open_positions):
                try:
                    position_id = pos.get('id', f'pos_{idx}')
                    symbol = pos.get('symbol', 'UNKNOWN')
                    action = pos.get('action', 'LONG')
                    entry_price = float(pos.get('entry_price', 0))
                    
                    realtime_price, source = get_realtime_price_with_fallback(symbol, bot, entry_price)
                    
                    if realtime_price and realtime_price > 0:
                        if not validate_price_reasonable(realtime_price, entry_price, symbol):
                            current_price = entry_price
                            price_source = "Entry (Invalid Live)"
                        else:
                            update_position_price_in_db(bot, position_id, realtime_price)
                            current_price = realtime_price
                            price_source = f"Live ({source})"
                    else:
                        current_price = float(pos.get('current_price', entry_price))
                        price_source = "Database"
                    
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
                    
                    display_symbol = convert_symbol_for_display(
                        symbol,
                        bot.mode,
                        getattr(bot, 'trading_mode', 'spot')
                    )
                    
                    pl_pct = 0.0
                    pl_value = 0.0
                    
                    if entry_price > 0 and current_price > 0:
                        if action == "LONG":
                            pl_pct = ((current_price - entry_price) / entry_price) * 100
                            pl_value = (current_price - entry_price) * (position_size / entry_price)
                        else:
                            pl_pct = ((entry_price - current_price) / entry_price) * 100
                            pl_value = (entry_price - current_price) * (position_size / entry_price)
                    
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
                    
                    with st.container():
                        col_pos1, col_pos2, col_pos3, col_pos4 = st.columns([2, 2, 2, 1])
                        
                        with col_pos1:
                            st.write(f"{emoji} **{display_symbol}**")
                            st.write(f"Action: `{action}`")
                            market = st.session_state.current_market if hasattr(st.session_state, 'current_market') else "Crypto"
                            st.write(f"🏁 Entry: {format_currency(entry_price, market)}")
                            st.write(f"📏 Size: {format_currency(position_size, market)}")
                        
                        with col_pos2:
                            price_emoji = "🟢" if "Live" in price_source else "🟡" if "Database" in price_source else "⚪"
                            st.write(f"{price_emoji} {price_source}: {format_currency(current_price, market)}")
                            
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
                            update_key = f"update_price_single_{position_id}_{symbol}_{idx}"
                            if st.button("🔄 Update", key=update_key):
                                current_price, source = get_realtime_price_with_fallback(symbol, bot, entry_price)
                                if current_price and current_price > 0:
                                    success = update_position_price_in_db(bot, position_id, current_price)
                                    if success:
                                        st.success(f"✅ {display_symbol} updated to {format_currency(current_price, market)} in DB!")
                                    else:
                                        st.warning(f"⚠️ {display_symbol} price update failed")
                                    st.rerun()
                                else:
                                    st.warning(f"⚠️ Cannot get real-time price for {display_symbol}")
                            
                            close_key = f"close_position_{position_id}_{symbol}_{idx}"
                            if st.button("❌ Close", key=close_key, type="secondary"):
                                with st.spinner("Closing position..."):
                                    try:
                                        success = False
                                        close_price = current_price if current_price > 0 else entry_price
                                        
                                        if hasattr(bot, 'close_position'):
                                            success = bot.close_position(position_id, close_price)
                                        
                                        if hasattr(st.session_state, 'test_positions'):
                                            st.session_state.test_positions = [
                                                p for p in st.session_state.test_positions 
                                                if p.get('id') != position_id and p.get('symbol') != symbol
                                            ]
                                        
                                        if success:
                                            st.success(f"✅ {display_symbol} closed at {format_currency(close_price, market)}!")
                                            time.sleep(1)
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
                    
                    with st.container():
                        st.warning(f"⚠️ Problem with position {idx+1}: {symbol if 'symbol' in pos else 'Unknown'}")
                        st.write(f"Error: {str(e)[:100]}")
                    continue

    # Tab 8: Live Scanner & Position Monitor
    with tab8:
        st.subheader("📡 Live Scanner & Position Monitor")
        
        mode_info = []
        if hasattr(bot, 'trading_mode'):
            mode_display = "🔄 Spot" if bot.trading_mode == "spot" else "⚡ Futures"
            mode_info.append(f"**Trading Mode:** {mode_display}")
        
        if st.session_state.scalping_mode:
            mode_info.append("⚡ **SCALPING:** ON")
        else:
            mode_info.append("📊 **REGULAR:** ON")
        
        if mode_info:
            st.info(" | ".join(mode_info))
        
        col1, col2 = st.columns([1, 2])
        with col1:
            if st.button("🚀 Start Live Monitoring" if not st.session_state.live_monitoring else "⏹️ Stop Monitoring", 
                        key="toggle_live_tab8", type="primary"):
                st.session_state.live_monitoring = not st.session_state.live_monitoring
                st.rerun()

        with col2:
            auto_refresh_live = st.checkbox("🔄 Auto Refresh (10s)", value=True, key="auto_refresh_live_tab8")
        
        if st.session_state.live_monitoring:
            st.success("📡 LIVE MONITORING ACTIVE")
            
            try:
                all_db_positions = bot.get_active_positions()
            except:
                all_db_positions = []
            
            all_positions = []
            if all_db_positions:
                all_positions.extend(all_db_positions)
            
            if hasattr(st.session_state, 'test_positions') and st.session_state.test_positions:
                for session_pos in st.session_state.test_positions:
                    session_symbol = session_pos.get('symbol', '')
                    exists = False
                    for db_pos in all_positions:
                        if db_pos.get('symbol') == session_symbol:
                            exists = True
                            break
                    if not exists:
                        all_positions.append(session_pos)
            
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
                        
                        live_price, source = get_realtime_price_with_fallback(symbol, bot, entry_price)
                        
                        if live_price and live_price > 0 and validate_price_reasonable(live_price, entry_price, symbol):
                            if hasattr(bot, 'update_position_current_price'):
                                bot.update_position_current_price(position_id, live_price)
                            current_price = live_price
                            price_source = f"Live ({source})"
                        else:
                            price_source = "Database"
                        
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
                        
                        col_l1, col_l2, col_l3 = st.columns([2, 2, 1])
                        
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
                        
                        st.divider()
                        
                    except Exception as e:
                        st.error(f"❌ Error in position {idx+1}: {e}")
                        continue
                
                if auto_refresh_live and st.session_state.live_monitoring:
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
                        print(f"📡 Live monitor: Updated {update_count} positions")
                    
                    time.sleep(10)
                    st.rerun()
                    
            else:
                st.info("📭 No active positions to monitor")
                st.info("👉 Open a position in Tab 4 first!")
        else:
            st.info("👉 Click 'Start Live Monitoring' to begin tracking positions")

# 🔥 PERBAIKAN 6: MAIN FUNCTION DENGAN SESSION STATE YANG BENAR
def main():
    # Initialize session state dengan benar
    default_states = {
        'logged_in': False,
        'username': "",
        'bot_instance': None,
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
        'regular_config': REGULAR_CONFIG_APP,
        'selected_symbol_display': None,
        'last_selected': None,
        'test_positions': [],
        'open_position_result': None,
        'open_position_risk': None,
        'last_scan_time': None,
        'scan_attempts': 0,
        'show_all_positions': False,
        'use_risk_management': False,
        'current_config': REGULAR_CONFIG_APP,
        'positions_initialized': False,
        'refresh_counter': 0,
        'background_thread_started': False
    }
    
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
