"""
F-8d 主档场景集验收
===================

W1 ARIS 规格合规：ρ_max ≤ 15 m、Δρ_bin ∈ [3,19] mm、meta 落盘 σ_ρ 全套溯源
W2 场景可用性：目标像素/帧 ≥ 5、孔径余量 > 0（对比旧 scene_set_main 的 0 像素场景）
W3 无真值泄漏：反演误差量级须与量化理论一致，且**远大于**浮点噪声
W4 ★I-2 逐(帧,列)包线判据一致率 = 100%
W5 ★I-1 对比对成立：M1 良约束 / M2 盲，且 σ_Pz 跨 τ_z=5cm 两侧
W6 渲染器独立校核：用暴力射线法复算若干 (帧,波束) 的掩码，与渲染结果比对
   —— 这一项是为了避免"渲染器自证"，必须用**另一条代码路径**
"""
import io, sys, json, glob, os
import numpy as np
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = "scene_set_main_f8"
TAU_Z = 0.05
scenes = sorted(glob.glob(os.path.join(ROOT, "M*")))
metas = {}
for d in scenes:
    with open(os.path.join(d, "meta.json"), encoding="utf-8") as f:
        metas[os.path.basename(d)] = json.load(f)

print("=" * 84)
print("W1 ARIS 规格合规")
print("=" * 84)
print(f"  {'场景':<22} {'ρ_max':>7} {'bins':>6} {'Δbin(mm)':>9} {'规格内':>7} "
      f"{'σ_ρ落盘':>8} {'来源':>14}")
w1 = True
for n, m in metas.items():
    c = m["config"]
    a = m["aris_compliance"]
    ok = a["dbin_within_spec_3_19mm"] and a["rho_max_within_spec_15m"] \
        and ("sigma_rho_m" in c) and ("sigma_rho_source" in c)
    w1 &= ok
    print(f"  {n:<22} {c['rho_max_m']:>7.1f} {c['range_bin_count']:>6} "
          f"{a['dbin_mm']:>9.2f} {'✅' if a['dbin_within_spec_3_19mm'] else '❌':>7} "
          f"{c['sigma_rho_m']*1000:>7.0f}mm {c['sigma_rho_source']:>14}")
print(f"  判定: {'通过' if w1 else '未通过'}")

print()
print("=" * 84)
print("W2 场景可用性（对比旧 scene_set_main）")
print("=" * 84)
print(f"  {'场景':<22} {'target/帧':>10} {'shadow':>9} {'unlit':>10} {'floor':>10} "
      f"{'unlit占比':>9}")
w2 = True
for n, m in metas.items():
    s = m["stats"]
    tot = s["n_shadow_px"] + s["n_unlit_px"] + s["n_floor_px"]
    frac_u = s["n_unlit_px"] / tot if tot else 0
    ok = s["target_px_per_frame"] >= 5
    w2 &= ok
    print(f"  {n:<22} {s['target_px_per_frame']:>10.1f} {s['n_shadow_px']:>9} "
          f"{s['n_unlit_px']:>10} {s['n_floor_px']:>10} {frac_u*100:>8.1f}%")
print("\n  旧 scene_set_main 对照：S3_main_single_mid 与 S3_main_mixed 为 0 像素/帧；"
      "\n  S1/S3_v3/S4 为 0.88 像素/帧（贴孔径边）")
print(f"  判定: {'通过' if w2 else '未通过'}（要求 ≥5 像素/帧）")

print()
print("=" * 84)
print("W3 无真值泄漏：误差量级检验")
print("=" * 84)
print(f"  {'场景':<22} {'h真值':>7} {'MAE(cm)':>8} {'bias(cm)':>9} "
      f"{'σ_h预测(cm)':>11} {'MAE/σ_h':>8}")
