# 大论文模拟数据集 —— 全量实现说明

> 本目录按《**大论文思想路线（改进版）**》《**创新点一/二·问题定义与模块分解**》的需求，
> 一次性生成两个创新点所需的全部模拟数据。
> **每个"细枝"如何实现、有何问题/疑问、还需要哪方面论文**都在本文档中详述。

---

## 0. 总体数据规模

| 维度 | 旧数据集（混合之前的 4 柱子 60 帧） | **大论文数据** |
|---|---|---|
| 帧数 | 60 | **120** |
| 关键帧 | 12 | **24** |
| 场景 | 4 根柱子 | **8 根**（含中心粗柱） |
| Landmark | 120 | **240** |
| 观测 | ~2000 | **6500-7300** |
| 关键帧观测 | ~390 | **1300-1500** |
| Track 长度 | 平均 16 帧 | 平均 30+ 帧 |
| **目标像素/帧** | - | **~200**（每帧 ~250 个目标像素） |
| **阴影像素/帧** | - | **~70000**（4-9M 总反演像素） |
| 高度反演中位误差 | - | **0.00 cm**（公式自洽） |
| 良约束 landmark 比例 | - | **30-50%**（取决于运动模式） |

---

## 1. 文件结构（每个运动模式目录）

```
big_paper_sim/<mode>/
├── meta.json                      # 完整摘要（统计 + 全部输出文件清单）
├── input/                          # 创新一输入（4 件套 + 标定 + 协方差）
│   ├── poses_est.npy               # (24, 4, 4) 关键帧位姿
│   ├── pose_frame_ids.npy          # (24,) 关键帧下标
│   ├── landmarks_final.npy         # (240, 3) landmark 坐标
│   ├── tracks.csv                  # 6500-7300 行（含 sigma_theta, sigma_rho）
│   ├── sensor_calib.yaml           # 声学标定
│   └── odom_rel.csv                # 23 段关键帧里程计
├── gt/                             # ground truth（位姿/landmark/图像）
│   ├── poses_gt.npy                # (120, 4, 4) 全部帧真值
│   ├── poses_keyframe_gt.npy       # (24, 4, 4) 关键帧真值
│   ├── landmarks_gt.npy            # (240, 3) landmark 真值
│   ├── sonar_images.npy            # (120, 800, 512) 声呐强度图
│   ├── sonar_lm_id.npy             # (120, 800, 512) 像素→lm 真值关联
│   ├── pixel_hits.npy              # (120, 800, 512, 3) 像素世界交点
│   └── pixel_elevs.npy             # (120, 800, 512) 回波仰角
├── innovation1/                    # 创新点一·几何层后处理
│   ├── poses_optimized.npy         # (24, 4, 4) BA 后位姿
│   ├── landmarks_optimized.npy     # (240, 3) BA 后 landmark
│   ├── confidence.npy              # (240,) 置信度（√观测数 归一）
│   ├── lambda_eigvals.npy          # (240, 3) 三个特征值
│   ├── lambda3_per_lm.npy          # (240,) λ3（最小）
│   ├── well_mask.npy               # (240,) bool 良约束判据
│   ├── normals.npy                 # (240, 3) 加权法向
│   ├── optimized_with_normals.ply   # 带法向+置信度点云
│   ├── observability_report.txt    # 可观测性分析报告
│   └── surface_mesh.ply            # （若有 Open3D）Poisson 网格
├── innovation2/                    # 创新点二·图像理解层
│   ├── target_masks.npy            # (120, 800, 512) bool 目标掩码
│   ├── shadow_masks.npy            # (120, 800, 512) bool 阴影掩码
│   ├── height_gt_maps.npy          # (120, 800, 512) float 高度真值
│   ├── shadow_length_maps.npy      # (120, 800, 512) float 阴影长度真值
│   ├── target_elev_maps.npy        # (120, 800, 512) float 目标仰角
│   ├── height_inverted.npy         # (120, 800, 512) float 高度反演结果
│   ├── sigma_height.npy            # (120, 800, 512) float 高度不确定度
│   └── inversion_stats.json        # 反演统计（中位误差、覆盖率）
├── segmentation_data/              # 语义分割训练数据（YOLO-seg / ViT+LoRA）
│   ├── images/frame_0000.npy ...   # 索引占位（指向 gt/sonar_images.npy）
│   ├── masks/frame_0000.png ...    # 三类 mask：0=背景, 1=目标, 2=阴影
│   ├── classes.txt                 # ['background', 'target', 'shadow']
│   └── meta.csv                    # 每帧统计
├── imu/imu_data.csv                # 2400 行 IMU（200Hz，t/gx/gy/gz/ax/ay/az）
└── dvl/dvl_data.csv                # 120 行 DVL（10Hz，t/vx/vy/vz）
```

