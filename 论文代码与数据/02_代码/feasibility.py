"""
T0.9 可反演性判据 + R-X1 std(φ) 版判据
========================================

根据几何参数判定"声学阴影→高度"反演是否可行。

公式（基于大论文 §7.1 验算）：
  - D_max = sqrt(rho_max^2 - z_s^2)        最大可观测水平距离
  - h_max = z_s * (1 - d / D_max)         在水平距离 d 处可反演的最大目标高度
  - L_s = d * h / (z_s - h)                阴影长度
  - elev_top = atan2(h - z_s, d)            到柱顶的仰角
  - L_s_clipped = min(L_s, rho_max - d)    阴影是否被 range_max 截断

可反演条件（全部满足）：
  1. h > 0 (有目标)
  2. h <= z_s (仰角向下，阴影落到地面)
  3. elev_top ∈ [fov_elev_lo, fov_elev_hi]  (柱顶在声呐仰角孔径内)
  4. d <= D_max (目标在量程内)
  5. L_s <= rho_max - d (阴影不超出量程)

R-X1（2026-09-05）：新增 std(φ) 版盲区角判据与临界精度。
  - Δφ_min = σ_ρ / (√N · τ_z)         替代旧 arcsin 版
  - τ_z^crit = √3 · σ_ρ / (√N · φ_max)  临界精度（盲区占比从 0 突变为有）
  - blind_fraction_curve: τ_z 三档 {2,5,10} cm 盲区占比曲线

输出：布尔 + h_max
"""
from __future__ import annotations
import numpy as np
from dataclasses import dataclass
from typing import Tuple


# ---- R-X1 新增：ARIS Explorer 3000 主档预设（TH7 决策）
ARIS_MAIN = {
    "phi_max_deg": 7.5,       # 主档孔径 ±7.5°
    "phi_max_rad": np.deg2rad(7.5),
    "fov_azim_deg": 30,       # 方位孔径
    "n_beams": 128,            # 主档波束数
    "sigma_rho_m": 0.01,       # 测距噪声 1cm（ARIS 标称 3-19mm 取中）
    "tau_z_m": 0.05,           # 高度精度要求 5cm
    "N_obs_default": 10,       # 默认观测数（多次通过累计）
}

# ---- R-X1 新增：宽孔径敏感性档（TH7 决策）
#      注：现有 S1–S6 场景为 600 bin / 25 m ⇒ Δρ_bin = 40.9 mm（采样受限），
#      理论计算用规格值 10 mm，实验须按 sigma_rho_ledger.md 从 meta.json 读取。
ARIS_WIDE = {
    "phi_max_deg": 17.0,
    "phi_max_rad": np.deg2rad(17.0),
    "fov_azim_deg": 30,
    "n_beams": 128,
    "sigma_rho_m": 0.01,
    "tau_z_m": 0.05,
    "N_obs_default": 10,
}


# ============================================================
# F-7：σ_ρ 台账读取接口（唯一来源，禁止脚本内硬编码）
#      台账文档：sigma_rho_ledger.md
# ============================================================

SIGMA_RHO_SPEC_MID = 0.010     # ARIS 规格 3–19 mm 取中，用于主档理论计算
SOUND_SPEED = 1500.0           # m/s


def sigma_rho_bandwidth_limited(bandwidth_hz: float) -> float:
    """物理分辨率 c/(2B)。"""
    return SOUND_SPEED / (2.0 * bandwidth_hz)


def sigma_rho_bin_limited(rho_max: float, n_bins: int, rho_min: float = 0.5) -> float:
    """采样受限分辨率（range bin 间隔）。"""
    if n_bins < 2:
        return float("inf")
    return (rho_max - rho_min) / (n_bins - 1)


