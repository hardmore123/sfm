import numpy as np
from config import C, finalize_pixel_mapping
from world import SceneWorld
from gt_surface import sample_gt_surface, verify_sample_quality
from eval_surface import (
    chamfer_distance, hausdorff_distance, volumetric_error,
    normal_angle_error, point_to_surface_distance,
    floating_point_density, evaluate_surface,
)

finalize_pixel_mapping(C)
world = SceneWorld(C)

# T0.10
print('=== T0.10 单元测试 ===')
points, normals = sample_gt_surface(world, n_per_object=300, rng=np.random.default_rng(42))
print(f'sampled: {len(points)} points')
result = verify_sample_quality(points, normals, world)
print(f'  max_dist_to_analytic: {result["max_dist_to_analytic"]:.4e} (要求 <= 1e-6)')
print(f'  max_normal_error_rad: {result["max_normal_error_rad"]:.4e} (要求 <= 1e-4)')
print(f'  std_over_mean_nn: {result["std_over_mean_nn"]:.4f} (要求 <= 0.3)')
print(f'  ok: {result["ok"]}')

# T0.11
print()
print('=== T0.11 单元测试 ===')
P = points
chamfer_self = chamfer_distance(P, P)
print(f'Chamfer(P, P) = {chamfer_self:.6e} (要求 = 0) {"PASS" if chamfer_self < 1e-9 else "FAIL"}')
P_shifted = P + np.array([0.05, 0, 0])
chamfer_5cm = chamfer_distance(P, P_shifted)
chamfer_err = abs(chamfer_5cm - 0.05) / 0.05
print(f'Chamfer(P, P+5cm) = {chamfer_5cm*100:.3f} cm (要求 5 cm +- 1%, 误差 {chamfer_err*100:.1f}%) {"PASS" if chamfer_err < 0.01 else "FAIL"}')
h = hausdorff_distance(P, P_shifted)
print(f'Hausdorff(P, P+5cm) = {h*100:.3f} cm (期望 5 cm)')
ve = volumetric_error(P, P_shifted, voxel_size=0.05)
print(f'Volumetric error(P, P+5cm) = {ve:.4f}')
mean_n, max_n = normal_angle_error(P, normals, P, normals)
print(f'Normal angle error (self) = mean={mean_n:.6f}, max={max_n:.6f}')
fp = floating_point_density(P, R=0.1)
print(f'Floating point ratio (R=10cm) = {fp:.4f}')
pts = point_to_surface_distance(P, P_shifted, normals)
print(f'Point-to-surface(P, P+5cm) = {pts*100:.3f} cm (期望 5)')
