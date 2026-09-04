import numpy as np
from config import C, finalize_pixel_mapping
from world import SceneWorld
from trajectory import euler_to_matrix
from shadow import render_shadow_map
from sonar_render import render_frame

# 量程 25 m（接近 P1 建议）
for rmax in [10, 15, 20, 25, 30]:
    test_sonar = C.sonar.__class__(
        beam_count=512, range_bin_count=1600,  # 1600 bin
        fov_azimuth_deg=(-65.0, 65.0), fov_elevation_deg=(-20.0, 20.0),
        range_min_m=0.50, range_max_m=rmax,
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
    
    all_pixels = img.flatten()
    nonzero = all_pixels[all_pixels > 0]
    seafloor_mean = all_pixels.mean()
    seafloor_db = 20*np.log10(seafloor_mean + 1e-12)
    above_3sigma_nz = (nonzero > 3 * noise_floor).sum() / len(nonzero) if len(nonzero) > 0 else 0
    print('range=%.0f m: 像素=%d, I>0=%d, 3sigma阈=%.2e' % (rmax, all_pixels.size, len(nonzero), 3*noise_floor))
    print('  Seafloor mean: %.4e (%.1f dB), Seafloor-Noise: %.1f dB' % (seafloor_mean, seafloor_db, seafloor_db - noise_db))
    print('  50 分位: %.2e, 95 分位: %.2e' % (np.percentile(nonzero, 50), np.percentile(nonzero, 95)))
    print('  I>0 中 > 3sigma: %.1f%%' % (above_3sigma_nz*100))
    print()
