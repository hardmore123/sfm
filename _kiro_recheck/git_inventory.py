import re, subprocess
from pathlib import Path

ROOT = Path("F:/sfm")
out = []


def git(*a):
    return subprocess.run(["git", "-c", "core.quotepath=false", *a], cwd=ROOT,
                          capture_output=True, text=True, encoding="utf-8", errors="replace").stdout


# 1) 未跟踪且未被忽略
untracked = [l for l in git("ls-files", "--others", "--exclude-standard").splitlines() if l]
out.append(f"== 未跟踪(未忽略) {len(untracked)} 个 ==")
tot = 0
for f in untracked:
    s = (ROOT / f).stat().st_size if (ROOT / f).exists() else 0
    tot += s
for f in untracked[:40]:
    out.append(f"  {f}  {(ROOT / f).stat().st_size // 1024} KB")
out.append(f"  合计 {tot/1e6:.2f} MB；>50MB 的：" +
           str([f for f in untracked if (ROOT / f).stat().st_size > 50e6]))

# 2) 简单敏感信息扫描（未跟踪文件）
pat = re.compile(r"(ghp_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY|password\s*=|api[_-]?key\s*=)", re.I)
hits = []
for f in untracked:
    p = ROOT / f
    if p.suffix.lower() in (".py", ".md", ".txt", ".json", ".log", ".yaml", ".csv") and p.stat().st_size < 5e6:
        t = p.read_text(encoding="utf-8", errors="ignore")
        if pat.search(t):
            hits.append(f)
out.append(f"== 敏感信息命中：{hits}")

# 3) 被 .gitignore 忽略的（按顶层目录汇总体积）
ign = [l for l in git("ls-files", "--others", "--ignored", "--exclude-standard", "--directory").splitlines() if l]
out.append(f"== 被 .gitignore 忽略的条目 {len(ign)} 个（按体积前 25）==")
sized = []
for e in ign:
    p = ROOT / e.rstrip("/")
    if p.is_dir():
        s = sum(q.stat().st_size for q in p.rglob("*") if q.is_file())
    elif p.exists():
        s = p.stat().st_size
    else:
        s = 0
    sized.append((s, e))
sized.sort(reverse=True)
for s, e in sized[:25]:
    out.append(f"  {s/1e6:10.1f} MB  {e}")
out.append(f"  忽略合计 {sum(s for s, _ in sized)/1e9:.2f} GB")
big = []
for s, e in sized:
    p = ROOT / e.rstrip("/")
    files = [p] if p.is_file() else list(p.rglob("*")) if p.is_dir() else []
    big += [q for q in files if q.is_file() and q.stat().st_size > 100e6]
out.append(f"  其中单文件 >100MB（GitHub 硬上限）：{len(big)} 个，例 {[str(q.relative_to(ROOT)) for q in big[:5]]}")
out.append("== .gitignore ==")
out.append((ROOT / ".gitignore").read_text(encoding="utf-8", errors="replace"))
(ROOT / "_kiro_recheck/git_inventory.txt").write_text("\n".join(out), encoding="utf-8")
