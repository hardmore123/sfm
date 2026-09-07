"""
R-X1 验证：std(φ) 版判据 + τ_z^crit（2026-09-05 复核）
======================================================

阶段表 R-X1 验收：
  - ARIS 主档 N=10 时 τ_z^crit 应为 4.2 cm
  - τ_z 三档 {2,5,10} cm 的盲区占比曲线
  - 与 TH1 数值表 (ARIS σ_ρ=10mm, N=10, τ_z=5cm ⇒ 3.6°) 复现一致

测试项：
  T1. blind_angle_std 复现 TH1 数值表
  T2. tau_z_crit ARIS N=10 = 4.2 cm
  T3. blind_fraction_curve 论文速查表
  T4. aris_main_profile / aris_wide_profile 两档对比
"""
import os
import sys
import numpy as np
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from feasibility import (
    blind_angle_std, tau_z_crit, blind_fraction_curve,
    aris_main_profile, aris_wide_profile,
    ARIS_MAIN, ARIS_WIDE,
)


def test_t1_th1_value_table():
    """复现 TH1 数值表：ARIS σ_ρ=10mm, N=10, τ_z=5cm ⇒ 3.6°；τ_z=2cm ⇒ 9.1° 超孔径。"""
    print("\n=== T1: blind_angle_std 复现 TH1 数值表 ===")
    sigma_rho = 0.01   # 10 mm
    N = 10
    tau_z_5cm = 0.05
    tau_z_2cm = 0.02

    phi_blind_5cm = blind_angle_std(sigma_rho, N, tau_z_5cm)
    phi_blind_2cm = blind_angle_std(sigma_rho, N, tau_z_2cm)
    print(f"  ARIS σ_ρ=10mm, N=10:")
    print(f"  τ_z=5cm  ⇒ Δφ_min = {np.degrees(phi_blind_5cm):.2f}° (TH1 期望 3.6°)")
    print(f"  τ_z=2cm  ⇒ Δφ_min = {np.degrees(phi_blind_2cm):.2f}° (TH1 期望 9.1°)")
    # 验收
    assert abs(np.degrees(phi_blind_5cm) - 3.6) < 0.2, \
        f"τ_z=5cm 偏差 {abs(np.degrees(phi_blind_5cm) - 3.6):.2f}° 超过 0.2° 容差"
    assert abs(np.degrees(phi_blind_2cm) - 9.1) < 0.2, \
        f"τ_z=2cm 偏差 {abs(np.degrees(phi_blind_2cm) - 9.1):.2f}° 超过 0.2° 容差"
    # 9.1° > ARIS 主档 7.5° ⇒ 超孔径
    assert np.degrees(phi_blind_2cm) > 7.5, "9.1° 应超 ARIS 主档 7.5° 孔径"
    print(f"[OK] TH1 数值表复现：3.6° / 9.1°（后者超主档孔径）")
    return True


def test_t2_tau_z_crit():
    """ARIS 主档 N=10 时 τ_z^crit 应为 4.2 cm。"""
    print("\n=== T2: tau_z_crit ARIS N=10 = 4.2 cm ===")
    sigma_rho = 0.01
    N = 10
    phi_max = ARIS_MAIN["phi_max_rad"]   # 7.5°

    tau_c = tau_z_crit(sigma_rho, N, phi_max)
    print(f"  σ_ρ={sigma_rho*1000}mm, N={N}, φ_max=7.5°")
    print(f"  τ_z^crit = {tau_c*100:.2f} cm (期望 4.2 cm)")
    # 验收
    assert abs(tau_c * 100 - 4.2) < 0.2, f"τ_z^crit 偏差 {abs(tau_c*100-4.2):.2f}cm 超过 0.2cm"
    print(f"[OK] τ_z^crit = {tau_c*100:.2f} cm (4.2 cm 复现)")
    return True


