"""
V2 基线 + 创新二·模块2 阴影高度先验（演示版）
================================================

在 ba_optimize.SonarBA 的 residuals 中追加一项"z 软约束"：
  r_z = w_z * (z_lm - z_prior) / sigma_z

参数：
  z_prior : (M,) 每个 landmark 的 z 高度先验（米），NaN/inf 表示无先验
  sigma_z : (M,) 每个 landmark 的 z 先验不确定度（米），inf 表示无先验
  w_z     : float  先验权重

这是大论文 6.1 主打实验"多视 + 阴影高度先验"的实际接入位置。
"""

import os, sys, time
import numpy as np
sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "BA代码")))

import ba_optimize as base


class SonarBAWithShadowPrior(base.SonarBA):
    """
    在 V2 的 residuals 中增加阴影高度软约束。
    """
    def __init__(self, poses6, landmarks, observations, odom_rel, pixel_calib,
                 z_prior=None, sigma_z=None, w_z=10.0, huber_delta=20.0, weights=None):
        super().__init__(poses6, landmarks, observations, odom_rel, pixel_calib,
                         weights=weights, huber_delta=huber_delta)
        M = self.M
        # 阴影高度先验
        if z_prior is None:
            z_prior = np.full(M, np.nan)
        if sigma_z is None:
            sigma_z = np.full(M, np.inf)
        self.z_prior = np.array(z_prior, dtype=np.float64).copy()
        self.sigma_z = np.array(sigma_z, dtype=np.float64).copy()
        self.w_z = float(w_z)

    def residuals(self, x):
        poses, lms = self.unpack(x)
        res = list(super().residuals(x).reshape(-1))   # 不行，会变 list of ndarray
        # 重新调用 super + 加 z 约束
        res = []
        # 1) 首帧先验
        res.append(self.w_prior * (poses[0] - self.poses0[0]))
        # 2) 里程计
        for (k, T_meas) in self.odom_rel:
            Tk = base.pose6_to_matrix(poses[k])
            Tk1 = base.pose6_to_matrix(poses[k + 1])
            T_rel = np.linalg.inv(Tk) @ Tk1
            Err = np.linalg.inv(T_meas) @ T_rel
            e_t = self.w_odomT * Err[:3, 3]
            e_r = self.w_odomR * base.rot_to_vec(Err[:3, :3])
            res.append(np.concatenate([e_t, e_r]))
        # 3) 声呐重投影
        R = np.array([base.euler_to_matrix(p[3], p[4], p[5]) for p in poses])
        Rt = np.transpose(R, (0, 2, 1))
        t = poses[:, :3]
        Pw = lms[self.o_lm]
        diff = Pw - t[self.o_pose]
        Pb = np.einsum("nij,nj->ni", Rt[self.o_pose], diff)
        theta_pred = np.arctan2(Pb[:, 1], Pb[:, 0])
        rho_pred = np.linalg.norm(Pb, axis=1)
        u_pred = self.A * theta_pred + self.B
        v_pred = self.C * rho_pred + self.D
        res.append(self.w_sonar * (u_pred - self.o_beam))
        res.append(self.w_sonar * (v_pred - self.o_range))
        # 4) 路标弱先验
        res.append(self.w_lmprior * (lms - self.land0).flatten())
        # 5) **创新二·模块2 阴影高度先验**
        valid_z = np.isfinite(self.z_prior) & np.isfinite(self.sigma_z) & (self.sigma_z > 0)
        if valid_z.any():
            r_z = (lms[valid_z, 2] - self.z_prior[valid_z]) / self.sigma_z[valid_z]
            res.append(self.w_z * r_z)
        return np.concatenate(res)


def run_v2_with_shadow_prior(
    input_dir, gt_dir, z_prior, sigma_z, w_z=10.0, label="A_only_multiview"
):
    """跑一次 V2+阴影先验 BA。"""
    poses_mat, frame_ids, landmarks, tracks = base.load_data(input_dir)
    K, M = len(frame_ids), landmarks.shape[0]
    poses6 = np.array([base.matrix_to_pose6(poses_mat[i]) for i in range(K)])
    track_to_lm = base.build_track_to_landmark(poses_mat, frame_ids, landmarks, tracks)
    A, B, C, D = base.calibrate_pixels(tracks)
    fid_to_idx = {int(fid): i for i, fid in enumerate(frame_ids)}
    observations = [(fid_to_idx[fid], track_to_lm[tid], th, rh, bm, rg)
                    for (fid, tid, th, rh, bm, rg) in tracks
                    if fid in fid_to_idx and tid in track_to_lm]
    odom_rel = [(k, np.linalg.inv(poses_mat[k]) @ poses_mat[k + 1]) for k in range(K - 1)]
    ba = SonarBAWithShadowPrior(poses6, landmarks, observations, odom_rel, (A, B, C, D),
                                 z_prior=z_prior, sigma_z=sigma_z, w_z=w_z)
    t0 = time.time()
    poses_opt, land_opt, res = ba.optimize(verbose=0)
    t = time.time() - t0
    # 评估
    gt_poses_K = np.load(os.path.join(gt_dir, "poses_keyframe_gt.npy"))
    gt_lm = np.load(os.path.join(gt_dir, "landmarks_gt.npy"))
    err_pos = np.linalg.norm(poses_opt[:, :3] - gt_poses_K[:, :3, 3], axis=1)
    err_lm = np.linalg.norm(land_opt - gt_lm, axis=1)
    err_lm_z = np.abs(land_opt[:, 2] - gt_lm[:, 2])
    return {
        "label": label,
        "time_s": t,
        "rms_px": float(np.sqrt(np.mean(res.fun ** 2))),
        "pose_err_mean_cm": float(err_pos.mean() * 100),
        "lm_err_mean_cm":   float(err_lm.mean() * 100),
        "lm_z_err_mean_cm": float(err_lm_z.mean() * 100),
    }
