# `02_代码/` 说明

## 为什么是扁平布局

这些模块之间是平级 `import`（`from config import Config`），分子目录会直接断链。
分组信息放在下面的表里，不放在目录结构里。

## 与原始工作区的关系

**所有 `.py` 与原始工作区逐字节相同**（仅去掉了 4 个文件的 UTF-8 BOM，不影响语义），
以保证它们仍是"通过验收的那一版"。唯一新增的是 `_setup_data.py`（建立数据布局）。

## 先跑这个

```powershell
python _setup_data.py
```

建立 4 个目录联接（不复制数据）+ 补一份 `_f8_sceneset_design.json`。移动过目录后重跑即可。

---

## 模块分组

### A. 仿真基础

| 文件 | 职责 | 踩过的坑 |
|---|---|---|
| `config.py` | 声呐 / 噪声 / 场景 / 轨迹配置 | 改完 sonar 参数后**必须**调 `finalize_pixel_mapping(cfg)`，否则像素映射还是旧的 |
| `world.py` | 场景几何 + 地标采样 | `SceneWorld(cfg)` 从 `cfg.scene` 构建，**不接受** `pillars=` 之类关键字参数 |
| `trajectory.py` | `make_poses(cfg) → (poses6, poses_T)` | 起伏是 `sin(2π·t·0.5)`，**半周期单侧** $z\in[z_s,z_s+A]$，不是 $[z_s-A,z_s+A]$；横滚 `0.05·sin(2πt)` = **2.9° 硬编码**，与 `pitch_amplitude` 无关 |
| `sonar_render.py` | 图像强度渲染 | |
| `sim_pipeline.py` | 端到端仿真 → BA 接口文件 | `tracks.csv` 的 `rho_m` 是**连续浮点**，只有 `range_index` 取整 ⇒ ★I 链的 $\sigma_\rho$ 是注入值，量化不进入 |

### B. 阴影渲染与高度反演（★II 主链）

| 文件 | 效力 | 说明 |
|---|---|---|
| **`shadow_f8_fixed.py`** | ✅ | 修正版。孔径判定用体系俯角；未照亮/被遮挡分开；精确圆柱轮廓遮挡；$L_s$ 从掩码量测 |
| `shadow.py` | ⚠️ 仅作依赖 | 渲染函数已被取代，但其几何辅助函数（`_beam_grid_rad`、`_object_target_z` 等）仍被 `shadow_f8_fixed` 引用，**不能删** |
| `height_inversion.py` | ⚠️ 仅追溯 | 旧反演（V1 简化式 + V2 精确式）。V2 路径受 Q1 恒等式影响 |

`shadow_f8_fixed.py` 的四个关键接口：

```python
# 1) 渲染：三类掩码分开输出
render_shadow_map_fixed(T_wb, world, cfg, azim_pad=0.0) -> ShadowRender
#   shadow_mask  该门海底在孔径内 + 被遮挡      ⇒ 真阴影
#   unlit_mask   该门海底不在孔径内             ⇒ 未照亮（**不是**阴影）
#   floor_mask   该门海底在孔径内 + 未被遮挡    ⇒ 有回波
#   azim_pad=0 是中心射线模型（与暴力射线法一致）；原码硬编码 0.5°，宽了 4 倍

# 2) 量测：从掩码找远端跳变，禁止读解析值
measure_shadow_far_edge(shadow_col, floor_col, rngs_m,
                        intensity_col=None, sub_bin=True) -> rho_end
#   会跳过中间的 unlit 门；返回 NaN 表示远端不可测（被孔径或量程截断）

# 3) 反演
invert_height_from_far_edge(rho_end, D_t, z_s) -> h
#   h = z_s(1 − D_t/D_e),  D_e = sqrt(rho_end² − z_s²)
#   ⚠️ D_t 必须传**轮廓远边缘** D_far = 柱心 + r，不是柱心！
#      差一个半径会引入 +r 量级偏置（本构型 +8.4 cm，见 Q6.3）

# 4) 不确定度传播（三项独立）
sigma_h_from_far_edge(rho_end, D_t, z_s, sigma_rho, sigma_Dt, sigma_zs) -> sigma_h
#   sigma_Dt / sigma_zs 来自 ★I(BA)，必须显式记账，否则漏项
```

**遮挡判据的精确解**（有限尺寸圆柱，沿波束中心射线）：

```
弦解：   d = d_h·cos(Δθ) ± sqrt(r² − d_h²·sin²(Δθ))
        d_near = base − half   （高光/leading edge 在这里）
        d_far  = base + half   （**阴影长度由这里决定**）
遮挡：   跳过条件  D <= d_near
        临界点    x_test = min(d_far, D)
        被挡 ⇔    z_s·(1 − x_test/D) < t_top
```

注意 `x_test = min(d_far, D)`：当海底点水平距**落在足迹内**（$d_{\rm near}<D<d_{\rm far}$）时也会被挡。
漏掉这一段就是 Q6.4。

### C. 判据（★I 主链）

