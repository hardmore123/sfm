"""
大论文 6.1 A vs B 实验（快速版：用 scipy 直接调 trf，无自定义类）
"""
import os, sys, time, json
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "BA代码")))

import ba_optimize as base
from scipy.optimize import least_squares
import csv


def load_setup(input_dir, gt_dir):
    poses_mat, frame_ids, landmarks, tracks = base.load_data(input_dir)
    K, M = len(frame_ids), landmarks.shape[0]
    poses6 = np.array([base.matrix_to_pose6(poses_mat[i]) for i in range(K)])
    track_to_lm = base.build_track_to_landmark(poses_mat, frame_ids, landmarks, tracks)
    A, B, C, D = base.calibrate_pixels(tracks)
    fid_to_idx = {int(fid): i for i, fid in enumerate(frame_ids)}
    observations = [(fid_to_idx[fid], track_to_lm[tid], th, rh, bm, rg)
                    for (fid, tid, th, rh, bm, rg) in tracks
                    if fid in fid_to_idx and tid in track_to_lm]
    odom_rel = [(k, np.linalg.inv(poses_mat[k]) @ poses_mat[k + 1]) for k in range(K - 1)]
    o_pose = np.array([o[0] for o in observations], dtype=np.int64)
    o_lm = np.array([o[1] for o in observations], dtype=np.int64)
    o_beam = np.array([o[4] for o in observations], dtype=np.float64)
    o_range = np.array([o[5] for o in observations], dtype=np.float64)
    return poses6, landmarks, observations, odom_rel, o_pose, o_lm, o_beam, o_range, A, B, C, D, K, M


def make_residuals(poses6, landmarks, odom_rel, o_pose, o_lm, o_beam, o_range, A, B, C, D, K, M,
                   z_prior=None, sigma_z=None, w_z=10.0,
                   w_prior=1000.0, w_odomT=100.0, w_odomR=100.0, w_sonar=1.0, w_lmprior=1.0):
    def unpack(x):
        poses = x[:K * 6].reshape(K, 6)
        lms = x[K * 6:].reshape(M, 3)
        return poses, lms

    def residuals(x):
        poses, lms = unpack(x)
        res = []
        # 1) 首帧先验
        res.append(w_prior * (poses[0] - poses6[0]))
        # 2) 里程计
        for (k, T_meas) in odom_rel:
            Tk = base.pose6_to_matrix(poses[k])
            Tk1 = base.pose6_to_matrix(poses[k + 1])
            T_rel = np.linalg.inv(Tk) @ Tk1
            Err = np.linalg.inv(T_meas) @ T_rel
            res.append(np.concatenate([w_odomT * Err[:3, 3],
                                      w_odomR * base.rot_to_vec(Err[:3, :3])]))
        # 3) 声呐
        R = np.array([base.euler_to_matrix(p[3], p[4], p[5]) for p in poses])
        Rt = np.transpose(R, (0, 2, 1))
        t = poses[:, :3]
        Pw = lms[o_lm]
        diff = Pw - t[o_pose]
        Pb = np.einsum("nij,nj->ni", Rt[o_pose], diff)
        theta_pred = np.arctan2(Pb[:, 1], Pb[:, 0])
        rho_pred = np.linalg.norm(Pb, axis=1)
        u_pred = A * theta_pred + B
        v_pred = C * rho_pred + D
        res.append(w_sonar * (u_pred - o_beam))
        res.append(w_sonar * (v_pred - o_range))
        # 4) lm 弱先验
        res.append(w_lmprior * (lms - landmarks).flatten())
        # 5) **创新二·模块2 阴影高度先验**
        if z_prior is not None and sigma_z is not None and w_z > 0:
            valid = np.isfinite(z_prior) & np.isfinite(sigma_z) & (sigma_z > 0)
            if valid.any():
                r_z = (lms[valid, 2] - z_prior[valid]) / sigma_z[valid]
                res.append(w_z * r_z)
        return np.concatenate(res)
    return residuals, unpack


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


