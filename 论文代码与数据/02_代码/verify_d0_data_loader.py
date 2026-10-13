# -*- coding: utf-8 -*-
"""D0: 真实数据加载器核查"""
import sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, r'F:\sfm\sfm_synthetic_pillars\real_data')
from loader import load_watertank_segmentation, load_quarry_fullsize, load_turntable_cropped
import numpy as np

print("=" * 60)
print("D0: 真实数据加载器核查")
print("=" * 60)

# 1) watertank-segmentation
print("\n--- watertank-segmentation ---")
w = load_watertank_segmentation(val_frac=0.2, seed=42)
n_train = len(w['train']['images'])
n_val = len(w['val']['images'])
print(f"  train={n_train}, val={n_val}, total={n_train+n_val}")
img0 = w['train']['images'][0]
print(f"  图像路径={os.path.basename(img0)}")
# 实际加载第一张图检查
from PIL import Image
img = np.array(Image.open(img0))
print(f"  图像尺寸={img.shape}, dtype={img.dtype}, range=[{img.min()},{img.max()}]")
if 'masks' in w['train'] and w['train']['masks']:
    mask0 = w['train']['masks'][0]
    mask = np.array(Image.open(mask0))
    classes = np.unique(mask)
    print(f"  掩码尺寸={mask.shape}, 类别={classes}")

# 2) quarry-fullsize
print("\n--- quarry-fullsize ---")
q = load_quarry_fullsize()
print(f"  {len(q)}段")
for k in list(q.keys())[:3]:
    print(f"  {k}: {len(q[k]['frames'])}帧")

# 3) turntable-cropped
print("\n--- turntable-cropped ---")
t = load_turntable_cropped(crop='object')
print(f"  {len(t)}类")
for k in list(t.keys())[:5]:
    print(f"  {k}: {len(t[k]['frames'])}帧")

print("\n✅ D0 数据加载器全部通过")
