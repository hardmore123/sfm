"""端到端冒烟测试：生成 → 复制 → V2 + V6 → 评估。"""
import os, sys, time, shutil, json
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import C
from sim_pipeline import generate
from run_ba_test import run_v2, run_v6, evaluate


def main():
    print("=== 端到端冒烟测试 ===")
    out = "./smoke_test"
    t0 = time.time()
    meta = generate(out_dir=out, cfg=C)
    t1 = time.time()
    print(f"[1/3] 数据生成: {t1-t0:.1f}s   stats={meta['stats']}")

    dst = "../BA代码/sim_input_smoke"
    if os.path.exists(dst):
        shutil.rmtree(dst)
    shutil.copytree(os.path.join(out, "input"), dst)
    print(f"[2/3] 复制 input/ 到 BA代码/sim_input_smoke")

    t0 = time.time()
    results = {}
    for algo_name, runner in [("V2", run_v2), ("V6", run_v6)]:
        if algo_name == "V2":
            m, p, l = runner(dst)
        else:
            m, p, l = runner(dst, os.path.join(out, "gt"))
        m.update(evaluate(p, l, os.path.join(out, "gt")))
        results[algo_name] = m
        pe = m["pose_trans_err_mean_m"] * 100
        le = m["lm_pos_err_mean_m"] * 100
        rms = m["final_rms"]
        tt = m["time_s"]
        print(f"  [{algo_name}] pos_err={pe:.2f}cm, lm_err={le:.2f}cm, "
              f"rms={rms:.3f}px, t={tt:.1f}s")
    t2 = time.time()
    print(f"[3/3] BA 测试: {t2-t0:.1f}s")

    with open(os.path.join(out, "smoke_report.json"), "w") as f:
        json.dump(results, f, indent=2, default=float)
    print("=== 冒烟测试通过 ===")


if __name__ == "__main__":
    main()
