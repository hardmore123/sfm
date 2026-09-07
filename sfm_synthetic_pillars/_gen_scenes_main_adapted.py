"""
R-SCN 调整版：主档兼容几何
============================

物理现实：ARIS 主档 ±7.5° 仰角孔径对 z_s=4.5m + d=10m + h=2.5m 场景不兼容
（elev_top = arctan2(-2, 10) = -11.3° > 7.5°，越界）

调整方案：
- 减小 z_s 到 2.5m（半 AUV 高度）
- 增大 d 到 15m（更远距离）
- 降低 h 到 1.5m（更矮目标）
- → elev_top = arctan2(1.5-2.5, 15) = -3.8°（在 ±7.5° 孔径内）

调整后场景 S1_main, S2_main, ..., S6_main（用 SONAR_ARIS 主档 + 新几何）

策略：
- 保留原 S1-S5 几何（标注 sensitivity_17deg）
- 新增 S1_main-S5_main 几何（标注 main_aris_7p5deg）
- S6（包线外负例）保留 h=5.5m，应判不可反演（验证 C-IV h>=z_s 仍工作）
"""
import os
import sys
import json
import time
import numpy as np
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import Config, SonarCfg, SensorNoiseCfg, SceneCfg, finalize_pixel_mapping
from feasibility import check_feasibility
from feasibility import ARIS_MAIN

OUT_ROOT = Path("F:/sfm/sfm_synthetic_pillars/scene_set_main")

# ARIS 主档
SONAR_ARIS_MAIN = {
    "fov_elevation_deg": (-ARIS_MAIN["phi_max_deg"], ARIS_MAIN["phi_max_deg"]),
    "fov_azimuth_deg": (-ARIS_MAIN["fov_azim_deg"] / 2, ARIS_MAIN["fov_azim_deg"] / 2),
    "beam_count": ARIS_MAIN["n_beams"],
    "range_bin_count": 600,
    "range_max_m": 25.0,
    "sigma_rho_m": ARIS_MAIN["sigma_rho_m"],
}

# 主档兼容场景几何（调整后）
SCENES_MAIN = {
    "S1_main_single": {
        "title": "主档·单目标良约束",
        "desc": "ARIS 主档 + 调整几何 (z_s=2.5, d=15, h=1.5) — 落在 ±7.5° 孔径内",
        "expected_feasible": True,
        "z_s_m": 2.5,
        "rho_max_m": 25.0,
        "h_pillar": 1.5,
        "d_pillar": 15.0,
    },
    "S2_main_forward_degenerate": {
        "title": "主档·forward 退化",
        "desc": "ARIS 主档 + forward 退化 (z_s=2.5, d=15, h=1.5, heave=0)",
        "expected_feasible": True,
        "z_s_m": 2.5,
        "rho_max_m": 25.0,
        "h_pillar": 1.5,
        "d_pillar": 15.0,
        "heave_amp": 0.0,
    },
    "S3_main_mixed": {
        "title": "主档·多形状混合",
        "desc": "ARIS 主档 + 3 目标混合",
        "expected_feasible": True,
        "z_s_m": 2.5,
        "h_pillar": 1.2,
        "d_pillar": 12.0,
    },
    "S5_main_envelope_edge": {
        "title": "主档·包线边缘",
        "desc": "ARIS 主档 + h=1.4m 接近 h_max (z_s=2.5, d=15)",
        "expected_feasible": True,
        "z_s_m": 2.5,
        "h_pillar": 1.4,
        "d_pillar": 15.0,
    },
    "S6_main_envelope_outlier": {
        "title": "主档·包线外负例",
        "desc": "ARIS 主档 + h=3.0m > z_s=2.5m（应判不可反演）",
        "expected_feasible": False,
        "z_s_m": 2.5,
        "h_pillar": 3.0,
        "d_pillar": 12.0,
    },
}


