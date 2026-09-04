import numpy as np
from config import C, finalize_pixel_mapping
from world import SceneWorld
from trajectory import euler_to_matrix
from sonar_render import render_frame

test_sonar = C.sonar.__class__(
    beam_count=512, range_bin_count=800,
    fov_azimuth_deg=(-65.0, 65.0), fov_elevation_deg=(-20.0, 20.0),
    range_min_m=0.20, range_max_m=6.00,
    speckle_sigma=0.20, noise_floor_db=45.0,
)
test_cfg = C.__class__(
    seed=42, sonar=test_sonar,
    scene=C.scene.__class__(
        pillars=[],  # 排除目标干扰
        cubes=[], spheres=[], rubble=[],
        floor_z_m=0.0, surface_z_m=10.0,
    ),
    traj=C.traj, noise=C.noise, output_dir='.',
)
finalize_pixel_mapping(test_cfg)
world = SceneWorld(test_cfg)

T_wb = np.eye(4)
T_wb[:3, 3] = [-3.0, 5.0, 1.5]
T_wb[:3, :3] = euler_to_matrix(0.0, 0.0, 0.0)

rng = np.random.default_rng(42)
img = render_frame(T_wb, world, test_cfg, shadow_mask=None, n_elev=101, rng=rng)

# 看图像分布
print('image shape:', img.shape)
print('image max:', img.max(), 'min:', img.min(), 'mean:', img.mean())
print('image 非零像素数:', (img > 0).sum())
# 看非零像素的分布
nonzero = img[img > 0]
print('非零像素数:', len(nonzero))
print('非零像素 I 分布:')
for p in [1, 5, 10, 25, 50, 75, 90, 95, 99]:
    print(f'  {p}% 分位: {np.percentile(nonzero, p):.4e}')
