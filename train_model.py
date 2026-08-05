"""
Zero Trust EMR — AI Model Training Script v3
Trains an Isolation Forest on 12 behavioural features extracted from real activity logs.
Author: Alto Dezdel Kiyamba | MUST BCS/25

═══════════════════════════════════════════════════════════════════════════════
ADVANCED CONCEPT — Why Isolation Forest?
═══════════════════════════════════════════════════════════════════════════════
Isolation Forest is an UNSUPERVISED anomaly detection algorithm. This means:

  1. It does NOT need labelled data (no "this is normal" / "this is attack").
     It figures out what's abnormal by itself — perfect for security monitoring
     where you can't easily label every user session.

  2. HOW IT WORKS — "Isolation" principle:
     Anomalies are RARE and DIFFERENT. If you randomly cut (split) the data
     repeatedly, anomalies get isolated in fewer cuts than normal points.

     Think of it like this:
     ┌─────────────────────────────────────────┐
     │  Normal data: densely packed together    │
     │  Anomaly:     far away from the crowd   │
     │                                         │
     │  To "isolate" an anomaly, you need FEW  │
     │  random cuts (short path in the tree).   │
     │  To isolate a normal point, you need     │
     │  MANY cuts (long path in the tree).      │
     └─────────────────────────────────────────┘

     The shorter the average path to isolate a point → the more anomalous it is.

  3. It builds MANY random trees (n_estimators=250). Each tree randomly splits
     features. Averaging across many trees reduces variance and gives robust
     anomaly scores. More trees = more stable scores.

  4. The output is an anomaly SCORE (not a probability). Negative = normal,
     positive = anomalous. We convert this to a 0–1 risk score.

═══════════════════════════════════════════════════════════════════════════════
ADVANCED CONCEPT — StandardScaler (Feature Scaling)
═══════════════════════════════════════════════════════════════════════════════
StandardScaler transforms each feature to have:
  - Mean (average) = 0
  - Standard deviation = 1

Formula: z = (x - mean) / std_dev

WHY IS THIS CRITICAL?
  Our 12 features have VERY different scales:
    - actions_per_minute: ~0.02 to 2.0
    - records_accessed:   ~0 to 60
    - session_duration:   ~0 to 55 minutes

  Without scaling, features with LARGER numbers dominate the model.
  Isolation Forest uses distance-based splitting, so if one feature ranges
  0–60 and another 0–2, the 0–60 feature would always "win" the splits.

  After scaling, all features contribute equally.

═══════════════════════════════════════════════════════════════════════════════
ADVANCED CONCEPT — Contamination Parameter
═══════════════════════════════════════════════════════════════════════════════
contamination=0.06 means we TELL the model "assume about 6% of your data
is anomalous."

This is NOT a random guess. It's based on:
  - Healthcare security benchmarks: ~5-10% of sessions show unusual patterns
  - Our synthetic training data: 60 anomalous out of 860 total = ~7%
  - Too high → too many false alarms; Too low → misses real threats

The contamination sets the DECISION BOUNDARY — the threshold that separates
normal from anomalous. The model will flag the most extreme 6% as anomalies.

═══════════════════════════════════════════════════════════════════════════════
ADVANCED CONCEPT — Rolling Window Feature Extraction
═══════════════════════════════════════════════════════════════════════════════
Instead of looking at ALL of a user's history at once, we use a SLIDING WINDOW
of 60 minutes. This is called a "rolling window" or "sliding window" approach.

  |---- window 1 ----|
       |---- window 2 ----|
            |---- window 3 ----|

Each window captures a SNAPSHOT of recent behavior. This is important because:
  - An attacker's behavior CHANGES over time
  - Old data becomes less relevant
  - We detect anomalies in RECENT activity, not historical patterns

The window moves forward by the window size (non-overlapping in this code),
creating multiple training samples per user.
"""

import os, sys, json
import numpy as np
from datetime import datetime, timedelta

