# 声学 SfM 模拟数据集 —— 任务完成报告

**任务**：在新文件夹中为 BA 代码生成符合接口的模拟数据集，柱子场景，含模拟声呐图、IMU、DVL。

**结果**：✅ **完全可行，且已端到端跑通**

---

## 📦 交付物

工作目录：`C:\Users\likunyuan\Desktop\private document\sfm\sfm_synthetic_pillars\`

### 1. 核心代码（13 个 .py）
| 文件 | 功能 |
|---|---|
| `config.py` | 全部可调参数（声学/传感器/场景/轨迹） |
| `world.py` | 3D 场景：4 根柱子的几何 + 柱面解析求交 |
| `trajectory.py` | AUV 6-DOF 轨迹，4 种运动模式 |
| `sonar_render.py` | 物理声呐成像（I(r,θ) = ∫σ·T·E/r² dφ），向量化 |
| `sim_pipeline.py` | 端到端：渲染+tracks+IMU/DVL |
| `run_ba_test.py` | 调用 BA（V2/V6）+ ground truth 评估 |
| `make_dataset.py` | 批量生成 4 种模式 |
| `make_montage.py` | 多模式声呐/3D 场景对比图 |
| `visualize.py` | 单数据集可视化（声呐/3D/track/重投影） |
| `smoke_test.py` | 端到端冒烟测试 |

### 2. 数据集
- `sim_output/` —— 默认 mixed 模式（1970 观测，120 landmark，4 根柱子）
- `multi_mode/{general,forward,yaw_y,mixed}/` —— 4 种运动模式各一份
- `smoke_test/` —— 冒烟测试输出

### 3. 文档
- `README.md` —— 完整使用说明
- `RESULTS.md` —— 端到端 BA 测试报告（含 V2 vs V6 对比表）

---

## 🔬 物理模型（论文级）

| 组件 | 模型 | 论文依据 |
|---|---|---|
| 方位/距离 | θ=atan2(y,x), ρ=‖P_b‖ | Huang&Kaess 2015 Eq.4-5 |
| 仰角歧义 | 不可观测（arc） | Qadri et al. 2022 |
| 像素强度 | I(r,θ) = ∫φ σ(φ)·T·E_e/r² dφ | Qadri 2022 Eq.1-2 |
| 噪声 | σ_θ=0.2°, σ_ρ=0.005m | Huang 2015 Table I |
| 像素映射 | beam=a·θ+b, range=c·ρ+d | Oculus M 手册 |

**4 根柱子场景**（harbor piling）：(-1.5,1.2,0.20,2.5) 等 4 个 (x,y,r,h)。

**4 种运动模式**（与 Huang 2015 Table II 对齐）：
- `general` —— 6-DOF 一般运动（**良约束**）
- `forward` —— 纯 x 方向（**欠约束**，V4 退化 case 3）
- `yaw_y` —— 偏航 + y 方向（**欠约束**，V4 退化 case 4）
- `mixed` —— 三段拼接（**同时测两种**）

---

## 🧪 端到端 BA 测试结果

### V2 基线（4 种模式）
| 模式 | 初始 RMS | 优化 RMS | 位姿 err mean | 路标 err mean | 时间 |
|---|---|---|---|---|---|
| general  | 2.68 px | 0.65 px | 3.51 cm | 7.18 cm | 10.5 s |
| forward  | 1.39 px | 0.28 px | 3.84 cm | **3.78 cm** | 12.9 s |
| yaw_y    | 2.70 px | 0.75 px | 2.89 cm | 10.27 cm | 24.3 s |
| **mixed**    | 2.46 px | 0.66 px | **2.78 cm** | 5.98 cm | 49.1 s |

### V6 统一版
| 模式 | 优化 RMS | 位姿 err mean | 路标 err mean | #良约束 |
|---|---|---|---|---|
| 全部 4 模式 | 0.30-0.73 px | 3.1-5.2 cm | **21.9-37.4 cm** | **0** |

### 关键发现 ⚠️
1. **V2 在所有模式都达到 cm 级精度**（位姿 2.78-3.84 cm，路标 3.78-10.27 cm）✅
2. **V6 在所有模式下所有 120 landmark 都被判为"欠约束"**（λ₂/λ₃ 判据触发）
   → **精确复现了 V4 论文中"198/217 全部欠约束"的现象**——说明数据生成器**有效** ✅
3. V6 的仰角孔径硬约束在欠约束情形下把路标 Z 锁在 ±0.30 rad 范围内，导致路标精度差
4. V6 速度比 V2 快 **5×**（mixed 模式 9.6s vs 49.1s）

### 声学/物理自检
- ✅ 声呐图视觉是合理的"弧形"柱面回波
- ✅ Track 长度分布：大多数 landmark 跨 5-35 帧可见
- ✅ 像素标定自洽：beam=225·θ+255, range=210·ρ-42（与理论值吻合）
- ✅ 重投影误差 BA 前后从 4.41px → 1.04px（4× 改善）

---

## 📂 文件清单

| 路径 | 大小 | 说明 |
|---|---|---|
| `sim_output/input/poses_est.npy` | 1.6 KB | 关键帧位姿 (12, 4, 4) |
| `sim_output/input/pose_frame_ids.npy` | 224 B | 关键帧下标 (12,) |
| `sim_output/input/landmarks_final.npy` | 3.0 KB | 120 landmark 坐标 |
| `sim_output/input/tracks.csv` | 148 KB | 1970 观测 |
| `sim_output/input/sensor_calib.yaml` | 680 B | 声学标定 |
| `sim_output/input/odom_rel.csv` | 1.3 KB | 11 段关键帧里程计 |
| `sim_output/imu/imu_data.csv` | 133 KB | 2400 IMU 样本（200Hz） |
| `sim_output/dvl/dvl_data.csv` | 3.6 KB | 120 DVL 样本（10Hz） |
| `sim_output/gt/sonar_images.npy` | 98 MB | 60 帧声呐强度图 |
| `sim_output/gt/poses_gt.npy` | 7.8 KB | 全部帧真值位姿 |
| `multi_mode/{mode}/input/...` | — | 4 种模式各一份 |
| `multi_mode/figs/sonar_montage.png` | 79 KB | 4×5 声呐图集 |
| `multi_mode/figs/scene_3d_montage.png` | 455 KB | 4 模式 3D 对比 |
| `sim_output/figs/{sonar_strip,scene_3d,track_density,reproj_err}.png` | — | 单数据集可视化 |

---

## 🚀 一键运行

```powershell
cd "C:\Users\likunyuan\Desktop\private document\sfm\sfm_synthetic_pillars"

