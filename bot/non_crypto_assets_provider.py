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
        
    def get_assets(self, category: str, limit: int = 200, force_update: bool = False) -> List[str]:
        """
        Dapatkan list simbol aset untuk kategori tertentu.
        
        Args:
            category: 'indonesia_stocks', 'forex', atau 'us_stocks'.
            limit: Maksimal jumlah simbol (default 200).
            force_update: Jika True, force fetch ulang dari API (ignore cache).
        
        Returns:
            List[str]: List simbol (misalnya ['BBCA.JK', 'BBRI.JK'] untuk indo stocks).
        """
        if category not in ['indonesia_stocks', 'forex', 'us_stocks']:
            raise ValueError(f"Invalid category: {category}. Pilih: indonesia_stocks, forex, us_stocks.")
        
        cache_key = f"{category}_assets"
        
        # Cek cache jika tidak force update
        if not force_update and cache_key in self.cache:
            cache_data = self.cache[cache_key]
            cache_time = datetime.fromisoformat(cache_data['timestamp'])
            if datetime.now() - cache_time < timedelta(days=CACHE_TTL_DAYS):
                logger.info(f"📦 Using cached assets for {category} ({len(cache_data['assets'])} symbols)")
                return cache_data['assets'][:limit]
        
        # Fetch dinamis
        logger.info(f"🔄 Fetching fresh assets for {category} (limit: {limit})")
        try:
            if category == 'indonesia_stocks':
                assets = self._fetch_all_indonesia_stocks(limit)
            else:
                assets = self._fetch_dynamic_assets(category, limit)
                
            if assets and len(assets) >= 20:  # Minimal validasi
                # Filter out invalid symbols yang sudah diketahui
                assets = [s for s in assets if s not in self.invalid_symbols]
                
                # Simpan ke cache
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
            logger.warning(f"⚠️ Dynamic fetch failed for {category}: {e}. Falling back to static list.")
            # Fallback ke list statis
            static_assets = self._get_static_assets(category)
            # Filter invalid symbols dari static list juga
            static_assets = [s for s in static_assets if s not in self.invalid_symbols]
            return static_assets[:limit]

    # =============================================
    # 🎯 NEW: FUNGSI SCREENER UNTUK ASET AKTIF
    # =============================================
    
    def get_active_assets(self, category: str = 'indonesia_stocks',
                         min_volume: float = 1_000_000,
                         min_volatility: float = 0.025,
                         min_price_change: float = 0.05,
                         limit: int = 50) -> List[str]:
        """
        🚨 PENTING: Ambil HANYA aset yang aktif/rame untuk analisa!
        Jangan analisa semua aset, waste of time!
        
        Args:
            category: 'indonesia_stocks', 'forex', 'us_stocks'
            min_volume: Volume minimal per hari (default 1 juta)
            min_volatility: Volatilitas minimal (2.5% = 0.025)
            min_price_change: Perubahan harga minimal dalam periode
            limit: Jumlah aset teraktif yang diambil
            
        Returns:
            List[str]: Simbol aset paling aktif untuk dianalisa
        """
        print(f"\n🔥 SCREENING ASET AKTIF ({category})")
        print("=" * 60)
        
        # 1. Ambil semua aset dulu
        all_assets = self.get_assets(category, limit=800 if category == 'indonesia_stocks' else 200)
        print(f"📊 Total aset: {len(all_assets)}")
        
        # 2. Filter yang aktif
        print(f"🔍 Screening untuk aset aktif (vol > {min_volume:,})...")
        
        # Untuk Indonesia stocks, screening lebih detail
        if category == 'indonesia_stocks':
            active_assets = self._screen_indonesia_stocks(
                all_assets, min_volume, min_volatility, min_price_change, limit
            )
        else:
            # Untuk forex/US stocks, pakai list statis yang sudah aktif
            active_assets = self._get_predefined_active(category, limit)
        
        print(f"✅ Ditemukan {len(active_assets)} aset aktif")
        print(f"🎯 Analisa ini saja: {active_assets[:10]}...")
        
        return active_assets
    
    def _screen_indonesia_stocks(self, symbols: List[str],
                               min_volume: float,
                               min_volatility: float,
                               min_price_change: float,
                               limit: int) -> List[str]:
        """Screening khusus saham Indonesia."""
        if not symbols:
            return []
        
        # Ambil 300 teratas dulu (yang biasanya lebih liquid)
        symbols_to_check = symbols[:300]
        
        results = []
        print(f"📈 Analisis {len(symbols_to_check)} saham teratas...")
        
        # Pakai threadpool untuk lebih cepat
        with ThreadPoolExecutor(max_workers=10) as executor:
            future_to_symbol = {
                executor.submit(self._check_asset_activity, s): s 
                for s in symbols_to_check
            }
            
            completed = 0
            for future in as_completed(future_to_symbol):
                completed += 1
                if completed % 50 == 0:
                    print(f"   Progress: {completed}/{len(symbols_to_check)}")
                
                symbol = future_to_symbol[future]
                try:
                    metrics = future.result(timeout=5)
                    if metrics and metrics['active']:
                        results.append({
                            'symbol': symbol,
                            'score': metrics['score'],
                            'volume': metrics['avg_volume'],
                            'volatility': metrics['volatility'],
                            'change': metrics['price_change']
                        })
                except:
                    continue
        
        # Sort by score
        results.sort(key=lambda x: x['score'], reverse=True)
        
        # Filter tambahan
        filtered = []
        for r in results:
            if (r['volume'] >= min_volume and
                r['volatility'] >= min_volatility and
                abs(r['change']) >= min_price_change):
                filtered.append(r['symbol'])
        
        return filtered[:limit]
    
    def _check_asset_activity(self, symbol: str) -> Dict:
        """Cek aktivitas 1 aset."""
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="15d", interval="1d")
            
            if hist.empty or len(hist) < 5:
                return {'active': False}
            
            # Metrics dasar
            avg_volume = hist['Volume'].mean()
            if avg_volume < 100_000:  # Skip yang sepi banget
                return {'active': False}
            
            # Volatilitas
            returns = hist['Close'].pct_change().dropna()
            volatility = returns.std() if len(returns) > 1 else 0
            
            # Price movement
            price_change = (hist['Close'].iloc[-1] - hist['Close'].iloc[0]) / hist['Close'].iloc[0]
            
            # Volume spike hari ini (jika ada)
            volume_spike = False
            if len(hist) > 5:
                avg_prev_volume = hist['Volume'][:-1].mean()
                last_volume = hist['Volume'].iloc[-1]
                volume_spike = last_volume > avg_prev_volume * 1.5
            
            # Hitung score
            score = (
                (np.log10(avg_volume + 1) * 0.4) +          # Volume (40%)
                (min(volatility * 100, 10) * 0.3) +         # Volatility (30%)
                (abs(price_change) * 100 * 0.2) +           # Price change (20%)
                (10 if volume_spike else 0) * 0.1           # Volume spike (10%)
            )
            
            return {
                'active': True,
                'score': score,
                'avg_volume': avg_volume,
                'volatility': volatility,
                'price_change': price_change,
                'volume_spike': volume_spike
            }
            
        except Exception as e:
            return {'active': False}
    
    def _get_predefined_active(self, category: str, limit: int) -> List[str]:
        """Untuk forex/US stocks, pakai list yang sudah diketahui aktif."""
        if category == 'forex':
            return [
                'EURUSD=X', 'USDJPY=X', 'GBPUSD=X', 'AUDUSD=X', 'USDCAD=X',
                'USDCHF=X', 'NZDUSD=X', 'EURGBP=X', 'EURJPY=X', 'GBPJPY=X',
                'AUDJPY=X', 'EURCHF=X', 'GBPCHF=X', 'AUDNZD=X', 'NZDJPY=X'
            ][:limit]
        elif category == 'us_stocks':
            # S&P 500 top movers
            return [
                'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'TSLA', 'NVDA', 'AMD', 'NFLX',
                'JPM', 'V', 'MA', 'JNJ', 'WMT', 'PG', 'UNH', 'HD', 'BAC', 'DIS', 'ADBE',
                'INTC', 'CSCO', 'PEP', 'CMCSA', 'T', 'XOM', 'CVX', 'ABT', 'KO', 'AVGO',
                'MRK', 'COST', 'ABBV', 'TMO', 'DHR', 'MCD', 'NKE', 'ACN', 'ADP', 'BMY'
            ][:limit]
        return []
    
    def get_hot_sectors(self) -> Dict[str, List[str]]:
        """
        Cari sektor yang lagi hot di Indonesia.
        Returns: {'BANK': ['BBCA.JK', 'BBRI.JK'], ...}
        """
        sector_map = {
            'BANK': ['BBCA', 'BBRI', 'BMRI', 'BNGA', 'BBNI', 'BCA'],
            'MINING': ['ANTM', 'ADRO', 'INCO', 'BRPT', 'PTBA', 'MDKA'],
            'CONSUMER': ['UNVR', 'ICBP', 'INDF', 'MYOR', 'ULTJ', 'STAR'],
            'TECH': ['GOTO', 'BRIS', 'DMMX', 'ARTO', 'TCID', 'DNET'],
            'PROPERTY': ['BSDE', 'CTRA', 'ASRI', 'SMRA', 'LWSA', 'PWON'],
            'INFRASTRUCTURE': ['WIKA', 'PTPP', 'ADHI', 'WEGE', 'JSMR', 'SRIL'],
            'ENERGY': ['PGAS', 'AKRA', 'MEDC', 'ENRG', 'AKRA', 'PGAS']
        }
        
        hot_sectors = {}
        all_active = self.get_active_assets(limit=100)
        
        for sector, tickers in sector_map.items():
            sector_stocks = [f"{t}.JK" for t in tickers if f"{t}.JK" in all_active]
            if len(sector_stocks) >= 2:  # Minimal 2 saham aktif di sektor itu
                hot_sectors[sector] = sector_stocks
        
        # Urutkan berdasarkan jumlah saham aktif
        return dict(sorted(hot_sectors.items(), key=lambda x: len(x[1]), reverse=True))
    
    def find_volume_spikes(self, threshold: float = 2.0) -> List[str]:
        """
        Cari aset dengan volume spike hari ini (> threshold x rata-rata)
        """
        print(f"\n🔍 Mencari volume spike (> {threshold}x rata-rata)...")
        
        active_symbols = self.get_active_assets(limit=100)
        spiked = []
        
        for symbol in active_symbols[:50]:  # Cek 50 teraktif dulu
            try:
                ticker = yf.Ticker(symbol)
                hist = ticker.history(period="5d")
                
                if len(hist) < 3:
                    continue
                
                avg_volume = hist['Volume'][:-1].mean()
                last_volume = hist['Volume'].iloc[-1]
                
                if avg_volume > 0 and (last_volume / avg_volume) > threshold:
                    spiked.append(f"{symbol} ({last_volume/avg_volume:.1f}x)")
                    
            except:
                continue
        
        return spiked

    # =============================================
    # FUNGSI LAMA (tetap dipertahankan)
    # =============================================
    
    def _fetch_all_indonesia_stocks(self, limit: int = 800) -> List[str]:
        """
        Fetch SEMUA saham Indonesia dari IDX.
        Menggunakan multiple sources dan validasi paralel.
        """
        try:
            all_symbols = set()
            
            # Source 1: IDX API Official (Semua perusahaan tercatat) - Improve dengan retry
            for attempt in range(3):  # Retry 3 kali
                try:
                    idx_symbols = self._fetch_from_idx_api()
                    all_symbols.update(idx_symbols)
                    logger.info(f"✅ Fetched {len(idx_symbols)} symbols from IDX API")
                    break
                except Exception as e:
                    logger.warning(f"IDX API failed (attempt {attempt+1}): {e}")
                    time.sleep(2)  # Delay retry
            
            # Source 2: IDX Website scraping - Improve headers anti-block
            for attempt in range(3):
                try:
                    idx_web_symbols = self._fetch_from_idx_website()
                    all_symbols.update(idx_web_symbols)
                    logger.info(f"✅ Fetched {len(idx_web_symbols)} symbols from IDX website")
                    break
                except Exception as e:
                    logger.warning(f"IDX website failed (attempt {attempt+1}): {e}")
                    time.sleep(2)
            
            # Source 3: Wikipedia (backup) - Sudah OK, tambah retry
            for attempt in range(3):
                try:
                    wiki_symbols = self._fetch_from_wikipedia()
                    all_symbols.update(wiki_symbols)
                    logger.info(f"✅ Fetched {len(wiki_symbols)} symbols from Wikipedia")
                    break
                except Exception as e:
                    logger.warning(f"Wikipedia failed (attempt {attempt+1}): {e}")
                    time.sleep(2)
            
            # Source 4: Investing.com (NEW ALTERNATIVE) - Scrape untuk list saham ID lengkap
            try:
                investing_symbols = self._fetch_from_investing_com()
                all_symbols.update(investing_symbols)
                logger.info(f"✅ Fetched {len(investing_symbols)} symbols from Investing.com")
            except Exception as e:
                logger.warning(f"Investing.com failed: {e}")
            
            # Source 5: TradingView (dinamis-kan dari statis) - Ubah jadi scrape jika possible
            try:
                tv_symbols = self._fetch_from_tradingview_dynamic()  # NEW: Dinamis scrape
                all_symbols.update(tv_symbols)
                logger.info(f"✅ Fetched {len(tv_symbols)} symbols from TradingView")
            except Exception as e:
                logger.warning(f"TradingView dynamic failed: {e}, using static fallback")
                tv_symbols = self._get_static_tradingview()  # Fallback ke statis asli
                all_symbols.update(tv_symbols)
            
            # Convert to list and format
            symbols_list = list(all_symbols)
            logger.info(f"📊 Total unique symbols collected: {len(symbols_list)}")
            
            # Validasi paralel dengan thread pool
            valid_symbols = self._validate_symbols_parallel(symbols_list[:limit*2])
            
            logger.info(f"✅ Validated {len(valid_symbols)} Indonesia stocks")
            return valid_symbols[:limit]
            
        except Exception as e:
            logger.error(f"All Indonesia stock fetch methods failed: {e}")
            # Fallback ke static list yang diperluas
            return self._get_all_indonesia_static()[:limit]
    
    def _fetch_from_idx_api(self) -> List[str]:
        """Fetch dari API resmi IDX."""
        symbols = []
        try:
            url = "https://www.idx.co.id/umbraco/Surface/ListedCompany/GetCompanyProfiles?length=2000&start=0"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'application/json, text/javascript, */*; q=0.01',
                'X-Requested-With': 'XMLHttpRequest',
                'Referer': 'https://www.idx.co.id/'
            }
            
            response = requests.get(url, headers=headers, timeout=15)
            if response.status_code == 200:
                data = response.json()
                if 'data' in data:
                    for company in data['data']:
                        symbol = company.get('KodeEmiten', '')
                        if symbol:
                            formatted = f"{symbol.strip().upper()}.JK"
                            symbols.append(formatted)
        except Exception as e:
            logger.error(f"IDX API error: {e}")
        
        return symbols
    
    def _fetch_from_idx_website(self) -> List[str]:
        """Scrape dari website IDX."""
        symbols = []
        try:
            url = "https://www.idx.co.id/listed-companies/company-profiles/"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            response = requests.get(url, headers=headers, timeout=15)
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                
                for link in soup.find_all('a'):
                    href = link.get('href', '')
                    if '/listed-companies/company-profiles/' in href and len(href) > 50:
                        parts = href.split('/')
                        if len(parts) >= 2:
                            symbol_part = parts[-2]
                            if symbol_part and len(symbol_part) <= 8:
                                symbols.append(f"{symbol_part.upper()}.JK")
        
        except Exception as e:
            logger.error(f"IDX website scrape error: {e}")
        
        return symbols
    
    def _fetch_from_wikipedia(self) -> List[str]:
        """Fetch dari Wikipedia IDX list."""
        symbols = []
        try:
            url = 'https://en.wikipedia.org/wiki/List_of_companies_listed_on_the_Indonesia_Stock_Exchange'
            
            for table_idx in range(0, 10):
                try:
                    tables = pd.read_html(url)
                    if table_idx < len(tables):
                        table = tables[table_idx]
                        
                        for col in table.columns:
                            col_lower = col.lower()
                            if 'code' in col_lower or 'symbol' in col_lower or 'kode' in col_lower or 'ticker' in col_lower:
                                col_data = table[col].dropna().astype(str)
                                for item in col_data:
                                    item_clean = item.strip().upper()
                                    if item_clean and len(item_clean) <= 8:
                                        if not item_clean.endswith('.JK'):
                                            item_clean += '.JK'
                                        symbols.append(item_clean)
                                break
                except:
                    continue
            
            symbols = list(set(symbols))
            
        except Exception as e:
            logger.error(f"Wikipedia fetch error: {e}")
        
        return symbols
    
    def _fetch_from_investing_com(self) -> List[str]:
        """Fetch dari Investing.com Indonesia equities."""
        symbols = []
        try:
            url = "https://id.investing.com/equities/indonesia"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept-Language': 'id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7'
            }
            
            response = requests.get(url, headers=headers, timeout=15)
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                
                table = soup.find('table', {'id': 'cross_rate_markets_stocks_1'})
                if table:
                    rows = table.find_all('tr')
                    for row in rows[1:]:
                        cols = row.find_all('td')
                        if len(cols) > 1:
                            symbol_tag = cols[1].find('a') if len(cols) > 1 else None
                            if symbol_tag:
                                symbol = symbol_tag.text.strip().upper()
                                if symbol and len(symbol) <= 8:
                                    symbols.append(f"{symbol}.JK")
            
            symbols = list(set(symbols))
            
        except Exception as e:
            logger.error(f"Investing.com scrape error: {e}")
        
        return symbols
    
    def _fetch_from_tradingview_dynamic(self) -> List[str]:
        """Dinamis scrape dari TradingView Indonesia stocks."""
        symbols = []
        try:
            url = "https://www.tradingview.com/markets/stocks-indonesia/market-movers-all-stocks/"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            response = requests.get(url, headers=headers, timeout=15)
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                
                rows = soup.find_all('tr', class_='tv-data-table__row')
                for row in rows:
                    symbol_tag = row.find('a', class_='tv-screener__symbol')
                    if symbol_tag:
                        symbol = symbol_tag.text.strip().upper()
                        if symbol and len(symbol) <= 8 and not symbol.endswith('.JK'):
                            symbols.append(f"{symbol}.JK")
            
            symbols = list(set(symbols))
            
        except Exception as e:
            logger.error(f"TradingView dynamic scrape error: {e}")
        
        return symbols
    
    def _get_static_tradingview(self) -> List[str]:
        """Fallback statis dari TradingView - versi ringkas."""
        return [
            'BBCA.JK', 'BBRI.JK', 'BMRI.JK', 'TLKM.JK', 'ASII.JK', 'UNVR.JK',
            'ICBP.JK', 'INDF.JK', 'ANTM.JK', 'ADRO.JK', 'AKRA.JK', 'AMRT.JK',
            'INCO.JK', 'BRPT.JK', 'SMGR.JK', 'PGAS.JK', 'KLBF.JK', 'CPIN.JK',
            'INTP.JK', 'BBNI.JK', 'BNGA.JK', 'BSDE.JK', 'BUKA.JK', 'GOTO.JK',
            'MDKA.JK', 'ITMG.JK', 'MNCN.JK', 'ERAA.JK', 'TPIA.JK', 'BUMI.JK',
            'CTRA.JK', 'EXCL.JK', 'HRUM.JK', 'JPFA.JK', 'JSMR.JK', 'KIJA.JK',
            'LPPF.JK', 'MEDC.JK', 'MYOR.JK', 'PTBA.JK', 'PTPP.JK', 'SIDO.JK',
            'SMRA.JK', 'SRIL.JK', 'TBIG.JK', 'TINS.JK', 'TOTO.JK', 'TPMA.JK',
            'ULTJ.JK', 'UNTR.JK', 'WIKA.JK', 'WSKT.JK', 'WSBP.JK', 'WEGE.JK',
            'WTON.JK', 'YPAS.JK', 'ACES.JK', 'ADMR.JK', 'AGRO.JK', 'AIMS.JK',
            'AKPI.JK', 'ALMI.JK', 'AMAG.JK', 'APLN.JK', 'ARNA.JK', 'ASSA.JK',
            'AUTO.JK', 'BATA.JK', 'BIMA.JK', 'BOLT.JK', 'BRMS.JK', 'BTEK.JK',
            'BTPN.JK', 'CARE.JK', 'CEKA.JK', 'CMNP.JK', 'CNTX.JK', 'COWL.JK',
            'CPRO.JK', 'CTTH.JK', 'DART.JK', 'DEWA.JK', 'DILD.JK', 'DNET.JK',
            'DSSA.JK', 'DVLA.JK', 'EKAD.JK', 'ELSA.JK', 'EMTK.JK', 'ENRG.JK',
            'ESSA.JK', 'ESTI.JK', 'EXSA.JK', 'FASW.JK', 'FILM.JK', 'GDST.JK',
            'GEMA.JK', 'GGRM.JK', 'GJTL.JK', 'GLOB.JK', 'GOLD.JK', 'GTBO.JK',
            'HDFA.JK', 'HEAL.JK', 'HELI.JK', 'HERO.JK', 'HITS.JK', 'HMSP.JK',
            'HOME.JK', 'ICON.JK', 'IFII.JK', 'IGAR.JK', 'IIKP.JK', 'IKAI.JK',
            'IMAS.JK', 'INAF.JK', 'INAI.JK', 'INCF.JK', 'INDX.JK', 'INKP.JK',
            'INPC.JK', 'INPP.JK', 'INPS.JK', 'INRU.JK', 'INTA.JK', 'IPCC.JK',
            'ISAT.JK', 'ITIC.JK', 'JAST.JK', 'JECC.JK', 'JIHD.JK', 'JKON.JK',
            'KBLI.JK', 'KBLM.JK', 'KDSI.JK', 'KKGI.JK', 'KOIN.JK', 'KPAL.JK',
            'KRAS.JK', 'LION.JK', 'LMAS.JK', 'LMPI.JK', 'LPCK.JK', 'LSIP.JK',
            'LTLS.JK', 'MABA.JK', 'MAGP.JK', 'MAIN.JK', 'MAPI.JK', 'MASA.JK',
            'MBAP.JK', 'MBSS.JK', 'MCAS.JK', 'MDIA.JK', 'MEGA.JK', 'MERK.JK',
            'MFIN.JK', 'MIKA.JK', 'MLBI.JK', 'MLIA.JK', 'MLPL.JK', 'MMLP.JK',
            'MPMX.JK', 'MRAT.JK', 'MTDL.JK', 'MTFN.JK', 'MYOH.JK', 'MYRX.JK',
            'NATO.JK', 'NFCX.JK', 'NIKL.JK', 'NIPS.JK', 'NOVO.JK', 'NRCA.JK',
            'OKAS.JK', 'OPMS.JK', 'PALM.JK', 'PANI.JK', 'PANS.JK', 'PBRX.JK',
            'PCAR.JK', 'PEHA.JK', 'PGLI.JK', 'PICO.JK', 'PJAA.JK', 'PKPK.JK',
            'PLAS.JK', 'PLIN.JK', 'PMJS.JK', 'PNBN.JK', 'PNBS.JK', 'PNIN.JK',
            'PNLF.JK', 'POLA.JK', 'POLU.JK', 'POWR.JK', 'PPRE.JK', 'PRAS.JK',
            'PRDA.JK', 'PSAB.JK', 'PSDN.JK', 'PSGO.JK', 'PTIS.JK', 'PTPW.JK',
            'PTRO.JK', 'PURI.JK', 'PWON.JK', 'PYFA.JK', 'RAJA.JK', 'RALS.JK',
            'RANC.JK', 'RBMS.JK', 'RDTX.JK', 'REAL.JK', 'RICY.JK', 'RIGS.JK',
            'RIMO.JK', 'RODA.JK', 'RONY.JK', 'ROTI.JK', 'RSGK.JK', 'RUIS.JK',
            'SAFE.JK', 'SAME.JK', 'SAMF.JK', 'SAPX.JK', 'SATU.JK', 'SBAT.JK',
            'SCCO.JK', 'SCMA.JK', 'SCNP.JK', 'SDMU.JK', 'SDPC.JK', 'SFAN.JK',
            'SGER.JK', 'SGRO.JK', 'SHID.JK', 'SIDO.JK', 'SILO.JK', 'SIMA.JK',
            'SIMP.JK', 'SIPD.JK', 'SKBM.JK', 'SKLT.JK', 'SKRN.JK', 'SKYB.JK',
            'SLIS.JK', 'SMBR.JK', 'SMCB.JK', 'SMMA.JK', 'SMMT.JK', 'SMRA.JK',
            'SMSM.JK', 'SNLK.JK', 'SOCI.JK', 'SOSS.JK', 'SOTS.JK', 'SPTO.JK',
            'SQMI.JK', 'SRSN.JK', 'SRTG.JK', 'SSIA.JK', 'SSMS.JK', 'SSTM.JK',
            'STAR.JK', 'STTP.JK', 'SUGI.JK', 'SULI.JK', 'SUPR.JK', 'SURY.JK',
            'SWAT.JK', 'TALF.JK', 'TAMA.JK', 'TAPG.JK', 'TARA.JK', 'TAXI.JK',
            'TBLA.JK', 'TCID.JK', 'TCPI.JK', 'TDPM.JK', 'TELE.JK', 'TFAS.JK',
            'TFCO.JK', 'TGKA.JK', 'TGRA.JK', 'TIFA.JK', 'TIRT.JK', 'TKIM.JK',
            'TLDN.JK', 'TMAS.JK', 'TMPO.JK', 'TOWR.JK', 'TOYS.JK', 'TRIO.JK',
            'TRIS.JK', 'TRST.JK', 'TRUB.JK', 'TSPC.JK', 'TUGU.JK', 'TUNA.JK',
            'UCID.JK', 'UFOE.JK', 'UNIC.JK', 'UNIT.JK', 'UNSP.JK', 'URBN.JK',
            'VICI.JK', 'VINS.JK', 'VIVA.JK', 'VOKS.JK', 'VRNA.JK', 'WAPO.JK',
            'WEHA.JK', 'WICO.JK', 'WIFI.JK', 'WINS.JK', 'WMPP.JK', 'WOOD.JK',
            'WOWS.JK', 'WSBP.JK', 'WSKT.JK', 'WTON.JK', 'YELO.JK', 'YPAS.JK',
            'ZBRA.JK', 'ZONE.JK'
        ]
    
    def _validate_symbols_parallel(self, symbols: List[str]) -> List[str]:
        """Validasi paralel symbols."""
        valid_symbols = []
        
        def validate_symbol(symbol):
            try:
                info = yf.Ticker(symbol).info
                if info and 'regularMarketPrice' in info and info['regularMarketPrice'] is not None:
                    return symbol
                else:
                    self.invalid_symbols.add(symbol)
                    return None
            except:
                self.invalid_symbols.add(symbol)
                return None
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(validate_symbol, s) for s in symbols]
            for future in concurrent.futures.as_completed(futures):
                result = future.result()
                if result:
                    valid_symbols.append(result)
        
        return valid_symbols
    
    def _fetch_dynamic_assets(self, category: str, limit: int) -> List[str]:
        """Fetch dinamis untuk forex dan us_stocks."""
        if category == 'us_stocks':
            return self._get_static_assets(category)
        elif category == 'forex':
            return self._get_static_assets(category)
        return []
    
    def _get_static_assets(self, category: str) -> List[str]:
        """List statis sebagai fallback."""
        if category == 'us_stocks':
            return [
                'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'TSLA', 'NVDA', 'BRK-B', 'JPM', 'V',
                'JNJ', 'WMT', 'PG', 'MA', 'UNH', 'HD', 'BAC', 'DIS', 'ADBE', 'NFLX',
                'CMCSA', 'PEP', 'CSCO', 'INTC', 'T', 'PFE', 'XOM', 'CVX', 'ABT', 'KO',
                'AVGO', 'MRK', 'COST', 'ABBV', 'TMO', 'DHR', 'MCD', 'NKE', 'ACN', 'ADP',
                'BMY', 'LLY', 'LIN', 'UPS', 'RTX', 'UNP', 'PM', 'TXN', 'SCHW', 'CVS',
                'LOW', 'DE', 'CAT', 'MDT', 'AMGN', 'GILD', 'CI', 'BKNG', 'PLD', 'SPGI',
                'AXP', 'INTU', 'ISRG', 'SBUX', 'GS', 'BLK', 'MMM', 'BA', 'MO', 'IBM',
                'GE', 'F', 'GM', 'AMD', 'QCOM', 'ADI', 'MU', 'AMAT', 'LRCX', 'KLAC',
                'NXPI', 'SWKS', 'QRVO', 'MRVL', 'ANET', 'CDNS', 'SNPS', 'ADSK', 'TTWO',
                'EA', 'ATVI', 'TTD', 'ROKU', 'SPOT', 'PYPL', 'SQ', 'SHOP', 'MELI', 'SE'
            ]
        elif category == 'indonesia_stocks':
            return self._get_all_indonesia_static()
        elif category == 'forex':
            return [
                'EURUSD=X', 'USDJPY=X', 'GBPUSD=X', 'AUDUSD=X', 'USDCAD=X',
                'USDCHF=X', 'NZDUSD=X', 'EURGBP=X', 'EURJPY=X', 'GBPJPY=X',
                'AUDJPY=X', 'EURCHF=X', 'GBPCHF=X', 'AUDNZD=X', 'NZDJPY=X',
                'USDSGD=X', 'USDHKD=X', 'USDCNY=X', 'USDKRW=X', 'USDMYR=X'
            ]
        return []
    
    def _get_all_indonesia_static(self) -> List[str]:
        """Static list semua saham Indonesia."""
        all_indonesia_stocks = self._get_static_tradingview()
        return list(set(all_indonesia_stocks))
    
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
# CONTOH PENGGUNAAN
# =============================================
if __name__ == "__main__":
    provider = NonCryptoAssetsProvider()
    
    print("🚀 NON-CRYPTO ASSETS PROVIDER + SCREENER")
    print("=" * 60)
    
    # 1. Ambil aset aktif untuk analisa (INI YANG PENTING!)
    print("\n1️⃣ Ambil aset aktif Indonesia (untuk analisa):")
    active_assets = provider.get_active_assets(
        category='indonesia_stocks',
        min_volume=500_000,      # Minimal volume 500k
        min_volatility=0.03,     # Minimal volatilitas 3%
        limit=30                 # Ambil 30 teraktif
    )
    print(f"   ✅ {len(active_assets)} aset aktif: {active_assets[:10]}...")
    
    # 2. Cari volume spike
    print("\n2️⃣ Cari volume spike hari ini:")
    spikes = provider.find_volume_spikes(threshold=2.0)
    if spikes:
        for spike in spikes[:5]:
            print(f"   📈 {spike}")
    else:
        print("   📉 Tidak ada volume spike signifikan")
    
    # 3. Cari sektor hot
    print("\n3️⃣ Sektor yang lagi hot:")
    hot_sectors = provider.get_hot_sectors()
    for sector, stocks in list(hot_sectors.items())[:3]:
        print(f"   🔥 {sector}: {', '.join(stocks[:3])}")
    
    # 4. Contoh analisa teknikal (cuma untuk aset aktif)
    print("\n4️⃣ Mulai analisa teknikal untuk aset aktif:")
    for symbol in active_assets[:5]:  # Analisa 5 pertama dulu
        print(f"   📊 Analisa {symbol}...")
        # Tambahkan kode analisa teknikal kamu di sini
        # misal: RSI, MACD, Support/Resistance, dll
    
    print("\n🎯 SIMPULAN: Analisa cuma aset aktif, jangan semua!")
    print(f"   Total aset: {len(provider.get_assets('indonesia_stocks', limit=800))}")
    print(f"   Aset aktif: {len(active_assets)}")
    print(f"   Efisiensi: {len(active_assets)/800*100:.1f}% lebih cepat!")
    
    # Simpan cache
    provider._save_cache()
