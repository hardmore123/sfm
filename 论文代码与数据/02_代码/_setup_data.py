"""建立脚本期望的数据布局（在 `02_代码/` 下运行一次即可）。

为什么需要这一步
----------------
交付副本的代码与原始工作区**逐字节相同**（不改任何一行），以保证它们仍是
"已通过验收的那一版"。代价是脚本里的相对路径仍指向原布局。本脚本用
目录联接（junction，不复制数据）把期望路径补齐。

会建立：
  scene_set_main_f8   -> ../04_数据/scene_set_main_f8      （交付内，唯一有效场景集）
  _f8_sceneset_design.json                                  （从 05_结果 复制，小文件）
  scene_set_v2        -> 原始工作区（若存在，仅供审计追溯，数据已作废）
  scene_set_main      -> 原始工作区（同上）

移动过交付目录后重跑本脚本即可修复联接。
"""
import io
import sys
import os
import shutil
import subprocess
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent          # 02_代码/
DELIV = HERE.parent                              # 论文代码与数据/
ORIG = Path("F:/sfm/sfm_synthetic_pillars")     # 原始工作区（作废数据仍在此）


def make_junction(link: Path, target: Path) -> str:
    if not target.exists():
        return "目标不存在，跳过"
    if link.exists() or link.is_symlink():
        try:
            if link.is_dir() and not link.is_symlink():
                # 已存在的真实目录：只在是空目录时移除
                if not any(link.iterdir()):
                    link.rmdir()
                else:
                    return "已存在同名非空目录，跳过"
            else:
                link.unlink()
        except OSError as e:
            return f"无法移除旧联接: {e}"
    r = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)],
                       capture_output=True, text=True)
    return "已建立" if r.returncode == 0 else f"失败: {r.stderr.strip()[:60]}"


def main():
    print("=" * 72)
    print("建立数据布局（junction，不复制）")
    print("=" * 72)

    jobs = [
        ("scene_set_main_f8", DELIV / "04_数据" / "scene_set_main_f8", "有效"),
        ("scene_set_v2", ORIG / "scene_set_v2", "作废·仅追溯"),
        ("scene_set_main", ORIG / "scene_set_main", "作废·仅追溯"),
        ("innov2_ablations", ORIG / "innov2_ablations", "作废·仅追溯"),
    ]
    for name, target, tag in jobs:
        st = make_junction(HERE / name, target)
        print(f"  {name:<20} [{tag:<10}] {st}")
        print(f"      -> {target}")

    # 设计 JSON：设计脚本会在 cwd 生成，这里先从 05_结果 补一份
    src = DELIV / "05_结果" / "F8主档" / "场景集设计_f8_sceneset_design.json"
    dst = HERE / "_f8_sceneset_design.json"
    if src.exists() and not dst.exists():
        shutil.copy2(src, dst)
        print(f"  _f8_sceneset_design.json  已从 05_结果 复制")
    elif dst.exists():
        print(f"  _f8_sceneset_design.json  已存在")

    print("\n完成。现在可在本目录直接运行各 verify_*.py。")
    print("注：f8_probe_shadow_visibility.py 需要作废场景集的 .npy（GB 级，未复制），")
    print("    其取证结论已固化在 01_理论支撑/审计链/Q1-Q6_*.md。")


if __name__ == "__main__":
    main()
