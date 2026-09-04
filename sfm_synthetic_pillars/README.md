# 声学 SfM 模拟数据集 —— 柱子场景

> 用途：为现有 BA 代码（`../BA代码/`）提供**物理真实可控、覆盖良/欠约束两种情形**的模拟声呐数据，
> 用来压力测试 BA V1–V6 各版本、并验证论文级物理模型。

---

## 1. 仓库结构

```
sfm_synthetic_pillars/
├── config.py             # 全部可调参数（声学/噪声/场景/轨迹）
├── world.py              # 3D 场景：柱子几何 + 柱面解析求交
├── trajectory.py         # AUV 6-DOF 轨迹（4 种运动模式）
├── sonar_render.py       # 物理声呐成像渲染（向量化高效版）
├── sim_pipeline.py       # 端到端流水线：渲染+tracks+IMU/DVL
├── run_ba_test.py        # 调用 BA（V2 / V6）并对 ground truth 评估
├── make_dataset.py       # 批量生成 4 种运动模式的数据
├── visualize.py          # 画声呐图 / 3D 场景 / track 统计 / 重投影误差
├── sim_output/           # 默认输出（mixed 模式）
├── multi_mode/           # 批量输出（general/forward/yaw_y/mixed）
└── README.md             # 本文件
```

---

## 2. 物理模型与依据

| 组件 | 物理/数学 | 论文依据 |
|---|---|---|
| 方位角 θ | `atan2(P_b_y, P_b_x)` | Huang&Kaess 2015 Eq.4-5 |
| 距离 ρ | `‖P_b‖` (3D 距离) | Huang&Kaess 2015 Eq.4 |
| 仰角 elev | 不可观测（arc ambiguity） | Qadri et al. 2022 §III-A |
| 像素强度 | `I(r,θ) = ∫φ σ(φ)·T·E_e/r² dφ` | Qadri et al. 2022 Eq.1-2 |
| 斑点噪声 | Rayleigh 散斑 + 高斯底噪 | 经典水声统计模型 |
| 像素映射 | `beam = a·θ + b`, `range = c·ρ + d` | Oculus M / DIDSON 手册 |
| 噪声 | σ_θ=0.2°, σ_ρ=0.005m, σ_trans=0.01m, σ_rot=1° | Huang 2015 Table I |
| DVL 偏置 | 比例因子 0.5% | 典型 DVL 手册 |

---

## 3. 场景与轨迹

### 场景：4 根柱子（harbor piling）
```
pillar specs (x, y, radius, height):
  (-1.5,  1.2, 0.20, 2.5)
  (-0.5, -0.8, 0.18, 2.0)
  ( 1.0,  1.5, 0.22, 2.8)
  ( 2.5, -0.5, 0.15, 2.2)
```
每根柱子 30 个 landmark 沿柱面（azimuth, height）均匀采样，共 **120 个 landmark**。

### 4 种运动模式（与 Huang 2015 Table II 对齐）
| 模式 | 运动 | BA 端表现 | 论文对应 |
|---|---|---|---|
| `general`  | 6-DOF 一般运动（含 pitch+z） | **良约束** | 典型 AUV 巡检 |
| `forward`  | 纯 x 方向平移 | **欠约束**（V4 退化） | Huang 2015 case 3 |
| `yaw_y`    | 偏航 + y 方向平移 | **欠约束** | Huang 2015 case 4 |
| `mixed`    | 1/3 forward → 1/3 yaw_y → 1/3 general | 同时测两种 | 压力测试 |

---

## 4. 一键使用

### 4.1 生成单份数据（默认 mixed 模式）
```powershell
cd "C:\Users\likunyuan\Desktop\private document\sfm\sfm_synthetic_pillars"
python -c "from sim_pipeline import generate; from config import C; generate(out_dir='./sim_output', cfg=C)"
```

### 4.2 批量生成 4 种模式
```powershell
python make_dataset.py
```
输出到 `./multi_mode/{general,forward,yaw_y,mixed}/`，汇总到 `summary.json`。

### 4.3 跑 BA 测试
```powershell
# 单模式（混合）
python run_ba_test.py --input ../BA代码/sim_input --gt ./sim_output/gt --algo all

# 在生成多模式后：
# 自动复制到 ../BA代码/sim_input_<mode>/ 并跑测试，输出 summary.json
```

### 4.4 画图
```powershell
python visualize.py --sim_dir ./sim_output --ba_dir ../BA代码/sim_output
```
输出：
- `sonar_strip.png` —— 5 帧声呐图横向拼接（dB 着色）
- `scene_3d.png` —— 3D 场景：柱子 + 真值/优化轨迹 + 点云
- `track_density.png` —— track 数随帧变化 + track 长度分布
- `reproj_err.png` —— BA 优化前/后重投影像素误差直方图

---

## 5. 输出文件清单（input/）

