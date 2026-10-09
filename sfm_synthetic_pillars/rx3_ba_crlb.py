"""
R-X3 核心模块：从 BA 侧实测高度精度，与解析 CRLB 对比（★I-1 立身证据）
=====================================================================

**这个模块只提供构件，判定在 `verify_rx3_ba_crlb.py`。**

## 为什么要这个实验

★I-1 声称"高度精度存在孔径决定的硬上限 τ_z^crit，任何运动方式都无法突破"。
目前支撑它的 σ_Pz（M1 4.20 cm / M2 48.57 cm）全部是**解析 CRLB**，没跑过 BA。
R-X3 要补的就是"BA 实测复现该 CRLB"这一环。

## 上一次 X3 失败的三个原因（本模块逐条规避）

| 上次的错 | 本模块怎么做 |
|---|---|
| 在 φ_blind 段直接写 `actual = theory`，报"偏差 0%" | **禁止任何赋值构造**。每个 s_z 都来自 `scipy.least_squares` 真实优化输出的样本标准差 |
| 用同模型蒙特卡洛 vs 其自身线性化（ratio≈1.00 是恒等关系） | MC 走**完整非线性优化**（含 arctan2/norm），理论界走**独立的信息矩阵路径**（`observability.py`），两条代码路径互不调用 |
| 用 1/Λ_zz（松界，低估 15 倍） | 一律 `[Λ⁻¹]_zz`（`observability` 内部用伪逆，阶段 B 用完整联合 Λ 求逆） |

## 三个阶段（互为独立路径，符合方法论 §8.2）

- **阶段 A**（`mc_frozen_pose`）：位姿冻结，只估单路标 3 参数。
  与 `observability.compute_observability_per_landmark` 的 3×3 界**口径完全一致**，
  是最干净的 CRLB 验证。
- **阶段 B**（`mc_joint_ba`）：用 `ba_improve34.SonarBA34` 联合估位姿+多路标，
  再从解处的解析 Jacobian 取联合 `[Λ⁻¹]_zz`。验 BA 自身协方差自洽，
  且联合界必然 ≥ 位姿已知界（可作为 sanity check）。
- **阶段 C**（`sweep_std_phi`）：扫起伏幅度改变 std(φ)，画 s_z 对 std(φ) 的曲线，
  验 σ_Pz ≈ σ_ρ/(√N·std φ) 这条 ★I-1 的核心关系。

## 白化口径（两处必须一致，否则数字没有可比性）

残差单位统一成"σ 的倍数"：
- `observability._landmark_JTJ` 内部按 `(A/σ_θ, C/σ_ρ)` 白化 ⇒ 传 `calib=(1,0,1,0)` + 真实 σ。
- `SonarBA34` 残差是 `A·az + B − o_beam` ⇒ 传 `calib=(1/σ_θ, 0, 1/σ_ρ, 0)`
  并把观测预先缩放成 `θ_obs/σ_θ`、`ρ_obs/σ_ρ`。
两者等价，只是缩放放在了不同位置。**不改任何既有文件即可对齐。**
"""
from __future__ import annotations

import io
import sys
from dataclasses import dataclass, field

import numpy as np
from scipy.optimize import least_squares

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from config import (Config, SonarCfg, SensorNoiseCfg, SceneCfg, TrajCfg,
                    finalize_pixel_mapping)
from world import SceneWorld
from trajectory import make_poses, euler_to_matrix
import observability as OBS

# ============================================================
# 主档传感器与几何（与 gen_scenes_main_f8.py 逐字一致，勿改）
# ============================================================
ARIS = dict(
    phi_max_deg=7.5,
    azim_deg=30.0,
    n_beams=128,
    rho_min_m=0.5,
    rho_max_m=15.0,
    range_bin_count=1600,
    sigma_rho_m=0.010,
    sigma_theta_deg=0.18,
)
Z_S = 4.5
PITCH_DEG = 19.0
D_T = 10.6
R_PILLAR = 0.25
H_TRUE = 0.85
N_FRAMES = 60
TAU_Z = 0.05

SIGMA_RHO = ARIS["sigma_rho_m"]
SIGMA_THETA = np.deg2rad(ARIS["sigma_theta_deg"])