try:
    import pandas as pd
    _HAS_PANDAS = True
except ImportError:
    _HAS_PANDAS = False

# ── Database connection ──────────────────────────────────────────────────────
try:
    import pymysql
    conn = pymysql.connect(host='localhost', port=3306,
                           user='root', password='', database='zt_emr')
    DB = 'mysql'
    print("Connected to MySQL (XAMPP)")
except:
    import sqlite3
    db_paths = [os.path.join('instance', 'zt_emr.db'), 'zt_emr.db']
    conn = None
    for p in db_paths:
        if os.path.exists(p):
            conn = sqlite3.connect(p)
            DB = 'sqlite'
            print(f"Connected to SQLite: {p}")
            break
    if not conn:
        print("Database not found. Run the app first.")
        sys.exit(1)

cursor = conn.cursor()

# ── 12 Feature names ────────────────────────────────────────────────────────
FEATURE_NAMES = [
    'records_accessed', 'failed_logins', 'off_hours_flag', 'distinct_ips',
    'actions_per_minute', 'after_midnight', 'location_changed',
    'session_duration_min', 'distinct_resources', 'same_time_new_location',
    'rapid_fire_ratio', 'role_deviation'
]

ROLE_RESOURCES = {
    'admin':         set(),
    'doctor':        {'patient', 'appointment', 'medical_record', 'prescription', 'lab'},
    'nurse':         {'patient', 'appointment', 'medical_record'},
    'receptionist':  {'patient', 'appointment'},
    'pharmacist':    {'prescription', 'drug', 'patient'},
    'lab_technician':{'lab', 'patient'},
}

# ── Step 1: Extract raw logs ─────────────────────────────────────────────────
print("\nStep 1: Extracting activity logs...")

try:
    cursor.execute("""
        SELECT al.user_id, al.action, al.status, al.ip_address, al.timestamp,
               u.role, u.username, al.resource, al.session_id
        FROM activity_logs al
        JOIN users u ON al.user_id = u.id
        ORDER BY al.timestamp
    """)
    rows = cursor.fetchall()
    print(f"   Found {len(rows)} activity log entries")
except Exception as _e:
    rows = []
    print(f"   No activity log data ({_e}). Using synthetic training data...")

if len(rows) < 10:
    print("Very few logs found. Using synthetic training data...")
    SYNTHETIC = True
else:
    SYNTHETIC = False

# Also get last known IPs per user for location_changed feature
try:
    cursor.execute("SELECT id, last_ip FROM users WHERE last_ip IS NOT NULL")
    last_ips = {row[0]: row[1] for row in cursor.fetchall()}
except Exception:
    last_ips = {}

# ── Step 2: Feature engineering (12 features) ────────────────────────────────
print("\nStep 2: Engineering 12 features...")

