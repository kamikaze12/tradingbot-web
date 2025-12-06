# ... (semua kode sebelumnya tetap sama)

class EnhancedCCXTDataProvider(EnhancedDataProvider):
    """Enhanced CCXT provider - UNIVERSAL (tanpa pemisahan spot/future)"""
    
    def __init__(self, exchange_id='binance', api_key='', secret=''):
        super().__init__()
        
        self.exchange_id = exchange_id
        exchange_class = getattr(ccxt, exchange_id, None)
        
        if exchange_class is None:
            logger.error(f"Exchange {exchange_id} not found in CCXT")
            self.exchange = None
        else:
            try:
                config = {
                    'apiKey': api_key,
                    'secret': secret,
                    'enableRateLimit': True,
                    'timeout': 30000,
                    'options': {
                        'defaultType': 'spot',  # Default ke spot, tapi akan load semua markets
                    }
                }
                
                self.exchange = exchange_class(config)
                
                # Load semua market tanpa filter
                try:
                    self.exchange.load_markets()
                    logger.info(f"✅ Successfully connected to {exchange_id}, loaded {len(self.exchange.markets)} markets")
                    
                    # Log market types yang tersedia
                    market_types = set()
                    for symbol, market in self.exchange.markets.items():
                        if 'type' in market:
                            market_types.add(market['type'])
                    
                    logger.info(f"📊 Available market types: {list(market_types)}")
                    
                except Exception as e:
                    logger.warning(f"⚠️ Could not load all markets: {e}")
                    self.exchange = None
                
            except Exception as e:
                logger.error(f"Failed to initialize {exchange_id}: {str(e)}")
                self.exchange = None

    def get_ohlcv(self, symbol, timeframe='1h', limit=200):
        """Get OHLCV data dengan validation - UNIVERSAL"""
        def fetch_ccxt_data():
            if not self.exchange:
                raise Exception(f"Exchange {self.exchange_id} not initialized")
            
            try:
                # Coba fetch data
                ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
                if not ohlcv:
                    # Coba dengan symbol alternatif
                    alt_symbols = self._get_alternative_symbols(symbol)
                    for alt_symbol in alt_symbols:
                        if alt_symbol != symbol:
                            try:
                                ohlcv = self.exchange.fetch_ohlcv(alt_symbol, timeframe, limit=limit)
                                if ohlcv:
                                    logger.info(f"⚠️ Using alternative symbol {alt_symbol} for {symbol}")
                                    symbol = alt_symbol
                                    break
                            except:
                                continue
                    
                    if not ohlcv:
                        raise ValueError(f"No OHLCV data returned for {symbol}")
                
                df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                
                # 🚨 BUANG BAR HARGA 100
                if 'close' in df.columns:
                    mask_100 = abs(df['close'] - 100.0) < 0.001
                    count_100 = mask_100.sum()
                    if count_100 > 0:
                        df = df[~mask_100].copy()
                        logger.warning(f"⚠️ Removed {count_100} bars with price 100 for {symbol}")
                
                # Validasi data
                is_valid, validation_msg = self.validate_market_data(df, symbol)
                if not is_valid:
                    logger.warning(f"CCXT data validation failed: {symbol}")
                    # Data sudah diperbaiki di dalam fungsi validate_market_data
                
                current_price = df['close'].iloc[-1] if len(df) > 0 else 0
                logger.info(f"📊 CCXT DATA: {symbol} - {len(df)} bars, current price: {current_price:.8f}")
                
                return df
                
            except Exception as e:
                logger.warning(f"CCXT failed for {symbol}: {str(e)}")
                raise

        return self._safe_api_call(fetch_ccxt_data)
        
    def get_ticker(self, symbol):
        """Get ticker data - UNIVERSAL"""
        def fetch_ticker():
            try:
                if not self.exchange:
                    raise Exception("Exchange not initialized")
                    
                ticker = self.exchange.fetch_ticker(symbol)
                last_price = ticker.get('last')
                
                if last_price is None or last_price <= 0:
                    # Coba dengan symbol alternatif
                    alt_symbols = self._get_alternative_symbols(symbol)
                    for alt_symbol in alt_symbols:
                        if alt_symbol != symbol:
                            try:
                                ticker = self.exchange.fetch_ticker(alt_symbol)
                                last_price = ticker.get('last')
                                if last_price and last_price > 0:
                                    logger.info(f"⚠️ Using alternative symbol {alt_symbol} for ticker")
                                    symbol = alt_symbol
                                    break
                            except:
                                continue
                    
                    if last_price is None or last_price <= 0:
                        raise ValueError(f"Invalid price for {symbol}: {last_price}")
                
                # 🚨 Cek harga 100
                if abs(last_price - 100.0) < 0.001:
                    raise ValueError(f"Suspicious price 100 for {symbol}")
                
                return {
                    'last': last_price,
                    'volume': ticker.get('baseVolume', 0),
                    'high': ticker.get('high'),
                    'low': ticker.get('low'),
                    'bid': ticker.get('bid'),
                    'ask': ticker.get('ask'),
                    'symbol': symbol
                }
            except Exception as e:
                logger.error(f"CCXT ticker error: {str(e)}")
                raise
        
        return self._safe_api_call(fetch_ticker)

    def get_popular_assets(self, limit=100, **kwargs):
        """Get popular assets - UNIVERSAL (tanpa pemisahan spot/future)"""
        try:
            logger.info(f"🔄 Getting {limit} popular assets from {self.exchange_id}...")
            
            if not self.exchange:
                logger.warning(f"Exchange {self.exchange_id} not initialized")
                return self._get_fallback_major_coins(limit)
            
            try:
                # Reload markets untuk memastikan data terbaru
                self.exchange.load_markets()
                markets = self.exchange.markets
                logger.info(f"📊 Loaded {len(markets)} markets from {self.exchange_id}")
            except Exception as e:
                logger.error(f"Failed to load markets: {e}")
                return self._get_fallback_major_coins(limit)
            
            # TAMPILKAN SEMUA SIMBOL, biar strategi yang filter
            target_markets = []
            for symbol, market in markets.items():
                # Prioritaskan USDT pairs (spot dan futures)
                if any(x in symbol for x in ['/USDT', ':USDT', '-USDT']):
                    target_markets.append(symbol)
            
            logger.info(f"📊 Found {len(target_markets)} USDT markets")
            
            # Filter stablecoins
            excluded_coins = ['BUSD', 'USDC', 'DAI', 'TUSD', 'USDP', 'UST', 'FDUSD']
            filtered_markets = [
                symbol for symbol in target_markets 
                if not any(excluded in symbol for excluded in excluded_coins)
            ]
            
            # Ambil berdasarkan volume
            assets_with_volume = []
            
            # Ambil sample untuk cek volume (max 50 untuk performance)
            sample_size = min(50, len(filtered_markets))
            markets_to_check = filtered_markets[:sample_size]
            
            for symbol in markets_to_check:
                try:
                    ticker = self.exchange.fetch_ticker(symbol)
                    volume = ticker.get('quoteVolume', 0) or ticker.get('baseVolume', 0)
                    assets_with_volume.append((symbol, volume))
                except:
                    assets_with_volume.append((symbol, 0))
                    continue
            
            # Sort berdasarkan volume (descending)
            assets_with_volume.sort(key=lambda x: x[1], reverse=True)
            
            # Prioritaskan coin utama
            major_coins = [
                'BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'XRP/USDT', 'ADA/USDT',
                'SOL/USDT', 'DOT/USDT', 'DOGE/USDT', 'AVAX/USDT', 'MATIC/USDT',
                'LTC/USDT', 'LINK/USDT', 'ATOM/USDT', 'XLM/USDT', 'BCH/USDT'
            ]
            
            # Tambahkan major coins dulu
            result = []
            for coin in major_coins:
                # Cari semua variasi dari major coin
                coin_variations = [
                    coin,
                    coin.replace('/USDT', ':USDT'),
                    coin.replace('/USDT', '-USDT'),
                    f"{coin.split('/')[0]}/USDT:USDT",
                    f"{coin.split('/')[0]}-USDT"
                ]
                
                for variation in coin_variations:
                    if variation in filtered_markets and variation not in result:
                        result.append(variation)
                        break
            
            # Tambahkan sisanya berdasarkan volume
            for symbol, _ in assets_with_volume:
                if symbol not in result and len(result) < limit:
                    result.append(symbol)
            
            # Jika masih kurang, tambahkan dari filtered_markets
            if len(result) < limit:
                for symbol in filtered_markets:
                    if symbol not in result and len(result) < limit:
                        result.append(symbol)
            
            # Format sebagai list of dict untuk konsistensi - TANPA 'type'
            formatted_result = []
            for symbol in result:
                # Extract base name
                base_name = symbol.split('/')[0] if '/' in symbol else symbol.split(':')[0]
                formatted_result.append({
                    'symbol': symbol,
                    'name': base_name,
                    'exchange': self.exchange_id
                })
            
            logger.info(f"✅ CCXT returning {len(formatted_result)} popular assets (UNIVERSAL)")
            if formatted_result:
                logger.info(f"   Top 5: {[item['symbol'] for item in formatted_result[:5]]}")
            return formatted_result[:limit]
            
        except Exception as e:
            logger.error(f"Error getting popular assets from {self.exchange_id}: {str(e)}")
            return self._get_fallback_major_coins(limit)

    def _get_fallback_major_coins(self, limit):
        """Fallback major coins - UNIVERSAL"""
        major_pairs = [
            'BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'XRP/USDT', 'ADA/USDT',
            'SOL/USDT', 'DOT/USDT', 'DOGE/USDT', 'AVAX/USDT', 'MATIC/USDT',
            'LTC/USDT', 'LINK/USDT', 'ATOM/USDT', 'XLM/USDT', 'BCH/USDT',
            'BTC/USDT:USDT', 'ETH/USDT:USDT', 'BNB/USDT:USDT',
            'XRP/USDT:USDT', 'ADA/USDT:USDT', 'SOL/USDT:USDT',
            'DOT/USDT:USDT', 'DOGE/USDT:USDT', 'AVAX/USDT:USDT', 'MATIC/USDT:USDT'
        ]
        
        formatted_result = []
        for symbol in major_pairs[:limit]:
            base_name = symbol.split('/')[0] if '/' in symbol else symbol.split(':')[0]
            formatted_result.append({
                'symbol': symbol,
                'name': base_name,
                'exchange': self.exchange_id
            })
        
        return formatted_result[:limit]

    def _get_alternative_symbols(self, symbol):
        """Dapatkan alternatif simbol untuk dicoba"""
        alt_symbols = [symbol]
        
        # Format asli
        alt_symbols.append(symbol)
        
        # Hapus futures marker
        if ':USDT' in symbol:
            alt_symbols.append(symbol.replace(':USDT', '/USDT'))
            alt_symbols.append(symbol.replace(':USDT', '-USDT'))
        
        # Ganti separator
        if '/USDT' in symbol:
            alt_symbols.append(symbol.replace('/USDT', ':USDT'))
            alt_symbols.append(symbol.replace('/USDT', '-USDT'))
        
        # Hapus duplikat
        return list(dict.fromkeys(alt_symbols))