def main():
    mode = "mixed"
    input_dir = "../BA代码/sim_input_big"
    gt_dir = f"./big_paper_sim/{mode}/gt"
    inv2_dir = f"./big_paper_sim/{mode}/innovation2"

    h_inv = np.load(os.path.join(inv2_dir, "height_inverted.npy"))
    sigma_h = np.load(os.path.join(inv2_dir, "sigma_height.npy"))

    poses6, landmarks, observations, odom_rel, o_pose, o_lm, o_beam, o_range, A, B, C, D, K, M = load_setup(input_dir, gt_dir)
    N, H, W = h_inv.shape
    print(f"数据: K={K} 关键帧, M={M} lm, N={N} 帧, H×W={H}×{W}")

    # 聚合成 lm 级 z_prior
    z_prior = np.full(M, np.nan)
    sigma_z = np.full(M, np.inf)
    lm_h = {j: [] for j in range(M)}
    for o in observations:
        pi, j, th, rh, bm, rg = o
        ri = int(np.clip(round(rg), 0, H - 1))
        bi = int(np.clip(round(bm), 0, W - 1))
        if np.isfinite(h_inv[pi, ri, bi]) and 0 < h_inv[pi, ri, bi] < 5.0:
            lm_h[j].append(h_inv[pi, ri, bi])
    for j in range(M):
        if lm_h[j]:
            z_prior[j] = float(np.median(lm_h[j]))
            sigma_z[j] = float(np.median(sigma_h[lm_h[j][0] > 0])) if lm_h[j] else 0.05
    # 用统一的不确定度（如果没有就 0.05m）
    sigma_z = np.where(np.isfinite(sigma_z), sigma_z, 0.05)
    n_prior = int(np.sum(np.isfinite(z_prior)))
    print(f"先验覆盖: {n_prior}/{M} lm, z median={np.nanmedian(z_prior):.2f}m, "
          f"sigma median={np.median(sigma_z[sigma_z<np.inf]):.3f}m")

    x0 = np.concatenate([poses6.flatten(), landmarks.flatten()])

    # ---- A: 无阴影先验 ----
    print("\n=== A. V2 + 无阴影高度先验（纯多视几何） ===")
    res_a_fn, unpack = make_residuals(poses6, landmarks, odom_rel, o_pose, o_lm, o_beam, o_range,
                                        A, B, C, D, K, M,
                                        z_prior=None, sigma_z=None, w_z=0)
    r0 = res_a_fn(x0)
    print(f"  初 RMS: {np.sqrt(np.mean(r0**2)):.3f}px")
    t0 = time.time()
    res_a = least_squares(res_a_fn, x0, method="trf", loss="huber", f_scale=20.0,
                          max_nfev=80, verbose=0)
    t_a = time.time() - t0
    poses_a, lms_a = unpack(res_a.x)
    res_a_dict = evaluate(poses_a, lms_a, gt_dir)
    res_a_dict["time_s"] = t_a
    res_a_dict["rms_px"] = float(np.sqrt(np.mean(res_a.fun**2)))
    print(f"  A: t={t_a:.1f}s, RMS={res_a_dict['rms_px']:.3f}px, "
          f"pos={res_a_dict['pose_err_mean_cm']:.2f}cm, lm={res_a_dict['lm_err_mean_cm']:.2f}cm, "
          f"z={res_a_dict['lm_z_err_mean_cm']:.2f}cm")

    # ---- B: 阴影高度先验 ----
    print("\n=== B. V2 + 阴影高度先验（创新二·模块2 注入） ===")
    res_b_fn, unpack = make_residuals(poses6, landmarks, odom_rel, o_pose, o_lm, o_beam, o_range,
                                        A, B, C, D, K, M,
                                        z_prior=z_prior, sigma_z=sigma_z, w_z=10.0)
    r0 = res_b_fn(x0)
    print(f"  初 RMS: {np.sqrt(np.mean(r0**2)):.3f}px")
    t0 = time.time()
    res_b = least_squares(res_b_fn, x0, method="trf", loss="huber", f_scale=20.0,
                          max_nfev=80, verbose=0)
    t_b = time.time() - t0
    poses_b, lms_b = unpack(res_b.x)
    res_b_dict = evaluate(poses_b, lms_b, gt_dir)
    res_b_dict["time_s"] = t_b
    res_b_dict["rms_px"] = float(np.sqrt(np.mean(res_b.fun**2)))
    print(f"  B: t={t_b:.1f}s, RMS={res_b_dict['rms_px']:.3f}px, "
          f"pos={res_b_dict['pose_err_mean_cm']:.2f}cm, lm={res_b_dict['lm_err_mean_cm']:.2f}cm, "
          f"z={res_b_dict['lm_z_err_mean_cm']:.2f}cm")

    # ---- 对比 ----
    delta_lm = res_a_dict['lm_err_mean_cm'] - res_b_dict['lm_err_mean_cm']
    delta_z = res_a_dict['lm_z_err_mean_cm'] - res_b_dict['lm_z_err_mean_cm']
    print("\n" + "=" * 70)
    print("6.1 仰角来源消融结果（A vs B）")
    print("=" * 70)
    print(f"{'配置':<30} | {'pos (cm)':<10} | {'lm (cm)':<10} | {'z (cm)':<10} | {'t(s)':<7}")
    print("-" * 75)
    print(f"{'A 只多视几何':<30} | {res_a_dict['pose_err_mean_cm']:<10.2f} | "
          f"{res_a_dict['lm_err_mean_cm']:<10.2f} | {res_a_dict['lm_z_err_mean_cm']:<10.2f} | "
          f"{res_a_dict['time_s']:<7.1f}")
    print(f"{'B 多视+阴影高度先验':<30} | {res_b_dict['pose_err_mean_cm']:<10.2f} | "
          f"{res_b_dict['lm_err_mean_cm']:<10.2f} | {res_b_dict['lm_z_err_mean_cm']:<10.2f} | "
          f"{res_b_dict['time_s']:<7.1f}")
    print(f"\n  创新二·模块2 阴影高度先验贡献:")
    print(f"    lm_err:  {res_a_dict['lm_err_mean_cm']:.2f} → {res_b_dict['lm_err_mean_cm']:.2f}cm "
          f"({'+' if delta_lm>=0 else ''}{delta_lm:.2f}cm, "
          f"{delta_lm/res_a_dict['lm_err_mean_cm']*100:+.1f}%)")
    print(f"    lm_z_err:{res_a_dict['lm_z_err_mean_cm']:.2f} → {res_b_dict['lm_z_err_mean_cm']:.2f}cm "
          f"({'+' if delta_z>=0 else ''}{delta_z:.2f}cm, "
          f"{delta_z/res_a_dict['lm_z_err_mean_cm']*100:+.1f}%)")
    print("=" * 70)
    with open("./innov2_a_vs_b_v2_result.json", "w") as f:
        json.dump({"A_只多视几何": res_a_dict, "B_多视+阴影高度先验": res_b_dict,
                   "delta_lm_cm": delta_lm, "delta_lm_z_cm": delta_z,
                   "n_prior": n_prior}, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()
