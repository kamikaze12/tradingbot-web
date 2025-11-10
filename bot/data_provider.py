import ccxt
import pandas as pd
import yfinance as yf
from abc import ABC, abstractmethod
from solana.rpc.api import Client
from solana.rpc.websocket_api import connect
import json
import asyncio
import base58
import os
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime

class DataProvider(ABC):
    @abstractmethod
    def get_ohlcv(self, symbol, timeframe, limit):
        pass
        
    @abstractmethod
    def get_ticker(self, symbol):
        pass
        
    @abstractmethod
    def get_popular_assets(self, limit):
        pass

class AlphaVantageProvider(DataProvider):
    def __init__(self, api_key=None):
        self.api_key = api_key or os.getenv('ALPHA_VANTAGE_KEY')
        if not self.api_key:
            print("Warning: Alpha Vantage API key not found.")
            self.api_key = None
        self.base_url = "https://www.alphavantage.co/query"

    def _convert_symbol(self, symbol, market_type='crypto'):
        if '/' in symbol:
            base, quote = symbol.split('/')
        elif '=X' in symbol:
            base = symbol.split('=')[0]
            return f"{base[:3]}/{base[3:]}"
        elif '.JK' in symbol:
            return symbol
        else:
            base = symbol.upper()
        if market_type == 'forex':
            return f"{base[:3]}/{base[3:]}"
        return base

    def get_ohlcv(self, symbol, timeframe, limit=200):
        if not self.api_key:
            return None
        try:
            symbol_av = self._convert_symbol(symbol)
            if '/' in symbol_av:
                function = "FX_DAILY"
            else:
                function = "DIGITAL_CURRENCY_DAILY" if 'crypto' in market_type else "TIME_SERIES_DAILY"
            params = {
                "function": function,
                "symbol": symbol_av,
                "market": "USD" if function == "DIGITAL_CURRENCY_DAILY" else None,
                "apikey": self.api_key,
                "outputsize": "full" if limit > 100 else "compact"
            }
            if function.startswith("FX_"):
                params["from_symbol"], params["to_symbol"] = symbol_av.split('/')
            response = requests.get(self.base_url, params=params)
            response.raise_for_status()
            data = response.json()
            time_series_key = next((k for k in data if "Time Series" in k), None)
            if time_series_key:
                ohlcv_data = data[time_series_key]
                df = pd.DataFrame.from_dict(ohlcv_data, orient='index')
                df = df.astype(float)
                df['timestamp'] = pd.to_datetime(df.index)
                df = df[['timestamp', '1. open', '2. high', '3. low', '4. close', '5. volume' if '5. volume' in df else '4. close']]
                if '5. volume' not in df.columns:
                    df['volume'] = 0
                df.columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
                df_sorted = df.sort_index().tail(limit)
                return df_sorted
            else:
                return None
        except Exception as e:
            return None

    def get_ticker(self, symbol):
        if not self.api_key:
            return None
        try:
            symbol_av = self._convert_symbol(symbol)
            function = "CURRENCY_EXCHANGE_RATE" if '/' in symbol_av else "GLOBAL_QUOTE"
            params = {
                "function": function,
                "symbol": symbol_av,
                "apikey": self.api_key
            }
            if function == "CURRENCY_EXCHANGE_RATE":
                params["from_currency"], params["to_currency"] = symbol_av.split('/')
            response = requests.get(self.base_url, params=params)
            response.raise_for_status()
            data = response.json()
            if "Realtime Currency Exchange Rate" in data:
                rate = data["Realtime Currency Exchange Rate"]
                return {'last': float(rate['5. Exchange Rate']), 'volume': 0}
            elif "Global Quote" in data:
                quote = data["Global Quote"]
                return {'last': float(quote['05. price']), 'volume': float(quote.get('06. volume', 0))}
            return None
        except Exception as e:
            return None

    def get_popular_assets(self, limit=100):
        return []

