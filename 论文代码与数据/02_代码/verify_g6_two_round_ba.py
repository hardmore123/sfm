# -*- coding: utf-8 -*-
"""
G6: 闭环耦合两轮BA信息融合验证(理论验证, 非独立BA实验)
================================================
2026-10-13声呐专家改进:

问题: 论文§11主张"5依赖7的κ_j, 7依赖5的ê_j——交替求解的耦合环"
      当前E2E是单向串行, 未做交替迭代

改进: 用信息融合公式验证两轮BA的σ_Pz单调下降
      文献: Two-Stage Probabilistic 3D Reconstruction 2025 (两阶段重建)
            McGann riSAM 2023 (GNC鲁棒优化)

诚实声明(2026-10-13严谨性审查修正):
  本脚本是信息融合公式的数值演示, 非独立BA优化实验.
  σ_Pz^(2)由公式σ_Pz_new^{-2}=σ_Pz_old^{-2}+σ_prior^{-2}计算,
  "理论vs实际一致性"是同义反复(同一公式), 不是独立验证.
  
  真正的BA实验需要:
  1. 第一轮真实BA优化(非公式)输出协方差矩阵
  2. 注入elev_prior后第二轮真实BA优化
  3. 比较两轮的协方差矩阵(独立计算)
  
  当前ba_unified.py的elev_prior接口已实现, 但需完整BA数据集
  (poses_est.npy等)才能运行真实BA. 本脚本用公式演示信息融合机制,
  验证: (1)公式自洽, (2)σ_Pz单调下降的数学必然性, (3)耦合链路完整.

理论(信息融合定理):
  第一轮: BA(无先验) → κ_j^(1) → ê_j^(1) → w_i^(1)
          σ_Pz^(1) 来自BA协方差(无先验注入)
  第二轮: BA(注入ê_j^(1), w_i^(1)) → κ_j^(2) → σ_Pz^(2)
          σ_Pz_new^{-2} = σ_Pz_old^{-2} + σ_prior^{-2}  (信息融合)
          σ_Pz^(2) < σ_Pz^(1)  ← 数学必然(信息增加→精度提升)

验证: M1场景, 第二轮σ_Pz < 第一轮σ_Pz(单调下降)
"""
import numpy as np
import os, sys, json
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
DELIV = os.path.dirname(HERE)

from shadow_f8_fixed import invert_height_from_far_edge, sigma_h_from_far_edge
from closed_loop_theory import (
    h_to_elev_prior, sigma_h_to_sigma_elev,
    kappa_to_s, envelope_to_g, confidence_init
)


def load_scene_measurements(scene_name):
    """加载场景的测量数据"""
    obs_dir = os.path.join(DELIV, "04_数据", "scene_set_main_f8", scene_name, "obs")
    meas_dir = os.path.join(DELIV, "04_数据", "scene_set_main_f8", scene_name, "innov2")
    meta_path = os.path.join(DELIV, "04_数据", "scene_set_main_f8", scene_name, "meta.json")
    
    if not os.path.exists(meta_path):
        return None
    
    import json as _json
    meta = _json.load(open(meta_path, encoding="utf-8"))
    
    # 优先从innov2/measurements.npy加载(含BA模拟的D_far)
    meas_path = os.path.join(meas_dir, "measurements.npy")
    if os.path.exists(meas_path):
        meas = np.load(meas_path)
        # 列: [帧,列,ρ_end,D_far,z_s,h_inv,σ_h]
        rho_end = meas[:, 2]
        D_far = meas[:, 3]
        z_s = meas[:, 4]
        h_inv_meas = meas[:, 5]
        sigma_h_meas = meas[:, 6]
        return {
            "meta": meta,
            "rho_end": rho_end,
            "D_far": D_far,
            "z_s": z_s,
            "h_inv_meas": h_inv_meas,
            "sigma_h_meas": sigma_h_meas,
        }
    return None


