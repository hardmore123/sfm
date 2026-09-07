# `04_数据/` 说明

## `scene_set_main_f8/` —— 唯一有效场景集

469 MB / 61 个文件。**这是目前唯一经审计确认无真值泄漏、且传感器参数全部落在
ARIS Explorer 3000 规格内的场景集。**

由 `02_代码/gen_scenes_main_f8.py` 确定性生成（固定种子），可随时重建：

```powershell
cd ..\02_代码
python _setup_data.py           # 若尚未建立联接
python gen_scenes_main_f8.py    # 约 8 分钟
```

### 传感器参数（逐项对照 ARIS 规格）

| 项 | 值 | ARIS Explorer 3000 规格 | 合规 |
|---|---|---|---|
| 垂直孔径 | ±7.5° | 垂直波束宽度 14–15° | ✅ |
| 方位孔径 | 30° | 30° | ✅ |
| 波束数 | 128 | 128 | ✅ |
| 量程 | 0.5–**15 m** | 探测模式（1.8 MHz）有效量程 **15 m** | ✅ |
| range bin | **1600** ⇒ $\Delta\rho_{\rm bin}=9.07$ mm | 距离分辨率 3–19 mm | ✅ 居中 |
| 下俯角 | 19° | 文档建议 15–20° | ✅ |
| $\sigma_\rho$（注入） | 10 mm | 3–19 mm 取中 | ✅ |

$\Rightarrow\ \tau_z^{\rm crit}=\dfrac{\sqrt3\times0.010}{\sqrt{60}\times0.1309}=4.18$ cm $\le\tau_z=5$ cm，**精度要求刚好可达**。

> 对照旧 `scene_set_main/`：$\rho_{\max}=40$ m（超规格 **2.7 倍**）、
> $\Delta\rho_{\rm bin}=65.9$ mm（超规格 **3.5 倍**）、`pitch=0` ⇒ $\tau_z^{\rm crit}=27.6$ cm，
> $\tau_z=5$ cm 完全不可达。

### 几何

$z_s=4.5$ m，$\theta_p=19°$，$D_t=10.6$ m，柱半径 $r=0.25$ m，60 帧。

派生量（含轮廓远边缘修正）：$u=z_s-h$、$D_e=\dfrac{(D_t+r)z_s}{u}$、
$\rho_{\rm target}=\sqrt{(D_t-r)^2+u^2}$、$\rho_{\rm end}=\sqrt{D_e^2+z_s^2}$。

$h=0.85$ 时：$L_s=3.03$ m（占 **334** 个 range bin，足够做亚 bin 量测）、$\rho_{\rm end}=14.11$ m ≤ 15 ✅。

### 五个场景

| 场景 | 角色 | $h$ | 起伏 $A$ | $\operatorname{std}\varphi$ | 分类 |
|---|---|---|---|---|---|
| `M1_well_constrained` | ★I-1 良约束基准 | 0.85 | 1.2 | 1.760° | 良约束（≥1.479°） |
| `M2_blind_low_spread` | ★I-1 盲（低离散度） | 0.85 | 0.1 | 0.152° | **盲** |
| `M3_envelope_inside` | ★I-2 包线内（距边 3 cm） | 1.05 | 1.2 | 1.783° | 可行 |
| `M4_envelope_outside` | ★I-2 包线外 | 1.12 | 1.2 | 1.790° | 部分列不可反演 |
| `M5_low_snr` | ★II 低 SNR | 0.85 | 1.2 | 1.760° | 可行 |

**两组对比对**：

- **M1 vs M2**（★I-1）：几何**完全相同**，只差轨迹起伏 ⇒ $\operatorname{std}(\varphi)$ 差 12 倍
- **M3 vs M4**（★I-2）：只差 7 cm 柱高，一个在包线内一个在外

包线内最大 $h=1.08$ m（binding 是**量程** $\rho_{\rm end}\le15$ m），故 1.05 在内、1.12 在外。

### 目录结构（每个场景）

