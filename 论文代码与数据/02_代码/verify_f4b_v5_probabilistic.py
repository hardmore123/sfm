# -*- coding: utf-8 -*-
"""
⚠️ 失败实验 — 保留作为教训, 非有效方法 ⚠️
F-4b v5(概率占据栅格): 失败, E=0.99(从0.53变差)
================================================
2026-10-13声呐专家诊断:

失败原因:
  阴影远端D_e=12.86m远超目标远边缘D_t+r=10.85m
  (阴影投射在海底上, 不是目标水平边界)
  用D_e作前向约束把目标本身也删了(V_recon=12L, FN=1352)
  
声呐专家判断:
  阴影远端=海底上阴影结束位置(目标高度投影), 不是目标水平边界
  概率方法在这里从根本上是错的——占据观测只在第一回波前沿,
  不能代表整个列
  
正确方法: 见 verify_f4b_v5_shape_prior.py(形状先验约束)

本文件保留作为失败教训, 不用于论文结论, 不计入reproduce_all
"""
  1. 阴影远端前向约束(物理直接):
     阴影远端rho_end的D_e = sqrt(rho_end² - z_s²)是目标远边缘的水平距离
     → 目标前方D_far以外(D_e < x)的体素可标为free(阴影末端之后=有回波=free)
     → 消除前方膨胀1038体素
  
  2. 概率占据栅格(贝叶斯更新, 文献[8]MRF):
     硬雕刻alive=False改为P(occ)更新, 未观测区维持先验(非直接保留)
     → 解决"非黑即白"问题
  
  3. 高度约束用反演h_inv(已实现) + 紧包围盒上界(消除上方膨胀)

