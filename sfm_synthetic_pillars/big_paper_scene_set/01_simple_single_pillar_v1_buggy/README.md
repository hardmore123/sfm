# 单根柱子（最简）

**目录**：`01_simple_single_pillar/`  **类别**：`simple`

## 用途

最简几何，sanity check

## 数据规模

- 帧数: 120
- 关键帧: 6
- 目标数: 1
- Landmark: 30
- 观测总数: 1657
- 关键帧观测: 144
- 目标像素: 6369
- 阴影像素: 3714878

## 声学配置

- beam_count: 512
- range_bin_count: 800
- 方位视场: (-65.0, 65.0)
- 仰角孔径: (-17.0, 17.0)
- 距离: [0.2, 6.0] m
- 散斑 σ: 0.2
- 噪声底: 45.0 dB

## 文件清单

- `input/` — 创新一输入（4 件套）
- `gt/` — ground truth（位姿/landmark/声呐图）
- `innovation1/` — 创新一后处理（可观测性+曲面）
- `innovation2/` — 创新二输出（掩码+阴影+高度反演）
- `segmentation_data/` — 语义分割训练数据
- `imu/imu_data.csv` — IMU 仿真
- `dvl/dvl_data.csv` — DVL 仿真
- `meta.json` — 完整摘要

## 适用实验

- **创新一·M1 软关联置信度**：在最小场景下验证置信度权重机制
- **创新一·M2 球坐标+视场**：单/双目标基础 sanity check
- **球 vs 柱**：对比声学阴影在不同几何下的形态差异
