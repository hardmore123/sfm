"""
R-X3 阶段 B：**完整联合 BA** 侧实测（位姿 + 多路标同时估计）
==============================================================

阶段 A 是"位姿冻结、只估单路标"，严格说是单点定位而非 BA。
本阶段用 `ba_improve34.SonarBA34` 联合估计位姿与全部路标，才是 §9 要求的"真跑 BA"。

## 为什么选 SonarBA34（而不是 ba_unified）

| 需求 | SonarBA34 | ba_unified |
|---|---|---|
| z 是直接状态量（不经 (ψ,r,elev) 换元） | ✅ 世界笛卡尔 XYZ | ❌ 相对球坐标，z 的方差会依赖 base_frame 位姿 |
| 可关掉全部鲁棒/截断 | ✅ `loss="linear"` | ❌ 最终一次求解写死 `loss="huber"` |
| 无仰角箱式 bounds | ✅ | ❌ ±0.30 rad，触界即截断估计 ⇒ s_z 偏小 |
| 无欠约束仰角网格搜索 | ✅ | ❌ elev 被量化到 61 格 ⇒ s_z 由格距决定 |
| 有解析 Jacobian 可直接算 Λ | ✅ `jac_analytic` | ❌ 数值 jac |

## 必须关掉的东西（否则 s_z 失真，就成了"自证"）

- `w_lmprior = 0`：路标弱先验默认 1.0，会把路标拉向初值。初值若取真值，
  这就是收缩偏置 ⇒ s_z 系统性偏小。**这正是"预测=实测"陷阱的一种形态。**
- `loss="linear"`：Huber 会削弱大残差，改变方差。
- 初值加扰动：避免"从真值出发一步不动"。

## ⚠️ 一个已被诊断出并修正的设计错误（务必不要改回去）

首版把**位姿初值也加了 σ=1 cm 的扰动**，结果 ratio 高达 1.47–1.57。诊断过程：

| 检查 | 结果 | 排除了什么 |
|---|---|---|
| max_nfev 60 → 600 的 z 漂移 | 仅 0.038 cm | 不是未收敛 |
| z_hat 的 robust std vs std | 15.30 vs 15.11，离群点 0 | 不是局部极小/离群 |
| 联合 CRLB 对 pinv rcond | 1e-15…1e-8 全给 8.865 cm | 不是数值病态 |
| 位姿冻结、8 帧的同口径对照 | ratio **1.095 ✅** | MC 框架与 CRLB 实现都对 |
| MC 中各帧位姿 z 的抖动 | **1.097 cm，8 帧几乎相同** | ⇒ 整体平移模式 |

**根因**：`SonarBA34` 的首帧先验是 `w_prior·(poses[0] − poses0[0])`，其中 `poses0`
就是构造时传入的位姿数组。若传入带扰动的初值，就等于**把锚点钉在错误位置**，
整个解随之整体平移，而这个误差源**不在 CRLB 里**（CRLB 只反映观测噪声）。

**修正**：位姿初值用真值（锚点正确），位姿的不确定度改由**带噪的 odom 测量**引入，
权重取 `1/σ_odom` ⇒ 该不确定度就被联合 Λ 正确计入，MC 与 CRLB 口径一致。

## 两个子档（递进，用来隔离位姿不确定度的贡献）

odom 一律是**带噪测量**（真值相对位姿 + 高斯噪声），权重 = 1/σ：

- **B1 里程计精**（σ_t=1 mm, σ_r=0.1 mrad）：位姿近似已知 ⇒ 应复现阶段 A 的 s_z。
- **B2 里程计粗**（σ_t=1 cm, σ_r=1 mrad）：位姿不确定度传入路标 ⇒ s_z 应更大。
  这不是失败，而是"联合估计的代价"；关键是**各档都与自己的联合 `[Λ⁻¹]_zz` 吻合**。

## 白化口径

残差 = `A·az + B − o_beam`。取 `calib=(1/σ_θ, 0, 1/σ_ρ, 0)`，
并令 `o_beam = θ_obs/σ_θ`、`o_range = ρ_obs/σ_ρ`
⇒ 残差 = `(az − θ_obs)/σ_θ`，与阶段 A 及 observability 完全同口径。
"""
from __future__ import annotations

