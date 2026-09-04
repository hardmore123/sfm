"""
声学 SfM 模拟数据生成流水线
============================

完成：
  1) 生成真值 6-DOF AUV 轨迹；
  2) 选关键帧；
  3) 在每帧上做物理声呐渲染；
  4) 把 ground truth pixel→lm 关联转成 BA 需要的 tracks.csv；
  5) 加入传感器级噪声（θ/ρ 噪声、漏检、误检、里程计差分）；
  6) 输出符合 BA 接口的 4 个文件 + 完整 ground truth 用于评估。

输出文件布局（默认 out_dir = ./sim_output）：
  input/poses_est.npy         (K, 4, 4)  关键帧 body→world 真值（可加噪给 BA）
  input/pose_frame_ids.npy    (K,)       关键帧在全部帧中的下标
  input/landmarks_final.npy   (M, 3)     ground truth landmark 坐标
  input/tracks.csv            每帧每条 track 的 (theta, rho, beam_idx, range_idx)
  input/sensor_calib.yaml     声学标定（与 BA 自标定接口一致）
  input/odom_rel.csv          关键帧相对位姿（可加噪）
  gt/poses_gt.npy             全部帧位姿真值
  gt/landmarks_gt.npy         与 landmarks_final.npy 相同
  gt/sonar_images.npy         (N, H, W) 全部帧原始强度图
  gt/sonar_lm_id.npy          (N, H, W) ground truth pixel→lm 关联（无噪声）
  gt/pixel_hits.npy           (N, H, W, 3) ground truth 像素对应世界交点
  imu/imu_data.csv            (t, gx, gy, gz, ax, ay, az) 模拟 IMU
  dvl/dvl_data.csv            (t, vx, vy, vz) 模拟 DVL
  meta.json                   全部参数 + 摘要统计
"""

from __future__ import annotations
import os, json, csv
import numpy as np
import yaml
from typing import Tuple, Dict, Any

from config import Config, C, finalize_pixel_mapping
from world import SceneWorld
from trajectory import make_poses, select_keyframe_indices, matrix_to_pose6, euler_to_matrix
from sonar_render import render_all_frames, _beam_grid_rad, _range_grid


# ==========================================
# 1. 关键帧声学观测 → tracks.csv
# ==========================================
def project_landmark_to_sonar(P_w: np.ndarray, T_wb: np.ndarray) -> Tuple[float, float]:
    """
    把世界点投影到声呐载体系，返回 (theta_rad, rho_m)。
    sonar convention: x_fwd, y_left, z_down
    与 ba_optimize.py 一致：theta = atan2(P_b_y, P_b_x), rho = ||P_b||
    """
    R_wb = T_wb[:3, :3]
    t_wb = T_wb[:3, 3]
    P_b = R_wb.T @ (P_w - t_wb)
    theta = float(np.arctan2(P_b[1], P_b[0]))
    rho = float(np.linalg.norm(P_b))
    return theta, rho


