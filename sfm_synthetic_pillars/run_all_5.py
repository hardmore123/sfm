"""
5 个 BA 版本完整对比
======================

调用 V2 (ba_optimize) / V4 (ba_improve) / V5 (ba_improve34) / V6 (ba_unified)
跑同一份 sim_input 目录，输出 ground truth 对比表。

V1 (12.5新.py) 跳过：数据硬编码，不接受外部输入。
V3 (ba_patent.py) 跳过：算法与 V2 完全相同（见 README.md）。
"""

import os, sys, time, json, argparse
import numpy as np

DEFAULT_BA_DIR = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "BA代码"))
sys.path.insert(0, DEFAULT_BA_DIR)

import ba_optimize as base
import ba_improve as imp
import ba_improve34 as imp34
import ba_unified as unif


def load_and_prepare(input_dir):
    """加载数据 + 通用预处理，返回 (poses6, landmarks, observations, odom_rel, calib, obs_by_lm, base_frame, well_mask, K, M, obs_dict)"""
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
    odom_rel = [(k, np.linalg.inv(poses_mat[k]) @ poses_mat[k + 1])
                for k in range(K - 1)]
    obs_by_lm = imp.build_obs_by_lm(observations)
    base_frame = imp.first_base_frame(observations, M)
    well_mask, _ = imp.classify_landmarks(poses6, landmarks, obs_by_lm, calib)
    obs_dict = {
        "pose": np.array([o[0] for o in observations]),
        "lm":   np.array([o[1] for o in observations]),
        "theta":np.array([o[2] for o in observations]),
        "rho":  np.array([o[3] for o in observations]),
        "beam": np.array([o[4] for o in observations]),
        "range":np.array([o[5] for o in observations]),
    }
    return (poses6, landmarks, observations, odom_rel, calib,
            obs_by_lm, base_frame, well_mask, K, M, obs_dict)


def evaluate(poses_opt, land_opt, gt_dir):
    gt_poses_K = np.load(os.path.join(gt_dir, "poses_keyframe_gt.npy"))
    gt_lm = np.load(os.path.join(gt_dir, "landmarks_gt.npy"))
    err_pos = np.linalg.norm(poses_opt[:, :3] - gt_poses_K[:, :3, 3], axis=1)
    err_lm = np.linalg.norm(land_opt - gt_lm, axis=1)
    err_lm_z = np.abs(land_opt[:, 2] - gt_lm[:, 2])
    return {
        "pose_err_mean_cm": float(err_pos.mean() * 100),
        "pose_err_max_cm":  float(err_pos.max() * 100),
        "lm_err_mean_cm":   float(err_lm.mean() * 100),
        "lm_err_max_cm":    float(err_lm.max() * 100),
        "lm_z_err_mean_cm": float(err_lm_z.mean() * 100),
        "lm_z_err_max_cm":  float(err_lm_z.max() * 100),
    }


def run_v2(input_dir, gt_dir):
    poses6, landmarks, observations, odom_rel, calib, *_ = load_and_prepare(input_dir)
    ba = base.SonarBA(poses6, landmarks, observations, odom_rel,
                      pixel_calib=calib, huber_delta=20.0)
    t0 = time.time()
    poses_opt, land_opt, res = ba.optimize(verbose=0)
    t = time.time() - t0
    return {
        "algo": "V2_baseline", "time_s": t,
        "n_obs": len(observations),
        "initial_rms_px": float(np.sqrt(np.mean(ba.residuals(ba.x0) ** 2))),
        "final_rms_px":   float(np.sqrt(np.mean(res.fun ** 2))),
    }, poses_opt, land_opt


def run_v4(input_dir, gt_dir):
    (poses6, landmarks, observations, odom_rel, calib,
     obs_by_lm, base_frame, well_mask, K, M, obs_dict) = load_and_prepare(input_dir)
    ba = imp.ImprovedSonarBA(poses6, landmarks, obs_by_lm, observations, odom_rel, calib,
                             well_mask=well_mask, base_frame=base_frame,
                             elev_range=(-0.30, 0.30), elev_grid=61, huber_delta=20.0)
    t0 = time.time()
    poses_opt, land_opt, _ = ba.optimize(verbose=0, n_outer=4)
    t = time.time() - t0
    return {
        "algo": "V4_improve_球坐标+欠约束", "time_s": t,
        "n_obs": len(observations),
        "n_well_constrained": int(well_mask.sum()),
        "initial_rms_px": float(np.sqrt(np.mean(imp.compute_metrics(poses6, landmarks, obs_dict, calib)["rms_px"] ** 2))),
        "final_rms_px":   float(np.sqrt(np.mean(imp.compute_metrics(poses_opt, land_opt, obs_dict, calib)["rms_px"] ** 2))),
    }, poses_opt, land_opt


