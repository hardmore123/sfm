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

## 2. 台账（按用途固定取值）

| 用途 | $\sigma_\rho$ | 依据 | 使用者 |
|---|---|---|---|
| **主档理论计算** | **10 mm** | ARIS Explorer 3000 规格 3–19 mm 取中（`real_data/ARIS_EXPLORER_3000_PARAMS.md`） | `feasibility.ARIS_MAIN`、$\tau_z^{\text{crit}}$ 表、盲区判据 |
| **主档仿真** | $\max\big(c/2B,\ \Delta\rho_{\rm bin}\big)$ | 物理分辨率 $c/2B=2.5$ mm 与采样间隔取大者。**采样受限时以 bin 为准**，须在 `meta.json` 落盘实际值 | 场景生成器、R-X3、R-X6 |
| **敏感性档** | 场景实际 $\Delta\rho_{\rm bin}$ | 随 `aperture_tier` 一同标注（D8） | 现有 S1–S6（600 bin / 24.5 m ⇒ **40.8 mm**） |
| **σ_h 传播单元测试** | 与被测场景一致 | 传播自洽性检验必须用同一 $\sigma_\rho$，否则 ratio 无意义 | `verify_sigma_h_propagation.py` |

### 2.1 当前各档的实际值

| 档位 | $\rho_{\max}$ | range bin | $\Delta\rho_{\rm bin}$ | 台账 $\sigma_\rho$ |
|---|---|---|---|---|
| 主档（ARIS，待生成） | 15 m | 1600 | 9.1 mm | **10 mm**（bin 与规格中值接近，取规格值） |
| 敏感性档（现 S1–S6） | 25 m | 600 | **40.8 mm** | **40.8 mm**（不是 0.05 m） |

> ⚠️ 现有 R-X3 / `verify_sigma_h_propagation.py` 用的 `sigma_rho=0.05` 与敏感性档的 40.8 mm 相差 23%，须改为从台账读取。

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