# =============================================
# ENHANCED YFINANCE DATA PROVIDER - UNIVERSAL
# =============================================

class EnhancedYFinanceDataProvider(EnhancedDataProvider):
    """Enhanced Yahoo Finance provider - UNIVERSAL"""
    
    def __init__(self):
        super().__init__()

    def get_ohlcv(self, symbol, timeframe='1h', limit=200):
        """Get OHLCV from Yahoo Finance - UNIVERSAL"""
        def fetch_yfinance_data():
            try:
                # Convert symbol ke format YFinance
                yf_symbol = self._convert_to_yfinance_symbol(symbol)
                
                interval_map = {'1h': '1h', '4h': '4h', '1d': '1d', '1w': '1wk'}
                interval = interval_map.get(timeframe, '1d')
                
                if interval == '1h':
                    period = '2mo' if limit > 30 else '5d'
                elif interval == '1d':
                    period = '1y' if limit > 100 else '6mo'
                else:
                    period = '1y'
                
                ticker = yf.Ticker(yf_symbol)
                df = ticker.history(period=period, interval=interval)
                
                if df.empty:
                    raise ValueError(f"No data returned from Yahoo Finance for {yf_symbol}")
                
                if len(df) > limit:
                    df = df.tail(limit)
                
                df.reset_index(inplace=True)
                df.columns = [col.lower() for col in df.columns]
                if 'date' in df.columns:
                    df.rename(columns={'date': 'timestamp'}, inplace=True)
                elif 'datetime' in df.columns:
                    df.rename(columns={'datetime': 'timestamp'}, inplace=True)
                
                df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
                
                # 🚨 BUANG BAR HARGA 100
                if 'close' in df.columns:
                    mask_100 = abs(df['close'] - 100.0) < 0.001
                    count_100 = mask_100.sum()
                    if count_100 > 0:
                        df = df[~mask_100].copy()
                        logger.warning(f"⚠️ Removed {count_100} bars with price 100 for {symbol}")
                
                # Validasi data
                is_valid, validation_msg = self.validate_market_data(df, symbol)
                if not is_valid:
                    logger.warning(f"YFinance data validation failed: {symbol}")
                
                return df
                
            except Exception as e:
                logger.error(f"YFinance error for {symbol}: {str(e)}")
                raise

        return self._safe_api_call(fetch_yfinance_data)

    def get_ticker(self, symbol):
        """Get ticker data from Yahoo Finance - UNIVERSAL"""
        def fetch_ticker():
            try:
                # Convert symbol ke format YFinance
                yf_symbol = self._convert_to_yfinance_symbol(symbol)
                
                ticker = yf.Ticker(yf_symbol)
                info = ticker.info
                history = ticker.history(period='1d')
                
                if not history.empty:
                    last_price = history['Close'].iloc[-1]
                    volume = history['Volume'].iloc[-1] if 'Volume' in history.columns else 0
                else:
                    last_price = info.get('currentPrice', info.get('regularMarketPrice', 0))
                    volume = info.get('volume', 0)
                
                if last_price <= 0:
                    raise ValueError(f"Invalid price from YFinance: {last_price}")
                
                # 🚨 Cek harga 100
                if abs(last_price - 100.0) < 0.001:
                    raise ValueError(f"Suspicious price 100 from YFinance")
                
                return {
                    'last': last_price,
                    'volume': volume,
                    'high': info.get('dayHigh', 0),
                    'low': info.get('dayLow', 0),
                    'market_cap': info.get('marketCap', 0),
                    'symbol': symbol
                }
            except Exception as e:
                logger.error(f"YFinance ticker error: {str(e)}")
                raise
        
        return self._safe_api_call(fetch_ticker)

    def get_popular_assets(self, limit=100, **kwargs):
        """Get popular assets - UNIVERSAL"""
        try:
            # Gabungkan semua jenis aset
            all_assets = []
            
            # Crypto
            crypto_assets = self._get_crypto_assets(limit)
            all_assets.extend(crypto_assets)
            
            # Forex
            forex_assets = self._get_forex_assets(limit)
            all_assets.extend(forex_assets)
            
            # US Stocks
            stock_assets = self._get_us_stock_assets(limit)
            all_assets.extend(stock_assets)
            
            # Indonesian Stocks
            id_stock_assets = self._get_id_stock_assets(limit)
            all_assets.extend(id_stock_assets)
            
            # Potong sesuai limit
            result = all_assets[:limit]
            
            logger.info(f"📈 YFinance returning {len(result)} popular assets (UNIVERSAL)")
            return result
            
        except Exception as e:
            logger.error(f"Error getting popular assets: {str(e)}")
            return self._get_fallback_assets(limit)

    def _convert_to_yfinance_symbol(self, symbol):
        """Convert symbol ke format YFinance"""
        if '/USDT' in symbol:
            return symbol.replace('/USDT', '-USD')
        elif ':USDT' in symbol:
            return symbol.replace(':USDT', '-USD')
        elif '/USD' in symbol and '=X' not in symbol:
            return symbol.replace('/USD', '-USD')
        else:
            return symbol

    def _get_crypto_assets(self, limit):
        """Get crypto assets"""
        crypto_pairs = [
            'BTC-USD', 'ETH-USD', 'BNB-USD', 'XRP-USD', 'ADA-USD',
            'SOL-USD', 'DOT-USD', 'DOGE-USD', 'AVAX-USD', 'MATIC-USD',
            'LTC-USD', 'LINK-USD', 'ATOM-USD', 'XLM-USD', 'BCH-USD',
            'ETC-USD', 'FIL-USD', 'THETA-USD', 'EOS-USD', 'XTZ-USD'
        ]
        
        result = []
        for symbol in crypto_pairs[:limit]:
            result.append({
                'symbol': symbol,
                'name': symbol.replace('-USD', ''),
                'category': 'crypto'
            })
        
        return result

    def _get_forex_assets(self, limit):
        """Get forex assets"""
        forex_pairs = [
            'EURUSD=X', 'USDJPY=X', 'GBPUSD=X', 'AUDUSD=X', 'USDCAD=X',
            'USDCHF=X', 'NZDUSD=X', 'EURGBP=X', 'EURJPY=X', 'GBPJPY=X'
        ]
        
        result = []
        for symbol in forex_pairs[:limit]:
            pair = symbol.replace('=X', '')
            result.append({
                'symbol': symbol,
                'name': pair,
                'category': 'forex'
            })
        
        return result

    def _get_us_stock_assets(self, limit):
        """Get US stock assets"""
        us_stocks = [
            'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA', 'META', 'NVDA', 'NFLX',
            'JPM', 'V', 'JNJ', 'WMT', 'PG', 'MA', 'UNH', 'HD', 'DIS'
        ]
        
        result = []
        for symbol in us_stocks[:limit]:
            result.append({
                'symbol': symbol,
                'name': symbol,
                'category': 'stock'
            })
        
        return result

    def _get_id_stock_assets(self, limit):
        """Get Indonesian stock assets"""
        id_stocks = [
            'BBCA.JK', 'BBRI.JK', 'BMRI.JK', 'BBNI.JK', 'BNGA.JK',
            'TLKM.JK', 'ASII.JK', 'UNVR.JK', 'ICBP.JK', 'INDF.JK'
        ]
        
        result = []
        for symbol in id_stocks[:limit]:
            result.append({
                'symbol': symbol,
                'name': symbol.replace('.JK', ''),
                'category': 'stock'
            })
        
        return result

    def _get_fallback_assets(self, limit):
        """Fallback assets"""
        fallback = [
            {'symbol': 'BTC-USD', 'name': 'Bitcoin', 'category': 'crypto'},
            {'symbol': 'ETH-USD', 'name': 'Ethereum', 'category': 'crypto'},
            {'symbol': 'AAPL', 'name': 'Apple', 'category': 'stock'},
            {'symbol': 'EURUSD=X', 'name': 'EUR/USD', 'category': 'forex'},
            {'symbol': 'BBCA.JK', 'name': 'Bank BCA', 'category': 'stock'}
        ]
        
        return fallback[:limit]

