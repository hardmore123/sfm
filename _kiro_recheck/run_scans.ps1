$env:PYTHONIOENCODING = "utf-8"
$tools = "F:\sfm\大论文思想路线\minimax任务分发\工具"
Set-Location -LiteralPath $tools
python "$tools\check_obsolete.py" | Out-Null; $a = $LASTEXITCODE
python "$tools\check_wording.py"  | Out-Null; $b = $LASTEXITCODE
python "$tools\regen_manifest.py" | Out-Null
python "$tools\check_manifest.py" | Out-Null; $c = $LASTEXITCODE
"obsolete=$a wording=$b manifest=$c" | Out-File -Encoding utf8 "F:\sfm\_kiro_recheck\scan_exit.txt"
