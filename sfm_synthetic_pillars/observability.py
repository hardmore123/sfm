"""
可观测性分析
================

量化"声呐俯仰角缺失"导致的 BA 病态。
对每个 landmark 用其全部观测构建 J^T J (3x3, J = d(beam,range)/dP_world)，
特征值 λ1 ≥ λ2 ≥ λ3：
  - λ3 → 0 ：俯仰方向完全不可观测（病态）
  - λ2/λ3 大：单方向强约束（与 V4 的"λ2/λ3<20"判据一致）
  - 三特征值相当：完全可观测（well-constrained）

论文对应：
  - Huang 2015 Table II 讨论"退化运动"（forward / yaw_y）
  - V4 论文用 λ2/λ3 < 20 判良/欠约束
  - 大论文：用 Fisher 信息 / A^TA 特征值**贯穿全文**解释"为什么需要视场约束、为什么阴影先验才是真正补可观测性的信息源"
"""

from __future__ import annotations
import numpy as np
from typing import Tuple

from config import Config, C
from world import SceneWorld
from trajectory import euler_to_matrix


def _landmark_JTJ(landmark_world: np.ndarray, observations: list, calib, K: int,
                  poses6: np.ndarray) -> np.ndarray:
    """
    对单个 landmark 收集其全部观测的 d(beam,range)/dP_world，构建 J^T J (3x3)。

    observations: 兼容多种格式
      - (pose_idx, beam, range)  ← build_obs_by_lm 输出
      - (pose_idx, lm_idx, theta_rad, rho_m, beam, range)
    """
    A, B, C, D = calib
    R_wb = np.array([euler_to_matrix(p[3], p[4], p[5]) for p in poses6])   # (K, 3, 3)
    t_wb = poses6[:, :3]                                                    # (K, 3)
    if len(observations) < 2:
        return np.zeros((3, 3))
    J_list = []
    for o in observations:
        if len(o) == 3:
            pi, beam, rng = o
        elif len(o) >= 6:
            pi, _lm, _theta, _rho, beam, rng = o[0], o[1], o[2], o[3], o[4], o[5]
        else:
            continue
        R = R_wb[pi]
        t = t_wb[pi]
        P_w = landmark_world
        Pb = R.T @ (P_w - t)
        rho = np.linalg.norm(Pb) + 1e-6
        # ∂θ/∂P_w = ((-P_b_y, P_b_x, 0) / (P_b_x²+P_b_y²))^T @ R.T  (1, 3)
        dtheta_dP = np.array([-Pb[1], Pb[0], 0.0]) / (Pb[0] ** 2 + Pb[1] ** 2 + 1e-9)
        # ∂ρ/∂P_w = (P_b / ρ)^T @ R.T  (1, 3)
        drho_dP = (Pb / rho)
        # J = (2, 3): 行 0 = A * dtheta_dP, 行 1 = C * drho_dP
        # 两者实际是 P_b 的函数 → R.T 把 P_b 坐标系映到 P_w
        # drho_dP 沿 P_b 方向，需要映到 P_w：R @ (P_b / rho) 不是，
        # 应该是 R.T @ (P_b / rho)? 等等：P_b = R.T @ (P_w - t)，
        # ∂P_b/∂P_w = R.T ⇒ ∂ρ/∂P_w = (∂ρ/∂P_b)^T @ (∂P_b/∂P_w) = (P_b/ρ)^T @ R.T
        # 作为 1×3 行向量
        drho_dP_w = (Pb / rho) @ R.T          # (3,) 等价于 R @ (P_b/ρ)
        # 等等——行向量 (1,3) @ (3,3) = (1,3)；列向量 (3,) 直接 @ 不行
        # 这里 Pb/rho 是 (3,) 行向量理解下：(3,) @ (3,3) = (3,) ✓
        J = np.array([
            A * dtheta_dP,                    # 实际是 (3,) —— 也是行向量
            C * drho_dP_w,
        ])
        J_list.append(J)
    if len(J_list) < 2:
        return np.zeros((3, 3))
    # 拼成 (N, 2, 3)
    J_arr = np.stack(J_list, axis=0)         # (N, 2, 3)
    # J^T J 沿 N 累加
    return np.einsum("nij,nik->jk", J_arr, J_arr)