# =============================================
# UNIFIED SMART DATA PROVIDER - UNIVERSAL
# =============================================

class UnifiedDataProvider(EnhancedDataProvider):
    """Provider terpadu dengan auto-fallback yang benar-benar bekerja - UNIVERSAL"""
    
    def __init__(self, exchange_id='binance', api_key='', secret=''):
        super().__init__()
        self.exchange_id = exchange_id
        
        # Setup primary provider (CCXT Universal)
        self.primary_provider = EnhancedCCXTDataProvider(
            exchange_id=exchange_id,
            api_key=api_key,
            secret=secret
        )
        
        # Setup fallback provider (YFinance Universal)
        self.fallback_provider = EnhancedYFinanceDataProvider()
        
        logger.info(f"🚀 UnifiedDataProvider ready | Exchange: {exchange_id}")
    
    def get_ohlcv(self, symbol, timeframe='1h', limit=200):
        """Get OHLCV data dengan auto-fallback - UNIVERSAL"""
        logger.info(f"📊 Getting OHLCV for {symbol} (limit: {limit})")
        
        # Coba primary provider dulu
        try:
            result = self.primary_provider.get_ohlcv(symbol, timeframe, limit)
            
            if result is not None and not result.empty:
                # 🚨 BUANG BAR HARGA 100
                if 'close' in result.columns:
                    mask_100 = abs(result['close'] - 100.0) < 0.001
                    count_100 = mask_100.sum()
                    
                    if count_100 > 0:
                        result = result[~mask_100].copy()
                        logger.warning(f"🚨 Removed {count_100} bars with price 100 for {symbol}")
                
                # Validasi
                if len(result) >= 20:
                    is_valid, msg = self.validate_market_data(result, symbol)
                    if is_valid:
                        logger.info(f"✅ Valid data from primary provider")
                        return result
        except Exception as e:
            logger.warning(f"⚠️ Primary provider failed: {e}")
        
        # Fallback ke YFinance
        logger.warning("🔄 AUTO-FALLBACK: Switching to YFinance...")
        
        try:
            result = self.fallback_provider.get_ohlcv(symbol, timeframe, limit)
            
            if result is not None and not result.empty:
                # 🚨 BUANG BAR HARGA 100
                if 'close' in result.columns:
                    mask_100 = abs(result['close'] - 100.0) < 0.001
                    count_100 = mask_100.sum()
                    if count_100 > 0:
                        result = result[~mask_100].copy()
                        logger.warning(f"🚨 Removed {count_100} bars with price 100 for {symbol}")
                
                # Validasi
                if len(result) >= 20:
                    is_valid, msg = self.validate_market_data(result, symbol)
                    if is_valid:
                        logger.info(f"✅ Valid data from fallback provider")
                        return result
        except Exception as e:
            logger.warning(f"⚠️ Fallback provider failed: {e}")
        
        # Semua gagal
        logger.error(f"🚨 ALL DATA SOURCES FAILED for {symbol}. Returning EMPTY DataFrame.")
        return pd.DataFrame()
    
    def get_ticker(self, symbol):
        """Get ticker data dengan auto-fallback - UNIVERSAL"""
        logger.debug(f"📈 Getting ticker for {symbol}")
        
        # Coba primary provider
        try:
            result = self.primary_provider.get_ticker(symbol)
            if result and result.get('last', 0) > 0 and abs(result.get('last', 0) - 100.0) > 0.001:
                return result
        except:
            pass
        
        # Fallback ke YFinance
        try:
            result = self.fallback_provider.get_ticker(symbol)
            if result and result.get('last', 0) > 0 and abs(result.get('last', 0) - 100.0) > 0.001:
                return result
        except:
            pass
        
        # Emergency fallback
        return {
            'last': self._estimate_realistic_price(symbol),
            'volume': 10000,
            'symbol': symbol,
            'timestamp': datetime.now()
        }
    
    def get_popular_assets(self, limit=100, **kwargs):
        """Get popular assets - UNIVERSAL"""
        logger.info(f"📋 Getting {limit} popular assets from {self.exchange_id}")
        
        # Coba primary provider
        try:
            assets = self.primary_provider.get_popular_assets(limit)
            if assets and len(assets) > 0:
                logger.info(f"✅ Found {len(assets)} assets from primary provider")
                return assets
        except Exception as e:
            logger.warning(f"⚠️ Primary provider failed: {e}")
        
        # Fallback ke YFinance
        try:
            assets = self.fallback_provider.get_popular_assets(limit)
            if assets and len(assets) > 0:
                logger.info(f"✅ Found {len(assets)} assets from fallback provider")
                return assets
        except Exception as e:
            logger.warning(f"⚠️ Fallback provider failed: {e}")
        
        # Emergency fallback
        return [
            {'symbol': 'BTC/USDT', 'name': 'Bitcoin', 'exchange': self.exchange_id},
            {'symbol': 'ETH/USDT', 'name': 'Ethereum', 'exchange': self.exchange_id},
            {'symbol': 'BNB/USDT', 'name': 'Binance Coin', 'exchange': self.exchange_id}
        ][:limit]
    
    def get_health_metrics(self):
        """Get health metrics"""
        base_metrics = super().get_health_metrics()
        
        base_metrics.update({
            'exchange': self.exchange_id,
            'primary_provider': self.primary_provider.__class__.__name__,
            'fallback_provider': self.fallback_provider.__class__.__name__
        })
        
        return base_metrics

