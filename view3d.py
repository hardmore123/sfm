# -*- coding: utf-8 -*-
"""
交互式三维查看器 (matplotlib) —— 声呐 BA 结果
================================================
用鼠标即可旋转 / 平移 / 缩放查看优化后的点云与关键帧轨迹。

操作:
    - 左键拖动     : 旋转视角
    - 右键拖动     : 缩放 (部分后端为滚轮缩放)
    - 中键拖动     : 平移
    - 键盘 o       : 叠加/隐藏 优化前(初始)点云做对比
    - 键盘 f       : 显示/隐藏 每个关键帧的局部坐标轴
    - 键盘 r       : 复位视角

用法:
    python view3d.py                # 显示优化后结果 (默认)
    python view3d.py --both         # 同时叠加优化前(灰) vs 优化后(蓝)
"""

import os
import sys
import numpy as np

# --- 选择一个可交互的后端 (窗口可用鼠标旋转) ---
import matplotlib
for backend in ("TkAgg", "Qt5Agg", "QtAgg", "MacOSX"):
    try:
        matplotlib.use(backend, force=True)
        break
    except Exception:
        continue
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401


def euler_to_matrix(roll, pitch, yaw):
    cr, sr = np.cos(roll), np.sin(roll)
    cp, sp = np.cos(pitch), np.sin(pitch)
    cy, sy = np.cos(yaw), np.sin(yaw)
    Rx = np.array([[1, 0, 0], [0, cr, -sr], [0, sr, cr]])
    Ry = np.array([[cp, 0, sp], [0, 1, 0], [-sp, 0, cp]])
    Rz = np.array([[cy, -sy, 0], [sy, cy, 0], [0, 0, 1]])
    return Rz @ Ry @ Rx


def load(folder):
    """加载优化结果; 若不存在则回退到初始结果。"""
    def pick(a, b):
        return a if os.path.exists(os.path.join(folder, a)) else b

    poses_opt = np.load(os.path.join(folder, pick("poses_optimized.npy", "poses_est.npy")))
    land_opt = np.load(os.path.join(folder, pick("landmarks_optimized.npy", "landmarks_final.npy")))
    poses_init = np.load(os.path.join(folder, "poses_est.npy"))
    land_init = np.load(os.path.join(folder, "landmarks_final.npy"))
    return poses_init, land_init, poses_opt, land_opt


def set_equal_aspect(ax, pts):
    x, y, z = pts[:, 0], pts[:, 1], pts[:, 2]
    r = max(x.max() - x.min(), y.max() - y.min(), z.max() - z.min()) / 2.0
    r = max(r, 1e-3)
    mx, my, mz = (x.max() + x.min()) / 2, (y.max() + y.min()) / 2, (z.max() + z.min()) / 2
    ax.set_xlim(mx - r, mx + r)
    ax.set_ylim(my - r, my + r)
    ax.set_zlim(mz - r, mz + r)


def draw_frames(ax, poses, length=0.12):
    handles = []
    for p in poses:
        R = euler_from_matrix_or_pose(p)
        pos = p[:3, 3] if p.ndim == 2 else p[:3]
        for col, k in (("r", 0), ("g", 1), ("b", 2)):
            q = ax.quiver(pos[0], pos[1], pos[2], R[0, k], R[1, k], R[2, k],
                          length=length, color=col, linewidth=1.0)
            handles.append(q)
    return handles


def euler_from_matrix_or_pose(p):
    """p 可以是 4x4 位姿矩阵, 直接返回其旋转部分。"""
    if p.ndim == 2 and p.shape == (4, 4):
        return p[:3, :3]
    return euler_to_matrix(p[3], p[4], p[5])


def poses_positions(poses):
    if poses.ndim == 3:      # (K,4,4)
        return poses[:, :3, 3]
    return poses[:, :3]      # (K,6)


def main():
    folder = os.path.dirname(os.path.abspath(__file__)) or "."
    show_both = "--both" in sys.argv

    poses_init, land_init, poses_opt, land_opt = load(folder)
    pos_opt = poses_positions(poses_opt)
    pos_init = poses_positions(poses_init)

    fig = plt.figure(figsize=(11, 9))
    ax = fig.add_subplot(111, projection="3d")

    state = {"show_init": show_both, "show_frames": True, "frame_handles": []}

    def redraw():
        ax.cla()
        # 优化后 (蓝)
        ax.scatter(land_opt[:, 0], land_opt[:, 1], land_opt[:, 2],
                   c="royalblue", s=10, alpha=0.8, label="Landmarks (optimized)")
        ax.plot(pos_opt[:, 0], pos_opt[:, 1], pos_opt[:, 2],
                "-o", color="crimson", ms=4, lw=1.5, label="Trajectory (optimized)")
        # 优化前 (灰) 叠加
        if state["show_init"]:
            ax.scatter(land_init[:, 0], land_init[:, 1], land_init[:, 2],
                       c="gray", s=8, alpha=0.35, label="Landmarks (initial)")
            ax.plot(pos_init[:, 0], pos_init[:, 1], pos_init[:, 2],
                    "--", color="dimgray", lw=1.0, alpha=0.6, label="Trajectory (initial)")
        # 关键帧坐标轴
        if state["show_frames"]:
            draw_frames(ax, poses_opt)
        # 世界坐标原点
        for col, k, name in (("r", 0, "X"), ("g", 1, "Y"), ("b", 2, "Z")):
            v = np.eye(3)[:, k]
            ax.quiver(0, 0, 0, v[0], v[1], v[2], length=0.4, color=col, linewidth=2.0)

        allpts = np.vstack([land_opt, pos_opt, land_init, pos_init])
        set_equal_aspect(ax, allpts)
        ax.set_xlabel("X (m)"); ax.set_ylabel("Y (m)"); ax.set_zlabel("Z (m)")
        ax.set_title("Sonar BA - Interactive 3D  (drag=rotate, keys: o/f/r)")
        ax.legend(loc="upper right", fontsize=8)
        fig.canvas.draw_idle()

    def on_key(event):
        if event.key == "o":
            state["show_init"] = not state["show_init"]; redraw()
        elif event.key == "f":
            state["show_frames"] = not state["show_frames"]; redraw()
        elif event.key == "r":
            ax.view_init(elev=25, azim=-60); fig.canvas.draw_idle()

    fig.canvas.mpl_connect("key_press_event", on_key)
    ax.view_init(elev=25, azim=-60)
    redraw()
    print("交互式窗口已打开: 左键旋转, 滚轮/右键缩放, 中键平移; 按 o 叠加初始点云, f 切换坐标轴, r 复位。")
    plt.show()


if __name__ == "__main__":
    main()
