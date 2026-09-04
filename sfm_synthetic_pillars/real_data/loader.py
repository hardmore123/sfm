"""
R0 真实数据集统一读取器
=============================

支持 marine-debris-fls-datasets-master 的 4 个子集：
  - watertank-segmentation: 1,868 张 + 12 类逐像素标注
  - quarry-fullsize: 10 段连续序列（289-2,341 帧/段）
  - turntable-cropped: 4,942 帧（转台，物体整圈旋转）
  - watertank-cropped: 2,364 patch

所有图像以 ARIS Explorer 3000 采集（详见 ARIS_EXPLORER_3000_PARAMS.md）。

关联文件：
  - real_data/INVENTORY.md     数据集资产清单
  - real_data/ARIS_EXPLORER_3000_PARAMS.md  传感器参数表

使用：
  from real_data.loader import load_watertank_segmentation, load_quarry_fullsize
  imgs, masks, classes = load_watertank_segmentation(split='train', val_frac=0.2)
"""
from __future__ import annotations
import os
import glob
import json
from typing import Tuple, Dict, List, Optional
import numpy as np

# 路径配置（与本文件相对的根目录）
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
REAL_DATA_ROOT = os.path.normpath(
    os.path.join(_THIS_DIR, '..', '..', '数据集（不上传git）',
                 'marine-debris-fls-datasets-master', 'md_fls_dataset', 'data')
)

# 数据集论文的类别定义（与 loader.py 中的 OBJECT_CLASS_MAPPING 一致）
WATERTANK_CLASSES = [
    'background', 'bottle', 'can', 'chain', 'drink-carton', 'hook',
    'propeller', 'shampoo-bottle', 'standing-bottle', 'tire', 'valve', 'wall'
]
# 共 12 类（0-11）


def _check_root() -> str:
    if not os.path.exists(REAL_DATA_ROOT):
        raise FileNotFoundError(
            f"Real data not found at {REAL_DATA_ROOT}\n"
            f"请确认路径 'F:/sfm/数据集（不上传git）/' 存在"
        )
    return REAL_DATA_ROOT


def load_watertank_segmentation(
    split: Optional[str] = None,
    val_frac: float = 0.2,
    seed: int = 42,
    image_size: Tuple[int, int] = (320, 480),
) -> Dict[str, Dict]:
    """
    加载 watertank-segmentation 子集（1,868 张 + 12 类逐像素标注）

    Args:
        split: 'train', 'val', 或 None（返回全部）
        val_frac: 验证集比例（仅 split 指定时使用）
        seed: 随机种子
        image_size: 图像尺寸（ARIS 原始 320×480 已是这个尺寸）

    Returns:
        {
          'train': {'images': List[str], 'masks': List[str], 'classes': List[str]},
          'val':   {...},
          'all':   {...},
        }
    """
    root = _check_root()
    sub = os.path.join(root, 'watertank-segmentation')
    images_dir = os.path.join(sub, 'Images')
    masks_dir = os.path.join(sub, 'Masks')

    # 列文件
    img_files = sorted(glob.glob(os.path.join(images_dir, '*.png')))
    msk_files = sorted(glob.glob(os.path.join(masks_dir, '*.png')))
    assert len(img_files) == len(msk_files) == 1868, \
        f"Expected 1868 pairs, got {len(img_files)} imgs and {len(msk_files)} masks"

    # 划分
    rng = np.random.default_rng(seed)
    n = len(img_files)
    perm = rng.permutation(n)
    n_val = int(n * val_frac)
    val_idx = set(perm[:n_val].tolist())
    train_idx = set(perm[n_val:].tolist())

    def _subset(idx_set):
        return {
            'images': [img_files[i] for i in sorted(idx_set)],
            'masks':  [msk_files[i] for i in sorted(idx_set)],
            'classes': WATERTANK_CLASSES,
        }

    return {
        'all':   _subset(set(range(n))),
        'train': _subset(train_idx),
        'val':   _subset(val_idx),
    }


def load_quarry_fullsize() -> Dict[str, Dict]:
    """
    加载 quarry-fullsize 子集（10 段连续序列）

    Returns:
        {
          '2016-06-22_113541': {'frames': [List[str]], 'n_frames': int, 'duration_s': float},
          ...
        }
    """
    root = _check_root()
    sub = os.path.join(root, 'quarry-fullsize')
    seqs = sorted([d for d in os.listdir(sub) if os.path.isdir(os.path.join(sub, d))])
    out = {}
    for seq in seqs:
        seq_dir = os.path.join(sub, seq)
        frames = sorted(glob.glob(os.path.join(seq_dir, '*.png')))
        out[seq] = {
            'frames': frames,
            'n_frames': len(frames),
            # 真实帧率未知，按 6 fps 估计
            'duration_s': len(frames) / 6.0,
        }
    return out


