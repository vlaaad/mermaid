# Agent working memory — Mermaid

## Objective and constraints
- Build the actual controllable 3D scene as close as practical to `Blonde-Mermaid-in-Atlantis-Ruins.png`.
- Desktop + browser, keyboard/mouse. 30 FPS is sufficient on this old laptop. Prioritize reference look and feel; use profiling to catch regressions, not chase 60 FPS. Share/instance meshes; NEVER bake fish, rays, vegetation, or other future actors into scenery.
- README is agent memory: maintain concrete state, commands, pitfalls, measurements, and next work as the project evolves. Do not rewrite as marketing/user documentation.
- User authorizes local Git commits. Repository now exists; user supplied initial/prep commits b090512 and 2a54da5. Preserve their work and commit our scene separately.
- Do not flatten the reference into a backdrop to improve the diff. The opening frame must come from the playable 3D world.

## Environment / access
- CWD `/home/vlaaad/Projects/mermaid`; running Defold 1.14.0 at `http://127.0.0.1:$(cat .internal/editor.port)`.
- `.internal/editor.token` is a secret local bearer token for `/eval` and `/bob`; do not print it.
- Running editor HTTP + engine + Blender Snap require unsandboxed execution here. Use `exec_command` escalation for these; don't launch another editor unnecessarily.
- Blender 5.2.2 LTS: `/snap/bin/blender` works outside sandbox. Meshes are glTF/GLB and editable there.
- Official builtins/shaders and protobuf classes are in `/opt/Defold/packages/defold-a81dbb0478e8b73931dc2d671563204f6ac0ef82.jar`. Read the installed source/schema first instead of guessing APIs.
- System Python includes Pillow + NumPy. No SciPy/skimage needed by project tools.

## Current implementation (update after verification)
- `tools/build_assets.py`: deterministic seed 73 geometry/layout generator. Y-up, meters, forward -Z. Emits vertex-colored GLBs, `.model`/`.go` resources, `main/world.collection`, `main/obstacles.lua`, and `assets/generated/manifest.json`.
- Geometry authored procedurally: 4 shared rock variants, fluted column, segmented arch, circular ruin, kelp cluster, coral/sponges, fish/ray, mermaid, seabed, surface, particles.
- Current generated world instances + player are recorded in `assets/generated/manifest.json` (vegetation/fish geometry reduced after profiling). Broad cliffs are instanced rocks; fish and kelp share meshes/materials. Static indexed primitives are not required; current generated GLBs use explicit triangles.
- `render/underwater.*`: perspective custom render pass, local-space instanced world-matrix shader, vertex colors, per-category vertex animation, shared cellular caustics texture, soft sun shadows, hemisphere/sand bounce fill, depth fog, and depth-aware volumetric water (no shaft cards).
- `main/main.script`: inertial swimming, camera-relative WASD, rise Space/E, dive Ctrl/Q, Shift boost, mouse drag orbit, R reset, P profiler; sphere/AABB sliding and a broad-phase-filtered segment/AABB camera arm test with stationary caching. Architecture is collidable (197 terrain/column/arch/ring boxes).
- Display 1280x720, high_dpi=0 to avoid uncontrolled DPR cost. Scene uses perspective 59deg vertical FOV.
- Scene renders on native and WebGL. Do not call it a close art match yet: mermaid art, rock variation, and composition remain visibly simpler than reference.

## Run / capture / inspect
```
python3 tools/build_assets.py
python3 tools/automation.py --build --focus --key W --hold 0.5
python3 tools/automation.py --build --focus --profile 120 --scale 1
```
- Wrapper: pinned Automation Bridge 2.5.0; copied managed `automation-bridge-python/`. Do not edit wrapper or store game code there. Import only package-root `editor`, `engine`.
- Reuse editor: `PYTHONPATH=automation-bridge-python python3 ...`; `p=editor.open_project('.',start_if_needed=False)`.
- Manually authored `.go`/`.collection` must be parsed via `p.preview.render(resource, resolution_multiplier=.5)` before building; native runtime is still the visual truth.
- `g=p.build_and_run(focus=True,timeout=180)`; screenshots atomic: `shot=g.screenshot(after_frames=2)`; save `shot.read_bytes()`.
- Use focus=True for profiler/control timings. Initial native graphics warmup/occlusion can throttle frames. `engine.run_while_iconified=1` is set; initial ready timeout45sec accounts for shader/OS warmup. Close the browser game while profiling native, and close native while profiling browser.
- `g.close()` releases this client and leaves the engine running; `g.close_engine()` terminates it. Do not close an engine used by another session.
- `g.command('mermaid.capture',{})` resets opening pose/camera/time=3 and freezes animation; `mermaid.resume` resumes. `mermaid.reset` takes `{freeze:bool}`. Any movement unfreezes.
- `g.state('mermaid')` exposes ready, frozen, time, speed, position, camera, heading input, frame count and smoothed frame_ms. Guard Lua APIs with `if automation_bridge then`.
- Current images: `artifacts/scene/opening.png` (authored scene), `artifacts/automation/latest.png` + `latest.json` (generic helper).

