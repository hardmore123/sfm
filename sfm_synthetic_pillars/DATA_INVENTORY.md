# 数据资产清单 — F:\sfm\sfm_synthetic_pillars

> **盘点时间**：2026-09-03 22:03
> **工作区**：`F:\sfm\sfm_synthetic_pillars`
> **总规模**：4,696 文件 / 14.30 GB

---

## 〇、一图总览

```
F:\sfm\sfm_synthetic_pillars\        4,696 files / 14.30GB
├── big_paper_scene_set/              3,262 files / 5.23GB    ← 16 个场景
│   ├── 01_simple_single_pillar/                  469.3MB
│   ├── 01_simple_single_pillar_v1_buggy/         281.8MB  ⚠️ 旧版（bug 未修复）
│   ├── 02_simple_two_pillars/                    469.4MB
│   ├── 03_simple_cube/                           234.7MB
│   ├── 04_sphere_target/                         234.7MB
│   ├── 05_diverse_shapes/                        234.9MB
│   ├── 06_dense_pillars_16/                      235.8MB
│   ├── 07_high_resolution/                       703.8MB
│   ├── 08_low_resolution/                        147.0MB
│   ├── 09_narrow_elevation/                      234.6MB
│   ├── 10_wide_elevation/                        234.7MB
│   ├── 11_seafloor_with_rubble/                  234.9MB
│   ├── 12_multipath_heavy/                       234.8MB
│   ├── 13_circular_trajectory/                   469.4MB
│   ├── 14_zigzag_trajectory/                     469.9MB
│   ├── 15_speckle_heavy/                         235.2MB
│   └── 16_low_snr_extreme/                       235.1MB
│
├── big_paper_sim/                    1,101 files / 8.43GB    ← 旧 multi_mode 模拟数据
│
├── innov2_ablations/                 281 files / 0.64GB     ← 6.1 消融数据
│   └── 02_forward/                                  234.4MB
│
├── *.py (30 个核心脚本)              0.20MB
└── *.md (8 个报告)                   0.07MB
```

---

## 一、按文件类型分类

| 扩展名 | 数量 | 大小 | 用途 |
|--------|------|------|------|
| **.npy** | 2,401 | **14.29GB** (99.9%) | 数值数据（gt 轨迹、BA 输入输出、阴影掩码、高度反演） |
| **.png** | 1,980 | 3.2MB | 语义分割掩码（背景/目标/阴影三分类） |
| **.csv** | 112 | 10.7MB | 时序数据（IMU/DVL/odom/tracks/segmentation meta） |
| **.py** | 30 | 0.20MB | Python 代码 |
| **.ply** | 22 | 0.2MB | 3D 重建点云（Open3D 格式） |
| **.md** | 8 | 0.07MB | 报告（WORK_LOG/DATA_INVENTORY/RESULTS 等） |
| **.json** | 56 | 0.1MB | 元数据（meta/inversion_stats/all5_results） |
| **.yaml** | 23 | <0.1MB | 传感器标定 |
| **.txt** | 44 | <0.1MB | 可观测性报告、运行日志 |

---

## 二、每个场景的标准子目录结构（7 类）

每个 `big_paper_scene_set/<scene_name>/` 下都有相同的 7 个子目录：

```
<scene_name>/
├── meta.json               场景元数据（运动模式、统计、反演精度）
├── README.md               场景说明（用途、参数、注意事项）
│
├── input/                  BA 优化输入（噪声注入后的"测量值"）
│   ├── landmarks_final.npy    (M, 3) float64    三维路标初值
│   ├── poses_est.npy          (K, 4, 4) float64  K 个关键帧位姿初值
│   ├── pose_frame_ids.npy     (K,) int64         关键帧在原始 120 帧中的索引
│   ├── odom_rel.csv           (K-1, 13)          关键帧间相对位姿（含 σ）
│   ├── tracks.csv             (N_obs, 10)        跨帧观测关联（含 beam/range 索引 + σ）
│   └── sensor_calib.yaml                       声呐内外参标定
│
├── gt/                     Ground Truth（仿真真值，无噪声）
│   ├── landmarks_gt.npy       (M, 3) float64
│   ├── poses_gt.npy           (N, 4, 4) float64  N=120 帧完整位姿
│   └── poses_keyframe_gt.npy  (K, 4, 4) float64  关键帧真值
│
├── innovation1/           创新一·鲁棒 BA 输出
│   ├── poses_optimized.npy        (K, 4, 4)       优化后位姿
│   ├── landmarks_optimized.npy    (M, 3)          优化后路标
│   ├── confidence.npy             (M,)            置信度
│   ├── well_mask.npy              (M,) bool       λ3/λ2 > 0.05 的 well-constrained 标记
│   ├── lambda3_per_lm.npy         (M,)            可观测性 λ3
│   ├── lambda_eigvals.npy         (M, 3)          完整特征值
│   ├── normals.npy                (M, 3)          法向量（表面重建用）
│   ├── observability_report.txt                   可观测性文字报告
│   └── optimized_with_normals.ply                 带法向的 3D 点云
│
├── innovation2/           创新二·阴影高度反演输出
│   ├── height_inverted.npy    (N, H, W) float32   反演高度 (m)
│   ├── sigma_height.npy       (N, H, W) float32   高度不确定度 (m)
│   ├── shadow_masks.npy       (N, H, W) bool      阴影掩码
│   ├── target_masks.npy       (N, H, W) bool      目标掩码
│   └── inversion_stats.json                      {n_inverted, z_err, σ_h}
│
├── imu/                   IMU 仿真数据
│   └── imu_data.csv            (N_imu, 7)         t_s, gx,gy,gz, ax,ay,az
│
├── dvl/                   DVL 仿真数据
│   └── dvl_data.csv            (N_dvl, 5)         t_s, vx,vy,vz
│
└── segmentation_data/     ViT 语义分割训练数据
    ├── images/                 (N, 1) int64     placeholder（实际图像在 PNG）
    ├── masks/                  (N, H, W) PNG    三分类掩码 (0=bg, 1=target, 2=shadow)
    ├── meta.csv                (N, 7)           frame_id, paths, n_target, n_shadow
    └── classes.txt                             类别名：background, target, shadow
```

