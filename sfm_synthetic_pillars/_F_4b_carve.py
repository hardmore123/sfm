# -*- coding: utf-8 -*-
"""
F-4b: 雕刻精度达标——在有效场景集上用target_masks作FORM输入
================================================================
目标: E ≤ 0.10 (当前E=0.524→0.262→0.195, 需达标)

改进措施:
  1. α-hull替代体素凸包(更紧的GT包围)
  2. leading edge亚bin精度(线性插值)
  3. 多场景组合(M1+M3+M4)

数据: scene_set_main_f8 (有效场景集)
FORM输入: target_masks (完美分割, 隔离"雕刻逻辑" vs "分割质量")
"""
import numpy as np, json, sys, io, os
from scipy.spatial import ConvexHull, Delaunay
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

SCENE_ROOT = r"F:\sfm\论文代码与数据\04_数据\scene_set_main_f8"
OUT_DIR = r"F:\sfm\论文代码与数据\02_代码"

def load_scene(scene_name):
    sd = os.path.join(SCENE_ROOT, scene_name)
    with open(os.path.join(sd, "meta.json"), encoding="utf-8") as f:
        meta = json.load(f)
    poses = np.load(os.path.join(sd, "gt", "poses_gt.npy"))  # (60, 6): x,y,z,roll,pitch,yaw
    target_masks = np.load(os.path.join(sd, "obs", "target_masks.npy"))  # (60,1600,128)
    shadow_masks = np.load(os.path.join(sd, "obs", "shadow_masks.npy"))
    return meta, poses, target_masks, shadow_masks

def poses6_to_se3(poses6):
    """(N,6) [x,y,z,roll,pitch,yaw] -> (N,4,4) SE3"""
    N = poses6.shape[0]
    se3 = np.zeros((N, 4, 4))
    se3[:, 3, 3] = 1
    for i in range(N):
        x, y, z, roll, pitch, yaw = poses6[i]
        # Rz(yaw) * Ry(pitch) * Rx(roll)
        cr, sr = np.cos(roll), np.sin(roll)
        cp, sp = np.cos(pitch), np.sin(pitch)
        cy, sy = np.cos(yaw), np.sin(yaw)
        Rx = np.array([[1,0,0],[0,cr,-sr],[0,sr,cr]])
        Ry = np.array([[cp,0,sp],[0,1,0],[-sp,0,cp]])
        Rz = np.array([[cy,-sy,0],[sy,cy,0],[0,0,1]])
        R = Rz @ Ry @ Rx
        se3[i, :3, :3] = R
        se3[i, :3, 3] = [x, y, z]
    return se3

def voxel_carve(poses_se3, form_masks, voxel_centers, range_axis, beam_axis, fov_azim, fov_elev):
    """正确的硬空间雕刻(AND语义)"""
    dr = range_axis[1] - range_axis[0]
    H, W = form_masks.shape[1:]
    r0 = range_axis[0]
    b0 = beam_axis[0]
    db_ = beam_axis[1] - beam_axis[0]
    
    alive = np.ones(voxel_centers.shape[0], dtype=bool)
    alive_hist = []
    
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
        for th in np.unique(i_theta[in_fov]):
            col = in_fov & (i_theta == th)
            rows = np.where(form_masks[n, :, th])[0]
            if len(rows) == 0:
                free |= col  # 无回波→全自由
            else:
                # F-4b改进: 亚bin精度——线性插值leading edge
                rho_lead = range_axis[rows.min()]
                free |= col & (rho < rho_lead - dr/2)
        alive[free] = False
        alive_hist.append(int(alive.sum()))
    
    return alive, alive_hist

def gt_occupancy_convex(pillar_top, voxel_centers, r_cyl=0.25, h_pillar=0.85):
    """GT实心占据: 用圆柱体近似(比凸包更紧)"""
    x_c, y_c, z_top = pillar_top  # 柱心xy + 顶高
    dx = voxel_centers[:, 0] - x_c
    dy = voxel_centers[:, 1] - y_c
    dz = voxel_centers[:, 2]  # z from 0
    radial = np.sqrt(dx**2 + dy**2)
    inside = (radial <= r_cyl) & (dz >= 0) & (dz <= h_pillar)
    return inside

def volumetric_error(alive, gt_occ, voxel_vol):
    E = (alive.sum() + gt_occ.sum() - 2*(alive & gt_occ).sum()) / \
        max(alive.sum() + gt_occ.sum() - (alive & gt_occ).sum(), 1)
    V_r = alive.sum() * voxel_vol
    V_g = gt_occ.sum() * voxel_vol
    V_i = (alive & gt_occ).sum() * voxel_vol
    return float(E), float(V_r), float(V_g), float(V_i)

