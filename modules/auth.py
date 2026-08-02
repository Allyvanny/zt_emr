from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from models.user import User
from models.logs import ActivityLog, RiskLog, AuthenticationLog
from extensions import db
from datetime import datetime, timedelta
import random, string, smtplib, os, json, secrets
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

def issue_session_token(user):
    """Create a fresh session token, store it in DB and Flask session.
    Any older device still holding a previous token is invalidated."""
    token = secrets.token_hex(32)
    user.session_token = token
    session['zt_session_token'] = token
    return token

def clean_location_text(text):
    """Server-side location cleanup. Normalizes location strings so the same
    place always looks the same regardless of which geolocation service or
    login session produced it. Removes bad road names, duplicate city names,
    and redundant administrative parts, while keeping the most specific
    place names (village, quarter, market area) at the front."""
    if not text: return text
    text = str(text).strip()
    # Remove "Shotcut to X" / "Shortcut to X" descriptions, not place names
    import re
    text = re.sub(r'\b(?:shortcut|shotcut)\s+to\s+\w+', '', text, flags=re.I)
    # Drop remaining junk descriptions
    bad = ['road to','route to','highway','motorway','towards',
           'near ','beside','next to','opposite','across from',
           'turnoff','turn off','junction','intersection','bypass']
    parts = [p.strip() for p in text.split(',') if p.strip()]
    cleaned = [p for p in parts if not any(b in p.lower() for b in bad)]
    # Deduplicate: "Mbeya, Mbeya Municipal" -> "Mbeya Municipal"
    # (the city name is repeated inside the municipality name)
    out = []
    for p in cleaned:
        if out:
            # Skip current part if it duplicates the previous part
            if p.lower() == out[-1].lower():
                continue
            # Skip city name if the next part (municipality) contains it:
            # "Mbeya, Mbeya Municipal" — keep only "Mbeya Municipal"
            prev_contains = p.lower().startswith(out[-1].lower()) and p.lower() != out[-1].lower()
            cur_contains  = out[-1].lower().startswith(p.lower()) and out[-1].lower() != p.lower()
            if prev_contains or cur_contains:
                out[-1] = p if len(p) >= len(out[-1]) else out[-1]
                continue
        out.append(p)
    result = ', '.join(out).strip(' ,')
    return result or text

def get_location(ip):
    if ip in ('127.0.0.1','::1'): return 'Localhost'
    try:
        import urllib.request
        with urllib.request.urlopen(f'http://ip-api.com/json/{ip}?fields=city,regionName,country,status', timeout=3) as r:
            d = json.loads(r.read())
            if d.get('status') == 'success':
                # Filter out useless values like continent names, timezone strings, etc.
                skip = {'africa', 'europe', 'asia', 'americas', 'oceania',
                        'unknown', '', 'none'}
                parts = []
                for p in (d.get('city',''), d.get('regionName',''), d.get('country','')):
                    val = (p or '').strip()
                    if val and val.lower() not in skip and '/' not in val:
                        parts.append(val)
                loc = ', '.join(parts) if parts else 'Unknown'
                return clean_location_text(loc)
    except: pass
    return 'Unknown'

def parse_device(ua):
    ua = ua or ''
    os_n = 'Windows' if 'Windows' in ua else 'Android' if 'Android' in ua else 'iOS' if 'iPhone' in ua else 'Linux' if 'Linux' in ua else 'macOS' if 'Mac' in ua else 'Unknown'
    br   = 'Edge' if 'Edg/' in ua else 'Chrome' if 'Chrome/' in ua else 'Firefox' if 'Firefox/' in ua else 'Safari' if 'Safari/' in ua else 'Browser'
    return f'{br} on {os_n}'

DEFAULT_OTP_EMAIL = 'altodezdel@gmail.com'

def otp_destination(user):
    """Return the email that the OTP is actually sent to.
    If the user has no real email (empty, @localhost, @emr.local, etc.)
    fall back to the default email altodezdel@gmail.com."""
    email = (user.email or '').strip()
    if not email:
        return DEFAULT_OTP_EMAIL
    local, sep, domain = email.rpartition('@')
    if not sep:
        return DEFAULT_OTP_EMAIL
    domain = domain.lower().strip()
    if not local or not domain:
        return DEFAULT_OTP_EMAIL
    if domain in ('localhost', 'local'):
        return DEFAULT_OTP_EMAIL
    if domain.endswith('.local') or domain.endswith('.localhost'):
        return DEFAULT_OTP_EMAIL
    return email

def mask_email(email):
    if not email or '@' not in email:
        return email
    em = email; at = em.index('@')
    return em[:2] + '***' + em[at:]

