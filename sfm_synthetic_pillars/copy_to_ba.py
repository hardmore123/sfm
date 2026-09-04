"""Copy input dir to BA代码/sim_input_big."""
import os, shutil
src = "C:/Users/likunyuan/Desktop/private document/sfm/sfm_synthetic_pillars/big_paper_sim/mixed/input"
dst = "C:/Users/likunyuan/Desktop/private document/sfm/BA代码/sim_input_big"
if os.path.exists(dst):
    shutil.rmtree(dst)
shutil.copytree(src, dst)
print("copied to:", dst)
for f in os.listdir(dst):
    print(" ", f)
