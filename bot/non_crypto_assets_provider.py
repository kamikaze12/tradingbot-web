import json
import os
from datetime import datetime, timedelta
import logging
import yfinance as yf
import pandas as pd
import numpy as np
from typing import List, Dict, Set
import requests
from bs4 import BeautifulSoup
import time
import concurrent.futures
from threading import Lock
from concurrent.futures import ThreadPoolExecutor, as_completed

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Cache file path
CACHE_FILE = 'assets_cache.json'
CACHE_TTL_DAYS = 3

class NonCryptoAssetsProvider:
    """
    Provider untuk list aset non-crypto (saham Indo, forex, saham US).
    - FIXED: Gunakan hanya saham LQ45 yang aktif trading
    - FIXED: Ambil data 90 hari untuk analisa teknikal
    - FIXED: Skip saham delisted/error
    """
    
    def __init__(self):
        self.cache = self._load_cache()
        self.invalid_symbols: Set[str] = set()
        self.cache_lock = Lock()
        self.rate_limit_delay = 0.5  # Delay antara request untuk hindari rate limit
        
    # =============================================
    # 🚨 PERBAIKAN UTAMA: GANTI KE SAHAM LQ45 SAJA
    # =============================================
    
    def get_assets(self, category: str, limit: int = 200, force_update: bool = False) -> List[str]:
        """
        Dapatkan list simbol aset untuk kategori tertentu.
        
        FIXED: Untuk Indonesia stocks, hanya gunakan LQ45 + Bluechip yang aktif
        """
        if category not in ['indonesia_stocks', 'forex', 'us_stocks']:
            raise ValueError(f"Invalid category: {category}. Pilih: indonesia_stocks, forex, us_stocks.")
        
        # 🚨 FIXED: Untuk saham Indonesia, gunakan LQ45 SAJA
        if category == 'indonesia_stocks':
            return self._get_lq45_stocks()[:limit]
        
        # Untuk forex dan US stocks, gunakan cache
        cache_key = f"{category}_assets"
        
        if not force_update and cache_key in self.cache:
            cache_data = self.cache[cache_key]
            cache_time = datetime.fromisoformat(cache_data['timestamp'])
            if datetime.now() - cache_time < timedelta(days=CACHE_TTL_DAYS):
                logger.info(f"📦 Using cached assets for {category}")
                return cache_data['assets'][:limit]
        
        # Fetch untuk forex dan US stocks
        try:
            assets = self._fetch_dynamic_assets(category, limit)
            if assets and len(assets) >= 10:
                with self.cache_lock:
                    self.cache[cache_key] = {
                        'timestamp': datetime.now().isoformat(),
                        'assets': assets
                    }
                    self._save_cache()
                return assets[:limit]
        except Exception as e:
            logger.warning(f"⚠️ Fetch failed for {category}: {e}")
        
        return self._get_static_assets(category)[:limit]
    
    def _get_lq45_stocks(self) -> List[str]:
        """Hanya saham LQ45 yang benar-benar aktif trading."""
        lq45 = [
            # ✅ Saham LIKUID dengan data YFinance yang BAGUS
            'BBCA.JK', 'BBRI.JK', 'BMRI.JK', 'TLKM.JK', 'ASII.JK',
            'UNVR.JK', 'ICBP.JK', 'INDF.JK', 'ANTM.JK', 'ADRO.JK',
            'AKRA.JK', 'AMRT.JK', 'INCO.JK', 'BRPT.JK', 'SMGR.JK',
            'PGAS.JK', 'KLBF.JK', 'CPIN.JK', 'INTP.JK', 'BBNI.JK',
            'BNGA.JK', 'BSDE.JK', 'GOTO.JK', 'MDKA.JK', 'ITMG.JK',
            'MNCN.JK', 'ERAA.JK', 'TPIA.JK', 'CTRA.JK', 'EXCL.JK',
            'JPFA.JK', 'JSMR.JK', 'KIJA.JK', 'MEDC.JK', 'MYOR.JK',
            'PTBA.JK', 'PTPP.JK', 'SMRA.JK', 'SRIL.JK', 'TBIG.JK',
            'TINS.JK', 'TKIM.JK', 'ULTJ.JK', 'UNTR.JK', 'WIKA.JK',
            'WSKT.JK', 'WEGE.JK', 'ADHI.JK', 'ASRI.JK', 'PWON.JK',
            'SMBR.JK', 'SIDO.JK', 'LPPF.JK', 'HRUM.JK', 'BUMI.JK',
            'AKPI.JK', 'BRPT.JK', 'INTP.JK', 'JSMR.JK', 'PTBA.JK'
        ]
        
        # Verifikasi saham yang benar-benar ada data di YFinance
        verified = []
        for symbol in lq45:
            if symbol not in self.invalid_symbols:
                try:
                    ticker = yf.Ticker(symbol)
                    hist = ticker.history(period="7d")
                    if not hist.empty and len(hist) > 3:
                        verified.append(symbol)
                    else:
                        self.invalid_symbols.add(symbol)
                        logger.warning(f"⚠️ {symbol}: No data found, marking as invalid")
                except Exception as e:
                    self.invalid_symbols.add(symbol)
                    logger.warning(f"⚠️ {symbol}: Error - {str(e)[:50]}")
            
            time.sleep(self.rate_limit_delay)  # Hindari rate limit
        
        logger.info(f"✅ Verified {len(verified)} LQ45 stocks with valid data")
        return verified
    
    # =============================================
    # 🎯 SCREENER YANG EFEKTIF (25 SAHAM TERAKTIF)
    # =============================================
    
    def get_active_assets(self, category: str = 'indonesia_stocks',
                         min_volume: float = 5_000_000,  # Minimal 5 juta volume
                         min_volatility: float = 0.015,   # Minimal 1.5% volatilitas
                         min_price_change: float = 0.02,  # Minimal 2% price change
                         limit: int = 25) -> List[str]:   # Hanya 25 terbaik
        """
        🚨 FIXED: Ambil HANYA 25 aset teraktif dari LQ45 untuk analisa!
        """
        print(f"\n🔥 SCREENING ASET AKTIF ({category})")
        print("=" * 60)
        
        if category != 'indonesia_stocks':
            return self._get_predefined_active(category, limit)
        
        # 1. Ambil saham LQ45
        lq45_stocks = self._get_lq45_stocks()[:50]  # 50 teratas
        print(f"📊 Total LQ45 stocks: {len(lq45_stocks)}")
        
        # 2. Screening dengan data 90 hari
        print("🔍 Screening untuk aset aktif...")
        
        screened_stocks = []
        results = []
        
        for symbol in lq45_stocks:
            try:
                # Ambil data 90 hari untuk analisa yang proper
                ticker = yf.Ticker(symbol)
                hist = ticker.history(period="90d", interval="1d")
                
                if len(hist) < 30:  # Minimal 30 data points
                    print(f"  ⚠️ {symbol}: Data kurang ({len(hist)} bars)")
                    continue
                
                # Hitung metrics
                avg_volume = hist['Volume'].mean()
                if avg_volume < min_volume:
                    continue  # Skip volume terlalu kecil
                
                # Volatilitas 30 hari terakhir
                recent_returns = hist['Close'][-30:].pct_change().dropna()
                volatility = recent_returns.std() if len(recent_returns) > 5 else 0
                
                if volatility < min_volatility:
                    continue  # Skip yang tidak volatile
                
                # Price change 30 hari
                price_change = (hist['Close'].iloc[-1] - hist['Close'].iloc[-30]) / hist['Close'].iloc[-30]
                if abs(price_change) < min_price_change:
                    continue  # Skip yang flat
                
                # Volume trend (5 hari vs 30 hari)
                volume_5d = hist['Volume'][-5:].mean()
                volume_30d = hist['Volume'][-30:].mean()
                volume_trend = volume_5d / volume_30d if volume_30d > 0 else 1
                
                # Hitung score
                volume_score = min(np.log10(avg_volume + 1) / 7, 1.0)
                volatility_score = min(volatility * 50, 1.0)
                trend_score = min(abs(price_change) * 20, 1.0)
                volume_trend_score = min(volume_trend, 2.0) / 2.0
                
                score = (
                    volume_score * 0.25 +
                    volatility_score * 0.25 +
                    trend_score * 0.25 +
                    volume_trend_score * 0.25
                ) * 100
                
                results.append({
                    'symbol': symbol,
                    'score': score,
                    'volume': avg_volume,
                    'volatility': volatility,
                    'price_change': price_change,
                    'volume_trend': volume_trend,
                    'data_points': len(hist)
                })
                
                time.sleep(self.rate_limit_delay * 2)  # Delay lebih lama
                
            except Exception as e:
                print(f"  ❌ {symbol}: Error - {str(e)[:50]}")
                continue
        
        # Sort by score
        results.sort(key=lambda x: x['score'], reverse=True)
        
        # Ambil top performers
        screened_stocks = [r['symbol'] for r in results[:limit]]
        
        if screened_stocks:
            print(f"✅ Ditemukan {len(screened_stocks)} aset aktif")
            print(f"🎯 Top 5: {screened_stocks[:5]}")
            
            # Debug info
            print(f"📈 Rata-rata data points: {np.mean([r['data_points'] for r in results[:10]]):.0f}")
            print(f"📊 Rata-rata volume: {np.mean([r['volume'] for r in results[:10]]):,.0f}")
            print(f"📉 Rata-rata volatilitas: {np.mean([r['volatility'] for r in results[:10]]):.3%}")
        else:
            print("⚠️ Tidak ada aset aktif ditemukan, gunakan LQ45 default")
            screened_stocks = lq45_stocks[:limit]
        
        return screened_stocks
    
    # =============================================
    # 🚀 TRADING SIGNAL GENERATOR (FIXED)
    # =============================================
    
    def generate_trading_signals(self, symbols: List[str] = None, 
                               min_bars: int = 40,  # Minimal 40 bars
                               rsi_oversold: int = 30,
                               rsi_overbought: int = 70) -> List[Dict]:
        """
        FIXED: Generate trading signals dengan data yang cukup.
        Hanya analisa jika punya minimal 40 bars data.
        """
        if symbols is None:
            symbols = self.get_active_assets('indonesia_stocks', limit=25)
        
        print(f"\n📈 GENERATING TRADING SIGNALS ({len(symbols)} symbols)")
        print("=" * 60)
        
        signals = []
        
        for symbol in symbols:
            try:
                print(f"  🔍 Analisa {symbol}...")
                
                # Ambil data 90 hari dengan retry
                for attempt in range(3):
                    try:
                        ticker = yf.Ticker(symbol)
                        hist = ticker.history(period="90d", interval="1d")
                        
                        if len(hist) < min_bars:
                            print(f"    ⚠️ Data tidak cukup: {len(hist)} < {min_bars} bars")
                            break  # Skip, tidak cukup data
                        
                        # ✅ DATA CUKUP, lanjut analisa
                        break
                        
                    except Exception as e:
                        if attempt < 2:
                            time.sleep(1)
                            continue
                        else:
                            raise e
                
                if 'hist' not in locals() or len(hist) < min_bars:
                    continue  # Skip jika tidak cukup data
                
                # ========== ANALISIS TEKNIKAL ==========
                
                # 1. RSI (14 period)
                delta = hist['Close'].diff()
                gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                rs = gain / loss
                rsi = 100 - (100 / (1 + rs))
                
                # 2. Moving Averages
                sma_20 = hist['Close'].rolling(window=20).mean()
                sma_50 = hist['Close'].rolling(window=50).mean()
                
                # 3. MACD
                exp12 = hist['Close'].ewm(span=12, adjust=False).mean()
                exp26 = hist['Close'].ewm(span=26, adjust=False).mean()
                macd = exp12 - exp26
                signal_line = macd.ewm(span=9, adjust=False).mean()
                
                # 4. Bollinger Bands
                bb_middle = hist['Close'].rolling(window=20).mean()
                bb_std = hist['Close'].rolling(window=20).std()
                bb_upper = bb_middle + (bb_std * 2)
                bb_lower = bb_middle - (bb_std * 2)
                
                # 5. Volume
                volume_sma = hist['Volume'].rolling(window=20).mean()
                current_volume = hist['Volume'].iloc[-1] if not hist.empty else 0
                volume_ratio = current_volume / volume_sma.iloc[-1] if volume_sma.iloc[-1] > 0 else 1
                
                # ========== CURRENT VALUES ==========
                current_price = hist['Close'].iloc[-1]
                current_rsi = rsi.iloc[-1]
                current_macd = macd.iloc[-1]
                current_signal = signal_line.iloc[-1]
                
                # Support & Resistance
                resistance = hist['High'][-20:].max()
                support = hist['Low'][-20:].min()
                
                # ========== GENERATE SIGNALS ==========
                signal_strength = 0
                signal_type = "HOLD"
                signal_reasons = []
                
                # RSI Signal
                if current_rsi < rsi_oversold:
                    signal_strength += 3
                    signal_reasons.append(f"RSI oversold ({current_rsi:.1f})")
                    signal_type = "BUY"
                elif current_rsi > rsi_overbought:
                    signal_strength += 3
                    signal_reasons.append(f"RSI overbought ({current_rsi:.1f})")
                    signal_type = "SELL"
                
                # MACD Crossover
                if (current_macd > current_signal and 
                    macd.iloc[-2] <= signal_line.iloc[-2]):
                    signal_strength += 2
                    signal_reasons.append("MACD bullish crossover")
                    if signal_type == "HOLD":
                        signal_type = "BUY"
                elif (current_macd < current_signal and 
                      macd.iloc[-2] >= signal_line.iloc[-2]):
                    signal_strength += 2
                    signal_reasons.append("MACD bearish crossover")
                    if signal_type == "HOLD":
                        signal_type = "SELL"
                
                # Moving Average Crossover
                if (sma_20.iloc[-1] > sma_50.iloc[-1] and 
                    sma_20.iloc[-2] <= sma_50.iloc[-2]):
                    signal_strength += 3
                    signal_reasons.append("Golden Cross (SMA20 > SMA50)")
                    signal_type = "BUY"
                elif (sma_20.iloc[-1] < sma_50.iloc[-1] and 
                      sma_20.iloc[-2] >= sma_50.iloc[-2]):
                    signal_strength += 3
                    signal_reasons.append("Death Cross (SMA20 < SMA50)")
                    signal_type = "SELL"
                
                # Bollinger Bands
                if current_price < bb_lower.iloc[-1]:
                    signal_strength += 2
                    signal_reasons.append("Price below Bollinger Lower Band")
                    if signal_type == "HOLD":
                        signal_type = "BUY"
                elif current_price > bb_upper.iloc[-1]:
                    signal_strength += 2
                    signal_reasons.append("Price above Bollinger Upper Band")
                    if signal_type == "HOLD":
                        signal_type = "SELL"
                
                # Support/Resistance Breakout
                if current_price > resistance:
                    signal_strength += 2
                    signal_reasons.append(f"Breakout resistance ({resistance:.0f})")
                    signal_type = "BUY"
                elif current_price < support:
                    signal_strength += 2
                    signal_reasons.append(f"Breakdown support ({support:.0f})")
                    signal_type = "SELL"
                
                # Volume Confirmation
                if volume_ratio > 1.5 and signal_type != "HOLD":
                    signal_strength += 1
                    signal_reasons.append(f"Volume spike ({volume_ratio:.1f}x)")
                
                # ========== FINAL DECISION ==========
                # Hanya ambil signal dengan strength >= 4
                if signal_strength >= 4 and signal_type != "HOLD":
                    signals.append({
                        'symbol': symbol,
                        'signal': signal_type,
                        'strength': signal_strength,
                        'reasons': signal_reasons,
                        'price': current_price,
                        'rsi': current_rsi,
                        'volume_ratio': volume_ratio,
                        'data_points': len(hist),
                        'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    })
                    
                    print(f"    ✅ {signal_type} (Strength: {signal_strength}/10)")
                    for reason in signal_reasons[:2]:
                        print(f"       • {reason}")
                
                else:
                    print(f"    ⚪ HOLD (Strength: {signal_strength}/10)")
                
                time.sleep(self.rate_limit_delay * 2)
                
            except Exception as e:
                print(f"    ❌ Error: {str(e)[:50]}")
                continue
        
        # Sort by signal strength
        signals.sort(key=lambda x: x['strength'], reverse=True)
        
        print(f"\n📊 Signal Summary: {len(signals)} signals generated")
        return signals
    
    # =============================================
    # 📊 FUNGSI TAMBAHAN YANG BERGUNA
    # =============================================
    
    def get_volume_spikes(self, threshold: float = 2.0, limit: int = 10) -> List[Dict]:
        """Cari saham dengan volume spike hari ini."""
        print(f"\n🔍 Mencari volume spike (> {threshold}x)...")
        
        active_symbols = self.get_active_assets(limit=30)
        spiked = []
        
        for symbol in active_symbols:
            try:
                ticker = yf.Ticker(symbol)
                hist = ticker.history(period="10d")
                
                if len(hist) < 5:
                    continue
                
                avg_volume = hist['Volume'][:-1].mean()
                last_volume = hist['Volume'].iloc[-1]
                
                if avg_volume > 0 and (last_volume / avg_volume) > threshold:
                    spiked.append({
                        'symbol': symbol,
                        'spike_ratio': last_volume / avg_volume,
                        'volume': last_volume,
                        'avg_volume': avg_volume
                    })
                    
                    if len(spiked) >= limit:
                        break
                
                time.sleep(self.rate_limit_delay)
                
            except Exception as e:
                continue
        
        # Sort by spike ratio
        spiked.sort(key=lambda x: x['spike_ratio'], reverse=True)
        
        if spiked:
            print(f"✅ Ditemukan {len(spiked)} volume spike")
            for spike in spiked[:5]:
                print(f"   📈 {spike['symbol']}: {spike['spike_ratio']:.1f}x")
        else:
            print("📉 Tidak ada volume spike signifikan")
        
        return spiked
    
    def get_hot_sectors(self) -> Dict[str, List[str]]:
        """Identifikasi sektor yang sedang aktif."""
        sector_map = {
            'BANKING': ['BBCA.JK', 'BBRI.JK', 'BMRI.JK', 'BBNI.JK', 'BNGA.JK'],
            'MINING': ['ANTM.JK', 'ADRO.JK', 'INCO.JK', 'BRPT.JK', 'PTBA.JK'],
            'CONSUMER': ['UNVR.JK', 'ICBP.JK', 'INDF.JK', 'MYOR.JK', 'ULTJ.JK'],
            'PROPERTY': ['BSDE.JK', 'CTRA.JK', 'ASRI.JK', 'SMRA.JK', 'PWON.JK'],
            'INFRASTRUCTURE': ['WIKA.JK', 'PTPP.JK', 'ADHI.JK', 'JSMR.JK', 'SRIL.JK'],
            'TECH': ['GOTO.JK', 'BRIS.JK', 'DMMX.JK', 'ARTO.JK', 'TCID.JK']
        }
        
        active_symbols = set(self.get_active_assets(limit=50))
        hot_sectors = {}
        
        for sector, stocks in sector_map.items():
            active_in_sector = [s for s in stocks if s in active_symbols]
            if len(active_in_sector) >= 2:  # Minimal 2 saham aktif
                hot_sectors[sector] = active_in_sector
        
        # Sort by number of active stocks
        return dict(sorted(hot_sectors.items(), 
                         key=lambda x: len(x[1]), 
                         reverse=True))
    
    # =============================================
    # 🛠️ FUNGSI HELPER (TETAP SAMA)
    # =============================================
    
    def _get_predefined_active(self, category: str, limit: int) -> List[str]:
        """List predefined untuk forex dan US stocks."""
        if category == 'forex':
            return [
                'EURUSD=X', 'USDJPY=X', 'GBPUSD=X', 'AUDUSD=X', 'USDCAD=X',
                'USDCHF=X', 'NZDUSD=X', 'EURGBP=X', 'EURJPY=X', 'GBPJPY=X'
            ][:limit]
        elif category == 'us_stocks':
            return [
                'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'TSLA', 'NVDA', 'AMD',
                'NFLX', 'JPM', 'V', 'MA', 'JNJ', 'WMT', 'PG', 'UNH', 'HD'
            ][:limit]
        return []
    
    def _fetch_dynamic_assets(self, category: str, limit: int) -> List[str]:
        """Fetch dinamis untuk forex dan US stocks."""
        return self._get_static_assets(category)[:limit]
    
    def _get_static_assets(self, category: str) -> List[str]:
        """Fallback static list."""
        if category == 'us_stocks':
            return [
                'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'TSLA', 'NVDA', 
                'JPM', 'V', 'JNJ', 'WMT', 'PG', 'MA', 'UNH', 'HD'
            ]
        elif category == 'indonesia_stocks':
            return self._get_lq45_stocks()
        elif category == 'forex':
            return [
                'EURUSD=X', 'USDJPY=X', 'GBPUSD=X', 'AUDUSD=X', 'USDCAD=X',
                'USDCHF=X', 'NZDUSD=X', 'EURGBP=X', 'EURJPY=X', 'GBPJPY=X'
            ]
        return []
    
    def _load_cache(self) -> Dict:
        """Load cache dari file JSON."""
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, 'r') as f:
                    return json.load(f)
            except:
                logger.warning("⚠️ Corrupted cache, starting fresh.")
        return {}
    
    def _save_cache(self):
        """Save cache ke file JSON."""
        with open(CACHE_FILE, 'w') as f:
            json.dump(self.cache, f)
        logger.debug("💾 Cache saved.")

# =============================================
# 🚀 CONTOH PENGGUNAAN
# =============================================
if __name__ == "__main__":
    provider = NonCryptoAssetsProvider()
    
    print("🚀 NON-CRYPTO ASSETS PROVIDER - FIXED VERSION")
    print("=" * 60)
    
    # 1. Dapatkan saham aktif LQ45
    print("\n1️⃣ Mengambil 25 saham LQ45 teraktif...")
    active_stocks = provider.get_active_assets(
        category='indonesia_stocks',
        min_volume=5_000_000,
        min_volatility=0.015,
        limit=25
    )
    print(f"   ✅ {len(active_stocks)} saham aktif: {active_stocks[:10]}...")
    
    # 2. Generate trading signals
    print("\n2️⃣ Generating trading signals (min 40 bars data)...")
    signals = provider.generate_trading_signals(
        symbols=active_stocks[:20],  # Analisa 20 teratas
        min_bars=40,
        rsi_oversold=30,
        rsi_overbought=70
    )
    
    # 3. Tampilkan hasil
    print("\n3️⃣ TRADING SIGNALS HASIL:")
    print("=" * 60)
    
    if signals:
        for i, signal in enumerate(signals[:10], 1):
            print(f"\n#{i} {signal['symbol']}: {signal['signal']} (Strength: {signal['strength']}/10)")
            print(f"   Price: {signal['price']:.0f} | RSI: {signal['rsi']:.1f} | Volume: {signal['volume_ratio']:.1f}x")
            print(f"   Reasons: {', '.join(signal['reasons'])}")
            print(f"   Data points: {signal['data_points']} bars")
    else:
        print("\n⚠️ Tidak ada signal trading yang ditemukan")
        print("   Kemungkinan penyebab:")
        print("   - Data kurang (minimal 40 bars)")
        print("   - Tidak ada kondisi oversold/overbought")
        print("   - Market sedang sideways")
    
    # 4. Volume spikes
    print("\n4️⃣ Volume Spikes Hari Ini:")
    spikes = provider.get_volume_spikes(threshold=2.0, limit=5)
    if spikes:
        for spike in spikes[:3]:
            print(f"   📈 {spike['symbol']}: {spike['spike_ratio']:.1f}x ({spike['volume']:,.0f} shares)")
    
    # 5. Hot sectors
    print("\n5️⃣ Sektor Aktif:")
    hot_sectors = provider.get_hot_sectors()
    for sector, stocks in list(hot_sectors.items())[:3]:
        print(f"   🔥 {sector}: {', '.join(stocks[:3])}")
    
    print("\n" + "=" * 60)
    print("🎯 STRATEGI EFEKTIF:")
    print("   • Analisa hanya 25 saham LQ45 teraktif")
    print("   • Minimal 40 bars data untuk analisa")
    print("   • Multi-indicator confirmation (RSI, MACD, MA, Volume)")
    print("   • Strength threshold >= 4 untuk filter noise")
    print("\n✅ File telah difix untuk menghasilkan signal trading!")
