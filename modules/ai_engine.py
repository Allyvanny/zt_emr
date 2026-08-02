"""
Zero Trust EMR — AI Engine v3
Enhanced anomaly detection with 12 behavioural features:
- records_accessed, failed_logins, off_hours, distinct_ips, actions_per_minute,
  after_midnight, location_changed, session_duration, distinct_resources,
  same_time_different_location, rapid_fire_actions, role_deviation
Author: Alto Dezdel Kiyamba | MUST BCS/25

═══════════════════════════════════════════════════════════════════════════════
ADVANCED CONCEPT — ML + Rule-Based Blending (Hybrid Approach)
═══════════════════════════════════════════════════════════════════════════════
Our risk scoring uses TWO approaches combined:

  1. MACHINE LEARNING (60% weight):
     The Isolation Forest learns complex patterns from data that rules can't
     express. It catches subtle, multi-feature anomalies.

  2. RULE-BASED (40% weight):
     Expert-defined rules that we KNOW are suspicious. These are transparent
     and explainable ("New device detected").

  WHY BLEND?
  ┌──────────────────────────────────────────────────────────────┐
  │  ML alone:      Good at patterns, bad at explanation         │
  │  Rules alone:   Good at explanation, misses complex attacks  │
  │  Blended:       Best of both — accurate AND explainable      │
  └──────────────────────────────────────────────────────────────┘

  This is a real-world production technique. Most enterprise security
  systems use hybrid approaches, not pure ML.

═══════════════════════════════════════════════════════════════════════════════
ADVANCED CONCEPT — Known-Good Reductions
═══════════════════════════════════════════════════════════════════════════════
After blending, we apply MULTIPLICATIVE reductions for known-good signals:

  If no rules flagged anything:
    - Known device → score *= 0.55 (45% reduction)
    - Known IP     → score *= 0.70 (30% reduction)
    - Daytime      → score *= 0.70 (30% reduction)

  These REDUCE the risk score (not add to it). The logic:
  If a doctor logs in from their usual laptop, during office hours,
  with no suspicious activity — that's clearly normal. Even if the ML
  model gives a moderate score, we should NOT flag it.

  The reductions are MULTIPLIED (not added) because:
  - They compound: known device + known IP + daytime = 0.55 × 0.70 × 0.70 = 0.27
  - This means a fully "known good" session gets a 73% reduction!
  - But if ANY rule flagged something (rule_score >= 0.15), we skip reductions
    because the rules detected a real concern.

═══════════════════════════════════════════════════════════════════════════════
ADVANCED CONCEPT — score_samples() to Risk Score Conversion
═══════════════════════════════════════════════════════════════════════════════
Isolation Forest's score_samples() returns raw anomaly scores:
  - Negative values (e.g. -0.3): NORMAL (point is easy to isolate = anomaly)
  - Positive values (e.g. +0.2): ANOMALOUS (point is hard to isolate = normal)

Wait — that's confusing! Let me clarify:
  - LOW score (very negative) = HARD to isolate = VERY ANOMALOUS
  - HIGH score (less negative/positive) = EASY to isolate = NORMAL

We flip this with: risk = 1 - (raw_score + 0.5)
  - raw = -0.5  → risk = 1.0 (certain anomaly)
  - raw =  0.0  → risk = 0.5 (uncertain)
  - raw =  0.5  → risk = 0.0 (certain normal)

Then clip to [0, 1] range.

═══════════════════════════════════════════════════════════════════════════════
ADVANCED CONCEPT — Cold-Start Training (_train_fresh)
═══════════════════════════════════════════════════════════════════════════════
When no pre-trained model exists, we train one from scratch using SYNTHETIC
data that mimics real EMR usage patterns. This is called "cold start."

The synthetic data has 4 groups:
  1. Normal daytime (600 samples): doctors, nurses, pharmacists working
  2. Normal after-hours (150 samples): on-call staff, night nurses
  3. Normal midnight (50 samples): emergency on-call only
  4. Anomalous (60 samples): attacker patterns

Each group has different statistical distributions for the 12 features.
The model learns to distinguish group 4 from groups 1-3.

This approach is valid because:
  - We KNOW what normal EMR usage looks like (domain knowledge)
  - We KNOW what attacks look like (security expertise)
  - The model only needs to learn the BOUNDARY between them
"""
from flask import Blueprint, jsonify, session, redirect, url_for, request
from flask_login import login_required, current_user
from models.logs import ActivityLog, RiskLog, AuthenticationLog
from models.user import User
from extensions import db
from datetime import datetime, timedelta
import numpy as np, pickle, os, json, math

