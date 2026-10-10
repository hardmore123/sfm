import subprocess, sys
from pathlib import Path

T = Path("F:/sfm/大论文思想路线/minimax任务分发/工具")
L = Path("F:/sfm/大论文思想路线/minimax任务分发/回报/日志")
res = {}
for s in ["check_data_structure.py", "regen_manifest.py", "check_manifest.py",
          "check_obsolete.py", "check_wording.py", "check_links.py"]:
    res[s] = subprocess.run([sys.executable, str(T / s)], cwd=str(T), capture_output=True).returncode
lines = [repr(res)]
for log, n in [("check_data_structure.log", 6), ("check_manifest.log", 7),
               ("check_obsolete.log", 4), ("check_wording.log", 4), ("check_links.log", 6)]:
    lines += (L / log).read_text(encoding="utf-8").splitlines()[:n][-2:]
Path("F:/sfm/_kiro_recheck/final_checks.txt").write_text("\n".join(lines), encoding="utf-8")
