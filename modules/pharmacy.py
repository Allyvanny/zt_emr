from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, session
from flask_login import login_required, current_user
from models.pharmacy import Drug, Prescription, PrescriptionItem
from models.patient import Patient
from models.logs import ActivityLog
from extensions import db
from datetime import datetime, date
from functools import wraps

pharmacy_bp = Blueprint('pharmacy', __name__)

def pharm_required(f):
    @wraps(f)
    def w(*a,**k):
        if current_user.role not in ('pharmacist','admin'): abort(403)
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

# ── Dashboard ──────────────────────────────────────────────────────────────
@pharmacy_bp.route('/dashboard')
@login_required
@pharm_required
def dashboard():
    e = escalate()
    if e: return e
    pending   = Prescription.query.filter_by(status='pending').count()
    dispensed = Prescription.query.filter_by(status='dispensed').count()
    total_drugs = Drug.query.count()
    low_stock   = Drug.query.filter(Drug.stock_qty <= Drug.reorder_level).count()
    out_of_stock= Drug.query.filter_by(stock_qty=0).count()
    recent_rx   = Prescription.query.order_by(Prescription.created_at.desc()).limit(8).all()
    low_drugs   = Drug.query.filter(Drug.stock_qty <= Drug.reorder_level).order_by(Drug.stock_qty).limit(8).all()
    from modules.ai_engine import compute_risk_score
    my_risk = compute_risk_score(current_user)
    log_act('view_pharmacy_dashboard','pharmacy')
    return render_template('pharmacy/dashboard.html',
        pending=pending, dispensed=dispensed, total_drugs=total_drugs,
        low_stock=low_stock, out_of_stock=out_of_stock,
        recent_rx=recent_rx, low_drugs=low_drugs, my_risk=my_risk)

# ── Prescriptions ──────────────────────────────────────────────────────────
@pharmacy_bp.route('/prescriptions')
@login_required
@pharm_required
def prescription_list():
    e = escalate()
    if e: return e
    status = request.args.get('status','pending')
    page   = request.args.get('page',1,type=int)
    rxs = Prescription.query.filter_by(status=status).order_by(Prescription.created_at.desc()).paginate(page=page,per_page=20)
    log_act('view_prescriptions','prescription')
    return render_template('pharmacy/prescriptions.html', rxs=rxs, status=status)

@pharmacy_bp.route('/prescriptions/<int:rx_id>')
@login_required
@pharm_required
def view_prescription(rx_id):
    e = escalate()
    if e: return e
    rx = Prescription.query.get_or_404(rx_id)
    drugs = Drug.query.order_by(Drug.name).all()
    log_act('view_prescription','prescription',rx_id)
    return render_template('pharmacy/view_prescription.html', rx=rx, drugs=drugs)

@pharmacy_bp.route('/prescriptions/<int:rx_id>/dispense', methods=['POST'])
@login_required
@pharm_required
def dispense(rx_id):
    rx = Prescription.query.get_or_404(rx_id)
    if rx.status != 'pending':
        flash('Prescription already processed.','warning')
        return redirect(url_for('pharmacy.view_prescription',rx_id=rx_id))

    # Process items from form
    drug_ids   = request.form.getlist('drug_id')
    dosages    = request.form.getlist('dosage')
    freqs      = request.form.getlist('frequency')
    durations  = request.form.getlist('duration')
    quantities = request.form.getlist('quantity')

    errors = []
    for i, did in enumerate(drug_ids):
        if not did: continue
        drug = Drug.query.get(int(did))
        if not drug: continue
        qty = int(quantities[i]) if i < len(quantities) and quantities[i] else 1
        if drug.stock_qty < qty:
            errors.append(f'{drug.name}: insufficient stock ({drug.stock_qty} available).')
            continue
        item = PrescriptionItem(prescription_id=rx.id, drug_id=drug.id,
            dosage=dosages[i] if i<len(dosages) else '',
            frequency=freqs[i] if i<len(freqs) else '',
            duration=durations[i] if i<len(durations) else '',
            quantity=qty, dispensed_qty=qty)
        drug.stock_qty -= qty
        db.session.add(item)

    if errors:
        for err in errors: flash(err,'warning')
    else:
        rx.status       = 'dispensed'
        rx.dispensed_by = current_user.id
        rx.dispensed_at = datetime.utcnow()
        db.session.commit()
        log_act('dispense_prescription','prescription',rx_id,details=f'Dispensed RX {rx.prescription_no}')
        flash(f'Prescription {rx.prescription_no} dispensed successfully.','success')
    db.session.commit()
    return redirect(url_for('pharmacy.prescription_list'))

@pharmacy_bp.route('/prescriptions/<int:rx_id>/cancel', methods=['POST'])
@login_required
@pharm_required
def cancel_prescription(rx_id):
    rx = Prescription.query.get_or_404(rx_id)
    rx.status = 'cancelled'; db.session.commit()
    log_act('cancel_prescription','prescription',rx_id)
    flash('Prescription cancelled.','info')
    return redirect(url_for('pharmacy.prescription_list'))

# ── Drug inventory ─────────────────────────────────────────────────────────
@pharmacy_bp.route('/drugs')
@login_required
@pharm_required
def drug_list():
    e = escalate()
    if e: return e
    search = request.args.get('search','').strip()
    q = Drug.query
    if search: q = q.filter(Drug.name.ilike(f'%{search}%')|Drug.generic_name.ilike(f'%{search}%'))
    drugs = q.order_by(Drug.name).paginate(page=request.args.get('page',1,type=int),per_page=25)
    log_act('view_drugs','drug')
    return render_template('pharmacy/drugs.html', drugs=drugs, search=search)

@pharmacy_bp.route('/drugs/add', methods=['GET','POST'])
@login_required
@pharm_required
def add_drug():
    if request.method == 'POST':
        exp_s = request.form.get('expiry_date','')
        exp   = datetime.strptime(exp_s,'%Y-%m-%d').date() if exp_s else None
        drug  = Drug(name=request.form.get('name','').strip(),
                     generic_name=request.form.get('generic_name','').strip(),
                     category=request.form.get('category',''),
                     unit=request.form.get('unit','Tablets'),
                     stock_qty=int(request.form.get('stock_qty',0)),
                     reorder_level=int(request.form.get('reorder_level',50)),
                     unit_price=float(request.form.get('unit_price',0)),
                     expiry_date=exp)
        db.session.add(drug); db.session.commit()
        log_act('add_drug','drug',drug.id,details=f'Added {drug.name}')
        flash(f'Drug {drug.name} added to inventory.','success')
    return redirect(url_for('pharmacy.drug_list'))


@pharmacy_bp.route('/prescriptions/<int:rx_id>/print')
@login_required
@pharm_required
def print_prescription(rx_id):
    rx = Prescription.query.get_or_404(rx_id)
    return render_template('pharmacy/print_prescription.html', rx=rx)
    return render_template('pharmacy/add_drug.html')

@pharmacy_bp.route('/drugs/<int:did>/restock', methods=['POST'])
@login_required
@pharm_required
def restock_drug(did):
    drug = Drug.query.get_or_404(did)
    qty  = int(request.form.get('qty',0))
    if qty > 0:
        drug.stock_qty += qty; db.session.commit()
        log_act('restock_drug','drug',did,details=f'Restocked {drug.name} by {qty}')
        flash(f'{drug.name} restocked by {qty} units. New stock: {drug.stock_qty}.','success')
    return redirect(url_for('pharmacy.drug_list'))
