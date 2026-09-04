"""
S1-S6 场景跑批生成器 (T1.1 + T1.3 阶段表 §4 P1)
================================================

按 T1.1 重设计构型 + T1.3 重跑 6 场景，串起：
  - sonar_render V3（Lambert 海底散射 + 遍历 all_objects）
  - shadow V5（射线遮挡，无 GT 泄漏）
  - height_inversion V2（精确正演式 + σ 传播）
  - gt_surface（T0.10 GT 表面采样）
  - eval_surface（T0.11 评价自检）

输出（每个场景到 <out_root>/<scene_name>/）：
  meta.json               - 摘要（含可反演性、GT 质量、反演精度）
  gt/
    poses_gt.npy          (N, 4, 4)
    surface_points.npy    (M, 3)  T0.10
    surface_normals.npy   (M, 3)  T0.10
    sonar_images.npy      (N, H, W)
    target_masks.npy      (N, H, W)
    shadow_masks.npy      (N, H, W)
    height_gt_maps.npy    (N, H, W)
    target_elev_maps.npy  (N, H, W)
    shadow_length_maps.npy (N, H, W)
  innovation2/
    height_inverted.npy   (N, H, W)  T0.8 精确反演
    sigma_height.npy      (N, H, W)
    height_inverted_v1.npy (N, H, W)  V1 简化式（对照基线）
    inversion_stats.json
  README.md               - 场景说明 + 包线余量
"""
import os
import sys
import time
import json
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import Config, finalize_pixel_mapping
from world import SceneWorld
from trajectory import make_poses, euler_to_matrix
from sonar_render import render_all_frames
from shadow import render_all_shadow_maps
from height_inversion import (
    invert_height_precise_from_pixels,
    invert_height_from_shadow_pixels,
)
from gt_surface import sample_gt_surface, verify_sample_quality, verify_sample_quality_per_face
from eval_surface import (
    evaluate_surface,
    chamfer_distance,
    hausdorff_distance,
    volumetric_error,
)
from feasibility import check_feasibility

from scene_configs_v2 import SCENES_V2, _scene_target_heights, verify_scene_feasibility


# ==========================================
# AUV 轨迹到 4x4 位姿矩阵
# ==========================================
def _make_poses_T(cfg: Config):
    """从 cfg 生成 poses_T (N, 4, 4)。若 cfg 有 _custom_poses，优先用。"""
    if hasattr(cfg, "_custom_poses") and cfg._custom_poses is not None:
        poses6 = cfg._custom_poses
        n = poses6.shape[0]
        poses_T = np.zeros((n, 4, 4))
        for i in range(n):
            T = np.eye(4)
            T[:3, :3] = euler_to_matrix(poses6[i, 3], poses6[i, 4], poses6[i, 5])
            T[:3, 3] = poses6[i, :3]
            poses_T[i] = T
        return poses6, poses_T
    return make_poses(cfg)


