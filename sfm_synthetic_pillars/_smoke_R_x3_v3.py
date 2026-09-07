import sys, os, time
sys.path.insert(0, r'F:\sfm\BA代码')
sys.path.insert(0, r'F:\sfm\sfm_synthetic_pillars')
import numpy as np
from _R_x3_full_ba_v3 import load_heave_h12, run_ba_once_v3

print('load...')
data = load_heave_h12()
landmarks, poses6, obs_by_lm, obs_list, odom_rel, calib, well_mask, base_frame, sigma_rho, sigma_theta, sigma_Pz_th = data
print(f'shape: {landmarks.shape}, well: {int(well_mask.sum())}')

# 5 组各 1 iter
weights_sets = [
    ('A_default', {'prior': 1000.0, 'odomT': 100.0, 'odomR': 100.0, 'sonar': 1.0}),
    ('B_balanced', {'prior': 1.0, 'odomT': 1.0, 'odomR': 1.0, 'sonar': 1.0}),
    ('C_sonar10', {'prior': 1.0, 'odomT': 1.0, 'odomR': 1.0, 'sonar': 10.0}),
    ('D_sonar100', {'prior': 1.0, 'odomT': 1.0, 'odomR': 1.0, 'sonar': 100.0}),
    ('E_pure_sonar', {'prior': 0.0, 'odomT': 0.0, 'odomR': 0.0, 'sonar': 1.0}),
]
for label, w in weights_sets:
    t0 = time.time()
    try:
        ba, r = run_ba_once_v3(landmarks, poses6, obs_by_lm, obs_list, odom_rel, calib, well_mask, base_frame, sigma_rho, sigma_theta, w, add_noise=True, seed=42)
        print(f'{label}: {time.time()-t0:.1f}s, z[:3]={r["world"][:3, 2]}')
    except Exception as e:
        print(f'{label}: FAIL {e}')

# GT
print(f'GT z[:3]: {landmarks[:3, 2]}')
