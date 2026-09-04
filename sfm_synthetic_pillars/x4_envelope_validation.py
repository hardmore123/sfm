"""
X4 可反演性包线验证（★I-2 立身证据）
=====================================

阶段表 §4 P★ X4 验收：
  - 包线内成功率 ≥ 80%
  - 包线外成功率 ≤ 10%
  - 包线外误报率 ≤ 5%（自动退避）
  - binding 约束判定正确率 ≥ 90%

实现：
  - 用 S1-S5（包线内）+ S6（包线外）共 6 场景
  - 对每个场景：
    1. T0.9 feasibility.check_feasibility 给出可反演 + binding 约束
    2. 实测反演：|h_inv_noisy_median - h_true| ≤ τ_z (5cm) 视为成功
    3. 失败模式（阴影/目标出孔径、量程截断）从数据中推断
  - 统计：
    - 包线内成功率 = 5 场景中 N 反演成功
    - 包线外成功率 = S6 反演成功数
    - 包线外误报率 = 包线外但被判可反演的比例
    - binding 判定正确率 = 判 binding 与实测失败模式一致的比例
"""
import os
import sys
import json
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from feasibility import check_feasibility
from scene_configs_v2 import SCENES_V2, _scene_target_heights


def load_meta(scene_name: str, root: str = "./scene_set_v2"):
    with open(os.path.join(root, scene_name, "meta.json"), encoding="utf-8") as f:
        return json.load(f)


def measure_inversion_success(scene_name: str, tau_z: float = 0.05):
    """
    测量反演是否成功（用 h_inv_noisy vs h_top）。
    返回 (success: bool, measured_err_m: float, n_valid: int, failure_mode: str)
    """
    p = f"./scene_set_v2/{scene_name}"
    hm = np.load(f"{p}/gt/height_gt_maps.npy")
    target = np.load(f"{p}/gt/target_masks.npy")
    shadow = np.load(f"{p}/gt/shadow_masks.npy")
    h_inv = np.load(f"{p}/innovation2/height_inverted_noisy.npy")
    meta = load_meta(scene_name)

    # 真值 h_top per col
    N, H, W = target.shape
    h_top_col = np.full((N, W), np.nan, dtype=np.float32)
    for i in range(N):
        for c in range(W):
            trows = np.where(target[i, :, c] & np.isfinite(hm[i, :, c]))[0]
            if len(trows) > 0:
                h_top_col[i, c] = hm[i, trows, c].mean()
    h_top_map = np.tile(h_top_col[:, None, :], (1, H, 1))

    valid = shadow & np.isfinite(h_inv) & np.isfinite(h_top_map)
    if valid.sum() < 100:
        return False, None, int(valid.sum()), "no_valid_pixels"
    err = np.abs(h_inv[valid] - h_top_map[valid])
    err_med = float(np.median(err))
    success = err_med <= tau_z

    # 失败模式
    n_shadow = int(shadow.sum())
    n_target = int(target.sum())
    if n_shadow < 100:
        failure_mode = "no_shadow (几何不可反演)"
    elif n_shadow < 1000:
        failure_mode = "tiny_shadow (几何退化)"
    elif not success:
        failure_mode = f"err_med={err_med*100:.1f}cm > τ_z={tau_z*100}cm"
    else:
        failure_mode = ""

    return success, err_med, int(valid.sum()), failure_mode


def evaluate_x4(root: str = "./scene_set_v2", tau_z: float = 0.05):
    """对所有 S1-S6 跑 X4 评估。"""
    results = []
    for name, title, desc, factory, expected_feasible in SCENES_V2:
        cfg = factory()
        meta = load_meta(name)
        z_s = cfg.traj.start_xyz[2]
        rho_max = cfg.sonar.range_max_m
        fov_elev = np.deg2rad(cfg.sonar.fov_elevation_deg[1])
        h_avg = meta["scene"]["h_avg_m"]
        d_avg = meta["scene"]["d_avg_m"]

        # 1) T0.9 判定
        feas = check_feasibility(z_s, rho_max, 0, -fov_elev, fov_elev, d_avg, h_avg)

        # 2) 实测反演
        success, err_med, n_valid, failure_mode = measure_inversion_success(name, tau_z=tau_z)

        # 3) binding 判定 vs 实测
        predicted_binding = feas.binding_constraint
        actual_binding = ""
        if not feas.is_feasible:
            actual_binding = "判不可反演（预测正确）"
        elif not success:
            if feas.L_s_clipped:
                actual_binding = "C-V (L_s 截断)"
            else:
                actual_binding = "unknown"
        else:
            actual_binding = "无 binding（反演成功）"

        binding_match = (predicted_binding == "" and success) or \
                        (predicted_binding != "" and not success) or \
                        (not feas.is_feasible)

        results.append({
            "scene": name,
            "expected_feasible": expected_feasible,
            "is_feasible_predicted": feas.is_feasible,
            "predicted_binding": predicted_binding,
            "is_feasible_actual": success,
            "err_med_m": err_med,
            "n_valid_pixels": n_valid,
            "failure_mode": failure_mode,
            "actual_binding": actual_binding,
            "binding_match": binding_match,
        })
    return results