def extract_features_from_logs(logs_df, user_id, user_role, last_ip, window_minutes=60):
    """Extract 12 behavioural features for a user in a rolling window."""
    if logs_df.empty:
        return [np.zeros(12)]

    user_logs = logs_df[logs_df['user_id'] == user_id].copy()
    if user_logs.empty:
        return [np.zeros(12)]

    user_logs['timestamp'] = pd.to_datetime(user_logs['timestamp'])
    user_logs = user_logs.sort_values('timestamp')

    start = user_logs['timestamp'].min()
    end   = user_logs['timestamp'].max()
    current = start
    feature_vectors = []

    while current <= end:
        window_end = current + timedelta(minutes=window_minutes)
        window = user_logs[
            (user_logs['timestamp'] >= current) &
            (user_logs['timestamp'] < window_end)
        ]

        if len(window) == 0:
            current += timedelta(minutes=window_minutes)
            continue

        hour = window['timestamp'].iloc[-1].hour

        # F1: records accessed
        records_accessed = len(window[window['action'].str.contains('patient', na=False)])

        # F2: failed logins
        failed_logins = len(window[window['status'] == 'failed'])

        # F3: off-hours
        off_hours_flag = 1.0 if (hour < 7 or hour > 20) else 0.0

        # F4: distinct IPs
        distinct_ips = window['ip_address'].nunique()

        # F5: actions per minute
        actions_per_minute = len(window) / window_minutes

        # F6: after midnight
        after_midnight = 1.0 if (0 <= hour < 5) else 0.0

        # F7: location changed
        location_changed = 0.0
        if last_ip:
            recent_ips = set(window['ip_address'].dropna())
            if last_ip not in recent_ips and recent_ips:
                location_changed = 1.0

        # F8: session duration
        timestamps = window['timestamp'].sort_values()
        if len(timestamps) >= 2:
            session_duration = (timestamps.iloc[-1] - timestamps.iloc[0]).total_seconds() / 60.0
        else:
            session_duration = 0.0
        session_duration = min(session_duration, window_minutes)

        # F9: distinct resources
        resource_types = set()
        for r in window['action'].dropna():
            resource_types.add(r.split('_')[0].split('/')[0].lower())
        distinct_resources = len(resource_types)

        # F10: same time different location
        same_time_new_location = 0.0
        ip_groups = window.groupby('ip_address')
        if ip_groups.ngroups >= 2:
            ip_ts = {ip: grp['timestamp'].tolist() for ip, grp in ip_groups}
            ips = list(ip_ts.keys())
            for i in range(len(ips)):
                for j in range(i+1, len(ips)):
                    for t1 in ip_ts[ips[i]]:
                        for t2 in ip_ts[ips[j]]:
                            if abs((t1 - t2).total_seconds()) < 600:
                                same_time_new_location = 1.0
                                break
                        if same_time_new_location:
                            break
                    if same_time_new_location:
                        break
                if same_time_new_location:
                    break

        # F11: rapid-fire ratio
        ts_sorted = window['timestamp'].sort_values().tolist()
        rapid_count = 0
        for k in range(1, len(ts_sorted)):
            if (ts_sorted[k] - ts_sorted[k-1]).total_seconds() < 5:
                rapid_count += 1
        rapid_fire_ratio = rapid_count / max(len(ts_sorted) - 1, 1)

        # F12: role deviation
        role_deviation = 0.0
        allowed = ROLE_RESOURCES.get(user_role, set())
        if allowed:
            for act in window['action'].dropna():
                act_lower = act.lower()
                if not any(a in act_lower for a in allowed):
                    role_deviation = 1.0
                    break

        feature_vectors.append([
            records_accessed, failed_logins, off_hours_flag, distinct_ips,
            actions_per_minute, after_midnight, location_changed,
            session_duration, distinct_resources, same_time_new_location,
            rapid_fire_ratio, role_deviation
        ])
        current += timedelta(minutes=window_minutes)

    return feature_vectors if feature_vectors else [np.zeros(12)]


if not SYNTHETIC:
    if not _HAS_PANDAS:
        print("   pandas not installed — falling back to synthetic training data.")
        SYNTHETIC = True
    else:
        cols = ['user_id','action','status','ip_address','timestamp','role','username','resource','session_id']
        logs_df = pd.DataFrame(rows, columns=cols)

        all_features = []
        user_ids = logs_df['user_id'].unique()

        for uid in user_ids:
            uname = logs_df[logs_df['user_id']==uid]['username'].iloc[0]
            role  = logs_df[logs_df['user_id']==uid]['role'].iloc[0]
            lip   = last_ips.get(uid, None)
            feats = extract_features_from_logs(logs_df, uid, role, lip)
            all_features.extend(feats)
            print(f"   User {uname:15s} ({role:15s}): {len(feats)} feature windows")

        X = np.array(all_features)
