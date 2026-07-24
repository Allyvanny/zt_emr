"""
Import data from deploy_data.json into SQLite on PythonAnywhere.
Run on PythonAnywhere: python seed_database.py
"""
import json, os
from datetime import datetime, date

# Must be inside Flask app context
from app import app, db
from models.user import User
from models.patient import Patient, MedicalRecord, VitalSign, Allergy
from models.logs import ActivityLog, RiskLog, AuthenticationLog
from models.pharmacy import Drug, Prescription, PrescriptionItem
from models.laboratory import LabRequest, LabResult
from models.appointment import Appointment

def parse_datetime(val):
    """Convert ISO string back to datetime object for SQLite."""
    if val is None or isinstance(val, (datetime, date)):
        return val
    if isinstance(val, str) and val.strip():
        try:
            return datetime.fromisoformat(val)
        except (ValueError, TypeError):
            return None
    return None

with app.app_context():
    db.create_all()

    if not os.path.exists('deploy_data.json'):
        print("deploy_data.json not found! Push it to GitHub first.")
        exit(1)

    with open('deploy_data.json') as f:
        data = json.load(f)

    # Import order matters (foreign keys)
    table_map = {
        'users': User,
        'patients': Patient,
        'medical_records': MedicalRecord,
        'vital_signs': VitalSign,
        'allergies': Allergy,
        'activity_logs': ActivityLog,
        'risk_logs': RiskLog,
        'authentication_logs': AuthenticationLog,
        'drugs': Drug,
        'prescriptions': Prescription,
        'prescription_items': PrescriptionItem,
        'lab_requests': LabRequest,
        'lab_results': LabResult,
        'appointments': Appointment,
    }

    for table_name, model in table_map.items():
        if table_name not in data:
            print(f"  Skipping {table_name} (not in export)")
            continue
        rows = data[table_name]['rows']
        columns = data[table_name]['columns']
        if not rows:
            print(f"  {table_name}: 0 rows (empty)")
            continue
        count = 0
        for row in rows:
            row_dict = dict(zip(columns, row))
            # Remove id to let SQLite auto-increment
            row_dict.pop('id', None)
            # Skip NULLs so defaults apply
            row_dict = {k: v for k, v in row_dict.items() if v is not None}
            # Convert ISO datetime strings to datetime objects
            for k, v in row_dict.items():
                row_dict[k] = parse_datetime(v)
            try:
                obj = model(**row_dict)
                db.session.add(obj)
                count += 1
            except Exception as e:
                print(f"  {table_name} row skipped: {e}")
        db.session.commit()
        print(f"  {table_name}: {count} rows imported")

    print("\nDone! All data imported.")
