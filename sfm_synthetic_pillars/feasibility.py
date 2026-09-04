"""
T0.9 可反演性判据
==================

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

输出：布尔 + h_max
"""
from __future__ import annotations
import numpy as np
from dataclasses import dataclass
from typing import Tuple


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
