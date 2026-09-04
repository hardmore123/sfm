"""
多场景模拟数据生成器
========================

按大论文各部分需求，一次性生成多个不同场景的模拟数据。

场景设计原则：
  - 覆盖大论文两大创新点的所有验证需求
  - 包含简单→复杂的多层次场景
  - 不同传感器配置（高低分辨率、宽窄仰角）
  - 不同环境（干净/有杂波/多径）
  - 不同轨迹（直线/圆周/之字）
  - 不同目标几何（柱/方/球/混合）

每个场景独立目录 + meta.json + 详细 README
"""

import os, sys, time, json, shutil
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "BA代码")))

from config import Config, C, finalize_pixel_mapping, SonarCfg, SceneCfg, TrajCfg
from big_paper_sim import generate_big_paper
from world import SceneWorld
from trajectory import make_poses


# ==========================================
# 场景定义
# ==========================================
def make_simple_single_pillar():
    """场景 1：1 根柱子（最简）"""
    cfg = Config()
    cfg.seed = 101
    cfg.scene = SceneCfg(
        scene_type="pillar",
        pillars=[(0.0, 0.0, 0.30, 2.8)],
    )
    cfg.traj.motion_mode = "general"
    cfg.traj.keyframe_indices = list(range(0, 60, 10))   # 6 关键帧
    return cfg


def make_simple_two_pillars():
    """场景 2：2 根柱子（最小双目标）"""
    cfg = Config()
    cfg.seed = 102
    cfg.scene = SceneCfg(
        scene_type="pillar",
        pillars=[(-1.0, 0.5, 0.25, 1.5), (1.0, -0.5, 0.25, 1.5)],   # 矮一些便于阴影可见
    )
    cfg.traj.motion_mode = "general"
    cfg.traj.keyframe_indices = list(range(0, 60, 6))
    return cfg


def make_simple_cube():
    """场景 3：1 个立方体（验证非柱面）"""
    cfg = Config()
    cfg.seed = 103
    cfg.scene = SceneCfg(
        scene_type="cube",
        pillars=[],
        cubes=[(0.0, 0.0, 0.0, 1.0)],   # cx, cy, z_bottom, half_size
    )
    cfg.traj.motion_mode = "general"
    cfg.traj.keyframe_indices = list(range(0, 60, 5))
    return cfg


def make_sphere_target():
    """场景 4：球（测试无阴影情形）"""
    cfg = Config()
    cfg.seed = 104
    cfg.scene = SceneCfg(
        scene_type="sphere",
        pillars=[],
        spheres=[(0.0, 0.0, 1.5, 0.6)],   # cx, cy, cz, radius
    )
    cfg.traj.motion_mode = "general"
    cfg.traj.keyframe_indices = list(range(0, 60, 5))
    return cfg


def make_diverse_shapes():
    """场景 5：多种几何混合（柱子+立方体+球）"""
    cfg = Config()
    cfg.seed = 105
    cfg.scene = SceneCfg(
        scene_type="mixed",
        pillars=[(-2.0, 1.0, 0.20, 2.5), (2.0, -1.0, 0.20, 2.5)],
        cubes=[(0.0, 1.5, 0.0, 0.4), (0.0, -1.5, 0.0, 0.4)],
        spheres=[(0.0, 0.0, 1.2, 0.5)],
    )
    cfg.traj.motion_mode = "general"
    cfg.traj.keyframe_indices = list(range(0, 60, 5))
    return cfg


def make_dense_pillars_16():
    """场景 6：16 根柱子密集排布（拥挤场景）"""
    cfg = Config()
    cfg.seed = 106
    pillars = []
    for x in range(-3, 4):
        for y in [-1.5, 0, 1.5]:
            r = 0.18 + 0.05 * ((x + 3) % 3)
            h = 2.0 + 0.3 * (x + 3)
            pillars.append((x * 0.8, y, r, h))
    cfg.scene = SceneCfg(scene_type="pillar", pillars=pillars)
    cfg.traj.motion_mode = "general"
    cfg.traj.keyframe_indices = list(range(0, 120, 5))   # 24 关键帧
    return cfg


