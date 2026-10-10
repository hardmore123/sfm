"""决定性对照：阶段 B 的同一构型（8 关键帧），分三种位姿处理方式比较。

  (a) 位姿完全冻结、只估单路标   → 应与 observability 的 3×3 界吻合（阶段 A 口径）
  (b) 位姿冻结、估全部 9 个路标   → 检验"多路标"本身是否引入差异
  (c) 位姿作为变量的联合 BA       → 阶段 B 的做法

若 (a)(b) 吻合而 (c) 偏大，则差异来自**位姿自由度**，属正常（联合估计的代价），
但需要一个与之匹配的理论界（联合 Λ 已经是了，所以要查为什么联合 Λ 给不出该值）。
"""
import io
import os
import sys
import time

sys.path.insert(0, r"F:\sfm\论文代码与数据\02_代码")
os.chdir(r"F:\sfm\论文代码与数据\02_代码")
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import numpy as np
from scipy.optimize import least_squares
import ba_improve34 as B34
import ba_optimize as base
import rx3_ba_crlb as X
from trajectory import make_poses, euler_to_matrix

CALIB_W = (1.0 / X.SIGMA_THETA, 0.0, 1.0 / X.SIGMA_RHO, 0.0)
N_KF, N_RING = 8, 4
N_TRIAL = 150


def build(heave, seed):
    cfg = X.make_cfg(heave=heave, seed=seed)
    poses6_all, _ = make_poses(cfg)
    kf = np.linspace(0, len(poses6_all) - 1, N_KF).astype(int)
    poses6 = poses6_all[kf].copy()
    h = cfg.scene.h_avg_m
    rng = np.random.default_rng(seed)
    lms = [np.array([X.D_T, 0.0, h])]
    for a in np.linspace(0, 2 * np.pi, N_RING, endpoint=False):
        lms.append(np.array([X.D_T + X.R_PILLAR * np.cos(a),
                             X.R_PILLAR * np.sin(a), h]))
        lms.append(np.array([X.D_T + X.R_PILLAR * np.cos(a),
                             X.R_PILLAR * np.sin(a), h * rng.uniform(0.3, 0.8)]))
    lms = np.array(lms)
    obs = []
    for i, p in enumerate(poses6):
        for j, P in enumerate(lms):
            if len(X.visible_frames(P, p.reshape(1, 6))) == 1:
                th, rh = X.project(P, p)
                obs.append((i, j, th, rh))
    return poses6, lms, obs


def mc_frozen_multi(poses6, lms, obs, n_trial=N_TRIAL, seed=3):
    """位姿冻结，联合估**全部路标**（每个路标独立，因为位姿已知 ⇒ 可分离）。
    只收集 0 号路标的 z。"""
    rng = np.random.default_rng(seed)
    R = np.array([euler_to_matrix(p[3], p[4], p[5]) for p in poses6])
    Rt = np.transpose(R, (0, 2, 1))
    t = poses6[:, :3]
    # 0 号路标的观测
    o0 = [(i, th, rh) for (i, j, th, rh) in obs if j == 0]
    idx = np.array([i for (i, _, _) in o0])
    th0 = np.array([th for (_, th, _) in o0])
    rh0 = np.array([rh for (_, _, rh) in o0])

    def resid(P, tho, rho_):
        Pb = np.einsum("kij,kj->ki", Rt[idx], P - t[idx])
        th = np.arctan2(Pb[:, 1], Pb[:, 0])
        rh = np.linalg.norm(Pb, axis=1)
        d = (th - tho + np.pi) % (2 * np.pi) - np.pi
        return np.concatenate([d / X.SIGMA_THETA, (rh - rho_) / X.SIGMA_RHO])

    zs = []
    for _ in range(n_trial):
        tho = th0 + rng.normal(0, X.SIGMA_THETA, len(idx))
        rho_ = rh0 + rng.normal(0, X.SIGMA_RHO, len(idx))
        P0 = lms[0] + rng.normal(0, 0.05, 3)
        s = least_squares(resid, P0, args=(tho, rho_), method="lm",
                          xtol=1e-12, ftol=1e-12)
        zs.append(s.x[2])
    return np.array(zs), idx


poses6, lms, obs = build(1.2, 801)
K = len(poses6)
print(f"构型：K={K} 关键帧, M={len(lms)} 路标, Nobs={len(obs)}")

