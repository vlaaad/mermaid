"""Build or attach, optionally send input, and save a runtime screenshot/report."""

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "automation-bridge-python"))

from automation_bridge import editor


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", action="store_true", help="Compile and launch; otherwise attach")
    parser.add_argument("--focus", action="store_true", help="Focus a newly built game for timing-sensitive tests")
    parser.add_argument("--key", help="Defold key name, such as W or SPACE")
    parser.add_argument("--hold", type=float, default=0.2, help="Key hold duration in seconds")
    parser.add_argument("--click", nargs=2, type=float, metavar=("X", "Y"))
    parser.add_argument("--scale", type=float, default=0.5, help="Screenshot resolution multiplier")
    parser.add_argument("--profile", type=int, default=0, metavar="FRAMES", help="Capture native profiler frames")
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/automation")
    args = parser.parse_args()
    if args.focus and not args.build:
        parser.error("--focus requires --build")
    if not 0 <= args.hold <= 60:
        parser.error("--hold must be between 0 and 60 seconds")
    if not 0.01 <= args.scale <= 1:
        parser.error("--scale must be between 0.01 and 1")
    if not 0 <= args.profile <= 600:
        parser.error("--profile must be between 0 and 600 frames")

    project = editor.open_project(ROOT, start_if_needed=False)
    required = ["scene", "screenshot"]
    if args.key:
        required.append("input.key>=2")
    if args.click:
        required.append("input.click")
    game = (
        project.build_and_run(timeout=180, focus=args.focus, required_capabilities=required)
        if args.build else project.connect_engine(required_capabilities=required)
    )
    try:
        report = {"health": game.health(), "input": [], "element_count": game.count()}
        if args.key:
            report["input"].append(dict(game.key(
                args.key, hold=args.hold, wait="released", timeout=max(15, args.hold + 5)
            )))
        if args.click:
            report["input"].append(dict(game.click(*args.click, timeout=15)))
        if args.profile:
            capture = game.profiler.capture(frames=args.profile, warmup_frames=5, thread="Main", timeout=45)
            report["profile"] = {
                "frames": len(capture.frames),
                "scopes": [asdict(row) for row in capture.scopes()],
                "counters": [asdict(row) for row in capture.counters()],
                "resources": [asdict(row) for row in game.profiler.resources()],
            }
        shot = game.screenshot(after_frames=2, timeout=15, resolution_multiplier=args.scale)
        args.output.mkdir(parents=True, exist_ok=True)
        destination = args.output / "latest.png"
        destination.write_bytes(shot.read_bytes())
        report["screenshot"] = dict(shot.raw)
        report["screenshot"]["saved_path"] = str(destination.resolve())
        (args.output / "latest.json").write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps({
            "screenshot": str(destination.resolve()),
            "report": str((args.output / "latest.json").resolve()),
            "element_count": report["element_count"],
            "input_states": [receipt["state"] for receipt in report["input"]],
        }, indent=2))
    finally:
        game.close()  # Release this client while leaving the game available for inspection.


if __name__ == "__main__":
    main()
