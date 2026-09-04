"""审计脚本：验证 observability.py 的坐标系错误 + 复核 CRLB 公式。"""
import numpy as np

np.set_printoptions(precision=4, suppress=True)


def Ry(a):
    c, s = np.cos(a), np.sin(a)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def jac(P_w, R, t, A, C, bug=False):
    """单次观测的 2x3 雅可比。bug=True 复现 observability.py 的坐标系不一致。"""
    Pb = R.T @ (P_w - t)
    rho = np.linalg.norm(Pb)
    dth_b = np.array([-Pb[1], Pb[0], 0.0]) / (Pb[0] ** 2 + Pb[1] ** 2)
    drho_b = Pb / rho
    if bug:
        row0 = A * dth_b              # ← 未转世界系（当前代码）
    else:
        row0 = A * (dth_b @ R.T)      # ← 正确
    row1 = C * (drho_b @ R.T)
    return np.vstack([row0, row1])


def sigma_pz(P_w, poses, A, C, sigma_rho, bug=False):
    """由 Lambda 的逆取 zz 元素，得到高度后验标准差（单位：m）。"""
    L = np.zeros((3, 3))
    for R, t in poses:
        J = jac(P_w, R, t, A, C, bug=bug)
        L += J.T @ J
    ev = np.linalg.eigvalsh(L)
    try:
        inv = np.linalg.inv(L)
        s = np.sqrt(abs(inv[2, 2])) * sigma_rho * C  # C 抵消：C=1/sigma_rho 时归一
    except np.linalg.LinAlgError:
        s = np.inf
    return s, ev


# ---------------- 传感器参数（ARIS Explorer 3000）----------------
sigma_rho = 0.010                     # 10 mm
sigma_th = np.deg2rad(0.25) / 3.0     # 波束宽 0.25°，取 1/3 作标准差
C = 1.0 / sigma_rho                   # 白化后的斜距行系数
A = 1.0 / sigma_th                    # 白化后的方位行系数

print("=" * 78)
print("A 组：observability.py 的坐标系错误影响（声呐下俯 20°，目标偏轴 10°）")
print("=" * 78)
theta_p = np.deg2rad(20.0)
R = Ry(theta_p)
t = np.array([0.0, 0.0, 4.0])
# 目标：地面距离 10 m，方位偏轴 10°，高 0.5 m
psi = np.deg2rad(10.0)
P = np.array([10 * np.cos(psi), 10 * np.sin(psi), 0.5])
Jb = jac(P, R, t, A, C, bug=True)
Jg = jac(P, R, t, A, C, bug=False)
print("方位行（bug 版，体坐标系）:", Jb[0])
print("方位行（正确版，世界系）  :", Jg[0])
print("两者夹角(deg)             :",
      np.degrees(np.arccos(np.clip(Jb[0] @ Jg[0] /
                                   (np.linalg.norm(Jb[0]) * np.linalg.norm(Jg[0])), -1, 1))))
print("方位行对世界 z 的偏导  bug:", Jb[0][2], "  正确:", Jg[0][2])
print("斜距行对世界 z 的偏导     :", Jg[1][2])
print("→ 斜距/方位 对 z 的信息比 :",
      (Jg[1][2] / Jg[0][2]) ** 2 if Jg[0][2] != 0 else np.inf)

print()
print("=" * 78)
print("B 组：CRLB 到底取决于 sin(phi) 还是 phi 的离散度")
print("=" * 78)


def make_poses(n, z0, dz, theta_p_deg=20.0):
    """n 个视角，沿 x 平移 + z 起伏 dz（峰峰值）。"""
    ps = []
    for i in range(n):
        x = -1.0 + 2.0 * i / max(n - 1, 1)
        z = z0 + dz * 0.5 * np.sin(2 * np.pi * i / max(n - 1, 1))
        ps.append((Ry(np.deg2rad(theta_p_deg)), np.array([x, 0.0, z])))
    return ps


def phi_stats(P_w, poses):
    phis = []
    for R, t in poses:
        d = P_w - t
        phis.append(np.arcsin(-d[2] / np.linalg.norm(d)))  # 世界系俯角
    phis = np.array(phis)
    return np.degrees(phis.mean()), np.degrees(phis.std())


print(f"{'构型':<26}{'phi均值°':>9}{'phi标准差°':>11}{'实测σPz(cm)':>13}"
      f"{'旧式σρ/(√N sinφ)':>18}{'新式σρ/(√N stdφ)':>18}")
for name, z0, dz, npose, tp in [
    ("下俯20° 无起伏 N=10", 4.0, 0.00, 10, 20.0),
    ("下俯20° 起伏0.2m N=10", 4.0, 0.20, 10, 20.0),
    ("下俯20° 起伏0.8m N=10", 4.0, 0.80, 10, 20.0),
    ("水平0°  起伏0.8m N=10", 4.0, 0.80, 10, 0.0),
    ("下俯20° 起伏0.8m N=30", 4.0, 0.80, 30, 20.0),
]:
    poses = make_poses(npose, z0, dz, tp)
    P = np.array([10.0, 0.0, 0.5])
    s, ev = sigma_pz(P, poses, A, C, sigma_rho, bug=False)
    m, sd = phi_stats(P, poses)
    old = sigma_rho / (np.sqrt(npose) * abs(np.sin(np.deg2rad(m)))) * 100
    new = (sigma_rho / (np.sqrt(npose) * np.deg2rad(sd)) * 100
           if sd > 1e-9 else np.inf)
    print(f"{name:<26}{m:>9.2f}{sd:>11.3f}{s*100:>13.2f}{old:>18.2f}{new:>18.2f}")
