"""
R-X6 空间雕刻（F-4 修正版）
============================

修正 `_R_x6_aykin_carve_v2.py` 的四处错误（见 审计_20260905 §3）：
  Bug1 逻辑方向反了：alive 初始全 True，任一视角判自由即删除（AND）；
       原版 alive 初始全 False + OR 累积（并集保留），方向完全相反。
  Bug2 leading edge 取 rows.min()（最近），原版取 rows.max()（最远，受多径污染）。
  Bug3 遮挡区 rho > rho_lead 不参与判定（unknown），原版纳入判定。
  Bug4 无回波波束 → 整条在视场量程内自由空间删除；原版 continue 跳过。

体积度量统一（修原版 V_recon 用凸包、V∩ 用体素的量纲不一致）：
  recon / gt / 交集 全部在同一体素网格上计数。

先过逻辑自检 S1/S2（不依赖真值精度），再看精度指标 S3/S4。
"""
import json
import numpy as np
from pathlib import Path
from scipy.spatial import ConvexHull, Delaunay

SCENE_ROOT = Path("F:/sfm/sfm_synthetic_pillars/scene_set_v2")


def make_binary_form(sonar_image, n_std=3.0, r_min_m=1.5, r_max_m=18.0, range_axis=None):
    """二值 FORM 图：dB 域 中位数 + n_std·MAD 阈值 + 距离门限。"""
    db = 20 * np.log10(sonar_image + 1e-9)
    nf = np.median(db)
    sigma = np.median(np.abs(db - nf)) * 1.4826
    form = db > (nf + n_std * sigma)
    if range_axis is not None:
        rmask = (range_axis >= r_min_m) & (range_axis <= r_max_m)
        form = form & rmask[:, None]
    return form


def voxel_carve(poses_se3, form_masks, voxel_centers, shape3,
                range_axis, beam_axis, fov_azim, fov_elev):
    """
    正确的硬空间雕刻（AND 语义）。
    返回 alive (bool, 展平) 与逐视角的 alive 计数序列（用于 S2 自检）。
    """
    dr = range_axis[1] - range_axis[0]
    db_ = beam_axis[1] - beam_axis[0]
    r0, b0 = range_axis[0], beam_axis[0]
    H, W = form_masks.shape[1:]

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
        # 只需遍历实际出现的 beam 列
        for th in np.unique(i_theta[in_fov]):
            col = in_fov & (i_theta == th)
            rows = np.where(form_masks[n, :, th])[0]
            if len(rows) == 0:
                # Bug4 修复：整条波束无回波 ⇒ 视场量程内全自由
                free |= col
            else:
                rho_lead = range_axis[rows.min()]          # Bug2 修复：min=近
                # Bug3 修复：仅前沿之前判自由；rho > rho_lead 为遮挡，不动
                free |= col & (rho < rho_lead - dr / 2)
        alive[free] = False                                 # Bug1 修复：AND=删除
        alive_hist.append(int(alive.sum()))

    return alive, alive_hist


def gt_occupancy(surface_pts, voxel_centers, convex=True):
    """GT 实心占据：凸目标用 ConvexHull+Delaunay 判体素中心是否在包内。"""
    if len(surface_pts) < 4:
        return np.zeros(voxel_centers.shape[0], dtype=bool)
    try:
        dl = Delaunay(surface_pts)
        return dl.find_simplex(voxel_centers) >= 0
    except Exception:
        return np.zeros(voxel_centers.shape[0], dtype=bool)


def volumetric_error(alive, gt_occ, voxel_vol):
    """E = (V + Ṽ - 2V∩)/(V + Ṽ - V∩)，三者同网格同度量。"""
    V_r = alive.sum() * voxel_vol
    V_g = gt_occ.sum() * voxel_vol
    V_i = (alive & gt_occ).sum() * voxel_vol
    denom = V_r + V_g - V_i
    if denom <= 1e-12:
        return 1.0, V_r, V_g, V_i
    return float((V_r + V_g - 2 * V_i) / denom), float(V_r), float(V_g), float(V_i)