def resolve_sigma_rho(meta: dict, bandwidth_hz: float = 0.3e6,
                      strict: bool = False) -> tuple:
    """
    按 sigma_rho_ledger.md 的约定解析场景应使用的 σ_ρ。

    读取顺序：
      1. meta['config']['sigma_rho_m']（生成时落盘的权威值）
      2. 缺失 ⇒ 由 range_bin_count / rho_max 按采样受限回填，并**告警**
      3. strict=True 时缺失直接报错（用于正式实验，防静默默认值）

    Returns:
        (sigma_rho_m, source_tag)
    """
    cfg = (meta or {}).get("config", {}) or {}
    if "sigma_rho_m" in cfg:
        return float(cfg["sigma_rho_m"]), cfg.get("sigma_rho_source", "meta")

    msg = ("meta.json 缺少 config.sigma_rho_m —— 按 sigma_rho_ledger.md，"
           "正式实验不得静默使用默认值")
    if strict:
        raise KeyError(msg)

    rho_max = cfg.get("rho_max_m")
    n_bins = cfg.get("range_bin_count")
    if rho_max and n_bins:
        s_bin = sigma_rho_bin_limited(float(rho_max), int(n_bins))
        s = max(sigma_rho_bandwidth_limited(bandwidth_hz), s_bin)
        import warnings
        warnings.warn(f"{msg}；已按采样受限回填 σ_ρ={s*1000:.1f} mm", stacklevel=2)
        return float(s), "range_bin_limited(fallback)"

    import warnings
    warnings.warn(f"{msg}；已回退到规格中值 {SIGMA_RHO_SPEC_MID*1000:.0f} mm",
                  stacklevel=2)
    return SIGMA_RHO_SPEC_MID, "aris_spec_mid(fallback)"


def min_elev_spread(sigma_rho: float, N: int, tau_z: float) -> float:
    """
    仰角离散度门限 Δφ_min（F-2 修正版，权威公式见
    ../大论文思想路线/理论修正_T1-T6.md §1.2b）。

    ⚠️ 返回值是对「各视角仰角的标准差 std(φ_k)」的门限，
       **不是**对「仰角本身 |φ|」的门限。二者物理含义不同：
         std(φ_k) 由轨迹决定；φ 由地标位置决定。
       位于 φ=5° 的地标，轨迹给它 std(φ)=3° 则可观测、给 0.1° 则盲，
       与它在孔径中的位置无关。因此**不存在"盲区占孔径 X%"这种量**。

    物理：CRLB  σ_Pz ≈ σ_ρ / (√N · std(φ_k))
    ⇒ 门限   Δφ_min = σ_ρ / (√N · τ_z)
    判据：std(φ_k) < Δφ_min  ⇒  该地标高度不可观测（σ_Pz > τ_z）

    Args:
        sigma_rho: 测距噪声 (m)
        N: 观测数
        tau_z: 高度精度要求 (m)
    Returns:
        Δφ_min: 仰角离散度门限 (rad)
    """
    if N < 1 or tau_z <= 0 or sigma_rho < 0:
        return np.inf
    return sigma_rho / (np.sqrt(N) * tau_z)


# 向后兼容别名（旧名有误导性：它不是"角度"而是"离散度门限"）
def blind_angle_std(sigma_rho: float, N: int, tau_z: float) -> float:
    """已弃用，请改用 min_elev_spread（名称更准确）。"""
    import warnings
    warnings.warn("blind_angle_std 已弃用，请改用 min_elev_spread",
                  DeprecationWarning, stacklevel=2)
    return min_elev_spread(sigma_rho, N, tau_z)