import io
import json
import sys
import time
from pathlib import Path

import numpy as np

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import rx3_ba_crlb as X
import ba_improve34 as B34
import ba_optimize as base

N_TRIAL = 200          # 判据要求 M ≥ 200
RATIO_LO, RATIO_HI = 0.8, 1.3
N_KF = 8               # 关键帧数（全 60 帧联合 BA 太慢，均匀抽取）
N_LM_PER_PILLAR = 4    # 柱面环上路标数（总路标 M = 2*该值 + 1）
MAX_NFEV = 60          # 见下方"关于 nfev 用满"的说明

# 关于 nfev 用满：`SonarBA34.solve` 内部写死 xtol=ftol=1e-10，trf 很难满足，
# 故 nfev 常等于 max_nfev。实测 max_nfev=60 与 100 得到**完全相同的 cost**
# （46.5），说明 60 次已收敛，用满上限不代表未收敛。为避免误读，本脚本
# 记录 cost 与其期望值（0.5·自由度）的比值作为收敛性证据。

CALIB_W = (1.0 / X.SIGMA_THETA, 0.0, 1.0 / X.SIGMA_RHO, 0.0)   # 白化 calib


def build_problem(heave=1.2, seed=801):
    """构建联合 BA 问题：关键帧位姿、柱面路标、可见观测。

    路标取柱体侧面 + 柱顶环，保证柱顶点（★I-1 关心的那个）在其中。
    """
    cfg = X.make_cfg(heave=heave, seed=seed)
    from trajectory import make_poses
    poses6_all, _ = make_poses(cfg)
    kf = np.linspace(0, len(poses6_all) - 1, N_KF).astype(int)
    poses6 = poses6_all[kf].copy()

    h = cfg.scene.h_avg_m
    rng = np.random.default_rng(seed)
    lms = [np.array([X.D_T, 0.0, h])]                     # 0 号 = 柱顶中心（关心它的 z）
    ang = np.linspace(0, 2 * np.pi, N_LM_PER_PILLAR, endpoint=False)
    for a in ang:                                          # 柱顶环 + 侧面点
        lms.append(np.array([X.D_T + X.R_PILLAR * np.cos(a),
                             X.R_PILLAR * np.sin(a),
                             h]))
        lms.append(np.array([X.D_T + X.R_PILLAR * np.cos(a),
                             X.R_PILLAR * np.sin(a),
                             h * rng.uniform(0.3, 0.8)]))
    lms = np.array(lms)

    # 可见观测（体系孔径判定）
    obs = []
    for i, p in enumerate(poses6):
        for j, P in enumerate(lms):
            if len(X.visible_frames(P, p.reshape(1, 6))) == 1:
                th, rh = X.project(P, p)
                obs.append((i, j, th, rh))
    return poses6, lms, obs


def make_observations(obs, rng):
    """加噪并预缩放成白化观测：(pose, lm, theta, rho, theta/σ_θ, rho/σ_ρ)。"""
    out = []
    for (i, j, th, rh) in obs:
        th_n = th + rng.normal(0.0, X.SIGMA_THETA)
        rh_n = rh + rng.normal(0.0, X.SIGMA_RHO)
        out.append((i, j, th_n, rh_n, th_n / X.SIGMA_THETA, rh_n / X.SIGMA_RHO))
    return out


def joint_crlb_z(ba, x, lm_idx=0):
    """从解处的解析 Jacobian 取联合 [Λ⁻¹]_zz（含位姿，边缘化后的 z 方差）。

    Λ = JᵀJ（残差已白化 ⇒ 无需再乘 Σ⁻¹）。
    变量布局：[poses(6K), landmarks(3M)] ⇒ 路标 j 的 z 在列 6K + 3j + 2。
    """
    J = ba.jac_analytic(x)
    Lam = (J.T @ J).toarray()
    col = 6 * ba.K + 3 * lm_idx + 2
    # 用伪逆：首帧先验虽固定规范，数值上仍可能接近奇异
    Lam_inv = np.linalg.pinv(Lam, rcond=1e-12)
    return float(np.sqrt(max(Lam_inv[col, col], 0.0)))


