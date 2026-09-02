import numpy as np
from scipy.optimize import least_squares
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
import cv2


# ==========================================
# 1. 基础数学工具
# ==========================================

def euler_to_matrix(roll, pitch, yaw):
    cr, sr = np.cos(roll), np.sin(roll)
    cp, sp = np.cos(pitch), np.sin(pitch)
    cy, sy = np.cos(yaw), np.sin(yaw)
    Rx = np.array([[1, 0, 0], [0, cr, -sr], [0, sr, cr]])
    Ry = np.array([[cp, 0, sp], [0, 1, 0], [-sp, 0, cp]])
    Rz = np.array([[cy, -sy, 0], [sy, cy, 0], [0, 0, 1]])
    return Rz @ Ry @ Rx


def normalize_angle(angle):
    return (angle + np.pi) % (2 * np.pi) - np.pi


# ==========================================
# 2. 核心优化器 (相对球坐标参数化)
# ==========================================

class SonarSFMOptimizer:
    def __init__(self, sonar_params):
        self.fx = sonar_params['fx']
        self.fy = sonar_params['fy']
        self.cx = sonar_params['cx']
        self.cy = sonar_params['cy']
        self.max_range = sonar_params['max_range']
        self.initialized = False
        self.landmark_base_indices = {}

    def initialize_landmarks(self, poses_init, observations):
        landmarks_param_dict = {}
        self.landmark_base_indices = {}
        obs_by_frame = {}
        for frame_idx, lm_idx, uv in observations:
            if frame_idx not in obs_by_frame: obs_by_frame[frame_idx] = []
            obs_by_frame[frame_idx].append((lm_idx, uv))

        sorted_frames = sorted(obs_by_frame.keys())
        max_lm_idx = max([obs[1] for obs in observations])
        src_height, src_width = my_params["src_shape"]

        for f_idx in sorted_frames:
            if f_idx >= len(poses_init): break
            for lm_idx, uv in obs_by_frame[f_idx]:
                if lm_idx in landmarks_param_dict: continue

                self.landmark_base_indices[lm_idx] = f_idx
                u, v = uv
                r_val = (v / src_height) * my_params['max_range']
                theta_val = 0.0
                phi_val = (u / src_width) * (my_params['max_angle'] - my_params['min_angle']) + my_params['min_angle']
                phi_val = np.radians(phi_val)
                landmarks_param_dict[lm_idx] = np.array([theta_val, phi_val, r_val])

        landmarks_init = []
        for i in range(max_lm_idx + 1):
            if i in landmarks_param_dict:
                landmarks_init.append(landmarks_param_dict[i])
            else:
                landmarks_init.append(np.array([0.0, 0.0, 1.0]))
                self.landmark_base_indices[i] = 0
        return landmarks_init

    def set_observations(self, poses_init, landmarks_init, odom_data, sonar_obs):
        self.num_poses = len(poses_init)
        self.num_landmarks = len(landmarks_init)
        self.num_odom = len(odom_data)
        self.sonar_obs = sonar_obs
        self.poses_init = np.array(poses_init, dtype=np.float64)
        self.landmarks_init = np.array(landmarks_init, dtype=np.float64)
        self.odom_data = np.array(odom_data, dtype=np.float64)

        self.weights = {
            'prior': np.eye(6) * 1,
            'sonar': np.eye(2) * 1,
            'odom': np.eye(6) * 1
        }
        self.theta0 = np.concatenate([self.poses_init.flatten(), self.landmarks_init.flatten()])
        self.initialized = True

    def sonar_projection_model_relative(self, current_pose, base_pose, landmark_spherical):
        theta, phi, r = landmark_spherical
        c_theta = np.cos(theta)
        x_base = r * np.cos(phi) * c_theta
        y_base = r * np.sin(phi) * c_theta
        z_base = r * np.sin(theta)
        P_base = np.array([x_base, y_base, z_base])

        R_base = euler_to_matrix(base_pose[3], base_pose[4], base_pose[5])
        t_base = base_pose[:3]
        P_world = R_base @ P_base + t_base

        R_curr = euler_to_matrix(current_pose[3], current_pose[4], current_pose[5])
        t_curr = current_pose[:3]
        P_body = R_curr.T @ (P_world - t_curr)

        x_s, y_s, z_s = P_body
        r_pred = np.sqrt(x_s ** 2 + y_s ** 2 + z_s ** 2)
        psi_pred = np.arctan2(y_s, x_s)
        theta_pred = np.arctan2(z_s, x_s)

        theta_pred = np.radians(theta_pred)

        if theta_pred < my_params['theta_min'] or theta_pred > my_params['theta_max']:
            u = 0.0
            v = 0.0
        else:
            u = self.cx + self.fx * psi_pred
            v = self.cy + self.fy * r_pred

        return np.array([u, v])

    def error_function(self, theta_vec):
        pose_dim, land_dim = 6, 3
        poses = theta_vec[:self.num_poses * pose_dim].reshape((self.num_poses, pose_dim))
        landmarks = theta_vec[self.num_poses * pose_dim:].reshape((self.num_landmarks, land_dim))
        errors = []
        errors.append(self.weights['prior'] @ (poses[0] - self.poses_init[0]))
        for k in range(self.num_odom):
            pred = poses[k + 1] - poses[k]
            pred[3:] = normalize_angle(pred[3:])
            meas = self.odom_data[k]
            err = pred - meas
            err[3:] = normalize_angle(err[3:])
            errors.append(self.weights['odom'] @ err)

        for (i, j, obs_uv) in self.sonar_obs:
            base_idx = self.landmark_base_indices.get(j, 0)
            if base_idx < len(poses):
                current_pose = poses[i]
                base_pose = poses[base_idx]
                lm_sphere = landmarks[j]
                pred_uv = self.sonar_projection_model_relative(current_pose, base_pose, lm_sphere)
                errors.append(self.weights['sonar'] @ (pred_uv - obs_uv))
        return np.concatenate(errors)

    def optimize(self, ftol=1e-6, verbose=1):
        assert self.initialized
        res = least_squares(self.error_function, self.theta0, method='lm', ftol=ftol, verbose=verbose, max_nfev=10000)
        optimized_poses = res.x[:self.num_poses * 6].reshape((self.num_poses, 6))
        optimized_params = res.x[self.num_poses * 6:].reshape((self.num_landmarks, 3))

        landmarks_xyz = []
        for j in range(self.num_landmarks):
            theta, phi, r = optimized_params[j]
            base_idx = self.landmark_base_indices.get(j, 0)
            base_pose = optimized_poses[base_idx]
            c_theta = np.cos(theta)
            x_b = r * np.cos(phi) * c_theta
            y_b = r * np.sin(phi) * c_theta
            z_b = r * np.sin(theta)
            P_b = np.array([x_b, y_b, z_b])
            R_base = euler_to_matrix(base_pose[3], base_pose[4], base_pose[5])
            t_base = base_pose[:3]
            P_w = R_base @ P_b + t_base
            landmarks_xyz.append(P_w)

        return {
            'poses': optimized_poses,
            'landmarks': np.array(landmarks_xyz),
            'raw_params': optimized_params,
            'cost': res.cost
        }


