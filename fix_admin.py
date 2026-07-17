import sqlite3
import os

# Try both possible database locations
paths = [
    os.path.join('instance', 'zt_emr.db'),
    'zt_emr.db',
    os.path.join(os.path.dirname(os.path.abspath(__file__)), 'zt_emr.db'),
    os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance', 'zt_emr.db'),
]

db_path = None
for p in paths:
    if os.path.exists(p):
        db_path = p
        print(f"Found database at: {p}")
        break

if not db_path:
    print("Database not found! Searched in:")
    for p in paths:
        print(f"  {p}")
else:
    conn = sqlite3.connect(db_path)
    conn.execute("UPDATE users SET requires_otp=0, failed_attempts=0, is_locked=0 WHERE username='admin'")
    conn.commit()
    
    # Verify
    cur = conn.execute("SELECT username, requires_otp, failed_attempts, is_locked FROM users WHERE username='admin'")
    row = cur.fetchone()
    print(f"Admin account: username={row[0]}, requires_otp={row[1]}, failed_attempts={row[2]}, is_locked={row[3]}")
    print("Done! Admin can now log in without OTP.")
    conn.close()