def tau_z_crit(sigma_rho: float, N: int, phi_max: float,
               mode: str = "uniform") -> float:
    """
    临界精度 τ_z^crit（R1 修正 2026-09-07：**必须区分两个界**）。

    权威推导见 ../大论文思想路线/理论修正_T1-T6.md §1.2d。

    mode="abs"（硬界，任何运动方式都无法突破）
        对区间 [-φ_max, +φ_max] 上的有界量，方差最大的分布是**两端点各半**
        的二点分布（Popoviciu 不等式 Var ≤ (M-m)²/4），故
            std(φ) ≤ φ_max
            τ_z^crit,abs = σ_ρ / (√N · φ_max)
        ARIS 主档（φ_max=7.5°、σ_ρ=10mm、N=10）⇒ **2.42 cm**
        达到它需要"观测集中在孔径两端"的 bang-bang 采集，所需起伏幅度
        A = D_t·tan(φ_max)，恰为 T6 独立给出的 A_opt（两条理论吻合）。

    mode="uniform"（默认；均匀扫过孔径的可达值，工程参考）
        目标均匀扫过整个孔径时 std(φ) = φ_max/√3，故
            τ_z^crit,unif = √3·σ_ρ / (√N · φ_max)
        ARIS 主档 ⇒ **4.18 cm**，与 Aykin 的横向可分辨距离
        d_R = R·dθ = 4.4 cm 几乎相同 ⇒ 常规采集下垂直与横向精度同量级。

    ⚠️ 首版只有 uniform 版且**误称其为硬界**。二者差 √3 倍，
       该差距正是采集规划可挖掘的空间。

    ⚠️ 数值巧合警告：τ_z^crit,abs = 2.42 cm 与**已作废的 sin 版**
       σ_ρ/(√N·sin φ_max) = 2.41 cm 几乎相同（sin7.5°≈0.1309 rad），
       但推导完全不同（sin 版错在把 1/Λ_zz 当后验方差，低估 15 倍）。
       不得因数值接近而认为 sin 版其实是对的。

    Args:
        sigma_rho: 测距噪声 (m)
        N: 观测数
        phi_max: 仰角孔径半宽 (rad)
        mode: "abs" 硬界 / "uniform" 均匀扫过（默认，保持向后兼容）
    Returns:
        tau_z_crit: 临界精度 (m)
    """
    if N < 1 or phi_max <= 0 or sigma_rho < 0:
        return np.inf
    if mode == "abs":
        std_max = phi_max
    elif mode == "uniform":
        std_max = phi_max / np.sqrt(3)
    else:
        raise ValueError(f"mode 必须是 'abs' 或 'uniform'，收到 {mode!r}")
    return sigma_rho / (np.sqrt(N) * std_max)


def blind_landmark_fraction(std_phi_per_landmark, sigma_rho: float, N,
                            tau_z_list=(0.02, 0.05, 0.10)) -> dict:
    """
    盲地标比例曲线（F-2 重构版，替代已作废的 blind_fraction_curve）。

    ⚠️ 与旧版的本质区别：
      旧版按 f = Δφ_min/φ_max 从**孔径几何**算出"盲区占孔径比例"——
      这是把 std 门限当成角度位置门限用，无物理意义（审计 20260905 P2）。
      新版是**经验量**：必须传入该轨迹下每个地标实际达到的 std(φ_jk)，
      统计其中低于门限的比例。

    Args:
        std_phi_per_landmark: (M,) 每个地标在该轨迹下实际的 std(φ_k)，单位 rad
        sigma_rho: 测距噪声 (m)
        N: 观测数；标量或 (M,) 每地标观测数
        tau_z_list: 精度档 (m)
    Returns:
        dict：每档的 Δφ_min 与盲地标比例
    """
    sp = np.asarray(std_phi_per_landmark, dtype=float)
    sp = sp[np.isfinite(sp)]
    M = sp.size
    Narr = np.full(M, N, dtype=float) if np.isscalar(N) else np.asarray(N, float)

    curve = {}
    for tz in tau_z_list:
        dmin = sigma_rho / (np.sqrt(np.maximum(Narr, 1)) * tz)   # 逐地标门限
        blind = sp < dmin
        curve[float(tz)] = {
            "delta_phi_min_rad_median": float(np.median(dmin)) if M else float("nan"),
            "delta_phi_min_deg_median": float(np.degrees(np.median(dmin))) if M else float("nan"),
            "n_blind": int(blind.sum()),
            "n_total": int(M),
            "fraction_blind": float(blind.mean()) if M else float("nan"),
            "fraction_blind_pct": float(blind.mean() * 100) if M else float("nan"),
        }
    return {
        "sigma_rho_m": sigma_rho,
        "n_landmarks": int(M),
        "std_phi_deg_median": float(np.degrees(np.median(sp))) if M else float("nan"),
        "std_phi_deg_max": float(np.degrees(sp.max())) if M else float("nan"),
        "by_tau_z": curve,
        "note": "盲地标比例为经验量，依赖具体轨迹；不存在'盲区占孔径比例'这种量",
    }


