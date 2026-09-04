import numpy as np
from config import C, finalize_pixel_mapping
from world import SceneWorld
from gt_surface import sample_gt_surface

finalize_pixel_mapping(C)
world = SceneWorld(C)
points, normals = sample_gt_surface(world, n_per_object=300, rng=np.random.default_rng(42))
print('points[1525] =', points[1525])

obj = world.pillars[5]
print('obj 5 =', obj.cx, obj.cy, obj.radius, obj.height)

# 显式算
dxy = np.sqrt((points[:, 0] - obj.cx)**2 + (points[:, 1] - obj.cy)**2)
print('dxy[1525] =', dxy[1525])
print('points[1525, 0] - cx =', points[1525, 0] - obj.cx)
print('points[1525, 1] - cy =', points[1525, 1] - obj.cy)
print('(x-cx)^2 + (y-cy)^2 =', (points[1525, 0] - obj.cx)**2 + (points[1525, 1] - obj.cy)**2)
print('sqrt:', np.sqrt((points[1525, 0] - obj.cx)**2 + (points[1525, 1] - obj.cy)**2))

side = np.abs(dxy - obj.radius)
print('side[1525] =', side[1525])
print('dxy[1525] - radius =', dxy[1525] - obj.radius)
print()

# 我猜 d = min(side, top, bot) 选错了
top = np.abs(points[:, 2] - obj.height)
bot = np.abs(points[:, 2] - 0.0)
print('top[1525] =', top[1525])
print('bot[1525] =', bot[1525])
in_cyl = (dxy < obj.radius) & (points[:, 2] > 0) & (points[:, 2] < obj.height)
print('in_cyl[1525] =', in_cyl[1525])
print('(dxy < radius)[1525] =', (dxy < obj.radius)[1525])
print()
# 算 d
d = np.where(in_cyl, np.minimum(top, bot), np.minimum(np.minimum(side, top), bot))
print('d[1525] =', d[1525])