def extract_tracks(landmarks: np.ndarray,                   # (M, 3) ground truth
                   poses_T: np.ndarray,                     # (N, 4, 4) 真值位姿
                   world: SceneWorld,
                   cfg: Config = C,
                   rng: np.random.Generator = None) -> Tuple[list, np.ndarray]:
    """
    从 ground truth 投影生成 tracks 列表。

    策略（保证既物理合理又观测丰富）：
      1) 对每帧的每个 landmark，用声学投影公式算 (theta, rho)；
      2) 只保留落在 (FOV, range) 内的 landmark；
      3) 同一 landmark 在不同帧的 (theta, rho) → 同一个 track_id；
      4) 加 (θ, ρ) 高斯噪声 + 漏检 + 误检，模拟真实检测不确定性。

    返回：
      out_rows : list of dict（与原 tracks.csv 格式一致）
      visibility : (N, M) bool，每帧每个 landmark 是否可见
    """
    if rng is None:
        rng = np.random.default_rng(cfg.seed)

    finalize_pixel_mapping(cfg)
    sonar = cfg.sonar
    pm = sonar.pixel_map
    az_lo, az_hi = np.deg2rad(sonar.fov_azimuth_deg[0]), np.deg2rad(sonar.fov_azimuth_deg[1])
    H, W = sonar.range_bin_count, sonar.beam_count
    M = landmarks.shape[0]
    N = poses_T.shape[0]

    # (N, M) 投影 (theta, rho)
    thetas = np.zeros((N, M))
    rhos = np.zeros((N, M))
    visibility = np.zeros((N, M), dtype=bool)
    for f in range(N):
        R_wb = poses_T[f, :3, :3]
        t_wb = poses_T[f, :3, 3]
        P_b = (R_wb.T @ (landmarks - t_wb).T).T   # (M, 3)
        theta_f = np.arctan2(P_b[:, 1], P_b[:, 0])
        rho_f = np.linalg.norm(P_b, axis=1)
        # 仰角孔径过滤
        elev_f = np.arctan2(P_b[:, 2], np.hypot(P_b[:, 0], P_b[:, 1]))
        elev_lo, elev_hi = np.deg2rad(sonar.fov_elevation_deg[0]), np.deg2rad(sonar.fov_elevation_deg[1])
        az_ok = (theta_f >= az_lo) & (theta_f <= az_hi)
        rng_ok = (rho_f >= sonar.range_min_m) & (rho_f <= sonar.range_max_m)
        el_ok = (elev_f >= elev_lo) & (elev_f <= elev_hi)
        visibility[f] = az_ok & rng_ok & el_ok
        thetas[f] = theta_f
        rhos[f] = rho_f

    # 加噪声生成 tracks
    out_rows = []
    dt_ms = int(cfg.traj.dt_s * 1000)
    t0_ms = 1700000000000
    for j in range(M):
        for f in range(N):
            if not visibility[f, j]:
                continue
            if rng.random() < cfg.noise.p_miss:
                continue
            th = float(thetas[f, j] + rng.normal(0, cfg.noise.sigma_theta_rad))
            rh = float(rhos[f, j] + rng.normal(0, cfg.noise.sigma_rho_m))
            beam_idx = pm["beam"]["a"] * th + pm["beam"]["b"]
            rng_idx = pm["range"]["c"] * rh + pm["range"]["d"]
            bi = float(np.clip(np.round(beam_idx), 0, W - 1))
            ri = float(np.clip(np.round(rng_idx), 0, H - 1))
            conf = float(rng.uniform(0.6, 1.0))
            out_rows.append({
                "frame_id": f,
                "timestamp": t0_ms + f * dt_ms,
                "track_id": j,
                "theta_rad": th,
                "rho_m": rh,
                "confidence": conf,
                "beam_index": bi,
                "range_index": ri,
            })

    # 误检：在 (FOV, range) 内随机生成 (θ, ρ)
    if cfg.noise.p_false_alarm > 0:
        n_true = len(out_rows)
        n_false = int(cfg.noise.p_false_alarm * n_true)
        for k in range(n_false):
            f = int(rng.integers(0, N))
            th = float(rng.uniform(az_lo, az_hi))
            rh = float(rng.uniform(sonar.range_min_m, sonar.range_max_m))
            beam_idx = pm["beam"]["a"] * th + pm["beam"]["b"]
            rng_idx = pm["range"]["c"] * rh + pm["range"]["d"]
            bi = float(np.clip(np.round(beam_idx), 0, W - 1))
            ri = float(np.clip(np.round(rng_idx), 0, H - 1))
            out_rows.append({
                "frame_id": f,
                "timestamp": t0_ms + f * dt_ms,
                "track_id": -1,                       # 误检，无对应 landmark
                "theta_rad": th,
                "rho_m": rh,
                "confidence": float(rng.uniform(0.0, 0.4)),
                "beam_index": bi,
                "range_index": ri,
            })

    out_rows.sort(key=lambda x: (x["frame_id"], x["track_id"]))
    return out_rows, visibility


