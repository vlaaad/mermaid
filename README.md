# Agent working memory — Mermaid

## Goal and working rules

- Build a real interactive 3D underwater mermaid scene matching `Blonde-Mermaid-in-Atlantis-Ruins.png`: lighting, composition, level, models, textures and movement. Desktop/browser, keyboard/mouse. Old Intel HD530 laptop; ~30FPS is sufficient. Appearance first, profile meaningful regressions.
- User's latest direction: **ONE visual element per fitting pass.** Freeze camera, geometry, pose/time and all unrelated settings. Match a specific element, inspect a real capture, then move on. Do not mix model/layout/lighting/palette/performance edits.
- Work remains far from the visual target. The near-black diff/90% target is UNMET. Never describe average RGB error as a fidelity percentage. Similar blue water must not count as a missing blue column: verify actual geometry separately.
- All actors stay independent/shared-mesh instances, including fish, rays and vegetation. No actor baking or reference-image backdrop/projection. Static geometry and shaders must survive swimming/camera orbit.
- README is agent memory, not user marketing. Maintain commands, current evidence, pitfalls and next work. User authorizes local Git commits. Preserve their commits/work.

## Current checkpoint — native pass39, 2026-10-16

- Actual captures/metrics/diffs: `artifacts/progress/pass27` through `pass32`. Latest39 MAE11.8485%, SSIM.40599, exact-black.0007716%, within10/channel5.9165%. These are diagnostics, NOT a close match. Baseline4: MAE11.8649%, SSIM.48805, tolerance4.4477%; structural similarity is still worse than baseline.
- Caustic-only passes27→30: gain.22→.66→1.20; then stone response.35 while sand stays1.20. Pattern size/color/motion unchanged. Constants `CAUSTIC_GAIN` and `STONE_CAUSTIC_RESPONSE` in underwater.fp.
- Clear seabed sample at960analysis: pixels(581,443)-(614,516). Reference display-luminance p10/50/90=.4409/.5377/.6604. Gain.22=.4583/.4821/.5120; gain.66=.4611/.4927/.5757; gain1.20=.4613/.5002/.6529. This fits bright seabed caustics, not their shape/color or every receiving surface. Recheck after other lighting/material changes.
- Caustic-shape-only33→34: seamless domain-warped receiver cells, same complete R intensity histogram; G stone/B waves unchanged. Surface gets its own pixel-identical old packed texture(surface_water.png), so the ceiling stays unchanged.34 MAE12.1108/SSIM.40172: curves look more natural but phase/coverage still mismatch.35 is an UNCHANGED repeat, not a brightness trial.
- Brightness-only34→36: gain1.20→.90, stone response still.35.37 tested ONLY sand reflectance(.72 multiplier), projected caustics unchanged. It made two patches too dark.38 uses.90 sand reflectance as a compromise measured across multiple shared floor patches(artifacts/progress/pass38/caustic-brightness.json). Patches still disagree: spatial lighting/pattern position cannot be fixed by a single gain. These are encoded display-luminance diagnostics, not radiance. Shape/coverage/color still differ.
- Sea-color-only passes30→32: bottom/view-ray fog RGB(.050,.49,.86), top(.065,.61,1.0); density remains.016. Same fog function for background and objects. No camera/geometry/caustic changes.
- Clear middle water box[x.495,y.37,x2.52,y2.42]: reference medianRGB(.1137,.6118,.9373), pass30(.0980,.5255,.7882), pass32(.1137,.6078,.9412). Upper box[.51,.17,.55,.23]: reference(.1922,.6863,.9686),32(.1804,.6824,.9490). Middle now within1 RGB level/channel, upper within5. These local results are not whole-image fidelity; patches still differ in gradients/texture.
- Mermaid-position-only pass32→33: model component local offset(.20,-.22,0), maintained by generator. Physical spawn, camera, geometry, pose and lighting unchanged; head/body shift slightly right/down toward reference. Tail shape still wrong.
- Current models: fuller curved tail, asymmetric swept flukes, continuous Blender-finished skin, curled hair, hollow sponges, branching coral, broad ribbon-kelp, curved two-sided manta, independent orange/silver/gold/blue fish. Detailed beveled/eroded architectural meshes. Warm sunlight/transmitted leaf light and cooler ambient shade.
- Render: normal opaque depth-tested pass, NO depth prepass.1024² sun shadow map/4PCF taps; quarter-res32step water scattering, depth-aware upsample/contact shading. Geometry AND post capped1280×720, then one-sample upscale to physical framebuffer. Far400, surfaceY50/plane±1000, ripple contrast fades90–180m, haze165–300m.
- Shared GLBs now indexed by FULL float32 vertex tuple, preserving hard normals/UV seams/color IDs/triangle order. Kelp2016→900vertices, coral10584→4284, fish486→120. Expanded-index reconstruction asserted exact. Actual capture before/after indexing99.8358% pixel-identical, mean difference.001277 RGB levels.
- Native pass24 profile(before extra columns): Frame37.51ms mean/p9585.03,71draws. Pass27:53.51/p9595.86,78draws. Do not claim30FPS or browser performance from native results. Current native movement/boost/rise/orbit checks PASS: W5.029m, boost8.936m(1.777x), rise3.670m, orbit1.286rad. Frame40.657ms mean/p9586.924,78draws. Browser pass32 rebuilt successfully, actual1280×720 canvas:504RAF samples,20.54FPS,48.690ms mean/p95100ms, no console warnings/errors. Evidence artifacts/progress/browser-pass32/. Browser W unfreezes and moves the player. Bundle still32 until next rebuild.

