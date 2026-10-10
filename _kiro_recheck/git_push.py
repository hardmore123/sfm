import os, subprocess
from pathlib import Path

out = []
BR = "docs/theory-correction-and-roadmap"
attempts = [
    ("ssh-443", "ssh://git@ssh.github.com:443/hardmore123/sfm.git"),
    ("https-origin", "origin"),
]
for tag, remote in attempts:
    env = dict(os.environ)
    env["GIT_SSH_COMMAND"] = ("ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new "
                              "-o ConnectTimeout=20")
    try:
        r = subprocess.run(["git", "push", remote, f"{BR}:{BR}"], cwd="F:/sfm",
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", env=env, timeout=200)
        out.append(f"[{tag}] rc={r.returncode}\n{r.stdout}{r.stderr}")
        if r.returncode == 0:
            break
    except subprocess.TimeoutExpired:
        out.append(f"[{tag}] timeout")
Path("F:/sfm/_kiro_recheck/git_push.log").write_text("\n".join(out), encoding="utf-8")
