"""诊断阶段 B 的 ratio 偏大：是未收敛、局部极小，还是联合 CRLB 算错？

三个检查：
  1) 同一批观测，max_nfev 60/200/600 的 z 估计是否还在漂（未收敛的直接证据）
  2) z_hat 分布有没有异常值（局部极小 ⇒ 少数离群点拉大 std）
  3) 联合 CRLB 对 pinv 的 rcond 是否敏感
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
import ba_improve34 as B34
import ba_optimize as base
import rx3_ba_crlb as X
from trajectory import make_poses

CALIB_W = (1.0 / X.SIGMA_THETA, 0.0, 1.0 / X.SIGMA_RHO, 0.0)
N_KF, N_RING = 8, 4


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


poses6, lms, obs = build(1.2, 801)
K = len(poses6)
odom = [(k, np.linalg.inv(base.pose6_to_matrix(poses6[k]))
         @ base.pose6_to_matrix(poses6[k + 1])) for k in range(K - 1)]
W = dict(prior=1000.0, odomT=1e4, odomR=1e4, sonar=1.0, lmprior=0.0)

# ---- 检查 1：收敛性（同一批观测，不同 max_nfev）----
print("=" * 88)
print("检查 1：同一批观测下 max_nfev 对 z 估计的影响（未收敛则 z 随 nfev 漂）")
print("=" * 88)
print(f"{'trial':>6}{'nfev=60':>12}{'nfev=200':>12}{'nfev=600':>12}"
      f"{'|Δ(60→600)|cm':>15}{'cost60':>10}{'cost600':>10}")
print("-" * 88)
rng = np.random.default_rng(99)
drifts = []
for t in range(5):
    obs_n = []
    for (i, j, th, rh) in obs:
        tn = th + rng.normal(0, X.SIGMA_THETA)
        rn = rh + rng.normal(0, X.SIGMA_RHO)
        obs_n.append((i, j, tn, rn, tn / X.SIGMA_THETA, rn / X.SIGMA_RHO))
    p0 = poses6 + rng.normal(0, 0.01, poses6.shape)
    l0 = lms + rng.normal(0, 0.05, lms.shape)
    zs, cs = {}, {}
    for mn in (60, 200, 600):
        ba = B34.SonarBA34(p0.copy(), l0.copy(), obs_n, odom, CALIB_W, weights=W)
        _p, _l, res, _ = ba.solve(jac_mode="analytic", loss="linear",
                                  max_nfev=mn, verbose=0)
        zs[mn] = _l[0, 2]
        cs[mn] = res.cost
    d = abs(zs[60] - zs[600]) * 100
    drifts.append(d)
    print(f"{t:>6}{zs[60]:>12.5f}{zs[200]:>12.5f}{zs[600]:>12.5f}"
          f"{d:>15.3f}{cs[60]:>10.2f}{cs[600]:>10.2f}")
print("-" * 88)
print(f"z 从 nfev=60 到 600 的平均漂移 = {np.mean(drifts):.3f} cm")
print("  ⇒ 若该漂移与 s_z(≈14cm) 同量级，则 ratio 偏大主要是**未收敛**造成的")

# ---- 检查 2：z_hat 分布是否有异常值 ----
print()
print("=" * 88)
print("检查 2：z_hat 分布（用 nfev=600 充分收敛），看有无离群点")
print("=" * 88)
rng = np.random.default_rng(7)
zh = []
t0 = time.time()
for t in range(40):
    obs_n = []
    for (i, j, th, rh) in obs:
        tn = th + rng.normal(0, X.SIGMA_THETA)
        rn = rh + rng.normal(0, X.SIGMA_RHO)
        obs_n.append((i, j, tn, rn, tn / X.SIGMA_THETA, rn / X.SIGMA_RHO))
    p0 = poses6 + rng.normal(0, 0.01, poses6.shape)
    l0 = lms + rng.normal(0, 0.05, lms.shape)
    ba = B34.SonarBA34(p0, l0, obs_n, odom, CALIB_W, weights=W)
    _p, _l, res, _ = ba.solve(jac_mode="analytic", loss="linear",
                              max_nfev=600, verbose=0)
    zh.append(_l[0, 2])
zh = np.array(zh)
err = (zh - lms[0, 2]) * 100
print(f"n={len(zh)}  耗时 {time.time()-t0:.0f}s")
print(f"  s_z      = {zh.std(ddof=1)*100:.3f} cm")
print(f"  bias     = {err.mean():+.3f} cm")
print(f"  IQR-based robust std = {(np.percentile(err,75)-np.percentile(err,25))/1.349:.3f} cm")
print(f"  min/max 误差 = {err.min():+.2f} / {err.max():+.2f} cm")
print(f"  |err|>3·robust_std 的个数 = "
      f"{int(np.sum(np.abs(err-np.median(err)) > 3*(np.percentile(err,75)-np.percentile(err,25))/1.349))}")

# ---- 检查 3：联合 CRLB 对 rcond 的敏感性 ----
print()
print("=" * 88)
print("检查 3：联合 CRLB 对 pinv rcond 的敏感性")
print("=" * 88)
ba = B34.SonarBA34(poses6.copy(), lms.copy(),
                   [(i, j, th, rh, th / X.SIGMA_THETA, rh / X.SIGMA_RHO)
                    for (i, j, th, rh) in obs],
                   odom, CALIB_W, weights=W)
J = ba.jac_analytic(ba.x0)
Lam = (J.T @ J).toarray()
col = 6 * ba.K + 3 * 0 + 2
ev = np.linalg.eigvalsh(Lam)
print(f"Λ 尺寸 {Lam.shape}  特征值范围 [{ev.min():.3e}, {ev.max():.3e}]  "
      f"条件数 {ev.max()/max(ev.min(),1e-30):.3e}")
for rc in (1e-15, 1e-12, 1e-10, 1e-8):
    Li = np.linalg.pinv(Lam, rcond=rc)
    print(f"  rcond={rc:>7.0e}  sqrt([Λ⁻¹]_zz) = {np.sqrt(max(Li[col,col],0))*100:.3f} cm")
try:
    Li2 = np.linalg.inv(Lam)
    print(f"  直接 inv     sqrt([Λ⁻¹]_zz) = {np.sqrt(max(Li2[col,col],0))*100:.3f} cm")
except np.linalg.LinAlgError:
    print("  直接 inv 失败（奇异）")
