import sys, os
sys.path.insert(0, r'F:\sfm\sfm_synthetic_pillars')
import numpy as np
from _R_x6_aykin_carve_v2 import make_binary_form_v2

scene_dir = r'F:/sfm/sfm_synthetic_pillars/scene_set_v2/S1_single_well_constrained'
sonar_imgs = np.load(os.path.join(scene_dir, 'gt/sonar_images.npy'))
target_masks = np.load(os.path.join(scene_dir, 'gt/target_masks.npy'))
N, H, W = sonar_imgs.shape
range_axis = np.linspace(0.5, 25.0, H)

# 比较 V1 (target 邻域) vs V2 (auto)
for n in [0, 5, 10, 15, 19]:
    form_v1 = target_masks[n]
    form_v2 = make_binary_form_v2(sonar_imgs[n], n_std=3.0, erosion=0,
                                    r_min_m=2.0, r_max_m=18.0, range_axis=range_axis)
    # V1 用 binary_dilation 11x11 iter=2
    from scipy.ndimage import binary_dilation
    struct = np.ones((11, 11), dtype=bool)
    form_v1_dil = binary_dilation(form_v1, structure=struct, iterations=2)
    # 每根 beam 的最远 FORM 行
    front_v1 = []
    front_v2 = []
    for th in range(W):
        rows_v1 = np.where(form_v1_dil[:, th])[0]
        if len(rows_v1) > 0:
            front_v1.append(range_axis[rows_v1.max()])
        rows_v2 = np.where(form_v2[:, th])[0]
        if len(rows_v2) > 0:
            front_v2.append(range_axis[rows_v2.max()])
    print(f'frame {n}: V1(dil) front range [{min(front_v1):.1f}, {max(front_v1):.1f}]m, '
          f'V2(auto) front range [{min(front_v2):.1f}, {max(front_v2):.1f}]m, '
          f'V1 mean front {np.mean(front_v1):.1f}m, V2 mean front {np.mean(front_v2):.1f}m')