def test_t3_blind_fraction_curve():
    """τ_z 三档 {2, 5, 10} cm 的盲区占比曲线。"""
    print("\n=== T3: blind_fraction_curve τ_z 三档曲线 ===")
    sigma_rho = 0.01
    N = 10
    phi_max = ARIS_MAIN["phi_max_rad"]
    curve = blind_fraction_curve(sigma_rho, N, phi_max, tau_z_list=(0.02, 0.05, 0.10))
    print(f"  ARIS 主档 (φ_max=7.5°, N=10, σ_ρ=10mm):")
    print(f"  τ_z^crit = {curve['tau_z_crit_cm']:.2f} cm")
    print(f"  {'τ_z':<10} {'Δφ_min':<12} {'盲区占比':<10}")
    for tz, info in curve["by_tau_z"].items():
        print(f"  {tz*100:.1f}cm{'':<5} {info['phi_blind_min_deg']:.2f}°{'':<7} {info['fraction_blind_pct']:.1f}%")
    # 验收
    f_2 = curve["by_tau_z"][0.02]["fraction_blind_pct"]
    f_5 = curve["by_tau_z"][0.05]["fraction_blind_pct"]
    f_10 = curve["by_tau_z"][0.10]["fraction_blind_pct"]
    # τ_z=10cm 盲区占比应该 < τ_z=2cm 盲区占比
    assert f_10 < f_5 < f_2, f"τ_z 越大盲区占比应越小：f_2={f_2}%, f_5={f_5}%, f_10={f_10}%"
    # τ_z=5cm ≈ 50% 盲区占比
    assert 30 < f_5 < 70, f"τ_z=5cm 盲区占比应在 [30%, 70%]，实际 {f_5}%"
    print(f"[OK] 盲区占比单调递减：f(2cm)={f_2:.0f}% > f(5cm)={f_5:.0f}% > f(10cm)={f_10:.0f}%")
    return True


def test_t4_aris_main_vs_wide():
    """ARIS 主档 vs 宽孔径敏感性档对比。"""
    print("\n=== T4: ARIS 主档 vs 宽孔径档 ===")
    main = aris_main_profile(N=10)
    wide = aris_wide_profile(N=10)
    print(f"  主档 (±7.5°):  τ_z^crit = {main['tau_z_crit_cm']:.2f} cm")
    print(f"  宽孔径 (±17°): τ_z^crit = {wide['tau_z_crit_cm']:.2f} cm")
    for tz, info in main["by_tau_z"].items():
        f_main = info["fraction_blind_pct"]
        f_wide = wide["by_tau_z"][tz]["fraction_blind_pct"]
        print(f"  τ_z={tz*100:.0f}cm: 主档 {f_main:.0f}% / 宽孔径 {f_wide:.0f}%")
    # 验收：宽孔径档 τ_z^crit 物理上应更小
    #   τ_z^crit = √3·σ_ρ/(√N·φ_max) ∝ 1/φ_max
    #   宽孔径（φ_max 大）下，给定 τ_z 引起的盲区占比小，
    #   ⇒ 只有 τ_z 更小（要求更高）才能触发 50% 盲区 ⇒ τ_z^crit 更小
    assert wide["tau_z_crit_cm"] < main["tau_z_crit_cm"], \
        f"宽孔径档 τ_z^crit 应更小（φ_max 大 ⇒ 盲区占比低）"
    # 同样 τ_z，宽孔径档盲区占比应更小
    for tz in (0.02, 0.05, 0.10):
        assert wide["by_tau_z"][tz]["fraction_blind"] < main["by_tau_z"][tz]["fraction_blind"], \
            f"τ_z={tz}: 宽孔径档盲区占比应更小"
    print(f"[OK] 宽孔径档 τ_z^crit = {wide['tau_z_crit_cm']:.2f} cm < 主档 {main['tau_z_crit_cm']:.2f} cm")
    return True


def main():
    print("=" * 60)
    print("R-X1 验证（2026-09-05）：std(φ) 版 + τ_z^crit")
    print("=" * 60)
    test_t1_th1_value_table()
    test_t2_tau_z_crit()
    test_t3_blind_fraction_curve()
    test_t4_aris_main_vs_wide()
    print("\n=== 全部 4 项测试通过 ===")
    print(f"\n=== 论文速查（ARIS 主档 N=10）===")
    main = aris_main_profile()
    print(f"  ARIS 主档: φ_max=±7.5°, σ_ρ=10mm, N=10")
    print(f"  τ_z^crit = {main['tau_z_crit_cm']:.2f} cm")
    print(f"  τ_z {{2,5,10}} cm 盲区占比:")
    for tz, info in main["by_tau_z"].items():
        print(f"    τ_z={tz*100:.0f}cm: Δφ_min={info['phi_blind_min_deg']:.2f}°, 占比={info['fraction_blind_pct']:.1f}%")


if __name__ == "__main__":
    main()
