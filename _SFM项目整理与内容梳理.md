# F:\sfm 项目整体整理与内容梳理

> 整理时间：2026 年（基于工作区现状盘点）
> 工作区根目录：`F:\sfm`
> git 仓库：`https://github.com/hardmore123/sfm.git`，分支 `docs/theory-correction-and-roadmap`
> 本文档是对整个 `F:\sfm` 文件夹的**全面梳理**，覆盖专利、大论文、BA 代码、数据集、论文集、理论基础等全部相关内容。

---

## 0. 一句话定位

本项目围绕**水下二维前视声呐（FLS）三维重建**，同时推进三条紧密关联的线：

1. **BA 代码线**：对上游初始位姿 + 点云 + 数据关联做光束平差（Bundle Adjustment）联合优化；
2. **专利线**：把 BA 方法写成发明专利（已到"定稿"版，含 5 张附图）；
3. **大论文线**：规划两个创新点（可观测性判据 ★I + 声学阴影补高度 ★II）的整体技术路线，并已形成经审计的交付材料。

> **三者关系**：专利是 BA 代码的方法化表达；大论文在专利/BA 基础上向前延伸，引入阴影反演与可观测性判据，把"BA 几何优化"和"阴影图像理解"串成闭环。

---

## 1. 工作区总览（体积与文件数）

> **全量统计**（不含 `.git`）：**28,147 个文件 / 23.7 GB**
> 按扩展名：png 21,287、npy 3,883、xml 1,868（数据集掩码）、py 227、md 204、csv 171、json 127、pdf 73、ply 35、docx 6、blend 5

| 顶层目录 | 体积 | 文件数 | 性质 |
|---|---|---|---|
| `论文代码与数据/` | 470.7 MB | 195 | ★大论文交付材料（经审计，效力分级） |
| `sfm_synthetic_pillars/` | 21.9 GB | 7351 | 仿真主工作区（含有效/作废/未审计数据） |
| `数据集（不上传git）/` | 1.46 GB | 20131 | 真实数据集（marine-debris-fls，第三方） |
| `论文集/` | 337.2 MB | 90 | 参考论文 PDF + ACSim 源码 |
| `专利/` | 10.8 MB | 20 | 专利稿件（docx + md，多版本） |
| `专利图/` | 11.1 MB | 13 | 专利附图（黑白合规 + 彩色旧版） |
| `BA代码/` | 4.9 MB | 112 | BA 实验代码与仿真输入/输出 |
| `汇报_BA成果/` | 2.4 MB | 19 | BA 阶段汇报材料（图 + 报告） |
| `大论文思想路线/` | 1.2 MB | 83 | 大论文思路、创新点设计、审计链、任务分发 |
| `output/` | 0.1 MB | 9 | BA 运行产物归档 |
| `_kiro_recheck/` | 0.2 MB | 67 | 复核脚本与日志（minimax 任务回报） |
| `input/` | 1.4 MB | 5 | BA 输入数据副本 |
| 顶层文件（约 50 个） | ~106 MB | — | 代码、数据、图、文档、日志（部分与子目录重复） |

> **注意**：顶层根目录散落着一批与子目录重复的文件（`ba_*.py`、`landmarks_*.npy`、`*.png`、`*.md`），是早期开发时的工作副本，已被 `BA代码/` 和 `论文代码与数据/02_代码/` 取代。

---

## 2. 目录树（完整结构）

