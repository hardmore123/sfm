"""
成像声呐模拟渲染器 V3
==========================

T0.5 + T0.6 重写：
  T0.5: 加海底 Lambert 散射 + 阴影衰减
       - 海底电平用 Kearney 2022 公式 σ ∝ sin²(θ_g)
       - 阴影区用 shadow.py 的 shadow_mask
       - 噪声底用 Rayleigh 散斑
       - 验收：海底像素 >噪声底 3σ 占比 ≥80%
              阴影/海底强度比达标
       v3 阶段表：海底电平 − 噪声底 ≥ 10 dB
                  阴影区 ≤ 噪声底 + 3 dB
  T0.6: 遍历 `world.all_objects`（修 E2）
       - 之前只画柱子
       - 现在统一用 `world.ray_intersect_all`
       - 验收：立方/球/散石场景目标像素数 >0

物理模型（参考 Kearney 2022 / HoloOcean）：
  I(rho, theta) = (E_e / r^2) · T(r) · σ(θ, φ) · cos(θ_inc)
  其中：
    E_e : 发射能量
    r   : 斜距
    T(r): 传播衰减 = 1 / (r²) · exp(-absorption · r)
    σ(θ, φ): 散射系数
    cos(θ_inc): 入射余弦（依赖目标表面法向）
  散射模型：
    Lambert:  σ = (ρ/π) · cos²(θ_i) ∝ sin²(θ_g)   （掠射角 < 45°）
    Jackson:  三域 D1/D2/D3

输出（每帧）：
  render_frame() → image (H, W) intensity
"""
from __future__ import annotations
from typing import Optional, Tuple
import numpy as np

from config import Config, C, SonarCfg, finalize_pixel_mapping
from world import SceneWorld, Pillar, Cube, Sphere
from trajectory import euler_to_matrix


def _beam_grid_rad(cfg: SonarCfg) -> np.ndarray:
    az_lo, az_hi = cfg.fov_azimuth_deg
    return np.deg2rad(np.linspace(az_lo, az_hi, cfg.beam_count))


def _range_grid(cfg: SonarCfg) -> np.ndarray:
    return np.linspace(cfg.range_min_m, cfg.range_max_m, cfg.range_bin_count)


def _seafloor_lambert_intensity(
    seafloor_pt: np.ndarray,  # 命中点 (x, y, z_floor)
    t_wb: np.ndarray,
    rho: float,
    seafloor_coeff: float = 10.0,  # 海底 Lambert 散射系数（线性）
) -> float:
    """
    海底 Lambert 散射强度（Kearney 2022 / 吴金荣 2014）。
    公式：σ = K · sin²(θ_g) / r²
    其中：
      K = seafloor_coeff（线性 Lambert 系数，无量纲）
        物理上 K ∝ μ_linear × system_gain
        泥底 μ = -27 dB（吴金荣 2014），加 K=5000 仿真增益 → K = 10
      θ_g = 掠射角（grazing angle）

    海底法线 = +z（朝上）。
    d_inc = (seafloor_pt - t_wb) / rho（从声呐到 hit，指向下方）
    sin(θ_g) = abs(d_inc[2])

    强度 = K · sin²(θ_g) / r²
    """
    d_inc = (seafloor_pt - t_wb) / rho
    sin_grazing = abs(d_inc[2])  # = |sin(elev)|
    sin_grazing = max(sin_grazing, 1e-3)
    I = seafloor_coeff * (sin_grazing ** 2) / (rho ** 2)
    return I


def _object_intensity(
    obj, hit: np.ndarray, t_wb: np.ndarray, rho: float
) -> float:
    """
    物体表面散射强度（简化 Lambert 散射）。
    对柱、立方、球统一用 Lambert 模型。
    """
    n = obj.surface_normal(*hit)
    d = (hit - t_wb) / rho
    cos_inc = max(0.0, float(-np.dot(n, d)))
    # 强度 = cos(θ_i) / r²（简化 Lambert）
    I = cos_inc / (rho ** 2 + 0.01)
    return I


