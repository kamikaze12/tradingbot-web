import time
import asyncio
import streamlit as st
from dotenv import load_dotenv
import sys
import os

# Fix import path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

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

# ====================================
# Main App
# ====================================
def main():
    st.title("🤖 TradingBot Multi-Market Dashboard")
    
    try:
        bot = init_bot()
    except Exception as e:
        st.error(f"Error initializing bot: {e}")
        return

    # -------------------------------
    # Init session state
    # -------------------------------
    defaults = {
        "positions_data": [],
        "history_data": [],
        "scanned_results": [],
        "selected_analysis": None,
        "selected_for_entry": {},
        "custom_result": None,
        "pump_fun_results": [],
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
                    st.session_state.selected_analysis = None
                    st.session_state.selected_for_entry = {}
                    st.session_state.pump_fun_results = []
                    st.success(f"Mode {mode_choice} berhasil diatur!")
                    st.rerun()
                else:
                    st.error(f"Gagal mengatur mode {mode_choice}")
            except Exception as e:
                st.error(f"Error setting mode: {e}")

        if bot.mode:
            st.success(f"Mode: {bot.mode.upper()}")

    if not bot.mode:
        st.warning("Pilih market di sidebar!")
        return

    # -------------------------------
    # Tabs
    # -------------------------------
    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        ["Top Aset", "Analisis Aset", "Custom Entry", "Posisi Aktif", "History"]
    )

    # ===============================
    # Tab 1: Top Aset
    # ===============================
    with tab1:
        st.subheader("Scan Top Aset")

        # Tampilkan opsi scan khusus untuk crypto
        if bot.mode == "crypto":
            scan_option = st.radio("Pilih jenis scan:", ["Standard Crypto", "Pump Fun Tokens"], key="scan_option")
        else:
            scan_option = "Standard"
            st.info("Mode Standard untuk Forex dan Saham Indonesia")

        if st.button("Scan Aset", key="scan_assets"):
            with st.spinner("Scanning..."):
                try:
                    if bot.mode == "crypto" and scan_option == "Pump Fun Tokens":
                        # Scan Pump Fun tokens
                        st.session_state.pump_fun_results = asyncio.run(bot.scan_pump_fun(10))
                        if st.session_state.pump_fun_results:
                            st.success(f"Found {len(st.session_state.pump_fun_results)} Pump Fun tokens!")
                        else:
                            st.info("No Pump Fun tokens found.")
                    else:
                        # Standard scan dengan error handling
                        try:
                            st.session_state.scanned_results = bot.scan_potential_assets(50)
                            if st.session_state.scanned_results:
                                st.success(f"Found {len(st.session_state.scanned_results)} signals!")
                            else:
                                st.info("No signals found in this scan.")
                        except Exception as scan_error:
                            st.error(f"Scanning error: {str(scan_error)}")
                            st.session_state.scanned_results = []
                    st.rerun()
                except Exception as e:
                    st.error(f"Error during scanning: {str(e)}")
                    # Reset results on error
                    st.session_state.scanned_results = []
                    st.session_state.pump_fun_results = []

        # Tampilkan hasil scan Pump Fun
        if st.session_state.pump_fun_results and bot.mode == "crypto" and scan_option == "Pump Fun Tokens":
            st.subheader("🚀 Pump Fun Tokens Baru")
            
            for i, token in enumerate(st.session_state.pump_fun_results, 1):
                col1, col2, col3 = st.columns([3, 2, 1])
                
                with col1:
                    st.write(f"**{i}. {token['symbol']}**")
                    st.write(f"Address: `{token['address'][:10]}...`")
                    if token.get('pair_url'):
                        st.write(f"[View on DexScreener]({token['pair_url']})")
                
                with col2:
                    st.write(f"Price: ${token['price_usd']:.6f}")
                    st.write(f"Volume 24h: ${token['volume_24h']:,.2f}")
                    st.write(f"Liquidity: ${token['liquidity']:,.2f}")
                
                with col3:
                    if st.button(f"Analisis", key=f"analyze_pump_{token['symbol']}"):
                        st.session_state.selected_analysis = {
                            'symbol': token['symbol'],
                            'current_price': token['price_usd'],
                            'action': 'NEUTRAL',
                            'score': 0,
                            'volume': token['volume_24h']
                        }
                        st.rerun()

        # Tampilkan hasil scan standard
        if st.session_state.scanned_results:
            st.subheader("Top Aset Potensial:")

            for i, res in enumerate(st.session_state.scanned_results, 1):
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.write(f"{i}. **{res['symbol']}** - {res['action']} (Score: {res.get('score', 'N/A')})")
                    
                    # Format TP levels dengan urutan yang benar
                    if res['action'] == "LONG":
                        st.write(f"Entry: {res['entry_low']:.5f} - {res['entry_high']:.5f}")
                        st.write(f"SL: {res['sl']:.5f}")
                        st.write(f"TP1: {res['tp1']:.5f} | TP2: {res['tp2']:.5f} | TP3: {res['tp3']:.5f}")
                    else:  # SHORT
                        st.write(f"Entry: {res['entry_low']:.5f} - {res['entry_high']:.5f}")
                        st.write(f"SL: {res['sl']:.5f}")
                        st.write(f"TP1: {res['tp1']:.5f} | TP2: {res['tp2']:.5f} | TP3: {res['tp3']:.5f}")
                        
                with col2:
                    if st.button(f"Pilih {i}", key=f"select_{res['symbol']}"):
                        st.session_state.selected_for_entry[res['symbol']] = res
                        st.success(f"Selected {res['symbol']}!")
                        st.rerun()

    # ===============================
    # Tab 2: Analisis Aset
    # ===============================
    with tab2:
        st.subheader("Analisis Aset Spesifik")
        
        symbol_to_analyze = st.text_input("Masukkan simbol aset:", key="analyze_symbol")
        
        if st.button("Analisis Sekarang", key="analyze_btn"):
            if symbol_to_analyze:
                with st.spinner("Menganalisis..."):
                    try:
                        analysis = bot.analyze_asset(symbol_to_analyze)
                        if analysis:
                            st.session_state.selected_analysis = analysis
                            st.success(f"Analisis untuk {symbol_to_analyze} selesai!")
                        else:
                            st.error(f"Tidak dapat menganalisis {symbol_to_analyze}")
                    except Exception as e:
                        st.error(f"Error analyzing {symbol_to_analyze}: {e}")
            else:
                st.warning("Masukkan simbol aset terlebih dahulu.")
        
        if st.session_state.selected_analysis:
            analysis = st.session_state.selected_analysis
            st.subheader(f"Hasil Analisis untuk {analysis['symbol']}")
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Aksi", analysis['action'])
                st.metric("Skor Total", analysis.get('score', 'N/A'))
                st.metric("Harga Saat Ini", f"{analysis['current_price']:.5f}")
            
            with col2:
                st.metric("RSI", f"{analysis.get('rsi', 'N/A'):.2f}")
                st.metric("ATR", f"{analysis.get('atr', 'N/A'):.5f}")
                st.metric("Volume Ratio", f"{analysis.get('volume_ratio', 'N/A'):.2f}")

    # ===============================
    # Tab 3: Custom Entry
    # ===============================
    with tab3:
        st.subheader("Custom Entry")
        
        symbol_custom = st.text_input("Masukkan simbol aset:", key="custom_symbol")
        entry_price_custom = st.number_input("Harga Entry:", value=0.0, step=0.0001, key="custom_entry")
        
        if st.button("Hitung TP/SL", key="calculate_custom"):
            if symbol_custom and entry_price_custom > 0:
                with st.spinner("Menghitung..."):
                    try:
                        result = bot.calculate_custom_entry(symbol_custom, entry_price_custom)
                        if result:
                            st.session_state.custom_result = result
                            st.success("Perhitungan selesai!")
                        else:
                            st.error("Tidak dapat menghitung TP/SL.")
                    except Exception as e:
                        st.error(f"Error calculating TP/SL: {e}")
            else:
                st.warning("Masukkan simbol dan harga entry yang valid.")
        
        if st.session_state.custom_result:
            result = st.session_state.custom_result
            st.subheader(f"Hasil untuk {result['symbol']}")
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Entry Price", f"{result['entry_price']:.5f}")
                st.metric("TP1", f"{result['tp1']:.5f}")
                st.metric("TP2", f"{result['tp2']:.5f}")
            
            with col2:
                st.metric("TP3", f"{result['tp3']:.5f}")
                st.metric("SL", f"{result['sl']:.5f}")

    # ===============================
    # Tab 4: Posisi Aktif
    # ===============================
    with tab4:
        st.subheader("Posisi Aktif")
        
        if st.button("Refresh Posisi", key="refresh_positions"):
            try:
                st.session_state.positions_data = bot.get_active_positions()
                st.success("Posisi diperbarui!")
                st.rerun()
            except Exception as e:
                st.error(f"Error refreshing positions: {e}")
        
        if not st.session_state.positions_data:
            st.info("Tidak ada posisi aktif.")
        else:
            st.write(f"Total Posisi Aktif: {len(st.session_state.positions_data)}")
            
            for pos in st.session_state.positions_data:
                pos_id = pos[0]
                symbol = pos[1]
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
                else:  # SHORT
                    pl_pct = ((entry_price - current_price) / entry_price) * 100
                pl_color = "green" if pl_pct >= 0 else "red"
                
                st.markdown("---")
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    st.write(f"**{symbol}** - {action}")
                    st.write(f"Entry: `{entry_price:.5f}` | Current: `{current_price:.5f}`")
                    st.write(f"SL: `{sl:.5f}`")
                    st.write(f"TP1: `{tp1:.5f}` | TP2: `{tp2:.5f}` | TP3: `{tp3:.5f}`")
                    st.write(f"P/L: <span style='color:{pl_color}'>{pl_pct:.2f}%</span>", unsafe_allow_html=True)

                with col2:
                    exit_price = st.number_input(
                        "Exit Price",
                        value=float(current_price),
                        step=0.0001,
                        key=f"exit_{symbol}"
                    )
                    if st.button("Tutup", key=f"close_{symbol}"):
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
        st.subheader("History Trading")
        
        if st.button("Refresh History", key="refresh_history"):
            try:
                st.session_state.history_data = bot.get_trade_history(20)
                st.success("History diperbarui!")
                st.rerun()
            except Exception as e:
                st.error(f"Error refreshing history: {e}")
        
        if not st.session_state.history_data:
            st.info("Tidak ada history trading.")
        else:
            st.write(f"Total Trade: {len(st.session_state.history_data)}")
            
            for trade in st.session_state.history_data:
                symbol = trade[1]
                action = trade[3]
                entry_price = trade[4]
                exit_price = trade[5]
                profit_loss = trade[6]
                timestamp = trade[8]
                
                color = "green" if profit_loss > 0 else "red"
                emoji = "✅" if profit_loss > 0 else "❌"
                
                st.markdown("---")
                st.write(f"{emoji} **{symbol}** - {action}")
                st.write(f"Entry: `{entry_price:.5f}` | Exit: `{exit_price:.5f}`")
                st.write(f"P/L: <span style='color:{color}'>{profit_loss:.5f}</span>", unsafe_allow_html=True)
                st.write(f"Waktu: {timestamp}")


if __name__ == "__main__":
    main()
