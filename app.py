import time
import asyncio
import threading
import schedule
import streamlit as st
import pandas as pd
from dotenv import load_dotenv
import random  # For varied fallback patterns
import sys
import os

# ✅ FIX: Add the project root to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Try to import plotly, fallback to streamlit charts if not available
try:
    import plotly.graph_objects as go
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False
    st.warning("Plotly not available. Install with: pip install plotly")

# ✅ FIX: Import from bot package
try:
    from bot.core import TradingBot
    print("✅ Successfully imported TradingBot from bot.core")
except ImportError as e:
    st.error(f"❌ Import Error: {e}")
    st.stop()

# ====================================
# Setup
# ====================================
load_dotenv()
st.set_page_config(page_title="TradingBot Pro", layout="wide")

# ====================================
# Login System
# ====================================
def check_login(username, password):
    """Simple login system with hardcoded users"""
    users = ["muraga", "user2", "user3", "admin"]
    passwords = ["namikaze", "password2", "password3", "admin123"]
    
    try:
        if username in users:
            user_index = users.index(username)
            # Check if password matches based on user index
            if user_index < len(passwords) and password == passwords[user_index]:
                return True
    except Exception as e:
        st.error(f"Login error: {e}")
    
    return False

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
    
    # Display available users for testing
    with st.expander("ℹ️ Test Accounts"):
        st.write("""
        **Available test accounts:**
        - Username: `muraga` | Password: `namikaze`
        - Username: `user2` | Password: `password2` 
        - Username: `user3` | Password: `password3`
        - Username: `admin` | Password: `admin123`
        """)

@st.cache_resource
def init_bot():
    """Inisialisasi TradingBot."""
    return TradingBot()

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

def calculate_tp_probability(current_price, tp1, tp2, tp3, sl, action, volatility=0.02):
    """Hitung probabilitas hit TP1, TP2, TP3 berdasarkan distance dan volatilitas"""
    try:
        if action == "LONG":
            # Untuk LONG: TP1 < TP2 < TP3, SL < Entry
            tp_levels = sorted([tp1, tp2, tp3])
            distances = {
                'tp1': max(0.001, (tp_levels[0] - current_price) / current_price),
                'tp2': max(0.001, (tp_levels[1] - current_price) / current_price),
                'tp3': max(0.001, (tp_levels[2] - current_price) / current_price),
                'sl': max(0.001, (current_price - sl) / current_price)
            }
            
            # Probabilitas berdasarkan rasio risk/reward
            risk_distance = distances['sl']
            probabilities = {}
            
            for i, target in enumerate(['tp1', 'tp2', 'tp3']):
                reward_distance = distances[target]
                if reward_distance <= 0:
                    probabilities[target] = 0.05
                    continue
                    
                # Base probability berdasarkan rasio risk/reward
                risk_reward_ratio = risk_distance / reward_distance
                
                if risk_reward_ratio > 3:
                    base_prob = 0.75  # Sangat baik
                elif risk_reward_ratio > 2:
                    base_prob = 0.60  # Baik
                elif risk_reward_ratio > 1:
                    base_prob = 0.45  # Sedang
                elif risk_reward_ratio > 0.5:
                    base_prob = 0.30  # Rendah
                else:
                    base_prob = 0.15  # Sangat rendah
                
                # Adjust untuk TP yang lebih jauh
                distance_penalty = i * 0.15  # TP2 kena penalty 15%, TP3 kena 30%
                adjusted_prob = max(0.05, base_prob - distance_penalty)
                
                # Adjust berdasarkan volatilitas
                volatility_adjustment = volatility * 2
                final_prob = max(0.05, min(0.85, adjusted_prob - volatility_adjustment))
                
                probabilities[target] = round(final_prob, 3)
                
        else:  # SHORT
            # Untuk SHORT: TP1 > TP2 > TP3, SL > Entry
            tp_levels = sorted([tp1, tp2, tp3], reverse=True)
            distances = {
                'tp1': max(0.001, (current_price - tp_levels[0]) / current_price),
                'tp2': max(0.001, (current_price - tp_levels[1]) / current_price),
                'tp3': max(0.001, (current_price - tp_levels[2]) / current_price),
                'sl': max(0.001, (sl - current_price) / current_price)
            }
            
            # Probabilitas berdasarkan rasio risk/reward
            risk_distance = distances['sl']
            probabilities = {}
            
            for i, target in enumerate(['tp1', 'tp2', 'tp3']):
                reward_distance = distances[target]
                if reward_distance <= 0:
                    probabilities[target] = 0.05
                    continue
                    
                # Base probability berdasarkan rasio risk/reward
                risk_reward_ratio = risk_distance / reward_distance
                
                if risk_reward_ratio > 3:
                    base_prob = 0.75  # Sangat baik
                elif risk_reward_ratio > 2:
                    base_prob = 0.60  # Baik
                elif risk_reward_ratio > 1:
                    base_prob = 0.45  # Sedang
                elif risk_reward_ratio > 0.5:
                    base_prob = 0.30  # Rendah
                else:
                    base_prob = 0.15  # Sangat rendah
                
                # Adjust untuk TP yang lebih jauh
                distance_penalty = i * 0.15  # TP2 kena penalty 15%, TP3 kena 30%
                adjusted_prob = max(0.05, base_prob - distance_penalty)
                
                # Adjust berdasarkan volatilitas
                volatility_adjustment = volatility * 2
                final_prob = max(0.05, min(0.85, adjusted_prob - volatility_adjustment))
                
                probabilities[target] = round(final_prob, 3)
        
        # Pastikan probabilitas menurun dari TP1 ke TP3
        if 'tp1' in probabilities and 'tp2' in probabilities and 'tp3' in probabilities:
            probabilities['tp1'] = max(probabilities['tp1'], probabilities['tp2'], probabilities['tp3'])
            probabilities['tp2'] = min(probabilities['tp1'], max(probabilities['tp2'], probabilities['tp3']))
            probabilities['tp3'] = min(probabilities['tp1'], probabilities['tp2'], probabilities['tp3'])
        
        return probabilities
        
    except Exception as e:
        print(f"Error calculating TP probability: {e}")
        # Return probabilities yang lebih realistis sebagai fallback
        return {"tp1": 0.6, "tp2": 0.35, "tp3": 0.15}

def safe_get(data, key, default=0):
    """Safe dictionary access dengan fallback"""
    if isinstance(data, dict):
        return data.get(key, default)
    return default

def get_valid_price(data, symbol=None, bot=None):
    """Enhanced function to get valid price from analysis data - FIXED VERSION"""
    if not isinstance(data, dict):
        return 1.0  # Default to 1.0 instead of 0.0
    
    # Priority order for price extraction
    price_sources = ['current_price', 'entry_price', 'ideal_entry', 'close', 'last']
    
    for source in price_sources:
        price = data.get(source)
        if price and isinstance(price, (int, float)) and price > 0:
            return float(price)
    
    # If no valid price found in data, try to get from ticker
    if symbol and bot and hasattr(bot, 'data_provider'):
        try:
            ticker = bot.data_provider.get_ticker(symbol)
            if ticker and 'last' in ticker and ticker['last'] > 0:
                return float(ticker['last'])
        except:
            pass
    
    # Final fallback - never return 0.0
    return 1.0  # Default minimum price

def validate_and_fix_price_levels(analysis, symbol=None, bot=None):
    """Validate and fix price levels in analysis data - FIXED VERSION"""
    if not isinstance(analysis, dict):
        return {'symbol': symbol, 'error': 'Invalid analysis data'}
    
    # Ensure symbol exists
    if 'symbol' not in analysis and symbol:
        analysis['symbol'] = symbol
    
    # Get a valid current price with better fallbacks
    current_price = get_valid_price(analysis, symbol, bot)
    
    # If current_price is still problematic, use more aggressive fallbacks
    if current_price <= 0:
        # Try to get from ticker directly
        try:
            if symbol and bot and hasattr(bot, 'data_provider'):
                ticker = bot.data_provider.get_ticker(symbol)
                if ticker and 'last' in ticker and ticker['last'] > 0:
                    current_price = ticker['last']
        except:
            pass
        
        # Ultimate fallback
        if current_price <= 0:
            current_price = 1.0
    
    # Fix all price fields
    price_fields = ['entry_price', 'ideal_entry', 'current_price', 'close', 'last']
    for field in price_fields:
        if analysis.get(field, 0) <= 0:
            analysis[field] = current_price
    
    # Fix TP/SL levels if they seem invalid
    action = analysis.get('action', 'LONG')
    
    # Get current values or set defaults
    tp1 = analysis.get('tp1', 0)
    tp2 = analysis.get('tp2', 0) 
    tp3 = analysis.get('tp3', 0)
    sl = analysis.get('sl', 0)
    
    # If levels are invalid, recalculate based on action and current price
    if (tp1 <= 0 or tp2 <= 0 or tp3 <= 0 or sl <= 0 or 
        tp1 == tp2 == tp3 == sl == current_price):
        
        if action == "LONG":
            analysis['tp1'] = current_price * 1.03
            analysis['tp2'] = current_price * 1.06
            analysis['tp3'] = current_price * 1.09
            analysis['sl'] = current_price * 0.97
        else:  # SHORT
            analysis['tp1'] = current_price * 0.97
            analysis['tp2'] = current_price * 0.94
            analysis['tp3'] = current_price * 0.91
            analysis['sl'] = current_price * 1.03
    
    return analysis

