from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from models.user import User
from models.logs import ActivityLog, RiskLog, AuthenticationLog
from extensions import db
from datetime import datetime, timedelta
import random, string, smtplib, os, json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

auth_bp = Blueprint('auth', __name__)
MAX_FAILED = 5
SMTP_HOST  = os.environ.get('SMTP_HOST',  'smtp.gmail.com')
SMTP_PORT  = int(os.environ.get('SMTP_PORT', 587))
SMTP_USER  = os.environ.get('SMTP_USER',  '')
SMTP_PASS  = os.environ.get('SMTP_PASS',  '')
SMTP_FROM  = os.environ.get('SMTP_FROM',  'Zero Trust EMR')

def _get_smtp_cfg():
    """Always return current SMTP settings (may be updated at runtime)."""
    import modules.auth as _m
    return _m.SMTP_HOST, _m.SMTP_PORT, _m.SMTP_USER, _m.SMTP_PASS, _m.SMTP_FROM

def gen_otp(): return ''.join(random.choices(string.digits, k=6))

def get_location(ip):
    if ip in ('127.0.0.1','::1'): return 'Localhost'
    try:
        import urllib.request
        with urllib.request.urlopen(f'http://ip-api.com/json/{ip}?fields=city,country,status', timeout=3) as r:
            d = json.loads(r.read())
            if d.get('status') == 'success': return f"{d.get('city','')}, {d.get('country','')}"
    except: pass
    return 'Unknown'

def parse_device(ua):
    ua = ua or ''
    os_n = 'Windows' if 'Windows' in ua else 'Android' if 'Android' in ua else 'iOS' if 'iPhone' in ua else 'Linux' if 'Linux' in ua else 'macOS' if 'Mac' in ua else 'Unknown'
    br   = 'Edge' if 'Edg/' in ua else 'Chrome' if 'Chrome/' in ua else 'Firefox' if 'Firefox/' in ua else 'Safari' if 'Safari/' in ua else 'Browser'
    return f'{br} on {os_n}'

def send_otp_email(user, otp):
    host, port, smtp_user, smtp_pass, smtp_from = _get_smtp_cfg()
    if not smtp_user or not smtp_pass:
        return False, "Email not configured. Go to Admin → Email Settings."
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f'🔐 EMR Security Code: {otp}'
        msg['From'] = smtp_from; msg['To'] = user.email
        html = f"""
        <div style="font-family:'Segoe UI',sans-serif;max-width:500px;margin:auto;background:#0f172a;border-radius:16px;overflow:hidden;">
          <div style="background:linear-gradient(135deg,#6366f1,#8b5cf6);padding:28px 32px;text-align:center;">
            <h1 style="color:white;margin:0;font-size:22px;">🔐 Zero Trust EMR</h1>
            <p style="color:rgba(255,255,255,.8);margin:4px 0 0;font-size:13px;">MUST · BCS/25 · Mbeya</p>
          </div>
          <div style="background:#1e293b;padding:28px 32px;">
            <p style="color:#94a3b8;font-size:14px;">Hello <span style="color:#f1f5f9;font-weight:600;">{user.full_name}</span>,</p>
            <p style="color:#94a3b8;font-size:14px;">Your security verification code is:</p>
            <div style="text-align:center;margin:24px 0;">
              <span style="display:inline-block;background:#6366f1;color:white;font-size:40px;font-weight:900;letter-spacing:14px;padding:18px 28px;border-radius:12px;">{otp}</span>
            </div>
            <div style="background:#0f172a;border-radius:8px;padding:14px 16px;margin-top:16px;">
              <p style="margin:0;color:#64748b;font-size:12px;">⏱ Expires in 5 minutes &nbsp;·&nbsp; 📍 {request.remote_addr} &nbsp;·&nbsp; 🖥 {parse_device(request.user_agent.string)}</p>
            </div>
            <p style="color:#475569;font-size:12px;margin-top:16px;">If you did not attempt to log in, contact your system administrator immediately.</p>
          </div>
        </div>"""
        msg.attach(MIMEText(html, 'html'))
        with smtplib.SMTP(host, int(port)) as s:
            s.ehlo(); s.starttls(); s.login(smtp_user, smtp_pass)
            s.sendmail(smtp_user, user.email, msg.as_string())
        return True, None
    except Exception as e: return False, str(e)

def log_auth(username, event, success=True, user_id=None, details=None):
    db.session.add(AuthenticationLog(username=username, user_id=user_id, event_type=event,
        ip_address=request.remote_addr, user_agent=request.user_agent.string[:256],
        success=success, details=details))
    db.session.commit()

