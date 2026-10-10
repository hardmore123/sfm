"""交付副本 → 开发副本（sfm_synthetic_pillars）同步本轮改动，保持"两处 .py 内容一致"。"""
import shutil
from pathlib import Path

D = Path("F:/sfm/论文代码与数据/02_代码")
V = Path("F:/sfm/sfm_synthetic_pillars")
L = Path("F:/sfm/论文代码与数据/01_理论支撑/公式权威")
code = ["feasibility.py", "observability.py", "gen_scenes_main_f8.py", "rx3_ba_crlb.py",
        "verify_rx3_ba_crlb.py", "verify_rx3_stageB.py", "verify_t7_roll_channel.py",
        "verify_sigma_theta_ledger.py"]
for n in code:
    shutil.copyfile(D / n, V / n)
for n in ["sigma_rho_ledger.md", "sigma_theta_ledger.md"]:
    shutil.copyfile(L / n, V / n)
shutil.copyfile(L / "理论修正_T1-T6.md", Path("F:/sfm/大论文思想路线/理论修正_T1-T6.md"))
print("synced", len(code), "code + 2 ledgers + 理论修正")