# ==========================================
# 3. 辅助函数与主流程 (已修改可视化部分)
# ==========================================

def visualize_results(result, save_path=None):
    poses = result['poses']
    landmarks = result['landmarks']

    fig = plt.figure(figsize=(12, 10))
    ax = fig.add_subplot(111, projection='3d')

    # 1. 绘制基本轨迹和地标
    ax.plot(poses[:, 0], poses[:, 1], poses[:, 2], 'k--', linewidth=1, label='Trajectory', alpha=0.5)
    ax.scatter(landmarks[:, 0], landmarks[:, 1], landmarks[:, 2], c='blue', marker='^', s=30, label='Landmarks')

    # 2. 定义绘制坐标轴的辅助函数 (quiver绘制矢量)
    def draw_coordinate_frame(ax, position, R_matrix, length=0.2, linewidth=1.5):
        # R_matrix 的列向量分别是 X, Y, Z 在世界坐标系下的方向
        # X轴 (红)
        ax.quiver(position[0], position[1], position[2],
                  R_matrix[0, 0], R_matrix[1, 0], R_matrix[2, 0],
                  length=length, color='r', linewidth=linewidth)
        # Y轴 (绿)
        ax.quiver(position[0], position[1], position[2],
                  R_matrix[0, 1], R_matrix[1, 1], R_matrix[2, 1],
                  length=length, color='g', linewidth=linewidth)
        # Z轴 (蓝)
        ax.quiver(position[0], position[1], position[2],
                  R_matrix[0, 2], R_matrix[1, 2], R_matrix[2, 2],
                  length=length, color='b', linewidth=linewidth)

    # 3. 绘制全局原点坐标轴 (World Frame, 稍微画大一点)
    origin = np.array([0, 0, 0])
    identity_R = np.eye(3)
    draw_coordinate_frame(ax, origin, identity_R, length=0.5, linewidth=2.0)
    ax.text(0.5, 0, 0, "X_w", color='r', fontsize=12, fontweight='bold')
    ax.text(0, 0.5, 0, "Y_w", color='g', fontsize=12, fontweight='bold')
    ax.text(0, 0, 0.5, "Z_w", color='b', fontsize=12, fontweight='bold')

    # 4. 绘制每个位姿的局部坐标轴 (Body Frame)
    # 这能直观地展示每一帧的旋转情况
    for i in range(len(poses)):
        pos = poses[i, :3]
        roll, pitch, yaw = poses[i, 3:]
        R = euler_to_matrix(roll, pitch, yaw)

        # 画出当前位姿的坐标系 (长度设小一点以免混乱)
        draw_coordinate_frame(ax, pos, R, length=0.15, linewidth=1.0)

        # 标注起点和终点
        if i == 0:
            ax.text(pos[0], pos[1], pos[2], "Start", fontsize=10)
        elif i == len(poses) - 1:
            ax.text(pos[0], pos[1], pos[2], "End", fontsize=10)

    # 5. 关键步骤：设置轴比例相等 (Equal Aspect Ratio)
    # Matplotlib 3D 默认会自动缩放轴以填满画布，导致正方体看起来像长方体。
    # 这里我们构建一个虚拟的立方体包围盒来强制比例相等。
    all_x = np.concatenate((poses[:, 0], landmarks[:, 0], [0, 0.5]))  # 包含原点
    all_y = np.concatenate((poses[:, 1], landmarks[:, 1], [0, 0.5]))
    all_z = np.concatenate((poses[:, 2], landmarks[:, 2], [0, 0.5]))

    max_range = np.array([all_x.max() - all_x.min(), all_y.max() - all_y.min(), all_z.max() - all_z.min()]).max() / 2.0
    mid_x = (all_x.max() + all_x.min()) * 0.5
    mid_y = (all_y.max() + all_y.min()) * 0.5
    mid_z = (all_z.max() + all_z.min()) * 0.5

    ax.set_xlim(mid_x - max_range, mid_x + max_range)
    ax.set_ylim(mid_y - max_range, mid_y + max_range)
    ax.set_zlim(mid_z - max_range, mid_z + max_range)

    ax.set_xlabel('X (m)')
    ax.set_ylabel('Y (m)')
    ax.set_zlabel('Z (m)')
    ax.set_title('Optimized Trajectory & Landmarks with Coordinate Axes')
    ax.legend()

    if save_path: plt.savefig(save_path)
    plt.show()


