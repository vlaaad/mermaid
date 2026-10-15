# Mermaid

Defold project for a third-person underwater exploration scene inspired by
`Blonde-Mermaid-in-Atlantis-Ruins.png`. Scene content is currently empty.

## Development setup

- Defold editor is running and reachable through `.internal/editor.port`.
- Automation Bridge is pinned to release **2.5.0** in `game.project`, with its
  matching dependency-free Python wrapper in `automation-bridge-python/`.
- The optional application API is enabled for future player/camera state,
  reset commands, and input acknowledgements. Guard Lua calls with
  `if automation_bridge then ... end` because the bridge is debug-only.
- Python 3 and Blender **5.2.2 LTS** are installed and verified. Blender's Snap
  launcher requires execution outside the restricted agent sandbox.

Keep the editor open on this project. From the project root:

```sh
# Build and launch, then capture the native game.
python3 tools/automation.py --build

# Attach to the running native game, send input, and capture afterward.
python3 tools/automation.py --key W --hold 0.5 --click 200 200

# Focus the game during timing-sensitive movement tests.
python3 tools/automation.py --build --focus --key W --hold 0.5

# Capture main-thread timings, counters, and resource sizes in latest.json.
python3 tools/automation.py --build --focus --profile 60
```

The helper saves `artifacts/automation/latest.png` and `latest.json`, including
native input receipts, health/capabilities, frame IDs, and capture metadata. It
leaves the game running. Coordinates use top-left window pixels; high-DPI
window dimensions may differ from configured project dimensions. Screenshots
default to half resolution; use `--scale 1` for full resolution. An unfocused
game may throttle frames, so use the focused build for control timing checks.
Agent sandbox restrictions may require escalation for local editor/engine HTTP.

Verified on 2026-10-15: Defold 1.14.0 built and launched the empty project with
the extension, captured a runtime PNG, and completed W-key and mouse-click
input with `released` receipts. The empty scene has no gameplay input handler;
these checks establish transport and capture, not character behavior.

The HTML5 build also compiles and starts in the browser. The bridge reports that
its debug HTTP server is unavailable in WebAssembly: use browser automation for
web screenshots/input and browser performance tools for web frame timings.
Launch HTML5 through Defold's Project > Build HTML5 command, or from Python:

```python
from automation_bridge import editor
project = editor.open_project(".", start_if_needed=False)
project.build_and_run_html5(timeout=180)
```

Run with `PYTHONPATH=automation-bridge-python`. The generated preview is under
`build/default_html5/__htmlLaunchDir/mermaid/` and can also be served locally:

```sh
python3 -m http.server 8765 --bind 127.0.0.1 --directory build/default_html5/__htmlLaunchDir/mermaid
```

Open `http://127.0.0.1:8765/`. Browser canvas focus, clicking, and key injection
were exercised; gameplay response needs a controller first. A native profiler
capture of 60 main-thread frames was also verified, including scope timings,
counters, and resource sizes. The helper records the main thread explicitly
rather than counting other profiler threads toward the requested frame count.

After updating the extension, refresh the entire matching Python wrapper using
the extension's documented installer/update helper and restart Python.
Do not put project code in the managed wrapper directory.

## Scene plan

### Opening-frame comparison

`tools/image_diff.py` compares two images, writes a fixed-scale difference
heatmap and pink difference overlay, a static comparison sheet, an interactive
wipe report, and JSON metrics with source hashes and preprocessing settings.
It uses Pillow and NumPy (already installed here); requirements are in
`tools/requirements-image-diff.txt`.

```sh
python3 tools/image_diff.py Blonde-Mermaid-in-Atlantis-Ruins.png artifacts/automation/latest.png --regions tools/reference_regions.json
```

Use equal camera aspect ratios. The current empty-project screenshot is 3:2
while the reference is approximately 16:9, so this command deliberately rejects
it. For an explicit diagnostic of that existing screenshot, append `--fit contain`.
This letterboxes the candidate and records a warning; no cropping, auto-alignment,
or color correction hides differences. Different resolutions with matching aspect
are resized to the same analysis viewport, 960 pixels wide by default.

Open `artifacts/image-diff/index.html`, or inspect `comparison.png` and
`metrics.json`. To serve the interactive report locally:

```sh
python3 -m http.server 8766 --bind 127.0.0.1 --directory artifacts/image-diff
```

Metrics are intentionally separate:

- **RGB MAE percent:** mean absolute RGB error / 255 × 100. A 10% score means
  average channel error of 25.5 levels; it does not mean 90% visual fidelity.
- **RGB SSIM:** local structural similarity, best = 1 (can be negative). Uses a
  7x7 uniform window and sample covariance; not a fidelity percentage.
- **Changed pixels percent:** pixels whose mean RGB error exceeds 10/255,
  configurable with `--pixel-threshold`.
