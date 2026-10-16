"""Verify the idle mermaid's rendered shadow remains stable as scene time advances."""
import argparse,json,sys
from pathlib import Path
import numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'automation-bridge-python'))
from automation_bridge import editor
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--attach',action='store_true')
p.add_argument('--keep-running',action='store_true')
p.add_argument('--output',type=Path,default=ROOT/'artifacts/lighting-final/shadow-stability')
args=p.parse_args();args.output.mkdir(parents=True,exist_ok=True)
project=editor.open_project(ROOT,start_if_needed=False)
g=project.connect_engine() if args.attach else project.build_and_run(focus=True,timeout=180)
def v(x,y,z):return dict(x=x,y=y,z=z)
try:
 g.wait_for_state('mermaid.ready',True,timeout=45)
 masks=[]
 for t in [3,5,7]:
  g.command('mermaid.capture',dict(position=v(0,1.5,-5),camera=v(3.1,5.2,1),look=v(0,-2,-8),time=t))
  g.command('mermaid.lighting',dict(mode=6));g.wait_frames(5)
  path=args.output/f'time-{t}.png';path.write_bytes(g.screenshot(after_frames=2).read_bytes())
  a=np.asarray(Image.open(path).convert('RGB'));h,w=a.shape[:2]
  # Ground below the character: excludes her mesh, animated fish and vegetation.
  crop=a[int(h*.78):int(h*.98),int(w*.18):int(w*.44),0]
  masks.append(crop<128)
 assert masks[0].sum()>1000,'The fixed view did not contain the character shadow'
 results=[]
 for mask in masks[1:]:
  overlap=float((mask&masks[0]).sum()/max(1,(mask|masks[0]).sum()))
  displacement=float(np.linalg.norm(np.argwhere(mask).mean(0)-np.argwhere(masks[0]).mean(0)))
  results.append(dict(overlap=overlap,centroid_displacement_pixels=displacement))
  assert overlap>.995 and displacement<.5,('Idle shadow moved',results)
 (args.output/'stability.json').write_text(json.dumps(results,indent=2)+'\n')
 print('Idle shadow stable:',results,flush=True)
finally:
 g.command('mermaid.lighting',dict(mode=0));g.command('mermaid.capture',{})
 if args.keep_running:g.command('mermaid.resume',{});g.close()
 else:g.close_engine()
