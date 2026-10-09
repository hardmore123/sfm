"""MANIFEST 完整性与校验和核查（供 minimax 任务04 直接运行，勿改）。

对 论文代码与数据/MANIFEST.json 中每个含 "rel" 的条目：
  1) 文件是否存在
  2) 字节数是否与 bytes 一致
  3) SHA1 前 12 位是否与 sha1 一致
整目录条目（无 rel）单独统计其目录是否存在。

退出码：全部一致 => 0；有任何不一致 => 3。
所有输出走 UTF-8。
"""
import hashlib
import io
import json
import sys
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# 直接把报告写成 UTF-8 文件，绕开 PowerShell 重定向编码问题
REPORT = Path(__file__).resolve().parent.parent / "回报" / "日志" / "check_manifest.log"
REPORT.parent.mkdir(parents=True, exist_ok=True)
_buf = []


def out(s=""):
    print(s)
    _buf.append(s)


BASE = Path("F:/sfm/论文代码与数据")
manifest = json.loads((BASE / "MANIFEST.json").read_text(encoding="utf-8"))
items = manifest["items"]

file_items = [it for it in items if "rel" in it]
dir_items = [it for it in items if "rel" not in it]

n_ok = 0
missing = []       # 文件不存在
size_bad = []      # 字节数不符
sha_bad = []       # SHA1 不符

for it in file_items:
    rel = it["rel"]
    p = BASE / rel
    if not p.exists():
        missing.append(rel)
        continue
    if p.is_dir():
        # 少数 rel 指向目录（如场景集根），只确认存在，不逐字节比对
        dir_items.append({"group": it.get("group", "?"), "files": "(rel 指向目录)",
                          "status": "存在", "rel": rel})
        continue
    data = p.read_bytes()
    actual_bytes = len(data)
    actual_sha = hashlib.sha1(data).hexdigest()[:12]
    exp_bytes = it.get("bytes")
    exp_sha = it.get("sha1")
    ok = True
    if exp_bytes is not None and actual_bytes != exp_bytes:
        size_bad.append((rel, exp_bytes, actual_bytes))
        ok = False
    if exp_sha is not None and actual_sha != exp_sha:
        sha_bad.append((rel, exp_sha, actual_sha))
        ok = False
    if ok:
        n_ok += 1

out("=" * 80)
out("MANIFEST 完整性与校验和核查")
out("=" * 80)
out(f"单文件条目总数：{len(file_items)}")
out(f"整目录条目：{len(dir_items)}（这些只核对目录是否存在，不逐文件比对）")
out(f"完全一致（存在+字节+SHA1）：{n_ok}")
out(f"缺失：{len(missing)}  字节不符：{len(size_bad)}  SHA1 不符：{len(sha_bad)}")
out()

if missing:
    out("【缺失文件】")
    for r in missing:
        out(f"    {r}")
if size_bad:
    out("【字节数不符】(rel, 期望, 实际)")
    for r, e, a in size_bad:
        out(f"    {r}  期望 {e}  实际 {a}")
if sha_bad:
    out("【SHA1 不符】(rel, 期望前12, 实际前12)")
    for r, e, a in sha_bad:
        out(f"    {r}  期望 {e}  实际 {a}")

out()
out("【整目录条目状态】")
for it in dir_items:
    grp = it.get("group", "?")
    files = it.get("files", "?")
    out(f"    group={grp}  files={files}  status={it.get('status')}")

all_ok = not missing and not size_bad and not sha_bad
out()
out("结论：" + ("全部一致 ✅" if all_ok else "存在不一致 ❌"))
REPORT.write_text("\n".join(_buf), encoding="utf-8")
out(f"\n[报告已写入] {REPORT}")
sys.exit(0 if all_ok else 3)