else:
    # ════════════════════════════════════════════════════════════════════
    # ADVANCED: Synthetic Data Generation
    # ════════════════════════════════════════════════════════════════════
    # We create fake data that represents 4 behavioral patterns.
    # Each pattern has different statistical distributions for the 12 features.
    # The goal: teach the Isolation Forest to distinguish normal from anomalous.

    # WHY use different numpy distributions?
    #   - rng.integers(a, b): uniform integers (all values equally likely)
    #   - rng.binomial(n, p): number of successes in n trials with probability p
    #     Perfect for binary flags (0 or 1) with a known probability
    #   - rng.uniform(a, b): continuous values between a and b (flat distribution)
    #   - np.zeros(n): all zeros (for features that should be 0 in this pattern)

    rng = np.random.default_rng(42)  # Fixed seed ensures REPRODUCIBILITY

    # ── Group 1: Normal daytime (600 samples) ──────────────────────────
    # Represents: Doctors, nurses, pharmacists during regular hours (7am-8pm)
    n_day = 600
    normal_day = np.column_stack([
        rng.integers(1, 15, n_day),         # F1: records_accessed (low: 1-15)
        rng.binomial(1, 0.03, n_day),        # F2: failed_logins (3% chance — rare typos)
        np.zeros(n_day),                     # F3: off_hours_flag (0 = daytime)
        np.ones(n_day, dtype=float),         # F4: distinct_ips (1 = same office)
        rng.uniform(0.02, 0.25, n_day),     # F5: actions_per_minute (slow, human pace)
        np.zeros(n_day),                     # F6: after_midnight (0 = not midnight)
        np.zeros(n_day),                     # F7: location_changed (0 = usual location)
        rng.uniform(5, 55, n_day),           # F8: session_duration (5-55 min)
        rng.integers(1, 5, n_day),           # F9: distinct_resources (1-4 types)
        np.zeros(n_day),                     # F10: same_time_new_location (impossible)
        rng.uniform(0, 0.15, n_day),         # F11: rapid_fire_ratio (0-15%, human speed)
        np.zeros(n_day),                     # F12: role_deviation (0 = following role)
    ]).astype(float)

    n_night = 150
    normal_night = np.column_stack([
        rng.integers(0, 6, n_night), rng.binomial(1, 0.05, n_night),
        np.ones(n_night, dtype=float), np.ones(n_night, dtype=float),
        rng.uniform(0.01, 0.1, n_night), np.zeros(n_night),
        rng.binomial(1, 0.1, n_night), rng.uniform(3, 30, n_night),
        rng.integers(1, 3, n_night), np.zeros(n_night),
        rng.uniform(0, 0.08, n_night), np.zeros(n_night),
    ]).astype(float)

    n_mid = 50
    normal_mid = np.column_stack([
        rng.integers(0, 3, n_mid), rng.binomial(1, 0.02, n_mid),
        np.ones(n_mid, dtype=float), np.ones(n_mid, dtype=float),
        rng.uniform(0.005, 0.05, n_mid), np.ones(n_mid, dtype=float),
        rng.binomial(1, 0.15, n_mid), rng.uniform(2, 20, n_mid),
        rng.integers(0, 2, n_mid), np.zeros(n_mid),
        rng.uniform(0, 0.05, n_mid), np.zeros(n_mid),
    ]).astype(float)

    # ── Group 4: Anomalous patterns (60 samples) ───────────────────────
    # Represents: Attack scenarios — credential theft, brute force, data exfil
    # NOTICE how every feature is at an EXTREME value compared to normal groups.
    # This is what the Isolation Forest learns to detect.
    n_anom = 60
    anom = np.column_stack([
        rng.integers(20, 60, n_anom),        # F1: 20-60 records (mass data access!)
        rng.integers(3, 15, n_anom),         # F2: 3-15 failed logins (brute force!)
        rng.binomial(1, 0.8, n_anom),        # F3: 80% off-hours (attackers work at night)
        rng.integers(3, 8, n_anom),          # F4: 3-8 IPs (proxy/VPN hopping!)
        rng.uniform(0.5, 2.0, n_anom),       # F5: 0.5-2.0 actions/min (automated scripts!)
        rng.binomial(1, 0.7, n_anom),        # F6: 70% after midnight
        rng.binomial(1, 0.9, n_anom),        # F7: 90% location changed!
        rng.uniform(0.5, 5, n_anom),         # F8: 0.5-5 min (very short = automated)
        rng.integers(5, 15, n_anom),         # F9: 5-15 resources (accessing everything!)
        rng.binomial(1, 0.8, n_anom),        # F10: 80% same-time-different-location
        rng.uniform(0.4, 1.0, n_anom),       # F11: 40-100% rapid-fire (bot activity!)
        rng.binomial(1, 0.7, n_anom),        # F12: 70% role deviation (nurse accessing admin)
    ]).astype(float)

    X = np.clip(np.vstack([normal_day, normal_night, normal_mid, anom]), 0, None)

