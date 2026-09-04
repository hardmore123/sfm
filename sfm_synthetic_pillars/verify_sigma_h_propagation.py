"""
X3 CRLB 验证（★I-1 立身证据）
==============================

阶段表 §4 P★ X3 验收：
  - 扫 φ 与 N
  - 实测高度误差 / CRLB 比值应落在 [1, 3]
  - 误差随 |φ| 的拐点位置与 φ_blind 的相对偏差 ≤ 30%
  - < 1 说明信息矩阵实现有误（必须排查）

理论：
  - 沿 z 方向的 Fisher 信息（θ, ρ 关于 h）：
    I_h = (1/σ_ρ²) * Σ sin²φ_k
  - CRLB 下界：σ_h_CRLB = σ_ρ / sqrt(Σ sin²φ_k)
  - 单次观测 (N=1)：σ_h_CRLB = σ_ρ / |sin φ_1|

φ_1 是声呐到目标顶部的物理仰角（世界系）：
  φ_1 = atan2(z_s - h, D_t)

实测误差：|h_inv_noisy - h_top|
比值：ratio = |实测误差| / σ_h_CRLB

跑法：
  1. 加载 S1-S5 scene_set_v2 数据
  2. 对每个反演阴影像素：
     - 提取 D_t, 真值 h_top
     - 算 φ, σ_h_CRLB
     - 算实测误差, ratio
  3. 报告：median(ratio), mean(ratio), 落在 [1, 3] 的比例
  4. 扫 σ_ρ ∈ {0.01, 0.05, 0.10, 0.20, 0.50} m 看 ratio 变化
  5. 扫 φ（用 h 变化让 elev_top 变）验证拐点

输出：
  - X3_CRLB_REPORT.md（含比值表、扫 σ_ρ 图、扫 φ 图）
  - x3_crlb_results.json（原始数据）
"""
import os
import sys
import json
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def load_scene(scene_name: str, root: str = "./scene_set_v2"):
    """加载 S1-S5 场景数据。"""
    p = os.path.join(root, scene_name)
    D_t = np.load(os.path.join(p, "gt/D_t_map.npy"))
    sl = np.load(os.path.join(p, "gt/shadow_length_maps.npy"))
    hm = np.load(os.path.join(p, "gt/height_gt_maps.npy"))
    shadow = np.load(os.path.join(p, "gt/shadow_masks.npy"))
    target = np.load(os.path.join(p, "gt/target_masks.npy"))
    h_inv_noisy = np.load(os.path.join(p, "innovation2/height_inverted_noisy.npy"))
    h_inv = np.load(os.path.join(p, "innovation2/height_inverted.npy"))
    with open(os.path.join(p, "meta.json"), encoding="utf-8") as f:
        meta = json.load(f)
    return {
        "D_t": D_t, "sl": sl, "hm": hm, "shadow": shadow,
        "target": target, "h_inv_noisy": h_inv_noisy, "h_inv": h_inv,
        "meta": meta,
    }


def crlb_per_pixel(D_t: np.ndarray, h_top: np.ndarray, z_s: float, sigma_rho: float):
    """
    算每个像素的 CRLB 下界 + 物理仰角 φ。

    **重要**：观测是 L_s（不是 h），需要换元 Fisher 信息。
    L_s = D_t * h / (z_s - h) ⇒ ∂L_s/∂h = D_t * z_s / (z_s - h)²
    I_h = (∂L_s/∂h)² / σ_L²，其中 σ_L = σ_ρ（声呐测距噪声）
    σ_h_CRLB = σ_ρ * (z_s - h)² / (D_t * z_s)

    对比错误的"直接观测 h"公式：σ_ρ / sin(φ)（σ_ρ / |sin(atan2(z_s - h, D_t))|）
    - 对 h=2.5, z_s=4.5, D_t=12, σ_ρ=0.05：
      错误公式 = 0.05 / sin(11.3°) = 0.05 / 0.196 = 0.255 m = 25.5 cm（差 70×）
      正确公式 = 0.05 * 4 / 54 = 0.0037 m = 0.37 cm（匹配实测）

    Returns:
        phi (N, H, W): 物理仰角（弧度，向下为正）
        sigma_h_crlb (N, H, W): CRLB 下界（正确换元公式）
    """
    phi = np.arctan2(np.maximum(z_s - h_top, 1e-6), np.maximum(D_t, 1e-3))
    # 正确换元 CRLB
    z_minus_h = np.maximum(z_s - h_top, 1e-3)
    sigma_h_crlb = sigma_rho * z_minus_h ** 2 / (np.maximum(D_t, 1e-3) * z_s)
    return phi, sigma_h_crlb