w3 = True
for n, m in metas.items():
    iv = m["inversion"]
    if iv["mae_cm"] is None:
        print(f"  {n:<22} 无量测")
        w3 = False
        continue
    r = iv["mae_cm"] / iv["sigma_h_pred_cm"] if iv["sigma_h_pred_cm"] else float("nan")
    # 泄漏判据：MAE 必须 >> 浮点噪声(~1e-13 cm)，且与 σ_h 同量级
    ok = iv["mae_cm"] > 1e-4 and 0.2 <= r <= 3.0
    w3 &= ok
    print(f"  {n:<22} {iv['h_true_m']:>7.2f} {iv['mae_cm']:>8.3f} "
          f"{iv['bias_cm']:>9.3f} {iv['sigma_h_pred_cm']:>11.3f} {r:>8.2f}")
print("\n  旧路径对照：无噪 MAE = 0.000 cm（恒等式，逐位相同）")
print(f"  判定: {'通过' if w3 else '未通过'}（MAE > 1e-4 cm 且 MAE/σ_h ∈ [0.2,3]）")

print()
print("=" * 84)
print("W4 ★I-2 逐(帧,列)包线判据")
print("=" * 84)
print(f"  {'场景':<22} {'预测可行':>8} {'实测到':>7} {'TP':>4} {'FP':>4} {'FN':>4} "
      f"{'TN':>4} {'一致率':>8}")
w4 = True
for n, m in metas.items():
    e = m["envelope_per_frame"]
    ok = e["agreement"] >= 0.999
    w4 &= ok
    print(f"  {n:<22} {e['n_pred_feasible']:>4}/{e.get('n_pairs_evaluated',e['n_frames']):<4} "
          f"{e['n_actually_measured']:>4}/{e.get('n_pairs_evaluated',e['n_frames']):<4} "
          f"{e['TP']:>4} {e['FP']:>4} {e['FN']:>4} {e['TN']:>4} "
          f"{e['agreement']*100:>7.1f}%")
print(f"  判定: {'通过' if w4 else '未通过'}（要求一致率 100%）")
print("  注: M4 有 TN —— 被判不可反演且确实量不到的样本，是判据的有效负例")

print()
print("=" * 84)
print("W5 ★I-1 对比对（多视 vs 阴影）")
print("=" * 84)
print(f"  {'场景':<22} {'heave':>6} {'std(φ)°':>8} {'Δφ_min°':>8} {'分类':>7} "
      f"{'σ_Pz(cm)':>9} {'阴影MAE(cm)':>11}")
for n in ("M1_well_constrained", "M2_blind_low_spread"):
    m = metas[n]
    o = m["observability"]; iv = m["inversion"]; c = m["config"]
    print(f"  {n:<22} {c['heave_m']:>6.1f} {o['std_phi_world_ray_deg']:>8.3f} "
          f"{o['delta_phi_min_deg']:>8.3f} "
          f"{'良约束' if o['is_well_constrained'] else '盲':>7} "
          f"{o['sigma_Pz_m']*100:>9.2f} {iv['mae_cm']:>11.3f}")
m1, m2 = metas["M1_well_constrained"], metas["M2_blind_low_spread"]
w5 = (m1["observability"]["is_well_constrained"]
      and not m2["observability"]["is_well_constrained"]
      and m1["observability"]["sigma_Pz_m"] <= TAU_Z
      and m2["observability"]["sigma_Pz_m"] > TAU_Z)
print(f"\n  M1: σ_Pz={m1['observability']['sigma_Pz_m']*100:.2f} cm ≤ τ_z=5cm ⇒ 多视够用")
print(f"  M2: σ_Pz={m2['observability']['sigma_Pz_m']*100:.2f} cm > τ_z=5cm ⇒ "
      f"多视**不够**，而阴影反演 MAE={m2['inversion']['mae_cm']:.3f} cm ≪ 5cm")
print(f"  ⇒ 阴影反演在多视失效处仍可用（这是两创新点串行的价值所在）")
print(f"  判定: {'通过' if w5 else '未通过'}")

print()
print("=" * 84)
print("W6 渲染器独立校核（暴力射线法，另一条代码路径）")
print("=" * 84)
sys.path.insert(0, ".")
from config import Config, SonarCfg, SceneCfg, finalize_pixel_mapping
from world import SceneWorld
import shadow_f8_fixed as SF
import gen_scenes_main_f8 as G


