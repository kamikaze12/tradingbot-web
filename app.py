import time
import asyncio
import threading
import schedule
import streamlit as st
from dotenv import load_dotenv
import sys
import os

# Add the parent directory to Python path to fix import issues
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot.core import TradingBot

# ====================================
# Setup
# ====================================
load_dotenv()
st.set_page_config(page_title="TradingBot Web", layout="wide")


@st.cache_resource
def init_bot():
    """Inisialisasi TradingBot (cached)."""
    return TradingBot()


def run_scheduler(bot):
    """Jalankan auto scan tiap 30 detik."""
    def scan_job():
        if bot.mode:
            try:
                results = bot.scan_potential_assets(10)
                if results:
                    st.session_state['latest_results'] = results[:5]
                    st.rerun()
            except Exception as e:
                print(f"Scheduler error: {e}")

    schedule.every(30).seconds.do(scan_job)
    while True:
        schedule.run_pending()
        time.sleep(1)


# ====================================
# Main App
# ====================================
def main():
    st.title("🤖 TradingBot Multi-Market Dashboard")
    
    try:
        bot = init_bot()
    except Exception as e:
        st.error(f"Error initializing bot: {e}")
        st.info("Please check if all dependencies are installed and environment variables are set.")
        return

    # -------------------------------
    # Init session state
    # -------------------------------
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
        "selected_for_entry": {},  # Menyimpan simbol yang dipilih untuk entry
        "custom_result": None,
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val

    # -------------------------------
    # Sidebar: pilih market
    # -------------------------------
    with st.sidebar:
        st.header("Pilih Market")
        mode_choice = st.selectbox("Market:", ["Crypto", "Forex", "Saham Indonesia"], key="mode")

        if st.button("Set Market"):
            try:
                if mode_choice == "Crypto":
                    success = bot.set_mode("crypto")
                elif mode_choice == "Forex":
                    success = bot.set_mode("forex")
                elif mode_choice == "Saham Indonesia":
                    success = bot.set_mode("saham_id")
                else:
                    success = False

                if success:
                    st.session_state.scanned_results = []
                    st.session_state.selected_symbols = []
                    st.session_state.selected_analysis = None
                    st.session_state.selected_for_entry = {}
                    st.success(f"Mode {mode_choice} berhasil diatur!")
                    st.rerun()
                else:
                    st.error(f"Gagal mengatur mode {mode_choice}")
            except Exception as e:
                st.error(f"Error setting mode: {e}")

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
                    st.error(f"Error refreshing data: {e}")

    if not bot.mode:
        st.warning("Pilih market di sidebar!")
        return

    # -------------------------------
    # Tabs
    # -------------------------------
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(
        ["Top Aset", "Analisis Aset", "Custom Entry", "Posisi Aktif", "History", "Live Scanner"]
    )

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
                try:
                    if bot.mode == "crypto" and scan_option == "Pump Fun Solana":
                        results = asyncio.run(bot.scan_pump_fun())
                        if results:
                            st.subheader("Token Baru di Pump Fun:")
                            for res in results:
                                st.write(f"**{res['symbol']}** - Price: {res['ticker']['last']}, "
                                         f"Volume: {res['ticker']['volume']}")
                                if st.button(f"Pilih {res['symbol']}", key=f"select_pump_{res['symbol']}"):
                                    st.session_state.selected_for_entry[res['symbol']] = res
                                    st.success(f"Selected {res['symbol']}!")
                                    st.rerun()
                        else:
                            st.info("Tidak ada token baru di Pump Fun.")

                    else:
                        st.session_state.scanned_results = bot.scan_potential_assets(50)
                        st.rerun()
                except Exception as e:
                    st.error(f"Error during scanning: {e}")

        # Tampilkan hasil scan
        if st.session_state.scanned_results:
            st.subheader("Top Aset Potensial:")

            for i, res in enumerate(st.session_state.scanned_results, 1):
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.write(f"{i}. **{res['symbol']}** - {res['action']} (Score: {res.get('score', 'N/A')})")
                    
                    # Format TP levels correctly based on action
                    if res['action'] == "LONG":
                        st.write(f"Entry Range: {res['entry_low']:.5f} - {res['entry_high']:.5f} | "
                                 f"SL: {res['sl']:.5f}")
                        # Show TP in correct order: TP1 < TP2 < TP3
                        st.write(f"TP1: {res['tp1']:.5f} | TP2: {res['tp2']:.5f} | TP3: {res['tp3']:.5f}")
                    else:  # SHORT
                        st.write(f"Entry Range: {res['entry_low']:.5f} - {res['entry_high']:.5f} | "
                                 f"SL: {res['sl']:.5f}")
                        # For SHORT, TP1 > TP2 > TP3
                        st.write(f"TP1: {res['tp1']:.5f} | TP2: {res['tp2']:.5f} | TP3: {res['tp3']:.5f}")
                    
                    # Tampilkan pola yang terdeteksi
                    if 'detected_patterns' in res and res['detected_patterns']:
                        st.write(f"📊 **Pola Terdeteksi:** {', '.join(res['detected_patterns'])}")
                    
                    # Tampilkan pattern score
                    if 'pattern_score' in res:
                        st.write(f"⭐ **Pattern Score:** {res['pattern_score']}")
                        
                with col2:
                    if st.button(f"Pilih {i}", key=f"select_{res['symbol']}"):
                        st.session_state.selected_for_entry[res['symbol']] = res
                        st.success(f"Selected {res['symbol']}!")
                        st.rerun()

            # Tampilkan input entry untuk setiap simbol yang dipilih
            for symbol, analysis in st.session_state.selected_for_entry.items():
                st.markdown("---")
                st.subheader(f"📈 Input Entry untuk {symbol}")
                
                col1, col2 = st.columns([2, 1])
                with col1:
                    entry_price = st.number_input(
                        "Entry Price",
                        value=analysis.get("ideal_entry", analysis.get("current_price", 0)),
                        step=0.001,
                        key=f"entry_{symbol}"
                    )
                
                with col2:
                    if st.button(f"✅ Tambah Posisi {symbol}", key=f"add_{symbol}"):
                        try:
                            # Calculate TP and SL based on entry price and action
                            if analysis["action"] == "LONG":
                                tp1 = entry_price + (analysis["tp1"] - analysis["ideal_entry"])
                                tp2 = entry_price + (analysis["tp2"] - analysis["ideal_entry"])
                                tp3 = entry_price + (analysis["tp3"] - analysis["ideal_entry"])
                                sl = entry_price - (analysis["ideal_entry"] - analysis["sl"])
                            else:  # SHORT
                                tp1 = entry_price - (analysis["ideal_entry"] - analysis["tp1"])
                                tp2 = entry_price - (analysis["ideal_entry"] - analysis["tp2"])
                                tp3 = entry_price - (analysis["ideal_entry"] - analysis["tp3"])
                                sl = entry_price + (analysis["sl"] - analysis["ideal_entry"])
                            
                            position_id = bot.db.save_position(
                                symbol=symbol,
                                market_type=bot.mode,
                                action=analysis["action"],
                                entry_price=entry_price,
                                tp1=tp1,
                                tp2=tp2,
                                tp3=tp3,
                                sl=sl,
                                entry_low=entry_price * (1 - bot.strategy.entry_range_pct),
                                entry_high=entry_price * (1 + bot.strategy.entry_range_pct),
                            )
                            if position_id:
                                st.success(f"Posisi {symbol} ditambahkan!")
                                st.session_state.positions_data = bot.get_active_positions()
                                st.session_state.selected_positions.append(symbol)
                                # Hapus dari selected_for_entry setelah berhasil ditambahkan
                                if symbol in st.session_state.selected_for_entry:
                                    del st.session_state.selected_for_entry[symbol]
                                st.rerun()
                            else:
                                st.error("Gagal tambah posisi.")
                        except Exception as e:
                            st.error(f"Error adding position: {e}")
                
                # Tampilkan detail pola untuk analisis yang dipilih
                if 'pattern_details' in analysis:
                    with st.expander("🔍 Detail Pola Teknikal"):
                        pattern_details = analysis['pattern_details']
                        col1, col2 = st.columns(2)
                        with col1:
                            st.write("**✅ Pola Terdeteksi:**")
                            for pattern, detected in pattern_details.items():
                                if detected:
                                    st.write(f"🎯 {pattern}")
                        with col2:
                            st.write("**❌ Pola Tidak Terdeteksi:**")
                            for pattern, detected in pattern_details.items():
                                if not detected:
                                    st.write(f"⚪ {pattern}")
                
                # Tombol untuk menghapus pilihan
                if st.button(f"🗑️ Hapus {symbol} dari pilihan", key=f"remove_{symbol}"):
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
                    st.error(f"Error deleting signals: {e}")

        # --- Auto Rescan
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
                    st.write(f"**{res['symbol']}** - {res['action']} (Score: {res.get('score', 'N/A')})")
                    if 'detected_patterns' in res and res['detected_patterns']:
                        st.write(f"📊 Pola: {', '.join(res['detected_patterns'])}")

    # ===============================
    # Tab 2: Analisis Aset
    # ===============================
    with tab2:
        st.subheader("🔍 Analisis Aset Spesifik")
        
        # Input untuk simbol tertentu
        symbol_to_analyze = st.text_input("Masukkan simbol aset:", key="analyze_symbol")
        
        col1, col2 = st.columns([2, 1])
        with col1:
            if st.button("🚀 Analisis Sekarang", key="analyze_btn"):
                if symbol_to_analyze:
                    with st.spinner("Menganalisis..."):
                        try:
                            analysis = bot.analyze_asset(symbol_to_analyze)
                            if analysis:
                                st.session_state.selected_analysis = analysis
                                st.success(f"Analisis untuk {symbol_to_analyze} selesai!")
                            else:
                                st.error(f"Tidak dapat menganalisis {symbol_to_analyze} atau sinyal tidak cukup kuat.")
                        except Exception as e:
                            st.error(f"Error analyzing {symbol_to_analyze}: {e}")
                else:
                    st.warning("Masukkan simbol aset terlebih dahulu.")
        
        # Tampilkan hasil analisis
        if st.session_state.selected_analysis:
            analysis = st.session_state.selected_analysis
            st.subheader(f"📊 Hasil Analisis untuk {analysis['symbol']}")
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric("🎯 Aksi", analysis['action'])
                st.metric("⭐ Skor Total", analysis.get('score', 'N/A'))
                st.metric("💰 Harga Saat Ini", f"{analysis['current_price']:.5f}")
                st.metric("📈 RSI", f"{analysis.get('rsi', 'N/A'):.2f}")
                st.metric("📊 Pattern Score", analysis.get('pattern_score', 'N/A'))
            
            with col2:
                st.metric("📈 Trend", analysis.get('trend', 'N/A'))
                st.metric("🔊 Volume Ratio", f"{analysis.get('volume_ratio', 'N/A'):.2f}")
                st.metric("📏 ATR", f"{analysis.get('atr', 'N/A'):.5f}")
                st.metric("📶 EMA Trend", analysis.get('ema_trend', 'N/A'))
                st.metric("🎯 EMA Score", analysis.get('ema_score', 'N/A'))
            
            # Tampilkan pola yang terdeteksi
            if 'detected_patterns' in analysis and analysis['detected_patterns']:
                st.subheader("📊 Pola Teknikal Terdeteksi")
                st.write(f"**Pola:** {', '.join(analysis['detected_patterns'])}")
            
            # Detail pola
            if 'pattern_details' in analysis:
                with st.expander("🔍 Detail Semua Pola"):
                    pattern_details = analysis['pattern_details']
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write("**✅ Terdeteksi:**")
                        for pattern, detected in pattern_details.items():
                            if detected:
                                st.write(f"🎯 {pattern}")
                    with col2:
                        st.write("**❌ Tidak Terdeteksi:**")
                        for pattern, detected in pattern_details.items():
                            if not detected:
                                st.write(f"⚪ {pattern}")
            
            # Input untuk entry price dan tombol untuk menambahkan ke posisi
            st.markdown("---")
            st.subheader("🎯 Tambah ke Posisi Aktif")
            
            entry_price = st.number_input(
                "Harga Entry",
                value=analysis.get('ideal_entry', analysis['current_price']),
                step=0.001,
                key=f"entry_analysis_{analysis['symbol']}"
            )
            
            if st.button("✅ Tambahkan ke Posisi Aktif", key=f"add_analysis_{analysis['symbol']}"):
                try:
                    # Calculate TP and SL based on the entry price and the analysis
                    if analysis["action"] == "LONG":
                        tp1 = entry_price + (analysis["tp1"] - analysis["ideal_entry"])
                        tp2 = entry_price + (analysis["tp2"] - analysis["ideal_entry"])
                        tp3 = entry_price + (analysis["tp3"] - analysis["ideal_entry"])
                        sl = entry_price - (analysis["ideal_entry"] - analysis["sl"])
                    else:  # SHORT
                        tp1 = entry_price - (analysis["ideal_entry"] - analysis["tp1"])
                        tp2 = entry_price - (analysis["ideal_entry"] - analysis["tp2"])
                        tp3 = entry_price - (analysis["ideal_entry"] - analysis["tp3"])
                        sl = entry_price + (analysis["sl"] - analysis["ideal_entry"])
                    
                    position_id = bot.db.save_position(
                        symbol=analysis['symbol'],
                        market_type=bot.mode,
                        action=analysis["action"],
                        entry_price=entry_price,
                        tp1=tp1,
                        tp2=tp2,
                        tp3=tp3,
                        sl=sl,
                        entry_low=entry_price * (1 - bot.strategy.entry_range_pct),
                        entry_high=entry_price * (1 + bot.strategy.entry_range_pct),
                    )
                    if position_id:
                        st.success(f"Posisi {analysis['symbol']} ditambahkan!")
                        # Refresh positions data
                        st.session_state.positions_data = bot.get_active_positions()
                        st.rerun()
                    else:
                        st.error("Gagal tambah posisi.")
                except Exception as e:
                    st.error(f"Error adding position: {e}")

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
                    try:
                        result = bot.calculate_custom_entry(symbol_custom, entry_price_custom)
                        if result:
                            st.session_state.custom_result = result
                            st.success("Perhitungan selesai!")
                        else:
                            st.error("Tidak dapat menghitung TP/SL. Pastikan simbol valid.")
                    except Exception as e:
                        st.error(f"Error calculating TP/SL: {e}")
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
                risk_reward = (result['tp1'] - result['entry_price']) / (result['entry_price'] - result['sl']) if result['entry_price'] > result['sl'] else 0
                st.metric("📊 Risk/Reward", f"{risk_reward:.2f}")
            
            # Tombol untuk menambahkan ke posisi
            if st.button("✅ Tambahkan ke Posisi Aktif", key="add_custom"):
                try:
                    position_id = bot.db.save_position(
                        symbol=result['symbol'],
                        market_type=bot.mode,
                        action="LONG",  # Default action untuk custom entry
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
                except Exception as e:
                    st.error(f"Error adding position: {e}")

    # ===============================
    # Tab 4: Posisi Aktif
    # ===============================
    with tab4:
        st.subheader("📊 Posisi Aktif")
        
        # Refresh positions data
        if st.button("🔄 Refresh Posisi", key="refresh_positions"):
            try:
                st.session_state.positions_data = bot.get_active_positions()
                st.success("Posisi diperbarui!")
                st.rerun()
            except Exception as e:
                st.error(f"Error refreshing positions: {e}")
        
        if not st.session_state.positions_data:
            st.info("📭 Tidak ada posisi aktif.")
        else:
            st.write(f"**📈 Total Posisi Aktif:** {len(st.session_state.positions_data)}")
            
            for pos in st.session_state.positions_data:
                # Unpack position data
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
                else:  # SHORT
                    pl_pct = ((entry_price - current_price) / entry_price) * 100
                    pl_color = "green" if pl_pct >= 0 else "red"
                
                st.markdown("---")
                col1, col2, col3 = st.columns([3, 1, 1])
                
                with col1:
                    st.write(f"**{symbol}** ({market_type}) - {action}")
                    st.write(f"📥 Entry: `{entry_price:.5f}` | 📊 Current: `{current_price:.5f}`")
                    
                    # Display TP levels in correct order
                    if action == "LONG":
                        st.write(f"🛡️ SL: `{sl:.5f}` | 🎯 TP1: `{tp1:.5f}` | 🎯 TP2: `{tp2:.5f}` | 🎯 TP3: `{tp3:.5f}`")
                    else:  # SHORT
                        st.write(f"🛡️ SL: `{sl:.5f}` | 🎯 TP1: `{tp1:.5f}` | 🎯 TP2: `{tp2:.5f}` | 🎯 TP3: `{tp3:.5f}`")
                    
                    st.write(f"💰 P/L: <span style='color:{pl_color}'>{pl_pct:.2f}%</span>", unsafe_allow_html=True)
                
                with col2:
                    # Update current price
                    if st.button("🔄", key=f"update_{symbol}"):
                        try:
                            ticker = bot.data_provider.get_ticker(symbol)
                            if ticker and 'last' in ticker:
                                bot.db.update_position_current_price(symbol, ticker['last'])
                                st.success(f"Harga {symbol} diperbarui!")
                                st.session_state.positions_data = bot.get_active_positions()
                                st.rerun()
                        except Exception as e:
                            st.error(f"Error updating price: {e}")
                
                with col3:
                    # Close position
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
                            st.error(f"Error closing position: {e}")

    # ===============================
    # Tab 5: History
    # ===============================
    with tab5:
        st.subheader("📋 History Trading")
        
        # Refresh history data
        if st.button("🔄 Refresh History", key="refresh_history"):
            try:
                st.session_state.history_data = bot.get_trade_history(20)
                st.success("History diperbarui!")
                st.rerun()
            except Exception as e:
                st.error(f"Error refreshing history: {e}")
        
        if not st.session_state.history_data:
            st.info("📭 Tidak ada history trading.")
        else:
            st.write(f"**📊 Total Trade:** {len(st.session_state.history_data)}")
            
            for trade in st.session_state.history_data:
                # Unpack trade data
                trade_id = trade[0]
                symbol = trade[1]
                market_type = trade[2]
                action = trade[3]
                entry_price = trade[4]
                exit_price = trade[5]
                profit_loss = trade[6]
                trade_type = trade[7]
                timestamp = trade[8]
                
                # Determine color based on profit/loss
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
        
        # Start/stop live monitoring
        if st.button("🚀 Mulai Live Monitoring" if not st.session_state.live_monitoring else "⏹️ Hentikan Live Monitoring"):
            st.session_state.live_monitoring = not st.session_state.live_monitoring
            st.rerun()
        
        if st.session_state.live_monitoring:
            st.info("📡 Live monitoring aktif. Harga akan diperbarui setiap 30 detik.")
            
            # Display current positions with live prices
            if st.session_state.positions_data:
                st.subheader("📊 Posisi Aktif - Live")
                for pos in st.session_state.positions_data:
                    symbol = pos[1]
                    entry_price = pos[4]
                    current_price = pos[11] if len(pos) > 11 else entry_price
                    
                    # Get latest price
                    try:
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
                        st.error(f"Error getting live price for {symbol}: {e}")
            
            # Auto refresh checkbox
            st_auto_refresh = st.checkbox("🔄 Auto Refresh (30s)")
            if st_auto_refresh:
                time.sleep(30)
                st.rerun()
                
            # Manual refresh button
            if st.button("🔄 Refresh Sekarang"):
                st.rerun()
                
        else:
            st.info("👉 Klik 'Mulai Live Monitoring' untuk memantau harga real-time.")


# ====================================
# Entry Point
# ====================================
if __name__ == "__main__":
    main()
