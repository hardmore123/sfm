import numpy as np
from config import C, finalize_pixel_mapping
from world import SceneWorld
from trajectory import euler_to_matrix
from shadow import render_shadow_map
from sonar_render import render_frame

# T0.5 最终验收：海底-only 场景
test_sonar = C.sonar.__class__(
    beam_count=512, range_bin_count=800,
    fov_azimuth_deg=(-65.0, 65.0), fov_elevation_deg=(-20.0, 20.0),
    range_min_m=0.50, range_max_m=10.0,
    speckle_sigma=0.20, noise_floor_db=45.0,
)
test_cfg = C.__class__(
    seed=42, sonar=test_sonar,
    scene=C.scene.__class__(
        pillars=[], cubes=[], spheres=[], rubble=[],
        floor_z_m=0.0, surface_z_m=10.0,
    ),
    traj=C.traj, noise=C.noise, output_dir='.',
)
finalize_pixel_mapping(test_cfg)
world = SceneWorld(test_cfg)

T_wb = np.eye(4)
T_wb[:3, 3] = [-3.0, 5.0, 3.0]
T_wb[:3, :3] = euler_to_matrix(0.0, 0.0, 0.0)

rng = np.random.default_rng(42)
img = render_frame(T_wb, world, test_cfg, shadow_mask=None, n_elev=51, rng=rng)

speckle = rng.normal(1.0, test_sonar.speckle_sigma, img.shape)
speckle = np.clip(speckle, 0.0, None)
noise_floor = 10 ** (-test_sonar.noise_floor_db / 20.0) * 0.001
img_noise = np.abs(rng.normal(0, noise_floor, img.shape))
noise_mean = img_noise.mean()
noise_db = 20*np.log10(noise_mean + 1e-12)

# === T0.5 验收（v3 阶段表 §6.1）===
# A: 海底电平 - 噪声底 >= 10 dB
# C: 阴影区 <= 噪声底 + 3 dB
# B: 海底像素 > 3sigma 占比 >= 80%（仅看 I>0 像素）

all_pixels = img.flatten()
nonzero = all_pixels[all_pixels > 0]
seafloor_mean = all_pixels.mean()
seafloor_db = 20*np.log10(seafloor_mean + 1e-12) if seafloor_mean > 0 else -200

# B: 在 I > 0 像素中 > 3σ 占比
if len(nonzero) > 0:
    above_3sigma_nz = (nonzero > 3 * noise_floor).sum() / len(nonzero)
    below_3sigma_nz = (nonzero <= 3 * noise_floor).sum()
else:
    above_3sigma_nz = 0
    below_3sigma_nz = 0

print('=== T0.5 验收 v3 阶段表 ===')
print('Total pixels:', all_pixels.size)
print('I > 0 pixels (seafloor 命中):', len(nonzero), '(%.1f%%)' % (len(nonzero)/all_pixels.size*100))
print('Seafloor mean: %.4e (%.1f dB)' % (seafloor_mean, seafloor_db))
print('Seafloor - Noise: %.1f dB' % (seafloor_db - noise_db), '[A]', 'PASS' if seafloor_db - noise_db >= 10 else 'FAIL')
print('I>0 中 >3sigma: %.1f%%' % (above_3sigma_nz*100), '[B]', 'PASS' if above_3sigma_nz >= 0.8 else 'FAIL')
print()

# C: 阴影验收 - 渲染一个含目标的图
test_cfg2 = C.__class__(
    seed=42, sonar=test_sonar,
    scene=C.scene.__class__(
        pillars=[(5.0, 5.0, 0.2, 0.8)],
        cubes=[], spheres=[], rubble=[],
        floor_z_m=0.0, surface_z_m=10.0,
    ),
    traj=C.traj, noise=C.noise, output_dir='.',
)
finalize_pixel_mapping(test_cfg2)
world2 = SceneWorld(test_cfg2)
T_wb2 = np.eye(4)
T_wb2[:3, 3] = [-3.0, 5.0, 3.0]
T_wb2[:3, :3] = euler_to_matrix(0.0, 0.0, 0.0)
tm, sm, hm, sl, te = render_shadow_map(T_wb2, world2, test_cfg2, n_elev=101, min_elev_deg=3.0)
rng = np.random.default_rng(42)
img2 = render_frame(T_wb2, world2, test_cfg2, shadow_mask=sm, n_elev=51, rng=rng)
shadow_pixels = img2[sm]
shadow_db = 20*np.log10(shadow_pixels.mean() + 1e-12) if shadow_pixels.size > 0 and shadow_pixels.mean() > 0 else -200
print('Shadow: %.1f dB' % shadow_db, '[C]', 'PASS' if shadow_db <= noise_db + 3 else 'FAIL')

# 综合
all_pass = (seafloor_db - noise_db >= 10) and (above_3sigma_nz >= 0.8) and (shadow_db <= noise_db + 3)
print()
print('=== ALL T0.5:', 'ALL PASS' if all_pass else 'PARTIAL ===')
