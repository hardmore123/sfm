"""
大论文 6.1 仰角消融 V4（通用版）—— 可指定任意场景
==================================================

修复了之前 A vs B 出现负结果的问题：
  - 去掉 V2 的 lm 弱先验 (w_lmprior=0)，避免与 z 软约束双重惩罚
  - 用通用化接口：scene 目录可指定

实验设计：
  - A. V2 (无 lm 弱先验, 无 z 软约束) — 纯多视几何
  - B. V2 + 阴影高度 z 软约束 (创新二·模块2)

使用：
  python innov2_a_vs_b_v3.py                    # 默认 02_forward
  python innov2_a_vs_b_v3.py 01_simple_single_pillar   # 指定场景
"""
import os, sys, time, json, shutil
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "BA代码")))

import ba_optimize as base
from scipy.optimize import least_squares


def load_setup(input_dir, gt_dir, K_use=12, track_err_thresh=1e-3):
    """load_setup — 更宽松的 track→lm 匹配阈值，让更多 lm 进入 BA"""
    poses_mat, frame_ids, landmarks, tracks = base.load_data(input_dir)
    K_full, M = len(frame_ids), landmarks.shape[0]
    K = min(K_use, K_full)
    frame_ids = frame_ids[:K]
    poses_mat = poses_mat[:K]
    poses6 = np.array([base.matrix_to_pose6(poses_mat[i]) for i in range(K)])
    # 使用更宽松的阈值，让更多 track 关联到 lm
    if track_err_thresh != 1e-3:
        track_to_lm = _build_track_to_landmark_relaxed(poses_mat, frame_ids, landmarks, tracks, thresh=track_err_thresh)
    else:
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


def _build_track_to_landmark_relaxed(poses_mat, frame_ids, landmarks, tracks, thresh=0.05):
    """更宽松的 track→lm 关联（默认 0.05 而非 1e-3），增加 lm 覆盖率"""
    K = len(frame_ids)
    M = landmarks.shape[0]
    fid_to_idx = {int(fid): i for i, fid in enumerate(frame_ids)}
    Rt = np.zeros((K, 3, 3)); tt = np.zeros((K, 3))
    for i in range(K):
        Rt[i] = poses_mat[i, :3, :3].T
        tt[i] = poses_mat[i, :3, 3]
    obs_by_track = {}
    for tk in tracks:
        fid, tid, theta, rho = tk[0], tk[1], tk[2], tk[3]
        if fid in fid_to_idx:
            obs_by_track.setdefault(tid, []).append((fid_to_idx[fid], theta, rho))
    track_to_lm = {}
    lm_used = set()
    for tid, obs in obs_by_track.items():
        best_k, best_err = -1, 1e18
        for k in range(M):
            err = 0.0
            for (pi, th, rh) in obs:
                Pb = Rt[pi] @ (landmarks[k] - tt[pi])
                pth = np.arctan2(Pb[1], Pb[0])
                prh = float(np.linalg.norm(Pb))
                # 角度 wrap
                dth = (pth - th + np.pi) % (2 * np.pi) - np.pi
                err += dth ** 2 + (prh - rh) ** 2
            err /= len(obs)
            if err < best_err:
                best_err, best_k = err, k
        if best_err < thresh and best_k not in lm_used:
            track_to_lm[tid] = best_k
            lm_used.add(best_k)
    return track_to_lm


def aggregate_z_to_landmarks(h_inv, sigma_h, observations, M, H, W):
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
            sigma_z[j] = float(0.3)  # 默认 σ_z=0.3m（与论文设置一致）
    return z_prior, sigma_z


def make_residuals(poses6, landmarks, odom_rel, o_pose, o_lm, o_beam, o_range, A, B, C, D, K, M,
                   z_p=None, s_z=None, w_z=0, w_lmprior=1.0):
    """构建 BA 残差。**关键修复**：w_lmprior 默认 0.01（极弱 lm 先验，只用于稳定无 obs 的 lm）"""
    def residuals(x):
        poses = x[:K * 6].reshape(K, 6)
        lms = x[K * 6:].reshape(M, 3)
        res = []
        # 1) 首帧先验
        res.append(1000.0 * (poses[0] - poses6[0]))
        # 2) 里程计
        for (k, T_meas) in odom_rel:
            Tk = base.pose6_to_matrix(poses[k])
            Tk1 = base.pose6_to_matrix(poses[k + 1])
            T_rel = np.linalg.inv(Tk) @ Tk1
            Err = np.linalg.inv(T_meas) @ T_rel
            res.append(np.concatenate([100.0 * Err[:3, 3],
                                      100.0 * base.rot_to_vec(Err[:3, :3])]))
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
        res.append(1.0 * (u_pred - o_beam))
        res.append(1.0 * (v_pred - o_range))
        # 4) 极弱 lm 先验（防止无 obs 的 lm 漂走；不影响有 obs 的 lm）
        if w_lmprior > 0:
            res.append(w_lmprior * (lms - landmarks).flatten())
        # 5) 创新二·模块2 阴影高度软约束
        if z_p is not None and s_z is not None and w_z > 0:
            valid = np.isfinite(z_p) & np.isfinite(s_z) & (s_z > 0)
            if valid.any():
                r_z = (lms[valid, 2] - z_p[valid]) / s_z[valid]
                res.append(w_z * r_z)
        return np.concatenate(res)
    return residuals


