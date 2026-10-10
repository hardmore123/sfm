import difflib
from pathlib import Path

D = Path("F:/sfm/论文代码与数据/02_代码")
V = Path("F:/sfm/sfm_synthetic_pillars")
for n in ["feasibility.py", "observability.py", "gen_scenes_main_f8.py"]:
    a = (V / n).read_text(encoding="utf-8").splitlines()
    b = (D / n).read_text(encoding="utf-8").splitlines()
    rem = [l for l in difflib.unified_diff(a, b, lineterm="", n=0)
           if l.startswith("-") and not l.startswith("---")]
    add = [l for l in difflib.unified_diff(a, b, lineterm="", n=0)
           if l.startswith("+") and not l.startswith("+++")]
    print(f"{n}: dev 有而交付无的行 {len(rem)}，交付新增 {len(add)}")
    for l in rem[:12]:
        print("   ", l[:110])
