"""
R-SCN V2：5 主档场景独立 factory（不依赖 SCENES_V2）
====================================================

R-X6/S3 修复：
- 原 _gen_scenes_main.py 第 94 行有 NameError（new_pillars 未定义）
- S3 用了 SCENES_V2 的 make_S3_mixed_shapes（柱+方+球），被 pillars 覆盖后 h_avg_m 计算混乱

V2 改法：
- 5 场景全部从零构造 Config，**不依赖 SCENES_V2 的任何 factory**
- S3 主档保持单柱 h=2.0（与原设计 h_main 一致）
- S6 保持 h=5.5 > z_s=4.5 验证负例判据

ARIS Explorer 3000 主档参数（来自 R-X1）：
- ±7.5° 仰角孔径（主档，非敏感性档）
- ±15° 方位孔径
- 128 波束
- σ_ρ = 1cm
- ρ_max = 40m

主档场景几何（调整后兼容 ±7.5° 孔径 + 余量 ≥ 30%）：
- d=16m（让 elev_top 落在 ±7.5° 孔径内）
- z_s=4.5
- ρ_max=40m（让 L_s 不被截断）
"""
import os
import sys
import json
import time
import numpy as np
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import Config, SonarCfg, SensorNoiseCfg, SceneCfg, TrajCfg, finalize_pixel_mapping
from feasibility import check_feasibility, ARIS_MAIN

OUT_ROOT = Path("F:/sfm/sfm_synthetic_pillars/scene_set_main")


def make_main_factory(name, z_s, h, d, heave, seed=400):
    """
    返回一个 factory：构造主档 + 单柱 + 自定义几何的 Config。

    参数：
        name: 场景名
        z_s:  AUV 中心 z 高度
        h:    单柱高度
        d:    柱到 AUV 起点的水平距离
        heave: 升沉幅度
        seed: 随机种子
    """
    def factory():
        cfg = Config(seed=seed)
        # 主档 ARIS 传感器
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
        # 场景：单柱
        # 设计：柱在世界 (d, 0, 0)，AUV 起点 (0, 0, z_s)，forward=0 原地起伏
        #     sim_pipeline x_mid = 0，d_avg = |0 - d| = d（精确匹配）
        #     AUV 朝向 +x，柱始终在正前方（FOV ±15° 内）
        cfg.traj = TrajCfg(
            n_frames=120,
            keyframe_indices=list(range(0, 120, 5)),
            dt_s=0.20,
            motion_mode="general" if heave > 0 else "forward",
            start_xyz=(0.0, 0.0, z_s),  # AUV 在原点
            start_rpy=(0.0, 0.0, 0.0),  # 朝 +x（向柱方向）
            forward_total_m=0.0,         # 原地起伏（不前进）
            sway_total_m=0.5,
            heave_amplitude_m=heave,
            pitch_amplitude_rad=0.10,
            yaw_amplitude_rad=0.20,
        )
        # 柱在 (d, 0, 0.3)
        cfg.scene = SceneCfg(
            scene_type="pillar",
            pillars=[(d, 0.0, 0.3, h)],
            floor_z_m=0.0,
            surface_z_m=z_s + 1.0,
        )
        cfg.scene.h_avg_m = h
        cfg.scene.d_avg_m = d
        finalize_pixel_mapping(cfg)
        return cfg
    return factory


# 主档场景（独立定义，不再走 SCENES_V2）
SCENES_MAIN_V2 = [
    # (新名, z_s, h, d, heave, seed, expected_feasible)
    ("S1_main_single",              4.5, 2.5, 16.0, 1.2, 401, True),   # 良约束（与 S1 几何一致）
    ("S2_main_forward_degenerate",  4.5, 2.5, 16.0, 0.0, 402, True),   # forward 退化（无 heave）
    ("S3_main_single_mid",          4.5, 2.0, 16.0, 1.2, 403, True),   # 中等 h 良约束（修复版：单柱 h=2.0）
    ("S5_main_envelope_edge",       4.5, 2.4, 16.0, 1.2, 405, True),   # 包线边 0.9h_max
    ("S6_main_envelope_outlier",    4.5, 5.5, 16.0, 1.2, 406, False),  # 包线外 h>z_s
]


def run_one_scene_v2(new_name, z_s, h, d, heave, seed, expected_feasible):
    """对单场景用主档参数生成。"""
    from gen_scenes_v2 import generate_scene_v2
    title = f"主档·{new_name}"
    desc = f"ARIS 主档: ±7.5° / 128 波束 / σ_ρ=1cm / ρ_max=40m. 几何 z_s={z_s}, h={h}, d={d}, heave={heave}."
    factory = make_main_factory(new_name, z_s, h, d, heave, seed)
    print(f"\n=== {new_name} (主档 V2) ===")
    t0 = time.time()
    try:
        meta = generate_scene_v2(
            new_name, title, desc, factory, expected_feasible,
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
        meta["aperture_rho_max_m"] = 40.0
        meta["aperture_note"] = (
            f"V2 独立 factory: 主档 ARIS ±7.5° / 128 波束 / σ_ρ=1cm / ρ_max=40m. "
            f"几何 z_s={z_s}, h={h}, d={d} 兼容主档（elev_top = arctan((h-z_s)/d) = "
            f"{np.degrees(np.arctan2(h - z_s, d)):.2f}°). "
        )
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2, ensure_ascii=False, default=str)
        print(f"  已标 aperture_tier=main_aris_7p5deg")
    return meta


def main():
    print("=" * 60)
    print("R-SCN V2：5 主档场景（独立 factory，不走 SCENES_V2）")
    print("=" * 60)
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    print(f"待生成 {len(SCENES_MAIN_V2)} 场景")

    # 清理旧 S3 主档（如果存在）
    s3_old = OUT_ROOT / "S3_main_mixed"
    if s3_old.exists():
        # 用 rename 标记为废弃，不删除
        deprecated = OUT_ROOT / "S3_main_mixed_DEPRECATED"
        if not deprecated.exists():
            s3_old.rename(deprecated)
            print(f"  已重命名旧 S3_main_mixed -> S3_main_mixed_DEPRECATED")

    results = []
    for new_name, z_s, h, d, heave, seed, exp_feas in SCENES_MAIN_V2:
        m = run_one_scene_v2(new_name, z_s, h, d, heave, seed, exp_feas)
        if m:
            results.append(m)

    # 汇总
    print(f"\n{'='*60}")
    print(f"=== 主档 V2 汇总 ===")
    print(f"{'场景':<32} {'z_s':<6} {'h':<6} {'d':<6} {'feas':<6} {'margin':<8} {'MAE_V2':<10}")
    print(f"{'-'*78}")
    n_feas = 0
    n_margin30 = 0
    n_correct_neg = 0
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
            if not feas and m['name'] == 'S6_main_envelope_outlier':
                n_correct_neg += 1
        except Exception as e:
            print(f"  [ERR] {m.get('name', '?')}: {e}")

    print(f"\n  可反演: {n_feas}/{len(results)}")
    print(f"  余量 ≥ 30%: {n_margin30}/{len(results)}")
    print(f"  S6 负例正确判: {n_correct_neg}/1")

    out_path = Path("R_SCN_MAIN_RESULTS.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"results": results, "n_feasible": n_feas, "n_margin_30": n_margin30,
                  "n_correct_neg_S6": n_correct_neg, "version": "v2"},
                  f, indent=2, ensure_ascii=False, default=str)
    print(f"\n[ok] 落盘 {out_path}")


if __name__ == "__main__":
    main()
