import pandas as pd
from tvDatafeed import TvDatafeed, Interval
import logging
import time
import sys

# Setup Logging khusus untuk Provider ini
logger = logging.getLogger("TVProvider")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(handler)

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
            if username and password:
                self.tv = TvDatafeed(username, password)
                logger.info("✅ Login ke TradingView berhasil (Authenticated)")
            else:
                self.tv = TvDatafeed()
                logger.info("✅ Terhubung ke TradingView (Anonymous Mode)")
            
            self.is_connected = True
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
                return None

        # Mapping Interval string ke Object TvDatafeed
        interval_map = {
            '1m': Interval.in_1_minute,
            '5m': Interval.in_5_minute,
            '15m': Interval.in_15_minute,
            '30m': Interval.in_30_minute,
            '1h': Interval.in_1_hour,
            '4h': Interval.in_4_hour,
            '1d': Interval.in_daily,
            '1w': Interval.in_weekly,
        }
        
        tv_interval = interval_map.get(interval, Interval.in_1_hour)

        try:
            # Request Data
            # logger.info(f"📡 Fetching TV: {exchange}:{symbol} ({interval})")
            data = self.tv.get_hist(
                symbol=symbol, 
                exchange=exchange, 
                interval=tv_interval, 
                n_bars=n_bars + 10 # Buffer extra
            )

            # Validasi Data Kosong
            if data is None or data.empty:
                # logger.warning(f"⚠️ Data kosong untuk {symbol}")
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
            df = df.rename(columns=rename_map)

            # 3. Pastikan Kolom Wajib Ada
            required_cols = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
            if not all(col in df.columns for col in required_cols):
                logger.error(f"❌ Format kolom salah dari TV: {df.columns}")
                return None

            # 4. Cleaning Data Types
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df['open'] = df['open'].astype(float)
            df['high'] = df['high'].astype(float)
            df['low'] = df['low'].astype(float)
            df['close'] = df['close'].astype(float)
            df['volume'] = df['volume'].astype(float)

            # 5. Set Index & Sort
            df = df.set_index('timestamp')
            df = df.sort_index()

            # 6. Hapus duplikat index jika ada
            df = df[~df.index.duplicated(keep='last')]

            # 7. Potong sesuai n_bars yang diminta (ambil yang terbaru)
            return df.tail(n_bars)

        except Exception as e:
            logger.error(f"❌ Error scraping {symbol}: {e}")
            return None

# ==========================================
# TESTING AREA (Jalankan file ini langsung)
# ==========================================
if __name__ == "__main__":
    print("\n🚀 Memulai Test TV Provider...")
    provider = TradingViewProvider()
    
    # Test 1: Saham Indo (BBCA)
    print("\n1️⃣ Test Saham Indonesia (BBCA)")
    df_indo = provider.get_hist("BBCA", "IDX", "1d", 50)
    if df_indo is not None:
        print(f"✅ Sukses! Data terakhir:\n{df_indo.tail(3)}")
    else:
        print("❌ Gagal ambil BBCA")

    # Test 2: Forex (EURUSD)
    print("\n2️⃣ Test Forex (EURUSD)")
    df_forex = provider.get_hist("EURUSD", "FX_IDC", "1h", 50)
    if df_forex is not None:
        print(f"✅ Sukses! Data terakhir:\n{df_forex.tail(3)}")
    else:
        print("❌ Gagal ambil EURUSD")
