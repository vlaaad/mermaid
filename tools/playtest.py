"""Exercise the actual controller, deterministic capture fixture, and native profiler."""
from dataclasses import asdict
import argparse
import json
import math
from pathlib import Path
import sys
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'automation-bridge-python'))
from automation_bridge import editor
from image_diff import load_rgb


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--attach',action='store_true',help='Reuse the current native build')
    args=parser.parse_args()
    out=ROOT/'artifacts/scene'
    out.mkdir(parents=True,exist_ok=True)
    p=editor.open_project(ROOT,start_if_needed=False)
    capabilities=['application.commands','application.state','input.key>=2','input.drag','screenshot']
    g=p.connect_engine(required_capabilities=capabilities) if args.attach else p.build_and_run(focus=True,timeout=180,required_capabilities=capabilities)
    g.wait_for_state('mermaid.ready',True,timeout=45)
    g.wait_frames(60)
    results={'screen':g.screen()}
    def ready():
        g.wait_frames(15)
        return dict(g.state('mermaid').value)
    def reset():
        g.command('mermaid.capture',{})
        return ready()
    def distance(a,b):
        return math.sqrt(sum((a['position'][axis]-b['position'][axis])**2 for axis in ['x','y','z']))
    try:
        reset()
        a=g.screenshot(after_frames=2)
        (out/'opening.png').write_bytes(a.read_bytes())
        g.wait_frames(10)
        b=g.screenshot(after_frames=2)
        identical=np.array_equal(np.asarray(load_rgb(a.path)),np.asarray(load_rgb(b.path)))
        assert identical, 'Frozen opening frame changed between captures'
        results['capture_repeat']={'pixel_identical':bool(identical)}

        start=reset()
        g.key('W',hold=1.0,wait='released',timeout=10)
        end=ready()
        normal=distance(start,end)
        assert end['position']['z']<start['position']['z']-1, (start,end)
        results['forward']={'meters':normal,'state':end}
        (out/'swimming.png').write_bytes(g.screenshot().read_bytes())

        start=reset()
        g.key('W',hold=1.0,modifiers='LSHIFT',wait='released',timeout=10)
        end=ready()
        boosted=distance(start,end)
        assert boosted>normal*1.4, (normal,boosted)
        results['boost']={'meters':boosted,'ratio':boosted/normal}

        start=reset()
        g.key('SPACE',hold=.7,wait='released',timeout=10)
        end=ready()
        assert end['position']['y']>start['position']['y']+1, (start,end)
        results['rise_meters']=end['position']['y']-start['position']['y']

        start=reset()
        screen=g.screen()['window']
        g.drag((screen['width']*.45,screen['height']*.5),(screen['width']*.65,screen['height']*.55),duration=.35)
        end=ready()
        assert abs(end['yaw']-start['yaw'])>.15, (start,end)
        results['orbit_radians']=end['yaw']-start['yaw']
        (out/'orbit.png').write_bytes(g.screenshot().read_bytes())

        reset()
        profile=g.profiler.capture(frames=180,warmup_frames=30,thread='Main',timeout=45)
        results['profile']={'scopes':[asdict(x) for x in profile.scopes()],'counters':[asdict(x) for x in profile.counters()]}
        (out/'playtest.json').write_text(json.dumps(results,indent=2)+'\n')
        print(json.dumps({k:v for k,v in results.items() if k!='profile'},indent=2))
        print('Frame scopes:',[(r.path,r.total.avg_ms,r.total.p95_ms) for r in profile.scopes(name='Frame')])
        print('Draw calls:',[(r.path,r.values.max) for r in profile.counters(contains='DrawCalls')])
    finally:
        g.close()


if __name__=='__main__':main()