```
F:\sfm\
├── .git/                                    # git 仓库（分支 docs/theory-correction-and-roadmap）
├── .gitignore
│
├── 论文代码与数据/                           # ★大论文交付材料（经审计，效力分级）
│   ├── README.md                            # 交付总入口
│   ├── 00_效力分级与作废清单.md              # ⚠️ 引用任何数字前先读
│   ├── MANIFEST.json / .bak                 # 全文件清单 + SHA1
│   ├── 会话交接_20260907.md                  # 新会话接续文档
│   ├── 01_理论支撑/
│   │   ├── README.md
│   │   ├── 实施任务表_验收标准_阶段安排.md
│   │   ├── 执行路线_数据资产_缺口清单.md
│   │   ├── 传感器规格/                       # ARIS Explorer 3000 参数 + 真实数据集清单
│   │   ├── 公式权威/                         # ★理论修正_T1-T6.md（公式唯一权威）+ σ 台账 + 打通状态清单
│   │   ├── 创新点设计/                       # 创新点一/二 问题定义 + 内容设计定稿 + 稠密化模块
│   │   ├── 审计链/                           # A1-A6 / P1-P6 / Q1-Q6 / 修正通知（按时间后者裁定前者）
│   │   └── 文献/                             # 精读笔记 + 待找文献 + 文献分析重构
│   ├── 02_代码/                              # ★全部代码（扁平布局，可直接运行）
│   │   ├── README.md
│   │   ├── _setup_data.py                   # 建立数据布局（junction）
│   │   ├── 仿真基础: config.py, world.py, trajectory.py, sonar_render.py, sim_pipeline.py
│   │   ├── 阴影渲染+反演(★II): shadow_f8_fixed.py(✅用这个), shadow.py(⚠️仅依赖), height_inversion.py
│   │   ├── 判据(★I): feasibility.py, observability.py, _f8_design_sceneset.py
│   │   ├── 稠密化(★II-2): R_x6_carve_fixed.py, surface_recon.py
│   │   ├── BA: ba_optimize.py, ba_improve.py, ba_improve34.py, ba_unified.py, ba_patent.py, view3d.py
│   │   ├── 场景生成: gen_scenes_main_f8.py, scene_configs.py
│   │   ├── 验证脚本(14个): verify_*.py, f8_probe_*.py（全部实测可跑）
│   │   └── __pycache__/
│   ├── 04_数据/
│   │   ├── README.md
│   │   └── scene_set_main_f8/               # ★唯一有效场景集（469 MB，5 场景）
│   │       ├── INDEX.json
│   │       ├── M1_well_constrained/
│   │       ├── M2_blind_low_spread/         # ★核心对比对（盲场景）
│   │       ├── M3_envelope_inside/
│   │       ├── M4_envelope_outside/
│   │       └── M5_low_snr/
│   │           每个场景: meta.json + gt/(真值) + obs/(观测量) + innov2/(反演结果)
│   ├── 05_结果/
│   │   ├── F8主档/                          # INDEX + 场景集设计 + 各场景 meta
│   │   └── 稠密化/                          # R_X6_FIXED_REPORT.md
│   └── 06_作废归档/                          # ❌ 被审计推翻的报告（保留追溯，禁止引用）
│       ├── README.md
│       ├── 含失效数字的报告/                 # P_STAR / R_X3 / R_X5 / R_X6 / X2B / X3_CRLB 等
│       ├── 工作日志/                         # WORK_LOG / SESSION_LOG / V11-V13
│       ├── 早期文档/                         # BIG_PAPER / DATA_INVENTORY / GAP_FIX / T0-T1
│       └── 理论/                             # THEORY_FIXES_T1-T6（已降级为实现笔记）
│
├── sfm_synthetic_pillars/                   # 仿真主工作区（开发副本，21.9 GB）
│   ├── 仿真脚本（与 02_代码 同源）: big_paper_sim.py, gen_scenes_*.py, shadow*.py, feasibility.py 等
│   ├── 验证脚本: verify_*.py, _verify_*.py
│   ├── 报告: WORK_LOG*.md, R_X*_REPORT.md, T1-T6 报告, LIT_NOTES, DATA_INVENTORY
│   ├── big_paper_scene_set/                 # 早期大规模仿真（5.9 GB，未经审计）
│   ├── big_paper_sim/                       # 早期大规模仿真（8.6 GB，未经审计）
│   ├── scene_set_main/                      # 作废场景集（2.6 GB，Q1/Q3/Q4 失效）
│   ├── scene_set_v2/                        # 作废场景集（739 MB，超规格）
│   ├── scene_set_main_f8/                   # ★有效场景集（与 04_数据 同源）
│   ├── innov2_ablations/                    # 作废消融数据（657 MB，Q1 失效）
│   ├── real_data/                           # 真实数据探针
│   ├── _tmp_heave_baseline/                 # 临时基线（2.8 GB）
│   └── __pycache__/
│
├── 数据集（不上传git）/                      # 真实数据集（1.43 GB，第三方）
│   └── marine-debris-fls-datasets-master/
│       ├── README.md
│       └── md_fls_dataset/
│           ├── loader.py, __init__.py
│           ├── models/                      # densenet, minixception, mobilenet, resnet, squeezenet
│           └── data/
│               ├── watertank-segmentation/  # 1868 图 + 掩码，12 类（ARIS Explorer 3000）
│               ├── watertank-cropped/       # 4942 帧，转台角作真值
│               ├── turntable-cropped/
│               └── quarry-fullsize/         # 7209 帧，自然阴影，无位姿真值
│
├── 论文集/                                  # 参考论文 PDF（337 MB，90 文件）
│   ├── README_论文清单.md                    # 论文清单与分类
│   ├── WANTED_PAPERS.md                     # 待找文献
│   ├── _AUDIT_REPORT.md                     # 论文集审计
│   ├── ACSim-master/                        # 声学相机仿真器源码
│   ├── _junk_to_delete/                     # 重复/占位 PDF（待删）
│   ├── *.pdf                                # 约 60 篇论文（ASfM / BA / 空间雕刻 / 阴影 / 数据集 / 鲁棒优化 / 分割）
│   └── 整理论文集.ps1, arxiv_fetch.ps1, campus_fetch.ps1
│
├── 专利/                                    # 专利稿件（10.8 MB，多版本）
│   ├── 专利代码/                             # ba_patent.py + 运行结果
│   ├── 专利定稿.md                           # ★最新定稿（符号统一、去 AI 痕迹）
│   ├── 专利最新初稿.md                       # 用户原始初稿
│   ├── 专利重构稿.md                         # 重构版（结构对齐、修 bug）
│   ├── 专利旧稿.md                           # 历史草稿（含可复用素材）
│   ├── 专利格式要求(1).md                    # 撰写格式要求
│   ├── 附图说明与画法.md                      # 5 张附图画法说明
│   ├── *.docx                               # 多个 docx 版本（含主参考模板 02B）
│   └── _02B.txt                              # 模板纯文本
│
├── 专利图/                                  # 专利附图（11.1 MB）
│   ├── draw_patent_figs.cs / draw_figs.exe  # 出图程序
│   ├── _build.ps1
│   ├── 图1_整体流程图_黑白.png 等 5 张        # ★黑白合规版（C# 生成）
│   └── 图1/2/3 彩色版.png, 图4.jpg, 图5.jpg   # 旧彩色/JPG 版（不合规，待替换）
│
├── BA代码/                                  # BA 实验代码（4.9 MB）
│   ├── README.md
│   ├── ba_optimize.py                        # 基线 BA
│   ├── ba_improve.py                         # 改进 1&2（相对球坐标 + 欠约束识别）
│   ├── ba_improve34.py                       # 改进 3&4（解析雅可比 + GNC 剔除外点）
│   ├── ba_unified.py                         # 统一版 V6（六合一）
│   ├── ba_patent.py                          # 专利对齐版
│   ├── view3d.py                             # 3D 可视化
│   ├── 12.5新.py                             # 最初原型（有 bug，勿直接用）
│   ├── BA环节总结与上游对接.md
│   ├── BA统一版_测试结果.md
│   ├── 上游对接清单.md
│   ├── sim_input*/                           # 16 组仿真输入（每组 6 文件）
│   └── sim_output/                           # 仿真输出
│
├── 汇报_BA成果/                             # BA 阶段汇报材料（2.4 MB）
│   ├── 汇报导览_先读这个.md                    # ★导览
│   ├── 改进依据与动机_为什么这么改.md           # 问题→论文依据→为什么→效果
│   ├── 图_效果/                              # 6 张讲解图（按顺序）+ 备用图
│   └── 报告_数据对照/                         # 5 份测试报告（改进12/34/统一版/方向全清单/阶段总结）
│
├── 大论文思想路线/                           # 大论文思路与理论（1.2 MB）
│   ├── 大论文思想路线_改进版.md                # ★改进版思路（硕士定位）
│   ├── 大论文整体思路.md / -0723.md            # 旧版备份
│   ├── 大论文思想路线说明.md
│   ├── 创新点内容设计_定稿.md                  # ★两创新点内容设计
│   ├── 创新点一/二_问题定义与模块分解.md
│   ├── 稠密化模块_点云生成内容设计.md
│   ├── 文献分析与思路重构_v3.md
│   ├── 理论修正_T1-T6.md                      # ★公式权威（与 01_理论支撑 同源）
│   ├── 理论基础_打通状态清单.md                # ★40 项断言三级标注
│   ├── 审计_20260904/05/06*.md                # 审计报告（文档倒挂/雕刻错误/阴影恒等式）
│   ├── 审计报告_逻辑与可靠性_20260904.md
│   ├── 任务表_理论收尾与立身_20260909.md
│   ├── 实施任务表_验收标准_阶段安排.md
│   ├── 执行路线_数据资产_缺口清单.md
│   ├── R_X3_报告_BA侧CRLB实测_20260909.md      # ★R-X3 实测结果
│   ├── 工作日志_20260909.md / 大论文写作日志.md / 会话交接_20260907.md
│   ├── 总体技术路线图.png
│   ├── draw_route.cs / draw_route.exe / _build_route.ps1
│   ├── minimax任务分发/                      # 给 minimax 的核查任务 + 回报 + 工具 + 日志
│   └── 论文代码/                             # ba_paper.py + 结果（与 专利代码 同源）
│
├── output/                                  # BA 运行产物归档
│   ├── 上游需要给的信息.md
│   └── BA_2026-07-23_110328/                # 运行产物（优化位姿/点云/PLY + 图 + report）
│
├── input/                                   # BA 输入数据副本（landmarks/poses/tracks）
│
├── _kiro_recheck/                           # 复核脚本与日志
│   ├── minimax原始日志/
│   ├── recheck.py, verify_core_formula.py, smoke_rx3.py 等
│   └── *.log, *.txt
│
└── 顶层散落文件（约 50 个）                   # 早期工作副本（多与子目录重复）
    ├── ba_optimize.py, ba_improve*.py, ba_unified.py, 12.5新.py, view3d.py
    ├── ba.cs, ba.exe                          # C# 实现版
    ├── poses_*.npy, landmarks_*.npy/.ply, tracks.csv, pose_frame_ids.npy
    ├── ba_*.png（6 张结果图）
    ├── BA*.md（6 份文档）
    ├── 交接文档.md, 参考论文与开源项目汇编.md
    ├── 声呐术语详解.md, 声呐论文知识库.md
    ├── 论文集.zip（103.7 MB）
    ├── BA代码.zip
    └── _*.ps1 / _*.py / _*.log / _*.txt（临时脚本与日志）
```