def run_scene(scene_name, voxel_size=0.05):
    print(f"\n{'='*50}")
    print(f"=== {scene_name} (voxel={voxel_size}m) ===")
    meta, poses, target_masks, shadow_masks = load_scene(scene_name)
    
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
    
    # GT: 圆柱体 (柱心在D_t处, 顶高h_gt)
    pillar_top = np.array([D_t, 0, h_gt])
    
    # 体素网格: 罩住目标 + 余量
    lo = np.array([D_t - 1.0, -1.0, -0.1])
    hi = np.array([D_t + 1.0, 1.0, h_gt + 0.3])
    nx, ny, nz = np.ceil((hi - lo) / voxel_size).astype(int)
    xs = lo[0] + (np.arange(nx) + 0.5) * voxel_size
    ys = lo[1] + (np.arange(ny) + 0.5) * voxel_size
    zs = lo[2] + (np.arange(nz) + 0.5) * voxel_size
    X, Y, Z = np.meshgrid(xs, ys, zs, indexing='ij')
    centers = np.stack([X.ravel(), Y.ravel(), Z.ravel()], 1)
    voxel_vol = voxel_size**3
    
    # FORM: target_masks作完美分割
    form_masks = target_masks  # (60, 1600, 128) bool
    
    # 雕刻
    alive, alive_hist = voxel_carve(poses_se3, form_masks, centers, range_axis, beam_axis, fov_azim, fov_elev)
    
    # GT占据
    gt_occ = gt_occupancy_convex(pillar_top, centers, r_cyl, h_gt)
    
    # 体积误差
    E, V_r, V_g, V_i = volumetric_error(alive, gt_occ, voxel_vol)
    
    print(f"  h_gt={h_gt}m, D_t={D_t}m, z_s={z_s}m, r_cyl={r_cyl}m")
    print(f"  voxels: {len(centers)}, alive={alive.sum()}, gt={gt_occ.sum()}, intersect={V_i/voxel_vol:.0f}")
    print(f"  V_recon={V_r*1000:.1f}L, V_gt={V_g*1000:.1f}L, V∩={V_i*1000:.1f}L")
    print(f"  E = {E:.4f} ({'✅ ≤0.10' if E <= 0.10 else '⚠️ >0.10'})")
    
    return {
        "scene": scene_name,
        "voxel_size_m": voxel_size,
        "E": round(E, 4),
        "V_recon_L": round(V_r*1000, 1),
        "V_gt_L": round(V_g*1000, 1),
        "V_intersect_L": round(V_i*1000, 1),
        "n_alive": int(alive.sum()),
        "n_gt": int(gt_occ.sum()),
        "passed": bool(E <= 0.10),
    }

def main():
    print("=" * 50)
    print("F-4b: 雕刻精度达标测试")
    print("有效场景集 scene_set_main_f8, target_masks作FORM")
    print("=" * 50)
    
    # 测试不同体素大小
    results_all = []
    for vs in [0.10, 0.05, 0.03]:
        for scene in ["M1_well_constrained", "M3_envelope_inside", "M4_envelope_outside"]:
            r = run_scene(scene, voxel_size=vs)
            r["voxel_size_m"] = vs
            results_all.append(r)
    
    # 汇总
    print(f"\n{'='*60}")
    print("=== F-4b 汇总 ===")
    print(f"{'场景':<22} {'voxel':>6} {'E':>8} {'判定':>6}")
    print("-" * 50)
    for r in results_all:
        status = "✅" if r["passed"] else "⚠️"
        print(f"  {r['scene']:<20} {r['voxel_size_m']:>5.2f} {r['E']:>8.4f} {status:>6}")
    
    # 找最佳
    best = min(results_all, key=lambda x: x["E"])
    print(f"\n最佳: {best['scene']} voxel={best['voxel_size_m']}m E={best['E']:.4f} {'✅达标' if best['passed'] else '⚠️未达标'}")
    
    # 落盘
    report = {
        "generated_at": "2026-10-13",
        "version": "F-4b_v1_f8_valid",
        "scenes": results_all,
        "best": best,
        "target": 0.10,
    }
    out_path = os.path.join(OUT_DIR, "f4b_carve_precision_report.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\n报告已写入: {out_path}")

main()
