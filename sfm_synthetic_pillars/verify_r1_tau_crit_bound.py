"""核查 ★I-1 核心断言：τ_z^crit 是否真的"任何运动方式都无法突破"。

现行文档的推导：
    φ_k ∈ [-φ_max, φ_max]  ⇒  std(φ) ≤ φ_max/√3   （均匀分布的标准差）
    ⇒  τ_z^crit = √3·σ_ρ/(√N·φ_max) = 4.18 cm （ARIS, N=10）

疑点：对**有界**随机变量，最大方差的分布不是均匀分布，而是**两端点各半**
     的二点分布（Bhatia–Davis / Popoviciu 不等式）：
         Var ≤ (b−a)²/4  ⇒  std ≤ φ_max   （区间 [-φ_max, φ_max]）
     若如此，真正的硬界是 σ_ρ/(√N·φ_max) = 2.42 cm，
     而 √3 版的 4.18 cm 只是"均匀扫过孔径"这一**特定**运动的结果。

本脚本用数值枚举 + 显式构造轨迹来判定。
"""
import io
import sys
import numpy as np
from itertools import product

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

PHI_MAX = np.deg2rad(7.5)
SIGMA_RHO = 0.010
N = 10


import feasibility as F


def tau_crit(std_max):
    return SIGMA_RHO / (np.sqrt(N) * std_max)


print("=" * 80)
print("① 有界区间上 std 的理论上界")
print("=" * 80)
print(f"  φ ∈ [-{np.degrees(PHI_MAX):.1f}°, +{np.degrees(PHI_MAX):.1f}°]")
print(f"  均匀分布      std = φ_max/√3 = {np.degrees(PHI_MAX/np.sqrt(3)):.4f}°")
print(f"  两端点各半     std = φ_max     = {np.degrees(PHI_MAX):.4f}°")
print(f"  Popoviciu 上界 std ≤ (b−a)/2   = {np.degrees(PHI_MAX):.4f}°")
print(f"  ⇒ 两端点分布**达到**上界，均匀分布只有它的 1/√3 = 0.577 倍")

print()
print("=" * 80)
print("② 数值枚举：N=10 个观测放在孔径内何处使 std 最大")
print("=" * 80)
best = None
# 枚举：k 个点放 -φ_max，N-k 个放 +φ_max
print(f"  {'−φ_max 处点数':>14} {'+φ_max 处点数':>14} {'std(φ)°':>10} {'τ_z^crit(cm)':>13}")
for k in range(0, N + 1):
    phi = np.array([-PHI_MAX] * k + [PHI_MAX] * (N - k))
    s = phi.std()
    if best is None or s > best[0]:
        best = (s, k)
    if k in (0, 2, 5, 8, 10):
        print(f"  {k:>14} {N-k:>14} {np.degrees(s):>10.4f} {tau_crit(s)*100:>13.3f}")
print(f"  ⇒ 最大 std 在 k={best[1]}（两端各半）：{np.degrees(best[0]):.4f}° = φ_max")

# 随机搜索确认没有更好的配置
rng = np.random.default_rng(0)
smax = 0.0
for _ in range(200000):
    phi = rng.uniform(-PHI_MAX, PHI_MAX, N)
    smax = max(smax, phi.std())
print(f"  20 万次随机采样的最大 std = {np.degrees(smax):.4f}° "
      f"(≤ φ_max = {np.degrees(PHI_MAX):.4f}° ✓)")

print()
print("=" * 80)
print("③ 两个 τ_z^crit 的差异")
print("=" * 80)
t_unif = tau_crit(PHI_MAX / np.sqrt(3))
t_abs = tau_crit(PHI_MAX)
print(f"  均匀扫过孔径（现行文档）  τ_z^crit = √3σ_ρ/(√N φ_max) = {t_unif*100:.2f} cm")
print(f"  两端点各半（真正的硬界）  τ_z^crit =   σ_ρ/(√N φ_max) = {t_abs*100:.2f} cm")
print(f"  比值 = √3 = {t_unif/t_abs:.4f}")
print()
print(f"  ⇒ 现行文档说\"{t_unif*100:.2f} cm 任何运动方式都无法突破\"**不成立**：")
print(f"     只要让观测集中在孔径两端（bang-bang 式停留），就能达到 {t_abs*100:.2f} cm。")

