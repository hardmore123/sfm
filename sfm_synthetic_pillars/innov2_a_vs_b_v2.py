"""
大论文 6.1 主打实验 V2 版本（A vs B）
=====================================

A. V2 + 无阴影高度先验（纯多视几何）
B. V2 + 创新二·模块2 阴影高度先验（世界笛卡尔 z 软约束）

用 V2（世界笛卡尔）作为基线，因为：
  - V4/V6 球坐标参数化下 lm 没有"全局 z"概念
  - V2 的 lm 状态就是 (x, y, z) 笛卡尔，加 z 软约束最直接
  - 之前实验证明 V2 在 mixed 模式达到 1.98cm 位姿 / 6.08cm 路标精度

实验结果应揭示：阴影高度先验对路标 Z 误差的贡献。
"""
import os, sys, time, json
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sonarba_with_shadow_prior import SonarBAWithShadowPrior, run_v2_with_shadow_prior


def aggregate_height_to_landmarks(
    h_inv, sigma_h, observations, M, H, W
):
    """
    把像素级反演结果聚合到 landmark 级。
    对每个 landmark，收集其所有观测 (frame, beam, range) 处的反演值 → 中位
    """
    elev_prior = np.full(M, np.nan)
    sigma_prior = np.full(M, np.inf)
    lm_h = {j: [] for j in range(M)}
    lm_s = {j: [] for j in range(M)}
    for o in observations:
        pi, j, th, rh, bm, rg = o
        ri = int(np.clip(round(rg), 0, H - 1))
        bi = int(np.clip(round(bm), 0, W - 1))
        if np.isfinite(h_inv[pi, ri, bi]) and 0 < h_inv[pi, ri, bi] < 5.0:
            lm_h[j].append(h_inv[pi, ri, bi])
            lm_s[j].append(sigma_h[pi, ri, bi])
    for j in range(M):
        if lm_h[j]:
            elev_prior[j] = float(np.median(lm_h[j]))
            sigma_prior[j] = float(np.median(lm_s[j]))
    return elev_prior, sigma_prior


def main():
    import ba_optimize as base
    mode = "mixed"
    input_dir = "../BA代码/sim_input_big"
    gt_dir = f"./big_paper_sim/{mode}/gt"
    inv2_dir = f"./big_paper_sim/{mode}/innovation2"

    h_inv = np.load(os.path.join(inv2_dir, "height_inverted.npy"))
    sigma_h = np.load(os.path.join(inv2_dir, "sigma_height.npy"))

    # 准备 observations
    poses_mat, frame_ids, landmarks, tracks = base.load_data(input_dir)
    K, M = len(frame_ids), landmarks.shape[0]
    track_to_lm = base.build_track_to_landmark(poses_mat, frame_ids, landmarks, tracks)
    fid_to_idx = {int(fid): i for i, fid in enumerate(frame_ids)}
    observations = [(fid_to_idx[fid], track_to_lm[tid], th, rh, bm, rg)
                    for (fid, tid, th, rh, bm, rg) in tracks
                    if fid in fid_to_idx and tid in track_to_lm]
    N, H, W = h_inv.shape
    print(f"数据: K={K} 关键帧, M={M} landmark, H×W={H}×{W} 像素")

    # 聚合到 lm 级
    z_prior, sigma_z = aggregate_height_to_landmarks(h_inv, sigma_h, observations, M, H, W)
    n_prior = int(np.sum(np.isfinite(z_prior)))
    print(f"  阴影高度先验覆盖: {n_prior}/{M} 个 landmark")
    if n_prior > 0:
        zp = z_prior[np.isfinite(z_prior)]
        sp = sigma_z[np.isfinite(sigma_z)]
        print(f"  z_prior: mean={np.mean(zp):.2f}m, median={np.median(zp):.2f}m, "
              f"range=[{zp.min():.2f}, {zp.max():.2f}]m")
        print(f"  sigma_z: median={np.median(sp):.3f}m")

    # ---- A: V2 无先验 ----
    print("\n=== A. V2 + 无阴影高度先验（纯多视几何） ===")
    res_a = run_v2_with_shadow_prior(input_dir, gt_dir,
                                      z_prior=np.full(M, np.nan),
                                      sigma_z=np.full(M, np.inf),
                                      w_z=0.0,
                                      label="A_only_multiview")
    print(f"  t={res_a['time_s']:.1f}s, RMS={res_a['rms_px']:.3f}px, "
          f"pos_err={res_a['pose_err_mean_cm']:.2f}cm, "
          f"lm_err={res_a['lm_err_mean_cm']:.2f}cm, "
          f"lm_z_err={res_a['lm_z_err_mean_cm']:.2f}cm")

    # ---- B: V2 + 阴影高度先验 ----
    print("\n=== B. V2 + 阴影高度先验（创新二·模块2 注入） ===")
    res_b = run_v2_with_shadow_prior(input_dir, gt_dir,
                                      z_prior=z_prior, sigma_z=sigma_z,
                                      w_z=10.0,
                                      label="B_multiview_plus_shadow_prior")
    print(f"  t={res_b['time_s']:.1f}s, RMS={res_b['rms_px']:.3f}px, "
          f"pos_err={res_b['pose_err_mean_cm']:.2f}cm, "
          f"lm_err={res_b['lm_err_mean_cm']:.2f}cm, "
          f"lm_z_err={res_b['lm_z_err_mean_cm']:.2f}cm")

    # ---- 对比 ----
    print("\n" + "=" * 70)
    print("6.1 仰角来源消融结果")
    print("=" * 70)
    print(f"{'配置':<35} | {'pos (cm)':<10} | {'lm (cm)':<10} | {'z (cm)':<10} | {'RMS':<8}")
    print("-" * 80)
    print(f"{'A 只多视几何':<35} | {res_a['pose_err_mean_cm']:<10.2f} | "
          f"{res_a['lm_err_mean_cm']:<10.2f} | {res_a['lm_z_err_mean_cm']:<10.2f} | {res_a['rms_px']:<8.3f}")
    print(f"{'B 多视+阴影高度先验':<35} | {res_b['pose_err_mean_cm']:<10.2f} | "
          f"{res_b['lm_err_mean_cm']:<10.2f} | {res_b['lm_z_err_mean_cm']:<10.2f} | {res_b['rms_px']:<8.3f}")
    delta = res_a['lm_z_err_mean_cm'] - res_b['lm_z_err_mean_cm']
    delta_lm = res_a['lm_err_mean_cm'] - res_b['lm_err_mean_cm']
    print(f"\n  创新二·模块2 阴影高度先验改进:")
    print(f"    lm_err 减少: {delta_lm:.2f}cm ({delta_lm/res_a['lm_err_mean_cm']*100:+.1f}%)")
    print(f"    lm_z_err 减少: {delta:.2f}cm ({delta/res_a['lm_z_err_mean_cm']*100:+.1f}%)")
    print("=" * 70)

    # 保存
    with open("./innov2_a_vs_b_v2_result.json", "w") as f:
        json.dump({"A_只多视几何": res_a, "B_多视+阴影高度先验": res_b,
                   "delta_lm_cm": delta_lm, "delta_lm_z_cm": delta}, f, indent=2, ensure_ascii=False)
    return res_a, res_b


if __name__ == "__main__":
    main()
