# 论文集审计报告 — V12

> **审计日期**：2026-09-04 15:11
> **审计工具**：PowerShell `Get-FileHash` (SHA256) + PDF 魔数检查
> **论文集位置**：`F:\sfm\论文集\`
> **统计**：52 文件 / 51 有效 PDF / 48 篇唯一 / 249.81 MB

---

## 一、总体统计

| 指标 | 数值 |
|------|------|
| 总文件数 | **52** |
| 有效 PDF（%PDF 魔数 + ≥100KB） | 51 |
| 损坏文件（非 %PDF 魔数） | 1 |
| 异常小文件（< 100KB） | 0 |
| 真正完全重复（SHA256 一致） | **3 组 / 6 文件** |
| 疑似重复（同名不同源） | 2 组（Aykin 2017 × 4，Wang 2023 × 2） |
| 唯一论文数（按 SHA256 前 16 位） | **48** |
| 总大小 | **249.81 MB** |
| 可清理大小（SHA256 完全重复） | 15.4 MB |
| 可清理大小（含同名重复） | ~25 MB |

---

## 二、SHA256 完全重复（真正物理重复，6 个文件 → 3 个）

### Group 1: `12F03E6EDC3E2080` (6.38 MB)
- `2507.05410v1.pdf`（arXiv ID 命名）
- `Westman_2025_Feature_Geometry_Stereo_Sidescan_FLS.pdf`（推荐保留）
- **清理**：`2507.05410v1.pdf`

### Group 2: `1D42812AE83E325F` (7.11 MB)
- `ACSim_A_Novel_Acoustic_Camera_Simulator_With_Recursive_Ray_Tracing_Artifact_Modeling_and_Ground_Truthing.pdf`（IEEE 完整名）
- `Wang_2025_ACSim_Acoustic_Camera_TRO.pdf`（推荐保留）
- **清理**：`ACSim_A_Novel_Acoustic_Camera_Simulator_With_Recursive_Ray_Tracing_Artifact_Modeling_and_Ground_Truthing.pdf`

### Group 3: `2233801DCBEA04AA` (1.91 MB)
- `Huang和Kaess - 2015 - Towards acoustic structure from motion for imaging sonar.pdf`（作者署名）
- `Towards_acoustic_structure_from_motion_for_imaging_sonar.pdf`（无作者署名）
- **清理**：`Towards_acoustic_structure_from_motion_for_imaging_sonar.pdf`（推荐保留有作者署名的）

---

## 三、损坏文件（HTML 残留）

### BROKEN-1: Aykin 2017 失败下载
- `Aykin_Negahdaripour_2017_3D_target_recon_FLS_space_carving.pdf` (5182 bytes)
- 状态：不是 %PDF 魔数，是 sci-hub HTML 错误页面
- **必须删除**

---

## 四、疑似重复（同名不同源，SHA256 不同）

### Group A: Aykin 2017 JOE Space Carving（4 份）
| 文件 | SHA256_16 | 大小 | 备注 |
|------|-----------|------|------|
| `Aykin_Negahdaripour_2017_Space_Carving_JOE.pdf` | 6AB600D4... | 2318785 | **推荐保留**（命名规范） |
| `Three-Dimensional_Target_Reconstruction_..._Space_Carving.pdf` | 268FD50F... | 2318773 | 删除 |
| `Three-Dimensional_Target_Reconstruction_..._Space_Carving (1).pdf` | 9B7A8D5C... | 2318773 | 删除 |
| `Three-Dimensional_Target_Reconstruction_..._Space_Carving (2).pdf` | 5E70FE8B... | 2318775 | 删除 |

**说明**：4 份大小几乎相同（2318773-2318775 bytes），SHA256 都不同。可能是同一 PDF 但不同元数据/时间戳/版本。
**建议**：只保留 1 份 `Aykin_Negahdaripour_2017_Space_Carving_JOE.pdf`，其他 3 份删除。

### Group B: Wang 2023 Motion Degeneracy（2 份）
| 文件 | SHA256_16 | 大小 |
|------|-----------|------|
| `Wang_2023_motion_degeneracy_FLS_self_supervised_arXiv.pdf` | E009CF1C... | 1675974 | **推荐保留**（命名规范） |
| `Motion_Degeneracy_in_Self-supervised_Learning_..._Forward-Looking_Sonar.pdf` | B7E86413... | 2439634 | 删除 |

---

## 五、V12 新增论文（之前 P1/P2 缺 → 现在 ✅）

| # | 文件 | 论文 | 之前状态 | 大小 |
|---|------|------|----------|------|
| 1 | `An_Automatic_Sonar_Target_Shadow_Extraction_Approach_..._Acoustic_Camera.pdf` | **Zhou 2025 TIM** | P2 ❌ | 5.82 MB |
| 2 | `Application_of_Forward-Scan_Sonar_Stereo_..._Scene_Reconstruction.pdf` | **Negahdaripour 2020 JOE FLS Stereo** | P2 ❌ | 10.20 MB |
| 3 | `Differentiable_Space_Carving_..._Imaging_Sonar.pdf` | **Feng 2024 RA-L** | P2 ❌ | 2.34 MB |
| 4 | `Modeling_2-D_Lens-Based_..._Diffuse_Reflectance.pdf` | **Aykin 2016 JOE Lens-Based** | P2 ❌ | 4.14 MB |
| 5 | `On_3-D_scene_interpretation_from_F-S_sonar_imagery.pdf` | **Negahdaripour 2012 OCEANS** | P1 ❌ | 1.08 MB |
| 6 | `On_degeneracy_of_optimization-based_state_estimation_problems.pdf` | **Zhang 2016 TRO 退化检测** | P2 ❌ | 2.25 MB |
| 7 | `On_the_initialization_of_statistical_optimum_filters_..._motion_estimation.pdf` | Zhang 系列另一篇 | 新增 | 0.81 MB |
| 8 | `Robust_map_optimization_using_dynamic_covariance_scaling.pdf` | **Agarwal 2013 DCS** | P2 ❌ | 1.14 MB |
| 9 | `142920.134011.pdf` | 待识别 | 新增 | 11.29 MB |
| 10 | `Motion_Degeneracy_..._Forward-Looking_Sonar.pdf` | Wang 2023 重命名版 | 已与 arXiv 版重复 | 2.44 MB |

---

## 六、完整文件清单（52 个，按大小降序）

| # | 文件 | 大小(MB) | SHA256_16 | 状态 |
|---|------|----------|-----------|------|
| 1 | jmse-14-01014-v2.pdf | 64.12 | C3A1389D... | OK |
| 2 | 142920.134011.pdf | 11.29 | CBDCA03E... | OK 待识别 |
| 3 | Application_of_Forward-Scan_Sonar_Stereo_..._Scene_Reconstruction.pdf | 10.20 | 9686E2B7... | OK（Negahdaripour 2020）|
| 4 | Yang_Carlone_GNC_TLS_RSS2019.pdf | 9.02 | 6A39C6CC... | OK |
| 5 | Wang_2025_ACSim_Acoustic_Camera_TRO.pdf | 7.45 | 1D42812E... | OK（推荐保留）|
| 6 | ACSim_A_Novel_..._Ground_Truthing.pdf | 7.45 | 1D42812E... | **DUPLICATE** |
| 7 | 2209.08221v1.pdf | 5.68 | 063BFB58... | OK |
| 8 | Zhang 等 - Adding Conditional Control... | 5.31 | 5CDB3DA7... | OK |
| 9 | An_Automatic_Sonar_Target_Shadow_Extraction_Approach_..._Acoustic_Camera.pdf | 5.82 | D6234AD5... | OK（Zhou 2025）|
| 10 | Lin 等 - 2025 - Acoustic Neural 3D... | 4.79 | 65702557... | OK |
| 11 | Huang - Acoustic Structure from Motion.pdf | 4.74 | 6A9D8C87... | OK |
| 12 | Potokar_2022_HoloOcean_ICRA.pdf | 5.85 | E1A489F3... | OK |
| 13 | Potokar_2022_HoloOcean_Sonar_IROS.pdf | 5.83 | 7DE0B6FE... | OK |
| 14 | Romrell_2025_HoloOcean_2.0_preview.pdf | 4.63 | CFF219A7... | OK |
| 15 | Yang_Carlone_TEASER_IROS_2019.pdf | 4.42 | 56F3C96A... | OK |
| 16 | Modeling_2-D_Lens-Based_..._Diffuse_Reflectance.pdf | 4.14 | 2955606B... | OK（Aykin 2016）|
| 17 | DISO_Direct_Imaging_Sonar_Odometry.pdf | 4.03 | D6C88128... | OK |
| 18 | Xu 等 - 2024 - DISO Direct Imaging Sonar Odometry.pdf | 4.03 | B67B8B84... | OK |
| 19 | Yang_Carlone_Certifiable_Perception_ICRA2020.pdf | 3.84 | 93CA41D8... | OK |
| 20 | Graduated_Non-Convexity_..._Rejection.pdf | 3.71 | CC2CB78B... | OK |
| 21 | Incremental_data_association_..._sonar.pdf | 3.46 | 266EAF58... | OK |
| 22 | Sonar_Image_Feature_Detection_..._Motion.pdf | 3.40 | AB1AC89A... | OK |
| 23 | Aykin_Negahdaripour_2017_Space_Carving_JOE.pdf | 2.32 | 6AB600D4... | OK（推荐保留）|
| 24 | Three-Dimensional_..._Space_Carving.pdf | 2.32 | 268FD50F... | **DUPLICATE** |
| 25 | Three-Dimensional_..._Space_Carving (1).pdf | 2.32 | 9B7A8D5C... | **DUPLICATE** |
| 26 | Three-Dimensional_..._Space_Carving (2).pdf | 2.32 | 5E70FE8B... | **DUPLICATE** |
| 27 | Huang和Kaess - 2015 - ..._imaging_sonar.pdf | 1.91 | 2233801D... | OK（推荐保留）|
| 28 | Towards_acoustic_structure_from_motion_..._sonar.pdf | 1.91 | 2233801D... | **DUPLICATE** |
| 29 | On_degeneracy_of_optimization-based_..._problems.pdf | 2.25 | E6EAD94F... | OK（Zhang 2016）|
| 30 | Wu_2014_ocean_reverberation_..._wuli_cn.pdf | 3.00 | 73B5DD0F... | OK |
| 31 | Kearney_2022_NSEA_..._Lambert_Rayleigh.pdf | 2.20 | 72316DCC... | OK |
| 32 | Westman_2025_Feature_Geometry_..._FLS.pdf | 6.69 | 12F03E6E... | OK（推荐保留）|
| 33 | 2507.05410v1.pdf | 6.69 | 12F03E6E... | **DUPLICATE** |
| 34 | Bathymetric-Structure-from-Motion-..._photogrammetry.pdf | 2.24 | F4EF0C4E... | OK |
| 35 | Differentiable_Space_Carving_..._Imaging_Sonar.pdf | 2.34 | 36AFE338... | OK（Feng 2024）|
| 36 | Motion_Degeneracy_..._Forward-Looking_Sonar.pdf | 2.44 | B7E86413... | **DUPLICATE** |
| 37 | Wang_2023_motion_degeneracy_..._arXiv.pdf | 1.68 | E009CF1C... | OK（推荐保留）|
| 38 | Feature-Based_SLAM_..._Landmarks.pdf | 1.36 | 90720A14... | OK |
| 39 | Wang_2024_FLS_ground_echo_simulation_arXiv.pdf | 1.29 | D5E4851B... | OK |
| 40 | simulated.pdf | 1.90 | E2D9B905... | OK |
| 41 | Westman 等 - 2020 - A Theory of Fermat Paths... | 1.21 | 7672D650... | OK |
| 42 | Robust_map_optimization_..._covariance_scaling.pdf | 1.14 | 4D9F77D6... | OK（Agarwal 2013）|
| 43 | On_3-D_scene_interpretation_from_F-S_sonar_imagery.pdf | 1.08 | 25D7ED4C... | OK（Negahdaripour 2012）|
| 44 | Aubard 等 - 2025 - Sonar-Based Deep Learning... | 1.08 | 8877E582... | OK |
| 45 | On_the_initialization_of_statistical_optimum_filters_...pdf | 0.81 | 246CCA01... | OK（Zhang 系列）|
| 46 | Bundle_Adjustment-Based_Sonar-Inertial_Odometry...pdf | 0.62 | 2C457D2E... | OK |
| 47 | Sunderhauf_Switchable_Constraints_IROS_2012.pdf | 0.60 | 2AE2D00D... | OK |
| 48 | 1-s2.0-S0003682X20305636-main.pdf | 2.26 | 49541B9C... | OK（Tang 2020 重复 1）|
| 49 | Tang_2020_Mobile_Active_Sonar_Height_AppliedAcoustics.pdf | 2.26 | 15715104... | OK（推荐保留）|
| 50 | 978-981-95-4049-5 (1).pdf | 0.45 | C4516D59... | OK |
| 51 | Aykin_Negahdaripour_2017_3D_target_recon_FLS_space_carving.pdf | 0.005 | 7A564298... | **BROKEN** |

---

## 七、清理操作清单（mavis-trash）

### 7.1 必删（损坏 + 完全重复）
```bash
mavis-trash "F:\sfm\论文集\Aykin_Negahdaripour_2017_3D_target_recon_FLS_space_carving.pdf"
mavis-trash "F:\sfm\论文集\2507.05410v1.pdf"
mavis-trash "F:\sfm\论文集\ACSim_A_Novel_Acoustic_Camera_Simulator_With_Recursive_Ray_Tracing_Artifact_Modeling_and_Ground_Truthing.pdf"
mavis-trash "F:\sfm\论文集\Towards_acoustic_structure_from_motion_for_imaging_sonar.pdf"
```

### 7.2 推荐删（同名疑似重复）
```bash
mavis-trash "F:\sfm\论文集\Three-Dimensional_Target_Reconstruction_From_Multiple_2-D_Forward-Scan_Sonar_Views_by_Space_Carving.pdf"
mavis-trash "F:\sfm\论文集\Three-Dimensional_Target_Reconstruction_From_Multiple_2-D_Forward-Scan_Sonar_Views_by_Space_Carving (1).pdf"
mavis-trash "F:\sfm\论文集\Three-Dimensional_Target_Reconstruction_From_Multiple_2-D_Forward-Scan_Sonar_Views_by_Space_Carving (2).pdf"
mavis-trash "F:\sfm\论文集\Motion_Degeneracy_in_Self-supervised_Learning_of_Elevation_Angle_Estimation_for_2D_Forward-Looking_Sonar.pdf"
mavis-trash "F:\sfm\论文集\1-s2.0-S0003682X20305636-main.pdf"
```

### 7.3 待识别
- `142920.134011.pdf` (11.29 MB) - 可能是 Tang 2020 完整版（11MB 偏大，可能是 IEEE 完整版含附录），需要打开看

### 7.4 清理后统计
- 52 → 43 个唯一文件
- 249.81 MB → ~225 MB
- 释放 25 MB

---

## 八、未识别文件待办

| 文件 | 大小 | 待办 |
|------|------|------|
| 142920.134011.pdf | 11.29 MB | 打开看标题，可能是 arXiv 1429.20134 编号（不知道对应什么论文） |
| On_the_initialization_of_statistical_optimum_filters_...pdf | 0.81 MB | Zhang 2016 系列，确认是哪一篇 |

---

*本报告由 Session 12 阶段产出（V12 审计），配合 `README_论文清单.md` + `LIT_NOTES.md` 一起使用*