---

## 3. 三条线详细梳理

### 3.1 大论文线（★主线，最系统化）

**落脚点**：纯二维前视声呐（FLS）三维重建。两个创新点**串行成闭环**：

```
★I 可观测性判据（多视 BA）
  I-1  高度精度存在孔径决定的硬上限 τ_z^crit —— 判"哪些点多视做不到"
  I-2  可反演性包线（C-I..C-IV + 照明带）—— 判"哪些点阴影能反演"
        │ 接口：D_far（轮廓远边缘）、z_s ← 只能由 ★I(BA) 提供
        ▼
★II 声学阴影补高度
  II-1 h = z_s(1 − D_far/D_e)，D_e 由阴影远端跳变量测
  II-2 空间雕刻稠密化 → 包围壳
        ▼
   三维重建结果
```

**当前立身状态**：

| 项 | 状态 | 差什么 |
|---|---|---|
| ★I-2 可反演性包线 | ✅ **立住** | 3600 个 (帧,列) 样本 FP=0、FN=0 |
| C7 无恒等式 | ✅ | 已在 scene_set_main_f8 上满足 |
| ★I-1 精度硬上限 | 🟢 **阶段 A/C 已立**（R-X3） | 严格 CRLB 被 MC 实测复现：M1 ratio 0.953、M2 ratio 0.987；阶段 B（完整联合 BA）进行中 |
| ★II-1 阴影反演 | 🟡 **半立** | 缺与 Zhou 2025 的同条件对比（R-X5） |
| ★II-2 空间雕刻 | ☐ **未立** | 需 F-4b：α-hull + 亚 bin + roll ⇒ E≤0.10（现 0.195） |
| 真实数据验证 | ☐ **未做** | 数据已备（1.43 GB），未纳入 |

