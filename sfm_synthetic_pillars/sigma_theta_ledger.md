# σ_θ 台账（测角/方位噪声口径的唯一来源）

> 与 `sigma_rho_ledger.md` 配套。**所有涉及 $\sigma_\theta$ 的脚本一律从本台账取值，禁止硬编码。**
> 起因：T7（`理论修正_T1-T6.md` §9）证明高度精度有一个**方位通道**，$\sigma_{z,\theta}\approx\bar\rho\,\sigma_\theta/(\sqrt N\operatorname{std}(r)\cos\theta_p)$，**正比于 $\sigma_\theta$**。
> 而 $\sigma_\theta$ 此前是没有来源的假设值，库内至少有 5 个互相矛盾的取值。
> 验收脚本：`verify_sigma_theta_ledger.py`（L1/L2/L4 通过，L3 如实报告临界值）。
> 版本：2026-09-09

---

## 1. 为什么必须记账

T7 之前，$\sigma_\theta$ 不影响任何高度结论（当时认为方位不提供高度信息），取多少都无所谓。
T7 之后，**只要轨迹含时变横滚，$\sigma_\theta$ 就直接缩放高度精度**：

| 量 | 对 $\sigma_\theta$ 的依赖 |
|---|---|
| 斜距通道 $\sigma_{z,\rho}$、$\tau_{z,\rho}^{\rm abs}$、$\Delta\varphi_{\min}$ | **无关**（实测：roll=0 时严格 CRLB 在 0.072°–0.30° 全区间内不变，L1） |
| 方位通道 $\sigma_{z,\theta}$ | **线性正比** |
| 主档 M1/M2 的严格 CRLB（含现行 roll ±2.9°） | M1 弱依赖，M2 **强依赖**（见 §3） |

---

## 2. 合理取值区间及依据

| $\sigma_\theta$ | 来源 / 物理含义 | 性质 |
|---|---|---|
| **0.072°** | 波束间隔 $0.25°/\sqrt{12}$：**按波束索引取整**的量化噪声 | 取整读数时的噪声下界（若做亚波束插值可更小，但需高 SNR，须实测证明） |
| 0.083° | $0.25°/3$，`verify_observability_theory.py` 旧取值 | 无独立依据，仅为历史值 |
| 0.10° | 1.8 MHz 水平波束宽 $0.3°/3$：高 SNR 点目标强度质心 | 乐观的工程估计 |
| **0.18°** | **现行主档**（`gen_scenes_main_f8`、`rx3_ba_crlb`） | 本台账确认的主值，见 §4 |
| 0.20° | Huang 2015 Table I；`config.py` 默认；`sim_pipeline` 的 tracks 建议列 0.0035 rad | **文献值**，同类声呐 SLAM 通行取值 |
| 0.25° | 一个波束间隔 | 无亚波束能力时的量级 |
| **0.30°** | 1.8 MHz 水平波束宽度（ARIS 规格） | 上界：特征在一个波束宽度内完全不确定 |
| 0.5° | `scene_configs.py` 某旧场景 | ❌ 超出物理上界，旧场景专用，不得用于主档 |

**主档合理区间：$\sigma_\theta\in[0.072°,\ 0.30°]$。** 下界由波束离散化给出，上界由物理波束宽度给出。

> 注：仿真主档用 `linspace(-15°, 15°, 128)`，实际波束间隔是 $30°/127=0.236°$，量化项为 **0.068°**，比 ARIS 规格值（0.25° ⇒ 0.072°）略小。
> `meta.json` 落盘的是仿真的实际值（`sigma_theta_beam_spacing_deg` / `sigma_theta_beam_quant_deg`）；本台账的区间下界按 ARIS 规格取。

### 2.1 ⚠️ 与 σ_ρ 同样的两种口径

和 `sigma_rho_ledger.md` §1b 完全同构，`tracks.csv` 同时存两列：

| 列 | 形态 | 有效 $\sigma_\theta$ |
|---|---|---|
| `theta_rad` | 连续浮点（真值 + $N(0,\sigma_{\rm inj})$） | $=\sigma_{\rm inj}$ |
| `beam_index` | 取整后的波束号 | $\sqrt{\sigma_{\rm inj}^2+\Delta_{\rm beam}^2/12}$，主档 $\sqrt{0.18^2+0.072^2}=$ **0.194°** |

`rx3_ba_crlb` / `verify_t7_*` 读连续量 ⇒ 用注入值。
`ba_optimize` / `ba_improve*` / `ba_unified` 的残差用的是 `beam_index`（经 `calibrate_pixels` 线性映射），
⇒ **这几个 BA 的有效 σ_θ 要叠加量化项**。在主档下这只差 8%，但如果改用更小的注入值，量化项就会成为主导。

---

## 3. 敏感性（`verify_sigma_theta_ledger.py` 实测）

主档几何，轨迹为 `trajectory.py` 现行的 roll = 0.05·sin(2πt)（±2.9°）。严格 CRLB = $\sqrt{[\Lambda^+]_{zz}}$：

