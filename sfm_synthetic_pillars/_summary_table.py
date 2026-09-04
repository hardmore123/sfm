"""打印 S1-S6 总结表（ASCII 输出，避免 GBK 问题）。"""
import json
import os

print('=== S1-S6 总结表 ===')
print('%-32s %-7s %-6s %-7s %-7s %-10s %-10s %-10s' % (
    'scene', 'feas', 'match', 'h_avg', 'd_avg', 'n_target', 'n_shadow', 'MAE_noisy'))
print('-' * 100)
for n in sorted(os.listdir('./scene_set_v2')):
    p = os.path.join('./scene_set_v2', n, 'meta.json')
    if not os.path.exists(p):
        continue
    with open(p, encoding='utf-8') as f:
        m = json.load(f)
    feas = 'feas' if m['feasibility']['is_feasible'] else 'infeas'
    match = 'OK' if m['feasibility']['feas_match'] else 'NO'
    h = m['scene']['h_avg_m']
    d = m['scene']['d_avg_m']
    mae = m['inversion']['mae_v2_noisy_median_cm']
    mae_str = f'{mae:.2f}cm' if mae is not None else 'N/A'
    print('%-32s %-7s %-6s %-7.2f %-7.2f %-10d %-10d %-10s' % (
        n, feas, match, h, d,
        m['stats']['n_target_pixels_total'],
        m['stats']['n_shadow_pixels_total'],
        mae_str))
