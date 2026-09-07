# R-X3 蒙特卡洛试跑报告（V1 · 2026-09-05）

> **作者**：Mavis
> **配套脚本**：`_R_x3_monte_carlo.py`（12.3 KB）
> **状态**：框架已就绪 + 试跑通过；完整 R-X3 待改进

---

## 一、目标

阶段表 R-X3 验收：
- 🔢 s_z / σ̂_Pz ∈ [0.8, 1.3]
- 🔢 s_z 与 σ_ρ/(√N·std(φ)) 的比值 ∈ [0.8, 1.3]
- 🔢 曲线拐点位置与 Δφ_min = σ_ρ/(√N·τ_z) 的相对偏差 ≤ 30%

**物理意义**：验证 R-X0b 修复后的理论 σ_Pz 是否与 BA 实际估计的标准差一致。这是 ★I-1 立身的物理依据。

---

## 二、试跑结果（n_mc=20, n_lm=3）

### 2.1 采样 landmarks

从 `_tmp_heave_baseline/general_h1.2` 30 个 landmarks 中采样 3 个：**[17, 19, 25]**

### 2.2 理论 σ_Pz (R-X0b 修复版)

| landmark | n_obs | σ_Pz_theory (m) |
|----------|-------|------------------|
| 17 | 4 | 0.029 |
| 19 | 4 | 0.034 |
| 25 | 5 | 0.011 |

### 2.3 蒙特卡洛结果

| landmark | n_obs | s_z (cm) | mean_z (m) | s_z/σ_Pz | 验收 |
|----------|-------|----------|------------|----------|------|
| 17 | 4 | **93.53** | 0.630 | **29.9×** | ❌ 远超 [0.8, 1.3] |
| 19 | 4 | 0.50 | 0.359 | 0.15× | ❌ 低于 [0.8, 1.3] |
| 25 | 5 | 0.31 | 2.340 | 0.27× | ❌ 低于 [0.8, 1.3] |

### 2.4 诊断

- **landmark 17**：s_z=93.53cm 远大于 σ_Pz=0.029m ⇒ BA 优化不稳定，可能陷入局部最优
- **landmark 19, 25**：s_z 远小于 σ_Pz ⇒ 实际 BA 估计器比 CRLB 更"确定"，可能因为 z bounds 截断
- **共同问题**：单 landmark 简化 BA（仅用 yaw、只解 z）过于简化，不足以验 σ_Pz

---

## 三、试跑结论

### ✅ 框架已就绪
- 数据读取（tracks.csv 解析 + pose_frame_ids 映射）✓
- R-X0b 修复版 σ_Pz 计算 ✓
- 加噪 + 蒙特卡洛循环 ✓
- 统计（s_z, std(φ), 各种比值）✓
- 落盘 R_X3_RESULTS.json ✓

### ❌ 试跑结果不通过验收

3/3 landmarks 比值不在 [0.8, 1.3] 区间。**根因**：单 landmark 简化 BA 模型过于简化，无法代表真实 BA 估计器。

---

## 四、改进建议（完整 R-X3 实现路径）

### 4.1 必须改进：完整 R 矩阵

当前 R 仅用 yaw，忽略 roll/pitch：
```python
# 当前（简化）
R = [[cos(yaw), -sin(yaw), 0],
     [sin(yaw),  cos(yaw), 0],
     [0,         0,        1]]

# 改进（完整）
R = euler_to_matrix(roll, pitch, yaw)  # 用 trajectory.euler_to_matrix
```

### 4.2 强烈建议：联合多 landmark BA

当前单 landmark 优化 z 不稳定（landmark 17 失败）。应改为多 landmark 联合：
```python
# 改进：解多个 landmark 的 z
z_all = [z_j for j in range(M)]
# 残差 = sum over j, i: (theta_obs_ji - theta_pred_ji)^2 / σ_θ^2 + (rho_obs_ji - rho_pred_ji)^2 / σ_ρ^2
```

或更彻底：用 `UnifiedSonarBA` 联合优化 poses + landmarks（参考 `F:\sfm\BA代码\ba_unified.py`）

### 4.3 建议：放宽 z bounds 或用无约束优化

z bounds [0, 2.5] 截断可能让某些 landmark 的 z 估计被强制截断，导致 s_z 偏小。改用无约束 + 物理先验正则。

### 4.4 实施路径

1. **R-X3a**（0.5d）：用完整 R 矩阵 + 联合多 landmark 优化 z（不动 poses）
2. **R-X3b**（1d）：用 UnifiedSonarBA 完整 BA，跑 M=200 次蒙特卡洛
3. **R-X3c**（1d）：扫 std(φ)（通过改 heave 幅度），画 s_z vs std(φ) 曲线，验拐点

合计约 2.5-3d 完成完整 R-X3。

---

## 五、本轮 session 状态汇总（2026-09-05）

### 已完成（5.5d 任务量）
- ✅ **R-X3b**：observability.py 修复 dtheta_dP 补 @ R.T + 白化 + 伪逆 CRLB
- ✅ **R-X0**：在 general_h1.2 上验证四分类（修复后 well=21/不足=1，70% well）
- ✅ **R-X1**：feasibility.py 新增 std(φ) 版 + τ_z^crit=4.18cm
- ✅ **R-SCN 标注**：S1-S6 meta.json 加 aperture_tier=sensitivity_17deg
- ✅ **报告改写**：P_STAR_REPORT.md / X3_CRLB_REPORT.md 逐行改写
- ✅ **R-X3 框架**：试跑通过 + 改进建议

### 待做（约 14d 任务量）
- ⏳ **R-X3 完整实现**（2.5-3d）：用完整 R 矩阵 + 联合 BA + M=200
- ⏳ **R-X5**（4d）：真正实现 Zhou 2025 双高度差分反演
- ⏳ **R-X6**（5d）：真正实现 Aykin 2017 空间雕刻
- ⏳ **R-X56c**（2d）：对比协议 C5 落地
- ⏳ **R-SCN 全套**（3d）：SONAR_ARIS 主档重生成 S1-S6

### G★-R 门当前状态
- ★I-2 ✅ 立身（待主档重跑确认）
- ★I-1 ⚠️ 物理前提齐全（R-X0b 修复完成），蒙特卡洛证据待 R-X3 完整
- ★II-1 / ★II-2 ❌ 未立身

---

*报告由 mavis agent 2026-09-05 产出。R-X3 试跑框架已交付，完整实现路径已列出。*
