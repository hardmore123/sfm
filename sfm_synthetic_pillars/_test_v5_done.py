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
img = render_frame(T_wb, world, test_cfg, shadow_mask=sm, n_lev=51, rng=rng) if False else render_frame(T_wb, world, test_cfg, shadow_mask=sm, n_elev=51, rng=rng)

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
shadow_db = 20*np.log10(shadow_pixels.mean() + 1e-12)

print('Noise mean: %.4e (%.1f dB)' % (noise_mean, noise_db))
print('Seafloor mean: %.4e (%.1f dB)' % (seafloor_mean, seafloor_db))
print('Seafloor - Noise: %.1f dB' % (seafloor_db - noise_db))
print('Seafloor > 3sigma: %.1f%%' % (above_3sigma*100))
print('Shadow: %.1f dB' % shadow_db)

pass_a = (seafloor_db - noise_db) >= 10
pass_b = above_3sigma >= 0.8
pass_c = shadow_db <= noise_db + 3
print()
print('=== T0.5 ===')
print('A 海底-噪声 >= 10 dB:', 'PASS' if pass_a else 'FAIL')
print('B 海底 > 3sigma >= 80%:', 'PASS' if pass_b else 'FAIL')
print('C 阴影 <= 噪声+3 dB:', 'PASS' if pass_c else 'FAIL')
print('ALL:', 'PASS' if (pass_a and pass_b and pass_c) else 'FAIL')
