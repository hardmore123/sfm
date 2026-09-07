"""
R-X3 完整版 V2：UnifiedSonarBA + 蒙特卡洛
==========================================

V4 bug 修复：
  1. lmprior=100 + sonar=1.0 权重失衡（100:1），landmark 被先验锁死 → s_z ≈ 1e-15 m
  2. 初值用 landmarks_final.npy（BA 后），再用 lmprior 100 锁回去 = 自循环
  3. M_mc=20 不足（之前报告说 200，实际只跑了 20）

V2 修复：
  1. lmprior=0，让 sonar 主导 BA
  2. 初值用 landmarks_gt.npy（GT），从零开始优化
  3. M_mc=200，标准蒙特卡洛
  4. 对照组 A: lmprior=100（原版 bug）
  5. 对照组 B: lmprior=0（修复版）

阶段表 R-X3 验收：
  🔢 s_z / σ̂_Pz ∈ [0.8, 1.3]
"""
import os
import sys
import json
import time
import numpy as np
from pathlib import Path

sys.path.insert(0, r'F:\sfm\BA代码')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ba_unified import UnifiedSonarBA
from ba_optimize import build_track_to_landmark, calibrate_pixels
from observability import compute_observability_per_landmark


def load_heave_h12_for_ba_v2():
    """
    读 _tmp_heave_baseline/general_h1.2 数据。

    V2 改：
    - landmarks 用 GT（不是 BA 后的 final）
    - 增加 well_mask 计算
    """
    base = Path("_tmp_heave_baseline/general_h1.2")
    # V2: 用 GT landmarks 作 BA 初值
    landmarks = np.load(base / "gt/landmarks_gt.npy")
    poses_se3 = np.load(base / "input/poses_est.npy")
    K = poses_se3.shape[0]
    from scipy.spatial.transform import Rotation
    poses6 = np.zeros((K, 6))
    for k in range(K):
        poses6[k, :3] = poses_se3[k, :3, 3]
        poses6[k, 3:] = Rotation.from_matrix(poses_se3[k, :3, :3]).as_euler('xyz', degrees=False)
    pose_frame_ids = np.load(base / "input/pose_frame_ids.npy")
    import csv
    tracks = []
    with open(base / "input/tracks.csv", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            tracks.append((int(row["frame_id"]),
                           int(row["track_id"]),
                           float(row["theta_rad"]),
                           float(row["rho_m"]),
                           float(row["beam_index"]),
                           float(row["range_index"])))
    A, B, C, D = calibrate_pixels(tracks)
    calib = (A, B, C, D)
    track_to_lm = build_track_to_landmark(poses_se3, pose_frame_ids, landmarks, tracks)
    import yaml
    with open(base / "input/sensor_calib.yaml", encoding="utf-8") as f:
        calib_dict = yaml.safe_load(f)
    sigma_rho = float(calib_dict.get("sigma_rho", 0.005))
    sigma_theta = float(calib_dict.get("sigma_theta", 0.0035))
    fid_to_pid = {int(fid): pid for pid, fid in enumerate(pose_frame_ids)}
    obs_by_lm = {}
    obs_list = []
    for (fid, tid, theta, rho, beam, rng) in tracks:
        if fid not in fid_to_pid:
            continue
        if tid not in track_to_lm:
            continue
        lm_idx = track_to_lm[tid]
        pose_idx = fid_to_pid[fid]
        obs_by_lm.setdefault(lm_idx, []).append((pose_idx, theta, rho))
        obs_list.append((pose_idx, lm_idx, theta, rho, beam, rng))
    M = landmarks.shape[0]
    obs_by_lm = {k: v for k, v in obs_by_lm.items() if k < M}
    obs_list = [o for o in obs_list if o[1] < M]
    out = compute_observability_per_landmark(
        landmarks, obs_by_lm, calib, poses6, tau_z=0.05,
        sigma_rho=sigma_rho, sigma_theta=sigma_theta,
    )
    cls = out["classification"]
    well_mask = (cls == 3) | (cls == 2)
    base_frame = np.array([obs_by_lm[j][0][0] if j in obs_by_lm else 0
                            for j in range(M)], dtype=int)
    odom_rel = []
    for k in range(K - 1):
        T_rel = np.linalg.inv(poses_se3[k]) @ poses_se3[k + 1]
        odom_rel.append((k, T_rel))
    return landmarks, poses6, obs_by_lm, obs_list, odom_rel, calib, well_mask, base_frame, sigma_rho, sigma_theta


def run_ba_once_v2(landmarks, poses6, obs_by_lm, obs_list, odom_rel, calib,
                  well_mask, base_frame, sigma_rho, sigma_theta,
                  lmprior=0.0, add_noise=True, seed=None):
    """跑一次 BA。V2: lmprior 可调。"""
    if add_noise and seed is not None:
        rng = np.random.default_rng(seed)
        obs_list_noisy = []
        for o in obs_list:
            pi, lm, theta, rho, beam, rng_idx = o
            theta_n = theta + rng.normal(0, sigma_theta)
            rho_n = rho + rng.normal(0, sigma_rho)
            obs_list_noisy.append((pi, lm, theta_n, rho_n, beam, rng_idx))
    else:
        obs_list_noisy = list(obs_list)
    weights = {
        "prior": 1000.0,    # 首帧先验（强制首帧不动）
        "odomT": 100.0,    # 里程计平移
        "odomR": 100.0,    # 里程计旋转
        "sonar": 1.0,      # 声呐观测
        "lmprior": lmprior,  # V2 关键：可调（0=无，100=原版）
        "elevprior": 0.0,
    }
    ba = UnifiedSonarBA(poses6, landmarks, obs_by_lm, obs_list_noisy, odom_rel,
                        calib, well_mask, base_frame,
                        elev_range=(-0.30, 0.30), elev_grid=61,
                        gnc_c_px=5.0, huber_delta=20.0,
                        weights=weights)
    result = ba.optimize(use_gnc=True, max_outer=10, verbose=False)
    return ba, result


def run_monte_carlo(M_mc, lmprior, landmarks, poses6, obs_by_lm, obs_list,
                    odom_rel, calib, well_mask, base_frame, sigma_rho, sigma_theta):
    """
    M_mc 次蒙特卡洛 BA，返回 z_estimates (M_mc, M_lm)
    """
    z_estimates = np.zeros((M_mc, landmarks.shape[0]))
    failed = 0
    for m in range(M_mc):
        try:
            _, result = run_ba_once_v2(landmarks, poses6, obs_by_lm, obs_list, odom_rel,
                                        calib, well_mask, base_frame, sigma_rho, sigma_theta,
                                        lmprior=lmprior, add_noise=True, seed=42 + m)
            z_estimates[m] = result["world"][:, 2]
        except Exception as e:
            failed += 1
            z_estimates[m] = np.nan
    if failed > 0:
        print(f"  [warn] {failed}/{M_mc} 次失败")
    return z_estimates


def evaluate_one_setup(label, lmprior, M_mc, landmarks, poses6, obs_by_lm, obs_list,
                      odom_rel, calib, well_mask, base_frame, sigma_rho, sigma_theta,
                      sigma_Pz_th):
    """
    对一组 (lmprior) 跑 M_mc 蒙特卡洛，输出 ratio 统计。
    """
    print(f"\n=== {label}（lmprior={lmprior}, M={M_mc}）===")
    t0 = time.time()
    z_estimates = run_monte_carlo(M_mc, lmprior, landmarks, poses6, obs_by_lm, obs_list,
                                    odom_rel, calib, well_mask, base_frame, sigma_rho, sigma_theta)
    dt = time.time() - t0
    print(f"  耗时 {dt:.1f}s ({dt/M_mc:.2f}s/iter)")

    s_z = np.nanstd(z_estimates, axis=0)
    mean_z = np.nanmean(z_estimates, axis=0)

    # 比 s_z / σ_Pz（well/weak landmarks）
    well_lm = np.where(well_mask)[0]
    ratios = []
    s_z_list = []
    sigma_list = []
    for j in well_lm:
        if np.isfinite(s_z[j]) and sigma_Pz_th[j] > 1e-9:
            r = s_z[j] / sigma_Pz_th[j]
            ratios.append(r)
            s_z_list.append(s_z[j])
            sigma_list.append(sigma_Pz_th[j])
    if ratios:
        r_arr = np.array(ratios)
        s_arr = np.array(s_z_list) * 100  # cm
        sig_arr = np.array(sigma_list) * 100  # cm
        n_in = int(np.sum((r_arr >= 0.8) & (r_arr <= 1.3)))
        print(f"  well/weak: {len(ratios)} 个")
        print(f"  s_z: median={np.median(s_arr):.2f}cm, range=[{s_arr.min():.2f}, {s_arr.max():.2f}]cm")
        print(f"  σ_Pz: median={np.median(sig_arr):.2f}cm, range=[{sig_arr.min():.2f}, {sig_arr.max():.2f}]cm")
        print(f"  ratio: median={np.median(r_arr):.3f}, range=[{r_arr.min():.3f}, {r_arr.max():.3f}]")
        print(f"  ratio ∈ [0.8, 1.3]: {n_in}/{len(ratios)}")
    return {
        "label": label,
        "lmprior": lmprior,
        "M_mc": M_mc,
        "well_lm_count": len(ratios),
        "s_z_median_cm": float(np.median(s_arr)) if ratios else None,
        "sigma_Pz_median_cm": float(np.median(sig_arr)) if ratios else None,
        "ratio_median": float(np.median(r_arr)) if ratios else None,
        "ratio_min": float(r_arr.min()) if ratios else None,
        "ratio_max": float(r_arr.max()) if ratios else None,
        "n_in_range": n_in if ratios else 0,
        "n_total": len(ratios),
    }


def main():
    print("=" * 60)
    print("R-X3 V2：lmprior 修复 + M=200 + 对照组")
    print("=" * 60)
    print("数据: _tmp_heave_baseline/general_h1.2")
    print("关键修复:")
    print("  - lmprior 可调（0=让 sonar 主导，100=原版 bug 复现）")
    print("  - landmarks 用 GT 作初值（不是 BA 后 final）")
    print("  - M=200 蒙特卡洛")
    print()

    # 加载
    print("加载数据...")
    landmarks, poses6, obs_by_lm, obs_list, odom_rel, calib, well_mask, base_frame, sigma_rho, sigma_theta = load_heave_h12_for_ba_v2()
    print(f"  landmarks: {landmarks.shape}, poses: {poses6.shape}")
    print(f"  obs_list: {len(obs_list)}, well_mask: well={int(well_mask.sum())}/{landmarks.shape[0]}")

    # σ_Pz 解析版
    out = compute_observability_per_landmark(
        landmarks, obs_by_lm, calib, poses6, tau_z=0.05,
        sigma_rho=sigma_rho, sigma_theta=sigma_theta,
    )
    sigma_Pz_th = out["sigma_Pz"]
    cls = out["classification"]
    print(f"  四分类: well={int((cls==3).sum())}, weak={int((cls==2).sum())}, "
          f"blind={int((cls==1).sum())}, insufficient={int((cls==0).sum())}")
    print(f"  σ_Pz (解析): median={np.median(sigma_Pz_th[np.isfinite(sigma_Pz_th)])*100:.2f}cm")

    # 三组对比
    M_mc = 200
    summaries = []

    # 组 A：lmprior=100（原版 bug）
    sA = evaluate_one_setup(
        "A_原版_bug", 100.0, M_mc, landmarks, poses6, obs_by_lm, obs_list,
        odom_rel, calib, well_mask, base_frame, sigma_rho, sigma_theta, sigma_Pz_th
    )
    summaries.append(sA)

    # 组 B：lmprior=0（修复版）
    sB = evaluate_one_setup(
        "B_修复版", 0.0, M_mc, landmarks, poses6, obs_by_lm, obs_list,
        odom_rel, calib, well_mask, base_frame, sigma_rho, sigma_theta, sigma_Pz_th
    )
    summaries.append(sB)

    # 组 C：lmprior=0.01（极弱先验，对照）
    sC = evaluate_one_setup(
        "C_极弱先验", 0.01, M_mc, landmarks, poses6, obs_by_lm, obs_list,
        odom_rel, calib, well_mask, base_frame, sigma_rho, sigma_theta, sigma_Pz_th
    )
    summaries.append(sC)

    # 汇总
    print(f"\n{'='*60}")
    print(f"=== 三组对比汇总 ===")
    print(f"{'组':<20} {'lmprior':<10} {'s_z (cm)':<12} {'σ_Pz (cm)':<12} {'ratio':<10} {'n_in/total':<12}")
    print(f"{'-'*76}")
    for s in summaries:
        s_z_s = f"{s['s_z_median_cm']:.2f}" if s['s_z_median_cm'] else "N/A"
        sig_s = f"{s['sigma_Pz_median_cm']:.2f}" if s['sigma_Pz_median_cm'] else "N/A"
        ratio_s = f"{s['ratio_median']:.3f}" if s['ratio_median'] is not None else "N/A"
        print(f"  {s['label']:<18} {s['lmprior']:<10.2f} {s_z_s:<12} {sig_s:<12} "
              f"{ratio_s:<10} {s['n_in_range']}/{s['n_total']}")

    # 落盘
    out = {
        "M_mc": M_mc,
        "well_lm_count": int(well_mask.sum()),
        "summaries": summaries,
    }
    out_path = Path("R_X3_BA_RESULTS_v2.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False, default=str)
    print(f"\n[ok] 落盘 {out_path}")


if __name__ == "__main__":
    main()
