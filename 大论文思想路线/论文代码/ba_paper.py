# -*- coding: utf-8 -*-
"""
【论文开发版】—— 请勿与项目基线 ba_optimize.py 混用
================================================
本文件是从项目基线 ba_optimize.py 复制而来的独立副本, 专供“大论文”方向修改,
用于承载两个创新点的实现 (创新点一: 几何优化层 BA 各模块; 创新点二: 声学阴影
分割 ViT+LoRA 注入高度/仰角先验)。对本文件的任何改动都不会影响项目基线代码。

  - 项目基线 (冻结, 勿改) : ../../ba_optimize.py
  - 专利开发版             : 专利/专利代码/ba_patent.py
  - 论文开发版 (本文件)    : 大论文思想路线/论文代码/ba_paper.py
------------------------------------------------

声呐三维重建 —— Bundle Adjustment (BA) 优化
================================================

本脚本对已有的声呐 SfM 结果进行光束平差(BA)联合优化：
    - 输入位姿:   poses_est.npy        (10, 4, 4)  关键帧 body->world 变换矩阵 T_wb
    - 关键帧编号: pose_frame_ids.npy   (10,)       [0,15,20,25,30,35,40,45,50,55]
    - 输入点云:   landmarks_final.npy  (217, 3)    世界坐标系下的三维路标 (XYZ)
    - 数据关联:   tracks.csv                        每帧每条 track 的声呐观测 (theta, rho)

声呐观测模型 (成像声呐 / forward-looking sonar):
    路标世界坐标 P_w -> 载体系:  P_b = R_f^T (P_w - t_f)
    方位角  theta = atan2(y_b, x_b)
    斜距    rho   = ||P_b||               (3D 距离)
    (俯仰角不可观测, 即声呐的仰角歧义, 由多帧观测 + 里程计约束共同求解)

BA 残差项:
    1) 位姿先验:   固定第 0 帧 (规范/gauge 约束)
    2) 里程计约束: 相邻关键帧之间的相对位姿 (由初始 poses_est 推得)
    3) 声呐重投影: 每个关键帧观测的 (theta, rho) 残差
    4) 路标弱先验: 拉向初始点云, 稳定欠约束(仅单帧可见)的路标

优化变量:  10 个位姿 (每个 6 维: x,y,z,roll,pitch,yaw) + N 个路标 (每个 3 维 XYZ)

输出:
    - poses_optimized.npy        优化后的位姿 (10,4,4)
    - landmarks_optimized.npy    优化后的点云 (N,3)
    - landmarks_optimized.ply    优化后的点云 (可用 MeshLab/CloudCompare 查看)
    - ba_result.png              优化前后的三维对比图
"""

import numpy as np
from scipy.optimize import least_squares
import matplotlib

matplotlib.use("Agg")  # 无界面后端：保存图片、不弹窗、不阻塞
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401
import csv
import os

# ==========================================
# 1. 基础数学工具 (与 12.5新.py 的欧拉约定保持一致: R = Rz@Ry@Rx)
# ==========================================

def euler_to_matrix(roll, pitch, yaw):
    cr, sr = np.cos(roll), np.sin(roll)
    cp, sp = np.cos(pitch), np.sin(pitch)
    cy, sy = np.cos(yaw), np.sin(yaw)
    Rx = np.array([[1, 0, 0], [0, cr, -sr], [0, sr, cr]])
    Ry = np.array([[cp, 0, sp], [0, 1, 0], [-sp, 0, cp]])
    Rz = np.array([[cy, -sy, 0], [sy, cy, 0], [0, 0, 1]])
    return Rz @ Ry @ Rx


def matrix_to_euler(R):
    """R = Rz(yaw) Ry(pitch) Rx(roll) 的逆运算 -> (roll, pitch, yaw)。"""
    sy = np.sqrt(R[2, 1] ** 2 + R[2, 2] ** 2)
    if sy > 1e-9:
        roll = np.arctan2(R[2, 1], R[2, 2])
        pitch = np.arctan2(-R[2, 0], sy)
        yaw = np.arctan2(R[1, 0], R[0, 0])
    else:  # 万向锁
        roll = np.arctan2(-R[1, 2], R[1, 1])
        pitch = np.arctan2(-R[2, 0], sy)
        yaw = 0.0
    return np.array([roll, pitch, yaw])


def normalize_angle(a):
    return (a + np.pi) % (2 * np.pi) - np.pi


