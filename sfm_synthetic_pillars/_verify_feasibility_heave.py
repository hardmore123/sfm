"""验证 feasibility 判据对 AUV heave 起伏的支持（S6 案例）。"""
import sys
import os
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from feasibility import check_feasibility, check_feasibility_with_heave

print("=== S6 案例：feasibility 判据对 AUV heave 起伏的支持 ===\n")

# S6 配置
z_s_center = 4.5     # AUV 平均高度
heave_amp = 1.2      # heave 振幅（AUV 实际 z ∈ [3.3, 5.7]）
h = 5.5              # 目标高度（h > z_s_center 但 < z_s_max）
rho_max = 25.0
fov_elev = 17.0      # ±17° 孔径
d = 10.0

print(f"S6 几何: z_s={z_s_center}m, heave={heave_amp}m, h={h}m, d={d}m")
print(f"  AUV 实际 z 范围: [{z_s_center - heave_amp}, {z_s_center + heave_amp}] m")
print(f"  h 相对 z_s_min={z_s_center - heave_amp}: {'h>z_s_min（严格 C-IV 越界）' if h > z_s_center - heave_amp else 'h<z_s_min'}")
print(f"  h 相对 z_s_max={z_s_center + heave_amp}: {'h>z_s_max（更不可能）' if h > z_s_center + heave_amp else 'h<z_s_max'}")
print()

# 旧版判定（用 z_s_center）
r_old = check_feasibility(z_s_center, rho_max, 0, -fov_elev, fov_elev, d, h)
print(f"【旧版】用 z_s={z_s_center}: is_feasible={r_old.is_feasible}, binding={r_old.binding_constraint}")
print(f"  elev_top={r_old.elev_top:.3f} rad = {180*r_old.elev_top/np.pi:.2f}°")
print(f"  h>=z_s_center? {h >= z_s_center} -> 旧版正确判不可反演")
print()

import numpy as np
# 新版（用 z_s_min 严格场景）
r_strict = check_feasibility(z_s_center, rho_max, 0, -fov_elev, fov_elev, d, h,
                              z_s_min=z_s_center - heave_amp, z_s_max=z_s_center + heave_amp)
print(f"【新版严格】用 z_s_min={z_s_center - heave_amp}: is_feasible={r_strict.is_feasible}, binding={r_strict.binding_constraint}")
print(f"  elev_top={r_strict.elev_top:.3f} rad = {180*r_strict.elev_top/np.pi:.2f}°")
print(f"  h>=z_s_min? {h >= z_s_center - heave_amp} -> 新版严格正确判不可反演")
print()

# 概率场景
r_prob = check_feasibility_with_heave(
    z_s_center, heave_amp, rho_max, 0, -fov_elev, fov_elev, d, h
)
print(f"【概率场景】fraction_feasible={r_prob['fraction_feasible']*100:.1f}%")
print(f"  strict_feasible: {r_prob['strict_feasible']}")
print(f"  loose_feasible (>50%): {r_prob['loose_feasible']}")
print(f"  binding: {r_prob['binding']}")
print()

# 对比 S1（包线内）
print("=" * 60)
print("对比：S1（h=2.5, 包线内）")
z_s_center_s1 = 4.5
h_s1 = 2.5
r_s1 = check_feasibility_with_heave(
    z_s_center_s1, heave_amp, rho_max, 0, -fov_elev, fov_elev, d, h_s1
)
print(f"  fraction_feasible={r_s1['fraction_feasible']*100:.1f}%")
print(f"  strict_feasible: {r_s1['strict_feasible']}")
print(f"  binding: {r_s1['binding']}")
