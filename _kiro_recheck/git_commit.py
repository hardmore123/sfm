import shutil, subprocess
from pathlib import Path

ROOT = Path("F:/sfm")
log = []


def run(*a):
    r = subprocess.run(["git", "-c", "core.quotepath=false", *a], cwd=ROOT,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    log.append(f"$ git {' '.join(a)}  -> {r.returncode}\n{r.stdout}{r.stderr}")
    return r


shutil.rmtree(ROOT / "_repro_check", ignore_errors=True)
log.append(f"_repro_check removed: {not (ROOT / '_repro_check').exists()}")

m = [p for p in (ROOT / "大论文思想路线/minimax任务分发").rglob("*") if p.is_file()]
big = sorted(m, key=lambda p: p.stat().st_size, reverse=True)[:3]
log.append(f"minimax: {len(m)} files {sum(p.stat().st_size for p in m)/1e6:.2f} MB; "
           f"largest {[(p.name, p.stat().st_size // 1024) for p in big]}")

paths = [
    # 修改过的已跟踪文件
    "sfm_synthetic_pillars/feasibility.py", "sfm_synthetic_pillars/gen_scenes_main_f8.py",
    "sfm_synthetic_pillars/observability.py", "sfm_synthetic_pillars/sigma_rho_ledger.md",
    "sfm_synthetic_pillars/scene_set_main_f8",
    "大论文思想路线/会话交接_20260907.md", "大论文思想路线/创新点内容设计_定稿.md",
    "大论文思想路线/实施任务表_验收标准_阶段安排.md",
    "大论文思想路线/审计_20260906_阴影反演恒等式与孔径未裁剪.md",
    "大论文思想路线/理论修正_T1-T6.md", "大论文思想路线/理论基础_打通状态清单.md",
    "论文代码与数据/01_理论支撑", "论文代码与数据/02_代码/feasibility.py",
    "论文代码与数据/02_代码/gen_scenes_main_f8.py", "论文代码与数据/02_代码/observability.py",
    "论文代码与数据/04_数据/README.md", "论文代码与数据/05_结果/F8主档",
    "论文代码与数据/MANIFEST.json", "论文代码与数据/README.md", "论文代码与数据/会话交接_20260907.md",
    # 本轮新增
    "sfm_synthetic_pillars/rx3_ba_crlb.py", "sfm_synthetic_pillars/sigma_theta_ledger.md",
    "sfm_synthetic_pillars/verify_rx3_ba_crlb.py", "sfm_synthetic_pillars/verify_rx3_stageB.py",
    "sfm_synthetic_pillars/verify_sigma_theta_ledger.py", "sfm_synthetic_pillars/verify_t7_roll_channel.py",
    "大论文思想路线/R_X3_报告_BA侧CRLB实测_20260909.md", "大论文思想路线/minimax任务分发",
    "大论文思想路线/任务表_理论收尾与立身_20260909.md", "大论文思想路线/工作日志_20260909.md",
    "论文代码与数据/02_代码/rx3_ba_crlb.py", "论文代码与数据/02_代码/rx3_ba_crlb_report.json",
    "论文代码与数据/02_代码/rx3_stageB_report.json",
    "论文代码与数据/02_代码/sigma_theta_ledger_report.json",
    "论文代码与数据/02_代码/sigma_theta_ledger_report.txt",
    "论文代码与数据/02_代码/t7_roll_channel_report.json",
    "论文代码与数据/02_代码/t7_roll_channel_report.txt",
    "论文代码与数据/02_代码/verify_rx3_ba_crlb.py", "论文代码与数据/02_代码/verify_rx3_stageB.py",
    "论文代码与数据/02_代码/verify_sigma_theta_ledger.py",
    "论文代码与数据/02_代码/verify_t7_roll_channel.py",
]
run("add", "--", *paths)
st = run("diff", "--cached", "--name-only").stdout.splitlines()
bad = [s for s in st if s.startswith(("_kiro_recheck", "_repro_check")) or s.endswith((".bak", ".npy"))
       or "E_GROUP_PAPER_REPORT" in s]
size = sum((ROOT / s).stat().st_size for s in st if (ROOT / s).exists())
log.append(f"staged {len(st)} files, {size/1e6:.2f} MB, forbidden={bad}")
if not bad:
    run("commit", "-m",
        "theory(T7): 双通道高度精度式 + σ_θ 台账 + R-X3 BA 侧实测\n\n"
        "- 理论修正 §9 T7：σ_Pz 补横滚激活的方位通道与 cos φ̄；孔径上限收窄为斜距通道上限\n"
        "- 新增 sigma_theta_ledger.md 与 resolve_sigma_theta；observability σ_θ 默认值量纲错误已修\n"
        "- R-X3：严格 CRLB 与 MC 真跑优化吻合（位姿已知 8/8，联合 BA 3/4）\n"
        "- gen_scenes_main_f8 meta 增加 strict/dual σ_Pz 与 σ_θ 溯源；场景 .npy 逐字节不变\n"
        "- 文档：T3/T4 倒挂更正、48.57cm 近似式标注、R-X3 归因更正\n"
        "- minimax 机械核查分发包（7 项任务 + 助手脚本），回归基线 16/16\n"
        "- 任务表 v4：理论收尾与创新点立身")
    run("log", "--oneline", "-1")
(ROOT / "_kiro_recheck/git_commit.log").write_text("\n".join(log), encoding="utf-8")
