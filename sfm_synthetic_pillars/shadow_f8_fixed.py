"""
F-8a/b/c 修正版阴影渲染 —— 消除三处缺陷
========================================

原 `shadow.py` 的问题（`审计_20260906_阴影反演恒等式与孔径未裁剪.md`）：

| 编号 | 缺陷 | 本模块的修正 |
|---|---|---|
| B2 | 仰角孔径检查用**世界系**角度对比**体系**边界，缺 pitch 变换。θ_p=19° 时把孔径中心的目标判成出界 | `elev_body = arctan2(P_b[2], hypot(P_b[0],P_b[1]))`，`P_b = R_wb^T (P_w − t_wb)` |
| B1 | 阴影足迹填充无孔径检查，未照亮区被当成阴影（旧构型下 91% 的"阴影"像素如此） | 逐距离门检查海底是否在体系孔径内；**未照亮**与**被遮挡**分成两个掩码 |
| B3 | `shadow_len` / `D_t_map` 逐像素写解析真值 ⇒ 反演成代数恒等式 | **不再输出解析 L_s / D_t**；改由 `measure_shadow_far_edge()` 从掩码量测，`D_t` 由 ★I(BA) 外部提供 |

设计原则（C7）：
    渲染只产出**传感器能观测到的东西**（掩码、强度）。
    任何解析几何量若要落盘，一律放进 `gt/` 且**禁止**被反演路径读取。
"""
from __future__ import annotations
import numpy as np
from typing import Tuple, NamedTuple

from config import Config, C, SonarCfg
from world import SceneWorld, Pillar, Cube, Sphere
from shadow import (_beam_grid_rad, _range_grid, _object_target_z,
                    _object_floor_z, _object_top_z_and_footprint)


# ============================================================
# 几何工具
# ============================================================

def elev_body(P_w, T_wb) -> float:
    """体系俯角（B2 修正的核心）。P_w 世界点，T_wb 4x4 位姿。"""
    R = T_wb[:3, :3]
    t = T_wb[:3, 3]
    P_b = R.T @ (np.asarray(P_w, dtype=float) - t)
    return float(np.arctan2(P_b[2], np.hypot(P_b[0], P_b[1])))


def floor_point_at_slant(theta_w: float, rho: float, t_wb, floor_z: float = 0.0):
    """沿方位 theta_w（世界系）、斜距 rho 的海底点。无解返回 None。"""
    dz = floor_z - float(t_wb[2])
    d_h2 = rho * rho - dz * dz
    if d_h2 <= 0:
        return None
    d_h = np.sqrt(d_h2)
    return np.array([t_wb[0] + d_h * np.cos(theta_w),
                     t_wb[1] + d_h * np.sin(theta_w),
                     floor_z])


class ShadowRender(NamedTuple):
    """渲染输出。**注意：不含解析 L_s / D_t**（B3）。"""
    target_mask: np.ndarray      # (H,W) 目标高光
    shadow_mask: np.ndarray      # (H,W) 被遮挡且该门海底本应可见 ⇒ 真阴影
    unlit_mask: np.ndarray       # (H,W) 该门海底不在孔径内 ⇒ 未照亮（非阴影）
    floor_mask: np.ndarray       # (H,W) 该门海底可见且未被遮挡 ⇒ 有回波
    target_elev_body: np.ndarray  # (H,W) 目标高光处的**体系**俯角（可观测量）


