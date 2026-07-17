"""
Zero Trust EMR — Updated AI Engine using saved trained model
Replace modules/ai_engine.py with this file after running train_model.py
Author: Alto Dezdel Kiyamba | MUST BCS/25
"""

from flask import Blueprint, jsonify, session, redirect, url_for, request
from flask_login import login_required, current_user
from models.logs import ActivityLog, RiskLog
from extensions import db
from datetime import datetime, timedelta
import numpy as np
import pickle
import os

ai_bp = Blueprint('ai', __name__)

# ── Load saved trained model ─────────────────────────────────────────────────
MODEL_DIR   = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'trained_models')
MODEL_PATH  = os.path.join(MODEL_DIR, 'isolation_forest.pkl')
SCALER_PATH = os.path.join(MODEL_DIR, 'scaler.pkl')

_MODEL  = None
_SCALER = None

def get_model():
    """Load model from disk if not already loaded. Falls back to in-memory training."""
    global _MODEL, _SCALER
    if _MODEL is None:
        if os.path.exists(MODEL_PATH) and os.path.exists(SCALER_PATH):
            try:
                with open(MODEL_PATH, 'rb')  as f: _MODEL  = pickle.load(f)
                with open(SCALER_PATH, 'rb') as f: _SCALER = pickle.load(f)
                print("✅ AI Model loaded from trained_models/isolation_forest.pkl")
            except Exception as e:
                print(f"⚠️  Could not load saved model: {e}. Training fresh...")
                _train_fresh()
        else:
            print("⚠️  No saved model found. Training fresh Isolation Forest...")
            _train_fresh()
    return _MODEL, _SCALER

def _train_fresh():
    """Train a basic model in memory when no saved model exists."""
    global _MODEL, _SCALER
    from sklearn.ensemble import IsolationForest
    from sklearn.preprocessing import StandardScaler
    rng    = np.random.default_rng(42)
    normal = np.clip(rng.normal(loc=[5,0,0,1,0.2,0], scale=[3,0.3,0.1,0.2,0.1,0.05], size=(300,6)), 0, None)
    scaler = StandardScaler()
    X_sc   = scaler.fit_transform(normal)
    model  = IsolationForest(n_estimators=200, contamination=0.08, random_state=42, n_jobs=-1)
    model.fit(X_sc)
    _MODEL  = model
    _SCALER = scaler

# ── Feature extraction ───────────────────────────────────────────────────────
def extract_features(user_id, window_minutes=60):
    """Extract 6 behavioural features from the last window_minutes of activity."""
    now   = datetime.utcnow()
    since = now - timedelta(minutes=window_minutes)
    logs  = ActivityLog.query.filter(
        ActivityLog.user_id  == user_id,
        ActivityLog.timestamp >= since
    ).all()

    if not logs:
        return np.array([0, 0, 0, 1, 0, 0], dtype=float)

    h = now.hour
    return np.array([
        sum(1 for l in logs if 'patient' in (l.resource or '')),   # records accessed
        sum(1 for l in logs if l.status == 'failed'),               # failed actions
        1 if (h < 7 or h > 20) else 0,                             # off hours
        len(set(l.ip_address for l in logs if l.ip_address)),       # distinct IPs
        len(logs) / max(window_minutes, 1),                         # actions/min
        1 if (0 <= h < 5) else 0,                                   # after midnight
    ], dtype=float)

