"""
F-8d 主档场景生成器（ARIS Explorer 3000 探测模式）
==================================================

与 `_gen_scenes_main_v2.py` 的关键差异：

| 项 | 旧 | 本生成器 |
|---|---|---|
| $\\rho_{max}$ | 40 m（**超 ARIS 规格 2.7 倍**） | **15 m**（探测模式 1.8 MHz 规格值） |
| range bin | 600 ⇒ Δ=65.9 mm（超规格 3.5 倍） | **1600 ⇒ Δ=9.07 mm**（居规格 3–19 mm 之中） |
| 下俯角 | 0°（逼出 40 m 量程） | **19°** |
| 阴影渲染 | `shadow.py`（孔径不裁剪 + 世界系/体系混用） | `shadow_f8_fixed.py` |
| $L_s$ | 解析真值逐像素写入 ⇒ **反演成恒等式** | 从掩码量测远端跳变 |
| $D_t$ | 由 $z_{top}$ 反算（用待估量算估计量） | **由 ★I(BA) 提供 + 注入定位噪声** |
| `meta.json` | 无 `sigma_rho_m` | 落盘 `sigma_rho_m` + `sigma_rho_source` 全套溯源 |

设计依据：`大论文思想路线/审计_20260906_阴影反演恒等式与孔径未裁剪.md`
场景表来源：`_f8_sceneset_design.json`（由 `_f8_design_sceneset.py` 生成并验收）
"""
from __future__ import annotations
import io
import sys
import os
import json
import time
from pathlib import Path
import numpy as np

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from config import (Config, SonarCfg, SensorNoiseCfg, SceneCfg, TrajCfg,
                    finalize_pixel_mapping)
from world import SceneWorld
from trajectory import make_poses, euler_to_matrix
import shadow_f8_fixed as SF
import feasibility as F

OUT_ROOT = Path("F:/sfm/sfm_synthetic_pillars/scene_set_main_f8")

# ---------------- 主档传感器（全部落在 ARIS 规格内）----------------
ARIS = dict(
    phi_max_deg=7.5,          # 垂直孔径（规格 14–15°）
    azim_deg=30.0,            # 方位孔径
    n_beams=128,
    rho_min_m=0.5,
    rho_max_m=15.0,           # 探测模式 1.8 MHz 有效量程
    range_bin_count=1600,     # ⇒ Δρ_bin = 9.07 mm
    sigma_rho_m=0.010,        # 规格 3–19 mm 取中
    sigma_theta_deg=0.18,
)
DBIN = (ARIS["rho_max_m"] - ARIS["rho_min_m"]) / (ARIS["range_bin_count"] - 1)

# ---------------- 基准几何（_f8_design_sceneset.py 择优）----------------
Z_S = 4.5
PITCH_DEG = 19.0
D_T = 10.6
N_FRAMES = 60

# D_t 由 ★I(BA) 给出的定位不确定度。水平方向是 BA 的强约束方向
# （★I-1 的整个论点就是"垂直难、水平易"），取与横向可分辨距离 d_R=4.4 cm
# 同量级的一半作为 1σ。
SIGMA_DT_M = 0.02
SIGMA_ZS_M = 0.02

# ---------------- 场景表 ----------------
SCENES = [
    # (name, h, heave, role, expected_invertible, seed, speckle, noise_floor)
    ("M1_well_constrained", 0.85, 1.2, "★I-1 良约束基准", True, 801, 0.20, 45.0),
    ("M2_blind_low_spread", 0.85, 0.1, "★I-1 盲（低离散度）", True, 802, 0.20, 45.0),
    # h 值由 _f8_design_sceneset.py 在**实际单侧起伏** z∈[z_s, z_s+A] 下扫出：
    # 包线内最大 h=1.08 m（含柱半径 r=0.25 的轮廓远边缘修正）（binding 为 H2 量程 ρ_end≤15），故 1.05 在内、1.12 在外。
    ("M3_envelope_inside", 1.05, 1.2, "★I-2 包线内（距边 3cm）", True, 803, 0.20, 45.0),
    ("M4_envelope_outside", 1.12, 1.2, "★I-2 包线外（应判不可反演）", False, 804, 0.20, 45.0),
    ("M5_low_snr", 0.85, 1.2, "★II 低 SNR", True, 805, 0.45, 38.0),
]


