$ErrorActionPreference = "Continue"
$csc = "C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe"
$dir = "c:\Users\likunyuan\Desktop\private document\sfm"
Set-Location $dir
& $csc /nologo /optimize+ /out:ba.exe /r:System.Drawing.dll ba.cs *> build.txt
if (Test-Path "$dir\ba.exe") {
    "BUILD_OK" | Add-Content build.txt
    & "$dir\ba.exe" *> run.txt
    "RUN_DONE" | Add-Content run.txt
} else {
    "BUILD_FAILED" | Add-Content build.txt
}
