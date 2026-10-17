# Mermaid — working notes

## Goal and current result

Build an interactive 3D scene matching `Blonde-Mermaid-in-Atlantis-Ruins.png`, with satisfying keyboard/mouse swimming on desktop and browser. Target hardware: Intel HD530 laptop; aim for 30 FPS.

**Historical opening fit before the close-detail pass: 20.16% of pixels within 10 RGB levels per channel (pass112).** Exact matches: 0.0199%; RGB MAE: 9.4601%; SSIM: 0.48273. These are diagnostics, not overall fidelity percentages. Evidence: `artifacts/progress/pass112/`.

The fin is a cupped, closed membrane with shared radial topology and corrected normals. Actor shader warps are removed. Real glTF skeletons now animate the mermaid, small fish, rooted kelp, stingrays and whales. Fixed-step schooling, contact springs and one shared water-current field drive their movement; see the living-world notes below. Sand caustics come from an offline refracted wave ray field.

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
- Browser frozen capture: `/?debug=1&capture=1&width=1280`. F9 writes actual browser evidence to `artifacts/scene/`. Press F9 with the canvas focused to save development evidence. Browser has no engine bridge HTTP; validate separately with one test renderer active.

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

Visible grass was static while its shadow animated: a stage-shared uniform name let the render override update only one clock binding. Grass, fish and ray shader animation/travel are now removed entirely, as requested. The actor vertex shader has no clocks or sine deformation. Currents, crowd avoidance and rigs will drive these actors later; the mermaid controller still moves the rigid character. Fragment clocks remain for water/caustics. The later living-world update moves bubble drift into the shared simulation.

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

The distant map previously followed the camera with a fixed -Z offset, so turning could expose its boundary. It is now a cached 2048² full-world static map covering 192m, with the character's changing shadow handled by the existing 24m local EVSM map. Static actors currently do not move. Moving fish and kelp now use the local dynamic map and are excluded from this cache; fixed scenery changes still invalidate it using `shadow_dirty`. This trades additional texture memory for removing the repeated distant caster pass. It is a world cache plus a local detail cascade, not camera-frustum CSM splits.