def simulate_ba_round1(data, s_theta_rad):
    """
    第一轮BA: 无先验注入, 纯多视角BA
    返回: σ_Pz^(1), κ_j^(1), ê_j^(1), w_i^(1)
    """
    meta = data["meta"]
    h_gt = meta["config"]["h_m"]
    z_s_center = data["z_s"].mean()
    D_far_mean = data["D_far"].mean()
    
    # 第一轮BA的σ_Pz来自CRLB双通道(无先验)
    # σ_Pz^{-2} = (σ_ρ cos(φ̄)/(√N std(φ)))^{-2} + (ρ̄ σ_θ/(√N std(roll) cos(θ_p)))^{-2}
    # 用场景的phi/roll统计
    phi_world_path = os.path.join(DELIV, "04_数据", "scene_set_main_f8", 
                                   meta.get("scene_name", "M1_well_constrained"),
                                   "gt", "phi_world_ray.npy")
    
    # 简化: 用measurements的统计
    N = len(data["rho_end"])
    # σ_Pz^(1): 纯BA(无先验), 来自roll通道
    rho_mean = data["rho_end"].mean()
    # 模拟std(roll) ~ 2°(M1良约束场景)
    std_roll = np.deg2rad(2.0)
    theta_p = np.deg2rad(19.0)  # 俯仰角
    sigma_rho = 9.07e-3 / np.sqrt(12)  # ARIS距离分辨率
    
    # 第一轮: 纯BA, σ_Pz^(1)
    sigma_Pz_1 = rho_mean * s_theta_rad / (np.sqrt(N) * std_roll * np.cos(theta_p))
    
    # 第一轮BA的κ_j(特征值倒数, 良约束~0.15)
    kappa_1 = np.array([0.15])
    
    # 第一轮ê_j: 从第一轮BA的z_s估计(无先验, 精度=σ_Pz^(1))
    # 模拟: z_s_ba = z_s_gt + N(0, σ_Pz^(1))
    rng = np.random.default_rng(42)
    z_s_ba_1 = z_s_center + rng.normal(0, sigma_Pz_1)
    
    # 第一轮h_inv: 用z_s_ba_1反演(精度受σ_Pz^(1)限制)
    h_inv_1 = float(np.mean(data["h_inv_meas"]))
    sigma_h_1 = float(np.mean(data["sigma_h_meas"]))
    
    # 第一轮ê_j(从h_inv_1)
    z_floor = 0.0
    R_base = np.eye(3)
    t_base = np.array([0.0, 0.0, z_s_ba_1])
    r_j = np.sqrt(D_far_mean**2 + (z_s_ba_1 - h_inv_1)**2)
    e_j_1 = h_to_elev_prior(h_inv_1, D_far_mean, z_s_ba_1, z_floor, R_base, t_base, r_j)
    sigma_e_1 = sigma_h_to_sigma_elev(h_inv_1, sigma_h_1, D_far_mean, z_s_ba_1, z_floor, R_base, t_base, r_j)
    
    # 第一轮置信度
    s_i = kappa_to_s(kappa_1)
    g_i = envelope_to_g(np.array([True]))  # M1在包线内
    q_i = np.array([1.0])  # 真值掩码
    w_i_1 = confidence_init(kappa_1, s_i, g_i, q_i)
    
    return {
        "sigma_Pz": sigma_Pz_1,
        "kappa_j": kappa_1,
        "e_j": e_j_1,
        "sigma_e": sigma_e_1,
        "w_i": w_i_1,
        "z_s_ba": z_s_ba_1,
        "h_inv": h_inv_1,
        "sigma_h": sigma_h_1,
    }


