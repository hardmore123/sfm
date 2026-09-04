"""
批量生成 4 种运动模式的大论文模拟数据
"""
import os, sys, time, json
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from big_paper_sim import generate_big_paper
from config import Config, C


def main():
    out_root = "./big_paper_sim"
    os.makedirs(out_root, exist_ok=True)
    modes = ["general", "forward", "yaw_y", "mixed"]
    summary = []
    for mode in modes:
        out_dir = os.path.join(out_root, mode)
        print(f"\n{'='*70}\n生成模式: {mode}\n{'='*70}")
        try:
            t0 = time.time()
            meta = generate_big_paper(out_dir=out_dir, motion_mode=mode, cfg=C)
            t = time.time() - t0
            meta["total_time_s"] = t
            summary.append({"mode": mode, "time_s": t, "stats": meta.get("stats", {}),
                            "innovation1": meta.get("innovation1_stats", {}),
                            "innovation2": meta.get("innovation2_stats", {})})
        except Exception as e:
            import traceback
            traceback.print_exc()
            summary.append({"mode": mode, "error": str(e)})
    with open(os.path.join(out_root, "summary.json"), "w") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False, default=str)
    print(f"\n{'='*70}\n大论文模拟数据批量生成完成\n{'='*70}")
    print(f"{'模式':<10} | {'#obs':<6} | {'#KF':<4} | {'#LM':<5} | {'反演像素':<10} | "
          f"{'良约束':<8} | {'耗时(s)':<8}")
    print("-" * 70)
    for s in summary:
        if "error" in s:
            print(f"{s['mode']:<10} | ERROR: {s['error']}")
            continue
        st = s.get("stats", {})
        i1 = s.get("innovation1", {})
        i2 = s.get("innovation2", {})
        n_inv = i2.get("n_inverted_pixels", 0)
        n_well = i1.get("n_well_constrained", 0)
        print(f"{s['mode']:<10} | {st.get('n_observations', 0):<6} | "
              f"{st.get('n_obs_keyframes', 0):<4} | {st.get('n_landmarks', 0):<5} | "
              f"{n_inv:<10} | {n_well:<8} | {s.get('time_s', 0):<8.1f}")
    print("=" * 70)


if __name__ == "__main__":
    main()
