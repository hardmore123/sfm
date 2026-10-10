"""rx3_ba_crlb 冒烟测试：先确认构型/可见性/CRLB/MC 各环节能跑通且数字合理。"""
import io
import os
import sys

sys.path.insert(0, r"F:\sfm\论文代码与数据\02_代码")
os.chdir(r"F:\sfm\论文代码与数据\02_代码")
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import numpy as np
import rx3_ba_crlb as X

for name, heave in [("M1_well_constrained", 1.2), ("M2_blind_low_spread", 0.1)]:
    poses6, P_top, idx, std_phi = X.build_scene(heave=heave)
    print(f"\n=== {name} (heave={heave}) ===")
    print(f"  总帧 {len(poses6)}  可见帧 {len(idx)}")
    print(f"  z 范围 [{poses6[:,2].min():.3f}, {poses6[:,2].max():.3f}]")
    print(f"  std(φ_world) = {np.degrees(std_phi):.4f}°")
    if len(idx) < 2:
        print("  ⚠️ 可见帧不足，跳过")
        continue
    cr = X.crlb_frozen_pose(P_top, poses6, idx)
    print(f"  CRLB σ_Pz = {cr['sigma_Pz']*100:.3f} cm   n_obs={cr['n_obs']}")
    print(f"  eigvals = {cr['eigvals']}")
    print(f"  近似式 σ_ρ/(√N·stdφ) = "
          f"{X.sigma_pz_std_phi_formula(std_phi, len(idx))*100:.3f} cm")
    mc = X.mc_frozen_pose(P_top, poses6, idx, n_trial=60)
    print(f"  MC(60): s_z = {mc.s_z*100:.3f} cm  bias={mc.bias_z*100:+.3f} cm  "
          f"fail={mc.n_fail}")
    if np.isfinite(mc.s_z) and cr["sigma_Pz"] > 0:
        print(f"  ⇒ ratio s_z/σ_Pz = {mc.s_z/cr['sigma_Pz']:.4f}  (判据 [0.8,1.3])")
