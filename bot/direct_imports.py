# bot/direct_imports.py
"""
STATIC IMPORTS DENGAN MOCK UNTUK SKIP ERROR TANPA UBAH LOKAL
"""

import sys
import os
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Mock class untuk RTI Downloader (dari app.py)
class MockRTIDownloader:
    def __init__(self, *args, **kwargs):
        logger.info("✅ Mock RTI Downloader initialized")
    
    def fetch_stocks(self):
        return ['BBCA', 'BBRI', 'BMRI']  # Mock data saham ID
    
    def get_stock_data(self, stock_code, period='1y'):
        import yfinance as yf
        try:
            ticker = yf.Ticker(f"{stock_code}.JK")
            df = ticker.history(period=period)
            return df.to_dict('records')
        except:
            return None

# Mock Scrapers module
class MockScrapers:
    RTI = type('RTI', (), {})()  # Dummy RTI
    RTI.RTI_Downloader = MockRTIDownloader

# Mock db_table untuk Investing
class MockDBTable:
    def __init__(self, name, schema=None):
        logger.info("✅ Mock db_table initialized")
    
    def insert(self, item):
        logger.info("✅ Mock insert called")

class DirectImporter:
    """Importer dengan mock untuk fix error"""
    
    def __init__(self):
        self.base_path = Path("bot/external_repos")
        self.import_cache = {}
    
    def import_forex_scraper(self):
        repo_path = self.base_path / "ForexScraper" / "forex"
        if repo_path.exists():
            sys.path.append(str(repo_path))
            try:
                from forex_scraper import ForexScraper  # Ganti nama file/class sesuai
                return ForexScraper
            except ImportError as e:
                logger.error(f"❌ Forex import failed: {e}")
        return self._create_mock_forex_scraper()
    
    def import_binance_scraper(self):
        repo_path = self.base_path / "Crypto_History_Scraper_BinanceApi"
        if repo_path.exists():
            sys.path.append(str(repo_path))
            try:
                from main import BinanceScraper  # Ganti nama class
                return BinanceScraper
            except ImportError as e:
                logger.error(f"❌ Binance import failed: {e}")
        return self._create_mock_binance_scraper()
    
    def import_indonesia_stocks_scraper(self):
        repo_path = self.base_path / "indonesia_stocks_scraper"
        if repo_path.exists():
            # Tambah path subfolders
            sys.path.append(str(repo_path))
            sys.path.append(str(repo_path / "RTI"))
            sys.path.append(str(repo_path / "IDX"))
            sys.path.append(str(repo_path / "Stockbit"))
            sys.path.append(str(repo_path / "Yahoo"))
            
            # Mock Scrapers sebelum import app.py
            sys.modules['Scrapers'] = MockScrapers()
            sys.modules['Scrapers.RTI'] = MockScrapers.RTI
            sys.modules['Scrapers.RTI.RTI_Downloader'] = MockRTIDownloader
            
            try:
                import app  # Panggil app.py langsung
                # Asumsi app.py define Downloader - return itu
                return app.Downloader if hasattr(app, 'Downloader') else MockRTIDownloader
            except ImportError as e:
                logger.error(f"❌ Indonesia import failed: {e}")
        return self._create_mock_indonesia_scraper()
    
    def import_investing_scraper(self):
        repo_path = self.base_path / "Investing_com_Scraper"
        if repo_path.exists():
            sys.path.append(str(repo_path))
            
            # Mock db_table sebelum import
            sys.modules['db_table'] = MockDBTable()
            
            try:
                import GoldScrape  # Panggil GoldScrape.py
                # Asumsi define class GoldScraper atau similar
                for attr_name in dir(GoldScrape):
                    attr = getattr(GoldScrape, attr_name)
                    if isinstance(attr, type) and ('Gold' in attr_name or 'Scraper' in attr_name):
                        return attr
                return GoldScrape  # Jika module
            except ImportError as e:
                logger.error(f"❌ Investing import failed: {e}")
        return self._create_mock_investing_scraper()

    # Mock creators tetap sama dari code asli

# Singleton, public API, test_all() tetap sama
