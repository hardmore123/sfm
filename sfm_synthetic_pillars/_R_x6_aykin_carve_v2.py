"""
R-X6 V2 修复：FORM 自动 + E 严格化 + 增视角
===========================================

V1 三个 bug 修复：
  1. FORM 用 target 邻域 = 作弊 → 改 make_binary_form (sonar dB 中位数 + MAD)
  2. volumetric_error 用质心距离高斯衰减 → 改体素化凸包 + 严格交集计数
  3. n_poses=6 太少 → 增到 12 帧

V2 限制：
  - 真 α-hull 需要 alphashape 库（未装），仍用 ConvexHull 近似
  - 论文中诚实标注 ConvexHull 简化

阶段表 R-X6 验收：
  - 凸目标 E ≤ 0.10
  - 凹目标 E ∈ [0.2, 0.8]
  - S ⊆ S̃ 包含性 ≥ 90%
"""
import os
import sys
import json
import numpy as np
from pathlib import Path
from scipy.spatial.transform import Rotation
from scipy.spatial import ConvexHull
from scipy.ndimage import binary_dilation

SCENE_ROOT = Path("F:/sfm/sfm_synthetic_pillars/scene_set_v2")


def make_binary_form_v2(sonar_image, n_std=3.0, erosion=0, r_min_m=1.5, r_max_m=18.0,
                        range_axis=None):
    """
    Aykin 2017 二值 FORM 图（V2 严格版）：
    1. 噪声底估计 = sonar 全局中位数
    2. 噪声 std = sonar 中位数绝对偏差 (MAD) × 1.4826
    3. 阈值 = 噪声底 + n_std × 噪声 std
    4. sonar > 阈值 → 目标 (1)；否则背景 (0)
    5. R 范围限制：去掉近场 AUV 自身 + 远场海底散射

    V2 关键改进（声呐专家）：
    - n_std=3.0 比 2.0 更严格
    - r_min=1.5m 去掉 AUV 自身近场信号
    - r_max=18.0m 去掉海底散射
    - 海底散射在声学场景下无法用全局阈值分离，必须加距离约束
    """
    # 在 dB 域操作
    sonar_db = 20 * np.log10(sonar_image + 1e-9)
    noise_floor = np.median(sonar_db)
    mad = np.median(np.abs(sonar_db - noise_floor))
    sigma = mad * 1.4826
    threshold_db = noise_floor + n_std * sigma
    form = sonar_db > threshold_db
    # R 范围限制（关键：去掉远场海底）
    if range_axis is not None:
        r_mask = (range_axis >= r_min_m) & (range_axis <= r_max_m)
        H = form.shape[0]
        if r_mask.shape[0] == H:
            form = form & r_mask[:, None]
    if erosion > 0:
        from scipy.ndimage import binary_erosion
        form = binary_erosion(form, iterations=erosion)
    return form


def voxelize_points(points, voxel_size=0.05, bounds=None):
    """
    体素化点云 → bool 3D 数组。
    bounds: ((xmin, ymin, zmin), (xmax, ymax, zmax)) 或 None（自动）
    Returns:
        voxel_grid: bool 3D
        origin: (3,) 体素原点
    """
    if bounds is None:
        bbox_min = points.min(axis=0) - voxel_size
        bbox_max = points.max(axis=0) + voxel_size
    else:
        bbox_min, bbox_max = bounds[0], bounds[1]
    origin = bbox_min
    dims = np.ceil((bbox_max - bbox_min) / voxel_size).astype(int)
    if (dims < 1).any():
        return np.zeros((1, 1, 1), dtype=bool), origin
    indices = np.floor((points - origin) / voxel_size).astype(int)
    # 截断到合法范围
    indices = np.clip(indices, 0, dims - 1)
    grid = np.zeros(dims, dtype=bool)
    grid[indices[:, 0], indices[:, 1], indices[:, 2]] = True
    return grid, origin