def render_shadow_map_fixed(T_wb: np.ndarray, world: SceneWorld,
                            cfg: Config = C,
                            azim_pad: float = 0.0) -> ShadowRender:
    """
    单帧渲染（F-8a 修正版）。

    与原 `render_shadow_map` 的接口差异：
      - 返回 NamedTuple，且**不返回** shadow_len / height_map / D_t_map
      - 新增 unlit_mask / floor_mask，把"未照亮"与"被遮挡"分开
      - 仰角判定全部在体系下做
      - 方位容差 azim_pad 默认 0（中心射线模型），原码硬编码 0.5°

    Args:
        azim_pad: 方位容差（rad）。0 = 中心射线模型（与暴力射线法一致）。
                  若要模拟波束有限宽度，传半个波束宽度，但需同时调整校核基准。
    """
    sonar = cfg.sonar
    beams_rad = _beam_grid_rad(sonar)
    rngs_m = _range_grid(sonar)
    H, W = sonar.range_bin_count, sonar.beam_count

    el_lo = np.deg2rad(sonar.fov_elevation_deg[0])
    el_hi = np.deg2rad(sonar.fov_elevation_deg[1])

    R_wb = T_wb[:3, :3]
    t_wb = T_wb[:3, 3]
    sx, sy, sz = float(t_wb[0]), float(t_wb[1]), float(t_wb[2])

    target_mask = np.zeros((H, W), dtype=bool)
    shadow_mask = np.zeros((H, W), dtype=bool)
    unlit_mask = np.zeros((H, W), dtype=bool)
    floor_mask = np.zeros((H, W), dtype=bool)
    target_elev = np.full((H, W), np.nan, dtype=np.float32)

    pm = sonar.pixel_map if sonar.pixel_map.get("beam", {}).get("a", 0) != 0 else None
    if pm is None:
        from config import finalize_pixel_mapping
        finalize_pixel_mapping(cfg)
        pm = sonar.pixel_map
    a_b, b_b = pm["beam"]["a"], pm["beam"]["b"]
    c_r, d_r = pm["range"]["c"], pm["range"]["d"]
    range_min, range_max = sonar.range_min_m, sonar.range_max_m

    # 波束方位在**体系**下给出；换到世界系需加 yaw
    yaw_w = float(np.arctan2(R_wb[1, 0], R_wb[0, 0]))

    for col, theta_b in enumerate(beams_rad):
        theta_w = theta_b + yaw_w

        # ---- 1. 落在该波束方位内的所有物体（**不做孔径过滤**）
        #     遮挡与"顶部是否在孔径内"无关：物体挡光就是挡光。
        #     孔径只决定"我们能否看见它的高光"（第 2 步）。
        in_beam = []          # (|dθ|, d_h, t_top, ρ_top)
        for obj in world.all_objects:
            t_top = _object_target_z(obj)
            z_flr = _object_floor_z(obj)
            if t_top <= z_flr or t_top >= sz:
                continue
            if not isinstance(obj, (Pillar, Cube, Sphere)):
                continue
            cx, cy = obj.cx, obj.cy
            dx, dy = cx - sx, cy - sy
            d_h = float(np.hypot(dx, dy))
            if d_h < 1e-3:
                continue
            th_obj = float(np.arctan2(dy, dx))
            dth = (th_obj - theta_w + np.pi) % (2 * np.pi) - np.pi
            r_xy = float(_object_top_z_and_footprint(obj)[4])
            # 中心射线模型：物体在该波束内 ⇔ 波束中心射线穿过物体。
            # 原 shadow.py 用硬编码 0.5° 填充，比半个波束间距（30°/128/2=0.117°）
            # 大 4 倍，会把阴影画到几何上不该有的波束里（W6 抽检 25/480 不一致）。
            # 波束有限宽度导致的边缘模糊是另一回事，不应混入遮挡判定。
            if abs(dth) > np.arctan2(r_xy, d_h) + azim_pad:
                continue
            # 轮廓的近/远边缘水平距（沿该波束中心射线穿过水平圆盘的弦）
            # W6 抽检发现：只用中心 d_h 判遮挡会漏掉"射线被远边缘挡住"的情形，
            # 且该简化恰与"点目标在 D_t"的反演假设一致 ⇒ 误差相互抵消（自证）。
            # 精确解：d = d_h·cos(dθ) ± sqrt(r² − d_h²sin²(dθ))
            s_ = d_h * np.sin(dth)
            disc = r_xy ** 2 - s_ ** 2
            if disc < 0:
                continue                      # 中心射线不穿过该圆盘
            half = float(np.sqrt(disc))
            base = d_h * np.cos(dth)
            d_near = base - half              # 近边缘（leading edge）
            d_far = base + half               # 远边缘（决定阴影长度）
            # 高光在 leading edge 顶部（Aykin：只有 leading edge 可靠）
            P_lead = np.array([sx + d_near * np.cos(theta_w),
                               sy + d_near * np.sin(theta_w), t_top])
            in_beam.append((abs(dth), d_near, d_far, t_top,
                            float(np.linalg.norm(P_lead - t_wb)),
                            elev_body(P_lead, T_wb)))

        bi = int(np.clip(np.round(a_b * theta_b + b_b), 0, W - 1))

        # ---- 2. 目标高光：仅当顶部在**体系**孔径内且在量程内（B2 修正）
        if in_beam:
            in_beam.sort(key=lambda c: c[0])
            _, d_near, d_far, t_top, rho_t, eb = in_beam[0]
            if (el_lo - 1e-3 <= eb <= el_hi + 1e-3
                    and range_min <= rho_t <= range_max):
                ri = int(np.clip(np.round(c_r * rho_t + d_r), 0, H - 1))
                target_mask[ri, bi] = True
                target_elev[ri, bi] = eb

        # ---- 3. 逐距离门判定：未照亮 / 被遮挡 / 有回波（B1 修正）
        for r, rho in enumerate(rngs_m):
            Pf = floor_point_at_slant(theta_w, float(rho), t_wb)
            if Pf is None:
                unlit_mask[r, bi] = True          # 斜距 < 高度，物理上无海底
                continue
            ebf = elev_body(Pf, T_wb)
            if ebf < el_lo - 1e-9 or ebf > el_hi + 1e-9:
                unlit_mask[r, bi] = True          # 海底不在孔径内 ⇒ 未照亮
                continue
            # 该门海底在孔径内：射线是否被遮挡？
            # 射线 sonar→海底点(水平距 D)，在水平距 x 处高度 z(x)=sz(1−x/D)。
            # 对有限尺寸物体，决定遮挡的是**轮廓远边缘** d_far（不是中心 d_h）：
            # 射线只要在 [d_near, d_far] 内任一点低于顶部即被挡，而 z(x) 单调递减，
            # 故最容易被挡的是 x=d_far。
            D_floor = float(np.hypot(Pf[0] - sx, Pf[1] - sy))
            blocked = False
            for _, d_near, d_far, t_top, _, _ in in_beam:
                if D_floor <= d_near:
                    continue          # 射线还没到物体，不可能被它挡
                # 射线在物体水平跨度 [d_near, min(d_far, D)] 内的最低点：
                # z(x)=sz(1−x/D) 单调递减 ⇒ 最低点在 x = min(d_far, D)。
                # 注意 D 落在足迹内（d_near<D<d_far）时也会被挡 ——
                # 首版写成 `if D_floor <= d_far: continue` 漏掉了这一段，
                # 被 W6 暴力射线校核抓出（阴影近端 9/480 不一致）。
                x_test = min(d_far, D_floor)
                z_ray = sz * (1.0 - x_test / D_floor)
                if z_ray < t_top:
                    blocked = True
                    break
            if blocked:
                shadow_mask[r, bi] = True         # 真阴影
            else:
                floor_mask[r, bi] = True          # 有回波

    return ShadowRender(target_mask, shadow_mask, unlit_mask, floor_mask, target_elev)


