# bot/direct_imports.py
"""
DIRECT IMPORTS BERDASARKAN STRUKTUR AKTUAL YANG ADA
"""

import sys
import os
import importlib.util
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class DirectImporter:
    """Importer berdasarkan struktur aktual repo"""
    
    def __init__(self):
        self.base_path = Path("bot/external_repos")
        self.import_cache = {}
    
    def import_forex_scraper(self):
        """Import ForexScraper dari folder forex/"""
        repo_path = self.base_path / "ForexScraper"
        
        # Coba cari di folder forex/
        forex_folder = repo_path / "forex"
        if forex_folder.exists() and forex_folder.is_dir():
            # Cari file Python di dalam folder forex/
            py_files = list(forex_folder.rglob("*.py"))
            for py_file in py_files:
                if py_file.name.endswith('.py') and not py_file.name.startswith('__'):
                    try:
                        return self._import_file(py_file, "ForexScraper")
                    except:
                        continue
        
        # Jika tidak ditemukan, buat mock
        logger.warning("⚠️  ForexScraper not found, using mock")
        return self._create_mock_forex_scraper()
    
    def import_binance_scraper(self):
        """Import dari Crypto_History_Scraper_BinanceApi/main.py"""
        repo_path = self.base_path / "Crypto_History_Scraper_BinanceApi"
        main_file = repo_path / "main.py"
        
        if main_file.exists():
            try:
                # Import dari main.py
                spec = importlib.util.spec_from_file_location(
                    "binance_scraper_main",
                    main_file
                )
                module = importlib.util.module_from_spec(spec)
                sys.modules["binance_scraper_main"] = module
                spec.loader.exec_module(module)
                
                # Cari class BinanceScraper di module
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if isinstance(attr, type):
                        if 'Binance' in attr_name or 'Scraper' in attr_name:
                            logger.info(f"✅ Found {attr_name} in main.py")
                            return attr
                
                # Jika tidak ada class, buat wrapper
                logger.info("✅ Using module as scraper")
                return module
                
            except Exception as e:
                logger.error(f"❌ Failed to import Binance scraper: {e}")
        
        return self._create_mock_binance_scraper()
    
    def import_indonesia_stocks_scraper(self):
        """Import dari indonesia_stocks_scraper/app.py"""
        repo_path = self.base_path / "indonesia_stocks_scraper"
        app_file = repo_path / "app.py"
        
        if app_file.exists():
            try:
                spec = importlib.util.spec_from_file_location(
                    "indonesia_stocks_app",
                    app_file
                )
                module = importlib.util.module_from_spec(spec)
                sys.modules["indonesia_stocks_app"] = module
                spec.loader.exec_module(module)
                
                # Cari scraper class
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if isinstance(attr, type):
                        if 'Indonesia' in attr_name or 'Scraper' in attr_name:
                            logger.info(f"✅ Found {attr_name} in app.py")
                            return attr
                
                return module
                
            except Exception as e:
                logger.error(f"❌ Failed to import Indonesia stocks scraper: {e}")
        
        return self._create_mock_indonesia_scraper()
    
    def import_investing_scraper(self):
        """Import dari Investing_com_Scraper/GoldScrape.py"""
        repo_path = self.base_path / "Investing_com_Scraper"
        gold_file = repo_path / "GoldScrape.py"
        
        if gold_file.exists():
            try:
                spec = importlib.util.spec_from_file_location(
                    "investing_gold_scrape",
                    gold_file
                )
                module = importlib.util.module_from_spec(spec)
                sys.modules["investing_gold_scrape"] = module
                spec.loader.exec_module(module)
                
                # Cari class
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if isinstance(attr, type):
                        if 'Gold' in attr_name or 'Scraper' in attr_name:
                            logger.info(f"✅ Found {attr_name} in GoldScrape.py")
                            return attr
                
                # Coba file lain
                for py_file in repo_path.glob("*.py"):
                    if py_file.name != 'GoldScrape.py':
                        try:
                            return self._import_file(py_file, "InvestingScraper")
                        except:
                            continue
                
                return module
                
            except Exception as e:
                logger.error(f"❌ Failed to import Investing scraper: {e}")
        
        return self._create_mock_investing_scraper()
    
    def _import_file(self, file_path, scraper_type):
        """Import generic dari file"""
        try:
            module_name = f"{scraper_type}_{file_path.stem}"
            spec = importlib.util.spec_from_file_location(module_name, file_path)
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
            return module
        except Exception as e:
            logger.error(f"❌ Failed to import {file_path}: {e}")
            return None
    
    # MOCK CREATORS
    def _create_mock_forex_scraper(self):
        class MockForexScraper:
            def fetch_pairs(self, limit=20):
                return ['EURUSD', 'USDJPY', 'GBPUSD', 'AUDUSD']
            
            def get_data(self, pair, timeframe='1h'):
                import yfinance as yf
                try:
                    ticker = yf.Ticker(f"{pair}=X")
                    df = ticker.history(period='1mo', interval='1h')
                    return df
                except:
                    return None
        return MockForexScraper
    
    def _create_mock_binance_scraper(self):
        class MockBinanceScraper:
            def fetch_historical(self, symbol, interval='1h', limit=100):
                import yfinance as yf
                try:
                    ticker = yf.Ticker(symbol.replace('/USDT', '-USD'))
                    df = ticker.history(period='1mo', interval='1h')
                    return df.tail(limit).to_dict('records')
                except:
                    return []
        return MockBinanceScraper
    
    def _create_mock_indonesia_scraper(self):
        class MockIndonesiaStocksScraper:
            def fetch_stocks(self):
                return ['BBCA', 'BBRI', 'BMRI', 'TLKM', 'ASII']
            
            def get_stock_data(self, stock_code, period='1y'):
                import yfinance as yf
                try:
                    ticker = yf.Ticker(f"{stock_code}.JK")
                    df = ticker.history(period=period)
                    return df.to_dict('records')
                except:
                    return None
        return MockIndonesiaStocksScraper
    
    def _create_mock_investing_scraper(self):
        class MockInvestingScraper:
            def fetch_indonesia_stocks(self):
                return ['BBCA', 'BBRI', 'BMRI', 'TLKM']
            
            def fetch_forex(self):
                return ['EURUSD', 'USDJPY', 'GBPUSD']
            
            def fetch_us_stocks(self):
                return ['AAPL', 'MSFT', 'GOOGL']
        return MockInvestingScraper

