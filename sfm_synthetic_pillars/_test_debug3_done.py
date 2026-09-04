import numpy as np
from config import C, finalize_pixel_mapping
from world import SceneWorld, Pillar, Cube, Sphere
from gt_surface import sample_gt_surface

finalize_pixel_mapping(C)
world = SceneWorld(C)
print('all_objects:', len(world.all_objects))
for i, obj in enumerate(world.all_objects):
    print(f'  {i}: {type(obj).__name__}')

points, normals = sample_gt_surface(world, n_per_object=300, rng=np.random.default_rng(42))
print(f'sampled: {len(points)} points')

# 对每个 obj 算所有点的距离
for i, obj in enumerate(world.all_objects):
    if isinstance(obj, Pillar):
        dxy = np.linalg.norm(points[:, :2] - np.array([obj.cx, obj.cy]), axis=1)
        dz = points[:, 2]
        side_dist = np.abs(dxy - obj.radius)
        top_dist = np.abs(dz - obj.height)
        bot_dist = np.abs(dz - 0.0)
        in_cyl = (dxy < obj.radius) & (dz > 0) & (dz < obj.height)
        d_obj = np.where(in_cyl,
                         np.minimum(top_dist, bot_dist),
                         np.minimum(np.minimum(side_dist, top_dist), bot_dist))
        n_in_cyl = in_cyl.sum()
        min_per = d_obj.min()
        max_per = d_obj.max()
    elif isinstance(obj, Sphere):
        r = np.linalg.norm(points - np.array([obj.cx, obj.cy, obj.cz]), axis=1)
        d_obj = np.abs(r - obj.radius)
        min_per = d_obj.min()
        max_per = d_obj.max()
    elif isinstance(obj, Cube):
        dx = np.abs(points[:, 0] - obj.cx) - obj.half_size
        dy = np.abs(points[:, 1] - obj.cy) - obj.half_size
        dz = np.abs(points[:, 2] - (obj.z_bottom + obj.half_size)) - obj.half_size
        d_obj = np.maximum(np.maximum(dx, dy), dz)
        min_per = d_obj.min()
        max_per = d_obj.max()
    else:
        continue
    print(f'  obj {i} ({type(obj).__name__}): min_dist={min_per:.4e}, max_dist={max_per:.4e}')

# 找最差点
all_min = np.full(len(points), np.inf)
for obj in world.all_objects:
    if isinstance(obj, Pillar):
        dxy = np.linalg.norm(points[:, :2] - np.array([obj.cx, obj.cy]), axis=1)
        dz = points[:, 2]
        side_dist = np.abs(dxy - obj.radius)
        top_dist = np.abs(dz - obj.height)
        bot_dist = np.abs(dz - 0.0)
        in_cyl = (dxy < obj.radius) & (dz > 0) & (dz < obj.height)
        d_obj = np.where(in_cyl,
                         np.minimum(top_dist, bot_dist),
                         np.minimum(np.minimum(side_dist, top_dist), bot_dist))
    elif isinstance(obj, Sphere):
        r = np.linalg.norm(points - np.array([obj.cx, obj.cy, obj.cz]), axis=1)
        d_obj = np.abs(r - obj.radius)
    elif isinstance(obj, Cube):
        dx = np.abs(points[:, 0] - obj.cx) - obj.half_size
        dy = np.abs(points[:, 1] - obj.cy) - obj.half_size
        dz = np.abs(points[:, 2] - (obj.z_bottom + obj.half_size)) - obj.half_size
        d_obj = np.maximum(np.maximum(dx, dy), dz)
    else:
        continue
    all_min = np.minimum(all_min, d_obj)

print('global min per point max:', all_min.max())
print('最差点 idx:', all_min.argmax(), 'min_d:', all_min[all_min.argmax()])
print('最差点 point:', points[all_min.argmax()])
