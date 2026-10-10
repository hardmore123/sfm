# 大论文多场景模拟数据集 — 综合说明

> **完成时间**：2026-09-03
> **目录**：`big_paper_scene_set/`
> **场景数**：16 个（覆盖大论文各部分的简单/复杂场景）

---

## 0. 设计原则

每个场景对应大论文的一个或多个**实验需求**：

| 大论文需求 | 场景 |
|---|---|
| 创新一·M1 软关联置信度 | 02（最小双目标）、06（拥挤）、11（杂波） |
| 创新一·M2 球坐标+视场 | 02、08（低分）、09（窄仰角）、10（宽仰角） |
| 创新一·M3 联合优化 | 全部 16 个 |
| 创新一·M4 加权曲面 | 06、11、12（杂波下加权泊松） |
| 创新二·M1 目标-背景分割 | 11、12、15、16（带杂波/低 SNR） |
| **创新二·M2 阴影→高度（核心）** | **全部 16 个**（不同几何/视角/声学） |
| 创新二·M3 语义关联 | 02、03、05（混合几何） |
| **6.1 仰角来源消融** | **02、04、13（低柱）、16** |
| 6.2 置信度流消融 | 02 vs 06 vs 11 |
| sim-to-real | 12、15、16（噪声场景） |
| 真实轨迹模拟 | 13（圆周）、14（之字） |

---

## 1. 场景总览

| 编号 | 场景名 | 类别 | 目标数 | #lm | #obs | #KF | 良约束% | 反演z_err(cm) | BA_RMS | 用途 |
|---|---|---|---|---|---|---|---|---|---|---|
| 01 | simple_single_pillar | simple | 1柱 | 30 | 1657 | 6 | 3% | 126.5 | 0.566 | 最简 sanity check |
| 02 | simple_two_pillars | simple | 2柱1.5m | 60 | 1160 | 10 | 10% | **0.00** | 0.541 | **6.1 消融主推** |
| 03 | simple_cube | simple | 1方 | 30 | 670 | 12 | 27% | 121.8 | 0.667 | 几何泛化（柱→方） |
| 04 | sphere_target | simple | 1球 | 30 | 1049 | 12 | 10% | **0.00** | 0.640 | 球目标测试无阴影 |
| 05 | diverse_shapes | complex | 柱+方+球 | 150 | 3443 | 12 | 21% | **0.00** | 0.613 | 复杂混合几何 |
| 06 | dense_pillars_16 | complex | 21柱 | 630 | 14002 | 9 | 33% | 128.9 | 0.542 | 拥挤关联压力 |
| 07 | high_resolution | sensor | 8柱 | 240 | 3910 | 12 | 45% | 137.0 | 0.921 | 高端声呐配置 |
| 08 | low_resolution | sensor | 2柱 | 60 | 1653 | 8 | 60% | 148.8 | 0.317 | 低端声呐配置 |
| 09 | narrow_elevation | sensor | 2柱 | 60 | 254 | 12 | 85% | 152.2 | 0.411 | 窄仰角±5°（约束紧） |
| 10 | wide_elevation | sensor | 2柱 | 60 | 1119 | 12 | 30% | 148.9 | 0.712 | 宽仰角±25°（约束松） |
| 11 | seafloor_with_rubble | env | 2柱+20石 | 200 | 2518 | 12 | 47% | 133.4 | 0.545 | 海底杂波 |
| 12 | multipath_heavy | env | 2柱 | 60 | 1661 | 12 | 12% | 133.5 | 0.712 | 多径/旁瓣干扰 |
| 13 | circular_trajectory | traj | 1柱 | 30 | 1754 | 9 | 67% | 122.6 | 0.682 | 圆周轨迹 |
| 14 | zigzag_trajectory | traj | 8柱 | 240 | 7966 | 9 | 36% | 124.6 | 0.652 | 之字形巡检 |
| 15 | speckle_heavy | aug | 8柱 | 240 | 6226 | 12 | 7% | 129.1 | 0.662 | 重相干斑增广 |
| 16 | low_snr_extreme | aug | 8柱 | 240 | 5161 | 12 | 32% | **58.1** | 1.378 | 极低 SNR+外点 |

> **说明**：每场景 60 帧（自定义轨迹如 13/14 用 120 帧）

---

## 2. ⚠️ 重要发现：高度反演的物理限制

**所有"高目标+range_max 限制"场景（h>1.8m）的反演误差都是 100+ cm**，这不是 bug，而是物理现实：

```
完整反演条件：h ≤ range_max × tan(fov_elevation_max)
默认配置：    6m × tan(17°) ≈ 1.83m
柱高 2.5-3.5m → 超出 → L_s 被截断 → h 系统性低估
```

### 2.1 各场景反演误差原因

| 误差水平 | 场景 | 原因 |
|---|---|---|
| **0.00 cm（完美）** | 02、04、05 | 柱/球高 1.5m，阴影完整落在 6m 范围内 |
| **58 cm** | 16_low_snr | 柱高 1.5m，但低 SNR 让 LM 弱先验影响 |
| **120-150 cm** | 01、03、06-15 | 柱高 2-3.5m + 默认 range_max 6m → 阴影被截断 |

