"""Build the HTML5 release and copy its static files to the Pages /docs root."""
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'automation-bridge-python'))
from automation_bridge import editor


def main():
    project = editor.open_project(ROOT, start_if_needed=False)
    output = ROOT / 'artifacts/pages-release'
    result = project.bob(
        options={'platform': 'wasm-web', 'architectures': 'wasm-web',
                 'archive': True, 'variant': 'release', 'bundle-output': str(output)},
        commands=('build', 'bundle'), timeout=240)
    if not result.success:
        raise RuntimeError(f'HTML5 release failed: {result}')
    bundle = output / 'mermaid'
    if not (bundle / 'index.html').is_file():
        raise RuntimeError(f'Missing release index: {bundle}')
    destination = ROOT / 'docs'
    shutil.copytree(bundle, destination, dirs_exist_ok=True)
    (destination / '.nojekyll').touch()
    print(f'HTML5 release copied to {destination}', flush=True)


if __name__ == '__main__':
    main()