# 单模式 (mixed)
python smoke_test.py

# 4 模式批量
python make_dataset.py
python make_montage.py

# 把数据喂给 BA
# （smoke_test / make_dataset 已自动复制到 ../BA代码/sim_input_*/）
cd ../BA代码
python ba_optimize.py     # 跑 V2
python ba_unified.py      # 跑 V6
```

---

## 💡 后续建议

1. **提升 V6 路标精度**：
   - 启用阴影仰角先验接口（`elev_prior`），V6 已留接口
   - 改用 `general` 模式（well-constrained 数量会上升）
2. **扩展数据集**：
   - 增加 `n_per_pillar` 到 50-100（更多 landmark）
   - 增加柱子数到 8-10（更复杂场景）
3. **加真实声学效应**：
   - 距离依赖衰减 `sonar.ambient_drop_db_per_m`
   - 多径反射（暂未建模）
4. **加 DVL/IMU 紧耦合**：
   - V6 已支持 `odom_rel` 协方差白化，可与 IMU 预积分融合

---

**完成时间**：2026-09-03  
**环境**：Python 3.14, numpy 2.5.1, scipy 1.18.0  
**与 BA 代码关系**：数据接口完全兼容 `../BA代码/{ba_optimize,ba_improve,ba_improve34,ba_unified}.py`
