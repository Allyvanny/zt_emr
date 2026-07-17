"""Seed 200 patients, 7 users, drugs, prescriptions, lab requests."""
from models.user import User
from models.patient import Patient, MedicalRecord
from models.pharmacy import Drug, Prescription, PrescriptionItem
from models.laboratory import LabRequest, LabResult
from extensions import db
from datetime import datetime, date
import random

FIRST=[
    'Baraka','Fatuma','Joseph','Maria','Hassan','Neema','Patrick','Salma','David','Zainab',
    'Michael','Aisha','Emmanuel','Rose','Goodluck','Happiness','Omari','Rehema','Juma','Lightness',
    'Ally','Zawadi','Ismail','Tumaini','Rajabu','Amani','Shukrani','Sabina','Dismas','Edina',
    'Fidelis','Consolata','Devotha','Gaudensia','Herieth','Illuminata','Jackline','Kanoni','Lilian',
    'Magdalena','Noel','Olivia','Perpetua','Redempta','Scholastica','Theodora','Ursulo','Veronica',
    'Winifred','Yustina','Zacharia','Abel','Beatrice','Cyprian','Dorice','Elias','Fides','Gabriel',
]
LAST=[
    'Mwangi','Kamau','Osei','Banda','Dlamini','Nkomo','Sithole','Moyo','Phiri','Chirwa',
    'Tembo','Mbewe','Kasanda','Njiru','Msambwa','Salehe','Mwanga','Mwakipesile','Kiyamba',
    'Msigwa','Mwakalinga','Mwaisaka','Ngonyani','Mlowe','Mwasumbi','Mwakasege','Maganga',
    'Lyimo','Mrema','Munisi','Mushi','Mwambe','Mwakalolo','Msangi','Mwenda','Mwita',
    'Nyambo','Omary','Pallangyo','Rutabanzibwa','Sanga','Tarimo','Urio','Venance','Warioba',
]
DIAGNOSES=['Malaria','Hypertension','Type 2 Diabetes Mellitus','Tuberculosis (PTB)',
    'Community-Acquired Pneumonia','Iron Deficiency Anaemia','Upper Respiratory Tract Infection',
    'Acute Gastroenteritis','Urinary Tract Infection','Typhoid Fever','HIV/AIDS (on ART)',
    'Sickle Cell Disease','Asthma','Epilepsy','Peptic Ulcer Disease','Chronic Kidney Disease',
    'Congestive Heart Failure','Stroke (CVA)','Dengue Fever','Cholera','Severe Acute Malnutrition',
    'Schistosomiasis','Brucellosis','Meningitis','Hepatitis B','Appendicitis',
    'Fracture (Closed)','Burns (Grade II)','Pre-eclampsia','Leishmaniasis']
TREATMENTS=['Artemether-Lumefantrine 80/480mg x3 days','Amlodipine 5mg OD + lifestyle',
    'Metformin 500mg BD + dietary counseling','Rifampicin+Isoniazid+Pyrazinamide+Ethambutol',
    'Amoxicillin 500mg TID x7d','Ferrous Sulfate 200mg OD x3 months','Paracetamol 500mg PRN + rest',
    'ORS + Metronidazole 400mg TID x5d','Ciprofloxacin 500mg BD x7d','Chloramphenicol 500mg QID x14d',
    'ARVs continuation + Cotrimoxazole','Hydroxyurea 500mg OD + Folic acid',
    'Salbutamol inhaler PRN + Budesonide','Carbamazepine 200mg BD','Omeprazole 20mg OD + triple therapy',
    'Furosemide 40mg OD + Enalapril 5mg OD','Aspirin 300mg stat + Atorvastatin 40mg OD',
    'Paracetamol + IV fluids','ORS + IV Ringer\'s Lactate + Doxycycline',
    'F75 therapeutic diet + micronutrients','Praziquantel 40mg/kg single dose',
    'Doxycycline 100mg BD x6wk','Ceftriaxone 2g IV OD x10d','Tenofovir+Lamivudine+Dolutegravir',
    'Surgical referral + Cefazolin','Immobilisation + analgesics','Silver sulfadiazine + IV fluids',
    'MgSO4 + antihypertensives','Sodium Stibogluconate 20mg/kg/day IM x30d',
    'Supportive care + monitoring']
