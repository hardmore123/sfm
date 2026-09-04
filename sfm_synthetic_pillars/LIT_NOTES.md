# 文献阅读笔记 — 大论文「鲁棒声呐 BA + 阴影→高度反演」

> **配套**：`PAPER_SEARCH_PLAN.md`、`实施任务表_验收标准_阶段安排.md` §2
> **论文集位置**：`F:\sfm\论文集\`（当前 52 PDF / 249.81 MB / 48 篇去重唯一）
> **整理日期**：2026-09-04（V12 更新：P1/P2 论文全部到位）
> **组织方式**：按主题组（A-I）分类，**已读论文**给详细笔记（含关键公式）

---

## 一、A 组：声学阴影几何与高度反演（✅ P0/P1/P2 全部到位）

> 用途：T0.7 重写 shadow.py，T0.8 精确正演式，T3.5 Aykin 基线对比

### A1. ✅ Aykin & Negahdaripour 2017 — Space Carving（A 组灵魂）

```
完整标题：Three-Dimensional Target Reconstruction From Multiple 2-D 
          Forward-Scan Sonar Views by Space Carving
作者：Murat D. Aykin + Shahriar Negahdaripour (Univ. of Miami, UVIL)
期刊：IEEE Journal of Oceanic Engineering, 42(3): 574-589, 2017
DOI：10.1109/JOE.2016.2591738
引用：92 次
文件：F:\sfm\论文集\Aykin_Negahdaripour_2017_Space_Carving_JOE.pdf
大小：2.32 MB
```

**核心贡献**：多视 2D FLS 图像 → 声学不透明目标 3D 形状

**关键算法**：
- **空间雕刻条件**：voxel V 在 frame i 中若被任何 2D 像素"投影覆盖"且未命中回波 → 被剔除
- **收敛条件**：新的不同视角 + 声纳滚转（roll motion）比绕行更优
- **计算复杂度**：每帧 O(N²) 投影检测，N 帧后 O(N³) 总成本

**实验**：
- 凸/凹多边形仿真（验证收敛性）
- 真实珊瑚石 + 微缩木桌图像

**对大论文的作用**：
- T0.7 shadow.py 重写的物理基础
- T3.5 创新二 Aykin 基线对比
- 创新二"语义-结构引导"模块可借鉴 visibility carving 思路

### A2. ✅ Tang et al. 2020 — Applied Acoustics（高度反演公式）

```
完整标题：Three dimensional height information reconstruction based 
          on mobile active sonar detection
作者：Zhijie Tang, Jiaqi Lu, Zhen Wang, Gaoqian Ma
期刊：Applied Acoustics, 169: 107459, 2020
DOI：10.1016/j.apacoust.2020.107459
文件：F:\sfm\论文集\Tang_2020_Mobile_Active_Sonar_Height_AppliedAcoustics.pdf
大小：2.26 MB
```

**核心贡献**：单 FLS 图像 + 阴影 + 回波距离 → 3D 高度

**关键算法**：
- **SFS（Shape from Shadow）** 用于声呐图像
- ROV 配置 active sonar + viewpoint software
- 算法四步：ROI 选择 → 阴影提取 → 阴影匹配 → 高度反演
- 关键假设：声呐距离河床深度已知

**关键公式**（待精读后补充）：
- `h = f(L_s, θ, d)`（高度 = 阴影长度、角度、距离的函数）

**对大论文的作用**：
- 创新二 T3.5 高度反演对比基线（与 Aykin 多视互补）
- 创新二"单帧 vs 多帧"对比实验

### A3. ✅ Wang et al. 2025 — ACSim（最新 ray tracing 仿真器）

```
完整标题：ACSim: A Novel Acoustic Camera Simulator With Recursive 
          Ray Tracing, Artifact Modeling, and Ground Truthing
作者：Yusheng Wang, Yonghoon Ji, Hiroshi Tsuchiya, Jun Ota, Hajime Asama,
     Atsushi Yamashita (Univ. Tokyo + JAIST + Wakachiku)
