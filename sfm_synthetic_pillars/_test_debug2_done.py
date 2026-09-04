import numpy as np
from config import C, finalize_pixel_mapping
from world import SceneWorld
from gt_surface import sample_gt_surface

finalize_pixel_mapping(C)
world = SceneWorld(C)
points, normals = sample_gt_surface(world, n_per_object=300, rng=np.random.default_rng(42))
print(f'sampled: {len(points)} points')

# 第一个柱子的距离
p0 = world.pillars[0]
print(f'Pillar 0: cx={p0.cx}, cy={p0.cy}, r={p0.radius}, h={p0.height}')

dxy = np.linalg.norm(points[:, :2] - np.array([p0.cx, p0.cy]), axis=1)
dz = points[:, 2]
print(f'  dxy min={dxy.min():.4f}, max={dxy.max():.4f}')
print(f'  dz min={dz.min():.4f}, max={dz.max():.4f}')
side_dist = np.abs(dxy - p0.radius)
top_dist = np.abs(dz - p0.height)
bot_dist = np.abs(dz - 0.0)
print(f'  side_dist: min={side_dist.min():.4e}, max={side_dist.max():.4e}')
print(f'  top_dist: min={top_dist.min():.4e}, max={top_dist.max():.4e}')
print(f'  bot_dist: min={bot_dist.min():.4e}, max={bot_dist.max():.4e}')

in_cyl = (dxy < p0.radius) & (dz > 0) & (dz < p0.height)
print(f'  in_cyl: {in_cyl.sum()} / {len(points)}')

min_d = np.where(in_cyl, np.minimum(top_dist, bot_dist),
                 np.minimum(np.minimum(side_dist, top_dist), bot_dist))
print(f'  min_d: min={min_d.min():.4e}, max={min_d.max():.4e}')
print(f'  min_d > 0.01: {(min_d > 0.01).sum()}')
print(f'  min_d > 0.1: {(min_d > 0.1).sum()}')
print(f'  min_d > 1.0: {(min_d > 1.0).sum()}')

# 看看具体点
idx = min_d.argmax()
print(f'\\n最差点: idx={idx}, point={points[idx]}, dxy={dxy[idx]:.4f}, dz={dz[idx]:.4f}')
print(f'  side_dist={side_dist[idx]:.4f}, top_dist={top_dist[idx]:.4f}, bot_dist={bot_dist[idx]:.4f}')
print(f'  in_cyl={in_cyl[idx]}, min_d={min_d[idx]:.4f}')

# 实际点是不是真的在柱 0 表面
print(f'  距柱 0 中心: {np.linalg.norm(points[idx] - np.array([p0.cx, p0.cy, 0])):.4f}')