ai_bp = Blueprint('ai', __name__)

MODEL_DIR   = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'trained_models')
MODEL_PATH  = os.path.join(MODEL_DIR, 'isolation_forest_v3.pkl')
SCALER_PATH = os.path.join(MODEL_DIR, 'scaler_v3.pkl')
META_PATH   = os.path.join(MODEL_DIR, 'model_meta_v3.json')
_MODEL = _SCALER = None

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


def get_model():
    global _MODEL, _SCALER
    if _MODEL is None:
        if os.path.exists(MODEL_PATH) and os.path.exists(SCALER_PATH):
            try:
                with open(MODEL_PATH, 'rb') as f: _MODEL  = pickle.load(f)
                with open(SCALER_PATH, 'rb') as f: _SCALER = pickle.load(f)
            except Exception as e:
                print(f"  Could not load saved model: {e}. Training fresh...")
                _train_fresh()
        else:
            _train_fresh()
    return _MODEL, _SCALER


def _train_fresh():
    """Cold-start training with realistic EMR synthetic data (12 features)."""
    global _MODEL, _SCALER
    from sklearn.ensemble import IsolationForest
    from sklearn.preprocessing import StandardScaler

    rng = np.random.default_rng(42)

    # Normal daytime sessions (doctors, nurses, pharmacists working)
    n_day = 600
    normal_day = np.column_stack([
        rng.integers(1, 15, n_day),         # records_accessed
        rng.binomial(1, 0.03, n_day),        # failed_logins (rare)
        np.zeros(n_day),                     # off_hours_flag
        np.ones(n_day, dtype=float),         # distinct_ips (1)
        rng.uniform(0.02, 0.25, n_day),     # actions_per_minute
        np.zeros(n_day),                     # after_midnight
        np.zeros(n_day),                     # location_changed
        rng.uniform(5, 55, n_day),           # session_duration_min
        rng.integers(1, 5, n_day),           # distinct_resources
        np.zeros(n_day),                     # same_time_new_location
        rng.uniform(0, 0.15, n_day),         # rapid_fire_ratio
        np.zeros(n_day),                     # role_deviation
    ]).astype(float)

    # Normal after-hours (on-call doctor, night nurse)
    n_night = 150
    normal_night = np.column_stack([
        rng.integers(0, 6, n_night),
        rng.binomial(1, 0.05, n_night),
        np.ones(n_night, dtype=float),       # off_hours_flag
        np.ones(n_night, dtype=float),
        rng.uniform(0.01, 0.1, n_night),
        np.zeros(n_night),                   # after_midnight (before 7pm is off_hours but not midnight)
        rng.binomial(1, 0.1, n_night),       # location_changed (home vs hospital)
        rng.uniform(3, 30, n_night),
        rng.integers(1, 3, n_night),
        np.zeros(n_night),
        rng.uniform(0, 0.08, n_night),
        np.zeros(n_night),
    ]).astype(float)

    # Normal midnight (very low activity, on-call)
    n_mid = 50
    normal_mid = np.column_stack([
        rng.integers(0, 3, n_mid),
        rng.binomial(1, 0.02, n_mid),
        np.ones(n_mid, dtype=float),
        np.ones(n_mid, dtype=float),
        rng.uniform(0.005, 0.05, n_mid),
        np.ones(n_mid, dtype=float),         # after_midnight
        rng.binomial(1, 0.15, n_mid),
        rng.uniform(2, 20, n_mid),
        rng.integers(0, 2, n_mid),
        np.zeros(n_mid),
        rng.uniform(0, 0.05, n_mid),
        np.zeros(n_mid),
    ]).astype(float)

    # Anomalous patterns
    n_anom = 60
    anom = np.column_stack([
        rng.integers(20, 60, n_anom),        # mass record access
        rng.integers(3, 15, n_anom),         # many failed logins
        rng.binomial(1, 0.8, n_anom),        # mostly off-hours
        rng.integers(3, 8, n_anom),          # many IPs
        rng.uniform(0.5, 2.0, n_anom),       # extremely fast actions
        rng.binomial(1, 0.7, n_anom),        # after midnight
        rng.binomial(1, 0.9, n_anom),        # location changed
        rng.uniform(0.5, 5, n_anom),         # very short sessions (automated)
        rng.integers(5, 15, n_anom),         # accessing many resource types
        rng.binomial(1, 0.8, n_anom),        # same time different location
        rng.uniform(0.4, 1.0, n_anom),       # rapid fire
        rng.binomial(1, 0.7, n_anom),        # role deviation
    ]).astype(float)

    X = np.clip(np.vstack([normal_day, normal_night, normal_mid, anom]), 0, None)
    scaler = StandardScaler()
    X_sc = scaler.fit_transform(X)
    model = IsolationForest(n_estimators=250, contamination=0.06, random_state=42, n_jobs=-1)
    model.fit(X_sc)
    _MODEL = model; _SCALER = scaler


