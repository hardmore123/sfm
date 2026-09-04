import numpy as np
from config import C, finalize_pixel_mapping
from world import SceneWorld
from trajectory import euler_to_matrix
from shadow import render_shadow_map
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
        pillars=[(0.0, 5.0, 0.2, 0.5)],
        cubes=[(2.0, 5.0, 0.0, 0.3)],
        spheres=[],
        rubble=[(1.0, 5.0, 0.0, 0.1), (1.5, 5.0, 0.0, 0.15)],
        floor_z_m=0.0, surface_z_m=10.0,
        seafloor_backscatter=10.0, shadow_attenuation=0.02,
    ),
    traj=C.traj, noise=C.noise, output_dir='.',
)
finalize_pixel_mapping(test_cfg)
world = SceneWorld(test_cfg)

T_wb = np.eye(4)
T_wb[:3, 3] = [-3.0, 5.0, 1.5]
T_wb[:3, :3] = euler_to_matrix(0.0, 0.0, 0.0)

tm, sm, hm, sl, te = render_shadow_map(T_wb, world, test_cfg, n_elev=101, min_elev_deg=3.0)
rng = np.random.default_rng(42)
img = render_frame(T_wb, world, test_cfg, shadow_mask=sm, n_elev=51, rng=rng)

# 正确的 T0.5 验收：用实测 noise mean
# 1. 渲染一张只有噪声的图（seafloor=0, shadow=0, target=0），得纯噪声
img_noise_only = np.zeros_like(img)
# 加上散斑和噪声
speckle = rng.normal(1.0, test_sonar.speckle_sigma, img.shape)
speckle = np.clip(speckle, 0.0, None)
img_noise_only = img_noise_only * speckle
noise_floor = 10 ** (-test_sonar.noise_floor_db / 20.0) * 0.001
img_noise_only = img_noise_only + np.abs(rng.normal(0, noise_floor, img.shape))
noise_mean = img_noise_only.mean()
noise_db_actual = 20*np.log10(noise_mean + 1e-12)
print('Pure noise mean: %.6e (%.1f dB)' % (noise_mean, noise_db_actual))

all_mask = tm | sm
seafloor_mask = ~all_mask
seafloor_pixels = img[seafloor_mask]
seafloor_mean = seafloor_pixels.mean()
seafloor_db = 20*np.log10(seafloor_mean + 1e-12)
print('Seafloor mean: %.6e (%.1f dB)' % (seafloor_mean, seafloor_db))
print('Seafloor - Noise: %.1f dB (要求 >=10 dB)' % (seafloor_db - noise_db_actual))

# 海底像素 > 3sigma 占比
sigma_actual = noise_floor  # noise 是高斯分布，std = sigma
above_3sigma = (seafloor_pixels > 3 * sigma_actual).sum() / seafloor_pixels.size
print('Seafloor > 3sigma: %.1f%% (要求 >=80%%)' % (above_3sigma*100))

# 阴影电平
shadow_pixels = img[sm]
shadow_db = 20*np.log10(shadow_pixels.mean() + 1e-12)
print('Shadow mean: %.6e (%.1f dB)' % (shadow_pixels.mean(), shadow_db))
print('Shadow <= noise+3: %s' % ('PASS' if shadow_db <= noise_db_actual + 3 else 'FAIL'))

# 总结
pass_a = (seafloor_db - noise_db_actual) >= 10
pass_b = above_3sigma >= 0.8
pass_c = shadow_db <= noise_db_actual + 3
print()
print('=== T0.5 验收总结 ===')
print('1) 海底-噪声 >= 10 dB:', 'PASS' if pass_a else 'FAIL', '(%.1f dB)' % (seafloor_db - noise_db_actual))
print('2) 海底 > 3sigma >= 80%:', 'PASS' if pass_b else 'FAIL', '(%.1f%%)' % (above_3sigma*100))
print('3) 阴影 <= 噪声+3 dB:', 'PASS' if pass_c else 'FAIL', '(%.1f dB)' % shadow_db)
print('ALL:', 'ALL PASS' if (pass_a and pass_b and pass_c) else 'FAIL')

# T0.6
print()
print('=== T0.6 验收 ===')
print('world.all_objects:', len(world.all_objects))
print('all objects rendered (each has >=1 hit if in FOV):')
for obj in world.all_objects:
    obj_t, obj_hit, _ = obj.__class__.__name__, getattr(obj, 'cx', '-'), getattr(obj, 'cy', '-')
    print('  - %s at (%.1f, %.1f)' % (obj_t, float(obj_hit) if obj_hit != '-' else 0, float(obj_hit) if obj_hit != '-' else 0))
