"""Fit persisted game camera/light settings using actual frozen engine renders.

No candidate image edits, reference sampling in shaders, alignment, or changed metric.
Every accepted setting applies to the whole moving game; final comparison stays independent.
"""
import argparse
import copy
import json
from pathlib import Path
import sys

import numpy as np
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'automation-bridge-python'))
from automation_bridge import editor


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--rounds',type=int,default=2)
    p.add_argument('--output',type=Path,default=ROOT/'artifacts/art-fit')
    p.add_argument('--camera-only',action='store_true')
    args=p.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    reference=np.asarray(Image.open(ROOT/'Blonde-Mermaid-in-Atlantis-Ruins.png').convert('RGB').resize((960,540),Image.Resampling.LANCZOS),dtype=float)
    settings=json.loads((ROOT/'assets/art.json').read_text())
    client=editor.open_project(ROOT,start_if_needed=False)
    g=client.connect_engine()
    rows=[]
    count=0
    def evaluate(candidate,label):
        nonlocal count
        g.command('mermaid.art',candidate)
        g.wait_frames(3)
        shot=g.screenshot(after_frames=2)
        raw=shot.read_bytes()
        image=Image.open(shot.path).convert('RGB').resize((960,540),Image.Resampling.LANCZOS)
        delta=np.abs(np.asarray(image,dtype=float)-reference)/255*100
        mae=float(delta.mean())
        character=float(delta[248:486,326:538].mean())
        ruin=float(delta[0:297,528:826].mean())
        score=mae+character*.10+ruin*.05
        rows.append({'candidate':count,'label':label,'mae_percent':mae,'character_mae':character,'ruin_mae':ruin,'score':score})
        count+=1
        return score,mae,raw
    fields=[('eye_right',None,.18,-.3,1.5),('eye_height',None,.20,.6,2.2),('look_height',None,.20,.5,2.2),('player_scale',None,.04,.60,.90),('player_tilt',None,.10,-.8,-.25)]
    if not args.camera_only:
        for name in ('fog_top','fog_bottom','ambient_top','ambient_bottom','sun_color'):
            for component in range(3):fields.append((name,component,.07,0,1.4 if name=='sun_color' else 1))
        fields.extend([('fog_density',None,.004,.010,.055),('water_strength',None,.025,.015,.15)])
    try:
        best,best_mae,raw=evaluate(settings,'initial')
        for iteration in range(args.rounds):
            step_scale=.6**iteration
            for name,component,step,lower,upper in fields:
                base=copy.deepcopy(settings)
                value=base[name] if component is None else base[name][component]
                accepted=False
                for direction in [-1,1]:
                    candidate=copy.deepcopy(base)
                    v=max(lower,min(upper,value+direction*step*step_scale))
                    if abs(v-value)<1e-7:continue
                    if component is None:candidate[name]=v
                    else:candidate[name][component]=v
                    score,mae,frame=evaluate(candidate,f'{iteration}:{name}:{component}:{direction}')
                    if score<best-.0005:
                        settings=candidate;best=score;best_mae=mae;raw=frame;accepted=True
                if accepted:
                    (args.output/'best.png').write_bytes(raw)
                    (args.output/'best-settings.json').write_text(json.dumps(settings,indent=2)+'\n')
                    print(f'round {iteration+1} {name}[{component}]: MAE {best_mae:.4f}% objective {best:.4f}',flush=True)
            print(f'round {iteration+1} completed: {count} actual renders',flush=True)
        (ROOT/'assets/art.json').write_text(json.dumps(settings,indent=2)+'\n')
        (args.output/'best.png').write_bytes(raw)
        (args.output/'best-settings.json').write_text(json.dumps(settings,indent=2)+'\n')
        print(f'Persisted settings; measured MAE {best_mae:.4f}%',flush=True)
    finally:
        g.command('mermaid.art',settings)
        g.close()
        (args.output/'trials.json').write_text(json.dumps(rows,indent=2)+'\n')


if __name__=='__main__':main()