def extract_features(user_id, window_minutes=60):
    """Extract 12 behavioural features for anomaly detection."""
    now   = datetime.utcnow()
    since = now - timedelta(minutes=window_minutes)
    logs  = ActivityLog.query.filter(
        ActivityLog.user_id   == user_id,
        ActivityLog.timestamp >= since
    ).all()

    if not logs:
        return np.zeros(12, dtype=float)

    h = now.hour
    user = User.query.get(user_id)
    role = user.role if user else ''

    # ── Feature 1: records accessed ─────────────────────────────────────
    records_accessed = sum(1 for l in logs if 'patient' in (l.resource or '').lower())

    # ── Feature 2: failed logins/actions ────────────────────────────────
    failed_logins = sum(1 for l in logs if l.status == 'failed')

    # ── Feature 3: off-hours flag (before 7am or after 8pm) ─────────────
    off_hours_flag = 1.0 if (h < 7 or h > 20) else 0.0

    # ── Feature 4: distinct IPs ─────────────────────────────────────────
    distinct_ips = len(set(l.ip_address for l in logs if l.ip_address))

    # ── Feature 5: actions per minute ───────────────────────────────────
    actions_per_minute = len(logs) / max(window_minutes, 1)

    # ── Feature 6: after midnight (12am–5am) ────────────────────────────
    after_midnight = 1.0 if (0 <= h < 5) else 0.0

    # ── Feature 7: location changed since last known ────────────────────
    # Check if the current IP differs from the user's last known IP
    location_changed = 0.0
    if user.last_ip:
        recent_unique_ips = set(l.ip_address for l in logs if l.ip_address)
        if user.last_ip not in recent_unique_ips and recent_unique_ips:
            location_changed = 1.0

    # ── Feature 8: session duration (minutes of activity in window) ─────
    if len(logs) >= 2:
        timestamps = sorted(l.timestamp for l in logs)
        session_duration = (timestamps[-1] - timestamps[0]).total_seconds() / 60.0
    else:
        session_duration = 0.0
    session_duration = min(session_duration, window_minutes)

    # ── Feature 9: distinct resource types accessed ─────────────────────
    resource_types = set()
    for l in logs:
        r = (l.resource or '').lower()
        if r:
            resource_types.add(r.split('_')[0].split('/')[0])
    distinct_resources = len(resource_types)

    # ── Feature 10: same time but new location (credential sharing) ─────
    # Multiple IPs active within the same hour window
    same_time_new_location = 0.0
    ip_timestamps = {}
    for l in logs:
        if l.ip_address:
            ip_timestamps.setdefault(l.ip_address, []).append(l.timestamp)
    if len(ip_timestamps) >= 2:
        for ip1, ts1 in ip_timestamps.items():
            for ip2, ts2 in ip_timestamps.items():
                if ip1 >= ip2:
                    continue
                for t1 in ts1:
                    for t2 in ts2:
                        if abs((t1 - t2).total_seconds()) < 600:  # within 10 min
                            same_time_new_location = 1.0
                            break
                    if same_time_new_location:
                        break
                if same_time_new_location:
                    break
            if same_time_new_location:
                break

    # ── Feature 11: rapid-fire ratio (actions within 5 seconds of each other) ──
    rapid_count = 0
    if len(logs) >= 2:
        timestamps = sorted(l.timestamp for l in logs)
        for i in range(1, len(timestamps)):
            if (timestamps[i] - timestamps[i-1]).total_seconds() < 5:
                rapid_count += 1
    rapid_fire_ratio = rapid_count / max(len(logs) - 1, 1)

    # ── Feature 12: role deviation (accessing resources outside role) ───
    role_deviation = 0.0
    allowed = ROLE_RESOURCES.get(role, set())
    if allowed:  # admin has no restrictions, so skip
        for l in logs:
            r = (l.resource or '').lower()
            if r and not any(a in r for a in allowed):
                role_deviation = 1.0
                break

    return np.array([
        records_accessed, failed_logins, off_hours_flag, distinct_ips,
        actions_per_minute, after_midnight, location_changed,
        session_duration, distinct_resources, same_time_new_location,
        rapid_fire_ratio, role_deviation
    ], dtype=float)


