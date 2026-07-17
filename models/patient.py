from extensions import db
from datetime import datetime

class Patient(db.Model):
    __tablename__ = 'patients'
    id                = db.Column(db.Integer, primary_key=True)
    patient_id        = db.Column(db.String(20), unique=True, nullable=False)
    full_name         = db.Column(db.String(120), nullable=False)
    date_of_birth     = db.Column(db.Date)
    gender            = db.Column(db.String(10))
    phone             = db.Column(db.String(20))
    address           = db.Column(db.String(200))
    emergency_contact = db.Column(db.String(120))
    blood_group       = db.Column(db.String(5))
    registered_at     = db.Column(db.DateTime, default=datetime.utcnow)
    registered_by     = db.Column(db.Integer, db.ForeignKey('users.id'))
    medical_records   = db.relationship('MedicalRecord', backref='patient', lazy=True)
    lab_requests      = db.relationship('LabRequest',    backref='patient', lazy=True)
    vital_signs       = db.relationship('VitalSign',     backref='patient', lazy=True)
    allergies         = db.relationship('Allergy',       backref='patient', lazy=True)

class MedicalRecord(db.Model):
    __tablename__ = 'medical_records'
    id              = db.Column(db.Integer, primary_key=True)
    patient_id      = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False)
    doctor_id       = db.Column(db.Integer, db.ForeignKey('users.id'))
    visit_date      = db.Column(db.DateTime, default=datetime.utcnow)
    diagnosis       = db.Column(db.Text)
    symptoms        = db.Column(db.Text)
    treatment       = db.Column(db.Text)
    prescription    = db.Column(db.Text)
    lab_results     = db.Column(db.Text)
    notes           = db.Column(db.Text)
    is_confidential = db.Column(db.Boolean, default=False)
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)
    doctor          = db.relationship('User', foreign_keys=[doctor_id])
    prescriptions   = db.relationship('Prescription', backref='medical_record', lazy=True)

class VitalSign(db.Model):
    __tablename__ = 'vital_signs'
    id                 = db.Column(db.Integer, primary_key=True)
    patient_id         = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False)
    recorded_by        = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    recorded_at        = db.Column(db.DateTime, default=datetime.utcnow)
    temperature_celsius = db.Column(db.Float)
    bp_systolic        = db.Column(db.Integer)
    bp_diastolic       = db.Column(db.Integer)
    pulse_rate         = db.Column(db.Integer)
    respiratory_rate   = db.Column(db.Integer)
    spo2_percent       = db.Column(db.Integer)
    weight_kg          = db.Column(db.Float)
    height_cm          = db.Column(db.Float)
    bmi                = db.Column(db.Float)
    notes              = db.Column(db.Text)
    recorder           = db.relationship('User', foreign_keys=[recorded_by])

class Allergy(db.Model):
    __tablename__ = 'allergies'
    id           = db.Column(db.Integer, primary_key=True)
    patient_id   = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False)
    allergen     = db.Column(db.String(120), nullable=False)
    reaction     = db.Column(db.String(200))
    severity     = db.Column(db.String(20), default='moderate')
    status       = db.Column(db.String(20), default='active')
    recorded_by  = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    recorded_at  = db.Column(db.DateTime, default=datetime.utcnow)
    notes        = db.Column(db.Text)
    recorder     = db.relationship('User', foreign_keys=[recorded_by])
