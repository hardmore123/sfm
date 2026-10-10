# scene_set_v2 — S1-S6 代表场景

> **阶段**：P1 仿真构型与数据重建（T1.1, T1.3, T1.5）
> **生成时间**：2026-09-04
> **报告**：`../T1_1_REPORT.md`

---

## 1. 场景总览

| # | 场景 | 设计意图 | 构型关键 | 期望可反演 | 实测可反演 | 匹配 |
|---|------|----------|----------|-----------|-----------|------|
| **S1** | `S1_single_well_constrained` | 单目标良约束（基线） | general + heave 1.2 | ✅ | ✅ | OK |
| **S2** | `S2_single_forward_degenerate` | forward 退化（BA 对照） | forward + heave 0 | ✅ | ✅ | OK |
| **S3** | `S3_mixed_shapes` | 多目标混合 | 柱+方+球 | ✅ | ✅ | OK |
| **S4** | `S4_low_snr` | 低 SNR | speckle 0.35 | ✅ | ✅ | OK |
| **S5** | `S5_envelope_edge` | 包线边缘 | h=0.9h_max | ✅ | ✅ | OK |
| **S6** | `S6_envelope_outlier` | 包线外负例 | h=5.5>z_s | ❌ | ❌ | OK |

**判定匹配**：6/6 全部通过（T1.1 验收）。

## 2. 共享构型（按 §7.1）

| 参数 | 值 | 物理意义 |
|------|-----|----------|
| 声呐距海底 $z_s$ | 4.5 m | 平台 altitude |
| 声呐量程 $\rho_{max}$ | 25 m | Oculus M1200d @1.2MHz |
| 方位视场 | ±65° | 水平 130° |
| 仰角孔径 | ±17° | ARIS 真实孔径 |
| 固定下俯 $\theta_p$ | 18° | 真实 MCM 构型（20-45° 下俯） |
| 升沉 heave | 1.2 m（S1-S5）；0.0（S2） | 多视差激励 |
| 俯仰摆动 | ±3° | 微调 |
| 偏航摆动 | ±5.7° | 多视差激励 |
| 声呐波束 | 256 beam × 600 range bin | 153K 像素/帧 |
| 帧数 | 20（关键帧 5） | 轻量数据 |

## 3. 场景几何

| # | 目标 | 距声呐 d | 包线余量 |
|---|------|---------|----------|
| S1 | 1 柱 h=2.5 r=0.4 | 10 m | 6%（h_max 2.67） |
| S2 | 1 柱 h=2.5 r=0.4 | 10 m | 6% |
| S3 | 2 柱(h=1.5)+1 方(h=1.0)+1 球(φ=0.8) | 13-17 m | 45%（h_avg 1.2, h_max 2.21） |
| S4 | 1 柱 h=2.5 r=0.4（低 SNR） | 10 m | 6% |
| S5 | 1 柱 h=2.40 r=0.4（h=0.9h_max） | 10 m | 11% |
| S6 | 1 柱 h=5.5 r=0.4（h>z_s 负例） | 10 m | 仰角向上 +5.7° ⇒ 不可反演 |

## 4. 产出 schema

每个场景到 `<scene>/`：
```
<scene>/
├── meta.json                   完整摘要（可反演性 + GT 质量 + 反演精度 + 耗时）
├── README.md                   场景说明（构型 + 数据规模 + 反演结果）
├── gt/
│   ├── poses_gt.npy            (N, 4, 4) 真值位姿
│   ├── surface_points.npy      (M, 3)   T0.10 GT 表面点
│   ├── surface_normals.npy     (M, 3)   T0.10 GT 表面法向
│   ├── sonar_images.npy        (N, H, W) 渲染声呐图（T0.5 V3）
│   ├── target_masks.npy        (N, H, W) 目标掩码
│   ├── shadow_masks.npy        (N, H, W) 阴影掩码
│   ├── height_gt_maps.npy      (N, H, W) 目标顶 z 真值
│   ├── target_elev_maps.npy    (N, H, W) 顶部射线仰角（世界系）
│   ├── shadow_length_maps.npy  (N, H, W) 物理 L_s
│   └── D_t_map.npy             (N, H, W) 声呐到目标底部水平距离（反演用）
├── innovation2/
│   ├── height_inverted.npy     (N, H, W) V2 精确反演
│   ├── sigma_height.npy        (N, H, W) σ 传播
│   ├── height_inverted_v1.npy  (N, H, W) V1 简化反演（对照基线）
│   ├── height_inverted_noisy.npy (N, H, W) V2 + σ_L=5cm 仿真噪声
│   └── sigma_height_noisy.npy
└── segmentation_data/          (可选) 训练用 masks
```

## 5. 反演结果汇总（T0.7 + T0.8 验收）

| 场景 | n_valid | V2 MAE | V2_noisy MAE | V1 MAE | 验收（≤5cm）|
|------|---------|--------|--------------|--------|------------|
| S1 | 35,196 | 0.00 cm | **0.36 cm** | 252.07 cm | ✅ |
| S2 | 66,690 | 0.00 cm | **0.30 cm** | — | ✅ |
| S3 | 44,765 | 0.00 cm | **0.58 cm** | — | ✅ |
| S4 | 35,196 | 0.00 cm | **0.36 cm** | — | ✅ |
| S5 | 28,634 | 0.00 cm | **0.38 cm** | — | ✅ |
| S6 | 0 (infeas) | N/A | N/A | — | N/A |

