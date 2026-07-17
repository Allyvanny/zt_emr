from extensions import db
from datetime import datetime

class LabRequest(db.Model):
    __tablename__ = 'lab_requests'
    id            = db.Column(db.Integer, primary_key=True)
    request_no    = db.Column(db.String(20), unique=True, nullable=False)
    patient_id    = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False)
    requested_by  = db.Column(db.Integer, db.ForeignKey('users.id'))
    processed_by  = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    test_type     = db.Column(db.String(100), nullable=False)
    test_category = db.Column(db.String(60))   # Haematology|Biochemistry|Microbiology|Serology|Urinalysis|Parasitology
    priority      = db.Column(db.String(20), default='routine')  # routine|urgent|stat
    status        = db.Column(db.String(20), default='pending')  # pending|in_progress|completed|cancelled
    clinical_notes= db.Column(db.Text)
    specimen_type = db.Column(db.String(60))
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at  = db.Column(db.DateTime)
    requester     = db.relationship('User', foreign_keys=[requested_by])
    processor     = db.relationship('User', foreign_keys=[processed_by])
    result        = db.relationship('LabResult', backref='request', uselist=False, lazy=True)

class LabResult(db.Model):
    __tablename__ = 'lab_results'
    id             = db.Column(db.Integer, primary_key=True)
    request_id     = db.Column(db.Integer, db.ForeignKey('lab_requests.id'), nullable=False, unique=True)
    result_data    = db.Column(db.Text, nullable=False)   # JSON or text
    reference_range= db.Column(db.Text)
    interpretation = db.Column(db.String(40))  # normal|abnormal|critical
    comments       = db.Column(db.Text)
    verified_by    = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)
    verifier       = db.relationship('User', foreign_keys=[verified_by])