def _otp_html(user, otp):
    return f"""
    <div style="font-family:'Segoe UI',sans-serif;max-width:500px;margin:auto;background:#0f172a;border-radius:16px;overflow:hidden;">
      <div style="background:linear-gradient(135deg,#6366f1,#8b5cf6);padding:28px 32px;text-align:center;">
        <h1 style="color:white;margin:0;font-size:22px;">Zero Trust EMR</h1>
        <p style="color:rgba(255,255,255,.8);margin:4px 0 0;font-size:13px;">MUST - BCS/25 - Mbeya</p>
      </div>
      <div style="background:#1e293b;padding:28px 32px;">
        <p style="color:#94a3b8;font-size:14px;">Hello <span style="color:#f1f5f9;font-weight:600;">{user.full_name}</span>,</p>
        <p style="color:#94a3b8;font-size:14px;">Your security verification code is:</p>
        <div style="text-align:center;margin:24px 0;">
          <span style="display:inline-block;background:#6366f1;color:white;font-size:40px;font-weight:900;letter-spacing:14px;padding:18px 28px;border-radius:12px;">{otp}</span>
        </div>
        <div style="background:#0f172a;border-radius:8px;padding:14px 16px;margin-top:16px;">
          <p style="margin:0;color:#64748b;font-size:12px;">Expires in 5 minutes - {request.remote_addr} - {parse_device(request.user_agent.string)}</p>
        </div>
        <p style="color:#475569;font-size:12px;margin-top:16px;">If you did not attempt to log in, contact your system administrator immediately.</p>
      </div>
    </div>"""

def _send_via_sendgrid(api_key, from_email, to_email, subject, html):
    import urllib.request
    data = json.dumps({
        "personalizations": [{"to": [{"email": to_email}]}],
        "from": {"email": from_email, "name": "Zero Trust EMR"},
        "subject": subject,
        "content": [{"type": "text/html", "value": html}]
    }).encode()
    req = urllib.request.Request(
        "https://api.sendgrid.com/v3/mail/send",
        data=data,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        },
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return resp.status in (200, 201, 202)

def _send_via_smtp(host, port, smtp_user, smtp_pass, from_email, to_email, subject, html):
    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject; msg['From'] = from_email; msg['To'] = to_email
    msg.attach(MIMEText(html, 'html'))
    with smtplib.SMTP(host, int(port)) as s:
        s.ehlo(); s.starttls(); s.login(smtp_user, smtp_pass)
        s.sendmail(from_email, to_email, msg.as_string())