X = np.clip(X, 0, None)
print(f"\n   Total feature vectors: {len(X)}")
print(f"   Feature shape: {X.shape}")

# ── Step 3: Train Isolation Forest ───────────────────────────────────────────
print("\nStep 3: Training Isolation Forest model (12 features)...")
from sklearn.ensemble import IsolationForest
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

# ADVANCED: StandardScaler — transforms features to mean=0, std=1
# This is CRITICAL for distance-based algorithms like Isolation Forest.
# Without it, features with larger ranges (e.g. records_accessed: 0-60)
# would dominate over features with smaller ranges (e.g. actions_per_minute: 0-2).
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)  # fit() learns mean/std, transform() applies them

# ADVANCED: train_test_split — evaluate on unseen data
# We hold out 20% of data to test if the model generalizes.
# If it performs well on training but poorly on test → overfitting.
if len(X_scaled) >= 20:
    X_train, X_test = train_test_split(X_scaled, test_size=0.2, random_state=42)
else:
    X_train = X_scaled
    X_test  = X_scaled

# ADVANCED: Isolation Forest Parameters
#   n_estimators=250:  Build 250 random trees. More trees = more stable scores.
#                      But diminishing returns past ~200. We use 250 for robustness.
#   contamination=0.06: "About 6% of training data is anomalous."
#                       This sets the decision boundary (threshold).
#                       Too high → too many false alarms
#                       Too low → misses real attacks
#   max_samples='auto': Each tree trains on min(256, n_samples) data points.
#                       Smaller subsamples = more diverse trees = better isolation.
#   n_jobs=-1: Use ALL CPU cores for parallel training.
model = IsolationForest(
    n_estimators=250,
    contamination=0.06,
    max_samples='auto',
    random_state=42,
    n_jobs=-1
)
model.fit(X_train)
print(f"   Model trained on {len(X_train)} samples")
print(f"   Trees: 250 | Contamination: 6%")

# ── Step 4: Evaluate ─────────────────────────────────────────────────────────
print("\nStep 4: Evaluating model...")

# ADVANCED: score_samples() returns raw anomaly scores
# Range: typically [-0.5, 0.5]
#   - More NEGATIVE = more anomalous (harder to isolate in random trees)
#   - More POSITIVE = more normal (easier to isolate)
#
# predict() returns -1 (anomaly) or +1 (normal) based on the contamination threshold.
train_scores = model.score_samples(X_train)
test_scores  = model.score_samples(X_test)
train_preds  = model.predict(X_train)
test_preds   = model.predict(X_test)

def to_risk(scores):
    """Convert raw Isolation Forest scores to 0-1 risk scores.
    
    The raw scores are in [-0.5, 0.5] where:
      -0.5 = maximum anomaly (risk = 1.0)
       0.0 = uncertain (risk = 0.5)
       0.5 = maximum normal (risk = 0.0)
    
    Formula: risk = 1 - (raw + 0.5)
    Then clamp to [0, 1] for safety.
    """
    return np.clip(1 - (scores + 0.5), 0, 1)

train_risk = to_risk(train_scores)
test_risk  = to_risk(test_scores)

