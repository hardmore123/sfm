# S4 低 SNR

**目录**：`S4_low_snr/`  **类别**：`可行`

## 用途

speckle 0.35 + 噪声底 55dB，CFAR 门限验证

## 构型（§7.1）

- z_s = 4.5 m
- ρ_max = 25.0 m
- θ_p = 18°
- heave = 1.2 m
- forward = 4.0 m
- speckle σ = 0.35
- 噪声底 = 55 dB

## 场景目标

- 柱: [2.5] m
- 立方: [] m
- 球: [] m
- h_avg = 2.50 m, d_avg = 10.00 m

## 可反演性（T0.9 判据）

- 期望：可反演
- 实测：可反演（匹配）
- h_max = 4.50 m（实际 h_avg = 2.50 m）
- elev_top = -11.3°
- L_s = 12.50 m（被截断：False）

## 数据规模

- 帧数: 20, 关键帧: 5
- 目标像素: 140, 阴影像素: 35,196
- GT 表面点: 1,500

## GT 质量（T0.10 验收）

- max_dist_to_analytic: 0.0000 m（阈值 1e-2 m）
- max_normal_error: 0.000000 rad（阈值 1e-4 rad）
- std/mean_nn: 0.644（阈值 0.3）
- 验收: PARTIAL

## 反演精度（T0.7 + T0.8 验收）

- V2 精确式 MAE: 0.0 cm（验收：≤5 cm 且非零）
- V1 简化式 MAE: None cm（对照）

## 文件清单

- `gt/poses_gt.npy` (N, 4, 4) - 真值位姿
- `gt/surface_points.npy` (M, 3) - T0.10 GT 表面点
- `gt/surface_normals.npy` (M, 3) - T0.10 GT 表面法向
- `gt/sonar_images.npy` (N, H, W) - 渲染声呐图
- `gt/target_masks.npy` / `shadow_masks.npy` - 目标/阴影掩码
- `gt/height_gt_maps.npy` - 目标高度真值（仅 target_mask 处有值）
- `gt/D_t_map.npy` - 声呐到目标底部水平距离
- `innovation2/height_inverted.npy` - V2 精确反演高度
- `innovation2/sigma_height.npy` - 不确定度
- `innovation2/height_inverted_v1.npy` - V1 简化反演（对照）
- `meta.json` - 完整摘要
