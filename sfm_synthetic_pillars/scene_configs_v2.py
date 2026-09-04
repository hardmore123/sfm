"""
S1-S6 仿真构型 v2 (T1.1 阶段表 §4 P1)
========================================
按阶段表 §7.1 验算的新构型生成 6 个代表场景：

  S1: 单目标 · 良约束 (general, heave 1.2)
  S2: 单目标 · forward 退化 (forward, heave 0, pitch 固定)
  S3: 多目标混合形状 (柱+方+球)
  S4: 低 SNR (speckle_sigma 0.35, 噪声底抬高)
  S5: 包线边缘 (h=0.9h_max)
  S6: 包线外负例 (h>z_s) — 应判不可反演

构型（按 §7.1）：
  - z_s = 4.5 m（声呐距海底高度）
  - ρ_max = 25 m（声呐量程）
  - θ_p = 18°（固定下俯 + 小幅 ±3° 摆动）
  - heave = 1.0-1.2 m
  - 目标尺度：目标在 x∈[-3,3]，地面距离 7-10 m
"""
import os
import sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import Config, SonarCfg, SceneCfg, TrajCfg, SensorNoiseCfg
from feasibility import check_feasibility


# ==========================================
# 公共构型常量（按阶段表 §7.1）
# ==========================================
BASE_Z_S = 4.5         # 声呐距海底高度 (m)
BASE_RHO_MAX = 25.0    # 声呐量程 (m)
BASE_PITCH_DEG = 18.0  # 固定下俯 18°（落在 ±17° 孔径内 + 1° 余量，约 14°-22° 有效）
BASE_HEAVE = 1.2       # 升沉幅度 (m)
BASE_FORWARD = 4.0     # AUV 移动距离 (m)，保持 d≈10-12 不出包线


def _base_cfg(seed: int = 200) -> Config:
    """基础构型：z_s=4.5, ρ=25, θ_p=18°，中等声呐配置。

    声呐：256 beam × 600 range bin → 153K 像素/帧
    帧数：20 帧，5 关键帧（每 4 帧取 1 关键帧）
    """
    cfg = Config()
    cfg.seed = seed
    cfg.sonar = SonarCfg(
        beam_count=256,
        range_bin_count=600,
        fov_azimuth_deg=(-65.0, 65.0),
        fov_elevation_deg=(-17.0, 17.0),
        range_min_m=0.50,
        range_max_m=BASE_RHO_MAX,
        speckle_sigma=0.20,
        noise_floor_db=45.0,
    )
    cfg.noise = SensorNoiseCfg(
        sigma_theta_rad=np.deg2rad(0.25),
        sigma_rho_m=0.010,
        p_false_alarm=0.02,
        p_miss=0.05,
        sigma_trans_m=0.015,
        sigma_rot_rad=np.deg2rad(1.5),
    )
    cfg.traj = TrajCfg(
        n_frames=20,
        keyframe_indices=list(range(0, 20, 4)),   # 5 关键帧
        dt_s=0.50,
        start_xyz=(-12.0, 0.0, BASE_Z_S),
        start_rpy=(0.0, np.deg2rad(BASE_PITCH_DEG), 0.0),
        forward_total_m=4.0,        # AUV 移动 4m（保持 d≈10-12）
        sway_total_m=0.0,
        heave_amplitude_m=BASE_HEAVE,
        pitch_amplitude_rad=0.05,    # ±3° 摆动
        yaw_amplitude_rad=0.10,     # ±5.7° 摆动
    )
    return cfg


# ==========================================
# S1-S6 场景工厂
# ==========================================
def make_S1_single_well_constrained():
    """S1: 单目标 · 良约束
    关键：general 模式 + heave 1.2（验证 BA 解出 z + 阴影反演辅助）
    h=2.5 < h_max(10m)=2.67, 包线内 31% 余量
    """
    cfg = _base_cfg(seed=201)
    cfg.scene = SceneCfg(
        scene_type="pillar",
        pillars=[(0.0, 0.0, 0.40, 2.5)],
    )
    cfg.traj.motion_mode = "general"
    return cfg


