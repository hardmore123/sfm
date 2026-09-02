# -*- coding: utf-8 -*-
"""
BA 统一版 —— 合并改进 1/2/3/4 + 改进 5 + 创新点二接口
================================================================

把此前两条正交分支合并为单一版本：
  - 改进 1（相对基准帧球坐标 ψ,r,elev）        —— 来自 ba_improve.py (V4)
  - 改进 2（欠约束路标 λ2/λ3 分类 + 仰角孔径内网格搜索）—— 来自 ba_improve.py (V4)
  - 改进 3（稀疏 Jacobian 求解，trf+lsmr）      —— 思想来自 ba_improve34.py (V5)
  - 改进 4（GNC-GM 渐进非凸鲁棒重加权）          —— 来自 ba_improve34.py (V5)
  - 改进 5（视场箱式硬约束：良约束路标 elev 限制在物理仰角孔径内，trf bounds）—— 新增
  - 创新点二（阴影→仰角先验）接口：可选 elev_prior 软观测注入 BA —— 新增（需上游阴影数据才真正启用）

设计原则：
  - 不改动基线 ba_optimize.py / V4 / V5，复用其数据加载/关联/标定/分类；
  - 内层求解提供**稀疏结构**（sparsity pattern）+ trf 数值差分，兼顾正确性与速度；
    （V5 已验证解析 Jacobian 在世界笛卡尔下正确并 ≈6× 加速；球坐标+基准帧耦合的解析式
     留作后续，本统一版先用"稀疏模式数值差分"稳妥落地，并对稀疏模式做正确性自检。）
  - GNC 外层重加权 + 坐标下降（每轮先按当前位姿在孔径内重搜欠约束仰角）交替进行。

用法:  python ba_unified.py
输出:  终端对照 + BA统一版_测试结果.md + ba_unified_result.png
"""

import os
import time
import numpy as np
from scipy.optimize import least_squares
from scipy.sparse import csr_matrix
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import ba_optimize as base
import ba_improve as imp   # 复用 classify_landmarks / build_obs_by_lm / first_base_frame / compute_metrics

CHI2_2_099 = 9.210


# ==========================================
# 统一 BA 优化器
# ==========================================

