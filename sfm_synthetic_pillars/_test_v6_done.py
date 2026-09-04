import numpy as np
from config import C, finalize_pixel_mapping
from world import SceneWorld
from trajectory import euler_to_matrix
from shadow import render_shadow_map
from sonar_render import render_frame

# P1 建议的几何：z_s=4-5, 下俯 15-20度
test_sonar = C.sonar.__class__(
    beam_count=512, range_bin_count=800,
    fov_azimuth_deg=(-65.0, 65.0), fov_elevation_deg=(-20.0, 20.0),
    range_min_m=0.50, range_max_m=15.0,  # 放宽
    speckle_sigma=0.20, noise_floor_db=45.0,
)
test_cfg = C.__class__(
    seed=42, sonar=test_sonar,
    scene=C.scene.__class__(
        pillars=[(8.0, 5.0, 0.2, 1.0)],  # 目标在 8m 处
        cubes=[], spheres=[], rubble=[],
        floor_z_m=0.0, surface_z_m=10.0,
    ),
    traj=C.traj, noise=C.noise, output_dir='.',
)
finalize_pixel_mapping(test_cfg)
world = SceneWorld(test_cfg)

# 声呐在 (-3, 5, 4)，下俯 15 度
T_wb = np.eye(4)
T_wb[:3, 3] = [-3.0, 5.0, 4.0]
T_wb[:3, :3] = euler_to_matrix(0.0, np.deg2rad(-15.0), 0.0)  # 下俯 15 度

tm, sm, hm, sl, te = render_shadow_map(T_wb, world, test_cfg, n_elev=101, min_elev_deg=3.0)
print('target:', tm.sum(), 'shadow:', sm.sum())

rng = np.random.default_rng(42)
img = render_frame(T_wb, world, test_cfg, shadow_mask=sm, n_elev=51, rng=rng)

# Pure noise
speckle = rng.normal(1.0, test_sonar.speckle_sigma, img.shape)
speckle = np.clip(speckle, 0.0, None)
noise_floor = 10 ** (-test_sonar.noise_floor_db / 20.0) * 0.001
img_noise = np.abs(rng.normal(0, noise_floor, img.shape))
noise_mean = img_noise.mean()
noise_db = 20*np.log10(noise_mean + 1e-12)

all_mask = tm | sm
seafloor_mask = ~all_mask
seafloor_pixels = img[seafloor_mask]
seafloor_mean = seafloor_pixels.mean()
seafloor_db = 20*np.log10(seafloor_mean + 1e-12)
above_3sigma = (seafloor_pixels > 3 * noise_floor).sum() / seafloor_pixels.size

shadow_pixels = img[sm]
shadow_db = 20*np.log10(shadow_pixels.mean() + 1e-12) if shadow_pixels.size > 0 else -200

print()
print('=== T0.5 验收（z_s=4, 下俯 15, 几何升级）===')
print('seafloor non-zero: %d / %d (%.1f%%)' % ((seafloor_pixels > 0).sum(), seafloor_pixels.size, (seafloor_pixels > 0).mean()*100))
print('Noise: %.4e (%.1f dB)' % (noise_mean, noise_db))
print('Seafloor: %.4e (%.1f dB)' % (seafloor_mean, seafloor_db))
print('Seafloor - Noise: %.1f dB' % (seafloor_db - noise_db))
print('Seafloor > 3sigma: %.1f%%' % (above_3sigma*100))
print('Shadow: %.1f dB' % shadow_db)
print()
pass_a = (seafloor_db - noise_db) >= 10
pass_b = above_3sigma >= 0.8
pass_c = shadow_db <= noise_db + 3
print('A:', 'PASS' if pass_a else 'FAIL', 'B:', 'PASS' if pass_b else 'FAIL', 'C:', 'PASS' if pass_c else 'FAIL')
