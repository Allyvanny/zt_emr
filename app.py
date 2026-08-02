"""
Zero Trust Security System for EMR
Author: Alto Dezdel Kiyamba | MUST BCS/25 | Reg: 23100533350059
Supervisor: Ms. Prisca Maro
"""
from flask import Flask, redirect, url_for, send_from_directory, session, flash
from extensions import db, login_manager
from datetime import datetime, timezone, timedelta
import os

app = Flask(__name__)
app.secret_key = os.urandom(32)

# East African Time (EAT) = UTC+3
EAT = timezone(timedelta(hours=3))

def _to_eat(dt, fmt):
    """Convert a datetime (or date) to East African Time string."""
    if dt is None:
        return ''
    # Plain date objects have no tzinfo — just format them as-is
    if isinstance(dt, datetime) and dt.tzinfo is not None:
        return dt.astimezone(EAT).strftime(fmt)
    if isinstance(dt, datetime):
        dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(EAT).strftime(fmt)
    # datetime.date — no timezone concept, format directly
    return dt.strftime(fmt)

@app.template_filter('eat')
def eat_filter(dt, fmt='%d %b %Y %H:%M'):
    return _to_eat(dt, fmt)

@app.template_filter('eat_date')
def eat_date_filter(dt, fmt='%d %b %Y'):
    return _to_eat(dt, fmt)

@app.template_filter('eat_time')
def eat_time_filter(dt, fmt='%H:%M'):
    return _to_eat(dt, fmt)

@app.template_filter('eat_datetime')
def eat_datetime_filter(dt, fmt='%d %B %Y at %H:%M'):
    return _to_eat(dt, fmt)

@app.template_filter('clean_loc')
def clean_loc_filter(text):
    """Normalize location strings for display."""
    from modules.auth import clean_location_text
    return clean_location_text(text) if text else ''
_basedir = os.path.abspath(os.path.dirname(__file__))
_db_url = os.environ.get('DATABASE_URL', '')
if not _db_url:
    # Auto-detect: MySQL if XAMPP is running locally, else SQLite
    try:
        import pymysql
        _conn = pymysql.connect(host='localhost', port=3306, user='root', password='', database='zt_emr', connect_timeout=2)
        _conn.close()
        _db_url = 'mysql+pymysql://root:@localhost:3306/zt_emr'
    except Exception:
        _db_url = 'sqlite:///' + os.path.join(_basedir, 'zt_emr.db')
app.config['SQLALCHEMY_DATABASE_URI'] = _db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
if 'mysql' in _db_url:
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_pre_ping': True,
        'pool_recycle': 280,
    }
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024

db.init_app(app)
login_manager.init_app(app)
login_manager.login_view = 'auth.login'


def _migrate_schema():
    """Add columns introduced after initial deploy without breaking existing DBs."""
    from sqlalchemy import inspect, text
    with app.app_context():
        insp = inspect(db.engine)
        if insp.has_table('users'):
            cols = {c['name'] for c in insp.get_columns('users')}
            if 'session_token' not in cols:
                with db.engine.begin() as conn:
                    conn.execute(text('ALTER TABLE users ADD COLUMN session_token VARCHAR(64)'))
        if insp.has_table('patient_accounts'):
            cols = {c['name'] for c in insp.get_columns('patient_accounts')}
            if 'session_token' not in cols:
                with db.engine.begin() as conn:
                    conn.execute(text('ALTER TABLE patient_accounts ADD COLUMN session_token VARCHAR(64)'))
            cols = {c['name'] for c in insp.get_columns('patient_accounts')}
            if 'last_fingerprint' not in cols:
                with db.engine.begin() as conn:
                    conn.execute(text('ALTER TABLE patient_accounts ADD COLUMN last_fingerprint VARCHAR(64)'))
            cols = {c['name'] for c in insp.get_columns('patient_accounts')}
            if 'last_ip' not in cols:
                with db.engine.begin() as conn:
                    conn.execute(text('ALTER TABLE patient_accounts ADD COLUMN last_ip VARCHAR(45)'))
            cols = {c['name'] for c in insp.get_columns('patient_accounts')}
            if 'last_device' not in cols:
                with db.engine.begin() as conn:
                    conn.execute(text('ALTER TABLE patient_accounts ADD COLUMN last_device VARCHAR(300)'))
            cols = {c['name'] for c in insp.get_columns('patient_accounts')}
            if 'last_location' not in cols:
                with db.engine.begin() as conn:
                    conn.execute(text('ALTER TABLE patient_accounts ADD COLUMN last_location VARCHAR(120)'))
            cols = {c['name'] for c in insp.get_columns('patient_accounts')}
            if 'otp_code' not in cols:
                with db.engine.begin() as conn:
                    conn.execute(text('ALTER TABLE patient_accounts ADD COLUMN otp_code VARCHAR(6)'))
            cols = {c['name'] for c in insp.get_columns('patient_accounts')}
            if 'otp_expiry' not in cols:
                with db.engine.begin() as conn:
                    conn.execute(text('ALTER TABLE patient_accounts ADD COLUMN otp_expiry DATETIME'))
        if insp.has_table('users'):
            cols = {c['name'] for c in insp.get_columns('users')}
            if 'last_fingerprint' not in cols:
                with db.engine.begin() as conn:
                    conn.execute(text('ALTER TABLE users ADD COLUMN last_fingerprint VARCHAR(64)'))


