"""逐个生成场景，避免大超时。"""
import os, sys, time, shutil, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "BA代码")))

import numpy as np
from config import Config
from scene_configs import SCENES
from big_paper_sim import generate_big_paper


def gen_one(name, factory, category, n_frames=60):
    out = f"./big_paper_scene_set/{name}"
    if os.path.exists(os.path.join(out, "meta.json")):
        print(f"[skip] {name} 已存在")
        return None
    if os.path.exists(out):
        shutil.rmtree(out, ignore_errors=True)
    os.makedirs(out, exist_ok=True)
    print(f"\n=== {name} ===")
    cfg = factory()
    cfg.traj.n_frames = n_frames
    if len(cfg.traj.keyframe_indices) > n_frames // 5 + 2:
        cfg.traj.keyframe_indices = list(range(0, n_frames, max(2, n_frames // 8)))
    t0 = time.time()
    try:
        meta = generate_big_paper(out_dir=out, motion_mode=cfg.traj.motion_mode, cfg=cfg)
    except Exception as e:
        import traceback; traceback.print_exc()
        return {"name": name, "error": str(e)}
    t = time.time() - t0
    if hasattr(cfg, "_custom_poses"):
        np.save(os.path.join(out, "gt", "custom_poses.npy"), cfg._custom_poses)
    # 写 README
    st = meta.get("stats", {})
    title, desc = next(((s[1], s[2]) for s in SCENES if s[0] == name), (name, ""))
    with open(os.path.join(out, "README.md"), "w", encoding="utf-8") as f:
        f.write(f"# {title}\n\n")
        f.write(f"**目录**：`{name}/`  **类别**：`{category}`\n\n")
        f.write(f"## 用途\n\n{desc}\n\n")
        f.write("## 数据规模\n\n")
        f.write(f"- 帧数: {st.get('n_frames', '?')}\n")
        f.write(f"- 关键帧: {st.get('n_keyframes', '?')}\n")
        f.write(f"- 目标数: {st.get('n_pillars', '?')}\n")
        f.write(f"- Landmark: {st.get('n_landmarks', '?')}\n")
        f.write(f"- 观测: {st.get('n_observations', '?')}\n")
        f.write(f"- 关键帧观测: {st.get('n_obs_keyframes', '?')}\n")
        f.write(f"- 目标像素: {st.get('n_target_pixels_total', '?')}\n")
        f.write(f"- 阴影像素: {st.get('n_shadow_pixels_total', '?')}\n\n")
        f.write("## 声学配置\n\n")
        f.write(f"- beam×range: {cfg.sonar.beam_count}×{cfg.sonar.range_bin_count}\n")
        f.write(f"- 方位 FOV: {cfg.sonar.fov_azimuth_deg}\n")
        f.write(f"- 仰角孔径: {cfg.sonar.fov_elevation_deg}\n")
        f.write(f"- 距离: [{cfg.sonar.range_min_m}, {cfg.sonar.range_max_m}] m\n")
        f.write(f"- 散斑σ: {cfg.sonar.speckle_sigma}\n")
        f.write(f"- 噪声底: {cfg.sonar.noise_floor_db} dB\n\n")
        from scene_configs import _suggest_experiments
        f.write("## 适用实验\n\n")
        f.write(_suggest_experiments(name, title, desc, category))
    print(f"  {name}: t={t:.1f}s, z_err={meta.get('innovation2_stats', {}).get('median_abs_error_m', 0)*100:.2f}cm")
    return {"name": name, "title": title, "category": category, "time_s": t,
            "stats": st, "innov1": meta.get("innovation1_stats", {}),
            "innov2": meta.get("innovation2_stats", {})}


if __name__ == "__main__":
    targets = sys.argv[1:] if len(sys.argv) > 1 else None
    if targets is None:
        targets = [s[0] for s in SCENES]
    summary = []
    t0 = time.time()
    for name, title, desc, factory, category in SCENES:
        if name not in targets:
            continue
        r = gen_one(name, factory, category, n_frames=60)
        if r is not None:
            summary.append(r)
    # 合并到 summary.json
    s_path = "./big_paper_scene_set/summary.json"
    existing = []
    if os.path.exists(s_path) and os.path.getsize(s_path) > 0:
        try:
            existing = json.load(open(s_path))
        except Exception:
            existing = []
    existing_names = {e.get("name") for e in existing if "name" in e}
    for r in summary:
        if r["name"] not in existing_names:
            existing.append(r)
    with open(s_path, "w") as f:
        json.dump(existing, f, indent=2, ensure_ascii=False, default=str)
    print(f"\n=== 总耗时 {time.time()-t0:.1f}s，新增/更新 {len(summary)} 个 ===")