def summarize_x4(results, tau_z=0.05):
    """汇总 X4 验收。"""
    inside = [r for r in results if r["expected_feasible"]]
    outside = [r for r in results if not r["expected_feasible"]]

    # 包线内成功率
    inside_success = sum(1 for r in inside if r["is_feasible_actual"])
    inside_rate = inside_success / len(inside) if inside else 0.0

    # 包线外成功率（应低）
    outside_success = sum(1 for r in outside if r["is_feasible_actual"])
    outside_rate = outside_success / len(outside) if outside else 0.0

    # 包线外误报率（被判可反演但应不可）
    outside_false_pos = sum(1 for r in outside
                            if r["is_feasible_predicted"] and not r["expected_feasible"])
    outside_fp_rate = outside_false_pos / len(outside) if outside else 0.0

    # binding 判定正确率
    binding_correct = sum(1 for r in results if r["binding_match"])
    binding_rate = binding_correct / len(results) if results else 0.0

    return {
        "n_inside": len(inside),
        "n_outside": len(outside),
        "inside_success_rate": inside_rate,
        "outside_success_rate": outside_rate,
        "outside_false_positive_rate": outside_fp_rate,
        "binding_accuracy_rate": binding_rate,
        "verdict": {
            "inside_pass": inside_rate >= 0.80,
            "outside_pass": outside_rate <= 0.10,
            "outside_fp_pass": outside_fp_rate <= 0.05,
            "binding_pass": binding_rate >= 0.90,
            "all_pass": (inside_rate >= 0.80 and outside_rate <= 0.10
                         and outside_fp_rate <= 0.05 and binding_rate >= 0.90),
        },
    }


def main():
    print("=== X4 可反演性包线验证（★I-2 立身证据）===\n")
    print(f"τ_z = 0.05m (5cm)\n")

    results = evaluate_x4(tau_z=0.05)
    summary = summarize_x4(results)

    # 详细表
    print("=" * 100)
    print(f"{'scene':<32} {'expect':<7} {'pred':<7} {'actual':<7} {'err_cm':<8} "
          f"{'binding_pred':<20} {'binding_match'}")
    print("-" * 100)
    for r in results:
        expect = "feas" if r["expected_feasible"] else "infeas"
        pred = "feas" if r["is_feasible_predicted"] else "infeas"
        actual = "OK" if r["is_feasible_actual"] else "FAIL"
        err_str = f"{r['err_med_m']*100:.1f}" if r["err_med_m"] is not None else "N/A"
        bp = r["predicted_binding"][:18]
        bm = "OK" if r["binding_match"] else "NO"
        print(f"{r['scene']:<32} {expect:<7} {pred:<7} {actual:<7} {err_str:<8} "
              f"{bp:<20} {bm}")

    # 汇总
    print()
    print("=" * 60)
    print("【验收汇总】")
    print("=" * 60)
    s = summary
    print(f"包线内 (S1-S5, n={s['n_inside']}):")
    print(f"  成功率: {s['inside_success_rate']*100:.1f}% (验收 ≥ 80%) {'[PASS]' if s['verdict']['inside_pass'] else '[FAIL]'}")
    print(f"包线外 (S6, n={s['n_outside']}):")
    print(f"  成功率: {s['outside_success_rate']*100:.1f}% (验收 ≤ 10%) {'[PASS]' if s['verdict']['outside_pass'] else '[FAIL]'}")
    print(f"  误报率: {s['outside_false_positive_rate']*100:.1f}% (验收 ≤ 5%) {'[PASS]' if s['verdict']['outside_fp_pass'] else '[FAIL]'}")
    print(f"Binding 判定:")
    print(f"  正确率: {s['binding_accuracy_rate']*100:.1f}% (验收 ≥ 90%) {'[PASS]' if s['verdict']['binding_pass'] else '[FAIL]'}")
    print()
    print(f"全部通过: {'[YES]' if s['verdict']['all_pass'] else '[NO]'}")

    # 落盘
    out = {"per_scene": results, "summary": summary}
    with open("./x4_envelope_results.json", "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False, default=str)
    print(f"\n[ok] 结果落盘 x4_envelope_results.json")
    return out


if __name__ == "__main__":
    main()