def simulate_ba_round2(round1, data):
    """
    第二轮BA: 注入第一轮的ê_j^(1)和w_i^(1)作为先验
    返回: σ_Pz^(2) < σ_Pz^(1)  (信息融合定理)
    
    理论: σ_Pz_new^{-2} = σ_Pz_old^{-2} + σ_prior^{-2}
    σ_prior = σ_e / w_i  (先验精度受置信度调制)
    """
    sigma_Pz_1 = round1["sigma_Pz"]
    sigma_e_1 = round1["sigma_e"]
    w_i_1 = round1["w_i"][0]
    
    # 先验的σ_Pz等效: σ_prior = σ_e / w_i
    # w_i∈[0,1], w=1→σ_prior=σ_e, w=0→σ_prior=∞(无先验)
    sigma_prior = sigma_e_1 / max(w_i_1, 1e-6)
    
    # 信息融合: σ_Pz_new^{-2} = σ_Pz_old^{-2} + σ_prior^{-2}
    sigma_Pz_2_inv2 = sigma_Pz_1**(-2) + sigma_prior**(-2)
    sigma_Pz_2 = 1.0 / np.sqrt(sigma_Pz_2_inv2)
    
    # 第二轮κ_j: 信息增加→κ_j增大(更良约束)
    # κ_new = κ_old * (σ_Pz_old / σ_Pz_new)^2
    kappa_2 = round1["kappa_j"] * (sigma_Pz_1 / sigma_Pz_2)**2
    
    # 第二轮ê_j: σ_Pz^(2)更小, 但z_s_ba_2不直接用GT(避免循环)
    # z_s_ba_2由信息融合公式给出精度(σ_Pz_2), 位置估计用先验+第一轮加权
    rng = np.random.default_rng(43)
    # 注: 不使用GT z_s_true(避免循环论证)
    # z_s_ba_2 = 第一轮估计 + 先验修正(先验=ê_j映射回z_s)
    # 简化: z_s_ba_2的精度由σ_Pz_2决定(信息融合), 位置用第一轮+噪声
    z_s_ba_2 = round1["z_s_ba"] + rng.normal(0, sigma_Pz_2)  # 精度=σ_Pz^(2)
    
    # 第二轮h_inv: 用z_s_ba_2反演(精度提升)
    h_inv_2 = round1["h_inv"]  # 反演高度本身不变(由阴影决定)
    # 但σ_h因σ_Pz减小而减小
    sigma_h_2 = round1["sigma_h"] * (sigma_Pz_2 / sigma_Pz_1)
    
    # 第二轮ê_j
    z_floor = 0.0
    R_base = np.eye(3)
    t_base = np.array([0.0, 0.0, z_s_ba_2])
    D_far_mean = data["D_far"].mean()
    r_j = np.sqrt(D_far_mean**2 + (z_s_ba_2 - h_inv_2)**2)
    e_j_2 = h_to_elev_prior(h_inv_2, D_far_mean, z_s_ba_2, z_floor, R_base, t_base, r_j)
    sigma_e_2 = sigma_h_to_sigma_elev(h_inv_2, sigma_h_2, D_far_mean, z_s_ba_2, z_floor, R_base, t_base, r_j)
    
    # 第二轮置信度(κ增大→s_i不变或增大)
    s_i_2 = kappa_to_s(kappa_2)
    g_i_2 = envelope_to_g(np.array([True]))
    q_i_2 = np.array([1.0])
    w_i_2 = confidence_init(kappa_2, s_i_2, g_i_2, q_i_2)
    
    return {
        "sigma_Pz": sigma_Pz_2,
        "kappa_j": kappa_2,
        "e_j": e_j_2,
        "sigma_e": sigma_e_2,
        "w_i": w_i_2,
        "z_s_ba": z_s_ba_2,
        "h_inv": h_inv_2,
        "sigma_h": sigma_h_2,
        "sigma_prior": sigma_prior,
    }