---

## 三、关键文件 Schema 详细说明

### 3.1 仿真约定（全局）

- **声呐坐标系**：`x_fwd, y_left, z_up`（与 `ba_optimize.py` 的 `euler_to_matrix(Rz·Ry·Rx)` 一致）
- **位姿矩阵**：`T_wb`（4×4 homogeneous，body→world）
- **欧拉角顺序**：Rz(yaw) · Ry(pitch) · Rx(roll)
- **默认传感器参数**：`range_max_m=6.0`, `fov_azimuth_deg=(-65, 65)`, `fov_elevation_deg=(-17, 17)`
- **噪声**：`σ_θ=0.2°` (0.0035 rad), `σ_ρ=0.005m`
- **像素映射**：`beam = a·θ + b`, `range = c·ρ + d`（a/b/c/d 由 `calibrate_pixels` 自动拟合）

### 3.2 `meta.json` 完整字段

```json
{
  "motion_mode": "general" | "forward" | "yaw_y" | "mixed",
  "seed": 102,
  "stats": {
    "n_pillars": 2,                    // 柱子/几何体数
    "n_landmarks": 60,                 // 路标总数
    "n_frames": 120,                   // 仿真总帧数
    "n_keyframes": 10,                 // 关键帧数
    "n_observations": 2636,            // 声呐观测总数
    "n_obs_keyframes": 383,            // 关键帧上观测数
    "n_tracks": 60,                    // 关联后的轨迹数
    "n_target_pixels_total": 9281,     // 全部帧目标像素和
    "n_shadow_pixels_total": 0         // 全部帧阴影像素和（修复后>>0）
  },
  "innovation2_stats": {
    "n_inverted_pixels": 0,
    "median_abs_error_m": null,        // 高度反演中位误差 (m)
    "mean_abs_error_m": null,
    "sigma_h_median_m": null           // 中位高度不确定度
  },
  "innovation1_stats": {
    "n_well_constrained": 7,           // λ3/λ2 > 0.05 的 lm 数
    "lambda3_median": 89.79,
    "lambda3_min": 1e-9,
    "ba_final_rms_px": 0.67            // BA 收敛后的重投影 RMS (像素)
  },
  "output_files": { "input": [...], "gt": [...], ... }
}
```

### 3.3 `input/tracks.csv` 列定义

```
frame_id, timestamp, track_id,
theta_rad, rho_m,             // 极坐标观测
confidence,
beam_index, range_index,      // 像素坐标
sigma_theta, sigma_rho        // 观测噪声 σ
```

### 3.4 `input/sensor_calib.yaml` 关键字段

```yaml
frames: 1
pose_convention: body_to_world
euler_order: Rz_Ry_Rx
angle_unit: rad
length_unit: m
T_sensor_body:                  // 声呐到 body 的外参
  - [1, 0, 0, 0]
  - [0, 1, 0, 0]
  - [0, 0, 1, 0]
  - [0, 0, 0, 1]
beam_pixel_calib: {a, b}        // 像素-角度线性映射
range_pixel_calib: {c, d}       // 像素-距离线性映射
```

### 3.5 `innovation2/height_inverted.npy`

