# Crypto History Scraper for Binance API

**Crypto History Scraper** is a lightweight Python tool designed to efficiently download historical cryptocurrency price data from Binance's API. It's perfect for backtesting trading strategies, data analysis, or building your own crypto datasets.

---

## ✨ Features

- 🚀 **Efficient Data Fetching** - Downloads historical 1-minute candlestick data from Binance
- 🔄 **Resumable Downloads** - Automatically resumes from the last downloaded timestamp
- 📊 **Pandas Integration** - Saves data in CSV format with proper column formatting
- ⏱️ **Rate Limit Handling** - Built-in delay to prevent hitting Binance API rate limits
- 📅 **Flexible Date Ranges** - Start from any date to download historical data
- 🔍 **Supports Any Trading Pair** - Works with all Binance trading pairs (e.g., BTCUSDT, ETHUSDT)

---

## 🛠️ Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/Sugarcube08/CryptoHistoryScraperBinanceAPI.git
   cd CryptoHistoryScraperBinanceAPI
   ```

2. **Set up a virtual environment (recommended)**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -e .
   ```

---

## 🚀 Usage

### Basic Usage
```bash
python main.py <SYMBOL> <START_DATE>
```

### Example
Download BTC/USDT data from August 17, 2017:
```bash
python main.py BTCUSDT 2017-08-17
```

### Arguments
- `SYMBOL`: Trading pair symbol (e.g., BTCUSDT, ETHUSDT)
- `START_DATE`: Start date in YYYY-MM-DD format

### Output
- Data is saved to `{SYMBOL}_1m.csv` in the project directory
- The file includes the following columns:
  - `open_time`: Opening time of the candle
  - `open`: Opening price
  - `high`: Highest price during the interval
  - `low`: Lowest price during the interval
  - `close`: Closing price
  - `volume`: Trading volume
  - `close_time`: Closing time of the candle
  - `quote_volume`: Quote asset volume
  - `trades`: Number of trades
  - `taker_buy_volume`: Taker buy volume
  - `taker_buy_quote`: Taker buy quote volume
  - `ignore`: Ignore column (part of Binance API response)

### Resuming Downloads
If the script is interrupted, simply run it again with the same parameters. It will automatically detect the last downloaded timestamp and resume from there.

---

## 📦 Dependencies

- Python 3.10+
- pandas >= 2.3.3
- python-binance >= 1.0.34

---

## 📝 Notes

- The script includes a small delay (0.2s) between API calls to avoid hitting Binance's rate limits.
- Data is saved in chunks to efficiently handle large datasets.
- The script creates a new file for each trading pair in the format `{SYMBOL}_1m.csv`.

---

## 🤝 Contributing

Contributions are welcome! If you'd like to contribute, please fork the repository and create a pull request with your changes.

---

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## ☕ Support Me

If you find this project useful, consider supporting my work:
[![Buy Me a Coffee](https://img.shields.io/badge/Buy%20Me%20a%20Coffee-Support%20Me-orange?style=flat-square&logo=buy-me-a-coffee)](https://www.buymeacoffee.com/sugarcube08)

---

## 📱 Connect With Me

[![YouTube](https://img.shields.io/badge/YouTube-%23FF0000.svg?logo=YouTube&logoColor=white)](https://www.youtube.com/@SugarCode-Z?sub_confirmation=1)
[![Instagram](https://img.shields.io/badge/Instagram-%23E4405F.svg?logo=Instagram&logoColor=white)](https://www.instagram.com/sugarcodez)
[![WhatsApp](https://img.shields.io/badge/WhatsApp-%25D366.svg?logo=whatsapp&logoColor=white)](https://whatsapp.com/channel/0029Vb5fFdzKgsNlaxFmhg1T)

---

> 💡 **Tip**: For large datasets, consider running the script on a server or cloud instance to avoid interruptions.