def log_act(user_id, action, resource=None, resource_id=None, status='success', details=None):
    db.session.add(ActivityLog(user_id=user_id, action=action, resource=resource,
        resource_id=resource_id, ip_address=request.remote_addr,
        user_agent=request.user_agent.string[:256], session_id=session.get('_id',''),
        status=status, details=details))
    db.session.commit()

def role_dashboard(role):
    mapping = {
        'admin':         'patients.dashboard',
        'doctor':        'appointments.doctor_dashboard',
        'nurse':         'patients.dashboard',
        'receptionist':  'patients.dashboard',
        'pharmacist':    'pharmacy.dashboard',
        'lab_technician':'laboratory.dashboard',
    }
    return url_for(mapping.get(role, 'patients.dashboard'))

@auth_bp.route('/login', methods=['GET','POST'])
def login():
    from flask_login import current_user
    if current_user.is_authenticated:
        return redirect(role_dashboard(current_user.role))
    if request.method == 'POST':
        username = request.form.get('username','').strip()
        password = request.form.get('password','').strip()
        user = User.query.filter_by(username=username).first()
        if not user:
            log_auth(username,'login',False,details='Not found')
            flash('Invalid username or password.','danger'); return render_template('auth/login.html')
        if user.is_locked:
            flash('Account locked. Contact administrator.','danger'); return render_template('auth/login.html')
        if not user.check_password(password):
            user.failed_attempts += 1
            if user.failed_attempts >= MAX_FAILED:
                user.is_locked = True
                flash('Account locked after too many failed attempts.','danger')
            else:
                flash(f'Invalid password. {MAX_FAILED - user.failed_attempts} attempt(s) left.','danger')
            db.session.commit(); return render_template('auth/login.html')
        user.failed_attempts = 0
        user.last_ip       = request.remote_addr
        user.last_device   = parse_device(request.user_agent.string)
        user.last_location = get_location(request.remote_addr)
        db.session.commit()
        from modules.ai_engine import compute_risk_score
        risk = compute_risk_score(user)
        # Read email config from file directly
        _email_cfg_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'email_config.py')
        _email_cfg = {}
        if os.path.exists(_email_cfg_path):
            try:
                with open(_email_cfg_path) as _f: exec(_f.read(), _email_cfg)
            except: pass
        _su = _email_cfg.get('SMTP_USER','') or os.environ.get('SMTP_USER','')
        _sp = _email_cfg.get('SMTP_PASS','') or os.environ.get('SMTP_PASS','')
        email_configured = bool(_su and _sp and '@' in _su)
        if email_configured and (risk['score'] >= 0.35 or user.requires_otp):
            otp = gen_otp()
            user.otp_code = otp; user.otp_expiry = datetime.utcnow()+timedelta(minutes=5); user.otp_verified=False
            db.session.commit()
            sent, err = send_otp_email(user, otp)
            session['pending_user_id'] = user.id
            session['risk_score']      = risk['score']
            session['risk_reason']     = risk['reason']
            log_auth(username,'otp_request',True,user.id,f'Risk={risk["score"]:.2f}|sent={sent}')
            if sent:
                em = user.email; at = em.index('@')
                flash(f'Verification code sent to {em[:2]}***{em[at:]}','info')
            else:
                flash(f'Email failed. DEMO CODE: {otp}','warning')
            return redirect(url_for('auth.verify_otp'))
        login_user(user); user.last_login = datetime.utcnow(); db.session.commit()
        log_auth(username,'login',True,user.id,f'Direct|{user.last_device}|{user.last_location}')
        log_act(user.id,'session_start',details=f'{user.last_location} via {user.last_device}')
        return redirect(role_dashboard(user.role))
    return render_template('auth/login.html')

@auth_bp.route('/verify-otp', methods=['GET','POST'])
def verify_otp():
    uid = session.get('pending_user_id')
    if not uid: return redirect(url_for('auth.login'))
    user = User.query.get(uid)
    if not user: return redirect(url_for('auth.login'))
    risk_score = session.get('risk_score',0); risk_reason = session.get('risk_reason','')
    if request.method == 'POST':
        entered = request.form.get('otp','').strip()
        if user.otp_expiry and datetime.utcnow() > user.otp_expiry:
            flash('OTP expired. Please log in again.','danger')
            session.pop('pending_user_id',None); return redirect(url_for('auth.login'))
        if entered == user.otp_code:
            user.otp_verified=True; user.last_login=datetime.utcnow(); user.requires_otp=False
            db.session.commit()
            [session.pop(k,None) for k in ['pending_user_id','risk_score','risk_reason']]
            login_user(user)
            log_auth(user.username,'otp_success',True,user.id)
            log_act(user.id,'session_start',details=f'MFA|{user.last_location}|{user.last_device}')
            flash('Identity verified. Welcome!','success')
            return redirect(role_dashboard(user.role))
        log_auth(user.username,'otp_fail',False,user.id,'Wrong OTP')
        flash('Invalid code. Try again.','danger')
    em=user.email; at=em.index('@'); masked=em[:2]+'***'+em[at:]
    return render_template('auth/verify_otp.html',user=user,masked_email=masked,
                           risk_score=risk_score,risk_reason=risk_reason)

