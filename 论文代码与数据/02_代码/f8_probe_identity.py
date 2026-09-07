"""F-8 核查：证明 scene_set_main / scene_set_v2 的 ★II-1 反演是代数恒等式。

链条：
  shadow.py 写入   L_s = D_t·h/(z_s−h)          （解析真值）
                   D_t_map = d_horiz_obj         （解析真值）
                   target_elev = arctan((h−z_s)/D_t)（解析真值）
  gen_scenes_v2 算  D_t = (z_s − z_top)/|tan(elev)|  ← z_top 就是待估的 h
  反演           h = z_s(1 − D_t/D_e),  D_e = D_t + L_s

代入：D_e = D_t + D_t·h/(z_s−h) = D_t·z_s/(z_s−h)
      h_inv = z_s(1 − (z_s−h)/z_s) = h        ⇒ 恒等，与数据无关
"""
import io, sys, json, os
import numpy as np
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

print("=" * 76)
print("① 符号验证：任意 (z_s, h, D_t) 下 h_inv − h 是否恒为 0")
print("=" * 76)
rng = np.random.default_rng(0)
maxerr = 0.0
for _ in range(100000):
    z_s = rng.uniform(0.5, 10.0)
    h = rng.uniform(0.01, z_s * 0.99)
    D_t = rng.uniform(0.5, 50.0)
    L_s = D_t * h / (z_s - h)          # shadow.py 写入的解析 L_s
    D_e = D_t + L_s
    h_inv = z_s * (1.0 - D_t / D_e)    # 反演式
    maxerr = max(maxerr, abs(h_inv - h))
print(f"  10 万组随机 (z_s,h,D_t)：max|h_inv − h| = {maxerr:.3e} m")
print(f"  ⇒ {'恒等式确认（误差仅浮点舍入）' if maxerr < 1e-9 else '非恒等'}")

print()
print("=" * 76)
print("② 数据验证：直接用场景落盘的 GT 复算")
print("=" * 76)
for scene in ["scene_set_main/S1_main_single",
              "scene_set_v2/S1_single_well_constrained"]:
    if not os.path.isdir(scene):
        continue
    m = json.load(open(os.path.join(scene, "meta.json"), encoding="utf-8"))
    z_s = m["config"]["z_s_m"]
    L = np.load(os.path.join(scene, "gt", "shadow_length_maps.npy"))
    D = np.load(os.path.join(scene, "gt", "D_t_map.npy"))
    Hg = np.load(os.path.join(scene, "gt", "height_gt_maps.npy"))
    inv = np.load(os.path.join(scene, "innovation2", "height_inverted.npy"))

    ok = np.isfinite(L) & np.isfinite(D) & (L > 0) & (D > 0)
    De = D[ok] + L[ok]
    h_re = z_s * (1.0 - D[ok] / De)

    print(f"\n  {scene}  (z_s={z_s})")
    print(f"    有效阴影像素 {ok.sum()}")
    print(f"    L_s 唯一值 {np.unique(np.round(L[ok],6)).size} 个  "
          f"D_t 唯一值 {np.unique(np.round(D[ok],6)).size} 个")
    # 与落盘 inverted 对比
    iv = inv[ok] if inv.shape == L.shape else None
    if iv is not None:
        d = np.abs(iv - h_re)
        d = d[np.isfinite(d)]
        if d.size:
            print(f"    我按恒等式复算 vs 落盘 height_inverted：max差 {d.max():.3e} m")
    # 与 GT 高度对比
    hg = Hg[ok] if Hg.shape == L.shape else None
    if hg is not None:
        v = np.isfinite(hg)
        if v.sum():
            e = np.abs(h_re[v] - hg[v])
            print(f"    恒等式复算 vs height_gt：max {e.max():.3e} m  "
                  f"中位 {np.median(e):.3e} m")

print()
print("=" * 76)
print("结论")
print("=" * 76)
print("""
★II-1 在 scene_set_main / scene_set_v2 上报出的反演精度（无噪 MAE=0.00 cm、
含噪 0.19 cm）不是测量精度，而是代数恒等式的浮点残差 + 人为注入 σ_L 的传播。
原因：shadow.py 把解析 L_s 与解析 D_t 逐像素写进 GT 图，
      gen_scenes_v2 又用 z_top（即待估的 h）反算 D_t。
⇒ 这些数字不可作为 ★II-1 的立身证据（与既有结论"500× 改进作废"同源，
   但范围更大：不仅对比无效，自身精度数字也无效）。
F-8 必须同时修：
  (a) shadow.py 阴影足迹须按仰角孔径裁剪（现只检查物体顶部）
  (b) L_s 必须由 shadow_mask 沿距离轴量测（leading/trailing edge），不得读解析值
  (c) D_t 必须由柱基回波或 BA 位姿给出，不得用 z_top 反算
""")