| $\sigma_\theta$ | M1 | M2 | M1（roll=0） | M2（roll=0） | M2 判定（$\tau_z$=5 cm） |
|---|---|---|---|---|---|
| 0.072° | 3.04 | **4.88** | 3.88 | 45.84 | **可观测** |
| 0.083° | 3.20 | 5.61 | 3.88 | 45.84 | 盲 |
| 0.10° | 3.37 | 6.74 | 3.88 | 45.84 | 盲 |
| **0.18°（主值）** | **3.70** | **11.85** | 3.88 | 45.84 | **盲** |
| 0.20° | 3.74 | 13.07 | 3.88 | 45.84 | 盲 |
| 0.25° | 3.79 | 15.97 | 3.88 | 45.84 | 盲 |
| 0.30° | 3.82 | 18.67 | 3.88 | 45.84 | 盲 |

（单位 cm）

- **L1** roll=0 两列在全区间内完全不变 ⇒ **斜距通道的所有结论（$\Delta\varphi_{\min}$、$\tau_{z,\rho}^{\rm abs}$、盲判据）与 σ_θ 取值无关** ✅
- **L2** M1 在全区间内都 ≤ 5 cm ⇒ M1"良约束"判定稳健 ✅
- **L3 M2 判定的临界值 $\sigma_\theta^*=0.074°$**：$\sigma_\theta$ 低于它时 M2 不再是盲。它恰好落在量化下界 0.072° 附近。
- **L4** 端点 MC 抽检（M2，300 次）：0.072° 时 MC/严格 = 0.932，0.30° 时 1.062 ✅

### 3.1 对结论的含义（必须如实写进论文）

> **M2"多视不够、需要阴影"这一判定，在 $\sigma_\theta\ge0.074°$ 时成立。**
> 这个条件覆盖合理区间的几乎全部（0.074°–0.30°）。只有当方位读数精确到波束量化极限、并且不叠加任何检测噪声时，判定才会翻转。
> 而且若读的是 `beam_index`，量化项本身就是 0.072°，叠加任何非零检测噪声后都会超过 $\sigma_\theta^*$。
> **所以在本仿真管线内这个判定是稳健的；推广到真实 ARIS 时，前提是方位检测噪声不优于量化极限。**

措辞纪律：
- 报告 M2 或任何"含横滚轨迹"的 $\sigma_{P_z}$ 时，**必须同时注明 $\sigma_\theta$**。
- 不得写"M2 在任何条件下都是盲"，应写"在 $\sigma_\theta\ge0.074°$（合理区间的几乎全部）下为盲"。

---

## 4. 台账（按用途固定取值）

| 用途 | $\sigma_\theta$ | 依据 |
|---|---|---|
| **主档理论计算与仿真注入** | **0.18°（3.14 mrad）** | 落在合理区间 [0.072°, 0.30°] 中段，与文献值 0.20°（Huang 2015）相差 10%；高于 M2 临界值 2.4 倍，判定不贴边 |
| 主档读 `beam_index` 的 BA | $\sqrt{0.18^2+0.072^2}=0.194°$ | §2.1 量化叠加 |
| **敏感性报告轴** | {0.072°, 0.10°, 0.18°, 0.30°} | 下界 / 乐观 / 主值 / 上界 |
| 真实数据（待做） | **由 turntable-cropped 标定**（RD-1） | 转台角已知 ⇒ 可直接统计方位残差，得到 ARIS 实际 σ_θ。**这是消除本台账唯一假设的办法** |

### 4.1 已发现的不一致（待清理）

| 位置 | 当前值 | 处置 |
|---|---|---|
| `observability._landmark_JTJ` 默认值 | `max(abs(D)*5e-3, 1e-3)`：**用距离截距推角度噪声，量纲错误** | 已改为未传参时告警（`ObservabilityWarning`），调用方必须显式传入 |
| `verify_observability_theory.py` | $0.25°/3=0.083°$ | 该脚本只验证斜距通道（roll=0 构型），结论与 σ_θ 无关（L1），**保留不改**，加注说明 |
| `sim_pipeline.write_tracks_csv` 建议列 | 0.0035 rad（0.20°）写死 | 与注入值不一致时会误导下游白化；改为写 `cfg.noise.sigma_theta_rad`（随下次数据重建一并改） |
| `scene_configs.py` 旧场景 | 0.5° | 超物理上界，仅旧场景，不进主档 |

---

## 5. 接口约定

场景生成时必须在 `meta.json` 的 `config` 内落盘（2026-09-09 起，`gen_scenes_main_f8.py` 已实现）：

```json
{
  "config": {
    "sigma_theta_rad": 0.0031416,
    "sigma_theta_deg": 0.18,
    "sigma_theta_source": "ledger_main_0p18deg",
    "sigma_theta_beam_quant_deg": 0.0722,
    "sigma_theta_note": "★I-1 方位通道 ∝ σ_θ；连续 theta_rad 用注入值，beam_index 需叠加量化项。见 sigma_theta_ledger.md"
  }
}
```

`sigma_theta_source` 取值：`ledger_main_0p18deg` / `beam_quant_limit` / `beamwidth_limit` / `calibrated_turntable`（RD-1 完成后）。

读取：`feasibility.resolve_sigma_theta(meta, strict)`，与 `resolve_sigma_rho` 同一约定——
缺失时按本台账主值回填**并告警**，`strict=True` 时直接报错，**不得静默使用默认值**。