def pose6_to_matrix(p):
    T = np.eye(4)
    T[:3, :3] = euler_to_matrix(p[3], p[4], p[5])
    T[:3, 3] = p[:3]
    return T


def matrix_to_pose6(T):
    p = np.zeros(6)
    p[:3] = T[:3, 3]
    p[3:] = matrix_to_euler(T[:3, :3])
    return p


def rot_to_vec(R):
    """旋转矩阵 -> 旋转向量 (轴角), 用于位姿相对残差。"""
    cos_theta = (np.trace(R) - 1.0) * 0.5
    cos_theta = np.clip(cos_theta, -1.0, 1.0)
    theta = np.arccos(cos_theta)
    if theta < 1e-8:
        return np.zeros(3)
    if np.pi - theta < 1e-6:
        # 接近 pi, 用对称部分求解
        A = (R + np.eye(3)) * 0.5
        axis = np.sqrt(np.maximum(np.diag(A), 0.0))
        return axis * theta
    v = np.array([R[2, 1] - R[1, 2],
                  R[0, 2] - R[2, 0],
                  R[1, 0] - R[0, 1]])
    return v / (2.0 * np.sin(theta)) * theta


# ==========================================
# 2. 数据加载
# ==========================================

def load_data(folder="."):
    poses_mat = np.load(os.path.join(folder, "poses_est.npy"))          # (K,4,4)
    frame_ids = np.load(os.path.join(folder, "pose_frame_ids.npy"))     # (K,)
    landmarks = np.load(os.path.join(folder, "landmarks_final.npy"))    # (M,3)

    tracks = []  # (frame_id, track_id, theta_rad, rho_m, beam_index, range_index)
    with open(os.path.join(folder, "tracks.csv"), "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            tracks.append((int(row["frame_id"]),
                           int(row["track_id"]),
                           float(row["theta_rad"]),
                           float(row["rho_m"]),
                           float(row["beam_index"]),
                           float(row["range_index"])))
    return poses_mat, frame_ids, landmarks, tracks


def calibrate_pixels(tracks):
    """从 tracks.csv 自标定像素映射: beam = A*theta + B, range = C*rho + D。"""
    th = np.array([t[2] for t in tracks])
    rh = np.array([t[3] for t in tracks])
    bm = np.array([t[4] for t in tracks])
    rg = np.array([t[5] for t in tracks])
    A, B = np.polyfit(th, bm, 1)
    C, D = np.polyfit(rh, rg, 1)
    return A, B, C, D


# ==========================================
# 3. 恢复 track_id -> 路标行号 的映射
#    landmarks_final 只包含 217 个被三角化的路标, 其行号对应
#    某个 track_id 子集的排序结果, 因此需要通过重投影匹配来恢复。
# ==========================================

def build_track_to_landmark(poses_mat, frame_ids, landmarks, tracks):
    K = len(frame_ids)
    M = landmarks.shape[0]
    fid_to_idx = {int(fid): i for i, fid in enumerate(frame_ids)}

    # 预计算每个关键帧的 R^T 与 t
    Rt = np.zeros((K, 3, 3))
    tt = np.zeros((K, 3))
    for i in range(K):
        Rt[i] = poses_mat[i, :3, :3].T
        tt[i] = poses_mat[i, :3, 3]

    # 收集关键帧上的观测, 按 track 归类
    obs_by_track = {}
    for tk in tracks:
        fid, tid, theta, rho = tk[0], tk[1], tk[2], tk[3]
        if fid in fid_to_idx:
            obs_by_track.setdefault(tid, []).append((fid_to_idx[fid], theta, rho))

    # 对每个路标, 在其可能观测到的关键帧上预测 (theta,rho)
    def predict(k, pose_idx):
        Pb = Rt[pose_idx] @ (landmarks[k] - tt[pose_idx])
        theta = np.arctan2(Pb[1], Pb[0])
        rho = np.linalg.norm(Pb)
        return theta, rho

    track_to_lm = {}
    lm_used = set()
    # 对每个 track 找重投影误差最小的路标
    for tid, obs in obs_by_track.items():
        best_k, best_err = -1, 1e18
        for k in range(M):
            err = 0.0
            for (pi, th, rh) in obs:
                pth, prh = predict(k, pi)
                err += normalize_angle(pth - th) ** 2 + (prh - rh) ** 2
            err /= len(obs)
            if err < best_err:
                best_err, best_k = err, k
        # 只接受匹配良好的关联 (阈值可调)
        if best_err < 1e-3 and best_k not in lm_used:
            track_to_lm[tid] = best_k
            lm_used.add(best_k)

    return track_to_lm


