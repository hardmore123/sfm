"""只把新生成的 meta.json / INDEX.json 安装到三处，绝不触碰 .npy。"""
import shutil
from pathlib import Path

NEW = Path("F:/sfm/_repro_check/scene_set_main_f8")
DELIV = Path("F:/sfm/论文代码与数据/04_数据/scene_set_main_f8")
DEV = Path("F:/sfm/sfm_synthetic_pillars/scene_set_main_f8")
RES = Path("F:/sfm/论文代码与数据/05_结果/F8主档")

scenes = sorted(p.name for p in NEW.iterdir() if p.is_dir())
n = 0
for sc in scenes:
    src = NEW / sc / "meta.json"
    for dst in (DELIV / sc / "meta.json", DEV / sc / "meta.json", RES / "各场景meta" / f"{sc}.json"):
        if dst.parent.exists():
            shutil.copyfile(src, dst)
            n += 1
for dst in (DELIV / "INDEX.json", DEV / "INDEX.json", RES / "INDEX.json"):
    shutil.copyfile(NEW / "INDEX.json", dst)
    n += 1
print("installed", n, "files for", scenes)
