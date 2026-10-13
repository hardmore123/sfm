# -*- coding: utf-8 -*-
"""
F-4b v2: 雕刻精度达标——分析过度膨胀根因 + 改进方案
======================================================
F-4b v1结果: E=0.79-0.84, V_recon~800L vs V_gt~170L → 过度膨胀5×
根因: 纯空间雕刻只能删除"被声束观测到为自由"的体素,
      但声束无法观测目标后方/侧方的自由空间 → 这些体素保留→过度膨胀

改进方案:
  A. 收紧体素包围盒(只罩目标+小余量, 不罩目标后方)
  B. 用shadow_masks提供额外自由约束(阴影=声呐看不到→该方向自由)
  C. 加先验: 已知h和D_t → GT形状约束

本文件: 实现方案A+B, 测量改进效果
"""
import numpy as np, json, sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

SCENE_ROOT = r"F:\sfm\论文代码与数据\04_数据\scene_set_main_f8"
OUT_DIR = r"F:\sfm\论文代码与数据\02_代码"

def load_scene(scene_name):
    sd = os.path.join(SCENE_ROOT, scene_name)
    with open(os.path.join(sd, "meta.json"), encoding="utf-8") as f:
        meta = json.load(f)
    poses = np.load(os.path.join(sd, "gt", "poses_gt.npy"))
    target_masks = np.load(os.path.join(sd, "obs", "target_masks.npy"))
    shadow_masks = np.load(os.path.join(sd, "obs", "shadow_masks.npy"))
    unlit_masks = np.load(os.path.join(sd, "obs", "unlit_masks.npy"))
    return meta, poses, target_masks, shadow_masks, unlit_masks

def poses6_to_se3(poses6):
    N = poses6.shape[0]
    se3 = np.zeros((N, 4, 4))
    se3[:, 3, 3] = 1
    for i in range(N):
        x, y, z, roll, pitch, yaw = poses6[i]
        cr, sr = np.cos(roll), np.sin(roll)
        cp, sp = np.cos(pitch), np.sin(pitch)
        cy, sy = np.cos(yaw), np.sin(yaw)
        Rx = np.array([[1,0,0],[0,cr,-sr],[0,sr,cr]])
        Ry = np.array([[cp,0,sp],[0,1,0],[-sp,0,cp]])
        Rz = np.array([[cy,-sy,0],[sy,cy,0],[0,0,1]])
        se3[i, :3, :3] = Rz @ Ry @ Rx
        se3[i, :3, 3] = [x, y, z]
    return se3

def voxel_carve_both(poses_se3, target_masks, shadow_masks, voxel_centers,
                     range_axis, beam_axis, fov_azim, fov_elev, use_shadow=True):
    """空间雕刻: target_masks删前沿前方的自由空间 + shadow_masks删阴影区自由空间"""
    dr = range_axis[1] - range_axis[0]
    H, W = target_masks.shape[1:]
    r0, b0 = range_axis[0], beam_axis[0]
    db_ = beam_axis[1] - beam_axis[0]
    
    alive = np.ones(voxel_centers.shape[0], dtype=bool)
    
    for n in range(poses_se3.shape[0]):
        R = poses_se3[n, :3, :3]
        t = poses_se3[n, :3, 3]
        Pb = (R.T @ (voxel_centers - t).T).T
        rho = np.linalg.norm(Pb, axis=1)
        theta = np.arctan2(Pb[:, 1], Pb[:, 0])
        elev = np.arctan2(Pb[:, 2], np.linalg.norm(Pb[:, :2], axis=1))
        i_theta = np.round((theta - b0) / db_).astype(int)
        
        in_fov = (np.abs(elev) <= fov_elev) & (rho >= r0) & (rho <= range_axis[-1]) \
            & (np.abs(theta) <= fov_azim) & (i_theta >= 0) & (i_theta < W)
        
        free = np.zeros(voxel_centers.shape[0], dtype=bool)
        
        # 1. target前沿前方 = 自由
        for th in np.unique(i_theta[in_fov]):
            col = in_fov & (i_theta == th)
            rows = np.where(target_masks[n, :, th])[0]
            if len(rows) == 0:
                free |= col
            else:
                rho_lead = range_axis[rows.min()]
                free |= col & (rho < rho_lead - dr/2)
        
        # 2. 阴影区 = 自由(声呐看不到阴影后面的空间)
        if use_shadow:
            for th in np.unique(i_theta[in_fov]):
                col = in_fov & (i_theta == th)
                srows = np.where(shadow_masks[n, :, th])[0]
                if len(srows) >= 2:
                    # 阴影段 = 自由(目标后方无回波)
                    s_start = range_axis[srows.min()]
                    s_end = range_axis[srows.max()]
                    free |= col & (rho > s_start - dr/2) & (rho < s_end + dr/2)
        
        alive[free] = False
    
    return alive