# =============================================
# DATA PROVIDER FACTORY - DIPERBAIKI
# =============================================

class DataProviderFactory:
    """Factory untuk membuat data provider - DIPERBAIKI"""
    
    @staticmethod
    def create_provider(provider_type, **kwargs):
        """Create data provider berdasarkan type"""
        
        if provider_type == 'universal':
            # 🆕 PROVIDER UNIVERSAL (REKOMENDASI UTAMA)
            exchange_id = kwargs.get('exchange_id', 'binance')
            api_key = kwargs.get('api_key', '')
            secret = kwargs.get('secret', '')
            return UnifiedDataProvider(
                exchange_id=exchange_id,
                api_key=api_key,
                secret=secret
            )
            
        elif provider_type == 'ccxt':
            # CCXT Universal (tanpa pemisahan spot/future)
            exchange_id = kwargs.get('exchange_id', 'binance')
            api_key = kwargs.get('api_key', '')
            secret = kwargs.get('secret', '')
            
            return EnhancedCCXTDataProvider(
                exchange_id=exchange_id,
                api_key=api_key,
                secret=secret
            )
                
        elif provider_type == 'yfinance':
            # YFinance Universal
            return EnhancedYFinanceDataProvider()
            
        elif provider_type == 'alphavantage':
            api_key = kwargs.get('api_key', 'demo')
            return AlphaVantageProvider(api_key=api_key)
        
        elif provider_type == 'robust':
            # Robust fetcher dengan universal providers
            primary_type = kwargs.get('primary_type', 'ccxt')
            secondary_type = kwargs.get('secondary_type', 'yfinance')
            
            primary_provider = DataProviderFactory.create_provider(primary_type, **kwargs)
            secondary_provider = DataProviderFactory.create_provider(secondary_type, **kwargs)
            
            return RobustDataFetcher(
                primary_provider=primary_provider,
                secondary_provider=secondary_provider,
                synthetic_fallback=kwargs.get('synthetic_fallback', True)
            )
            
        else:
            raise ValueError(f"Unknown provider type: {provider_type}")

