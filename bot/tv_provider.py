import pandas as pd
import logging
import time
import sys
from datetime import datetime, timedelta
import numpy as np

# Setup Logging khusus untuk Provider ini
logger = logging.getLogger("TVProvider")

class TradingViewProvider:
    def __init__(self, username=None, password=None):
        """
        Inisialisasi koneksi ke TradingView.
        Default menggunakan mode Anonymous (tanpa login).
        """
        self.tv = None
        self.is_connected = False
        self._connect(username, password)

    def _connect(self, username, password):
        try:
            # Coba import tvDatafeed
            try:
                from tvDatafeed import TvDatafeed, Interval
                self.tv_module = TvDatafeed
                self.interval_module = Interval
            except ImportError:
                logger.error("❌ tvDatafeed not installed. Install with: pip install tvDatafeed")
                self.is_connected = False
                return
            
            if username and password:
                self.tv = self.tv_module(username, password)
                logger.info("✅ Login ke TradingView berhasil (Authenticated)")
            else:
                self.tv = self.tv_module()
                logger.info("✅ Terhubung ke TradingView (Anonymous Mode)")
            
            self.is_connected = True
            logger.info("✅ TradingViewProvider initialized successfully")
        except Exception as e:
            logger.error(f"❌ Gagal connect ke TradingView: {e}")
            self.is_connected = False

    def get_hist(self, symbol: str, exchange: str = 'IDX', interval: str = '1h', n_bars: int = 100) -> pd.DataFrame:
        """
        Mengambil data OHLCV dari TradingView.
        
        Args:
            symbol (str): Ticker saham/forex (misal 'BBCA', 'EURUSD')
            exchange (str): Bursa (IDX, FX_IDC, OANDA, NASDAQ)
            interval (str): Timeframe ('1m', '5m', '1h', '1d')
            n_bars (int): Jumlah candle yang diambil
            
        Returns:
            pd.DataFrame: DataFrame standar (open, high, low, close, volume)
        """
        if not self.is_connected or not self.tv:
            # Coba reconnect sekali jika putus
            self._connect(None, None)
            if not self.is_connected:
                logger.error("❌ TradingView not connected")
                return None

        # Mapping Interval string ke Object TvDatafeed
        interval_map = {
            '1m': self.interval_module.in_1_minute,
            '5m': self.interval_module.in_5_minute,
            '15m': self.interval_module.in_15_minute,
            '30m': self.interval_module.in_30_minute,
            '1h': self.interval_module.in_1_hour,
            '4h': self.interval_module.in_4_hour,
            '1d': self.interval_module.in_daily,
            '1w': self.interval_module.in_weekly,
        }
        
        tv_interval = interval_map.get(interval)
        if tv_interval is None:
            logger.error(f"❌ Interval tidak didukung: {interval}")
            return None

        try:
            # Request Data
            logger.debug(f"📡 Fetching TV: {exchange}:{symbol} ({interval}) x{n_bars}")
            
            # Tambah buffer untuk data lebih banyak
            data = self.tv.get_hist(
                symbol=symbol, 
                exchange=exchange, 
                interval=tv_interval, 
                n_bars=n_bars + 20  # Buffer extra
            )

            # Validasi Data Kosong
            if data is None or data.empty:
                logger.warning(f"⚠️ Data kosong untuk {symbol} di {exchange}")
                return None

            # 1. Reset Index (Index bawaan TV agak aneh)
            df = data.reset_index()

            # 2. Rename Kolom ke Standar Bot (Lowercase)
            # Format raw TV biasanya: symbol, datetime, open, high, low, close, volume
            rename_map = {
                'datetime': 'timestamp',
                'open': 'open',
                'high': 'high',
                'low': 'low',
                'close': 'close',
                'volume': 'volume'
            }
            
            # Filter kolom yang ada saja
            existing_cols = {k: v for k, v in rename_map.items() if k in df.columns}
            df = df.rename(columns=existing_cols)

            # 3. Pastikan Kolom Wajib Ada
            required_cols = ['open', 'high', 'low', 'close']
            for col in required_cols:
                if col not in df.columns:
                    logger.error(f"❌ Kolom {col} tidak ditemukan dalam data TV")
                    return None

            # 4. Cleaning Data Types
            if 'timestamp' in df.columns:
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                # Set index
                df = df.set_index('timestamp')
            
            # Konversi ke float
            for col in required_cols + (['volume'] if 'volume' in df.columns else []):
                df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # Handle NaN values
            df = df.fillna(method='ffill').fillna(method='bfill')
            
            # 5. Sort Index (pastikan ascending)
            df = df.sort_index()

            # 6. Hapus duplikat index jika ada
            df = df[~df.index.duplicated(keep='last')]

            # 7. Potong sesuai n_bars yang diminta (ambil yang terbaru)
            result = df.tail(n_bars)
            
            if len(result) < 5:
                logger.warning(f"⚠️ Data terlalu sedikit: {len(result)} bars")
                return None
                
            logger.debug(f"✅ TV Success: {symbol} -> {len(result)} bars")
            return result

        except Exception as e:
            logger.error(f"❌ Error scraping {symbol} di {exchange}: {e}")
            return None

    def get_multiple_symbols(self, symbols, exchange='IDX', interval='1d', n_bars=100):
        """Ambil data multiple symbols (batch)"""
        results = {}
        for symbol in symbols:
            try:
                df = self.get_hist(symbol, exchange, interval, n_bars)
                if df is not None:
                    results[symbol] = df
                    time.sleep(0.5)  # Rate limiting
            except Exception as e:
                logger.error(f"❌ Error for {symbol}: {e}")
        return results

# ==========================================
# TESTING AREA (Jalankan file ini langsung)
# ==========================================
if __name__ == "__main__":
    print("\n🚀 Memulai Test TV Provider...")
    
    # Setup logging
    logging.basicConfig(level=logging.INFO)
    
    provider = TradingViewProvider()
    
    if provider.is_connected:
        print("✅ TradingView connected successfully")
        
        # Test 1: Saham Indo (BBCA)
        print("\n1️⃣ Test Saham Indonesia (BBCA)")
        df_indo = provider.get_hist("BBCA", "IDX", "1d", 50)
        if df_indo is not None:
            print(f"✅ Sukses! Data: {len(df_indo)} bars")
            print(f"   Last 3 rows:\n{df_indo.tail(3)}")
            print(f"   Price range: {df_indo['close'].min():.2f} - {df_indo['close'].max():.2f}")
        else:
            print("❌ Gagal ambil BBCA")

        # Test 2: Forex (EURUSD)
        print("\n2️⃣ Test Forex (EURUSD)")
        df_forex = provider.get_hist("EURUSD", "FX_IDC", "1h", 50)
        if df_forex is not None:
            print(f"✅ Sukses! Data: {len(df_forex)} bars")
            print(f"   Last 3 rows:\n{df_forex.tail(3)}")
        else:
            print("❌ Gagal ambil EURUSD")

        # Test 3: US Stocks (AAPL)
        print("\n3️⃣ Test US Stocks (AAPL)")
        df_us = provider.get_hist("AAPL", "NASDAQ", "1d", 50)
        if df_us is not None:
            print(f"✅ Sukses! Data: {len(df_us)} bars")
            print(f"   Last 3 rows:\n{df_us.tail(3)}")
        else:
            print("❌ Gagal ambil AAPL")
    else:
        print("❌ Failed to connect to TradingView")
