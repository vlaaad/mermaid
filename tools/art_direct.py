"""Apply real scene art settings, capture the engine, and measure against the reference."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'automation-bridge-python'))
from automation_bridge import editor


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--settings',type=Path,default=ROOT/'assets/art.json')
    parser.add_argument('--output',type=Path,default=ROOT/'artifacts/art-pass/current')
    parser.add_argument('--build',action='store_true')
    args=parser.parse_args()
    p=editor.open_project(ROOT,start_if_needed=False)
    if args.build:p.preview.render('main/world.collection',resolution_multiplier=.25)
    g=p.build_and_run(focus=True,timeout=180) if args.build else p.connect_engine()
    try:
        g.wait_for_state('mermaid.ready',True,timeout=45)
        g.wait_frames(30 if args.build else 2)
        settings=json.loads(args.settings.read_text())
        g.command('mermaid.art',settings)
        g.wait_frames(8)
        args.output.mkdir(parents=True,exist_ok=True)
        (args.output/'frame.png').write_bytes(g.screenshot(after_frames=2).read_bytes())
        (args.output/'settings.json').write_text(json.dumps(settings,indent=2)+'\n')
        (args.output/'state.json').write_text(json.dumps(g.state('mermaid').value,indent=2)+'\n')
        # Runtime warnings are part of the capture evidence, not silently ignored.
        console=p.console.read()
        issues=[line for line in console.lines if 'WARNING:' in line or 'ERROR:' in line]
        (args.output/'warnings.json').write_text(json.dumps(issues,indent=2)+'\n')
        print('Runtime warnings/errors:',len(issues))
        if issues:raise RuntimeError('Resolve runtime warnings/errors before judging this art capture: '+issues[0])
    finally:g.close()
    return subprocess.call([sys.executable,str(ROOT/'tools/image_diff.py'),str(ROOT/'Blonde-Mermaid-in-Atlantis-Ruins.png'),str(args.output/'frame.png'),'--output',str(args.output/'diff'),'--regions',str(ROOT/'tools/reference_regions.json'),'--max-mae-percent','4'])


if __name__=='__main__':sys.exit(main())
