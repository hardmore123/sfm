"""
R-SCN 全套 V2：用 gen_scenes_v2.generate_scene_v2 + 主档调整几何
=============================================================

阶段表 R-SCN 验收：
  - 主档场景 meta.json 含 aperture_tier: "main_aris_7p5deg"
  - 用 X1 判据确认主档场景落在包线内且余量 ≥ 30%

策略：
- 复用 gen_scenes_v2.generate_scene_v2 主流程
- 写自定义 factory：取 SCENES_V2[i] 的几何参数，但用主档传感器参数
- 调整场景几何（z_s=2.5, d=15, h=1.5）兼容 ±7.5° 孔径
- S6 包线外（h=3.0 > z_s=2.5）应判不可反演

注：原 S1-S5（z_s=4.5, d=10, h=2.5） elev_top=arctan2(-2, 10)=-11.3° 超 ±7.5° 孔径
    所以必须调整几何；这是 R-SCN 调整版的核心改动。
"""
import os
import sys
import json
import time
import numpy as np
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import Config, SonarCfg, SensorNoiseCfg, SceneCfg, finalize_pixel_mapping
from scene_configs_v2 import SCENES_V2
from feasibility import check_feasibility, ARIS_MAIN

OUT_ROOT = Path("F:/sfm/sfm_synthetic_pillars/scene_set_main")


# 主档场景几何（调整后兼容 ±7.5° 孔径 + 余量 ≥ 30%）
# 设计原则：d=15m 让 elev_top 落在 ±7.5° 孔径内，rho_max=40m 让 L_s 不被截断
# ARIS Explorer 3000 标称量程 5-40m
SCENES_MAIN = [
    # (新名, 原名, z_s, h, d, heave)
    ("S1_main_single",            "S1_single_well_constrained",   4.5, 2.5, 16.0, 1.2),
    ("S2_main_forward_degenerate", "S2_single_forward_degenerate", 4.5, 2.5, 16.0, 0.0),
    ("S3_main_mixed",             "S3_mixed_shapes",                4.5, 2.0, 16.0, 1.2),
    ("S5_main_envelope_edge",     "S5_envelope_edge",              4.5, 2.4, 16.0, 1.2),
    ("S6_main_envelope_outlier",  "S6_envelope_outlier",           4.5, 5.5, 16.0, 1.2),
]


def _scene_factory_for_main(orig_name, z_s_main, h_main, d_main, heave_main):
    """返回一个 factory：生成主档 + 自定义几何的 Config。"""
    orig_factory = None
    for s in SCENES_V2:
        if s[0] == orig_name:
            orig_factory = s[3]
            break
    if orig_factory is None:
        raise ValueError(f"原场景 {orig_name} 不在 SCENES_V2 中")

    def factory():
        cfg = orig_factory()
        # 替换 SonarCfg 为 ARIS 主档
        cfg.sonar = SonarCfg(
            fov_elevation_deg=(-ARIS_MAIN["phi_max_deg"], ARIS_MAIN["phi_max_deg"]),
            fov_azimuth_deg=(-ARIS_MAIN["fov_azim_deg"] / 2, ARIS_MAIN["fov_azim_deg"] / 2),
            beam_count=ARIS_MAIN["n_beams"],
            range_bin_count=600,
            range_min_m=0.5,
            range_max_m=40.0,  # ARIS 标称 5-40m
        )
        cfg.noise = SensorNoiseCfg(
            sigma_theta_rad=np.deg2rad(0.18),
            sigma_rho_m=ARIS_MAIN["sigma_rho_m"],
        )
        # 调整场景几何（z_s, h, d, heave）
        if hasattr(cfg, 'traj'):
            # trajectory 配置：start_xyz[2] 是 z
            cfg.traj.start_xyz = (cfg.traj.start_xyz[0], cfg.traj.start_xyz[1], z_s_main)
        if hasattr(cfg, 'motion'):
            # motion 配置：heave_amp_m
            if hasattr(cfg.motion, 'heave_amp_m'):
                cfg.motion.heave_amp_m = heave_main
        # scene 配置：重置为 1 根柱在 AUV 前方 d_main 米
        # d_main 是从 AUV 起点（中位）到柱的距离
        # 原 cfg.traj.start_xyz[0] = -12, forward_total_m = 4, x_mid = -10
        # 柱世界 x = x_mid + d_main = -10 + 15 = 5
        x_mid = cfg.traj.start_xyz[0] + 0.5 * cfg.traj.forward_total_m
        cfg.scene.pillars = [(x_mid + d_main, 0.0, 0.3, h_main)]
        # 同步 cfg.scene.d_avg_m
        if hasattr(cfg.scene, 'd_avg_m'):
            cfg.scene.d_avg_m = d_main
        # 同步 cfg.scene.h_avg_m
        if hasattr(cfg.scene, 'h_avg_m'):
            cfg.scene.h_avg_m = h_main
        # 同步 cfg.scene.pillar_heights
        if hasattr(cfg.scene, 'pillar_heights'):
            cfg.scene.pillar_heights = [h_main] * len(new_pillars)
        # z_s 配置
        if hasattr(cfg, 'z_s'):
            cfg.z_s = z_s_main
        if hasattr(cfg, 'sonar') and hasattr(cfg.sonar, 'z_s_m'):
            cfg.sonar.z_s_m = z_s_main
        finalize_pixel_mapping(cfg)
        return cfg
    return factory