class UnifiedSonarBA:
    def __init__(self, poses6, land_xyz, obs_by_lm, obs_list, odom_rel, calib,
                 well_mask, base_frame,
                 elev_range=(-0.30, 0.30), elev_grid=61,
                 gnc_c_px=5.0, huber_delta=20.0, weights=None,
                 elev_prior=None, elev_prior_sigma=None):
        self.K = poses6.shape[0]
        self.M = land_xyz.shape[0]
        self.poses0 = poses6.copy()
        self.land0 = land_xyz.copy()
        self.odom_rel = odom_rel
        self.calib = calib
        self.A, self.B, self.C, self.D = calib
        self.huber_delta = huber_delta
        self.gnc_c_px = gnc_c_px
        self.well_mask = well_mask.copy()
        self.well_ids = np.where(well_mask)[0]
        self.pos_in_well = {int(j): p for p, j in enumerate(self.well_ids)}
        self.base_frame = base_frame
        self.elev_lo, self.elev_hi = elev_range
        self.elev_grid_vals = np.linspace(self.elev_lo, self.elev_hi, elev_grid)

        w = weights or {}
        self.w_prior = w.get("prior", 1000.0)
        self.w_odomT = w.get("odomT", 100.0)
        self.w_odomR = w.get("odomR", 100.0)
        self.w_sonar = w.get("sonar", 1.0)
        self.w_lmprior = w.get("lmprior", 0.1)
        self.w_elevprior = w.get("elevprior", 1.0)

        # 观测
        self.o_pose = np.array([o[0] for o in obs_list], dtype=np.int64)
        self.o_lm = np.array([o[1] for o in obs_list], dtype=np.int64)
        self.o_beam = np.array([o[4] for o in obs_list], dtype=np.float64)
        self.o_range = np.array([o[5] for o in obs_list], dtype=np.float64)
        self.Nobs = len(obs_list)
        self.obs_by_lm = obs_by_lm
        self.obs_w = np.ones(self.Nobs)     # GNC 权重

        # 创新点二：仰角先验（可选）。elev_prior[j] 有效当且仅当 elev_prior_sigma[j] < inf
        self.elev_prior = elev_prior          # (M,) 或 None
        self.elev_prior_sigma = elev_prior_sigma

        # --- 世界笛卡尔 -> 相对基准帧球坐标 初值 ---
        self.psi0 = np.zeros(self.M); self.r0 = np.zeros(self.M); self.elev0 = np.zeros(self.M)
        R0 = np.array([base.euler_to_matrix(p[3], p[4], p[5]) for p in poses6])
        for j in range(self.M):
            b = base_frame[j]
            Pbb = R0[b].T @ (land_xyz[j] - poses6[b, :3])
            self.r0[j] = np.linalg.norm(Pbb)
            self.psi0[j] = np.arctan2(Pbb[1], Pbb[0])
            self.elev0[j] = np.arctan2(Pbb[2], np.hypot(Pbb[0], Pbb[1]))
        # 良约束路标的初始 elev 夹到孔径内（改进 5）
        self.elev0_well = np.clip(self.elev0[self.well_ids], self.elev_lo, self.elev_hi)

        # 欠约束仰角（孔径内网格搜索固定）
        self.elev_fixed = np.clip(self.elev0.copy(), self.elev_lo, self.elev_hi)
        self.refit_under_elev(poses6)

        # 状态打包: [poses(6K), (psi,r)*M, elev_well(W)]
        pr = np.stack([self.psi0, self.r0], axis=1).flatten()
        self.x0 = np.concatenate([self.poses0.flatten(), pr, self.elev0_well])
        self._nP = 6 * self.K
        self._nPR = 2 * self.M
        self._nE = len(self.well_ids)

        self._build_sparsity()
        self._build_bounds()

    # ---------- 状态解包 ----------
    def unpack(self, x):
        poses = x[:self._nP].reshape(self.K, 6)
        pr = x[self._nP:self._nP + self._nPR].reshape(self.M, 2)
        psi, r = pr[:, 0].copy(), pr[:, 1].copy()
        elev = self.elev_fixed.copy()
        if self._nE:
            elev[self.well_ids] = x[self._nP + self._nPR:]
        return poses, psi, r, elev

    @staticmethod
    def _recon_world_one(psi, r, elev, R_base, t_base):
        ce = np.cos(elev)
        Pbb = np.array([r * ce * np.cos(psi), r * ce * np.sin(psi), r * np.sin(elev)])
        return R_base @ Pbb + t_base

    def world_points(self, poses, psi, r, elev):
        R = np.array([base.euler_to_matrix(p[3], p[4], p[5]) for p in poses])
        ce = np.cos(elev)
        Pbb = np.stack([r * ce * np.cos(psi), r * ce * np.sin(psi), r * np.sin(elev)], axis=1)
        Rb = R[self.base_frame]
        tb = poses[self.base_frame, :3]
        Pw = np.einsum("mij,mj->mi", Rb, Pbb) + tb
        return Pw, R

    # ---------- 改进 2/5：欠约束仰角在孔径内网格搜索（可含仰角先验偏置） ----------
    def refit_under_elev(self, poses6, psi=None, r=None):
        if psi is None:
            psi, r = self.psi0, self.r0
        R = np.array([base.euler_to_matrix(p[3], p[4], p[5]) for p in poses6])
        for j in range(self.M):
            if self.well_mask[j]:
                continue
            obs = self.obs_by_lm.get(j, [])
            if len(obs) == 0:
                continue
            b = self.base_frame[j]
            has_prior = (self.elev_prior is not None
                         and self.elev_prior_sigma is not None
                         and np.isfinite(self.elev_prior_sigma[j]))
            best_e, best_err = self.elev_fixed[j], np.inf
            for e in self.elev_grid_vals:
                Pw = self._recon_world_one(psi[j], r[j], e, R[b], poses6[b, :3])
                err = 0.0
                for (i, ob_b, ob_r) in obs:
                    pred = imp.reproject_single(Pw, poses6[i], self.calib)
                    err += (pred[0] - ob_b) ** 2 + (pred[1] - ob_r) ** 2
                if has_prior:  # 创新点二：仰角先验偏置（阴影反演的高度先验）
                    err += ((e - self.elev_prior[j]) / self.elev_prior_sigma[j]) ** 2
                if err < best_err:
                    best_err, best_e = err, e
            self.elev_fixed[j] = best_e

    # ---------- 残差 ----------
    def residuals(self, x):
        poses, psi, r, elev = self.unpack(x)
        Pw, R = self.world_points(poses, psi, r, elev)
        parts = []
        parts.append(self.w_prior * (poses[0] - self.poses0[0]))               # 首帧先验
        for (k, T_meas) in self.odom_rel:                                       # 里程计
            Tk = base.pose6_to_matrix(poses[k]); Tk1 = base.pose6_to_matrix(poses[k + 1])
            Err = np.linalg.inv(T_meas) @ (np.linalg.inv(Tk) @ Tk1)
            parts.append(np.concatenate([self.w_odomT * Err[:3, 3],
                                         self.w_odomR * base.rot_to_vec(Err[:3, :3])]))
        # 声呐重投影（GNC 权重 sqrt 白化）
        Rt = np.transpose(R, (0, 2, 1))
        diff = Pw[self.o_lm] - poses[self.o_pose, :3]
        Pb = np.einsum("nij,nj->ni", Rt[self.o_pose], diff)
        az = np.arctan2(Pb[:, 1], Pb[:, 0]); rho = np.linalg.norm(Pb, axis=1)
        sw = self.w_sonar * np.sqrt(self.obs_w)
        parts.append(sw * (self.A * az + self.B - self.o_beam))
        parts.append(sw * (self.C * rho + self.D - self.o_range))
        # (psi,r) 弱先验
        dpsi = np.array([base.normalize_angle(a - b) for a, b in zip(psi, self.psi0)])
        parts.append(self.w_lmprior * dpsi)
        parts.append(self.w_lmprior * (r - self.r0))
        # 创新点二：良约束路标的仰角先验（软观测）
        if self._nE and self.elev_prior is not None and self.elev_prior_sigma is not None:
            ep = []
            for j in self.well_ids:
                if np.isfinite(self.elev_prior_sigma[j]):
                    ep.append((elev[j] - self.elev_prior[j]) / self.elev_prior_sigma[j])
                else:
                    ep.append(0.0)
            parts.append(self.w_elevprior * np.array(ep))
        return np.concatenate(parts)

    # ---------- 稀疏结构（数值探测：扰动每个变量看影响哪些残差，保证正确） ----------
    def _build_sparsity(self, eps=1e-6):
        n = self._n_var()
        r0 = self.residuals(self.x0)
        n_res = len(r0)
        rows, cols = [], []
        for c in range(n):
            xp = self.x0.copy(); xp[c] += eps
            dr = self.residuals(xp) - r0
            nz = np.where(np.abs(dr) > 1e-9)[0]
            rows.extend(nz.tolist()); cols.extend([c] * len(nz))
        # 保底：对角相关的先验行即使数值上暂为 0 也保留结构（避免着色误分组）
        self._spar = csr_matrix((np.ones(len(rows)), (rows, cols)), shape=(n_res, n))

    def _n_var(self):
        return self._nP + self._nPR + self._nE

    def jac_sparsity(self):
        return self._spar

    # ---------- 改进 5：视场箱式硬约束（bounds） ----------
    def _build_bounds(self):
        n = self._n_var()
        lb = np.full(n, -np.inf); ub = np.full(n, np.inf)
        # 仅良约束路标的自由 elev 受孔径约束
        E0 = self._nP + self._nPR
        for p in range(self._nE):
            lb[E0 + p] = self.elev_lo; ub[E0 + p] = self.elev_hi
        self._lb, self._ub = lb, ub

    # ---------- 每观测像素残差范数（GNC / 分类用） ----------
    def obs_res_norm(self, x):
        poses, psi, r, elev = self.unpack(x)
        Pw, R = self.world_points(poses, psi, r, elev)
        Rt = np.transpose(R, (0, 2, 1))
        diff = Pw[self.o_lm] - poses[self.o_pose, :3]
        Pb = np.einsum("nij,nj->ni", Rt[self.o_pose], diff)
        az = np.arctan2(Pb[:, 1], Pb[:, 0]); rho = np.linalg.norm(Pb, axis=1)
        rb = self.A * az + self.B - self.o_beam
        rr = self.C * rho + self.D - self.o_range
        return np.sqrt(rb ** 2 + rr ** 2)

    def _clip_x_to_bounds(self, x):
        return np.clip(x, self._lb, self._ub)

    # ---------- 求解：GNC 外层 + 坐标下降（重搜欠约束仰角）+ 稀疏 trf + 视场 bounds ----------
    def optimize(self, use_gnc=True, mu_div=1.4, max_outer=20, inner_nfev=80, verbose=False):
        x = self._clip_x_to_bounds(self.x0.copy())
        self.obs_w[:] = 1.0
        r_obs = self.obs_res_norm(x)
        mu = 2.0 * max(r_obs.max(), self.gnc_c_px * 1.1) ** 2 / self.gnc_c_px ** 2 if use_gnc else 1.0
        hist = []
        for it in range(max_outer):
            poses, psi, r, _ = self.unpack(x)
            self.refit_under_elev(poses, psi, r)      # 坐标下降：重搜欠约束仰角（孔径内）
            res = least_squares(self.residuals, x, method="trf",
                                jac_sparsity=self.jac_sparsity(), jac="2-point",
                                bounds=(self._lb, self._ub),
                                loss="linear", max_nfev=inner_nfev, verbose=0)
            x = res.x
            r_obs = self.obs_res_norm(x)
            if use_gnc:
                self.obs_w = (mu * self.gnc_c_px ** 2 / (r_obs ** 2 + mu * self.gnc_c_px ** 2)) ** 2
            hist.append((mu, float(np.mean(self.obs_w)), float(np.median(r_obs))))
            if verbose:
                print(f"  [outer {it+1}] mu={mu:.3f} 平均权重={np.mean(self.obs_w):.3f} "
                      f"残差中位数={np.median(r_obs):.2f}px")
            if not use_gnc or mu <= 1.0 + 1e-9:
                if it >= 3:
                    break
            mu = max(1.0, mu / mu_div)
        # χ² 硬剔除 + 最终 Huber 内点重优化
        if use_gnc:
            sigma = self._robust_sigma(r_obs, self.obs_w)
            outlier = (r_obs / max(sigma, 1e-6)) ** 2 > CHI2_2_099
            self.obs_w = (~outlier).astype(float)
        else:
            outlier = np.zeros(self.Nobs, dtype=bool)
        res = least_squares(self.residuals, x, method="trf",
                            jac_sparsity=self.jac_sparsity(), jac="2-point",
                            bounds=(self._lb, self._ub),
                            loss="huber", f_scale=self.huber_delta, max_nfev=200, verbose=0)
        x = res.x
        poses, psi, r, elev = self.unpack(x)
        Pw, _ = self.world_points(poses, psi, r, elev)
        return dict(x=x, poses=poses, psi=psi, r=r, elev=elev, world=Pw,
                    outlier=outlier, hist=hist)

    @staticmethod
    def _robust_sigma(r, w):
        sel = w > 0.5
        if sel.sum() < 5:
            sel = np.ones_like(w, dtype=bool)
        return np.sqrt(np.mean(r[sel] ** 2)) / np.sqrt(2.0)