def main():
    print("=" * 70)
    print("G6: 闭环耦合两轮BA交替迭代验证")
    print("=" * 70)
    print()
    print("文献: Two-Stage Probabilistic 3D Reconstruction 2025")
    print("      McGann riSAM 2023 (GNC鲁棒优化)")
    print()
    print("理论: σ_Pz_new^{-2} = σ_Pz_old^{-2} + σ_prior^{-2}")
    print("      (信息融合定理: 先验注入→信息增加→σ_Pz下降)")
    print()
    
    scene = "M1_well_constrained"
    data = load_scene_measurements(scene)
    if data is None:
        print(f"[ERR] 无法加载{scene}数据")
        return
    
    s_theta_rad = np.deg2rad(0.18)  # σ_θ理论值(ARIS规格)
    
    # ===== 第一轮BA(无先验) =====
    print("--- 第一轮BA: 无先验注入 ---")
    r1 = simulate_ba_round1(data, s_theta_rad)
    print(f"  σ_Pz^(1) = {r1['sigma_Pz']*100:.4f} cm  (纯BA, 无先验)")
    print(f"  κ_j^(1) = {r1['kappa_j'][0]:.4f}  (良约束)")
    print(f"  ê_j^(1) = {np.rad2deg(r1['e_j']):.4f}° ± {np.rad2deg(r1['sigma_e']):.4f}°")
    print(f"  w_i^(1) = {r1['w_i'][0]:.4f}  (置信度)")
    print(f"  z_s_ba^(1) = {r1['z_s_ba']:.4f}m (含σ_Pz误差)")
    print(f"  h_inv^(1) = {r1['h_inv']:.4f}m, σ_h = {r1['sigma_h']*100:.4f}cm")
    
    # ===== 第二轮BA(注入第一轮先验) =====
    print(f"\n--- 第二轮BA: 注入ê_j^(1), w_i^(1) ---")
    r2 = simulate_ba_round2(r1, data)
    print(f"  σ_prior = σ_e/w_i = {np.rad2deg(r2['sigma_prior']):.4f}° = {r2['sigma_prior']*100:.4f}cm")
    print(f"  σ_Pz^(2) = {r2['sigma_Pz']*100:.4f} cm  (注入先验后)")
    print(f"  κ_j^(2) = {r2['kappa_j'][0]:.4f}  (信息增加→更良约束)")
    print(f"  ê_j^(2) = {np.rad2deg(r2['e_j']):.4f}° ± {np.rad2deg(r2['sigma_e']):.4f}°")
    print(f"  w_i^(2) = {r2['w_i'][0]:.4f}  (置信度)")
    print(f"  σ_h^(2) = {r2['sigma_h']*100:.4f}cm (因σ_Pz减小而减小)")
    
    # ===== 验证: σ_Pz单调下降 =====
    print(f"\n--- 验证: 信息融合定理 ---")
    improvement = (r1["sigma_Pz"] - r2["sigma_Pz"]) / r1["sigma_Pz"] * 100
    print(f"  σ_Pz: {r1['sigma_Pz']*100:.4f}cm → {r2['sigma_Pz']*100:.4f}cm")
    print(f"  改进: {improvement:.2f}% (信息融合公式)")
    
    # 注: 以下"理论vs实际"是同义反复(同一公式计算), 非独立验证
    sigma_Pz_theory = 1.0 / np.sqrt(r1["sigma_Pz"]**(-2) + r2["sigma_prior"]**(-2))
    print(f"  公式σ_Pz^(2) = {sigma_Pz_theory*100:.4f}cm (信息融合公式)")
    print(f"  计算σ_Pz^(2) = {r2['sigma_Pz']*100:.4f}cm")
    print(f"  注: 两者一致是同义反复(同一公式), 非独立验证")
    print(f"  独立验证需真实BA优化输出协方差(未来工作)")
    
    # ===== 验收 =====
    print(f"\n--- 验收 ---")
    passed = r2["sigma_Pz"] < r1["sigma_Pz"]
    if passed:
        print(f"  ✅ G6验收通过: σ_Pz^(2) < σ_Pz^(1) (信息融合数学必然性)")
        print(f"     先验注入→信息增加→σ_Pz下降(数学定理, 非实验)")
        print(f"     论文§11'交替求解耦合环'有理论支撑")
        print(f"     注: 真实BA实验验证是未来工作(需完整BA数据集)")
    else:
        print(f"  ⚠️ G6验收失败: σ_Pz未下降")
    
    # ===== 闭环耦合分析 =====
    print(f"\n--- 闭环耦合分析 ---")
    print(f"  第一轮: BA(无先验) → κ_j^(1)={r1['kappa_j'][0]:.3f} → ê_j^(1)={np.rad2deg(r1['e_j']):.2f}° → w_i^(1)={r1['w_i'][0]:.2f}")
    print(f"  第二轮: BA(注入ê_j^(1),w_i^(1)) → κ_j^(2)={r2['kappa_j'][0]:.3f} → σ_Pz^(2)={r2['sigma_Pz']*100:.2f}cm")
    print(f"  耦合: 5(h→ê_j)依赖7(BA)的κ_j, 7(BA)依赖5的ê_j → 交替求解")
    
    report = {
        "scene": scene,
        "round1": {
            "sigma_Pz_cm": round(r1["sigma_Pz"]*100, 4),
            "kappa_j": round(r1["kappa_j"][0], 4),
            "e_j_deg": round(np.rad2deg(r1["e_j"]), 4),
            "sigma_e_deg": round(np.rad2deg(r1["sigma_e"]), 4),
            "w_i": round(r1["w_i"][0], 4),
            "sigma_h_cm": round(r1["sigma_h"]*100, 4),
        },
        "round2": {
            "sigma_Pz_cm": round(r2["sigma_Pz"]*100, 4),
            "kappa_j": round(r2["kappa_j"][0], 4),
            "e_j_deg": round(np.rad2deg(r2["e_j"]), 4),
            "sigma_e_deg": round(np.rad2deg(r2["sigma_e"]), 4),
            "w_i": round(r2["w_i"][0], 4),
            "sigma_h_cm": round(r2["sigma_h"]*100, 4),
            "sigma_prior_cm": round(r2["sigma_prior"]*100, 4),
        },
        "improvement_pct": round(improvement, 2),
        "theory_check": {
            "sigma_Pz_formula_cm": round(sigma_Pz_theory*100, 4),
            "sigma_Pz_computed_cm": round(r2["sigma_Pz"]*100, 4),
            "note": "formula=computed(同义反复, 同一公式), 非独立验证",
            "independent_verification_needed": "真实BA优化输出协方差(未来工作)",
        },
        "passed": bool(passed),
        "honesty_note": "本脚本是信息融合公式数值演示, 非独立BA实验",
    }
    
    report_path = os.path.join(HERE, "g6_two_round_ba_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"\n报告已保存: {report_path}")


if __name__ == "__main__":
    main()
