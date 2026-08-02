from extensions import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id              = db.Column(db.Integer, primary_key=True)
    username        = db.Column(db.String(80), unique=True, nullable=False)
    password_hash   = db.Column(db.String(256), nullable=False)
    full_name       = db.Column(db.String(120), nullable=False)
    role            = db.Column(db.String(30), nullable=False)
    email           = db.Column(db.String(120), unique=True, nullable=False)
    avatar          = db.Column(db.String(200), nullable=True)   # filename in static/uploads/avatars/
    is_active       = db.Column(db.Boolean, default=True)
    is_locked       = db.Column(db.Boolean, default=False)
    failed_attempts = db.Column(db.Integer, default=0)
    last_login      = db.Column(db.DateTime)
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)
    created_by      = db.Column(db.Integer, nullable=True)
    otp_code        = db.Column(db.String(6))
    otp_expiry      = db.Column(db.DateTime)
    otp_verified    = db.Column(db.Boolean, default=False)
    requires_otp    = db.Column(db.Boolean, default=False)
    last_ip         = db.Column(db.String(45))
    last_device     = db.Column(db.String(300))
    last_location   = db.Column(db.String(120))
    session_token   = db.Column(db.String(64))
    last_fingerprint = db.Column(db.String(64))

    activity_logs = db.relationship('ActivityLog', backref='user', lazy=True, foreign_keys='ActivityLog.user_id')
    risk_logs     = db.relationship('RiskLog',     backref='user', lazy=True, foreign_keys='RiskLog.user_id')

    def set_password(self, p): self.password_hash = generate_password_hash(p)
    def check_password(self, p): return check_password_hash(self.password_hash, p)

    @property
    def avatar_url(self):
        if self.avatar:
            return f'/static/uploads/avatars/{self.avatar}'
        return None

    def __repr__(self): return f'<User {self.username} [{self.role}]>'
