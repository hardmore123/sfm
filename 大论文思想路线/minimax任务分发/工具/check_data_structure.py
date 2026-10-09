"""任务05 助手：交付数据体量与结构核查（只读，零副作用）。

统计 04_数据/scene_set_main_f8 的文件数、总字节、场景结构，与已知基线比对。
自写 UTF-8 报告。退出码：全部一致 => 0；否则 => 8。
"""
import io
import sys
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

DATA = Path("F:/sfm/论文代码与数据/04_数据/scene_set_main_f8")

EXP_FILES = 61
# 2026-09-09：meta.json 新增 T7/σ_θ 字段（.npy 逐字节不变），总字节 491768159 → 491776812
EXP_BYTES = 491776812
EXP_SCENES = ["M1_well_constrained", "M2_blind_low_spread", "M3_envelope_inside",
              "M4_envelope_outside", "M5_low_snr"]
EXP_SUBDIRS = {"gt", "innov2", "obs"}
EXP_PER_SCENE_FILES = 12

buf = []


def out(s=""):
    print(s)
    buf.append(s)


all_files = [p for p in DATA.rglob("*") if p.is_file()]
n_files = len(all_files)
n_bytes = sum(p.stat().st_size for p in all_files)

out("=" * 80)
out("任务05 · 交付数据体量与结构核查（只读）")
out("=" * 80)
out(f"文件总数：{n_files}（期望 {EXP_FILES}）  ->  {'✅' if n_files == EXP_FILES else '❌'}")
out(f"总字节数：{n_bytes}（期望 {EXP_BYTES}）  ->  {'✅' if n_bytes == EXP_BYTES else '❌'}")
out("")

scene_dirs = sorted([d.name for d in DATA.iterdir() if d.is_dir()])
scenes_ok = scene_dirs == sorted(EXP_SCENES)
out(f"场景目录：{scene_dirs}")
out(f"  与期望一致：{'✅' if scenes_ok else '❌'}")
out("")

struct_ok = True
out("各场景结构：")
for name in EXP_SCENES:
    d = DATA / name
    if not d.is_dir():
        out(f"  {name}: ❌ 目录缺失")
        struct_ok = False
        continue
    fc = len([p for p in d.rglob("*") if p.is_file()])
    subs = {x.name for x in d.iterdir() if x.is_dir()}
    meta = (d / "meta.json").exists()
    row_ok = (fc == EXP_PER_SCENE_FILES) and (subs == EXP_SUBDIRS) and meta
    struct_ok = struct_ok and row_ok
    out(f"  {name}: files={fc} subdirs={sorted(subs)} meta={meta}  ->  {'✅' if row_ok else '❌'}")

all_ok = (n_files == EXP_FILES) and (n_bytes == EXP_BYTES) and scenes_ok and struct_ok
out("")
out("总判定：" + ("全部一致 ✅" if all_ok else "存在不一致 ❌"))

report = Path(__file__).resolve().parent.parent / "回报" / "日志" / "check_data_structure.log"
report.parent.mkdir(parents=True, exist_ok=True)
report.write_text("\n".join(buf), encoding="utf-8")
out(f"\n[报告已写入] {report}")
sys.exit(0 if all_ok else 8)