# ==========================================
# 4. BA 优化器
# ==========================================

class SonarBA:
    def __init__(self, poses6, landmarks, observations, odom_rel,
                 pixel_calib, weights=None, huber_delta=20.0):
        """
        poses6:       (K,6)  初始位姿
        landmarks:    (M,3)  初始路标
        observations: list of (pose_idx, lm_idx, theta, rho, beam, range)
        odom_rel:     list of (k, T_rel_meas 4x4)  相邻关键帧相对位姿测量(真实里程计)
        pixel_calib:  (A,B,C,D)  beam=A*theta+B, range=C*rho+D
        huber_delta:  Huber 鲁棒核阈值 (像素)
        """
        self.K = poses6.shape[0]
        self.M = landmarks.shape[0]
        self.poses0 = poses6.copy()
        self.land0 = landmarks.copy()
        self.odom_rel = odom_rel
        self.A, self.B, self.C, self.D = pixel_calib
        self.huber_delta = huber_delta

        # 观测向量化
        self.o_pose = np.array([o[0] for o in observations], dtype=np.int64)
        self.o_lm = np.array([o[1] for o in observations], dtype=np.int64)
        self.o_beam = np.array([o[4] for o in observations], dtype=np.float64)
        self.o_range = np.array([o[5] for o in observations], dtype=np.float64)

        w = weights or {}
        self.w_prior = w.get("prior", 1000.0)    # 第0帧规范约束(强)
        self.w_odomT = w.get("odomT", 100.0)      # 里程计平移(真实但不完美)
        self.w_odomR = w.get("odomR", 100.0)      # 里程计旋转
        self.w_sonar = w.get("sonar", 1.0)        # 声呐重投影(像素)
        self.w_lmprior = w.get("lmprior", 1.0)    # 路标弱先验

        self.x0 = np.concatenate([self.poses0.flatten(), self.land0.flatten()])

    def unpack(self, x):
        poses = x[: self.K * 6].reshape(self.K, 6)
        lms = x[self.K * 6:].reshape(self.M, 3)
        return poses, lms

    def residuals(self, x):
        poses, lms = self.unpack(x)
        res = []

        # 1) 第0帧先验 (固定初始位姿, 消除规范自由度)
        res.append(self.w_prior * (poses[0] - self.poses0[0]))

        # 2) 里程计相对位姿约束
        for (k, T_meas) in self.odom_rel:
            Tk = pose6_to_matrix(poses[k])
            Tk1 = pose6_to_matrix(poses[k + 1])
            T_rel = np.linalg.inv(Tk) @ Tk1
            Err = np.linalg.inv(T_meas) @ T_rel
            e_t = self.w_odomT * Err[:3, 3]
            e_r = self.w_odomR * rot_to_vec(Err[:3, :3])
            res.append(np.concatenate([e_t, e_r]))

        # 3) 声呐重投影残差 (像素量纲, 向量化)
        R = np.array([euler_to_matrix(p[3], p[4], p[5]) for p in poses])  # (K,3,3)
        Rt = np.transpose(R, (0, 2, 1))                                   # (K,3,3)
        t = poses[:, :3]                                                  # (K,3)
        Pw = lms[self.o_lm]                                              # (Nobs,3)
        diff = Pw - t[self.o_pose]                                        # (Nobs,3)
        Pb = np.einsum("nij,nj->ni", Rt[self.o_pose], diff)              # (Nobs,3)
        theta_pred = np.arctan2(Pb[:, 1], Pb[:, 0])
        rho_pred = np.linalg.norm(Pb, axis=1)
        u_pred = self.A * theta_pred + self.B
        v_pred = self.C * rho_pred + self.D
        res.append(self.w_sonar * (u_pred - self.o_beam))
        res.append(self.w_sonar * (v_pred - self.o_range))

        # 4) 路标弱先验
        res.append(self.w_lmprior * (lms - self.land0).flatten())

        return np.concatenate(res)

    def optimize(self, verbose=2):
        r0 = self.residuals(self.x0)
        print(f"初始代价 (0.5*||r||^2) = {0.5 * np.sum(r0 ** 2):.6f}, "
              f"RMS = {np.sqrt(np.mean(r0 ** 2)):.6f}")
        result = least_squares(self.residuals, self.x0, method="trf",
                               loss="huber", f_scale=self.huber_delta,
                               verbose=verbose, max_nfev=200)
        rf = result.fun
        print(f"优化后代价 (0.5*||r||^2) = {0.5 * np.sum(rf ** 2):.6f}, "
              f"RMS = {np.sqrt(np.mean(rf ** 2)):.6f}")
        poses, lms = self.unpack(result.x)
        return poses, lms, result