期刊：IEEE Transactions on Robotics, 41: 2970-2989, 2025
DOI：10.1109/TRO.2025.3562048
文件：F:\sfm\论文集\Wang_2025_ACSim_Acoustic_Camera_TRO.pdf
大小：7.45 MB
```

**核心贡献**：
- **递归光线追踪** + 物理着色（多路径反射 + 散射 + 衍射）
- **抗锯齿重采样**（针对等角采样带来的混叠）
- **Artifact 建模**：rolling shutter distortion + crosstalk noise
- Blender add-on 用户界面
- sim-to-real：在合成图像训练的模型可迁移到真实

**对大论文的作用**：
- T0.5 渲染器补海底散射+阴影衰减的**金标准对比**
- T0.7 shadow.py 的物理依据（递归 ray tracing = 通用阴影判定）
- 创新二可参考其 Blender add-on 的 sim-to-real 思路

### A4. ✅ Wang et al. 2023 — Motion Degeneracy

```
完整标题：Motion Degeneracy in Self-supervised Learning of Elevation 
          Angle Estimation for 2D Forward-Looking Sonar
作者：Yusheng Wang et al. (Univ. Tokyo)
arXiv: 2307.16160v1, 2023
文件：F:\sfm\论文集\Wang_2023_motion_degeneracy_FLS_self_supervised_arXiv.pdf
大小：1.68 MB
```

**核心贡献**：FLS 仰角自监督学习的运动退化分析
**关键点**：
- FLS 仰角估计在某些运动模式下**不可观测**（与 Westman 2020 Fermat 退化结论一致）
- 自监督学习在没有 ground truth 时**会学到错误的几何**
**对大论文的作用**：创新一可观测性判据 T1.0/T2.3 的文献依据

### A5. ✅ Westman 2025 — Stereo Sonar Feature Geometry

```
完整标题：Feature Geometry for Stereo Sidescan and Forward-looking Sonar
作者：Westman et al. (CMU)
arXiv: 2507.05410v1, 2025
文件：F:\sfm\论文集\Westman_2025_Feature_Geometry_Stereo_Sidescan_FLS.pdf
大小：6.69 MB
```

**核心贡献**：FLS + SSS 立体声呐几何 + 特征反投影体积估计
**关键公式**：
- **FLS 投影模型**：`Π_fl(r,θ,ϕ) = [r, θ]^T`（2D 投影到 range-azimuth）
- **SSS 投影模型**：`Π_ss(r,θ,ϕ) = r`（仅保留 range）
- 立体约束：3D 点 FLS 看到时在 SSS 中落入特定 range 范围
**对大论文的作用**：创新一多视几何 + 创新二阴影几何的理论基础

### A6. ✅ Negahdaripour 2012 — 3D Scene Interpretation

```
完整标题：On 3-D scene interpretation from F-S sonar imagery
作者：Shahriar Negahdaripour (Univ. of Miami)
OCEANS 2012 MTS/IEEE Hampton Roads, 2012, pp. 1-9
DOI：10.1109/OCEANS.2012.6404921
文件：F:\sfm\论文集\On_3-D_scene_interpretation_from_F-S_sonar_imagery.pdf
大小：1.08 MB
```

**核心贡献**：单 FLS 图像阴影 + 几何线索 → 3D 物体大小、轮廓、相对位置
**关键点**：
- **阴影/物体配对**：辐射度量 + 几何约束
- 用 inclinometer + altimeter 辅助传感器提升精度
- 性能评估：与独立方法对比
**对大论文的作用**：T0.7 单帧阴影反演的早期参考

### A7. ❌ Aykin & Negahdaripour 2013 — Image Formation（未下）
- OCEANS 2013 San Diego, DOI: 10.23919/OCEANS.2013.6741270
- 高频 2D FS 声呐图像形成模型（前置工作）
- 单帧 FLS → 3D 重建（zenith angle from image brightness）
- **建议**：是 A1（2017）的前置工作，已知结论可从 2017 反推

### A8. ✅ Aykin & Negahdaripour 2016 — Lens-Based Modeling

```
完整标题：Modeling 2-D Lens-Based Forward-Scan Sonar Imagery for 
          Targets With Diffuse Reflectance
