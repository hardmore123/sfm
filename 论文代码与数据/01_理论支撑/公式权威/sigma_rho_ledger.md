# σ_ρ 台账（测距噪声口径的唯一来源）

> 任务 F-7。**所有涉及 $\sigma_\rho$ 的脚本一律从本台账取值，禁止硬编码。**
> 起因：审计 20260905 P6 发现三处口径不一致——ARIS 规格 3–19 mm、X3 用 0.05 m、场景采样 41.7 mm。
> 而 $\tau_z^{\text{crit}}=\sqrt3\sigma_\rho/(\sqrt N\varphi_{\max})$ 与 $\Delta\varphi_{\min}=\sigma_\rho/(\sqrt N\tau_z)$ **均正比于 $\sigma_\rho$**，口径不统一则所有数字不可比。
> 版本：2026-09-05

---

## 1. 为什么必须统一

$\sigma_\rho$ 直接线性缩放两个核心量：

| 量 | 公式 | $\sigma_\rho$ 从 10 mm 变 50 mm 的后果 |
|---|---|---|
| 精度硬上限 | $\tau_z^{\text{crit}}=\sqrt3\sigma_\rho/(\sqrt N\varphi_{\max})$ | 4.2 cm → **20.9 cm**（结论从"刚好可达"变成"完全不可达"） |
| 离散度门限 | $\Delta\varphi_{\min}=\sigma_\rho/(\sqrt N\tau_z)$ | 3.62° → **18.1°**（超出 ARIS 孔径 ⇒ 全盲） |

**同一批实验若混用两个值，结论会相互矛盾。**

---

## 1b. ⚠️ 两条创新链的 σ_ρ 口径必须分开（2026-09-06 修订）

初版台账把两条链混为一条，实测发现二者的观测量根本不同：

| 链 | 观测量 | 在 pipeline 中的形态 | 有效 $\sigma_\rho$ |
|---|---|---|---|
| **★I-1 多视 CRLB** | 斜距 $\rho$ | `tracks.csv` 的 `rho_m` 是**连续浮点**（`rhos + N(0,σ)`），只有 `range_index` 被取整 | **= 注入噪声**，range bin 不进入 |
| **★II-1 阴影反演** | 阴影长度 $L_s$ | 在图像上沿距离轴数 bin（leading/trailing edge） | **受 $\Delta\rho_{\rm bin}$ 量化限制** |

**依据**（`sim_pipeline.py:118-122`）：

```python
rh = float(rhos[f, j] + rng.normal(0, cfg.noise.sigma_rho_m))   # 连续
rng_idx = pm["range"]["c"] * rh + pm["range"]["d"]
ri = float(np.clip(np.round(rng_idx), 0, H - 1))                # 仅索引取整
out_rows.append({... "rho_m": rh, "range_index": ri ...})       # 两者都存
```

下游若读 `rho_m` ⇒ $\sigma_\rho$ = 注入值；若读 `range_index` 反解 ⇒ 还要叠加量化项
$\sqrt{\sigma_{\rm inj}^2+\Delta\rho_{\rm bin}^2/12}$。

> **量化误差的标准差是 $\Delta/\sqrt{12}$，不是 $\Delta$。** 初版台账把 `sigma_rho_bin_limited`
> 的返回值（bin 宽度）直接当作 $\sigma_\rho$，对**噪声**而言高估了 $\sqrt{12}\approx3.46$ 倍。
> 但把 bin 宽度当作**分辨率**与 ARIS 规格 3–19 mm 对表是正确的——规格给的就是分辨率。
> 故：**与 ARIS 规格对表用 bin 宽度；代入 CRLB 当噪声用 $\Delta/\sqrt{12}$。**

---

## 2. 台账（按用途固定取值）

| 用途 | $\sigma_\rho$ | 依据 | 使用者 |
|---|---|---|---|
| **主档理论计算** | **10 mm** | ARIS Explorer 3000 规格 3–19 mm 取中（`real_data/ARIS_EXPLORER_3000_PARAMS.md`） | `feasibility.ARIS_MAIN`、$\tau_z^{\text{crit}}$ 表、盲区判据 |
| **主档仿真** | $\max\big(c/2B,\ \Delta\rho_{\rm bin}\big)$ | 物理分辨率 $c/2B=2.5$ mm 与采样间隔取大者。**采样受限时以 bin 为准**，须在 `meta.json` 落盘实际值 | 场景生成器、R-X3、R-X6 |
| **敏感性档** | 场景实际 $\Delta\rho_{\rm bin}$ | 随 `aperture_tier` 一同标注（D8） | 现有 S1–S6（600 bin / 24.5 m ⇒ **40.8 mm**） |
| **σ_h 传播单元测试** | 与被测场景一致 | 传播自洽性检验必须用同一 $\sigma_\rho$，否则 ratio 无意义 | `verify_sigma_h_propagation.py` |

