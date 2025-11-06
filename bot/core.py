import time
import asyncio
import threading
import schedule
import streamlit as st
import pandas as pd
from dotenv import load_dotenv

try:
    import plotly.graph_objects as go
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False
    st.warning("Plotly not available. Install with: pip install plotly")

from bot.core import TradingBot

load_dotenv()
st.set_page_config(page_title="TradingBot Pro", layout="wide")

@st.cache_resource
def init_bot():
    return TradingBot()

def run_scheduler(bot):
    def scan_job():
        if bot.mode:
            results = bot.scan_potential_assets(10)
            if results:
                st.session_state['latest_results'] = results[:5]

    schedule.every(30).seconds.do(scan_job)
    while True:
        schedule.run_pending()
        time.sleep(1)

def main():
    st.title("TradingBot Pro - Enhanced Dashboard")
    bot = init_bot()

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

    with st.sidebar:
        st.header("Market Selection")
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

            if st.button("Refresh Semua Data", key="refresh_all"):
                st.session_state.positions_data = bot.get_active_positions()
                st.session_state.history_data = bot.get_trade_history()
                st.session_state.last_refresh = {"positions": time.time(), "history": time.time()}
                st.success("Data berhasil direfresh!")
                st.rerun()

    if not bot.mode:
        st.warning("Pilih market di sidebar!")
        return

    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
        "Top Aset", "Analisis Aset", "Custom Entry", "Posisi Aktif", 
        "History", "Live Scanner", "ML Backtest", "Portfolio"
    ])

    with tab1:
        st.subheader("Scan Top Aset")

        if bot.mode == "crypto":
            scan_option = st.radio("Pilih jenis scan:", ["Standard Crypto", "Pump Fun Solana"])
        else:
            scan_option = "Standard"
            st.info("Mode Standard untuk Forex dan Saham Indonesia")

        if st.button("Scan Aset", key="scan_assets"):
            with st.spinner("Scanning 100 aset..."):
                fallback_count = 0
                all_results = bot.scan_potential_assets(100)  # Scan 100 koin
                if all_results:
                    all_results.sort(key=lambda x: abs(x.get('score', 0)), reverse=True)
                    st.session_state.scanned_results = all_results[:10]  # Tampil 10 terbaik
                    st.success("Scan selesai! Menampilkan 10 terbaik dari 100.")
                else:
                    st.warning("Tidak ada hasil scan dari metode utama. Mencoba fallback dengan aset populer.")
                    fallback_assets = bot.get_popular_assets(100)
                    fallback_results = []
                    for asset in fallback_assets:
                        for attempt in range(3):  # NEW: Retry 3x untuk avoid rate limit
                            analysis = bot.analyze_asset(asset)
                            if analysis:
                                fallback_results.append(analysis)
                                break
                            else:
                                time.sleep(1)  # Delay 1s per retry
                                print(f"Retry {attempt+1} for {asset}")
                        if not analysis:
                            ticker = bot.data_provider.get_ticker(asset)
                            if ticker and 'last' in ticker:
                                current_price = ticker['last']
                                percentage = ticker.get('percentage', 0)
                                volume = ticker.get('volume', 1.0)
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
                                fallback_count += 1
                            else:
                                st.warning(f"Gagal mengambil data untuk {asset}")
                    if fallback_results:
                        fallback_results.sort(key=lambda x: abs(x.get('score', 0)), reverse=True)
                        st.session_state.scanned_results = fallback_results[:10]
                        st.info(f"Fallback selesai! Total fallback: {fallback_count}. Menampilkan 10 terbaik.")
                    else:
                        st.error("Tidak ada data sama sekali. Periksa koneksi atau API key.")
                    st.rerun()

        if st.session_state.scanned_results:
            st.subheader("Top 10 Aset Potensial (dari 100 yang discan):")

            for i, res in enumerate(st.session_state.scanned_results, 1):
                if isinstance(res, dict) and 'symbol' in res:
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.write(f"{i}. **{res['symbol']}** - {res['action']} (Score: {res['score']})")
                        st.write(f"Entry Range: {res['entry_low']:.5f} - {res['entry_high']:.5f} | "
                                 f"SL: {res['sl']:.5f}")
                        st.write(f"TP1: {res['tp1']:.5f} | TP2: {res['tp2']:.5f} | TP3: {res['tp3']:.5f}")
                        
                        if 'detected_patterns' in res and res['detected_patterns']:
                            st.write(f"📊 **Pola Terdeteksi:** {', '.join(res['detected_patterns'])}")
                        
                        if 'pattern_score' in res:
                            st.write(f"⭐ **Pattern Score:** {res['pattern_score']}")
                            
                        if 'risk_category' in res:
                            st.write(f"⚖️ **Risk Category:** {res['risk_category']}")
                            
                    with col2:
                        if st.button(f"Pilih {i}", key=f"select_{res['symbol']}"):
                            st.session_state.selected_for_entry[res['symbol']] = res
                            st.success(f"Selected {res['symbol']}!")
                            st.rerun()
                else:
                    st.warning("Data analisis tidak valid untuk salah satu aset.")

            for symbol, analysis in list(st.session_state.selected_for_entry.items()):
                if isinstance(analysis, dict) and 'symbol' in analysis:
                    st.markdown("---")
                    st.subheader(f"Input Entry untuk {symbol}")
                    
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
                    
                    with st.expander("Detail Analisis"):
                        if 'momentum_quality' in analysis:
                            st.write(f"**Momentum Quality:** {analysis['momentum_quality']}")
                        if 'market_phase' in analysis:
                            st.write(f"**Market Phase:** {analysis['market_phase']}")
                        if 'reward_ratio' in analysis:
                            st.write(f"**Reward Ratio:** {analysis['reward_ratio']:.2f}")
                    
                    if st.button(f"Hapus {symbol} dari pilihan", key=f"remove_{symbol}"):
                        if symbol in st.session_state.selected_for_entry:
                            del st.session_state.selected_for_entry[symbol]
                        st.rerun()
                else:
                    st.warning(f"Data analisis tidak valid untuk {symbol}. Menghapus dari pilihan.")
                    if symbol in st.session_state.selected_for_entry:
                        del st.session_state.selected_for_entry[symbol]
                    st.rerun()

            st.markdown("---")
            st.subheader("Kelola Sinyal")
            if st.button("Hapus Semua Sinyal Tidak Terpilih", key="confirm_delete"):
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
        if st.checkbox("Auto Rescan (30s)"):
            if "scheduler_thread" not in st.session_state:
                st.session_state["scheduler_thread"] = threading.Thread(
                    target=run_scheduler, args=(bot,), daemon=True
                )
                st.session_state["scheduler_thread"].start()

            if "latest_results" in st.session_state:
                st.subheader("Latest Scan Results:")
                for res in st.session_state["latest_results"]:
                    if isinstance(res, dict) and 'symbol' in res:
                        st.write(f"**{res['symbol']}** - {res['action']} (Score: {res['score']})")
                        if 'detected_patterns' in res and res['detected_patterns']:
                            st.write(f"Pola: {', '.join(res['detected_patterns'])}")

    # (Lanjutkan dengan tab lain seperti asli, karena fix hanya di Tab 1)

if __name__ == "__main__":
    main()
