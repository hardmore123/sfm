"""
对大论文数据快速跑 3 个代表 BA（V2/V4/V6）。
"""
import os, sys, time, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "BA代码")))

import numpy as np
import ba_optimize as base
import ba_improve as imp
import ba_unified as unif

input_dir = "../BA代码/sim_input_big"
gt_dir = "./big_paper_sim/mixed/gt"

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

# 评估函数
def evaluate(poses_opt, land_opt):
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

results = {}

# V2
print("=" * 60); print("V2 基线"); print("=" * 60)
ba = base.SonarBA(poses6, landmarks, observations, odom_rel,
                  pixel_calib=calib, huber_delta=20.0)
t0 = time.time()
poses_opt, land_opt, res = ba.optimize(verbose=0)
t = time.time() - t0
results["V2"] = {"time_s": t, "rms_px": float(np.sqrt(np.mean(res.fun**2)))}
results["V2"].update(evaluate(poses_opt, land_opt))
print(f"V2: t={t:.1f}s, RMS={results['V2']['rms_px']:.3f}px, "
      f"pos_err={results['V2']['pose_err_mean_cm']:.2f}cm, lm_err={results['V2']['lm_err_mean_cm']:.2f}cm")

# V4
print("=" * 60); print("V4 球坐标+欠约束"); print("=" * 60)
obs_by_lm = imp.build_obs_by_lm(observations)
base_frame = imp.first_base_frame(observations, M)
well_mask, _ = imp.classify_landmarks(poses6, landmarks, obs_by_lm, calib)
ba1 = imp.ImprovedSonarBA(poses6, landmarks, obs_by_lm, observations, odom_rel, calib,
                          well_mask=well_mask, base_frame=base_frame,
                          elev_range=(-0.30, 0.30), elev_grid=61, huber_delta=20.0)
t0 = time.time()
poses_opt, land_opt, _ = ba1.optimize(verbose=0, n_outer=4)
t = time.time() - t0
results["V4"] = {"time_s": t, "n_well": int(well_mask.sum())}
results["V4"].update(evaluate(poses_opt, land_opt))
print(f"V4: t={t:.1f}s, n_well={results['V4']['n_well']}/{M}, "
      f"pos_err={results['V4']['pose_err_mean_cm']:.2f}cm, lm_err={results['V4']['lm_err_mean_cm']:.2f}cm")

# V6
print("=" * 60); print("V6 统一版"); print("=" * 60)
ba2 = unif.UnifiedSonarBA(poses6, landmarks, obs_by_lm, observations, odom_rel, calib,
                          well_mask, base_frame, elev_range=(-0.30, 0.30),
                          gnc_c_px=5.0, huber_delta=20.0)
t0 = time.time()
out = ba2.optimize(use_gnc=True, verbose=False)
t = time.time() - t0
results["V6"] = {"time_s": t, "rms_px": float(np.sqrt(np.mean(ba2.residuals(out["x"])**2))),
                 "n_well": int(well_mask.sum()),
                 "n_outliers": int(out.get("outlier", np.zeros(0)).sum())}
results["V6"].update(evaluate(out["poses"], out["world"]))
print(f"V6: t={t:.1f}s, RMS={results['V6']['rms_px']:.3f}px, n_well={results['V6']['n_well']}, "
      f"outliers={results['V6']['n_outliers']}, pos_err={results['V6']['pose_err_mean_cm']:.2f}cm, "
      f"lm_err={results['V6']['lm_err_mean_cm']:.2f}cm")

# 保存
with open("./all5_big_mixed.json", "w") as f:
    json.dump(results, f, indent=2, ensure_ascii=False)
print("\n=== 大论文数据 3 版本对比 ===")
for k, m in results.items():
    print(f"{k}: t={m['time_s']:.1f}s, pos={m['pose_err_mean_cm']:.2f}cm, lm={m['lm_err_mean_cm']:.2f}cm")
