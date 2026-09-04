# 论文全集清单 — 大论文「鲁棒声呐 BA + 阴影→高度反演」

> **整理日期**：2026-09-04（V12 更新：40 → 52 PDF，48 唯一，新增 9 篇 P1/P2 论文）
> **论文库位置**：`F:\sfm\论文集\`
> **统计**：**52 PDF / 249.81 MB / 48 篇去重唯一**
> **组织**：按主题组（A-I）分类，每篇统一格式

---

## 阅读说明

**每篇论文的统一格式**：
```
N. 作者 年份 — 关键词标签

完整标题
作者
期刊/会议, 卷(期): 页码
DOI: 10.xxxx/xxxxx
引用数（可选）

⭐⭐⭐ 优先级
🔍 核心贡献
📐 关键公式/算法
🎯 对大论文的用途
⏱ 阶段
```

**状态标记**：
- ✅ = 已下载到 `F:\sfm\论文集\`（提供文件名 + 大小 + SHA256 前 16 位）
- 🔁 = 重复文件（多份相同论文，列出 SHA256 一致组）
- ❌ = 未下载（需机构权限/校园网）
- ❓ = 文件存在但无法识别（待人工查看）

---

# 🔴 A 组：声学阴影几何与高度反演（**P0/P1/P2 全部到位** ✅）

## A1. ✅ Wang 2023 — Motion Degeneracy
```
文件：Wang_2023_motion_degeneracy_FLS_self_supervised_arXiv.pdf
大小：1.68 MB, SHA256: E009CF1C...
```
⭐⭐⭐ 🔍 FLS 仰角自监督学习的运动退化分析

## A2. ✅ Westman 2025 — Stereo Sonar Feature Geometry
```
文件：Westman_2025_Feature_Geometry_Stereo_Sidescan_FLS.pdf
大小：6.69 MB, SHA256: 12F03E6E...（推荐保留）
🔁 重复：2507.05410v1.pdf (相同 SHA256)
```
⭐⭐⭐ 🔍 FLS + SSS 立体声呐几何 + 特征反投影体积估计

## A3. ✅ Aykin & Negahdaripour 2017 — Space Carving（A 组灵魂）
```
文件：Aykin_Negahdaripour_2017_Space_Carving_JOE.pdf
大小：2.32 MB, SHA256: 6AB600D4...（推荐保留）
🔁 重复 3 份同名不同源（SHA256 不同）：
  - Three-Dimensional_..._Space_Carving.pdf (268FD50F...)
  - Three-Dimensional_..._Space_Carving (1).pdf (9B7A8D5C...)
  - Three-Dimensional_..._Space_Carving (2).pdf (5E70FE8B...)
