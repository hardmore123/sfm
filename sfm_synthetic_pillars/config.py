"""
声学 SfM 模拟数据集配置 —— 柱子场景
========================================

本文件集中所有可调参数（声学/传感器/场景/轨迹）。
设计原则：
  1) 物理参数取自公开论文（Huang&Kaess 2015、Qadri et al. 2022 等）
     与真实声呐手册（Oculus M 系列、DIDSON）；
  2) 改一个数即可在不改主流程的前提下生成不同难度的数据；
  3) 所有 ground truth 在 sim 时落盘，方便 BA 端到端评估误差。

使用：
    from config import C  # 直接 import 这个全局对象即可
"""

from dataclasses import dataclass, field
from typing import List, Tuple
import numpy as np


@dataclass
class SonarCfg:
    """成像声呐 (Forward-Looking Sonar, FLS) 参数。"""
    # 几何分辨率
    beam_count: int = 512                # 方位波束数（Oculus M 系列常用 512）
    range_bin_count: int = 800           # 距离 bin 数
    fov_azimuth_deg: Tuple[float, float] = (-65.0, 65.0)  # 方位视场
    fov_elevation_deg: Tuple[float, float] = (-17.0, 17.0)  # 仰角孔径
    range_min_m: float = 0.20
    range_max_m: float = 6.00
    sound_speed_mps: float = 1500.0      # 用于把距离分辨率换算到 m

    # 物理参数
    center_frequency_hz: float = 1.2e6   # Oculus M 默认 1.2MHz
    bandwidth_hz: float = 0.3e6          # 带宽 → 距离分辨率 δ_r ≈ c/(2B)
    tx_power_db: float = 210.0           # 发射功率（仅作强度缩放）
    noise_floor_db: float = 45.0         # 噪声底（决定最小可检测强度）
    speckle_sigma: float = 0.20          # 斑点噪声相对标准差
    ambient_drop_db_per_m: float = 0.5   # 沿传播方向的吸收衰减

    # 像素映射（与 BA 侧像素自标定接口完全一致）
    pixel_map: dict = field(default_factory=lambda: {
        "beam":  {"a": 0.0, "b": 0.0},   # 由 beam_count 自动算
        "range": {"c": 0.0, "d": 0.0},   # 由 range_bin_count 自动算
    })


@dataclass
class SensorNoiseCfg:
    """传感器噪声参数（论文级）。"""
    # 声呐测向/测距噪声（Huang 2015 Table I: σ_θ=0.2°, σ_ρ=0.005m）
    sigma_theta_rad: float = np.deg2rad(0.2)
    sigma_rho_m: float = 0.005
    # 误检/漏检率
    p_false_alarm: float = 0.01
    p_miss: float = 0.02

    # 里程计 (DVL + IMU) 噪声
    sigma_trans_m: float = 0.01          # DVL 平移 std
    sigma_rot_rad: float = np.deg2rad(1.0)  # IMU 角度 std
    # 偏置 (DVL 比例因子 / IMU 偏置)
    dvl_scale_bias: float = 0.005        # 0.5% 比例因子误差
    imu_gyro_bias_radps: float = 0.001   # 角速度偏置

    # IMU 采样率
    imu_rate_hz: float = 200.0
    dvl_rate_hz: float = 10.0