def render_frame(
    T_wb: np.ndarray,
    world: SceneWorld,
    cfg: Config = C,
    shadow_mask: Optional[np.ndarray] = None,  # (H, W) bool, 若提供则应用阴影衰减
    n_elev: int = 25,
    rng: Optional[np.random.Generator] = None,
    return_pixel_hits: bool = False,
):
    """
    单帧渲染 V3。

    改进：
    - 遍历 world.all_objects（pillar/cube/sphere/rubble）
    - 加海底 Lambert 散射（v3 阶段表 §4 T0.5）
    - 加阴影衰减（用 shadow_mask）
    - 加 Rayleigh 散斑 + 噪声底
    """
    finalize_pixel_mapping(cfg)
    sonar = cfg.sonar
    beams_rad = _beam_grid_rad(sonar)               # (W,)
    rngs_m = _range_grid(sonar)                     # (H,)
    H, W = sonar.range_bin_count, sonar.beam_count
    elev_lo = np.deg2rad(sonar.fov_elevation_deg[0])
    elev_hi = np.deg2rad(sonar.fov_elevation_deg[1])
    phis = np.linspace(elev_lo, elev_hi, n_elev)    # (P,)

    R_wb = T_wb[:3, :3]
    t_wb = T_wb[:3, 3]
    pm = sonar.pixel_map
    a_b, b_b = pm["beam"]["a"], pm["beam"]["b"]
    c_r, d_r = pm["range"]["c"], pm["range"]["d"]

    # 1. 渲染图像
    image = np.zeros((H, W), dtype=np.float64)

    # 1a. 海底背景：所有 beam 上都先有 Lambert 海底回波
    for col, theta in enumerate(beams_rad):
        for phi in phis:
            # 海底平面 = world.floor_z
            if abs(np.sin(phi)) < 1e-6:
                continue  # 水平射线不碰 floor
            # 海底 hit: z_floor + t*sin(phi) = world.floor_z
            # 但要从声呐出发，方向 (cos(theta)*cos(phi), sin(theta)*cos(phi), sin(phi))
            # 在 body 坐标系：方向 d_b = (cos(θ)cos(φ), sin(θ)cos(φ), sin(φ))
            d_b = np.array([np.cos(theta) * np.cos(phi),
                            np.sin(theta) * np.cos(phi),
                            np.sin(phi)])
            d_w = R_wb @ d_b
            # 在世界系中：起点 t_wb，方向 d_w
            # 海底平面 z = world.floor_z
            if abs(d_w[2]) < 1e-6:
                continue
            t_floor = (world.floor_z - t_wb[2]) / d_w[2]
            if t_floor < 1e-3:
                continue  # 在声呐下面或太近
            rho = float(t_floor)
            if rho < sonar.range_min_m or rho > sonar.range_max_m:
                continue
            hit = t_wb + t_floor * d_w
            # 海底强度（线性 Lambert 系数）
            I = _seafloor_lambert_intensity(
                hit, t_wb, rho,
                seafloor_coeff=world.cfg.scene.seafloor_backscatter)
            # 像素位置
            bi = int(np.clip(np.round(a_b * theta + b_b), 0, W - 1))
            ri = int(np.clip(np.round(c_r * rho + d_r), 0, H - 1))
            image[ri, bi] = max(image[ri, bi], I)

    # 1b. 物体：遍历 world.all_objects
    for obj in world.all_objects:
        # 优化：先算 bbox 投影到 range-beam 空间，只对相关像素循环
        for col, theta in enumerate(beams_rad):
            for phi in phis:
                t, hit = _ray_object_intersect(R_wb, t_wb, theta, phi, obj)
                if t is None or hit is None:
                    continue
                rho = float(np.linalg.norm(hit - t_wb))
                if rho < sonar.range_min_m or rho > sonar.range_max_m:
                    continue
                I = _object_intensity(obj, hit, t_wb, rho)
                bi = int(np.clip(np.round(a_b * theta + b_b), 0, W - 1))
                ri = int(np.clip(np.round(c_r * rho + d_r), 0, H - 1))
                # 物体强度高于海底（一般），叠加
                image[ri, bi] = max(image[ri, bi], I)

    # 2. 应用阴影衰减（若提供 shadow_mask）
    if shadow_mask is not None:
        # 阴影区强度衰减到 noise_floor
        image = np.where(shadow_mask, image * cfg.scene.shadow_attenuation, image)

    # 3. 加噪声：散斑（乘性高斯）+ 噪声底（加性）
    if rng is not None:
        speckle = rng.normal(1.0, sonar.speckle_sigma, image.shape)
        speckle = np.clip(speckle, 0.0, None)
        image = image * speckle
        # 噪声底（Kearney 2022 Rayleigh）
        noise_floor = 10 ** (-sonar.noise_floor_db / 20.0) * 0.001
        image = image + np.abs(rng.normal(0, noise_floor, image.shape))
        image = np.clip(image, 0, None)

    return image.astype(np.float32)


