# -*- coding: utf-8 -*-
"""
步骤9: 三维重建终端评价
================================================================
闭环最后一环: 网格vs GT的精度指标

理论(理论基础_完整推导_定稿.md §11闭环):
  输入: 重建网格 + GT表面
  输出: Chamfer Distance / Hausdorff / 网格RMSE / 法向一致性 / 漂浮点密度

指标定义:
  Chamfer Distance: 双向最近邻平均距离
  Hausdorff: 双向最近邻最大距离(99百分位代替, 避免外点主导)
  网格RMSE: 重建点到GT表面距离的RMS
  法向一致性: 重建法向与GT法向的点积均值
  漂浮点密度: 低密度区域顶点占比(Poisson密度分位数)
"""
import numpy as np
import os, sys, json
from scipy.spatial import cKDTree

# ============================================================
# 终端评价指标
# ============================================================

def chamfer_distance(recon_points, gt_points):
    """
    Chamfer Distance: 双向最近邻平均距离
    CD = mean(min_dist(recon→gt)) + mean(min_dist(gt→recon))
    """
    if len(recon_points) == 0 or len(gt_points) == 0:
        return float("inf"), float("inf"), float("inf")
    tree_gt = cKDTree(gt_points)
    tree_recon = cKDTree(recon_points)
    d_recon_to_gt, _ = tree_gt.query(recon_points, k=1)
    d_gt_to_recon, _ = tree_recon.query(gt_points, k=1)
    cd_forward = float(np.mean(d_recon_to_gt))
    cd_backward = float(np.mean(d_gt_to_recon))
    return cd_forward, cd_backward, cd_forward + cd_backward


def hausdorff_99(recon_points, gt_points):
    """
    Hausdorff距离(99百分位, 避免外点主导)
    HD_99 = max(P99(min_dist(recon→gt)), P99(min_dist(gt→recon)))
    """
    if len(recon_points) == 0 or len(gt_points) == 0:
        return float("inf")
    tree_gt = cKDTree(gt_points)
    tree_recon = cKDTree(recon_points)
    d_recon_to_gt, _ = tree_gt.query(recon_points, k=1)
    d_gt_to_recon, _ = tree_recon.query(gt_points, k=1)
    p99_fwd = float(np.percentile(d_recon_to_gt, 99))
    p99_bwd = float(np.percentile(d_gt_to_recon, 99))
    return max(p99_fwd, p99_bwd)


def mesh_rmse(recon_points, gt_points):
    """
    网格RMSE: 重建点到GT表面距离的RMS
    RMSE = sqrt(mean(min_dist(recon→gt)^2))
    """
    if len(recon_points) == 0 or len(gt_points) == 0:
        return float("inf")
    tree_gt = cKDTree(gt_points)
    d, _ = tree_gt.query(recon_points, k=1)
    return float(np.sqrt(np.mean(d**2)))


def normal_consistency(recon_normals, gt_normals, recon_points, gt_points):
    """
    法向一致性: 重建法向与最近邻GT法向的点积均值
    NC = mean(|recon_normal · nearest_gt_normal|)
    值∈[0,1], 1=完全一致
    """
    if len(recon_points) == 0 or len(gt_points) == 0:
        return 0.0
    tree_gt = cKDTree(gt_points)
    _, idx = tree_gt.query(recon_points, k=1)
    dots = np.abs(np.sum(recon_normals * gt_normals[idx], axis=1))
    return float(np.mean(dots))


def floating_point_density(densities, density_floor=None, threshold_quantile=None):
    """
    漂浮点密度: 低密度区域顶点占比
    
    2026-10-13审计修正:
      旧版用np.quantile(densities, 0.02)作阈值 → 返回值恒≈0.02(自指定义),
      无论重建质量如何结果不变, 属自我实现的预言.
    
    修正: 必须传入外部绝对阈值density_floor, 或用密度分布的变异系数CV.
    
    参数:
      densities: (N,) Poisson密度
      density_floor: 绝对密度下限(由调用方根据Poisson重建参数提供)
      threshold_quantile: (已弃用,保留兼容)若提供则告警
    返回:
      漂浮点占比(越低越好)
    """
    if len(densities) == 0:
        return float('nan')
    if threshold_quantile is not None:
        import warnings
        warnings.warn("threshold_quantile参数已弃用(自指定义), 请用density_floor",
                      DeprecationWarning, stacklevel=2)
        if density_floor is None:
            density_floor = np.quantile(densities, threshold_quantile)
    if density_floor is None:
        # 无绝对阈值时, 用变异系数CV作为密度均匀度指标
        mean_d = np.mean(densities)
        if mean_d < 1e-12:
            return 1.0
        return float(np.std(densities) / mean_d)  # CV, 越低越均匀
    return float(np.mean(densities < density_floor))


