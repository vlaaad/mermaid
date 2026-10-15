# Agent working memory — Mermaid

## Objective and constraints
- Acceptance target: frozen opening-frame RGB MAE≤4% at the unchanged960px-wide comparison, plus reported SSIM and regional errors. The target is UNMET. Do not loosen settings or substitute a baked reference backdrop.
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
- `main/main.script`: inertial swimming, camera-relative WASD, rise Space/E, dive Ctrl/Q, Shift boost, mouse drag orbit, R reset, P profiler; sphere/AABB sliding and a broad-phase-filtered segment/AABB camera arm test with stationary caching. Architecture is collidable; current counts are in `assets/generated/manifest.json`.
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
- `--max-mae-percent 4` is an optional MAE-only gate, not 90% fidelity. Global score can hide a missing small subject; check mermaid/ruin ROIs and actual images.
- Empty black baseline at960x540: RGB MAE39.2437%, SSIM0.0021356. Reference self-check MAE0/SSIM1. Seven known-value tests pass.
- User now requires4% RGB MAE under the existing fixed comparison protocol. This remains unmet; do not treat11% as acceptable or weaken the measurement. First prioritize camera composition, silhouettes, character, water/light. Once accepted, use actual rendered opening frame for tighter regression testing.

## Art direction / lighting checkpoint — 2026-10-15
- User's latest priorities: old laptop, 30 FPS acceptable; focus on look/feel, not 60 FPS. Fish and other future actors must remain independent. Current layout: 571 independent instances, 197 collision boxes. No fish fields, static chunk baking, or shaft cards remain. Shared meshes still instance.
- Compared reference against actual runtime. Primary deficits: uniform blue light, absent cast/contact shade, flat-looking ray planes, sparse material detail and simple procedural character/rocks. Lighting alone cannot close the geometry/art gap.
- Historical first lighting pass: 1024² sun depth map; opaque scene with 3×3 filtered sun shadows; quarter-resolution 32-step world-space water scattering; depth-aware 4-tap upsampling + contact shading + present. Scene RT capped1920×1080. Depth attachments MUST set `flags=render.TEXTURE_BIT` and must not be transient when sampled later.
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

## Historical browser evidence (before4% revision)
- Bob HTML5 build succeeds without launching Firefox. Actual browser screenshot: `artifacts/scene/browser.png` (1280×720). At capture: 600 RAF samples, mean27.37ms /36.54 FPS, p9566.70ms, trace disabled, ANGLE Intel HD530. Average clears30; spikes remain. Do not claim locked30 or60.
- Browser W key reached input and changed Z4.00→3.99 immediately, with frozen false/speed.35m/s; full held-key/boost/vertical/orbit tests passed natively.
- Browser reference diff: MAE11.8050%, SSIM0.48127, coarse9.43657%. Report `artifacts/browser-diff/index.html`; native report remains `artifacts/image-diff/index.html`.
- Normal playable tab is `http://127.0.0.1:8765/`. Local preview was relaunched detached (`subprocess.Popen(...,start_new_session=True)`) because a long-lived exec session received SIGTERM and broke capture POST. PID in `artifacts/server.pid`, logs `artifacts/server.log`. Before relaunch, inspect stored PID/port; avoid duplicate servers. Stop only the known agent-owned server when required.

## Active revision: warnings, shadows, 4% target
- User rejected previous11% and now requires4% with the unchanged RGB MAE protocol. `tools/art_direct.py` applies real settings, captures the engine, records warnings/state, emits regional comparison, and exits1 until the4% gate passes. Rendering success is distinct from that expected acceptance failure.
- Original six material warnings came from unused sampler/constant declarations in blit/volume materials. Removed the declarations; verified native captures report zero runtime warnings/errors. Do not leave cosmetic warnings for later.
- Shadow corrections:2048² fixed-extent map with light-space texel snapping; receiver-plane depth comparison at actual sampled texel centers; bounded world-normal offset; closed stone casters render back faces, while leaves/fins remain double-sided.12-sample spiral filtering grows the penumbra with approximate blocker separation. Buried geometry belowY=-.4 is discarded in the shadow pass. A wrong guessed enum (`graphics.FACE_FRONT`) failed; official correct constant is `graphics.FACE_TYPE_FRONT`. Never repeat this guess.
- `assets/art.json` is the authoritative camera/light preset; generator emits `main/art.lua`. `mermaid.art` applies supported preset fields to the actual running game, resets/freeze camera, and updates renderer constants. Normal play and HTML5 use the same persisted preset. Avoid editing generated Lua directly.
- `tools/tune_art.py --rounds 2` uses real engine captures to fit camera/lighting, then persists the best preset. Objective includes raw global MAE and fixed character/ruin ROIs; ALL final acceptance still uses unchanged `image_diff.py`. Trials and genuine frames go under artifacts; no registration/cropping/recoloring/reference textures in shaders. After fitting, regenerate/build/capture again: the world authoring helper uses the preset when emitting fixed actor positions, so do not carry over an unrechecked fitted score.
- Terrain uses smaller denser strata and supporting foundations (`dense_terrain`), keeping shared instanced meshes and separate future actors. Max model count raised2048 to fit1060 scene models. Camera collision/ground boxes676 in current dense variant; recalc from manifest after generation.
- Ruin window and arch silhouettes separated; added left masonry tower, dominant pillar at reference location, temple column base/lintel, broken floor ruins. Fish/ray reference landmarks are mapped to fixed 3D coordinates at authoring time (`at_screen`); actors remain ordinary independent GOs and drift/deform in play. These are not camera-facing reference cards.
- Water plane raisedY48; fog matches far clear color and surface detail fades at far depth. Warped caustics, finer overhead wave patches, fuller independently animated kelp and foreground ribbon leaves. Actual camera/player presets now differ from original values; read art.json.
- Mermaid has corrected elliptical tube normals, asymmetrical open arm pose, small fingers, curved scale pattern, randomized flowing hair locks/back coverage, warm near-character lighting, greener translucent-looking flukes. Geometry remains a procedural approximation and is still a substantial source of reference mismatch.
- Generated limestone: `assets/textures/limestone-v1.png`, exact prompt/provenance in sibling `.prompt.txt`, built-in imagegen. Triplanar albedo/bump on rock/ruin geometry; separate `sand.material` category8 keeps seabed smooth. Lighting, caustics, shadows and all actors remain dynamic. Retain the source bitmap outside generated/ so regenerating meshes cannot overwrite it.
- Known experiments: a too-tall backing wall blocked the window and was removed; per-ledge foundations preserve support without blocking key silhouettes. Strong surface pattern and bump amplitude created distracting detail; inspect actual output rather than trusting a lower MAE. Do not select a visually worse image only because one metric improves slightly.

