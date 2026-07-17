"""
Zero Trust EMR — Training Results Visualisation
Run this AFTER train_model.py to see charts of the model performance.
Author: Alto Dezdel Kiyamba | MUST BCS/25
"""

import numpy as np
import pickle
import json
import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.gridspec import GridSpec

# ── Load model ───────────────────────────────────────────────────────────────
MODEL_DIR   = 'trained_models'
model_path  = os.path.join(MODEL_DIR, 'isolation_forest.pkl')
scaler_path = os.path.join(MODEL_DIR, 'scaler.pkl')
meta_path   = os.path.join(MODEL_DIR, 'model_meta.json')

if not os.path.exists(model_path):
    print("❌ No trained model found. Run train_model.py first.")
    exit(1)

with open(model_path,  'rb') as f: model  = pickle.load(f)
with open(scaler_path, 'rb') as f: scaler = pickle.load(f)
with open(meta_path,   'r') as f: meta   = json.load(f)

print("✅ Model loaded. Generating visualisations...")

# ── Generate test data ────────────────────────────────────────────────────────
rng = np.random.default_rng(99)

# Normal behaviour patterns
normal_day   = rng.normal(loc=[4,0,0,1,0.12,0], scale=[2,0.1,0.05,0.1,0.04,0.01], size=(150,6))
normal_night = rng.normal(loc=[1,0,1,1,0.04,0], scale=[1,0.1,0.05,0.1,0.01,0.05], size=(50,6))
# Anomalous patterns
anomalies    = np.array([
    [30, 5, 1, 4, 0.9, 1],   # mass data access at night
    [0,  8, 0, 6, 0.1, 0],   # many failed logins, multiple IPs
    [25, 0, 1, 1, 0.7, 1],   # very high access rate after midnight
    [15, 3, 1, 3, 0.5, 0],   # moderate anomaly
    [20, 2, 0, 5, 0.6, 0],   # many IPs, high access
])

X_normal = np.clip(np.vstack([normal_day, normal_night]), 0, None)
X_anom   = np.clip(anomalies, 0, None)
X_all    = np.vstack([X_normal, X_anom])

# Scale and score
X_normal_sc = scaler.transform(X_normal)
X_anom_sc   = scaler.transform(X_anom)
X_all_sc    = scaler.transform(X_all)

scores_normal = model.score_samples(X_normal_sc)
scores_anom   = model.score_samples(X_anom_sc)
scores_all    = model.score_samples(X_all_sc)
preds_all     = model.predict(X_all_sc)

def to_risk(s): return np.clip(1-(s+0.5), 0, 1)
risk_normal = to_risk(scores_normal)
risk_anom   = to_risk(scores_anom)
risk_all    = to_risk(scores_all)

# ── Plot ──────────────────────────────────────────────────────────────────────
fig = plt.figure(figsize=(18, 13))
fig.patch.set_facecolor('#F0F4FF')
gs  = GridSpec(3, 3, figure=fig, hspace=0.45, wspace=0.38)

TEAL   = '#00b8b8'
VIOLET = '#7c5cbf'
RED    = '#e8445a'
AMBER  = '#f5a623'
GREEN  = '#00c896'
GREY   = '#cccccc'

# ── Title ──
fig.text(0.5, 0.97,
    'Zero Trust EMR — AI Model Training Results',
    ha='center', va='top', fontsize=16, fontweight='bold', color='#1a1a3e')
fig.text(0.5, 0.945,
    'Algorithm: Isolation Forest (Unsupervised Anomaly Detection)  |  '
    f'Trained: {meta.get("trained_at","N/A")[:10]}  |  '
    f'Samples: {meta.get("training_samples","N/A")}  |  '
    'Author: Alto Dezdel Kiyamba | MUST BCS/25',
    ha='center', va='top', fontsize=9, color='#555555')

# ── Chart 1: Risk score distribution ──
ax1 = fig.add_subplot(gs[0, 0])
ax1.set_facecolor('white')
bins = np.linspace(0, 1, 25)
ax1.hist(risk_normal, bins=bins, color=GREEN,  alpha=0.75, label='Normal behaviour', edgecolor='white')
ax1.hist(risk_anom,   bins=bins, color=RED,    alpha=0.85, label='Anomalous behaviour', edgecolor='white')
ax1.axvline(0.30, color=AMBER,  linestyle='--', linewidth=1.5, label='Low/Medium (0.30)')
ax1.axvline(0.55, color=AMBER,  linestyle=':',  linewidth=1.5, label='Medium/High (0.55)')
ax1.axvline(0.75, color=RED,    linestyle='--', linewidth=1.5, label='High/Critical (0.75)')
ax1.set_title('Risk Score Distribution', fontweight='bold', fontsize=11)
ax1.set_xlabel('Risk Score (0 = normal, 1 = anomalous)')
ax1.set_ylabel('Number of samples')
ax1.legend(fontsize=7)
ax1.grid(axis='y', alpha=0.3)

