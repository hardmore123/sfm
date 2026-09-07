import sys, os
sys.path.insert(0, r'F:\sfm\sfm_synthetic_pillars')
import numpy as np
from _R_x6_aykin_carve_v2 import make_binary_form_v2

# 加载 S1 sonar
scene_dir = r'F:/sfm/sfm_synthetic_pillars/scene_set_v2/S1_single_well_constrained'
sonar_imgs = np.load(os.path.join(scene_dir, 'gt/sonar_images.npy'))
N, H, W = sonar_imgs.shape
print(f'sonar: {sonar_imgs.shape}')

# FORM 分布
n_total = 0
n_form = 0
for n in range(N):
    form = make_binary_form_v2(sonar_imgs[n], n_std=1.5, erosion=0)
    n_total += form.size
    n_form += form.sum()
print(f'FORM auto: {n_form/n_total*100:.2f}% of pixels')

# 看距离分布：FORM 在什么距离
for n in [0, 10, 19]:
    form = make_binary_form_v2(sonar_imgs[n], n_std=1.5, erosion=0)
    rows_with_form = np.where(form.any(axis=1))[0]
    if len(rows_with_form) > 0:
        # range_axis 0.5-25m
        r_min = 0.5 + rows_with_form.min() / (H - 1) * (25 - 0.5)
        r_max = 0.5 + rows_with_form.max() / (H - 1) * (25 - 0.5)
        print(f'frame {n}: FORM 在距离 [{r_min:.1f}, {r_max:.1f}]m, n_pixels={form.sum()}')
    else:
        print(f'frame {n}: no FORM')