def _parse_device(ua_string):
    """Extract short device fingerprint from user agent."""
    ua = ua_string or ''
    os_n = ('Windows' if 'Windows' in ua else
            'Android' if 'Android' in ua else
            'iOS'     if 'iPhone' in ua or 'iPad' in ua else
            'Linux'   if 'Linux' in ua else
            'macOS'   if 'Mac' in ua else 'Unknown')
    br   = ('Edge'    if 'Edg/'     in ua else
            'Chrome'  if 'Chrome/'  in ua else
            'Firefox' if 'Firefox/' in ua else
            'Safari'  if 'Safari/'  in ua else 'Browser')
    return f'{br} on {os_n}'


def compute_risk_score(user):
    """
    Enhanced risk scoring with 12 features, location awareness, and
    intelligent ML + rule-based blending.
    """
    features      = extract_features(user.id)
    model, scaler = get_model()

    # ── ML score from Isolation Forest ──────────────────────────────────
    # STEP 1: Scale the raw features using the SAME scaler from training
    # IMPORTANT: You must use the SAME scaler that was fit during training.
    # If you create a new scaler, it will have different mean/std values
    # and the model will produce wrong scores. This is a common mistake!
    if scaler is not None:
        f_scaled = scaler.transform(features.reshape(1, -1))
    else:
        f_scaled = features.reshape(1, -1)

    # STEP 2: Get the raw anomaly score from the model
    # score_samples() returns values typically in [-0.5, 0.5] range
    raw   = model.score_samples(f_scaled)[0]

    # STEP 3: Convert to 0-1 risk score (see docstring above for math)
    ml_score = float(np.clip(1 - (raw + 0.5), 0, 1))

    reasons = []
    h  = datetime.utcnow().hour

    try:
        current_ip = request.remote_addr or ''
        current_ua = request.user_agent.string or ''
    except:
        current_ip = ''
        current_ua = ''

    current_device = _parse_device(current_ua)
    known_ip       = user.last_ip     or ''
    known_device   = user.last_device or ''
    is_known_device = (known_device and current_device == known_device)
    is_known_ip     = (known_ip and current_ip == known_ip)
    is_daytime      = (7 <= h <= 20)

    # Device fingerprint from client JS (stable per physical device)
    try:
        current_fp = (request.form.get('device_fp') or '').strip()[:64]
    except Exception:
        current_fp = ''
    known_fp       = user.last_fingerprint or ''
    is_known_fp    = bool(known_fp and current_fp and current_fp == known_fp)

    # ── Rule-based signals (each contributes to a weighted sum) ─────────
    rule_score = 0.0
    rule_weight = 0.0

    # Signal 1: New device (weight 0.30)
    if not is_known_device and known_device:
        rule_score += 0.30
        rule_weight += 0.30
        reasons.append(f'New device: {current_device} (known: {known_device})')
    elif is_known_device:
        rule_score += 0.0
        rule_weight += 0.30

    # Signal 1b: New device fingerprint (weight 0.25) — same physical device check
    if known_fp and current_fp and not is_known_fp:
        rule_score += 0.25
        rule_weight += 0.25
        reasons.append('New device fingerprint - different physical device than last login')
    elif is_known_fp:
        rule_weight += 0.25

    # Signal 2: New IP (weight 0.15)
    if not is_known_ip and known_ip:
        rule_score += 0.15
        rule_weight += 0.15
        reasons.append(f'New IP: {current_ip} (known: {known_ip})')
    elif is_known_ip:
        rule_weight += 0.15

    # Signal 3: Location changed (weight 0.20)
    if features[6] == 1:  # location_changed
        rule_score += 0.20
        rule_weight += 0.20
        reasons.append('Login from different location than last session')
    else:
        rule_weight += 0.20

    # Signal 4: Same time different location — credential sharing (weight 0.25)
    if features[9] == 1:  # same_time_new_location
        rule_score += 0.25
        rule_weight += 0.25
        reasons.append('Multiple locations active simultaneously (possible credential sharing)')
    else:
        rule_weight += 0.25

    # Signal 5: Role deviation (weight 0.10)
    if features[11] == 1:  # role_deviation
        rule_score += 0.10
        rule_weight += 0.10
        reasons.append('Accessing resources outside assigned role')
    else:
        rule_weight += 0.10

    # Signal 6: Failed logins boost (weight 0.15)
    if features[1] >= 3:
        rule_score += 0.15
        rule_weight += 0.15
        reasons.append(f'{int(features[1])} failed login attempts')
    elif features[1] >= 1:
        rule_score += 0.05
        rule_weight += 0.15
    else:
        rule_weight += 0.15

    # Signal 7: After midnight boost (weight 0.10)
    if features[5] == 1:
        rule_score += 0.10
        rule_weight += 0.10
        reasons.append('Activity after midnight (12am-5am)')
    else:
        rule_weight += 0.10

    # Signal 8: Rapid-fire actions (weight 0.10)
    if features[10] > 0.5:
        rule_score += 0.10
        rule_weight += 0.10
        reasons.append(f'Rapid-fire actions detected ({features[10]:.0%} within 5s)')
    else:
        rule_weight += 0.10

    # Signal 9: Mass record access (weight 0.10)
    if features[0] >= 30:
        rule_score += 0.10
        rule_weight += 0.10
        reasons.append(f'{int(features[0])} patient records accessed rapidly')
    else:
        rule_weight += 0.10

    # Signal 10: Distinct IPs in session (weight 0.10)
    if features[3] >= 3:
        rule_score += 0.10
        rule_weight += 0.10
        reasons.append(f'{int(features[3])} different IP addresses in session')
    else:
        rule_weight += 0.10

    # Signal 11: First-ever login (weight 0.15)
    if not known_device and not known_ip:
        rule_score += 0.15
        rule_weight += 0.15
        reasons.append('First login - no prior session history')

    # ── Normalize rule score ────────────────────────────────────────────
    # ADVANCED: Normalization — converting to [0, 1] range
    # The rule_score is a weighted sum (not a probability). We divide by the
    # total weight to normalize it to [0, 1]. This makes it comparable to
    # the ML score (which is already 0-1).
    #
    # Example: If only 3 of 11 rules fired, weight = 0.30+0.15+0.20 = 0.65
    #   rule_score / 0.65 = normalized score in [0, 1]
    rule_score = rule_score / max(rule_weight, 0.01)

    # ── Blend ML and rule-based scores (60% ML, 40% rules) ──────────────
    # ADVANCED: Weighted Ensemble — combining multiple scoring methods
    #
    # WHY 60/40 split?
    #   - ML (60%): Better at detecting complex, multi-feature anomalies
    #     that individual rules can't catch (e.g., subtle patterns)
    #   - Rules (40%): More transparent, explainable, and reliable for
    #     known attack patterns (new device, brute force, etc.)
    #
    # The blend gives us:
    #   - ML's pattern recognition for UNKNOWN threats
    #   - Rules' transparency for EXPLAINING risk scores to admins
    #
    # This is a production-grade technique used in real security systems.
    # Pure ML = black box. Pure rules = rigid. Blend = best of both.
    score = 0.60 * ml_score + 0.40 * rule_score

    # ── Known-good reductions (only if rules didn't flag anything) ──────
    if rule_score < 0.15:
        if is_known_device:
            score *= 0.55
        if is_known_ip:
            score *= 0.70
        if is_daytime:
            score *= 0.70

    # ── Clamp ───────────────────────────────────────────────────────────
    score = round(float(np.clip(score, 0.0, 1.0)), 3)

    # ── Level classification ────────────────────────────────────────────
    level = ('low'      if score < 0.25 else
             'medium'   if score < 0.45 else
             'high'     if score < 0.70 else
             'critical')

    reason = '; '.join(reasons) if reasons else 'Normal pattern - known device & location'

    return {
        'score':              score,
        'level':              level,
        'reason':             reason,
        'features':           features.tolist(),
        'feature_names':      FEATURE_NAMES,
        'ml_score':           round(ml_score, 3),
        'rule_score':         round(rule_score, 3),
        'device_status':      'known' if is_known_device else 'NEW',
        'ip_status':          'known' if is_known_ip     else 'NEW',
    }


