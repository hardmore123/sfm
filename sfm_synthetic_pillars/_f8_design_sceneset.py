"""F-8d 主档场景集设计（约束检查器 v2，修正 v1 的两处错误）。

v1 的错误：
  ① G1 要求"阴影近端（柱基，水平距 D_t）在孔径内" —— 错。
     柱基被柱体自身遮挡，本无回波，不必在孔径内。
     正确条件：阴影在**距离轴**上的跨度 [ρ_target, ρ_end] 必须落在
     "被照亮的海底带" 内，否则暗区是"未照亮"而非"被遮挡"（审计 Q2）。
  ② G2 与 G3 其实是同一个约束 —— 柱顶俯角与阴影远端俯角恒等：
        -arctan(u/D_t) == -arctan(z_s/(D_t·z_s/u))    （同一条掠射线）

正确约束集（ARIS 主档）：
  H1 照明覆盖：ρ_target ≥ z_s/sin(θ_p+φ_max)  且  ρ_end ≤ z_s/sin(θ_p−φ_max)
  H2 量程    ：ρ_end ≤ ρ_max = 15 m
  H3 余量    ：柱顶俯角距孔径边 ≥ margin_min
  H4 C-I     ：h < z_s
  H5 C-III   ：h·D_t/(D_t²+z_s(z_s−h)) ≤ tan(2φ_max)
  H6 起伏鲁棒：在 z_s ± A 全程 H1–H3 均成立（★I-1 需要靠 heave 制造 std(φ)）
"""
import io, sys, json
import numpy as np
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

PHI_MAX = np.deg2rad(7.5)
RHO_MAX = 15.0
RHO_MIN = 0.5
N_BINS = 1600
N_FRAMES = 60                    # 与 gen_scenes_main_f8.py 的 N_FRAMES 一致
SIGMA_RHO_INJ = 0.010            # ★I-1 链：注入斜距噪声
DBIN = (RHO_MAX - RHO_MIN) / (N_BINS - 1)


R_OBJ = 0.25          # 柱半径（须与生成器 R_PILLAR 一致）


def geom(z_s, h, D_t, r_obj=R_OBJ):
    """返回 (u, D_e, L_s, rho_target, rho_end, elev_top)。

    ⚠️ 有限尺寸物体：决定阴影远端的是**轮廓远边缘** D_t+r，不是柱心 D_t；
       高光（leading edge）在**近边缘** D_t−r。
       首版全用柱心，导致 (a) 包线 h_max 高估、(b) 反演有 +r 量级系统偏置
       （本构型约 +8 cm）。W6 暴力射线校核抓出此问题。
    """
    u = z_s - h
    d_far = D_t + r_obj
    d_near = D_t - r_obj
    D_e = d_far * z_s / u
    L_s = D_e - d_near
    rho_target = np.hypot(d_near, u)
    rho_end = np.hypot(D_e, z_s)
    elev_top = -np.arctan2(u, d_near)
    return u, D_e, L_s, rho_target, rho_end, elev_top


def check(z_s, theta_p, D_t, h, margin_min_deg=2.0, rho_max=RHO_MAX):
    """单构型可行性。theta_p>0 = 下俯（rad）。返回 (ok, info)。"""
    info = {}
    if not (0 < h < z_s):
        return False, {"fail": "H4 C-I: h<z_s"}
    u, D_e, L_s, rt, re, et = geom(z_s, h, D_t)
    lo, hi = -theta_p - PHI_MAX, -theta_p + PHI_MAX      # 世界俯角区间
    info.update(u=u, D_e=D_e, L_s=L_s, rho_target=rt, rho_end=re,
                elev_top_deg=np.degrees(et),
                fov_deg=(np.degrees(lo), np.degrees(hi)))

    # H1' 照明带：只要求**阴影远端** ρ_end 落在照明带内。
    #     阴影近端无需被照亮 —— D_t 不由阴影起点量测，而由 ★I(BA) 给出的
    #     柱体水平位置提供（这正是两创新点串行的接口，见 F-8c）。
    #     h = z_s(1 − D_t/D_e)：D_t 来自 BA，D_e 来自阴影远端跳变。
    a_lo = theta_p + PHI_MAX
    a_hi = theta_p - PHI_MAX
    illum_near = z_s / np.sin(a_lo) if a_lo > 1e-9 else np.inf
    illum_far = z_s / np.sin(a_hi) if a_hi > 1e-9 else np.inf
    info.update(illum_near=illum_near, illum_far=illum_far)
    if re < illum_near:
        return False, {**info,
                       "fail": f"H1' 阴影远端 {re:.2f} < 照明带近界 {illum_near:.2f}"
                               f"（远端跳变不可见）"}
    if re > illum_far:
        return False, {**info,
                       "fail": f"H1' 阴影远端 {re:.2f} > 照明带远界 {illum_far:.2f}"}
    # 记录阴影中可观测的比例（近端未照亮段不计入）
    info["shadow_visible_frac"] = float(
        (re - max(rt, illum_near)) / (re - rt)) if re > rt else 0.0
    # H2 量程
    if re > rho_max:
        return False, {**info, "fail": f"H2 阴影远端斜距 {re:.2f} > {rho_max}"}
    # H3 余量
    m = min(et - lo, hi - et)
    info["margin_top_deg"] = np.degrees(m)
    if np.degrees(m) < margin_min_deg:
        return False, {**info, "fail": f"H3 柱顶余量 {np.degrees(m):.2f}° < {margin_min_deg}°"}
    # H5 C-III（用轮廓远边缘，与 geom 一致）
    c3 = h * (D_t + R_OBJ) / ((D_t + R_OBJ)**2 + z_s * u)
    info.update(c3_lhs=c3, c3_rhs=np.tan(2 * PHI_MAX))
    if c3 > np.tan(2 * PHI_MAX):
        return False, {**info, "fail": "H5 C-III"}
    return True, info


