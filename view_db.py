"""
Quick script to view all data in the VideoStats database.
Run: python view_db.py
"""

import sqlite3
from pathlib import Path

db_path = Path(__file__).parent / "videostats.db"

if not db_path.exists():
    print(f"Database file not found: {db_path}")
    exit(1)

conn = sqlite3.connect(str(db_path))
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

print("=" * 60)
print("VIDEOSTATS DATABASE CONTENTS")
print("=" * 60)

# Get all tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
tables = [row[0] for row in cursor.fetchall()]

for table in tables:
    print(f"\n{'=' * 60}")
    print(f"TABLE: {table}")
    print('=' * 60)
    
    # Get column names
    cursor.execute(f"PRAGMA table_info({table})")
    columns = [row[1] for row in cursor.fetchall()]
    print(f"Columns: {', '.join(columns)}")
    
    # Get all rows
    cursor.execute(f"SELECT * FROM {table}")
    rows = cursor.fetchall()
    
    if rows:
        print(f"\nRows ({len(rows)} total):")
        print("-" * 60)
        for i, row in enumerate(rows, 1):
            print(f"\nRow {i}:")
            for col in columns:
                value = row[col]
                print(f"  {col}: {value}")
    else:
        print("\n(No data)")

conn.close()
print("\n" + "=" * 60)

