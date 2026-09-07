"""
S3_main_v3 修复：h=2.5 避开 C-II 越界，让主档 5/6 通过
======================================================

原 S3_main_single_mid (h=2.0):
  - elev_top = arctan((2.0-4.5)/16) = -8.88° 越界 ±7.5° → C-II 不可反演

V3 修复 (h=2.5):
  - elev_top = arctan((2.5-4.5)/16) = -7.13° ✓ 在 ±7.5° 内
  - margin = (4.5-2.5)/4.5 = 44.4% ✓

注：S3_main_single_mid (h=2.0) 保留作为"包线外判负"物理证据
   S3_main_v3 (h=2.5) 作为"中等高度良约束"消融场景
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


def make_S3_main_v3_factory():
    """S3_main_v3 主档 h=2.5 工厂（修复版）。"""
    def factory():
        cfg = Config(seed=403)
        cfg.sonar = SonarCfg(
            fov_elevation_deg=(-ARIS_MAIN["phi_max_deg"], ARIS_MAIN["phi_max_deg"]),
            fov_azimuth_deg=(-ARIS_MAIN["fov_azim_deg"] / 2, ARIS_MAIN["fov_azim_deg"] / 2),
            beam_count=ARIS_MAIN["n_beams"],
            range_bin_count=600,
            range_min_m=0.5,
            range_max_m=40.0,
        )
        cfg.noise = SensorNoiseCfg(
            sigma_theta_rad=np.deg2rad(0.18),
            sigma_rho_m=ARIS_MAIN["sigma_rho_m"],
        )
        # V3 修复：h=2.5（与 S1/S2/S4 同高，避开 C-II 越界）
        z_s, h, d, heave = 4.5, 2.5, 16.0, 1.2
        cfg.traj = TrajCfg(
            n_frames=120,
            keyframe_indices=list(range(0, 120, 5)),
            dt_s=0.20,
            motion_mode="general",
            start_xyz=(0.0, 0.0, z_s),
            start_rpy=(0.0, 0.0, 0.0),
            forward_total_m=0.0,
            sway_total_m=0.5,
            heave_amplitude_m=heave,
            pitch_amplitude_rad=0.10,
            yaw_amplitude_rad=0.20,
        )
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


def main():
    print("=" * 60)
    print("S3_main_v3 修复：h=2.5 避开 C-II 越界")
    print("=" * 60)
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    new_name = "S3_main_v3"
    title = f"主档·{new_name}"
    desc = (
        f"ARIS 主档 V3 修复: ±7.5° / 128 波束 / σ_ρ=1cm / ρ_max=40m. "
        f"几何 z_s=4.5, h=2.5, d=16 (elev_top=-7.13° < 7.5° ✓). "
        f"V3 修复：原 S3_main_single_mid h=2.0 因 C-II 越界不可反演, "
        f"本场景 h=2.5 让 5/6 主档通过 (含 S3 包线内消融)."
    )
    expected_feasible = True
    factory = make_S3_main_v3_factory()

    from gen_scenes_v2 import generate_scene_v2
    t0 = time.time()
    try:
        meta = generate_scene_v2(
            new_name, title, desc, factory, expected_feasible,
            out_root=str(OUT_ROOT), verbose=False,
        )
    except Exception as e:
        print(f"[ERR] {e}")
        import traceback
        traceback.print_exc()
        return None
    dt = time.time() - t0
    print(f"耗时 {dt:.1f}s")

    # 标 aperture_tier + 标 V3 修复
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
        meta["snr_tier"] = "normal"
        meta["version"] = "v3"
        meta["supersedes"] = "S3_main_single_mid (h=2.0, C-II 越界)"
        meta["aperture_note"] = (
            "S3 V3 修复：ARIS ±7.5° / 128 波束 / σ_ρ=1cm / ρ_max=40m. "
            "h=2.5 (与 S1/S2/S4 同高) 让 elev_top=-7.13° 落在 ±7.5° 内, "
            "替代 h=2.0 (C-II 越界). 让 5/6 主档场景通过."
        )
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2, ensure_ascii=False, default=str)
        print(f"已标 aperture_tier=main_aris_7p5deg + version=v3 + supersedes=S3_main_single_mid")

    # 打印关键字段
    print(f"\n=== S3_main_v3 验收 ===")
    print(f"  feas: {meta.get('feasibility', {}).get('is_feasible')}")
    print(f"  h_max: {meta.get('feasibility', {}).get('h_max_m'):.2f}m")
    print(f"  elev_top: {meta.get('feasibility', {}).get('elev_top_deg'):.2f}°")
    h_pillar = meta.get('scene', {}).get('h_avg_m', 1)
    h_max = meta.get('feasibility', {}).get('h_max_m', 0)
    margin = (h_max - h_pillar) / h_max * 100 if h_max > 0 else 0
    print(f"  h_pillar: {h_pillar}m, margin: {margin:.1f}%")
    mae = meta.get('inversion', {}).get('mae_v2_median_m')
    mae_noisy = meta.get('inversion', {}).get('mae_v2_noisy_median_m')
    mae_s = f"{mae*100:.2f}cm" if mae is not None else "N/A"
    mae_noisy_s = f"{mae_noisy*100:.2f}cm" if mae_noisy is not None else "N/A"
    print(f"  MAE_V2: {mae_s}")
    print(f"  MAE_V2_noisy: {mae_noisy_s}")
    return meta


if __name__ == "__main__":
    main()
