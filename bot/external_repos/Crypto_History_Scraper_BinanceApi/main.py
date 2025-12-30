from binance.client import Client
import pandas as pd
import os
import time
import sys
from datetime import datetime

client = Client()
interval = Client.KLINE_INTERVAL_1MINUTE
CHUNK_LIMIT = 1000   # Binance max per request

# -------- CLI ARGUMENTS ----------
if len(sys.argv) < 3:
    print("Usage: python main.py <SYMBOL> <START_DATE>")
    print("Example: python main.py BTCUSDT 2017-08-17")
    sys.exit()

symbol = sys.argv[1].upper()
START_DATE = sys.argv[2]
csv_file = f"{symbol}_1m.csv"
# ---------------------------------

def get_last_timestamp():
    """Return last open_time from CSV if exists, else None"""
    if not os.path.exists(csv_file):
        return None
    
    try:
        last_row = None
        for chunk in pd.read_csv(csv_file, chunksize=500000):
            last_row = chunk.tail(1)
        return int(pd.Timestamp(last_row["open_time"].values[0]).timestamp() * 1000)
    except Exception:
        return None


def fetch_and_append(start_ms):
    candles = client.get_klines(
        symbol=symbol,
        interval=interval,
        startTime=start_ms,
        limit=CHUNK_LIMIT
    )

    if not candles:
        return None

    cols = [
        "open_time","open","high","low","close","volume",
        "close_time","quote_volume","trades",
        "taker_buy_volume","taker_buy_quote","ignore"
    ]

    df = pd.DataFrame(candles, columns=cols)

    # Convert timestamps
    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
    df["close_time"] = pd.to_datetime(df["close_time"], unit="ms")

    # Append to CSV
    header_needed = not os.path.exists(csv_file)
    df.to_csv(csv_file, mode="a", index=False, header=header_needed)

    print(f"Saved {len(df)} candles → last: {df['open_time'].iloc[-1]}")
    return candles[-1][6] + 1   # next startTime


def main():
    print(f"Starting lazy download for {symbol} 1m data…")

    last_ts = get_last_timestamp()
    if last_ts:
        print(f"Resuming from {datetime.utcfromtimestamp(last_ts/1000)} UTC")
        start_ms = last_ts
    else:
        print("Starting fresh download")
        start_ms = int(pd.Timestamp(START_DATE).timestamp() * 1000)

    while True:
        next_start = fetch_and_append(start_ms)

        if not next_start:
            print("Up to date! ✔️")
            break

        start_ms = next_start
        time.sleep(0.2)   # avoid rate limit


if __name__ == "__main__":
    main()