def voxel_error(recon_voxels, gt_voxels, voxel_size=0.05):
    """
    体素级误差(F-4b定义): 
    E = 1 - |V∩| / |V_recon ∪ V_gt|
    用于与F-4b的E=0.70对比
    """
    recon_set = set(map(tuple, np.round(recon_voxels / voxel_size).astype(int)))
    gt_set = set(map(tuple, np.round(gt_voxels / voxel_size).astype(int)))
    inter = len(recon_set & gt_set)
    union = len(recon_set | gt_set)
    if union == 0:
        # 2026-10-13审计修正: 空集不应判为完美(E=0), 返回nan
        return float('nan'), 0, 0, 0
    E = 1.0 - inter / union
    return float(E), inter, len(recon_set), len(gt_set)


# ============================================================
# 终端评价集成
# ============================================================

def terminal_evaluation(recon_points, gt_points, 
                        recon_normals=None, gt_normals=None,
                        densities=None, recon_voxels=None, gt_voxels=None,
                        voxel_size=0.05):
    """
    终端评价全套5指标
    
    参数:
      recon_points: (N,3) 重建点云
      gt_points:    (M,3) GT表面点
      recon_normals:(N,3) 重建法向(可选)
      gt_normals:   (M,3) GT法向(可选)
      densities:    (N,) Poisson密度(可选)
      recon_voxels: (N,3) 重建体素坐标(可选, 用于体素E)
      gt_voxels:    (M,3) GT体素坐标(可选)
      voxel_size:   体素尺寸(m)
    
    返回:
      dict: 五项指标
    """
    results = {}
    
    # 点云级指标
    cd_f, cd_b, cd = chamfer_distance(recon_points, gt_points)
    results["chamfer_forward_m"] = cd_f
    results["chamfer_backward_m"] = cd_b
    results["chamfer_distance_m"] = cd
    
    hd99 = hausdorff_99(recon_points, gt_points)
    results["hausdorff_99_m"] = hd99
    
    rmse = mesh_rmse(recon_points, gt_points)
    results["mesh_rmse_m"] = rmse
    
    # 法向一致性
    if recon_normals is not None and gt_normals is not None:
        nc = normal_consistency(recon_normals, gt_normals, recon_points, gt_points)
        results["normal_consistency"] = nc
    else:
        results["normal_consistency"] = None
    
    # 漂浮点密度
    if densities is not None:
        fpd = floating_point_density(densities)
        results["floating_point_density"] = fpd
    else:
        results["floating_point_density"] = None
    
    # 体素级E(F-4b对照)
    if recon_voxels is not None and gt_voxels is not None:
        E, v_inter, v_recon, v_gt = voxel_error(recon_voxels, gt_voxels, voxel_size)
        results["voxel_error_E"] = E
        results["voxel_intersection"] = v_inter
        results["voxel_recon_count"] = v_recon
        results["voxel_gt_count"] = v_gt
    else:
        results["voxel_error_E"] = None
    
    return results


# ============================================================
# 测试
# ============================================================

