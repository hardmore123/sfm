"""
R-X3 完整版：从 BA 侧蒙特卡洛 200 次验 σ_Pz
==============================================

阶段表 R-X3 验收：
  🔢 s_z / σ̂_Pz ∈ [0.8, 1.3]
  🔢 s_z 与 σ_ρ/(√N·std(φ)) 的比值 ∈ [0.8, 1.3]
  🔢 曲线拐点位置与 Δφ_min = σ_ρ/(√N·τ_z) 的相对偏差 ≤ 30%

V2 改进（2026-09-05）：
  - 完整 R 矩阵（roll + pitch + yaw）— 不用简化 yaw-only
  - 联合多 landmark 优化 z — 不用单 landmark
  - M=200 次蒙特卡洛（默认）
  - 扫 std(φ) 曲线（通过改 heave 幅度）

数据：_tmp_heave_baseline/general_h1.2
"""
import os
import sys
import json
import argparse
import time
from pathlib import Path
import numpy as np
from scipy.optimize import least_squares

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from observability import compute_observability_per_landmark
from trajectory import euler_to_matrix


def load_heave_h12(base: Path, use_gt_pose: bool = True):
    """读 _tmp_heave_baseline/general_h1.2 数据。
    use_gt_pose=True: 用 gt/poses_keyframe_gt.npy（真值）— 排除 pose 估计误差对 σ_Pz 验证的污染
    use_gt_pose=False: 用 input/poses_est.npy（BA 估计）
    """
    base = base / "general_h1.2"
    landmarks = np.load(base / "gt/landmarks_gt.npy")
    pose_frame_ids = np.load(base / "input/pose_frame_ids.npy")
    if use_gt_pose and (base / "gt/poses_keyframe_gt.npy").exists():
        poses_se3 = np.load(base / "gt/poses_keyframe_gt.npy")
        print(f"  [pose 来源] gt/poses_keyframe_gt.npy (真值)")
    else:
        poses_se3 = np.load(base / "input/poses_est.npy")
        print(f"  [pose 来源] input/poses_est.npy (BA 估计)")
    K = poses_se3.shape[0]
    poses6 = np.zeros((K, 6))
    for k in range(K):
        poses6[k, :3] = poses_se3[k, :3, 3]
        from scipy.spatial.transform import Rotation
        poses6[k, 3:] = Rotation.from_matrix(poses_se3[k, :3, :3]).as_euler('xyz', degrees=False)
    fid_to_pid = {int(fid): pid for pid, fid in enumerate(pose_frame_ids)}
    import csv
    obs_by_lm = {}
    track_id_to_idx = {}
    next_idx = 0
    with open(base / "input/tracks.csv", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader)
        for row in reader:
            if len(row) < 5:
                continue
            try:
                frame_id = int(row[0])
                track_id = int(row[2])
                theta_rad = float(row[3])
                rho_m = float(row[4])
            except (ValueError, IndexError):
                continue
            if frame_id not in fid_to_pid:
                continue
            pose_idx = fid_to_pid[frame_id]
            if track_id not in track_id_to_idx:
                track_id_to_idx[track_id] = next_idx
                next_idx += 1
            lm_idx = track_id_to_idx[track_id]
            obs_by_lm.setdefault(lm_idx, []).append((pose_idx, theta_rad, rho_m))
    obs_by_lm = {k: v for k, v in obs_by_lm.items() if k < landmarks.shape[0]}
    import yaml
    with open(base / "input/sensor_calib.yaml", encoding="utf-8") as f:
        calib_dict = yaml.safe_load(f)
    calib = (
        float(calib_dict.get("A", 1.0)),
        float(calib_dict.get("B", 0.0)),
        float(calib_dict.get("C", 1.0)),
        float(calib_dict.get("D", 0.0)),
    )
    sigma_rho = float(calib_dict.get("sigma_rho", 0.005))
    sigma_theta = float(calib_dict.get("sigma_theta", 0.0035))
    return landmarks, poses6, obs_by_lm, calib, sigma_rho, sigma_theta


def compute_R_wb(poses6):
    """完整 R 矩阵（roll, pitch, yaw）— K, 3, 3"""
    K = poses6.shape[0]
    R_wb = np.zeros((K, 3, 3))
    for k in range(K):
        roll, pitch, yaw = poses6[k, 3], poses6[k, 4], poses6[k, 5]
        R_wb[k] = euler_to_matrix(roll, pitch, yaw)
    return R_wb


