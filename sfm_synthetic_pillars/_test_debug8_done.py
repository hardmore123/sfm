import numpy as np
from config import C, finalize_pixel_mapping
from world import SceneWorld
from gt_surface import sample_gt_surface, verify_sample_quality

finalize_pixel_mapping(C)
world = SceneWorld(C)
points, normals = sample_gt_surface(world, n_per_object=300, rng=np.random.default_rng(42))

# 重新算 min_d_per_point
min_d_per_point = np.full(len(points), np.inf)
for obj in world.pillars:
    dxy = np.sqrt((points[:, 0] - obj.cx)**2 + (points[:, 1] - obj.cy)**2)
    dz = points[:, 2]
    side = np.abs(dxy - obj.radius)
    top = np.abs(dz - obj.height)
    bot = np.abs(dz - 0.0)
    in_cyl = (dxy <= obj.radius + 1e-9) & (dz > -1e-9) & (dz < obj.height + 1e-9)
    d = np.where(in_cyl, np.minimum(top, bot), np.minimum(np.minimum(side, top), bot))
    min_d_per_point = np.minimum(min_d_per_point, d)

print('min_d_per_point max:', min_d_per_point.max())
print('idx of max:', min_d_per_point.argmax())
print('point:', points[min_d_per_point.argmax()])

# 看每根柱
for i, obj in enumerate(world.pillars):
    dxy = np.sqrt((points[:, 0] - obj.cx)**2 + (points[:, 1] - obj.cy)**2)
    dz = points[:, 2]
    side = np.abs(dxy - obj.radius)
    top = np.abs(dz - obj.height)
    bot = np.abs(dz - 0.0)
    in_cyl = (dxy <= obj.radius + 1e-9) & (dz > -1e-9) & (dz < obj.height + 1e-9)
    d = np.where(in_cyl, np.minimum(top, bot), np.minimum(np.minimum(side, top), bot))
    print(f'  obj {i} ({obj.cx}, {obj.cy}, r={obj.radius}, h={obj.height}): d at idx 1525 = {d[1525]:.4e}')