## Geometry presence audit

- `mermaid.lighting {mode:5}` renders actual visible column/arch/window geometry WHITE, all other visible geometry/water BLACK, preserving depth occlusion. No fog/post color. Restore mode0 afterwards. Debug IDs are vertex alpha: columns.1, arches.2, ring.3 under stone params0; normal output stays OPAQUE alpha1.
- `tools/reference_structure.json`:11 coarse hand-marked required-column regions. `tools/structure_check.py` rejects ordinary colored captures, checks visible area/vertical span. It is a presence audit, not proof of correct silhouette/detail; neighboring masonry can overlap boxes. Inspect mask and normal capture too.
- Added/corrected real main/left pair/behind-main/ring-left/right-rear columns and temple lintel. Stable landmark GO names/transforms: `assets/source/landmarks.json`.
- Current audit still flags `left_distant_pillar`, `left_distant_pillar_pair`, `central_distant_pillar` as missing/occluded. Do not hide this by fog/color adjustment. Their visibility/placement is a later isolated geometry task.

## Run, capture, compare

```bash
python3 tools/capture_diff.py
python3 tools/capture_diff.py --output artifacts/progress/pass33 --profile
python3 -m unittest tools.test_image_diff tools.test_structure_check -q
python3 tools/playtest.py
```

- NO required arguments. Reuse/start editor → build/run native → ready → freeze openingtime3 → warm30frames → normal capture → semantic architecture mask/audit → exit engine → ONE RGB diff PNG. Editor stays open. Engine cleanup also runs on failure.
- Default output `artifacts/image-diff/`: `capture.png`+`capture.json`, debug `structure-mask.png`+`structure.json`, **ONE difference** `diff.png`, `metrics.json`. Mask/capture are source/debug evidence, not extra diffs. No HTML/overlay/extra heatmap.
- Diff PNG top=reference+game side by side; bottom=one grayscale RGB RMS error. Inputs NOT converted to grayscale: delta=(refRGB-gameRGB)/255; error=sqrt(mean(delta²)); displayed gray=round(255*sqrt(error)). Fixed curve, exact-equal black; larger error brighter. Never threshold/normalize/grade the diff to satisfy the target.
- Fixed960px analysis width, strict aspect within.5%, LANCZOS resize. No alignment/crop/warp/color fitting. Diff bottom enlarged2x NEAREST. Normal1920×1760 review sheet.
- `black_pixels_percent` is exact RGB equality after fixed analysis. `within_tolerance_pixels_percent` means EVERY channel differs≤10/255; easier intermediate milestone, never changes error pixels. Changed-pixel metric is a different historical measure(mean RGB error>10). MAE=mean absolute RGB error/255; RGB SSIM7×7/sample covariance; blur diagnostic only.
- Optional `--reference`, `--output`, `--max-mae-percent4`(explicit MAE-only gate), `--profile`(90 Main-thread frames→profile.json). Default0=workflow success,1=explicit MAE gate failed,2=real error. Do not equate workflow success with art acceptance.
-16 known-value tests cover RGB-only color changes, one unblended diff, strict/tolerance separation, aspect, and geometry-vs-blue-water presence checks.
- Playtest checks capture stability, W/boost/rise/orbit and native profiler. It closes engines it launches; `--attach` only disconnects. Frozen repeat showed16pixels(max6levels) changing over3.7M, frozen simulation state unchanged. Stability test allows≤8levels at≤.01%pixels and requires identical frozen state; reports exact equality separately. The reference diff remains STRICT.