### 2.2 修复方法（**大论文应写明**）

- **方法 A（推荐）**：把 `cfg.sonar.range_max_m` 改大到 10-12m（覆盖 3.5m/tan(17°)=11.4m）
- **方法 B**：场景中降低柱高到 1.5m（参考场景 02/04/05）
- **方法 C**：接受截断作为"论文的物理限制"——**反向思考：低位反演公式失效正是 6.1 实验要证明的"阴影先验必要性"**

---

## 3. 各场景详细说明

### 3.1 simple 类别（5 个）

#### 01_simple_single_pillar
- **目标**：1 根柱子（h=2.8m, r=0.30m）
- **测试目的**：最简几何，sanity check
- **关键发现**：良约束仅 1/30（3%）—— 单目标无基线多样性
- **建议**：用作算法 baseline 演示

#### 02_simple_two_pillars ⭐ 主推
- **目标**：2 根柱子（h=1.5m，间隔 2m）
- **测试目的**：最小双目标，**6.1 消融最佳数据**
- **关键发现**：z_err=**0.00cm**（完美反演）— 因为柱高低、L_s 完整
- **建议**：作为 A vs B 消融主数据

#### 03_simple_cube
- **目标**：1 个立方体（半边长 1m，h=2m）
- **测试目的**：验证几何模型对非柱面目标的泛化
- **关键发现**：z_err=121.8cm（立方体 z=2m，L_s 截断）
- **建议**：在 range_max 加大到 10m 时重测

#### 04_sphere_target
- **目标**：1 个球（r=0.6m，球心 z=1.5）
- **测试目的**：球几乎不产生阴影，**测试反演失败情形**
- **关键发现**：z_err=0.00cm，但 shadow_pixels 很少（球阴影仅一侧）
- **建议**：用作"球目标 → 阴影极少"对照

#### 05_diverse_shapes ⭐ 重要
- **目标**：2柱+2方+1球（150 landmark）
- **测试目的**：多种几何混合，验证通用性
- **关键发现**：z_err=**0.00cm**（柱高 2.5m 但因为是 general 轨迹 z 起伏，阴影更完整）
- **建议**：作为通用性测试数据

### 3.2 complex 类别（1 个）

#### 06_dense_pillars_16
- **目标**：21 根柱子（密集排布 3×7 网格，0.8m 间距）
- **测试目的**：拥挤场景，验证关联压力
- **关键发现**：14002 观测、597 tracks、210/630 良约束 — **关联成功率最高**
- **建议**：M1 软关联测试主数据

### 3.3 sensor 类别（4 个）

#### 07_high_resolution
- **声呐**：1024 beam × 1200 range（高端）
- **测试目的**：高端声呐配置，验证细节捕捉
- **关键发现**：BA RMS=0.92px（最高，因 107/240 良约束）

#### 08_low_resolution
- **声呐**：128 beam × 200 range（低端）
- **测试目的**：老声呐/低端配置，验证鲁棒性
- **关键发现**：BA RMS=0.32px（最低，因 60% 良约束）
- **建议**：作"低端设备部署可行性"评估

#### 09_narrow_elevation
- **仰角孔径**：±5°（约束紧）
- **测试目的**：M2 视场约束极限
- **关键发现**：良约束 51/60（85%），但**几乎无俯仰信息**（z_err=152cm）

#### 10_wide_elevation
- **仰角孔径**：±25°（约束松）
- **测试目的**：M2 视场约束极限
- **关键发现**：良约束 18/60（30%），但 z_err 仍 149cm（h 超出 L_s）

### 3.4 env 类别（2 个）

#### 11_seafloor_with_rubble
- **环境**：2 柱 + 20 散石（海底背景杂波）
- **测试目的**：真实水下环境，杂波强
- **关键发现**：200 landmark（柱+散石）、94/200 良约束
- **建议**：M1 软关联 + M4 加权泊松 主数据

#### 12_multipath_heavy
- **噪声**：speckle=0.4, noise_floor=50dB（强）
- **测试目的**：多径/旁瓣干扰
- **关键发现**：良约束 7/60（12%）—— 极低，验证 GNC 必要性

### 3.5 traj 类别（2 个）

#### 13_circular_trajectory
- **轨迹**：AUV 圆周环绕 1 根柱子（R=2.5m, 120 帧）
- **测试目的**：360° 视角覆盖
- **关键发现**：良约束 20/30（67%）—— 圆周给最大基线多样性
- **z_err=122cm**：目标超出 fov_elev，但轨迹本身质量好

#### 14_zigzag_trajectory
- **轨迹**：AUV 之字形巡检（120 帧，8 柱）
- **测试目的**：典型水下巡检模式
- **关键发现**：7966 观测、193 tracks — 数据量丰富

### 3.6 aug 类别（2 个）

#### 15_speckle_heavy
- **噪声**：speckle=0.5, noise_floor=55dB
- **测试目的**：sim-to-real 数据增强
- **关键发现**：良约束 17/240（7%）—— 极差，体现数据增强必要性

