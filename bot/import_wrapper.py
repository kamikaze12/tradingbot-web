# File: import_wrapper.py
"""
Wrapper untuk import dari external repos dengan struktur yang berbeda
"""

import importlib.util
import sys
import os
from pathlib import Path

class ExternalRepoImporter:
    """Import module dari external repos dengan berbagai struktur"""
    
    def __init__(self):
        self.base_path = Path("bot/external_repos")
        self.modules_cache = {}
    
    def find_main_file(self, repo_name, patterns=None):
        """Cari file utama di repo"""
        if patterns is None:
            patterns = ["scraper.py", "main.py", "tracker.py", "analyzer.py", "strategy.py"]
        
        repo_path = self.base_path / repo_name
        if not repo_path.exists():
            return None
        
        for pattern in patterns:
            for py_file in repo_path.rglob(pattern):
                return py_file
        
        # Jika tidak ditemukan, cari file .py pertama
        py_files = list(repo_path.rglob("*.py"))
        if py_files:
            return py_files[0]
        
        return None
    
    def import_from_repo(self, repo_name, class_name=None):
        """Import dari repo dengan nama tertentu"""
        if repo_name in self.modules_cache:
            module = self.modules_cache[repo_name]
            if class_name:
                return getattr(module, class_name)
            return module
        
        main_file = self.find_main_file(repo_name)
        if not main_file:
            print(f"❌ No Python files found in {repo_name}")
            return None
        
        try:
            # Buat module name
            module_name = f"bot.external_repos.{repo_name}"
            
            # Load module
            spec = importlib.util.spec_from_file_location(
                module_name,
                main_file
            )
            module = importlib.util.module_from_spec(spec)
            
            # Eksekusi module
            spec.loader.exec_module(module)
            
            # Cache
            self.modules_cache[repo_name] = module
            
            # Cari class jika diminta
            if class_name:
                # Cari class di module
                if hasattr(module, class_name):
                    return getattr(module, class_name)
                else:
                    # Cari class yang cocok
                    for attr_name in dir(module):
                        attr = getattr(module, attr_name)
                        if (isinstance(attr, type) and 
                            (class_name.lower() in attr_name.lower() or 
                             class_name.lower() in str(attr).lower())):
                            return attr
            
            return module
            
        except Exception as e:
            print(f"❌ Error importing {repo_name}: {e}")
            import traceback
            traceback.print_exc()
            return None

# Singleton instance
importer = ExternalRepoImporter()

# Import functions
def import_indonesia_stocks_scraper():
    """Import Indonesia stocks scraper"""
    return importer.import_from_repo("Indonesia_stocks_scraper", "IndonesiaStocksScraper")

def import_binance_scraper():
    """Import Binance scraper"""
    return importer.import_from_repo("Crypto_History_Scraper_BrowneApi", "BinanceScraper")

def import_investing_scraper():
    """Import Investing.com scraper"""
    return importer.import_from_repo("Investing_cem_Scraper", "InvestingScraper")

def import_forex_scraper():
    """Import Forex scraper"""
    return importer.import_from_repo("ForexScraper", "ForexGeneralScraper")

# Test imports
if __name__ == "__main__":
    print("🧪 Testing imports...")
    
    # Test import Indonesia stocks scraper
    IndonesiaStocksScraper = import_indonesia_stocks_scraper()
    if IndonesiaStocksScraper:
        print(f"✅ IndonesiaStocksScraper: {IndonesiaStocksScraper}")
        INDONESIA_SCRAPER_AVAILABLE = True
    else:
        print("❌ IndonesiaStocksScraper not available")
        INDONESIA_SCRAPER_AVAILABLE = False
    
    # Test others...
