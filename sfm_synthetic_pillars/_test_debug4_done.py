import numpy as np
from config import C, finalize_pixel_mapping
from world import SceneWorld, Pillar, Cube, Sphere
from gt_surface import sample_gt_surface

finalize_pixel_mapping(C)
world = SceneWorld(C)
points, normals = sample_gt_surface(world, n_per_object=300, rng=np.random.default_rng(42))

# 用最差点的位置 (2.614, -0.360, 1.002)
pt = np.array([[2.614, -0.360, 1.002]])
print('Test point:', pt[0])

# 对每个 obj 算距离
for i, obj in enumerate(world.all_objects):
    if isinstance(obj, Pillar):
        dxy = np.sqrt((pt[0, 0] - obj.cx)**2 + (pt[0, 1] - obj.cy)**2)
        dz = pt[0, 2]
        side = abs(dxy - obj.radius)
        top = abs(dz - obj.height)
        bot = abs(dz - 0.0)
        in_cyl = (dxy < obj.radius) & (dz > 0) & (dz < obj.height)
        if in_cyl:
            d = min(top, bot)
        else:
            d = min(min(side, top), bot)
        print(f'  obj {i} Pillar ({obj.cx}, {obj.cy}, r={obj.radius}, h={obj.height}): dxy={dxy:.4f}, side={side:.4f}, in_cyl={in_cyl}, d={d:.4f}')

# 用全 points 数组
print()
print('===== 用 points 数组算 =====')
all_min = np.full(len(points), np.inf)
for i, obj in enumerate(world.all_objects):
    if isinstance(obj, Pillar):
        dxy = np.sqrt((points[:, 0] - obj.cx)**2 + (points[:, 1] - obj.cy)**2)
        dz = points[:, 2]
        side = np.abs(dxy - obj.radius)
        top = np.abs(dz - obj.height)
        bot = np.abs(dz - 0.0)
        in_cyl = (dxy < obj.radius) & (dz > 0) & (dz < obj.height)
        d = np.where(in_cyl, np.minimum(top, bot), np.minimum(np.minimum(side, top), bot))
    all_min = np.minimum(all_min, d)

idx = all_min.argmax()
print('最差点 idx:', idx, 'd:', all_min[idx])
print('最差点:', points[idx])
