"""
可视化模拟数据集
==================

生成 4 张图（统一存到 sim_output/figs/）：
  1) sonar_strip.png    - 几帧声呐图横向拼接（带 dB 着色 + 像素轴标注）
  2) scene_3d.png       - 3D 场景：柱子 + 真值/优化轨迹 + 点云
  3) track_density.png  - 每帧 track 数量与 landmark 可见数随时间变化
  4) reproj_err.png     - BA 优化前/后的重投影像素误差直方图
"""

import os, sys, argparse
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def plot_sonar_strip(gt_dir, out_path, frame_ids=(0, 15, 30, 45, 59)):
    images = np.load(os.path.join(gt_dir, "sonar_images.npy"))  # (N, H, W)
    fig, axes = plt.subplots(1, len(frame_ids), figsize=(4 * len(frame_ids), 4))
    for ax, f in zip(axes, frame_ids):
        img = images[f]
        # 强度 → dB（限幅 -60~0）
        img_db = 20 * np.log10(img + 1e-6)
        img_db = np.clip(img_db, -60, 0)
        ax.imshow(img_db, cmap="viridis", aspect="auto", origin="upper")
        ax.set_title(f"frame {f}")
        ax.set_xlabel("beam")
        ax.set_ylabel("range bin")
    fig.suptitle("Simulated Forward-Looking Sonar Images (dB)")
    fig.tight_layout()
    fig.savefig(out_path, dpi=130)
    plt.close(fig)
    print(f"  saved {out_path}")


def plot_scene_3d(gt_dir, ba_dir, out_path):
    from mpl_toolkits.mplot3d import Axes3D  # noqa
    poses_gt = np.load(os.path.join(gt_dir, "poses_gt.npy"))
    poses_K_gt = np.load(os.path.join(gt_dir, "poses_keyframe_gt.npy"))
    landmarks_gt = np.load(os.path.join(gt_dir, "landmarks_gt.npy"))

    fig = plt.figure(figsize=(10, 7))
    ax = fig.add_subplot(111, projection="3d")
    # 真值轨迹
    ax.plot(poses_gt[:, 0, 3], poses_gt[:, 1, 3], poses_gt[:, 2, 3],
            "k-", lw=1, alpha=0.5, label="trajectory GT")
    # 关键帧
    ax.scatter(poses_K_gt[:, 0, 3], poses_K_gt[:, 1, 3], poses_K_gt[:, 2, 3],
               c="red", s=40, marker="^", label="keyframes GT")
    # 点云
    ax.scatter(landmarks_gt[:, 0], landmarks_gt[:, 1], landmarks_gt[:, 2],
               c="blue", s=5, alpha=0.5, label="landmarks GT")
    # 优化结果（如果有）
    if os.path.exists(os.path.join(ba_dir, "landmarks_optimized.npy")):
        land_opt = np.load(os.path.join(ba_dir, "landmarks_optimized.npy"))
        ax.scatter(land_opt[:, 0], land_opt[:, 1], land_opt[:, 2],
                   c="green", s=5, alpha=0.5, label="landmarks OPT")
    if os.path.exists(os.path.join(ba_dir, "poses_optimized.npy")):
        poses_opt = np.load(os.path.join(ba_dir, "poses_optimized.npy"))
        ax.plot(poses_opt[:, 0, 3], poses_opt[:, 1, 3], poses_opt[:, 2, 3],
                "g--", lw=1, alpha=0.7, label="trajectory OPT")
    ax.set_xlabel("X (m)"); ax.set_ylabel("Y (m)"); ax.set_zlabel("Z (m)")
    ax.set_title("Simulated 3D Scene (Pillars + AUV Trajectory)")
    ax.legend(loc="upper right", fontsize=8)
    fig.tight_layout()
    fig.savefig(out_path, dpi=130)
    plt.close(fig)
    print(f"  saved {out_path}")