def make_S2_single_forward_degenerate():
    """S2: 单目标 · forward 退化
    关键：forward + heave=0 + pitch 固定（保持 z 不可观测对照）
    h=2.5, 包线内 31% 余量，但 BA 解不出 z
    """
    cfg = _base_cfg(seed=202)
    cfg.scene = SceneCfg(
        scene_type="pillar",
        pillars=[(0.0, 0.0, 0.40, 2.5)],
    )
    cfg.traj.motion_mode = "forward"
    cfg.traj.heave_amplitude_m = 0.0
    cfg.traj.pitch_amplitude_rad = 0.0
    cfg.traj.sway_total_m = 0.0
    return cfg


def make_S3_mixed_shapes():
    """S3: 多目标混合形状
    关键：柱 + 方 + 球 混合，检验 h_eff 不再用全局常数
    4 个目标（放在 d≈15 处，确保 elev_top 在孔径内）：
      2 柱 (h=1.5/1.5) + 1 立方 (h=1.0) + 1 球 (h=0.8)
    """
    cfg = _base_cfg(seed=203)
    cfg.scene = SceneCfg(
        scene_type="mixed",
        pillars=[(3.0, 1.0, 0.40, 1.5), (7.0, -1.0, 0.40, 1.5)],
        cubes=[(5.0, 0.5, 0.0, 0.5)],          # 立方半边 0.5 → 高 1.0
        spheres=[(5.0, -0.5, 0.4, 0.4)],        # 球半径 0.4 → 高 0.8
    )
    cfg.traj.motion_mode = "general"
    return cfg


def make_S4_low_snr():
    """S4: 低 SNR
    关键：speckle 0.35 + 噪声底 55dB（验证 CFAR 门限 + 阴影分割）
    h=2.5, 包线内 31% 余量
    """
    cfg = _base_cfg(seed=204)
    cfg.scene = SceneCfg(
        scene_type="pillar",
        pillars=[(0.0, 0.0, 0.40, 2.5)],
    )
    cfg.sonar.speckle_sigma = 0.35
    cfg.sonar.noise_floor_db = 55.0
    cfg.noise.p_false_alarm = 0.05
    cfg.noise.p_miss = 0.10
    cfg.traj.motion_mode = "general"
    return cfg


def make_S5_envelope_edge():
    """S5: 包线边缘
    关键：h = 0.9 h_max（z_s=4.5, d=10, ρ=25 ⇒ h_max=2.67 ⇒ 0.9=2.40）
    应判可反演但余量小，验证判据的连续性
    """
    cfg = _base_cfg(seed=205)
    cfg.scene = SceneCfg(
        scene_type="pillar",
        pillars=[(0.0, 0.0, 0.40, 2.40)],
    )
    cfg.traj.motion_mode = "general"
    return cfg


def make_S6_envelope_outlier():
    """S6: 包线外负例
    关键：h = 5.5 > z_s = 4.5 ⇒ 仰角向上无阴影
    应判不可反演（验证判据不是事后解释）
    """
    cfg = _base_cfg(seed=206)
    cfg.scene = SceneCfg(
        scene_type="pillar",
        pillars=[(0.0, 0.0, 0.40, 5.5)],
    )
    cfg.traj.motion_mode = "general"
    return cfg


# ==========================================
# 场景元信息
# ==========================================
SCENES_V2 = [
    # (name, title, design_intent, factory, expected_feasible)
    ("S1_single_well_constrained",  "S1 单目标·良约束",   "general + heave 1.2，包线内 31% 余量",         make_S1_single_well_constrained,   True),
    ("S2_single_forward_degenerate","S2 单目标·forward 退化", "forward + heave=0 + pitch 固定（退化对照）",  make_S2_single_forward_degenerate, True),
    ("S3_mixed_shapes",             "S3 多目标混合",      "柱+方+球，检验 h_eff 不再用全局常数",         make_S3_mixed_shapes,              True),
    ("S4_low_snr",                  "S4 低 SNR",          "speckle 0.35 + 噪声底 55dB，CFAR 门限验证",    make_S4_low_snr,                   True),
    ("S5_envelope_edge",            "S5 包线边缘",        "h=0.9h_max=2.40m，余量小应可反演",            make_S5_envelope_edge,             True),
    ("S6_envelope_outlier",         "S6 包线外负例",      "h=5.5>z_s=4.5，应判不可反演",                 make_S6_envelope_outlier,          False),
]


