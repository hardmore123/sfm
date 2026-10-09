"""
σ_θ 台账验收：方位噪声取值对 ★I-1 结论的敏感性（配套 sigma_theta_ledger.md）
============================================================================

T7 后，高度精度的方位通道 σ_z,θ ∝ σ_θ。σ_θ 原是未记账的假设值（0.18°），
本脚本回答三个问题：
  Q1  主档 M1/M2 的严格 CRLB 随 σ_θ 如何变化（取 σ_θ 合理区间的全部端点）
  Q2  M2 "盲"（σ_Pz > τ_z）这一判定在多大 σ_θ 下翻转——临界 σ_θ*
  Q3  斜距通道（roll=0）的结论是否与 σ_θ 无关（应当无关）

判据：
  L1  roll=0 时严格 CRLB 对 σ_θ 不敏感（全区间变化 ≤ 1%）——斜距通道结论稳健
  L2  M1 在全区间内都 ≤ τ_z（良约束判定稳健）
  L3  报告 M2 的临界 σ_θ*（不设通过阈值，如实给出，供台账引用）
  L4  MC 抽检两个端点（σ_θ 最小/最大），MC/严格 ∈ [0.8, 1.3]（端点处公式仍可信）

输出自写 UTF-8：sigma_theta_ledger_report.json / .txt
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
import observability as OBS

OUT_DIR = Path(__file__).resolve().parent
TAU_Z = X.TAU_Z

# σ_θ 合理区间的端点与关键取值（单位：度）——依据见 sigma_theta_ledger.md §2
SIGMA_THETA_DEG = [
    (0.072, "0.25°/√12：128 波束索引取整的量化极限（下界）"),
    (0.083, "0.25°/3：verify_observability_theory 旧取值"),
    (0.10, "1.8 MHz 波束宽 0.3°/3（高 SNR 质心）"),
    (0.18, "现行主档取值（rx3/gen_scenes）"),
    (0.20, "Huang 2015 Table I / config.py 默认 / tracks 建议列"),
    (0.25, "一个波束间隔"),
    (0.30, "1.8 MHz 水平波束宽度（上界，等价于无亚波束能力）"),
]

_buf = []


def out(s=""):
    print(s, flush=True)
    _buf.append(s)


def strict_crlb(P, poses6, idx, s_th_rad):
    obs_by_lm = {0: [(int(i), 0.0, 0.0) for i in idx]}
    r = OBS.compute_observability_per_landmark(
        landmarks=P.reshape(1, 3), obs_by_lm=obs_by_lm, calib=(1.0, 0.0, 1.0, 0.0),
        poses6=poses6, tau_z=TAU_Z, sigma_rho=X.SIGMA_RHO, sigma_theta=s_th_rad)
    return float(r["sigma_Pz"][0])


def scene(heave, seed, zero_roll=False):
    poses6, P, _i, _s = X.build_scene(heave=heave, seed=seed)
    if zero_roll:
        poses6 = poses6.copy()
        poses6[:, 3] = 0.0
    idx = X.visible_frames(P, poses6)
    return poses6, P, idx


out("=" * 104)
out("σ_θ 台账验收 · 方位噪声取值对 ★I-1 结论的敏感性")
out("=" * 104)
out(f"主档：σ_ρ={X.SIGMA_RHO*1000:.0f}mm θ_p={X.PITCH_DEG}° τ_z={TAU_Z*100:.0f}cm；"
    f"轨迹 roll 为 trajectory.py 现行的 0.05·sin(2πt)（±2.9°）")
out("")

SC = {"M1": scene(1.2, 801), "M2": scene(0.1, 802),
      "M1_roll0": scene(1.2, 801, True), "M2_roll0": scene(0.1, 802, True)}

out(f"{'σ_θ(°)':>8} {'M1':>9} {'M2':>9} {'M1 roll0':>10} {'M2 roll0':>10}  M2判定  依据")
out("-" * 104)
table = []
for deg, why in SIGMA_THETA_DEG:
    s = np.deg2rad(deg)
    v = {k: strict_crlb(SC[k][1], SC[k][0], SC[k][2], s) for k in SC}
    blind = v["M2"] > TAU_Z
    table.append(dict(sigma_theta_deg=deg, basis=why,
                      **{f"crlb_{k}_cm": v[k] * 100 for k in v}, M2_blind=bool(blind)))
    out(f"{deg:>8.3f} {v['M1']*100:>8.2f}c {v['M2']*100:>8.2f}c "
        f"{v['M1_roll0']*100:>9.2f}c {v['M2_roll0']*100:>9.2f}c  "
        f"{'盲' if blind else '可观测':<5} {why}")
out("-" * 104)

# ---- Q2：M2 判定翻转的临界 σ_θ*（二分）----
P2, p2, i2 = SC["M2"][1], SC["M2"][0], SC["M2"][2]
lo, hi = np.deg2rad(0.01), np.deg2rad(1.0)
f = lambda s: strict_crlb(P2, p2, i2, s) - TAU_Z
if f(lo) < 0 < f(hi):
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        if f(mid) > 0:
            hi = mid
        else:
            lo = mid
    s_crit = np.degrees(0.5 * (lo + hi))
else:
    s_crit = float("nan")
out(f"Q2 M2 判定翻转的临界 σ_θ* = {s_crit:.4f}°  （σ_θ < σ_θ* 时 M2 不再是盲）")

# ---- 判据 ----
r0 = [r["crlb_M1_roll0_cm"] for r in table], [r["crlb_M2_roll0_cm"] for r in table]
l1 = all((max(c) - min(c)) / min(c) <= 0.01 for c in r0)
l2 = all(r["crlb_M1_cm"] <= TAU_Z * 100 for r in table)

# ---- L4：MC 抽检两端点 ----
out("")
out("L4 MC 抽检（M2，现行轨迹，300 次真跑优化）：")
mc_rows = []
saved = X.SIGMA_THETA
l4 = True
for deg in (SIGMA_THETA_DEG[0][0], SIGMA_THETA_DEG[-1][0]):
    X.SIGMA_THETA = np.deg2rad(deg)          # mc_frozen_pose 读模块级 σ_θ
    try:
        mc = X.mc_frozen_pose(P2, p2, i2, n_trial=300, seed=int(deg * 1e4))
    finally:
        X.SIGMA_THETA = saved
    cr = strict_crlb(P2, p2, i2, np.deg2rad(deg))
    ratio = mc.s_z / cr
    l4 = l4 and (0.8 <= ratio <= 1.3)
    mc_rows.append(dict(sigma_theta_deg=deg, crlb_cm=cr * 100, mc_cm=mc.s_z * 100, ratio=ratio))
    out(f"  σ_θ={deg:.3f}°  严格 {cr*100:.2f} cm  MC {mc.s_z*100:.2f} cm  ratio {ratio:.3f}")

out("")
out(f"L1 roll=0 时严格 CRLB 与 σ_θ 无关（变化 ≤1%）：{'✅' if l1 else '❌'}")
out(f"L2 M1 在 σ_θ 全区间内都 ≤ τ_z               ：{'✅' if l2 else '❌'}")
out(f"L3 M2 临界 σ_θ* = {s_crit:.3f}°（如实报告，不设阈值）")
out(f"L4 端点处 MC/严格 ∈ [0.8,1.3]                 ：{'✅' if l4 else '❌'}")
ok = bool(l1 and l2 and l4)
out(f"总判定：{'✅ 通过' if ok else '❌ 未通过'}")

rep = dict(generated_at=time.strftime("%Y-%m-%d %H:%M:%S"), tau_z_m=TAU_Z,
           table=table, M2_sigma_theta_crit_deg=s_crit, mc_check=mc_rows,
           criteria=dict(L1=bool(l1), L2=bool(l2), L4=bool(l4)), passed=ok)
(OUT_DIR / "sigma_theta_ledger_report.json").write_text(
    json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
(OUT_DIR / "sigma_theta_ledger_report.txt").write_text("\n".join(_buf), encoding="utf-8")
sys.exit(0 if ok else 1)