def run_v5(input_dir, gt_dir, use_gnc=True):
    """V5: 解析稀疏 Jacobian + GNC（世界笛卡尔）。"""
    (poses6, landmarks, observations, odom_rel, calib, *_rest) = load_and_prepare(input_dir)
    ba = imp34.SonarBA34(poses6, landmarks, observations, odom_rel, calib)
    t0 = time.time()
    if use_gnc:
        # GNC 流程（与 V5 报告一致）
        poses_opt, land_opt, x_opt, outlier, sigma, hist = ba.solve_gnc(
            c_px=10.0, mu_div=1.4, max_iters=40, inner_nfev=50, verbose=False)
        final_res = ba.residuals(x_opt)
        algo_name = "V5_稀疏+GNC"
        n_out = int(outlier.sum())
    else:
        # 纯解析稀疏
        poses_opt, land_opt, res, dt = ba.solve(jac_mode="analytic", loss="huber", f_scale=20.0)
        final_res = res.fun
        algo_name = "V5_无GNC(解析稀疏)"
        n_out = 0
    t = time.time() - t0
    return {
        "algo": algo_name, "time_s": t,
        "n_obs": len(observations),
        "initial_rms_px": float(np.sqrt(np.mean(ba.residuals(ba.x0) ** 2))),
        "final_rms_px":   float(np.sqrt(np.mean(final_res ** 2))),
        "n_outliers":     n_out,
    }, poses_opt, land_opt


def run_v6(input_dir, gt_dir, use_gnc=True):
    (poses6, landmarks, observations, odom_rel, calib,
     obs_by_lm, base_frame, well_mask, *_rest) = load_and_prepare(input_dir)
    ba = unif.UnifiedSonarBA(
        poses6, landmarks, obs_by_lm, observations, odom_rel, calib,
        well_mask, base_frame, elev_range=(-0.30, 0.30),
        gnc_c_px=5.0, huber_delta=20.0)
    t0 = time.time()
    out = ba.optimize(use_gnc=use_gnc, verbose=False)
    t = time.time() - t0
    return {
        "algo": "V6_统一版" if use_gnc else "V6_无GNC",
        "time_s": t,
        "n_obs": len(observations),
        "n_well_constrained": int(well_mask.sum()),
        "initial_rms_px": float(np.sqrt(np.mean(ba.residuals(ba.x0) ** 2))),
        "final_rms_px":   float(np.sqrt(np.mean(ba.residuals(out["x"]) ** 2))),
        "n_outliers":     int(out.get("outlier", np.zeros(0)).sum()),
    }, out["poses"], out["world"]


# 跑 5 个版本
ALGOS = {
    "V2":       ("V2 基线（世界笛卡尔+Huber）",          run_v2),
    "V4":       ("V4 球坐标+欠约束分类",                 run_v4),
    "V5":       ("V5 解析稀疏+GNC",                    lambda inp, gt: run_v5(inp, gt, use_gnc=True)),
    "V5_nognc": ("V5 解析稀疏（无 GNC）",                lambda inp, gt: run_v5(inp, gt, use_gnc=False)),
    "V6":       ("V6 统一版（球坐标+稀疏+GNC+视场箱）",   run_v6),
    "V6_nognc": ("V6 统一版（无 GNC）",                  lambda inp, gt: run_v6(inp, gt, use_gnc=False)),
}


def run_one_mode(mode_dir, gt_dir, input_dir):
    """对一份 input_dir 跑 5 个 BA 版本。"""
    results = {}
    for key, (label, runner) in ALGOS.items():
        print(f"\n--- {key}: {label} ---")
        try:
            t0 = time.time()
            m, p, l = runner(input_dir, gt_dir)
            t = time.time() - t0
            ev = evaluate(p, l, gt_dir)
            m.update(ev)
            results[key] = m
            print(f"  RMS: {m['initial_rms_px']:.2f} → {m['final_rms_px']:.2f} px, "
                  f"t={m['time_s']:.1f}s, "
                  f"pos_err={m['pose_err_mean_cm']:.2f}cm, "
                  f"lm_err={m['lm_err_mean_cm']:.2f}cm")
        except Exception as e:
            print(f"  [ERROR] {e}")
            import traceback; traceback.print_exc()
            results[key] = {"algo": label, "error": str(e)}
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="BA 输入目录（含 4 件套）")
    ap.add_argument("--gt", required=True, help="ground truth 目录")
    ap.add_argument("--out", default=None, help="结果 JSON 输出路径")
    args = ap.parse_args()

    print(f"输入: {args.input}")
    print(f"ground truth: {args.gt}")
    print("=" * 100)
    results = run_one_mode(None, args.gt, args.input)
    print("\n" + "=" * 100)
    print("=== 5 版本对比 ===")
    print("=" * 100)
    # 打印表格
    print(f"{'版本':<25} | {'初 RMS':<8} | {'末 RMS':<8} | {'t(s)':<7} | "
          f"{'位姿 err':<10} | {'路标 err':<10} | {'Z err':<10} | {'#well'}")
    print("-" * 100)
    for k, m in results.items():
        if "error" in m:
            print(f"{k:<25} | ERROR: {m['error']}")
            continue
        print(f"{m['algo']:<25} | {m['initial_rms_px']:<8.3f} | {m['final_rms_px']:<8.3f} | "
              f"{m['time_s']:<7.1f} | {m['pose_err_mean_cm']:<10.2f} | "
              f"{m['lm_err_mean_cm']:<10.2f} | {m['lm_z_err_mean_cm']:<10.2f} | "
              f"{m.get('n_well_constrained', '-')}")
    print("=" * 100)

    if args.out:
        with open(args.out, "w") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        print(f"\n报告写入: {args.out}")


if __name__ == "__main__":
    main()
