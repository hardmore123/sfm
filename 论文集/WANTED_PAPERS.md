# 校园网爬取行动手册 — 大论文「鲁棒声呐 BA + 阴影→高度反演」

> **配套**：`PAPER_SEARCH_PLAN.md` §2（9 组）、`LIT_NOTES.md`（已读笔记）
> **使用场景**：把 Mavis agent 放在校园网（机构代理/EasyConnect/VPN）下，自动爬取被付费墙挡住的论文
> **整理日期**：2026-09-04

---

## 一、9 大方向（按优先级）

### 🔴 P0 立即 — 2.5 周内必需

#### A 组：声学阴影几何与高度反演（最关键）
- **必读作者**：Murat D. Aykin、Shahriar Negahdaripour（UVIL Miami）
- **核心问题**：阴影长度 L_s 与目标高度 h 的精确公式？适用范围？误差上界？
- **关键问题**：
  1. `L_s = h × |tan(elev)|` 公式的精度
  2. h/z_s ∈ [0, ?] 范围
  3. 多 SNR 下能到 1cm 吗？

#### H 组：海底散射与声呐成像仿真
- **必读**：Lambert / Jackson / HoloOcean / ACSim
- **关键问题**：
  1. 阴影/海底强度比（20dB vs 40dB）
  2. 角度依赖（Lambert vs Jackson）
  3. 现成可调用仿真器

### 🟡 P1 一周内

#### G 组：可观测性与退化度量
- **必读**：Zhang 退化检测、Fisher information、λ3 阈值

#### B 组：鲁棒估计
- **必读**：Yang Carlone GNC、Switchable Constraints、DCS

### 🟢 P4 4 周后

#### F 组：网格评价 Poisson
- **必读**：Kazhdan 2013 (Screened Poisson)、Hoppe 1992

### 🟢 P5 5 周后

#### E 组：声呐分割与 PEFT
- **必读**：SAM adaptation、LoRA segmentation、few-shot sonar

### ⚪ P6 写作时

#### I 组：评价指标规范

### ✅ 已覆盖（仅查漏）

#### C 组：多视几何（13 篇已有） — Westman 2020 Fermat、Huang ASfM、DISO 等
#### D 组：神经隐式（3 篇已有） — Lin 2025、NeuSIS 2024、simulated

---

## 二、搜索关键词（中英双语）

### A 组 阴影几何
| # | 关键词 | 目标 |
|---|--------|------|
| 1 | `Aykin Negahdaripour shadow height side-scan sonar` | 经典公式来源 |
| 2 | `shadow-based 3D reconstruction forward-looking sonar` | FLS 上的阴影反演 |
| 3 | `grazing angle shadow length target height` | 掠射角下阴影长度 |
| 4 | `acoustic shadow height estimation FLS` | 高度反演精度 |
| 5 | `Negahdaripour space carving FS sonar` | 多视空间雕刻 |
| 6 | `FLS 声学阴影 高度反演` | 中文检索 |
| 7 | `acoustic shadow modeling 2D lens sonar` | 透镜式声呐建模 |

### H 组 海底散射 + 仿真
| # | 关键词 | 目标 |
|---|--------|------|
| 1 | `Lambert seafloor backscatter grazing angle sonar` | Lambert 散射 |
| 2 | `Jackson backscattering model seafloor` | Jackson 三域模型 |
| 3 | `forward-looking sonar image simulation` | FLS 完整仿真 |
| 4 | `HoloOcean sonar simulator Unreal Engine` | BYU 仿真器 |
| 5 | `ACSim acoustic camera ray tracing` | 东京大学 2025 |
| 6 | `octree sonar imaging rendering` | 八叉树成像 |
| 7 | `recursive ray tracing acoustic` | 多路径反射 |
| 8 | `海底 散射 强度 经验公式` | 中文实测 |
| 9 | `APL-UW composite roughness` | Jackson 散射 |
| 10 | `BOGGART Boyle Chotiros backscatter` | 高频散射对比 |

