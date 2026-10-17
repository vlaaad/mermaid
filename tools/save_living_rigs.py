"""Blender CLI: keep inspectable/editable armatures and real action tracks."""
import bpy,sys
from pathlib import Path
root=Path(sys.argv[sys.argv.index('--')+1]);bpy.context.preferences.filepaths.save_version=0
for name in ['mermaid','kelp','ribbon_kelp','fish']:
    bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
    bpy.ops.import_scene.gltf(filepath=str(root/'assets/generated'/f'{name}.glb'))
    bpy.ops.wm.save_as_mainfile(filepath=str(root/'assets/source'/f'{name}-rig.blend'))
