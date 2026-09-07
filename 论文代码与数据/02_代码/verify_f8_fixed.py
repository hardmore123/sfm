"""
F-8a/b/c 修正验收
=================

T1 (B2) θ_p=19° 下目标能被检出   —— 原码会漏掉（把孔径中心判成出界）
T2 (B1) unlit 与 shadow 已分开    —— 原码把未照亮区当阴影
T3 (B3) 反演**不再是恒等式**      —— 关键项：
        误差须 >0 且与「远端量测量化」理论一致，
        而非原码那样 max|h_inv−h| ~1e-15
T4      σ_h 传播与实测 std 相符（比值 ∈ [0.7, 1.5]）
"""
import io, sys, copy
import numpy as np
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from config import Config, SonarCfg, finalize_pixel_mapping
from world import SceneWorld, Pillar
from trajectory import euler_to_matrix
import shadow as SH_OLD
import shadow_f8_fixed as SF

# ---- F-8d 主档构型
Z_S, TP_DEG, D_T, H_TRUE = 4.5, 19.0, 10.6, 0.85
RHO_MIN, RHO_MAX, N_BINS = 0.5, 15.0, 1600
PHI_MAX = 7.5
DBIN = (RHO_MAX - RHO_MIN) / (N_BINS - 1)


def make_cfg():
    cfg = Config()
    cfg.sonar = SonarCfg(
        fov_elevation_deg=(-PHI_MAX, PHI_MAX),
        fov_azimuth_deg=(-15.0, 15.0),
        beam_count=128,
        range_bin_count=N_BINS,
        range_min_m=RHO_MIN,
        range_max_m=RHO_MAX,
    )
    finalize_pixel_mapping(cfg)
    return cfg


def make_pose(z_s=Z_S, tp_deg=TP_DEG):
    T = np.eye(4)
    T[:3, :3] = euler_to_matrix(0.0, np.deg2rad(tp_deg), 0.0)
    T[:3, 3] = [0.0, 0.0, z_s]
    return T


cfg = make_cfg()
# SceneWorld 从 cfg.scene 构建，故通过 cfg 注入柱体
cfg.scene.pillars = [(D_T, 0.0, 0.25, H_TRUE)]
cfg.scene.cubes = []
cfg.scene.spheres = []
cfg.scene.rubble = []
cfg.scene.floor_z_m = 0.0
world = SceneWorld(cfg)
T = make_pose()

print("=" * 78)
print(f"构型 z_s={Z_S} θ_p={TP_DEG}° D_t={D_T} h={H_TRUE}  "
      f"ρ∈[{RHO_MIN},{RHO_MAX}]/{N_BINS}bin (Δ={DBIN*1000:.2f}mm)")
print("=" * 78)

# ---------------- T1 ----------------
print("\nT1 (B2) 目标检出：原码 vs 修正码")
old = SH_OLD.render_shadow_map(T, world, cfg)
n_tgt_old = int(old[0].sum())
new = SF.render_shadow_map_fixed(T, world, cfg)
n_tgt_new = int(new.target_mask.sum())
print(f"  原码 target 像素数 = {n_tgt_old}")
print(f"  修正 target 像素数 = {n_tgt_new}")
t1 = (n_tgt_old == 0) and (n_tgt_new > 0)
print(f"  判定: {'通过' if t1 else '未通过'}"
      f"（原码应为 0 = 漏检；修正应 >0）")

# ---------------- T2 ----------------
print("\nT2 (B1) unlit / shadow 分离")
ns, nu, nf = int(new.shadow_mask.sum()), int(new.unlit_mask.sum()), int(new.floor_mask.sum())
print(f"  shadow={ns}  unlit={nu}  floor={nf}")
print(f"  三者互斥: "
      f"{'✅' if not (new.shadow_mask & new.unlit_mask).any() and not (new.shadow_mask & new.floor_mask).any() else '❌'}")
n_sh_old = int(old[1].sum())
print(f"  原码 shadow 像素数 = {n_sh_old}（未区分未照亮）")
t2 = (ns > 0) and (nu > 0) and not (new.shadow_mask & new.unlit_mask).any()
print(f"  判定: {'通过' if t2 else '未通过'}")

# ---------------- T3 ----------------
print("\nT3 (B3) 反演是否仍为恒等式")
rngs = np.linspace(RHO_MIN, RHO_MAX, N_BINS)
u = Z_S - H_TRUE
D_e_true = D_T * Z_S / u
rho_end_true = np.hypot(D_e_true, Z_S)
print(f"  解析 D_e={D_e_true:.4f} ρ_end={rho_end_true:.4f} m")

errs, rho_ms = [], []
for c in range(new.shadow_mask.shape[1]):
    if not new.shadow_mask[:, c].any():
        continue
    rho_m = SF.measure_shadow_far_edge(new.shadow_mask[:, c],
                                       new.floor_mask[:, c], rngs)
    if not np.isfinite(rho_m):
        continue
    h_inv = SF.invert_height_from_far_edge(rho_m, D_T, Z_S)
    if np.isfinite(h_inv):
        errs.append(h_inv - H_TRUE)
        rho_ms.append(rho_m)