## Browser path / profiling
- Preferred build without launching a separate Firefox instance:
```python
p.bob(options={'platform':'wasm-web','architectures':'wasm-web','archive':True,'variant':'debug',
               'bundle-output':str((p.root/'artifacts/browser').resolve())},commands=('build','bundle'),timeout=240)
```
- Bob must bundle OUTSIDE `build/` (reserved by Defold); the verified output is `artifacts/browser/mermaid/`. `p.build_and_run_html5(timeout=180)` remains a fallback but opens another Firefox tab and writes `build/default_html5/__htmlLaunchDir/mermaid/`.
```
python3 tools/serve.py
```
- Inspect `http://127.0.0.1:8765/` with CUA browser tools. Reload after each rebuild.
- Bridge debug HTTP is unavailable in WebAssembly. Use browser UI input and screenshots. Game publishes `window.mermaidState` for dev inspection, not engine introspection via HTTP.
- Native profiler: `g.profiler.capture(frames=120,warmup_frames=5,thread='Main',timeout=45)`, then `.scopes()`, `.counters()`, `g.profiler.resources()`. Always filter Main; otherwise '120 frames' includes profiler/worker threads.
- P toggles built-in profiler UI. Browser runtime performance must be measured separately. Budget33.3ms; report p95/spikes and draw calls, not just average FPS. `?debug=1` shows a rolling600-sample RAF panel and state; `?capture=1` hides HUD/freezes opening time; `?width=1920` forces full-HD framebuffer; `?trace=1` enables Defold Performance Timeline scopes (profiling overhead, use only when recording).

## Visual measurement
```
python3 tools/image_diff.py Blonde-Mermaid-in-Atlantis-Ruins.png artifacts/scene/opening.png --regions tools/reference_regions.json
python3 -m unittest tools.test_image_diff -v
```
- Emits `artifacts/image-diff/index.html` (wipe + regional table), `comparison.png`, fixed-scale `heatmap.png`, highlighted overlay, hashes/settings/metrics JSON.
- Default analysis width960, matching aspect required within .5%. Explicit `--fit contain` letterboxes mismatch and records warning. Never silently crop/warp/grade to lower error.
- RGB MAE = average absolute RGB channel error /255 x100. SSIM uses 7x7 sample covariance, RGB mean; best1, can be negative. Changed pixels default mean RGB error>10/255. Blurred MAE is only coarse palette/layout diagnostic.
- `--max-mae-percent 10` is an optional MAE-only gate, not 90% fidelity. Global score can hide a missing small subject; check mermaid/ruin ROIs and actual images.
- Empty black baseline at960x540: RGB MAE39.2437%, SSIM0.0021356. Reference self-check MAE0/SSIM1. Seven known-value tests pass.
- Matching concept art below10% pixel MAE is a stretch/exploratory target, not promised. First prioritize camera composition, silhouettes, character, water/light. Once accepted, use actual rendered opening frame for tighter regression testing.

