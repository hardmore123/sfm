import subprocess, time
from pathlib import Path

out = []
for i in range(6):
    try:
        r = subprocess.run(["git", "push", "origin",
                            "docs/theory-correction-and-roadmap:docs/theory-correction-and-roadmap"],
                           cwd="F:/sfm", capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=180)
        out.append(f"try {i+1}: rc={r.returncode} {r.stderr.strip()[-300:]}")
        if r.returncode == 0:
            break
    except subprocess.TimeoutExpired:
        out.append(f"try {i+1}: timeout")
    time.sleep(15)
s = subprocess.run(["git", "status", "-sb"], cwd="F:/sfm", capture_output=True, text=True,
                   encoding="utf-8", errors="replace").stdout.splitlines()[0]
out.append(s)
Path("F:/sfm/_kiro_recheck/git_push_retry.log").write_text("\n".join(out), encoding="utf-8")