def check_heave(z_s, theta_p, D_t, h, A, margin_min_deg=1.0, n=60):
    """H6 起伏鲁棒：沿**实际**起伏轨迹 z ∈ [z_s, z_s+A] 全程可行。"""
    worst = None
    for zz in heave_z(z_s, A, n):
        ok, inf = check(float(zz), theta_p, D_t, h, margin_min_deg)
        if not ok:
            return False, {"z_s_fail": float(zz), **inf}
        if worst is None or inf["margin_top_deg"] < worst["margin_top_deg"]:
            worst = inf
    return True, worst


def frame_feasible(z_s_frame, theta_p, D_t, h, rho_max=RHO_MAX):
    """逐帧包线判据（★I-2 的正确评估粒度）。

    场景级二值标签不合适：起伏使不同帧的 ρ_end 不同，
    一个场景可能部分帧可反演、部分帧不可。应报**逐帧混淆矩阵**。
    """
    return check(float(z_s_frame), theta_p, D_t, h,
                 margin_min_deg=0.0, rho_max=rho_max)


def heave_z(z_s, A, n=60):
    """复现 `trajectory.py:76` 的实际起伏模型（**必须与生成器一致**）。

    实际： zs = sz + A·sin(2π·t·0.5),  t ∈ [0,1]
    ⇒ 相位只走 0→π ⇒ **半周期、单侧**：z ∈ [z_s, z_s+A]
    （首版误设为全周期 z ∈ [z_s−A, z_s+A]，导致 std(φ) 高估 2.3 倍、
      且把 M4 的包线判据算错。）
    """
    t = np.linspace(0.0, 1.0, n)
    return z_s + A * np.sin(2 * np.pi * t * 0.5)


def std_phi_of_heave(z_s, D_t, h, A, n=60):
    """实际起伏下**世界系射线**俯角的标准差（rad）。

    注意用世界系射线角，非体系角：CRLB 的零空间方向由射线方向决定，
    纯旋转不改变射线 ⇒ 静态下俯不改善 σ_Pz。
    """
    zz = heave_z(z_s, A, n)
    phi = -np.arctan2(zz - h, D_t)
    return float(np.std(phi))