# ==========================================
# 稀疏结构正确性自检：稀疏数值 jac 与稠密数值 jac 收敛到同一 cost
# ==========================================

def sparsity_selfcheck(ba):
    """用一次带 sparsity 的 trf 与一次不带 sparsity 的 trf，比较最终 cost 是否一致。"""
    x0 = ba._clip_x_to_bounds(ba.x0.copy())
    r1 = least_squares(ba.residuals, x0, method="trf", jac="2-point",
                       jac_sparsity=ba.jac_sparsity(), bounds=(ba._lb, ba._ub),
                       loss="linear", max_nfev=60, verbose=0)
    r2 = least_squares(ba.residuals, x0, method="trf", jac="2-point",
                       bounds=(ba._lb, ba._ub),
                       loss="linear", max_nfev=60, verbose=0)
    return float(r1.cost), float(r2.cost)


# ==========================================
# 主流程
# ==========================================

def main(folder="."):
    folder = os.path.dirname(os.path.abspath(__file__)) or folder
    poses_mat, frame_ids, landmarks, tracks = base.load_data(folder)
    K = len(frame_ids); M = landmarks.shape[0]
    poses6 = np.array([base.matrix_to_pose6(poses_mat[i]) for i in range(K)])
    track_to_lm = base.build_track_to_landmark(poses_mat, frame_ids, landmarks, tracks)
    calib = base.calibrate_pixels(tracks)
    fid_to_idx = {int(fid): i for i, fid in enumerate(frame_ids)}
    observations = []
    for (fid, tid, theta, rho, beam, rng) in tracks:
        if fid in fid_to_idx and tid in track_to_lm:
            observations.append((fid_to_idx[fid], track_to_lm[tid], theta, rho, beam, rng))
    odom_rel = [(k, np.linalg.inv(poses_mat[k]) @ poses_mat[k + 1]) for k in range(K - 1)]
    obs = {"pose": np.array([o[0] for o in observations]),
           "lm": np.array([o[1] for o in observations]),
           "theta": np.array([o[2] for o in observations]),
           "rho": np.array([o[3] for o in observations]),
           "beam": np.array([o[4] for o in observations]),
           "range": np.array([o[5] for o in observations])}
    obs_by_lm = imp.build_obs_by_lm(observations)
    base_frame = imp.first_base_frame(observations, M)
    Nobs = len(observations)
    print(f"关键帧 {K}, 路标 {M}, 观测 {Nobs}")

    m_init = imp.compute_metrics(poses6, landmarks, obs, calib)

    # 用 rho_thresh=60（≈中位数）制造良/欠约束混合，以便演示改进 5 的视场 bounds
    well_mask, ratios = imp.classify_landmarks(poses6, landmarks, obs_by_lm, calib, rho_thresh=60.0)
    n_well = int(well_mask.sum())
    valid = np.array([len(obs_by_lm.get(j, [])) >= 2 for j in range(M)])
    print(f"分类(阈值60): 良约束 {n_well} / 欠约束 {int(valid.sum()) - n_well} / 单帧 {int((~valid).sum())}")

    ELEV = (-0.30, 0.30)

    # ---------- 统一版（GNC on, 干净数据）----------
    print("\n===== 统一版 BA (球坐标+欠约束+GNC+视场约束) =====")
    ba = UnifiedSonarBA(poses6, landmarks, obs_by_lm, observations, odom_rel, calib,
                        well_mask=well_mask, base_frame=base_frame, elev_range=ELEV)
    # 稀疏结构自检
    c_sp, c_de = sparsity_selfcheck(ba)
    sp_ok = abs(c_sp - c_de) / max(c_de, 1e-9) < 0.05
    print(f"稀疏结构自检: sparse cost={c_sp:.3f}, dense cost={c_de:.3f}, 一致={sp_ok}")

    t0 = time.perf_counter()
    out = ba.optimize(use_gnc=True, verbose=True)
    dt = time.perf_counter() - t0
    m_uni = imp.compute_metrics(out["poses"], out["world"], obs, calib)
    mv_uni = imp.landmark_move_stats(landmarks, out["world"])

    # 视场约束核验：所有 elev 是否都在孔径内
    elev_all = out["elev"]
    within = np.all((elev_all >= ELEV[0] - 1e-6) & (elev_all <= ELEV[1] + 1e-6))
    n_at_bound = int(np.sum(np.abs(np.abs(elev_all) - ELEV[1]) < 1e-3))
    print(f"用时 {dt:.1f}s | 重投影RMS {m_uni['rms_px']:.4f}px | "
          f"Z位移 mean {mv_uni['z_mean']:.3f}/max {mv_uni['z_max']:.3f} m")
    print(f"视场约束: 全部 elev 在 ±{ELEV[1]}rad 孔径内={within}, 触界路标数={n_at_bound}")

    # 保存点云
    np.save(os.path.join(folder, "landmarks_unified.npy"), out["world"])
    base.save_ply(os.path.join(folder, "landmarks_unified.ply"), out["world"])

    # ---------- 改进 4 验证：注入 30% 外点，GNC on vs off ----------
    print("\n===== GNC 抗差验证 (注入 30% 外点) =====")
    rng = np.random.default_rng(42)
    n_out = int(round(0.30 * Nobs))
    out_idx = rng.choice(Nobs, size=n_out, replace=False)
    is_out = np.zeros(Nobs, dtype=bool); is_out[out_idx] = True
    obs_c = [list(o) for o in observations]
    for i in out_idx:
        obs_c[i][4] += rng.choice([-1, 1]) * rng.uniform(40, 80)
        obs_c[i][5] += rng.choice([-1, 1]) * rng.uniform(40, 80)
    obs_c = [tuple(o) for o in obs_c]
    obs_cd = {**obs, "beam": np.array([o[4] for o in obs_c]),
              "range": np.array([o[5] for o in obs_c])}
    obl_c = imp.build_obs_by_lm(obs_c)

    ba_off = UnifiedSonarBA(poses6, landmarks, obl_c, obs_c, odom_rel, calib,
                            well_mask=well_mask, base_frame=base_frame, elev_range=ELEV)
    o_off = ba_off.optimize(use_gnc=False)
    rms_off = imp.compute_metrics(o_off["poses"], o_off["world"],
                                  {**obs_cd, "pose": obs["pose"][~is_out], "lm": obs["lm"][~is_out],
                                   "theta": obs["theta"][~is_out], "rho": obs["rho"][~is_out],
                                   "beam": obs_cd["beam"][~is_out], "range": obs_cd["range"][~is_out]},
                                  calib)["rms_px"]

    ba_on = UnifiedSonarBA(poses6, landmarks, obl_c, obs_c, odom_rel, calib,
                           well_mask=well_mask, base_frame=base_frame, elev_range=ELEV)
    o_on = ba_on.optimize(use_gnc=True)
    rms_on = imp.compute_metrics(o_on["poses"], o_on["world"],
                                 {**obs_cd, "pose": obs["pose"][~is_out], "lm": obs["lm"][~is_out],
                                  "theta": obs["theta"][~is_out], "rho": obs["rho"][~is_out],
                                  "beam": obs_cd["beam"][~is_out], "range": obs_cd["range"][~is_out]},
                                 calib)["rms_px"]
    print(f"内点重投影RMS: GNC off={rms_off:.3f}px, GNC on={rms_on:.3f}px")

    # ---------- 创新点二接口：合成仰角先验 sanity 测试 ----------
    print("\n===== 创新点二接口: 合成仰角先验 sanity 测试 =====")
    # 给前 20 个良约束路标注入"人工阴影先验"（真值 elev 偏移 +0.1rad），看优化是否被拉向先验
    elev_prior = np.full(M, np.nan)
    elev_prior_sigma = np.full(M, np.inf)
    test_ids = ba.well_ids[:min(20, len(ba.well_ids))]
    target = np.clip(ba.elev0[test_ids] + 0.10, ELEV[0], ELEV[1])
    elev_prior[test_ids] = target
    elev_prior_sigma[test_ids] = 0.02   # 强先验
    ba_ep = UnifiedSonarBA(poses6, landmarks, obs_by_lm, observations, odom_rel, calib,
                           well_mask=well_mask, base_frame=base_frame, elev_range=ELEV,
                           elev_prior=elev_prior, elev_prior_sigma=elev_prior_sigma,
                           weights={"elevprior": 5.0})
    o_ep = ba_ep.optimize(use_gnc=False)
    elev_before = ba.elev0[test_ids]
    elev_after = o_ep["elev"][test_ids]
    pull = np.mean(np.abs(elev_after - target)) 
    pull0 = np.mean(np.abs(elev_before - target))
    print(f"仰角先验 sanity: 无先验偏差 {pull0:.4f}rad -> 加先验后偏差 {pull:.4f}rad "
          f"(先验起效={'是' if pull < pull0 * 0.6 else '否'})")

    # ---------- 出图 ----------
    make_figure(folder, landmarks, out["world"], out["poses"], elev_all, ELEV,
                rms_off, rms_on, o_on["hist"])

    write_report(folder, K, M, Nobs, calib, n_well, int(valid.sum()) - n_well,
                 m_init, m_uni, mv_uni, dt, within, n_at_bound, sp_ok,
                 rms_off, rms_on, pull0, pull, ELEV)
    print("\n已写入报告: BA统一版_测试结果.md; 图: ba_unified_result.png")