# ==========================================
# 2. 关键帧位姿 + 相对位姿
# ==========================================
def build_keyframe_poses(poses_T: np.ndarray, keyframe_idx: list,
                         add_noise: bool = True,
                         rng: np.random.Generator = None) -> Tuple[np.ndarray, list]:
    """
    从全部帧位姿中选关键帧，**给 BA 的位姿是带噪声的初值**（与真实 BA 流程一致）。
    返回 (poses_K, odom_rel_list)
      poses_K: (K, 4, 4) 噪声关键帧位姿
      odom_rel_list: list of (k, T_rel_meas 4x4)
    """
    if rng is None:
        rng = np.random.default_rng(0)
    K = len(keyframe_idx)
    poses_K = poses_T[keyframe_idx].copy()
    if add_noise:
        for i in range(K):
            # 平移加噪
            poses_K[i, :3, 3] += rng.normal(0, 0.02, 3)
            # 旋转加噪（小角度）
            dtheta = rng.normal(0, np.deg2rad(0.5), 3)
            dR = euler_to_matrix(*dtheta)
            poses_K[i, :3, :3] = poses_K[i, :3, :3] @ dR
    # 相对位姿（真值）
    odom_rel = []
    for k in range(K - 1):
        T_rel = np.linalg.inv(poses_K[k]) @ poses_K[k + 1]
        odom_rel.append((k, T_rel))
    return poses_K, odom_rel


# ==========================================
# 3. IMU / DVL 模拟
# ==========================================
def simulate_imu_dvl(poses_T: np.ndarray, cfg: Config = C,
                     rng: np.random.Generator = None) -> Tuple[np.ndarray, np.ndarray]:
    """
    简单 IMU/DVL 仿真：
      IMU：陀螺仪测角速度 (rad/s)、加速度计测比力 (m/s^2)，加入高斯噪声 + 偏置
      DVL：测载体坐标系下速度 (m/s)，加入高斯噪声 + 比例因子偏置

    返回：
      imu_data : (M, 7)  [t, gx, gy, gz, ax, ay, az]
      dvl_data : (K, 4)  [t, vx, vy, vz]
    """
    if rng is None:
        rng = np.random.default_rng(cfg.seed + 1)
    n = poses_T.shape[0]
    dt = cfg.traj.dt_s
    # IMU 采样
    imu_rate = cfg.noise.imu_rate_hz
    n_imu = int(np.ceil(n * dt * imu_rate))
    t_imu = np.linspace(0.0, n * dt, n_imu)
    # 解析位姿的导数
    vel_world = np.gradient(poses_T[:, :3, 3], dt, axis=0)   # (N, 3)
    omega_world = np.zeros((n, 3))
    for i in range(1, n):
        R_rel = poses_T[i, :3, :3] @ poses_T[i - 1, :3, :3].T
        angle = np.arccos(np.clip((np.trace(R_rel) - 1) / 2, -1, 1))
        if angle > 1e-6:
            axis = np.array([R_rel[2, 1] - R_rel[1, 2],
                             R_rel[0, 2] - R_rel[2, 0],
                             R_rel[1, 0] - R_rel[0, 1]]) / (2 * np.sin(angle))
            omega_world[i] = axis * angle / dt
    # 把世界系速度/角速度投影到载体系
    gx = np.zeros(n_imu); gy = np.zeros(n_imu); gz = np.zeros(n_imu)
    ax = np.zeros(n_imu); ay = np.zeros(n_imu); az = np.zeros(n_imu)
    for k, t in enumerate(t_imu):
        i = int(np.clip(t / dt, 0, n - 1))
        R_wb = poses_T[i, :3, :3]
        omega_b = R_wb.T @ omega_world[i]
        gx[k] = omega_b[0] + cfg.noise.imu_gyro_bias_radps + rng.normal(0, 0.002)
        gy[k] = omega_b[1] + cfg.noise.imu_gyro_bias_radps + rng.normal(0, 0.002)
        gz[k] = omega_b[2] + cfg.noise.imu_gyro_bias_radps + rng.normal(0, 0.002)
        v_b = R_wb.T @ vel_world[i]
        # 加速度计 = 旋转分量（简单近似）+ 噪声
        a_w = np.gradient(vel_world, dt, axis=0)[i] + np.array([0, 0, 9.81])  # 简化：含重力
        a_b = R_wb.T @ a_w
        ax[k] = a_b[0] + rng.normal(0, 0.05)
        ay[k] = a_b[1] + rng.normal(0, 0.05)
        az[k] = a_b[2] + rng.normal(0, 0.05)
    imu_data = np.stack([t_imu, gx, gy, gz, ax, ay, az], axis=1)

    # DVL：每帧一个速度（10Hz）
    dvl_rate = cfg.noise.dvl_rate_hz
    n_dvl = int(np.ceil(n * dt * dvl_rate))
    t_dvl = np.linspace(0.0, n * dt, n_dvl)
    vx = np.zeros(n_dvl); vy = np.zeros(n_dvl); vz = np.zeros(n_dvl)
    scale = 1.0 + cfg.noise.dvl_scale_bias
    for k, t in enumerate(t_dvl):
        i = int(np.clip(t / dt, 0, n - 1))
        R_wb = poses_T[i, :3, :3]
        v_b = R_wb.T @ vel_world[i]
        vx[k] = scale * v_b[0] + rng.normal(0, 0.02)
        vy[k] = scale * v_b[1] + rng.normal(0, 0.02)
        vz[k] = scale * v_b[2] + rng.normal(0, 0.02)
    dvl_data = np.stack([t_dvl, vx, vy, vz], axis=1)
    return imu_data, dvl_data


