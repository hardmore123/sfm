"""
批量跑全部 16 个场景，每场景 60 帧（加快速度）
"""
import os, sys, time, json, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "BA代码")))

import numpy as np
from config import Config, TrajCfg
from scene_configs import SCENES
from big_paper_sim import generate_big_paper


def main(out_root="./big_paper_scene_set", n_frames=60):
    os.makedirs(out_root, exist_ok=True)
    selected = SCENES
    print(f"\n将生成 {len(selected)} 个场景，每个 {n_frames} 帧 → {out_root}/\n")
    summary = []
    t_total = time.time()
    for i, (name, title, desc, factory, category) in enumerate(selected, 1):
        out_dir = os.path.join(out_root, name)
        # 已存在则跳过
        if os.path.exists(os.path.join(out_dir, "meta.json")):
            print(f"[{i:2d}/{len(selected)}] {name}: 已存在，跳过")
            try:
                with open(os.path.join(out_dir, "meta.json")) as f:
                    summary.append(json.load(f))
            except Exception:
                pass
            continue
        if os.path.exists(out_dir):
            shutil.rmtree(out_dir)
        os.makedirs(out_dir, exist_ok=True)
        print(f"\n[{i:2d}/{len(selected)}] {name} | {title}")
        try:
            cfg = factory()
            cfg.traj.n_frames = n_frames
            # 默认 keyframes: 6-8 个
            if len(cfg.traj.keyframe_indices) > n_frames // 5 + 2:
                cfg.traj.keyframe_indices = list(range(0, n_frames, max(2, n_frames // 8)))
            t0 = time.time()
            meta = generate_big_paper(out_dir=out_dir, motion_mode=cfg.traj.motion_mode, cfg=cfg)
            t = time.time() - t0
            if hasattr(cfg, "_custom_poses"):
                np.save(os.path.join(out_dir, "gt", "custom_poses.npy"), cfg._custom_poses)
            # 写 README
            st = meta.get("stats", {})
            with open(os.path.join(out_dir, "README.md"), "w", encoding="utf-8") as f:
                f.write(f"# {title}\n\n")
                f.write(f"**目录**：`{name}/`  **类别**：`{category}`\n\n")
                f.write(f"## 用途\n\n{desc}\n\n")
                f.write(f"## 数据规模\n\n")
                f.write(f"- 帧数: {st.get('n_frames', '?')}\n")
                f.write(f"- 关键帧: {st.get('n_keyframes', '?')}\n")
                f.write(f"- 目标数: {st.get('n_pillars', '?')}\n")
                f.write(f"- Landmark: {st.get('n_landmarks', '?')}\n")
                f.write(f"- 观测总数: {st.get('n_observations', '?')}\n")
                f.write(f"- 关键帧观测: {st.get('n_obs_keyframes', '?')}\n")
                f.write(f"- 目标像素: {st.get('n_target_pixels_total', '?')}\n")
                f.write(f"- 阴影像素: {st.get('n_shadow_pixels_total', '?')}\n\n")
                f.write("## 声学配置\n\n")
                f.write(f"- beam_count: {cfg.sonar.beam_count}\n")
                f.write(f"- range_bin_count: {cfg.sonar.range_bin_count}\n")
                f.write(f"- 方位视场: {cfg.sonar.fov_azimuth_deg}\n")
                f.write(f"- 仰角孔径: {cfg.sonar.fov_elevation_deg}\n")
                f.write(f"- 距离: [{cfg.sonar.range_min_m}, {cfg.sonar.range_max_m}] m\n")
                f.write(f"- 散斑 σ: {cfg.sonar.speckle_sigma}\n")
                f.write(f"- 噪声底: {cfg.sonar.noise_floor_db} dB\n\n")
                f.write("## 文件清单\n\n")
                f.write("- `input/` — 创新一输入（4 件套）\n")
                f.write("- `gt/` — ground truth（位姿/landmark/声呐图）\n")
                f.write("- `innovation1/` — 创新一后处理（可观测性+曲面）\n")
                f.write("- `innovation2/` — 创新二输出（掩码+阴影+高度反演）\n")
                f.write("- `segmentation_data/` — 语义分割训练数据\n")
                f.write("- `imu/imu_data.csv` — IMU 仿真\n")
                f.write("- `dvl/dvl_data.csv` — DVL 仿真\n")
                f.write("- `meta.json` — 完整摘要\n\n")
                f.write("## 适用实验\n\n")
                from scene_configs import _suggest_experiments
                f.write(_suggest_experiments(name, title, desc, category))
            summary.append({"name": name, "title": title, "category": category,
                            "time_s": t, "stats": st,
                            "innov1": meta.get("innovation1_stats", {}),
                            "innov2": meta.get("innovation2_stats", {})})
            print(f"  耗时 {t:.1f}s, 反演像素 {st.get('n_shadow_pixels_total', 0)}, "
                  f"BA末RMS {meta.get('innovation1_stats', {}).get('ba_final_rms_px', 0):.3f}px")
        except Exception as e:
            import traceback; traceback.print_exc()
            summary.append({"name": name, "title": title, "error": str(e)})
    # 写 summary
    with open(os.path.join(out_root, "summary.json"), "w") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False, default=str)
    # 总览
    print(f"\n{'='*80}\n所有场景完成（总耗时 {time.time()-t_total:.1f}s）\n{'='*80}")
    print(f"{'场景':<35} | {'#lm':<5} | {'#obs':<6} | {'#KF':<4} | {'良约束%':<10} | {'反演z_err':<12} | {'t(s)':<7}")
    print("-" * 90)
    for s in summary:
        if "error" in s:
            print(f"{s['name']:<35} | ERROR: {s['error'][:50]}")
            continue
        st = s.get("stats", {})
        i1 = s.get("innov1", {})
        i2 = s.get("innov2", {})
        n_lm = st.get("n_landmarks", 0)
        n_well = i1.get("n_well_constrained", 0)
        well_pct = n_well / n_lm * 100 if n_lm else 0
        z_err = i2.get("median_abs_error_m", 0) * 100
        print(f"{s['name']:<35} | {n_lm:<5} | {st.get('n_observations', 0):<6} | "
              f"{st.get('n_keyframes', 0):<4} | {well_pct:<10.1f} | {z_err:<12.2f} | {s.get('time_s', 0):<7.1f}")
    print("=" * 90)
    print(f"详细报告: {out_root}/summary.json")


if __name__ == "__main__":
    main()
