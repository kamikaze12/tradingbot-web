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
    from core import TradingBot
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
    
    action = analysis.get('action', 'LONG')
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

# ====================================
# Main App - SIMPLIFIED VERSION
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

    # Sidebar - SIMPLIFIED & FIXED
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
        
        # Refresh data
        if st.button("🔄 Refresh Data", key="refresh_data"):
            try:
                st.session_state.positions_data = bot.get_active_positions()
                st.session_state.history_data = bot.get_trade_history()
                st.success("Data refreshed!")
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")

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

    # Main Tabs
    tab1, tab2, tab3, tab4 = st.tabs([
        "📊 Scan Assets", "🔍 Analyze", "💼 Positions", "📈 History"
    ])

    # Tab 1: Scan Assets
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

        # Display scanned results
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
                        st.write(f"💰 Price: `{current_price:.5f}` | SL: `{safe_get(res, 'sl', 0):.5f}`")
                        
                        # Display TP levels
                        tp1, tp2, tp3 = safe_get(res, 'tp1', 0), safe_get(res, 'tp2', 0), safe_get(res, 'tp3', 0)
                        if action == "LONG":
                            tp1, tp2, tp3 = sorted([tp1, tp2, tp3])
                        else:
                            tp1, tp2, tp3 = sorted([tp1, tp2, tp3], reverse=True)
                        
                        st.write(f"🎯 TP: `{tp1:.5f}` | `{tp2:.5f}` | `{tp3:.5f}`")
                    
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

    # Tab 2: Analyze Asset
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
            
            with col2:
                st.metric("Trend", safe_get(analysis, 'trend', 'NEUTRAL'))
                st.metric("RSI", f"{safe_get(analysis, 'rsi', 0):.1f}")
                st.metric("Volume Ratio", f"{safe_get(analysis, 'volume_ratio', 0):.2f}")

    # Tab 3: Positions
    with tab3:
        st.subheader("Active Positions")
        
        if st.button("🔄 Refresh Positions", key="refresh_positions"):
            st.session_state.positions_data = bot.get_active_positions()
            st.rerun()
        
        if not st.session_state.positions_data:
            st.info("No active positions")
        else:
            for pos in st.session_state.positions_data:
                try:
                    if isinstance(pos, tuple):
                        symbol = pos[1]
                        action = pos[3]
                        entry_price = pos[4]
                        current_price = pos[11] if len(pos) > 11 else entry_price
                    else:
                        symbol = safe_get(pos, 'symbol')
                        action = safe_get(pos, 'action')
                        entry_price = safe_get(pos, 'entry_price')
                        current_price = safe_get(pos, 'current_price', entry_price)
                    
                    # Calculate P/L
                    if action == "LONG":
                        pl_pct = ((current_price - entry_price) / entry_price) * 100
                    else:
                        pl_pct = ((entry_price - current_price) / entry_price) * 100
                    
                    pl_color = "green" if pl_pct >= 0 else "red"
                    
                    col1, col2, col3 = st.columns([3, 2, 1])
                    with col1:
                        st.write(f"**{symbol}** - {action}")
                        st.write(f"Entry: `{entry_price:.5f}` | Current: `{current_price:.5f}`")
                        st.write(f"P/L: <span style='color:{pl_color}'>{pl_pct:.2f}%</span>", unsafe_allow_html=True)
                    
                    with col3:
                        if st.button("Close", key=f"close_{symbol}"):
                            try:
                                if bot.close_position(safe_get(pos, 'id', 0), current_price):
                                    st.success("Position closed!")
                                    st.session_state.positions_data = bot.get_active_positions()
                                    st.rerun()
                            except Exception as e:
                                st.error(f"Close error: {e}")
                except Exception as e:
                    st.error(f"Position error: {e}")

    # Tab 4: History
    with tab4:
        st.subheader("Trade History")
        
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