❌ 损坏：Aykin_Negahdaripour_2017_3D_target_recon_FLS_space_carving.pdf (5182 bytes)
```
⭐⭐⭐🔴 🔍 多视 2D FLS → 3D 形状（visibility carving + projection cone）

## A4. ✅ Tang et al. 2020 — Applied Acoustics
```
文件：Tang_2020_Mobile_Active_Sonar_Height_AppliedAcoustics.pdf
大小：2.26 MB, SHA256: 15715104...（推荐保留）
🔁 重复：1-s2.0-S0003682X20305636-main.pdf (49541B9C...)
```
⭐⭐⭐🔴 🔍 单 FLS 图像 + 阴影 + 回波距离 → 3D 高度

## A5. ✅ Wang et al. 2025 — ACSim
```
文件：Wang_2025_ACSim_Acoustic_Camera_TRO.pdf
大小：7.45 MB, SHA256: 1D42812E...（推荐保留）
🔁 重复：ACSim_A_Novel_..._Ground_Truthing.pdf (相同 SHA256)
```
⭐⭐⭐🔴 🔍 递归光线追踪 + 物理着色（多路径反射 + 散射 + 衍射）

## A6. ✅ Negahdaripour 2012 — 3D Scene Interpretation
```
文件：On_3-D_scene_interpretation_from_F-S_sonar_imagery.pdf
大小：1.08 MB, SHA256: 25D7ED4C...
```
⭐⭐ 🔍 单 FLS 图像阴影 + 几何线索 → 3D 物体大小、轮廓、相对位置

## A7. ❌ Aykin & Negahdaripour 2013 — Image Formation
```
Forward-look 2-D sonar image formation and 3-D reconstruction
OCEANS 2013 MTS/IEEE San Diego, 2013, pp. 1-10
DOI: 10.23919/OCEANS.2013.6741270
```
⭐⭐ 🔍 高频 2D FS 声呐图像形成模型（前置工作）

## A8. ✅ Aykin & Negahdaripour 2016 — Lens-Based Modeling
```
文件：Modeling_2-D_Lens-Based_Forward-Scan_Sonar_Imagery_for_Targets_With_Diffuse_Reflectance.pdf
大小：4.14 MB, SHA256: 2955606B...
```
⭐ 🔍 透镜式 FLS（acoustic lens）图像形成建模

## A9. ✅ Negahdaripour 2020 — FLS Stereo
```
文件：Application_of_Forward-Scan_Sonar_Stereo_for_3-D_Scene_Reconstruction.pdf
大小：10.20 MB, SHA256: 9686E2B7...
```
⭐ 🔍 双 FLS 立体几何（双相机/单相机两位置）

## A10. ✅ Zhou et al. 2025 — Automatic Shadow Extraction
```
文件：An_Automatic_Sonar_Target_Shadow_Extraction_Approach_for_Rapid_Seafloor_3-D_Perception_Using_a_Single_Acoustic_Camera.pdf
大小：5.82 MB, SHA256: D6234AD5...
```
⭐⭐ 🔍 单帧声呐目标阴影自动提取 → 3D 感知

## A11. ✅ Feng et al. 2024 — Differentiable Space Carving
```
文件：Differentiable_Space_Carving_for_3D_Reconstruction_Using_Imaging_Sonar.pdf
大小：2.34 MB, SHA256: 36AFE338...
```
⭐⭐ 🔍 可微空间雕刻（DSC）+ 占用概率网格 + 多分辨率 hash 编码
📐 比 NeRF 快 10×，细节更多

---

# 🔴 B 组：鲁棒估计（**P0/P1/P2 全部到位** ✅）— 创新一关键

## B1. ✅ Yang et al. 2020 — GNC RA-L（创新一灵魂）
```
文件：Graduated_Non-Convexity_for_Robust_Spatial_Perception_From_Non-Minimal_Solvers_to_Global_Outlier_Rejection.pdf
大小：3.71 MB, SHA256: CC2CB78B...
引用：~500 次
```
⭐⭐⭐🔴 🔍 GNC 算法：非凸鲁棒问题"凸化" + 全局最优 outlier rejection

## B2. ✅ Yang, Carlone 2019 — GNC arXiv 完整版
```
文件：Yang_Carlone_GNC_TLS_RSS2019.pdf
大小：9.02 MB, SHA256: 6A39C6CC...
```
⭐⭐⭐ 🔍 GNC 算法最完整版本（13 页 + 7 页附录）

## B3. ✅ Yang, Carlone 2020 — Certifiable Perception
```
文件：Yang_Carlone_Certifiable_Perception_ICRA2020.pdf
大小：3.84 MB, SHA256: 93CA41D8...
```
⭐⭐ 🔍 认证感知（Certifiable Perception）框架

## B4. ✅ Yang et al. 2019 — TEASER
```
文件：Yang_Carlone_TEASER_IROS_2019.pdf
大小：4.42 MB, SHA256: 56F3C96A...
```
⭐⭐ 🔍 TEASER：快速可认证的点云配准

## B5. ✅ Sünderhauf 2012 — Switchable Constraints
```
文件：Sunderhauf_Switchable_Constraints_IROS_2012.pdf
大小：0.60 MB, SHA256: 2AE2D00D...
```
⭐⭐ 🔍 SC（Switchable Constraints）鲁棒核

## B6. ✅ Agarwal 2013 — Dynamic Covariance Scaling
```
文件：Robust_map_optimization_using_dynamic_covariance_scaling.pdf
大小：1.14 MB, SHA256: 4D9F77D6...
```
⭐⭐ 🔍 DCS（Dynamic Covariance Scaling）鲁棒核

## B7. ✅ Zhang 2016 — Degeneracy Detection (G 组交叉)
```
文件：On_degeneracy_of_optimization-based_state_estimation_problems.pdf
大小：2.25 MB, SHA256: E6EAD94F...
```
⭐⭐ 🔍 退化检测（基于 Hessian 矩阵特征值）
📐 λ_min 阈值依据

## B8. ✅ Zhang 2016 — Initialization Filters
```
文件：On_the_initialization_of_statistical_optimum_filters_with_application_to_motion_estimation.pdf
大小：0.81 MB, SHA256: 246CCA01...
```
⭐ 🔍 Zhang 系列另一篇：滤波初始化

---

# ✅ C 组：多视几何（已覆盖 14 篇）

## C1. ✅ Westman 2020 — Fermat Paths
```
文件：Westman 等 - 2020 - A Theory of Fermat Paths for 3D Imaging Sonar Reconstruction.pdf
大小：1.21 MB, SHA256: 7672D650...
```
⭐⭐⭐ 🔍 Fermat 路径条件 → 仰角反演的多解性

## C2-C14. 其余 13 篇
- Huang ASfM 系列（2 篇）：
  - `Huang - Acoustic Structure from Motion.pdf` (4.74 MB, 6A9D8C87...)
  - `Huang和Kaess - 2015 - Towards acoustic structure from motion for imaging sonar.pdf` (1.91 MB, 2233801D... 推荐保留)
  - 🔁 重复: `Towards_acoustic_structure_from_motion_for_imaging_sonar.pdf` (相同 SHA256)
- `Sonar_Image_Feature_Detection_and_Matching_for_Acoustic_Structure_from_Motion.pdf` (3.40 MB, AB1AC89A...)
- `Incremental_data_association_for_acoustic_structure_from_motion.pdf` (3.46 MB, 266EAF58...)
- `Bundle_Adjustment-Based_Sonar-Inertial_Odometry_for_Underwater_Navigation.pdf` (0.62 MB, 2C457D2E...)
- `Feature-Based_SLAM_for_Imaging_Sonar_with_Under-Constrained_Landmarks.pdf` (1.36 MB, 90720A14...)
- `DISO_Direct_Imaging_Sonar_Odometry.pdf` (4.03 MB, D6C88128...)
- `Xu 等 - 2024 - DISO Direct Imaging Sonar Odometry.pdf` (4.03 MB, B67B8B84...)
- `Bathymetric-Structure-from-Motion-..._photogrammetry.pdf` (2.24 MB, F4EF0C4E...)
- `jmse-14-01014-v2.pdf` (64.12 MB, C3A1389D...) — 6D 位姿
- Westman 2025 Stereo Sonar（已列 A2）
- `Westman 等 - 2020 - A Theory of Fermat Paths...` （已列 C1）

---

# ✅ D 组：神经隐式（已覆盖 3 篇）

## D1. ✅ Lin 2025 — Acoustic Neural 3D
```
文件：Lin 等 - 2025 - Acoustic Neural 3D Reconstruction Under Pose Drift.pdf
大小：4.79 MB, SHA256: 65702557...
```

## D2. ✅ NeuSIS 2024
- `2209.08221v1.pdf` (5.68 MB, 063BFB58...)
- `simulated.pdf` (1.90 MB, E2D9B905...)

## D3. ✅ 978-981-95-4049-5（书籍章节）
- `978-981-95-4049-5 (1).pdf` (0.45 MB, C4516D59...)

---

# 🟡 F 组：网格评价 Poisson（P4 段必需，1/2 覆盖）

## F1. ✅ Kazhdan & Hoppe 2013 — Screened Poisson
```
文件：Kazhdan_Hoppe_2013_Screened_Poisson_CGF.pdf
大小：19.85 MB, SHA256: 857106C3...
引用：~1000 次
```

## F2. ❌ Hoppe 1992 — Surface Reconstruction
```
Surface Reconstruction from Unorganized Points
ACM SIGGRAPH, 1992
引用：~2000 次
```

---

# ✅ G 组：可观测性（充分覆盖 4 篇）

## G1. ✅ Wang 2023 Motion Degeneracy（已列 A1）
## G2. ✅ Westman 2025 Stereo Sonar（已列 A2）
## G3. ✅ Westman 2020 Fermat Paths（已列 C1）
## G4. ✅ Zhang 2016 TRO 退化检测（已列 B7）

---

# ✅ H 组：海底散射 + 仿真（P0 已满）

## H1. ✅ Kearney & Penko 2022 — NSEA
```
文件：Kearney_2022_NSEA_seafloor_backscatter_Lambert_Rayleigh.pdf
大小：2.20 MB, SHA256: 72316DCC...
```
⭐⭐⭐ 🔍 Lambert 散射 + Rayleigh 噪声 + FLS 完整仿真

## H2. ✅ Potokar 2022 — HoloOcean ICRA
```
文件：Potokar_2022_HoloOcean_ICRA.pdf
大小：5.85 MB, SHA256: E1A489F3...
```

## H3. ✅ Potokar 2022 — HoloOcean Sonar IROS
```
文件：Potokar_2022_HoloOcean_Sonar_IROS.pdf
大小：5.83 MB, SHA256: 7DE0B6FE...
```

## H4. ✅ Romrell 2025 — HoloOcean 2.0
```
文件：Romrell_2025_HoloOcean_2.0_preview.pdf
大小：4.63 MB, SHA256: CFF219A7...
```

## H5. ✅ Wang 2024 — FLS Ground Echo
```
文件：Wang_2024_FLS_ground_echo_simulation_arXiv.pdf
大小：1.29 MB, SHA256: D5E4851B...
```

## H6. ✅ 吴金荣 2014 — 海洋混响（中文）
```
文件：Wu_2014_ocean_reverberation_Lambert_Jackson_wuli_cn.pdf
大小：3.00 MB, SHA256: 73B5DD0F...
```

## H7. ❌ Stanic 1998 — Jackson vs BOGGART
## H8. ❌ Jackson 1986 — JASA
## H9. ❌ Parnum 2004 — ACOUSTICS

---

# 🟢 E 组：声呐分割（P5 段必需）

## E1. ❌ SAM Adaptation for Sonar
## E2. ❌ LoRA Segmentation for FLS

---

# ⚪ I 组：评价指标（P6 写作时）

## I1-I3. ❌ 待定

---

# 🔁 重复文件清单（清理建议）

## 必删（损坏 + 完全重复）
```
mavis-trash "F:\sfm\论文集\Aykin_Negahdaripour_2017_3D_target_recon_FLS_space_carving.pdf"  # 5182 bytes HTML
mavis-trash "F:\sfm\论文集\2507.05410v1.pdf"  # Westman 2025 重复
mavis-trash "F:\sfm\论文集\ACSim_A_Novel_Acoustic_Camera_Simulator_With_Recursive_Ray_Tracing_Artifact_Modeling_and_Ground_Truthing.pdf"  # ACSim 2025 重复
mavis-trash "F:\sfm\论文集\Towards_acoustic_structure_from_motion_for_imaging_sonar.pdf"  # Huang&Kaess 2015 重复
```

## 推荐删（同名疑似重复）
```
mavis-trash "F:\sfm\论文集\Three-Dimensional_Target_Reconstruction_From_Multiple_2-D_Forward-Scan_Sonar_Views_by_Space_Carving.pdf"
mavis-trash "F:\sfm\论文集\Three-Dimensional_Target_Reconstruction_From_Multiple_2-D_Forward-Scan_Sonar_Views_by_Space_Carving (1).pdf"
mavis-trash "F:\sfm\论文集\Three-Dimensional_Target_Reconstruction_From_Multiple_2-D_Forward-Scan_Sonar_Views_by_Space_Carving (2).pdf"
mavis-trash "F:\sfm\论文集\Motion_Degeneracy_in_Self-supervised_Learning_of_Elevation_Angle_Estimation_for_2D_Forward-Looking_Sonar.pdf"
mavis-trash "F:\sfm\论文集\1-s2.0-S0003682X20305636-main.pdf"
```

---

# 📊 汇总统计（V12 更新）

## 按组覆盖

| 组 | 主题 | 现有 | 待补 | 状态 | 变化 |
|---|------|------|------|------|------|
| A | 阴影几何 | 9 | 2 | ✅ **P0/P1/P2 全到** | +4 (A6, A8, A9, A10, A11) |
| B | 鲁棒估计 | 7 | 0 | ✅ **P0/P1/P2 全到** | +3 (B6, B7, B8) |
| C | 多视几何 | 14 | 0 | ✅ 充分 | 0 |
| D | 神经隐式 | 3 | 0 | ✅ 充分 | 0 |
| E | 声呐分割 | 0 | 2 | ❌ 全缺 | 0 |
| F | 网格 Poisson | 1 | 1 | ⚠ 1/2 | 0 |
| G | 可观测性 | 4 | 0 | ✅ 充分 | +1 (Zhang 2016) |
| H | 海底散射 | 6 | 3 | ✅ 已满 | 0 |
| I | 评价指标 | 0 | 3 | ❌ P6 | 0 |
| **总计** | | **44** | **11** | **55 篇** | **+10 (P1/P2 全到)** |

## 按阶段优先级（V12 更新）

| 优先级 | 论文数 | 状态 | 变化 |
|--------|--------|------|------|
| 🔴 P0 立即 | 0 缺 | ✅ **全部到手** | 0 |
| 🟡 P1 一周内 | 0 缺 | ✅ **全部到手** | -4 (A6 已下) |
| 🟢 P2 段 | 1 缺 | 待补 Hoppe 1992 | -5 (A8/A9/A10/A11, B6, B7 已下) |
| 🟢 P5 段 | 2 缺 | 待补 SAM, LoRA | 0 |
| ⚪ P6 段 | 3 缺 | 写作时 | 0 |
| ⚪ 剩余 | 5 缺 | 写作时 | 0 |

## 创新点对照

### 创新一：鲁棒 BA
- ✅ 7 篇全部到位（GNC×2, Certifiable, TEASER, SC, DCS, Zhang 退化）
- 完全可推进 T2.1 创新一实现

### 创新二：阴影→高度反演
- ✅ 9 篇全部到位（Aykin×2, Negahdaripour×2, Tang 2020, ACSim 2025, Westman 2025, Zhou 2025, Feng 2024）
- 完全可推进 T0.5 + T0.7 + T3.5

---

# 📁 文件结构

```
F:\sfm\论文集\
├── README_论文清单.md              ← 本文件（V12）
├── _AUDIT_REPORT.md                ← 审计报告（V12）
├── WANTED_PAPERS.md                ← 行动手册
├── *.pdf                           ← 52 个 PDF（含 9 个待清理重复/损坏）
└── ...

F:\sfm\sfm_synthetic_pillars\
├── LIT_NOTES.md                    ← 阅读笔记（V12，含新增论文详细笔记）
├── PAPER_SEARCH_PLAN.md            ← 论文查找计划
├── WANTED_PAPERS.md                ← 校园网行动手册
└── campus_fetch.ps1                ← 校园网下载脚本
```

---

*本清单由 Session 12 阶段产出（V12），配合 `LIT_NOTES.md` + `WANTED_PAPERS.md` 一起使用*
