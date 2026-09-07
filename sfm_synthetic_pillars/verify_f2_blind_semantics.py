"""
F-2 验收：盲区判据的语义正确性
================================

关键单元测试（区分 std 版与已作废的 sin 版）：
  **同一个仰角位置 φ、两条不同轨迹，必须给出不同的盲判。**
  旧版 f = Δφ_min/φ_max 只看 φ_max，无法区分轨迹 ⇒ 必然给出相同结果。
  新版看每地标实际的 std(φ_k) ⇒ 能区分。

同时验收：
  - tau_z_crit 复现 ARIS 主档 4.2 cm（N=10）
  - blind_fraction_curve 已作废并抛 NotImplementedError
"""
import io
import sys
import numpy as np
import feasibility as F

# 保证重定向到文件时也用 UTF-8（Windows 默认 GBK 会编不了 ⇒ 等符号）
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def phi_series(z_traj, d=10.0, z_target=1.25):
    """给定声呐 z 序列，算目标点的世界俯角序列。"""
    return np.arctan2(np.asarray(z_traj) - z_target, d)


print("=" * 78)
print("T1  τ_z^crit 复现（ARIS 主档 φ_max=7.5°, σ_ρ=10mm, N=10 ⇒ 期望 4.2 cm）")
print("=" * 78)
p = F.aris_main_profile(N=10)
print(f"  φ_max              = {p['phi_max_deg']:.1f}°")
print(f"  std(φ) 可达上界     = {p['max_achievable_std_phi_deg']:.2f}°  (= φ_max/√3)")
print(f"  τ_z^crit           = {p['tau_z_crit_cm']:.2f} cm")
ok1 = abs(p["tau_z_crit_cm"] - 4.2) < 0.2
print(f"  判定: {'通过' if ok1 else '未通过'}（期望 4.2 ± 0.2 cm）")

print()
print("=" * 78)
print("T2  关键语义测试：同一 φ 位置 + 两条不同轨迹 ⇒ 必须给出不同盲判")
print("=" * 78)
# 两条轨迹：声呐平均高度相同（故 φ 均值相同），但起伏幅度需跨越 Δφ_min
# Δφ_min=3.62° 对应 d=10m 处的等效起伏 ≈ 10·tan(3.62°)·√2 ≈ 0.90 m（正弦 std=A/√2）
z_flat = 4.5 + 0.10 * np.sin(np.linspace(0, 2 * np.pi, 10))   # std(φ) ≈ 0.35° 远低于门限
z_wavy = 4.5 + 1.40 * np.sin(np.linspace(0, 2 * np.pi, 10))   # std(φ) ≈ 4.8° 高于门限

phi_flat = phi_series(z_flat)
phi_wavy = phi_series(z_wavy)
print(f"  轨迹A(平): φ 均值 {np.degrees(phi_flat.mean()):.3f}°  std {np.degrees(phi_flat.std()):.4f}°")
print(f"  轨迹B(起伏): φ 均值 {np.degrees(phi_wavy.mean()):.3f}°  std {np.degrees(phi_wavy.std()):.4f}°")
print(f"  → φ 均值几乎相同（差 {abs(np.degrees(phi_flat.mean()-phi_wavy.mean())):.3f}°），"
      f"std 差 {np.degrees(phi_wavy.std())/max(np.degrees(phi_flat.std()),1e-9):.0f} 倍")

sr, N, tz = 0.010, 10, 0.05
dmin = F.min_elev_spread(sr, N, tz)
print(f"\n  Δφ_min(σ_ρ=10mm, N=10, τ_z=5cm) = {np.degrees(dmin):.3f}°")
for nm, ph in [("轨迹A(平)", phi_flat), ("轨迹B(起伏)", phi_wavy)]:
    r = F.blind_landmark_fraction([ph.std()], sr, N, tau_z_list=(0.05,))
    b = r["by_tau_z"][0.05]
    print(f"  {nm:<12} std(φ)={np.degrees(ph.std()):.4f}°  "
          f"盲判={'盲' if b['n_blind'] else '可观测'}")

ra = F.blind_landmark_fraction([phi_flat.std()], sr, N, tau_z_list=(0.05,))
rb = F.blind_landmark_fraction([phi_wavy.std()], sr, N, tau_z_list=(0.05,))
differ = ra["by_tau_z"][0.05]["n_blind"] != rb["by_tau_z"][0.05]["n_blind"]
print(f"\n  判定: {'通过' if differ else '未通过'}"
      f"（两条轨迹须给出不同盲判；旧 sin 版只看 φ_max，必然相同）")

print()
print("=" * 78)
print("T3  已作废接口须显式报错")
print("=" * 78)
try:
    F.blind_fraction_curve(0.01, 10, np.deg2rad(7.5))
    ok3 = False
    print("  未通过：blind_fraction_curve 仍可调用")
except NotImplementedError as e:
    ok3 = True
    print("  通过：blind_fraction_curve 抛 NotImplementedError")
    print(f"    提示信息首行: {str(e).splitlines()[0]}")

print()
print("=" * 78)
print("T4  多地标经验盲比例（示例：20 个地标，std(φ) 从 0.01° 到 5°）")
print("=" * 78)
stds = np.deg2rad(np.linspace(0.01, 5.0, 20))
r = F.blind_landmark_fraction(stds, sr, N, tau_z_list=(0.02, 0.05, 0.10))
print(f"  地标数 {r['n_landmarks']}, std(φ) 中位 {r['std_phi_deg_median']:.2f}°, "
      f"最大 {r['std_phi_deg_max']:.2f}°")
for tz, v in r["by_tau_z"].items():
    print(f"    τ_z={tz*100:>5.1f}cm  Δφ_min={v['delta_phi_min_deg_median']:>6.3f}°  "
          f"盲地标 {v['n_blind']:>2}/{v['n_total']}  ({v['fraction_blind_pct']:>5.1f}%)")
print(f"  注: {r['note']}")

print()
print("=" * 78)
print(f"F-2 总判定: {'全部通过' if (ok1 and differ and ok3) else '存在未通过项'}")
print("=" * 78)
