import subprocess, sys
from pathlib import Path

TOOLS = Path("F:/sfm/大论文思想路线/minimax任务分发/工具")
res = {}
for s in ["check_obsolete.py", "check_wording.py", "regen_manifest.py", "check_manifest.py"]:
    r = subprocess.run([sys.executable, str(TOOLS / s)], cwd=str(TOOLS), capture_output=True)
    res[s] = r.returncode
Path("F:/sfm/_kiro_recheck/scan_exit.txt").write_text(repr(res), encoding="utf-8")