def make_cfg(h, heave, seed, speckle, noise_floor):
    cfg = Config(seed=seed)
    cfg.sonar = SonarCfg(
        fov_elevation_deg=(-ARIS["phi_max_deg"], ARIS["phi_max_deg"]),
        fov_azimuth_deg=(-ARIS["azim_deg"] / 2, ARIS["azim_deg"] / 2),
        beam_count=ARIS["n_beams"],
        range_bin_count=ARIS["range_bin_count"],
        range_min_m=ARIS["rho_min_m"],
        range_max_m=ARIS["rho_max_m"],
    )
    cfg.noise = SensorNoiseCfg(
        sigma_theta_rad=np.deg2rad(ARIS["sigma_theta_deg"]),
        sigma_rho_m=ARIS["sigma_rho_m"],
    )
    try:
        cfg.noise.speckle_sigma = speckle
        cfg.noise.noise_floor_db = noise_floor
    except Exception:
        pass
    cfg.traj = TrajCfg(
        n_frames=N_FRAMES,
        keyframe_indices=list(range(0, N_FRAMES, 5)),
        dt_s=0.20,
        motion_mode="general" if heave > 0 else "forward",
        start_xyz=(0.0, 0.0, Z_S),
        # ★ 关键：下俯 19°。正号 pitch = 下俯（已在 verify_f8a 中验证）
        start_rpy=(0.0, np.deg2rad(PITCH_DEG), 0.0),
        forward_total_m=0.0,
        sway_total_m=0.0,
        heave_amplitude_m=heave,
        # 纯旋转不改变声呐→地标的射线，不带来新的高度信息，
        # 且会扰动孔径覆盖 ⇒ 置 0，让 std(φ) 只由起伏（平移）驱动。
        pitch_amplitude_rad=0.0,
        yaw_amplitude_rad=0.0,
    )
    cfg.scene = SceneCfg(
        scene_type="pillar",
        pillars=[(D_T, 0.0, 0.25, h)],
        cubes=[], spheres=[], rubble=[],
        floor_z_m=0.0,
        surface_z_m=Z_S + 1.0,
    )
    cfg.scene.h_avg_m = h
    cfg.scene.d_avg_m = D_T
    finalize_pixel_mapping(cfg)
    return cfg


def world_ray_elev(poses6, P_w):
    """世界系射线俯角序列（CRLB 的 std(φ) 用这个，**不是**体系角）。"""
    d = np.hypot(P_w[0] - poses6[:, 0], P_w[1] - poses6[:, 1])
    return np.arctan2(P_w[2] - poses6[:, 2], d)


def poses6_to_T(p6):
    T = np.eye(4)
    T[:3, :3] = euler_to_matrix(p6[3], p6[4], p6[5])
    T[:3, 3] = p6[:3]
    return T


