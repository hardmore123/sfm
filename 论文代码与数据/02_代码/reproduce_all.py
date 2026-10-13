# -*- coding: utf-8 -*-
"""
一键复现全部实验结果
====================
在新电脑上 clone 仓库后，运行此脚本即可复现全部实验数据。

使用方法:
    cd 论文代码与数据\02_代码
    python reproduce_all.py            # 全部步骤
    python reproduce_all.py --skip-gen # 跳过场景生成（已有数据时）
    python reproduce_all.py --only s6  # 只跑S6敏感性分析

环境要求:
    Python 3.11+
    numpy (pip install numpy)
    scipy (pip install scipy)    # 仅R_x6雕刻和BA需要

输出:
    04_数据/scene_set_main_f8/     ← 生成的场景数据
    02_代码/*_report.json/.txt     ← 各实验报告
"""
import os, sys, io, subprocess, time, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HERE = os.path.dirname(os.path.abspath(__file__))
DELIV = os.path.dirname(HERE)
REPO_ROOT = os.path.dirname(DELIV)

def run_script(name, script_path, desc, required=True, needs_data=True):
    """运行一个验证脚本，返回(成功?, 耗时)"""
    print(f"\n{'='*60}")
    print(f"[{name}] {desc}")
    print(f"  脚本: {script_path}")
    print(f"{'='*60}")
    
    if needs_data:
        scene_dir = os.path.join(DELIV, "04_数据", "scene_set_main_f8")
        if not os.path.isdir(scene_dir):
            print(f"  [SKIP] 场景数据不存在: {scene_dir}")
            print(f"  请先运行: python gen_scenes_main_f8.py")
            return False, 0
    
    if not os.path.isfile(script_path):
        print(f"  [SKIP] 脚本不存在: {script_path}")
        return False, 0
    
    t0 = time.time()
    try:
        result = subprocess.run(
            [sys.executable, script_path],
            cwd=HERE,
            capture_output=True,
            text=True,
            timeout=600,  # 10分钟超时
            encoding='utf-8',
            errors='replace'
        )
        elapsed = time.time() - t0
        
        # 打印输出（最后30行）
        output_lines = result.stdout.strip().split('\n') if result.stdout else []
        if len(output_lines) > 40:
            print(f"  ... (前{len(output_lines)-30}行省略) ...")
            for line in output_lines[-30:]:
                print(f"  {line}")
        else:
            for line in output_lines:
                print(f"  {line}")
        
        if result.returncode != 0:
            print(f"  [FAIL] 退出码={result.returncode}, 耗时={elapsed:.1f}s")
            if result.stderr:
                for line in result.stderr.strip().split('\n')[-5:]:
                    print(f"    STDERR: {line}")
            return False, elapsed
        
        print(f"  [OK] 耗时={elapsed:.1f}s")
        return True, elapsed
        
    except subprocess.TimeoutExpired:
        elapsed = time.time() - t0
        print(f"  [TIMEOUT] 超过600s, 耗时={elapsed:.1f}s")
        return False, elapsed
    except Exception as e:
        elapsed = time.time() - t0
        print(f"  [ERROR] {e}, 耗时={elapsed:.1f}s")
        return False, elapsed

def main():
    print("=" * 60)
    print("大论文实验数据一键复现")
    print("=" * 60)
    print(f"  仓库根目录: {REPO_ROOT}")
    print(f"  代码目录:   {HERE}")
    print(f"  交付目录:   {DELIV}")
    print(f"  Python:     {sys.executable}")
    
    args = sys.argv[1:]
    skip_gen = "--skip-gen" in args
    only = None
    if "--only" in args:
        idx = args.index("--only")
        if idx + 1 < len(args):
            only = args[idx + 1]
    
    results = []
    
    # ===== 步骤0: 生成场景数据（如果需要）=====
    scene_dir = os.path.join(DELIV, "04_数据", "scene_set_main_f8")
    has_data = os.path.isdir(scene_dir) and os.path.isfile(os.path.join(scene_dir, "INDEX.json"))
    
    if not skip_gen and not has_data:
        print(f"\n[步骤0] 生成场景数据（约8分钟）")
        ok, t = run_script("GEN", os.path.join(HERE, "gen_scenes_main_f8.py"),
                          "生成F-8场景集（固定种子，确定性可复现）", needs_data=False)
        results.append(("GEN", ok, t))
        
        if ok:
            print(f"\n[步骤0b] 建立数据布局junction")
            ok2, t2 = run_script("SETUP", os.path.join(HERE, "_setup_data.py"),
                               "建立数据布局联接", needs_data=False)
            results.append(("SETUP", ok2, t2))
    elif has_data:
        print(f"\n[步骤0] 场景数据已存在，跳过生成")
        results.append(("GEN", True, 0))
    else:
        print(f"\n[步骤0] 跳过场景生成")
    
    # ===== 步骤1: 核心验证脚本 =====
    verify_scripts = [
        ("W6",   "verify_f8d_sceneset.py",        "场景集验收（W1-W6独立射线法互校）", True),
        ("T7",   "verify_t7_roll_channel.py",     "★I-1 双通道CRLB验证（三路互校）", True),
        ("R1",   "verify_r1_tau_crit_bound.py",    "★I-1 孔径精度上限验证", True),
        ("A5",   "verify_a5_cross_term.py",       "★I-1 交叉项量化（偏保守≤12%）", False),
        ("S6",   "verify_s6_sensitivity.py",      "S6 假设敏感性分析（6个假设）", False),
        ("S2",   "verify_s2_ba_audit.py",         "S2 BA代码审计（5项检查）", False),
        ("RX5",  "verify_rx5_zhou_comparison.py",  "★II-1 R-X5: 本文vs Zhou 2025对比", True),
        ("F4b",  "verify_f4b_carve_precision.py",  "★II-2 F-4b: 雕刻精度分析", True),
    ]
    
    for tag, script, desc, needs_data in verify_scripts:
        if only and only.lower() != tag.lower():
            continue
        ok, t = run_script(tag, os.path.join(HERE, script), desc, needs_data=needs_data)
        results.append((tag, ok, t))
    
    # ===== 汇总 =====
    print(f"\n{'='*60}")
    print("复现结果汇总")
    print(f"{'='*60}")
    print(f"{'步骤':<8} {'状态':<8} {'耗时':<10}")
    print("-" * 30)
    n_pass = 0
    n_fail = 0
    for tag, ok, t in results:
        status = "✅ PASS" if ok else "❌ FAIL"
        print(f"  {tag:<6} {status:<8} {t:>7.1f}s")
        if ok: n_pass += 1
        else: n_fail += 1
    
    print(f"\n  通过: {n_pass}/{n_pass+n_fail}")
    if n_fail > 0:
        print(f"  失败: {n_fail} 个步骤需要排查")
        sys.exit(1)
    else:
        print(f"\n  ✅ 全部复现成功！实验数据可在新电脑上完整重建。")

if __name__ == "__main__":
    main()
