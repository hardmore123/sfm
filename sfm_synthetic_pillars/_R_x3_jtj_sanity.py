"""
R-X3 完整版框架：用 R-X0b 修复版 σ_Pz 公式 + V2 高度反演残差验证
=====================================================================

R-X3 验收：
  🔢 s_z / σ̂_Pz ∈ [0.8, 1.3]
  🔢 s_z / (σ_ρ/(√N·std(φ))) ∈ [0.8, 1.3]

简化策略（避免完整 UnifiedSonarBA 接入的复杂性）：
  - σ_Pz 解析版：R-X0b 修复版 (J^T J)^+ 伪逆
  - s_z 蒙特卡洛：用 V2 高度反演公式 + 加噪
    - 对每 landmark，用多帧 L_s 测量
    - 蒙特卡洛 200 次加噪 → V2 反演 → z 估计 → std
  - 比 s_z / σ_Pz

注：完整 R-X3 需要 UnifiedSonarBA 联合 BA（pose + landmark）。
    本框架用 V2 闭式解（每 landmark 独立）做简化。
"""
import os
import sys
import json
import time
import numpy as np
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from observability import compute_observability_per_landmark
from feasibility import ARIS_MAIN
from trajectory import euler_to_matrix


def load_heave_h12(base="F:/sfm/sfm_synthetic_pillars/_tmp_heave_baseline"):
    """读 _tmp_heave_baseline/general_h1.2 数据。"""
    base = Path(base) / "general_h1.2"
    landmarks = np.load(base / "gt/landmarks_gt.npy")
    pose_frame_ids = np.load(base / "input/pose_frame_ids.npy")
    poses_se3 = np.load(base / "input/poses_est.npy")
    K = poses_se3.shape[0]
    poses6 = np.zeros((K, 6))
    from scipy.spatial.transform import Rotation
    for k in range(K):
        poses6[k, :3] = poses_se3[k, :3, 3]
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


def v2_invert_height_mc(landmark_xy, obs_list, poses6, sigma_rho, sigma_theta, n_mc=200):
    """
    用 V2 公式对单 landmark 多视做蒙特卡洛 BA 反演 z。
    V2: h = L_s · z_s / (D_t + L_s)
    简化：每帧用 L_s 测量（沿阴影段），但 V2 需要 D_t。
    这里假设 D_t = 平均水平距离（从 pose 推断）。

    Returns: z_estimates (n_mc,), mean_z, s_z
    """
    M = len(obs_list)
    if M < 2:
        return None
    rng = np.random.default_rng(42)
    z_estimates = []
    # 估计 D_t（用首帧的 obs 计算 D_t）
    pi0, theta0, rho0 = obs_list[0]
    R0 = np.array([
        [np.cos(poses6[pi0, 5]), -np.sin(poses6[pi0, 5]), 0],
        [np.sin(poses6[pi0, 5]),  np.cos(poses6[pi0, 5]), 0],
        [0, 0, 1],
    ])
    t0 = poses6[pi0, :3]
    # D_t 用 GT 估算（从 landmark 已知）
    landmark_3d = np.array([landmark_xy[0], landmark_xy[1], 0])
    Pb = R0.T @ (landmark_3d - t0)
    D_t = np.hypot(Pb[0], Pb[1])
    if D_t < 0.5:
        D_t = 5.0  # fallback

    # 估算 L_s：从多帧 rho 差分（粗略）
    rho_arr = np.array([o[2] for o in obs_list])
    L_s_est = np.median(rho_arr) - D_t
    if L_s_est <= 0:
        L_s_est = 1.0

    z_s_init = float(poses6[pi0, 2])
    for m in range(n_mc):
        # 加噪
        obs_noisy = []
        for pi, theta, rho in obs_list:
            obs_noisy.append((pi, theta + rng.normal(0, sigma_theta),
                              rho + rng.normal(0, sigma_rho)))
        # 用 V2 公式
        rho_noisy_arr = np.array([o[2] for o in obs_noisy])
        L_s_noisy = np.median(rho_noisy_arr) - D_t
        if L_s_noisy <= 0:
            continue
        z_s_noisy = z_s_init + rng.normal(0, 0.05)
        # h = L_s · z_s / (D_t + L_s)
        h = L_s_noisy * z_s_noisy / (D_t + L_s_noisy)
        h = np.clip(h, 0, z_s_noisy - 0.01)
        z_estimates.append(h)
    if len(z_estimates) < 10:
        return None
    z_arr = np.array(z_estimates)
    return z_arr, float(z_arr.mean()), float(z_arr.std())


