import numpy as np
from config import C, finalize_pixel_mapping
from world import SceneWorld, Pillar
from gt_surface import sample_gt_surface

finalize_pixel_mapping(C)
world = SceneWorld(C)
points, normals = sample_gt_surface(world, n_per_object=300, rng=np.random.default_rng(42))

# idx=1525 的点
pt = points[1525]
print('idx 1525:', pt)

# 用 NumPy 向量化算每个 obj 的距离
all_min = np.full(len(points), np.inf)
for i, obj in enumerate(world.pillars):
    dxy = np.sqrt((points[:, 0] - obj.cx)**2 + (points[:, 1] - obj.cy)**2)
    dz = points[:, 2]
    side = np.abs(dxy - obj.radius)
    top = np.abs(dz - obj.height)
    bot = np.abs(dz - 0.0)
    in_cyl = (dxy < obj.radius) & (dz > 0) & (dz < obj.height)
    d = np.where(in_cyl, np.minimum(top, bot), np.minimum(np.minimum(side, top), bot))
    # 直接看 1525 距离
    print(f'  obj {i}: d[1525] = {d[1525]:.4f} (柱 {obj.cx}, {obj.cy}, r={obj.radius}, h={obj.height})')
    all_min = np.minimum(all_min, d)
    print(f'  -> all_min[1525] = {all_min[1525]:.4f}')
print()
print('final all_min[1525]:', all_min[1525])
print('all_min max:', all_min.max(), 'at idx', all_min.argmax())
print('max pt:', points[all_min.argmax()])
