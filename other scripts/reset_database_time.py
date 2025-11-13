# -*- coding: utf-8 -*-
"""
Reset the last_processed_time to start of today.

This will allow the system to pick up lifelogs from earlier in the day
that were missed during initial startup.
"""

import sqlite3
from datetime import datetime, date
import sys
import os

# Add project root to path
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from core.env_loader import get_env

db_path = get_env('DATABASE_PATH', './nutrition_tracker.db')

print("="*60)
print("RESET LAST PROCESSED TIME")
print("="*60)
print()

# Connect to database
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Check current value
cursor.execute('SELECT last_processed_time, last_processed_id FROM processing_state ORDER BY id DESC LIMIT 1')
current = cursor.fetchone()

print(f"Current last_processed_time: {current[0]}")
print(f"Current last_processed_id: {current[1]}")
print()

# Set to start of today (midnight)
today_start = datetime.combine(date.today(), datetime.min.time())
new_timestamp = today_start.isoformat()

print(f"Resetting to: {new_timestamp} (midnight today)")
print()

# Update
cursor.execute('''
    UPDATE processing_state 
    SET last_processed_time = ?, last_processed_id = NULL, updated_at = ?
    WHERE id = (SELECT id FROM processing_state ORDER BY id DESC LIMIT 1)
''', (new_timestamp, datetime.utcnow().isoformat()))

conn.commit()

# Verify
cursor.execute('SELECT last_processed_time, last_processed_id FROM processing_state ORDER BY id DESC LIMIT 1')
new_value = cursor.fetchone()

print(f"SUCCESS: Updated successfully!")
print(f"New last_processed_time: {new_value[0]}")
print(f"New last_processed_id: {new_value[1]}")
print()
print("="*60)
print("Now restart your application:")
print("  1. Stop the app (Ctrl+C)")
print("  2. Run: python main.py")
print()
print("It will now process lifelogs from midnight today forward,")
print("including your 12:51 PM 'log that' entry!")
print("="*60)

conn.close()