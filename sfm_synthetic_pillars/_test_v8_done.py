import numpy as np
from config import C, finalize_pixel_mapping
from world import SceneWorld
from trajectory import euler_to_matrix
from shadow import render_shadow_map
from sonar_render import render_frame

# 1. 海底-only 场景（验证 A, B, C 三项）
test_sonar = C.sonar.__class__(
    beam_count=512, range_bin_count=800,
    fov_azimuth_deg=(-65.0, 65.0), fov_elevation_deg=(-20.0, 20.0),
    range_min_m=0.50, range_max_m=10.0,
    speckle_sigma=0.20, noise_floor_db=45.0,
)
test_cfg = C.__class__(
    seed=42, sonar=test_sonar,
    scene=C.scene.__class__(
        pillars=[],  # 无目标
        cubes=[], spheres=[], rubble=[],
        floor_z_m=0.0, surface_z_m=10.0,
    ),
    traj=C.traj, noise=C.noise, output_dir='.',
)
finalize_pixel_mapping(test_cfg)
world = SceneWorld(test_cfg)

T_wb = np.eye(4)
T_wb[:3, 3] = [-3.0, 5.0, 3.0]
T_wb[:3, :3] = euler_to_matrix(0.0, 0.0, 0.0)

# 不用 shadow mask（无目标）
rng = np.random.default_rng(42)
img = render_frame(T_wb, world, test_cfg, shadow_mask=None, n_elev=51, rng=rng)

# Pure noise
speckle = rng.normal(1.0, test_sonar.speckle_sigma, img.shape)
speckle = np.clip(speckle, 0.0, None)
noise_floor = 10 ** (-test_sonar.noise_floor_db / 20.0) * 0.001
img_noise = np.abs(rng.normal(0, noise_floor, img.shape))
noise_mean = img_noise.mean()
noise_db = 20*np.log10(noise_mean + 1e-12)

seafloor_pixels = img.flatten()
seafloor_mean = seafloor_pixels.mean()
seafloor_db = 20*np.log10(seafloor_mean + 1e-12) if seafloor_mean > 0 else -200
above_3sigma = (seafloor_pixels > 3 * noise_floor).sum() / seafloor_pixels.size
# 看 I 分布
print('Seafloor pixels: %d, all > 0: %d' % (seafloor_pixels.size, (seafloor_pixels > 0).sum()))
print('  percentile 1: %.2e' % np.percentile(seafloor_pixels, 1))
print('  percentile 50: %.2e' % np.percentile(seafloor_pixels, 50))
print('  percentile 95: %.2e' % np.percentile(seafloor_pixels, 95))
print('  3sigma = %.2e' % (3*noise_floor))
print('  fraction > 3sigma: %.1f%%' % (above_3sigma*100))
print('  Seafloor - Noise: %.1f dB' % (seafloor_db - noise_db))
print()

# T0.5 验收（B 在"无目标"场景下，所有像素都是海底或噪声）
# 大部分像素 I 小是因为 r 大 + sin(θ) 小（声呐 z=3，看 floor at z=0 在 -7° 到 -20° 之间）
# 当 z_s 更高时，d_horiz 范围更大，更多像素有强 I

# 改用 z_s=5 + 下俯 15度 + 量程 25（看 floor 范围大）
test_sonar2 = C.sonar.__class__(
    beam_count=512, range_bin_count=800,
    fov_azimuth_deg=(-65.0, 65.0), fov_elevation_deg=(-20.0, 20.0),
    range_min_m=0.50, range_max_m=20.0,
    speckle_sigma=0.20, noise_floor_db=45.0,
)
test_cfg2 = C.__class__(
    seed=42, sonar=test_sonar2,
    scene=C.scene.__class__(pillars=[], cubes=[], spheres=[], rubble=[],
                              floor_z_m=0.0, surface_z_m=10.0),
    traj=C.traj, noise=C.noise, output_dir='.',
)
finalize_pixel_mapping(test_cfg2)
world2 = SceneWorld(test_cfg2)
T_wb2 = np.eye(4)
T_wb2[:3, 3] = [-3.0, 5.0, 5.0]  # z_s = 5
T_wb2[:3, :3] = euler_to_matrix(0.0, np.deg2rad(-15.0), 0.0)  # 下俯 15

rng = np.random.default_rng(42)
img2 = render_frame(T_wb2, world2, test_cfg2, shadow_mask=None, n_elev=101, rng=rng)
seafloor_pixels2 = img2.flatten()
seafloor_mean2 = seafloor_pixels2.mean()
seafloor_db2 = 20*np.log10(seafloor_mean2 + 1e-12) if seafloor_mean2 > 0 else -200
above_3sigma2 = (seafloor_pixels2 > 3 * noise_floor).sum() / seafloor_pixels2.size
print('z_s=5, 下俯 15 deg, range=20:')
print('  Seafloor mean: %.4e (%.1f dB)' % (seafloor_mean2, seafloor_db2))
print('  Seafloor - Noise: %.1f dB' % (seafloor_db2 - noise_db))
print('  3sigma = %.2e' % (3*noise_floor))
print('  fraction > 3sigma: %.1f%%' % (above_3sigma2*100))
print('  percentile 50: %.2e' % np.percentile(seafloor_pixels2, 50))
print('  percentile 1: %.2e' % np.percentile(seafloor_pixels2, 1))
