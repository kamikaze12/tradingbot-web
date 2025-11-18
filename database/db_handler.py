import os
import psycopg2
import threading
from dotenv import load_dotenv
from datetime import datetime, timedelta
import streamlit as st
import pandas as pd
import numpy as np
import json
import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from enum import Enum
import time
from contextlib import contextmanager

load_dotenv()

# Enhanced logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class TradeType(Enum):
    LONG = "LONG"
    SHORT = "SHORT"
    NEUTRAL = "NEUTRAL"

class PositionStatus(Enum):
    ACTIVE = "active"
    PARTIAL_TP = "partial_tp"
    TRAILING = "trailing"
    CLOSED = "closed"
    CANCELLED = "cancelled"

@dataclass
class EnhancedPosition:
    """Enhanced position data structure"""
    symbol: str
    market_type: str
    action: str
    entry_price: float
    position_size: float
    current_price: float
    stop_loss: float
    take_profit_1: float
    take_profit_2: float
    take_profit_3: float
    trailing_stop: Optional[float] = None
    trailing_distance: float = 0.0
    partial_tp_executed: List[Dict] = None
    risk_category: str = "MEDIUM"
    position_score: int = 0
    status: str = "active"
    created_at: datetime = None
    updated_at: datetime = None
    
    def __post_init__(self):
        if self.partial_tp_executed is None:
            self.partial_tp_executed = []
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.updated_at is None:
            self.updated_at = datetime.now()

