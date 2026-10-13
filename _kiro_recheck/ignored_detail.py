import subprocess
from collections import defaultdict
from pathlib import Path

ROOT = Path("F:/sfm")
r = subprocess.run(["git", "-c", "core.quotepath=false", "ls-files", "--others", "--ignored",
                    "--exclude-standard"], cwd=ROOT, capture_output=True, text=True,
                   encoding="utf-8", errors="replace")
files = [f for f in r.stdout.splitlines() if f]

# 规则归属：哪条 .gitignore 规则排除了它
chk = subprocess.run(["git", "-c", "core.quotepath=false", "check-ignore", "-v", "--stdin"],
                     cwd=ROOT, input="\n".join(files), capture_output=True, text=True,
                     encoding="utf-8", errors="replace").stdout.splitlines()
rule_of = {}
for line in chk:
    meta, path = line.split("\t", 1)
    rule_of[path] = meta.split(":", 2)[2]

DATA_EXT = {".npy", ".zip", ".ply", ".h5", ".hdf5", ".pt", ".pth", ".ckpt", ".png", ".jpg",
            ".jpeg", ".xml", ".csv", ".bmp", ".tif", ".tiff", ".blend", ".blend1", ".exe"}
by_rule = defaultdict(lambda: [0, 0])
info_files = []          # 非数据类：文档、代码、文本——这类才可能是"信息"
for f in files:
    p = ROOT / f
    s = p.stat().st_size if p.exists() else 0
    rule = rule_of.get(f, "?")
    by_rule[rule][0] += 1
    by_rule[rule][1] += s
    if p.suffix.lower() not in DATA_EXT and "__pycache__" not in f and not f.endswith((".pyc", ".pyo")):
        info_files.append((f, s, rule))

out = [f"被忽略文件总数 {len(files)}，合计 {sum(v[1] for v in by_rule.values())/1e9:.2f} GB", "",
       "== 按排除规则汇总 =="]
for rule, (n, s) in sorted(by_rule.items(), key=lambda kv: -kv[1][1]):
    out.append(f"{s/1e6:11.1f} MB  {n:6d} 个  规则 {rule}")
out += ["", f"== 非数据类文件（文档/代码/文本/配置）共 {len(info_files)} 个 =="]
agg = defaultdict(list)
for f, s, rule in info_files:
    agg[Path(f).suffix.lower() or "(无扩展名)"].append((f, s, rule))
for ext, lst in sorted(agg.items(), key=lambda kv: -len(kv[1])):
    out.append(f"-- {ext}：{len(lst)} 个，{sum(x[1] for x in lst)/1e6:.2f} MB")
    for f, s, rule in sorted(lst)[:60]:
        out.append(f"     {s/1024:9.1f} KB  {f}   [{rule}]")
    if len(lst) > 60:
        out.append(f"     ……另有 {len(lst)-60} 个")
(ROOT / "_kiro_recheck/ignored_detail.txt").write_text("\n".join(out), encoding="utf-8")
