"""
X2b heave 最优幅度精细扫（用 T1.2 真实数据补充）
==================================================

阶段表 §4 P★ X2b 验收：
  - 画出"真实良约束数"与"观测不足比例"随 A 的双曲线，找到交点
  - 实测最优 A 与 A_opt = D_t · tan(φ_max) 的相对偏差 ≤ 25%

数据来源：T1_2_HEAVE_BASELINE_REPORT.md
  - general 模式 heave 0.4 → 3.3% well, n_obs 1657
  - general 模式 heave 0.8 → 30.0% well, n_obs 1562
  - general 模式 heave 1.2 → 80.0% well, n_obs 1360
  - forward 模式 heave 0.4/0.8/1.2 → 6.7% well (恒定)

理论：
  - A_opt = D_t · tan(φ_max) 让 AUV 上下覆盖整个仰角孔径
  - 当 A < A_opt: AUV 摆动不充分 → well 比例低
  - 当 A > A_opt: AUV 摆动超出 FOV → 观测损失，well 比例也下降
"""
import os
import sys
import json
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


# T1.2 真实数据
T12_DATA = {
    "general": [
        {"heave": 0.4, "well_pct": 3.3, "n_obs": 1657},
        {"heave": 0.8, "well_pct": 30.0, "n_obs": 1562},
        {"heave": 1.2, "well_pct": 80.0, "n_obs": 1360},
    ],
    "forward": [
        {"heave": 0.4, "well_pct": 6.7, "n_obs": 1650},
        {"heave": 0.8, "well_pct": 6.7, "n_obs": 1650},
        {"heave": 1.2, "well_pct": 6.7, "n_obs": 1650},
    ],
}


def find_A_opt(D_t=12.0, phi_max_deg=17.0):
    """A_opt = D_t · tan(φ_max) 让 AUV 上下覆盖整个仰角孔径。"""
    return D_t * np.tan(np.deg2rad(phi_max_deg))


def fit_well_vs_heave():
    """用 T1.2 数据（3 点）拟合 well_pct 随 heave 变化的曲线。"""
    data = T12_DATA["general"]
    A = np.array([d["heave"] for d in data])
    W = np.array([d["well_pct"] for d in data])
    # 二次拟合 W = a * A² + b * A + c
    coeffs = np.polyfit(A, W, deg=2)
    return np.poly1d(coeffs)


def find_optimal_A_from_data():
    """从 T1.2 数据找最优 heave：well_pct ≥ 40% 目标的最小 heave。"""
    data = T12_DATA["general"]
    target_pct = 40.0
    # 排序按 heave
    data_sorted = sorted(data, key=lambda d: d["heave"])
    # 找首个 well_pct >= 40 的 heave
    for d in data_sorted:
        if d["well_pct"] >= target_pct:
            return d["heave"]
    return None  # 没找到


def main():
    print("=== X2b heave 最优幅度精细扫（用 T1.2 数据）===\n")

    A_opt = find_A_opt()
    print(f"理论 A_opt = D_t · tan(φ_max) = 12 · tan(17°) = {A_opt:.3f} m\n")

    # T1.2 数据
    print("=" * 70)
    print("【T1.2 真实数据】（general 模式，K=6 关键帧，h=2.8m 单柱）")
    print("=" * 70)
    print(f"{'heave(m)':<10} {'well_pct':<10} {'n_obs':<8} {'达标≥40%':<8} {'距离A_opt偏差'}")
    print("-" * 70)
    for d in T12_DATA["general"]:
        a = d["heave"]
        well = d["well_pct"]
        n = d["n_obs"]
        meets = "PASS" if well >= 40.0 else "FAIL"
        dev_pct = abs(a - A_opt) / A_opt * 100
        print(f"{a:<10.2f} {well:<10.1f} {n:<8} {meets:<8} {dev_pct:.1f}%")

    # 找最优 A
    print()
    print("=" * 70)
    print("【最优 heave 搜索】")
    print("=" * 70)
    best_A = find_optimal_A_from_data()
    if best_A is not None:
        dev_pct = abs(best_A - A_opt) / A_opt * 100
        print(f"实测最优 A (well_pct ≥ 40% 目标的最小 heave): {best_A:.2f} m")
        print(f"理论 A_opt: {A_opt:.3f} m")
        print(f"偏差: {dev_pct:.1f}%  (验收 ≤ 25%) {'[PASS]' if dev_pct <= 25 else '[FAIL]'}")
    else:
        print("T1.2 数据未达到 well_pct ≥ 40% 目标")
        dev_pct = 100.0
        best_A = None

    # 拟合曲线
    print()
    print("=" * 70)
    print("【二次拟合 W(heave) = a*A^2 + b*A + c】")
    print("=" * 70)
    try:
        poly = fit_well_vs_heave()
        print(f"  W(heave) = {poly.coeffs[0]:.2f}*A^2 + {poly.coeffs[1]:.2f}*A + {poly.coeffs[2]:.2f}")
        # 找 W(heave) = 40 的解
        roots = np.roots(poly.coeffs - np.array([0, 0, 40]))
        real_roots = roots[np.isreal(roots)].real
        real_roots = real_roots[(real_roots > 0) & (real_roots < 5)]
        if len(real_roots) > 0:
            interp_A = float(real_roots[0])
            print(f"  W = 40% 的解: heave = {interp_A:.3f} m")
            print(f"  vs A_opt = {A_opt:.3f} m 偏差: {abs(interp_A - A_opt)/A_opt*100:.1f}%")
        # W(heave) = 80 的解
        roots80 = np.roots(poly.coeffs - np.array([0, 0, 80]))
        real_roots80 = roots80[np.isreal(roots80)].real
        real_roots80 = real_roots80[(real_roots80 > 0) & (real_roots80 < 5)]
        if len(real_roots80) > 0:
            print(f"  W = 80% 的解: heave = {float(real_roots80[0]):.3f} m")
    except Exception as e:
        print(f"  拟合失败: {e}")

    # 报告
    out = {
        "t12_general_data": T12_DATA["general"],
        "t12_forward_data": T12_DATA["forward"],
        "A_opt_theory": A_opt,
        "best_A_data": best_A,
        "deviation_pct": dev_pct if best_A else None,
        "passed": bool(best_A is not None and dev_pct <= 25.0),
    }
    with open("./x2b_heave_results.json", "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(f"\n[ok] 结果落盘 x2b_heave_results.json")
    return out


if __name__ == "__main__":
    main()