| 文件 | 关键接口 | 说明 |
|---|---|---|
| `feasibility.py` | `min_elev_spread(σ_ρ, N, τ_z)` | 返回的是对 $\operatorname{std}(\varphi_k)$ 的门限，**不是**对 $\lvert\varphi\rvert$ 的门限 |
| | `tau_z_crit(σ_ρ, N, φ_max)` | $\sqrt3\sigma_\rho/(\sqrt N\varphi_{\max})$ |
| | `blind_landmark_fraction(std_phi_per_landmark, ...)` | **经验量**，须传该轨迹下每个地标实际的 $\operatorname{std}(\varphi_{jk})$ |
| | `resolve_sigma_rho(meta, strict=False)` | 按台账解析；缺失告警，`strict=True` 报错（防静默默认值） |
| | `sigma_rho_bin_limited` / `sigma_rho_bandwidth_limited` | 采样受限 / 带宽受限分辨率 |
| | `check_feasibility(...)` | 包线四约束，返回 `binding_constraint` |
| | `aris_main_profile(N)` / `aris_wide_profile(N)` | 孔径能力剖面（只报孔径能决定的量） |
| | ~~`blind_fraction_curve`~~ | **已作废**，调用抛 `NotImplementedError` |
| | ~~`blind_angle_std`~~ | 已弃用别名，调用发 `DeprecationWarning` |
| `observability.py` | Fisher 信息 / $\sigma_{P_z}$ / 四分类 | 雅可比已修正为体坐标系（`@ R.T`）并做白化 |
| `_f8_design_sceneset.py` | `check` / `check_heave` / `frame_feasible` / `geom` / `std_phi_of_heave` / `heave_z` | 有 `__main__` 保护，import 无副作用。`geom` 已含柱半径修正 |

**两个容易混的角**（混用会同时错两处，见 Q6.1）：

| 用途 | 用哪个 | 为什么 |
|---|---|---|
| 孔径可见性 | **体系**俯角 `arctan2(P_b[2], hypot(P_b[0],P_b[1]))`，$P_b=R_{wb}^\top(P_w-t_{wb})$ | 孔径固连于声呐 |
| CRLB 的 $\operatorname{std}(\varphi)$ | **世界系射线**俯角 | 决定雅可比零空间方向的是射线方向。纯旋转不改变射线 ⇒ 静态下俯不改善 $\sigma_{P_z}$ |

### D. 场景设计与生成

| 文件 | 说明 |
|---|---|
| `_f8_design_sceneset.py` | 主档几何设计 + 约束搜索。直接运行会输出可行域表并落盘 `_f8_sceneset_design.json` |
| `gen_scenes_main_f8.py` | 生成 `scene_set_main_f8/`（5 场景，约 8 分钟）。`obs/` = 可观测量（反演只许读这里）、`gt/` = 真值（仅评估）、`innov2/` = 反演结果 |
| `f8_design_geometry.py` | 早期可行域搜索（约束集为 v1，**已被 `_f8_design_sceneset.py` 取代**，保留追溯） |
| `scene_configs.py` | 旧场景表。被 `feasibility.py:429` 懒加载引用（函数内 import，核心功能不依赖） |
| `big_paper_sim.py` | 早期大规模仿真主程序。**未经本轮审计** |

### E. 稠密化（★II-2）

| 文件 | 说明 |
|---|---|
| `R_x6_carve_fixed.py` | 修正版空间雕刻：`alive=ones` + **AND** 删除 + `rows.min()`。原实现 AND/OR 方向反了（P4） |
| `surface_recon.py` | 表面重建（需 `open3d`） |

### F. BA（★I 的位姿与稀疏点来源）

`ba_optimize.py`、`ba_improve.py`、`ba_improve34.py`、`ba_unified.py`、`ba_patent.py`、`view3d.py`

> ⚠️ 这几个是既有代码，**尚未纳入 F-8 验证体系**，结果未经本轮审计。
> ★I-1 还缺的"BA 侧实测"（R-X3）就是要用它们来做。

---

## 验证脚本与数据依赖

| 脚本 | 需要的数据 | 备注 |
|---|---|---|
| `verify_f2_blind_semantics.py` | 无 | |
| `verify_f7_sigma_rho_ledger.py` | `scene_set_v2/S1_*/meta.json` | 联接到原工作区 |
| `verify_observability_theory.py` | 无 | |
| `verify_sigma_h_propagation.py` | `scene_set_v2/` | 同上 |
| `verify_f8a_shadow_aperture.py` | 无 | |
| `verify_f8_fixed.py` | 无（自建最小场景） | |
| `verify_f8_sceneset_design.py` | `_f8_sceneset_design.json` | `_setup_data.py` 会补 |
| `verify_f8d_sceneset.py` | `scene_set_main_f8/` | 交付内 |
| `verify_x6_carve_logic.py` | 无 | |
| `verify_x6_roll_vs_straight.py` | 无 | |
| `f8_probe_identity.py` | 无（纯符号+数据两段，数据段容错） | Q1 取证 |
| `f8_probe_sigma_rho.py` | `scene_set_main/`、`scene_set_v2/` | 联接 |
| `f8_probe_shadow_visibility.py` | 旧场景集的 `.npy`（**GB 级，未复制**） | 结论已固化在 Q1–Q6 审计文档 |
| `f8_design_geometry.py` | 无 | |

跑 `_setup_data.py` 后，以上 14 个脚本**实测全部 exit 0**。

## 依赖

- 必需：Python 3.11+、`numpy`
- 可选：`open3d`（仅 `surface_recon.py` / `big_paper_sim.py` 的点云导出）
- **不需要** `pandas`（探针脚本已改用标准库 `csv`）
