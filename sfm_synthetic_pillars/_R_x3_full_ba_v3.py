"""
R-X3 V3：重设计 BA weights 验证 ratio 物理可达性
==================================================

V2 揭示根因：BA 默认 weights (prior:odom:sonar = 1200:1) 让 sonar 信息被先验吃光
V3 重设计 weights 让 sonar 主导：
  - 组 A (默认 bug):    prior=1000, odom=100, sonar=1, lmprior=0
  - 组 B (平衡):        prior=1, odom=1, sonar=1, lmprior=0
  - 组 C (sonar 主导):  prior=1, odom=1, sonar=10, lmprior=0
  - 组 D (强 sonar):    prior=1, odom=1, sonar=100, lmprior=0
  - 组 E (纯 sonar):    prior=0, odom=0, sonar=1, lmprior=0

阶段表 R-X3 验收：
  - s_z / σ̂_Pz ∈ [0.8, 1.3]  物理可达性
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


def load_heave_h12():
    """读 _tmp_heave_baseline/general_h1.2 数据（V2 改：landmarks 用 GT）。"""
    base = Path("_tmp_heave_baseline/general_h1.2")
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
    sigma_Pz_th = out["sigma_Pz"]
    cls = out["classification"]
    well_mask = (cls == 3) | (cls == 2)
    base_frame = np.array([obs_by_lm[j][0][0] if j in obs_by_lm else 0
                            for j in range(M)], dtype=int)
    odom_rel = []
    for k in range(K - 1):
        T_rel = np.linalg.inv(poses_se3[k]) @ poses_se3[k + 1]
        odom_rel.append((k, T_rel))
    return landmarks, poses6, obs_by_lm, obs_list, odom_rel, calib, well_mask, base_frame, sigma_rho, sigma_theta, sigma_Pz_th


def run_ba_once_v3(landmarks, poses6, obs_by_lm, obs_list, odom_rel, calib,
                  well_mask, base_frame, sigma_rho, sigma_theta,
                  weights_dict, add_noise=True, seed=None):
    """跑一次 BA。V3: weights 完全可调。"""
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
        "prior": weights_dict.get("prior", 0.0),
        "odomT": weights_dict.get("odomT", 0.0),
        "odomR": weights_dict.get("odomR", 0.0),
        "sonar": weights_dict.get("sonar", 1.0),
        "lmprior": weights_dict.get("lmprior", 0.0),
        "elevprior": 0.0,
    }
    ba = UnifiedSonarBA(poses6, landmarks, obs_by_lm, obs_list_noisy, odom_rel,
                        calib, well_mask, base_frame,
                        elev_range=(-0.30, 0.30), elev_grid=61,
                        gnc_c_px=5.0, huber_delta=20.0,
                        weights=weights)
    result = ba.optimize(use_gnc=True, max_outer=10, verbose=False)
    return ba, result


def run_monte_carlo_v3(M_mc, weights_dict, landmarks, poses6, obs_by_lm, obs_list,
                      odom_rel, calib, well_mask, base_frame, sigma_rho, sigma_theta):
    z_estimates = np.zeros((M_mc, landmarks.shape[0]))
    failed = 0
    for m in range(M_mc):
        try:
            _, result = run_ba_once_v3(landmarks, poses6, obs_by_lm, obs_list, odom_rel,
                                        calib, well_mask, base_frame, sigma_rho, sigma_theta,
                                        weights_dict=weights_dict, add_noise=True, seed=42 + m)
            z_estimates[m] = result["world"][:, 2]
        except Exception as e:
            failed += 1
            z_estimates[m] = np.nan
    if failed > 0:
        print(f"  [warn] {failed}/{M_mc} 次失败")
    return z_estimates


def evaluate_one_weights(label, weights_dict, M_mc, landmarks, poses6, obs_by_lm, obs_list,
                        odom_rel, calib, well_mask, base_frame, sigma_rho, sigma_theta,
                        sigma_Pz_th):
    """对一组 weights 跑 M_mc 蒙特卡洛。"""
    w_summary = ", ".join(f"{k}={v}" for k, v in weights_dict.items() if v > 0)
    print(f"\n=== {label}（{w_summary}, M={M_mc}）===")
    t0 = time.time()
    z_estimates = run_monte_carlo_v3(M_mc, weights_dict, landmarks, poses6, obs_by_lm, obs_list,
                                       odom_rel, calib, well_mask, base_frame, sigma_rho, sigma_theta)
    dt = time.time() - t0
    print(f"  耗时 {dt:.1f}s ({dt/M_mc:.2f}s/iter)")

    s_z = np.nanstd(z_estimates, axis=0)
    well_lm = np.where(well_mask)[0]
    ratios = []
    s_z_list = []
    sigma_list = []
    mean_z_list = []
    for j in well_lm:
        if np.isfinite(s_z[j]) and sigma_Pz_th[j] > 1e-9:
            r = s_z[j] / sigma_Pz_th[j]
            ratios.append(r)
            s_z_list.append(s_z[j])
            sigma_list.append(sigma_Pz_th[j])
            mean_z_list.append(np.nanmean(z_estimates[:, j]))
    if ratios:
        r_arr = np.array(ratios)
        s_arr = np.array(s_z_list) * 100
        sig_arr = np.array(sigma_list) * 100
        m_arr = np.array(mean_z_list) * 100  # cm
        n_in = int(np.sum((r_arr >= 0.8) & (r_arr <= 1.3)))
        n_close = int(np.sum((r_arr >= 0.5) & (r_arr <= 2.0)))
        print(f"  s_z: median={np.median(s_arr):.4f}cm")
        print(f"  σ_Pz: median={np.median(sig_arr):.4f}cm")
        print(f"  mean_z: median={np.median(m_arr):.4f}cm (BA 后 z 散布)")
        print(f"  ratio: median={np.median(r_arr):.3f}, range=[{r_arr.min():.3f}, {r_arr.max():.3f}]")
        print(f"  ratio ∈ [0.8, 1.3]: {n_in}/{len(ratios)}")
        print(f"  ratio ∈ [0.5, 2.0]: {n_close}/{len(ratios)} (宽松验收)")
    return {
        "label": label,
        "weights": weights_dict,
        "M_mc": M_mc,
        "well_lm_count": len(ratios),
        "s_z_median_cm": float(np.median(s_arr)) if ratios else None,
        "sigma_Pz_median_cm": float(np.median(sig_arr)) if ratios else None,
        "mean_z_median_cm": float(np.median(m_arr)) if ratios else None,
        "ratio_median": float(np.median(r_arr)) if ratios else None,
        "ratio_min": float(r_arr.min()) if ratios else None,
        "ratio_max": float(r_arr.max()) if ratios else None,
        "n_in_range": n_in if ratios else 0,
        "n_close": n_close if ratios else 0,
        "n_total": len(ratios),
    }


def main():
    print("=" * 60)
    print("R-X3 V3：重设计 weights 验证 ratio 物理可达性")
    print("=" * 60)
    print("V2 揭示：默认 weights (1200:1) 让 sonar 信息被先验吃光")
    print("V3 重设计：5 组 weights 对照")
    print()

    # 加载
    print("加载数据...")
    landmarks, poses6, obs_by_lm, obs_list, odom_rel, calib, well_mask, base_frame, sigma_rho, sigma_theta, sigma_Pz_th = load_heave_h12()
    print(f"  landmarks: {landmarks.shape}, well: {int(well_mask.sum())}, obs: {len(obs_list)}")
    print(f"  σ_Pz 解析版: median={np.median(sigma_Pz_th[np.isfinite(sigma_Pz_th)])*100:.4f}cm")

    # 3 组 weights 对照（A 已知锁定，B 关键测试 sonar 主导，C 增强对照）
    weights_sets = [
        ("A_默认bug",   {"prior": 1000.0, "odomT": 100.0, "odomR": 100.0, "sonar": 1.0, "lmprior": 0.0}),
        ("B_平衡",      {"prior": 1.0,    "odomT": 1.0,    "odomR": 1.0,    "sonar": 1.0, "lmprior": 0.0}),
        ("C_sonar10",   {"prior": 1.0,    "odomT": 1.0,    "odomR": 1.0,    "sonar": 10.0, "lmprior": 0.0}),
    ]

    M_mc = 50  # V3 减少 iter 数（原 200），B/C 约 50×20s=17min/组
    summaries = []
    for label, wd in weights_sets:
        s = evaluate_one_weights(label, wd, M_mc, landmarks, poses6, obs_by_lm, obs_list,
                                  odom_rel, calib, well_mask, base_frame, sigma_rho, sigma_theta,
                                  sigma_Pz_th)
        summaries.append(s)

    # 汇总
    print(f"\n{'='*60}")
    print(f"=== 5 组 weights 对比汇总 ===")
    print(f"{'组':<18} {'s_z(cm)':<12} {'σ_Pz(cm)':<12} {'mean_z':<10} {'ratio':<10} {'n_close/total':<14}")
    print(f"{'-'*80}")
    for s in summaries:
        s_z_s = f"{s['s_z_median_cm']:.4f}" if s['s_z_median_cm'] else "N/A"
        sig_s = f"{s['sigma_Pz_median_cm']:.4f}" if s['sigma_Pz_median_cm'] else "N/A"
        mz_s = f"{s['mean_z_median_cm']:.2f}" if s['mean_z_median_cm'] else "N/A"
        ratio_s = f"{s['ratio_median']:.3f}" if s['ratio_median'] is not None else "N/A"
        print(f"  {s['label']:<16} {s_z_s:<12} {sig_s:<12} {mz_s:<10} {ratio_s:<10} {s['n_close']}/{s['n_total']}")

    # 落盘
    out = {
        "M_mc": M_mc,
        "well_lm_count": int(well_mask.sum()),
        "summaries": summaries,
    }
    out_path = Path("R_X3_BA_RESULTS_v3.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False, default=str)
    print(f"\n[ok] 落盘 {out_path}")


if __name__ == "__main__":
    main()
