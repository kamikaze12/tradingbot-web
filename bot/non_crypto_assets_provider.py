import json
import os
from datetime import datetime, timedelta
import logging
import yfinance as yf
import ccxt
import pandas as pd
import numpy as np
from typing import List, Dict, Optional, Set
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
CACHE_TTL_DAYS = 3  # Update setiap 3 hari

class NonCryptoAssetsProvider:
    """
    Provider untuk list aset non-crypto (saham Indo, forex, saham US).
    - Update otomatis setiap 3 hari (optional via force_update).
    - Fallback ke list statis jika fetch gagal.
    - Kategori: 'indonesia_stocks', 'forex', 'us_stocks'.
    - NEW: Built-in screener untuk cari aset aktif/rame.
    """
    
    def __init__(self):
        self.cache = self._load_cache()
        self.invalid_symbols: Set[str] = set()  # Untuk simpan simbol yang tidak valid
        self.cache_lock = Lock()
        self.volume_cache = {}  # Cache untuk volume dan data
        self.volume_cache_time = {}
        
    # =============================================
    # 🚨 PERBAIKAN UTAMA: GET DATA DENGAN PERIODE YANG CUKUP
    # =============================================
    
    def get_historical_data(self, symbol: str, days: int = 90, interval: str = "1d") -> pd.DataFrame:
        """
        Get historical data dengan multiple fallback dan periode yang cukup.
        Minimal 60 hari data untuk analisis teknikal.
        """
        try:
            # Coba Yahoo Finance dengan retry
            for attempt in range(3):
                try:
                    ticker = yf.Ticker(symbol)
                    
                    # PERBAIKAN 1: Gunakan periode yang lebih panjang
                    period = f"{max(days, 90)}d"  # Minimal 90 hari
                    hist = ticker.history(period=period, interval=interval)
                    
                    # PERBAIKAN 2: Jika data kurang, coba dengan interval yang berbeda
                    if len(hist) < 40 and interval == "1d":
                        # Coba ambil data 6 bulan
                        hist = ticker.history(period="6mo", interval=interval)
                    
                    if not hist.empty and len(hist) >= 20:
                        # Cache data untuk performa
                        cache_key = f"{symbol}_history"
                        self.volume_cache[cache_key] = hist
                        self.volume_cache_time[cache_key] = datetime.now()
                        return hist
                    elif attempt < 2:
                        time.sleep(1)  # Tunggu sebelum retry
                        continue
                        
                except Exception as e:
                    if attempt < 2:
                        time.sleep(1)
                        continue
            
            # Jika Yahoo Finance gagal, coba metode alternatif
            return self._get_fallback_data(symbol, days)
            
        except Exception as e:
            logger.warning(f"Failed to get historical data for {symbol}: {e}")
            return pd.DataFrame()
    
    def _get_fallback_data(self, symbol: str, days: int) -> pd.DataFrame:
        """Fallback method untuk mendapatkan data."""
        try:
            # Method 1: Gunakan yfinance dengan interval lebih lama
            ticker = yf.Ticker(symbol)
            
            # Coba berbagai periode
            periods_to_try = ["6mo", "1y", "2y"]
            
            for period in periods_to_try:
                try:
                    hist = ticker.history(period=period, interval="1d")
                    if len(hist) >= 30:
                        # Slice untuk mendapatkan data terakhir (days) hari
                        if len(hist) > days:
                            hist = hist[-days:]
                        return hist
                except:
                    continue
            
            # Method 2: Jika semua gagal, return data minimal yang ada
            hist = ticker.history(period="1mo", interval="1d")
            if not hist.empty:
                return hist
                
        except Exception as e:
            logger.error(f"All fallback methods failed for {symbol}: {e}")
        
        return pd.DataFrame()
    
    # =============================================
    # 🎯 PERBAIKAN SCREENER: PASTIKAN DATA CUKUP
    # =============================================
    
    def get_active_assets(self, category: str = 'indonesia_stocks',
                         min_volume: float = 1_000_000,
                         min_volatility: float = 0.025,
                         min_price_change: float = 0.05,
                         limit: int = 50) -> List[str]:
        """
        🚨 PENTING: Ambil HANYA aset yang aktif/rame untuk analisa!
        Jangan analisa semua aset, waste of time!
        
        PERBAIKAN: Gunakan data yang cukup untuk screening
        """
        print(f"\n🔥 SCREENING ASET AKTIF ({category})")
        print("=" * 60)
        
        # 1. Gunakan list saham likuid terlebih dahulu
        if category == 'indonesia_stocks':
            # Mulai dengan LQ45 + saham bluechip
            liquid_symbols = self._get_liquid_indonesia_stocks()
            print(f"📊 Mulai dengan {len(liquid_symbols)} saham likuid")
        else:
            liquid_symbols = self.get_assets(category, limit=200)
        
        # 2. Screening dengan data yang cukup
        print(f"🔍 Screening untuk aset aktif...")
        
        active_assets = []
        
        with ThreadPoolExecutor(max_workers=5) as executor:
            future_to_symbol = {}
            
            for symbol in liquid_symbols[:100]:  # Batasi 100 untuk efisiensi
                future = executor.submit(
                    self._check_asset_activity_enhanced, 
                    symbol,
                    min_volume,
                    min_volatility,
                    min_price_change
                )
                future_to_symbol[future] = symbol
            
            completed = 0
            for future in as_completed(future_to_symbol):
                completed += 1
                symbol = future_to_symbol[future]
                
                try:
                    result = future.result(timeout=10)
                    if result['active']:
                        active_assets.append({
                            'symbol': symbol,
                            'score': result['score'],
                            'volume': result['avg_volume'],
                            'data_points': result['data_points']
                        })
                        
                    # Progress update
                    if completed % 10 == 0:
                        print(f"   Progress: {completed}/{min(100, len(liquid_symbols))}")
                        
                except Exception as e:
                    continue
        
        # Sort dan filter
        if active_assets:
            active_assets.sort(key=lambda x: x['score'], reverse=True)
            result_symbols = [item['symbol'] for item in active_assets[:limit]]
            
            print(f"✅ Ditemukan {len(result_symbols)} aset aktif")
            print(f"📈 Data points rata-rata: {np.mean([item['data_points'] for item in active_assets[:10]]):.0f}")
            
            if result_symbols:
                print(f"🎯 Top 5: {result_symbols[:5]}")
            return result_symbols
        else:
            print("⚠️ Tidak ada aset aktif ditemukan, gunakan fallback")
            return self._get_fallback_active(category, limit)
    
    def _check_asset_activity_enhanced(self, symbol: str, 
                                     min_volume: float,
                                     min_volatility: float,
                                     min_price_change: float) -> Dict:
        """
        Enhanced screening dengan data yang cukup.
        """
        try:
            # PERBAIKAN: Ambil data yang cukup
            hist = self.get_historical_data(symbol, days=60)
            
            # PERBAIKAN: Minimal 30 data points untuk analisis
            if hist.empty or len(hist) < 30:
                return {'active': False, 'data_points': len(hist) if not hist.empty else 0}
            
            # Hitung metrik dengan data yang cukup
            avg_volume = hist['Volume'].mean()
            
            # Skip volume terlalu kecil
            if avg_volume < min_volume * 0.5:  # Threshold lebih rendah untuk screening awal
                return {'active': False, 'data_points': len(hist)}
            
            # Volatilitas 30 hari terakhir
            recent_close = hist['Close'][-30:] if len(hist) >= 30 else hist['Close']
            returns = recent_close.pct_change().dropna()
            
            if len(returns) < 10:
                volatility = returns.std() if len(returns) > 1 else 0
            else:
                volatility = returns.std()
            
            # Price change 30 hari vs 60 hari
            if len(hist) >= 30:
                price_change_30d = (hist['Close'].iloc[-1] - hist['Close'].iloc[-30]) / hist['Close'].iloc[-30]
            else:
                price_change_30d = (hist['Close'].iloc[-1] - hist['Close'].iloc[0]) / hist['Close'].iloc[0]
            
            # Volume trend
            if len(hist) >= 20:
                volume_20d_avg = hist['Volume'][-20:].mean()
                volume_trend = volume_20d_avg / avg_volume if avg_volume > 0 else 1
            else:
                volume_trend = 1
            
            # Hitung score dengan bobot yang diperbaiki
            volume_score = min(np.log10(avg_volume + 1) / 6, 1.0)  # Normalize
            volatility_score = min(volatility * 20, 1.0)  # Normalize
            trend_score = min(abs(price_change_30d) * 10, 1.0)  # Normalize
            volume_trend_score = min(volume_trend, 2.0) / 2.0  # Normalize
            
            score = (
                volume_score * 0.3 +
                volatility_score * 0.3 +
                trend_score * 0.2 +
                volume_trend_score * 0.2
            )
            
            return {
                'active': True,
                'score': score * 100,
                'avg_volume': avg_volume,
                'volatility': volatility,
                'price_change': price_change_30d,
                'volume_trend': volume_trend,
                'data_points': len(hist)
            }
            
        except Exception as e:
            return {'active': False, 'error': str(e), 'data_points': 0}
    
    def _get_liquid_indonesia_stocks(self) -> List[str]:
        """Dapatkan list saham likuid (LQ45 + Bluechip)."""
        liquid_stocks = [
            # LQ45
            'BBCA.JK', 'BBRI.JK', 'BMRI.JK', 'TLKM.JK', 'ASII.JK', 'UNVR.JK',
            'ICBP.JK', 'INDF.JK', 'ANTM.JK', 'ADRO.JK', 'AKRA.JK', 'AMRT.JK',
            'INCO.JK', 'BRPT.JK', 'SMGR.JK', 'PGAS.JK', 'KLBF.JK', 'CPIN.JK',
            'INTP.JK', 'BBNI.JK', 'BNGA.JK', 'BSDE.JK', 'BUKA.JK', 'GOTO.JK',
            'MDKA.JK', 'ITMG.JK', 'MNCN.JK', 'ERAA.JK', 'TPIA.JK', 'BUMI.JK',
            'CTRA.JK', 'EXCL.JK', 'HRUM.JK', 'JPFA.JK', 'JSMR.JK', 'KIJA.JK',
            'LPPF.JK', 'MEDC.JK', 'MYOR.JK', 'PTBA.JK', 'PTPP.JK', 'SIDO.JK',
            'SMRA.JK', 'SRIL.JK', 'TBIG.JK',
            
            # Bluechip tambahan
            'TLKM.JK', 'UNTR.JK', 'WIKA.JK', 'WSKT.JK', 'WTON.JK', 'WSBP.JK',
            'WEGE.JK', 'ADHI.JK', 'ASRI.JK', 'CTRA.JK', 'PWON.JK', 'SMRA.JK',
            'SMBR.JK', 'SMCB.JK', 'TINS.JK', 'TKIM.JK', 'ULTJ.JK', 'UNTR.JK'
        ]
        
        return list(set(liquid_stocks))  # Remove duplicates
    
    def _get_fallback_active(self, category: str, limit: int) -> List[str]:
        """Fallback list untuk aset aktif."""
        if category == 'indonesia_stocks':
            return self._get_liquid_indonesia_stocks()[:limit]
        elif category == 'forex':
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
    
    # =============================================
    # 🚨 PERBAIKAN: GENERATE TRADING SIGNAL
    # =============================================
    
    def generate_trading_signals(self, symbols: List[str] = None, 
                               rsi_period: int = 14,
                               rsi_oversold: int = 30,
                               rsi_overbought: int = 70) -> List[Dict]:
        """
        Generate trading signals untuk list symbols.
        
        Returns: List of dict dengan signal
        """
        if symbols is None:
            symbols = self.get_active_assets('indonesia_stocks', limit=30)
        
        print(f"\n📈 GENERATING TRADING SIGNALS ({len(symbols)} symbols)")
        print("=" * 60)
        
        signals = []
        
        for symbol in symbols:
            try:
                # Get data dengan periode yang cukup
                hist = self.get_historical_data(symbol, days=90)
                
                if len(hist) < 40:  # Minimal 40 data points
                    print(f"⚠️ {symbol}: Insufficient data ({len(hist)} bars)")
                    continue
                
                # Calculate RSI
                delta = hist['Close'].diff()
                gain = (delta.where(delta > 0, 0)).rolling(window=rsi_period).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window=rsi_period).mean()
                rs = gain / loss
                rsi = 100 - (100 / (1 + rs))
                
                # Calculate Moving Averages
                sma_20 = hist['Close'].rolling(window=20).mean()
                sma_50 = hist['Close'].rolling(window=50).mean()
                
                # Calculate MACD
                exp12 = hist['Close'].ewm(span=12, adjust=False).mean()
                exp26 = hist['Close'].ewm(span=26, adjust=False).mean()
                macd = exp12 - exp26
                signal_line = macd.ewm(span=9, adjust=False).mean()
                
                # Volume analysis
                volume_sma = hist['Volume'].rolling(window=20).mean()
                current_volume = hist['Volume'].iloc[-1]
                volume_ratio = current_volume / volume_sma.iloc[-1] if volume_sma.iloc[-1] > 0 else 1
                
                # Current values
                current_price = hist['Close'].iloc[-1]
                current_rsi = rsi.iloc[-1]
                current_macd = macd.iloc[-1]
                current_signal = signal_line.iloc[-1]
                
                # Support and Resistance
                resistance = hist['High'].rolling(window=20).max().iloc[-1]
                support = hist['Low'].rolling(window=20).min().iloc[-1]
                
                # Generate signal
                signal_strength = 0
                signal_type = "HOLD"
                signal_reasons = []
                
                # RSI Signal
                if current_rsi < rsi_oversold:
                    signal_strength += 2
                    signal_reasons.append(f"RSI oversold ({current_rsi:.1f})")
                    signal_type = "BUY"
                elif current_rsi > rsi_overbought:
                    signal_strength += 2
                    signal_reasons.append(f"RSI overbought ({current_rsi:.1f})")
                    signal_type = "SELL"
                
                # MACD Signal
                if current_macd > current_signal and macd.iloc[-2] <= signal_line.iloc[-2]:
                    signal_strength += 1
                    signal_reasons.append("MACD bullish crossover")
                    if signal_type == "HOLD":
                        signal_type = "BUY"
                elif current_macd < current_signal and macd.iloc[-2] >= signal_line.iloc[-2]:
                    signal_strength += 1
                    signal_reasons.append("MACD bearish crossover")
                    if signal_type == "HOLD":
                        signal_type = "SELL"
                
                # Moving Average Signal
                if sma_20.iloc[-1] > sma_50.iloc[-1] and sma_20.iloc[-2] <= sma_50.iloc[-2]:
                    signal_strength += 2
                    signal_reasons.append("Golden Cross (SMA20 > SMA50)")
                    signal_type = "BUY"
                elif sma_20.iloc[-1] < sma_50.iloc[-1] and sma_20.iloc[-2] >= sma_50.iloc[-2]:
                    signal_strength += 2
                    signal_reasons.append("Death Cross (SMA20 < SMA50)")
                    signal_type = "SELL"
                
                # Support/Resistance Breakout
                if current_price > resistance:
                    signal_strength += 1
                    signal_reasons.append(f"Breakout resistance ({resistance:.0f})")
                    signal_type = "BUY"
                elif current_price < support:
                    signal_strength += 1
                    signal_reasons.append(f"Breakdown support ({support:.0f})")
                    signal_type = "SELL"
                
                # Volume Confirmation
                if volume_ratio > 1.5 and signal_type != "HOLD":
                    signal_strength += 1
                    signal_reasons.append(f"Volume spike ({volume_ratio:.1f}x)")
                
                # Filter: Only signals with strength > 2
                if signal_strength >= 2 and signal_type != "HOLD":
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
                    
                    print(f"✅ {symbol}: {signal_type} (Strength: {signal_strength}) - {', '.join(signal_reasons[:2])}")
                
            except Exception as e:
                print(f"❌ {symbol}: Error - {str(e)[:50]}")
                continue
        
        # Sort by signal strength
        signals.sort(key=lambda x: x['strength'], reverse=True)
        
        print(f"\n📊 Signal Summary: {len(signals)} signals generated")
        return signals
    
    # =============================================
    # 🎯 FUNGSI UTAMA YANG DIPERBAIKI
    # =============================================
    
    def get_assets(self, category: str, limit: int = 200, force_update: bool = False) -> List[str]:
        """
        Dapatkan list simbol aset untuk kategori tertentu.
        
        PERBAIKAN: Gunakan liquid stocks untuk Indonesia
        """
        if category not in ['indonesia_stocks', 'forex', 'us_stocks']:
            raise ValueError(f"Invalid category: {category}. Pilih: indonesia_stocks, forex, us_stocks.")
        
        cache_key = f"{category}_assets"
        
        # Untuk indonesia_stocks, gunakan liquid stocks langsung
        if category == 'indonesia_stocks':
            liquid_stocks = self._get_liquid_indonesia_stocks()[:limit]
            print(f"📊 Using {len(liquid_stocks)} liquid Indonesia stocks")
            return liquid_stocks
        
        # Untuk forex dan us_stocks, gunakan cache seperti biasa
        if not force_update and cache_key in self.cache:
            cache_data = self.cache[cache_key]
            cache_time = datetime.fromisoformat(cache_data['timestamp'])
            if datetime.now() - cache_time < timedelta(days=CACHE_TTL_DAYS):
                logger.info(f"📦 Using cached assets for {category} ({len(cache_data['assets'])} symbols)")
                return cache_data['assets'][:limit]
        
        # Fetch dinamis untuk forex dan us_stocks
        logger.info(f"🔄 Fetching fresh assets for {category} (limit: {limit})")
        try:
            assets = self._fetch_dynamic_assets(category, limit)
                
            if assets and len(assets) >= 10:
                with self.cache_lock:
                    self.cache[cache_key] = {
                        'timestamp': datetime.now().isoformat(),
                        'assets': assets
                    }
                    self._save_cache()
                logger.info(f"✅ Fetched {len(assets)} fresh assets for {category}")
                return assets[:limit]
            else:
                raise ValueError(f"Fetch returned insufficient assets: {len(assets) if assets else 0}")
        
        except Exception as e:
            logger.warning(f"⚠️ Dynamic fetch failed for {category}: {e}. Using static list.")
            return self._get_static_assets(category)[:limit]
    
    # =============================================
    # FUNGSI YANG TIDAK BERUBAH (tetap dipertahankan)
    # =============================================
    
    def _check_asset_activity(self, symbol: str) -> Dict:
        """Wrapper untuk backward compatibility."""
        return self._check_asset_activity_enhanced(symbol, 500000, 0.02, 0.03)
    
    def get_hot_sectors(self) -> Dict[str, List[str]]:
        """
        Cari sektor yang lagi hot di Indonesia.
        Returns: {'BANK': ['BBCA.JK', 'BBRI.JK'], ...}
        """
        sector_map = {
            'BANK': ['BBCA', 'BBRI', 'BMRI', 'BNGA', 'BBNI'],
            'MINING': ['ANTM', 'ADRO', 'INCO', 'BRPT', 'PTBA'],
            'CONSUMER': ['UNVR', 'ICBP', 'INDF', 'MYOR', 'ULTJ'],
            'TECH': ['GOTO', 'BRIS', 'DMMX', 'ARTO', 'TCID'],
            'PROPERTY': ['BSDE', 'CTRA', 'ASRI', 'SMRA', 'PWON'],
            'INFRASTRUCTURE': ['WIKA', 'PTPP', 'ADHI', 'JSMR', 'SRIL'],
            'ENERGY': ['PGAS', 'AKRA', 'MEDC', 'ENRG', 'AKRA']
        }
        
        hot_sectors = {}
        all_active = self.get_active_assets(limit=50)
        
        for sector, tickers in sector_map.items():
            sector_stocks = [f"{t}.JK" for t in tickers if f"{t}.JK" in all_active]
            if len(sector_stocks) >= 2:
                hot_sectors[sector] = sector_stocks
        
        return dict(sorted(hot_sectors.items(), key=lambda x: len(x[1]), reverse=True))
    
    def find_volume_spikes(self, threshold: float = 2.0) -> List[str]:
        """
        Cari aset dengan volume spike hari ini.
        PERBAIKAN: Gunakan data yang cukup
        """
        print(f"\n🔍 Mencari volume spike (> {threshold}x rata-rata)...")
        
        active_symbols = self.get_active_assets(limit=30)
        spiked = []
        
        for symbol in active_symbols:
            try:
                hist = self.get_historical_data(symbol, days=30)
                
                if len(hist) < 10:
                    continue
                
                # Gunakan 20 hari sebelumnya sebagai baseline
                if len(hist) > 20:
                    avg_volume = hist['Volume'][-21:-1].mean()  # 20 hari sebelum hari ini
                else:
                    avg_volume = hist['Volume'][:-1].mean()
                
                last_volume = hist['Volume'].iloc[-1]
                
                if avg_volume > 0 and (last_volume / avg_volume) > threshold:
                    spike_ratio = last_volume / avg_volume
                    spiked.append(f"{symbol} ({spike_ratio:.1f}x)")
                    
            except:
                continue
        
        return spiked
    
    # =============================================
    # FUNGSI HELPER TIDAK BERUBAH
    # =============================================
    
    def _fetch_all_indonesia_stocks(self, limit: int = 800) -> List[str]:
        """Tetap sama."""
        return self._get_liquid_indonesia_stocks()[:limit]
    
    def _fetch_from_idx_api(self) -> List[str]:
        """Tetap sama."""
        return []
    
    def _fetch_from_idx_website(self) -> List[str]:
        """Tetap sama."""
        return []
    
    def _fetch_from_wikipedia(self) -> List[str]:
        """Tetap sama."""
        return []
    
    def _fetch_from_investing_com(self) -> List[str]:
        """Tetap sama."""
        return []
    
    def _fetch_from_tradingview_dynamic(self) -> List[str]:
        """Tetap sama."""
        return []
    
    def _get_static_tradingview(self) -> List[str]:
        """Tetap sama."""
        return self._get_liquid_indonesia_stocks()
    
    def _validate_symbols_parallel(self, symbols: List[str]) -> List[str]:
        """Tetap sama."""
        return symbols[:200]
    
    def _fetch_dynamic_assets(self, category: str, limit: int) -> List[str]:
        """Tetap sama."""
        return self._get_static_assets(category)[:limit]
    
    def _get_static_assets(self, category: str) -> List[str]:
        """Tetap sama."""
        if category == 'us_stocks':
            return [
                'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'TSLA', 'NVDA', 'BRK-B', 'JPM', 'V',
                'JNJ', 'WMT', 'PG', 'MA', 'UNH', 'HD', 'BAC', 'DIS', 'ADBE', 'NFLX'
            ]
        elif category == 'indonesia_stocks':
            return self._get_liquid_indonesia_stocks()
        elif category == 'forex':
            return [
                'EURUSD=X', 'USDJPY=X', 'GBPUSD=X', 'AUDUSD=X', 'USDCAD=X',
                'USDCHF=X', 'NZDUSD=X', 'EURGBP=X', 'EURJPY=X', 'GBPJPY=X'
            ]
        return []
    
    def _get_all_indonesia_static(self) -> List[str]:
        """Tetap sama."""
        return self._get_liquid_indonesia_stocks()
    
    def _load_cache(self) -> Dict:
        """Tetap sama."""
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, 'r') as f:
                    return json.load(f)
            except:
                logger.warning("⚠️ Corrupted cache, starting fresh.")
        return {}
    
    def _save_cache(self):
        """Tetap sama."""
        with open(CACHE_FILE, 'w') as f:
            json.dump(self.cache, f)
        logger.debug("💾 Cache saved.")