# ==========================================
# 4. 写文件
# ==========================================
def write_tracks_csv(path: str, rows: list) -> None:
    """写 tracks.csv，列与原项目一致（外加 sigma_theta/sigma_rho 建议列）。"""
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["frame_id", "timestamp", "track_id",
                    "theta_rad", "rho_m", "confidence",
                    "beam_index", "range_index",
                    "sigma_theta", "sigma_rho"])
        for r in rows:
            sigma_th = 0.0035   # ≈ 0.2°
            sigma_rh = 0.005
            w.writerow([
                r["frame_id"], r["timestamp"], r["track_id"],
                f"{r['theta_rad']:.6f}", f"{r['rho_m']:.6f}", f"{r['confidence']:.3f}",
                f"{r['beam_index']:.1f}", f"{r['range_index']:.1f}",
                f"{sigma_th:.6f}", f"{sigma_rh:.6f}",
            ])


def write_sensor_calib(path: str, cfg: Config = C) -> None:
    """写 sensor_calib.yaml（与上游对接清单 P0-2 字段一致）。"""
    finalize_pixel_mapping(cfg)
    sonar = cfg.sonar
    data = {
        "frames": {
            "pose_convention": "body_to_world",
            "euler_order": "Rz_Ry_Rx",
            "angle_unit": "rad",
            "length_unit": "m",
            "timestamp_unit": "ms",
            "theta_positive_dir": "left",
            "T_sensor_body": [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]],
        },
        "sonar": {
            "beam_count": int(sonar.beam_count),
            "range_bin_count": int(sonar.range_bin_count),
            "fov_azimuth_deg": [float(sonar.fov_azimuth_deg[0]), float(sonar.fov_azimuth_deg[1])],
            "elevation_aperture_deg": [float(sonar.fov_elevation_deg[0]), float(sonar.fov_elevation_deg[1])],
            "range_min_m": float(sonar.range_min_m),
            "range_max_m": float(sonar.range_max_m),
            "sound_speed_mps": float(sonar.sound_speed_mps),
            "bandwidth_hz": float(sonar.bandwidth_hz),
        },
        "pixel_mapping": {
            "beam":  {"a": float(sonar.pixel_map["beam"]["a"]), "b": float(sonar.pixel_map["beam"]["b"])},
            "range": {"c": float(sonar.pixel_map["range"]["c"]), "d": float(sonar.pixel_map["range"]["d"])},
        },
    }
    with open(path, "w") as f:
        yaml.safe_dump(data, f, sort_keys=False, allow_unicode=True)


