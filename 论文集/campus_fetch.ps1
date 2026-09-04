# 校园网下载脚本
# 配合 WANTED_PAPERS.md 使用
# 在校园网/机构 VPN 环境下运行

$ErrorActionPreference = 'Continue'

# 论文存放目录：脚本所在目录的 "论文集" 子目录，若不存在则用脚本所在目录
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$paperDir = Join-Path $scriptDir "论文集"
if (-not (Test-Path $paperDir)) {
    $paperDir = $scriptDir
}
Write-Host "论文目录: $paperDir"

# 验证当前出口 IP
Write-Host "=== 当前出口 IP 验证 ==="
try {
    $ip = (Invoke-WebRequest -Uri "https://api.ipify.org" -UseBasicParsing -TimeoutSec 10).Content
    Write-Host "Exit IP: $ip"
    if ($ip -match "edu\.cn|\.ac\.|byu\.|mit\.|cmu\.|harvard\.|stanford\.") {
        Write-Host "[OK] 已在校园网/机构网下" -ForegroundColor Green
    } else {
        Write-Host "[WARN] IP 不是教育网/机构网，可能无法访问 IEEE/Elsevier" -ForegroundColor Yellow
    }
} catch {
    Write-Host "[ERROR] 无法获取 IP，请确认网络" -ForegroundColor Red
}

# 论文清单（id, title, doi）
$allPapers = @(
    # === A 组：阴影几何 (4 篇) ===
    @{ id = 1; title = "Aykin_Negahdaripour_2017_Space_Carving_JOE"; doi = "10.1109/JOE.2016.2591738" },
    @{ id = 2; title = "Aykin_Negahdaripour_2013_Image_Formation_OCEANS"; doi = "10.23919/OCEANS.2013.6741270" },
    @{ id = 3; title = "Negahdaripour_2012_3D_Scene_Interpretation_OCEANS"; doi = "10.1109/OCEANS.2012.6404921" },
    @{ id = 4; title = "Wang_2025_ACSim_Acoustic_Camera_TRO"; doi = "10.1109/TRO.2025.3562048" },
    # === H 组：海底散射 + 仿真 (4 篇) ===
    @{ id = 5; title = "Stanic_1998_Shallow_water_Reverberation_JOE"; doi = "10.1109/48.701189" },
    @{ id = 6; title = "Tang_2020_Mobile_Active_Sonar_Height_AppliedAcoustics"; doi = "10.1016/j.apacoust.2020.107459" },
    @{ id = 7; title = "Jackson_1986_High_frequency_Backscatter_JASA"; doi = "10.1121/1.394286" },
    @{ id = 8; title = "Parnum_2004_Angular_Dependence_Backscatter_ACOUSTICS"; doi = "NO_DOI" },
    # === G 组：可观测性 (2 篇) ===
    @{ id = 9; title = "Yang_Carlone_GNC_IJRR_2020"; doi = "10.1177/0278364919880633" },
    @{ id = 10; title = "Sunderhauf_Switchable_Constraints_IROS_2012"; doi = "10.1109/IROS.2012.6385566" },
    # === F 组：网格 Poisson (1 篇) ===
    @{ id = 11; title = "Kazhdan_Hoppe_2013_Screened_Poisson_CGF"; doi = "10.1111/cgf.12178" }
)

$success = 0
$fail = 0
$skip = 0

Write-Host "`n=== 开始下载 $($allPapers.Count) 篇论文 ===`n"

foreach ($p in $allPapers) {
    $outFile = Join-Path $paperDir ($p.title + ".pdf")
    if (Test-Path $outFile) {
        $sz = (Get-Item $outFile).Length
        Write-Host "[SKIP] $($p.title) already exists ($sz bytes)" -ForegroundColor DarkGray
        $skip++
        continue
    }

    # 优先 Sci-Hub（多源重试），再 IEEE
    $urls = @()
    if ($p.doi -ne "NO_DOI") {
        $urls += "https://sci-hub.se/$($p.doi)"
        $urls += "https://sci-hub.ru/$($p.doi)"
        $urls += "https://sci-hub.box/$($p.doi)"
        $urls += "https://www.sci-hub.st/$($p.doi)"
    }

    $downloaded = $false
    foreach ($url in $urls) {
        try {
            Write-Host "[TRY] $url" -ForegroundColor Cyan
            Invoke-WebRequest -Uri $url -OutFile $outFile -UseBasicParsing -TimeoutSec 90 -MaximumRedirection 10
            $sz = (Get-Item $outFile).Length
            if ($sz -gt 100000) {
                Write-Host "  [OK] $($p.title) ($sz bytes)" -ForegroundColor Green
                $success++
                $downloaded = $true
                break
            } else {
                Write-Host "  [WARN] too small: $sz bytes"
            }
        } catch {
            Write-Host "  [FAIL] $($_.Exception.Message)" -ForegroundColor DarkRed
        }
    }

    if (-not $downloaded) {
        $fail++
        Write-Host "  [ERROR] $($p.title) 所有源都失败，需要机构代理手动下载" -ForegroundColor Red
    }
}

Write-Host "`n=== 总结 ===" -ForegroundColor Yellow
Write-Host "成功: $success"
Write-Host "失败: $fail"
Write-Host "跳过: $skip"
Write-Host "总文件: $((Get-ChildItem $paperDir -Filter '*.pdf').Count)"
