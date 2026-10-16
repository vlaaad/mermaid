# Mermaid — working notes

## Goal and current result

Build an interactive 3D scene matching `Blonde-Mermaid-in-Atlantis-Ruins.png`, with satisfying keyboard/mouse swimming on desktop and browser. Target hardware: Intel HD530 laptop; aim for 30 FPS.

**Historical opening fit before the close-detail pass: 20.16% of pixels within 10 RGB levels per channel (pass112).** Exact matches: 0.0199%; RGB MAE: 9.4601%; SSIM: 0.48273. These are diagnostics, not overall fidelity percentages. Evidence: `artifacts/progress/pass112/`.

The fin is a cupped, closed membrane with shared radial topology and corrected normals. Actor shader deformation and travel are removed for grass, mermaid, fish and rays, along with the idle character bob: plants, fish and rays stay still, and the controller moves and rotates the rigid character. Crowd simulation will drive fish placement and avoidance later. Shared currents and skeletal deformation are future work. Sand caustics come from an offline refracted wave ray field.

Close shadows use a texel-snapped 512² EVSM4 map covering 24m around the character, with a separable Gaussian prefilter and a blend into the cached 2048² full-world depth map. Nearby receivers usually need one filtered shadow lookup. The far map still occludes light shafts. This adds a small caster pass and two 512² blurs while removing the full-resolution eight-sample screen-space contact darkening that produced silhouette rims.

Water has a separate `surface.fp`: two scrolling, rotated wave-normal layers, mipmapping and anisotropic filtering, dielectric Fresnel reflection, a softened Snell window and an antialiased refracted sun. The sun's above-water direction is derived from the direction used by the underwater lighting and shafts. Underwater reflections use a blue scattered-light environment approximation, without reflecting nearby architecture. The surface has a broader near-white sun halo, a brighter underwater reflected fill, and the same base distance-haze density as tall architecture. Shafts now come from single sunlight scattering through uniform water, occluded by the same ruins shadow map used by surface lighting. The quarter-resolution pass uses 64 intervals anchored to world planes, exact Beer-Lambert transmittance integration within each interval, a forward Henyey-Greenstein phase function (g = 0.5), and filtered shadow visibility. Incoming sunlight varies through a separate, static, band-limited irradiance aperture on the water plane. Its isolated fine peaks form sun-aligned volume shafts; mip filtering broadens them using water depth and the view interval footprint. This is an artistic surface-focusing approximation. The floor caustic network is no longer extruded through the volume, which produced a web pattern. The volume is fixed in world space, and actual scene occluders stop the shafts. It stops at opaque geometry and the water boundary. There are no beam cards, animated domain warps, or noise-density clouds. This is a single-scattering approximation, not full volumetric caustics or multiple scattering.

The quarter-resolution shaft buffer stores full view depth in RGBA16F. Upsampling rejects unrelated background depths, follows grazing-surface depth slopes, and does not force background light onto silhouette edges. Bubbles use two-triangle billboards with an antialiased white rim, a white highlight, a transparent center, premultiplied blending and no depth writes.

All 1,205 rocks now have geometry-derived convex collision hulls, including lintels and the detailed foreground block. Six overlapping body spheres cover the character, and the camera clips against hull faces. All 288 rooted actors are placed using the final stone geometry and their individual mesh root feet. `tools/check_world.py` verifies collider coverage and root support. No unsupported roots were found. `tools/detail_check.py` captures rear/side/sand/upward views and checks boosted contact with a large boulder. Evidence: `artifacts/close-detail/delivered/` and `artifacts/close-detail/world-audit.json`.

Opening structure checks found all 11 required regions in the preceding close-detail pass. The new lighting changes the old pixel-fit score; use the current captures rather than treating pass112 as the current rendered result. The preceding close-detail WebGL build measured about 20–22 FPS at 1280×720 on this HD530, comparable to the isolated starting build at about 21 FPS on the same machine. This remains below the 30 FPS target. Evidence: `artifacts/close-detail/browser-before/`, `browser-after/` and `browser-water-metrics.json`. Browser swimming and upward orbit pass, with no WebGL warnings/errors.

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

Mermaid vertex alpha identifies skin 0, tail .25, fluke .5, hair .75, garment 1. Normal fragment output stays opaque. Mermaid, kelp, fish and ray shader motion is disabled; actor vertex transforms are rigid. All actor movement/deformation belongs to the future currents, crowd and rig systems. Controls: WASD, Space/E rise, Ctrl/Q dive, Shift boost, mouse drag orbit, R reset, P profiler.

