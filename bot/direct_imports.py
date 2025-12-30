# bot/direct_imports.py
"""
SIMPLE STATIC IMPORTS - PANGGIL FILE UTAMA LANGSUNG
"""

import sys
import os
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class DirectImporter:
    """Importer sederhana dengan static import"""
    
    def __init__(self):
        self.base_path = Path("bot/external_repos")
        self.import_cache = {}
    
    def import_forex_scraper(self):
        """Import langsung dari forex folder"""
        repo_path = self.base_path / "ForexScraper" / "forex"
        if repo_path.exists():
            sys.path.append(str(repo_path))  # Tambah path forex folder
            try:
                from some_forex_file import ForexScraper  # Ganti 'some_forex_file' dengan nama file .py utama di forex/
                logger.info("✅ Imported ForexScraper directly")
                return ForexScraper
            except ImportError as e:
                logger.error(f"❌ Forex import failed: {e}")
        return self._create_mock_forex_scraper()
    
    def import_binance_scraper(self):
        """Import langsung dari main.py"""
        repo_path = self.base_path / "Crypto_History_Scraper_BinanceApi"
        main_file = repo_path / "main.py"
        if main_file.exists():
            sys.path.append(str(repo_path))  # Tambah path repo
            try:
                from main import BinanceScraper  # Asumsi class nama BinanceScraper di main.py
                logger.info("✅ Imported BinanceScraper directly")
                return BinanceScraper
            except ImportError as e:
                logger.error(f"❌ Binance import failed: {e}")
        return self._create_mock_binance_scraper()
    
    def import_indonesia_stocks_scraper(self):
        """Import langsung dari app.py - Fix untuk RTI subfolder"""
        repo_path = self.base_path / "indonesia_stocks_scraper"
        app_file = repo_path / "app.py"
        if app_file.exists():
            sys.path.append(str(repo_path))  # Tambah root repo
            sys.path.append(str(repo_path / "RTI"))  # Tambah subfolder RTI (dari gambar kamu)
            # Tambah sys.path untuk subfolder lain jika perlu: IDX, Stockbit, Yahoo
            sys.path.append(str(repo_path / "IDX"))
            sys.path.append(str(repo_path / "Stockbit"))
            sys.path.append(str(repo_path / "Yahoo"))
            try:
                # Ubah import di app.py jika perlu (hilangkan 'Scrapers.'), tapi di sini panggil langsung
                from app import IndonesiaStocksScraper  # Asumsi class nama ini di app.py; ganti sesuai
                logger.info("✅ Imported IndonesiaStocksScraper directly")
                return IndonesiaStocksScraper
            except ImportError as e:
                logger.error(f"❌ Indonesia import failed: {e} - Cek app.py import RTI")
        return self._create_mock_indonesia_scraper()
    
    def import_investing_scraper(self):
        """Import langsung dari GoldScrape.py - Fix db_table jika hilang"""
        repo_path = self.base_path / "Investing_com_Scraper"
        gold_file = repo_path / "GoldScrape.py"
        if gold_file.exists():
            sys.path.append(str(repo_path))  # Tambah path repo
            try:
                # Jika db_table hilang, tambah mock di sini atau hapus import di GoldScrape.py
                from GoldScrape import InvestingScraper  # Asumsi class nama ini
                logger.info("✅ Imported InvestingScraper directly")
                return InvestingScraper
            except ImportError as e:
                logger.error(f"❌ Investing import failed: {e} - Tambah db_table.py jika perlu")
        return self._create_mock_investing_scraper()

# Sisanya sama: _create_mock_*, singleton, public API, test_all()

# Di akhir, if __name__ == "__main__": test_all()