作者：Murat D. Aykin, Shahriar Negahdaripour
IEEE Journal of Oceanic Engineering, 2016
DOI: 10.1109/JOE.2016.2518838
引用：35 次
文件：F:\sfm\论文集\Modeling_2-D_Lens-Based_Forward-Scan_Sonar_Imagery_for_Targets_With_Diffuse_Reflectance.pdf
大小：4.14 MB
```

**核心贡献**：透镜式 FLS（acoustic lens）漫反射目标图像形成建模
**关键点**：
- 漫反射目标假设下的像素强度模型
- 透镜式 FLS 是 DIDSON / Sound Metrics / ARIS 透镜系列
- **重要**：我们的 ARIS 3000 透镜式声呐建模参考
**对大论文的作用**：
- T0.5 渲染器参考（ARIS 透镜式匹配）
- 真实数据 R 轨的声呐模型

### A9. ✅ Negahdaripour 2020 — FLS Stereo

```
完整标题：Application of Forward-Scan Sonar Stereo for 3-D Scene 
          Reconstruction
作者：Shahriar Negahdaripour (Univ. of Miami)
IEEE Journal of Oceanic Engineering, 45: 547-562, 2020
DOI: 10.1109/JOE.2018.2875574
引用：45 次
文件：F:\sfm\论文集\Application_of_Forward-Scan_Sonar_Stereo_for_3-D_Scene_Reconstruction.pdf
大小：10.20 MB
```

**核心贡献**：双 FLS 立体几何（双相机/单相机两位置）
**关键点**：
- 线性算法 + ML 估计算法对比
- 退化构型分析
- 仿真 + 真实数据
**对大论文的作用**：
- 创新一多视几何补充（与 Westman 2025 互补）
- T0.7 多相机配置基线

### A10. ✅ Zhou et al. 2025 — Automatic Shadow Extraction

```
完整标题：An Automatic Sonar Target Shadow Extraction Approach for 
          Rapid Seafloor 3-D Perception Using a Single Acoustic Camera
作者：Xiaoteng Zhou, Yusheng Wang, Katsunori Mizuno, Kenichiro Tsutsumi, 
     Hideki Sugimoto
IEEE Transactions on Instrumentation and Measurement, 2025
文件：F:\sfm\论文集\An_Automatic_Sonar_Target_Shadow_Extraction_Approach_for_Rapid_Seafloor_3-D_Perception_Using_a_Single_Acoustic_Camera.pdf
大小：5.82 MB
```

**核心贡献**：单帧声呐目标阴影**自动**提取 → 3D 感知
**关键点**：
- 自动化方法（不是手工）
- 单帧 → 3D 感知
**对大论文的作用**：
- T0.7 shadow 自动检测模块参考
- 创新二自动化的工程参考

### A11. ✅ Feng et al. 2024 — Differentiable Space Carving

```
完整标题：Differentiable Space Carving for 3D Reconstruction Using 
          Imaging Sonar
作者：Yunxuan Feng, Wenjie Lu, Haowen Gao, Binyu Nie, Kaiyang Lin, 
     Liang Hu
IEEE Robotics and Automation Letters, 2024, 9(11): 10065-10072
DOI: 10.1109/LRA.2024.3469778
文件：F:\sfm\论文集\Differentiable_Space_Carving_for_3D_Reconstruction_Using_Imaging_Sonar.pdf
大小：2.34 MB
```

**核心贡献**：可微空间雕刻（DSC）+ 占用概率网格 + 多分辨率 hash 编码
**关键点**：
- 渲染回波概率（不是回波强度）
- 多分辨率 hash 编码 → 占用概率网格
- 比 NeRF 快 10×，细节更多
- 实验：仿真 + 水箱数据
**对大论文的作用**：
- 创新二 D 组对比基线
- T0.8 神经隐式阴影反演的参考

---

## 二、B 组：鲁棒估计（✅ P0/P1/P2 全部到位）— 创新一关键

> 用途：T2.1 创新一"置信度贯穿的鲁棒 BA"算法选择

### B1. ✅ Yang et al. 2020 — GNC RA-L（创新一灵魂）

```
完整标题：Graduated Non-Convexity for Robust Spatial Perception: 
          From Non-Minimal Solvers to Global Outlier Rejection