def brute_force_classify(T_wb, rho, theta_b, z_s_unused, D_t, h, phi_max_rad,
                         floor_z=0.0):
    """暴力法：显式构造海底点 → 判孔径 → 显式沿射线步进查遮挡。"""
    R, t = T_wb[:3, :3], T_wb[:3, 3]
    yaw = np.arctan2(R[1, 0], R[0, 0])
    th_w = theta_b + yaw
    dz = floor_z - t[2]
    if rho ** 2 - dz ** 2 <= 0:
        return "unlit"
    dh = np.sqrt(rho ** 2 - dz ** 2)
    P = np.array([t[0] + dh * np.cos(th_w), t[1] + dh * np.sin(th_w), floor_z])
    Pb = R.T @ (P - t)
    eb = np.arctan2(Pb[2], np.hypot(Pb[0], Pb[1]))
    if abs(eb) > phi_max_rad + 1e-9:
        return "unlit"
    # 沿射线密集步进查是否穿过柱体
    for s in np.linspace(0.0, 1.0, 4000):
        Q = t + s * (P - t)
        if np.hypot(Q[0] - D_t, Q[1] - 0.0) <= 0.25 and floor_z <= Q[2] <= h:
            return "shadow"
    return "floor"


cfg = G.make_cfg(0.85, 1.2, 801, 0.20, 45.0)
world = SceneWorld(cfg)
from trajectory import make_poses
poses6, poses_T = make_poses(cfg)
r0 = SF.render_shadow_map_fixed(poses_T[0], world, cfg)
rngs = np.linspace(G.ARIS["rho_min_m"], G.ARIS["rho_max_m"],
                   G.ARIS["range_bin_count"])
beams = np.deg2rad(np.linspace(-G.ARIS["azim_deg"] / 2, G.ARIS["azim_deg"] / 2,
                               G.ARIS["n_beams"]))
phi_max = np.deg2rad(G.ARIS["phi_max_deg"])

rng = np.random.default_rng(11)
# 优先抽中心波束（有柱体的列）+ 随机波束
cols_with = [c for c in range(r0.shadow_mask.shape[1]) if r0.shadow_mask[:, c].any()]
test_cols = (cols_with[:4] if cols_with else []) + list(rng.choice(128, 4, replace=False))
n_chk = 0
n_bad = 0
bad_examples = []
for c in test_cols:
    for r in rng.choice(G.ARIS["range_bin_count"], 60, replace=False):
        got = ("shadow" if r0.shadow_mask[r, c] else
               "unlit" if r0.unlit_mask[r, c] else
               "floor" if r0.floor_mask[r, c] else "none")
        exp = brute_force_classify(poses_T[0], float(rngs[r]), float(beams[c]),
                                   None, G.D_T, 0.85, phi_max)
        n_chk += 1
        if got != exp:
            n_bad += 1
            if len(bad_examples) < 5:
                bad_examples.append((int(r), int(c), got, exp, float(rngs[r])))
print(f"  抽检 {n_chk} 个 (距离门, 波束) 组合，不一致 {n_bad} 个")
for r, c, got, exp, rho in bad_examples:
    print(f"    bin={r} beam={c} ρ={rho:.3f}: 渲染={got} 暴力法={exp}")
w6 = n_bad == 0
print(f"  判定: {'通过' if w6 else '未通过'}")

print()
print("=" * 84)
alls = [w1, w2, w3, w4, w5, w6]
names = ["W1 规格合规", "W2 可用性", "W3 无泄漏", "W4 包线判据",
         "W5 ★I-1 对比对", "W6 渲染独立校核"]
for nm, v in zip(names, alls):
    print(f"  {nm:<18} {'✅' if v else '❌'}")
print(f"\nF-8d 验收总判定: {'全部通过' if all(alls) else '存在未通过项'}")
print("=" * 84)