def _scene_target_heights(cfg: Config):
    """提取场景中所有目标的 h 值（柱: 顶高，方: 2*half，球: 2*r）。"""
    heights = []
    for p in cfg.scene.pillars:
        heights.append(p[3])
    for c in cfg.scene.cubes:
        heights.append(2 * c[3])
    for s in cfg.scene.spheres:
        heights.append(2 * s[3])
    return heights


def verify_scene_feasibility(cfg: Config, h: float, d: float = 10.0):
    """对场景做可反演性判定。"""
    z_s = cfg.traj.start_xyz[2]
    rho_max = cfg.sonar.range_max_m
    fov_elev = np.deg2rad(cfg.sonar.fov_elevation_deg[1])
    return check_feasibility(z_s, rho_max, 0, -fov_elev, fov_elev, d, h)


def report_feasibility():
    """打印 6 场景可反演性判定表（阶段表 T1.1 验收之一）。"""
    print("\n=== S1-S6 场景可反演性自检 (T1.1 验收: 5/6 可反演) ===\n")
    print(f"{'scene':<32} {'h(m)':<6} {'z_s':<6} {'rho':<6} {'elev_top':<10} {'h_max':<7} {'feas':<6} {'clipped':<8} {'expect':<7}")
    print("-" * 110)
    n_feas = 0
    n_correct = 0
    for name, title, desc, factory, expected in SCENES_V2:
        cfg = factory()
        heights = _scene_target_heights(cfg)
        # S3 多目标：取平均
        h_avg = np.mean(heights) if heights else 0
        # d_avg：用 AUV 路径中位（而非起点）到目标的水平距离
        if cfg.scene.pillars or cfg.scene.cubes or cfg.scene.spheres:
            target_xys = []
            for p in cfg.scene.pillars:
                target_xys.append((p[0], p[1]))
            for c in cfg.scene.cubes:
                target_xys.append((c[0], c[1]))
            for s in cfg.scene.spheres:
                target_xys.append((s[0], s[1]))
            # AUV 中位 x = start_x + 0.5*forward（沿 x 直线，sway=0）
            x_mid = cfg.traj.start_xyz[0] + 0.5 * cfg.traj.forward_total_m
            y_mid = cfg.traj.start_xyz[1]
            d_avg = np.mean([np.hypot(x - x_mid, y - y_mid) for x, y in target_xys])
        else:
            d_avg = 10.0

        r = verify_scene_feasibility(cfg, h_avg, d_avg)
        feas_str = "True" if r.is_feasible else "False"
        clip_str = "True" if r.L_s_clipped else "False"
        expect_str = "feas" if expected else "infeas"
        correct = (r.is_feasible == expected)
        if correct:
            n_correct += 1
        if r.is_feasible:
            n_feas += 1
        print(f"{name:<32} {h_avg:<6.2f} {cfg.traj.start_xyz[2]:<6.1f} {cfg.sonar.range_max_m:<6.1f} "
              f"{np.degrees(r.elev_top):<10.2f}° {r.h_max:<7.2f} {feas_str:<6} {clip_str:<8} {expect_str:<7} "
              f"{'OK' if correct else 'MISMATCH'}")
    print(f"\nfeasible: {n_feas}/6  (期望 5/6: S6 不可反演)")
    print(f"判定正确: {n_correct}/6  (期望 6/6)")
    return n_feas, n_correct


if __name__ == "__main__":
    n_feas, n_correct = report_feasibility()
    if n_correct == 6:
        print("\n[PASS] 6/6 场景可反演性判定与设计意图一致")
    else:
        print(f"\n[FAIL] 判定错误 {6 - n_correct}/6，需调整场景参数")
