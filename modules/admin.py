from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from models.user import User
from models.logs import ActivityLog, RiskLog, AuthenticationLog
from extensions import db
from functools import wraps

admin_bp = Blueprint('admin', __name__)

def admin_only(f):
    @wraps(f)
    def w(*a,**k):
        if current_user.role != 'admin': abort(403)
        return f(*a,**k)
    return w

ROLES = ['doctor','nurse','receptionist','pharmacist','lab_technician','admin']
ROLE_LABELS = {'doctor':'Doctor','nurse':'Nurse','receptionist':'Receptionist',
               'pharmacist':'Pharmacist','lab_technician':'Lab Technician','admin':'Administrator'}

@admin_bp.route('/users')
@login_required
@admin_only
def user_list():
    users = User.query.order_by(User.role, User.full_name).all()
    return render_template('admin/users.html', users=users, role_labels=ROLE_LABELS)

@admin_bp.route('/users/create', methods=['GET','POST'])
@login_required
@admin_only
def create_user():
    if request.method == 'POST':
        username = request.form.get('username','').strip().lower()
        full_name= request.form.get('full_name','').strip()
        email    = request.form.get('email','').strip().lower()
        role     = request.form.get('role','nurse')
        password = request.form.get('password','').strip()
        if not all([username,full_name,email,password]):
            flash('All fields required.','danger'); return render_template('admin/create_user.html',roles=ROLES,role_labels=ROLE_LABELS)
        if User.query.filter_by(username=username).first():
            flash('Username exists.','danger'); return render_template('admin/create_user.html',roles=ROLES,role_labels=ROLE_LABELS)
        if User.query.filter_by(email=email).first():
            flash('Email already registered.','danger'); return render_template('admin/create_user.html',roles=ROLES,role_labels=ROLE_LABELS)
        if len(password)<8:
            flash('Password min 8 chars.','danger'); return render_template('admin/create_user.html',roles=ROLES,role_labels=ROLE_LABELS)
        u = User(username=username,full_name=full_name,email=email,role=role,created_by=current_user.id)
        u.set_password(password); db.session.add(u); db.session.commit()
        flash(f'Account created for {full_name} ({ROLE_LABELS.get(role,role)}).','success')
        return redirect(url_for('admin.user_list'))
    return render_template('admin/create_user.html',roles=ROLES,role_labels=ROLE_LABELS)

@admin_bp.route('/users/<int:uid>/toggle-lock', methods=['POST'])
@login_required
@admin_only
def toggle_lock(uid):
    u = User.query.get_or_404(uid)
    if u.id==current_user.id: flash('Cannot lock yourself.','danger'); return redirect(url_for('admin.user_list'))
    u.is_locked=not u.is_locked
    if not u.is_locked: u.failed_attempts=0
    db.session.commit(); flash(f'{u.username} {"locked" if u.is_locked else "unlocked"}.','success')
    return redirect(url_for('admin.user_list'))

@admin_bp.route('/users/<int:uid>/force-mfa', methods=['POST'])
@login_required
@admin_only
def force_mfa(uid):
    u = User.query.get_or_404(uid); u.requires_otp=True; db.session.commit()
    flash(f'MFA enforced for {u.username}.','warning'); return redirect(url_for('admin.user_list'))

@admin_bp.route('/users/<int:uid>/clear-mfa', methods=['POST'])
@login_required
@admin_only
def clear_mfa(uid):
    u = User.query.get_or_404(uid); u.requires_otp=False; u.failed_attempts=0; db.session.commit()
    flash(f'MFA cleared for {u.username}.','success'); return redirect(url_for('admin.user_list'))

@admin_bp.route('/activity-logs')
@login_required
@admin_only
def activity_logs():
    page = request.args.get('page',1,type=int)
    logs = ActivityLog.query.order_by(ActivityLog.timestamp.desc()).paginate(page=page,per_page=30)
    return render_template('admin/activity_logs.html', logs=logs)

@admin_bp.route('/risk-logs')
@login_required
@admin_only
def risk_logs():
    page = request.args.get('page',1,type=int)
    logs = RiskLog.query.order_by(RiskLog.timestamp.desc()).paginate(page=page,per_page=30)
    return render_template('admin/risk_logs.html', logs=logs)

@admin_bp.route('/auth-logs')
@login_required
@admin_only
def auth_logs():
    page = request.args.get('page',1,type=int)
    logs = AuthenticationLog.query.order_by(AuthenticationLog.timestamp.desc()).paginate(page=page,per_page=30)
    return render_template('admin/auth_logs.html', logs=logs)

@admin_bp.route('/users/<int:uid>/edit', methods=['GET','POST'])
@login_required
@admin_only
def edit_user(uid):
    u = User.query.get_or_404(uid)
    ROLE_LIST = ['doctor','nurse','receptionist','pharmacist','lab_technician','admin']
    if request.method == 'POST':
        full_name = request.form.get('full_name','').strip()
        email     = request.form.get('email','').strip().lower()
        role      = request.form.get('role', u.role)

        if not full_name or not email:
            flash('Full name and email are required.','danger')
            return render_template('admin/edit_user.html', u=u, roles=ROLE_LIST, role_labels=ROLE_LABELS)

        # Check email not taken by someone else
        existing = User.query.filter_by(email=email).first()
        if existing and existing.id != u.id:
            flash('That email is already used by another user.','danger')
            return render_template('admin/edit_user.html', u=u, roles=ROLE_LIST, role_labels=ROLE_LABELS)

        u.full_name = full_name
        u.email     = email
        u.role      = role
        db.session.commit()
        flash(f'{u.username} updated successfully. Email set to {email}','success')
        return redirect(url_for('admin.user_list'))

    return render_template('admin/edit_user.html', u=u, roles=ROLE_LIST, role_labels=ROLE_LABELS)

@admin_bp.route('/users/<int:uid>/clear-device', methods=['POST'])
@login_required
@admin_only
def clear_device(uid):
    """Reset device trust so the user can sign in from a new device."""
    u = User.query.get_or_404(uid)
    u.last_fingerprint = None
    db.session.add(ActivityLog(
        user_id=current_user.id, action='clear_device_trust', resource='user',
        resource_id=u.id, ip_address=request.remote_addr,
        details=f'Device fingerprint cleared for {u.username} by {current_user.username}'
    ))
    db.session.commit()
    flash(f'Device trust cleared for {u.username}. They can now log in from a new device.','success')
    return redirect(url_for('admin.user_list'))
