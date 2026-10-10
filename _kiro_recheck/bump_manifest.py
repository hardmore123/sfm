from pathlib import Path
T = Path("F:/sfm/大论文思想路线/minimax任务分发")
for f, pairs in {
    "任务04_MANIFEST完整性核查.md": [("| 111 |", "| 115 |"), ("**110**", "**114**"),
                                   ("完全一致 = 110", "完全一致 = 114"), ("| 完全一致 | 110 |", "| 完全一致 | 114 |")],
    "README_给minimax.md": [("110 一致/0 缺失/0 不符", "114 一致/0 缺失/0 不符")],
    "我方核验清单_Kiro.md": [("16/16、8、7、110/0/0", "16/16、8、7、114/0/0"), ("15/15、8、7、110/0/0", "16/16、8、7、114/0/0")],
    "回报/_总结模板.md": [("110/0/0（全部一致）", "114/0/0（全部一致）")],
}.items():
    p = T / f; t = p.read_text(encoding="utf-8"); h = 0
    for a, b in pairs:
        if a in t: t = t.replace(a, b); h += 1
    p.write_text(t, encoding="utf-8"); print(f, h)
