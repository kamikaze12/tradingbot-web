# bot/external_repos/__init__.py
import sys
import os

# Tambahkan current directory ke Python path
current_dir = os.path.dirname(__file__)
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# Setup untuk semua submodules
submodules = [
    'Crypto_History_Scraper_BinanceApi',
    'cryptocurrency_scraper',
    'indonesia_stocks_scraper',
    'ForexScraper',
    'ForexTrackerpro',
    'Forex_analyzer_X_scrapper',
    'Investing_com_Scraper',
    'quant_trading'
]

for submodule in submodules:
    submodule_path = os.path.join(current_dir, submodule)
    if os.path.exists(submodule_path) and submodule_path not in sys.path:
        sys.path.insert(0, submodule_path)

print(f"✅ external_repos initialized with {len(submodules)} submodules")