def build_main_config(name, scene_def):
    """构建 ARIS 主档 Config。"""
    cfg = Config()
    cfg.name = name

    # SonarCfg
    cfg.sonar = SonarCfg(
        fov_elevation_deg=SONAR_ARIS_MAIN["fov_elevation_deg"],
        fov_azimuth_deg=SONAR_ARIS_MAIN["fov_azimuth_deg"],
        beam_count=SONAR_ARIS_MAIN["beam_count"],
        range_bin_count=SONAR_ARIS_MAIN["range_bin_count"],
        range_min_m=0.5,
        range_max_m=SONAR_ARIS_MAIN["range_max_m"],
    )
    cfg.noise = SensorNoiseCfg(
        sigma_theta_rad=np.deg2rad(0.18),
        sigma_rho_m=SONAR_ARIS_MAIN["sigma_rho_m"],
    )
    # 调整场景几何
    cfg.scene = SceneCfg(
        pillars=[(scene_def["d_pillar"], 0.0, 0.3, scene_def["h_pillar"])],
    )
    # 运动参数
    cfg.motion = cfg.motion if hasattr(cfg, 'motion') else None
    # 设 z_s
    if not hasattr(cfg, 'traj'):
        # 用 motion 字典设 start_xyz
        pass
    # 直接设 cfg 字段
    cfg.z_s = scene_def["z_s_m"]
    finalize_pixel_mapping(cfg)
    return cfg


