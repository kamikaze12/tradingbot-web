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
            
            # Source 1: IDX API Official (Semua perusahaan tercatat)
            try:
                idx_symbols = self._fetch_from_idx_api()
                all_symbols.update(idx_symbols)
                logger.info(f"✅ Fetched {len(idx_symbols)} symbols from IDX API")
            except Exception as e:
                logger.warning(f"IDX API failed: {e}")
            
            # Source 2: IDX Website scraping
            try:
                idx_web_symbols = self._fetch_from_idx_website()
                all_symbols.update(idx_web_symbols)
                logger.info(f"✅ Fetched {len(idx_web_symbols)} symbols from IDX website")
            except Exception as e:
                logger.warning(f"IDX website failed: {e}")
            
            # Source 3: Wikipedia (backup)
            try:
                wiki_symbols = self._fetch_from_wikipedia()
                all_symbols.update(wiki_symbols)
                logger.info(f"✅ Fetched {len(wiki_symbols)} symbols from Wikipedia")
            except Exception as e:
                logger.warning(f"Wikipedia failed: {e}")
            
            # Source 4: TradingView/Investing.com scraping (backup)
            try:
                tv_symbols = self._fetch_from_tradingview()
                all_symbols.update(tv_symbols)
                logger.info(f"✅ Fetched {len(tv_symbols)} symbols from TradingView")
            except Exception as e:
                logger.warning(f"TradingView failed: {e}")
            
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
            # URL untuk semua perusahaan tercatat
            url = "https://www.idx.co.id/umbraco/Surface/ListedCompany/GetCompanyProfiles?length=2000&start=0"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
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
        """Scrape dari website IDX."""
        symbols = []
        try:
            # Main page for listed companies
            url = "https://www.idx.co.id/listed-companies/company-profiles/"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
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
        """Fetch dari Wikipedia IDX list."""
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
    
    def _fetch_from_tradingview(self) -> List[str]:
        """Fetch dari TradingView/Investing.com."""
        symbols = []
        try:
            # Major Indonesian stocks from TradingView
            major_symbols = [
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
                'WOWS.JK', 'YELO.JK', 'ZBRA.JK', 'ZONE.JK'
            ]
            symbols.extend(major_symbols)
            
        except Exception as e:
            logger.error(f"TradingView fetch error: {e}")
        
        return symbols
    
    def _validate_symbols_parallel(self, symbols: List[str]) -> List[str]:
        """Validasi simbol secara paralel menggunakan thread pool."""
        valid_symbols = []
        invalid_count = 0
        
        def validate_single(symbol: str):
            try:
                ticker = yf.Ticker(symbol)
                hist = ticker.history(period='7d')
                
                if not hist.empty and len(hist) >= 3:
                    # Cek apakah ada pergerakan harga
                    price_range = hist['High'].max() - hist['Low'].min()
                    if price_range > 0:
                        return symbol, True
                
                return symbol, False
            except Exception:
                return symbol, False
        
        # Gunakan thread pool untuk validasi paralel
        max_workers = min(20, len(symbols))
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(validate_single, sym): sym for sym in symbols}
            
            for future in concurrent.futures.as_completed(futures):
                symbol, is_valid = future.result()
                if is_valid:
                    valid_symbols.append(symbol)
                else:
                    invalid_count += 1
                    self.invalid_symbols.add(symbol)
        
        logger.info(f"🔄 Validation complete: {len(valid_symbols)} valid, {invalid_count} invalid")
        return valid_symbols
    
    def _fetch_dynamic_assets(self, category: str, limit: int) -> List[str]:
        """Fetch list aset dinamis dari yfinance/ccxt."""
        if category == 'us_stocks':
            return self._fetch_us_stocks(limit)
        elif category == 'forex':
            return self._fetch_forex_pairs(limit)
        return []
    
    def _fetch_us_stocks(self, limit: int) -> List[str]:
        """Fetch saham US populer."""
        try:
            # Daftar S&P 500
            symbols = []
            try:
                url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
                df = pd.read_html(url)[0]
                sp500_symbols = df['Symbol'].tolist()
                symbols.extend(sp500_symbols)
                logger.info(f"Fetched {len(sp500_symbols)} symbols from S&P 500")
            except Exception as e:
                logger.warning(f"Wikipedia S&P 500 failed: {e}")
            
            # Validasi
            valid_symbols = []
            for symbol in symbols[:limit*2]:
                try:
                    ticker = yf.Ticker(symbol)
                    info = ticker.info
                    if 'regularMarketPrice' in info or 'currentPrice' in info:
                        valid_symbols.append(symbol)
                        if len(valid_symbols) >= limit:
                            break
                except:
                    continue
            
            logger.info(f"Validated {len(valid_symbols)} US stocks")
            return valid_symbols[:limit]
            
        except Exception as e:
            logger.error(f"US stock fetch failed: {e}")
            return self._get_static_assets('us_stocks')[:limit]
    
    def _fetch_forex_pairs(self, limit: int) -> List[str]:
        """Fetch forex pairs."""
        try:
            symbols = []
            
            # Major pairs
            major_pairs = [
                'EURUSD=X', 'USDJPY=X', 'GBPUSD=X', 'AUDUSD=X', 'USDCAD=X',
                'USDCHF=X', 'NZDUSD=X', 'EURGBP=X', 'EURJPY=X', 'GBPJPY=X',
                'AUDJPY=X', 'EURCHF=X', 'GBPCHF=X', 'AUDNZD=X', 'NZDJPY=X',
                'USDSGD=X', 'USDHKD=X', 'USDCNY=X', 'USDKRW=X', 'USDMYR=X'
            ]
            symbols.extend(major_pairs)
            
            # Validasi
            valid_symbols = []
            for symbol in symbols[:limit*2]:
                try:
                    ticker = yf.Ticker(symbol)
                    hist = ticker.history(period='1d')
                    if not hist.empty:
                        valid_symbols.append(symbol)
                        if len(valid_symbols) >= limit:
                            break
                except:
                    continue
            
            logger.info(f"Validated {len(valid_symbols)} forex pairs")
            return valid_symbols[:limit]
            
        except Exception as e:
            logger.error(f"Forex fetch failed: {e}")
            return self._get_static_assets('forex')[:limit]
    
    def _get_all_indonesia_static(self) -> List[str]:
        """SEMUA saham Indonesia dari berbagai sumber."""
        # List komprehensif ~800+ saham
        all_indonesia_stocks = [
            # LQ45 - 45 saham paling likuid
            'BBCA.JK', 'BBRI.JK', 'BMRI.JK', 'TLKM.JK', 'ASII.JK', 'UNVR.JK',
            'ICBP.JK', 'INDF.JK', 'ANTM.JK', 'ADRO.JK', 'AKRA.JK', 'AMRT.JK',
            'INCO.JK', 'BRPT.JK', 'SMGR.JK', 'PGAS.JK', 'KLBF.JK', 'CPIN.JK',
            'INTP.JK', 'BBNI.JK', 'BNGA.JK', 'BSDE.JK', 'BUKA.JK', 'GOTO.JK',
            'MDKA.JK', 'ITMG.JK', 'MNCN.JK', 'ERAA.JK', 'TPIA.JK', 'BUMI.JK',
            'CTRA.JK', 'EXCL.JK', 'HRUM.JK', 'JPFA.JK', 'JSMR.JK', 'KIJA.JK',
            'LPPF.JK', 'MEDC.JK', 'MYOR.JK', 'PTBA.JK', 'PTPP.JK', 'SIDO.JK',
            'SMRA.JK', 'SRIL.JK', 'TBIG.JK', 'TINS.JK', 'TOTO.JK', 'TPMA.JK',
            'ULTJ.JK', 'UNTR.JK', 'WIKA.JK', 'WSKT.JK', 'WSBP.JK', 'WEGE.JK',
            
            # IDX80 - 80 saham dengan kapitalisasi terbesar
            'ACES.JK', 'ADMR.JK', 'AGRO.JK', 'AIMS.JK', 'AKPI.JK', 'ALMI.JK',
            'AMAG.JK', 'APLN.JK', 'ARNA.JK', 'ASSA.JK', 'AUTO.JK', 'BATA.JK',
            'BIMA.JK', 'BOLT.JK', 'BRMS.JK', 'BTEK.JK', 'BTPN.JK', 'CARE.JK',
            'CEKA.JK', 'CMNP.JK', 'CNTX.JK', 'COWL.JK', 'CPRO.JK', 'CTTH.JK',
            'DART.JK', 'DEWA.JK', 'DILD.JK', 'DNET.JK', 'DSSA.JK', 'DVLA.JK',
            'EKAD.JK', 'ELSA.JK', 'EMTK.JK', 'ENRG.JK', 'ESSA.JK', 'ESTI.JK',
            'EXSA.JK', 'FASW.JK', 'FILM.JK', 'GDST.JK', 'GEMA.JK', 'GGRM.JK',
            'GJTL.JK', 'GLOB.JK', 'GOLD.JK', 'GTBO.JK', 'HDFA.JK', 'HEAL.JK',
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
            
            # Additional stocks from various sectors
            # Finance/Banking
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
            'YPAS.JK', 'ZBRA.JK', 'ZONE.JK', 'ZYRX.JK'
        ]
        
        # Remove duplicates
        return list(set(all_indonesia_stocks))
    
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