def gen_one(name, h, heave, role, expected, seed, speckle, noise_floor,
            verbose=True):
    t0 = time.time()
    cfg = make_cfg(h, heave, seed, speckle, noise_floor)
    world = SceneWorld(cfg)
    poses6, poses_T = make_poses(cfg)
    rngs = np.linspace(ARIS["rho_min_m"], ARIS["rho_max_m"],
                       ARIS["range_bin_count"])
    rng = np.random.default_rng(seed)

    if verbose:
        print(f"\n=== {name} ===  {role}")
        print(f"  h={h} heave={heave} z_s={Z_S} θ_p={PITCH_DEG}° D_t={D_T}")

    # ---- 渲染（修正版）
    tm, sm, um, fm, te = SF.render_all_fixed(poses_T, world, cfg, verbose=False)

    # ---- 逐帧逐列量测阴影远端 → 反演高度
    P_top = np.array([D_T, 0.0, h])
    R_PILLAR = 0.25
    beams = np.deg2rad(np.linspace(-ARIS["azim_deg"] / 2, ARIS["azim_deg"] / 2,
                                   ARIS["n_beams"]))
    recs = []
    for i in range(len(poses_T)):
        z_s_i = float(poses6[i, 2])
        R_i = poses_T[i][:3, :3]
        yaw_i = float(np.arctan2(R_i[1, 0], R_i[0, 0]))
        # 柱心水平距与方位，由 ★I(BA) 的地标点云给出
        dx = P_top[0] - poses6[i, 0]
        dy = P_top[1] - poses6[i, 1]
        d_h_c = float(np.hypot(dx, dy))
        th_c = float(np.arctan2(dy, dx))
        z_s_ba = z_s_i + float(rng.normal(0.0, SIGMA_ZS_M))
        for c in range(sm.shape[2]):
            if not sm[i, :, c].any():
                continue
            rho_end = SF.measure_shadow_far_edge(sm[i, :, c], fm[i, :, c], rngs)
            if not np.isfinite(rho_end):
                continue
            # 反演所需的水平参考是**轮廓远边缘** D_far，不是柱心 D_t。
            # 决定阴影长度的是轮廓远边缘（见 shadow_f8_fixed 的遮挡判据）；
            # 若误用柱心，会引入 +r 量级的系统偏置（本构型约 +8 cm）。
            # D_far 由 BA 的柱心 + 半径 + 已知波束方位算出，无需真值高度。
            dth = (th_c - (beams[c] + yaw_i) + np.pi) % (2 * np.pi) - np.pi
            s_ = d_h_c * np.sin(dth)
            disc = R_PILLAR ** 2 - s_ ** 2
            if disc < 0:
                continue
            D_far = d_h_c * np.cos(dth) + float(np.sqrt(disc))
            D_far_ba = D_far + float(rng.normal(0.0, SIGMA_DT_M))
            h_inv = SF.invert_height_from_far_edge(rho_end, D_far_ba, z_s_ba)
            if not np.isfinite(h_inv):
                continue
            s_h = SF.sigma_h_from_far_edge(
                rho_end, D_far_ba, z_s_ba,
                sigma_rho=DBIN / np.sqrt(12), sigma_Dt=SIGMA_DT_M,
                sigma_zs=SIGMA_ZS_M)
            recs.append((i, c, rho_end, D_far_ba, z_s_ba, h_inv, s_h))

    recs_arr = np.array(recs, dtype=np.float64) if recs else np.zeros((0, 7))

    # ---- 逐 (帧, 列) 包线预测 vs 实测（★I-2 的正确评估粒度）
    # 粒度必须到列：不同列的轮廓远边缘 d_far 不同（随方位偏移 dθ 变化），
    # 故同一帧内部分列可量测、部分不可。按帧聚合会产生虚假的 FN/FP。
    measured_pairs = set((int(r[0]), int(r[1])) for r in recs) if recs else set()
    pred_list, act_list = [], []
    for i in range(len(poses6)):
        z_i = float(poses6[i, 2])
        R_i = poses_T[i][:3, :3]
        yaw_i = float(np.arctan2(R_i[1, 0], R_i[0, 0]))
        dx = P_top[0] - poses6[i, 0]
        dy = P_top[1] - poses6[i, 1]
        d_h_c = float(np.hypot(dx, dy))
        th_c = float(np.arctan2(dy, dx))
        for c in range(sm.shape[2]):
            dth = (th_c - (beams[c] + yaw_i) + np.pi) % (2 * np.pi) - np.pi
            s_ = d_h_c * np.sin(dth)
            disc = R_PILLAR ** 2 - s_ ** 2
            if disc < 0:
                continue                      # 该列无柱体，不在评估集内
            d_far = d_h_c * np.cos(dth) + float(np.sqrt(disc))
            u_i = z_i - h
            if u_i <= 0:
                pred_list.append(False)
                act_list.append((i, c) in measured_pairs)
                continue
            D_e_i = d_far * z_i / u_i
            rho_end_i = float(np.hypot(D_e_i, z_i))
            # H2 量程 + H1' 照明带远界
            a_hi = np.deg2rad(PITCH_DEG) - np.deg2rad(ARIS["phi_max_deg"])
            il_far = z_i / np.sin(a_hi) if a_hi > 1e-9 else np.inf
            ok_ic = (rho_end_i <= ARIS["rho_max_m"]) and (rho_end_i <= il_far)
            pred_list.append(bool(ok_ic))
            act_list.append((i, c) in measured_pairs)
    frame_pred = np.array(pred_list, dtype=bool)
    frame_act = np.array(act_list, dtype=bool)
    tp_ = int((frame_pred & frame_act).sum())
    fp_ = int((frame_pred & ~frame_act).sum())
    fn_ = int((~frame_pred & frame_act).sum())
    tn_ = int((~frame_pred & ~frame_act).sum())

    # ---- 可观测性：std(世界系射线俯角)
    phi = world_ray_elev(poses6, P_top)
    std_phi = float(np.std(phi))
    n_obs = len(poses6)
    dphi_min = ARIS["sigma_rho_m"] / (np.sqrt(n_obs) * 0.05)
    sigma_Pz = (ARIS["sigma_rho_m"] / (np.sqrt(n_obs) * std_phi)
                if std_phi > 1e-12 else float("inf"))

    # ---- 落盘
    d = OUT_ROOT / name
    (d / "gt").mkdir(parents=True, exist_ok=True)
    (d / "obs").mkdir(parents=True, exist_ok=True)
    (d / "innov2").mkdir(parents=True, exist_ok=True)
    # obs/ = 传感器能观测到的量（反演只许读这里）
    np.save(d / "obs" / "target_masks.npy", tm)
    np.save(d / "obs" / "shadow_masks.npy", sm)
    np.save(d / "obs" / "unlit_masks.npy", um)
    np.save(d / "obs" / "floor_masks.npy", fm)
    np.save(d / "obs" / "target_elev_body.npy", te)
    # gt/ = 真值，**仅供评估**
    np.save(d / "gt" / "poses_gt.npy", poses6)
    np.save(d / "gt" / "pillar_top_gt.npy", P_top)
    np.save(d / "gt" / "phi_world_ray.npy", phi)
    np.save(d / "gt" / "frame_envelope_pred.npy", frame_pred)
    np.save(d / "gt" / "frame_measured.npy", frame_act)
    # innov2/ = 反演结果
    if recs_arr.size:
        np.save(d / "innov2" / "measurements.npy", recs_arr)

    h_inv_all = recs_arr[:, 5] if recs_arr.size else np.array([])
    s_h_all = recs_arr[:, 6] if recs_arr.size else np.array([])
    err = h_inv_all - h if h_inv_all.size else np.array([])

    meta = {
        "name": name,
        "role": role,
        "aperture_tier": "main_aris_7p5deg",
        "generator": "gen_scenes_main_f8.py",
        "design_source": "_f8_sceneset_design.json",
        "audit_ref": "审计_20260906_阴影反演恒等式与孔径未裁剪.md",
        "config": {
            "z_s_m": Z_S,
            "pitch_deg": PITCH_DEG,
            "D_t_m": D_T,
            "h_m": h,
            "heave_m": heave,
            "n_frames": N_FRAMES,
            "fov_elev_deg": [-ARIS["phi_max_deg"], ARIS["phi_max_deg"]],
            "fov_azim_deg": ARIS["azim_deg"],
            "beam_count": ARIS["n_beams"],
            "range_min_m": ARIS["rho_min_m"],
            "range_max_m": ARIS["rho_max_m"],
            "rho_max_m": ARIS["rho_max_m"],
            "range_bin_count": ARIS["range_bin_count"],
            # ---- σ_ρ 全套溯源（F-7 台账要求）
            "sigma_rho_m": ARIS["sigma_rho_m"],
            "sigma_rho_source": "aris_spec_mid",
            "sigma_rho_bin_m": float(DBIN),
            "sigma_rho_quant_m": float(DBIN / np.sqrt(12)),
            "sigma_rho_note": (
                "★I-1 链用 sigma_rho_m（tracks 的 rho_m 连续）；"
                "★II-1 链用 sigma_rho_quant_m = Δρ_bin/√12（L_s 沿距离轴量化）。"
                "见 sigma_rho_ledger.md §1b"),
            "sigma_Dt_m": SIGMA_DT_M,
            "sigma_zs_m": SIGMA_ZS_M,
            "speckle_sigma": speckle,
            "noise_floor_db": noise_floor,
        },
        "aris_compliance": {
            "dbin_mm": float(DBIN * 1000),
            "dbin_within_spec_3_19mm": bool(0.003 <= DBIN <= 0.019),
            "rho_max_within_spec_15m": bool(ARIS["rho_max_m"] <= 15.0),
        },
        "observability": {
            "std_phi_world_ray_deg": float(np.degrees(std_phi)),
            "delta_phi_min_deg": float(np.degrees(dphi_min)),
            "is_well_constrained": bool(std_phi >= dphi_min),
            "sigma_Pz_m": float(sigma_Pz),
            "tau_z_m": 0.05,
            "tau_z_crit_m": float(F.tau_z_crit(ARIS["sigma_rho_m"], n_obs,
                                               np.deg2rad(ARIS["phi_max_deg"]))),
        },
        "stats": {
            "n_target_px": int(tm.sum()),
            "n_shadow_px": int(sm.sum()),
            "n_unlit_px": int(um.sum()),
            "n_floor_px": int(fm.sum()),
            "n_measurements": int(recs_arr.shape[0]),
            "target_px_per_frame": float(tm.sum() / N_FRAMES),
        },
        "envelope_per_frame": {
            "n_frames": int(len(poses6)),
            "n_pairs_evaluated": int(frame_pred.size),
            "n_pred_feasible": int(frame_pred.sum()),
            "n_actually_measured": int(frame_act.sum()),
            "TP": tp_, "FP": fp_, "FN": fn_, "TN": tn_,
            "agreement": float((tp_ + tn_) / max(frame_pred.size, 1)),
            "note": ("逐 (帧,列) 包线判据 vs 实际是否量到远端。粒度必须到列："
                     "各列轮廓远边缘 d_far 随方位偏移不同，按帧聚合会产生虚假 FN/FP。"),
        },
        "inversion": {
            "expected_invertible": expected,
            "n_valid": int(err.size),
            "h_true_m": h,
            "mae_cm": float(np.mean(np.abs(err)) * 100) if err.size else None,
            "bias_cm": float(np.mean(err) * 100) if err.size else None,
            "std_cm": float(np.std(err, ddof=1) * 100) if err.size > 1 else None,
            "sigma_h_pred_cm": float(np.median(s_h_all) * 100) if s_h_all.size else None,
            "leak_free": True,
            "leak_note": (
                "L_s 由 obs/shadow_masks 量测远端跳变得到；D_t 与 z_s 由 ★I(BA) "
                "提供并注入定位噪声。反演路径不读任何解析几何量 ⇒ 非恒等式（C7）。"),
        },
        "timing_s": round(time.time() - t0, 1),
    }
    with open(d / "meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    if verbose:
        o = meta["observability"]
        st = meta["stats"]
        iv = meta["inversion"]
        print(f"  std(φ_world)={o['std_phi_world_ray_deg']:.3f}° "
              f"Δφ_min={o['delta_phi_min_deg']:.3f}° ⇒ "
              f"{'良约束' if o['is_well_constrained'] else '盲'}"
              f"  σ_Pz={o['sigma_Pz_m']*100:.2f} cm")
        print(f"  像素: target={st['n_target_px']} ({st['target_px_per_frame']:.1f}/帧) "
              f"shadow={st['n_shadow_px']} unlit={st['n_unlit_px']} floor={st['n_floor_px']}")
        ef = meta["envelope_per_frame"]
        print(f"  逐(帧,列)包线: 预测可行 {ef['n_pred_feasible']}/{ef['n_pairs_evaluated']}  "
              f"实测到 {ef['n_actually_measured']}/{ef['n_pairs_evaluated']}  "
              f"TP={ef['TP']} FP={ef['FP']} FN={ef['FN']} TN={ef['TN']}  "
              f"一致率={ef['agreement']*100:.1f}%")
        print(f"  量测 {iv['n_valid']} 条  "
              f"MAE={iv['mae_cm'] if iv['mae_cm'] is None else round(iv['mae_cm'],3)} cm  "
              f"bias={iv['bias_cm'] if iv['bias_cm'] is None else round(iv['bias_cm'],3)} cm  "
              f"σ_h预测={iv['sigma_h_pred_cm'] if iv['sigma_h_pred_cm'] is None else round(iv['sigma_h_pred_cm'],3)} cm")
        print(f"  耗时 {meta['timing_s']}s")
    return meta


def main():
    print("=" * 78)
    print("F-8d 主档场景生成（ARIS 探测模式：ρ_max=15m / 1600bin / ±7.5° / 下俯19°）")
    print("=" * 78)
    print(f"  Δρ_bin = {DBIN*1000:.2f} mm  "
          f"{'✅在 ARIS 规格 3-19mm 内' if 0.003<=DBIN<=0.019 else '❌超规格'}")
    print(f"  输出 → {OUT_ROOT}")
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    metas = []
    for args in SCENES:
        try:
            metas.append(gen_one(*args))
        except Exception as e:
            print(f"  [ERR] {args[0]}: {e}")
            import traceback
            traceback.print_exc()
    with open(OUT_ROOT / "INDEX.json", "w", encoding="utf-8") as f:
        json.dump([{k: m[k] for k in ("name", "role", "observability",
                                      "stats", "inversion")} for m in metas],
                  f, ensure_ascii=False, indent=2)
    print(f"\n完成 {len(metas)}/{len(SCENES)} 个场景")


if __name__ == "__main__":
    main()