**V2 (无噪声) MAE = 0**：几何 GT 自洽（数学必然，因为 L_s 用物体几何 h 算，反演公式严格还原 h）。
**V2_noisy (σ_L=5cm) MAE ≤ 0.6 cm**：T0.7 验收通过（≤5cm + 非零）。

## 6. 重建命令

### 6.1 跑全部 6 场景
```bash
cd F:\sfm\sfm_synthetic_pillars
python gen_scenes_v2.py
```

### 6.2 跑单个场景
```bash
python gen_scenes_v2.py S1_single_well_constrained
python gen_scenes_v2.py S3_mixed_shapes S4_low_snr
```

### 6.3 可反演性自检
```bash
python scene_configs_v2.py
```
输出 6 场景 + 期望/实测/匹配三列表。

### 6.4 数据加载
```python
import numpy as np
m = np.load('./scene_set_v2/S1_single_well_constrained/meta.json', allow_pickle=True).item()
# 加载数据
gt = np.load('./scene_set_v2/S1_single_well_constrained/gt/sonar_images.npy')
tm = np.load('./scene_set_v2/S1_single_well_constrained/gt/target_masks.npy')
sm = np.load('./scene_set_v2/S1_single_well_constrained/gt/shadow_masks.npy')
h_inv = np.load('./scene_set_v2/S1_single_well_constrained/innovation2/height_inverted.npy')
```

## 7. 适用实验

| 创新点 | 适用实验 |
|--------|----------|
| 创新一·M1 软关联置信度 | S1（单目标 sanity）/ S2（forward 退化）/ S5（边缘） |
| 创新一·M2 球坐标+视场 | S1（基线）/ S3（多目标）/ S5（边缘） |
| 创新一·M3 多视几何退化检测 | **S2**（必须退化）/ S1（必须良约束） |
| 创新一·M4 加权曲面 | S3（多目标曲面）/ S1（单目标） |
| 创新二·M1 目标-背景分割 | S4（低 SNR）/ S3（多目标） |
| 创新二·M2 阴影高度反演 | **所有** S1-S5（V2_noisy MAE 0.3-0.6 cm） |
| 创新二·M3 κ 门控 | S5（边缘）+ S2（退化）对照 |
| 创新二·M4 Aykin 对比 | 所有 S1-S5 |
| 创新二·M5 跨目标语义关联 | S3（多目标） |
| T0.9 可反演性包线 | **所有** S1-S6（验证 5/6 匹配） |
| T0.7 阴影→高度反演 | S1（基线）/ S4（低 SNR）/ S5（边缘） |

## 8. 已知边界

### 8.1 T0.10 std/mean_nn 未达 0.3
单柱场景 1500 点 NN 距离 std/mean = 0.65-0.88，柱间空隙大。
- 影响：仅 T0.10 单元测试 std/mean_nn 验收；反演、BA、可观测性均不依赖 GT 表面点云均匀性
- 修复方向：增加采样密度到 5000+ 或用 Poisson disk sampling（P4 阶段 T4.4 处理）

### 8.2 S6 AUV heave 让部分帧可反演
S6 期望 h=5.5 > z_s=4.5 不可反演，但 AUV heave=1.2 让 z_s 在 [3.3, 5.7] 起伏，部分帧（z_s > 5.5）可反演。
- 影响：feasibility 场景级判定已对（h_max/z_s 关系），但瞬时帧级判定需细化
- 修复方向：feasibility 判据用 AUV 瞬时 z_s 而非起点（留到 P2 T2.3）

### 8.3 阴影超出量程
S1-S5 场景下 h ∈ [1.2, 2.5], z_s=4.5, d ∈ [10, 15] ⇒ L_s = d*h/(z_s-h) ∈ [5.3, 15.0]
- 当 L_s + d > range_max (= 25)：阴影被截断
- 例：S1 h=2.5, d=10 ⇒ L_s=15, L_s + d = 25 ⇒ 临界
- 当前 shadow.py V5.2 **物理 L_s 保留**，绘制时用 `min(rho_end, range_max)` 截断，反演用物理 L_s
- 影响：反演 h 与真值自洽（数学恒等）

## 9. 下一步

1. **P★ 入口**：
   - X0 observability 四分类判据（含 insufficient）
   - X3 CRLB 验证（用 S1 数据扫 φ 与 N）
   - X5 baseline_zhou_shadow.py（学习式基线）
   - X6 baseline_aykin_carve.py（空间雕刻基线）
2. **P2 创新一**：
   - T2.1 w 交替 + GNC 防塌缩
   - T2.2 各向异性白化
   - T2.3 可观测性度量升级
3. **P3 创新二**：
   - T3.1 阴影几何量测
   - T3.2 局部海底平面拟合
   - T3.3 h→仰角先验转换
   - T3.4 κ 门控注入
4. **R 真实数据**：
   - R1 watertank-segmentation 目标分割
   - R4 turntable-cropped 复现 Aykin 结论
   - R5 quarry-fullsize 阴影→高度定性验证

---

*生成于 2026-09-04，由 `gen_scenes_v2.py` 一键跑出。*