`playtest.py` passes frozen stability, forward swimming, boost (1.95× normal distance), rise and orbit after this pass. `detail_check.py` passes boosted boulder contact. All 16 existing image/structure tests pass. The preceding close-detail WebGL build completed without build errors or warnings. That pass’s native frozen profiling measured 40.3ms mean / 90.6ms p95, 79 draws, compared with 47.5ms / 96.1ms for its starting build. Timings remain variable and the 30 FPS target is not yet met on this hardware. See `artifacts/close-detail/delivered/profile.json` and browser evidence in `artifacts/close-detail/browser-after/` rather than reusing the historical pass87 24ms result.

## Runtime and tooling

- Editor HTTP: `http://127.0.0.1:$(cat .internal/editor.port)`. Never print `.internal/editor.token`. Editor/engine/Blender may require sandbox escalation; avoid concurrent builds.
- Defold 1.14.0; Automation Bridge 2.5.0. Managed wrapper: `automation-bridge-python/`; do not edit it. Set `PYTHONPATH=automation-bridge-python` for direct bridge scripts.
- Bridge: `editor.open_project('.', start_if_needed=False)`, `build_and_run(focus=True, timeout=180)`, wait for `mermaid.ready`, command `mermaid.capture`. State is `.value`; screenshots use `.read_bytes()`. `close_engine()` exits the engine; `close()` only disconnects.
- Web bundle: Bob `build,bundle`, platform/architecture `wasm-web`, archive true; output `artifacts/browser/` (outside reserved `build/`). `python3 tools/serve.py` serves port 8765; check for an existing server first.
- Browser frozen capture: `/?debug=1&capture=1&width=1280`. “Save frame and timings” writes actual browser evidence to `artifacts/scene/`. Click canvas before keyboard input. Browser has no engine bridge HTTP; validate separately with one test renderer active.

## Rendering constraints

Opaque depth-tested geometry with a separate premultiplied transparent bubble pass; no depth prepass or alpha discard. Keep fish, fins, hair and kelp two-sided. Sampled depth attachments require `render.TEXTURE_BIT`; fullscreen glTF UVs need V restored at each render-target lookup.

Geometry/post cap: 1280×720; desktop scene MSAA follows Display Samples (4 by default), with FXAA on WebGL; 512² RGBA32F EVSM4 near shadows plus 1024² distant depth shadows; quarter-resolution 64-interval shadowed single scattering in RGBA16F; depth-aware upsampling. Float render targets and linear float filtering are required; validated on HD530 desktop OpenGL and WebGL2. Shared GLBs index complete vertex tuples to preserve seams and normals. Collision substeps ≤25ms and dt cap .1 prevent slow motion under load.

Rejected experiments: hand-extruded cliffs (passes21–22), cutout hair/tail/plants (`7e66368`, reverted), connected outcrop (passes50–51, reverted: worse visuals and 92 draws), `SORT_NONE` (pass52: 97 draws). Do not restore blindly.

## Water rendering references