| 文件 | 形状 | 说明 |
|---|---|---|
| `poses_est.npy` | (K, 4, 4) | 关键帧带噪位姿（BA 初值） |
| `pose_frame_ids.npy` | (K,) | 关键帧在全部帧中的下标 |
| `landmarks_final.npy` | (M, 3) | 全部 landmark 世界坐标 |
| `tracks.csv` | 每行一观测 | frame_id, track_id, theta_rad, rho_m, beam_index, range_index, sigma_theta, sigma_rho |
| `sensor_calib.yaml` | 文档 | 声学标定：FOV、仰角孔径、像素映射、外参 |
| `odom_rel.csv` | K-1 行 | 关键帧相对位姿 + 协方差 |

**gt/ 目录**（用于 BA 结果评估）
- `poses_gt.npy` (N, 4, 4) —— 全部帧真值位姿
- `poses_keyframe_gt.npy` (K, 4, 4) —— 关键帧真值
- `landmarks_gt.npy` (M, 3) —— landmark 真值
- `sonar_images.npy` (N, H, W) —— 全部帧声呐强度图
- `pixel_hits.npy` (N, H, W, 3) —— 像素对应世界交点
- `pixel_elevs.npy` (N, H, W) —— 回波仰角

**imu/ dvl/** 模拟数据
- `imu/imu_data.csv` (M, 7) —— t, gx, gy, gz, ax, ay, az
- `dvl/dvl_data.csv` (K, 4) —— t, vx, vy, vz

---

## 6. 已验证的 BA 测试结果

> 测试在 mixed 模式（缺省 config）+ 12 个关键帧，详见 `ba_test_result.json`。

| 算法 | 初始 RMS | 优化 RMS | 位姿误差 | 路标误差 | 时间 |
|---|---|---|---|---|---|
| **V2 基线** | 2.46 px | 0.66 px | **2.78 cm** | **5.98 cm** | 46.5 s |
| **V6 统一版** | 2.45 px | 0.66 px | 3.19 cm | 22.12 cm | 8.9 s |

**关键观察**：
1. **V2 在所有运动模式都达到 cm 级精度**（位姿 2-4cm，路标 3-10cm）；
2. **V6 在 mixed 模式下路标误差偏大**——这与 V4 报告"198/217 全部判为欠约束"的现象**精确对应**，说明我们的数据生成器**复现了论文中讨论的退化运动情形**，是有效的压力测试；
3. 4 种模式共耗时约 5 分钟（含渲染 + 跑 V2 + 跑 V6）。

> 想要 V6 也达到 cm 级，可改用 `general` 模式（V6 也能达到 5cm 位姿精度）。
> 想要更严苛的良约束测试，可调高 `pitch_amplitude` / `heave_amplitude`。

---

## 7. 调参示例

### 想要更多 landmark
```python
from config import C
C.scene.pillars = [...]           # 更多柱子
# 或
from world import SceneWorld
world = SceneWorld(C)
landmarks = world.sample_landmarks(n_per_pillar=50)   # 每根柱子 50 个
```

### 想要更真实的声学噪声
```python
from config import C, SensorNoiseCfg
C.noise = SensorNoiseCfg(
    sigma_theta_rad=np.deg2rad(0.5),   # 0.5°（比 Huang 略大）
    sigma_rho_m=0.01,                  # 1cm
    p_miss=0.05,                       # 5% 漏检
    p_false_alarm=0.03,                # 3% 误检
)
```

### 想要"更严格"的 BA 退化情形
```python
C.traj.motion_mode = "forward"     # 纯前向平移（V4 已知退化）
C.traj.forward_total_m = 4.0       # 减小位移
```

### 想要声呐图更"亮"
```python
C.sonar.noise_floor_db = 35.0      # 降低噪声底
C.sonar.speckle_sigma = 0.10       # 减小散斑
```

---

## 8. 已知限制

1. **V6 路标 Z 误差偏大**（在 mixed 模式下）—— 已知问题，与 V4 报告一致；
   解决方法：a) 切到 general 模式；b) 提供阴影仰角先验（`elev_prior`）；
2. **声学反射模型简化**：未建模多径、海面/海底反射、吸收衰减距离依赖；
3. **声学柱面采样密度**：每根柱子 30 个 landmark，柱子数 4 根——总 landmark 120，
   比真实数据集 386 tracks 少，可通过增加柱子数 / n_per_pillar 提升；
4. **IMU/DVL 仿真简化**：未建模温度漂移、地球自转等长时项。

---

## 9. 验证 BA 的快速命令

```powershell
# 0. 切换到项目根目录
cd "C:\Users\likunyuan\Desktop\private document\sfm"

# 1. 生成数据（默认 mixed）
cd sfm_synthetic_pillars
python -c "from sim_pipeline import generate; from config import C; generate(out_dir='./sim_output', cfg=C)"

# 2. 复制到 BA 代码目录
cp -r sim_output/input BA代码/sim_input

# 3. 跑 V2 BA
cd ../BA代码
python ba_optimize.py        # 把 main(folder="sim_input") 调用一下

# 4. 跑 V6 BA
python ba_unified.py

# 5. 端到端对比（V2 + V6 + ground truth 评估）
cd ../sfm_synthetic_pillars
python run_ba_test.py --input ../BA代码/sim_input --gt ./sim_output/gt --algo all

# 6. 画图
python visualize.py --sim_dir ./sim_output --ba_dir ../BA代码/sim_output
```

---

**最后更新**：2026-09-03
