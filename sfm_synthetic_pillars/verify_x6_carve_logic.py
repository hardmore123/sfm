"""用几何精确 FORM 隔离雕刻逻辑：把 GT 表面点投影成目标占据区作 FORM。
若此时 S1=100%，证明雕刻的 AND 语义完全正确，S1 未达标纯属图像分割/leading-edge 问题。"""
import json
import numpy as np
from pathlib import Path
import R_x6_carve_fixed as m

SCENE_ROOT = Path("F:/sfm/sfm_synthetic_pillars/scene_set_v2")


def ideal_form(surf, poses, N, H, W, range_axis, beam_axis, fov_elev):
    """由 GT 表面点投影生成精确 FORM（目标在图像上的真实占据）。"""
    dr = range_axis[1] - range_axis[0]
    db = beam_axis[1] - beam_axis[0]
    r0, b0 = range_axis[0], beam_axis[0]
    form = np.zeros((N, H, W), dtype=bool)
    for n in range(N):
        R = poses[n, :3, :3]; t = poses[n, :3, 3]
        Pb = (R.T @ (surf - t).T).T
        rho = np.linalg.norm(Pb, axis=1)
        theta = np.arctan2(Pb[:, 1], Pb[:, 0])
        elev = np.arctan2(Pb[:, 2], np.linalg.norm(Pb[:, :2], axis=1))
        ir = np.round((rho - r0) / dr).astype(int)
        it = np.round((theta - b0) / db).astype(int)
        ok = (ir >= 0) & (ir < H) & (it >= 0) & (it < W) & (np.abs(elev) <= fov_elev)
        form[n, ir[ok], it[ok]] = True
    return form


def run(scene):
    d = SCENE_ROOT / scene
    meta = json.load(open(d / "meta.json", encoding="utf-8"))
    poses = np.load(d / "gt/poses_gt.npy")
    imgs = np.load(d / "gt/sonar_images.npy")
    surf = np.load(d / "gt/surface_points.npy")
    N, H, W = imgs.shape
    cfg = meta["config"]
    fov_elev = np.deg2rad(cfg["fov_elev_deg"][1])
    fov_azim = np.deg2rad(15.0)
    range_axis = np.linspace(0.5, cfg["rho_max_m"], H)
    beam_axis = np.linspace(-fov_azim, fov_azim, W)

    form = ideal_form(surf, poses, N, H, W, range_axis, beam_axis, fov_elev)

    lo = surf.min(0) - 0.3; hi = surf.max(0) + 0.3
    vs = 0.05
    nx, ny, nz = np.ceil((hi - lo) / vs).astype(int)
    xs = lo[0] + (np.arange(nx) + 0.5) * vs
    ys = lo[1] + (np.arange(ny) + 0.5) * vs
    zs = lo[2] + (np.arange(nz) + 0.5) * vs
    X, Y, Z = np.meshgrid(xs, ys, zs, indexing="ij")
    centers = np.stack([X.ravel(), Y.ravel(), Z.ravel()], 1)

    alive, hist = m.voxel_carve(poses, form, centers, (nx, ny, nz),
                                range_axis, beam_axis, fov_azim, fov_elev)
    gt = m.gt_occupancy(surf, centers)
    incl = 100.0 * (gt & alive).sum() / max(gt.sum(), 1)
    mono = all(hist[i + 1] <= hist[i] for i in range(len(hist) - 1))
    E, Vr, Vg, Vi = m.volumetric_error(alive, gt, vs ** 3)
    return incl, mono, E, form.mean() * 100


print("=== 几何精确 FORM（隔离雕刻逻辑）===")
print("%-30s %10s %8s %8s %8s" % ("scene", "S1_incl%", "S2_mono", "E", "FORM%"))
for s in ["S1_single_well_constrained", "S2_single_forward_degenerate",
          "S3_mixed_shapes", "S4_low_snr", "S5_envelope_edge"]:
    incl, mono, E, cov = run(s)
    print("%-30s %10.1f %8s %8.3f %8.3f" % (s, incl, str(mono), E, cov))