# ============================================================
# F-8b：从掩码量测阴影远端（禁止读解析值）
# ============================================================

def measure_shadow_far_edge(shadow_col: np.ndarray, floor_col: np.ndarray,
                            rngs_m: np.ndarray,
                            intensity_col: np.ndarray | None = None,
                            sub_bin: bool = True) -> float:
    """
    量测单列（单波束）阴影的**远端**斜距 ρ_end。

    定义：阴影→有回波 的最后一次跳变位置。
    亚 bin：若给强度，用跳变两侧强度做线性插值定位半幅点；
            否则取两 bin 中点（等价 0.5 bin 分辨率）。

    返回 NaN 表示该列量不到远端（阴影未在孔径内结束）。
    """
    sh = np.asarray(shadow_col, dtype=bool)
    fl = np.asarray(floor_col, dtype=bool)
    if not sh.any():
        return float("nan")
    idx = np.where(sh)[0]
    last = idx.max()
    # 远端必须紧接一个有回波的门，否则说明阴影是被孔径/量程截断的
    nxt = last + 1
    while nxt < len(fl) and not (fl[nxt] or sh[nxt]):
        nxt += 1                      # 跳过中间的 unlit 门
    if nxt >= len(fl) or not fl[nxt]:
        return float("nan")           # 远端不可测
    if not sub_bin:
        return float(rngs_m[nxt])
    if intensity_col is None:
        return float(0.5 * (rngs_m[last] + rngs_m[nxt]))
    # 强度半幅插值
    I0 = float(intensity_col[last])
    I1 = float(intensity_col[nxt])
    if abs(I1 - I0) < 1e-12:
        return float(0.5 * (rngs_m[last] + rngs_m[nxt]))
    f = (0.5 * (I0 + I1) - I0) / (I1 - I0)
    f = float(np.clip(f, 0.0, 1.0))
    return float(rngs_m[last] + f * (rngs_m[nxt] - rngs_m[last]))


