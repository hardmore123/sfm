"""核对新旧 meta：除新增字段 + timing_s 外，原有字段是否全部数值不变；并打印新增字段。"""
import json
import sys
import io
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

OLD = Path("F:/sfm/论文代码与数据/04_数据/scene_set_main_f8")
NEW = Path("F:/sfm/_repro_check/scene_set_main_f8")


def flat(d, p=""):
    o = {}
    for k, v in d.items():
        if isinstance(v, dict):
            o.update(flat(v, p + k + "."))
        else:
            o[p + k] = v
    return o


def close(a, b):
    if isinstance(a, float) or isinstance(b, float):
        try:
            return abs(float(a) - float(b)) <= 1e-12 + 1e-9 * abs(float(b))
        except Exception:
            return a == b
    return a == b


bad = 0
for sc in sorted(p.name for p in OLD.iterdir() if p.is_dir()):
    a = flat(json.loads((OLD / sc / "meta.json").read_text(encoding="utf-8")))
    b = flat(json.loads((NEW / sc / "meta.json").read_text(encoding="utf-8")))
    changed = [k for k in a if k != "timing_s" and (k not in b or not close(a[k], b[k]))]
    added = [k for k in b if k not in a]
    bad += len(changed)
    o = lambda k: b[k]
    print(f"{sc:<22} 原字段改变 {len(changed)}  新增 {len(added)}  "
          f"approx={o('observability.sigma_Pz_m')*100:.2f}  "
          f"strict={o('observability.sigma_Pz_strict_m')*100:.2f}  "
          f"dual={o('observability.sigma_Pz_dual_m')*100:.2f}  "
          f"roll={o('observability.std_roll_deg'):.2f}°  "
          f"well_strict={o('observability.is_well_constrained_strict')}")
    if changed:
        print("   改变:", changed)
print("原字段改变总数:", bad)
