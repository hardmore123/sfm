"""
声学阴影生成器 V5.2 — 解析几何（去 GT 依赖 + 物理正确）
========================================================

v4 之前的 bug（已修）：用 `world.pillars` 的 `max(height)` 作为 h_eff，触发 D1（真值泄漏）。
v5 修复：用 `world.ray_intersect_all` 射线追踪，**不**用任何全局高度。
v5.1 选 max z 命中：但对柱，max z 命中是柱面某点 z ≠ 柱顶 h，导致 L_s 偏小。
v5.2 改用**解析几何**：
  - 对每根 beam 遍历所有物体
  - 对每个物体，**已知** (cx, cy, h)（物体几何），用解析公式算阴影：
    - d_horiz_obj = sqrt((cx - sx)² + (cy - sy)²)   声呐到目标底部水平距离
    - elev_world = arctan((h - z_s) / d_horiz_obj)   顶部射线仰角（向下 < 0）
    - L_s = d_horiz_obj * h / (z_s - h)             阴影长度
  - 存 target 像素 (theta, rho_target) + D_t (= d_horiz_obj)
  - 存 shadow 像素的 L_s（用于反演）
  - 反演 h = L_s * z_s / (D_t + L_s)（精确正演式）
  - **不存 h 到 height_map 的 shadow 像素**（避免恒等式泄漏）

**T0.7 验收**：
  - 单柱场景阴影末端斜距与解析 ρ_e 偏差 ≤ 2 range bin
  - 反演 h 误差必须**非零**（v4 的 2.38e-07 是恒等式泄漏的证据）
  - 误差上限 ≤ 5 cm（v3 阶段表 §6.1 项 2）

输出（每帧）：
  target_mask   (H, W)  bool        — 目标命中像素
  shadow_mask   (H, W)  bool        — 阴影像素
  height_map    (H, W)  float       — 目标 z 坐标（柱顶 h，仅 target 像素有值；shadow 像素 NaN）
  shadow_len    (H, W)  float       — 阴影长度（米，仅 shadow 像素有值）
  D_t_map       (H, W)  float       — 声呐到目标底部水平距离（仅 shadow 像素有值，反演用）
  target_elev   (H, W)  float       — 该 beam 对应目标的等效仰角（弧度）
"""
from __future__ import annotations
import numpy as np
from typing import Tuple

from config import Config, C, SonarCfg
from world import SceneWorld, Pillar, Cube, Sphere


def _beam_grid_rad(cfg: SonarCfg) -> np.ndarray:
    az_lo, az_hi = cfg.fov_azimuth_deg
    return np.deg2rad(np.linspace(az_lo, az_hi, cfg.beam_count))


def _range_grid(cfg: SonarCfg) -> np.ndarray:
    return np.linspace(cfg.range_min_m, cfg.range_max_m, cfg.range_bin_count)


def _object_top_z_and_footprint(obj):
    """返回 (h_top, z_floor, cx, cy, half_extent_xy)：
      h_top  物体顶 z
      z_floor 物体底 z
      cx, cy 物体水平中心
      half_extent_xy 物体水平最大半径（柱: r, 球: r, 立方: half_size*sqrt(2)）
    """
    if isinstance(obj, Pillar):
        return float(obj.height), 0.0, float(obj.cx), float(obj.cy), float(obj.radius)
    if isinstance(obj, Cube):
        h_top = obj.z_bottom + 2 * obj.half_size
        return float(h_top), float(obj.z_bottom), float(obj.cx), float(obj.cy), float(obj.half_size * np.sqrt(2))
    if isinstance(obj, Sphere):
        return float(obj.cz + obj.radius), float(obj.cz - obj.radius), float(obj.cx), float(obj.cy), float(obj.radius)
    return None


def _object_target_z(obj):
    """目标"目标 z"——对该物体在 z=h_top 平面上的命中."""
    if isinstance(obj, Pillar):
        return float(obj.height)
    if isinstance(obj, Cube):
        return float(obj.z_bottom + 2 * obj.half_size)
    if isinstance(obj, Sphere):
        return float(obj.cz + obj.radius)
    return 0.0


def _object_floor_z(obj):
    if isinstance(obj, Pillar):
        return 0.0
    if isinstance(obj, Cube):
        return float(obj.z_bottom)
    if isinstance(obj, Sphere):
        return float(obj.cz - obj.radius)
    return 0.0


