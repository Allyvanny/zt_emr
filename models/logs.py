from extensions import db
from datetime import datetime

class ActivityLog(db.Model):
    __tablename__ = 'activity_logs'
    id          = db.Column(db.Integer, primary_key=True)
    user_id     = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    action      = db.Column(db.String(100), nullable=False)
    resource    = db.Column(db.String(100))
    resource_id = db.Column(db.Integer)
    ip_address  = db.Column(db.String(45))
    user_agent  = db.Column(db.String(256))
    timestamp   = db.Column(db.DateTime, default=datetime.utcnow)
    session_id  = db.Column(db.String(64))
    status      = db.Column(db.String(20), default='success')
    details     = db.Column(db.Text)
    def to_dict(self):
        return {'id':self.id,'user_id':self.user_id,'action':self.action,
                'resource':self.resource,'ip_address':self.ip_address,
                'timestamp':self.timestamp.isoformat(),'status':self.status,'details':self.details}

class RiskLog(db.Model):
    __tablename__ = 'risk_logs'
    id             = db.Column(db.Integer, primary_key=True)
    user_id        = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    risk_score     = db.Column(db.Float, nullable=False)
    risk_level     = db.Column(db.String(10))
    trigger_reason = db.Column(db.Text)
    action_taken   = db.Column(db.String(100))
    timestamp      = db.Column(db.DateTime, default=datetime.utcnow)
    resolved       = db.Column(db.Boolean, default=False)

class AuthenticationLog(db.Model):
    __tablename__ = 'authentication_logs'
    id         = db.Column(db.Integer, primary_key=True)
    username   = db.Column(db.String(80))
    user_id    = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    event_type = db.Column(db.String(50))
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.String(256))
    timestamp  = db.Column(db.DateTime, default=datetime.utcnow)
    success    = db.Column(db.Boolean, default=True)
    details    = db.Column(db.Text)
