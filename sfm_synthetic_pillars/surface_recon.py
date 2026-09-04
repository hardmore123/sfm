"""
置信度引导的加权曲面重建原型
================================

创新点一·模块4 的轻量原型：
  - 从 BA 优化后的点云出发
  - 用每个点的**置信度**（来自观测重复数 / 优化残差倒数）
  - 估算法向：加权 PCA
  - 重建曲面：基于 Open3D 的 Poisson Reconstruction（如果可用），
    否则退化为有向点云 + 法向输出

设计原则：
  - 任何点云都给出法向和加权信息（不依赖 Open3D）
  - 有 Open3D 时跑完整 Poisson 重建
  - 输出 .ply 供 view3d.py / MeshLab 查看
"""

from __future__ import annotations
import os
import numpy as np
from typing import Tuple, Optional


def estimate_normals_weighted_pca(
    points: np.ndarray,         # (N, 3)
    weights: np.ndarray,        # (N,) 置信度
    k: int = 16,
) -> np.ndarray:
    """
    加权 PCA 法向估计：对每个点取 k 近邻，构建加权协方差矩阵，主成分为法向。

    权重应用：每个邻域点的权重 w_i，邻域中心用 w_i 加权均值。
    """
    from scipy.spatial import cKDTree
    N = points.shape[0]
    normals = np.zeros_like(points)
    tree = cKDTree(points)
    # 防止权重全 0
    w = np.maximum(weights, 1e-6)
    w_sum_global = w.sum()
    for i in range(N):
        dist, idx = tree.query(points[i], k=min(k, N))
        idx = np.atleast_1d(idx)
        pts_nb = points[idx]
        w_nb = w[idx]
        w_nb = w_nb / w_nb.sum()                         # 局部归一
        center = (pts_nb * w_nb[:, None]).sum(axis=0)
        diff = pts_nb - center
        C = (diff * w_nb[:, None]).T @ diff              # (3, 3) 加权协方差
        evals, evecs = np.linalg.eigh(C)                  # 升序
        normals[i] = evecs[:, 0]                          # 最小特征值对应的特征向量
    # 朝向一致化：让法向朝向点云中心（粗略方法）
    centroid = (points * w[:, None]).sum(axis=0) / w_sum_global
    flip = ((points - centroid) * normals).sum(axis=1) < 0
    normals[flip] *= -1
    return normals


def reconstruct_poisson_open3d(points: np.ndarray, normals: np.ndarray,
                                weights: np.ndarray, depth: int = 8):
    """
    用 Open3D 跑 Poisson Surface Reconstruction。
    weights 通过"点密度"间接影响：构造点云时按权重复制（重采样）。

    返回 Open3D TriangleMesh 或 None（Open3D 不可用时）。
    """
    try:
        import open3d as o3d
    except ImportError:
        return None
    # 按权重重采样
    n_repeat = np.maximum((weights * 50).astype(int), 1)
    pts_rep = np.repeat(points, n_repeat, axis=0)
    nls_rep = np.repeat(normals, n_repeat, axis=0)
    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(pts_rep)
    pcd.normals = o3d.utility.Vector3dVector(nls_rep)
    mesh, densities = o3d.geometry.TriangleMesh.create_from_point_cloud_poisson(
        pcd, depth=depth, width=0, scale=1.1, linear_fit=False)
    # 去除低密度顶点（漂浮物抑制）
    densities = np.asarray(densities)
    if len(densities) > 0:
        density_thr = np.quantile(densities, 0.02)
        keep = densities > density_thr
        mesh.remove_vertices_by_mask(~keep)
    return mesh


def save_ply_with_normals(path: str, points: np.ndarray, normals: np.ndarray,
                          weights: Optional[np.ndarray] = None) -> None:
    """保存带法向+置信度的 .ply 供查看。"""
    with open(path, "w") as f:
        f.write("ply\nformat ascii 1.0\n")
        f.write(f"element vertex {len(points)}\n")
        f.write("property float x\nproperty float y\nproperty float z\n")
        f.write("property float nx\nproperty float ny\nproperty float nz\n")
        if weights is not None:
            f.write("property float confidence\n")
        f.write("end_header\n")
        for i in range(len(points)):
            if weights is not None:
                f.write(f"{points[i,0]:.4f} {points[i,1]:.4f} {points[i,2]:.4f} "
                        f"{normals[i,0]:.4f} {normals[i,1]:.4f} {normals[i,2]:.4f} "
                        f"{weights[i]:.4f}\n")
            else:
                f.write(f"{points[i,0]:.4f} {points[i,1]:.4f} {points[i,2]:.4f} "
                        f"{normals[i,0]:.4f} {normals[i,1]:.4f} {normals[i,2]:.4f}\n")
