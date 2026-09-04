import numpy as np
from config import C, finalize_pixel_mapping
from world import SceneWorld
from gt_surface import sample_gt_surface, verify_sample_quality

finalize_pixel_mapping(C)
world = SceneWorld(C)
points, normals = sample_gt_surface(world, n_per_object=300, rng=np.random.default_rng(42))
print('Total points:', len(points))

# 重新算
all_min = np.full(len(points), np.inf)
for obj in world.pillars:
    dxy = np.sqrt((points[:, 0] - obj.cx)**2 + (points[:, 1] - obj.cy)**2)
    dz = points[:, 2]
    side = np.abs(dxy - obj.radius)
    top = np.abs(dz - obj.height)
    bot = np.abs(dz - 0.0)
    in_cyl = (dxy < obj.radius) & (dz > 0) & (dz < obj.height)
    d = np.where(in_cyl, np.minimum(top, bot), np.minimum(np.minimum(side, top), bot))
    all_min = np.minimum(all_min, d)

print('all_min max:', all_min.max())
print('idx of max:', all_min.argmax())
print('point at max idx:', points[all_min.argmax()])
print('all_min at idx 1525:', all_min[1525])

# 重新 verify
result = verify_sample_quality(points, normals, world)
print()
print('=== T0.10 重新验收 ===')
print(f'  max_dist_to_analytic: {result["max_dist_to_analytic"]:.6e} (要求 <= 1e-6) {"PASS" if result["max_dist_to_analytic"] < 1e-6 else "FAIL"}')
print(f'  max_normal_error_rad: {result["max_normal_error_rad"]:.6e} (要求 <= 1e-4) {"PASS" if result["max_normal_error_rad"] < 1e-4 else "FAIL"}')
print(f'  std_over_mean_nn: {result["std_over_mean_nn"]:.6f} (要求 <= 0.3) {"PASS" if result["std_over_mean_nn"] < 0.3 else "FAIL"}')
print(f'  ok: {result["ok"]}')
