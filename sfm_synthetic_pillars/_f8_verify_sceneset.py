"""F-8d 场景集设计验收：逐场景校验 + binding 约束分布统计。

验收项：
  V1 M1/M3/M5 在 heave 全程可行；M4 应被判不可反演
  V2 M1 std(φ) ≥ Δφ_min（良约束）、M2 std(φ) < Δφ_min（盲）
  V3 Δρ_bin ∈ ARIS 规格 3–19 mm，τ_z_crit ≤ τ_z=5 cm
  V4 binding 约束分布：查明主档下最先卡住的是哪一个（★I-2 的可报告结果）
"""
import io, sys, json
import numpy as np
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, ".")
from _f8_design_sceneset import (check, check_heave, geom, std_phi_of_heave,
                                 PHI_MAX, RHO_MAX, DBIN, SIGMA_RHO_INJ, N_BINS)

D = json.load(open("_f8_sceneset_design.json", encoding="utf-8"))
Z_S = D["base_geometry"]["z_s_m"]
TP = np.deg2rad(D["base_geometry"]["pitch_deg"])
tau_z, N = 0.05, 10
dphi_min = SIGMA_RHO_INJ / (np.sqrt(N) * tau_z)

print("=" * 82)
print("V1+V2 逐场景校验")
print("=" * 82)
print(f"  Δφ_min = {np.degrees(dphi_min):.3f}°   (σ_ρ={SIGMA_RHO_INJ*1000:.0f}mm, N={N}, τ_z={tau_z*100:.0f}cm)")
print()
print(f"  {'场景':<22} {'h':>5} {'A':>5} {'std(φ)°':>8} {'离散度':>7} "
      f"{'全程可行':>8} {'L_s':>6} {'ρ_end':>7} {'可见段':>7}")
rows = []
for s in D["scenes"]:
    h, A, D_t = s["h_m"], s["heave_m"], s["D_t_m"]
    sp = std_phi_of_heave(Z_S, D_t, h, A)
    ok, inf = check_heave(Z_S, TP, D_t, h, A)
    _, De, Ls, rt, re, et = geom(Z_S, h, D_t)
    ok0, inf0 = check(Z_S, TP, D_t, h)
    vis = inf0.get("shadow_visible_frac", float("nan")) if ok0 else float("nan")
    rows.append((s["name"], ok, sp, inf))
    print(f"  {s['name']:<22} {h:>5.2f} {A:>5.2f} {np.degrees(sp):>8.3f} "
          f"{'良约束' if sp>=dphi_min else '盲':>7} "
          f"{'是' if ok else '否':>8} {Ls:>6.2f} {re:>7.2f} "
          f"{(f'{vis*100:.0f}%' if np.isfinite(vis) else '—'):>7}")
    if not ok:
        print(f"        └ 判不可反演，原因：{inf.get('fail','?')}"
              f"（z_s={inf.get('z_s_fail','?')}）")

# 预期
exp = {"M1_well_constrained": (True, "良约束"),
       "M2_blind_low_spread": (True, "盲"),
       "M3_envelope_inside": (True, None),
       "M4_envelope_outside": (False, None),
       "M5_low_snr": (True, None)}
print("\n  预期对照：")
v12 = True
for nm, ok, sp, inf in rows:
    e_ok, e_cls = exp[nm]
    cls = "良约束" if sp >= dphi_min else "盲"
    hit = (ok == e_ok) and (e_cls is None or cls == e_cls)
    v12 &= hit
    print(f"    {nm:<22} 期望{'可行' if e_ok else '不可行'}"
          f"{'/'+e_cls if e_cls else '':<8} 实际{'可行' if ok else '不可行'}/{cls:<6} "
          f"{'✅' if hit else '❌'}")
print(f"\n  V1+V2 判定: {'通过' if v12 else '未通过'}")

print()
print("=" * 82)
print("V3 采样与精度上限")
print("=" * 82)
tc = np.sqrt(3) * SIGMA_RHO_INJ / (np.sqrt(N) * PHI_MAX)
v3a = 0.003 <= DBIN <= 0.019
v3b = tc <= tau_z
print(f"  ρ_max={RHO_MAX} m / {N_BINS} bin ⇒ Δρ_bin={DBIN*1000:.2f} mm  "
      f"ARIS 规格 3-19mm: {'✅' if v3a else '❌'}")
print(f"  τ_z_crit={tc*100:.2f} cm ≤ τ_z={tau_z*100:.0f} cm: {'✅' if v3b else '❌'}")
print(f"  量化噪声 Δ/√12 = {DBIN/np.sqrt(12)*1000:.2f} mm "
      f"(≤ 注入 σ_ρ={SIGMA_RHO_INJ*1000:.0f}mm ⇒ 注入项主导: "
      f"{'✅' if DBIN/np.sqrt(12) <= SIGMA_RHO_INJ else '❌'})")
print(f"  V3 判定: {'通过' if (v3a and v3b) else '未通过'}")

print()
print("=" * 82)
print("V4 binding 约束分布（主档 ρ_max=15 m 下，谁最先卡住？）")
print("=" * 82)
from collections import Counter
cnt = Counter()
# 对每个 (θ_p, D_t)，沿 h 增大方向找第一个失败的约束
for tp_deg in range(12, 31):
    tp = np.deg2rad(tp_deg)
    for D_t in np.arange(3.0, 14.0, 0.2):
        last_ok = False
        for h in np.arange(0.10, 4.40, 0.02):
            ok, inf = check(Z_S, tp, D_t, h, margin_min_deg=0.0)
            if ok:
                last_ok = True
            elif last_ok:
                f = inf.get("fail", "?")
                key = f.split("（")[0].split(" ")[0]   # 取约束编号
                cnt[key] += 1
                break
tot = sum(cnt.values())
print(f"  共 {tot} 条 (θ_p, D_t) 扫描线，各约束成为 binding 的次数：")
for k, v in cnt.most_common():
    print(f"    {k:<8} {v:>5}  ({v/tot*100:>5.1f}%)")
print(f"\n  ⇒ 主档下最主要的 binding 约束是 **{cnt.most_common(1)[0][0]}**")
print("     注：先前记录的 'C-III 在真实 ARIS 下先 binding' 需按此更正——")
print("     ρ_max 改为真实规格 15 m 后，量程约束成为主导。")

print()
print("=" * 82)
print(f"F-8d 设计验收总判定: {'全部通过' if (v12 and v3a and v3b) else '存在未通过项'}")
print("=" * 82)
