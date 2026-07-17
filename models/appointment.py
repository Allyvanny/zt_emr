from extensions import db
from datetime import datetime

class Appointment(db.Model):
    __tablename__ = 'appointments'

    id              = db.Column(db.Integer, primary_key=True)
    appointment_no  = db.Column(db.String(20), unique=True, nullable=False)
    patient_id      = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False)
    doctor_id       = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    requested_by    = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)  # receptionist
    appointment_date= db.Column(db.DateTime, nullable=False)
    reason          = db.Column(db.Text)
    notes           = db.Column(db.Text)
    status          = db.Column(db.String(20), default='pending')
    # pending | approved | rejected | completed | cancelled
    approved_at     = db.Column(db.DateTime)
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)

    patient    = db.relationship('Patient', foreign_keys=[patient_id])
    doctor     = db.relationship('User',    foreign_keys=[doctor_id])
    requester  = db.relationship('User',    foreign_keys=[requested_by])
