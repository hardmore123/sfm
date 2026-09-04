"""
表面评价模块（任务 T0.11）
============================

阶段表 §4 T0.11 验收：
  - 单元测试：平移 5 cm 点云对的 Chamfer = 5 cm ± 1%
  - 自比 = 0
  - 同步实现 Hausdorff、法向角误差、漂浮点密度、point-to-surface

度量定义（参考 Aykin 2017 式(8)(9)）：
  Chamfer: 双向平均最近点距离
    C(P, Q) = (1/|P|) Σ_p∈P min_q∈Q ||p - q|| + (1/|Q|) Σ_q∈Q min_p∈P ||q - p||
  Hausdorff: 双向最大最近点距离
    H(P, Q) = max(max_p∈P min_q∈Q ||p - q||, max_q∈Q min_p∈P ||q - p||)
  Volumetric: Aykin 2017 式(8)
    E = (V + V_tilde - 2 V∩) / (V + V_tilde - V∩)
  法向角误差：arccos(|n_p · n_q|)
  Point-to-surface：点到最近平面的距离
"""
from __future__ import annotations
import numpy as np
from typing import Optional, Tuple


def chamfer_distance(
    P: np.ndarray, Q: np.ndarray,
    max_n: int = 10000,
) -> float:
    """
    Chamfer 距离（双向平均最近点距离）。
    P, Q: (N, 3) and (M, 3) 点云
    返回: 平均最近点距离（米）
    """
    if len(P) == 0 or len(Q) == 0:
        return float("inf")
    from scipy.spatial import cKDTree
    # 抽样加速
    if len(P) > max_n:
        idx = np.random.choice(len(P), max_n, replace=False)
        P = P[idx]
    if len(Q) > max_n:
        idx = np.random.choice(len(Q), max_n, replace=False)
        Q = Q[idx]
    tree_Q = cKDTree(Q)
    tree_P = cKDTree(P)
    d_pq, _ = tree_Q.query(P)  # P → Q 最近距离
    d_qp, _ = tree_P.query(Q)  # Q → P 最近距离
    return float(d_pq.mean() + d_qp.mean()) / 2


def hausdorff_distance(
    P: np.ndarray, Q: np.ndarray,
    max_n: int = 10000,
) -> float:
    """
    Hausdorff 距离（双向最大最近点距离）。
    """
    if len(P) == 0 or len(Q) == 0:
        return float("inf")
    from scipy.spatial import cKDTree
    if len(P) > max_n:
        idx = np.random.choice(len(P), max_n, replace=False)
        P = P[idx]
    if len(Q) > max_n:
        idx = np.random.choice(len(Q), max_n, replace=False)
        Q = Q[idx]
    tree_Q = cKDTree(Q)
    tree_P = cKDTree(P)
    d_pq, _ = tree_Q.query(P)
    d_qp, _ = tree_P.query(Q)
    return float(max(d_pq.max(), d_qp.max()))


def normal_angle_error(
    P: np.ndarray, N_p: np.ndarray,
    Q: np.ndarray, N_q: np.ndarray,
    max_n: int = 5000,
) -> Tuple[float, float]:
    """
    法向角误差（最近点配对）。
    P, N_p: 重建点云 + 法向
    Q, N_q: GT 点云 + 法向
    返回: (mean error in rad, max error in rad)
    """
    if len(P) == 0 or len(Q) == 0:
        return float("inf"), float("inf")
    from scipy.spatial import cKDTree
    if len(P) > max_n:
        idx = np.random.choice(len(P), max_n, replace=False)
        P, N_p = P[idx], N_p[idx]
    if len(Q) > max_n:
        idx = np.random.choice(len(Q), max_n, replace=False)
        Q, N_q = Q[idx], N_q[idx]
    tree_Q = cKDTree(Q)
    _, idx_q = tree_Q.query(P)  # P → Q 最近点索引
    # 配对的法向夹角
    n_p_norm = N_p / np.maximum(np.linalg.norm(N_p, axis=1, keepdims=True), 1e-9)
    n_q_norm = N_q / np.maximum(np.linalg.norm(N_q, axis=1, keepdims=True), 1e-9)
    cos_a = np.abs(np.sum(n_p_norm * n_q_norm[idx_q], axis=1))
    cos_a = np.clip(cos_a, 0.0, 1.0)
    angles = np.arccos(cos_a)
    return float(angles.mean()), float(angles.max())


