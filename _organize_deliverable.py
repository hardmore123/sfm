"""把大论文的代码、数据、理论文档整理复制到 `论文代码与数据/`。

分区原则（关键）：
  有效 = 经审计后仍成立、可在论文中引用
  作废 = 已被审计推翻，**保留以便追溯，但不得引用**
两者必须物理分开，否则等于交付一堆混杂的无效材料。
"""
import io
import sys
import os
import json
import shutil
import hashlib
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = Path("F:/sfm")
SP = ROOT / "sfm_synthetic_pillars"
TH = ROOT / "大论文思想路线"
OUT = ROOT / "论文代码与数据"

# ============================================================
# 01 理论支撑（全部有效）
# ============================================================
THEORY = [
    (TH / "理论修正_T1-T6.md", "01_理论支撑/公式权威/理论修正_T1-T6.md"),
    (SP / "sigma_rho_ledger.md", "01_理论支撑/公式权威/sigma_rho_ledger.md"),
    (TH / "审计报告_逻辑与可靠性_20260904.md", "01_理论支撑/审计链/A1-A6_审计报告_逻辑与可靠性_20260904.md"),
    (TH / "审计_P星阶段结果复核_20260904.md", "01_理论支撑/审计链/P星阶段结果复核_20260904.md"),
    (TH / "审计_20260905_文档倒挂与雕刻错误.md", "01_理论支撑/审计链/P1-P6_审计_20260905_文档倒挂与雕刻错误.md"),
    (TH / "审计_20260906_阴影反演恒等式与孔径未裁剪.md", "01_理论支撑/审计链/Q1-Q6_审计_20260906_阴影反演恒等式与孔径未裁剪.md"),
    (SP / "_CORRECTION_NOTICE.md", "01_理论支撑/审计链/_CORRECTION_NOTICE.md"),
    (TH / "创新点内容设计_定稿.md", "01_理论支撑/创新点设计/创新点内容设计_定稿.md"),
    (TH / "创新点一_问题定义与模块分解.md", "01_理论支撑/创新点设计/创新点一_问题定义与模块分解.md"),
    (TH / "创新点二_问题定义与模块分解.md", "01_理论支撑/创新点设计/创新点二_问题定义与模块分解.md"),
    (TH / "稠密化模块_点云生成内容设计.md", "01_理论支撑/创新点设计/稠密化模块_点云生成内容设计.md"),
    (TH / "文献分析与思路重构_v3.md", "01_理论支撑/文献/文献分析与思路重构_v3.md"),
    (SP / "LIT_NOTES.md", "01_理论支撑/文献/LIT_NOTES_精读笔记.md"),
    (SP / "WANTED_PAPERS.md", "01_理论支撑/文献/WANTED_PAPERS_待找文献.md"),
    (SP / "PAPER_SEARCH_PLAN.md", "01_理论支撑/文献/PAPER_SEARCH_PLAN.md"),
    (TH / "实施任务表_验收标准_阶段安排.md", "01_理论支撑/实施任务表_验收标准_阶段安排.md"),
    (SP / "real_data" / "ARIS_EXPLORER_3000_PARAMS.md", "01_理论支撑/传感器规格/ARIS_EXPLORER_3000_PARAMS.md"),
    (SP / "real_data" / "INVENTORY.md", "01_理论支撑/传感器规格/真实数据集_INVENTORY.md"),
]

# ============================================================
# 02 核心代码（有效）
# ============================================================
CODE = [
    # -- 仿真基础
    (SP / "config.py", "02_核心代码/仿真基础/config.py"),
    (SP / "world.py", "02_核心代码/仿真基础/world.py"),
    (SP / "trajectory.py", "02_核心代码/仿真基础/trajectory.py"),
    (SP / "sonar_render.py", "02_核心代码/仿真基础/sonar_render.py"),
    (SP / "sim_pipeline.py", "02_核心代码/仿真基础/sim_pipeline.py"),
    # -- 阴影渲染与高度反演（★II 主链）
    (SP / "shadow_f8_fixed.py", "02_核心代码/阴影与反演/shadow_f8_fixed.py"),
    (SP / "shadow.py", "02_核心代码/阴影与反演/shadow.py"),
    (SP / "height_inversion.py", "02_核心代码/阴影与反演/height_inversion.py"),
    # -- 判据（★I 主链）
    (SP / "feasibility.py", "02_核心代码/判据/feasibility.py"),
    (SP / "observability.py", "02_核心代码/判据/observability.py"),
    # -- 稠密化（★II-2）
    (SP / "R_x6_carve_fixed.py", "02_核心代码/稠密化/R_x6_carve_fixed.py"),
    (SP / "surface_recon.py", "02_核心代码/稠密化/surface_recon.py"),
    # -- 场景设计与生成
    (SP / "_f8_design_sceneset.py", "02_核心代码/场景生成/f8_design_sceneset.py"),
    (SP / "gen_scenes_main_f8.py", "02_核心代码/场景生成/gen_scenes_main_f8.py"),
    (SP / "scene_configs.py", "02_核心代码/场景生成/scene_configs.py"),
    (SP / "big_paper_sim.py", "02_核心代码/场景生成/big_paper_sim.py"),
]

