"""
Zero Trust EMR — Export AI Training Data for Supervisor Review
Author: Alto Dezdel Kiyamba | MUST BCS/25

Run this from your project folder:
& "C:\\Users\\ALTO KIHAMBA\\AppData\\Local\\Python\\pythoncore-3.14-64\\python.exe" export_training_data.py

It creates a folder "ai_training_data_export" containing:
  1. raw_activity_logs.csv      -> the raw data pulled from the database
  2. engineered_features.csv    -> the 6 features computed per time-window per user
  3. training_summary.txt       -> a plain-English summary report for your supervisor
"""
import os
import pymysql
import pandas as pd
import numpy as np
from datetime import timedelta

OUT_DIR = 'ai_training_data_export'
os.makedirs(OUT_DIR, exist_ok=True)

# ── Connect to the same MySQL database the app uses ──────────────────────────
conn = pymysql.connect(host='localhost', port=3306, user='root', password='', database='zt_emr')

# ── Step 1: Pull the RAW data exactly as the model sees it ──────────────────
query = """
    SELECT al.id, al.user_id, u.username, u.role, al.action, al.status,
           al.ip_address, al.timestamp
    FROM activity_logs al
    JOIN users u ON al.user_id = u.id
    ORDER BY al.timestamp
"""
raw_df = pd.read_sql(query, conn)
raw_path = os.path.join(OUT_DIR, 'raw_activity_logs.csv')
raw_df.to_csv(raw_path, index=False)
print(f"✅ Saved {len(raw_df)} raw log rows  ->  {raw_path}")

# ── Step 2: Re-run the SAME feature engineering the model uses ──────────────
def extract_features_from_logs(logs_df, user_id, window_minutes=60):
    user_logs = logs_df[logs_df['user_id'] == user_id].copy()
    if user_logs.empty:
        return []

    user_logs['timestamp'] = pd.to_datetime(user_logs['timestamp'])
    user_logs = user_logs.sort_values('timestamp')

    rows = []
    start, end = user_logs['timestamp'].min(), user_logs['timestamp'].max()
    current = start

    while current <= end:
        window_end = current + timedelta(minutes=window_minutes)
        window = user_logs[(user_logs['timestamp'] >= current) & (user_logs['timestamp'] < window_end)]

        if len(window) == 0:
            current += timedelta(minutes=window_minutes)
            continue

        hour = window['timestamp'].iloc[-1].hour
        rows.append({
            'user_id': user_id,
            'username': window['username'].iloc[0],
            'role': window['role'].iloc[0],
            'window_start': current,
            'window_end': window_end,
            'records_accessed':    len(window[window['action'].str.contains('patient', na=False)]),
            'failed_logins':       len(window[window['status'] == 'failed']),
            'off_hours_flag':      1 if (hour < 7 or hour > 20) else 0,
            'distinct_ips':        window['ip_address'].nunique(),
            'actions_per_minute':  round(len(window) / window_minutes, 4),
            'after_midnight_flag': 1 if (0 <= hour < 5) else 0,
        })
        current += timedelta(minutes=window_minutes)

    return rows

all_rows = []
for uid in raw_df['user_id'].unique():
    all_rows.extend(extract_features_from_logs(raw_df, uid))

feat_df = pd.DataFrame(all_rows)
feat_path = os.path.join(OUT_DIR, 'engineered_features.csv')
feat_df.to_csv(feat_path, index=False)
print(f"✅ Saved {len(feat_df)} engineered feature rows  ->  {feat_path}")

# ── Step 3: Write a plain-English summary for your supervisor ───────────────
summary_path = os.path.join(OUT_DIR, 'training_summary.txt')
with open(summary_path, 'w') as f:
    f.write("ZERO TRUST EMR — AI MODEL TRAINING DATA SUMMARY\n")
    f.write("Author: Alto Dezdel Kiyamba | MUST BCS/25\n")
    f.write("="*60 + "\n\n")

    f.write("1. DATA SOURCE\n")
    f.write(f"   Database table: activity_logs (joined with users)\n")
    f.write(f"   Total raw log entries used: {len(raw_df)}\n")
    f.write(f"   Number of distinct users:   {raw_df['user_id'].nunique()}\n")
    f.write(f"   Date range: {raw_df['timestamp'].min()}  to  {raw_df['timestamp'].max()}\n\n")

    f.write("   Users included:\n")
    for _, row in raw_df.groupby(['username','role']).size().reset_index(name='log_count').iterrows():
        f.write(f"     - {row['username']:15s} ({row['role']:15s}) : {row['log_count']} log entries\n")
    f.write("\n")

    f.write("2. FEATURE ENGINEERING\n")
    f.write("   Raw logs are grouped into 60-minute rolling windows per user.\n")
    f.write("   For each window, 6 behavioural features are computed:\n")
    f.write("     1. records_accessed    - patient records opened in the window\n")
    f.write("     2. failed_logins       - number of failed actions/logins\n")
    f.write("     3. off_hours_flag      - 1 if activity is before 7am or after 8pm\n")
    f.write("     4. distinct_ips        - number of different IP addresses used\n")
    f.write("     5. actions_per_minute  - speed/intensity of activity\n")
    f.write("     6. after_midnight_flag - 1 if activity is between 12am-5am\n\n")
    f.write(f"   Total feature vectors (training rows) produced: {len(feat_df)}\n\n")

    if len(feat_df) > 0:
        f.write("   Feature statistics:\n")
        f.write(feat_df[['records_accessed','failed_logins','off_hours_flag',
                          'distinct_ips','actions_per_minute','after_midnight_flag']]
                          .describe().round(3).to_string())
        f.write("\n\n")

    f.write("3. MODEL\n")
    f.write("   Algorithm: Isolation Forest (unsupervised anomaly detection, scikit-learn)\n")
    f.write("   Why unsupervised: we do not have labelled 'attack' examples, so the model\n")
    f.write("   learns what NORMAL staff behaviour looks like and flags anything that\n")
    f.write("   deviates significantly as higher risk.\n\n")

    f.write("4. FILES IN THIS EXPORT\n")
    f.write("   raw_activity_logs.csv     - the exact raw rows pulled from the database\n")
    f.write("   engineered_features.csv   - the 6-feature vectors computed from those rows\n")
    f.write("   training_summary.txt      - this report\n")

print(f"✅ Saved summary report          ->  {summary_path}")
print(f"\n📁 Everything is in the folder: {os.path.abspath(OUT_DIR)}")
print("   Show your supervisor these 3 files — they explain exactly what data trained the model.")

conn.close()