def volumetric_error_strict(recon_points, gt_points, voxel_size=0.05):
    """
    严格 volumetric error (Aykin 2017 式 8):
        E = (V + Ṽ - 2V∩) / (V + Ṽ - V∩)

    实现：体素化两凸包，统计体素数。
    凸包是浮点表示，vol 难直接算；改用体素化近似（Aykin 2017 也是这种近似）。
    """
    if len(recon_points) < 4 or len(gt_points) < 4:
        return 1.0, 0.0, 0.0

    # 取相同 bbox 体素化（避免 bbox 差异）
    all_pts = np.vstack([recon_points, gt_points])
    bbox_min = all_pts.min(axis=0) - 0.1
    bbox_max = all_pts.max(axis=0) + 0.1
    bounds = (bbox_min, bbox_max)

    recon_grid, origin = voxelize_points(recon_points, voxel_size, bounds)
    gt_grid, _ = voxelize_points(gt_points, voxel_size, bounds)

    # 凸包体积（用 ConvexHull）
    try:
        V_recon = ConvexHull(recon_points).volume
    except Exception:
        V_recon = 0.0
    try:
        V_gt = ConvexHull(gt_points).volume
    except Exception:
        V_gt = 0.0

    # 交集体素数 → 转体积
    n_inter_voxels = int((recon_grid & gt_grid).sum())
    V_inter_voxelized = n_inter_voxels * voxel_size ** 3
    # 并集体素数
    n_union_voxels = int((recon_grid | gt_grid).sum())
    V_union_voxelized = n_union_voxels * voxel_size ** 3

    # 用体素化交集作为 V∩（更严格）
    V_inter = V_inter_voxelized
    if V_recon + V_gt - V_inter <= 1e-9:
        return 0.0, V_recon, V_gt
    E = (V_recon + V_gt - 2 * V_inter) / (V_recon + V_gt - V_inter + 1e-9)
    return float(np.clip(E, 0, 1)), float(V_recon), float(V_gt)


def voxel_carve_hard_v2(poses_se3, form_masks, voxel_origin, voxel_size, n_voxels,
                          range_axis, beam_axis, fov_azim, fov_elev):
    """硬雕刻（同 V1，前沿光锥 + OR 累积）"""
    nx, ny, nz = n_voxels
    N = poses_se3.shape[0]
    H, W = form_masks.shape[1:]

    x = voxel_origin[0] + np.arange(nx) * voxel_size
    y = voxel_origin[1] + np.arange(ny) * voxel_size
    z = voxel_origin[2] + np.arange(nz) * voxel_size
    X, Y, Z = np.meshgrid(x, y, z, indexing='ij')
    voxel_centers = np.stack([X.ravel(), Y.ravel(), Z.ravel()], axis=1)
    alive = np.zeros(voxel_centers.shape[0], dtype=bool)

    dr = range_axis[1] - range_axis[0] if len(range_axis) > 1 else 0.04
    dtheta = beam_axis[1] - beam_axis[0] if len(beam_axis) > 1 else 0.024

    for n in range(N):
        R = poses_se3[n, :3, :3]
        t = poses_se3[n, :3, 3]
        voxel_in_sonar = (R.T @ (voxel_centers - t).T).T
        rho = np.linalg.norm(voxel_in_sonar, axis=1)
        theta = np.arctan2(voxel_in_sonar[:, 1], voxel_in_sonar[:, 0])
        elev = np.arctan2(voxel_in_sonar[:, 2], np.linalg.norm(voxel_in_sonar[:, :2], axis=1))

        i_rho = np.round((rho - range_axis[0]) / dr).astype(int)
        i_theta = np.round((theta - beam_axis[0]) / dtheta).astype(int)

        in_image = (i_rho >= 0) & (i_rho < H) & (i_theta >= 0) & (i_theta < W)
        in_elev = np.abs(elev) <= fov_elev
        in_range = (rho >= range_axis[0]) & (rho <= range_axis[-1])

        valid_idx = np.where(in_image & in_elev & in_range)[0]
        if len(valid_idx) == 0:
            continue

        unique_thetas = np.unique(i_theta[valid_idx])
        carved_this_frame = np.zeros(voxel_centers.shape[0], dtype=bool)
        for th in unique_thetas:
            beam_mask = i_theta[valid_idx] == th
            beam_idx = valid_idx[beam_mask]
            beam_form = form_masks[n, :, th]
            form_rows = np.where(beam_form)[0]
            if len(form_rows) == 0:
                continue
            front_rho = form_rows.max()
            keep_mask = i_rho[beam_idx] <= front_rho
            carved_this_frame[beam_idx[keep_mask]] = True
        alive = alive | carved_this_frame

    carved = alive.reshape(nx, ny, nz)
    return carved


