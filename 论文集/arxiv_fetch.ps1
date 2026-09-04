# 定向下载脚本：只抓 arXiv / 作者直链已确认的论文
# 校园网对 Sci-Hub / IEEE 都封了，但 arXiv 和 Hugues Hoppe 个人站都通

$ErrorActionPreference = 'Continue'
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$paperDir = $scriptDir
Write-Host "论文目录: $paperDir`n"

# 每条: id, title, url, source
$targets = @(
    @{
        id = 1
        title = "Yang_Carlone_GNC_TLS_RSS2019"
        url = "https://arxiv.org/pdf/1903.08588"
        source = "arXiv"
    }
    @{
        id = 2
        title = "Yang_Carlone_Certifiable_Perception_ICRA2020"
        url = "https://arxiv.org/pdf/1909.08605"
        source = "arXiv"
    }
    @{
        id = 3
        title = "Kazhdan_Hoppe_2013_Screened_Poisson_CGF"
        url = "https://www.hhoppe.com/screenedpoisson.pdf"
        source = "Hugues Hoppe"
    }
    @{
        id = 4
        title = "Kazhdan_Bolitho_Hoppe_2006_Poisson_Reconstruction"
        url = "https://www.cs.jhu.edu/~misha/Code/PoissonRecon/Version%201.6/poissonrecon.pdf"
        source = "Kazhdan 主页 (尝试)"
    }
)

$success = 0
$fail = 0
$skip = 0

Write-Host "=== 开始下载 $($targets.Count) 篇（仅 arXiv + 作者直链） ===`n"

foreach ($t in $targets) {
    $outFile = Join-Path $paperDir ($t.title + ".pdf")
    if (Test-Path $outFile) {
        $sz = (Get-Item $outFile).Length
        if ($sz -gt 100000) {
            Write-Host "[SKIP] $($t.title) 已存在 ($sz bytes)" -ForegroundColor DarkGray
            $skip++
            continue
        } else {
            Write-Host "[REDO] $($t.title) 存在但过小 ($sz bytes)，重新下载" -ForegroundColor Yellow
        }
    }

    try {
        Write-Host "[TRY] [$($t.source)] $($t.url)" -ForegroundColor Cyan
        Invoke-WebRequest -Uri $t.url -OutFile $outFile -UseBasicParsing -TimeoutSec 60 -MaximumRedirection 8
        $sz = (Get-Item $outFile).Length
        if ($sz -gt 100000) {
            Write-Host "  [OK] $($t.title) ($sz bytes)" -ForegroundColor Green
            $success++
        } else {
            Write-Host "  [WARN] 过小: $sz bytes，删除" -ForegroundColor Yellow
            $outFile | Rename-Item -NewName { $_.Name -replace '\.pdf$', '.stub.pdf' }
            $fail++
        }
    } catch {
        Write-Host "  [FAIL] $($_.Exception.Message)" -ForegroundColor Red
        $fail++
    }
}

Write-Host "`n=== 总结 ===" -ForegroundColor Yellow
Write-Host "成功: $success"
Write-Host "失败: $fail"
Write-Host "跳过: $skip"
Write-Host "新增 PDF 总数: $((Get-ChildItem $paperDir -Filter '*.pdf' | Where-Object { $_.Length -gt 100000 }).Count)"
