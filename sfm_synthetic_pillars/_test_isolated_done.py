import numpy as np

# 单点
pt = np.array([2.61360906, -0.36038273, 1.00175577])

# 柱 5: (2.5, -0.5, 0.18, 2.4)
cx, cy, r, h = 2.5, -0.5, 0.18, 2.4
dxy = np.sqrt((pt[0] - cx)**2 + (pt[1] - cy)**2)
dz = pt[2]
side = abs(dxy - r)
top = abs(dz - h)
bot = abs(dz - 0.0)
in_cyl = (dxy < r) and (dz > 0) and (dz < h)
print('dxy =', dxy)
print('dz =', dz)
print('side =', side)
print('top =', top)
print('bot =', bot)
print('in_cyl =', in_cyl)
if in_cyl:
    d = min(top, bot)
else:
    d = min(min(side, top), bot)
print('d =', d)
