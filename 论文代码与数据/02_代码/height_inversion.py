"""
声学阴影 → 目标高度/仰角反演 V2（精确正演式 + σ 传播）
========================================================

v1 公式（简化式）：
    L_shadow = h / tan(elev)
    h = L_shadow * tan(elev)
    **问题**：v1 用 launch elev 近似，**当范围变大时 v1 会高估 h**（T0.8 验收点）

v2 公式（精确正演式）—— 阶段表 §4 T0.8 验收要求：
    给定：
      z_s : 声呐到 floor 的高度
      h   : 目标高度（z_target - z_floor），h < z_s
      D_t : 声呐到目标底部（floor 投影）的水平距离
    几何关系（"目标垂直立于水平地面"经典模型）：
      声呐到目标顶部的仰角：elev = atan2(h - z_s, D_t)   （朝下，elev < 0）
      阴影长度（沿 hit 方向投到 floor 的水平距离）：
        L_s = h / |tan(elev)| = h * D_t / (z_s - h)   （z_s > h）
    ⇒ 整理：
      L_s * (z_s - h) = h * D_t
      L_s * z_s - L_s * h = h * D_t
      h * (D_t + L_s) = L_s * z_s
      ⇒ h = L_s * z_s / (D_t + L_s)
    这是**精确反演**（无近似）。等价于 h/z_s = L_s/(D_t + L_s) = 1 - D_t/D_e
    其中 D_e = D_t + L_s（声呐到阴影末端的水平距离）

**与 v1 对比**：
    v1: h_v1 = L_s * tan(elev_v1)       其中 elev_v1 = atan2(z_s - h, D_t)
    v2: h_v2 = L_s * z_s / (D_t + L_s)   显式精确
    偏差：v1 隐式用了真实 h（不能反演）—— v1 是循环定义
    v2 直接给出 h — 无循环

**σ 传播**（T0.8 + T0.5 要求）：
    σ_h² = (∂h/∂L_s)² σ_L² + (∂h/∂D_t)² σ_D² + (∂h/∂z_s)² σ_z²
    其中：
      ∂h/∂L_s = z_s * D_t / (D_t + L_s)² = (z_s - h) * D_t / z_s / (D_t + L_s)
                ≈ h/z_s · D_t/(D_t+L_s)  （数学校验：= h * D_t / (z_s*(D_t+L_s)) = h*z_s*D_t/(z_s²*(D_t+L_s)) 
                  错！重算：h = L_s*z_s/(D_t+L_s) ⇒ ∂h/∂L_s = z_s * (D_t + L_s - L_s) / (D_t+L_s)² = z_s * D_t / (D_t+L_s)²
      ∂h/∂D_t = -L_s * z_s / (D_t + L_s)² = -h * (D_t + L_s) / D_t · D_t / (D_t+L_s)² ... 
                简化为 = -L_s * z_s / (D_t + L_s)²
      ∂h/∂z_s = L_s / (D_t + L_s) = h / z_s
    关键：以前 v1 漏掉了 σ_z（声呐测深误差），导致 σ_h 偏小

接口：
  invert_height_precise(
      L_s_m, D_t_m, z_s_m,
      sigma_L_m=None, sigma_D_m=None, sigma_z_m=None
  ) -> (h_m, sigma_h_m)

  invert_height_from_shadow(...)  → 保留 v1 简化式（兼容旧调用）

  invert_height_from_shadow_pixels(...)  → 批量反演
"""

from __future__ import annotations
import numpy as np


def invert_height_precise(
    L_s_m: float | np.ndarray,
    D_t_m: float | np.ndarray,
    z_s_m: float | np.ndarray,
    sigma_L_m: float | None = None,
    sigma_D_m: float | None = None,
    sigma_z_m: float | None = None,
) -> tuple[float | np.ndarray, float | np.ndarray]:
    """
    精确反演：h = z_s - sqrt(2 D_t L_s + L_s²)

    参数:
      L_s_m:  阴影长度（米）
      D_t_m: 声呐到目标底部（floor 投影）的水平距离（米）
      z_s_m: 声呐到 floor 的高度（米）
      sigma_L_m: L_s 测量误差（默认 0.05m ≈ 5cm）
      sigma_D_m: D_t 测量误差（默认 0.05m）
      sigma_z_m: z_s 误差（默认 0.05m）
    """
    if sigma_L_m is None:
        sigma_L_m = 0.05
    if sigma_D_m is None:
        sigma_D_m = 0.05
    if sigma_z_m is None:
        sigma_z_m = 0.05

    # === 核心反演（精确式） ===
    # h = L_s * z_s / (D_t + L_s)
    denom = D_t_m + L_s_m
    h_m = L_s_m * z_s_m / np.maximum(denom, 1e-6)
    # 物理保护：h ∈ [0, z_s)
    h_m = np.clip(h_m, 0.0, np.maximum(z_s_m, 0.0))

    # === σ 传播（精确一阶 Taylor） ===
    # ∂h/∂L_s = z_s * D_t / (D_t + L_s)²
    # ∂h/∂D_t = -L_s * z_s / (D_t + L_s)²
    # ∂h/∂z_s = L_s / (D_t + L_s) = h / z_s
    denom_sq = np.maximum(denom ** 2, 1e-12)
    dh_dL = z_s_m * D_t_m / denom_sq
    dh_dD = -L_s_m * z_s_m / denom_sq
    dh_dz = L_s_m / np.maximum(denom, 1e-6)
    sigma_h_m = np.sqrt((dh_dL * sigma_L_m) ** 2 +
                        (dh_dD * sigma_D_m) ** 2 +
                        (dh_dz * sigma_z_m) ** 2)
    return h_m, sigma_h_m


