"""为阶段 B 找可接受的规模/迭代上限组合：目标单次 solve < 2s 且收敛。"""
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


def build(heave, seed, n_kf, n_ring):
    cfg = X.make_cfg(heave=heave, seed=seed)
    poses6_all, _ = make_poses(cfg)
    kf = np.linspace(0, len(poses6_all) - 1, n_kf).astype(int)
    poses6 = poses6_all[kf].copy()
    h = cfg.scene.h_avg_m
    rng = np.random.default_rng(seed)
    lms = [np.array([X.D_T, 0.0, h])]
    for a in np.linspace(0, 2 * np.pi, n_ring, endpoint=False):
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


def trial(poses6, lms, obs, odomT, max_nfev, use_odom, rng):
    obs_n = []
    for (i, j, th, rh) in obs:
        tn = th + rng.normal(0, X.SIGMA_THETA)
        rn = rh + rng.normal(0, X.SIGMA_RHO)
        obs_n.append((i, j, tn, rn, tn / X.SIGMA_THETA, rn / X.SIGMA_RHO))
    K = len(poses6)
    odom = ([(k, np.linalg.inv(base.pose6_to_matrix(poses6[k]))
              @ base.pose6_to_matrix(poses6[k + 1])) for k in range(K - 1)]
            if use_odom else [])
    w = dict(prior=1000.0, odomT=odomT, odomR=odomT, sonar=1.0, lmprior=0.0)
    p0 = poses6 + rng.normal(0, 0.01, poses6.shape)
    l0 = lms + rng.normal(0, 0.05, lms.shape)
    ba = B34.SonarBA34(p0, l0, obs_n, odom, CALIB_W, weights=w)
    t0 = time.time()
    _p, _l, res, _ = ba.solve(jac_mode="analytic", loss="linear",
                              max_nfev=max_nfev, verbose=0)
    return time.time() - t0, res, _l[0, 2], ba


CONFIGS = [
    # n_kf, n_ring, odomT, max_nfev, use_odom
    (8, 4, 1e4, 100, True),
    (8, 4, 1e4, 60, True),
    (8, 4, 100.0, 100, True),
    (8, 4, 0.0, 100, False),
    (6, 4, 1e4, 60, True),
    (10, 6, 1e4, 60, True),
]

print(f"{'n_kf':>5}{'n_ring':>7}{'odomT':>8}{'nfev_max':>9}{'odom':>6}"
      f"{'M':>4}{'Nobs':>6}{'t(s)':>7}{'nfev':>6}{'cost':>10}{'期望cost':>10}{'z误差cm':>9}")
print("-" * 96)
for (nk, nr, ot, mn, uo) in CONFIGS:
    poses6, lms, obs = build(1.2, 801, nk, nr)
    rng = np.random.default_rng(5)
    ts, costs, zs, nfevs = [], [], [], []
    for _ in range(3):
        t, res, z, ba = trial(poses6, lms, obs, ot, mn, uo, rng)
        ts.append(t); costs.append(res.cost); zs.append(z); nfevs.append(res.nfev)
    n_res = 6 + (6 * (nk - 1) if uo else 0) + 2 * len(obs) + 3 * len(lms)
    n_var = 6 * nk + 3 * len(lms)
    exp_cost = 0.5 * max(n_res - n_var, 1)
    print(f"{nk:>5}{nr:>7}{ot:>8.0f}{mn:>9}{str(uo):>6}"
          f"{len(lms):>4}{len(obs):>6}{np.mean(ts):>7.2f}{int(np.mean(nfevs)):>6}"
          f"{np.mean(costs):>10.1f}{exp_cost:>10.1f}"
          f"{(np.mean(zs)-lms[0,2])*100:>+9.2f}")
