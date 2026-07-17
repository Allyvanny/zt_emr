from extensions import db
from datetime import datetime

class Drug(db.Model):
    __tablename__ = 'drugs'
    id           = db.Column(db.Integer, primary_key=True)
    name         = db.Column(db.String(120), nullable=False)
    generic_name = db.Column(db.String(120))
    category     = db.Column(db.String(60))
    unit         = db.Column(db.String(20), default='Tablets')
    stock_qty    = db.Column(db.Integer, default=0)
    reorder_level= db.Column(db.Integer, default=50)
    unit_price   = db.Column(db.Float, default=0.0)
    expiry_date  = db.Column(db.Date)
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def is_low_stock(self): return self.stock_qty <= self.reorder_level
    @property
    def is_out_of_stock(self): return self.stock_qty == 0

class Prescription(db.Model):
    __tablename__ = 'prescriptions'
    id               = db.Column(db.Integer, primary_key=True)
    prescription_no  = db.Column(db.String(20), unique=True, nullable=False)
    patient_id       = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False)
    medical_record_id= db.Column(db.Integer, db.ForeignKey('medical_records.id'), nullable=True)
    prescribed_by    = db.Column(db.Integer, db.ForeignKey('users.id'))
    dispensed_by     = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    status           = db.Column(db.String(20), default='pending')  # pending|dispensed|cancelled
    notes            = db.Column(db.Text)
    created_at       = db.Column(db.DateTime, default=datetime.utcnow)
    dispensed_at     = db.Column(db.DateTime)
    items            = db.relationship('PrescriptionItem', backref='prescription', lazy=True)
    patient          = db.relationship('Patient', foreign_keys=[patient_id])
    prescriber       = db.relationship('User', foreign_keys=[prescribed_by])
    dispenser        = db.relationship('User', foreign_keys=[dispensed_by])

class PrescriptionItem(db.Model):
    __tablename__ = 'prescription_items'
    id              = db.Column(db.Integer, primary_key=True)
    prescription_id = db.Column(db.Integer, db.ForeignKey('prescriptions.id'), nullable=False)
    drug_id         = db.Column(db.Integer, db.ForeignKey('drugs.id'), nullable=False)
    dosage          = db.Column(db.String(80))
    frequency       = db.Column(db.String(80))
    duration        = db.Column(db.String(80))
    quantity        = db.Column(db.Integer, default=1)
    dispensed_qty   = db.Column(db.Integer, default=0)
    drug            = db.relationship('Drug', foreign_keys=[drug_id])
