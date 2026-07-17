import pymysql

try:
    conn = pymysql.connect(
        host='localhost',
        port=3306,
        user='root',
        password='',
        database='zt_emr'
    )
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET requires_otp=0, failed_attempts=0, is_locked=0 WHERE username='admin'")
    conn.commit()
    
    cursor.execute("SELECT id, username, email, requires_otp, is_locked FROM users WHERE username='admin'")
    row = cursor.fetchone()
    if row:
        print(f"Admin fixed!")
        print(f"  Username:     {row[1]}")
        print(f"  Email:        {row[2]}")
        print(f"  Requires OTP: {row[3]}")
        print(f"  Is Locked:    {row[4]}")
        print("\nYou can now log in as admin without OTP.")
    conn.close()

except Exception as e:
    print(f"Error: {e}")
    print("\nMake sure MySQL is running in XAMPP and database 'zt_emr' exists.")