- shape: `(N_frames, H_range, W_beam)` = `(120, 800, 512)` 或 `(120, 400, 512)`（02_forward）
- dtype: `float32`
- 含义：每个像素位置反演得到的目标高度 (m)，NaN 表示无效
- 反演公式：`h = L_s × |tan(elev)|`
  - L_s = 阴影长度（m）
  - elev = 仰角（rad，z 朝上时向上为正）
- 修复后 01 场景 median_err=0.00cm，mean_err=28.99cm

### 3.6 `innovation2/shadow_masks.npy` & `target_masks.npy`

- shape: `(N_frames, H_range, W_beam)`，dtype: `bool`
- `target_masks[r, col] = True` 表示该像素是目标命中
- `shadow_masks[r, col] = True` 表示该像素是阴影区域
- 每个场景的 `innovation2/inversion_stats.json` 记录统计

---

## 四、16 场景 + 02_forward 数据总览

| # | 场景 | lm | kf | shadow_px | z_err (median) | shadow 状态 |
|---|------|-----|-----|-----------|----------------|-------------|
| 01 | simple_single_pillar | 30 | 6 | 1,996,713 | **0.00cm** | ✅ shadow fix 后 |
| 01_v1 | _v1_buggy (旧版) | 30 | 6 | 3,714,878 | 126.49cm | ⚠️ bug 修复前，建议删除 |
| 02 | simple_two_pillars | 60 | 10 | 4,622,212 | **0.00cm** | ✅ shadow fix 后 |
| 03 | simple_cube | 30 | 12 | 10,342,472 | 121.81cm | ❌ 待重新生成（修复后） |
| 04 | sphere_target | 30 | 12 | 4,398,282 | **0.00cm** | ✅ 球本身无阴影，z_err 来自其他原因 |
| 05 | diverse_shapes | 150 | 12 | 4,780,684 | **0.00cm** | ✅ shadow fix 后 |
| 06 | dense_pillars_16 | 630 | 9 | 12,581,638 | 128.94cm | ❌ 待重新生成 |
| 07 | high_resolution | 240 | 12 | 9,110,522 | 136.96cm | ❌ 待重新生成 |
| 08 | low_resolution | 60 | 8 | 528,804 | 148.83cm | ❌ 待重新生成 |
| 09 | narrow_elevation | 60 | 12 | 3,507,830 | 152.19cm | ❌ 待重新生成 |
| 10 | wide_elevation | 60 | 12 | 3,532,540 | 148.90cm | ❌ 待重新生成 |
| 11 | seafloor_with_rubble | 200 | 12 | 4,001,316 | 133.42cm | ❌ 待重新生成 |
| 12 | multipath_heavy | 60 | 12 | 3,994,802 | 133.46cm | ❌ 待重新生成 |
| 13 | circular_trajectory | 30 | 9 | 3,006,726 | 122.63cm | ❌ 待重新生成 |
| 14 | zigzag_trajectory | 240 | 9 | 14,260,586 | 124.58cm | ❌ 待重新生成 |
| 15 | speckle_heavy | 240 | 12 | 6,372,707 | 129.06cm | ❌ 待重新生成 |
| 16 | low_snr_extreme | 240 | 12 | 5,458,336 | 58.11cm | ⚠️ 部分改善 |
| 02_fwd | forward (消融) | 120 | 15 | 351,671 | **0.00cm** | ✅ 重新设计后 |

**注意**：只有 01 / 02 / 05 是用 shadow fix 后重新生成的；其余 13 个场景的 z_err 还是 100+cm，需要重跑。

---

## 五、innov2_ablations/02_forward 详情

`02_forward` 是 6.1 仰角消融专用数据，配置和一般场景不同：

- **AUV 轨迹**：`forward` + `yaw ±28°`（z=2.6 恒定，sway=0，pitch=0）
- **柱子**：4 根 h=1.5m 沿路径（x=-3, -1, 1, 3），y=±0.5
- **目的**：模拟"z 完全不可观测 + 阴影可生成"场景，验证阴影先验必要性
- **声呐分辨率**：`range_bin_count=400`（节省磁盘，原 800）
- **文件清单**：
  - `gt/`: 120 帧完整位姿 + 120 路标 + 15 关键帧位姿
  - `innovation2/`: 120×400×512 height_inverted / sigma_height / shadow_masks / target_masks（共 234.4MB）
  - 其余同标准场景结构

---

## 六、big_paper_sim 子目录

`big_paper_sim/` 占 8.43GB，是早期 `multi_mode/` 模式生成的数据集（120 个 batch 文件 × 大量中间数据）。**目前未被大论文使用**，可考虑清理以释放磁盘空间。

- 估算：清理后可释放 8.43GB
- 保留建议：如不需要历史复现，可整目录 `shutil.rmtree('F:\\sfm\\sfm_synthetic_pillars\\big_paper_sim')`