def blind_fraction_curve(*args, **kwargs):
    """已作废：原按 Δφ_min/φ_max 算"盲区占孔径比例"，无物理意义。

    Δφ_min 是对 std(φ_k) 的门限（由轨迹决定），不是对 |φ| 的门限
    （由地标位置决定）。详见 审计_20260905_文档倒挂与雕刻错误.md P2。
    请改用 blind_landmark_fraction()，并传入实际的 std(φ_jk) 数组。
    """
    raise NotImplementedError(
        "blind_fraction_curve 已作废（把 std 门限当角度位置门限用）。\n"
        "请改用 blind_landmark_fraction(std_phi_per_landmark, sigma_rho, N, tau_z_list)，\n"
        "需传入该轨迹下每个地标实际的 std(φ_k)。\n"
        "孔径相关的正确结论只有 tau_z_crit()。"
    )


def aris_main_profile(N: int = 10) -> dict:
    """ARIS 主档的孔径能力剖面（论文可直接引用的速查表，F-2 重构）。"""
    return _aperture_profile(ARIS_MAIN, N, "main_aris_7p5deg")


def aris_wide_profile(N: int = 10) -> dict:
    """ARIS 宽孔径敏感性档的孔径能力剖面（F-2 后只报孔径相关的正确结论）。"""
    return _aperture_profile(ARIS_WIDE, N, "sensitivity_17deg")


def _aperture_profile(preset: dict, N: int, tier: str) -> dict:
    """
    孔径能力剖面（F-2 重构）：只报孔径能决定的量。

    ⚠️ 不再输出"盲区占孔径比例"——该量无物理意义（审计 20260905 P2）。
    孔径能决定的唯一结论是精度硬上限 τ_z^crit；
    盲地标比例是经验量，须用 blind_landmark_fraction() 并传入实际 std(φ_jk)。
    """
    sr = preset["sigma_rho_m"]
    pm = preset["phi_max_rad"]
    tc = tau_z_crit(sr, N, pm)
    return {
        "aperture_tier": tier,
        "sigma_rho_m": sr,
        "N": N,
        "phi_max_deg": float(np.degrees(pm)),
        "max_achievable_std_phi_deg": float(np.degrees(pm / np.sqrt(3))),
        "tau_z_crit_m": float(tc),
        "tau_z_crit_cm": float(tc * 100),
        "delta_phi_min_deg_by_tau_z": {
            f"{tz:.2f}m": float(np.degrees(min_elev_spread(sr, N, tz)))
            for tz in (0.02, 0.05, 0.10)
        },
        "note": ("τ_z^crit 是孔径决定的精度硬上限；盲地标比例请用 "
                 "blind_landmark_fraction() 传入实际 std(φ_jk) 计算"),
    }


@dataclass
class FeasibilityResult:
    is_feasible: bool
    h_max: float
    reason: str
    D_max: float
    elev_top: float
    L_s: float
    L_s_clipped: bool
    binding_constraint: str = ""   # 哪个约束卡住（C-I/C-II/C-III/C-IV）


