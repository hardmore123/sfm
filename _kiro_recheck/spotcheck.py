"""抽查任务01 各日志里的"关键期望值"是否真实出现（核对 minimax 的判定是否读对日志）。"""
import io
import re
import sys
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

LOG = Path("F:/sfm/大论文思想路线/minimax任务分发/回报/日志")

# (日志, 说明, 正则)
CHECKS = [
    ("verify_f2_blind_semantics.py.log", "τ_z^crit ≈ 4.18 cm", r"4\.18"),
    ("verify_f2_blind_semantics.py.log", "两轨迹 std 差约14倍(0.35/4.85)", r"0\.35|4\.85"),
    ("verify_f8_fixed.py.log", "T3 h误差 ≈0.121 cm", r"0\.12\d"),
    ("verify_f8_fixed.py.log", "总判定 通过", r"总判定.*通过"),
    ("verify_f8d_sceneset.py.log", "W6 抽检480组", r"480"),
    ("f8_probe_identity.py.log", "恒等式取证 ~1e-15", r"1\.7\d?e-15|e-15"),
    ("verify_observability_theory.py.log", "CRLB 与实测吻合", r"吻合|ratio|比值|6\.\d%"),
    ("verify_r1_tau_crit_bound.py.log", "R1 双界通过", r"通过|PASS|✅"),
]

print("=" * 88)
print("任务01 关键期望值抽查")
print("=" * 88)
allok = True
for logname, desc, pat in CHECKS:
    p = LOG / logname
    if not p.exists():
        print(f"❌ {logname} 不存在")
        allok = False
        continue
    txt = p.read_text(encoding="utf-8", errors="replace")
    m = re.search(pat, txt)
    hit = bool(m)
    allok = allok and hit
    sample = ""
    if hit:
        # 取命中所在行
        for ln in txt.splitlines():
            if re.search(pat, ln):
                sample = ln.strip()[:78]
                break
    print(f"{'✅' if hit else '❌'} {desc:34} | {sample}")

print("-" * 88)
print("抽查结论：" + ("关键数字全部真实存在 ✅" if allok else "有缺失 ❌"))