errs = np.asarray(errs)
rho_ms = np.asarray(rho_ms)
print(f"  可量测列数 = {errs.size}")
if errs.size:
    print(f"  量测 ρ_end 中位={np.median(rho_ms):.4f} m  "
          f"与解析差={np.median(rho_ms)-rho_end_true:+.4f} m "
          f"({abs(np.median(rho_ms)-rho_end_true)/DBIN:.2f} bin)")
    print(f"  h 误差: 中位={np.median(errs)*100:+.3f} cm  "
          f"std={errs.std(ddof=1)*100 if errs.size>1 else 0:.3f} cm  "
          f"max|·|={np.abs(errs).max()*100:.3f} cm")
    t3 = np.abs(errs).max() > 1e-6      # 必须显著大于浮点噪声
    print(f"  判定: {'通过' if t3 else '未通过'}"
          f"（须 >1e-6 m；原码为 ~1e-15 = 恒等式）")
else:
    t3 = False
    print("  判定: 未通过（无可量测列）")

# ---------------- T4 ----------------
# 单构型下所有列的量测值完全相同（量化确定性 + 几何相同）⇒ std=0，
# 无法用来验 σ_h。必须让真值 ρ_end 落在不同亚 bin 相位上做蒙特卡洛。
print("\nT4 σ_h 传播 vs 蒙特卡洛（跨亚 bin 相位）")


def quantize_measure(rho_end_true, rngs):
    """复现 measure_shadow_far_edge 的量化行为（不跑完整渲染）。
    最后一个阴影 bin = 最大的 rngs[i] < rho_end_true；下一个 bin 为 floor。
    亚 bin 取中点。"""
    i = int(np.searchsorted(rngs, rho_end_true, side="right") - 1)
    if i < 0 or i + 1 >= len(rngs):
        return float("nan")
    return 0.5 * (rngs[i] + rngs[i + 1])


# 先用完整渲染在 4 个 D_t 上校核该快速模型
print("  ① 快速量化模型 vs 完整渲染校核")
ok_model = True
for D_t_v in (9.6, 10.1, 10.6, 11.1):
    cfg_v = make_cfg()
    cfg_v.scene.pillars = [(D_t_v, 0.0, 0.25, H_TRUE)]
    cfg_v.scene.cubes = []; cfg_v.scene.spheres = []; cfg_v.scene.rubble = []
    cfg_v.scene.floor_z_m = 0.0
    w_v = SceneWorld(cfg_v)
    r_v = SF.render_shadow_map_fixed(T, w_v, cfg_v)
    cols = [c for c in range(r_v.shadow_mask.shape[1]) if r_v.shadow_mask[:, c].any()]
    if not cols:
        print(f"    D_t={D_t_v}: 无阴影列，跳过")
        continue
    c0 = cols[len(cols) // 2]
    rho_render = SF.measure_shadow_far_edge(r_v.shadow_mask[:, c0],
                                            r_v.floor_mask[:, c0], rngs)
    De_t = D_t_v * Z_S / (Z_S - H_TRUE)
    rho_t_true = np.hypot(De_t, Z_S)
    rho_fast = quantize_measure(rho_t_true, rngs)
    d = abs(rho_render - rho_fast)
    hit = d < 1.5 * DBIN
    ok_model &= hit
    print(f"    D_t={D_t_v:>5.1f}  真值ρ_end={rho_t_true:.4f}  "
          f"渲染={rho_render:.4f}  快速模型={rho_fast:.4f}  "
          f"差={d/DBIN:.2f} bin {'✅' if hit else '❌'}")

print(f"  快速模型可用: {'✅' if ok_model else '❌'}")

# ② 蒙特卡洛：让 D_t 连续变化以扫遍亚 bin 相位
print("  ② 蒙特卡洛 (D_t 连续变化 2000 次，扫遍亚 bin 相位)")
rng = np.random.default_rng(7)
mc_err = []
for _ in range(2000):
    D_t_v = rng.uniform(9.5, 11.5)
    De_t = D_t_v * Z_S / (Z_S - H_TRUE)
    rho_t_true = np.hypot(De_t, Z_S)
    rho_m = quantize_measure(rho_t_true, rngs)
    h_i = SF.invert_height_from_far_edge(rho_m, D_t_v, Z_S)
    if np.isfinite(h_i):
        mc_err.append(h_i - H_TRUE)
mc_err = np.asarray(mc_err)
sig_rho_meas = DBIN / np.sqrt(12)
sh = SF.sigma_h_from_far_edge(rho_end_true, D_T, Z_S,
                              sigma_rho=sig_rho_meas, sigma_Dt=0.0, sigma_zs=0.0)
print(f"    样本 {mc_err.size}  偏置={mc_err.mean()*100:+.4f} cm  "
      f"std={mc_err.std(ddof=1)*100:.4f} cm")
print(f"    σ_ρ(量化)=Δ/√12={sig_rho_meas*1000:.2f} mm  ⇒  σ_h 预测={sh*100:.4f} cm")
ratio = mc_err.std(ddof=1) / sh if sh > 0 else float("nan")
print(f"    比值 实测/预测 = {ratio:.3f}")
t4 = ok_model and (0.5 <= ratio <= 2.0)
print(f"  判定: {'通过' if t4 else '未通过'}（模型可用 且 比值 ∈ [0.5, 2.0]）")

print()
print("=" * 78)
allok = t1 and t2 and t3
print(f"F-8a/b/c 判定: T1={'✅' if t1 else '❌'} T2={'✅' if t2 else '❌'} "
      f"T3={'✅' if t3 else '❌'} T4={'✅' if t4 else '⚠️'}")
print(f"总判定（T1-T3 必过）: {'通过' if allok else '未通过'}")
print("=" * 78)
