"""Capture fixed close views and probe swimming into a large rendered boulder."""
import argparse
from dataclasses import asdict
import sys,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'automation-bridge-python'))
from automation_bridge import editor
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('output',type=Path,nargs='?',default=ROOT/'artifacts/close-detail/final')
parser.add_argument('--profile',action='store_true')
parser.add_argument('--keep-running',action='store_true')
args=parser.parse_args()
success=False
p=editor.open_project(ROOT,start_if_needed=False)
g=p.build_and_run(focus=True,timeout=180)
out=args.output
out.mkdir(parents=True,exist_ok=True)
def v(x,y,z):return dict(x=x,y=y,z=z)
views={
 'fin-rear':dict(camera=v(-.5,4.9,9),look=v(-1,4.4,4)),
 'fin-side':dict(camera=v(3.6,4.7,4.5),look=v(-1,4.5,4)),
 'sun':dict(camera=v(-.4,7,13),look=v(16,50,0)),
 'sand':dict(position=v(0,-1,-10),camera=v(3,2,-3),look=v(0,-3,-13)),
}
try:
 g.wait_for_state('mermaid.ready',True,timeout=45)
 for name,data in views.items():
  g.command('mermaid.capture',data);g.wait_frames(5)
  (out/(name+'.png')).write_bytes(g.screenshot(after_frames=2).read_bytes())
 # Try boosting straight through the broad face of a large foreground boulder.
 hulls=json.loads((ROOT/'main/obstacles.lua').read_text().removeprefix('return ').replace('{','[').replace('}',']'))
 hulls=[h for h in hulls if len(h)==7]
 g.command('mermaid.capture',dict(position=v(-11,1.5,-12)))
 g.wait_frames(5)
 samples=[]
 for _ in range(5):
  g.key('W',hold=.40,modifiers='LSHIFT',wait='released',timeout=10)
  s=dict(g.state('mermaid').value);point=s['position'];samples.append(s)
  for h in hulls:
   if all(abs(point[axis]-h[i])<h[i+3] for i,axis in enumerate(['x','y','z'])):
    distances=[sum(point[axis]*plane[i] for i,axis in enumerate(['x','y','z']))-plane[3] for plane in h[6]]
    assert max(distances)>-.02, ('Player crossed into rendered stone',s)
 (out/'boulder-contact.png').write_bytes(g.screenshot(after_frames=2).read_bytes())
 (out/'collision-probe.json').write_text(json.dumps(samples,indent=2)+'\n')
 assert samples[-1]['position']['z']>-19 or samples[-1]['position']['y']>3.5, 'Swam through the boulder face'
 g.command('mermaid.capture',{})
 (out/'opening.png').write_bytes(g.screenshot(after_frames=5).read_bytes())
 if args.profile:
  profile=g.profiler.capture(frames=120,warmup_frames=30,thread='Main',timeout=45)
  details={'scopes':[asdict(x) for x in profile.scopes()],'counters':[asdict(x) for x in profile.counters()]}
  (out/'profile.json').write_text(json.dumps(details,indent=2)+'\n')
  print('Frame ms:',[(x.total.avg_ms,x.total.p95_ms) for x in profile.scopes(name='Frame')],flush=True)
  print('Draws:',[x.values.max for x in profile.counters(contains='DrawCalls')],flush=True)
 if args.keep_running:g.command('mermaid.resume',{})
 success=True
 print('Close views captured; boosted boulder contact passed.',flush=True)
finally:
 if args.keep_running and success:g.close()
 else:g.close_engine()
