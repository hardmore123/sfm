"""F-8 关键核查：scene_set_main 的阴影近端是否真的不在视场内？

若为真，则 L_s 无法从图像量测（看不到阴影起点），
inversion 报出的 0.19 cm MAE 必然来自真值几何 ⇒ 属真值泄漏（同 pillar_h_max 一类）。

判据：阴影掩码在距离轴上的最小 bin 对应的斜距
  - 若 ≈ 柱基斜距 √(D_t²+z_s²) = 16.62 m ⇒ 近端可见
  - 若 ≈ 孔径切断处斜距 √(34.2²+4.5²) = 34.5 m ⇒ 近端不可见（被孔径切掉）
"""
import io, sys, json, os
import numpy as np
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

for scene in ["scene_set_main/S1_main_single",
              "scene_set_v2/S1_single_well_constrained"]:
    m = json.load(open(os.path.join(scene, "meta.json"), encoding="utf-8"))
    c = m["config"]
    rmax = c.get("range_max_m", c.get("rho_max_m"))
    rmin = c.get("range_min_m", 0.5)
    nb = c["range_bin_count"]
    z_s = c["z_s_m"]
    phi_max = abs(m.get("aperture_elev_deg", [-7.5, 7.5])[0]) \
        if isinstance(m.get("aperture_elev_deg"), list) else 7.5
    pitch = c.get("pitch_deg", 0.0)
    d_avg = m["scene"]["d_avg_m"]
    h = m["scene"]["h_avg_m"]
    dbin = (rmax - rmin) / (nb - 1)

    print("=" * 76)
    print(f"{scene}")
    print(f"  z_s={z_s} pitch={pitch}° phi_max=±{phi_max}° D_t={d_avg} h={h} "
          f"range {rmin}-{rmax}m/{nb}bin")

    # 解析预期
    u = z_s - h
    D_e = d_avg * z_s / u
    slant_base = np.hypot(d_avg, z_s)                 # 柱基斜距
    slant_end = np.hypot(D_e, z_s)                    # 阴影远端斜距
    # 孔径下边缘切断的海底水平距（世界俯角 = -(pitch+phi_max)）
    ang_lo = np.deg2rad(pitch + phi_max)
    D_cut_near = z_s / np.tan(ang_lo) if ang_lo > 1e-9 else np.inf
    ang_hi = np.deg2rad(max(pitch - phi_max, 1e-9))
    D_cut_far = z_s / np.tan(ang_hi) if pitch - phi_max > 1e-9 else np.inf
    print(f"  解析: 柱基斜距={slant_base:.2f}m  阴影远端 D_e={D_e:.2f}m 斜距={slant_end:.2f}m")
    print(f"        孔径可见海底水平距区间 = [{D_cut_near:.2f}, "
          f"{D_cut_far if np.isfinite(D_cut_far) else float('inf'):.2f}] m")
    print(f"        ⇒ 柱基 D_t={d_avg} {'在' if d_avg>=D_cut_near else '**不在**'}可见区间内")

    sm = np.load(os.path.join(scene, "gt", "shadow_masks.npy"))
    print(f"\n  shadow_masks shape={sm.shape} dtype={sm.dtype} 总真值={int(sm.sum())}")
    # 距离轴是 axis=1（H=range_bin_count）
    ridx = np.where(sm.any(axis=(0, 2)))[0]
    if ridx.size == 0:
        print("  掩码全空")
        continue
    r_lo_bin, r_hi_bin = ridx.min(), ridx.max()
    slant_lo = rmin + r_lo_bin * dbin
    slant_hi = rmin + r_hi_bin * dbin
    print(f"  掩码距离 bin 范围 [{r_lo_bin}, {r_hi_bin}] "
          f"⇒ 斜距 [{slant_lo:.2f}, {slant_hi:.2f}] m")

    print(f"\n  近端归属判定：")
    print(f"    掩码最近斜距 {slant_lo:.2f} m")
    print(f"    vs 柱基斜距 {slant_base:.2f} m        差 {abs(slant_lo-slant_base):.2f} m")
    cut_slant = np.hypot(D_cut_near, z_s)
    print(f"    vs 孔径切断斜距 {cut_slant:.2f} m    差 {abs(slant_lo-cut_slant):.2f} m")
    if abs(slant_lo - slant_base) < abs(slant_lo - cut_slant):
        print("    => 近端 = 柱基，阴影起点可见 ✅")
    else:
        print("    => 近端 = 孔径切断处，**阴影起点不可见** ❌")
        print("       ⇒ L_s 无法从图像量测，inversion 的低 MAE 必来自真值几何")

    # 掩码实际跨度 vs 解析 L_s
    span_slant = slant_hi - slant_lo
    print(f"\n  掩码斜距跨度 {span_slant:.2f} m  vs  解析 L_s={D_e-d_avg:.2f} m "
          f"(水平)  ⇒ 比 {span_slant/(D_e-d_avg):.3f}")
    print()