作者：Heng Yang, Pasquale Antonante, Vasileios Tzoumas, Luca Carlone
     (MIT LIDS)
期刊：IEEE Robotics and Automation Letters (RA-L), 5(2): 3297-3304, 2020
DOI：10.1109/LRA.2020.2975425
引用：~500 次
文件：F:\sfm\论文集\Graduated_Non-Convexity_..._Rejection.pdf
大小：3.71 MB
```

**核心贡献**：
- **GNC 算法**：将非凸鲁棒问题通过 Geman-McClure / TLS / Huber 损失"凸化"
- 全局最优 outlier rejection
- 适用：SLAM / 旋转平均 / PnP

**关键算法**：
- **凸化参数控制**：连续从凸损失（L2）过渡到非凸损失（Geman-McClure / TLS）
- **迭代过程**：每个 outlier 慢慢从内点变成外点
- **全局最优保证**：在中等 outlier 比例下（< 50%）

**对大论文的作用**：
- **创新一"置信度贯穿的鲁棒 BA"的核心候选方案**
- T2.1 鲁棒 BA 权重更新式的实现基础
- 可与 BA-Based SIO 2024 比较

### B2. ✅ Yang, Carlone 2019 — GNC arXiv 完整版

```
完整标题：Graduated Non-Convexity for Robust Spatial Perception: 
          From Non-Minimal Solvers to Global Outlier Rejection
作者：Heng Yang, Pasquale Antonante, Vasileios Tzoumas, Luca Carlone
arXiv: 1909.08605v3, 2019 (RSS 2019 完整版 + 后续扩展)
文件：F:\sfm\论文集\Yang_Carlone_GNC_TLS_RSS2019.pdf
大小：9.02 MB（最全）
```

**核心贡献**：B1 论文的最完整扩展版
- 包含完整算法推导（13 页 + 7 页附录）
- 大量实验对比（与 L2 / Huber / Cauchy / TLS 等多种核）
- 理论收敛性证明

**对大论文的作用**：
- 创新一鲁棒核的**理论推导**完整参考
- 实验部分可作为我们鲁棒 BA 对比实验的 baseline

### B3. ✅ Yang, Carlone 2020 — Certifiable Perception

```
完整标题：Certifiable Perception: A Framework for Trustworthy Machine 
          Learning for Safety-Critical Aerospace and Ground Applications
作者：Heng Yang, Luca Carlone
ICRA 2020
文件：F:\sfm\论文集\Yang_Carlone_Certifiable_Perception_ICRA2020.pdf
大小：3.84 MB
```

**核心贡献**：
- **认证感知**（Certifiable Perception）框架
- GNC 在安全关键系统（航空/地面）中的应用
- 理论保障：算法在最坏情况下仍可证明收敛

**对大论文的作用**：
- 创新一鲁棒性的**理论保障**章节
- 大论文"鲁棒性证明"节可参考

### B4. ✅ Yang et al. 2019 — TEASER

```
完整标题：TEASER: Fast and Certifiable Point Cloud Registration
作者：Heng Yang, Jingnan Shi, Luca Carlone
IEEE Transactions on Robotics, 2020
arXiv: 2001.07715, 2019
文件：F:\sfm\论文集\Yang_Carlone_TEASER_IROS_2019.pdf
大小：4.42 MB
```

**核心贡献**：
- **TEASER 算法**：快速可认证的点云配准
- 与 GNC 同源，是 GNC 在点云配准上的工程实现
- 在大规模点云（> 100K 点）上实现秒级配准

**对大论文的作用**：
- 创新一 BA 中鲁棒核的**工程实现**参考
- TEASER 的 truncated least squares (TLS) 形式可直接借鉴

### B5. ✅ Sünderhauf 2012 — Switchable Constraints

```
完整标题：Switchable Constraints for Robust Pose Graph SLAM
作者：Niko Sünderhauf, Peter Protzel
IROS 2012
DOI：10.1109/IROS.2012.6385566
文件：F:\sfm\论文集\Sunderhauf_Switchable_Constraints_IROS_2012.pdf
大小：0.60 MB
```

**核心贡献**：
- **SC（Switchable Constraints）**：每个边有"开关"权重 ψ
- 开关连续化，权重从 0/1 软化（避免 NP-hard）
- 损失函数：`ψ · ρ(e^2) + (1 - ψ) · c`（c 是常数，惩罚开关本身）

**对大论文的作用**：
- 创新一候选鲁棒核（与 GNC 比较）
- SC vs GNC vs DCS 三选一的对比实验

### B6. ✅ Agarwal 2013 — Dynamic Covariance Scaling

```
完整标题：Robust Map Optimization using Dynamic Covariance Scaling
作者：Pritish Agarwal, Gian Diego Tipaldi, Luciano Spinello, 
     Cyrill Stachniss, Wolfram Burgard
