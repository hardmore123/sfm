"""F-8 主档场景几何设计：在 ARIS 主档硬约束下搜索可行 (z_s, theta_p, D_t, h)。

主档硬约束（全部来自 ARIS Explorer 3000 规格，见 real_data/ARIS_EXPLORER_3000_PARAMS.md）：
  A1 垂直孔径 ±7.5°（绕指向方向），下俯角 theta_p 可调
  A2 探测模式有效量程 rho_max = 15 m
  A3 距离分辨率须落在规格 3–19 mm 内 ⇒ range_bin_count 由 rho_max 定

几何约束：
  G1 阴影近端（柱基，在海底）须在孔径内
  G2 阴影远端 D_e 须在孔径内 **且** 斜距 ≤ rho_max
  G3 柱顶须在孔径内，且留 margin_min 余量（避免像 S1/S5 那样贴边）
  G4 C-I: h < z_s
  G5 C-III: h·D_t/(D_t² + z_s(z_s−h)) ≤ tan(2·phi_max)

阴影几何：D_e = D_t·z_s/(z_s−h)，L_s = D_e − D_t
"""
import io, sys
import numpy as np
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

PHI_MAX = np.deg2rad(7.5)
RHO_MAX = 15.0
MARGIN_MIN = np.deg2rad(1.5)      # 柱顶距孔径边至少留 1.5°


def elev_of(D, dz):
    """水平距 D、相对声呐的竖直落差 dz(>0 表示在声呐下方) 的世界俯角（负=向下）。"""
    return -np.arctan2(dz, D)


def check(z_s, theta_p, D_t, h, margin_min=MARGIN_MIN, verbose=False):
    """返回 (ok, info)。theta_p>0 表示下俯。"""
    lo = -theta_p - PHI_MAX      # 世界俯角下界（更向下）
    hi = -theta_p + PHI_MAX      # 世界俯角上界
    info = {}

    if not (0 < h < z_s):
        return False, {"fail": "G4 C-I: h<z_s 不满足"}

    u = z_s - h                   # 柱顶到声呐的竖直落差
    D_e = D_t * z_s / u
    L_s = D_e - D_t
    info.update(D_e=D_e, L_s=L_s, u=u)

    # G1 阴影近端（柱基，落差 z_s）
    e_near = elev_of(D_t, z_s)
    # G2 阴影远端（海底，落差 z_s）
    e_far = elev_of(D_e, z_s)
    slant_far = np.hypot(D_e, z_s)
    # G3 柱顶（落差 u）
    e_top = elev_of(D_t, u)
    info.update(e_near_deg=np.degrees(e_near), e_far_deg=np.degrees(e_far),
                e_top_deg=np.degrees(e_top), slant_far=slant_far,
                fov_deg=(np.degrees(lo), np.degrees(hi)))

    if not (lo <= e_near <= hi):
        return False, {**info, "fail": "G1 阴影近端出孔径"}
    if not (lo <= e_far <= hi):
        return False, {**info, "fail": "G2 阴影远端出孔径"}
    if slant_far > RHO_MAX:
        return False, {**info, "fail": f"G2 阴影远端斜距 {slant_far:.2f} > {RHO_MAX}"}
    m_top = min(e_top - lo, hi - e_top)
    info["margin_top_deg"] = np.degrees(m_top)
    if m_top < margin_min:
        return False, {**info, "fail": f"G3 柱顶余量 {np.degrees(m_top):.2f}° < "
                                      f"{np.degrees(margin_min):.2f}°"}
    # G5 C-III
    c3 = h * D_t / (D_t**2 + z_s * u)
    info.update(c3_lhs=c3, c3_rhs=np.tan(2 * PHI_MAX))
    if c3 > np.tan(2 * PHI_MAX):
        return False, {**info, "fail": "G5 C-III 不满足"}
    return True, info


print("=" * 78)
print("① 复核现状：scene_set_main 的 pitch_deg=0（无下俯）为何逼出 rho_max=40 m")
print("=" * 78)
ok, info = check(z_s=4.5, theta_p=0.0, D_t=16.0, h=2.5)
print(f"  现状 (z_s=4.5, 下俯 0°, D_t=16, h=2.5): {'可行' if ok else '不可行'}")
for k in ("fov_deg", "e_near_deg", "e_top_deg", "e_far_deg", "D_e", "slant_far",
          "margin_top_deg", "fail"):
    if k in info:
        v = info[k]
        print(f"    {k:<16} {v if not isinstance(v,float) else round(v,3)}")
