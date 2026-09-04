"""
大论文 6.1 主打实验：仰角来源消融
==================================

A. 只多视几何（无阴影高度先验）
B. 多视几何 + 阴影高度先验

对同一份数据跑两次 V6 优化：
  第一次：elev_prior 全 NaN/inf（不注入）
  第二次：elev_prior = 创新二·模块2 反演结果

期望：B 的路标 Z 误差显著小于 A（因为阴影先验补了不可观测的仰角维）。

注意：当前 V6 接口只接受 (M,) 形状的 per-landmark 先验，
我们需要把像素级反演聚合成 landmark 级。
"""

import os, sys, time, json
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "BA代码")))

import ba_optimize as base
import ba_improve as imp
import ba_unified as unif


def load_data(input_dir):
    poses_mat, frame_ids, landmarks, tracks = base.load_data(input_dir)
    K, M = len(frame_ids), landmarks.shape[0]
    poses6 = np.array([base.matrix_to_pose6(poses_mat[i]) for i in range(K)])
    track_to_lm = base.build_track_to_landmark(poses_mat, frame_ids, landmarks, tracks)
    A, B, C, D = base.calibrate_pixels(tracks)
    calib = (A, B, C, D)
    fid_to_idx = {int(fid): i for i, fid in enumerate(frame_ids)}
    observations = [(fid_to_idx[fid], track_to_lm[tid], th, rh, bm, rg)
                    for (fid, tid, th, rh, bm, rg) in tracks
                    if fid in fid_to_idx and tid in track_to_lm]
    odom_rel = [(k, np.linalg.inv(poses_mat[k]) @ poses_mat[k + 1]) for k in range(K - 1)]
    return poses_mat, frame_ids, landmarks, tracks, poses6, calib, observations, odom_rel, K, M


def evaluate(poses_opt, land_opt, gt_dir):
    gt_poses_K = np.load(os.path.join(gt_dir, "poses_keyframe_gt.npy"))
    gt_lm = np.load(os.path.join(gt_dir, "landmarks_gt.npy"))
    err_pos = np.linalg.norm(poses_opt[:, :3] - gt_poses_K[:, :3, 3], axis=1)
    err_lm = np.linalg.norm(land_opt - gt_lm, axis=1)
    err_lm_z = np.abs(land_opt[:, 2] - gt_lm[:, 2])
    return {
        "pose_err_mean_cm": float(err_pos.mean() * 100),
        "lm_err_mean_cm":   float(err_lm.mean() * 100),
        "lm_z_err_mean_cm": float(err_lm_z.mean() * 100),
    }


def aggregate_height_inversion_to_landmarks(
    h_inv: np.ndarray,           # (N, H, W)
    sigma_h: np.ndarray,         # (N, H, W)
    valid: np.ndarray,           # (N, H, W) bool
    observations: list,          # list of (pose_idx, lm_idx, theta, rho, beam, range)
    N: int, H: int, W: int, M: int,
):
    """
    把像素级高度反演结果聚合到每个 landmark 上：
      对每个 landmark，收集其所有观测 (frame, beam, range) 处的反演值
      求中位 → lm 级高度先验
    """
    pm = {  # 默认 pixel mapping（与 cfg 一致）
        "beam_a": 512 / np.deg2rad(130.0),  # beam_count / 2π
        "beam_b": 256,
        "range_c": 800 / 3.8,  # range_bin_count / (max-min)
        "range_d": -800 * 0.2 / 3.8,
    }
    elev_prior = np.full(M, np.nan)
    sigma_prior = np.full(M, np.inf)
    # 收集每个 lm 在所有帧的所有观测
    lm_obs_heights = {j: [] for j in range(M)}
    lm_obs_sigmas = {j: [] for j in range(M)}
    for o in observations:
        pi, j, th, rh, bm, rg = o
        ri = int(np.clip(round(rg), 0, H - 1))
        bi = int(np.clip(round(bm), 0, W - 1))
        if valid[pi, ri, bi] and np.isfinite(h_inv[pi, ri, bi]):
            lm_obs_heights[j].append(h_inv[pi, ri, bi])
            lm_obs_sigmas[j].append(sigma_h[pi, ri, bi])
    for j in range(M):
        if len(lm_obs_heights[j]) > 0:
            elev_prior[j] = float(np.median(lm_obs_heights[j]))
            sigma_prior[j] = float(np.median(lm_obs_sigmas[j]))
    n_prior = int(np.sum(np.isfinite(elev_prior)))
    return elev_prior, sigma_prior, n_prior


