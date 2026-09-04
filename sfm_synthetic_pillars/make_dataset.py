"""
批量生成多模式模拟数据集
=========================

对 4 种运动模式各生成一份数据：
  general / forward / yaw_y / mixed

每份都自动跑 V2 + V6 BA 测试，把结果汇总到 summary.json / summary.md。
"""

import os, json, time, sys
import numpy as np

# 把当前目录加入 path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import C, Config
from sim_pipeline import generate
from run_ba_test import run_all


def make_one(mode: str, out_root: str = "./multi_mode") -> dict:
    cfg = Config()
    cfg.traj.motion_mode = mode
    # 关键帧：根据模式选
    if mode == "forward":
        cfg.traj.keyframe_indices = [0, 10, 20, 30, 40, 50, 55]   # 7 关键帧
    else:
        cfg.traj.keyframe_indices = [0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55]  # 12
    out_dir = os.path.join(out_root, mode)
    print(f"\n{'='*60}\n生成模式: {mode}\n{'='*60}")
    t0 = time.time()
    meta = generate(out_dir=out_dir, cfg=cfg)
    gen_t = time.time() - t0
    # 复制 input/ 到 BA代码/sim_input_<mode>
    import shutil
    ba_input = f"../BA代码/sim_input_{mode}"
    if os.path.exists(ba_input):
        shutil.rmtree(ba_input)
    shutil.copytree(os.path.join(out_dir, "input"), ba_input)
    # 跑 BA
    t0 = time.time()
    results, poses, lands = run_all(ba_input, os.path.join(out_dir, "gt"), algos=("V2", "V6"))
    ba_t = time.time() - t0
    return {
        "mode": mode,
        "gen_time_s": gen_t,
        "ba_time_s": ba_t,
        "meta": meta["stats"],
        "results": results,
    }


def main():
    out_root = "./multi_mode"
    os.makedirs(out_root, exist_ok=True)
    modes = ["general", "forward", "yaw_y", "mixed"]
    summary = []
    for mode in modes:
        try:
            s = make_one(mode, out_root)
            summary.append(s)
        except Exception as e:
            print(f"[ERR] mode={mode} failed: {e}")
            summary.append({"mode": mode, "error": str(e)})
    # 写 summary.json
    with open(os.path.join(out_root, "summary.json"), "w") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False, default=str)
    # 打印表格
    print("\n" + "=" * 100)
    print(f"{'Mode':<10} | {'#Obs':<6} | {'#KF':<4} | {'#LM':<5} | "
          f"{'V2 pos err':<14} | {'V2 lm err':<14} | {'V6 pos err':<14} | {'V6 lm err':<14}")
    print("-" * 100)
    for s in summary:
        if "error" in s:
            print(f"{s['mode']:<10} | ERROR: {s['error']}")
            continue
        v2 = s["results"].get("V2", {})
        v6 = s["results"].get("V6", {})
        v2_pe = f"{v2.get('pose_trans_err_mean_m', 0)*100:.2f}cm"
        v2_le = f"{v2.get('lm_pos_err_mean_m', 0)*100:.2f}cm"
        v6_pe = f"{v6.get('pose_trans_err_mean_m', 0)*100:.2f}cm"
        v6_le = f"{v6.get('lm_pos_err_mean_m', 0)*100:.2f}cm"
        n_obs = s["meta"].get("n_observations", 0)
        n_kf = s["meta"].get("n_obs_on_keyframes", 0)
        n_lm = s["meta"].get("n_landmarks", 0)
        print(f"{s['mode']:<10} | {n_obs:<6} | {n_kf:<4} | {n_lm:<5} | {v2_pe:<14} | {v2_le:<14} | {v6_pe:<14} | {v6_le:<14}")
    print("=" * 100)
    print(f"详细报告: {out_root}/summary.json")


if __name__ == "__main__":
    main()
