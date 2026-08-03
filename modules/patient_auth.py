"""
Patient Portal Auth — Zero Trust EMR
No MFA for patients — simple username + password only.
Separate session from staff login.
"""
from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from flask_login import login_user, logout_user, current_user, login_required
from models.patient_portal import PatientAccount
from extensions import db
from datetime import datetime, date
import secrets

patient_auth_bp = Blueprint('patient_auth', __name__)


@patient_auth_bp.route('/patient/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username  = request.form.get('username', '').strip().lower()
        password  = request.form.get('password', '').strip()
        confirm   = request.form.get('confirm_password', '').strip()
        full_name = request.form.get('full_name', '').strip()
        email     = request.form.get('email', '').strip().lower()
        phone     = request.form.get('phone', '').strip()
        dob_s     = request.form.get('date_of_birth', '')
        gender    = request.form.get('gender', '')
        address   = request.form.get('address', '').strip()
        blood     = request.form.get('blood_group', '')
        emergency = request.form.get('emergency_contact', '').strip()

        # Validation
        if not all([username, password, full_name, email]):
            flash('Username, password, full name and email are required.', 'danger')
            return render_template('auth_patient/register.html')
        if password != confirm:
            flash('Passwords do not match.', 'danger')
            return render_template('auth_patient/register.html')
        if len(password) < 6:
            flash('Password must be at least 6 characters.', 'danger')
            return render_template('auth_patient/register.html')
        if PatientAccount.query.filter_by(username=username).first():
            flash('Username already taken. Please choose another.', 'danger')
            return render_template('auth_patient/register.html')
        if PatientAccount.query.filter_by(email=email).first():
            flash('Email already registered.', 'danger')
            return render_template('auth_patient/register.html')

        dob = None
        if dob_s:
            try: dob = datetime.strptime(dob_s, '%Y-%m-%d').date()
            except: pass

        # Try to link to existing patient record
        from models.patient import Patient
        existing_patient = Patient.query.filter(
            Patient.full_name.ilike(f'%{full_name}%')
        ).first()

        # Get first available doctor as default
        from models.user import User
        default_doctor = User.query.filter_by(role='doctor', is_active=True).first()

        account = PatientAccount(
            username=username, full_name=full_name, email=email,
            phone=phone, date_of_birth=dob, gender=gender,
            address=address, blood_group=blood,
            emergency_contact=emergency,
            patient_id=existing_patient.id if existing_patient else None,
            assigned_doctor_id=default_doctor.id if default_doctor else None
        )
        account.set_password(password)
        db.session.add(account)
        db.session.commit()

        flash('Account created successfully! You can now log in.', 'success')
        return redirect(url_for('patient_auth.login'))

    return render_template('auth_patient/register.html')


@patient_auth_bp.route('/patient/login', methods=['GET', 'POST'])
def login():
    # Redirect if already logged in as patient
    if current_user.is_authenticated:
        if hasattr(current_user, 'patient_id') or isinstance(current_user, PatientAccount):
            return redirect(url_for('patient_portal.dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        account = PatientAccount.query.filter_by(username=username, is_active=True).first()

        if not account or not account.check_password(password):
            flash('Invalid username or password.', 'danger')
            return render_template('auth_patient/login.html')

        # ── Device trust check ──────────────────────────────────────────
        # An unrecognized device is NOT hard-blocked — it must verify via OTP
        # email before the login completes. A known device logs in directly.
        from modules.auth import device_is_trusted
        incoming_fp = (request.form.get('device_fp') or '').strip()[:64]
        known_fp    = account.last_fingerprint or ''
        # First-ever device, or a device not approved within the last 30 days,
        # must be approved via OTP before it can log in / be remembered.
        new_device  = bool(incoming_fp) and (not known_fp or not device_is_trusted(account, incoming_fp))
        if new_device:
            from modules.auth import gen_otp, send_otp_email, mask_email, otp_destination
            from datetime import timedelta
            otp = gen_otp()
            account.otp_code = otp; account.otp_expiry = datetime.utcnow()+timedelta(minutes=5)
            db.session.commit()
            sent, err = send_otp_email(account, otp)
            session['pending_patient_id'] = account.id
            session['pending_new_device'] = incoming_fp
            if sent:
                em = mask_email(otp_destination(account))
                flash(f'New device detected — a verification code has been sent to {em} to approve it.', 'info')
            else:
                flash(f'New device detected — verification required. DEMO CODE: {otp} (Email error: {err})', 'warning')
            return redirect(url_for('patient_auth.verify_device'))

        # Simple login — no MFA for known devices
        token = secrets.token_hex(32)
        account.session_token = token
        session['zt_session_token'] = token
        account.last_ip = request.remote_addr
        from modules.auth import parse_device, get_location
        account.last_device = parse_device(request.user_agent.string)
        account.last_fingerprint = incoming_fp
        # Trusted (known) device — refresh the 30-day trust window on each login
        if incoming_fp and incoming_fp == account.last_fingerprint:
            account.last_fingerprint_at = datetime.utcnow()
        loc = get_location(request.remote_addr)
        if loc not in ('Unknown', 'Localhost') or not account.last_location:
            account.last_location = loc
        login_user(account, remember=True)
        account.last_login = datetime.utcnow()
        db.session.commit()

        flash(f'Welcome back, {account.full_name}!', 'success')
        return redirect(url_for('patient_portal.dashboard'))

    return render_template('auth_patient/login.html')


@patient_auth_bp.route('/patient/verify-device', methods=['GET', 'POST'])
def verify_device():
    """Patient verifies a new device via OTP email before enrollment."""
    from datetime import timedelta
    pid = session.get('pending_patient_id')
    if not pid:
        return redirect(url_for('patient_auth.login'))
    account = PatientAccount.query.get(pid)
    if not account:
        session.pop('pending_patient_id', None)
        return redirect(url_for('patient_auth.login'))
    pending_fp = session.get('pending_new_device', '')
    if request.method == 'POST':
        entered = request.form.get('otp', '').strip()
        if account.otp_expiry and datetime.utcnow() > account.otp_expiry:
            flash('Code expired. Please log in again.', 'danger')
            [session.pop(k, None) for k in ['pending_patient_id', 'pending_new_device']]
            return redirect(url_for('patient_auth.login'))
        if entered == account.otp_code:
            remember = request.form.get('remember_device') != 'off'
            if remember:
                account.last_fingerprint = pending_fp
                from modules.auth import DEVICE_TRUST_DAYS
                account.last_fingerprint_at = datetime.utcnow()
            token = secrets.token_hex(32)
            account.session_token = token
            session['zt_session_token'] = token
            account.last_ip = request.remote_addr
            from modules.auth import parse_device, get_location
            account.last_device = parse_device(request.user_agent.string)
            loc = get_location(request.remote_addr)
            if loc not in ('Unknown', 'Localhost') or not account.last_location:
                account.last_location = loc
            login_user(account, remember=True)
            account.last_login = datetime.utcnow()
            db.session.commit()
            [session.pop(k, None) for k in ['pending_patient_id', 'pending_new_device']]
            flash(f'Device approved. Welcome back, {account.full_name}!', 'success')
            return redirect(url_for('patient_portal.dashboard'))
        flash('Invalid code. Try again.', 'danger')
    from modules.auth import mask_email, otp_destination
    masked = mask_email(otp_destination(account))
    return render_template('auth_patient/verify_device.html', masked_email=masked,
                           account=account)


@patient_auth_bp.route('/patient/resend-device-otp', methods=['POST'])
def resend_device_otp():
    from datetime import timedelta
    pid = session.get('pending_patient_id')
    if not pid:
        return redirect(url_for('patient_auth.login'))
    account = PatientAccount.query.get(pid)
    if not account:
        return redirect(url_for('patient_auth.login'))
    from modules.auth import gen_otp, send_otp_email, mask_email, otp_destination
    otp = gen_otp()
    account.otp_code = otp; account.otp_expiry = datetime.utcnow()+timedelta(minutes=5)
    db.session.commit()
    sent, err = send_otp_email(account, otp)
    if sent:
        flash(f'A new verification code has been sent to {mask_email(otp_destination(account))}.', 'info')
    else:
        flash(f'Email failed: {err}. Contact support.', 'danger')
    return redirect(url_for('patient_auth.verify_device'))

@patient_auth_bp.route('/patient/logout')
def logout():
    reason = request.args.get('reason', '')
    logout_user()
    if reason == 'idle':
        flash('Signed out after 5 minutes of inactivity. Please sign in again.', 'warning')
    else:
        flash('You have been signed out.', 'info')
    return redirect(url_for('patient_auth.login'))


@patient_auth_bp.route('/patient/language/<lang>')
def set_language(lang):
    """Switch patient-portal language (English / Swahili). Works pre-login too."""
    from modules.i18n import SUPPORTED_LANGS
    if lang in SUPPORTED_LANGS:
        session['lang'] = lang
    return redirect(request.referrer or url_for('patient_auth.login'))

# ══════════════════════════════════════════════════════════════════════════════
# Route 1: Create portal account for an existing patient (staff side)
# URL: /patient/create-account/<patient_db_id>
# ══════════════════════════════════════════════════════════════════════════════
@patient_auth_bp.route('/patient/create-account/<int:patient_db_id>', methods=['GET','POST'])
@login_required
def create_portal_account(patient_db_id):
    """
    Staff (receptionist/admin/doctor/nurse) creates a portal account
    for a patient who was already registered in the system.
    """
    from flask_login import current_user
    from models.patient import Patient
    from models.user import User

    # Only staff can access this
    if not hasattr(current_user, 'role'):
        flash('Access denied.', 'danger')
        return redirect(url_for('auth.login'))

    if current_user.role not in ('receptionist', 'admin', 'doctor', 'nurse'):
        flash('You do not have permission to create patient portal accounts.', 'danger')
        return redirect(url_for('patients.patient_list'))

    patient = Patient.query.get_or_404(patient_db_id)

    # Check if portal account already exists for this patient
    existing = PatientAccount.query.filter_by(patient_id=patient_db_id).first()
    if existing:
        flash(f'Portal account already exists for {patient.full_name}. Username: {existing.username}', 'info')
        return redirect(url_for('patients.view_patient', patient_id=patient_db_id))

    # Auto-generate username from patient name
    import re
    base_username = re.sub(r'[^a-z0-9]', '_', patient.full_name.lower().strip())[:20]
    base_username = re.sub(r'_+', '_', base_username).strip('_')

    # Ensure username is unique
    username = base_username
    counter  = 1
    while PatientAccount.query.filter_by(username=username).first():
        username = f'{base_username}_{counter}'
        counter += 1

    # Auto-generate a simple password: first name + last 4 digits of patient_id
    first_name = patient.full_name.split()[0].lower()
    pid_digits  = ''.join(filter(str.isdigit, patient.patient_id))[-4:]
    default_password = f'{first_name}{pid_digits}'

    if request.method == 'POST':
        username         = request.form.get('username', username).strip().lower()
        password         = request.form.get('password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()
        email            = request.form.get('email', '').strip().lower()

        # Validation
        if not username or not password or not email:
            flash('Username, password and email are required.', 'danger')
            return render_template('auth_patient/create_portal_account.html',
                                   patient=patient, username=username,
                                   default_password=default_password)

        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return render_template('auth_patient/create_portal_account.html',
                                   patient=patient, username=username,
                                   default_password=default_password)

        if len(password) < 6:
            flash('Password must be at least 6 characters.', 'danger')
            return render_template('auth_patient/create_portal_account.html',
                                   patient=patient, username=username,
                                   default_password=default_password)

        if PatientAccount.query.filter_by(username=username).first():
            flash(f'Username "{username}" is already taken. Try another.', 'danger')
            return render_template('auth_patient/create_portal_account.html',
                                   patient=patient, username=username,
                                   default_password=default_password)

        if email and PatientAccount.query.filter_by(email=email).first():
            flash(f'Email "{email}" is already registered.', 'danger')
            return render_template('auth_patient/create_portal_account.html',
                                   patient=patient, username=username,
                                   default_password=default_password)

        # Get assigned doctor
        default_doctor = User.query.filter_by(role='doctor', is_active=True).first()

        # Create the portal account linked to this patient
        account = PatientAccount(
            username           = username,
            full_name          = patient.full_name,
            email              = email or f'{username}@emr.local',
            phone              = patient.phone,
            date_of_birth      = patient.date_of_birth,
            gender             = patient.gender,
            address            = patient.address,
            blood_group        = patient.blood_group,
            emergency_contact  = patient.emergency_contact,
            patient_id         = patient.id,
            assigned_doctor_id = default_doctor.id if default_doctor else None,
        )
        account.set_password(password)
        db.session.add(account)

        # Log the action
        from models.logs import ActivityLog
        db.session.add(ActivityLog(
            user_id    = current_user.id,
            action     = 'create_patient_portal_account',
            resource   = 'patient_account',
            resource_id= patient.id,
            ip_address = request.remote_addr,
            details    = f'Portal account created for {patient.full_name} by {current_user.username}'
        ))
        db.session.commit()

        flash(
            f'✅ Portal account created! '
            f'Patient can log in at /patient/login with username: {username}',
            'success'
        )
        return redirect(url_for('patients.view_patient', patient_id=patient_db_id))

    return render_template('auth_patient/create_portal_account.html',
                           patient=patient,
                           username=username,
                           default_password=default_password)


# ══════════════════════════════════════════════════════════════════════════════
# Route 2: Quick reset password for a patient portal account (staff side)
# URL: /patient/reset-password/<patient_db_id>
# ══════════════════════════════════════════════════════════════════════════════
@patient_auth_bp.route('/patient/reset-password/<int:patient_db_id>', methods=['POST'])
@login_required
def reset_patient_password(patient_db_id):
    from flask_login import current_user
    if not hasattr(current_user, 'role') or current_user.role not in ('receptionist','admin','doctor','nurse'):
        flash('Access denied.', 'danger')
        return redirect(url_for('patients.patient_list'))

    account = PatientAccount.query.filter_by(patient_id=patient_db_id).first()
    if not account:
        flash('No portal account found for this patient.', 'danger')
        return redirect(url_for('patients.view_patient', patient_id=patient_db_id))

    new_password = request.form.get('new_password', '').strip()
    if len(new_password) < 6:
        flash('Password must be at least 6 characters.', 'danger')
        return redirect(url_for('patients.view_patient', patient_id=patient_db_id))

    account.set_password(new_password)
    db.session.commit()
    flash(f'Password reset successfully for {account.full_name}. New password: {new_password}', 'success')
    return redirect(url_for('patients.view_patient', patient_id=patient_db_id))