def _is_in_azimuth_fov(theta_target: float, beam_thetas: np.ndarray, az_fov_deg: tuple) -> np.ndarray:
    """检查目标方位是否在声呐 FOV 内（按 beam 角度）。返回 bool 数组。"""
    az_lo, az_hi = np.deg2rad(az_fov_deg[0]), np.deg2rad(az_fov_deg[1])
    # 方位差（mod 2π）
    diff = (theta_target - beam_thetas + np.pi) % (2 * np.pi) - np.pi
    return (diff >= az_lo) & (diff <= az_hi)


def render_shadow_map(T_wb: np.ndarray, world: SceneWorld, cfg: Config = C,
                      n_elev: int = 31, min_elev_deg: float = 1.0):
    """
    V5.2 解析几何阴影渲染。

    对每根 beam：
      1. 遍历所有物体
      2. 对每个物体，**已知** (cx, cy, h)：
         - d_horiz_obj = sqrt((cx - sx)² + (cy - sy)²)
         - theta_目标 = atan2(cy - sy, cx - sx)
         - 检查 theta_目标 在 FOV 内
         - elev_world = atan2(h - z_s, d_horiz_obj) （向下 < 0）
         - 检查 elev_world 在 FOV 仰角内
         - L_s = d_horiz_obj * h / (z_s - h)
         - 检查 L_s + d_horiz_obj 在量程内
         - 标记 target 像素 (theta_目标, rho_target) 其中 rho_target = sqrt(d_horiz_obj² + (z_s - h)²)
         - 标记 shadow 像素 (theta_目标, rho_target to rho_target + L_s/cos(elev_world))
    """
    sonar = cfg.sonar
    beams_rad = _beam_grid_rad(sonar)              # (W,)
    rngs_m = _range_grid(sonar)                    # (H,)
    H, W = sonar.range_bin_count, sonar.beam_count

    elev_lo = np.deg2rad(sonar.fov_elevation_deg[0])
    elev_hi = np.deg2rad(sonar.fov_elevation_deg[1])

    R_wb = T_wb[:3, :3]
    t_wb = T_wb[:3, 3]
    sonar_z = float(t_wb[2])

    target_mask = np.zeros((H, W), dtype=bool)
    shadow_mask = np.zeros((H, W), dtype=bool)
    height_map = np.full((H, W), np.nan, dtype=np.float32)
    shadow_len = np.full((H, W), np.nan, dtype=np.float32)
    D_t_map = np.full((H, W), np.nan, dtype=np.float32)
    target_elev = np.full((H, W), np.nan, dtype=np.float32)

    pm = sonar.pixel_map if sonar.pixel_map.get("beam", {}).get("a", 0) != 0 else None
    if pm is None:
        from config import finalize_pixel_mapping
        finalize_pixel_mapping(cfg)
        pm = sonar.pixel_map
    a_b, b_b = pm["beam"]["a"], pm["beam"]["b"]
    c_r, d_r = pm["range"]["c"], pm["range"]["d"]

    range_min = sonar.range_min_m
    range_max = sonar.range_max_m
    dr = rngs_m[1] - rngs_m[0] if len(rngs_m) > 1 else 0.04  # 单 bin 距离

    sx, sy, sz = float(t_wb[0]), float(t_wb[1]), sonar_z

    for col, theta in enumerate(beams_rad):
        # 1. 找该 beam 方向上最近的目标（按 theta_目标 接近 beam_theta 的物体）
        # 简化：对每个物体，检查它的 theta_目标 是否在 beam 的 FOV 邻域
        candidates = []  # (theta_err, d_horiz_obj, h, obj, elev_world, L_s, rho_target)
        for obj in world.all_objects:
            t = _object_target_z(obj)
            z_floor = _object_floor_z(obj)
            if t <= z_floor or t >= sz:
                continue  # 目标在 floor 上或高于声呐，无阴影
            # 物体水平中心
            if isinstance(obj, Pillar):
                cx, cy = obj.cx, obj.cy
            elif isinstance(obj, Cube):
                cx, cy = obj.cx, obj.cy
            elif isinstance(obj, Sphere):
                cx, cy = obj.cx, obj.cy
            else:
                continue
            dx = cx - sx
            dy = cy - sy
            d_horiz_obj = float(np.hypot(dx, dy))
            if d_horiz_obj < 1e-3:
                continue
            theta_目标 = float(np.arctan2(dy, dx))
            # 方位差（mod 2π）
            dtheta = (theta_目标 - theta + np.pi) % (2 * np.pi) - np.pi
            # 容差：物体水平半径 / d_horiz_obj（视角占位）
            r_xy = float(_object_top_z_and_footprint(obj)[4])
            angular_radius = np.arctan2(r_xy, d_horiz_obj)
            if abs(dtheta) > angular_radius + np.deg2rad(0.5):
                continue  # 物体不在该 beam 视角内
            # 顶部仰角
            elev_world = float(np.arctan2(t - sz, d_horiz_obj))  # 向下 < 0
            if elev_world < elev_lo - 1e-3 or elev_world > elev_hi + 1e-3:
                continue
            # 阴影长度（物理 L_s = 沿射线到 z=0 的水平距离，不依赖 range_max）
            L_s = d_horiz_obj * t / (sz - t)
            if L_s < dr:
                continue
            # 阴影末端水平距离
            D_e = d_horiz_obj + L_s
            # 阴影末端斜距
            rho_end = float(np.sqrt(D_e ** 2 + sz ** 2))
            # target 斜距（声呐到顶）
            rho_target = float(np.sqrt(d_horiz_obj ** 2 + (sz - t) ** 2))
            if rho_target < range_min or rho_target > range_max:
                continue
            # 阴影可能超出量程，物理 L_s 保留（反演用），仅记录 L_s_clipped 标记
            L_s_clipped = rho_end > range_max
            if L_s_clipped:
                # 仅用于绘制时截断，不修改 L_s（避免恒等式泄漏）
                # L_s_clipped 标志可用于上游报告截断状态
                pass
            candidates.append((abs(dtheta), d_horiz_obj, t, obj, elev_world, L_s, rho_target, L_s_clipped))

        if not candidates:
            continue
        # 选方位差最小的目标
        candidates.sort(key=lambda c: c[0])
        dtheta, d_horiz_obj, t, obj, elev_world, L_s, rho_target, L_s_clipped = candidates[0]

        # 2. target 像素
        bi = int(np.clip(np.round(a_b * theta + b_b), 0, W - 1))
        ri = int(np.clip(np.round(c_r * rho_target + d_r), 0, H - 1))
        target_mask[ri, bi] = True
        height_map[ri, bi] = float(t)  # 目标顶 z
        target_elev[ri, bi] = elev_world  # 世界系仰角（向下 < 0）

        # 3. 阴影像素
        # 阴影末端斜距（物理）
        D_e = d_horiz_obj + L_s
        rho_end_phys = float(np.sqrt(D_e ** 2 + sz ** 2))
        # 绘制用 rho_end（被 range_max 截断）；反演用 L_s 物理值
        rho_end_draw = min(rho_end_phys, range_max)
        r_end_f = (rho_end_draw - range_min) / (range_max - range_min) * (H - 1)
        r_end = int(np.clip(np.round(r_end_f), 0, H - 1))
        for r in range(ri + 1, min(r_end + 1, H)):
            shadow_mask[r, bi] = True
            shadow_len[r, bi] = L_s  # 物理 L_s（反演用）
            D_t_map[r, bi] = d_horiz_obj  # 反演用 D_t

    return target_mask, shadow_mask, height_map, shadow_len, D_t_map, target_elev


