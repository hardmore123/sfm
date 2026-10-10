"""测阶段 B 单次联合 BA 的耗时与规模，用来定 MC 次数。"""
import io
import os
import sys
import time

sys.path.insert(0, r"F:\sfm\论文代码与数据\02_代码")
os.chdir(r"F:\sfm\论文代码与数据\02_代码")
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import numpy as np
import verify_rx3_stageB as S
import ba_improve34 as B34
import ba_optimize as base
import rx3_ba_crlb as X

poses6, lms, obs = S.build_problem(heave=1.2, seed=801)
print(f"K={len(poses6)}  M={len(lms)}  Nobs={len(obs)}")
print(f"变量数 = {6*len(poses6) + 3*len(lms)}")

odom_rel = [(k, np.linalg.inv(base.pose6_to_matrix(poses6[k]))
             @ base.pose6_to_matrix(poses6[k + 1])) for k in range(len(poses6) - 1)]
weights = dict(prior=1000.0, odomT=1e4, odomR=1e4, sonar=1.0, lmprior=0.0)
rng = np.random.default_rng(1)

for trial in range(3):
    obs_n = S.make_observations(obs, rng)
    p_init = poses6 + rng.normal(0.0, 0.01, size=poses6.shape)
    l_init = lms + rng.normal(0.0, 0.05, size=lms.shape)
    t0 = time.time()
    ba = B34.SonarBA34(p_init, l_init, obs_n, odom_rel, S.CALIB_W, weights=weights)
    t_build = time.time() - t0
    t0 = time.time()
    _p, _l, res, _dt = ba.solve(jac_mode="analytic", loss="linear",
                                max_nfev=300, verbose=0)
    t_solve = time.time() - t0
    t0 = time.time()
    cj = S.joint_crlb_z(ba, res.x, 0)
    t_crlb = time.time() - t0
    print(f"  trial{trial}: build={t_build:.2f}s solve={t_solve:.2f}s crlb={t_crlb:.2f}s "
          f"nfev={res.nfev} cost={res.cost:.3e} z={_l[0,2]:.4f} (真值 {lms[0,2]:.4f}) "
          f"joint_crlb={cj*100:.2f}cm")