Photo study: [Dave Fleetham's underwater sunlight photograph](https://pixels.com/featured/sunlight-below-ocean-surface-dave-fleetham.html) and the Getty underwater photograph in [Popular Mechanics](https://www.popularmechanics.com/science/environment/a25781337/ocean-colder-climate-change-little-ice-age/). The visual takeaway is fine shafts within broad illumination, with uneven spacing and a bright surface source. The aperture now has finer isolated peaks and lower energy. Four small aperture quadrature taps filter along each integration interval instead of smearing the whole interval isotropically; no extra shadow samples or full-resolution pass were added. Depth broadening is smaller. Rays remain an artistic, world-space single-scattering approximation.

Expanded native regression passes at forward/backward/side swimming views: static fully lit/umbra disagreements between maps are 0–0.0023% of tested ground pixels. The static comparison excludes the character from casting, since the world cache intentionally omits her. Actor visible/shadow overlap is 99.998%, and rigid actors move zero pixels between times 3 and 7. Normal, shadow-disabled and far-shadow column captures are retained for inspection. Evidence: `artifacts/remaining-artifacts/regression/`, `lighting-final/`.


## 3D steering and deeper exploration

Click the scene to enable mouse steering; **W** supplies forward thrust in the aimed 3D direction, with **Shift** boost. **Tab** releases steering on desktop and browser; browser Escape also releases it. Defold's editor preview reserves Escape for quitting, so Tab is the portable release key. S reverses; A/D and Space/Q remain optional positioning controls. Pitch reaches about ±85°. The mermaid's rigid model smoothly aligns with thrust, accounting for its authored curved head-to-fin axis. That checkpoint kept actors rigid; the living-world update below replaces the temporary setup with actual skeletal rigs.

Native pointer capture gives continuous relative aiming. The embedded browser used for testing refuses pointer lock; click-to-steer remains active without holding a button, and steering near a viewport edge while thrusting permits continued turns. Tab, Escape, reset and focus loss release steering. The game now has no HUD or on-screen controls. Browser diagnostics require the explicit `?debug=1` development option.

The authored ruins keep their shallow foundations. Beyond their edges, the seafloor descends through an intermediate ledge to a basin roughly 78m below the old floor, with additional arches, columns, grounded boulders, coral and fish. The closest descent is behind the starting camera: turn around, swim beyond the shelf, then aim down. Travel is no longer clamped to the old shallow volume. The camera follows below the old floor, clips against terrain as well as stone, and body collision accounts for changing orientation while stationary.

`tools/bathymetry.py` generates the visible seabed and the exact triangle-height table in `main/seafloor.lua`. Collision uses the same triangulation, rather than a second analytic surface. Daylight loses brightness and red light with world depth. Haze integrates the available scattered light along the complete sightline, split at the shallow illumination plateau; it no longer uses camera depth as a multiplier for all distant water. Viewing the basin from above therefore shows dim deep water, while looking upward can still reveal the bright surface. Distance extinction uses actual sightline length. The existing quarter-resolution shafts also evaluate depth attenuation at their world-space samples. No additional full-resolution pass or ray-march steps are added. The water integration and shadow caster depth ranges now include the lower basin; the static map covers 192×208m. The old -4.4m shadow discard is removed.

The world has 1,810 scenery instances, below the 2,048 limit. All 1,205 boulders have hulls; all 288 rooted actors are supported. A separate audit finds all 48 new deep boulders intersect the terrain, including those near slopes. Native floor queries at 35 actual mesh-triangle centroids differ by at most 0.0000191m. Steep W climbs/dives, body orientation, mouse steering, release, lower-floor contact and depth brightness checks pass in `tools/exploration_check.py`. The tested water luminance falls from about 125 to 79 to 39 across three depths.

The expanded shadow regression also passes in the deep basin: static near/far fully lit/umbra disagreement is 0% there and at most 0.0029% in the original forward/backward/side views. Visible/shadow actor geometry overlap is 100%, with zero movement at frozen times. Evidence: `artifacts/exploration/shadows-final/`, `grounding.json`, and native captures.

Browser end-to-end input testing swam from the opening shelf to position (-0.22,-67.78,85), then turned back toward the lower ruins; click-to-steer and Tab release pass. Final 1280×720 frozen opening capture measured 17.8 FPS / 56.1ms mean / 116.7ms p95 (600 RAF samples); live opening readings varied around 18–20 FPS. The less crowded lower-basin capture measured 28.8 FPS / 34.7ms mean / 83.5ms p95. These are different camera workloads, not an A/B benchmark. No graphics warnings/errors occur; only the expected unavailable debug HTTP bridge warning is logged. Browser uses the existing FXAA fallback. The opening still misses the HD530 30 FPS target. Evidence: `artifacts/exploration/browser/`.

Final native 1280×720 verification measured 50.13ms mean / 103.06ms p95 over 120 profiler frames, with 94 draws. The prior same-size MSAA checkpoint measured 53.79ms / 109.30ms and 140 draws; timing variance prevents treating the difference as a precise speedup. Cached scenery removes repeated caster draws, while scene MSAA and its preserved-depth pass still carry their documented cost. The 30 FPS goal remains unmet in the opening. Final evidence: `artifacts/exploration/delivered/`; optional vertical hover also preserves the existing heading.


## Living world and deep landmarks

Normal desktop play has no text, labels, buttons or loading overlay. Browser play adds only a fullscreen icon and an invisible performance toggle; touch regions have no visible controls. Click to steer, W to swim, Shift to boost and Tab to release still work; controls remain documented here.

`tools/rig_assets.py` exports actual glTF skins, inverse bind matrices, two-bone vertex weights and sampled joint tracks. The mermaid has 21 joints through the spine, chest, head, shoulders, elbows, wrists, tail, separate flukes and four-part hair chain. A vertical dolphin stroke travels down the body and tail, with sculling arms, delayed wrists and hair follow-through. Smoothed speed selects swim, glide or idle actions with 0.55s transitions; cadence follows thrust. Heading has angular inertia, turns induce banking, and released thrust coasts rather than stopping abruptly. Fish have three-joint tail rigs. Plants have five-joint rooted stem chains. These are skeletal poses uploaded by Defold, with shared skinning code for visible, depth and shadow passes. Static geometry keeps its separate rigid vertex path. Editable armatures/actions are saved as `assets/source/*-rig.blend` by `tools/save_living_rigs.py`.

`main/currents.lua` supplies a continuous, gently reversing world-space water velocity to the player, schools, foliage and bubbles. `main/life.lua` advances schools at 10 Hz and springs at 20 Hz. All 248 small fish use body-size personal space, alignment, gentle cohesion, distributed school goals, player avoidance and predictive stone avoidance; a symmetric spatial-hash clearance correction prevents fish bodies overlapping, and final positions are projected outside the same convex stone volumes used by the player. Fish interpolate positions between simulation steps; distant fish update their tail poses and headings at 10 Hz. Frozen captures skip unchanged simulation/pose writes. Numeric spatial hashes bound neighbor/stone searches without creating temporary coordinate strings each tick. The 137 kelp instances bend through damped angular springs driven by current and nearby bodies; roots stay pinned. Each plant currently has one coupled bend degree of freedom across its joint chain, rather than independent leaf physics.

A pool of 65 white, transparent billboard bubbles is recycled between six fixed vents and speed-dependent swimming emissions. Buoyancy, shared-current advection and lifetime fade run in the simulation; the bubble vertex program only faces the camera. The player collision proxy includes extra room for the swimming tail's envelope.

Only the mermaid creates attachment game objects for its bones. Fish and plants keep their skeletal poses inside the rig system with `create_go_bones: false`, avoiding roughly 1,400 otherwise unnecessary game objects. The world has 1,945 scenery instances and remains within the existing 2,048 limits, including the mermaid's attachment bones. Moving fish, foliage and the player cast through the local dynamic shadow map; the full-world cache contains fixed stone and sand. The two rays now cruise with skeletal wing strokes and a small response to the shared current; see the sea-animal notes below. Far foliage/animal shadows fade with the local map's existing transition.

The descent now includes a contour avenue on supported masonry, a lower circular sanctuary and a buried gateway with pottery cargo. Shared amphora meshes, coral, kelp, rubble and additional schools provide smaller discoveries. `assets/source/deep-landmarks.json` records their locations. Regeneration seats pottery and all rooted actors against final supporting geometry; the avenue's buried plinths have convex collision hulls.

Validation commands: `python3 -m unittest tools.test_living_rigs tools.test_image_diff tools.test_structure_check -q`, `python3 tools/check_world.py`, `python3 tools/life_check.py artifacts/living-world/native-final`, and `python3 tools/render_regression.py artifacts/living-world/shadows --attach --keep-running`. The rig tests skin actual vertices to verify fixed roots, normalized nonnegative weights and vertical fin displacement. Runtime checks measure bone-relative motion, real thrust/wake emission, crowd collision, player/plant contact, deterministic frozen captures and deep views.


The final world audit covers 1,227 rock/foundation hulls and 352 rooted plants, corals and pots, with no uncovered hulls or floating roots. All 19 rig/image/structure tests pass. Native tests confirm deterministic frozen captures, about 0.59m of fin motion relative to the peduncle, schooling without stone penetration, plant contact, swimming bubble emission and lower-floor contact. The complete shallow/deep shadow regression has 100% visible/shadow silhouette overlap at both times and at most 0.00285% disagreement in static ground interiors. The final shader also passes full-stroke side-view silhouette comparisons at two phases. Evidence: `artifacts/living-world/optimized/`, `shadows/`, and `final-check/`.

Final isolated native 1280×720 profiling: live simulation **52.98ms mean / 106.90ms p95** over 120 frames, averaging 90.66 draws; frozen opening **49.37ms / 106.76ms** over 90 frames. The earlier opening checkpoint was 50.13ms mean with rigid actors. These runs vary; the final live/frozen comparison adds about 3.6ms in this session. The skeletal shader shares matrix fetches with normals and skips the second matrix for single-influence vertices. No graphics or script errors were logged, and the native preview is left running.

Final WebGL build has no build issues. Default play exposes only the game canvas. Real W/Shift input, steering release, visible swimming and white wake bubbles pass with no runtime errors. Browser uses FXAA. The final frozen 1280×720 sample measured **12.64 FPS / 79.09ms mean / 135.20ms p95** over 600 RAF samples; live moved views read roughly 10–12 FPS. This is slower than the previous 17.8 FPS frozen checkpoint, and the HD530 30 FPS target remains unmet. CPU-side school/pose update reductions did not recover that browser cost; further browser rendering work is still needed. Evidence: `artifacts/living-world/browser-final/`. Browser diagnostics remain explicitly opt-in and are absent during normal play.


## Swim and depth refinement

`tools/swim_refinement_check.py` verifies fixed views of the same basin from above, the ledge and deep water; bright surface visibility from below; actual wrist/elbow, hair/head and fin/peduncle relative motion; full-stroke visible/shadow silhouette agreement; release-to-glide behavior; and sustained all-school spacing and stone clearance. It records isolated live/frozen frame timings. The unit rig checks also skin real hand and hair vertices through a complete stroke, so merely adding animation tracks cannot satisfy them. Run `python3 tools/swim_refinement_check.py artifacts/swim-refinement/native`.

The final checks pass with 20 unit tests, 100% full-stroke visible/shadow silhouette overlap, about 0.46–0.47m wrist motion relative to the elbows, 0.76m hair-tip motion relative to the head, and 0.70m fin motion relative to the peduncle. The three sustained crowd samples have zero fish overlaps or stone penetration; nearest-neighbor p10 is about 1.30–1.32m, with about 0.85m minimum body-envelope clearance after settling. Basin view luminance is about 53 from above, 17 at the ledge and 9 inside; the sun remains visible from below. Releasing thrust transitions through the glide clip. Evidence: `artifacts/swim-refinement/native/`.

Haze uses an endpoint form of the same height-dependent scattering integral, reusing the plateau crossing rather than evaluating two complete intervals. The six fixed comparison views change by less than 0.00006 RGB levels per channel on average. No render pass, sample count, fish count or mesh triangle count was added. Final isolated native profiling at 1280×720 measures **66.20ms mean / 126.48ms p95 live**, and **61.48ms / 124.80ms frozen**. A same-session old-camera-haze comparison with the new rig measured 52.31ms frozen; the corrected lighting still has a material cost. The first unoptimized path integral measured 69.65ms frozen. These results remain below the HD530 30 FPS target; they are not a claimed performance improvement over the previous living-world checkpoint.

The final WebGL bundle has no build issues or runtime render errors. Real swimming, mouse steering/release and a descent to the ledge pass; normal play exposes only the game canvas. The final frozen 1280×720 sample measures **13.71 FPS / 72.94ms mean / 125.20ms p95** over 600 RAF samples, using FXAA on the HD530. Live moved views remain around 10–13 FPS. Browser evidence is in `artifacts/swim-refinement/browser/`; native preview is restored after browser verification.


## Stingrays and distant whales

The two existing stingrays use seven-joint rigs with synchronous, delayed wing-tip strokes and flexible tails. Their world-fixed loops stay around their original swimming areas. Rays use the same skinned visible, depth and near-shadow paths as the other animals; the old rigid category-6 debug override is removed. The right wing's reversed surface normals are corrected.

Three shared-mesh whales, about 33–38m long, cruise farther out as hazy silhouettes. Two start roughly 145–180m from the opening; the third passes beyond the deep basin. They use eight-joint rigs with vertical tail/fluke strokes and quieter pectoral movement. Normal water extinction supplies their distance fade. Paths are independent of the camera, with a small current response. Far joint poses update at 10 Hz while movement stays smooth. No actor shader sine deformation, extra rendering pass, texture, or per-bone game object is added. The whale mesh has 1,268 triangles; there are only three new model instances. The reef's existing 1,945 instances and the three whales remain within the existing limits.

`tools/sea_animals.py` authors the whale geometry and routes; `main/ocean_motion.lua` drives all five animals. `tools/build_assets.py` regenerates the geometry, skins, route table and separate whale collection. Editable sources are `assets/source/ray-rig.blend` and `whale-rig.blend`. The complete whale loops are checked with conservative swept envelopes against stone, terrain and the water surface.

Run `python3 -m unittest tools.test_living_rigs tools.test_ocean_routes tools.test_image_diff tools.test_structure_check -q` (23 tests) and `python3 tools/ocean_check.py artifacts/ocean-animals/native`. Actual skinned vertices verify vertical ray wingbeats and whale fluke movement; native tests confirm all five animals travel, visible/shadow silhouettes overlap 100% at both checked phases, and no graphics/script errors occur. Native 1280×720 live profiling measures **65.66ms mean / 128.14ms p95**, averaging 95.48 draws, close to the previous 66.20ms live checkpoint. This is not a speedup claim; the HD530 30 FPS goal remains unmet. Evidence: `artifacts/ocean-animals/native/`.

The WebGL bundle also passes with no build or render errors. A 600-sample frozen 1280×720 run measures **13.52 FPS / 73.98ms mean / 133.50ms p95** using FXAA; live readings remain around 10–13 FPS. Actual browser swimming and animal motion pass. An additional 180-pose ray-loop check finds no deformed vertices within 0.35m of nearby stone. Browser and clearance evidence is in `artifacts/ocean-animals/`. Native preview is left running.


## Level support and deeper habitats

The architecture support audit now checks each exported column base and arch pier, the circular walls, and the lower feet of the added foundations. It excludes the actor's own triangles, so a column cannot validate against its own capital. All 49 structures pass. Thirty-three shared masonry footings continue into the continuous seabed and have geometry-derived convex collision hulls. Four narrow rock props are replaced by these foundations. The main circular wall is aligned with a slightly wider, deeper supporting arcade, closing its unsupported rear edge. All 1,256 rock/foundation hulls and 376 rooted actors pass the exported-geometry audit.

Four small habitats along the descent and around the lower basin add 12 skeletal plants, 12 corals/sponges and 20 fish. Their roots are seated against final scenery. Fish join the existing current-driven, spaced schools and stone avoidance. The total is 268 small fish and 149 skeletal plants. There are 2,018 reef instances; including three whales, the three main actors and all mermaid bone attachments gives a conservative 2,045 game objects, within the existing 2,048 limits.

Water now has actual broad, crossing wave displacement, with a total amplitude bounded by 0.85m. A 3m shared grid covers the swimming area; coarse outer skirts extend into the haze. Its 13,689 indexed vertices replace an initial 53,824-vertex grid with unused UV seams. The optical shader receives the same wave gradients, layered with finer filtered ripples. Both visible and MSAA depth rendering use `surface.vp`, with a dedicated vertex clock; all actor animation remains skeletal. The far surface haze matches the open-water background. No reflection render or additional shadow pass is introduced; native depth rendering adds one water-only draw.

Run `python3 tools/check_world.py`, the existing 23 rig/route/image/structure unit tests, and `python3 tools/level_tour.py artifacts/level-polish/final-native`. The tour captures supports, both deep levels, grazing waves and the bright sun window at two phases, checks actual depth motion, and checks live fish spacing before native profiling. Evidence: `artifacts/level-polish/`.

Final native checks report no script or graphics errors. Actual sampled surface depth changes between both wave phases (top-region mean differences 4.24 and 1.68 RGB levels in the depth diagnostic), confirming vertex displacement reaches the MSAA depth path. All three live-school samples have zero body overlaps or stone penetration; nearest-neighbor p10 remains about 1.29–1.30m. The final 1280×720 live sample measures **67.77ms mean / 130.97ms p95**, averaging 98.02 draws, compared with the preceding 65.66ms / 128.14ms checkpoint. Timing varies, and the HD530 30 FPS target remains unmet.

The final WebGL build has no build issues or runtime warnings/errors. Actual input tests climb to the sunlit surface and descend to the lower sanctuary, with the new plants and schools visible. The saved frozen 1280×720 sample measures **12.72 FPS / 78.65ms mean / 153.80ms p95** over 600 RAF samples, compared with the preceding 13.52 FPS / 73.98ms sample. Live moved views read about 10–12 FPS; the added detail has a small measured cost rather than a speedup. Browser evidence is in `artifacts/level-polish/browser/`; native preview is restored afterward.


## Distant basin terrain

Nine uneven massifs and escarpments extend the seabed beyond the playable ruins and basin. Their centers lie roughly 160–370m from the opening, with broken crests, lower saddles and open channels between them. They stay below the water surface and use the existing depth-dependent extinction, so the land reads as distant blue silhouettes. They are fixed world geometry with ordinary parallax.

The relief is part of the existing seabed model. A coarse 16m outer grid replaces the previous almost-flat outer skirt; the inner collision triangles keep their 4m spacing. The mesh has 20,800 triangles, up from 12,788, with no new instance or draw call. Opaque vertex alpha marks distant faces for broad sun/ambient lighting and normal haze, skipping close caustic/detail textures and shadow fetches. Nearby terrain, actors and their lighting retain their existing path.

Every sampled reachable floor point, including a body margin, is unchanged. The complete whale route envelopes also have zero terrain-height change. The exported terrain has no interior open edges; physics-table vertex heights match the visible mesh within 0.0000043m. All 49 architecture supports, 376 rooted actors and 1,256 rock/foundation hulls still pass; the existing 23 tests pass. Evidence: `artifacts/distant-terrain/geometry.json` and the world audit. `tools/distant_terrain_check.py` captures the opening, west/east/north/south views and two deep-basin directions, then profiles live native rendering.

Native inspection confirms the ridges are visible through the haze from all four directions and above the deep basin. No build/runtime warnings or errors occur. Live native 1280×720 profiling measures **65.91ms mean / 124.81ms p95**, with **98 draws**, versus the previous 67.77ms / 130.97ms sample and 98.02 draws. These runs vary; this is comparable cost rather than a speedup claim, and the HD530 30 FPS target remains unmet. Evidence: `artifacts/distant-terrain/native/`.


## Web controls and browser floor compatibility

The expanded seabed initially exceeded the browser backend's 16-bit model-index limit and was rejected entirely. The outer grid now uses 16m spacing: **62,400 vertices / 20,800 triangles**, below 65,536. Asset generation and the terrain check explicitly guard this limit. Nearby floor geometry, roots and collision remain intact.

Holding a finger on the left half supplies forward thrust in the current 3D aim direction. Swiping the right half changes yaw and pitch. Defold's `TOUCH_MULTI` binding and `main/touch_controls.lua` own these controls; contact roles stay fixed until release, simultaneous fingers work independently, and source-tagged emulated mouse events are ignored. Cancellation, focus loss and resize clear the touch state. Keyboard and mouse controls remain available.

The invisible top-right input region in `main/game_ui.lua` toggles **Defold's built-in profiler** in its compact frame/draw-call view, with a wall-clock FPS and milliseconds-per-frame line drawn through the engine's debug-text path. The invisible control creates no GUI component, node, texture or button drawing. The explicitly allowed fullscreen button lives in the browser shell, just to the left; it enters/exits fullscreen and resizes the canvas with the correct aspect ratio. There is no HTML profiling overlay or HTML movement/steering handler. The shell contains browser startup, canvas sizing, fullscreen API integration and explicit development capture plumbing.

Five Lua tests exercise independent hold/swipe contacts, release/cancel behavior, portrait scaling, the actual game input handler, emulated-mouse rejection, keyboard coexistence and tapping the invisible profiler corner while thrust remains held. Run the existing tests plus `python3 -m unittest tools.test_touch_controls -q` (28 total). Physical multi-touch hardware is not available to the browser automation session; these tests exercise the real Lua handler with multi-contact packets.

Browser development captures now use **F9** while `?debug=1` is present. They save the real game canvas (including the engine profiler when enabled) and timing/state evidence to `artifacts/scene/`. No development capture button is drawn in HTML or in the game.

The final compatible terrain and Lua controls pass native keyboard swimming (speed 4.38m/s) and log no warnings or errors. Final native 1280×720 profiling measures **65.15ms mean / 127.05ms p95**, with **98 draws** while profiling information is hidden. Evidence: `artifacts/distant-terrain/final-native/` and `final-performance/`.

Final browser inspection confirms the restored sand floor, readable in-game FPS text, the invisible corner toggling profiling on/off, and HTML fullscreen entering/exiting correctly. The profiler is enabled synchronously through Defold’s profiler API; its minimized view retains resource counters. No runtime warnings/errors were logged. Screenshot evidence: `artifacts/distant-terrain/browser/final-profiler/`.

The development F9 capture queues a microtask at the end of the current engine frame, before WebGL discards its backbuffer; scheduling the copy in the next animation frame produced black captures. Final on/off PNGs were inspected and contain the actual rendered scene. Timing samples in these UI-check captures include toggling the profiler and are not isolated performance benchmarks.