def check_session_risk(user):
    """Mid-session check — triggers for genuinely suspicious activity."""
    cfg_path = os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), 'email_config.py')
    cfg = {}
    if os.path.exists(cfg_path):
        try:
            with open(cfg_path) as f: exec(f.read(), cfg)
        except: pass
    smtp_u = cfg.get('SMTP_USER','') or os.environ.get('SMTP_USER','')
    smtp_p = cfg.get('SMTP_PASS','') or os.environ.get('SMTP_PASS','')
    if not (smtp_u and smtp_p and '@' in smtp_u):
        return False

    last = session.get('last_mfa_challenge')
    if last:
        elapsed = (datetime.utcnow() - datetime.fromisoformat(last)).total_seconds()
        if elapsed < 1800:
            return False

    risk = compute_risk_score(user)

    db.session.add(RiskLog(
        user_id=user.id, risk_score=risk['score'],
        risk_level=risk['level'], trigger_reason=risk['reason'],
        action_taken='session_check'
    ))
    db.session.commit()

    if risk['score'] >= 0.65:
        session['escalation_risk_score']  = risk['score']
        session['escalation_risk_reason'] = risk['reason']
        session['escalation_redirect']    = request.url
        session['last_mfa_challenge']     = datetime.utcnow().isoformat()
        return True
    return False