print("  → 阴影远端斜距远超 ARIS 15 m 量程，这才是 rho_max 被设成 40 的原因")

print()
print("=" * 78)
print("② 无下俯时，rho_max=15 m 能容纳的最大柱高（说明 pitch=0 不可救）")
print("=" * 78)
print(f"  {'z_s':>5} {'最大 h':>8}  说明")
for z_s in (0.8, 1.0, 1.5, 2.0, 3.0, 4.5):
    best = None
    for h in np.arange(0.05, z_s, 0.01):
        for D_t in np.arange(1.0, 15.0, 0.05):
            o, _ = check(z_s, 0.0, D_t, h)
            if o:
                best = h
                break
    print(f"  {z_s:>5.1f} {(f'{best:.2f} m' if best else '无解'):>8}")
print("  → 无下俯时柱高上限极低甚至无解，pitch=0 在 15 m 量程下不可用")

print()
print("=" * 78)
print("③ 加下俯角后的可行域（z_s=4.5 m，ARIS 真实作业高度）")
print("=" * 78)
print(f"  {'下俯°':>6} {'h范围':>16} {'D_t范围':>16} {'样例(D_t,h,L_s,余量)':>34}")
for tp_deg in (5, 10, 15, 20, 25):
    tp = np.deg2rad(tp_deg)
    hs, dts, samples = [], [], []
    for h in np.arange(0.05, 4.5, 0.05):
        for D_t in np.arange(1.0, 15.0, 0.1):
            o, inf = check(4.5, tp, D_t, h)
            if o:
                hs.append(h); dts.append(D_t)
                samples.append((D_t, h, inf["L_s"], inf["margin_top_deg"]))
    if hs:
        # 取余量最大的样例
        s = max(samples, key=lambda x: x[3])
        print(f"  {tp_deg:>6} {f'{min(hs):.2f}-{max(hs):.2f}':>16} "
              f"{f'{min(dts):.1f}-{max(dts):.1f}':>16} "
              f"{f'D_t={s[0]:.1f} h={s[1]:.2f} L_s={s[2]:.2f} m={s[3]:.2f}°':>34}")
    else:
        print(f"  {tp_deg:>6} {'无解':>16}")

print()
print("=" * 78)
print("④ 推荐主档构型（余量最大化 + L_s 适中 + h 覆盖 τ_z 的 10-40 倍）")
print("=" * 78)
cands = []
for tp_deg in np.arange(8, 26, 1.0):
    tp = np.deg2rad(tp_deg)
    for h in np.arange(0.2, 3.0, 0.05):
        for D_t in np.arange(2.0, 15.0, 0.1):
            o, inf = check(4.5, tp, D_t, h, margin_min=np.deg2rad(2.0))
            if o and 1.5 <= inf["L_s"] <= 8.0:
                cands.append((inf["margin_top_deg"], tp_deg, D_t, h, inf["L_s"],
                              inf["slant_far"], inf["e_top_deg"]))
cands.sort(reverse=True)
print(f"  可行组合 {len(cands)} 个，按柱顶余量降序前 8：")
print(f"  {'余量°':>7} {'下俯°':>7} {'D_t':>6} {'h':>6} {'L_s':>7} {'远端斜距':>9} {'柱顶俯角°':>10}")
for c in cands[:8]:
    print(f"  {c[0]:>7.2f} {c[1]:>7.1f} {c[2]:>6.1f} {c[3]:>6.2f} {c[4]:>7.2f} "
          f"{c[5]:>9.2f} {c[6]:>10.2f}")

if cands:
    _, tp, D_t, h, L_s, sf, et = cands[0]
    print(f"\n  ★ 推荐：z_s=4.5 m, 下俯={tp:.0f}°, D_t={D_t:.1f} m, h={h:.2f} m")
    print(f"     ⇒ L_s={L_s:.2f} m, 远端斜距={sf:.2f} m (≤15 ✓), 柱顶俯角={et:.2f}°")
    import feasibility as F
    for nb in (800, 1200, 1600):
        s = F.sigma_rho_bin_limited(15.0, nb)
        print(f"     range_bin={nb:>4} ⇒ Δρ_bin={s*1000:5.2f} mm "
              f"{'✓在 ARIS 规格 3-19mm 内' if 0.003<=s<=0.019 else '✗超规格'}"
              f"  τ_z_crit={F.tau_z_crit(s,10,PHI_MAX)*100:.2f} cm")