class DatabaseHandler:
    def __init__(self):
        self.db_type = "postgresql"
        self.thread_local = threading.local()
        self.connection_pool = {}
        self.max_pool_size = 5
        
        # Initialize performance monitoring FIRST
        self.query_count = 0
        self.error_count = 0
        self.last_cleanup = datetime.now()
        
        # Then initialize database
        self._initialize_database()
        self.create_enhanced_tables()

    # =========================================================
    # ENHANCED CONNECTION MANAGEMENT
    # =========================================================
    
    def _initialize_database(self):
        """Initialize database dengan connection pool"""
        try:
            # Test connection dan create database jika tidak ada
            conn_params = self._get_connection_params()
            if not conn_params:
                logger.error("No database configuration found")
                return
                
            # Test connection
            test_conn = psycopg2.connect(**conn_params)
            test_conn.close()
            logger.info("✅ Database connection test successful")
            
        except Exception as e:
            logger.error(f"❌ Database initialization failed: {e}")
            self.error_count += 1  # Track error
            if hasattr(st, 'error'):
                st.error(f"Database initialization failed: {e}")

    @contextmanager
    def get_connection(self):
        """Enhanced connection management dengan connection pool dan context manager"""
        conn = None
        try:
            thread_id = threading.get_ident()
            
            # Check for existing connection in pool
            if (hasattr(self.thread_local, 'conn') and 
                self.thread_local.conn and 
                not self.thread_local.conn.closed):
                conn = self.thread_local.conn
                yield conn
                return
            
            # Get new connection
            conn_params = self._get_connection_params()
            if not conn_params:
                raise Exception("No database configuration found")
            
            conn = psycopg2.connect(**conn_params)
            conn.autocommit = False
            
            # Store connection in thread local
            self.thread_local.conn = conn
            self.query_count += 1
            
            yield conn
            
            # Commit successful transaction
            conn.commit()
            
        except Exception as e:
            if conn:
                conn.rollback()
            self.error_count += 1
            logger.error(f"Database connection error: {e}")
            raise
        finally:
            # Don't close connection immediately, reuse it
            pass

    def _get_connection_params(self):
        """Enhanced connection parameters dengan fallback options"""
        # Default values
        params = {
            'dbname': 'postgres',
            'user': 'postgres',
            'password': '',
            'host': 'localhost',
            'port': 5432,
            'connect_timeout': 10,
            'keepalives': 1,
            'keepalives_idle': 30,
            'keepalives_interval': 10,
            'keepalives_count': 5,
            'application_name': 'TradingBot_v2'
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
            env_mapping = {
                'DB_HOST': 'host',
                'DB_USER': 'user', 
                'DB_PASSWORD': 'password',
                'DB_NAME': 'dbname',
                'DB_PORT': 'port'
            }
            
            env_found = False
            for env_key, param_key in env_mapping.items():
                env_value = os.getenv(env_key)
                if env_value:
                    if param_key == 'port':
                        params[param_key] = int(env_value)
                    else:
                        params[param_key] = env_value
                    env_found = True
            
            if env_found:
                return params
           
            # Priority 3: Default local setup
            logger.info("Using default local database configuration")
            return params
           
        except Exception as e:
            logger.error(f"Error getting connection params: {e}")
            self.error_count += 1
            return None

    def close_all_connections(self):
        """Close all database connections"""
        try:
            if hasattr(self.thread_local, "conn"):
                self.thread_local.conn.close()
                del self.thread_local.conn
                
            # Close any other connections in pool
            for thread_id, conn in list(self.connection_pool.items()):
                try:
                    conn.close()
                except:
                    pass
                del self.connection_pool[thread_id]
                
            logger.info("All database connections closed")
        except Exception as e:
            logger.error(f"Error closing connections: {e}")

    # =========================================================
    # ENHANCED TABLE SCHEMA
    # =========================================================
    
    def create_enhanced_tables(self):
        """Create enhanced tables untuk semua features"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                # Drop tables jika perlu reset (comment out in production)
                # self._drop_tables(cursor)
                
                # Table: signals (enhanced)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS signals (
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
                        pattern_score INTEGER,
                        momentum_score INTEGER,
                        market_regime TEXT,
                        volatility REAL,
                        risk_category TEXT,
                        confidence REAL DEFAULT 0.5,
                        pattern_details JSONB,
                        tp_probabilities JSONB,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Table: positions (enhanced dengan trailing stops dan partial TP)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS positions (
                        id SERIAL PRIMARY KEY,
                        symbol TEXT NOT NULL,
                        market_type TEXT NOT NULL,
                        action TEXT NOT NULL,
                        entry_price REAL NOT NULL,
                        position_size REAL NOT NULL,
                        current_price REAL,
                        entry_low REAL,
                        entry_high REAL,
                        tp1 REAL,
                        tp2 REAL,
                        tp3 REAL,
                        sl REAL NOT NULL,
                        trailing_stop REAL,
                        trailing_distance REAL DEFAULT 0,
                        partial_tp_executed JSONB DEFAULT '[]',
                        risk_category TEXT DEFAULT 'MEDIUM',
                        position_score INTEGER DEFAULT 0,
                        status TEXT DEFAULT 'active',
                        pnl REAL DEFAULT 0,
                        pnl_percent REAL DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        closed_at TIMESTAMP,
                        close_reason TEXT
                    )
                """)
                
                # Table: trade_history (enhanced)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS trade_history (
                        id SERIAL PRIMARY KEY,
                        symbol TEXT NOT NULL,
                        market_type TEXT NOT NULL,
                        action TEXT NOT NULL,
                        entry_price REAL NOT NULL,
                        exit_price REAL NOT NULL,
                        position_size REAL NOT NULL,
                        profit_loss REAL,
                        profit_loss_percent REAL,
                        commission REAL DEFAULT 0,
                        slippage REAL DEFAULT 0,
                        type TEXT,
                        duration_minutes INTEGER,
                        risk_reward_ratio REAL,
                        position_score INTEGER,
                        exit_reason TEXT,
                        strategy_version TEXT DEFAULT 'v2.0',
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Table: portfolio_allocations (NEW)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS portfolio_allocations (
                        id SERIAL PRIMARY KEY,
                        symbol TEXT NOT NULL,
                        market_type TEXT NOT NULL,
                        allocation_percent REAL NOT NULL,
                        allocated_capital REAL NOT NULL,
                        risk_category TEXT,
                        score INTEGER,
                        expected_return REAL,
                        risk_adjustment REAL DEFAULT 1.0,
                        optimization_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Table: backtest_results (NEW)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS backtest_results (
                        id SERIAL PRIMARY KEY,
                        symbol TEXT NOT NULL,
                        market_type TEXT NOT NULL,
                        strategy_name TEXT,
                        timeframe TEXT,
                        total_trades INTEGER,
                        winning_trades INTEGER,
                        losing_trades INTEGER,
                        win_rate REAL,
                        total_pnl REAL,
                        sharpe_ratio REAL,
                        max_drawdown REAL,
                        final_balance REAL,
                        period_days INTEGER,
                        test_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        parameters JSONB,
                        equity_curve JSONB
                    )
                """)
                
                # Table: ml_analysis (NEW)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS ml_analysis (
                        id SERIAL PRIMARY KEY,
                        symbol TEXT NOT NULL,
                        market_type TEXT NOT NULL,
                        traditional_score INTEGER,
                        ml_confidence REAL,
                        combined_score INTEGER,
                        feature_importance JSONB,
                        prediction_metrics JSONB,
                        risk_metrics JSONB,
                        analysis_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Table: market_regimes (NEW)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS market_regimes (
                        id SERIAL PRIMARY KEY,
                        symbol TEXT NOT NULL,
                        market_type TEXT NOT NULL,
                        regime_type TEXT NOT NULL,
                        trend_strength REAL,
                        volatility_regime TEXT,
                        support_levels JSONB,
                        resistance_levels JSONB,
                        volume_profile JSONB,
                        detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Table: performance_metrics (NEW)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS performance_metrics (
                        id SERIAL PRIMARY KEY,
                        metric_date DATE NOT NULL,
                        total_trades INTEGER DEFAULT 0,
                        winning_trades INTEGER DEFAULT 0,
                        total_pnl REAL DEFAULT 0,
                        win_rate REAL DEFAULT 0,
                        avg_profit REAL DEFAULT 0,
                        avg_loss REAL DEFAULT 0,
                        profit_factor REAL DEFAULT 0,
                        sharpe_ratio REAL DEFAULT 0,
                        max_drawdown REAL DEFAULT 0,
                        daily_return REAL DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE (metric_date)
                    )
                """)
                
                # Sekarang buat semua INDEX dengan statement terpisah
                self._create_indexes(cursor)
                
                conn.commit()
                logger.info("✅ Enhanced tables and indexes created successfully")
                
            except Exception as e:
                conn.rollback()
                logger.error(f"Error creating enhanced tables: {e}")
                self.error_count += 1
                raise
            finally:
                cursor.close()

    def _create_indexes(self, cursor):
        """Create all necessary indexes separately"""
        try:
            # Indexes for signals table
            cursor.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS signals_symbol_market_timestamp_idx 
                ON signals (symbol, market_type, timestamp)
            """)
            
            # Indexes for positions table
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS positions_symbol_status_idx 
                ON positions (symbol, status)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS positions_market_type_status_idx 
                ON positions (market_type, status)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS positions_created_at_idx 
                ON positions (created_at)
            """)
            
            # Indexes for trade_history table
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS trade_history_symbol_timestamp_idx 
                ON trade_history (symbol, timestamp)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS trade_history_market_type_idx 
                ON trade_history (market_type)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS trade_history_timestamp_idx 
                ON trade_history (timestamp)
            """)
            
            # Indexes for portfolio_allocations table
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS portfolio_allocations_symbol_idx 
                ON portfolio_allocations (symbol)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS portfolio_allocations_optimization_date_idx 
                ON portfolio_allocations (optimization_date)
            """)
            
            # Indexes for backtest_results table
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS backtest_results_symbol_idx 
                ON backtest_results (symbol)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS backtest_results_test_date_idx 
                ON backtest_results (test_date)
            """)
            
            # Indexes for ml_analysis table
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS ml_analysis_symbol_date_idx 
                ON ml_analysis (symbol, analysis_date)
            """)
            
            # Indexes for market_regimes table
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS market_regimes_symbol_regime_idx 
                ON market_regimes (symbol, regime_type)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS market_regimes_detected_at_idx 
                ON market_regimes (detected_at)
            """)
            
            logger.info("✅ All indexes created successfully")
            
        except Exception as e:
            logger.error(f"Error creating indexes: {e}")
            self.error_count += 1
            raise

    def _drop_tables(self, cursor):
        """Drop tables untuk development (gunakan dengan hati-hati!)"""
        tables = [
            'signals', 'positions', 'trade_history', 'portfolio_allocations',
            'backtest_results', 'ml_analysis', 'market_regimes', 'performance_metrics'
        ]
        
        for table in tables:
            try:
                cursor.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
                logger.info(f"Dropped table: {table}")
            except Exception as e:
                logger.warning(f"Error dropping table {table}: {e}")
                self.error_count += 1

    # =========================================================
    # ENHANCED SIGNALS MANAGEMENT
    # =========================================================
    
    def save_signal(self, data: Dict[str, Any]) -> Optional[int]:
        """Save enhanced signal dengan comprehensive data"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                # Convert numpy types dan handle data validation
                converted_data = self._convert_numpy_types(data)
                
                # Prepare pattern details
                pattern_details = converted_data.get('pattern_details', {})
                if isinstance(pattern_details, dict):
                    pattern_details_json = json.dumps(pattern_details)
                else:
                    pattern_details_json = '{}'
                
                # Prepare TP probabilities
                tp_probabilities = converted_data.get('tp_probabilities', {})
                if isinstance(tp_probabilities, dict):
                    tp_probabilities_json = json.dumps(tp_probabilities)
                else:
                    tp_probabilities_json = '{}'
                
                cursor.execute("""
                    INSERT INTO signals (
                        symbol, market_type, action, entry_low, entry_high,
                        tp1, tp2, tp3, sl, current_price,
                        rsi, trend, volume_ratio, atr, score,
                        hh, hl, lh, ll, ema_trend, ema_score,
                        pattern_score, momentum_score, market_regime, volatility,
                        risk_category, confidence, pattern_details, tp_probabilities
                    )
                    VALUES (
                        %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    RETURNING id
                """, (
                    converted_data.get("symbol"),
                    converted_data.get("market_type", "unknown"),
                    converted_data.get("action"),
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
                    bool(converted_data.get("hh", False)),
                    bool(converted_data.get("hl", False)),
                    bool(converted_data.get("lh", False)),
                    bool(converted_data.get("ll", False)),
                    converted_data.get("ema_trend", "NEUTRAL"),
                    converted_data.get("ema_score", 0),
                    converted_data.get("pattern_score", 0),
                    converted_data.get("momentum_score", 0),
                    converted_data.get("market_regime", "unknown"),
                    converted_data.get("volatility", 0.02),
                    converted_data.get("risk_category", "MEDIUM"),
                    converted_data.get("confidence", 0.5),
                    pattern_details_json,
                    tp_probabilities_json
                ))
                
                signal_id = cursor.fetchone()[0]
                conn.commit()
                
                logger.info(f"Signal saved with ID: {signal_id} for {converted_data.get('symbol')}")
                return signal_id
                
            except Exception as e:
                conn.rollback()
                logger.error(f"Error saving signal: {e}")
                self.error_count += 1
                raise
            finally:
                cursor.close()

    def get_signals(self, market_type: str = None, limit: int = 50, 
                   min_score: int = 0, hours_back: int = 24) -> List[Dict]:
        """Get signals dengan advanced filtering"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                query = """
                    SELECT * FROM signals 
                    WHERE timestamp >= NOW() - INTERVAL %s hours
                """
                params = [hours_back]
                
                if market_type:
                    query += " AND market_type = %s"
                    params.append(market_type)
                
                if min_score > 0:
                    query += " AND ABS(score) >= %s"
                    params.append(min_score)
                
                query += " ORDER BY timestamp DESC LIMIT %s"
                params.append(limit)
                
                cursor.execute(query, params)
                columns = [desc[0] for desc in cursor.description]
                results = []
                
                for row in cursor.fetchall():
                    result_dict = dict(zip(columns, row))
                    # Parse JSON fields
                    if result_dict.get('pattern_details'):
                        try:
                            result_dict['pattern_details'] = json.loads(result_dict['pattern_details'])
                        except:
                            result_dict['pattern_details'] = {}
                    if result_dict.get('tp_probabilities'):
                        try:
                            result_dict['tp_probabilities'] = json.loads(result_dict['tp_probabilities'])
                        except:
                            result_dict['tp_probabilities'] = {}
                    
                    results.append(result_dict)
                
                return results
                
            except Exception as e:
                logger.error(f"Error getting signals: {e}")
                self.error_count += 1
                return []
            finally:
                cursor.close()

    def delete_old_signals(self, days: int = 7) -> int:
        """Delete signals older than specified days"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    "DELETE FROM signals WHERE timestamp < NOW() - INTERVAL %s days",
                    (days,)
                )
                deleted_count = cursor.rowcount
                conn.commit()
                
                logger.info(f"Deleted {deleted_count} signals older than {days} days")
                return deleted_count
                
            except Exception as e:
                conn.rollback()
                logger.error(f"Error deleting old signals: {e}")
                self.error_count += 1
                return 0
            finally:
                cursor.close()

    # =========================================================
    # ENHANCED POSITIONS MANAGEMENT - FIXED TP1-TP3
    # =========================================================
    
    def save_position(self, symbol: str, market_type: str, action: str, 
                     entry_price: float, tp1: float, tp2: float, tp3: float, 
                     sl: float, entry_low: float = None, entry_high: float = None,
                     current_price: float = None, position_size: float = None,
                     trailing_distance: float = 0, risk_category: str = "MEDIUM",
                     position_score: int = 0) -> Optional[int]:
        """Save enhanced position dengan trailing stops dan risk management"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                if current_price is None:
                    current_price = entry_price
                if entry_low is None:
                    entry_low = entry_price * 0.98
                if entry_high is None:
                    entry_high = entry_price * 1.02
                if position_size is None:
                    # Calculate default position size based on risk
                    position_size = self._calculate_default_position_size(entry_price, sl)
                
                # Calculate trailing stop jika enabled
                trailing_stop = None
                if trailing_distance > 0:
                    if action == "LONG":
                        trailing_stop = entry_price - trailing_distance
                    else:
                        trailing_stop = entry_price + trailing_distance
                
                cursor.execute("""
                    INSERT INTO positions (
                        symbol, market_type, action, entry_price, position_size,
                        current_price, entry_low, entry_high, tp1, tp2, tp3, sl,
                        trailing_stop, trailing_distance, risk_category, position_score
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    symbol, market_type, action, entry_price, position_size,
                    current_price, entry_low, entry_high, tp1, tp2, tp3, sl,
                    trailing_stop, trailing_distance, risk_category, position_score
                ))
                
                position_id = cursor.fetchone()[0]
                conn.commit()
                
                logger.info(f"Position saved with ID: {position_id} for {symbol}")
                return position_id
                
            except Exception as e:
                conn.rollback()
                logger.error(f"Error saving position: {e}")
                self.error_count += 1
                return None
            finally:
                cursor.close()

    def _calculate_default_position_size(self, entry_price: float, stop_loss: float, 
                                       risk_per_trade: float = 0.01, account_balance: float = 10000) -> float:
        """Calculate default position size based on risk management"""
        if entry_price <= 0 or stop_loss <= 0:
            return 0.0
            
        risk_amount = account_balance * risk_per_trade
        price_risk = abs(entry_price - stop_loss)
        
        if price_risk == 0:
            return 0.0
            
        position_size = risk_amount / price_risk
        
        # Limit to 20% of account balance
        max_position_value = account_balance * 0.2
        max_position_size = max_position_value / entry_price
        
        return min(position_size, max_position_size)

    def update_position_current_price(self, symbol: str, current_price: float) -> bool:
        """Update current price untuk position dan calculate PnL"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                # Get position details
                cursor.execute(
                    "SELECT id, entry_price, action, position_size FROM positions WHERE symbol = %s AND status = 'active'",
                    (symbol,)
                )
                position = cursor.fetchone()
                
                if not position:
                    logger.warning(f"No active position found for {symbol}")
                    return False
                
                position_id, entry_price, action, position_size = position
                
                # Calculate PnL
                if action == "LONG":
                    pnl = (current_price - entry_price) * position_size
                    pnl_percent = (current_price - entry_price) / entry_price * 100
                else:  # SHORT
                    pnl = (entry_price - current_price) * position_size
                    pnl_percent = (entry_price - current_price) / entry_price * 100
                
                # Update position
                cursor.execute("""
                    UPDATE positions 
                    SET current_price = %s, pnl = %s, pnl_percent = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (current_price, pnl, pnl_percent, position_id))
                
                conn.commit()
                logger.debug(f"Updated current price for {symbol} to {current_price}, PnL: {pnl:.2f}")
                return True
                
            except Exception as e:
                conn.rollback()
                logger.error(f"Error updating current price: {e}")
                self.error_count += 1
                return False
            finally:
                cursor.close()

    def update_trailing_stop(self, symbol: str, new_stop: float) -> bool:
        """Update trailing stop loss untuk position"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    UPDATE positions 
                    SET trailing_stop = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE symbol = %s AND status = 'active'
                """, (new_stop, symbol))
                
                affected = cursor.rowcount
                conn.commit()
                
                if affected > 0:
                    logger.info(f"Updated trailing stop for {symbol} to {new_stop}")
                    return True
                else:
                    logger.warning(f"No active position found for {symbol} to update trailing stop")
                    return False
                    
            except Exception as e:
                conn.rollback()
                logger.error(f"Error updating trailing stop: {e}")
                self.error_count += 1
                return False
            finally:
                cursor.close()

    def execute_partial_take_profit(self, position_id: int, tp_level: float, 
                                  close_percentage: float = 0.5) -> bool:
        """Execute partial take profit untuk position - FIXED"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                # Get current position - HANYA ambil kolom yang diperlukan
                cursor.execute(
                    "SELECT symbol, position_size, partial_tp_executed FROM positions WHERE id = %s",
                    (position_id,)
                )
                position = cursor.fetchone()
                
                if not position:
                    logger.error(f"Position {position_id} not found")
                    return False
                
                symbol, current_size, partial_tp_json = position
                
                # Parse existing partial TPs
                partial_tp_executed = []
                if partial_tp_json:
                    try:
                        partial_tp_executed = json.loads(partial_tp_json)
                    except:
                        partial_tp_executed = []
                
                # Calculate new position size
                close_size = current_size * close_percentage
                new_size = current_size - close_size
                
                # Add to partial TP history
                partial_tp_executed.append({
                    'timestamp': datetime.now().isoformat(),
                    'price': tp_level,
                    'size': close_size,
                    'percentage': close_percentage
                })
                
                # Update position
                cursor.execute("""
                    UPDATE positions 
                    SET position_size = %s, partial_tp_executed = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (new_size, json.dumps(partial_tp_executed), position_id))
                
                # If position size is very small, close it
                if new_size < 0.001:
                    cursor.execute("""
                        UPDATE positions 
                        SET status = 'closed', closed_at = CURRENT_TIMESTAMP, close_reason = 'partial_tp_complete'
                        WHERE id = %s
                    """, (position_id,))
                
                conn.commit()
                logger.info(f"Partial TP executed for {symbol}: closed {close_percentage:.1%} at {tp_level}")
                return True
                
            except Exception as e:
                conn.rollback()
                logger.error(f"Error executing partial TP: {e}")
                self.error_count += 1
                return False
            finally:
                cursor.close()

    def get_active_positions(self, market_type: str = None) -> List[Dict]:
        """Get active positions dengan enhanced data - FIXED"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                if market_type:
                    cursor.execute("""
                        SELECT * FROM positions
                        WHERE status = 'active' AND market_type = %s
                        ORDER BY created_at DESC
                    """, (market_type,))
                else:
                    cursor.execute("""
                        SELECT * FROM positions 
                        WHERE status = 'active' 
                        ORDER BY created_at DESC
                    """)
                
                columns = [desc[0] for desc in cursor.description]
                results = []
                
                for row in cursor.fetchall():
                    result_dict = dict(zip(columns, row))
                    
                    # Parse JSON fields
                    if result_dict.get('partial_tp_executed'):
                        try:
                            result_dict['partial_tp_executed'] = json.loads(result_dict['partial_tp_executed'])
                        except:
                            result_dict['partial_tp_executed'] = []
                    
                    results.append(result_dict)
                
                return results
                
            except Exception as e:
                logger.error(f"Error getting active positions: {e}")
                self.error_count += 1
                return []
            finally:
                cursor.close()

    def close_position(self, position_id: int, close_price: float, 
                      exit_type: str = "manual", commission: float = 0) -> bool:
        """Close position dan save ke trade history - FIXED"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                # Get position details - AMBIL SEMUA KOLOM TP YANG DIPERLUKAN
                cursor.execute("""
                    SELECT symbol, market_type, action, entry_price, position_size, 
                           current_price, sl, tp1, tp2, tp3, created_at
                    FROM positions WHERE id = %s
                """, (position_id,))
                
                position = cursor.fetchone()
                if not position:
                    logger.error(f"Position {position_id} not found")
                    return False
                
                # Unpack semua nilai termasuk tp1, tp2, tp3
                (symbol, market_type, action, entry_price, position_size, 
                 current_price, sl, tp1, tp2, tp3, created_at) = position
                
                # Calculate final PnL
                if action == "LONG":
                    profit_loss = (close_price - entry_price) * position_size
                else:  # SHORT
                    profit_loss = (entry_price - close_price) * position_size
                
                profit_loss_percent = (profit_loss / (entry_price * position_size)) * 100 if entry_price * position_size > 0 else 0
                
                # Calculate duration
                duration_minutes = 0
                if created_at:
                    duration_minutes = int((datetime.now() - created_at).total_seconds() / 60)
                
                # Calculate risk/reward ratio menggunakan tp1
                risk_reward_ratio = 0
                if sl and tp1 and entry_price:
                    if action == "LONG":
                        risk = entry_price - sl
                        reward = tp1 - entry_price
                    else:
                        risk = sl - entry_price
                        reward = entry_price - tp1
                    
                    if risk > 0:
                        risk_reward_ratio = reward / risk
                
                # Insert trade history
                cursor.execute("""
                    INSERT INTO trade_history (
                        symbol, market_type, action, entry_price, exit_price,
                        position_size, profit_loss, profit_loss_percent, commission,
                        type, duration_minutes, risk_reward_ratio
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    symbol, market_type, action, entry_price, close_price,
                    position_size, profit_loss, profit_loss_percent, commission,
                    exit_type, duration_minutes, risk_reward_ratio
                ))
                
                # Update position status
                cursor.execute("""
                    UPDATE positions 
                    SET status = 'closed', closed_at = CURRENT_TIMESTAMP, 
                        current_price = %s, close_reason = %s,
                        pnl = %s, pnl_percent = %s
                    WHERE id = %s
                """, (close_price, exit_type, profit_loss, profit_loss_percent, position_id))
                
                conn.commit()
                
                # Update performance metrics
                self._update_performance_metrics()
                
                logger.info(f"Position {position_id} closed: {symbol} at {close_price}, P/L: {profit_loss:.2f}")
                return True
                
            except Exception as e:
                conn.rollback()
                logger.error(f"Error closing position: {e}")
                self.error_count += 1
                return False
            finally:
                cursor.close()
      def delete_signal_by_symbol(self, symbol, market_type):
    """Delete signals by symbol"""
    with self.get_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "DELETE FROM signals WHERE symbol = %s AND market_type = %s",
                (symbol, market_type)
            )
            deleted_count = cursor.rowcount
            conn.commit()
            
            logger.info(f"Deleted {deleted_count} signals for {symbol}")
            return deleted_count
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Error deleting signals: {e}")
            self.error_count += 1
            return 0
        finally:
            cursor.close()
    # =========================================================
    # ENHANCED TRADE HISTORY
    # =========================================================
  
    def get_trade_history(self, market_type: str = None, limit: int = 50, 
                         days_back: int = 30) -> List[Dict]:
        """Get trade history dengan advanced filtering"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                query = """
                    SELECT * FROM trade_history 
                    WHERE timestamp >= NOW() - INTERVAL %s days
                """
                params = [days_back]
                
                if market_type:
                    query += " AND market_type = %s"
                    params.append(market_type)
                
                query += " ORDER BY timestamp DESC LIMIT %s"
                params.append(limit)
                
                cursor.execute(query, params)
                columns = [desc[0] for desc in cursor.description]
                
                return [dict(zip(columns, row)) for row in cursor.fetchall()]
                
            except Exception as e:
                logger.error(f"Error getting trade history: {e}")
                self.error_count += 1
                return []
            finally:
                cursor.close()

    def get_performance_stats(self, days: int = 30) -> Dict[str, Any]:
        """Get comprehensive performance statistics"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total_trades,
                        COUNT(CASE WHEN profit_loss > 0 THEN 1 END) as winning_trades,
                        COUNT(CASE WHEN profit_loss <= 0 THEN 1 END) as losing_trades,
                        AVG(CASE WHEN profit_loss > 0 THEN profit_loss END) as avg_win,
                        AVG(CASE WHEN profit_loss <= 0 THEN profit_loss END) as avg_loss,
                        SUM(profit_loss) as total_pnl,
                        AVG(profit_loss_percent) as avg_return_percent
                    FROM trade_history 
                    WHERE timestamp >= NOW() - INTERVAL %s days
                """, (days,))
                
                result = cursor.fetchone()
                if not result:
                    return {}
                
                (total_trades, winning_trades, losing_trades, 
                 avg_win, avg_loss, total_pnl, avg_return_percent) = result
                
                # Calculate additional metrics
                win_rate = winning_trades / total_trades if total_trades > 0 else 0
                profit_factor = abs(avg_win * winning_trades) / abs(avg_loss * losing_trades) if losing_trades > 0 and avg_loss else float('inf')
                
                # Get best and worst trades
                cursor.execute("""
                    SELECT symbol, profit_loss, profit_loss_percent, timestamp
                    FROM trade_history 
                    WHERE timestamp >= NOW() - INTERVAL %s days
                    ORDER BY profit_loss DESC LIMIT 5
                """, (days,))
                best_trades = cursor.fetchall()
                
                cursor.execute("""
                    SELECT symbol, profit_loss, profit_loss_percent, timestamp
                    FROM trade_history 
                    WHERE timestamp >= NOW() - INTERVAL %s days
                    ORDER BY profit_loss ASC LIMIT 5
                """, (days,))
                worst_trades = cursor.fetchall()
                
                return {
                    'total_trades': total_trades,
                    'winning_trades': winning_trades,
                    'losing_trades': losing_trades,
                    'win_rate': win_rate,
                    'total_pnl': total_pnl,
                    'avg_win': avg_win or 0,
                    'avg_loss': avg_loss or 0,
                    'avg_return_percent': avg_return_percent or 0,
                    'profit_factor': profit_factor,
                    'best_trades': best_trades,
                    'worst_trades': worst_trades,
                    'period_days': days
                }
                
            except Exception as e:
                logger.error(f"Error getting performance stats: {e}")
                self.error_count += 1
                return {}
            finally:
                cursor.close()

    # =========================================================
    # PORTFOLIO ALLOCATIONS
    # =========================================================
    
    def save_portfolio_allocation(self, allocations: List[Dict[str, Any]]) -> bool:
        """Save portfolio allocations"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                # Delete old allocations for today
                cursor.execute("""
                    DELETE FROM portfolio_allocations 
                    WHERE optimization_date >= CURRENT_DATE
                """)
                
                # Insert new allocations
                for allocation in allocations:
                    cursor.execute("""
                        INSERT INTO portfolio_allocations (
                            symbol, market_type, allocation_percent, allocated_capital,
                            risk_category, score, expected_return, risk_adjustment
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        allocation.get('symbol'),
                        allocation.get('market_type', 'crypto'),
                        allocation.get('allocation_percent', 0),
                        allocation.get('allocated_capital', 0),
                        allocation.get('risk_category', 'MEDIUM'),
                        allocation.get('score', 0),
                        allocation.get('expected_return', 0),
                        allocation.get('risk_adjustment', 1.0)
                    ))
                
                conn.commit()
                logger.info(f"Saved {len(allocations)} portfolio allocations")
                return True
                
            except Exception as e:
                conn.rollback()
                logger.error(f"Error saving portfolio allocations: {e}")
                self.error_count += 1
                return False
            finally:
                cursor.close()

    def get_current_portfolio_allocations(self) -> List[Dict]:
        """Get current portfolio allocations"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    SELECT * FROM portfolio_allocations 
                    WHERE optimization_date >= CURRENT_DATE
                    ORDER BY allocation_percent DESC
                """)
                
                columns = [desc[0] for desc in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]
                
            except Exception as e:
                logger.error(f"Error getting portfolio allocations: {e}")
                self.error_count += 1
                return []
            finally:
                cursor.close()

    # =========================================================
    # BACKTEST RESULTS
    # =========================================================
    
    def save_backtest_result(self, result_data: Dict[str, Any]) -> bool:
        """Save backtest results"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                equity_curve = result_data.get('equity_curve', [])
                parameters = result_data.get('parameters', {})
                
                cursor.execute("""
                    INSERT INTO backtest_results (
                        symbol, market_type, strategy_name, timeframe,
                        total_trades, winning_trades, losing_trades, win_rate,
                        total_pnl, sharpe_ratio, max_drawdown, final_balance,
                        period_days, parameters, equity_curve
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    result_data.get('symbol'),
                    result_data.get('market_type', 'crypto'),
                    result_data.get('strategy_name', 'EnhancedStrategy'),
                    result_data.get('timeframe', '1h'),
                    result_data.get('total_trades', 0),
                    result_data.get('winning_trades', 0),
                    result_data.get('losing_trades', 0),
                    result_data.get('win_rate', 0),
                    result_data.get('total_pnl', 0),
                    result_data.get('sharpe_ratio', 0),
                    result_data.get('max_drawdown', 0),
                    result_data.get('final_balance', 0),
                    result_data.get('period_days', 0),
                    json.dumps(parameters),
                    json.dumps(equity_curve)
                ))
                
                conn.commit()
                logger.info(f"Backtest result saved for {result_data.get('symbol')}")
                return True
                
            except Exception as e:
                conn.rollback()
                logger.error(f"Error saving backtest result: {e}")
                self.error_count += 1
                return False
            finally:
                cursor.close()

    def get_backtest_results(self, symbol: str = None, limit: int = 10) -> List[Dict]:
        """Get backtest results"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                if symbol:
                    cursor.execute("""
                        SELECT * FROM backtest_results 
                        WHERE symbol = %s 
                        ORDER BY test_date DESC 
                        LIMIT %s
                    """, (symbol, limit))
                else:
                    cursor.execute("""
                        SELECT * FROM backtest_results 
                        ORDER BY test_date DESC 
                        LIMIT %s
                    """, (limit,))
                
                columns = [desc[0] for desc in cursor.description]
                results = []
                
                for row in cursor.fetchall():
                    result_dict = dict(zip(columns, row))
                    
                    # Parse JSON fields
                    if result_dict.get('parameters'):
                        try:
                            result_dict['parameters'] = json.loads(result_dict['parameters'])
                        except:
                            result_dict['parameters'] = {}
                    
                    if result_dict.get('equity_curve'):
                        try:
                            result_dict['equity_curve'] = json.loads(result_dict['equity_curve'])
                        except:
                            result_dict['equity_curve'] = []
                    
                    results.append(result_dict)
                
                return results
                
            except Exception as e:
                logger.error(f"Error getting backtest results: {e}")
                self.error_count += 1
                return []
            finally:
                cursor.close()

    # =========================================================
    # ML ANALYSIS STORAGE
    # =========================================================
    
    def save_ml_analysis(self, analysis_data: Dict[str, Any]) -> bool:
        """Save ML analysis results"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                feature_importance = analysis_data.get('feature_importance', {})
                prediction_metrics = analysis_data.get('prediction_metrics', {})
                risk_metrics = analysis_data.get('risk_metrics', {})
                
                cursor.execute("""
                    INSERT INTO ml_analysis (
                        symbol, market_type, traditional_score, ml_confidence,
                        combined_score, feature_importance, prediction_metrics, risk_metrics
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    analysis_data.get('symbol'),
                    analysis_data.get('market_type', 'crypto'),
                    analysis_data.get('traditional_score', 0),
                    analysis_data.get('ml_confidence', 0.5),
                    analysis_data.get('combined_score', 0),
                    json.dumps(feature_importance),
                    json.dumps(prediction_metrics),
                    json.dumps(risk_metrics)
                ))
                
                conn.commit()
                logger.debug(f"ML analysis saved for {analysis_data.get('symbol')}")
                return True
                
            except Exception as e:
                conn.rollback()
                logger.error(f"Error saving ML analysis: {e}")
                self.error_count += 1
                return False
            finally:
                cursor.close()

    # =========================================================
    # PERFORMANCE METRICS
    # =========================================================
    
    def _update_performance_metrics(self):
        """Update daily performance metrics"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                today = datetime.now().date()
                
                # Get today's trades
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total_trades,
                        COUNT(CASE WHEN profit_loss > 0 THEN 1 END) as winning_trades,
                        SUM(profit_loss) as total_pnl
                    FROM trade_history 
                    WHERE DATE(timestamp) = %s
                """, (today,))
                
                result = cursor.fetchone()
                if not result:
                    return
                
                total_trades, winning_trades, total_pnl = result
                
                win_rate = winning_trades / total_trades if total_trades > 0 else 0
                
                # Calculate additional metrics
                cursor.execute("""
                    SELECT 
                        AVG(CASE WHEN profit_loss > 0 THEN profit_loss END) as avg_profit,
                        AVG(CASE WHEN profit_loss <= 0 THEN profit_loss END) as avg_loss
                    FROM trade_history 
                    WHERE DATE(timestamp) = %s
                """, (today,))
                
                avg_result = cursor.fetchone()
                avg_profit, avg_loss = avg_result if avg_result else (0, 0)
                
                profit_factor = abs(avg_profit * winning_trades) / abs(avg_loss * (total_trades - winning_trades)) if avg_loss and (total_trades - winning_trades) > 0 else 0
                
                # Insert or update daily metrics
                cursor.execute("""
                    INSERT INTO performance_metrics (
                        metric_date, total_trades, winning_trades, total_pnl, win_rate,
                        avg_profit, avg_loss, profit_factor, daily_return
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (metric_date) 
                    DO UPDATE SET
                        total_trades = EXCLUDED.total_trades,
                        winning_trades = EXCLUDED.winning_trades,
                        total_pnl = EXCLUDED.total_pnl,
                        win_rate = EXCLUDED.win_rate,
                        avg_profit = EXCLUDED.avg_profit,
                        avg_loss = EXCLUDED.avg_loss,
                        profit_factor = EXCLUDED.profit_factor,
                        daily_return = EXCLUDED.daily_return,
                        created_at = CURRENT_TIMESTAMP
                """, (
                    today, total_trades, winning_trades, total_pnl, win_rate,
                    avg_profit or 0, avg_loss or 0, profit_factor, total_pnl
                ))
                
                conn.commit()
                
            except Exception as e:
                conn.rollback()
                logger.error(f"Error updating performance metrics: {e}")
                self.error_count += 1
            finally:
                cursor.close()

    def get_performance_metrics(self, days: int = 30) -> List[Dict]:
        """Get performance metrics untuk period tertentu"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    SELECT * FROM performance_metrics 
                    WHERE metric_date >= CURRENT_DATE - INTERVAL %s days
                    ORDER BY metric_date DESC
                """, (days,))
                
                columns = [desc[0] for desc in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]
                
            except Exception as e:
                logger.error(f"Error getting performance metrics: {e}")
                self.error_count += 1
                return []
            finally:
                cursor.close()

    # =========================================================
    # DATA MAINTENANCE AND CLEANUP
    # =========================================================
    
    def cleanup_old_data(self, days: int = 30):
        """Clean up old data dari semua tables"""
        try:
            results = {}
            
            # Clean up old signals
            signals_count = self.delete_old_signals(days)
            results['signals'] = signals_count
            
            # Clean up old trade history
            with self.get_connection() as conn:
                cursor = conn.cursor()
                try:
                    cursor.execute(
                        "DELETE FROM trade_history WHERE timestamp < NOW() - INTERVAL %s days",
                        (days,)
                    )
                    history_count = cursor.rowcount
                    results['trade_history'] = history_count
                    
                    # Clean up closed positions
                    cursor.execute(
                        "DELETE FROM positions WHERE status = 'closed' AND closed_at < NOW() - INTERVAL %s days",
                        (days,)
                    )
                    positions_count = cursor.rowcount
                    results['positions'] = positions_count
                    
                    # Clean up old backtest results
                    cursor.execute(
                        "DELETE FROM backtest_results WHERE test_date < NOW() - INTERVAL %s days",
                        (days * 3,)  # Keep backtests longer
                    )
                    backtest_count = cursor.rowcount
                    results['backtest_results'] = backtest_count
                    
                    # Clean up old ML analysis
                    cursor.execute(
                        "DELETE FROM ml_analysis WHERE analysis_date < NOW() - INTERVAL %s days",
                        (days * 7,)  # Keep ML analysis longer
                    )
                    ml_count = cursor.rowcount
                    results['ml_analysis'] = ml_count
                    
                    conn.commit()
                    
                except Exception as e:
                    conn.rollback()
                    logger.error(f"Error during data cleanup: {e}")
                    self.error_count += 1
                finally:
                    cursor.close()
            
            self.last_cleanup = datetime.now()
            logger.info(f"Data cleanup completed: {results}")
            return results
            
        except Exception as e:
            logger.error(f"Error in cleanup_old_data: {e}")
            self.error_count += 1
            return {}

    def get_database_stats(self) -> Dict[str, Any]:
        """Get database statistics"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                stats = {}
                tables = [
                    'signals', 'positions', 'trade_history', 'portfolio_allocations',
                    'backtest_results', 'ml_analysis', 'performance_metrics'
                ]
                
                for table in tables:
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    count = cursor.fetchone()[0]
                    stats[table] = count
                
                # Get recent activity
                cursor.execute("""
                    SELECT 
                        COUNT(*) as active_positions,
                        SUM(pnl) as total_open_pnl
                    FROM positions 
                    WHERE status = 'active'
                """)
                active_result = cursor.fetchone()
                stats['active_positions'] = active_result[0] if active_result else 0
                stats['total_open_pnl'] = active_result[1] if active_result else 0
                
                # Get today's trades
                cursor.execute("""
                    SELECT COUNT(*), COALESCE(SUM(profit_loss), 0)
                    FROM trade_history 
                    WHERE DATE(timestamp) = CURRENT_DATE
                """)
                today_result = cursor.fetchone()
                stats['today_trades'] = today_result[0] if today_result else 0
                stats['today_pnl'] = today_result[1] if today_result else 0
                
                # Add performance metrics
                stats['total_queries'] = self.query_count
                stats['total_errors'] = self.error_count
                stats['error_rate'] = self.error_count / max(1, self.query_count)
                stats['last_cleanup'] = self.last_cleanup
                
                return stats
                
            except Exception as e:
                logger.error(f"Error getting database stats: {e}")
                self.error_count += 1
                return {}
            finally:
                cursor.close()

    # =========================================================
    # UTILITY METHODS
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
        except (ValueError, TypeError):
            try:
                return str(data)
            except:
                return data

    def health_check(self) -> Dict[str, Any]:
        """Comprehensive database health check"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Test basic query
                cursor.execute("SELECT 1")
                basic_test = cursor.fetchone()[0] == 1
                
                # Check table counts
                cursor.execute("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public'
                """)
                tables = [row[0] for row in cursor.fetchall()]
                
                # Check connection metrics
                cursor.execute("SELECT count(*) FROM pg_stat_activity WHERE datname = current_database()")
                active_connections = cursor.fetchone()[0]
                
                cursor.close()
                
                return {
                    'status': 'healthy' if basic_test else 'unhealthy',
                    'basic_test': basic_test,
                    'tables_count': len(tables),
                    'tables': tables,
                    'active_connections': active_connections,
                    'total_queries': self.query_count,
                    'error_rate': self.error_count / max(1, self.query_count),
                    'last_cleanup': self.last_cleanup.isoformat() if self.last_cleanup else None
                }
                
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            self.error_count += 1
            return {
                'status': 'unhealthy',
                'error': str(e)
            }

# Example usage and testing
def test_tp_functionality():
    """Test function untuk verify TP1-TP3 functionality"""
    db = DatabaseHandler()
    
    print("🧪 Testing TP1-TP3 functionality...")
    
    # Test save position dengan TP1-TP3
    position_id = db.save_position(
        symbol="BTC/USDT",
        market_type="crypto", 
        action="LONG",
        entry_price=50000,
        tp1=52000,
        tp2=54000, 
        tp3=56000,
        sl=48000
    )
    
    print(f"✅ Position saved with ID: {position_id}")
    
    # Test get active positions
    positions = db.get_active_positions()
    print(f"✅ Active positions: {len(positions)}")
    
    for pos in positions:
        print(f"   Symbol: {pos['symbol']}, TP1: {pos['tp1']}, TP2: {pos['tp2']}, TP3: {pos['tp3']}")
    
    # Test partial TP
    if position_id:
        success = db.execute_partial_take_profit(position_id, 52000, 0.5)
        if success:
            print("✅ Partial TP executed successfully")
        else:
            print("❌ Partial TP execution failed")
    
    # Test close position
    if position_id:
        success = db.close_position(position_id, 53000, "test")
        if success:
            print("✅ Position closed successfully")
        else:
            print("❌ Position close failed")
    
    print("🎉 TP1-TP3 testing completed!")

if __name__ == "__main__":
    # Test the enhanced database handler
    db = DatabaseHandler()
    
    print("🚀 Testing Enhanced Database Handler...")
    
    # Test health check
    health = db.health_check()
    print(f"Health Check: {health}")
    
    # Test database stats
    stats = db.get_database_stats()
    print(f"Database Stats: {stats}")
    
    # Test performance stats
    performance = db.get_performance_stats(days=7)
    print(f"Performance Stats: {performance}")
    
    # Test TP functionality
    test_tp_functionality()
    
    print("✅ Enhanced Database Handler Testing Completed!")