def evaluate(scene_name, voxel_size=0.05, n_poses=None, form_mode="auto"):
    d = SCENE_ROOT / scene_name
    meta = json.load(open(d / "meta.json", encoding="utf-8"))
    poses = np.load(d / "gt/poses_gt.npy")
    imgs = np.load(d / "gt/sonar_images.npy")
    surf = np.load(d / "gt/surface_points.npy")
    N, H, W = imgs.shape

    cfg = meta.get("config", {})
    fov_elev = np.deg2rad(cfg.get("fov_elev_deg", [-17, 17])[1])
    fov_azim = np.deg2rad(15.0)   # 方位半孔径（beam_axis 端点）
    range_axis = np.linspace(0.5, cfg.get("rho_max_m", 25.0), H)
    beam_axis = np.linspace(-fov_azim, fov_azim, W)

    # 体素网格：罩住 GT 包围盒 + 余量
    lo = surf.min(0) - 0.3
    hi = surf.max(0) + 0.3
    nx, ny, nz = np.ceil((hi - lo) / voxel_size).astype(int)
    xs = lo[0] + (np.arange(nx) + 0.5) * voxel_size
    ys = lo[1] + (np.arange(ny) + 0.5) * voxel_size
    zs = lo[2] + (np.arange(nz) + 0.5) * voxel_size
    X, Y, Z = np.meshgrid(xs, ys, zs, indexing="ij")
    centers = np.stack([X.ravel(), Y.ravel(), Z.ravel()], 1)

    if form_mode == "gt_target":
        # 诊断用：完美分割（目标真值掩码作 FORM），隔离"雕刻逻辑" vs "分割质量"
        tm = np.load(d / "gt/target_masks.npy")
        form = tm.astype(bool)
    else:
        form = np.array([make_binary_form(imgs[n], range_axis=range_axis) for n in range(N)])
    has = np.array([form[n].sum() > 0 for n in range(N)])
    idx = np.where(has)[0]
    if n_poses:
        idx = idx[np.linspace(0, len(idx) - 1, min(n_poses, len(idx))).astype(int)]

    alive, hist = voxel_carve(poses[idx], form[idx], centers, (nx, ny, nz),
                              range_axis, beam_axis, fov_azim, fov_elev)
    gt_occ = gt_occupancy(surf, centers)

    # ---- S1 逻辑自检：雕后是否仍包含全部 GT 占据体素 ----
    gt_kept = (gt_occ & alive).sum()
    inclusion = 100.0 * gt_kept / max(gt_occ.sum(), 1)

    # ---- S2 逻辑自检：体素数随视角单调不增 ----
    monotone = all(hist[i + 1] <= hist[i] for i in range(len(hist) - 1))

    E, V_r, V_g, V_i = volumetric_error(alive, gt_occ, voxel_size ** 3)

    return {
        "scene": scene_name, "n_views": len(idx), "voxel_size": voxel_size,
        "form_cov_pct": float(form[idx].mean() * 100),
        "n_alive": int(alive.sum()), "n_gt_occ": int(gt_occ.sum()),
        "S1_inclusion_pct": float(inclusion),
        "S2_monotone_nonincreasing": bool(monotone),
        "alive_hist": hist,
        "V_recon": V_r, "V_gt": V_g, "V_inter": V_i,
        "volumetric_error": E,
    }


def main():
    scenes = ["S1_single_well_constrained", "S2_single_forward_degenerate",
              "S3_mixed_shapes", "S4_low_snr", "S5_envelope_edge"]
    print("=" * 92)
    print("R-X6 空间雕刻（F-4 修正版）— 先看 S1/S2 逻辑自检")
    print("=" * 92)
    print(f"{'scene':<30}{'views':>6}{'FORM%':>7}{'alive':>7}{'gt_occ':>7}"
          f"{'S1_incl%':>10}{'S2_mono':>9}{'E':>8}")
    print("-" * 92)
    out = []
    for s in scenes:
        try:
            r = evaluate(s, voxel_size=0.05)
        except Exception as e:
            print(f"{s:<30}  ERROR: {e}")
            continue
        out.append(r)
        print(f"{r['scene']:<30}{r['n_views']:>6}{r['form_cov_pct']:>7.2f}"
              f"{r['n_alive']:>7}{r['n_gt_occ']:>7}{r['S1_inclusion_pct']:>10.1f}"
              f"{str(r['S2_monotone_nonincreasing']):>9}{r['volumetric_error']:>8.3f}")

    print()
    print("=== 逻辑自检判定（不依赖真值精度）===")
    s1_pass = all(r["S1_inclusion_pct"] >= 99.5 for r in out)
    s2_pass = all(r["S2_monotone_nonincreasing"] for r in out)
    print(f"  S1 包含性（雕后含全部 GT 占据体素，应 100%）: {'通过' if s1_pass else '未通过'}")
    print(f"  S2 体素数随视角单调不增: {'通过' if s2_pass else '未通过'}")
    print()
    print("=== 精度判定 ===")
    for r in out:
        tag = "凸单柱" if r["scene"] in (
            "S1_single_well_constrained", "S2_single_forward_degenerate",
            "S4_low_snr", "S5_envelope_edge") else "凹/多形状"
        print(f"  {r['scene']:<30} E={r['volumetric_error']:.3f}  ({tag})")
    print()
    print("注：本仿真为 AUV 直线轨迹（无 Aykin 的 roll 构型），仰角多样性有限，")
    print("    E 若偏大需区分是逻辑问题（S1/S2 未过）还是构型问题（S1/S2 过但 E 大）。")

    with open("R_X6_FIXED_RESULTS.json", "w", encoding="utf-8") as f:
        json.dump({"results": out, "S1_pass": s1_pass, "S2_pass": s2_pass},
                  f, indent=2, ensure_ascii=False)
    print("\n[ok] -> R_X6_FIXED_RESULTS.json")


if __name__ == "__main__":
    main()
