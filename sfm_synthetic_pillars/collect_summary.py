"""汇总所有场景 meta.json 到一个 summary.json。"""
import os, json, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

out_root = "./big_paper_scene_set"
from scene_configs import SCENES
SCENE_DICT = {s[0]: s for s in SCENES}

summary = []
for d in sorted(os.listdir(out_root)):
    p = os.path.join(out_root, d)
    if not os.path.isdir(p):
        continue
    meta_path = os.path.join(p, "meta.json")
    if not os.path.exists(meta_path):
        continue
    try:
        with open(meta_path) as f:
            meta = json.load(f)
    except Exception:
        continue
    cfg_meta = meta.get("cfg") or meta.get("meta", {}).get("cfg", {})
    cfg = SCENE_DICT.get(d, (d, d, "", None, ""))[1:5]
    title = SCENE_DICT.get(d, (d,))[0] if len(cfg) >= 1 else d
    summary.append({
        "name": d,
        "title": SCENE_DICT.get(d, (d, d, "", None))[1],
        "category": SCENE_DICT.get(d, (d,)*5)[4],
        "stats": meta.get("stats", {}),
        "innov1": meta.get("innovation1_stats", {}),
        "innov2": meta.get("innovation2_stats", {}),
    })

with open(os.path.join(out_root, "summary.json"), "w") as f:
    json.dump(summary, f, indent=2, ensure_ascii=False, default=str)
print(f"已汇总 {len(summary)} 个场景到 {out_root}/summary.json")
