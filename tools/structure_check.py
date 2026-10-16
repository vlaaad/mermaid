"""Audit visible architectural geometry independently of blue water/color similarity.

Input is mermaid.lighting mode5, rendered with normal depth/occlusion. White means
column/arch/window geometry; everything else is black. Coarse hand-marked boxes
are presence checks, not proof of matching shape, detail, or overall similarity.
"""
import json
from pathlib import Path
import numpy as np
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]


def audit(mask_image, targets=None):
    rgb=np.asarray(mask_image.convert('RGB'),dtype=np.int16)
    if (np.max(rgb,axis=2)-np.min(rgb,axis=2)>2).mean()>.01:
        raise ValueError('Expected the grayscale architecture mask from lighting mode5, not the normal color capture')
    mask=rgb.mean(axis=2)>127
    targets=targets if targets is not None else json.loads((ROOT/'tools/reference_structure.json').read_text())
    checks={}
    for name,target in targets.items():
        x,y,w,h=target['box']
        region=mask[round(y*mask.shape[0]):round((y+h)*mask.shape[0]),round(x*mask.shape[1]):round((x+w)*mask.shape[1])]
        rows=float(region.any(axis=1).mean())
        area=float(region.mean())
        checks[name]={'box':target['box'],'visible_rows_percent':rows*100,'visible_area_percent':area*100,
                      'present':bool(rows>=target['min_row_coverage'] and area>=.08)}
    return {'protocol':'white architecture geometry with normal depth occlusion; no fog or color grading',
            'limitation':'Coarse presence/vertical-span audit. Neighboring masonry can overlap a box; inspect actual geometry and silhouettes too.',
            'all_required_present':all(v['present'] for v in checks.values()),
            'missing_or_occluded':[k for k,v in checks.items() if not v['present']], 'checks':checks}
