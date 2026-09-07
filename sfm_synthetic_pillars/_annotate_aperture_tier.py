"""
R-SCN 标注：给 S1-S6 meta.json 加 aperture_tier=sensitivity_17deg
==============================================================

阶段表 R-SCN 中间步骤（不重跑数据）：
- 现有 S1-S5 实际生成于 fov_elev ±17° / 256 波束 / σ_ρ=0.05m
- 标 aperture_tier="sensitivity_17deg"
- 留 S6 同步（包线外负例）

输出：每个场景的 meta.json 加字段
  - aperture_tier: "sensitivity_17deg"
  - aperture_elev_deg: 17
  - aperture_note: "..."

用法：python _annotate_aperture_tier.py
"""
import os
import json
import sys
from pathlib import Path

SCENE_ROOT = Path("F:/sfm/sfm_synthetic_pillars/scene_set_v2")
APERTURE_NOTE = (
    "敏感性档 ±17° / 256 波束 / σ_ρ=5cm. "
    "主档（ARIS ±7.5° / 128 波束 / σ_ρ=1cm）需重跑"
)


def annotate_one(scene_dir: Path) -> bool:
    meta_path = scene_dir / "meta.json"
    if not meta_path.exists():
        print(f"  [SKIP] {scene_dir.name}: meta.json 不存在")
        return False
    with open(meta_path, encoding="utf-8") as f:
        meta = json.load(f)
    # 已标注则跳过
    if meta.get("aperture_tier"):
        print(f"  [SKIP] {scene_dir.name}: 已有 aperture_tier={meta['aperture_tier']}")
        return True
    # 推断 tier：默认 sensitivity_17deg（这些场景是历史 17° 生成的）
    meta["aperture_tier"] = "sensitivity_17deg"
    meta["aperture_elev_deg"] = 17.0
    meta["aperture_note"] = APERTURE_NOTE
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)
    print(f"  [OK]   {scene_dir.name}: 已标 aperture_tier=sensitivity_17deg")
    return True


def main():
    if not SCENE_ROOT.exists():
        print(f"[ERR] {SCENE_ROOT} 不存在")
        sys.exit(1)
    print(f"=== R-SCN 标注：{SCENE_ROOT} ===\n")
    n_ok = 0
    n_skip = 0
    for d in sorted(SCENE_ROOT.iterdir()):
        if not d.is_dir():
            continue
        if annotate_one(d):
            n_ok += 1
        else:
            n_skip += 1
    print(f"\n=== 完成：{n_ok} 场景已标，{n_skip} 跳过 ===")


if __name__ == "__main__":
    main()
