import json
import os
from datetime import datetime, timedelta
import logging
import yfinance as yf
import pandas as pd
import numpy as np
from typing import List, Dict, Set, Tuple, Optional, Any, Union
import requests
from bs4 import BeautifulSoup
import time
import concurrent.futures
from threading import Lock
from concurrent.futures import ThreadPoolExecutor, as_completed

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Cache file path
CACHE_FILE = 'assets_cache.json'
CACHE_TTL_DAYS = 3

class NonCryptoAssetsProvider:
    """
    Provider untuk list aset non-crypto dengan filter cerdas untuk hindari saham sampah.
    UPDATED: Smart filtering system untuk buang saham stagnan (KPAS.JK) & pertahankan yang aktif.
    """
    
    def __init__(self):
        self.cache = self._load_cache()
        self.invalid_symbols: Set[str] = set()
        self.stagnant_symbols: Set[str] = set()
        self.cache_lock = Lock()
        self.rate_limit_delay = 0.3  # Optimal untuk rate limiting
        self._verified_stocks = None
        
        # Inisialisasi blacklist saham sampah
        self._init_stock_blacklist()
    
    def _validate_and_fix_data(self, data: Any) -> Optional[pd.DataFrame]:
        """
        Validasi dan konversi data ke DataFrame dengan aman.
        Mencegah error 'ambiguous truth value' untuk DataFrame.
        """
        try:
            if data is None:
                logger.debug("❌ Data is None")
                return None
            
            # Jika sudah DataFrame
            if isinstance(data, pd.DataFrame):
                if data.empty:
                    logger.debug("⚠️ DataFrame is empty")
                    return None
                return data
            
            # Jika string, coba parse
            if isinstance(data, str):
                try:
                    # Coba parse JSON string
                    parsed = json.loads(data)
                    if isinstance(parsed, dict) and 'data' in parsed:
                        df = pd.DataFrame(parsed['data'])
                    elif isinstance(parsed, list):
                        df = pd.DataFrame(parsed)
                    else:
                        df = pd.DataFrame([parsed])
                    
                    if df.empty:
                        return None
                    return df
                except json.JSONDecodeError:
                    # Jika bukan JSON, coba eval (hati-hati!)
                    try:
                        df = pd.DataFrame(eval(data))
                        if df.empty:
                            return None
                        return df
                    except:
                        logger.warning(f"❌ Cannot parse string data: {data[:100]}...")
                        return None
            
            # Jika dict atau list
            if isinstance(data, (dict, list)):
                df = pd.DataFrame(data)
                if df.empty:
                    return None
                return df
            
            logger.warning(f"❌ Unsupported data type: {type(data)}")
            return None
            
        except Exception as e:
            logger.error(f"❌ Error in data validation: {str(e)}")
            return None
    
    def _init_stock_blacklist(self):
        """Inisialisasi blacklist saham yang diketahui stagnan/sampah."""
        # Saham dengan harga mentok, tidak pernah bergerak, atau sangat illiquid
        self.stagnant_blacklist = {
            # Harga mentok < 50 (penny stocks stagnant)
            'KPAS.JK', 'KBLV.JK', 'LAPD.JK', 'LPGI.JK', 'LPPS.JK', 'MAMI.JK',
            'MKTR.JK', 'MLIA.JK', 'MLPL.JK', 'NASA.JK', 'NATO.JK', 'NZIA.JK',
            'PACK.JK', 'PADI.JK', 'PANI.JK', 'PBID.JK', 'PBSA.JK', 'PEHA.JK',
            'PGUN.JK', 'PLAS.JK', 'PLIN.JK', 'PMMP.JK', 'POLA.JK', 'POLI.JK',
            'POLU.JK', 'POOL.JK', 'PPGL.JK', 'PRDA.JK', 'PSDN.JK', 'PSGO.JK',
            'PTDU.JK', 'PTIS.JK', 'PTRO.JK', 'PTSN.JK', 'PUDP.JK', 'PYFA.JK',
            'PZZA.JK', 'RAJA.JK', 'RALS.JK', 'RANC.JK', 'RBMS.JK', 'REAL.JK',
            'RELI.JK', 'RICY.JK', 'RIGS.JK', 'RISE.JK', 'RMKE.JK', 'ROCK.JK',
            'RODA.JK', 'ROTI.JK', 'RUIS.JK', 'SAFE.JK', 'SAGE.JK', 'SAMA.JK',
            'SAMF.JK', 'SAPX.JK', 'SATU.JK', 'SBAT.JK', 'SBMA.JK', 'SCBD.JK',
            'SCNP.JK', 'SCPI.JK', 'SDMU.JK', 'SDPC.JK', 'SDRA.JK', 'SFAN.JK',
            'SGER.JK', 'SGRO.JK', 'SHID.JK', 'SHIP.JK', 'SICO.JK', 'SILO.JK',
            'SINI.JK', 'SIPD.JK', 'SKBM.JK', 'SKLT.JK', 'SKRN.JK', 'SLIS.JK',
            'SMBR.JK', 'SMDR.JK', 'SMGA.JK', 'SMKL.JK', 'SMKM.JK', 'SMMT.JK',
            'SMRU.JK', 'SMSM.JK', 'SNLK.JK', 'SOCI.JK', 'SOFA.JK', 'SOHO.JK',
            'SONA.JK', 'SOSS.JK', 'SOTS.JK', 'SPMA.JK', 'SPTO.JK', 'SQMI.JK',
            'SRAJ.JK', 'SRSN.JK', 'STAA.JK', 'STAR.JK', 'STRK.JK', 'SUGI.JK',
            'SULI.JK', 'SUPR.JK', 'SURE.JK', 'SWAT.JK', 'TALF.JK', 'TAMU.JK',
            'TARA.JK', 'TAXI.JK', 'TBMS.JK', 'TCID.JK', 'TCPI.JK', 'TDPM.JK',
            'TECH.JK', 'TEBE.JK', 'TELE.JK', 'TFAS.JK', 'TFCO.JK', 'TGKA.JK',
            'TIFA.JK', 'TIRT.JK', 'TJWI.JK', 'TMPO.JK', 'TNCA.JK', 'TOPS.JK',
            'TOTL.JK', 'TRGU.JK', 'TRIM.JK', 'TRIN.JK', 'TRIS.JK', 'TRJA.JK',
            'TRUE.JK', 'TRUK.JK', 'TRUS.JK', 'TUGU.JK', 'UANG.JK', 'UCID.JK',
            'UFOE.JK', 'UNIQ.JK', 'UNSP.JK', 'UVCR.JK', 'VAST.JK', 'VICI.JK',
            'VICO.JK', 'VINS.JK', 'VOKS.JK', 'VTNY.JK', 'WAPO.JK', 'WEHA.JK',
            'WGSH.JK', 'WINE.JK', 'WINS.JK', 'WMPP.JK', 'WMUU.JK', 'WOMF.JK',
            'WOOD.JK', 'WOWS.JK', 'YELO.JK', 'YPAS.JK', 'ZATA.JK', 'ZONE.JK',
            'ZBRA.JK', 'ZYRX.JK',
            
            # Delisted/suspended (update Jan 2026)
            'ALMI.JK', 'ARMY.JK', 'ARTI.JK', 'BEBS.JK', 'BIKA.JK', 'CNTX.JK',
            'ENVY.JK', 'FKON.JK', 'HDTX.JK', 'HITS.JK', 'KPAL.JK', 'MAGP.JK',
            'RSGK.JK', 'SKYB.JK', 'SRIL.JK', 'TGRA.JK', 'WICO.JK', 'CHEK.JK',
            'PMUI.JK', 'COIN.JK', 'CDIA.JK', 'NIPS.JK', 'PRAS.JK', 'POSA.JK',
            'INAF.JK', 'WIKA.JK', 'WSKT.JK'
        }
        
        # Premium stocks - saham yang selalu aktif dan likuid
        self.premium_stocks = [
            'BBCA.JK', 'BBRI.JK', 'BMRI.JK', 'BBNI.JK', 'TLKM.JK', 'ASII.JK',
            'UNVR.JK', 'INDF.JK', 'ANTM.JK', 'ADRO.JK', 'CPIN.JK', 'ICBP.JK',
            'INCO.JK', 'ITMG.JK', 'KLBF.JK', 'SMGR.JK', 'PGAS.JK', 'PTBA.JK',
            'UNTR.JK', 'GOTO.JK', 'BRPT.JK', 'MDKA.JK', 'AKRA.JK', 'TPIA.JK',
            'EMTK.JK', 'ESSA.JK', 'EXCL.JK', 'MEDC.JK', 'SRTG.JK', 'TOWR.JK',
            'BNGA.JK', 'BRIS.JK', 'BSDE.JK', 'JPFA.JK', 'JSMR.JK', 'MNCN.JK',
            'PGEO.JK', 'SIDO.JK', 'TINS.JK', 'ACES.JK', 'ADMR.JK', 'AMMN.JK',
            'AVIA.JK', 'BUKA.JK', 'BUMI.JK', 'BYAN.JK', 'CTRA.JK', 'DSSA.JK',
            'HEAL.JK', 'INKP.JK', 'INTP.JK', 'MAPA.JK', 'MTEL.JK', 'NCKL.JK',
            'SCMA.JK', 'TBIG.JK', 'WIKA.JK', 'WSKT.JK'  # Masih aktif di Jan 2026
        ]
    
    def _get_active_stocks(self) -> List[str]:
        """Dapatkan daftar saham aktif dengan filter cerdas untuk hindari saham sampah."""
        
        if self._verified_stocks is not None:
            return self._verified_stocks
        
        logger.info("🔄 Memulai screening saham dengan filter cerdas...")
        
        # Gabungkan semua sumber saham
        all_stocks = list(set(
            self._get_base_stocks() + 
            self.premium_stocks +
            self._get_additional_liquid_stocks()
        ))
        
        # Filter out blacklisted stocks
        filtered_stocks = [s for s in all_stocks if s not in self.stagnant_blacklist]
        
        logger.info(f"📊 Total stocks setelah filter blacklist: {len(filtered_stocks)}")
        
        # Screening dengan multi-threading untuk efisiensi
        screened_stocks = self._screen_stocks_with_scoring(filtered_stocks)
        
        # Jika hasil kurang dari 100, tambahkan premium stocks sebagai backup
        if len(screened_stocks) < 100:
            backup_needed = 100 - len(screened_stocks)
            for stock in self.premium_stocks:
                if stock not in screened_stocks and stock not in self.stagnant_blacklist:
                    screened_stocks.append(stock)
                    backup_needed -= 1
                    if backup_needed <= 0:
                        break
        
        # Simpan cache
        self._verified_stocks = screened_stocks[:200]  # Maksimal 200 saham
        
        logger.info(f"✅ FINAL: {len(self._verified_stocks)} saham aktif terpilih")
        logger.info(f"🎯 Top 10: {', '.join(self._verified_stocks[:10])}")
        
        return self._verified_stocks
    
    def _get_base_stocks(self) -> List[str]:
        """Dapatkan daftar saham dasar dari berbagai sumber."""
        base_stocks = [
            # LQ45 Core (45 saham)
            'AADI.JK', 'ACES.JK', 'ADMR.JK', 'ADRO.JK', 'AKRA.JK', 'AMMN.JK', 
            'ANTM.JK', 'ASII.JK', 'AVIA.JK', 'BBCA.JK', 'BBNI.JK', 'BBRI.JK', 
            'BMRI.JK', 'BRMS.JK', 'BRPT.JK', 'BUKA.JK', 'BUMI.JK', 'BYAN.JK', 
            'CPIN.JK', 'CTRA.JK', 'DSSA.JK', 'EMTK.JK', 'ESSA.JK', 'EXCL.JK', 
            'GOTO.JK', 'HEAL.JK', 'ICBP.JK', 'INCO.JK', 'INDF.JK', 'INKP.JK', 
            'INTP.JK', 'ITMG.JK', 'JPFA.JK', 'JSMR.JK', 'KLBF.JK', 'MAPA.JK', 
            'MDKA.JK', 'MEDC.JK', 'MTEL.JK', 'NCKL.JK', 'PGAS.JK', 'PTBA.JK', 
            'PGEO.JK', 'SCMA.JK', 'SIDO.JK', 'SMGR.JK', 'SRTG.JK', 'TBIG.JK', 
            'TINS.JK', 'TLKM.JK', 'TOWR.JK', 'TPIA.JK', 'UNTR.JK', 'UNVR.JK',
            
            # IDX80 dan high performers
            'AGII.JK', 'AGRO.JK', 'AKSI.JK', 'ALTO.JK', 'AMRT.JK', 'APLN.JK',
            'ARTO.JK', 'ASRI.JK', 'ASSA.JK', 'BACA.JK', 'BALI.JK', 'BANK.JK',
            'BBHI.JK', 'BBKP.JK', 'BBTN.JK', 'BCAP.JK', 'BFIN.JK', 'BINA.JK',
            'BJBR.JK', 'BJTM.JK', 'BKSW.JK', 'BMAS.JK', 'BNGA.JK', 'BNII.JK',
            'BRIS.JK', 'BSDE.JK', 'BSSR.JK', 'BTPS.JK', 'BVIC.JK', 'CASA.JK',
            'CMNP.JK', 'CMRY.JK', 'CSAP.JK', 'CSMI.JK', 'DMAS.JK', 'DMND.JK',
            'DOID.JK', 'DSNG.JK', 'DUTI.JK', 'ELSA.JK', 'ENRG.JK', 'FAST.JK',
            'FREN.JK', 'GEMS.JK', 'GIAA.JK', 'GOOD.JK', 'HEXA.JK', 'HOKI.JK',
            'HRTA.JK', 'HRUM.JK', 'IBFN.JK', 'IFSH.JK', 'IMAS.JK', 'IMJS.JK',
            'IMPC.JK', 'INAI.JK', 'INCF.JK', 'INDO.JK', 'INDR.JK', 'INDX.JK',
            'INDY.JK', 'INPC.JK', 'INPP.JK', 'INPS.JK', 'INRU.JK', 'IPCC.JK',
            'IPCM.JK', 'IPOL.JK', 'ISAT.JK', 'ISSP.JK', 'ITIC.JK', 'JARR.JK',
            'JAST.JK', 'JECC.JK', 'JIHD.JK', 'JKSW.JK', 'JMAS.JK', 'JRPT.JK',
            'KAEF.JK', 'KARW.JK', 'KBAG.JK', 'KBLI.JK', 'KBLM.JK', 'KDSI.JK',
            'KEEN.JK', 'KIAS.JK', 'KIJA.JK', 'KKES.JK', 'KMDS.JK', 'KMTR.JK',
            'KOBX.JK', 'KOPI.JK', 'KPPI.JK', 'KRAS.JK', 'KREN.JK', 'LAND.JK',
            'LCKM.JK', 'LEAD.JK', 'LIFE.JK', 'LINK.JK', 'LION.JK', 'LMAX.JK',
            'LMSH.JK', 'LPGI.JK', 'LPIN.JK', 'LPLI.JK', 'LPPF.JK', 'LRNA.JK',
            'LTLS.JK', 'LUCK.JK', 'MAIN.JK', 'MAPI.JK', 'MARI.JK', 'MARK.JK',
            'MASA.JK', 'MAYA.JK', 'MBSS.JK', 'MBTO.JK', 'MCAS.JK', 'MCOR.JK',
            'MDIA.JK', 'MDLN.JK', 'MDRN.JK', 'MEGA.JK', 'META.JK', 'MGNA.JK',
            'MGRO.JK', 'MICE.JK', 'MIKA.JK', 'MINA.JK', 'MITI.JK', 'MKPI.JK',
            'MLBI.JK', 'MLPT.JK', 'MLTX.JK', 'MNCN.JK', 'MPMX.JK', 'MPPA.JK',
            'MRAT.JK', 'MSIN.JK', 'MSKY.JK', 'MTDL.JK', 'MTFN.JK', 'MTLA.JK',
            'MTMH.JK', 'MTPS.JK', 'MTSM.JK', 'MTWI.JK', 'MYOH.JK', 'MYOR.JK',
            'MYTX.JK', 'NETV.JK', 'NFCX.JK', 'NIKL.JK', 'NRCA.JK', 'NSSS.JK',
            'NTBK.JK', 'NUSA.JK', 'OBMD.JK', 'OILS.JK', 'OKAS.JK', 'OMRE.JK',
            'OPMS.JK', 'PAMG.JK', 'PCAR.JK', 'PDAI.JK', 'PDES.JK', 'PEGE.JK',
            'PICO.JK', 'PKPK.JK', 'PMJS.JK', 'PORT.JK', 'POWR.JK', 'PPRE.JK',
            'PRIM.JK', 'PSAB.JK', 'PSKT.JK', 'RMKO.JK', 'SBSN.JK', 'SMRA.JK',
            'SMMA.JK', 'SSIA.JK', 'STTP.JK', 'TIRA.JK', 'TKIM.JK', 'TMAS.JK',
            'TPMA.JK', 'TRST.JK', 'ULTJ.JK', 'UNIC.JK', 'UNIT.JK', 'VIVA.JK',
            'WEGE.JK', 'WTON.JK'
        ]
        
        return base_stocks
    
    def _get_additional_liquid_stocks(self) -> List[str]:
        """Tambahan saham likuid dari sektor-sektor penting."""
        return [
            # Banking & Finance
            'BBTN.JK', 'BNII.JK', 'BACA.JK', 'BJBR.JK', 'BJTM.JK',
            
            # Mining & Resources
            'BRMS.JK', 'MDKA.JK', 'TINS.JK', 'BYAN.JK', 'BUMI.JK',
            
            # Consumer
            'SIDO.JK', 'ULTJ.JK', 'MYOR.JK', 'TCPI.JK', 'MLBI.JK',
            
            # Property & Real Estate
            'BSDE.JK', 'CTRA.JK', 'ASRI.JK', 'PWON.JK', 'JRPT.JK',
            
            # Infrastructure
            'WIKA.JK', 'JSMR.JK', 'ADHI.JK', 'PTPP.JK', 'WEGE.JK',
            
            # Technology
            'GOTO.JK', 'DMMX.JK', 'ARTO.JK', 'TCID.JK', 'DSSA.JK',
            
            # Energy
            'AKRA.JK', 'HRUM.JK', 'ITMG.JK', 'ENRG.JK', 'MEDC.JK'
        ]
    
    def _screen_stocks_with_scoring(self, stocks: List[str]) -> List[str]:
        """Screening saham dengan sistem scoring multi-parameter."""
        
        scored_results = []
        max_workers = min(10, len(stocks) // 10 + 1)
        
        # Gunakan ThreadPoolExecutor untuk parallel processing
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_stock = {
                executor.submit(self._evaluate_stock, stock): stock 
                for stock in stocks[:300]  # Batasi screening untuk efisiensi
            }
            
            for future in concurrent.futures.as_completed(future_to_stock):
                stock = future_to_stock[future]
                try:
                    result = future.result()
                    if result:
                        scored_results.append(result)
                except Exception as e:
                    logger.debug(f"⚠️ Error screening {stock}: {str(e)[:50]}")
        
        # Sort berdasarkan score tertinggi
        scored_results.sort(key=lambda x: x['total_score'], reverse=True)
        
        # Ambil saham dengan score minimal 70
        qualified_stocks = [
            r['symbol'] for r in scored_results 
            if r['total_score'] >= 70 and r['passed_filters']
        ]
        
        logger.info(f"📊 Screening results: {len(qualified_stocks)}/{len(scored_results)} saham qualified")
        
        return qualified_stocks
    
    def _evaluate_stock(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Evaluasi single stock dengan multiple criteria."""
        
        if symbol in self.invalid_symbols:
            return None
        
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="90d")
            
            # Validasi data dengan fungsi baru
            hist = self._validate_and_fix_data(hist)
            
            # FILTER 1: Data availability
            if hist is None or len(hist) < 30:
                self.invalid_symbols.add(symbol)
                return None
            
            # Pastikan kolom ada
            if 'Close' not in hist.columns or 'Volume' not in hist.columns:
                self.invalid_symbols.add(symbol)
                return None
            
            close_prices = hist['Close']
            volumes = hist['Volume']
            
            # FILTER 2: Price range (hindari saham flat)
            if len(close_prices) == 0:
                self.stagnant_symbols.add(symbol)
                return None
            
            price_min = float(close_prices.min())
            price_max = float(close_prices.max())
            
            if price_min > 0:
                price_range_pct = ((price_max - price_min) / price_min) * 100
            else:
                price_range_pct = 0
            
            if price_range_pct < 3:  # Range harga kurang dari 3% dalam 90 hari
                self.stagnant_symbols.add(symbol)
                logger.debug(f"❌ {symbol}: Price too flat ({price_range_pct:.1f}%)")
                return None
            
            # FILTER 3: Volume (hindari illiquid)
            if len(volumes) > 0:
                avg_volume = float(volumes.mean())
            else:
                avg_volume = 0
            
            if avg_volume < 100000:  # Volume rata-rata kurang dari 100k
                self.stagnant_symbols.add(symbol)
                logger.debug(f"❌ {symbol}: Volume too low ({avg_volume:,.0f})")
                return None
            
            # FILTER 4: Volume consistency
            volume_days = (volumes > avg_volume * 0.1).sum()
            if volume_days < len(volumes) * 0.3:  # Kurang dari 30% hari ada volume signifikan
                logger.debug(f"⚠️ {symbol}: Inconsistent volume ({volume_days}/{len(volumes)} days)")
            
            # ========== SCORING SYSTEM ==========
            
            # 1. PRICE MOVEMENT SCORE (0-40)
            if price_range_pct < 5:
                movement_score = 20
            elif price_range_pct < 10:
                movement_score = 25
            elif price_range_pct < 20:
                movement_score = 30
            elif price_range_pct < 40:
                movement_score = 35
            else:
                movement_score = 40
            
            # 2. LIQUIDITY SCORE (0-30)
            if avg_volume < 500000:
                liquidity_score = 15
            elif avg_volume < 2000000:
                liquidity_score = 20
            elif avg_volume < 10000000:
                liquidity_score = 25
            else:
                liquidity_score = 30
            
            # 3. TREND SCORE (0-20)
            returns_90d = ((close_prices.iloc[-1] - close_prices.iloc[0]) / close_prices.iloc[0]) * 100
            
            if returns_90d > 30:
                trend_score = 20
            elif returns_90d > 15:
                trend_score = 18
            elif returns_90d > 5:
                trend_score = 15
            elif returns_90d > 0:
                trend_score = 12
            elif returns_90d > -10:
                trend_score = 8
            else:
                trend_score = 5
            
            # 4. VOLATILITY SCORE (0-10) - volatilitas sehat
            price_std = close_prices.std()
            avg_price = close_prices.mean()
            volatility_pct = (price_std / avg_price) * 100 if avg_price > 0 else 0
            
            if 2 <= volatility_pct <= 10:
                volatility_score = 10
            elif 1 <= volatility_pct < 2 or 10 < volatility_pct <= 15:
                volatility_score = 7
            else:
                volatility_score = 3
            
            # 5. PRICE LEVEL BONUS (0-5)
            current_price = close_prices.iloc[-1]
            if current_price > 1000:  # > 1000 = blue chip
                price_bonus = 5
            elif current_price > 500:
                price_bonus = 4
            elif current_price > 100:
                price_bonus = 3
            elif current_price > 50:
                price_bonus = 2
            else:
                price_bonus = 1
            
            # TOTAL SCORE
            total_score = movement_score + liquidity_score + trend_score + volatility_score + price_bonus
            
            result = {
                'symbol': symbol,
                'total_score': total_score,
                'passed_filters': True,
                'metrics': {
                    'price_range_pct': price_range_pct,
                    'avg_volume': avg_volume,
                    'returns_90d': returns_90d,
                    'volatility_pct': volatility_pct,
                    'current_price': current_price
                }
            }
            
            logger.debug(f"✅ {symbol}: Score={total_score}, Range={price_range_pct:.1f}%, Vol={avg_volume:,.0f}")
            return result
            
        except Exception as e:
            self.invalid_symbols.add(symbol)
            logger.debug(f"⚠️ {symbol}: Error in evaluation - {str(e)[:50]}")
            return None
    
    def get_stock_quality_report(self, symbol: str) -> Dict[str, Any]:
        """Dapatkan laporan kualitas untuk stock tertentu."""
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="90d")
            
            # Validasi data dengan fungsi baru
            hist = self._validate_and_fix_data(hist)
            if hist is None:
                return {
                    'error': 'No data available',
                    'symbol': symbol,
                    'quality_score': -100,
                    'is_stagnant': True,
                    'issues': ['No historical data'],
                    'strengths': []
                }
            
            close_prices = hist['Close']
            volumes = hist['Volume']
            
            # Validasi data series
            if len(close_prices) == 0 or len(volumes) == 0:
                return {
                    'error': 'Insufficient data',
                    'symbol': symbol,
                    'quality_score': -100,
                    'is_stagnant': True,
                    'issues': ['Insufficient data points'],
                    'strengths': []
                }
            
            # Calculate metrics dengan error handling
            try:
                current_price = float(close_prices.iloc[-1]) if len(close_prices) > 0 else 0
                price_high = float(close_prices.max())
                price_low = float(close_prices.min())
                
                # Hindari division by zero
                if price_low > 0:
                    price_range_pct = ((price_high - price_low) / price_low) * 100
                else:
                    price_range_pct = 0
                
                avg_volume = float(volumes.mean()) if len(volumes) > 0 else 0
                max_volume = float(volumes.max()) if len(volumes) > 0 else 0
                
                # Volume consistency
                if avg_volume > 0:
                    volume_consistency = (volumes > avg_volume * 0.3).mean() * 100
                else:
                    volume_consistency = 0
                
                # Returns
                if len(close_prices) >= 2 and close_prices.iloc[0] > 0:
                    returns_90d = ((close_prices.iloc[-1] - close_prices.iloc[0]) / close_prices.iloc[0]) * 100
                else:
                    returns_90d = 0
                
                # Volatility
                if len(close_prices) > 1:
                    volatility = close_prices.pct_change().std() * 100
                else:
                    volatility = 0
                
            except Exception as calc_error:
                logger.error(f"Error calculating metrics for {symbol}: {str(calc_error)}")
                return {
                    'error': f'Calculation error: {str(calc_error)}',
                    'symbol': symbol,
                    'quality_score': -50,
                    'is_stagnant': True,
                    'issues': ['Error in metric calculation'],
                    'strengths': []
                }
            
            metrics = {
                'symbol': symbol,
                'current_price': current_price,
                'price_90d_high': price_high,
                'price_90d_low': price_low,
                'price_range_pct': price_range_pct,
                'avg_volume': avg_volume,
                'max_volume': max_volume,
                'volume_consistency': volume_consistency,
                'returns_90d': returns_90d,
                'volatility': volatility,
                'data_points': len(hist)
            }
            
            # Quality assessment
            quality_score = 0
            issues = []
            strengths = []
            
            if price_range_pct < 3:
                issues.append('Harga terlalu flat (range < 3%)')
                quality_score -= 30
            elif price_range_pct > 20:
                strengths.append('Pergerakan harga baik')
                quality_score += 20
            
            if avg_volume < 100000:
                issues.append('Volume sangat rendah')
                quality_score -= 30
            elif avg_volume > 1000000:
                strengths.append('Likuiditas baik')
                quality_score += 20
            
            if volume_consistency < 30:
                issues.append('Volume tidak konsisten')
                quality_score -= 10
            
            metrics['quality_score'] = quality_score
            metrics['issues'] = issues
            metrics['strengths'] = strengths
            metrics['is_stagnant'] = quality_score < 0
            metrics['error'] = None  # Explicitly set to None jika tidak ada error
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error in get_stock_quality_report for {symbol}: {str(e)}")
            return {
                'error': str(e),
                'symbol': symbol,
                'quality_score': -100,
                'is_stagnant': True,
                'issues': ['System error'],
                'strengths': []
            }
    
    def get_assets(self, category: str, limit: int = 200, force_update: bool = False) -> List[str]:
        """Dapatkan list simbol aset untuk kategori tertentu."""
        if category not in ['indonesia_stocks', 'forex', 'us_stocks']:
            raise ValueError(f"Invalid category: {category}. Pilih: indonesia_stocks, forex, us_stocks.")
        
        if category == 'indonesia_stocks':
            return self._get_active_stocks()[:limit]
        
        cache_key = f"{category}_assets"
        
        if not force_update and cache_key in self.cache:
            cache_data = self.cache[cache_key]
            cache_time = datetime.fromisoformat(cache_data['timestamp'])
            if datetime.now() - cache_time < timedelta(days=CACHE_TTL_DAYS):
                logger.info(f"📦 Using cached assets for {category}")
                return cache_data['assets'][:limit]
        
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
    
    def get_active_assets(self, category: str = 'indonesia_stocks',
                         min_volume: float = 5_000_000,
                         min_volatility: float = 0.015,
                         min_price_change: float = 0.02,
                         limit: int = 25) -> List[str]:
        """Ambil aset teraktif dengan filter tambahan."""
        
        print(f"\n🔥 SCREENING ASET AKTIF ({category})")
        print("=" * 60)
        
        if category != 'indonesia_stocks':
            return self._get_predefined_active(category, limit)
        
        # Gunakan saham yang sudah terverifikasi
        active_stocks = self._get_active_stocks()[:100]
        print(f"📊 Total verified stocks: {len(active_stocks)}")
        
        screened_stocks = []
        results = []
        
        for symbol in active_stocks:
            try:
                ticker = yf.Ticker(symbol)
                hist = ticker.history(period="90d", interval="1d")
                
                # Validasi data
                hist = self._validate_and_fix_data(hist)
                if hist is None:
                    continue
                
                if len(hist) < 30:
                    continue
                
                # Pastikan kolom ada
                if 'Close' not in hist.columns or 'Volume' not in hist.columns:
                    continue
                
                avg_volume = hist['Volume'].mean()
                if avg_volume < min_volume:
                    continue
                
                recent_returns = hist['Close'][-30:].pct_change().dropna()
                volatility = recent_returns.std() if len(recent_returns) > 5 else 0
                
                if volatility < min_volatility:
                    continue
                
                price_change = (hist['Close'].iloc[-1] - hist['Close'].iloc[-30]) / hist['Close'].iloc[-30]
                if abs(price_change) < min_price_change:
                    continue
                
                volume_5d = hist['Volume'][-5:].mean()
                volume_30d = hist['Volume'][-30:].mean()
                volume_trend = volume_5d / volume_30d if volume_30d > 0 else 1
                
                # Score calculation
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
                    'volume_trend': volume_trend
                })
                
                time.sleep(self.rate_limit_delay)
                
            except Exception:
                continue
        
        results.sort(key=lambda x: x['score'], reverse=True)
        screened_stocks = [r['symbol'] for r in results[:limit]]
        
        if screened_stocks:
            print(f"✅ Ditemukan {len(screened_stocks)} aset aktif")
            print(f"🎯 Top 5: {screened_stocks[:5]}")
        else:
            print("⚠️ Tidak ada aset aktif ditemukan, gunakan default")
            screened_stocks = active_stocks[:limit]
        
        return screened_stocks
    
    def generate_trading_signals(self, symbols: List[str] = None,
                               min_bars: int = 40,
                               rsi_oversold: int = 30,
                               rsi_overbought: int = 70) -> List[Dict[str, Any]]:
        """Generate trading signals dengan filter kualitas."""
        
        if symbols is None:
            symbols = self.get_active_assets('indonesia_stocks', limit=25)
        
        print(f"\n📈 GENERATING TRADING SIGNALS ({len(symbols)} symbols)")
        print("=" * 60)
        
        signals = []
        
        for symbol in symbols:
            try:
                # Cek kualitas stock sebelum analisa
                quality_report = self.get_stock_quality_report(symbol)
                
                # Validasi hasil quality report
                if not isinstance(quality_report, dict):
                    print(f"  ⚠️ {symbol}: Invalid quality report type - skipped")
                    continue
                
                if 'error' in quality_report and quality_report['error']:
                    print(f"  ⚠️ {symbol}: Error in quality check - {quality_report.get('error', 'Unknown')}")
                    continue
                
                if quality_report.get('is_stagnant', False):
                    print(f"  ⚠️ {symbol}: Saham stagnan - skipped")
                    continue
                
                print(f"  🔍 Analisa {symbol}...")
                
                ticker = yf.Ticker(symbol)
                hist = ticker.history(period="90d", interval="1d")
                
                # Validasi data historis
                hist = self._validate_and_fix_data(hist)
                if hist is None:
                    print(f"    ⚠️ Tidak ada data historis yang valid")
                    continue
                
                if len(hist) < min_bars:
                    print(f"    ⚠️ Data tidak cukup: {len(hist)} < {min_bars} bars")
                    continue
                
                # Pastikan kolom ada
                required_columns = ['Close', 'Volume']
                for col in required_columns:
                    if col not in hist.columns:
                        print(f"    ⚠️ Kolom {col} tidak ditemukan")
                        continue
                
                # Analisis teknikal dengan error handling
                try:
                    close_series = hist['Close']
                    volume_series = hist['Volume']
                    
                    # RSI Calculation
                    delta = close_series.diff()
                    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                    
                    # Hindari division by zero
                    with np.errstate(divide='ignore', invalid='ignore'):
                        rs = gain / loss
                        rs = rs.replace([np.inf, -np.inf], np.nan).fillna(0)
                        rsi = 100 - (100 / (1 + rs))
                    
                    # Moving Averages
                    sma_20 = close_series.rolling(window=20).mean()
                    sma_50 = close_series.rolling(window=50).mean()
                    
                    # MACD
                    exp12 = close_series.ewm(span=12, adjust=False).mean()
                    exp26 = close_series.ewm(span=26, adjust=False).mean()
                    macd = exp12 - exp26
                    signal_line = macd.ewm(span=9, adjust=False).mean()
                    
                    # Get current values
                    current_price = float(close_series.iloc[-1]) if len(close_series) > 0 else 0
                    current_rsi = float(rsi.iloc[-1]) if len(rsi) > 0 else 50
                    current_macd = float(macd.iloc[-1]) if len(macd) > 0 else 0
                    current_signal = float(signal_line.iloc[-1]) if len(signal_line) > 0 else 0
                    
                except Exception as calc_error:
                    print(f"    ❌ Error dalam kalkulasi indikator: {str(calc_error)}")
                    continue
                
                # Generate signals
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
                if len(macd) >= 2 and len(signal_line) >= 2:
                    if current_macd > current_signal and macd.iloc[-2] <= signal_line.iloc[-2]:
                        signal_strength += 2
                        signal_reasons.append("MACD bullish crossover")
                        if signal_type == "HOLD":
                            signal_type = "BUY"
                    elif current_macd < current_signal and macd.iloc[-2] >= signal_line.iloc[-2]:
                        signal_strength += 2
                        signal_reasons.append("MACD bearish crossover")
                        if signal_type == "HOLD":
                            signal_type = "SELL"
                
                # Moving Average Crossover
                if len(sma_20) >= 2 and len(sma_50) >= 2:
                    if sma_20.iloc[-1] > sma_50.iloc[-1] and sma_20.iloc[-2] <= sma_50.iloc[-2]:
                        signal_strength += 3
                        signal_reasons.append("Golden Cross (SMA20 > SMA50)")
                        signal_type = "BUY"
                    elif sma_20.iloc[-1] < sma_50.iloc[-1] and sma_20.iloc[-2] >= sma_50.iloc[-2]:
                        signal_strength += 3
                        signal_reasons.append("Death Cross (SMA20 < SMA50)")
                        signal_type = "SELL"
                
                # Volume Confirmation
                volume_sma = volume_series.rolling(window=20).mean()
                current_volume = float(volume_series.iloc[-1]) if len(volume_series) > 0 else 0
                volume_sma_last = float(volume_sma.iloc[-1]) if len(volume_sma) > 0 and not pd.isna(volume_sma.iloc[-1]) else 1
                
                if volume_sma_last > 0:
                    volume_ratio = current_volume / volume_sma_last
                else:
                    volume_ratio = 1
                
                if volume_ratio > 1.5 and signal_type != "HOLD":
                    signal_strength += 1
                    signal_reasons.append(f"Volume spike ({volume_ratio:.1f}x)")
                
                # Final decision
                if signal_strength >= 4 and signal_type != "HOLD":
                    signal_data = {
                        'symbol': symbol,
                        'signal': signal_type,
                        'strength': signal_strength,
                        'reasons': signal_reasons,
                        'price': current_price,
                        'rsi': current_rsi,
                        'volume_ratio': volume_ratio,
                        'data_points': len(hist),
                        'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        'error': None  # Explicitly set
                    }
                    
                    signals.append(signal_data)
                    print(f"    ✅ {signal_type} (Strength: {signal_strength}/10)")
                else:
                    print(f"    ⚪ HOLD (Strength: {signal_strength}/10)")
                
                time.sleep(self.rate_limit_delay)
                
            except Exception as e:
                print(f"    ❌ Error: {str(e)[:50]}")
                # Tambahkan signal error untuk tracking
                error_signal = {
                    'symbol': symbol,
                    'signal': 'ERROR',
                    'strength': 0,
                    'reasons': [f'Error: {str(e)[:100]}'],
                    'price': 0,
                    'rsi': 50,
                    'volume_ratio': 1,
                    'data_points': 0,
                    'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    'error': str(e)
                }
                signals.append(error_signal)
                continue
        
        # Filter out error signals jika ingin
        valid_signals = [s for s in signals if s.get('error') is None]
        valid_signals.sort(key=lambda x: x['strength'], reverse=True)
        
        print(f"\n📊 Signal Summary: {len(valid_signals)} valid signals generated")
        return valid_signals
    
    # Helper methods (sebelumnya ada di code asli)
    def _get_predefined_active(self, category: str, limit: int) -> List[str]:
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
        return self._get_static_assets(category)[:limit]
    
    def _get_static_assets(self, category: str) -> List[str]:
        if category == 'us_stocks':
            return [
                'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'TSLA', 'NVDA',
                'JPM', 'V', 'JNJ', 'WMT', 'PG', 'MA', 'UNH', 'HD'
            ]
        elif category == 'indonesia_stocks':
            return self._get_active_stocks()
        elif category == 'forex':
            return [
                'EURUSD=X', 'USDJPY=X', 'GBPUSD=X', 'AUDUSD=X', 'USDCAD=X',
                'USDCHF=X', 'NZDUSD=X', 'EURGBP=X', 'EURJPY=X', 'GBPJPY=X'
            ]
        return []
    
    def _load_cache(self) -> Dict:
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, 'r') as f:
                    return json.load(f)
            except:
                logger.warning("⚠️ Corrupted cache, starting fresh.")
        return {}
    
    def _save_cache(self):
        with open(CACHE_FILE, 'w') as f:
            json.dump(self.cache, f)
        logger.debug("💾 Cache saved.")


# =============================================
# 🚀 CONTOH PENGGUNAAN
# =============================================
if __name__ == "__main__":
    provider = NonCryptoAssetsProvider()
    
    print("🚀 NON-CRYPTO ASSETS PROVIDER - SMART FILTER SYSTEM")
    print("=" * 60)
    
    # Test kualitas saham
    print("\n🧪 TEST KUALITAS SAHAM:")
    test_stocks = ['BBCA.JK', 'KPAS.JK', 'ANTM.JK', 'UNKNOWN.JK']
    
    for stock in test_stocks:
        report = provider.get_stock_quality_report(stock)
        if 'error' not in report or report['error'] is None:
            status = "✅ BAIK" if not report.get('is_stagnant') else "❌ STAGNAN"
            print(f"  {stock}: {status} | Range: {report['price_range_pct']:.1f}% | Volume: {report['avg_volume']:,.0f}")
        else:
            print(f"  {stock}: {report['error']}")
    
    # 1. Dapatkan saham aktif
    print("\n1️⃣ Mengambil saham aktif terbaik...")
    active_stocks = provider.get_active_assets(
        category='indonesia_stocks',
        min_volume=5_000_000,
        min_volatility=0.015,
        limit=25
    )
    print(f"   ✅ {len(active_stocks)} saham aktif: {active_stocks[:10]}...")
    
    # 2. Generate trading signals
    print("\n2️⃣ Generating trading signals...")
    signals = provider.generate_trading_signals(
        symbols=active_stocks[:20],
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
            print(f"   Reasons: {', '.join(signal['reasons'][:3])}")
    else:
        print("\n⚠️ Tidak ada signal trading yang ditemukan")
    
    print("\n" + "=" * 60)
    print("🎯 KEUNGGULAN SISTEM BARU:")
    print("   • Smart blacklist untuk saham stagnan (KPAS.JK, dll)")
    print("   • Scoring system multi-parameter")
    print("   • Volume & price movement validation")
    print("   • Multi-threading untuk screening cepat")
    print("   • Quality report untuk tiap saham")
    print("   • Data validation system untuk hindari ambiguous errors")
    print("\n✅ Sistem filter cerdas telah aktif!")