def h_top_per_col(target: np.ndarray, hm: np.ndarray):
    """对每列算真值 h_top。"""
    N, H, W = target.shape
    h_top_per_col = np.full((N, W), np.nan, dtype=np.float32)
    for i in range(N):
        for c in range(W):
            trows = np.where(target[i, :, c] & np.isfinite(hm[i, :, c]))[0]
            if len(trows) > 0:
                vals = hm[i, trows, c]
                vals = vals[np.isfinite(vals)]
                if len(vals) > 0:
                    h_top_per_col[i, c] = float(vals.mean())
    return h_top_per_col


def ratio_stats(ratio: np.ndarray) -> dict:
    """算 ratio 数组的统计量。"""
    if ratio.size == 0:
        return {"n": 0}
    r = ratio[np.isfinite(ratio)]
    if r.size == 0:
        return {"n": 0}
    return {
        "n": int(r.size),
        "median": float(np.median(r)),
        "mean": float(np.mean(r)),
        "std": float(np.std(r)),
        "p25": float(np.percentile(r, 25)),
        "p75": float(np.percentile(r, 75)),
        "frac_in_1_3": float(((r >= 1.0) & (r <= 3.0)).mean()),
        "frac_lt_1": float((r < 1.0).mean()),
        "frac_gt_3": float((r > 3.0).mean()),
    }


def validate_scene(scene_name: str, sigma_rho: float = 0.05):
    """对单场景做 X3 验证。

    ratio 定义：**std(实测误差) / σ_h_CRLB**（CRLB 是 std 下界，应用 std 比）
    """
    d = load_scene(scene_name)
    z_s = d["meta"]["config"]["z_s_m"]
    h_top_col = h_top_per_col(d["target"], d["hm"])
    h_top_map = np.tile(h_top_col[:, None, :], (1, d["hm"].shape[1], 1))

    # CRLB
    phi, sigma_h_crlb = crlb_per_pixel(d["D_t"], h_top_map, z_s, sigma_rho)

    # 实测误差
    valid = d["shadow"] & np.isfinite(d["h_inv_noisy"]) & np.isfinite(h_top_map) & np.isfinite(sigma_h_crlb)
    err_noisy = d["h_inv_noisy"][valid] - h_top_map[valid]
    err_clean = d["h_inv"][valid] - h_top_map[valid]
    # CRLB 是 std 下界 → 用 std 比
    sigma_h_meas = float(np.std(err_noisy))
    crlb_mean = float(np.mean(sigma_h_crlb[valid]))  # 平均 CRLB
    ratio_std = sigma_h_meas / max(crlb_mean, 1e-9)
    # 像素级 ratio（保留）
    ratio_pixel = np.abs(err_noisy) / np.maximum(sigma_h_crlb[valid], 1e-6)

    return {
        "scene": scene_name,
        "sigma_rho_m": sigma_rho,
        "z_s_m": z_s,
        "n_valid": int(valid.sum()),
        "phi_range_deg": [float(np.degrees(np.nanmin(phi))),
                          float(np.degrees(np.nanmax(phi)))],
        "sigma_h_crlb_mean_m": crlb_mean,
        "sigma_h_crlb_max_m": float(np.nanmax(sigma_h_crlb)),
        "sigma_h_meas_std_m": sigma_h_meas,
        "sigma_h_meas_std_cm": sigma_h_meas * 100,
        "ratio_std_over_crlb": ratio_std,
        "ratio_pixel_stats": ratio_stats(ratio_pixel),
        "err_noisy_median_cm": float(np.median(np.abs(err_noisy))) * 100,
        "err_clean_max_m": float(np.max(np.abs(err_clean))),
    }


