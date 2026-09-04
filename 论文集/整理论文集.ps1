# 论文集合整理脚本
# 任务：
#   1. 重命名 4 篇主论文到标准约定（Author_Year_Keyword_Journal.pdf）
#   2. 重命名 1 篇额外好货（TEASER）
#   3. 把垃圾文件（stub / probe / 重复 / 无关）移到 _junk 子目录，等用户确认后删除
# 幂等：重复运行只会"已处理"提示，不会重复操作

$ErrorActionPreference = 'Stop'
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$junkDir = Join-Path $scriptDir "_junk_to_delete"

# === 1. 重命名映射 ===
$renames = @(
    # 主论文
    @{
        from = "1-s2.0-S0003682X20305636-main.pdf"
        to   = "Tang_2020_Mobile_Active_Sonar_Height_AppliedAcoustics.pdf"
        note = "Tang 2020 移动声呐高度反演 (DOI 10.1016/j.apacoust.2020.107459)"
    }
    @{
        from = "ACSim_A_Novel_Acoustic_Camera_Simulator_With_Recursive_Ray_Tracing_Artifact_Modeling_and_Ground_Truthing.pdf"
        to   = "Wang_2025_ACSim_Acoustic_Camera_TRO.pdf"
        note = "Wang 2025 ACSim 声学相机仿真 (DOI 10.1109/TRO.2025.3562048)"
    }
    @{
        from = "Switchable_constraints_for_robust_pose_graph_SLAM.pdf"
        to   = "Sunderhauf_Switchable_Constraints_IROS_2012.pdf"
        note = "Sunderhauf 2012 鲁棒位姿图 (DOI 10.1109/IROS.2012.6385566)"
    }
    @{
        from = "Three-Dimensional_Target_Reconstruction_From_Multiple_2-D_Forward-Scan_Sonar_Views_by_Space_Carving.pdf"
        to   = "Aykin_Negahdaripour_2017_Space_Carving_JOE.pdf"
        note = "Aykin 2017 空间雕刻 (DOI 10.1109/JOE.2016.2591738)"
    }
    # 额外好货
    @{
        from = "TEASER_Fast_and_Certifiable_Point_Cloud_Registration.pdf"
        to   = "Yang_Carlone_TEASER_IROS_2019.pdf"
        note = "TEASER 鲁棒点云配准（Yang Carlone 额外）"
    }
)

# === 2. 待隔离文件 ===
$junkPatterns = @(
    @{ pattern = "*.stub.pdf";        reason = "Sci-Hub 错误页 stub (7326B)" }
    @{ pattern = "PROBE_DELETE_*";    reason = "探针残留" }
    @{ pattern = "*Space Carving (1).pdf"; reason = "Aykin 2017 重复下载" }
    @{ pattern = "*Dereverberation.pdf";   reason = "房间声学去混响，与水下声呐无关" }
)

Write-Host "论文目录: $scriptDir" -ForegroundColor Cyan
Write-Host "隔离目录: $junkDir`n"

# === 执行重命名 ===
Write-Host "=== 1. 重命名 ===" -ForegroundColor Yellow
$renamed = 0
$skipped = 0
foreach ($r in $renames) {
    $src = Join-Path $scriptDir $r.from
    $dst = Join-Path $scriptDir $r.to
    if (-not (Test-Path $src)) {
        Write-Host "  [SKIP] 源不存在: $($r.from)" -ForegroundColor DarkGray
        $skipped++
        continue
    }
    if (Test-Path $dst) {
        Write-Host "  [SKIP] 目标已存在: $($r.to)" -ForegroundColor DarkGray
        $skipped++
        continue
    }
    Move-Item -LiteralPath $src -Destination $dst
    Write-Host "  [OK] $($r.from) -> $($r.to)" -ForegroundColor Green
    Write-Host "       $($r.note)" -ForegroundColor DarkGray
    $renamed++
}

# === 隔离垃圾 ===
Write-Host "`n=== 2. 隔离垃圾 ===" -ForegroundColor Yellow
if (-not (Test-Path $junkDir)) {
    New-Item -ItemType Directory -Path $junkDir | Out-Null
    Write-Host "  [CREATE] $junkDir" -ForegroundColor DarkGray
}
$junked = 0
foreach ($p in $junkPatterns) {
    $files = Get-ChildItem -LiteralPath $scriptDir -Filter $p.pattern -ErrorAction SilentlyContinue
    foreach ($f in $files) {
        $dest = Join-Path $junkDir $f.Name
        if (Test-Path $dest) {
            # 已隔离，跳过
            continue
        }
        Move-Item -LiteralPath $f.FullName -Destination $junkDir
        $sz = [math]::Round($f.Length/1KB, 1)
        Write-Host "  [JUNK] $($f.Name) ($sz KB) - $($p.reason)" -ForegroundColor DarkYellow
        $junked++
    }
}

# === 报告最终状态 ===
Write-Host "`n=== 最终状态 ===" -ForegroundColor Yellow
$pdfs = Get-ChildItem -LiteralPath $scriptDir -Filter "*.pdf" | Where-Object { $_.Length -gt 100000 }
Write-Host "有效论文 (>$([math]::Round(100,0)) KB): $($pdfs.Count) 篇" -ForegroundColor Green
$pdfs | Sort-Object Name | ForEach-Object {
    $sz = [math]::Round($_.Length/1MB, 2)
    Write-Host "  [$sz MB] $($_.Name)" -ForegroundColor Gray
}

$junkFiles = Get-ChildItem -LiteralPath $junkDir -ErrorAction SilentlyContinue
Write-Host "`n隔离文件: $($junkFiles.Count) 个" -ForegroundColor DarkYellow
$junkFiles | ForEach-Object {
    $sz = [math]::Round($_.Length/1KB, 1)
    Write-Host "  [$sz KB] $($_.Name)" -ForegroundColor DarkGray
}

Write-Host "`n=== 总结 ===" -ForegroundColor Yellow
Write-Host "重命名: $renamed / 跳过: $skipped"
Write-Host "隔离: $junked"
Write-Host "有效论文数: $($pdfs.Count)"
Write-Host "`n隔离目录不会自动删除，请确认后手动删除：$junkDir" -ForegroundColor DarkGray