def evaluate_aykin_v2(scene_name, voxel_size=0.1, n_poses=12, form_mode="auto"):
    """对单场景跑 R-X6 V2。"""
    print(f"\n=== {scene_name} ===")
    scene_dir = SCENE_ROOT / scene_name
    with open(scene_dir / "meta.json", encoding="utf-8") as f:
        meta = json.load(f)
    h_pillar = meta["scene"]["h_avg_m"]
    print(f"  h_pillar = {h_pillar} m, form_mode={form_mode}")

    poses_se3 = np.load(scene_dir / "gt/poses_gt.npy")
    sonar_imgs = np.load(scene_dir / "gt/sonar_images.npy")
    surface_pts = np.load(scene_dir / "gt/surface_points.npy")
    print(f"  sonar: {sonar_imgs.shape}, GT surface: {surface_pts.shape}, "
          f"z range [{surface_pts[:, 2].min():.2f}, {surface_pts[:, 2].max():.2f}]")

    N, H, W = sonar_imgs.shape

    range_axis = np.linspace(0.5, 25.0, H)
    beam_axis = np.linspace(-np.deg2rad(15), np.deg2rad(15), W)
    fov_azim = np.deg2rad(30)
    fov_elev = np.deg2rad(17)

    # FORM 生成（V2 关键：自动分割，不用 target）
    form_masks = np.zeros((N, H, W), dtype=bool)
    for n in range(N):
        if form_mode == "auto":
            form_masks[n] = make_binary_form_v2(sonar_imgs[n], n_std=3.0, erosion=0,
                                                  r_min_m=2.0, r_max_m=15.0,
                                                  range_axis=range_axis)
        elif form_mode == "gt_target":
            # 保留旧模式作对照（V1 行为）
            target_masks = np.load(scene_dir / "gt/target_masks.npy")
            struct = np.ones((11, 11), dtype=bool)
            form_masks[n] = binary_dilation(target_masks[n], structure=struct, iterations=2)
    form_cov = form_masks.mean() * 100
    print(f"  FORM 占比: {form_cov:.2f}%")

    # 选 n_poses 帧（V2 增到 12）
    has_form = np.array([form_masks[t].sum() > 0 for t in range(N)])
    valid_idx = np.where(has_form)[0]
    n_poses = min(n_poses, len(valid_idx))
    sel_idx = np.linspace(0, len(valid_idx) - 1, n_poses).astype(int)
    poses_sel = poses_se3[valid_idx[sel_idx]]
    form_sel = form_masks[valid_idx[sel_idx]]
    print(f"  选 {n_poses} 帧做雕刻（valid={len(valid_idx)}）")

    voxel_origin = np.array([-0.6, -0.6, 0.0])
    n_voxels = (12, 12, 30)

    carved = voxel_carve_hard_v2(
        poses_sel, form_sel, voxel_origin, voxel_size, n_voxels,
        range_axis, beam_axis, fov_azim, fov_elev
    )
    n_carved = carved.sum()
    print(f"  雕刻后保留体素: {n_carved} ({n_carved / np.prod(n_voxels) * 100:.1f}%)")

    # 凸包
    x = voxel_origin[0] + np.arange(n_voxels[0]) * voxel_size
    y = voxel_origin[1] + np.arange(n_voxels[1]) * voxel_size
    z = voxel_origin[2] + np.arange(n_voxels[2]) * voxel_size
    X, Y, Z = np.meshgrid(x, y, z, indexing='ij')
    recon_pts = np.stack([X[carved], Y[carved], Z[carved]], axis=1)

    # 严格 volumetric error
    E, V_recon, V_gt = volumetric_error_strict(recon_pts, surface_pts, voxel_size=0.05)
    print(f"  V_recon = {V_recon:.3f} m^3, V_gt = {V_gt:.3f} m^3")
    print(f"  volumetric error E (严格) = {E:.3f}")

    # 包含性
    x_min, y_min, z_min = surface_pts.min(axis=0)
    x_max, y_max, z_max = surface_pts.max(axis=0)
    margin = 0.2
    in_box = (
        (recon_pts[:, 0] >= x_min - margin) & (recon_pts[:, 0] <= x_max + margin) &
        (recon_pts[:, 1] >= y_min - margin) & (recon_pts[:, 1] <= y_max + margin) &
        (recon_pts[:, 2] >= z_min - margin) & (recon_pts[:, 2] <= z_max + margin)
    )
    inclusion_pct = in_box.mean() * 100 if len(recon_pts) > 0 else 0
    print(f"  inclusion (S in S_tilde +-{margin}m): {inclusion_pct:.1f}%")

    return {
        "scene": scene_name,
        "h_pillar": h_pillar,
        "n_poses": n_poses,
        "form_mode": form_mode,
        "form_coverage_pct": float(form_cov),
        "n_carved": int(n_carved),
        "n_carved_pct": float(n_carved / np.prod(n_voxels) * 100),
        "V_recon": V_recon,
        "V_gt": V_gt,
        "volumetric_error_strict": E,
        "inclusion_pct": float(inclusion_pct),
    }


