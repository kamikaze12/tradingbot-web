import ccxt
import time
import threading
import json
import warnings
from datetime import datetime
from .strategies import TechnicalAnalysisStrategy
from .data_provider import CCXTDataProvider
from .notifier import SoundNotifier
from database.db_handler import DatabaseHandler

warnings.filterwarnings('ignore')

class TradingBot:
    def __init__(self, config_path='config/config.json'):
        self.config_path = config_path
        self.load_config()
        
        # Initialize components
        self.data_provider = CCXTDataProvider(
            exchange_id=self.config.get('exchange', 'binance'),
            api_key=self.config.get('api_key', ''),
            secret=self.config.get('api_secret', '')
        )
        
        self.strategy = TechnicalAnalysisStrategy(
            atr_multiplier=self.config.get('atr_multiplier', 1.0),
            entry_range_pct=self.config.get('entry_range_pct', 0.02)
        )
        
        self.notifier = SoundNotifier()
        self.db = DatabaseHandler()
        
        self.symbols = self.config.get('symbols', [])
        self.timeframe = self.config.get('timeframe', '1h')
        self.alert_active = False
        self.entry_positions = {}
        self.position_ids = {}
        
    def load_config(self):
        try:
            with open(self.config_path, 'r') as f:
                self.config = json.load(f)
        except FileNotFoundError:
            self.config = {
                'symbols': ['SOL/USDT', 'ADA/USDT', 'XRP/USDT', 'DOT/USDT', 'AVAX/USDT'],
                'timeframe': '1h',
                'atr_multiplier': 1.0,
                'entry_range_pct': 0.02,
                'exchange': 'binance',
                'api_key': '',
                'api_secret': ''
            }
            self.save_config()
            
    def save_config(self):
        with open(self.config_path, 'w') as f:
            json.dump(self.config, f, indent=4)
            
    def get_popular_coins(self, limit=20):
        return self.data_provider.get_popular_coins(limit)
            
    def menu_1_top_5_coins(self):
        print("Menganalisis Top 5 Koin Potensial...")
        popular_coins = self.get_popular_coins(15)
        
        results = []
        print("Sedang menganalisis koin-koin populer...")
        for coin in popular_coins:
            df = self.data_provider.get_ohlcv(coin, self.timeframe, 100)
            if df is None or len(df) < 50:
                continue
                
            analysis = self.strategy.analyze(df)
            if analysis and analysis['action'] in ['LONG', 'SHORT']:
                analysis['symbol'] = coin
                results.append(analysis)
            time.sleep(0.1)
        
        results.sort(key=lambda x: x.get('score', 0), reverse=True)
        
        print("\n" + "="*60)
        print("TOP 5 KOIN POTENSIAL UNTUK TRADING")
        print("="*60)
        
        if not results:
            print("Tidak ada sinyal trading kuat yang ditemukan.")
            return
            
        for i, result in enumerate(results[:5], 1):
            print(f"\n{i}. {result['symbol']} - {result['action']} (Score: {result['score']}/5)")
            print(f"   Range Entry: {result['entry_low']:.4f} - {result['entry_high']:.4f}")
            print(f"   TP1: {result['tp1']:.4f} | TP2: {result['tp2']:.4f} | TP3: {result['tp3']:.4f}")
            print(f"   SL: {result['sl']:.4f}")
            print(f"   RSI: {result['rsi']:.2f} | Trend: {result['trend']}")
            print(f"   Volume: {result['volume_ratio']:.2f}x rata-rata")
            
        print(f"\nPilih koin yang ingin dimonitor (contoh: 1 3 5 atau 'all' untuk semua):")
        choice = input("Pilihan: ").strip().lower()
        
        selected_coins = []
        if choice == 'all':
            selected_coins = results[:5]
        else:
            try:
                indices = [int(x.strip()) - 1 for x in choice.split() if x.strip().isdigit()]
                for idx in indices:
                    if 0 <= idx < len(results[:5]):
                        selected_coins.append(results[idx])
            except:
                print("Input tidak valid, menggunakan 3 koin teratas")
                selected_coins = results[:3]
                
        if selected_coins:
            for coin in selected_coins:
                symbol = coin['symbol']
                print(f"\nUntuk {symbol}, range entry: {coin['entry_low']:.4f} - {coin['entry_high']:.4f}")
                
                while True:
                    try:
                        actual_entry = float(input(f"Masukkan harga entry aktual untuk {symbol}: "))
                        if coin['entry_low'] <= actual_entry <= coin['entry_high']:
                            atr = coin['atr']
                            if coin['action'] == "LONG":
                                coin['tp1'] = actual_entry + atr * self.strategy.atr_multiplier
                                coin['tp2'] = actual_entry + atr * self.strategy.atr_multiplier * 2
                                coin['tp3'] = actual_entry + atr * self.strategy.atr_multiplier * 3
                                coin['sl'] = actual_entry - atr * self.strategy.atr_multiplier
                            else:
                                coin['tp1'] = actual_entry - atr * self.strategy.atr_multiplier
                                coin['tp2'] = actual_entry - atr * self.strategy.atr_multiplier * 2
                                coin['tp3'] = actual_entry - atr * self.strategy.atr_multiplier * 3
                                coin['sl'] = actual_entry + atr * self.strategy.atr_multiplier
                                
                            coin['entry'] = actual_entry
                            break
                        else:
                            print(f"Entry harus dalam range {coin['entry_low']:.4f} - {coin['entry_high']:.4f}")
                    except ValueError:
                        print("Masukkan angka yang valid.")
            
            self.entry_positions = {coin['symbol']: coin for coin in selected_coins}
            self.alert_active = True
            print(f"\n✅ Memonitor {len(selected_coins)} koin untuk alert...")
            print("🔊 Sound alert AKTIF!")
            self.notifier.play_alert()
            
            for symbol, position in self.entry_positions.items():
                position_id = self.db.save_position(position)
                self.position_ids[symbol] = position_id
                print(f"Posisi {symbol} disimpan dengan ID: {position_id}")
                
            alert_thread = threading.Thread(target=self.start_monitoring)
            alert_thread.daemon = True
            alert_thread.start()
    
    def menu_2_analyze_coin(self):
        symbol = input("Masukkan simbol koin (contoh: SOL/USDT): ").strip().upper()
        if not symbol.endswith('/USDT'):
            symbol += '/USDT'
            
        print(f"Menganalisis {symbol}...")
        df = self.data_provider.get_ohlcv(symbol, self.timeframe, 100)
        if df is None or len(df) < 50:
            print(f"Tidak dapat mendapatkan data untuk {symbol} atau data tidak cukup")
            return
            
        analysis = self.strategy.analyze(df)
        if analysis:
            analysis['symbol'] = symbol
            print(f"\n=== HASIL ANALISIS {symbol} ===")
            print(f"Arah: {analysis['action']} (Score: {analysis['score']}/5)")
            print(f"Range Entry: {analysis['entry_low']:.4f} - {analysis['entry_high']:.4f}")
            print(f"TP1: {analysis['tp1']:.4f}")
            print(f"TP2: {analysis['tp2']:.4f}")
            print(f"TP3: {analysis['tp3']:.4f}")
            print(f"SL: {analysis['sl']:.4f}")
            print(f"RSI: {analysis['rsi']:.2f}")
            print(f"Trend: {analysis['trend']}")
            print(f"Volume: {analysis['volume_ratio']:.2f}x rata-rata")
            
            signal_id = self.db.save_signal(analysis)
            print(f"Signal ID: {signal_id}")
            
            monitor = input("\nIngin monitor koin ini untuk alert? (y/n): ").lower()
            if monitor == 'y':
                print(f"Range entry: {analysis['entry_low']:.4f} - {analysis['entry_high']:.4f}")
                
                while True:
                    try:
                        actual_entry = float(input("Masukkan harga entry aktual: "))
                        if analysis['entry_low'] <= actual_entry <= analysis['entry_high']:
                            atr = analysis['atr']
                            if analysis['action'] == "LONG":
                                analysis['tp1'] = actual_entry + atr * self.strategy.atr_multiplier
                                analysis['tp2'] = actual_entry + atr * self.strategy.atr_multiplier * 2
                                analysis['tp3'] = actual_entry + atr * self.strategy.atr_multiplier * 3
                                analysis['sl'] = actual_entry - atr * self.strategy.atr_multiplier
                            else:
                                analysis['tp1'] = actual_entry - atr * self.strategy.atr_multiplier
                                analysis['tp2'] = actual_entry - atr * self.strategy.atr_multiplier * 2
                                analysis['tp3'] = actual_entry - atr * self.strategy.atr_multiplier * 3
                                analysis['sl'] = actual_entry + atr * self.strategy.atr_multiplier
                                
                            analysis['entry'] = actual_entry
                            break
                        else:
                            print(f"Entry harus dalam range {analysis['entry_low']:.4f} - {analysis['entry_high']:.4f}")
                    except ValueError:
                        print("Masukkan angka yang valid.")
                
                self.entry_positions[symbol] = analysis
                self.alert_active = True
                
                position_id = self.db.save_position(analysis)
                self.position_ids[symbol] = position_id
                print(f"Posisi {symbol} disimpan dengan ID: {position_id}")
                
                print("✅ Alert aktif! Bot akan memantau pergerakan harga.")
                print("🔊 Sound alert AKTIF!")
                self.notifier.play_alert()
                alert_thread = threading.Thread(target=self.start_monitoring)
                alert_thread.daemon = True
                alert_thread.start()
        else:
            print(f"Tidak dapat menganalisis {symbol} atau tidak ada sinyal trading")
            
    def menu_3_custom_entry(self):
        symbol = input("Masukkan simbol koin (contoh: BTC/USDT): ").strip().upper()
        if not symbol.endswith('/USDT'):
            symbol += '/USDT'
            
        try:
            entry_price = float(input("Masukkan harga entry: "))
            direction = input("Masukkan arah trading (LONG/SHORT): ").strip().upper()
            
            if direction not in ['LONG', 'SHORT']:
                print("Arah trading harus LONG atau SHORT")
                return
                
            df = self.data_provider.get_ohlcv(symbol, self.timeframe, 100)
            if df is None or len(df) < 50:
                print("Gagal mendapatkan data market atau data tidak cukup")
                return
                
            import talib
            atr = talib.ATR(df['high'], df['low'], df['close'], timeperiod=14).iloc[-1]
            
            if direction == "LONG":
                tp1 = entry_price + atr * self.strategy.atr_multiplier
                tp2 = entry_price + atr * self.strategy.atr_multiplier * 2
                tp3 = entry_price + atr * self.strategy.atr_multiplier * 3
                sl = entry_price - atr * self.strategy.atr_multiplier
            else:
                tp1 = entry_price - atr * self.strategy.atr_multiplier
                tp2 = entry_price - atr * self.strategy.atr_multiplier * 2
                tp3 = entry_price - atr * self.strategy.atr_multiplier * 3
                sl = entry_price + atr * self.strategy.atr_multiplier
                
            print(f"\n=== HASIL PERHITUNGAN UNTUK {symbol} ===")
            print(f"Arah: {direction}")
            print(f"Entry: {entry_price:.4f}")
            print(f"TP1: {tp1:.4f}")
            print(f"TP2: {tp2:.4f}")
            print(f"TP3: {tp3:.4f}")
            print(f"SL: {sl:.4f}")
            
            position_data = {
                'symbol': symbol,
                'action': direction,
                'entry': entry_price,
                'tp1': tp1,
                'tp2': tp2,
                'tp3': tp3,
                'sl': sl,
                'current_price': df['close'].iloc[-1] if df is not None else entry_price,
                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            position_id = self.db.save_position(position_data)
            self.position_ids[symbol] = position_id
            print(f"Posisi {symbol} disimpan dengan ID: {position_id}")
            
            monitor = input("\nIngin monitor posisi ini untuk alert? (y/n): ").lower()
            if monitor == 'y':
                self.entry_positions[symbol] = position_data
                self.alert_active = True
                print("Alert aktif! Bot akan memantau pergerakan harga.")
                print("🔊 Sound alert AKTIF!")
                self.notifier.play_alert()
                alert_thread = threading.Thread(target=self.start_monitoring)
                alert_thread.daemon = True
                alert_thread.start()
                
        except ValueError:
            print("Input harga tidak valid")
        except Exception as e:
            print(f"Error: {e}")
            
    def menu_4_show_positions(self):
        if not self.entry_positions:
            print("Tidak ada posisi yang aktif.")
            return
            
        print("\n=== POSISI AKTIF ===")
        for symbol, position in self.entry_positions.items():
            position_id = self.position_ids.get(symbol, 'N/A')
            print(f"\n{symbol} (ID: {position_id}) - {position['action']}")
            print(f"Entry: {position['entry']}")
            print(f"TP1: {position['tp1']} {'✅' if position.get('tp1_hit') else ''}")
            print(f"TP2: {position['tp2']} {'✅' if position.get('tp2_hit') else ''}")
            print(f"TP3: {position['tp3']} {'✅' if position.get('tp3_hit') else ''}")
            print(f"SL: {position['sl']}")
            print(f"Harga Sekarang: {position.get('current_price', 'N/A')}")
            print(f"Waktu Entry: {position.get('timestamp', 'N/A')}")
            
    def menu_5_show_history(self):
        print("\n=== HISTORY TRADING ===")
        history = self.db.get_trade_history(limit=10)
        
        if not history:
            print("Belum ada history trading.")
            return
            
        for trade in history:
            print(f"\n{trade[1]} - {trade[2]}")
            print(f"Entry: {trade[3]} | Exit: {trade[4]}")
            print(f"P/L: {trade[5]:.4f} | Type: {trade[6]}")
            print(f"Time: {trade[7]}")
            
    def start_monitoring(self):
        print("📡 Memulai live alerts dengan sound...")
        print("🔊 Sound alert AKTIF!")
        print("⏹️  Tekan Ctrl+C di menu utama untuk menghentikan")
        
        try:
            while self.alert_active and self.entry_positions:
                for symbol, position in list(self.entry_positions.items()):
                    try:
                        ticker = self.data_provider.get_ticker(symbol)
                        if not ticker:
                            continue
                            
                        current_price = ticker['last']
                        
                        self.entry_positions[symbol]['current_price'] = current_price
                        
                        position_id = self.position_ids.get(symbol)
                        if position_id:
                            self.db.update_position(position_id, {'current_price': current_price})
                        
                        if position['action'] == 'LONG':
                            if current_price <= position['sl']:
                                print(f"\n🚨 SELL NOW! {symbol} hit Stop Loss at {current_price}")
                                print(f"Entry: {position['entry']} | SL: {position['sl']}")
                                self.notifier.play_alert("loss")
                                
                                if symbol in self.position_ids:
                                    self.db.close_position(self.position_ids[symbol], current_price, "SL")
                                    del self.position_ids[symbol]
                                
                                del self.entry_positions[symbol]
                            elif current_price >= position['tp3']:
                                print(f"\n🎯 TP3 HIT! {symbol} at {current_price}")
                                print(f"Entry: {position['entry']} | TP3: {position['tp3']}")
                                self.notifier.play_alert("profit")
                                
                                if symbol in self.position_ids:
                                    self.db.close_position(self.position_ids[symbol], current_price, "TP3")
                                    del self.position_ids[symbol]
                                
                                del self.entry_positions[symbol]
                            elif current_price >= position['tp2']:
                                if 'tp2_hit' not in position:
                                    print(f"\n🎯 TP2 HIT! {symbol} at {current_price}")
                                    print(f"Entry: {position['entry']} | TP2: {position['tp2']}")
                                    self.notifier.play_alert("profit")
                                    self.entry_positions[symbol]['tp2_hit'] = True
                            elif current_price >= position['tp1']:
                                if 'tp1_hit' not in position:
                                    print(f"\n🎯 TP1 HIT! {symbol} at {current_price}")
                                    print(f"Entry: {position['entry']} | TP1: {position['tp1']}")
                                    self.notifier.play_alert("profit")
                                    self.entry_positions[symbol]['tp1_hit'] = True
                                    
                        elif position['action'] == 'SHORT':
                            if current_price >= position['sl']:
                                print(f"\n🚨 SELL NOW! {symbol} hit Stop Loss at {current_price}")
                                print(f"Entry: {position['entry']} | SL: {position['sl']}")
                                self.notifier.play_alert("loss")
                                
                                if symbol in self.position_ids:
                                    self.db.close_position(self.position_ids[symbol], current_price, "SL")
                                    del self.position_ids[symbol]
                                
                                del self.entry_positions[symbol]
                            elif current_price <= position['tp3']:
                                print(f"\n🎯 TP3 HIT! {symbol} at {current_price}")
                                print(f"Entry: {position['entry']} | TP3: {position['tp3']}")
                                self.notifier.play_alert("profit")
                                
                                if symbol in self.position_ids:
                                    self.db.close_position(self.position_ids[symbol], current_price, "TP3")
                                    del self.position_ids[symbol]
                                
                                del self.entry_positions[symbol]
                            elif current_price <= position['tp2']:
                                if 'tp2_hit' not in position:
                                    print(f"\n🎯 TP2 HIT! {symbol} at {current_price}")
                                    print(f"Entry: {position['entry']} | TP2: {position['tp2']}")
                                    self.notifier.play_alert("profit")
                                    self.entry_positions[symbol]['tp2_hit'] = True
                            elif current_price <= position['tp1']:
                                if 'tp1_hit' not in position:
                                    print(f"\n🎯 TP1 HIT! {symbol} at {current_price}")
                                    print(f"Entry: {position['entry']} | TP1: {position['tp1']}")
                                    self.notifier.play_alert("profit")
                                    self.entry_positions[symbol]['tp1_hit'] = True
                                
                    except Exception as e:
                        print(f"Error monitoring {symbol}: {e}")
                        
                if not self.entry_positions:
                    print("\n✅ Semua posisi telah ditutup.")
                    self.alert_active = False
                    break
                    
                time.sleep(10)
                
        except Exception as e:
            print(f"Error in monitoring: {e}")

    def run(self):
        while True:
            print("\n" + "="*50)
            print("🤖 BOT TRADING DENGAN SOUND ALERT")
            print("="*50)
            print("1. Top 5 koin potensial (Pilih yang mau dimonitor)")
            print("2. Analisis koin tertentu")
            print("3. Hitung TP1-3 untuk entry custom") 
            print("4. Lihat posisi aktif")
            print("5. Lihat history trading")
            print("6. Keluar")
            
            choice = input("\nPilih menu (1-6): ")
            
            if choice == '1':
                self.menu_1_top_5_coins()
            elif choice == '2':
                self.menu_2_analyze_coin()
            elif choice == '3':
                self.menu_3_custom_entry()
            elif choice == '4':
                self.menu_4_show_positions()
            elif choice == '5':
                self.menu_5_show_history()
            elif choice == '6':
                print("Terima kasih telah menggunakan bot trading!")
                self.alert_active = False
                break
            else:
                print("Pilihan tidak valid.")
