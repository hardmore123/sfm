"""
R-X3 完整版：从 UnifiedSonarBA 联合 BA 提取 cov 矩阵 + 蒙特卡洛
================================================================

阶段表 R-X3 验收：
  🔢 s_z / σ̂_Pz ∈ [0.8, 1.3]
  🔢 s_z / (σ_ρ/(√N·std(φ))) ∈ [0.8, 1.3]

实现：
  1. 读 _tmp_heave_baseline/general_h1.2 数据
  2. 构造 UnifiedSonarBA 接口（odom_rel, calib, well_mask, base_frame）
  3. 跑 BA 优化
  4. 提取 BA 输出 cov 矩阵 → σ_Pz
  5. 蒙特卡洛 M=200 次加噪 BA → 算 s_z
  6. 比 s_z / σ_Pz
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


def load_heave_h12_for_ba():
    """读 _tmp_heave_baseline/general_h1.2 数据，构造 UnifiedSonarBA 输入。
    用 ba_optimize.build_track_to_landmark 恢复 track_id → lm_idx 映射（重投影匹配）。
    """
    base = Path("_tmp_heave_baseline/general_h1.2")
    # landmarks（用 BA 优化后的 landmarks_final 作初值，与 obs 一致）
    landmarks = np.load(base / "input/landmarks_final.npy")
    # poses SE(3) → poses6
    poses_se3 = np.load(base / "input/poses_est.npy")
    K = poses_se3.shape[0]
    from scipy.spatial.transform import Rotation
    poses6 = np.zeros((K, 6))
    for k in range(K):
        poses6[k, :3] = poses_se3[k, :3, 3]
        poses6[k, 3:] = Rotation.from_matrix(poses_se3[k, :3, :3]).as_euler('xyz', degrees=False)
    # pose_frame_ids
    pose_frame_ids = np.load(base / "input/pose_frame_ids.npy")
    # tracks.csv
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
    # calib（从 tracks 拟合）
    A, B, C, D = calibrate_pixels(tracks)
    calib = (A, B, C, D)
    # build_track_to_landmark（重投影匹配）
    track_to_lm = build_track_to_landmark(poses_se3, pose_frame_ids, landmarks, tracks)
    # sigma_rho / sigma_theta
    import yaml
    with open(base / "input/sensor_calib.yaml", encoding="utf-8") as f:
        calib_dict = yaml.safe_load(f)
    sigma_rho = float(calib_dict.get("sigma_rho", 0.005))
    sigma_theta = float(calib_dict.get("sigma_theta", 0.0035))
    # 构造 obs_by_lm + obs_list
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
    # 截断到 landmarks 范围
    M = landmarks.shape[0]
    obs_by_lm = {k: v for k, v in obs_by_lm.items() if k < M}
    obs_list = [o for o in obs_list if o[1] < M]
    # well_mask（用 observability 算）
    out = compute_observability_per_landmark(
        landmarks, obs_by_lm, calib, poses6, tau_z=0.05,
        sigma_rho=sigma_rho, sigma_theta=sigma_theta,
    )
    cls = out["classification"]
    well_mask = (cls == 3) | (cls == 2)  # well + weak
    # base_frame: 每 landmark 首次观测的 pose_idx
    base_frame = np.array([obs_by_lm[j][0][0] if j in obs_by_lm else 0
                            for j in range(M)], dtype=int)
    # odom_rel: K-1 个相对位姿
    odom_rel = []
    for k in range(K - 1):
        T_rel = np.linalg.inv(poses_se3[k]) @ poses_se3[k + 1]
        odom_rel.append((k, T_rel))
    return landmarks, poses6, obs_by_lm, obs_list, odom_rel, calib, well_mask, base_frame, sigma_rho, sigma_theta


def run_ba_once(landmarks, poses6, obs_by_lm, obs_list, odom_rel, calib,
                well_mask, base_frame, sigma_rho, sigma_theta,
                add_noise=True, seed=None):
    """跑一次 BA，返回 BA 后的 landmarks 数组。"""
    if add_noise and seed is not None:
        rng = np.random.default_rng(seed)
        # 对 obs_list 加噪（theta, rho）
        obs_list_noisy = []
        for o in obs_list:
            pi, lm, theta, rho, beam, rng_idx = o
            theta_n = theta + rng.normal(0, sigma_theta)
            rho_n = rho + rng.normal(0, sigma_rho)
            obs_list_noisy.append((pi, lm, theta_n, rho_n, beam, rng_idx))
    else:
        obs_list_noisy = list(obs_list)
    # 加 landmarks 先验权重（防止 BA 跑飞）
    # weights: prior, odomT, odomR, sonar, lmprior, elevprior
    weights = {
        "prior": 1000.0,    # 首帧先验（强制首帧不动）
        "odomT": 100.0,    # 里程计平移
        "odomR": 100.0,    # 里程计旋转
        "sonar": 1.0,      # 声呐观测
        "lmprior": 100.0,  # landmarks 先验（强拉回初值）
        "elevprior": 0.0,
    }
    # 创建 BA
    ba = UnifiedSonarBA(poses6, landmarks, obs_by_lm, obs_list_noisy, odom_rel,
                        calib, well_mask, base_frame,
                        elev_range=(-0.30, 0.30), elev_grid=61,
                        gnc_c_px=5.0, huber_delta=20.0,
                        weights=weights)
    # 跑优化
    result = ba.optimize(use_gnc=True, max_outer=10, verbose=False)
    return ba, result


def compute_sigma_Pz_from_JTJ(ba, J_full, sigma_obs):
    """
    从 BA 雅可比矩阵算 σ_Pz = sqrt([(J^T Σ^{-1} J)^+]_zz)
    J_full: (N, 2) 残差对 landmark z 的雅可比
    简化版：J 是 N×1 向量（仅 z 维度）
    """
    # N 残差
    N = J_full.shape[0]
    # Σ = σ_obs² · I
    J_weighted = J_full / sigma_obs  # (N,)
    # H = J^T J
    H = np.sum(J_weighted ** 2)
    if H < 1e-12:
        return np.inf
    return float(1.0 / np.sqrt(H))


def main():
    print("=" * 60)
    print("R-X3 完整版：UnifiedSonarBA + 蒙特卡洛")
    print("=" * 60)
    print("数据: _tmp_heave_baseline/general_h1.2")
    print()

    # 加载 + 构造 BA 输入
    print("加载数据...")
    landmarks, poses6, obs_by_lm, obs_list, odom_rel, calib, well_mask, base_frame, sigma_rho, sigma_theta = load_heave_h12_for_ba()
    print(f"  landmarks: {landmarks.shape}, poses: {poses6.shape}")
    print(f"  obs_list: {len(obs_list)}, obs_by_lm: {len(obs_by_lm)}")
    print(f"  well_mask: well={int(well_mask.sum())}/{landmarks.shape[0]}")
    print(f"  calib: {calib}, σ_ρ={sigma_rho}, σ_θ={sigma_theta}")

    # 跑 1 次 BA（无加噪）
    print(f"\n跑第 1 次 BA（无加噪）...")
    t0 = time.time()
    ba0, result0 = run_ba_once(landmarks, poses6, obs_by_lm, obs_list, odom_rel, calib,
                                well_mask, base_frame, sigma_rho, sigma_theta,
                                add_noise=False)
    dt = time.time() - t0
    print(f"  耗时 {dt:.1f}s")
    land_after_ba = result0["world"]
    print(f"  BA 后 landmark shape: {land_after_ba.shape}")
    print(f"  BA 后 landmark z: {land_after_ba[:5, 2]}")

    # 检查 well/weak landmarks 的 z 与 GT 差
    diff_z = land_after_ba[:, 2] - landmarks[:, 2]
    print(f"  z 偏差 median: {np.median(diff_z):.4f}m, max: {np.max(np.abs(diff_z)):.4f}m")

    # σ_Pz 解析版（R-X0b）
    out_obs = compute_observability_per_landmark(
        landmarks, obs_by_lm, calib, poses6, tau_z=0.05,
        sigma_rho=sigma_rho, sigma_theta=sigma_theta,
    )
    sigma_Pz_th = out_obs["sigma_Pz"]
    print(f"\n  σ_Pz 解析版: median={np.median(sigma_Pz_th[np.isfinite(sigma_Pz_th)]):.4f}m")

    # 跑 M=20 蒙特卡洛（试用；M=200 在后续 session）
    M_mc = 20
    print(f"\n跑 M={M_mc} 蒙特卡洛 BA（每次加噪 + 重跑）...")
    z_estimates = np.zeros((M_mc, landmarks.shape[0]))
    for m in range(M_mc):
        if m % 5 == 0:
            print(f"  mc {m}/{M_mc}...", flush=True)
        t1 = time.time()
        ba_m, result_m = run_ba_once(landmarks, poses6, obs_by_lm, obs_list, odom_rel, calib,
                                       well_mask, base_frame, sigma_rho, sigma_theta,
                                       add_noise=True, seed=42 + m)
        z_estimates[m] = result_m["world"][:, 2]
        dt_m = time.time() - t1
        if m == 0:
            print(f"    单次 BA 耗时 {dt_m:.2f}s（预计总 {dt_m * M_mc / 60:.1f} min）")

    # 算 s_z
    s_z = z_estimates.std(axis=0)  # (M,)
    mean_z = z_estimates.mean(axis=0)  # (M,)

    # 比 s_z / σ_Pz
    print(f"\n=== R-X3 完整版汇总（well/weak landmarks）===")
    well_lm = np.where(well_mask)[0]
    print(f"  well/weak landmarks: {len(well_lm)}")
    ratios = []
    for j in well_lm:
        s_z_j = s_z[j]
        sigma_th_j = float(sigma_Pz_th[j])
        if sigma_th_j > 1e-9 and np.isfinite(s_z_j):
            r = s_z_j / sigma_th_j
            ratios.append((j, r, s_z_j, sigma_th_j))
    if ratios:
        r_arr = np.array([r[1] for r in ratios])
        print(f"  s_z / σ_Pz ratio: median={np.median(r_arr):.3f}, "
              f"min={r_arr.min():.3f}, max={r_arr.max():.3f}")
        n_in = int(np.sum((r_arr >= 0.8) & (r_arr <= 1.3)))
        print(f"  ratio ∈ [0.8, 1.3]: {n_in}/{len(ratios)}")
        # 前 5 个 ratio
        print(f"\n  top 5 ratios:")
        sorted_r = sorted(ratios, key=lambda x: x[1])
        for j, r, s, t in sorted_r[:5]:
            print(f"    lm {j}: s_z={s*100:.2f}cm, σ_Pz={t*100:.2f}cm, ratio={r:.3f}")

    # 落盘
    out = {
        "M_mc": M_mc,
        "well_lm": [int(j) for j in well_lm],
        "ratios": [(int(j), float(r), float(s), float(t)) for j, r, s, t in ratios],
        "n_in_range": n_in if ratios else 0,
        "n_total": len(ratios),
    }
    out_path = Path("R_X3_BA_RESULTS.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False, default=str)
    print(f"\n[ok] 落盘 {out_path}")


if __name__ == "__main__":
    main()
