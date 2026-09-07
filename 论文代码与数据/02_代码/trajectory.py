"""
AUV 轨迹生成器
================

支持 4 种模式（对应 Huang&Kaess 2015 Table II 的运动学分析）：
  - "general"   : 一般 6-DOF 运动（含 pitch + z 起伏，**良约束**）
  - "forward"   : 纯 x 方向平移（**欠约束**——V4 已量化）
  - "yaw_y"     : 偏航 + y 方向平移（**欠约束**）
  - "mixed"     : 前 1/3 forward → 中 1/3 yaw_y → 后 1/3 general
                  （一份数据同时给 BA 制造压力 + 验证良约束情形）

每帧输出 (x, y, z, roll, pitch, yaw)，共 n_frames 帧。
"""

from __future__ import annotations
from typing import Tuple, List
import numpy as np

from config import Config, C, TrajCfg


def euler_to_matrix(roll: float, pitch: float, yaw: float) -> np.ndarray:
    """R = Rz(yaw)·Ry(pitch)·Rx(roll)，与 ba_optimize.py 完全一致。"""
    cr, sr = np.cos(roll), np.sin(roll)
    cp, sp = np.cos(pitch), np.sin(pitch)
    cy, sy = np.cos(yaw), np.sin(yaw)
    Rx = np.array([[1, 0, 0], [0, cr, -sr], [0, sr, cr]])
    Ry = np.array([[cp, 0, sp], [0, 1, 0], [-sp, 0, cp]])
    Rz = np.array([[cy, -sy, 0], [sy, cy, 0], [0, 0, 1]])
    return Rz @ Ry @ Rx


def matrix_to_pose6(T: np.ndarray) -> np.ndarray:
    """4x4 → (x,y,z,roll,pitch,yaw)。"""
    p = np.zeros(6)
    p[:3] = T[:3, 3]
    R = T[:3, :3]
    sy = np.sqrt(R[2, 1] ** 2 + R[2, 2] ** 2)
    if sy > 1e-9:
        roll = np.arctan2(R[2, 1], R[2, 2])
        pitch = np.arctan2(-R[2, 0], sy)
        yaw = np.arctan2(R[1, 0], R[0, 0])
    else:
        roll = np.arctan2(-R[1, 2], R[1, 1])
        pitch = np.arctan2(-R[2, 0], sy)
        yaw = 0.0
    p[3:] = [roll, pitch, yaw]
    return p


def make_poses(cfg: Config = C) -> Tuple[np.ndarray, np.ndarray]:
    """
    根据 cfg.traj 生成所有帧的 6-DOF 位姿。

    返回：
      poses6 : (n_frames, 6)  欧拉位姿 (x, y, z, roll, pitch, yaw)
      poses_T : (n_frames, 4, 4)  4x4 变换矩阵 T_wb（body→world）
    """
    n = cfg.traj.n_frames
    t = np.linspace(0.0, 1.0, n)
    sx, sy, sz = cfg.traj.start_xyz
    sr, sp, syaw = cfg.traj.start_rpy
    fwd = cfg.traj.forward_total_m
    sway_amp = cfg.traj.sway_total_m
    heave_amp = cfg.traj.heave_amplitude_m
    pitch_amp = cfg.traj.pitch_amplitude_rad
    yaw_amp = cfg.traj.yaw_amplitude_rad

    xs = np.zeros(n); ys = np.zeros(n); zs = np.zeros(n)
    rolls = np.zeros(n); pitchs = np.zeros(n); yaws = np.zeros(n)

    mode = cfg.traj.motion_mode
    if mode == "general":
        # 一般 6-DOF：x 前推 + y/z 摆动 + pitch/yaw 摆动
        xs = sx + fwd * t
        ys = sy + sway_amp * np.sin(2 * np.pi * t)
        zs = sz + heave_amp * np.sin(2 * np.pi * t * 0.5)
        rolls = sr + 0.05 * np.sin(2 * np.pi * t)
        pitchs = sp + pitch_amp * np.sin(2 * np.pi * t * 0.5)
        yaws = syaw + yaw_amp * np.sin(2 * np.pi * t * 0.5)
    elif mode == "forward":
        # 纯 x 平移（欠约束）
        xs = sx + fwd * t
        ys = np.full(n, sy)
        zs = np.full(n, sz)
        rolls = np.full(n, sr); pitchs = np.full(n, sp); yaws = np.full(n, syaw)
    elif mode == "yaw_y":
        # 偏航 + y 平移（欠约束）
        xs = np.full(n, sx + 0.5 * fwd * t)  # 极慢前推
        ys = sy + sway_amp * 2.0 * np.sin(yaw_amp * 2 * np.pi * t)
        zs = np.full(n, sz)
        yaws = syaw + yaw_amp * np.sin(2 * np.pi * t)
        pitchs = np.full(n, sp); rolls = np.full(n, sr)
    elif mode == "mixed":
        # 三段拼接：forward → yaw_y → general
        # 段 1 (0~1/3): 纯 forward
        # 段 2 (1/3~2/3): yaw + y
        # 段 3 (2/3~1): general（z 起伏 + pitch + 略前进）
        i1, i2 = n // 3, 2 * n // 3
        # 第一段
        xs[:i1] = sx + fwd * 0.4 * np.linspace(0, 1, i1)
        ys[:i1] = sy
        zs[:i1] = sz
        rolls[:i1] = sr; pitchs[:i1] = sp; yaws[:i1] = syaw
        # 第二段
        tt2 = np.linspace(0, 1, i2 - i1)
        x1 = xs[i1 - 1]
        y1 = ys[i1 - 1]
        xs[i1:i2] = x1
        ys[i1:i2] = y1 + sway_amp * 2.0 * np.sin(2 * np.pi * tt2)
        zs[i1:i2] = sz
        rolls[i1:i2] = sr
        pitchs[i1:i2] = sp
        yaws[i1:i2] = syaw + yaw_amp * np.sin(2 * np.pi * tt2)
        # 第三段
        tt3 = np.linspace(0, 1, n - i2)
        x2 = xs[i2 - 1]; y2 = ys[i2 - 1]
        xs[i2:] = x2 + fwd * 0.6 * tt3
        ys[i2:] = y2 + sway_amp * 0.5 * np.sin(2 * np.pi * tt3)
        zs[i2:] = sz + heave_amp * np.sin(2 * np.pi * tt3 * 0.5)
        rolls[i2:] = sr + 0.05 * np.sin(2 * np.pi * tt3)
        pitchs[i2:] = sp + pitch_amp * np.sin(2 * np.pi * tt3 * 0.5)
        yaws[i2:] = syaw + yaw_amp * 0.5 * np.sin(2 * np.pi * tt3 * 0.5)
    else:
        raise ValueError(f"Unknown motion_mode: {mode}")

    poses6 = np.stack([xs, ys, zs, rolls, pitchs, yaws], axis=1)   # (n, 6)
    poses_T = np.zeros((n, 4, 4))
    for i in range(n):
        T = np.eye(4)
        T[:3, :3] = euler_to_matrix(rolls[i], pitchs[i], yaws[i])
        T[:3, 3] = poses6[i, :3]
        poses_T[i] = T
    return poses6, poses_T


def select_keyframe_indices(cfg: Config = C) -> List[int]:
    """返回关键帧在全部帧中的下标。"""
    return list(cfg.traj.keyframe_indices)