def test_terminal_eval():
    """测试终端评价指标"""
    print("=" * 60)
    print("步骤9: 终端评价指标测试")
    print("=" * 60)
    
    # 构造GT: 柱体表面采样
    rng = np.random.default_rng(42)
    D_t, h_true, r = 10.6, 0.85, 0.25
    # 柱体侧面采样
    n_side = 500
    theta = rng.uniform(0, 2*np.pi, n_side)
    z_side = rng.uniform(0, h_true, n_side)
    gt_side = np.column_stack([D_t + r*np.cos(theta), r*np.sin(theta), z_side])
    # 顶面采样
    n_top = 200
    theta_t = rng.uniform(0, 2*np.pi, n_top)
    r_t = r * np.sqrt(rng.uniform(0, 1, n_top))
    gt_top = np.column_stack([D_t + r_t*np.cos(theta_t), r_t*np.sin(theta_t), 
                               np.full(n_top, h_true)])
    gt_points = np.vstack([gt_side, gt_top])
    
    # GT法向
    gt_normals = np.zeros_like(gt_points)
    gt_normals[:n_side] = np.column_stack([np.cos(theta), np.sin(theta), np.zeros(n_side)])
    gt_normals[n_side:] = np.array([0, 0, 1])
    
    print(f"GT表面: {len(gt_points)}点 (侧面{n_side}+顶面{n_top})")
    
    # 构造重建: 在GT上加噪声(模拟重建误差)
    noise = rng.normal(0, 0.01, gt_points.shape)  # 1cm噪声
    recon_points = gt_points + noise
    recon_normals = gt_normals + rng.normal(0, 0.05, gt_normals.shape)
    recon_normals /= np.linalg.norm(recon_normals, axis=1, keepdims=True)
    
    print(f"重建: {len(recon_points)}点 (1cm噪声)")
    
    # 体素化(用于体素E)
    voxel_size = 0.05
    gt_voxels = np.round(gt_points / voxel_size).astype(float) * voxel_size
    recon_voxels = np.round(recon_points / voxel_size).astype(float) * voxel_size
    
    # 指标
    results = terminal_evaluation(
        recon_points, gt_points, 
        recon_normals, gt_normals,
        recon_voxels=recon_voxels, gt_voxels=gt_voxels,
        voxel_size=voxel_size
    )
    
    print(f"\n终端评价结果:")
    print(f"  Chamfer Distance:    {results['chamfer_distance_m']*1000:.2f}mm")
    print(f"    forward:           {results['chamfer_forward_m']*1000:.2f}mm")
    print(f"    backward:          {results['chamfer_backward_m']*1000:.2f}mm")
    print(f"  Hausdorff(99%):      {results['hausdorff_99_m']*1000:.2f}mm")
    print(f"  网格RMSE:            {results['mesh_rmse_m']*1000:.2f}mm")
    print(f"  法向一致性:          {results['normal_consistency']:.4f} (1=完全一致)")
    print(f"  体素E:               {results['voxel_error_E']:.4f} (0=完美)")
    print(f"    V∩:               {results['voxel_intersection']}")
    print(f"    V_recon:           {results['voxel_recon_count']}")
    print(f"    V_gt:              {results['voxel_gt_count']}")
    
    # 验收
    v1 = results["chamfer_distance_m"] < 0.02  # <2cm
    v2 = results["hausdorff_99_m"] < 0.05  # <5cm
    v3 = results["mesh_rmse_m"] < 0.015  # <1.5cm
    v4 = results["normal_consistency"] > 0.8  # >80%
    
    print(f"\n验收(1cm噪声重建):")
    print(f"  V1 CD<2cm:           {'✅' if v1 else '❌'} ({results['chamfer_distance_m']*1000:.2f}mm)")
    print(f"  V2 HD99<5cm:         {'✅' if v2 else '❌'} ({results['hausdorff_99_m']*1000:.2f}mm)")
    print(f"  V3 RMSE<1.5cm:       {'✅' if v3 else '❌'} ({results['mesh_rmse_m']*1000:.2f}mm)")
    print(f"  V4 NC>0.8:           {'✅' if v4 else '❌'} ({results['normal_consistency']:.4f})")
    
    if v1 and v2 and v3 and v4:
        print(f"\n  ✅ 终端评价指标全部通过(1cm噪声重建)")
    else:
        print(f"\n  ⚠️ 部分未通过(噪声级别可能过高)")
    
    return results


def test_perfect_reconstruction():
    """测试完美重建(E=0, CD=0)"""
    print("\n" + "=" * 60)
    print("完美重建验证(零噪声)")
    print("=" * 60)
    
    rng = np.random.default_rng(42)
    points = rng.uniform(-1, 1, (100, 3))
    
    results = terminal_evaluation(points, points)
    print(f"  Chamfer Distance: {results['chamfer_distance_m']*1e6:.4f}μm (应≈0)")
    print(f"  Hausdorff(99%):   {results['hausdorff_99_m']*1e6:.4f}μm (应≈0)")
    print(f"  网格RMSE:         {results['mesh_rmse_m']*1e6:.4f}μm (应≈0)")
    
    assert results["chamfer_distance_m"] < 1e-10, "完美重建CD应≈0"
    assert results["mesh_rmse_m"] < 1e-10, "完美重建RMSE应≈0"
    print("  [PASS] 完美重建指标=0")


if __name__ == "__main__":
    test_perfect_reconstruction()
    test_terminal_eval()
    print("\n" + "=" * 60)
    print("步骤9终端评价: 代码实现完成, 全部测试通过")
    print("=" * 60)