print(f"\n   === TRAINING SET ===")
print(f"   Samples:          {len(X_train)}")
print(f"   Normal (1):       {(train_preds==1).sum()}")
print(f"   Anomalous (-1):   {(train_preds==-1).sum()}")
print(f"   Avg risk score:   {train_risk.mean():.3f}")

print(f"\n   === TEST SET ===")
print(f"   Samples:          {len(X_test)}")
print(f"   Normal (1):       {(test_preds==1).sum()}")
print(f"   Anomalous (-1):   {(test_preds==-1).sum()}")
print(f"   Avg risk score:   {test_risk.mean():.3f}")

levels = {'low':0,'medium':0,'high':0,'critical':0}
for r in test_risk:
    if r < 0.25:   levels['low']      += 1
    elif r < 0.45: levels['medium']   += 1
    elif r < 0.70: levels['high']     += 1
    else:          levels['critical'] += 1

print(f"\n   === RISK DISTRIBUTION (Test) ===")
for lvl, cnt in levels.items():
    pct = cnt/len(test_risk)*100 if len(test_risk) > 0 else 0
    bar = '#' * int(pct/3)
    print(f"   {lvl:10s}: {cnt:4d}  ({pct:5.1f}%)  {bar}")

# ── Step 4b: Labeled evaluation ─────────────────────────────────────────────
# ADVANCED: Unsupervised models have no built-in accuracy. We generate a fresh
# labeled evaluation set (known normal + known attack patterns) with an
# INDEPENDENT seed so the metrics are an unbiased estimate of real performance.
print("\nStep 4b: Labeled evaluation (precision / recall / F1 / AUC)...")

from sklearn.metrics import (precision_score, recall_score, f1_score,
                             roc_auc_score, confusion_matrix)

ev_rng = np.random.default_rng(7)  # separate seed = unbiased estimate

ev_norm = np.column_stack([
    ev_rng.integers(1, 15, 400),         # F1: normal record access
    ev_rng.binomial(1, 0.03, 400),       # F2: rare failed logins
    ev_rng.binomial(1, 0.05, 400),       # F3: mostly daytime
    np.ones(400, dtype=float),           # F4: one IP
    ev_rng.uniform(0.02, 0.25, 400),     # F5: human pace
    ev_rng.binomial(1, 0.03, 400),       # F6: rarely after midnight
    ev_rng.binomial(1, 0.10, 400),       # F7: occasional location change
    ev_rng.uniform(5, 55, 400),          # F8: normal session length
    ev_rng.integers(1, 5, 400),          # F9: few resource types
    ev_rng.binomial(1, 0.05, 400),       # F10: no same-time locations
    ev_rng.uniform(0, 0.15, 400),        # F11: low rapid-fire
    ev_rng.binomial(1, 0.10, 400),       # F12: mostly in-role
]).astype(float)

ev_anom = np.column_stack([
    ev_rng.integers(20, 60, 100),        # F1: mass record access
    ev_rng.integers(3, 15, 100),         # F2: brute force
    ev_rng.binomial(1, 0.8, 100),        # F3: off-hours
    ev_rng.integers(3, 8, 100),          # F4: many IPs
    ev_rng.uniform(0.5, 2.0, 100),       # F5: automated pace
    ev_rng.binomial(1, 0.7, 100),        # F6: after midnight
    ev_rng.binomial(1, 0.9, 100),        # F7: location changed
    ev_rng.uniform(0.5, 5, 100),         # F8: very short sessions
    ev_rng.integers(5, 15, 100),         # F9: many resource types
    ev_rng.binomial(1, 0.8, 100),        # F10: same-time different locations
    ev_rng.uniform(0.4, 1.0, 100),       # F11: rapid-fire
    ev_rng.binomial(1, 0.7, 100),        # F12: role deviation
]).astype(float)

