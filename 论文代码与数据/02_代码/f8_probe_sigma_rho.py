"""F-8 前置探针：区分两条创新链各自的有效 σ_ρ。

★I-1 多视 CRLB 链：观测量是 tracks.csv 的 rho_m（连续浮点）
    ⇒ σ_ρ = 注入噪声，range bin 不进入
★II-1 阴影反演链：观测量是阴影掩码沿距离轴的 bin 数
    ⇒ σ_ρ 受 Δρ_bin 量化直接限制

本探针实测 shadow_length_maps 的实际量化粒度，确认后者。
"""
import io, sys, json, glob, os
import numpy as np
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

for scene in ["scene_set_main/S1_main_single",
              "scene_set_v2/S1_single_well_constrained"]:
    if not os.path.isdir(scene):
        continue
    meta = json.load(open(os.path.join(scene, "meta.json"), encoding="utf-8"))
    cfg = meta["config"]
    rmax = cfg.get("range_max_m", cfg.get("rho_max_m"))
    nb = cfg["range_bin_count"]
    rmin = cfg.get("range_min_m", 0.5)
    dbin = (rmax - rmin) / (nb - 1)

    print("=" * 74)
    print(f"场景 {scene}")
    print(f"  tier={meta.get('aperture_tier','(缺)')}  range {rmin}-{rmax} m / {nb} bin")
    print(f"  Δρ_bin = {dbin*1000:.2f} mm     Δ/√12 = {dbin/np.sqrt(12)*1000:.2f} mm")

    slp = os.path.join(scene, "gt", "shadow_length_maps.npy")
    if not os.path.exists(slp):
        print("  [无 shadow_length_maps.npy]")
        continue
    L = np.load(slp)
    Lv = L[np.isfinite(L) & (L > 0)]
    print(f"\n  阴影长度图 shape={L.shape}  有效样本 {Lv.size}")
    print(f"  L_s 范围 {Lv.min():.4f} ~ {Lv.max():.4f} m")

    # 实测量化粒度：非零唯一值之间的最小正间隔
    u = np.unique(np.round(Lv, 9))
    if u.size > 1:
        d = np.diff(u)
        d = d[d > 1e-9]
        print(f"  唯一值 {u.size} 个，相邻间隔：min={d.min()*1000:.3f} mm  "
              f"中位={np.median(d)*1000:.3f} mm")
        # 是否为 Δρ_bin 的整数倍
        ratio = np.median(d) / dbin
        print(f"  中位间隔 / Δρ_bin = {ratio:.4f}")
        if abs(ratio - 1.0) < 0.05:
            print("  => L_s 按整 bin 量化，量化步长 = Δρ_bin  ✅确认")
        elif ratio < 0.05:
            print("  => L_s 是连续量（未按 bin 量化）")
        else:
            print(f"  => 量化步长 ≈ {ratio:.2f} × Δρ_bin")
    else:
        print("  唯一值只有 1 个，无法测粒度")

    # σ_h 对 σ_L 的放大：h = z_s(1 - D_t/D_e)，∂h/∂L 的量级
    zs = cfg.get("z_s_m", 4.5)
    sh = os.path.join(scene, "innovation2", "sigma_height.npy")
    if os.path.exists(sh):
        S = np.load(sh)
        Sv = S[np.isfinite(S) & (S > 0)]
        if Sv.size:
            print(f"\n  σ_h（该场景落盘）中位 {np.median(Sv)*100:.2f} cm  "
                  f"90分位 {np.percentile(Sv,90)*100:.2f} cm")
            print(f"  与 τ_z=5cm 比：中位 {'≤' if np.median(Sv)<=0.05 else '>'} τ_z")
    print()

print("=" * 74)
print("结论要点")
print("=" * 74)
print("""
两条链的 σ_ρ 口径必须分开记账：
  ★I-1（多视 CRLB）  观测 rho_m 连续 ⇒ σ_ρ = 注入噪声（10 mm）
  ★II-1（阴影反演）  观测 L_s 按 bin ⇒ σ_ρ 受 Δρ_bin 限制
台账 sigma_rho_ledger.md 原先把两者混为一条，须拆分。
""")