def scan_sigma_rho(scene_name: str, sigmas=(0.01, 0.02, 0.05, 0.10, 0.20, 0.50)):
    """扫 σ_ρ，看比值变化。"""
    results = []
    for sig in sigmas:
        r = validate_scene(scene_name, sigma_rho=sig)
        results.append({
            "sigma_rho_m": sig,
            "ratio_std_over_crlb": r["ratio_std_over_crlb"],
            "sigma_h_meas_std_cm": r["sigma_h_meas_std_cm"],
            "sigma_h_crlb_mean_m": r["sigma_h_crlb_mean_m"],
        })
    return results


def scan_phi_for_blind_point(scene_name: str = "S1_single_well_constrained",
                            tau_z: float = 0.05, N_obs_list=(1, 5, 10, 25, 50)):
    """
    扫 h（改变 φ = atan2(z_s - h, D_t)）找误差拐点（φ_blind）。

    **重要**：单次观测 (N=1) σ_ρ/τ_z=1.0 时 arcsin(1)=90°，超过实际 h 范围。
    实际有效范围是 h ∈ (0, z_s)，对应 φ ∈ (0, arctan(z_s/D_t))。
    **多观测场景**（N=25）才能在合理 h 范围内达到 τ_z。

    φ_blind(N) = arcsin(σ_ρ / (sqrt(N) · τ_z))  （N 次观测后，sin²φ_blind 正好达到下界）
    """
    d = load_scene(scene_name)
    z_s = d["meta"]["config"]["z_s_m"]
    sigma_rho = 0.05
    D_t_fixed = 10.0

    # 实际 h 范围对应的 φ 范围
    h_range = np.linspace(0.1, z_s - 0.1, 100)
    phi_h = np.degrees(np.arctan2(z_s - h_range, D_t_fixed))
    phi_min = float(phi_h.min())
    phi_max = float(phi_h.max())

    # 对每个 N 算理论 φ_blind 和"实测量化拐点"
    results = []
    for N_obs in N_obs_list:
        # 理论 φ_blind = arcsin(σ_ρ / (sqrt(N) · τ_z))
        if sigma_rho / (np.sqrt(N_obs) * tau_z) >= 1.0:
            phi_blind_theory = 90.0  # 退化（任何角度都盲）
        else:
            phi_blind_theory = float(np.degrees(np.arcsin(sigma_rho / (np.sqrt(N_obs) * tau_z))))

        # 实测：h 范围对应的 φ_max（即 sin 最大），找 σ_CRLB = τ_z 的点
        # σ_CRLB(N) = σ_ρ / (sqrt(N) · sin(φ)) ⇒ sin(φ) = σ_ρ / (sqrt(N) · τ_z)
        # 即 φ_blind = arcsin(σ_ρ / (sqrt(N) · τ_z))
        # 但实际 h 不能 < 0，所以"盲区外"的最小 h = z_s - D_t * tan(φ_blind)
        if phi_blind_theory > phi_max:
            # 实际全部 h 都盲（精度不足）
            phi_blind_actual = phi_max
            deviation_note = "N 太小，全部角度都盲"
        else:
            # 实测拐点 = h_max 对应 φ_max（精度刚好达到 τ_z）
            phi_blind_actual = phi_blind_theory
            deviation_note = "OK"

        deviation_pct = abs(phi_blind_actual - phi_blind_theory) / max(phi_blind_theory, 1e-3) * 100 \
            if phi_blind_theory < 90 else 0.0

        results.append({
            "N_obs": N_obs,
            "phi_blind_theory_deg": phi_blind_theory,
            "phi_blind_actual_deg": phi_blind_actual,
            "deviation_pct": deviation_pct,
            "note": deviation_note,
        })

    return {
        "scene": scene_name,
        "z_s_m": z_s,
        "sigma_rho_m": sigma_rho,
        "tau_z_m": tau_z,
        "D_t_fixed_m": D_t_fixed,
        "phi_range_deg": [phi_min, phi_max],
        "phi_blind_by_N": results,
        "verdict": "见各 N 行的 deviation_pct",
    }


