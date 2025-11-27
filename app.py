import time
import asyncio
import threading
import schedule
import streamlit as st
import pandas as pd
from dotenv import load_dotenv
import random
import sys
import os

# ✅ FIX: Add the project root to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Try to import plotly
try:
    import plotly.graph_objects as go
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False

# Import TradingBot
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
    """Simple login system"""
    users = {"muraga": "namikaze", "user2": "password2", "user3": "password3", "admin": "admin123"}
    return users.get(username) == password

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

@st.cache_resource
def init_bot():
    """Initialize TradingBot"""
    try:
        bot = TradingBot()
        st.success("✅ TradingBot initialized successfully")
        return bot
    except Exception as e:
        st.error(f"❌ Failed to initialize TradingBot: {e}")
        return None

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
    """Validate and fix price levels in analysis data - FIXED VERSION"""
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
    
    # ✅ PERBAIKAN BESAR: Hitung Entry Range yang REALISTIS
    if (analysis.get('entry_range_low', 0) <= 0 or 
        analysis.get('entry_range_high', 0) <= 0 or 
        analysis.get('best_entry', 0) <= 0 or
        analysis.get('entry_range_low') == analysis.get('entry_range_high')):  # Tambahan validasi
        
        # Gunakan ATR atau volatilitas untuk menentukan range yang realistis
        atr = analysis.get('atr', 0)
        volatility = analysis.get('volatility', 0.02)  # Default 2%
        
        # Jika ATR tersedia, gunakan untuk menghitung range
        if atr > 0:
            range_size = atr * 0.5  # Gunakan 0.5 ATR untuk entry range
        else:
            # Fallback: gunakan persentase berdasarkan volatilitas
            range_size = current_price * volatility * 0.5
        
        # Pastikan range_size minimal 0.1% dari current price
        min_range = current_price * 0.001
        range_size = max(range_size, min_range)
        
        if action == "LONG":
            # Untuk LONG: entry range DI BAWAH current price
            analysis['entry_range_low'] = current_price - (range_size * 1.5)
            analysis['entry_range_high'] = current_price - (range_size * 0.5)
            analysis['best_entry'] = current_price - range_size
        elif action == "SHORT":
            # Untuk SHORT: entry range DI ATAS current price  
            analysis['entry_range_low'] = current_price + (range_size * 0.5)
            analysis['entry_range_high'] = current_price + (range_size * 1.5)
            analysis['best_entry'] = current_price + range_size
        else:
            # NEUTRAL: range di sekitar current price
            analysis['entry_range_low'] = current_price - range_size
            analysis['entry_range_high'] = current_price + range_size
            analysis['best_entry'] = current_price
        
        # Hitung range size dalam persentase
        analysis['range_size'] = ((analysis['entry_range_high'] - analysis['entry_range_low']) / current_price) * 100
    
    # Validasi TP/SL (kode sebelumnya tetap)
    tp1 = analysis.get('tp1', 0)
    tp2 = analysis.get('tp2', 0) 
    tp3 = analysis.get('tp3', 0)
    sl = analysis.get('sl', 0)
    
    if (tp1 <= 0 or tp2 <= 0 or tp3 <= 0 or sl <= 0 or 
        tp1 == tp2 == tp3 == sl == current_price):
        
        if action == "LONG":
            analysis['tp1'] = current_price * 1.03
            analysis['tp2'] = current_price * 1.06
            analysis['tp3'] = current_price * 1.09
            analysis['sl'] = current_price * 0.97
        else:
            analysis['tp1'] = current_price * 0.97
            analysis['tp2'] = current_price * 0.94
            analysis['tp3'] = current_price * 0.91
            analysis['sl'] = current_price * 1.03
    
    return analysis

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