def generate_main_scene(name, scene_def):
    """生成单场景（直接调核心函数）。"""
    from world import SceneWorld
    from trajectory import make_poses
    from sonar_render import render_all_frames
    from shadow import render_all_shadow_maps
    from height_inversion import (
        invert_height_precise_from_pixels,
        invert_height_from_shadow_pixels,
    )
    from gt_surface import sample_gt_surface, verify_sample_quality_per_face
    from eval_surface import volumetric_error

    cfg = build_main_config(name, scene_def)
    out_dir = OUT_ROOT / name
    gt_dir = out_dir / "gt"
    inv2_dir = out_dir / "innovation2"
    for d in [out_dir, gt_dir, inv2_dir]:
        d.mkdir(parents=True, exist_ok=True)

    # 设 z_s / heave 到 cfg 顶层字段
    z_s = scene_def["z_s_m"]
    heave_amp = scene_def.get("heave_amp", 1.0)
    h_pillar = scene_def["h_pillar"]
    d_pillar = scene_def["d_pillar"]
    rho_max = scene_def["rho_max_m"]
    n_frames = 20

    # 生成 poses（手写）
    poses6 = np.zeros((n_frames, 6))
    t = np.linspace(0, 1, n_frames)
    poses6[:, 0] = -d_pillar - 4   # AUV x
    poses6[:, 1] = 0.0
    poses6[:, 2] = z_s + heave_amp * np.sin(2 * np.pi * t)
    poses6[:, 3] = 0.0
    poses6[:, 4] = 0.0
    poses6[:, 5] = 0.0
    poses_T = np.zeros((n_frames, 4, 4))
    from trajectory import euler_to_matrix
    for i in range(n_frames):
        T = np.eye(4)
        T[:3, :3] = euler_to_matrix(poses6[i, 3], poses6[i, 4], poses6[i, 5])
        T[:3, 3] = poses6[i, :3]
        poses_T[i] = T

    # 设 cfg.scene pillar（1 根柱在 d=d_pillar）
    cfg.scene = SceneCfg(
        pillars=[(d_pillar, 0.0, 0.3, h_pillar)],
    )

    # 仿真
    world = SceneWorld(cfg)
    sonar_imgs, target_masks = render_all_frames(world, poses_T, cfg, rng_seed=42)
    shadow_masks, shadow_lengths = render_all_shadow_maps(
        world, poses_T, cfg,
        render_target_masks=target_masks,
        n_elev_render=15, n_elev_shadow=25,
    )
    target_elev_maps = np.zeros_like(sonar_imgs)
    h_gt_maps = np.zeros_like(sonar_imgs)
    D_t_map = np.zeros_like(sonar_imgs)
    for i in range(n_frames):
        P_auv = poses_T[i, :3, 3]
        for c in range(cfg.sonar.beam_count):
            beam_angle = np.deg2rad(-15 + 30 * c / max(cfg.sonar.beam_count - 1, 1))
            for r in range(cfg.sonar.range_bin_count):
                rho = 0.5 + 25.0 * r / max(cfg.sonar.range_bin_count - 1, 1)
                P_hit = P_auv + np.array([rho * np.cos(beam_angle),
                                            rho * np.sin(beam_angle),
                                            -np.tan(np.deg2rad(0)) * rho])
                P_hit[2] = poses_T[i, 2, 3]  # 保持 AUV z
                d_to_pillar = np.sqrt((P_hit[0] - d_pillar)**2 + P_hit[1]**2)
                if d_to_pillar < 0.3 and target_masks[i, r, c]:
                    h_gt_maps[i, r, c] = h_pillar
                    target_elev_maps[i, r, c] = np.arctan2(poses_T[i, 2, 3] - h_pillar,
                                                          np.sqrt((P_hit[0] - d_pillar)**2 + P_hit[1]**2))
                # 简化 D_t
                D_t_map[i, r, c] = rho

    # GT 表面采样
    surface_pts, surface_normals = sample_gt_surface(world, n_per_object=1500)
    # 反演 V2
    h_inv, sigma_h = invert_height_precise_from_pixels(
        shadow_lengths, D_t_map, target_elev_maps, target_masks, z_s,
        sigma_rho=SONAR_ARIS_MAIN["sigma_rho_m"],
        sigma_D=0.05, sigma_elev=np.deg2rad(0.5), sigma_z=0.05,
    )
    h_inv_v1 = invert_height_from_shadow_pixels(
        shadow_lengths, D_t_map, target_elev_maps, target_masks, z_s,
    )

    # 保存
    np.save(gt_dir / "poses_gt.npy", poses_T)
    np.save(gt_dir / "sonar_images.npy", sonar_imgs)
    np.save(gt_dir / "target_masks.npy", target_masks)
    np.save(gt_dir / "shadow_masks.npy", shadow_masks)
    np.save(gt_dir / "height_gt_maps.npy", h_gt_maps)
    np.save(gt_dir / "target_elev_maps.npy", target_elev_maps)
    np.save(gt_dir / "shadow_length_maps.npy", shadow_lengths)
    np.save(gt_dir / "D_t_map.npy", D_t_map)
    np.save(gt_dir / "surface_points.npy", surface_pts)
    np.save(gt_dir / "surface_normals.npy", surface_normals)
    np.save(inv2_dir / "height_inverted.npy", h_inv)
    np.save(inv2_dir / "sigma_height.npy", sigma_h)
    np.save(inv2_dir / "height_inverted_v1.npy", h_inv_v1)

    # meta
    n_target_total = int(target_masks.sum())
    n_shadow_total = int(shadow_masks.sum())
    valid = target_masks & np.isfinite(h_inv) & np.isfinite(h_gt_maps)
    if valid.sum() > 0:
        err = np.abs(h_inv[valid] - h_gt_maps[valid])
        mae_v2 = float(np.median(err))
    else:
        mae_v2 = None

    # 可反演判定
    r_feas = check_feasibility(z_s, rho_max, 0, np.deg2rad(7.5), np.deg2rad(7.5),
                                d_pillar, h_pillar)
    h_max = r_feas.h_max
    margin = (h_max - h_pillar) / h_max * 100 if h_max > 0 else 0

    meta = {
        "name": name,
        "title": scene_def["title"],
        "description": scene_def["desc"],
        "category": "feasible" if r_feas.is_feasible else "infeasible",
        "config": {
            "z_s_m": z_s,
            "rho_max_m": rho_max,
            "fov_elev_deg": [-7.5, 7.5],
            "fov_azim_deg": [-15, 15],
            "beam_count": 128,
            "sigma_rho_m": SONAR_ARIS_MAIN["sigma_rho_m"],
            "heave_m": heave_amp,
        },
        "scene": {
            "n_pillars": 1,
            "h_avg_m": h_pillar,
            "d_avg_m": d_pillar,
        },
        "feasibility": {
            "is_feasible": r_feas.is_feasible,
            "h_max_m": h_max,
            "margin_pct": margin,
            "binding": r_feas.binding_constraint,
        },
        "stats": {
            "n_frames": n_frames,
            "n_target_pixels_total": n_target_total,
            "n_shadow_pixels_total": n_shadow_total,
        },
        "inversion": {
            "n_valid_pixels": int(valid.sum()),
            "mae_v2_median_m": mae_v2,
        },
        "aperture_tier": "main_aris_7p5deg",
        "aperture_elev_deg": 7.5,
        "aperture_azim_deg": 15.0,
        "aperture_n_beams": 128,
        "aperture_sigma_rho_m": SONAR_ARIS_MAIN["sigma_rho_m"],
        "aperture_note": "主档 ARIS Explorer 3000: ±7.5° / 128 波束 / σ_ρ=1cm",
    }
    with open(out_dir / "meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False, default=str)
    return meta


def main():
    print("=" * 60)
    print("R-SCN 全套：SONAR_ARIS 主档（调整几何）")
    print("=" * 60)
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    results = []
    for name, scene_def in SCENES_MAIN.items():
        print(f"\n=== {name} ===")
        t0 = time.time()
        try:
            meta = generate_main_scene(name, scene_def)
            dt = time.time() - t0
            print(f"  耗时 {dt:.1f}s")
            print(f"  可反演: {meta['feasibility']['is_feasible']}, "
                  f"h_max={meta['feasibility']['h_max_m']:.2f}m, "
                  f"余量={meta['feasibility']['margin_pct']:.1f}%, "
                  f"binding={meta['feasibility']['binding']}")
            if meta['inversion']['mae_v2_median_m']:
                print(f"  V2 MAE: {meta['inversion']['mae_v2_median_m']*100:.2f}cm")
            results.append(meta)
        except Exception as e:
            print(f"  [ERR] {e}")
            import traceback
            traceback.print_exc()

    # 汇总
    print(f"\n{'='*60}")
    print(f"=== 主档场景汇总 ===")
    print(f"{'场景':<32} {'z_s':<6} {'h_pillar':<10} {'d':<6} {'feas':<6} {'margin':<8} {'MAE_V2':<10}")
    print(f"{'-'*78}")
    for m in results:
        mae = m['inversion']['mae_v2_median_m']
        mae_s = f"{mae*100:.2f}cm" if mae else "N/A"
        print(f"  {m['name']:<30} {m['config']['z_s_m']:<6.2f} {m['scene']['h_avg_m']:<10.2f} "
              f"{m['scene']['d_avg_m']:<6.2f} {str(m['feasibility']['is_feasible']):<6} "
              f"{m['feasibility']['margin_pct']:<8.1f} {mae_s:<10}")

    n_feas = sum(1 for m in results if m['feasibility']['is_feasible'])
    n_margin30 = sum(1 for m in results if m['feasibility']['margin_pct'] >= 30)
    print(f"\n  可反演: {n_feas}/{len(results)}")
    print(f"  余量 ≥ 30%: {n_margin30}/{len(results)}")

    # 落盘
    out_path = Path("R_SCN_MAIN_RESULTS.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"results": results, "n_feasible": n_feas, "n_margin_30": n_margin30},
                  f, indent=2, ensure_ascii=False, default=str)
    print(f"\n[ok] 落盘 {out_path}")


if __name__ == "__main__":
    main()