### G 组 可观测性
| # | 关键词 | 目标 |
|---|--------|------|
| 1 | `Zhang degeneracy detection SLAM` | Zhang 2016 经典 |
| 2 | `observability analysis acoustic structure from motion` | 声呐 SfM 可观测性 |
| 3 | `Fisher information degenerate motion` | Fisher 退化 |
| 4 | `condition number landmark parameterization` | κ 阈值 |
| 5 | `Fermat path 3D imaging sonar` | Westman 退化条件 |
| 6 | `motion degeneracy self-supervised sonar` | 运动退化 |

### B 组 鲁棒估计
| # | 关键词 | 目标 |
|---|--------|------|
| 1 | `Yang Carlone graduated non-convexity SLAM` | GNC |
| 2 | `switchable constraints robust pose graph` | SC |
| 3 | `dynamic covariance scaling SLAM` | DCS |
| 4 | `M-estimator bundle adjustment sonar` | 鲁棒核 |

### F 组 网格 Poisson
| # | 关键词 | 目标 |
|---|--------|------|
| 1 | `Kazhdan Screened Poisson surface reconstruction` | 2013 |
| 2 | `Hoppe surface reconstruction unorganized points` | 1992 |
| 3 | `normal estimation point cloud` | 法向估计 |
| 4 | `mesh evaluation Chamfer F-score` | 评价指标 |

### E 组 声呐分割
| # | 关键词 | 目标 |
|---|--------|------|
| 1 | `SAM adaptation sonar segmentation` | SAM 微调 |
| 2 | `LoRA few-shot sonar segmentation` | LoRA 分割 |
| 3 | `ViT underwater acoustic classification` | ViT 声学 |
| 4 | `watertank segmentation FLS dataset` | 水箱数据集 |

### I 组 评价指标
| # | 关键词 | 目标 |
|---|--------|------|
| 1 | `benchmark 3D reconstruction metrics` | 评测基准 |
| 2 | `Chamfer distance Hausdorff point cloud` | 点云距离 |
| 3 | `MMD EMD generative model` | 分布距离 |

---

## 三、目标论文清单（已知 DOI + 直接链接）

### A 组（4 篇需下）

| # | 论文 | 期刊/会议 | DOI | 直链 | 优先级 |
|---|------|-----------|-----|------|--------|
| 1 | Aykin & Negahdaripour 2017 "Space Carving" | IEEE JOE 42(3):574-589 | 10.1109/JOE.2016.2591738 | IEEE | ⭐⭐⭐ |
| 2 | Aykin & Negahdaripour 2013 "Image Formation" | OCEANS 2013 San Diego | 10.23919/OCEANS.2013.6741270 | IEEE | ⭐⭐ |
| 3 | Negahdaripour 2012 "3D Scene Interpretation" | OCEANS 2012 | 10.1109/OCEANS.2012.6404921 | IEEE | ⭐⭐ |
| 4 | Wang et al. 2025 ACSim | IEEE T-RO 41:2970-2989 | 10.1109/TRO.2025.3562048 | IEEE | ⭐⭐⭐ |

### H 组（4 篇需下）

| # | 论文 | 期刊/会议 | DOI | 直链 | 优先级 |
|---|------|-----------|-----|------|--------|
| 5 | Stanic et al. 1998 "Shallow-water Reverberation" | IEEE JOE 23(3):199 | 10.1109/48.701189 | IEEE | ⭐⭐ |
| 6 | Tang et al. 2020 "Mobile Active Sonar Height" | Applied Acoustics 169:107459 | 10.1016/j.apacoust.2020.107459 | Elsevier | ⭐⭐⭐ |
| 7 | Jackson et al. 1986 "High-frequency Backscatter" | JASA 80(4):1188 | 10.1121/1.394286 | AIP | ⭐ |
| 8 | Parnum 2004 "Angular Dependence Backscatter" | ACOUSTICS 2004 | — | 开放 | ⭐ |

### G 组（2 篇需下）

| # | 论文 | 期刊/会议 | DOI | 优先级 |
|---|------|-----------|-----|--------|
| 9 | Zhang 2016 "On Degeneracy" | TRO / IJRR | 待查 | ⭐⭐ |
| 10 | Yang Carlone GNC | ICRA 2019 / IJRR 2020 | 10.1177/0278364919880633 | ⭐⭐ |

