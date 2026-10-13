"""补传：BA代码/sim_input*/ 全部文件 + 作废/未审计场景集的小文本元数据。只用 git add -f，不改 .gitignore。"""
import subprocess, time
from pathlib import Path

ROOT = Path("F:/sfm")
log = []


def git(*a, timeout=200, inp=None):
    r = subprocess.run(["git", "-c", "core.quotepath=false", *a], cwd=ROOT, capture_output=True,
                       text=True, encoding="utf-8", errors="replace", timeout=timeout, input=inp)
    log.append(f"$ git {' '.join(a[:3])} ... -> {r.returncode} {r.stderr.strip()[-300:]}")
    return r


ignored = [f for f in git("ls-files", "--others", "--ignored", "--exclude-standard").stdout.splitlines() if f]

# A) BA代码/sim_input*/ 全部文件
A = [f for f in ignored if f.startswith("BA代码/sim_input")]
# B) 作废/未审计场景集的小文本元数据（只取 sfm_synthetic_pillars 侧，避开 02_代码 下的 junction 副本）
META_DIRS = ("sfm_synthetic_pillars/big_paper_sim/", "sfm_synthetic_pillars/big_paper_scene_set/",
             "sfm_synthetic_pillars/_tmp_heave_baseline/", "sfm_synthetic_pillars/scene_set_v2/",
             "sfm_synthetic_pillars/scene_set_main/", "sfm_synthetic_pillars/innov2_ablations/")
META_EXT = (".json", ".md", ".txt", ".yaml", ".yml")
B = [f for f in ignored if f.startswith(META_DIRS) and f.lower().endswith(META_EXT)
     and (ROOT / f).stat().st_size < 1e6]

for name, lst in (("A sim_input", A), ("B 元数据", B)):
    sz = sum((ROOT / f).stat().st_size for f in lst)
    mx = max(((ROOT / f).stat().st_size, f) for f in lst) if lst else (0, "")
    log.append(f"{name}: {len(lst)} 个, {sz/1e6:.2f} MB, 最大 {mx[0]/1e6:.2f} MB {mx[1]}")

files = A + B
assert all((ROOT / f).stat().st_size < 50e6 for f in files), "存在超过 50MB 的文件，中止"
# 分批 add -f，避免命令行过长
for i in range(0, len(files), 200):
    git("add", "-f", "--", *files[i:i + 200])
staged = [l for l in git("diff", "--cached", "--name-only").stdout.splitlines() if l]
log.append(f"staged {len(staged)}")
if staged:
    git("commit", "-m",
        "data: 补传 BA 仿真输入与作废场景集的文本元数据（force-add）\n\n"
        f"- BA代码/sim_input*/ 共 {len(A)} 个文件：汇报_BA成果 重建图的复现输入\n"
        f"- 作废/未审计场景集的 meta.json / README.md / *.txt / *.yaml 共 {len(B)} 个：便于追溯\n"
        "- 大体积 .npy 掩码与图像仍按 .gitignore 不入库；02_代码 下 junction 副本不重复跟踪")
    for k in range(6):
        r = git("push", "origin", "docs/theory-correction-and-roadmap", timeout=240)
        if r.returncode == 0:
            log.append(f"push ok on try {k+1}")
            break
        time.sleep(15)
log.append(git("status", "-sb").stdout.splitlines()[0])
log.append(git("log", "--oneline", "-1").stdout.strip())
(ROOT / "_kiro_recheck/git_add_extra.log").write_text("\n".join(log), encoding="utf-8")
