# Mermaid — working notes

## Goal and current result

Build an interactive 3D scene matching `Blonde-Mermaid-in-Atlantis-Ruins.png`, with satisfying keyboard/mouse swimming on desktop and browser. Target hardware: Intel HD530 laptop; aim for 30 FPS.

**Current target: 20% of pixels within 10 RGB levels per channel. Latest measured: 19.26% (pass102).** Exact matches: 0.0141%; RGB MAE: 9.7213%; SSIM: 0.46494. These are diagnostics, not overall fidelity percentages. Evidence: `artifacts/progress/pass102/`.

Retained work: broader pointed fins with clean concave topology and filtered veins; larger head/scalp; lower arms and flowing locks; rotated connected arcade, deeper column fluting, all 11 required column regions present; olive grass with three corrected roots; blue rock/floor materials with softer sand caustics, height-based bottom-water haze, stronger surface sunlight patch, foreground stone volume with local bevel detail. Native pass87: 24.0ms mean / 24.5ms p95, 78 draws. Previous slow profiles overlapped CPU-heavy fitting; do not attribute them solely to rock bevels.

Retained layout now includes broader columns and deeper left and right ledge groups, with their plants/collision moved together; the right group exposes the orange school. The right mid-terrace trial (43,-42, height13.5) is retained. Rock material now uses softer direct light and stronger cool ambient fill, verified in pass97 against the same frozen camera/time. Latest validated browser build remains pass53, about 19 FPS; rebuild and validate current web output before reporting browser performance.

## Produce a diff

From the project directory:

```bash
python3 tools/capture_diff.py
```

No required arguments. Reuses/starts Defold, builds and runs the native game, freezes the opening at time 3, captures the scene and architecture mask, exits the game, and compares against the reference. The editor stays open.

Outputs in `artifacts/image-diff/`:

- `diff.png`: reference and capture above one RGB difference panel.
- `metrics.json`: scores, settings and regional diagnostics.
- `capture.png`, `capture.json`: actual framebuffer and frozen state.
- `structure-mask.png`, `structure.json`: visible architecture audit.

For a separate checkpoint and native profiling:

```bash
python3 tools/capture_diff.py --output artifacts/progress/pass56 --profile
```

The comparison uses fixed 960px analysis width and LANCZOS resizing, with no alignment, cropping, warping or color correction. Exact equality is black; larger RGB error is brighter under a fixed square-root display curve. The 10-level tolerance score is reported separately and never thresholds the difference image. `--max-mae-percent 4` optionally gates MAE only; exit codes are 0 for workflow success, 1 for failed MAE gate, 2 for an error.

## Working rules and next work

- Fit **one visual element per pass**. Freeze camera, pose/time and unrelated settings; inspect a real capture before proceeding.
- Keep real 3D geometry and independent shared-mesh actors. No reference backdrops, projections or actor baking. Inspect swimming and orbit views too.
- Main remaining mismatches: foreground/midground rock shape and placement, vegetation, character and architecture. Do not count blue water as missing blue geometry.
- All 11 architecture regions pass as of pass79. The coarse audit checks presence, not silhouette accuracy; inspect the normal capture too.
- Unsupported coral `(-9,9,-20)` and sponge `(-11,4.5,-11)` remain. Three prominent grass roots were seated on measured ledges. Raycast support before moving plants; helper: `artifacts/progress/check_support.py` (extend its mesh filter for `rock3_detail` if querying the new block).
- Preserve existing work. Commit each verified improvement that is retained. Historical experiments and measurements remain in `artifacts/progress/`.

## Build assets and validate

```bash
python3 tools/build_assets.py
python3 -m unittest tools.test_image_diff tools.test_structure_check -q
python3 tools/playtest.py
```

Generator: seed 73, Y-up meters, forward -Z; emits shared GLBs, world layout, collision boxes, manifest and named landmarks. Limit: 2048 model/GO instances. Editable sources: `assets/source/mermaid.blend` and `ruins.blend`. Blender: `/snap/bin/blender`.

Finished meshes are cached by raw-mesh/script signature. Manual edits must export to the relevant `*-finished.glb` with material `reef`, vertex colors, normals and UVs; reset ruins display offsets before export. Changing generator geometry or finishing scripts can replace manual exports, so preserve them first.

Mermaid vertex alpha identifies skin 0, tail .25, fluke .5, hair .75, garment 1. Normal fragment output stays opaque. Swimming, hair and tail deformation currently use the vertex shader. Controls: WASD, Space/E rise, Ctrl/Q dive, Shift boost, mouse drag orbit, R reset, P profiler.

`playtest.py` checks frozen stability, swimming, boost, rise, orbit and native profiling. Last complete movement/browser validation: pass53. Latest native frozen profile: pass87, 24.0ms mean, 78 draws. Revalidate current changes separately on native and web.

## Runtime and tooling

- Editor HTTP: `http://127.0.0.1:$(cat .internal/editor.port)`. Never print `.internal/editor.token`. Editor/engine/Blender may require sandbox escalation; avoid concurrent builds.
- Defold 1.14.0; Automation Bridge 2.5.0. Managed wrapper: `automation-bridge-python/`; do not edit it. Set `PYTHONPATH=automation-bridge-python` for direct bridge scripts.
- Bridge: `editor.open_project('.', start_if_needed=False)`, `build_and_run(focus=True, timeout=180)`, wait for `mermaid.ready`, command `mermaid.capture`. State is `.value`; screenshots use `.read_bytes()`. `close_engine()` exits the engine; `close()` only disconnects.
- Web bundle: Bob `build,bundle`, platform/architecture `wasm-web`, archive true; output `artifacts/browser/` (outside reserved `build/`). `python3 tools/serve.py` serves port 8765; check for an existing server first.
- Browser frozen capture: `/?debug=1&capture=1&width=1280`. “Save frame and timings” writes actual browser evidence to `artifacts/scene/`. Click canvas before keyboard input. Browser has no engine bridge HTTP; validate separately with one test renderer active.

## Rendering constraints

Opaque depth-tested rendering; no depth prepass or alpha discard. Keep fish, fins, hair and kelp two-sided. Sampled depth attachments require `render.TEXTURE_BIT`; fullscreen glTF UVs need V restored at each render-target lookup.

Geometry/post cap: 1280×720; 1024² shadow map with 4 PCF taps; quarter-resolution 32-step water scattering; depth-aware upsampling. Shared GLBs index complete vertex tuples to preserve seams and normals. Collision substeps ≤25ms and dt cap .1 prevent slow motion under load.

Rejected experiments: hand-extruded cliffs (passes21–22), cutout hair/tail/plants (`7e66368`, reverted), connected outcrop (passes50–51, reverted: worse visuals and 92 draws), `SORT_NONE` (pass52: 97 draws). Do not restore blindly.