def make_high_resolution():
    """场景 7：高分辨率声呐（1024 beam × 1200 range）"""
    cfg = Config()
    cfg.seed = 107
    cfg.scene = SceneCfg(
        scene_type="pillar",
        pillars=[(p[0] * 1.5, p[1] * 1.5, p[2], p[3]) for p in C.scene.pillars],
    )
    cfg.sonar = SonarCfg(
        beam_count=1024, range_bin_count=1200,
        fov_azimuth_deg=(-65.0, 65.0), fov_elevation_deg=(-17.0, 17.0),
        range_min_m=0.10, range_max_m=5.00,
    )
    cfg.traj.motion_mode = "general"
    cfg.traj.keyframe_indices = list(range(0, 60, 5))
    return cfg


def make_low_resolution():
    """场景 8：低分辨率声呐（128 beam × 200 range）— 老声呐/低端"""
    cfg = Config()
    cfg.seed = 108
    cfg.scene = SceneCfg(
        scene_type="pillar",
        pillars=[(-1.0, 0.5, 0.25, 2.5), (1.0, -0.5, 0.25, 2.5)],
    )
    cfg.sonar = SonarCfg(
        beam_count=128, range_bin_count=200,
        fov_azimuth_deg=(-50.0, 50.0), fov_elevation_deg=(-15.0, 15.0),
        range_min_m=0.30, range_max_m=4.00,
    )
    cfg.traj.motion_mode = "general"
    cfg.traj.keyframe_indices = list(range(0, 60, 8))
    return cfg


def make_narrow_elevation():
    """场景 9：窄仰角孔径（±5°，约束紧）"""
    cfg = Config()
    cfg.seed = 109
    cfg.scene = SceneCfg(
        scene_type="pillar",
        pillars=[(-1.0, 0.5, 0.25, 2.5), (1.0, -0.5, 0.25, 2.5)],
    )
    cfg.sonar = SonarCfg(
        beam_count=512, range_bin_count=800,
        fov_azimuth_deg=(-65.0, 65.0), fov_elevation_deg=(-5.0, 5.0),  # 窄！
        range_min_m=0.20, range_max_m=4.00,
    )
    cfg.traj.motion_mode = "general"
    cfg.traj.keyframe_indices = list(range(0, 60, 5))
    return cfg


def make_wide_elevation():
    """场景 10：宽仰角孔径（±25°，约束松）"""
    cfg = Config()
    cfg.seed = 110
    cfg.scene = SceneCfg(
        scene_type="pillar",
        pillars=[(-1.0, 0.5, 0.25, 2.5), (1.0, -0.5, 0.25, 2.5)],
    )
    cfg.sonar = SonarCfg(
        beam_count=512, range_bin_count=800,
        fov_azimuth_deg=(-65.0, 65.0), fov_elevation_deg=(-25.0, 25.0),  # 宽！
        range_min_m=0.20, range_max_m=4.00,
    )
    cfg.traj.motion_mode = "general"
    cfg.traj.keyframe_indices = list(range(0, 60, 5))
    return cfg


def make_seafloor_with_rubble():
    """场景 11：海底+散石（背景杂波）"""
    cfg = Config()
    cfg.seed = 111
    # 主目标 2 根柱子
    pillars = [(-1.0, 0.5, 0.25, 2.5), (1.0, -0.5, 0.25, 2.5)]
    # 散石（小石块，水池地板附近）
    import random
    rng = random.Random(111)
    rubble = []
    for _ in range(20):
        x = rng.uniform(-2.5, 2.5)
        y = rng.uniform(-1.5, 1.5)
        r = rng.uniform(0.05, 0.12)
        rubble.append((x, y, 0.0, r))
    cfg.scene = SceneCfg(
        scene_type="pillar",
        pillars=pillars, rubble=rubble,
        seafloor_backscatter=0.10,   # 强背景
    )
    cfg.traj.motion_mode = "general"
    cfg.traj.keyframe_indices = list(range(0, 60, 5))
    return cfg


def make_multipath_heavy():
    """场景 12：多径/旁瓣干扰"""
    cfg = Config()
    cfg.seed = 112
    cfg.scene = SceneCfg(
        scene_type="pillar",
        pillars=[(-1.0, 0.5, 0.25, 2.5), (1.0, -0.5, 0.25, 2.5)],
    )
    cfg.sonar.speckle_sigma = 0.4    # 强散斑
    cfg.sonar.noise_floor_db = 50.0  # 高噪声底
    cfg.traj.motion_mode = "general"
    cfg.traj.keyframe_indices = list(range(0, 60, 5))
    return cfg