# ── Chart 2: Feature importance (mean absolute deviation per feature) ──
ax2 = fig.add_subplot(gs[0, 1])
ax2.set_facecolor('white')
feature_names = ['Records\nAccessed', 'Failed\nLogins', 'Off\nHours', 'Distinct\nIPs', 'Actions\nper Min', 'After\nMidnight']
importance = np.abs(X_anom_sc.mean(axis=0) - X_normal_sc.mean(axis=0))
colours = [TEAL, RED, AMBER, VIOLET, GREEN, '#e8445a']
bars = ax2.bar(feature_names, importance, color=colours, edgecolor='white', linewidth=0.5)
ax2.set_title('Feature Discriminative Power\n(Anomaly vs Normal mean diff)', fontweight='bold', fontsize=11)
ax2.set_ylabel('Mean absolute difference')
ax2.grid(axis='y', alpha=0.3)
for bar, val in zip(bars, importance):
    ax2.text(bar.get_x()+bar.get_width()/2, bar.get_height()+0.02, f'{val:.2f}',
             ha='center', va='bottom', fontsize=8, fontweight='bold')

# ── Chart 3: Risk levels pie chart ──
ax3 = fig.add_subplot(gs[0, 2])
ax3.set_facecolor('white')
all_risks = np.concatenate([risk_normal, risk_anom])
lvl_counts = {
    'Low\n(<0.30)':      (all_risks <  0.30).sum(),
    'Medium\n(0.30-0.55)':(( all_risks >= 0.30) & (all_risks < 0.55)).sum(),
    'High\n(0.55-0.75)': ((all_risks >= 0.55) & (all_risks < 0.75)).sum(),
    'Critical\n(≥0.75)': (all_risks >= 0.75).sum(),
}
pie_cols = [GREEN, AMBER, RED, VIOLET]
wedges, texts, autotexts = ax3.pie(
    lvl_counts.values(), labels=lvl_counts.keys(),
    colors=pie_cols, autopct='%1.1f%%',
    startangle=90, pctdistance=0.75,
    wedgeprops={'edgecolor':'white','linewidth':2}
)
for t in autotexts: t.set_fontsize(8); t.set_fontweight('bold')
ax3.set_title('Risk Level Distribution\n(All samples)', fontweight='bold', fontsize=11)

# ── Chart 4: Anomaly score over simulated time ──
ax4 = fig.add_subplot(gs[1, :2])
ax4.set_facecolor('white')
time_points = np.arange(len(risk_all))
normal_mask = np.array([1]*len(risk_normal)+[0]*len(risk_anom), dtype=bool)
anom_mask   = ~normal_mask
ax4.fill_between(time_points, 0, 0.30, alpha=0.08, color=GREEN,  label='Low zone')
ax4.fill_between(time_points, 0.30, 0.55, alpha=0.08, color=AMBER, label='Medium zone')
ax4.fill_between(time_points, 0.55, 0.75, alpha=0.08, color=RED,   label='High zone')
ax4.fill_between(time_points, 0.75, 1.00, alpha=0.08, color=VIOLET,label='Critical zone')
ax4.scatter(time_points[normal_mask], risk_all[normal_mask], c=GREEN,  s=12, alpha=0.6, label='Normal', zorder=3)
ax4.scatter(time_points[anom_mask],   risk_all[anom_mask],   c=RED,    s=60, alpha=0.9, label='Anomaly', marker='^', zorder=4)
ax4.axhline(0.35, color=TEAL,   linestyle='--', linewidth=1.5, label='MFA trigger (0.35)')
ax4.axhline(0.55, color=AMBER,  linestyle='--', linewidth=1.5, label='High risk (0.55)')
ax4.set_title('Risk Score Timeline — Normal vs Anomalous Sessions', fontweight='bold', fontsize=11)
ax4.set_xlabel('Session sample index')
ax4.set_ylabel('Risk Score')
ax4.set_ylim(0, 1.05)
ax4.legend(fontsize=8, ncol=4)
ax4.grid(alpha=0.3)

# ── Chart 5: Decision boundary (2D: records vs failed logins) ──
ax5 = fig.add_subplot(gs[1, 2])
ax5.set_facecolor('white')
xx,yy=np.meshgrid(np.linspace(-1,35,80), np.linspace(-1,10,80))
grid_raw = np.c_[xx.ravel(), yy.ravel(),
                 np.ones(xx.ravel().shape)*0.5,
                 np.ones(xx.ravel().shape)*1,
                 np.ones(xx.ravel().shape)*0.15,
                 np.zeros(xx.ravel().shape)]
grid_sc  = scaler.transform(grid_raw)
Z = model.score_samples(grid_sc).reshape(xx.shape)
ax5.contourf(xx, yy, Z, levels=15, cmap='RdYlGn', alpha=0.7)
ax5.scatter(X_normal[:,0], X_normal[:,1], c=GREEN, s=12, alpha=0.6, label='Normal', zorder=3)
ax5.scatter(X_anom[:,0],   X_anom[:,1],   c=RED,   s=80, marker='^', alpha=0.9, label='Anomaly', zorder=4)
ax5.set_title('Decision Boundary\n(Records vs Failed Logins)', fontweight='bold', fontsize=11)
ax5.set_xlabel('Records Accessed (per hour)')
ax5.set_ylabel('Failed Login Attempts')
ax5.legend(fontsize=8)

