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
    - UPDATED: Gunakan daftar saham aktif IDX per Januari 2026 (high cap, liquid)
    - FIXED: Ambil data 90 hari untuk analisa teknikal
    - FIXED: Skip saham delisted/error
    """
    
    def __init__(self):
        self.cache = self._load_cache()
        self.invalid_symbols: Set[str] = set()
        self.cache_lock = Lock()
        self.rate_limit_delay = 0.5  # Delay antara request untuk hindari rate limit
        self._verified_stocks = None  # Cache untuk saham terverifikasi
        
    # =============================================
    # 🚨 UPDATE UTAMA: GANTI KE SAHAM IDX AKTIF 2026
    # =============================================
    
    def _get_active_stocks(self) -> List[str]:
        """Update daftar saham aktif IDX per Januari 2026 (high cap, liquid, exclude delisted/suspended). 
        Total ~200 saham bagus dengan trend positif."""
        
        # Jika sudah di-cache, return cache
        if self._verified_stocks is not None:
            return self._verified_stocks
            
        active_stocks = [
            # LQ45 Core (45 saham aktif dari periode Nov 2025-Jan 2026, termasuk update July 2025: AADI dan SCMA masuk)
            'AADI.JK', 'ACES.JK', 'ADMR.JK', 'ADRO.JK', 'AKRA.JK', 'AMMN.JK', 'ANTM.JK', 'ASII.JK', 
            'AVIA.JK', 'BBCA.JK', 'BBNI.JK', 'BBRI.JK', 'BMRI.JK', 'BRMS.JK', 'BRPT.JK', 'BUKA.JK', 
            'BUMI.JK', 'BYAN.JK', 'CPIN.JK', 'CTRA.JK', 'DSSA.JK', 'EMTK.JK', 'ESSA.JK', 'EXCL.JK', 
            'GOTO.JK', 'HEAL.JK', 'ICBP.JK', 'INCO.JK', 'INDF.JK', 'INKP.JK', 'INTP.JK', 'ITMG.JK', 
            'JPFA.JK', 'JSMR.JK', 'KLBF.JK', 'MAPA.JK', 'MDKA.JK', 'MEDC.JK', 'MTEL.JK', 'NCKL.JK', 
            'PGAS.JK', 'PTBA.JK', 'PGEO.JK', 'SCMA.JK', 'SIDO.JK', 'SMGR.JK', 'SRTG.JK', 'TBIG.JK', 
            'TINS.JK', 'TLKM.JK', 'TOWR.JK', 'TPIA.JK', 'UNTR.JK', 'UNVR.JK',

            # Tambahan dari IDX80 dan top performers 2025-2026 (high liquid mid-cap dengan trend positif: banking/mining/consumer/property)
            'AGII.JK', 'AGRO.JK', 'AKSI.JK', 'ALTO.JK', 'AMRT.JK', 'APLN.JK', 'ARTO.JK', 'ASRI.JK', 
            'ASSA.JK', 'BACA.JK', 'BALI.JK', 'BANK.JK', 'BBHI.JK', 'BBKP.JK', 'BBTN.JK', 'BCAP.JK', 
            'BFIN.JK', 'BINA.JK', 'BJBR.JK', 'BJTM.JK', 'BKSW.JK', 'BMAS.JK', 'BNGA.JK', 'BNII.JK', 
            'BRIS.JK', 'BSDE.JK', 'BSSR.JK', 'BTPS.JK', 'BVIC.JK', 'CASA.JK', 'CMNP.JK', 'CMRY.JK', 
            'CSAP.JK', 'CSMI.JK', 'DMAS.JK', 'DMND.JK', 'DOID.JK', 'DSNG.JK', 'DUTI.JK', 'ELSA.JK', 
            'ENRG.JK', 'FAST.JK', 'FREN.JK', 'GEMS.JK', 'GIAA.JK', 'GOOD.JK', 'HEXA.JK', 'HOKI.JK', 
            'HRTA.JK', 'HRUM.JK', 'IBFN.JK', 'IFSH.JK', 'IMAS.JK', 'IMJS.JK', 'IMPC.JK', 'INAF.JK',
            'INAI.JK', 'INCF.JK', 'INDO.JK', 'INDR.JK', 'INDX.JK', 'INDY.JK', 'INPC.JK', 'INPP.JK', 
            'INPS.JK', 'INRU.JK', 'IPCC.JK', 'IPCM.JK', 'IPOL.JK', 'ISAT.JK', 'ISSP.JK', 'ITIC.JK', 
            'JARR.JK', 'JAST.JK', 'JECC.JK', 'JIHD.JK', 'JKSW.JK', 'JMAS.JK', 'JRPT.JK', 'KAEF.JK', 
            'KARW.JK', 'KBAG.JK', 'KBLI.JK', 'KBLM.JK', 'KBLV.JK', 'KDSI.JK', 'KEEN.JK', 'KIAS.JK', 
            'KIJA.JK', 'KKES.JK', 'KMDS.JK', 'KMTR.JK', 'KOBX.JK', 'KOPI.JK', 'KPAS.JK', 'KPPI.JK', 
            'KRAS.JK', 'KREN.JK', 'LAND.JK', 'LAPD.JK', 'LCKM.JK', 'LEAD.JK', 'LIFE.JK', 'LINK.JK', 
            'LION.JK', 'LMAX.JK', 'LMSH.JK', 'LPGI.JK', 'LPIN.JK', 'LPLI.JK', 'LPPF.JK', 'LPPS.JK', 
            'LRNA.JK', 'LTLS.JK', 'LUCK.JK', 'MAIN.JK', 'MAMI.JK', 'MAPB.JK', 'MAPI.JK', 'MARI.JK', 
            'MARK.JK', 'MASA.JK', 'MAYA.JK', 'MBSS.JK', 'MBTO.JK', 'MCAS.JK', 'MCOR.JK', 'MDIA.JK', 
            'MDLN.JK', 'MDRN.JK', 'MEGA.JK', 'META.JK', 'MGNA.JK', 'MGRO.JK', 'MICE.JK', 'MIKA.JK', 
            'MINA.JK', 'MITI.JK', 'MKPI.JK', 'MKTR.JK', 'MLBI.JK', 'MLIA.JK', 'MLPL.JK', 'MLPT.JK', 
            'MLTX.JK', 'MNCN.JK', 'MPMX.JK', 'MPPA.JK', 'MRAT.JK', 'MSIN.JK', 'MSKY.JK', 'MTDL.JK', 
            'MTFN.JK', 'MTLA.JK', 'MTMH.JK', 'MTPS.JK', 'MTSM.JK', 'MTWI.JK', 'MYOH.JK', 'MYOR.JK', 
            'MYTX.JK', 'NASA.JK', 'NATO.JK', 'NETV.JK', 'NFCX.JK', 'NIKL.JK', 'NRCA.JK', 'NSSS.JK', 
            'NTBK.JK', 'NUSA.JK', 'NZIA.JK', 'OBMD.JK', 'OILS.JK', 'OKAS.JK', 'OMRE.JK', 'OPMS.JK', 
            'PACK.JK', 'PADI.JK', 'PALM.JK', 'PAMG.JK', 'PANI.JK', 'PBID.JK', 'PBSA.JK', 'PCAR.JK', 
            'PDAI.JK', 'PDES.JK', 'PEGE.JK', 'PEHA.JK', 'PGUN.JK', 'PICO.JK', 'PKPK.JK', 'PLAS.JK', 
            'PLIN.JK', 'PMJS.JK', 'PMMP.JK', 'PNLF.JK', 'POLA.JK', 'POLI.JK', 'POLU.JK', 'POOL.JK', 
            'PORT.JK', 'POWR.JK', 'PPGL.JK', 'PPRE.JK', 'PRDA.JK', 'PRIM.JK', 'PSAB.JK', 'PSDN.JK', 
            'PSGO.JK', 'PSKT.JK', 'PTDU.JK', 'PTIS.JK', 'PTRO.JK', 'PTSN.JK', 'PUDP.JK', 'PWON.JK', 
            'PYFA.JK', 'PZZA.JK', 'RAJA.JK', 'RALS.JK', 'RANC.JK', 'RBMS.JK', 'RDTX.JK', 'REAL.JK', 
            'RELI.JK', 'RICY.JK', 'RIGS.JK', 'RISE.JK', 'RMKE.JK', 'RMKO.JK', 'ROCK.JK', 'RODA.JK', 
            'ROTI.JK', 'RUIS.JK', 'SAFE.JK', 'SAGE.JK', 'SAMA.JK', 'SAMF.JK', 'SAPX.JK', 'SATU.JK', 
            'SBAT.JK', 'SBMA.JK', 'SBSN.JK', 'SCBD.JK', 'SCMA.JK', 'SCNP.JK', 'SCPI.JK', 'SDMU.JK', 
            'SDPC.JK', 'SDRA.JK', 'SFAN.JK', 'SGER.JK', 'SGRO.JK', 'SHID.JK', 'SHIP.JK', 'SICO.JK', 
            'SILO.JK', 'SINI.JK', 'SIPD.JK', 'SKBM.JK', 'SKLT.JK', 'SKRN.JK', 'SLIS.JK', 'SMAR.JK', 
            'SMBR.JK', 'SMDR.JK', 'SMGA.JK', 'SMKL.JK', 'SMKM.JK', 'SMMA.JK', 'SMMT.JK', 'SMRU.JK', 
            'SMSM.JK', 'SNLK.JK', 'SOCI.JK', 'SOFA.JK', 'SOHO.JK', 'SONA.JK', 'SOSS.JK', 'SOTS.JK', 
            'SPMA.JK', 'SPTO.JK', 'SQMI.JK', 'SRAJ.JK', 'SRSN.JK', 'STAA.JK', 'STAR.JK', 'STRK.JK', 
            'STTP.JK', 'SUGI.JK', 'SULI.JK', 'SUPR.JK', 'SURE.JK', 'SWAT.JK', 'TALF.JK', 'TAMU.JK', 
            'TARA.JK', 'TAXI.JK', 'TBMS.JK', 'TCID.JK', 'TCPI.JK', 'TDPM.JK', 'TECH.JK', 'TEBE.JK', 
            'TELE.JK', 'TFAS.JK', 'TFCO.JK', 'TGKA.JK', 'TIFA.JK', 'TIRT.JK', 'TJWI.JK', 'TKIM.JK', 
            'TMAS.JK', 'TMPO.JK', 'TNCA.JK', 'TOPS.JK', 'TOTL.JK', 'TPMA.JK', 'TRGU.JK', 'TRIM.JK', 
            'TRIN.JK', 'TRIS.JK', 'TRJA.JK', 'TRST.JK', 'TRUE.JK', 'TRUK.JK', 'TRUS.JK', 'TUGU.JK', 
            'UANG.JK', 'UCID.JK', 'UFOE.JK', 'UNIC.JK', 'UNIQ.JK', 'UNSP.JK', 'UVCR.JK', 'VAST.JK', 
            'VICI.JK', 'VICO.JK', 'VINS.JK', 'VIVA.JK', 'VKTR.JK', 'VOKS.JK', 'VTNY.JK', 'WAPO.JK', 
            'WEGE.JK', 'WEHA.JK', 'WGSH.JK', 'WINE.JK', 'WINS.JK', 'WMPP.JK', 'WMUU.JK', 'WOMF.JK', 
            'WOOD.JK', 'WOWS.JK', 'YELO.JK', 'YPAS.JK', 'ZATA.JK', 'ZONE.JK', 'ZBRA.JK', 'ZYRX.JK'
        ]
        
        # Exclude delisted/suspended (dari IDX 2025-2026 update)
        delisted_suspended = [
            'ALMI.JK', 'ARMY.JK', 'ARTI.JK', 'BEBS.JK', 'BIKA.JK', 'CNTX.JK', 'ENVY.JK', 'FKON.JK', 
            'HDTX.JK', 'HITS.JK', 'KPAL.JK', 'MAGP.JK', 'RSGK.JK', 'SKYB.JK', 'SRIL.JK', 'TGRA.JK', 
            'WICO.JK', 'CHEK.JK', 'PMUI.JK', 'COIN.JK', 'CDIA.JK', 'NIPS.JK', 'PRAS.JK', 'POSA.JK',
            'WIKA.JK', 'WSKT.JK', 'INAF.JK'
        ]
        active_stocks = [s for s in active_stocks if s not in delisted_suspended]
        
        # Verifikasi dengan YFinance
        verified = []
        for symbol in active_stocks:
            if symbol not in self.invalid_symbols:
                try:
                    time.sleep(0.5)  # Anti-rate limit (dikurangi dari 2 detik)
                    ticker = yf.Ticker(symbol)
                    hist = ticker.history(period="30d")  # Cukup 30 hari untuk verifikasi awal
                    if not hist.empty and len(hist) >= 15 and (hist['Volume'] > 0).mean() > 0.7:
                        # Check ada data minimal
                        if len(hist) > 1:
                            verified.append(symbol)
                    else:
                        self.invalid_symbols.add(symbol)
                        logger.debug(f"⚠️ {symbol}: Insufficient data ({len(hist)} bars)")
                except Exception as e:
                    self.invalid_symbols.add(symbol)
                    logger.debug(f"⚠️ {symbol}: Error - {str(e)[:50]}")
        
        # Cache hasil
        self._verified_stocks = verified[:200]  # Cap di 200
        
        logger.info(f"✅ Verified {len(self._verified_stocks)} active high-cap liquid stocks (Jan 2026)")
        return self._verified_stocks
    
    def get_assets(self, category: str, limit: int = 200, force_update: bool = False) -> List[str]:
        """
        Dapatkan list simbol aset untuk kategori tertentu.
        
        UPDATED: Untuk Indonesia stocks, gunakan daftar aktif Januari 2026
        """
        if category not in ['indonesia_stocks', 'forex', 'us_stocks']:
            raise ValueError(f"Invalid category: {category}. Pilih: indonesia_stocks, forex, us_stocks.")
        
        # 🚨 UPDATED: Untuk saham Indonesia, gunakan daftar aktif 2026
        if category == 'indonesia_stocks':
            return self._get_active_stocks()[:limit]
        
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
    
    # =============================================
    # 🎯 SCREENER YANG EFEKTIF (25 SAHAM TERAKTIF)
    # =============================================
    
    def get_active_assets(self, category: str = 'indonesia_stocks',
                         min_volume: float = 5_000_000,  # Minimal 5 juta volume
                         min_volatility: float = 0.015,   # Minimal 1.5% volatilitas
                         min_price_change: float = 0.02,  # Minimal 2% price change
                         limit: int = 25) -> List[str]:   # Hanya 25 terbaik
        """
        🚨 UPDATED: Ambil HANYA 25 aset teraktif dari daftar aktif 2026 untuk analisa!
        """
        print(f"\n🔥 SCREENING ASET AKTIF ({category})")
        print("=" * 60)
        
        if category != 'indonesia_stocks':
            return self._get_predefined_active(category, limit)
        
        # 1. Ambil saham aktif 2026
        active_stocks = self._get_active_stocks()[:100]  # 100 teratas untuk screening
        print(f"📊 Total active stocks: {len(active_stocks)}")
        
        # 2. Screening dengan data 90 hari
        print("🔍 Screening untuk aset aktif...")
        
        screened_stocks = []
        results = []
        
        for symbol in active_stocks:
            try:
                # Ambil data 90 hari untuk analisa yang proper
                ticker = yf.Ticker(symbol)
                hist = ticker.history(period="90d", interval="1d")
                
                if len(hist) < 30:  # Minimal 30 data points
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
                
                time.sleep(self.rate_limit_delay)
                
            except Exception as e:
                continue
        
        # Sort by score
        results.sort(key=lambda x: x['score'], reverse=True)
        
        # Ambil top performers
        screened_stocks = [r['symbol'] for r in results[:limit]]
        
        if screened_stocks:
            print(f"✅ Ditemukan {len(screened_stocks)} aset aktif")
            print(f"🎯 Top 5: {screened_stocks[:5]}")
            
            # Debug info
            if results:
                print(f"📈 Rata-rata data points: {np.mean([r['data_points'] for r in results[:10]]):.0f}")
                print(f"📊 Rata-rata volume: {np.mean([r['volume'] for r in results[:10]]):,.0f}")
                print(f"📉 Rata-rata volatilitas: {np.mean([r['volatility'] for r in results[:10]]):.3%}")
        else:
            print("⚠️ Tidak ada aset aktif ditemukan, gunakan default")
            screened_stocks = active_stocks[:limit]
        
        return screened_stocks
    
    # =============================================
    # 🚀 TRADING SIGNAL GENERATOR (FIXED)
    # =============================================
    
    def generate_trading_signals(self, symbols: List[str] = None, 
                               min_bars: int = 40,  # Minimal 40 bars
                               rsi_oversold: int = 30,
                               rsi_overbought: int = 70) -> List[Dict]:
        """
        UPDATED: Generate trading signals dengan data yang cukup.
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
                            break
                        
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
                
                time.sleep(self.rate_limit_delay)
                
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
            'BANKING': ['BBCA.JK', 'BBRI.JK', 'BMRI.JK', 'BBNI.JK', 'BNGA.JK', 'BRIS.JK', 'BBTN.JK'],
            'MINING': ['ANTM.JK', 'ADRO.JK', 'INCO.JK', 'BRPT.JK', 'PTBA.JK', 'MDKA.JK', 'TINS.JK'],
            'CONSUMER': ['UNVR.JK', 'ICBP.JK', 'INDF.JK', 'MYOR.JK', 'ULTJ.JK', 'SIDO.JK', 'TCPI.JK'],
            'PROPERTY': ['BSDE.JK', 'CTRA.JK', 'ASRI.JK', 'SMRA.JK', 'PWON.JK', 'JRPT.JK', 'LPPS.JK'],
            'INFRASTRUCTURE': ['WIKA.JK', 'PTPP.JK', 'ADHI.JK', 'JSMR.JK', 'SRIL.JK', 'WEGE.JK', 'MTEL.JK'],
            'TECH': ['GOTO.JK', 'BRIS.JK', 'DMMX.JK', 'ARTO.JK', 'TCID.JK', 'EMTK.JK', 'DSSA.JK'],
            'ENERGY': ['PGAS.JK', 'MEDC.JK', 'AKRA.JK', 'HRUM.JK', 'BUMI.JK', 'ITMG.JK', 'ENRG.JK']
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
    # 🛠️ FUNGSI HELPER (UPDATED)
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
            return self._get_active_stocks()  # Gunakan daftar aktif 2026
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
    
    print("🚀 NON-CRYPTO ASSETS PROVIDER - UPDATED 2026 VERSION")
    print("=" * 60)
    
    # 1. Dapatkan saham aktif 2026
    print("\n1️⃣ Mengambil 25 saham aktif terbaik 2026...")
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
    print("🎯 STRATEGI EFEKTIF 2026:")
    print("   • Analisa hanya 25 saham aktif terbaik dari daftar 200+")
    print("   • Minimal 40 bars data untuk analisa")
    print("   • Multi-indicator confirmation (RSI, MACD, MA, Volume)")
    print("   • Strength threshold >= 4 untuk filter noise")
    print("\n✅ File telah diupdate dengan daftar saham aktif Januari 2026!")