def make_circular_trajectory():
    """场景 13：圆周轨迹（环绕目标）"""
    cfg = Config()
    cfg.seed = 113
    cfg.scene = SceneCfg(
        scene_type="pillar",
        pillars=[(0.0, 0.0, 0.30, 1.5)],
    )
    cfg.traj.motion_mode = "general"
    n = 120
    poses6 = np.zeros((n, 6))
    for i in range(n):
        t = i / n * 2 * np.pi
        R = 2.5
        x, y = R * np.cos(t), R * np.sin(t)
        poses6[i, 0] = x
        poses6[i, 1] = y
        poses6[i, 2] = 1.5
        poses6[i, 3] = 0.0
        poses6[i, 4] = 0.05 * np.sin(t)
        # yaw 始终指向中心 (0,0)：yaw = atan2(0 - y, 0 - x) = atan2(-y, -x) = t + π
        poses6[i, 5] = t + np.pi
    cfg._custom_poses = poses6
    cfg.traj.keyframe_indices = list(range(0, 120, 8))
    return cfg


def make_zigzag_trajectory():
    """场景 14：之字形轨迹（典型水下巡检）"""
    cfg = Config()
    cfg.seed = 114
    cfg.scene = SceneCfg(
        scene_type="pillar",
        pillars=[(p[0] * 0.8, p[1] * 0.8, p[2], p[3]) for p in C.scene.pillars],
    )
    # 自定义之字形
    n = 120
    poses6 = np.zeros((n, 6))
    for i in range(n):
        t = i / n
        poses6[i, 0] = -3 + 6 * t     # 直线前推
        poses6[i, 1] = 1.5 * np.sin(4 * np.pi * t)  # 之字形
        poses6[i, 2] = 1.5 + 0.3 * np.sin(2 * np.pi * t)
        poses6[i, 3] = 0.0
        poses6[i, 4] = 0.05 * np.cos(2 * np.pi * t)
        poses6[i, 5] = -0.1 * np.cos(4 * np.pi * t)   # 朝向随之摆动
    cfg._custom_poses = poses6
    cfg.traj.motion_mode = "general"
    cfg.traj.keyframe_indices = list(range(0, 120, 5))
    return cfg


def make_speckle_heavy():
    """场景 15：相干斑重（数据增强 - 模拟真实声呐噪声）"""
    cfg = Config()
    cfg.seed = 115
    cfg.scene = SceneCfg(
        scene_type="pillar",
        pillars=[(p[0] * 0.8, p[1] * 0.8, p[2], p[3]) for p in C.scene.pillars],
    )
    cfg.sonar.speckle_sigma = 0.5
    cfg.sonar.noise_floor_db = 55.0
    cfg.traj.motion_mode = "general"
    cfg.traj.keyframe_indices = list(range(0, 60, 5))
    return cfg


def make_low_snr_extreme():
    """场景 16：极低 SNR（高外点率）— 测试鲁棒性"""
    cfg = Config()
    cfg.seed = 116
    # 柱子矮一些，让阴影在 range 范围内
    cfg.scene = SceneCfg(
        scene_type="pillar",
        pillars=[(p[0] * 0.8, p[1] * 0.8, p[2], 1.5) for p in C.scene.pillars],
    )
    cfg.sonar.speckle_sigma = 0.6
    cfg.sonar.noise_floor_db = 60.0
    from config import SensorNoiseCfg
    cfg.noise = SensorNoiseCfg(
        sigma_theta_rad=np.deg2rad(0.5),
        sigma_rho_m=0.02,
        p_miss=0.10,
        p_false_alarm=0.10,
    )
    cfg.traj.motion_mode = "general"
    cfg.traj.keyframe_indices = list(range(0, 60, 5))
    return cfg


