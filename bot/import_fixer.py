# bot/import_fixer.py
"""
Import fixer berdasarkan struktur aktual repo
"""

import sys
import importlib.util
from pathlib import Path

def import_forex_scraper_fixed():
    """Import ForexScraper berdasarkan struktur sebenarnya"""
    repo_path = Path("bot/external_repos/ForexScraper")
    
    # Coba berbagai kemungkinan
    possibilities = [
        ("scraper.py", "ForexGeneralScraper"),
        ("forex_scraper.py", "ForexScraper"),
        ("main.py", "ForexScraper"),
        ("__init__.py", "ForexScraper"),
        ("ForexScraper.py", "ForexScraper")
    ]
    
    for file_name, class_name in possibilities:
        file_path = repo_path / file_name
        if file_path.exists():
            try:
                spec = importlib.util.spec_from_file_location(
                    f"forex_scraper_{file_name}",
                    file_path
                )
                module = importlib.util.module_from_spec(spec)
                sys.modules[f"forex_scraper_{file_name}"] = module
                spec.loader.exec_module(module)
                
                # Cari class
                if hasattr(module, class_name):
                    return getattr(module, class_name)
                else:
                    # Cari class apapun yang ada
                    for attr_name in dir(module):
                        attr = getattr(module, attr_name)
                        if isinstance(attr, type) and 'forex' in attr_name.lower():
                            print(f"⚠️  Using {attr_name} instead of {class_name}")
                            return attr
            except Exception as e:
                print(f"⚠️  Failed to load {file_name}: {e}")
    
    # Jika semua gagal, buat mock
    print("⚠️  Creating mock ForexScraper")
    class MockForexScraper:
        def fetch_pairs(self, limit=20):
            return ['EURUSD', 'USDJPY', 'GBPUSD', 'AUDUSD']
    
    return MockForexScraper

def import_indonesia_stocks_scraper_fixed():
    """Import Indonesia stocks scraper"""
    repo_path = Path("bot/external_repos/indonesia_stocks_scraper")
    
    possibilities = [
        ("scraper.py", "IndonesiaStocksScraper"),
        ("idx_scraper.py", "IDXScraper"),
        ("main.py", "IndonesiaStocksScraper"),
        ("stock_scraper.py", "StockScraper")
    ]
    
    for file_name, class_name in possibilities:
        file_path = repo_path / file_name
        if file_path.exists():
            try:
                spec = importlib.util.spec_from_file_location(
                    f"indo_scraper_{file_name}",
                    file_path
                )
                module = importlib.util.module_from_spec(spec)
                sys.modules[f"indo_scraper_{file_name}"] = module
                spec.loader.exec_module(module)
                
                if hasattr(module, class_name):
                    return getattr(module, class_name)
            except:
                continue
    
    # Mock
    class MockIndonesiaStocksScraper:
        def fetch_stocks(self):
            return ['BBCA', 'BBRI', 'BMRI', 'TLKM']
    
    return MockIndonesiaStocksScraper

# ... buat fungsi serupa untuk scraper lain