### B 组（3 篇需下）

| # | 论文 | 期刊/会议 | DOI | 优先级 |
|---|------|-----------|-----|--------|
| 11 | Yang et al. 2020 GNC | IJRR | 10.1177/0278364919880633 | ⭐⭐ |
| 12 | Sünderhauf 2012 SC | IROS | 10.1109/IROS.2012.6385566 | ⭐ |
| 13 | Agarwal 2013 DCS | IROS | 10.1109/IROS.2013.6696567 | ⭐ |

### F 组（2 篇需下）

| # | 论文 | 期刊/会议 | 优先级 |
|---|------|-----------|--------|
| 14 | Kazhdan Hoppe 2013 Screened Poisson | CGF | ⭐⭐ |
| 15 | Hoppe 1992 Surface Reconstruction | SIGGRAPH | ⭐⭐ |

### E 组（3 篇需下）

| # | 论文 | 期刊/会议 | 优先级 |
|---|------|-----------|--------|
| 16 | SAM adaptation underwater | ArXiv 2024 | ⭐ |
| 17 | LoRA segmentation sonar | 待查 | ⭐ |
| 18 | marine-debris FLS segmentation | ArXiv | ⭐ |

### 扩展（1 篇）

| # | 论文 | 期刊/会议 | 优先级 |
|---|------|-----------|--------|
| 19 | Aykin 2016 JOE "Modeling 2-D Lens-Based" | 10.1109/JOE.2016.2518838 | ⭐ |
| 20 | Negahdaripour 2020 JOE FLS Stereo | 10.1109/JOE.2018.2875574 | ⭐ |
| 21 | Feng 2024 RA-L "Differentiable Space Carving" | 10.1109/LRA.2024.3469778 | ⭐ |
| 22 | Zhou 2025 TIM "Shadow Extraction" | 待查 | ⭐ |

---

## 四、校园网下载脚本

### 4.1 PowerShell 脚本（`论文集合\campus_fetch.ps1`，与本手册同目录）