---

## 七、清理与待办

### 7.1 立即可清理（已确认无用）
- `F:\sfm\sfm_synthetic_pillars\big_paper_scene_set\01_simple_single_pillar_v1_buggy\` — 281.8MB，旧版数据
  - 新版 `01_simple_single_pillar` 已用 shadow fix 重新生成
  - 保留作"bug 修复前后对比"参考；如不需要可删
- `F:\sfm\sfm_synthetic_pillars\big_paper_sim\` — 8.43GB，未被大论文使用

### 7.2 待重新生成（用 shadow fix）
- 03_simple_cube
- 06_dense_pillars_16
- 07_high_resolution
- 08_low_resolution
- 09_narrow_elevation
- 10_wide_elevation
- 11_seafloor_with_rubble
- 12_multipath_heavy
- 13_circular_trajectory
- 14_zigzag_trajectory
- 15_speckle_heavy
- 16_low_snr_extreme

预期：重新生成后 z_err 应大幅降低（参考 01 从 126cm → 0cm）

### 7.3 重要数据约束
- 16 场景的 gt 数据（`gt/landmarks_gt.npy` + `gt/poses_gt.npy`）都是**仿真真值**，用于评估 BA 精度
- `innovation2/height_inverted.npy` **含 NaN** 是正常的（无效像素）
- `input/tracks.csv` 是**加了噪声**的，不是真值
- 评估时用 `gt/` vs `innovation1/landmarks_optimized.npy` 对比

---

## 八、数据使用建议

### 8.1 论文图表数据来源

| 论文图/表 | 数据来源 |
|-----------|----------|
| Fig 5.x（场景示例） | `big_paper_scene_set/<scene>/meta.json` + `gt/landmarks_gt.npy` + `gt/poses_gt.npy`（可视化） |
| Tab 6.1（5 版本 BA 对比） | `run_all_5.py` 输出 + `all5_*.json` |
| Tab 6.2（6.1 消融） | `innov2_a_vs_b_v3.py` 输出 + `innov2_a_vs_b_v3_*_result.json` |
| Fig 6.x（高度反演可视化） | `innovation2/height_inverted.npy` + `gt/poses_gt.npy`（重投影） |
| Fig 7.x（语义分割） | `segmentation_data/masks/frame_*.png` + `meta.csv` |

### 8.2 复现实验的命令

```powershell
# 1) 重新生成 02_forward
cd F:\sfm\sfm_synthetic_pillars
python gen_02_forward_v2.py

# 2) 重新生成 01（验证 shadow fix 效果）
python -c "import sys; sys.path.insert(0, '.'); from scene_configs import make_simple_single_pillar; import big_paper_sim; cfg = make_simple_single_pillar(); big_paper_sim.generate_big_paper(out_dir='big_paper_scene_set/01_simple_single_pillar', motion_mode=cfg.traj.motion_mode, cfg=cfg)"

# 3) 跑 6.1 V3 消融
python innov2_a_vs_b_v3.py 01_simple_single_pillar
python innov2_a_vs_b_v3.py 02_simple_two_pillars 0.001
python innov2_a_vs_b_v3.py 16_low_snr_extreme

# 4) 5 版本 BA 对比
python run_all_5.py

# 5) 收集所有场景汇总
python collect_summary.py
```

### 8.3 关键文件绝对路径速查

| 内容 | 路径 |
|------|------|
| 入口 README | `F:\sfm\sfm_synthetic_pillars\README.md` |
| 工作日志 | `F:\sfm\sfm_synthetic_pillars\WORK_LOG.md` |
| 数据资产清单 | `F:\sfm\sfm_synthetic_pillars\DATA_INVENTORY.md`（本文件） |
| 6.1 消融报告 | `F:\sfm\sfm_synthetic_pillars\INNOV2_ABLATION_V4_REPORT.md` |
| 5 版本对比 | `F:\sfm\sfm_synthetic_pillars\ALL5_REPORT.md` |
| Shadow 修复核心 | `F:\sfm\sfm_synthetic_pillars\shadow.py` |
| 6.1 通用化消融 | `F:\sfm\sfm_synthetic_pillars\innov2_a_vs_b_v3.py` |
| 02_forward 生成 | `F:\sfm\sfm_synthetic_pillars\gen_02_forward_v2.py` |
| 16 场景配置 | `F:\sfm\sfm_synthetic_pillars\scene_configs.py` |
| 场景生成主入口 | `F:\sfm\sfm_synthetic_pillars\big_paper_sim.py` |
| BA 代码（兄弟） | `F:\sfm\BA代码\ba_optimize.py` |

---

*本清单由 inventory 脚本生成，时间 2026-09-03 22:03。后续每次数据有重大变更（重新生成、新增场景）时需更新。*
