"""
为 4 种运动模式各生成声呐图集与 3D 场景对比图。
"""
import os, sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def load_gt(mode_dir):
    images = np.load(os.path.join(mode_dir, "gt", "sonar_images.npy"))
    poses_gt = np.load(os.path.join(mode_dir, "gt", "poses_gt.npy"))
    poses_K = np.load(os.path.join(mode_dir, "gt", "poses_keyframe_gt.npy"))
    landmarks = np.load(os.path.join(mode_dir, "gt", "landmarks_gt.npy"))
    return images, poses_gt, poses_K, landmarks


def sonar_montage(modes_root, out_path, frame_ids=(0, 15, 30, 45, 59)):
    modes = ["general", "forward", "yaw_y", "mixed"]
    fig, axes = plt.subplots(len(modes), len(frame_ids),
                              figsize=(3 * len(frame_ids), 2.5 * len(modes)))
    for i, m in enumerate(modes):
        d = os.path.join(modes_root, m)
        if not os.path.isdir(d):
            continue
        images, *_ = load_gt(d)
        for j, f in enumerate(frame_ids):
            ax = axes[i, j]
            img = images[f]
            img_db = np.clip(20 * np.log10(img + 1e-6), -60, 0)
            ax.imshow(img_db, cmap="viridis", aspect="auto", origin="upper")
            if i == 0:
                ax.set_title(f"frame {f}")
            if j == 0:
                ax.set_ylabel(m, fontsize=12, fontweight="bold")
            ax.set_xticks([]); ax.set_yticks([])
    fig.suptitle("Simulated Sonar Images Across 4 Motion Modes", fontsize=14)
    fig.tight_layout()
    fig.savefig(out_path, dpi=130)
    plt.close(fig)
    print(f"  saved {out_path}")


def scene_3d_montage(modes_root, out_path):
    from mpl_toolkits.mplot3d import Axes3D  # noqa
    modes = ["general", "forward", "yaw_y", "mixed"]
    fig = plt.figure(figsize=(16, 12))
    for i, m in enumerate(modes):
        d = os.path.join(modes_root, m)
        if not os.path.isdir(d):
            continue
        images, poses_gt, poses_K, landmarks = load_gt(d)
        ax = fig.add_subplot(2, 2, i + 1, projection="3d")
        ax.plot(poses_gt[:, 0, 3], poses_gt[:, 1, 3], poses_gt[:, 2, 3],
                "k-", lw=1, alpha=0.5, label="trajectory")
        ax.scatter(poses_K[:, 0, 3], poses_K[:, 1, 3], poses_K[:, 2, 3],
                   c="red", s=30, marker="^", label="keyframes")
        ax.scatter(landmarks[:, 0], landmarks[:, 1], landmarks[:, 2],
                   c="blue", s=5, alpha=0.5, label="landmarks")
        ax.set_title(f"motion mode = {m}")
        ax.set_xlabel("X"); ax.set_ylabel("Y"); ax.set_zlabel("Z")
        ax.legend(loc="upper right", fontsize=8)
    fig.suptitle("3D Scene Across 4 Motion Modes", fontsize=14)
    fig.tight_layout()
    fig.savefig(out_path, dpi=130)
    plt.close(fig)
    print(f"  saved {out_path}")


def main():
    ap = __import__("argparse").ArgumentParser()
    ap.add_argument("--modes_root", default="./multi_mode")
    ap.add_argument("--out_dir", default="./multi_mode/figs")
    args = ap.parse_args()
    os.makedirs(args.out_dir, exist_ok=True)
    print("[montage] sonar montage ...")
    sonar_montage(args.modes_root, os.path.join(args.out_dir, "sonar_montage.png"))
    print("[montage] scene 3D montage ...")
    scene_3d_montage(args.modes_root, os.path.join(args.out_dir, "scene_3d_montage.png"))
    print(f"\n所有图存到: {args.out_dir}")


if __name__ == "__main__":
    main()
