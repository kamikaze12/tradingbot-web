# Tambahkan di bagian ENHANCED POSITIONS MANAGEMENT
# Setelah method save_position dan sebelum update_position_current_price

def update_position(self, position_id: int, **kwargs) -> bool:
    """Update multiple position fields - VERSI PERBAIKAN"""
    with self.get_connection() as conn:
        cursor = conn.cursor()
        try:
            # Filter dan validasi fields yang boleh diupdate
            allowed_fields = {
                'current_price', 'pnl', 'pnl_percent', 'status', 
                'closed_at', 'close_reason', 'updated_at', 'sl',
                'tp1', 'tp2', 'tp3', 'trailing_stop', 'position_size'
            }
            
            # Hanya ambil fields yang diizinkan dan bukan None
            update_data = {}
            for key, value in kwargs.items():
                if key in allowed_fields and value is not None:
                    # Konversi tipe data jika perlu
                    if isinstance(value, (np.float64, np.int64)):
                        value = float(value)
                    update_data[key] = value
            
            if not update_data:
                logger.warning(f"No valid fields to update for position {position_id}")
                return False
            
            # Bangun query UPDATE dinamis
            set_clauses = []
            params = []
            
            for key, value in update_data.items():
                if key == 'updated_at':
                    set_clauses.append(f"{key} = CURRENT_TIMESTAMP")
                else:
                    set_clauses.append(f"{key} = %s")
                    params.append(value)
            
            # Tambah updated_at otomatis jika belum ada
            if 'updated_at' not in update_data:
                set_clauses.append("updated_at = CURRENT_TIMESTAMP")
            
            params.append(position_id)
            
            query = f"""
                UPDATE positions 
                SET {', '.join(set_clauses)}
                WHERE id = %s
            """
            
            cursor.execute(query, tuple(params))
            
            # Jika update current_price, hitung ulang PnL
            if 'current_price' in update_data:
                self._recalculate_pnl_for_position(position_id, conn)
            
            conn.commit()
            logger.info(f"✅ Updated position {position_id}: {list(update_data.keys())}")
            return True
            
        except Exception as e:
            conn.rollback()
            logger.error(f"❌ Error updating position {position_id}: {e}")
            self.error_count += 1
            return False
        finally:
            cursor.close()

def _recalculate_pnl_for_position(self, position_id: int, conn=None) -> bool:
    """Recalculate PnL untuk position - INTERNAL METHOD"""
    close_conn = False
    if conn is None:
        conn = psycopg2.connect(**self._get_connection_params())
        close_conn = True
    
    try:
        cursor = conn.cursor()
        
        # Dapatkan data posisi
        cursor.execute("""
            SELECT entry_price, current_price, action, position_size 
            FROM positions 
            WHERE id = %s
        """, (position_id,))
        
        row = cursor.fetchone()
        if not row:
            return False
        
        entry_price, current_price, action, position_size = row
        
        # Konversi ke float
        entry_price = float(entry_price) if entry_price else 0
        current_price = float(current_price) if current_price else entry_price
        position_size = float(position_size) if position_size else 0
        
        # Hitung PnL
        if action == "LONG":
            pnl = (current_price - entry_price) * position_size
            pnl_percent = ((current_price - entry_price) / entry_price * 100) if entry_price > 0 else 0
        else:  # SHORT
            pnl = (entry_price - current_price) * position_size
            pnl_percent = ((entry_price - current_price) / entry_price * 100) if entry_price > 0 else 0
        
        # Update PnL di database
        cursor.execute("""
            UPDATE positions 
            SET pnl = %s, pnl_percent = %s 
            WHERE id = %s
        """, (pnl, pnl_percent, position_id))
        
        if close_conn:
            conn.commit()
        
        logger.debug(f"Recalculated PnL for position {position_id}: {pnl:.2f} ({pnl_percent:.2f}%)")
        return True
        
    except Exception as e:
        logger.error(f"Error recalculating PnL for position {position_id}: {e}")
        return False
    finally:
        if cursor:
            cursor.close()
        if close_conn and conn:
            conn.close()