# ==========================================
# 场景元信息（用于 README）
# ==========================================
SCENES = [
    ("01_simple_single_pillar", "单根柱子（最简）", "最简几何，sanity check", make_simple_single_pillar, "simple"),
    ("02_simple_two_pillars",  "两根柱子（最小双目标）", "验证最小可观测情形", make_simple_two_pillars, "simple"),
    ("03_simple_cube",         "立方体（验证非柱面）", "验证几何模型泛化（柱→方）", make_simple_cube, "simple"),
    ("04_sphere_target",       "球（测试无阴影）", "球几乎不产生阴影，测反演失败情形", make_sphere_target, "simple"),
    ("05_diverse_shapes",      "多种几何混合", "柱+方+球 同时存在，复杂场景", make_diverse_shapes, "complex"),
    ("06_dense_pillars_16",    "16 根柱子密集排布", "拥挤场景，验证关联压力", make_dense_pillars_16, "complex"),
    ("07_high_resolution",     "高分辨率声呐 (1024×1200)", "高端声呐配置，验证细节捕捉", make_high_resolution, "sensor"),
    ("08_low_resolution",      "低分辨率声呐 (128×200)", "老声呐/低端配置，验证鲁棒性", make_low_resolution, "sensor"),
    ("09_narrow_elevation",    "窄仰角孔径 (±5°)", "约束紧的成像几何", make_narrow_elevation, "sensor"),
    ("10_wide_elevation",      "宽仰角孔径 (±25°)", "约束松的成像几何", make_wide_elevation, "sensor"),
    ("11_seafloor_with_rubble","海底+散石（背景杂波）", "真实水下环境，杂波强", make_seafloor_with_rubble, "env"),
    ("12_multipath_heavy",     "多径/旁瓣干扰", "强噪声测试，验证鲁棒核", make_multipath_heavy, "env"),
    ("13_circular_trajectory", "圆周轨迹（环绕目标）", "360° 视角覆盖", make_circular_trajectory, "traj"),
    ("14_zigzag_trajectory",   "之字形轨迹", "典型水下巡检模式", make_zigzag_trajectory, "traj"),
    ("15_speckle_heavy",       "重相干斑（增强）", "sim-to-real 数据增强", make_speckle_heavy, "aug"),
    ("16_low_snr_extreme",     "极低 SNR（极端外点）", "极限噪声测试，验证 GNC", make_low_snr_extreme, "aug"),
]