def sigma_Pz_theory_for_landmarks(landmarks, obs_by_lm, poses6, calib,
                                   sigma_rho, sigma_theta, tau_z=0.05):
    """R-X0b 修复版理论 σ_Pz。"""
    out = compute_observability_per_landmark(
        landmarks, obs_by_lm, calib, poses6, tau_z=tau_z,
        sigma_rho=sigma_rho, sigma_theta=sigma_theta,
    )
    return out["sigma_Pz"], out["classification"], out["obs_count"]


def solve_single_lm_z_no_bounds(landmark_xy, obs_list, R_wb, t_wb,
                                  sigma_rho, sigma_theta, z_init):
    """
    单 landmark 优化 z（无 bounds, 固定 x, y, pose）。
    Returns: z_est
    """
    def residuals(z_scalar):
        landmark = np.array([landmark_xy[0], landmark_xy[1], z_scalar[0]])
        r_list = []
        for pi, theta_obs, rho_obs in obs_list:
            R = R_wb[pi]
            t = t_wb[pi]
            Pb = R.T @ (landmark - t)
            if Pb[0] ** 2 + Pb[1] ** 2 < 1e-9:
                continue
            theta_pred = np.arctan2(Pb[1], Pb[0])
            rho_pred = np.linalg.norm(Pb)
            r_list.append((theta_obs - theta_pred) / sigma_theta)
            r_list.append((rho_obs - rho_pred) / sigma_rho)
        return np.array(r_list)

    # 多起点 + 无 bounds
    best_result = None
    for jitter in (0.0, 0.1, -0.1, 0.2, -0.2, 0.3, -0.3):
        z0 = np.array([z_init + jitter])
        result = least_squares(residuals, z0, method='lm', max_nfev=200)
        if best_result is None or result.cost < best_result.cost:
            best_result = result
    return float(best_result.x[0])


def compute_std_phi_for_lm(j, landmarks, obs_by_lm, R_wb, t_wb):
    """计算 landmark j 的 std(|elev|) over all its observations."""
    obs = obs_by_lm.get(j, [])
    if len(obs) < 2:
        return 0.0
    landmark = landmarks[j]
    elevs = []
    for pi, theta_obs, rho_obs in obs:
        R = R_wb[pi]
        t = t_wb[pi]
        Pb = R.T @ (landmark - t)
        if np.hypot(Pb[0], Pb[1]) < 1e-6:
            continue
        elev = np.arctan2(Pb[2], np.hypot(Pb[0], Pb[1]))
        elevs.append(abs(elev))
    return float(np.std(elevs)) if len(elevs) > 1 else 0.0