# ============================================================
# 03 验证脚本（有效）—— 每个对应一个验收项
# ============================================================
VERIFY = [
    (SP / "verify_f8_fixed.py", "03_验证脚本/F8_阴影渲染与反演/verify_f8_fixed.py"),
    (SP / "verify_f8a_shadow_aperture.py", "03_验证脚本/F8_阴影渲染与反演/verify_f8a_shadow_aperture.py"),
    (SP / "verify_f8d_sceneset.py", "03_验证脚本/F8_阴影渲染与反演/verify_f8d_sceneset.py"),
    (SP / "_f8_probe_identity.py", "03_验证脚本/F8_阴影渲染与反演/probe_identity_恒等式取证.py"),
    (SP / "_f8_probe_shadow_visibility.py", "03_验证脚本/F8_阴影渲染与反演/probe_shadow_visibility.py"),
    (SP / "_probe_f8_sigma.py", "03_验证脚本/F8_阴影渲染与反演/probe_sigma_rho_两条链口径.py"),
    (SP / "_f8_verify_sceneset.py", "03_验证脚本/F8_阴影渲染与反演/verify_sceneset_design.py"),
    (SP / "_f8_design_geometry.py", "03_验证脚本/F8_阴影渲染与反演/design_geometry_可行域搜索.py"),
    (SP / "verify_f2_blind_semantics.py", "03_验证脚本/理论层/verify_f2_blind_semantics.py"),
    (SP / "_verify_f7.py", "03_验证脚本/理论层/verify_f7_sigma_rho台账.py"),
    (SP / "verify_observability_theory.py", "03_验证脚本/理论层/verify_observability_theory.py"),
    (SP / "verify_sigma_h_propagation.py", "03_验证脚本/理论层/verify_sigma_h_propagation.py"),
    (SP / "verify_x6_carve_logic.py", "03_验证脚本/稠密化/verify_x6_carve_logic.py"),
    (SP / "verify_x6_roll_vs_straight.py", "03_验证脚本/稠密化/verify_x6_roll_vs_straight.py"),
]

# ============================================================
# 05 结果（有效）
# ============================================================
RESULTS = [
    (SP / "_f8_sceneset_design.json", "05_结果/F8主档/场景集设计_f8_sceneset_design.json"),
    (SP / "R_X6_FIXED_REPORT.md", "05_结果/稠密化/R_X6_FIXED_REPORT.md"),
]

# ============================================================
# 06 作废归档（保留追溯，禁止引用）
# ============================================================
DEPRECATED = [
    (SP / "THEORY_FIXES_T1-T6.md", "06_作废归档/理论/THEORY_FIXES_T1-T6_已降级为实现笔记.md"),
    (SP / "P_STAR_REPORT.md", "06_作废归档/含失效数字的报告/P_STAR_REPORT_含500倍改进已作废.md"),
    (SP / "X3_CRLB_REPORT.md", "06_作废归档/含失效数字的报告/X3_CRLB_REPORT_判定不成立.md"),
    (SP / "R_X3_FINAL_REPORT.md", "06_作废归档/含失效数字的报告/R_X3_FINAL_REPORT.md"),
    (SP / "R_X3_FULL_REPORT.md", "06_作废归档/含失效数字的报告/R_X3_FULL_REPORT.md"),
    (SP / "R_X3_PROGRESS_REPORT.md", "06_作废归档/含失效数字的报告/R_X3_PROGRESS_REPORT.md"),
    (SP / "R_X5_FULL_REPORT.md", "06_作废归档/含失效数字的报告/R_X5_FULL_REPORT.md"),
    (SP / "R_X6_FULL_REPORT.md", "06_作废归档/含失效数字的报告/R_X6_FULL_REPORT_雕刻方向反了.md"),
    (SP / "R_X6_V2_FULL_REPORT.md", "06_作废归档/含失效数字的报告/R_X6_V2_FULL_REPORT_雕刻方向反了.md"),
    (SP / "R_X56C_FULL_REPORT.md", "06_作废归档/含失效数字的报告/R_X56C_FULL_REPORT.md"),
    (SP / "INNOV2_ABLATION_V4_REPORT.md", "06_作废归档/含失效数字的报告/INNOV2_ABLATION_V4_REPORT_受Q1恒等式影响.md"),
    (SP / "R_SCN_FULL_REPORT.md", "06_作废归档/含失效数字的报告/R_SCN_FULL_REPORT.md"),
    (SP / "X2B_REPORT.md", "06_作废归档/含失效数字的报告/X2B_REPORT_模型过简.md"),
    (SP / "WORK_LOG.md", "06_作废归档/工作日志/WORK_LOG.md"),
    (SP / "WORK_LOG_AND_THOUGHTS_V11.md", "06_作废归档/工作日志/WORK_LOG_AND_THOUGHTS_V11.md"),
    (SP / "WORK_LOG_AND_THOUGHTS_V12.md", "06_作废归档/工作日志/WORK_LOG_AND_THOUGHTS_V12.md"),
    (SP / "WORK_LOG_AND_THOUGHTS_V13.md", "06_作废归档/工作日志/WORK_LOG_AND_THOUGHTS_V13.md"),
    (SP / "SESSION_LOG_2026-09-04.md", "06_作废归档/工作日志/SESSION_LOG_2026-09-04.md"),
    (SP / "DATA_INVENTORY.md", "06_作废归档/早期文档/DATA_INVENTORY.md"),
    (SP / "BIG_PAPER_README.md", "06_作废归档/早期文档/BIG_PAPER_README.md"),
    (SP / "BIG_PAPER_DELIVERY.md", "06_作废归档/早期文档/BIG_PAPER_DELIVERY.md"),
    (SP / "T1_1_REPORT.md", "06_作废归档/早期文档/T1_1_REPORT.md"),
    (SP / "T1_2_HEAVE_BASELINE_REPORT.md", "06_作废归档/早期文档/T1_2_HEAVE_BASELINE_REPORT.md"),
    (SP / "T0_4_T0_6_DOC.md", "06_作废归档/早期文档/T0_4_T0_6_DOC.md"),
    (SP / "GAP_FIX_REPORT.md", "06_作废归档/早期文档/GAP_FIX_REPORT.md"),
    (SP / "FINAL_GAP_FIX_REPORT.md", "06_作废归档/早期文档/FINAL_GAP_FIX_REPORT.md"),
]