# ---- (a) 位姿冻结 + 单路标 ----
zs_a, idx0 = mc_frozen_multi(poses6, lms, obs)
cr_a = X.crlb_frozen_pose(lms[0], poses6, idx0)
print()
print("=" * 90)
print("(a) 位姿冻结、只估 0 号路标")
print("=" * 90)
print(f"  0 号路标可见帧数 = {len(idx0)}")
print(f"  严格 CRLB (observability 3×3) = {cr_a['sigma_Pz']*100:.3f} cm")
print(f"  MC 实测 s_z                    = {zs_a.std(ddof=1)*100:.3f} cm")
print(f"  bias                           = {(zs_a.mean()-lms[0,2])*100:+.3f} cm")
print(f"  ⇒ ratio = {zs_a.std(ddof=1)/cr_a['sigma_Pz']:.3f}   (判据 [0.8,1.3])")

# ---- (c) 联合 BA：位姿也是变量 ----
odom = [(k, np.linalg.inv(base.pose6_to_matrix(poses6[k]))
         @ base.pose6_to_matrix(poses6[k + 1])) for k in range(K - 1)]
W = dict(prior=1000.0, odomT=1e4, odomR=1e4, sonar=1.0, lmprior=0.0)
rng = np.random.default_rng(11)
zs_c, crlbs = [], []
t0 = time.time()
for _ in range(N_TRIAL):
    obs_n = []
    for (i, j, th, rh) in obs:
        tn = th + rng.normal(0, X.SIGMA_THETA)
        rn = rh + rng.normal(0, X.SIGMA_RHO)
        obs_n.append((i, j, tn, rn, tn / X.SIGMA_THETA, rn / X.SIGMA_RHO))
    p0 = poses6 + rng.normal(0, 0.01, poses6.shape)
    l0 = lms + rng.normal(0, 0.05, lms.shape)
    ba = B34.SonarBA34(p0, l0, obs_n, odom, CALIB_W, weights=W)
    _p, _l, res, _ = ba.solve(jac_mode="analytic", loss="linear",
                              max_nfev=60, verbose=0)
    zs_c.append(_l[0, 2])
    J = ba.jac_analytic(res.x)
    Lam = (J.T @ J).toarray()
    col = 6 * ba.K + 2
    crlbs.append(np.sqrt(max(np.linalg.pinv(Lam, rcond=1e-12)[col, col], 0)))
zs_c = np.array(zs_c)
print()
print("=" * 90)
print("(c) 联合 BA（位姿为变量，odom 强约束）")
print("=" * 90)
print(f"  耗时 {time.time()-t0:.0f}s")
print(f"  联合 CRLB (中位) = {np.median(crlbs)*100:.3f} cm")
print(f"  MC 实测 s_z      = {zs_c.std(ddof=1)*100:.3f} cm")
print(f"  bias             = {(zs_c.mean()-lms[0,2])*100:+.3f} cm")
print(f"  ⇒ ratio = {zs_c.std(ddof=1)/np.median(crlbs):.3f}")

# ---- 关键诊断：位姿真的被钉住了吗？----
print()
print("=" * 90)
print("关键诊断：MC 中位姿的实际抖动（odomT=1e4 是否真把位姿钉住）")
print("=" * 90)
rng = np.random.default_rng(12)
pose_dev = []
for _ in range(20):
    obs_n = []
    for (i, j, th, rh) in obs:
        tn = th + rng.normal(0, X.SIGMA_THETA)
        rn = rh + rng.normal(0, X.SIGMA_RHO)
        obs_n.append((i, j, tn, rn, tn / X.SIGMA_THETA, rn / X.SIGMA_RHO))
    p0 = poses6 + rng.normal(0, 0.01, poses6.shape)
    l0 = lms + rng.normal(0, 0.05, lms.shape)
    ba = B34.SonarBA34(p0, l0, obs_n, odom, CALIB_W, weights=W)
    _p, _l, res, _ = ba.solve(jac_mode="analytic", loss="linear",
                              max_nfev=60, verbose=0)
    pose_dev.append(_p[:, 2] - poses6[:, 2])     # 各帧 z 的偏差
pose_dev = np.array(pose_dev)
print(f"  各帧位姿 z 的偏差 std（跨试验）= {pose_dev.std(axis=0)*100} cm")
print(f"  平均 = {pose_dev.std(axis=0).mean()*100:.3f} cm")
print("  ⇒ 若这个量与路标 z 的 s_z 同量级，说明位姿并未被钉住，")
print("    联合 BA 的路标高度误差里混入了位姿高度误差。")