# Perbaiki method update_position_current_price agar lebih robust
def update_position_current_price(self, symbol: str, current_price: float) -> bool:
    """Update current price untuk ALL active positions dengan simbol tertentu"""
    with self.get_connection() as conn:
        cursor = conn.cursor()
        try:
            # Konversi current_price ke float
            current_price = float(current_price) if current_price is not None else None
            
            if current_price is None:
                logger.error(f"Invalid current_price for {symbol}")
                return False
            
            # Dapatkan semua posisi aktif dengan simbol ini
            cursor.execute(
                "SELECT id FROM positions WHERE symbol = %s AND status = 'active'",
                (symbol,)
            )
            positions = cursor.fetchall()
            
            if not positions:
                logger.warning(f"No active positions found for {symbol}")
                return False
            
            updated_count = 0
            for (position_id,) in positions:
                # Update dengan metode update_position yang baru
                success = self._update_single_position_price(position_id, current_price, conn)
                if success:
                    updated_count += 1
            
            conn.commit()
            logger.info(f"Updated {updated_count} active positions for {symbol}")
            return updated_count > 0
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Error updating current prices for {symbol}: {e}")
            self.error_count += 1
            return False
        finally:
            cursor.close()

def _update_single_position_price(self, position_id: int, current_price: float, conn=None) -> bool:
    """Update price untuk single position - INTERNAL METHOD"""
    close_conn = False
    if conn is None:
        conn = psycopg2.connect(**self._get_connection_params())
        close_conn = True
    
    try:
        cursor = conn.cursor()
        
        # Dapatkan data posisi
        cursor.execute("""
            SELECT entry_price, action, position_size 
            FROM positions 
            WHERE id = %s
        """, (position_id,))
        
        row = cursor.fetchone()
        if not row:
            return False
        
        entry_price, action, position_size = row
        
        # Konversi ke float
        entry_price = float(entry_price) if entry_price else 0
        position_size = float(position_size) if position_size else 0
        
        # Hitung PnL
        if action == "LONG":
            pnl = (current_price - entry_price) * position_size
            pnl_percent = ((current_price - entry_price) / entry_price * 100) if entry_price > 0 else 0
        else:  # SHORT
            pnl = (entry_price - current_price) * position_size
            pnl_percent = ((entry_price - current_price) / entry_price * 100) if entry_price > 0 else 0
        
        # Update di database
        cursor.execute("""
            UPDATE positions 
            SET current_price = %s, pnl = %s, pnl_percent = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (current_price, pnl, pnl_percent, position_id))
        
        if close_conn:
            conn.commit()
        
        return True
        
    except Exception as e:
        logger.error(f"Error updating single position {position_id}: {e}")
        return False
    finally:
        if cursor:
            cursor.close()
        if close_conn and conn:
            conn.close()

# Tambah method untuk mendapatkan position by ID
def get_position_by_id(self, position_id: int) -> Optional[Dict]:
    """Get position by ID"""
    with self.get_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT * FROM positions WHERE id = %s
            """, (position_id,))
            
            columns = [desc[0] for desc in cursor.description]
            row = cursor.fetchone()
            
            if not row:
                return None
            
            result_dict = dict(zip(columns, row))
            
            # Konversi numeric values
            for key, value in result_dict.items():
                if isinstance(value, Decimal):
                    result_dict[key] = float(value)
            
            if result_dict.get('partial_tp_executed'):
                try:
                    result_dict['partial_tp_executed'] = json.loads(result_dict['partial_tp_executed'])
                except:
                    result_dict['partial_tp_executed'] = []
            
            return result_dict
            
        except Exception as e:
            logger.error(f"Error getting position {position_id}: {e}")
            return None
        finally:
            cursor.close()

