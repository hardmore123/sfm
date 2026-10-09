"""任务02 助手：作废公式残留扫描（有效文档口径）。

复用 02_代码/scan_obsolete_formulas.py 的 PATTERNS 与 MARKERS（逐字复制，见下方注释），
但排除三类目录后统计"有效文档内未标注残留"：
  - minimax任务分发/  （本分发目录，任务文件里含作废模式作为示例，属噪声）
  - 06_作废归档/       （作废归档，残留是预期的）
  - sfm_synthetic_pillars/（开发副本，历史文件）
  - _junk

自写 UTF-8 报告，绕开 PowerShell 编码问题（供 minimax 直接运行）。
退出码：有效文档内未标注残留 == 0 => 0；否则 => 6。

> 注：PATTERNS/MARKERS 与 scan_obsolete_formulas.py 保持一致；若后者更新，请同步本文件。
"""
import io
import re
import sys
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOTS = [Path("F:/sfm/大论文思想路线"), Path("F:/sfm/论文代码与数据"),
         Path("F:/sfm/sfm_synthetic_pillars")]

# 排除目录（相对片段命中即排除）
EXCLUDE = ("minimax任务分发", "06_作废归档", "sfm_synthetic_pillars", "_junk",
           "scene_set_v2", "scene_set_main", "innov2_ablations")

# —— 以下 PATTERNS / MARKERS 逐字复制自 02_代码/scan_obsolete_formulas.py ——
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
           "不得写", "不可用于论文", "正确但极松", "仅作对照", "无物理意义",
           "逻辑不成立", "不成立", "低估", "误判", "~~", "应写", "改用",
           "定位错误", "恒等式", "无效", "该表述", "原写")


def excluded(p: Path) -> bool:
    s = str(p)
    return any(e in s for e in EXCLUDE)


unmarked = []
marked_ct = 0
total = 0
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
            for pid, pat, desc in PATTERNS:
                if re.search(pat, ln):
                    total += 1
                    ctx = "\n".join(lines[max(0, i - 6):i + 7])
                    if any(m in ctx for m in MARKERS):
                        marked_ct += 1
                    else:
                        rel = str(p).replace("F:\\sfm\\", "")
                        unmarked.append((pid, rel, i + 1, ln.strip()[:100]))

buf = []


def out(s=""):
    print(s)
    buf.append(s)


out("=" * 88)
out("任务02 · 作废公式残留扫描（有效文档口径，已排除分发目录/作废归档/开发副本）")
out("=" * 88)
out(f"命中总数：{total}   已标注：{marked_ct}   有效文档内未标注残留：{len(unmarked)}")
out("")
if unmarked:
    out("【有效文档内未标注残留 —— 需处理】")
    for pid, rel, ln, text in unmarked:
        out(f"    [{pid}] {rel}:{ln}")
        out(f"          {text}")
else:
    out("✅ 有效文档内无未标注残留")

report = Path(__file__).resolve().parent.parent / "回报" / "日志" / "check_obsolete.log"
report.parent.mkdir(parents=True, exist_ok=True)
report.write_text("\n".join(buf), encoding="utf-8")
out(f"\n[报告已写入] {report}")
sys.exit(0 if not unmarked else 6)