# Singleton instance
_importer = DirectImporter()

# Public API
def get_forex_scraper():
    return _importer.import_forex_scraper()

def get_binance_scraper():
    return _importer.import_binance_scraper()

def get_indonesia_stocks_scraper():
    return _importer.import_indonesia_stocks_scraper()

def get_investing_scraper():
    return _importer.import_investing_scraper()

# Test function
def test_all():
    print("\n" + "="*60)
    print("🧪 TESTING DIRECT IMPORTS")
    print("="*60)
    
    results = {}
    
    print("\n1. Testing ForexScraper...")
    ForexScraper = get_forex_scraper()
    results['Forex'] = '✅ OK' if ForexScraper else '❌ Failed'
    print(f"   Result: {results['Forex']}")
    
    print("\n2. Testing BinanceScraper...")
    BinanceScraper = get_binance_scraper()
    results['Binance'] = '✅ OK' if BinanceScraper else '❌ Failed'
    print(f"   Result: {results['Binance']}")
    
    print("\n3. Testing IndonesiaStocksScraper...")
    IndonesiaStocksScraper = get_indonesia_stocks_scraper()
    results['Indonesia'] = '✅ OK' if IndonesiaStocksScraper else '❌ Failed'
    print(f"   Result: {results['Indonesia']}")
    
    print("\n4. Testing InvestingScraper...")
    InvestingScraper = get_investing_scraper()
    results['Investing'] = '✅ OK' if InvestingScraper else '❌ Failed'
    print(f"   Result: {results['Investing']}")
    
    print("\n" + "="*60)
    print("📊 SUMMARY:")
    for name, status in results.items():
        print(f"  {name}: {status}")
    
    return results

if __name__ == "__main__":
    # Jalankan sebagai script standalone
    import logging
    logging.basicConfig(level=logging.INFO)
    test_all()
else:
    # Ketika di-import sebagai module
    pass
