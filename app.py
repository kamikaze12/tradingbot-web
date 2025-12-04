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
import json

# ✅ FIX: Add the project root to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Try to import plotly
try:
    import plotly.graph_objects as go
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False

# Import TradingBot - FIXED IMPORT
try:
    from bot.core import TradingBot
    print("✅ Successfully imported TradingBot from bot.core")
except ImportError as e:
    try:
        from core import TradingBot
        print("✅ Successfully imported TradingBot from core")
    except ImportError as e2:
        st.error(f"❌ Import Error: {e2}")
        st.stop()

# ====================================
# Setup
# ====================================
load_dotenv()
st.set_page_config(page_title="TradingBot Pro", layout="wide")

# ====================================
# Helper Functions - ENHANCED
# ====================================
def check_login(username, password):
    """Simple login system"""
    users = {"muraga": "namikaze", "user2": "password2", "user3": "password3", "admin": "admin123"}
    return users.get(username) == password

def format_symbol_for_mode(symbol, market_type, trading_mode):
    """Format symbol sesuai dengan market type dan trading mode - FIXED VERSION"""
    if not symbol:
        return symbol
    
    symbol = str(symbol).upper()
    
    # 🚨 **FIX**: Deteksi jika sudah format futures
    futures_markers = [':USDT', 'PERP', '/USDT:', 'FUTURES', 'USDT:', '-USDT', '-PERP']
    is_already_futures = any(marker in symbol for marker in futures_markers)
    
    if market_type == "crypto":
        if trading_mode == "futures" and not is_already_futures:
            # Format futures: default ke format dengan :USDT (OKX/Binance)
            if '/USDT' in symbol:
                # Contoh: BTC/USDT -> BTC/USDT:USDT
                return f"{symbol}:USDT"
            elif 'USDT' in symbol and '/' not in symbol:
                # Contoh: BTCUSDT -> BTC/USDT:USDT
                base = symbol.replace('USDT', '')
                return f"{base}/USDT:USDT"
            else:
                # Contoh: BTC -> BTC/USDT:USDT
                return f"{symbol}/USDT:USDT"
        elif trading_mode == "spot" and is_already_futures:
            # Konversi futures ke spot: hapus marker futures
            for marker in futures_markers:
                symbol = symbol.replace(marker, '')
            # Pastikan format spot: BTC/USDT
            if 'USDT' in symbol and '/' not in symbol:
                base = symbol.replace('USDT', '')
                return f"{base}/USDT"
    
    # Untuk market lain, biarkan seperti semula
    return symbol

def convert_symbol_for_display(symbol, market_type, trading_mode):
    """Convert symbol untuk display yang user-friendly"""
    if not symbol:
        return symbol
    
    symbol = str(symbol)
    
    if trading_mode == "futures":
        if symbol.endswith("-PERP"):
            return f"{symbol.replace('-PERP', '')} (Futures)"
        elif symbol.endswith("-SWAP"):
            return f"{symbol.replace('-SWAP', '')} (Swap)"
    
    # Format spot lebih rapi
    if market_type == "crypto" and "/" in symbol:
        return symbol
    
    if market_type == "forex" and "/" in symbol:
        return symbol
    
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

@st.cache_resource
def init_bot():
    """Initialize TradingBot"""
    try:
        bot = TradingBot()
        print("✅ TradingBot initialized successfully")
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
        analysis.get('entry_range_low') == analysis.get('entry_range_high')):
        
        # Gunakan ATR atau volatilitas untuk menentukan range yang realistis
        atr = analysis.get('atr', 0)
        volatility = analysis.get('volatility', 0.02)  # Default 2%
        
        print(f"DEBUG {symbol}: ATR={atr}, Volatility={volatility}, Current={current_price}")
        
        # Jika ATR tersedia, gunakan untuk menghitung range
        if atr > 0:
            range_size = atr * 0.5  # Gunakan 0.5 ATR untuk entry range
        else:
            # Fallback: gunakan persentase berdasarkan volatilitas
            range_size = current_price * volatility * 0.5
        
        # Pastikan range_size minimal 0.5% dari current price
        min_range = current_price * 0.005  # 0.5% minimal
        range_size = max(range_size, min_range)
        
        # Pastikan range_size maksimal 3% (untuk menghindari range terlalu besar)
        max_range = current_price * 0.03
        range_size = min(range_size, max_range)
        
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
    
    # ✅ PERBAIKAN KRITIS: Validasi TP/SL (kode sebelumnya tetap)
    tp1 = analysis.get('tp1', 0)
    tp2 = analysis.get('tp2', 0) 
    tp3 = analysis.get('tp3', 0)
    sl = analysis.get('sl', 0)
    
    if (tp1 <= 0 or tp2 <= 0 or tp3 <= 0 or sl <= 0 or 
        tp1 == tp2 == tp3 == sl == current_price):
        
        if action == "LONG":
            analysis['tp1'] = current_price * 1.02  # 2%
            analysis['tp2'] = current_price * 1.04  # 4%
            analysis['tp3'] = current_price * 1.06  # 6%
            analysis['sl'] = current_price * 0.98   # -2%
            
            # Urutkan ascending untuk LONG
            tp_levels = sorted([analysis['tp1'], analysis['tp2'], analysis['tp3']])
            analysis['tp1'], analysis['tp2'], analysis['tp3'] = tp_levels
            
        else:  # SHORT
            analysis['tp1'] = current_price * 0.98  # -2%
            analysis['tp2'] = current_price * 0.96  # -4%
            analysis['tp3'] = current_price * 0.94  # -6%
            analysis['sl'] = current_price * 1.02   # +2%
            
            # ✅ PERBAIKAN: Urutkan DESCENDING untuk SHORT
            tp_levels = sorted([analysis['tp1'], analysis['tp2'], analysis['tp3']], reverse=True)
            analysis['tp1'], analysis['tp2'], analysis['tp3'] = tp_levels
    
    return analysis