def compute_observability_per_landmark(
    landmarks: np.ndarray,        # (M, 3)
    obs_by_lm: dict,              # {lm_id: [(pose_idx, beam, range, ...), ...]}
    calib: tuple,                 # (A, B, C, D)
    poses6: np.ndarray,           # (K, 6)
    tau_z: float = 0.05,          # 高度精度要求 (m)
    sigma_rho: float = 0.05,      # 测距噪声 (m)
    sigma_theta: float = None,    # 测角噪声 (rad)，默认从 calib 推
) -> dict:
    """
    对每个 landmark 计算 A^TA 特征值 + CRLB 高度精度 + **四分类**判据。

    四分类（阶段表 P-1 TH2 + §4 X0）：
      - **insufficient**（观测不足）：obs_count < 2 或 λ3 = 0
      - **blind**（盲区）：σ_Pz > τ_z（CRLB 预测高度误差 > 5cm）
      - **weak**（弱约束）：σ_Pz ∈ (τ_z, 5·τ_z]
      - **well**（良约束）：σ_Pz ≤ τ_z

    Returns:
      'eigvals' : (M, 3) 三特征值
      'lambda3', 'lambda2', 'lambda1' : (M,) 特征值
      'ratios_32', 'ratios_21', 'ratios_31' : (M,) 比值
      'obs_count' : (M,) 观测数
      'sigma_Pz' : (M,) 高度估计 CRLB（m）
      'classification' : (M,) int (0=insufficient, 1=blind, 2=weak, 3=well)
      'well_mask' : (M,) bool  σ_Pz ≤ τ_z（向后兼容 V4）
      'blind_mask' : (M,) bool  σ_Pz > τ_z
      'weak_mask' : (M,) bool  τ_z < σ_Pz ≤ 5τ_z
      'insufficient_mask' : (M,) bool  obs < 2
    """
    M = landmarks.shape[0]
    eigvals = np.zeros((M, 3))
    obs_count = np.zeros(M, dtype=int)
    for j in range(M):
        obs = obs_by_lm.get(j, [])
        if len(obs) < 2:
            eigvals[j] = [0, 0, 0]
            obs_count[j] = len(obs)
            continue
        JTJ = _landmark_JTJ(landmarks[j], obs, calib, len(poses6), poses6)
        ev = np.linalg.eigvalsh(JTJ)
        ev = np.sort(ev)[::-1]   # 降序
        eigvals[j] = ev
        obs_count[j] = len(obs)
    eps = 1e-9
    l3 = np.maximum(eigvals[:, 2], eps)
    l2 = np.maximum(eigvals[:, 1], eps)
    l1 = np.maximum(eigvals[:, 0], eps)
    # CRLB 高度精度 σ_Pz = sqrt(Λ^{-1}_{zz}) ≈ sqrt(1/λ3)（简化）
    sigma_Pz = 1.0 / np.sqrt(l3)

    # 四分类
    classification = np.zeros(M, dtype=int)  # 默认 insufficient
    insufficient = obs_count < 2
    # 非 insufficient 的话，用 σ_Pz vs τ_z 分
    valid_obs = ~insufficient
    blind = valid_obs & (sigma_Pz > tau_z)
    weak = valid_obs & (sigma_Pz > tau_z) & (sigma_Pz <= 5 * tau_z)
    strong = valid_obs & (sigma_Pz <= tau_z)
    # 修正逻辑：blind = σ_Pz > 5τ_z（完全盲区），weak = τ_z < σ_Pz ≤ 5τ_z，well = σ_Pz ≤ τ_z
    blind = valid_obs & (sigma_Pz > 5 * tau_z)
    weak = valid_obs & (tau_z < sigma_Pz) & (sigma_Pz <= 5 * tau_z)
    well = valid_obs & (sigma_Pz <= tau_z)
    classification[insufficient] = 0
    classification[blind] = 1
    classification[weak] = 2
    classification[well] = 3

    return {
        "eigvals": eigvals,
        "lambda3": l3,
        "lambda2": l2,
        "lambda1": l1,
        "ratios_32": l3 / l2,
        "ratios_21": l2 / l1,
        "ratios_31": l3 / l1,
        "obs_count": obs_count,
        "sigma_Pz": sigma_Pz,
        "classification": classification,
        "well_mask": well,
        "blind_mask": blind,
        "weak_mask": weak,
        "insufficient_mask": insufficient,
    }


def summarize_observability(obs_dict: dict, mode_name: str = "default") -> str:
    """生成可观测性分析的可读报告（含四分类统计）。"""
    l1, l2, l3 = obs_dict["lambda1"], obs_dict["lambda2"], obs_dict["lambda3"]
    r32 = obs_dict["ratios_32"]
    sigma_Pz = obs_dict.get("sigma_Pz")
    n_well = int(obs_dict["well_mask"].sum())
    n_weak = int(obs_dict["weak_mask"].sum())
    n_blind = int(obs_dict["blind_mask"].sum())
    n_insuf = int(obs_dict["insufficient_mask"].sum())
    n = len(l3)
    txt = f"=== 可观测性分析 [{mode_name}] ===\n"
    txt += f"landmarks: {n}\n"
    txt += f"四分类统计:\n"
    txt += f"  insufficient (obs<2):    {n_insuf} ({n_insuf/n*100:.1f}%)\n"
    txt += f"  blind (σ_Pz>5τ_z):       {n_blind} ({n_blind/n*100:.1f}%)\n"
    txt += f"  weak (τ_z<σ_Pz≤5τ_z):    {n_weak} ({n_weak/n*100:.1f}%)\n"
    txt += f"  well (σ_Pz≤τ_z):         {n_well} ({n_well/n*100:.1f}%)\n"
    txt += f"λ3 分布: min={l3.min():.2e}, median={np.median(l3):.2e}, max={l3.max():.2e}\n"
    txt += f"λ3/λ2 分布: min={r32.min():.4f}, median={np.median(r32):.4f}, max={r32.max():.4f}\n"
    if sigma_Pz is not None:
        txt += f"σ_Pz 分布: min={sigma_Pz.min():.3f}, median={np.median(sigma_Pz):.3f}, max={sigma_Pz.max():.3f}\n"
    return txt
