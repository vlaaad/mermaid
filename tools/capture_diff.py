"""Build/run Mermaid, capture its frozen opening, exit the game, then compare.

Run from any directory: python3 /path/to/mermaid/tools/capture_diff.py
The Defold editor is reused or started as needed; the editor stays open.
"""

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "automation-bridge-python"))

from automation_bridge import editor
from tools.image_diff import compare


def run(reference, output, *, max_mae=None):
    reference, output = Path(reference).resolve(), Path(output).resolve()
    if not reference.is_file():
        raise ValueError(f"Reference image does not exist: {reference}")
    capture = output / "capture.png"
    if reference == capture:
        raise ValueError("Capture destination would overwrite the reference image")
    regions = json.loads((ROOT / "tools/reference_regions.json").read_text())
    output.mkdir(parents=True, exist_ok=True)

    print("Opening project; building and starting the game…", flush=True)
    project = editor.open_project(ROOT, start_if_needed=True)
    game = project.build_and_run(
        focus=True, timeout=180,
        required_capabilities=["application.commands", "application.state", "screenshot"],
    )
    try:
        game.wait_for_state("mermaid.ready", True, timeout=45)
        print("Freezing the opening pose and capturing…", flush=True)
        game.command("mermaid.capture", {})
        game.wait_frames(30, timeout=30)
        shot = game.screenshot(after_frames=2, timeout=30)
        capture.write_bytes(shot.read_bytes())
        state = dict(game.state("mermaid").value)
        if not state.get("frozen"):
            raise RuntimeError("Game was unfrozen during capture; rerun without gameplay input")
        evidence = {"state": state, "screen": game.screen(), "screenshot": str(capture)}
        (output / "capture.json").write_text(json.dumps(evidence, indent=2) + "\n")
    finally:
        # close() alone leaves the process alive. Exit even if capture fails.
        print("Exiting the game…", flush=True)
        game.close_engine(timeout=5)

    print("Game exited. Comparing the captured image…", flush=True)
    report = compare(reference, capture, output, regions=regions, max_mae=max_mae)
    print(json.dumps({
        "screenshot": str(capture),
        "report": str(output / "index.html"),
        "metrics": report["metrics"],
        "mae_gate": report["mae_gate"],
    }, indent=2))
    return 1 if report["mae_gate"] and not report["mae_gate"]["passed"] else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", type=Path, default=ROOT / "Blonde-Mermaid-in-Atlantis-Ruins.png")
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/image-diff")
    parser.add_argument("--max-mae-percent", type=float, help="Optional color-error gate; exit 1 when exceeded")
    args = parser.parse_args()
    if args.max_mae_percent is not None and not 0 <= args.max_mae_percent <= 100:
        parser.error("--max-mae-percent must be between 0 and 100")
    try:
        return run(args.reference, args.output, max_mae=args.max_mae_percent)
    except KeyboardInterrupt:
        print("Capture/diff interrupted.", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"Capture/diff failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