# ==========================================
# 5. 可视化 (优化前 vs 优化后)
# ==========================================

def draw_frame(ax, position, R, length=0.15, lw=1.0):
    ax.quiver(*position, R[0, 0], R[1, 0], R[2, 0], length=length, color="r", linewidth=lw)
    ax.quiver(*position, R[0, 1], R[1, 1], R[2, 1], length=length, color="g", linewidth=lw)
    ax.quiver(*position, R[0, 2], R[1, 2], R[2, 2], length=length, color="b", linewidth=lw)


def set_equal_aspect(ax, pts):
    x, y, z = pts[:, 0], pts[:, 1], pts[:, 2]
    max_range = max(x.max() - x.min(), y.max() - y.min(), z.max() - z.min()) / 2.0
    mx, my, mz = (x.max() + x.min()) / 2, (y.max() + y.min()) / 2, (z.max() + z.min()) / 2
    ax.set_xlim(mx - max_range, mx + max_range)
    ax.set_ylim(my - max_range, my + max_range)
    ax.set_zlim(mz - max_range, mz + max_range)


def visualize(poses0, land0, poses_opt, land_opt, save_path="ba_result.png"):
    fig = plt.figure(figsize=(16, 7))

    for col, (title, poses6, lms, color) in enumerate([
        ("Initial (before BA)", poses0, land0, "gray"),
        ("Optimized (after BA)", poses_opt, land_opt, "blue"),
    ]):
        ax = fig.add_subplot(1, 2, col + 1, projection="3d")
        pos = poses6[:, :3]
        ax.plot(pos[:, 0], pos[:, 1], pos[:, 2], "k--", lw=1, alpha=0.6, label="Trajectory")
        ax.scatter(lms[:, 0], lms[:, 1], lms[:, 2], c=color, s=8, alpha=0.7, label="Landmarks")
        for i in range(len(poses6)):
            draw_frame(ax, pos[i], euler_to_matrix(*poses6[i, 3:]), length=0.12)
        ax.text(*pos[0], "Start", fontsize=9)
        ax.text(*pos[-1], "End", fontsize=9)
        allpts = np.vstack([lms, pos])
        set_equal_aspect(ax, allpts)
        ax.set_xlabel("X (m)"); ax.set_ylabel("Y (m)"); ax.set_zlabel("Z (m)")
        ax.set_title(title)
        ax.legend(loc="upper right")

    plt.tight_layout()
    if save_path:
        plt.savefig(save_path, dpi=150)
        print(f"已保存对比图: {save_path}")
    plt.close(fig)


def visualize_topview(poses0, land0, poses_opt, land_opt, save_path="ba_topview.png"):
    """俯视图: 投影到 XY 平面 (沿 Z 轴向下看)。"""
    fig, axes = plt.subplots(1, 2, figsize=(15, 7))
    for ax, (title, poses6, lms, color) in zip(axes, [
        ("Initial (before BA)", poses0, land0, "gray"),
        ("Optimized (after BA)", poses_opt, land_opt, "blue"),
    ]):
        ax.scatter(lms[:, 0], lms[:, 1], c=color, s=8, alpha=0.7, label="Landmarks")
        ax.plot(poses6[:, 0], poses6[:, 1], "k--", lw=1, alpha=0.6, label="Trajectory")
        ax.scatter(poses6[:, 0], poses6[:, 1], c="red", s=25, zorder=3)
        ax.annotate("Start", poses6[0, :2]); ax.annotate("End", poses6[-1, :2])
        ax.set_xlabel("X (m)"); ax.set_ylabel("Y (m)")
        ax.set_aspect("equal", adjustable="datalim")
        ax.set_title(title + " - Top View (XY)")
        ax.grid(True, ls=":", alpha=0.5)
        ax.legend(loc="upper right")
    plt.tight_layout()
    if save_path:
        plt.savefig(save_path, dpi=150)
        print(f"已保存俯视图: {save_path}")
    plt.close(fig)


