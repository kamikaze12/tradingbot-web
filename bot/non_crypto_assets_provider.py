import json
import os
from datetime import datetime, timedelta
import logging
import yfinance as yf
import ccxt
import pandas as pd
from typing import List, Dict, Optional
import requests
from bs4 import BeautifulSoup

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
            assets = self._fetch_dynamic_assets(category, limit)
            if assets and len(assets) >= 20:  # Minimal validasi
                # Simpan ke cache
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
            return static_assets[:limit]
    
    def _fetch_dynamic_assets(self, category: str, limit: int) -> List[str]:
        """Fetch list aset dinamis dari yfinance/ccxt."""
        if category == 'us_stocks':
            return self._fetch_us_stocks(limit)
        elif category == 'indonesia_stocks':
            return self._fetch_indonesia_stocks(limit)
        elif category == 'forex':
            return self._fetch_forex_pairs(limit)
        return []
    
    def _fetch_us_stocks(self, limit: int) -> List[str]:
        """Fetch saham US populer (S&P 500 dan NASDAQ 100)."""
        try:
            # Method 1: Download S&P 500 dari Wikipedia
            symbols = []
            try:
                url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
                df = pd.read_html(url)[0]
                sp500_symbols = df['Symbol'].tolist()
                symbols.extend(sp500_symbols)
                logger.info(f"Fetched {len(sp500_symbols)} symbols from S&P 500")
            except Exception as e:
                logger.warning(f"Wikipedia S&P 500 failed: {e}")
            
            # Method 2: Download NASDAQ 100
            try:
                url = 'https://en.wikipedia.org/wiki/Nasdaq-100'
                df = pd.read_html(url)[4]  # Table ke-4 biasanya berisi komponen
                nasdaq_symbols = df['Ticker'].tolist()
                symbols.extend(nasdaq_symbols)
                logger.info(f"Fetched {len(nasdaq_symbols)} symbols from NASDAQ 100")
            except Exception as e:
                logger.warning(f"Wikipedia NASDAQ 100 failed: {e}")
            
            # Method 3: Dow Jones 30
            try:
                dow_symbols = ['MMM', 'AXP', 'AMGN', 'AAPL', 'BA', 'CAT', 'CVX', 'CSCO', 'KO', 
                              'DOW', 'GS', 'HD', 'HON', 'IBM', 'INTC', 'JNJ', 'JPM', 'MCD', 
                              'MRK', 'MSFT', 'NKE', 'PG', 'CRM', 'TRV', 'UNH', 'VZ', 'V', 'WMT', 'DIS']
                symbols.extend(dow_symbols)
                logger.info(f"Added {len(dow_symbols)} Dow Jones symbols")
            except Exception as e:
                logger.warning(f"Dow Jones fetch failed: {e}")
            
            # Remove duplicates and validate
            unique_symbols = list(set(symbols))
            logger.info(f"Total unique US stocks before validation: {len(unique_symbols)}")
            
            # Validasi dengan yfinance (batch processing)
            valid_symbols = []
            batch_size = 50
            
            for i in range(0, min(len(unique_symbols), limit*2), batch_size):
                batch = unique_symbols[i:i+batch_size]
                for symbol in batch:
                    try:
                        # Quick validation
                        ticker = yf.Ticker(symbol)
                        # Coba ambil info dasar
                        info = ticker.info
                        if 'regularMarketPrice' in info or 'currentPrice' in info:
                            valid_symbols.append(symbol)
                            if len(valid_symbols) >= limit:
                                logger.info(f"Validated {len(valid_symbols)} US stocks")
                                return valid_symbols[:limit]
                    except Exception as e:
                        continue
            
            logger.info(f"Validated {len(valid_symbols)} US stocks")
            return valid_symbols[:limit]
            
        except Exception as e:
            logger.error(f"All US stock fetch methods failed: {e}")
            return self._get_static_assets('us_stocks')[:limit]
    
    def _fetch_indonesia_stocks(self, limit: int) -> List[str]:
        """Fetch saham Indonesia populer dari berbagai sumber."""
        try:
            symbols = []
            
            # Method 1: Dari IDX website atau data publik
            try:
                # Coba ambil dari IDX data publik
                idx_url = "https://www.idx.co.id/umbraco/Surface/ListedCompany/GetCompanyProfiles?length=1000&start=0"
                response = requests.get(idx_url, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    if 'data' in data:
                        for company in data['data']:
                            symbol = company.get('KodeEmiten', '') + '.JK'
                            if symbol and symbol != '.JK':
                                symbols.append(symbol)
                        logger.info(f"Fetched {len(symbols)} symbols from IDX API")
            except Exception as e:
                logger.warning(f"IDX API failed: {e}")
            
            # Method 2: Wikipedia IDX
            if len(symbols) < 100:
                try:
                    url = 'https://en.wikipedia.org/wiki/List_of_companies_listed_on_the_Indonesia_Stock_Exchange'
                    tables = pd.read_html(url)
                    for table in tables:
                        if 'Code' in table.columns:
                            idx_symbols = table['Code'].dropna().tolist()
                            idx_symbols = [s + '.JK' for s in idx_symbols if isinstance(s, str) and s]
                            symbols.extend(idx_symbols)
                            break
                    logger.info(f"Fetched additional symbols from Wikipedia")
                except Exception as e:
                    logger.warning(f"Wikipedia IDX failed: {e}")
            
            # Method 3: Static list yang diperluas
            if len(symbols) < 50:
                static_symbols = self._get_static_assets('indonesia_stocks')
                symbols.extend(static_symbols)
                logger.info(f"Added {len(static_symbols)} static symbols")
            
            # Remove duplicates
            unique_symbols = list(set(symbols))
            logger.info(f"Total unique IDX symbols before validation: {len(unique_symbols)}")
            
            # Validasi dengan yfinance
            valid_symbols = []
            batch_size = 30
            
            for i in range(0, min(len(unique_symbols), limit*2), batch_size):
                batch = unique_symbols[i:i+batch_size]
                for symbol in batch:
                    try:
                        ticker = yf.Ticker(symbol)
                        # Coba ambil data 1 hari untuk validasi
                        hist = ticker.history(period='7d')
                        if not hist.empty and len(hist) >= 1:
                            valid_symbols.append(symbol)
                            if len(valid_symbols) >= limit:
                                logger.info(f"Validated {len(valid_symbols)} Indonesia stocks")
                                return valid_symbols[:limit]
                    except Exception as e:
                        continue
            
            logger.info(f"Validated {len(valid_symbols)} Indonesia stocks")
            return valid_symbols[:limit]
            
        except Exception as e:
            logger.error(f"All Indonesia stock fetch methods failed: {e}")
            return self._get_static_assets('indonesia_stocks')[:limit]
    
    def _fetch_forex_pairs(self, limit: int) -> List[str]:
        """Fetch forex pairs dari berbagai sumber."""
        try:
            symbols = []
            
            # Method 1: Yahoo Finance major pairs
            major_pairs = [
                'EURUSD=X', 'USDJPY=X', 'GBPUSD=X', 'AUDUSD=X', 'USDCAD=X',
                'USDCHF=X', 'NZDUSD=X', 'EURGBP=X', 'EURJPY=X', 'GBPJPY=X',
                'AUDJPY=X', 'EURCHF=X', 'GBPCHF=X', 'AUDNZD=X', 'NZDJPY=X',
                'USDSGD=X', 'USDHKD=X', 'USDCNY=X', 'USDKRW=X', 'USDMYR=X'
            ]
            symbols.extend(major_pairs)
            
            # Method 2: CCXT untuk pairs tambahan
            try:
                exchange = ccxt.binance()
                markets = exchange.load_markets()
                forex_symbols = []
                for symbol in markets:
                    if '/' in symbol:
                        base, quote = symbol.split('/')
                        # Hanya pairs dengan mata uang fiat utama
                        major_currencies = ['USD', 'EUR', 'JPY', 'GBP', 'AUD', 'CAD', 'CHF', 'NZD', 'SGD', 'HKD']
                        if quote in major_currencies and base not in ['BTC', 'ETH', 'USDT', 'BNB']:
                            yf_symbol = f"{base}{quote}=X"
                            forex_symbols.append(yf_symbol)
                
                # Tambah 50 pairs teratas berdasarkan volume
                symbols.extend(forex_symbols[:50])
                logger.info(f"Added {len(forex_symbols[:50])} forex pairs from CCXT")
            except Exception as e:
                logger.warning(f"CCXT forex failed: {e}")
            
            # Method 3: Cross pairs
            cross_pairs = []
            majors = ['EUR', 'USD', 'JPY', 'GBP', 'AUD', 'CAD', 'CHF', 'NZD']
            for i in range(len(majors)):
                for j in range(i+1, len(majors)):
                    if majors[i] != 'USD' and majors[j] != 'USD':  # Cross pairs tanpa USD
                        cross_pairs.append(f"{majors[i]}{majors[j]}=X")
            
            symbols.extend(cross_pairs[:30])
            
            # Remove duplicates
            unique_symbols = list(set(symbols))
            logger.info(f"Total unique forex pairs: {len(unique_symbols)}")
            
            # Validasi dengan yfinance
            valid_symbols = []
            for symbol in unique_symbols:
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
            logger.error(f"All forex fetch methods failed: {e}")
            return self._get_static_assets('forex')[:limit]
    
    def _get_static_assets(self, category: str) -> List[str]:
        """List statis hardcoded sebagai fallback (extended ke ~200 per kategori)."""
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
                'EA', 'ATVI', 'TTD', 'ROKU', 'SPOT', 'PYPL', 'SQ', 'SHOP', 'MELI', 'SE',
                'NET', 'CRWD', 'ZS', 'OKTA', 'PANW', 'FTNT', 'CYBR', 'PLTR', 'SNOW',
                'DDOG', 'MDB', 'TWLO', 'TEAM', 'ZS', 'ESTC', 'AI', 'PATH', 'ASAN',
                'SMAR', 'BILL', 'COUP', 'DOCU', 'ZM', 'FSLY', 'PINS', 'SNAP', 'TWTR',
                'UBER', 'LYFT', 'DASH', 'ABNB', 'EXPE', 'BKNG', 'TRIP', 'RCL', 'NCLH',
                'CCL', 'MAR', 'HLT', 'HYATT', 'AAL', 'DAL', 'UAL', 'LUV', 'ALK', 'JBLU',
                'SAVE', 'FDX', 'UPS', 'EXPD', 'CHRW', 'JBHT', 'LSTR', 'ODFL', 'XPO',
                'YRCW', 'ZTO', 'JD', 'BABA', 'PDD', 'TCEHY', 'BIDU', 'NTES', 'BILI',
                'IQ', 'TME', 'YY', 'DOYU', 'HUYA', 'WB', 'MOMO', 'VIPS', 'JD', 'BIDU',
                'EDU', 'TAL', 'DAO', 'FUTU', 'NIO', 'XPEV', 'LI', 'KC', 'YUMC', 'BZUN',
                'VNET', 'SOHU', 'NTES', 'SINA', 'CTRP', 'EH', 'QD', 'FINV', 'LX', 'QFIN',
                'TIGR', 'AMC', 'GME', 'BB', 'NOK', 'TLRY', 'SNDL', 'CGC', 'ACB', 'TLRY',
                'CRON', 'HEXO', 'OGI', 'CWBHF', 'GWPH', 'KERN', 'TRUL', 'GTBIF', 'CCHWF'
            ]
        elif category == 'indonesia_stocks':
            return [
                'BBCA.JK', 'BBRI.JK', 'BMRI.JK', 'TLKM.JK', 'ASII.JK', 'UNVR.JK', 'ICBP.JK', 'INDF.JK', 'ANTM.JK', 'ADRO.JK',
                'AKRA.JK', 'AMRT.JK', 'INCO.JK', 'BRPT.JK', 'SMGR.JK', 'PGAS.JK', 'KLBF.JK', 'CPIN.JK', 'INTP.JK', 'BBNI.JK',
                'BNGA.JK', 'BSDE.JK', 'BUKA.JK', 'GOTO.JK', 'MDKA.JK', 'ITMG.JK', 'MNCN.JK', 'ERAA.JK', 'TPIA.JK', 'BUMI.JK',
                'CTRA.JK', 'EXCL.JK', 'HRUM.JK', 'JPFA.JK', 'JSMR.JK', 'KIJA.JK', 'LPPF.JK', 'MEDC.JK', 'MYOR.JK', 'PTBA.JK',
                'PTPP.JK', 'SIDO.JK', 'SMRA.JK', 'SRIL.JK', 'TBIG.JK', 'TINS.JK', 'TOTO.JK', 'TPMA.JK', 'ULTJ.JK', 'UNTR.JK',
                'WIKA.JK', 'WSKT.JK', 'WSBP.JK', 'WEGE.JK', 'WTON.JK', 'YPAS.JK', 'ACES.JK', 'ADMR.JK', 'AGRO.JK', 'AIMS.JK',
                'AKPI.JK', 'ALMI.JK', 'AMAG.JK', 'APLN.JK', 'ARNA.JK', 'ASSA.JK', 'AUTO.JK', 'BATA.JK', 'BIMA.JK', 'BOLT.JK',
                'BRMS.JK', 'BTEK.JK', 'BTPN.JK', 'CARE.JK', 'CEKA.JK', 'CMNP.JK', 'CNTX.JK', 'COWL.JK', 'CPRO.JK', 'CTTH.JK',
                'DART.JK', 'DEWA.JK', 'DILD.JK', 'DNET.JK', 'DSSA.JK', 'DVLA.JK', 'EKAD.JK', 'ELSA.JK', 'EMTK.JK', 'ENRG.JK',
                'ESSA.JK', 'ESTI.JK', 'EXSA.JK', 'FASW.JK', 'FILM.JK', 'GDST.JK', 'GEMA.JK', 'GGRM.JK', 'GJTL.JK', 'GLOB.JK',
                'GOLD.JK', 'GTBO.JK', 'HDFA.JK', 'HEAL.JK', 'HELI.JK', 'HERO.JK', 'HITS.JK', 'HMSP.JK', 'HOME.JK', 'ICON.JK',
                'IFII.JK', 'IGAR.JK', 'IIKP.JK', 'IKAI.JK', 'IMAS.JK', 'INAF.JK', 'INAI.JK', 'INCF.JK', 'INDX.JK', 'INKP.JK',
                'INPC.JK', 'INPP.JK', 'INPS.JK', 'INRU.JK', 'INTA.JK', 'INTP.JK', 'IPCC.JK', 'ISAT.JK', 'ITIC.JK', 'ITMG.JK',
                'JAST.JK', 'JECC.JK', 'JIHD.JK', 'JKON.JK', 'JPFA.JK', 'JSMR.JK', 'KBLI.JK', 'KBLM.JK', 'KDSI.JK', 'KIJA.JK',
                'KKGI.JK', 'KLBF.JK', 'KOIN.JK', 'KPAL.JK', 'KRAS.JK', 'LION.JK', 'LMAS.JK', 'LMPI.JK', 'LPCK.JK', 'LPPF.JK',
                'LSIP.JK', 'LTLS.JK', 'MABA.JK', 'MAGP.JK', 'MAIN.JK', 'MAPI.JK', 'MASA.JK', 'MBAP.JK', 'MBSS.JK', 'MCAS.JK',
                'MDIA.JK', 'MDKA.JK', 'MEDC.JK', 'MEGA.JK', 'MERK.JK', 'META.JK', 'MFIN.JK', 'MIKA.JK', 'MLBI.JK', 'MLIA.JK',
                'MLPL.JK', 'MMLP.JK', 'MNCN.JK', 'MPMX.JK', 'MRAT.JK', 'MTDL.JK', 'MTFN.JK', 'MYOH.JK', 'MYOR.JK', 'MYRX.JK',
                'NATO.JK', 'NFCX.JK', 'NIKL.JK', 'NIPS.JK', 'NOVO.JK', 'NRCA.JK', 'OKAS.JK', 'OPMS.JK', 'PALM.JK', 'PANI.JK',
                'PANS.JK', 'PBRX.JK', 'PCAR.JK', 'PEHA.JK', 'PGAS.JK', 'PGLI.JK', 'PICO.JK', 'PJAA.JK', 'PKPK.JK', 'PLAS.JK',
                'PLIN.JK', 'PMJS.JK', 'PNBN.JK', 'PNBS.JK', 'PNIN.JK', 'PNLF.JK', 'POLA.JK', 'POLU.JK', 'POWR.JK', 'PPRE.JK',
                'PRAS.JK', 'PRDA.JK', 'PSAB.JK', 'PSDN.JK', 'PSGO.JK', 'PTBA.JK', 'PTIS.JK', 'PTPP.JK', 'PTPW.JK', 'PTRO.JK',
                'PURI.JK', 'PWON.JK', 'PYFA.JK', 'RAJA.JK', 'RALS.JK', 'RANC.JK', 'RBMS.JK', 'RDTX.JK', 'REAL.JK', 'RICY.JK',
                'RIGS.JK', 'RIMO.JK', 'RODA.JK', 'RONY.JK', 'ROTI.JK', 'RSGK.JK', 'RUIS.JK', 'SAFE.JK', 'SAME.JK', 'SAMF.JK',
                'SAPX.JK', 'SATU.JK', 'SBAT.JK', 'SCCO.JK', 'SCMA.JK', 'SCNP.JK', 'SDMU.JK', 'SDPC.JK', 'SFAN.JK', 'SGER.JK',
                'SGRO.JK', 'SHID.JK', 'SIDO.JK', 'SILO.JK', 'SIMA.JK', 'SIMP.JK', 'SIPD.JK', 'SKBM.JK', 'SKLT.JK', 'SKRN.JK',
                'SKYB.JK', 'SLIS.JK', 'SMBR.JK', 'SMCB.JK', 'SMGR.JK', 'SMMA.JK', 'SMMT.JK', 'SMRA.JK', 'SMSM.JK', 'SNLK.JK',
                'SOCI.JK', 'SOSS.JK', 'SOTS.JK', 'SPTO.JK', 'SQMI.JK', 'SRIL.JK', 'SRSN.JK', 'SRTG.JK', 'SSIA.JK', 'SSMS.JK',
                'SSTM.JK', 'STAR.JK', 'STTP.JK', 'SUGI.JK', 'SULI.JK', 'SUPR.JK', 'SURY.JK', 'SWAT.JK', 'TALF.JK', 'TAMA.JK',
                'TAPG.JK', 'TARA.JK', 'TAXI.JK', 'TBIG.JK', 'TBLA.JK', 'TCID.JK', 'TCPI.JK', 'TDPM.JK', 'TEBE.JK', 'TELE.JK',
                'TFAS.JK', 'TFCO.JK', 'TGKA.JK', 'TGRA.JK', 'TIFA.JK', 'TINS.JK', 'TIRT.JK', 'TKIM.JK', 'TLDN.JK', 'TLKM.JK',
                'TMAS.JK', 'TMPO.JK', 'TOTO.JK', 'TOWR.JK', 'TOYS.JK', 'TPIA.JK', 'TPMA.JK', 'TRIO.JK', 'TRIS.JK', 'TRST.JK',
                'TRUB.JK', 'TSPC.JK', 'TUGU.JK', 'TUNA.JK', 'UCID.JK', 'UFOE.JK', 'ULTJ.JK', 'UNIC.JK', 'UNIT.JK', 'UNSP.JK',
                'UNTR.JK', 'UNVR.JK', 'URBN.JK', 'VICI.JK', 'VINS.JK', 'VIVA.JK', 'VOKS.JK', 'VRNA.JK', 'WAPO.JK', 'WEGE.JK',
                'WEHA.JK', 'WICO.JK', 'WIFI.JK', 'WIKA.JK', 'WINS.JK', 'WMPP.JK', 'WOOD.JK', 'WOWS.JK', 'WSBP.JK', 'WSKT.JK',
                'WTON.JK', 'YELO.JK', 'YPAS.JK', 'ZBRA.JK', 'ZONE.JK'
            ]
        elif category == 'forex':
            return [
                'EURUSD=X', 'USDJPY=X', 'GBPUSD=X', 'AUDUSD=X', 'USDCAD=X', 'USDCHF=X', 'NZDUSD=X', 'EURGBP=X', 'EURJPY=X', 'GBPJPY=X',
                'AUDJPY=X', 'EURCHF=X', 'GBPCHF=X', 'AUDNZD=X', 'NZDJPY=X', 'USDSGD=X', 'USDHKD=X', 'USDCNY=X', 'USDKRW=X', 'USDMYR=X',
                'EURUSD', 'USDJPY', 'GBPUSD', 'AUDUSD', 'USDCAD', 'USDCHF', 'NZDUSD', 'EURGBP', 'EURJPY', 'GBPJPY',
                'AUDJPY', 'EURCHF', 'GBPCHF', 'AUDNZD', 'NZDJPY', 'USDSGD', 'USDHKD', 'USDCNY', 'USDKRW', 'USDMYR',
                'EURCAD', 'EURAUD', 'EURNZD', 'GBPAUD', 'GBPCAD', 'GBPNZD', 'AUDCAD', 'AUDCHF', 'NZDCAD', 'NZDCHF',
                'CADJPY', 'CHFJPY', 'EURSEK', 'EURNOK', 'EURDKK', 'EURPLN', 'EURHUF', 'EURCZK', 'EURRON', 'EURTRY',
                'USDRUB', 'USDINR', 'USDBRL', 'USDMXN', 'USDZAR', 'USDTWD', 'USDTHB', 'USDPHP', 'USDIDR', 'USDVND',
                'USDBDT', 'USDPKR', 'USDLKR', 'USDKWD', 'USDBHD', 'USDQAR', 'USDSAR', 'USDAED', 'USDOMR', 'USDJOD',
                'GBPAUD', 'GBPCAD', 'GBPCHF', 'GBPNZD', 'GBPSEK', 'GBPNOK', 'GBPDKK', 'GBPPLN', 'GBPHUF', 'GBPCZK',
                'GBPTRY', 'GBPRUB', 'GBPINR', 'GBPBRL', 'GBPMXN', 'GBPZAR', 'AUDSEK', 'AUDNOK', 'AUDDKK', 'AUDPLN',
                'AUDHUF', 'AUDCZK', 'AUDTRY', 'AUDRUB', 'AUDINR', 'AUDBRL', 'AUDMXN', 'AUDZAR', 'CADSEK', 'CADNOK',
                'CADDKK', 'CADPLN', 'CADHUF', 'CADCZK', 'CADTRY', 'CADRUB', 'CADINR', 'CADBRL', 'CADMXN', 'CADZAR',
                'CHFSEK', 'CHFNOK', 'CHFDKK', 'CHFPLN', 'CHFHUF', 'CHFCZK', 'CHFTRY', 'CHFRUB', 'CHFINR', 'CHFBRL',
                'CHFMXN', 'CHFZAR', 'NZDSEK', 'NZDNOK', 'NZDDKK', 'NZDPLN', 'NZDHUF', 'NZDCZK', 'NZDTRY', 'NZDRUB',
                'NZDIHR', 'NZDBRL', 'NZDMXN', 'NZDZAR', 'SEKJPY', 'NOKJPY', 'DKKJPY', 'PLNJPY', 'HUFJPY', 'CZKJPY',
                'TRYJPY', 'RUBJPY', 'INRJPY', 'BRLJPY', 'MXNJPY', 'ZARJPY', 'TWDPHP', 'THBPHP', 'IDRPHP', 'VNDPHP',
                'BDTPHP', 'PKRPHP', 'LKRPHP', 'KWDPHP', 'BHDPHP', 'QARPHP', 'SARPHP', 'AEDPHP', 'OMRPHP', 'JODPHP'
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
    
    # Test indo stocks (update optional)
    indo_stocks = provider.get_assets('indonesia_stocks', limit=200, force_update=True)
    print(f"Indonesia Stocks ({len(indo_stocks)}): {indo_stocks[:10]}...")  # Print 10 pertama
    
    # Test forex (tanpa force update, pakai cache jika ada)
    forex = provider.get_assets('forex', limit=200)
    print(f"Forex Pairs ({len(forex)}): {forex[:10]}...")
    
    # Test US stocks
    us_stocks = provider.get_assets('us_stocks', limit=200)
    print(f"US Stocks ({len(us_stocks)}): {us_stocks[:10]}...")
    
    # Simpan cache
    provider._save_cache()