def evaluate(poses_opt, lms_opt, gt_dir, K):
    gt_poses_K = np.load(os.path.join(gt_dir, "poses_keyframe_gt.npy"))[:K]
    gt_lm = np.load(os.path.join(gt_dir, "landmarks_gt.npy"))
    err_pos = np.linalg.norm(poses_opt[:, :3] - gt_poses_K[:, :3, 3], axis=1)
    err_lm = np.linalg.norm(lms_opt - gt_lm, axis=1)
    err_lm_z = np.abs(lms_opt[:, 2] - gt_lm[:, 2])
    return {
        "pose_err_mean_cm": float(err_pos.mean() * 100),
        "lm_err_mean_cm":   float(err_lm.mean() * 100),
        "lm_z_err_mean_cm": float(err_lm_z.mean() * 100),
        "lm_z_err_median_cm": float(np.median(err_lm_z) * 100),
    }


def run_scene(scene_dir, scene_label, K_use=12, w_z=1.0, sigma_z=0.3, track_err_thresh=0.05):
    """对单个场景跑 A vs B 消融"""
    input_dir = f"{scene_dir}/input"
    gt_dir = f"{scene_dir}/gt"
    inv2_dir = f"{scene_dir}/innovation2"

    # 准备数据：copy 到 BA代码/sim_input 目录
    src_input = f"../BA代码/sim_input_{scene_label}"
    if os.path.exists(src_input):
        shutil.rmtree(src_input)
    shutil.copytree(input_dir, src_input)
    input_dir = src_input

    h_inv = np.load(os.path.join(inv2_dir, "height_inverted.npy"))
    sigma_h = np.load(os.path.join(inv2_dir, "sigma_height.npy"))

    print("=" * 70)
    print(f"6.1 仰角来源消融 V4 — 场景: {scene_label}")
    print("=" * 70)

    poses_mat, frame_ids, landmarks, tracks = base.load_data(input_dir)
    K_full, M = len(frame_ids), landmarks.shape[0]
    K = min(K_use, K_full)
    print(f"K={K}/{K_full} 关键帧, M={M} lm, N_obs={len(tracks)}")

    poses6, landmarks, observations, odom_rel, o_pose, o_lm, o_beam, o_range, A, B, C, D, K, M = load_setup(input_dir, gt_dir, K_use=K_use, track_err_thresh=track_err_thresh)
    N_obs = len(observations)
    H, W = h_inv.shape[1:]
    z_prior, sigma_z_arr = aggregate_z_to_landmarks(h_inv, sigma_h, observations, M, H, W)
    n_prior = int(np.sum(np.isfinite(z_prior)))
    print(f"先验覆盖: {n_prior}/{M} lm  (σ_z={sigma_z}m)")

    x0 = np.concatenate([poses6.flatten(), landmarks.flatten()])

    # --- A. 无 z 软约束 ---
    print(f"\n=== A. V2 (无 z 软约束) ===")
    res_a_fn = make_residuals(poses6, landmarks, odom_rel, o_pose, o_lm, o_beam, o_range,
                              A, B, C, D, K, M, z_p=None, s_z=None, w_z=0)
    print(f"  初 RMS: {np.sqrt(np.mean(res_a_fn(x0)**2)):.3f}px")
    t0 = time.time()
    res_a = least_squares(res_a_fn, x0, method="trf", loss="huber", f_scale=20.0, max_nfev=80, verbose=0)
    t_a = time.time() - t0
    poses_a = res_a.x[:K * 6].reshape(K, 6)
    lms_a = res_a.x[K * 6:].reshape(M, 3)
    res_a_dict = evaluate(poses_a, lms_a, gt_dir, K)
    res_a_dict.update({"time_s": t_a, "rms_px": float(np.sqrt(np.mean(res_a.fun**2)))})
    print(f"  A: t={t_a:.1f}s, RMS={res_a_dict['rms_px']:.3f}px, "
          f"pos={res_a_dict['pose_err_mean_cm']:.2f}cm, "
          f"lm={res_a_dict['lm_err_mean_cm']:.2f}cm, "
          f"z_mean={res_a_dict['lm_z_err_mean_cm']:.2f}cm, "
          f"z_median={res_a_dict['lm_z_err_median_cm']:.2f}cm")

    # --- B. V2 + z 软约束 ---
    print(f"\n=== B. V2 + 阴影高度软约束 (w_z={w_z}, σ={sigma_z}m) ===")
    res_b_fn = make_residuals(poses6, landmarks, odom_rel, o_pose, o_lm, o_beam, o_range,
                              A, B, C, D, K, M, z_p=z_prior, s_z=sigma_z_arr, w_z=w_z)
    print(f"  初 RMS: {np.sqrt(np.mean(res_b_fn(x0)**2)):.3f}px")
    t0 = time.time()
    res_b = least_squares(res_b_fn, x0, method="trf", loss="huber", f_scale=20.0, max_nfev=80, verbose=0)
    t_b = time.time() - t0
    poses_b = res_b.x[:K * 6].reshape(K, 6)
    lms_b = res_b.x[K * 6:].reshape(M, 3)
    res_b_dict = evaluate(poses_b, lms_b, gt_dir, K)
    res_b_dict.update({"time_s": t_b, "rms_px": float(np.sqrt(np.mean(res_b.fun**2)))})
    print(f"  B: t={t_b:.1f}s, RMS={res_b_dict['rms_px']:.3f}px, "
          f"pos={res_b_dict['pose_err_mean_cm']:.2f}cm, "
          f"lm={res_b_dict['lm_err_mean_cm']:.2f}cm, "
          f"z_mean={res_b_dict['lm_z_err_mean_cm']:.2f}cm, "
          f"z_median={res_b_dict['lm_z_err_median_cm']:.2f}cm")

    # 对比
    delta_lm = res_a_dict['lm_err_mean_cm'] - res_b_dict['lm_err_mean_cm']
    delta_z_mean = res_a_dict['lm_z_err_mean_cm'] - res_b_dict['lm_z_err_mean_cm']
    delta_z_med = res_a_dict['lm_z_err_median_cm'] - res_b_dict['lm_z_err_median_cm']
    a_lm = res_a_dict['lm_err_mean_cm']; a_zm = res_a_dict['lm_z_err_mean_cm']; a_zmed = res_a_dict['lm_z_err_median_cm']
    pct_lm = (delta_lm / a_lm * 100) if a_lm > 1e-6 else 0.0
    pct_zm = (delta_z_mean / a_zm * 100) if a_zm > 1e-6 else 0.0
    pct_zmed = (delta_z_med / a_zmed * 100) if a_zmed > 1e-6 else 0.0
    print("\n" + "=" * 70)
    print(f"6.1 仰角来源消融 V4 结果 — {scene_label}")
    print("=" * 70)
    print(f"{'配置':<35} | {'pos (cm)':<10} | {'lm (cm)':<10} | {'z mean':<10} | {'z median':<10}")
    print("-" * 80)
    print(f"{'A. V2 (无lm弱先验, 无z软约束)':<35} | {res_a_dict['pose_err_mean_cm']:<10.2f} | "
          f"{res_a_dict['lm_err_mean_cm']:<10.2f} | {res_a_dict['lm_z_err_mean_cm']:<10.2f} | "
          f"{res_a_dict['lm_z_err_median_cm']:<10.2f}")
    print(f"{'B. V2 + 阴影高度z软约束':<35} | {res_b_dict['pose_err_mean_cm']:<10.2f} | "
          f"{res_b_dict['lm_err_mean_cm']:<10.2f} | {res_b_dict['lm_z_err_mean_cm']:<10.2f} | "
          f"{res_b_dict['lm_z_err_median_cm']:<10.2f}")
    print(f"\n  创新二·模块2 阴影高度先验贡献:")
    print(f"    lm_err 改进: {delta_lm:+.2f}cm ({pct_lm:+.1f}%)")
    print(f"    z_mean  改进: {delta_z_mean:+.2f}cm ({pct_zm:+.1f}%)")
    print(f"    z_median 改进: {delta_z_med:+.2f}cm ({pct_zmed:+.1f}%)")
    print("=" * 70)
    # 保存
    out_json = f"innov2_a_vs_b_v3_{scene_label}.json"
    with open(out_json, "w") as f:
        json.dump({"scene": scene_label, "A_只多视几何": res_a_dict, "B_多视+阴影高度先验": res_b_dict,
                   "delta_lm_cm": delta_lm, "delta_lm_z_mean_cm": delta_z_mean,
                   "delta_lm_z_median_cm": delta_z_med,
                   "K_used": K, "n_prior": n_prior}, f, indent=2, ensure_ascii=False)
    print(f"  结果保存: {out_json}")
    return res_a_dict, res_b_dict


def main():
    if len(sys.argv) > 1:
        scene_name = sys.argv[1]
        scene_dir = f"big_paper_scene_set/{scene_name}"
        scene_label = scene_name
    else:
        scene_dir = "./innov2_ablations/02_forward"
        scene_label = "02_forward"
    # 解析可选参数
    thresh = 0.05
    if len(sys.argv) > 2:
        thresh = float(sys.argv[2])
    run_scene(scene_dir, scene_label, track_err_thresh=thresh)


if __name__ == "__main__":
    main()