def plot_track_density(tracks_csv, out_path):
    import csv
    from collections import defaultdict
    n_per_frame = defaultdict(int)
    n_per_track = defaultdict(int)
    with open(tracks_csv, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            n_per_frame[int(row["frame_id"])] += 1
            n_per_track[int(row["track_id"])] += 1
    frames = sorted(n_per_frame.keys())
    counts_f = [n_per_frame[f] for f in frames]
    counts_t = list(n_per_track.values())
    fig, axes = plt.subplots(1, 2, figsize=(12, 4))
    axes[0].bar(frames, counts_f, color="steelblue")
    axes[0].set_xlabel("frame id"); axes[0].set_ylabel("# tracks")
    axes[0].set_title("Tracks per frame")
    axes[0].grid(True, ls=":", alpha=0.5)
    axes[1].hist(counts_t, bins=30, color="darkorange", edgecolor="black")
    axes[1].set_xlabel("# observations per track")
    axes[1].set_ylabel("# tracks")
    axes[1].set_title("Track length distribution")
    axes[1].grid(True, ls=":", alpha=0.5)
    fig.tight_layout()
    fig.savefig(out_path, dpi=130)
    plt.close(fig)
    print(f"  saved {out_path}")


def plot_reproj_err(input_dir, ba_dir, out_path, gt_dir):
    """计算重投影像素误差直方图（BA 前后）。"""
    import importlib
    sys.path.insert(0, os.path.normpath(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "BA代码")))
    import ba_optimize as base

    poses_mat, frame_ids, landmarks, tracks = base.load_data(input_dir)
    K = len(frame_ids); M = landmarks.shape[0]
    poses6 = np.array([base.matrix_to_pose6(poses_mat[i]) for i in range(K)])
    track_to_lm = base.build_track_to_landmark(poses_mat, frame_ids, landmarks, tracks)
    A, B, C, D = base.calibrate_pixels(tracks)
    fid_to_idx = {int(fid): i for i, fid in enumerate(frame_ids)}
    observations = [(fid_to_idx[fid], track_to_lm[tid], th, rh, bm, rg)
                    for (fid, tid, th, rh, bm, rg) in tracks
                    if fid in fid_to_idx and tid in track_to_lm]
    o_beam = np.array([o[4] for o in observations])
    o_range = np.array([o[5] for o in observations])
    o_pose = np.array([o[0] for o in observations])
    o_lm = np.array([o[1] for o in observations])

    def calc(poses6, lms):
        R = np.array([base.euler_to_matrix(p[3], p[4], p[5]) for p in poses6])
        t = poses6[:, :3]
        Pb = np.einsum("nij,nj->ni", np.transpose(R, (0, 2, 1))[o_pose], lms[o_lm] - t[o_pose])
        theta = np.arctan2(Pb[:, 1], Pb[:, 0])
        rho = np.linalg.norm(Pb, axis=1)
        u_pred = A * theta + B
        v_pred = C * rho + D
        return np.sqrt((u_pred - o_beam) ** 2 + (v_pred - o_range) ** 2)

    err0 = calc(poses6, landmarks)
    if os.path.exists(os.path.join(ba_dir, "landmarks_optimized.npy")):
        lms_opt = np.load(os.path.join(ba_dir, "landmarks_optimized.npy"))
        poses_opt_mat = np.load(os.path.join(ba_dir, "poses_optimized.npy"))
        poses6_opt = np.array([base.matrix_to_pose6(poses_opt_mat[i]) for i in range(K)])
        err1 = calc(poses6_opt, lms_opt)
    else:
        err1 = err0
    fig, axes = plt.subplots(1, 2, figsize=(12, 4))
    axes[0].hist(err0, bins=60, color="gray", edgecolor="black", alpha=0.7)
    axes[0].set_xlabel("reprojection error (px)")
    axes[0].set_ylabel("# observations")
    axes[0].set_title(f"Before BA   RMS={np.sqrt(np.mean(err0**2)):.2f}px")
    axes[0].grid(True, ls=":", alpha=0.5)
    axes[1].hist(err1, bins=60, color="green", edgecolor="black", alpha=0.7)
    axes[1].set_xlabel("reprojection error (px)")
    axes[1].set_ylabel("# observations")
    axes[1].set_title(f"After BA    RMS={np.sqrt(np.mean(err1**2)):.2f}px")
    axes[1].grid(True, ls=":", alpha=0.5)
    fig.tight_layout()
    fig.savefig(out_path, dpi=130)
    plt.close(fig)
    print(f"  saved {out_path}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sim_dir", default="./sim_output",
                    help="模拟数据集根目录（含 input/ gt/）")
    ap.add_argument("--ba_dir", default="../BA代码/sim_output",
                    help="BA 输出目录（含 poses_optimized.npy 等）")
    args = ap.parse_args()
    gt_dir = os.path.join(args.sim_dir, "gt")
    input_dir = os.path.join(args.sim_dir, "input")
    fig_dir = os.path.join(args.sim_dir, "figs")
    os.makedirs(fig_dir, exist_ok=True)
    print("[viz] plotting sonar strip ...")
    plot_sonar_strip(gt_dir, os.path.join(fig_dir, "sonar_strip.png"))
    print("[viz] plotting 3D scene ...")
    plot_scene_3d(gt_dir, args.ba_dir, os.path.join(fig_dir, "scene_3d.png"))
    print("[viz] plotting track density ...")
    plot_track_density(os.path.join(input_dir, "tracks.csv"),
                       os.path.join(fig_dir, "track_density.png"))
    print("[viz] plotting reprojection error ...")
    plot_reproj_err(input_dir, args.ba_dir,
                    os.path.join(fig_dir, "reproj_err.png"), gt_dir)
    print(f"\nAll figures saved to {fig_dir}/")


if __name__ == "__main__":
    main()
