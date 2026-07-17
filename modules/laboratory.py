from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, session
from flask_login import login_required, current_user
from models.laboratory import LabRequest, LabResult
from models.patient import Patient
from models.logs import ActivityLog
from extensions import db
from datetime import datetime
from functools import wraps

laboratory_bp = Blueprint('laboratory', __name__)

TEST_CATEGORIES = {
    'Haematology':  ['Full Blood Count (FBC)','Haemoglobin (Hgb)','Platelet Count','ESR','Blood Film (Malaria)','Reticulocyte Count','Prothrombin Time (PT)','APTT'],
    'Biochemistry': ['Blood Glucose (FBG/RBG)','HbA1c','Lipid Profile','Liver Function Tests (LFTs)','Renal Function Tests (RFTs)','Electrolytes','Uric Acid','Albumin','CRP','BNP'],
    'Microbiology': ['Blood Culture & Sensitivity','Urine C&S','Sputum Culture','Wound Swab C&S','Stool Culture','Throat Swab','CSF Culture','AFB Smear'],
    'Serology':     ['HIV Rapid Test','Widal Test','Hepatitis B Surface Antigen','Hepatitis C Antibody','RPR (Syphilis)','Brucella Agglutination','Dengue NS1 Ag','COVID-19 Antigen'],
    'Urinalysis':   ['Urinalysis (Dipstick)','Urine Microscopy','24hr Urine Protein','Urine Pregnancy Test','Urine Culture'],
    'Parasitology': ['Malaria RDT','Malaria Thick/Thin Film','Stool O&E (Ova & Eggs)','Filarial Blood Film','Kato-Katz (Schistosoma)'],
    'Immunology':   ['CD4 Count','Viral Load','ANA','ANCA','Rheumatoid Factor','Complement C3/C4'],
    'Histopathology':['Biopsy Analysis','FNAC','PAP Smear','Bone Marrow Aspirate'],
}

def lab_required(f):
    @wraps(f)
    def w(*a,**k):
        if current_user.role not in ('lab_technician','admin','doctor'): abort(403)
        return f(*a,**k)
    return w

def lab_tech_only(f):
    @wraps(f)
    def w(*a,**k):
        if current_user.role not in ('lab_technician','admin'): abort(403)
        return f(*a,**k)
    return w

def log_act(action, resource=None, rid=None, details=None):
    db.session.add(ActivityLog(user_id=current_user.id, action=action, resource=resource,
        resource_id=rid, ip_address=request.remote_addr,
        user_agent=request.user_agent.string[:256], session_id=session.get('_id',''), details=details))
    db.session.commit()

def escalate():
    from modules.ai_engine import check_session_risk
    if check_session_risk(current_user): return redirect(url_for('auth.session_mfa'))
    return None

@laboratory_bp.route('/dashboard')
@login_required
@lab_tech_only
def dashboard():
    e = escalate()
    if e: return e
    pending    = LabRequest.query.filter_by(status='pending').count()
    in_progress= LabRequest.query.filter_by(status='in_progress').count()
    completed  = LabRequest.query.filter_by(status='completed').count()
    urgent     = LabRequest.query.filter_by(priority='urgent',status='pending').count()
    stat_req   = LabRequest.query.filter_by(priority='stat',status='pending').count()
    recent     = LabRequest.query.order_by(LabRequest.created_at.desc()).limit(10).all()
    from modules.ai_engine import compute_risk_score
    my_risk = compute_risk_score(current_user)
    log_act('view_lab_dashboard','laboratory')
    return render_template('laboratory/dashboard.html',
        pending=pending, in_progress=in_progress, completed=completed,
        urgent=urgent, stat_req=stat_req, recent=recent, my_risk=my_risk)

@laboratory_bp.route('/requests')
@login_required
@lab_required
def request_list():
    e = escalate()
    if e: return e
    status   = request.args.get('status','pending')
    priority = request.args.get('priority','')
    page     = request.args.get('page',1,type=int)
    q = LabRequest.query
    if status:   q = q.filter_by(status=status)
    if priority: q = q.filter_by(priority=priority)
    requests = q.order_by(LabRequest.created_at.desc()).paginate(page=page,per_page=20)
    log_act('view_lab_requests','lab_request')
    return render_template('laboratory/requests.html', requests=requests, status=status, priority=priority,
                           categories=list(TEST_CATEGORIES.keys()))