# ── Chart 6: Model parameters table ──
ax6 = fig.add_subplot(gs[2, 0])
ax6.set_facecolor('white')
ax6.axis('off')
params = [
    ['Algorithm',       'Isolation Forest'],
    ['Trees (n_estimators)', '200'],
    ['Contamination',   '8% (0.08)'],
    ['Features',        '6 behavioural'],
    ['Scaling',         'StandardScaler'],
    ['MFA trigger',     'Risk ≥ 0.35'],
    ['High risk',       'Risk ≥ 0.55'],
    ['Training samples', str(meta.get('training_samples','N/A'))],
    ['Test samples',    str(meta.get('test_samples','N/A'))],
    ['Avg risk (train)',str(meta.get('avg_risk_train','N/A'))],
]
tbl = ax6.table(cellText=params, colLabels=['Parameter','Value'],
                cellLoc='left', loc='center',
                colWidths=[0.55,0.45])
tbl.auto_set_font_size(False); tbl.set_fontsize(9)
tbl[0,0].set_facecolor(VIOLET); tbl[0,0].set_text_props(color='white',fontweight='bold')
tbl[0,1].set_facecolor(VIOLET); tbl[0,1].set_text_props(color='white',fontweight='bold')
for i in range(1,len(params)+1):
    bg = '#F8F8FF' if i%2==0 else 'white'
    tbl[i,0].set_facecolor(bg); tbl[i,1].set_facecolor(bg)
ax6.set_title('Model Parameters', fontweight='bold', fontsize=11, pad=10)

# ── Chart 7: Anomaly detection accuracy bar ──
ax7 = fig.add_subplot(gs[2, 1])
ax7.set_facecolor('white')
detected    = (model.predict(X_anom_sc)   == -1).sum()
true_normal = (model.predict(X_normal_sc) ==  1).sum()
categories  = ['Normal\nCorrectly Kept', 'Anomalies\nDetected', 'Anomalies\nMissed', 'Normal\nFalse Alarms']
values      = [true_normal, detected, len(X_anom)-detected, len(X_normal)-true_normal]
colours2    = [GREEN, TEAL, RED, AMBER]
bars2       = ax7.bar(categories, values, color=colours2, edgecolor='white', linewidth=0.5)
ax7.set_title('Detection Performance', fontweight='bold', fontsize=11)
ax7.set_ylabel('Count')
ax7.grid(axis='y', alpha=0.3)
for bar, val in zip(bars2, values):
    ax7.text(bar.get_x()+bar.get_width()/2, bar.get_height()+0.1, str(val),
             ha='center', va='bottom', fontsize=10, fontweight='bold')
detect_rate = detected/len(X_anom)*100 if len(X_anom) > 0 else 0
ax7.set_title(f'Detection Performance\nAnomalies Detected: {detect_rate:.0f}%', fontweight='bold', fontsize=11)

# ── Chart 8: Feature heatmap (normal vs anomalous) ──
ax8 = fig.add_subplot(gs[2, 2])
ax8.set_facecolor('white')
feat_names_short = ['Records', 'Failed\nLogins', 'Off\nHours', 'Multi\nIPs', 'Speed', 'Midnight']
norm_means = X_normal.mean(axis=0)
anom_means = X_anom.mean(axis=0)
x_idx = np.arange(len(feat_names_short))
w = 0.35
ax8.bar(x_idx-w/2, norm_means, w, color=GREEN, label='Normal',   edgecolor='white')
ax8.bar(x_idx+w/2, anom_means, w, color=RED,   label='Anomaly',  edgecolor='white', alpha=0.85)
ax8.set_xticks(x_idx); ax8.set_xticklabels(feat_names_short, fontsize=8)
ax8.set_title('Average Feature Values\nNormal vs Anomalous', fontweight='bold', fontsize=11)
ax8.set_ylabel('Mean value')
ax8.legend(fontsize=9); ax8.grid(axis='y', alpha=0.3)

# ── Footer ──
fig.text(0.5, 0.01,
    'Zero Trust EMR  |  Isolation Forest Anomaly Detection  |  '
    'Alto Dezdel Kiyamba  |  MUST BCS/25  |  Supervisor: Ms. Prisca Maro',
    ha='center', va='bottom', fontsize=8, color='#999999')

plt.savefig('trained_models/training_results.png', dpi=150, bbox_inches='tight',
            facecolor=fig.get_facecolor())
print("✅ Chart saved: trained_models/training_results.png")
plt.savefig('trained_models/training_results_hd.png', dpi=300, bbox_inches='tight',
            facecolor=fig.get_facecolor())
print("✅ HD chart saved: trained_models/training_results_hd.png")
plt.close()
print("\n📊 Open trained_models/training_results.png to see your model performance charts.")
