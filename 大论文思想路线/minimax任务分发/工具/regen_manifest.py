"""重新生成 论文代码与数据/MANIFEST.json，使其与当前实际交付布局一致。

规则：
  - 遍历 论文代码与数据/ 下所有真实文件，逐个记 group/rel/bytes/sha1(前12)/status。
  - 跳过：02_代码 下指向作废数据的联接（scene_set_*、innov2_ablations）、任何 __pycache__、
          MANIFEST.json 自身。
  - 04_数据/scene_set_main_f8 作为一条“整目录”聚合项（files + bytes），不逐文件展开
    （其完整性由 check_data_structure.py 单独核查）。
自写 UTF-8。生成前会把旧 MANIFEST 备份为 MANIFEST.json.bak。
"""
import hashlib
import io
import json
import sys
from datetime import datetime
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BASE = Path("F:/sfm/论文代码与数据")
DATA_AGG = "04_数据/scene_set_main_f8"          # 作为聚合项
SKIP_SEGMENTS = ("__pycache__",)
# 02_代码 下这些是指向作废数据的目录联接，不纳入
JUNCTION_NAMES = ("scene_set_v2", "scene_set_main", "innov2_ablations",
                  "scene_set_main_f8")


def is_skipped(p: Path) -> bool:
    parts = p.relative_to(BASE).parts
    if any(seg in parts for seg in SKIP_SEGMENTS):
        return True
    # 跳过 02_代码 下的联接目录内容
    if len(parts) >= 2 and parts[0] == "02_代码" and parts[1] in JUNCTION_NAMES:
        return True
    # 04_数据/scene_set_main_f8 的逐文件不在这里收（聚合另算）
    rel = p.relative_to(BASE).as_posix()
    if rel.startswith(DATA_AGG + "/"):
        return True
    if p.name == "MANIFEST.json":
        return True
    if p.name == "MANIFEST.json.bak":
        return True
    return False


items = []
for p in sorted(BASE.rglob("*")):
    if not p.is_file():
        continue
    if is_skipped(p):
        continue
    rel = p.relative_to(BASE).as_posix()
    group = rel.split("/")[0]
    data = p.read_bytes()
    items.append({
        "group": group,
        "rel": rel,
        "bytes": len(data),
        "sha1": hashlib.sha1(data).hexdigest()[:12],
        "status": "有效",
    })

# 04_数据/scene_set_main_f8 聚合项
data_dir = BASE / DATA_AGG
agg_files = [q for q in data_dir.rglob("*") if q.is_file()]
agg_bytes = sum(q.stat().st_size for q in agg_files)
items.append({
    "group": "04_数据",
    "rel": DATA_AGG,
    "files": len(agg_files),
    "bytes": agg_bytes,
    "status": "已复制（整目录）",
    "note": "逐文件完整性由 check_data_structure.py 核查",
})

manifest = {
    "generated_by": "minimax任务分发/工具/regen_manifest.py",
    "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "note": "按当前实际交付布局（02_代码 扁平）重建；旧版按早期嵌套布局生成，已备份为 MANIFEST.json.bak",
    "items": items,
}

# 备份旧的
old = BASE / "MANIFEST.json"
if old.exists():
    (BASE / "MANIFEST.json.bak").write_bytes(old.read_bytes())

old.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

n_file = sum(1 for it in items if "rel" in it and "sha1" in it)
print(f"重建完成：单文件条目 {n_file}，聚合目录 1（{len(agg_files)} 文件 / {agg_bytes} 字节）")
print(f"写入 {old}")
print("旧版已备份为 MANIFEST.json.bak")