⚠️ 实际结果: 全部失败(E=0.99), 详见上方失败诊断 ⚠️
"""
import numpy as np
import os, sys, json
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
DELIV = os.path.dirname(HERE)

from verify_f4b_carve_precision import (
    load_scene, voxel_carve_both, poses6_to_se3, gt_occupancy_cylinder,
    run_scene_optimized
)
from shadow_f8_fixed import measure_shadow_far_edge


def compute_shadow_far_edge_per_frame(shadow_masks, floor_masks, range_axis, poses_se3):
    """
    逐帧计算阴影远端D_e(目标远边缘水平距离)
    
    理论: 阴影远端rho_end → D_e = sqrt(rho_end² - z_s²)
    D_e是目标远边缘的水平距离, 目标前方D_e以外的体素可标为free
    
    返回: (K,) 每帧的D_e数组(nan=无阴影)
    """
    K = shadow_masks.shape[0]
    W = shadow_masks.shape[2]
    D_e_per_frame = np.full(K, np.nan)
    
    for i in range(K):
        z_s_i = poses_se3[i, 2, 3]  # 声呐高度
        # 对每列量测阴影远端
        rho_ends = []
        for c in range(W):
            if not shadow_masks[i, :, c].any():
                continue
            rho_end = measure_shadow_far_edge(
                shadow_masks[i, :, c], floor_masks[i, :, c], range_axis
            )
            if np.isfinite(rho_end):
                rho_ends.append(rho_end)
        
        if len(rho_ends) > 0:
            # 取中位数(鲁棒)
            rho_end_med = np.median(rho_ends)
            D_e = np.sqrt(max(rho_end_med**2 - z_s_i**2, 0))
            D_e_per_frame[i] = D_e
    
    return D_e_per_frame


def run_scene_probabilistic(scene_name, voxel_size=0.05, p_free_threshold=0.5,
                             p_prior=0.5, p_occupied_obs=0.85, p_free_obs=0.15,
                             use_frontier_constraint=True):
    """
    F-4b v5: 概率占据栅格 + 阴影远端前向约束
    
    改进(相比v4):
      1. 阴影远端前向约束: 目标前方D_e以外标为free(消除前方膨胀)
      2. 概率更新: 硬删除改为贝叶斯更新(未观测区维持先验)
      3. 高度约束: 用反演h_inv(已实现)
    
    贝叶斯更新(log-odds形式):
      l(p) = log(p/(1-p))  先验log-odds
      有回波观测: l += log(p_occupied_obs / (1-p_occupied_obs))
      无回波+在视场内: l += log(p_free_obs / (1-p_free_obs))
      阴影远端前方: l += log(p_free_obs / (1-p_free_obs))  (强free)
      P(occ) = sigmoid(l) > p_free_threshold → 占据
    """
    meta, poses, target_masks, shadow_masks, unlit_masks = load_scene(scene_name)
    
    h_gt = meta["config"]["h_m"]
    D_t = meta["config"]["D_t_m"]
    z_s = meta["config"]["z_s_m"]
    r_cyl = 0.25
    H_bins = meta["config"]["range_bin_count"]
    W_beams = meta["config"]["beam_count"]
    rho_max = meta["config"]["rho_max_m"]
    rho_min = meta["config"]["range_min_m"]
    fov_elev = np.deg2rad(7.5)
    fov_azim = np.deg2rad(meta["config"].get("fov_azim_deg", 30) / 2)
    range_axis = np.linspace(rho_min, rho_max, H_bins)
    beam_axis = np.linspace(-fov_azim, fov_azim, W_beams)
    
    poses_se3 = poses6_to_se3(poses)
    pillar_top = np.array([D_t, 0, h_gt])
    
    # 从measurements获取反演h_inv
    meas_path = os.path.join(DELIV, "04_数据", "scene_set_main_f8", scene_name, "innov2", "measurements.npy")
    if os.path.exists(meas_path):
        meas = np.load(meas_path)
        h_inv = float(np.mean(meas[:, 5]))
    else:
        print(f"  [WARN] {scene_name}: 无measurements.npy")
        h_inv = h_gt
    
    # 紧包围盒
    lo = np.array([D_t - 0.5, -0.5, -0.05])
    hi = np.array([D_t + 0.5, 0.5, h_gt + 0.15])
    nx, ny, nz = np.ceil((hi - lo) / voxel_size).astype(int)
    xs = lo[0] + (np.arange(nx) + 0.5) * voxel_size
    ys = lo[1] + (np.arange(ny) + 0.5) * voxel_size
    zs = lo[2] + (np.arange(nz) + 0.5) * voxel_size
    X, Y, Z = np.meshgrid(xs, ys, zs, indexing='ij')
    centers = np.stack([X.ravel(), Y.ravel(), Z.ravel()], 1)
    voxel_vol = voxel_size**3
    N = len(centers)
    
    # ===== 贝叶斯占据栅格(log-odds) =====
    # 先验log-odds = log(p_prior / (1-p_prior))
    l_prior = np.log(p_prior / (1 - p_prior))
    log_odds = np.full(N, l_prior)
    
    # 观测log-odds
    l_occ = np.log(p_occupied_obs / (1 - p_occupied_obs))  # 有回波→占据
    l_free = np.log(p_free_obs / (1 - p_free_obs))        # 无回波→自由
    
    # 逐帧贝叶斯更新
    for n in range(poses_se3.shape[0]):
        R = poses_se3[n, :3, :3]
        t = poses_se3[n, :3, 3]
        Pb = (R.T @ (centers - t).T).T
        rho = np.linalg.norm(Pb, axis=1)
        theta = np.arctan2(Pb[:, 1], Pb[:, 0])
        elev = np.arctan2(Pb[:, 2], np.linalg.norm(Pb[:, :2], axis=1))
        i_theta = np.round((theta - beam_axis[0]) / (beam_axis[1] - beam_axis[0])).astype(int)
        
        dr = range_axis[1] - range_axis[0]
        in_fov = (np.abs(elev) <= fov_elev) & (rho >= range_axis[0]) & (rho <= range_axis[-1]) \
            & (np.abs(theta) <= fov_azim) & (i_theta >= 0) & (i_theta < W_beams)
        
        # 对每个beam列: 有回波→occ, 无回波→free
        for th_idx in np.unique(i_theta[in_fov]):
            col = in_fov & (i_theta == th_idx)
            rows = np.where(target_masks[n, :, th_idx])[0]
            if len(rows) == 0:
                # 无回波波束 → 视场内全free
                log_odds[col] += l_free
            else:
                rho_lead = range_axis[rows.min()]
                # 前沿之前 = free
                free_mask = col & (rho < rho_lead - dr / 2)
                log_odds[free_mask] += l_free
                # 有回波区 = occupied (目标高光)
                # 不在这里加l_occ(避免把声呐波束宽度内的所有体素标occ)
                # 仅前沿位置标occ
                occ_mask = col & (np.abs(rho - rho_lead) < dr)
                log_odds[occ_mask] += l_occ
    
    # ===== 阴影远端前向约束(新改进) =====
    if use_frontier_constraint:
        # 从floor_masks获取(若有), 否则用shadow_masks
        floor_masks = None
        # 逐帧计算D_e(阴影远端水平距离)
        # 加载floor_masks
        obs_dir = os.path.join(DELIV, "04_数据", "scene_set_main_f8", scene_name, "obs")
        floor_path = os.path.join(obs_dir, "floor_masks.npy")
        if os.path.exists(floor_path):
            floor_masks = np.load(floor_path)
        else:
            # 用unlit_masks的补集作为floor近似
            floor_masks = ~unlit_masks
        
        D_e_per_frame = compute_shadow_far_edge_per_frame(
            shadow_masks, floor_masks, range_axis, poses_se3
        )
        valid_D_e = D_e_per_frame[np.isfinite(D_e_per_frame)]
        if len(valid_D_e) > 0:
            D_e_med = np.median(valid_D_e)
            # 目标前方D_e以外 → free(强约束)
            # D_e是目标远边缘水平距离, x > D_e + r_cyl(柱体远边缘)的体素 = free
            x_world = centers[:, 0]
            front_free = x_world > (D_e_med + r_cyl * 0.5)
            log_odds[front_free] += l_free * 3  # 强free(3倍权重)
            print(f"  阴影远端前向约束: D_e={D_e_med:.3f}m, 前方>{D_e_med+r_cyl*0.5:.3f}m标free")
    
    # ===== 高度约束(反演h_inv) =====
    above_h = centers[:, 2] > h_inv
    log_odds[above_h] += l_free * 2  # 强free(2倍)
    
    # 海底以下
    below_floor = centers[:, 2] < 0
    log_odds[below_floor] += l_free * 5  # 极强free
    
    # ===== 阈值判定 =====
    p_occ = 1.0 / (1.0 + np.exp(-log_odds))
    alive = p_occ > p_free_threshold
    
    gt_occ = gt_occupancy_cylinder(pillar_top, centers, r_cyl, h_gt)
    
    V_r = alive.sum() * voxel_vol
    V_g = gt_occ.sum() * voxel_vol
    V_i = (alive & gt_occ).sum() * voxel_vol
    denom = V_r + V_g - V_i
    E = (V_r + V_g - 2*V_i) / max(denom, 1e-12)
    
    # 分析假阳性/假阴性
    false_pos = (alive & ~gt_occ).sum()
    false_neg = (~alive & gt_occ).sum()
    
    print(f"  {scene_name:<22} vs={voxel_size:.2f} +概率栅格+前向约束 "
          f"E={E:.4f} V_r={V_r*1000:.1f}L V_g={V_g*1000:.1f}L V∩={V_i*1000:.1f}L "
          f"FP={false_pos} FN={false_neg} "
          f"{'✅达标' if E<=0.30 else '⚠️未达标'}")
    
    return {
        "scene": scene_name, "voxel_size": voxel_size,
        "mode": "probabilistic+frontier_constraint",
        "h_inv": round(float(h_inv), 4),
        "E": round(float(E), 4),
        "V_recon_L": round(float(V_r*1000), 1),
        "V_gt_L": round(float(V_g*1000), 1),
        "V_intersect_L": round(float(V_i*1000), 1),
        "false_positive": int(false_pos),
        "false_negative": int(false_neg),
        "passed": bool(E <= 0.30),
    }


def main():
    print("=" * 70)
    print("F-4b v5: 概率占据栅格 + 阴影远端前向约束")
    print("=" * 70)
    print()
    print("改进分析:")
    print("  v4: E=0.53, 假阳性240L(前方130L+上方49L+后方45L)")
    print("  v5: +阴影远端前向约束(消除前方130L) + 概率更新(软化非黑即白)")
    print("  目标: E≤0.30")
    print()
    
    scenes = ["M1_well_constrained", "M3_envelope_inside", "M4_envelope_outside"]
    results = []
    for s in scenes:
        print(f"\n--- {s} ---")
        for vs in [0.05, 0.03]:
            r = run_scene_probabilistic(s, voxel_size=vs)
            results.append(r)
    
    print("\n" + "=" * 70)
    print("F-4b v5 vs v4 对比")
    print("=" * 70)
    print(f"{'场景':<22} {'v4 E':<8} {'v5 E':<8} {'改进':<8} {'v5 V_recon':<12} {'v5 FP':<8}")
    for r in results:
        if r["voxel_size"] == 0.05:
            scene = r["scene"]
            v4_E = 0.53  # v4 M1的E
            v5_E = r["E"]
            print(f"{scene:<22} {v4_E:<8.4f} {v5_E:<8.4f} {v4_E-v5_E:<8.4f} "
                  f"{r['V_recon_L']:<12.1f} {r['false_positive']:<8}")
    
    best = min(results, key=lambda x: x["E"])
    print(f"\n最佳: {best['scene']} vs={best['voxel_size']} E={best['E']} "
          f"{'✅达标' if best['passed'] else '⚠️未达标'}")
    
    # 保存报告
    report_path = os.path.join(HERE, "f4b_v5_probabilistic_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump({"results": results, "best": best}, f, indent=2, ensure_ascii=False)
    print(f"\n报告已保存: {report_path}")


if __name__ == "__main__":
    main()