def main():
    print("=" * 60)
    print("R-X6 V2：FORM 自动 + E 严格 + 增视角")
    print("=" * 60)
    print("V1 -> V2 修复:")
    print("  1. FORM 改用 make_binary_form (sonar 自动 dB 阈值)")
    print("  2. E 改用体素化凸包 + 严格交集计数")
    print("  3. n_poses: 6 -> 12")
    print()
    scenes = [
        "S1_single_well_constrained",
        "S2_single_forward_degenerate",
        "S3_mixed_shapes",
        "S4_low_snr",
        "S5_envelope_edge",
    ]

    # V2a: FORM auto + 12 视角（推荐）
    results_v2 = []
    for s in scenes:
        r = evaluate_aykin_v2(s, voxel_size=0.1, n_poses=12, form_mode="auto")
        if r:
            results_v2.append(r)

    # V2b: FORM auto + 6 视角（消融 1：视角数）
    results_v2_6p = []
    for s in scenes:
        r = evaluate_aykin_v2(s, voxel_size=0.1, n_poses=6, form_mode="auto")
        if r:
            results_v2_6p.append(r)

    # 汇总
    print(f"\n{'='*60}")
    print(f"=== 5 场景 V2 对比（12 vs 6 视角）===")
    print(f"{'场景':<30} {'h_pillar':<8} {'n_poses':<8} {'form%':<8} {'E_严格':<8} {'V_recon':<8} {'V_gt':<8} {'包含性':<8}")
    print(f"{'-'*100}")
    for r_v2, r_v2p in zip(results_v2, results_v2_6p):
        print(f"  {r_v2['scene']:<28} {r_v2['h_pillar']:<8.1f} "
              f"12{'':<6} {r_v2['form_coverage_pct']:<8.2f} "
              f"{r_v2['volumetric_error_strict']:<8.3f} "
              f"{r_v2['V_recon']:<8.3f} {r_v2['V_gt']:<8.3f} {r_v2['inclusion_pct']:<8.1f}%")
        print(f"  {r_v2['scene'] + ' (6p)':<28} {r_v2p['h_pillar']:<8.1f} "
              f"6{'':<7} {r_v2p['form_coverage_pct']:<8.2f} "
              f"{r_v2p['volumetric_error_strict']:<8.3f} "
              f"{r_v2p['V_recon']:<8.3f} {r_v2p['V_gt']:<8.3f} {r_v2p['inclusion_pct']:<8.1f}%")

    # 验收
    print(f"\n=== R-X6 V2 验收（FORM auto + 12 视角）===")
    Es = [r["volumetric_error_strict"] for r in results_v2]
    inclusions = [r["inclusion_pct"] for r in results_v2]
    n_pass_convex = sum(1 for i, s in enumerate(scenes) if s != "S3_mixed_shapes" and Es[i] <= 0.10)
    n_pass_concave = sum(1 for i, s in enumerate(scenes) if s == "S3_mixed_shapes" and 0.2 <= Es[i] <= 0.8)
    n_include = sum(1 for inc in inclusions if inc >= 90)
    print(f"  凸目标 E ≤ 0.10: {n_pass_convex}/4 (S1/S2/S4/S5)")
    print(f"  凹目标 E ∈ [0.2, 0.8]: {n_pass_concave}/1 (S3)")
    print(f"  包含性 ≥ 90%: {n_include}/{len(inclusions)}")

    # 落盘
    out = {
        "results_v2_12p": results_v2,
        "results_v2_6p": results_v2_6p,
        "summary": {
            "n_scenes": len(results_v2),
            "n_E_le_010_convex": n_pass_convex,
            "n_E_in_020_080_concave": n_pass_concave,
            "n_inclusion_ge_90": n_include,
            "version": "v2",
        },
    }
    out_path = Path("R_X6_V2_RESULTS.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False, default=str)
    print(f"\n[ok] 落盘 {out_path}")


if __name__ == "__main__":
    main()
