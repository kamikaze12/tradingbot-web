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
from decimal import Decimal

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
        
        # Initialize performance monitoring
        self.query_count = 0
        self.error_count = 0
        self.last_cleanup = datetime.now()
        
        # Initialize database
        self._initialize_database()
        self.create_enhanced_tables()
        
        # Run migrations - FIXED: Tidak menggunakan __init__ untuk migrasi
        self._run_migrations()

    def _run_migrations(self):
        """Run all necessary database migrations"""
        try:
            self.migrate_positions_table()
            self.migrate_trade_history_table()
            logger.info("✅ All database migrations completed successfully")
        except Exception as e:
            logger.error(f"❌ Database migrations failed: {e}")
            # Jangan hentikan eksekusi jika migrasi gagal

    # =========================================================
    # ENHANCED CONNECTION MANAGEMENT
    # =========================================================
    
    def _initialize_database(self):
        """Initialize database dengan connection pool"""
        try:
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
            self.error_count += 1
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
               
                if all(key in secrets for key in ['DB_HOST', 'DB_USER', 'DB_PASSWORD', 'DB_NAME']):
                    params.update({
                        'host': secrets['DB_HOST'],
                        'user': secrets['DB_USER'],
                        'password': secrets['DB_PASSWORD'],
                        'dbname': secrets['DB_NAME'],
                        'port': int(secrets.get('DB_PORT', 5432))
                    })
                    return params
               
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
    # AUTO-MIGRATION FOR MISSING COLUMNS - ENHANCED
    # =========================================================
    
    def migrate_positions_table(self):
        """Automatically migrate positions table if columns are missing"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                columns_to_add = [
                    ('position_size', 'REAL DEFAULT 0.0'),
                    ('trailing_stop', 'REAL'),
                    ('trailing_distance', 'REAL DEFAULT 0'),
                    ('partial_tp_executed', 'JSONB DEFAULT \'[]\''),
                    ('risk_category', 'TEXT DEFAULT \'MEDIUM\''),
                    ('position_score', 'INTEGER DEFAULT 0'),
                    ('pnl', 'REAL DEFAULT 0'),
                    ('pnl_percent', 'REAL DEFAULT 0'),
                    ('closed_at', 'TIMESTAMP'),
                    ('close_reason', 'TEXT')
                ]
                
                for column_name, column_type in columns_to_add:
                    try:
                        cursor.execute("""
                            SELECT column_name 
                            FROM information_schema.columns 
                            WHERE table_name='positions' AND column_name=%s
                        """, (column_name,))
                        
                        if not cursor.fetchone():
                            logger.info(f"Adding missing column '{column_name}' to positions table")
                            cursor.execute(f"ALTER TABLE positions ADD COLUMN {column_name} {column_type}")
                            conn.commit()
                            logger.info(f"✅ Successfully added column '{column_name}'")
                            
                    except Exception as e:
                        logger.warning(f"Could not add column '{column_name}': {e}")
                        conn.rollback()
                        continue
                
                cursor.close()
                logger.info("✅ Positions table migration completed")
                
        except Exception as e:
            logger.error(f"Error during positions table migration: {e}")

    def migrate_trade_history_table(self):
        """Automatically migrate trade_history table if columns are missing"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                columns_to_add = [
                    ('position_size', 'REAL NOT NULL DEFAULT 0.0'),
                    ('profit_loss_percent', 'REAL'),
                    ('commission', 'REAL DEFAULT 0'),
                    ('slippage', 'REAL DEFAULT 0'),
                    ('type', 'TEXT'),
                    ('duration_minutes', 'INTEGER'),
                    ('risk_reward_ratio', 'REAL'),
                    ('position_score', 'INTEGER'),
                    ('exit_reason', 'TEXT'),
                    ('strategy_version', 'TEXT DEFAULT \'v2.0\'')
                ]
                
                for column_name, column_type in columns_to_add:
                    try:
                        cursor.execute("""
                            SELECT column_name 
                            FROM information_schema.columns 
                            WHERE table_name='trade_history' AND column_name=%s
                        """, (column_name,))
                        
                        if not cursor.fetchone():
                            logger.info(f"Adding missing column '{column_name}' to trade_history table")
                            cursor.execute(f"ALTER TABLE trade_history ADD COLUMN {column_name} {column_type}")
                            conn.commit()
                            logger.info(f"✅ Successfully added column '{column_name}' to trade_history")
                            
                    except Exception as e:
                        logger.warning(f"Could not add column '{column_name}' to trade_history: {e}")
                        conn.rollback()
                        continue
                
                cursor.close()
                logger.info("✅ Trade_history table migration completed")
                
        except Exception as e:
            logger.error(f"Error during trade_history table migration: {e}")

    # =========================================================
    # ENHANCED TABLE SCHEMA
    # =========================================================
    
    def create_enhanced_tables(self):
        """Create enhanced tables untuk semua features"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
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
                        position_size REAL DEFAULT 0.0,
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
                
                # Table: portfolio_allocations
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
                
                # Table: backtest_results
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
                
                # Table: ml_analysis
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
                
                # Table: market_regimes
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
                
                # Table: performance_metrics
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
                
                # Create indexes
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
            indexes = [
                ("signals_symbol_market_timestamp_idx", "signals (symbol, market_type, timestamp)"),
                ("positions_symbol_status_idx", "positions (symbol, status)"),
                ("positions_market_type_status_idx", "positions (market_type, status)"),
                ("positions_created_at_idx", "positions (created_at)"),
                ("trade_history_symbol_timestamp_idx", "trade_history (symbol, timestamp)"),
                ("trade_history_market_type_idx", "trade_history (market_type)"),
                ("trade_history_timestamp_idx", "trade_history (timestamp)"),
                ("portfolio_allocations_symbol_idx", "portfolio_allocations (symbol)"),
                ("portfolio_allocations_optimization_date_idx", "portfolio_allocations (optimization_date)"),
                ("backtest_results_symbol_idx", "backtest_results (symbol)"),
                ("backtest_results_test_date_idx", "backtest_results (test_date)"),
                ("ml_analysis_symbol_date_idx", "ml_analysis (symbol, analysis_date)"),
                ("market_regimes_symbol_regime_idx", "market_regimes (symbol, regime_type)"),
                ("market_regimes_detected_at_idx", "market_regimes (detected_at)")
            ]
            
            for index_name, index_def in indexes:
                cursor.execute(f"CREATE INDEX IF NOT EXISTS {index_name} ON {index_def}")
            
            logger.info("✅ All indexes created successfully")
            
        except Exception as e:
            logger.error(f"Error creating indexes: {e}")
            self.error_count += 1
            raise

    # =========================================================
    # ENHANCED SIGNALS MANAGEMENT
    # =========================================================
    
    def save_signal(self, data: Dict[str, Any]) -> Optional[int]:
        """Save enhanced signal dengan comprehensive data"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                converted_data = self._convert_numpy_types(data)
                
                pattern_details = converted_data.get('pattern_details', {})
                pattern_details_json = json.dumps(pattern_details) if isinstance(pattern_details, dict) else '{}'
                
                tp_probabilities = converted_data.get('tp_probabilities', {})
                tp_probabilities_json = json.dumps(tp_probabilities) if isinstance(tp_probabilities, dict) else '{}'
                
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
                    float(converted_data.get("entry_low")) if converted_data.get("entry_low") is not None else None,
                    float(converted_data.get("entry_high")) if converted_data.get("entry_high") is not None else None,
                    float(converted_data.get("tp1")) if converted_data.get("tp1") is not None else None,
                    float(converted_data.get("tp2")) if converted_data.get("tp2") is not None else None,
                    float(converted_data.get("tp3")) if converted_data.get("tp3") is not None else None,
                    float(converted_data.get("sl")) if converted_data.get("sl") is not None else None,
                    float(converted_data.get("current_price")) if converted_data.get("current_price") is not None else None,
                    float(converted_data.get("rsi")) if converted_data.get("rsi") is not None else None,
                    converted_data.get("trend"),
                    float(converted_data.get("volume_ratio")) if converted_data.get("volume_ratio") is not None else None,
                    float(converted_data.get("atr")) if converted_data.get("atr") is not None else None,
                    int(converted_data.get("score")) if converted_data.get("score") is not None else None,
                    bool(converted_data.get("hh", False)),
                    bool(converted_data.get("hl", False)),
                    bool(converted_data.get("lh", False)),
                    bool(converted_data.get("ll", False)),
                    converted_data.get("ema_trend", "NEUTRAL"),
                    int(converted_data.get("ema_score", 0)),
                    int(converted_data.get("pattern_score", 0)),
                    int(converted_data.get("momentum_score", 0)),
                    converted_data.get("market_regime", "unknown"),
                    float(converted_data.get("volatility", 0.02)),
                    converted_data.get("risk_category", "MEDIUM"),
                    float(converted_data.get("confidence", 0.5)),
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
                query = "SELECT * FROM signals WHERE timestamp >= NOW() - INTERVAL %s hours"
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

    # =========================================================
    # ENHANCED POSITIONS MANAGEMENT - FIXED
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
                # Konversi semua nilai float ke Python native float (bukan np.float64)
                entry_price = float(entry_price) if entry_price is not None else None
                tp1 = float(tp1) if tp1 is not None else None
                tp2 = float(tp2) if tp2 is not None else None
                tp3 = float(tp3) if tp3 is not None else None
                sl = float(sl) if sl is not None else None
                
                if current_price is None:
                    current_price = entry_price
                else:
                    current_price = float(current_price)
                    
                if entry_low is None:
                    entry_low = entry_price * 0.98
                else:
                    entry_low = float(entry_low)
                    
                if entry_high is None:
                    entry_high = entry_price * 1.02
                else:
                    entry_high = float(entry_high)
                    
                if position_size is None:
                    position_size = self._calculate_default_position_size(entry_price, sl)
                else:
                    position_size = float(position_size)
                
                trailing_distance = float(trailing_distance) if trailing_distance is not None else 0.0
                position_score = int(position_score) if position_score is not None else 0
                
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
        # Konversi ke Python native float
        entry_price = float(entry_price) if entry_price is not None else 0.0
        stop_loss = float(stop_loss) if stop_loss is not None else 0.0
        
        if entry_price <= 0 or stop_loss <= 0:
            return 0.0
            
        risk_amount = account_balance * risk_per_trade
        price_risk = abs(entry_price - stop_loss)
        
        if price_risk == 0:
            return 0.0
            
        position_size = risk_amount / price_risk
        
        max_position_value = account_balance * 0.2
        max_position_size = max_position_value / entry_price
        
        return min(position_size, max_position_size)

    def update_position_current_price(self, symbol: str, current_price: float) -> bool:
        """Update current price untuk position dan calculate PnL"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                # Konversi current_price ke float
                current_price = float(current_price) if current_price is not None else None
                
                if current_price is None:
                    logger.error(f"Invalid current_price for {symbol}")
                    return False
                
                cursor.execute(
                    "SELECT id, entry_price, action, position_size FROM positions WHERE symbol = %s AND status = 'active'",
                    (symbol,)
                )
                position = cursor.fetchone()
                
                if not position:
                    logger.warning(f"No active position found for {symbol}")
                    return False
                
                position_id, entry_price, action, position_size = position
                
                # Konversi nilai dari database ke float
                entry_price = float(entry_price) if entry_price is not None else 0.0
                position_size = float(position_size) if position_size is not None else 0.0
                
                if action == "LONG":
                    pnl = (current_price - entry_price) * position_size
                    pnl_percent = (current_price - entry_price) / entry_price * 100 if entry_price != 0 else 0
                else:
                    pnl = (entry_price - current_price) * position_size
                    pnl_percent = (entry_price - current_price) / entry_price * 100 if entry_price != 0 else 0
                
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

    def close_position(self, position_id: int, close_price: float, 
                      exit_type: str = "manual", commission: float = 0) -> bool:
        """Close position dan save ke trade history - FIXED VERSION"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                # Konversi close_price ke float
                close_price = float(close_price) if close_price is not None else None
                commission = float(commission) if commission is not None else 0.0
                
                if close_price is None:
                    logger.error(f"Invalid close_price for position {position_id}")
                    return False
                
                # Get position details
                cursor.execute("""
                    SELECT symbol, market_type, action, entry_price, position_size, 
                           sl, tp1, created_at
                    FROM positions WHERE id = %s
                """, (position_id,))
                
                position = cursor.fetchone()
                if not position:
                    logger.error(f"Position {position_id} not found")
                    return False
                
                symbol, market_type, action, entry_price, position_size, sl, tp1, created_at = position
                
                # Konversi nilai dari database ke float
                entry_price = float(entry_price) if entry_price is not None else 0.0
                position_size = float(position_size) if position_size is not None else 0.0
                sl = float(sl) if sl is not None else 0.0
                tp1 = float(tp1) if tp1 is not None else 0.0
                
                # Calculate final PnL
                if action == "LONG":
                    profit_loss = (close_price - entry_price) * position_size
                    profit_loss_percent = ((close_price - entry_price) / entry_price) * 100 if entry_price != 0 else 0
                else:
                    profit_loss = (entry_price - close_price) * position_size
                    profit_loss_percent = ((entry_price - close_price) / entry_price) * 100 if entry_price != 0 else 0
                
                # Calculate duration
                duration_minutes = 0
                if created_at:
                    duration_minutes = int((datetime.now() - created_at).total_seconds() / 60)
                
                # Calculate risk/reward ratio
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

    def get_active_positions(self, market_type: str = None) -> List[Dict]:
        """Get active positions dengan enhanced data"""
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
                    
                    # Konversi numeric values yang mungkin Decimal
                    for key, value in result_dict.items():
                        if isinstance(value, Decimal):
                            result_dict[key] = float(value)
                    
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

    def execute_partial_take_profit(self, position_id: int, tp_level: float, 
                                  close_percentage: float = 0.5) -> bool:
        """Execute partial take profit untuk position"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                # Konversi nilai ke float
                tp_level = float(tp_level) if tp_level is not None else None
                close_percentage = float(close_percentage) if close_percentage is not None else 0.5
                
                if tp_level is None:
                    logger.error(f"Invalid tp_level for position {position_id}")
                    return False
                
                cursor.execute(
                    "SELECT symbol, position_size, partial_tp_executed FROM positions WHERE id = %s",
                    (position_id,)
                )
                position = cursor.fetchone()
                
                if not position:
                    logger.error(f"Position {position_id} not found")
                    return False
                
                symbol, current_size, partial_tp_json = position
                
                # Konversi current_size ke float
                current_size = float(current_size) if current_size is not None else 0.0
                
                partial_tp_executed = []
                if partial_tp_json:
                    try:
                        partial_tp_executed = json.loads(partial_tp_json)
                    except:
                        partial_tp_executed = []
                
                close_size = current_size * close_percentage
                new_size = current_size - close_size
                
                partial_tp_executed.append({
                    'timestamp': datetime.now().isoformat(),
                    'price': tp_level,
                    'size': close_size,
                    'percentage': close_percentage
                })
                
                cursor.execute("""
                    UPDATE positions 
                    SET position_size = %s, partial_tp_executed = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (new_size, json.dumps(partial_tp_executed), position_id))
                
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

    # =========================================================
    # ENHANCED TRADE HISTORY
    # =========================================================
  
    def get_trade_history(self, market_type: str = None, limit: int = 50, 
                         days_back: int = 30) -> List[Dict]:
        """Get trade history dengan advanced filtering"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                query = "SELECT * FROM trade_history WHERE timestamp >= NOW() - INTERVAL %s days"
                params = [days_back]
                
                if market_type:
                    query += " AND market_type = %s"
                    params.append(market_type)
                
                query += " ORDER BY timestamp DESC LIMIT %s"
                params.append(limit)
                
                cursor.execute(query, params)
                columns = [desc[0] for desc in cursor.description]
                results = []
                
                for row in cursor.fetchall():
                    result_dict = dict(zip(columns, row))
                    
                    # Konversi Decimal ke float untuk hasil yang lebih bersih
                    for key, value in result_dict.items():
                        if isinstance(value, Decimal):
                            result_dict[key] = float(value)
                    
                    results.append(result_dict)
                
                return results
                
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
                
                # Konversi Decimal ke float
                avg_win = float(avg_win) if avg_win is not None else 0.0
                avg_loss = float(avg_loss) if avg_loss is not None else 0.0
                total_pnl = float(total_pnl) if total_pnl is not None else 0.0
                avg_return_percent = float(avg_return_percent) if avg_return_percent is not None else 0.0
                
                win_rate = winning_trades / total_trades if total_trades > 0 else 0
                profit_factor = abs(avg_win * winning_trades) / abs(avg_loss * losing_trades) if losing_trades > 0 and avg_loss else float('inf')
                
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
                    'period_days': days
                }
                
            except Exception as e:
                logger.error(f"Error getting performance stats: {e}")
                self.error_count += 1
                return {}
            finally:
                cursor.close()

    # =========================================================
    # UTILITY METHODS - ENHANCED
    # =========================================================
    
    def _convert_numpy_types(self, data):
        """Convert numpy types to native Python types - Enhanced version"""
        if isinstance(data, dict):
            return {k: self._convert_numpy_types(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._convert_numpy_types(item) for item in data]
        elif isinstance(data, tuple):
            return tuple(self._convert_numpy_types(item) for item in data)
        elif data is None:
            return None
        elif isinstance(data, (np.integer, np.int64, np.int32, np.int16, np.int8)):
            return int(data)
        elif isinstance(data, (np.floating, np.float64, np.float32, np.float16)):
            return float(data)
        elif isinstance(data, np.bool_):
            return bool(data)
        elif isinstance(data, np.ndarray):
            return data.tolist()
        elif isinstance(data, Decimal):
            return float(data)
        elif hasattr(data, "item"):
            try:
                return data.item()
            except:
                return data
        else:
            return data

    def _update_performance_metrics(self):
        """Update daily performance metrics"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                today = datetime.now().date()
                
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
                
                # Konversi ke Python native types
                total_trades = int(total_trades) if total_trades is not None else 0
                winning_trades = int(winning_trades) if winning_trades is not None else 0
                total_pnl = float(total_pnl) if total_pnl is not None else 0.0
                
                win_rate = winning_trades / total_trades if total_trades > 0 else 0
                
                cursor.execute("""
                    SELECT 
                        AVG(CASE WHEN profit_loss > 0 THEN profit_loss END) as avg_profit,
                        AVG(CASE WHEN profit_loss <= 0 THEN profit_loss END) as avg_loss
                    FROM trade_history 
                    WHERE DATE(timestamp) = %s
                """, (today,))
                
                avg_result = cursor.fetchone()
                avg_profit, avg_loss = avg_result if avg_result else (0, 0)
                
                avg_profit = float(avg_profit) if avg_profit is not None else 0.0
                avg_loss = float(avg_loss) if avg_loss is not None else 0.0
                
                profit_factor = abs(avg_profit * winning_trades) / abs(avg_loss * (total_trades - winning_trades)) if avg_loss and (total_trades - winning_trades) > 0 else 0
                
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

    def health_check(self) -> Dict[str, Any]:
        """Comprehensive database health check"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("SELECT 1")
                basic_test = cursor.fetchone()[0] == 1
                
                cursor.execute("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public'
                """)
                tables = [row[0] for row in cursor.fetchall()]
                
                cursor.execute("SELECT count(*) FROM pg_stat_activity WHERE datname = current_database()")
                active_connections = cursor.fetchone()[0]
                
                cursor.close()
                
                return {
                    'status': 'healthy' if basic_test else 'unhealthy',
                    'basic_test': basic_test,
                    'tables_count': len(tables),
                    'tables': tables,
                    'active_connections': int(active_connections),
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

# Test function dengan perbaikan
def test_database_functionality():
    """Test comprehensive database functionality"""
    db = DatabaseHandler()
    
    print("🧪 Testing Database Handler...")
    
    # Test health check
    health = db.health_check()
    print(f"Health Check: {health['status']}")
    print(f"Tables: {health['tables_count']}")
    
    # Test save position dengan numpy values
    print("\n🧪 Testing save_position with numpy values...")
    try:
        # Simulasikan numpy values yang mungkin datang dari pandas
        import numpy as np
        position_id = db.save_position(
            symbol="BTC/USDT",
            market_type="crypto", 
            action="LONG",
            entry_price=np.float64(50000.0),
            tp1=np.float64(52000.0),
            tp2=np.float64(54000.0), 
            tp3=np.float64(56000.0),
            sl=np.float64(48000.0)
        )
        
        print(f"✅ Position saved with ID: {position_id}")
        
        # Test get active positions
        positions = db.get_active_positions()
        print(f"✅ Active positions: {len(positions)}")
        
        # Test update current price dengan numpy
        print("\n🧪 Testing update_position_current_price...")
        success = db.update_position_current_price("BTC/USDT", np.float64(51000.0))
        if success:
            print("✅ Current price updated successfully")
        else:
            print("❌ Current price update failed")
        
        # Test close position
        if position_id:
            print("\n🧪 Testing close_position...")
            success = db.close_position(position_id, np.float64(53000.0), "test")
            if success:
                print("✅ Position closed successfully")
            else:
                print("❌ Position close failed")
        
        # Test performance stats
        performance = db.get_performance_stats(days=7)
        print(f"\n✅ Performance stats retrieved")
        print(f"   Total trades: {performance.get('total_trades', 0)}")
        print(f"   Total PnL: {performance.get('total_pnl', 0):.2f}")
        
        # Test save signal dengan numpy data
        print("\n🧪 Testing save_signal with numpy data...")
        signal_data = {
            "symbol": "ETH/USDT",
            "market_type": "crypto",
            "action": "LONG",
            "entry_low": np.float64(2500.0),
            "entry_high": np.float64(2550.0),
            "tp1": np.float64(2700.0),
            "tp2": np.float64(2800.0),
            "tp3": np.float64(2900.0),
            "sl": np.float64(2400.0),
            "current_price": np.float64(2520.0),
            "rsi": np.float64(65.5),
            "score": np.int64(85),
            "confidence": np.float64(0.8)
        }
        
        signal_id = db.save_signal(signal_data)
        if signal_id:
            print(f"✅ Signal saved with ID: {signal_id}")
        else:
            print("❌ Signal save failed")
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n🎉 Database testing completed!")

if __name__ == "__main__":
    test_database_functionality()
