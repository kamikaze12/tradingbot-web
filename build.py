# build.py
import PyInstaller.__main__
import os

PyInstaller.__main__.run([
    'main.py',
    '--onefile',
    '--name=TradingBot',
    '--add-data=.env;.',
    '--add-data=config;config',
    '--hidden-import=psycopg2',
    '--hidden-import=python-dotenv', 
    '--hidden-import=ccxt',
    '--hidden-import=pandas',
    '--hidden-import=numpy',
    '--hidden-import=talib',
    '--clean'
])