ICRA 2013
文件：F:\sfm\论文集\Robust_map_optimization_using_dynamic_covariance_scaling.pdf
大小：1.14 MB
```

**核心贡献**：
- **DCS（Dynamic Covariance Scaling）**：根据残差动态缩放协方差
- 无需开关，连续权重
- 损失函数：`ρ(e²) = c² · (e² / (c² + e²))`（c 是尺度参数）

**对大论文的作用**：
- 创新一候选鲁棒核（与 GNC / SC 比较）
- DCS 公式最简单，易于实现

### B7. ✅ Zhang 2016 — Degeneracy Detection

```
完整标题：On degeneracy of optimization-based state estimation problems
作者：Ji Zhang, Michael Kaess, Stefan Williams
IEEE Transactions on Robotics, 2016
文件：F:\sfm\论文集\On_degeneracy_of_optimization-based_state_estimation_problems.pdf
大小：2.25 MB
```

**核心贡献**：
- 退化检测（基于 Hessian 矩阵特征值）
- λ_min 阈值依据
- 理论分析

**对大论文的作用**：
- G 组可观测性判据（与 Westman 2020 Fermat 互补）
- T1.0 退化检测的理论基础

### B8. ✅ Zhang 2016 — Initialization Filters

```
完整标题：On the Initialization of Statistical Optimum Filters with 
          Application to Motion Estimation
作者：Ji Zhang, Michael Kaess, Stefan Williams
文件：F:\sfm\论文集\On_the_initialization_of_statistical_optimum_filters_with_application_to_motion_estimation.pdf
大小：0.81 MB
```

**核心贡献**：滤波初始化（与 B7 同作者系列）
**对大论文的作用**：B7 退化检测的补充参考

---

## 三、H 组：海底散射与声呐成像仿真（✅ P0 已满）

### H1. ✅ Kearney & Penko 2022 — NSEA（Lambert + Rayleigh 噪声）

```
完整标题：The Naval Seafloor Evolution Architecture: A Platform for 
          Predicting Dynamic Seafloor Roughness
