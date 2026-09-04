"""
端到端 BA 测试脚本
===================

对 sim_pipeline.generate() 产出的 input/ 目录运行 BA（V2 / V4 / V5 / V6），
并与 gt/ 目录中的 ground truth 比较，给出量化评估。

用法：
    python run_ba_test.py --input <input_dir> --gt <gt_dir> --algo all
"""

import argparse, os, sys, json, time
import numpy as np

# 切到 BA代码 目录导入模块
DEFAULT_BA_DIR = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "BA代码"))
sys.path.insert(0, DEFAULT_BA_DIR)

import ba_optimize as base


def evaluate(poses_opt, land_opt, gt_dir):
    """与 ground truth 比较，返回评估字典。"""
    gt_poses_K = np.load(os.path.join(gt_dir, "poses_keyframe_gt.npy"))
    gt_lm = np.load(os.path.join(gt_dir, "landmarks_gt.npy"))
    err_pos = np.linalg.norm(poses_opt[:, :3] - gt_poses_K[:, :3, 3], axis=1)
    err_lm = np.linalg.norm(land_opt - gt_lm, axis=1)
    err_lm_z = np.abs(land_opt[:, 2] - gt_lm[:, 2])
    return {
        "pose_trans_err_mean_m": float(err_pos.mean()),
        "pose_trans_err_max_m": float(err_pos.max()),
        "lm_pos_err_mean_m": float(err_lm.mean()),
        "lm_pos_err_max_m": float(err_lm.max()),
        "lm_z_err_mean_m": float(err_lm_z.mean()),
        "lm_z_err_max_m": float(err_lm_z.max()),
    }


def run_v2(input_dir):
    """V2 基线 (世界笛卡尔 + 固定 Huber + 数值稠密)。"""
    poses_mat, frame_ids, landmarks, tracks = base.load_data(input_dir)
    K, M = len(frame_ids), landmarks.shape[0]
    poses6 = np.array([base.matrix_to_pose6(poses_mat[i]) for i in range(K)])
    track_to_lm = base.build_track_to_landmark(poses_mat, frame_ids, landmarks, tracks)
    A, B, C, D = base.calibrate_pixels(tracks)
    fid_to_idx = {int(fid): i for i, fid in enumerate(frame_ids)}
    observations = [(fid_to_idx[fid], track_to_lm[tid], th, rh, bm, rg)
                    for (fid, tid, th, rh, bm, rg) in tracks
                    if fid in fid_to_idx and tid in track_to_lm]
    odom_rel = [(k, np.linalg.inv(poses_mat[k]) @ poses_mat[k + 1])
                for k in range(K - 1)]
    ba = base.SonarBA(poses6, landmarks, observations, odom_rel,
                      pixel_calib=(A, B, C, D), huber_delta=20.0)
    t0 = time.time()
    poses_opt, land_opt, res = ba.optimize(verbose=0)
    t = time.time() - t0
    return {
        "algo": "V2_baseline",
        "time_s": t,
        "n_obs_used": len(observations),
        "n_lm_associated": len(track_to_lm),
        "final_rms": float(np.sqrt(np.mean(res.fun ** 2))),
        "initial_rms": float(np.sqrt(np.mean(ba.residuals(ba.x0) ** 2))),
    }, poses_opt, land_opt