def load_turntable_cropped(
    crop: str = 'all',
) -> Dict[str, Dict]:
    """
    加载 turntable-cropped 子集

    文件名分 3 种模式：
      - object-sideways-frame-NNN.png   仅物体
      - platform-sideways-frame-NNN.png 物体+平台（侧视）
      - platform-standing-frame-NNN.png 物体+平台（正视）

    Args:
        crop: 'all'（全部）/ 'object'（仅物体）/ 'platform-sideways' / 'platform-standing'

    Returns:
        {
          'bottle':  {'frames': [List[str]], 'yaw_per_frame_deg': float, ...},
          ...
        }
    """
    root = _check_root()
    sub = os.path.join(root, 'turntable-cropped')

    classes = sorted([d for d in os.listdir(sub) if os.path.isdir(os.path.join(sub, d))])
    out = {}
    for cls in classes:
        cls_dir = os.path.join(sub, cls)
        # 收集所有模式
        info = {'frames_all': [], 'crops': {}}
        for pattern_prefix in ['object-sideways', 'platform-sideways', 'platform-standing']:
            pattern = os.path.join(cls_dir, f'{pattern_prefix}-frame-*.png')
            files = sorted(glob.glob(pattern))
            info['crops'][pattern_prefix] = files
            info['frames_all'].extend(files)
        # 按 crop 选择返回
        if crop == 'all':
            frames = info['frames_all']
        elif crop == 'object':
            frames = info['crops']['object-sideways']
        elif crop == 'platform-sideways':
            frames = info['crops']['platform-sideways']
        elif crop == 'platform-standing':
            frames = info['crops']['platform-standing']
        else:
            raise ValueError(f"crop must be 'all'/'object'/'platform-sideways'/'platform-standing', got {crop}")
        # 提取 frame number
        ns = [int(os.path.basename(f).split('-')[-1].split('.')[0]) for f in frames]
        n = len(frames)
        yaw_per_frame_deg = 360.0 / n if n > 0 else 0.0
        out[cls] = {
            'frames': frames,
            'frame_indices': ns,
            'n_frames': n,
            'yaw_per_frame_deg': yaw_per_frame_deg,
            'crop': crop,
            'crops_breakdown': {k: len(v) for k, v in info['crops'].items()},
        }
    return out


def load_watertank_cropped() -> Dict[str, List[str]]:
    """
    加载 watertank-cropped 子集（2,364 patch）

    Returns:
        {class_name: [list of patch paths]}
    """
    root = _check_root()
    sub = os.path.join(root, 'watertank-cropped')
    classes = sorted([d for d in os.listdir(sub) if os.path.isdir(os.path.join(sub, d))])
    out = {}
    for cls in classes:
        cls_dir = os.path.join(sub, cls)
        out[cls] = sorted(glob.glob(os.path.join(cls_dir, '*.png')))
    return out


def inventory() -> Dict:
    """打印/返回所有子集的简要盘点"""
    root = _check_root()
    out = {
        'real_data_root': root,
        'subsets': {},
    }
    # watertank-segmentation
    try:
        w = load_watertank_segmentation()
        out['subsets']['watertank-segmentation'] = {
            'n_images': len(w['all']['images']),
            'n_classes': len(w['all']['classes']),
            'classes': w['all']['classes'],
        }
    except Exception as e:
        out['subsets']['watertank-segmentation'] = {'error': str(e)}
    # quarry-fullsize
    try:
        q = load_quarry_fullsize()
        seq_info = {k: {'n_frames': v['n_frames']} for k, v in q.items()}
        out['subsets']['quarry-fullsize'] = {
            'n_sequences': len(q),
            'n_frames_total': sum(v['n_frames'] for v in q.values()),
            'sequences': seq_info,
        }
    except Exception as e:
        out['subsets']['quarry-fullsize'] = {'error': str(e)}
    # turntable-cropped
    try:
        t = load_turntable_cropped()
        out['subsets']['turntable-cropped'] = {
            'n_classes': len(t),
            'n_frames_total': sum(v['n_frames'] for v in t.values()),
            'classes': list(t.keys()),
        }
    except Exception as e:
        out['subsets']['turntable-cropped'] = {'error': str(e)}
    # watertank-cropped
    try:
        wc = load_watertank_cropped()
        out['subsets']['watertank-cropped'] = {
            'n_classes': len(wc),
            'n_patches_total': sum(len(v) for v in wc.values()),
        }
    except Exception as e:
        out['subsets']['watertank-cropped'] = {'error': str(e)}
    return out


if __name__ == '__main__':
    import sys
    inv = inventory()
    print(json.dumps(inv, indent=2, ensure_ascii=False))
