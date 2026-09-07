import sys, os
sys.path.insert(0, r'F:\sfm\sfm_synthetic_pillars')
import numpy as np
from _R_x6_aykin_carve_v2 import evaluate_aykin_v2

print("smoke S1...")
r = evaluate_aykin_v2("S1_single_well_constrained", voxel_size=0.1, n_poses=12, form_mode="auto")
print()
print("results:", r)
