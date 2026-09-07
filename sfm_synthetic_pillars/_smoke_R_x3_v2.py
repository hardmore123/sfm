import sys, os, time
sys.path.insert(0, r'F:\sfm\BA代码')
sys.path.insert(0, r'F:\sfm\sfm_synthetic_pillars')
import numpy as np
from _R_x3_full_ba_v2 import load_heave_h12_for_ba_v2, run_ba_once_v2

print('load...')
landmarks, poses6, obs_by_lm, obs_list, odom_rel, calib, well_mask, base_frame, sigma_rho, sigma_theta = load_heave_h12_for_ba_v2()
print(f'landmarks: {landmarks.shape}, well: {int(well_mask.sum())}, obs_list: {len(obs_list)}')

print()
print('A. lmprior=100 (bug) 1 iter:')
t0 = time.time()
ba, r = run_ba_once_v2(landmarks, poses6, obs_by_lm, obs_list, odom_rel, calib, well_mask, base_frame, sigma_rho, sigma_theta, lmprior=100.0, add_noise=True, seed=42)
print('  耗时', round(time.time()-t0, 1), 's, BA z[:3]:', r['world'][:3, 2])

print()
print('B. lmprior=0 (fix) 1 iter:')
t0 = time.time()
ba, r = run_ba_once_v2(landmarks, poses6, obs_by_lm, obs_list, odom_rel, calib, well_mask, base_frame, sigma_rho, sigma_theta, lmprior=0.0, add_noise=True, seed=42)
print('  耗时', round(time.time()-t0, 1), 's, BA z[:3]:', r['world'][:3, 2])

print()
print('GT z[:3]:', landmarks[:3, 2])
