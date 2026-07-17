from flask import Blueprint, render_template, request, send_file, abort
from flask_login import login_required, current_user
from models.logs import ActivityLog, RiskLog, AuthenticationLog
from models.user import User
from extensions import db
from datetime import datetime, timezone, timedelta
import csv, io, json
from functools import wraps

forensics_bp = Blueprint('forensics', __name__)

def admin_only(f):
    @wraps(f)
    def w(*a,**k):
        if current_user.role!='admin': abort(403)
        return f(*a,**k)
    return w

@forensics_bp.route('/audit-trail')
@login_required
@admin_only
def audit_trail():
    uid_f  = request.args.get('user_id',type=int)
    action_f = request.args.get('action','')
    date_from= request.args.get('date_from','')
    date_to  = request.args.get('date_to','')
    q = ActivityLog.query.order_by(ActivityLog.timestamp.desc())
    if uid_f:    q = q.filter(ActivityLog.user_id==uid_f)
    if action_f: q = q.filter(ActivityLog.action.ilike(f'%{action_f}%'))
    if date_from:
        try: q = q.filter(ActivityLog.timestamp>=datetime.strptime(date_from,'%Y-%m-%d'))
        except: pass
    if date_to:
        try: q = q.filter(ActivityLog.timestamp<=datetime.strptime(date_to,'%Y-%m-%d'))
        except: pass
    logs  = q.limit(200).all()
    users = User.query.all()
    return render_template('forensics/audit_trail.html', logs=logs, users=users,
                           user_id=uid_f, action_filter=action_f, date_from=date_from, date_to=date_to)

@forensics_bp.route('/export/csv')
@login_required
@admin_only
def export_csv():
    logs = ActivityLog.query.order_by(ActivityLog.timestamp.desc()).all()
    out  = io.StringIO()
    w    = csv.writer(out)
    w.writerow(['ID','User ID','Username','Action','Resource','IP','Status','Timestamp','Details'])
    for l in logs:
        u = User.query.get(l.user_id)
        w.writerow([l.id,l.user_id,u.username if u else '?',l.action,l.resource,l.ip_address,l.status,l.timestamp.strftime('%Y-%m-%d %H:%M:%S'),l.details or ''])
    out.seek(0)
    fname = f'forensic_audit_{datetime.now(timezone(timedelta(hours=3))).strftime("%Y%m%d_%H%M%S")}.csv'
    return send_file(io.BytesIO(out.getvalue().encode()),mimetype='text/csv',as_attachment=True,download_name=fname)

@forensics_bp.route('/export/json')
@login_required
@admin_only
def export_json():
    logs = ActivityLog.query.order_by(ActivityLog.timestamp.desc()).all()
    out  = json.dumps({'exported_at':datetime.utcnow().isoformat(),'logs':[l.to_dict() for l in logs]},indent=2)
    fname= f'forensic_audit_{datetime.now(timezone(timedelta(hours=3))).strftime("%Y%m%d_%H%M%S")}.json'
    return send_file(io.BytesIO(out.encode()),mimetype='application/json',as_attachment=True,download_name=fname)

@forensics_bp.route('/user-timeline/<int:uid>')
@login_required
@admin_only
def user_timeline(uid):
    user      = User.query.get_or_404(uid)
    activity  = ActivityLog.query.filter_by(user_id=uid).order_by(ActivityLog.timestamp.desc()).limit(100).all()
    risk_evts = RiskLog.query.filter_by(user_id=uid).order_by(RiskLog.timestamp.desc()).limit(50).all()
    auth_evts = AuthenticationLog.query.filter_by(user_id=uid).order_by(AuthenticationLog.timestamp.desc()).limit(50).all()
    return render_template('forensics/user_timeline.html',user=user,activity=activity,risk_events=risk_evts,auth_events=auth_evts)
