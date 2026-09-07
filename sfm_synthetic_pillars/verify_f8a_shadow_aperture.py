"""F-8a 验收：shadow.py 的孔径处理三处缺陷

B1（Q2）阴影足迹不按孔径裁剪 —— 填充循环 `for r in range(ri+1, r_end+1)`
        对每个距离门无条件置 True，未检查该距离门上海底是否真被照亮。
B2（新）仰角孔径检查用**世界系**角度对比**体系**边界，缺 pitch 变换。
        正确：elev_body = arctan2(P_b[2], hypot(P_b[0],P_b[1]))，P_b = R_wb^T (P_w − t_wb)
B3（Q1）shadow_len / D_t_map 逐像素写入解析真值 ⇒ 反演成恒等式。

本脚本先量化 B1/B2 的偏差，再验证修正函数。
"""
import io, sys
import numpy as np
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from trajectory import euler_to_matrix

PHI_MAX = np.deg2rad(7.5)


def elev_world_of(P_w, t_wb):
    """shadow.py 现在的做法：纯几何世界系俯角。"""
    d = np.hypot(P_w[0] - t_wb[0], P_w[1] - t_wb[1])
    return np.arctan2(P_w[2] - t_wb[2], d)


def elev_body_of(P_w, T_wb):
    """正确做法：体系俯角。"""
    R = T_wb[:3, :3]
    t = T_wb[:3, 3]
    P_b = R.T @ (np.asarray(P_w, float) - t)
    return np.arctan2(P_b[2], np.hypot(P_b[0], P_b[1]))


print("=" * 78)
print("B2  仰角孔径检查缺 pitch 变换：偏差量化")
print("=" * 78)
print(f"  {'下俯°':>6} {'世界系俯角°':>12} {'体系俯角°':>11} {'偏差°':>8} "
      f"{'现码判定':>9} {'正确判定':>9} {'一致':>5}")
n_bad = 0
for tp_deg in (0, 5, 10, 15, 19, 25):
    T = np.eye(4)
    T[:3, :3] = euler_to_matrix(0.0, np.deg2rad(tp_deg), 0.0)
    T[:3, 3] = [0.0, 0.0, 4.5]
    # 柱顶：水平距 10.6、高 0.85
    P_w = np.array([10.6, 0.0, 0.85])
    ew = elev_world_of(P_w, T[:3, 3])
    eb = elev_body_of(P_w, T)
    cur = (-PHI_MAX <= ew <= PHI_MAX)          # shadow.py 现在的判定
    cor = (-PHI_MAX <= eb <= PHI_MAX)          # 正确判定
    same = cur == cor
    n_bad += (not same)
    print(f"  {tp_deg:>6} {np.degrees(ew):>12.3f} {np.degrees(eb):>11.3f} "
          f"{np.degrees(eb-ew):>8.3f} {str(cur):>9} {str(cor):>9} "
          f"{'✅' if same else '❌'}")
print(f"\n  ⇒ {n_bad}/6 个下俯角上现码判定与正确判定**不一致**")
print("     pitch=0 时二者相同（这解释了为何 bug 一直没暴露：主档场景 pitch 恰为 0）")
print("     但 F-8d 设计要求 θ_p=19°，此时现码会把孔径中心的目标判成出界")

print()
print("=" * 78)
print("B1  阴影足迹未按孔径裁剪：以 F-8d 设计构型量化")
print("=" * 78)
z_s, tp, D_t, h = 4.5, np.deg2rad(19.0), 10.6, 0.85
u = z_s - h
D_e = D_t * z_s / u
rho_t = np.hypot(D_t, u)
rho_e = np.hypot(D_e, z_s)
# 照明带（体系孔径 ±φ_max 绕下俯方向）
a_lo, a_hi = tp + PHI_MAX, tp - PHI_MAX
il_near = z_s / np.sin(a_lo)
il_far = z_s / np.sin(a_hi)
print(f"  构型 z_s={z_s} θ_p=19° D_t={D_t} h={h}")
print(f"  阴影距离跨度      [{rho_t:.2f}, {rho_e:.2f}] m")
print(f"  照明带（海底可见） [{il_near:.2f}, {il_far:.2f}] m")
ov_lo, ov_hi = max(rho_t, il_near), min(rho_e, il_far)
print(f"  真正可观测的阴影   [{ov_lo:.2f}, {ov_hi:.2f}] m  "
      f"占阴影 {(ov_hi-ov_lo)/(rho_e-rho_t)*100:.1f}%")

print(f"\n  对照 pitch=0 的旧构型 (z_s=4.5, D_t=16, h=2.5, ρ_max=40)：")
z2, D2, h2 = 4.5, 16.0, 2.5
u2 = z2 - h2
De2 = D2 * z2 / u2
rt2, re2 = np.hypot(D2, u2), np.hypot(De2, z2)
il2_near = z2 / np.sin(0 + PHI_MAX)
print(f"    阴影跨度 [{rt2:.2f}, {re2:.2f}]  照明带近界 {il2_near:.2f}")
ov2_lo, ov2_hi = max(rt2, il2_near), re2
frac2 = max(0.0, (ov2_hi - ov2_lo)) / (re2 - rt2)
print(f"    真正可观测 [{ov2_lo:.2f}, {ov2_hi:.2f}]  占 {frac2*100:.1f}%")
print(f"    ⇒ 旧构型下 {100-frac2*100:.1f}% 的\"阴影\"像素实为未照亮区（B1 的实际危害）")

print()
print("=" * 78)
print("B3  反演恒等式（复核 Q1）")
print("=" * 78)
rng = np.random.default_rng(1)
err = 0.0
for _ in range(20000):
    zz = rng.uniform(1.0, 8.0)
    hh = rng.uniform(0.05, zz * 0.95)
    dd = rng.uniform(1.0, 30.0)
    Ls = dd * hh / (zz - hh)          # shadow.py 写入的解析 L_s
    err = max(err, abs(zz * (1 - dd / (dd + Ls)) - hh))
print(f"  max|h_inv − h| = {err:.3e} m ⇒ "
      f"{'恒等式（真值泄漏）确认' if err < 1e-9 else '非恒等'}")

print()
print("=" * 78)
print("修正要求")
print("=" * 78)
print("""  F-8a: 阴影填充改为逐距离门检查「该门上海底是否在体系孔径内」，
        并把「未照亮」与「被遮挡」分成两个掩码输出。
  F-8b: shadow_len 不再写解析值；改由 shadow_mask 的 leading/trailing edge
        沿距离轴量测（含亚 bin 插值）。
  F-8c: D_t 不再由 z_top 反算；改由 ★I(BA) 的地标水平位置提供。""")