@laboratory_bp.route('/requests/new', methods=['GET','POST'])
@login_required
def new_request():
    if current_user.role not in ('doctor','admin','nurse'): abort(403)
    e = escalate()
    if e: return e
    patients = Patient.query.order_by(Patient.full_name).all()
    if request.method == 'POST':
        pid      = int(request.form.get('patient_id'))
        tests    = request.form.getlist('tests')
        priority = request.form.get('priority','routine')
        category = request.form.get('test_category','General')
        notes    = request.form.get('clinical_notes','').strip()
        specimen = request.form.get('specimen_type','Blood')
        for test in tests:
            if not test.strip(): continue
            rno = f'LAB-{datetime.utcnow().year}-{LabRequest.query.count()+1:05d}'
            db.session.add(LabRequest(request_no=rno, patient_id=pid,
                requested_by=current_user.id, test_type=test,
                test_category=category, priority=priority,
                clinical_notes=notes, specimen_type=specimen, status='pending'))
        db.session.commit()
        log_act('new_lab_request','lab_request',details=f'{len(tests)} tests ordered')
        flash(f'{len(tests)} lab test(s) requested successfully.','success')
        return redirect(url_for('laboratory.request_list'))
    return render_template('laboratory/new_request.html', patients=patients,
                           test_categories=TEST_CATEGORIES)

@laboratory_bp.route('/requests/<int:rid>')
@login_required
@lab_required
def view_request(rid):
    e = escalate()
    if e: return e
    req = LabRequest.query.get_or_404(rid)
    log_act('view_lab_request','lab_request',rid)
    return render_template('laboratory/view_request.html', req=req)

@laboratory_bp.route('/requests/<int:rid>/process', methods=['POST'])
@login_required
@lab_tech_only
def process_request(rid):
    req = LabRequest.query.get_or_404(rid)
    req.status       = 'in_progress'
    req.processed_by = current_user.id
    db.session.commit()
    log_act('process_lab_request','lab_request',rid)
    flash(f'Lab request {req.request_no} marked as In Progress.','info')
    return redirect(url_for('laboratory.view_request',rid=rid))

@laboratory_bp.route('/requests/<int:rid>/result', methods=['GET','POST'])
@login_required
@lab_tech_only
def enter_result(rid):
    e = escalate()
    if e: return e
    req = LabRequest.query.get_or_404(rid)
    if request.method == 'POST':
        result_text   = request.form.get('result_data','').strip()
        ref_range     = request.form.get('reference_range','').strip()
        interpretation= request.form.get('interpretation','normal')
        comments      = request.form.get('comments','').strip()
        if req.result:
            req.result.result_data=result_text; req.result.reference_range=ref_range
            req.result.interpretation=interpretation; req.result.comments=comments
            req.result.verified_by=current_user.id
        else:
            db.session.add(LabResult(request_id=req.id, result_data=result_text,
                reference_range=ref_range, interpretation=interpretation,
                comments=comments, verified_by=current_user.id))
        req.status       = 'completed'
        req.completed_at = datetime.utcnow()
        req.processed_by = current_user.id
        db.session.commit()
        log_act('enter_lab_result','lab_request',rid,details=f'Result for {req.request_no}')
        flash(f'Result for {req.request_no} saved successfully.','success')
        return redirect(url_for('laboratory.request_list',status='completed'))
    return render_template('laboratory/enter_result.html', req=req)

@laboratory_bp.route('/results')
@login_required
@lab_required
def result_list():
    e = escalate()
    if e: return e
    page = request.args.get('page',1,type=int)
    interp = request.args.get('interp','')
    q = LabResult.query
    if interp: q = q.join(LabRequest).filter(LabResult.interpretation==interp)
    results = q.order_by(LabResult.created_at.desc()).paginate(page=page,per_page=20)
    log_act('view_lab_results','lab_result')
    return render_template('laboratory/results.html', results=results, interp=interp)


@laboratory_bp.route('/requests/<int:rid>/print')
@login_required
@lab_required
def print_result(rid):
    from datetime import datetime
    req = LabRequest.query.get_or_404(rid)
    return render_template('laboratory/print_result.html', req=req, now=datetime.utcnow())