_migrate_schema()

@login_manager.user_loader
def load_user(user_id):
    """
    Supports two user types:
    - Staff users: stored in users table, id is plain integer
    - Patient accounts: stored in patient_accounts table, id prefixed with 'patient_'
    """
    if str(user_id).startswith('patient_'):
        from models.patient_portal import PatientAccount
        pid = int(str(user_id).replace('patient_', ''))
        return PatientAccount.query.get(pid)
    else:
        from models.user import User
        return User.query.get(int(user_id))


@app.before_request
def enforce_single_session():
    """One active login per account: a newer login invalidates all older sessions."""
    from flask_login import current_user, logout_user
    if not current_user.is_authenticated:
        return
    uid = current_user.get_id()
    db_token = getattr(current_user, 'session_token', None)
    if db_token and session.get('zt_session_token') != db_token:
        try:
            if not str(uid).startswith('patient_'):
                from modules.auth import log_act
                log_act(current_user.id, 'session_kicked', details='Superseded by a newer login on another device')
        except Exception:
            pass
        logout_user()
        flash('Signed out: this account was just logged in from another device.', 'warning')
        if str(uid).startswith('patient_'):
            return redirect(url_for('patient_auth.login'))
        return redirect(url_for('auth.login'))

# Load saved email config
email_config_path = os.path.join(os.path.dirname(__file__), 'email_config.py')
if os.path.exists(email_config_path):
    cfg = {}
    try:
        with open(email_config_path) as f:
            exec(f.read(), cfg)
        os.environ.setdefault('SMTP_HOST', cfg.get('SMTP_HOST', ''))
        os.environ.setdefault('SMTP_PORT', str(cfg.get('SMTP_PORT', 587)))
        os.environ.setdefault('SMTP_USER', cfg.get('SMTP_USER', ''))
        os.environ.setdefault('SMTP_PASS', cfg.get('SMTP_PASS', ''))
        os.environ.setdefault('SMTP_FROM', cfg.get('SMTP_FROM', ''))
    except:
        pass

# Register blueprints
from modules.auth            import auth_bp
from modules.patients        import patients_bp
from modules.pharmacy        import pharmacy_bp
from modules.laboratory      import laboratory_bp
from modules.admin           import admin_bp
from modules.forensics       import forensics_bp
from modules.ai_engine       import ai_bp
from modules.profile         import profile_bp
from modules.appointments    import appointments_bp
from modules.patient_auth    import patient_auth_bp
from modules.patient_portal  import patient_portal_bp

app.register_blueprint(auth_bp,           url_prefix='/auth')
app.register_blueprint(patients_bp,       url_prefix='/patients')
app.register_blueprint(pharmacy_bp,       url_prefix='/pharmacy')
app.register_blueprint(laboratory_bp,     url_prefix='/lab')
app.register_blueprint(admin_bp,          url_prefix='/admin')
app.register_blueprint(forensics_bp,      url_prefix='/forensics')
app.register_blueprint(ai_bp,             url_prefix='/ai')
app.register_blueprint(profile_bp,        url_prefix='')
app.register_blueprint(appointments_bp,   url_prefix='')
app.register_blueprint(patient_auth_bp,   url_prefix='')
app.register_blueprint(patient_portal_bp, url_prefix='')

# Patient portal EN/SW translations — available as {{ t('key') }} in all templates
from modules.i18n import register_i18n
register_i18n(app)

@app.route('/')
def index():
    return redirect(url_for('auth.login'))

@app.route('/static/uploads/avatars/<filename>')
def uploaded_avatar(filename):
    folder = os.path.join(app.root_path, 'static', 'uploads', 'avatars')
    return send_from_directory(folder, filename)

@app.errorhandler(403)
def forbidden(e):   return "<h2>403 — Access Denied</h2><a href='/'>Home</a>", 403
@app.errorhandler(404)
def not_found(e):   return "<h2>404 — Not Found</h2><a href='/'>Home</a>", 404
@app.errorhandler(413)
def too_large(e):   return "<h2>413 — File too large (max 5MB)</h2><a href='/'>Home</a>", 413

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        from modules.seed import seed_data
        seed_data()
    app.run(debug=True, port=5000, host='0.0.0.0')
