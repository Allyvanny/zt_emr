"""
Profile Module — Zero Trust EMR
Handles user profile viewing, avatar upload, password change.
"""
import os, uuid
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from models.user import User
from models.logs import ActivityLog
from extensions import db
from werkzeug.utils import secure_filename

profile_bp = Blueprint('profile', __name__)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_upload_folder():
    folder = os.path.join(current_app.root_path, 'static', 'uploads', 'avatars')
    os.makedirs(folder, exist_ok=True)
    return folder

def log_act(action, details=None):
    db.session.add(ActivityLog(
        user_id=current_user.id, action=action,
        ip_address=request.remote_addr,
        user_agent=request.user_agent.string[:256],
        details=details
    ))
    db.session.commit()


@profile_bp.route('/profile')
@login_required
def view_profile():
    from models.logs import ActivityLog, RiskLog, AuthenticationLog
    recent_activity = ActivityLog.query.filter_by(user_id=current_user.id)\
                                       .order_by(ActivityLog.timestamp.desc()).limit(10).all()
    recent_risk     = RiskLog.query.filter_by(user_id=current_user.id)\
                                   .order_by(RiskLog.timestamp.desc()).limit(5).all()
    auth_events     = AuthenticationLog.query.filter_by(user_id=current_user.id)\
                                             .order_by(AuthenticationLog.timestamp.desc()).limit(10).all()
    from modules.ai_engine import compute_risk_score
    my_risk = compute_risk_score(current_user)
    return render_template('profile/view.html',
                           recent_activity=recent_activity,
                           recent_risk=recent_risk,
                           auth_events=auth_events,
                           my_risk=my_risk)


@profile_bp.route('/profile/upload-avatar', methods=['POST'])
@login_required
def upload_avatar():
    if 'avatar' not in request.files:
        flash('No file selected.', 'danger')
        return redirect(url_for('profile.view_profile'))

    file = request.files['avatar']
    if file.filename == '':
        flash('No file selected.', 'danger')
        return redirect(url_for('profile.view_profile'))

    if not allowed_file(file.filename):
        flash('Invalid file type. Please upload PNG, JPG, JPEG, GIF, or WEBP.', 'danger')
        return redirect(url_for('profile.view_profile'))

    # Check file size
    file.seek(0, 2)
    size = file.tell()
    file.seek(0)
    if size > MAX_FILE_SIZE:
        flash('File too large. Maximum size is 5MB.', 'danger')
        return redirect(url_for('profile.view_profile'))

    # Delete old avatar
    if current_user.avatar:
        old_path = os.path.join(get_upload_folder(), current_user.avatar)
        if os.path.exists(old_path):
            os.remove(old_path)

    # Save new avatar with unique name
    ext      = file.filename.rsplit('.', 1)[1].lower()
    filename = f'{current_user.id}_{uuid.uuid4().hex[:8]}.{ext}'
    filepath = os.path.join(get_upload_folder(), filename)
    file.save(filepath)

    current_user.avatar = filename
    db.session.commit()
    log_act('update_avatar', details='Profile picture updated')
    flash('Profile picture updated successfully!', 'success')
    return redirect(url_for('profile.view_profile'))


@profile_bp.route('/profile/remove-avatar', methods=['POST'])
@login_required
def remove_avatar():
    if current_user.avatar:
        old_path = os.path.join(get_upload_folder(), current_user.avatar)
        if os.path.exists(old_path):
            os.remove(old_path)
        current_user.avatar = None
        db.session.commit()
        log_act('remove_avatar', details='Profile picture removed')
        flash('Profile picture removed.', 'info')
    return redirect(url_for('profile.view_profile'))


@profile_bp.route('/profile/change-password', methods=['POST'])
@login_required
def change_password():
    current_pw  = request.form.get('current_password', '').strip()
    new_pw      = request.form.get('new_password', '').strip()
    confirm_pw  = request.form.get('confirm_password', '').strip()

    if not current_user.check_password(current_pw):
        flash('Current password is incorrect.', 'danger')
        return redirect(url_for('profile.view_profile'))
    if len(new_pw) < 8:
        flash('New password must be at least 8 characters.', 'danger')
        return redirect(url_for('profile.view_profile'))
    if new_pw != confirm_pw:
        flash('New passwords do not match.', 'danger')
        return redirect(url_for('profile.view_profile'))

    current_user.set_password(new_pw)
    db.session.commit()
    log_act('change_password', details='Password changed successfully')
    flash('Password changed successfully!', 'success')
    return redirect(url_for('profile.view_profile'))


@profile_bp.route('/settings/email', methods=['GET', 'POST'])
@login_required
def email_settings():
    """Admin-only page to configure SMTP settings stored in a local config file."""
    if current_user.role != 'admin':
        flash('Only administrators can configure email settings.', 'danger')
        return redirect(url_for('profile.view_profile'))

    config_path = os.path.join(current_app.root_path, 'email_config.py')
    current_config = {}

    # Read existing config
    if os.path.exists(config_path):
        try:
            with open(config_path) as f:
                exec(f.read(), current_config)
        except:
            pass

    if request.method == 'POST':
        smtp_user = request.form.get('smtp_user', '').strip()
        smtp_pass = request.form.get('smtp_pass', '').strip()
        smtp_host = request.form.get('smtp_host', 'smtp.gmail.com').strip()
        smtp_port = request.form.get('smtp_port', '587').strip()
        sendgrid_key = request.form.get('sendgrid_key', '').strip()
        email_provider = request.form.get('email_provider', 'smtp')

        config_content = f"""# Zero Trust EMR — Email Configuration
# Generated automatically. Do not edit manually.
SMTP_HOST = '{smtp_host}'
SMTP_PORT = {smtp_port}
SMTP_USER = '{smtp_user}'
SMTP_PASS = '{smtp_pass}'
SMTP_FROM = 'Zero Trust EMR <{smtp_user}>'
SENDGRID_API_KEY = '{sendgrid_key}'
"""
        with open(config_path, 'w') as f:
            f.write(config_content)

        # Update os.environ so auth module picks it up immediately
        import os as _os
        _os.environ['SMTP_HOST'] = smtp_host
        _os.environ['SMTP_PORT'] = smtp_port
        _os.environ['SMTP_USER'] = smtp_user
        _os.environ['SMTP_PASS'] = smtp_pass
        _os.environ['SMTP_FROM'] = f'Zero Trust EMR <{smtp_user}>'

        # Reload auth module smtp vars
        import modules.auth as auth_mod
        auth_mod.SMTP_HOST = smtp_host
        auth_mod.SMTP_PORT = int(smtp_port)
        auth_mod.SMTP_USER = smtp_user
        auth_mod.SMTP_PASS = smtp_pass
        auth_mod.SMTP_FROM = f'Zero Trust EMR <{smtp_user}>'

        log_act('update_email_config', details=f'SMTP configured for {smtp_user}')
        flash('Email settings saved! OTP codes will now be sent to real Gmail addresses.', 'success')

        # Send test email
        if 'send_test' in request.form:
            from modules.auth import send_otp_email
            ok, err = send_otp_email(current_user, '123456')
            if ok:
                flash(f'Test email sent to {current_user.email}! Check your inbox.', 'success')
            else:
                flash(f'Test failed: {err}', 'danger')

        return redirect(url_for('profile.email_settings'))

    return render_template('profile/email_settings.html', config=current_config)
