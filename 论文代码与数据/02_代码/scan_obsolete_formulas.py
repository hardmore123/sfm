"""扫描全部文档中已作废公式/表述的残留，并判断是否已就地标注作废。

判定规则：命中作废模式的行，若其上下 6 行内出现"作废/已废/勿用/不得引用/更正/
DEPRECATED/⚠️"等标记，视为已标注；否则计为**未标注残留**（需修）。
"""
import io
import sys
import re
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOTS = [Path("F:/sfm/大论文思想路线"), Path("F:/sfm/论文代码与数据"),
         Path("F:/sfm/sfm_synthetic_pillars")]

# (编号, 正则, 说明)
PATTERNS = [
    ("O1", r"arcsin\s*[\\{(]*\s*\\?frac?\s*\{?\\sigma_\\rho|\\arcsin\\frac\{\\sigma_\\rho\}|arcsin\(\s*\\?sigma_?\\?rho\s*/",
     "φ_blind = arcsin(σ_ρ/(√N·τ_z))  ← sin 版盲区角，已作废"),
    ("O2", r"\\sqrt\{\\sum_?\{?k?=?1?\}?\^?\{?N?\}?\s*\\sin\^2\\varphi|sqrt\{\\sum.{0,20}\\sin\^2",
     "σ_Pz ≥ σ_ρ/√(Σsin²φ_k)  ← 实为 1/Λ_zz 松界，低估 15 倍"),
    ("O3", r"\\sin\\varphi_\{\\text\{max\}\}|\\sqrt\s*N\\?,?\\sin\\varphi_\{\\max\}|\(\\sqrt N\\sin\\varphi_\{\\max\}\)|sqrt N\s*\\sin\\varphi",
     "τ_z_crit = σ_ρ/(√N·sinφ_max)  ← 应为 √3σ_ρ/(√N·φ_max)"),
    ("O4", r"2\.4\s*cm", "τ_z_crit = 2.4 cm  ← 正式值 4.2 cm"),
    ("O5", r"100%[／/]\s*48%|48%[／/]\s*24%|盲区占孔径|盲区占比",
     "盲区占孔径 100%/48%/24%  ← std 门限非角度门限，无物理意义"),
    ("O6", r"500\s*[×xX]|500[-–]600\s*[×xX]|505×|522×", "500× 改进  ← 违反 C2/C5 + 张冠李戴"),
    ("O7", r"运动幅度越大盲区越小", "旧叙事，已作废"),
    ("O8", r"与运动方式无关的不可观测", "★I-1 旧表述，逻辑不成立"),
    ("O9", r"heave\s*提到\s*1\.0|heave 提到 1\.0[–-]1\.2", "旧 heave 建议，已作废"),
    ("O10", r"方位角完全不携带|完全不携带垂直信息", "措辞违规（斜距贡献是方位 82 倍）"),
    ("O11", r"下俯角(改善|提升).{0,6}(高度)?可观测", "措辞违规（实测 0° 与 20° 的 σ_Pz 相同）"),
]

MARKERS = ("作废", "已废", "勿用", "不得引用", "不得使用", "更正", "修正为", "DEPRECATED",
           "⚠️", "❌", "已被推翻", "失效", "旧式", "原地保留", "已弃用", "禁止",
           # 以下为"文档正在说明该项错在哪"的语境标记，属正常引用而非残留
           "不得写", "不可用于论文", "正确但极松", "仅作对照", "无物理意义",
           "逻辑不成立", "不成立", "低估", "误判", "~~", "应写", "改用",
           "定位错误", "恒等式", "无效", "该表述", "原写")


def scan():
    hits = []
    for root in ROOTS:
        if not root.exists():
            continue
        for p in root.rglob("*.md"):
            if "_junk" in str(p):
                continue
            try:
                lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
            except Exception:
                continue
            for i, ln in enumerate(lines):
                for pid, pat, desc in PATTERNS:
                    if re.search(pat, ln):
                        ctx = "\n".join(lines[max(0, i - 6):i + 7])
                        marked = any(m in ctx for m in MARKERS)
                        hits.append(dict(pid=pid, desc=desc, file=p, line=i + 1,
                                         marked=marked,
                                         text=ln.strip()[:110]))
    return hits


h = scan()
print("=" * 96)
print("作废公式/表述残留扫描")
print("=" * 96)
unmarked = [x for x in h if not x["marked"]]
marked = [x for x in h if x["marked"]]
print(f"命中 {len(h)} 处：已标注作废 {len(marked)}，**未标注 {len(unmarked)}**\n")

by_pid = {}
for x in unmarked:
    by_pid.setdefault(x["pid"], []).append(x)

if not unmarked:
    print("✅ 无未标注残留")
else:
    print("需处理的未标注残留：")
    for pid, _, desc in PATTERNS:
        if pid not in by_pid:
            continue
        print(f"\n【{pid}】{desc}   共 {len(by_pid[pid])} 处")
        for x in by_pid[pid]:
            rel = str(x["file"]).replace("F:\\sfm\\", "")
            print(f"    {rel}:{x['line']}")
            print(f"        {x['text']}")

print("\n" + "=" * 96)
print("已标注作废的命中（无需处理，仅确认）")
print("=" * 96)
agg = {}
for x in marked:
    rel = str(x["file"]).replace("F:\\sfm\\", "")
    agg.setdefault((x["pid"], rel), 0)
    agg[(x["pid"], rel)] += 1
for (pid, rel), c in sorted(agg.items()):
    print(f"  {pid:<4} {rel}  ({c} 处)")