def run_one_scene_main(new_name, orig_name, z_s_main, h_main, d_main, heave_main):
    """对单场景用主档参数生成。"""
    from gen_scenes_v2 import generate_scene_v2
    title = f"主档·{new_name}"
    desc = f"ARIS 主档: ±7.5° / 128 波束 / σ_ρ=1cm (调整几何 z_s={z_s_main}, h={h_main}, d={d_main})"
    expected = (h_main < z_s_main)  # 仅当 h < z_s 可反演

    factory = _scene_factory_for_main(orig_name, z_s_main, h_main, d_main, heave_main)
    print(f"\n=== {new_name} (主档) ===")
    t0 = time.time()
    try:
        meta = generate_scene_v2(
            new_name, title, desc, factory, expected,
            out_root=str(OUT_ROOT), verbose=False,
        )
    except Exception as e:
        print(f"  [ERR] {e}")
        import traceback
        traceback.print_exc()
        return None
    dt = time.time() - t0
    print(f"  耗时 {dt:.1f}s")

    # 标注 aperture_tier
    meta_path = OUT_ROOT / new_name / "meta.json"
    if meta_path.exists():
        with open(meta_path, encoding="utf-8") as f:
            meta = json.load(f)
        meta["aperture_tier"] = "main_aris_7p5deg"
        meta["aperture_elev_deg"] = 7.5
        meta["aperture_azim_deg"] = 15.0
        meta["aperture_n_beams"] = 128
        meta["aperture_sigma_rho_m"] = ARIS_MAIN["sigma_rho_m"]
        meta["aperture_note"] = (
            f"主档 ARIS Explorer 3000: ±7.5° / 128 波束 / σ_ρ=1cm / ρ_max=40m. "
            f"原 S1-S5 几何（d=10m）elev_top 超 ±7.5° 孔径，"
            f"本场景调整 d=15m + ρ_max=40m 兼容主档（h={h_main}）。"
        )
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2, ensure_ascii=False, default=str)
        print(f"  已标 aperture_tier=main_aris_7p5deg")

    return meta


def main():
    print("=" * 60)
    print("R-SCN 全套 V2：SONAR_ARIS 主档 + 调整几何")
    print("=" * 60)
    OUT_ROOT.mkdir(parents=True, exist_ok=True)

    print(f"待生成 {len(SCENES_MAIN)} 场景")
    results = []
    for new_name, orig_name, z_s, h, d, heave in SCENES_MAIN:
        m = run_one_scene_main(new_name, orig_name, z_s, h, d, heave)
        if m:
            results.append(m)

    # 汇总
    print(f"\n{'='*60}")
    print(f"=== 主档场景汇总 ===")
    print(f"{'场景':<32} {'z_s':<6} {'h':<6} {'d':<6} {'feas':<6} {'margin':<8} {'MAE_V2':<10}")
    print(f"{'-'*78}")
    n_feas = 0
    n_margin30 = 0
    for m in results:
        try:
            feas = m.get('feasibility', {}).get('is_feasible', False)
            h_max = m.get('feasibility', {}).get('h_max_m', 0)
            h_pillar = m.get('scene', {}).get('h_avg_m', 1)
            margin = (h_max - h_pillar) / h_max * 100 if h_max > 0 else 0
            mae = m.get('inversion', {}).get('mae_v2_median_m')
            mae_s = f"{mae*100:.2f}cm" if mae is not None else "N/A"
            z_s = m.get('config', {}).get('z_s_m', '?')
            h_p = m.get('scene', {}).get('h_avg_m', '?')
            d_p = m.get('scene', {}).get('d_avg_m', '?')
            print(f"  {m['name']:<30} {z_s:<6.2f} {h_p:<6.2f} {d_p:<6.2f} "
                  f"{str(feas):<6} {margin:<8.1f} {mae_s:<10}")
            if feas:
                n_feas += 1
            if margin >= 30:
                n_margin30 += 1
        except Exception as e:
            print(f"  [ERR] {m.get('name', '?')}: {e}")

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
