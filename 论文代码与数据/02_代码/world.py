"""
3D 场景模块 —— 多种几何目标
================================

支持：
  - Pillar：垂直圆柱（默认）
  - Cube：立方体（6 个面，bbox 求交）
  - Sphere：球（球面方程）
  - L-shape：L 形块（2 个 cube 组合）

渲染策略（统一）：
  对每个 (theta, phi) 方向，用 ray-tracing 求最近命中点：
    1) 圆柱：解析求交
    2) 立方体：AABB 6 面求交
    3) 球：球面求交
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import List, Tuple, Optional
import numpy as np

from config import Config, C, SceneCfg


@dataclass
class Pillar:
    cx: float; cy: float; radius: float; height: float

    def surface_normal(self, x, y, z):
        dxy = np.hypot(x - self.cx, y - self.cy)
        if abs(dxy - self.radius) < 1e-2:
            n = np.array([x - self.cx, y - self.cy, 0.0])
            n /= max(np.linalg.norm(n), 1e-9)
            return n
        if abs(z - self.height) < 1e-2:
            return np.array([0.0, 0.0, 1.0])
        if abs(z) < 1e-2:
            return np.array([0.0, 0.0, -1.0])
        return np.array([0.0, 0.0, 1.0])


@dataclass
class Cube:
    """中心 (cx, cy)，底面 z=z_bottom，边长 = 2*half_size"""
    cx: float; cy: float; z_bottom: float; half_size: float

    def surface_normal(self, x, y, z):
        # 简化：返回主要面法向
        dx, dy, dz = x - self.cx, y - self.cy, z - (self.z_bottom + self.half_size)
        h = self.half_size
        adx, ady, adz = abs(dx), abs(dy), abs(dz)
        if adx > ady and adx > adz:
            return np.array([1.0 if dx > 0 else -1.0, 0, 0])
        if ady > adx and ady > adz:
            return np.array([0, 1.0 if dy > 0 else -1.0, 0])
        return np.array([0, 0, 1.0 if dz > 0 else -1.0])


@dataclass
class Sphere:
    cx: float; cy: float; cz: float; radius: float

    def surface_normal(self, x, y, z):
        n = np.array([x - self.cx, y - self.cy, z - self.cz])
        n /= max(np.linalg.norm(n), 1e-9)
        return n


def _ray_aabb_intersect(o, d, box_min, box_max):
    """射线-AABB 求交。返回 (t_near, t_far) 或 None。"""
    inv_d = np.where(np.abs(d) > 1e-9, 1.0 / d, np.inf)
    t1 = (box_min - o) * inv_d
    t2 = (box_max - o) * inv_d
    t_near = np.max(np.minimum(t1, t2))
    t_far = np.min(np.maximum(t1, t2))
    if t_near > t_far or t_far < 1e-6:
        return None
    return t_near, t_far


def _ray_sphere_intersect(o, d, center, radius):
    """射线-球求交。返回 t 列表（最多 2 个）。"""
    oc = o - center
    b = float(np.dot(oc, d))
    c = float(np.dot(oc, oc) - radius ** 2)
    disc = b * b - c
    if disc < 0:
        return []
    sq = np.sqrt(disc)
    return [-b - sq, -b + sq]


def _ray_cylinder_intersect(o, d, center_xy, radius, z_min, z_max):
    """射线-有限圆柱求交（侧面 + 上下底）。返回 t 或 None。"""
    oc = o[:2] - center_xy
    dxdy = d[:2]
    a = float(np.dot(dxdy, dxdy))
    b = 2.0 * float(np.dot(oc, dxdy))
    c = float(np.dot(oc, oc) - radius ** 2)
    if a < 1e-9:
        return None
    disc = b * b - 4 * a * c
    if disc < 0:
        return None
    sq = np.sqrt(disc)
    t1 = (-b - sq) / (2 * a)
    t2 = (-b + sq) / (2 * a)
    candidates = []
    for t in [t1, t2]:
        if t > 1e-6:
            z = o[2] + t * d[2]
            if z_min - 1e-3 <= z <= z_max + 1e-3:
                candidates.append(t)
    # 上下底
    if abs(d[2]) > 1e-9:
        for z_face in [z_min, z_max]:
            t = (z_face - o[2]) / d[2]
            if t > 1e-6:
                p = o + t * d
                if np.hypot(p[0] - center_xy[0], p[1] - center_xy[1]) <= radius + 1e-3:
                    candidates.append(t)
    if not candidates:
        return None
    return min(candidates)


def _ray_object_intersect(o, d, obj):
    """统一接口：射线-物体求交，返回最近 t 或 None。"""
    if isinstance(obj, Pillar):
        return _ray_cylinder_intersect(o, d, np.array([obj.cx, obj.cy]),
                                       obj.radius, 0.0, obj.height)
    if isinstance(obj, Cube):
        box_min = np.array([obj.cx - obj.half_size, obj.cy - obj.half_size, obj.z_bottom])
        box_max = np.array([obj.cx + obj.half_size, obj.cy + obj.half_size, obj.z_bottom + 2 * obj.half_size])
        res = _ray_aabb_intersect(o, d, box_min, box_max)
        if res is None:
            return None
        return res[0]
    if isinstance(obj, Sphere):
        ts = _ray_sphere_intersect(o, d, np.array([obj.cx, obj.cy, obj.cz]), obj.radius)
        if not ts:
            return None
        # 保留 > 1e-6 的最近
        valid = [t for t in ts if t > 1e-6]
        return min(valid) if valid else None
    return None


class SceneWorld:
    """统一场景容器。"""
    def __init__(self, cfg: Config = C):
        self.cfg = cfg
        self.pillars: List[Pillar] = [Pillar(*p) for p in cfg.scene.pillars]
        self.cubes: List[Cube] = [Cube(*c) for c in cfg.scene.cubes]
        self.spheres: List[Sphere] = [Sphere(*s) for s in cfg.scene.spheres]
        self.rubble: List[Sphere] = [
            Sphere(r[0], r[1], r[2], r[3]) for r in cfg.scene.rubble
        ]
        self.floor_z = cfg.scene.floor_z_m
        self.surface_z = cfg.scene.surface_z_m
        self.all_objects: list = self.pillars + self.cubes + self.spheres + self.rubble
        self._landmarks_cache: Optional[np.ndarray] = None

    def sample_landmarks(self, n_per_pillar: int = 30, n_floor: int = 0,
                         rng: Optional[np.random.Generator] = None,
                         use_cache: bool = True) -> np.ndarray:
        """从所有几何目标采样 landmark。"""
        if use_cache and self._landmarks_cache is not None and n_floor == 0:
            return self._landmarks_cache
        if rng is None:
            rng = np.random.default_rng(self.cfg.seed)
        lms = []
        # 圆柱面
        for p in self.pillars:
            az = rng.uniform(0, 2 * np.pi, n_per_pillar)
            hh = rng.uniform(0.1, p.height - 0.1, n_per_pillar)
            for a, h in zip(az, hh):
                lms.append([p.cx + p.radius * np.cos(a),
                            p.cy + p.radius * np.sin(a), h])
        # 立方体（6 面，每面 n_per_pillar/6）
        for c in self.cubes:
            n_per_face = max(2, n_per_pillar // 6)
            for axis in range(3):
                for sign in [-1, 1]:
                    for _ in range(n_per_face):
                        u = rng.uniform(-c.half_size, c.half_size)
                        v = rng.uniform(-c.half_size, c.half_size)
                        pt = [c.cx, c.cy, c.z_bottom + c.half_size]
                        if axis == 0: pt[0] += sign * c.half_size
                        elif axis == 1: pt[1] += sign * c.half_size
                        else: pt[2] += sign * c.half_size
                        off = [0, 0, 0]
                        if axis == 0: off[1] = u; off[2] = v
                        elif axis == 1: off[0] = u; off[2] = v
                        else: off[0] = u; off[1] = v
                        lms.append([pt[0] + off[0], pt[1] + off[1], pt[2] + off[2]])
        # 球面
        for s in self.spheres:
            az = rng.uniform(0, 2 * np.pi, n_per_pillar)
            el = rng.uniform(-np.pi / 2 + 0.1, np.pi / 2 - 0.1, n_per_pillar)
            for a, e in zip(az, el):
                lms.append([s.cx + s.radius * np.cos(e) * np.cos(a),
                            s.cy + s.radius * np.cos(e) * np.sin(a),
                            s.cz + s.radius * np.sin(e)])
        # 散石（小球近似）
        for s in self.rubble:
            az = rng.uniform(0, 2 * np.pi, max(2, n_per_pillar // 4))
            el = rng.uniform(0, np.pi / 2 - 0.1, max(2, n_per_pillar // 4))
            for a, e in zip(az, el):
                lms.append([s.cx + s.radius * np.cos(e) * np.cos(a),
                            s.cy + s.radius * np.cos(e) * np.sin(a),
                            s.cz + s.radius * np.sin(e)])
        # 地板
        for _ in range(n_floor):
            x = rng.uniform(-2.5, 2.5)
            y = rng.uniform(-1.5, 1.5)
            lms.append([x, y, self.floor_z + 0.001])
        out = np.array(lms) if lms else np.zeros((0, 3))
        if use_cache and n_floor == 0:
            self._landmarks_cache = out
        return out

    def pillar_intersection(self, pillar: Pillar, R_wb, t_wb, theta, elev):
        """兼容旧接口：单根柱面求交。"""
        d_b = np.array([np.cos(theta) * np.cos(elev),
                        np.sin(theta) * np.cos(elev),
                        np.sin(elev)])
        d_w = R_wb @ d_b
        return _ray_cylinder_intersect(t_wb, d_w, np.array([pillar.cx, pillar.cy]),
                                        pillar.radius, 0.0, pillar.height)

    def surface_normal(self, x, y, z):
        """返回该点处的外法线（按最近物体）。"""
        for obj in self.all_objects:
            if isinstance(obj, Pillar):
                dxy = np.hypot(x - obj.cx, y - obj.cy)
                if abs(dxy - obj.radius) < 1e-2 and 0 <= z <= obj.height:
                    return obj.surface_normal(x, y, z)
            elif isinstance(obj, Cube):
                if (abs(x - obj.cx) >= obj.half_size - 1e-2 or
                    abs(y - obj.cy) >= obj.half_size - 1e-2 or
                    abs(z - (obj.z_bottom + obj.half_size)) >= obj.half_size - 1e-2):
                    if (obj.cx - obj.half_size - 1e-2 <= x <= obj.cx + obj.half_size + 1e-2 and
                        obj.cy - obj.half_size - 1e-2 <= y <= obj.cy + obj.half_size + 1e-2 and
                        obj.z_bottom - 1e-2 <= z <= obj.z_bottom + 2 * obj.half_size + 1e-2):
                        return obj.surface_normal(x, y, z)
            elif isinstance(obj, Sphere):
                if abs(np.linalg.norm([x - obj.cx, y - obj.cy, z - obj.cz]) - obj.radius) < 1e-2:
                    return obj.surface_normal(x, y, z)
        return np.array([0.0, 0.0, 1.0])

    def ray_intersect_all(self, R_wb, t_wb, theta, elev):
        """统一接口：射线对所有物体求交，返回最近命中 (t, object)。"""
        d_b = np.array([np.cos(theta) * np.cos(elev),
                        np.sin(theta) * np.cos(elev),
                        np.sin(elev)])
        d_w = R_wb @ d_b
        o = t_wb
        best_t = None
        best_obj = None
        for obj in self.all_objects:
            t = _ray_object_intersect(o, d_w, obj)
            if t is not None and (best_t is None or t < best_t):
                best_t = t
                best_obj = obj
        return best_t, best_obj

    def pixel_intensity(self, R_wb, t_wb, theta, rho_pixel, elev_min, elev_max,
                        n_elev_samples=31):
        """积分求像素强度。"""
        dphi = (elev_max - elev_min) / (n_elev_samples - 1)
        elevs = np.linspace(elev_min, elev_max, n_elev_samples)
        total = 0.0
        best_hit = None
        best_r = np.inf
        for phi in elevs:
            t, obj = self.ray_intersect_all(R_wb, t_wb, theta, phi)
            if t is None:
                continue
            hit = t_wb + t * (R_wb @ np.array([np.cos(theta)*np.cos(phi),
                                                np.sin(theta)*np.cos(phi),
                                                np.sin(phi)]))
            r = np.linalg.norm(hit - t_wb)
            if abs(r - rho_pixel) > 0.02:
                continue
            n_w = self.surface_normal(*hit)
            d_w = (hit - t_wb) / max(r, 1e-6)
            cos_inc = max(0.0, -float(n_w @ d_w))
            I = cos_inc / (r * r + 0.01)
            if I > total:
                total = I
                if r < best_r:
                    best_r = r
                    best_hit = hit
        return total, best_hit
