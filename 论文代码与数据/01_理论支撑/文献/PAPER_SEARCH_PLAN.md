# 论文查找计划 — 按阶段表 §2 优先级

> **配套**：`实施任务表_验收标准_阶段安排.md` §2 文献检索方案
> **当前 17 篇论文**（`F:\sfm\论文集\`）
> **缺口**：A / F / H 三组完全空缺；B / E / G 部分覆盖
> **计划日期**：2026-09-04

---

## 一、现有论文按组覆盖

| 组 | 主题 | 现有 | 状态 |
|----|------|------|------|
| **A** | 声学阴影几何与高度反演 | 2 篇 (Wang 2023, Westman 2025) | ⚠ Aykin 2017 仍缺 |
| **B** | 鲁棒估计与防塌缩 | 2 篇 (BA-Based SIO, Feature-Based SLAM) | ⚠ 缺专用 GNC |
| **C** | 仰角弧交会与多视三角化 | 14 篇 (Westman, Huang, DISO, ASfM, +Westman 2025) | ✓ 已覆盖 |
| **D** | 神经隐式/可微渲染 | 3 篇 (Lin 2025, NeuSIS 2024, simulated) | ✓ 已覆盖 |
| **E** | 声呐分割与 PEFT | 2 篇 (Aubard 综述, jmse-6D) | ⚠ 缺 SAM/PEFT |
| **F** | 网格评价 Poisson | 0 篇 | ❌ **完全空缺** |
| **G** | 可观测性与退化度量 | 3 篇 (Feature-Based SLAM, Bathymetric-SfM, +Wang 2023) | ✓ 已覆盖 |
| **H** | 海底散射与仿真 | 6 篇 (Kearney, Potokar×2, Romrell, Wang 2024, Wu 2014) | ✓ **P0 已满** |
| **I** | 评价指标规范 | 0 篇 | 可在 P6 写作时查 |

> **2026-09-04 更新**：本轮下载 8 篇 A/H 组 PDF，详见 `LIT_NOTES.md`

---

## 二、查找时间表

| 优先级 | 组 | **什么时候查** | 任务依赖 | 状态 |
|--------|----|----------------|----------|------|
| ~~**🔴 P0 立即**~~ | ~~**A**~~ | ~~**本周末**~~ | ~~T0.7 重写 shadow.py~~ | ⚠ **本轮 2/6 补** |
| ✅ **P0 已满** | **H** | 本周末 | T0.4/T0.5 在 1 周内 | ✅ **6/6 补全** |
| 🟡 P1 1 周内 | **G** | 5 天内 | T1.0/T2.3 需 κ 阈值 | ⚠ 有 2 篇 partial |
| 🟡 P2 2 周内 | **B** | T2.1 创新一前 | 鲁棒 BA 权重更新式 | ⚠ 有 2 篇 partial |
| 🟢 P4 4 周后 | **F** | P4 段开始时 | T2.5/T4.4 网格 | ❌ 待补 |
| 🟢 P5 5 周后 | **E** | P5 段开始时 | T5.0/R1 分割基线 | ⚠ 有 2 篇 partial |
| ⚪ P6 | I | 写作时 | 指标规范 | 不急 |

---

## 三、🔴 P0 立即要查的论文清单

### A 组：声学阴影几何与高度反演（核心，最关键）

> 必读作者：**Murat D. Aykin**、**Shahriar Negahdaripour**（公式来源）

| 检索词 | 目标 |
|--------|------|
| `Aykin Negahdaripour shadow height side-scan sonar` | 阴影长度→目标高度经典公式 |
| `shadow-based 3D reconstruction forward-looking sonar` | FLS 上的阴影反演 |
| `grazing angle shadow length target height` | 掠射角下阴影长度与目标高度关系 |
| `acoustic shadow height estimation FLS` | 高度反演的精度评估 |

**关键问题**：
1. 阴影长度 L_s 与目标高度 h 的精确公式是什么？（`L_s = h × |tan(elev)|` 还是 `L_s = h × (d + h × elev) / d` 还是更复杂的？）
2. 适用范围：h/z_s ∈ [0, ?]，L_s 在什么条件下被量程截断？
3. 误差上界：典型 5cm 吗？多 SNR 下能到 1cm？

**若找到 4+ 篇**：T0.7 阴影判定的物理依据、T0.8 精确正演式、T3.5 Aykin 基线对比 → 全部解锁

### H 组：海底散射与声呐成像仿真

> 必读：Lambert 模型 / Jackson 模型 / HoloOcean 仿真器

| 检索词 | 目标 |
|--------|------|
| `seafloor backscatter Lambert grazing angle sonar` | Lambert 散射模型 |
| `Jackson backscattering model seafloor` | Jackson 掠射角依赖 |
| `forward-looking sonar image simulation` | FLS 完整仿真 |
| `HoloOcean sonar simulator` | 现成仿真器 |
| `DAVE underwater simulator` | 现成仿真器 |

**关键问题**：
1. 阴影/海底的强度比到底是 20dB 还是 40dB？这决定 T0.4 的对比度阈值
2. 海底散射的角度依赖是 Lambert 还是 Jackson？
3. 是否有现成可调用的仿真器？

---

## 四、🟡 P1 一周内要查的论文清单

### G 组：可观测性与退化度量

> 必读：**Zhang 退化检测**、Fisher information 退化判定

| 检索词 | 目标 |
|--------|------|
| `Zhang degeneracy detection SLAM` | Zhang 2016 经典方法 |
| `observability analysis acoustic structure from motion` | 声呐 SfM 可观测性 |
| `Fisher information degenerate motion` | Fisher 退化判定 |
| `condition number landmark parameterization` | 条件数阈值依据 |

**关键问题**：
- 当前代码 κ 阈值 0.05 是"拍的"。文献依据是什么？3-sigma？λ3/λ2 比值？
- Westman 2020 (Fermat paths) 里有 λ3 讨论，需要细读

### B 组：鲁棒估计

| 检索词 | 目标 |
|--------|------|
| `Yang Carlone graduated non-convexity SLAM` | GNC 论文 |
| `switchable constraints robust pose graph` | SC 论文 |
| `dynamic covariance scaling SLAM` | DCS 论文 |

**关键问题**：选哪种鲁棒核？阈值依据？

---

## 五、🟢 P4/P5 段再查

- **F 组**：Kazhdan 2013 (Screened Poisson), Hoppe 1992 (surface reconstruction), normal estimation
- **E 组**：SAM adaptation for sonar, LoRA segmentation, few-shot sonar segmentation

---

## 六、检索结果处理

每篇新论文按以下流程入库：
1. 下载 PDF 到 `F:\sfm\论文集\`
2. 更新本文件 §1 现有覆盖表
3. 写一段阅读笔记到 `real_data/LIT_NOTES.md`（待建）
4. 标注关键公式、阈值、参数表

---

## 七、本轮执行结果（2026-09-04）

### 7.1 A 组（阴影几何）下载结果

| 论文 | 来源 | 状态 |
|------|------|------|
| **Wang 2023 Motion Degeneracy** | arXiv 2307.16160 | ✅ 已下载 1.68 MB |
| **Westman 2025 Stereo Sonar Feature Geometry** | arXiv 2507.05410 | ✅ 已下载 6.69 MB |
| Aykin 2017 JOE Space Carving | sci-hub 域名受阻 | ❌ 暂未下 |
| Aykin 2013 OCEANS Image Formation | IEEE 付费 | ❌ 暂未下 |
| ACSim 2025 IEEE T-RO | IEEE 付费 | ❌ 暂未下 |

### 7.2 H 组（海底散射 + 仿真）下载结果 — **P0 已满** ✅

| 论文 | 来源 | 状态 |
|------|------|------|
| **Kearney 2022 NSEA** (Lambert + Rayleigh) | arXiv 2211.09092 | ✅ 已下载 2.20 MB |
| **Potokar 2022 HoloOcean ICRA** | BYU 镜像 | ✅ 已下载 5.85 MB |
| **Potokar 2022 HoloOcean Sonar IROS** | BYU 镜像 | ✅ 已下载 5.83 MB |
| **Romrell 2025 HoloOcean 2.0 Preview** | arXiv 2510.06160 | ✅ 已下载 4.63 MB |
| **Wang 2024 FLS Ground Echo** | arXiv 2304.08146v2 | ✅ 已下载 1.29 MB |
| **吴金荣 2014 海洋混响** (中文, 含 Jackson) | 物理学报 | ✅ 已下载 3.00 MB |

### 7.3 论文集总览
- **总 PDF 数**：27 篇（17 → 25 → 27）
- **总大小**：~137 MB
- **A 组覆盖**：从 0/6 → 2/6（仍有 4 篇待补）
- **H 组覆盖**：从 0/6 → 6/6 ✅
- **G 组覆盖**：从 2/3 → 3/3 ✅（Wang 2023 补上）

### 7.4 关键发现（已读笔记）
1. **Lambert 散射公式**（Kearney 2022）：
   `σ = (ρ/π)·cos²(θ_i) ∝ sin²(θ_g)`，适用掠射角 < 45°
2. **Rayleigh 噪声**（Kearney 2022）：
   `Y(r,θ) ~ Rayleigh(B(r)·σ(r,θ))`（中心极限定理）
3. **Jackson 三域模型**（吴金荣 2014）：
   - D1 0-10° Kirchhoff / D2 15-50° Bragg / D3 55-70° 体积散射
4. **泥质海底 μ = -27 dB**（Mackenzie 530Hz/1030Hz 实测，被广泛验证）
5. **FLS 投影模型**（Westman 2025）：
   `Π_fl(r,θ,ϕ) = [r,θ]^T`

### 7.5 仍需用户机构权限
- Aykin 2017 JOE（最重要的空间雕刻论文）
- Aykin 2013 OCEANS（图像形成基础）
- ACSim 2025（最新 ray tracing 仿真器）

---

*本文件由 Session 12 阶段产出物（V10），配合 `WORK_LOG.md` V10 一起记录*
