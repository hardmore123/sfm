"""核心公式推导核验：σ_Pz 到底由哪些信息通道决定。

假设 H：σ_Pz ≈ σ_ρ/(√N·stdφ) 只是【斜距通道 + 固定方位 + 小离散】的近似，
  (a) 严格的斜距通道应带 cos(φ̄) 因子；
  (b) 横滚(roll)随时间变化时，方位通道也提供高度信息：
      σ_z,az ≈ ρ·σ_θ / (√N · std(roll) · cos θ_p)
  两通道信息相加：σ_z^-2 ≈ σ_rng^-2 + σ_az^-2

判别：把 roll 列清零重算严格 CRLB——若 H 成立，M2 的严格界应从 ~12 cm 跳回 ~46 cm。
"""
import io
import os
import sys

sys.path.insert(0, r"F:\sfm\论文代码与数据\02_代码")
os.chdir(r"F:\sfm\论文代码与数据\02_代码")
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import numpy as np
import rx3_ba_crlb as X

S_RHO, S_TH = X.SIGMA_RHO, X.SIGMA_THETA
THP = np.deg2rad(X.PITCH_DEG)

print("=" * 100)
print("(1) 斜距通道的严格式：σ_z = σ_ρ·sqrt(Σcos²φ / Σ_{j<k} sin²(φ_k−φ_j))  ≈  σ_ρ·cosφ̄/(√N·stdφ)")
print("    用 verify_observability_theory 的 5 组公开数据检验 cosφ̄ 因子：")
print("=" * 100)
rows = [("下俯20° 无起伏 N=10", 19.36, 15.78, 14.89),
        ("下俯20° 起伏0.2m", 19.34, 18.76, 17.71),
        ("下俯20° 起伏0.8m", 19.30, 16.61, 15.68),
        ("水平0°  起伏0.8m", 19.30, 16.61, 15.68),
        ("下俯20° 起伏0.8m N=30", 19.29, 10.86, 10.25)]
print(f"{'构型':<24}{'φ̄°':>7}{'旧式(无cos)':>12}{'×cosφ̄':>10}{'实测':>8}{'残差':>8}")
for n, ph, old, meas in rows:
    new = old * np.cos(np.deg2rad(ph))
    print(f"{n:<24}{ph:>7.2f}{old:>12.2f}{new:>10.2f}{meas:>8.2f}{(new-meas)/meas*100:>7.2f}%")

print()
print("=" * 100)
print("(2) 横滚通道：主档 M1/M2，原轨迹（含硬编码 roll ±2.9°）vs roll 清零")
print("=" * 100)
hdr = (f"{'场景':<6}{'roll':>8}{'stdφ°':>8}{'std roll°':>10}{'严格CRLB':>10}"
       f"{'斜距通道':>10}{'方位通道':>10}{'两通道合成':>11}{'合成/严格':>10}")
print(hdr)
for name, hv, sd in [("M1", 1.2, 801), ("M2", 0.1, 802)]:
    poses6, P, idx, std_phi = X.build_scene(heave=hv, seed=sd)
    for tag in ("原轨迹", "roll=0"):
        p = poses6.copy()
        if tag == "roll=0":
            p[:, 3] = 0.0
        idx2 = X.visible_frames(P, p)
        cr = X.crlb_frozen_pose(P, p, idx2)["sigma_Pz"]
        phi = X.world_ray_elev(p[idx2], P)
        N = len(idx2)
        sphi = np.std(phi); phibar = np.mean(phi)
        rho = np.mean(np.linalg.norm(P - p[idx2, :3], axis=1))
        sroll = np.std(p[idx2, 3])
        s_rng = S_RHO * np.cos(phibar) / (np.sqrt(N) * sphi)
        s_az = (rho * S_TH / (np.sqrt(N) * sroll * np.cos(THP))) if sroll > 1e-12 else np.inf
        s_cmb = 1.0 / np.sqrt(1 / s_rng ** 2 + (0 if np.isinf(s_az) else 1 / s_az ** 2))
        print(f"{name:<6}{tag:>8}{np.degrees(sphi):>8.3f}{np.degrees(sroll):>10.3f}"
              f"{cr*100:>9.2f}c{s_rng*100:>9.2f}c"
              f"{(s_az*100 if np.isfinite(s_az) else float('inf')):>9.2f}c"
              f"{s_cmb*100:>10.2f}c{s_cmb/cr:>10.3f}")

print()
print("=" * 100)
print("(3) 横滚能否突破斜距'硬界' τ_abs=σ_ρ/(√N φ_max)？ ARIS N=10, ρ≈11.7m, θ_p=19°")
print("=" * 100)
N = 10; rho = 11.7; phimax = np.deg2rad(7.5)
t_abs = S_RHO / (np.sqrt(N) * phimax)
print(f"斜距通道硬界 τ_abs = {t_abs*100:.2f} cm")
for deg in (2.9, 5, 10, 15, 20, 30):
    sr = np.deg2rad(deg)            # bang-bang roll ±deg ⇒ std = deg
    s_az = rho * S_TH / (np.sqrt(N) * sr * np.cos(THP))
    cmb = 1 / np.sqrt(1 / t_abs ** 2 + 1 / s_az ** 2)
    print(f"  roll ±{deg:>4.1f}° (bang-bang): 方位通道 {s_az*100:6.2f} cm  "
          f"⇒ 两通道合成 {cmb*100:5.2f} cm  {'< 硬界' if cmb < t_abs else ''}")

print()
print("=" * 100)
print("(4) T6 / R1 的'自动吻合'：A = D_t·tanφ_max 与单侧起伏约定")
print("=" * 100)
Dt = X.D_T; zs = X.Z_S; h = X.H_TRUE
lo, hi = THP - phimax, THP + phimax
full = Dt * (np.tan(hi) - np.tan(lo))
half_up = Dt * (np.tan(hi) - np.tan(THP))
print(f"D_t·tanφ_max                          = {Dt*np.tan(phimax):.2f} m  （R1/T6 给的 A）")
print(f"目标从孔径中心扫到上沿所需单侧起伏    = {half_up:.2f} m  （≈D_t·tanφ/cos²θ_p）")
print(f"目标扫满整个孔径(±φ_max)所需峰峰值    = {full:.2f} m  （Popoviciu 上界 std=φ_max 需要这个）")
print(f"trajectory.py 的 heave 是单侧 z∈[z_s, z_s+A] ⇒ A 是峰峰值")