def evaluate_and_log_risk(user):
    risk   = compute_risk_score(user)
    action = ('monitor'             if risk['level'] == 'low'    else
              'enhanced_monitoring' if risk['level'] == 'medium' else
              'mfa_escalation')
    db.session.add(RiskLog(
        user_id=user.id, risk_score=risk['score'],
        risk_level=risk['level'], trigger_reason=risk['reason'],
        action_taken=action
    ))
    db.session.commit()
    return risk


@ai_bp.route('/ai/risk/<int:uid>')
@login_required
def risk_check(uid):
    if current_user.role != 'admin' and current_user.id != uid:
        return jsonify({'error': 'Forbidden'}), 403
    u = User.query.get(uid)
    if not u: return jsonify({'error': 'Not found'}), 404
    return jsonify(compute_risk_score(u))

@ai_bp.route('/ai/model-info')
@login_required
def model_info():
    if current_user.role != 'admin':
        return jsonify({'error': 'Forbidden'}), 403
    if os.path.exists(META_PATH):
        with open(META_PATH) as f: return jsonify(json.load(f))
    model, _ = get_model()
    return jsonify({'algorithm': 'IsolationForest',
                    'n_estimators': model.n_estimators,
                    'contamination': model.contamination,
                    'n_features': 12,
                    'feature_names': FEATURE_NAMES})