## Art direction / lighting checkpoint — 2026-10-15
- User's latest priorities: old laptop, 30 FPS acceptable; focus on look/feel, not 60 FPS. Fish and other future actors must remain independent. Current layout: 571 independent instances, 197 collision boxes. No fish fields, static chunk baking, or shaft cards remain. Shared meshes still instance.
- Compared reference against actual runtime. Primary deficits: uniform blue light, absent cast/contact shade, flat-looking ray planes, sparse material detail and simple procedural character/rocks. Lighting alone cannot close the geometry/art gap.
- Render passes: 1024² sun depth map; opaque scene with 3×3 filtered sun shadows; quarter-resolution 32-step world-space water scattering; depth-aware 4-tap upsampling + contact shading + present. Scene RT capped1920×1080. Depth attachments MUST set `flags=render.TEXTURE_BIT` and must not be transient when sampled later.
- Shadow pass uses the SAME animated vertex shader as the opaque pass, with separate caster predicates/constants for stone0, kelp1, fish2, mermaid3, ray6. Surface4 and dust7 do not cast. Thus fish/tail/kelp deformation and future GO movement retain matching shadows.
- Sun direction normalize(.35,.90,-.24), surfaceY26; caustics projection and scattering use the same direction. Scattering integrates camera→opaque hit, clipped at80m, with exponential extinction and animated surface apertures. This is an art-directed single-scattering approximation, not full GI. Indirect fill approximates sky/sand bounce analytically.
- New looser hair locks, fuller kelp, mineral mottling, brighter coral fill, fewer gold fish, extra floor ruins, and foreground pillar clearance around the ring. Still procedural prototype quality; don't describe as a close reference match.
- `mermaid.lighting {mode:0}` normal; mode1 depth,2 scattering,3 sun visibility,4 world position. Exposed through native bridge, not normal game UI. Debug views saved under `artifacts/lighting/`; before frame is `before.png`.
- Frozen native comparison: RGB MAE11.8134%, SSIM0.48573, blurredMAE9.4608%. Previous pre-lighting frame~11.74%/0.490. New lighting is spatially more coherent, but the overall metric has not improved. Do not claim the10% target is reached or adjust comparison to force it.

## Verified checks and pitfalls
- Latest `python3 tools/playtest.py` passed: identical frozen captures, W3.65m, boost7.17m (1.96×), rise2.70m, drag orbit1.20rad. Actual profiler50 draw calls; native Main Frame mean47.12ms/p9593.13ms during profiling at2560×1440 presentation. This is a regression diagnostic, not a browser FPS claim. Earlier measurements varied widely with GPU load/focus; don't use the earlier3ms CPU scope as real frame rate.
- `python3 -m unittest tools.test_image_diff -q`: 7 known-value tests pass. Generator / playtest / server compile as Python. Native and Bob HTML5 builds pass.
- Capture waits for `mermaid.ready` and warmup; initial OS/window resizing can change captures. Warmed frozen frames are pixel-identical.
- Native .resize/window_width settings did not override this OS scale2 framebuffer. Read actual `g.screen()` dimensions; renderer caps the world target and presents to the physical window.
- glTF imports fullscreen UVs flipped vertically. Every RT sampling pass restores V. First RT iteration inverted the scene; never fix screenshots after capture. Inspect actual native AND browser after renderer changes.
- All generated GLB triangles need unit normals, colors[0,1], and no degenerate pole/leaf-tip triangles. Defold validates these strictly. Generator clamps/discards appropriately.
- Multiple game tabs/native engines distort laptop GPU measurements. Close agent-created extra renderers; do not terminate user browser processes. Native `g.close()` only releases bridge, use `g.close_engine()` to stop our engine.
- Browser keys: documented Playwright canvas locator `.press('w')` reaches controller; `Tab.pressKey()` was unreliable. Controller preserves80ms tap intent so short synthetic taps survive slow frames.
- Browser evidence: `/?debug=1&capture=1&width=1280`, click **Save frame and timings**. Actual canvas PNG→`artifacts/scene/browser.png`, state/RAF samples/backend→`browser-metrics.json`. Never substitute a native image. Server accepts same-origin loopback capture POST only. Black canvas readback retries20 frames then reports unavailable.
- `[hidden]{display:none!important}` is necessary; #loading display:grid otherwise overrode hidden.
- Browser RAF pacing uses `display.update_frequency=0`; native configured60 cap is a ceiling, not a requirement. Timeline scopes only via `?trace=1`, with overhead. Renderer capture fixtures freeze animation but normal play resumes on input.
- Controller idle collision skip + camera stationary cache / broad phase retained. Baking experiments increased memory/vertex traffic without a web FPS gain and were discarded. Never reintroduce actor baking to chase performance.

