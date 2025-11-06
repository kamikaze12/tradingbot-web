import time
import asyncio
import threading
import schedule
import streamlit as st
import pandas as pd
from dotenv import load_dotenv

# Try to import plotly, fallback to streamlit charts if not available
try:
    import plotly.graph_objects as go
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False
    st.warning("Plotly not available. Install with: pip install plotly")

from bot.core import TradingBot

# ====================================
# Setup
# ====================================
load_dotenv()
st.set_page_config(page_title="TradingBot Pro", layout="wide")

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

# ====================================
# Main App
# ====================================
def main():
    st.title("🚀 TradingBot Pro - Enhanced Dashboard")
    bot = init_bot()

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
            if mode_choice == "Crypto":
                bot.set_mode("crypto")
            elif mode_choice == "Forex":
                bot.set_mode("forex")
            elif mode_choice == "Saham Indonesia":
                bot.set_mode("saham_id")

            st.session_state.scanned_results = []
            st.session_state.selected_symbols = []
            st.session_state.selected_analysis = None
            st.session_state.selected_for_entry = {}
            st.rerun()

        if bot.mode:
            st.success(f"Mode: {bot.mode.upper()}")

            if st.button("🔄 Refresh Semua Data", key="refresh_all"):
                st.session_state.positions_data = bot.get_active_positions()
                st.session_state.history_data = bot.get_trade_history()
                st.session_state.last_refresh = {"positions": time.time(), "history": time.time()}
                st.success("Data berhasil direfresh!")
                st.rerun()

    if not bot.mode:
        st.warning("Pilih market di sidebar!")
        return

    # Enhanced Tabs
    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
        "📊 Top Aset", "🔍 Analisis Aset", "🎯 Custom Entry", "💼 Posisi Aktif", 
        "📈 History", "📡 Live Scanner", "🤖 ML Backtest", "⚖️ Portfolio"
    ])

    # ===============================
    # Tab 1: Top Aset
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
                                st.session_state.selected_for_entry[symbol] = analysis
                                st.success(f"Selected {res['symbol']}!")
                                st.rerun()
                    else:
                        st.info("Tidak ada token baru di Pump Fun.")

                else:
                    all_results = bot.scan_potential_assets(100)  # Scan 100 koin
                    if all_results:
                        # Sort berdasarkan abs(score) descending (LONG/SHORT kuat duluan)
                        all_results.sort(key=lambda x: abs(x.get('score', 0)), reverse=True)
                        st.session_state.scanned_results = all_results[:10]  # Tampil hanya 10 terbaik
                        st.success("Scan selesai! Menampilkan 10 terbaik dari 100.")
                    else:
                        st.warning("Tidak ada hasil scan dari metode utama. Mencoba fallback dengan aset populer.")
                        fallback_assets = bot.get_popular_assets(100)
                        fallback_results = []
                        for asset in fallback_assets:
                            analysis = bot.analyze_asset(asset)
                            if analysis and analysis["action"] in ["LONG", "SHORT"] and analysis["score"] >= 1:
                                fallback_results.append(analysis)
                            elif analysis is None:
                                ticker = bot.data_provider.get_ticker(asset)
                                if ticker and 'last' in ticker:
                                    current_price = ticker['last']
                                    percentage = ticker.get('percentage', 0)
                                    volume = ticker.get('volume', 1.0)
                                    # Variasi score berdasarkan ticker
                                    simple_score = 2 if percentage > 0 else -2 if percentage < 0 else 1
                                    simple_patterns = ['ranging_channel'] if volume < 1000 else ['symmetrical_triangle'] if percentage == 0 else []
                                    simple_pattern_score = 1 if simple_patterns else 0
                                    analysis = {
                                        'symbol': asset,
                                        'action': 'LONG' if percentage > 0 else 'SHORT' if percentage < 0 else 'NEUTRAL',
                                        'score': simple_score,
                                        'ideal_entry': current_price,
                                        'entry_low': current_price * 0.99,
                                        'entry_high': current_price * 1.01,
                                        'tp1': current_price * (1.05 if percentage > 0 else 0.95),
                                        'tp2': current_price * (1.10 if percentage > 0 else 0.90),
                                        'tp3': current_price * (1.15 if percentage > 0 else 0.85),
                                        'sl': current_price * (0.95 if percentage > 0 else 1.05),
                                        'current_price': current_price,
                                        'rsi': 50.0 + (percentage * 5),
                                        'trend': 'BULLISH' if percentage > 0 else 'BEARISH' if percentage < 0 else 'NEUTRAL',
                                        'volume_ratio': volume / 1000 if volume > 1000 else 1.0,
                                        'atr': current_price * 0.01,
                                        'detected_patterns': simple_patterns,
                                        'pattern_score': simple_pattern_score,
                                        'ema_trend': 'NEUTRAL',
                                        'ema_score': 0
                                    }
                                    fallback_results.append(analysis)
                                else:
                                    st.warning(f"Gagal mengambil data untuk {asset}")
                        st.session_state.scanned_results = fallback_results
                        if not fallback_results:
                            st.error("Tidak ada data sama sekali. Periksa koneksi atau API key.")
                    st.rerun()

        # Tampilkan hasil scan
        if st.session_state.scanned_results:
            st.subheader("Top Aset Potensial:")

            for i, res in enumerate(st.session_state.scanned_results, 1):
                if isinstance(res, dict) and 'symbol' in res:
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.write(f"{i}. **{res['symbol']}** - {res['action']} (Score: {res['score']})")
                        st.write(f"Entry Range: {res['entry_low']:.5f} - {res['entry_high']:.5f} | "
                                 f"SL: {res['sl']:.5f}")
                        st.write(f"TP1: {res['tp1']:.5f} | TP2: {res['tp2']:.5f} | TP3: {res['tp3']:.5f}")
                        
                        # Tampilkan pola yang terdeteksi
                        if 'detected_patterns' in res and res['detected_patterns']:
                            st.write(f"📊 **Pola Terdeteksi:** {', '.join(res['detected_patterns'])}")
                        
                        # Tampilkan pattern score
                        if 'pattern_score' in res:
                            st.write(f"⭐ **Pattern Score:** {res['pattern_score']}")
                            
                        # Tampilkan risk category
                        if 'risk_category' in res:
                            st.write(f"⚖️ **Risk Category:** {res['risk_category']}")
                            
                    with col2:
                        if st.button(f"Pilih {i}", key=f"select_{res['symbol']}"):
                            st.session_state.selected_for_entry[res['symbol']] = res
                            st.success(f"Selected {res['symbol']}!")
                            st.rerun()
                else:
                    st.warning("Data analisis tidak valid untuk salah satu aset.")

            # Tampilkan input entry untuk setiap simbol yang dipilih
            for symbol, analysis in list(st.session_state.selected_for_entry.items()):
                if isinstance(analysis, dict) and 'symbol' in analysis:
                    st.markdown("---")
                    st.subheader(f"📈 Input Entry untuk {symbol}")
                    
                    col1, col2 = st.columns([2, 1])
                    with col1:
                        entry_price = st.number_input(
                            "Entry Price",
                            value=analysis.get("ideal_entry", analysis.get("entry_price", 0.0)),
                            step=0.001,
                            key=f"entry_{symbol}"
                        )
                    
                    with col2:
                        if st.button(f"✅ Tambah Posisi {symbol}", key=f"add_{symbol}"):
                            ideal_entry = analysis.get("ideal_entry", entry_price)
                            position_id = bot.db.save_position(
                                symbol=symbol,
                                market_type=bot.mode,
                                action=analysis["action"],
                                entry_price=entry_price,
                                tp1=entry_price + (analysis["tp1"] - ideal_entry),
                                tp2=entry_price + (analysis["tp2"] - ideal_entry),
                                tp3=entry_price + (analysis["tp3"] - ideal_entry),
                                sl=entry_price - (ideal_entry - analysis["sl"]),
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
                    
                    with st.expander("🔍 Detail Analisis"):
                        if 'momentum_quality' in analysis:
                            st.write(f"**Momentum Quality:** {analysis['momentum_quality']}")
                        if 'market_phase' in analysis:
                            st.write(f"**Market Phase:** {analysis['market_phase']}")
                        if 'reward_ratio' in analysis:
                            st.write(f"**Reward Ratio:** {analysis['reward_ratio']:.2f}")
                    
                    if st.button(f"🗑️ Hapus {symbol} dari pilihan", key=f"remove_{symbol}"):
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
                        st.write(f"**{res['symbol']}** - {res['action']} (Score: {res['score']})")
                        if 'detected_patterns' in res and res['detected_patterns']:
                            st.write(f"📊 Pola: {', '.join(res['detected_patterns'])}")

    # ===============================
    # Tab 2: Analisis Aset
    # ===============================
    with tab2:
        st.subheader("🔍 Analisis Aset Spesifik")
        
        symbol_input = st.text_input("Masukkan simbol aset:", key="symbol_input")

        if st.button("Analisis", key="analyze_asset"):
            with st.spinner("Menganalisis..."):
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
                if analysis and isinstance(analysis, dict) and 'symbol' in analysis:
                    st.session_state.selected_analysis = analysis
                    st.rerun()
                else:
                    ticker = bot.data_provider.get_ticker(symbol)
                    if ticker and 'last' in ticker:
                        current_price = ticker['last']
                        analysis = {
                            'symbol': symbol,
                            'action': 'LONG',
                            'score': 1,
                            'ideal_entry': current_price,
                            'entry_low': current_price * 0.99,
                            'entry_high': current_price * 1.01,
                            'tp1': current_price * 1.05,
                            'tp2': current_price * 1.10,
                            'tp3': current_price * 1.15,
                            'sl': current_price * 0.95,
                            'current_price': current_price,
                            'rsi': 50.0,
                            'trend': 'NEUTRAL',
                            'volume_ratio': 1.0,
                            'atr': current_price * 0.01,
                            'detected_patterns': [],
                            'pattern_score': 0,
                            'ema_trend': 'NEUTRAL',
                            'ema_score': 0
                        }
                        st.session_state.selected_analysis = analysis
                        st.warning("Menggunakan analisis fallback karena data historis tidak cukup.")
                        st.rerun()
                    else:
                        st.session_state.selected_analysis = None
                        st.error("Tidak dapat menganalisis aset. Pastikan simbol valid.")

        # Tampilkan hasil analisis
        if st.session_state.selected_analysis:
            analysis = st.session_state.selected_analysis
            if isinstance(analysis, dict) and 'symbol' in analysis:
                st.subheader(f"📊 Hasil Analisis untuk {analysis['symbol']}")
                
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("💰 Current Price", f"{analysis.get('current_price', 0):.5f}")
                    st.metric("📈 Trend", analysis.get('trend', 'NEUTRAL'))
                    st.metric("📊 RSI", f"{analysis.get('rsi', 0):.2f}")
                    st.metric("⭐ Score", analysis.get('score', 0))
                
                with col2:
                    st.metric("📉 ATR", f"{analysis.get('atr', 0):.5f}")
                    st.metric("🔄 Volume Ratio", f"{analysis.get('volume_ratio', 0):.2f}")
                    st.metric("EMA Trend", analysis.get('ema_trend', 'NEUTRAL'))
                    st.metric("EMA Score", analysis.get('ema_score', 0))
                
                # Enhanced analysis details
                if 'detected_patterns' in analysis and analysis['detected_patterns']:
                    st.write(f"📊 **Pola Terdeteksi:** {', '.join(analysis['detected_patterns'])}")
                
                if 'pattern_score' in analysis:
                    st.write(f"⭐ **Pattern Score:** {analysis['pattern_score']}")
                
                # Enhanced metrics
                col3, col4 = st.columns(2)
                with col3:
                    if 'risk_category' in analysis:
                        st.metric("⚖️ Risk Category", analysis['risk_category'])
                    if 'momentum_quality' in analysis:
                        st.metric("📈 Momentum Quality", analysis['momentum_quality'])
                with col4:
                    if 'market_phase' in analysis:
                        st.metric("🌊 Market Phase", analysis['market_phase'])
                    if 'reward_ratio' in analysis:
                        st.metric("🎯 Reward Ratio", f"{analysis['reward_ratio']:.2f}")
                
                st.subheader("🎯 Take Profit & Stop Loss")
                st.write(f"TP1: {analysis.get('tp1', 0):.5f}")
                st.write(f"TP2: {analysis.get('tp2', 0):.5f}")
                st.write(f"TP3: {analysis.get('tp3', 0):.5f}")
                st.write(f"SL: {analysis.get('sl', 0):.5f}")
                
                # Input entry price
                entry_price = st.number_input(
                    "Entry Price",
                    value=analysis.get("ideal_entry", 0.0),
                    step=0.001,
                    key="entry_analysis"
                )
                
                if st.button(f"✅ Tambah Posisi {analysis.get('symbol', 'Aset')}", key="add_analysis"):
                    ideal_entry = analysis.get("ideal_entry", entry_price)
                    position_id = bot.db.save_position(
                        symbol=analysis['symbol'],
                        market_type=bot.mode,
                        action=analysis.get("action", "LONG"),
                        entry_price=entry_price,
                        tp1=entry_price + (analysis.get("tp1", 0) - ideal_entry),
                        tp2=entry_price + (analysis.get("tp2", 0) - ideal_entry),
                        tp3=entry_price + (analysis.get("tp3", 0) - ideal_entry),
                        sl=entry_price - (ideal_entry - analysis.get("sl", 0)),
                        entry_low=entry_price * (1 - bot.strategy.entry_range_pct),
                        entry_high=entry_price * (1 + bot.strategy.entry_range_pct),
                    )
                    if position_id:
                        st.success(f"Posisi {analysis['symbol']} ditambahkan!")
                        st.session_state.positions_data = bot.get_active_positions()
                        st.rerun()
                    else:
                        st.error("Gagal tambah posisi.")
            else:
                st.error("Data analisis tidak valid. Coba analisis ulang.")

    # ===============================
    # Tab 3: Custom Entry
    # ===============================
    with tab3:
        st.subheader("🎯 Custom Entry")
        
        symbol_custom = st.text_input("Masukkan simbol aset:", key="custom_symbol")
        entry_price_custom = st.number_input("Harga Entry:", value=0.0, step=0.0001, key="custom_entry")
        
        if st.button("🧮 Hitung TP/SL", key="calculate_custom"):
            if symbol_custom and entry_price_custom > 0:
                with st.spinner("Menghitung..."):
                    result = bot.calculate_custom_entry(symbol_custom, entry_price_custom)
                    if result:
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
                risk_reward = (result['tp1'] - result['entry_price']) / (result['entry_price'] - result['sl'])
                st.metric("📊 Risk/Reward", f"{risk_reward:.2f}")
            
            # Tombol untuk menambahkan ke posisi
            if st.button("✅ Tambahkan ke Posisi Aktif", key="add_custom"):
                position_id = bot.db.save_position(
                    symbol=result['symbol'],
                    market_type=bot.mode,
                    action="LONG",
                    entry_price=result['entry_price'],
                    tp1=result['tp1'],
                    tp2=result['tp2'],
                    tp3=result['tp3'],
                    sl=result['sl'],
                    entry_low=result['entry_price'] * 0.99,
                    entry_high=result['entry_price'] * 1.01,
                )
                if position_id:
                    st.success(f"Posisi {result['symbol']} ditambahkan!")
                    st.session_state.positions_data = bot.get_active_positions()
                    st.rerun()
                else:
                    st.error("Gagal tambah posisi.")

    # ===============================
    # Tab 4: Posisi Aktif
    # ===============================
    with tab4:
        st.subheader("💼 Posisi Aktif")
        
        if st.button("🔄 Refresh Posisi", key="refresh_positions"):
            st.session_state.positions_data = bot.get_active_positions()
            st.success("Posisi diperbarui!")
            st.rerun()
        
        if not st.session_state.positions_data:
            st.info("📭 Tidak ada posisi aktif.")
        else:
            st.write(f"**📈 Total Posisi Aktif:** {len(st.session_state.positions_data)}")
            
            for pos in st.session_state.positions_data:
                pos_id = pos[0]
                symbol = pos[1]
                market_type = pos[2]
                action = pos[3]
                entry_price = pos[4]
                current_price = pos[11] if len(pos) > 11 else entry_price
                sl = pos[9] if len(pos) > 9 else 0
                tp1 = pos[6] if len(pos) > 6 else 0
                tp2 = pos[7] if len(pos) > 7 else 0
                tp3 = pos[8] if len(pos) > 8 else 0
                
                # Calculate P/L
                if action == "LONG":
                    pl_pct = ((current_price - entry_price) / entry_price) * 100
                    pl_color = "green" if pl_pct >= 0 else "red"
                else:
                    pl_pct = ((entry_price - current_price) / entry_price) * 100
                    pl_color = "green" if pl_pct >= 0 else "red"
                
                st.markdown("---")
                col1, col2, col3 = st.columns([3, 1, 1])
                
                with col1:
                    st.write(f"**{symbol}** ({market_type}) - {action}")
                    st.write(f"📥 Entry: `{entry_price:.5f}` | 📊 Current: `{current_price:.5f}`")
                    st.write(f"🛡️ SL: `{sl:.5f}` | 🎯 TP1: `{tp1:.5f}` | 🎯 TP2: `{tp2:.5f}` | 🎯 TP3: `{tp3:.5f}`")
                    st.write(f"💰 P/L: <span style='color:{pl_color}'>{pl_pct:.2f}%</span>", unsafe_allow_html=True)
                
                with col2:
                    if st.button("🔄", key=f"update_{symbol}"):
                        ticker = bot.data_provider.get_ticker(symbol)
                        if ticker and 'last' in ticker:
                            bot.db.update_position_current_price(symbol, ticker['last'])
                            st.success(f"Harga {symbol} diperbarui!")
                            st.session_state.positions_data = bot.get_active_positions()
                            st.rerun()
                
                with col3:
                    exit_price = st.number_input(
                        "Exit Price",
                        value=float(current_price),
                        step=0.0001,
                        key=f"exit_{symbol}"
                    )
                    if st.button("🔒 Tutup", key=f"close_{symbol}"):
                        if bot.close_position(pos_id, exit_price):
                            st.success(f"Posisi {symbol} ditutup!")
                            st.session_state.positions_data = bot.get_active_positions()
                            st.rerun()
                        else:
                            st.error("Gagal menutup posisi.")

    # ===============================
    # Tab 5: History
    # ===============================
    with tab5:
        st.subheader("📋 History Trading")
        
        if st.button("🔄 Refresh History", key="refresh_history"):
            st.session_state.history_data = bot.get_trade_history(20)
            st.success("History diperbarui!")
            st.rerun()
        
        if not st.session_state.history_data:
            st.info("📭 Tidak ada history trading.")
        else:
            st.write(f"**📊 Total Trade:** {len(st.session_state.history_data)}")
            
            for trade in st.session_state.history_data:
                trade_id = trade[0]
                symbol = trade[1]
                market_type = trade[2]
                action = trade[3]
                entry_price = trade[4]
                exit_price = trade[5]
                profit_loss = trade[6]
                trade_type = trade[7]
                timestamp = trade[8]
                
                color = "green" if profit_loss > 0 else "red"
                emoji = "✅" if profit_loss > 0 else "❌"
                
                st.markdown("---")
                st.write(f"{emoji} **{symbol}** ({market_type}) - {action} - {trade_type}")
                st.write(f"📥 Entry: `{entry_price:.5f}` | 📤 Exit: `{exit_price:.5f}`")
                st.write(f"💰 P/L: <span style='color:{color}'>{profit_loss:.5f}</span>", unsafe_allow_html=True)
                st.write(f"⏰ Waktu: {timestamp}")

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
                    symbol = pos[1]
                    entry_price = pos[4]
                    current_price = pos[11] if len(pos) > 11 else entry_price
                    
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

        if st.session_state.selected_analysis and isinstance(st.session_state.selected_analysis, dict):
            analysis = st.session_state.selected_analysis
            st.subheader("🤖 Enhanced Analysis")
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Base Score", analysis.get('base_score', analysis.get('score', 0)))
                if 'ml_confidence' in analysis:
                    st.metric("ML Confidence", f"{analysis.get('ml_confidence', 1.0):.2f}")
            with col2:
                st.metric("Final Score", analysis.get('final_score', analysis.get('score', 0)))
                st.metric("Action", analysis.get('action', 'NEUTRAL'))
            
            if 'risk_metrics' in analysis:
                st.subheader("📊 Risk Metrics")
                risk_cols = st.columns(3)
                with risk_cols[0]:
                    st.metric("Risk Category", analysis['risk_metrics']['risk_category'])
                    st.metric("Reward Ratio", f"{analysis['risk_metrics']['reward_ratio']:.2f}")
                with risk_cols[1]:
                    st.metric("Position Size", f"{analysis['risk_metrics']['optimal_position_size']:.1%}")
                with risk_cols[2]:
                    st.metric("Drawdown Risk", analysis['risk_metrics']['drawdown_risk'])

        if st.session_state.risk_assessments:
            st.subheader("⚖️ Risk Assessments")
            for symbol, assessment in st.session_state.risk_assessments.items():
                with st.expander(f"Risk Assessment for {symbol}"):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write(f"**Risk Category:** {assessment['risk_category']}")
                        st.write(f"**Volatility Level:** {assessment['volatility_level']}")
                    with col2:
                        st.write(f"**Optimal Position:** {assessment['optimal_position_size']:.1%}")
                        st.write(f"**Reward Ratio:** {assessment['reward_ratio']:.2f}")
                    st.info(f"**Recommendation:** {assessment['recommendation']}")

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

if __name__ == "__main__":
    main()
