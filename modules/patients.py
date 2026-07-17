from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, session
from flask_login import login_required, current_user
from models.patient import Patient, MedicalRecord, VitalSign, Allergy
from models.logs import ActivityLog, RiskLog
from extensions import db
from datetime import datetime
from functools import wraps

patients_bp = Blueprint('patients', __name__)

PERMS = {
    'admin':        ['view','register','add_record','edit','delete'],
    'doctor':       ['view','register','add_record','edit'],
    'nurse':        ['view','register','add_record'],
    'receptionist': ['view','register'],
    'pharmacist':   ['view'],
    'lab_technician':['view'],
}

def perm(p):
    def dec(f):
        @wraps(f)
        def w(*a,**k):
            if p not in PERMS.get(current_user.role,[]): abort(403)
            return f(*a,**k)
        return w
    return dec

def log_act(action, resource=None, rid=None, status='success', details=None):
    db.session.add(ActivityLog(user_id=current_user.id, action=action, resource=resource,
        resource_id=rid, ip_address=request.remote_addr,
        user_agent=request.user_agent.string[:256], session_id=session.get('_id',''),
        status=status, details=details))
    db.session.commit()

def escalate():
    from modules.ai_engine import check_session_risk
    if check_session_risk(current_user): return redirect(url_for('auth.session_mfa'))
    return None

@patients_bp.route('/dashboard')
@login_required
def dashboard():
    e = escalate()
    if e: return e
    total_p = Patient.query.count()
    total_r = MedicalRecord.query.count()
    recent  = Patient.query.order_by(Patient.registered_at.desc()).limit(8).all()
    risk_users = []
    if current_user.role == 'admin':
        risk_users = RiskLog.query.order_by(RiskLog.timestamp.desc()).limit(10).all()
    from modules.ai_engine import compute_risk_score
    my_risk = compute_risk_score(current_user)
    log_act('view_dashboard','dashboard')
    return render_template('patients/dashboard.html', total_patients=total_p,
                           total_records=total_r, recent_patients=recent,
                           risk_users=risk_users, my_risk=my_risk)

@patients_bp.route('/list')
@login_required
@perm('view')
def patient_list():
    e = escalate()
    if e: return e
    search = request.args.get('search','').strip()
    page   = request.args.get('page',1,type=int)
    q = Patient.query
    if search:
        q = q.filter(Patient.full_name.ilike(f'%{search}%')|Patient.patient_id.ilike(f'%{search}%'))
    patients = q.order_by(Patient.registered_at.desc()).paginate(page=page,per_page=25)
    log_act('view_patient_list','patient',details=f'search={search}')
    return render_template('patients/list.html', patients=patients, search=search)

@patients_bp.route('/register', methods=['GET','POST'])
@login_required
@perm('register')
def register_patient():
    e = escalate()
    if e: return e
    if request.method == 'POST':
        fn = request.form.get('full_name','').strip()
        if not fn: flash('Full name required.','danger'); return render_template('patients/register.html')
        dob = None
        dob_s = request.form.get('date_of_birth','')
        if dob_s:
            try: dob = datetime.strptime(dob_s,'%Y-%m-%d').date()
            except: flash('Invalid date.','danger'); return render_template('patients/register.html')
        pid = f'PT-{datetime.utcnow().year}-{Patient.query.count()+1:05d}'
        p = Patient(patient_id=pid, full_name=fn, date_of_birth=dob,
                    gender=request.form.get('gender',''),
                    phone=request.form.get('phone','').strip(),
                    address=request.form.get('address','').strip(),
                    emergency_contact=request.form.get('emergency_contact','').strip(),
                    blood_group=request.form.get('blood_group',''),
                    registered_by=current_user.id)
        db.session.add(p); db.session.commit()
        log_act('register_patient','patient',p.id,details=f'Registered {fn}')
        flash(f'Patient {fn} registered. ID: {pid}','success')
        return redirect(url_for('patients.view_patient',patient_id=p.id))
    return render_template('patients/register.html')

@patients_bp.route('/<int:patient_id>')
@login_required
@perm('view')
def view_patient(patient_id):
    e = escalate()
    if e: return e
    p = Patient.query.get_or_404(patient_id)
    records = MedicalRecord.query.filter_by(patient_id=p.id).order_by(MedicalRecord.visit_date.desc()).all()
    from models.pharmacy import Prescription
    from models.laboratory import LabRequest
    prescriptions = Prescription.query.filter_by(patient_id=p.id).order_by(Prescription.created_at.desc()).limit(5).all()
    lab_requests  = LabRequest.query.filter_by(patient_id=p.id).order_by(LabRequest.created_at.desc()).limit(5).all()
    allergies     = Allergy.query.filter_by(patient_id=p.id).order_by(Allergy.recorded_at.desc()).all()
    latest_vitals = VitalSign.query.filter_by(patient_id=p.id).order_by(VitalSign.recorded_at.desc()).first()
    log_act('view_patient','patient',p.id,details=f'Viewed {p.full_name}')
    return render_template('patients/view.html',patient=p,records=records,
                           prescriptions=prescriptions,lab_requests=lab_requests,
                           allergies=allergies,latest_vitals=latest_vitals)

