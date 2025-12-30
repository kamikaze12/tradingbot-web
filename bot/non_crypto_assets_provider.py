import json
import os
from datetime import datetime, timedelta
import logging
import yfinance as yf
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

# Import wrapper baru
try:
    from import_wrapper import (
        import_indonesia_stocks_scraper,
        import_investing_scraper,
        import_forex_scraper,
        import_binance_scraper
    )
    
    # Import scrapers
    IndonesiaStocksScraper = import_indonesia_stocks_scraper()
    INDONESIA_SCRAPER_AVAILABLE = IndonesiaStocksScraper is not None
    
    InvestingScraper = import_investing_scraper()
    INVESTING_SCRAPER_AVAILABLE = InvestingScraper is not None
    
    ForexGeneralScraper = import_forex_scraper()
    FOREX_SCRAPER_AVAILABLE = ForexGeneralScraper is not None
    
    BinanceScraper = import_binance_scraper()
    BINANCE_SCRAPER_AVAILABLE = BinanceScraper is not None
    
except Exception as e:
    logger.warning(f"Failed to import scrapers: {e}")
    INDONESIA_SCRAPER_AVAILABLE = False
    INVESTING_SCRAPER_AVAILABLE = False
    FOREX_SCRAPER_AVAILABLE = False
    BINANCE_SCRAPER_AVAILABLE = False

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
            
            # Source 2: IndonesiaStocksScraper (NEW)
            if INDONESIA_SCRAPER_AVAILABLE:
                for attempt in range(3):
                    try:
                        indo_scraper = IndonesiaStocksScraper()
                        indo_symbols = indo_scraper.fetch_stocks()
                        # Format symbols dengan .JK jika belum ada
                        formatted_symbols = []
                        for symbol in indo_symbols:
                            if isinstance(symbol, str) and symbol.strip():
                                symbol_clean = symbol.strip().upper()
                                if not symbol_clean.endswith('.JK'):
                                    symbol_clean += '.JK'
                                formatted_symbols.append(symbol_clean)
                        
                        all_symbols.update(formatted_symbols)
                        logger.info(f"✅ Fetched {len(formatted_symbols)} from IndonesiaStocksScraper")
                        break
                    except Exception as e:
                        logger.warning(f"IndonesiaStocksScraper failed (attempt {attempt+1}): {e}")
                        time.sleep(2)
            
            # Source 3: IDX Website scraping - Improve headers anti-block
            for attempt in range(3):
                try:
                    idx_web_symbols = self._fetch_from_idx_website()
                    all_symbols.update(idx_web_symbols)
                    logger.info(f"✅ Fetched {len(idx_web_symbols)} symbols from IDX website")
                    break
                except Exception as e:
                    logger.warning(f"IDX website failed (attempt {attempt+1}): {e}")
                    time.sleep(2)
            
            # Source 4: Wikipedia (backup) - Sudah OK, tambah retry
            for attempt in range(3):
                try:
                    wiki_symbols = self._fetch_from_wikipedia()
                    all_symbols.update(wiki_symbols)
                    logger.info(f"✅ Fetched {len(wiki_symbols)} symbols from Wikipedia")
                    break
                except Exception as e:
                    logger.warning(f"Wikipedia failed (attempt {attempt+1}): {e}")
                    time.sleep(2)
            
            # Source 5: Investing.com Scraper (NEW)
            if INVESTING_SCRAPER_AVAILABLE:
                try:
                    investing_scraper = InvestingScraper()
                    investing_symbols = []
                    
                    # Coba fetch dari metode yang tersedia
                    if hasattr(investing_scraper, 'fetch_indonesia_stocks'):
                        indo_stocks = investing_scraper.fetch_indonesia_stocks()
                        if indo_stocks:
                            investing_symbols.extend([f"{s.strip().upper()}.JK" for s in indo_stocks if s])
                    
                    if hasattr(investing_scraper, 'fetch_all_stocks'):
                        all_stocks = investing_scraper.fetch_all_stocks()
                        if all_stocks:
                            # Filter untuk saham Indonesia
                            for stock in all_stocks:
                                if isinstance(stock, dict) and 'symbol' in stock:
                                    symbol = stock.get('symbol', '').strip().upper()
                                    if symbol and len(symbol) <= 8:
                                        investing_symbols.append(f"{symbol}.JK")
                    
                    all_symbols.update(investing_symbols)
                    logger.info(f"✅ Fetched {len(investing_symbols)} symbols from Investing.com Scraper")
                except Exception as e:
                    logger.warning(f"Investing.com Scraper failed: {e}")
            
            # Source 6: TradingView (dinamis-kan dari statis)
            try:
                tv_symbols = self._fetch_from_tradingview_dynamic()
                all_symbols.update(tv_symbols)
                logger.info(f"✅ Fetched {len(tv_symbols)} symbols from TradingView")
            except Exception as e:
                logger.warning(f"TradingView dynamic failed: {e}, using static fallback")
                tv_symbols = self._get_static_tradingview()
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
            return self._fetch_us_stocks_dynamic(limit)
        elif category == 'forex':
            return self._fetch_forex_dynamic(limit)
        return []
    
    def _fetch_forex_dynamic(self, limit: int) -> List[str]:
        """Fetch dinamis untuk forex pairs."""
        forex_pairs = set()
        
        # Source 1: ForexGeneralScraper
        if FOREX_SCRAPER_AVAILABLE:
            try:
                forex_scraper = ForexGeneralScraper()
                if hasattr(forex_scraper, 'fetch_pairs'):
                    pairs = forex_scraper.fetch_pairs(limit)
                    # Format pairs untuk yfinance (tambahkan =X jika belum ada)
                    formatted_pairs = []
                    for pair in pairs:
                        if isinstance(pair, str) and pair.strip():
                            pair_clean = pair.strip().upper()
                            if 'USD' in pair_clean and not pair_clean.endswith('=X'):
                                pair_clean += '=X'
                            formatted_pairs.append(pair_clean)
                    
                    forex_pairs.update(formatted_pairs)
                    logger.info(f"✅ Fetched {len(formatted_pairs)} from ForexGeneralScraper")
            except Exception as e:
                logger.warning(f"ForexGeneralScraper failed: {e}")
        
        # Source 2: InvestingScraper untuk forex
        if INVESTING_SCRAPER_AVAILABLE:
            try:
                investing_scraper = InvestingScraper()
                if hasattr(investing_scraper, 'fetch_forex'):
                    investing_forex = investing_scraper.fetch_forex()
                    if investing_forex:
                        # Format pairs
                        formatted_investing = []
                        for pair in investing_forex:
                            if isinstance(pair, str) and pair.strip():
                                pair_clean = pair.strip().upper()
                                if 'USD' in pair_clean and not pair_clean.endswith('=X'):
                                    pair_clean += '=X'
                                formatted_investing.append(pair_clean)
                        
                        forex_pairs.update(formatted_investing)
                        logger.info(f"✅ Fetched {len(formatted_investing)} from Investing.com forex")
            except Exception as e:
                logger.warning(f"Investing.com forex fetch failed: {e}")
        
        # Source 3: Static list sebagai fallback
        if not forex_pairs:
            static_forex = self._get_static_assets('forex')
            forex_pairs.update(static_forex)
            logger.info("📦 Using static forex list as fallback")
        
        return list(forex_pairs)[:limit]
    
    def _fetch_us_stocks_dynamic(self, limit: int) -> List[str]:
        """Fetch dinamis untuk US stocks."""
        us_stocks = set()
        
        # Source 1: InvestingScraper untuk US stocks
        if INVESTING_SCRAPER_AVAILABLE:
            try:
                investing_scraper = InvestingScraper()
                if hasattr(investing_scraper, 'fetch_us_stocks'):
                    stocks = investing_scraper.fetch_us_stocks()
                    if stocks:
                        # Format symbols
                        formatted_stocks = []
                        for stock in stocks:
                            if isinstance(stock, str) and stock.strip():
                                formatted_stocks.append(stock.strip().upper())
                            elif isinstance(stock, dict) and 'symbol' in stock:
                                symbol = stock.get('symbol', '').strip().upper()
                                if symbol:
                                    formatted_stocks.append(symbol)
                        
                        us_stocks.update(formatted_stocks)
                        logger.info(f"✅ Fetched {len(formatted_stocks)} from Investing.com US stocks")
            except Exception as e:
                logger.warning(f"Investing.com US stocks fetch failed: {e}")
        
        # Source 2: Static list sebagai base
        static_us = self._get_static_assets('us_stocks')
        us_stocks.update(static_us)
        
        # Validasi simbol (opsional, bisa di-comment jika terlalu lama)
        # valid_stocks = self._validate_symbols_parallel(list(us_stocks)[:100])
        # return valid_stocks[:limit]
        
        return list(us_stocks)[:limit]
    
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
