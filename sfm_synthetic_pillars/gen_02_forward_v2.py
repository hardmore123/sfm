"""
6.1 消融 V3 数据生成（修复版）—— 02_forward_yaw
====================================================

V1 失败原因：
  - 纯 forward (AUV 直线 x 方向，z=1.5，pitch=yaw=0)
  - 柱子 h=1.5m，sonar 高度等于柱顶高度
  - 射线只能在 elev=0° 命中柱顶侧面，shadow.py 触发 `tan(e)<1e-3` 跳过
  - 结果：n_shadow_pixels=0，6.1 完全失效

V2 修复：
  - **保留 "z 完全不可观测"** 的关键属性（z 恒定、无 pitch）
  - **加入 yaw 摆动**（小角度正弦），让 sonar 从不同角度看到柱子
  - 柱子高度改为 2.5m，sonar z=1.5 在柱顶下方，可以看柱侧
  - shadow 可正常生成
  - y 方向小位移辅助（sway_amp 不为 0）

结果：z 完全自由（只能从阴影先验获得），阴影能生成。
"""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "BA代码")))

import numpy as np
from config import Config, SceneCfg, TrajCfg
from world import SceneWorld
from trajectory import euler_to_matrix
from big_paper_sim import generate_big_paper


def make_02_forward_yaw():
    """02_forward_yaw: forward + 小角度 yaw 摆动，z 恒定（z 不可观测）

    关键设计：
      - AUV z=2.6m，高于柱顶 h=1.5m
      - 声呐总能"看到"柱顶，阴影可正常生成
      - z 恒定 + pitch=0，BA 中 lm z 仍完全不可观测
      - yaw 摆动 + y sway，让声呐从多角度看到柱子
      - 2 根柱子沿 AUV 路径分布（x=-3, x=3），让 AUV 有更多帧看到柱子
    """
    cfg = Config()
    cfg.seed = 102
    cfg.scene = SceneCfg(
        scene_type="pillar",
        # 4 根柱子沿 AUV 路径（x=-3, -1, 1, 3）均匀分布，y 偏置 ±0.5 让 AUV sway 时仍能看见
        pillars=[
            (-3.0,  0.5, 0.4, 1.5),
            (-1.0, -0.5, 0.4, 1.5),
            ( 1.0,  0.5, 0.4, 1.5),
            ( 3.0, -0.5, 0.4, 1.5),
        ],
    )
    cfg.traj.motion_mode = "forward"
    cfg.traj.start_xyz = (-5.0, 0.0, 2.6)   # AUV 高于柱顶
    cfg.traj.forward_total_m = 10.0          # 10m 行程（x: -5 → 5）
    cfg.traj.n_frames = 120                  # 120 帧
    cfg.traj.yaw_amplitude_rad = 0.5         # 约 28° 摆动（让声呐从多角度看到柱顶）
    cfg.traj.sway_total_m = 0.0              # 关键：sway=0，z 完全不可观测
    cfg.traj.keyframe_indices = list(range(0, 120, 8))   # 15 关键帧
    # 降低 sonar 分辨率以节省磁盘（h_inv 数组大小 = N*H*W*4 bytes）
    cfg.sonar.range_bin_count = 400          # 默认 800 → 400，省一半
    return cfg


def patch_forward_with_yaw(cfg: Config):
    """
    big_paper_sim 调用 trajectory.make_poses(..., motion_mode=cfg.traj.motion_mode)
    而 'forward' 分支是纯 x 方向、不带 yaw/sway。
    我们需要 monkey-patch trajectory.make_poses 让 'forward' 也带 yaw 摆动。

    实现思路：在 generate_big_paper 调用前，临时替换 trajectory 模块的 make_poses。
    """
    from trajectory import make_poses as _orig_make_poses

    def patched_make_poses(cfg, mode=None, rng=None):
        if mode is None:
            mode = cfg.traj.motion_mode
        if mode != "forward":
            return _orig_make_poses(cfg, mode, rng)
        # forward + yaw + sway
        n = cfg.traj.n_frames
        t = np.linspace(0.0, 1.0, n)
        sx, sy, sz = cfg.traj.start_xyz
        fwd = cfg.traj.forward_total_m
        sway_amp = cfg.traj.sway_total_m
        yaw_amp = cfg.traj.yaw_amplitude_rad
        xs = sx + fwd * t
        ys = sy + sway_amp * np.sin(2 * np.pi * t)
        zs = np.full(n, sz)
        rolls = np.zeros(n)
        pitchs = np.zeros(n)        # 关键：pitch 仍为 0（z 不可观测）
        yaws = yaw_amp * np.sin(2 * np.pi * t)
        poses6 = np.stack([xs, ys, zs, rolls, pitchs, yaws], axis=1)
        poses_T = np.zeros((n, 4, 4))
        for i in range(n):
            R = euler_to_matrix(rolls[i], pitchs[i], yaws[i])
            T = np.eye(4)
            T[:3, :3] = R
            T[:3, 3] = [xs[i], ys[i], zs[i]]
            poses_T[i] = T
        return poses6, poses_T

    # 替换
    import trajectory
    trajectory.make_poses = patched_make_poses
    # 同时 patch big_paper_sim 引用
    import big_paper_sim
    big_paper_sim.make_poses = patched_make_poses
    return cfg


def main():
    out = "./innov2_ablations/02_forward"
    # 不删旧数据，先备份
    backup = "./innov2_ablations/02_forward_v1_noshadow"
    if os.path.exists(out) and not os.path.exists(backup):
        if os.path.exists(backup):
            import shutil; shutil.rmtree(backup)
        import shutil
        shutil.copytree(out, backup)
        print(f"[backup] {out} -> {backup}")

    # 删除并重新生成
    if os.path.exists(out):
        import shutil
        shutil.rmtree(out)
        print(f"[clean] 删除旧 {out}")

    print(f"=== 重新生成 {out} (forward + yaw) ===")
    cfg = make_02_forward_yaw()
    patch_forward_with_yaw(cfg)
    t0 = time.time()
    meta = generate_big_paper(out_dir=out, motion_mode=cfg.traj.motion_mode, cfg=cfg)
    print(f"  耗时 {time.time()-t0:.1f}s")
    print(f"  n_shadow_pixels_total: {meta['stats']['n_shadow_pixels_total']}")
    print(f"  n_inverted_pixels: {meta['innovation2_stats']['n_inverted_pixels']}")
    if meta['innovation2_stats']['median_abs_error_m'] is not None:
        print(f"  z_err_median: {meta['innovation2_stats']['median_abs_error_m']*100:.2f}cm")
    print("OK")


if __name__ == "__main__":
    main()