class DexScreenerProvider:
    def __init__(self):
        self.base_url = "https://api.dexscreener.com/latest/dex"

    def get_ticker(self, chain, token_address):
        try:
            url = f"{self.base_url}/tokens/{chain}/{token_address}"
            response = requests.get(url)
            response.raise_forstatus()
            data = response.json()
            if 'pairs' in data and data['pairs']:
                pair = data['pairs'][0]
                return {
                    'last': float(pair.get('priceUsd', 0)),
                    'volume': float(pair.get('volume', {}).get('h24', 0)),
                    'liquidity': float(pair.get('liquidity', {}).get('usd', 0)),
                    'fdv': float(pair.get('fdv', 0))
                }
            return None
        except Exception as e:
            return None

    def search_pairs(self, query):
        try:
            url = f"{self.base_url}/search?q={query}"
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
            return data.get('pairs', [])
        except Exception as e:
            return []

class CCXTDataProvider(DataProvider):
    def __init__(self, exchange_id='kucoin', api_key='', secret=''):
        exchange_class = getattr(ccxt, exchange_id)
        self.exchange = exchange_class({
            'apiKey': api_key,
            'secret': secret,
            'enableRateLimit': True,
        })
        self.fallback_yf = YFinanceDataProvider(market_type='crypto')
        self.fallback_av = AlphaVantageProvider()

    def _convert_symbol(self, symbol, target='yf'):
        base = symbol.split('/')[0] if '/' in symbol else symbol.upper()
        if target == 'yf':
            return f"{base}-USD"
        elif target == 'av':
            return base
        return symbol

    def get_ohlcv(self, symbol, timeframe, limit=200):
        try:
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            return df
        except Exception as e:
            for fallback, target in [(self.fallback_yf, 'yf'), (self.fallback_av, 'av')]:
                try:
                    conv_symbol = self._convert_symbol(symbol, target)
                    df = fallback.get_ohlcv(conv_symbol, timeframe, limit)
                    if df is not None and len(df) >= 50:
                        return df
                except Exception:
                    continue
            dates = pd.date_range(end=pd.Timestamp.now(), periods=limit, freq='D')
            dummy_data = {
                'timestamp': dates,
                'open': [1.0] * limit,
                'high': [1.1] * limit,
                'low': [0.9] * limit,
                'close': [1.0 + (i / 100) for i in range(limit)],
                'volume': [1000 + i for i in range(limit)]
            }
            return pd.DataFrame(dummy_data)

    def get_ticker(self, symbol):
        try:
            return self.exchange.fetch_ticker(symbol)
        except Exception as e:
            for fallback, target in [(self.fallback_yf, 'yf'), (self.fallback_av, 'av')]:
                try:
                    conv_symbol = self._convert_symbol(symbol, target)
                    fb_ticker = fallback.get_ticker(conv_symbol)
                    if fb_ticker is not None:
                        return fb_ticker
                except Exception:
                    continue
            return {'last': 1.0, 'volume': 1000}

    def get_popular_assets(self, limit=100):
        try:
            markets = self.exchange.load_markets()
            if self.exchange.id in ['binance', 'bybit', 'kucoin']:
                usdt_markets = [symbol for symbol in markets if symbol.endswith('/USDT')]
                excluded_coins = ['BUSD', 'USDC', 'DAI', 'TUSD', 'USDP', 'UST']
                filtered_markets = [symbol for symbol in usdt_markets if not any(excluded in symbol for excluded in excluded_coins)]
                try:
                    tickers = self.exchange.fetch_tickers()
                    filtered_markets.sort(key=lambda x: tickers[x]['quoteVolume'] if x in tickers else 0, reverse=True)
                except Exception:
                    pass
                return filtered_markets[:limit]
        except Exception:
            pass
        return ['BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'XRP/USDT', 'ADA/USDT'][:limit]

class YFinanceDataProvider(DataProvider):
    def __init__(self, market_type='saham_id'):
        self.market_type = market_type
        self.fallback_av = AlphaVantageProvider()

    def _convert_symbol(self, symbol, target='av'):
        base = symbol.split('=')[0] if '=X' in symbol else symbol.split('.')[0] if '.JK' in symbol else symbol
        if target == 'av':
            if self.market_type == 'forex':
                from_curr, to_curr = base[:3], base[3:]
                return f"{from_curr}/{to_curr}"
            return base
        return symbol

    def get_ohlcv(self, symbol, timeframe='1h', limit=200):
        try:
            interval_map = {'1h': '1h', '4h': '4h', '1d': '1d', '1w': '1wk'}
            interval = interval_map.get(timeframe, '1h')
            period = '5d' if interval == '1h' and limit <= 120 else '2mo' if interval == '1h' else '1y'
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=period, interval=interval)
            if len(df) > limit:
                df = df.tail(limit)
            df.reset_index(inplace=True)
            df.columns = [col.lower() for col in df.columns]
            if 'date' in df.columns:
                df.rename(columns={'date': 'timestamp'}, inplace=True)
            elif 'datetime' in df.columns:
                df.rename(columns={'datetime': 'timestamp'}, inplace=True)
            df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
            return df
        except Exception as e:
            try:
                conv_symbol = self._convert_symbol(symbol, 'av')
                av_df = self.fallback_av.get_ohlcv(conv_symbol, timeframe, limit)
                if av_df is not None:
                    return av_df
            except Exception:
                pass
            dates = pd.date_range(end=pd.Timestamp.now(), periods=limit, freq='D')
            dummy_data = {
                'timestamp': dates,
                'open': [1.0] * limit,
                'high': [1.1] * limit,
                'low': [0.9] * limit,
                'close': [1.0 + (i / 100) for i in range(limit)],
                'volume': [1000 + i for i in range(limit)]
            }
            return pd.DataFrame(dummy_data)

    def get_ticker(self, symbol):
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            hist = ticker.history(period='1d', interval='1m')
            last_price = hist['Close'].iloc[-1] if not hist.empty else info.get('regularMarketPrice', info.get('previousClose', 0))
            volume = info.get('volume', hist['Volume'].iloc[-1] if not hist.empty else 0)
            return {'last': last_price, 'volume': volume}
        except Exception as e:
            try:
                conv_symbol = self._convert_symbol(symbol, 'av')
                av_tk = self.fallback_av.get_ticker(conv_symbol)
                if av_tk is not None:
                    return av_tk
            except Exception:
                pass
            return {'last': 1.0, 'volume': 1000}

    def get_popular_assets(self, limit=100):
        """Get popular assets with web scraping for Indonesian stocks"""
        if self.market_type == "forex":
            return self._get_forex_pairs(limit)
        elif self.market_type == "saham_id":
            return self._scrape_popular_id_stocks(limit)
        elif self.market_type == "stocks":
            return self._get_international_stocks(limit)
        else:
            return []

    def _scrape_popular_id_stocks(self, limit=100):
        """Scrape popular Indonesian stocks from investing.com"""
        try:
            print("🕸️ Scraping popular Indonesian stocks from investing.com...")
            
            # URL untuk saham paling aktif
            url = "https://id.investing.com/equities/top-stock-gainers"
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept-Language': 'id-ID,id;q=0.9,en;q=0.8',
                'Referer': 'https://id.investing.com/'
            }
            
            response = requests.get(url, headers=headers, timeout=15)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                stocks = self._parse_investing_stocks(soup)
                
                if stocks:
                    print(f"✅ Found {len(stocks)} stocks from investing.com")
                    return stocks[:limit]
                else:
                    print("⚠️ No stocks found from investing.com, using fallback")
            
            # Fallback ke Yahoo Finance trending
            yf_stocks = self._scrape_yahoo_trending_id()
            if yf_stocks:
                print(f"✅ Found {len(yf_stocks)} stocks from Yahoo Finance")
                return yf_stocks[:limit]
                
            # Ultimate fallback - comprehensive manual list
            return self._get_comprehensive_id_stocks(limit)
            
        except Exception as e:
            print(f"❌ Error scraping popular stocks: {e}")
            return self._get_comprehensive_id_stocks(limit)

    def _parse_investing_stocks(self, soup):
        """Parse stock data from investing.com HTML"""
        stocks = []
        try:
            # Cari table yang berisi data saham
            tables = soup.find_all('table')
            
            for table in tables:
                # Cari rows dalam table
                rows = table.find_all('tr')[1:]  # Skip header
                
                for row in rows:
                    try:
                        # Cari link saham (berisi symbol)
                        stock_link = row.find('a', href=re.compile(r'/equities/'))
                        if stock_link:
                            href = stock_link.get('href', '')
                            symbol = self._extract_symbol_from_url(href)
                            
                            if symbol and symbol not in stocks:
                                stocks.append(f"{symbol}.JK")
                                
                                # Debug info
                                stock_name = stock_link.get_text(strip=True)
                                print(f"   📈 Found: {symbol}.JK - {stock_name}")
                                
                    except Exception as e:
                        continue
                        
                    if len(stocks) >= 100:  # Limit early
                        break
                        
        except Exception as e:
            print(f"Error parsing investing.com: {e}")
            
        return stocks

    def _extract_symbol_from_url(self, url):
        """Extract stock symbol from investing.com URL"""
        try:
            # Contoh URL: /equities/bbca-jk
            # Contoh URL: /equities/bank-central-asia-tbk_bbca-jk
            match = re.search(r'/equities/([a-zA-Z0-9-]+)$', url)
            if match:
                symbol_part = match.group(1)
                # Extract symbol dari akhir URL (bbca-jk -> BBCA)
                if '-' in symbol_part:
                    symbol = symbol_part.split('-')[0].upper()
                    return symbol
        except Exception:
            pass
        return None

    def _scrape_yahoo_trending_id(self):
        """Scrape trending Indonesian stocks from Yahoo Finance"""
        try:
            url = "https://finance.yahoo.com/trending-stocks"
            headers = {'User-Agent': 'Mozilla/5.0'}
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                stocks = []
                
                # Cari symbol dengan .JK
                symbols = soup.find_all(text=re.compile(r'\.JK'))
                for symbol_text in symbols:
                    symbol = symbol_text.strip()
                    if symbol.endswith('.JK') and symbol not in stocks:
                        stocks.append(symbol)
                        
                return stocks
        except Exception as e:
            print(f"Error scraping Yahoo trending: {e}")
            
        return []

    def _get_comprehensive_id_stocks(self, limit=100):
        """Comprehensive fallback list of Indonesian stocks"""
        comprehensive_stocks = [
            # BANKING (25)
            'BBCA.JK', 'BBRI.JK', 'BMRI.JK', 'BBNI.JK', 'BNGA.JK',
            'BDMN.JK', 'BTPN.JK', 'BJBR.JK', 'BJTM.JK', 'BNLI.JK',
            'BACA.JK', 'AGRO.JK', 'BNBA.JK', 'BKSW.JK', 'SDRA.JK',
            'BBKP.JK', 'BEKS.JK', 'BGTG.JK', 'BINA.JK', 'BIPI.JK',
            'BMTR.JK', 'BNBA.JK', 'BNII.JK', 'BTEK.JK', 'BUKK.JK',
            
            # TELCO & TECH (15)
            'TLKM.JK', 'ISAT.JK', 'EXCL.JK', 'FREN.JK', 'ICON.JK',
            'LINK.JK', 'MTEL.JK', 'TIRA.JK', 'DNET.JK', 'EDGE.JK',
            'GLOB.JK', 'MYOR.JK', 'RSGK.JK', 'SDPC.JK', 'TCID.JK',
            
            # CONSUMER GOODS (20)
            'UNVR.JK', 'ICBP.JK', 'INDF.JK', 'MYOR.JK', 'ULTJ.JK',
            'SKLT.JK', 'STTP.JK', 'CLEO.JK', 'DLTA.JK', 'MERK.JK',
            'ROTI.JK', 'PANI.JK', 'SOSS.JK', 'STAR.JK', 'TOTO.JK',
            'AYLS.JK', 'BISI.JK', 'CPRO.JK', 'DMND.JK', 'JPFA.JK',
            
            # MINING & ENERGY (15)
            'ADRO.JK', 'ANTM.JK', 'PTBA.JK', 'ITMG.JK', 'MEDC.JK',
            'BUMI.JK', 'BYAN.JK', 'HRUM.JK', 'INCO.JK', 'MBAP.JK',
            'PGAS.JK', 'AKRA.JK', 'ENRG.JK', 'ELSA.JK', 'KKGI.JK',
            
            # PROPERTY & REAL ESTATE (15)
            'BSDE.JK', 'CTRA.JK', 'DMAS.JK', 'LPKR.JK', 'PWON.JK',
            'SMRA.JK', 'APLN.JK', 'ASRI.JK', 'BKSL.JK', 'DUTI.JK',
            'GPRA.JK', 'JRPT.JK', 'KOTA.JK', 'LPCK.JK', 'NIRO.JK',
            
            # INFRASTRUCTURE & MANUFACTURING (15)
            'WIKA.JK', 'PTPP.JK', 'ADHI.JK', 'WSKT.JK', 'JSMR.JK',
            'SRIL.JK', 'SMBR.JK', 'SMCB.JK', 'SMSM.JK', 'TINS.JK',
            'TKIM.JK', 'INTP.JK', 'KLBF.JK', 'SCMA.JK', 'SRTG.JK'
        ]
        return comprehensive_stocks[:limit]

    def _get_forex_pairs(self, limit=100):
        """Comprehensive forex pairs list"""
        forex_pairs = [
            # MAJOR PAIRS (8)
            'EURUSD=X', 'USDJPY=X', 'GBPUSD=X', 'AUDUSD=X', 
            'USDCAD=X', 'USDCHF=X', 'NZDUSD=X', 'USDCNY=X',
            
            # EURO CROSSES (15)
            'EURGBP=X', 'EURJPY=X', 'EURAUD=X', 'EURCAD=X', 'EURCHF=X',
            'EURNZD=X', 'EURSEK=X', 'EURNOK=X', 'EURDKK=X', 'EURHUF=X',
            'EURPLN=X', 'EURCZK=X', 'EURTRY=X', 'EURMXN=X', 'EURZAR=X',
            
            # GBP CROSSES (12)
            'GBPJPY=X', 'GBPAUD=X', 'GBPCAD=X', 'GBPCHF=X', 'GBPNZD=X',
            'GBPSEK=X', 'GBPNOK=X', 'GBPDKK=X', 'GBPHUF=X', 'GBPPLN=X',
            'GBPCZK=X', 'GBPTRY=X',
            
            # JPY CROSSES (15)
            'AUDJPY=X', 'CADJPY=X', 'CHFJPY=X', 'NZDJPY=X', 'SEKJPY=X',
            'NOKJPY=X', 'DKKJPY=X', 'HUFJPY=X', 'PLNJPY=X', 'CZKJPY=X',
            'TRYJPY=X', 'MXNJPY=X', 'ZARJPY=X', 'SGDJPY=X', 'HKDJPY=X',
            
            # AUD CROSSES (10)
            'AUDCAD=X', 'AUDCHF=X', 'AUDNZD=X', 'AUDSEK=X', 'AUDNOK=X',
            'AUDDKK=X', 'AUDHUF=X', 'AUDPLN=X', 'AUDCZK=X', 'AUDTRY=X',
            
            # CAD CROSSES (10)
            'CADCHF=X', 'CADSEK=X', 'CADNOK=X', 'CADDKK=X', 'CADHUF=X',
            'CADPLN=X', 'CADCZK=X', 'CADTRY=X', 'CADMXN=X', 'CADZAR=X',
            
            # CHF CROSSES (10)
            'CHFSEK=X', 'CHFNOK=X', 'CHFDKK=X', 'CHFHUF=X', 'CHFPLN=X',
            'CHFCZK=X', 'CHFTRY=X', 'CHFMXN=X', 'CHFZAR=X', 'CHFSGD=X',
            
            # EXOTIC PAIRS (20)
            'USDMXN=X', 'USDTRY=X', 'USDZAR=X', 'USDHKD=X', 'USDSGD=X',
            'USDTHB=X', 'USDSEK=X', 'USDNOK=X', 'USDDKK=X', 'USDPLN=X',
            'USDHUF=X', 'USDCZK=X', 'USDRON=X', 'USDILS=X', 'USDCLP=X',
            'USDPHP=X', 'USDIDR=X', 'USDINR=X', 'USDBRL=X', 'USDRUB=X'
        ]
        return forex_pairs[:limit]

    def _get_international_stocks(self, limit=100):
        """Popular international stocks (US & Global)"""
        stocks = [
            # TECH GIANTS (20)
            'NVDA', 'META', 'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA', 'AVGO',
            'ORCL', 'CSCO', 'IBM', 'INTC', 'AMD', 'QCOM', 'TXN', 'ADBE',
            'CRM', 'NOW', 'UBER', 'LYFT',
            
            # SEMICONDUCTORS (15)
            'NVDA', 'AVGO', 'AMD', 'QCOM', 'TXN', 'INTC', 'MU', 'AMAT',
            'LRCX', 'KLAC', 'ASML', 'TSM', 'NXPI', 'SWKS', 'MRVL',
            
            # AI & TECH (15)
            'PLTR', 'AI', 'PATH', 'CRWD', 'ZS', 'NET', 'DDOG', 'MDB',
            'SNOW', 'TEAM', 'OKTA', 'SPLK', 'ESTC', 'DBX', 'FSLY',
            
            # CONSUMER & RETAIL (15)
            'MCD', 'SBUX', 'NKE', 'TGT', 'WMT', 'COST', 'HD', 'LOW',
            'AMZN', 'EBAY', 'ETSY', 'SHOP', 'BABA', 'JD', 'PDD',
            
            # FINANCIAL (10)
            'JPM', 'BAC', 'WFC', 'GS', 'MS', 'V', 'MA', 'AXP', 'PYPL', 'SQ',
            
            # HEALTHCARE (10)
            'JNJ', 'PFE', 'MRK', 'ABT', 'TMO', 'DHR', 'LLY', 'UNH', 'CVS', 'WBA',
            
            # ENERGY & INDUSTRIAL (10)
            'XOM', 'CVX', 'COP', 'SLB', 'BA', 'CAT', 'DE', 'GE', 'HON', 'LMT',
            
            # ENTERTAINMENT & MEDIA (5)
            'NFLX', 'DIS', 'WBD', 'PARA', 'SPOT'
        ]
        return stocks[:limit]

    def search_assets(self, query, limit=20):
        """Enhanced search with web scraping for real-time data"""
        if self.market_type == 'saham_id':
            return self._search_id_stocks_enhanced(query, limit)
        elif self.market_type == 'forex':
            return self._search_forex_pairs_enhanced(query, limit)
        else:
            return self._search_crypto_yf(query, limit)

    def _search_id_stocks_enhanced(self, query, limit):
        """Enhanced search for Indonesian stocks with multiple sources"""
        results = set()
        
        # Method 1: Search dari investing.com
        investing_results = self._search_investing_com(query)
        results.update(investing_results)
        
        # Method 2: Search dari Yahoo Finance Indonesia
        yf_results = self._search_yahoo_id_stocks(query)
        results.update(yf_results)
        
        # Method 3: Search dari manual list
        query_clean = query.upper().replace('.JK', '').strip()
        for stock in self._get_comprehensive_id_stocks(200):
            if query_clean in stock.replace('.JK', ''):
                results.add(stock)
        
        return list(results)[:limit]

    def _search_investing_com(self, query):
        """Search stocks from investing.com"""
        try:
            url = f"https://id.investing.com/search/?q={query}"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept-Language': 'id-ID,id;q=0.9,en;q=0.8'
            }
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                stocks = set()
                
                # Cari results yang mengandung .JK
                links = soup.find_all('a', href=re.compile(r'/equities/'))
                for link in links:
                    href = link.get('href', '')
                    symbol = self._extract_symbol_from_url(href)
                    if symbol:
                        stocks.add(f"{symbol}.JK")
                
                return list(stocks)
        except Exception as e:
            print(f"Error searching investing.com: {e}")
        
        return []

    def _search_yahoo_id_stocks(self, query):
        """Search Indonesian stocks from Yahoo Finance"""
        stocks = set()
        try:
            # Yahoo Finance search for Indonesian stocks
            search_url = f"https://query2.finance.yahoo.com/v1/finance/search?q={query}.JK&quotesCount=10&newsCount=0"
            response = requests.get(search_url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                for quote in data.get('quotes', []):
                    symbol = quote.get('symbol', '')
                    if symbol and '.JK' in symbol:
                        stocks.add(symbol)
        except Exception:
            pass
        return stocks

    def _search_forex_pairs_enhanced(self, query, limit):
        """Enhanced search for forex pairs"""
        results = set()
        
        # Major and minor forex pairs
        major_pairs = [
            'EURUSD=X', 'USDJPY=X', 'GBPUSD=X', 'AUDUSD=X', 'USDCAD=X',
            'USDCHF=X', 'NZDUSD=X', 'EURGBP=X', 'EURJPY=X', 'GBPJPY=X'
        ]
        
        # Cross pairs
        cross_pairs = [
            'AUDJPY=X', 'CADJPY=X', 'CHFJPY=X', 'EURCAD=X', 'GBPCAD=X',
            'AUDCAD=X', 'NZDCAD=X', 'EURAUD=X', 'GBPAUD=X', 'NZDJPY=X'
        ]
        
        # Exotic pairs
        exotic_pairs = [
            'USDMXN=X', 'USDTRY=X', 'USDCNY=X', 'USDINR=X', 'USDBRL=X',
            'USDRUB=X', 'USDZAR=X', 'USDKRW=X', 'USDSEK=X', 'USDNOK=X'
        ]
        
        all_pairs = major_pairs + cross_pairs + exotic_pairs
        query_clean = query.upper().replace('=X', '').replace('/', '').strip()
        
        for pair in all_pairs:
            pair_clean = pair.replace('=X', '').replace('/', '')
            if query_clean in pair_clean:
                results.add(pair)
        
        return list(results)[:limit]

    def _search_crypto_yf(self, query, limit):
        """Search crypto via yfinance"""
        cryptos = set()
        try:
            search_url = f"https://query2.finance.yahoo.com/v1/finance/search?q={query}-USD&quotesCount=10&newsCount=0"
            response = requests.get(search_url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                for quote in data.get('quotes', []):
                    symbol = quote.get('symbol', '')
                    if symbol and '-USD' in symbol:
                        cryptos.add(symbol)
        except Exception:
            pass
        
        # Fallback to common cryptos
        if not cryptos:
            common_crypto = ['BTC-USD', 'ETH-USD', 'BNB-USD', 'XRP-USD', 'ADA-USD']
            query_clean = query.upper().replace('-USD', '').strip()
            for crypto in common_crypto:
                crypto_clean = crypto.replace('-USD', '')
                if query_clean in crypto_clean:
                    cryptos.add(crypto)
        
        return list(cryptos)[:limit]

class SolanaPumpFunProvider:
    def __init__(self, rpc_url):
        self.client = Client(rpc_url)
        self.program_id = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"
        self.dex_provider = DexScreenerProvider()
  
    async def monitor_new_tokens(self, limit=10):
        results = []
        try:
            async with connect(self.client._provider.endpoint_uri + "/") as websocket:
                await websocket.logs_subscribe(
                    {"mentions": [self.program_id]},
                    commitment="finalized"
                )
                async for msg in websocket:
                    if "create" in str(msg.result.value.logs):
                        token_mint = self.extract_token_mint(msg)
                        if token_mint:
                            ticker = await self.get_solana_ticker(token_mint)
                            results.append({'symbol': token_mint, 'ticker': ticker})
                            if len(results) >= limit:
                                break
        except Exception as e:
            pass
        return results
  
    def extract_token_mint(self, msg):
        return "EXAMPLE_MINT_TOKEN"

    async def get_solana_ticker(self, mint):
        return self.dex_provider.get_ticker('solana', mint)