@patients_bp.route('/<int:patient_id>/add-record', methods=['GET','POST'])
@login_required
@perm('add_record')
def add_record(patient_id):
    e = escalate()
    if e: return e
    p = Patient.query.get_or_404(patient_id)
    from models.pharmacy import Drug
    drugs = Drug.query.order_by(Drug.name).all()
    if request.method == 'POST':
        rec = MedicalRecord(patient_id=p.id, doctor_id=current_user.id,
            diagnosis=request.form.get('diagnosis','').strip(),
            symptoms=request.form.get('symptoms','').strip(),
            treatment=request.form.get('treatment','').strip(),
            prescription=request.form.get('prescription','').strip(),
            lab_results=request.form.get('lab_results','').strip(),
            notes=request.form.get('notes','').strip(),
            is_confidential='is_confidential' in request.form)
        db.session.add(rec); db.session.flush()

        # Auto-create prescription if prescribed
        rx_notes = request.form.get('prescription','').strip()
        if rx_notes:
            from models.pharmacy import Prescription
            rx_no = f'RX-{datetime.utcnow().year}-{Prescription.query.count()+1:05d}'
            rx = Prescription(prescription_no=rx_no, patient_id=p.id,
                              medical_record_id=rec.id, prescribed_by=current_user.id,
                              notes=rx_notes, status='pending')
            db.session.add(rx)

        # Auto-create lab request if ordered
        lab_ordered = request.form.getlist('lab_tests')
        for test in lab_ordered:
            if test:
                from models.laboratory import LabRequest
                rno = f'LAB-{datetime.utcnow().year}-{LabRequest.query.count()+1:05d}'
                db.session.add(LabRequest(request_no=rno, patient_id=p.id,
                    requested_by=current_user.id, test_type=test,
                    test_category='General', priority='routine',
                    clinical_notes=request.form.get('diagnosis',''),
                    specimen_type='Blood', status='pending'))

        db.session.commit()
        log_act('add_record','patient',p.id,details=f'Record for {p.full_name}')
        flash('Medical record added successfully.','success')
        return redirect(url_for('patients.view_patient',patient_id=p.id))
    return render_template('patients/add_record.html',patient=p,drugs=drugs)


@patients_bp.route('/<int:patient_id>/vital-signs', methods=['GET','POST'])
@login_required
@perm('add_record')
def vital_signs(patient_id):
    e = escalate()
    if e: return e
    p = Patient.query.get_or_404(patient_id)
    prev = VitalSign.query.filter_by(patient_id=p.id).order_by(VitalSign.recorded_at.desc()).first()
    if request.method == 'POST':
        def _float(k):
            v = request.form.get(k,'').strip()
            return float(v) if v else None
        def _int(k):
            v = request.form.get(k,'').strip()
            return int(v) if v else None
        temp   = _float('temperature_celsius')
        sys    = _int('bp_systolic')
        dia    = _int('bp_diastolic')
        pulse  = _int('pulse_rate')
        resp   = _int('respiratory_rate')
        spo2   = _int('spo2_percent')
        weight = _float('weight_kg')
        height = _float('height_cm')
        bmi    = round(weight / ((height/100)**2), 1) if weight and height and height > 0 else None
        vs = VitalSign(patient_id=p.id, recorded_by=current_user.id,
                       temperature_celsius=temp, bp_systolic=sys, bp_diastolic=dia,
                       pulse_rate=pulse, respiratory_rate=resp, spo2_percent=spo2,
                       weight_kg=weight, height_cm=height, bmi=bmi,
                       notes=request.form.get('notes','').strip())
        db.session.add(vs); db.session.commit()
        log_act('record_vitals','patient',p.id,details=f'Vitals for {p.full_name}')
        flash('Vital signs recorded successfully.','success')
        return redirect(url_for('patients.view_patient',patient_id=p.id))
    return render_template('patients/vital_signs.html', patient=p, prev=prev)


@patients_bp.route('/<int:patient_id>/allergies/add', methods=['POST'])
@login_required
@perm('add_record')
def add_allergy(patient_id):
    p = Patient.query.get_or_404(patient_id)
    allergen = request.form.get('allergen','').strip()
    if not allergen:
        flash('Allergen name is required.','danger')
        return redirect(url_for('patients.view_patient',patient_id=p.id))
    a = Allergy(patient_id=p.id, allergen=allergen,
                reaction=request.form.get('reaction','').strip(),
                severity=request.form.get('severity','moderate'),
                recorded_by=current_user.id,
                notes=request.form.get('notes','').strip())
    db.session.add(a); db.session.commit()
    log_act('add_allergy','patient',p.id,details=f'Allergy: {allergen}')
    flash(f'Allergy "{allergen}" recorded.','success')
    return redirect(url_for('patients.view_patient',patient_id=p.id))


@patients_bp.route('/<int:patient_id>/allergies/<int:allergy_id>/resolve', methods=['POST'])
@login_required
@perm('add_record')
def resolve_allergy(patient_id, allergy_id):
    a = Allergy.query.get_or_404(allergy_id)
    a.status = 'resolved'
    db.session.commit()
    log_act('resolve_allergy','patient',patient_id,details=f'Resolved: {a.allergen}')
    flash(f'Allergy "{a.allergen}" marked as resolved.','success')
    return redirect(url_for('patients.view_patient',patient_id=patient_id))