**核心交付物**：`论文代码与数据/`（168 文件 / 470 MB，按效力分级物理隔离）

**效力分级**（⚠️ 引用数字前必读 `00_效力分级与作废清单.md`）：
- ✅ 有效：`01_理论支撑/`、`02_代码/`、`04_数据/`、`05_结果/`
- ⚠️ 仅依赖/追溯：`shadow.py`、`height_inversion.py`、旧场景集联接
- ❌ 作废：`06_作废归档/`（"改进 500 倍"、"MAE=0.00 cm" 等数字失效，原因是真值泄漏/恒等式）

**核心公式（有效版）**：

| 量 | 公式 | ARIS 主档数值 |
|---|---|---|
| 高度 CRLB（双通道式，T7） | $\sigma_{P_z}^{-2}\approx(\frac{\sigma_\rho\cos\bar\varphi}{\sqrt N\operatorname{std}\varphi})^{-2}+(\frac{\bar\rho\sigma_\theta}{\sqrt N\operatorname{std}(r)\cos\theta_p})^{-2}$ | — |
| 离散度门限 | $\Delta\varphi_{\min}=\dfrac{\sigma_\rho}{\sqrt N\tau_z}$ | N=60 ⇒ 1.479° |
| 斜距通道硬界 | $\tau_z^{\rm crit,abs}=\dfrac{\sigma_\rho\cos\bar\varphi}{\sqrt N\varphi_{\max}}$ | N=10 ⇒ 2.42 cm |
| 均匀扫过可达值 | $\tau_z^{\rm crit,unif}=\dfrac{\sqrt3\sigma_\rho}{\sqrt N\varphi_{\max}}$ | N=10 ⇒ 4.18 cm |
| 阴影反演 | $h=z_s(1-\dfrac{D_{\rm far}}{D_e}),\ D_e=\sqrt{\rho_{\rm end}^2-z_s^2}$ | — |
| 有限尺寸物体 | $D_e=\dfrac{(D_t+r)z_s}{z_s-h}$（**轮廓远边缘**） | 用柱心有 +8.4 cm 偏置 |