# Tambah method untuk update multiple positions sekaligus
def update_multiple_positions_prices(self, position_updates: List[Dict]) -> Dict:
    """
    Update multiple positions dengan harga baru
    
    Args:
        position_updates: List of dicts dengan format:
            [{'position_id': 1, 'current_price': 50000}, ...]
    
    Returns:
        Dict dengan hasil update: {'total': X, 'success': Y, 'failed': Z}
    """
    results = {'total': len(position_updates), 'success': 0, 'failed': 0, 'errors': []}
    
    with self.get_connection() as conn:
        cursor = conn.cursor()
        try:
            for update in position_updates:
                position_id = update.get('position_id')
                current_price = update.get('current_price')
                symbol = update.get('symbol')
                
                if not position_id or current_price is None:
                    results['failed'] += 1
                    results['errors'].append(f"Missing data for update: {update}")
                    continue
                
                try:
                    # Konversi harga ke float
                    current_price = float(current_price)
                    
                    # Coba update dengan ID
                    success = False
                    if position_id:
                        cursor.execute("""
                            SELECT id FROM positions WHERE id = %s AND status = 'active'
                        """, (position_id,))
                        
                        if cursor.fetchone():
                            # Gunakan method internal untuk update
                            if self._update_single_position_price(position_id, current_price, conn):
                                success = True
                    
                    # Fallback: coba update dengan symbol jika ID tidak ditemukan
                    if not success and symbol:
                        cursor.execute("""
                            UPDATE positions 
                            SET current_price = %s, updated_at = CURRENT_TIMESTAMP
                            WHERE symbol = %s AND status = 'active'
                        """, (current_price, symbol))
                        
                        if cursor.rowcount > 0:
                            success = True
                    
                    if success:
                        results['success'] += 1
                    else:
                        results['failed'] += 1
                        results['errors'].append(f"No active position found for: {update}")
                        
                except Exception as e:
                    results['failed'] += 1
                    results['errors'].append(f"Error updating {position_id or symbol}: {str(e)[:100]}")
                    conn.rollback()  # Rollback transaksi saat ini, lanjut ke berikutnya
            
            conn.commit()
            logger.info(f"Updated {results['success']}/{results['total']} positions")
            return results
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Error updating multiple positions: {e}")
            return results
        finally:
            cursor.close()

# Tambah method untuk cleanup old data
def cleanup_old_data(self, days_to_keep: int = 90) -> Dict:
    """Cleanup old data dari database untuk maintain performance"""
    with self.get_connection() as conn:
        cursor = conn.cursor()
        try:
            cleanup_date = datetime.now() - timedelta(days=days_to_keep)
            
            # Backup counts before cleanup
            cursor.execute("SELECT COUNT(*) FROM signals WHERE timestamp < %s", (cleanup_date,))
            old_signals = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM trade_history WHERE timestamp < %s", (cleanup_date,))
            old_history = cursor.fetchone()[0]
            
            # Archive old data (opsional - bisa diimplementasikan kemudian)
            # Untuk sekarang, hapus saja
            
            # Hapus old signals
            cursor.execute("DELETE FROM signals WHERE timestamp < %s", (cleanup_date,))
            deleted_signals = cursor.rowcount
            
            # Hapus old trade history
            cursor.execute("DELETE FROM trade_history WHERE timestamp < %s", (cleanup_date,))
            deleted_history = cursor.rowcount
            
            # Vacuum database untuk reclaim space
            cursor.execute("VACUUM ANALYZE")
            
            conn.commit()
            
            result = {
                'old_signals_count': old_signals,
                'old_history_count': old_history,
                'deleted_signals': deleted_signals,
                'deleted_history': deleted_history,
                'cleanup_date': cleanup_date.isoformat()
            }
            
            logger.info(f"✅ Database cleanup completed: {result}")
            self.last_cleanup = datetime.now()
            
            return result
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Error during database cleanup: {e}")
            return {'error': str(e)}
        finally:
            cursor.close()