def save_ply(path, points):
    with open(path, "w") as f:
        f.write("ply\nformat ascii 1.0\n")
        f.write(f"element vertex {len(points)}\n")
        f.write("property float x\nproperty float y\nproperty float z\n")
        f.write("end_header\n")
        for p in points:
            f.write(f"{p[0]:.6f} {p[1]:.6f} {p[2]:.6f}\n")
    print(f"已保存点云: {path}")


# ==========================================
# 6. 主流程
# ==========================================

def main(folder=".", out_folder=None):
    if out_folder is None:
        out_folder = folder
    os.makedirs(out_folder, exist_ok=True)
    poses_mat, frame_ids, landmarks, tracks = load_data(folder)
    K = len(frame_ids)
    print(f"关键帧数: {K}, 帧编号: {list(map(int, frame_ids))}")
    print(f"初始路标数: {landmarks.shape[0]}, 观测总数: {len(tracks)}")

    # --- 位姿转 6 维 ---
    poses6 = np.array([matrix_to_pose6(poses_mat[i]) for i in range(K)])

    # --- 恢复 track -> landmark 映射 ---
    track_to_lm = build_track_to_landmark(poses_mat, frame_ids, landmarks, tracks)
    print(f"成功关联 track->landmark 数: {len(track_to_lm)}")

    # --- 像素自标定 ---
    A, B, C, D = calibrate_pixels(tracks)
    print(f"像素标定: beam={A:.3f}*theta+{B:.3f}, range={C:.3f}*rho+{D:.3f}")

    # --- 组织关键帧观测 ---
    fid_to_idx = {int(fid): i for i, fid in enumerate(frame_ids)}
    observations = []
    for (fid, tid, theta, rho, beam, rng) in tracks:
        if fid in fid_to_idx and tid in track_to_lm:
            observations.append((fid_to_idx[fid], track_to_lm[tid], theta, rho, beam, rng))
    print(f"参与 BA 的声呐观测数: {len(observations)}")

    # 每个路标的观测次数统计
    cnt = np.zeros(landmarks.shape[0], dtype=int)
    for o in observations:
        cnt[o[1]] += 1
    print(f"路标平均被观测次数: {cnt[cnt > 0].mean():.2f}, "
          f"多帧(>=2)可见路标: {(cnt >= 2).sum()}")

    # --- 里程计相对位姿 (由初始位姿推得) ---
    odom_rel = []
    for k in range(K - 1):
        T_rel = np.linalg.inv(poses_mat[k]) @ poses_mat[k + 1]
        odom_rel.append((k, T_rel))

    # --- 运行 BA (Huber 鲁棒核, δ=20 px) ---
    ba = SonarBA(poses6, landmarks, observations, odom_rel,
                 pixel_calib=(A, B, C, D), huber_delta=20.0)
    poses_opt, land_opt, res = ba.optimize(verbose=2)

    # --- 保存结果 ---
    poses_opt_mat = np.array([pose6_to_matrix(p) for p in poses_opt])
    np.save(os.path.join(out_folder, "poses_optimized.npy"), poses_opt_mat)
    np.save(os.path.join(out_folder, "landmarks_optimized.npy"), land_opt)
    save_ply(os.path.join(out_folder, "landmarks_optimized.ply"), land_opt)

    # --- 位移变化统计 ---
    dpos = np.linalg.norm(poses_opt[:, :3] - poses6[:, :3], axis=1)
    dland = np.linalg.norm(land_opt - landmarks, axis=1)
    print(f"位姿平移平均变化: {dpos.mean():.4f} m (最大 {dpos.max():.4f} m)")
    print(f"路标平均移动: {dland.mean():.4f} m (最大 {dland.max():.4f} m)")

    # --- 可视化 ---
    visualize(poses6, landmarks, poses_opt, land_opt,
              save_path=os.path.join(out_folder, "ba_result.png"))
    visualize_topview(poses6, landmarks, poses_opt, land_opt,
                      save_path=os.path.join(out_folder, "ba_topview.png"))


if __name__ == "__main__":
    # 本文件在 大论文思想路线/论文代码/ 下, 输入数据在项目根目录 (上两级), 复用
    # 根目录数据、无需在此复制 .npy/.csv。输出仍写到本文件所在目录, 与项目基线隔离。
    _here = os.path.dirname(os.path.abspath(__file__))
    _data_root = os.path.abspath(os.path.join(_here, "..", ".."))
    main(_data_root, out_folder=_here)
