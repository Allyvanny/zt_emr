"""
Patient Portal — Zero Trust EMR
Patient dashboard, messaging with doctors, appointment requests.
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from models.patient_portal import PatientAccount, Message, AppointmentRequest
from models.user import User
from models.patient import Patient, MedicalRecord
from models.laboratory import LabRequest, LabResult
from models.pharmacy import Prescription
from extensions import db
from datetime import datetime
from functools import wraps

patient_portal_bp = Blueprint('patient_portal', __name__)

def patient_required(f):
    """Ensure only PatientAccount users access patient portal."""
    @wraps(f)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('patient_auth.login'))
        if not isinstance(current_user, PatientAccount):
            flash('This area is for patients only.', 'danger')
            return redirect(url_for('patient_auth.login'))
        return f(*args, **kwargs)
    return wrapped


# ── Dashboard ─────────────────────────────────────────────────────────────────
@patient_portal_bp.route('/patient/dashboard')
@patient_required
def dashboard():
    # Unread messages
    unread = Message.query.filter_by(
        receiver_patient_id=current_user.id,
        is_read=False
    ).count()

    # Recent messages
    recent_msgs = Message.query.filter_by(
        receiver_patient_id=current_user.id
    ).order_by(Message.created_at.desc()).limit(5).all()

    # Appointment requests
    my_requests = AppointmentRequest.query.filter_by(
        patient_account_id=current_user.id
    ).order_by(AppointmentRequest.created_at.desc()).limit(5).all()

    # Medical records (if linked to patient)
    records = []
    prescriptions = []
    lab_results = []
    if current_user.patient_id:
        records = MedicalRecord.query.filter_by(
            patient_id=current_user.patient_id
        ).order_by(MedicalRecord.visit_date.desc()).limit(5).all()

        prescriptions = Prescription.query.filter_by(
            patient_id=current_user.patient_id
        ).order_by(Prescription.created_at.desc()).limit(5).all()

        lab_reqs = LabRequest.query.filter_by(
            patient_id=current_user.patient_id,
            status='completed'
        ).order_by(LabRequest.created_at.desc()).limit(5).all()
        lab_results = [r for r in lab_reqs if r.result]

    # Assigned doctor
    doctor = current_user.assigned_doctor

    # Stats
    total_messages  = Message.query.filter_by(receiver_patient_id=current_user.id).count()
    total_requests  = AppointmentRequest.query.filter_by(patient_account_id=current_user.id).count()
    pending_requests= AppointmentRequest.query.filter_by(
        patient_account_id=current_user.id, status='pending').count()

    return render_template('patient_portal/dashboard.html',
        unread=unread, recent_msgs=recent_msgs,
        my_requests=my_requests, records=records,
        prescriptions=prescriptions, lab_results=lab_results,
        doctor=doctor, total_messages=total_messages,
        total_requests=total_requests, pending_requests=pending_requests)


# ── Messages ──────────────────────────────────────────────────────────────────
@patient_portal_bp.route('/patient/messages')
@patient_required
def messages():
    inbox = Message.query.filter_by(
        receiver_patient_id=current_user.id
    ).order_by(Message.created_at.desc()).all()

    sent = Message.query.filter_by(
        sender_patient_id=current_user.id
    ).order_by(Message.created_at.desc()).all()

    # Mark all as read
    for msg in inbox:
        if not msg.is_read:
            msg.is_read = True
            msg.read_at = datetime.utcnow()
    db.session.commit()

    doctors = User.query.filter_by(role='doctor', is_active=True).all()
    nurses  = User.query.filter(User.role.in_(['nurse','admin']), User.is_active==True).all()
    staff   = doctors + nurses

    return render_template('patient_portal/messages.html',
        inbox=inbox, sent=sent, staff=staff)


@patient_portal_bp.route('/patient/messages/send', methods=['GET', 'POST'])
@patient_required
def send_message():
    doctors = User.query.filter_by(role='doctor', is_active=True).all()
    nurses  = User.query.filter(User.role.in_(['nurse','admin']), User.is_active==True).all()
    staff   = doctors + nurses
    reply_to = request.args.get('reply_to', type=int)
    parent_msg = Message.query.get(reply_to) if reply_to else None

    if request.method == 'POST':
        receiver_id  = request.form.get('receiver_id', type=int)
        subject      = request.form.get('subject', '').strip()
        body         = request.form.get('body', '').strip()
        msg_type     = request.form.get('message_type', 'general')
        reply_to_id  = request.form.get('reply_to_id', type=int)

        if not all([receiver_id, subject, body]):
            flash('Please fill in all required fields.', 'danger')
            return render_template('patient_portal/send_message.html',
                                   staff=staff, parent_msg=parent_msg)

        msg = Message(
            subject=subject, body=body, message_type=msg_type,
            sender_patient_id=current_user.id,
            receiver_staff_id=receiver_id,
            reply_to_id=reply_to_id
        )
        db.session.add(msg)
        db.session.commit()
        flash('Message sent successfully!', 'success')
        return redirect(url_for('patient_portal.messages'))

    return render_template('patient_portal/send_message.html',
                           staff=staff, parent_msg=parent_msg)


@patient_portal_bp.route('/patient/messages/<int:msg_id>')
@patient_required
def view_message(msg_id):
    msg = Message.query.get_or_404(msg_id)
    if msg.receiver_patient_id != current_user.id and msg.sender_patient_id != current_user.id:
        abort(403)
    if not msg.is_read and msg.receiver_patient_id == current_user.id:
        msg.is_read = True; msg.read_at = datetime.utcnow()
        db.session.commit()
    return render_template('patient_portal/view_message.html', msg=msg)


# ── Appointment Requests ──────────────────────────────────────────────────────
@patient_portal_bp.route('/patient/appointments')
@patient_required
def appointment_requests():
    requests = AppointmentRequest.query.filter_by(
        patient_account_id=current_user.id
    ).order_by(AppointmentRequest.created_at.desc()).all()
    doctors = User.query.filter_by(role='doctor', is_active=True).all()
    return render_template('patient_portal/appointments.html',
                           requests=requests, doctors=doctors)


@patient_portal_bp.route('/patient/appointments/request', methods=['GET', 'POST'])
@patient_required
def request_appointment():
    doctors = User.query.filter_by(role='doctor', is_active=True).all()

    if request.method == 'POST':
        doctor_id   = request.form.get('preferred_doctor_id', type=int)
        pref_date_s = request.form.get('preferred_date', '').strip()
        pref_date2_s= request.form.get('preferred_date_2', '').strip()
        reason      = request.form.get('reason', '').strip()
        urgency     = request.form.get('urgency', 'routine')

        if not reason:
            flash('Please describe the reason for your appointment.', 'danger')
            return render_template('patient_portal/request_appointment.html', doctors=doctors)

        pref_date = pref_date2 = None
        try:
            if pref_date_s:  pref_date  = datetime.strptime(pref_date_s,  '%Y-%m-%dT%H:%M')
            if pref_date2_s: pref_date2 = datetime.strptime(pref_date2_s, '%Y-%m-%dT%H:%M')
        except: pass

        req_no = f'REQ-{datetime.utcnow().year}-{AppointmentRequest.query.count()+1:05d}'
        appt_req = AppointmentRequest(
            request_no=req_no,
            patient_account_id=current_user.id,
            preferred_doctor_id=doctor_id,
            preferred_date=pref_date,
            preferred_date_2=pref_date2,
            reason=reason, urgency=urgency
        )
        db.session.add(appt_req)

        # Also send a message to the doctor
        if doctor_id:
            auto_msg = Message(
                subject=f'Appointment Request — {urgency.upper()}',
                body=f'Patient {current_user.full_name} has requested an appointment.\n\nReason: {reason}\n\nPreferred date: {pref_date_s or "Flexible"}\nUrgency: {urgency}',
                message_type='appointment_request',
                sender_patient_id=current_user.id,
                receiver_staff_id=doctor_id
            )
            db.session.add(auto_msg)

        db.session.commit()
        flash(f'Appointment request {req_no} submitted! Your doctor will respond soon.', 'success')
        return redirect(url_for('patient_portal.appointment_requests'))

    return render_template('patient_portal/request_appointment.html', doctors=doctors)


# ── My Health Records ─────────────────────────────────────────────────────────
@patient_portal_bp.route('/patient/my-health')
@patient_required
def my_health():
    if not current_user.patient_id:
        return render_template('patient_portal/my_health.html',
                               records=[], prescriptions=[], lab_results=[],
                               not_linked=True)

    records = MedicalRecord.query.filter_by(
        patient_id=current_user.patient_id
    ).order_by(MedicalRecord.visit_date.desc()).all()

    prescriptions = Prescription.query.filter_by(
        patient_id=current_user.patient_id
    ).order_by(Prescription.created_at.desc()).all()

    lab_reqs = LabRequest.query.filter_by(
        patient_id=current_user.patient_id
    ).order_by(LabRequest.created_at.desc()).all()

    return render_template('patient_portal/my_health.html',
        records=records, prescriptions=prescriptions,
        lab_results=lab_reqs, not_linked=False)


# ── Profile ───────────────────────────────────────────────────────────────────
@patient_portal_bp.route('/patient/profile', methods=['GET', 'POST'])
@patient_required
def profile():
    if request.method == 'POST':
        current_user.phone   = request.form.get('phone', '').strip()
        current_user.address = request.form.get('address', '').strip()
        current_user.emergency_contact = request.form.get('emergency_contact', '').strip()
        db.session.commit()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('patient_portal.profile'))
    return render_template('patient_portal/profile.html')


# ── Staff: Reply to patient messages ─────────────────────────────────────────
@patient_portal_bp.route('/staff/patient-messages')
@login_required
def staff_messages():
    """Staff view of all patient messages — accessible to doctors/nurses/admin."""
    if not hasattr(current_user, 'role'):
        abort(403)
    if current_user.role not in ('doctor','nurse','admin'):
        abort(403)

    # Messages received by this staff member from patients
    received = Message.query.filter_by(
        receiver_staff_id=current_user.id
    ).order_by(Message.created_at.desc()).all()

    unread_count = sum(1 for m in received if not m.is_read)
    return render_template('patient_portal/staff_messages.html',
                           received=received, unread_count=unread_count)


@patient_portal_bp.route('/staff/patient-messages/<int:msg_id>/reply', methods=['POST'])
@login_required
def staff_reply(msg_id):
    if not hasattr(current_user, 'role') or current_user.role not in ('doctor','nurse','admin'):
        abort(403)
    parent = Message.query.get_or_404(msg_id)
    body   = request.form.get('body', '').strip()
    if not body:
        flash('Reply cannot be empty.', 'danger')
        return redirect(url_for('patient_portal.staff_messages'))

    reply = Message(
        subject=f'Re: {parent.subject}',
        body=body, message_type=parent.message_type,
        sender_staff_id=current_user.id,
        receiver_patient_id=parent.sender_patient_id,
        reply_to_id=parent.id
    )
    parent.is_read = True; parent.read_at = datetime.utcnow()
    db.session.add(reply); db.session.commit()
    flash('Reply sent to patient.', 'success')
    return redirect(url_for('patient_portal.staff_messages'))


@patient_portal_bp.route('/staff/appointment-requests')
@login_required
def staff_appointment_requests():
    """Staff view of all patient appointment requests."""
    if not hasattr(current_user, 'role') or current_user.role not in ('doctor','nurse','admin','receptionist'):
        abort(403)
    if current_user.role == 'doctor':
        reqs = AppointmentRequest.query.filter_by(
            preferred_doctor_id=current_user.id
        ).order_by(AppointmentRequest.created_at.desc()).all()
    else:
        reqs = AppointmentRequest.query.order_by(AppointmentRequest.created_at.desc()).all()

    return render_template('patient_portal/staff_appt_requests.html', reqs=reqs)


@patient_portal_bp.route('/staff/appointment-requests/<int:req_id>/review', methods=['POST'])
@login_required
def review_appointment_request(req_id):
    if not hasattr(current_user, 'role') or current_user.role not in ('doctor','admin','receptionist'):
        abort(403)
    req    = AppointmentRequest.query.get_or_404(req_id)
    action = request.form.get('action', '')
    notes  = request.form.get('response_notes', '').strip()

    req.status        = 'approved' if action == 'approve' else 'rejected'
    req.response_notes= notes
    req.reviewed_by   = current_user.id
    req.reviewed_at   = datetime.utcnow()
    db.session.commit()

    # Notify patient via message
    notif = Message(
        subject=f'Your appointment request has been {req.status}',
        body=f'Dear {req.patient_account.full_name},\n\nYour appointment request ({req.request_no}) has been {req.status}.\n\n{"Reason: " + notes if notes else ""}',
        message_type='appointment_request',
        sender_staff_id=current_user.id,
        receiver_patient_id=req.patient_account_id
    )
    db.session.add(notif); db.session.commit()
    flash(f'Request {req.request_no} has been {req.status}. Patient notified.', 'success')
    return redirect(url_for('patient_portal.staff_appointment_requests'))