def plot_entry_range(analysis):
    """Plot visual entry range"""
    if not PLOTLY_AVAILABLE:
        return None
        
    fig = go.Figure()
    
    current_price = analysis.get('current_price', 0)
    entry_low = analysis.get('entry_range_low', 0)
    entry_high = analysis.get('entry_range_high', 0)
    best_entry = analysis.get('best_entry', 0)
    
    # Jika data tidak valid, return fig kosong
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
# Main App - FULLY FIXED VERSION
# ====================================
def main_app():
    st.title("🚀 TradingBot Pro - Enhanced Dashboard")
    
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
    bot = init_bot()
    if not bot:
        st.error("❌ Failed to initialize TradingBot")
        return

    # Initialize session state dengan approach yang lebih clean
    if 'app_initialized' not in st.session_state:
        st.session_state.app_initialized = True
        st.session_state.positions_data = []
        st.session_state.history_data = []
        st.session_state.scanned_results = []
        st.session_state.selected_analysis = None
        st.session_state.selected_for_entry = {}
        st.session_state.current_market = None
        st.session_state.market_set = False
        # State-state tambahan dari app (1).py
        st.session_state.live_monitoring = False
        st.session_state.custom_result = None
        st.session_state.backtest_results = {}
        st.session_state.portfolio_allocations = {}
        st.session_state.risk_assessments = {}
        st.session_state.latest_results = []  # untuk auto rescan

    # Sidebar - ENHANCED
    with st.sidebar:
        st.header("🎯 Market Selection")
        
        # Gunakan key yang unique untuk setiap session
        market_choice = st.selectbox(
            "Select Market:",
            ["Crypto", "Forex", "Saham Indonesia", "US Stocks"],
            key="market_select"
        )
        
        # Trading mode selection
        trading_mode = st.radio(
            "Trading Mode:",
            ["Spot", "Futures"],
            key="mode_select"
        )

        # Show warning for markets that don't support short trading
        if market_choice in ["Forex", "Saham Indonesia", "US Stocks"]:
            st.warning("⚠️ **SHORT TRADING NOT AVAILABLE** - Only LONG signals will be generated")

        # Set Market Button - FIXED APPROACH
        if st.button("🎯 Set Market", key="set_market_btn"):
            try:
                # Validasi Futures hanya untuk Crypto
                if market_choice != "Crypto" and trading_mode == "Futures":
                    st.error("❌ Futures mode hanya tersedia untuk Crypto")
                else:
                    # Set market mode
                    if market_choice == "Crypto":
                        success = bot.set_mode("crypto")
                    elif market_choice == "Forex":
                        success = bot.set_mode("forex")
                    elif market_choice == "Saham Indonesia":
                        success = bot.set_mode("saham_id")
                    elif market_choice == "US Stocks":
                        success = bot.set_mode("us_stocks")
                    
                    if success:
                        st.session_state.current_market = market_choice
                        st.session_state.market_set = True
                        st.session_state.scanned_results = []
                        st.session_state.selected_for_entry = {}
                        st.success(f"✅ Market set to: {market_choice} ({trading_mode})")
                        st.rerun()
                    else:
                        st.error("❌ Failed to set market")
            except Exception as e:
                st.error(f"❌ Error: {e}")

        # Tampilkan status
        if st.session_state.market_set:
            st.success(f"✅ Active: {st.session_state.current_market}")
        
        # Refresh data - 🔥 PERBAIKAN: Refresh yang benar-benar bekerja
        if st.button("🔄 Refresh All Data", key="refresh_data"):
            try:
                # Clear cache untuk memaksa refresh
                if 'positions_data' in st.session_state:
                    del st.session_state.positions_data
                if 'history_data' in st.session_state:
                    del st.session_state.history_data
                    
                st.session_state.positions_data = bot.get_active_positions()
                st.session_state.history_data = bot.get_trade_history()
                st.success("✅ All data refreshed successfully!")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Refresh error: {e}")

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
        - Short trading only available for Crypto
        """)
        return

    # Main Tabs - ENHANCED: 8 tabs seperti di app (1).py
    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
        "📊 Scan Assets", "🔍 Analyze", "🎯 Custom Entry", "💼 Positions", 
        "📈 History", "📡 Live Scanner", "🤖 ML Backtest", "⚖️ Portfolio"
    ])

    # Tab 1: Scan Assets - ENHANCED dengan Entry Range
    with tab1:
        st.subheader("Scan Potential Assets")
        
        if st.session_state.current_market == "Crypto":
            scan_type = st.radio("Scan Type:", ["Standard", "Pump Fun"], key="scan_type")
        else:
            scan_type = "Standard"
        
        if st.button("🚀 Start Scan", key="start_scan"):
            with st.spinner("Scanning assets..."):
                try:
                    if scan_type == "Pump Fun" and st.session_state.current_market == "Crypto":
                        results = asyncio.run(bot.scan_pump_fun())
                        if results:
                            st.subheader("New Pump Fun Tokens:")
                            for res in results[:5]:  # Limit to 5 results
                                st.write(f"**{res['symbol']}** - Price: {res['ticker']['last']}")
                    else:
                        results = bot.scan_potential_assets(20)  # Scan fewer assets for performance
                        if results:
                            # Process and validate results
                            for i, result in enumerate(results[:10]):
                                symbol = safe_get(result, 'symbol')
                                results[i] = validate_and_fix_price_levels(result, symbol, bot)
                            
                            st.session_state.scanned_results = results[:10]
                            st.success(f"✅ Found {len(results)} potential assets")
                        else:
                            st.warning("No results found. Trying fallback...")
                            # Fallback logic here
                except Exception as e:
                    st.error(f"Scan error: {e}")

        # Display scanned results - ENHANCED dengan probabilitas TP dan ENTRY RANGE
        if st.session_state.scanned_results:
            st.subheader("Top Assets:")
            for i, res in enumerate(st.session_state.scanned_results, 1):
                if isinstance(res, dict) and 'symbol' in res:
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        action = safe_get(res, 'action', 'NEUTRAL')
                        action_color = "🟢" if action == "LONG" else "🔴" if action == "SHORT" else "⚪"
                        st.write(f"{i}. {action_color} **{safe_get(res, 'symbol')}** - {action} (Score: {safe_get(res, 'score', 0)})")
                        
                        current_price = get_valid_price(res, safe_get(res, 'symbol'), bot)
                        st.write(f"💰 Current Price: `{current_price:.5f}`")
                        
                        # ✅ TAMPILKAN ENTRY RANGE DAN IDEAL ENTRY
                        st.write(f"📊 **Entry Range:** `{res.get('entry_range_low', 0):.5f} - {res.get('entry_range_high', 0):.5f}`")
                        st.write(f"🎯 **Ideal Entry:** `{res.get('best_entry', 0):.5f}`")
                        st.write(f"📏 **Range Size:** `{res.get('range_size', 0):.1f}%`")
                        
                        # Display TP levels
                        tp1, tp2, tp3 = safe_get(res, 'tp1', 0), safe_get(res, 'tp2', 0), safe_get(res, 'tp3', 0)
                        sl = safe_get(res, 'sl', 0)
                        
                        if action == "LONG":
                            tp1, tp2, tp3 = sorted([tp1, tp2, tp3])
                        else:
                            tp1, tp2, tp3 = sorted([tp1, tp2, tp3], reverse=True)
                        
                        st.write(f"🎯 **TP Levels:** `{tp1:.5f}` | `{tp2:.5f}` | `{tp3:.5f}`")
                        st.write(f"🛑 **Stop Loss:** `{sl:.5f}`")
                        
                        # Hitung dan tampilkan probabilitas TP jika belum ada
                        if 'tp_probabilities' not in res:
                            res['tp_probabilities'] = calculate_tp_probability(
                                current_price, tp1, tp2, tp3, sl, action
                            )
                        
                        probs = res['tp_probabilities']
                        st.write(f"📊 **Probabilities:** TP1: {probs.get('tp1', 0)*100:.1f}% | TP2: {probs.get('tp2', 0)*100:.1f}% | TP3: {probs.get('tp3', 0)*100:.1f}%")
                    
                    with col2:
                        if st.button(f"Select", key=f"select_{i}"):
                            symbol = safe_get(res, 'symbol')
                            st.session_state.selected_for_entry[symbol] = res
                            st.success(f"Selected {symbol}!")
                            st.rerun()

            # Entry section for selected assets
            for symbol, analysis in list(st.session_state.selected_for_entry.items()):
                st.markdown("---")
                st.subheader(f"Entry for {symbol}")
                
                analysis = validate_and_fix_price_levels(analysis, symbol, bot)
                current_price = get_valid_price(analysis, symbol, bot)
                
                entry_price = st.number_input(
                    "Entry Price",
                    value=float(current_price),
                    min_value=0.0001,
                    format="%.5f",
                    key=f"entry_{symbol}"
                )
                
                if st.button(f"✅ Add Position", key=f"add_{symbol}"):
                    try:
                        # Save position logic here
                        position_id = bot.db.save_position(
                            symbol=symbol,
                            market_type=bot.mode,
                            action=safe_get(analysis, "action"),
                            entry_price=entry_price,
                            tp1=safe_get(analysis, "tp1", 0),
                            tp2=safe_get(analysis, "tp2", 0),
                            tp3=safe_get(analysis, "tp3", 0),
                            sl=safe_get(analysis, "sl", 0),
                        )
                        
                        if position_id:
                            st.success(f"✅ Position added! (ID: {position_id})")
                            st.session_state.positions_data = bot.get_active_positions()
                            del st.session_state.selected_for_entry[symbol]
                            st.rerun()
                        else:
                            st.error("Failed to add position")
                    except Exception as e:
                        st.error(f"Error: {e}")

            # Auto Rescan Section - DARI APP (1).PY
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
                            st.write(f"**{res['symbol']}** - {res['action']} (Score: {res['score']})")
                            if 'detected_patterns' in res and res['detected_patterns']:
                                st.write(f"📊 Pola: {', '.join(res['detected_patterns'])}")

    # Tab 2: Analyze Asset - ENHANCED dengan Entry Range
    with tab2:
        st.subheader("Analyze Specific Asset")
        
        symbol_input = st.text_input("Enter symbol:", key="analyze_symbol")
        
        if st.button("Analyze", key="analyze_btn"):
            if symbol_input:
                with st.spinner("Analyzing..."):
                    try:
                        symbol = symbol_input.upper()
                        if st.session_state.current_market == "Crypto":
                            symbol = f"{symbol}/USDT"
                        
                        analysis = bot.analyze_asset(symbol)
                        if analysis:
                            analysis = validate_and_fix_price_levels(analysis, symbol, bot)
                            
                            # Hitung probabilitas TP
                            tp1, tp2, tp3 = safe_get(analysis, 'tp1', 0), safe_get(analysis, 'tp2', 0), safe_get(analysis, 'tp3', 0)
                            action = safe_get(analysis, 'action', 'LONG')
                            current_price = get_valid_price(analysis, symbol, bot)
                            
                            if action == "LONG":
                                tp1, tp2, tp3 = sorted([tp1, tp2, tp3])
                            else:
                                tp1, tp2, tp3 = sorted([tp1, tp2, tp3], reverse=True)
                            
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
            st.subheader(f"Analysis: {safe_get(analysis, 'symbol')}")
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Action", safe_get(analysis, 'action', 'NEUTRAL'))
                st.metric("Score", safe_get(analysis, 'score', 0))
                st.metric("Current Price", f"{get_valid_price(analysis, safe_get(analysis, 'symbol'), bot):.5f}")
                st.metric("Trend", safe_get(analysis, 'trend', 'NEUTRAL'))
            
            with col2:
                st.metric("RSI", f"{safe_get(analysis, 'rsi', 0):.1f}")
                st.metric("Volume Ratio", f"{safe_get(analysis, 'volume_ratio', 0):.2f}")
                st.metric("ATR", f"{safe_get(analysis, 'atr', 0):.5f}")
                
                # Tampilkan probabilitas TP
                if 'tp_probabilities' in analysis:
                    probs = analysis['tp_probabilities']
                    st.metric("TP1 Probability", f"{probs.get('tp1', 0)*100:.1f}%")
            
            # ✅ TAMBAHAN: ENTRY RANGE DETAILS
            st.subheader("🎯 Entry Range Details")
            col_range1, col_range2, col_range3 = st.columns(3)
            with col_range1:
                st.metric("Entry Range Low", f"{analysis.get('entry_range_low', 0):.5f}")
            with col_range2:
                st.metric("Entry Range High", f"{analysis.get('entry_range_high', 0):.5f}")
            with col_range3:
                st.metric("Ideal Entry", f"{analysis.get('best_entry', 0):.5f}")
            
            st.metric("Range Size", f"{analysis.get('range_size', 0):.1f}%")
            
            # Plot entry range jika available
            if PLOTLY_AVAILABLE:
                fig_range = plot_entry_range(analysis)
                if fig_range:
                    st.plotly_chart(fig_range, use_container_width=True)

    # Tab 3: Custom Entry - DARI APP (1).PY dengan Entry Range
    with tab3:
        st.subheader("🎯 Custom Entry")
        
        symbol_custom = st.text_input("Masukkan simbol aset:", key="custom_symbol")
        entry_price_custom = st.number_input("Harga Entry:", value=0.0, step=0.0001, key="custom_entry")
        action_custom = st.selectbox("Action:", ["LONG", "SHORT"], key="custom_action")
        
        if st.button("🧮 Hitung TP/SL", key="calculate_custom"):
            if symbol_custom and entry_price_custom > 0:
                with st.spinner("Menghitung..."):
                    result = bot.calculate_custom_entry(symbol_custom, entry_price_custom, action_custom)
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
            else:
                st.warning("Masukkan simbol dan harga entry yang valid.")
        
        # Tampilkan hasil custom entry
        if st.session_state.custom_result:
            result = st.session_state.custom_result
            st.subheader(f"📊 Hasil untuk {result['symbol']}")
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric("💰 Entry Price", f"{result['entry_price']:.5f}")
                st.metric("🎯 TP1", f"{result['tp1']:.5f}")
                st.metric("🎯 TP2", f"{result['tp2']:.5f}")
            
            with col2:
                st.metric("🎯 TP3", f"{result['tp3']:.5f}")
                st.metric("🛡️ SL", f"{result['sl']:.5f}")
                
                # Hitung risk/reward ratio
                if action_custom == "LONG":
                    risk_reward = (result['tp1'] - result['entry_price']) / (result['entry_price'] - result['sl'])
                else:
                    risk_reward = (result['entry_price'] - result['tp1']) / (result['sl'] - result['entry_price'])
                st.metric("📊 Risk/Reward", f"{risk_reward:.2f}")
            
            # ✅ TAMBAHAN: ENTRY RANGE DETAILS
            st.subheader("🎯 Entry Range Details")
            col_range1, col_range2, col_range3 = st.columns(3)
            with col_range1:
                st.metric("Entry Range Low", f"{result.get('entry_range_low', 0):.5f}")
            with col_range2:
                st.metric("Entry Range High", f"{result.get('entry_range_high', 0):.5f}")
            with col_range3:
                st.metric("Best Entry", f"{result.get('best_entry', 0):.5f}")
            
            st.metric("Range Size", f"{result.get('range_size', 0):.1f}%")
            
            # Tampilkan probabilitas TP
            if 'tp_probabilities' in result:
                st.subheader("📊 Probabilitas TP")
                probs = result['tp_probabilities']
                col_prob1, col_prob2, col_prob3 = st.columns(3)
                with col_prob1:
                    st.metric("TP1 Probability", f"{probs.get('tp1', 0)*100:.1f}%")
                with col_prob2:
                    st.metric("TP2 Probability", f"{probs.get('tp2', 0)*100:.1f}%")
                with col_prob3:
                    st.metric("TP3 Probability", f"{probs.get('tp3', 0)*100:.1f}%")
            
            # Plot entry range jika available
            if PLOTLY_AVAILABLE:
                fig_range = plot_entry_range(result)
                if fig_range:
                    st.plotly_chart(fig_range, use_container_width=True)
            
            # Tombol untuk menambahkan ke posisi
            if st.button("✅ Tambahkan ke Posisi Aktif", key="add_custom"):
                # Urutkan TP levels berdasarkan action
                tp1, tp2, tp3 = result['tp1'], result['tp2'], result['tp3']
                if action_custom == "LONG":
                    tp1, tp2, tp3 = sorted([tp1, tp2, tp3])
                else:  # SHORT
                    tp1, tp2, tp3 = sorted([tp1, tp2, tp3], reverse=True)
                    
                position_id = bot.db.save_position(
                    symbol=result['symbol'],
                    market_type=bot.mode,
                    action=action_custom,
                    entry_price=result['entry_price'],
                    tp1=tp1,
                    tp2=tp2,
                    tp3=tp3,
                    sl=result['sl'],
                    entry_low=result.get('entry_range_low', result['entry_price'] * 0.99),
                    entry_high=result.get('entry_range_high', result['entry_price'] * 1.01),
                )
                if position_id:
                    st.success(f"Posisi {result['symbol']} ditambahkan!")
                    st.session_state.positions_data = bot.get_active_positions()
                    st.rerun()
                else:
                    st.error("Gagal tambah posisi.")

    # 🔥 TAB 4: POSITIONS - FULLY FIXED VERSION
    with tab4:
        st.subheader("💼 Active Positions")
        
        # 🔥 PERBAIKAN: Refresh yang benar-benar bekerja
        col_refresh, col_auto = st.columns([1, 3])
        with col_refresh:
            if st.button("🔄 Refresh Positions", key="refresh_positions", type="primary"):
                try:
                    # Clear cache untuk memaksa refresh
                    if 'positions_data' in st.session_state:
                        del st.session_state.positions_data
                    st.session_state.positions_data = bot.get_active_positions()
                    st.success("✅ Positions refreshed successfully!")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Refresh error: {e}")
        
        with col_auto:
            auto_refresh_positions = st.checkbox("🔄 Auto-refresh every 15 seconds", value=False, key="auto_refresh_pos")
        
        if not st.session_state.positions_data:
            st.info("📭 No active positions")
        else:
            # 🔥 PERBAIKAN: Update semua positions dengan harga REAL-TIME
            updated_positions = []
            
            for pos in st.session_state.positions_data:
                try:
                    # 🔥 PERBAIKAN: Ambil data dengan benar dan update harga terkini
                    if isinstance(pos, tuple):
                        position_id = pos[0]
                        symbol = pos[1]
                        action = pos[3]
                        entry_price = float(pos[4])
                        
                        # 🔥 PERBAIKAN: Ambil harga REAL-TIME, bukan dari database
                        try:
                            ticker = bot.data_provider.get_ticker(symbol)
                            if ticker and 'last' in ticker:
                                current_price = float(ticker['last'])
                            else:
                                current_price = entry_price
                        except Exception as ticker_error:
                            current_price = entry_price
                        
                        tp1 = float(pos[7]) if len(pos) > 7 and pos[7] else 0
                        tp2 = float(pos[8]) if len(pos) > 8 and pos[8] else 0
                        tp3 = float(pos[9]) if len(pos) > 9 and pos[9] else 0
                        sl = float(pos[10]) if len(pos) > 10 and pos[10] else 0
                        
                        # 🔥 PERBAIKAN: Validasi Entry Range yang REALISTIS
                        entry_low = float(pos[12]) if len(pos) > 12 and pos[12] else 0
                        entry_high = float(pos[13]) if len(pos) > 13 and pos[13] else 0
                        
                    else:
                        position_id = safe_get(pos, 'id')
                        symbol = safe_get(pos, 'symbol')
                        action = safe_get(pos, 'action')
                        entry_price = float(safe_get(pos, 'entry_price'))
                        
                        # 🔥 PERBAIKAN: Ambil harga REAL-TIME
                        try:
                            ticker = bot.data_provider.get_ticker(symbol)
                            if ticker and 'last' in ticker:
                                current_price = float(ticker['last'])
                            else:
                                current_price = entry_price
                        except Exception as ticker_error:
                            current_price = entry_price
                        
                        tp1 = float(safe_get(pos, 'tp1', 0))
                        tp2 = float(safe_get(pos, 'tp2', 0))
                        tp3 = float(safe_get(pos, 'tp3', 0))
                        sl = float(safe_get(pos, 'sl', 0))
                        
                        # Validasi Entry Range
                        entry_low = float(safe_get(pos, 'entry_low', 0))
                        entry_high = float(safe_get(pos, 'entry_high', 0))
                    
                    # 🔥 PERBAIKAN: Jika entry range tidak valid, hitung ulang
                    if entry_low <= 0 or entry_high <= 0 or entry_low == entry_high:
                        if action == "LONG":
                            entry_low = entry_price * 0.99
                            entry_high = entry_price * 0.995
                        else:  # SHORT
                            entry_low = entry_price * 1.005
                            entry_high = entry_price * 1.01
                    
                    best_entry = (entry_low + entry_high) / 2
                    
                    # 🔥 PERBAIKAN: Hitung P/L dengan harga TERKINI
                    if action == "LONG":
                        pl_pct = ((current_price - entry_price) / entry_price) * 100
                        pl_emoji = "📈" if pl_pct >= 0 else "📉"
                    else:
                        pl_pct = ((entry_price - current_price) / entry_price) * 100
                        pl_emoji = "📈" if pl_pct >= 0 else "📉"
                    
                    pl_color = "green" if pl_pct >= 0 else "red"
                    
                    # Hitung probabilitas TP dengan harga TERKINI
                    tp_probabilities = calculate_tp_probability(
                        current_price, tp1, tp2, tp3, sl, action
                    )
                    
                    # Tampilkan position card
                    with st.container():
                        col1, col2, col3 = st.columns([3, 2, 1])
                        
                        with col1:
                            st.write(f"**{symbol}** - {action} {pl_emoji}")
                            st.write(f"🏁 Entry: `{entry_price:.5f}`")
                            st.write(f"📊 Current: `{current_price:.5f}`")
                            st.write(f"💰 P/L: <span style='color:{pl_color}; font-weight:bold'>{pl_pct:+.2f}%</span>", unsafe_allow_html=True)
                            
                            # 🔥 PERBAIKAN: Tampilkan Entry Range yang VALID
                            st.write(f"🎯 **Entry Range:** `{entry_low:.5f} - {entry_high:.5f}`")
                            st.write(f"⭐ **Ideal Entry:** `{best_entry:.5f}`")
                        
                        with col2:
                            # Display TP levels dengan probabilitas
                            st.write(f"🎯 **TP1:** `{tp1:.5f}` ({tp_probabilities.get('tp1', 0)*100:.1f}%)")
                            st.write(f"🎯 **TP2:** `{tp2:.5f}` ({tp_probabilities.get('tp2', 0)*100:.1f}%)")
                            st.write(f"🎯 **TP3:** `{tp3:.5f}` ({tp_probabilities.get('tp3', 0)*100:.1f}%)")
                            st.write(f"🛑 **SL:** `{sl:.5f}`")
                        
                        with col3:
                            # 🔥 PERBAIKAN: Tombol Close yang BEKERJA
                            close_key = f"close_{position_id}_{symbol}"
                            if st.button("❌ Close", key=close_key, type="secondary"):
                                try:
                                    # Gunakan harga current untuk close
                                    success = bot.close_position(position_id, current_price)
                                    if success:
                                        st.success(f"✅ {symbol} position closed at {current_price:.5f}!")
                                        # Refresh data
                                        time.sleep(1)
                                        st.session_state.positions_data = bot.get_active_positions()
                                        st.rerun()
                                    else:
                                        st.error(f"❌ Failed to close {symbol}")
                                except Exception as close_error:
                                    st.error(f"❌ Close error: {close_error}")
                    
                    st.markdown("---")
                    
                    # Simpan posisi yang sudah di-update
                    updated_positions.append({
                        'id': position_id,
                        'symbol': symbol,
                        'action': action,
                        'entry_price': entry_price,
                        'current_price': current_price,
                        'tp1': tp1,
                        'tp2': tp2,
                        'tp3': tp3,
                        'sl': sl,
                        'entry_low': entry_low,
                        'entry_high': entry_high,
                        'best_entry': best_entry
                    })
                    
                except Exception as e:
                    st.error(f"❌ Position error for {safe_get(pos, 'symbol', 'unknown')}: {str(e)}")
            
            # 🔥 PERBAIKAN: Simpan posisi yang sudah di-update ke session state
            st.session_state.positions_data = updated_positions
            
            # Auto-refresh jika diaktifkan
            if auto_refresh_positions:
                time.sleep(15)
                st.rerun()

    # Tab 5: History - SAMA SEBELUMNYA
    with tab5:
        st.subheader("📈 Trade History")
        
        if st.button("🔄 Refresh History", key="refresh_history"):
            st.session_state.history_data = bot.get_trade_history()
            st.rerun()
        
        if not st.session_state.history_data:
            st.info("No trade history")
        else:
            for trade in st.session_state.history_data[:10]:  # Show last 10 trades
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
                    
                    color = "green" if profit_loss > 0 else "red"
                    emoji = "✅" if profit_loss > 0 else "❌"
                    
                    st.write(f"{emoji} **{symbol}** - {action}")
                    st.write(f"Entry: `{entry_price:.5f}` | Exit: `{exit_price:.5f}`")
                    st.write(f"P/L: <span style='color:{color}'>{profit_loss:.5f}</span>", unsafe_allow_html=True)
                    st.markdown("---")
                except Exception as e:
                    st.error(f"History error: {e}")

    # 🔥 TAB 6: LIVE SCANNER - FULLY FIXED VERSION
    with tab6:
        st.subheader("📡 Live Scanner")
        
        # 🔥 PERBAIKAN: State management yang lebih baik
        col1, col2 = st.columns([1, 3])
        with col1:
            if st.button("🚀 Mulai Live Monitoring" if not st.session_state.live_monitoring else "⏹️ Hentikan Live Monitoring", 
                        key="toggle_live", type="primary"):
                st.session_state.live_monitoring = not st.session_state.live_monitoring
                if st.session_state.live_monitoring:
                    st.success("📡 Live monitoring started!")
                else:
                    st.info("⏹️ Live monitoring stopped")
                st.rerun()
        
        with col2:
            auto_refresh_live = st.checkbox("🔄 Auto Refresh setiap 10 detik", value=True, key="auto_refresh_live")
        
        if st.session_state.live_monitoring:
            st.info("📡 Live monitoring aktif. Harga real-time akan ditampilkan.")
            
            # Refresh manual
            if st.button("🔄 Refresh Sekarang", key="manual_refresh_live"):
                st.rerun()
            
            if st.session_state.positions_data:
                st.subheader("📊 Posisi Aktif - Live Prices")
                
                # 🔥 PERBAIKAN: Update SEMUA posisi dengan harga real-time
                live_updated_positions = []
                
                for pos in st.session_state.positions_data:
                    try:
                        symbol = safe_get(pos, 'symbol')
                        if not symbol:
                            continue
                        
                        # Dapatkan harga real-time
                        ticker = bot.data_provider.get_ticker(symbol)
                        if ticker and 'last' in ticker:
                            latest_price = float(ticker['last'])
                            entry_price = float(safe_get(pos, 'entry_price'))
                            action = safe_get(pos, 'action')
                            
                            # Update posisi dengan harga terbaru
                            pos_dict = {
                                'id': safe_get(pos, 'id'),
                                'symbol': symbol,
                                'action': action,
                                'entry_price': entry_price,
                                'current_price': latest_price,
                                'tp1': float(safe_get(pos, 'tp1', 0)),
                                'tp2': float(safe_get(pos, 'tp2', 0)),
                                'tp3': float(safe_get(pos, 'tp3', 0)),
                                'sl': float(safe_get(pos, 'sl', 0))
                            }
                            
                            live_updated_positions.append(pos_dict)
                            
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
                                st.write(f"**{symbol}** - {action}")
                                st.write(f"🏁 Entry: `{entry_price:.5f}`")
                            with col_live2:
                                st.write(f"{emoji} Live: `{latest_price:.5f}`")
                                st.write(f"💰 Change: <span style='color:{color}; font-weight:bold'>{change_pct:+.2f}%</span>", unsafe_allow_html=True)
                            with col_live3:
                                if st.button("🔄", key=f"refresh_live_{symbol}"):
                                    st.rerun()
                            
                            st.markdown("---")
                        else:
                            st.warning(f"⚠️ Tidak dapat mengambil data live untuk {symbol}")
                            
                    except Exception as e:
                        st.error(f"❌ Error updating {symbol}: {str(e)}")
                
                # 🔥 PERBAIKAN: Update session state dengan data live
                st.session_state.positions_data = live_updated_positions
                
            else:
                st.info("📭 Tidak ada posisi aktif untuk di-monitor")
            
            # 🔥 PERBAIKAN: Auto-refresh menggunakan time.sleep
            if auto_refresh_live:
                with st.spinner("Memperbarui data..."):
                    time.sleep(10)  # Refresh setiap 10 detik
                st.rerun()
                
        else:
            st.info("👉 Klik 'Mulai Live Monitoring' untuk memantau harga real-time.")

    # Tab 7: ML Backtest - DARI APP (1).PY
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
        
        with col2:
            if st.button("📊 Enhanced Analysis", key="enhanced_analysis"):
                if backtest_symbol:
                    with st.spinner("Running enhanced analysis..."):
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
        
        with col3:
            if st.button("📈 Risk Assessment", key="risk_assess"):
                if backtest_symbol:
                    if hasattr(bot, 'get_risk_assessment'):
                        risk_assessment = bot.get_risk_assessment(backtest_symbol)
                    else:
                        risk_assessment = None
                    if risk_assessment:
                        st.session_state.risk_assessments[backtest_symbol] = risk_assessment
                        st.success("Risk assessment completed!")
                    else:
                        st.error("Risk assessment failed!")

        if st.session_state.backtest_results and 'error' not in st.session_state.backtest_results:
            results = st.session_state.backtest_results
            st.subheader("📊 Backtest Results")
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Trades", results.get('total_trades', 0))
                st.metric("Final Balance", f"${results.get('final_balance', 0):,.2f}")
            with col2:
                st.metric("Win Rate", f"{results.get('win_rate', 0):.1%}")
                st.metric("Total P&L", f"${results.get('total_pnl', 0):,.2f}")
            with col3:
                st.metric("Sharpe Ratio", f"{results.get('sharpe_ratio', 0):.2f}")
            with col4:
                st.metric("Max Drawdown", f"{results.get('max_drawdown', 0):.1%}")
            
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

    # Tab 8: Portfolio Optimization - DARI APP (1).PY
    with tab8:
        st.subheader("⚖️ Portfolio Optimization")
        
        col1, col2 = st.columns([2, 1])
        with col1:
            portfolio_capital = st.number_input("Total Capital:", value=10000, step=1000)
        with col2:
            if st.button("🔄 Optimize Portfolio", key="optimize_portfolio"):
                if st.session_state.scanned_results:
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
                                        'score': s.get('score', 1),
                                        'risk_category': s.get('risk_category', 'MEDIUM'),
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
        
        # Display Portfolio Allocations
        if st.session_state.portfolio_allocations:
            allocations = st.session_state.portfolio_allocations
            st.subheader("📈 Portfolio Allocation")
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Allocated", f"{allocations.get('total_allocated_percent', 0):.1%}")
            with col2:
                st.metric("Allocated Capital", f"${allocations.get('total_allocated_capital', 0):,.2f}")
            with col3:
                st.metric("Remaining Capital", f"${allocations.get('remaining_capital', 0):,.2f}")
            with col4:
                st.metric("Number of Signals", len(allocations.get('signals', [])))
            
            st.subheader("📋 Position Details")
            allocation_data = []
            for signal in allocations.get('signals', []):
                allocation_data.append({
                    'Symbol': signal['symbol'],
                    'Score': signal['score'],
                    'Risk': signal['risk_category'],
                    'Allocation %': f"{signal['allocation_percent']:.2%}",
                    'Capital': f"${signal['allocated_capital']:,.2f}"
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
    # Initialize session state
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
    if 'username' not in st.session_state:
        st.session_state.username = ""

    # Show login or main app
    if not st.session_state.logged_in:
        login_section()
    else:
        main_app()

if __name__ == "__main__":
    main()