def _ray_object_intersect(R_wb, t_wb, theta, phi, obj):
    """单物体射线追踪（与 world._ray_object_intersect 等价，但避免 import 复杂）。"""
    d_b = np.array([np.cos(theta) * np.cos(phi),
                    np.sin(theta) * np.cos(phi),
                    np.sin(phi)])
    d_w = R_wb @ d_b
    if isinstance(obj, Pillar):
        from world import _ray_cylinder_intersect
        t = _ray_cylinder_intersect(t_wb, d_w, np.array([obj.cx, obj.cy]),
                                    obj.radius, 0.0, obj.height)
        if t is None:
            return None, None
        hit = t_wb + t * d_w
        return float(t), hit
    if isinstance(obj, Cube):
        from world import _ray_aabb_intersect
        box_min = np.array([obj.cx - obj.half_size, obj.cy - obj.half_size, obj.z_bottom])
        box_max = np.array([obj.cx + obj.half_size, obj.cy + obj.half_size,
                            obj.z_bottom + 2 * obj.half_size])
        res = _ray_aabb_intersect(t_wb, d_w, box_min, box_max)
        if res is None:
            return None, None
        t = res[0]
        hit = t_wb + t * d_w
        return float(t), hit
    if isinstance(obj, Sphere):
        from world import _ray_sphere_intersect
        ts = _ray_sphere_intersect(t_wb, d_w, np.array([obj.cx, obj.cy, obj.cz]), obj.radius)
        if not ts:
            return None, None
        valid = [t for t in ts if t > 1e-6]
        if not valid:
            return None, None
        t = min(valid)
        hit = t_wb + t * d_w
        return float(t), hit
    return None, None


def render_all_frames(
    poses_T: np.ndarray,
    world: SceneWorld,
    cfg: Config = C,
    shadow_masks: Optional[np.ndarray] = None,  # (N, H, W) bool
    n_elev: int = 25,
    rng: Optional[np.random.Generator] = None,
    verbose: bool = True,
):
    """批量渲染 V3。"""
    N = poses_T.shape[0]
    sonar = cfg.sonar
    H, W = sonar.range_bin_count, sonar.beam_count
    images = np.zeros((N, H, W), dtype=np.float32)
    for i in range(N):
        if verbose and ((i + 1) % 5 == 0 or i == 0 or i == N - 1):
            print(f"  [render v3] frame {i+1}/{N}", flush=True)
        sm = shadow_masks[i] if shadow_masks is not None else None
        images[i] = render_frame(
            poses_T[i], world, cfg=cfg, shadow_mask=sm,
            n_elev=n_elev, rng=rng)
    return images