def sha1(p, blocks=1 << 20):
    h = hashlib.sha1()
    with open(p, "rb") as f:
        while True:
            b = f.read(blocks)
            if not b:
                break
            h.update(b)
    return h.hexdigest()[:12]


def copy_group(items, manifest, group):
    n_ok = n_miss = 0
    for src, rel in items:
        dst = OUT / rel
        if not src.exists():
            manifest.append({"group": group, "rel": rel, "src": str(src),
                             "status": "缺失"})
            print(f"    [缺失] {src.name}")
            n_miss += 1
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        manifest.append({"group": group, "rel": rel, "src": str(src),
                         "bytes": src.stat().st_size, "sha1": sha1(src),
                         "status": "已复制"})
        n_ok += 1
    print(f"  {group}: 复制 {n_ok} 个" + (f"，缺失 {n_miss} 个" if n_miss else ""))
    return n_ok, n_miss


def main():
    print("=" * 76)
    print("整理大论文交付材料 → 论文代码与数据/")
    print("=" * 76)
    manifest = []

    print("\n[01] 理论支撑")
    copy_group(THEORY, manifest, "01_理论支撑")
    print("\n[02] 核心代码")
    copy_group(CODE, manifest, "02_核心代码")
    print("\n[03] 验证脚本")
    copy_group(VERIFY, manifest, "03_验证脚本")
    print("\n[05] 结果")
    copy_group(RESULTS, manifest, "05_结果")
    print("\n[06] 作废归档")
    copy_group(DEPRECATED, manifest, "06_作废归档")

    # ---- 04 数据：唯一有效场景集
    print("\n[04] 数据 — scene_set_main_f8（唯一有效场景集）")
    src_ds = SP / "scene_set_main_f8"
    dst_ds = OUT / "04_数据" / "scene_set_main_f8"
    if dst_ds.exists():
        shutil.rmtree(dst_ds)
    shutil.copytree(src_ds, dst_ds)
    nf = sum(1 for _ in dst_ds.rglob("*") if _.is_file())
    sz = sum(p.stat().st_size for p in dst_ds.rglob("*") if p.is_file())
    print(f"  已复制 {nf} 个文件，{sz/1024/1024:.1f} MB")
    manifest.append({"group": "04_数据", "rel": "04_数据/scene_set_main_f8",
                     "src": str(src_ds), "files": nf, "bytes": sz,
                     "status": "已复制（整目录）"})

    # ---- 结果汇总表
    idx = src_ds / "INDEX.json"
    if idx.exists():
        shutil.copy2(idx, OUT / "05_结果" / "F8主档" / "INDEX.json")
        for d in sorted(src_ds.glob("M*")):
            mp = d / "meta.json"
            if mp.exists():
                tgt = OUT / "05_结果" / "F8主档" / "各场景meta" / f"{d.name}.json"
                tgt.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(mp, tgt)

    with open(OUT / "MANIFEST.json", "w", encoding="utf-8") as f:
        json.dump({"generated_by": "_organize_deliverable.py",
                   "items": manifest}, f, ensure_ascii=False, indent=2)

    tot = sum(p.stat().st_size for p in OUT.rglob("*") if p.is_file())
    nfile = sum(1 for p in OUT.rglob("*") if p.is_file())
    print("\n" + "=" * 76)
    print(f"完成：{nfile} 个文件，合计 {tot/1024/1024:.1f} MB")
    print(f"清单已落盘 {OUT/'MANIFEST.json'}")
    print("=" * 76)


if __name__ == "__main__":
    main()