def write_odom_csv(path: str, odom_rel: list, cfg: Config = C) -> None:
    """写 odom_rel.csv（与上游对接清单 P1-2 字段一致）。"""
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["k", "dx", "dy", "dz", "droll", "dpitch", "dyaw",
                    "sigma_x", "sigma_y", "sigma_z", "sigma_roll", "sigma_pitch", "sigma_yaw"])
        sigma_t = cfg.noise.sigma_trans_m
        sigma_r = cfg.noise.sigma_rot_rad
        for k, T in odom_rel:
            t = T[:3, 3]
            R = T[:3, :3]
            # R = Rz·Ry·Rx → euler
            sy = np.sqrt(R[2, 1] ** 2 + R[2, 2] ** 2)
            if sy > 1e-9:
                roll = np.arctan2(R[2, 1], R[2, 2])
                pitch = np.arctan2(-R[2, 0], sy)
                yaw = np.arctan2(R[1, 0], R[0, 0])
            else:
                roll = np.arctan2(-R[1, 2], R[1, 1])
                pitch = np.arctan2(-R[2, 0], sy)
                yaw = 0.0
            w.writerow([k,
                        f"{t[0]:.6f}", f"{t[1]:.6f}", f"{t[2]:.6f}",
                        f"{roll:.6f}", f"{pitch:.6f}", f"{yaw:.6f}",
                        f"{sigma_t:.4f}", f"{sigma_t:.4f}", f"{sigma_t:.4f}",
                        f"{sigma_r:.6f}", f"{sigma_r:.6f}", f"{sigma_r:.6f}"])


def write_imu_csv(path: str, imu: np.ndarray) -> None:
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["t_s", "gx", "gy", "gz", "ax", "ay", "az"])
        for r in imu:
            w.writerow([f"{r[0]:.4f}",
                        f"{r[1]:.5f}", f"{r[2]:.5f}", f"{r[3]:.5f}",
                        f"{r[4]:.4f}", f"{r[5]:.4f}", f"{r[6]:.4f}"])


def write_dvl_csv(path: str, dvl: np.ndarray) -> None:
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["t_s", "vx", "vy", "vz"])
        for r in dvl:
            w.writerow([f"{r[0]:.4f}", f"{r[1]:.4f}", f"{r[2]:.4f}", f"{r[3]:.4f}"])


