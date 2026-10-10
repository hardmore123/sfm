"""Kiro 复核器：独立重跑 minimax 跑过的助手脚本，与其原始日志逐行比对（防篡改）。

用法：python recheck.py
前置：minimax 原始日志已备份到 F:/sfm/_kiro_recheck/minimax原始日志/
"""
import io
import subprocess
import sys
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

TOOLS = Path("F:/sfm/大论文思想路线/minimax任务分发/工具")
LOGDIR = Path("F:/sfm/大论文思想路线/minimax任务分发/回报/日志")
BACKUP = Path("F:/sfm/_kiro_recheck/minimax原始日志")

CHECKS = [
    ("check_obsolete.py", "check_obsolete.log", 6),
    ("check_wording.py", "check_wording.log", 7),
    ("check_manifest.py", "check_manifest.log", 0),
    ("check_data_structure.py", "check_data_structure.log", 0),
    ("check_links.py", "check_links.log", 0),
]

print("=" * 92)
print("Kiro 复核：重跑助手脚本 + 与 minimax 原始日志逐行比对")
print("=" * 92)
print(f"{'脚本':28}{'退出码':>8}{'期望':>6}  {'日志比对':<22}判定")
print("-" * 92)

all_ok = True
for script, logname, exp_code in CHECKS:
    r = subprocess.run([sys.executable, str(TOOLS / script)], cwd=str(TOOLS),
                       capture_output=True)
    code = r.returncode
    mine = (LOGDIR / logname)
    theirs = (BACKUP / logname)
    if not theirs.exists():
        cmp_txt, cmp_ok = "minimax日志缺失", False
    else:
        a = mine.read_text(encoding="utf-8", errors="replace").splitlines()
        b = theirs.read_text(encoding="utf-8", errors="replace").splitlines()
        # 忽略"[报告已写入]"这类含绝对路径的行
        a = [x for x in a if "报告已写入" not in x]
        b = [x for x in b if "报告已写入" not in x]
        cmp_ok = (a == b)
        if cmp_ok:
            cmp_txt = "完全一致"
        else:
            ndiff = sum(1 for x, y in zip(a, b) if x != y) + abs(len(a) - len(b))
            cmp_txt = f"有差异({ndiff}行)"
    code_ok = (code == exp_code)
    ok = code_ok and cmp_ok
    all_ok = all_ok and ok
    print(f"{script:28}{code:>8}{exp_code:>6}  {cmp_txt:<22}{'✅' if ok else '❌'}")

print("-" * 92)
print("复核结论：" + ("全部一致，minimax 日志可信 ✅" if all_ok else "存在不一致，需排查 ❌"))
sys.exit(0 if all_ok else 1)