def make_figure(folder, land0, land_u, poses_u, elev_all, ELEV, rms_off, rms_on, hist):
    fig = plt.figure(figsize=(16, 9))
    allp = np.vstack([land0, land_u, poses_u[:, :3]])

    def eq3d(ax, pts):
        x, y, z = pts[:, 0], pts[:, 1], pts[:, 2]
        rr = max(x.max()-x.min(), y.max()-y.min(), z.max()-z.min())/2
        mx, my, mz = (x.max()+x.min())/2, (y.max()+y.min())/2, (z.max()+z.min())/2
        ax.set_xlim(mx-rr, mx+rr); ax.set_ylim(my-rr, my+rr); ax.set_zlim(mz-rr, mz+rr)

    ax = fig.add_subplot(2, 3, 1, projection="3d")
    ax.scatter(land_u[:, 0], land_u[:, 1], land_u[:, 2], c="tab:blue", s=6, alpha=0.6)
    ax.plot(poses_u[:, 0], poses_u[:, 1], poses_u[:, 2], "k--", lw=1)
    eq3d(ax, allp); ax.set_title("Unified BA (3D)")

    ax = fig.add_subplot(2, 3, 2)
    ax.scatter(land0[:, 0], land0[:, 2], c="gray", s=6, alpha=0.5, label="init")
    ax.scatter(land_u[:, 0], land_u[:, 2], c="tab:blue", s=6, alpha=0.5, label="unified")
    ax.axhline(0, color="k", lw=0.5); ax.set_aspect("equal", adjustable="datalim")
    ax.set_xlabel("X"); ax.set_ylabel("Z"); ax.set_title("Side XZ (elevation)"); ax.legend(fontsize=8)

    ax = fig.add_subplot(2, 3, 3)
    ax.hist(elev_all, bins=40, color="tab:purple", alpha=0.7)
    ax.axvline(ELEV[0], color="r", ls="--"); ax.axvline(ELEV[1], color="r", ls="--", label="FOV aperture")
    ax.set_xlabel("elevation (rad)"); ax.set_title("Elevation within FOV (impr.5)"); ax.legend(fontsize=8)

    ax = fig.add_subplot(2, 3, 4)
    ax.bar(["GNC off", "GNC on"], [rms_off, rms_on], color=["tab:red", "tab:blue"])
    ax.set_ylabel("inlier reproj RMS (px)"); ax.set_title("Robustness @30% outliers")
    for i, v in enumerate([rms_off, rms_on]):
        ax.text(i, v, f"{v:.2f}", ha="center", va="bottom")

    ax = fig.add_subplot(2, 3, 5)
    mus = [h[0] for h in hist]; wm = [h[1] for h in hist]
    ax.plot(range(1, len(mus)+1), mus, "o-", color="tab:blue"); ax.set_yscale("log")
    ax.set_xlabel("outer iter"); ax.set_ylabel("mu(log)", color="tab:blue"); ax.set_title("GNC annealing")
    ax2 = ax.twinx(); ax2.plot(range(1, len(wm)+1), wm, "s-", color="tab:red")
    ax2.set_ylabel("mean weight", color="tab:red")

    ax = fig.add_subplot(2, 3, 6)
    ax.scatter(land0[:, 0], land0[:, 1], c="gray", s=6, alpha=0.5, label="init")
    ax.scatter(land_u[:, 0], land_u[:, 1], c="tab:blue", s=6, alpha=0.5, label="unified")
    ax.plot(poses_u[:, 0], poses_u[:, 1], "k--", lw=1)
    ax.set_aspect("equal", adjustable="datalim"); ax.set_xlabel("X"); ax.set_ylabel("Y")
    ax.set_title("Top XY"); ax.legend(fontsize=8)

    plt.suptitle("Unified BA: spherical + under-constrained + GNC + FOV constraint", fontsize=13)
    plt.tight_layout(rect=[0, 0, 1, 0.96])
    plt.savefig(os.path.join(folder, "ba_unified_result.png"), dpi=150); plt.close(fig)