def _report():
    """设计报告与落盘（仅直接运行时执行，避免被 import 时产生副作用）。"""
    print("=" * 80)
    print("① 修正后的可行域（z_s=4.5 m, ρ_max=15 m, 1600 bin）")
    print("=" * 80)
    print(f"  {'下俯°':>6} {'h 范围':>14} {'D_t 范围':>14} {'可行组合':>8}")
    best_by_tp = {}
    for tp_deg in range(8, 31, 1):
        tp = np.deg2rad(tp_deg)
        hs, ds, cands = [], [], []
        for h in np.arange(0.10, 4.4, 0.05):
            for D_t in np.arange(2.0, 15.0, 0.1):
                ok, inf = check(4.5, tp, D_t, h)
                if ok:
                    hs.append(h); ds.append(D_t)
                    cands.append((inf["margin_top_deg"], D_t, h, inf))
        if hs:
            best_by_tp[tp_deg] = max(cands, key=lambda c: c[0])
            print(f"  {tp_deg:>6} {f'{min(hs):.2f}-{max(hs):.2f}':>14} "
                  f"{f'{min(ds):.1f}-{max(ds):.1f}':>14} {len(cands):>8}")
        else:
            print(f"  {tp_deg:>6} {'无解':>14}")
    
    print()
    print("=" * 80)
    print("② heave 鲁棒性：★I-1 需要用起伏幅度 A 制造 std(φ) 对比")
    print("=" * 80)
    tau_z, N = 0.05, N_FRAMES  # N 必须与生成器帧数一致（gen_scenes_main_f8.N_FRAMES）
    dphi_min = SIGMA_RHO_INJ / (np.sqrt(N) * tau_z)
    print(f"  Δφ_min(σ_ρ=10mm, N=10, τ_z=5cm) = {np.degrees(dphi_min):.3f}°")
    print(f"\n  取 θ_p=19°, D_t=10.6, h=0.85（①的最优构型）：")
    print(f"  {'A(m)':>6} {'std(φ)°':>9} {'判定':>10} {'全程可行':>9} {'最差余量°':>10}")
    sel = []
    for A in (0.0, 0.1, 0.2, 0.3, 0.5, 0.8, 1.0, 1.2, 1.5):
        sp = std_phi_of_heave(4.5, 10.6, 0.85, A)
        ok, inf = check_heave(4.5, np.deg2rad(19), 10.6, 0.85, A)
        verdict = "良约束" if sp >= dphi_min else "盲"
        print(f"  {A:>6.1f} {np.degrees(sp):>9.3f} {verdict:>10} "
              f"{'是' if ok else '否':>9} "
              f"{(f'{inf[chr(39)+chr(39)]}' if False else f'{inf.get(chr(109)+chr(97)+chr(114)+chr(103)+chr(105)+chr(110)+chr(95)+chr(116)+chr(111)+chr(112)+chr(95)+chr(100)+chr(101)+chr(103), float(chr(110)+chr(97)+chr(110))):.2f}'):>10}")
        if ok:
            sel.append((A, sp, verdict))
    
    print()
    print("=" * 80)
    print("③ 主档场景集设计（覆盖 ★I-1 / ★I-2 / ★II 所需角色）")
    print("=" * 80)
    
    # 固定基准构型
    Z_S, TP, D_T, H = 4.5, 19.0, 10.6, 0.85
    u, D_e, L_s, rt, re, et = geom(Z_S, H, D_T)
    print(f"  基准：z_s={Z_S} θ_p={TP}° D_t={D_T} h={H}")
    print(f"        u={u:.2f} D_e={D_e:.2f} L_s={L_s:.2f} ρ_target={rt:.2f} ρ_end={re:.2f}")
    print(f"        柱顶俯角={np.degrees(et):.2f}°  L_s 占 {L_s/DBIN:.0f} 个 range bin")
    
    # 找 heave 大到能"良约束"且全程可行的 A
    A_well = None
    A_blind = None
    for A, sp, v in sel:
        if v == "良约束" and A_well is None:
            A_well = A
        if v == "盲" and A > 0 and A_blind is None:
            A_blind = A
    print(f"\n  ★I-1 对比对：A_blind={A_blind} (std φ={np.degrees(std_phi_of_heave(Z_S,D_T,H,A_blind or 0)):.2f}°) "
          f"vs A_well={A_well} (std φ={np.degrees(std_phi_of_heave(Z_S,D_T,H,A_well or 0)):.2f}°)")
    
    # 包线边缘 / 外点：扫 h 找 binding 切换点
    # ⚠️ 必须在 **heave 全程** 下扫：z_s 降到 z_s−A 时 (z_s−h) 变小、D_e 变大，
    #    包线比标称 z_s 下更紧。用标称 z_s 扫会高估 h_max（首版就犯了这个错）。
    A_env = A_well if A_well is not None else 0.0
    print(f"\n  ★I-2 包线边缘（θ_p={TP}°, D_t={D_T}, heave A={A_env} 全程）：")
    prev_ok, prev_fail = None, None
    for h in np.arange(0.10, 4.40, 0.01):
        ok, inf = check_heave(Z_S, np.deg2rad(TP), D_T, h, A_env, margin_min_deg=0.0)
        if ok:
            prev_ok = (h, inf)
        elif prev_ok is not None:
            prev_fail = (h, inf)
            break
    if prev_ok and prev_fail:
        print(f"    包线内最大 h = {prev_ok[0]:.2f} m")
        print(f"    刚出包线 h = {prev_fail[0]:.2f} m ⇒ {prev_fail[1].get('fail','?')}")
        # 对照：若按标称 z_s（不考虑起伏）会得到多少
        p2 = None
        for h in np.arange(0.10, 4.40, 0.01):
            ok2, _ = check(Z_S, np.deg2rad(TP), D_T, h, margin_min_deg=0.0)
            if ok2:
                p2 = h
            elif p2 is not None:
                break
        print(f"    （若忽略起伏按标称 z_s={Z_S} 扫会得 h_max={p2:.2f} m，"
              f"高估 {(p2-prev_ok[0])/prev_ok[0]*100:.0f}%）")
    
    design = {
        "aperture_tier": "main_aris_7p5deg",
        "sonar": {
            "phi_max_deg": 7.5, "fov_azim_deg": 30, "n_beams": 128,
            "rho_min_m": RHO_MIN, "rho_max_m": RHO_MAX, "range_bin_count": N_BINS,
            "dbin_mm": DBIN * 1000,
            "sigma_rho_m": SIGMA_RHO_INJ, "sigma_rho_source": "aris_spec_mid",
            "sigma_rho_bin_m": DBIN, "sigma_rho_quant_m": DBIN / np.sqrt(12),
        },
        "base_geometry": {"z_s_m": Z_S, "pitch_deg": TP, "D_t_m": D_T, "h_m": H,
                          "L_s_m": float(L_s), "rho_target_m": float(rt),
                          "rho_end_m": float(re),
                          "elev_top_deg": float(np.degrees(et))},
        "scenes": [
            {"name": "M1_well_constrained", "role": "★I-1 良约束基准",
             "heave_m": A_well, "h_m": H, "D_t_m": D_T, "note": "std(φ) ≥ Δφ_min"},
            {"name": "M2_blind_low_spread", "role": "★I-1 盲（低离散度）",
             "heave_m": A_blind, "h_m": H, "D_t_m": D_T, "note": "std(φ) < Δφ_min"},
            {"name": "M3_envelope_inside", "role": "★I-2 包线内（近边）",
             "heave_m": A_env, "h_m": round(prev_ok[0] - 0.03, 2) if prev_ok else H,
             "D_t_m": D_T, "note": "包线内但距 binding 仅 3 cm"},
            {"name": "M4_envelope_outside", "role": "★I-2 包线外（应判不可反演）",
             "heave_m": A_env, "h_m": round(prev_fail[0] + 0.03, 2) if prev_fail else None,
             "D_t_m": D_T, "note": prev_fail[1].get("fail", "") if prev_fail else ""},
            {"name": "M5_low_snr", "role": "★II 低 SNR",
             "heave_m": A_well, "h_m": H, "D_t_m": D_T, "note": "speckle/noise_floor 加重"},
        ],
        "acceptance": {
            "dbin_within_aris_spec": bool(0.003 <= DBIN <= 0.019),
            "tau_z_crit_cm": float(np.sqrt(3) * SIGMA_RHO_INJ / (np.sqrt(10) * PHI_MAX) * 100),
            "L_s_in_bins": float(L_s / DBIN),
        },
    }
    
    print()
    print("=" * 80)
    print("④ 验收指标自检")
    print("=" * 80)
    a = design["acceptance"]
    print(f"  Δρ_bin = {DBIN*1000:.2f} mm  在 ARIS 规格 3-19mm 内: "
          f"{'✅' if a['dbin_within_aris_spec'] else '❌'}")
    print(f"  τ_z_crit = {a['tau_z_crit_cm']:.2f} cm  ≤ τ_z=5cm: "
          f"{'✅' if a['tau_z_crit_cm'] <= 5 else '❌'}")
    print(f"  基准 L_s 占 {a['L_s_in_bins']:.0f} 个 range bin (需 ≥50 以支持亚 bin 量测): "
          f"{'✅' if a['L_s_in_bins'] >= 50 else '❌'}")
    print(f"  ρ_end = {re:.2f} m ≤ ρ_max=15: {'✅' if re <= RHO_MAX else '❌'}")
    
    with open("_f8_sceneset_design.json", "w", encoding="utf-8") as f:
        json.dump(design, f, ensure_ascii=False, indent=2)
    print("\n  设计已落盘 _f8_sceneset_design.json")
    for s in design["scenes"]:
        print(f"    {s['name']:<22} {s['role']:<22} heave={s['heave_m']} h={s['h_m']}")
    


if __name__ == "__main__":
    _report()
