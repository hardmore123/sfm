"""文档内部链接与文件引用可解析性核查（供 minimax 任务06 直接运行，勿改）。

扫描有效文档目录下的 .md，抽取两类本地引用并检查目标是否存在：
  1) Markdown 链接 [text](target)  —— 仅当 target 像本地文件（带已知扩展名、非 http/锚点）
  2) Kiro 文件引用  #[[file:target]]
target 相对该 .md 所在目录解析。

输出按"有效目录 / 作废归档目录"分组，因为作废归档里的死链是预期的。
退出码：有效目录内无死链 => 0；否则 => 4。
"""
import io
import re
import sys
from pathlib import Path
from urllib.parse import unquote

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# 直接把报告写成 UTF-8 文件，绕开 PowerShell 重定向编码问题
REPORT = Path(__file__).resolve().parent.parent / "回报" / "日志" / "check_links.log"
REPORT.parent.mkdir(parents=True, exist_ok=True)
_buf = []


def out(s=""):
    print(s)
    _buf.append(s)

ROOTS = [Path("F:/sfm/大论文思想路线"), Path("F:/sfm/论文代码与数据")]
ARCHIVE_MARK = "06_作废归档"

# 认作"本地文件"的扩展名
EXTS = (".md", ".py", ".png", ".json", ".pdf", ".npy", ".yaml", ".yml",
        ".csv", ".txt", ".ply", ".cs", ".exe", ".jpg", ".jpeg")

LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
FILEREF_RE = re.compile(r"#\[\[file:([^\]]+)\]\]")


def is_local_file_target(t: str) -> bool:
    t = t.strip()
    if not t:
        return False
    if t.startswith(("http://", "https://", "mailto:", "#")):
        return False
    # 去掉锚点
    base = t.split("#")[0].strip()
    if not base:
        return False
    return base.lower().endswith(EXTS)


def resolve_ok(md_path: Path, target: str) -> bool:
    base = unquote(target.split("#")[0].strip())
    p = (md_path.parent / base).resolve()
    return p.exists()


broken_active = []
broken_archive = []
n_links = 0

for root in ROOTS:
    if not root.exists():
        continue
    for md in root.rglob("*.md"):
        # 跳过本分发目录自身，避免自引用噪声
        if "minimax任务分发" in str(md):
            continue
        try:
            text = md.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        targets = []
        for m in LINK_RE.finditer(text):
            t = m.group(1)
            if is_local_file_target(t):
                targets.append(t)
        for m in FILEREF_RE.finditer(text):
            targets.append(m.group(1))
        for t in targets:
            n_links += 1
            if not resolve_ok(md, t):
                rel = str(md).replace("F:\\sfm\\", "")
                entry = f"{rel}  ->  {t}"
                if ARCHIVE_MARK in str(md):
                    broken_archive.append(entry)
                else:
                    broken_active.append(entry)

out("=" * 80)
out("文档内部链接与文件引用核查")
out("=" * 80)
out(f"检查的本地引用总数：{n_links}")
out(f"有效目录内死链：{len(broken_active)}")
out(f"作废归档内死链（预期，可忽略）：{len(broken_archive)}")
out()
if broken_active:
    out("【有效目录内死链 —— 需处理】")
    for e in broken_active:
        out(f"    {e}")
else:
    out("✅ 有效目录内无死链")
out()
if broken_archive:
    out("【作废归档内死链 —— 预期，仅列出】")
    for e in broken_archive:
        out(f"    {e}")

REPORT.write_text("\n".join(_buf), encoding="utf-8")
out(f"\n[报告已写入] {REPORT}")
sys.exit(0 if not broken_active else 4)