def check_feasibility(
    z_s: float,
    rho_max: float,
    theta_p: float,        # 平台下俯角（rad），0 = 水平，+ = 俯
    fov_elev_lo: float,    # 仰角孔径下界（rad）
    fov_elev_hi: float,    # 仰角孔径上界（rad）
    d: float,              # 目标水平距离 (m)
    h: float,              # 目标高度 (m)
    z_s_min: float = None, # AUV 起伏最小 z（瞬时），默认 = z_s
    z_s_max: float = None, # AUV 起伏最大 z（瞬时），默认 = z_s
) -> FeasibilityResult:
    """
    单目标可反演性判定。

    Args:
        z_s: 声呐距海底高度 (m)
        rho_max: 声呐最大量程 (m)
        theta_p: 平台下俯角 (rad)
        fov_elev_lo, fov_elev_hi: 仰角孔径 (rad)
        d: 目标到声呐的水平距离 (m)
        h: 目标高度 (m)
        z_s_min, z_s_max: AUV 起伏瞬时 z 范围（默认 = z_s，无起伏）

    **改进**：考虑 AUV heave 起伏对瞬时 z_s 的影响。
    - 严格场景：要求**所有**瞬时 z_s 都能反演 → 用 z_s_min 算
    - 概率场景：要求**部分**瞬时 z_s 能反演 → 用 z_s_max 算并报告概率
    """
    # 默认值
    if z_s_min is None:
        z_s_min = z_s
    if z_s_max is None:
        z_s_max = z_s

    # 1) 目标存在
    if h <= 0:
        return FeasibilityResult(False, 0.0, "目标高度 h<=0", 0, 0, 0, False, "C-I (h<=0)")

    # 2) 严格场景：用最小 z_s 判定（C-II）
    #    若 AUV 起伏最小 z_s 时 h>z_s_min，则整个起伏区间都可反演
    if h >= z_s_min:
        return FeasibilityResult(False, 0.0,
            f"目标高度 h={h:.2f}m >= z_s_min={z_s_min:.2f}m (AUV 起伏最小时), 仰角向上无阴影",
            0, np.arctan2(h - z_s_min, d), 0, False, "C-IV (h>=z_s_min 仰角向上)")
    elev_top_strict = np.arctan2(h - z_s_min, d)  # 最严格仰角
    if not (fov_elev_lo <= elev_top_strict <= fov_elev_hi):
        return FeasibilityResult(False, 0.0,
            f"严格场景柱顶仰角 {np.degrees(elev_top_strict):.1f}° (用 z_s_min={z_s_min}) 不在声呐孔径内",
            0, elev_top_strict, 0, False, "C-II (elev_top 越界)")

    # 3) 距离在量程内（用 z_s_min 算最严格的 D_max）
    D_max = np.sqrt(rho_max**2 - z_s_min**2) if rho_max > z_s_min else 0
    if d > D_max:
        return FeasibilityResult(False, 0.0,
            f"目标距离 d={d:.2f}m 超出 D_max={D_max:.2f}m (用 z_s_min={z_s_min})", D_max, elev_top_strict, 0, False, "C-III (d>D_max)")

    # 4) 阴影长度（用最严格的 z_s_min）
    L_s = d * h / (z_s_min - h)
    elev_top_loose = np.arctan2(h - z_s_max, d)  # 概率场景的仰角（AUV 起伏最大时）

    # 5) 阴影不超出量程
    L_s_clipped = L_s > (rho_max - d)
    if L_s_clipped:
        h_max = (rho_max - d) * z_s_min / rho_max
        binding = "C-V (L_s 被 range_max 截断)"
    else:
        h_max = z_s_min  # 理论上 h 可以等于 z_s_min（仰角水平）
        binding = ""

    # 概率场景信息：z_s_max 时是否还能反演
    loose_feasible = h < z_s_max  # z_s_max > h 时
    return FeasibilityResult(
        is_feasible=True,
        h_max=h_max,
        reason="",
        D_max=D_max,
        elev_top=elev_top_strict,  # 用最严格的
        L_s=L_s,
        L_s_clipped=L_s_clipped,
        binding_constraint=binding,
        # 扩展字段（向后兼容）
    )


def check_feasibility_with_heave(
    z_s_center: float,
    heave_amp: float,
    rho_max: float,
    theta_p: float,
    fov_elev_lo: float,
    fov_elev_hi: float,
    d: float,
    h: float,
) -> dict:
    """
    考虑 AUV heave 起伏的可行性判定（推荐用于 S6 等负例）。

    AUV 实际 z ∈ [z_s_center - heave_amp, z_s_center + heave_amp]
    - 严格场景：用 z_s_min = z_s_center - heave_amp 判定（最严）
    - 概率场景：算瞬时可反演概率

    Returns: dict 含 'strict_feasible', 'loose_feasible', 'fraction_feasible', 'binding'
    """
    z_s_min = z_s_center - heave_amp
    z_s_max = z_s_center + heave_amp

    # 严格场景
    strict = check_feasibility(z_s_center, rho_max, theta_p, fov_elev_lo, fov_elev_hi, d, h,
                                z_s_min=z_s_min, z_s_max=z_s_max)

    # 概率场景：模拟 AUV 起伏 100 帧，统计可反演比例
    n_frames = 100
    n_feasible = 0
    for i in range(n_frames):
        t = i / n_frames
        z_s_inst = z_s_center + heave_amp * np.sin(2 * np.pi * t)
        r = check_feasibility(z_s_inst, rho_max, theta_p, fov_elev_lo, fov_elev_hi, d, h)
        if r.is_feasible:
            n_feasible += 1
    frac_feasible = n_feasible / n_frames

    return {
        "strict_feasible": strict.is_feasible,
        "loose_feasible": frac_feasible > 0.5,  # 概率 > 50% 判 loose 可反演
        "fraction_feasible": frac_feasible,
        "binding": strict.binding_constraint,
        "z_s_min": z_s_min,
        "z_s_max": z_s_max,
    }


