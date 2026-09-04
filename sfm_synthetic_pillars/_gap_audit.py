"""
查漏盘点 —— 列出所有未完成/不完善项
====================================
扫描项目状态，生成 gap 清单。
"""
import os
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(r"F:\sfm\sfm_synthetic_pillars")
PHASE_TABLE = Path(r"F:\sfm\大论文思想路线\实施任务表_验收标准_阶段安排.md")


def check_file_exists(rel_path):
    return (ROOT / rel_path).exists()


def get_file_size_mb(rel_path):
    p = ROOT / rel_path
    if p.exists():
        return p.stat().st_size / 1024 / 1024
    return 0.0


def check_dir_exists(rel_path):
    p = ROOT / rel_path
    if p.exists():
        files = list(p.rglob("*"))
        return f"{len(files)} files, {sum(f.stat().st_size for f in files if f.is_file()) / 1024 / 1024:.1f} MB"
    return "MISSING"


def main():
    gaps = []

    # ====================================
    # P0 收尾 3 项
    # ====================================
    # T0.5 B 验收修订 (FOV 物理限制)
    g = {
        "id": "P0-T0.5-B",
        "task": "T0.5 B 验收修订（FOV 物理限制，识别命中距离段）",
        "status": "FAIL",
        "detail": "当前海底 > 3σ 占比 = 0.8% < 80% (FOV 物理限制：在 z_s=1.5-3m 几何下 FOV ±20° 内只有 ~14° 角度范围能命中 floor)",
        "fix": "改验收条件为'在命中距离段内'（按 angle 范围过滤），或写文档说明物理限制",
        "priority": "MEDIUM",
    }
    gaps.append(g)

    # T0.10 std/mean_nn
    g = {
        "id": "P0-T0.10-std",
        "task": "T0.10 std/mean_nn 验收（已放宽到 1.0，但单柱仍 0.65-0.88）",
        "status": "PARTIAL",
        "detail": "场景 S1-S6 std/mean_nn = 0.65-0.88（柱面曲率+柱间空隙）。已放宽阈值到 1.0。但实际物理均匀性仅指物体内部 NN 距离",
        "fix": "在 verify_sample_quality 加'分面评估'选项（柱面/顶面/底面分组），使 std/mean 通过",
        "priority": "MEDIUM",
    }
    gaps.append(g)

    # T0.11 Point-to-surface 单元测试
    g = {
        "id": "P0-T0.11-pt2sf",
        "task": "T0.11 Point-to-surface 单元测试（5cm 应约 5cm）",
        "status": "FAIL",
        "detail": "P+5cm 测试：自比 = 0 PASS，但 P+5cm 点对点云应 ≈ 5cm（实际 1.91cm）。原因：P 点云不均匀分布（多在物体表面，少在 5cm 偏移处）",
        "fix": "测试时构造均匀体素点云再 +5cm 偏移，应得 ≈ 5cm。或用 N+5cm 自身对比（高斯采样 +5cm 偏移）",
        "priority": "MEDIUM",
    }
    gaps.append(g)

    # ====================================
    # P1 收尾
    # ====================================
    # T1.4 旧数据归档
    g = {
        "id": "P1-T1.4-archive",
        "task": "T1.4 旧数据归档（big_paper_sim 8.43GB + 01_v1_buggy 281.8MB）",
        "status": "PENDING",
        "detail": "big_paper_sim/ 8.43GB 未被大论文用（V4 报告已证），01_v1_buggy/ 281.8MB 是 shadow 修复前旧版",
        "fix": "用 mavis-trash 释放 8.7GB（需用户确认）",
        "priority": "LOW",
    }
    gaps.append(g)

    # 旧 16 场景重新生成
    g = {
        "id": "P1-old-16-regen",
        "task": "旧 16 场景用 shadow V5.2 重新生成",
        "status": "SKIP",
        "detail": "旧的 big_paper_scene_set/01-16 已经证明'因 D1 真值泄漏失效'（阶段表 §1.2）。新场景 scene_set_v2/S1-S6 已替代。旧 16 场景可作废",
        "fix": "在 DATA_INVENTORY.md 标注'作废'，不再 regen",
        "priority": "LOW",
    }
    gaps.append(g)

    # ====================================
    # P★ 补漏
    # ====================================
    # X2b heave 用 T1.2 数据补充
    g = {
        "id": "PSTAR-X2b-data",
        "task": "X2b heave 用 T1.2 数据补充（不用 analytical 简化）",
        "status": "PARTIAL",
        "detail": "当前 x2b_heave_optimal.py 用 analytical 模型过于简化（σ_Pz 全是 0.0019m，跟 A 无关）。实际 T1.2 数据 general heave 0.4/0.8/1.2 → 3.3%/30%/80% well-constrained",
        "fix": "读 T1.2 数据，按 heave 聚合 well-constrained 比例，画双曲线找 A_opt",
        "priority": "MEDIUM",
    }
    gaps.append(g)

    # X7 σ 校准性
    g = {
        "id": "PSTAR-X7-calibration",
        "task": "X7 σ 校准性（实际误差落在 ±σ 内比例 ∈ [60%, 75%]）",
        "status": "PARTIAL",
        "detail": "X3 已证 std/CRLB ≈ 1，但未单独算'误差落在 ±σ 区间'比例",
        "fix": "用 X3 数据算覆盖率 (CDF)，验证在 ±1σ / ±2σ 区间内比例",
        "priority": "LOW",
    }
    gaps.append(g)

    # X2 四组运动对比
    g = {
        "id": "PSTAR-X2-motion",
        "task": "X2 四组运动对比（水平 / +roll / +heave / +pitch）",
        "status": "PENDING",
        "detail": "阶段表 X2 验收：四组同'等效仰角激励'对比 σ_Pz 分布与四分类比例",
        "fix": "从场景配置生成 4 组（已有 scene_configs 框架），跑 X0 四分类对比",
        "priority": "LOW",
    }
    gaps.append(g)

    # X8 位姿贡献隔离
    g = {
        "id": "PSTAR-X8-pose",
        "task": "X8 位姿贡献隔离（同雕刻器分别用真值/BA/纯里程计位姿）",
        "status": "PENDING",
        "detail": "依赖 P2 阶段 T2.* 创新一 BA，需要先有 BA 框架",
        "fix": "留到 P2 阶段做",
        "priority": "LOW",
    }
    gaps.append(g)

    # X9 雕刻包含性覆盖率
    g = {
        "id": "PSTAR-X9-carve",
        "task": "X9 雕刻包含性覆盖率校准（GT 表面点落在 S_α 内的比例）",
        "status": "PENDING",
        "detail": "依赖 P4 阶段 T4.4 雕刻器",
        "fix": "留到 P4 阶段做",
        "priority": "LOW",
    }
    gaps.append(g)

    # ====================================
    # P2/P3 入口
    # ====================================
    g = {
        "id": "P2-innov1",
        "task": "P2 创新一·鲁棒 BA（T2.1 w 交替 + GNC + 防塌缩）",
        "status": "PENDING",
        "detail": "T2.1 验收：不塌缩 mean(w)≥0.5 + w<0.1 占比 = 注入外点率 ±5%；耗时 ≤1.5×；外点召回 ≥90% / 内点保留 ≥95%",
        "fix": "用 S1-S5 数据跑 V2/V4/V5/V6 BA 对比，画'w 分布 + 召回/保留'图",
        "priority": "HIGH",
    }
    gaps.append(g)

    g = {
        "id": "P3-innov2",
        "task": "P3 创新二·阴影反演链（T3.1 阴影量测 + T3.4 κ 门控）",
        "status": "PENDING",
        "detail": "T3.1 验收：相邻性检验剔除率 ≥90% + L_s 偏差 ≤2 range bin；T3.4 验收：低 κ 组改善 ≥20% + 高 κ 组 ±5%",
        "fix": "从阴影 mask 提取 L_s（不依赖物体几何），加 κ 门控注入 BA",
        "priority": "HIGH",
    }
    gaps.append(g)

    # ====================================
    # R 真实数据轨
    # ====================================
    g = {
        "id": "R1-segmentation",
        "task": "R1 watertank-segmentation 目标分割基线",
        "status": "PENDING",
        "detail": "1,868 张图 + 12 类掩码可用，IoU 阈值待 E 组文献定",
        "fix": "用 YOLO-seg 或 ViT+LoRA 跑 baseline，报告 mIoU",
        "priority": "MEDIUM",
    }
    gaps.append(g)

    g = {
        "id": "R2-shadow-label",
        "task": "R2 quarry-fullsize 阴影类补标（150-250 帧）",
        "status": "PENDING",
        "detail": "原 12 类无阴影类，需人工补标 150-250 帧；两人交叉复核 IoU ≥0.85 或单人隔周自检 ≥0.90",
        "fix": "用 LabelMe 补标，分批标注（每周 50 帧）",
        "priority": "LOW",
    }
    gaps.append(g)

    g = {
        "id": "R4-turntable",
        "task": "R4 turntable-cropped 复现 Aykin 结论（★I-1 真实数据佐证）",
        "status": "PENDING",
        "detail": "15 类 4,942 帧，物体整圈偏航，无 roll 构型正是 Aykin 判定低效情形",
        "fix": "用 turntable 数据跑可观测性，验证 σ_Pz 显著大于他构型",
        "priority": "MEDIUM",
    }
    gaps.append(g)

    g = {
        "id": "R5-shadow-height",
        "task": "R5 quarry-fullsize 阴影→高度定性验证",
        "status": "PENDING",
        "detail": "至少 3 个目标给出反演高度与可反演性判据自洽性检查（无 GT，定性）",
        "fix": "用 R2 标注 + T3.1 量测，给出定性反演结果",
        "priority": "LOW",
    }
    gaps.append(g)

    g = {
        "id": "R6-sim2real",
        "task": "R6 sim-to-real 落差分析",
        "status": "PENDING",
        "detail": "报出分割 IoU + 重投影 RMS 两项的仿真/真实落差数字",
        "fix": "对比 R1 + S1-S5 数据，章节化",
        "priority": "LOW",
    }
    gaps.append(g)

    # ====================================
    # 论文 / 文档
    # ====================================
    g = {
        "id": "DOC-pipeline",
        "task": "完整论文 pipeline（创新一 + 创新二 章节）",
        "status": "PENDING",
        "detail": "已有：S1-S6 数据 + X3/X4/X5/X6 立身证据。缺：完整论文段落 + 图表（Fig 6.x 消融图、Fig 7.x 创新点图）",
        "fix": "写 §3 创新一 + §4 创新二 + §5 实验 + §6 结论",
        "priority": "MEDIUM",
    }
    g = {
        "id": "DOC-crlb-correction",
        "task": "阶段表 §6.1 #17 CRLB 公式修正（论文写作要点）",
        "status": "PENDING",
        "detail": "原 σ_ρ/sin(φ) 应改为 σ_ρ·(z_s-h)²/(D_t·z_s) — X3 验证已确认",
        "fix": "在论文 §3.2 引用 + 改阶段表对应条目",
        "priority": "LOW",
    }

    # ====================================
    # 输出报告
    # ====================================
    out = {
        "n_gaps": len(gaps),
        "gaps": gaps,
        "by_priority": {
            "HIGH": [g for g in gaps if g["priority"] == "HIGH"],
            "MEDIUM": [g for g in gaps if g["priority"] == "MEDIUM"],
            "LOW": [g for g in gaps if g["priority"] == "LOW"],
        },
    }

    print(f"=== 项目查漏盘点（{len(gaps)} 项）===\n")
    for p in ["HIGH", "MEDIUM", "LOW"]:
        items = out["by_priority"][p]
        print(f"\n【{p}】（{len(items)} 项）")
        for g in items:
            print(f"  [{g['id']:<22}] {g['status']:<8} {g['task']}")
            if g['status'] != "PENDING":
                print(f"    详细: {g['detail'][:80]}")
            print(f"    修复: {g['fix'][:80]}")

    with open("./_gap_audit.json", "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(f"\n[ok] 落盘 _gap_audit.json")
    return out


if __name__ == "__main__":
    main()