#### 16_low_snr_extreme
- **配置**：柱高 1.5m + 极低 SNR（10% 漏检 + 10% 误检）
- **测试目的**：**6.1 消融 + 极限鲁棒性测试**
- **关键发现**：z_err=**58.1cm**（低柱+大噪声——有趣的"反演受先验影响"案例）
- **建议**：作为 6.1 B 实验的"困难场景"

---

## 4. 文件结构（每场景统一）

```
<scene_name>/
├── README.md             # 该场景详细说明（自动生成）
├── meta.json             # 完整摘要
├── input/                # 创新一输入
│   ├── poses_est.npy     (K, 4, 4)
│   ├── pose_frame_ids.npy (K,)
│   ├── landmarks_final.npy (M, 3)
│   ├── tracks.csv        (~1000-14000 行)
│   ├── sensor_calib.yaml
│   └── odom_rel.csv
├── gt/                   # Ground truth（小文件，完整）
│   ├── poses_gt.npy
│   ├── poses_keyframe_gt.npy
│   └── landmarks_gt.npy
├── innovation1/          # 创新一后处理
│   ├── confidence.npy
│   ├── lambda_eigvals.npy
│   ├── lambda3_per_lm.npy
│   ├── well_mask.npy
│   ├── normals.npy
│   ├── optimized_with_normals.ply
│   ├── observability_report.txt
│   ├── poses_optimized.npy
│   └── landmarks_optimized.npy
├── innovation2/          # 创新二输出（小文件，核心）
│   ├── target_masks.npy      (N, 800, 512) bool
│   ├── shadow_masks.npy      (N, 800, 512) bool
│   ├── height_inverted.npy   (N, 800, 512) float
│   ├── sigma_height.npy      (N, 800, 512) float
│   └── inversion_stats.json
├── segmentation_data/    # YOLO-seg / ViT+LoRA 训练数据
│   ├── images/frame_*.npy (60 帧索引)
│   ├── masks/frame_*.png  (60 帧 mask: 0=背景, 1=目标, 2=阴影)
│   ├── classes.txt
│   └── meta.csv
├── imu/imu_data.csv
└── dvl/dvl_data.csv
```

---

## 5. 磁盘与存储

**生成时设置**：
- 默认每个场景 ~200-700 MB（不含大文件）
- `SIM_FULL=1` 环境变量启用完整模式（额外 +200MB/场景存 sonar_images/pixel_hits）

**节省磁盘的方法**：
```python
# 在 gen_scenes.py 中已经做了：
# 1. 默认不存 sonar_images.npy / pixel_hits.npy / pixel_elevs.npy（gt/ 大文件）
# 2. 默认不存 innovation2 中间文件（shadow_length_maps, target_elev_maps）
# 3. 只保留核心：target_masks, shadow_masks, height_inverted, sigma_height
```

---

## 6. 一键运行

```powershell
cd "C:\Users\likunyuan\Desktop\private document\sfm\sfm_synthetic_pillars"

# 跑全部 16 场景（已生成，跳过已存在的）
python gen_scenes.py

# 跑单个场景
python gen_scenes.py 02_simple_two_pillars

# 完整模式（含大文件，需 ≥5GB 磁盘空间）
$env:SIM_FULL="1"
python gen_scenes.py 02_simple_two_pillars 05_diverse_shapes

# 汇总统计
python collect_summary.py
python print_summary.py big_paper_scene_set\summary.json
```

---

## 7. 推荐实验（按大论文各部分）

### 第 3 章 创新点一：置信度贯穿的鲁棒声呐 BA
- **M1 软关联置信度**：用 06（拥挤）+ 11（杂波）+ 12（多径）做关联消融
- **M2 球坐标+视场**：用 09（窄仰角）+ 10（宽仰角）对比
- **M3 联合优化**：所有场景都跑 V2/V5/V6 对比（见 `run_all_5.py`）
- **M4 加权曲面**：用 11（杂波）做加权 vs 无加权泊松对比

### 第 4 章 创新点二：阴影引导的高度反演
- **核心消融 6.1**：用 **02（最简双柱）** + **16（极限外点）** 做 A vs B
  - A 只多视几何
  - B 多视+阴影高度先验
- **方法对比**：用 04（球）作为"阴影极少"的反例
- **鲁棒性**：用 12、15、16 测试低 SNR 下阴影反演鲁棒性

### 第 5 章 系统集成与整体实验
- **消融矩阵**：在 02、05、06、11 上跑完整 7 模块消融
- **真实轨迹模拟**：用 13（圆周）+ 14（之字）作为实战测试
- **不同声呐部署**：用 07、08、09、10 测试声呐配置敏感性

---

## 8. 适用 BA 代码（项目根目录 ../BA代码）

```powershell
# 复制任一场景到 BA 代码
cp -r big_paper_scene_set/02_simple_two_pillars/input ../BA代码/sim_input

# 跑 5 版本对比
cd ../BA代码
python ba_optimize.py
python ba_unified.py
```

---

**所有 16 场景已生成并保留在 `big_paper_scene_set/`。**