# =============================================
# DYNAMIC DATA PROVIDER - DIPERBAIKI
# =============================================

class DynamicDataProvider(EnhancedDataProvider):
    """Dynamic data provider dengan fallback yang benar - UNIVERSAL"""
    
    def __init__(self, exchange_id='binance', api_key='', secret=''):
        super().__init__()
        self.exchange_id = exchange_id
        
        # List exchange untuk dicoba secara berurutan
        self.exchange_list = ['binance', 'kucoin', 'bybit', 'okx']
        self.current_exchange_idx = 0
        
        # Setup providers
        self._setup_providers(exchange_id, api_key, secret)
        
        logger.info(f"DynamicDataProvider initialized for exchange: {exchange_id}")

    def _setup_providers(self, exchange_id, api_key, secret):
        """Setup providers dengan sistem fallback yang benar"""
        
        try:
            # Setup CCXT provider universal
            self.primary_provider = EnhancedCCXTDataProvider(
                exchange_id=exchange_id,
                api_key=api_key,
                secret=secret
            )
            
            # Setup YFinance fallback
            self.fallback_provider = EnhancedYFinanceDataProvider()
            
            logger.info(f"✅ Providers setup: {self.primary_provider.__class__.__name__} + YFinance")
            
        except Exception as e:
            logger.error(f"❌ Failed to setup CCXT provider: {e}")
            # Fallback ke YFinance saja
            self.primary_provider = EnhancedYFinanceDataProvider()
            self.fallback_provider = EnhancedYFinanceDataProvider()
            logger.info(f"⚠️ Using YFinance as primary (CCXT failed)")

    def get_ohlcv(self, symbol, timeframe='1h', limit=200):
        """Get OHLCV data dengan auto-fallback"""
        return self._execute_with_fallback('get_ohlcv', symbol, timeframe, limit)

    def get_ticker(self, symbol):
        """Get ticker data dengan auto-fallback"""
        return self._execute_with_fallback('get_ticker', symbol)

    def get_popular_assets(self, limit=100, **kwargs):
        """Get popular assets dengan auto-fallback"""
        return self._execute_with_fallback('get_popular_assets', limit=limit)

    def _execute_with_fallback(self, method_name, *args, **kwargs):
        """Execute method dengan fallback otomatis"""
        try:
            # Coba primary provider
            method = getattr(self.primary_provider, method_name)
            result = method(*args, **kwargs)
            
            # Validasi result
            if self._validate_result(result, method_name):
                return result
            else:
                raise ValueError("Invalid data from primary provider")
                
        except Exception as e:
            logger.warning(f"⚠️ Primary provider failed for {method_name}: {e}")
            
            # Fallback ke YFinance
            try:
                method = getattr(self.fallback_provider, method_name)
                result = method(*args, **kwargs)
                
                if self._validate_result(result, method_name):
                    logger.info(f"✅ Fallback successful for {method_name}")
                    return result
                else:
                    raise ValueError("Invalid data from fallback provider")
                    
            except Exception as fallback_e:
                logger.error(f"❌ Fallback also failed: {fallback_e}")
                
                # Emergency fallback
                if method_name == 'get_ohlcv':
                    return pd.DataFrame()
                elif method_name == 'get_ticker':
                    return {
                        'last': self._estimate_realistic_price(kwargs.get('symbol', args[0] if args else 'BTC/USDT')),
                        'volume': 10000,
                        'symbol': kwargs.get('symbol', args[0] if args else 'BTC/USDT')
                    }
                elif method_name == 'get_popular_assets':
                    return [
                        {'symbol': 'BTC/USDT', 'name': 'Bitcoin', 'exchange': self.exchange_id},
                        {'symbol': 'ETH/USDT', 'name': 'Ethereum', 'exchange': self.exchange_id}
                    ]
                return None

    def _validate_result(self, result, method_name):
        """Validasi hasil"""
        if result is None:
            return False
            
        if method_name == 'get_ohlcv':
            if not isinstance(result, pd.DataFrame) or result.empty:
                return False
            
            if 'close' in result.columns and len(result) > 0:
                has_100 = (abs(result['close'] - 100.0) < 0.001).any()
                if has_100:
                    logger.warning(f"⚠️ Rejecting result with price 100")
                    return False
            
            return True
        elif method_name == 'get_ticker':
            return isinstance(result, dict) and result.get('last', 0) > 0 and abs(result.get('last', 0) - 100.0) > 0.001
        elif method_name == 'get_popular_assets':
            return isinstance(result, list) and len(result) > 0
            
        return False

