"""Native captures and runtime checks for sparse skeletal sea animals."""
import argparse,json,sys,math
from pathlib import Path
from dataclasses import asdict
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
def shot(n):
 path=args.output/(n+'.png');path.write_bytes(g.screenshot(after_frames=3).read_bytes());return np.asarray(Image.open(path).convert('RGB'))
results={}
try:
 g.wait_for_state('mermaid.ready',True,timeout=60);g.resize(1280,720);wait(12);g.resize(2560,1440);wait(12)
 pose({});shot('warmup');pose({});shot('opening');initial=life();results['initial']=initial['large_animals'];assert initial['whales']==3 and initial['drifters']==2
 pose(dict(time=35));shot('opening-later');later=life();results['later']=later['large_animals']
 for a,b in zip(results['initial'],results['later']):assert math.dist([a[k] for k in 'xyz'],[b[k] for k in 'xyz'])>5,(a,b)
 print('All five animals move along their routes',flush=True)
 views={
  'ray':dict(position=v(-30,16,-10),camera=v(-15,22,-15),look=v(-15,18,-24)),
  'whale-detail':dict(position=v(-40,25,-90),camera=v(-30,42,-92),look=v(-30,38,-133)),
  'whale-distant-right':dict(position=v(20,15,5),camera=v(25,9,13),look=v(62,28,-144)),
  'deep-silhouette':dict(position=v(20,-65,75),camera=v(18,-61,80),look=v(-72,-37,62)),
 }
 overlaps=[]
 for name,data in views.items():
  for t in (3,4.8):
   pose(dict(data,time=t));shot(name+'-'+str(t))
   if name in ('ray','whale-detail'):
    masks=[]
    for mode in (10,11):
     g.command('mermaid.lighting',dict(mode=mode));wait(5);a=shot(name+'-'+str(t)+'-pass-'+str(mode));masks.append(a.mean(axis=2)>128)
    assert masks[0].sum()>1000,(name,t)
    overlap=float((masks[0]&masks[1]).sum()/max(1,(masks[0]|masks[1]).sum()));overlaps.append(overlap);assert overlap>.995,(name,t,overlap)
    g.command('mermaid.lighting',dict(mode=0))
 results['silhouette_overlap']=overlaps;print('Visible/shadow poses match',overlaps,flush=True)
 pose({});g.command('mermaid.resume',{});wait(100);live=life();results['live']=live['large_animals']
 assert all(0<=a['cursor']<=1 for a in results['live'])
 shot('living-opening')
 profile=g.profiler.capture(frames=120,warmup_frames=20,thread='Main',timeout=90)
 results['live_frame_ms']=[asdict(x) for x in profile.scopes(name='Frame')];results['draw_calls']=[asdict(x) for x in profile.counters(contains='DrawCalls')]
 errors=[l for l in project.console.read().lines if l.startswith('ERROR:') or 'WARNING:GRAPHICS' in l];results['errors']=errors;assert not errors,errors
finally:
 g.input.flush(release=True);g.command('mermaid.lighting',dict(mode=0));g.command('mermaid.capture',{});g.command('mermaid.resume',{});g.close()
 (args.output/'results.json').write_text(json.dumps(results,indent=2)+'\n')
print(json.dumps({k:v for k,v in results.items() if k not in ['initial','later','live']},indent=2),flush=True)