**作废公式（禁用）**：$\varphi_{\rm blind}=\arcsin\frac{\sigma_\rho}{\sqrt N\tau_z}$（sin 版，应为 std 门限）；$\sigma_{P_z}\ge\frac{\sigma_\rho}{\sqrt{\sum\sin^2\varphi_k}}$（松界，低估 15 倍）；$D_e=\frac{D_t z_s}{z_s-h}$（柱心版）。

---

### 3.2 专利线

**专利名称**：一种视场约束下数据关联与位姿联合优化的声呐三维重建方法

**对应 BA 代码的核心创新**：
1. 软数据关联（负指数核置信度权重）替代硬性 RANSAC 剔除
2. 相对球坐标参数化 + 视场箱式硬约束（抑制俯仰缺失导致的病态）
3. 置信度从 BA 贯穿到曲面重建（加权泊松）
4. 4 个优选：多视图仰角弧初始化、各向异性信息矩阵、俯仰可观测性自适应、鲁棒核渐进调度

**文件状态**：
- `专利定稿.md`：★最新定稿（243 行，符号统一、去 AI 痕迹、术语规范）
- `专利最新初稿.md`/`专利重构稿.md`/`专利旧稿.md`：历史版本
- `*.docx`：7 个 Word 版本（含主参考模板 02B、第二版标定方法等）
- `专利图/`：5 张附图（黑白合规版已生成，彩色旧版待替换）
- `专利代码/`：`ba_patent.py` + 运行结果

**关键提醒**（来自交接文档"坑 6"）：当前 `ba_optimize.py`/`ba.cs` 用的是世界系 XYZ 参数化 + 路标弱先验，**没有**专利宣称的"相对球坐标 + 视场箱式硬约束"；软关联 $w^{(0)}$、S4 曲面重建、4 个优选也都没在代码里。写论文/答辩前必须补进代码。

---

### 3.3 BA 代码线

**四项改进**（都有实测数字与图）：

| 改进 | 依据论文 | 效果 |
|---|---|---|
| 相对球坐标参数化 | Westman 2018、Huang 2016 | 隔离不可观测俯仰自由度 |
| 欠约束路标识别 | Westman 2018 | JᵀJ 特征值判据，欠约束仰角移出优化 |
| 解析雅可比 + 稀疏求解 | BA 通用（Triggs） | **6× 加速**（73.3s → 12.3s） |
| GNC + χ² 剔除外点 | Yang & Carlone 2020、Sünderhauf 2012 | 35% 外点下半径误差 22.1 → 10.7 cm |

**实测结果**：
- 重投影 RMS 1.86 → 0.57 px（单柱）、2.26 → 0.67 px（双柱）
- Z 向漂移 ↓69.5%
- 解析雅可比经有限差分校验，最大绝对误差 3.7e-4

**代码版本**：
- `ba_optimize.py`：基线（世界系 XYZ + Huber δ=20）
- `ba_improve.py`：改进 1&2
- `ba_improve34.py`：改进 3&4（速度 + GNC）
- `ba_unified.py`：统一版 V6（六合一）
- `ba_patent.py`：专利对齐版
- `ba.cs`/`ba.exe`：C# 实现（与 ba_optimize.py 同逻辑）

> ⚠️ BA 代码**尚未纳入 F-8 验证体系**，结果未经本轮审计（见会话交接 §6）。

---

## 4. 数据集梳理

### 4.1 仿真数据（sfm_synthetic_pillars/）

