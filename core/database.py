"""
Database initialization and management.

Provides SQLite connection and core table setup.
Modules add their own tables via setup_database() method.
"""

import sqlite3
import os
from datetime import date, datetime


def init_database(db_path='./nutrition_tracker.db'):
    """
    Initialize SQLite database with core tables.
    
    Modules will add their own tables via their setup_database() methods.
    
    Args:
        db_path: Path to SQLite database file
        
    Returns:
        sqlite3.Connection: Database connection
    """
    # Ensure directory exists
    db_dir = os.path.dirname(db_path)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir)
    
    conn = sqlite3.connect(db_path, check_same_thread=False)
    cursor = conn.cursor()
    
    # Core metadata table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS system_metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Track last processed lifelog
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS processing_state (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            last_processed_time DATETIME NOT NULL,
            last_processed_id TEXT,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Initialize processing state if not exists
    cursor.execute('SELECT COUNT(*) FROM processing_state')
    if cursor.fetchone()[0] == 0:
        cursor.execute('''
            INSERT INTO processing_state (last_processed_time, last_processed_id)
            VALUES (?, ?)
        ''', (datetime.utcnow().isoformat(), None))
    
    conn.commit()
    
    print("✅ Core database initialized")
    return conn


def get_last_processed_time(conn):
    """Get the last processed timestamp for Limitless polling"""
    cursor = conn.cursor()
    cursor.execute('SELECT last_processed_time FROM processing_state ORDER BY id DESC LIMIT 1')
    row = cursor.fetchone()
    return row[0] if row else datetime.utcnow().isoformat()


def update_last_processed_time(conn, timestamp, lifelog_id=None):
    """Update the last processed timestamp"""
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE processing_state 
        SET last_processed_time = ?, last_processed_id = ?, updated_at = ?
        WHERE id = (SELECT id FROM processing_state ORDER BY id DESC LIMIT 1)
    ''', (timestamp, lifelog_id, datetime.utcnow().isoformat()))
    conn.commit()
