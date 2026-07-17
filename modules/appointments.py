"""
Appointments Module — Zero Trust EMR
Doctors: view, approve, reject, complete appointments
Receptionists: book appointments for patients
Patients registered by doctors directly from their dashboard
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, session
from flask_login import login_required, current_user
from models.appointment import Appointment
from models.patient import Patient
from models.user import User
from models.logs import ActivityLog
from extensions import db
from datetime import datetime
from functools import wraps

appointments_bp = Blueprint('appointments', __name__)

ALLOWED_ROLES = ['doctor', 'nurse', 'receptionist', 'admin']

def log_act(action, resource=None, rid=None, details=None):
    db.session.add(ActivityLog(
        user_id=current_user.id, action=action, resource=resource,
        resource_id=rid, ip_address=request.remote_addr,
        user_agent=request.user_agent.string[:256],
        session_id=session.get('_id', ''), details=details
    ))
    db.session.commit()

def escalate():
    from modules.ai_engine import check_session_risk
    if check_session_risk(current_user):
        return redirect(url_for('auth.session_mfa'))
    return None

# ── Doctor Dashboard ──────────────────────────────────────────────────────────
@appointments_bp.route('/doctor/dashboard')
@login_required
def doctor_dashboard():
    if current_user.role not in ('doctor', 'admin'):
        abort(403)
    e = escalate()
    if e: return e

    from models.patient import Patient, MedicalRecord
    from models.pharmacy import Prescription
    from models.laboratory import LabRequest

    # Today's appointments
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_end   = datetime.utcnow().replace(hour=23, minute=59, second=59)

    today_appts = Appointment.query.filter(
        Appointment.doctor_id == current_user.id,
        Appointment.appointment_date >= today_start,
        Appointment.appointment_date <= today_end,
        Appointment.status.in_(['approved', 'pending'])
    ).order_by(Appointment.appointment_date).all()

    # Pending approvals
    pending_appts = Appointment.query.filter_by(
        doctor_id=current_user.id, status='pending'
    ).order_by(Appointment.appointment_date).all()

    # Recent patients seen by this doctor
    recent_records = MedicalRecord.query.filter_by(
        doctor_id=current_user.id
    ).order_by(MedicalRecord.visit_date.desc()).limit(8).all()

    # Stats
    total_patients  = MedicalRecord.query.filter_by(doctor_id=current_user.id).with_entities(
        MedicalRecord.patient_id).distinct().count()
    total_appts     = Appointment.query.filter_by(doctor_id=current_user.id).count()
    pending_count   = Appointment.query.filter_by(doctor_id=current_user.id, status='pending').count()
    pending_rx      = Prescription.query.filter_by(prescribed_by=current_user.id, status='pending').count()
    pending_labs    = LabRequest.query.filter_by(requested_by=current_user.id, status='pending').count()

    from modules.ai_engine import compute_risk_score
    my_risk = compute_risk_score(current_user)

    log_act('view_doctor_dashboard', 'dashboard')

    return render_template('appointments/doctor_dashboard.html',
        today_appts=today_appts, pending_appts=pending_appts,
        recent_records=recent_records,
        total_patients=total_patients, total_appts=total_appts,
        pending_count=pending_count, pending_rx=pending_rx,
        pending_labs=pending_labs, my_risk=my_risk)


# ── List Appointments ─────────────────────────────────────────────────────────
@appointments_bp.route('/appointments')
@login_required
def appointment_list():
    if current_user.role not in ALLOWED_ROLES:
        abort(403)
    e = escalate()
    if e: return e

    status   = request.args.get('status', 'all')
    page     = request.args.get('page', 1, type=int)

    q = Appointment.query
    if current_user.role == 'doctor':
        q = q.filter_by(doctor_id=current_user.id)
    if status != 'all':
        q = q.filter_by(status=status)

    appointments = q.order_by(Appointment.appointment_date.desc()).paginate(page=page, per_page=20)
    doctors      = User.query.filter_by(role='doctor').all()

    log_act('view_appointments', 'appointment')
    return render_template('appointments/list.html',
        appointments=appointments, status=status, doctors=doctors)


# ── Book Appointment ──────────────────────────────────────────────────────────
@appointments_bp.route('/appointments/book', methods=['GET', 'POST'])
@login_required
def book_appointment():
    if current_user.role not in ('receptionist', 'doctor', 'nurse', 'admin'):
        abort(403)
    e = escalate()
    if e: return e

    patients = Patient.query.order_by(Patient.full_name).all()
    doctors  = User.query.filter_by(role='doctor', is_active=True).all()

    if request.method == 'POST':
        patient_id   = request.form.get('patient_id', type=int)
        doctor_id    = request.form.get('doctor_id', type=int)
        appt_date_s  = request.form.get('appointment_date', '').strip()
        reason       = request.form.get('reason', '').strip()
        notes        = request.form.get('notes', '').strip()

        if not all([patient_id, doctor_id, appt_date_s]):
            flash('Patient, doctor and appointment date are required.', 'danger')
            return render_template('appointments/book.html', patients=patients, doctors=doctors)

        try:
            appt_date = datetime.strptime(appt_date_s, '%Y-%m-%dT%H:%M')
        except ValueError:
            flash('Invalid date/time format.', 'danger')
            return render_template('appointments/book.html', patients=patients, doctors=doctors)

        # Generate appointment number
        appt_no = f'APT-{datetime.utcnow().year}-{Appointment.query.count()+1:05d}'

        appt = Appointment(
            appointment_no   = appt_no,
            patient_id       = patient_id,
            doctor_id        = doctor_id,
            requested_by     = current_user.id,
            appointment_date = appt_date,
            reason           = reason,
            notes            = notes,
            status           = 'approved' if current_user.role == 'doctor' else 'pending'
        )
        if current_user.role == 'doctor':
            appt.approved_at = datetime.utcnow()

        db.session.add(appt)
        db.session.commit()

        log_act('book_appointment', 'appointment', appt.id,
                details=f'Booked {appt_no} for patient {patient_id}')
        flash(f'Appointment {appt_no} booked successfully.', 'success')
        return redirect(url_for('appointments.appointment_list'))

    return render_template('appointments/book.html', patients=patients, doctors=doctors)


# ── View single appointment ───────────────────────────────────────────────────
@appointments_bp.route('/appointments/<int:appt_id>')
@login_required
def view_appointment(appt_id):
    if current_user.role not in ALLOWED_ROLES:
        abort(403)
    appt = Appointment.query.get_or_404(appt_id)
    log_act('view_appointment', 'appointment', appt_id)
    return render_template('appointments/view.html', appt=appt)


# ── Approve Appointment ───────────────────────────────────────────────────────
@appointments_bp.route('/appointments/<int:appt_id>/approve', methods=['POST'])
@login_required
def approve_appointment(appt_id):
    if current_user.role not in ('doctor', 'admin'):
        abort(403)
    appt = Appointment.query.get_or_404(appt_id)

    if appt.doctor_id != current_user.id and current_user.role != 'admin':
        flash('You can only approve your own appointments.', 'danger')
        return redirect(url_for('appointments.appointment_list'))

    appt.status      = 'approved'
    appt.approved_at = datetime.utcnow()
    notes = request.form.get('notes', '').strip()
    if notes:
        appt.notes = notes
    db.session.commit()

    log_act('approve_appointment', 'appointment', appt_id,
            details=f'Approved {appt.appointment_no}')
    flash(f'Appointment {appt.appointment_no} approved successfully.', 'success')
    return redirect(url_for('appointments.doctor_dashboard'))


# ── Reject Appointment ────────────────────────────────────────────────────────
@appointments_bp.route('/appointments/<int:appt_id>/reject', methods=['POST'])
@login_required
def reject_appointment(appt_id):
    if current_user.role not in ('doctor', 'admin'):
        abort(403)
    appt = Appointment.query.get_or_404(appt_id)

    if appt.doctor_id != current_user.id and current_user.role != 'admin':
        flash('You can only reject your own appointments.', 'danger')
        return redirect(url_for('appointments.appointment_list'))

    reason = request.form.get('reject_reason', '').strip()
    appt.status = 'rejected'
    appt.notes  = f'Rejected: {reason}' if reason else 'Rejected by doctor'
    db.session.commit()

    log_act('reject_appointment', 'appointment', appt_id,
            details=f'Rejected {appt.appointment_no}: {reason}')
    flash(f'Appointment {appt.appointment_no} rejected.', 'info')
    return redirect(url_for('appointments.doctor_dashboard'))


# ── Complete Appointment ──────────────────────────────────────────────────────
@appointments_bp.route('/appointments/<int:appt_id>/complete', methods=['POST'])
@login_required
def complete_appointment(appt_id):
    if current_user.role not in ('doctor', 'admin'):
        abort(403)
    appt = Appointment.query.get_or_404(appt_id)
    appt.status = 'completed'
    db.session.commit()
    log_act('complete_appointment', 'appointment', appt_id)
    flash(f'Appointment {appt.appointment_no} marked as completed.', 'success')
    return redirect(url_for('appointments.doctor_dashboard'))


# ── Cancel Appointment ────────────────────────────────────────────────────────
@appointments_bp.route('/appointments/<int:appt_id>/cancel', methods=['POST'])
@login_required
def cancel_appointment(appt_id):
    if current_user.role not in ALLOWED_ROLES:
        abort(403)
    appt = Appointment.query.get_or_404(appt_id)
    appt.status = 'cancelled'
    db.session.commit()
    log_act('cancel_appointment', 'appointment', appt_id)
    flash(f'Appointment {appt.appointment_no} cancelled.', 'info')
    return redirect(url_for('appointments.appointment_list'))