---

## 2. 创新点一（几何优化层）：每个细枝如何实现

### 模块1 软数据关联置信度 ⚠️ 部分实现
- **现状**：`confidence.npy` 用"√观测数"作简化代理（与 V4 的 ρ 阈值同源思想）
- **已有 BA 残差**（V2/V4/V5/V6）已支持 Huber/GNC 鲁棒
- **缺**：完整可学习置信度（Switchable Constraints / DCS / max-mixtures）
- **可补**：在 BA 内层加权重变量 w，损失加防塌缩正则 ‖w‖²_α
- **相关论文待补**：Switchable Constraints(Sünderhauf12)、Dynamic Covariance Scaling(Agarwal13)、max-mixtures(Olson)

### 模块2 相对球坐标 + 视场硬约束 ✅ V4/V6 已实现
- **实现位置**：`ba_unified.py:UnifiedSonarBA`
- **机制**：
  - 相对基准帧球坐标 `(ψ, r, elev)` 参数化地标
  - 良约束路标的 `elev` 用 `trf` bounds 限制在 ±0.30 rad 孔径
  - 欠约束路标的 `elev` 在孔径内做 61 网格点搜索
- **论文对应**：V4 已验证"全部 198/217 判为欠约束"；我们用同样判据在 mixed 模式有 71/240 良约束、yaw_y 模式 120/240
- **可观测性量化**：`lambda3_per_lm.npy` 输出 Fisher 信息最小特征值 λ3
- **问题**：在"纯前向平移"运动下 V4/V6 路标 Z 误差 ~20cm——这是球坐标 + 仰角硬约束的固有限制，**不是 bug，是设计**

### 模块3 位姿-地标联合优化 ✅ V2/V4/V5/V6 都已实现
- **现状**：`ba_optimize.SonarBA`（V2 基线）跑通了所有模式
- **测得精度**（mixed 模式）：位姿 2.78cm / 路标 5.98cm / RMS 0.66px
- **5 版本对比**：V5（世界笛卡尔+稀疏解析+GNC）综合最优：5.77cm 路标，2.85cm 位姿，0.63px RMS，12.6s

### 模块4 置信度引导加权曲面重建 ✅ 加权法向已实现，Poisson 需 Open3D
- **加权 PCA 法向**：`surface_recon.estimate_normals_weighted_pca`（K=16 近邻）
- **置信度**：从 `confidence.npy` 读取（√观测数）
- **加权泊松**：`reconstruct_poisson_open3d` 需 Open3D（未装，自动降级到点云+法向）
- **输出**：`optimized_with_normals.ply`（带法向+置信度），可用 MeshLab 查看
- **缺**：加权泊松 + 多视图一致性后处理

### 基础适配 各向异性协方差白化 ✅
- **现状**：`tracks.csv` 含 `sigma_theta` (0.0035 rad) 和 `sigma_rho` (0.005m)
- **缺**：BA 残差未做白化（`w_sonar * (pred - obs)` 仍是统一权重）
- **可补**：把 BA 残差改成 `(A·Δθ)/σ_θ, (C·Δρ)/σ_ρ` 形式白化
- **相关论文**：统计声呐噪声模型

---

## 3. 创新点二（图像理解层）：每个细枝如何实现

### 模块1 目标-背景分割 ⚠️ 数据已就绪，模型未训练
- **数据**：`segmentation_data/masks/` 120 帧 PNG mask（0=背景, 1=目标, 2=阴影）
- **格式**：YOLO-seg 兼容（classes.txt: background, target, shadow）
- **缺**：ViT+LoRA 训练脚本 / YOLO-seg 训练脚本
- **可补**：用 `pip install ultralytics` 训 YOLO-seg；SAM 微调用 segment-anything + LoRA
- **相关论文待补**：SAM、LoRA、YOLO-seg、声呐语义分割、sim-to-real

### 模块2 声学阴影分割 + 高度反演（**核心**）✅ 全链路实现
- **正演模型**（`height_inversion.py`）：
  ```
  L_shadow(θ, elev) = h / |tan(elev)|    # 目标垂直立于水平海底
  ⇒ h = L_shadow * |tan(elev)|
  ```
- **不确定度**（一阶 Taylor 传播）：
  ```
  σ_h² = tan²(elev)·σ_L² + L_s²·(1 + tan²(elev))²·σ_elev²
  ```
- **数据**：
  - `gt/sonar_images.npy` 声呐强度图
  - `innovation2/shadow_masks.npy` 声学阴影真值
  - `innovation2/height_gt_maps.npy` 高度真值（每像素）
  - `innovation2/height_inverted.npy` 阴影反演结果
  - `innovation2/sigma_height.npy` 不确定度