# ── Risk scoring ─────────────────────────────────────────────────────────────
def compute_risk_score(user):
    """
    Compute risk score for a user.
    Returns dict: {score, level, reason, features}
    """
    features       = extract_features(user.id)
    model, scaler  = get_model()

    # Scale features using the same scaler used during training
    if scaler is not None:
        f_scaled = scaler.transform(features.reshape(1, -1))
    else:
        f_scaled = features.reshape(1, -1)

    # Isolation Forest score: more negative = more anomalous
    raw   = model.score_samples(f_scaled)[0]
    score = float(np.clip(1 - (raw + 0.5), 0, 1))

    # Rule-based boosters on top of ML score
    reasons = []
    if features[1] >= 3:
        score = min(1.0, score + 0.30)
        reasons.append(f'{int(features[1])} failed attempts')
    if features[0] >= 20:
        score = min(1.0, score + 0.20)
        reasons.append(f'{int(features[0])} records accessed in 1hr')
    if features[2] == 1:
        score = min(1.0, score + 0.15)
        reasons.append('outside business hours')
    if features[5] == 1:
        score = min(1.0, score + 0.20)
        reasons.append('after midnight activity')
    if features[3] >= 3:
        score = min(1.0, score + 0.15)
        reasons.append('multiple IP addresses')

    score  = round(score, 3)
    level  = ('low'      if score < 0.30 else
              'medium'   if score < 0.55 else
              'high'     if score < 0.75 else
              'critical')
    reason = '; '.join(reasons) if reasons else 'Normal activity pattern'

    return {
        'score':    score,
        'level':    level,
        'reason':   reason,
        'features': features.tolist()
    }

def evaluate_and_log_risk(user):
    """Compute risk, log it, and flag user if high."""
    risk   = compute_risk_score(user)
    action = ('monitor'              if risk['level'] == 'low'    else
              'enhanced_monitoring'  if risk['level'] == 'medium' else
              'mfa_escalation')
    if risk['level'] in ('high', 'critical'):
        user.requires_otp = True

    db.session.add(RiskLog(
        user_id=user.id, risk_score=risk['score'],
        risk_level=risk['level'], trigger_reason=risk['reason'],
        action_taken=action
    ))
    db.session.commit()
    return risk

def check_session_risk(user):
    """
    Called on every protected page load.
    Returns True if mid-session MFA should be triggered.
    """
    # Skip if email not configured
    import os as _os
    _cfg = os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), 'email_config.py')
    _vars = {}
    if os.path.exists(_cfg):
        try:
            with open(_cfg) as _f: exec(_f.read(), _vars)
        except: pass
    _su = _vars.get('SMTP_USER','') or _os.environ.get('SMTP_USER','')
    _sp = _vars.get('SMTP_PASS','') or _os.environ.get('SMTP_PASS','')
    if not (_su and _sp and '@' in _su):
        return False

    # Don't re-challenge within 10 minutes
    last = session.get('last_mfa_challenge')
    if last:
        elapsed = (datetime.utcnow() - datetime.fromisoformat(last)).total_seconds()
        if elapsed < 600:
            return False

    risk = compute_risk_score(user)

    db.session.add(RiskLog(
        user_id=user.id, risk_score=risk['score'],
        risk_level=risk['level'], trigger_reason=risk['reason'],
        action_taken='session_check'
    ))
    db.session.commit()

    if risk['score'] >= 0.55:
        session['escalation_risk_score']  = risk['score']
        session['escalation_risk_reason'] = risk['reason']
        session['escalation_redirect']    = request.url
        return True
    return False

# ── API routes ───────────────────────────────────────────────────────────────
@ai_bp.route('/risk/<int:uid>')
@login_required
def risk_check(uid):
    from models.user import User
    if current_user.role != 'admin' and current_user.id != uid:
        return jsonify({'error': 'Forbidden'}), 403
    user = User.query.get_or_404(uid)
    return jsonify(compute_risk_score(user))

@ai_bp.route('/risk-summary')
@login_required
def risk_summary():
    if current_user.role != 'admin':
        return jsonify({'error': 'Forbidden'}), 403
    from models.user import User
    results = []
    for u in User.query.filter_by(is_active=True).all():
        r = compute_risk_score(u)
        results.append({'user_id': u.id, 'username': u.username,
                        'role': u.role, **r})
    return jsonify(results)

@ai_bp.route('/model-info')
@login_required
def model_info():
    """Return info about the loaded model."""
    if current_user.role != 'admin':
        return jsonify({'error': 'Forbidden'}), 403
    meta_path = os.path.join(MODEL_DIR, 'model_meta.json')
    if os.path.exists(meta_path):
        import json
        with open(meta_path) as f:
            return jsonify(json.load(f))
    model, _ = get_model()
    return jsonify({
        'algorithm':    'IsolationForest',
        'n_estimators': model.n_estimators,
        'contamination': model.contamination,
        'source':       'in-memory (run train_model.py to save)',
    })
