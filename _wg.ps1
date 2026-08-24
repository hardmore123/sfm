$c = Get-Command winget -ErrorAction SilentlyContinue
if ($c) { "WINGET: " + $c.Source | Set-Content -Encoding utf8 wg.txt }
else { "WINGET_NONE" | Set-Content -Encoding utf8 wg.txt }
