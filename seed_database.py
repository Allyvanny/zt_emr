"""
Import deploy_data.json into SQLite using raw SQL (no ORM issues).
Run on PythonAnywhere: python3 seed_database.py
"""
import json, os, sqlite3
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'zt_emr.db')

if not os.path.exists('deploy_data.json'):
    print("deploy_data.json not found! git pull first.")
    exit(1)

with open('deploy_data.json') as f:
    data = json.load(f)

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# Create all tables first via Flask
from app import app, db
with app.app_context():
    db.create_all()

# Import each table with raw SQL
for table_name, table_data in data.items():
    columns = table_data['columns']
    rows = table_data['rows']
    if not rows:
        print(f"  {table_name}: 0 rows (empty)")
        continue

    # Remove 'id' column to let SQLite auto-increment
    if 'id' in columns:
        idx = columns.index('id')
        columns = [c for i, c in enumerate(columns) if i != idx]
        rows = [[v for i, v in enumerate(row) if i != idx] for row in rows]

    placeholders = ', '.join(['?'] * len(columns))
    cols = ', '.join(f'`{c}`' for c in columns)
    sql = f"INSERT OR IGNORE INTO `{table_name}` ({cols}) VALUES ({placeholders})"

    count = 0
    for row in rows:
        # Convert ISO datetime strings to actual strings (SQLite stores them as text)
        clean = []
        for v in row:
            clean.append(v)
        try:
            cur.execute(sql, clean)
            count += 1
        except Exception as e:
            pass  # Skip rows with errors silently

    conn.commit()
    print(f"  {table_name}: {count}/{len(rows)} rows imported")

conn.close()
print("\nDone! Reload your web app.")