- **Blurred RGB MAE:** coarse palette/layout diagnostic only, not a substitute
  for geometry, detailed structure, or correct character art.
- **Regional scores:** explicit normalized rectangles for the mermaid, circular
  ruin, foreground, distant corridor, and surface in `tools/reference_regions.json`.
  These are appearance checks in fixed rectangles, not semantic object detection.

`--max-mae-percent 10` optionally exits 1 when that single metric exceeds 10;
the default produces a report without implying acceptance. No composite
“match percentage” is invented. Scores depend on analysis resolution, so keep
`--width`, viewport, and all comparison settings fixed between iterations.

For reproducible opening-frame captures, the scene must first expose a debug
capture fixture: fixed camera/FOV, player pose, random seed, lighting/animation
time, viewport and device pixel ratio; await model/texture loading and rendering.
Capture the real 3D scene in that ready state, rather than the first loading frame.
This fixture will be implemented with the scene. Browser and native captures
must both be checked. After approving the opening frame, save it as a separate
game-render baseline for tighter visual regression tests.

The empty black scene currently measures **39.24% RGB MAE**, **0.0021 SSIM**, and
**100% changed pixels** against the art at the default analysis resolution.
This only verifies the comparison workflow; no scene match is claimed.

Known-value tests: `python3 -m unittest tools.test_image_diff -v`.
SSIM background: [scikit-image's structural similarity example](https://scikit-image.org/docs/stable/auto_examples/transform/plot_ssim.html).

### Implementation sequence

Targets: **desktop and browser, keyboard/mouse, 60 FPS in browser**, with instanced
and optimized rendering and profiler-guided development. Initial visual target:
1080p on an agreed representative desktop/laptop; validate on real browsers and
hardware before treating 60 FPS as a guarantee. Build one compact explorable ruin.

1. **Movement and camera blockout.** Perspective camera and a proxy swimmer in
   a small 3D test space. Camera-relative WASD, mouse orbit, ascend/descend,
   boost, responsive acceleration, gentle drag, smooth turns/banking, collision
   sliding, and camera obstruction handling. Publish player/camera state and
   reset commands for repeatable bridge tests. Verify browser pointer lock and
   focus behavior early.
2. **Reference composition and assets.** Build a layered rocky corridor in
   Blender with broken columns, arches, and the large circular ruin as a distant
   landmark. Establish meter scale and glTF/GLB export early. Use modular meshes,
   shared materials/texture atlases, and Defold-compatible instanced materials
   for repeated rocks, columns, vegetation, and fish. Keep draw calls measurable.
3. **Underwater rendering prototype.** Directional sun, cool ambient fill,
   depth/distance fog with water color absorption, animated world-space caustics,
   moving surface highlights, and sun shafts. Start with inexpensive shaft
   geometry and restrained transparency. Prototype on a small art sample and
   profile in-browser before producing all assets. Recreate Blender material
   effects in Defold shaders; material nodes do not transfer as runtime shaders.
4. **Mermaid.** Create or import a rigged blonde mermaid with a turquoise tail,
   readable fins, and warm highlights. Blend idle, swim, boost, and turn motion;
   add secondary hair/fin motion. A proxy supports initial control work. The
   final character is the main asset-quality risk for matching the reference.
5. **Living environment.** Swaying kelp, coral color accents, small fish schools,
   occasional rays, particles, bubbles, and restrained underwater audio. Reuse
   geometry; add distance culling/LOD and cap transparent layers and simulation
   counts. Animate appropriate repeated assets in shaders to reduce CPU work.
6. **Profile and polish continuously.** Use the Defold profiler for CPU scopes,
   rendering statistics, draw calls, and memory; use browser profiling for the
   actual web target. Budget roughly 16.7 ms/frame and inspect spikes as well as
   averages. Check GPU cost, overdraw, asset sizes, startup time, and browser
   memory. Keep a repeatable traversal and fixed-camera screenshot checkpoints.

First milestone: swim through one convincing sunlit archway, with responsive
controls, fog, caustics, a stable camera, and a measured browser frame budget,
before expanding the environment. Native bridge tests and browser playtests
complement each other; native screenshots alone do not validate browser output.

## What is needed

No additional paid software or services are required to start. Blender, Defold,
Python, GLSL shaders, and the bridge cover the initial workflow. Network access
is needed for dependency fetching and native extension builds.

Useful remaining inputs: representative browser/hardware for the 60 FPS target,
and whether a preferred rigged character already exists. Otherwise begin with
an original stylized proxy and procedural environment assets. A polished
character may later benefit from a supplied/licensed model or dedicated character
art. Audio can wait until the visual and movement milestone works.

References: [Automation Bridge](https://github.com/defold/extension-automation-bridge),
[Defold models](https://defold.com/manuals/model/),
[Defold lights](https://defold.com/manuals/light/).
