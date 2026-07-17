"""
Run this once to create the 3 new tables for the Patient Portal:
- patient_accounts
- messages
- appointment_requests

Usage:
& "C:\\Users\\ALTO KIHAMBA\\AppData\\Local\\Python\\pythoncore-3.14-64\\python.exe" create_portal_tables.py
"""
import pymysql

conn = pymysql.connect(host='localhost', port=3306, user='root', password='', database='zt_emr')
cur = conn.cursor()

print("Creating patient_accounts table...")
cur.execute("""
CREATE TABLE IF NOT EXISTS patient_accounts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(80) UNIQUE NOT NULL,
    password_hash VARCHAR(256) NOT NULL,
    full_name VARCHAR(120) NOT NULL,
    email VARCHAR(120) UNIQUE NOT NULL,
    phone VARCHAR(30),
    date_of_birth DATE,
    gender VARCHAR(10),
    address VARCHAR(200),
    emergency_contact VARCHAR(120),
    blood_group VARCHAR(5),
    avatar VARCHAR(200),
    is_active BOOLEAN DEFAULT TRUE,
    patient_id INT,
    assigned_doctor_id INT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_login DATETIME,
    FOREIGN KEY (patient_id) REFERENCES patients(id),
    FOREIGN KEY (assigned_doctor_id) REFERENCES users(id)
)
""")

print("Creating messages table...")
cur.execute("""
CREATE TABLE IF NOT EXISTS messages (
    id INT AUTO_INCREMENT PRIMARY KEY,
    subject VARCHAR(200) NOT NULL,
    body TEXT NOT NULL,
    message_type VARCHAR(30) DEFAULT 'general',
    sender_patient_id INT,
    sender_staff_id INT,
    receiver_patient_id INT,
    receiver_staff_id INT,
    is_read BOOLEAN DEFAULT FALSE,
    read_at DATETIME,
    reply_to_id INT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (sender_patient_id) REFERENCES patient_accounts(id),
    FOREIGN KEY (sender_staff_id) REFERENCES users(id),
    FOREIGN KEY (receiver_patient_id) REFERENCES patient_accounts(id),
    FOREIGN KEY (receiver_staff_id) REFERENCES users(id),
    FOREIGN KEY (reply_to_id) REFERENCES messages(id)
)
""")

print("Creating appointment_requests table...")
cur.execute("""
CREATE TABLE IF NOT EXISTS appointment_requests (
    id INT AUTO_INCREMENT PRIMARY KEY,
    request_no VARCHAR(20) UNIQUE NOT NULL,
    patient_account_id INT NOT NULL,
    preferred_doctor_id INT,
    preferred_date DATETIME,
    preferred_date_2 DATETIME,
    reason TEXT NOT NULL,
    urgency VARCHAR(20) DEFAULT 'routine',
    status VARCHAR(20) DEFAULT 'pending',
    response_notes TEXT,
    reviewed_by INT,
    reviewed_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (patient_account_id) REFERENCES patient_accounts(id),
    FOREIGN KEY (preferred_doctor_id) REFERENCES users(id),
    FOREIGN KEY (reviewed_by) REFERENCES users(id)
)
""")

conn.commit()
print("\n✅ All 3 patient portal tables created successfully!")
print("   - patient_accounts")
print("   - messages")
print("   - appointment_requests")
conn.close()