@auth_bp.route('/resend-otp', methods=['POST'])
def resend_otp():
    uid = session.get('pending_user_id')
    if not uid: return redirect(url_for('auth.login'))
    user = User.query.get(uid)
    if not user: return redirect(url_for('auth.login'))
    otp=gen_otp(); user.otp_code=otp; user.otp_expiry=datetime.utcnow()+timedelta(minutes=5)
    db.session.commit()
    sent,err = send_otp_email(user,otp)
    flash('A new verification code has been sent to your email.' if sent else f'Email failed: {err}. Contact administrator.','info' if sent else 'danger')
    return redirect(url_for('auth.verify_otp'))

@auth_bp.route('/session-mfa', methods=['GET','POST'])
@login_required
def session_mfa():
    # If email not configured, skip MFA entirely and redirect to dashboard
    _email_cfg_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'email_config.py')
    _email_cfg = {}
    if os.path.exists(_email_cfg_path):
        try:
            with open(_email_cfg_path) as _f: exec(_f.read(), _email_cfg)
        except: pass
    _su = _email_cfg.get('SMTP_USER','') or os.environ.get('SMTP_USER','')
    _sp = _email_cfg.get('SMTP_PASS','') or os.environ.get('SMTP_PASS','')
    if not (_su and _sp and '@' in _su):
        # Email not configured - bypass MFA, go straight to dashboard
        session.pop('escalation_risk_score', None)
        session.pop('escalation_risk_reason', None)
        session.pop('escalation_redirect', None)
        flash('Email not configured. Log in as admin and set up Email Settings to enable MFA.', 'warning')
        return redirect(url_for('patients.dashboard'))

    risk_score  = session.get('escalation_risk_score',0)
    risk_reason = session.get('escalation_risk_reason','Elevated risk')
    redirect_to = session.get('escalation_redirect',url_for('patients.dashboard'))
    if request.method=='POST':
        entered = request.form.get('otp','').strip()
        if current_user.otp_expiry and datetime.utcnow()>current_user.otp_expiry:
            flash('Code expired. New one sent.','danger'); return redirect(url_for('auth.session_mfa'))
        if entered==current_user.otp_code:
            current_user.otp_verified=True; db.session.commit()
            session['last_mfa_challenge']=datetime.utcnow().isoformat()
            [session.pop(k,None) for k in ['escalation_risk_score','escalation_risk_reason','escalation_redirect']]
            log_auth(current_user.username,'session_mfa_success',True,current_user.id)
            flash('Re-verified. You may continue.','success')
            return redirect(redirect_to)
        log_auth(current_user.username,'session_mfa_fail',False,current_user.id,'Wrong OTP mid-session')
        flash('Invalid code.','danger')
    otp=gen_otp(); current_user.otp_code=otp; current_user.otp_expiry=datetime.utcnow()+timedelta(minutes=5)
    db.session.commit()
    sent,err = send_otp_email(current_user,otp)
    if not sent: flash(f'Email delivery failed: {err}. Contact administrator.','danger')
    em=current_user.email; at=em.index('@'); masked=em[:2]+'***'+em[at:]
    return render_template('auth/session_mfa.html',masked_email=masked,
                           risk_score=risk_score,risk_reason=risk_reason)

@auth_bp.route('/logout')
@login_required
def logout():
    log_act(current_user.id,'session_end',details='Logged out')
    log_auth(current_user.username,'logout',True,current_user.id)
    logout_user(); flash('Signed out securely.','info')
    return redirect(url_for('auth.login'))

@auth_bp.route('/refine-location', methods=['POST'])
@login_required
def refine_location():
    """
    Called client-side after login using the browser's Geolocation API.
    Public IP-geolocation can never resolve private/LAN IPs (192.168.x.x,
    127.0.0.1) — that's a networking limit, not a bug. This is DISPLAY-ONLY;
    risk scoring already ran at login using the IP-derived location, which
    can't be spoofed as easily as a client-reported browser location.
    """
    data = request.get_json(silent=True) or {}
    city    = (data.get('city') or '').strip()
    country = (data.get('country') or '').strip()
    if not city and not country:
        return jsonify({'ok': False}), 400

    place = ', '.join(p for p in (city, country) if p) or 'Unknown'
    if current_user.last_location in (None, '', 'Unknown', 'Localhost'):
        current_user.last_location = place
        db.session.commit()
        log_act(current_user.id, 'location_refined', details=f'Device-reported: {place}')

    return jsonify({'ok': True, 'location': place})