def main(only=None, out_root="./big_paper_scene_set"):
    os.makedirs(out_root, exist_ok=True)
    selected = SCENES if only is None else [s for s in SCENES if s[0] in only]
    print(f"\n将生成 {len(selected)} 个场景到 {out_root}/\n")
    summary = []
    for name, title, desc, factory, category in selected:
        out_dir = os.path.join(out_root, name)
        os.makedirs(out_dir, exist_ok=True)
        print(f"\n{'='*70}\n{name} | {title}\n{'='*70}")
        try:
            cfg = factory()
            t0 = time.time()
            meta = generate_big_paper(out_dir=out_dir, motion_mode=cfg.traj.motion_mode, cfg=cfg)
            t = time.time() - t0
            # 注入 custom poses
            if hasattr(cfg, "_custom_poses"):
                np.save(os.path.join(out_dir, "gt", "custom_poses.npy"), cfg._custom_poses)
            # 写场景说明 README
            with open(os.path.join(out_dir, "README.md"), "w", encoding="utf-8") as f:
                f.write(f"# {title}\n\n")
                f.write(f"**目录**：`{name}/`  **类别**：`{category}`\n\n")
                f.write(f"## 用途\n\n{desc}\n\n")
                f.write("## 数据规模\n\n")
                st = meta.get("stats", {})
                f.write(f"- 帧数: {st.get('n_frames', '?')}\n")
                f.write(f"- 关键帧: {st.get('n_keyframes', '?')}\n")
                f.write(f"- 目标数: {st.get('n_pillars', '?')}\n")
                f.write(f"- Landmark: {st.get('n_landmarks', '?')}\n")
                f.write(f"- 观测总数: {st.get('n_observations', '?')}\n")
                f.write(f"- 关键帧观测: {st.get('n_obs_keyframes', '?')}\n")
                f.write(f"- 目标像素: {st.get('n_target_pixels_total', '?')}\n")
                f.write(f"- 阴影像素: {st.get('n_shadow_pixels_total', '?')}\n\n")
                f.write("## 声学配置\n\n")
                f.write(f"- beam_count: {cfg.sonar.beam_count}\n")
                f.write(f"- range_bin_count: {cfg.sonar.range_bin_count}\n")
                f.write(f"- 方位视场: {cfg.sonar.fov_azimuth_deg}\n")
                f.write(f"- 仰角孔径: {cfg.sonar.fov_elevation_deg}\n")
                f.write(f"- 距离: [{cfg.sonar.range_min_m}, {cfg.sonar.range_max_m}] m\n")
                f.write(f"- 散斑 σ: {cfg.sonar.speckle_sigma}\n")
                f.write(f"- 噪声底: {cfg.sonar.noise_floor_db} dB\n\n")
                f.write("## 文件清单\n\n")
                f.write("- `input/` — 创新一输入（4 件套）\n")
                f.write("- `gt/` — ground truth（位姿/landmark/声呐图）\n")
                f.write("- `innovation1/` — 创新一后处理（可观测性+曲面）\n")
                f.write("- `innovation2/` — 创新二输出（掩码+阴影+高度反演）\n")
                f.write("- `segmentation_data/` — 语义分割训练数据\n")
                f.write("- `imu/imu_data.csv` — IMU 仿真\n")
                f.write("- `dvl/dvl_data.csv` — DVL 仿真\n")
                f.write("- `meta.json` — 完整摘要\n\n")
                f.write("## 适用实验\n\n")
                f.write(_suggest_experiments(name, title, desc, category))
            summary.append({"name": name, "title": title, "category": category,
                            "time_s": t, "stats": st,
                            "innov1": meta.get("innovation1_stats", {}),
                            "innov2": meta.get("innovation2_stats", {})})
        except Exception as e:
            import traceback; traceback.print_exc()
            summary.append({"name": name, "title": title, "error": str(e)})
    # 写 summary
    with open(os.path.join(out_root, "summary.json"), "w") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False, default=str)
    # 打印总览
    print(f"\n{'='*70}\n所有场景生成完成\n{'='*70}")
    print(f"{'场景':<35} | {'#lm':<5} | {'#obs':<6} | {'#KF':<4} | {'目标像素':<10} | {'耗时':<7}")
    print("-" * 80)
    for s in summary:
        if "error" in s:
            print(f"{s['name']:<35} | ERROR: {s['error'][:50]}")
            continue
        st = s.get("stats", {})
        n_tgt = st.get("n_target_pixels_total", 0)
        print(f"{s['name']:<35} | {st.get('n_landmarks', 0):<5} | "
              f"{st.get('n_observations', 0):<6} | {st.get('n_keyframes', 0):<4} | "
              f"{n_tgt:<10} | {s.get('time_s', 0):<7.1f}")
    print("=" * 80)


def _suggest_experiments(name, title, desc, category):
    """对每个场景给推荐的实验。"""
    txt = ""
    if category == "simple":
        txt += "- **创新一·M1 软关联置信度**：在最小场景下验证置信度权重机制\n"
        txt += "- **创新一·M2 球坐标+视场**：单/双目标基础 sanity check\n"
        txt += "- **球 vs 柱**：对比声学阴影在不同几何下的形态差异\n"
    elif category == "complex":
        txt += "- **创新一·M1 数据关联**：拥挤场景下硬关联 vs 软关联对比\n"
        txt += "- **创新二·M2 阴影高度反演**：混合几何的阴影反演精度\n"
    elif category == "sensor":
        txt += "- **不同分辨率/孔径对 BA 精度的影响**：分辨率 vs 精度曲线\n"
        txt += "- **创新一·M2 视场约束**：窄仰角（约束紧）vs 宽仰角（约束松）的影响\n"
    elif category == "env":
        txt += "- **创新一·M1 软关联鲁棒性**：杂波/多径下 RANSAC vs 软关联对比\n"
        txt += "- **创新二·M1 目标-背景分割**：评估在杂波下的目标检测能力\n"
        txt += "- **创新一·M4 加权曲面**：杂波下加权泊松抑制漂浮物\n"
    elif category == "traj":
        txt += "- **6.1 仰角来源消融**：圆周/之字 vs 直线，对比多视几何+阴影先验增益\n"
        txt += "- **可观测性分析**：圆周 vs 之字 vs 直线对 λ3 分布的影响\n"
    elif category == "aug":
        txt += "- **sim-to-real 增强**：重相干斑训练对真实数据泛化的影响\n"
        txt += "- **创新一·M1 软关联 vs GNC 在低 SNR 下**：极低 SNR 下 GNC 优势验证\n"
    return txt


if __name__ == "__main__":
    main()
