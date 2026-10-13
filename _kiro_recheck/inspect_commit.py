import subprocess
from collections import Counter
from pathlib import Path

ROOT = Path("F:/sfm")
r = subprocess.run(["git", "-c", "core.quotepath=false", "show", "--stat=400", "--format=", "--name-status", "HEAD"],
                   cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
rows = [l.split("\t", 1) for l in r.stdout.splitlines() if "\t" in l]
files = [p for _, p in rows]
top = Counter("/".join(p.split("/")[:2]) for p in files)
ext = Counter(Path(p).suffix.lower() for p in files)
sz = [(ROOT / p).stat().st_size for p in files if (ROOT / p).exists()]
junction = [p for p in files if p.startswith("论文代码与数据/02_代码/scene_set") or p.startswith("论文代码与数据/02_代码/innov2")]
out = [f"HEAD 文件数 {len(files)}，合计 {sum(sz)/1e6:.2f} MB，最大 {max(sz)/1e6:.2f} MB",
       f"状态 {Counter(s for s, _ in rows)}", f"junction 副本 {len(junction)}",
       "按目录：", *[f"  {n:4d}  {k}" for k, n in top.most_common()],
       "按扩展名：", *[f"  {n:4d}  {k or '(无)'}" for k, n in ext.most_common()]]
(ROOT / "_kiro_recheck/inspect_commit.txt").write_text("\n".join(out), encoding="utf-8")
