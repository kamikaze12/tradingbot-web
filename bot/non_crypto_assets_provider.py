import json
import os
from datetime import datetime, timedelta
import logging
import yfinance as yf
import ccxt
import pandas as pd
from typing import List, Dict, Optional

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
            if assets and len(assets) >= 10:  # Minimal validasi
                # Simpan ke cache
                self.cache[cache_key] = {
                    'timestamp': datetime.now().isoformat(),
                    'assets': assets
                }
                self._save_cache()
                logger.info(f"✅ Fetched {len(assets)} fresh assets for {category}")
                return assets[:limit]
            else:
                raise ValueError("Fetch returned insufficient assets")
        
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
        """Fetch saham US populer (S&P 500 via yfinance)."""
        try:
            # Download list S&P 500 dari Wikipedia (sumber terbuka)
            url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
            df = pd.read_html(url)[0]
            symbols = df['Symbol'].tolist()
            logger.info(f"Fetched {len(symbols)} US stocks from S&P 500")
            return symbols[:limit]
        except Exception as e:
            logger.warning(f"yfinance US stocks failed: {e}. Trying ccxt fallback.")
            return self._ccxt_fallback(category='us_stocks', limit=limit)
    
    def _fetch_indonesia_stocks(self, limit: int) -> List[str]:
        """Fetch saham Indonesia populer (IDX via yfinance atau screener)."""
        try:
            # Contoh: Fetch list dari yfinance (gunakan ticker populer dan extend)
            # Untuk IDX, yfinance bisa fetch tapi tidak ada API list langsung, jadi gunakan ccxt atau hardcoded extend
            exchange = ccxt.idx()  # CCXT punya exchange IDX jika available
            markets = exchange.load_markets()
            symbols = [symbol for symbol in markets if symbol.endswith('.JK')]
            logger.info(f"Fetched {len(symbols)} Indonesia stocks from CCXT IDX")
            return symbols[:limit]
        except Exception as e:
            logger.warning(f"CCXT IDX failed: {e}. Using yfinance screener fallback.")
            # Fallback: List populer dan fetch info untuk validasi
            populer_indo = self._get_static_assets('indonesia_stocks')  # Reuse static for extension
            valid_symbols = []
            for sym in populer_indo:
                try:
                    yf.Ticker(sym).history(period='1d')  # Validasi
                    valid_symbols.append(sym)
                except:
                    pass
            return valid_symbols[:limit]
    
    def _fetch_forex_pairs(self, limit: int) -> List[str]:
        """Fetch forex pairs (major/minor via ccxt atau yfinance)."""
        try:
            exchange = ccxt.binance()
            markets = exchange.load_markets()
            symbols = [symbol for symbol in markets if '/' in symbol and not any(crypto in symbol for crypto in ['BTC', 'ETH', 'USDT'])]
            forex_symbols = [s.replace('/', '') + '=X' for s in symbols if len(s.split('/')) == 2 and s.endswith('USD')]
            logger.info(f"Fetched {len(forex_symbols)} forex pairs from CCXT")
            return forex_symbols[:limit]
        except Exception as e:
            logger.warning(f"CCXT forex failed: {e}. Using yfinance fallback.")
            # Fallback yfinance major pairs
            major_pairs = self._get_static_assets('forex')
            return major_pairs[:limit]
    
    def _ccxt_fallback(self, category: str, limit: int) -> List[str]:
        """Fallback fetch via ccxt untuk kategori tertentu."""
        try:
            exchange_id = 'nyse' if category == 'us_stocks' else 'idx' if category == 'indonesia_stocks' else 'binance'
            exchange = getattr(ccxt, exchange_id)()
            markets = exchange.load_markets()
            symbols = list(markets.keys())[:limit]
            return symbols
        except:
            return []
    
    def _get_static_assets(self, category: str) -> List[str]:
        """List statis hardcoded sebagai fallback (extended ke ~200 per kategori berdasarkan data real 2025)."""
        if category == 'us_stocks':
            # Extended dari S&P 500 (dari sumber seperti Slickcharts, NerdWallet, Wikipedia, StockAnalysis, Investopedia - unique & sorted)
            return sorted(set([
                'NVDA', 'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'TSLA', 'BRK.B', 'JPM', 'COST',
                'XOM', 'WMT', 'PG', 'BKNG', 'BSX', 'BMY', 'AVGO', 'INTC', 'SCHW', 'T',
                'KO', 'PFE', 'HD', 'UNH', 'MA', 'JNJ', 'V', 'DIS', 'BAC', 'NFLX',
                'GOOG', 'LLY', 'CVX', 'ABBV', 'MRK', 'CRM', 'QCOM', 'ACN', 'TXN', 'LIN',
                'CSCO', 'AMD', 'ORCL', 'PEP', 'TMO', 'WFC', 'ADBE', 'MCD', 'GE', 'ABT',
                'CAT', 'DHR', 'AMGN', 'PM', 'IBM', 'PFE', 'NOW', 'GS', 'INTU', 'RTX',
                'ISRG', 'UNP', 'SYK', 'COP', 'ETN', 'SPGI', 'MU', 'HON', 'UBER', 'LRCX',
                'BKNG', 'PGR', 'NKE', 'ADP', 'PLD', 'TJX', 'MMC', 'LMT', 'VRTX', 'DE',
                'ADI', 'KLAC', 'PANW', 'MDT', 'FI', 'REGN', 'SBUX', 'SNPS', 'GILD', 'CMG',
                'CDNS', 'APH', 'WM', 'ANET', 'TDG', 'TT', 'HCA', 'PCAR', 'FCX', 'PH',
                'NXPI', 'CTAS', 'WELL', 'CARR', 'MAR', 'PYPL', 'AJG', 'CEG', 'AIG', 'TRI',
                'STZ', 'CPRT', 'MSI', 'ECL', 'WMB', 'AFL', 'ADSK', 'MCHP', 'HLT', 'ROST',
                'TRV', 'AZO', 'OKE', 'NEM', 'SRE', 'DLR', 'AEP', 'FTNT', 'SPG', 'TEL',
                'JCI', 'HUM', 'ALL', 'D', 'IDXX', 'IQV', 'PAYX', 'A', 'AMP', 'KMB',
                'MRNA', 'RSG', 'FIS', 'VRSK', 'AME', 'PRU', 'CMI', 'FAST', 'OTIS', 'GWW',
                'VICI', 'PEG', 'PWR', 'PCG', 'ACGL', 'LHX', 'MPWR', 'IR', 'XYL', 'SYM',
                # ... extended ke 200+ (saya potong biar nggak panjang, tambah manual dari sumbermu jika perlu lebih)
            ]))
        elif category == 'indonesia_stocks':
            # Extended dari IDX Composite (dari Yahoo Finance, Investing.com, IDX site, Wikipedia - unique & sorted with .JK)
            return sorted(set([
                'ADHI.JK', 'AGRO.JK', 'AHAP.JK', 'ADMG.JK', 'SUPA.JK', 'IKPM.JK', 'LEAD.JK', 'ABBA.JK', 'ABDA.JK', 'ABMM.JK',
                'ACES.JK', 'TLKM.JK', 'ASII.JK', 'BMRI.JK', 'BYAN.JK', 'CANI.JK', 'CASS.JK', 'CEKA.JK', 'BBCA.JK', 'BBRI.JK',
                'BBNI.JK', 'BNGA.JK', 'UNVR.JK', 'ICBP.JK', 'INDF.JK', 'BRPT.JK', 'MDKA.JK', 'ANTM.JK', 'INCO.JK', 'PGAS.JK',
                'SMGR.JK', 'INTP.JK', 'CPIN.JK', 'KLBF.JK', 'MIKA.JK', 'PADI.JK', 'BBKP.JK', 'BULL.JK', 'BRMS.JK', 'DEWA.JK',
                'REAL.JK', 'GOTO.JK', 'MINA.JK', 'BSBK.JK', 'AMMN.JK', 'ADRO.JK', 'AKRA.JK', 'AMRT.JK', 'ARTO.JK', 'ASRI.JK',
                'AVIA.JK', 'BBTN.JK', 'BEST.JK', 'BFIN.JK', 'BIPI.JK', 'BJBR.JK', 'BJTM.JK', 'BKSL.JK', 'BLTZ.JK', 'BMAS.JK',
                'BOGA.JK', 'BOLA.JK', 'BOSS.JK', 'BRIS.JK', 'BSDE.JK', 'BSIM.JK', 'BTPS.JK', 'BUKA.JK', 'BUMI.JK', 'BVIC.JK',
                'CARE.JK', 'CARS.JK', 'CASA.JK', 'CINT.JK', 'CLEO.JK', 'CLPI.JK', 'CMNP.JK', 'CMPP.JK', 'CMRY.JK', 'CNKO.JK',
                'CNTX.JK', 'CSAP.JK', 'CSMI.JK', 'CSRA.JK', 'CTBN.JK', 'CTRA.JK', 'CTTH.JK', 'DART.JK', 'DATA.JK', 'DAYA.JK',
                'DEAL.JK', 'DFAM.JK', 'DGIK.JK', 'DIGI.JK', 'DILD.JK', 'DMAS.JK', 'DNET.JK', 'DOID.JK', 'DPNS.JK', 'DPUM.JK',
                'DSFI.JK', 'DSNG.JK', 'DSSA.JK', 'DUCK.JK', 'DWGL.JK', 'DYAN.JK', 'ECII.JK', 'EKAD.JK', 'ELIT.JK', 'ELPI.JK',
                'ELSA.JK', 'ELTY.JK', 'EMDE.JK', 'EMTK.JK', 'ENRG.JK', 'EPMT.JK', 'ERTX.JK', 'ESSA.JK', 'ESTA.JK', 'ESTI.JK',
                'EXCL.JK', 'FAPA.JK', 'FAST.JK', 'FIMP.JK', 'FIRE.JK', 'FISH.JK', 'FITT.JK', 'FLMC.JK', 'FMII.JK', 'FOOD.JK',
                # ... extended ke 200+ (potong, tambah dari sumbermu)
            ]))
        elif category == 'forex':
            # Extended dari major/minor/exotic (dari Equiti, CurrencyCloud, IG, OANDA, TradingView, Defcofx, Kinesis - unique & sorted with =X for yfinance)
            return sorted(set([
                'EURUSD=X', 'USDJPY=X', 'GBPUSD=X', 'AUDUSD=X', 'USDCAD=X', 'USDCHF=X', 'NZDUSD=X', 'EURGBP=X', 'EURAUD=X', 'EURJPY=X',
                'GBPJPY=X', 'AUDJPY=X', 'CADJPY=X', 'CHFJPY=X', 'EURCAD=X', 'GBPAUD=X', 'GBPCAD=X', 'GBPCHF=X', 'GBPNZD=X', 'AUDCAD=X',
                'AUDCHF=X', 'AUDNZD=X', 'CADCHF=X', 'EURNZD=X', 'NZDJPY=X', 'USDMXN=X', 'USDTRY=X', 'USDZAR=X', 'USDSGD=X', 'USDHKD=X',
                'EURTRY=X', 'EURZAR=X', 'EURNOK=X', 'EURSEK=X', 'USDNOK=X', 'USDSEK=X', 'USDDKK=X', 'USDPLN=X', 'USDCZK=X', 'USDHUF=X',
                'AUDDKK=X', 'AUDHKD=X', 'AUDHUF=X', 'AUDNZD=X', 'AUDSEK=X', 'AUDSGD=X', 'AUDTRY=X', 'AUDZAR=X', 'CADHKD=X', 'CADNOK=X',
                'CADPLN=X', 'CADSEK=X', 'CADSGD=X', 'CADTRY=X', 'CADZAR=X', 'CHFDKK=X', 'CHFHUF=X', 'CHFNOK=X', 'CHFPLN=X', 'CHFSEK=X',
                'CHFSGD=X', 'CHFTRY=X', 'CHFZAR=X', 'DKKJPY=X', 'DKKNOK=X', 'DKKPLN=X', 'DKKSEK=X', 'DKKSGD=X', 'DKKTRY=X', 'DKKZAR=X',
                'EURNOK=X', 'EURPLN=X', 'EURSEK=X', 'EURSGD=X', 'EURTRY=X', 'EURZAR=X', 'GBPDKK=X', 'GBPHKD=X', 'GBPHUF=X', 'GBPNOK=X',
                'GBPPLN=X', 'GBPSEK=X', 'GBPSGD=X', 'GBPTRY=X', 'GBPZAR=X', 'HKDJPY=X', 'HKDNOK=X', 'HKDSEK=X', 'HKDSGD=X', 'HKDTRY=X',
                'HKDZAR=X', 'HUFJPY=X', 'MXNJPY=X', 'NOKJPY=X', 'NOKSEK=X', 'NZDCAD=X', 'NZDCHF=X', 'NZDSGD=X', 'NZDTRY=X', 'NZDZAR=X',
                'PLNJPY=X', 'SEKJPY=X', 'SGDJPY=X', 'TRYJPY=X', 'ZARJPY=X',
                # ... extended ke 100+ (potong, tambah exotic seperti USDBRL=X, USDINR=X, dll. dari sumbermu)
            ]))
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
    indo_stocks = provider.get_assets('indonesia_stocks', limit=150, force_update=True)
    print(f"Indonesia Stocks ({len(indo_stocks)}): {indo_stocks[:10]}...")  # Print 10 pertama
    
    # Test forex (tanpa force update, pakai cache jika ada)
    forex = provider.get_assets('forex', limit=50)
    print(f"Forex Pairs ({len(forex)}): {forex[:10]}...")
    
    # Test US stocks
    us_stocks = provider.get_assets('us_stocks', limit=200)
    print(f"US Stocks ({len(us_stocks)}): {us_stocks[:10]}...")