## Source and asset authoring

```bash
python3 tools/build_assets.py
```

- Deterministic seed73, Y-up meters, forward -Z. Emits shared GLBs/.model/.go, world.collection, obstacles.lua, manifest.json and named landmarks. Current counts in manifest; limits2048model/GO instances.
- `assets/source/mermaid.blend`: editable current mesh. Raw/finished GLBs + signature cache alongside. `tools/finish_character.py` unions skin(.018voxel), smooths3, decimates.55, rejoins untouched hair/fins/clothing with UV/material IDs. `build_assets.py` runs Blender only if raw mesh/script changes; otherwise copies cached finishedGLB. No armature yet; swimming/hair/tail deformation is in the vertex shader.
- Mermaid vertex alpha encodes skin0,tail.25,fluke.5,hair.75,garment1; preserve these IDs and active vertex colors when editing/exporting. Normal fragment alpha is ALWAYS1, not the ID.
- `assets/source/ruins.blend`: column/arch/ring arranged side-by-side for editing. `tools/finish_ruins.py` welds, physically erodes.024, bevels.045/2segments, weighted normals, slight mottling; exports BEFORE display offsets. Finished triangles column5912/arch4626/ring4290. Cached raw/finishedGLBs/signature.
- Manual Blender edits must export back to the relevant `*-finished.glb`, material `reef`, active vertex color/normals/UVs. For ruins export one object at a time with location reset to0(display offsets are not world placement). Cache uses raw generator/script signature: unchanged generation copies that finished file. Changing raw generator/script regenerates and replaces manual finished mesh, so preserve manual source revisions first.
- Limestone bitmap/provenance is in assets/textures; reused only this asset from a rejected pass. No old palette fitting/prepass returned. Shared packed caustics texture R=receiving caustics,G=stone noise,B=water wave field.

## Editor/bridge/browser commands

- CWD `/home/vlaaad/Projects/mermaid`, Defold1.14.0. Editor `http://127.0.0.1:$(cat .internal/editor.port)`. `.internal/editor.token` is SECRET; never print. Editor/engine/BlenderSnap require execution escalation here. Reuse editor; avoid concurrent editor builds.
- Blender5.2.2 `/snap/bin/blender`; system Python has Pillow+NumPy. Installed Defold sources/schema: `/opt/Defold/packages/defold-a81dbb0478e8b73931dc2d671563204f6ac0ef82.jar`. Read local API/schema before guessing.
- Pinned Automation Bridge2.5.0 + managed wrapper automation-bridge-python. Do not edit wrapper. `PYTHONPATH=automation-bridge-python`.

