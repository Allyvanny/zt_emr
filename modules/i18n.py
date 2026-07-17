"""
Patient Portal translations — English / Swahili.
No external dependency (no Flask-Babel, no .po compilation needed).
Language choice is stored in the session and only affects patient-facing pages.
"""
from flask import session

DEFAULT_LANG    = 'en'
SUPPORTED_LANGS = ('en', 'sw')
LANG_LABELS     = {'en': 'English', 'sw': 'Kiswahili'}

TRANSLATIONS = {
    # ── Sidebar / nav (patient_portal/base.html) ──
    'brand_name':              {'en': 'Health Portal',                'sw': 'Tovuti ya Afya'},
    'nav_section_my_health':   {'en': 'My Health',                    'sw': 'Afya Yangu'},
    'nav_dashboard':           {'en': 'Dashboard',                    'sw': 'Dashibodi'},
    'nav_health_records':      {'en': 'My Health Records',            'sw': 'Rekodi Zangu za Afya'},
    'nav_my_appointments':     {'en': 'My Appointments',              'sw': 'Miadi Yangu'},
    'nav_section_comm':        {'en': 'Communication',                'sw': 'Mawasiliano'},
    'nav_messages':            {'en': 'Messages',                     'sw': 'Ujumbe'},
    'nav_new_message':         {'en': 'New Message',                  'sw': 'Ujumbe Mpya'},
    'nav_request_appointment': {'en': 'Request Appointment',          'sw': 'Omba Miadi'},
    'nav_section_account':     {'en': 'Account',                      'sw': 'Akaunti'},
    'nav_my_profile':          {'en': 'My Profile',                   'sw': 'Wasifu Wangu'},
    'sign_out':                {'en': 'Sign Out',                     'sw': 'Toka'},
    'patient_label':           {'en': 'Patient',                      'sw': 'Mgonjwa'},
    'footer_text':             {'en': 'Patient Health Portal — Zero Trust EMR • MUST BCS/25 • Alto Dezdel Kiyamba',
                                 'sw': 'Tovuti ya Afya ya Mgonjwa — Zero Trust EMR • MUST BCS/25 • Alto Dezdel Kiyamba'},
    'language_label':          {'en': 'Language',                     'sw': 'Lugha'},

    # ── Login page ──
    'patient_portal_title':    {'en': 'Patient Portal',               'sw': 'Tovuti ya Mgonjwa'},
    'tagline_zt':              {'en': 'Zero Trust EMR — MUST BCS/25', 'sw': 'Zero Trust EMR — MUST BCS/25'},
    'health_fingertips':       {'en': 'Your health, at your fingertips', 'sw': 'Afya yako, mkononi mwako'},
    'feat_message_doctor':     {'en': 'Message doctor',               'sw': 'Tuma ujumbe kwa daktari'},
    'feat_book_appointments':  {'en': 'Book appointments',            'sw': 'Panga miadi'},
    'feat_health_records':     {'en': 'Health records',               'sw': 'Rekodi za afya'},
    'feat_prescriptions':      {'en': 'Prescriptions',                'sw': 'Dawa Zilizoandikwa'},
    'username':                {'en': 'Username',                     'sw': 'Jina la Mtumiaji'},
    'password':                {'en': 'Password',                     'sw': 'Nenosiri'},
    'your_username':           {'en': 'Your username',                'sw': 'Jina lako la mtumiaji'},
    'your_password':           {'en': 'Your password',                'sw': 'Nenosiri lako'},
    'sign_in':                 {'en': '🔓 Sign In',                   'sw': '🔓 Ingia'},
    'new_here':                {'en': 'New here?',                    'sw': 'Mgeni hapa?'},
    'no_account':              {'en': 'No account?',                  'sw': 'Huna akaunti?'},
    'create_one_free':         {'en': 'Create one free →',            'sw': 'Fungua bila malipo →'},
    'staff_login':             {'en': '🔐 Staff login (Doctors, Nurses, Admin)',
                                 'sw': '🔐 Kuingia kwa Wafanyakazi (Madaktari, Wauguzi, Msimamizi)'},

    # ── Register page ──
    'create_your_account':     {'en': 'Create Your Account',          'sw': 'Fungua Akaunti Yako'},
    'join_portal':             {'en': 'Join the Patient Portal — free & easy', 'sw': 'Jiunge na Tovuti ya Mgonjwa — bure na rahisi'},
    'section_credentials':     {'en': '👤 Account Credentials',       'sw': '👤 Taarifa za Akaunti'},
    'email_address':           {'en': 'Email Address',                'sw': 'Barua Pepe'},
    'confirm_password':        {'en': 'Confirm Password',             'sw': 'Thibitisha Nenosiri'},
    'section_personal':        {'en': '📋 Personal Information',      'sw': '📋 Taarifa Binafsi'},
    'full_name':               {'en': 'Full Name',                    'sw': 'Jina Kamili'},
    'date_of_birth':           {'en': 'Date of Birth',                'sw': 'Tarehe ya Kuzaliwa'},
    'gender':                  {'en': 'Gender',                       'sw': 'Jinsia'},
    'select_placeholder':      {'en': '— Select —',                   'sw': '— Chagua —'},
    'male':                    {'en': 'Male',                         'sw': 'Mwanaume'},
    'female':                  {'en': 'Female',                       'sw': 'Mwanamke'},
    'other':                   {'en': 'Other',                        'sw': 'Nyingine'},
    'phone_number':            {'en': 'Phone Number',                 'sw': 'Namba ya Simu'},
    'blood_group':             {'en': 'Blood Group',                  'sw': 'Aina ya Damu'},
    'address':                 {'en': 'Address',                      'sw': 'Anwani'},
    'emergency_contact':       {'en': 'Emergency Contact',            'sw': 'Mawasiliano ya Dharura'},
    'emergency_hint':          {'en': 'Person to contact in case of emergency', 'sw': 'Mtu wa kuwasiliana naye endapo kuna dharura'},
    'create_account_btn':      {'en': '✓ Create My Account',          'sw': '✓ Fungua Akaunti Yangu'},
    'already_have_account':    {'en': 'Already have an account?',     'sw': 'Una akaunti tayari?'},
    'sign_in_link':            {'en': 'Sign in →',                    'sw': 'Ingia →'},
    'username_hint':           {'en': 'Lowercase, no spaces',         'sw': 'Herufi ndogo, bila nafasi'},
    'min_6_chars':             {'en': 'Min 6 characters',             'sw': 'Angalau herufi 6'},
    'repeat_password':         {'en': 'Repeat password',              'sw': 'Rudia nenosiri'},
    'full_name_hint':          {'en': 'Your full name as on medical records', 'sw': 'Jina lako kamili kama lilivyo kwenye rekodi za matibabu'},

    # ── Dashboard ──
    'my_dashboard':            {'en': 'My Dashboard',                 'sw': 'Dashibodi Yangu'},
    'welcome_back':            {'en': 'Welcome back, {name}',         'sw': 'Karibu tena, {name}'},
    'hello_wave':              {'en': 'Hello, {name}! 👋',            'sw': 'Habari, {name}! 👋'},
    'your_doctor':             {'en': 'Your doctor:',                 'sw': 'Daktari wako:'},
    'welcome_to_portal':       {'en': 'Welcome to your health portal', 'sw': 'Karibu kwenye tovuti yako ya afya'},
    'last_login':              {'en': 'Last login:',                  'sw': 'Kuingia mara ya mwisho:'},
    'first_visit':             {'en': 'First visit',                  'sw': 'Ziara ya kwanza'},
    'message_doctor_btn':      {'en': '💬 Message Doctor',            'sw': '💬 Tuma Ujumbe kwa Daktari'},
    'request_appointment_btn': {'en': '📅 Request Appointment',       'sw': '📅 Omba Miadi'},
    'stat_messages':           {'en': 'Messages',                     'sw': 'Ujumbe'},
    'stat_unread':             {'en': 'unread',                       'sw': 'haujasomwa'},
    'stat_appointments':       {'en': 'Appointments',                 'sw': 'Miadi'},
    'stat_pending':            {'en': 'pending',                      'sw': 'inasubiri'},
    'stat_health_records':     {'en': 'Health Records',               'sw': 'Rekodi za Afya'},
    'not_yet_linked':          {'en': 'Not yet linked',               'sw': 'Bado haijaunganishwa'},
    'stat_prescriptions':      {'en': 'Prescriptions',                'sw': 'Dawa Zilizoandikwa'},
    'recent_messages':         {'en': '💬 Recent Messages',           'sw': '💬 Ujumbe wa Hivi Karibuni'},
    'view_all':                {'en': 'View all →',                   'sw': 'Ona zote →'},
    'no_messages_yet':         {'en': 'No messages yet.',             'sw': 'Hakuna ujumbe bado.'},
    'send_first_message':      {'en': 'Send your first message',      'sw': 'Tuma ujumbe wako wa kwanza'},
    'my_appt_requests':        {'en': '📅 My Appointment Requests',   'sw': '📅 Maombi Yangu ya Miadi'},
    'no_appt_requests':        {'en': 'No appointment requests yet.', 'sw': 'Hakuna maombi ya miadi bado.'},
    'any_doctor':              {'en': 'Any doctor',                   'sw': 'Daktari yeyote'},
    'date_flexible':           {'en': 'Date flexible',                'sw': 'Tarehe inabadilika'},
    'recent_health_records':   {'en': '🩺 Recent Health Records',     'sw': '🩺 Rekodi za Afya za Hivi Karibuni'},
    'th_date':                 {'en': 'Date',                         'sw': 'Tarehe'},
    'th_doctor':               {'en': 'Doctor',                       'sw': 'Daktari'},
    'th_diagnosis':            {'en': 'Diagnosis',                    'sw': 'Uchunguzi'},
    'th_treatment':            {'en': 'Treatment',                    'sw': 'Matibabu'},
    'quick_message_doctor':    {'en': 'Message My Doctor',            'sw': 'Tuma Ujumbe kwa Daktari Wangu'},
    'quick_request_appt':      {'en': 'Request Appointment',          'sw': 'Omba Miadi'},
    'quick_view_records':      {'en': 'View Health Records',          'sw': 'Ona Rekodi za Afya'},
    'quick_update_profile':    {'en': 'Update My Profile',            'sw': 'Sasisha Wasifu Wangu'},

    # ── Messages list page ──
    'page_messages':           {'en': 'Messages',                     'sw': 'Ujumbe'},
    'msg_subtitle':            {'en': 'Communicate with your healthcare team', 'sw': 'Wasiliana na timu yako ya afya'},
    'received_sent_count':     {'en': '{recv} received · {sent} sent', 'sw': '{recv} zilizopokelewa · {sent} zilizotumwa'},
    'tab_inbox':                {'en': '📥 Inbox',                    'sw': '📥 Ujumbe Uliopokelewa'},
    'tab_sent':                 {'en': '📤 Sent',                     'sw': '📤 Ulizotuma'},
    'inbox_empty':              {'en': 'Your inbox is empty',         'sw': 'Sanduku lako la ujumbe halina kitu'},
    'inbox_empty_sub':          {'en': 'Messages from your doctor will appear here', 'sw': 'Ujumbe kutoka kwa daktari wako utaonekana hapa'},
    'no_sent_yet':              {'en': 'No sent messages yet.',       'sw': 'Hakuna ujumbe uliotumwa bado.'},
    'send_a_message':           {'en': 'Send a message',              'sw': 'Tuma ujumbe'},
    'to_label':                 {'en': 'To:',                         'sw': 'Kwa:'},
    'read_label':               {'en': '✓ Read',                      'sw': '✓ Imesomwa'},
    'unread_label':              {'en': 'Unread',                     'sw': 'Haijasomwa'},

    # ── Send message page ──
    'send_message_title':      {'en': 'Send Message',                 'sw': 'Tuma Ujumbe'},
    'send_message_sub':        {'en': 'Contact your healthcare team',  'sw': 'Wasiliana na timu yako ya afya'},
    'breadcrumb_messages':     {'en': '← Messages',                   'sw': '← Ujumbe'},
    'new_message_h2':          {'en': 'New Message',                  'sw': 'Ujumbe Mpya'},
    'replying_to':             {'en': 'Replying to',                  'sw': 'Unajibu'},
    'compose_message':         {'en': '✉️ Compose Message',           'sw': '✉️ Andika Ujumbe'},
    'send_to':                 {'en': 'Send To',                      'sw': 'Tuma Kwa'},
    'select_recipient':        {'en': '— Select recipient —',         'sw': '— Chagua mpokeaji —'},
    'message_type':            {'en': 'Message Type',                 'sw': 'Aina ya Ujumbe'},
    'type_general':            {'en': '💬 General Message',           'sw': '💬 Ujumbe wa Kawaida'},
    'type_medical_advice':     {'en': '🩺 Medical Advice',            'sw': '🩺 Ushauri wa Kitabibu'},
    'type_appointment_request':{'en': '📅 Appointment Request',       'sw': '📅 Ombi la Miadi'},
    'type_progress_update':    {'en': '📊 Progress Update',           'sw': '📊 Taarifa ya Maendeleo'},
    'type_urgent':             {'en': '🚨 Urgent',                    'sw': '🚨 Dharura'},
    'subject_label':           {'en': 'Subject',                      'sw': 'Kichwa cha Habari'},
    'subject_placeholder':     {'en': 'Brief subject of your message…', 'sw': 'Kichwa kifupi cha ujumbe wako…'},
    'message_label':           {'en': 'Message',                      'sw': 'Ujumbe'},
    'message_placeholder':     {'en': 'Write your message here. Be as detailed as possible so your doctor can help you better…',
                                 'sw': 'Andika ujumbe wako hapa. Toa maelezo mengi iwezekanavyo ili daktari wako aweze kukusaidia vizuri zaidi…'},
    'message_privacy_hint':    {'en': 'Your message is private and secure. Only you and the recipient can read it.',
                                 'sw': 'Ujumbe wako ni wa faragha na salama. Wewe na mpokeaji tu ndio mnaweza kuusoma.'},
    'encrypted_notice':        {'en': '🔒 Your messages are encrypted and stored securely in the Zero Trust EMR system.',
                                 'sw': '🔒 Ujumbe wako umefichwa na kuhifadhiwa kwa usalama katika mfumo wa Zero Trust EMR.'},
    'cancel':                  {'en': 'Cancel',                       'sw': 'Ghairi'},
    'send_message_btn':        {'en': '📤 Send Message',              'sw': '📤 Tuma Ujumbe'},

    # ── View message page ──
    'message_word':            {'en': 'Message',                      'sw': 'Ujumbe'},
    'reply_btn':                {'en': '↩️ Reply',                    'sw': '↩️ Jibu'},
    'replies_count':            {'en': 'Replies ({n})',               'sw': 'Majibu ({n})'},
    'reply_to_message':         {'en': '↩️ Reply to this message',    'sw': '↩️ Jibu ujumbe huu'},

    # ── My Appointments list page ──
    'my_appointments_title':   {'en': 'My Appointments',              'sw': 'Miadi Yangu'},
    'my_appointments_sub':     {'en': 'Track your appointment requests', 'sw': 'Fuatilia maombi yako ya miadi'},
    'my_appt_requests_h2':     {'en': 'My Appointment Requests',      'sw': 'Maombi Yangu ya Miadi'},
    'total_requests_count':    {'en': '{n} total requests',           'sw': 'jumla ya maombi {n}'},
    'new_request_btn':         {'en': '📅 New Request',               'sw': '📅 Ombi Jipya'},
    'any_available_doctor':    {'en': 'Any available doctor',         'sw': 'Daktari yeyote aliyepo'},
    'flexible':                {'en': 'Flexible',                     'sw': 'Inabadilika'},
    'alt_label':               {'en': 'Alt:',                         'sw': 'Mbadala:'},
    'requested_label':         {'en': '🕐 Requested',                 'sw': '🕐 Iliombwa'},
    'status_pending_note':     {'en': 'Your request is being reviewed. You will receive a message once the doctor responds.',
                                 'sw': 'Ombi lako linakaguliwa. Utapokea ujumbe mara daktari atakapojibu.'},
    'status_approved_note':    {'en': 'Approved!',                    'sw': 'Imeidhinishwa!'},
    'appt_confirmed':          {'en': 'Your appointment has been confirmed.', 'sw': 'Miadi yako imethibitishwa.'},
    'status_rejected_note':    {'en': 'Not approved.',                'sw': 'Haikuidhinishwa.'},
    'submit_new_request':      {'en': 'Submit a new request →',       'sw': 'Wasilisha ombi jipya →'},
    'no_appt_requests_title':  {'en': 'No appointment requests yet',  'sw': 'Hakuna maombi ya miadi bado'},
    'no_appt_requests_sub':    {'en': 'Request an appointment with your doctor and they will confirm a suitable time.',
                                 'sw': 'Omba miadi na daktari wako naye atathibitisha muda unaofaa.'},
    'request_first_appt':      {'en': '📅 Request My First Appointment', 'sw': '📅 Omba Miadi Yangu ya Kwanza'},

    # ── Request appointment page ──
    'request_appt_title':      {'en': 'Request Appointment',          'sw': 'Omba Miadi'},
    'request_appt_sub':        {'en': 'Ask your doctor for an appointment', 'sw': 'Omba miadi kwa daktari wako'},
    'breadcrumb_my_appts':     {'en': '← My Appointments',            'sw': '← Miadi Yangu'},
    'request_an_appt_h2':      {'en': 'Request an Appointment',       'sw': 'Omba Miadi'},
    'appt_details_section':    {'en': '📅 Appointment Details',       'sw': '📅 Maelezo ya Miadi'},
    'preferred_doctor':        {'en': 'Preferred Doctor',             'sw': 'Daktari Unayempendelea'},
    'any_available_doctor_opt':{'en': '— Any available doctor —',     'sw': '— Daktari yeyote aliyepo —'},
    'urgency_level':           {'en': 'Urgency Level',                'sw': 'Kiwango cha Dharura'},
    'urgency_routine':         {'en': '🟢 Routine — within 2 weeks',  'sw': '🟢 Kawaida — ndani ya wiki 2'},
    'urgency_urgent':          {'en': '🟡 Urgent — within 2 days',    'sw': '🟡 Dharura — ndani ya siku 2'},
    'urgency_emergency':       {'en': '🔴 Emergency — today if possible', 'sw': '🔴 Dharura Kubwa — leo ikiwezekana'},
    'preferred_datetime':      {'en': 'Preferred Date & Time',        'sw': 'Tarehe na Muda Unaopendelea'},
    'first_choice_hint':       {'en': 'First choice — leave blank if flexible', 'sw': 'Chaguo la kwanza — acha wazi kama linabadilika'},
    'alt_datetime':            {'en': 'Alternative Date & Time',      'sw': 'Tarehe na Muda Mbadala'},
    'second_choice_hint':      {'en': 'Second choice (optional)',     'sw': 'Chaguo la pili (si lazima)'},
    'reason_for_appt':         {'en': 'Reason for Appointment',       'sw': 'Sababu ya Miadi'},
    'reason_placeholder':      {'en': 'Please describe:\n• What symptoms are you experiencing?\n• How long have you had them?\n• Any previous treatment?\n• Any questions for your doctor?',
                                 'sw': 'Tafadhali eleza:\n• Una dalili gani?\n• Umekuwa nazo kwa muda gani?\n• Kuna matibabu yoyote ya awali?\n• Una maswali yoyote kwa daktari wako?'},
    'reason_hint':             {'en': 'The more detail you provide, the better your doctor can prepare for your visit.',
                                 'sw': 'Kadiri unavyotoa maelezo zaidi, ndivyo daktari wako anavyoweza kujiandaa vizuri zaidi kwa ziara yako.'},
    'whats_next':              {'en': '📬 What happens next?',        'sw': '📬 Nini kinafuata?'},
    'next_step_1':             {'en': 'Your request is sent to the doctor', 'sw': 'Ombi lako linatumwa kwa daktari'},
    'next_step_2':             {'en': 'Doctor reviews and approves or suggests a new time', 'sw': 'Daktari anakagua na kuidhinisha au kupendekeza muda mpya'},
    'next_step_3':             {'en': 'You receive a notification message', 'sw': 'Utapokea ujumbe wa taarifa'},
    'next_step_4':             {'en': 'Come in at the confirmed time', 'sw': 'Fika kwa muda ulioidhinishwa'},
    'submit_request_btn':      {'en': '📅 Submit Request',            'sw': '📅 Wasilisha Ombi'},

    # ── My Health Records page ──
    'health_records_title':    {'en': 'My Health Records',            'sw': 'Rekodi Zangu za Afya'},
    'health_records_sub':      {'en': 'Your medical history, prescriptions and lab results',
                                 'sw': 'Historia yako ya matibabu, dawa zilizoandikwa na matokeo ya maabara'},
    'not_linked_title':        {'en': 'Your account is not yet linked to a medical record', 'sw': 'Akaunti yako bado haijaunganishwa na rekodi ya matibabu'},
    'not_linked_body':         {'en': 'Please visit the hospital reception and ask them to link your patient file to this account using your registered name:',
                                 'sw': 'Tafadhali fika ofisi ya mapokezi ya hospitali na uwaombe kuunganisha faili lako la mgonjwa na akaunti hii kwa kutumia jina ulilosajili nalo:'},
    'message_hospital':        {'en': '💬 Message the Hospital',      'sw': '💬 Tuma Ujumbe kwa Hospitali'},
    'tab_records':             {'en': 'Medical Records',              'sw': 'Rekodi za Matibabu'},
    'tab_prescriptions':       {'en': 'Prescriptions',                'sw': 'Dawa Zilizoandikwa'},
    'tab_lab':                 {'en': 'Lab Results',                  'sw': 'Matokeo ya Maabara'},
    'by_doctor':               {'en': 'by',                           'sw': 'na'},
    'confidential_badge':      {'en': 'Confidential',                 'sw': 'Siri'},
    'no_diagnosis':            {'en': 'No diagnosis',                 'sw': 'Hakuna uchunguzi'},
    'lbl_symptoms':            {'en': 'Symptoms',                     'sw': 'Dalili'},
    'lbl_diagnosis':           {'en': 'Diagnosis',                    'sw': 'Uchunguzi'},
    'lbl_treatment':           {'en': 'Treatment',                    'sw': 'Matibabu'},
    'lbl_prescription':        {'en': 'Prescription',                 'sw': 'Dawa Zilizoandikwa'},
    'lbl_notes':               {'en': 'Notes',                        'sw': 'Maelezo'},
    'confidential_notice':     {'en': '🔒 This record has been marked confidential by your doctor.',
                                 'sw': '🔒 Rekodi hii imewekwa alama ya siri na daktari wako.'},
    'no_records_yet':          {'en': 'No medical records on file yet.', 'sw': 'Hakuna rekodi za matibabu bado.'},
    'th_rx_number':            {'en': 'RX Number',                    'sw': 'Namba ya Dawa'},
    'th_prescribed_by':        {'en': 'Prescribed By',                'sw': 'Aliyeandika'},
    'th_status':               {'en': 'Status',                       'sw': 'Hali'},
    'th_details':              {'en': 'Details',                      'sw': 'Maelezo'},
    'more_suffix':             {'en': 'more',                         'sw': 'zaidi'},
    'no_prescriptions':        {'en': 'No prescriptions on file.',    'sw': 'Hakuna dawa zilizoandikwa.'},
    'lbl_result':              {'en': 'Result',                       'sw': 'Matokeo'},
    'lbl_reference':           {'en': 'Reference',                    'sw': 'Kiwango cha Rejea'},
    'lbl_comments':            {'en': 'Comments',                     'sw': 'Maoni'},
    'lbl_reported':            {'en': 'Reported',                     'sw': 'Iliripotiwa'},
    'results_pending':         {'en': 'Results pending…',             'sw': 'Matokeo yanasubiriwa…'},
    'no_lab_results':          {'en': 'No lab results on file.',      'sw': 'Hakuna matokeo ya maabara.'},

    # ── Profile page ──
    'profile_title':           {'en': 'My Profile',                   'sw': 'Wasifu Wangu'},
    'profile_sub':             {'en': 'Manage your personal information', 'sw': 'Simamia taarifa zako binafsi'},
    'patient_account_badge':   {'en': 'Patient Account',              'sw': 'Akaunti ya Mgonjwa'},
    'lbl_username':            {'en': 'Username',                     'sw': 'Jina la Mtumiaji'},
    'lbl_dob':                 {'en': 'Date of Birth',                'sw': 'Tarehe ya Kuzaliwa'},
    'lbl_gender':               {'en': 'Gender',                      'sw': 'Jinsia'},
    'lbl_blood_group':          {'en': 'Blood Group',                 'sw': 'Aina ya Damu'},
    'lbl_my_doctor':            {'en': 'My Doctor',                   'sw': 'Daktari Wangu'},
    'not_assigned':             {'en': 'Not assigned',                'sw': 'Hajapangwa'},
    'linked_title':             {'en': 'Linked to Medical Record',    'sw': 'Imeunganishwa na Rekodi ya Matibabu'},
    'linked_sub':                {'en': 'Your health history is visible in this portal', 'sw': 'Historia yako ya afya inaonekana kwenye tovuti hii'},
    'not_linked_short_title':   {'en': 'Not yet linked',              'sw': 'Bado haijaunganishwa'},
    'not_linked_short_sub':     {'en': 'Visit reception to link your medical records', 'sw': 'Fika mapokezi kuunganisha rekodi zako za matibabu'},
    'update_contact_section':   {'en': '✏️ Update Contact Details',   'sw': '✏️ Sasisha Maelezo ya Mawasiliano'},
    'home_address':             {'en': 'Home Address',                'sw': 'Anwani ya Nyumbani'},
    'your_address':             {'en': 'Your address',                'sw': 'Anwani yako'},
    'save_changes_btn':         {'en': '✓ Save Changes',              'sw': '✓ Hifadhi Mabadiliko'},
}


def t(key, **kwargs):
    """Translate `key` into the current session language (defaults to English)."""
    lang = session.get('lang', DEFAULT_LANG)
    entry = TRANSLATIONS.get(key)
    if not entry:
        return key
    text = entry.get(lang, entry.get(DEFAULT_LANG, key))
    if kwargs:
        try:
            text = text.format(**kwargs)
        except Exception:
            pass
    return text


def current_lang():
    return session.get('lang', DEFAULT_LANG)


def register_i18n(app):
    """Call once from app.py: makes t() and current_lang() available in all templates."""
    app.context_processor(lambda: {'t': t, 'current_lang': current_lang()})