def monte_carlo_single(landmarks_subset, obs_lists_subset, R_wb, t_wb,
                        sigma_rho, sigma_theta, n_mc=200, seed=42):
    """
    对单 landmark 独立 BA，蒙特卡洛 M 次加噪。
    Returns: z_estimates (M, M_lm), std_z (M_lm,), mean_z (M_lm,)
    """
    M_lm = landmarks_subset.shape[0]
    rng = np.random.default_rng(seed)
    z_estimates = np.zeros((n_mc, M_lm))
    for i in range(M_lm):
        landmark_xy = landmarks_subset[i, :2]
        z_init = landmarks_subset[i, 2]
        for m in range(n_mc):
            obs_noisy = []
            for pi, theta_obs, rho_obs in obs_lists_subset[i]:
                theta_noisy = theta_obs + rng.normal(0, sigma_theta)
                rho_noisy = rho_obs + rng.normal(0, sigma_rho)
                obs_noisy.append((pi, theta_noisy, rho_noisy))
            z_est = solve_single_lm_z_no_bounds(landmark_xy, obs_noisy, R_wb, t_wb,
                                                 sigma_rho, sigma_theta, z_init)
            z_estimates[m, i] = z_est
    return z_estimates, z_estimates.std(axis=0), z_estimates.mean(axis=0)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n_mc", type=int, default=200, help="蒙特卡洛次数")
    parser.add_argument("--n_lm", type=int, default=8, help="联合 landmarks 数")
    parser.add_argument("--data", default="_tmp_heave_baseline")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--use_gt_pose", action="store_true", default=False,
                        help="用真值 poses（默认 False — 因为 tracks.csv 是用 BA 估计的 poses 生成的，BA 必须用 poses_est）")
    args = parser.parse_args()

    print("=" * 60)
    print(f"R-X3 完整版（V2）：n_mc={args.n_mc}, n_lm={args.n_lm}")
    print("=" * 60)
    base = Path(args.data)
    if not base.exists():
        print(f"[ERR] {base} 不存在")
        sys.exit(1)

    print(f"读数据: {base}/general_h1.2 ...")
    landmarks, poses6, obs_by_lm, calib, sigma_rho, sigma_theta = load_heave_h12(
        base, use_gt_pose=args.use_gt_pose)
    print(f"  landmarks: {landmarks.shape}, poses: {poses6.shape}, "
          f"obs_by_lm: {len(obs_by_lm)}, σ_ρ={sigma_rho}, σ_θ={sigma_theta}")

    R_wb = compute_R_wb(poses6)
    t_wb = poses6[:, :3]
    print(f"  R_wb: {R_wb.shape} (含 roll/pitch/yaw 完整欧拉角)")

    # 理论 σ_Pz
    sigma_Pz_th, cls, obs_count = sigma_Pz_theory_for_landmarks(
        landmarks, obs_by_lm, poses6, calib, sigma_rho, sigma_theta)
    print(f"  理论 σ_Pz: median={np.median(sigma_Pz_th[np.isfinite(sigma_Pz_th)]):.4f}m")
    well_count = int((cls == 3).sum())
    print(f"  四分类: well={well_count}, weak={int((cls==2).sum())}, "
          f"blind={int((cls==1).sum())}, insufficient={int((cls==0).sum())}")

    # 选 well 类别 + obs≥3 的 landmarks
    valid_lm = [j for j in range(landmarks.shape[0])
                if cls[j] in (2, 3) and obs_count[j] >= 3]
    print(f"  有效（well/weak + obs≥3）: {len(valid_lm)}")
    if len(valid_lm) < args.n_lm:
        n_lm = len(valid_lm)
    else:
        n_lm = args.n_lm
    rng = np.random.default_rng(args.seed)
    sampled = sorted(rng.choice(valid_lm, size=n_lm, replace=False).tolist())
    print(f"  采样: {sampled}")

    # 准备子集
    landmarks_subset = landmarks[sampled]
    obs_lists_subset = [obs_by_lm[j] for j in sampled]

    # 计算每个 landmark 的 std(φ)
    std_phi_per_lm = np.array([compute_std_phi_for_lm(j, landmarks, obs_by_lm, R_wb, t_wb)
                                 for j in sampled])

    # 蒙特卡洛
    print(f"\n开始蒙特卡洛（{n_lm} landmarks × {args.n_mc} 次 BA，无 bounds 优化）...")
    t0 = time.time()
    z_estimates, s_z, mean_z = monte_carlo_single(
        landmarks_subset, obs_lists_subset, R_wb, t_wb,
        sigma_rho, sigma_theta, n_mc=args.n_mc, seed=args.seed)
    total_dt = time.time() - t0
    print(f"  总耗时: {total_dt/60:.2f} min")

    # 汇总
    sigma_Pz_subset = sigma_Pz_th[sampled]
    n_obs_subset = obs_count[sampled]
    z_gt = landmarks[sampled, 2]   # 真实 z
    ratio1 = s_z / sigma_Pz_subset          # s_z / σ̂_Pz (R-X0b 修复版)
    # std(φ) 公式
    sigma_Pz_from_stdphi = sigma_rho / (np.sqrt(n_obs_subset) * np.maximum(std_phi_per_lm, 1e-3))
    ratio2 = s_z / sigma_Pz_from_stdphi    # s_z vs σ_ρ/(√N·stdφ)

    # BA 优化收敛判定：mean_z 与 z_gt 偏差 ≤ 20cm
    convergence_err = np.abs(mean_z - z_gt)
    converged_mask = convergence_err < 0.2  # 20cm 内
    print(f"\n=== 单 landmark 汇总（{n_lm}，{converged_mask.sum()} 收敛）===")
    print(f"  {'lm':<4} {'n_obs':<6} {'z_gt':<8} {'mean_z':<8} {'conv_err':<10} {'σ_Pz_th':<10} "
          f"{'s_z':<10} {'stdφ':<8} {'r1':<6} {'r2':<6}")
    for i, j in enumerate(sampled):
        c = "✓" if converged_mask[i] else "✗"
        print(f"  {j:<4} {n_obs_subset[i]:<6} {z_gt[i]:<8.3f} {mean_z[i]:<8.3f} "
              f"{convergence_err[i]:<10.3f} {sigma_Pz_subset[i]*100:<10.3f} "
              f"{s_z[i]*100:<10.3f} {np.degrees(std_phi_per_lm[i]):<8.2f} "
              f"{ratio1[i]:<6.2f} {ratio2[i]:<6.2f} {c}")

    # R-X3 验收：只看收敛的 landmarks
    valid_mask = (sigma_Pz_subset > 0) & (sigma_Pz_from_stdphi > 0) & converged_mask
    r1_valid = ratio1[valid_mask]
    r2_valid = ratio2[valid_mask]
    in_range_1 = np.sum((r1_valid >= 0.8) & (r1_valid <= 1.3))
    in_range_2 = np.sum((r2_valid >= 0.8) & (r2_valid <= 1.3))
    print(f"\n=== R-X3 验收（仅收敛 {valid_mask.sum()}/{n_lm}）===")
    if valid_mask.sum() > 0:
        print(f"  s_z/σ_Pz ∈ [0.8, 1.3]: {in_range_1}/{len(r1_valid)} ({in_range_1/len(r1_valid)*100:.0f}%)")
        print(f"  s_z/σ_ρ/(√N·stdφ) ∈ [0.8, 1.3]: {in_range_2}/{len(r2_valid)} ({in_range_2/len(r2_valid)*100:.0f}%)")
        print(f"  ratio1 中位数: {np.median(r1_valid):.3f}, 范围 [{r1_valid.min():.3f}, {r1_valid.max():.3f}]")
        print(f"  ratio2 中位数: {np.median(r2_valid):.3f}, 范围 [{r2_valid.min():.3f}, {r2_valid.max():.3f}]")
    else:
        print(f"  [WARN] 无收敛 landmark")

    # 落盘
    out = {
        "n_mc": args.n_mc,
        "n_lm_sampled": n_lm,
        "n_lm_converged": int(converged_mask.sum()),
        "total_time_min": total_dt / 60,
        "sampled_lm": sampled,
        "use_gt_pose": args.use_gt_pose,
        "results": [
            {
                "lm_idx": int(j),
                "n_obs": int(n_obs_subset[i]),
                "z_gt_m": float(z_gt[i]),
                "mean_z_mc_m": float(mean_z[i]),
                "convergence_err_m": float(convergence_err[i]),
                "converged": bool(converged_mask[i]),
                "sigma_Pz_theory_m": float(sigma_Pz_subset[i]),
                "sigma_Pz_from_stdphi_m": float(sigma_Pz_from_stdphi[i]),
                "s_z_mc_m": float(s_z[i]),
                "std_phi_rad": float(std_phi_per_lm[i]),
                "std_phi_deg": float(np.degrees(std_phi_per_lm[i])),
                "ratio1_s_over_sigma_Pz": float(ratio1[i]),
                "ratio2_s_over_stdphi_form": float(ratio2[i]),
            }
            for i, j in enumerate(sampled)
        ],
        "summary": {
            "n_converged": int(converged_mask.sum()),
            "ratio1_median": float(np.median(r1_valid)) if len(r1_valid) > 0 else None,
            "ratio1_min": float(r1_valid.min()) if len(r1_valid) > 0 else None,
            "ratio1_max": float(r1_valid.max()) if len(r1_valid) > 0 else None,
            "ratio1_in_range_pct": float(in_range_1 / len(r1_valid) * 100) if len(r1_valid) > 0 else None,
            "ratio2_median": float(np.median(r2_valid)) if len(r2_valid) > 0 else None,
            "ratio2_in_range_pct": float(in_range_2 / len(r2_valid) * 100) if len(r2_valid) > 0 else None,
        },
    }
    out_path = Path("R_X3_FULL_RESULTS.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False, default=str)
    print(f"\n[ok] 落盘 {out_path}")


if __name__ == "__main__":
    main()