| 目录 | 体积 | 状态 | 说明 |
|---|---|---|---|
| `scene_set_main_f8/` | 469 MB | ✅ **唯一有效** | 5 场景（M1-M5），ARIS 规格内，无真值泄漏 |
| `scene_set_main/` | 2.6 GB | ❌ 作废 | 8 场景（S1-S6），Q1/Q3/Q4：ρ_max=40m 超规格、2/8 场景目标像素为 0 |
| `scene_set_v2/` | 739 MB | ❌ 作废 | 6 场景（S1-S6），敏感性档 ±17°，Δρ_bin=40.9mm 超规格 |
| `innov2_ablations/` | 657 MB | ❌ 作废 | 2 子目录（02_forward / 02_forward_v1_noshadow），Q1 恒等式泄漏 |
| `big_paper_sim/` | 8.6 GB | ⚠️ 未审计 | 4 子目录（forward / general / mixed / yaw_y），早期大规模仿真 |
| `big_paper_scene_set/` | 5.9 GB | ⚠️ 未审计 | 16 场景（01_simple_single_pillar … 16_low_snr_extreme），早期大规模仿真 |
| `_tmp_heave_baseline/` | 2.8 GB | ⚠️ 临时 | 6 子目录（forward/general × h0.4/0.8/1.2），heave 基线数据 |
| `real_data/` | <1 MB | — | ARIS 参数 + 数据集清单 + loader.py + poisson_smoke.ply |

**big_paper_scene_set 的 16 个场景**（早期大规模仿真，未经审计）：
01_simple_single_pillar / 01_simple_single_pillar_v1_buggy / 02_simple_two_pillars / 03_simple_cube / 04_sphere_target / 05_diverse_shapes / 06_dense_pillars_16 / 08_low_resolution / 09_narrow_elevation / 10_wide_elevation / 11_seafloor_with_rubble / 12_multipath_heavy / 13_circular_trajectory / 14_zigzag_trajectory / 15_speckle_heavy / 16_low_snr_extreme

**scene_set_main 的 8 个场景**（作废）：S1_main_single / S2_main_forward_degenerate / S3_main_mixed_DEPRECATED / S3_main_single_mid / S3_main_v3 / S4_main_low_snr / S5_main_envelope_edge / S6_main_envelope_outlier

**有效场景集 scene_set_main_f8 的 5 个场景**（传感器全部落在 ARIS Explorer 3000 规格内：±7.5°、128 波束、ρ∈[0.5,15]m、1600 bin、θ_p=19°）：

| 场景 | h | std(φ) | σ_P_z | 阴影 MAE | 分类 |
|---|---|---|---|---|---|
| M1_well_constrained | 0.85 | 1.760° | 4.20 cm | 0.681 cm | 良约束 |
| **M2_blind_low_spread** | 0.85 | 0.152° | 48.57 cm | 0.577 cm | **盲** |
| M3_envelope_inside | 1.05 | 1.783° | 4.15 cm | 0.638 cm | 良约束 |
| M4_envelope_outside | 1.12 | 1.790° | 4.13 cm | 0.637 cm | 良约束（TN=52） |
| M5_low_snr | 0.85 | 1.760° | 4.20 cm | 0.692 cm | 良约束 |

> **M1 vs M2 是核心对比对**：几何完全相同、只差轨迹起伏（1.2m vs 0.1m）。M2 多视给 48.57 cm，阴影反演给 0.577 cm ⇒ "阴影是多视必要补充"的直接证据。

### 4.2 真实数据集（数据集（不上传git）/，1.43 GB）

`marine-debris-fls-datasets-master`（ARIS Explorer 3000）：
- `watertank-segmentation/`：1868 图 + 掩码，12 类
- `watertank-cropped/`：4942 帧，转台角作真值
- `turntable-cropped/`：转台数据
- `quarry-fullsize/`：7209 帧，自然阴影，**无位姿真值**
- `models/`：densenet / minixception / mobilenet / resnet / squeezenet

---

## 5. 理论基础梳理

### 5.1 公式权威与优先级链（D10）

```
理论修正_T1-T6.md            ← 公式唯一权威
  ↑ 裁定依据
审计链：A1–A6(0904) → P1–P6(0905) → Q1–Q6(0906) → R1(0907) → T7(0909)   后者裁定前者
  ↓ 应服从
创新点内容设计_定稿.md 等设计文档
  ↓
实现笔记与旧报告（多在 06_作废归档/）
```

规则：代码与权威文档冲突时，**先改文档再改代码**，不得只改一侧。

### 5.2 理论基础打通状态（40 项断言，三级标注）

- ✅ 已验证：有可复跑脚本 + 独立路径核对
- 🟡 已推导未验证：公式成立但无数值核对，或同模型自证
- ☐ 未做：尚未推导或落地