### 2.1 当前各档的实际值（2026-09-06 核实）

| 档位 | $\rho_{\max}$ | range bin | $\Delta\rho_{\rm bin}$ | 合规性 | ★I-1 用 | ★II-1 用 |
|---|---|---|---|---|---|---|
| **`scene_set_main_f8`（已生成 ✅）** | **15 m** | **1600** | **9.07 mm** | ✅ 在 3–19 mm 内 | 10 mm | $\Delta/\sqrt{12}=2.62$ mm 作噪声 |
| `scene_set_main` **现状** | 40 m | 600 | **65.94 mm** | ❌ **超规格 3.5 倍** | 10 mm（注入） | 65.94 mm |
| 敏感性档 `scene_set_v2` | 25 m | 600 | **40.90 mm** | ❌ 超规格 2.2 倍 | 10 mm（注入） | 40.90 mm |

**$\tau_z^{\rm crit}$ 随之的差异（$N=10$、$\varphi_{\max}=7.5°$）**：

| $\sigma_\rho$ 来源 | 值 | $\tau_z^{\rm crit}$ | 对 $\tau_z=5$ cm |
|---|---|---|---|
| 主档目标 bin | 9.07 mm | **3.79 cm** | ✅ 可达 |
| ARIS 规格中值 | 10 mm | 4.18 cm | ✅ 可达 |
| `scene_set_v2` bin | 40.90 mm | 17.1 cm | ❌ 不可达 |
| `scene_set_main` bin | 65.94 mm | **27.6 cm** | ❌ 不可达 |

> ⚠️ 现有 `verify_sigma_h_propagation.py` / `_verify_R_x0b.py` 用的 `sigma_rho=0.05` 与
> 任何一档的实际值都不符（敏感性档 40.9 mm、主档现状 65.9 mm），须改为从台账读取。

---

## 3. 已发现的不一致（F-7 待清理项）

| 位置 | 当前值 | 应改为 |
|---|---|---|
| `verify_sigma_h_propagation.py` | 硬编码 `sigma_rho=0.05` | 从场景 `meta.json` 读 `sigma_rho_m` |
| `R_x6_carve_fixed.py` | 未显式使用（仅用 bin 量化） | 无需改，但 leading edge 容差 `dr/2` 应改用台账值 |
| `_R_x3_full_ba*.py` 系列 | 待核 | 从台账读取 |
| 场景 `meta.json` | 未落盘 `sigma_rho_m` | 生成时写入 |

---

## 4. 接口约定

场景生成时必须在 `meta.json` 的 `config` 内落盘：

```json
{
  "config": {
    "sigma_rho_m": 0.0408,
    "sigma_rho_source": "range_bin_limited",
    "range_bin_count": 600,
    "rho_max_m": 25.0
  },
  "aperture_tier": "sensitivity_17deg"
}
```

`sigma_rho_source` 取值：`aris_spec_mid`（规格中值 10 mm）／`range_bin_limited`（采样受限）／`bandwidth_limited`（$c/2B$）。

**所有实验脚本读取顺序**：`meta.json` 的 `config.sigma_rho_m` → 若缺失则按本台账 §2.1 回填并告警，**不得静默使用默认值**。

### 4.1 `scene_set_main_f8` 的实际落盘（F-8d 已实现）

```json
{
  "config": {
    "sigma_rho_m": 0.01,
    "sigma_rho_source": "aris_spec_mid",
    "sigma_rho_bin_m": 0.009068,
    "sigma_rho_quant_m": 0.002618,
    "sigma_rho_note": "★I-1 链用 sigma_rho_m（tracks 的 rho_m 连续）；★II-1 链用 sigma_rho_quant_m = Δρ_bin/√12（L_s 沿距离轴量化）。见 sigma_rho_ledger.md §1b",
    "sigma_Dt_m": 0.02,
    "sigma_zs_m": 0.02,
    "range_bin_count": 1600,
    "rho_max_m": 15.0
  },
  "aris_compliance": {
    "dbin_mm": 9.068,
    "dbin_within_spec_3_19mm": true,
    "rho_max_within_spec_15m": true
  },
  "aperture_tier": "main_aris_7p5deg"
}
```

新增 `sigma_Dt_m` / `sigma_zs_m`：★II 反演的 $D_t$ 与 $z_s$ 来自 ★I(BA)，
其不确定度必须显式记账，否则 $\sigma_h$ 传播会漏项。取 2 cm（与横向可分辨距离 $d_R=4.4$ cm 的一半同量级）。