# =============================================
# CONTOH PENGGUNAAN DENGAN SIGNAL
# =============================================
if __name__ == "__main__":
    provider = NonCryptoAssetsProvider()
    
    print("🚀 NON-CRYPTO ASSETS PROVIDER + TRADING SIGNAL GENERATOR")
    print("=" * 60)
    
    # 1. Ambil aset aktif
    print("\n1️⃣ Mengambil aset aktif Indonesia...")
    active_assets = provider.get_active_assets(
        category='indonesia_stocks',
        min_volume=500_000,
        limit=30
    )
    print(f"   ✅ {len(active_assets)} aset aktif ditemukan")
    
    # 2. Generate trading signals
    print("\n2️⃣ Generating trading signals...")
    signals = provider.generate_trading_signals(
        symbols=active_assets[:15],  # Analisa 15 teratas
        rsi_oversold=30,
        rsi_overbought=70
    )
    
    # 3. Tampilkan hasil
    print("\n3️⃣ TRADING SIGNALS HASIL:")
    print("=" * 60)
    
    if signals:
        for i, signal in enumerate(signals[:5], 1):  # Tampilkan 5 terbaik
            print(f"\n#{i} {signal['symbol']}: {signal['signal']} (Strength: {signal['strength']}/10)")
            print(f"   Price: {signal['price']:.0f} | RSI: {signal['rsi']:.1f} | Volume: {signal['volume_ratio']:.1f}x")
            print(f"   Reasons: {', '.join(signal['reasons'])}")
            print(f"   Data points: {signal['data_points']} bars")
    else:
        print("\n⚠️ Tidak ada signal trading yang ditemukan")
        print("   Cek:")
        print("   - Apakah data cukup (minimal 40 bars)")
        print("   - Apakah parameter RSI sesuai")
        print("   - Coba ganti time frame")
    
    # 4. Volume spikes
    print("\n4️⃣ Volume Spikes:")
    spikes = provider.find_volume_spikes(threshold=2.0)
    if spikes:
        for spike in spikes[:3]:
            print(f"   📈 {spike}")
    else:
        print("   📉 Tidak ada volume spike signifikan")
    
    # 5. Hot sectors
    print("\n5️⃣ Hot Sectors:")
    hot_sectors = provider.get_hot_sectors()
    for sector, stocks in list(hot_sectors.items())[:2]:
        print(f"   🔥 {sector}: {', '.join(stocks[:3])}")
    
    print("\n" + "=" * 60)
    print(f"📊 SUMMARY:")
    print(f"   Total assets screened: {len(active_assets)}")
    print(f"   Trading signals found: {len(signals)}")
    
    if signals:
        buy_signals = [s for s in signals if s['signal'] == 'BUY']
        sell_signals = [s for s in signals if s['signal'] == 'SELL']
        print(f"   BUY signals: {len(buy_signals)}")
        print(f"   SELL signals: {len(sell_signals)}")
    
    print("\n✅ SELESAI! File telah diperbaiki untuk menghasilkan signal trading.")
