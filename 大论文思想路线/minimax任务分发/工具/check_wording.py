"""任务03 助手：措辞纪律与作废数字扫描（纯子串匹配，独立于任务02 的正则路径）。

与 check_obsolete.py（正则）互为独立核查路径——本项目方法论要求"另一条独立路径复算"。
用最朴素的子串包含判断，排除分发目录/作废归档/开发副本，自写 UTF-8 报告。
退出码：有效文档内违规残留 == 0 => 0；否则 => 7。
"""
import io
import sys
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOTS = [Path("F:/sfm/大论文思想路线"), Path("F:/sfm/论文代码与数据")]
EXCLUDE = ("minimax任务分发", "06_作废归档", "sfm_synthetic_pillars", "_junk",
           "scene_set_v2", "scene_set_main", "innov2_ablations")

# (编号, 子串列表[任一命中], 说明)
PATTERNS = [
    ("W1", ["完全不携带"], "不得写'方位角完全不携带垂直信息'"),
    ("W2", ["下俯角改善", "下俯角提升"], "不得写'下俯角改善/提升可观测性'"),
    ("W3", ["与运动方式无关的不可观测"], "★I-1 旧表述，逻辑不成立"),
    ("W4", ["运动幅度越大盲区越小"], "已作废叙事"),
    ("W5", ["盲区占孔径", "盲区占比"], "std 门限非角度门限，无物理意义"),
    ("W6", ["500×", "500 ×", "改进 500", "500-600×", "505×", "522×"], "500× 改进，违反 C2/C5"),
    ("W7", ["MAE=0.00", "MAE = 0.00", "MAE＝0.00", "0.00 cm", "0.00cm"], "作废的'MAE=0.00 cm'恒等式假象"),
    ("W8", ["2.4 cm", "2.4cm"], "作废的 τ_z^crit=2.4 cm（正式值 4.2 cm）"),
]

# 合规语境标记（说明该项是错的，属正常引用）
OK_MARKERS = ("不得写", "应写", "作废", "⚠️", "❌", "~~", "旧", "更正", "无物理意义",
              "逻辑不成立", "不成立", "低估", "误判", "改用", "恒等式", "无效",
              "无关", "假象", "已废", "禁止", "不得引用", "失效", "推翻", "注释")


def excluded(p: Path) -> bool:
    return any(e in str(p) for e in EXCLUDE)


hits = []
for root in ROOTS:
    if not root.exists():
        continue
    for p in root.rglob("*.md"):
        if excluded(p):
            continue
        try:
            lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        except Exception:
            continue
        for i, ln in enumerate(lines):
            for wid, subs, desc in PATTERNS:
                if any(s in ln for s in subs):
                    ctx = "\n".join(lines[max(0, i - 6):i + 7])
                    ok = any(m in ctx for m in OK_MARKERS)
                    rel = str(p).replace("F:\\sfm\\", "")
                    hits.append((wid, ok, rel, i + 1, ln.strip()[:100]))

violations = [h for h in hits if not h[1]]
buf = []


def out(s=""):
    print(s)
    buf.append(s)


out("=" * 88)
out("任务03 · 措辞纪律与作废数字扫描（纯子串路径，已排除分发目录/作废归档/开发副本）")
out("=" * 88)
out(f"命中总数：{len(hits)}   合规语境：{len(hits) - len(violations)}   违规残留：{len(violations)}")
out("")
if violations:
    out("【有效文档内违规残留 —— 需处理】")
    for wid, ok, rel, ln, text in violations:
        out(f"    [{wid}] {rel}:{ln}")
        out(f"          {text}")
else:
    out("✅ 有效文档内无违规残留")

report = Path(__file__).resolve().parent.parent / "回报" / "日志" / "check_wording.log"
report.parent.mkdir(parents=True, exist_ok=True)
report.write_text("\n".join(buf), encoding="utf-8")
out(f"\n[报告已写入] {report}")
sys.exit(0 if not violations else 7)
