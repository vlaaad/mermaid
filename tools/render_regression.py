"""Verify rigid plants, fish and rays match their shadow geometry and near/far ground shadows agree."""
import argparse,json,sys
from pathlib import Path
import numpy as np
from PIL import Image
from world_geometry import triangles
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'automation-bridge-python'))
from automation_bridge import editor
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('output',type=Path)
p.add_argument('--baseline',action='store_true')
p.add_argument('--keep-running',action='store_true')
args=p.parse_args();args.output.mkdir(parents=True,exist_ok=True)
project=editor.open_project(ROOT,start_if_needed=False)
g=project.build_and_run(focus=False,timeout=180)
def v(x,y,z):return dict(x=x,y=y,z=z)
def capture(name,pose,mode=0):
 g.command('mermaid.capture',pose);g.command('mermaid.lighting',dict(mode=mode));g.wait_frames(5)
 path=args.output/(name+'.png');path.write_bytes(g.screenshot(after_frames=2).read_bytes())
 return np.asarray(Image.open(path).convert('RGB'))
try:
 g.wait_for_state('mermaid.ready',True,timeout=45)
 masks={};results={}
 column=triangles(ROOT/'assets/generated/column.glb')
 _,vertices=np.unique(column.reshape(-1,3),axis=0,return_inverse=True)
 vertices=vertices.reshape(-1,3)
 edges=np.sort(np.concatenate([vertices[:,[0,1]],vertices[:,[1,2]],vertices[:,[2,0]]]),axis=1)
 _,counts=np.unique(edges,axis=0,return_counts=True)
 results['column_triangles']=len(column)
 results['column_open_edges']=int((counts==1).sum())
 for time in (3,7):
  pose=dict(camera=v(-6,5,4),look=v(-9,5,0),time=time)
  capture(f'actors-{time}',pose)
  for mode in (10,11):masks[time,mode]=capture(f'actors-{time}-pass-{mode}',pose,mode)[...,0]>128
 for time in (3,7):
  a,b=masks[time,10],masks[time,11]
  assert a.sum()>1000 and b.sum()>1000,'Actor fixture is empty'
  results[f'pass_overlap_time_{time}']=float((a&b).sum()/(a|b).sum())
 a,b=masks[3,10],masks[7,10]
 results['visible_actor_pixels_moved']=int((a!=b).sum())
 for mode in (0,6,7,8,9,12):
  capture(f'boundary-wide-{mode}',dict(position=v(7,1,-11),camera=v(10,6,-3),look=v(7,-3,-14)),mode)
  capture(f'boundary-close-{mode}',dict(position=v(7,1,-11),camera=v(8,3.5,-8),look=v(7,-3,-14)),mode)
 for view in ('wide','close'):
  def channel(mode):
   return np.asarray(Image.open(args.output/f'boundary-{view}-{mode}.png').convert('RGB'))[...,0]/255
  near,far,weight,sand=(channel(mode) for mode in (6,7,9,12))
  ground=(weight>.99)&(sand>.99)
  assert ground.sum()>1000,'Ground shadow fixture is empty'
  # Compare full umbra/lit interiors; the prefiltered near map has softer edges.
  disagreement=((near<.1)&(far>.9))|((near>.9)&(far<.1))
  results[f'{view}_ground_interior_disagreement']=float(disagreement[ground].mean())
 for x in (-8,7,22):
  capture(f'boundary-focus-{x}',dict(position=v(x,1,-11),camera=v(10,6,-3),look=v(7,-3,-14)),6)
 capture('rays',dict(camera=v(0,7,13),look=v(11,27,-44)))
 capture('rays-offset',dict(position=v(1,4.8,4),camera=v(2,7,13),look=v(13,27,-44)))
 capture('sun',dict(camera=v(-.4,7,13),look=v(16,50,0)))
 (args.output/'results.json').write_text(json.dumps(results,indent=2)+'\n')
 print(json.dumps(results,indent=2),flush=True)
 if not args.baseline:
  assert results['column_open_edges']==0,('Column mesh has holes',results)
  assert min(results[f'pass_overlap_time_{t}'] for t in (3,7))>.995,('Visible and shadow geometry differ',results)
  assert results['visible_actor_pixels_moved']==0,('Environmental actors still animate in the shader',results)
  assert max(results[f'{view}_ground_interior_disagreement'] for view in ('wide','close'))<.001,('Near/far shadow interiors disagree',results)
finally:
 g.command('mermaid.lighting',dict(mode=0));g.command('mermaid.capture',{})
 if args.keep_running:g.command('mermaid.resume',{});g.close()
 else:g.close_engine()
