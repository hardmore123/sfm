"""
生成 02_simple_two_pillars 的 forward 模式版本（专门用于 6.1 消融）
"""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "BA代码")))

from config import Config, SceneCfg, TrajCfg
from big_paper_sim import generate_big_paper


def make_02_forward():
    """02_simple_two_pillars + forward 模式（V2 在 forward 退化下 lm z 不可观测）"""
    cfg = Config()
    cfg.seed = 102
    cfg.scene = SceneCfg(
        scene_type="pillar",
        pillars=[(-1.0, 0.5, 0.25, 1.5), (1.0, -0.5, 0.25, 1.5)],
    )
    cfg.traj.motion_mode = "forward"   # 关键：forward 模式（z 完全不可观测）
    cfg.traj.keyframe_indices = list(range(0, 60, 6))
    return cfg


def main():
    out = "./innov2_ablations/02_forward"
    if not os.path.exists(out + "/meta.json"):
        print(f"=== 生成 {out} ===")
        cfg = make_02_forward()
        t0 = time.time()
        meta = generate_big_paper(out_dir=out, motion_mode=cfg.traj.motion_mode, cfg=cfg)
        print(f"  耗时 {time.time()-t0:.1f}s, z_err={meta['innovation2_stats']['median_abs_error_m']*100:.2f}cm")
    else:
        print(f"[skip] {out} 已存在")
    print("OK")


if __name__ == "__main__":
    main()