- [GPU Gems: Effective Water Simulation from Physical Models](https://developer.nvidia.com/gpugems/gpugems/part-i-natural-effects/chapter-1-effective-water-simulation-physical-models): layered directional wave normals.
- [Monzon et al., Real-Time Underwater Spectral Rendering (2024)](https://onlinelibrary.wiley.com/doi/10.1111/cgf.15009): dielectric water surface, Fresnel reflection and Snell's window. This project implements an RGB approximation, not the paper's full spectral transport model.
- [Defold material filtering](https://defold.com/manuals/material/): trilinear mip filtering and anisotropy for grazing surface views.

## Lighting follow-up validation

`tools/detail_check.py` now includes near/wide shadow and bubble views. `tools/shadow_check.py` captures the actual shadow visibility at times 3, 5 and 7 in a fixed view. Its isolated ground-shadow masks overlap 100%, with zero centroid displacement. Lighting debug mode 6 shows receiver shadow visibility without caustics or scattering. Native movement, boost, rise, orbit and frozen-frame repeat checks pass; the repeat was pixel-identical. All 16 image/structure unit tests pass. Evidence: `artifacts/lighting-final/delivered-final/`, `artifacts/lighting-final/shadow-stability/` and `artifacts/scene/playtest.json`.

Final native profiling measured 54.6ms mean / 112.7ms p95, 94 draws; the same-session starting build measured 57.4ms / 110.4ms, 79 draws. The final controller playtest measured 57.5ms mean / 114.6ms p95, confirming the variance. This machine's desktop/browser timings fluctuate substantially; the 30 FPS goal remains unmet. Earlier `artifacts/shadow-quality/browser-after/` measurements predate the replacement of the marching light field and should not be treated as the final shaft result.

Shadow research: [Microsoft: Cascaded Shadow Maps](https://learn.microsoft.com/en-us/windows/win32/dxtecharts/cascaded-shadow-maps) for near-field texel density and stable projections; [NVIDIA GPU Gems: Variance Shadow Maps](https://developer.nvidia.com/gpugems/gpugems3/part-ii-light-and-shadows/chapter-8-summed-area-variance-shadow-maps) for filterable moments and prefiltering; [MJP: Shadow Maps](https://therealmjp.github.io/posts/shadow-maps/) for the four-moment exponential variant and its precision/bleeding tradeoffs. The implementation uses ordinary separable filtering, not summed-area tables.

Scattering reference: [Hillaire, Physically-based and Unified Volumetric Rendering in Frostbite, SIGGRAPH 2015](https://advances.realtimerendering.com/s2015/), particularly transmittance-aware integration and shadowed sunlight. This renderer uses a direct low-resolution ray integral, not Frostbite’s froxel framework. Rejected light-field experiments: warped sine slabs (oblique sheets/moving haze) and separate authored Gaussian shafts (read as sprite effects).

Final WebGL validation: 16.2 FPS (61.8ms mean / 116.0ms p95, 600 RAF samples) at 1280×720 on Mesa Intel HD530/ANGLE. Swimming input passes; no WebGL/render warnings or errors. The debug-only bridge reports its expected unavailable HTTP endpoint on WebGL. Evidence: `artifacts/lighting-final/browser/`. This remains below 30 FPS; do not reuse prior 20–22 FPS measurements as current performance.

## Shadow cutoff, rigid actors and solid columns

The near EVSM clear previously used values outside 0–1 and a tiny negative moment. Defold’s graphics clear API takes 8-bit color channels even for floating-point targets. Both exponential depth warps now use shifted exponent 32 values, with a representable empty-texel clear `(1,1,0,0)`. Near/far solid casters both use back-face culling, and both caster frusta include a 2m guard for future rig deformation. Thin leaves bias their shadow receiver toward the sun to avoid self-shadow acne on the back side.

Visible grass was static while its shadow animated: a stage-shared uniform name let the render override update only one clock binding. Grass, fish and ray shader animation/travel are now removed entirely, as requested. The actor vertex shader has no clocks or sine deformation. Currents, crowd avoidance and rigs will drive these actors later; the mermaid controller still moves the rigid character. Fragment clocks remain for water/caustics, and bubbles retain their separate drift shader.

The web pattern came from projecting the floor caustic network through the volume. A separate static, band-limited irradiance aperture now produces broader, isolated shafts aligned with the sun in world space. It is an artistic surface-focusing approximation, integrated through the existing quarter-resolution volume, rather than beam cards or animated density clouds. Aperture mip filtering includes the integration interval footprint to prevent narrow shafts popping between samples. Filtering logarithms and the projection basis are calculated once per view ray, outside the 64-sample loop.

The broken column stripes were actual holes between six separate drum shells. The shaft is now continuous and capped, with recessed joints, 48 radial samples and no bevel on tiny joint transitions. The finished column has 3,060 triangles, down from 4,178; its open-edge count falls from 774 to zero. Editable Blender source and generator/cache data are updated; unrelated finished meshes are preserved. The world audit still finds 1,157 covered rock hulls and 273 supported plants, with no floating roots.

`python3 tools/render_regression.py artifacts/shadow-repair/actors-final` checks actual visible/shadow actor geometry, time stability, near/far ground shadows and closed column topology. At times 3 and 7, actor silhouettes do not move and overlap 99.9974% between visible/shadow passes. Near/far ground shadow interiors disagree in 0.0021% of eligible wide-view pixels and 0.00019% of close-view pixels; softened edge differences are excluded. The mermaid shadow test has 100% overlap and zero centroid movement at times 3, 5 and 7. Debug modes 7/8 isolate far/near visibility, 9 displays near weight, 10/11 compare actor geometry paths, and 12 identifies sand receivers.

Native controls, boosted boulder contact, all 16 image/structure unit tests and the world audit pass. The frozen opening repeats pixel-identically. Final native detail checks measured 78.1ms mean / 151.5ms p95, 100 draws; earlier runs ranged from 35.9 to 63.7ms mean. Timing varies substantially, and stable 30 FPS remains unmet. No native render/build warnings or errors. Evidence: `artifacts/shadow-repair/delivered/`, `actors-final/`, `mermaid-stability/` and `native/playtest.json`.

Final WebGL build succeeds with no build issues. Swimming input passes, and no WebGL/render warnings or errors occur; the debug bridge reports only its expected unavailable HTTP server. The saved frozen 1280×720 capture measured 15.0 FPS (66.8ms mean / 183.3ms p95, 600 RAF samples). Live samples varied from about 11 to 18 FPS in the same session. Swimming and upward orbit also pass; `sunlight.png` records the moved camera and visible shafts. Evidence: `artifacts/shadow-repair/browser-final/`.

MSAA comparison with identical frozen camera: Display Samples 4 measured 46.54ms, Samples 0 measured 41.16ms, then Samples 4 measured 42.95ms (120 frames each, 100 draws). The 0/4 screenshots are pixel-identical. Display Samples controls window MSAA independently of our single-sample offscreen scene targets, so this option does not smooth scene geometry in the current pipeline. It may add a small cost, but does not explain the confirmed column mesh holes. The user’s setting remains 4. Evidence: `artifacts/shadow-repair/msaa/`; [Defold render target/MSAA documentation](https://defold.com/manuals/render/).


## Scene sampling

Display Samples now controls scene anti-aliasing. The checked-in value is 4. Desktop uses the requested scene-target MSAA count (2/4/8 subject to hardware support); 0/1 disables it. Shadow maps and post-process targets stay single-sampled. Defold resolves multisampled color when switching targets, but its OpenGL backend does not resolve the sampled depth attachment. Desktop MSAA therefore uses a separate unshaded, color-write-disabled geometry pass for the water/upsampling depth texture. The single-sample path skips that pass. Both targets resize with the viewport.

In this engine build, WebGL reports offscreen MSAA unsupported and falls back to one sample. Browser builds therefore use a compact FXAA edge filter in the existing presentation pass when Display Samples exceeds 1, with no MSAA target or extra depth pass. It runs after tone mapping, skips low-contrast pixels and preserves local luminance bounds; it does not alter depth. Browser FXAA is a fallback, not four-sample MSAA. Startup logs identify OFF, MSAA xN or FXAA. Reference: [NVIDIA FXAA white paper](https://developer.download.nvidia.com/assets/gamedev/files/sdk/11/FXAA_WhitePaper.pdf).

Verified native 1280×720 framebuffer A/B: no MSAA measured 39.52ms mean / 88.38ms p95 (100 draws), versus 53.79ms / 109.30ms at four samples (140 draws). This is a real quality/cost tradeoff: about 14.27ms in this run. The architecture mask gains partial edge coverage from 10 to 5,338 pixels; the water-depth diagnostic is pixel-identical. This comparison exercised target resizing as well. Evidence: `artifacts/sampling/compare-1280/`. An earlier resize request settled at 640×360; those figures are kept separately in `artifacts/sampling/compare/` and are not 1280×720 results.

Native close-view captures, boosted boulder contact and all 16 image/structure tests pass. Evidence: `artifacts/sampling/msaa4/`. Earlier window-only MSAA comparisons above predate this fix.

Final WebGL startup confirms `SCENE_AA FXAA`, with no graphics/render warnings or errors (only the expected unavailable debug HTTP bridge). The saved 1280×720 frozen capture measured 15.3 FPS, 65.3ms mean / 117.7ms p95 over 600 RAF samples. The scene remains below 30 FPS on HD530. Evidence: `artifacts/sampling/browser/`.

## Camera-independent sunlight and closer ray detail

The remaining lintel/column edge marks were shadow reception artifacts, separate from the previously closed mesh holes. Closed stone now casts its back surface consistently in both maps (front-face culling); thin actors remain two-sided. The distant PCF uses high-precision coordinates and caster slope bias instead of extrapolating receiver planes across bevel silhouettes. This removes the repeated triangular edge pattern without increasing per-pixel shadow taps.

The distant map previously followed the camera with a fixed -Z offset, so turning could expose its boundary. It is now a cached 2048² full-world static map covering 192m, with the character's changing shadow handled by the existing 24m local EVSM map. Static actors currently do not move. Future currents/crowd simulation must invalidate the cache using `shadow_dirty` when those actors change. This trades additional texture memory for removing the repeated distant caster pass. It is a world cache plus a local detail cascade, not camera-frustum CSM splits.

Photo study: [Dave Fleetham's underwater sunlight photograph](https://pixels.com/featured/sunlight-below-ocean-surface-dave-fleetham.html) and the Getty underwater photograph in [Popular Mechanics](https://www.popularmechanics.com/science/environment/a25781337/ocean-colder-climate-change-little-ice-age/). The visual takeaway is fine shafts within broad illumination, with uneven spacing and a bright surface source. The aperture now has finer isolated peaks and lower energy. Four small aperture quadrature taps filter along each integration interval instead of smearing the whole interval isotropically; no extra shadow samples or full-resolution pass were added. Depth broadening is smaller. Rays remain an artistic, world-space single-scattering approximation.

Expanded native regression passes at forward/backward/side swimming views: static fully lit/umbra disagreements between maps are 0–0.0023% of tested ground pixels. The static comparison excludes the character from casting, since the world cache intentionally omits her. Actor visible/shadow overlap is 99.998%, and rigid actors move zero pixels between times 3 and 7. Normal, shadow-disabled and far-shadow column captures are retained for inspection. Evidence: `artifacts/remaining-artifacts/regression/`, `lighting-final/`.


## 3D steering and deeper exploration

Click the scene to enable mouse steering; **W** supplies forward thrust in the aimed 3D direction, with **Shift** boost. **Tab** releases steering on desktop and browser; browser Escape also releases it. Defold's editor preview reserves Escape for quitting, so Tab is the portable release key. S reverses; A/D and Space/Q remain optional positioning controls. Pitch reaches about ±85°. The mermaid's rigid model smoothly aligns with thrust, accounting for its authored curved head-to-fin axis. No actor vertex deformation or procedural fish/grass motion has returned.

Native pointer capture gives continuous relative aiming. The embedded browser used for testing refuses pointer lock; click-to-steer remains active without holding a button, and steering near a viewport edge while thrusting permits continued turns. Tab, Escape, reset and focus loss release steering. Both surfaces display depth below the water surface; diagnostic captures hide the native HUD.

The authored ruins keep their shallow foundations. Beyond their edges, the seafloor descends through an intermediate ledge to a basin roughly 78m below the old floor, with additional arches, columns, grounded boulders, coral and fish. The closest descent is behind the starting camera: turn around, swim beyond the shelf, then aim down. Travel is no longer clamped to the old shallow volume. The camera follows below the old floor, clips against terrain as well as stone, and body collision accounts for changing orientation while stationary.

`tools/bathymetry.py` generates the visible seabed and the exact triangle-height table in `main/seafloor.lua`. Collision uses the same triangulation, rather than a second analytic surface. Daylight and haze lose brightness and red light with depth, while the upper ruins retain their established illumination. The water integration and shadow caster depth ranges now include the lower basin; the static map covers 192×208m. The old -4.4m shadow discard is removed.

The world has 1,810 scenery instances, below the 2,048 limit. All 1,205 boulders have hulls; all 288 rooted actors are supported. A separate audit finds all 48 new deep boulders intersect the terrain, including those near slopes. Native floor queries at 35 actual mesh-triangle centroids differ by at most 0.0000191m. Steep W climbs/dives, body orientation, mouse steering, release, lower-floor contact and depth brightness checks pass in `tools/exploration_check.py`. The tested water luminance falls from about 125 to 79 to 39 across three depths.

The expanded shadow regression also passes in the deep basin: static near/far fully lit/umbra disagreement is 0% there and at most 0.0029% in the original forward/backward/side views. Visible/shadow actor geometry overlap is 100%, with zero movement at frozen times. Evidence: `artifacts/exploration/shadows-final/`, `grounding.json`, and native captures.

Browser end-to-end input testing swam from the opening shelf to position (-0.22,-67.78,85), then turned back toward the lower ruins; click-to-steer and Tab release pass. Final 1280×720 frozen opening capture measured 17.8 FPS / 56.1ms mean / 116.7ms p95 (600 RAF samples); live opening readings varied around 18–20 FPS. The less crowded lower-basin capture measured 28.8 FPS / 34.7ms mean / 83.5ms p95. These are different camera workloads, not an A/B benchmark. No graphics warnings/errors occur; only the expected unavailable debug HTTP bridge warning is logged. Browser uses the existing FXAA fallback. The opening still misses the HD530 30 FPS target. Evidence: `artifacts/exploration/browser/`.

Final native 1280×720 verification measured 50.13ms mean / 103.06ms p95 over 120 profiler frames, with 94 draws. The prior same-size MSAA checkpoint measured 53.79ms / 109.30ms and 140 draws; timing variance prevents treating the difference as a precise speedup. Cached scenery removes repeated caster draws, while scene MSAA and its preserved-depth pass still carry their documented cost. The 30 FPS goal remains unmet in the opening. Final evidence: `artifacts/exploration/delivered/`; optional vertical hover also preserves the existing heading.