SYMPTOMS=['Fever, chills, headache, sweating','Persistent headache, dizziness, blurred vision',
    'Polyuria, polydipsia, weight loss','Cough >2wks, night sweats, weight loss',
    'Chest pain, cough, fever, dyspnoea','Pallor, fatigue, palpitations','Sore throat, runny nose',
    'Nausea, vomiting, diarrhoea, cramps','Dysuria, frequency, lower abdominal pain',
    'High fever, abdominal pain, constipation','Weight loss, chronic cough, oral thrush',
    'Bone pain, swelling, jaundice','Wheeze, chest tightness, nocturnal cough',
    'Recurrent seizures, post-ictal confusion','Epigastric pain, heartburn, haematemesis',
    'Bilateral leg oedema, dyspnoea on exertion','Sudden weakness, slurred speech, facial droop',
    'High fever, rash, myalgia, retro-orbital pain','Profuse watery diarrhoea, vomiting, dehydration',
    'Wasting, oedema, irritability','Haematuria, abdominal pain','Fever, joint pain, sweating',
    'Fever, severe headache, neck stiffness','Jaundice, fatigue, RUQ pain','RLQ pain, anorexia',
    'Deformity, swelling, pain post-trauma','Burn wound, blistering','Headache, oedema, high BP',
    'Skin ulcer, lymphadenopathy','General malaise, fatigue, anorexia']
DRUGS_DATA=[
    ('Artemether-Lumefantrine 80/480mg','Artemether-Lumefantrine','Antimalarial','Tablets',500,100,1500),
    ('Amoxicillin 500mg','Amoxicillin','Antibiotic','Capsules',400,80,800),
    ('Metronidazole 400mg','Metronidazole','Antibiotic','Tablets',600,100,600),
    ('Paracetamol 500mg','Paracetamol','Analgesic','Tablets',1000,200,300),
    ('Amlodipine 5mg','Amlodipine','Antihypertensive','Tablets',300,60,1200),
    ('Metformin 500mg','Metformin','Antidiabetic','Tablets',400,80,900),
    ('Ferrous Sulfate 200mg','Ferrous Sulfate','Supplement','Tablets',600,100,400),
    ('Ciprofloxacin 500mg','Ciprofloxacin','Antibiotic','Tablets',200,50,1800),
    ('Omeprazole 20mg','Omeprazole','Antacid','Capsules',300,60,1100),
    ('Salbutamol Inhaler','Salbutamol','Bronchodilator','Inhalers',80,20,8500),
    ('Carbamazepine 200mg','Carbamazepine','Anticonvulsant','Tablets',200,40,1500),
    ('Furosemide 40mg','Furosemide','Diuretic','Tablets',300,60,700),
    ('Enalapril 5mg','Enalapril','Antihypertensive','Tablets',250,50,1000),
    ('Hydroxyurea 500mg','Hydroxyurea','Antineoplastic','Capsules',100,30,5500),
    ('Rifampicin 150mg','Rifampicin','Antituberculosis','Tablets',400,80,2000),
    ('Isoniazid 100mg','Isoniazid','Antituberculosis','Tablets',400,80,800),
    ('Cotrimoxazole 480mg','Cotrimoxazole','Antibiotic','Tablets',500,100,600),
    ('Doxycycline 100mg','Doxycycline','Antibiotic','Capsules',200,50,1200),
    ('Ceftriaxone 1g','Ceftriaxone','Antibiotic','Vials',150,40,12000),
    ('Normal Saline 0.9% 1L','Sodium Chloride','IV Fluid','Bags',200,50,3500),
    ('Ringer\'s Lactate 1L','Lactated Ringer\'s','IV Fluid','Bags',200,50,3800),
    ('ORS Sachets','Oral Rehydration Salts','Supplement','Sachets',800,200,500),
    ('Folic Acid 5mg','Folic Acid','Supplement','Tablets',700,150,300),
    ('Vitamin B Complex','Vitamin B Complex','Supplement','Tablets',500,100,800),
    ('Chloramphenicol 500mg','Chloramphenicol','Antibiotic','Capsules',100,30,1800),
    ('Atorvastatin 40mg','Atorvastatin','Statin','Tablets',200,50,2200),
    ('Aspirin 75mg','Aspirin','Antiplatelet','Tablets',400,80,500),
    ('Praziquantel 600mg','Praziquantel','Anthelmintic','Tablets',200,40,3000),
    ('Acyclovir 200mg','Acyclovir','Antiviral','Tablets',150,40,2500),
    ('Budesonide 200mcg Inhaler','Budesonide','Corticosteroid','Inhalers',50,15,18000),
]

