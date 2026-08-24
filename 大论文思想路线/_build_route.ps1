$ErrorActionPreference = "Continue"
$csc = "C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe"
& $csc /nologo /optimize+ /out:draw_route.exe /r:System.Drawing.dll draw_route.cs *> build_route.txt
if (Test-Path ".\draw_route.exe") {
    "BUILD_OK" | Add-Content build_route.txt
    & ".\draw_route.exe" *> run_route.txt
    "RUN_DONE" | Add-Content run_route.txt
} else {
    "BUILD_FAILED" | Add-Content build_route.txt
}
