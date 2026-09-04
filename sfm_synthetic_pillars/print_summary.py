"""打印 summary.json。"""
import json, sys
s = json.load(open(sys.argv[1]))
print(f"场景总数: {len(s)}\n")
print(f"{'场景':<35} | {'#lm':<5} | {'#obs':<6} | {'#KF':<4} | {'良约束':<8} | {'反演z_err_cm':<14} | {'BA_RMS':<10} | {'t_s':<7}")
print("-" * 110)
for r in s:
    if "error" in r:
        print(f"{r['name']:<35} | ERROR")
        continue
    st = r.get("stats", {})
    i1 = r.get("innov1", {})
    i2 = r.get("innov2", {})
    z_err_cm = (i2.get("median_abs_error_m", 0) or 0) * 100
    print(f"{r['name']:<35} | {st.get('n_landmarks', 0):<5} | {st.get('n_observations', 0):<6} | "
          f"{st.get('n_keyframes', 0):<4} | {i1.get('n_well_constrained', 0):<8} | "
          f"{z_err_cm:<14.2f} | {i1.get('ba_final_rms_px', 0):<10.3f} | {r.get('time_s', 0):<7.1f}")