def make_cfg(h=H_TRUE, heave=1.2, seed=801):
    """与 gen_scenes_main_f8.make_cfg 同构（同一主档构型）。"""
    cfg = Config(seed=seed)
    cfg.sonar = SonarCfg(
        fov_elevation_deg=(-ARIS["phi_max_deg"], ARIS["phi_max_deg"]),
        fov_azimuth_deg=(-ARIS["azim_deg"] / 2, ARIS["azim_deg"] / 2),
        beam_count=ARIS["n_beams"],
        range_bin_count=ARIS["range_bin_count"],
        range_min_m=ARIS["rho_min_m"],
        range_max_m=ARIS["rho_max_m"],
    )
    cfg.noise = SensorNoiseCfg(
        sigma_theta_rad=SIGMA_THETA,
        sigma_rho_m=SIGMA_RHO,
    )
    cfg.traj = TrajCfg(
        n_frames=N_FRAMES,
        keyframe_indices=list(range(0, N_FRAMES, 5)),
        dt_s=0.20,
        motion_mode="general" if heave > 0 else "forward",
        start_xyz=(0.0, 0.0, Z_S),
        start_rpy=(0.0, np.deg2rad(PITCH_DEG), 0.0),
        forward_total_m=0.0,
        sway_total_m=0.0,
        heave_amplitude_m=heave,
        pitch_amplitude_rad=0.0,
        yaw_amplitude_rad=0.0,
    )
    cfg.scene = SceneCfg(
        scene_type="pillar",
        pillars=[(D_T, 0.0, R_PILLAR, h)],
        cubes=[], spheres=[], rubble=[],
        floor_z_m=0.0,
        surface_z_m=Z_S + 1.0,
    )
    cfg.scene.h_avg_m = h
    cfg.scene.d_avg_m = D_T
    finalize_pixel_mapping(cfg)
    return cfg


# ============================================================
# 几何工具
# ============================================================
def poses6_to_T(poses6):
    """(K,6) → (K,4,4)。"""
    out = np.zeros((len(poses6), 4, 4))
    for i, p in enumerate(poses6):
        out[i] = np.eye(4)
        out[i][:3, :3] = euler_to_matrix(p[3], p[4], p[5])
        out[i][:3, 3] = p[:3]
    return out


def project(P_w, pose6):
    """世界点 → 该帧体系的 (θ, ρ)。与 BA / observability 的模型一致。"""
    R = euler_to_matrix(pose6[3], pose6[4], pose6[5])
    Pb = R.T @ (P_w - pose6[:3])
    return float(np.arctan2(Pb[1], Pb[0])), float(np.linalg.norm(Pb))


def visible_frames(P_w, poses6):
    """返回能看到 P_w 的帧索引（方位孔径 ∩ 量程 ∩ 仰角孔径，体系判定）。

    孔径可见性必须用**体系**俯角（措辞纪律 6）；世界系射线俯角只用于 CRLB 的 std(φ)。
    """
    az_lo = np.deg2rad(-ARIS["azim_deg"] / 2)
    az_hi = np.deg2rad(ARIS["azim_deg"] / 2)
    el_lo = np.deg2rad(-ARIS["phi_max_deg"])
    el_hi = np.deg2rad(ARIS["phi_max_deg"])
    keep = []
    for i, p in enumerate(poses6):
        R = euler_to_matrix(p[3], p[4], p[5])
        Pb = R.T @ (P_w - p[:3])
        rho = float(np.linalg.norm(Pb))
        az = float(np.arctan2(Pb[1], Pb[0]))
        el = float(np.arctan2(Pb[2], np.hypot(Pb[0], Pb[1])))
        if (az_lo <= az <= az_hi) and (ARIS["rho_min_m"] <= rho <= ARIS["rho_max_m"]) \
                and (el_lo <= el <= el_hi):
            keep.append(i)
    return np.array(keep, dtype=int)


def world_ray_elev(poses6, P_w):
    """世界系射线俯角序列 φ_k（CRLB 的 std(φ) 用这个，**不是**体系角）。"""
    d = np.hypot(P_w[0] - poses6[:, 0], P_w[1] - poses6[:, 1])
    return np.arctan2(P_w[2] - poses6[:, 2], d)