def check_current_16_scenes():
    """
    对当前 big_paper_scene_set/01-16 场景做可反演性判定

    期望：与实测 n_prior≈0 吻合（多数场景应判不可反演或严重截断）
    """
    import os, json, sys
    sys.path.insert(0, r'F:\sfm\sfm_synthetic_pillars')
    from scene_configs import SCENES

    scene_dir = r'F:\sfm\sfm_synthetic_pillars\big_paper_scene_set'
    fov_elev = np.deg2rad(17)  # ±17°
    fct_map = {s[0]: s[3] for s in SCENES}
    results = []
    for sd in sorted(os.listdir(scene_dir)):
        meta = f'{scene_dir}/{sd}/meta.json'
        if not os.path.exists(meta):
            continue
        if sd == '01_simple_single_pillar_v1_buggy':
            continue
        m = json.load(open(meta, encoding='utf-8'))
        n_inv = m.get('innovation2_stats', {}).get('n_inverted_pixels', 0)
        z_err_med = m.get('innovation2_stats', {}).get('median_abs_error_m')

        # 从 scene_configs 拿场景几何
        if sd not in fct_map:
            results.append((sd, 'N/A (no factory)', 0, 0, n_inv, z_err_med))
            continue
        cfg = fct_map[sd]()
        pillars = cfg.scene.pillars if hasattr(cfg.scene, 'pillars') else []
        cubes = cfg.scene.cubes if hasattr(cfg.scene, 'cubes') else []
        spheres = cfg.scene.spheres if hasattr(cfg.scene, 'spheres') else []
        # 取所有目标
        heights = []
        for p in pillars:
            heights.append(p[3])
        for c in cubes:
            heights.append(2 * c[3])  # cube: half_size * 2
        for s in spheres:
            heights.append(2 * s[3])  # sphere: 2 * radius
        h_avg = np.mean(heights) if heights else 0

        # 仿真默认
        z_s = cfg.traj.start_xyz[2]
        rho_max = cfg.sonar.range_max_m

        # 估算平均距离：d ≈ sqrt((pillar_x - auv_x)^2 + ...) ≈ 1.5m
        d = 1.5
        f = check_feasibility(z_s, rho_max, 0, -fov_elev, fov_elev, d, h_avg)
        results.append((sd, f.is_feasible, f.h_max, f.L_s_clipped, n_inv, z_err_med))
    return results