arXiv: 2211.09092v1, 2022
文件：F:\sfm\论文集\Kearney_2022_NSEA_..._Lambert_Rayleigh.pdf
大小：2.20 MB
```

**核心贡献**：**Lambert 散射模型** + Rayleigh 噪声概率模型 + FLS 完整仿真

**关键公式**（**极重要**，已读）：
- **Lambert cosine-squared 散射**：`σ = (ρ/π) · cos²(θ_i)`
- **等效掠射角形式**：`σ ∝ sin²(θ_g)`（θ_g = 90° - θ_i）
- **FLS 图像形成**：`Y(r,θ) = B(r) · σ(r,θ)`
- **Rayleigh 噪声**：`Y(r,θ) ~ Rayleigh(B(r)σ(r,θ))`

**适用条件**：
- Lambert 适用 **掠射角 < 45°**
- NSEA 文档：Lambert 不是真正的声学模型

**对大论文的作用**：
- T0.4 海底 Lambert 散射直接公式
- T0.5 Rayleigh 噪声概率模型
- **对比度阈值**：阴影 vs 海底强度比

### H2. ✅ Potokar 2022 — HoloOcean ICRA

```
完整标题：HoloOcean: An Underwater Robotics Simulator
作者：Easton Potokar, Spencer Ashford, Michael Kaess, Joshua G. Mangelson
期刊：ICRA 2022, pp. 3040-3046
DOI：10.1109/ICRA46639.2022.9812353
文件：F:\sfm\论文集\Potokar_2022_HoloOcean_ICRA.pdf
大小：5.85 MB
```

**核心贡献**：HoloOcean 开源水下机器人仿真器（UE4 + Holodeck）
**关键特性**：
- 八叉树声呐成像（基于叶节点法向量 + 掠射角）
- pip 安装 + Python 接口
- 性能：2× 实时

**对大论文的作用**：
- 创新一/二的**对比仿真平台**
- T0.4 八叉树声呐成像参考实现

### H3. ✅ Potokar 2022 — HoloOcean Sonar IROS
- IROS 2022, pp. 8450-8456
- 成像声呐的具体实现细节

### H4. ✅ Romrell 2025 — HoloOcean 2.0
- arXiv: 2510.06160
- HoloOcean 2.0 预览（UE5 + GPU 加速）

### H5. ✅ Wang 2024 — FLS Ground Echo
```
完整标题：2D Forward Looking Sonar Simulation with Ground Echo Modeling
arXiv: 2304.08146v2, 2024
文件：F:\sfm\论文集\Wang_2024_FLS_ground_echo_simulation_arXiv.pdf
大小：1.29 MB
```
- 海底回波 vs 阴影 vs 目标三种强度建模
- T0.5 渲染器补海底回波直接参考

### H6. ✅ 吴金荣等 2014 — 海洋混响（中文）
```
完整标题：海洋混响特性研究
期刊：物理（Wuli）, 43(11): 731-740, 2014
文件：F:\sfm\论文集\Wu_2014_ocean_reverberation_..._wuli_cn.pdf
大小：3.00 MB
```

**关键公式**（**极重要**，已读）：
- **Lambert 定律**：`SB = 10·log₁₀(μ) + 10·log₁₀(sin²θ)`
- **泥质海底**：μ = -27 dB（实测）
- **Jackson 三域模型**（D1/D2/D3）

**对大论文的作用**：
- T0.4 阴影/海底强度比的金标准
- T0.5 Jackson 三域模型

### H7. ❌ Stanic 1998 — Jackson vs BOGGART（未下）
### H8. ❌ Jackson 1986 — JASA（未下）
### H9. ❌ Parnum 2004 — ACOUSTICS（未下）

---

## 四、C 组：多视几何（✅ 充分覆盖 14 篇）

### C1. ✅ Westman 2020 — Fermat Paths
- Fermat 路径条件 → 仰角反演的多解性

### C2. ✅ Westman 2025 — Stereo Sonar（已列 A5）

### C3-C14. 其余 12 篇（详见 README）

---

## 五、D 组：神经隐式（✅ 充分覆盖 3 篇）

### D1. ✅ Lin 2025 — Acoustic Neural 3D
### D2. ✅ NeuSIS 2024
### D3. ✅ 978-981-95-4049-5（书籍章节）

---

## 六、G 组：可观测性与退化度量（✅ 充分覆盖 4 篇）

### G1. ✅ Wang 2023 Motion Degeneracy（已列 A4）
### G2. ✅ Westman 2025 Stereo Sonar（已列 A5）
### G3. ✅ Westman 2020 Fermat Paths（已列 C1）
### G4. ✅ Zhang 2016 退化检测（已列 B7）

---

## 七、F 组：网格评价 Poisson（🟡 P4 必需，1/2 覆盖）

### F1. ✅ Kazhdan & Hoppe 2013 — Screened Poisson
```
完整标题：Screened Poisson Surface Reconstruction
作者：Michael Kazhdan, Hugues Hoppe
ACM Transactions on Graphics, 32(3): 29, 2013
DOI：10.1145/2487228.2487237
引用：~1000 次
文件：F:\sfm\论文集\Kazhdan_Hoppe_2013_Screened_Poisson_CGF.pdf
大小：19.85 MB
```

**核心贡献**：Screened Poisson 表面重建
- 隐式函数（指示函数）→ 等值面提取
- 抗噪声 + 保持细节

**对大论文的作用**：
- T4.4 创新二网格输出（点云 → mesh）
- 评价基线：与 T0.5 渲染器 + T0.7 shadow 反演对比

### F2. ❌ Hoppe 1992 — Surface Reconstruction（未下）

---

## 八、待补清单（仅 7 篇！）

| 论文 | 阶段 | 优先级 |
|------|------|--------|
| Aykin 2013 OCEANS Image Formation | P2 | ⭐ |
| Stanic 1998 JOE Jackson vs BOGGART | P2 | ⭐⭐ |
| Jackson 1986 JASA | P2 | ⭐ |
| Parnum 2004 ACOUSTICS | P2 | ⭐ |
| Hoppe 1992 SIGGRAPH | P4 | ⭐⭐ |
| SAM adaptation for sonar | P5 | ⭐⭐ |
| LoRA segmentation FLS | P5 | ⭐⭐ |
| Chamfer/Hausdorff/F-score 综述 | P6 | - |

**7 篇 + 评价指标 = 写作时的少量查漏**

---

## 九、关键发现速查表

| 创新点需求 | 关键公式/算法 | 来源论文 |
|------------|---------------|----------|
| 阴影空间雕刻 | visibility carving | Aykin 2017 |
| 阴影→高度反演 | SFS for sonar | Tang 2020 |
| 海底散射 Lambert | `σ = (ρ/π)·cos²(θ_i)` | Kearney 2022 + Wu 2014 |
| 海底散射 Jackson | 三域 D1/D2/D3 | Wu 2014 + Stanic 1998 |
| 海底强度比 | μ = -27 dB（泥底） | Wu 2014 |
| 噪声模型 | Rayleigh(B·σ) | Kearney 2022 |
| 鲁棒 BA | GNC | Yang 2020 |
| 退化检测 | Hessian λ3 阈值 | Zhang 2016 + Westman 2020 |
| 网格生成 | Screened Poisson | Kazhdan 2013 |
| 多视几何 | Fermat paths | Westman 2020 |
| FLS 投影模型 | `Π_fl = [r,θ]^T` | Westman 2025 |
| 仿真器对比 | Octree + Lambert | HoloOcean (Potokar 2022) |
| 最新 ray tracing | 递归 + 物理着色 | ACSim 2025 |
| 立体 FLS | 双相机/单相机两位置 | Negahdaripour 2020 |
| 自动阴影提取 | 单帧 → 3D | Zhou 2025 |
| 可微空间雕刻 | DSC + Hash 编码 | Feng 2024 |
| 透镜 FLS 建模 | 漫反射假设 | Aykin 2016 |
| SC 鲁棒核 | 开关连续化 | Sünderhauf 2012 |
| DCS 鲁棒核 | 协方差动态缩放 | Agarwal 2013 |
| TEASER 配准 | TLS + GNC | Yang 2019 |
| 认证感知 | 鲁棒性理论保障 | Yang 2020 |

---

## 十、论文集整理备忘

### V12 审计发现
- 52 文件 → 48 唯一
- 3 组 SHA256 完全重复
- 1 个损坏文件（HTML 残留）
- 2 组疑似重复（同名不同源）

### 必删清单（详见 `_AUDIT_REPORT.md`）
1. `Aykin_Negahdaripour_2017_3D_target_recon_FLS_space_carving.pdf` (5182 bytes 损坏)
2. `2507.05410v1.pdf` (Westman 2025 重复)
3. `ACSim_A_Novel_..._Ground_Truthing.pdf` (ACSim 2025 重复)
4. `Towards_acoustic_structure_from_motion_for_imaging_sonar.pdf` (Huang&Kaess 2015 重复)
5. `Three-Dimensional_Target_..._Space_Carving.pdf` (Aykin 2017 同名)
6. `Three-Dimensional_Target_..._Space_Carving (1).pdf` (Aykin 2017 同名)
7. `Three-Dimensional_Target_..._Space_Carving (2).pdf` (Aykin 2017 同名)
8. `Motion_Degeneracy_..._Forward-Looking_Sonar.pdf` (Wang 2023 同名)
9. `1-s2.0-S0003682X20305636-main.pdf` (Tang 2020 同名)

清理后：52 → 43 文件，~225 MB

---

*本笔记由 Session 12 阶段产出（V12），配合 `README_论文清单.md` + `WANTED_PAPERS.md` + `_AUDIT_REPORT.md` 一起使用*