```python
from automation_bridge import editor
p=editor.open_project('.',start_if_needed=False)
g=p.build_and_run(focus=True,timeout=180)
g.wait_for_state('mermaid.ready',True,timeout=45)
g.command('mermaid.capture',{}) # freeze/reset opening; resume command unfreezes
state=g.state('mermaid').value # NOT .data
shot=g.screenshot(after_frames=2,timeout=30)
# save shot.read_bytes(); g.screen() is actual framebuffer/window evidence
profile=g.profiler.capture(frames=120,warmup_frames=5,thread='Main',timeout=45)
g.close_engine(timeout=5) # g.close() alone leaves engine alive
p.bob(options={'platform':'wasm-web','architectures':'wasm-web','archive':True,'variant':'debug',
              'bundle-output':str((p.root/'artifacts/browser').resolve())},
      commands=('build','bundle'),timeout=240)
```

- Bob output must be OUTSIDE build/(reserved). Verified destination artifacts/browser/mermaid. Avoid build_and_run_html5 unless necessary; it opens another Firefox instance. Console lines are strings: `p.console.read().lines`; check WARN/ERROR. Bob timeout: inspect console before retrying; operation may still be running.
- `python3 tools/serve.py` → localhost8765, default Bob bundle. Existing detached server PID/log in artifacts/server.pid/server.log; check health before launching a duplicate.
- Browser `/?debug=1&capture=1&width=1280`: frozen opening, actual1280×720 canvas, rolling600 RAF samples, renderer, **Save frame and timings** button→same-origin server capture→artifacts/scene/browser.png/browser-metrics.json. These are actual web captures; never substitute native. `?debug=1` live, movement unfreezes, `?trace=1` scopes adds overhead.
- WebAssembly has no bridge debug HTTP. Use browser UI controls. Canvas locator `.press('w')` reaches controller; Tab.pressKey was unreliable. `display.update_frequency=0` for web RAF. Check native and browser separately with only one agent game renderer active; do not kill user browser processes.

## Pitfalls, validation and next work

- User rejected7e66368(blue cutout hair/tail/plants); revertc424f31 restored913f1fb. Their later97fcc09 checkpoint is not an accepted art match. Do not reintroduce depth prepass/alpha discard or trust only frozen MAE. Inspect animated frames and camera orbit.
- Render depth attachments sampled later MUST use flags=render.TEXTURE_BIT and not transient. glTF fullscreen UV imports flippedV: each RT lookup restores V; never repair screenshots afterwards.
- Keep fish/fins/hair/kelp two-sided. Stone/sand can cull backs. Fixed sponge wall winding before culling; fish fins use thin predicate. All GLB normals unit/colors bounded/no degenerate poles. Explicit Python float serialization prevents numpy repr leaking into Lua collision files.
- Engine max_time_step.1/controller dtcap.1/collision substeps≤25ms avoid slow motion under load. Controls WASD,Space/E,Ctrl/Q,Shift,drag,R,P. Sphere/AABB sliding and cached broad-phase camera obstruction.
- Prior hand-outlined extruded cliff experiment21–22 looked like stacked shelves; rejected and removed. Do not restore it. Fuller terrain is current, still wrong relative to art. Earlier long notes preserved locally at artifacts/progress/agent-notes-through-pass32.md; per-pass captures/metrics remain under artifacts/progress/.
- Sponge-only38→39: moved sponge_1417 from(-10.7,13,-20), actual rock supportY.549, to(-15.5,14.42,-14), rock topY14.582 and nearby samples14.425–14.633. Only this instance changed, scale/yaw/lighting unchanged. Root slightly embedded, closer to reference upper-left ledge.
- Known moving-view bugs: other unsupported plants remain: coral(-9,9,-20) actualsupportY-2.496; kelp(-11,11,-5) actualsupportY-4.238; sponge(-11,4.5,-11) supportY-4.271. Terrain moves invalidated old placement. Root placement needs explicit supported ledges, not arbitrary screen positions. Artifact check_support.py raycasts actual GLB rock triangles and scene transforms. Hard seabed rectangle edge visible during orbit. Fix each as a separate geometry pass.
- Next: record evidence and commit reviewable checkpoint. Then ONE visual element at a time: mermaid screen placement, remaining column visibility, rock silhouette/position, vegetation shape/placement, caustic pattern, surface texture. Recheck coupled lighting quantities without changing several elements at once. Never call the90%/all-black goal achieved while geometry is missing or the normal scene still looks wrong.