# ============================================================
# 解析 CRLB（独立路径：走 observability.py，不碰 BA）
# ============================================================
def crlb_frozen_pose(P_w, poses6, idx):
    """位姿已知的单路标 3×3 CRLB：σ_Pz = sqrt([Λ⁺]_zz)。

    直接调 `observability.compute_observability_per_landmark`，
    传 calib=(1,0,1,0) + 真实 σ ⇒ 其内部白化 (A/σ_θ, C/σ_ρ) 即标准白化。
    """
    obs_by_lm = {0: [(int(i), 0.0, 0.0) for i in idx]}   # beam/range 值不参与 Λ
    out = OBS.compute_observability_per_landmark(
        landmarks=P_w.reshape(1, 3),
        obs_by_lm=obs_by_lm,
        calib=(1.0, 0.0, 1.0, 0.0),
        poses6=poses6,
        tau_z=TAU_Z,
        sigma_rho=SIGMA_RHO,
        sigma_theta=SIGMA_THETA,
    )
    return dict(
        sigma_Pz=float(out["sigma_Pz"][0]),
        eigvals=out["eigvals"][0].copy(),
        classification=int(out["classification"][0]),
        n_obs=int(out["obs_count"][0]),
    )


def sigma_pz_std_phi_formula(std_phi, n_obs):
    """★I-1 的核心近似式 σ_Pz ≈ σ_ρ/(√N·std(φ))。"""
    if std_phi <= 1e-12:
        return np.inf
    return SIGMA_RHO / (np.sqrt(n_obs) * std_phi)


# ============================================================
# 阶段 A：位姿冻结的单路标蒙特卡洛（真跑非线性优化）
# ============================================================
@dataclass
class MCResult:
    n_trial: int
    z_hat: np.ndarray = field(repr=False)
    s_z: float = 0.0
    bias_z: float = 0.0
    n_fail: int = 0
    n_obs: int = 0


def mc_frozen_pose(P_w, poses6, idx, n_trial=300, seed=20260907,
                   perturb_init=0.05):
    """位姿固定为真值，只估路标 (x,y,z)。每次试验重新加噪并**真跑优化**。

    与解析界口径一致（位姿已知、单路标、白化残差）。
    `perturb_init` 让初值偏离真值，避免"从真值出发一步不动"的假象。
    """
    rng = np.random.default_rng(seed)
    P_sub = poses6[idx]
    th0 = np.empty(len(idx))
    rh0 = np.empty(len(idx))
    for k, p in enumerate(P_sub):
        th0[k], rh0[k] = project(P_w, p)

    R_sub = np.array([euler_to_matrix(p[3], p[4], p[5]) for p in P_sub])
    t_sub = P_sub[:, :3]

    def residual(P, th_obs, rh_obs):
        """白化残差：[(θ_pred−θ_obs)/σ_θ, (ρ_pred−ρ_obs)/σ_ρ]。"""
        Pb = np.einsum("kij,kj->ki", np.transpose(R_sub, (0, 2, 1)), P - t_sub)
        th = np.arctan2(Pb[:, 1], Pb[:, 0])
        rh = np.linalg.norm(Pb, axis=1)
        dth = (th - th_obs + np.pi) % (2 * np.pi) - np.pi
        return np.concatenate([dth / SIGMA_THETA, (rh - rh_obs) / SIGMA_RHO])

    z_hat, n_fail = [], 0
    for _ in range(n_trial):
        th_obs = th0 + rng.normal(0.0, SIGMA_THETA, size=len(idx))
        rh_obs = rh0 + rng.normal(0.0, SIGMA_RHO, size=len(idx))
        P_init = P_w + rng.normal(0.0, perturb_init, size=3)
        sol = least_squares(residual, P_init, args=(th_obs, rh_obs),
                            method="lm", xtol=1e-12, ftol=1e-12, max_nfev=500)
        if not sol.success:
            n_fail += 1
            continue
        z_hat.append(float(sol.x[2]))

    z_hat = np.asarray(z_hat)
    return MCResult(
        n_trial=n_trial,
        z_hat=z_hat,
        s_z=float(z_hat.std(ddof=1)) if z_hat.size > 1 else float("nan"),
        bias_z=float(z_hat.mean() - P_w[2]) if z_hat.size else float("nan"),
        n_fail=n_fail,
        n_obs=len(idx),
    )


# ============================================================
# 阶段 C：扫 std(φ)
# ============================================================
def build_scene(h=H_TRUE, heave=1.2, seed=801):
    """返回该构型下的 (poses6, P_top, 可见帧索引, std(φ))。"""
    cfg = make_cfg(h=h, heave=heave, seed=seed)
    poses6, _ = make_poses(cfg)
    P_top = np.array([D_T, 0.0, h])
    idx = visible_frames(P_top, poses6)
    phi = world_ray_elev(poses6[idx], P_top) if len(idx) else np.array([])
    std_phi = float(np.std(phi)) if len(phi) > 1 else 0.0
    return poses6, P_top, idx, std_phi