# ============================================================
# F-8c：D_t 由 ★I(BA) 提供，反演不再自造 D_t
# ============================================================

def invert_height_from_far_edge(rho_end: float, D_t: float, z_s: float,
                                floor_z: float = 0.0) -> float:
    """
    h = z_s·(1 − D_t/D_e)，其中
      D_e = sqrt(ρ_end² − z_s²)   ← 由量测的远端斜距换算（**观测量**）
      D_t                          ← 由 ★I(BA) 的地标水平位置给出（**上游输入**）
      z_s                          ← 由 ★I(BA) 的位姿给出（**上游输入**）

    与旧路径的区别：ρ_end 是量测的，D_t 来自独立信息源，
    二者都不是从 h 反算的 ⇒ 不构成恒等式。
    """
    zs = float(z_s) - float(floor_z)
    if not np.isfinite(rho_end) or rho_end <= abs(zs):
        return float("nan")
    D_e = np.sqrt(rho_end ** 2 - zs ** 2)
    if D_e <= 0 or D_t <= 0:
        return float("nan")
    return float(zs * (1.0 - D_t / D_e))


def sigma_h_from_far_edge(rho_end: float, D_t: float, z_s: float,
                          sigma_rho: float, sigma_Dt: float,
                          sigma_zs: float, floor_z: float = 0.0) -> float:
    """σ_h 一阶传播（各项独立）。"""
    zs = float(z_s) - float(floor_z)
    if not np.isfinite(rho_end) or rho_end <= abs(zs):
        return float("nan")
    D_e = np.sqrt(rho_end ** 2 - zs ** 2)
    if D_e <= 0 or D_t <= 0:
        return float("nan")
    # h = zs(1 − D_t/D_e),  D_e = sqrt(ρ² − zs²)
    dDe_drho = rho_end / D_e
    dh_dDe = zs * D_t / D_e ** 2
    dh_drho = dh_dDe * dDe_drho
    dh_dDt = -zs / D_e
    dDe_dzs = -zs / D_e
    dh_dzs = (1.0 - D_t / D_e) + zs * D_t / D_e ** 2 * dDe_dzs
    return float(np.sqrt((dh_drho * sigma_rho) ** 2
                         + (dh_dDt * sigma_Dt) ** 2
                         + (dh_dzs * sigma_zs) ** 2))


def render_all_fixed(poses_T: np.ndarray, world: SceneWorld,
                     cfg: Config = C, verbose: bool = True):
    """多帧渲染。返回 (target_masks, shadow_masks, unlit_masks, floor_masks, target_elevs)。"""
    N = len(poses_T)
    H, W = cfg.sonar.range_bin_count, cfg.sonar.beam_count
    tm = np.zeros((N, H, W), dtype=bool)
    sm = np.zeros((N, H, W), dtype=bool)
    um = np.zeros((N, H, W), dtype=bool)
    fm = np.zeros((N, H, W), dtype=bool)
    te = np.full((N, H, W), np.nan, dtype=np.float32)
    for i in range(N):
        r = render_shadow_map_fixed(poses_T[i], world, cfg)
        tm[i], sm[i], um[i], fm[i], te[i] = (r.target_mask, r.shadow_mask,
                                             r.unlit_mask, r.floor_mask,
                                             r.target_elev_body)
        if verbose and (i + 1) % 20 == 0:
            print(f"    渲染 {i+1}/{N}")
    return tm, sm, um, fm, te