def noisy_odom(poses6, sigma_t, sigma_r, rng):
    """带噪的相邻帧相对位姿测量：T_meas = T_true · exp(噪声)。

    这是物理上正确的做法——里程计是**测量**，本身有噪声。
    权重取 1/σ 后，该不确定度会被联合 Λ 正确计入。
    """
    out = []
    for k in range(len(poses6) - 1):
        T_true = (np.linalg.inv(base.pose6_to_matrix(poses6[k]))
                  @ base.pose6_to_matrix(poses6[k + 1]))
        dt = rng.normal(0.0, sigma_t, 3)
        dr = rng.normal(0.0, sigma_r, 3)
        T_pert = np.eye(4)
        T_pert[:3, :3] = base.euler_to_matrix(dr[0], dr[1], dr[2])
        T_pert[:3, 3] = dt
        out.append((k, T_true @ T_pert))
    return out


def run_variant(name, heave, sigma_odom_t, sigma_odom_r, seed, n_trial=N_TRIAL):
    poses6, lms, obs = build_problem(heave=heave, seed=seed)
    K, M, N = len(poses6), len(lms), len(obs)
    # 白化：odom 残差除以 σ ⇒ 权重 = 1/σ
    weights = dict(prior=1000.0,
                   odomT=1.0 / sigma_odom_t, odomR=1.0 / sigma_odom_r,
                   sonar=1.0, lmprior=0.0)          # ★ lmprior=0，关掉路标先验

    rng = np.random.default_rng(seed * 7 + 1)
    z_hat, n_fail, costs, crlbs = [], 0, [], []
    # 有效自由度：lmprior=0 使 3M 个路标先验残差恒为 0，不计入
    n_res_eff = 6 + 6 * (K - 1) + 2 * N
    dof = max(n_res_eff - (6 * K + 3 * M), 1)
    for _t in range(n_trial):
        obs_n = make_observations(obs, rng)
        # ★ 位姿初值必须用真值：首帧先验会把第 0 帧锚在 poses0[0]，
        #   若传扰动值就等于把锚点放错，整个解整体平移（见文件头"设计错误"一节）。
        p_init = poses6.copy()
        # 每次试验重新抽 odom 测量噪声（这才是位姿不确定度的来源）
        odom_rel = noisy_odom(poses6, sigma_odom_t, sigma_odom_r, rng)
        # 路标初值仍加扰动，避免"从真值出发一步不动"的假象
        l_init = lms + rng.normal(0.0, 0.05, size=lms.shape)
        ba = B34.SonarBA34(p_init, l_init, obs_n, odom_rel, CALIB_W, weights=weights)
        try:
            _poses, _lms, res, _dt = ba.solve(jac_mode="analytic", loss="linear",
                                              max_nfev=MAX_NFEV, verbose=0)
        except Exception:
            n_fail += 1
            continue
        if not np.isfinite(res.cost):
            n_fail += 1
            continue
        z_hat.append(float(_lms[0, 2]))
        costs.append(float(res.cost))
        # 每次试验都算联合界，最后取中位数（避免只取一次遇到异常解）
        crlbs.append(joint_crlb_z(ba, res.x, lm_idx=0))

    z_hat = np.asarray(z_hat)
    s_z = float(z_hat.std(ddof=1)) if z_hat.size > 1 else float("nan")
    bias = float(z_hat.mean() - lms[0, 2]) if z_hat.size else float("nan")
    crlb_j = float(np.median(crlbs)) if crlbs else None
    return dict(name=name, heave=heave,
                sigma_odom_t=sigma_odom_t, sigma_odom_r=sigma_odom_r,
                K=K, M=M, n_obs=N,
                s_z_cm=s_z * 100, bias_cm=bias * 100,
                joint_crlb_cm=(crlb_j * 100) if crlb_j else None,
                joint_crlb_iqr_cm=(float(np.percentile(crlbs, 75)
                                         - np.percentile(crlbs, 25)) * 100)
                if len(crlbs) > 3 else None,
                ratio=(s_z / crlb_j) if (crlb_j and crlb_j > 0) else None,
                cost_median=float(np.median(costs)) if costs else None,
                cost_expected=0.5 * dof,
                cost_over_expected=(float(np.median(costs)) / (0.5 * dof))
                if costs else None,
                n_effective=int(z_hat.size), n_fail=n_fail)


