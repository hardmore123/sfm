import io, sys, json, warnings
import numpy as np
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import feasibility as F

print("=== F-7 sigma_rho 台账接口验收 ===")
print("规格中值        : %.1f mm" % (F.SIGMA_RHO_SPEC_MID * 1000))
print("带宽受限 c/2B   : %.1f mm  (B=0.3MHz)" % (F.sigma_rho_bandwidth_limited(0.3e6) * 1000))
print("采样受限(25m/600): %.1f mm" % (F.sigma_rho_bin_limited(25.0, 600) * 1000))
print("采样受限(15m/1600): %.1f mm" % (F.sigma_rho_bin_limited(15.0, 1600) * 1000))

m = json.load(open("scene_set_v2/S1_single_well_constrained/meta.json", encoding="utf-8"))
with warnings.catch_warnings(record=True) as w:
    warnings.simplefilter("always")
    s, src = F.resolve_sigma_rho(m)
    got_warn = len(w) > 0
print("\nS1 场景解析      : sigma_rho=%.1f mm  source=%s  告警=%s"
      % (s * 1000, src, got_warn))

try:
    F.resolve_sigma_rho(m, strict=True)
    strict_ok = False
except KeyError:
    strict_ok = True
print("strict 模式缺失即报错: %s" % strict_ok)

print("\n=== 口径统一后 tau_z_crit 的差异（说明为何必须统一）===")
for name, sr in [("规格中值 10mm", 0.010), ("敏感性档实测 40.9mm", 0.0409)]:
    for tier, pm in [("主档 7.5°", np.deg2rad(7.5)), ("敏感档 17°", np.deg2rad(17))]:
        print("  %-20s %-12s tau_z_crit = %5.1f cm"
              % (name, tier, F.tau_z_crit(sr, 10, pm) * 100))

ok = got_warn and strict_ok
print("\nF-7 判定: %s" % ("通过" if ok else "未通过"))