def run_v6(input_dir, gt_dir):
    """V6 统一版（相对球坐标 + 稀疏 + GNC + 视场箱 + 阴影仰角先验接口）。"""
    import ba_improve as imp
    import ba_unified as unif

    poses_mat, frame_ids, landmarks, tracks = base.load_data(input_dir)
    K, M = len(frame_ids), landmarks.shape[0]
    poses6 = np.array([base.matrix_to_pose6(poses_mat[i]) for i in range(K)])
    track_to_lm = base.build_track_to_landmark(poses_mat, frame_ids, landmarks, tracks)
    A, B, C, D = base.calibrate_pixels(tracks)
    fid_to_idx = {int(fid): i for i, fid in enumerate(frame_ids)}
    observations = [(fid_to_idx[fid], track_to_lm[tid], th, rh, bm, rg)
                    for (fid, tid, th, rh, bm, rg) in tracks
                    if fid in fid_to_idx and tid in track_to_lm]
    odom_rel = [(k, np.linalg.inv(poses_mat[k]) @ poses_mat[k + 1])
                for k in range(K - 1)]
    # 分类良/欠约束
    obs_by_lm = imp.build_obs_by_lm(observations)
    base_frame = imp.first_base_frame(observations, M)
    well_mask, _ = imp.classify_landmarks(poses6, landmarks, obs_by_lm, (A, B, C, D))
    calib = (A, B, C, D)
    elev_range = (-0.30, 0.30)
    ba = unif.UnifiedSonarBA(
        poses6, landmarks, obs_by_lm, observations, odom_rel, calib,
        well_mask, base_frame, elev_range=elev_range,
        gnc_c_px=5.0, huber_delta=20.0)
    t0 = time.time()
    out = ba.optimize(use_gnc=True, verbose=False)
    t = time.time() - t0
    return {
        "algo": "V6_unified",
        "time_s": t,
        "n_obs_used": len(observations),
        "n_lm_associated": len(track_to_lm),
        "n_well_constrained": int(well_mask.sum()),
        "final_rms": float(np.sqrt(np.mean(ba.residuals(out["x"]) ** 2))),
        "initial_rms": float(np.sqrt(np.mean(ba.residuals(ba.x0) ** 2))),
        "n_outliers": int(out.get("outlier", np.zeros(0)).sum()),
    }, out["poses"], out["world"]


def run_all(input_dir, gt_dir, algos=("V2", "V6")):
    """依次跑指定算法。"""
    results = {}
    poses_opt_dict = {}
    land_opt_dict = {}
    if "V2" in algos:
        m, p, l = run_v2(input_dir)
        m.update(evaluate(p, l, gt_dir))
        results["V2"] = m
        poses_opt_dict["V2"] = p
        land_opt_dict["V2"] = l
    if "V6" in algos:
        m, p, l = run_v6(input_dir, gt_dir)
        m.update(evaluate(p, l, gt_dir))
        results["V6"] = m
        poses_opt_dict["V6"] = p
        land_opt_dict["V6"] = l
    return results, poses_opt_dict, land_opt_dict


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--gt", required=True)
    ap.add_argument("--algo", default="all", choices=["V2", "V6", "all"])
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    algos = ("V2", "V6") if args.algo == "all" else (args.algo,)
    results, poses, lands = run_all(args.input, args.gt, algos=algos)
    # 打印
    print("\n" + "=" * 78)
    print(f"BA end-to-end test   input={args.input}")
    print("=" * 78)
    for name, m in results.items():
        print(f"\n[{name}] {m['algo']}")
        print(f"  初始 RMS:  {m['initial_rms']:.3f} px")
        print(f"  优化 RMS:  {m['final_rms']:.3f} px")
        print(f"  时间:      {m['time_s']:.2f} s")
        print(f"  关联:      {m['n_lm_associated']} / 120 landmarks")
        print(f"  观测:      {m['n_obs_used']}")
        if "n_well_constrained" in m:
            print(f"  良约束:    {m['n_well_constrained']}")
        print(f"  位姿误差:  mean={m['pose_trans_err_mean_m']*100:.2f}cm, "
              f"max={m['pose_trans_err_max_m']*100:.2f}cm")
        print(f"  路标误差:  mean={m['lm_pos_err_mean_m']*100:.2f}cm, "
              f"max={m['lm_pos_err_max_m']*100:.2f}cm")
        print(f"  路标 Z 误差: mean={m['lm_z_err_mean_m']*100:.2f}cm, "
              f"max={m['lm_z_err_max_m']*100:.2f}cm")
    print("=" * 78)
    if args.out:
        with open(args.out, "w") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        print(f"\n报告已写入: {args.out}")


if __name__ == "__main__":
    main()