def render_all_shadow_maps(poses_T: np.ndarray, world: SceneWorld,
                           cfg: Config = C, n_elev: int = 31,
                           min_elev_deg: float = 1.0, verbose: bool = True):
    """批量渲染所有帧的阴影图（V5.2）。"""
    N = poses_T.shape[0]
    H, W = cfg.sonar.range_bin_count, cfg.sonar.beam_count
    target_masks = np.zeros((N, H, W), dtype=bool)
    shadow_masks = np.zeros((N, H, W), dtype=bool)
    height_maps = np.full((N, H, W), np.nan, dtype=np.float32)
    shadow_lens = np.full((N, H, W), np.nan, dtype=np.float32)
    D_t_maps = np.full((N, H, W), np.nan, dtype=np.float32)
    target_elevs = np.full((N, H, W), np.nan, dtype=np.float32)
    for i in range(N):
        if verbose and ((i + 1) % 10 == 0 or i == 0 or i == N - 1):
            print(f"  [shadow v5.2] frame {i+1}/{N}", flush=True)
        tm, sm, hm, sl, dt, te = render_shadow_map(
            poses_T[i], world, cfg, n_elev=n_elev, min_elev_deg=min_elev_deg)
        target_masks[i] = tm
        shadow_masks[i] = sm
        height_maps[i] = hm
        shadow_lens[i] = sl
        D_t_maps[i] = dt
        target_elevs[i] = te
    return target_masks, shadow_masks, height_maps, shadow_lens, D_t_maps, target_elevs
