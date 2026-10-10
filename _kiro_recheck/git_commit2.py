import os, subprocess
from pathlib import Path

ROOT = Path("F:/sfm")
log = []


def git(*a, env=None, timeout=200):
    r = subprocess.run(["git", "-c", "core.quotepath=false", *a], cwd=ROOT, capture_output=True,
                       text=True, encoding="utf-8", errors="replace", env=env, timeout=timeout)
    log.append(f"$ git {' '.join(a)} -> {r.returncode}\n{r.stdout[-3000:]}{r.stderr[-2000:]}")
    return r


untracked = [l for l in git("ls-files", "--others", "--exclude-standard").stdout.splitlines() if l]
log.append(f"untracked to add: {len(untracked)}")
git("add", "--", *untracked)
staged = [l for l in git("diff", "--cached", "--name-only").stdout.splitlines() if l]
log.append(f"staged {len(staged)}; npy/大文件={[s for s in staged if s.endswith('.npy') or (ROOT/s).stat().st_size > 50e6]}")
git("commit", "-m",
    "chore: 补传剩余未跟踪文件（复核脚本与日志、MANIFEST 备份、E 组文献报告）\n\n"
    "- _kiro_recheck/：Kiro 对 minimax 工作的复核脚本、minimax 原始日志备份、T7/R-X3 诊断脚本\n"
    "- 论文代码与数据/MANIFEST.json.bak：按旧嵌套布局生成的 MANIFEST（历史快照）\n"
    "- sfm_synthetic_pillars/E_GROUP_PAPER_REPORT.md")
git("log", "--oneline", "-3")
git("push", "origin", "docs/theory-correction-and-roadmap:docs/theory-correction-and-roadmap", timeout=240)
log.append("== remaining untracked ==\n" + git("ls-files", "--others", "--exclude-standard").stdout)
log.append("== status -sb ==\n" + git("status", "-sb").stdout[:400])
(ROOT / "_kiro_recheck/git_commit2.log").write_text("\n".join(log), encoding="utf-8")
