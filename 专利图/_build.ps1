Set-Location $PSScriptRoot
$csc = "C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe"
& $csc /nologo /optimize+ /out:draw_figs.exe /r:System.Drawing.dll draw_patent_figs.cs *> build.txt
if (Test-Path ".\draw_figs.exe") {
    "BUILD_OK" | Add-Content build.txt
    & ".\draw_figs.exe" *> run.txt
    "RUN_DONE" | Add-Content run.txt
} else {
    "BUILD_FAILED" | Add-Content build.txt
}
