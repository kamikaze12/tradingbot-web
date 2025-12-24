import json
import os
from datetime import datetime, timedelta
import logging
import yfinance as yf  # Tetap pakai untuk validasi minimal (quick check), tapi bisa dihapus jika ingin pure non-yfinance
import ccxt
import pandas as pd
from typing import List, Dict, Optional, Set
import requests
from bs4 import BeautifulSoup
import time
import concurrent.futures
from threading import Lock

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
            
            # Validasi paralel dengan thread pool - Improve: Tambah check minimal data (gratis, tanpa full OHLCV)
            valid_symbols = self._validate_symbols_parallel(symbols_list[:limit*2])
            
            logger.info(f"✅ Validated {len(valid_symbols)} Indonesia stocks")
            return valid_symbols[:limit]
            
        except Exception as e:
            logger.error(f"All Indonesia stock fetch methods failed: {e}")
            # Fallback ke static list yang diperluas
            return self._get_all_indonesia_static()[:limit]
    
    def _fetch_from_idx_api(self) -> List[str]:
        """Fetch dari API resmi IDX. - Improve: Tambah headers dan timeout."""
        symbols = []
        try:
            # URL untuk semua perusahaan tercatat
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
                            # Format: kode + .JK
                            formatted = f"{symbol.strip().upper()}.JK"
                            symbols.append(formatted)
        except Exception as e:
            logger.error(f"IDX API error: {e}")
        
        return symbols
    
    def _fetch_from_idx_website(self) -> List[str]:
        """Scrape dari website IDX. - Improve: Tambah headers anti-block."""
        symbols = []
        try:
            # Main page for listed companies
            url = "https://www.idx.co.id/listed-companies/company-profiles/"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            response = requests.get(url, headers=headers, timeout=15)
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Cari semua link yang mengandung kode saham
                for link in soup.find_all('a'):
                    href = link.get('href', '')
                    if '/listed-companies/company-profiles/' in href and len(href) > 50:
                        # Extract symbol dari URL
                        parts = href.split('/')
                        if len(parts) >= 2:
                            symbol_part = parts[-2]
                            if symbol_part and len(symbol_part) <= 8:
                                symbols.append(f"{symbol_part.upper()}.JK")
        
        except Exception as e:
            logger.error(f"IDX website scrape error: {e}")
        
        return symbols
    
    def _fetch_from_wikipedia(self) -> List[str]:
        """Fetch dari Wikipedia IDX list. - Improve: Cari multiple tables."""
        symbols = []
        try:
            url = 'https://en.wikipedia.org/wiki/List_of_companies_listed_on_the_Indonesia_Stock_Exchange'
            
            # Try multiple table indices
            for table_idx in range(0, 10):
                try:
                    tables = pd.read_html(url)
                    if table_idx < len(tables):
                        table = tables[table_idx]
                        
                        # Cari kolom yang berisi kode saham
                        for col in table.columns:
                            col_lower = col.lower()
                            if 'code' in col_lower or 'symbol' in col_lower or 'kode' in col_lower or 'ticker' in col_lower:
                                # Extract symbols
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
            
            # Remove duplicates
            symbols = list(set(symbols))
            
        except Exception as e:
            logger.error(f"Wikipedia fetch error: {e}")
        
        return symbols
    
    def _fetch_from_investing_com(self) -> List[str]:
        """NEW: Fetch dari Investing.com Indonesia equities - Scrape table untuk symbols lengkap."""
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
                
                # Cari table saham
                table = soup.find('table', {'id': 'cross_rate_markets_stocks_1'})  # ID table di Investing.com
                if table:
                    rows = table.find_all('tr')
                    for row in rows[1:]:  # Skip header
                        cols = row.find_all('td')
                        if len(cols) > 1:
                            # Kolom 1 biasanya nama, kolom 2 symbol/ticker
                            symbol_tag = cols[1].find('a') if len(cols) > 1 else None
                            if symbol_tag:
                                symbol = symbol_tag.text.strip().upper()
                                if symbol and len(symbol) <= 8:
                                    symbols.append(f"{symbol}.JK")
            
            # Remove duplicates
            symbols = list(set(symbols))
            
        except Exception as e:
            logger.error(f"Investing.com scrape error: {e}")
        
        return symbols
    
    def _fetch_from_tradingview_dynamic(self) -> List[str]:
        """NEW: Dinamis scrape dari TradingView Indonesia stocks - Alternatif gratis."""
        symbols = []
        try:
            url = "https://www.tradingview.com/markets/stocks-indonesia/market-movers-all-stocks/"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            response = requests.get(url, headers=headers, timeout=15)
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Cari symbols dari table
                rows = soup.find_all('tr', class_='tv-data-table__row')
                for row in rows:
                    symbol_tag = row.find('a', class_='tv-screener__symbol')
                    if symbol_tag:
                        symbol = symbol_tag.text.strip().upper()
                        if symbol and len(symbol) <= 8 and not symbol.endswith('.JK'):
                            symbols.append(f"{symbol}.JK")
            
            # Remove duplicates
            symbols = list(set(symbols))
            
        except Exception as e:
            logger.error(f"TradingView dynamic scrape error: {e}")
        
        return symbols
    
    def _get_static_tradingview(self) -> List[str]:
        """Fallback statis dari TradingView - Asli, tapi diperluas sedikit dari source publik."""
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
            'HDFA.JK', 'HEAL.JK', 'HELI.JK', 'HERO.JK', 'HIT...(truncated 9286 characters)...,
            'HELI.JK', 'HERO.JK', 'HITS.JK', 'HMSP.JK', 'HOME.JK', 'ICON.JK',
            'IFII.JK', 'IGAR.JK', 'IIKP.JK', 'IKAI.JK', 'IMAS.JK', 'INAF.JK',
            'INAI.JK', 'INCF.JK', 'INDX.JK', 'INKP.JK', 'INPC.JK', 'INPP.JK',
            'INPS.JK', 'INRU.JK', 'INTA.JK', 'IPCC.JK', 'ISAT.JK', 'ITIC.JK',
            'JAST.JK', 'JECC.JK', 'JIHD.JK', 'JKON.JK', 'KBLI.JK', 'KBLM.JK',
            'KDSI.JK', 'KKGI.JK', 'KOIN.JK', 'KPAL.JK', 'KRAS.JK', 'LION.JK',
            'LMAS.JK', 'LMPI.JK', 'LPCK.JK', 'LSIP.JK', 'LTLS.JK', 'MABA.JK',
            'MAGP.JK', 'MAIN.JK', 'MAPI.JK', 'MASA.JK', 'MBAP.JK', 'MBSS.JK',
            'MCAS.JK', 'MDIA.JK', 'MEGA.JK', 'MERK.JK', 'MFIN.JK', 'MIKA.JK',
            'MLBI.JK', 'MLIA.JK', 'MLPL.JK', 'MMLP.JK', 'MPMX.JK', 'MRAT.JK',
            'MTDL.JK', 'MTFN.JK', 'MYOH.JK', 'MYRX.JK', 'NATO.JK', 'NFCX.JK',
            'NIKL.JK', 'NIPS.JK', 'NOVO.JK', 'NRCA.JK', 'OKAS.JK', 'OPMS.JK',
            'PALM.JK', 'PANI.JK', 'PANS.JK', 'PBRX.JK', 'PCAR.JK', 'PEHA.JK',
            'PGLI.JK', 'PICO.JK', 'PJAA.JK', 'PKPK.JK', 'PLAS.JK', 'PLIN.JK',
            'PMJS.JK', 'PNBN.JK', 'PNBS.JK', 'PNIN.JK', 'PNLF.JK', 'POLA.JK',
            'POLU.JK', 'POWR.JK', 'PPRE.JK', 'PRAS.JK', 'PRDA.JK', 'PSAB.JK',
            'PSDN.JK', 'PSGO.JK', 'PTIS.JK', 'PTPW.JK', 'PTRO.JK', 'PURI.JK',
            'PWON.JK', 'PYFA.JK', 'RAJA.JK', 'RALS.JK', 'RANC.JK', 'RBMS.JK',
            'RDTX.JK', 'REAL.JK', 'RICY.JK', 'RIGS.JK', 'RIMO.JK', 'RODA.JK',
            'RONY.JK', 'ROTI.JK', 'RSGK.JK', 'RUIS.JK', 'SAFE.JK', 'SAME.JK',
            'SAMF.JK', 'SAPX.JK', 'SATU.JK', 'SBAT.JK', 'SCCO.JK', 'SCMA.JK',
            'SCNP.JK', 'SDMU.JK', 'SDPC.JK', 'SFAN.JK', 'SGER.JK', 'SGRO.JK',
            'SHID.JK', 'SIDO.JK', 'SILO.JK', 'SIMA.JK', 'SIMP.JK', 'SIPD.JK',
            'SKBM.JK', 'SKLT.JK', 'SKRN.JK', 'SKYB.JK', 'SLIS.JK', 'SMBR.JK',
            'SMCB.JK', 'SMMA.JK', 'SMMT.JK', 'SMRA.JK', 'SMSM.JK', 'SNLK.JK',
            'SOCI.JK', 'SOSS.JK', 'SOTS.JK', 'SPTO.JK', 'SQMI.JK', 'SRSN.JK',
            'SRTG.JK', 'SSIA.JK', 'SSMS.JK', 'SSTM.JK', 'STAR.JK', 'STTP.JK',
            'SUGI.JK', 'SULI.JK', 'SUPR.JK', 'SURY.JK', 'SWAT.JK', 'TALF.JK',
            'TAMA.JK', 'TAPG.JK', 'TARA.JK', 'TAXI.JK', 'TBLA.JK', 'TCID.JK',
            'TCPI.JK', 'TDPM.JK', 'TELE.JK', 'TFAS.JK', 'TFCO.JK', 'TGKA.JK',
            'TGRA.JK', 'TIFA.JK', 'TIRT.JK', 'TKIM.JK', 'TLDN.JK', 'TMAS.JK',
            'TMPO.JK', 'TOWR.JK', 'TOYS.JK', 'TRIO.JK', 'TRIS.JK', 'TRST.JK',
            'TRUB.JK', 'TSPC.JK', 'TUGU.JK', 'TUNA.JK', 'UCID.JK', 'UFOE.JK',
            'UNIC.JK', 'UNIT.JK', 'UNSP.JK', 'URBN.JK', 'VICI.JK', 'VINS.JK',
            'VIVA.JK', 'VOKS.JK', 'VRNA.JK', 'WAPO.JK', 'WEHA.JK', 'WICO.JK',
            'WIFI.JK', 'WINS.JK', 'WMPP.JK', 'WOOD.JK', 'WOWS.JK', 'YELO.JK',
            'ZBRA.JK', 'ZONE.JK',
            
            # Additional stocks from various sectors (diperluas dari source publik seperti Investing.com statis)
            'BNII.JK', 'BACA.JK', 'BBSI.JK', 'BJTM.JK', 'BJBR.JK', 'BKSW.JK',
            'BMAS.JK', 'BNBA.JK', 'BNLI.JK', 'BOGA.JK', 'BRIS.JK', 'BTEK.JK',
            'BVIC.JK', 'BABP.JK', 'BDMN.JK', 'BEKS.JK', 'BFIN.JK', 'BGTG.JK',
            'BHIT.JK', 'BINA.JK', 'BIPI.JK', 'BIRD.JK', 'BKKB.JK', 'BLTA.JK',
            'BMRI.JK', 'BNGA.JK', 'BOBA.JK', 'BRMS.JK', 'BSWD.JK', 'BTEL.JK',
            'BTPN.JK', 'BUDI.JK', 'CARE.JK', 'CASH.JK', 'CENT.JK', 'CFIN.JK',
            'CINT.JK', 'CITY.JK', 'CMRY.JK', 'CNTX.JK', 'COWL.JK', 'CSAP.JK',
            'CSIS.JK', 'CTRA.JK', 'CURR.JK', 'DART.JK', 'DAYA.JK', 'DEWA.JK',
            'DGIK.JK', 'DILD.JK', 'DIVA.JK', 'DKFT.JK', 'DMAS.JK', 'DMMX.JK',
            'DNAR.JK', 'DPNS.JK', 'DSNG.JK', 'DUCK.JK', 'DUTI.JK', 'DVLA.JK',
            'DWGL.JK', 'ECII.JK', 'EKAD.JK', 'ELSA.JK', 'ELTY.JK', 'EMDE.JK',
            'EMTK.JK', 'ENRG.JK', 'EPMT.JK', 'ERAA.JK', 'ESSA.JK', 'ESTI.JK',
            'ETWA.JK', 'EXCL.JK', 'FAST.JK', 'FASW.JK', 'FILM.JK', 'FIRE.JK',
            'FISH.JK', 'FITT.JK', 'FMII.JK', 'FORU.JK', 'FORZ.JK', 'FPNI.JK',
            'FREN.JK', 'FUJI.JK', 'GAMA.JK', 'GDST.JK', 'GEMA.JK', 'GEMS.JK',
            'GGRM.JK', 'GIAA.JK', 'GJTL.JK', 'GLOB.JK', 'GMFI.JK', 'GMTD.JK',
            'GOLD.JK', 'GOLL.JK', 'GPRA.JK', 'GSMF.JK', 'GTBO.JK', 'GTSI.JK',
            'GWSA.JK', 'HADE.JK', 'HAIS.JK', 'HDFA.JK', 'HDTX.JK', 'HEAL.JK',
            'HELI.JK', 'HERO.JK', 'HITS.JK', 'HKMU.JK', 'HMSP.JK', 'HOME.JK',
            'HOMI.JK', 'HOTL.JK', 'HRTA.JK', 'IATA.JK', 'IBFN.JK', 'IBST.JK',
            'ICON.JK', 'IDPR.JK', 'IFII.JK', 'IFSH.JK', 'IGAR.JK', 'IIKP.JK',
            'IKAI.JK', 'IKAN.JK', 'IMAS.JK', 'IMPC.JK', 'INAF.JK', 'INAI.JK',
            'INCF.JK', 'INCI.JK', 'INCO.JK', 'INDF.JK', 'INDO.JK', 'INDR.JK',
            'INDS.JK', 'INDX.JK', 'INDY.JK', 'INKP.JK', 'INPC.JK', 'INPP.JK',
            'INPS.JK', 'INRU.JK', 'INTA.JK', 'INTD.JK', 'INTP.JK', 'IPCC.JK',
            'IPCM.JK', 'IPOL.JK', 'ISAT.JK', 'ISSP.JK', 'ITIC.JK', 'ITMA.JK',
            'ITMG.JK', 'JAST.JK', 'JAWA.JK', 'JAYA.JK', 'JECC.JK', 'JGLE.JK',
            'JIHD.JK', 'JKON.JK', 'JKSW.JK', 'JMAS.JK', 'JPFA.JK', 'JRPT.JK',
            'JSMR.JK', 'JSPT.JK', 'JTPE.JK', 'KAEF.JK', 'KARW.JK', 'KBLI.JK',
            'KBLM.JK', 'KBRI.JK', 'KDSI.JK', 'KEEN.JK', 'KEJU.JK', 'KIJA.JK',
            'KINO.JK', 'KIOS.JK', 'KJEN.JK', 'KKGI.JK', 'KLBF.JK', 'KMDS.JK',
            'KMTR.JK', 'KOIN.JK', 'KONI.JK', 'KOPI.JK', 'KOTA.JK', 'KPAL.JK',
            'KPAS.JK', 'KPIG.JK', 'KRAS.JK', 'KREN.JK', 'LAND.JK', 'LAPD.JK',
            'LCGP.JK', 'LCKM.JK', 'LEAD.JK', 'LIFE.JK', 'LINK.JK', 'LION.JK',
            'LMAS.JK', 'LMPI.JK', 'LMSH.JK', 'LPCK.JK', 'LPGI.JK', 'LPIN.JK',
            'LPLI.JK', 'LPPF.JK', 'LPPS.JK', 'LRNA.JK', 'LSIP.JK', 'LTLS.JK',
            'LUCK.JK', 'MABA.JK', 'MAGP.JK', 'MAIN.JK', 'MAMI.JK', 'MAPA.JK',
            'MAPI.JK', 'MASA.JK', 'MAYA.JK', 'MBAP.JK', 'MBSS.JK', 'MCAS.JK',
            'MCOL.JK', 'MCOR.JK', 'MDIA.JK', 'MDKA.JK', 'MDLN.JK', 'MEDC.JK',
            'MEGA.JK', 'MERK.JK', 'META.JK', 'MFIN.JK', 'MGNA.JK', 'MICE.JK',
            'MIDI.JK', 'MIKA.JK', 'MINA.JK', 'MIRA.JK', 'MITI.JK', 'MKNT.JK',
            'MLBI.JK', 'MLIA.JK', 'MLPL.JK', 'MLPT.JK', 'MMLP.JK', 'MNCN.JK',
            'MOLI.JK', 'MPMX.JK', 'MPOW.JK', 'MPPA.JK', 'MRAT.JK', 'MREI.JK',
            'MSIN.JK', 'MSKY.JK', 'MTDL.JK', 'MTFN.JK', 'MTLA.JK', 'MTPS.JK',
            'MTSM.JK', 'MYOH.JK', 'MYOR.JK', 'MYRX.JK', 'MYTX.JK', 'NANO.JK',
            'NASA.JK', 'NATO.JK', 'NELY.JK', 'NFCX.JK', 'NICK.JK', 'NIKL.JK',
            'NIPS.JK', 'NISP.JK', 'NIRO.JK', 'NOVO.JK', 'NPGF.JK', 'NRCA.JK',
            'NUSA.JK', 'NZIA.JK', 'OASA.JK', 'OBMD.JK', 'OCAP.JK', 'OKAS.JK',
            'OMRE.JK', 'OPMS.JK', 'PADI.JK', 'PALM.JK', 'PAMG.JK', 'PANI.JK',
            'PANS.JK', 'PBRX.JK', 'PCAR.JK', 'PDES.JK', 'PEHA.JK', 'PGAS.JK',
            'PGLI.JK', 'PICO.JK', 'PJAA.JK', 'PKPK.JK', 'PLAS.JK', 'PLIN.JK',
            'PMJS.JK', 'PNBN.JK', 'PNBS.JK', 'PNIN.JK', 'PNLF.JK', 'POLA.JK',
            'POLU.JK', 'PONI.JK', 'PORT.JK', 'POWR.JK', 'PPRE.JK', 'PRAS.JK',
            'PRDA.JK', 'PRIM.JK', 'PSAB.JK', 'PSDN.JK', 'PSGO.JK', 'PSKT.JK',
            'PSSI.JK', 'PTBA.JK', 'PTIS.JK', 'PTPP.JK', 'PTPW.JK', 'PTRO.JK',
            'PTSN.JK', 'PURA.JK', 'PURI.JK', 'PWON.JK', 'PYFA.JK', 'RAJA.JK',
            'RALS.JK', 'RANC.JK', 'RBMS.JK', 'RDTX.JK', 'REAL.JK', 'RELI.JK',
            'RICY.JK', 'RIGS.JK', 'RIMO.JK', 'RISE.JK', 'ROCK.JK', 'RODA.JK',
            'RONY.JK', 'ROTI.JK', 'RSGK.JK', 'RUIS.JK', 'RUNS.JK', 'SAFE.JK',
            'SAME.JK', 'SAMF.JK', 'SAPX.JK', 'SATU.JK', 'SBAT.JK', 'SCCO.JK',
            'SCMA.JK', 'SCNP.JK', 'SCPI.JK', 'SDMU.JK', 'SDPC.JK', 'SDRA.JK',
            'SFAN.JK', 'SGER.JK', 'SGRO.JK', 'SHID.JK', 'SIDO.JK', 'SILO.JK',
            'SIMA.JK', 'SIMP.JK', 'SIPD.JK', 'SKBM.JK', 'SKLT.JK', 'SKRN.JK',
            'SKYB.JK', 'SLIS.JK', 'SMBR.JK', 'SMCB.JK', 'SMDR.JK', 'SMGR.JK',
            'SMKL.JK', 'SMMA.JK', 'SMMT.JK', 'SMRA.JK', 'SMSM.JK', 'SNLK.JK',
            'SOCI.JK', 'SOSS.JK', 'SOTS.JK', 'SPTO.JK', 'SQMI.JK', 'SRAJ.JK',
            'SRIL.JK', 'SRSN.JK', 'SRTG.JK', 'SSIA.JK', 'SSMS.JK', 'SSTM.JK',
            'STAR.JK', 'STTP.JK', 'SUGI.JK', 'SULI.JK', 'SUPR.JK', 'SURY.JK',
            'SWAT.JK', 'TALF.JK', 'TAMA.JK', 'TAPG.JK', 'TARA.JK', 'TAXI.JK',
            'TBIG.JK', 'TBLA.JK', 'TCID.JK', 'TCPI.JK', 'TDPM.JK', 'TEBE.JK',
            'TELE.JK', 'TFAS.JK', 'TFCO.JK', 'TGKA.JK', 'TGRA.JK', 'TIFA.JK',
            'TINS.JK', 'TIRT.JK', 'TKI.JK', 'TKIM.JK', 'TLDN.JK', 'TLKM.JK',
            'TMAS.JK', 'TMPO.JK', 'TOTO.JK', 'TOWR.JK', 'TOYS.JK', 'TPIA.JK',
            'TPMA.JK', 'TRIO.JK', 'TRIS.JK', 'TRST.JK', 'TRUB.JK', 'TSPC.JK',
            'TUGU.JK', 'TUNA.JK', 'UCID.JK', 'UFOE.JK', 'ULTJ.JK', 'UNIC.JK',
            'UNIT.JK', 'UNSP.JK', 'UNTR.JK', 'UNVR.JK', 'URBN.JK', 'VICI.JK',
            'VINS.JK', 'VIVA.JK', 'VOKS.JK', 'VRNA.JK', 'WAPO.JK', 'WEGE.JK',
            'WEHA.JK', 'WICO.JK', 'WIFI.JK', 'WIKA.JK', 'WINS.JK', 'WMPP.JK',
            'WOOD.JK', 'WOWS.JK', 'WSBP.JK', 'WSKT.JK', 'WTON.JK', 'YELO.JK',
            'YPAS.JK', 'ZBRA.JK', 'ZONE.JK', 'ZYRX.JK',
            # Tambahan dari source publik (Investing.com statis untuk fallback)
            'ABDA.JK', 'ABMM.JK', 'ACST.JK', 'ADHI.JK', 'AGII.JK', 'AGRS.JK', 'AHAP.JK', 'AISA.JK',
            'AKSI.JK', 'ALDO.JK', 'ALKA.JK', 'ALTO.JK', 'AMFG.JK', 'AMIN.JK', 'AMOR.JK', 'ANDI.JK',
            # ... (kamu bisa tambah lebih banyak dari list publik jika perlu, tapi ini cukup untuk contoh)
        ]
    
    def _validate_symbols_parallel(self, symbols: List[str]) -> List[str]:
        """Validasi paralel symbols - Improve: Tambah quick check jika symbol punya data minimal (gratis, pakai requests head check jika possible)."""
        valid_symbols = []
        
        def validate_symbol(symbol):
            try:
                # Quick check: Cek jika symbol exist di Yahoo (minimal, tanpa full download)
                # Note: Ini masih pakai yfinance minimal, jika ingin hapus, ganti dengan check URL IDX
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
        """Fetch dinamis untuk forex dan us_stocks - Tidak diubah, karena fokus saham ID."""
        # Kode asli tetap
        if category == 'us_stocks':
            # Contoh fetch dari API atau scrape (asli)
            return self._get_static_assets(category)  # Bisa diimprove mirip saham ID jika perlu
        elif category == 'forex':
            return self._get_static_assets(category)
        return []
    
    def _get_static_assets(self, category: str) -> List[str]:
        """List statis sebagai fallback. - Tidak diubah banyak."""
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
        """Static list semua saham Indonesia - Diperluas dari multiple sources."""
        all_indonesia_stocks = self._get_static_tradingview()  # Reuse dari statis TradingView
        return list(set(all_indonesia_stocks))  # Remove duplicates
    
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

# Contoh penggunaan jika run sebagai script
if __name__ == "__main__":
    provider = NonCryptoAssetsProvider()
    
    # Test SEMUA saham Indonesia
    indo_stocks = provider.get_assets('indonesia_stocks', limit=800, force_update=True)
    print(f"🎯 SEMUA Saham Indonesia ({len(indo_stocks)}):")
    print(f"First 20: {indo_stocks[:20]}")
    print(f"Last 20: {indo_stocks[-20:]}")
    
    # Test forex
    forex = provider.get_assets('forex', limit=100)
    print(f"\n📊 Forex Pairs ({len(forex)}): {forex[:10]}...")
    
    # Test US stocks
    us_stocks = provider.get_assets('us_stocks', limit=200)
    print(f"\n🇺🇸 US Stocks ({len(us_stocks)}): {us_stocks[:10]}...")
    
    # Simpan cache
    provider._save_cache()
