import sys, os
sys.path.insert(0, r'F:\sfm\sfm_synthetic_pillars')
import numpy as np
from _R_x6_aykin_carve_v2 import make_binary_form_v2, voxel_carve_hard_v2

scene_dir = r'F:/sfm/sfm_synthetic_pillars/scene_set_v2/S1_single_well_constrained'
poses_se3 = np.load(os.path.join(scene_dir, 'gt/poses_gt.npy'))
sonar_imgs = np.load(os.path.join(scene_dir, 'gt/sonar_images.npy'))
surface_pts = np.load(os.path.join(scene_dir, 'gt/surface_points.npy'))
N, H, W = sonar_imgs.shape
print(f'sonar: {N}x{H}x{W}, GT surface: {surface_pts.shape}')

# FORM auto
form_masks = np.zeros((N, H, W), dtype=bool)
for n in range(N):
    form_masks[n] = make_binary_form_v2(sonar_imgs[n], n_std=3.0, erosion=0)

# 选 6 帧
n_poses = 6
sel = np.linspace(0, N-1, n_poses).astype(int)
poses_sel = poses_se3[sel]
form_sel = form_masks[sel]

range_axis = np.linspace(0.5, 25.0, H)
beam_axis = np.linspace(-np.deg2rad(15), np.deg2rad(15), W)
fov_elev = np.deg2rad(17)

voxel_origin = np.array([-0.6, -0.6, 0.0])
n_voxels = (12, 12, 30)
voxel_size = 0.1

carved = voxel_carve_hard_v2(poses_sel, form_sel, voxel_origin, voxel_size, n_voxels,
                              range_axis, beam_axis, np.deg2rad(30), fov_elev)
n_carved = carved.sum()
print(f'carved: {n_carved}/{np.prod(n_voxels)} = {n_carved/np.prod(n_voxels)*100:.1f}%')

# 分布
x = voxel_origin[0] + np.arange(n_voxels[0]) * voxel_size
y = voxel_origin[1] + np.arange(n_voxels[1]) * voxel_size
z = voxel_origin[2] + np.arange(n_voxels[2]) * voxel_size
X, Y, Z = np.meshgrid(x, y, z, indexing='ij')
xs, ys, zs = X[carved], Y[carved], Z[carved]
print(f'carved z 范围: [{zs.min():.2f}, {zs.max():.2f}]')
print(f'carved xy 范围: x=[{xs.min():.2f}, {xs.max():.2f}], y=[{ys.min():.2f}, {ys.max():.2f}]')
print(f'GT z 范围: [{surface_pts[:,2].min():.2f}, {surface_pts[:,2].max():.2f}]')

# 1) 限制 elev（去掉 elev 接近 0 区域，海底散射）
# 重新跑 carve with stricter elev
carved_elev = voxel_carve_hard_v2(poses_sel, form_sel, voxel_origin, voxel_size, n_voxels,
                                    range_axis, beam_axis, np.deg2rad(30), np.deg2rad(8))  # 严到 8°
n_elev = carved_elev.sum()
print(f'\nwith fov_elev=8deg: carved {n_elev} ({n_elev/np.prod(n_voxels)*100:.1f}%)')
