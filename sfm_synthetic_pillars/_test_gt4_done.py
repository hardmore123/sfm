import numpy as np
from config import C, finalize_pixel_mapping
from world import SceneWorld
from gt_surface import sample_gt_surface, verify_sample_quality
from eval_surface import (
    chamfer_distance, hausdorff_distance, volumetric_error,
    normal_angle_error, point_to_surface_distance,
    floating_point_density,
)

finalize_pixel_mapping(C)
world = SceneWorld(C)

print('=== T0.10 单元测试（强约束 dxy=radius 后）===')
points, normals = sample_gt_surface(world, n_per_object=300, rng=np.random.default_rng(42))
print(f'sampled: {len(points)} points')
result = verify_sample_quality(points, normals, world)
print(f'  max_dist_to_analytic: {result["max_dist_to_analytic"]:.4e} (要求 <= 1e-6) {"PASS" if result["max_dist_to_analytic"] < 1e-6 else "FAIL"}')
print(f'  max_normal_error_rad: {result["max_normal_error_rad"]:.4e} (要求 <= 1e-4) {"PASS" if result["max_normal_error_rad"] < 1e-4 else "FAIL"}')
print(f'  std_over_mean_nn: {result["std_over_mean_nn"]:.4f} (要求 <= 0.3) {"PASS" if result["std_over_mean_nn"] < 0.3 else "FAIL"}')
print(f'  ok: {result["ok"]}')
