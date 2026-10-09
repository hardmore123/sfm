"""任务01 驱动：逐个 subprocess 运行全部 verify/probe 脚本，捕获退出码与输出，
自写 UTF-8 的每脚本日志与一张汇总表，绕开 PowerShell 编码问题（供 minimax 直接运行）。

判定口径（机械、客观）：
  hard_fail  = 退出码 != 0，或输出含 "Traceback" / "AssertionError"
  soft_flag  = 输出含 "FAIL"/"未通过"/"失败"（但退出码 0）——供人工判是否为说明文字
每脚本"通过"当且仅当 not hard_fail。
"""
import io
import subprocess
import sys
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

CODE = Path("F:/sfm/论文代码与数据/02_代码")
OUT = Path(__file__).resolve().parent.parent / "回报" / "日志"
OUT.mkdir(parents=True, exist_ok=True)

SCRIPTS = [
    "verify_f2_blind_semantics.py",
    "verify_f7_sigma_rho_ledger.py",
    "verify_observability_theory.py",
    "verify_sigma_h_propagation.py",
    "verify_f8a_shadow_aperture.py",
    "verify_f8_fixed.py",
    "verify_f8_sceneset_design.py",
    "verify_f8d_sceneset.py",
    "verify_x6_carve_logic.py",
    "verify_x6_roll_vs_straight.py",
    "verify_r1_tau_crit_bound.py",
    "f8_probe_identity.py",
    "f8_probe_sigma_rho.py",
    "f8_design_geometry.py",
    "verify_t7_roll_channel.py",      # T7 双通道高度精度式（2026-09-09 新增）
    "verify_sigma_theta_ledger.py",   # σ_θ 台账敏感性（2026-09-09 新增）
]

HARD = ("Traceback", "AssertionError")
SOFT = ("FAIL", "未通过", "失败")

rows = []
for s in SCRIPTS:
    path = CODE / s
    if not path.exists():
        rows.append((s, "缺文件", "-", "-", "脚本不存在"))
        continue
    try:
        r = subprocess.run([sys.executable, str(path)], cwd=str(CODE),
                           capture_output=True, timeout=1200)
        out = r.stdout.decode("utf-8", errors="replace") + \
            "\n---STDERR---\n" + r.stderr.decode("utf-8", errors="replace")
        code = r.returncode
    except subprocess.TimeoutExpired:
        out = "(超时 1200s)"
        code = -999
    (OUT / f"{s}.log").write_text(out, encoding="utf-8")
    hard = code != 0 or any(m in out for m in HARD)
    soft = any(m in out for m in SOFT)
    verdict = "未通过" if hard else "通过"
    note = "含 FAIL/失败字样(需人工判)" if (soft and not hard) else ""
    rows.append((s, verdict, str(code), "有" if soft else "无", note))

buf = []


def out(s=""):
    print(s)
    buf.append(s)


out("=" * 90)
out("任务01 · 验证脚本全量回归 —— 汇总")
out("=" * 90)
out(f"{'脚本':42} {'判定':6} {'退出码':6} {'软标记':6} 备注")
out("-" * 90)
n_pass = 0
for s, v, c, soft, note in rows:
    if v == "通过":
        n_pass += 1
    out(f"{s:42} {v:6} {c:>6} {soft:>6} {note}")
out("-" * 90)
out(f"通过 {n_pass} / {len(rows)}")
out("")
out("说明：每脚本原始输出见同目录 <脚本名>.log。")
out("'软标记=有' 表示输出里出现 FAIL/失败/未通过 字样但退出码为 0，")
out("需人工确认那是说明文字还是真失败（多数是脚本在解释缺陷）。")

report = OUT.parent / "任务01_自动汇总.md"
report.write_text("# 任务01 自动汇总\n\n```\n" + "\n".join(buf) + "\n```\n",
                  encoding="utf-8")
out(f"\n[汇总已写入] {report}")
sys.exit(0 if n_pass == len(rows) else 5)