**★I-1 链**（高度可观测性与精度上限）：1.1✅ 1.2⚠️降为近似式 1.3✅ 1.4✅收窄 1.5✅ 1.6⚠️ 1.7✅ 1.8✅ 1.9✅ 1.10✅ 1.11🟡 1.12✅ 1.13✅
**★I-2 链**（可反演性包线）：2.1-2.10 全部 ✅，理论已闭合
**★II 链**（阴影反演与稠密化）：部分 ✅，★II-2 未立

### 5.3 十一处实现缺陷（已全部修正）

按发现批次：Q1–Q4（核查旧场景集）、Q5（约束检查器自身）、Q6（修正实现时，全部由独立校核抓出）、A/P 批（更早）。

**最重要的方法论教训**（Q1 与 Q6.3）：估计器与数据生成器共享同一简化，误差相互抵消，自证为高精度。特点是代码每行都对、数字漂亮（MAE 0.00 cm）、看代码看不出来。唯一有效检出手段是**用另一条独立代码路径复算同一个量**。

### 5.4 措辞纪律（写作时必须遵守）

| 不得写 | 应写 |
|---|---|
| "方位角完全不携带垂直信息" | "垂直可观测性由斜距主导"（斜距贡献是方位 82 倍） |
| "下俯角改善高度可观测性" | "下俯角仅用于照亮海底以形成阴影" |
| "存在与运动方式无关的不可观测区" | "不含时变横滚的运动无法突破斜距通道孔径上限" |
| 把 σ_P_z 说成"BA 实测误差" | "解析 CRLB"（完整 BA 实测进行中） |
| 把 720 条量测当独立样本 | 来自 60 帧×12 列、帧间高度相关，不做显著性检验 |

---

## 6. 论文集梳理

`论文集/`（337 MB，约 60 篇 PDF + ACSim 源码），按主题分类：

| 主题 | 代表论文 |
|---|---|
| 声呐 ASfM / BA | Huang 2015/2016、Westman 2020/2025、Incremental data association、Sonar feature detection |
| 空间雕刻 | Aykin & Negahdaripour 2017、Three-Dimensional Target Reconstruction、Differentiable Space Carving |
| 阴影反演 | Aykin 阴影几何、An Automatic Sonar Target Shadow Extraction、Tang 2020 Mobile Active Sonar Height |
| 退化/可观测性 | Wang 2023 motion degeneracy、On degeneracy of optimization-based state estimation、Motion Degeneracy self-supervised |
| 鲁棒优化 | Yang & Carlone TEASER/GNC/TLS/Certifiable Perception、Sunderhauf Switchable Constraints、Robust map optimization DCS |
| 数据集 | Singh 2021 Marine Debris FLS、Valdenegro 2025、Xie 2022 UATD |
| 仿真 | Wang 2025 ACSim、Potokar HoloOcean、simulated.pdf |
| 分割/深度学习 | Lian SAM/SAM2、Wang SAM Meets Sonar、Kannangara SegFormer LoRA、Aubard Sonar DL Overview |
| 光学 SfM 对照 | Bathymetric SfM、Adding Conditional Control (ControlNet) |

**ACSim-master**（声学相机仿真器，Blender 插件）：
- `built_in/`：of.blend + wakachiku_tank.blend（Blender 场景资产）
- `demo/`：SonarRT.zip + test.blend
- `optimized/`：debug.blend + optimized.blend + process_rays.pyx + ray_tracing.pyx + setup.py

