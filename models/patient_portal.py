from extensions import db
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from flask_login import UserMixin

class PatientAccount(db.Model, UserMixin):
    """
    Separate login account for patients.
    Linked to the patients table via patient_id (the PT-XXXX number).
    No MFA required — just username + password.
    """
    __tablename__ = 'patient_accounts'

    id              = db.Column(db.Integer, primary_key=True)
    username        = db.Column(db.String(80), unique=True, nullable=False)
    password_hash   = db.Column(db.String(256), nullable=False)
    full_name       = db.Column(db.String(120), nullable=False)
    email           = db.Column(db.String(120), unique=True, nullable=False)
    phone           = db.Column(db.String(30))
    date_of_birth   = db.Column(db.Date)
    gender          = db.Column(db.String(10))
    address         = db.Column(db.String(200))
    emergency_contact = db.Column(db.String(120))
    blood_group     = db.Column(db.String(5))
    avatar          = db.Column(db.String(200))
    is_active       = db.Column(db.Boolean, default=True)
    patient_id      = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=True)
    assigned_doctor_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)
    last_login      = db.Column(db.DateTime)
    session_token   = db.Column(db.String(64))
    last_ip         = db.Column(db.String(45))
    last_device     = db.Column(db.String(300))
    last_location   = db.Column(db.String(120))
    last_fingerprint = db.Column(db.String(64))

    # Relationships
    patient         = db.relationship('Patient', foreign_keys=[patient_id], backref='account')
    assigned_doctor = db.relationship('User', foreign_keys=[assigned_doctor_id])
    messages_sent   = db.relationship('Message', foreign_keys='Message.sender_patient_id', backref='sender_patient', lazy=True)
    messages_received=db.relationship('Message', foreign_keys='Message.receiver_patient_id', backref='receiver_patient', lazy=True)
    appointment_requests = db.relationship('AppointmentRequest', backref='patient_account', lazy=True)

    def set_password(self, p): self.password_hash = generate_password_hash(p)
    def check_password(self, p): return check_password_hash(self.password_hash, p)
    def get_id(self): return f'patient_{self.id}'   # prefix so we can distinguish from staff
    def __repr__(self): return f'<PatientAccount {self.username}>'


class Message(db.Model):
    """
    Messages between patients and doctors/nurses.
    """
    __tablename__ = 'messages'

    id                  = db.Column(db.Integer, primary_key=True)
    subject             = db.Column(db.String(200), nullable=False)
    body                = db.Column(db.Text, nullable=False)
    message_type        = db.Column(db.String(30), default='general')
    # general | appointment_request | medical_advice | progress_update | urgent

    # Sender — either a patient or a staff member
    sender_patient_id   = db.Column(db.Integer, db.ForeignKey('patient_accounts.id'), nullable=True)
    sender_staff_id     = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    # Receiver — either a patient or a staff member
    receiver_patient_id = db.Column(db.Integer, db.ForeignKey('patient_accounts.id'), nullable=True)
    receiver_staff_id   = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    is_read             = db.Column(db.Boolean, default=False)
    read_at             = db.Column(db.DateTime)
    reply_to_id         = db.Column(db.Integer, db.ForeignKey('messages.id'), nullable=True)
    created_at          = db.Column(db.DateTime, default=datetime.utcnow)

    sender_staff    = db.relationship('User', foreign_keys=[sender_staff_id])
    receiver_staff  = db.relationship('User', foreign_keys=[receiver_staff_id])
    replies         = db.relationship('Message', backref=db.backref('parent', remote_side=[id]), lazy=True)

    @property
    def sender_name(self):
        if self.sender_patient: return self.sender_patient.full_name
        if self.sender_staff:   return f'Dr. {self.sender_staff.full_name}' if self.sender_staff.role=='doctor' else self.sender_staff.full_name
        return 'Unknown'

    @property
    def type_icon(self):
        icons = {'general':'💬','appointment_request':'📅','medical_advice':'🩺','progress_update':'📊','urgent':'🚨'}
        return icons.get(self.message_type, '💬')


class AppointmentRequest(db.Model):
    """
    Appointment requests submitted by patients through the portal.
    """
    __tablename__ = 'appointment_requests'

    id                  = db.Column(db.Integer, primary_key=True)
    request_no          = db.Column(db.String(20), unique=True, nullable=False)
    patient_account_id  = db.Column(db.Integer, db.ForeignKey('patient_accounts.id'), nullable=False)
    preferred_doctor_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    preferred_date      = db.Column(db.DateTime)
    preferred_date_2    = db.Column(db.DateTime)   # second choice
    reason              = db.Column(db.Text, nullable=False)
    urgency             = db.Column(db.String(20), default='routine')  # routine | urgent | emergency
    status              = db.Column(db.String(20), default='pending')
    # pending | approved | rejected | cancelled
    response_notes      = db.Column(db.Text)
    reviewed_by         = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    reviewed_at         = db.Column(db.DateTime)
    created_at          = db.Column(db.DateTime, default=datetime.utcnow)

    preferred_doctor    = db.relationship('User', foreign_keys=[preferred_doctor_id])
    reviewer            = db.relationship('User', foreign_keys=[reviewed_by])