def solve_sonar_sfm(sonar_params, odom_data, observations, start_pose=None, init_poses=None):
    if init_poses is None:
        if start_pose is None: start_pose = np.zeros(6)
        calculated_poses = [np.array(start_pose)]
        curr_pose = np.array(start_pose)
        for odom in odom_data:
            next_pose = curr_pose + odom
            next_pose[3:] = normalize_angle(next_pose[3:])
            calculated_poses.append(next_pose)
            curr_pose = next_pose
        init_poses = calculated_poses

    optimizer = SonarSFMOptimizer(sonar_params)
    init_landmarks_spherical = optimizer.initialize_landmarks(init_poses, observations)
    optimizer.set_observations(init_poses, init_landmarks_spherical, odom_data, observations)
    print("开始优化 (Relative Spherical Parameterization)...")
    result = optimizer.optimize(verbose=1)
    return result


if __name__ == "__main__":
    image_path = 'data/090.png'
    raw_img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    if raw_img is None:
        raw_img = np.zeros((381, 512), dtype=np.uint8)

    my_params = {'fx': 225.66, 'fy': 170, 'cx': 256.0, 'cy': 0,
                 'max_range': 3.0, 'min_angle': -65.0, 'max_angle': 65.0,
                 'src_shape': raw_img.shape,
                 'theta_min':-10.0, 'theta_max':10.0}



    my_odom = [
        np.array([0.0000, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000]),
        np.array([-0.0294, 0.0091, -0.0744, -0.0247, -0.0773, -0.0133]),
        np.array([-0.0851, -0.0156, -0.1250, 0.0336, -0.2047, -0.0307]),
        np.array([-0.0804, 0.0167, -0.1732, -0.0162, -0.2596, -0.0414]),
        np.array([-0.0816, 0.0078, -0.2127, 0.0167, -0.2878, -0.0555]),
        np.array([-0.0951, -0.0197, -0.2418, 0.0027, -0.3115, -0.0447]),
        np.array([-0.0690, 0.0229, -0.2551, 0.0031, -0.3252, -0.0455]),
        np.array([-0.0692, -0.0022, -0.2661, 0.0127, -0.3319, -0.0057]),
        np.array([-0.0486, 0.0160, -0.3108, -0.0139, -0.3290, -0.0216]),
        np.array([-0.0360, -0.0353, -0.3053, 0.0168, -0.3233, -0.0120]),
        np.array([-0.0106, 0.0030, -0.3169, -0.0109, -0.2967, -0.0307]),
        np.array([-0.0178, -0.0518, -0.3030, 0.0086, -0.2745, -0.0181]),
]

    odom_deltas = [
        np.array([-0.0294, 0.0091, -0.0744, -0.0247, -0.0773, -0.0133]),
        np.array([-0.0851, -0.0156, -0.1250, 0.0336, -0.2047, -0.0307]),
        np.array([-0.0804, 0.0167, -0.1732, -0.0162, -0.2596, -0.0414]),
        np.array([-0.0816, 0.0078, -0.2127, 0.0167, -0.2878, -0.0555]),
        np.array([-0.0951, -0.0197, -0.2418, 0.0027, -0.3115, -0.0447]),
        np.array([-0.0690, 0.0229, -0.2551, 0.0031, -0.3252, -0.0455]),
        np.array([-0.0692, -0.0022, -0.2661, 0.0127, -0.3319, -0.0057]),
        np.array([-0.0486, 0.0160, -0.3108, -0.0139, -0.3290, -0.0216]),
        np.array([-0.0360, -0.0353, -0.3053, 0.0168, -0.3233, -0.0120]),
        np.array([-0.0106, 0.0030, -0.3169, -0.0109, -0.2967, -0.0307]),
        np.array([-0.0178, -0.0518, -0.3030, 0.0086, -0.2745, -0.0181]),
    ]

    my_obs = [
        (0, 0, np.array([175.63, 337.08])),
        (0, 1, np.array([177.61, 313.16])),
        (0, 2, np.array([179.60, 288.24])),
        (0, 3, np.array([186.54, 274.29])),
        (0, 4, np.array([196.47, 259.34])),
        (0, 5, np.array([200.43, 245.38])),
        (0, 6, np.array([214.33, 234.42])),
        (0, 7, np.array([226.23, 239.40])),
        (0, 8, np.array([236.16, 244.39])),
        (0, 9, np.array([242.11, 260.34])),
        (0, 10, np.array([245.09, 270.30])),
        (0, 11, np.array([247.07, 281.27])),
        (0, 12, np.array([247.07, 291.23])),
        (0, 13, np.array([248.06, 304.19])),
        (0, 14, np.array([249.05, 311.17])),
        (1, 0, np.array([169.49, 323.13])),
        (1, 1, np.array([170.48, 301.20])),
        (1, 2, np.array([174.45, 278.28])),
        (1, 3, np.array([175.44, 265.32])),
        (1, 4, np.array([182.39, 253.36])),
        (1, 5, np.array([188.34, 239.40])),
        (1, 6, np.array([205.21, 224.45])),
        (1, 7, np.array([222.08, 222.46])),
        (1, 8, np.array([232.99, 233.42])),
        (1, 9, np.array([240.93, 247.38])),
        (1, 10, np.array([242.91, 257.35])),
        (1, 11, np.array([239.94, 266.32])),
        (1, 12, np.array([243.91, 280.27])),
        (1, 13, np.array([241.92, 291.23])),
        (1, 14, np.array([245.89, 300.20])),
        (2, 0, np.array([138.53, 304.19])),
        (2, 1, np.array([137.53, 282.26])),
        (2, 2, np.array([142.50, 260.34])),
        (2, 3, np.array([148.45, 244.39])),
        (2, 4, np.array([152.42, 224.45])),
        (2, 5, np.array([164.33, 213.49])),
        (2, 6, np.array([175.24, 201.53])),
        (2, 7, np.array([197.07, 198.54])),
        (2, 8, np.array([210.96, 207.51])),
        (2, 9, np.array([218.90, 220.47])),
        (2, 10, np.array([218.90, 229.44])),
        (2, 11, np.array([223.86, 242.39])),
        (2, 12, np.array([227.83, 252.36])),
        (2, 13, np.array([227.83, 264.32])),
        (2, 14, np.array([228.82, 278.28])),
        (3, 0, np.array([121.46, 276.28])),
        (3, 1, np.array([120.47, 256.35])),
        (3, 2, np.array([124.43, 231.43])),
        (3, 3, np.array([127.41, 212.49])),
        (3, 4, np.array([138.33, 195.55])),
        (3, 5, np.array([147.26, 184.58])),
        (3, 6, np.array([164.12, 175.61])),
        (3, 7, np.array([184.96, 172.62])),
        (3, 8, np.array([200.84, 179.60])),
        (3, 9, np.array([210.76, 189.57])),
        (3, 10, np.array([217.71, 205.51])),
        (3, 11, np.array([220.68, 219.47])),
        (3, 12, np.array([221.67, 233.42])),
        (3, 13, np.array([222.67, 238.41])),
        (3, 14, np.array([224.65, 254.35])),
        (4, 0, np.array([104.39, 254.35])),
        (4, 1, np.array([105.38, 237.41])),
        (4, 2, np.array([109.35, 219.47])),
        (4, 3, np.array([115.30, 199.53])),
        (4, 4, np.array([122.25, 181.59])),
        (4, 5, np.array([133.16, 172.62])),
        (4, 6, np.array([156.98, 163.65])),
        (4, 7, np.array([176.82, 159.66])),
        (4, 8, np.array([192.70, 168.64])),
        (4, 9, np.array([202.62, 181.59])),
        (4, 10, np.array([207.58, 193.55])),
        (4, 11, np.array([215.52, 207.51])),
        (4, 12, np.array([218.50, 222.46])),
        (4, 13, np.array([218.50, 236.41])),
        (4, 14, np.array([218.50, 254.35])),
        (5, 0, np.array([89.30, 235.42])),
        (5, 1, np.array([91.29, 208.50])),
        (5, 2, np.array([96.25, 190.56])),
        (5, 3, np.array([103.19, 174.62])),
        (5, 4, np.array([114.11, 158.67])),
        (5, 5, np.array([127.01, 143.72])),
        (5, 6, np.array([138.91, 144.71])),
        (5, 7, np.array([152.81, 140.73])),
        (5, 8, np.array([165.71, 145.71])),
        (5, 9, np.array([181.58, 146.71])),
        (5, 10, np.array([187.53, 154.68])),
        (5, 11, np.array([198.45, 168.64])),
        (5, 12, np.array([206.39, 175.61])),
        (5, 13, np.array([207.38, 190.56])),
        (5, 14, np.array([209.36, 207.51])),
        (6, 0, np.array([80.19, 231.43])),
        (6, 1, np.array([82.17, 215.48])),
        (6, 2, np.array([85.15, 198.54])),
        (6, 3, np.array([91.10, 180.60])),
        (6, 4, np.array([98.05, 162.66])),
        (6, 5, np.array([110.95, 150.69])),
        (6, 6, np.array([125.83, 141.72])),
        (6, 7, np.array([144.68, 138.73])),
        (6, 8, np.array([154.60, 136.74])),
        (6, 9, np.array([173.46, 144.71])),
        (6, 10, np.array([189.33, 149.70])),
        (6, 11, np.array([199.26, 162.66])),
        (6, 12, np.array([205.21, 174.62])),
        (6, 13, np.array([204.22, 189.57])),
        (6, 14, np.array([209.18, 201.53])),
        (7, 0, np.array([78.99, 224.45])),
        (7, 1, np.array([76.02, 203.52])),
        (7, 2, np.array([81.97, 185.58])),
        (7, 3, np.array([83.95, 168.64])),
        (7, 4, np.array([92.88, 155.68])),
        (7, 5, np.array([104.79, 138.73])),
        (7, 6, np.array([126.62, 132.75])),
        (7, 7, np.array([148.45, 125.78])),
        (7, 8, np.array([169.29, 129.76])),
        (7, 9, np.array([180.20, 138.73])),
        (7, 10, np.array([193.10, 146.71])),
        (7, 11, np.array([201.04, 161.66])),
        (7, 12, np.array([205.01, 172.62])),
        (7, 13, np.array([206.00, 181.59])),
        (7, 14, np.array([207.98, 201.53])),
        (8, 0, np.array([72.84, 209.50])),
        (8, 1, np.array([75.81, 194.55])),
        (8, 2, np.array([78.79, 174.62])),
        (8, 3, np.array([84.74, 161.66])),
        (8, 4, np.array([91.69, 146.71])),
        (8, 5, np.array([101.61, 133.75])),
        (8, 6, np.array([122.45, 128.77])),
        (8, 7, np.array([142.29, 122.79])),
        (8, 8, np.array([157.18, 124.78])),
        (8, 9, np.array([181.98, 135.74])),
        (8, 10, np.array([193.89, 152.69])),
        (8, 11, np.array([203.81, 168.64])),
        (8, 12, np.array([205.80, 181.59])),
        (8, 13, np.array([205.80, 189.57])),
        (8, 14, np.array([206.79, 202.52])),
        (9, 0, np.array([70.65, 205.51])),
        (9, 1, np.array([69.66, 182.59])),
        (9, 2, np.array([73.63, 166.64])),
        (9, 3, np.array([82.56, 150.69])),
        (9, 4, np.array([93.47, 134.75])),
        (9, 5, np.array([108.36, 122.79])),
        (9, 6, np.array([133.16, 119.80])),
        (9, 7, np.array([149.04, 115.81])),
        (9, 8, np.array([165.91, 118.80])),
        (9, 9, np.array([179.80, 128.77])),
        (9, 10, np.array([189.72, 141.72])),
        (9, 11, np.array([198.65, 151.69])),
        (9, 12, np.array([206.59, 164.65])),
        (9, 13, np.array([208.57, 179.60])),
        (9, 14, np.array([209.57, 195.55])),
        (10, 0, np.array([72.43, 200.53])),
        (10, 1, np.array([75.41, 179.60])),
        (10, 2, np.array([81.36, 162.66])),
        (10, 3, np.array([81.36, 147.70])),
        (10, 4, np.array([93.27, 133.75])),
        (10, 5, np.array([109.15, 123.78])),
        (10, 6, np.array([125.02, 117.80])),
        (10, 7, np.array([146.85, 118.80])),
        (10, 8, np.array([158.76, 117.80])),
        (10, 9, np.array([172.65, 122.79])),
        (10, 10, np.array([186.54, 126.77])),
        (10, 11, np.array([197.46, 135.74])),
        (10, 12, np.array([203.41, 146.71])),
        (10, 13, np.array([207.38, 151.69])),
        (10, 14, np.array([209.36, 170.63])),
        (11, 0, np.array([69.27, 196.54])),
        (11, 1, np.array([69.27, 181.59])),
        (11, 2, np.array([74.23, 166.64])),
        (11, 3, np.array([77.21, 151.69])),
        (11, 4, np.array([85.15, 138.73])),
        (11, 5, np.array([98.05, 123.78])),
        (11, 6, np.array([115.91, 116.81])),
        (11, 7, np.array([136.74, 110.82])),
        (11, 8, np.array([154.60, 111.82])),
        (11, 9, np.array([184.37, 117.80])),
        (11, 10, np.array([193.30, 124.78])),
        (11, 11, np.array([202.23, 135.74])),
        (11, 12, np.array([205.21, 143.72])),
        (11, 13, np.array([209.18, 154.68])),
        (11, 14, np.array([209.18, 175.61])),
    ]

    start_pose = np.array([0.0, 0.0, 0.0, 0.03491, 0.1322, 0.22348])
    result = solve_sonar_sfm(my_params, odom_deltas, my_obs, start_pose=start_pose, init_poses=my_odom)
    if result:
        visualize_results(result)