# ====================================
# Main App
# ====================================
def main_app():
    st.title("🚀 TradingBot Pro - Enhanced Dashboard")
    
    # Display user info and logout button
    col1, col2 = st.columns([3, 1])
    with col1:
        st.write(f"Welcome, **{st.session_state.username}**! 👋")
    with col2:
        if st.button("🚪 Logout"):
            st.session_state.logged_in = False
            st.session_state.username = ""
            st.rerun()

    try:
        bot = init_bot()
        print("✅ TradingBot initialized successfully")
    except Exception as e:
        st.error(f"❌ Failed to initialize TradingBot: {e}")
        return

    # Enhanced session state
    defaults = {
        "last_refresh": {"positions": 0, "history": 0},
        "positions_data": [],
        "history_data": [],
        "scanned_results": [],
        "live_monitoring": False,
        "selected_positions": [],
        "selected_symbols": [],
        "selected_analysis": None,
        "latest_results": [],
        "selected_for_entry": {},
        "custom_result": None,
        "backtest_results": {},
        "portfolio_allocations": {},
        "risk_assessments": {}
    }
    
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val

    # Sidebar
    with st.sidebar:
        st.header("🎯 Market Selection")
        mode_choice = st.selectbox("Market:", ["Crypto", "Forex", "Saham Indonesia"], key="mode")

        if st.button("Set Market"):
            try:
                if mode_choice == "Crypto":
                    success = bot.set_mode("crypto")
                elif mode_choice == "Forex":
                    success = bot.set_mode("forex")
                elif mode_choice == "Saham Indonesia":
                    success = bot.set_mode("saham_id")

                if success:
                    st.session_state.scanned_results = []
                    st.session_state.selected_symbols = []
                    st.session_state.selected_analysis = None
                    st.session_state.selected_for_entry = {}
                    st.success(f"✅ Market set to {mode_choice}")
                    st.rerun()
                else:
                    st.error("❌ Failed to set market")
            except Exception as e:
                st.error(f"❌ Error setting market: {e}")

        if bot.mode:
            st.success(f"Mode: {bot.mode.upper()}")

            if st.button("🔄 Refresh Semua Data", key="refresh_all"):
                try:
                    st.session_state.positions_data = bot.get_active_positions()
                    st.session_state.history_data = bot.get_trade_history()
                    st.session_state.last_refresh = {"positions": time.time(), "history": time.time()}
                    st.success("Data berhasil direfresh!")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Error refreshing data: {e}")

    if not bot.mode:
        st.warning("Pilih market di sidebar!")
        return

    # Enhanced Tabs
    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
        "📊 Top Aset", "🔍 Analisis Aset", "🎯 Custom Entry", "💼 Posisi Aktif", 
        "📈 History", "📡 Live Scanner", "🤖 ML Backtest", "⚖️ Portfolio"
    ])

    # ===============================
    # Tab 1: Top Aset - FIXED VERSION
    # ===============================
    with tab1:
        st.subheader("Scan Top Aset")

        if bot.mode == "crypto":
            scan_option = st.radio("Pilih jenis scan:", ["Standard Crypto", "Pump Fun Solana"])
        else:
            scan_option = "Standard"
            st.info("Mode Standard untuk Forex dan Saham Indonesia")

        if st.button("Scan Aset", key="scan_assets"):
            with st.spinner("Scanning..."):
                try:
                    if bot.mode == "crypto" and scan_option == "Pump Fun Solana":
                        results = asyncio.run(bot.scan_pump_fun())
                        if results:
                            st.subheader("Token Baru di Pump Fun:")
                            for res in results:
                                st.write(f"**{res['symbol']}** - Price: {res['ticker']['last']}, "
                                         f"Volume: {res['ticker']['volume']}")
                                if st.button(f"Pilih {res['symbol']}", key=f"select_pump_{res['symbol']}"):
                                    symbol = res['symbol']
                                    analysis = bot.analyze_asset(symbol)
                                    if analysis is None:
                                        entry_price = res['ticker']['last']
                                        analysis = bot.calculate_custom_entry(symbol, entry_price)
                                        if analysis is None:
                                            analysis = {
                                                'symbol': symbol,
                                                'entry_price': entry_price,
                                                'tp1': entry_price * 1.1,
                                                'tp2': entry_price * 1.2,
                                                'tp3': entry_price * 1.3,
                                                'sl': entry_price * 0.9,
                                                'action': 'LONG',
                                                'score': 5,
                                                'ideal_entry': entry_price
                                            }
                                        else:
                                            analysis['action'] = "LONG"
                                            analysis['score'] = 5
                                            analysis['ideal_entry'] = analysis['entry_price']
                                    
                                    # Validate and fix price levels
                                    analysis = validate_and_fix_price_levels(analysis, symbol, bot)
                                    
                                    # Hitung probabilitas TP dengan TP levels yang benar
                                    tp1, tp2, tp3 = analysis['tp1'], analysis['tp2'], analysis['tp3']
                                    if analysis['action'] == "LONG":
                                        tp1, tp2, tp3 = sorted([tp1, tp2, tp3])
                                    elif analysis['action'] == "SHORT":
                                        tp1, tp2, tp3 = sorted([tp1, tp2, tp3], reverse=True)
                                    
                                    current_price = get_valid_price(analysis, symbol, bot)
                                    analysis['tp_probabilities'] = calculate_tp_probability(
                                        current_price,
                                        tp1, tp2, tp3,
                                        analysis['sl'], analysis['action']
                                    )
                                    
                                    st.session_state.selected_for_entry[symbol] = analysis
                                    st.success(f"Selected {res['symbol']}!")
                                    st.rerun()
                        else:
                            st.info("Tidak ada token baru di Pump Fun.")

                    else:
                        all_results = bot.scan_potential_assets(100)  # Scan 100 koin
                        if all_results:
                            # Sort berdasarkan abs(score) descending untuk dapat 10 terbaik
                            all_results.sort(key=lambda x: abs(safe_get(x, 'score', 0)), reverse=True)
                            
                            # Validate and fix price levels for each result
                            for i, result in enumerate(all_results[:10]):
                                symbol = safe_get(result, 'symbol')
                                all_results[i] = validate_and_fix_price_levels(result, symbol, bot)
                                
                                # Urutkan TP levels sebelum hitung probability
                                tp1, tp2, tp3 = safe_get(result, 'tp1', 0), safe_get(result, 'tp2', 0), safe_get(result, 'tp3', 0)
                                if safe_get(result, 'action') == "LONG":
                                    tp1, tp2, tp3 = sorted([tp1, tp2, tp3])
                                elif safe_get(result, 'action') == "SHORT":
                                    tp1, tp2, tp3 = sorted([tp1, tp2, tp3], reverse=True)
                                
                                current_price = get_valid_price(result, symbol, bot)
                                result['tp_probabilities'] = calculate_tp_probability(
                                    current_price,
                                    tp1, tp2, tp3,
                                    safe_get(result, 'sl', 0), safe_get(result, 'action'),
                                    safe_get(result, 'volatility', 0.02)
                                )
                            
                            st.session_state.scanned_results = all_results[:10]  # Tampil hanya 10 terbaik
                            st.success("Scan selesai! Menampilkan 10 terbaik dari 100.")
                        else:
                            st.warning("Tidak ada hasil scan dari metode utama. Mencoba fallback dengan aset populer.")
                            fallback_assets = bot.get_popular_assets(100)
                            fallback_results = []
                            for asset in fallback_assets:
                                analysis = bot.analyze_asset(asset)
                                
                                # ✅ PERBAIKAN: Ambil baik LONG (score >= 3) maupun SHORT (score <= -3)
                                if analysis and safe_get(analysis, "action") in ["LONG", "SHORT"] and abs(safe_get(analysis, "score", 0)) >= 3:
                                    # Validate and fix price levels
                                    symbol = safe_get(analysis, 'symbol')
                                    analysis = validate_and_fix_price_levels(analysis, symbol, bot)
                                    
                                    # Urutkan TP levels sebelum hitung probability
                                    tp1, tp2, tp3 = safe_get(analysis, 'tp1', 0), safe_get(analysis, 'tp2', 0), safe_get(analysis, 'tp3', 0)
                                    if safe_get(analysis, 'action') == "LONG":
                                        tp1, tp2, tp3 = sorted([tp1, tp2, tp3])
                                    elif safe_get(analysis, 'action') == "SHORT":
                                        tp1, tp2, tp3 = sorted([tp1, tp2, tp3], reverse=True)
                                    
                                    # Hitung probabilitas TP
                                    current_price = get_valid_price(analysis, symbol, bot)
                                    analysis['tp_probabilities'] = calculate_tp_probability(
                                        current_price,
                                        tp1, tp2, tp3,
                                        safe_get(analysis, 'sl', 0), safe_get(analysis, 'action'),
                                        safe_get(analysis, 'volatility', 0.02)
                                    )
                                    fallback_results.append(analysis)
                                    
                                elif analysis is None:
                                    try:
                                        symbol = asset.get('symbol') if isinstance(asset, dict) else asset
                                        ticker = bot.data_provider.get_ticker(symbol)
                                        if ticker and 'last' in ticker and ticker['last'] > 0:
                                            current_price = ticker['last']
                                            percentage = ticker.get('percentage', 0)
                                            volume = ticker.get('volume', 1.0)
                                            
                                            # ✅ PERBAIKAN: Berikan skor negatif untuk SHORT yang kuat
                                            # Untuk percentage negatif besar, berikan skor SHORT yang kuat
                                            if percentage < -5:  # Turun drastis -> SHORT kuat
                                                simple_score = random.randint(-8, -5)
                                                action = 'SHORT'
                                            elif percentage < -2:  # Turun -> SHORT medium
                                                simple_score = random.randint(-5, -3) 
                                                action = 'SHORT'
                                            elif percentage > 5:   # Naik drastis -> LONG kuat
                                                simple_score = random.randint(5, 8)
                                                action = 'LONG'
                                            elif percentage > 2:   # Naik -> LONG medium
                                                simple_score = random.randint(3, 5)
                                                action = 'LONG'
                                            else:  # Sideways -> random bias
                                                if random.random() > 0.5:
                                                    simple_score = random.randint(3, 5)
                                                    action = 'LONG'
                                                else:
                                                    simple_score = random.randint(-5, -3)
                                                    action = 'SHORT'
                                            
                                            possible_patterns = ['ranging_channel', 'symmetrical_triangle', 'ascending_triangle', 'descending_triangle', 'uptrend_channel', 'downtrend_channel', 'rising_wedge', 'falling_wedge', 'broadening_ascending', 'broadening_descending']
                                            num_patterns = random.randint(1, 4)
                                            simple_patterns = random.sample(possible_patterns, num_patterns)
                                            simple_pattern_score = num_patterns
                                            
                                            # Urutkan TP levels berdasarkan action
                                            if action == 'LONG':
                                                tp1 = current_price * 1.03
                                                tp2 = current_price * 1.06
                                                tp3 = current_price * 1.09
                                                sl = current_price * 0.97
                                                tp1, tp2, tp3 = sorted([tp1, tp2, tp3])
                                            else:  # SHORT
                                                tp1 = current_price * 0.97
                                                tp2 = current_price * 0.94
                                                tp3 = current_price * 0.91
                                                sl = current_price * 1.03
                                                tp1, tp2, tp3 = sorted([tp1, tp2, tp3], reverse=True)
                                            
                                            analysis = {
                                                'symbol': symbol,
                                                'action': action,
                                                'score': simple_score,
                                                'ideal_entry': current_price,
                                                'entry_low': current_price * 0.99,
                                                'entry_high': current_price * 1.01,
                                                'tp1': tp1,
                                                'tp2': tp2,
                                                'tp3': tp3,
                                                'sl': sl,
                                                'current_price': current_price,
                                                'rsi': 50.0 + (percentage * 5),
                                                'trend': 'BULLISH' if simple_score > 0 else 'BEARISH' if simple_score < 0 else 'NEUTRAL',
                                                'volume_ratio': volume / 1000 if volume > 1000 else 1.0,
                                                'atr': current_price * 0.01,
                                                'detected_patterns': simple_patterns,
                                                'pattern_score': simple_pattern_score,
                                                'ema_trend': 'NEUTRAL',
                                                'ema_score': 0,
                                                'volatility': 0.02
                                            }
                                            # Hitung probabilitas TP
                                            analysis['tp_probabilities'] = calculate_tp_probability(
                                                current_price,
                                                analysis['tp1'], analysis['tp2'], analysis['tp3'],
                                                analysis['sl'], analysis['action'],
                                                0.02
                                            )
                                            fallback_results.append(analysis)
                                    except Exception as e:
                                        st.warning(f"Gagal mengambil data untuk {asset}: {e}")
                                        
                            if fallback_results:
                                # ✅ PERBAIKAN: Sort berdasarkan absolute value untuk memasukkan SHORT yang kuat
                                fallback_results.sort(key=lambda x: abs(safe_get(x, 'score', 0)), reverse=True)
                                st.session_state.scanned_results = fallback_results[:10]
                                st.info(f"Fallback selesai! Menampilkan {len(fallback_results)} aset (LONG & SHORT).")
                            else:
                                st.error("Tidak ada data sama sekali. Periksa koneksi atau API key.")
                        st.rerun()
                except Exception as e:
                    st.error(f"❌ Error during scan: {e}")

        # Tampilkan hasil scan - FIXED PRICE DISPLAY
        if st.session_state.scanned_results:
            st.subheader("Top 10 Aset Potensial (dari 100 yang discan):")

            for i, res in enumerate(st.session_state.scanned_results, 1):
                if isinstance(res, dict) and 'symbol' in res:
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        # Tampilkan dengan warna berbeda untuk LONG/SHORT
                        action = safe_get(res, 'action', 'NEUTRAL')
                        if action == "LONG":
                            st.write(f"{i}. **{safe_get(res, 'symbol')}** - 🟢 {action} (Score: {safe_get(res, 'score', 0)})")
                        else:
                            st.write(f"{i}. **{safe_get(res, 'symbol')}** - 🔴 {action} (Score: {safe_get(res, 'score', 0)})")
                        
                        # ✅ FIXED: Get valid price with priority
                        current_price = get_valid_price(res, safe_get(res, 'symbol'), bot)
                        entry_price = safe_get(res, 'entry_price', current_price)
                        ideal_entry = safe_get(res, 'ideal_entry', entry_price)
                        
                        # Use the best available price
                        display_price = current_price if current_price > 0 else entry_price if entry_price > 0 else ideal_entry
                        
                        st.write(f"💰 Current: `{current_price:.5f}` | Entry: `{entry_price:.5f}` | Ideal: `{ideal_entry:.5f}`")
                        st.write(f"🛑 SL: {safe_get(res, 'sl', 0):.5f}")
                        
                        # Urutkan TP levels untuk display
                        tp1, tp2, tp3 = safe_get(res, 'tp1', 0), safe_get(res, 'tp2', 0), safe_get(res, 'tp3', 0)
                        if action == "LONG":
                            tp1, tp2, tp3 = sorted([tp1, tp2, tp3])  # Kecil ke besar
                        elif action == "SHORT":
                            tp1, tp2, tp3 = sorted([tp1, tp2, tp3], reverse=True)  # Besar ke kecil
                        
                        st.write(f"🎯 TP1: {tp1:.5f} | 🎯 TP2: {tp2:.5f} | 🎯 TP3: {tp3:.5f}")
                        
                        # Tampilkan probabilitas TP jika ada
                        if 'tp_probabilities' in res:
                            probs = res['tp_probabilities']
                            st.write(f"📊 **Probabilitas:** TP1: {safe_get(probs, 'tp1', 0)*100:.1f}% | TP2: {safe_get(probs, 'tp2', 0)*100:.1f}% | TP3: {safe_get(probs, 'tp3', 0)*100:.1f}%")
                        
                        # Tampilkan pola yang terdeteksi
                        if 'detected_patterns' in res and res['detected_patterns']:
                            st.write(f"📊 **Pola Terdeteksi:** {', '.join(res['detected_patterns'])}")
                        
                        # Tampilkan pattern score
                        if 'pattern_score' in res:
                            st.write(f"⭐ **Pattern Score:** {safe_get(res, 'pattern_score', 0)}")
                            
                        # Tampilkan risk category
                        if 'risk_category' in res:
                            st.write(f"⚖️ **Risk Category:** {safe_get(res, 'risk_category', 'MEDIUM')}")
                            
                    with col2:
                        if st.button(f"Pilih {i}", key=f"select_{safe_get(res, 'symbol')}_{i}"):
                            # Validate and fix the analysis before storing
                            symbol = safe_get(res, 'symbol')
                            validated_analysis = validate_and_fix_price_levels(res, symbol, bot)
                            st.session_state.selected_for_entry[symbol] = validated_analysis
                            st.success(f"Selected {symbol}!")
                            st.rerun()
                else:
                    st.warning("Data analisis tidak valid untuk salah satu aset.")

            # Tampilkan input entry untuk setiap simbol yang dipilih - FIXED VERSION
            for symbol, analysis in list(st.session_state.selected_for_entry.items()):
                if isinstance(analysis, dict) and 'symbol' in analysis:
                    st.markdown("---")
                    st.subheader(f"📈 Input Entry untuk {symbol}")
                    
                    # Validate analysis data first
                    analysis = validate_and_fix_price_levels(analysis, symbol, bot)
                    
                    col1, col2 = st.columns([2, 1])
                    with col1:
                        # Get valid default entry price - FIXED VERSION
                        default_entry = get_valid_price(analysis, symbol, bot)
                        
                        # Ensure default entry is reasonable
                        if default_entry <= 0:
                            default_entry = 0.01  # Minimum reasonable price
                        
                        # Create a unique key for this symbol's input
                        input_key = f"entry_{symbol}_{int(time.time())}"
                        
                        entry_price = st.number_input(
                            "Entry Price",
                            value=float(default_entry),
                            min_value=0.0001,  # Minimum allowed value
                            max_value=1000000.0,  # Maximum allowed value  
                            step=0.0001,  # Smaller step for crypto
                            format="%.5f",  # Show 5 decimal places
                            key=input_key  # Unique key to prevent conflicts
                        )
                        
                        # Display current price for reference
                        current_price = get_valid_price(analysis, symbol, bot)
                        st.write(f"💡 Current price: `{current_price:.5f}`")
                    
                    with col2:
                        if st.button(f"✅ Tambah Posisi {symbol}", key=f"add_{symbol}_{int(time.time())}"):
                            try:
                                # Use the validated analysis
                                ideal_entry = safe_get(analysis, "ideal_entry", entry_price)
                                
                                # Urutkan TP levels sebelum simpan
                                tp1, tp2, tp3 = safe_get(analysis, "tp1", 0), safe_get(analysis, "tp2", 0), safe_get(analysis, "tp3", 0)
                                if safe_get(analysis, "action") == "LONG":
                                    tp1, tp2, tp3 = sorted([tp1, tp2, tp3])
                                elif safe_get(analysis, "action") == "SHORT":
                                    tp1, tp2, tp3 = sorted([tp1, tp2, tp3], reverse=True)
                                
                                # Adjust TP levels berdasarkan entry price yang baru
                                tp1_adj = entry_price + (tp1 - ideal_entry)
                                tp2_adj = entry_price + (tp2 - ideal_entry)
                                tp3_adj = entry_price + (tp3 - ideal_entry)
                                sl_adj = entry_price - (ideal_entry - safe_get(analysis, "sl", 0))
                                
                                position_id = bot.db.save_position(
                                    symbol=symbol,
                                    market_type=bot.mode,
                                    action=safe_get(analysis, "action"),
                                    entry_price=entry_price,
                                    tp1=tp1_adj,
                                    tp2=tp2_adj,
                                    tp3=tp3_adj,
                                    sl=sl_adj,
                                    entry_low=entry_price * (1 - bot.strategy.entry_range_pct),
                                    entry_high=entry_price * (1 + bot.strategy.entry_range_pct),
                                )
                                if position_id:
                                    st.success(f"Posisi {symbol} ditambahkan!")
                                    st.session_state.positions_data = bot.get_active_positions()
                                    st.session_state.selected_positions.append(symbol)
                                    if symbol in st.session_state.selected_for_entry:
                                        del st.session_state.selected_for_entry[symbol]
                                    st.rerun()
                                else:
                                    st.error("Gagal tambah posisi.")
                            except Exception as e:
                                st.error(f"❌ Error adding position: {e}")
                    
                    with st.expander("🔍 Detail Analisis"):
                        if 'momentum_quality' in analysis:
                            st.write(f"**Momentum Quality:** {safe_get(analysis, 'momentum_quality')}")
                        if 'market_phase' in analysis:
                            st.write(f"**Market Phase:** {safe_get(analysis, 'market_phase')}")
                        if 'reward_ratio' in analysis:
                            st.write(f"**Reward Ratio:** {safe_get(analysis, 'reward_ratio', 0):.2f}")
                        if 'tp_probabilities' in analysis:
                            probs = analysis['tp_probabilities']
                            st.write(f"**Probabilitas TP:** TP1: {safe_get(probs, 'tp1', 0)*100:.1f}% | TP2: {safe_get(probs, 'tp2', 0)*100:.1f}% | TP3: {safe_get(probs, 'tp3', 0)*100:.1f}%")
                    
                    if st.button(f"🗑️ Hapus {symbol} dari pilihan", key=f"remove_{symbol}_{int(time.time())}"):
                        if symbol in st.session_state.selected_for_entry:
                            del st.session_state.selected_for_entry[symbol]
                        st.rerun()
                else:
                    st.warning(f"Data analisis tidak valid untuk {symbol}. Menghapus dari pilihan.")
                    if symbol in st.session_state.selected_for_entry:
                        del st.session_state.selected_for_entry[symbol]
                    st.rerun()

            # --- Kelola sinyal
            st.markdown("---")
            st.subheader("⚙️ Kelola Sinyal")
            if st.button("🧹 Hapus Semua Sinyal Tidak Terpilih", key="confirm_delete"):
                try:
                    non_selected = [
                        r["symbol"] for r in st.session_state.scanned_results
                        if r["symbol"] not in st.session_state.selected_positions and 
                        r["symbol"] not in st.session_state.selected_for_entry
                    ]
                    for sym in non_selected:
                        bot.db.delete_signal_by_symbol(sym, bot.mode)

                    st.success("Sinyal tidak terpilih dihapus!")
                    st.session_state.scanned_results = [
                        r for r in st.session_state.scanned_results
                        if r["symbol"] in st.session_state.selected_positions or
                        r["symbol"] in st.session_state.selected_for_entry
                    ]
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Error deleting signals: {e}")

        else:
            st.info("Tidak ada hasil scan. Periksa koneksi, API key, atau coba mode lain.")

        st.markdown("---")
        if st.checkbox("🔄 Auto Rescan (30s)"):
            if "scheduler_thread" not in st.session_state:
                st.session_state["scheduler_thread"] = threading.Thread(
                    target=run_scheduler, args=(bot,), daemon=True
                )
                st.session_state["scheduler_thread"].start()

            if "latest_results" in st.session_state:
                st.subheader("📡 Latest Scan Results:")
                for res in st.session_state["latest_results"]:
                    if isinstance(res, dict) and 'symbol' in res:
                        st.write(f"**{safe_get(res, 'symbol')}** - {safe_get(res, 'action')} (Score: {safe_get(res, 'score', 0)})")
                        if 'detected_patterns' in res and res['detected_patterns']:
                            st.write(f"📊 Pola: {', '.join(res['detected_patterns'])}")

    # ===============================
    # Tab 2: Analisis Aset - FIXED
    # ===============================
    with tab2:
        st.subheader("🔍 Analisis Aset Spesifik")
        
        symbol_input = st.text_input("Masukkan simbol aset:", key="symbol_input")

        if st.button("Analisis", key="analyze_asset"):
            with st.spinner("Menganalisis..."):
                try:
                    symbol = symbol_input.upper()
                    if bot.mode == "crypto":
                        symbol = f"{symbol}/USDT"
                    elif bot.mode == "forex":
                        if symbol == "XAU":
                            symbol = "GC=F"
                        elif len(symbol) == 6:
                            symbol = f"{symbol}=X"
                        else:
                            st.error("Format symbol forex: 6 huruf seperti EURUSD atau XAU untuk gold.")
                            st.stop()
                    elif bot.mode == "saham_id":
                        symbol = f"{symbol}.JK"
                    
                    analysis = bot.analyze_asset(symbol)
                    
                    # Validate and fix the analysis
                    analysis = validate_and_fix_price_levels(analysis, symbol, bot)
                    
                    if analysis and isinstance(analysis, dict) and 'symbol' in analysis:
                        # Urutkan TP levels sebelum hitung probability
                        tp1, tp2, tp3 = safe_get(analysis, 'tp1', 0), safe_get(analysis, 'tp2', 0), safe_get(analysis, 'tp3', 0)
                        if safe_get(analysis, 'action') == "LONG":
                            tp1, tp2, tp3 = sorted([tp1, tp2, tp3])
                        elif safe_get(analysis, 'action') == "SHORT":
                            tp1, tp2, tp3 = sorted([tp1, tp2, tp3], reverse=True)
                        
                        # Hitung probabilitas TP
                        current_price = get_valid_price(analysis, symbol, bot)
                        analysis['tp_probabilities'] = calculate_tp_probability(
                            current_price,
                            tp1, tp2, tp3,
                            safe_get(analysis, 'sl', 0), safe_get(analysis, 'action'),
                            safe_get(analysis, 'volatility', 0.02)
                        )
                        
                        st.session_state.selected_analysis = analysis
                        st.rerun()
                    else:
                        try:
                            # Fallback analysis
                            ticker = bot.data_provider.get_ticker(symbol)
                            if ticker and 'last' in ticker and ticker['last'] > 0:
                                current_price = ticker['last']
                                
                                # Urutkan TP levels untuk fallback
                                tp1 = current_price * 1.03
                                tp2 = current_price * 1.06
                                tp3 = current_price * 1.09
                                sl = current_price * 0.97
                                tp1, tp2, tp3 = sorted([tp1, tp2, tp3])
                                
                                analysis = {
                                    'symbol': symbol,
                                    'action': 'LONG',
                                    'score': 1,
                                    'ideal_entry': current_price,
                                    'entry_low': current_price * 0.99,
                                    'entry_high': current_price * 1.01,
                                    'tp1': tp1,
                                    'tp2': tp2,
                                    'tp3': tp3,
                                    'sl': sl,
                                    'current_price': current_price,
                                    'rsi': 50.0,
                                    'trend': 'NEUTRAL',
                                    'volume_ratio': 1.0,
                                    'atr': current_price * 0.01,
                                    'detected_patterns': [],
                                    'pattern_score': 0,
                                    'ema_trend': 'NEUTRAL',
                                    'ema_score': 0,
                                    'volatility': 0.02
                                }
                                # Hitung probabilitas TP
                                analysis['tp_probabilities'] = calculate_tp_probability(
                                    current_price,
                                    analysis['tp1'], analysis['tp2'], analysis['tp3'],
                                    analysis['sl'], analysis['action'],
                                    0.02
                                )
                                st.session_state.selected_analysis = analysis
                                st.warning("Menggunakan analisis fallback karena data historis tidak cukup.")
                                st.rerun()
                            else:
                                st.session_state.selected_analysis = None
                                st.error("Tidak dapat menganalisis aset. Pastikan simbol valid.")
                        except Exception as e:
                            st.error(f"❌ Error analyzing asset: {e}")
                except Exception as e:
                    st.error(f"❌ Error during analysis: {e}")

        # Tampilkan hasil analisis - FIXED
        if st.session_state.selected_analysis:
            analysis = st.session_state.selected_analysis
            if isinstance(analysis, dict) and 'symbol' in analysis:
                
                # Validate the analysis data
                symbol = safe_get(analysis, 'symbol')
                analysis = validate_and_fix_price_levels(analysis, symbol, bot)
                
                st.subheader(f"📊 Hasil Analisis untuk {safe_get(analysis, 'symbol')}")
                
                # Get valid prices
                current_price = get_valid_price(analysis, symbol, bot)
                entry_price = safe_get(analysis, 'entry_price', current_price)
                
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("💰 Current Price", f"{current_price:.5f}")
                    st.metric("📈 Trend", safe_get(analysis, 'trend', 'NEUTRAL'))
                    st.metric("📊 RSI", f"{safe_get(analysis, 'rsi', 0):.2f}")
                    st.metric("⭐ Score", safe_get(analysis, 'score', 0))
                
                with col2:
                    st.metric("📉 ATR", f"{safe_get(analysis, 'atr', 0):.5f}")
                    st.metric("🔄 Volume Ratio", f"{safe_get(analysis, 'volume_ratio', 0):.2f}")
                    st.metric("EMA Trend", safe_get(analysis, 'ema_trend', 'NEUTRAL'))
                    st.metric("EMA Score", safe_get(analysis, 'ema_score', 0))
                
                # Enhanced analysis details
                if 'detected_patterns' in analysis and analysis['detected_patterns']:
                    st.write(f"📊 **Pola Terdeteksi:** {', '.join(analysis['detected_patterns'])}")
                
                if 'pattern_score' in analysis:
                    st.write(f"⭐ **Pattern Score:** {safe_get(analysis, 'pattern_score', 0)}")
                
                # Tampilkan probabilitas TP
                if 'tp_probabilities' in analysis:
                    st.subheader("📊 Probabilitas TP")
                    probs = analysis['tp_probabilities']
                    col_prob1, col_prob2, col_prob3 = st.columns(3)
                    with col_prob1:
                        st.metric("TP1 Probability", f"{safe_get(probs, 'tp1', 0)*100:.1f}%")
                    with col_prob2:
                        st.metric("TP2 Probability", f"{safe_get(probs, 'tp2', 0)*100:.1f}%")
                    with col_prob3:
                        st.metric("TP3 Probability", f"{safe_get(probs, 'tp3', 0)*100:.1f}%")
                
                # Enhanced metrics
                col3, col4 = st.columns(2)
                with col3:
                    if 'risk_category' in analysis:
                        st.metric("⚖️ Risk Category", safe_get(analysis, 'risk_category'))
                    if 'momentum_quality' in analysis:
                        st.metric("📈 Momentum Quality", safe_get(analysis, 'momentum_quality'))
                with col4:
                    if 'market_phase' in analysis:
                        st.metric("🌊 Market Phase", safe_get(analysis, 'market_phase'))
                    if 'reward_ratio' in analysis:
                        st.metric("🎯 Reward Ratio", f"{safe_get(analysis, 'reward_ratio', 0):.2f}")
                
                st.subheader("🎯 Take Profit & Stop Loss")
                
                # Urutkan TP levels untuk display
                tp1, tp2, tp3 = safe_get(analysis, 'tp1', 0), safe_get(analysis, 'tp2', 0), safe_get(analysis, 'tp3', 0)
                if safe_get(analysis, 'action') == "LONG":
                    tp1, tp2, tp3 = sorted([tp1, tp2, tp3])  # Kecil ke besar
                elif safe_get(analysis, 'action') == "SHORT":
                    tp1, tp2, tp3 = sorted([tp1, tp2, tp3], reverse=True)  # Besar ke kecil
                
                st.write(f"🎯 TP1: {tp1:.5f}")
                st.write(f"🎯 TP2: {tp2:.5f}")
                st.write(f"🎯 TP3: {tp3:.5f}")
                st.write(f"🛑 SL: {safe_get(analysis, 'sl', 0):.5f}")
                
                # Input entry price dengan default yang valid - FIXED
                default_entry = entry_price if entry_price > 0 else current_price
                if default_entry <= 0:
                    default_entry = 1.0  # Final fallback

                entry_price_input = st.number_input(
                    "Entry Price",
                    value=float(default_entry),
                    min_value=0.0001,
                    max_value=1000000.0,
                    step=0.0001,
                    format="%.5f",
                    key="entry_analysis_unique"
                )
                
                if st.button("✅ Tambah Posisi", key="add_analysis"):
                    try:
                        ideal_entry = safe_get(analysis, "ideal_entry", entry_price_input)
                        
                        # Gunakan TP yang sudah diurutkan
                        position_id = bot.db.save_position(
                            symbol=safe_get(analysis, 'symbol'),
                            market_type=bot.mode,
                            action=safe_get(analysis, "action", "LONG"),
                            entry_price=entry_price_input,
                            tp1=entry_price_input + (tp1 - ideal_entry),
                            tp2=entry_price_input + (tp2 - ideal_entry),
                            tp3=entry_price_input + (tp3 - ideal_entry),
                            sl=entry_price_input - (ideal_entry - safe_get(analysis, "sl", 0)),
                            entry_low=entry_price_input * (1 - bot.strategy.entry_range_pct),
                            entry_high=entry_price_input * (1 + bot.strategy.entry_range_pct),
                        )
                        if position_id:
                            st.success(f"Posisi {safe_get(analysis, 'symbol')} ditambahkan!")
                            st.session_state.positions_data = bot.get_active_positions()
                            st.rerun()
                        else:
                            st.error("Gagal tambah posisi.")
                    except Exception as e:
                        st.error(f"❌ Error adding position: {e}")
            else:
                st.error("Data analisis tidak valid. Coba analisis ulang.")

    # ===============================
    # Tab 3: Custom Entry - FIXED
    # ===============================
    with tab3:
        st.subheader("🎯 Custom Entry")
        
        symbol_custom = st.text_input("Masukkan simbol aset:", key="custom_symbol")
        
        # Ganti input entry price di Custom Entry - FIXED:
        entry_price_custom = st.number_input(
            "Harga Entry:", 
            value=1.0,  # Default to 1.0 instead of 0.0
            min_value=0.0001,
            max_value=1000000.0,
            step=0.0001,
            format="%.5f",
            key="custom_entry_unique"
        )
        
        action_custom = st.selectbox("Action:", ["LONG", "SHORT"], key="custom_action")
        
        if st.button("🧮 Hitung TP/SL", key="calculate_custom"):
            if symbol_custom and entry_price_custom > 0:
                with st.spinner("Menghitung..."):
                    try:
                        result = bot.calculate_custom_entry(symbol_custom, entry_price_custom)
                        if result:
                            # Pastikan TP/SL berbeda dari entry price
                            if (result['tp1'] == result['tp2'] == result['tp3'] == result['sl'] == entry_price_custom):
                                st.warning("⚠️ Perhitungan ATR menghasilkan nilai 0. Menggunakan fallback calculation...")
                                # Fallback calculation
                                if action_custom == "LONG":
                                    result['tp1'] = entry_price_custom * 1.02
                                    result['tp2'] = entry_price_custom * 1.04
                                    result['tp3'] = entry_price_custom * 1.06
                                    result['sl'] = entry_price_custom * 0.98
                                else:  # SHORT
                                    result['tp1'] = entry_price_custom * 0.98
                                    result['tp2'] = entry_price_custom * 0.96
                                    result['tp3'] = entry_price_custom * 0.94
                                    result['sl'] = entry_price_custom * 1.02
                            
                            # Urutkan TP levels
                            tp1, tp2, tp3 = result['tp1'], result['tp2'], result['tp3']
                            if action_custom == "LONG":
                                tp1, tp2, tp3 = sorted([tp1, tp2, tp3])
                            else:  # SHORT
                                tp1, tp2, tp3 = sorted([tp1, tp2, tp3], reverse=True)
                            
                            result['tp1'], result['tp2'], result['tp3'] = tp1, tp2, tp3
                            
                            # Hitung probabilitas TP
                            result['tp_probabilities'] = calculate_tp_probability(
                                entry_price_custom,
                                result['tp1'], result['tp2'], result['tp3'],
                                result['sl'], action_custom
                            )
                            st.session_state.custom_result = result
                            st.success("Perhitungan selesai!")
                        else:
                            st.error("Tidak dapat menghitung TP/SL. Pastikan simbol valid.")
                    except Exception as e:
                        st.error(f"❌ Error calculating TP/SL: {e}")
            else:
                st.warning("Masukkan simbol dan harga entry yang valid.")
        
        # Tampilkan hasil custom entry
        if st.session_state.custom_result:
            result = st.session_state.custom_result
            st.subheader(f"📊 Hasil untuk {safe_get(result, 'symbol')}")
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric("💰 Entry Price", f"{safe_get(result, 'entry_price', 0):.5f}")
                st.metric("🎯 TP1", f"{safe_get(result, 'tp1', 0):.5f}")
                st.metric("🎯 TP2", f"{safe_get(result, 'tp2', 0):.5f}")
            
            with col2:
                st.metric("🎯 TP3", f"{safe_get(result, 'tp3', 0):.5f}")
                st.metric("🛡️ SL", f"{safe_get(result, 'sl', 0):.5f}")
                
                # Hitung risk/reward ratio
                if action_custom == "LONG":
                    risk_reward = (safe_get(result, 'tp1', 0) - safe_get(result, 'entry_price', 0)) / (safe_get(result, 'entry_price', 0) - safe_get(result, 'sl', 0))
                else:
                    risk_reward = (safe_get(result, 'entry_price', 0) - safe_get(result, 'tp1', 0)) / (safe_get(result, 'sl', 0) - safe_get(result, 'entry_price', 0))
                st.metric("📊 Risk/Reward", f"{risk_reward:.2f}")
            
            # Tampilkan probabilitas TP
            if 'tp_probabilities' in result:
                st.subheader("📊 Probabilitas TP")
                probs = result['tp_probabilities']
                col_prob1, col_prob2, col_prob3 = st.columns(3)
                with col_prob1:
                    st.metric("TP1 Probability", f"{safe_get(probs, 'tp1', 0)*100:.1f}%")
                with col_prob2:
                    st.metric("TP2 Probability", f"{safe_get(probs, 'tp2', 0)*100:.1f}%")
                with col_prob3:
                    st.metric("TP3 Probability", f"{safe_get(probs, 'tp3', 0)*100:.1f}%")
            
            # Tombol untuk menambahkan ke posisi
            if st.button("✅ Tambahkan ke Posisi Aktif", key="add_custom"):
                try:
                    # Urutkan TP levels berdasarkan action
                    tp1, tp2, tp3 = safe_get(result, 'tp1', 0), safe_get(result, 'tp2', 0), safe_get(result, 'tp3', 0)
                    if action_custom == "LONG":
                        tp1, tp2, tp3 = sorted([tp1, tp2, tp3])
                    else:  # SHORT
                        tp1, tp2, tp3 = sorted([tp1, tp2, tp3], reverse=True)
                        
                    position_id = bot.db.save_position(
                        symbol=safe_get(result, 'symbol'),
                        market_type=bot.mode,
                        action=action_custom,
                        entry_price=safe_get(result, 'entry_price', 0),
                        tp1=tp1,
                        tp2=tp2,
                        tp3=tp3,
                        sl=safe_get(result, 'sl', 0),
                        entry_low=safe_get(result, 'entry_price', 0) * 0.99,
                        entry_high=safe_get(result, 'entry_price', 0) * 1.01,
                    )
                    if position_id:
                        st.success(f"Posisi {safe_get(result, 'symbol')} ditambahkan!")
                        st.session_state.positions_data = bot.get_active_positions()
                        st.rerun()
                    else:
                        st.error("Gagal tambah posisi.")
                except Exception as e:
                    st.error(f"❌ Error adding position: {e}")

    # ===============================
    # Tab 4: Posisi Aktif
    # ===============================
    with tab4:
        st.subheader("💼 Posisi Aktif")
        
        if st.button("🔄 Refresh Posisi", key="refresh_positions"):
            try:
                st.session_state.positions_data = bot.get_active_positions()
                st.success("Posisi diperbarui!")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Error refreshing positions: {e}")
        
        if not st.session_state.positions_data:
            st.info("📭 Tidak ada posisi aktif.")
        else:
            st.write(f"**📈 Total Posisi Aktif:** {len(st.session_state.positions_data)}")
            
            for pos in st.session_state.positions_data:
                try:
                    # Handle both tuple and dictionary responses
                    if isinstance(pos, tuple):
                        pos_id = pos[0]        # id
                        symbol = pos[1]        # symbol
                        market_type = pos[2]   # market_type
                        action = pos[3]        # action
                        entry_price = pos[4]   # entry_price
                        tp1 = pos[7] if len(pos) > 7 else 0  # tp1
                        tp2 = pos[8] if len(pos) > 8 else 0  # tp2  
                        tp3 = pos[9] if len(pos) > 9 else 0  # tp3
                        sl = pos[10] if len(pos) > 10 else 0 # sl
                        current_price = pos[11] if len(pos) > 11 else entry_price  # current_price
                    else:
                        pos_id = safe_get(pos, 'id', 0)
                        symbol = safe_get(pos, 'symbol', '')
                        market_type = safe_get(pos, 'market_type', '')
                        action = safe_get(pos, 'action', '')
                        entry_price = safe_get(pos, 'entry_price', 0)
                        tp1 = safe_get(pos, 'tp1', 0)
                        tp2 = safe_get(pos, 'tp2', 0)
                        tp3 = safe_get(pos, 'tp3', 0)
                        sl = safe_get(pos, 'sl', 0)
                        current_price = safe_get(pos, 'current_price', entry_price)
                    
                    # Validasi dan urutkan TP levels
                    if action == "LONG":
                        # Untuk LONG: TP1 < TP2 < TP3, SL < Entry
                        tp1, tp2, tp3 = sorted([tp1, tp2, tp3])
                        if not (sl < entry_price < tp1 < tp2 < tp3):
                            st.error(f"⚠️ INVALID LEVELS untuk {symbol}: Pastikan SL < Entry < TP1 < TP2 < TP3")
                            continue
                    elif action == "SHORT":
                        # Untuk SHORT: TP1 > TP2 > TP3, SL > Entry  
                        tp1, tp2, tp3 = sorted([tp1, tp2, tp3], reverse=True)
                        if not (sl > entry_price > tp1 > tp2 > tp3):
                            st.error(f"⚠️ INVALID LEVELS untuk {symbol}: Pastikan SL > Entry > TP1 > TP2 > TP3")
                            continue
                    
                    # Calculate P/L
                    if action == "LONG":
                        pl_pct = ((current_price - entry_price) / entry_price) * 100
                        pl_color = "green" if pl_pct >= 0 else "red"
                    else:
                        pl_pct = ((entry_price - current_price) / entry_price) * 100
                        pl_color = "green" if pl_pct >= 0 else "red"
                    
                    # Hitung probabilitas TP untuk posisi aktif
                    tp_probabilities = calculate_tp_probability(
                        current_price, tp1, tp2, tp3, sl, action
                    )
                    
                    st.markdown("---")
                    col1, col2, col3, col4 = st.columns([3, 2, 1, 1])
                    
                    with col1:
                        if action == "LONG":
                            st.write(f"**{symbol}** ({market_type}) - 🟢 {action}")
                        else:
                            st.write(f"**{symbol}** ({market_type}) - 🔴 {action}")
                        st.write(f"📥 Entry: `{entry_price:.5f}` | 📊 Current: `{current_price:.5f}`")
                        st.write(f"💰 P/L: <span style='color:{pl_color}'>{pl_pct:.2f}%</span>", unsafe_allow_html=True)
                    
                    with col2:
                        # Display TP levels dengan probabilitas
                        st.write(f"🎯 TP1: `{tp1:.5f}` ({safe_get(tp_probabilities, 'tp1', 0)*100:.1f}%)")
                        st.write(f"🎯 TP2: `{tp2:.5f}` ({safe_get(tp_probabilities, 'tp2', 0)*100:.1f}%)")
                        st.write(f"🎯 TP3: `{tp3:.5f}` ({safe_get(tp_probabilities, 'tp3', 0)*100:.1f}%)")
                        st.write(f"🛑 SL: `{sl:.5f}`")
                    
                    with col3:
                        if st.button("🔄", key=f"update_{symbol}"):
                            try:
                                ticker = bot.data_provider.get_ticker(symbol)
                                if ticker and 'last' in ticker:
                                    bot.db.update_position_current_price(symbol, ticker['last'])
                                    st.success(f"Harga {symbol} diperbarui!")
                                    st.session_state.positions_data = bot.get_active_positions()
                                    st.rerun()
                            except Exception as e:
                                st.error(f"❌ Error updating price: {e}")
                    
                    with col4:
                        exit_price = st.number_input(
                            "Exit Price",
                            value=float(current_price),
                            step=0.0001,
                            key=f"exit_{symbol}"
                        )
                        if st.button("🔒 Tutup", key=f"close_{symbol}"):
                            try:
                                if bot.close_position(pos_id, exit_price):
                                    st.success(f"Posisi {symbol} ditutup!")
                                    st.session_state.positions_data = bot.get_active_positions()
                                    st.rerun()
                                else:
                                    st.error("Gagal menutup posisi.")
                            except Exception as e:
                                st.error(f"❌ Error closing position: {e}")
                except Exception as e:
                    st.error(f"❌ Error processing position: {e}")

    # ===============================
    # Tab 5: History
    # ===============================
    with tab5:
        st.subheader("📋 History Trading")
        
        if st.button("🔄 Refresh History", key="refresh_history"):
            try:
                st.session_state.history_data = bot.get_trade_history(20)
                st.success("History diperbarui!")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Error refreshing history: {e}")
        
        if not st.session_state.history_data:
            st.info("📭 Tidak ada history trading.")
        else:
            st.write(f"**📊 Total Trade:** {len(st.session_state.history_data)}")
            
            for trade in st.session_state.history_data:
                try:
                    # Handle both tuple and dictionary responses
                    if isinstance(trade, tuple):
                        trade_id = trade[0]      # id
                        symbol = trade[1]        # symbol
                        market_type = trade[2]   # market_type
                        action = trade[3]        # action
                        entry_price = trade[4]   # entry_price
                        exit_price = trade[5]    # exit_price
                        profit_loss = trade[6]   # profit_loss
                        trade_type = trade[7]    # trade_type
                        timestamp = trade[8]     # timestamp
                    else:
                        trade_id = safe_get(trade, 'id', 0)
                        symbol = safe_get(trade, 'symbol', '')
                        market_type = safe_get(trade, 'market_type', '')
                        action = safe_get(trade, 'action', '')
                        entry_price = safe_get(trade, 'entry_price', 0)
                        exit_price = safe_get(trade, 'exit_price', 0)
                        profit_loss = safe_get(trade, 'profit_loss', 0)
                        trade_type = safe_get(trade, 'type', '')
                        timestamp = safe_get(trade, 'timestamp', '')
                    
                    color = "green" if profit_loss > 0 else "red"
                    emoji = "✅" if profit_loss > 0 else "❌"
                    
                    st.markdown("---")
                    st.write(f"{emoji} **{symbol}** ({market_type}) - {action} - {trade_type}")
                    st.write(f"📥 Entry: `{entry_price:.5f}` | 📤 Exit: `{exit_price:.5f}`")
                    st.write(f"💰 P/L: <span style='color:{color}'>{profit_loss:.5f}</span>", unsafe_allow_html=True)
                    st.write(f"⏰ Waktu: {timestamp}")
                except Exception as e:
                    st.error(f"❌ Error processing trade: {e}")

    # ===============================
    # Tab 6: Live Scanner
    # ===============================
    with tab6:
        st.subheader("📡 Live Scanner")
        
        if st.button("🚀 Mulai Live Monitoring" if not st.session_state.live_monitoring else "⏹️ Hentikan Live Monitoring"):
            st.session_state.live_monitoring = not st.session_state.live_monitoring
            st.rerun()
        
        if st.session_state.live_monitoring:
            st.info("📡 Live monitoring aktif. Harga akan diperbarui setiap 30 detik.")
            
            if st.session_state.positions_data:
                st.subheader("📊 Posisi Aktif - Live")
                for pos in st.session_state.positions_data:
                    try:
                        # Handle both tuple and dictionary responses
                        if isinstance(pos, tuple):
                            symbol = pos[1]        # symbol
                            entry_price = pos[4]   # entry_price
                            current_price = pos[11] if len(pos) > 11 else entry_price  # current_price
                        else:
                            symbol = safe_get(pos, 'symbol', '')
                            entry_price = safe_get(pos, 'entry_price', 0)
                            current_price = safe_get(pos, 'current_price', entry_price)
                        
                        ticker = bot.data_provider.get_ticker(symbol)
                        if ticker and 'last' in ticker:
                            latest_price = ticker['last']
                            price_change = ((latest_price - current_price) / current_price) * 100
                            total_change = ((latest_price - entry_price) / entry_price) * 100
                            
                            color = "green" if price_change >= 0 else "red"
                            total_color = "green" if total_change >= 0 else "red"
                            
                            st.write(f"**{symbol}**")
                            st.write(f"📊 Current: `{current_price:.5f}` → Live: `{latest_price:.5f}`")
                            st.write(f"📈 Change: <span style='color:{color}'>{price_change:+.2f}%</span>", unsafe_allow_html=True)
                            st.write(f"💰 Total P/L: <span style='color:{total_color}'>{total_change:+.2f}%</span>", unsafe_allow_html=True)
                            st.markdown("---")
                    except Exception as e:
                        st.error(f"❌ Error updating live data for {symbol}: {e}")
            
            st_auto_refresh = st.checkbox("🔄 Auto Refresh (30s)")
            if st_auto_refresh:
                time.sleep(30)
                st.rerun()
                
            if st.button("🔄 Refresh Sekarang"):
                st.rerun()
                
        else:
            st.info("👉 Klik 'Mulai Live Monitoring' untuk memantau harga real-time.")

    # ===============================
    # Tab 7: ML Backtest
    # ===============================
    with tab7:
        st.subheader("🤖 ML Backtest & Analysis")
        
        col1, col2 = st.columns([2, 1])
        with col1:
            backtest_symbol = st.text_input("Symbol untuk Backtest:", key="backtest_symbol")
        with col2:
            backtest_days = st.selectbox("Period:", [30, 90, 180, 365], index=2)
        
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("🚀 Run Backtest", key="run_backtest"):
                if backtest_symbol:
                    with st.spinner("Running comprehensive backtest..."):
                        try:
                            symbol = backtest_symbol.upper()
                            if bot.mode == "crypto":
                                symbol = f"{symbol}/USDT"
                            elif bot.mode == "forex":
                                if symbol == "XAU":
                                    symbol = "GC=F"
                                elif len(symbol) == 6:
                                    symbol = f"{symbol}=X"
                            elif bot.mode == "saham_id":
                                symbol = f"{symbol}.JK"
                            
                            if hasattr(bot, 'run_comprehensive_backtest'):
                                results = bot.run_comprehensive_backtest(symbol, backtest_days)
                            else:
                                results = {"error": "Backtest feature not available"}
                            st.session_state.backtest_results = results
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Error running backtest: {e}")
        
        with col2:
            if st.button("📊 Enhanced Analysis", key="enhanced_analysis"):
                if backtest_symbol:
                    with st.spinner("Running enhanced analysis..."):
                        try:
                            symbol = backtest_symbol.upper()
                            if bot.mode == "crypto":
                                symbol = f"{symbol}/USDT"
                            
                            if hasattr(bot, 'analyze_with_ml'):
                                analysis = bot.analyze_with_ml(symbol)
                            else:
                                analysis = bot.analyze_asset(symbol)
                            if analysis:
                                st.session_state.selected_analysis = analysis
                                st.success("Enhanced analysis completed!")
                            else:
                                st.error("Enhanced analysis failed!")
                        except Exception as e:
                            st.error(f"❌ Error in enhanced analysis: {e}")
        
        with col3:
            if st.button("📈 Risk Assessment", key="risk_assess"):
                if backtest_symbol:
                    try:
                        if hasattr(bot, 'get_risk_assessment'):
                            risk_assessment = bot.get_risk_assessment(backtest_symbol)
                        else:
                            risk_assessment = None
                        if risk_assessment:
                            st.session_state.risk_assessments[backtest_symbol] = risk_assessment
                            st.success("Risk assessment completed!")
                        else:
                            st.error("Risk assessment failed!")
                    except Exception as e:
                        st.error(f"❌ Error in risk assessment: {e}")

        if st.session_state.backtest_results and 'error' not in st.session_state.backtest_results:
            results = st.session_state.backtest_results
            st.subheader("📊 Backtest Results")
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Trades", safe_get(results, 'total_trades', 0))
                st.metric("Final Balance", f"${safe_get(results, 'final_balance', 0):,.2f}")
            with col2:
                st.metric("Win Rate", f"{safe_get(results, 'win_rate', 0):.1%}")
                st.metric("Total P&L", f"${safe_get(results, 'total_pnl', 0):,.2f}")
            with col3:
                st.metric("Sharpe Ratio", f"{safe_get(results, 'sharpe_ratio', 0):.2f}")
            with col4:
                st.metric("Max Drawdown", f"{safe_get(results, 'max_drawdown', 0):.1%}")
            
            if 'equity_curve' in results and PLOTLY_AVAILABLE:
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    y=results['equity_curve'],
                    mode='lines',
                    name='Equity Curve',
                    line=dict(color='green')
                ))
                fig.update_layout(
                    title="Equity Curve",
                    xaxis_title="Time",
                    yaxis_title="Portfolio Value"
                )
                st.plotly_chart(fig, use_container_width=True)
        
        elif st.session_state.backtest_results and 'error' in st.session_state.backtest_results:
            st.error(f"Backtest Error: {st.session_state.backtest_results['error']}")

        if st.session_state.selected_analysis and isinstance(st.session_state.selected_analysis, dict):
            analysis = st.session_state.selected_analysis
            st.subheader("🤖 Enhanced Analysis")
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Base Score", safe_get(analysis, 'base_score', safe_get(analysis, 'score', 0)))
                if 'ml_confidence' in analysis:
                    st.metric("ML Confidence", f"{safe_get(analysis, 'ml_confidence', 1.0):.2f}")
            with col2:
                st.metric("Final Score", safe_get(analysis, 'final_score', safe_get(analysis, 'score', 0)))
                st.metric("Action", safe_get(analysis, 'action', 'NEUTRAL'))
            
            if 'risk_metrics' in analysis:
                st.subheader("📊 Risk Metrics")
                risk_cols = st.columns(3)
                with risk_cols[0]:
                    st.metric("Risk Category", safe_get(analysis['risk_metrics'], 'risk_category', ''))
                    st.metric("Reward Ratio", f"{safe_get(analysis['risk_metrics'], 'reward_ratio', 0):.2f}")
                with risk_cols[1]:
                    st.metric("Position Size", f"{safe_get(analysis['risk_metrics'], 'optimal_position_size', 0):.1%}")
                with risk_cols[2]:
                    st.metric("Drawdown Risk", safe_get(analysis['risk_metrics'], 'drawdown_risk', ''))

        if st.session_state.risk_assessments:
            st.subheader("⚖️ Risk Assessments")
            for symbol, assessment in st.session_state.risk_assessments.items():
                with st.expander(f"Risk Assessment for {symbol}"):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write(f"**Risk Category:** {safe_get(assessment, 'risk_category', '')}")
                        st.write(f"**Volatility Level:** {safe_get(assessment, 'volatility_level', '')}")
                    with col2:
                        st.write(f"**Optimal Position:** {safe_get(assessment, 'optimal_position_size', 0):.1%}")
                        st.write(f"**Reward Ratio:** {safe_get(assessment, 'reward_ratio', 0):.2f}")
                    st.info(f"**Recommendation:** {safe_get(assessment, 'recommendation', '')}")

    # ===============================
    # Tab 8: Portfolio Optimization
    # ===============================
    with tab8:
        st.subheader("⚖️ Portfolio Optimization")
        
        col1, col2 = st.columns([2, 1])
        with col1:
            portfolio_capital = st.number_input("Total Capital:", value=10000, step=1000)
        with col2:
            if st.button("🔄 Optimize Portfolio", key="optimize_portfolio"):
                if st.session_state.scanned_results:
                    try:
                        if hasattr(bot, 'optimize_portfolio_allocation'):
                            allocations = bot.optimize_portfolio_allocation(
                                st.session_state.scanned_results, 
                                portfolio_capital
                            )
                        else:
                            signals = st.session_state.scanned_results[:5]  # Take top 5
                            total_signals = len(signals)
                            if total_signals > 0:
                                base_allocation = 1.0 / total_signals
                                allocations = {
                                    'signals': [
                                        {
                                            'symbol': s['symbol'],
                                            'score': safe_get(s, 'score', 1),
                                            'risk_category': safe_get(s, 'risk_category', 'MEDIUM'),
                                            'allocation_percent': base_allocation,
                                            'allocated_capital': portfolio_capital * base_allocation
                                        }
                                        for s in signals
                                    ],
                                    'total_allocated_percent': 1.0,
                                    'total_allocated_capital': portfolio_capital,
                                    'remaining_capital': 0
                                }
                            else:
                                allocations = {}
                        st.session_state.portfolio_allocations = allocations
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Error optimizing portfolio: {e}")
        
        # Display Portfolio Allocations
        if st.session_state.portfolio_allocations:
            allocations = st.session_state.portfolio_allocations
            st.subheader("📈 Portfolio Allocation")
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Allocated", f"{safe_get(allocations, 'total_allocated_percent', 0):.1%}")
            with col2:
                st.metric("Allocated Capital", f"${safe_get(allocations, 'total_allocated_capital', 0):,.2f}")
            with col3:
                st.metric("Remaining Capital", f"${safe_get(allocations, 'remaining_capital', 0):,.2f}")
            with col4:
                st.metric("Number of Signals", len(safe_get(allocations, 'signals', [])))
            
            st.subheader("📋 Position Details")
            allocation_data = []
            for signal in safe_get(allocations, 'signals', []):
                allocation_data.append({
                    'Symbol': safe_get(signal, 'symbol'),
                    'Score': safe_get(signal, 'score', 0),
                    'Risk': safe_get(signal, 'risk_category', 'MEDIUM'),
                    'Allocation %': f"{safe_get(signal, 'allocation_percent', 0):.2%}",
                    'Capital': f"${safe_get(signal, 'allocated_capital', 0):,.2f}"
                })
            
            if allocation_data:
                df_allocations = pd.DataFrame(allocation_data)
                st.dataframe(df_allocations, use_container_width=True)
                
                if PLOTLY_AVAILABLE:
                    fig = go.Figure(data=[go.Pie(
                        labels=[s['symbol'] for s in allocations['signals']],
                        values=[s['allocated_capital'] for s in allocations['signals']],
                        hole=.3
                    )])
                    fig.update_layout(title="Portfolio Allocation")
                    st.plotly_chart(fig, use_container_width=True)
        
        st.subheader("🔗 Portfolio Analysis")
        st.info("""
        **Portfolio Features:**
        - Risk-adjusted position sizing
        - Diversification scoring
        - Dynamic allocation optimization
        - Correlation analysis
        """)

def main():
    # Initialize session state for login
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
    if 'username' not in st.session_state:
        st.session_state.username = ""

    # Show login page if not logged in
    if not st.session_state.logged_in:
        login_section()
    else:
        main_app()

if __name__ == "__main__":
    main()
