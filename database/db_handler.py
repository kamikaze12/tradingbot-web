import os
import psycopg2
import threading
from dotenv import load_dotenv
from datetime import datetime, timedelta
import streamlit as st

load_dotenv()

def create_enhanced_tables(self):
    """Create enhanced tables for Phase 2 features"""
    conn, cursor = None, None
    try:
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Table: backtest_results
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS backtest_results (
                id SERIAL PRIMARY KEY,
                symbol TEXT NOT NULL,
                market_type TEXT NOT NULL,
                total_trades INTEGER,
                winning_trades INTEGER,
                losing_trades INTEGER,
                win_rate REAL,
                total_pnl REAL,
                sharpe_ratio REAL,
                max_drawdown REAL,
                final_balance REAL,
                period_days INTEGER,
                test_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Table: portfolio_allocations
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS portfolio_allocations (
                id SERIAL PRIMARY KEY,
                symbol TEXT NOT NULL,
                market_type TEXT NOT NULL,
                allocation_percent REAL,
                allocated_capital REAL,
                risk_category TEXT,
                score INTEGER,
                optimization_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Table: ml_analysis
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ml_analysis (
                id SERIAL PRIMARY KEY,
                symbol TEXT NOT NULL,
                market_type TEXT NOT NULL,
                traditional_score INTEGER,
                ml_confidence REAL,
                combined_score INTEGER,
                risk_metrics JSONB,
                analysis_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.commit()
        print("Enhanced tables created successfully")
        
    except Exception as e:
        print(f"Error creating enhanced tables: {e}")
        if conn:
            conn.rollback()
    finally:
        if cursor:
            cursor.close()

def save_backtest_result(self, result_data):
    """Save backtest results to database"""
    conn = self.get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO backtest_results (
                symbol, market_type, total_trades, winning_trades, losing_trades,
                win_rate, total_pnl, sharpe_ratio, max_drawdown, final_balance, period_days
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            result_data['symbol'],
            result_data.get('market_type', 'unknown'),
            result_data['total_trades'],
            result_data['winning_trades'],
            result_data['losing_trades'],
            result_data['win_rate'],
            result_data['total_pnl'],
            result_data['sharpe_ratio'],
            result_data['max_drawdown'],
            result_data['final_balance'],
            result_data['period_days']
        ))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error saving backtest result: {e}")
        conn.rollback()
        return False
    finally:
        cursor.close()

# Panggil method enhanced tables di __init__
# Tambahkan di __init__ method DatabaseHandler:
# self.create_enhanced_tables()
class DatabaseHandler:
    def __init__(self):
        self.db_type = "postgresql"
        self.thread_local = threading.local()
        self.create_tables()

    # =========================================================
    # Connection - SIMPLIFIED & FIXED
    # =========================================================
    def get_connection(self):
        """Get or create a thread-local database connection"""
        if not hasattr(self.thread_local, "conn"):
            try:
                # Get connection parameters
                conn_params = self._get_connection_params()
               
                if not conn_params:
                    raise Exception("No database configuration found")
               
                print(f"Connecting to: {conn_params['host']}:{conn_params['port']} as {conn_params['user']}")
                self.thread_local.conn = psycopg2.connect(**conn_params)
                print("Connected to database successfully")
               
            except Exception as e:
                print(f"Failed to connect to database: {e}")
                if hasattr(st, 'error'):
                    st.error(f"Database connection failed: {e}")
                raise
        return self.thread_local.conn

    def _get_connection_params(self):
        """Get connection parameters from Streamlit secrets or environment"""
        # Default values
        params = {
            'dbname': 'postgres',
            'user': 'postgres',
            'password': '',
            'host': 'localhost',
            'port': 5432,
            'sslmode': 'require',
            'keepalives': 1,
            'keepalives_idle': 30,
            'keepalives_interval': 10,
            'keepalives_count': 5
        }
       
        try:
            # Priority 1: Streamlit Secrets
            if hasattr(st, 'secrets'):
                secrets = st.secrets
               
                # Check individual parameters first
                if all(key in secrets for key in ['DB_HOST', 'DB_USER', 'DB_PASSWORD', 'DB_NAME']):
                    params.update({
                        'host': secrets['DB_HOST'],
                        'user': secrets['DB_USER'],
                        'password': secrets['DB_PASSWORD'],
                        'dbname': secrets['DB_NAME'],
                        'port': int(secrets.get('DB_PORT', 5432))
                    })
                    return params
               
                # Check database section
                if 'database' in secrets:
                    db_config = secrets['database']
                    if all(key in db_config for key in ['DB_HOST', 'DB_USER', 'DB_PASSWORD', 'DB_NAME']):
                        params.update({
                            'host': db_config['DB_HOST'],
                            'user': db_config['DB_USER'],
                            'password': db_config['DB_PASSWORD'],
                            'dbname': db_config['DB_NAME'],
                            'port': int(db_config.get('DB_PORT', 5432))
                        })
                        return params
           
            # Priority 2: Environment Variables
            if all(os.getenv(key) for key in ['DB_HOST', 'DB_USER', 'DB_PASSWORD', 'DB_NAME']):
                params.update({
                    'host': os.getenv('DB_HOST'),
                    'user': os.getenv('DB_USER'),
                    'password': os.getenv('DB_PASSWORD'),
                    'dbname': os.getenv('DB_NAME'),
                    'port': int(os.getenv('DB_PORT', 5432))
                })
                return params
           
            # If we get here, no valid config found
            return None
           
        except Exception as e:
            print(f"Error getting connection params: {e}")
            return None

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
    # Cleanup Methods - NEW
    # =========================================================
    def cleanup_old_signals(self, days=7):
        """Clean up signals older than specified days"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "DELETE FROM signals WHERE timestamp < NOW() - INTERVAL '%s days'",
                (days,)
            )
            conn.commit()
            deleted_count = cursor.rowcount
            print(f"Cleaned up {deleted_count} old signals (older than {days} days)")
            return deleted_count
        except Exception as e:
            print(f"Error cleaning up old signals: {e}")
            conn.rollback()
            return 0
        finally:
            cursor.close()

    def cleanup_old_data(self, days=7):
        """Clean up all old data including positions and history"""
        try:
            signals_count = self.cleanup_old_signals(days)
            
            # Clean up old positions
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM positions WHERE created_at < NOW() - INTERVAL '%s days' AND status = 'closed'",
                (days,)
            )
            positions_count = cursor.rowcount
            
            # Clean up old trade history
            cursor.execute(
                "DELETE FROM trade_history WHERE timestamp < NOW() - INTERVAL '%s days'",
                (days,)
            )
            history_count = cursor.rowcount
            
            conn.commit()
            print(f"Cleaned up {signals_count} signals, {positions_count} positions, {history_count} history records")
            return {
                'signals': signals_count,
                'positions': positions_count,
                'history': history_count
            }
        except Exception as e:
            print(f"Error cleaning up old data: {e}")
            if conn:
                conn.rollback()
            return {'signals': 0, 'positions': 0, 'history': 0}
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
                (float(current_price), symbol),
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
                else: # SHORT
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

    def close_connection(self):
        """Close the database connection"""
        if hasattr(self.thread_local, "conn"):
            self.thread_local.conn.close()
            del self.thread_local.conn
            print("Database connection closed")
