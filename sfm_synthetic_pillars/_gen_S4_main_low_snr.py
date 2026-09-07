"""
S4_main_low_snr 生成：主档 ±7.5° / 128 波束 / σ_ρ=1cm / 低 SNR
================================================================

设计：
  - h=2.5, z_s=4.5, d=16, heave=1.2（与 S1 主档同几何）
  - speckle=0.35, noise_floor=55dB（与 sensitivity 档 S4 同 SNR）
  - 验证主档硬件 + 低 SNR 条件下的可反演性

声呐专家角度：
  - 主档 ±7.5° 孔径 + 低 SNR 组合是真实作业的常见工况
  - 与 sensitivity 档 S4 形成"硬件物理 vs 算法性能"对照
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


def make_S4_main_low_snr_factory():
    """S4_main_low_snr 主档低 SNR 工厂。"""
    def factory():
        cfg = Config(seed=404)
        cfg.sonar = SonarCfg(
            fov_elevation_deg=(-ARIS_MAIN["phi_max_deg"], ARIS_MAIN["phi_max_deg"]),
            fov_azimuth_deg=(-ARIS_MAIN["fov_azim_deg"] / 2, ARIS_MAIN["fov_azim_deg"] / 2),
            beam_count=ARIS_MAIN["n_beams"],
            range_bin_count=600,
            range_min_m=0.5,
            range_max_m=40.0,
            speckle_sigma=0.35,         # 关键：与 sensitivity S4 同
            noise_floor_db=55.0,        # 关键：与 sensitivity S4 同
        )
        cfg.noise = SensorNoiseCfg(
            sigma_theta_rad=np.deg2rad(0.18),
            sigma_rho_m=ARIS_MAIN["sigma_rho_m"],
            p_false_alarm=0.05,        # 关键：低 SNR 增加误检
            p_miss=0.10,                # 关键：低 SNR 增加漏检
        )
        # 几何：与 S1 主档一致（h=2.5, d=16, z_s=4.5, heave=1.2）
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
    print("S4_main_low_snr 生成：主档 ±7.5° / 128 波束 / 低 SNR")
    print("=" * 60)
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    new_name = "S4_main_low_snr"
    title = f"主档·{new_name}"
    desc = (
        f"ARIS 主档 + 低 SNR: ±7.5° / 128 波束 / σ_ρ=1cm / ρ_max=40m. "
        f"speckle=0.35, 噪声底 55dB, p_false_alarm=0.05, p_miss=0.10. "
        f"几何 z_s=4.5, h=2.5, d=16 (elev_top=-7.13° < 7.5° ✓)."
    )
    expected_feasible = True
    factory = make_S4_main_low_snr_factory()

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

    # 标 aperture_tier + 标低 SNR
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
        meta["snr_tier"] = "low"
        meta["speckle_sigma"] = 0.35
        meta["noise_floor_db"] = 55.0
        meta["aperture_note"] = (
            "S4 主档低 SNR：ARIS ±7.5° / 128 波束 / σ_ρ=1cm / ρ_max=40m. "
            "speckle=0.35, 噪声底 55dB (与 sensitivity 档 S4 同 SNR). "
            "验证主档硬件 + 低 SNR 联合工况下的可反演性."
        )
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2, ensure_ascii=False, default=str)
        print(f"已标 aperture_tier=main_aris_7p5deg + snr_tier=low")

    # 打印关键字段
    print(f"\n=== S4_main_low_snr 验收 ===")
    print(f"  feas: {meta.get('feasibility', {}).get('is_feasible')}")
    print(f"  h_max: {meta.get('feasibility', {}).get('h_max_m'):.2f}m")
    print(f"  elev_top: {meta.get('feasibility', {}).get('elev_top_deg'):.2f}°")
    h_pillar = meta.get('scene', {}).get('h_avg_m', 1)
    h_max = meta.get('feasibility', {}).get('h_max_m', 0)
    margin = (h_max - h_pillar) / h_max * 100 if h_max > 0 else 0
    print(f"  h_pillar: {h_pillar}m, margin: {margin:.1f}%")
    mae = meta.get('inversion', {}).get('mae_v2_median_m')
    mae_s = f"{mae*100:.2f}cm" if mae is not None else "N/A"
    print(f"  MAE_V2: {mae_s}")
    return meta


if __name__ == "__main__":
    main()