```powershell
$ErrorActionPreference = 'Continue'
$paperDir = "F:\sfm\论文集"

# 校园网环境下，应该能直接访问 IEEE / Elsevier / Springer
# 验证当前出口 IP
Write-Host "=== 当前出口 IP 验证 ==="
try {
    $ip = (Invoke-WebRequest -Uri "https://api.ipify.org" -UseBasicParsing -TimeoutSec 10).Content
    Write-Host "Exit IP: $ip"
    Write-Host "如果 IP 是教育网/机构段(EDU/CN)，说明已接入校园网"
} catch {
    Write-Host "[WARN] 无法获取 IP，请确认校园网已连接"
}

# === A 组：阴影几何 (4 篇) ===
$groupA = @(
    @{ id = 1; title = "Aykin_Negahdaripour_2017_Space_Carving_JOE"; doi = "10.1109/JOE.2016.2591738" },
    @{ id = 2; title = "Aykin_Negahdaripour_2013_Image_Formation_OCEANS"; doi = "10.23919/OCEANS.2013.6741270" },
    @{ id = 3; title = "Negahdaripour_2012_3D_Scene_Interpretation_OCEANS"; doi = "10.1109/OCEANS.2012.6404921" },
    @{ id = 4; title = "Wang_2025_ACSim_Acoustic_Camera_TRO"; doi = "10.1109/TRO.2025.3562048" }
)

# === H 组：海底散射 + 仿真 (4 篇) ===
$groupH = @(
    @{ id = 5; title = "Stanic_1998_Shallow_water_Reverberation_JOE"; doi = "10.1109/48.701189" },
    @{ id = 6; title = "Tang_2020_Mobile_Active_Sonar_Height_AppliedAcoustics"; doi = "10.1016/j.apacoust.2020.107459" },
    @{ id = 7; title = "Jackson_1986_High_frequency_Backscatter_JASA"; doi = "10.1121/1.394286" },
    @{ id = 8; title = "Parnum_2004_Angular_Dependence_Backscatter_ACOUSTICS"; doi = "NO_DOI" }
)

# === G 组：可观测性 (2 篇) ===
$groupG = @(
    @{ id = 9; title = "Yang_Carlone_GNC_IJRR_2020"; doi = "10.1177/0278364919880633" },
    @{ id = 10; title = "Sunderhauf_Switchable_Constraints_IROS_2012"; doi = "10.1109/IROS.2012.6385566" }
)

# === F 组：网格 Poisson (2 篇) ===
$groupF = @(
    @{ id = 11; title = "Kazhdan_Hoppe_2013_Screened_Poisson_CGF"; doi = "10.1111/cgf.12178" }
)

# === 整合所有组 ===
$allPapers = $groupA + $groupH + $groupG + $groupF

$success = 0
$fail = 0
$skip = 0

Write-Host "`n=== 开始下载 $($allPapers.Count) 篇论文 ===`n"

foreach ($p in $allPapers) {
    $outFile = Join-Path $paperDir ($p.title + ".pdf")
    if (Test-Path $outFile) {
        $sz = (Get-Item $outFile).Length
        Write-Host "[SKIP] $($p.title) already exists ($sz bytes)"
        $skip++
        continue
    }

    # 优先 Sci-Hub，再 IEEE
    $urls = @(
        "https://sci-hub.se/$($p.doi)",
        "https://sci-hub.ru/$($p.doi)",
        "https://sci-hub.box/$($p.doi)",
        "https://www.sci-hub.st/$($p.doi)"
    )

    $downloaded = $false
    foreach ($url in $urls) {
        try {
            Write-Host "[TRY] $url"
            $response = Invoke-WebRequest -Uri $url -OutFile $outFile -UseBasicParsing -TimeoutSec 90 -MaximumRedirection 10
            $sz = (Get-Item $outFile).Length
            if ($sz -gt 100000) {
                Write-Host "  [OK] $($p.title) ($sz bytes)"
                $success++
                $downloaded = $true
                break
            } else {
                Write-Host "  [WARN] too small: $sz bytes"
            }
        } catch {
            Write-Host "  [FAIL] $($_.Exception.Message)"
        }
    }

    if (-not $downloaded) {
        $fail++
        Write-Host "  [ERROR] $($p.title) 所有源都失败"
    }
}

Write-Host "`n=== 总结 ==="
Write-Host "成功: $success"
Write-Host "失败: $fail"
Write-Host "跳过: $skip"
```

### 4.2 校园网启动流程

1. **连接校园网**
   - 教育网/CERNET 直接连
   - 校外用 EasyConnect / WebVPN / 校园 VPN 客户端
   - 验证 IP 段含 `.edu.cn` 或机构 IP

2. **运行脚本**
   ```powershell
   cd <论文集合目录>          # 例如 C:\Users\q\Desktop\论文集合
   powershell -ExecutionPolicy Bypass -File .\campus_fetch.ps1
   ```
   > 脚本会自动把 PDF 放到脚本所在目录的 `论文集\` 子目录，没有该子目录就直接放脚本所在目录。

3. **预期产出**
   - 11 篇 P0/P1 关键论文 PDF
   - 失败的需要手抓或机构代理二次尝试

### 4.3 如果还有失败

- **IEEE**：用 WebVPN 后再试（`vpn.your-univ.edu.cn` → IEEE 链接）
- **Elsevier ScienceDirect**：同上
- **AIP / JASA**：很多已开放
- **ResearchGate**：作者主页可能有 author-uploaded PDF

---

## 五、产出文档链

```
<论文集合目录>\
├── 论文集\                            ← 论文 PDF 库（当前 27 + 校园网预期 11 = 38 篇）
├── LIT_NOTES.md                        ← 阅读笔记（按 A-H 组分类）
├── PAPER_SEARCH_PLAN.md                ← 论文查找计划（覆盖表 + 时间表）
├── WANTED_PAPERS.md                    ← 本文件：校园网爬取手册
└── campus_fetch.ps1                    ← 一键下载脚本
```

---

*本手册由 Session 12 阶段产出物，配合 `WORK_LOG.md` V10 一起记录*