**_junk_to_delete/**：12 个重复/占位 stub PDF（待删除）。

---

## 7. 当前缺口与下一步

| 项 | 状态 | 阻塞什么 |
|---|---|---|
| ★I-1 阶段 B（完整联合 BA） | 🟡 进行中 | 措辞只能写"位姿已知条件下的实测" |
| ★II-1 与 Zhou 2025 同条件对比 | ☐ 需 R-X5 | ★II-1 立身 |
| ★II-2 α-hull + 亚 bin + roll | ☐ 需 F-4b | ★II-2 立身（E≤0.10，现 0.195） |
| 真实数据验证 | ☐ 未做 | ARIS 数据已备（1.43 GB） |
| 代码对齐专利核心创新 | ☐ 未做 | 相对球坐标 + 视场约束 + S4 曲面 + 4 优选 |
| 阴影分割（ViT+LoRA） | ☐ 未做 | ★II-1 全链路 |

**门禁**：★I-1 与 ★II-1 补齐前不进入下一阶段。

---

## 8. 环境与运行注意事项

| 项 | 说明 |
|---|---|
| Python | 3.11+，依赖 numpy（open3d 仅点云导出需要，pandas 不需要） |
| 跑验证 | `cd 论文代码与数据\02_代码; python _setup_data.py; python verify_f8d_sceneset.py` |
| 重新生成场景 | `python gen_scenes_main_f8.py`（约 8 分钟） |
| 改完 sonar 参数 | 必须调 `finalize_pixel_mapping(cfg)` |
| `SceneWorld(cfg)` | 不接受关键字参数，通过 `cfg.scene.pillars` 注入 |
| trajectory.py 起伏 | `sin(2π·t·0.5)`，半周期单侧 z∈[z_s, z_s+A]；横滚 0.05·sin(2πt) 硬编码 2.9° |
| git | 只推 `docs/theory-correction-and-roadmap` 分支，不推 main；数据全部在库外 |

### 8.1 .gitignore 排除策略（数据全部在库外）

git 仓库**只跟踪源码、Markdown 文档与小型配置**，排除规则要点：
- **仿真数据**：`sfm_synthetic_pillars/` 下 `big_paper_*`、`innov2_ablations`、`_tmp_*`、`scene_set_v2`、`__pycache__` 全部排除（约 18.3 GB）
- **真实数据集**：`数据集（不上传git）` 整个排除（1.43 GB）
- **论文集**：`*.pdf`、`ACSim-master/`、`*.blend` 全部排除（0.30 GB）
- **二进制产物**：`*.exe`、`*.npy`、`*.zip`、`*.ply`、`*.h5`、`*.pt` 等排除
- **专利文档**：`专利/*.docx`、`*.doc` 排除
- **交付数据**：`论文代码与数据/04_数据/scene_set_main_f8/` 排除（469 MB，可由 `gen_scenes_main_f8.py` 确定性重建）；`02_代码/` 下 4 个 junction 也排除
- **临时脚本**：`_tmp*`、`_probe.py`、`AGENT_ADDRESS.txt` 排除
- **递归排除**：所有 `*.pdf` 与 `_junk_to_delete/` 目录

> 结果：历次提交体积 25 KB – 24 MB 文本，库内无数据。

### 8.2 output/BA_2026-07-23_110328/（BA 运行产物归档）

最早一次完整 BA 运行的产物（2026-07-23）：
`ba_log.txt`、`ba_result.png`（3D 重建图）、`ba_topview.png`（俯视图）、`residual_hist.png`（残差直方图）、`landmarks_optimized.npy/.ply`、`poses_optimized.npy`、`report.md`

---

## 9. 重复与冗余文件提示

顶层根目录散落着一批与子目录重复的文件，属于早期开发工作副本：

- **代码**：`ba_optimize.py`、`ba_improve*.py`、`ba_unified.py`、`12.5新.py`、`view3d.py`（与 `BA代码/` 和 `02_代码/` 重复）
- **数据**：`poses_*.npy`、`landmarks_*.npy/.ply`、`tracks.csv`、`pose_frame_ids.npy`（与 `input/` 重复）
- **图**：`ba_*.png`（6 张，与 `汇报_BA成果/图_效果/备用图/` 重复）
- **文档**：`BA*.md`（6 份，与 `BA代码/` 和 `汇报_BA成果/报告_数据对照/` 重复）
- **压缩包**：`论文集.zip`（103.7 MB，是 `论文集/` 的压缩备份）、`BA代码.zip`
- **临时脚本**：`_*.ps1`、`_*.py`、`_*.log`、`_*.txt`

> 建议：以 `论文代码与数据/`（经审计的交付材料）和 `BA代码/` 为准，顶层散落文件可视为历史副本，整理时可归档或清理。

---

## 10. 关键文档阅读顺序（给接手者）

1. `论文代码与数据/会话交接_20260907.md` — 新会话先读，了解现状与踩坑
2. `论文代码与数据/README.md` — 交付材料总入口
3. `论文代码与数据/00_效力分级与作废清单.md` — ⚠️ 引用数字前必读
4. `大论文思想路线/大论文思想路线_改进版.md` — 大论文定位与两创新点
5. `大论文思想路线/理论基础_打通状态清单.md` — 40 项断言状态
6. `大论文思想路线/创新点内容设计_定稿.md` — 创新点内容设计
7. `论文代码与数据/01_理论支撑/公式权威/理论修正_T1-T6.md` — 公式唯一权威
8. `专利/专利定稿.md` — 专利最新版
9. `汇报_BA成果/汇报导览_先读这个.md` — BA 阶段成果
10. `交接文档.md` — 项目最初交接（2026-07-23，历史背景）
