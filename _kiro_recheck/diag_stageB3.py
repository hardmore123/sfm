"""诊断 B1_M2 的 ratio=0.261（MC 远小于 CRLB，反常）。

假设：M2 高度弱可观测（std φ=0.152°），z 方向梯度极小，有限迭代下 ẑ 停在初值附近
      ⇒ s_z 被"路标初值扰动 σ"主导，不反映真实估计散布。

判别实验：
  1) 固定观测噪声种子，只改初值扰动 σ ∈ {0.01, 0.05, 0.20}
     → 若 s_z 随初值 σ 正比变化，假设成立
  2) 固定初值（完全不扰动 z），只让观测噪声变化，加大 max_nfev
     → 这才是"纯观测噪声导致的散布"
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
import verify_rx3_stageB as S

N = 60          # 每组 MC 次数（诊断用，不做最终判定）

poses6, lms, obs = S.build_problem(heave=0.1, seed=802)   # M2 构型
K = len(poses6)
print(f"M2 构型：K={K}  M={len(lms)}  Nobs={len(obs)}")

W = dict(prior=1000.0, odomT=1.0 / 1e-3, odomR=1.0 / 1e-4, sonar=1.0, lmprior=0.0)


def run(pert_lm, max_nfev, n=N, seed=5, pert_z_only=None):
    rng = np.random.default_rng(seed)
    zs, crlbs = [], []
    for _ in range(n):
        obs_n = S.make_observations(obs, rng)
        odom = S.noisy_odom(poses6, 1e-3, 1e-4, rng)
        l0 = lms.copy()
        if pert_lm > 0:
            l0 = l0 + rng.normal(0, pert_lm, lms.shape)
        if pert_z_only is not None:      # 只扰动 xy，z 用真值
            l0 = lms + rng.normal(0, pert_z_only, lms.shape)
            l0[:, 2] = lms[:, 2]
        ba = B34.SonarBA34(poses6.copy(), l0, obs_n, odom, S.CALIB_W, weights=W)
        _p, _l, res, _ = ba.solve(jac_mode="analytic", loss="linear",
                                  max_nfev=max_nfev, verbose=0)
        zs.append(_l[0, 2])
        J = ba.jac_analytic(res.x)
        Lam = (J.T @ J).toarray()
        col = 6 * ba.K + 2
        crlbs.append(np.sqrt(max(np.linalg.pinv(Lam, rcond=1e-12)[col, col], 0)))
    zs = np.array(zs)
    return zs.std(ddof=1) * 100, (zs.mean() - lms[0, 2]) * 100, np.median(crlbs) * 100


print()
print("=" * 92)
print("实验 1：s_z 是否随【路标初值扰动 σ】变化（若正比 ⇒ 被初值主导）")
print("=" * 92)
print(f"{'初值扰动σ(m)':>13}{'max_nfev':>10}{'s_z(cm)':>10}{'bias(cm)':>10}"
      f"{'CRLB(cm)':>10}{'ratio':>8}")
print("-" * 92)
for pert in (0.01, 0.05, 0.20):
    t0 = time.time()
    s, b, c = run(pert, 60)
    print(f"{pert:>13.2f}{60:>10}{s:>10.2f}{b:>+10.2f}{c:>10.2f}{s/c:>8.3f}"
          f"   ({time.time()-t0:.0f}s)")

print()
print("=" * 92)
print("实验 2：加大 max_nfev（让弱方向真正收敛），初值扰动固定 0.05")
print("=" * 92)
print(f"{'max_nfev':>10}{'s_z(cm)':>10}{'bias(cm)':>10}{'CRLB(cm)':>10}{'ratio':>8}")
print("-" * 92)
for mn in (60, 300, 1000):
    t0 = time.time()
    s, b, c = run(0.05, mn)
    print(f"{mn:>10}{s:>10.2f}{b:>+10.2f}{c:>10.2f}{s/c:>8.3f}   ({time.time()-t0:.0f}s)")

print()
print("=" * 92)
print("实验 3：z 初值用真值（只扰动 xy），排除 z 初值随机性")
print("=" * 92)
for mn in (60, 300):
    s, b, c = run(0.0, mn, pert_z_only=0.05)
    print(f"  max_nfev={mn:>5}  s_z={s:.2f} cm  bias={b:+.2f} cm  "
          f"CRLB={c:.2f} cm  ratio={s/c:.3f}")
print()
print("解读：若实验 1 中 s_z ∝ 初值 σ，且实验 2 中 s_z 随 nfev 增大而趋向 CRLB，")
print("      则 ratio=0.261 的根因是【弱可观测方向上优化未走到最小值，ẑ 滞留初值附近】。")
