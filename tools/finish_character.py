"""Blender CLI: join/smooth the skin while preserving hair, clothing and fin meshes.

Called by build_assets.py. Vertex alpha encodes shader material IDs, not opacity.
"""
import sys
from pathlib import Path
import bpy
import bmesh

raw, finished, blend = map(Path, sys.argv[sys.argv.index('--')+1:])
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
bpy.ops.import_scene.gltf(filepath=str(raw))
original = next(o for o in bpy.context.scene.objects if o.type == 'MESH')
attribute = original.data.color_attributes.active_color or original.data.color_attributes[0]
color_name = attribute.name

def alpha(poly):
    index = poly.loop_indices[0] if attribute.domain == 'CORNER' else poly.vertices[0]
    return attribute.data[index].color[3]

skin_faces = [p.index for p in original.data.polygons if alpha(p) < .1]
if not skin_faces:
    raise RuntimeError('No skin material IDs found; refusing to overwrite character')
mesh = bpy.data.meshes.new('Continuous skin')
mesh.from_pydata([v.co[:] for v in original.data.vertices], [], [original.data.polygons[i].vertices[:] for i in skin_faces])
skin = bpy.data.objects.new('Continuous skin', mesh)
bpy.context.collection.objects.link(skin)
skin.matrix_world = original.matrix_world.copy()
material = original.data.materials[0]
skin.data.materials.append(material)
# Weld the triangle export before voxel union, removing all unused non-skin vertices.
bm = bmesh.new();bm.from_mesh(mesh)
bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=.00001)
bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
bm.to_mesh(mesh);bm.free()
bpy.ops.object.select_all(action='DESELECT')
skin.select_set(True);bpy.context.view_layer.objects.active=skin
skin.data.remesh_voxel_size=.018
bpy.ops.object.voxel_remesh()
smooth=skin.modifiers.new('Sculpt surface relaxation','SMOOTH');smooth.factor=.35;smooth.iterations=3
bpy.ops.object.modifier_apply(modifier=smooth.name)
decimate=skin.modifiers.new('Skin topology reduction','DECIMATE');decimate.ratio=.55
bpy.ops.object.modifier_apply(modifier=decimate.name)
for p in skin.data.polygons:p.use_smooth=True
colors=skin.data.color_attributes.new(name=color_name,type='FLOAT_COLOR',domain='CORNER')
for c in colors.data:c.color=(.93,.70,.47,0.0)
skin.data.color_attributes.active_color=colors
skin.data.uv_layers.new(name='UVMap')
# Preserve every non-skin face and its original UV/color material ID.
bm=bmesh.new();bm.from_mesh(original.data);bm.faces.ensure_lookup_table()
bmesh.ops.delete(bm,geom=[bm.faces[i] for i in skin_faces],context='FACES')
bmesh.ops.delete(bm,geom=[v for v in bm.verts if not v.link_faces],context='VERTS')
bm.to_mesh(original.data);bm.free()
original.select_set(True);skin.select_set(True);bpy.context.view_layer.objects.active=original
bpy.ops.object.join()
original.name='Mermaid';original.data.name='Mermaid authored mesh'
original.data.color_attributes.active_color=original.data.color_attributes[color_name]
# The only glTF material maps to the existing Defold mermaid material.
material.name='reef'
blend.parent.mkdir(parents=True,exist_ok=True)
bpy.context.preferences.filepaths.save_version=0
bpy.ops.wm.save_as_mainfile(filepath=str(blend))
props=bpy.ops.export_scene.gltf.get_rna_type().properties['export_vertex_color'].enum_items
mode='ACTIVE' if 'ACTIVE' in props.keys() else 'MATERIAL'
bpy.ops.export_scene.gltf(filepath=str(finished),export_format='GLB',use_selection=True,
                         export_animations=False,export_cameras=False,export_lights=False,
                         export_vertex_color=mode,export_normals=True,export_texcoords=True)
print('CHARACTER_FINISHED vertices',len(original.data.vertices),'faces',len(original.data.polygons))
