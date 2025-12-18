"""
MARKET ASSETS MANAGER
File terpusat untuk manage list saham Indonesia, US, Forex, dan Crypto
Auto-update dengan data aktual dari berbagai sumber
"""
import json
import pandas as pd
import yfinance as yf
import requests
from datetime import datetime, timedelta
import logging
from typing import Dict, List, Optional, Any
import time
import os

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MarketAssetsManager:
    """Manager terpusat untuk semua market assets"""
    
    def __init__(self, cache_dir: str = "market_data", auto_update: bool = True):
        self.cache_dir = cache_dir
        self.auto_update = auto_update
        
        # Buat directory jika belum ada
        os.makedirs(cache_dir, exist_ok=True)
        
        # File paths
        self.id_stocks_file = f"{cache_dir}/id_stocks.json"
        self.us_stocks_file = f"{cache_dir}/us_stocks.json"
        self.forex_pairs_file = f"{cache_dir}/forex_pairs.json"
        self.crypto_symbols_file = f"{cache_dir}/crypto_symbols.json"
        self.combined_file = f"{cache_dir}/all_markets.json"
        
        # Inisialisasi dengan data default
        self._init_default_lists()
        
        # Auto update jika perlu
        if auto_update:
            self.check_and_update()
    
    def _init_default_lists(self):
        """Initialize dengan default lists jika file tidak ada"""
        
        # SAHAM INDONESIA (LQ45 + Blue Chips)
        self.DEFAULT_ID_STOCKS = [
            # Bank & Financial
            "BBCA.JK", "BBRI.JK", "BMRI.JK", "BBNI.JK", "BNGA.JK",
            # Blue Chips
            "TLKM.JK", "ASII.JK", "UNVR.JK", "ICBP.JK", "INDF.JK",
            # Energy & Mining
            "ANTM.JK", "ADRO.JK", "PTBA.JK", "ITMG.JK", "MEDC.JK",
            # Consumer
            "GGRM.JK", "HMSP.JK", "ROTI.JK", "MYOR.JK", "MLBI.JK",
            # Property
            "BSDE.JK", "CTRA.JK", "PWON.JK", "DMAS.JK", "LPLI.JK",
            # Infrastructure
            "WIKA.JK", "PTPP.JK", "WEGE.JK", "SSMS.JK", "AKRA.JK",
            # Healthcare
            "KLBF.JK", "SILO.JK", "DVLA.JK", "PYFA.JK", "TSPC.JK",
            # Technology
            "GOTO.JK", "ARTO.JK", "DMMX.JK", "MTDL.JK", "EDGE.JK",
            # Plantation
            "LSIP.JK", "SIMP.JK", "TBLA.JK", "SGRO.JK", "JAWA.JK"
        ]
        
        # SAHAM US (S&P 500 Top 100)
        self.DEFAULT_US_STOCKS = [
            # Tech Giants
            "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA",
            # Semiconductors
            "AVGO", "AMD", "QCOM", "INTC", "TXN", "MU", "AMAT",
            # Financial
            "JPM", "BAC", "WFC", "GS", "MS", "C", "SCHW",
            # Healthcare
            "JNJ", "UNH", "PFE", "ABT", "MRK", "TMO", "LLY",
            # Consumer
            "PG", "KO", "PEP", "WMT", "COST", "TGT", "HD",
            # Industrial
            "BA", "CAT", "HON", "MMM", "GE", "RTX", "LMT",
            # Energy
            "XOM", "CVX", "COP", "SLB", "EOG", "PSX", "MPC",
            # Communication
            "VZ", "T", "CMCSA", "DIS", "NFLX", "TMUS", "CHTR",
            # Real Estate
            "AMT", "PLD", "CCI", "EQIX", "PSA", "SPG", "DLR"
        ]
        
        # FOREX PAIRS (Major + Cross + Exotic)
        self.DEFAULT_FOREX_PAIRS = [
            # Majors
            "EURUSD=X", "USDJPY=X", "GBPUSD=X", "USDCHF=X",
            "AUDUSD=X", "USDCAD=X", "NZDUSD=X",
            # European Crosses
            "EURGBP=X", "EURCHF=X", "EURNZD=X", "EURCAD=X",
            "EURAUD=X", "GBPJPY=X", "GBPCHF=X",
            # Asian
            "USDKRW=X", "USDSGD=X", "USDHKD=X", "USDINR=X",
            "USDCNY=X", "USDMYR=X", "USDTHB=X", "USDPHP=X",
            # Commodity
            "AUDJPY=X", "CADJPY=X", "NZDJPY=X", "CHFJPY=X"
        ]
        
        # CRYPTO (Major + Top Alts)
        self.DEFAULT_CRYPTO_SYMBOLS = [
            # Bitcoin & Ethereum
            "BTC-USD", "ETH-USD",
            # Top 10
            "BNB-USD", "SOL-USD", "XRP-USD", "ADA-USD", "AVAX-USD",
            "DOGE-USD", "DOT-USD", "TRX-USD", "MATIC-USD",
            # DeFi
            "LINK-USD", "UNI-USD", "AAVE-USD", "MKR-USD", "COMP-USD",
            # Layer 2
            "ARB-USD", "OP-USD", "IMX-USD", "STRK-USD",
            # AI & Meme
            "TAO-USD", "RNDR-USD", "WLD-USD", "SHIB-USD", "PEPE-USD"
        ]
    
    def save_to_file(self, data: Dict, filepath: str):
        """Save data ke JSON file"""
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.info(f"✅ Data saved to {filepath}")
        except Exception as e:
            logger.error(f"❌ Failed to save {filepath}: {e}")
    
    def load_from_file(self, filepath: str, default_data: List = None) -> Dict:
        """Load data dari JSON file"""
        try:
            if os.path.exists(filepath):
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Check if data is stale (older than 7 days)
                if 'last_updated' in data:
                    last_updated = datetime.fromisoformat(data['last_updated'])
                    if datetime.now() - last_updated < timedelta(days=7):
                        logger.info(f"📦 Using cached data from {filepath}")
                        return data
                
            # Return default if file doesn't exist or data is stale
            if default_data:
                return {
                    'symbols': default_data,
                    'last_updated': datetime.now().isoformat(),
                    'source': 'default'
                }
            return {}
                
        except Exception as e:
            logger.warning(f"⚠️ Failed to load {filepath}: {e}")
            if default_data:
                return {
                    'symbols': default_data,
                    'last_updated': datetime.now().isoformat(),
                    'source': 'default'
                }
            return {}
    
    def check_and_update(self):
        """Check if data needs update and update if necessary"""
        logger.info("🔄 Checking if market data needs update...")
        
        # Check each file
        files_to_update = []
        
        for filepath, default in [
            (self.id_stocks_file, self.DEFAULT_ID_STOCKS),
            (self.us_stocks_file, self.DEFAULT_US_STOCKS),
            (self.forex_pairs_file, self.DEFAULT_FOREX_PAIRS),
            (self.crypto_symbols_file, self.DEFAULT_CRYPTO_SYMBOLS)
        ]:
            if not os.path.exists(filepath):
                files_to_update.append((filepath, default))
            else:
                data = self.load_from_file(filepath, default)
                if 'last_updated' in data:
                    last_updated = datetime.fromisoformat(data['last_updated'])
                    if datetime.now() - last_updated > timedelta(days=7):
                        files_to_update.append((filepath, default))
        
        if files_to_update:
            logger.info(f"📊 Updating {len(files_to_update)} market lists...")
            self.update_all_markets()
        else:
            logger.info("✅ All market data is up to date")
    
    def update_all_markets(self):
        """Update semua market lists sekaligus"""
        logger.info("🚀 Starting comprehensive market data update...")
        
        results = {
            'indonesian_stocks': self.update_id_stocks(),
            'us_stocks': self.update_us_stocks(),
            'forex_pairs': self.update_forex_pairs(),
            'crypto_symbols': self.update_crypto_symbols(),
            'combined': {},
            'last_updated': datetime.now().isoformat(),
            'update_source': 'auto_update'
        }
        
        # Buat combined list untuk kemudahan akses
        results['combined'] = {
            'all_symbols': results['indonesian_stocks']['symbols'] + 
                          results['us_stocks']['symbols'] + 
                          results['forex_pairs']['symbols'] + 
                          results['crypto_symbols']['symbols'],
            'counts': {
                'indonesian_stocks': len(results['indonesian_stocks']['symbols']),
                'us_stocks': len(results['us_stocks']['symbols']),
                'forex_pairs': len(results['forex_pairs']['symbols']),
                'crypto_symbols': len(results['crypto_symbols']['symbols'])
            }
        }
        
        # Save individual files
        self.save_to_file(results['indonesian_stocks'], self.id_stocks_file)
        self.save_to_file(results['us_stocks'], self.us_stocks_file)
        self.save_to_file(results['forex_pairs'], self.forex_pairs_file)
        self.save_to_file(results['crypto_symbols'], self.crypto_symbols_file)
        self.save_to_file(results, self.combined_file)
        
        logger.info("✅ All market data updated successfully!")
        return results
    
    def update_id_stocks(self) -> Dict:
        """Update list saham Indonesia dengan volume filtering"""
        logger.info("📈 Updating Indonesian stocks list...")
        
        # List semua saham Indonesia yang mungkin
        all_id_symbols = self.DEFAULT_ID_STOCKS + [
            "AKRA.JK", "APLN.JK", "ASSA.JK", "BTPN.JK", "DOID.JK",
            "ELSA.JK", "EXCL.JK", "FREN.JK", "GJTL.JK", "HEXA.JK",
            "IFII.JK", "INKP.JK", "JSMR.JK", "KIJA.JK", "LPGI.JK",
            "MBAP.JK", "MNCN.JK", "PGAS.JK", "PSSI.JK", "SMCB.JK",
            "SRIL.JK", "TINS.JK", "TKIM.JK", "TPIA.JK", "ULTJ.JK",
            "WSBP.JK", "WTON.JK"
        ]
        
        valid_stocks = []
        volume_data = []
        
        for symbol in all_id_symbols:
            try:
                # Rate limiting
                time.sleep(0.1)
                
                ticker = yf.Ticker(symbol)
                hist = ticker.history(period="1mo")
                
                if hist.empty:
                    continue
                
                # Filter berdasarkan volume
                avg_volume = hist['Volume'].mean()
                if avg_volume > 100000:  # Minimal 100k volume rata-rata
                    valid_stocks.append(symbol)
                    
                    volume_data.append({
                        'symbol': symbol,
                        'avg_volume': int(avg_volume),
                        'last_price': float(hist['Close'].iloc[-1]) if len(hist) > 0 else 0,
                        'last_volume': int(hist['Volume'].iloc[-1]) if len(hist) > 0 else 0
                    })
                    
                    logger.debug(f"  ✅ {symbol}: {avg_volume:,.0f} volume")
                else:
                    logger.debug(f"  ❌ {symbol}: Low volume ({avg_volume:,.0f})")
                    
            except Exception as e:
                logger.debug(f"  ⚠️ {symbol}: Error - {e}")
                continue
        
        # Sort by volume (highest first)
        volume_data.sort(key=lambda x: x['avg_volume'], reverse=True)
        valid_stocks = [item['symbol'] for item in volume_data[:100]]  # Ambil top 100
        
        result = {
            'symbols': valid_stocks,
            'volume_ranked': volume_data[:50],  # Top 50 by volume
            'last_updated': datetime.now().isoformat(),
            'source': 'yfinance_filtered',
            'total_scanned': len(all_id_symbols),
            'total_passed': len(valid_stocks)
        }
        
        logger.info(f"✅ ID stocks updated: {len(valid_stocks)} stocks (filtered by volume)")
        return result
    
    def update_us_stocks(self) -> Dict:
        """Update list saham US dengan filtering"""
        logger.info("📈 Updating US stocks list...")
        
        # Load S&P 500 symbols (static untuk sekarang)
        sp500_symbols = self.DEFAULT_US_STOCKS
        
        valid_stocks = []
        market_cap_data = []
        
        for symbol in sp500_symbols[:150]:  # Cek 150 pertama
            try:
                time.sleep(0.05)  # Rate limit
                
                ticker = yf.Ticker(symbol)
                info = ticker.info
                
                if not info:
                    continue
                
                market_cap = info.get('marketCap', 0)
                
                # Filter: market cap > $10B
                if market_cap > 10_000_000_000:
                    valid_stocks.append(symbol)
                    
                    market_cap_data.append({
                        'symbol': symbol,
                        'market_cap': market_cap,
                        'name': info.get('longName', symbol),
                        'sector': info.get('sector', 'Unknown'),
                        'volume': info.get('volume', 0)
                    })
                    
            except Exception as e:
                logger.debug(f"  ⚠️ {symbol}: Error - {e}")
                continue
        
        # Sort by market cap
        market_cap_data.sort(key=lambda x: x['market_cap'], reverse=True)
        valid_stocks = [item['symbol'] for item in market_cap_data[:100]]
        
        result = {
            'symbols': valid_stocks,
            'market_cap_ranked': market_cap_data[:50],
            'last_updated': datetime.now().isoformat(),
            'source': 'yfinance_sp500',
            'total_scanned': len(sp500_symbols[:150]),
            'total_passed': len(valid_stocks)
        }
        
        logger.info(f"✅ US stocks updated: {len(valid_stocks)} stocks")
        return result
    
    def update_forex_pairs(self) -> Dict:
        """Update list forex pairs"""
        logger.info("📈 Updating Forex pairs list...")
        
        # Forex pairs relatif stabil, pakai default + beberapa tambahan
        all_forex = self.DEFAULT_FOREX_PAIRS + [
            # Emerging markets
            "USDZAR=X", "USDBRL=X", "USDMXN=X", "USDTRY=X", "USDRUB=X",
            # European minors
            "EURSEK=X", "EURNOK=X", "EURDKK=X", "EURPLN=X", "EURHUF=X",
            # Asia minor
            "USDTWD=X", "USDIDR=X", "USDVND=X"
        ]
        
        # Coba cek volume/availability
        valid_pairs = []
        
        for pair in all_forex[:30]:  # Cek 30 pairs pertama
            try:
                time.sleep(0.1)
                
                # Convert untuk YFinance (sudah format benar)
                ticker = yf.Ticker(pair)
                hist = ticker.history(period="5d")
                
                if not hist.empty and len(hist) > 0:
                    valid_pairs.append(pair)
                    logger.debug(f"  ✅ {pair}: Available")
                else:
                    logger.debug(f"  ⚠️ {pair}: No data")
                    
            except Exception as e:
                logger.debug(f"  ❌ {pair}: Error - {e}")
                continue
        
        result = {
            'symbols': valid_pairs,
            'last_updated': datetime.now().isoformat(),
            'source': 'yfinance_forex',
            'categories': {
                'majors': [p for p in valid_pairs if any(x in p for x in ['EUR', 'USD', 'JPY', 'GBP', 'CHF'])],
                'crosses': [p for p in valid_pairs if '=X' in p and p.count('USD') == 0],
                'exotics': [p for p in valid_pairs if any(x in p for x in ['KRW', 'SGD', 'HKD', 'INR', 'MYR'])]
            }
        }
        
        logger.info(f"✅ Forex pairs updated: {len(valid_pairs)} pairs")
        return result
    
    def update_crypto_symbols(self) -> Dict:
        """Update list crypto symbols"""
        logger.info("📈 Updating Crypto symbols list...")
        
        # Crypto dari YFinance
        crypto_symbols = self.DEFAULT_CRYPTO_SYMBOLS
        
        valid_crypto = []
        crypto_data = []
        
        for symbol in crypto_symbols:
            try:
                time.sleep(0.1)
                
                ticker = yf.Ticker(symbol)
                hist = ticker.history(period="5d")
                
                if not hist.empty and len(hist) > 0:
                    avg_volume = hist['Volume'].mean()
                    
                    if avg_volume > 1000:  # Minimal volume
                        valid_crypto.append(symbol)
                        
                        crypto_data.append({
                            'symbol': symbol,
                            'name': symbol.replace('-USD', ''),
                            'avg_volume': float(avg_volume),
                            'last_price': float(hist['Close'].iloc[-1]),
                            'price_change': float(hist['Close'].pct_change().iloc[-1] * 100) if len(hist) > 1 else 0
                        })
                        
                        logger.debug(f"  ✅ {symbol}: ${hist['Close'].iloc[-1]:.2f}")
                    else:
                        logger.debug(f"  ⚠️ {symbol}: Low volume")
                else:
                    logger.debug(f"  ❌ {symbol}: No data")
                    
            except Exception as e:
                logger.debug(f"  ❌ {symbol}: Error - {e}")
                continue
        
        result = {
            'symbols': valid_crypto,
            'crypto_data': crypto_data,
            'last_updated': datetime.now().isoformat(),
            'source': 'yfinance_crypto',
            'total_scanned': len(crypto_symbols),
            'total_passed': len(valid_crypto)
        }
        
        logger.info(f"✅ Crypto symbols updated: {len(valid_crypto)} symbols")
        return result
    
    def get_market_data(self, market_type: str = None) -> Dict:
        """Get market data by type or all"""
        if market_type == 'indonesian_stocks':
            return self.load_from_file(self.id_stocks_file, self.DEFAULT_ID_STOCKS)
        elif market_type == 'us_stocks':
            return self.load_from_file(self.us_stocks_file, self.DEFAULT_US_STOCKS)
        elif market_type == 'forex_pairs':
            return self.load_from_file(self.forex_pairs_file, self.DEFAULT_FOREX_PAIRS)
        elif market_type == 'crypto_symbols':
            return self.load_from_file(self.crypto_symbols_file, self.DEFAULT_CRYPTO_SYMBOLS)
        else:
            # Return all combined
            if os.path.exists(self.combined_file):
                return self.load_from_file(self.combined_file, {})
            else:
                # Generate combined data
                return {
                    'indonesian_stocks': self.load_from_file(self.id_stocks_file, self.DEFAULT_ID_STOCKS),
                    'us_stocks': self.load_from_file(self.us_stocks_file, self.DEFAULT_US_STOCKS),
                    'forex_pairs': self.load_from_file(self.forex_pairs_file, self.DEFAULT_FOREX_PAIRS),
                    'crypto_symbols': self.load_from_file(self.crypto_symbols_file, self.DEFAULT_CRYPTO_SYMBOLS),
                    'last_updated': datetime.now().isoformat(),
                    'source': 'combined'
                }
    
    def get_symbols(self, market_type: str, limit: int = None) -> List[str]:
        """Get symbols list untuk market tertentu"""
        data = self.get_market_data(market_type)
        symbols = data.get('symbols', [])
        
        if limit and len(symbols) > limit:
            return symbols[:limit]
        return symbols
    
    def get_all_symbols(self, limit_per_type: int = 50) -> List[str]:
        """Get semua symbols dari semua market types"""
        all_symbols = []
        
        for market_type in ['indonesian_stocks', 'us_stocks', 'forex_pairs', 'crypto_symbols']:
            symbols = self.get_symbols(market_type, limit_per_type)
            all_symbols.extend(symbols)
        
        return all_symbols
    
    def get_statistics(self) -> Dict:
        """Get statistics about market data"""
        stats = {}
        
        for market_type, filepath in [
            ('indonesian_stocks', self.id_stocks_file),
            ('us_stocks', self.us_stocks_file),
            ('forex_pairs', self.forex_pairs_file),
            ('crypto_symbols', self.crypto_symbols_file)
        ]:
            data = self.load_from_file(filepath, [])
            stats[market_type] = {
                'count': len(data.get('symbols', [])),
                'last_updated': data.get('last_updated', 'Never'),
                'source': data.get('source', 'unknown')
            }
        
        return stats

# Singleton instance untuk kemudahan akses
market_manager = MarketAssetsManager(auto_update=True)

# Helper functions untuk quick access
def get_id_stocks(limit: int = None) -> List[str]:
    """Get Indonesian stocks"""
    return market_manager.get_symbols('indonesian_stocks', limit)

def get_us_stocks(limit: int = None) -> List[str]:
    """Get US stocks"""
    return market_manager.get_symbols('us_stocks', limit)

def get_forex_pairs(limit: int = None) -> List[str]:
    """Get Forex pairs"""
    return market_manager.get_symbols('forex_pairs', limit)

def get_crypto_symbols(limit: int = None) -> List[str]:
    """Get Crypto symbols"""
    return market_manager.get_symbols('crypto_symbols', limit)

def get_all_markets(limit_per_type: int = 25) -> List[str]:
    """Get semua markets"""
    return market_manager.get_all_symbols(limit_per_type)