def main():
    print("=" * 60)
    print("R-X3 完整版框架：R-X0b σ_Pz vs V2 蒙特卡洛 s_z")
    print("=" * 60)
    print("数据: _tmp_heave_baseline/general_h1.2")
    print()

    # 加载
    landmarks, poses6, obs_by_lm, calib, sigma_rho, sigma_theta = load_heave_h12()
    print(f"  landmarks: {landmarks.shape}, poses: {poses6.shape}, "
          f"obs_by_lm: {len(obs_by_lm)}, σ_ρ={sigma_rho}, σ_θ={sigma_theta}")

    # σ_Pz 解析版（R-X0b 修复）
    out = compute_observability_per_landmark(
        landmarks, obs_by_lm, calib, poses6, tau_z=0.05,
        sigma_rho=sigma_rho, sigma_theta=sigma_theta,
    )
    sigma_Pz_th = out["sigma_Pz"]
    cls = out["classification"]
    print(f"  四分类: well={int((cls==3).sum())}, weak={int((cls==2).sum())}, "
          f"blind={int((cls==1).sum())}, insufficient={int((cls==0).sum())}")

    # 选 well + obs≥3 的 landmarks
    valid_lm = [j for j in range(landmarks.shape[0])
                if cls[j] in (2, 3) and len(obs_by_lm.get(j, [])) >= 3]
    print(f"  有效 landmarks: {len(valid_lm)}")

    rng = np.random.default_rng(7)
    n_sample = min(5, len(valid_lm))
    sampled = sorted(rng.choice(valid_lm, size=n_sample, replace=False).tolist())
    print(f"  采样: {sampled}")

    # 蒙特卡洛
    results = []
    for j in sampled:
        landmark_xy = landmarks[j, :2]
        z_gt = landmarks[j, 2]
        # 蒙特卡洛 s_z
        mc = v2_invert_height_mc(landmark_xy, obs_by_lm[j], poses6, sigma_rho, sigma_theta, n_mc=200)
        if mc is None:
            continue
        z_arr, mean_z, s_z = mc
        sigma_th = float(sigma_Pz_th[j])
        ratio = s_z / sigma_th if sigma_th > 1e-9 else np.inf
        results.append({
            "lm_idx": int(j),
            "n_obs": len(obs_by_lm[j]),
            "z_gt_m": float(z_gt),
            "mean_z_mc_m": mean_z,
            "s_z_mc_m": s_z,
            "sigma_Pz_theory_m": sigma_th,
            "ratio1": float(ratio),
        })
        print(f"  lm {j}: z_gt={z_gt:.2f}, mean_z={mean_z:.3f}, "
              f"s_z={s_z*100:.2f}cm, σ_Pz={sigma_th*100:.2f}cm, ratio={ratio:.2f}")

    # 汇总
    print(f"\n=== R-X3 完整版汇总 ===")
    ratios = [r["ratio1"] for r in results if r["sigma_Pz_theory_m"] > 1e-9]
    if ratios:
        print(f"  s_z / σ_Pz ratio: median={np.median(ratios):.2f}, "
              f"range=[{min(ratios):.2f}, {max(ratios):.2f}]")
        n_in = sum(1 for r in ratios if 0.8 <= r <= 1.3)
        print(f"  ratio ∈ [0.8, 1.3]: {n_in}/{len(ratios)}")

    out_path = Path("R_X3_FULL_RESULTS.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"results": results, "n_in_range": n_in if ratios else 0,
                   "n_total": len(ratios)}, f, indent=2, ensure_ascii=False, default=str)
    print(f"\n[ok] 落盘 {out_path}")


if __name__ == "__main__":
    main()