def send_otp_email(user, otp):
    host, port, smtp_user, smtp_pass, smtp_from = _get_smtp_cfg()
    subject = f'EMR Security Code: {otp}'
    html = _otp_html(user, otp)

    # Load email config from file for SendGrid key
    _email_cfg_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'email_config.py')
    _email_cfg = {}
    if os.path.exists(_email_cfg_path):
        try:
            with open(_email_cfg_path) as _f: exec(_f.read(), _email_cfg)
        except: pass
    sendgrid_key = _email_cfg.get('SENDGRID_API_KEY', '') or os.environ.get('SENDGRID_API_KEY', '')
    from_email = _email_cfg.get('SMTP_USER', '') or smtp_user

    to_email = otp_destination(user)

    # Try SendGrid API first (works on PythonAnywhere free)
    if sendgrid_key and from_email:
        try:
            _send_via_sendgrid(sendgrid_key, from_email, to_email, subject, html)
            return True, None
        except Exception as e:
            import traceback; traceback.print_exc()
            return False, f"SendGrid error: {e}"

    # Fallback to SMTP (works on localhost)
    if not smtp_user or not smtp_pass:
        return False, "Email not configured. Go to Admin -> Email Settings."
    try:
        _send_via_smtp(host, port, smtp_user, smtp_pass, smtp_from, to_email, subject, html)
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
        # ── Device trust check ──────────────────────────────────────────
        # If this account already has a registered device fingerprint, only
        # that same device may sign in. A different/unknown device is blocked.
        incoming_fp = (request.form.get('device_fp') or '').strip()[:64]
        known_fp    = user.last_fingerprint or ''
        if known_fp and incoming_fp != known_fp:
            log_auth(username,'device_blocked',False,user.id,
                     f'Unknown device {incoming_fp or "(no fingerprint)"} (known: {known_fp})')
            flash('Login blocked: unrecognized device. Contact your administrator.','danger')
            return render_template('auth/login.html')
        # Compute risk against PREVIOUS session's device/IP/fingerprint
        # BEFORE overwriting them with the current login's values.
        from modules.ai_engine import compute_risk_score
        risk = compute_risk_score(user)
        user.last_ip       = request.remote_addr
        user.last_device   = parse_device(request.user_agent.string)
        user.last_fingerprint = (request.form.get('device_fp') or '').strip()[:64]
        ip_location = get_location(request.remote_addr)
        # Only overwrite last_location with IP data if IP returned something useful,
        # or if the user has no location yet. Never replace a good browser-based
        # location with 'Unknown' from a failed IP lookup.
        if ip_location not in ('Unknown', 'Localhost') or not user.last_location:
            user.last_location = ip_location
        db.session.commit()
        # Read email config from file directly
        _email_cfg_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'email_config.py')
        _email_cfg = {}
        if os.path.exists(_email_cfg_path):
            try:
                with open(_email_cfg_path) as _f: exec(_f.read(), _email_cfg)
            except: pass
        _su = _email_cfg.get('SMTP_USER','') or os.environ.get('SMTP_USER','')
        _sp = _email_cfg.get('SMTP_PASS','') or os.environ.get('SMTP_PASS','')
        _sg = _email_cfg.get('SENDGRID_API_KEY','') or os.environ.get('SENDGRID_API_KEY','')
        email_configured = bool((_su and (_sp or _sg)) and '@' in _su)
        # Admin-forced MFA: trigger regardless of email config
        # First-time login: always require OTP
        # Risk-based MFA: only if email is configured
        is_first_login = user.last_login is None
        should_mfa = user.requires_otp or is_first_login or (email_configured and risk['score'] >= 0.35)
        if should_mfa:
            otp = gen_otp()
            user.otp_code = otp; user.otp_expiry = datetime.utcnow()+timedelta(minutes=5); user.otp_verified=False
            db.session.commit()
            sent, err = send_otp_email(user, otp)
            session['pending_user_id'] = user.id
            session['risk_score']      = risk['score']
            session['risk_reason']     = risk['reason']
            log_auth(username,'otp_request',True,user.id,f'Risk={risk["score"]:.2f}|sent={sent}')
            if sent:
                em = mask_email(otp_destination(user))
                flash(f'Verification code sent to {em}','info')
            else:
                flash(f'Verification required. DEMO CODE: {otp} (Email error: {err})','warning')
            return redirect(url_for('auth.verify_otp'))
        login_user(user); user.last_login = datetime.utcnow(); issue_session_token(user); db.session.commit()
        log_auth(username,'login',True,user.id,f'Direct|{user.last_device}|{user.last_location}')
        log_act(user.id,'session_start',details=f'{user.last_location} via {user.last_device}')
        return redirect(role_dashboard(user.role) + '?new_session=1')
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
            user.otp_verified=True; user.last_login=datetime.utcnow()
            # DON'T clear requires_otp — if admin forced it, keep it for every login
            db.session.commit()
            [session.pop(k,None) for k in ['pending_user_id','risk_score','risk_reason']]
            login_user(user); issue_session_token(user); db.session.commit()
            log_auth(user.username,'otp_success',True,user.id)
            log_act(user.id,'session_start',details=f'MFA|{user.last_location}|{user.last_device}')
            flash('Identity verified. Welcome!','success')
            return redirect(role_dashboard(user.role) + '?new_session=1')
        flash('Invalid code. Try again.','danger')
    masked = mask_email(otp_destination(user))
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
    if sent:
        flash(f'A new verification code has been sent to {mask_email(otp_destination(user))}.','info')
    else:
        flash(f'Email failed: {err}. Contact administrator.','danger')
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
    masked = mask_email(otp_destination(current_user))
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
    Called client-side after login (see static/js/location.js) using the
    browser's Geolocation API. This lets us show a real place name even on
    private/LAN IPs (192.168.x.x, localhost) where public IP-geolocation
    services can never resolve a location — they only work for public IPs.

    NOTE: this is DISPLAY-ONLY. Risk scoring (compute_risk_score) already
    ran at login time using the network-derived IP location, which cannot
    be spoofed as easily as a client-reported browser location. We never
    let this endpoint influence risk scoring — a device could always lie
    about its GPS position, so it isn't trustworthy as a security signal
    in a Zero Trust design, only as a friendlier display value.
    """
    data = request.get_json(silent=True) or {}
    city      = (data.get('city') or '').strip()
    country   = (data.get('country') or '').strip()
    detailed  = (data.get('detailed') or '').strip()
    if not city and not country and not detailed:
        return jsonify({'ok': False}), 400

    # Prefer the detailed location string (e.g. "Ikuti, Iyunga, Mbeya")
    # over the basic "city, country" format.
    place = detailed if detailed else ', '.join(p for p in (city, country) if p) or 'Unknown'
    # Clean the location server-side so stored values are consistent
    place = clean_location_text(place)
    # Always update — browser GPS is more accurate than IP-based location.
    # We never let this endpoint influence risk scoring (see docstring),
    # so it's safe to always overwrite for display purposes.
    if place and place != 'Unknown':
        current_user.last_location = place
        db.session.commit()
        log_act(current_user.id, 'location_refined', details=f'Device-reported: {place}')

    return jsonify({'ok': True, 'location': place})
