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
print('image: max=%.4f mean=%.6f' % (img.max(), img.mean()))

noise_sigma = 10 ** (-test_sonar.noise_floor_db / 20.0) * 0.001
all_mask = tm | sm
seafloor_mask = ~all_mask
seafloor_pixels = img[seafloor_mask]
above_3sigma = (seafloor_pixels > 3 * noise_sigma).sum() / seafloor_pixels.size
seafloor_mean = seafloor_pixels.mean()
seafloor_db = 20*np.log10(seafloor_mean + 1e-12)
noise_db = -test_sonar.noise_floor_db
shadow_pixels = img[sm]
shadow_db = 20*np.log10(shadow_pixels.mean() + 1e-12)

print()
print('=== T0.5 验收 ===')
print('海底像素:', seafloor_mask.sum(), '(%.1f%%)' % (seafloor_mask.mean()*100))
print('海底 > 3sigma: %.1f%% (要求 >=80%%) %s' % (above_3sigma*100, 'PASS' if above_3sigma >= 0.8 else 'FAIL'))
print('海底电平: %.6f = %.1f dB' % (seafloor_mean, seafloor_db))
print('海底-噪声底: %.1f dB (要求 >=10 dB) %s' % (seafloor_db - noise_db, 'PASS' if seafloor_db - noise_db >= 10 else 'FAIL'))
print('阴影电平: %.1f dB (要求 <= %.1f dB) %s' % (shadow_db, noise_db+3, 'PASS' if shadow_db <= noise_db+3 else 'FAIL'))
all_pass = above_3sigma >= 0.8 and seafloor_db - noise_db >= 10 and shadow_db <= noise_db+3
print('all 3 T0.5 验收:', 'ALL PASS' if all_pass else 'FAIL')

# 验证 立方体也可见
print()
print('=== T0.6 验证：立方体/散石有目标像素 ===')
# 立方在 (2, 5)，散石在 (1, 5), (1.5, 5)
# 看图中最强像素位置
max_idx = np.unravel_index(img.argmax(), img.shape)
print('img max at (row, col) =', max_idx, 'val =', img.max())
threshold = np.percentile(img, 99)
strong = (img > threshold).sum()
print('强像素数 (>99 分位):', strong)
