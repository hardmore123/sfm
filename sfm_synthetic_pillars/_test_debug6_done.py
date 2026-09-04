import numpy as np
from config import C, finalize_pixel_mapping
from world import SceneWorld
from gt_surface import sample_gt_surface

finalize_pixel_mapping(C)
world = SceneWorld(C)
points, normals = sample_gt_surface(world, n_per_object=300, rng=np.random.default_rng(42))

# idx=1525 的点
pt = points[1525]
print('idx 1525:', pt)
# 它属于哪根柱？
for i, p in enumerate(world.pillars):
    dxy = np.sqrt((pt[0] - p.cx)**2 + (pt[1] - p.cy)**2)
    print(f'  距柱 {i} ({p.cx}, {p.cy}): dxy = {dxy:.6f}, r = {p.radius}, diff = {dxy - p.radius:.6f}')

# 看 sample 出来的 1525 / 300 = 5.08 → 柱 5
# 柱 5 sample 范围
obj5 = world.pillars[5]
print()
print('柱 5 sample 范围: x in [%.4f, %.4f], y in [%.4f, %.4f]' % (
    obj5.cx - obj5.radius, obj5.cx + obj5.radius,
    obj5.cy - obj5.radius, obj5.cy + obj5.radius))
print('柱 5 实际 cx, cy, r:', obj5.cx, obj5.cy, obj5.radius)

# 是不是我 sample 函数没用强约束
# 让我直接看顶/底 sample
n_per_object = 300
n_side = 180
n_top = 60
n_bot = 60
# 柱 5 的 sample 范围: 0-179 柱面, 180-239 顶, 240-299 底
# 1525 / 300 = 5.083 → 柱 5 的第 25 个点（柱面 25）
# 柱 5 sample 300 点，id 1500-1799
# 25th 柱面 → idx 1500 + 24 = 1524 或 1525
print('idx 1525 is in pillar 5, sample idx in pillar:', 1525 - 1500)