## Research used for this lighting pass
- NVIDIA GPU Gems3, [Volumetric Light Scattering](https://developer.nvidia.com/gpugems/gpugems3/part-ii-light-and-shadows/chapter-13-volumetric-light-scattering-post-process): scattering must depend on travel through the medium and occlusion; sunlight paths parallel in world space. Our implementation uses depth reconstruction + world-space integration, not its screen-space radial-blur algorithm.
- [Penrose underwater rendering, GDC2018](https://media.gdcvault.com/gdc2018/presentations/devon_penney_penrose_water.pdf): reference for volumetric underwater look and translucent/FX integration.
- [Defold render API](https://defold.com/ref/render-lua/) / [render pipeline](https://defold.com/manuals/render/): texture-backed depth attachment flags, sampler bindings, material overrides, RT lifetime.

## Next work (art first)
1. Inspect newest browser/native frames alongside the reference. Main gap is now sculpted geometry/material quality: weathered broken rock silhouettes, ruins integrated into terraces, less uniform block scale.
2. Refine mermaid anatomy, posed hands/arms, organic hair clumps/tips, curved fluke silhouette and scales. Current generator is an editable starting point; Blender5.2.2 is available for real sculpt/model work. Keep controller separate from mesh authoring.
3. Improve surface light/refraction, broad value composition, natural kelp motion, local color accents; adjust rays from actual moving-camera views, not only opening frame. Preserve depth-aware integration.
4. Profile only to catch meaningful regressions against the30 FPS budget on this device; prioritize visual gains over60 FPS optimization. Browser profiling/capture results below are the current evidence, not historical benchmarks.

## Current browser evidence
- Bob HTML5 build succeeds without launching Firefox. Actual browser screenshot: `artifacts/scene/browser.png` (1280×720). At capture: 600 RAF samples, mean27.37ms /36.54 FPS, p9566.70ms, trace disabled, ANGLE Intel HD530. Average clears30; spikes remain. Do not claim locked30 or60.
- Browser W key reached input and changed Z4.00→3.99 immediately, with frozen false/speed.35m/s; full held-key/boost/vertical/orbit tests passed natively.
- Browser reference diff: MAE11.8050%, SSIM0.48127, coarse9.43657%. Report `artifacts/browser-diff/index.html`; native report remains `artifacts/image-diff/index.html`.
- Normal playable tab is `http://127.0.0.1:8765/`. Local preview was relaunched detached (`subprocess.Popen(...,start_new_session=True)`) because a long-lived exec session received SIGTERM and broke capture POST. PID in `artifacts/server.pid`, logs `artifacts/server.log`. Before relaunch, inspect stored PID/port; avoid duplicate servers. Stop only the known agent-owned server when required.

## Rollback and user feedback — 2026-10-16
- User explicitly requested rollback of the rejected visual pass. Commit c424f31 reverts 7e66368; scene, renderer, assets, controller and tools are restored to 913f1fb. Do not reapply its depth prepass or metric-driven palette/layout fitting.
- Rejected build showed blue missing surfaces in animated hair, tail and vegetation. Frozen-frame checks missed this live rendering regression. Any future render change requires inspecting animated frames and camera movement, not merely a deterministic opening capture.
- User's central art feedback: reference reads as a BIG OPEN WORLD; our level reads as a narrow CORRIDOR. Tail silhouette differs from reference. Water surface looks wrong. Rollback is a baseline restoration, not a resolution of these art deficits.
- Metric audit: image_diff.py compares corresponding pixels after LANCZOS resizing to width960 (reference aspect). RGB MAE is mean absolute channel difference divided by255, not percent pixels different and not a fidelity percentage. Similar blue backgrounds can dominate the average and conceal wrong layout/scale/silhouettes. Changed-pixel percentage and SSIM are separate outputs. No automatic alignment/cropping/color matching occurs under default strict mode.
- The 4% RGB MAE target remains unmet, but must NEVER drive accepting visibly worse art. Judge open-world composition/relative landmark sizes, tail outline, surface appearance, and live surface integrity directly alongside any metrics. Previous rejected build's lower MAE is not evidence of visual improvement.
- Next art pass must start with reference composition and world proportions, then tail modeling and a convincing distant water surface. Do not attempt to solve these with blanket fog/palette changes or a smaller color-error score.
- Audit of rejected frozen browser report:9.756% average RGB error, but82.20% of pixels exceeded mean RGB difference10/255 and SSIM was only0.456. These separate values demonstrate why presenting only MAE was misleading. Formula implementation passes7 known-value tests; the failure was using color MAE as the main art objective.
- Rollback verification: native build launched; frozen and animated captures saved under artifacts/rollback/. Bob wasm-web build/bundle succeeded and existing localhost browser tab was reloaded and visually inspected. Hair/green tail are solid again in these captures. Restored renderer retains historical material warnings/art limitations; do not carry forward the rejected pass's zero-warning or improved-score claims. Only README differs from913f1fb after the revert.