# ==========================================
# 5. 主入口
# ==========================================
def generate(out_dir: str = "./sim_output", cfg: Config = C,
             write_plots: bool = True) -> Dict[str, Any]:
    """
    生成完整模拟数据集。
    返回 meta dict（包含 ground truth 与生成参数）。
    """
    finalize_pixel_mapping(cfg)
    os.makedirs(out_dir, exist_ok=True)
    in_dir = os.path.join(out_dir, "input")
    gt_dir = os.path.join(out_dir, "gt")
    imu_dir = os.path.join(out_dir, "imu")
    dvl_dir = os.path.join(out_dir, "dvl")
    for d in [in_dir, gt_dir, imu_dir, dvl_dir]:
        os.makedirs(d, exist_ok=True)

    rng = np.random.default_rng(cfg.seed)

    # ---- 真值位姿 ----
    poses6, poses_T = make_poses(cfg)
    keyframe_idx = select_keyframe_indices(cfg)
    print(f"[sim] poses: {poses_T.shape}, keyframes: {keyframe_idx}")

    # ---- 场景 + 渲染 ----
    world = SceneWorld(cfg)
    print(f"[sim] world: {len(world.pillars)} pillars")
    print(f"[sim] rendering sonar frames ...")
    images, lm_ids, elevs, hits = render_all_frames(
        poses_T, world, cfg=cfg, n_elev=25, rng=rng)

    # ---- 真值 landmark（同时供 tracks 投影和 BA 用） ----
    landmarks = world.sample_landmarks(n_per_pillar=30, rng=rng)
    M = landmarks.shape[0]
    print(f"[sim] landmarks: {M}")

    # ---- tracks.csv ----
    print(f"[sim] extracting tracks ...")
    rows, visibility = extract_tracks(landmarks, poses_T, world, cfg=cfg, rng=rng)
    print(f"[sim] tracks total: {len(rows)}")
    # 关键帧上的
    kf_set = set(keyframe_idx)
    n_obs_kf = sum(1 for r in rows if r["frame_id"] in kf_set)
    print(f"[sim] obs on keyframes: {n_obs_kf}")
    n_tracks = len({r["track_id"] for r in rows if r["track_id"] >= 0})
    print(f"[sim] unique tracks: {n_tracks}")
    # visibility 统计
    vis_per_lm = visibility.sum(axis=0)
    print(f"[sim] lm visibility: min={vis_per_lm.min()}, max={vis_per_lm.max()}, "
          f"mean={vis_per_lm.mean():.1f}, n_multi_frame={(vis_per_lm >= 2).sum()}/{M}")

    # ---- 关键帧位姿（含噪初值） ----
    poses_K_noisy, odom_rel = build_keyframe_poses(poses_T, keyframe_idx,
                                                    add_noise=True, rng=rng)

    # ---- 写文件 ----
    np.save(os.path.join(in_dir, "poses_est.npy"), poses_K_noisy)
    np.save(os.path.join(in_dir, "pose_frame_ids.npy"), np.array(keyframe_idx, dtype=np.int64))
    np.save(os.path.join(in_dir, "landmarks_final.npy"), landmarks)
    np.save(os.path.join(gt_dir, "landmarks_gt.npy"), landmarks)
    np.save(os.path.join(gt_dir, "poses_gt.npy"), poses_T)
    np.save(os.path.join(gt_dir, "sonar_images.npy"), images)
    np.save(os.path.join(gt_dir, "sonar_lm_id.npy"), lm_ids)
    np.save(os.path.join(gt_dir, "pixel_hits.npy"), hits)
    np.save(os.path.join(gt_dir, "pixel_elevs.npy"), elevs)
    np.save(os.path.join(gt_dir, "poses_keyframe_gt.npy"), poses_T[keyframe_idx])

    write_tracks_csv(os.path.join(in_dir, "tracks.csv"), rows)
    write_sensor_calib(os.path.join(in_dir, "sensor_calib.yaml"), cfg)
    write_odom_csv(os.path.join(in_dir, "odom_rel.csv"), odom_rel, cfg)

    # IMU/DVL
    print(f"[sim] simulating IMU/DVL ...")
    imu, dvl = simulate_imu_dvl(poses_T, cfg=cfg, rng=rng)
    write_imu_csv(os.path.join(imu_dir, "imu_data.csv"), imu)
    write_dvl_csv(os.path.join(dvl_dir, "dvl_data.csv"), dvl)

    # ---- meta ----
    meta = {
        "cfg": {
            "seed": cfg.seed,
            "motion_mode": cfg.traj.motion_mode,
            "n_frames": cfg.traj.n_frames,
            "n_keyframes": len(keyframe_idx),
            "keyframe_indices": keyframe_idx,
            "n_pillars": len(world.pillars),
            "pillar_specs": cfg.scene.pillars,
            "sonar": {
                "beam_count": cfg.sonar.beam_count,
                "range_bin_count": cfg.sonar.range_bin_count,
                "fov_azimuth_deg": cfg.sonar.fov_azimuth_deg,
                "fov_elevation_deg": cfg.sonar.fov_elevation_deg,
                "range_min_m": cfg.sonar.range_min_m,
                "range_max_m": cfg.sonar.range_max_m,
            },
            "noise": {
                "sigma_theta_rad": cfg.noise.sigma_theta_rad,
                "sigma_rho_m": cfg.noise.sigma_rho_m,
                "p_miss": cfg.noise.p_miss,
                "p_false_alarm": cfg.noise.p_false_alarm,
            },
        },
        "stats": {
            "n_observations": len(rows),
            "n_obs_on_keyframes": n_obs_kf,
            "n_tracks": n_tracks,
            "n_landmarks": int(landmarks.shape[0]),
            "n_imu_samples": int(imu.shape[0]),
            "n_dvl_samples": int(dvl.shape[0]),
        },
    }
    with open(os.path.join(out_dir, "meta.json"), "w") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)
    print(f"[sim] DONE. Output: {out_dir}")
    return meta