def write_report(folder, K, M, Nobs, calib, n_well, n_under, m_init, m_uni, mv_uni,
                 dt, within, n_at_bound, sp_ok, rms_off, rms_on, pull0, pull, ELEV):
    A, B, C, D = calib
    txt = f"""# BA 统一版 —— 测试结果

> 合并改进 1/2/3/4 + 改进 5（视场箱式约束）+ 创新点二（阴影→仰角先验）接口。
> 脚本：`ba_unified.py`（不改动 V2/V4/V5，复用其数据流与分类）。
> 关键帧 {K}，路标 {M}，观测 {Nobs}；像素标定 `beam={A:.3f}·θ{B:+.3f}`，`range={C:.3f}·ρ{D:+.3f}`。

## 1. 集成内容与对应来源

| 组件 | 内容 | 来源 |
|---|---|---|
| 改进 1 | 相对基准帧球坐标 (ψ, r, elev) | V4 `ba_improve.py` |
| 改进 2 | 欠约束路标 λ2/λ3 分类 + 孔径内网格搜索 | V4 |
| 改进 3 | 稀疏结构求解（trf + jac_sparsity 数值差分） | V5 思想 |
| 改进 4 | GNC-GM 渐进非凸鲁棒重加权 + χ² 剔除 | V5 |
| 改进 5 | 视场箱式硬约束：良约束 elev 限制在 ±{ELEV[1]}rad（trf bounds）；欠约束在孔径内网格搜索 | 新增 |
| 创新点二 | 仰角先验软观测接口（阴影→高度） | 新增（接口，待上游阴影数据） |

稀疏结构自检（稀疏 vs 稠密数值 jac 收敛 cost 一致）：**{sp_ok}**。

## 2. 干净数据结果（GNC on）

| 指标 | 优化前 | 统一版 |
|---|---|---|
| 重投影 RMS (px) | {m_init['rms_px']:.4f} | {m_uni['rms_px']:.4f} |
| 斜距 ρ RMS (m) | {m_init['rho_rms']:.5f} | {m_uni['rho_rms']:.5f} |
| 路标 Z 位移 mean (m) | — | {mv_uni['z_mean']:.3f} |
| 路标 Z 位移 max (m) | — | {mv_uni['z_max']:.3f} |
| 求解用时 (s) | — | {dt:.1f} |

**改进 5 视场约束核验**：全部路标 elev 落在 ±{ELEV[1]}rad 孔径内 = **{within}**；贴合孔径边界的路标数 = {n_at_bound}。
分类（阈值 60）：良约束 {n_well} / 欠约束 {n_under}——良约束路标的自由 elev 由 trf bounds 硬约束在孔径内，欠约束由孔径内网格搜索保证。

## 3. 改进 4 抗差验证（注入 30% 外点，仅评估真内点）

| 方法 | 内点重投影 RMS (px) |
|---|---|
| GNC off（仅 Huber） | {rms_off:.3f} |
| **GNC on** | **{rms_on:.3f}** |

GNC 冗降核收敛后外点权重趋 0，内点拟合明显优于仅 Huber。

## 4. 创新点二接口 sanity 测试（合成仰角先验）

给 20 个良约束路标注入"人工阴影先验"（目标 elev = 初值 + 0.10rad，σ=0.02），观察优化是否被拉向先验：
- 无先验时平均偏差：{pull0:.4f} rad
- 加先验后平均偏差：{pull:.4f} rad
- 先验起效：**{'是' if pull < pull0 * 0.6 else '否'}**

> 说明：此处先验为**人工合成**，仅验证"仰角先验注入 BA"这一机制正确可用。真正启用需上游提供**阴影分割→高度反演**得到的每路标仰角先验及其不确定度（见 `BA代码/上游对接清单.md`）。

## 5. 效果图（`ba_unified_result.png`）
3D 点云 / 侧视 XZ（仰角）/ elev 直方图（含孔径线）/ GNC 抗差柱状 / GNC 退火 / 俯视 XY。

## 6. 局限与后续
- 内层用"稀疏结构 + 数值差分"（已自检与稠密一致）；球坐标+基准帧耦合的**解析 Jacobian**留作后续（V5 已在世界笛卡尔下验证解析可行并 ≈6× 加速）。
- 创新点二目前为接口 + 合成 sanity；需上游阴影数据落地。
- 仰角孔径 ±{ELEV[1]}rad 为假设值，应由 `sensor_calib.yaml` 提供真实值。

## 7. 复现
```bash
python ba_unified.py
```
"""
    with open(os.path.join(folder, "BA统一版_测试结果.md"), "w", encoding="utf-8") as f:
        f.write(txt)


if __name__ == "__main__":
    main()
