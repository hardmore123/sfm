# -*- coding: utf-8 -*-
"""Inspect scene_set_main_f8 data structure for R-X5 adaptation"""
import numpy as np, json, sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

root = r"F:\sfm\论文代码与数据\04_数据\scene_set_main_f8"
for scene in ["M1_well_constrained", "M2_blind_low_spread"]:
    sd = os.path.join(root, scene)
    print(f"\n=== {scene} ===")
    with open(os.path.join(sd, "meta.json"), encoding="utf-8") as f:
        meta = json.load(f)
    print(f"  z_s={meta['config']['z_s_m']}, heave={meta['config']['heave_m']}, h={meta['config']['h_m']}")
    print(f"  n_frames={meta['config']['n_frames']}, range_bins={meta['config']['range_bin_count']}, beams={meta['config']['beam_count']}")
    
    # Check all npy files
    for subdir in ["gt", "obs", "innov2"]:
        d = os.path.join(sd, subdir)
        if not os.path.isdir(d): continue
        for fn in sorted(os.listdir(d)):
            if not fn.endswith(".npy"): continue
            fp = os.path.join(d, fn)
            arr = np.load(fp)
            print(f"  {subdir}/{fn}: shape={arr.shape}, dtype={arr.dtype}, range=[{arr.min():.4f},{arr.max():.4f}]")