def point_to_surface_distance(
    P: np.ndarray, Q: np.ndarray, N_q: np.ndarray,
    max_n: int = 5000,
) -> float:
    """
    P 中每点到 Q 局部平面的距离。
    局部平面 = Q 最近点 + 法向。
    """
    if len(P) == 0 or len(Q) == 0:
        return float("inf")
    from scipy.spatial import cKDTree
    if len(P) > max_n:
        idx = np.random.choice(len(P), max_n, replace=False)
        P = P[idx]
    if len(Q) > max_n:
        idx = np.random.choice(len(Q), max_n, replace=False)
        Q, N_q = Q[idx], N_q[idx]
    tree_Q = cKDTree(Q)
    d, idx_q = tree_Q.query(P)
    # 局部平面：Q[idx_q] + N_q[idx_q] * t
    # P 到平面的距离 = (P - Q[idx_q]) · N_q[idx_q]
    n_norm = N_q[idx_q] / np.maximum(np.linalg.norm(N_q[idx_q], axis=1, keepdims=True), 1e-9)
    signed_dist = np.sum((P - Q[idx_q]) * n_norm, axis=1)
    return float(np.abs(signed_dist).mean())


def volumetric_error(
    P: np.ndarray, Q: np.ndarray,
    voxel_size: float = 0.02,
) -> float:
    """
    Aykin 2017 式(8) volumetric error：
    E = (V + V_tilde - 2 V∩) / (V + V_tilde - V∩)
    其中 V, V_tilde, V∩ 用体素化近似。
    """
    if len(P) == 0 or len(Q) == 0:
        return float("inf")
    # 体素化（在 P, Q 公共 bbox 内）
    bbox_min = np.minimum(P.min(axis=0), Q.min(axis=0))
    bbox_max = np.maximum(P.max(axis=0), Q.max(axis=0))
    dims = np.ceil((bbox_max - bbox_min) / voxel_size).astype(int) + 1
    dims = np.maximum(dims, 1)  # 至少 1
    V = np.zeros(dims, dtype=bool)
    V_tilde = np.zeros(dims, dtype=bool)
    p_idx = np.floor((P - bbox_min) / voxel_size).astype(int)
    t_idx = np.floor((Q - bbox_min) / voxel_size).astype(int)
    p_idx = np.clip(p_idx, 0, dims - 1)
    t_idx = np.clip(t_idx, 0, dims - 1)
    V[p_idx[:, 0], p_idx[:, 1], p_idx[:, 2]] = True
    V_tilde[t_idx[:, 0], t_idx[:, 1], t_idx[:, 2]] = True
    V_count = V.sum()
    V_tilde_count = V_tilde.sum()
    V_inter = (V & V_tilde).sum()
    V_union = (V | V_tilde).sum()
    if V_union == 0:
        return 0.0
    E = (V_count + V_tilde_count - 2 * V_inter) / max(V_union, 1)
    return float(E)


def floating_point_density(
    P: np.ndarray, R: float = 0.05,
) -> float:
    """
    漂浮点密度 = 在 P 附近 R 球内没点的 P 占比。
    物理意义：建出的点云中"孤立点"（无近邻）= 漂浮/噪声点。
    """
    if len(P) == 0:
        return 0.0
    from scipy.spatial import cKDTree
    tree = cKDTree(P)
    # 每个点的最近邻距离
    nn_d, _ = tree.query(P, k=2)
    nn_d = nn_d[:, 1]  # 排除自身
    floating = (nn_d > R).sum() / len(P)
    return float(floating)


def evaluate_surface(
    P_recon: np.ndarray, N_recon: np.ndarray,
    P_gt: np.ndarray, N_gt: np.ndarray,
    voxel_size: float = 0.02,
) -> dict:
    """
    综合表面评价。

    P_recon, N_recon: 重建点云 + 法向（可空）
    P_gt, N_gt: GT 点云 + 法向

    返回：字典含所有指标
    """
    result = {
        "chamfer_m": chamfer_distance(P_recon, P_gt) if len(P_recon) > 0 else float("inf"),
        "hausdorff_m": hausdorff_distance(P_recon, P_gt) if len(P_recon) > 0 else float("inf"),
        "volumetric_err": volumetric_error(P_recon, P_gt, voxel_size) if len(P_recon) > 0 else float("inf"),
        "floating_ratio": floating_point_density(P_recon) if len(P_recon) > 0 else 0.0,
    }
    if len(P_recon) > 0 and len(N_recon) > 0 and len(P_gt) > 0 and len(N_gt) > 0:
        mean_n, max_n = normal_angle_error(P_recon, N_recon, P_gt, N_gt)
        result["normal_angle_mean_rad"] = mean_n
        result["normal_angle_max_rad"] = max_n
        result["point_to_surface_m"] = point_to_surface_distance(P_recon, P_gt, N_gt)
    return result
