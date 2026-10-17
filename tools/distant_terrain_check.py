"""Capture distant basin silhouettes from opening, side and deep-water views."""
import argparse,json,sys
from pathlib import Path
from dataclasses import asdict
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'automation-bridge-python'))
from automation_bridge import editor
p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path);p.add_argument('--attach',action='store_true');p.add_argument('--no-profile',action='store_true');p.add_argument('--profile-only',action='store_true');args=p.parse_args();args.output.mkdir(parents=True,exist_ok=True)
manifest=json.loads((ROOT/'assets/generated/manifest.json').read_text())
assert manifest['seabed']['vertices']<=65535,'Seabed would be rejected by the browser graphics backend'
project=editor.open_project(ROOT,start_if_needed=False);g=project.connect_engine() if args.attach else project.build_and_run(focus=False,timeout=180)
v=lambda x,y,z:dict(x=x,y=y,z=z)
views={
 'opening':{},
 'west':dict(camera=v(-25,8,12),look=v(-194,5,-40)),
 'east':dict(camera=v(40,10,0),look=v(202,5,-104)),
 'south':dict(camera=v(-.4,7,13),look=v(-20,-8,155)),
 'north':dict(camera=v(0,12,-80),look=v(-30,0,-242)),
 'deep-south':dict(position=v(18,-65,80),camera=v(18,-61,80),look=v(-50,-20,155)),
 'deep-west':dict(position=v(18,-65,80),camera=v(18,-61,80),look=v(-175,-5,-20)),
}
results={}
try:
 g.wait_for_state('mermaid.ready',True,timeout=60);g.resize(1280,720);g.wait_frames(12,timeout=30);g.resize(2560,1440);g.wait_frames(12,timeout=30)
 g.command('mermaid.capture',{});g.wait_frames(10,timeout=20);g.screenshot(after_frames=2)
 for name,data in ({} if args.profile_only else views).items():
  g.command('mermaid.capture',data);g.wait_frames(12,timeout=25)
  (args.output/(name+'.png')).write_bytes(g.screenshot(after_frames=3).read_bytes());print('Captured',name,flush=True)
 if not args.no_profile:
  g.command('mermaid.capture',{});g.key('W',hold=20,wait='started');g.wait_frames(15,timeout=25)
  results['keyboard_swim_speed']=g.state('mermaid').value['speed'];assert results['keyboard_swim_speed']>1
  g.input.flush(release=True)
  g.command('mermaid.capture',{});g.command('mermaid.resume',{})
  r=g.profiler.capture(frames=120,warmup_frames=20,thread='Main',timeout=90)
  results['frame_ms']=[asdict(x) for x in r.scopes(name='Frame')];results['draw_calls']=[asdict(x) for x in r.counters(contains='DrawCalls')]
 results['issues']=[l for l in project.console.read().lines if l.startswith('ERROR:') or l.startswith('WARNING:')];assert not results['issues'],results['issues']
finally:
 g.command('mermaid.capture',{});g.command('mermaid.resume',{});g.close()
 (args.output/'results.json').write_text(json.dumps(results,indent=2)+'\n')
print(json.dumps(results,indent=2),flush=True)
