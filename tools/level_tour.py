"""Inspect final ruins supports, deep habitats, surface waves and live schools."""
import argparse,json,sys
from dataclasses import asdict
from pathlib import Path
import numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'automation-bridge-python'))
from automation_bridge import editor
p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path);p.add_argument('--attach',action='store_true');args=p.parse_args();args.output.mkdir(parents=True,exist_ok=True)
project=editor.open_project(ROOT,start_if_needed=False);g=project.connect_engine() if args.attach else project.build_and_run(focus=False,timeout=180)
v=lambda x,y,z:dict(x=x,y=y,z=z)
def wait(n):g.wait_frames(n,timeout=max(15,n*.7))
def pose(data):g.command('mermaid.capture',data);wait(12)
def life():return g.command('mermaid.life',{},timeout=20)['result']
def shot(name):
 path=args.output/(name+'.png');path.write_bytes(g.screenshot(after_frames=3).read_bytes());return np.asarray(Image.open(path).convert('RGB'))
results={}
try:
 g.wait_for_state('mermaid.ready',True,timeout=60);g.resize(1280,720);wait(12);g.resize(2560,1440);wait(12)
 pose({});shot('warmup');pose({});shot('opening')
 views={
  'arcade-support':dict(position=v(23,1,-34),camera=v(17,1,-34),look=v(28,9,-54)),
  'rear-colonnade':dict(position=v(70,20,-20),camera=v(50,24,-45),look=v(40,12,-67)),
  'rear-arch':dict(position=v(-40,12,-65),camera=v(-20,10,-74),look=v(-15,5,-91)),
  'descent-garden':dict(position=v(-17,-35,48),camera=v(-11,-35,51),look=v(-17,-38,42)),
  'ledge-garden':dict(position=v(13,-35,52),camera=v(19,-35,55),look=v(13,-37,46)),
  'deep-gateway':dict(position=v(-24,-76,83),camera=v(-12,-75,88),look=v(-23,-78,73)),
  'deep-sanctuary':dict(position=v(22,-79,87),camera=v(29,-79,88),look=v(22,-81,77)),
  'surface':dict(position=v(0,43,15),camera=v(0,47.2,15),look=v(2,50,-35)),
  'sun-window':dict(position=v(0,30,10),camera=v(0,32,10),look=v(8,50,4)),
 }
 for name,data in views.items():
  pose(dict(data,time=3));a=shot(name+'-3')
  if name in ('surface','sun-window'):
   g.command('mermaid.lighting',dict(mode=1));wait(5);depth3=shot(name+'-depth-3');g.command('mermaid.lighting',dict(mode=0))
   pose(dict(data,time=4.3));b=shot(name+'-4.3');results[name+'_motion_mae']=float(abs(a.astype(float)-b).mean());assert results[name+'_motion_mae']>.15
   # Depth capture exercises the separate MSAA depth pass at the same phases.
   g.command('mermaid.lighting',dict(mode=1));wait(5);depth4=shot(name+'-depth-4.3');g.command('mermaid.lighting',dict(mode=0))
   results[name+'_depth_motion_mae']=float(abs(depth3[:200].astype(float)-depth4[:200]).mean())
   assert results[name+'_depth_motion_mae']>.05,'Surface normals moved but geometry depth did not'
  print('Captured',name,flush=True)
 s=life();results['fish']=s['fish'];results['plants']=s['plants'];assert s['fish']==268 and s['plants']==149,s
 pose(views['deep-sanctuary']);g.command('mermaid.resume',{});samples=[]
 for _ in range(3):
  wait(80);s=life();samples.append({k:s[k] for k in ('minimum_fish_gap','fish_overlaps','nearest_fish_p10','maximum_fish_penetration','mean_fish_travel')})
  assert s['fish_overlaps']==0 and s['minimum_fish_gap']>.2 and s['maximum_fish_penetration']<.025,samples
 results['live_schools']=samples;shot('deep-sanctuary-live');print('Crowd clearance passes',samples,flush=True)
 pose({});g.command('mermaid.resume',{})
 profile=g.profiler.capture(frames=120,warmup_frames=20,thread='Main',timeout=90)
 results['live_frame_ms']=[asdict(x) for x in profile.scopes(name='Frame')];results['draw_calls']=[asdict(x) for x in profile.counters(contains='DrawCalls')]
 errors=[l for l in project.console.read().lines if l.startswith('ERROR:') or 'WARNING:GRAPHICS' in l];results['errors']=errors;assert not errors,errors
finally:
 g.input.flush(release=True);g.command('mermaid.lighting',dict(mode=0));g.command('mermaid.capture',{});g.command('mermaid.resume',{});g.close()
 (args.output/'results.json').write_text(json.dumps(results,indent=2)+'\n')
print(json.dumps(results,indent=2),flush=True)