# ================================================================
# 主流程（**必须有 __main__ 保护**：本模块会被 import 用于计时/复核，
# 若主流程写在模块级，import 就会触发整轮蒙特卡洛。项目里 `_f8_design_sceneset.py`
# 同样加了这个保护。）
# ================================================================
VARIANTS = [
    # name,                  heave, σ_odom_t(m), σ_odom_r(rad), seed
    ("B1_M1_odom_fine",        1.2, 1e-3, 1e-4, 801),
    ("B1_M2_odom_fine",        0.1, 1e-3, 1e-4, 802),
    ("B2_M1_odom_coarse",      1.2, 1e-2, 1e-3, 811),
    ("B2_M2_odom_coarse",      0.1, 1e-2, 1e-3, 812),
]


def main(n_trial=N_TRIAL):
    print("=" * 96)
    print("R-X3 阶段 B · 完整联合 BA（位姿 + 多路标）实测 vs 联合 CRLB")
    print("=" * 96)
    print("SonarBA34，loss=linear，w_lmprior=0（关掉路标先验），解析 Jacobian")
    print(f"关键帧 {N_KF}，蒙特卡洛 {n_trial} 次/档，每次重新加噪 + 初值扰动 + 真跑优化")

    report = {"generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
              "n_trial": n_trial, "n_keyframe": N_KF,
              "criterion": f"s_z/joint_CRLB in [{RATIO_LO}, {RATIO_HI}]",
              "variants": []}

    print()
    print(f"{'档位':<22}{'heave':>6}{'σ_odom':>9}{'K':>4}{'M':>4}{'Nobs':>6}"
          f"{'联合CRLB':>11}{'MC实测':>10}{'ratio':>8}{'bias':>9}{'判定':>6}")
    print("-" * 100)

    all_pass = True
    t0 = time.time()
    for (nm, hv, ot, orr, sd) in VARIANTS:
        r = run_variant(nm, hv, ot, orr, sd, n_trial=n_trial)
        ok = (r["ratio"] is not None) and (RATIO_LO <= r["ratio"] <= RATIO_HI)
        r["passed"] = bool(ok)
        all_pass = all_pass and ok
        report["variants"].append(r)
        cr = f"{r['joint_crlb_cm']:.2f}c" if r["joint_crlb_cm"] else "  n/a"
        rt = f"{r['ratio']:.3f}" if r["ratio"] else "  n/a"
        print(f"{nm:<22}{hv:>6.1f}{r['sigma_odom_t']*100:>8.1f}c"
              f"{r['K']:>4}{r['M']:>4}{r['n_obs']:>6}"
              f"{cr:>11}{r['s_z_cm']:>9.2f}c{rt:>8}{r['bias_cm']:>+8.2f}c"
              f"{'✅' if ok else '❌':>6}")

    print("-" * 100)
    print(f"耗时 {time.time()-t0:.0f}s")

    report["overall_passed"] = bool(all_pass)
    print()
    print(f"阶段 B 判定：{'✅ 通过' if all_pass else '❌ 未通过'}"
          f"（每档 MC 实测与其自身联合 CRLB 吻合，ratio ∈ [{RATIO_LO}, {RATIO_HI}]）")
    print()
    print("解读：")
    print("  B1（位姿强约束）应接近阶段 A 的位姿已知界；")
    print("  B2（位姿自由）的 s_z 应 ≥ B1——差值就是位姿不确定度对高度的贡献。")
    print("  两档各自与自己的联合 [Λ⁻¹]_zz 吻合，才说明 BA 与协方差实现都对。")

    out = Path(__file__).with_name("rx3_stageB_report.json")
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[报告] {out}")
    return all_pass


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else N_TRIAL
    sys.exit(0 if main(n_trial=n) else 1)