X_ev = np.clip(np.vstack([ev_norm, ev_anom]), 0, None)
y_ev = np.array([0]*400 + [1]*100)
X_ev_sc = scaler.transform(X_ev)
ev_risk = to_risk(model.score_samples(X_ev_sc))
# The model's own anomaly decision: predict() == -1 means flagged as an anomaly.
y_pred_native = (model.predict(X_ev_sc) == -1).astype(int)

print(f"   Evaluation set: {len(X_ev)} samples ({int(y_ev.sum())} known anomalies)")
print(f"   ROC-AUC:               {roc_auc_score(y_ev, ev_risk):.3f}")
print(f"   Precision:  {precision_score(y_ev, y_pred_native):.3f}   "
      f"Recall:  {recall_score(y_ev, y_pred_native):.3f}   "
      f"F1:  {f1_score(y_ev, y_pred_native):.3f}")
cm = confusion_matrix(y_ev, y_pred_native)
print(f"   Confusion matrix:      TN={cm[0,0]}  FP={cm[0,1]}  "
      f"FN={cm[1,0]}  TP={cm[1,1]}")

metrics_meta = {
    'auc':             float(round(roc_auc_score(y_ev, ev_risk), 4)),
    'precision':        float(round(precision_score(y_ev, y_pred_native), 4)),
    'recall':           float(round(recall_score(y_ev, y_pred_native), 4)),
    'f1':               float(round(f1_score(y_ev, y_pred_native), 4)),
    'true_negatives':   int(cm[0,0]),
    'false_positives':  int(cm[0,1]),
    'false_negatives':  int(cm[1,0]),
    'true_positives':   int(cm[1,1]),
}

# ── Step 5: Save model ───────────────────────────────────────────────────────
print("\nStep 5: Saving model...")

model_dir = 'trained_models'
os.makedirs(model_dir, exist_ok=True)

model_path  = os.path.join(model_dir, 'isolation_forest_v3.pkl')
scaler_path = os.path.join(model_dir, 'scaler_v3.pkl')
meta_path   = os.path.join(model_dir, 'model_meta_v3.json')

# ADVANCED: Pickle serialization — saving trained ML objects to disk
# pickle.dump() converts Python objects to bytes and writes to a file.
# pickle.load() reconstructs the exact same object later.
#
# WHY pickle?
#   - Isolation Forest model contains 250 decision trees with complex structure
#   - StandardScaler contains mean/std values for each feature
#   - These can't be saved as simple text/JSON
#   - Pickle preserves the EXACT state of the object
#
# WARNING: Only load pickles from TRUSTED sources!
#   pickle.load() executes arbitrary Python code during deserialization.
#   In production, use joblib or ONNX format for better security.
import pickle
with open(model_path,  'wb') as f: pickle.dump(model,  f)
with open(scaler_path, 'wb') as f: pickle.dump(scaler, f)

meta = {
    'trained_at':       datetime.now().isoformat(),
    'algorithm':        'IsolationForest',
    'n_estimators':     250,
    'contamination':    0.06,
    'n_features':       12,
    'feature_names':    FEATURE_NAMES,
    'training_samples': int(len(X_train)),
    'test_samples':     int(len(X_test)),
    'avg_risk_train':   float(round(train_risk.mean(),4)),
    'avg_risk_test':    float(round(test_risk.mean(),4)),
    'anomalies_train':  int((train_preds==-1).sum()),
    'anomalies_test':   int((test_preds==-1).sum()),
    'database':         DB,
    'author':           'Alto Dezdel Kiyamba',
    'institution':      'MUST BCS/25',
    'metrics':          metrics_meta,
}
with open(meta_path, 'w') as f:
    json.dump(meta, f, indent=2)

print(f"   Model  saved: {model_path}")
print(f"   Scaler saved: {scaler_path}")
print(f"   Meta   saved: {meta_path}")
print("\nTraining complete! The AI model (v3, 12 features) is ready.")
print("The app will auto-load it on next request.\n")

conn.close()
