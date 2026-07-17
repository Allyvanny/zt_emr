from flask import Blueprint, jsonify, session, redirect, url_for, request
from flask_login import login_required, current_user
from models.logs import ActivityLog, RiskLog
from extensions import db
from datetime import datetime, timedelta
import numpy as np

ai_bp = Blueprint('ai', __name__)

def extract_features(user_id, window=60):
    now = datetime.utcnow()
    logs = ActivityLog.query.filter(ActivityLog.user_id==user_id, ActivityLog.timestamp>=now-timedelta(minutes=window)).all()
    if not logs: return np.array([0,0,0,1,0,0],dtype=float)
    h = now.hour
    return np.array([
        sum(1 for l in logs if l.resource=='patient'),
        sum(1 for l in logs if l.status=='failed'),
        1 if (h<7 or h>20) else 0,
        len(set(l.ip_address for l in logs if l.ip_address)),
        len(logs)/max(window,1),
        1 if 0<=h<5 else 0
    ], dtype=float)

def get_model():
    global _MODEL
    if _MODEL is None:
        try:
            from sklearn.ensemble import IsolationForest
            rng = np.random.default_rng(42)
            data = np.clip(rng.normal(loc=[5,0,0,1,0.2,0],scale=[3,0.3,0.1,0.2,0.1,0.05],size=(300,6)),0,None)
            _MODEL = IsolationForest(contamination=0.1,random_state=42); _MODEL.fit(data)
        except: _MODEL = None
    return _MODEL
_MODEL = None

def compute_risk_score(user):
    f = extract_features(user.id); model = get_model()
    score = float(np.clip(1-(model.score_samples(f.reshape(1,-1))[0]+0.5),0,1)) if model else min(1.0,(f[0]/50)*.4+(f[1]/5)*.4+f[2]*.2)
    reasons = []
    if f[1]>=3: score=min(1.0,score+0.3); reasons.append(f'{int(f[1])} failed attempts')
    if f[0]>=20: score=min(1.0,score+0.2); reasons.append(f'{int(f[0])} records in 1hr')
    if f[2]==1: score=min(1.0,score+0.15); reasons.append('outside business hours')
    if f[5]==1: score=min(1.0,score+0.2); reasons.append('after midnight')
    if f[3]>=3: score=min(1.0,score+0.15); reasons.append('multiple IPs')
    score=round(score,3)
    level='low' if score<0.3 else 'medium' if score<0.55 else 'high' if score<0.75 else 'critical'
    return {'score':score,'level':level,'reason':'; '.join(reasons) if reasons else 'Normal pattern','features':f.tolist()}

def evaluate_and_log_risk(user):
    risk=compute_risk_score(user)
    action='monitor' if risk['level']=='low' else 'enhanced_monitoring' if risk['level']=='medium' else 'mfa_escalation'
    if risk['level'] in ('high','critical'): user.requires_otp=True
    db.session.add(RiskLog(user_id=user.id,risk_score=risk['score'],risk_level=risk['level'],trigger_reason=risk['reason'],action_taken=action))
    db.session.commit(); return risk

def check_session_risk(user):
    # Never trigger mid-session MFA if email is not configured
    import os as _os
    _cfg_path = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))), 'email_config.py')
    _cfg = {}
    if _os.path.exists(_cfg_path):
        try:
            with open(_cfg_path) as _f: exec(_f.read(), _cfg)
        except: pass
    _su = _cfg.get('SMTP_USER','') or _os.environ.get('SMTP_USER','')
    _sp = _cfg.get('SMTP_PASS','') or _os.environ.get('SMTP_PASS','')
    if not (_su and _sp and '@' in _su):
        return False  # Email not configured, skip MFA

    last = session.get('last_mfa_challenge')
    if last and (datetime.utcnow()-datetime.fromisoformat(last)).total_seconds()<600: return False
    risk=compute_risk_score(user)
    db.session.add(RiskLog(user_id=user.id,risk_score=risk['score'],risk_level=risk['level'],trigger_reason=risk['reason'],action_taken='session_check'))
    db.session.commit()
    if risk['score']>=0.55:
        session['escalation_risk_score']=risk['score']; session['escalation_risk_reason']=risk['reason']
        session['escalation_redirect']=request.url; return True
    return False

@ai_bp.route('/risk/<int:uid>')
@login_required
def risk_check(uid):
    from models.user import User
    if current_user.role!='admin' and current_user.id!=uid: return jsonify({'error':'Forbidden'}),403
    return jsonify(compute_risk_score(User.query.get_or_404(uid)))

@ai_bp.route('/risk-summary')
@login_required
def risk_summary():
    if current_user.role!='admin': return jsonify({'error':'Forbidden'}),403
    from models.user import User
    return jsonify([{'user_id':u.id,'username':u.username,'role':u.role,**compute_risk_score(u)} for u in User.query.filter_by(is_active=True).all()])
