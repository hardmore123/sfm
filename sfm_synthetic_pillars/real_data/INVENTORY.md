# 真实数据集资产清单

> **数据源**：`F:\sfm\数据集（不上传git）\marine-debris-fls-datasets-master\`
> **论文**：Valdenegro-Toro et al. *The Marine Debris Forward-Looking Sonar Datasets*, OCEANS 2025, arXiv:2503.22880
> **传感器**：ARIS Explorer 3000（详见 `ARIS_EXPLORER_3000_PARAMS.md`）
> **盘点时间**：2026-09-04
> **R0 阶段产出物**

---

## 〇、总体规模

- **总文件数**：20,122
- **总大小**：1.46 GB
- **子集数**：4（3 个含标注/位姿 + 1 个裁剪块）
- **最关键资产**：`watertank-segmentation`（1,868 张 + 12 类逐像素标注，**直接可用**）

---

## 一、子集清单

### 1.1 `watertank-segmentation` ⭐⭐⭐（最直接可用）

| 项 | 值 |
|----|-----|
| 文件数 | 5,606（1,868 图 + 1,868 掩码 + 1,868 XML 框 + 2 README/img） |
| 大小 | 0.12 GB |
| 图像 | 320×480, uint8, range [0, 252] |
| 标注 | 12 类逐像素掩码（0=bg, 1=bottle, 2=can, 3=chain, 4=drink-carton, 5=hook, 6=propeller, 7=shampoo-bottle, 8=standing-bottle, 9=tire, 10=valve, 11=wall） |
| 框标注 | 1,868 个 LabelMe XML（每类外接矩形） |
| 标准划分 | 70/30 = 1,495 train / 373 val（seed=42） |
| **对论文价值** | **直接可用**：创新二·模块1 目标分割的训练/验证数据 |
| 优先级 | **P0**（立刻用） |

### 1.2 `quarry-fullsize` ⭐⭐⭐（最高科学价值）

| 项 | 值 |
|----|-----|
| 文件数 | 7,210 |
| 大小 | 1.19 GB |
| 序列数 | 10 段（每段 264-2,341 帧，2016-06-22 采石场实地） |
| 总帧数 | 7,209 |
| 估计时长 | ~20 分钟（按 6 fps） |
| **位姿真值** | **无** |
| 物理环境 | 自然海底，**自然声学阴影** |
| **对论文价值** | **阴影反演真实验证**（R5 任务）、**多视几何真实验证**（R4 任务） |
| 优先级 | **P0**（R 轨最重要） |

### 1.3 `turntable-cropped` ⭐⭐（位姿近似已知）

| 项 | 值 |
|----|-----|
| 文件数 | 4,942 |
| 大小 | 0.10 GB |
| 物体类别 | 18 个（高类）/ 12 个（细类） |
| 总帧数（object-sideways） | 1,281 |
| 总帧数（含 platform） | 3,752 |
| **位姿真值** | **转台角等间隔**（每个物体 yaw_per_frame ≈ 1-4°，由帧数推算） |
| 三种模式 | object-sideways（仅物体）/ platform-sideways（含平台侧视）/ platform-standing（含平台正视） |
| **对论文价值** | **多视几何真实验证**（R4 任务最强牌）：相对位姿已知，BA 验证可量化 |
| 优先级 | **P1** |

### 1.4 `watertank-cropped` ⭐（基础验证用）

| 项 | 值 |
|----|-----|
| 文件数 | 2,364 |
| 大小 | 0.02 GB |
| 用途 | 分类/匹配任务的裁剪块 |
| **对论文价值** | 特征描述子验证（优先级低） |
| 优先级 | **P3** |

---

## 二、文件命名规范

### 2.1 `watertank-segmentation`

- 图：`marine-debris-aris3k-NNNN.png`（NNNN = 0..1867）
- 掩码：`marine-debris-aris3k-NNNN.png`（在 `Masks/`）
- 框标注：`marine-debris-aris3k-NNNN.xml`（在 `BoxAnnotations/`）

### 2.2 `quarry-fullsize`

- 序列目录：`YYYY-MM-DD_HHMMSS/`（10 个）
- 帧：`YYYY-MM-DD_HHMMSS-frameNNNNN.png`（5 位序号）

### 2.3 `turntable-cropped`

- 物体目录：`object_name/`
- 帧命名 3 种：
  - `object-sideways-frame-NNN.png`（仅物体）
  - `platform-sideways-frame-NNN.png`（含平台侧视）
  - `platform-standing-frame-NNN.png`（含平台正视）

---

## 三、与论文阶段的映射

按 `实施任务表_验收标准_阶段安排.md`：

| 任务 | 依赖子集 | 状态 |
|------|----------|------|
| R0 数据集接入 | 全部 4 个 | ✅ **完成**（本目录） |
| R1 watertank 分割基线 | watertank-segmentation | 待启动（T5.0 文献后） |
| R2 quarry 阴影类补标 | quarry-fullsize | 待启动（4 d） |
| R3 阴影分割评测 | R2 输出 | 待启动 |
| R4 turntable 多视验证 | turntable-cropped | 待启动（4 d） |
| R5 quarry 定性验证 | quarry-fullsize | 待启动（3 d） |
| R6 sim-to-real 落差 | R1-R5 全部 | 待启动 |

---

## 四、复现实验的命令

```python
import sys
sys.path.insert(0, 'F:/sfm/sfm_synthetic_pillars/real_data')
from loader import load_watertank_segmentation, load_quarry_fullsize, load_turntable_cropped

# 1) 拿 1,868 张 12 类标注（直接用于 ViT 训练）
w = load_watertank_segmentation(val_frac=0.2, seed=42)
print(w['train']['images'][:3])

# 2) 10 段连续序列
q = load_quarry_fullsize()
print(q['2016-06-22_143000']['frames'][:3])

# 3) 转台 18 类物体
t = load_turntable_cropped(crop='object')
print(t['can']['frames'][:3])
```

---

## 五、与 ARIS Explorer 3000 参数的一致性

| 数据集 | 是否符合 ARIS 物理 |
|--------|---------------------|
| watertank | ✅ ARIS 3MHz 识别模式，5m 内 |
| quarry | ✅ 实际 5-15m（探测模式 1.8MHz） |
| turntable | ✅ 5m 内（识别模式） |
| watertank-cropped | ✅ 同 watertank |

所有子集与 `ARIS_EXPLORER_3000_PARAMS.md` 物理一致。

---

*本清单为 R0 阶段产出物（与 `ARIS_EXPLORER_3000_PARAMS.md` 配套）。后续 R1-R5 的产出物（训练权重、补标集、验证报告）将放在 `real_data/results/` 子目录。*
