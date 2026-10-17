"""Check depth from above, real upper-body motion, glide, and crowd spacing."""
import argparse,json,sys
from dataclasses import asdict
from pathlib import Path
import numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'automation-bridge-python'))
from automation_bridge import editor
p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path);p.add_argument('--attach',action='store_true');args=p.parse_args();args.output.mkdir(parents=True,exist_ok=True)
project=editor.open_project(ROOT,start_if_needed=False)
g=project.connect_engine() if args.attach else project.build_and_run(focus=False,timeout=180)
v=lambda x,y,z:dict(x=x,y=y,z=z)
def wait(n):g.wait_frames(n,timeout=max(15,n*.7))
def state():return dict(g.state('mermaid').value)
def life():return g.command('mermaid.life',{},timeout=20)['result']
def pose(data):
 g.command('mermaid.capture',data);wait(15)
 if 'camera' in data:
  assert all(abs(state()['camera'][k]-data['camera'][k])<.001 for k in 'xyz'),state()
def shot(name):
 path=args.output/(name+'.png');path.write_bytes(g.screenshot(after_frames=3).read_bytes())
 return np.asarray(Image.open(path).convert('RGB'))
def relative(s,a,b):return np.array([s['bones'][a][k]-s['bones'][b][k] for k in 'xyz'])
results={}
try:
 g.wait_for_state('mermaid.ready',True,timeout=60)
 g.resize(1280,720);wait(12);g.resize(2560,1440);wait(12)
 # Warm the capture path before measuring fixed views.
 pose({});shot('opening-warmup')
 luminance=[]
 for name,y in [('above',7),('middle',-28),('deep',-70)]:
  pose(dict(position=v(23,y-2,76),camera=v(35,y,81),look=v(24,-79,68)))
  a=shot('basin-'+name);patch=a[100:260,1000:1200].astype(float)
  luminance.append(float((patch@np.array([.2126,.7152,.0722])).mean()))
 print('Depth views captured',flush=True)
 results['basin_luminance']=luminance
 assert luminance[0]<65 and luminance[0]>luminance[1]>luminance[2],luminance
 pose(dict(position=v(3,-65,66),camera=v(3,-62,68),look=v(16,50,0)))
 a=shot('look-up');results['sun_bright_pixels']=int((a.min(axis=2)>180).sum());assert results['sun_bright_pixels']>200
 samples=[]
 for i,t in enumerate([0,.3,.6,.9,1.2,1.5]):
  pose(dict(position=v(-35,16,45),swim_speed=4.4,time=t,pitch=.1,camera=v(-29,16,47),look=v(-35,16,45)))
  samples.append(life())
  if i in (1,4):shot('stroke-'+str(i))
 results['stroke_samples']=samples;motion={}
 for a,b,minimum in [('wrist_left','elbow_left',.12),('wrist_right','elbow_right',.12),('hair_tip','head',.30),('fin_left','peduncle',.15)]:
  vectors=[relative(s,a,b) for s in samples];motion[a]=float(max(np.linalg.norm(a-b) for a in vectors for b in vectors))
  assert motion[a]>minimum,(a,motion)
 results['relative_motion_m']=motion
 print('Joint motion',motion,flush=True)
 # Visible/depth/shadow poses must still use exactly the same skinning path.
 silhouettes=[]
 for t in (.35,1.25):
  pose(dict(position=v(-35,16,45),swim_speed=4.4,time=t,pitch=.1,camera=v(-29,16,47),look=v(-35,16,45)))
  masks=[]
  for mode in (10,11):
   g.command('mermaid.lighting',dict(mode=mode));wait(5);a=shot('mask-'+str(t)+'-'+str(mode));masks.append(a.mean(axis=2)>128)
  overlap=float((masks[0]&masks[1]).sum()/max(1,(masks[0]|masks[1]).sum()));silhouettes.append(overlap);assert overlap>.995,overlap
 g.command('mermaid.lighting',dict(mode=0));results['silhouette_overlap']=silhouettes
 pose(dict(position=v(-35,16,45),pitch=.1));g.key('W',hold=20,wait='started');wait(25)
 moving=state();assert moving['speed']>4
 g.input.flush(release=True)
 glide=[]
 for _ in range(10):
  wait(3);glide.append(dict(state=state(),clip=life()['clip']))
 results['coast']=glide
 print('Glide transition checked',flush=True)
 assert any(s['clip']=='glide' for s in glide),glide
 results['coast_distance_m']=float(np.linalg.norm(np.array([glide[-1]['state']['position'][k]-moving['position'][k] for k in 'xyz'])))
 assert results['coast_distance_m']>.8
 pose({});g.command('mermaid.resume',{});spacing=[]
 for _ in range(3):
  wait(100);s=life();spacing.append({k:s[k] for k in ['minimum_fish_gap','fish_overlaps','nearest_fish_p10','nearest_fish_median','maximum_fish_penetration']})
  assert s['minimum_fish_gap']>.20 and s['fish_overlaps']==0 and s['nearest_fish_p10']>1.0,s
  assert s['maximum_fish_penetration']<.025,s
 results['crowd_spacing']=spacing;shot('school-spacing')
 print('Crowd spacing',spacing,flush=True)
 pose({});g.command('mermaid.resume',{})
 profile=g.profiler.capture(frames=120,warmup_frames=20,thread='Main',timeout=90)
 results['live_frame_ms']=[asdict(x) for x in profile.scopes(name='Frame')]
 results['draw_calls']=[asdict(x) for x in profile.counters(contains='DrawCalls')]
 pose({})
 profile=g.profiler.capture(frames=90,warmup_frames=20,thread='Main',timeout=90)
 results['frozen_frame_ms']=[asdict(x) for x in profile.scopes(name='Frame')]
 errors=[l for l in project.console.read().lines if l.startswith('ERROR:') or 'WARNING:GRAPHICS' in l]
 results['errors']=errors;assert not errors,errors
finally:
 g.input.flush(release=True);g.command('mermaid.lighting',dict(mode=0));g.command('mermaid.capture',{});g.command('mermaid.resume',{});g.close()
 (args.output/'results.json').write_text(json.dumps(results,indent=2)+'\n')
print(json.dumps({k:v for k,v in results.items() if k not in ['stroke_samples','coast']},indent=2),flush=True)