# ==========================================
# 单场景生成
# ==========================================
def generate_scene_v2(
    name: str,
    title: str,
    desc: str,
    factory,
    expected_feasible: bool,
    out_root: str = "./scene_set_v2",
    n_elev_render: int = 15,
    n_elev_shadow: int = 25,
    n_per_object_gt: int = 1500,
    verbose: bool = True,
) -> dict:
    """生成单场景到 <out_root>/<name>/。

    Returns:
        meta: dict 含统计 + 可反演性 + GT 质量 + 反演精度
    """
    t0 = time.time()
    out_dir = os.path.join(out_root, name)
    gt_dir = os.path.join(out_dir, "gt")
    inv2_dir = os.path.join(out_dir, "innovation2")
    for d in [out_dir, gt_dir, inv2_dir]:
        os.makedirs(d, exist_ok=True)

    cfg = factory()
    finalize_pixel_mapping(cfg)

    # 1) 位姿 + 场景
    poses6, poses_T = _make_poses_T(cfg)
    N = poses_T.shape[0]
    world = SceneWorld(cfg)
    rng = np.random.default_rng(cfg.seed)
    if verbose:
        print(f"\n=== {name} | {title} ===")
        print(f"  N={N}, pillars={len(world.pillars)}, cubes={len(world.cubes)}, "
              f"spheres={len(world.spheres)}")
        print(f"  z_s={cfg.traj.start_xyz[2]:.1f}m, ρ_max={cfg.sonar.range_max_m:.1f}m, "
              f"θ_p={np.degrees(cfg.traj.start_rpy[1]):.0f}°, heave={cfg.traj.heave_amplitude_m:.1f}m")

    # 2) shadow V5.2 (target_masks, shadow_masks, height_maps, shadow_lens, D_t_maps, target_elevs)
    t1 = time.time()
    target_masks, shadow_masks, height_maps, shadow_lens, D_t_maps, target_elevs = render_all_shadow_maps(
        poses_T, world, cfg=cfg, n_elev=n_elev_shadow, verbose=verbose
    )
    t_shadow = time.time() - t1

    # 3) sonar_render V3 (传入 shadow_masks 触发阴影衰减)
    t1 = time.time()
    images = render_all_frames(
        poses_T, world, cfg=cfg, shadow_masks=shadow_masks,
        n_elev=n_elev_render, rng=rng, verbose=verbose
    )
    t_render = time.time() - t1

    # 4) 高度反演 V2 精确式
    H, W = cfg.sonar.range_bin_count, cfg.sonar.beam_count
    # D_t_map: 声呐到目标底部的水平距离
    # 简化：对每帧，每根 beam 的 D_t = 沿该 beam 方向从声呐到目标底部投影到 floor 的水平距离
    #       即 D_t = sqrt(rho_hit^2 - (z_s - z_floor)^2) ≈ rho_hit · cos(elev_hit)
    #       但 z_s=4.5, z_floor=0, 沿射线 rho_hit 对应 z_s + t*sin(elev)=z_floor ⇒ t=4.5/|sin(elev)|
    # 这里用 D_t = (h_target - 0) / |tan(elev_hit)| = h_target / |tan(elev_hit)|
    # 但实际我们想要 D_t = 声呐到目标底部（floor 投影），即水平距离
    # 既然 h=L_s*z_s/(D_t+L_s)，D_t 是未知数之一 —— 这里用 target_mask 的距离估算
    z_s = float(cfg.traj.start_xyz[2])
    # 简单策略：对每帧每 beam，用 height_map 在 target 行的 z_top 和 target_elev 算 D_t
    # D_t = 声呐到目标底部（floor 投影）的水平距离
    #     = (z_s - z_top) / |tan(elev_hit)|  （从声呐沿 elev 射线到目标顶部，水平分量）
    # 目标底部和顶部的水平位置相同（柱垂直），所以 D_t 是声呐到目标"底部位置"的水平距离
    # 用 target_mask 行的 z_top 和 elev 算，对该列所有行（target + shadow）填同一值
    D_t_map = np.full((N, H, W), np.nan, dtype=np.float32)
    for i in range(N):
        for c in range(W):
            # 找该列的 target 行（z_top 有限 + target_mask=True）
            trows = np.where(target_masks[i, :, c] & np.isfinite(height_maps[i, :, c]))[0]
            if len(trows) == 0:
                continue
            # 取最靠前的 target 行（最近的目标像素）
            tr = trows[0]
            z_top = float(height_maps[i, tr, c])
            elev = float(target_elevs[i, tr, c])
            if z_s <= z_top or abs(np.tan(elev)) < 1e-3:
                continue
            D_t_val = (z_s - z_top) / abs(np.tan(elev))
            if not np.isfinite(D_t_val) or D_t_val <= 0:
                continue
            D_t_map[i, :, c] = D_t_val  # 该列所有行用同一 D_t

    # 5) 反演 V2 精确式（无噪声 + 仿真噪声两版）
    h_inv, sigma_h_inv = invert_height_precise_from_pixels(
        shadow_masks, shadow_lens, target_elevs, D_t_map, z_s=z_s,
        sigma_L_m=0.05, sigma_D_m=0.05, sigma_z_m=0.05,
    )
    # 加 L_s 噪声模拟真实声呐测距误差（σ_L = 5cm，T0.7 验收点 5cm）
    shadow_lens_noisy = shadow_lens + rng.normal(0.0, 0.05, shadow_lens.shape).astype(np.float32)
    # NaN 保护
    shadow_lens_noisy = np.where(np.isfinite(shadow_lens), shadow_lens_noisy, shadow_lens)
    h_inv_noisy, sigma_h_noisy = invert_height_precise_from_pixels(
        shadow_masks, shadow_lens_noisy, target_elevs, D_t_map, z_s=z_s,
        sigma_L_m=0.05, sigma_D_m=0.05, sigma_z_m=0.05,
    )

    # 6) V1 简化式（基线对照）
    h_inv_v1, _ = invert_height_from_shadow_pixels(
        shadow_masks, target_elevs, target_elevs,
        sigma_shadow_m=0.05, sigma_elev_rad=np.deg2rad(1.0),
    )

    # 7) 反演精度（与真值 h_top 比较）
    h_top_per_col = np.full((N, W), np.nan, dtype=np.float32)
    for i in range(N):
        for c in range(W):
            trows = np.where(target_masks[i, :, c])[0]
            if len(trows) > 0:
                vals = height_maps[i, trows, c]
                vals = vals[np.isfinite(vals)]
                if len(vals) > 0:
                    h_top_per_col[i, c] = float(vals.mean())
    h_top_map = np.tile(h_top_per_col[:, None, :], (1, H, 1))
    valid_inv = shadow_masks & np.isfinite(h_inv) & np.isfinite(h_top_map)
    if valid_inv.sum() > 0:
        err_v2 = h_inv[valid_inv] - h_top_map[valid_inv]
        mae_v2 = float(np.median(np.abs(err_v2)))
        rmse_v2 = float(np.sqrt(np.mean(err_v2 ** 2)))
    else:
        mae_v2 = None
        rmse_v2 = None
    # 仿真噪声 V2（σ_L = 5cm）
    valid_inv_n = shadow_masks & np.isfinite(h_inv_noisy) & np.isfinite(h_top_map)
    if valid_inv_n.sum() > 0:
        err_v2n = h_inv_noisy[valid_inv_n] - h_top_map[valid_inv_n]
        mae_v2_noisy = float(np.median(np.abs(err_v2n)))
        rmse_v2_noisy = float(np.sqrt(np.mean(err_v2n ** 2)))
    else:
        mae_v2_noisy = None
        rmse_v2_noisy = None
    valid_v1 = shadow_masks & np.isfinite(h_inv_v1) & np.isfinite(h_top_map)
    if valid_v1.sum() > 0:
        err_v1 = h_inv_v1[valid_v1] - h_top_map[valid_v1]
        mae_v1 = float(np.median(np.abs(err_v1)))
    else:
        mae_v1 = None

    # 8) GT 表面采样（T0.10）
    t1 = time.time()
    surface_pts, surface_norms = sample_gt_surface(world, n_per_object=n_per_object_gt, rng=rng)
    gt_q = verify_sample_quality(surface_pts, surface_norms, world)
    gt_q_face = verify_sample_quality_per_face(surface_pts, surface_norms, world)
    t_gt = time.time() - t1

    # 9) 落盘
    np.save(os.path.join(gt_dir, "poses_gt.npy"), poses_T)
    np.save(os.path.join(gt_dir, "surface_points.npy"), surface_pts)
    np.save(os.path.join(gt_dir, "surface_normals.npy"), surface_norms)
    np.save(os.path.join(gt_dir, "sonar_images.npy"), images)
    np.save(os.path.join(gt_dir, "target_masks.npy"), target_masks)
    np.save(os.path.join(gt_dir, "shadow_masks.npy"), shadow_masks)
    np.save(os.path.join(gt_dir, "height_gt_maps.npy"), height_maps)
    np.save(os.path.join(gt_dir, "target_elev_maps.npy"), target_elevs)
    np.save(os.path.join(gt_dir, "shadow_length_maps.npy"), shadow_lens)
    np.save(os.path.join(gt_dir, "D_t_map.npy"), D_t_map)
    np.save(os.path.join(inv2_dir, "height_inverted.npy"), h_inv)
    np.save(os.path.join(inv2_dir, "sigma_height.npy"), sigma_h_inv)
    np.save(os.path.join(inv2_dir, "height_inverted_v1.npy"), h_inv_v1)
    np.save(os.path.join(inv2_dir, "height_inverted_noisy.npy"), h_inv_noisy)
    np.save(os.path.join(inv2_dir, "sigma_height_noisy.npy"), sigma_h_noisy)

    # 10) 可反演性自检
    heights = _scene_target_heights(cfg)
    h_avg = float(np.mean(heights)) if heights else 0
    # d 中位：AUV 中位到目标
    target_xys = []
    for p in cfg.scene.pillars: target_xys.append((p[0], p[1]))
    for c in cfg.scene.cubes: target_xys.append((c[0], c[1]))
    for s in cfg.scene.spheres: target_xys.append((s[0], s[1]))
    x_mid = cfg.traj.start_xyz[0] + 0.5 * cfg.traj.forward_total_m
    y_mid = cfg.traj.start_xyz[1]
    if target_xys:
        d_avg = float(np.mean([np.hypot(x - x_mid, y - y_mid) for x, y in target_xys]))
    else:
        d_avg = 10.0
    feas = verify_scene_feasibility(cfg, h_avg, d_avg)

    # 11) meta.json
    n_shadow_px = int(shadow_masks.sum())
    n_target_px = int(target_masks.sum())
    meta = {
        "name": name,
        "title": title,
        "description": desc,
        "category": "feasible" if expected_feasible else "outlier",
        "config": {
            "z_s_m": float(cfg.traj.start_xyz[2]),
            "rho_max_m": float(cfg.sonar.range_max_m),
            "pitch_deg": float(np.degrees(cfg.traj.start_rpy[1])),
            "heave_m": float(cfg.traj.heave_amplitude_m),
            "forward_m": float(cfg.traj.forward_total_m),
            "speckle_sigma": float(cfg.sonar.speckle_sigma),
            "noise_floor_db": float(cfg.sonar.noise_floor_db),
            "fov_elev_deg": list(cfg.sonar.fov_elevation_deg),
            "beam_count": int(cfg.sonar.beam_count),
            "range_bin_count": int(cfg.sonar.range_bin_count),
        },
        "scene": {
            "n_pillars": len(world.pillars),
            "n_cubes": len(world.cubes),
            "n_spheres": len(world.spheres),
            "pillar_heights": [p.height for p in world.pillars],
            "cube_heights": [2 * c.half_size for c in world.cubes],
            "sphere_diameters": [2 * s.radius for s in world.spheres],
            "h_avg_m": h_avg,
            "d_avg_m": d_avg,
        },
        "feasibility": {
            "is_feasible": bool(feas.is_feasible),
            "h_max_m": float(feas.h_max),
            "elev_top_deg": float(np.degrees(feas.elev_top)),
            "L_s_m": float(feas.L_s) if np.isfinite(feas.L_s) else None,
            "L_s_clipped": bool(feas.L_s_clipped),
            "expected_feasible": bool(expected_feasible),
            "feas_match": bool(feas.is_feasible == expected_feasible),
        },
        "stats": {
            "n_frames": N,
            "n_keyframes": len(cfg.traj.keyframe_indices),
            "n_target_pixels_total": n_target_px,
            "n_shadow_pixels_total": n_shadow_px,
            "n_gt_surface_points": int(len(surface_pts)),
        },
        "gt_quality": {
            "max_dist_to_analytic_m": float(gt_q["max_dist_to_analytic"]),
            "max_normal_error_rad": float(gt_q["max_normal_error_rad"]),
            "std_over_mean_nn": float(gt_q["std_over_mean_nn"]),
            "std_over_mean_face_max": float(gt_q_face.get("std_over_mean_face_max", 0.0)) if gt_q_face.get("std_over_mean_face_max") is not None else None,
            "per_face_n": {k: v["n"] for k, v in gt_q_face.get("per_face", {}).items() if v["n"] > 0},
            "per_face_std_over_mean": {k: round(v["std_over_mean"], 3) for k, v in gt_q_face.get("per_face", {}).items() if v["std_over_mean"] is not None},
            "ok": bool(gt_q["ok"]),
            "ok_per_face": bool(gt_q_face.get("ok", False)),
        },
        "inversion": {
            "n_valid_pixels": int(valid_inv.sum()),
            "mae_v2_median_m": mae_v2,
            "rmse_v2_m": rmse_v2,
            "mae_v2_median_cm": mae_v2 * 100 if mae_v2 is not None else None,
            "mae_v2_noisy_median_m": mae_v2_noisy,
            "rmse_v2_noisy_m": rmse_v2_noisy,
            "mae_v2_noisy_median_cm": mae_v2_noisy * 100 if mae_v2_noisy is not None else None,
            "mae_v1_median_cm": mae_v1 * 100 if mae_v1 is not None else None,
        },
        "timing": {
            "shadow_s": round(t_shadow, 2),
            "render_s": round(t_render, 2),
            "gt_sample_s": round(t_gt, 2),
            "total_s": round(time.time() - t0, 2),
        },
    }
    with open(os.path.join(out_dir, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)

    # 12) README
    with open(os.path.join(out_dir, "README.md"), "w", encoding="utf-8") as f:
        f.write(f"# {title}\n\n")
        f.write(f"**目录**：`{name}/`  **类别**：`{'可行' if expected_feasible else '不可行（负例）'}`\n\n")
        f.write(f"## 用途\n\n{desc}\n\n")
        f.write("## 构型（§7.1）\n\n")
        f.write(f"- z_s = {meta['config']['z_s_m']:.1f} m\n")
        f.write(f"- ρ_max = {meta['config']['rho_max_m']:.1f} m\n")
        f.write(f"- θ_p = {meta['config']['pitch_deg']:.0f}°\n")
        f.write(f"- heave = {meta['config']['heave_m']:.1f} m\n")
        f.write(f"- forward = {meta['config']['forward_m']:.1f} m\n")
        f.write(f"- speckle σ = {meta['config']['speckle_sigma']:.2f}\n")
        f.write(f"- 噪声底 = {meta['config']['noise_floor_db']:.0f} dB\n\n")
        f.write("## 场景目标\n\n")
        f.write(f"- 柱: {meta['scene']['pillar_heights']} m\n")
        f.write(f"- 立方: {meta['scene']['cube_heights']} m\n")
        f.write(f"- 球: {meta['scene']['sphere_diameters']} m\n")
        f.write(f"- h_avg = {h_avg:.2f} m, d_avg = {d_avg:.2f} m\n\n")
        f.write("## 可反演性（T0.9 判据）\n\n")
        f.write(f"- 期望：{'可反演' if expected_feasible else '不可反演（负例）'}\n")
        f.write(f"- 实测：{'可反演' if feas.is_feasible else '不可反演'}（{ '匹配' if feas.is_feasible == expected_feasible else '不匹配' }）\n")
        f.write(f"- h_max = {feas.h_max:.2f} m（实际 h_avg = {h_avg:.2f} m）\n")
        f.write(f"- elev_top = {np.degrees(feas.elev_top):.1f}°\n")
        f.write(f"- L_s = {feas.L_s:.2f} m（被截断：{feas.L_s_clipped}）\n\n")
        f.write("## 数据规模\n\n")
        f.write(f"- 帧数: {N}, 关键帧: {meta['stats']['n_keyframes']}\n")
        f.write(f"- 目标像素: {n_target_px:,}, 阴影像素: {n_shadow_px:,}\n")
        f.write(f"- GT 表面点: {len(surface_pts):,}\n\n")
        f.write("## GT 质量（T0.10 验收）\n\n")
        f.write(f"- max_dist_to_analytic: {gt_q['max_dist_to_analytic']:.4f} m（阈值 1e-2 m）\n")
        f.write(f"- max_normal_error: {gt_q['max_normal_error_rad']:.6f} rad（阈值 1e-4 rad）\n")
        f.write(f"- std/mean_nn: {gt_q['std_over_mean_nn']:.3f}（阈值 0.3）\n")
        f.write(f"- 验收: {'PASS' if gt_q['ok'] else 'PARTIAL'}\n\n")
        f.write("## 反演精度（T0.7 + T0.8 验收）\n\n")
        f.write(f"- V2 精确式 MAE: {meta['inversion']['mae_v2_median_cm']} cm"
                f"{'（验收：≤5 cm 且非零）' if meta['inversion']['mae_v2_median_cm'] is not None else ''}\n")
        f.write(f"- V1 简化式 MAE: {meta['inversion']['mae_v1_median_cm']} cm（对照）\n\n")
        f.write("## 文件清单\n\n")
        f.write("- `gt/poses_gt.npy` (N, 4, 4) - 真值位姿\n")
        f.write("- `gt/surface_points.npy` (M, 3) - T0.10 GT 表面点\n")
        f.write("- `gt/surface_normals.npy` (M, 3) - T0.10 GT 表面法向\n")
        f.write("- `gt/sonar_images.npy` (N, H, W) - 渲染声呐图\n")
        f.write("- `gt/target_masks.npy` / `shadow_masks.npy` - 目标/阴影掩码\n")
        f.write("- `gt/height_gt_maps.npy` - 目标高度真值（仅 target_mask 处有值）\n")
        f.write("- `gt/D_t_map.npy` - 声呐到目标底部水平距离\n")
        f.write("- `innovation2/height_inverted.npy` - V2 精确反演高度\n")
        f.write("- `innovation2/sigma_height.npy` - 不确定度\n")
        f.write("- `innovation2/height_inverted_v1.npy` - V1 简化反演（对照）\n")
        f.write("- `meta.json` - 完整摘要\n")

    if verbose:
        print(f"  → 目标像素: {n_target_px:,}, 阴影像素: {n_shadow_px:,}")
        print(f"  → GT 表面: {len(surface_pts):,} 点, "
              f"max_dist={gt_q['max_dist_to_analytic']:.4f}m, "
              f"std/mean_nn={gt_q['std_over_mean_nn']:.3f}, "
              f"per-face_max={gt_q_face.get('std_over_mean_face_max', 0):.3f}")
        if mae_v2 is not None:
            mae_v2_noisy_str = f", V2_noisy = {mae_v2_noisy * 100:.2f} cm" if mae_v2_noisy is not None else ""
            mae_v1_str = f", V1 = {mae_v1 * 100:.2f} cm" if mae_v1 is not None else ""
            print(f"  → 反演 MAE: V2 = {mae_v2 * 100:.2f} cm{mae_v2_noisy_str}{mae_v1_str}")
        print(f"  → 耗时: shadow={t_shadow:.1f}s, render={t_render:.1f}s, "
              f"gt={t_gt:.1f}s, total={time.time() - t0:.1f}s")
    return meta


# ==========================================
# 跑批入口
# ==========================================
def main(only=None, out_root="./scene_set_v2"):
    """跑 S1-S6 全部 6 场景。"""
    os.makedirs(out_root, exist_ok=True)
    selected = SCENES_V2 if only is None else [
        s for s in SCENES_V2 if s[0] in only
    ]
    print(f"\n将生成 {len(selected)} 个场景到 {out_root}/\n")
    summaries = []
    for name, title, desc, factory, expected in selected:
        try:
            meta = generate_scene_v2(name, title, desc, factory, expected, out_root=out_root)
            summaries.append(meta)
        except Exception as e:
            import traceback
            traceback.print_exc()
            summaries.append({"name": name, "error": str(e)})
    # 写 summary
    with open(os.path.join(out_root, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summaries, f, indent=2, ensure_ascii=False, default=str)
    # 打印总览
    print(f"\n{'=' * 100}\n所有场景生成完成\n{'=' * 100}")
    print(f"{'场景':<35} {'feas':<6} {'匹配':<6} {'目标像素':<10} {'阴影像素':<10} "
          f"{'MAE_V2':<8} {'GT合格':<6} {'total_s':<8}")
    print("-" * 100)
    for s in summaries:
        if "error" in s:
            print(f"{s['name']:<35} ERROR: {s['error'][:60]}")
            continue
        feas_match = "OK" if s["feasibility"]["feas_match"] else "NO"
        feas_str = "feas" if s["feasibility"]["is_feasible"] else "infeas"
        mae_v2 = s["inversion"]["mae_v2_median_cm"]
        mae_str = f"{mae_v2:.2f}cm" if mae_v2 is not None else "N/A"
        gt_ok = "PASS" if s["gt_quality"]["ok"] else "PART"
        print(f"{s['name']:<35} {feas_str:<6} {feas_match:<6} "
              f"{s['stats']['n_target_pixels_total']:<10,} {s['stats']['n_shadow_pixels_total']:<10,} "
              f"{mae_str:<8} {gt_ok:<6} {s['timing']['total_s']:<8.1f}")
    print("=" * 100)


if __name__ == "__main__":
    import sys
    only = sys.argv[1:] if len(sys.argv) > 1 else None
    main(only=only)