def seed_data():
    if User.query.count() > 0:
        return
    print("Seeding Zero Trust EMR v4...")
    users_data = [
        ('admin',        'Admin User',              'admin',          'admin@emr.local',        'Admin@1234'),
        ('dr_john',      'Dr. John Msambwa',        'doctor',         'dr.john@emr.local',      'Doctor@123'),
        ('dr_amina',     'Dr. Amina Salehe',        'doctor',         'dr.amina@emr.local',     'Doctor@123'),
        ('nurse_grace',  'Nurse Grace Mwanga',      'nurse',          'nurse.grace@emr.local',  'Nurse@1234'),
        ('receptionist', 'Sara Mwakipesile',        'receptionist',   'sara@emr.local',         'Recept@123'),
        ('pharmacist',   'Pharm. James Mwita',      'pharmacist',     'pharm.james@emr.local',  'Pharm@1234'),
        ('lab_tech',     'Lab Tech Amina Ngonyani', 'lab_technician', 'lab.amina@emr.local',    'LabTech@123'),
    ]
    created = []
    for username, full_name, role, email, password in users_data:
        u = User(username=username, full_name=full_name, role=role, email=email)
        u.set_password(password); db.session.add(u); created.append(u)
    db.session.flush()

    # Seed drugs
    drugs = []
    from datetime import date
    exp = date(2026, 12, 31)
    for name, generic, cat, unit, stock, reorder, price in DRUGS_DATA:
        d = Drug(name=name, generic_name=generic, category=cat, unit=unit,
                 stock_qty=stock, reorder_level=reorder, unit_price=price, expiry_date=exp)
        db.session.add(d); drugs.append(d)
    db.session.flush()

    rec = created[4]; doc1 = created[1]; doc2 = created[2]
    pharm = created[5]; lab_t = created[6]

    random.seed(2025)
    for i in range(1, 201):
        dob = date(random.randint(1945,2015), random.randint(1,12), random.randint(1,28))
        p = Patient(patient_id=f'PT-2025-{i:05d}',
            full_name=f'{random.choice(FIRST)} {random.choice(LAST)}',
            date_of_birth=dob, gender=random.choice(['Male','Female']),
            phone=f'+255 7{random.randint(10,99)} {random.randint(100,999)} {random.randint(100,999)}',
            address=f'P.O. Box {random.randint(1,999)}, {random.choice(["Mbeya","Dar es Salaam","Arusha","Dodoma","Mwanza","Iringa"])}',
            emergency_contact=f'+255 6{random.randint(50,99)} {random.randint(100,999)} {random.randint(100,999)}',
            blood_group=random.choice(['A+','A-','B+','B-','AB+','AB-','O+','O-']),
            registered_by=rec.id)
        db.session.add(p); db.session.flush()

        for _ in range(random.randint(1,4)):
            idx = random.randint(0, len(DIAGNOSES)-1)
            doc = random.choice([doc1, doc2])
            rec_obj = MedicalRecord(patient_id=p.id, doctor_id=doc.id,
                diagnosis=DIAGNOSES[idx], symptoms=SYMPTOMS[idx % len(SYMPTOMS)],
                treatment=TREATMENTS[idx % len(TREATMENTS)],
                prescription=TREATMENTS[idx % len(TREATMENTS)],
                lab_results=f'CBC: WBC 8.2, Hgb {random.uniform(8,14):.1f}, Plt {random.randint(100,350)}',
                notes='Patient advised to complete treatment. Return in 2 weeks.',
                is_confidential=random.random()<0.08)
            db.session.add(rec_obj); db.session.flush()

            # Prescription
            if random.random() > 0.3:
                rx_no = f'RX-2025-{Prescription.query.count()+1:05d}'
                rx = Prescription(prescription_no=rx_no, patient_id=p.id,
                    medical_record_id=rec_obj.id, prescribed_by=doc.id,
                    dispensed_by=pharm.id if random.random()>0.4 else None,
                    status=random.choice(['pending','dispensed','dispensed','dispensed']),
                    notes=TREATMENTS[idx % len(TREATMENTS)])
                if rx.status=='dispensed':
                    rx.dispensed_at = datetime.utcnow()
                db.session.add(rx); db.session.flush()
                drug = random.choice(drugs)
                qty  = random.randint(10,60)
                if drug.stock_qty >= qty:
                    db.session.add(PrescriptionItem(prescription_id=rx.id, drug_id=drug.id,
                        dosage='1 tablet', frequency='Twice daily', duration='7 days',
                        quantity=qty, dispensed_qty=qty if rx.status=='dispensed' else 0))
                    if rx.status=='dispensed': drug.stock_qty -= qty

            # Lab request
            if random.random() > 0.4:
                tests = ['Full Blood Count','Malaria RDT','Blood Glucose','HIV Rapid Test','Urinalysis','Hepatitis B Surface Antigen','Widal Test','CD4 Count']
                test  = random.choice(tests)
                rno   = f'LAB-2025-{LabRequest.query.count()+1:05d}'
                status= random.choice(['pending','completed','completed','in_progress'])
                lr = LabRequest(request_no=rno, patient_id=p.id, requested_by=doc.id,
                    processed_by=lab_t.id if status!='pending' else None,
                    test_type=test, test_category='Haematology', priority=random.choice(['routine','routine','urgent']),
                    clinical_notes=DIAGNOSES[idx], specimen_type='Blood', status=status,
                    completed_at=datetime.utcnow() if status=='completed' else None)
                db.session.add(lr); db.session.flush()
                if status=='completed':
                    interp = random.choice(['normal','normal','abnormal','critical'])
                    db.session.add(LabResult(request_id=lr.id,
                        result_data=f'Hgb: {random.uniform(8,15):.1f} g/dL\nWBC: {random.uniform(4,14):.1f} x10⁹/L\nPlt: {random.randint(80,400)} x10⁹/L',
                        reference_range='Hgb: 12-17 g/dL\nWBC: 4-11 x10⁹/L\nPlt: 150-400 x10⁹/L',
                        interpretation=interp, verified_by=lab_t.id,
                        comments='Result verified by laboratory technician.'))

    db.session.commit()
    print(f"Seeded: {Patient.query.count()} patients, {Drug.query.count()} drugs, {Prescription.query.count()} prescriptions, {LabRequest.query.count()} lab requests")
    print("\n--- LOGIN CREDENTIALS ---")
    for u, fn, role, email, pw in users_data:
        print(f"  {role:15s} | {u:15s} | {pw:15s} | {email}")
    print("-------------------------\n")