def calculate_tp_probability(current_price, tp1, tp2, tp3, sl, action, volatility=0.02):
    """Hitung probabilitas hit TP1, TP2, TP3 berdasarkan distance dan volatilitas - FIXED"""
    try:
        if action == "LONG":
            # Untuk LONG: TP1 < TP2 < TP3, SL < Entry
            tp_levels = sorted([tp1, tp2, tp3])
            distances = {
                'tp1': max(0.0001, (tp_levels[0] - current_price) / current_price),
                'tp2': max(0.0001, (tp_levels[1] - current_price) / current_price),
                'tp3': max(0.0001, (tp_levels[2] - current_price) / current_price),
                'sl': max(0.0001, (current_price - sl) / current_price)
            }
            
        else:  # SHORT
            # Untuk SHORT: TP harus diurutkan dari TERDEKAT ke TERJAUH
            # TP TERDEKAT = nilai TERBESAR (karena harga turun dari current_price)
            tp_levels = sorted([tp1, tp2, tp3], reverse=True)
            
            # Debug: print urutan TP
            print(f"SHORT TP Levels sorted: {tp_levels}")
            
            distances = {
                'tp1': max(0.0001, (current_price - tp_levels[0]) / current_price),  # TP terdekat
                'tp2': max(0.0001, (current_price - tp_levels[1]) / current_price),  # TP menengah
                'tp3': max(0.0001, (current_price - tp_levels[2]) / current_price),  # TP terjauh
                'sl': max(0.0001, (sl - current_price) / current_price)  # SL di atas
            }
        
        # Debug distances
        print(f"Distances for {action}: {distances}")
        
        # Probabilitas berdasarkan rasio risk/reward
        risk_distance = distances['sl']
        probabilities = {}
        
        for i, target in enumerate(['tp1', 'tp2', 'tp3']):
            reward_distance = distances[target]
            
            if reward_distance <= 0 or risk_distance <= 0:
                probabilities[target] = 0.05
                continue
            
            # Risk/Reward Ratio = Reward / Risk
            risk_reward_ratio = reward_distance / risk_distance
            
            # Base probability berdasarkan risk/reward ratio
            if risk_reward_ratio >= 3:
                base_prob = 0.75  # Sangat baik
            elif risk_reward_ratio >= 2:
                base_prob = 0.65  # Baik
            elif risk_reward_ratio >= 1.5:
                base_prob = 0.55  # Cukup baik
            elif risk_reward_ratio >= 1:
                base_prob = 0.45  # Sedang
            elif risk_reward_ratio >= 0.5:
                base_prob = 0.35  # Rendah
            else:
                base_prob = 0.20  # Sangat rendah
            
            # Adjust untuk TP yang lebih jauh
            distance_penalty = i * 0.20  # TP2 -20%, TP3 -40%
            
            # Adjust berdasarkan volatilitas (volatility tinggi = probability lebih rendah)
            volatility_adjustment = volatility * 1.5
            
            final_prob = base_prob - distance_penalty - volatility_adjustment
            
            # Batasi antara 5% dan 85%
            final_prob = max(0.05, min(0.85, final_prob))
            
            probabilities[target] = round(final_prob, 3)
        
        # Pastikan TP1 > TP2 > TP3
        if probabilities.get('tp1', 0) < probabilities.get('tp2', 0):
            probabilities['tp1'], probabilities['tp2'] = probabilities['tp2'], probabilities['tp1']
        if probabilities.get('tp1', 0) < probabilities.get('tp3', 0):
            probabilities['tp1'], probabilities['tp3'] = probabilities['tp3'], probabilities['tp1']
        if probabilities.get('tp2', 0) < probabilities.get('tp3', 0):
            probabilities['tp2'], probabilities['tp3'] = probabilities['tp3'], probabilities['tp2']
        
        return probabilities
        
    except Exception as e:
        print(f"Error calculating TP probability: {e}")
        # Return probabilities yang lebih realistis sebagai fallback
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

    # Initialize bot dengan error handling yang lebih baik
    if 'bot_instance' not in st.session_state:
        try:
            bot = init_bot()
            if bot:
                st.session_state.bot_instance = bot
                # 🚨 **FIX**: Set default mode jika belum diset
                if not hasattr(bot, 'mode'):
                    bot.mode = "crypto"
                if not hasattr(bot, 'trading_mode'):
                    bot.trading_mode = "spot"
            else:
                st.error("❌ Failed to initialize TradingBot")
                st.stop()
        except Exception as e:
            st.error(f"❌ Bot initialization error: {e}")
            st.stop()
    
    bot = st.session_state.bot_instance
    
    # 🚨 **FIX**: Tampilkan status provider
    with st.expander("🔧 Provider Status", expanded=False):
        try:
            if hasattr(bot, 'data_provider') and hasattr(bot.data_provider, 'get_health_metrics'):
                metrics = bot.data_provider.get_health_metrics()
                st.write(f"**Active Exchange:** {metrics.get('active_exchange', 'Unknown')}")
                st.write(f"**Market Type:** {metrics.get('market_type', 'Unknown')}")
                st.write(f"**Trading Mode:** {metrics.get('trading_mode', 'Unknown')}")
                st.write(f"**Using CCXT:** {metrics.get('using_ccxt', False)}")
                st.write(f"**Using YFinance:** {metrics.get('using_yfinance', False)}")
                
                if metrics.get('using_yfinance', False):
                    st.info("ℹ️ Using YFinance as data source (CCXT may be unavailable)")
        except:
            st.write("Provider status unavailable")

    # Initialize session state dengan approach yang lebih clean
    if 'app_initialized' not in st.session_state:
        st.session_state.app_initialized = True
        st.session_state.positions_data = []
        st.session_state.history_data = []
        st.session_state.scanned_results = []
        st.session_state.selected_analysis = None
        st.session_state.selected_for_entry = {}
        st.session_state.current_market = None
        st.session_state.current_trading_mode = None  # ✅ Tambah untuk trading mode
        st.session_state.market_set = False
        # State-state tambahan dari app (1).py
        st.session_state.live_monitoring = False
        st.session_state.custom_result = None
        st.session_state.backtest_results = {}
        st.session_state.portfolio_allocations = {}
        st.session_state.risk_assessments = {}
        st.session_state.latest_results = []  # untuk auto rescan

    # Sidebar - ENHANCED dengan Trading Mode Support
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

        # Set Market Button - FIXED APPROACH dengan trading_mode
        if st.button("🎯 Set Market", key="set_market_btn"):
            try:
                # Validasi Futures hanya untuk Crypto
                if market_choice != "Crypto" and trading_mode == "Futures":
                    st.error("❌ Futures mode hanya tersedia untuk Crypto")
                else:
                    # Set market mode menggunakan parameter yang benar
                    market_mode_map = {
                        "Crypto": "crypto",
                        "Forex": "forex", 
                        "Saham Indonesia": "saham_id",
                        "US Stocks": "us_stocks"
                    }
                    
                    mode_string = market_mode_map[market_choice]
                    
                    # 🚨 **PERBAIKAN UTAMA**: Gunakan approach yang lebih toleran
                    try:
                        # 1. Set trading mode dulu (jika ada method)
                        if hasattr(bot, 'set_trading_mode'):
                            trading_mode_lower = trading_mode.lower()
                            if trading_mode_lower in ['futures', 'future']:
                                bot.set_trading_mode('futures')
                            else:
                                bot.set_trading_mode('spot')
                        else:
                            # Set attribute langsung
                            bot.trading_mode = trading_mode.lower()
                        
                        # 2. Set market mode dengan error handling
                        if hasattr(bot, 'set_mode'):
                            success = bot.set_mode(mode_string)
                            
                            # 🚨 **FIX**: Meskipun success False, tetap lanjutkan
                            if success or (not success and hasattr(bot, 'mode')):
                                # Update bot mode jika set_mode gagal tapi attribute ada
                                bot.mode = mode_string
                                
                                # Set session state
                                st.session_state.current_market = market_choice
                                st.session_state.current_trading_mode = trading_mode
                                st.session_state.market_set = True
                                st.session_state.scanned_results = []
                                st.session_state.selected_for_entry = {}
                                
                                st.success(f"✅ Market set to: {market_choice} ({trading_mode})")
                                st.info("ℹ️ Note: Provider mungkin memiliki limit data, scanning tetap bisa dilakukan")
                                st.rerun()
                            else:
                                st.error("❌ Failed to set market mode")
                        else:
                            # Fallback: set attribute langsung
                            bot.mode = mode_string
                            
                            st.session_state.current_market = market_choice
                            st.session_state.current_trading_mode = trading_mode
                            st.session_state.market_set = True
                            st.success(f"✅ Market set to: {market_choice} ({trading_mode})")
                            st.rerun()
                            
                    except Exception as set_error:
                        # 🚨 **FIX**: Tetap lanjutkan meskipun ada error
                        st.warning(f"⚠️ Warning during set: {str(set_error)[:100]}")
                        
                        # Tetap set session state agar bisa melanjutkan
                        st.session_state.current_market = market_choice
                        st.session_state.current_trading_mode = trading_mode
                        st.session_state.market_set = True
                        
                        st.success(f"✅ Market set to: {market_choice} ({trading_mode}) (with warnings)")
                        st.rerun()
                        
            except Exception as e:
                # 🚨 **FIX**: Tangani error dengan lebih baik
                st.error(f"❌ Error: {str(e)[:200]}")
                
                # Tampilkan solusi
                with st.expander("🔧 Troubleshooting Tips"):
                    st.write("""
                    1. **Data Provider Issue**: Bot menggunakan UnifiedDataProvider dengan OKX
                    2. **Test Connection**: Provider test hanya mendapatkan 10 bar data (minimal 20)
                    3. **Tapi Scanning tetap bisa bekerja** dengan data yang ada
                    
                    **Solusi:**
                    - Coba scanning assets dulu
                    - Jika gagal, coba market lain (Forex, Saham, Stocks)
                    - Atau tunggu beberapa menit untuk koneksi stabil
                    """)
        
        # Tampilkan status market dan trading mode
        if st.session_state.market_set:
            st.success(f"✅ Active: {st.session_state.current_market}")
            if hasattr(bot, 'trading_mode'):
                mode_display = bot.trading_mode.upper()
                st.info(f"📊 Mode: {mode_display}")
                if bot.trading_mode == "futures":
                    # Cek leverage dari bot atau config
                    leverage = getattr(bot, 'leverage', 1)
                    if hasattr(bot, 'config') and 'leverage' in bot.config:
                        leverage = bot.config['leverage']
                    st.info(f"⚡ Leverage: {leverage}x")
        
        # Trading Mode Specific Controls
        if st.session_state.market_set and hasattr(bot, 'trading_mode') and bot.trading_mode == "futures":
            st.subheader("⚡ Futures Settings")
            leverage_options = [1, 3, 5, 10, 20, 50, 100]
            current_leverage = getattr(bot, 'leverage', 1)
            if hasattr(bot, 'config') and 'leverage' in bot.config:
                current_leverage = bot.config['leverage']
            
            selected_leverage = st.selectbox(
                "Select Leverage:",
                leverage_options,
                index=leverage_options.index(current_leverage) if current_leverage in leverage_options else 0
            )
            
            if st.button("Apply Leverage", key="apply_leverage"):
                try:
                    # Simpan leverage ke bot dan config
                    bot.leverage = selected_leverage
                    if hasattr(bot, 'config'):
                        bot.config['leverage'] = selected_leverage
                    
                    # Jika ada method set_leverage, panggil
                    if hasattr(bot, 'set_leverage'):
                        bot.set_leverage(selected_leverage)
                    
                    # Simpan config ke file
                    try:
                        with open('config.json', 'w') as f:
                            json.dump(bot.config, f, indent=2)
                    except:
                        pass
                    
                    st.success(f"✅ Leverage set to {selected_leverage}x")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Failed to set leverage: {e}")
        
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
                        st.write("- Crypto: BTCUSDT-PERP, ETHUSDT-PERP")
                        st.write("- Forex: EURUSD-PERP, GBPUSD-PERP (jika tersedia)")

        # 🚨 PERBAIKAN TAMBAHAN: Tambahkan troubleshooting section di sidebar
        with st.sidebar.expander("🆘 Troubleshooting", expanded=False):
            st.write("""
            **Common Issues & Solutions:**
            
            1. **"Failed to set market configuration"**
               - Provider test gagal karena hanya dapat 10 bar data
               - **SOLUSI**: Klik "Set Market" lagi atau lanjutkan scanning
            
            2. **No scan results**
               - Provider mungkin rate limited
               - **SOLUSI**: Tunggu 30 detik, lalu coba lagi
            
            3. **Futures not working**
               - Hanya crypto yang support futures
               - **SOLUSI**: Pilih "Crypto" + "Futures"
            
            4. **Can't get real-time prices**
               - Exchange API mungkin down
               - **SOLUSI**: Coba market lain (Forex/Stocks)
            """)
            
            if st.button("🔄 Force Reinitialize Bot"):
                if 'bot_instance' in st.session_state:
                    del st.session_state.bot_instance
                st.rerun()

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
        - Leverage available for Futures trading
        """)
        return

    # Main Tabs - ENHANCED: 8 tabs dengan trading mode support
    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
        "📊 Scan Assets", "🔍 Analyze", "🎯 Custom Entry", "💼 Positions", 
        "📈 History", "📡 Live Scanner", "🤖 ML Backtest", "⚖️ Portfolio"
    ])

    # Tab 1: Scan Assets - ENHANCED dengan Entry Range dan Symbol Conversion
    with tab1:
        st.subheader("Scan Potential Assets")
        
        # Tampilkan mode aktif
        if hasattr(bot, 'trading_mode'):
            mode_badge = "🔄 SPOT" if bot.trading_mode == "spot" else "⚡ FUTURES"
            st.info(f"**Mode:** {mode_badge} | **Market:** {st.session_state.current_market}")
        
        if st.session_state.current_market == "Crypto":
            scan_type = st.radio("Scan Type:", ["Standard", "Pump Fun"], key="scan_type")
        else:
            scan_type = "Standard"
        
        # 🔥 PERBAIKAN: Scan dengan simbol yang diformat sesuai mode
        if st.button("🚀 Start Scan", key="start_scan"):
            with st.spinner("Scanning assets..."):
                try:
                    # 🚨 **FIX**: Tambahkan fallback jika provider bermasalah
                    max_retries = 2
                    results = None
                    
                    for attempt in range(max_retries):
                        try:
                            results = bot.scan_potential_assets(20)
                            if results and len(results) > 0:
                                break
                            else:
                                st.warning(f"Attempt {attempt+1}: No results found")
                        except Exception as scan_error:
                            if attempt < max_retries - 1:
                                st.warning(f"Attempt {attempt+1} failed: {str(scan_error)[:100]}")
                                time.sleep(2)  # Tunggu sebentar
                            else:
                                st.error(f"Scan failed after {max_retries} attempts")
                    
                    if results:
                        # Process and validate results dengan simbol yang diformat
                        formatted_results = []
                        for result in results[:15]:  # Batasi untuk performa
                            if isinstance(result, dict) and 'symbol' in result:
                                original_symbol = safe_get(result, 'symbol')
                                
                                # Format simbol sesuai trading mode
                                formatted_symbol = format_symbol_for_mode(
                                    original_symbol, 
                                    bot.mode, 
                                    getattr(bot, 'trading_mode', 'spot')
                                )
                                
                                # Update simbol dalam result
                                result['symbol'] = formatted_symbol
                                result['original_symbol'] = original_symbol  # Simpan original
                                
                                # Validasi price levels
                                validated_result = validate_and_fix_price_levels(result, formatted_symbol, bot)
                                formatted_results.append(validated_result)
                        
                        st.session_state.scanned_results = formatted_results
                        st.success(f"✅ Found {len(formatted_results)} potential assets")
                    else:
                        # 🚨 **FIX**: Berikan opsi fallback
                        st.warning("⚠️ No signals found with current provider")
                        
                        with st.expander("🔄 Try Alternative"):
                            if st.button("Try YFinance Fallback"):
                                try:
                                    # Coba gunakan YFinance secara langsung
                                    from bot.data_provider import EnhancedYFinanceDataProvider
                                    yf_provider = EnhancedYFinanceDataProvider(market_type="crypto")
                                    # Lakukan scanning sederhana...
                                    st.info("YFinance fallback activated")
                                except:
                                    st.error("YFinance fallback also failed")
                                    
                except Exception as e:
                    st.error(f"Scan error: {str(e)[:200]}")

        # Display scanned results - ENHANCED dengan probabilitas TP dan ENTRY RANGE
        if st.session_state.scanned_results:
            st.subheader("Top Assets:")
            for i, res in enumerate(st.session_state.scanned_results, 1):
                if isinstance(res, dict) and 'symbol' in res:
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        symbol = safe_get(res, 'symbol')
                        action = safe_get(res, 'action', 'NEUTRAL')
                        action_color = "🟢" if action == "LONG" else "🔴" if action == "SHORT" else "⚪"
                        
                        # Tampilkan simbol dengan format display
                        display_symbol = convert_symbol_for_display(
                            symbol, 
                            bot.mode, 
                            getattr(bot, 'trading_mode', 'spot')
                        )
                        
                        st.write(f"{i}. {action_color} **{display_symbol}** - {action} (Score: {safe_get(res, 'score', 0)})")
                        
                        # Tampilkan original simbol jika berbeda
                        if 'original_symbol' in res and res['original_symbol'] != symbol:
                            st.caption(f"Original: {res['original_symbol']}")
                        
                        current_price = get_valid_price(res, symbol, bot)
                        st.write(f"💰 Current Price: `{current_price:.5f}`")
                        
                        # ✅ TAMPILKAN ENTRY RANGE DAN IDEAL ENTRY
                        st.write(f"📊 **Entry Range:** `{res.get('entry_range_low', 0):.5f} - {res.get('entry_range_high', 0):.5f}`")
                        st.write(f"🎯 **Ideal Entry:** `{res.get('best_entry', 0):.5f}`")
                        if 'range_size' in res:
                            st.write(f"📏 **Range Size:** `{res.get('range_size', 0):.1f}%`")
                        
                        # Display TP levels (sudah diurutkan oleh validate_and_fix_price_levels)
                        tp1, tp2, tp3 = safe_get(res, 'tp1', 0), safe_get(res, 'tp2', 0), safe_get(res, 'tp3', 0)
                        sl = safe_get(res, 'sl', 0)
                        
                        st.write(f"🎯 **TP Levels:** `{tp1:.5f}` | `{tp2:.5f}` | `{tp3:.5f}`")
                        st.write(f"🛑 **Stop Loss:** `{sl:.5f}`")
                        
                        # Hitung dan tampilkan probabilitas TP
                        if 'tp_probabilities' not in res:
                            res['tp_probabilities'] = calculate_tp_probability(
                                current_price, tp1, tp2, tp3, sl, action
                            )
                        
                        probs = res['tp_probabilities']
                        st.write(f"📊 **Probabilities:** TP1: {probs.get('tp1', 0)*100:.1f}% | TP2: {probs.get('tp2', 0)*100:.1f}% | TP3: {probs.get('tp3', 0)*100:.1f}%")
                    
                    with col2:
                        if st.button(f"Select", key=f"select_{i}"):
                            st.session_state.selected_for_entry[symbol] = res
                            st.success(f"Selected {display_symbol}!")
                            st.rerun()

            # Entry section for selected assets
            for symbol, analysis in list(st.session_state.selected_for_entry.items()):
                st.markdown("---")
                
                # Tampilkan simbol dengan format display
                display_symbol = convert_symbol_for_display(
                    symbol, 
                    bot.mode, 
                    getattr(bot, 'trading_mode', 'spot')
                )
                
                st.subheader(f"Entry for {display_symbol}")
                
                analysis = validate_and_fix_price_levels(analysis, symbol, bot)
                current_price = get_valid_price(analysis, symbol, bot)
                
                # 🔥 PERBAIKAN: Entry dengan leverage untuk futures
                col_entry1, col_entry2 = st.columns([2, 1])
                with col_entry1:
                    entry_price = st.number_input(
                        "Entry Price",
                        value=float(analysis.get('best_entry', current_price)),
                        min_value=0.0001,
                        format="%.5f",
                        key=f"entry_{symbol}"
                    )
                
                with col_entry2:
                    # Jika futures mode, tampilkan leverage
                    if hasattr(bot, 'trading_mode') and bot.trading_mode == "futures":
                        leverage = st.selectbox(
                            "Leverage",
                            [1, 3, 5, 10, 20, 50, 100],
                            index=0,
                            key=f"leverage_{symbol}"
                        )
                    else:
                        leverage = 1
                
                if st.button(f"✅ Add Position", key=f"add_{symbol}"):
                    try:
                        # Prepare additional data untuk futures
                        additional_data = {}
                        if hasattr(bot, 'trading_mode') and bot.trading_mode == "futures":
                            additional_data['leverage'] = leverage
                        
                        # Save position logic
                        position_id = bot.db.save_position(
                            symbol=symbol,
                            market_type=bot.mode,
                            action=safe_get(analysis, "action"),
                            entry_price=entry_price,
                            tp1=safe_get(analysis, "tp1", 0),
                            tp2=safe_get(analysis, "tp2", 0),
                            tp3=safe_get(analysis, "tp3", 0),
                            sl=safe_get(analysis, "sl", 0),
                            **additional_data
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

            # Auto Rescan Section
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

    # Tab 2: Analyze Asset - ENHANCED dengan Entry Range dan Symbol Conversion
    with tab2:
        st.subheader("Analyze Specific Asset")
        
        # Info mode
        if hasattr(bot, 'trading_mode'):
            mode_status = "🔄 Spot" if bot.trading_mode == "spot" else "⚡ Futures"
            st.caption(f"Mode: {mode_status}")
        
        col_analyze1, col_analyze2 = st.columns([2, 1])
        with col_analyze1:
            symbol_input = st.text_input("Enter symbol:", key="analyze_symbol", placeholder="BTC or BTC/USDT or BTCUSDT-PERP")
        
        with col_analyze2:
            # Contoh simbol berdasarkan mode
            with st.expander("Examples"):
                if hasattr(bot, 'trading_mode'):
                    if bot.trading_mode == "spot":
                        st.write("Spot Examples:")
                        st.write("- BTC/USDT")
                        st.write("- ETH/USDT")
                        st.write("- EUR/USD")
                    else:
                        st.write("Futures Examples:")
                        st.write("- BTCUSDT-PERP")
                        st.write("- ETHUSDT-PERP")
                        st.write("- BTC-PERP")
        
        if st.button("Analyze", key="analyze_btn"):
            if symbol_input:
                with st.spinner("Analyzing..."):
                    try:
                        symbol = symbol_input.upper()
                        
                        # 🔥 PERBAIKAN: Format simbol sebelum analisis
                        formatted_symbol = format_symbol_for_mode(
                            symbol, 
                            bot.mode,
                            getattr(bot, 'trading_mode', 'spot')
                        )
                        
                        st.info(f"Analyzing: {formatted_symbol}")
                        
                        analysis = bot.analyze_asset(formatted_symbol)
                        if analysis:
                            analysis = validate_and_fix_price_levels(analysis, formatted_symbol, bot)
                            
                            # Tambahkan simbol yang diformat
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
            
            st.subheader(f"Analysis: {symbol_display}")
            
            # Tampilkan info simbol
            if 'original_input' in analysis and analysis['original_input'] != analysis.get('formatted_symbol', ''):
                st.caption(f"Original input: {analysis['original_input']}")
            
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
            
            if 'range_size' in analysis:
                st.metric("Range Size", f"{analysis.get('range_size', 0):.1f}%")
            
            # Plot entry range jika available
            if PLOTLY_AVAILABLE:
                fig_range = plot_entry_range(analysis)
                if fig_range:
                    st.plotly_chart(fig_range, use_container_width=True)

    # Tab 3: Custom Entry - DENGAN Trading Mode Support
    with tab3:
        st.subheader("🎯 Custom Entry")
        
        # Mode info
        if hasattr(bot, 'trading_mode'):
            mode_display = "🔄 Spot" if bot.trading_mode == "spot" else "⚡ Futures"
            st.info(f"**Trading Mode:** {mode_display}")
        
        col_symbol, col_action = st.columns([2, 1])
        with col_symbol:
            symbol_custom = st.text_input("Masukkan simbol aset:", key="custom_symbol", 
                                         placeholder="BTC untuk auto-format")
        with col_action:
            action_custom = st.selectbox("Action:", ["LONG", "SHORT"], key="custom_action")
        
        # 🔥 PERBAIKAN: Format simbol otomatis
        formatted_custom_symbol = None
        if symbol_custom:
            formatted_custom_symbol = format_symbol_for_mode(
                symbol_custom.upper(),
                bot.mode,
                getattr(bot, 'trading_mode', 'spot')
            )
            
            if formatted_custom_symbol != symbol_custom.upper():
                st.info(f"Simbol akan diformat menjadi: **{formatted_custom_symbol}**")
        
        col_price, col_leverage = st.columns([2, 1])
        with col_price:
            entry_price_custom = st.number_input("Harga Entry:", value=0.0, step=0.0001, key="custom_entry")
        
        with col_leverage:
            # Tampilkan leverage untuk futures
            if hasattr(bot, 'trading_mode') and bot.trading_mode == "futures":
                leverage_custom = st.selectbox(
                    "Leverage:",
                    [1, 3, 5, 10, 20, 50, 100],
                    index=0,
                    key="custom_leverage"
                )
            else:
                leverage_custom = 1
                st.text("Leverage: 1x (Spot)")
        
        if st.button("🧮 Hitung TP/SL", key="calculate_custom"):
            if symbol_custom and entry_price_custom > 0:
                with st.spinner("Menghitung..."):
                    try:
                        # Gunakan simbol yang sudah diformat
                        symbol_to_use = formatted_custom_symbol if formatted_custom_symbol else symbol_custom.upper()
                        
                        result = bot.calculate_custom_entry(symbol_to_use, entry_price_custom, action_custom)
                        if result:
                            # Validasi dan perbaiki price levels
                            result = validate_and_fix_price_levels(result, symbol_to_use, bot)
                            
                            # Tambahkan info trading mode
                            result['trading_mode'] = getattr(bot, 'trading_mode', 'spot')
                            result['leverage'] = leverage_custom
                            
                            # Urutkan TP levels sesuai action
                            if action_custom == "LONG":
                                tp1, tp2, tp3 = sorted([result['tp1'], result['tp2'], result['tp3']])
                            else:  # SHORT
                                tp1, tp2, tp3 = sorted([result['tp1'], result['tp2'], result['tp3']], reverse=True)
                            
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
                        st.error(f"Error: {e}")
            else:
                st.warning("Masukkan simbol dan harga entry yang valid.")
        
        # Tampilkan hasil custom entry
        if st.session_state.custom_result:
            result = st.session_state.custom_result
            symbol_display = convert_symbol_for_display(
                result['symbol'],
                bot.mode,
                result.get('trading_mode', 'spot')
            )
            
            st.subheader(f"📊 Hasil untuk {symbol_display}")
            
            # Tampilkan mode dan leverage
            col_mode, col_lev = st.columns(2)
            with col_mode:
                mode_badge = "🔄 SPOT" if result.get('trading_mode') == 'spot' else "⚡ FUTURES"
                st.metric("Mode", mode_badge)
            with col_lev:
                if result.get('trading_mode') == 'futures':
                    st.metric("Leverage", f"{result.get('leverage', 1)}x")
            
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
            
            if 'range_size' in result:
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
                if action_custom == "LONG":
                    tp1, tp2, tp3 = sorted([result['tp1'], result['tp2'], result['tp3']])
                else:  # SHORT
                    tp1, tp2, tp3 = sorted([result['tp1'], result['tp2'], result['tp3']], reverse=True)
                
                # Prepare additional data
                additional_data = {}
                if result.get('trading_mode') == 'futures':
                    additional_data['leverage'] = result.get('leverage', 1)
                
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
                    **additional_data
                )
                if position_id:
                    st.success(f"Posisi {symbol_display} ditambahkan!")
                    st.session_state.positions_data = bot.get_active_positions()
                    st.rerun()
                else:
                    st.error("Gagal tambah posisi.")

    # 🔥 TAB 4: POSITIONS - FULLY FIXED VERSION dengan Trading Mode Support
    with tab4:
        st.subheader("💼 Active Positions")
        
        # Mode info
        if hasattr(bot, 'trading_mode'):
            mode_display = "🔄 Spot" if bot.trading_mode == "spot" else "⚡ Futures"
            st.info(f"**Trading Mode:** {mode_display}")
        
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
                        
                        # Ambil leverage jika ada
                        leverage = float(pos[14]) if len(pos) > 14 and pos[14] else 1
                        
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
                        leverage = float(safe_get(pos, 'leverage', 1))
                    
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
                    
                    # 🔥 PERBAIKAN: Tampilkan simbol dengan format display
                    display_symbol = convert_symbol_for_display(
                        symbol,
                        bot.mode,
                        getattr(bot, 'trading_mode', 'spot')
                    )
                    
                    # Tampilkan position card
                    with st.container():
                        col1, col2, col3 = st.columns([3, 2, 1])
                        
                        with col1:
                            st.write(f"**{display_symbol}** - {action} {pl_emoji}")
                            
                            # 🔥 PERBAIKAN: Tampilkan leverage jika futures atau leverage > 1
                            if (getattr(bot, 'trading_mode', 'spot') == 'futures' or leverage > 1):
                                st.write(f"⚡ **Leverage:** {leverage}x")
                            
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
                                        st.success(f"✅ {display_symbol} position closed at {current_price:.5f}!")
                                        # Refresh data
                                        time.sleep(1)
                                        st.session_state.positions_data = bot.get_active_positions()
                                        st.rerun()
                                    else:
                                        st.error(f"❌ Failed to close {display_symbol}")
                                except Exception as close_error:
                                    st.error(f"❌ Close error: {close_error}")
                    
                    st.markdown("---")
                    
                    # Simpan posisi yang sudah di-update
                    updated_positions.append({
                        'id': position_id,
                        'symbol': symbol,
                        'display_symbol': display_symbol,
                        'action': action,
                        'entry_price': entry_price,
                        'current_price': current_price,
                        'tp1': tp1,
                        'tp2': tp2,
                        'tp3': tp3,
                        'sl': sl,
                        'entry_low': entry_low,
                        'entry_high': entry_high,
                        'best_entry': best_entry,
                        'leverage': leverage
                    })
                    
                except Exception as e:
                    st.error(f"❌ Position error for {safe_get(pos, 'symbol', 'unknown')}: {str(e)}")
            
            # 🔥 PERBAIKAN: Simpan posisi yang sudah di-update ke session state
            st.session_state.positions_data = updated_positions
            
            # Auto-refresh jika diaktifkan
            if auto_refresh_positions:
                time.sleep(15)
                st.rerun()

    # Tab 5: History - DENGAN Symbol Conversion
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
                    
                    # 🔥 PERBAIKAN: Format simbol untuk display
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

    # 🔥 TAB 6: LIVE SCANNER - FULLY FIXED VERSION dengan Trading Mode
    with tab6:
        st.subheader("📡 Live Scanner")
        
        # Mode info
        if hasattr(bot, 'trading_mode'):
            mode_display = "🔄 Spot" if bot.trading_mode == "spot" else "⚡ Futures"
            st.info(f"**Trading Mode:** {mode_display}")
        
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
                            leverage = safe_get(pos, 'leverage', 1)
                            
                            # 🔥 PERBAIKAN: Format simbol untuk display
                            display_symbol = convert_symbol_for_display(
                                symbol,
                                bot.mode,
                                getattr(bot, 'trading_mode', 'spot')
                            )
                            
                            # Update posisi dengan harga terbaru
                            pos_dict = {
                                'id': safe_get(pos, 'id'),
                                'symbol': symbol,
                                'display_symbol': display_symbol,
                                'action': action,
                                'entry_price': entry_price,
                                'current_price': latest_price,
                                'tp1': float(safe_get(pos, 'tp1', 0)),
                                'tp2': float(safe_get(pos, 'tp2', 0)),
                                'tp3': float(safe_get(pos, 'tp3', 0)),
                                'sl': float(safe_get(pos, 'sl', 0)),
                                'leverage': leverage
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
                                st.write(f"**{display_symbol}** - {action}")
                                if (getattr(bot, 'trading_mode', 'spot') == 'futures' or leverage > 1):
                                    st.write(f"⚡ {leverage}x")
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

    # Tab 7: ML Backtest - DENGAN Symbol Conversion
    with tab7:
        st.subheader("🤖 ML Backtest & Analysis")
        
        # Mode info
        if hasattr(bot, 'trading_mode'):
            mode_display = "🔄 Spot" if bot.trading_mode == "spot" else "⚡ Futures"
            st.info(f"**Trading Mode:** {mode_display}")
        
        col1, col2 = st.columns([2, 1])
        with col1:
            backtest_symbol = st.text_input("Symbol untuk Backtest:", key="backtest_symbol")
        with col2:
            backtest_days = st.selectbox("Period:", [30, 90, 180, 365], index=2)
        
        # 🔥 PERBAIKAN: Format simbol sebelum backtest
        formatted_backtest_symbol = None
        if backtest_symbol:
            formatted_backtest_symbol = format_symbol_for_mode(
                backtest_symbol.upper(),
                bot.mode,
                getattr(bot, 'trading_mode', 'spot')
            )
            
            if formatted_backtest_symbol != backtest_symbol.upper():
                st.info(f"Simbol akan diformat: **{formatted_backtest_symbol}**")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("🚀 Run Backtest", key="run_backtest"):
                if backtest_symbol:
                    with st.spinner("Running comprehensive backtest..."):
                        symbol_to_use = formatted_backtest_symbol if formatted_backtest_symbol else backtest_symbol.upper()
                        
                        if hasattr(bot, 'run_comprehensive_backtest'):
                            results = bot.run_comprehensive_backtest(symbol_to_use, backtest_days)
                        else:
                            results = {"error": "Backtest feature not available"}
                        st.session_state.backtest_results = results
                        st.rerun()
        
        with col2:
            if st.button("📊 Enhanced Analysis", key="enhanced_analysis"):
                if backtest_symbol:
                    with st.spinner("Running enhanced analysis..."):
                        symbol_to_use = formatted_backtest_symbol if formatted_backtest_symbol else backtest_symbol.upper()
                        
                        if hasattr(bot, 'analyze_with_ml'):
                            analysis = bot.analyze_with_ml(symbol_to_use)
                        else:
                            analysis = bot.analyze_asset(symbol_to_use)
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

    # Tab 8: Portfolio Optimization - DENGAN Trading Mode Support
    with tab8:
        st.subheader("⚖️ Portfolio Optimization")
        
        # Mode info
        if hasattr(bot, 'trading_mode'):
            mode_display = "🔄 Spot" if bot.trading_mode == "spot" else "⚡ Futures"
            st.info(f"**Trading Mode:** {mode_display}")
        
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
                # Format simbol untuk display
                display_symbol = convert_symbol_for_display(
                    signal['symbol'],
                    bot.mode,
                    getattr(bot, 'trading_mode', 'spot')
                )
                
                allocation_data.append({
                    'Symbol': display_symbol,
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
                        labels=[convert_symbol_for_display(s['symbol'], bot.mode, getattr(bot, 'trading_mode', 'spot')) 
                               for s in allocations['signals']],
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
        - Futures margin calculations (if applicable)
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