def run_a_vs_b(input_dir, gt_dir, mode_name: str = "mixed"):
    print(f"\n{'='*70}\n6.1 仰角来源消融实验 (mode={mode_name})\n{'='*70}")
    inv2_dir = os.path.join("big_paper_sim", mode_name, "innovation2")
    h_inv = np.load(os.path.join(inv2_dir, "height_inverted.npy"))
    sigma_h = np.load(os.path.join(inv2_dir, "sigma_height.npy"))
    valid = np.load(os.path.join(inv2_dir, "height_inverted.npy"))   # 用 !isfinite(h_inv) 反算
    valid = np.isfinite(h_inv) & (h_inv > 0) & (h_inv < 5.0)   # 合理性裁剪

    poses_mat, frame_ids, landmarks, tracks, poses6, calib, observations, odom_rel, K, M = load_data(input_dir)
    obs_by_lm = imp.build_obs_by_lm(observations)
    base_frame = imp.first_base_frame(observations, M)
    well_mask, _ = imp.classify_landmarks(poses6, landmarks, obs_by_lm, calib)

    # 聚合成 landmark 级先验
    N, H, W = h_inv.shape
    elev_prior, sigma_prior, n_prior = aggregate_height_inversion_to_landmarks(
        h_inv, sigma_h, valid, observations, N, H, W, M)
    print(f"  创新二·模块2 反演像素: {int(valid.sum()):,}")
    print(f"  聚合到 landmark 级先验: {n_prior}/{M} 个 landmark 有先验")
    if n_prior > 0:
        prior_z = elev_prior[np.isfinite(elev_prior)]
        sigma_z = sigma_prior[np.isfinite(sigma_prior)]
        print(f"  高度先验: mean={np.mean(prior_z):.2f}m, median={np.median(prior_z):.2f}m")
        print(f"  不确定度: median={np.median(sigma_z):.3f}m")

    # ---- A: 只多视几何（无先验）----
    print("\n--- A. 只多视几何（V6 无先验） ---")
    ba_a = unif.UnifiedSonarBA(poses6, landmarks, obs_by_lm, observations, odom_rel, calib,
                                well_mask, base_frame, elev_range=(-0.30, 0.30),
                                gnc_c_px=5.0, huber_delta=20.0)
    t0 = time.time()
    out_a = ba_a.optimize(use_gnc=True, verbose=False)
    t_a = time.time() - t0
    res_a = evaluate(out_a["poses"], out_a["world"], gt_dir)
    res_a["time_s"] = t_a
    print(f"  A: t={t_a:.1f}s, pos_err={res_a['pose_err_mean_cm']:.2f}cm, "
          f"lm_err={res_a['lm_err_mean_cm']:.2f}cm, lm_z_err={res_a['lm_z_err_mean_cm']:.2f}cm")

    # ---- B: 多视 + 阴影高度先验 ----
    print("\n--- B. 多视几何 + 阴影高度先验（创新二·模块2 注入） ---")
    ba_b = unif.UnifiedSonarBA(poses6, landmarks, obs_by_lm, observations, odom_rel, calib,
                                well_mask, base_frame, elev_range=(-0.30, 0.30),
                                gnc_c_px=5.0, huber_delta=20.0,
                                elev_prior=elev_prior, elev_prior_sigma=sigma_prior)
    t0 = time.time()
    out_b = ba_b.optimize(use_gnc=True, verbose=False)
    t_b = time.time() - t0
    res_b = evaluate(out_b["poses"], out_b["world"], gt_dir)
    res_b["time_s"] = t_b
    print(f"  B: t={t_b:.1f}s, pos_err={res_b['pose_err_mean_cm']:.2f}cm, "
          f"lm_err={res_b['lm_err_mean_cm']:.2f}cm, lm_z_err={res_b['lm_z_err_mean_cm']:.2f}cm")

    # ---- 对比 ----
    print("\n=== A vs B 仰角来源消融 ===")
    print(f"{'配置':<30} | {'pos err (cm)':<12} | {'lm err (cm)':<12} | {'lm z err (cm)':<12}")
    print("-" * 70)
    print(f"{'A 只多视几何':<30} | {res_a['pose_err_mean_cm']:<12.2f} | "
          f"{res_a['lm_err_mean_cm']:<12.2f} | {res_a['lm_z_err_mean_cm']:<12.2f}")
    print(f"{'B 多视+阴影高度先验':<30} | {res_b['pose_err_mean_cm']:<12.2f} | "
          f"{res_b['lm_err_mean_cm']:<12.2f} | {res_b['lm_z_err_mean_cm']:<12.2f}")
    delta_lm = res_a['lm_err_mean_cm'] - res_b['lm_err_mean_cm']
    delta_z = res_a['lm_z_err_mean_cm'] - res_b['lm_z_err_mean_cm']
    print(f"\n  改进: lm_err 减少 {delta_lm:.2f}cm ({delta_lm/res_a['lm_err_mean_cm']*100:.1f}%)")
    print(f"  改进: lm_z_err 减少 {delta_z:.2f}cm ({delta_z/res_a['lm_z_err_mean_cm']*100:.1f}%)")
    return res_a, res_b


if __name__ == "__main__":
    res_a, res_b = run_a_vs_b(
        input_dir="../BA代码/sim_input_big",
        gt_dir="./big_paper_sim/mixed/gt",
        mode_name="mixed")
    with open("./innov2_a_vs_b_result.json", "w") as f:
        json.dump({"A_多视几何": res_a, "B_多视+阴影高度先验": res_b}, f, indent=2, ensure_ascii=False)