- **验证**：4 模式 × 4-9M 像素反演中位绝对误差 = **0.00 cm**（用 L_shadow 和 elev 真值时）—— 说明公式与 ground truth 完全自洽
- **下一步**：
  - 加 L_s 和 elev 的真值噪声（σ_L=0.05m, σ_elev=1°），看反演误差传播
  - 训练 ViT+LoRA 从声呐图预测阴影区域
  - 与 Aykin 式手工阈值基线对比

### 模块3 语义一致性关联约束 ⚠️ 数据就绪，约束未接入
- **数据**：`segmentation_data/masks/` 提供每像素的语义标签
- **缺**：BA 数据关联阶段加"同语义区域才可匹配"门控
- **可补**：在 `ba_optimize.build_track_to_landmark` 中加 mask 检查

---

## 4. 物理/数学模型与论文依据

| 组件 | 模型 | 论文依据 |
|---|---|---|
| 方位/距离 | θ=atan2(y,x), ρ=‖P_b‖ | Huang&Kaess 2015 Eq.4-5 |
| 仰角歧义 | 不可观测（arc） | Qadri 2022 §III-A |
| 像素强度 | I(r,θ) = ∫φ σ(φ)·T·E/r² dφ | Qadri 2022 Eq.1-2 |
| 声学阴影 | L_s = h / |tan(elev)| | Aykin & Negahdaripour 2013-2017 |
| 高度反演不确定度 | 一阶 Taylor | 经典误差传播 |
| 可观测性 | Fisher 信息 / A^TA 特征值 | Zhang degeneration factor; Westman 等 |
| 噪声 | σ_θ=0.2°, σ_ρ=0.005m | Huang 2015 Table I |
| 鲁棒核 | Huber, GNC-GM | Yang&Carlone 2020 |

---

## 5. 各模块"问题/疑问/还需要的论文"

### 5.1 创新点一（几何层）

| 模块 | 现状 | 问题/疑问 | 还需要的论文 |
|---|---|---|---|
| 软关联置信度 | 简化代理 | 怎样防权重塌缩？w 衰减后还能不能恢复？ | Sünderhauf 2012 (Switchable Constraints); Agarwal 2013 (DCS); Olson (max-mixtures) |
| 球坐标+视场 | V6 已实现 | forward 模式下路标 Z 误差大（已知退化） | 改进：把球坐标 + 笛卡尔 参数化按 well-constrained 数动态切换 |
| 联合优化 | V5 最优 | GNC 对 clean 数据几乎无增益 | Yang&Carlone 2020 GNC 理论；Barron general loss |
| 加权曲面 | 加权 PCA 已实现 | Poisson 需 Open3D；多大置信度才够？ | Kazhdan 2013 (Screened Poisson); Points2Surf; 神经面 |
| 协方差白化 | 数据有 σ 列 | 残差未做白化 | 各向异性 BA 经典文献 |
| 可观测性 | λ3, λ3/λ2 已输出 | 与运动模式如何联动？自适应当前没用上 | Zhang & Heng 退化因子; Rong 可观测性 |

### 5.2 创新点二（图像层）

| 模块 | 现状 | 问题/疑问 | 还需要的论文 |
|---|---|---|---|
| 目标-背景分割 | YOLO/ViT 训练数据已就绪 | 小样本下训练是否收敛？背景杂波是否被正确分割？ | SAM (Kirillov 2023); LoRA (Hu 2021); YOLO-seg; 声呐域适应 |
| 声学阴影分割 | 阴影真值已生成 | 真实声呐里阴影边界模糊→训练精度？ | Qadri 2022 (声学成像); 阴影检测综述 |
| 高度反演公式 | 公式自洽（0cm 误差） | 真实阴影长度怎么测？仰角怎么估？ | Aykin & Negahdaripour 2013-2017 (核心) |
| 高度先验注入 | V6 已留 `elev_prior` 接口 | 实际接入效果如何？ | 这正是大论文创新二的核心实证 |
| 语义关联 | 掩码已生成 | 跨帧同语义匹配怎么做？ | 语义 SLAM 综述（如 LSeg-SLAM） |

### 5.3 整体闭环

| 环节 | 现状 | 还需要的论文/工作 |
|---|---|---|
| 反哺（几何→分割） | 未做 | 投影一致性约束分割 |
| Sim-to-real | 仅仿真 | HoloOcean/DAVE；相干斑仿真；ControlNet 合成 |
| 真值与定量 | 仿真全真值 | 真实受控靶/水箱 CAD 已知物体/多波束参考 |
| 评价指标体系 | 部分 | Chamfer/Hausdorff/ATE/RPE/mIoU/Dice 的标准定义 |

---

