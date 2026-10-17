"""Native behavioral checks: actual bone poses, crowd collision, touch and wake."""
import argparse,json,sys
from pathlib import Path
from dataclasses import asdict
import numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'automation-bridge-python'))
from automation_bridge import editor
p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path);p.add_argument('--attach',action='store_true');args=p.parse_args();args.output.mkdir(parents=True,exist_ok=True)
project=editor.open_project(ROOT,start_if_needed=False);g=project.connect_engine() if args.attach else project.build_and_run(focus=False,timeout=180)
def v(x,y,z):return dict(x=x,y=y,z=z)
def wait(n):g.wait_frames(n,timeout=max(10,n*.5))
def state():return dict(g.state('mermaid').value)
def life():return g.command('mermaid.life',{},timeout=20)['result']
def shot(name):
 path=args.output/(name+'.png');path.write_bytes(g.screenshot(after_frames=2).read_bytes());return np.asarray(Image.open(path).convert('RGB'))
def pose(data):g.command('mermaid.capture',data);wait(8)
results={}
try:
 g.wait_for_state('mermaid.ready',True,timeout=45)
 g.resize(1280,720);wait(12);g.resize(2560,1440);wait(12)
 pose({});a=shot('opening');wait(5);b=shot('opening-repeat')
 results['frozen_pixels_changed']=int(np.any(a!=b,axis=2).sum());assert np.array_equal(a,b),'Frozen scene changes'
 results['initial']=life()
 g.command('mermaid.resume',{});wait(85);results['live']=life();results['drift']=state();shot('living-reef')
 assert results['live']['steps']>30 and results['live']['mean_fish_travel']>.5
 assert results['live']['maximum_fish_penetration']<.025,results['live']['maximum_fish_penetration']
 assert results['live']['maximum_bend']>.02
 assert results['live']['active_bubbles']>0
 # A free-water thrust fixture isolates the real swim clip from collisions.
 pose(dict(position=v(-35,16,45),pitch=.1));g.key('W',hold=20,wait='started');wait(16)
 results['stroke_a']=life();results['swim_a']=state();shot('stroke-a')
 samples=[]
 for _ in range(5):
  wait(2);samples.append(life())
 results['stroke_samples']=samples;results['stroke_b']=samples[-1];results['swim_b']=state();shot('stroke-b');g.input.flush(release=True)
 assert results['stroke_b']['clip']=='swim' and results['stroke_b']['wake_emitted']>0
 # Compare the fin relative to the peduncle across several phases; translation
 # and rigid steering cannot satisfy this, and a full-cycle alias cannot hide it.
 def relative(s):
  a=s['bones']['fin_left'];b=s['bones']['peduncle'];return np.array([a[k]-b[k] for k in 'xyz'])
 vectors=[relative(s) for s in samples]
 results['fin_relative_motion_m']=float(max(np.linalg.norm(a-b) for a in vectors for b in vectors))
 assert results['fin_relative_motion_m']>.05,results['fin_relative_motion_m']
 # Frozen close side views exercise the full real swim rig at known phases.
 for name,time in [('upstroke',.35),('downstroke',1.25)]:
  pose(dict(position=v(-35,16,45),swim_speed=4.4,time=time,pitch=.1,camera=v(-29,16,47),look=v(-35,16,45)))
  shot(name)
 # Place the character beside rooted foreground kelp, then let its spring react.
 plant=next(p for p in results['initial']['near_plants'] if p['id'].endswith('1397'))
 pose(dict(position=v(plant['x']+.65,plant['y']+plant['height']*.5,plant['z']),camera=v(-4,5,7),look=v(-9,5,0)))
 g.command('mermaid.resume',{});wait(40);results['contact']=life();shot('plant-contact')
 assert results['contact']['contacts']>0,'Plant does not respond to the player'
 # View each added deep landmark from within swimming reach.
 for name,data in {
  'avenue':dict(position=v(-19,-22,38),camera=v(-8,-19,42),look=v(-20,-26,33)),
  'sanctuary':dict(position=v(23,-72,77),camera=v(35,-70,81),look=v(24,-79,68)),
  'gateway':dict(position=v(-22,-73,77),camera=v(-12,-70,81),look=v(-23,-77,70)),
  'pottery':dict(position=v(24,-80,72),camera=v(28,-80,72),look=v(24,-83,68)),
 }.items():pose(data);shot('deep-'+name)
 pose({});g.command('mermaid.resume',{});wait(10)
 profile=g.profiler.capture(frames=90,warmup_frames=10,thread='Main',timeout=90)
 results['profile']=[asdict(x) for x in profile.scopes(name='Frame')];results['draw_calls']=[asdict(x) for x in profile.counters(contains='DrawCalls')]
 errors=[l for l in project.console.read().lines if l.startswith('ERROR:') or 'WARNING:GRAPHICS' in l]
 results['errors']=errors;assert not errors,errors
finally:
 g.input.flush(release=True);g.command('mermaid.capture',{});g.command('mermaid.resume',{});g.close()
 (args.output/'results.json').write_text(json.dumps(results,indent=2)+'\n')
print(json.dumps({k:v for k,v in results.items() if k not in ['initial','live','stroke_a','stroke_b','contact']},indent=2),flush=True)
