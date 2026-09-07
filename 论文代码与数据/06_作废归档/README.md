# `06_作废归档/` —— 禁止引用

> 这里的每份文件都含有**已被审计推翻**的结论或数字。
> 保留它们只有一个目的：**追溯**——让人能查到"当时错在哪、怎么发现的、改成了什么"。
> 完整的作废理由见 `../00_效力分级与作废清单.md`。

---

## 为什么不直接删掉

三个理由：

1. **审计链需要被审计对象。** `01_理论支撑/审计链/` 里的 A/P/Q 三批审计都在引用这些报告的具体数字，
   删掉会让审计文档失去指向。
2. **防止重犯。** 比如"500 倍改进"是怎么算出来的、为什么看起来合理——这个过程本身有警示价值。
3. **论文写作时可能要交代。** 若审稿人问"为什么不和 Aykin 2017 比"，答案就在这批文件里
   （Aykin 2017 是空间雕刻论文，不做阴影测高，比了属张冠李戴）。

---

## 目录

### `理论/`

| 文件 | 状态 |
|---|---|
| `THEORY_FIXES_T1-T6_已降级为实现笔记.md` | **已降级**。公式的唯一权威是 `01_理论支撑/公式权威/理论修正_T1-T6.md`。本文中 `σ_Pz ≥ σ_ρ/√(Σsin²φ_k)`、`φ_blind = arcsin(σ_ρ/(√N·τ_z))` 均已作废（实为 $1/\Lambda_{zz}$ 松界，**低估 15 倍**）。另混入的 `σ_ρ(z_s−h)²/(D_t·z_s)` 属另一物理问题（阴影反演的 $\sigma_h$ 传播），不可与多视可观测性混用 |

### `含失效数字的报告/`

| 文件 | 失效的是什么 | 裁定 |
|---|---|---|
| `P_STAR_REPORT_含500倍改进已作废.md` | "V2 比 Aykin/Zhou 改进 500–600 倍" | P 批 |
| `X3_CRLB_REPORT_判定不成立.md` | "5/5 场景 std/CRLB ∈ [1.005,1.016]" —— 验的是 $\sigma_h$ 传播而非多视 $\sigma_{P_z}$，且 $\varphi_{\rm blind}$ 段直接赋值 | A 批 |
| `R_X3_FINAL_REPORT.md` / `R_X3_FULL_REPORT.md` / `R_X3_PROGRESS_REPORT.md` | 同上系列 | A 批 |
| `R_X5_FULL_REPORT.md` | 与 Zhou 2025 的对比不满足同条件（C5） | P 批 |
| `R_X6_FULL_REPORT_雕刻方向反了.md` / `R_X6_V2_FULL_REPORT_雕刻方向反了.md` | 雕刻 AND/OR 方向写反 ⇒ $E=0.9975$ | P4 |
| `R_X56C_FULL_REPORT.md` | 统一对比协议未落实 A3 双侧修正 | P 批 |
| `INNOV2_ABLATION_V4_REPORT_受Q1恒等式影响.md` | 全部 ★II 反演精度数字 | **Q1** |
| `R_SCN_FULL_REPORT.md` | 场景集报告，基于超规格的旧主档 | Q3/Q4 |
| `X2B_REPORT_模型过简.md` | heave 最优幅度的 analytical 模型过于简化 | 自认 |

> **修正后的雕刻结果**（有效）在 `../05_结果/稠密化/R_X6_FIXED_REPORT.md`：
> 方向修正后 $E$ 从 0.9975 → 直线 0.524 → 6 位置环绕 0.262 → 2 位置×8 roll **0.195**。
> 目标 $E\le0.10$ **仍未达到**，属实现精细度问题（需 α-hull + 亚 bin），
> 按 D9 **不得**写成"研究发现"。

### `工作日志/`

`WORK_LOG.md`、`WORK_LOG_AND_THOUGHTS_V11/V12/V13.md`、`SESSION_LOG_2026-09-04.md`

过程记录。含大量当时认为成立、后被推翻的中间结论。**只作时间线参考。**

### `早期文档/`

`DATA_INVENTORY.md`、`BIG_PAPER_README.md`、`BIG_PAPER_DELIVERY.md`、
`T1_1_REPORT.md`、`T1_2_HEAVE_BASELINE_REPORT.md`、`T0_4_T0_6_DOC.md`、
`GAP_FIX_REPORT.md`、`FINAL_GAP_FIX_REPORT.md`

早期阶段的文档与报告，多数基于后来发现超规格的仿真构型（$\rho_{\max}=6$ m 或 40 m），
且在 Q1 泄漏被发现之前。**状态未逐项核查，一律按作废处理。**

---

## 仍在原工作区、未复制的作废数据

| 目录 | 体积 | 说明 |
|---|---|---|
| `sfm_synthetic_pillars/scene_set_main/` | 2.6 GB | 8 个场景。孔径标对了但量程超规格 2.7 倍、2 个场景目标像素为 0 |
| `sfm_synthetic_pillars/scene_set_v2/` | 739 MB | 6 个场景。敏感性档 ±17°，$\Delta\rho_{\rm bin}=40.9$ mm 超规格 |
| `sfm_synthetic_pillars/innov2_ablations/` | 657 MB | ★II 消融实验，受 Q1 影响 |
| `sfm_synthetic_pillars/big_paper_sim/` | 8.6 GB | 未经审计 |
| `sfm_synthetic_pillars/big_paper_scene_set/` | 5.9 GB | 未经审计 |
| `sfm_synthetic_pillars/_tmp_heave_baseline/` | 2.8 GB | 临时基线 |

前三个由 `02_代码/_setup_data.py` 建立目录联接，以便审计追溯类脚本
（`f8_probe_sigma_rho.py`、`verify_f7_sigma_rho_ledger.py`、`f8_probe_shadow_visibility.py`）能跑。

**这些目录的 `meta.json` 里的 `inversion` 段（`mae_v2_median_cm` 等）全部无效。**
可以用的只有几何与可观测性统计（`config`、`scene`、`stats`、`feasibility`），
用途限于说明"旧构型为何不合规"。