# =============================================
# TEST FUNCTIONS - DIPERBAIKI
# =============================================

def test_universal_provider():
    """Test Universal Provider"""
    print("\n🧪 Testing Universal Provider...")
    
    # Test 1: Universal CCXT Provider
    print("\n1. Testing Universal CCXT Provider:")
    provider = EnhancedCCXTDataProvider(exchange_id='binance')
    
    assets = provider.get_popular_assets(10)
    print(f"✅ Popular assets: {len(assets)} found")
    for i, asset in enumerate(assets[:5]):
        print(f"   {i+1}. {asset['symbol']} ({asset.get('name', 'N/A')})")
    
    # Test 2: Unified Provider
    print("\n2. Testing Unified Provider:")
    unified = UnifiedDataProvider(exchange_id='binance')
    
    # Test OHLCV
    try:
        data = unified.get_ohlcv("BTC/USDT", '1h', 20)
        if not data.empty:
            print(f"✅ OHLCV data: {len(data)} rows")
            print(f"   Latest price: {data['close'].iloc[-1] if len(data) > 0 else 'N/A'}")
        else:
            print("❌ No OHLCV data")
    except Exception as e:
        print(f"❌ OHLCV error: {e}")
    
    # Test 3: Factory
    print("\n3. Testing Factory:")
    factory_provider = DataProviderFactory.create_provider('universal', exchange_id='binance')
    assets = factory_provider.get_popular_assets(5)
    print(f"✅ Factory assets: {len(assets)} found")
    for asset in assets:
        print(f"   - {asset['symbol']}")

if __name__ == "__main__":
    print("=" * 60)
    print("UNIVERSAL DATA PROVIDER TEST SUITE")
    print("=" * 60)
    
    # Run tests
    test_universal_provider()
    
    print("\n" + "=" * 60)
    print("TESTS COMPLETED")
    print("=" * 60)
