"""
Zero Trust EMR - Performance Benchmark
Measures real request-response times for key pages using the Flask test client
with a fully seeded database. Run after the app is set up:

    python benchmark_performance.py

Outputs a summary table of p50/p95/max response times per endpoint.
"""
import os, sys, time, tempfile, statistics

os.environ['FLASK_ENV'] = 'testing'
tmpdir = tempfile.mkdtemp(prefix='emr_bench_')
os.environ['DATABASE_URL'] = 'sqlite:///' + os.path.join(tmpdir, 'bench.db')

sys.path.insert(0, r'C:\xampp\htdocs\zt_emr')

from app import app as flask_app
from extensions import db
from modules.seed import seed_data

PAGE_PLAN = {
    'Receptionist': [
        ('patients.dashboard',      '/dashboard',            None),
        ('patients.list',           '/list',                 None),
        ('patients.register',       '/register',             None),
        ('patients.view',           '/<pid>',                1),
    ],
    'Doctor': [
        ('appointments.doctor_dashboard', '/doctor/dashboard', None),
        ('appointments.list',             '/appointments',    None),
        ('patients.list',                 '/list',            None),
        ('patients.view',                 '/<pid>',           1),
        ('appointments.book',             '/appointments/book', None),
    ],
    'Lab Technician': [
        ('laboratory.dashboard', '/dashboard', None),
        ('laboratory.requests',  '/requests',  None),
        ('laboratory.results',   '/results',   None),
        ('laboratory.view_request', '/requests/<rid>', 1),
    ],
    'Pharmacist': [
        ('pharmacy.dashboard',     '/dashboard',          None),
        ('pharmacy.prescriptions', '/prescriptions',      None),
        ('pharmacy.drugs',         '/drugs',              None),
        ('pharmacy.view_prescription', '/prescriptions/<rx_id>', 1),
    ],
    'Admin': [
        ('patients.dashboard',     '/dashboard',  None),
        ('admin.users',            '/users',      None),
        ('admin.activity_logs',    '/activity-logs', None),
        ('admin.risk_logs',        '/risk-logs',  None),
        ('admin.auth_logs',        '/auth-logs',  None),
        ('forensics.audit_trail',  '/audit-trail', None),
    ],
}

LOGINS = {
    'admin':         ('admin',        'Admin@1234'),
    'Doctor':        ('dr_john',      'Doctor@123'),
    'Lab Technician':('lab_tech',     'LabTech@123'),
    'Pharmacist':    ('pharmacist',   'Pharm@1234'),
    'Receptionist':  ('receptionist', 'Recept@123'),
}

# Map benchmark role labels (PAGE_PLAN keys) to LOGINS keys
ROLE_LOGIN_KEY = {
    'Admin': 'admin',
    'Doctor': 'Doctor',
    'Lab Technician': 'Lab Technician',
    'Pharmacist': 'Pharmacist',
    'Receptionist': 'Receptionist',
}


def login(client, username, password):
    resp = client.post('/login', data={
        'username': username, 'password': password,
        'device_fp': 'benchmark-device',
    }, follow_redirects=False)
    # New device triggers OTP - verify with the demo flow if redirected
    if resp.status_code == 302 and '/verify-otp' in resp.headers.get('Location', ''):
        with flask_app.app_context():
            from models.user import User
            u = User.query.filter_by(username=username).first()
            code = u.otp_code
        client.post('/verify-otp', data={'otp': code, 'remember_device': 'off'})
    return client


def time_endpoint(client, path):
    times = []
    for _ in range(10):
        t0 = time.perf_counter()
        client.get(path, follow_redirects=False)
        times.append((time.perf_counter() - t0) * 1000)
    times.sort()
    p50  = times[len(times)//2]
    p95  = times[int(len(times)*0.95)-1]
    mx   = times[-1]
    return p50, p95, mx


def main():
    with flask_app.app_context():
        db.drop_all(); db.create_all()
        seed_data()
        from models.patient import Patient
        from models.laboratory import LabRequest
        from models.pharmacy import Prescription
        first_pid = Patient.query.first().id
        first_rx  = Prescription.query.first().id
        first_lab = LabRequest.query.first().id
        print(f"Seeded: {Patient.query.count()} patients, "
              f"{Prescription.query.count()} prescriptions, "
              f"{LabRequest.query.count()} lab requests")
        print()

        results = []
        for role in PAGE_PLAN:
            login_key = ROLE_LOGIN_KEY.get(role)
            if not login_key:
                continue
            client = flask_app.test_client()
            login(client, *LOGINS[login_key])
            row = {'role': role, 'pages': []}
            for name, path, swap in PAGE_PLAN[role]:
                url = path.replace('<pid>', str(first_pid)) \
                          .replace('<rid>', str(first_lab)) \
                          .replace('<rx_id>', str(first_rx))
                p50, p95, mx = time_endpoint(client, url)
                row['pages'].append((name, url, p50, p95, mx))
            results.append(row)
            print(f"{role}: done")

        print("\n=== PERFORMANCE BENCHMARK (10 requests each) ===")
        print("Timings are server-side processing time via the Flask test client")
        print("(excludes network latency; a real browser adds ~50-150ms RTT).")
        print(f"{'Role':<16}{'Page':<38}{'p50':>8}{'p95':>8}{'max':>9}")
        print('-' * 80)
        all_p50 = []
        for row in results:
            for name, url, p50, p95, mx in row['pages']:
                all_p50.append(p50)
                print(f"{row['role']:<16}{name:<38}{p50:>7.1f}ms{p95:>7.1f}ms{mx:>8.1f}ms")
        print('-' * 80)
        print(f"Overall median p50: {statistics.median(all_p50):.1f} ms")
        print(f"Overall mean   p50: {statistics.mean(all_p50):.1f} ms")


if __name__ == '__main__':
    main()
