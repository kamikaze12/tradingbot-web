python -m PyInstaller --onefile ^
--name=TradingBot ^
--add-data=".env;." ^
--add-data="config;config" ^
--add-data="C:\Users\muraga\AppData\Roaming\Python\Python313\site-packages\talib;talib" ^
--hidden-import=psycopg2 ^
--hidden-import=python-dotenv ^
--hidden-import=ccxt ^
--hidden-import=pandas ^
--hidden-import=numpy ^
--clean ^
main.py