## 6. 一键运行

```powershell
cd "C:\Users\likunyuan\Desktop\private document\sfm\sfm_synthetic_pillars"

# 单模式（默认 mixed）
python big_paper_sim.py --out ./big_paper_sim/mixed --mode mixed

# 4 模式批量
python run_big_paper_batch.py

# 5 版本 BA 对比（用最新数据）
python run_all_5.py --input ./big_paper_sim/mixed/input --gt ./big_paper_sim/mixed/gt
```

---

## 7. 关键设计取舍说明

1. **为何 8 根柱子 + 240 landmark**：
   - 大论文创新二·模块2（阴影反演）需要更多目标点对比，4 根不够形成"消融"
   - 240 接近真实数据集（386 track_id）的规模

2. **为何 4 种运动模式都生成**：
   - general 对应良约束情形（创新一·V6 球坐标设计目标）
   - forward / yaw_y 对应欠约束（创新一·V4 退化分析 + 创新二核心证据）
   - mixed 模拟真实巡检（不同运动段拼接）

3. **为何高度反演 0.00 cm 误差**：
   - 我们用的是 **ground truth L_shadow 和 ground truth elev** 直接代入公式
   - 这是"理论上限"；下一步加噪声才会体现真实反演误差

4. **为何目标-背景-阴影三类 mask 都生成了 120 帧**：
   - 给 ViT+LoRA 训练足够的小样本
   - YOLO-seg 训练可直接用（class 编号 0/1/2 与 classes.txt 对齐）

5. **为何不预装 Open3D 跑 Poisson 重建**：
   - Open3D 在 Windows 上 pip 装常有版本冲突
   - 我们输出带法向+置信度的 .ply，可用 MeshLab / CloudCompare 打开
   - Poisson 是模块4 的 prototype，install 后会自动启用

---

## 8. 大论文实验 6.1 仰角来源消融（关键实验）已就绪

按大论文思想路线 §6.1 的设计：

| 情形 | 数据/脚本 | 预期结果 |
|---|---|---|
| **A 只多视几何** | `run_all_5.py --algo V2`（世界笛卡尔 BA） | 路标 Z 误差较大（受可观测性限制） |
| **B 多视 + 阴影高度先验** | 改 V6 注入 `elevation_prior = height_inverted / sigma_height` | 路标 Z 误差显著下降（**这是核心证据**） |

具体接入方法（待写）：

```python
import ba_unified as unif
# 创新二·模块2 高度反演结果
h_inv = np.load("./big_paper_sim/mixed/innovation2/height_inverted.npy")
sigma_h = np.load("./big_paper_sim/mixed/innovation2/sigma_height.npy")

# 聚合到 landmark 级（按 visibility 加权平均）
elev_prior = np.full(M, np.nan)         # 每个 landmark 的仰角先验
sigma_elev_prior = np.full(M, np.inf)   # 默认极大（无先验）
# ... 对每个 landmark 找到对应像素的平均值 ...

# 注入 V6
ba = unif.UnifiedSonarBA(
    poses6, landmarks, ..., elev_prior=elev_prior, elev_prior_sigma=sigma_elev_prior)
```

**这一对比就是大论文创新二的核心实证，建议作为论文主打实验之一。**

---

## 9. 残留风险与未解决问题

### 已识别但未实现
1. **阴影反演的真实噪声模型**：当前 L 和 elev 是 ground truth，需加 σ_L, σ_elev 看误差传播
2. **ViT+LoRA / YOLO-seg 训练**：模型与训练脚本需要单独补
3. **Open3D Poisson 重建**：需 `pip install open3d`
4. **真实受控靶验证**：本数据集是纯仿真
5. **高度先验注入 V6 的对比实验**：未跑（A vs B 消融）

### 还需要联网检索的论文方向（按优先级）
1. ★★★ 神经隐式/可微渲染声呐重建（NeuSIS Lin 25, Qadri 22）—— SOTA 定位
2. ★★★ Aykin & Negahdaripour 2013-2017 阴影→高度系列 —— 切割新颖性
3. ★★★ Switchable Constraints / DCS / max-mixtures —— 防退化正则
4. ★★ GNC + χ² 理论（Yang&Carlone 20）+ Barron general loss
5. ★★ SAM + LoRA 在声呐上的应用（域适应 + 极坐标数据增强）
6. ★★ 加权泊松 / Points2Surf / 神经面 —— 曲面重建

---

**完成时间**：2026-09-03
**总数据规模**：4 模式 × (120 帧 + 8 柱子 + 240 landmark + 6500-7300 观测 + 7M+ 阴影像素反演)
**总耗时**：约 16 分钟（4 模式批量）
**生成的所有数据均保留在 `./big_paper_sim/`**
