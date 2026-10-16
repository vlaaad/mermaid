"""Exercise 3D thrust, mouse steering, deep floor contact and depth lighting."""
import argparse,json,sys
from dataclasses import asdict
from pathlib import Path
import numpy as np
from PIL import Image
from world_geometry import triangles
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'automation-bridge-python'))
from automation_bridge import editor
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('output',type=Path)
p.add_argument('--keep-running',action='store_true')
p.add_argument('--attach',action='store_true')
args=p.parse_args();args.output.mkdir(parents=True,exist_ok=True)
project=editor.open_project(ROOT,start_if_needed=False)
g=project.connect_engine() if args.attach else project.build_and_run(focus=False,timeout=180)
def v(x,y,z):return dict(x=x,y=y,z=z)
def settle():
 g.wait_frames(12);return dict(g.state('mermaid').value)
def pose(data):
 g.command('mermaid.capture',data);return settle()
def shot(name):
 path=args.output/(name+'.png');path.write_bytes(g.screenshot(after_frames=2).read_bytes())
 return np.asarray(Image.open(path).convert('RGB'))
results={}
try:
 g.wait_for_state('mermaid.ready',True,timeout=45)
 # Resize requests are logical on this desktop; assert the actual framebuffer.
 g.resize(1280,720);g.wait_frames(15)
 g.resize(2560,1440);g.wait_frames(15)
 results['screen']=g.screen()
 assert all(results['screen']['backbuffer'][k]==v for k,v in dict(width=1280,height=720).items()),results['screen']
 pose({});shot('opening')
 for name,pitch in [('climb',1.1),('dive',-1.1)]:
  start=pose(dict(position=v(-35,20,50),pitch=pitch))
  receipt=g.key('W',hold=10,modifiers='LSHIFT',wait='started',timeout=10)
  g.wait_frames(12);moving=dict(g.state('mermaid').value);shot(name)
  g.input.cancel(receipt['input_id'],release=True)
  end=settle();results[name]=dict(start=start,moving=moving,end=end)
  delta=end['position']['y']-start['position']['y']
  assert delta*(1 if pitch>0 else -1)>3,(name,start,end)
  assert (moving['tilt']> -1 if pitch>0 else moving['tilt']< -1.8),('Character does not pitch toward thrust',moving)
 # A real mouse drag enters continuous steering. Releasing the mouse button
 # keeps steering active; Escape must release it again.
 start=pose({});screen=g.screen()['window'];w,h=screen['width'],screen['height']
 g.drag((w*.45,h*.5),(w*.65,h*.68),duration=.4)
 end=settle();results['mouse']=dict(start=start,end=end)
 assert abs(end['yaw']-start['yaw'])>.2 and abs(end['pitch']-start['pitch'])>.2,(start,end)
 assert end['steering'],'Click did not enable mouse steering'
 g.key('TAB',wait='released');assert not settle()['steering'],'Tab did not release the mouse'
 # Probe the actual exported triangle centroids, not a second copy of the
 # bathymetry formula, against the native collision module.
 tri=triangles(ROOT/'assets/generated/seabed.glb');centers=tri.mean(axis=1)
 valid=np.flatnonzero((abs(centers[:,0])<125)&(centers[:,2]>-180)&(centers[:,2]<80))
 errors=[]
 for index in valid[np.linspace(0,len(valid)-1,35,dtype=int)]:
  x,y,z=centers[index]
  sample=g.command('mermaid.floor',dict(x=float(x),z=float(z)))['result']
  errors.append(abs(sample['height']-y))
 results['floor_max_error_m']=float(max(errors));assert max(errors)<.0001,errors
 start=pose(dict(position=v(3,-70,65),pitch=-1.3))
 g.key('W',hold=2.7,modifiers='LSHIFT',wait='released',timeout=15)
 end=settle();results['deep_contact']=dict(start=start,end=end)
 floor=g.command('mermaid.floor',dict(x=end['position']['x'],z=end['position']['z']))['result']['height']
 assert floor+.4<end['position']['y']< -74,('Did not reach or respect the lower floor',floor,end)
 shot('deep-contact')
 brightness=[]
 for y in (4,-28,-70):
  pose(dict(position=v(-35,y,64),camera=v(-35,y+2,69),look=v(-35,y+2,100)))
  a=shot('water-'+str(y));patch=a[200:420,200:1080].astype(float)
  brightness.append(float((patch@np.array([.2126,.7152,.0722])).mean()))
 results['water_luminance']=brightness
 assert brightness[0]>brightness[1]*1.25 and brightness[1]>brightness[2]*1.25,brightness
 for name,data in {
  'ledge':dict(position=v(4,-10,28),camera=v(15,-11,24),look=v(2,-30,36)),
  'deep-ruins':dict(position=v(8,-70,73),camera=v(15,-68,77),look=v(3,-74,64)),
  'look-up':dict(position=v(3,-65,66),camera=v(3,-62,68),look=v(16,50,0)),
 }.items():pose(data);shot(name)
 pose({})
 profile=g.profiler.capture(frames=120,warmup_frames=30,thread='Main',timeout=45)
 results['frame_ms']=[asdict(x) for x in profile.scopes(name='Frame')]
 results['draw_calls']=[asdict(x) for x in profile.counters(contains='DrawCalls')]
 (args.output/'results.json').write_text(json.dumps(results,indent=2)+'\n')
 print(json.dumps({k:results[k] for k in ('floor_max_error_m','water_luminance','frame_ms','draw_calls')},indent=2),flush=True)
finally:
 g.input.flush(release=True)
 g.command('mermaid.lighting',dict(mode=0));g.command('mermaid.capture',{})
 if args.keep_running:g.command('mermaid.resume',{});g.close()
 else:g.close_engine()