def invert_height_from_shadow(
    shadow_length_m: float | np.ndarray,
    target_elev_rad: float | np.ndarray,
    sigma_shadow_m: float | None = None,
    sigma_elev_rad: float | None = None,
) -> tuple[float | np.ndarray, float | np.ndarray]:
    """
    V1 简化反演：h = L_s * |tan(elev)|。仅作兼容保留，**不推荐使用**。
    推荐用 invert_height_precise(L_s, D_t, z_s)。
    """
    if sigma_shadow_m is None:
        sigma_shadow_m = 0.05
    if sigma_elev_rad is None:
        sigma_elev_rad = np.deg2rad(1.0)
    tan_e = np.tan(target_elev_rad)
    h_m = shadow_length_m * np.abs(tan_e)
    abs_tan = np.abs(tan_e)
    d_h_d_L = abs_tan
    d_h_d_e = shadow_length_m * (1.0 + tan_e ** 2)
    sigma_h_m = np.sqrt((d_h_d_L * sigma_shadow_m) ** 2 +
                        (d_h_d_e * sigma_elev_rad) ** 2)
    return h_m, sigma_h_m


def invert_height_from_shadow_pixels(
    shadow_mask: np.ndarray,    # (H, W) bool
    shadow_len: np.ndarray,     # (H, W) float, NaN where no shadow
    target_elev: np.ndarray,    # (H, W) float, NaN where no target on beam
    sigma_shadow_m: float = 0.05,
    sigma_elev_rad: float = np.deg2rad(1.0),
    min_elev_deg: float = 1.0,
) -> tuple[np.ndarray, np.ndarray]:
    """
    批量反演（V1 简化版）。保留用于和 V2 精确版对比。
    """
    h_map = np.full_like(shadow_len, np.nan)
    sigma_h_map = np.full_like(shadow_len, np.nan)
    valid = shadow_mask & np.isfinite(shadow_len) & np.isfinite(target_elev)
    elev_abs = np.abs(np.rad2deg(target_elev))
    valid = valid & (elev_abs >= min_elev_deg)
    if not valid.any():
        return h_map, sigma_h_map
    h, sig = invert_height_from_shadow(
        shadow_len[valid], target_elev[valid],
        sigma_shadow_m, sigma_elev_rad)
    h_map[valid] = h
    sigma_h_map[valid] = sig
    return h_map, sigma_h_map


def invert_height_precise_from_pixels(
    shadow_mask: np.ndarray,    # (H, W) bool
    shadow_len: np.ndarray,     # (H, W) float, NaN where no shadow
    target_elev: np.ndarray,    # (H, W) float, NaN where no target on beam (V5.2 不再使用)
    D_t_map: np.ndarray,        # (H, W) float, 声呐到目标底部水平距离（米）
    z_s: float,                 # 声呐到 floor 的高度（米）
    sigma_L_m: float = 0.05,
    sigma_D_m: float = 0.05,
    sigma_z_m: float = 0.05,
) -> tuple[np.ndarray, np.ndarray]:
    """
    批量反演（V2 精确版）—— **推荐**。
    用 D_t + L_s + z_s 反演 h = L_s * z_s / (D_t + L_s)，不依赖 target_elev。
    target_elev 参数保留仅为兼容 v5.0 接口。
    """
    h_map = np.full_like(shadow_len, np.nan)
    sigma_h_map = np.full_like(shadow_len, np.nan)
    valid = (shadow_mask & np.isfinite(shadow_len)
             & np.isfinite(D_t_map) & (shadow_len > 0) & (D_t_map > 0))
    if not valid.any():
        return h_map, sigma_h_map
    L_s = shadow_len[valid]
    D_t = D_t_map[valid]
    z_s_arr = np.full_like(L_s, z_s)
    h, sig = invert_height_precise(
        L_s, D_t, z_s_arr,
        sigma_L_m=sigma_L_m, sigma_D_m=sigma_D_m, sigma_z_m=sigma_z_m)
    h_map[valid] = h
    sigma_h_map[valid] = sig
    return h_map, sigma_h_map


# --------------------- 与 Aykin 式手工阈值法的对比基线 ---------------------

def aykin_shadow_length_threshold(
    sonar_image: np.ndarray,
    target_mask: np.ndarray,
    beam_axis_theta: np.ndarray,
    elev_axis: np.ndarray,
    threshold_db: float = -6.0,
) -> np.ndarray:
    """Aykin & Negahdaripour 风格的阴影长度估计（V1 兼容）。"""
    H, W = sonar_image.shape
    img_db = 20 * np.log10(sonar_image + 1e-6)
    shadow_len = np.zeros((H, W), dtype=np.float32)
    sonar_cfg_range = np.linspace(0.2, 4.0, H)
    for col in range(W):
        if not target_mask[:, col].any():
            continue
        target_rows = np.where(target_mask[:, col])[0]
        t_row = target_rows[0]
        if t_row >= H - 2:
            continue
        target_db = img_db[t_row, col]
        for r in range(t_row + 1, H):
            if img_db[r, col] < target_db + threshold_db:
                shadow_len[r, col] = sonar_cfg_range[r] - sonar_cfg_range[t_row]
            else:
                break
    return shadow_len
