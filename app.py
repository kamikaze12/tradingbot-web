import time
import asyncio
import threading
import schedule
import streamlit as st
from dotenv import load_dotenv

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
            results = bot.scan_potential_assets(10)
            if results:
                st.session_state['latest_results'] = results[:5]
                st.rerun()

    schedule.every(30).seconds.do(scan_job)
    while True:
        schedule.run_pending()
        time.sleep(1)


# ====================================
# Main App
# ====================================
def main():
    st.title("🤖 TradingBot Multi-Market Dashboard")
    bot = init_bot()

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

        # Tampilkan hasil scan
        if st.session_state.scanned_results:
            st.subheader("Top Aset Potensial:")

            for i, res in enumerate(st.session_state.scanned_results, 1):
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
                        value=analysis["ideal_entry"],
                        step=0.001,
                        key=f"entry_{symbol}"
                    )
                
                with col2:
                    if st.button(f"✅ Tambah Posisi {symbol}", key=f"add_{symbol}"):
                        position_id = bot.db.save_position(
                            symbol=symbol,
                            market_type=bot.mode,
                            action=analysis["action"],
                            entry_price=entry_price,
                            tp1=entry_price + (analysis["tp1"] - analysis["ideal_entry"]),
                            tp2=entry_price + (analysis["tp2"] - analysis["ideal_entry"]),
                            tp3=entry_price + (analysis["tp3"] - analysis["ideal_entry"]),
                            sl=entry_price - (analysis["ideal_entry"] - analysis["sl"]),
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
                    st.write(f"**{res['symbol']}** - {res['action']} (Score: {res['score']})")
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
                        analysis = bot.analyze_asset(symbol_to_analyze)
                        if analysis:
                            st.session_state.selected_analysis = analysis
                            st.success(f"Analisis untuk {symbol_to_analyze} selesai!")
                        else:
                            st.error(f"Tidak dapat menganalisis {symbol_to_analyze} atau sinyal tidak cukup kuat.")
                else:
                    st.warning("Masukkan simbol aset terlebih dahulu.")
        
        # Tampilkan hasil analisis
        if st.session_state.selected_analysis:
            analysis = st.session_state.selected_analysis
            st.subheader(f"📊 Hasil Analisis untuk {analysis['symbol']}")
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric("🎯 Aksi", analysis['action'])
                st.metric("⭐ Skor Total", analysis['score'])
                st.metric("💰 Harga Saat Ini", f"{analysis['current_price']:.5f}")
                st.metric("📈 RSI", f"{analysis['rsi']:.2f}")
                st.metric("📊 Pattern Score", analysis.get('pattern_score', 0))
            
            with col2:
                st.metric("📈 Trend", analysis['trend'])
                st.metric("🔊 Volume Ratio", f"{analysis['volume_ratio']:.2f}")
                st.metric("📏 ATR", f"{analysis['atr']:.5f}")
                st.metric("📶 EMA Trend", analysis['ema_trend'])
                st.metric("🎯 EMA Score", analysis['ema_score'])
            
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
                # Calculate TP and SL based on the entry price and the analysis
                position_id = bot.db.save_position(
                    symbol=analysis['symbol'],
                    market_type=bot.mode,
                    action=analysis["action"],
                    entry_price=entry_price,
                    tp1=entry_price + (analysis["tp1"] - analysis["ideal_entry"]),
                    tp2=entry_price + (analysis["tp2"] - analysis["ideal_entry"]),
                    tp3=entry_price + (analysis["tp3"] - analysis["ideal_entry"]),
                    sl=entry_price - (analysis["ideal_entry"] - analysis["sl"]),
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
                st.metric("📊 Risk/Reward", f"{(result['tp1'] - result['entry_price']) / (result['entry_price'] - result['sl']):.2f}")
            
            # Tombol untuk menambahkan ke posisi
            if st.button("✅ Tambahkan ke Posisi Aktif", key="add_custom"):
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

    # ===============================
    # Tab 4: Posisi Aktif
    # ===============================
    with tab4:
        st.subheader("📊 Posisi Aktif")
        
        # Refresh positions data
        if st.button("🔄 Refresh Posisi", key="refresh_positions"):
            st.session_state.positions_data = bot.get_active_positions()
            st.success("Posisi diperbarui!")
            st.rerun()
        
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
                
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.write(f"**{symbol}** ({market_type}) - {action}")
                    st.write(f"Entry: {entry_price:.5f} | Current: {current_price:.5f}")
                    st.write(f"SL: {sl:.5f} | TP1: {tp1:.5f} | TP2: {tp2:.5f} | TP3: {tp3:.5f}")
                
                with col2:
                    if st.button(f"❌ Tutup {symbol}", key=f"close_{pos_id}"):
                        bot.db.close_position(pos_id)
                        st.success(f"Posisi {symbol} ditutup!")
                        st.session_state.positions_data = bot.get_active_positions()
                        st.rerun()

    # ===============================
    # Tab 5: History
    # ===============================
    with tab5:
        st.subheader("📜 Trade History")
        
        if st.button("🔄 Refresh History", key="refresh_history"):
            st.session_state.history_data = bot.get_trade_history()
            st.success("History diperbarui!")
            st.rerun()
        
        if not st.session_state.history_data:
            st.info("📭 Tidak ada history trading.")
        else:
            st.write(f"**📊 Total Transaksi:** {len(st.session_state.history_data)}")
            
            for hist in st.session_state.history_data:
                hist_id = hist[0]
                symbol = hist[1]
                action = hist[2]
                entry_price = hist[3]
                exit_price = hist[4]
                pnl = hist[6]
                closed_at = hist[7]
                
                st.write(f"**{symbol}** - {action} | Entry: {entry_price:.5f} | Exit: {exit_price:.5f} "
                         f"| PnL: {pnl:.2f} | Closed At: {closed_at}")

    # ===============================
    # Tab 6: Live Scanner
    # ===============================
    with tab6:
        st.subheader("📡 Live Market Monitoring")
        
        if st.button("▶️ Mulai Monitoring", key="start_monitor"):
            st.session_state.live_monitoring = True
            st.success("Live monitoring dimulai!")
            st.rerun()
        
        if st.button("⏹️ Stop Monitoring", key="stop_monitor"):
            st.session_state.live_monitoring = False
            st.success("Live monitoring dihentikan!")
            st.rerun()
        
        if st.session_state.live_monitoring:
            with st.spinner("🔄 Memantau pasar..."):
                live_results = bot.live_monitor()
                if live_results:
                    st.subheader("🔥 Peluang Terbaru:")
                    for res in live_results:
                        st.write(f"**{res['symbol']}** - {res['action']} (Score: {res['score']})")
                else:
                    st.info("Tidak ada peluang baru saat ini.")


if __name__ == "__main__":
    main()
