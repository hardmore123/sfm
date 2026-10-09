"""
T7 验收：高度精度的双通道式（斜距通道 + 横滚激活的方位通道）
==============================================================

待验证的公式（理论修正 T7）：

    σ_rng = σ_ρ · cos φ̄ / (√N · std φ)                      斜距通道（含 cos φ̄ 因子）
    σ_az  = ρ̄ · σ_θ / (√N · std(roll) · cos θ_p)             横滚激活的方位通道
    σ_Pz^-2 ≈ σ_rng^-2 + σ_az^-2                             两通道信息相加

三条独立路径互校（方法论 §8.2）：
  路径 1  严格 CRLB  sqrt([Λ⁺]_zz)            observability.py（完整 3×3 雅可比）
  路径 2  双通道解析式                         本脚本，只用 std φ、std roll、ρ̄
  路径 3  蒙特卡洛真跑非线性优化的 s_z         rx3_ba_crlb.mc_frozen_pose

判据：
  V1  roll=0 时，严格 CRLB 与斜距单通道式相对偏差 ≤ 2%
  V2  各 roll 档，双通道式 / 严格 CRLB ∈ [0.85, 1.15]
  V3  各 roll 档，MC s_z / 严格 CRLB ∈ [0.8, 1.3]（禁止赋值构造，每个 s_z 来自真实优化）
  V4  同一起伏下，roll 幅度增大 ⇒ 严格 CRLB 单调下降（横滚确实提供高度信息）

只改轨迹的 roll 列，其余几何与主档 gen_scenes_main_f8 完全一致。
报告自写 UTF-8：t7_roll_channel_report.json / .txt
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
import feasibility as F

N_TRIAL = 300
THP = np.deg2rad(X.PITCH_DEG)
OUT_DIR = Path(__file__).resolve().parent

_buf = []


def out(s=""):
    print(s, flush=True)
    _buf.append(s)


def set_roll(poses6, mode, amp_deg):
    """替换 roll 列。mode: zero / sine（与 trajectory.py 同形，幅度可调）/ bangbang。"""
    p = poses6.copy()
    n = len(p)
    t = np.linspace(0.0, 1.0, n)
    a = np.deg2rad(amp_deg)
    if mode == "zero":
        p[:, 3] = 0.0
    elif mode == "sine":
        p[:, 3] = a * np.sin(2 * np.pi * t)
    elif mode == "bangbang":
        p[:, 3] = np.where(np.arange(n) % 2 == 0, a, -a)
    else:
        raise ValueError(mode)
    return p


def dual_channel(P, poses6, idx):
    phi = X.world_ray_elev(poses6[idx], P)
    N = len(idx)
    s_phi = float(np.std(phi))
    phibar = float(np.mean(phi))
    rho = float(np.mean(np.linalg.norm(P - poses6[idx, :3], axis=1)))
    s_roll = float(np.std(poses6[idx, 3]))
    s_rng = X.SIGMA_RHO * np.cos(phibar) / (np.sqrt(N) * s_phi) if s_phi > 1e-12 else np.inf
    s_az = (rho * X.SIGMA_THETA / (np.sqrt(N) * s_roll * np.cos(THP))) if s_roll > 1e-12 else np.inf
    inv2 = (0.0 if np.isinf(s_rng) else s_rng ** -2) + (0.0 if np.isinf(s_az) else s_az ** -2)
    s_cmb = inv2 ** -0.5 if inv2 > 0 else np.inf
    old = X.sigma_pz_std_phi_formula(s_phi, N)          # 旧近似式（无 cos、无 roll）
    lib = F.sigma_pz_dual_channel(X.SIGMA_RHO, X.SIGMA_THETA, N, s_phi, phibar,
                                  s_roll, rho, THP)["sigma_pz"]
    return dict(N=N, std_phi_deg=np.degrees(s_phi), std_roll_deg=np.degrees(s_roll),
                rho=rho, s_rng=s_rng, s_az=s_az, s_cmb=s_cmb, s_old=old, s_lib=lib)


CASES = [
    # (场景, heave, seed, roll 模式, 幅度°)
    ("M1", 1.2, 801, "zero", 0.0),
    ("M1", 1.2, 801, "sine", 2.865),      # 与 trajectory.py 硬编码 0.05 rad 相同
    ("M1", 1.2, 801, "bangbang", 10.0),
    ("M2", 0.1, 802, "zero", 0.0),
    ("M2", 0.1, 802, "sine", 2.865),
    ("M2", 0.1, 802, "bangbang", 5.0),
    ("M2", 0.1, 802, "bangbang", 10.0),
]

out("=" * 118)
out("T7 验收 · 双通道高度精度式（斜距 + 横滚激活的方位通道），三条独立路径互校")
out("=" * 118)
out(f"主档：σ_ρ={X.SIGMA_RHO*1000:.0f}mm σ_θ={np.degrees(X.SIGMA_THETA):.2f}° θ_p={X.PITCH_DEG}° "
    f"D_t={X.D_T} h={X.H_TRUE} N_frames={X.N_FRAMES}；MC {N_TRIAL} 次/档（真跑优化）")
out("")
out(f"{'场景':<4}{'roll':>9}{'可见':>5}{'stdφ°':>8}{'stdroll°':>9}"
    f"{'严格CRLB':>10}{'旧式':>9}{'斜距通道':>10}{'方位通道':>10}{'双通道':>9}"
    f"{'双/严格':>8}{'MC s_z':>9}{'MC/严格':>8}")
out("-" * 118)

rows = []
t0 = time.time()
for name, hv, sd, mode, amp in CASES:
    poses6, P, _idx, _ = X.build_scene(heave=hv, seed=sd)
    p = set_roll(poses6, mode, amp)
    idx = X.visible_frames(P, p)
    if len(idx) < 3:
        out(f"{name:<4}{mode}{amp:>5.1f}  可见帧不足({len(idx)})，跳过")
        continue
    cr = X.crlb_frozen_pose(P, p, idx)["sigma_Pz"]
    dc = dual_channel(P, p, idx)
    mc = X.mc_frozen_pose(P, p, idx, n_trial=N_TRIAL, seed=sd * 13 + int(amp * 10))
    tag = f"{mode[:4]}{amp:.1f}"
    fmt = lambda v: f"{v*100:>8.2f}c" if np.isfinite(v) else f"{'inf':>9}"
    out(f"{name:<4}{tag:>9}{dc['N']:>5}{dc['std_phi_deg']:>8.3f}{dc['std_roll_deg']:>9.3f}"
        f"{cr*100:>9.2f}c{fmt(dc['s_old'])}{fmt(dc['s_rng']):>10}{fmt(dc['s_az']):>10}"
        f"{fmt(dc['s_cmb'])}{dc['s_cmb']/cr:>8.3f}{mc.s_z*100:>8.2f}c{mc.s_z/cr:>8.3f}")
    rows.append(dict(scene=name, heave=hv, roll_mode=mode, roll_amp_deg=amp,
                     n_visible=dc["N"], std_phi_deg=dc["std_phi_deg"],
                     std_roll_deg=dc["std_roll_deg"], rho_mean_m=dc["rho"],
                     crlb_strict_cm=cr * 100,
                     old_formula_cm=dc["s_old"] * 100 if np.isfinite(dc["s_old"]) else None,
                     range_channel_cm=dc["s_rng"] * 100 if np.isfinite(dc["s_rng"]) else None,
                     azimuth_channel_cm=dc["s_az"] * 100 if np.isfinite(dc["s_az"]) else None,
                     dual_channel_cm=dc["s_cmb"] * 100,
                     dual_channel_lib_cm=dc["s_lib"] * 100,
                     ratio_dual_over_strict=dc["s_cmb"] / cr,
                     mc_s_z_cm=mc.s_z * 100, ratio_mc_over_strict=mc.s_z / cr,
                     mc_bias_cm=mc.bias_z * 100, mc_n_eff=int(mc.z_hat.size)))
out("-" * 118)
out(f"耗时 {time.time()-t0:.0f}s")

# ---------------- 判据 ----------------
out("")
v1_rows = [r for r in rows if r["roll_mode"] == "zero"]
v1 = all(abs(r["range_channel_cm"] / r["crlb_strict_cm"] - 1) <= 0.02 for r in v1_rows)
v2 = all(0.85 <= r["ratio_dual_over_strict"] <= 1.15 for r in rows)
v3 = all(0.8 <= r["ratio_mc_over_strict"] <= 1.3 for r in rows)
v4 = True
for sc in ("M1", "M2"):
    rr = sorted([r for r in rows if r["scene"] == sc], key=lambda r: r["std_roll_deg"])
    cs = [r["crlb_strict_cm"] for r in rr]
    v4 = v4 and all(b <= a + 1e-9 for a, b in zip(cs, cs[1:]))

for r in v1_rows:
    out(f"  V1 细节 {r['scene']} roll=0：斜距通道 {r['range_channel_cm']:.3f} vs 严格 "
        f"{r['crlb_strict_cm']:.3f} cm，偏差 {(r['range_channel_cm']/r['crlb_strict_cm']-1)*100:+.2f}%")
out(f"V1 roll=0 时斜距单通道式与严格 CRLB 偏差 ≤2%      ：{'✅' if v1 else '❌'}")
out(f"V2 双通道式 / 严格 CRLB ∈ [0.85, 1.15]             ：{'✅' if v2 else '❌'}")
out(f"V3 MC s_z / 严格 CRLB ∈ [0.8, 1.3]（真跑优化）     ：{'✅' if v3 else '❌'}")
out(f"V4 同起伏下 roll 增大 ⇒ 严格 CRLB 单调下降          ：{'✅' if v4 else '❌'}")
v5 = all(abs(r["dual_channel_lib_cm"] - r["dual_channel_cm"]) < 1e-9 for r in rows)
t_old = F.tau_z_crit(0.01, 10, np.deg2rad(7.5), mode="abs")
t_cos = F.tau_z_crit(0.01, 10, np.deg2rad(7.5), mode="abs", cos_phi_bar=1.0)
v5 = bool(v5 and abs(t_old - t_cos) < 1e-15)      # 默认参数向后兼容
out(f"V5 feasibility 库函数与本脚本式一致、tau_z_crit 向后兼容：{'✅' if v5 else '❌'}")
ok = v1 and v2 and v3 and v4 and v5
out("")
out(f"T7 总判定：{'✅ 通过' if ok else '❌ 未通过'}")
out("")
out("解读：roll=0 时只剩斜距通道，此时严格界=斜距单通道式（含 cos φ̄）。")
out("      roll≠0 时方位通道开始提供高度信息，严格界下降——斜距通道的'孔径上限'不再是全部上限。")

rep = dict(generated_at=time.strftime("%Y-%m-%d %H:%M:%S"), n_trial=N_TRIAL,
           criteria=dict(V1=v1, V2=v2, V3=v3, V4=v4, V5=v5), passed=ok, rows=rows)
(OUT_DIR / "t7_roll_channel_report.json").write_text(
    json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
(OUT_DIR / "t7_roll_channel_report.txt").write_text("\n".join(_buf), encoding="utf-8")
sys.exit(0 if ok else 1)