## Verification — 2026-10-16 (supersedes earlier checkpoint values)
- Final native frozen frame: RGB MAE9.7681%, SSIM0.46479, coarseMAE7.3404%;4% acceptance gate FAILS. Before this revision11.8134%. Regional MAE: mermaid10.13%, circular ruin7.44%, left foreground10.13%, distant corridor9.57%, surface/light10.05%. Saved final report `artifacts/image-diff/index.html`, full captures/experimental metrics in `artifacts/art-pass/`.
- Final native console: zero warnings/errors. Full `tools/playtest.py` passes: identical frozen frames; W4.92m; Shift+W8.46m (1.72×); rise3.64m; orbit-.79rad. These distances include the documented post-input coast/wait. Native profiler86 draws with depth prepass; Main Frame47.60ms/p9599.77ms at2560×1440 presentation and1920×1080 world target. Browser actual RAF is still the performance truth for its own path.
- Dense scene caused a browser regression to22.6FPS/mean44.26ms/p9583.4ms at1280×720 before the fix. Added opaque depth prepass with the SAME animated vertex shader, then PCF/texture-heavy opaque shading with LEQUAL, depth writes disabled, front-to-back sorting. Predicates depth0 static stone/sand/surface;1 kelp;2 fish;3 player;6 ray;7 dust. Do not drop deformations from depth prepass: it would clip animated fins/leaves incorrectly. Frozen frame metrics unchanged after this pass.
- Defold's default max timestep clamped game dt near33ms even when rendering slower. This made published `frame_ms` underreport stalls and swimming slow down. `engine.max_time_step=.1`, controller cap.1; movement uses collision substeps≤25ms. Browser RAF timings remain independent. Initial warmup frame waits allow15s for60 frames on this laptop; previous5s timeout expired with a reachable advancing engine.
- Material preview defaults now carry actual ambient values and skip sun-map lookup if the light matrix is absent. This avoids black/NaN previews in the Defold resource editor without changing runtime lighting.
- 7 fixed-value image-diff tests pass; Python tools compile; diff whitespace check passes.4% is an explicit unmet visual acceptance check, distinct from code/build/runtime checks.

## Final browser evidence — 2026-10-16
- Final Bob HTML5 build succeeds. Browser dev console warns/errors: none. Actual1280×720 canvas saved to `artifacts/scene/browser.png`;600 RAF samples mean34.95ms /28.61FPS, p9583.40ms, trace off, ANGLE Intel HD530. Recovered from22.6FPS after depth prepass, approximately the user's30FPS tolerance but not locked30; spikes remain.
- Browser W reaches controller, unfreezes, speed.73m/s and Z4.00→3.97 immediately. Native full controls/boost/vertical/orbit and deterministic capture pass after timestep correction.
- Browser reference: RGB MAE9.7560%, SSIM0.45617, coarse7.2991%;4% gate FAILS. Report `artifacts/browser-diff/index.html`; screenshot/hash/settings/regions retained there. This is the final emitted build's score, not the best temporary tuning state.
- Next visual work: improve reference-specific geometry/silhouettes/materials and architecture placement. Current lighting/camera search has diminishing gains; further blanket tuning cannot replace modeling. Keep4% as the unmet acceptance target and retain the fixed measurement protocol. Next passes must improve both actual appearance and honest measurements, not substitute a reference-backed image or flatten future actors.
