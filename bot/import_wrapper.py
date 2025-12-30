# bot/import_wrapper.py - UPDATE

import importlib.util
import sys
import os
import logging
from pathlib import Path
from typing import Optional, Any, Dict, List

# Setup logging
logger = logging.getLogger(__name__)

class ExternalRepoImporter:
    def __init__(self, base_path: str = "bot/external_repos"):
        self.base_path = Path(base_path)
        self.modules_cache: Dict[str, Any] = {}
        
        # Debug: list semua repo yang ada
        self._debug_list_repos()
    
    def _debug_list_repos(self):
        """Debug: List semua repo dan file didalamnya"""
        print("\n🔍 DEBUG: Listing external repos...")
        if not self.base_path.exists():
            print("❌ Folder external_repos tidak ditemukan!")
            return
        
        for item in self.base_path.iterdir():
            if item.is_dir():
                print(f"\n📁 {item.name}:")
                # List semua .py files
                py_files = list(item.rglob("*.py"))
                if py_files:
                    for py_file in py_files:
                        print(f"  📄 {py_file.relative_to(item)}")
                        # Baca isi file untuk cari class
                        try:
                            with open(py_file, 'r') as f:
                                content = f.read()
                                classes = self._extract_classes(content)
                                if classes:
                                    print(f"    🏷️  Classes: {', '.join(classes)}")
                        except:
                            pass
                else:
                    print("  ⚠️  No .py files found")
    
    def _extract_classes(self, content: str) -> List[str]:
        """Extract class names dari file content"""
        import re
        classes = []
        lines = content.split('\n')
        for line in lines:
            line = line.strip()
            if line.startswith('class '):
                # Extract class name
                match = re.match(r'class\s+(\w+)', line)
                if match:
                    classes.append(match.group(1))
        return classes
    
    def import_from_repo(self, repo_name: str, expected_class: str = None):
        """Import dari repo tertentu"""
        repo_path = self.base_path / repo_name
        if not repo_path.exists():
            print(f"❌ Repo {repo_name} tidak ditemukan di {repo_path}")
            return None
        
        print(f"\n🔧 Importing from {repo_name}...")
        
        # Cari semua .py files
        py_files = list(repo_path.rglob("*.py"))
        if not py_files:
            print(f"⚠️  No Python files in {repo_name}")
            return None
        
        # Coba setiap file
        for py_file in py_files:
            try:
                print(f"  📂 Trying {py_file.name}...")
                
                # Buat module name
                module_name = f"bot.external_repos.{repo_name}.{py_file.stem}"
                
                # Load module
                spec = importlib.util.spec_from_file_location(
                    module_name,
                    py_file
                )
                if spec is None:
                    continue
                
                module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = module
                spec.loader.exec_module(module)
                
                print(f"  ✅ Successfully loaded module")
                
                # List semua attributes
                print(f"  📋 Module attributes:")
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if isinstance(attr, type):
                        print(f"    🏷️  Class: {attr_name}")
                    elif not attr_name.startswith('_'):
                        print(f"    📝 Attr: {attr_name} ({type(attr).__name__})")
                
                # Cari class yang diinginkan
                if expected_class:
                    if hasattr(module, expected_class):
                        cls = getattr(module, expected_class)
                        print(f"  🎯 Found expected class: {expected_class}")
                        return cls
                    else:
                        print(f"  ⚠️  Class {expected_class} not found in {py_file.name}")
                
                # Jika tidak ada expected class, return module
                return module
                
            except Exception as e:
                print(f"  ❌ Error loading {py_file.name}: {e}")
                continue
        
        print(f"❌ All files in {repo_name} failed to load")
        return None

# Singleton
importer = ExternalRepoImporter()

# Test specific repos
def test_forex_scraper():
    return importer.import_from_repo("ForexScraper", "ForexGeneralScraper")

def test_indonesia_stocks_scraper():
    return importer.import_from_repo("indonesia_stocks_scraper", "IndonesiaStocksScraper")

def test_investing_scraper():
    return importer.import_from_repo("Investing_com_Scraper", "InvestingScraper")

def test_binance_scraper():
    return importer.import_from_repo("Crypto_History_Scraper_BinanceApi", "BinanceScraper")

if __name__ == "__main__":
    print("🧪 DEBUG: Testing imports...")
    test_forex_scraper()
    test_indonesia_stocks_scraper()
    test_investing_scraper()
    test_binance_scraper()
