# Mermaid — working notes

## Goal and current result

Build an interactive 3D scene matching `Blonde-Mermaid-in-Atlantis-Ruins.png`, with satisfying keyboard/mouse swimming on desktop and browser. Target hardware: Intel HD530 laptop; aim for 30 FPS.

**Historical opening fit before the close-detail pass: 20.16% of pixels within 10 RGB levels per channel (pass112).** Exact matches: 0.0199%; RGB MAE: 9.4601%; SSIM: 0.48273. These are diagnostics, not overall fidelity percentages. Evidence: `artifacts/progress/pass112/`.

The close-detail pass replaces the flat fin with a cupped, closed membrane, shared radial topology, corrected normals and independent blade flex. Sand caustics now come from an offline refracted wave ray field. Shadows bilinearly interpolate four depth comparisons with the existing 1024² map, removing the old four-level snapped PCF without increasing the map size or pass count.

Water has a separate `surface.fp`: two scrolling, rotated wave-normal layers, mipmapping and anisotropic filtering, dielectric Fresnel reflection, a softened Snell window and an antialiased refracted sun. The sun's above-water direction is derived from the direction used by the underwater lighting and shafts. Underwater reflections use a blue scattered-light environment approximation, without reflecting nearby architecture. Quarter-resolution scattering uses midpoint integration to avoid the old fixed pixel-noise grid; shafts vary with surface position and wave slope.

All 1,157 rocks now have geometry-derived convex collision hulls, including lintels and the detailed foreground block. Six overlapping body spheres cover the character, and the camera clips against hull faces. All 273 rooted actors are placed using the final stone geometry and their individual mesh root feet. `tools/check_world.py` verifies collider coverage and root support. No unsupported roots were found. `tools/detail_check.py` captures rear/side/sand/upward views and checks boosted contact with a large boulder. Evidence: `artifacts/close-detail/delivered/` and `artifacts/close-detail/world-audit.json`.

Opening structure checks still find all 11 required regions. The new lighting changes the old pixel-fit score; use the current captures rather than treating pass112 as the current rendered result. The final WebGL build measures about 20–22 FPS at 1280×720 on this HD530, comparable to the isolated starting build at about 21 FPS on the same machine. This remains below the 30 FPS target. Evidence: `artifacts/close-detail/browser-before/`, `browser-after/` and `browser-water-metrics.json`. Browser swimming and upward orbit pass, with no WebGL warnings/errors.

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
- Regeneration seats rooted actors against the complete final stone geometry. Run `tools/check_world.py` after moving geometry or plants; it checks every exported root foot, including stems around the edges of clusters.
- Preserve existing work. Commit each verified improvement that is retained. Historical experiments and measurements remain in `artifacts/progress/`.

## Build assets and validate

```bash
OPENBLAS_NUM_THREADS=1 python3 tools/build_assets.py
python3 tools/check_world.py
python3 -m unittest tools.test_image_diff tools.test_structure_check -q
python3 tools/playtest.py
```

Generator: seed 73, Y-up meters, forward -Z; emits shared GLBs, world layout, collision boxes, manifest and named landmarks. Limit: 2048 model/GO instances. Editable sources: `assets/source/mermaid.blend` and `ruins.blend`. Blender: `/snap/bin/blender`.

Finished meshes are cached by raw-mesh/script signature. Manual edits must export to the relevant `*-finished.glb` with material `reef`, vertex colors, normals and UVs; reset ruins display offsets before export. Changing generator geometry or finishing scripts can replace manual exports, so preserve them first.

Mermaid vertex alpha identifies skin 0, tail .25, fluke .5, hair .75, garment 1. Normal fragment output stays opaque. Swimming, hair and tail deformation currently use the vertex shader. Controls: WASD, Space/E rise, Ctrl/Q dive, Shift boost, mouse drag orbit, R reset, P profiler.

`playtest.py` passes frozen stability, forward swimming, boost (1.95× normal distance), rise and orbit after this pass. `detail_check.py` passes boosted boulder contact. All 16 existing image/structure tests pass. WebGL builds without errors or warnings. Final native frozen profiling measured 40.3ms mean / 90.6ms p95, 79 draws, compared with 47.5ms / 96.1ms for the starting build in this session. Timings remain variable and the 30 FPS target is not yet met on this hardware. See `artifacts/close-detail/delivered/profile.json` and browser evidence in `artifacts/close-detail/browser-after/` rather than reusing the historical pass87 24ms result.

## Runtime and tooling

- Editor HTTP: `http://127.0.0.1:$(cat .internal/editor.port)`. Never print `.internal/editor.token`. Editor/engine/Blender may require sandbox escalation; avoid concurrent builds.
- Defold 1.14.0; Automation Bridge 2.5.0. Managed wrapper: `automation-bridge-python/`; do not edit it. Set `PYTHONPATH=automation-bridge-python` for direct bridge scripts.
- Bridge: `editor.open_project('.', start_if_needed=False)`, `build_and_run(focus=True, timeout=180)`, wait for `mermaid.ready`, command `mermaid.capture`. State is `.value`; screenshots use `.read_bytes()`. `close_engine()` exits the engine; `close()` only disconnects.
- Web bundle: Bob `build,bundle`, platform/architecture `wasm-web`, archive true; output `artifacts/browser/` (outside reserved `build/`). `python3 tools/serve.py` serves port 8765; check for an existing server first.
- Browser frozen capture: `/?debug=1&capture=1&width=1280`. “Save frame and timings” writes actual browser evidence to `artifacts/scene/`. Click canvas before keyboard input. Browser has no engine bridge HTTP; validate separately with one test renderer active.

## Rendering constraints

Opaque depth-tested rendering; no depth prepass or alpha discard. Keep fish, fins, hair and kelp two-sided. Sampled depth attachments require `render.TEXTURE_BIT`; fullscreen glTF UVs need V restored at each render-target lookup.

Geometry/post cap: 1280×720; 1024² shadow map with four bilinearly interpolated depth comparisons; quarter-resolution 24-step water scattering; depth-aware upsampling. Shared GLBs index complete vertex tuples to preserve seams and normals. Collision substeps ≤25ms and dt cap .1 prevent slow motion under load.

Rejected experiments: hand-extruded cliffs (passes21–22), cutout hair/tail/plants (`7e66368`, reverted), connected outcrop (passes50–51, reverted: worse visuals and 92 draws), `SORT_NONE` (pass52: 97 draws). Do not restore blindly.

## Water rendering references

- [GPU Gems: Effective Water Simulation from Physical Models](https://developer.nvidia.com/gpugems/gpugems/part-i-natural-effects/chapter-1-effective-water-simulation-physical-models): layered directional wave normals.
- [Monzon et al., Real-Time Underwater Spectral Rendering (2024)](https://onlinelibrary.wiley.com/doi/10.1111/cgf.15009): dielectric water surface, Fresnel reflection and Snell's window. This project implements an RGB approximation, not the paper's full spectral transport model.
- [Defold material filtering](https://defold.com/manuals/material/): trilinear mip filtering and anisotropy for grazing surface views.