print()
print("=" * 80)
print("④ bang-bang 轨迹在物理上可实现吗？")
print("=" * 80)
# 目标在 D_t 处、柱顶落差 u；声呐 z 在 [z0-A, z0+A] 摆动
# 世界系射线俯角 φ = -arctan(u/D_t)，u 随 z 变
D_t, u0, z0 = 10.6, 3.65, 4.5
print(f"  构型 D_t={D_t} m, 标称落差 u={u0} m")
print(f"  要让 φ 达到 ±φ_max={np.degrees(PHI_MAX):.1f}°，需 u = D_t·tan(φ) = "
      f"±{D_t*np.tan(PHI_MAX):.3f} m")
print(f"  即声呐 z 需在 {u0 - D_t*np.tan(PHI_MAX):+.2f} ~ {u0 + D_t*np.tan(PHI_MAX):+.2f} m "
      f"范围内摆动（相对柱顶）")
print(f"  对应起伏幅度 A ≈ {D_t*np.tan(PHI_MAX):.2f} m（单侧）")
print(f"  ⇒ 这正是 T6 的 A_opt ≈ D_t·tan(φ_max) = {D_t*np.tan(PHI_MAX):.2f} m ✅ 两者一致")

# 但要"停在两端"而非正弦扫过
print()
print("  正弦起伏 vs bang-bang 停留（同幅度 A）的 std 对比：")
A = D_t * np.tan(PHI_MAX)
for name, phi in [
    ("正弦（半周期，实际轨迹）",
     -np.arctan2(u0 - A * np.sin(np.linspace(0, np.pi, N)), D_t)),
    ("正弦（全周期）",
     -np.arctan2(u0 - A * np.sin(np.linspace(0, 2*np.pi, N, endpoint=False)), D_t)),
    ("两端各半（bang-bang）",
     -np.arctan2(np.array([u0 - A] * (N//2) + [u0 + A] * (N - N//2)), D_t)),
]:
    s = phi.std()
    print(f"    {name:<24} std={np.degrees(s):>7.4f}°  "
          f"σ_Pz={SIGMA_RHO/(np.sqrt(N)*s)*100:>6.2f} cm")

print()
print("=" * 80)
print("结论")
print("=" * 80)
print(f"""
现行文档 §1.2b 的 τ_z^crit = √3σ_ρ/(√N·φ_max) = {t_unif*100:.2f} cm
**不是**"任何运动方式都无法突破"的硬界，而是"目标均匀扫过整个孔径"
这一特定运动下的值。

真正的硬界（Popoviciu 不等式，std ≤ (b−a)/2）是
    τ_z^crit,abs = σ_ρ/(√N·φ_max) = {t_abs*100:.2f} cm
由观测集中在孔径两端的 bang-bang 轨迹达到，且该轨迹物理可实现
（所需起伏幅度恰为 T6 的 A_opt = D_t·tan φ_max）。

⇒ 需要区分两个量，并修正 ★I-1 的表述：
   τ_z^crit,abs  = σ_ρ/(√N·φ_max)      硬界，任何运动都无法突破
   τ_z^crit,unif = √3σ_ρ/(√N·φ_max)    均匀扫过孔径的可达值（工程参考）

⚠️ 注意 τ_z^crit,abs = {t_abs*100:.2f} cm 与**已作废的 sin 版**数值几乎相同
   （因 sin(7.5°)=0.1305 ≈ 0.1309 rad）。但二者推导完全不同：
   sin 版错在把 1/Λ_zz 当后验方差；本式是对 std 上界用 Popoviciu 不等式。
   **数值巧合，不可混为一谈。**
""")


print()
print("=" * 80)
print("⑤ 与 feasibility.tau_z_crit 的双界实现对表（R1 验收）")
print("=" * 80)
ok = True
for n in (10, 30, 60, 100):
    a = F.tau_z_crit(SIGMA_RHO, n, PHI_MAX, mode="abs")
    u = F.tau_z_crit(SIGMA_RHO, n, PHI_MAX, mode="uniform")
    ea = SIGMA_RHO / (np.sqrt(n) * PHI_MAX)
    eu = np.sqrt(3) * SIGMA_RHO / (np.sqrt(n) * PHI_MAX)
    hit = abs(a - ea) < 1e-15 and abs(u - eu) < 1e-15 and abs(u / a - np.sqrt(3)) < 1e-12
    ok &= hit
    print(f"  N={n:>3}  abs={a*100:>5.2f}cm  unif={u*100:>5.2f}cm  "
          f"比值={u/a:.4f}  {chr(10004) if hit else chr(10007)}")
mark = chr(10004) if ok else chr(10007)
verdict = "通过" if ok else "未通过"
print("\nR1 判定: " + mark + " " + verdict + "（双界公式与 √3 关系均正确）")
