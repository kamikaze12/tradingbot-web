import os
import psycopg2
import threading
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()


class DatabaseHandler:
    def __init__(self):
        self.db_type = os.getenv("DB_TYPE", "postgresql")
        self.thread_local = threading.local()
        self.create_tables()

    # =========================================================
    # Connection
    # =========================================================
    def get_connection(self):
        """Get or create a thread-local database connection"""
        if not hasattr(self.thread_local, "conn"):
            try:
                print(f"Connecting to database: {os.getenv('DB_HOST')}")
                self.thread_local.conn = psycopg2.connect(
                    dbname=os.getenv("DB_NAME", "postgres"),
                    user=os.getenv("DB_USER", "postgres"),
                    password=os.getenv("DB_PASSWORD", ""),
                    host=os.getenv("DB_HOST", "localhost"),
                    port=os.getenv("DB_PORT", "5432"),
                )
                print("Connected to database successfully")
            except Exception as e:
                print(f"Failed to connect to database: {e}")
                raise
        return self.thread_local.conn

    # =========================================================
    # Schema
    # =========================================================
    def create_tables(self):
        """Create tables with the correct schema"""
        conn, cursor = None, None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            # Drop tables (reset)
            cursor.execute("DROP TABLE IF EXISTS signals CASCADE")
            cursor.execute("DROP TABLE IF EXISTS positions CASCADE")
            cursor.execute("DROP TABLE IF EXISTS trade_history CASCADE")

            # Table: signals
            cursor.execute(
                """
                CREATE TABLE signals (
                    id SERIAL PRIMARY KEY,
                    symbol TEXT NOT NULL,
                    market_type TEXT NOT NULL,
                    action TEXT NOT NULL,
                    entry_low REAL,
                    entry_high REAL,
                    tp1 REAL,
                    tp2 REAL,
                    tp3 REAL,
                    sl REAL,
                    current_price REAL,
                    rsi REAL,
                    trend TEXT,
                    volume_ratio REAL,
                    atr REAL,
                    score INTEGER,
                    hh BOOLEAN,
                    hl BOOLEAN,
                    lh BOOLEAN,
                    ll BOOLEAN,
                    ema_trend TEXT,
                    ema_score INTEGER,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            # Table: positions
            cursor.execute(
                """
                CREATE TABLE positions (
                    id SERIAL PRIMARY KEY,
                    symbol TEXT NOT NULL,
                    market_type TEXT NOT NULL,
                    action TEXT NOT NULL,
                    entry_price REAL,
                    entry_low REAL,
                    entry_high REAL,
                    tp1 REAL,
                    tp2 REAL,
                    tp3 REAL,
                    sl REAL,
                    current_price REAL,
                    status TEXT DEFAULT 'active',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    closed_at TIMESTAMP
                )
                """
            )

            # Table: trade_history
            cursor.execute(
                """
                CREATE TABLE trade_history (
                    id SERIAL PRIMARY KEY,
                    symbol TEXT NOT NULL,
                    market_type TEXT NOT NULL,
                    action TEXT NOT NULL,
                    entry_price REAL,
                    exit_price REAL,
                    profit_loss REAL,
                    type TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            conn.commit()
            print("Tables created successfully")

        except Exception as e:
            print(f"Error creating tables: {e}")
            if conn:
                conn.rollback()
        finally:
            if cursor:
                cursor.close()

    # =========================================================
    # Signals
    # =========================================================
    def save_signal(self, data):
        """Save signal to database with boolean casting"""
        conn = self.get_connection()
        cursor = conn.cursor()
        converted_data = self._convert_numpy_types(data)
        print(f"Saving signal: {converted_data}")

        try:
            hh = bool(converted_data.get("hh", False))
            hl = bool(converted_data.get("hl", False))
            lh = bool(converted_data.get("lh", False))
            ll = bool(converted_data.get("ll", False))

            cursor.execute(
                """
                INSERT INTO signals (
                    symbol, market_type, action, entry_low, entry_high,
                    tp1, tp2, tp3, sl, current_price,
                    rsi, trend, volume_ratio, atr, score,
                    hh, hl, lh, ll, ema_trend, ema_score
                )
                VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s
                )
                RETURNING id
                """,
                (
                    converted_data["symbol"],
                    data["market_type"],
                    converted_data["action"],
                    converted_data.get("entry_low"),
                    converted_data.get("entry_high"),
                    converted_data.get("tp1"),
                    converted_data.get("tp2"),
                    converted_data.get("tp3"),
                    converted_data.get("sl"),
                    converted_data.get("current_price"),
                    converted_data.get("rsi"),
                    converted_data.get("trend"),
                    converted_data.get("volume_ratio"),
                    converted_data.get("atr"),
                    converted_data.get("score"),
                    hh,
                    hl,
                    lh,
                    ll,
                    converted_data.get("ema_trend", "NEUTRAL"),
                    converted_data.get("ema_score", 0),
                ),
            )

            conn.commit()
            signal_id = cursor.fetchone()[0]
            print(f"Signal saved with ID: {signal_id}")
            return signal_id

        except Exception as e:
            print(f"Error saving signal: {e}")
            conn.rollback()
            raise
        finally:
            cursor.close()

    def get_all_signals(self, market_type):
        """Get all signals for a market"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT * FROM signals WHERE market_type = %s ORDER BY timestamp DESC",
                (market_type,),
            )
            return cursor.fetchall()
        finally:
            cursor.close()

    def delete_signal_by_symbol(self, symbol, market_type):
        """Delete signal by symbol"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "DELETE FROM signals WHERE symbol = %s AND market_type = %s",
                (symbol, market_type),
            )
            conn.commit()
            print(f"Deleted signal for {symbol}")
            return cursor.rowcount > 0
        except Exception as e:
            print(f"Error deleting signal: {e}")
            conn.rollback()
            return False
        finally:
            cursor.close()

    # =========================================================
    # Positions
    # =========================================================
    def save_position(
        self,
        symbol,
        market_type,
        action,
        entry_price,
        tp1,
        tp2,
        tp3,
        sl,
        entry_low=None,
        entry_high=None,
        current_price=None,
    ):
        """Save a new position to the database"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            if current_price is None:
                current_price = entry_price
            if entry_low is None:
                entry_low = entry_price * 0.98
            if entry_high is None:
                entry_high = entry_price * 1.02

            cursor.execute(
                """
                INSERT INTO positions (
                    symbol, market_type, action, entry_price,
                    entry_low, entry_high, tp1, tp2, tp3, sl, current_price
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    symbol,
                    market_type,
                    action,
                    entry_price,
                    entry_low,
                    entry_high,
                    tp1,
                    tp2,
                    tp3,
                    sl,
                    current_price,
                ),
            )

            conn.commit()
            position_id = cursor.fetchone()[0]
            print(f"Position saved with ID: {position_id}")
            return position_id

        except Exception as e:
            print(f"Error saving position: {e}")
            conn.rollback()
            return None
        finally:
            cursor.close()

    def update_position_current_price(self, symbol, current_price):
        """Update current price for a position"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE positions SET current_price = %s WHERE symbol = %s AND status = 'active'",
                (current_price, symbol),
            )
            conn.commit()
            print(f"Updated current price for {symbol} to {current_price}")
            return cursor.rowcount > 0
        except Exception as e:
            print(f"Error updating current price: {e}")
            conn.rollback()
            return False
        finally:
            cursor.close()

    def get_active_positions(self, market_type=None):
        """Get active positions from database"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            if market_type:
                cursor.execute(
                    """
                    SELECT * FROM positions
                    WHERE status = %s AND market_type = %s
                    ORDER BY created_at DESC
                    """,
                    ("active", market_type),
                )
            else:
                cursor.execute(
                    "SELECT * FROM positions WHERE status = %s ORDER BY created_at DESC",
                    ("active",),
                )
            return cursor.fetchall()
        finally:
            cursor.close()

    def close_position(self, position_id, close_price, exit_type):
        """Close a position and save to history"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT * FROM positions WHERE id = %s", (position_id,))
            position = cursor.fetchone()

            if position:
                if position[3] == "LONG":
                    profit_loss = close_price - position[4]
                else:  # SHORT
                    profit_loss = position[4] - close_price

                # Insert trade history
                cursor.execute(
                    """
                    INSERT INTO trade_history (
                        symbol, market_type, action,
                        entry_price, exit_price, profit_loss, type
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        position[1],
                        position[2],
                        position[3],
                        position[4],
                        close_price,
                        profit_loss,
                        exit_type,
                    ),
                )

                # Update position status
                cursor.execute(
                    """
                    UPDATE positions
                    SET status = 'closed', closed_at = CURRENT_TIMESTAMP, current_price = %s
                    WHERE id = %s
                    """,
                    (close_price, position_id),
                )

                conn.commit()
                print(f"Position {position_id} closed with P/L: {profit_loss}")
                return True
            return False

        except Exception as e:
            print(f"Error closing position: {e}")
            conn.rollback()
            return False
        finally:
            cursor.close()

    # =========================================================
    # Trade History
    # =========================================================
    def get_trade_history(self, market_type=None, limit=10):
        """Get trade history from database"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            if market_type:
                cursor.execute(
                    """
                    SELECT * FROM trade_history
                    WHERE market_type = %s
                    ORDER BY timestamp DESC LIMIT %s
                    """,
                    (market_type, limit),
                )
            else:
                cursor.execute(
                    "SELECT * FROM trade_history ORDER BY timestamp DESC LIMIT %s",
                    (limit,),
                )
            return cursor.fetchall()
        finally:
            cursor.close()

    # =========================================================
    # Utils
    # =========================================================
    def _convert_numpy_types(self, data):
        """Convert numpy types to native Python types"""
        if isinstance(data, dict):
            return {k: self._convert_numpy_types(v) for k, v in data.items()}
        if data is None:
            return None
        if hasattr(data, "item"):
            return data.item()
        try:
            return float(data)
        except Exception:
            return str(data)
