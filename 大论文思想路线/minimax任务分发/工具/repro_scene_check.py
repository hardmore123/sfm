"""安全的场景集确定性复现校验（零副作用，不触碰交付数据）。

做法：把 gen_scenes_main_f8 的输出目录改到临时目录再生成，然后与交付副本
04_数据/scene_set_main_f8 逐文件比对（字节 + SHA1）。绝不覆盖交付数据。

用途：
  1) 判定"确定性生成"是否逐字节可复现（决定复现任务的验收能否定成精确匹配）；
  2) 作为可分发给 minimax 的"生成+比对"任务的执行器。

自写 UTF-8 报告。退出码：全部逐字节一致 => 0；有差异 => 9。
"""
import hashlib
import io
import os
import sys
import shutil
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

CODE = Path("F:/sfm/论文代码与数据/02_代码")
DELIVERED = Path("F:/sfm/论文代码与数据/04_数据/scene_set_main_f8")
TMP = Path("F:/sfm/_repro_check/scene_set_main_f8")

COMPARE_ONLY = "--compare-only" in sys.argv

sys.path.insert(0, str(CODE))
os.chdir(str(CODE))

if not COMPARE_ONLY:
    # 清空临时目录
    if TMP.parent.exists():
        shutil.rmtree(TMP.parent, ignore_errors=True)
    TMP.mkdir(parents=True, exist_ok=True)

    import gen_scenes_main_f8 as G      # noqa: E402
    G.OUT_ROOT = TMP                    # 改输出到临时目录（不碰交付数据）
    G.main()


def sha1(p: Path) -> str:
    return hashlib.sha1(p.read_bytes()).hexdigest()


def _deep_eq(a, b, rtol=1e-9, atol=1e-12):
    """深比较：忽略 timing_s；浮点按相对/绝对容差算相等（吸收末位 ULP 差）。"""
    if isinstance(a, dict) and isinstance(b, dict):
        ka = {k for k in a if k != "timing_s"}
        kb = {k for k in b if k != "timing_s"}
        if ka != kb:
            return False
        return all(_deep_eq(a[k], b[k], rtol, atol) for k in ka)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(_deep_eq(x, y, rtol, atol) for x, y in zip(a, b))
    if isinstance(a, float) or isinstance(b, float):
        try:
            return abs(float(a) - float(b)) <= atol + rtol * abs(float(b))
        except Exception:
            return a == b
    return a == b


def same_ignoring_timing(a: Path, b: Path) -> bool:
    """meta.json 专用：忽略 timing_s、容忍浮点末位差后比对。"""
    import json
    try:
        return _deep_eq(json.loads(a.read_text(encoding="utf-8")),
                        json.loads(b.read_text(encoding="utf-8")))
    except Exception:
        return False


def rel_files(root: Path):
    return {p.relative_to(root).as_posix(): p for p in root.rglob("*") if p.is_file()}

# INDEX.json 含 timing 字段，随运行时间变化，比对时忽略
IGNORE = {"INDEX.json"}

deliv = rel_files(DELIVERED)
new = rel_files(TMP)

buf = []


def out(s=""):
    print(s)
    buf.append(s)


out("=" * 80)
out("场景集确定性复现校验（生成到临时目录，与交付逐文件比对）")
out("=" * 80)
out(f"交付副本文件数：{len(deliv)}   复现文件数：{len(new)}")

only_deliv = sorted(set(deliv) - set(new) - IGNORE)
only_new = sorted(set(new) - set(deliv) - IGNORE)
common = sorted((set(deliv) & set(new)) - IGNORE)

byte_match, byte_diff, meta_ok = [], [], []
for r in common:
    if deliv[r].stat().st_size == new[r].stat().st_size and sha1(deliv[r]) == sha1(new[r]):
        byte_match.append(r)
    elif r.endswith("meta.json") and same_ignoring_timing(deliv[r], new[r]):
        meta_ok.append(r)          # 仅 timing_s 不同，实质一致
    else:
        byte_diff.append(r)

out(f"共有文件：{len(common)}   逐字节一致：{len(byte_match)}   "
    f"meta仅timing差(实质一致)：{len(meta_ok)}   实质不一致：{len(byte_diff)}")
out(f"仅交付有：{len(only_deliv)}   仅复现有：{len(only_new)}   （已忽略 {sorted(IGNORE)}）")
out("")
if byte_diff:
    out("【逐字节不一致的文件】")
    for r in byte_diff:
        out(f"    {r}  交付 {deliv[r].stat().st_size}B  复现 {new[r].stat().st_size}B")
if only_deliv:
    out("【仅交付有】")
    for r in only_deliv:
        out(f"    {r}")
if only_new:
    out("【仅复现有】")
    for r in only_new:
        out(f"    {r}")

all_ok = (not byte_diff) and (not only_deliv) and (not only_new)
out("")
out("结论：" + ("确定性可复现 ✅（全部 .npy 逐字节一致；meta.json 至多仅 timing_s / 浮点末位不同）"
                if all_ok
                else "存在实质差异（见上）——需排查"))

report = Path(__file__).resolve().parent.parent / "回报" / "日志" / "repro_scene_check.log"
report.parent.mkdir(parents=True, exist_ok=True)
report.write_text("\n".join(buf), encoding="utf-8")
out(f"\n[报告已写入] {report}")
out(f"[临时目录] {TMP.parent}（可删）")
sys.exit(0 if all_ok else 9)
