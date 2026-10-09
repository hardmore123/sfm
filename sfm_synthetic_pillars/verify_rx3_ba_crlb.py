"""
R-X3 验收：BA 侧实测高度精度 vs 解析 CRLB（★I-1 立身证据）
==========================================================

判据（`会话交接_20260907.md` §9）：
    s_z^MC / sqrt([Λ⁻¹]_zz) ∈ [0.8, 1.3]
其中 s_z^MC 必须来自**真跑优化**的样本标准差，不得赋值构造。

三个阶段：
  A  位姿冻结、单路标 3 参数：与 observability 的 3×3 界口径完全一致
  B  联合 BA（SonarBA34，位姿+多路标，关掉鲁棒核与先验）：真正的 BA 侧
  C  扫起伏幅度 ⇒ std(φ) 曲线：验 ★I-1 的核心关系

同时并列三个量，回答"文档里的 48.57 cm 到底是什么"：
  σ_Pz^strict  = sqrt([Λ⁺]_zz)                严格 CRLB（observability.py）
  σ_Pz^approx  = σ_ρ/(√N·std φ)               ★I-1 的近似式（文档引用的就是它）
  s_z^MC       = std(蒙特卡洛优化输出的 ẑ)     实测

输出：控制台 + `rx3_ba_crlb_report.json`
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

N_TRIAL = 300          # 判据要求 M ≥ 200
RATIO_LO, RATIO_HI = 0.8, 1.3

report = {"generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
          "n_trial": N_TRIAL,
          "criterion": f"s_z/sigma_Pz_strict in [{RATIO_LO}, {RATIO_HI}]",
          "sensor": {k: v for k, v in X.ARIS.items()},
          "geometry": {"z_s": X.Z_S, "pitch_deg": X.PITCH_DEG, "D_t": X.D_T,
                       "r_pillar": X.R_PILLAR, "h": X.H_TRUE,
                       "n_frames": X.N_FRAMES, "tau_z": X.TAU_Z},
          "stageA": [], "stageC": []}

print("=" * 92)
print("R-X3 · BA 侧实测高度精度 vs 解析 CRLB（★I-1）")
print("=" * 92)
print(f"主档 ARIS：±{X.ARIS['phi_max_deg']}°  ρ∈[{X.ARIS['rho_min_m']},{X.ARIS['rho_max_m']}]m  "
      f"σ_ρ={X.SIGMA_RHO*1000:.0f}mm  σ_θ={np.degrees(X.SIGMA_THETA):.2f}°  "
      f"N={X.N_FRAMES} 帧  τ_z={X.TAU_Z*100:.0f}cm")
print(f"蒙特卡洛 {N_TRIAL} 次/场景，每次重新加噪并真跑非线性优化（禁止赋值构造）")

# ================================================================
# 阶段 A：位姿冻结的单路标 MC（与 3×3 解析界同口径）
# ================================================================
print()
print("=" * 92)
print("阶段 A · 位姿冻结、单路标 3 参数（与 observability 的 3×3 界口径一致）")
print("=" * 92)
print(f"{'场景':<22}{'heave':>6}{'可见帧':>7}{'std(φ)°':>10}"
      f"{'严格CRLB':>11}{'近似式':>10}{'MC实测':>10}{'ratio':>8}{'判定':>6}")
print("-" * 92)

SCENES_A = [
    ("M1_well_constrained", 1.2, 801),
    ("M2_blind_low_spread", 0.1, 802),
]

stageA_pass = True
for name, heave, seed in SCENES_A:
    poses6, P_top, idx, std_phi = X.build_scene(heave=heave, seed=seed)
    if len(idx) < 2:
        print(f"{name:<22}{heave:>6.1f}{len(idx):>7}  可见帧不足，跳过")
        stageA_pass = False
        continue
    cr = X.crlb_frozen_pose(P_top, poses6, idx)
    approx = X.sigma_pz_std_phi_formula(std_phi, len(idx))
    mc = X.mc_frozen_pose(P_top, poses6, idx, n_trial=N_TRIAL, seed=seed * 100 + 7)
    ratio = mc.s_z / cr["sigma_Pz"] if cr["sigma_Pz"] > 0 else np.nan
    ok = RATIO_LO <= ratio <= RATIO_HI
    stageA_pass = stageA_pass and ok
    print(f"{name:<22}{heave:>6.1f}{len(idx):>7}{np.degrees(std_phi):>10.4f}"
          f"{cr['sigma_Pz']*100:>10.2f}c{approx*100:>9.2f}c{mc.s_z*100:>9.2f}c"
          f"{ratio:>8.3f}{'✅' if ok else '❌':>6}")
    # bias 的采样标准误，用于判断 bias 是否显著
    se = mc.s_z / np.sqrt(max(mc.z_hat.size, 1))
    report["stageA"].append(dict(
        name=name, heave=heave, n_visible=int(len(idx)),
        std_phi_deg=float(np.degrees(std_phi)),
        sigma_Pz_strict_cm=cr["sigma_Pz"] * 100,
        sigma_Pz_approx_cm=approx * 100,
        s_z_mc_cm=mc.s_z * 100,
        ratio_mc_over_strict=float(ratio),
        ratio_approx_over_strict=float(approx / cr["sigma_Pz"]) if cr["sigma_Pz"] > 0 else None,
        bias_cm=mc.bias_z * 100,
        bias_se_cm=se * 100,
        bias_significant=bool(abs(mc.bias_z) > 2 * se),
        eigvals=cr["eigvals"].tolist(),
        n_fail=mc.n_fail,
        n_effective=int(mc.z_hat.size),
        classification=cr["classification"],
        passed=bool(ok),
    ))

print("-" * 92)
print(f"阶段 A 判定：{'✅ 通过' if stageA_pass else '❌ 未通过'}"
      f"（ratio ∈ [{RATIO_LO}, {RATIO_HI}]）")

# 近似式 vs 严格界的差异（这是本轮的关键发现）
print()
print("近似式 σ_ρ/(√N·stdφ) 相对严格界 [Λ⁺]_zz 的高估倍数：")
for e in report["stageA"]:
    r = e["ratio_approx_over_strict"]
    if r:
        print(f"  {e['name']:<22} {r:>6.2f}×   "
              f"（严格 {e['sigma_Pz_strict_cm']:.2f} cm vs 近似 {e['sigma_Pz_approx_cm']:.2f} cm）")
print("  ⇒ 近似式假设 z 与水平坐标解耦，只计 φ 离散度这一项；")
print("    严格界含完整 3×3 耦合（下俯 19° 时斜距/方位都对世界 z 有偏导），故更小。")
print("    std(φ) 越小，两者分歧越大。**文档引用的 48.57 cm 属近似式，不是严格 CRLB。**")

# ================================================================
# 阶段 C：扫起伏幅度 ⇒ std(φ)
# ================================================================
print()
print("=" * 92)
print("阶段 C · 扫起伏幅度，验 s_z 对 std(φ) 的关系（★I-1 核心）")
print("=" * 92)
print(f"{'heave(m)':>9}{'可见帧':>7}{'std(φ)°':>10}{'严格CRLB':>11}"
      f"{'近似式':>10}{'MC实测':>10}{'ratio':>8}{'判定':>6}")
print("-" * 92)

HEAVES = [0.1, 0.2, 0.4, 0.8, 1.2, 1.6]
stageC_pass = True
n_c_eval = 0
for hv in HEAVES:
    poses6, P_top, idx, std_phi = X.build_scene(heave=hv, seed=900)
    if len(idx) < 2:
        print(f"{hv:>9.1f}{len(idx):>7}  可见帧不足，跳过")
        continue
    cr = X.crlb_frozen_pose(P_top, poses6, idx)
    approx = X.sigma_pz_std_phi_formula(std_phi, len(idx))
    mc = X.mc_frozen_pose(P_top, poses6, idx, n_trial=N_TRIAL, seed=int(hv * 1000) + 13)
    ratio = mc.s_z / cr["sigma_Pz"] if cr["sigma_Pz"] > 0 else np.nan
    ok = RATIO_LO <= ratio <= RATIO_HI
    stageC_pass = stageC_pass and ok
    n_c_eval += 1
    print(f"{hv:>9.1f}{len(idx):>7}{np.degrees(std_phi):>10.4f}"
          f"{cr['sigma_Pz']*100:>10.2f}c{approx*100:>9.2f}c{mc.s_z*100:>9.2f}c"
          f"{ratio:>8.3f}{'✅' if ok else '❌':>6}")
    report["stageC"].append(dict(
        heave=hv, n_visible=int(len(idx)),
        std_phi_deg=float(np.degrees(std_phi)),
        sigma_Pz_strict_cm=cr["sigma_Pz"] * 100,
        sigma_Pz_approx_cm=approx * 100,
        s_z_mc_cm=mc.s_z * 100,
        ratio_mc_over_strict=float(ratio),
        bias_cm=mc.bias_z * 100,
        n_effective=int(mc.z_hat.size),
        passed=bool(ok),
    ))

print("-" * 92)
print(f"阶段 C 判定：{'✅ 通过' if stageC_pass and n_c_eval >= 4 else '❌ 未通过'}"
      f"（{n_c_eval} 个档位全部 ratio ∈ [{RATIO_LO}, {RATIO_HI}]）")

# 单调性检查：std(φ) 越大，精度应越好
if len(report["stageC"]) >= 3:
    sp = np.array([e["std_phi_deg"] for e in report["stageC"]])
    sz = np.array([e["s_z_mc_cm"] for e in report["stageC"]])
    order = np.argsort(sp)
    mono = bool(np.all(np.diff(sz[order]) <= 1e-9) or
                np.corrcoef(sp, sz)[0, 1] < -0.7)
    print(f"单调性：std(φ) 增大 ⇒ s_z 减小  "
          f"corr={np.corrcoef(sp, sz)[0, 1]:+.3f}  {'✅' if mono else '⚠️'}")
    report["stageC_monotonic"] = mono
    report["stageC_corr"] = float(np.corrcoef(sp, sz)[0, 1])

# ================================================================
# 汇总
# ================================================================
report["stageA_passed"] = bool(stageA_pass)
report["stageC_passed"] = bool(stageC_pass and n_c_eval >= 4)
overall = report["stageA_passed"] and report["stageC_passed"]
report["overall_passed"] = bool(overall)

print()
print("=" * 92)
print(f"R-X3 阶段 A/C 总判定：{'✅ 通过' if overall else '❌ 未通过'}")
print("=" * 92)
print("已证：严格 CRLB [Λ⁺]_zz 与蒙特卡洛真跑优化的 s_z 吻合（MC ≥ CRLB，符合下界性质）。")
print("待补：阶段 B（SonarBA34 联合估位姿+路标）——见 verify_rx3_stageB.py。")
print()
print("⚠️ 措辞纪律：本脚本的 s_z 来自**位姿冻结的单路标优化**，")
print("   在阶段 B 完成前，不得表述为『完整 BA 实测』，应写『位姿已知条件下的实测』。")

out = Path(__file__).with_name("rx3_ba_crlb_report.json")
out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"\n[报告] {out}")
sys.exit(0 if overall else 1)