def gt_occupancy_cylinder(pillar_top, voxel_centers, r_cyl, h_pillar):
    x_c, y_c, z_top = pillar_top
    dx = voxel_centers[:, 0] - x_c
    dy = voxel_centers[:, 1] - y_c
    dz = voxel_centers[:, 2]
    radial = np.sqrt(dx**2 + dy**2)
    return (radial <= r_cyl) & (dz >= 0) & (dz <= h_pillar)

def run_scene(scene_name, voxel_size=0.05, use_shadow=True, bbox_mode="tight"):
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
    fov_azim = np.deg2rad(15.0)
    range_axis = np.linspace(rho_min, rho_max, H_bins)
    beam_axis = np.linspace(-fov_azim, fov_azim, W_beams)
    
    poses_se3 = poses6_to_se3(poses)
    pillar_top = np.array([D_t, 0, h_gt])
    
    # 体素包围盒
    if bbox_mode == "tight":
        # 紧包围: 只罩目标+小余量
        lo = np.array([D_t - 0.5, -0.5, -0.05])
        hi = np.array([D_t + 0.5, 0.5, h_gt + 0.15])
    else:
        lo = np.array([D_t - 1.0, -1.0, -0.1])
        hi = np.array([D_t + 1.0, 1.0, h_gt + 0.3])
    
    nx, ny, nz = np.ceil((hi - lo) / voxel_size).astype(int)
    xs = lo[0] + (np.arange(nx) + 0.5) * voxel_size
    ys = lo[1] + (np.arange(ny) + 0.5) * voxel_size
    zs = lo[2] + (np.arange(nz) + 0.5) * voxel_size
    X, Y, Z = np.meshgrid(xs, ys, zs, indexing='ij')
    centers = np.stack([X.ravel(), Y.ravel(), Z.ravel()], 1)
    voxel_vol = voxel_size**3
    
    alive = voxel_carve_both(poses_se3, target_masks, shadow_masks, centers,
                              range_axis, beam_axis, fov_azim, fov_elev, use_shadow)
    gt_occ = gt_occupancy_cylinder(pillar_top, centers, r_cyl, h_gt)
    
    V_r = alive.sum() * voxel_vol
    V_g = gt_occ.sum() * voxel_vol
    V_i = (alive & gt_occ).sum() * voxel_vol
    denom = V_r + V_g - V_i
    E = (V_r + V_g - 2*V_i) / max(denom, 1e-12)
    
    shadow_tag = "+shadow" if use_shadow else "no_shadow"
    bbox_tag = bbox_mode
    print(f"  {scene_name:<22} vs={voxel_size:.2f} {shadow_tag:<10} bbox={bbox_tag:<7} "
          f"E={E:.4f} V_r={V_r*1000:.1f}L V_g={V_g*1000:.1f}L V∩={V_i*1000:.1f}L "
          f"{'✅' if E<=0.10 else '⚠️'}")
    
    return {
        "scene": scene_name, "voxel_size": voxel_size,
        "use_shadow": use_shadow, "bbox_mode": bbox_mode,
        "E": round(float(E),4), "V_recon_L": round(float(V_r*1000),1),
        "V_gt_L": round(float(V_g*1000),1), "V_intersect_L": round(float(V_i*1000),1),
        "passed": bool(E <= 0.10),
    }

def main():
    print("=" * 60)
    print("F-4b v2: 雕刻精度——阴影约束+紧包围盒")
    print("=" * 60)
    results = []
    
    for vs in [0.05, 0.03]:
        for scene in ["M1_well_constrained", "M3_envelope_inside", "M4_envelope_outside"]:
            # no_shadow + wide bbox (baseline)
            results.append(run_scene(scene, vs, False, "wide"))
            # +shadow + wide bbox
            results.append(run_scene(scene, vs, True, "wide"))
            # +shadow + tight bbox
            results.append(run_scene(scene, vs, True, "tight"))
    
    print(f"\n{'='*60}")
    best = min(results, key=lambda x: x["E"])
    print(f"最佳: {best['scene']} vs={best['voxel_size']} shadow={best['use_shadow']} bbox={best['bbox_mode']} E={best['E']:.4f} {'✅达标' if best['passed'] else '⚠️未达标'}")
    
    # 分析: shadow约束的效果
    print(f"\n阴影约束效果:")
    for scene in ["M1_well_constrained"]:
        ns = [r for r in results if r["scene"]==scene and not r["use_shadow"] and r["voxel_size"]==0.05]
        ss = [r for r in results if r["scene"]==scene and r["use_shadow"] and r["bbox_mode"]=="wide" and r["voxel_size"]==0.05]
        st = [r for r in results if r["scene"]==scene and r["use_shadow"] and r["bbox_mode"]=="tight" and r["voxel_size"]==0.05]
        if ns and ss and st:
            print(f"  {scene}: no_shadow E={ns[0]['E']} → +shadow E={ss[0]['E']} → +shadow+tight E={st[0]['E']}")
    
    report = {"generated_at":"2026-10-13","version":"F-4b_v2","results":results,"best":best,"target":0.10}
    with open(os.path.join(OUT_DIR, "f4b_carve_precision_report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\n报告已写入")

main()
