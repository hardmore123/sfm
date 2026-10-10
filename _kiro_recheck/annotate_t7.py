from pathlib import Path

note = " ⚠️ **T7（2026-09-09）作废**：此上限只约束斜距通道，时变横滚可以突破，见 `理论修正_T1-T6.md` §9.5"
files = [r"F:\sfm\论文代码与数据\README.md",
         r"F:\sfm\大论文思想路线\会话交接_20260907.md",
         r"F:\sfm\论文代码与数据\会话交接_20260907.md"]
pairs = [
    (r"> 在给定观测数下，高度精度存在由孔径决定的硬上限 $\tau_z^{\rm crit}$，任何运动方式都无法突破。",
     r"> ~~在给定观测数下，高度精度存在由孔径决定的硬上限 $\tau_z^{\rm crit}$，任何运动方式都无法突破。~~" + note),
    (r"| **硬界**（任何运动无法突破） |",
     r"| **斜距通道硬界**（⚠️T7：时变横滚可突破） |"),
    (r'"高度精度存在孔径决定的硬上限 $\tau_z^{\rm crit,abs}$，任何运动方式都无法突破" |',
     r'"不含时变横滚的运动无法突破斜距通道的孔径上限 $\tau_{z,\rho}^{\rm abs}$"（T7 修订） |'),
    (r"| 高度 CRLB | $\sigma_{P_z}\approx\dfrac{\sigma_\rho}{\sqrt N\operatorname{std}(\varphi_k)}$ | 与实测吻合 6% 内 |",
     r"| 高度 CRLB | $\sigma_{P_z}\approx\dfrac{\sigma_\rho}{\sqrt N\operatorname{std}(\varphi_k)}$（⚠️T7：仅斜距通道近似，正式式为双通道，见 理论修正 §9） | 与实测吻合 6% 内 |"),
]
for f in files:
    p = Path(f)
    t = p.read_text(encoding="utf-8")
    n = 0
    for a, b in pairs:
        if a in t:
            t = t.replace(a, b)
            n += 1
    p.write_text(t, encoding="utf-8")
    print(p.parent.name, p.name, n)