```
M<n>_<name>/
├── meta.json                  ← 全部参数、可观测性、统计、反演结果、σ_ρ 溯源
├── obs/                       ← **传感器可观测量。反演只许读这里**
│   ├── target_masks.npy       (60, 1600, 128) bool  目标高光
│   ├── shadow_masks.npy       (60, 1600, 128) bool  真阴影（海底在孔径内 + 被遮挡）
│   ├── unlit_masks.npy        (60, 1600, 128) bool  未照亮（海底不在孔径内）
│   ├── floor_masks.npy        (60, 1600, 128) bool  有回波
│   └── target_elev_body.npy   (60, 1600, 128) f32   高光处**体系**俯角
├── gt/                        ← 真值，**仅供评估，禁止进反演路径**
│   ├── poses_gt.npy           (60, 6)
│   ├── pillar_top_gt.npy      (3,)
│   ├── phi_world_ray.npy      (60,)    世界系射线俯角
│   ├── frame_envelope_pred.npy         逐 (帧,列) 包线预测
│   └── frame_measured.npy              逐 (帧,列) 实测是否成功
└── innov2/
    └── measurements.npy       (n, 7)  [frame, col, ρ_end, D_far_ba, z_s_ba, h_inv, σ_h]
```

**`obs/` 与 `gt/` 的物理隔离是刻意设计**（C7）：旧实现把解析 $L_s$ 和 $D_t$ 写进 GT 图、
反演又去读，导致整条链退化成代数恒等式。现在反演路径只允许触碰 `obs/`。

`unlit_mask` 与 `shadow_mask` 分开也是刻意的：**"未照亮"与"被遮挡"物理含义不同**，
未照亮区不携带遮挡体的高度信息，不能进阴影反演。旧实现把两者混为一谈，
在旧构型下有 **91%** 的"阴影"像素实为未照亮区。

### 结果

| 场景 | 多视 $\sigma_{P_z}$ | 阴影 MAE | bias | $\sigma_h$ 预测 | (帧,列) 一致率 |
|---|---|---|---|---|---|
| M1 | 4.20 cm | 0.681 cm | +0.006 cm | 0.839 cm | 100%（TP=720） |
| **M2** | **48.57 cm** | **0.577 cm** | −0.020 cm | 0.716 cm | 100%（TP=720） |
| M3 | 4.15 cm | 0.638 cm | −0.047 cm | 0.813 cm | 100%（TP=720） |
| M4 | 4.13 cm | 0.637 cm | +0.013 cm | 0.814 cm | 100%（TP=668, **TN=52**） |
| M5 | 4.20 cm | 0.692 cm | −0.006 cm | 0.838 cm | 100%（TP=720） |

**M2 是关键场景**：多视 CRLB 给出 48.57 cm（差 $\tau_z=5$ cm 要求 10 倍），
阴影反演给出 0.577 cm。M1/M2 几何完全相同、只差起伏 ⇒ 这是"阴影是多视的必要补充"的直接证据。

**未照亮占比 67.5–78.3%**：±7.5° 孔径 + 19° 下俯的照明带只有斜距 $[10.09, 22.57]$ m，
与量程 $[0.5,15]$ m 相交后仅 $[10.09,15]$ m 有海底回波。

### 引用这些数字时

1. $\sigma_{P_z}$ 是**解析 CRLB**，不是跑 BA 实测的 —— 不得写成"BA 实测误差"
2. 720 条量测来自 60 帧 × 12 列，帧间几何高度相关（M2 近乎静止）—— **不得当独立样本**做显著性检验
3. bias 已经过轮廓远边缘修正。若误用柱心 $D_t$ 反演，偏置是 **+8.4 cm**（Q6.3）

---

## 未随本材料复制的数据

| 内容 | 位置 | 原因 |
|---|---|---|
| 真实数据集 1.43 GB（ARIS Explorer 3000） | `F:/sfm/数据集（不上传git）/marine-debris-fls-datasets-master/` | 第三方数据、体积大。清单见 `01_理论支撑/传感器规格/真实数据集_INVENTORY.md`：`watertank-segmentation` 1868 图+掩码+XML/12 类、`quarry-fullsize` 10 段/7209 帧（自然海底与阴影，无位姿真值）、`turntable-cropped` 18 类/4942 帧（转台角作位姿真值） |
| `scene_set_main/` 2.6 GB | `F:/sfm/sfm_synthetic_pillars/` | **★II 精度数字因 Q1 恒等式泄漏而失效**。几何/可观测性统计仍可用于说明"旧构型为何不合规"。`_setup_data.py` 会建立联接 |
| `scene_set_v2/` 739 MB | 同上 | 同上（敏感性档 ±17°，$\Delta\rho_{\rm bin}=40.9$ mm 超规格） |
| `innov2_ablations/` 657 MB | 同上 | 同上 |
| `big_paper_sim/` 8.6 GB、`big_paper_scene_set/` 5.9 GB、`_tmp_heave_baseline/` 2.8 GB | 同上 | 早期大规模仿真，**未经本轮审计**，状态未核 |