@dataclass
class SceneCfg:
    """3D 场景（柱子群）参数。"""
    # 场景类型：'pillar'（默认）/ 'cube' / 'sphere' / 'mixed' / 'plane_only'
    scene_type: str = "pillar"
    # 柱子布置：每根柱子 (x, y, radius, height)
    pillars: List[Tuple[float, float, float, float]] = field(default_factory=lambda: [
        (-2.5,  1.5, 0.20, 2.5),
        (-1.5, -1.2, 0.18, 2.0),
        (-0.5,  1.8, 0.22, 2.8),
        ( 0.5, -1.0, 0.15, 2.2),
        ( 1.5,  1.5, 0.25, 3.0),
        ( 2.5, -0.5, 0.18, 2.4),
        ( 3.0,  1.2, 0.20, 2.6),
        ( 0.0,  0.0, 0.30, 3.5),     # 中心粗柱子
    ])
    # 立方体列表：(x, y, z, half_size)  z 是底面 z，立方体从 z 到 z+2*half_size
    cubes: List[Tuple[float, float, float, float]] = field(default_factory=list)
    # 球列表：(x, y, z_bottom, radius)
    spheres: List[Tuple[float, float, float, float]] = field(default_factory=list)
    # L 形块（用 2 个立方体近似）
    L_shapes: List[dict] = field(default_factory=list)
    # 散石（无固定形状）：(x, y, z, radius)
    rubble: List[Tuple[float, float, float, float]] = field(default_factory=list)
    # 附加干扰：水池地板（位于 z=0 平面以下）—— 阴影会投在地板上
    floor_z_m: float = 0.0
    # 海面（位于 z=h 处）
    surface_z_m: float = 5.0
    # 海底 Lambert 散射系数（线性）
    # 经验：seafloor_backscatter=100 + shadow_attenuation=0.0005 → T0.5 验收接近通过
    seafloor_backscatter: float = 100.0    # 线性 Lambert 系数
    # 阴影区衰减（声学阴影中信号衰减系数，0=完全黑，1=无衰减）
    shadow_attenuation: float = 0.0005     # 0.05% 残留（强声学阴影）
    # 多径干扰强度（0=无，1=强）
    multipath_strength: float = 0.0


@dataclass
class TrajCfg:
    """AUV 轨迹参数。"""
    # 总帧数与关键帧选取（大论文要求：扩大数据量）
    n_frames: int = 120
    keyframe_indices: List[int] = field(default_factory=lambda: list(range(0, 120, 5)))  # 24 关键帧
    dt_s: float = 0.20                    # 帧间隔

    # 运动模式：
    #   "general"   - 一般 6-DOF，含 pitch 和 z 起伏（良约束）
    #   "forward"   - 纯 x 平移（欠约束，对应 V4 报告的退化情形）
    #   "yaw_y"     - 偏航 + y 平移（欠约束）
    #   "mixed"     - 混合：含一段 forward 一段 pitch+z，给 BA 同时测两种情形
    motion_mode: str = "mixed"

    # 起点
    start_xyz: Tuple[float, float, float] = (-6.0, 0.0, 1.5)
    start_rpy: Tuple[float, float, float] = (0.0, 0.0, 0.0)  # roll pitch yaw (rad)

    # 总位移
    forward_total_m: float = 8.0          # 沿 x 方向总前进
    sway_total_m: float = 0.5             # 沿 y 摆动幅度
    heave_amplitude_m: float = 0.4         # 升沉幅度（z 起伏）
    pitch_amplitude_rad: float = 0.10     # 俯仰幅度（≈6°）
    yaw_amplitude_rad: float = 0.20       # 偏航幅度


@dataclass
class Config:
    seed: int = 42
    sonar: SonarCfg = field(default_factory=SonarCfg)
    noise: SensorNoiseCfg = field(default_factory=SensorNoiseCfg)
    scene: SceneCfg = field(default_factory=SceneCfg)
    traj: TrajCfg = field(default_factory=TrajCfg)
    output_dir: str = "."


C = Config()


def finalize_pixel_mapping(cfg: Config) -> None:
    """由波束/距离 bin 数自动算像素线性映射（与 BA calibrate_pixels 兼容）。"""
    n_beam = cfg.sonar.beam_count
    n_rng = cfg.sonar.range_bin_count
    az_lo, az_hi = cfg.sonar.fov_azimuth_deg
    r_lo, r_hi = cfg.sonar.range_min_m, cfg.sonar.range_max_m
    # beam = a * theta_deg + b，theta_deg ∈ [az_lo, az_hi] → beam ∈ [0, n_beam-1]
    # 约定 BA 端 theta 是 rad，因此 a 单位是 beam/rad
    az_lo_rad, az_hi_rad = np.deg2rad(az_lo), np.deg2rad(az_hi)
    a_b = (n_beam - 1) / (az_hi_rad - az_lo_rad)
    b_b = -a_b * az_lo_rad
    c_r = (n_rng - 1) / (r_hi - r_lo)
    d_r = -c_r * r_lo
    cfg.sonar.pixel_map["beam"] = {"a": a_b, "b": b_b}
    cfg.sonar.pixel_map["range"] = {"c": c_r, "d": d_r}