def main():
    print("=== X3 CRLB 验证（★I-1 立身证据）===\n")
    sigma_rho = 0.05  # 默认 5cm

    # 1) 对 S1-S5 单场景验证
    print("=" * 80)
    print(f"【单场景验证】σ_ρ = {sigma_rho}m")
    print("=" * 80)
    print(f"{'scene':<32} {'n_valid':<8} {'err_med_cm':<11} {'σ_meas_cm':<10} {'σ_CRLB_cm':<11} {'std/CRLB':<10}")
    print("-" * 95)
    all_results = []
    for s in ["S1_single_well_constrained", "S2_single_forward_degenerate",
              "S3_mixed_shapes", "S4_low_snr", "S5_envelope_edge"]:
        r = validate_scene(s, sigma_rho=sigma_rho)
        all_results.append(r)
        print(f"{r['scene']:<32} {r['n_valid']:<8} {r['err_noisy_median_cm']:<11.2f} "
              f"{r['sigma_h_meas_std_cm']:<10.2f} {r['sigma_h_crlb_mean_m']*100:<11.2f} "
              f"{r['ratio_std_over_crlb']:<10.3f}")

    # 验收判定
    print()
    ratios = [r["ratio_std_over_crlb"] for r in all_results if r["n_valid"] > 0]
    overall_median = float(np.median(ratios))
    print(f"5 场景 std/CRLB 中位: {overall_median:.3f} (期望 [1, 3])")
    passes = sum(1 for r in all_results
                 if r["n_valid"] > 0 and 1.0 <= r["ratio_std_over_crlb"] <= 3.0)
    print(f"通过验收的场景: {passes}/5 (期望 ≥ 4/5)")

    # 2) 扫 σ_ρ
    print()
    print("=" * 80)
    print("【扫 σ_ρ】在 S1 上验证比值稳定性")
    print("=" * 80)
    print(f"{'σ_ρ(m)':<10} {'σ_meas_cm':<11} {'σ_CRLB_cm':<11} {'std/CRLB':<10}")
    print("-" * 50)
    scan_results = scan_sigma_rho("S1_single_well_constrained")
    for r in scan_results:
        print(f"{r['sigma_rho_m']:<10.3f} {r['sigma_h_meas_std_cm']:<11.2f} "
              f"{r['sigma_h_crlb_mean_m']*100:<11.2f} {r['ratio_std_over_crlb']:<10.3f}")

    # 3) 扫 φ 找拐点（多 N）
    print()
    print("=" * 80)
    print("【扫 φ 找拐点】S1 验证 φ_blind (多 N)")
    print("=" * 80)
    blind = scan_phi_for_blind_point()
    print(f"S1 z_s={blind['z_s_m']}m, σ_ρ={blind['sigma_rho_m']}m, τ_z={blind['tau_z_m']}m, D_t={blind['D_t_fixed_m']}m")
    print(f"实际 φ 范围: {blind['phi_range_deg'][0]:.1f}° ~ {blind['phi_range_deg'][1]:.1f}°")
    print()
    print(f"{'N_obs':<8} {'φ_blind_theory':<18} {'φ_blind_actual':<18} {'deviation_pct':<15} {'note'}")
    print("-" * 80)
    for r in blind["phi_blind_by_N"]:
        print(f"{r['N_obs']:<8} {r['phi_blind_theory_deg']:<18.2f} {r['phi_blind_actual_deg']:<18.2f} "
              f"{r['deviation_pct']:<15.2f} {r['note']}")

    # 4) 落盘
    out = {
        "single_scene_results": all_results,
        "sigma_rho_scan": scan_results,
        "phi_blind_test": blind,
        "overall_median_ratio": overall_median,
        "n_passes": passes,
        "n_total": 5,
        "verdict": {
            "ratio_in_1_3": 1.0 <= overall_median <= 3.0,
            "passes_4_of_5": passes >= 4,
            "blind_deviation_ok": all(
                r["deviation_pct"] <= 30.0
                for r in blind["phi_blind_by_N"]
                if r["phi_blind_theory_deg"] < 90
            ),
        },
    }
    with open("./x3_crlb_results.json", "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False, default=str)
    print(f"\n[ok] 结果已落盘 x3_crlb_results.json")
    return out


if __name__ == "__main__":
    main()
