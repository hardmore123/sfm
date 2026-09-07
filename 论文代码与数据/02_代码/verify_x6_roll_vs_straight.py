"""决定性验证：雕刻逻辑对了，给足 elev 多样性（Aykin 式 roll 构型）能否达 E≤0.10。
构造 N_P 位置 × N_R roll（绕视线轴旋转），几何精确 FORM 雕刻凸单柱。
对照直线轨迹（roll=0）。这同时验证 R-X6 逻辑与 ★I-1（需 elev 多样性）。"""
import numpy as np
from scipy.spatial import Delaunay


def gt_cylinder_surface(r=0.4, h=2.5, nth=60, nz=40):
    th = np.linspace(0, 2 * np.pi, nth, endpoint=False)
    zz = np.linspace(0, h, nz)
    pts = [[r * np.cos(t), r * np.sin(t), z] for z in zz for t in th]
    # 顶盖
    for rr in np.linspace(0, r, 8):
        for t in th:
            pts.append([rr * np.cos(t), rr * np.sin(t), h])
    return np.array(pts)


def Rx(a):
    c, s = np.cos(a), np.sin(a)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


def look_at(cam, target):
    """相机在 cam 看向 target，返回 R_wb（体 x 轴 = 视线方向）。"""
    f = target - cam; f = f / np.linalg.norm(f)
    up = np.array([0, 0, 1.0])
    left = np.cross(up, f); left = left / np.linalg.norm(left)
    u = np.cross(f, left)
    return np.stack([f, left, u], axis=1)   # 列 = 体轴在世界中的方向


def carve(poses, surf, centers, range_axis, beam_axis, fov_elev, fov_azim):
    dr = range_axis[1] - range_axis[0]; dbb = beam_axis[1] - beam_axis[0]
    r0, b0 = range_axis[0], beam_axis[0]; H = len(range_axis); W = len(beam_axis)
    # 几何精确 FORM
    N = len(poses)
    alive = np.ones(centers.shape[0], dtype=bool); hist = []
    for R, t in poses:
        Pbs = (R.T @ (surf - t).T).T
        rs = np.linalg.norm(Pbs, axis=1); ts = np.arctan2(Pbs[:, 1], Pbs[:, 0])
        es = np.arctan2(Pbs[:, 2], np.linalg.norm(Pbs[:, :2], axis=1))
        irs = np.round((rs - r0) / dr).astype(int); its = np.round((ts - b0) / dbb).astype(int)
        ok = (irs >= 0) & (irs < H) & (its >= 0) & (its < W) & (np.abs(es) <= fov_elev)
        form = np.zeros((H, W), dtype=bool); form[irs[ok], its[ok]] = True

        Pb = (R.T @ (centers - t).T).T
        rho = np.linalg.norm(Pb, axis=1); theta = np.arctan2(Pb[:, 1], Pb[:, 0])
        elev = np.arctan2(Pb[:, 2], np.linalg.norm(Pb[:, :2], axis=1))
        it = np.round((theta - b0) / dbb).astype(int)
        inf = (np.abs(elev) <= fov_elev) & (rho >= r0) & (rho <= range_axis[-1]) \
            & (np.abs(theta) <= fov_azim) & (it >= 0) & (it < W)
        free = np.zeros(centers.shape[0], dtype=bool)
        for th in np.unique(it[inf]):
            col = inf & (it == th); rows = np.where(form[:, th])[0]
            if len(rows) == 0:
                free |= col
            else:
                free |= col & (rho < range_axis[rows.min()] - dr / 2)
        alive[free] = False; hist.append(int(alive.sum()))
    return alive, hist


def evalE(alive, gt, vv):
    Vr = alive.sum() * vv; Vg = gt.sum() * vv; Vi = (alive & gt).sum() * vv
    dn = Vr + Vg - Vi
    return (Vr + Vg - 2 * Vi) / dn if dn > 1e-12 else 1.0


def build(NP, NR, R_orbit=12.0, z=4.5):
    """NP 个方位位置 × NR 个 roll。目标在原点，柱高 2.5。"""
    surf = gt_cylinder_surface()
    tgt = np.array([0, 0, 1.25])
    poses = []
    for ip in range(NP):
        az = 2 * np.pi * ip / NP
        cam = np.array([R_orbit * np.cos(az), R_orbit * np.sin(az), z])
        Rb = look_at(cam, tgt)
        for ir in range(NR):
            roll = np.pi * ir / NR   # 0..180°，180/NR 步长
            poses.append((Rb @ Rx(roll), cam))
    return poses, surf


H, W = 600, 256
fov_elev = np.deg2rad(17); fov_azim = np.deg2rad(15)
range_axis = np.linspace(0.5, 25.0, H); beam_axis = np.linspace(-fov_azim, fov_azim, W)
vs = 0.05
lo = np.array([-0.6, -0.6, -0.1]); hi = np.array([0.6, 0.6, 2.7])
nx, ny, nz = np.ceil((hi - lo) / vs).astype(int)
xs = lo[0] + (np.arange(nx) + 0.5) * vs; ys = lo[1] + (np.arange(ny) + 0.5) * vs
zs = lo[2] + (np.arange(nz) + 0.5) * vs
X, Y, Z = np.meshgrid(xs, ys, zs, indexing="ij")
centers = np.stack([X.ravel(), Y.ravel(), Z.ravel()], 1)
surf0 = gt_cylinder_surface()
gt = Delaunay(surf0).find_simplex(centers) >= 0

print("=== R-X6 决定性验证：雕刻逻辑正确性 vs elev 多样性 ===")
print("目标：凸单柱 r=0.4 h=2.5；GT 占据体素 =", int(gt.sum()))
print("%-28s %8s %10s %8s" % ("构型", "视角数", "S1_incl%", "E"))
for name, NP, NR in [("直线近似(1位置×1)", 1, 1),
                     ("2位置×1(无roll)", 2, 1),
                     ("6位置×1(无roll,环绕)", 6, 1),
                     ("2位置×8roll(Aykin)", 2, 8),
                     ("6位置×8roll(Aykin理想)", 6, 8)]:
    poses, surf = build(NP, NR)
    alive, hist = carve(poses, surf, centers, range_axis, beam_axis, fov_elev, fov_azim)
    incl = 100.0 * (gt & alive).sum() / gt.sum()
    E = evalE(alive, gt, vs ** 3)
    print("%-28s %8d %10.1f %8.3f" % (name, len(poses), incl, E))