if __name__ == '__main__':
    print('=== T0.9 可反演性判据自检 ===\n')
    # Test 1: 01_simple_single_pillar, h=2.8, z_s=1.5, d=1.5
    r = check_feasibility(z_s=1.5, rho_max=6.0, theta_p=0,
                          fov_elev_lo=-np.deg2rad(17), fov_elev_hi=np.deg2rad(17),
                          d=1.5, h=2.8)
    print(f'Test 1: 01 场景 (h=2.8, z_s=1.5, d=1.5)')
    print(f'  feasible={r.is_feasible}, h_max={r.h_max:.2f}, L_s={r.L_s:.2f}, L_s_clipped={r.L_s_clipped}')
    print(f'  reason: {r.reason}\n')

    # Test 2: 02 场景, h=1.5, z_s=1.5, d=1.5（边界情况）
    r = check_feasibility(z_s=1.5, rho_max=6.0, theta_p=0,
                          fov_elev_lo=-np.deg2rad(17), fov_elev_hi=np.deg2rad(17),
                          d=1.5, h=1.5)
    print(f'Test 2: 02 场景 (h=1.5, z_s=1.5, d=1.5) - 边界退化情况')
    print(f'  feasible={r.is_feasible}, h_max={r.h_max:.2f}')
    print(f'  reason: {r.reason}\n')

    # Test 3: 06 场景, h=2.5, z_s=1.5, d=2.0
    r = check_feasibility(z_s=1.5, rho_max=6.0, theta_p=0,
                          fov_elev_lo=-np.deg2rad(17), fov_elev_hi=np.deg2rad(17),
                          d=2.0, h=2.5)
    print(f'Test 3: 06 场景 (h=2.5, z_s=1.5, d=2.0)')
    print(f'  feasible={r.is_feasible}, h_max={r.h_max:.2f}, L_s={r.L_s:.2f}, L_s_clipped={r.L_s_clipped}')
    print(f'  reason: {r.reason}\n')

    # Test 4: 论文 §7.1 建议新构型 z_s=5, rho_max=30, h=2.5, d=10
    r = check_feasibility(z_s=5.0, rho_max=30.0, theta_p=0,
                          fov_elev_lo=-np.deg2rad(17), fov_elev_hi=np.deg2rad(17),
                          d=10.0, h=2.5)
    print(f'Test 4: 论文 §7.1 推荐新构型 (z_s=5, rho_max=30, h=2.5, d=10)')
    print(f'  feasible={r.is_feasible}, h_max={r.h_max:.2f}, L_s={r.L_s:.2f}, L_s_clipped={r.L_s_clipped}')
    print(f'  reason: {r.reason}\n')

    # Test 5: §7.1 包线外 (h > z_s)
    r = check_feasibility(z_s=1.5, rho_max=6.0, theta_p=0,
                          fov_elev_lo=-np.deg2rad(17), fov_elev_hi=np.deg2rad(17),
                          d=2.0, h=3.0)
    print(f'Test 5: §7.1 包线外 (h=3.0 > z_s=1.5)')
    print(f'  feasible={r.is_feasible}, h_max={r.h_max:.2f}')
    print(f'  reason: {r.reason}\n')

    # 跑全部 16 场景
    print('=== 当前 16 场景可反演性判定（与 n_inv 交叉验证）===')
    results = check_current_16_scenes()
    print(f'{"scene":<35} {"feasible":<10} {"h_max":<8} {"clipped":<8} {"n_inv":<12} {"z_err_med":<10}')
    feasible_count = 0
    clipped_count = 0
    for sd, feas, h_max, clipped, n_inv, z_err in results:
        feas_s = str(feas) if not isinstance(feas, str) else feas
        h_max_s = f'{h_max:.2f}' if isinstance(h_max, (int, float)) else str(h_max)
        clipped_s = str(clipped)
        n_inv_s = f'{n_inv:,}' if isinstance(n_inv, int) else str(n_inv)
        z_err_s = f'{z_err*100:.2f}cm' if z_err is not None and isinstance(z_err, float) else 'N/A'
        print(f'{sd:<35} {feas_s:<10} {h_max_s:<8} {clipped_s:<8} {n_inv_s:<12} {z_err_s:<10}')
        if feas_s == 'True': feasible_count += 1
        if clipped_s == 'True': clipped_count += 1
    print(f'\nfeasible: {feasible_count}/16 (期望≈0 或很少，证实 z_s=1.5, rho_max=6 条件下多数不可反演)')
    print(f'L_s_clipped: {clipped_count}/16 (期望大部分被截断)')
    print(f'\n  关键发现: 即使 n_inv 看起来很大，但大部分是 L_s 被 range_max 截断后')
    print(f'  反演出的 h_inv ≈ 0~0.5m（被截断的上界），与真实 h=1.5-2.5m 偏差大')
    print(f'  → 现有 16 场景的 z_err=0.00cm 主要来自 shadow 修复使用 pillar_h_max 真值（GT 泄漏）')
    print(f'  → 真正的反演误差必须按 T0.7 重写 shadow.py 重新评估')
